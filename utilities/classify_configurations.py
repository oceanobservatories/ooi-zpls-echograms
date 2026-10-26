#!/usr/bin/env python
"""
Inventory EK80 raw files by recording configuration.

Reads the datagram framing, the XML0 Configuration/Parameter datagrams,
and the fixed 140-byte RAW3 sample headers of each Simrad .raw file. Each
pinged channel's pulse form (CW, LFM, FMD from Parameter datagrams) and
sample encoding (power or complex from the RAW3 datatype bits) is recorded
and used to define the instrument configuration.

Ping timing is also recorded, to assess whether pings can interfere: each
channel's pulse duration and frequency band (Parameter datagrams), each
channel's median ping interval, and the mean number of channels sharing a
ping time (RAW3 timestamps; about 1 for sequential transmission, about the
channel count for simultaneous transmission).

Writes two CSVs to the output directory:

ek80_file_inventory.csv
    One row per file. Resumable: files already listed are skipped on rerun,
    except rows with status error or truncated, which are rescanned (the
    newest file in a live tree is usually still being written). A CSV
    written by an older version of this script (different columns) is not
    appended to; use a new output directory.
ek80_config_runs.csv
    Consecutive files (per site) with an identical configuration signature
    collapsed into date ranges, with a full/reduced duty-cycle label for
    broadband runs derived from the median inter-file cadence. Each run
    also reports its pulse durations, frequency bands, median shortest
    ping interval and median channels per ping time, and flags runs whose
    ping interval is shorter than the two-way travel time to the sea
    surface (ping_overlap), i.e. where the surface echo of one ping can
    arrive after the next ping is transmitted.

Usage
-----
python classify_configurations.py -o OUTPUT_DIR [-w WORKERS] SITE=ROOT [SITE=ROOT ...]
"""
import argparse
import csv
import os
import re
import statistics
import struct
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

NT_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)
RAW3_HEADER = struct.Struct('<128shxxll')  # channel_id, datatype, spare, offset, count
PULSE_FORMS = {'0': 'CW', '1': 'LFM', '2': 'FMD'}
FULL_DUTY_MAX_CADENCE_MIN = 30.0  # same threshold as classify_recording_mode
SOUND_SPEED = 1480.0  # m/s, deliberately slow so the surface round-trip estimate errs long (conservative)
FNAME_RE = re.compile(r'D(\d{8})-T(\d{6})')
RETRY_STATUSES = ('error', 'truncated')
FIELDS = ['site', 'path', 'status', 'file_time', 'ping_start', 'ping_end', 'size_mb', 'n_channels', 'category',
          'signature', 'channel_ids', 'pulse_ms', 'band_khz', 'ping_interval_s', 'min_ping_interval_s',
          'pings_per_time']


def _nt_time(low: int, high: int) -> datetime:
    """
    Convert a Windows NT timestamp (100 ns ticks since 1601-01-01 UTC) to
    an aware datetime.
    """
    return NT_EPOCH + timedelta(microseconds=((high << 32) | low) / 10)


def _encoding(datatype: int) -> str:
    """
    Decode the RAW3 datatype bit field: bit 0 power, bits 2-3 complex
    (float16 or float32 samples).
    """
    if datatype & 0b1:
        return 'power'
    if datatype & 0b1100:
        return 'complex'
    return f'unknown({datatype})'


def _parse_xml0(payload: bytes) -> tuple[str, dict[str, dict]]:
    """
    Parse an XML0 datagram payload.

    Returns the root tag and a per-channel dict of {'form', 'freq', 'band',
    'pulse'}. Configuration datagrams give only the transducer frequency.
    Parameter datagrams give the pulse form, the frequency (the CW
    frequency or the FM sweep midpoint), the band in kHz ('120' for CW,
    '95-160' for FM) and the pulse duration in seconds. Other XML0 types
    return an empty dict.
    """
    try:
        root = ET.fromstring(payload.rstrip(b'\x00'))
    except ET.ParseError:
        return 'ParseError', {}

    entries: dict[str, dict] = {}
    if root.tag == 'Configuration':
        for ch in root.iter('Channel'):
            td = ch.find('Transducer')
            freq = td.get('Frequency') if td is not None else None
            entries[(ch.get('ChannelID') or '').strip()] = {
                'form': None, 'freq': float(freq) if freq else None, 'band': None, 'pulse': None}
    elif root.tag == 'Parameter':
        for ch in root.iter('Channel'):
            f0, f1 = ch.get('FrequencyStart'), ch.get('FrequencyEnd')
            code = ch.get('PulseForm') or ('1' if f0 else '0')
            if ch.get('Frequency'):
                freq = float(ch.get('Frequency'))
                band = f'{freq / 1000:g}'
            elif f0 and f1:
                freq = (float(f0) + float(f1)) / 2
                band = f'{float(f0) / 1000:g}-{float(f1) / 1000:g}'
            else:
                freq, band = None, '?'
            duration = ch.get('PulseDuration') or ch.get('PulseLength')
            entries[(ch.get('ChannelID') or '').strip()] = {
                'form': PULSE_FORMS.get(code, f'form{code}'), 'freq': freq, 'band': band,
                'pulse': float(duration) if duration else None}
    return root.tag, entries


def _categorize(forms: set[str], encodes: set[str]) -> str:
    """
    Map the union of pulse forms and encodings over all pinged channels to
    a coarse configuration category.
    """
    if not encodes:
        return 'no_pings'
    if forms and forms <= {'CW'}:
        if encodes == {'power'}:
            return 'NB_power'
        if encodes == {'complex'}:
            return 'NB_complex'
        return 'NB_mixed_encode'
    if 'CW' in forms:
        return 'BB_with_CW'
    if forms:
        return 'BB_without_CW'
    return 'unknown_pulse_form'


def _median_interval(times: list[datetime]) -> float | None:
    """
    Return the median interval in seconds between consecutive ping times,
    or None if there are fewer than two pings.
    """
    if len(times) < 2:
        return None
    times = sorted(times)
    return statistics.median((b - a).total_seconds() for a, b in zip(times, times[1:]))


def scan_file(site: str, path: str) -> dict[str, object]:
    """
    Walk the datagrams of one .raw file and return its inventory record.

    Status is ok, truncated (final datagram incomplete; the file is still
    classified from what was read), ek60 (legacy CON0/RAW0 datagrams
    found), or error.
    """
    rec: dict[str, object] = dict.fromkeys(FIELDS, '')
    rec.update(site=site, path=path)
    match = FNAME_RE.search(Path(path).name)
    if match:
        ftime = datetime.strptime(''.join(match.groups()), '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        rec['file_time'] = ftime.isoformat(timespec='seconds')

    config_freq: dict[str, float | None] = {}
    param_freq: dict[str, float | None] = {}
    forms: dict[str, set[str]] = defaultdict(set)
    encodes: dict[str, set[str]] = defaultdict(set)
    pulses: dict[str, set[float]] = defaultdict(set)
    bands: dict[str, set[str]] = defaultdict(set)
    ping_times: dict[str, list[datetime]] = defaultdict(list)
    all_times: set[int] = set()  # ping times across all channels, rounded to 1 ms
    n_raw3 = 0
    xml_cache: dict[bytes, tuple[str, dict]] = {}
    first = last = None
    status = 'ok'

    try:
        size = os.path.getsize(path)
        rec['size_mb'] = round(size / 2**20, 1)
        with open(path, 'rb') as fh:
            while True:
                pos = fh.tell()
                length_bytes = fh.read(4)
                if len(length_bytes) < 4:
                    break
                (length,) = struct.unpack('<l', length_bytes)
                if length < 12 or pos + 8 + length > size:
                    status = 'truncated'
                    break
                head = fh.read(12)
                dg_type = head[:4]
                if dg_type == b'XML0':
                    payload = fh.read(length - 12)
                    if payload not in xml_cache:
                        xml_cache[payload] = _parse_xml0(payload)
                    tag, entries = xml_cache[payload]
                    for cid, entry in entries.items():
                        if tag == 'Configuration':
                            config_freq[cid] = entry['freq']
                        elif tag == 'Parameter':
                            forms[cid].add(entry['form'])
                            param_freq[cid] = entry['freq']
                            bands[cid].add(entry['band'])
                            if entry['pulse'] is not None:
                                pulses[cid].add(entry['pulse'])
                elif dg_type == b'RAW3':
                    cid_raw, datatype, _, _ = RAW3_HEADER.unpack(fh.read(RAW3_HEADER.size))
                    cid = cid_raw.split(b'\x00', 1)[0].decode('ascii', 'replace').strip()
                    encodes[cid].add(_encoding(datatype))
                    last = _nt_time(*struct.unpack('<LL', head[4:12]))
                    first = first or last
                    ping_times[cid].append(last)
                    all_times.add(round(last.timestamp() * 1000))
                    n_raw3 += 1
                elif dg_type in (b'CON0', b'RAW0'):
                    status = 'ek60'
                    break
                fh.seek(pos + 4 + length + 4)
    except (OSError, struct.error) as err:
        rec['status'] = f'error: {err}'
        return rec

    def _freq(cid: str) -> float:
        return config_freq.get(cid) or param_freq.get(cid) or 0.0

    pinged = sorted(encodes, key=lambda c: (_freq(c), c))
    parts = []
    for cid in pinged:
        khz = f'{_freq(cid) / 1000:g}kHz' if _freq(cid) else '?kHz'
        parts.append(f"{khz}:{'/'.join(sorted(forms.get(cid, {'?'})))}:{'/'.join(sorted(encodes[cid]))}")
    all_forms = set().union(*(forms.get(c, set()) for c in pinged))
    all_encodes = set().union(*(encodes[c] for c in pinged))

    intervals = {c: _median_interval(ping_times[c]) for c in pinged}
    valid_intervals = [v for v in intervals.values() if v is not None]

    rec.update(
        status=status,
        ping_start=first.isoformat(timespec='seconds') if first else '',
        ping_end=last.isoformat(timespec='seconds') if last else '',
        n_channels=len(pinged),
        category='EK60' if status == 'ek60' else _categorize(all_forms, all_encodes),
        signature='|'.join(parts),
        channel_ids=';'.join(pinged),
        pulse_ms=';'.join('/'.join(f'{p * 1000:g}' for p in sorted(pulses[c])) or '?' for c in pinged),
        band_khz=';'.join('/'.join(sorted(bands[c])) or '?' for c in pinged),
        ping_interval_s=';'.join(f'{intervals[c]:.3f}' if intervals[c] is not None else '?' for c in pinged),
        min_ping_interval_s=round(min(valid_intervals), 3) if valid_intervals else '',
        pings_per_time=round(n_raw3 / len(all_times), 2) if all_times else '',
    )
    return rec


def _surface_round_trip_s(site: str) -> float | None:
    """
    Two-way travel time in seconds from an upward-looking sensor to the sea
    surface, from the site's nominal deployed depth in the package's
    site_config, or None if the site (or the package) is not available.
    """
    try:
        from ooi_zpls_echograms.zpls_echogram import site_config
    except ImportError:
        return None
    cfg = site_config.get(site)
    if cfg is None or cfg.get('instrument_orientation') != 'up':
        return None
    return 2 * cfg['deployed_depth'] / SOUND_SPEED


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse consecutive files (per site) sharing a configuration signature
    into date-range runs, label broadband runs full or reduced duty by
    median inter-file cadence, and flag runs whose ping interval is shorter
    than the two-way travel time to the surface.
    """
    df = df.drop_duplicates('path', keep='last')
    df = df[~df['status'].str.startswith('error')].copy()
    df['t0'] = pd.to_datetime(df['ping_start'].where(df['ping_start'] != '', df['file_time']), utc=True)
    df['t1'] = pd.to_datetime(df['ping_end'].where(df['ping_end'] != '', df['file_time']), utc=True)
    df['size_mb'] = pd.to_numeric(df['size_mb'], errors='coerce')
    df['min_ping_interval_s'] = pd.to_numeric(df['min_ping_interval_s'], errors='coerce')
    df['pings_per_time'] = pd.to_numeric(df['pings_per_time'], errors='coerce')
    df = df.sort_values(['site', 't0'])

    by_site = df.groupby('site')
    df['cadence_min'] = (by_site['t0'].shift(-1) - df['t0']).dt.total_seconds() / 60
    df['run'] = (df['signature'] != by_site['signature'].shift()).cumsum()

    runs = df.groupby('run').agg(
        site=('site', 'first'),
        category=('category', 'first'),
        start=('t0', 'min'),
        end=('t1', 'max'),
        n_files=('path', 'size'),
        median_cadence_min=('cadence_min', 'median'),
        total_gb=('size_mb', lambda s: round(s.sum() / 1024, 1)),
        pulse_ms=('pulse_ms', 'first'),
        band_khz=('band_khz', 'first'),
        median_min_ping_interval_s=('min_ping_interval_s', 'median'),
        median_pings_per_time=('pings_per_time', 'median'),
        signature=('signature', 'first'),
    ).reset_index(drop=True)

    is_bb = runs['category'].str.startswith('BB')
    cadence = runs['median_cadence_min']
    runs['duty'] = ''
    runs.loc[is_bb & (cadence < FULL_DUTY_MAX_CADENCE_MIN), 'duty'] = 'full'
    runs.loc[is_bb & (cadence >= FULL_DUTY_MAX_CADENCE_MIN), 'duty'] = 'reduced'
    runs.loc[is_bb & cadence.isna(), 'duty'] = 'unknown'
    runs['median_cadence_min'] = runs['median_cadence_min'].round(1)

    round_trip = runs['site'].map({site: _surface_round_trip_s(site) for site in runs['site'].unique()})
    interval = runs['median_min_ping_interval_s']
    known = round_trip.notna() & interval.notna()
    runs['surface_round_trip_s'] = round_trip.round(3)
    runs['ping_overlap'] = ''
    runs.loc[known, 'ping_overlap'] = (interval[known] < round_trip[known]).map({True: 'yes', False: 'no'})
    runs['median_min_ping_interval_s'] = interval.round(3)
    runs['median_pings_per_time'] = runs['median_pings_per_time'].round(2)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description='Inventory EK80 raw files by recording configuration.')
    parser.add_argument('roots', nargs='+', help='SITE=/path/to/raw/tree (searched recursively for *.raw)')
    parser.add_argument('-o', '--output-dir', type=Path, required=True)
    parser.add_argument('-w', '--workers', type=int, default=8)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    files_csv = args.output_dir / 'ek80_file_inventory.csv'

    done: set[str] = set()
    if files_csv.exists():
        with files_csv.open(newline='') as fh:
            header = next(csv.reader(fh), [])
        if header != FIELDS:
            parser.error(f'{files_csv} was written by a different version of this script (columns differ); '
                         f'use a new --output-dir')
        prev = pd.read_csv(files_csv, keep_default_na=False, usecols=['path', 'status'])
        done = set(prev.loc[~prev['status'].str.startswith(RETRY_STATUSES), 'path'])

    todo: list[tuple[str, str]] = []
    for spec in args.roots:
        site, root = spec.split('=', 1)
        todo += [(site, str(p)) for p in sorted(Path(root).rglob('*.raw')) if str(p) not in done]
    print(f'{len(done)} files already inventoried, {len(todo)} to scan', flush=True)

    write_header = not files_csv.exists()
    with files_csv.open('a', newline='') as fh, ProcessPoolExecutor(args.workers) as pool:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        futures = [pool.submit(scan_file, site, path) for site, path in todo]
        for n, future in enumerate(as_completed(futures), 1):
            writer.writerow(future.result())
            if n % 500 == 0:
                fh.flush()
                print(f'  {n}/{len(todo)}', flush=True)

    runs = summarize(pd.read_csv(files_csv, keep_default_na=False))
    runs_csv = args.output_dir / 'ek80_config_runs.csv'
    runs.to_csv(runs_csv, index=False)
    print(runs[['site', 'category', 'duty', 'start', 'end', 'n_files', 'median_cadence_min', 'pulse_ms',
                'median_min_ping_interval_s', 'median_pings_per_time', 'ping_overlap']].to_string(index=False))
    print(f'\nPer-file: {files_csv}\nRuns:     {runs_csv}')


if __name__ == '__main__':
    main()

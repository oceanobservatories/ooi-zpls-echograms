#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Near real-time processing for the cabled EK80 bioacoustic sonars
(CE02SHBP, CE04OSPS). Intended to run once nightly after the previous
calendar day's raw files have all been collected.
"""
import argparse
import glob
import os
import re
import shutil

from datetime import date, datetime, timedelta, UTC
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from PIL import Image

from .zpls_echogram import (
    EXPECTED_FREQUENCY_COUNT,
    _previous_day_last_file,
    attributes,
    ek_file_list,
    generate_echogram,
    process_sonar_data,
    set_file_name,
    site_config,
)

# fixed resample parameters for the cabled sites
RESAMPLE_FREQ = '15Min'
TIME_SHIFT = pd.to_timedelta(450, unit='sec')
MAX_GAP = '45Min'
WEEK_GRID_EPOCH = date(2012, 1, 1)


def week_bounds(day: date) -> tuple[date, date]:
    """
    Find the (start, stop) bounds, stop exclusive, of the 7-day week
    that the given calendar day falls in, using the same grid (anchored
    to 2012-01-01) as the backlog batch scripts.

    :param day: the calendar day to locate within the weekly grid.
    :return: (week_start, week_stop) as date objects; week_stop is
        exclusive (the week runs up to, but not including, week_stop).
    """
    days_since_epoch = (day - WEEK_GRID_EPOCH).days
    week_index = days_since_epoch // 7
    week_start = WEEK_GRID_EPOCH + timedelta(days=7 * week_index)
    week_stop = week_start + timedelta(days=7)
    return week_start, week_stop


def week_output_paths(site: str, proc_root: str, day: date) -> tuple[str, str, str, str]:
    """
    Build the week's processed output directory and file name prefix
    for a given day.

    :param site: 8-letter OOI site code (CE02SHBP or CE04OSPS).
    :param proc_root: processed output parent directory, one level
        above the per-year 'processed' folders.
    :param day: any calendar day within the target week.
    :return: (output_directory, file_name, week_start_str,
        week_stop_str); the latter two as YYYYMMDD strings.
    """
    week_start, week_stop = week_bounds(day)
    week_start_str = week_start.strftime('%Y%m%d')
    week_stop_str = week_stop.strftime('%Y%m%d')
    output_directory = os.path.join(
        proc_root, str(week_stop.year), 'processed', f'{week_start_str}-{week_stop_str}'
    )
    file_name = set_file_name(site, [week_start_str, week_stop_str])
    return output_directory, file_name, week_start_str, week_stop_str


def drop_converted_stores(output_directory: str, raw_files: list[str]) -> int:
    """Delete the zarr stores of the given raw files so they are reconverted"""
    removed = 0
    for raw_file in raw_files:
        store = Path(output_directory) / f'{Path(raw_file).stem}.zarr'
        if store.is_dir():
            shutil.rmtree(store)
            removed += 1
    return removed


def convert_yesterday(site: str, data_root: str, proc_root: str, zpls_model: str, yesterday: date) -> None:
    """
    Convert and process "yesterday" into its full-resolution daily
    NetCDF. Uses a one-day window (yesterday up to, but not including,
    today); the backward buffer (previous day's last file) is picked up
    inside process_sonar_data. The converted stores for yesterday's files
    and the buffer file are deleted first so files that were still being
    synced on an earlier run are reconverted from scratch.

    :param site: 8-letter OOI site code (CE02SHBP or CE04OSPS).
    :param data_root: raw data parent directory, one level ABOVE the
        per-year folders (e.g. .../mj01c/ZPLSCB101_10.33.13.7, not
        .../mj01c/ZPLSCB101_10.33.13.7/2023).
    :param proc_root: processed output parent directory, one level
        above the per-year 'processed' folders.
    :param zpls_model: 'EK80' (the only model this module targets).
    :param yesterday: the calendar day to convert and process.
    """
    output_directory, file_name, _, _ = week_output_paths(site, proc_root, yesterday)
    os.makedirs(output_directory, exist_ok=True)

    data_directory = os.path.join(data_root, str(yesterday.year))
    tilt_correction = site_config[site]['tilt_correction']

    # one-day window [yesterday, yesterday + 1); the backward buffer is picked up inside process_sonar_data
    dates = [yesterday.strftime('%Y%m%d'), (yesterday + timedelta(days=1)).strftime('%Y%m%d')]

    # raw files may have been rsync'ed while still being written, so always reconvert the files in play
    day_files = sorted(f for sub in ek_file_list(data_directory, dates) for f in sub)
    buffer_file = _previous_day_last_file(data_directory, dates[0], zpls_model)
    n_removed = drop_converted_stores(output_directory, day_files + ([buffer_file] if buffer_file else []))
    print(f'{site}: removed {n_removed} existing converted store(s) for {dates[0]}')

    process_sonar_data(
        site, data_directory, output_directory, dates, zpls_model, None,
        tilt_correction, file_name, RESAMPLE_FREQ, TIME_SHIFT, MAX_GAP,
    )


def remove_buffer_copies(output_directory: str, week_start_str: str) -> None:
    """Delete zarr stores in the week folder whose raw file started before the week (backward buffer copies)."""
    for store in Path(output_directory).glob('*.zarr'):
        match = re.search(r'D(\d{8})-T\d{6}', store.name)
        if match and match.group(1) < week_start_str:
            shutil.rmtree(store)
            print(f'removed buffer copy {store.name}')


def regenerate_weekly_average(site: str, proc_root: str, day: date) -> None:
    """
    Regenerate this week's averaged NetCDF and echogram PNG from every
    _Full_YYYYMMDD.nc file currently present in the week's output
    folder (however many days have accumulated so far), overwriting
    whatever was there before. Skips writing if no daily files exist yet,
    or if fewer than the expected number of frequency channels have valid
    data.

    :param site: 8-letter OOI site code (CE02SHBP or CE04OSPS).
    :param proc_root: processed output parent directory, one level
        above the per-year 'processed' folders.
    :param day: any calendar day within the target week (used only to
        locate the week and its folder).
    """
    output_directory, file_name, week_start_str, week_stop_str = week_output_paths(site, proc_root, day)

    daily_files = sorted(glob.glob(os.path.join(output_directory, file_name + '_Full_*.nc')))
    if not daily_files:
        print(f'{site}: no daily files present yet for {week_start_str}-{week_stop_str}, '
              f'skipping weekly average/echogram regeneration.')
        return

    # reduce one day at a time so only one day of full-resolution data is in memory (protects against OOM)
    day_avgs = []
    for daily_file in daily_files:
        with xr.open_dataset(daily_file) as daily_ds:
            shifted = daily_ds.assign_coords(ping_time=daily_ds['ping_time'] + TIME_SHIFT)
            day_avgs.append(shifted.resample(ping_time=RESAMPLE_FREQ).mean(dim='ping_time', skipna=True,
                                                                           keep_attrs=True).compute())
    # a bin spanning midnight appears once per day; this resample merges the two halves and restores the grid
    avg = xr.concat(day_avgs, dim='ping_time', data_vars='minimal', coords='minimal', compat='override')
    # echo_range/nominal_depth are per-day coordinates; take the union across days (matches the backlog fallback)
    for coord in ('echo_range', 'nominal_depth'):
        merged = xr.concat([d[coord].reset_coords(drop=True) for d in day_avgs], dim='day',
                           join='outer').max('day', skipna=True)
        avg = avg.assign_coords({coord: merged})
    avg = avg.resample(ping_time=RESAMPLE_FREQ).mean(keep_attrs=True)
    avg = avg.interpolate_na(dim='ping_time', max_gap=MAX_GAP)
    avg = avg.dropna('range_sample', subset=['echo_range'])

    # same channel-count guard zpls_echogram() applies before plotting
    expected_count = EXPECTED_FREQUENCY_COUNT.get('EK80')
    actual_count = avg.sizes.get('frequency_nominal')
    if expected_count is not None and actual_count != expected_count:
        print(f'{site}: only {actual_count} of the expected {expected_count} frequency channels reported valid '
              f'data for {week_start_str}-{week_stop_str} '
              f'(frequencies present: {list(avg.frequency_nominal.values)}). Skipping echogram generation.')
        return

    cfg = site_config[site]
    generate_echogram(
        avg, site, cfg['long_name'], cfg['deployed_depth'], output_directory, file_name,
        [week_start_str, week_stop_str],
        vertical_range=cfg['vertical_range'], colorbar_range=cfg['colorbar_range'],
    )

    # add the OOI logo watermark
    echogram_path = os.path.join(output_directory, file_name + '.png')
    echo_image = Image.open(echogram_path)
    # noinspection PyTypeChecker
    ooi_image = Image.open(files('ooi_zpls_echograms').joinpath('ooi-logo.png'))
    width, height = echo_image.size
    transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    transparent.paste(echo_image, (0, 0))
    if max(cfg['vertical_range']) > 99:
        transparent.paste(ooi_image, (96, 15), mask=ooi_image)
    else:
        transparent.paste(ooi_image, (80, 15), mask=ooi_image)
    transparent.save(echogram_path)

    # write the averaged NetCDF
    avg['ping_time'] = avg['ping_time'].values.astype(np.float64) / 10.0 ** 9
    avg.attrs = attributes['global']
    avg.attrs['instrument_orientation'] = cfg['instrument_orientation']
    for v in avg.variables:
        avg[v].attrs = attributes[v]
    avg_file = os.path.join(output_directory, file_name) + '_Averaged.nc'
    avg.to_netcdf(avg_file, mode='w', format='NETCDF4', engine='h5netcdf')

    print(f'{site}: regenerated weekly average and echogram for {week_start_str}-{week_stop_str} '
          f'from {len(daily_files)} daily file(s).')


def run_nightly(site: str, data_root: str, proc_root: str, zpls_model: str, day: date | None = None) -> None:
    """
    Run one full nightly cycle: convert "yesterday", then regenerate the
    week's averaged NetCDF and echogram from whatever daily files exist
    so far this week.

    :param site: 8-letter OOI site code (CE02SHBP or CE04OSPS).
    :param data_root: raw data parent directory, one level above the
        per-year folders.
    :param proc_root: processed output parent directory, one level
        above the per-year 'processed' folders.
    :param zpls_model: 'EK80' (the only model this module targets).
    :param day: override for "yesterday", mainly for testing; defaults
        to the actual calendar day before today, UTC (matching the UTC
        time encoding already used throughout the processed NetCDF
        output).
    """
    yesterday = day if day is not None else datetime.now(UTC).date() - timedelta(days=1)
    convert_yesterday(site, data_root, proc_root, zpls_model, yesterday)
    regenerate_weekly_average(site, proc_root, yesterday)
    output_directory, _, week_start_str, _ = week_output_paths(site, proc_root, yesterday)
    remove_buffer_copies(output_directory, week_start_str)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Live (nightly) processing for a cabled EK80 bioacoustic sonar.')
    parser.add_argument('-s', '--site', dest='site', type=str, required=True,
                        help='OOI 8-letter site code (CE02SHBP or CE04OSPS).')
    parser.add_argument('-d', '--data-root', dest='data_root', type=str, required=True,
                        help='Raw data parent directory, one level above the per-year folders '
                             '(e.g. /node_data/mj01c/ZPLSCB101_10.33.13.7).')
    parser.add_argument('-o', '--proc-root', dest='proc_root', type=str, required=True,
                        help='Processed output parent directory, one level above the per-year '
                             "'processed' folders (e.g. /data/zplsc/CE02SHBP/MJ01C/07-ZPLSCB101).")
    parser.add_argument('-zm', '--zpls-model', dest='zpls_model', type=str, default='EK80',
                        help="ZPLS instrument model (default 'EK80'; this module only supports EK80).")
    parser.add_argument('--date', dest='date_override', type=str, required=False,
                        help='YYYYMMDD override for "yesterday", for testing. Defaults to the actual '
                             'calendar day before today, UTC.')
    args = parser.parse_args(argv)

    site = args.site.upper()
    if site not in site_config:
        parser.error(f'Unrecognized site: {site}')

    zpls_model = args.zpls_model.upper()
    if zpls_model != 'EK80':
        parser.error('This module only supports EK80 (the cabled backlog scripts and process_sonar_data '
                     'cover other cases).')

    day = datetime.strptime(args.date_override, '%Y%m%d').date() if args.date_override else None

    run_nightly(site, os.path.abspath(args.data_root), os.path.abspath(args.proc_root), zpls_model, day)


if __name__ == '__main__':
    main()

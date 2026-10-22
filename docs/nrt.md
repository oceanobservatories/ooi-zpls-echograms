# Near Real-Time Processing for the Cabled EK80 Sites

This document describes the nightly processing of the cabled EK80 bioacoustic sonars at
[CE02SHBP](https://oceanobservatories.org/site/ce02shbp/) and [CE04OSPS](https://oceanobservatories.org/site/ce04osps/)
by `ooi_zpls_echograms.cabled_nrt_echogram`, and the weekly repair run by `utilities/weekly_trailing_backlog.sh`. For
installing the container image and scheduling these jobs, see [deployment.md](deployment.md).

## What it produces

Processing follows the same weekly grid as the backlog scripts: 7-day weeks starting on Sunday, anchored to 2012-01-01.
Each week has its own output folder, `<PROC_ROOT>/<year of the week's stop date>/processed/<start>-<stop>/`, where the
stop date is exclusive. A week that crosses New Year is filed under the new year.

Every night, for the previous UTC day, the job:

1. Converts and calibrates that day's raw files and writes the day's full-resolution file,
   `<SITE>_Bioacoustic_Echogram_<start>-<stop>_Calibrated_Sv_Full_<YYYYMMDD>.nc`, into the week's folder, along with
   one converted `.zarr` store per raw file.
2. Regenerates the week's averaged file (`..._Calibrated_Sv_Averaged.nc`) and echogram (`..._Calibrated_Sv.png`) from
   all the daily files present in the week's folder so far. The echogram for the current week therefore grows by
   one day each night until the week is complete.
3. Removes converted stores in the week's folder that belong to raw files from before the week started (see
   [Backward buffer copies](#backward-buffer-copies)).

## How a nightly run works

### Converting the day

The run uses a one-day window: the target day only, with no files from the following day. The pipeline needs the raw
file that was being written as the day started (the previous day's last file), because pings from that file can run
past midnight into the target day. `process_sonar_data` picks that file up automatically as a backward buffer.

Before converting, the job deletes any existing converted stores for the target day's raw files and for the backward
buffer file, so every file in play is reconverted from scratch. This is deliberate. RCA's collection server copies raw
files into the archive on its own schedule, and a file can be copied while it is still being written. A store converted
from a partial copy would otherwise be reused by every later run. Reconverting costs about a minute per file, which is
small next to the cost of silently keeping truncated data.

### Regenerating the week

The weekly average is built one day at a time so that only one day of full-resolution data is held in memory: each
daily file is shifted onto the bin centers, resampled to 15-minute means, and released before the next is opened. The
per-day results are then concatenated and resampled again, which merges the 15-minute bin that spans each midnight from
its two halves. Range and depth coordinates are taken as the union across days, gaps of up to 45 minutes are filled by
linear interpolation, and range bins with no data on any channel are dropped.

If fewer than 3 frequency channels have valid data for the week, the averaged file and echogram are not rewritten, and
the files from the previous night stay in place. This normally means the instrument was misconfigured or a channel was
switched off.

### Backward buffer copies

Converting the first day of a week reconverts the previous day's last raw file, which belongs to the previous week, and
writes its store into the current week's folder. Those copies are removed at the end of every run so they are not
duplicated in the archive. The week that file belongs to keeps its own copy.

## Running it

The module runs inside the container image. It takes the raw data and processed output roots one level above the
per-year folders:

```shell
python -m ooi_zpls_echograms.cabled_nrt_echogram -s SITE -d DATA_ROOT -o PROC_ROOT [--date YYYYMMDD]
```

| Argument              | Description                                                                                 |
|:----------------------|:--------------------------------------------------------------------------------------------|
| `-s`, `--site`        | `CE02SHBP` or `CE04OSPS`                                                                    |
| `-d`, `--data-root`   | Raw data parent directory, above the per-year folders                                       |
| `-o`, `--proc-root`   | Processed output parent directory, above the per-year `processed` folders                   |
| `-zm`, `--zpls-model` | Defaults to `EK80`, the only model this module supports                                     |
| `--date`              | Process this day instead of yesterday (UTC); used for testing and for redoing a day by hand |

The raw and processed roots for the two sites, as seen inside the container with the standard mounts
(`/rsn_cabled/rsn_data/DVT_Data` mounted read-only at `/node_data`, the processed output root at `/data/zplsc`):

| Site     | Data root                                 | Processed root                            |
|:---------|:------------------------------------------|:------------------------------------------|
| CE02SHBP | `/node_data/mj01c/ZPLSCB101_10.33.13.7`   | `/data/zplsc/CE02SHBP/MJ01C/07-ZPLSCB101` |
| CE04OSPS | `/node_data/pc01b/ZPLSCB102_10.33.10.143` | `/data/zplsc/CE04OSPS/PC01B/05-ZPLSCB102` |

Example, redoing 2026-10-12 for CE04OSPS:

```shell
podman run --rm \
    -v /rsn_cabled/rsn_data/DVT_Data:/node_data:ro \
    -v /data/zplsc:/data/zplsc \
    ooi-zpls-echograms:<tag> \
    python -m ooi_zpls_echograms.cabled_nrt_echogram -s CE04OSPS \
        -d /node_data/pc01b/ZPLSCB102_10.33.10.143 -o /data/zplsc/CE04OSPS/PC01B/05-ZPLSCB102 --date 20261012
```

A manual run regenerates the whole week's average and echogram afterward, so redoing any day in a week leaves that
week's products current.

## Schedule

Both sites run nightly at 02:00 UTC, processing the previous UTC day.

## Weekly trailing backlog

A nightly run can only process the raw files that have arrived by the time it starts. If the copy of a file was
incomplete, or arrives late, that day is short. `utilities/weekly_trailing_backlog.sh` repairs this by reprocessing the
last complete week (or the last N complete weeks):

```shell
weekly_trailing_backlog.sh SITE DATA_ROOT PROC_ROOT [N_WEEKS]
```

`N_WEEKS` defaults to 1. For each of those weeks it deletes every converted store in the week's folder, reruns the
week through `batch_zplsc_cabled.sh` (grouped by year, so a week that crosses New Year is handled correctly), and then
removes the backward buffer copies. The current, incomplete week is never touched. Set `DRY_RUN=1` to print what would
be deleted and run without changing anything.

It needs the processing environment, so it is run inside the container like the nightly job. Its batch runs write one
log per week to `$LOG_DIR` (default `/zplsc_processing/logs/<SITE>`).

## Checking a run

A successful night ends with a line of the form:

```
CE02SHBP: regenerated weekly average and echogram for 20261011-20261018 from 4 daily file(s).
```

The number of daily files should match the number of days of the week processed so far. Other messages to know:

| Message                                                                       | Meaning                                                                                                       |
|:------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------|
| `<SITE>: removed N existing converted store(s) for YYYYMMDD`                  | Start of the conversion; N is 0 or 1 on a first run, about the day's file count plus one when a day is redone |
| `<file>: processing failed (error: ...)`                                      | One raw file could not be processed and was skipped; the rest of the day continues                            |
| `<file>: all channels are LFM/broadband, no usable CW data, ...`              | The file holds only broadband channels, which are not processed                                               |
| `YYYYMMDD: no usable data from N file(s) (M own-day), skipping day.`          | No file for that day could be processed; no daily file is written                                             |
| `YYYYMMDD: none of the M own-day file(s) produced usable data, ...`           | Only the backward buffer file converted; no daily file is written                                             |
| `<SITE>: no daily files present yet for <week>, skipping ...`                 | Nothing to average yet for that week                                                                          |
| `<SITE>: only N of the expected 3 frequency channels reported valid data ...` | The week's average and echogram were not rewritten (see above)                                                |

Most gaps in the record come from power or cable outages, when no raw files were recorded at all, and from RCA
changing the instrument configuration. Those are real gaps with nothing to backfill. Partial copies of raw files are a
minor cause, and the weekly trailing backlog repairs them.

## Memory and run time

Peak memory is set by file conversion, not by the weekly averaging step. Measured on single-site test weeks with the
monitor sampling every 15 s, so true peaks may be somewhat higher:

| Site     | Daily `_Full_` file | Container peak | System peak | 7-day test week |
|:---------|:--------------------|:---------------|:------------|:----------------|
| CE04OSPS | ~10.9 GB            | ~76 GiB        | ~84 GiB     | ~77 min         |
| CE02SHBP | ~5.0 GB             | ~37 GiB        | ~46 GiB     | ~42 min         |

A normal nightly run processes one day per site, which takes a few minutes for each.

#!/usr/bin/env python
"""
Redraw echograms from existing _Averaged.nc files.

Takes one or more averaged files and rewrites the echogram PNG next to
each one, using the site's current colormap, colorbar range and vertical
range from site_config. The site and date range are read from the file
name, so the script works for any site, instrument, folder layout and
chunk length. No data files are changed. A file that cannot be redrawn is
reported as FAILED and the run continues.

Selecting which files to redraw is left to the caller, e.g.:

    find /data/zplsc/CE02SHBP -name '*_Averaged.nc' -print0 | \\
        xargs -0 python regenerate_echograms.py

Usage
-----
python regenerate_echograms.py AVERAGED_FILE [AVERAGED_FILE ...]
"""
import argparse
import re
import sys
from importlib.resources import files
from pathlib import Path

import xarray as xr
from PIL import Image

from ooi_zpls_echograms.zpls_echogram import generate_echogram, site_config

NAME_RE = re.compile(r'(?P<site>.+)_Bioacoustic_Echogram_(?P<start>\d{8})-(?P<stop>\d{8})_Calibrated_Sv_Averaged\.nc')


def add_watermark(echogram_path: Path, vertical_range: list[int]) -> None:
    """
    Add the OOI logo to an echogram PNG (same placement as the processing
    code).

    :param echogram_path: path to the echogram PNG, rewritten in place.
    :param vertical_range: the site's vertical range, used to place the logo.
    """
    echo_image = Image.open(echogram_path)
    # noinspection PyTypeChecker
    ooi_image = Image.open(files('ooi_zpls_echograms').joinpath('ooi-logo.png'))
    width, height = echo_image.size
    transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    transparent.paste(echo_image, (0, 0))
    if max(vertical_range) > 99:
        transparent.paste(ooi_image, (96, 15), mask=ooi_image)
    else:
        transparent.paste(ooi_image, (80, 15), mask=ooi_image)
    transparent.save(echogram_path)


def redraw(avg_file: Path) -> str:
    """
    Redraw the echogram for one averaged file.

    :param avg_file: path to a <SITE>_Bioacoustic_Echogram_<start>-<stop>
        _Calibrated_Sv_Averaged.nc file.
    :return: a short status message for the log.
    """
    match = NAME_RE.fullmatch(avg_file.name)
    if not match:
        return 'skipped, file name does not match <SITE>_Bioacoustic_Echogram_<start>-<stop>_..._Averaged.nc'
    site = match['site'].upper()
    if site not in site_config:
        return f'skipped, site {site} is not in site_config'
    cfg = site_config[site]
    dates = [match['start'], match['stop']]
    file_name = avg_file.name.removesuffix('_Averaged.nc')

    with xr.open_dataset(avg_file) as ds:
        avg = ds.load()

    generate_echogram(avg, site, cfg['long_name'], cfg['deployed_depth'], str(avg_file.parent), file_name, dates,
                      vertical_range=cfg['vertical_range'], colorbar_range=cfg['colorbar_range'],
                      colormap=cfg['colormap'])
    add_watermark(avg_file.parent / (file_name + '.png'), cfg['vertical_range'])
    return f"redrawn with {cfg['colormap']} {cfg['colorbar_range']}"


def main() -> None:
    parser = argparse.ArgumentParser(description='Redraw echograms from existing _Averaged.nc files.')
    parser.add_argument('files', nargs='+', type=Path, help='one or more _Averaged.nc files')
    args = parser.parse_args()

    failed = 0
    for avg_file in args.files:
        try:
            status = redraw(avg_file)
        except Exception as err:
            status = f'FAILED ({err})'
            failed += 1
        print(f'{avg_file}: {status}', flush=True)

    print(f'\n{len(args.files)} file(s), {failed} failed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()

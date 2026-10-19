#!/usr/bin/env python
"""
Find and remove duplicate EK80 converted stores (.zarr) that were written
into more than one subfolder under a site's processed output tree.

Usage:
    python duplication_check.py ROOT [ROOT ...] [--delete]

Each ROOT is a `<year>/processed` directory, e.g.
/data/zplsc/CE02SHBP/MJ01C/07-ZPLSCB101/2023/processed. Pass every year of a
site in one call so duplicates that straddle a year boundary are found.

Without --delete, runs in dry-run mode: reports what it would do and exits.
"""
import argparse
import re
import shutil

from datetime import datetime
from pathlib import Path


def parse_store_date(name: str) -> datetime | None:
    """
    Parse the recording date embedded in an EK80 converted store's name
    ('D{YYYYMMDD}-T{HHMMSS}', the same convention as the raw file).

    :param name: store directory name (e.g. 'ZPLSCB101-D20251111-T192133.zarr').
    :return: parsed datetime, or None if the name does not match.
    """
    match = re.search(r"D(\d{8})-T(\d{6})", name)
    if match:
        return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    return None


def parse_range(folder_name: str) -> tuple[datetime, datetime] | None:
    """
    Parse a subfolder's '<start>-<stop>' name into its half-open
    (start, stop) date range, matching normalize_date_range's convention.

    :param folder_name: subfolder name, e.g. '20251105-20251112'.
    :return: (start, stop) as datetimes, or None if the name doesn't match.
    """
    match = re.fullmatch(r"(\d{8})-(\d{8})", folder_name)
    if not match:
        return None
    return (datetime.strptime(match.group(1), "%Y%m%d"),
            datetime.strptime(match.group(2), "%Y%m%d"))


def select_keeper(paths: list[Path]) -> tuple[Path | None, list[Path]]:
    """
    Determine which copy of a duplicated store belongs in its folder
    by matching the store's embedded date against each folder's date range.

    :param paths: all locations a same-named store was found.
    :return: (keeper, rest) -- keeper is None if the date doesn't cleanly
        match exactly one candidate folder's range (flag for manual review
        rather than guess).
    """
    store_date = parse_store_date(paths[0].name)
    if store_date is None:
        return None, paths

    matches = [p for p in paths
              if (r := parse_range(p.parent.name)) and r[0] <= store_date < r[1]]

    if len(matches) != 1:
        return None, paths

    return matches[0], [p for p in paths if p != matches[0]]


def find_converted_stores(root: Path) -> dict[str, list[Path]]:
    """
    Walk all subfolders under root and group converted stores
    (.zarr directories) by their base file name.

    :param root: a `<year>/processed` directory containing `<start>-<stop>`
        subfolders.
    :return: mapping of store base name to the list of full paths where
        that name was found (len > 1 means duplicated across chunks).
    """
    groups: dict[str, list[Path]] = {}
    for chunk_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for store in chunk_dir.glob('*.zarr'):
            groups.setdefault(store.name, []).append(store)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Remove duplicate converted echodata stores across subfolders.')
    parser.add_argument('roots', type=Path, nargs='+',
                        help='one or more <year>/processed directories containing subfolders')
    parser.add_argument('--delete', action='store_true',
                        help='actually remove duplicates (default: dry-run report only)')
    args = parser.parse_args()

    groups: dict[str, list[Path]] = {}
    for root in args.roots:
        for name, paths in find_converted_stores(root).items():
            groups.setdefault(name, []).extend(paths)
    duplicates = {name: paths for name, paths in groups.items() if len(paths) > 1}

    if not duplicates:
        print('No duplicate converted stores found.')
        return

    total = 0
    for name, paths in duplicates.items():
        keeper, rest = select_keeper(paths)
        if keeper is None:
            print(f'AMBIGUOUS date-range match, skipping (needs manual review): {name} -> {paths}')
            continue
        for dupe in rest:
            total += 1
            if args.delete:
                shutil.rmtree(dupe)
                print(f'Removed: {dupe} (kept {keeper})')
            else:
                print(f'Would remove: {dupe} (kept {keeper})')

    mode = 'Removed' if args.delete else 'Would remove'
    print(f'\n{mode} {total} duplicate store(s) across {len(duplicates)} name(s).')


if __name__ == '__main__':
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import cmocean
import dateutil.parser as dparser
import echopype as ep
import gc
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import os
import pandas as pd
import re
import warnings
import xarray as xr

from collections import OrderedDict
from datetime import datetime, date, timedelta
from echopype.qc import exist_reversed_time, coerce_increasing_time
from importlib.resources import files
from pandas.plotting import register_matplotlib_converters
from pathlib import Path
from PIL import Image
from tqdm.auto import tqdm
from typing import List, Tuple

warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
register_matplotlib_converters()
site_config = {
    'CE01ISSM': {
        'long_name': 'Coastal Endurance, Oregon Inshore Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 25],
        'deployed_depth': 25,
        'depth_offset': 1.0,
        'average_salinity': 33,
        'average_temperature': 10,
        'instrument_orientation': 'up'
    },
    'CE02SHBP': {
        'long_name': 'Coastal Endurance, Oregon Shelf Cabled Benthic Experiment Package',
        'tilt_correction': 0,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 81],
        'deployed_depth': 81,
        'depth_offset': 2.0,
        'average_salinity': 33,
        'average_temperature': 10,
        'instrument_orientation': 'up'
    },
    'CE04OSPS': {
        'long_name': 'Coastal Endurance, Oregon Offshore Cabled Shallow Profiler Mooring',
        'tilt_correction': 0,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 200],
        'deployed_depth': 200,
        'depth_offset': 0.0,
        'average_salinity': 34,
        'average_temperature': 9,
        'instrument_orientation': 'up'
    },
    'CE06ISSM': {
        'long_name': 'Coastal Endurance, Washington Inshore Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 30],
        'deployed_depth': 29,
        'depth_offset': 1.0,
        'average_salinity': 33,
        'average_temperature': 11,
        'instrument_orientation': 'up'
    },
    'CE07SHSM': {
        'long_name': 'Coastal Endurance, Washington Shelf Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 90],
        'deployed_depth': 87,
        'depth_offset': 1.0,
        'average_salinity': 33,
        'average_temperature': 9,
        'instrument_orientation': 'up'
    },
    'CE09OSSM': {
        'long_name': 'Coastal Endurance, Washington Offshore Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 540],
        'deployed_depth': 542,
        'depth_offset': 1.0,
        'average_salinity': 33,
        'average_temperature': 8,
        'instrument_orientation': 'up'
    },
    'CP01CNSM': {
        'long_name': 'Coastal Pioneer New England Shelf, Central Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 135],
        'deployed_depth': 135,
        'depth_offset': 1.0,
        'average_salinity': 35,
        'average_temperature': 13,
        'instrument_orientation': 'up'
    },
    'CP03ISSM': {
        'long_name': 'Coastal Pioneer New England Shelf, Inshore Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 95],
        'deployed_depth': 95,
        'depth_offset': 1.0,
        'average_salinity': 34,
        'average_temperature': 14,
        'instrument_orientation': 'up'
    },
    'CP04OSSM': {
        'long_name': 'Coastal Pioneer New England Shelf, Offshore Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 455],
        'deployed_depth': 455,
        'depth_offset': 1.0,
        'average_salinity': 35,
        'average_temperature': 12,
        'instrument_orientation': 'up'
    },
    'CP10CNSM': {
        'long_name': 'Coastal Pioneer Mid-Atlantic Bight, Central Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 30],
        'deployed_depth': 30,
        'depth_offset': 1.0,
        'average_salinity': 33.6,
        'average_temperature': 14.1,
        'instrument_orientation': 'up'
    },
    'CP11NOSM': {
        'long_name': 'Coastal Pioneer Mid-Atlantic Bight, Northern Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 100],
        'deployed_depth': 100,
        'depth_offset': 1.0,
        'average_salinity': 34.6,
        'average_temperature': 12.1,
        'instrument_orientation': 'up'
    },
    'CP11SOSM': {
        'long_name': 'Coastal Pioneer Mid-Atlantic Bight, Southern Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 100],
        'deployed_depth': 100,
        'depth_offset': 1.0,
        'average_salinity': 34.4,
        'average_temperature': 12.2,
        'instrument_orientation': 'up'
    },
    'GI02HYPM_UPPER': {
        'long_name': 'Global Irminger Sea, Apex Profiler Mooring, Upward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 150],
        'deployed_depth': 150,
        'depth_offset': 0.0,
        'average_salinity': 35,
        'average_temperature': 5,
        'instrument_orientation': 'up'
    },
    'GI02HYPM_LOWER': {
        'long_name': 'Global Irminger Sea, Apex Profiler Mooring, Downward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 400],
        'deployed_depth': 150,
        'depth_offset': -1.62,
        'average_salinity': 35,
        'average_temperature': 5,
        'instrument_orientation': 'down'
    },
    'GP02HYPM_UPPER': {
        'long_name': 'Global Station Papa, Apex Profiler Mooring, Upward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 150],
        'deployed_depth': 150,
        'depth_offset': 0,
        'average_salinity': 33,
        'average_temperature': 6,
        'instrument_orientation': 'up'
    },
    'GP02HYPM_LOWER': {
        'long_name': 'Global Station Papa, Apex Profiler Mooring, Downward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 400],
        'deployed_depth': 150,
        'depth_offset': -1.62,
        'average_salinity': 33,
        'average_temperature': 6,
        'instrument_orientation': 'down'
    },
    'GA02HYPM_UPPER': {
        'long_name': 'Global Argentine Basin, Apex Profiler Mooring, Upward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 150],
        'deployed_depth': 150,
        'depth_offset': 0,
        'average_salinity': 34,
        'average_temperature': 8,
        'instrument_orientation': 'up'
    },
    'GA02HYPM_LOWER': {
        'long_name': 'Global Argentine Basin, Apex Profiler Mooring, Downward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 400],
        'deployed_depth': 150,
        'depth_offset': -1.62,
        'average_salinity': 34,
        'average_temperature': 8,
        'instrument_orientation': 'down'
    },
    'GS02HYPM_UPPER': {
        'long_name': 'Global Southern Ocean, Apex Profiler Mooring, Upward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 150],
        'deployed_depth': 150,
        'depth_offset': 0,
        'average_salinity': 34,
        'average_temperature': 7,
        'instrument_orientation': 'up'
    },
    'GS02HYPM_LOWER': {
        'long_name': 'Global Southern Ocean, Apex Profiler Mooring, Downward Looking',
        'tilt_correction': 15,
        'colorbar_range': [-95, -65],
        'vertical_range': [0, 400],
        'deployed_depth': 150,
        'depth_offset': -1.62,
        'average_salinity': 34,
        'average_temperature': 7,
        'instrument_orientation': 'down'
    }
}

attributes = {
    # attributes for the variables in the NetCDF files
    'global': {
        'title': 'Measurements of the Volume Acoustic Backscatter Strength',
        'summary': ('Volume acoustic backscatter strength measurements collected by bioacoustic sonar sensors '
                    'deployed on subsurface moorings and seafloor platforms as part of the Ocean Observatories '
                    'Initiative (OOI) project funded by the National Science Foundation. Data was converted and '
                    'processed from raw instrument files to this processed dataset using the open-source package '
                    'echopype (https://echopype.readthedocs.io/en/latest/) and the code provided by OOI '
                    '(https://github.com/oceanobservatories/ooi-zpls-echograms)'),
        'project': 'Ocean Observatories Initiative',
        'acknowledgement': 'National Science Foundation',
        'references': 'https://oceanobservatories.org',
        'creator_name': 'Ocean Observatories Initiative',
        'creator_email': 'helpdesk@oceanobservatories.org',
        'creator_url': 'https://oceanobservatories.org',
        'featureType': 'timeSeries',
        'cdm_data_type': 'Station',
        'Conventions': 'CF-1.7'
    },
    'frequency_nominal': {
        'long_name': 'Acoustic Frequency',
        'standard_name': 'sound_frequency',
        'units': 'Hz'
    },
    'ping_time': {
        'long_name': 'Time of Each Ping',
        'standard_name': 'time',
        'units': 'seconds since 1970-01-01T00:00:00.000000Z',
        'calendar': 'Gregorian',
        'comment': ('Derived from the instrument internal clock. Note, instrument clocks are subject to drift over '
                    'the course of a deployment. The data should be checked against other sensors to determine if '
                    'drift and offset corrections to the instrument clock are applicable.')
    },
    'range_sample': {
        'long_name': 'Vertical Range Bin Number',
        'comment': 'Bin number starting with 0 at the sensor face, used to derive the vertical range.',
        'units': 'count'
    },
    'echo_range': {
        'long_name': 'Vertical Range',
        'units': 'm',
        'comment': 'Vertical range from the sensor face, corrected for sensor tilt where applicable.',
    },
    'nominal_depth': {
        'long_name': 'Nominal Depth',
        'standard_name': 'depth',
        'units': 'm',
        'comment': ('Nominal depth bins of the volume acoustic backscatter strength (Sv) data for each frequency, '
                    'derived from the range, sensor tilt, orientation, and depth offset (if any) of the instrument '
                    'relative to the platform frame. The actual depth of the platform will vary due to tides (seafloor '
                    'platforms) or blow-down events (subsurface moorings). Users will need to determine the actual '
                    'depth of the bins based on measurements from co-located sensors (e.g. a CTD).'),
        'positive': 'up'
    },
    'Sv': {
        'long_name': 'Volume Acoustic Backscatter Strength (Sv re 1 m-1)',
        'units': 'dB',
        'comment': ('Initial estimate of the volume acoustic backscatter strength derived from the raw instrument '
                    'data using echopype to convert and process the data.'),
        'ooi_data_product': 'SONBSCA_L1'
    }
}

# set expected frequency counts (used to trap misconfigured sensors)
EXPECTED_FREQUENCY_COUNT = {'EK60': 3, 'EK80': 3, 'AZFP': 4}


def set_file_name(site, dates):
    """
    Create the file name for the echogram based on the mooring site name,
    and the date range plotted.

    :param site: mooring site name.
    :param dates: date range shown in the plot.
    :return: file name as a string created from the inputs.
    """
    file_name = site + '_Bioacoustic_Echogram_' + dates[0] + '-' + dates[1] + '_Calibrated_Sv'
    return file_name


def ax_config(ax, frequency):
    """
    Configure axis elements for the echogram, setting title, date formatting
    and direction of the y-axis

    :param ax: graphics handle to the axis object.
    :param frequency: acoustic frequency of the data plotted in this axis.
    :return None:
    """
    title = '%.0f kHz' % (frequency / 1000)
    ax.set_title(title)
    ax.grid(False)

    ax.set_ylabel('Vertical Range (m)')
    x_fmt = mdates.DateFormatter('%b-%d')
    ax.xaxis.set_major_formatter(x_fmt)
    ax.set_xlabel('')


def generate_echogram(data, site, long_name, deployed_depth, output_directory, file_name, dates,
                      vertical_range=None, colorbar_range=None):
    """
    Generates and saves to disk an echogram of the acoustic volume backscatter
    for each of the frequencies.

    :param data: xarray dataset containing the acoustic volume backscatter data.
    :param site: 8 letter OOI code (e.g. CP01CNSM) name of the mooring.
    :param long_name: Full descriptive name of the mooring.
    :param deployed_depth: nominal instrument depth in meters.
    :param output_directory: directory to save the echogram plot to.
    :param file_name: file name to use for the echogram.
    :param dates: date range to plot, sets the x-axis.
    :param vertical_range: vertical range to plot, sets the y-axis.
    :param colorbar_range: colorbar range to plot, sets the colormap.
    :return None: generates and saves an echogram to disk.
    """
    # setup defaults based on inputs
    frequency_list = data.frequency_nominal.values
    t = datetime.strptime(dates[0], '%Y%m%d')
    start_date = datetime.strftime(t, '%Y-%m-%d')
    t = datetime.strptime(dates[1], '%Y%m%d')
    stop_date = datetime.strftime(t, '%Y-%m-%d')
    params = {
        'font.size': 11,
        'axes.linewidth': 1.0,
        'axes.titlelocation': 'right',
        'figure.figsize': [17, 11],
        'figure.dpi': 100,
        'xtick.major.size': 4,
        'xtick.major.pad': 4,
        'xtick.major.width': 1.0,
        'ytick.major.size': 4,
        'ytick.major.pad': 4,
        'ytick.major.width': 1.0
    }
    plt.rcParams.update(params)

    # set the y_min and y_max from the vertical range
    if not vertical_range:
        y_min = 0
        y_max = np.amax(data.echo_range.values)
    else:
        y_min = vertical_range[0]
        y_max = vertical_range[1]

    # set the color map to "balance" from cmocean and set the c_min and c_max from the colorbar range
    my_cmap = cmocean.cm.balance
    if not colorbar_range:
        v_min = None  # colorbar range will be set by the range in the data
        v_max = None
    else:
        v_min = colorbar_range[0]
        v_max = colorbar_range[1]

    # determine if this is an upward or downward looking sensor
    if 'LOWER' in site:
        upward = False
    else:
        upward = True

    # initialize the echogram figure and set the title
    fig, ax = plt.subplots(nrows=len(frequency_list), sharex='all', sharey='all')
    ht = fig.suptitle('{} ({})\n{} to {} UTC\n{} m nominal deployment depth'.format(long_name, site[:8], start_date,
                                                                                    stop_date, deployed_depth))
    ht.set_horizontalalignment('left')
    ht.set_position([0.257, 0.94])  # position title to the left

    # populate the subplots
    im = []
    for index in range(len(frequency_list)):
        im.append(data.isel(frequency_nominal=index).Sv.plot(x='ping_time', y='echo_range', vmin=v_min, vmax=v_max,
                                                             ax=ax[index], cmap=my_cmap, add_colorbar=False))
        ax_config(ax[index], frequency_list[index])

    # set a common x- and y-axis, label the x-axis and create space for a shared colorbar
    ax[0].set_xlim([date.fromisoformat(start_date), date.fromisoformat(stop_date)])
    # if upward looking, increase y-axis from bottom to top, otherwise increase from the top to the bottom
    if upward:
        ax[0].set_ylim([y_min, y_max])
    else:
        ax[0].set_ylim([y_max, y_min])

    fig.subplots_adjust(right=0.89)
    cbar = fig.add_axes([0.91, 0.30, 0.012, 0.40])
    fig.colorbar(im[0], cax=cbar, label='S$_v$ (dB re 1 m$^{-1}$)')

    # save the echogram
    echogram_name = file_name + '.png'
    plt.savefig(os.path.join(output_directory, echogram_name), dpi=150, bbox_inches='tight')


def range_correction(data, tilt_correction):
    """
    Apply a correction to the calculated range using the supplied tilt
    correction value instead of the instrument's measured tilt/roll values.
    Adjusts the echo_range variable in the xarray object directly.

    :param data: xarray dataset with the calculated range.
    :param tilt_correction: tilt correction value in degrees to use.
    """
    data['echo_range'] = data.echo_range * np.cos(np.deg2rad(tilt_correction))


def normalize_date_range(dates):
    """
    Normalize the user-supplied date range into a (start, stop) pair of
    YYYYMMDD strings, where stop is an exclusive upper bound (i.e. the
    range covers [start, stop], matching the convention used by the
    weekly batch scripts). Handles three input shapes:
      - a single YYYYMMDD day        -> (day, day + 1)
      - a single YYYYMM month        -> (first-of-month, first-of-next-month)
      - two explicit start/stop tokens (YYYYMMDD or YYYYMM), used as-is

    Idempotent: calling this again on an already-normalized pair is a no-op,
    so it is safe to call from multiple entry points.

    :param dates: list of 1 or 2 date strings from the -dr argument.
    :return: [start, stop] as YYYYMMDD strings, exclusive stop.
    """
    if len(dates) == 1:
        if len(dates[0]) == 6:
            dates = [dates[0], dates[0]]
        else:
            dates = [dates[0], (dparser.parse(dates[0]) + timedelta(days=1)).strftime('%Y%m%d')]

    if len(dates[0]) == 6:
        dates[0] = dates[0] + '01'
        end_year = int(dates[1][:4])
        end_month = int(dates[1][4:6])
        if end_month == 12:
            dates[1] = '%04d0101' % (end_year + 1)
        else:
            dates[1] = '%04d%02d01' % (end_year, end_month + 1)

    return dates


def azfp_file_list(data_directory, dates):
    """
    Generate a list of file paths pointing to the .01A files from an AZFP that
    contain the dates the user has requested.

    :param data_directory: path to directory with the AZFP .01A files.
    :param dates: starting and ending dates to use in generating the file list.
    :return: the list of potential .01A file names, including full path.
    """
    dates = normalize_date_range(dates)
    sdate = dparser.parse(dates[0])
    edate = dparser.parse(dates[1]) - timedelta(days=1)
    delta = edate - sdate

    file_list = []
    for i in range(delta.days + 1):
        day = sdate + timedelta(days=i)
        azfp_files = glob.glob(os.path.join(data_directory, day.strftime('%Y%m')) + '/'
                               + day.strftime('%y%m%d') + '*.01A')
        file_list.append(azfp_files)

    return file_list


def ek_file_list(data_directory, dates):
    """
    Generate a list of file paths pointing to the .raw files from an EK60 or
    EK80 that contain the dates the user has requested.

    :param data_directory: path to directory with the EK60/EK80 .raw files.
    :param dates: starting and ending dates to use in generating the file list.
    :return: the .raw file names, including full path.
    """
    dates = normalize_date_range(dates)
    sdate = dparser.parse(dates[0])
    edate = dparser.parse(dates[1]) - timedelta(days=1)
    delta = edate - sdate

    normalized = os.path.normpath(data_directory)
    base_year = os.path.basename(normalized)
    year_scoped = base_year.isdigit() and len(base_year) == 4
    parent_dir = os.path.dirname(normalized)

    file_list = []
    for i in range(delta.days + 1):
        day = sdate + timedelta(days=i)
        if year_scoped and day.strftime('%Y') != base_year:
            search_dir = os.path.join(parent_dir, day.strftime('%Y'))
        else:
            search_dir = data_directory
        ek_files = glob.glob(os.path.join(search_dir, day.strftime('%m'), day.strftime('%d')) + '/*.raw')
        file_list.append(ek_files)

    return file_list


def classify_recording_mode(filepaths: List[str], threshold_minutes: float = 30) -> List[Tuple[str, str]]:
    """
    Classify files as broadband or narrowband based on time gaps between
    consecutive recordings. Note, this is somewhat crude, but faster than
    opening the files via echopype.

    Parameters
    ----------
    filepaths : list of str
        List of file paths containing datetime strings in format
        'D{YYYYMMDD}-T{HHMMSS}'.
    threshold_minutes : float, optional
        Time threshold in minutes to distinguish between broadband (shorter
        gaps) and narrowband (longer gaps). Default is 30 minutes.

    Returns
    -------
    list of tuple
        List of (filepath, mode) tuples where mode is either 'broadband' or
        'narrowband'.

    Notes
    -----
    The last file in a sorted sequence is classified based on the gap before
    it. If only one file exists, it's classified as 'unknown'.
    """
    if not filepaths:
        return []

    # Extract datetime and sort files chronologically
    file_times = []
    for filepath in filepaths:
        match = re.search(r"D(\d{8})-T(\d{6})", filepath)
        if not match:
            continue
        dt_str = f"{match.group(1)}{match.group(2)}"
        dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
        file_times.append((filepath, dt))

    file_times.sort(key=lambda x: x[1])

    if len(file_times) == 1:
        return [(file_times[0][0], "unknown")]

    # Classify based on time gap to next file
    results = []
    for i in range(len(file_times) - 1):
        gap_minutes = (file_times[i + 1][1] - file_times[i][1]).total_seconds() / 60
        mode = "broadband" if gap_minutes < threshold_minutes else "narrowband"
        results.append((file_times[i][0], mode))

    # Last file uses the gap before it
    last_gap = (file_times[-1][1] - file_times[-2][1]).total_seconds() / 60
    last_mode = "broadband" if last_gap < threshold_minutes else "narrowband"
    results.append((file_times[-1][0], last_mode))

    return results


def _parse_file_datetime(filepath):
    """
    Parse the recording datetime embedded in a raw sonar filename, handling
    both filename conventions used across instrument types:
      - EK60/EK80: 'D{YYYYMMDD}-T{HHMMSS}' embedded anywhere in the name
        (e.g. 'ZPLSCB101-D20250810-T011824.raw')
      - AZFP: file name is 'yymmddHH.01A' (e.g. '19101307.01A'; year assumed
        20xx)

    :param filepath: path to a raw sonar data file.
    :return: parsed datetime, or None if neither convention matches.
    """
    match = re.search(r"D(\d{8})-T(\d{6})", filepath)
    if match:
        return datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")

    stem = Path(filepath).stem
    match = re.fullmatch(r"(\d{8})", stem)
    if match:
        return datetime.strptime('20' + match.group(1), "%Y%m%d%H")

    return None


def _group_files_by_day(file_list):
    """
    Group an already-sorted flat file list into an OrderedDict keyed by
    YYYYMMDD, preserving chronological order both across and within days.
    Supports both EK60/EK80 and AZFP filename conventions via
    _parse_file_datetime.

    :param file_list: flat, sorted list of file paths.
    :return: OrderedDict of {YYYYMMDD: [file paths for that day]}.
    """
    grouped = OrderedDict()
    for f in file_list:
        dt = _parse_file_datetime(f)
        if dt is None:
            continue
        day_key = dt.strftime('%Y%m%d')
        grouped.setdefault(day_key, []).append(f)
    return grouped


def _forward_buffer_files(next_day_files, bin_width):
    """
    Select the leading files from the next day needed to correctly compute
    the current day's final resample bin (which spans midnight).

    :param next_day_files: sorted list of file paths for the following day
        (empty list if this is the last day of the chunk).
    :param bin_width: pandas offset alias for the resample bin width
        ('15Min' or '60Min'), used to bound how far into the next day we
        need to look.
    :return: list of file paths from next_day_files needed for the buffer.
    """
    if not next_day_files:
        return []

    width = pd.Timedelta(bin_width)
    buffer_files = []
    for f in next_day_files:
        dt = _parse_file_datetime(f)
        if dt is None:
            continue
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if dt - day_start <= width:
            buffer_files.append(f)
        else:
            # files are sorted chronologically, so once we're past the
            # buffer window there's no need to keep scanning
            break
    return buffer_files


def _previous_day_last_file(data_directory, start_date_str, zpls_model):
    """
    Find the last file (by sorted filename) recorded on the calendar day
    immediately before start_date_str. Used as the backward buffer for the
    FIRST day of a requested range, since a file recorded late the day
    before a range starts can run past midnight into the range's first
    real day -- without this, that data is silently invisible, because
    ek_file_list/azfp_file_list only globs folders within the
    requested range.

    :param data_directory: path to directory with the raw files (same
        directory passed to ek_file_list/azfp_file_list).
    :param start_date_str: YYYYMMDD string, the first day of the requested
        range (i.e. dates[0] after normalize_date_range).
    :param zpls_model: Model of bioacoustic sonar sensor used.
    :return: path to the last file from the previous day, or None if there
        isn't one.
    """
    prev_day = datetime.strptime(start_date_str, '%Y%m%d') - timedelta(days=1)
    if zpls_model == 'AZFP':
        pattern = (os.path.join(data_directory, prev_day.strftime('%Y%m')) + '/'
                   + prev_day.strftime('%y%m%d') + '*.01A')
    else:
        # EK60/EK80's directory structure is year-scoped. If the requested
        # range starts on Jan 1st, the previous day (Dec 31) falls in a
        # different year, check and swap the year component.
        normalized = os.path.normpath(data_directory)
        base_year = os.path.basename(normalized)
        prev_year = prev_day.strftime('%Y')
        if base_year.isdigit() and len(base_year) == 4 and prev_year != base_year:
            search_dir = os.path.join(os.path.dirname(normalized), prev_year)
        else:
            search_dir = data_directory
        pattern = os.path.join(search_dir, prev_day.strftime('%m'), prev_day.strftime('%d')) + '/*.raw'

    prev_files = sorted(glob.glob(pattern))
    return prev_files[-1] if prev_files else None


def process_sonar_data(site, data_directory, output_directory, dates, zpls_model, xml_file,
                        tilt_correction, file_name, resample_freq, time_shift, max_gap):
    """
    Use echopype to convert and process the raw bioacoustic sonar data from
    either an AZFP (in *.01A files), or an EK60/EK80 (in *.raw files).
    Processes one calendar day at a time rather than the whole requested
    date range at once: converts, writes that day's full-resolution NetCDF,
    resamples, and releases the full-resolution data from memory before
    moving to the next day. Each day's resample pass includes a forward
    buffer so the density of the final bin spanning midnight is computed
    correctly rather than truncated.

    :param site: Site name where the data was collected.
    :param data_directory: Source directory where the raw data files are
        located (assumes a standardized file structure will be followed by the
        OOI operators).
    :param output_directory: Output directory to save the results.
    :param dates: Starting and ending dates to search for raw data files in the
        data directory to convert and process.
    :param zpls_model: Model of bioacoustic sonar sensor used.
    :param xml_file: If the model is an AZFP, the XML file (with instrument
        calibration coefficients needed for the conversion) must also be
        specified (usually just one per deployment).
    :param tilt_correction: Tilt of the sonar transducers (typically 15
        degrees for the uncabled sensors to minimize interference from the
        riser elements).
    :param file_name: base file name (from set_file_name), used to construct
        each day's full-resolution NetCDF path.
    :param resample_freq: pandas resample offset alias, '15Min' or '60Min'.
    :param time_shift: pd.Timedelta bin-centering shift applied before
        resampling.
    :param max_gap: pandas offset alias string passed to interpolate_na
        max_gap, e.g. '45Min' or '180Min'.
    :return: (avg_chunk, nc_files) where avg_chunk is the concatenated,
        gap-interpolated averaged xarray Dataset for the whole date range
        (or None if no data was processed), and nc_files is the list of
        daily full-resolution NetCDF paths written.
    """
    # generate and classify the flat file list exactly as before -- broadband
    # filtering needs global, cross-day context to be accurate, so this stays
    # a whole-chunk operation even though conversion below is per-day
    if zpls_model == 'AZFP':
        file_list = azfp_file_list(data_directory, dates)
    else:
        file_list = ek_file_list(data_directory, dates)

    file_list = [file for sub in file_list for file in sub]
    if not file_list:
        return None, []

    file_list.sort()

    if zpls_model == 'EK80':
        classifications = classify_recording_mode(file_list, threshold_minutes=30)
        file_list = [file for file, mode in classifications if mode != "broadband"]
        if not file_list:
            return None, []

    by_day = _group_files_by_day(file_list)
    day_keys = list(by_day.keys())
    if not day_keys:
        return None, []

    # the very first day of the range has no preceding day inside by_day to
    # borrow a backward buffer from -- look one calendar day earlier
    range_start = normalize_date_range(list(dates))[0]
    first_day_backward_file = _previous_day_last_file(data_directory, range_start, zpls_model)

    nc_file = os.path.join(output_directory, file_name)
    nc_files = []
    daily_averages = []

    for i, day_key in enumerate(day_keys):
        day_files = by_day[day_key]
        next_day_files = by_day[day_keys[i + 1]] if i + 1 < len(day_keys) else []
        forward_buffer = _forward_buffer_files(next_day_files, resample_freq)

        # backward buffer: always pull the immediately preceding file
        if i == 0:
            backward_buffer = [first_day_backward_file] if first_day_backward_file else []
        else:
            prev_day_files = by_day[day_keys[i - 1]]
            backward_buffer = prev_day_files[-1:] if prev_day_files else []

        combined_files = backward_buffer + day_files + forward_buffer
        desc = f'Converting and processing {len(combined_files)} raw {zpls_model} data files ({day_key})'
        echo = [_process_file(f, site, output_directory, zpls_model, xml_file, tilt_correction)
                for f in tqdm(combined_files, desc=desc)]
        echo = [e for e in echo if e is not None]
        if not echo:
            # this day (including its buffer) produced no usable data -- skip it
            # and move on
            continue

        try:
            day_ds = xr.combine_by_coords(echo, join='outer', combine_attrs='override')
        except ValueError:
            day_ds = xr.concat(echo, dim='ping_time', join='outer', combine_attrs='override')
            if 'ping_time' in day_ds.echo_range.indexes.keys():
                day_ds['echo_range'] = day_ds['echo_range'].max(dim='ping_time', skipna=True)
                day_ds['nominal_depth'] = day_ds['nominal_depth'].max(dim='ping_time', skipna=True)
        del echo

        day_ds = day_ds.sortby('ping_time')
        _, index = np.unique(day_ds['ping_time'], return_index=True)
        day_ds = day_ds.isel(ping_time=index)
        day_ds = day_ds.sortby('frequency_nominal')
        range_correction(day_ds, tilt_correction)

        # reset data types (matches the whole-chunk behavior this replaces)
        day_ds['range_sample'] = day_ds['range_sample'].astype(np.int32)
        day_ds['echo_range'] = day_ds['echo_range'].astype(np.float32)
        day_ds['nominal_depth'] = day_ds['nominal_depth'].astype(np.float32)
        day_ds['frequency_nominal'] = day_ds['frequency_nominal'].astype(np.float32)
        day_ds['Sv'] = day_ds['Sv'].astype(np.float32)

        # split off this day's own records (excludes buffer) for the full-resolution NetCDF write
        day_start = datetime.strptime(day_key, '%Y%m%d')
        day_end = day_start + timedelta(days=1)
        own_day_mask = (day_ds.ping_time >= np.datetime64(day_start)) & (day_ds.ping_time < np.datetime64(day_end))
        day_only_ds = day_ds.isel(ping_time=own_day_mask.values)

        day_nc_path = nc_file + "_Full_%s.nc" % day_key
        write_ds = day_only_ds.copy()
        write_ds['ping_time'] = write_ds['ping_time'].values.astype(np.float64) / 10.0 ** 9
        write_ds.attrs = attributes['global']
        write_ds.attrs['instrument_orientation'] = site_config[site]['instrument_orientation']
        for v in write_ds.variables:
            write_ds[v].attrs = attributes[v]
        write_ds.to_netcdf(day_nc_path, mode='w', format='NETCDF4', engine='h5netcdf')
        nc_files.append(day_nc_path)
        del write_ds

        # resample using the full day (backward buffer + current day + forward
        # buffer) so both the first bin (which may start before midnight, if
        # a file recorded late the previous day ran over) and the last bin
        # (which may span into the next day) are computed correctly
        resample_ds = day_ds.copy()
        resample_ds['ping_time'] = resample_ds['ping_time'] + time_shift
        day_avg = resample_ds.resample(ping_time=resample_freq).mean(dim='ping_time', skipna=True, keep_attrs=True)
        day_avg = day_avg.interpolate_na(dim='ping_time', max_gap=max_gap)
        day_avg = day_avg.compute()
        day_avg = day_avg.sel(ping_time=(day_avg.ping_time >= np.datetime64(day_start))
                                       & (day_avg.ping_time < np.datetime64(day_end)))
        daily_averages.append(day_avg)

        # release the expensive full-resolution data for this day before moving on
        del day_ds, day_only_ds, resample_ds
        n = 1
        while n > 0:
            n = gc.collect()

    if not daily_averages:
        return None, nc_files

    # concatenate the per-day averaged datasets the same way individual files are combined within a day
    try:
        avg_chunk = xr.combine_by_coords(daily_averages, join='outer', combine_attrs='override')
    except ValueError as e:
        avg_chunk = xr.concat(daily_averages, dim='ping_time', join='outer', combine_attrs='override')
        print(f'  combine_by_coords FAILED, used concat fallback: {e}', flush=True)
        if 'ping_time' in avg_chunk.echo_range.indexes.keys():
            avg_chunk['echo_range'] = avg_chunk['echo_range'].max(dim='ping_time', skipna=True)
            avg_chunk['nominal_depth'] = avg_chunk['nominal_depth'].max(dim='ping_time', skipna=True)

    avg_chunk = avg_chunk.sortby('ping_time')
    _, index = np.unique(avg_chunk['ping_time'], return_index=True)
    avg_chunk = avg_chunk.isel(ping_time=index)

    # trim NaN range_sample bins once, over the fully assembled chunk
    avg_chunk = avg_chunk.dropna('range_sample', subset=['echo_range'])

    return avg_chunk, nc_files


def _process_file(file, site, output_directory, zpls_model, xml_file, tilt_correction):
    """
    Internal method used for the conversion and processing of an individual raw
    sonar data file. While an internal method, this could still be used to
    create a parallel processing method to speed up the conversion and
    processing of the raw sonar data files.

    :param file: Individual raw sonar data file to process and convert.
    :param site: Site name where the data was collected.
    :param output_directory: Output directory to save the results.
    :param zpls_model: Model of bioacoustic sonar sensor used.
    :param xml_file: If the model is an AZFP, the XML file (with instrument
        calibration coefficients needed for the conversion) must also be
        specified (usually just one per deployment).
    :param tilt_correction: Tilt of the sonar transducers (typically 15
        degrees for the uncabled sensors to avoid interference from the
        riser elements).
    :return: Converted and processed bioacoustic sonar data in a xarray
        dataset object.
    """
    # convert and process the raw files using echopype
    env_params = {
        'temperature': site_config[site]['average_temperature'],  # temperature in degrees Celsius
        'salinity': site_config[site]['average_salinity'],  # salinity in PSU
        'pressure': site_config[site]['deployed_depth']  # approximate pressure (using depth m)
    }
    depth_offset = site_config[site]['depth_offset']  # height of sensor relative to site depth
    downward = site_config[site]['instrument_orientation'] == 'down'  # instrument orientation

    # load the raw file, creating an xarray dataset object
    try:
        # if this file was already converted, read the existing converted store
        # instead of reparsing the raw file
        stem = Path(file).stem
        converted_ext = '.zarr' if zpls_model == 'EK80' else '.nc'
        converted_path = Path(output_directory) / (stem + converted_ext)
        already_converted = converted_path.exists()
        if already_converted:
            ds = ep.open_converted(converted_path)
        elif zpls_model == 'AZFP':
            ds = ep.open_raw(file, sonar_model=zpls_model, xml_path=xml_file)
        else:
            ds = ep.open_raw(file, sonar_model=zpls_model)
    except Exception as e:
        print(f'Error ({e}) converting file: {file}')
        return None

    # add ICES metadata attributes
    ds['Platform']['platform_name'] = site  # OOI site name
    ds['Platform']['platform_code_ICES'] = '3164'  # ICES SHIPC code
    if site == 'CE02SHBP':
        ds['Platform']['platform_type'] = 'Fixed Benthic Node'  # ICES platform class 11
    elif site == 'CE04OSPS' or 'HYPM' in site:
        ds['Platform']['platform_type'] = 'Subsurface Mooring'  # ICES platform class 43
    else:
        ds['Platform']['platform_type'] = 'Mooring'   # ICES platform class 48

    # process the data, calculating the volume acoustic backscatter strength and the vertical range
    waveform = 'CW'  # defaults for the EK60 and EK80
    encode = 'power'
    if zpls_model == 'EK80':
        try:
            # determining waveform and encoding methods from the data (accounting for 3 different configuration modes)
            beam_grp = ds['Sonar/Beam_group1']
            has_complex = (beam_grp is not None and 'backscatter_i' in beam_grp.data_vars
                          and bool(beam_grp['backscatter_i'].notnull().any()))

            # determine if any channels are broadband, and if so drop them
            if has_complex and beam_grp is not None and 'transmit_type' in beam_grp.data_vars:
                tt = beam_grp['transmit_type'].values
                is_cw = np.array(['LFM' not in set(row) for row in tt])

                if not is_cw.all():
                    # drop LFM/broadband channels
                    cw_channels = beam_grp['channel'].values[is_cw].tolist()
                    if not cw_channels:
                        print(f'{file}: all channels are LFM/broadband, no usable CW data, end processing.')
                        del ds
                        return None
                    original_source_file = ds.source_file  # combine_echodata loses this -- restore below
                    ds = ep.combine_echodata([ds], channel_selection=cw_channels)
                    ds.source_file = original_source_file
                    beam_grp = ds['Sonar/Beam_group1']

                # clean up transmit_type NaN-padding on the retained channels
                tt_cw = beam_grp['transmit_type']
                valid_ping = (tt_cw != 'nan').any(dim='channel').compute()
                beam_trimmed = beam_grp.isel(ping_time=valid_ping.values)
                tt_fixed = xr.where(beam_trimmed['transmit_type'] == 'nan', 'CW',
                                     beam_trimmed['transmit_type'])
                beam_trimmed = beam_trimmed.assign(transmit_type=tt_fixed)
                ds['Sonar/Beam_group1'] = beam_trimmed
                beam_grp = ds['Sonar/Beam_group1']

            # set the encoding type and compute the Sv
            encode = 'complex' if has_complex else 'power'
            ds_sv = ep.calibrate.compute_Sv(ds, env_params=env_params, waveform_mode=waveform, encode_mode=encode)

            # check the number of output channels are as expected
            expected_channels = beam_grp.sizes.get('channel', 0)
            if ds_sv.sizes.get('channel', 0) != expected_channels:
                print(f'{file}: compute_Sv returned {ds_sv.sizes.get("channel", 0)} channels, '
                      f'expected {expected_channels}, end processing.')
                del ds
                return None
        except Exception as e:
            print(f'{file}: compute_Sv failed (error: {e}), end processing.')
            # manual garbage collection; echopype seems to leave a lot of detritus behind it
            del ds
            n = 1
            while n > 0:
                n = gc.collect()
            return None
    elif zpls_model == 'EK60':
        ds_sv = ep.calibrate.compute_Sv(ds, env_params=env_params, waveform_mode=waveform, encode_mode=encode)
    else:
        # AZFP processing, no waveform or encoding required
        ds_sv = ep.calibrate.compute_Sv(ds, env_params=env_params)

    # Correct reversed ping times
    if exist_reversed_time(ds_sv, "ping_time"):
        # Coerce increasing time
        coerce_increasing_time(ds_sv)

    # calculate the depth from the range
    ds_sv = ep.consolidate.add_depth(ds_sv, ds, depth_offset=depth_offset, tilt=tilt_correction, downward=downward)

    # add the split-beam angle -- only meaningful for EK60/EK80
    if zpls_model in ('EK60', 'EK80'):
        ds_sv = ep.consolidate.add_splitbeam_angle(ds_sv, ds, waveform_mode=waveform, encode_mode=encode,
                                                    to_disk=False)

    # convert the channel dimension to frequency
    ds_sv = ep.consolidate.swap_dims_channel_frequency(ds_sv)

    # extract the Sv, range and depth data
    data = ds_sv[['Sv', 'echo_range', 'depth']]

    # save the data to disk, skipping if this file was already converted
    if not already_converted:
        if zpls_model == 'EK80':
            # output the files to Zarr (while larger than the NetCDF, faster for the EK80 files)
            ds.to_zarr(Path(output_directory), overwrite=False)
        else:
            ds.to_netcdf(Path(output_directory), overwrite=False)

    # clear the echodata objects from memory and clean up after echopype
    del ds, ds_sv
    n = 1
    while n > 0:
        n = gc.collect()

    # rework the extracted dataset to make it easier to work with in further processing
    # --- convert range to a coordinate
    data['range_sample'] = data['range_sample'].astype(np.int32)  # convert the data type for range_sample
    data['echo_range'] = data['echo_range'].max(dim='ping_time', skipna=True)
    data = data.set_coords('echo_range')  # set up range as a coordinate variable
    # --- convert depth to a coordinate
    data['depth'] = data['depth'].max(dim='ping_time', skipna=True)
    data = data.set_coords('depth')  # setup depth as a coordinate variable
    data = data.rename({'depth': 'nominal_depth'})

    # make sure ping_time is monotonic and the time-stamps are unique
    data = data.sortby('ping_time')
    _, index = np.unique(data['ping_time'], return_index=True)
    data = data.isel(ping_time=index)

    return data


def zpls_echogram(site, data_directory, output_directory, dates, zpls_model, xml_file, **kwargs):
    """
    Main processing function to convert and process data from either the ASL
    AZFP or the Kongsberg Simrad EK60/EK80. Uses echopype to convert the raw
    data files (saving the converted data in NetCDF or Zarr files that conform
    to the SONAR-NetCDF4 ICES convention). Further processes the data by
    applying instrument calibration coefficients to calculate the volume
    acoustic backscatter strength (Sv re 1-m). Processed data is saved to
    daily files at full resolution and then temporally averaged to create
    echogram plots for the date range specified (averaged data is also saved).

    :param site: Site name where the data was collected
    :param data_directory: Source directory where the raw data files are
        located (assumes a standardized file structure will be followed by the
        OOI operators)
    :param output_directory: Output directory to save the results
    :param dates: Starting and ending dates to search for raw data files in the
        data directory to convert and process
    :param zpls_model: Model of bioacoustic sonar sensor used
    :param xml_file: If the model is an AZFP, the XML file (with instrument
        calibration coefficients needed for the conversion) must also be
        specified (usually just one per deployment)
    :kwargs tilt_correction: Tilt of the sonar transducers (typically 15
        degrees for the uncabled sensors to avoid interference from the
        riser elements)
    :kwargs deployed_depth: Deployment depth of the instrument
    :kwargs vertical_range: Vertical range to use in setting the extent of the
        y-axis in the echogram plots
    :kwargs colorbar_range: Volume acoustic backscatter strength range to
        use for the colorbar
    """
    # assign the keyword arguments (defaults to None of not set)
    tilt_correction = kwargs.get('tilt_correction')
    deployed_depth = kwargs.get('deployed_depth')
    vertical_range = kwargs.get('vertical_range')
    colorbar_range = kwargs.get('colorbar_range')

    # normalize the date range (handles single-day, single-month, and explicit
    # start/stop input) before dates[1] is accessed below
    dates = normalize_date_range(dates)

    # make sure the data output directory exists
    output_directory = os.path.join(output_directory, dates[0] + '-' + dates[1])
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory, exist_ok=True)

    # determine if an XML file has not been specified for AZFP data
    if zpls_model == 'AZFP' and not xml_file:
        raise ValueError('If the ZPLS model is AZFP, you must specify an XML file with the instrument '
                         'configuration and calibration parameters.')

    if zpls_model not in ['AZFP', 'EK60', 'EK80']:
        raise ValueError('The ZPLS model must be set as either AZFP, EK60 or EK80 (case sensitive)')

    file_name = set_file_name(site, dates)

    # decide resample parameters before processing
    if 'HYPM' in site:
        resample_freq = '60Min'
        time_shift = pd.to_timedelta(30, unit="min")
        max_gap = '180Min'
    else:
        resample_freq = '15Min'
        time_shift = pd.to_timedelta(450, unit="sec")
        max_gap = '45Min'

    # convert and process the data, one calendar day at a time, writing and
    # releasing each day's full-resolution data as it goes rather than
    # holding the whole chunk in memory simultaneously
    avg, nc_files = process_sonar_data(site, data_directory, output_directory, dates, zpls_model, xml_file,
                                        tilt_correction, file_name, resample_freq, time_shift, max_gap)

    # test to see if we have any data from the processing
    if avg is None:
        print(f'No data files were converted and processed. Check input settings, in particular the path to the raw '
              f'data files (or whether these were broadband files) for dates between {dates[0]} and {dates[1]}.')
        return None

    # catch a channel-count mismatch (happens when only 1 or 2 frequencies is present)
    expected_count = EXPECTED_FREQUENCY_COUNT.get(zpls_model)
    actual_count = avg.sizes.get('frequency_nominal')
    if expected_count is not None and actual_count != expected_count:
        print(f'Only {actual_count} of the expected {expected_count} frequency channels reported valid data for '
            + f'dates between {dates[0]} and {dates[1]} (frequencies present: {list(avg.frequency_nominal.values)}). '
            + f'Skipping echogram generation.')
        return None

    # generate the echogram
    long_name = site_config[site]['long_name']
    generate_echogram(avg, site, long_name, deployed_depth, output_directory, file_name, dates,
                      vertical_range=vertical_range, colorbar_range=colorbar_range)

    # add the OOI logo as a watermark
    echogram = os.path.join(output_directory, file_name + '.png')
    echo_image = Image.open(echogram)
    # noinspection PyTypeChecker
    ooi_image = Image.open(files('ooi_zpls_echograms').joinpath('ooi-logo.png'))
    width, height = echo_image.size
    transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    transparent.paste(echo_image, (0, 0))
    if max(vertical_range) > 99:
        transparent.paste(ooi_image, (96, 15), mask=ooi_image)
    else:
        transparent.paste(ooi_image, (80, 15), mask=ooi_image)

    # re-save the echogram with the added logo
    transparent.save(echogram)

    # save the averaged data
    nc_file = os.path.join(output_directory, file_name)
    avg['ping_time'] = avg['ping_time'].values.astype(np.float64) / 10.0 ** 9
    avg.attrs = attributes['global']
    avg.attrs['instrument_orientation'] = site_config[site]['instrument_orientation']
    for v in avg.variables:
        avg[v].attrs = attributes[v]

    avg_file = nc_file + '_Averaged.nc'
    avg.to_netcdf(avg_file, mode='w', format='NETCDF4', engine='h5netcdf')
    return None


def main(argv=None):
    # Creating an argparse object
    parser = argparse.ArgumentParser(description='ZPLSC/G echogram generator')

    # Creating input arguments
    parser.add_argument('-s', '--site', dest='site', type=str, required=True,
                        help='The OOI 8-letter site name for where the ZPLSC/G is located.')
    parser.add_argument('-d', '--data_directory', dest='data_directory', type=str, required=True,
                        help='The path to the root directory below which the .01A or .raw files may be found.')
    parser.add_argument('-o', '--output_directory', dest='output_directory', type=str, required=True,
                        help='The path to the root directory below which the .nc file(s) and .png plot will be saved.')
    parser.add_argument('-dr', '--date_range', dest='dates', type=str, nargs='+', required=True,
                        help=('Date range to plot as either YYYYMM or YYYYMMDD. Specifying an end date is optional, '
                              'it will be assumed to be 1 month or 1 day depending on input.'))
    parser.add_argument('-zm', '--zpls_model', dest='zpls_model', type=str, required=True,
                        help='Specifies the ZPLS instrument model, either AZFP, EK60 or EK80.')
    parser.add_argument('-xf', '--xml_file', dest='xml_file', type=str, required=False,
                        help='The path to .XML file used to process the AZFP data in the .01A files')
    parser.add_argument('-tc', '--tilt_correction', dest='tilt_correction', type=int, required=False,
                        help='Apply tilt correction in degree(s)')
    parser.add_argument('-dd', '--deployed_depth', dest='deployed_depth', type=int, required=False,
                        help='The depth where the ZPLSC/G is located at')
    parser.add_argument('-cr', '--colorbar_range', dest='colorbar_range', type=int, nargs=2, required=False,
                        help='Set colorbar range. Usage: "min" "max"')
    parser.add_argument('-vr', '--vertical_range', dest='vertical_range', type=int, nargs=2, required=False,
                        help='Set the range for the y-axis. Usage: "min" "max"')

    # parse the input arguments
    args = parser.parse_args(argv)
    site = args.site.upper()
    data_directory = os.path.abspath(args.data_directory)
    output_directory = os.path.abspath(args.output_directory)
    dates = args.dates
    zpls_model = args.zpls_model.upper()
    tilt_correction = args.tilt_correction
    deployed_depth = args.deployed_depth
    colorbar_range = args.colorbar_range
    vertical_range = args.vertical_range
    xml_file = args.xml_file
    if xml_file:
        xml_file = os.path.abspath(xml_file)

    # assign per site variables
    if site in site_config:
        # if tilt_correction flag is not set, set the tilt correction from the site configuration
        if tilt_correction is None:
            tilt_correction = site_config[site]['tilt_correction']
        # if deployed_depth flag is not set, set the deployed_depth from the site configuration
        if deployed_depth is None:
            deployed_depth = site_config[site]['deployed_depth']
        # if colorbar_range flag is not set, set the colorbar_range from the site configuration
        if colorbar_range is None:
            colorbar_range = site_config[site]['colorbar_range']
        # if vertical_range flag is not set, set the vertical_range from the site configuration
        if vertical_range is None:
            vertical_range = site_config[site]['vertical_range']
    elif site is not None:
        raise parser.error('The site name was not found in the configuration dictionary.')

    # make sure the root output directory exists
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory, exist_ok=True)

    # convert and process the data
    if zpls_model not in ['AZFP', 'EK60', 'EK80']:
        raise ValueError('The ZPLS model must be set as either AZFP, EK60 or EK80 (case sensitive)')
    else:
        zpls_echogram(site, data_directory, output_directory, dates, zpls_model, xml_file,
                      deployed_depth=deployed_depth, tilt_correction=tilt_correction,
                      colorbar_range=colorbar_range, vertical_range=vertical_range)


if __name__ == '__main__':
    main()

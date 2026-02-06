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
import warnings

import pandas as pd
import xarray as xr

from calendar import monthrange
from dask import compute, delayed
from datetime import datetime, date, timedelta
from echopype.qc import exist_reversed_time, coerce_increasing_time
from importlib.resources import files
from pandas.plotting import register_matplotlib_converters
from pathlib import Path
from PIL import Image
from tqdm.dask import TqdmCallback

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
        'long_name': 'Coastal Pioneer, Central Surface Mooring',
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
        'long_name': 'Coastal Pioneer, Inshore Surface Mooring',
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
        'long_name': 'Coastal Pioneer, Offshore Surface Mooring',
        'tilt_correction': 15,
        'colorbar_range': [-90, -50],
        'vertical_range': [0, 455],
        'deployed_depth': 455,
        'depth_offset': 1.0,
        'average_salinity': 35,
        'average_temperature': 12,
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
        'calendar': 'gregorian',
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
        'units': 'dB ',
        'comments': ('Initial estimate of the volume acoustic backscatter strength derived from the raw instrument '
                     'data using echopype to convert and process the data.'),
        'ooi_data_product': 'SONBSCA_L1'
    }
}


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


def azfp_file_list(data_directory, dates):
    """
    Generate a list of file paths pointing to the .01A files from an AZFP that
    contain the dates the user has requested.

    :param data_directory: path to directory with the AZFP .01A files.
    :param dates: starting and ending dates to use in generating the file list.
    :return: the list of potential .01A file names, including full path.
    """
    if len(dates) == 1:
        dates += [dates[0]]

    if len(dates[0]) == 6:
        dates[0] = dates[0] + '01'
        dates[1] = dates[1] + str(monthrange(int(dates[1][:4]), int(dates[1][4:]))[1])

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
    if len(dates) == 1:
        dates += [dates[0]]

    if len(dates[0]) == 6:
        dates[0] = dates[0] + '01'
        dates[1] = dates[1] + str(monthrange(int(dates[1][:4]), int(dates[1][4:]))[1])

    sdate = dparser.parse(dates[0])
    edate = dparser.parse(dates[1]) - timedelta(days=1)
    delta = edate - sdate

    file_list = []
    for i in range(delta.days + 1):
        day = sdate + timedelta(days=i)
        ek_files = glob.glob(os.path.join(data_directory, day.strftime('%m'), day.strftime('%d')) + '/*.raw')
        file_list.append(ek_files)

    return file_list


def process_sonar_data(site, data_directory, output_directory, dates, zpls_model, xml_file, tilt_correction):
    """
    Use echopype to convert and process the raw bioacoustic sonar data from
    either an AZFP (in *.01A files), or an EK60/EK80 (in *.raw files) as the
    first step in the process of generating daily and averaged processed
    NetCDF files and echograms for use by the community.

    :param site: Site name where the data was collected.
    :param data_directory: Source directory where the raw data files are
        located (assumes a standardized file structure will be followed by the
        OOI operators).
    :param output_directory: Output directory to save the results
    :param dates: Starting and ending dates to search for raw data files in the
        data directory to convert and process.
    :param zpls_model: Model of bioacoustic sonar sensor used.
    :param xml_file: If the model is an AZFP, the XML file (with instrument
        calibration coefficients needed for the conversion) must also be
        specified (usually just one per deployment).
    :param tilt_correction: Tilt of the sonar transducers (typically 15
        degrees for the uncabled sensors to minimize interference from the
        riser elements).
    :return: Converted and processed bioacoustic sonar data in a xarray
        dataset object for the date range indicated by the dates input,
        with the object sorted in time and checked to make sure the time
        record is monotonic.
    """
    # generate a list of data files given the input dates
    if zpls_model == 'AZFP':
        file_list = azfp_file_list(data_directory, dates)
    else:
        file_list = ek_file_list(data_directory, dates)

    # reset the file_list to a single index
    file_list = [file for sub in file_list for file in sub]
    if not file_list:
        # if there are no files to process, exit cleanly
        return None

    # sort the file list alphanumerically
    file_list.sort()

    # convert and process the raw files using echopype
    delayed_tasks = [delayed(_process_file)(file, site, output_directory, zpls_model, xml_file, tilt_correction)
                     for file in file_list]
    with TqdmCallback(desc=f'Converting the {len(file_list)} raw {zpls_model} data files'):
        echo = compute(*delayed_tasks, scheduler='threads', num_workers=4)

    echo = [i for i in echo if i is not None]
    if not echo:
        # if no files were processed, exit cleanly
        return None

    # concatenate the data into a single dataset
    try:
        single_ds = xr.combine_by_coords(echo, join='outer', combine_attrs='override')
    except ValueError:
        single_ds = xr.concat(echo, dim='ping_time', join='outer', combine_attrs='override')
        if 'ping_time' in single_ds.echo_range.indexes.keys():
            single_ds['echo_range'] = single_ds['echo_range'].sel(ping_time=single_ds.ping_time[0], drop=True)
            single_ds['nominal_depth'] = single_ds['nominal_depth'].sel(ping_time=single_ds.ping_time[0], drop=True)

    del echo

    # manual garbage collection; echopype seems to leave a lot of detritus behind it
    n = 1
    while n > 0:
        n = gc.collect()

    # sort the data by the time and make sure the time index is unique
    sorted_ds = single_ds.sortby('ping_time')
    _, index = np.unique(sorted_ds['ping_time'], return_index=True)
    sorted_ds = sorted_ds.isel(ping_time=index)

    # correct the range for instrument tilt
    range_correction(sorted_ds, tilt_correction)

    # pass the final, sorted Sv data back for further processing
    return sorted_ds


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

    # load the raw file, creating a xarray dataset object
    try:
        if zpls_model == 'AZFP':
            ds = ep.open_raw(file, sonar_model=zpls_model, xml_path=xml_file)
        else:
            ds = ep.open_raw(file, sonar_model=zpls_model)
    except Exception as e:
        print('Error ''%s'' converting file: %s' % (e, file))
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
    waveform = []  # default for the AZFP and EK60
    encode = []    # default for the AZFP and EK60
    if zpls_model == 'EK80':
        # setting as defaults for the EK80, but may require resetting
        waveform = 'CW'
        encode = 'power'
        try:
            ds_sv = ep.calibrate.compute_Sv(ds, env_params=env_params, waveform_mode=waveform, encode_mode=encode)
        except Exception as e:
            print(f'Unit might be running in broadband mode (error: {e}), changing the configuration')
            try:
                waveform = 'BB'
                encode = 'complex'
                ds_sv = ep.calibrate.compute_Sv(ds, env_params=env_params, waveform_mode=waveform, encode_mode=encode)
            except Exception as e:
                print(f'Error processing file (unknown configuration): {file}, error message: {e}.')
                return None
    else:
        # the AZFP and EK60 are narrowband
        ds_sv = ep.calibrate.compute_Sv(ds, env_params=env_params, waveform_mode=waveform, encode_mode=encode)

    # Correct reversed ping times
    if exist_reversed_time(ds_sv, "ping_time"):
        # Coerce increasing time
        coerce_increasing_time(ds_sv)

    # calculate the depth from the range and convert the channel dimension to frequency
    ds_sv = ep.consolidate.add_depth(ds_sv, ds, depth_offset=depth_offset, tilt=tilt_correction, downward=downward)
    ds_sv = ep.consolidate.swap_dims_channel_frequency(ds_sv)

    # add the split-beam angle
    ds_sv = ep.consolidate.add_splitbeam_angle(ds_sv, ds, waveform_mode=waveform, encode_mode=encode, to_disk=False)

    # extract the Sv, range and depth data
    data = ds_sv[['Sv', 'echo_range', 'depth']]

    # save the data to NetCDF or Zarr files (will automatically skip if already created)
    if zpls_model == 'AZFP':
        ds.to_netcdf(Path(output_directory))
    else:
        ds.to_zarr(Path(output_directory), overwrite=False)

    # clear the echodata objects from memory
    del ds, ds_sv

    # rework the extracted dataset to make it easier to work with in further processing
    # --- convert range to a coordinate
    data['range_sample'] = data['range_sample'].astype(np.int32)  # convert the data type for range_sample
    data['echo_range'] = data['echo_range'].sel(ping_time=data.ping_time[0], drop=True)
    data = data.set_coords('echo_range')  # setup range as a coordinate variable
    # --- convert depth to a coordinate
    data['depth'] = data['depth'].sel(ping_time=data.ping_time[0], drop=True)
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

    # make sure the data output directory exists
    output_directory = os.path.join(output_directory, dates[0] + '-' + dates[1])
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory, exist_ok=True)

    # determine if an XML file has not been specified for AZFP data
    if zpls_model == 'AZFP' and not xml_file:
        raise ValueError('If the ZPLS model is AZFP, you must specify an XML file with the instrument '
                         'configuration and calibration parameters.')

    # convert and process the data
    if zpls_model not in ['AZFP', 'EK60', 'EK80']:
        raise ValueError('The ZPLS model must be set as either AZFP, EK60 or EK80 (case sensitive)')
    else:
        data = process_sonar_data(site, data_directory, output_directory, dates, zpls_model, xml_file, tilt_correction)

    # test to see if we have any data from the processing
    if not data:
        raise SystemExit('No data files were converted and processed. Check input settings, in particular the path '
                         'to the raw data files for dates between %s and %s.' % (dates[0], dates[1]))

    # save the full resolution processed data to daily NetCDF files
    file_name = set_file_name(site, dates)

    # reset data types (helps to control size of NetCDF files)
    data['range_sample'] = data['range_sample'].astype(np.int32)
    data['echo_range'] = data['echo_range'].astype(np.float32)
    data['nominal_depth'] = data['nominal_depth'].astype(np.float32)
    data['frequency_nominal'] = data['frequency_nominal'].astype(np.float32)
    data['Sv'] = data['Sv'].astype(np.float32)

    # split the data into daily records
    days, datasets = zip(*data.groupby("ping_time.day"))

    # create a list of file names based on the day of the record
    start = datetime.strptime(dates[0], '%Y%m%d')
    stop = datetime.strptime(dates[1], '%Y%m%d')
    date_list = [start + timedelta(days=x) for x in range(0, (stop - start).days)]
    nc_file = os.path.join(output_directory, file_name)
    nc_files = []
    for day in days:
        for dt in date_list:
            if dt.day == day:
                nc_files.append(nc_file + "_Full_%s.nc" % dt.strftime('%Y%m%d'))

    # convert ping_time from a datetime64[ns] object to a float (seconds since 1970) and update the attributes
    for dataset in datasets:
        dataset['ping_time'] = dataset['ping_time'].values.astype(np.float64) / 10.0 ** 9
        dataset.attrs = attributes['global']
        dataset.attrs['instrument_orientation'] = site_config[site]['instrument_orientation']

        for v in dataset.variables:
            dataset[v].attrs = attributes[v]

    # save the daily files
    xr.save_mfdataset(datasets, nc_files, mode='w', format='NETCDF4', engine='h5netcdf')

    # clean up any NaN's in the range values (some EK60 files seem to have this problem)
    data = data.dropna('range_sample', subset=['echo_range'])

    # if a global mooring, create hourly averaged data records, otherwise create 15-minute records
    if 'HYPM' in site:
        # resample the data into a 60-minute averaged record, filling gaps less than 180 minutes
        data['ping_time'] = data['ping_time'] + pd.to_timedelta(30, unit="min")
        avg = data.resample(ping_time='60Min').mean(dim='ping_time', skipna=True, keep_attrs=True)
        avg = avg.interpolate_na(dim='ping_time', max_gap='180Min')
    else:
        # resample the data into a 15-minute averaged record, filling gaps less than 45 minutes
        data['ping_time'] = data['ping_time'] + pd.to_timedelta(450, unit="sec")
        avg = data.resample(ping_time='15Min').mean(dim='ping_time', skipna=True, keep_attrs=True)
        avg = avg.interpolate_na(dim='ping_time', max_gap='45Min')

    # generate the echogram
    avg = avg.compute()
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
    avg['ping_time'] = avg['ping_time'].values.astype(np.float64) / 10.0 ** 9
    avg.attrs = attributes['global']
    avg.attrs['instrument_orientation'] = site_config[site]['instrument_orientation']
    for v in avg.variables:
        avg[v].attrs = attributes[v]

    avg_file = nc_file + '_Averaged.nc'
    avg.to_netcdf(avg_file, mode='w', format='NETCDF4', engine='h5netcdf')


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

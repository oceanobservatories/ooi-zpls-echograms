# OOI Bioacoustic Sonar Processing and Echogram Generation

**Authors**
James Kuo, jkuo@whoi.edu; Stephanie Petillo, spetillo@whoi.edu; and Christopher Wingard, chris.wingard@oregonstate.edu  

## Description

The Ocean Observatories Initiative (OOI) collects ocean sonar, or bioacoustic sonar data, from most of the sites that
comprise the different Coastal and Global arrays. The sensor type used depends on whether the site is cabled or 
uncabled. The [ASL Environmental Sciences Acoustic Zooplankton Fish Profiler (AZFP)](https://www.aslenv.com/product-details.html#AZFP) is 
used at the uncabled Coastal and Global (CG) sites, while the cabled sites use a Kongsberg Maritime Simrad echo
sounder -- the (now discontinued) [EK60](https://www.kongsberg.com/discovery/products/discontinued/simrad-ek60/)
prior to summer 2023, and the [EK80](https://www.kongsberg.com/what-we-do/ocean-space/ocean-science/ek-scientific-echo-sounder/)
since. The table below provides a full list of the arrays, sites and sensor types where 
the bioacoustic sonar sensors (a total of 17) are deployed.

**Note on EK80 processing:** this pipeline processes EK80 narrowband (CW) data recorded with either power or complex
sample encoding; the encoding is detected per file. Broadband (LFM) channels are not processed: when a file contains
both CW and LFM channels, the LFM channels are dropped and the CW channels kept, and files with only LFM channels are
skipped. Files recorded at a full broadband duty cycle are identified by their inter-file cadence (under 30 minutes)
and skipped before conversion; this heuristic is approximately 99% effective, so a small fraction may still need
manual review.

|         Array          |                           Site                            | Sensor Model | Depth | Description                                                     |
|:----------------------:|:---------------------------------------------------------:|:------------:|:-----:|:----------------------------------------------------------------|
|   Coastal Endurance    | [CE01ISSM](https://oceanobservatories.org/site/ce01issm/) |     AZFP     | 25 m  | Oregon Inshore Surface Mooring                                  |
|   Coastal Endurance    | [CE02SHBP](https://oceanobservatories.org/site/ce02shbp/) |  EK60/EK80   | 80 m  | Oregon Shelf Cabled Benthic Experiment Package                  |
|   Coastal Endurance    | [CE04OSPS](https://oceanobservatories.org/site/ce04osps/) |  EK60/EK80   | 200 m | Oregon Offshore Cabled Shallow Profiler Mooring                 |
|   Coastal Endurance    | [CE06ISSM](https://oceanobservatories.org/site/ce06issm/) |     AZFP     | 29 m  | Washington Inshore Surface Mooring                              |
|   Coastal Endurance    | [CE07SHSM](https://oceanobservatories.org/site/ce07shsm/) |     AZFP     | 87 m  | Washington Shelf Surface Mooring                                |
|   Coastal Endurance    | [CE09OSSM](https://oceanobservatories.org/site/ce09ossm/) |     AZFP     | 542 m | Washington Offshore Surface Mooring                             |
|  Coastal Pioneer NES   | [CP03ISSM](https://oceanobservatories.org/site/cp03issm/) |     AZFP     | 95 m  | Inshore Surface Mooring                                         |
|  Coastal Pioneer NES   | [CP01CNSM](https://oceanobservatories.org/site/cp01cnsm/) |     AZFP     | 135 m | Central Surface Mooring                                         |
|  Coastal Pioneer NES   | [CP04OSSM](https://oceanobservatories.org/site/cp04ossm/) |     AZFP     | 450 m | Offshore Surface Mooring                                        |
|  Coastal Pioneer MAB   | [CP11NOSM](https://oceanobservatories.org/site/cp11nosm/) |     AZFP     | 95 m  | Northern Surface Mooring                                        |
|  Coastal Pioneer MAB   | [CP10CNSM](https://oceanobservatories.org/site/cp10cnsm/) |     AZFP     | 135 m | Central Surface Mooring                                         |
|  Coastal Pioneer MAB   | [CP11SOSM](https://oceanobservatories.org/site/cp11sosm/) |     AZFP     | 450 m | Southern Surface Mooring                                        |
| Global Argentine Basin | [GA02HYPM](https://oceanobservatories.org/site/ga02hypm/) |     AZFP     | 150 m | Apex Profiler Mooring, both upward and downward looking sensors |
|  Global Irminger Sea   | [GI02HYPM](https://oceanobservatories.org/site/gi02hypm/) |     AZFP     | 150 m | Apex Profiler Mooring, both upward and downward looking sensors |
|  Global Station Papa   | [GP02HYPM](https://oceanobservatories.org/site/gp02hypm/) |     AZFP     | 150 m | Apex Profiler Mooring, both upward and downward looking sensors |
| Global Southern Ocean  | [GS02HYPM](https://oceanobservatories.org/site/gs02hypm/) |     AZFP     | 150 m | Apex Profiler Mooring, both upward and downward looking sensors |

[Echopype](https://echopype.readthedocs.io/en/latest/), the open-source ocean sonar data processing module, is utilized 
to process the OOI bioacoustic sonar data from the cabled and uncabled sensors. Weekly echograms are produced so 
the user community can quickly assess the quality and applicability of the data to their research needs. 
Additionally, preliminary processed data (saved to NetCDF files) is generated to facilitate access to the data in a
standard format for others to use for further processing and analysis.

This code was originally developed as part of the [ooicgsn-data-tools](https://github.com/oceanobservatories/ooicgsn-data-tools) 
toolbox, but was extracted out to make it standalone and installable as a package for internal OOI use in processing 
the realtime cabled data from [CE02SHBP](https://oceanobservatories.org/site/ce02shbp/) and 
[CE04OSPS](https://oceanobservatories.org/site/ce04osps/).

## Installation and Setup

Future releases will make this code available for installation via conda-forge. For now users will need to download (or 
use git to clone) the code to their local computer, set up a virtual environment for the processing, and then install a 
development copy of the code into that environment. The installation and setup steps below, assume the user has already 
installed either [anaconda](https://www.anaconda.com/products/individual) or [miniconda](https://docs.conda.io/en/latest/miniconda.html) 
to use in executing the Python code.

```shell
# download the ooi-zpls-echograms code
mkdir -p /home/ooiuser/code
cd /home/ooiuser/code
git clone https://github.com/oceanobservatories/ooi-zpls-echograms.git
cd ooi-zpls-echograms

# configure the OOI python environment
conda env create -f environment.yml
conda activate echogram

# install the package as a local development package
pip install -e .
```

Note, the use of `/home/ooiuser/code` above, and `/home/ooiuser/data` below, are solely for the purposes of these
examples. It is expected that users will have their own directory structure. Adapt and change as needed.

`environment.yml` defines the development environment. Production processing runs in a container built from the
`Dockerfile`, which creates the environment from the pinned `environment.lock.txt` so the validated package versions
are reproduced exactly; see [docs/deployment.md](docs/deployment.md).

## Usage

The code is intended to be used largely from the command line in a shell. Though users can import `ooi_zpls_echograms` 
as a module and run the individual functions directly, the intent is to provide a means of batch processing the 
bioacoustic sonar data for internal OOI use. Scripts used to run the processing are available in the [utilities](utilities)
directory. Once installed (see Installation and Setup), the `zpls-echogram` command is available directly on the
PATH. The basic sequence of commands is:

```shell
zpls-echogram -s [site_code] -d [data_directory] -o [output_directory] -dr [dates] -zm [instrument_type]
```

The inputs to the function are defined below, based on whether they are required or optional.

|    Required Inputs     | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |  
|:----------------------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|       -s, --site       | The OOI 8-letter site name for where the ZPLSC/G is located.                                                                                                                                                                                                                                                                                                                                                                                                                      |  
|  -d, --data_directory  | The path to the root data directory, below which the .01A or .raw files may be found.                                                                                                                                                                                                                                                                                                                                                                                             |  
| -o, --output_directory | The path to the root data directory where .nc file and .png plot will be saved.                                                                                                                                                                                                                                                                                                                                                                                                   |  
|   -dr, --date_range    | The date range to process, as YYYYMMDD or YYYYMM. The stop date is exclusive (processing runs up to, but not including, it). Both dates must use the same format. Examples:<br>`-dr 20200118` processes the day 01/18/2020,<br>`-dr 202001` processes the whole month, 01/01/2020 through 01/31/2020,<br>`-dr 202001 202002` processes 01/01/2020 through 02/29/2020 (a month stop includes that whole month),<br>`-dr 20200115 20200216` processes 01/15/2020 through 02/15/2020 |  
|   -zm, --zpls_model    | Sensor model: EK60 or EK80 for cabled data, or an AZFP for uncabled                                                                                                                                                                                                                                                                                                                                                                                                               |
|  **-xf, --xml_file**   | The path to .xml file to use if the sensor model is an AZFP. **Required if the sensor model is AZFP**                                                                                                                                                                                                                                                                                                                                                                             |  

|     Optional flags     | Description                                    |  
|:----------------------:|:-----------------------------------------------|
| -tc, --tilt_correction | Apply tilt correction in degree(s)             |  
| -dd, --deployed_depth  | The depth where the ZPLSC/G is located at      |  
| -cr, --colorbar_range  | Set colorbar range. Usage: "min max"           |  
| -vr, --vertical_range  | Set the range for the y-axis. Usage: "min max" |  

### Usage Notes

* The root data directory depends on the data source. For cabled data (EK60 or EK80), the path to the root data
  directory ends with the year (e.g. `/home/ooiuser/data/CE04OSPS/PC01B/05-ZPLSCB102/2017`); when a requested date
  range crosses into an adjacent year, that year's sibling folder is searched automatically. For uncabled data, the
  path to the root data directory ends with `DATA`
  (e.g. `/home/ooiuser/data/CP01CNSM/R00012/instruments/dcl37/ZPLSC_sn55080/DATA`).
 
* The path to the `.xml` file is required if the ZPLS model is an AZFP. The `.xml` file contains instrument specific
  settings and calibration coefficients needed to process the data.

* In the case of the global Apex Profiler (subsurface) moorings, the OOI 8-letter site name is appended with either an 
  "_Upper" or "_Lower" to indicate which of the sensors is being used (there are two on the 150 m sphere, one looking 
  up towards the surface, and the other looking down).

* The colorbar range and colormap for each site are set in `site_config` in `zpls_echogram.py` (`colorbar_range` and
  `colormap`, any colormap name registered with matplotlib, e.g. `magma` or `cmo.balance`). The range can also be
  overridden per run with the optional `-cr` flag. After changing either, existing echograms can be redrawn from their
  `_Averaged.nc` files with `utilities/regenerate_echograms.py`, without reprocessing any data.

* If `-zm EK80` is used, only narrowband (CW) channels are processed, with power or complex encoding detected per
  file. Broadband (LFM) channels are dropped, files with no CW channels are skipped, and files recorded at a full
  broadband duty cycle (identified by inter-file gaps under 30 minutes) are skipped before conversion.
  
## Utilities and Related Tools

| Tool                                               | Purpose                                                                                                                             |
|:---------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------------|
| `utilities/batch_zplsc_cabled.sh`                  | Batch process a year of cabled EK60/EK80 data in weekly chunks (4 in parallel, per-chunk logs)                                      |
| `utilities/batch_zplsc_uncabled.sh`                | Batch process an AZFP deployment in weekly chunks                                                                                   |
| `utilities/weekly_trailing_backlog.sh`             | Reprocess the last N complete weeks of cabled EK80 data to repair days that were incomplete when the nightly run happened           |
| `utilities/classify_configurations.py`             | Inventory EK80 raw files by recording configuration (pulse form, encoding, pulse length, band, ping timing) using only file headers |
| `utilities/regenerate_echograms.py`                | Redraw echogram PNGs from existing `_Averaged.nc` files with the current `site_config` colormap and ranges                          |
| `python -m ooi_zpls_echograms.cabled_nrt_echogram` | Nightly near real-time processing for the cabled EK80 sites; see [docs/nrt.md](docs/nrt.md)                                         |
| `python -m ooi_zpls_echograms.duplication_check`   | Find and remove duplicate EK80 converted stores left in adjacent weekly folders by backlog runs                                     |

## Raw and Processed Data Folders and Files

### Raw Data
The raw ZPLS data can be found on the [OOI Raw Data server](https://rawdata.oceanobservatories.org/files/), with the
directory structure dependent on the ZPLS instrument type (an AZFP, or an EK60 or EK80).

For the AZFP, the data are organized by the instrument in a folder called `DATA`, below which the files are organized
in folders named according the year and month (e.g. `201610`) the data was collected. The files are named according to 
the year, month, day and hour the data were recorded (e.g. `16101401.01A`). The higher level directory structure above
`DATA` is created by OOI technicians after the mooring is recovered. If the ZPLS data from the 
[Global Argentine Basin, upward looking sensor for Deployment 3](https://rawdata.oceanobservatories.org/files/GA02HYPM/R00003/instruments/ZPLSG_sn55067/) 
were downloaded to a local folder in the users `/home/ooiuser/data` directory named `GA`, the folders would look like:

```
/home/ooiuser/data/GA/ZPLSG_sn55067/DATA/201610
    GA/ZPLSG_sn55067/DATA/201610/16101401.01A
    GA/ZPLSG_sn55067/DATA/201610/16101402.01A
    GA/ZPLSG_sn55067/DATA/201610/16101403.01A
    GA/ZPLSG_sn55067/DATA/201610/*.01A
    GA/ZPLSG_sn55067/DATA/201610/16101417.XML
/home/ooiuser/data/GA/ZPLSG_sn55067/DATA/201611
    GA/ZPLSG_sn55067/DATA/201611/16111401.01A
    GA/ZPLSG_sn55067/DATA/201611/16111402.01A
    GA/ZPLSG_sn55067/DATA/201611/16111403.01A
    GA/ZPLSG_sn55067/DATA/201611/*.01A
```

For the EK60, the data are organized by OOI technicians in folders based on the year, month and day (e.g. `2017/01/01`)
the data was collected. Files are named by the instrument according to the date and time the file was created (e.g. 
`OOI-D20170831-T113333.raw`). If the ZPLS data from the [Coastal Endurance, Oregon Offshore Cabled Shallow Profiler 
Mooring, 200 m Platform](https://rawdata.oceanobservatories.org/files/CE04OSPS/PC01B/05-ZPLSCB102) from 2017 were 
downloaded to local folder in the user's `/home/ooiuser/data` directory named `CE04`, the folders would look like:

```
/home/ooiuser/data/CE04/PC01B/05-ZPLSCB102/2017/01/01/
    CE04/PC01B/05-ZPLSCB102/2017/01/01/OOI-D20170101-T000000.bot
    CE04/PC01B/05-ZPLSCB102/2017/01/01/OOI-D20170101-T000000.idx
    CE04/PC01B/05-ZPLSCB102/2017/01/01/OOI-D20170101-T000000.raw
/home/ooiuser/data/CE04/PC01B/05-ZPLSCB102/2017/01/02
    CE04/PC01B/05-ZPLSCB102/2017/01/02/OOI-D20170102-T000000.bot
    CE04/PC01B/05-ZPLSCB102/2017/01/02/OOI-D20170102-T000000.idx
    CE04/PC01B/05-ZPLSCB102/2017/01/02/OOI-D20170102-T000000.raw
```

The EK80 data, which replaced the EK60 at both cabled sites in summer 2023, use the same year, month and day folder
structure. Files are named with the instrument identifier and the date and time the file was created (e.g.
`ZPLSCB102-D20250615-T120210.raw`).

For the AZFP example above, the root data directory would be `/home/ooiuser/data/GA/ZPLSG_sn55067/DATA`. For the EK60
or EK80 example, the root data directory would be `/home/ooiuser/data/CE04/PC01B/05-ZPLSCB102/2017`.

### Processed Data
Processed data are created in a folder of the users choice. We recommend placing the data at the same level as the root 
data directory, but in a separate folder called `processed`. The data in the `processed` folder are organized into 
sub-folders named according to the date range entered for processing. For example, using the AZFP data from above, if 
the date range was `-dr 20170101 20170108` (2017-01-01 through 2017-01-07; the stop date is exclusive), then the
processed data would end up in a folder `20170101-20170108`.
The full path would be `/home/ooiuser/data/GA/ZPLSG_sn55067/processed/20170101-20170108/`

There are three types of processed data created by the zpls_echogram script:

1. **Converted**: These are files converted from the raw format (either `.01A` or `.raw`) by the echopype convert
   function, 1:1 with the source raw data files. AZFP and EK60 data are saved as NetCDF (`.nc`) files and EK80 data as
   Zarr (`.zarr`) stores. Both use the
   [SONAR-NetCDF4](http://www.ices.dk/sites/pub/Publication%20Reports/Cooperative%20Research%20Report%20(CRR)/CRR341.pdf)
   formatting convention.
2. **Processed**: The echopype calibration function (`ep.calibrate.compute_Sv`), taking the converted files as inputs,
   is used to calculate the volume acoustic backscatter strength (Sv), the range (distance from the sensor face) in
   meters, and the nominal depth of each range bin. This subset of data is saved in daily `.nc` files that use the site
   and date range to construct the file name. Continuing to use the AZFP example from above, data for 2017-01-01 would
   be saved in `GA02HYPM_Upper_Bioacoustic_Echogram_20170101-20170108_Calibrated_Sv_Full_20170101.nc`.
3. **Averaged**: Takes the processed data one step further and applies temporal averaging (15 minute means for the
   coastal ZPLSC and 60 minute means for the global ZPLSG) for use in creating the echograms. Missing data is filled in
   via linear interpolation for gaps of up to 3x the averaging time window. The averaged Sv, range and nominal depth
   are saved in a single `.nc` file covering the date range specified, using a similar file naming convention as the
   processed data above except the term `Full_20170101` in the file name above is replaced with `Averaged`
   (e.g. `GA02HYPM_Upper_Bioacoustic_Echogram_20170101-20170108_Calibrated_Sv_Averaged.nc`).
   
An echogram covering the time period specified by the date range is created from the averaged data and saved along with
the three data types listed above. The echogram shares the base name of the data files (e.g.,
`GA02HYPM_Upper_Bioacoustic_Echogram_20170101-20170108_Calibrated_Sv.png`).

## Processing Examples

The examples below show how to use the Python script with some of the different options from above. The examples are
all built around using the AZFP data from the Global Argentine Basin upward looking sensor.

**Example 1:**
```shell
# set default data directories and the XML file 
GA_DATA="/home/ooiuser/data/GA/ZPLSG_sn55067/DATA"
GA_PROC="/home/ooiuser/data/GA/ZPLSG_sn55067/processed"
GA_XML="/home/ooiuser/data/GA/ZPLSG_sn55067/DATA/201610/16101417.XML"

# set the site, the script will look at the default mooring configuration and
# apply the tilt angle correction (15 degrees for GA02HYPM_Upper) and the 
# deployment depth (150 m for GA02HYPM_Upper). 
SITE="GA02HYPM_Upper"

# convert and process the data
conda activate echogram
zpls-echogram -s $SITE -d $GA_DATA -o $GA_PROC -dr 20161115 20161116 -zm AZFP -xf $GA_XML
```
Process data for 2016-11-15 (the stop date is exclusive). The `.nc` files and `.png` plot will be stored under
`/home/ooiuser/data/GA/ZPLSG_sn55067/processed/20161115-20161116/`.

**Example 2:**  
```shell
zpls-echogram -s $SITE -d $GA_DATA -o $GA_PROC -dr 201611 -zm AZFP -xf $GA_XML
```
Process the data for the entire month of November, from 2016-11-01 through 2016-11-30. The `.nc` files and `.png` plot
will be stored under `/home/ooiuser/data/GA/ZPLSG_sn55067/processed/20161101-20161201/`.

**Example 3:**  
```shell
zpls-echogram -s $SITE -d $GA_DATA -o $GA_PROC -dr 201611 -zm AZFP -xf $GA_XML -tc 10
```
Change the default tilt correction angle to 10 degrees via the optional `-tc` flag.

**Example 4:**  
```shell
zpls-echogram -s $SITE -d $GA_DATA -o $GA_PROC -dr 201611 -zm AZFP -xf $GA_XML -dd 160
```
If the instrument is deployed at 160 m, instead of the design depth of 150 m. The optional flag `-dd 160` will 
override the mooring configuration.

**Example 5:**
```shell
zpls-echogram -s $SITE -d $GA_DATA -o $GA_PROC -dr 201611 -zm AZFP -xf $GA_XML -cr -120 -20 -dd 160
```
Change both the deployed depth to 160 m and the default colorbar range to -120 to -20 dB via the optional `-cr` flag.

**Example 6:**  
```shell
zpls-echogram -s $SITE -d $GA_DATA -o $GA_PROC -xf $GA_XML -dr 201611 -zm AZFP -vr 0 160 -dd 160
```
Change the default vertical range to use 0 to 160 m for the new deployment depth of 160 m via the optional `-vr` flag.

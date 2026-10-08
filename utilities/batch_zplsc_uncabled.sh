#!/bin/bash
#
# Setup a batch processing job for the recovered data from an uncabled AZFP
# bioacoustic sonar sensor.
#
# C. Wingard 2021-11-10
#
# NOTE: CONDA_SH is host/container-specific and MUST resolve to a valid
# conda.sh for the environment this script runs in -- especially if invoked
# from cron, which does not source .bashrc/.profile.
CONDA_SH="${CONDA_SH:-/home/ooiuser/miniconda3/etc/profile.d/conda.sh}"

set -euo pipefail

# Parse the command line inputs, setting the data directories and processing dates
if [ $# -ne 6 ]; then
    echo "$0: required inputs are the site name, the path to the raw and processed data"
    echo "directories, the path to the XML file with instrument specific calibration"
    echo "coefficients, and the starting and ending dates (format is YYYY-MM-DD) of the"
    echo "deployment to batch process."
    echo ""
    echo "    example: $0 ce07shsm /home/ooiuser/data/raw/CE07SHSM/R00010/instrmts/dcl37/ZPLSC_sn55099/DATA \\ "
    echo "        /home/ooiuser/data/raw/CE07SHSM/R00010/instrmts/dcl37/ZPLSC_sn55099/processed \\ "
    echo "        /home/ooiuser/data/raw/CE07SHSM/R00010/instrmts/dcl37/ZPLSC_sn55099/DATA/201910/19101018.XML \\ "
    echo "        \"2019-10-10\" \"2020-07-16\""
    exit 1
fi
SITE=${1^^}
DATA_DIR=$2
PROC_DIR=$3
XML_FILE=$4
START_DATE=`date -u +%Y%m%d -d $5`
END_DATE=`date -u +%Y%m%d -d $6`

# activate the echogram environment
. "$CONDA_SH" || { echo "$0: failed to source $CONDA_SH" >&2; exit 1; }
conda activate echogram || { echo "$0: failed to activate 'echogram' env" >&2; exit 1; }

# LOG_DIR is where per-chunk stdout/stderr goes. Override via `-e LOG_DIR=...`
LOG_DIR="${LOG_DIR:-/zplsc_processing/logs/$SITE}"
mkdir -p "$LOG_DIR"

# Set up concurrent parallel processing using 4 cores (equates to 4 weeks)
N=4
FAILED=0

# process the data, using 2012-01-01 as the base year for all plots
for d in $(seq $(date -u +%s -d "2012-01-01") +604800 $(date -u +%s -d $END_DATE)); do
    start_date=`date -u +%Y%m%d -d @$d`
    stop_date=`date -u +%Y%m%d -d "$start_date+7days"`
    if [[ $stop_date -gt $START_DATE ]]; then 
        chunk_log="$LOG_DIR/${start_date}_${stop_date}.log"
        (zpls-echogram -s $SITE -d $DATA_DIR -o $PROC_DIR -dr $start_date $stop_date -zm AZFP -xf $XML_FILE) \
            > "$chunk_log" 2>&1 &
    fi
    while (( $(jobs -rp | wc -l) >= N )); do
        # there are already $N jobs outstanding, wait for a job to finish
        wait -n -p done_pid || { echo "$0: job (PID $done_pid) failed, see $LOG_DIR" >&2; FAILED=1; }
    done
done
# drain remaining jobs
while (( $(jobs -rp | wc -l) > 0 )); do
    wait -n -p done_pid || { echo "$0: job (PID $done_pid) failed, see $LOG_DIR" >&2; FAILED=1; }
done

if (( FAILED != 0 )); then
    echo "$0: one or more processing jobs failed, see messages above" >&2
    exit 1
fi

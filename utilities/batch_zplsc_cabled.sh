#!/bin/bash
#
# Setup a batch processing job for telemetered data files from a cabled EK60
# or EK80 bioacoustic sonar sensor.
#
# C. Wingard 2021-11-10
#
# NOTE: CONDA_SH is host/container-specific and MUST resolve to a valid
# conda.sh for the environment this script runs in -- especially if invoked
# from cron, which does not source .bashrc/.profile and so cannot rely on
# $CONDA_EXE or anything else from an interactive shell's environment.
# Override by setting CONDA_SH in the calling environment (e.g. via `podman
# run -e CONDA_SH=/opt/conda/etc/profile.d/conda.sh`); otherwise this falls
# back to the host default below.
CONDA_SH="${CONDA_SH:-/home/ooiuser/miniconda3/etc/profile.d/conda.sh}"

set -euo pipefail

# Parse the command line inputs, setting the data directories and processing dates
if [ $# -ne 6 ]; then
    echo "$0: required inputs are the site name, the EK model, the path to the raw and"
    echo "processed data directories, and the starting and ending dates (format is"
    echo "YYYY-MM-DD) of the year to batch process."
    echo ""
    echo "    example: $0 CE04OSPS EK60 /home/ooiuser/data/raw/CE04OSPS/PC01B/05-ZPLSCB102/2017 \\ "
    echo "        /home/ooiuser/data/raw/CE04OSPS/PC01B/05-ZPLSCB102/2017/processed \\ "
    echo "        \"2017-01-01\" \"2017-09-16\""
    exit 1
fi
SITE=${1^^}
ZPLS_MODEL=${2^^}
DATA_DIR=$3
PROC_DIR=$4
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
        (zpls-echogram -s $SITE -d $DATA_DIR -o $PROC_DIR -dr $start_date $stop_date -zm $ZPLS_MODEL) \
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

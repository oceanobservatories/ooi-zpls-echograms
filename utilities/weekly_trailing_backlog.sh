#!/bin/bash
# Weekly trailing backlog for the cabled EK80 near real-time job.
#
# Re-runs the last N weeks (default 1) through batch_zplsc_cabled.sh to repair
# days that were short because raw files were only partially synced when the
# nightly job ran. All *.zarr stores in each week folder are deleted first so
# every raw file is reconverted from the complete copy.
#
# usage: weekly_trailing_backlog.sh SITE DATA_ROOT PROC_ROOT [N_WEEKS]
#   DATA_ROOT  raw data parent directory, above the per-year folders
#   PROC_ROOT  processed output parent directory, above the per-year 'processed' folders
# set DRY_RUN=1 to print what would be deleted and run without changing anything.
set -euo pipefail

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
    echo "usage: $0 SITE DATA_ROOT PROC_ROOT [N_WEEKS]" >&2
    exit 1
fi

SITE=${1^^}
DATA_ROOT=${2%/}
PROC_ROOT=${3%/}
N_WEEKS=${4:-1}
DRY_RUN="${DRY_RUN:-0}"

if ! [[ "$N_WEEKS" =~ ^[1-9][0-9]*$ ]]; then
    echo "N_WEEKS must be a positive integer, got: $N_WEEKS" >&2
    exit 1
fi

BATCH="$(dirname "$0")/batch_zplsc_cabled.sh"
WEEK_SECONDS=604800
EPOCH=$(date -u +%s -d "2012-01-01")
TODAY=$(date -u +%s -d "$(date -u +%Y-%m-%d)")
CURRENT_WEEK=$(( (TODAY - EPOCH) / WEEK_SECONDS ))

declare -A Y_START Y_END
WEEKS=()
FAILED=0

for (( i = N_WEEKS; i >= 1; i-- )); do
    start_s=$(( EPOCH + (CURRENT_WEEK - i) * WEEK_SECONDS ))
    stop_s=$(( start_s + WEEK_SECONDS ))
    start=$(date -u +%Y-%m-%d -d "@$start_s")
    last_day=$(date -u +%Y-%m-%d -d "@$(( stop_s - 86400 ))")
    start_c=$(date -u +%Y%m%d -d "@$start_s")
    stop_c=$(date -u +%Y%m%d -d "@$stop_s")
    stop_year=$(date -u +%Y -d "@$stop_s")
    week_dir="$PROC_ROOT/$stop_year/processed/${start_c}-${stop_c}"
    WEEKS+=("$week_dir|$start_c")

    if [ -d "$week_dir" ]; then
        for store in "$week_dir"/*.zarr; do
            [ -d "$store" ] || continue
            if [ "$DRY_RUN" = "1" ]; then
                echo "DRY_RUN: would remove $store"
            else
                rm -rf "$store"
            fi
        done
    fi

    [[ -n "${Y_START[$stop_year]:-}" ]] || Y_START[$stop_year]=$start
    Y_END[$stop_year]=$last_day
done

for year in $(printf '%s\n' "${!Y_START[@]}" | sort); do
    if [ "$DRY_RUN" = "1" ]; then
        echo "DRY_RUN: bash $BATCH $SITE EK80 $DATA_ROOT/$year $PROC_ROOT/$year/processed ${Y_START[$year]} ${Y_END[$year]}"
    else
        bash "$BATCH" "$SITE" EK80 "$DATA_ROOT/$year" "$PROC_ROOT/$year/processed" "${Y_START[$year]}" "${Y_END[$year]}" \
            || FAILED=1
    fi
done

# remove backward-buffer copies (stores whose raw file started before the week start)
for entry in "${WEEKS[@]}"; do
    week_dir=${entry%|*}
    week_start=${entry#*|}
    [ -d "$week_dir" ] || continue
    for store in "$week_dir"/*.zarr; do
        [ -d "$store" ] || continue
        if [[ "$(basename "$store")" =~ D([0-9]{8})-T[0-9]{6} ]] && [[ "${BASH_REMATCH[1]}" < "$week_start" ]]; then
            if [ "$DRY_RUN" = "1" ]; then
                echo "DRY_RUN: would remove buffer copy $store"
            else
                rm -rf "$store"
            fi
        fi
    done
done

if (( FAILED != 0 )); then
    exit 1
fi

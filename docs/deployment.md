# Deploying the Cabled EK80 Processing

This guide is for the system administrators who will host the nightly processing of the cabled EK80 bioacoustic sonars
(CE02SHBP and CE04OSPS). It assumes as little as possible about the host: the processing runs in a container, and the
scheduling, paths, image tag and service account are all set in a few small configuration files. What the jobs do,
and how to check their output, is described in [nrt.md](nrt.md).

The examples use podman and systemd, which is how the processing was developed and tested. Any container runtime and
scheduler that can meet the [requirements](#requirements) will do.

## Requirements

| Requirement | Details |
|:------------|:--------|
| Raw data | The cabled raw data tree (currently `/rsn_cabled/rsn_data/DVT_Data`), readable by the service account. Mounted read-only. |
| Processed output | A writable directory for processed output (currently `/data/zplsc`). See [Storage](#storage) for sizing. |
| Service account | One account to run all jobs, with read access to the raw tree and write access to the output, lock and log directories. |
| Container runtime | podman (tested rootless with podman 5.8) or docker. |
| Memory | See [Memory](#memory). |
| Network at build time | Access to `conda.anaconda.org` and `docker.io` to build the image. Not needed at run time. |
| Clock | UTC-aware scheduling; the nightly jobs run at 02:00 UTC and process the previous UTC day. |

## Building the image

Build from the repository root:

```shell
podman build -t ooi-zpls-echograms:2026.10 .
```

Use a dated tag rather than `latest`, so the running version is always identifiable and an older image can be put back
by changing one line of configuration.

The `Dockerfile` pins the base image by digest and creates the processing environment from `environment.lock.txt`, an
exact list of every package, exported from the image the backlog and nightly processing were validated with. The build
does not resolve versions, so rebuilding later gives the same environment, as long as conda-forge still serves those
package files. Do not build without the lock file or regenerate it; changing package versions changes the processed
data and needs revalidation (see [Upgrading](#upgrading)).

To check that a new build matches the validated environment:

```shell
diff <(podman run --rm ooi-zpls-echograms:2026.10 conda list -p /opt/conda/envs/echogram --explicit --md5) \
     environment.lock.txt && echo "environment matches the lock"
```

The first lines of the lock file are comments and will show up in the diff; every package line should match.

For a build that does not depend on package servers at all, export a validated image and load it on the host:

```shell
podman save -o ooi-zpls-echograms_2026.10.tar ooi-zpls-echograms:2026.10   # on the build host
podman load -i ooi-zpls-echograms_2026.10.tar                               # on the processing host
```

## Configuration

Templates are in [deploy/systemd](../deploy/systemd). Settings live in environment files, one shared and one per site:

| File | Variable | Meaning |
|:-----|:---------|:--------|
| `common.env` | `IMAGE` | Container image and tag |
| | `RAW_MOUNT` | Host path of the raw data tree; mounted read-only at `/node_data` in the container |
| | `PROC_MOUNT` | Host path of the processed output; mounted at the same path in the container |
| | `LOCK_FILE` | Lock shared by every job (see [Scheduling](#scheduling)) |
| | `LOG_DIR` | Host directory for the weekly backlog's per-week logs |
| | `N_WEEKS` | Complete weeks the weekly backlog reprocesses (default 1, the previous week) |
| `CE02SHBP.env`, `CE04OSPS.env` | `DATA_ROOT` | Site raw data root, as seen inside the container |
| | `PROC_ROOT` | Site processed output root, as seen inside the container |

The per-site files only need to change if the layout of the raw tree or the output tree changes. The raw data paths
are expected to stay the same on the new host.

## Scheduling

There are four jobs, each a templated unit instantiated once per site:

| Unit | When | What |
|:-----|:-----|:-----|
| `zplsc-nrt@CE02SHBP`, `zplsc-nrt@CE04OSPS` | Daily, 02:00 UTC | Process the previous UTC day and update that week's products |
| `zplsc-backlog@CE02SHBP`, `zplsc-backlog@CE04OSPS` | Wednesday, 10:00 UTC | Reprocess the previous complete week to repair short days |

All four take the same lock (`flock -w 43200 ${LOCK_FILE}`), so only one job runs at a time; the others wait up to
12 hours. This is required, not a tuning choice:

- Running jobs one at a time keeps peak memory at that of the larger site rather than the sum of all jobs.
- The weekly backlog deletes and rebuilds files in week folders that a nightly job may be reading.

`Persistent=true` in the timers runs a job that was missed while the host was down at the next boot.

### Installing the templates as system units

1. Replace `SERVICE_ACCOUNT` in both `.service` files.
2. Copy the `.service` and `.timer` files to `/etc/systemd/system/`.
3. Copy `common.env.example` to `/etc/zplsc/common.env`, and the two site files to `/etc/zplsc/`. Edit as needed.
4. Create the lock and log directories, owned by the service account (by default `/var/lib/zplsc` and
   `/var/log/zplsc`).
5. Enable the timers:

```shell
systemctl daemon-reload
systemctl enable --now zplsc-nrt@CE02SHBP.timer zplsc-nrt@CE04OSPS.timer
systemctl enable --now zplsc-backlog@CE02SHBP.timer zplsc-backlog@CE04OSPS.timer
```

The instance name must match the site env file name exactly (`CE02SHBP`, `CE04OSPS`), because it is also passed to the
processing as the site code.

Rootless podman started from a system unit with `User=` needs the service account's runtime environment: lingering
enabled (`loginctl enable-linger SERVICE_ACCOUNT`), subordinate UID/GID ranges in `/etc/subuid` and `/etc/subgid`,
and usually `Environment=XDG_RUNTIME_DIR=/run/user/<uid>` in the unit. Running the same files as systemd user units of
the service account avoids most of this, and is how they were tested; see the comments at the top of
`zplsc-nrt@.service`. Rootful podman also works, but the output files will then be owned by root unless the container
is run with `--user`.

### Without systemd

Any scheduler will do if it meets these conditions:

- Each site's nightly job runs once a day, after 02:00 UTC.
- Every job, nightly and weekly, takes the same exclusive lock and waits for it rather than skipping.
- A job is allowed to run for several hours, including time spent waiting for the lock.
- Standard output and error are kept.

The command each job runs is the `ExecStart` line of the matching unit file.

## Logs

The nightly job writes to standard output, which systemd sends to the journal:

```shell
journalctl -u zplsc-nrt@CE04OSPS.service --since yesterday
systemctl list-timers 'zplsc-*'
```

The weekly backlog also writes one log per reprocessed week to `${LOG_DIR}/<SITE>/`. [nrt.md](nrt.md) lists the
messages to look for. A successful nightly run ends with a line of the form
`CE04OSPS: regenerated weekly average and echogram for 20261011-20261018 from 4 daily file(s).`

## Memory

Peak memory is set by file conversion. Measured on single-site test weeks, sampled every 15 s, so true peaks may be
somewhat higher:

| Site | Container peak | Host peak |
|:-----|:---------------|:----------|
| CE04OSPS | ~76 GiB | ~84 GiB |
| CE02SHBP | ~37 GiB | ~46 GiB |

With the jobs serialized by the lock, size the host for the larger site with a safety margin: doubling the highest
host peak gives about 170 GiB. If jobs are ever allowed to run in parallel, size for the sum of the jobs that can
overlap instead.

## Storage

Each nightly run adds one full-resolution file per site per day, about 5 GB for CE02SHBP and 11 GB for CE04OSPS on the
test weeks, roughly 16 GB a day or 6 TB a year for both sites. The converted `.zarr` stores, one per raw file, come on
top of that, as do the weekly averaged files and echograms, which are small. Sizes depend on the instrument
configuration RCA uses, so treat these as estimates and monitor actual use.

## Upgrading

To deploy new code or a new environment:

1. Build the new image under a new tag. Leave the running image in place.
2. Rerun a reference week with the new image into a scratch output directory and compare it with the current output
   using `xr.testing.assert_allclose`; `ncompare` checks structure only, not values. The reference week used so far is
   CE02SHBP `20231022-20231029`.
3. Change `IMAGE` in `common.env` to the new tag. The next scheduled run uses it.

Rolling back is the same change in reverse.

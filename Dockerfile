# Production image for ooi-zpls-echograms. The "echogram" environment is created from an explicit lock file exported
# from the validated image (2026-10-16), so a rebuild reproduces it exactly. Regenerate environment.lock.txt only
# deliberately, and rerun the regression checks when you do (see docs/deployment.md).
FROM docker.io/condaforge/miniforge3@sha256:8edc74dee5b29511a9c1a8941c77efbf438b47edffb6320ab8675dc06bd618c2
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1

# create the environment from the explicit lock (no solver, no version drift)
COPY environment.lock.txt /tmp/environment.lock.txt
RUN conda create -y -p /opt/conda/envs/echogram --file /tmp/environment.lock.txt \
    && conda clean -afy \
    && rm /tmp/environment.lock.txt
ENV PATH=/opt/conda/envs/echogram/bin:$PATH

# default mount points (raw data read-only, processed output read-write)
RUN mkdir -p /node_data /data/zplsc

# install the package itself; --no-deps so pip cannot pull anything outside the lock
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir --no-deps .

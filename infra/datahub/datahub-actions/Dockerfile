FROM acryldata/datahub-actions:releases-v1.1.0

# Fix: Install setuptools to resolve 'No module named pkg_resources' error
# The base image uses a venv at /home/datahub/.venv without pip
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip python3-setuptools && \
    rm -rf /var/lib/apt/lists/* && \
    /home/datahub/.venv/bin/python3 -m ensurepip --upgrade 2>/dev/null || true && \
    /home/datahub/.venv/bin/python3 -m pip install --no-cache-dir setuptools wheel
USER datahub
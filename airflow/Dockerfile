FROM apache/airflow:2.10.5-python3.11
LABEL org.opencontainers.image.source=https://github.com/maastrichtlawtech/case-law-explorer

USER root

# Install build dependencies in a single RUN command to reduce layers
RUN apt-get update --quiet && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set timezone
ENV TZ=Europe/Amsterdam
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam /etc/localtime

USER airflow

# Create data directories
RUN mkdir -p /opt/airflow/data/raw /opt/airflow/data/processed

# Install Python dependencies - pip is already recent in the base image
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --quiet -r requirements.txt \
    && rm requirements.txt

# Remove conflicting argparse package
RUN pip uninstall -y argparse

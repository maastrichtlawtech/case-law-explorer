# Docker file to be run from the ROOT FOLDER because of access rights
# https://stackoverflow.com/questions/24537340/docker-adding-a-file-from-a-parent-directory

FROM ubuntu:20.04

WORKDIR /src
# VOLUME /src/data

# Copy the extraction scripts into the Docker image
COPY data_extraction/caselaw/rechtspraak/* .
COPY data_extraction/caselaw/legal_intelligence/* .

# Copy py requirments file
COPY data_extraction/caselaw/requirements.txt .

# Copy definitions file
COPY definitions.py .

# Copy extraction script
COPY data_extraction/caselaw/extract.sh .

# Install pip3 and clean up apt-get
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install py requirements
RUN pip3 install -r requirements.txt

CMD sh extract.sh
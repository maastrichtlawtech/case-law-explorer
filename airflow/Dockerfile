FROM apache/airflow:2.3.0
USER root
LABEL org.opencontainers.image.source=https://github.com/maastrichtlawtech/case-law-explorer
RUN apt-get update && apt-get autoremove -yqq --purge && apt-get clean
USER airflow 
RUN mkdir -p /opt/airflow/data/rechtspraak
RUN mkdir -p /opt/airflow/data/cellar
RUN mkdir -p /opt/airflow/data/cellar/archive
RUN mkdir -p /opt/airflow/data/echr
COPY ./requirements.txt ./requirements.txt
RUN python3 -m pip install --upgrade pip
RUN pip3 install -r ./requirements.txt
RUN pip3 uninstall -y argparse
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam/etc/localtime
ENV TZ=Europe/Warsaw

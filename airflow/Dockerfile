FROM apache/airflow:2.3.0
USER root
RUN apt-get update && apt-get autoremove -yqq --purge && apt-get clean
USER airflow 
RUN mkdir -p /opt/airflow/data/rechtspraak
RUN mkdir -p /opt/airflow/data/cellar
RUN mkdir -p /opt/airflow/data/cellar/archive
RUN mkdir -p /opt/airflow/data/echr
COPY requirements.txt ./requirements.txt 
RUN python3 -m pip install --upgrade pip
RUN pip3 install -r ./requirements.txt
RUN pip3 uninstall -y argparse

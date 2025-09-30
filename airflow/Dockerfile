<<<<<<< HEAD
FROM apache/airflow:2.3.0-python3.8
=======
FROM apache/airflow:2.10.5-python3.11
USER root
>>>>>>> origin/airflow
LABEL org.opencontainers.image.source=https://github.com/maastrichtlawtech/case-law-explorer
RUN apt-get update && apt-get autoremove -yqq --purge && apt-get clean
RUN apt-get install -y gosu
RUN apt-get install -y serdi
USER airflow 
RUN mkdir -p /opt/airflow/data/raw
RUN mkdir -p /opt/airflow/data/processed
COPY ./requirements.txt ./requirements.txt
RUN python3 -m pip install --upgrade pip
RUN pip3 install -r ./requirements.txt
RUN pip3 install apache-airflow==2.9.0
RUN pip3 uninstall -y argparse
RUN ln -sf /usr/share/zoneinfo/Europe/Amsterdam/etc/localtime
CMD 'airflow db init'
ENV TZ=Europe/Amsterdam

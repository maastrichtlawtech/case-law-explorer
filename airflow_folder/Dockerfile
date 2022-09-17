FROM apache/airflow:2.3.4-python3.9
COPY ../requirements.txt ./requirements.txt
#ADD data_extraction data_extraction
#ADD definitions definitions
RUN mkdir -p /opt/airflow_folder/output/rechtspraak
RUN mkdir -p /opt/airflow_folder/output/cellar
RUN mkdir -p /opt/airflow_folder/output/echr
RUN pip install --user --upgrade pip
RUN pip install --no-cache-dir --user -r ./requirements.txt

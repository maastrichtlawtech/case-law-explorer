FROM apache/airflow:2.3.3
COPY requirements.txt /requirements.txt
ADD data_extraction data_extraction
ADD definitions definitions
RUN pip install --user --upgrade pip
RUN pip install --no-cache-dir --user -r /requirements.txt

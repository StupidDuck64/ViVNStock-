FROM apache/airflow:3.0.6-python3.12

# Copy và cài đặt requirements cho Airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless curl tar && \
    rm -rf /var/lib/apt/lists/*

COPY ./dags/dag_sync_manager.py /opt/airflow/dags
USER airflow

# Thiết lập biến môi trường cho Virtual Env (dbt)
ENV VIRTUAL_ENV=/opt/airflow/dbt_venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# replace dbt-postgres with another supported adapter if you're using a different warehouse type
RUN source dbt_venv/bin/activate && \
    pip install --no-cache-dir dbt-spark[PyHive] && \
    deactivate

RUN pip install 'acryl-datahub-airflow-plugin>=1.1.0.4'

RUN pip install 'acryl-datahub-airflow-plugin>=1.1.0.4'
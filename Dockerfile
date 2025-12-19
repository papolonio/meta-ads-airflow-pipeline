FROM apache/airflow:2.10.5
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         vim \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
USER airflow
COPY requirements.txt /
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt

# 2.8.3
# Instalar dependências
USER root
RUN apt-get update \
    && apt-get install -y wget unzip \
    && apt-get clean

FROM apache/airflow:2.10.0-python3.10
ENV AIRFLOW_HOME=/opt/airflow

WORKDIR $AIRFLOW_HOME

USER root
RUN apt-get update -qq && apt-get install vim -qqq && apt install wget -qq

# 安裝 OpenJDK 11
ENV JAVA_HOME=/home/jdk-11.0.2
ENV PATH="${JAVA_HOME}/bin/:${PATH}"

RUN DOWNLOAD_URL="https://download.java.net/java/GA/jdk11/9/GPL/openjdk-11.0.2_linux-x64_bin.tar.gz" \
    && TMP_DIR="$(mktemp -d)" \
    && curl -fL "${DOWNLOAD_URL}" --output "${TMP_DIR}/openjdk-11.0.2_linux-x64_bin.tar.gz" \
    && mkdir -p "${JAVA_HOME}" \
    && tar xzf "${TMP_DIR}/openjdk-11.0.2_linux-x64_bin.tar.gz" -C "${JAVA_HOME}" --strip-components=1 \
    && rm -rf "${TMP_DIR}" \
    && java --version


RUN mkdir -p /opt/spark/jars && chmod -R 777 /opt/spark/jars

RUN wget https://github.com/GoogleCloudDataproc/spark-bigquery-connector/releases/download/0.34.1/spark-3.4-bigquery-0.34.1.jar -O /opt/spark/jars/spark-bigquery-latest.jar

COPY requirements.txt .
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt


USER $AIRFLOW_UID

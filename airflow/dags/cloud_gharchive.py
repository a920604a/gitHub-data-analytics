from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryCreateEmptyTableOperator

from airflow.decorators import task

from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable

from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, to_date

import os
import itertools
import pandas as pd
from io import StringIO
import logging

# Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# GCS/BQ 設定
GCS_BUCKET = Variable.get("GCS_BUCKET")
GCS_PATH =  Variable.get("GCS_PATH") 
GCS_PROCESS_PATH = Variable.get("GCS_PROCESS_PATH")
BQ_PROJECT = Variable.get("BQ_PROJECT")
BQ_DATASET = Variable.get("BQ_DATASET")
BQ_DATASET_AREA = Variable.get("BQ_DATASET_AREA")
BQ_TABLE = Variable.get("BQ_TABLE") 


default_args = {
    "owner": "airflow",
    "start_date": datetime(2025, 3, 24),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

path_to_local_home = os.environ.get("AIRFLOW_HOME", "/opt/airflow")

with DAG(
    dag_id="cloud_gharchive_dag",
    default_args=default_args,
    # schedule_interval=None,
    schedule_interval='@hourly',  # 每小時運行一次
    catchup=False,
) as dag:

    now = datetime.utcnow() - timedelta(hours=2)    
    date_str = now.strftime('%Y-%m-%d')
    current_hour = now.hour
    dataset_file = f"{date_str}-{current_hour}.json.gz"
    dataset_url = f"https://data.gharchive.org/{dataset_file}"
    local_gz_path = f"{path_to_local_home}/data/{dataset_file}"    
    gcs_gz_path = f"{GCS_PATH}/{dataset_file}"

    os.makedirs(f"{path_to_local_home}/data", exist_ok=True)

    fetch_data_task = BashOperator(
        task_id="fetch_data",
        bash_command=f"wget {dataset_url} -O {local_gz_path} && gzip -d {local_gz_path}"
    )
    def ingest_and_save_data(dataset_name: str):
        path_to_json = f"{path_to_local_home}/data/{dataset_name}"
        path_to_parquet = f"{path_to_local_home}/data/{dataset_name}.parquet"

        try:
            dfs = []
            with open(path_to_json, 'r') as f:
                while True:
                    lines = list(itertools.islice(f, 1000))
                    if not lines:
                        break
                    dfs.append(pd.read_json(StringIO(''.join(lines)), lines=True))
            df = pd.concat(dfs)
            df["created_at"] = pd.to_datetime(df["created_at"]).dt.tz_localize(None).astype("datetime64[ms]")
            df.to_parquet(path_to_parquet, engine="pyarrow", compression="gzip")
            os.remove(path_to_json)
        except Exception as e:
            logger.error(f"處理資料錯誤: {e}")
            raise
        return path_to_parquet

    ingest_and_save_task = PythonOperator(
        task_id="ingest_and_save",
        python_callable=ingest_and_save_data,
        op_kwargs={"dataset_name": dataset_file.replace(".gz", "")},
        do_xcom_push=False
    )

    load_gcs_task = LocalFilesystemToGCSOperator(
        task_id="load_gcs",
        src=f"{path_to_local_home}/data/{dataset_file.replace('.gz', '')}.parquet",
        dst=gcs_gz_path.replace(".gz", ".parquet"),
        bucket=GCS_BUCKET,
        mime_type="application/octet-stream",
    )

    def clean_with_spark(local: str, **kwargs):
        spark = SparkSession.builder.master("local[*]").appName('spark-clean').getOrCreate()
        df = spark.read.option("header", "true").parquet(local)

        df_filtered = df.filter(col("type") == "WatchEvent") \
            .groupBy("repo.name") \
            .agg(count("*").alias("watch_count")) \
            .orderBy(col("watch_count").desc())

        output_dir = os.path.join(os.path.dirname(local), f"{GCS_PROCESS_PATH}/")
        os.makedirs(output_dir, exist_ok=True)
        df_filtered.write.parquet(output_dir, mode='overwrite')
        print(df_filtered.head(20))
        print([
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.endswith(".parquet")
            ])
        return [
            os.path.join(output_dir, f)
            for f in os.listdir(output_dir)
            if f.endswith(".parquet")
            ]

    spark_clean_task = PythonOperator(
        task_id='spark_clean',
        python_callable=clean_with_spark,
        op_kwargs={"local": f"{path_to_local_home}/data/{dataset_file.replace('.gz','')}.parquet"},
    )

    # 使用 Dynamic Task Mapping 上傳多個清理後檔案
    upload_cleaned_files = LocalFilesystemToGCSOperator.partial(
        task_id="upload_cleaned_files",
        dst=f"{GCS_PROCESS_PATH}/{dataset_file.replace('.gz', '.parquet').replace('.json', '')}",  # 使用原始檔案名稱
        bucket=GCS_BUCKET
    ).expand(
        src=spark_clean_task.output
    )
    
    remove_parquet_task = BashOperator(
        task_id = "remove_parquet",
        bash_command = f"rm -rf {path_to_local_home}/data/{dataset_file.replace('.gz', '')}.parquet"
    )
    remove_processd_data_task = BashOperator(
        task_id = "remove_processed_data",
        bash_command = f"rm -rf {path_to_local_home}/data/{GCS_PROCESS_PATH}"
        
    )
    
    # 臨時 staging table 名稱
    BQ_STAGING_TABLE = f"{BQ_TABLE}_staging"

    # 先將資料載入 staging table
    load_to_staging = GCSToBigQueryOperator(
        task_id='load_to_staging',
        bucket=GCS_BUCKET,
        source_objects=[f"{GCS_PROCESS_PATH}/{dataset_file.replace('.gz', '.parquet').replace('.json', '')}"],
        destination_project_dataset_table=f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_STAGING_TABLE}",
        source_format="PARQUET",
        write_disposition="WRITE_TRUNCATE",
        create_disposition="CREATE_IF_NEEDED",
    )
    
    check_or_create_table = BigQueryCreateEmptyTableOperator(
        task_id="check_or_create_main_table",
        dataset_id=BQ_DATASET,
        table_id=BQ_TABLE,
        project_id=BQ_PROJECT,
        schema_fields=[
            {"name": "name", "type": "STRING", "mode": "REQUIRED"},
            {"name": "watch_count", "type": "INTEGER", "mode": "REQUIRED"},
        ],
        exists_ok=True,  # 重點在這個參數，表格存在也不會報錯
    )
    
    
    # 然後使用 MERGE 語法去更新正式表格
    merge_to_main = BigQueryInsertJobOperator(
        task_id="merge_to_main",
        configuration={
            "query": {
                "query": f"""
                    MERGE `{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}` T
                    USING `{BQ_PROJECT}.{BQ_DATASET}.{BQ_STAGING_TABLE}` S
                    ON T.name = S.name
                    WHEN MATCHED THEN
                    UPDATE SET watch_count = S.watch_count
                    WHEN NOT MATCHED THEN
                    INSERT (name, watch_count) VALUES (S.name, S.watch_count)
                """,
                "useLegacySql": False,
            }
        },
    )

 
    
    # 任務鏈
    fetch_data_task  >> ingest_and_save_task >> load_gcs_task
    load_gcs_task >> spark_clean_task >> upload_cleaned_files >> remove_parquet_task>> load_to_staging >> check_or_create_table  >> merge_to_main  >> remove_processd_data_task

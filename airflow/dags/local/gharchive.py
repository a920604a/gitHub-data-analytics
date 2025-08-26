from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


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


default_args = {
    "owner": "airflow",
    "start_date": datetime(2025, 3, 24),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


path_to_local_home = os.environ.get("AIRFLOW_HOME", "/opt/airflow")

with DAG(
    dag_id="gharchive_dag",
    default_args=default_args,
    # schedule_interval=None,
    schedule_interval="@hourly",  # 每小時運行一次
    catchup=False,
) as dag:

    now = datetime.utcnow() - timedelta(hours=2)
    date_str = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    dataset_file = f"{date_str}-{current_hour}.json.gz"
    dataset_url = f"https://data.gharchive.org/{dataset_file}"
    local_gz_path = f"{path_to_local_home}/data/{dataset_file}"

    os.makedirs(f"{path_to_local_home}/data", exist_ok=True)

    fetch_data_task = BashOperator(
        task_id="fetch_data",
        bash_command=f"wget {dataset_url} -O {local_gz_path} && gzip -d {local_gz_path}",
    )

    def ingest_and_save_data(dataset_name: str):
        path_to_json = f"{path_to_local_home}/data/{dataset_name}"
        path_to_parquet = f"{path_to_local_home}/data/{dataset_name}.parquet"

        try:
            dfs = []
            with open(path_to_json, "r") as f:
                while True:
                    lines = list(itertools.islice(f, 1000))
                    if not lines:
                        break
                    dfs.append(pd.read_json(StringIO("".join(lines)), lines=True))
            df = pd.concat(dfs)
            df["created_at"] = (
                pd.to_datetime(df["created_at"])
                .dt.tz_localize(None)
                .astype("datetime64[ms]")
            )
            df.to_parquet(path_to_parquet, engine="pyarrow", compression="gzip")
            os.remove(path_to_json)
        except Exception as e:
            logger.error(f"處理資料錯誤: {e}")
            raise
        return path_to_parquet

    # 任務鏈

    # fetch_data_task >> ingest。_and_save_task >> load_gcs_task
    # load_gcs_task >> spark_clean_task >> upload_cleaned_files >> remove_parquet_task>> load_to_staging >> check_or_create_table  >> merge_to_main  >> remove_processd_data_task

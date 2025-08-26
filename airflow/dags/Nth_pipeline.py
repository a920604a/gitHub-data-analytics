from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.decorators import task
from google.cloud import storage, bigquery
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, unix_timestamp
from airflow.models import Variable
import os
import logging

# Logger 設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# GCS 和 BigQuery 設定
GCS_BUCKET = Variable.get("GCS_BUCKET")
GCS_PATH =  Variable.get("GCS_PATH")
GCS_PROCESS_PATH = Variable.get("GCS_PROCESS_PATH")
BQ_PROJECT = Variable.get("BQ_PROJECT")
BQ_DATASET = Variable.get("BQ_DATASET")
BQ_TABLE_MOST_ACTIVE = "most_active_developers"

# Default arguments 設定
default_args = {
    "owner": "airflow",
    "start_date": datetime(2025, 3, 24),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

path_to_local_home = os.environ.get("AIRFLOW_HOME", "/opt/airflow")

# DAG 定義
with DAG(
    dag_id="process_most_active_developers",
    default_args=default_args,
    schedule_interval='@hourly',  # 每小時執行
    catchup=False,
) as dag:
    
    # 確保資料夾存在
    os.makedirs(f"{path_to_local_home}/activate_data", exist_ok=True)

    # 下載 GCS 上的 Parquet 檔案到本地
    def download_parquet_from_gcs(bucket_name: str, gcs_path: str, local_base_path: str, **kwargs):
        # 建立本地資料夾
        local_dir = os.path.join(local_base_path, "activate_data")
        os.makedirs(local_dir, exist_ok=True)

        # 使用 GCP SDK 下載檔案
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=gcs_path)  # 列出所有符合條件的檔案

        # 下載檔案並保存至本地
        downloaded_files  = []
        for blob in blobs:
            local_file = os.path.join(local_dir, blob.name.split('/')[-1])  # 檔案名
            try:
                logger.info(f"下載檔案: {blob.name} 到 {local_file}")
                blob.download_to_filename(local_file)
                logger.info(f"檔案下載完成: {local_file}")
                downloaded_files.append(local_file)
            except Exception as e:
                logger.error(f"檔案下載失敗: {blob.name}, 錯誤: {e}")
        
        # 使用 XCom 推送下載的檔案路徑列表
        ti = kwargs['ti']
        ti.xcom_push(key='downloaded_files', value=downloaded_files )
        return downloaded_files


    download_gcs_parquet_task = PythonOperator(
        task_id="download_gcs_parquet",
        python_callable=download_parquet_from_gcs,
        op_kwargs={
            "bucket_name": GCS_BUCKET,
            "gcs_path": GCS_PATH,
            "local_base_path": path_to_local_home
        },
        provide_context=True,  # 確保提供上下文
        do_xcom_push=True,     # 啟用 XCom 推送
    )
    
    # 使用 PySpark 進行資料清理和轉換
    def spark_cleaning_and_transformation(output_dir: str, **kwargs):
        
        input_files = kwargs['ti'].xcom_pull(task_ids='download_gcs_parquet', key='downloaded_files')
        
        for input_file in input_files:
            print(f"input_file {input_file}")

        spark = SparkSession.builder \
            .appName("GitHub Activity Data Processing") \
            .getOrCreate()

        # 計算一個月前的日期
        one_month_ago = datetime.now() - timedelta(days=30)
        output_files = []
        # 遍歷所有下載的 parquet 檔案
        for input_file in input_files:
            try:
                logger.info(f"處理檔案: {input_file}")
                df = spark.read.parquet(input_file)
                print(f"輸入範本 {df.show(5)}")

                # 清理和轉換資料
                df_cleaned = df.select(
                    col("id").alias("event_id"),
                    col("type").alias("event_type"),
                    col("actor.id").alias("actor_id"),
                    col("actor.login").alias("actor_login"),
                    col("repo.id").alias("repo_id"),
                    col("repo.name").alias("repo_name"),
                    col("created_at")
                )

                # 轉換時間戳
                df_cleaned = df_cleaned.withColumn("created_at", unix_timestamp(col("created_at")).cast("timestamp"))

                # # 過濾最近一個月的資料
                # df_filtered = df_cleaned.filter(col("created_at") >= one_month_ago)

                # # 計算每個 Repo 的事件數量
                # df_repo_activity = df_filtered.groupBy("repo_id", "repo_name") \
                #     .agg(count("event_id").alias("event_count")) \
                #     .orderBy(col("event_count").desc())

                # 儲存處理後的資料為 Parquet 檔案
                output_file = os.path.join(output_dir, f"repo_activity_{input_file.split('/')[-1].replace('.json.parquet', '')}")
                output_files.append(output_file)
                df_cleaned.write.parquet(output_file, mode="overwrite")
                print(f" 輸出範本 {df_cleaned.show(5)}")
                logger.info(f"檔案處理完成並儲存至: {output_dir}")
            except Exception as e:
                logger.error(f"處理檔案失敗: {input_file}, 錯誤: {e}")
        
        spark.stop()
        return output_files
        # 推送結果至 XCom，將 output_path_list 推送至後續任務
    
   
    spark_processing_task = PythonOperator(
        task_id="spark_cleaning_and_transformation",
        python_callable=spark_cleaning_and_transformation,
        op_kwargs={
            "output_dir": f"{path_to_local_home}/activate_data/processed_data"
        },
        provide_context=True,  # 確保提供上下文
    )
    
    def upload_to_gcs_and_bigquery(ti, **kwargs):
        downloaded_files = ti.xcom_pull(task_ids='download_gcs_parquet', key='downloaded_files')
        processed_folders = ti.xcom_pull(task_ids='spark_cleaning_and_transformation', key='return_value')

        client_gcs = storage.Client()
        bucket = client_gcs.bucket(GCS_BUCKET)

        client_bq = bigquery.Client()

        for src_folder in processed_folders:
            gcs_folder = f"{GCS_PROCESS_PATH}/repo_activity/{os.path.basename(src_folder)}"

            for file_name in os.listdir(src_folder):
                if not file_name.endswith(".parquet"):
                    continue

                local_path = os.path.join(src_folder, file_name)
                blob_path = f"{gcs_folder}/{file_name}"

                if not os.path.exists(local_path):
                    logger.error(f"檔案不存在: {local_path}")
                    continue
                logger.info(f"開始上傳: {local_path} → gs://{GCS_BUCKET}/{blob_path}")

                blob = bucket.blob(blob_path)
                blob.upload_from_filename(local_path)
                logger.info(f"已上傳到 GCS")

                table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE_MOST_ACTIVE}"
                job_config = bigquery.LoadJobConfig(
                    source_format=bigquery.SourceFormat.PARQUET,
                    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                    autodetect=True,
                )
                uri = f"gs://{GCS_BUCKET}/{blob_path}"
                load_job = client_bq.load_table_from_uri(uri, table_id, job_config=job_config)
                load_job.result()  # 等待完成
                logger.info(f"已上傳到 BigQuery → {table_id}")
        
        
    upload_to_gcs_and_bigquery_task = PythonOperator(
        task_id="upload_to_gcs_and_bigquery",
        python_callable=upload_to_gcs_and_bigquery,
        provide_context=True,  # 確保提供上下文
    )
        
    remove_all_data_task =  BashOperator(
        task_id = "remove_all_data",
        bash_command = f"rm -rf {path_to_local_home}/activate_data"
    )
    # 任務順序
    download_gcs_parquet_task >> spark_processing_task  >> upload_to_gcs_and_bigquery_task >> remove_all_data_task


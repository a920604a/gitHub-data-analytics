# GitHub 數據分析管線

該專案透過分析 GitHub Watch 事件提供對開源開發趨勢的洞察。它使用 GCP、Airflow 和 BigQuery 構建，允許利益相關者即時探索開發人員參與度和儲存庫受歡迎程度。

## 1. 問題描述

本專案使用 GitHub Archive 資料集分析 GitHub 倉庫的活動情況。目的是擷取、處理與分析「關注（Watch）」事件，以洞察倉庫趨勢、使用者參與度與時間序列的活動模式。

主要分析項目包括：
- 找出最受歡迎的倉庫
- 分析使用者參與行為
- 理解 GitHub 活動的時間趨勢

此管線能提供開源專案人氣與開發者行為的可行性洞察。

## 2. 系統架構
```mermaid
flowchart LR
    %% 定義樣式
    classDef source fill:#f9f,stroke:#333,stroke-width:1px,color:#000;
    classDef pipeline fill:#ffeb99,stroke:#333,stroke-width:1px,color:#000;
    classDef gcp fill:#99ddff,stroke:#333,stroke-width:1px,color:#000;
    classDef dashboard fill:#b3ffb3,stroke:#333,stroke-width:1px,color:#000;

    %% GitHub Data Source
    subgraph GitHub_Data_Source[GitHub Data Source]
    direction TB
        A[GitHub Archive JSON]
    end
    class A source;

    %% Airflow Pipeline
    subgraph Airflow_Pipeline[Airflow Pipeline]
    direction BT
        B[raw data] 
        C[Parquet] 
        E[資料清洗轉換]
    end
    class B,C,D,E pipeline;

    %% GCP Infrastructure
    subgraph GCP_Infrastructure[GCP Infrastructure]
    direction LR
        F[GCS Bucket] 
        G[BigQuery Dataset]
    end
    class F,G gcp;

    %% Dashboard
    subgraph Dashboard[Streamlit Dashboard]
        H[互動式儀表板]
    end
    class H dashboard;

    %% 資料流向
    A -->|下載 JSON| B -->|轉換格式| C -->|上傳 Parquet| F
    C -->|資料清洗轉換| E --> |上傳| G
    G -->|查詢分析| H

```

架構採模組化設計，確保系統具備可擴展性與可維護性。整合雲端服務、工作流程調度與資料處理工具。

## 3. 雲端基礎建設

本專案部署於 Google Cloud Platform（GCP），並透過 Terraform 進行基礎建設即程式碼（IaC）的管理。

### 雲端元件：
- **Google Cloud Storage (GCS)**：作為數據湖，用來儲存處理後的 GitHub Archive 資料。
- **Google BigQuery**：作為數據倉儲，支援分析查詢。

### 基礎建設部署：
- 使用 Terraform 配置與管理 GCP 資源。
- 主要資源包括：
  - 儲存處理資料的 GCS bucket
  - 用於分析的 BigQuery dataset

部署指令如下：
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

## 4. 資料擷取 - 批次處理與工作流程調度
本專案使用 Apache Airflow 進行資料管線調度與自動化批次處理，整體設計採用「分層式 ETL」思維：
前段以 Pandas 進行靈活的資料解析與 schema 清洗，後段則交由 PySpark 處理大量轉換與聚合，最終輸出至 BigQuery。

**🧭 DAG 處理流程**

1. 下載資料
   - 使用 `BashOperator` 下載當前小時的 GitHub Archive JSON 檔。
   - 檔案儲存至暫存目錄供後續轉換使用。

2. 初步轉換（Pandas）
   - 以 `PythonOperator` 載入 JSON，利用 Pandas 進行資料結構化與欄位前處理（如展開 nested JSON、timestamp 格式轉換）。
   - 此階段著重於靈活清洗與 schema 驗證。
   - 輸出為中間層 Parquet 檔案。

3. 批次轉換（PySpark）
   - 使用 PySpark 讀取 Parquet，進行大規模的轉換、過濾與彙整（例如依事件類型聚合、取樣或計算統計特徵）。
   - 藉由 Spark 的分散式架構處理大量 GitHub 活動事件（特別是跨日或週級資料）。

4. 上傳與資料倉儲
   - 透過 `GCS Operators` 將處理後的資料上傳至 Google Cloud Storage。
   - 使用 `BigQueryInsertJobOperator` 建立對應的外部表格，提供下游分析查詢使用。

| 步驟                               | 描述                                                                                           | 使用技術                                    |
| -------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------- |
| **1️⃣ 資料下載**                     | 每小時從 `https://data.gharchive.org/` 下載當前小時的 JSON 檔案（gzip 壓縮），解壓後存入 Airflow 容器的 `/data` 目錄。    | `BashOperator`                          |
| **2️⃣ JSON 轉換為 Parquet（Pandas）** | 逐批（每 1000 行）載入 JSON，利用 **Pandas** 清洗欄位（特別是 `created_at` 轉換為 datetime64[ms]），並輸出為 Parquet 檔。  | `PythonOperator` + `pandas`             |
| **3️⃣ 上傳原始 Parquet 至 GCS**       | 將 Pandas 輸出的 Parquet 上傳至指定的 Google Cloud Storage Bucket。                                     | `LocalFilesystemToGCSOperator`          |
| **4️⃣ 大規模聚合清洗（PySpark）**         | 啟動 **SparkSession**，讀取 Parquet，篩選出 `WatchEvent` 類型事件，依照 `repo.name` 分組計算 watch_count，並依數量排序。 | `PythonOperator` + `PySpark`            |
| **5️⃣ 上傳清洗後結果至 GCS**             | 使用 Airflow 的 Dynamic Task Mapping，將多個 Spark 輸出的 Parquet 分批上傳至 GCS 的 Processed 目錄。            | `LocalFilesystemToGCSOperator.expand()` |
| **6️⃣ 匯入 BigQuery（Staging）**     | 從 GCS 匯入至臨時 staging table（使用 Parquet source）。                                                | `GCSToBigQueryOperator`                 |
| **7️⃣ 建立/檢查正式表格**                | 若正式表格不存在則自動建立（含 schema）。                                                                     | `BigQueryCreateEmptyTableOperator`      |
| **8️⃣ 合併更新正式表格**                 | 透過 BigQuery `MERGE` 語法整合同名專案的 watch_count。                                                   | `BigQueryInsertJobOperator`             |
| **9️⃣ 清理暫存檔案**                   | 刪除本地與中間層 Parquet 資料。                                                                         | `BashOperator`                          |


🚀 啟動工作流程指令：
```bash
cd airflow
make up
```
請確認 `env.json` 設定正確後再啟動 Airflow。

## 5. 數據倉儲

BigQuery 是主要的資料倉儲工具：
- 從 GCS 的 Parquet 檔建立外部表格。
- 優化分析 GitHub 資料的查詢效率。

## 6. 資料轉換

資料轉換流程包含：

1. **Python/Pandas**：用於初步 ETL 處理。
   - 過濾所需 GitHub 事件。
   - 轉換為 Parquet 格式以提升效能。

2. **SQL**：在 BigQuery 進行進一步資料轉換與分析。

## 7. 儀表板

本專案提供互動式儀表板進行資料視覺化。

主要儀表板內容包括：
- 倉庫人氣趨勢分析。
- 根據 Watch 數排序的熱門倉庫。
- 使用者參與度與活躍模式。

### Streamlit 儀表板：
本儀表板採用 Streamlit 架設，可於本地端瀏覽 `http://localhost:8501`。或成果[展示1](https://github.com/a920604a/data-engineering-zoomcamp-2025/blob/main/project/GitHub%20WatchEvent%20%E7%86%B1%E9%96%80%20Repo.pdf), [展示2](./ActivityDashboard.pdf)


使用 Docker 啟動 Streamlit：
```bash
cd Visual
docker-compose up
```

請確認 `docker-compose.yml` 設定正確以支援儀表板顯示。

## 8. 可重現性指南

### 前置需求：
- 已啟用計費功能的 Google Cloud 帳戶。
- 安裝 Docker 與 Docker Compose。
- 安裝 Terraform。
- 安裝 Python 3.9 以上版本。

### 安裝與部署步驟：

1. **Clone 專案倉庫**：
   ```bash
   git clone https://github.com/a920604a/data-engineering-zoomcamp-2025.git
   cd project
   ```

2. **設定 GCP 認證**：
   - 建立具備必要權限的 Service Account。
   - 下載 JSON 金鑰檔案。
   - 將其命名為 `service-account.json` 放在專案根目錄。

3. **部署雲端基礎建設**：
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

4. **啟動 Airflow**：
   ```bash
   cd airflow
   make up
   ```

5. **服務入口**：
   - Airflow UI: http://localhost:8080

6. **環境變數：**
Airflow 需一個 `env.json` 檔案存放敏感變數，請將此檔案放置於 `airflow` 資料夾中。

   範例 `env.json`：
   ```json
   {
   "GCP_PROJECT": "your-gcp-project-id",
   "GCS_BUCKET": "your-gcs-bucket-name",
   "BIGQUERY_DATASET": "your-bigquery-dataset-name"
   }
   ```
7. **觸發管線**：
   - 於 Airflow UI 中觸發 `cloud_gharchive_dag` DAG。

依照以上步驟即可完整重現本專案並開始 GitHub 數據分析。

## 使用技術

- **基礎建設**：Terraform, Google Cloud Platform
- **工作流程調度**：Apache Airflow
- **儲存**：Google Cloud Storage
- **資料倉儲**：Google BigQuery
- **資料處理**：Python, Pandas, PySpark
- **容器化**：Docker, Docker Compose
- **資料視覺化**：Streamlit

## Project Structure
```
  ├── airflow/ # Airflow DAGs and configs 
  ├── terraform/ # IaC scripts for GCP 
  ├── Visual/ # Dashboard code 
  └── README.md # Project overview
```

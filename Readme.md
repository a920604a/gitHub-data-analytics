# GitHub Data Analytics Pipeline

This project provides insights into open-source development trends by analyzing GitHub Watch events. Built using GCP, Airflow, and BigQuery, it allows stakeholders to explore developer engagement and repository popularity in real-time.

## 1. Problem Description

This project analyzes GitHub repository activity using the GitHub Archive dataset. The goal is to extract, process, and analyze watch events to uncover insights into repository trends, user engagement, and activity patterns over time.

Key analytics include:
- Identifying the most popular repositories
- Analyzing user engagement patterns
- Understanding temporal trends in GitHub activities

This pipeline provides actionable insights into open-source project popularity and developer behavior.

## 2. Architecture

![Architecture Diagram](architecture-diagram.svg)

The architecture follows a modular design, ensuring scalability and maintainability. It integrates cloud services, workflow orchestration, and data processing tools.

## 3. Cloud Infrastructure

The project is deployed on Google Cloud Platform (GCP) using Infrastructure as Code (IaC) with Terraform.

### Cloud Components:
- **Google Cloud Storage (GCS)**: Acts as a data lake for storing processed GitHub Archive data.
- **Google BigQuery**: Serves as the data warehouse for analytics queries.

### Infrastructure as Code:
- Terraform provisions and manages GCP resources.
- Key resources include:
  - GCS bucket for data lake storage
  - BigQuery dataset for data warehousing

To deploy the infrastructure:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

## 4. Data Ingestion - Batch Processing & Workflow Orchestration

Apache Airflow orchestrates the data pipeline with a DAG that performs the following steps:

1. Download hourly GitHub Archive data (JSON format).
2. Transform raw data into Parquet format.
3. Upload processed data to Google Cloud Storage.
4. Create external tables in BigQuery for analytics.

### Key Airflow DAG components:
- **BashOperator**: Downloads data.
- **PythonOperator**: Transforms data.
- **GCS Operators**: Handles cloud storage operations.
- **BigQuery Operators**: Manages data warehouse operations.


To run the workflow:
```bash
cd airflow
make up
```
Ensure the `env.json` file is properly configured before starting Airflow.

## 5. Data Warehouse

BigQuery is the primary data warehouse:
- External tables are created from GCS Parquet files.
- Optimized for analytical queries on GitHub data.

## 6. Transformations

Data transformations are performed using:

1. **Python/Pandas**: For initial ETL processing.
   - Filters relevant GitHub events.
   - Converts data to optimized Parquet format.

2. **SQL**: For advanced transformations and analytics in BigQuery.

## 7. Dashboard

The project includes an interactive dashboard for data visualization.

Key dashboard components:
- Repository popularity trends over time.
- Top trending repositories by watch events.
- User engagement metrics and patterns.

### Streamlit Dashboard:
The dashboard is built using Streamlit and can be accessed locally at `http://localhost:8501`. or [demo 1](https://github.com/a920604a/data-engineering-zoomcamp-2025/blob/main/project/GitHub%20WatchEvent%20%E7%86%B1%E9%96%80%20Repo.pdf), [demo 2](./ActivityDashboard.pdf)


To start the Streamlit server using Docker:
```bash

docker-compose up
```

Ensure the `docker-compose.yml` file is properly configured for Streamlit visualization.

## 8. Reproducibility

### Prerequisites:
- Google Cloud Platform account with billing enabled.
- Docker and Docker Compose.
- Terraform.
- Python 3.9+.

### Setup and Deployment:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/a920604a/data-engineering-zoomcamp-2025.git
   cd project
   ```

2. **Set up GCP credentials**:
   - Create a service account with appropriate permissions.
   - Download the JSON key file.
   - Place it in the project directory as `service-account.json`.

3. **Deploy cloud infrastructure**:
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

4. **Start Airflow**:
   ```bash
   cd airflow
   make up
   ```

5. **Access services**:
   - Airflow UI: http://localhost:8080
6. **Environment Variables:**
Airflow requires an `env.json` file to store sensitive variables. Place this file in the `airflow` directory.

   Example `env.json`:
   ```json
   {
   "GCP_PROJECT": "your-gcp-project-id",
   "GCS_BUCKET": "your-gcs-bucket-name",
   "BIGQUERY_DATASET": "your-bigquery-dataset-name"
   }
   ```
7. **Trigger the pipeline**:
   - From the Airflow UI, trigger the `cloud_gharchive_dag` DAG.

Follow these steps to fully reproduce the project and start analyzing GitHub data.

## Technologies Used

- **Infrastructure**: Terraform, Google Cloud Platform.
- **Workflow Orchestration**: Apache Airflow.
- **Storage**: Google Cloud Storage.
- **Data Warehouse**: Google BigQuery.
- **Data Processing**: Python, Pandas, PySpark.
- **Containerization**: Docker, Docker Compose.
- **Visualization**: Streamlit.


## Project Structure
```
  ├── airflow/ # Airflow DAGs and configs 
  ├── terraform/ # IaC scripts for GCP 
  ├── Visual/ # Dashboard code 
  └── README.md # Project overview
```

import os

from dotenv import load_dotenv

load_dotenv()


UPLOAD_DIR = "/data/uploaded_files"
# === 基本設定 ===


COLLECTION_NAME = "notes_collection"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@note-db:5432/note")


MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://note-minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "airflow")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "airflow123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "github-repo")

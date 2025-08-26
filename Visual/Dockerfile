# 使用官方 Python 3.9 基底映像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製要求的檔案
COPY requirements.txt /app/requirements.txt

# 安裝需求套件
RUN pip install --no-cache-dir -r requirements.txt

# 複製 Streamlit 應用程式代碼
COPY . /app

# 設定環境變數，告訴 Streamlit 在哪個端口運行
ENV STREAMLIT_SERVER_PORT=8501

# 啟動 Streamlit 應用
CMD ["streamlit", "run", "Home.py"]

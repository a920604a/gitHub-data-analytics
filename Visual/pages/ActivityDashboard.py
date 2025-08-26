import streamlit as st
from google.cloud import bigquery
import pandas as pd
import altair as alt
from datetime import date

# 初始化 BigQuery client（需設定 GOOGLE_APPLICATION_CREDENTIALS）
client = bigquery.Client()

# 設定資料表
BQ_PROJECT = "dz-final-project"
BQ_DATASET = "gharchive"
BQ_TABLE = "most_active_developers"
TABLE_REF = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

# 預設時間區間
today = date.today()
first_day = date(today.year, today.month, 1)

# Streamlit UI
st.title("📊 GitHub 活動分析儀表板")

start_date = st.date_input("開始日期", value=first_day)
end_date = st.date_input("結束日期", value=today)

# 資料查詢模板
@st.cache_data(show_spinner=False)
def query_bq(query: str) -> pd.DataFrame:
    return client.query(query).to_dataframe()

# 1. 活動類型分佈
st.header("📌 活動類型分佈")
query1 = f"""
SELECT event_type, COUNT(*) AS count
FROM `{TABLE_REF}`
WHERE DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'
GROUP BY event_type
ORDER BY count DESC
"""
df_event_type = query_bq(query1)

st.altair_chart(
    alt.Chart(df_event_type).mark_bar().encode(
        x=alt.X("event_type:N", sort='-y'),
        y="count:Q",
        tooltip=["event_type", "count"]
    ).properties(width=700, height=400),
    use_container_width=True
)

# 2. 最活躍使用者排行
st.header("👤 最活躍使用者 Top 10")
query2 = f"""
SELECT actor_login, COUNT(*) AS count
FROM `{TABLE_REF}`
WHERE DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'
GROUP BY actor_login
ORDER BY count DESC
LIMIT 10
"""
df_users = query_bq(query2)
st.dataframe(df_users)

# 3. 最活躍 Repo 排行
st.header("📦 最活躍 Repo Top 10")
query3 = f"""
SELECT repo_name, COUNT(*) AS count
FROM `{TABLE_REF}`
WHERE DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'
GROUP BY repo_name
ORDER BY count DESC
LIMIT 10
"""
df_repos = query_bq(query3)
st.dataframe(df_repos)

# 4. 每日活動趨勢
st.header("📅 每日活動趨勢")
query4 = f"""
SELECT DATE(created_at) AS event_date, COUNT(*) AS count
FROM `{TABLE_REF}`
WHERE DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'
GROUP BY event_date
ORDER BY event_date
"""
df_daily = query_bq(query4)

st.altair_chart(
    alt.Chart(df_daily).mark_line(point=True).encode(
        x="event_date:T",
        y="count:Q",
        tooltip=["event_date", "count"]
    ).properties(width=700, height=400),
    use_container_width=True
)

# 5. 篩選特定活動類型分析
st.header("🔎 特定活動類型每日趨勢")
event_types = df_event_type['event_type'].tolist()
selected_type = st.selectbox("選擇活動類型", event_types)

query5 = f"""
SELECT DATE(created_at) AS event_date, COUNT(*) AS count
FROM `{TABLE_REF}`
WHERE DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'
AND event_type = '{selected_type}'
GROUP BY event_date
ORDER BY event_date
"""
df_type_trend = query_bq(query5)

st.altair_chart(
    alt.Chart(df_type_trend).mark_area(opacity=0.5).encode(
        x="event_date:T",
        y="count:Q",
        tooltip=["event_date", "count"]
    ).properties(width=700, height=400),
    use_container_width=True
)

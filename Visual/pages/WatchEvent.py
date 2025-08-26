import streamlit as st
import pandas as pd
from google.cloud import bigquery
from datetime import datetime
import altair as alt
import plotly.express as px

# 初始化 BigQuery 客戶端
client = bigquery.Client()

# 設定資料庫資訊
BQ_PROJECT = "dz-final-project"
BQ_DATASET = "gharchive"
BQ_TABLE = "github_archive"
TABLE_REF = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

@st.cache_resource
def get_watch_events():
    """
    從 BigQuery 抓取熱門 GitHub WatchEvent 資料。
    """
    query = f"""
        SELECT name AS repo_name, watch_count
        FROM `{TABLE_REF}`
        ORDER BY watch_count DESC
        LIMIT 1000
    """
    df = client.query(query).to_dataframe()
    df["url"] = df["repo_name"].apply(lambda name: f"http://github.com/{name}")
    df["link"] = df["url"].apply(lambda url: f'<a href="{url}" target="_blank">點我</a>')
    return df

@st.cache_resource
def get_table_created_time():
    """
    從 BigQuery 查詢資料表建立時間。
    """
    table = client.get_table(TABLE_REF)
    return table.created.isoformat()

# 圖表：Altair
def plot_altair_chart(df):
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('watch_count:Q', title='Watch 次數'),
        y=alt.Y('repo_name:N', sort='-x', title='Repository'),
        tooltip=['repo_name', 'watch_count']
    ).properties(
        width='container',
        height=600,
        title="Watch 次數前 1000 名 Repository"
    )
    st.altair_chart(chart, use_container_width=True)

# 圖表：Plotly
def plot_plotly_chart(df):
    fig = px.bar(
        df,
        x='watch_count',
        y='repo_name',
        orientation='h',
        title='📊 GitHub WatchEvent Top 100',
        labels={'watch_count': 'Watch 次數', 'repo_name': 'Repository'},
        height=800
    )
    st.plotly_chart(fig, use_container_width=True)

# 圖表：Pie Chart
def plot_pie_chart(df):
    top10 = df.head(10)
    fig = px.pie(
        top10,
        names='repo_name',
        values='watch_count',
        title='前 10 名 Repo 的 Watch 分佈',
        hole=0.3
    )
    st.plotly_chart(fig, use_container_width=True)

# === 主流程 ===

# 取得資料與創建時間
df = get_watch_events()
created_time_iso = get_table_created_time()
created_time = datetime.fromisoformat(created_time_iso).strftime("%Y-%m-%d %H:%M:%S")

# 設定 Streamlit 頁面
st.set_page_config(page_title="GitHub WatchEvent 熱門 Repo", page_icon="📊", layout="wide")

# 顯示標題與說明（含資料建立時間）
st.markdown(f"""
    <h1 style="text-align: center; color: #2D9CDB;">📈 GitHub WatchEvent 熱門 Repo</h1>
    <p style="text-align: center; color: #7B7B7B;">根據 GitHub WatchEvent 統計最熱門的 repositories</p>
    <p style="text-align: center; font-size: 14px; color: #B0B0B0;">資料表建立時間：{created_time}</p>
""", unsafe_allow_html=True)

# 顯示圖表與資料
if df.empty:
    st.warning("目前查無資料")
else:
    # 圖表選擇
    chart_type = st.radio("選擇要顯示的圖表類型", ["Bar Chart（Altair）", "Bar Chart（Plotly）", "Pie Chart"], horizontal=True)

    if chart_type == "Bar Chart（Altair）":
        plot_altair_chart(df)
    elif chart_type == "Bar Chart（Plotly）":
        plot_plotly_chart(df)
    elif chart_type == "Pie Chart":
        plot_pie_chart(df)

    # 顯示表格（帶超連結）
    st.write("### Repository 詳細資料")
    df_display = df[["repo_name", "watch_count", "link"]].rename(columns={
        "repo_name": "Repository",
        "watch_count": "Watch 次數",
        "link": "連結"
    })
    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

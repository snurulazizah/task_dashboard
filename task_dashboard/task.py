# dashboard_sales.py
import streamlit as st
import pandas as pd
from pandas import to_datetime
import plotly.express as px
import requests
import os
from dotenv import load_dotenv

# =======================
# 1️⃣ Konfigurasi Awal
# =======================
st.set_page_config(page_title="Sales Performance Dashboard", layout="wide")
st.title("📊 Sales Performance Dashboard")
st.markdown("Menampilkan performa sales berdasarkan jumlah task (Qontak CRM).")

# =======================
# 2️⃣ Load Token dari .env
# =======================
load_dotenv()  # membaca file .env
API_TOKEN = os.getenv("QONTAK_API_TOKEN")

if not API_TOKEN:
    st.error("❌ Token QONTAK_API_TOKEN tidak ditemukan. Pastikan sudah ditulis di file .env.")
    st.stop()

# =======================
# 3️⃣ Ambil data dari API
# =======================
@st.cache_data(ttl=3600)
def get_tasks(page=1, per_page=100):
    url = f"https://crm.qontak.com/api/v3.1/tasks?filter=alltask&page={page}&per_page={per_page}"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"Gagal ambil data API: {r.status_code}")
        st.text(r.text[:300])
        return pd.DataFrame()
    data = r.json()
    return pd.json_normalize(data["response"])

df = get_tasks()

if df.empty:
    st.warning("Data belum tersedia atau token expired.")
    st.stop()

# =======================
# 4️⃣ Persiapan Data
# =======================
df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
df_display = df[["id", "name", "user_full_name", "crm_task_status_id", "due_date", "created_at"]]

# =======================
# 5️⃣ Filter
# =======================
col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input(
        "📅 Tanggal mulai (due_date)",
        df["due_date"].min().date() if df["due_date"].notnull().any() else pd.Timestamp.now().date()
    )
    end_date = st.date_input(
        "📅 Tanggal akhir (due_date)",
        df["due_date"].max().date() if df["due_date"].notnull().any() else pd.Timestamp.now().date()
    )

with col2:
    sales_selected = st.multiselect(
        "👤 Pilih Sales",
        sorted(df["user_full_name"].dropna().unique()),
        default=None
    )

mask = (df["due_date"].dt.date >= start_date) & (df["due_date"].dt.date <= end_date)
if sales_selected:
    mask &= df["user_full_name"].isin(sales_selected)

df_filtered = df.loc[mask]

st.write(f"Menampilkan {len(df_filtered)} task dari {len(df)} total data.")

# =======================
# 6️⃣ Ringkasan & Visual
# =======================
st.subheader("📋 Ringkasan Task per Sales")
summary = (
    df_filtered.groupby("user_full_name")
    .agg(total_task=("id", "count"))
    .reset_index()
    .sort_values(by="total_task", ascending=False)
)

st.dataframe(summary, use_container_width=True)

st.subheader("📈 Grafik Task per Sales")
if not summary.empty:
    fig = px.bar(
        summary, x="user_full_name", y="total_task",
        text="total_task", color="user_full_name",
        title="Jumlah Task per Sales",
        labels={"user_full_name": "Sales", "total_task": "Jumlah Task"}
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Tidak ada data sesuai filter.")

# =======================
# 7️⃣ Download CSV
# =======================
st.download_button(
    label="⬇️ Download Data (CSV)",
    data=df_filtered.to_csv(index=False),
    file_name="sales_performance.csv",
    mime="text/csv"
)

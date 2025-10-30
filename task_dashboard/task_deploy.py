import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
from pandas import json_normalize

# =============================
# 1️⃣ KONFIGURASI DASHBOARD
# =============================
st.set_page_config(page_title="Sales Performance Dashboard", layout="wide")
st.title("📊 Sales Performance Dashboard (Qontak CRM)")
st.markdown("Analisis performa sales berdasarkan data task CRM secara langsung.")

# =============================
# 3️⃣ AMBIL DATA LANGSUNG DARI API (TANPA FUNGSI DEF)
# =============================
url = "https://app.qontak.com/api/v3.1/tasks?filter=alltask&page=1&per_page=1000"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",  # <-- Bearer token
    "Accept": "application/json"
}

# === 3. LAKUKAN REQUEST KE API ===
response = requests.get(url, headers=headers)

# === 4. CEK HASILNYA ===
content_type = response.headers.get("Content-Type", "")

if response.status_code == 200 and "application/json" in content_type:
    data = response.json()
    
    # Ubah ke DataFrame untuk tampilan tabel
    df = json_normalize(data["response"])

# =============================
# 4️⃣ BERSIHKAN DAN SIAPKAN DATA
# =============================

# Ubah list of dict di kolom 'additional_fields' menjadi dict tunggal
df_expanded = (
    df['additional_fields']
    .apply(lambda x: {d['name']: d.get('value', None) for d in x})
    .apply(pd.Series)
)

# Gabungkan kembali dengan DataFrame asli
df_final = pd.concat([df.drop(columns=['additional_fields']), df_expanded], axis=1)

# Jika ingin menyatukan kolom hasil menjadi satu string dengan koma
df_final['merged'] = df_expanded.apply(lambda row: ', '.join([f"{k}: {v}" for k, v in row.items() if pd.notnull(v)]), axis=1)


if df_final.empty:
    st.warning("⚠️ Data kosong atau belum berhasil diambil.")
    st.stop()
df_final["due_date"] = pd.to_datetime(df_final.get("due_date"), errors="coerce")
df_final["convert_to"] = pd.to_numeric(df_final["convert_to"], errors="coerce").astype("Int64")
df_final["engagement_type"] = pd.to_numeric(df_final["engagement_type"], errors="coerce").astype("Int64")

# Ganti angka 1–5 dengan karakter (mapping status)
status_mapping = {
    1: "Belum Dimulai",
    2: "Dalam Proses",
    3: "Menunggu",
    4: "Selesai",
    5: "Ditunda"
}
df_final["crm_task_status"] = df_final["crm_task_status_id"].map(status_mapping)

mapping_convert = {
    3866814: "Lead Engaged",
    3866815: "Prospect",
    3866816: "Meeting Need",
    3866817: "Proposal Submitted",
    3866818: "Presentation",
    3866819: "Deal",
    3866820: "Invoice"}

df_final["convert_to_label"] = df_final["convert_to"].map(mapping_convert)


# =============================
# 5️⃣ FILTER DATA
# =============================
st.sidebar.header("🔍 Filter Data")

# Filter due date
from datetime import datetime, timedelta

filter_type = st.sidebar.radio("🗓 Filter Tanggal", ["1 Tanggal", "Range Tanggal"])

if filter_type == "1 Tanggal":
    selected_date = st.sidebar.date_input(
        "Pilih tanggal",
       df_final["due_date"].dropna().min().date() if df_final["due_date"].notnull().any() else datetime.now().date()
    )
    # Filter untuk satu tanggal
    df_filtered = df_final[df_final["due_date"].dt.date == selected_date]

elif filter_type == "Range Tanggal":
    start_date, end_date = st.sidebar.date_input(
        "Pilih rentang tanggal",
        [
            df_final["due_date"].dropna().min().date() if df_final["due_date"].notnull().any() else datetime.now().date() - timedelta(days=7),
            df_final["due_date"].dropna().max().date() if df_final["due_date"].notnull().any() else datetime.now().date()
        ]
    )
    # Filter untuk range tanggal
    df_filtered = df_final[
        (df_final["due_date"].dt.date >= start_date) &
        (df_final["due_date"].dt.date <= end_date)
    ]


# Filter status
status_selected = st.sidebar.multiselect(
    "Pilih Status Task",
    options=list(status_mapping.values()),
    default=list(status_mapping.values())
)
df_filtered = df_filtered[df_filtered["crm_task_status"].isin(status_selected)]

# Filter sales
sales_selected = st.sidebar.multiselect(
    "Pilih Sales (user_full_name)",
    options=sorted(df_final["user_full_name"].dropna().unique()),
    default=None
)
if sales_selected:
    df_filtered = df_filtered[df_filtered["user_full_name"].isin(sales_selected)]

 # === FILTER CONVERT TO DAN ENGAGEMENT TYPE ===
st.sidebar.subheader("🔄 Filter Convert To")

convert_options = sorted(df_final["convert_to_label"].dropna().unique())
convert_selected = st.sidebar.multiselect(
    "Pilih Convert To",
    options=convert_options,
    default=convert_options
)
df_filtered_2= df_final[df_final["convert_to_label"].isin(convert_selected)]

   
    
# =============================
# 6️⃣ TABEL DAN METRIK
# =============================
st.subheader("📋 Data Task (Hasil Filter)")
with st.expander("Lihat / Sembunyikan Data Task", expanded=True):
    st.dataframe(df_filtered, use_container_width=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Task", len(df_filtered))
with col2:
    st.metric("Task Selesai", len(df_filtered[df_filtered["crm_task_status_id"] == 4]))
with col3:
    st.metric("Task Dalam Proses", len(df_filtered[df_filtered["crm_task_status_id"] == 2]))

with col4:
    st.metric("Belum di mulai", len(df_filtered[df_filtered["crm_task_status_id"] == 1]))


# =============================
# 7️⃣ GRAFIK TASK PER SALES & STATUS
# =============================
st.subheader("📈 Grafik Task per Sales dan Status")

summary = (
    df_filtered.groupby(["crm_task_status", "user_full_name"])
    .agg(total_task=("id", "count"))
    .reset_index()
)

if not summary.empty:
    # Tentukan warna manual per status
    color_map = {
    "Selesai": "#10B981",        # hijau elegan (lebih dalam dari hijau terang)
    "Dalam Proses": "#9CA3AF",   # kuning lembut & tidak mencolok
    "Belum Dimulai": "#4B5563",  # merah elegan (deep red)
    "Menunggu": "#5DADE2",       # biru lembut (optional)
    "Ditunda": "#BDC3C7"         # abu muda netral (optional)
}

    fig = px.bar(
        summary,
        x="user_full_name",
        y="total_task",
        color="crm_task_status",
        text="total_task",
        title="Jumlah Task Berdasarkan Status dan Sales",
        barmode="group",
        color_discrete_map=color_map,  # <--- pakai peta warna manual
        labels={
            "user_full_name": "Sales",
            "total_task": "Jumlah Task",
            "crm_task_status": "Status"
        }
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(
        legend_title_text="Status Task",
        xaxis_title="Sales",
        yaxis_title="Jumlah Task",
        plot_bgcolor="white",
        legend=dict(title_font=dict(size=12), font=dict(size=10))
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Tidak ada data sesuai filter.")
st.subheader("📊 Task Summary Berdasarkan Conversion Stage")

# === Membuat tabel pivot jumlah task per user dan crm_task_status_id ===
def create_conversion_summary(df_source, convert_id, title):
    st.markdown(f"#### {title}")

    # Filter data sesuai convert_to ID
    df_sub = df_source[df_source["convert_to_label"] == convert_id]

    if df_sub.empty:
        st.info(f"Tidak ada data untuk {title}")
        return

    # Buat pivot table langsung berdasarkan crm_task_status_id
    pivot_table = pd.pivot_table(
        df_sub,
        index="user_full_name",
        columns="crm_task_status",
        values="id",
        aggfunc="count",
        fill_value=0
    ).reset_index()

    # Tambahkan kolom total task
    pivot_table["Total Task"] = pivot_table.drop("user_full_name", axis=1).sum(axis=1)

    # Urutkan kolom agar rapi: user_full_name dulu, lalu semua status task, lalu total
    status_cols = [col for col in pivot_table.columns if col not in ["user_full_name", "Total Task"]]
    pivot_table = pivot_table[["user_full_name"] + status_cols + ["Total Task"]]

    # Tampilkan tabel
    st.dataframe(pivot_table, use_container_width=True)


# === 1️⃣ Prospect ===
create_conversion_summary(df_filtered, 'Prospect', "📋 Jumlah Prospect per User dan Status Task")

# === 2️⃣ Proposal Submitted ===
create_conversion_summary(df_filtered, 'Proposal Submitted', "📋 Jumlah Proposal Submitted per User dan Status Task")

# === 3️⃣ Presentation ===
create_conversion_summary(df_filtered, 'Presentation', "📋 Jumlah Presentation per User dan Status Task")

# === 4️⃣ Deal ===
create_conversion_summary(df_filtered, 'Deal', "📋 Jumlah Deal per User dan Status Task")

# === 5️⃣ Invoice ===
create_conversion_summary(df_filtered, 'Invoice', "📋 Jumlah Invoice per User dan Status Task")



# =============================
# 🗓 8️⃣ GRAFIK DAILY TASK BERDASARKAN STATUS
# =============================
st.subheader("🗓 Grafik Daily Task Berdasarkan Status Task")

# Pastikan kolom due_date ada
if "due_date" in df_filtered.columns:
    df_daily = (
        df_filtered.dropna(subset=["due_date"])
        .groupby([df_filtered["due_date"].dt.date, "crm_task_status"])
        .agg(total_task=("id", "count"))
        .reset_index()
        .rename(columns={"due_date": "Tanggal"})
    )

    if not df_daily.empty:
        fig_daily = px.line(
            df_daily,
            x="Tanggal",
            y="total_task",
            color="crm_task_status",
            markers=True,
            title="Tren Harian Jumlah Task Berdasarkan Status",
            labels={
                "Tanggal": "Tanggal Task",
                "total_task": "Jumlah Task",
                "crm_task_status": "Status Task"
            }
        )
        fig_daily.update_traces(mode="lines+markers", line=dict(width=2))
        fig_daily.update_layout(
            xaxis=dict(dtick="D1", tickformat="%d-%b"),
            hovermode="x unified"
        )

        # ✅ Tambahkan expander di sini
        with st.expander("📊 Lihat / Sembunyikan Grafik Daily Task", expanded=True):
            st.plotly_chart(fig_daily, use_container_width=True)

    else:
        st.info("Tidak ada data untuk menampilkan grafik harian.")
else:
    st.warning("Kolom due_date tidak ditemukan di dataset.")


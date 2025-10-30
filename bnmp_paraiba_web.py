"""
BNMP Paraíba - Painel Web (Dark) com filtros laterais em estilo 'botões'
Autor: Gerado para Ramon Barbosa
Funcionalidades:
- Upload XLSX ou download por URL (se disponível sem CAPTCHA)
- Filtros laterais (Situação, Órgão Expedidor, Peça, Data)
- Quick-buttons no sidebar com os top valores (estilo dashboard)
- Contadores, gráficos, tabela dinâmica e geração de PDF
- Tema escuro aplicado via CSS
"""

import os
import io
import datetime
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Optional mapping: folium/heatmap only if locations exist
try:
    import folium
    from folium.plugins import HeatMap
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except Exception:
    HAS_FOLIUM = False

# ---------- Config ----------
OUT_DIR = os.path.join(os.path.expanduser('~'), 'bnmp_paraiba')
os.makedirs(OUT_DIR, exist_ok=True)
FILTERED_OUTPUT = os.path.join(OUT_DIR, 'BNMP_Paraiba_filtered.xlsx')
REPORT_OUTPUT = os.path.join(OUT_DIR, 'Relatorio_BNMP_Paraiba.pdf')

st.set_page_config(page_title="BNMP PB - Painel (Dark)", layout="wide")
# Inject simple dark CSS to get a more 'dashboard' feel
st.markdown(
    """
    <style>
    .reportview-container {background: #0f1115;}
    .css-1v0mbdj {background: #0f1115;}
    .stApp { color: #E6EEF3; }
    .sidebar .sidebar-content { background: #0b0d10; }
    .stButton>button { background-color: #1f2937; color: #fff; border-radius: 6px; }
    .stDownloadButton>button { background-color: #059669; color: white; }
    .stSelectbox, .stMultiselect, .stTextInput input { background: #0f1720; color: #e6eef3; }
    .stDataFrame table { background: #0f1720; color: #e6eef3; }
    .css-ffhzg2 { color: #e6eef3; } /* titles */
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📊 BNMP - Paraíba (Dark Dashboard)")
st.markdown("Painel com filtros laterais (botões rápidos + seletores), busca e relatório PDF.")

# -------- Sidebar filters (buttons + multiselects) ----------
st.sidebar.header("Filtros Rápidos")

# Inputs (upload or URL)
url_input = st.sidebar.text_input("URL de download (opcional, sem CAPTCHA)")
uploaded_file = st.sidebar.file_uploader("Ou faça upload do arquivo XLSX", type=["xlsx", "xls"])

# Helper to load dataframe
@st.cache_data
def read_excel_bytes(bytes_io):
    try:
        return pd.read_excel(BytesIO(bytes_io))
    except Exception:
        return pd.read_excel(io.BytesIO(bytes_io))

def load_df():
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            return df
        except Exception as e:
            st.sidebar.error(f"Erro ao ler arquivo enviado: {e}")
            return None
    elif url_input:
        st.sidebar.info("Tentando baixar URL...")
        try:
            import requests
            r = requests.get(url_input, timeout=30)
            if 'captcha' in r.text.lower():
                st.sidebar.error("URL requer CAPTCHA — faça upload manual do XLSX.")
                return None
            return read_excel_bytes(r.content)
        except Exception as e:
            st.sidebar.error(f"Falha no download: {e}")
            return None
    else:
        return None

df = load_df()

if df is None:
    st.info("Envie um arquivo XLSX ou informe um link direto (sem CAPTCHA).")
    st.stop()

# Normalize column names (strip)
df.columns = [c.strip() for c in df.columns]

# Column names expected from your sheet
# You've provided: Número, Nome, Alcunha, Nome da Mãe, Nome do Pai, Data de Nascimento, Situação, Data, Órgão Expedidor, Peça
# We'll safely handle missing columns
col_num = next((c for c in df.columns if c.lower().startswith("númer") or c.lower().startswith("numero")), None)
col_nome = next((c for c in df.columns if c.lower() == "nome"), None)
col_alcunha = next((c for c in df.columns if "alcun" in c.lower()), None)
col_mae = next((c for c in df.columns if "mãe" in c.lower() or "mae" in c.lower()), None)
col_pai = next((c for c in df.columns if "pai" in c.lower()), None)
col_dtnasc = next((c for c in df.columns if "nascimento" in c.lower() or "data de nascimento" in c.lower()), None)
col_sit = next((c for c in df.columns if "situa" in c.lower()), None)
col_data = next((c for c in df.columns if c.lower() == "data"), None)
col_org = next((c for c in df.columns if "órgão" in c.lower() or "orgao" in c.lower() or "expedidor" in c.lower()), None)
col_peca = next((c for c in df.columns if "peça" in c.lower() or "peca" in c.lower() or "descricao" in c.lower()), None)

# Prepare DataFrame copies & date parsing
df_work = df.copy()
if col_data:
    try:
        df_work[col_data] = pd.to_datetime(df_work[col_data], errors='coerce')
    except Exception:
        pass

# Sidebar: build filter widgets
st.sidebar.markdown("### Filters")

# Date range filter
if col_data:
    min_date = df_work[col_data].min()
    max_date = df_work[col_data].max()
    date_range = st.sidebar.date_input("Faixa de data (Data)", value=(min_date.date() if pd.notnull(min_date) else None,
                                                                     max_date.date() if pd.notnull(max_date) else None))
else:
    date_range = None

# Function to extract unique values safely
def uniques(col):
    if col and col in df_work.columns:
        return list(df_work[col].fillna("Não informado").astype(str).value_counts().index)
    return []

# Situação filter (multiselect + quick-buttons)
sit_vals = uniques(col_sit)
selected_situations = st.sidebar.multiselect("Situação", options=sit_vals, default=None)
st.sidebar.markdown("Situação - rápidos:")
if sit_vals:
    top_sit = sit_vals[:6]
    cols_buttons = st.sidebar.columns(2)
    for i, val in enumerate(top_sit):
        if cols_buttons[i % 2].button(val):
            # emulate selection
            selected_situations = [val]
            st.session_state['quick_sit'] = val

# Órgão Expedidor filter
org_vals = uniques(col_org)
selected_orgs = st.sidebar.multiselect("Órgão Expedidor", options=org_vals, default=None)
st.sidebar.markdown("Órgãos - rápidos:")
if org_vals:
    top_org = org_vals[:6]
    cols_buttons = st.sidebar.columns(2)
    for i, val in enumerate(top_org):
        if cols_buttons[i % 2].button(val):
            selected_orgs = [val]
            st.session_state['quick_org'] = val

# Peça / Tipo de crime filter
peca_vals = uniques(col_peca)
selected_pecas = st.sidebar.multiselect("Peça / Tipo", options=peca_vals, default=None)
st.sidebar.markdown("Peças - rápidas:")
if peca_vals:
    top_pec = peca_vals[:6]
    cols_buttons = st.sidebar.columns(2)
    for i, val in enumerate(top_pec):
        if cols_buttons[i % 2].button(val):
            selected_pecas = [val]
            st.session_state['quick_pec'] = val

# Search box for name / número
search_text = st.sidebar.text_input("Pesquisar por Nome / Número")

# Apply filters
df_filtered = df_work.copy()

if selected_situations:
    df_filtered = df_filtered[df_filtered[col_sit].fillna("Não informado").astype(str).isin(selected_situations)]

if selected_orgs:
    df_filtered = df_filtered[df_filtered[col_org].fillna("Não informado").astype(str).isin(selected_orgs)]

if selected_pecas:
    df_filtered = df_filtered[df_filtered[col_peca].fillna("Não informado").astype(str).isin(selected_pecas)]

if date_range and col_data:
    try:
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        df_filtered = df_filtered[(df_filtered[col_data] >= start_date) & (df_filtered[col_data] <= end_date)]
    except Exception:
        pass

if search_text:
    s = search_text.strip().lower()
    mask = pd.Series(False, index=df_filtered.index)
    for c in [col_num, col_nome, col_alcunha, col_mae, col_pai]:
        if c and c in df_filtered.columns:
            mask = mask | df_filtered[c].astype(str).str.lower().str.contains(s, na=False)
    df_filtered = df_filtered[mask]

# Save filtered copy
try:
    df_filtered.to_excel(FILTERED_OUTPUT, index=False)
except Exception:
    pass

# -------- Main layout (top counters + charts + table) --------
col1, col2, col3, col4 = st.columns([1,1,1,1])
col1.metric("Total Mandados", len(df_filtered))
col2.metric("Situações únicas", df_filtered[col_sit].nunique() if col_sit else 0)
col3.metric("Órgãos únicos", df_filtered[col_org].nunique() if col_org else 0)
col4.metric("Peças únicas", df_filtered[col_peca].nunique() if col_peca else 0)

st.markdown("---")
st.subheader("Gráficos")

# Plot helper using matplotlib
def plot_barh(series, title):
    fig, ax = plt.subplots(figsize=(8,4))
    series_sorted = series.sort_values()
    series_sorted.plot(kind='barh', ax=ax)
    ax.set_title(title, color='white')
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.patch.set_facecolor('#0f1115')
    ax.set_facecolor('#0f1115')
    return fig

# Top by Situação
if col_sit:
    sit_series = df_filtered[col_sit].fillna('Não informado').astype(str).value_counts().head(20)
    st.pyplot(plot_barh(sit_series, "Mandados por Situação (Top 20)"))

# Top Órgãos
if col_org:
    org_series = df_filtered[col_org].fillna('Não informado').astype(str).value_counts().head(20)
    st.pyplot(plot_barh(org_series, "Mandados por Órgão Expedidor (Top 20)"))

# Top Peças
if col_peca:
    pec_series = df_filtered[col_peca].fillna('Não informado').astype(str).value_counts().head(20)
    st.pyplot(plot_barh(pec_series, "Mandados por Peça / Tipo (Top 20)"))

st.markdown("---")
st.subheader("Resultados (tabela)")

# Show table (paginated-like, show first 1000)
st.dataframe(df_filtered.head(1000).reset_index(drop=True))

# If folium available and there are latitude/longitude columns, show heatmap
lat_col = next((c for c in df_filtered.columns if 'lat' in c.lower()), None)
lon_col = next((c for c in df_filtered.columns if 'lon' in c.lower() or 'lng' in c.lower()), None)
if HAS_FOLIUM and lat_col and lon_col:
    coords = df_filtered[[lat_col, lon_col]].dropna().values.tolist()
    if coords:
        m = folium.Map(location=[-7.5, -36.5], zoom_start=7)
        HeatMap(coords).add_to(m)
        st_folium(m, width=900, height=500)

# -------- PDF generation ----------
def gerar_pdf(mun_counts_series, org_series, pec_series, total_count):
    doc = SimpleDocTemplate(REPORT_OUTPUT, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = []
    flow.append(Paragraph("Relatório BNMP - Paraíba", styles['Title']))
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(f"Data de geração: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    flow.append(Paragraph(f"Total de mandados (após filtros): {total_count}", styles['Normal']))
    flow.append(Spacer(1, 12))

    # Situação
    flow.append(Paragraph("Top Situações", styles['Heading2']))
    data = [["Situação", "Contagem"]] + [[i, int(v)] for i, v in mun_counts_series.items()]
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey), ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)]))
    flow.append(t)
    flow.append(Spacer(1,12))

    # Orgãos
    flow.append(Paragraph("Top Órgãos Expedidores", styles['Heading2']))
    data = [["Órgão", "Contagem"]] + [[i, int(v)] for i, v in org_series.items()]
    t2 = Table(data)
    t2.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey), ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)]))
    flow.append(t2)
    flow.append(Spacer(1,12))

    # Peças
    flow.append(Paragraph("Top Peças / Tipos", styles['Heading2']))
    data = [["Peça/Tipo", "Contagem"]] + [[i, int(v)] for i, v in pec_series.items()]
    t3 = Table(data)
    t3.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey), ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)]))
    flow.append(t3)

    doc.build(flow)
    return REPORT_OUTPUT

# Button to generate PDF
if st.button("📄 Gerar Relatório PDF"):
    sit_top = df_filtered[col_sit].fillna('Não informado').astype(str).value_counts().head(20) if col_sit else pd.Series()
    org_top = df_filtered[col_org].fillna('Não informado').astype(str).value_counts().head(20) if col_org else pd.Series()
    pec_top = df_filtered[col_peca].fillna('Não informado').astype(str).value_counts().head(20) if col_peca else pd.Series()
    out_pdf = gerar_pdf(sit_top, org_top, pec_top, len(df_filtered))
    with open(out_pdf, "rb") as f:
        st.download_button("⬇️ Baixar Relatório (PDF)", f, file_name=os.path.basename(out_pdf), mime="application/pdf")
    st.success(f"PDF gerado: {out_pdf}")

st.markdown("---")
st.caption("Painel gerado para uso interno. Desenvolvido por Ramon.")

"""
BNMP Paraíba - Painel Web com Relatório PDF e Busca por Município
Autor: Ramon Barbosa
"""

import os
import io
import datetime
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# ----------------- CONFIG -----------------
OUT_DIR = os.path.join(os.path.expanduser('~'), 'bnmp_paraiba')
os.makedirs(OUT_DIR, exist_ok=True)
FILTERED_OUTPUT = os.path.join(OUT_DIR, 'BNMP_Paraiba_filtered.xlsx')
REPORT_OUTPUT = os.path.join(OUT_DIR, 'Relatorio_BNMP_Paraiba.pdf')

st.set_page_config(page_title="Painel BNMP Paraíba", layout="wide")
st.title("📊 Painel BNMP - Estado da Paraíba")

# Sidebar
st.sidebar.header("Configurações")
url_input = st.sidebar.text_input("URL para download automático (opcional)", value="")
manual_file = st.sidebar.file_uploader("Ou envie manualmente o arquivo XLSX do BNMP", type=["xlsx", "xls"])

# ----------------- Funções -----------------
def load_bnmp_data():
    if manual_file is not None:
        df = pd.read_excel(manual_file)
        return df
    elif url_input:
        try:
            st.info("Baixando arquivo...")
            r = requests.get(url_input, timeout=30)
            if 'captcha' in r.text.lower():
                st.error("O portal BNMP está protegido por CAPTCHA. Faça o download manual.")
                return None
            df = pd.read_excel(io.BytesIO(r.content))
            return df
        except Exception as e:
            st.error(f"Erro ao baixar: {e}")
            return None
    else:
        st.warning("Envie um arquivo ou informe um link válido.")
        return None


def detect_columns(df):
    state_col = next((c for c in df.columns if 'uf' in c.lower() or 'estado' in c.lower()), None)
    mun_col = next((c for c in df.columns if 'muni' in c.lower() or 'cidade' in c.lower()), None)
    crime_col = next((c for c in df.columns if 'crime' in c.lower() or 'descricao' in c.lower() or 'peca' in c.lower()), None)
    return state_col, mun_col, crime_col


def filter_paraiba(df):
    state_col, mun_col, crime_col = detect_columns(df)
    if not state_col:
        st.error("Não foi possível detectar coluna de Estado.")
        return None, None, None
    possible_vals = ['pb', 'paraiba', 'paraíba']
    mask = df[state_col].astype(str).str.lower().isin(possible_vals)
    mask |= df[state_col].astype(str).str.lower().str.contains(r'\\bpb\\b')
    filtered = df[mask].copy()
    if len(filtered) == 0:
        st.warning("Nenhum registro encontrado para Paraíba.")
    return filtered, mun_col, crime_col


def plot_bar(data, title, xlabel):
    fig, ax = plt.subplots(figsize=(8, 4))
    data.sort_values().plot(kind='barh', ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    plt.tight_layout()
    return fig


def create_heatmap(df, mun_col=None):
    if 'latitude' in df.columns and 'longitude' in df.columns:
        coords = df[['latitude', 'longitude']].dropna().values.tolist()
        if len(coords) == 0:
            st.warning("Sem coordenadas geográficas para gerar mapa.")
            return
        m = folium.Map(location=[-7.5, -36.5], zoom_start=7)
        HeatMap(coords).add_to(m)
        st_folium(m, width=900, height=600)
    elif mun_col:
        counts = df[mun_col].fillna('Não informado').value_counts().reset_index()
        counts.columns = ['Município', 'Mandados']
        st.dataframe(counts)
        st.info("Sem coordenadas. Exibindo tabela de mandados por município.")
    else:
        st.warning("Não foi possível gerar o mapa.")


def gerar_pdf(mun_counts, crime_counts, total):
    doc = SimpleDocTemplate(REPORT_OUTPUT, pagesize=A4)
    styles = getSampleStyleSheet()
    flow = []

    flow.append(Paragraph("Relatório BNMP - Estado da Paraíba", styles['Title']))
    flow.append(Spacer(1, 12))
    flow.append(Paragraph(f"Data de geração: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    flow.append(Paragraph(f"Total de mandados filtrados: <b>{total}</b>", styles['Normal']))
    flow.append(Spacer(1, 20))

    # Municipios
    flow.append(Paragraph("Top 20 Municípios com mais mandados", styles['Heading2']))
    data = [["Município", "Mandados"]] + list(mun_counts.items())
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    flow.append(t)
    flow.append(Spacer(1, 20))

    # Crimes
    flow.append(Paragraph("Top 20 Tipos de Crime", styles['Heading2']))
    data = [["Tipo de Crime", "Mandados"]] + list(crime_counts.items())
    t = Table(data)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    flow.append(t)

    doc.build(flow)
    return REPORT_OUTPUT


# ----------------- Execução -----------------
if st.sidebar.button("Processar BNMP"):
    df = load_bnmp_data()
    if df is not None:
        filtered, mun_col, crime_col = filter_paraiba(df)
        if filtered is not None and len(filtered) > 0:
            filtered.to_excel(FILTERED_OUTPUT, index=False)
            st.success(f"✅ {len(filtered)} registros filtrados e salvos em {FILTERED_OUTPUT}")

            st.subheader("📈 Estatísticas Gerais")
            mun_counts = filtered[mun_col].fillna('Não informado').astype(str).value_counts().head(20) if mun_col else None
            crime_counts = filtered[crime_col].fillna('Não informado').astype(str).value_counts().head(20) if crime_col else None

            if mun_counts is not None:
                st.pyplot(plot_bar(mun_counts, "Mandados por Município (Top 20)", "Qtd"))
            if crime_counts is not None:
                st.pyplot(plot_bar(crime_counts, "Mandados por Tipo (Top 20)", "Qtd"))

            st.subheader("🗺️ Mapa de Calor / Distribuição")
            create_heatmap(filtered, mun_col)

            # 🔍 BUSCA POR MUNICÍPIO
            if mun_col:
                st.subheader("🔍 Buscar Mandados por Município")
                busca = st.text_input("Digite o nome (ou parte) do município:")
                if busca:
                    filtro_busca = filtered[filtered[mun_col].str.contains(busca, case=False, na=False)]
                    if not filtro_busca.empty:
                        st.success(f"{len(filtro_busca)} mandados encontrados para '{busca.title()}'")
                        st.dataframe(filtro_busca)

                        if crime_col:
                            crime_counts_local = filtro_busca[crime_col].fillna('Não informado').astype(str).value_counts().head(15)
                            st.pyplot(plot_bar(crime_counts_local, f"Mandados por Tipo - {busca.title()}", "Qtd"))
                    else:
                        st.warning("Nenhum registro encontrado para este município.")

            # Botão de PDF
            if st.button("📄 Gerar Relatório PDF"):
                pdf_path = gerar_pdf(mun_counts, crime_counts, len(filtered))
                st.success(f"Relatório gerado com sucesso: {pdf_path}")
                with open(pdf_path, "rb") as f:
                    st.download_button("⬇️ Baixar Relatório PDF", f, file_name="Relatorio_BNMP_Paraiba.pdf", mime="application/pdf")

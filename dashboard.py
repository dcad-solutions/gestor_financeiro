import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from sheets_service import SheetsService
from ai_agent import FinancialAIAgent
from config import SPREADSHEET_ID, CENTROS_DE_CUSTO

# Configuração da página Streamlit
st.set_page_config(
    page_title="Gestor Financeiro 360° | Casa • Consultório • D-CAD",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS personalizada
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #1f77b4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def carregar_transacoes():
    """Carrega dados da planilha com cache inteligente de 60 segundos."""
    try:
        service = SheetsService()
        df = service.get_all_transactions()
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def main():
    # Cabeçalho
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title("💼 Painel de Controle Financeiro Integrado")
        st.caption("Visão em tempo real das finanças pessoais e negócios: **Casa**, **Consultório** e **D-CAD**.")
    with col_t2:
        if SPREADSHEET_ID:
            st.markdown(
                f"""
                <div style="text-align: right; padding-top: 20px;">
                    <a href="https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit" target="_blank" 
                       style="text-decoration: none; background: #0f9d58; color: white; padding: 10px 16px; border-radius: 6px; font-weight: bold;">
                        📊 Abrir Planilha Google
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Barra Lateral - Filtros
    st.sidebar.header("🔍 Filtros de Análise")

    # Botão de recarregar cache
    if st.sidebar.button("🔄 Atualizar Dados Agora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    df_raw, erro = carregar_transacoes()

    if erro:
        st.error(f"⚠️ Erro ao conectar com o Google Sheets: {erro}")
        st.info("Verifique se o arquivo `credentials.json` e o `SPREADSHEET_ID` foram configurados no `.env`.")
        return

    if df_raw.empty:
        st.warning("Nenhuma transação encontrada na planilha. Envie mensagens pelo Telegram para começar!")
        return

    # Filtro de Centro de Custo
    centro_selecionado = st.sidebar.selectbox(
        "Centro de Custo",
        ["Todos (Consolidado)"] + CENTROS_DE_CUSTO
    )

    # Filtro de Usuário (Lançado Por)
    usuario_selecionado = "Todos"
    if "Lançado Por" in df_raw.columns:
        usuarios = [str(u) for u in df_raw["Lançado Por"].dropna().unique() if str(u).strip()]
        if len(usuarios) > 1:
            usuario_selecionado = st.sidebar.selectbox("👤 Lançado Por", ["Todos"] + sorted(usuarios))

    # Filtro de Período
    opcoes_periodo = ["Mês Atual", "Últimos 30 Dias", "Últimos 90 Dias", "Ano Atual", "Todo o Período", "Personalizado"]
    periodo_escolhido = st.sidebar.selectbox("Período de Tempo", opcoes_periodo)

    hoje = datetime.now()
    if periodo_escolhido == "Mês Atual":
        data_inicio = datetime(hoje.year, hoje.month, 1)
        data_fim = hoje
    elif periodo_escolhido == "Últimos 30 Dias":
        data_inicio = hoje - timedelta(days=30)
        data_fim = hoje
    elif periodo_escolhido == "Últimos 90 Dias":
        data_inicio = hoje - timedelta(days=90)
        data_fim = hoje
    elif periodo_escolhido == "Ano Atual":
        data_inicio = datetime(hoje.year, 1, 1)
        data_fim = hoje
    elif periodo_escolhido == "Personalizado":
        col_d1, col_d2 = st.sidebar.columns(2)
        data_inicio = col_d1.date_input("Início", hoje - timedelta(days=30))
        data_fim = col_d2.date_input("Fim", hoje)
        data_inicio = datetime.combine(data_inicio, datetime.min.time())
        data_fim = datetime.combine(data_fim, datetime.max.time())
    else:
        data_inicio = df_raw["Data"].min() if not df_raw["Data"].isna().all() else hoje
        data_fim = hoje

    # Aplicação dos Filtros
    df = df_raw.copy()
    if "Data" in df.columns:
        df = df[(df["Data"] >= pd.to_datetime(data_inicio)) & (df["Data"] <= pd.to_datetime(data_fim))]

    if centro_selecionado != "Todos (Consolidado)":
        df = df[df["Centro de Custo"] == centro_selecionado]

    if usuario_selecionado != "Todos" and "Lançado Por" in df.columns:
        df = df[df["Lançado Por"] == usuario_selecionado]

    # Cálculos Principais
    total_despesas = df[df["Tipo"] == "Despesa"]["Valor"].sum()
    total_receitas = df[df["Tipo"] == "Receita"]["Valor"].sum()
    saldo_liquido = total_receitas - total_despesas
    qtd_transacoes = len(df)

    # Cards de Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔴 Despesas Totais", f"R$ {total_despesas:,.2f}")
    with col2:
        st.metric("🟢 Receitas Totais", f"R$ {total_receitas:,.2f}")
    with col3:
        delta_color = "normal" if saldo_liquido >= 0 else "inverse"
        st.metric("💰 Saldo Líquido", f"R$ {saldo_liquido:,.2f}", delta=f"R$ {saldo_liquido:,.2f}", delta_color=delta_color)
    with col4:
        st.metric("📝 Total de Lançamentos", f"{qtd_transacoes}")

    st.markdown("---")

    # Gráficos em Linha Dupla
    col_g1, col_g2 = st.columns([1, 1])

    with col_g1:
        st.subheader("📊 Divisão de Despesas por Centro de Custo")
        df_desp = df[df["Tipo"] == "Despesa"]
        if not df_desp.empty:
            custo_por_centro = df_desp.groupby("Centro de Custo")["Valor"].sum().reset_index()
            fig_pizza = px.pie(
                custo_por_centro,
                values="Valor",
                names="Centro de Custo",
                hole=0.45,
                color="Centro de Custo",
                color_discrete_map={"Casa": "#3498db", "Consultório": "#2ecc71", "D-CAD": "#e74c3c"}
            )
            fig_pizza.update_traces(textposition="inside", textinfo="percent+label")
            fig_pizza.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350)
            st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("Nenhuma despesa no período selecionado.")

    with col_g2:
        st.subheader("🏷️ Top Categorias de Despesas")
        if not df_desp.empty:
            top_cat = (
                df_desp.groupby("Categoria")["Valor"]
                .sum()
                .sort_values(ascending=True)
                .tail(8)
                .reset_index()
            )
            fig_bar = px.bar(
                top_cat,
                x="Valor",
                y="Categoria",
                orientation="h",
                text="Valor",
                color_discrete_sequence=["#1f77b4"]
            )
            fig_bar.update_traces(texttemplate="R$ %{text:,.2f}", textposition="outside")
            fig_bar.update_layout(
                xaxis_title="Valor (R$)",
                yaxis_title="",
                margin=dict(t=20, b=20, l=20, r=40),
                height=350
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Sem dados para listar categorias.")

    # Evolução Temporal
    st.subheader("📈 Evolução Temporal dos Gastos")
    if not df.empty and "Data" in df.columns:
        df_timeline = df.copy()
        df_timeline["Data_Formatada"] = df_timeline["Data"].dt.strftime("%Y-%m-%d")
        timeline_grp = (
            df_timeline[df_timeline["Tipo"] == "Despesa"]
            .groupby(["Data_Formatada", "Centro de Custo"])["Valor"]
            .sum()
            .reset_index()
        )
        if not timeline_grp.empty:
            fig_line = px.bar(
                timeline_grp,
                x="Data_Formatada",
                y="Valor",
                color="Centro de Custo",
                barmode="stack",
                color_discrete_map={"Casa": "#3498db", "Consultório": "#2ecc71", "D-CAD": "#e74c3c"}
            )
            fig_line.update_layout(
                xaxis_title="Data",
                yaxis_title="Despesa (R$)",
                margin=dict(t=20, b=20, l=20, r=20),
                height=350
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Sem transações de despesa no período para a linha do tempo.")

    # Módulo de Consultoria Financeira com IA
    st.markdown("---")
    st.subheader("🧠 Consultoria Financeira Estratégica com IA")
    with st.expander("✨ Clique para gerar um Diagnóstico Executivo Automatizado", expanded=False):
        if st.button("🚀 Gerar Análise com IA Agora"):
            with st.spinner("Analisando padrões, categorias e centros de custos com o Gemini..."):
                # Prepara resumo para o prompt
                resumo_txt = f"Período: {periodo_escolhido}\nTotal Despesas: R$ {total_despesas:.2f}\nTotal Receitas: R$ {total_receitas:.2f}\n\n"
                resumo_txt += "Detalhamento por Centro de Custo:\n"
                for c in CENTROS_DE_CUSTO:
                    df_c = df[df["Centro de Custo"] == c]
                    d_val = df_c[df_c["Tipo"] == "Despesa"]["Valor"].sum()
                    r_val = df_c[df_c["Tipo"] == "Receita"]["Valor"].sum()
                    top_c_cat = df_c[df_c["Tipo"] == "Despesa"].groupby("Categoria")["Valor"].sum().to_dict()
                    resumo_txt += f"- {c}: Despesas R$ {d_val:.2f}, Receitas R$ {r_val:.2f}. Principais categorias: {top_c_cat}\n"

                agent = FinancialAIAgent()
                diagnostico = agent.generate_analysis(resumo_txt)
                st.markdown(diagnostico)

    # Tabela Detalhada de Transações
    st.markdown("---")
    st.subheader("📋 Histórico Completo de Transações")
    col_f1, col_f2 = st.columns([2, 1])
    termo_busca = col_f1.text_input("🔍 Buscar por descrição ou categoria:", "")

    df_exibicao = df.copy()
    if termo_busca:
        df_exibicao = df_exibicao[
            df_exibicao["Descrição"].astype(str).str.contains(termo_busca, case=False, na=False) |
            df_exibicao["Categoria"].astype(str).str.contains(termo_busca, case=False, na=False)
        ]

    # Ordena da mais recente para a mais antiga
    if "Data" in df_exibicao.columns:
        df_exibicao = df_exibicao.sort_values(by=["Data", "Hora"], ascending=False)

    colunas_visiveis = [
        "Data", "Hora", "Centro de Custo", "Tipo", "Valor", "Categoria", "Descrição", "Forma de Pagamento", "Lançado Por", "Origem"
    ]
    cols_existentes = [c for c in colunas_visiveis if c in df_exibicao.columns]

    st.dataframe(
        df_exibicao[cols_existentes].style.format({"Valor": "R$ {:,.2f}".format}),
        use_container_width=True,
        height=400
    )


if __name__ == "__main__":
    main()

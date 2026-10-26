import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from sheets_service import SheetsService, parse_currency_value
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
    .card-box {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.04);
        margin-bottom: 15px;
    }
    .badge-casa {
        background-color: #e8f4fd;
        color: #1976d2;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 12px;
    }
    .badge-consultorio {
        background-color: #e8f8f0;
        color: #2e7d32;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 12px;
    }
    .badge-dcad {
        background-color: #fdebee;
        color: #c62828;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 12px;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30)
def carregar_dados():
    """Carrega transações e cartões com cache de 30 segundos."""
    try:
        service = SheetsService()
        df_tx = service.get_all_transactions()
        df_cartoes = service.get_cartoes_summary()
        return df_tx, df_cartoes, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)


def main():
    # Cabeçalho
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title("💼 Painel de Controle Financeiro Integrado")
        st.caption("Visão em tempo real das finanças: **Casa**, **Consultório** e **D-CAD**.")
    with col_t2:
        if SPREADSHEET_ID:
            st.markdown(
                f"""
                <div style="text-align: right; padding-top: 15px;">
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

    df_raw, df_cartoes, erro = carregar_dados()

    if erro:
        st.error(f"⚠️ Erro ao conectar com o Google Sheets: {erro}")
        st.info("Verifique se o arquivo `credentials.json` e o `SPREADSHEET_ID` foram configurados corretamente.")
        return

    # Filtro de Centro de Custo
    centro_selecionado = st.sidebar.selectbox(
        "Centro de Custo",
        ["Todos (Consolidado)"] + CENTROS_DE_CUSTO
    )

    # Filtro de Usuário (Lançado Por)
    usuario_selecionado = "Todos"
    if not df_raw.empty and "Lançado Por" in df_raw.columns:
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
        data_inicio = df_raw["Data"].min() if (not df_raw.empty and not df_raw["Data"].isna().all()) else hoje
        data_fim = hoje

    # Aplicação dos Filtros em df
    df = df_raw.copy()
    if not df.empty and "Data" in df.columns:
        df = df[(df["Data"] >= pd.to_datetime(data_inicio)) & (df["Data"] <= pd.to_datetime(data_fim))]

    if centro_selecionado != "Todos (Consolidado)":
        df = df[df["Centro de Custo"] == centro_selecionado]

    if usuario_selecionado != "Todos" and "Lançado Por" in df.columns:
        df = df[df["Lançado Por"] == usuario_selecionado]

    # Abas Principais
    tab_visao, tab_cartoes, tab_historico = st.tabs([
        "📊 Visão Geral & Centros de Custo",
        "💳 Controle de Cartões de Crédito",
        "📋 Histórico Completo de Lançamentos"
    ])

    # ==========================================
    # ABA 1: VISÃO GERAL
    # ==========================================
    with tab_visao:
        if df.empty:
            st.info("Nenhuma transação encontrada no período selecionado. Faça lançamentos pelo Telegram!")
        else:
            total_despesas = df[df["Tipo"] == "Despesa"]["Valor"].sum()
            total_receitas = df[df["Tipo"] == "Receita"]["Valor"].sum()
            saldo_liquido = total_receitas - total_despesas
            qtd_transacoes = len(df)

            # Cards de Métricas com formatação precisa de centavos
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🔴 Despesas Totais", f"R$ {total_despesas:,.2f}")
            with col2:
                st.metric("🟢 Receitas Totais", f"R$ {total_receitas:,.2f}")
            with col3:
                delta_color = "normal" if saldo_liquido >= 0 else "inverse"
                st.metric("💰 Saldo Líquido", f"R$ {saldo_liquido:,.2f}", delta=f"R$ {saldo_liquido:,.2f}", delta_color=delta_color)
            with col4:
                st.metric("📝 Lançamentos", f"{qtd_transacoes}")

            st.markdown("---")

            # Gráficos
            col_g1, col_g2 = st.columns([1, 1])

            with col_g1:
                st.subheader("📊 Despesas por Centro de Custo")
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
                    fig_pizza.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=340)
                    st.plotly_chart(fig_pizza, use_container_width=True)
                else:
                    st.info("Nenhuma despesa no período.")

            with col_g2:
                st.subheader("🏷️ Top Categorias")
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
                        height=340
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Sem despesas para listar categorias.")

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
                        height=340
                    )
                    st.plotly_chart(fig_line, use_container_width=True)

            # Módulo IA
            st.markdown("---")
            with st.expander("✨ Gerar Diagnóstico Financeiro Estratégico com IA", expanded=False):
                if st.button("🚀 Analisar Finanças com IA Agora"):
                    with st.spinner("Analisando padrões e centros de custo..."):
                        resumo_txt = f"Período: {periodo_escolhido}\nTotal Despesas: R$ {total_despesas:.2f}\nTotal Receitas: R$ {total_receitas:.2f}\n\n"
                        for c in CENTROS_DE_CUSTO:
                            df_c = df[df["Centro de Custo"] == c]
                            d_val = df_c[df_c["Tipo"] == "Despesa"]["Valor"].sum()
                            r_val = df_c[df_c["Tipo"] == "Receita"]["Valor"].sum()
                            resumo_txt += f"- {c}: Despesas R$ {d_val:.2f}, Receitas R$ {r_val:.2f}\n"

                        agent = FinancialAIAgent()
                        diagnostico = agent.generate_analysis(resumo_txt)
                        st.markdown(diagnostico)

    # ==========================================
    # ABA 2: CONTROLE DE CARTÕES DE CRÉDITO
    # ==========================================
    with tab_cartoes:
        st.subheader("💳 Gestão e Limites dos Cartões de Crédito")
        st.caption("Acompanhe o limite disponível, faturas utilizadas e compras parceladas vinculadas a cada Centro de Custo.")

        if df_cartoes.empty:
            st.warning("Nenhum cartão cadastrado na aba 'Controle de Cartões' da planilha.")
        else:
            # Filtro por Centro de Custo dos Cartões
            df_cards = df_cartoes.copy()
            if centro_selecionado != "Todos (Consolidado)":
                df_cards = df_cards[df_cards["Centro de Custo"] == centro_selecionado]

            # KPIs Globais de Cartões
            tot_limite = df_cards["Limite Total"].sum()
            tot_usado = df_cards["Limite Utilizado"].sum()
            tot_disp = tot_limite - tot_usado
            perc_usado = (tot_usado / tot_limite * 100) if tot_limite > 0 else 0

            kc1, kc2, kc3, kc4 = st.columns(4)
            with kc1:
                st.metric("💳 Limite Total Cadastrado", f"R$ {tot_limite:,.2f}")
            with kc2:
                st.metric("🔴 Limite Comprometido (Faturas)", f"R$ {tot_usado:,.2f}")
            with kc3:
                st.metric("🟢 Limite Total Disponível", f"R$ {tot_disp:,.2f}")
            with kc4:
                st.metric("📊 % de Comprometimento", f"{perc_usado:.1f}%")

            st.markdown("---")

            # Cards Individuais de cada Cartão
            st.markdown("### 📋 Cartões Ativos por Centro de Custo")
            cols_grid = st.columns(3)

            badge_classes = {
                "Casa": "badge-casa",
                "Consultório": "badge-consultorio",
                "D-CAD": "badge-dcad"
            }

            for idx, (_, row) in enumerate(df_cards.iterrows()):
                col_atual = cols_grid[idx % 3]
                c_nome = row["Cartão"]
                c_centro = row["Centro de Custo"]
                c_banco = row.get("Banco / Emissor", "Banco")
                c_limite = float(row.get("Limite Total", 0.0))
                c_usado = float(row.get("Limite Utilizado", 0.0))
                c_disp = c_limite - c_usado
                c_fech = row.get("Dia Fechamento", "-")
                c_venc = row.get("Dia Vencimento", "-")
                c_badge = badge_classes.get(c_centro, "badge-casa")

                ratio = min(max(c_usado / c_limite, 0.0), 1.0) if c_limite > 0 else 0.0

                with col_atual:
                    st.markdown(
                        f"""
                        <div class="card-box">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 18px; font-weight: bold;">💳 {c_nome}</span>
                                <span class="{c_badge}">{c_centro}</span>
                            </div>
                            <div style="color: #666; font-size: 13px; margin-bottom: 12px;">Emissor: {c_banco} | Venc: dia {c_venc} (Fecha dia {c_fech})</div>
                            <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 4px;">
                                <span>Utilizado: <b>R$ {c_usado:,.2f}</b></span>
                                <span>Disponível: <b style="color: #2e7d32;">R$ {c_disp:,.2f}</b></span>
                            </div>
                            <div style="font-size: 12px; color: #888; margin-bottom: 6px;">Limite Total: R$ {c_limite:,.2f} ({ratio*100:.1f}% usado)</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.progress(ratio)

            # Tabela de Compras Parceladas Ativas
            st.markdown("---")
            st.markdown("### 🔢 Compras Parceladas Registradas")
            if not df_raw.empty and "Parcelas" in df_raw.columns:
                df_parc = df_raw[
                    (df_raw["Parcelas"].notna()) &
                    (df_raw["Parcelas"] != "À vista") &
                    (df_raw["Parcelas"] != "N/A") &
                    (df_raw["Parcelas"] != "")
                ]

                if centro_selecionado != "Todos (Consolidado)":
                    df_parc = df_parc[df_parc["Centro de Custo"] == centro_selecionado]

                if not df_parc.empty:
                    cols_parc = ["Data", "Cartão", "Descrição", "Valor", "Parcelas", "Centro de Custo", "Lançado Por"]
                    exist_parc = [c for c in cols_parc if c in df_parc.columns]
                    st.dataframe(
                        df_parc[exist_parc].style.format({"Valor": "R$ {:,.2f}".format}),
                        use_container_width=True
                    )
                else:
                    st.info("Nenhuma compra parcelada registrada no momento.")
            else:
                st.info("Nenhuma compra parcelada registrada.")

    # ==========================================
    # ABA 3: HISTÓRICO DE LANÇAMENTOS
    # ==========================================
    with tab_historico:
        st.subheader("📋 Histórico Completo de Transações")
        if df.empty:
            st.info("Nenhum lançamento no período.")
        else:
            col_f1, col_f2 = st.columns([2, 1])
            termo_busca = col_f1.text_input("🔍 Buscar por descrição, categoria ou cartão:", "")

            df_exibicao = df.copy()
            if termo_busca:
                mask = (
                    df_exibicao["Descrição"].astype(str).str.contains(termo_busca, case=False, na=False) |
                    df_exibicao["Categoria"].astype(str).str.contains(termo_busca, case=False, na=False) |
                    df_exibicao["Cartão"].astype(str).str.contains(termo_busca, case=False, na=False)
                )
                df_exibicao = df_exibicao[mask]

            if "Data" in df_exibicao.columns:
                df_exibicao = df_exibicao.sort_values(by=["Data", "Hora"], ascending=False)

            colunas_visiveis = [
                "Data", "Hora", "Centro de Custo", "Tipo", "Valor", "Categoria",
                "Descrição", "Forma de Pagamento", "Cartão", "Parcelas", "Lançado Por", "Origem"
            ]
            cols_existentes = [c for c in colunas_visiveis if c in df_exibicao.columns]

            st.dataframe(
                df_exibicao[cols_existentes].style.format({"Valor": "R$ {:,.2f}".format}),
                use_container_width=True,
                height=450
            )


if __name__ == "__main__":
    main()

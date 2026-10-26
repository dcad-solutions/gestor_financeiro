import traceback
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
        tb = traceback.format_exc()
        return pd.DataFrame(), pd.DataFrame(), f"{e}\n\n{tb}"


def main():
    # Identifica o SPREADSHEET_ID (da config ou dos secrets do Streamlit Cloud)
    sheet_link_id = SPREADSHEET_ID
    try:
        if hasattr(st, "secrets") and "SPREADSHEET_ID" in st.secrets:
            sheet_link_id = st.secrets["SPREADSHEET_ID"]
    except Exception:
        pass

    # Cabeçalho
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title("💼 Painel de Controle Financeiro Integrado")
        st.caption("Visão em tempo real das finanças: **Casa**, **Consultório** e **D-CAD**.")
    with col_t2:
        if sheet_link_id:
            st.markdown(
                f"""
                <div style="text-align: right; padding-top: 15px;">
                    <a href="https://docs.google.com/spreadsheets/d/{sheet_link_id}/edit" target="_blank" 
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
        st.error(f"⚠️ Erro ao conectar com o Google Sheets:\n```\n{erro}\n```")
        st.info("Verifique se as credenciais do Google Cloud (`gcp_service_account`) e o `SPREADSHEET_ID` foram configurados corretamente nos Secrets do Streamlit Cloud.")
        return

    # Filtro de Centro de Custo
    centro_selecionado = st.sidebar.selectbox(
        "Centro de Custo",
        ["Todos (Consolidado)"] + CENTROS_DE_CUSTO
    )

    # Filtro de Usuário (Lançado Por)
    usuario_selecionado = "Todos"
    if not df_raw.empty and "Lançado Por" in df_raw.columns:
        usuarios = [str(u).strip() for u in df_raw["Lançado Por"].dropna().unique() if str(u).strip() and str(u).strip() != "nan"]
        if len(usuarios) > 1:
            usuario_selecionado = st.sidebar.selectbox("👤 Lançado Por", ["Todos"] + sorted(usuarios))

    # Filtro de Período
    opcoes_periodo = ["Mês Atual", "Últimos 30 Dias", "Últimos 90 Dias", "Ano Atual", "Todo o Período", "Personalizado"]
    periodo_escolhido = st.sidebar.selectbox("Período de Tempo", opcoes_periodo)

    hoje = datetime.now()
    fim_do_dia = datetime.combine(hoje.date(), datetime.max.time())
    if periodo_escolhido == "Mês Atual":
        data_inicio = datetime(hoje.year, hoje.month, 1)
        data_fim = fim_do_dia
    elif periodo_escolhido == "Últimos 30 Dias":
        data_inicio = hoje - timedelta(days=30)
        data_fim = fim_do_dia
    elif periodo_escolhido == "Últimos 90 Dias":
        data_inicio = hoje - timedelta(days=90)
        data_fim = fim_do_dia
    elif periodo_escolhido == "Ano Atual":
        data_inicio = datetime(hoje.year, 1, 1)
        data_fim = fim_do_dia
    elif periodo_escolhido == "Personalizado":
        col_d1, col_d2 = st.sidebar.columns(2)
        d_ini = col_d1.date_input("Início", (hoje - timedelta(days=30)).date())
        d_fim = col_d2.date_input("Fim", hoje.date())
        data_inicio = datetime.combine(d_ini, datetime.min.time())
        data_fim = datetime.combine(d_fim, datetime.max.time())
    else:
        if not df_raw.empty and "Data" in df_raw.columns and not df_raw["Data"].isna().all():
            min_data = df_raw["Data"].dropna().min()
            data_inicio = min_data.to_pydatetime() if hasattr(min_data, "to_pydatetime") else hoje
        else:
            data_inicio = hoje
        data_fim = fim_do_dia

    # Aplicação dos Filtros em df
    df = df_raw.copy()
    if not df.empty and "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        df = df[(df["Data"].isna()) | ((df["Data"] >= pd.to_datetime(data_inicio)) & (df["Data"] <= pd.to_datetime(data_fim)))]

    if not df.empty and "Centro de Custo" in df.columns and centro_selecionado != "Todos (Consolidado)":
        df = df[df["Centro de Custo"] == centro_selecionado]

    if not df.empty and "Lançado Por" in df.columns and usuario_selecionado != "Todos":
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
        if df.empty or "Tipo" not in df.columns or "Valor" not in df.columns:
            st.info("Nenhuma transação encontrada no período selecionado. Faça lançamentos pelo Telegram!")
        else:
            # Garante valores numéricos
            df["Valor"] = pd.to_numeric(df["Valor"].apply(parse_currency_value), errors="coerce").fillna(0.0)

            total_despesas = float(df[df["Tipo"] == "Despesa"]["Valor"].sum())
            total_receitas = float(df[df["Tipo"] == "Receita"]["Valor"].sum())
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
                st.metric("📝 Lançamentos", f"{qtd_transacoes}")

            st.markdown("---")

            # Gráficos
            col_g1, col_g2 = st.columns([1, 1])

            with col_g1:
                st.subheader("📊 Despesas por Centro de Custo")
                df_desp = df[df["Tipo"] == "Despesa"]
                if not df_desp.empty and "Centro de Custo" in df_desp.columns:
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
                if not df_desp.empty and "Categoria" in df_desp.columns:
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
            if not df.empty and "Data" in df.columns and "Tipo" in df.columns:
                df_timeline = df.copy()
                df_timeline["Data_Valida"] = pd.to_datetime(df_timeline["Data"], errors="coerce")
                df_timeline = df_timeline.dropna(subset=["Data_Valida"])
                if not df_timeline.empty:
                    df_timeline["Data_Formatada"] = df_timeline["Data_Valida"].dt.strftime("%Y-%m-%d")
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
                    else:
                        st.info("Sem despesas para exibir no gráfico temporal.")

            # Módulo IA
            st.markdown("---")
            with st.expander("✨ Gerar Diagnóstico Financeiro Estratégico com IA", expanded=False):
                if st.button("🚀 Analisar Finanças com IA Agora"):
                    with st.spinner("Analisando padrões e centros de custo..."):
                        resumo_txt = f"Período: {periodo_escolhido}\nTotal Despesas: R$ {total_despesas:.2f}\nTotal Receitas: R$ {total_receitas:.2f}\n\n"
                        for c in CENTROS_DE_CUSTO:
                            df_c = df[df["Centro de Custo"] == c]
                            d_val = df_c[df_c["Tipo"] == "Despesa"]["Valor"].sum() if not df_c.empty else 0.0
                            r_val = df_c[df_c["Tipo"] == "Receita"]["Valor"].sum() if not df_c.empty else 0.0
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

        if df_cartoes.empty or "Cartão" not in df_cartoes.columns:
            st.warning("Nenhum cartão cadastrado na aba 'Controle de Cartões' da planilha.")
        else:
            # Filtro por Centro de Custo dos Cartões e remoção de cartões vazios
            df_cards = df_cartoes.copy()
            df_cards = df_cards[df_cards["Cartão"].astype(str).str.strip().ne("") & df_cards["Cartão"].notna()]

            if df_cards.empty:
                st.warning("Nenhum cartão ativo cadastrado.")
            else:
                for col in ["Limite Total", "Limite Utilizado", "Limite Disponível"]:
                    if col in df_cards.columns:
                        df_cards[col] = df_cards[col].apply(parse_currency_value)
                    else:
                        df_cards[col] = 0.0

                if centro_selecionado != "Todos (Consolidado)" and "Centro de Custo" in df_cards.columns:
                    df_cards = df_cards[df_cards["Centro de Custo"] == centro_selecionado]

                # KPIs Globais de Cartões
                tot_limite = float(df_cards["Limite Total"].sum()) if not df_cards.empty else 0.0
                tot_usado = float(df_cards["Limite Utilizado"].sum()) if not df_cards.empty else 0.0
                tot_disp = float(df_cards["Limite Disponível"].sum()) if not df_cards.empty else 0.0
                perc_usado = (tot_usado / tot_limite * 100) if tot_limite > 0 else 0.0

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
                    c_nome = str(row.get("Cartão", "")).strip()
                    c_centro = str(row.get("Centro de Custo", "Casa")).strip()
                    c_banco = str(row.get("Banco / Emissor", "Banco")).strip()
                    c_limite = float(parse_currency_value(row.get("Limite Total", 0.0)))
                    c_usado = float(parse_currency_value(row.get("Limite Utilizado", 0.0)))
                    c_disp = max(c_limite - c_usado, 0.0)
                    c_fech = row.get("Dia Fechamento", "-")
                    c_venc = row.get("Dia Vencimento", "-")
                    c_badge = badge_classes.get(c_centro, "badge-casa")

                    ratio = (c_usado / c_limite) if c_limite > 0 else 0.0
                    if pd.isna(ratio) or ratio < 0.0:
                        ratio = 0.0
                    elif ratio > 1.0:
                        ratio = 1.0

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
                    df_parc = df_raw.copy()
                    df_parc["Parcelas_Str"] = df_parc["Parcelas"].astype(str).str.strip().str.lower()
                    df_parc = df_parc[
                        df_parc["Parcelas_Str"].notna() &
                        (~df_parc["Parcelas_Str"].isin(["", "à vista", "a vista", "n/a", "none", "1", "1x", "nan"]))
                    ]

                    if centro_selecionado != "Todos (Consolidado)" and "Centro de Custo" in df_parc.columns:
                        df_parc = df_parc[df_parc["Centro de Custo"] == centro_selecionado]

                    if not df_parc.empty:
                        cols_parc = ["Data", "Cartão", "Descrição", "Valor", "Parcelas", "Centro de Custo", "Lançado Por"]
                        exist_parc = [c for c in cols_parc if c in df_parc.columns]
                        df_parc_display = df_parc[exist_parc].copy()
                        if "Valor" in df_parc_display.columns:
                            df_parc_display["Valor"] = df_parc_display["Valor"].apply(
                                lambda v: f"R$ {parse_currency_value(v):,.2f}"
                            )
                        if "Data" in df_parc_display.columns:
                            df_parc_display["Data"] = pd.to_datetime(df_parc_display["Data"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
                        st.dataframe(df_parc_display, use_container_width=True)
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
            df_disp = df_exibicao[cols_existentes].copy()

            if "Valor" in df_disp.columns:
                df_disp["Valor"] = df_disp["Valor"].apply(
                    lambda v: f"R$ {parse_currency_value(v):,.2f}"
                )
            if "Data" in df_disp.columns:
                df_disp["Data"] = pd.to_datetime(df_disp["Data"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")

            st.dataframe(
                df_disp,
                use_container_width=True,
                height=450
            )


if __name__ == "__main__":
    main()

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    SPREADSHEET_ID,
    CENTROS_DE_CUSTO,
    CATEGORIAS_PADRAO,
    CARTOES_PADRAO
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

COLUMNS = [
    "ID",
    "Data",
    "Hora",
    "Centro de Custo",
    "Tipo",
    "Valor",
    "Categoria",
    "Descrição",
    "Forma de Pagamento",
    "Cartão",
    "Parcelas",
    "Lançado Por",
    "Origem"
]

COLUMNS_CARTOES = [
    "Cartão",
    "Centro de Custo",
    "Banco / Emissor",
    "Limite Total",
    "Limite Utilizado",
    "Limite Disponível",
    "Compras Parceladas",
    "Dia Fechamento",
    "Dia Vencimento",
    "Status"
]


def parse_currency_value(val) -> float:
    """
    Converte valor monetário de forma robusta e precisa,
    garantindo que centavos não sejam multiplicados por 100 ou 1000.
    """
    if pd.isna(val) or val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    val_str = str(val).strip()
    val_str = val_str.replace("R$", "").replace("r$", "").strip()

    if not val_str:
        return 0.0

    # Se tiver ambos '.' e ',', padrão brasileiro clássico: 1.250,50
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        # Padrão brasileiro sem separador de milhar: 35,50
        val_str = val_str.replace(",", ".")
    elif "." in val_str:
        # Se tiver apenas '.', verifica se é decimal (35.50 / 35.5) ou milhar (1.000)
        parts = val_str.split(".")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            # Decimal normal (ex: 35.50) -> mantém o ponto
            pass
        elif len(parts) == 2 and len(parts[1]) == 3 and float(parts[0]) > 0:
            # Milhar sem centavos (ex: 1.000) -> remove o ponto
            val_str = val_str.replace(".", "")
        else:
            # Múltiplos pontos de milhar: 1.000.000
            val_str = val_str.replace(".", "")

    try:
        return float(val_str)
    except ValueError:
        return 0.0


class SheetsService:
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self._authenticate()

    def _authenticate(self):
        """Autentica com a conta de serviço do Google Cloud (suporta arquivo local e Streamlit Cloud Secrets)."""
        credentials = None

        # 1. Tenta carregar do Streamlit Secrets (quando hospedado na nuvem do Streamlit)
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
                secret_dict = dict(st.secrets["gcp_service_account"])
                credentials = Credentials.from_service_account_info(
                    secret_dict, scopes=SCOPES
                )
        except Exception:
            pass

        # 2. Se não estiver no Streamlit Secrets, usa o arquivo credentials.json local
        if not credentials:
            cred_path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
            if not cred_path.exists():
                raise FileNotFoundError(
                    f"Arquivo de credenciais não encontrado: {GOOGLE_SERVICE_ACCOUNT_FILE}. "
                    "Baixe o JSON da Service Account do Google Cloud e salve neste caminho."
                )
            credentials = Credentials.from_service_account_file(
                str(cred_path), scopes=SCOPES
            )

        self.client = gspread.authorize(credentials)

        sheet_id = SPREADSHEET_ID
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "SPREADSHEET_ID" in st.secrets:
                sheet_id = st.secrets["SPREADSHEET_ID"]
        except Exception:
            pass

        if sheet_id:
            self.spreadsheet = self.client.open_by_key(sheet_id)

    def ensure_structure(self):
        """Inicializa as abas e cabeçalhos na planilha caso ainda não existam."""
        if not self.spreadsheet:
            raise ValueError("SPREADSHEET_ID não está configurado.")

        existing_sheets = [s.title for s in self.spreadsheet.worksheets()]

        # 1. Cria ou valida aba principal 'Todas as Transações'
        if "Todas as Transações" not in existing_sheets:
            master_sheet = self.spreadsheet.add_worksheet(
                title="Todas as Transações", rows=1000, cols=len(COLUMNS)
            )
            master_sheet.append_row(COLUMNS)
        else:
            master_sheet = self.spreadsheet.worksheet("Todas as Transações")
            master_sheet.update("A1:M1", [COLUMNS])

        # 2. Cria abas específicas para cada Centro de Custo usando fórmula automática FILTER (A2:M)
        for centro in CENTROS_DE_CUSTO:
            if centro not in existing_sheets:
                sub_sheet = self.spreadsheet.add_worksheet(title=centro, rows=500, cols=len(COLUMNS))
                sub_sheet.append_row(COLUMNS)
                formula = f"=IFERROR(FILTER('Todas as Transações'!A2:M, 'Todas as Transações'!D2:D = \"{centro}\"), \"Nenhum registro para {centro}\")"
                sub_sheet.update_acell("A2", formula)
            else:
                sub_sheet = self.spreadsheet.worksheet(centro)
                sub_sheet.update("A1:M1", [COLUMNS])
                formula = f"=IFERROR(FILTER('Todas as Transações'!A2:M, 'Todas as Transações'!D2:D = \"{centro}\"), \"Nenhum registro para {centro}\")"
                sub_sheet.update_acell("A2", formula)

        # 3. Cria ou valida aba 'Controle de Cartões'
        if "Controle de Cartões" not in existing_sheets:
            cartoes_sheet = self.spreadsheet.add_worksheet(
                title="Controle de Cartões", rows=100, cols=len(COLUMNS_CARTOES)
            )
            cartoes_sheet.append_row(COLUMNS_CARTOES)
            for idx, c in enumerate(CARTOES_PADRAO, start=2):
                linha = [
                    c["cartao"],
                    c["centro_custo"],
                    c["banco"],
                    float(c["limite_total"]),
                    f"=IFERROR(SUMIFS('Todas as Transações'!$F$2:$F, 'Todas as Transações'!$J$2:$J, A{idx}, 'Todas as Transações'!$E$2:$E, \"Despesa\"), 0)",
                    f"=D{idx}-E{idx}",
                    f"=COUNTIFS('Todas as Transações'!$J$2:$J, A{idx}, 'Todas as Transações'!$K$2:$K, \"<>À vista\", 'Todas as Transações'!$K$2:$K, \"<>\")",
                    c["dia_fechamento"],
                    c["dia_vencimento"],
                    c["status"]
                ]
                cartoes_sheet.append_row(linha, value_input_option="USER_ENTERED")
        else:
            cartoes_sheet = self.spreadsheet.worksheet("Controle de Cartões")
            cartoes_sheet.update("A1:J1", [COLUMNS_CARTOES])
            # Se a aba estiver vazia além do cabeçalho, popula os cartões padrão
            if len(cartoes_sheet.get_all_values()) <= 1:
                for idx, c in enumerate(CARTOES_PADRAO, start=2):
                    linha = [
                        c["cartao"],
                        c["centro_custo"],
                        c["banco"],
                        float(c["limite_total"]),
                        f"=IFERROR(SUMIFS('Todas as Transações'!$F$2:$F, 'Todas as Transações'!$J$2:$J, A{idx}, 'Todas as Transações'!$E$2:$E, \"Despesa\"), 0)",
                        f"=D{idx}-E{idx}",
                        f"=COUNTIFS('Todas as Transações'!$J$2:$J, A{idx}, 'Todas as Transações'!$K$2:$K, \"<>À vista\", 'Todas as Transações'!$K$2:$K, \"<>\")",
                        c["dia_fechamento"],
                        c["dia_vencimento"],
                        c["status"]
                    ]
                    cartoes_sheet.append_row(linha, value_input_option="USER_ENTERED")

        # Remove a aba padrão 'Sheet1' ou 'Página1' se for nova
        for default_title in ["Sheet1", "Página1"]:
            if default_title in existing_sheets and len(self.spreadsheet.worksheets()) > 1:
                try:
                    self.spreadsheet.del_worksheet(self.spreadsheet.worksheet(default_title))
                except Exception:
                    pass

    def add_transaction(
        self,
        centro_custo: str,
        tipo: str,
        valor: float,
        categoria: str,
        descricao: str,
        forma_pagamento: str = "Não especificado",
        cartao: str = "N/A",
        parcelas: str = "À vista",
        lancado_por: str = "Desconhecido",
        origem: str = "Telegram",
        data_personalizada: Optional[str] = None
    ) -> Dict:
        """Adiciona uma transação na aba mestre da planilha."""
        if not self.spreadsheet:
            raise ValueError("Planilha não conectada.")

        agora = datetime.now()
        data_str = data_personalizada or agora.strftime("%Y-%m-%d")
        hora_str = agora.strftime("%H:%M:%S")
        transacao_id = str(uuid.uuid4())[:8].upper()

        # Garante padronização do centro de custo
        centro_formatado = centro_custo.strip()
        if centro_formatado not in CENTROS_DE_CUSTO:
            centro_lower = centro_formatado.lower()
            if "casa" in centro_lower:
                centro_formatado = "Casa"
            elif "consult" in centro_lower:
                centro_formatado = "Consultório"
            elif "cad" in centro_lower or "d-cad" in centro_lower:
                centro_formatado = "D-CAD"
            else:
                centro_formatado = "Casa"

        tipo_formatado = "Receita" if tipo.lower() in ["receita", "entrada", "ganho"] else "Despesa"
        valor_float = round(float(valor), 2)

        # Ajusta cartão e parcelas
        cartao_formatado = cartao.strip() if (cartao and cartao != "None") else "N/A"
        parcelas_formatado = parcelas.strip() if (parcelas and parcelas != "None") else "À vista"

        linha = [
            transacao_id,
            data_str,
            hora_str,
            centro_formatado,
            tipo_formatado,
            valor_float,
            categoria.strip(),
            descricao.strip(),
            forma_pagamento.strip(),
            cartao_formatado,
            parcelas_formatado,
            lancado_por.strip(),
            origem.strip()
        ]

        master_sheet = self.spreadsheet.worksheet("Todas as Transações")
        master_sheet.append_row(linha, value_input_option="USER_ENTERED")

        return {
            "id": transacao_id,
            "data": data_str,
            "centro_custo": centro_formatado,
            "tipo": tipo_formatado,
            "valor": valor_float,
            "categoria": categoria,
            "descricao": descricao,
            "forma_pagamento": forma_pagamento,
            "cartao": cartao_formatado,
            "parcelas": parcelas_formatado,
            "lancado_por": lancado_por
        }

    def get_all_transactions(self) -> pd.DataFrame:
        """Carrega todas as transações em um DataFrame do Pandas com tipagem correta."""
        if not self.spreadsheet:
            return pd.DataFrame(columns=COLUMNS)

        master_sheet = self.spreadsheet.worksheet("Todas as Transações")
        dados = master_sheet.get_all_records()
        if not dados:
            return pd.DataFrame(columns=COLUMNS)

        df = pd.DataFrame(dados)

        # Converte valores com a função robusta parse_currency_value
        if "Valor" in df.columns:
            df["Valor"] = df["Valor"].apply(parse_currency_value)

        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

        return df

    def get_cartoes_summary(self) -> pd.DataFrame:
        """Carrega e calcula o resumo de cartões de crédito da aba 'Controle de Cartões'."""
        if not self.spreadsheet:
            return pd.DataFrame(columns=COLUMNS_CARTOES)

        try:
            ws = self.spreadsheet.worksheet("Controle de Cartões")
            dados = ws.get_all_records()
            if not dados:
                return pd.DataFrame(columns=COLUMNS_CARTOES)

            df = pd.DataFrame(dados)
            for col in ["Limite Total", "Limite Utilizado", "Limite Disponível"]:
                if col in df.columns:
                    df[col] = df[col].apply(parse_currency_value)

            return df
        except Exception as e:
            logger.error(f"Erro ao buscar cartões: {e}")
            return pd.DataFrame(columns=COLUMNS_CARTOES)

    def get_monthly_summary(self, ano: int, mes: int) -> Dict:
        """Retorna resumo de despesas e receitas do mês por centro de custo."""
        df = self.get_all_transactions()
        if df.empty or "Data" not in df.columns:
            return {c: {"despesas": 0.0, "receitas": 0.0, "saldo": 0.0} for c in CENTROS_DE_CUSTO}

        df_mes = df[(df["Data"].dt.year == ano) & (df["Data"].dt.month == mes)]

        resumo = {}
        for centro in CENTROS_DE_CUSTO:
            df_c = df_mes[df_mes["Centro de Custo"] == centro]
            despesas = df_c[df_c["Tipo"] == "Despesa"]["Valor"].sum()
            receitas = df_c[df_c["Tipo"] == "Receita"]["Valor"].sum()
            resumo[centro] = {
                "despesas": float(despesas),
                "receitas": float(receitas),
                "saldo": float(receitas - despesas)
            }

        return resumo

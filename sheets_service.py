import uuid
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
    CATEGORIAS_PADRAO
)

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
    "Origem"
]

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
            first_row = master_sheet.row_values(1)
            if not first_row:
                master_sheet.append_row(COLUMNS)

        # 2. Cria abas específicas para cada Centro de Custo usando fórmula automática FILTER
        for centro in CENTROS_DE_CUSTO:
            if centro not in existing_sheets:
                sub_sheet = self.spreadsheet.add_worksheet(title=centro, rows=500, cols=len(COLUMNS))
                # Insere o cabeçalho
                sub_sheet.append_row(COLUMNS)
                # Na célula A2, adiciona a fórmula de filtro dinâmico
                formula = f"=IFERROR(FILTER('Todas as Transações'!A2:J, 'Todas as Transações'!D2:D = \"{centro}\"), \"Nenhum registro para {centro}\")"
                sub_sheet.update_acell("A2", formula)

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

        # Garante padronização
        centro_formatado = centro_custo.strip()
        if centro_formatado not in CENTROS_DE_CUSTO:
            # Fallback tolerante
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

        linha = [
            transacao_id,
            data_str,
            hora_str,
            centro_formatado,
            tipo_formatado,
            float(valor),
            categoria.strip(),
            descricao.strip(),
            forma_pagamento.strip(),
            origem.strip()
        ]

        master_sheet = self.spreadsheet.worksheet("Todas as Transações")
        master_sheet.append_row(linha, value_input_option="USER_ENTERED")

        return {
            "id": transacao_id,
            "data": data_str,
            "centro_custo": centro_formatado,
            "tipo": tipo_formatado,
            "valor": float(valor),
            "categoria": categoria,
            "descricao": descricao,
            "forma_pagamento": forma_pagamento
        }

    def get_all_transactions(self) -> pd.DataFrame:
        """Carrega todas as transações em um DataFrame do Pandas."""
        if not self.spreadsheet:
            return pd.DataFrame(columns=COLUMNS)

        master_sheet = self.spreadsheet.worksheet("Todas as Transações")
        dados = master_sheet.get_all_records()
        if not dados:
            return pd.DataFrame(columns=COLUMNS)

        df = pd.DataFrame(dados)
        # Converte tipos
        if "Valor" in df.columns:
            # Limpa caso venha formatado como moeda
            df["Valor"] = (
                df["Valor"]
                .astype(str)
                .str.replace("R$", "", regex=False)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)

        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

        return df

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

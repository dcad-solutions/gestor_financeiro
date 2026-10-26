import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_USER = int(os.getenv("ADMIN_TELEGRAM_USER", "8589007485"))
ALLOWED_USERS_FILE = BASE_DIR / "allowed_users.json"
ALLOWED_TELEGRAM_USERS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_TELEGRAM_USERS", "").split(",")
    if uid.strip().isdigit()
]

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Google Sheets
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", str(BASE_DIR / "credentials.json")
)

# URL do Dashboard Streamlit na Nuvem (Streamlit Cloud)
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://gestor-dcad.streamlit.app")

# Centros de Custo suportados
CENTROS_DE_CUSTO = ["Casa", "Consultório", "D-CAD"]

# Categorias sugeridas por centro de custo para padronização
CATEGORIAS_PADRAO = {
    "Casa": [
        "Alimentação / Supermercado",
        "Moradia / Contas (Água/Luz/Internet)",
        "Lazer / Restaurantes",
        "Saúde / Farmácia",
        "Transporte / Combustível",
        "Educação / Cursos",
        "Vestuário / Compras",
        "Outros Pessoal"
    ],
    "Consultório": [
        "Insumos / Materiais Clínicos",
        "Aluguel / Condomínio do Consultório",
        "Contas / Serviços (Energia/Telefone/Limpeza)",
        "Equipamentos / Manutenção",
        "Equipe / Secretária / Pró-labore",
        "Taxas / CRO / Licenças / Alvarás",
        "Marketing / Divulgação",
        "Outros Consultório"
    ],
    "D-CAD": [
        "Softwares / Licenças CAD/CAM",
        "Maquinário / Peças / Manutenção",
        "Servidores / Nuvem / Infraestrutura",
        "Materiais de Produção / Fresagem",
        "Impostos / Contabilidade PJ",
        "Honorários / Equipe Técnica",
        "Vendas / Logística",
        "Outros D-CAD"
    ]
}

# Cartões de Crédito pré-cadastrados por Centro de Custo
# Você pode alterar limites e nomes na aba 'Controle de Cartões' da planilha
CARTOES_PADRAO = [
    {
        "cartao": "Nubank Casa",
        "centro_custo": "Casa",
        "banco": "Nubank",
        "limite_total": 10000.0,
        "dia_fechamento": 3,
        "dia_vencimento": 10,
        "status": "Ativo"
    },
    {
        "cartao": "Itaú Casa",
        "centro_custo": "Casa",
        "banco": "Itaú",
        "limite_total": 15000.0,
        "dia_fechamento": 8,
        "dia_vencimento": 15,
        "status": "Ativo"
    },
    {
        "cartao": "Inter Consultório",
        "centro_custo": "Consultório",
        "banco": "Banco Inter",
        "limite_total": 20000.0,
        "dia_fechamento": 12,
        "dia_vencimento": 20,
        "status": "Ativo"
    },
    {
        "cartao": "Santander Consultório",
        "centro_custo": "Consultório",
        "banco": "Santander",
        "limite_total": 25000.0,
        "dia_fechamento": 28,
        "dia_vencimento": 5,
        "status": "Ativo"
    },
    {
        "cartao": "Bradesco D-CAD PJ",
        "centro_custo": "D-CAD",
        "banco": "Bradesco",
        "limite_total": 30000.0,
        "dia_fechamento": 2,
        "dia_vencimento": 10,
        "status": "Ativo"
    },
    {
        "cartao": "C6 Bank D-CAD PJ",
        "centro_custo": "D-CAD",
        "banco": "C6 Bank",
        "limite_total": 15000.0,
        "dia_fechamento": 18,
        "dia_vencimento": 25,
        "status": "Ativo"
    }
]

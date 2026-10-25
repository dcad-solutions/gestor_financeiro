import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
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

# URL do Dashboard Streamlit (utiliza o IP local da máquina para permitir acesso via celular)
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://192.168.0.60:8501")

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

"""
Script utilitário para validar as credenciais e inicializar a estrutura
de abas e cabeçalhos na planilha do Google Sheets.
"""
import sys
from sheets_service import SheetsService
from config import SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_FILE

def main():
    print("=" * 60)
    print("🛠️  INICIALIZADOR DO GOOGLE SHEETS - GESTOR FINANCEIRO")
    print("=" * 60)

    if not SPREADSHEET_ID:
        print("❌ ERRO: SPREADSHEET_ID não está configurado no arquivo .env.")
        print("   Crie uma planilha no Google Sheets e cole o ID dela no .env.")
        sys.exit(1)

    print(f"📄 Planilha ID: {SPREADSHEET_ID}")
    print(f"🔑 Arquivo de credenciais: {GOOGLE_SERVICE_ACCOUNT_FILE}")
    print("\n⏳ Conectando ao Google Sheets...")

    try:
        service = SheetsService()
        print("✅ Autenticação realizada com sucesso!")
        print("⏳ Criando/verificando abas ('Todas as Transações', 'Casa', 'Consultório', 'D-CAD')...")
        service.ensure_structure()
        print("✅ Estrutura de abas configurada com sucesso!")
        print("\n✨ Tudo pronto! O bot e o dashboard já podem ler e escrever nesta planilha.")
    except Exception as e:
        print(f"\n❌ Falha na conexão: {e}")
        print("\nDicas para solucionar:")
        print("1. Verifique se o arquivo credentials.json está na pasta do projeto.")
        print("2. Lembre-se de abrir a sua planilha no Google Sheets, clicar em 'Compartilhar' e adicionar o e-mail da Service Account (ex: seu-bot@projeto.iam.gserviceaccount.com) com permissão de 'Editor'.")
        sys.exit(1)

if __name__ == "__main__":
    main()

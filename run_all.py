"""
Script unificado para iniciar simultaneamente:
1. O Bot do Telegram (processando mensagens, áudios e comprovantes)
2. O Dashboard Interativo em Streamlit (acessível no navegador na porta 8501)
"""
import subprocess
import sys
import os
import signal
import time

def main():
    print("=" * 60)
    print("🚀 INICIANDO GESTOR FINANCEIRO (BOT TELEGRAM + DASHBOARD)")
    print("=" * 60)

    # 1. Inicia o Bot do Telegram
    print("🤖 Iniciando Bot do Telegram...")
    bot_process = subprocess.Popen([sys.executable, "bot.py"])

    # 2. Inicia o Dashboard Streamlit
    print("📊 Iniciando Dashboard Streamlit na porta 8501...")
    dashboard_process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "dashboard.py",
        "--server.port=8501",
        "--server.headless=true"
    ])

    print("\n✅ Ambos os serviços estão em execução!")
    print("👉 Dashboard disponível em: http://localhost:8501 (ou no IP do seu servidor na rede local)")
    print("👉 Bot aguardando mensagens no Telegram.")
    print("\nPressione Ctrl + C para encerrar ambos os serviços.\n")

    def shutdown(signum, frame):
        print("\n🛑 Encerrando serviços...")
        bot_process.terminate()
        dashboard_process.terminate()
        bot_process.wait()
        dashboard_process.wait()
        print("👋 Todos os serviços finalizados com segurança.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Mantém o processo principal vivo monitorando os subprocessos
    while True:
        time.sleep(2)
        if bot_process.poll() is not None:
            print("⚠️ O processo do Bot encerrou inesperadamente.")
            break
        if dashboard_process.poll() is not None:
            print("⚠️ O processo do Dashboard encerrou inesperadamente.")
            break

if __name__ == "__main__":
    main()

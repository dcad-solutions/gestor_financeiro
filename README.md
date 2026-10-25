# 💼 Gestor Financeiro Inteligente via Telegram & Google Sheets

Agente financeiro com inteligência artificial para controle financeiro consolidado e separado por 3 Centros de Custo:
- 🏠 **Casa** (Finanças pessoais, família, contas de casa)
- 🩺 **Consultório** (Despesas clínicas, insumos de saúde, secretária, aluguel)
- 💻 **D-CAD** (Licenças de software CAD/CAM, maquinário, infraestrutura)

Os dados são alimentados em tempo real pelo **Telegram** (por texto livre, mensagem de áudio ou foto de comprovante) e sincronizados imediatamente em planilhas do **Google Sheets**, com um **Dashboard Interativo em Streamlit** e diagnósticos estratégicos gerados por IA.

---

## 🏗️ Como o Sistema Funciona

```
[ Telegram ] ──────────► [ Agente IA (Gemini) ] ──────────► [ Google Sheets ]
(Texto / Áudio / Foto)    (Extrai valor, centro,              (Todas as Transações,
                           categoria e tipo)                   Casa, Consultório, D-CAD)
                                                                     │
                                                                     ▼
                                                          [ Dashboard Streamlit ]
                                                          (Gráficos, KPIs, Diagnóstico IA)
```

---

## 🚀 Passo a Passo de Configuração

### 1. Criar o Bot no Telegram
1. No Telegram, abra a conversa com o [@BotFather](https://t.me/BotFather).
2. Envie o comando `/newbot`.
3. Escolha um nome de exibição (ex: `Gestor Financeiro`) e um username (ex: `meu_gestor_financeiro_bot`).
4. Copie o **Token HTTP API** gerado.
5. Descubra seu ID de usuário do Telegram conversando com [@userinfobot](https://t.me/userinfobot) (ele responderá seu `Id` numérico, ex: `123456789`).

### 2. Obter Chave da API do Google Gemini (Gratuita)
1. Acesse o [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Clique em **Create API key**.
3. Copie a chave gerada.

### 3. Configurar a Planilha e as Credenciais do Google Cloud
1. Crie uma nova planilha em branco no seu [Google Sheets](https://sheets.new) e dê o nome que preferir (ex: `Controle Financeiro 360`).
2. Copie o **ID da Planilha** na URL do navegador:
   - Exemplo: `https://docs.google.com/spreadsheets/d/`**`1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`**`/edit`
   - O ID é a parte em negrito entre `/d/` e `/edit`.
3. Para permitir que o robô acesse sua planilha:
   - Acesse o [Google Cloud Console](https://console.cloud.google.com/).
   - Crie um novo projeto (ou use um existente).
   - Ative a **Google Sheets API** e a **Google Drive API** na seção *APIs e Serviços > Biblioteca*.
   - Vá em *APIs e Serviços > Credenciais > Criar Credenciais > Conta de serviço (Service Account)*.
   - Dê um nome (ex: `bot-financeiro`) e clique em Concluir.
   - Clique na conta de serviço criada, vá na aba **Chaves (Keys) > Adicionar chave > Criar nova chave (JSON)**.
   - O download do arquivo JSON começará. Renomeie esse arquivo para `credentials.json` e coloque-o dentro da pasta deste projeto.
   - ⚠️ **PASSO MAIS IMPORTANTE**: Abra o arquivo `credentials.json`, copie o `client_email` (ex: `bot-financeiro@seu-projeto.iam.gserviceaccount.com`). Vá na sua planilha do Google Sheets, clique no botão azul **Compartilhar** no topo direito e adicione esse e-mail como **Editor**!

---

## ⚙️ Instalação e Execução

### No seu computador ou no servidor 24 horas:

1. **Clone ou copie a pasta do projeto**:
   ```bash
   cd gestor-financeiro-telegram
   ```

2. **Crie um ambiente virtual Python (recomendado)**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # No Mac/Linux
   # ou venv\Scripts\activate no Windows
   ```

3. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure o arquivo de variáveis de ambiente**:
   Copie o modelo de exemplo:
   ```bash
   cp .env.example .env
   ```
   Abra o arquivo `.env` e preencha com seus dados:
   ```ini
   TELEGRAM_BOT_TOKEN=seu_token_aqui
   ALLOWED_TELEGRAM_USERS=seu_id_do_telegram
   GEMINI_API_KEY=sua_chave_gemini_aqui
   SPREADSHEET_ID=o_id_da_sua_planilha_google
   GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json
   ```

5. **Inicialize a estrutura da planilha**:
   Execute este comando uma única vez para formatar as abas automaticamente:
   ```bash
   python setup_sheets.py
   ```

6. **Inicie o Bot e o Dashboard juntos**:
   ```bash
   python run_all.py
   ```
   - O Bot ficará ativo esperando mensagens no Telegram.
   - O Dashboard estará disponível no seu navegador em `http://localhost:8501`.

---

## 📱 Acessando o Dashboard de outros dispositivos

Como o servidor ficará ligado 24h, você pode acessar o dashboard pelo seu celular, tablet ou outro computador conectado na mesma rede Wi-Fi:
- Descubra o IP local da máquina 24h (ex: `192.168.1.50`).
- No celular ou notebook, basta abrir o navegador e digitar: `http://192.168.1.50:8501`.
- Para acessar de fora de casa com total segurança, você pode usar ferramentas gratuitas como [Tailscale](https://tailscale.com/) ou [Cloudflare Tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

---

## 💬 Exemplos de Uso no Telegram

- **Texto Simples:**
  - *"Almoço com a família 120 reais no débito"* (Classifica como **Casa**, Alimentação)
  - *"Comprei resina 3M 350 reais consultório"* (Classifica como **Consultório**, Insumos)
  - *"Renovação licença Exocad 2.400 d-cad no cartão"* (Classifica como **D-CAD**, Softwares)
  - *"Recebi 800 do paciente Carlos clareamento"* (Registra como **Receita** no Consultório)

- **Áudios:**
  - Basta enviar uma mensagem de voz rápida descrevendo a despesa. O modelo transcreve e extrai os valores automaticamente.

- **Comprovantes / Recibos:**
  - Envie uma foto de um recibo de papel, cupom fiscal ou print de Pix. O agente extrai o valor, data e favorecido, pedindo apenas para você confirmar o centro de custo!

- **Comandos:**
  - `/resumo`: Mostra o balanço de despesas, receitas e saldo de cada centro de custo no mês.
  - `/planilha`: Envia o link direto da sua planilha no Google Sheets.

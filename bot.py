import os
import json
import tempfile
import logging
from datetime import datetime
from typing import Dict, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_TELEGRAM_USER,
    ALLOWED_USERS_FILE,
    ALLOWED_TELEGRAM_USERS,
    SPREADSHEET_ID,
    CENTROS_DE_CUSTO,
    DASHBOARD_URL
)
from sheets_service import SheetsService
from ai_agent import FinancialAIAgent

# Configuração de logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Instâncias dos serviços
sheets_service = None
try:
    sheets_service = SheetsService()
except Exception as e:
    logger.warning(f"SheetsService não iniciado de imediato: {e}")

ai_agent = FinancialAIAgent()

# Dicionário em memória para guardar transações pendentes de confirmação
# { user_id: { ...dados_transacao... } }
pending_transactions: Dict[int, Dict] = {}

# Solicitações de acesso pendentes de novos usuários aguardando aprovação do admin
# { user_id: { "name": str, "username": str, "requested_at": str } }
pending_access_requests: Dict[int, Dict] = {}


def load_allowed_users() -> Dict[str, Dict]:
    """Carrega usuários autorizados do arquivo JSON."""
    if not ALLOWED_USERS_FILE.exists():
        initial = {
            str(ADMIN_TELEGRAM_USER): {
                "name": "Dr. Leonardo Viana",
                "role": "Admin",
                "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        try:
            with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(initial, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return initial

    try:
        with open(ALLOWED_USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler {ALLOWED_USERS_FILE}: {e}")
        return {str(ADMIN_TELEGRAM_USER): {"name": "Admin", "role": "Admin"}}


def save_allowed_user(user_id: int, name: str, username: Optional[str] = None):
    """Salva um novo usuário na lista de autorizados."""
    users = load_allowed_users()
    users[str(user_id)] = {
        "name": name,
        "username": username or "",
        "role": "Usuário Autorizado",
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def remove_allowed_user(user_id: int) -> bool:
    """Remove um usuário da lista de autorizados."""
    users = load_allowed_users()
    if str(user_id) in users:
        if user_id == ADMIN_TELEGRAM_USER:
            return False  # Não permite remover o próprio admin
        del users[str(user_id)]
        with open(ALLOWED_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    return False


def is_user_allowed(user_id: int) -> bool:
    """Verifica se o usuário é o admin ou está na lista de autorizados."""
    if user_id == ADMIN_TELEGRAM_USER:
        return True
    users = load_allowed_users()
    if str(user_id) in users:
        return True
    if ALLOWED_TELEGRAM_USERS and user_id in ALLOWED_TELEGRAM_USERS:
        return True
    return False


def get_user_display_name(user) -> str:
    """Retorna o nome amigável do usuário do Telegram."""
    if not user:
        return "Desconhecido"
    nome = user.first_name or ""
    if user.last_name:
        nome += f" {user.last_name}"
    if user.username:
        nome += f" (@{user.username})"
    return nome.strip() or f"User_{user.id}"


async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Garante autenticação do usuário ou envia pedido de autorização ao Admin."""
    user = update.effective_user
    if not user:
        return False

    if is_user_allowed(user.id):
        return True

    user_name = get_user_display_name(user)
    username_str = f"@{user.username}" if user.username else "Sem @username"

    # Se já enviou solicitação e está pendente
    if user.id in pending_access_requests:
        if update.message:
            await update.message.reply_text(
                "⏳ *Sua solicitação de acesso já foi enviada ao Administrador.*\n"
                "Você receberá uma mensagem aqui assim que o seu acesso for liberado!",
                parse_mode=ParseMode.MARKDOWN
            )
        return False

    # Registra como pendente
    pending_access_requests[user.id] = {
        "name": user_name,
        "username": user.username,
        "requested_at": datetime.now().strftime("%H:%M:%S")
    }

    # Avisa o novo usuário
    if update.message:
        await update.message.reply_text(
            f"👋 Olá, *{user.first_name}*!\n\n"
            "🔒 *Acesso Restrito ao Gestor Financeiro*\n"
            "Enviei uma solicitação de autorização diretamente ao Administrador no Telegram.\n\n"
            "Você receberá uma notificação aqui assim que ele aprovar seu acesso!",
            parse_mode=ParseMode.MARKDOWN
        )

    # Notifica o Administrador com botões interativos
    keyboard = [
        [
            InlineKeyboardButton("✅ Autorizar Acesso", callback_data=f"auth_approve_{user.id}"),
            InlineKeyboardButton("❌ Recusar", callback_data=f"auth_reject_{user.id}")
        ]
    ]
    msg_admin = (
        "🔔 *NOVA SOLICITAÇÃO DE ACESSO AO BOT FINANCEIRO*\n\n"
        f"• *Nome:* {user_name}\n"
        f"• *Username:* {username_str}\n"
        f"• *ID do Telegram:* `{user.id}`\n\n"
        "Deseja autorizar esta pessoa a registrar despesas e visualizar relatórios?"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_USER,
            text=msg_admin,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Erro ao notificar admin: {e}")

    return False


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mensagem de boas-vindas e instruções."""
    if not await check_auth(update, context):
        return

    msg = (
        "👋 *Olá! Eu sou o seu Agente Financeiro Pessoal & Empresarial.*\n\n"
        "Estou pronto para organizar suas finanças divididas nos 3 centros de custo:\n"
        "🏠 *Casa* (Pessoal e Família)\n"
        "🩺 *Consultório* (Clínico e Odontológico)\n"
        "💻 *D-CAD* (Tecnologia e CAD/CAM)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ *Como você pode lançar informações:*\n\n"
        "1️⃣ *Por Texto Livre:*\n"
        "• _\"Paguei 350 energia consultorio\"_\n"
        "• _\"Gastei 85 mercado no crédito\"_\n"
        "• _\"Renovação licença CAD 1800 d-cad\"_\n"
        "• _\"Recebi 1200 paciente canal consultorio\"_\n\n"
        "2️⃣ *Por Mensagem de Áudio:*\n"
        "Basta gravar um áudio rápido falando o valor, o que comprou e onde!\n\n"
        "3️⃣ *Por Foto ou Comprovante:*\n"
        "Tire uma foto do cupom fiscal ou envie o print do comprovante Pix/Boleto.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 *Comandos Úteis:*\n"
        "• `/dashboard` - Abrir painel web de gráficos\n"
        "• `/resumo` - Ver balanço do mês atual\n"
        "• `/planilha` - Link para abrir sua planilha no Google Sheets\n"
        "• `/ajuda` - Relembrar estes comandos"
    )

    planilha_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit" if SPREADSHEET_ID else "https://sheets.google.com"
    keyboard = [
        [
            InlineKeyboardButton("📊 Abrir Dashboard", url=DASHBOARD_URL),
            InlineKeyboardButton("📑 Abrir Planilha", url=planilha_url)
        ]
    ]
    await update.message.reply_text(
        msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia botões para abrir o dashboard web e a planilha."""
    if not await check_auth(update, context):
        return

    planilha_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit" if SPREADSHEET_ID else "https://sheets.google.com"
    keyboard = [
        [
            InlineKeyboardButton("📊 Abrir Dashboard Financeiro", url=DASHBOARD_URL)
        ],
        [
            InlineKeyboardButton("📑 Abrir Planilha Google Sheets", url=planilha_url)
        ]
    ]
    texto = (
        "📈 *Painel de Controle Financeiro em Tempo Real:*\n\n"
        "Acesse os gráficos, relatórios e diagnósticos com IA tocando no botão abaixo:"
    )
    await update.message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_planilha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia o link direto da planilha."""
    if not await check_auth(update, context):
        return

    if not SPREADSHEET_ID:
        await update.message.reply_text("⚠️ `SPREADSHEET_ID` ainda não foi configurado no arquivo `.env`.")
        return

    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
    await update.message.reply_text(
        f"📊 *Sua Planilha no Google Sheets:*\n[Clique aqui para abrir a Planilha]({url})",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=False
    )


async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera resumo financeiro do mês corrente."""
    if not await check_auth(update, context):
        return

    if not sheets_service or not SPREADSHEET_ID:
        await update.message.reply_text("⚠️ Conexão com a planilha não configurada.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    agora = datetime.now()
    meses_pt = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    nome_mes = meses_pt[agora.month]

    try:
        resumo = sheets_service.get_monthly_summary(agora.year, agora.month)
        
        texto = f"📅 *Resumo de {nome_mes}/{agora.year}*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        total_despesas = 0.0
        total_receitas = 0.0

        emojis = {"Casa": "🏠", "Consultório": "🩺", "D-CAD": "💻"}

        for centro in CENTROS_DE_CUSTO:
            d = resumo.get(centro, {"despesas": 0.0, "receitas": 0.0, "saldo": 0.0})
            total_despesas += d["despesas"]
            total_receitas += d["receitas"]
            emoji = emojis.get(centro, "📁")

            texto += (
                f"{emoji} *{centro}*\n"
                f"   • Despesas: `R$ {d['despesas']:,.2f}`\n"
                f"   • Receitas: `R$ {d['receitas']:,.2f}`\n"
                f"   • Saldo: `R$ {d['saldo']:,.2f}`\n\n"
            )

        saldo_geral = total_receitas - total_despesas
        texto += (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *TOTAL CONSOLIDADO:*\n"
            f"• Despesas Totais: `R$ {total_despesas:,.2f}`\n"
            f"• Receitas Totais: `R$ {total_receitas:,.2f}`\n"
            f"• Saldo Líquido: `R$ {saldo_geral:,.2f}`\n"
        )

        await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Erro ao obter resumo: {e}")
        await update.message.reply_text(f"❌ Ocorreu um erro ao buscar dados da planilha: {e}")


def make_confirmation_keyboard(centro_definido: bool = True) -> InlineKeyboardMarkup:
    """Cria botões de ação para confirmação ou seleção de centro de custo."""
    if centro_definido:
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar Lançamento", callback_data="confirm_save"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_tx")
            ],
            [
                InlineKeyboardButton("🔄 Mudar Centro de Custo", callback_data="choose_center")
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("🏠 Casa", callback_data="set_center_Casa"),
                InlineKeyboardButton("🩺 Consultório", callback_data="set_center_Consultório"),
                InlineKeyboardButton("💻 D-CAD", callback_data="set_center_D-CAD")
            ],
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_tx")
            ]
        ]
    return InlineKeyboardMarkup(keyboard)


def format_transaction_card(tx: Dict) -> str:
    """Formata visualmente os dados da transação para revisão do usuário."""
    tipo_emoji = "🔴 Despesa" if tx.get("tipo") == "Despesa" else "🟢 Receita"
    centro = tx.get("centro_custo", "Indefinido")
    centro_emoji = {"Casa": "🏠", "Consultório": "🩺", "D-CAD": "💻"}.get(centro, "❓")
    forma = tx.get("forma_pagamento", "Não informado")
    cartao = tx.get("cartao", "N/A")
    parcelas = tx.get("parcelas", "À vista")

    card = (
        f"📝 *Revisão do Lançamento:*\n\n"
        f"• *Tipo:* {tipo_emoji}\n"
        f"• *Valor:* `R$ {float(tx.get('valor', 0.0)):,.2f}`\n"
        f"• *Centro de Custo:* {centro_emoji} *{centro}*\n"
        f"• *Categoria:* {tx.get('categoria', 'Geral')}\n"
        f"• *Descrição:* {tx.get('descricao', '-')}\n"
        f"• *Pagamento:* {forma}\n"
    )

    if forma == "Cartão de Crédito" or (cartao and cartao != "N/A"):
        card += f"• *Cartão:* 💳 {cartao}\n"
        card += f"• *Parcelamento:* 🔢 {parcelas}\n"

    lancado_por = tx.get("lancado_por", "Você")
    card += (
        f"• *Lançado por:* 👤 {lancado_por}\n"
        f"• *Data:* `{tx.get('data', datetime.now().strftime('%Y-%m-%d'))}`\n"
    )
    return card


async def handle_message_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto."""
    if not await check_auth(update, context):
        return

    user_text = update.message.text
    user_id = update.effective_user.id

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    try:
        user_name = get_user_display_name(update.effective_user)
        parsed = ai_agent.parse_text(user_text)
        parsed["origem"] = "Texto Telegram"
        parsed["lancado_por"] = user_name
        pending_transactions[user_id] = parsed

        tem_centro = (
            parsed.get("confianca_centro_custo") is True and
            parsed.get("centro_custo") in CENTROS_DE_CUSTO
        )

        reply_markup = make_confirmation_keyboard(centro_definido=tem_centro)
        card = format_transaction_card(parsed)

        if not tem_centro:
            card += "\n❓ *Por favor, selecione abaixo para qual centro de custo este lançamento pertence:*"

        await update.message.reply_text(card, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Erro no processamento de texto: {e}")
        await update.message.reply_text(f"❌ Erro ao analisar mensagem: {e}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de áudio."""
    if not await check_auth(update, context):
        return

    user_id = update.effective_user.id
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)

    temp_audio_path = None
    try:
        voice = update.message.voice
        file_obj = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
            temp_audio_path = tf.name

        await file_obj.download_to_drive(temp_audio_path)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        user_name = get_user_display_name(update.effective_user)
        parsed = ai_agent.parse_audio(temp_audio_path)
        parsed["origem"] = "Áudio Telegram"
        parsed["lancado_por"] = user_name
        pending_transactions[user_id] = parsed

        tem_centro = (
            parsed.get("confianca_centro_custo") is True and
            parsed.get("centro_custo") in CENTROS_DE_CUSTO
        )

        reply_markup = make_confirmation_keyboard(centro_definido=tem_centro)
        card = format_transaction_card(parsed)

        if not tem_centro:
            card += "\n❓ *Por favor, selecione para qual centro de custo este áudio se refere:*"

        await update.message.reply_text(card, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Erro no processamento de áudio: {e}")
        await update.message.reply_text(f"❌ Não foi possível processar o áudio: {e}")
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa fotos de comprovantes ou notas fiscais."""
    if not await check_auth(update, context):
        return

    user_id = update.effective_user.id
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)

    temp_img_path = None
    try:
        # Pega a foto de maior resolução enviada
        photo = update.message.photo[-1]
        file_obj = await context.bot.get_file(photo.file_id)
        caption = update.message.caption or ""

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            temp_img_path = tf.name

        await file_obj.download_to_drive(temp_img_path)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        user_name = get_user_display_name(update.effective_user)
        parsed = ai_agent.parse_image(temp_img_path, user_caption=caption)
        parsed["origem"] = "Comprovante/Foto Telegram"
        parsed["lancado_por"] = user_name
        pending_transactions[user_id] = parsed

        tem_centro = (
            parsed.get("confianca_centro_custo") is True and
            parsed.get("centro_custo") in CENTROS_DE_CUSTO
        )

        reply_markup = make_confirmation_keyboard(centro_definido=tem_centro)
        card = format_transaction_card(parsed)

        if not tem_centro:
            card += "\n❓ *Comprovante lido com sucesso! Escolha o centro de custo para salvar:*"

        await update.message.reply_text(card, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Erro no processamento de imagem: {e}")
        await update.message.reply_text(f"❌ Erro ao ler comprovante: {e}")
    finally:
        if temp_img_path and os.path.exists(temp_img_path):
            os.remove(temp_img_path)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gerencia cliques nos botões inline."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    action = query.data

    # Ações de autorização de novos usuários (Exclusivas do Admin)
    if action.startswith("auth_approve_"):
        if user_id != ADMIN_TELEGRAM_USER:
            await query.edit_message_text("⚠️ Apenas o Administrador pode autorizar novos usuários.")
            return

        target_id = int(action.replace("auth_approve_", ""))
        user_info = pending_access_requests.pop(target_id, {"name": f"User_{target_id}", "username": ""})
        save_allowed_user(target_id, user_info.get("name", "Usuário"), user_info.get("username", ""))

        await query.edit_message_text(
            f"✅ *ACESSO AUTORIZADO!*\n\n"
            f"O usuário *{user_info.get('name')}* (ID: `{target_id}`) agora está autorizado a usar o bot.",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "🎉 *Parabéns! Seu acesso foi aprovado pelo Administrador!*\n\n"
                    "Você já pode enviar suas despesas e receitas por texto livre, áudio ou fotos de comprovantes.\n\n"
                    "Envie `/start` para começar!"
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Erro ao notificar usuário aprovado: {e}")
        return

    elif action.startswith("auth_reject_"):
        if user_id != ADMIN_TELEGRAM_USER:
            await query.edit_message_text("⚠️ Apenas o Administrador pode gerenciar acessos.")
            return

        target_id = int(action.replace("auth_reject_", ""))
        user_info = pending_access_requests.pop(target_id, {"name": f"User_{target_id}"})

        await query.edit_message_text(
            f"❌ *SOLICITAÇÃO RECUSADA.*\n\nO acesso para *{user_info.get('name')}* (ID: `{target_id}`) foi recusado.",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="❌ Sua solicitação de acesso não foi aprovada pelo Administrador."
            )
        except Exception:
            pass
        return

    if user_id not in pending_transactions:
        await query.edit_message_text("⚠️ Este lançamento expirou ou já foi processado.")
        return

    tx = pending_transactions[user_id]

    if action == "cancel_tx":
        del pending_transactions[user_id]
        await query.edit_message_text("❌ Lançamento cancelado.")
        return

    elif action == "choose_center":
        # Apresenta botões para trocar o centro de custo
        await query.edit_message_text(
            format_transaction_card(tx) + "\nEscolha o centro de custo:",
            reply_markup=make_confirmation_keyboard(centro_definido=False),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    elif action.startswith("set_center_"):
        novo_centro = action.replace("set_center_", "")
        tx["centro_custo"] = novo_centro
        tx["confianca_centro_custo"] = True
        # Mostra o card atualizado com botão de confirmação
        await query.edit_message_text(
            format_transaction_card(tx) + "\nCentro de custo selecionado! Confirme para salvar:",
            reply_markup=make_confirmation_keyboard(centro_definido=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    elif action == "confirm_save":
        if not sheets_service:
            await query.edit_message_text("⚠️ Erro: Conexão com Google Sheets não configurada.")
            return

        try:
            res = sheets_service.add_transaction(
                centro_custo=tx.get("centro_custo", "Casa"),
                tipo=tx.get("tipo", "Despesa"),
                valor=tx.get("valor", 0.0),
                categoria=tx.get("categoria", "Geral"),
                descricao=tx.get("descricao", "Sem descrição"),
                forma_pagamento=tx.get("forma_pagamento", "Não especificado"),
                cartao=tx.get("cartao", "N/A"),
                parcelas=tx.get("parcelas", "À vista"),
                lancado_por=tx.get("lancado_por", "Desconhecido"),
                origem=tx.get("origem", "Telegram"),
                data_personalizada=tx.get("data")
            )

            del pending_transactions[user_id]

            planilha_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit" if SPREADSHEET_ID else "https://sheets.google.com"
            success_keyboard = [
                [
                    InlineKeyboardButton("📊 Ver no Dashboard", url=DASHBOARD_URL),
                    InlineKeyboardButton("📑 Ver na Planilha", url=planilha_url)
                ]
            ]

            msg_sucesso = (
                f"✅ *Lançamento salvo com sucesso no Google Sheets!*\n\n"
                f"🆔 *ID:* `{res['id']}`\n"
                f"📁 *Centro de Custo:* {res['centro_custo']}\n"
                f"💰 *Valor:* `R$ {res['valor']:,.2f}`\n"
                f"🏷️ *Categoria:* {res['categoria']}\n"
                f"📝 *Descrição:* {res['descricao']}\n"
                f"💳 *Pagamento:* {res['forma_pagamento']}\n"
            )

            if res.get("cartao") and res.get("cartao") != "N/A":
                msg_sucesso += f"💳 *Cartão:* {res['cartao']} ({res.get('parcelas', 'À vista')})\n"

            msg_sucesso += (
                f"👤 *Lançado por:* {res.get('lancado_por', 'Você')}\n\n"
                f"_A planilha e o dashboard já foram atualizados em tempo real!_"
            )

            await query.edit_message_text(
                msg_sucesso,
                reply_markup=InlineKeyboardMarkup(success_keyboard),
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Erro ao salvar na planilha: {e}")
            await query.edit_message_text(f"❌ Erro ao salvar na planilha: {e}")


async def cmd_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista todos os usuários com acesso autorizado (Comando de Admin)."""
    user_id = update.effective_user.id
    if user_id != ADMIN_TELEGRAM_USER:
        await update.message.reply_text("🚫 Este comando é restrito ao Administrador.")
        return

    users = load_allowed_users()
    texto = "👥 *Usuários Autorizados no Bot:*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    for uid, info in users.items():
        role = "👑 Admin" if int(uid) == ADMIN_TELEGRAM_USER else "👤 Usuário"
        nome = info.get("name", "Sem nome")
        username = f" (@{info.get('username')})" if info.get("username") else ""
        texto += f"• *{nome}*{username}\n  🆔 ID: `{uid}` | {role}\n\n"

    texto += "━━━━━━━━━━━━━━━━━━━━━\n"
    texto += "💡 _Para revogar o acesso de alguém, envie:_ `/remover <ID>`"
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)


async def cmd_remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove um usuário da lista de autorizados (Comando de Admin)."""
    user_id = update.effective_user.id
    if user_id != ADMIN_TELEGRAM_USER:
        await update.message.reply_text("🚫 Este comando é restrito ao Administrador.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Informe o ID do usuário que deseja remover.\nExemplo: `/remover 123456789`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id_str = context.args[0].strip()
    if not target_id_str.isdigit():
        await update.message.reply_text("⚠️ O ID deve conter apenas números.")
        return

    target_id = int(target_id_str)
    if target_id == ADMIN_TELEGRAM_USER:
        await update.message.reply_text("⚠️ Você não pode remover o próprio Administrador!")
        return

    if remove_allowed_user(target_id):
        await update.message.reply_text(f"✅ O acesso do usuário ID `{target_id}` foi revogado com sucesso.", parse_mode=ParseMode.MARKDOWN)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="⚠️ Seu acesso ao bot financeiro foi revogado pelo Administrador."
            )
        except Exception:
            pass
    else:
        await update.message.reply_text(f"⚠️ Usuário ID `{target_id}` não foi encontrado na lista de autorizados.", parse_mode=ParseMode.MARKDOWN)


def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ ERRO: Defina a variável TELEGRAM_BOT_TOKEN no arquivo .env")
        return

    print("🤖 Iniciando o Bot Financeiro do Telegram...")

    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("dashboard", "📊 Abrir painel web de gráficos"),
            BotCommand("resumo", "📅 Ver balanço do mês atual"),
            BotCommand("planilha", "📑 Abrir planilha Google Sheets"),
            BotCommand("usuarios", "👥 Gerenciar usuários (Admin)"),
            BotCommand("ajuda", "❓ Como usar o assistente")
        ])

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("painel", cmd_dashboard))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("planilha", cmd_planilha))
    app.add_handler(CommandHandler("usuarios", cmd_usuarios))
    app.add_handler(CommandHandler("remover", cmd_remover))

    # Mensagens de texto, áudio e fotos
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Callbacks interativos dos botões
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    print("✅ Bot online e pronto para receber mensagens!")
    app.run_polling()


if __name__ == "__main__":
    main()

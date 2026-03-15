import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN    = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
KEYS_CHANNEL = int(os.environ.get("KEYS_CHANNEL", "-1003721030654"))
SBP_PHONE = os.environ.get("SBP_PHONE", "+7XXXXXXXXXX")
SBP_NAME  = os.environ.get("SBP_NAME", "Евгений В.")

PLANS = {
    "start": {"name": "Start", "rub": 500,   "desc": "~300 фото, ~15 видео, базовые модели",            "emoji": "⚪"},
    "basic": {"name": "Basic", "rub": 1000,  "desc": "~600 фото, ~30 видео, все модели",                "emoji": "🔵"},
    "pro":   {"name": "Pro",   "rub": 3000,  "desc": "~1900 фото, ~100 видео, Nano Banana, Veo, Kling", "emoji": "🟢"},
    "elite": {"name": "Elite", "rub": 5000,  "desc": "~3200 фото, ~400 видео HD, 30+ моделей",          "emoji": "🟣"},
    "max":   {"name": "Max",   "rub": 7000,  "desc": "~4500 фото, ~800 видео, приоритет моделей",       "emoji": "🟡"},
    "ultra": {"name": "Ultra", "rub": 10000, "desc": "~6500 фото, ~1500 видео, максимум возможностей",  "emoji": "🔴"},
}

# Временное хранилище ожидающих оплат (в памяти)
pending_orders = {}

# ─── KEEP-ALIVE ───────────────────────────────────────────

class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, format, *args):
        pass

def run_keep_alive():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(('0.0.0.0', port), KeepAlive).serve_forever()

def is_admin(user_id):
    return user_id == ADMIN_ID

# ─── TELEGRAM CHANNEL KEYS ────────────────────────────────

async def add_key_to_channel(bot, plan_id: str, key: str) -> int:
    """Добавляет ключ в канал, возвращает message_id"""
    msg = await bot.send_message(
        KEYS_CHANNEL,
        f"{plan_id}:{key}"
    )
    return msg.message_id

async def get_key_from_channel(bot, plan_id: str):
    """Ищет первый ключ нужного тарифа в канале"""
    try:
        # Получаем историю канала
        messages = await bot.get_chat_history(KEYS_CHANNEL, limit=200)
        for msg in messages:
            if msg.text and msg.text.startswith(f"{plan_id}:"):
                key = msg.text.split(":", 1)[1].strip()
                return key, msg.message_id
    except Exception as e:
        logger.error(f"get_key error: {e}")
    return None, None

async def count_keys_in_channel(bot, plan_id: str) -> int:
    """Считает ключи тарифа в канале"""
    try:
        count = 0
        async for msg in bot.get_chat_history(KEYS_CHANNEL, limit=500):
            if msg.text and msg.text.startswith(f"{plan_id}:"):
                count += 1
        return count
    except Exception as e:
        logger.error(f"count_keys error: {e}")
        return 0

async def delete_key_from_channel(bot, message_id: int):
    """Удаляет ключ из канала"""
    try:
        await bot.delete_message(KEYS_CHANNEL, message_id)
    except Exception as e:
        logger.error(f"delete_key error: {e}")

# ─── KEYBOARDS ────────────────────────────────────────────

def plans_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {p['rub']}₽",
            callback_data=f"buy_{pid}"
        )])
    return InlineKeyboardMarkup(rows)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Добавить ключи", callback_data="admin_addkeys")],
        [InlineKeyboardButton("📊 Остаток ключей", callback_data="admin_keys")],
        [InlineKeyboardButton("🗑 Очистить ключи", callback_data="admin_delkeys")],
        [InlineKeyboardButton("⏳ Ожидают оплаты", callback_data="admin_pending")],
    ])

def addkeys_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(f"{p['emoji']} {p['name']} — {p['rub']}₽", callback_data=f"addkey_{pid}")])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)

def delkeys_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(f"🗑 {p['name']} — {p['rub']}₽", callback_data=f"delkey_{pid}")])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)

# ─── START ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.message.from_user.id):
        await update.message.reply_text(
            "👁 *ElSpy Pay* — Панель управления\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_text(
            "👁 *ElSpy Pay* — пополнение баланса ElSpy AI\n\n"
            "Выбери тариф и оплати через СБП.\n"
            "После отправки скрина — ключ придёт в течение 5 минут.\n\n"
            "💡 Баланс не сгорает!",
            parse_mode="Markdown",
            reply_markup=plans_keyboard()
        )

# ─── BUTTONS ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    bot = context.bot

    if query.data == "admin_addkeys" and is_admin(uid):
        await query.message.edit_text(
            "➕ *Добавить ключи*\n\nВыбери тариф:",
            parse_mode="Markdown",
            reply_markup=addkeys_keyboard()
        )

    elif query.data == "admin_keys" and is_admin(uid):
        await query.message.edit_text("⏳ Считаю ключи...", parse_mode="Markdown")
        text = "📊 *Остаток ключей:*\n\n"
        for pid, p in PLANS.items():
            count = await count_keys_in_channel(bot, pid)
            emoji = "✅" if count > 0 else "❌"
            text += f"{emoji} *{p['name']}* ({p['rub']}₽): {count} шт\n"
        await query.message.edit_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )

    elif query.data == "admin_pending" and is_admin(uid):
        if not pending_orders:
            await query.message.edit_text(
                "✅ Нет ожидающих оплат",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
            )
            return
        text = f"⏳ *Ожидают подтверждения: {len(pending_orders)}*\n\nПроверь личные сообщения — там кнопки подтверждения."
        await query.message.edit_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )

    elif query.data == "admin_delkeys" and is_admin(uid):
        await query.message.edit_text(
            "🗑 *Очистить ключи*\n\nВыбери тариф:",
            parse_mode="Markdown",
            reply_markup=delkeys_keyboard()
        )

    elif query.data == "admin_back" and is_admin(uid):
        await query.message.edit_text(
            "👁 *ElSpy Pay* — Панель управления\n\nВыбери действие:",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )

    elif query.data.startswith("addkey_") and is_admin(uid):
        pid = query.data[7:]
        p = PLANS[pid]
        context.user_data["adding_key_plan"] = pid
        await query.message.edit_text(
            f"➕ *Добавить ключ — {p['name']} ({p['rub']}₽)*\n\n"
            f"Отправь ключи следующим сообщением.\n"
            f"Можно несколько — каждый с новой строки:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
        )

    elif query.data.startswith("delkey_") and is_admin(uid):
        pid = query.data[7:]
        p = PLANS[pid]
        await query.message.edit_text(f"⏳ Удаляю ключи *{p['name']}*...", parse_mode="Markdown")
        deleted = 0
        try:
            async for msg in bot.get_chat_history(KEYS_CHANNEL, limit=500):
                if msg.text and msg.text.startswith(f"{pid}:"):
                    await bot.delete_message(KEYS_CHANNEL, msg.message_id)
                    deleted += 1
        except Exception as e:
            logger.error(f"delkey error: {e}")
        await query.message.edit_text(
            f"✅ Удалено *{deleted}* ключей тарифа *{p['name']}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )

    elif query.data.startswith("confirm_") and is_admin(uid):
        order_id = query.data[8:]
        if order_id not in pending_orders:
            await query.message.edit_caption("❌ Заявка не найдена (уже обработана?)")
            return
        order = pending_orders[order_id]
        pid = order["plan"]
        user_id = order["user_id"]
        p = PLANS[pid]

        # Ищем ключ в канале
        key, msg_id = await get_key_from_channel(bot, pid)
        if not key:
            await query.message.edit_caption("❌ Ключи закончились! Добавь ключи и подтверди вручную.")
            return

        # Удаляем ключ из канала
        await delete_key_from_channel(bot, msg_id)
        del pending_orders[order_id]

        await query.message.edit_caption(
            f"✅ Подтверждено! Ключ отправлен пользователю {user_id}",
            parse_mode="Markdown"
        )

        await bot.send_message(
            user_id,
            f"✅ *Оплата подтверждена!*\n\n"
            f"Тариф: *{p['name']}* ({p['rub']}₽)\n\n"
            f"🔑 *Ключ активации:*\n`{key}`\n\n"
            f"📋 *Как активировать:*\n"
            f"1. Перейди на сайт\n"
            f"2. Войди в аккаунт\n"
            f"3. Нажми «Пополнить баланс»\n"
            f"4. Введи ключ — баланс пополнится на *{p['rub']}₽*\n\n"
            f"⚠️ Ключ одноразовый!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌐 Перейти на сайт", url="https://elspy.ai6700.com/")
            ]])
        )

    elif query.data.startswith("reject_") and is_admin(uid):
        order_id = query.data[7:]
        if order_id not in pending_orders:
            await query.message.edit_caption("❌ Заявка не найдена")
            return
        user_id = pending_orders[order_id]["user_id"]
        del pending_orders[order_id]

        await query.message.edit_caption(f"❌ Заявка отклонена. Уведомление отправлено пользователю {user_id}")
        await bot.send_message(
            user_id,
            "❌ *Оплата не подтверждена.*\n\n"
            "Возможно скрин нечёткий или сумма не совпадает.\n"
            "Напиши в поддержку если есть вопросы.",
            parse_mode="Markdown"
        )

    elif query.data.startswith("buy_"):
        pid = query.data[4:]
        p = PLANS.get(pid)
        if not p:
            return
        context.user_data["selected_plan"] = pid
        await query.message.reply_text(
            f"{p['emoji']} *{p['name']}* — {p['rub']}₽\n\n"
            f"_{p['desc']}_\n\n"
            f"💳 *Оплата через СБП:*\n"
            f"📱 Номер: `{SBP_PHONE}`\n"
            f"👤 Получатель: {SBP_NAME}\n"
            f"💰 Сумма: *{p['rub']} ₽*\n\n"
            f"После оплаты отправь сюда *скриншот* подтверждения платежа.",
            parse_mode="Markdown"
        )

# ─── MESSAGES ─────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if is_admin(uid):
        return

    pid = context.user_data.get("selected_plan")
    if not pid:
        await update.message.reply_text("Сначала выбери тариф:", reply_markup=plans_keyboard())
        return

    p = PLANS[pid]
    user = update.message.from_user
    order_id = f"{uid}_{update.message.message_id}"

    pending_orders[order_id] = {"plan": pid, "user_id": uid}
    context.user_data.pop("selected_plan", None)

    await update.message.reply_text(
        "⏳ *Скрин получен!*\n\nОжидай подтверждения — обычно до 5 минут.",
        parse_mode="Markdown"
    )

    name = f"@{user.username}" if user.username else f"{user.first_name} ({uid})"
    await context.bot.send_photo(
        ADMIN_ID,
        update.message.photo[-1].file_id,
        caption=f"💳 *Новая оплата!*\n\n"
                f"👤 Пользователь: {name}\n"
                f"📦 Тариф: *{p['name']}* ({p['rub']}₽)\n\n"
                f"Подтверди или отклони:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("❌ Отклонить",   callback_data=f"reject_{order_id}")
        ]])
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if is_admin(uid) and "adding_key_plan" in context.user_data:
        pid = context.user_data.pop("adding_key_plan")
        p = PLANS[pid]
        new_keys = [k.strip() for k in update.message.text.strip().splitlines() if k.strip()]
        added = 0
        for key in new_keys:
            await add_key_to_channel(context.bot, pid, key)
            added += 1
        await update.message.reply_text(
            f"✅ Добавлено *{added}* ключей для *{p['name']}* ({p['rub']}₽)\n\n"
            f"Ключи сохранены в канале — не потеряются при перезапуске!",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
        return

    await update.message.reply_text(
        "📸 Отправь *скриншот* оплаты или выбери тариф:",
        parse_mode="Markdown",
        reply_markup=plans_keyboard()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Помощь*\n\n/start — главное меню\n/help — помощь\n\nПоддержка: @elspy\\_support",
        parse_mode="Markdown"
    )

def main():
    threading.Thread(target=run_keep_alive, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("ElSpy Pay bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

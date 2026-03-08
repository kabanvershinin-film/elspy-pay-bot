import os
import logging
import json
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PreCheckoutQueryHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

PLANS = {
    "basic":  {"name": "Basic",  "rub": 1000,  "stars": 500,  "desc": "~600 фото, ~30 видео, все модели",               "emoji": "🔵"},
    "pro":    {"name": "Pro",    "rub": 3000,  "stars": 1500, "desc": "~1900 фото, ~100 видео, Nano Banana, Veo, Kling", "emoji": "🟢"},
    "elite":  {"name": "Elite",  "rub": 6000,  "stars": 3000, "desc": "~3200 фото 30+ моделей, ~600 видео HD",           "emoji": "🟣"},
    "max":    {"name": "Max",    "rub": 12000, "stars": 6000, "desc": "~6500 фото, ~1500 видео, приоритет моделей",       "emoji": "🟡"},
}

KEYS_FILE = "/tmp/keys.json"
WAITING_KEY = 1

def load_keys():
    try:
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"basic": [], "pro": [], "elite": [], "max": []}

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f)

def is_admin(user_id):
    return user_id == ADMIN_ID

def plans_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {p['rub']}₽  ({p['stars']} ⭐)",
            callback_data=f"buy_{pid}"
        )])
    return InlineKeyboardMarkup(rows)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Добавить ключи", callback_data="admin_addkeys")],
        [InlineKeyboardButton("📊 Остаток ключей", callback_data="admin_keys")],
        [InlineKeyboardButton("🗑 Очистить ключи", callback_data="admin_delkeys")],
    ])

def addkeys_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']}",
            callback_data=f"addkey_{pid}"
        )])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)

def delkeys_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(
            f"🗑 {p['name']}",
            callback_data=f"delkey_{pid}"
        )])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)

# ─── USER COMMANDS ────────────────────────────────────────

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
            "Выбери тариф и оплати через Telegram Stars.\n"
            "После оплаты получишь ключ активации для сайта.\n\n"
            "💡 Баланс не сгорает!",
            parse_mode="Markdown",
            reply_markup=plans_keyboard()
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    # ── ADMIN ──
    if query.data == "admin_addkeys" and is_admin(uid):
        await query.message.edit_text(
            "➕ *Добавить ключи*\n\nВыбери тариф:",
            parse_mode="Markdown",
            reply_markup=addkeys_keyboard()
        )

    elif query.data == "admin_keys" and is_admin(uid):
        keys = load_keys()
        text = "📊 *Остаток ключей:*\n\n"
        for pid, p in PLANS.items():
            count = len(keys.get(pid, []))
            emoji = "✅" if count > 0 else "❌"
            text += f"{emoji} *{p['name']}*: {count} шт\n"
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
        ]]))

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
        context.user_data["adding_key_plan"] = pid
        p = PLANS[pid]
        await query.message.edit_text(
            f"➕ *Добавить ключ — {p['name']}*\n\n"
            f"Отправь ключ следующим сообщением.\n"
            f"Можно отправить несколько ключей — каждый с новой строки:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data="admin_back")
            ]])
        )

    elif query.data.startswith("delkey_") and is_admin(uid):
        pid = query.data[7:]
        keys = load_keys()
        keys[pid] = []
        save_keys(keys)
        p = PLANS[pid]
        await query.message.edit_text(
            f"✅ Ключи тарифа *{p['name']}* очищены",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
            ]])
        )

    # ── USER ──
    elif query.data.startswith("buy_"):
        pid = query.data[4:]
        p = PLANS.get(pid)
        if not p:
            return
        keys = load_keys()
        if not keys.get(pid):
            await query.message.reply_text(
                f"😔 Ключи для тарифа *{p['name']}* временно недоступны.\nПопробуй позже.",
                parse_mode="Markdown"
            )
            return
        await query.message.reply_text(
            f"{p['emoji']} *{p['name']}*\n\n"
            f"💰 Стоимость: *{p['rub']}₽* ({p['stars']} ⭐)\n"
            f"📦 Включает: {p['desc']}\n\n"
            f"Нажми чтобы оплатить через Telegram Stars:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"⭐ Оплатить {p['stars']} Stars", callback_data=f"pay_{pid}")
            ]])
        )

    elif query.data.startswith("pay_"):
        pid = query.data[4:]
        p = PLANS.get(pid)
        if not p:
            return
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=f"ElSpy AI — {p['name']}",
            description=f"Пополнение баланса {p['rub']}₽. {p['desc']}",
            payload=f"elspy_{pid}_{query.from_user.id}",
            currency="XTR",
            prices=[LabeledPrice(label=f"Тариф {p['name']}", amount=p['stars'])],
            provider_token=""
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    # Если админ добавляет ключи
    if is_admin(uid) and "adding_key_plan" in context.user_data:
        pid = context.user_data.pop("adding_key_plan")
        p = PLANS[pid]
        new_keys = [k.strip() for k in update.message.text.strip().splitlines() if k.strip()]
        keys = load_keys()
        keys[pid].extend(new_keys)
        save_keys(keys)
        await update.message.reply_text(
            f"✅ Добавлено *{len(new_keys)}* ключей для *{p['name']}*\n"
            f"Всего теперь: *{len(keys[pid])}* шт",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
        return

    await update.message.reply_text("Выбери тариф:", reply_markup=plans_keyboard())

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    parts = payment.invoice_payload.split("_")
    pid = parts[1]
    user_id = update.message.from_user.id
    p = PLANS.get(pid)
    if not p:
        await update.message.reply_text("❌ Ошибка. Напиши в поддержку.")
        return

    keys = load_keys()
    if not keys.get(pid):
        await update.message.reply_text("❌ Ключи закончились! Напиши в поддержку.")
        if ADMIN_ID:
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ *Ключи закончились!*\nТариф: {p['name']}\nПользователь: {user_id}",
                parse_mode="Markdown"
            )
        return

    key = keys[pid].pop(0)
    save_keys(keys)
    logger.info(f"Payment: user={user_id}, plan={pid}, key={key}")

    remaining = len(keys[pid])
    if ADMIN_ID and remaining <= 2:
        await context.bot.send_message(
            ADMIN_ID,
            f"⚠️ *Мало ключей!*\nТариф: *{p['name']}*\nОсталось: {remaining} шт",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"➕ Добавить ключи", callback_data="admin_addkeys")
            ]])
        )

    await update.message.reply_text(
        f"✅ *Оплата прошла!*\n\n"
        f"Тариф: *{p['name']}* ({p['rub']}₽)\n\n"
        f"🔑 *Ключ активации:*\n"
        f"`{key}`\n\n"
        f"📋 *Как активировать:*\n"
        f"1. Перейди на elspy.ai\n"
        f"2. Войди в аккаунт\n"
        f"3. Нажми «Пополнить баланс»\n"
        f"4. Введи ключ — баланс пополнится на *{p['rub']}₽*\n\n"
        f"⚠️ Ключ одноразовый, не передавай другим!",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Помощь*\n\n"
        "/start — главное меню\n"
        "/help — помощь\n\n"
        "Поддержка: @elspy\\_support",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("ElSpy Pay bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

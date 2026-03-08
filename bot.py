import os
import logging
import json
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PreCheckoutQueryHandler, CallbackQueryHandler,
    filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))  # Твой Telegram ID

PLANS = {
    "basic":  {"name": "Basic",  "rub": 1000,  "stars": 500,  "desc": "~600 фото, ~30 видео, все модели",               "emoji": "🔵"},
    "pro":    {"name": "Pro",    "rub": 3000,  "stars": 1500, "desc": "~1900 фото, ~100 видео, Nano Banana, Veo, Kling", "emoji": "🟢"},
    "elite":  {"name": "Elite",  "rub": 6000,  "stars": 3000, "desc": "~3200 фото 30+ моделей, ~600 видео HD",           "emoji": "🟣"},
    "max":    {"name": "Max",    "rub": 12000, "stars": 6000, "desc": "~6500 фото, ~1500 видео, приоритет моделей",       "emoji": "🟡"},
}

# Хранилище ключей: {"basic": ["KEY1", "KEY2"], "pro": [...], ...}
KEYS_FILE = "/tmp/keys.json"

def load_keys():
    try:
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"basic": [], "pro": [], "elite": [], "max": []}

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f)

def plans_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {p['rub']}₽  ({p['stars']} ⭐)",
            callback_data=f"buy_{pid}"
        )])
    return InlineKeyboardMarkup(rows)

def is_admin(user_id):
    return user_id == ADMIN_ID

# ─── ADMIN COMMANDS ───────────────────────────────────────

async def addkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить ключ: /addkey basic КЛЮЧ"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Нет доступа")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "📋 Использование:\n`/addkey basic КЛЮЧ`\n`/addkey pro КЛЮЧ`\n`/addkey elite КЛЮЧ`\n`/addkey max КЛЮЧ`",
            parse_mode="Markdown"
        )
        return

    pid = context.args[0].lower()
    key = context.args[1].strip()

    if pid not in PLANS:
        await update.message.reply_text("❌ Неверный тариф. Используй: basic, pro, elite, max")
        return

    keys = load_keys()
    keys[pid].append(key)
    save_keys(keys)

    await update.message.reply_text(
        f"✅ Ключ добавлен!\n\nТариф: *{PLANS[pid]['name']}*\nКлюч: `{key}`\nВсего ключей: {len(keys[pid])}",
        parse_mode="Markdown"
    )

async def keys_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сколько ключей осталось: /keys"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Нет доступа")
        return

    keys = load_keys()
    text = "🔑 *Остаток ключей:*\n\n"
    for pid, p in PLANS.items():
        count = len(keys.get(pid, []))
        emoji = "✅" if count > 0 else "❌"
        text += f"{emoji} *{p['name']}*: {count} шт\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def delkeys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить все ключи тарифа: /delkeys basic"""
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Нет доступа")
        return

    if not context.args:
        await update.message.reply_text("Использование: `/delkeys basic`", parse_mode="Markdown")
        return

    pid = context.args[0].lower()
    if pid not in PLANS:
        await update.message.reply_text("❌ Неверный тариф")
        return

    keys = load_keys()
    keys[pid] = []
    save_keys(keys)
    await update.message.reply_text(f"✅ Ключи тарифа *{PLANS[pid]['name']}* очищены", parse_mode="Markdown")

# ─── USER COMMANDS ────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👁 *ElSpy Pay* — пополнение баланса ElSpy AI\n\n"
        "Выбери тариф и оплати через Telegram Stars.\n"
        "После оплаты получишь ключ активации для сайта.\n\n"
        "💡 Баланс не сгорает!",
        parse_mode="Markdown",
        reply_markup=plans_keyboard()
    )

async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💳 *Выбери тариф:*", parse_mode="Markdown", reply_markup=plans_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("buy_"):
        pid = query.data[4:]
        p = PLANS.get(pid)
        if not p:
            return

        # Проверяем наличие ключей
        keys = load_keys()
        if not keys.get(pid):
            await query.message.reply_text(
                f"😔 Ключи для тарифа *{p['name']}* временно недоступны.\nПопробуй позже или выбери другой тариф.",
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

    # Берём ключ из списка
    keys = load_keys()
    if not keys.get(pid):
        await update.message.reply_text(
            "❌ Ключи закончились! Напиши в поддержку — вернём деньги или пришлём ключ вручную."
        )
        # Уведомляем админа
        if ADMIN_ID:
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ Ключи закончились!\nТариф: {p['name']}\nПользователь: {user_id}\nОплатил: {p['stars']} ⭐"
            )
        return

    key = keys[pid].pop(0)  # Берём первый ключ
    save_keys(keys)

    logger.info(f"Payment: user={user_id}, plan={pid}, key={key}")

    # Уведомляем админа если ключей мало
    remaining = len(keys[pid])
    if ADMIN_ID and remaining <= 2:
        await context.bot.send_message(
            ADMIN_ID,
            f"⚠️ Мало ключей!\nТариф: *{p['name']}*\nОсталось: {remaining} шт\nДобавь: `/addkey {pid} КЛЮЧ`",
            parse_mode="Markdown"
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
        "/plans — выбрать тариф\n"
        "/help — помощь\n\n"
        "Поддержка: @elspy\\_support",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери тариф:", reply_markup=plans_keyboard())

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("plans", show_plans))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addkey", addkey))
    app.add_handler(CommandHandler("keys", keys_status))
    app.add_handler(CommandHandler("delkeys", delkeys))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("ElSpy Pay bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

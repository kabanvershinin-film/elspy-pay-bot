import os
import logging
import secrets
from datetime import datetime
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    PreCheckoutQueryHandler, CallbackQueryHandler,
    filters, ContextTypes
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

PLANS = {
    "basic":  {"name": "Basic",  "rub": 1000,  "stars": 500,  "label": "СТАРТ",    "desc": "~600 фото, ~30 видео, все модели",               "emoji": "🔵"},
    "pro":    {"name": "Pro",    "rub": 3000,  "stars": 1500, "label": "ХИТ ⭐",   "desc": "~1900 фото, ~100 видео, Nano Banana, Veo, Kling", "emoji": "🟢"},
    "elite":  {"name": "Elite",  "rub": 6000,  "stars": 3000, "label": "ПРО",      "desc": "~3200 фото 30+ моделей, ~600 видео HD",           "emoji": "🟣"},
    "max":    {"name": "Max",    "rub": 12000, "stars": 6000, "label": "МАКСИМУМ", "desc": "~6500 фото, ~1500 видео, приоритет моделей",       "emoji": "🟡"},
}

keys_store = {}

def generate_key(plan_id: str, user_id: int) -> str:
    key = f"ELSPY-{plan_id.upper()}-{secrets.token_hex(6).upper()}"
    keys_store[key] = {
        "plan": plan_id,
        "user_id": user_id,
        "rub": PLANS[plan_id]["rub"],
        "created_at": datetime.now().isoformat(),
        "used": False
    }
    return key

def plans_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(
            f"{p['emoji']} {p['name']} — {p['rub']}₽  ({p['stars']} ⭐)",
            callback_data=f"buy_{pid}"
        )])
    return InlineKeyboardMarkup(rows)

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
    await update.message.reply_text(
        "💳 *Выбери тариф:*",
        parse_mode="Markdown",
        reply_markup=plans_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("buy_"):
        pid = query.data[4:]
        p = PLANS.get(pid)
        if not p:
            return
        await query.message.reply_text(
            f"{p['emoji']} *{p['name']}* — {p['label']}\n\n"
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

    key = generate_key(pid, user_id)
    logger.info(f"Payment: user={user_id}, plan={pid}, key={key}")

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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("ElSpy Pay bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

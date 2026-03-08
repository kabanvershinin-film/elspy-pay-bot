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
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
SBP_PHONE = os.environ.get("SBP_PHONE", "+7XXXXXXXXXX")  # Твой номер СБП
SBP_NAME  = os.environ.get("SBP_NAME", "Евгений В.")     # Имя получателя

PLANS = {
    "basic":  {"name": "Basic",  "rub": 1000,  "stars": 500,  "desc": "~600 фото, ~30 видео, все модели",               "emoji": "🔵"},
    "pro":    {"name": "Pro",    "rub": 3000,  "stars": 1500, "desc": "~1900 фото, ~100 видео, Nano Banana, Veo, Kling", "emoji": "🟢"},
    "elite":  {"name": "Elite",  "rub": 6000,  "stars": 3000, "desc": "~3200 фото 30+ моделей, ~600 видео HD",           "emoji": "🟣"},
    "max":    {"name": "Max",    "rub": 12000, "stars": 6000, "desc": "~6500 фото, ~1500 видео, приоритет моделей",       "emoji": "🟡"},
}

KEYS_FILE = "/tmp/keys.json"
PENDING_FILE = "/tmp/pending.json"

def load_keys():
    try:
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"basic": [], "pro": [], "elite": [], "max": []}

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f)

def load_pending():
    try:
        with open(PENDING_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_pending(pending):
    with open(PENDING_FILE, "w") as f:
        json.dump(pending, f)

def is_admin(user_id):
    return user_id == ADMIN_ID

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
        rows.append([InlineKeyboardButton(f"{p['emoji']} {p['name']}", callback_data=f"addkey_{pid}")])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)

def delkeys_keyboard():
    rows = []
    for pid, p in PLANS.items():
        rows.append([InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"delkey_{pid}")])
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

    # ── ADMIN ──
    if query.data == "admin_addkeys" and is_admin(uid):
        await query.message.edit_text("➕ *Добавить ключи*\n\nВыбери тариф:", parse_mode="Markdown", reply_markup=addkeys_keyboard())

    elif query.data == "admin_keys" and is_admin(uid):
        keys = load_keys()
        text = "📊 *Остаток ключей:*\n\n"
        for pid, p in PLANS.items():
            count = len(keys.get(pid, []))
            emoji = "✅" if count > 0 else "❌"
            text += f"{emoji} *{p['name']}*: {count} шт\n"
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    elif query.data == "admin_pending" and is_admin(uid):
        pending = load_pending()
        if not pending:
            await query.message.edit_text("✅ Нет ожидающих оплат", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))
            return
        text = f"⏳ *Ожидают подтверждения: {len(pending)}*\n\nПроверь личные сообщения — там кнопки подтверждения."
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    elif query.data == "admin_delkeys" and is_admin(uid):
        await query.message.edit_text("🗑 *Очистить ключи*\n\nВыбери тариф:", parse_mode="Markdown", reply_markup=delkeys_keyboard())

    elif query.data == "admin_back" and is_admin(uid):
        await query.message.edit_text("👁 *ElSpy Pay* — Панель управления\n\nВыбери действие:", parse_mode="Markdown", reply_markup=admin_keyboard())

    elif query.data.startswith("addkey_") and is_admin(uid):
        pid = query.data[7:]
        context.user_data["adding_key_plan"] = pid
        p = PLANS[pid]
        await query.message.edit_text(
            f"➕ *Добавить ключ — {p['name']}*\n\nОтправь ключи следующим сообщением.\nМожно несколько — каждый с новой строки:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="admin_back")]])
        )

    elif query.data.startswith("delkey_") and is_admin(uid):
        pid = query.data[7:]
        keys = load_keys()
        keys[pid] = []
        save_keys(keys)
        await query.message.edit_text(f"✅ Ключи тарифа *{PLANS[pid]['name']}* очищены", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]))

    # ── ADMIN CONFIRM/REJECT ──
    elif query.data.startswith("confirm_") and is_admin(uid):
        order_id = query.data[8:]
        pending = load_pending()
        if order_id not in pending:
            await query.message.edit_caption("❌ Заявка не найдена (уже обработана?)")
            return
        order = pending[order_id]
        pid = order["plan"]
        user_id = order["user_id"]
        p = PLANS[pid]

        keys = load_keys()
        if not keys.get(pid):
            await query.message.edit_caption("❌ Ключи закончились! Добавь ключи и подтверди вручную.")
            return

        key = keys[pid].pop(0)
        save_keys(keys)
        del pending[order_id]
        save_pending(pending)

        await query.message.edit_caption(f"✅ Подтверждено! Ключ `{key}` отправлен пользователю {user_id}", parse_mode="Markdown")

        await context.bot.send_message(
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
        pending = load_pending()
        if order_id not in pending:
            await query.message.edit_caption("❌ Заявка не найдена")
            return
        order = pending[order_id]
        user_id = order["user_id"]
        del pending[order_id]
        save_pending(pending)

        await query.message.edit_caption(f"❌ Заявка отклонена. Уведомление отправлено пользователю {user_id}")
        await context.bot.send_message(
            user_id,
            "❌ *Оплата не подтверждена.*\n\nВозможно скрин нечёткий или сумма не совпадает.\nНапиши в поддержку если есть вопросы.",
            parse_mode="Markdown"
        )

    # ── USER ──
    elif query.data.startswith("buy_"):
        pid = query.data[4:]
        p = PLANS.get(pid)
        if not p:
            return
        context.user_data["selected_plan"] = pid
        await query.message.reply_text(
            f"{p['emoji']} *{p['name']}* — {p['rub']}₽\n\n"
            f"💳 *Оплата через СБП:*\n"
            f"🏦 Банк: Сбербанк\n"
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

    pending = load_pending()
    pending[order_id] = {"plan": pid, "user_id": uid, "username": user.username or str(uid)}
    save_pending(pending)

    context.user_data.pop("selected_plan", None)

    await update.message.reply_text(
        "⏳ *Скрин получен!*\n\nОжидай подтверждения — обычно до 5 минут.",
        parse_mode="Markdown"
    )

    # Уведомляем админа
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
            InlineKeyboardButton("❌ Отклонить",  callback_data=f"reject_{order_id}")
        ]])
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id

    if is_admin(uid) and "adding_key_plan" in context.user_data:
        pid = context.user_data.pop("adding_key_plan")
        p = PLANS[pid]
        new_keys = [k.strip() for k in update.message.text.strip().splitlines() if k.strip()]
        keys = load_keys()
        keys[pid].extend(new_keys)
        save_keys(keys)
        await update.message.reply_text(
            f"✅ Добавлено *{len(new_keys)}* ключей для *{p['name']}*\nВсего: *{len(keys[pid])}* шт",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
        return

    await update.message.reply_text(
        "📸 Отправь *скриншот* оплаты или выбери тариф:",
        parse_mode="Markdown",
        reply_markup=plans_keyboard()
    )

async def pin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.message.from_user.id):
        return
    msg = await update.message.reply_text(
        "👁 *ElSpy AI — Пополнение баланса*\n\n"
        "Оплачивай через СБП и получай ключ активации.\n\n"
        "🔵 Basic — 1000₽\n"
        "🟢 Pro — 3000₽\n"
        "🟣 Elite — 6000₽\n"
        "🟡 Max — 12000₽\n\n"
        "💡 Баланс не сгорает!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 Пополнить баланс", url="https://t.me/elspy_pay_bot?start=pay")
        ]])
    )
    await context.bot.pin_chat_message(chat_id=update.message.chat_id, message_id=msg.message_id)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Помощь*\n\n/start — главное меню\n/help — помощь\n\nПоддержка: @elspy\\_support",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("pin", pin_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("ElSpy Pay bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

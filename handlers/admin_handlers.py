# handlers/admin_handlers.py
import os
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import asyncio
from db.mongo_client import db
from api.brawl_api import get_player
from utils.time_utils import format_moscow_date

ADMIN_ID = int(os.getenv("ADMIN_USER_ID")) if os.getenv("ADMIN_USER_ID") else None

WAITING_FOR_SEASON_START, WAITING_FOR_SEASON_END, WAITING_FOR_NORM = range(3)

async def admin_only(update: Update):
    if update.effective_user.id != ADMIN_ID:
        return False
    return True

# --- /ACK ---
async def ack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    pending = list(db.users.find({"status": "pending"}))
    if not pending:
        await update.message.reply_text("✅ Нет ожидающих подтверждения.")
        return

    text = "🐻 МЕДВЕЖАТА | ОЖИДАЮЩИЕ ПОДТВЕРЖДЕНИЯ 🐾\n\n"
    buttons = []
    for u in pending:
        name = u['real_name']
        tag = u['bs_tag']
        username = u.get('tg_username', '—')
        text += f"🧑‍🦰 {name} (#{tag}) — @{username}\n"
        buttons.append(InlineKeyboardButton(name, callback_data=f"ack_user_{u['tg_id']}"))

    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="ack_back")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def ack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("ack_user_"):
        tg_id = int(data.split("_")[-1])
        user = db.users.find_one({"tg_id": tg_id})
        if not user:
            await query.edit_message_text("❌ Пользователь не найден.")
            return

        keyboard = [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"approve_{tg_id}"),
                InlineKeyboardButton("🔍 Кто это?", callback_data=f"whois_{user['bs_tag']}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{tg_id}")
            ]
        ]
        msg = f"Управление: {user['real_name']} (#{user['bs_tag']})"
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

# --- Approve/Reject/Whois ---
async def approve_reject_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("approve_"):
        tg_id = int(data.split("_")[1])
        db.users.update_one({"tg_id": tg_id}, {"$set": {"status": "approved"}})
        try:
            await context.bot.send_message(tg_id, "✅ Поздравляем! Вы приняты в клуб «МЕДВЕЖАТА»! 🎉\nТеперь доступны все команды.")
        except:
            pass
        await query.edit_message_text("✅ Пользователь принят.")

    elif data.startswith("reject_"):
        tg_id = int(data.split("_")[1])
        db.users.update_one({"tg_id": tg_id}, {"$set": {"status": "rejected"}})
        try:
            await context.bot.send_message(tg_id, "❌ Ваша регистрация отклонена администратором.")
        except:
            pass
        await query.edit_message_text("❌ Пользователь отклонён.")

    elif data.startswith("whois_"):
        bs_tag = data.split("_", 1)[1]
        try:
            player = await asyncio.to_thread(get_player, bs_tag)
            msg = (
                f"🔍 Информация об игроке:\n"
                f"Ник: {player['name']}\n"
                f"Тег: #{bs_tag}\n"
                f"Трофеи: {player['trophies']}\n"
                f"Клуб: {player.get('club', {}).get('name', '—')}"
            )
            await query.message.reply_text(msg)
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка: {e}")

# --- /history ---
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    events = list(db.club_history.find().sort("timestamp", -1).limit(20))
    if not events:
        await update.message.reply_text("📜 История пуста.")
        return

    text = "🐻 МЕДВЕЖАТА | ИСТОРИЯ 📜\n\n"
    for e in events:
        dt = format_moscow_date(e["timestamp"])
        event_text = "присоединился к клубу 🐾" if e["event"] == "joined" else "покинул клуб ❌"
        text += f"{dt} — {e['name']} (#{e['bs_tag']}) {event_text}\n"

    await update.message.reply_text(text)

# --- /we ---
async def we(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return

    users = list(db.users.find({"status": "approved"}))
    if not users:
        await update.message.reply_text("👥 Нет участников.")
        return

    buttons = [InlineKeyboardButton(u["real_name"], callback_data=f"we_user_{u['tg_id']}") for u in users]
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    await update.message.reply_text("Выберите игрока:", reply_markup=InlineKeyboardMarkup(keyboard))

async def we_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = int(query.data.split("_")[-1])

    user = db.users.find_one({"tg_id": tg_id})
    if not user:
        await query.edit_message_text("❌ Не найден.")
        return

    keyboard = [
        [InlineKeyboardButton("📏 Изменить норму", callback_data=f"we_norm_{tg_id}")],
        [InlineKeyboardButton("🚫 Удалить из бота", callback_data=f"we_del_{tg_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="we_back")]
    ]
    await query.edit_message_text(f"Управление: {user['real_name']}", reply_markup=InlineKeyboardMarkup(keyboard))

async def we_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("we_norm_"):
        tg_id = int(data.split("_")[-1])
        context.user_data["editing_user"] = tg_id
        await query.edit_message_text("Введите новую норму (число):")
        return 1  # state

    elif data.startswith("we_del_"):
        tg_id = int(data.split("_")[-1])
        db.users.delete_one({"tg_id": tg_id})
        db.players_cache.delete_one({"bs_tag": db.users.find_one({"tg_id": tg_id})["bs_tag"]})
        await query.edit_message_text("✅ Удалено.")

# --- /season ---
async def season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update):
        return
    await update.message.reply_text("Введите дату начала сезона (дд.мм.гггг):")
    return WAITING_FOR_SEASON_START

# (Остальной код /season опущён для краткости — можно реализовать по аналогии)

# --- Register handlers ---
__all__ = [
    "ack", "ack_callback", "approve_reject_whois",
    "history", "we", "we_callback", "we_action",
    "season"
]
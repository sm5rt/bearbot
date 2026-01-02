# handlers/user_handlers.py
import os
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import asyncio
from db.mongo_client import db
from utils.validators import is_valid_tag, clean_tag, is_in_club
from utils.season import get_season_config, days_until_end
from utils.time_utils import format_moscow_date

WAITING_FOR_SEASON_START, WAITING_FOR_SEASON_END, WAITING_FOR_NORM = range(3)

def get_user_status(tg_id):
    user = db.users.find_one({"tg_id": tg_id})
    return user.get("status") if user else None

def send_photo_or_text(update, context, photo_name, caption):
    photo_path = f"assets/{photo_name}"
    try:
        with open(photo_path, "rb") as f:
            return update.message.reply_photo(photo=f, caption=caption)
    except FileNotFoundError:
        return update.message.reply_text(caption)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = (
        "🐻 МЕДВЕЖАТА | Brawl Stars\n\n"
        "🔥 Добро пожаловать в бот клуба «МЕДВЕЖАТА»!\n\n"
        "📌 Зарегистрируйся: /register Имя #Тег\n"
        "❓ Справка: /help"
    )
    await send_photo_or_text(update, context, "start.jpg", caption)

# --- /help ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🐻 МЕДВЕЖАТА | СПРАВКА 📚\n\n"
        "📌 /register — начать регистрацию\n"
        "🧭 /navigator — меню команд\n"
        "🧑‍🦰 /me — мой профиль\n"
        "👥 /you — профиль другого\n"
        "🏆 /top — рейтинги\n"
        "🏡 /club — информация о клубе"
    )
    await send_photo_or_text(update, context, "help.jpg", text)

# --- /register ---
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используй: /register ИмяВЖизни #Тег")
        return

    real_name = " ".join(args[:-1])
    tag = args[-1]

    if not is_valid_tag(tag):
        await update.message.reply_text("❌ Неверный формат тега. Пример: #2GJ9YJUQ")
        return

    clean_bs_tag = clean_tag(tag)

    if not await asyncio.to_thread(is_in_club, clean_bs_tag):
        await update.message.reply_text("❌ Игрок не состоит в клубе «МЕДВЕЖАТА»!")
        return

    user = update.effective_user
    db.users.update_one(
        {"tg_id": user.id},
        {
            "$set": {
                "tg_id": user.id,
                "tg_username": user.username,
                "real_name": real_name,
                "bs_tag": clean_bs_tag,
                "status": "pending",
                "join_bot_date": datetime.now(timezone.utc),
                "join_club_date": datetime.now(timezone.utc)  # будет обновлено при первом входе
            }
        },
        upsert=True
    )

    # Уведомление админу
    admin_id = os.getenv("ADMIN_USER_ID")
    if admin_id:
        try:
            keyboard = [
                [
                    InlineKeyboardButton("✅ Принять", callback_data=f"approve_{user.id}"),
                    InlineKeyboardButton("🔍 Кто это?", callback_data=f"whois_{clean_bs_tag}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}")
                ]
            ]
            msg = (
                f"🐻 МЕДВЕЖАТА | РЕГИСТРАЦИЯ\n"
                f"Имя: {real_name}\n"
                f"Тег: #{clean_bs_tag}\n"
                f"Telegram: @{user.username or '—'}\n"
                f"Дата запроса: {format_moscow_date(datetime.now(timezone.utc))}\n\n"
                f"👉 Выберите действие:"
            )
            await context.bot.send_message(
                chat_id=int(admin_id),
                text=msg,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logging.error(f"Не удалось отправить админу: {e}")

    await send_photo_or_text(
        update, context, "register.jpg",
        "✅ Запрос на регистрацию отправлен!\n\n"
        "⏳ Ожидайте подтверждения от администратора."
    )

# --- /navigator ---
async def navigator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_status(update.effective_user.id) != "approved":
        await update.message.reply_text(
            "❌ Сначала зарегистрируйся и дождись подтверждения админа! Используй /register"
        )
        return

    keyboard = [
        [InlineKeyboardButton("🧑‍🦰 /me", callback_data="nav_me")],
        [InlineKeyboardButton("👥 /you", callback_data="nav_you")],
        [InlineKeyboardButton("🏆 /top", callback_data="nav_top")],
        [InlineKeyboardButton("🏡 /club", callback_data="nav_club")],
        [InlineKeyboardButton("❓ /help", callback_data="nav_help")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="nav_back")]
    ]
    await send_photo_or_text(
        update, context, "navigator.jpg",
        "🐻 МЕДВЕЖАТА | НАВИГАТОР 🧭\nВыбери, куда отправимся:"
    )
    await update.message.reply_text("Меню:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- /me ---
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_status(update.effective_user.id) != "approved":
        await update.message.reply_text("❌ Сначала зарегистрируйся и дождись подтверждения.")
        return

    user = db.users.find_one({"tg_id": update.effective_user.id})
    cache = db.players_cache.find_one({"bs_tag": user["bs_tag"]})
    if not cache:
        await update.message.reply_text("⚠️ Данные ещё не загружены. Попробуй через минуту.")
        return

    config = get_season_config()
    norm = user.get("custom_norm", config["base_norm"])
    current = cache["trophies"]
    # В реальности — нужно хранить trophies_at_join
    progress = current  # временно
    percent = min(100, round(progress / norm * 100)) if norm > 0 else 0

    if progress >= norm:
        status_emoji = "✅"
        status_text = "Да"
    elif progress > 0:
        status_emoji = "⚠️"
        status_text = "Нет"
    else:
        status_emoji = "❌"
        status_text = "Нет"

    days, hours = days_until_end()

    text = (
        f"🐻 МЕДВЕЖАТА | МОЙ ПРОФИЛЬ 🐻\n\n"
        f"📅 ОСНОВНАЯ ИНФОРМАЦИЯ:\n"
        f"Имя: {user['real_name']} 🎯\n"
        f"Имя в Telegram: {update.effective_user.first_name} 🐾\n"
        f"Username: @{update.effective_user.username or '—'}\n"
        f"ID: {update.effective_user.id}\n"
        f"В боте с: {format_moscow_date(user['join_bot_date'])} 📅\n\n"
        f"🎮 ИГРОВАЯ ИНФОРМАЦИЯ:\n"
        f"Ник в игре: {cache['name']} 🐻\n"
        f"ID аккаунта: #{user['bs_tag']}\n"
        f"Клуб: «МЕДВЕЖАТА» 🛡️\n"
        f"В клубе с: {format_moscow_date(user.get('join_club_date', user['join_bot_date']))} 📆\n\n"
        f"📊 СЕЗОННАЯ СТАТИСТИКА:\n"
        f"Норма трофеев: {norm} 🎯\n"
        f"Начало сезона: 0 кубков 📈\n"
        f"Текущий прогресс: {current} кубков (+{progress}) 🚀\n"
        f"Норма выполнена: {status_emoji} {status_text}\n"
        f"Дней до конца сезона: {days} дней ({hours} часов) ⏳"
    )
    await send_photo_or_text(update, context, "me.jpg", text)

# --- /you ---
async def you(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_status(update.effective_user.id) != "approved":
        await update.message.reply_text("❌ Сначала зарегистрируйся и дождись подтверждения.")
        return

    if not context.args:
        await update.message.reply_text("Используй: /you @username или /you #Тег")
        return

    query = context.args[0]
    db_user = None

    if query.startswith("@"):
        db_user = db.users.find_one({"tg_username": query[1:], "status": "approved"})
    elif query.startswith("#"):
        clean_tag = clean_tag(query)
        db_user = db.users.find_one({"bs_tag": clean_tag, "status": "approved"})
    else:
        await update.message.reply_text("❌ Используй @username или #Тег")
        return

    if not db_user:
        await update.message.reply_text("❌ Игрок не найден или не подтверждён.")
        return

    cache = db.players_cache.find_one({"bs_tag": db_user["bs_tag"]})
    if not cache:
        await update.message.reply_text("⚠️ Данные ещё не загружены.")
        return

    config = get_season_config()
    norm = db_user.get("custom_norm", config["base_norm"])
    current = cache["trophies"]
    progress = current
    percent = min(100, round(progress / norm * 100)) if norm > 0 else 0

    if progress >= norm:
        status_emoji = "✅"
        status_text = "Да"
    else:
        status_emoji = "❌"
        status_text = "Нет"

    days, hours = days_until_end()

    text = (
        f"🐻 МЕДВЕЖАТА | ПРОФИЛЬ [{cache['name']}] 🐾\n\n"
        f"📅 ОСНОВНАЯ ИНФОРМАЦИЯ:\n"
        f"Имя: {db_user['real_name']} 🎯\n"
        f"Имя в Telegram: {cache['name']} 🐾\n"
        f"Username: @{db_user.get('tg_username', '—')}\n"
        f"ID: {db_user['tg_id']}\n"
        f"В боте с: {format_moscow_date(db_user['join_bot_date'])} 📅\n\n"
        f"🎮 ИГРОВАЯ ИНФОРМАЦИЯ:\n"
        f"Ник в игре: {cache['name']} 🐻\n"
        f"ID аккаунта: #{db_user['bs_tag']}\n"
        f"Клуб: «МЕДВЕЖАТА» 🛡️\n"
        f"В клубе с: {format_moscow_date(db_user.get('join_club_date', db_user['join_bot_date']))} 📆\n\n"
        f"📊 СЕЗОННАЯ СТАТИСТИКА:\n"
        f"Норма трофеев: {norm} 🎯\n"
        f"Начало сезона: 0 кубков 📈\n"
        f"Текущий прогресс: {current} кубков (+{progress}) 🚀\n"
        f"Норма выполнена: {status_emoji} {status_text}\n"
        f"Дней до конца сезона: {days} дней ({hours} часов) ⏳"
    )
    await send_photo_or_text(update, context, "you.jpg", text)

# --- /top ---
TOP_STATE = 0
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_status(update.effective_user.id) != "approved":
        await update.message.reply_text("❌ Сначала зарегистрируйся и дождись подтверждения.")
        return

    # Собираем игроков
    users = list(db.users.find({"status": "approved"}))
    players = []
    for u in users:
        cache = db.players_cache.find_one({"bs_tag": u["bs_tag"]})
        if not cache:
            continue
        norm = u.get("custom_norm", get_season_config()["base_norm"])
        progress = cache["trophies"]  # временно
        players.append({
            "name": cache["name"],
            "tag": u["bs_tag"],
            "trophies": cache["trophies"],
            "progress": progress,
            "percent": min(100, round(progress / norm * 100)) if norm > 0 else 0
        })

    # Сортируем по кубкам
    players.sort(key=lambda x: x["trophies"], reverse=True)
    lines = []
    for i, p in enumerate(players[:10]):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        lines.append(f"{medal} [{p['name']}](bs://%23{p['tag']}) — {p['trophies']}")

    text = "🐻 МЕДВЕЖАТА | ТОП ПО КУБКАМ 🏆\n\n" + "\n".join(lines)
    keyboard = [
        [InlineKeyboardButton("➡️ Перейти к прогрессу", callback_data="top_progress")],
        [InlineKeyboardButton("🏠 Вернуться в /navigator", callback_data="nav_back")]
    ]
    context.user_data["top_players"] = players
    await send_photo_or_text(update, context, "top.jpg", text)
    await update.message.reply_text("Выберите:", reply_markup=InlineKeyboardMarkup(keyboard))

async def top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "top_progress":
        players = context.user_data.get("top_players", [])
        players.sort(key=lambda x: x["percent"], reverse=True)
        lines = []
        for i, p in enumerate(players[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} [{p['name']}](bs://%23{p['tag']}) — +{p['progress']} ({p['percent']}%)")

        text = "🐻 МЕДВЕЖАТА | ТОП ПО ПРОГРЕССУ 📊\n\n" + "\n".join(lines)
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к кубкам", callback_data="top_trophies")],
            [InlineKeyboardButton("🏠 Вернуться в /navigator", callback_data="nav_back")]
        ]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "top_trophies":
        players = context.user_data.get("top_players", [])
        players.sort(key=lambda x: x["trophies"], reverse=True)
        lines = []
        for i, p in enumerate(players[:10]):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} [{p['name']}](bs://%23{p['tag']}) — {p['trophies']}")

        text = "🐻 МЕДВЕЖАТА | ТОП ПО КУБКАМ 🏆\n\n" + "\n".join(lines)
        keyboard = [
            [InlineKeyboardButton("➡️ Перейти к прогрессу", callback_data="top_progress")],
            [InlineKeyboardButton("🏠 Вернуться в /navigator", callback_data="nav_back")]
        ]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- /club ---
async def club(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_status(update.effective_user.id) != "approved":
        await update.message.reply_text("❌ Сначала зарегистрируйся и дождись подтверждения.")
        return

    users = list(db.users.find({"status": "approved"}))
    config = get_season_config()
    done = sum(1 for u in users if db.players_cache.find_one({"bs_tag": u["bs_tag"]}, {"trophies": 1}) is not None)

    days, hours = days_until_end()

    text = (
        "🐻 МЕДВЕЖАТА | ИНФОРМАЦИЯ О КЛУБЕ 🛡️\n\n"
        "🏷️ Название: «МЕДВЕЖАТА»\n"
        f"🏷️ Тег: #{os.getenv('CLUB_TAG')}\n"
        f"👥 Участников: {len(users)} (0 онлайн) 🐾\n\n"
        "🏆 Трофеи клуба: 0 (+0 за сезон) 📈\n"
        f"✅ Норму выполнили: {done} из {len(users)} игроков (0%) 🎯\n\n"
        f"📆 Сезон:\n"
        f"Начало: {config['start_date'].strftime('%d.%m.%Y')}\n"
        f"Конец: {config['end_date'].strftime('%d.%m.%Y')}\n"
        f"До конца: {days} дней ({hours} часов) ⏳\n\n"
        "🔥 Держим планку! Медвежья сила в единстве! 🐻💪"
    )
    await send_photo_or_text(update, context, "club.jpg", text)

# Navigation callbacks
async def nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav_me":
        await me(update, context)
    elif data == "nav_you":
        await update.effective_message.reply_text("Используй: /you @username или /you #Тег")
    elif data == "nav_top":
        await top(update, context)
    elif data == "nav_club":
        await club(update, context)
    elif data == "nav_help":
        await help_command(update, context)
    elif data == "nav_back":
        await query.edit_message_text("🧭 Вернулись в предыдущее меню.")

# --- Export handlers
__all__ = [
    "start", "help_command", "register", "navigator", "me", "you", "top", "club",
    "top_callback", "nav_callback"
]
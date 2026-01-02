# jobs/club_monitor.py
import asyncio
import logging
from datetime import datetime, timezone
from api.brawl_api import get_club_members
from db.mongo_client import db
import os

CLUB_TAG = os.getenv("CLUB_TAG")

async def check_club_changes(context):
    """
    Проверяет изменения в составе клуба каждые 5 минут.
    """
    try:
        logging.info("🔁 Запуск check_club_changes...")
        current_members = await asyncio.to_thread(get_club_members, CLUB_TAG)
        current_tags = {m["tag"][1:]: m for m in current_members}

        # Получаем предыдущий состав из БД
        prev_docs = list(db.club_members.find())
        prev_tags = {doc["bs_tag"]: doc for doc in prev_docs}

        # Логируем новых участников
        for tag, data in current_tags.items():
            if tag not in prev_tags:
                db.club_history.insert_one({
                    "bs_tag": tag,
                    "name": data["name"],
                    "event": "joined",
                    "timestamp": datetime.now(timezone.utc)
                })
                logging.info(f"🆕 {data['name']} ({tag}) присоединился к клубу.")

                # Обновляем дату вступления у пользователя
                db.users.update_one(
                    {"bs_tag": tag},
                    {"$set": {"join_club_date": datetime.now(timezone.utc)}}
                )

        # Логируем вышедших и удаляем из бота
        for tag, doc in prev_tags.items():
            if tag not in current_tags:
                db.club_history.insert_one({
                    "bs_tag": tag,
                    "name": doc["name"],
                    "event": "left",
                    "timestamp": datetime.now(timezone.utc)
                })
                logging.info(f"🚪 {doc['name']} ({tag}) покинул клуб. Удаляем из бота...")
                # Удаляем пользователя из всех коллекций
                db.users.delete_one({"bs_tag": tag})
                db.players_cache.delete_one({"bs_tag": tag})

        # Обновляем актуальный состав
        db.club_members.delete_many({})
        db.club_members.insert_many([
            {
                "bs_tag": m["tag"][1:],
                "name": m["name"],
                "trophies": m["trophies"],
                "last_seen": datetime.now(timezone.utc)
            }
            for m in current_members
        ])
        logging.info("✅ Состав клуба обновлён.")

    except Exception as e:
        logging.error(f"❌ Ошибка в check_club_changes: {e}", exc_info=True)

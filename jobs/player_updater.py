# jobs/player_updater.py
import asyncio
import logging
from datetime import datetime, timezone
from api.brawl_api import get_player
from db.mongo_client import db

async def update_players_cache(context):
    """
    Обновляет кэш данных игроков каждые 5 минут.
    """
    try:
        logging.info("🔁 Запуск update_players_cache...")
        users = list(db.users.find({"status": "approved"}))
        for user in users:
            try:
                player_data = await asyncio.to_thread(get_player, user["bs_tag"])
                db.players_cache.update_one(
                    {"bs_tag": user["bs_tag"]},
                    {
                        "$set": {
                            "bs_tag": user["bs_tag"],
                            "name": player_data["name"],
                            "trophies": player_data["trophies"],
                            "club_tag": player_data.get("club", {}).get("tag", "")[1:] if player_data.get("club") else None,
                            "last_updated": datetime.now(timezone.utc)
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                logging.error(f"❌ Не удалось обновить игрока {user['bs_tag']}: {e}")
        logging.info("✅ Кэш игроков обновлён.")
    except Exception as e:
        logging.error(f"❌ Ошибка в update_players_cache: {e}", exc_info=True)

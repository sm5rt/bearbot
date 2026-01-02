# utils/season.py
from datetime import datetime, timezone
from db.mongo_client import db
import os

def get_season_config():
    config = db.season_config.find_one({"_id": "current"})
    if not config:
        config = {
            "_id": "current",
            "start_date": datetime(2025, 12, 1, tzinfo=timezone.utc),
            "end_date": datetime(2026, 1, 15, 23, 59, 59, tzinfo=timezone.utc),
            "base_norm": int(os.getenv("NORM", "3000"))
        }
        db.season_config.insert_one(config)
    return config

def days_until_end():
    config = get_season_config()
    now = datetime.now(timezone.utc)
    if now > config["end_date"]:
        return 0, 0
    delta = config["end_date"] - now
    days = delta.days
    hours = int(delta.total_seconds() // 3600)
    return days, hours
# utils/time_utils.py
from datetime import datetime, timezone, timedelta

def utc_to_moscow(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt + timedelta(hours=3)

def format_moscow_date(dt: datetime) -> str:
    moscow = utc_to_moscow(dt)
    return moscow.strftime("%d.%m.%Y %H:%M")
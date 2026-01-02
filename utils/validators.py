# utils/validators.py
import re
from api.brawl_api import get_club_members
import os

CLUB_TAG = os.getenv("CLUB_TAG")

def is_valid_tag(tag: str) -> bool:
    if not tag.startswith("#"):
        return False
    clean = tag[1:].upper()
    return bool(re.fullmatch(r"[0-9A-Z]{6,12}", clean))

def clean_tag(tag: str) -> str:
    return tag[1:].upper() if tag.startswith("#") else tag.upper()

def is_in_club(bs_tag: str) -> bool:
    try:
        members = get_club_members(CLUB_TAG)
        return bs_tag in {m["tag"][1:] for m in members}
    except:
        return False
# api/brawl_api.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()
BRAWL_API_TOKEN = os.getenv("BRAWL_API_TOKEN")
HEADERS = {"Authorization": f"Bearer {BRAWL_API_TOKEN}"}

def get_player(tag: str):
    resp = requests.get(f"https://api.brawlstars.com/v1/players/%23{tag}", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()

def get_club_members(tag: str):
    resp = requests.get(f"https://api.brawlstars.com/v1/clubs/%23{tag}/members", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()["items"]
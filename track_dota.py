import os
import asyncio
import aiohttp
from utils import load_config, TelegramNotifier, get_current_time, log

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Missing Telegram bot token or chat ID in environment variables.")

if not STEAM_API_KEY:
    raise ValueError("Missing Steam API key in environment variables.")

notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

# Load steam user list from config.json
config = load_config()
STEAM_USERS = config.get("steam_user", {})

dota_playtime = {}

async def fetch_player_summaries():
    """Fetches Steam player summaries using the Steam API with rate-limit handling."""
    if not STEAM_USERS:
        log("No Steam users configured to track.", "warning")
        return []

    steam_ids = ",".join(STEAM_USERS.keys())
    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_ids}"

    backoff = 5  # Initial retry delay
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 429:
                        log("Rate-limited by Steam API. Retrying in {backoff} seconds...", "warning")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 60)  # Exponential backoff, max 60s
                        continue
                    if response.status != 200:
                        log(f"Steam API error: {response.status}", "error")
                        return []
                    data = await response.json()
                    return data.get("response", {}).get("players", [])
        except Exception as e:
            log(f"Error fetching Steam data: {e}", "error")
            return []

async def track_dota_playtime():
    """Tracks the playtime of Dota 2 players."""
    while True:
        players = await fetch_player_summaries()
        if not players:
            await asyncio.sleep(60)
            continue

        for player in players:
            steam_id = player["steamid"]
            game = player.get("gameextrainfo", None)
            nickname = STEAM_USERS.get(steam_id, f"Unknown ({steam_id})")

            if game == "Dota 2":
                if steam_id not in dota_playtime:
                    dota_playtime[steam_id] = {"start_time": get_current_time(), "total": 0}
                    log(f"{nickname} started playing Dota 2.")

            elif steam_id in dota_playtime:
                start_time = dota_playtime[steam_id]["start_time"]
                play_duration = (get_current_time() - start_time).total_seconds() / 3600
                dota_playtime[steam_id]["total"] += play_duration
                total_playtime = round(dota_playtime[steam_id]["total"], 2)

                log(f"{nickname} stopped playing. Total session time: {round(play_duration, 2)} hours. Total: {total_playtime} hours.")
                
                dota_playtime.pop(steam_id)

        await asyncio.sleep(60)

async def send_daily_report():
    """Sends a daily playtime report at 08:00 AM (server time)."""
    while True:
        now = get_current_time()
        if now.hour == 8 and now.minute == 0:
            message = "*Dota 2 Playtime Yesterday*\n"
            for steam_id, data in dota_playtime.items():
                nickname = STEAM_USERS.get(steam_id, f"Unknown ({steam_id})")
                total_playtime = round(data["total"], 2)
                message += f"- *{nickname}:* {total_playtime} hours\n"

            if dota_playtime:
                await notifier.send_message(message)
                log("Sent daily playtime report.")

            dota_playtime.clear()

        await asyncio.sleep(60)

async def start_track_dota():
    """Starts tracking and sending reports."""
    await asyncio.gather(track_dota_playtime(), send_daily_report())

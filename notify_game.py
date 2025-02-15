import os
import aiohttp
import asyncio
import random
from utils import log, TelegramNotifier

# Load required environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Missing Telegram bot token or chat ID in environment variables.")

notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
player_status = {}

# Steam users should still come from config.json
from utils import load_config
config = load_config()
STEAM_USERS = config.get("steam_user", {})

async def fetch_player_summaries():
    """Fetches Steam player summaries using the Steam API with rate limiting."""
    if not STEAM_USERS:
        log("No Steam users configured to track.", "warning")
        return []

    steam_ids = ",".join(STEAM_USERS.keys())

    if not STEAM_API_KEY:
        log("Missing Steam API key in environment variables.", "error")
        return []

    url = f"http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_ids}"

    retries = 5
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", {}).get("players", [])
                    elif response.status == 429:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        log(f"Rate limited. Retrying in {wait_time:.2f} seconds...", "warning")
                        await asyncio.sleep(wait_time)
                    else:
                        log(f"Steam API error: {response.status} - {await response.text()}", "error")
        except Exception as e:
            log(f"Error fetching Steam data: {e}", "error")
        await asyncio.sleep(1)  # Small delay before retrying
    return []

async def check_game_status():
    """Checks and notifies when a player starts playing a game."""
    while True:
        players = await fetch_player_summaries()
        if not players:
            log("No players found or failed to fetch data. Retrying in 60s.", "warning")
            await asyncio.sleep(60)
            continue

        for player in players:
            steam_id = player["steamid"]
            game = player.get("gameextrainfo", None)
            nickname = STEAM_USERS.get(steam_id, f"Unknown ({steam_id})")

            # First-time check, store the game status without notifying
            if steam_id not in player_status:
                player_status[steam_id] = game
                continue  

            previous_game = player_status[steam_id]

            if game and game != previous_game:
                log(f"{nickname} is now playing {game}.", "info")
                await notifier.send_message(f"*{nickname}* is now playing *{game}*.")

            player_status[steam_id] = game

        await asyncio.sleep(60)

async def start_notify_game():
    """Starts the game notification loop."""
    log("Starting Steam game status tracking...", "info")
    await check_game_status()

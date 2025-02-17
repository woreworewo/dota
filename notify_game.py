import os
import aiohttp
import asyncio
import random
from utils import log, TelegramNotifier, load_config

# Load required environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Missing Telegram bot token or chat ID in environment variables.")

if not STEAM_API_KEY:
    raise ValueError("Missing Steam API key in environment variables.")

notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
player_status = {}

# Load Steam users from config.json
config = load_config()
STEAM_USERS = config.get("steam_user", {})

async def fetch_player_summaries():
    """Fetch Steam player summaries using the Steam API with rate limiting."""
    if not STEAM_USERS:
        log("No Steam users configured to track.", "warning")
        return []

    steam_ids = ",".join(STEAM_USERS.keys())
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
    """Check and notify when a player starts playing a new game."""
    while True:
        players = await fetch_player_summaries()
        if not players:
            log("No players found or failed to fetch data. Retrying in 60s.", "warning")
            await asyncio.sleep(60)
            continue

        for player in players:
            steam_id = player.get("steamid")
            if not steam_id:
                continue

            game = player.get("gameextrainfo")
            nickname = STEAM_USERS.get(steam_id, f"Unknown ({steam_id})")

            # If it's a new player, initialize their game status in player_status
            if steam_id not in player_status:
                player_status[steam_id] = game
                continue  

            # Get the previous game status
            previous_game = player_status.get(steam_id)

            # Check if the player is playing a new game or if their game has changed
            if game != previous_game:
                if game:  # If the player is playing a game
                    log(f"{nickname} is now playing {game}.", "info")
                    await notifier.send_message(f"*{nickname}* is now playing *{game}*.")
                else:  # If the player is not playing a game
                    log(f"{nickname} is no longer playing a game.", "info")
                    await notifier.send_message(f"*{nickname}* is no longer playing a game.")

            # Update the player's game status in player_status
            player_status[steam_id] = game  

        # Wait 60 seconds before checking again
        await asyncio.sleep(60)

async def start_notify_game():
    """Start the game notification loop."""
    log("Starting Steam game status tracking...", "info")
    await check_game_status()

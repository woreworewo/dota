import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
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

# Load Steam user list from config.json
config = load_config()
STEAM_USERS = config.get("steam_user", {})

# Directory for player-specific playtime files
PLAYTIME_DIR = "playtime"

if not os.path.exists(PLAYTIME_DIR):
    os.makedirs(PLAYTIME_DIR)

# Load player-specific playtime data
def load_playtime_data(steam_id):
    file_path = os.path.join(PLAYTIME_DIR, f"{steam_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            return json.load(file)
    return {"sessions": [], "total": 0}

# Save player-specific playtime data
def save_playtime_data(steam_id, data):
    file_path = os.path.join(PLAYTIME_DIR, f"{steam_id}.json")
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)

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
                        log(f"Rate-limited by Steam API. Retrying in {backoff} seconds...", "warning")
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
    """Tracks the playtime of Dota 2 players and stores data persistently."""
    active_players = {}  # Track currently playing players with start time

    while True:
        players = await fetch_player_summaries()
        now = get_current_time()

        if not players:
            await asyncio.sleep(60)
            continue

        for player in players:
            steam_id = player["steamid"]
            game = player.get("gameextrainfo", None)
            nickname = STEAM_USERS.get(steam_id, f"Unknown ({steam_id})")
            playtime_data = load_playtime_data(steam_id)

            if "sessions" not in playtime_data:
                playtime_data["sessions"] = []
            if "total" not in playtime_data:
                playtime_data["total"] = 0

            if game == "Dota 2":
                if steam_id not in active_players:  # Prevent duplicate starts
                    active_players[steam_id] = now
                    playtime_data["sessions"].append({"start": now.isoformat()})
                    log(f"{nickname} started playing Dota 2 at {now}.")
                    save_playtime_data(steam_id, playtime_data)

            elif steam_id in active_players:
                # Player stopped playing, end session
                start_time = active_players.pop(steam_id)  # Get start time
                play_duration_seconds = (now - start_time).total_seconds()

                # Convert duration to hours, minutes, seconds
                hours = int(play_duration_seconds // 3600)
                minutes = int((play_duration_seconds % 3600) // 60)
                seconds = int(play_duration_seconds % 60)

                duration_formatted = f"{hours}h {minutes}m {seconds}s"
                play_duration_hours = round(play_duration_seconds / 3600, 2)  # Store in hours

                last_session = playtime_data["sessions"][-1]
                last_session["end"] = now.isoformat()
                last_session["duration"] = duration_formatted  # Save detailed duration
                playtime_data["total"] += play_duration_hours

                total_playtime_hours = round(playtime_data["total"], 2)
                log(f"{nickname} stopped playing. Session: {duration_formatted}. Total: {total_playtime_hours}h.")

                save_playtime_data(steam_id, playtime_data)

        await asyncio.sleep(60)

async def send_daily_report():
    """Sends a daily playtime report at 08:00 AM and removes data older than 30 days."""
    while True:
        now = get_current_time()
        if now.hour == 8 and now.minute == 0:
            message = "*Dota 2 Playtime Yesterday*\n"
            cutoff_date = now - timedelta(days=30)
            has_playtime = False  # Track if any player has non-zero playtime

            for steam_id in STEAM_USERS.keys():
                playtime_data = load_playtime_data(steam_id)

                # Remove old sessions
                playtime_data["sessions"] = [
                    s for s in playtime_data["sessions"] if datetime.fromisoformat(s["start"]) >= cutoff_date
                ]

                # Sum up the total playtime from sessions
                total_playtime_seconds = sum(
                    (datetime.fromisoformat(s["end"]) - datetime.fromisoformat(s["start"])).total_seconds()
                    for s in playtime_data["sessions"] if "end" in s
                )

                total_playtime_hours = total_playtime_seconds / 3600
                total_playtime_formatted = f"{int(total_playtime_hours)}h {int((total_playtime_hours * 60) % 60)}m {int((total_playtime_hours * 3600) % 60)}s"

                # Only include players with non-zero playtime
                if total_playtime_hours > 0:
                    nickname = STEAM_USERS.get(steam_id, f"Unknown ({steam_id})")
                    message += f"- *{nickname}:* {total_playtime_formatted}\n"
                    has_playtime = True  # At least one player has playtime

                # If no recent sessions, remove player from tracking
                if not playtime_data["sessions"]:
                    file_path = os.path.join(PLAYTIME_DIR, f"{steam_id}.json")
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            log(f"Removed old playtime data for {steam_id}.")
                        else:
                            log(f"File {file_path} not found, skipping deletion.")
                    except Exception as e:
                        log(f"Error deleting file {file_path}: {e}")

            # Send report only if at least one player has playtime
            if has_playtime:
                await notifier.send_message(message)
                log("Sent daily playtime report.")
            else:
                log("No playtime recorded, skipping report.")

        await asyncio.sleep(60)

async def start_track_dota():
    """Starts tracking and sending reports."""
    await asyncio.gather(track_dota_playtime(), send_daily_report())

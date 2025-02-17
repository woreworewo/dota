import os
import json
import logging
import aiohttp
import pytz
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load configuration
CONFIG_PATH = Path("config.json")

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    raise FileNotFoundError("config.json not found!")

config = load_config()

# Ensure required environment variables exist
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
steam_api_key = os.getenv("STEAM_API_KEY")

if not telegram_bot_token or not telegram_chat_id:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment variables.")

if not steam_api_key:
    raise ValueError("Missing STEAM_API_KEY in environment variables.")

logging_enabled = config.get("logging_enabled", True)

# Set up logging
LOG_FILE = "bot.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)

def log(message, level="info"):
    """Logs a message to the file and console."""
    if logging_enabled:
        log_func = getattr(logging, level, logging.info)
        log_func(message)
    print(message)

def steam_id_to_account_id(steam_id):
    """Converts a Steam64 ID to a Steam Account ID."""
    return int(steam_id) - 76561197960265728

def get_current_time():
    """Returns the current time based on the timezone in config.json."""
    timezone = config.get("timezone", "UTC")  # Default to UTC if missing
    return datetime.now(pytz.timezone(timezone))

# Telegram Notifier
class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or telegram_bot_token
        self.chat_id = chat_id or telegram_chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    async def send_message(self, message):
        """Send a message asynchronously to Telegram."""
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_url, json=payload) as response:
                return await response.json()

# Add a tracked player to config.json
def add_tracked_player(steam64_id, nickname):
    """Adds a player to the tracked players list."""
    try:
        config_data = load_config()
        tracked_players_64 = config_data.get("steam_user", {})
        
        if steam64_id in tracked_players_64:
            raise ValueError(f"Player with Steam64 ID {steam64_id} is already being tracked.")
        
        tracked_players_64[steam64_id] = nickname
        config_data["steam_user"] = tracked_players_64
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        
        log(f"Player {nickname} added to tracked players.")
    except Exception as e:
        log(f"Error adding player {nickname}: {e}", level="error")
        raise e

# Remove a tracked player from config.json
def remove_tracked_player(steam64_id):
    """Removes a player from the tracked players list."""
    try:
        config_data = load_config()
        tracked_players_64 = config_data.get("steam_user", {})
        
        if steam64_id not in tracked_players_64:
            raise ValueError(f"Player with Steam64 ID {steam64_id} is not tracked.")
        
        del tracked_players_64[steam64_id]
        config_data["steam_user"] = tracked_players_64
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        
        log(f"Player with Steam64 ID {steam64_id} removed from tracked players.")
    except Exception as e:
        log(f"Error removing player with Steam64 ID {steam64_id}: {e}", level="error")
        raise e

# Change a player's nickname
def change_player_nickname(nickname, new_nickname):
    """Changes the nickname of a tracked player."""
    try:
        config_data = load_config()
        tracked_players_64 = config_data.get("steam_user", {})
        
        # Find the steam64 ID corresponding to the nickname
        steam64_id = None
        for sid, name in tracked_players_64.items():
            if name == nickname:
                steam64_id = sid
                break
        
        if not steam64_id:
            raise ValueError(f"Player with nickname {nickname} is not being tracked.")
        
        tracked_players_64[steam64_id] = new_nickname
        config_data["steam_user"] = tracked_players_64
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        
        log(f"Player {nickname} renamed to {new_nickname}.")
    except Exception as e:
        log(f"Error renaming player {nickname} to {new_nickname}: {e}", level="error")
        raise e

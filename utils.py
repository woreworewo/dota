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

import os
import json
import requests
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LOG_FILE_PATH = "bot.log"

# Get values from .env
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")  # Developer group ID

if not BOT_TOKEN or not LOG_CHAT_ID:
    print("Bot token or log chat ID missing in .env. Exiting.")
    exit(1)

# Send logs to Telegram
def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": LOG_CHAT_ID,
        "text": f"*Log Update:*\n```{text}```",
        "parse_mode": "MarkdownV2"
    }
    response = requests.post(url, data=data)
    print(response.json())  # Debugging

# Monitor log file and send updates
def tail_log():
    with open(LOG_FILE_PATH, "r") as file:
        file.seek(0, os.SEEK_END)
        while True:
            line = file.readline()
            if line:
                send_to_telegram(line.strip())
            time.sleep(1)

if __name__ == "__main__":
    tail_log()

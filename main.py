import asyncio
import nest_asyncio
import os
from dotenv import load_dotenv
from cache_manager import update_cache, cache_player_data
from notify_game import start_notify_game
from track_dota import start_track_dota
from utils import log, load_config
from telegram.ext import Application
from commands import setup_command_handlers  # Import function to setup commands

# Load .env
load_dotenv()

# Load config
config = load_config()
tracked_players = config.get("steam_user", {})
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", config.get("telegram_bot_token"))

if not TOKEN or ":" not in TOKEN:
    raise ValueError("Invalid or missing Telegram bot token! Please check your .env or config.json")

async def main():
    log("Starting bot...")

    # Start Telegram bot in a separate thread
    telegram_app = setup_telegram_commands()  # This will setup the commands
    loop = asyncio.get_event_loop()
    loop.create_task(run_telegram_bot(telegram_app))

    # Run initial cache update
    log("Updating full cache...")
    await update_cache()

    # Start periodic tasks
    asyncio.create_task(schedule_cache_updates())  # Full update every 6 hours
    asyncio.create_task(check_new_matches())  # Player match updates every 5 minutes

    # Start other modules
    log("Starting game tracking modules...")
    await asyncio.gather(
        start_notify_game(),
        start_track_dota()
    )

def setup_telegram_commands():
    """Setup Telegram bot and command handlers."""
    app = Application.builder().token(TOKEN).build()
    setup_command_handlers(app)  # Register command handlers here
    log("Telegram bot is ready.")
    return app

async def run_telegram_bot(app):
    """Run Telegram bot polling in an async function."""
    log("Starting Telegram bot polling...")
    await app.run_polling()

async def schedule_cache_updates():
    """Update full cache (heroes, items, patches, player data) every 6 hours."""
    while True:
        log("Scheduled full cache update triggered.")
        await update_cache()
        log("Full cache update completed.")
        await asyncio.sleep(6 * 60 * 60)  # Wait 6 hours

async def check_new_matches():
    """Update only tracked players' matches every 5 minutes."""
    while True:
        log("Checking for new matches...")
        async with asyncio.Semaphore(2):  # Limit concurrent requests
            await asyncio.gather(*(cache_player_data(None, player) for player in tracked_players))
        log("Match check completed. Waiting 5 minutes...")
        await asyncio.sleep(5 * 60)  # Wait 5 minutes

if __name__ == "__main__":
    nest_asyncio.apply()  # Prevent event loop conflicts
    asyncio.run(main())

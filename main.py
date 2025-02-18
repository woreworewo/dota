import asyncio
import nest_asyncio
import os
import cache_manager
from dotenv import load_dotenv
from notify_game import start_notify_game
from track_dota import start_track_dota
from utils import log, load_config
from telegram.ext import Application, CommandHandler  # Import CommandHandler here
from commands import setup_command_handlers  # Import function to setup commands
from match_tracker import track_matches_periodically
from quote import setup_quote_scheduler, setup_quote_command_handlers
from beban_tracker import beban  # Import /beban command handler

# Load .env
load_dotenv()

# Load config
config = load_config()
tracked_players_64 = config.get("steam_user", {})  # Load Steam 64-bit IDs
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", config.get("telegram_bot_token"))

if not TOKEN or ":" not in TOKEN:
    raise ValueError("Invalid or missing Telegram bot token! Please check your .env or config.json")

async def main():
    log("Starting bot...")

    # Start Telegram bot
    telegram_app = setup_telegram_commands()
    loop = asyncio.get_event_loop()
    loop.create_task(run_telegram_bot(telegram_app))

    # Start match tracking
    log("Starting match tracking module...")
    for steam_id in tracked_players_64.keys():
        asyncio.create_task(track_matches_periodically(steam_id))

    # Start other tracking tasks
    await asyncio.gather(
        start_notify_game(),
        start_track_dota()
    )

    # Start the quote scheduler to send a random quote daily
    setup_quote_scheduler()

def setup_telegram_commands():
    """Setup Telegram bot and command handlers."""
    app = Application.builder().token(TOKEN).build()
    setup_command_handlers(app)  # Register other command handlers
    setup_quote_command_handlers(app)  # Register quote-related command handlers
    
    # Add /beban command handler from beban_tracker
    app.add_handler(CommandHandler("beban", beban))  # Register /beban command handler
    
    log("Telegram bot is ready.")
    return app

async def run_telegram_bot(app):
    """Run Telegram bot polling in an async function."""
    log("Starting Telegram bot polling...")
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()  # Prevent event loop conflicts
    asyncio.run(main())

import asyncio
from telegram.ext import Application, CommandHandler
from cache_manager import update_cache, cache_player_data
from notify_game import start_notify_game
from track_dota import start_track_dota
from utils import log, load_config
from commands import last_match_command  # Import last match command

# Load config
config = load_config()
tracked_players = config.get("steam_user", {})

TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your actual token

async def main():
    log("Starting bot...")

    # Initialize Telegram bot
    application = Application.builder().token(TOKEN).build()

    # Register commands
    application.add_handler(CommandHandler("lastmatch", last_match_command))

    # Run initial cache update
    log("Updating full cache...")
    await update_cache()

    # Start periodic tasks
    asyncio.create_task(schedule_cache_updates())  # Full update every 6 hours
    asyncio.create_task(check_new_matches())  # Player match updates every 5 minutes

    # Start other modules
    log("Starting game tracking modules...")
    asyncio.create_task(start_notify_game())
    asyncio.create_task(start_track_dota())

    # Run bot polling (it manages its own event loop)
    await application.run_polling()

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
    asyncio.run(main())  # Correctly runs the bot with a clean event loop

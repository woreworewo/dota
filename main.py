import asyncio
import subprocess
from cache_manager import update_cache, cache_player_data
from notify_game import start_notify_game
from track_dota import start_track_dota
from utils import log, load_config

# Load config
config = load_config()
tracked_players = config.get("steam_user", {})

async def main():
    log("Starting bot...")

    # Start log watcher in background
    start_log_watcher()

    # Run initial cache update
    log("Updating full cache...")
    await update_cache()

    # Start periodic tasks
    asyncio.create_task(schedule_cache_updates())  # Full update every 6 hours
    asyncio.create_task(check_new_matches())  # Player match updates every 10 minutes

    # Start other modules
    log("Starting game tracking modules...")
    await asyncio.gather(
        start_notify_game(),
        start_track_dota()
    )

def start_log_watcher():
    """Start log_watcher.py as a background process."""
    try:
        subprocess.Popen(["python", "log_watcher.py"])
        log("Log watcher started successfully.")
    except Exception as e:
        log(f"Failed to start log watcher: {e}")

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
    asyncio.run(main())

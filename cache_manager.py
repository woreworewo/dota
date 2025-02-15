import aiohttp
import asyncio
import json
from pathlib import Path
from utils import log, get_current_time

API_BASE_URL = "https://api.opendota.com/api"
CACHE_DIR = Path("cache")
CACHE_FILES = {
    "heroes": CACHE_DIR / "heroes.json",
    "items": CACHE_DIR / "items.json",
    "patches": CACHE_DIR / "patches.json"
}

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)

async def fetch_data(session, url, retries=3):
    """Fetch data from API with retry mechanism and exponential backoff."""
    for attempt in range(retries):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))  # Default to 10s
                    log(f"[{get_current_time()}] Rate limited. Retrying in {retry_after} seconds...", "warning")
                    await asyncio.sleep(retry_after)
                else:
                    log(f"[{get_current_time()}] Attempt {attempt + 1}: Failed to fetch {url} - Status Code: {response.status}", "warning")
        except aiohttp.ClientError as e:
            log(f"[{get_current_time()}] Attempt {attempt + 1}: Network error while fetching {url}: {e}", "error")
        await asyncio.sleep(2 ** attempt)  # Exponential backoff (2, 4, 8 sec)
    return None

async def fetch_heroes(session):
    """Fetch and cache hero data."""
    log(f"[{get_current_time()}] Fetching hero data...")
    data = await fetch_data(session, f"{API_BASE_URL}/heroes")
    if data:
        with open(CACHE_FILES["heroes"], "w") as f:
            json.dump(data, f, indent=4)
        log(f"[{get_current_time()}] Hero data updated.")

async def fetch_items(session):
    """Fetch and cache item data."""
    log(f"[{get_current_time()}] Fetching item data...")
    data = await fetch_data(session, f"{API_BASE_URL}/constants/items")
    if data:
        with open(CACHE_FILES["items"], "w") as f:
            json.dump(data, f, indent=4)
        log(f"[{get_current_time()}] Item data updated.")

async def fetch_patches(session):
    """Fetch and cache patch data."""
    log(f"[{get_current_time()}] Fetching patch data...")
    data = await fetch_data(session, f"{API_BASE_URL}/constants/patchnotes")
    if data:
        with open(CACHE_FILES["patches"], "w") as f:
            json.dump(data, f, indent=4)
        log(f"[{get_current_time()}] Patch data updated.")

async def update_static_cache():
    """Update static cache (heroes, items, patches)."""
    log(f"[{get_current_time()}] Starting static cache update...")

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            fetch_heroes(session),
            fetch_items(session),
            fetch_patches(session)
        )

    log(f"[{get_current_time()}] Static cache update completed.")

async def update_cache_command(update: Update, context: CallbackContext):
    """Trigger the static cache update."""
    await update.message.reply_text("Starting static cache update...")
    try:
        await update_static_cache()  # Trigger the static cache update
        await update.message.reply_text("Static cache update completed successfully!")
    except Exception as e:
        await update.message.reply_text(f"Error during static cache update: {e}")

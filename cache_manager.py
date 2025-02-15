import aiohttp
import asyncio
import json
import time
from pathlib import Path
from utils import steam_id_to_account_id, log, load_config, get_current_time
from asyncio import Queue

API_BASE_URL = "https://api.opendota.com/api"
CACHE_DIR = Path("cache")
PLAYERS_DIR = CACHE_DIR / "players"
MATCHES_DIR = CACHE_DIR / "matches"

# Ensure cache directories exist
CACHE_DIR.mkdir(exist_ok=True)
PLAYERS_DIR.mkdir(exist_ok=True)
MATCHES_DIR.mkdir(exist_ok=True)

CACHE_FILES = {
    "heroes": CACHE_DIR / "heroes.json",
    "items": CACHE_DIR / "items.json",
    "patches": CACHE_DIR / "patches.json"
}

# Load config
config = load_config()
tracked_players = config.get("steam_user", {})

# Rate limiting setup
RATE_LIMIT = 60  # 60 requests per minute
request_queue = Queue()
last_request_time = time.time()
requests_sent = 0

def load_cache(file_path):
    """Load cache from JSON file, return empty dict if file is missing or corrupted."""
    if file_path.exists():
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            log(f"[{get_current_time()}] Error loading {file_path}, resetting cache.", "warning")
    return {}

def save_cache(file_path, data):
    """Save data to cache file."""
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
    except OSError as e:
        log(f"[{get_current_time()}] Error saving cache {file_path}: {e}", "error")

async def rate_limit_check():
    """Ensures we respect the rate limit of 60 requests per minute."""
    global requests_sent, last_request_time

    while True:
        # Check the number of requests sent within the last minute
        if time.time() - last_request_time > 60:
            last_request_time = time.time()
            requests_sent = 0

        if requests_sent >= RATE_LIMIT:
            sleep_time = 60 - (time.time() - last_request_time)
            log(f"[{get_current_time()}] Rate limit reached, sleeping for {sleep_time:.2f} seconds...", "warning")
            await asyncio.sleep(sleep_time)
        
        # Dequeue and send the request
        await request_queue.get()
        requests_sent += 1
        await asyncio.sleep(1)  # Small delay to avoid burst traffic

async def fetch_data(session, url, retries=3):
    """Fetch data from API with retry mechanism and exponential backoff."""
    await request_queue.put(1)  # Enqueue the request

    for attempt in range(retries):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))  # Default to 10s
                    log(f"[{get_current_time()}] Rate-limited by OpenDota API. Retrying in {retry_after} seconds...", "warning")
                    await asyncio.sleep(retry_after)
                else:
                    log(f"[{get_current_time()}] Attempt {attempt + 1}: Failed to fetch {url} - Status Code: {response.status}", "warning")
        except aiohttp.ClientError as e:
            log(f"[{get_current_time()}] Attempt {attempt + 1}: Network error while fetching {url}: {e}", "error")
        await asyncio.sleep(2 ** attempt)  # Exponential backoff (2, 4, 8 sec)
    return None

async def cache_heroes(session):
    log(f"[{get_current_time()}] Fetching hero data...")
    data = await fetch_data(session, f"{API_BASE_URL}/heroes")
    if data:
        save_cache(CACHE_FILES["heroes"], data)
        log(f"[{get_current_time()}] Hero data updated.")

async def cache_items(session):
    log(f"[{get_current_time()}] Fetching item data...")
    data = await fetch_data(session, f"{API_BASE_URL}/constants/items")
    if data:
        save_cache(CACHE_FILES["items"], data)
        log(f"[{get_current_time()}] Item data updated.")

async def cache_patches(session):
    log(f"[{get_current_time()}] Fetching patch data...")
    data = await fetch_data(session, f"{API_BASE_URL}/constants/patchnotes")
    if data:
        save_cache(CACHE_FILES["patches"], data)
        log(f"[{get_current_time()}] Patch data updated.")

async def cache_player_data(session, steam_id):
    """Fetch and cache player data including last match ID."""
    account_id = steam_id_to_account_id(steam_id)
    player_file = PLAYERS_DIR / f"{steam_id}.json"
    player_data = load_cache(player_file)

    log(f"[{get_current_time()}] Fetching data for Steam ID: {steam_id}...")

    # Fetch profile and win/loss data
    profile_data = await fetch_data(session, f"{API_BASE_URL}/players/{account_id}")
    wl_data = await fetch_data(session, f"{API_BASE_URL}/players/{account_id}/wl")

    if profile_data:
        player_data.update(profile_data)
    if wl_data:
        player_data["win_loss"] = wl_data

    save_cache(player_file, player_data)
    log(f"[{get_current_time()}] Player data cached: {steam_id}")

async def update_cache():
    """Update all caches in parallel except last match data."""
    log(f"[{get_current_time()}] Starting cache update...")

    async with aiohttp.ClientSession() as session:
        # Start rate limiting task
        asyncio.create_task(rate_limit_check())

        # Update all cache in parallel
        await asyncio.gather(
            cache_heroes(session),
            cache_items(session),
            cache_patches(session),
            *[cache_player_data(session, player) for player in tracked_players]
        )

    log(f"[{get_current_time()}] Cache update completed.")

# Add the update cache command handler
async def handle_update_cache_command():
    """Handle the update cache command."""
    await update_cache()

if __name__ == "__main__":
    asyncio.run(handle_update_cache_command())

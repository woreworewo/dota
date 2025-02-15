import aiohttp
import asyncio
import json
from pathlib import Path
from utils import steam_id_to_account_id, log, load_config, get_current_time

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

    # Fetch recent matches to determine last match ID
    recent_matches = await fetch_data(session, f"{API_BASE_URL}/players/{account_id}/recentMatches")
    if recent_matches:
        latest_match_id = recent_matches[0]["match_id"]
        previous_match_id = player_data.get("last_match_id")

        # Only fetch match data if it's a new match
        if latest_match_id != previous_match_id:
            await cache_match_data(session, latest_match_id)  # Fetch match data if not cached
            player_data["last_match_id"] = latest_match_id  # Update last match ID

    save_cache(player_file, player_data)
    log(f"[{get_current_time()}] Player data cached: {steam_id}")

async def cache_match_data(session, match_id):
    """Fetch and cache match details only if not already cached."""
    match_file = MATCHES_DIR / f"{match_id}.json"
    if match_file.exists():
        log(f"[{get_current_time()}] Skipping match {match_id}, already cached.")
        return

    log(f"[{get_current_time()}] Fetching match data for Match ID: {match_id}...")
    match_data = await fetch_data(session, f"{API_BASE_URL}/matches/{match_id}")
    if match_data:
        save_cache(match_file, match_data)
        log(f"[{get_current_time()}] Match data cached: {match_id}")

async def update_cache():
    """Update all caches in parallel using a single session."""
    log(f"[{get_current_time()}] Starting cache update...")

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            cache_heroes(session),
            cache_items(session),
            cache_patches(session),
            *[cache_player_data(session, player) for player in tracked_players]
        )

    log(f"[{get_current_time()}] Cache update completed.")

if __name__ == "__main__":
    asyncio.run(update_cache())

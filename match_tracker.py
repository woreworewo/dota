import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv
from utils import log, get_current_time, load_config

# Load environment variables
load_dotenv()
config = load_config()

STEAM_API_KEY = os.getenv("STEAM_API_KEY", config.get("steam_api_key"))
DOTA_API_URL = "https://api.steampowered.com/IDOTA2Match_570/GetMatchHistory/V1/"
CACHE_DIR = "cache/steam/"  # Directory to save match data
STEAM_ID_OFFSET = 76561197960265728  # Convert Steam 64-bit ID to 32-bit account ID

async def fetch_match_data(steam_id):
    """Fetch match data from the Dota API."""
    account_id = int(steam_id) - STEAM_ID_OFFSET  # Convert to 32-bit ID
    params = {"key": STEAM_API_KEY, "account_id": account_id}

    async with aiohttp.ClientSession() as session:
        async with session.get(DOTA_API_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                await save_match_data(data)  # Save only new matches
                return data
            log(f"Failed to fetch match data for Steam ID {steam_id}: {response.status}")
            return None

async def save_match_data(data):
    """Save only new match data to disk."""
    os.makedirs(CACHE_DIR, exist_ok=True)  # Ensure the directory exists
    matches = data.get("result", {}).get("matches", [])

    for match in matches:
        match_id = str(match.get("match_id"))
        if not match_id:
            continue

        file_path = os.path.join(CACHE_DIR, f"{match_id}.json")
        if os.path.exists(file_path):
            continue  # Skip if match file already exists

        # Save match data asynchronously
        def write_to_file():
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(match, file, indent=4)

        await asyncio.to_thread(write_to_file)
        log(f"New match saved: {file_path}")

async def track_matches_periodically(steam_id, interval=300):
    """Periodically fetch and process match data."""
    while True:
        log(f"Checking for new matches for Steam ID: {steam_id}...")
        await fetch_match_data(steam_id)
        await asyncio.sleep(interval)

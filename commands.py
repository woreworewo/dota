import os
import json
from pathlib import Path
from telegram import Update
from telegram.ext import CallbackContext

CACHE_DIR = Path("cache/matches")
HEROES_CACHE = Path("cache/heroes.json")

# Load tracked players from config
CONFIG_PATH = Path("config.json")
with CONFIG_PATH.open("r", encoding="utf-8") as f:
    config = json.load(f)
tracked_players = config.get("steam_user", {})


def get_hero_name(hero_id):
    """Fetch hero name from cache."""
    if HEROES_CACHE.exists():
        with HEROES_CACHE.open("r", encoding="utf-8") as f:
            heroes_data = json.load(f)
            return heroes_data.get(str(hero_id), "Unknown")  # Ensure hero_id is string
    return "Unknown"


async def get_last_match_data():
    """Fetch the latest match data from cache/matches/."""
    try:
        match_files = sorted(CACHE_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if not match_files:
            return "No match data found."

        latest_match_file = match_files[0]  
        with latest_match_file.open("r", encoding="utf-8") as f:
            match_data = json.load(f)

        if not match_data:
            return "Match data is empty."

        return format_match_stats(match_data)

    except Exception as e:
        return f"Error loading match data: {e}"


def format_match_stats(match_data):
    """Format the match stats for Telegram output."""
    try:
        match_id = match_data.get("match_id", "Unknown")
        duration = match_data.get("duration", 0) // 60
        winner = "Radiant" if match_data.get("radiant_win", False) else "Dire"

        players = match_data.get("players", [])
        if not players:
            return "No player data found."

        stats = []
        for p in players:
            account_id = str(p.get("account_id"))  # Convert to string for matching
            if account_id in tracked_players:
                name = tracked_players[account_id]  # Use nickname from config
                hero_name = get_hero_name(p.get("hero_id", 0))
                kills, deaths, assists = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
                gpm, xpm = p.get("gold_per_min", 0), p.get("xp_per_min", 0)

                stats.append(f"*{name}* ({hero_name}) – {kills}/{deaths}/{assists} KDA, {gpm} GPM, {xpm} XPM")

        if not stats:
            return "No tracked players found in the last match."

        stats_text = "\n".join(stats)
        return f"*Match ID:* {match_id}\n*Duration:* {duration} min\n*Winner:* {winner}\n\n{stats_text}"

    except Exception as e:
        return f"Error formatting match data: {e}"


async def last_match_command(update: Update, context: CallbackContext):
    """Telegram command to fetch and send last match stats."""
    chat_id = update.message.chat_id
    message = await get_last_match_data()
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

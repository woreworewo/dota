import os
import json
from telegram import Update
from telegram.ext import CallbackContext

CACHE_DIR = "cache/matches"

def get_last_match_data():
    """Fetch the latest match data from cache/matches/."""
    try:
        match_files = sorted(os.listdir(CACHE_DIR), reverse=True)
        if not match_files:
            return "No match data found."

        latest_match_file = match_files[0]  
        match_path = os.path.join(CACHE_DIR, latest_match_file)

        with open(match_path, "r", encoding="utf-8") as f:
            match_data = json.load(f)

        return format_match_stats(match_data)

    except Exception as e:
        return f"Error loading match data: {e}"


def format_match_stats(match_data):
    """Format the match stats for Telegram output."""
    try:
        match_id = match_data.get("match_id", "Unknown")
        duration = match_data.get("duration", 0) // 60  
        radiant_win = match_data.get("radiant_win", False)
        winner = "Radiant" if radiant_win else "Dire"

        players = match_data.get("players", [])
        stats = []

        for p in players:
            name = p.get("personaname", "Unknown")
            hero = p.get("hero_name", "Unknown")
            kills, deaths, assists = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
            gpm, xpm = p.get("gold_per_min", 0), p.get("xp_per_min", 0)

            stats.append(f"*{name}* ({hero}) – {kills}/{deaths}/{assists} KDA, {gpm} GPM, {xpm} XPM")

        stats_text = "\n".join(stats)
        return f"*Match ID:* {match_id}\n*Duration:* {duration} min\n*Winner:* {winner}\n\n{stats_text}"

    except Exception as e:
        return f"Error formatting match data: {e}"


def last_match_command(update: Update, context: CallbackContext):
    """Telegram command to fetch and send last match stats."""
    chat_id = update.message.chat_id
    message = get_last_match_data()
    context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

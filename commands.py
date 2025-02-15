import os
import json
from pathlib import Path
from telegram import Update
from telegram.ext import CallbackContext

CACHE_DIR = Path("cache/matches")


async def get_last_match_data():
    """Fetch the latest match data from cache/matches/."""
    try:
        match_files = sorted(CACHE_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
        if not match_files:
            return "No match data found."

        latest_match_file = match_files[0]  # Ambil file terbaru
        with latest_match_file.open("r", encoding="utf-8") as f:
            match_data = json.load(f)

        if not match_data:  # Cek jika file kosong
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

        stats = [
            f"*{p.get('personaname', 'Unknown')}* ({p.get('hero_name', 'Unknown')}) – "
            f"{p.get('kills', 0)}/{p.get('deaths', 0)}/{p.get('assists', 0)} KDA, "
            f"{p.get('gold_per_min', 0)} GPM, {p.get('xp_per_min', 0)} XPM"
            for p in players
        ]

        stats_text = "\n".join(stats)
        return f"*Match ID:* {match_id}\n*Duration:* {duration} min\n*Winner:* {winner}\n\n{stats_text}"

    except Exception as e:
        return f"Error formatting match data: {e}"


async def last_match_command(update: Update, context: CallbackContext):
    """Telegram command to fetch and send last match stats."""
    chat_id = update.message.chat_id
    message = await get_last_match_data()  # Gunakan await untuk fungsi async
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

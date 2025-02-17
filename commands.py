import json
import aiohttp
import asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils import load_config, add_tracked_player, remove_tracked_player, change_player_nickname
from cache_manager import update_cache
from datetime import datetime, timedelta

# Ensure cache directory exists
STEAM_MATCH_CACHE_DIR = Path('cache/steam')  # Directory where the match_id files are stored
MATCH_DATA_CACHE_DIR = Path('cache/matches')  # Directory where the match data files are stored

CACHE_DIR = Path("cache/matches")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEROES_FILE = Path("cache/heroes.json")

# Load tracked players from config
config = load_config()
tracked_players_64 = config.get("steam_user", {})

# Convert Steam 64-bit IDs to 32-bit account IDs
STEAM_ID_OFFSET = 76561197960265728
tracked_players = {str(int(steam_id) - STEAM_ID_OFFSET): nickname for steam_id, nickname in tracked_players_64.items()}

# Load hero names from cache/heroes.json
def load_heroes():
    try:
        with HEROES_FILE.open("r", encoding="utf-8") as f:
            heroes_data = json.load(f)
        return {hero["id"]: hero["localized_name"] for hero in heroes_data}
    except Exception as e:
        print(f"Error loading heroes: {e}")
        return {}

heroes_dict = load_heroes()

# Update the config file with new data
def update_config(new_data):
    """Update the config.json file with new data."""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        config_data.update(new_data)

        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)

        return "Config updated successfully!"
    except Exception as e:
        return f"Error updating config: {e}"

last_update_time = None  # To track last update time
cooldown_time = timedelta(minutes=10)  # 10-minute cooldown

async def update_cache_command(update: Update, context: CallbackContext):
    global last_update_time
    now = datetime.now()

    if last_update_time and now - last_update_time < cooldown_time:
        await update.message.reply_text("Cache update was recently done. Please try again later.")
        return

    await update.message.reply_text("Starting cache update...")
    try:
        await update_cache()  # Call update_cache from cache_manager.py
        last_update_time = now  # Update last update time
        await update.message.reply_text("Cache update completed successfully!")
    except Exception as e:
        await update.message.reply_text(f"Error during cache update: {e}")

async def get_last_match_data():
    """Fetch the latest match data from OpenDota using the match_id from the latest cache file."""
    try:
        # Look for the latest match_id.json file in the cache/steam/ directory
        match_id_files = sorted(STEAM_MATCH_CACHE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not match_id_files:
            return "No match ID file found in cache/steam/."

        # Extract the match_id from the filename (e.g., '8158792452.json')
        latest_match_id_file = match_id_files[0]
        match_id_str = latest_match_id_file.stem  # Get the filename without the extension (e.g., '8158792452')

        try:
            match_id = int(match_id_str)
        except ValueError:
            return "Invalid match_id format in the latest cache file."

        # Check if the match data already exists in the cache directory
        match_data_file = MATCH_DATA_CACHE_DIR / f"{match_id}.json"
        if match_data_file.exists():
            # If match data exists in cache, read and return it
            with match_data_file.open("r", encoding="utf-8") as f:
                match_data = json.load(f)
            return format_match_stats(match_data, tracked_players, heroes_dict)

        # If match data does not exist in cache, fetch it from OpenDota
        url = f"https://api.opendota.com/api/matches/{match_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    match_data = await response.json()
                    
                    # Save the fetched match data to the cache directory
                    with match_data_file.open("w", encoding="utf-8") as f:
                        json.dump(match_data, f)
                    
                    return format_match_stats(match_data, tracked_players, heroes_dict)
                else:
                    return f"Error fetching match data from OpenDota: {response.status}"

    except Exception as e:
        return f"Error loading match data: {e}"

def format_match_stats(match_data, tracked_players, heroes_dict):
    """Format the match stats for Telegram output, filtering only tracked players."""
    try:
        match_id = match_data.get("match_id", "Unknown")
        winner = "Radiant" if match_data.get("radiant_win", False) else "Dire"

        players = match_data.get("players", [])
        if not players:
            return "No player data found."

        tracked_team_players = []

        # Determine if tracked players are Radiant or Dire based on first tracked player
        tracked_team = None

        for p in players:
            account_id = str(p.get("account_id", ""))  # Ensure account_id is a string
            if account_id in tracked_players:  # Only include tracked players
                nickname = tracked_players[account_id]
                team = "Radiant" if p.get("isRadiant", False) else "Dire"
                hero_id = p.get("hero_id", -1)  # Use hero_id to fetch the hero name
                hero = heroes_dict.get(hero_id, "Unknown")  # Fetch hero name from the heroes dictionary
                kills, deaths, assists = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)

                # If tracked_team is not set, set it based on the first tracked player's team
                if tracked_team is None:
                    tracked_team = team

                tracked_team_players.append((nickname, hero, kills, deaths, assists, team))

        # Determine if the tracked team won or lost
        if (tracked_team == "Radiant" and match_data.get("radiant_win", False)) or (tracked_team == "Dire" and not match_data.get("radiant_win", False)):
            result = "won"
        else:
            result = "lost"

        # Prepare the result message with tracked players and their result
        if tracked_team_players:
            players_names = [nickname for nickname, hero, kills, deaths, assists, team in tracked_team_players]
            result_message = f"*{', '.join(players_names)}* {result} a game as {tracked_team}"

            # Prepare detailed stats for each tracked player (without GPM and XPM)
            stats_text = "\n".join([
                f"*{nickname}* ({hero}) – {kills}/{deaths}/{assists}"
                for nickname, hero, kills, deaths, assists, team in tracked_team_players
            ])

        else:
            return "No tracked players found in the last match."

        return f"*Match ID:* {match_id}\n\n{result_message}\n\n{stats_text}"

    except Exception as e:
        return f"Error formatting match data: {e}"

async def last_match_command(update: Update, context: CallbackContext):
    """Telegram command to fetch and send last match stats for tracked players."""
    chat_id = update.message.chat_id
    message = await get_last_match_data()
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

# Implement the /track, /untrack, /rename, and /list commands
async def track_player(update: Update, context: CallbackContext):
    """Track a player by Steam64 ID and nickname."""
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /track <Steam64 ID> <Nickname>")
        return
    
    steam64_id = context.args[0]
    nickname = context.args[1]
    
    try:
        add_tracked_player(steam64_id, nickname)
        await update.message.reply_text(f"Player {nickname} (Steam64 ID {steam64_id}) is now being tracked.")
    except Exception as e:
        await update.message.reply_text(f"Error adding player: {e}")

async def untrack_player(update: Update, context: CallbackContext):
    """Untrack a player by Steam64 ID."""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /untrack <Steam64 ID>")
        return
    
    steam64_id = context.args[0]
    
    try:
        remove_tracked_player(steam64_id)
        await update.message.reply_text(f"Player with Steam64 ID {steam64_id} is no longer being tracked.")
    except Exception as e:
        await update.message.reply_text(f"Error removing player: {e}")

async def rename_player(update: Update, context: CallbackContext):
    """Rename a tracked player using Steam64 ID and new nickname."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /rename <Steam64 ID> <New Nickname>")
        return

    steam64_id = context.args[0]
    new_nickname = " ".join(context.args[1:])
    
    # Check if the steam64_id exists in the tracked players (tracked_players_64)
    if steam64_id not in tracked_players_64:
        await update.message.reply_text(f"Error: Steam64 ID '{steam64_id}' not found.")
        return

    try:
        # Get the old nickname
        old_nickname = tracked_players_64[steam64_id]

        # Update the nickname in tracked_players_64
        tracked_players_64[steam64_id] = new_nickname

        # Also update the nickname in tracked_players (if necessary)
        tracked_players[str(int(steam64_id) - STEAM_ID_OFFSET)] = new_nickname

        # Optionally, update config file if needed
        update_config({"steam_user": tracked_players_64})

        # Respond with the success message
        await update.message.reply_text(f"Player {old_nickname} (Steam64 ID: {steam64_id}) is now renamed to {new_nickname}.")
        
    except Exception as e:
        await update.message.reply_text(f"Error changing nickname: {e}")

async def list_tracked_players(update: Update, context: CallbackContext):
    """List all currently tracked players."""
    if not tracked_players:
        await update.message.reply_text("No players are currently being tracked.")
        return
    
    # Format the list to show Steam64 ID and Nickname
    player_list = "\n".join([f"{steam_id}: {nickname}" for steam_id, nickname in tracked_players_64.items()])
    await update.message.reply_text(f"Currently tracked players:\n{player_list}")

def setup_command_handlers(dispatcher):
    """Setup command handlers for the Telegram bot."""
    dispatcher.add_handler(CommandHandler("lastmatch", last_match_command))
    dispatcher.add_handler(CommandHandler("lm", last_match_command))
    dispatcher.add_handler(CommandHandler("track", track_player))
    dispatcher.add_handler(CommandHandler("untrack", untrack_player))
    dispatcher.add_handler(CommandHandler("rename", rename_player))
    dispatcher.add_handler(CommandHandler("list", list_tracked_players))  # Changed to /list
    dispatcher.add_handler(CommandHandler("update", update_cache_command))

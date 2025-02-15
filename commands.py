import json
from pathlib import Path
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler
from utils import load_config, cache_manager  # Assuming cache_manager is imported

CACHE_DIR = Path("cache/matches")
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

# Hero dictionary (id -> hero name)
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

async def track_player(update: Update, context: CallbackContext):
    """Track a player by Steam 64-bit ID."""
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /track <steam_id> <nickname>")
        return
    
    steam_id = context.args[0]
    nickname = context.args[1]
    
    # Check if player is already tracked
    if steam_id in tracked_players_64:
        await update.message.reply_text(f"{nickname} is already being tracked.")
        return
    
    # Add player to the config file
    tracked_players_64[steam_id] = nickname
    update_config({"steam_user": tracked_players_64})
    
    await update.message.reply_text(f"Now tracking {nickname} (Steam ID: {steam_id})")

async def untrack_player(update: Update, context: CallbackContext):
    """Untrack a player by Steam 64-bit ID."""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /untrack <steam_id>")
        return
    
    steam_id = context.args[0]
    
    # Check if player is being tracked
    if steam_id not in tracked_players_64:
        await update.message.reply_text(f"No player found with Steam ID: {steam_id}")
        return
    
    # Remove player from the config file
    del tracked_players_64[steam_id]
    update_config({"steam_user": tracked_players_64})
    
    await update.message.reply_text(f"Stopped tracking player with Steam ID: {steam_id}")

async def change_nickname(update: Update, context: CallbackContext):
    """Change the nickname of a tracked player."""
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /nickname <current_nickname> <new_nickname>")
        return

    current_nickname = context.args[0]
    new_nickname = context.args[1]

    # Find the Steam ID corresponding to the current nickname
    steam_id = None
    for player_id, nickname in tracked_players_64.items():
        if nickname == current_nickname:
            steam_id = player_id
            break

    if not steam_id:
        await update.message.reply_text(f"No player found with nickname: {current_nickname}")
        return

    # Update the nickname in the config file
    tracked_players_64[steam_id] = new_nickname
    update_config({"steam_user": tracked_players_64})

    await update.message.reply_text(f"Nickname for {current_nickname} updated to {new_nickname}")

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
    """Format the match stats for Telegram output, filtering only tracked players."""
    try:
        match_id = match_data.get("match_id", "Unknown")
        duration = match_data.get("duration", 0) // 60
        winner = "Radiant" if match_data.get("radiant_win", False) else "Dire"

        players = match_data.get("players", [])
        if not players:
            return "No player data found."

        stats = []
        for p in players:
            account_id = str(p.get("account_id", ""))
            if account_id in tracked_players:  # Only include tracked players
                nickname = tracked_players[account_id]
                hero_id = p.get("hero_id", -1)  # Use hero_id instead of hero_name
                hero = heroes_dict.get(hero_id, "Unknown")  # Fetch hero name from the heroes dictionary
                kills, deaths, assists = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
                gpm, xpm = p.get("gold_per_min", 0), p.get("xp_per_min", 0)

                stats.append(f"*{nickname}* ({hero}) – {kills}/{deaths}/{assists} *KDA*, {gpm} *GPM*, {xpm} *XPM*")

        if not stats:
            return "No tracked players found in the last match."

        stats_text = "\n".join(stats)
        return f"*Match ID:* {match_id}\n*Duration:* {duration} min\n*Winner:* {winner}\n\n{stats_text}"

    except Exception as e:
        return f"Error formatting match data: {e}"

async def last_match_command(update: Update, context: CallbackContext):
    """Telegram command to fetch and send last match stats for tracked players."""
    chat_id = update.message.chat_id
    message = await get_last_match_data()
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

async def update_cache(update: Update, context: CallbackContext):
    """Update the cache data, except the last match."""
    try:
        # Update hero data and any other necessary cache (except last match)
        heroes_dict = load_heroes()  # Refresh hero data
        cache_manager.update_hero_cache(heroes_dict)  # Assuming cache_manager has a method to update the heroes cache
        
        # You can add more cache updates here as necessary.
        
        await update.message.reply_text("Cache updated successfully, excluding the last match data.")
    except Exception as e:
        await update.message.reply_text(f"Error updating cache: {e}")

def setup_command_handlers(dispatcher):
    """Setup command handlers for the Telegram bot."""
    dispatcher.add_handler(CommandHandler("lastmatch", last_match_command))
    dispatcher.add_handler(CommandHandler("lm", last_match_command))
    dispatcher.add_handler(CommandHandler("track", track_player))
    dispatcher.add_handler(CommandHandler("untrack", untrack_player))
    dispatcher.add_handler(CommandHandler("nickname", change_nickname))
    dispatcher.add_handler(CommandHandler("update", update_cache))  # Added the new update command

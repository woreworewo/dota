import heapq
import os
import json
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from dotenv import load_dotenv
import asyncio

# Load .env
load_dotenv()

# Folder where match data is stored
MATCH_FOLDER = "cache/matches/"

# Load config.json
with open("config.json", "r") as config_file:
    config_data = json.load(config_file)

# Function to convert account ID to Steam ID
def account_id_to_steam_id(account_id):
    return 76561197960265728 + account_id

# Function to get player name from Steam ID
def get_player_name(steam_id):
    return config_data["steam_user"].get(str(steam_id), "Unknown")

# Function to load all match data from cache
def load_all_matches():
    matches = []
    for filename in os.listdir(MATCH_FOLDER):
        if filename.endswith(".json"):
            with open(os.path.join(MATCH_FOLDER, filename), "r") as f:
                match_data = json.load(f)
                matches.append(match_data)
    return matches

# Function to get the worst players based on performance metrics
def get_worst_players():
    matches = load_all_matches()
    if not matches:
        return []

    player_stats = {}
    total_deaths = {}
    player_match_count = {}

    for match in matches:
        duration_minutes = match.get("duration", 0) / 60  # Match duration in minutes
        total_team_kills = sum(player.get("kills", 0) for player in match.get("players", []))
        total_pings = sum(player.get("pings", 0) for player in match.get("players", []))
        total_chat_activity = sum(player.get("chat_messages", 0) for player in match.get("players", []))

        for player in match.get("players", []):
            account_id = player.get("account_id")
            if not account_id:
                continue

            steam_id = account_id_to_steam_id(account_id)
            player_name = get_player_name(steam_id)

            # Limit to 10 matches per player
            if steam_id not in player_match_count:
                player_match_count[steam_id] = 0
            if player_match_count[steam_id] >= 10:
                continue
            player_match_count[steam_id] += 1

            # Metrics calculation
            duration_minutes = max(1, duration_minutes)  # Avoid division by zero

            # Calculate KDA
            kda = (player.get("kills", 0) + player.get("assists", 0)) / max(1, player.get("deaths", 1))

            # GPM and XPM
            gpm = player.get("gold", 0) / duration_minutes
            xpm = player.get("xp", 0) / duration_minutes

            # Hero damage per minute
            hero_damage_per_minute = player.get("hero_damage", 0) / duration_minutes

            # Tower damage
            tower_damage = player.get("tower_damage", 0)

            # Last hits per minute
            last_hits_per_minute = player.get("last_hits", 0) / duration_minutes

            # Net worth
            net_worth = player.get("gold", 0) - player.get("gold_spent", 0)

            # Teamfight participation
            teamfight_participation = (player.get("kills", 0) + player.get("assists", 0)) / max(1, total_team_kills)

            # Calculate Wards Placed Per Minute and Wards Destroyed Per Minute
            wards_placed_per_min = (player.get("observer_wards", 0) + player.get("sentry_wards", 0)) / duration_minutes
            wards_destroyed_per_min = player.get("wards_destroyed", 0) / duration_minutes

            # Calculate Death Impact
            death_impact = player.get("death_impact", 0)  # Placeholder; should be calculated based on game impact

            # Gold/Experience Efficiency
            gold_efficiency = player.get("gold_efficiency", 1)  # Placeholder; needs actual formula
            experience_efficiency = player.get("experience_efficiency", 1)  # Placeholder; needs actual formula

            # Communication metrics
            pings_per_min = total_pings / max(1, len(match.get("players", [])))  # Average pings per player
            chat_activity = total_chat_activity / max(1, len(match.get("players", [])))  # Average chat activity

            # Calculate Score (lower score is worse performance)
            score = (
                (1 / max(1, kda)) +  # Penalize for low KDA
                (1 / max(1, gpm)) -  # Penalize for low GPM
                (1 / max(1, xpm)) -  # Penalize for low XPM
                (1 / max(1, hero_damage_per_minute)) -  # Penalize for low hero damage
                (1 / max(1, tower_damage)) -  # Penalize for low tower damage
                (1 / max(1, last_hits_per_minute)) -  # Penalize for low last hits
                (1 / max(1, net_worth)) -  # Penalize for low net worth
                (1 / max(1, teamfight_participation)) -  # Penalize for low teamfight participation
                (1 / max(1, wards_placed_per_min)) -  # Penalize for low wards placed
                (1 / max(1, wards_destroyed_per_min)) -  # Penalize for low wards destroyed
                death_impact -  # Penalize for higher death impact
                (1 / max(1, gold_efficiency)) -  # Penalize for low gold efficiency
                (1 / max(1, experience_efficiency)) -  # Penalize for low experience efficiency
                (1 / max(1, pings_per_min)) -  # Penalize for low pings activity
                (1 / max(1, chat_activity))  # Penalize for low chat activity
            )

            # Update player stats
            if steam_id not in player_stats:
                player_stats[steam_id] = {
                    "name": player_name,
                    "score": 0,
                    "matches": 0
                }

            player_stats[steam_id]["score"] += score
            player_stats[steam_id]["matches"] += 1

            # Track deaths for "Top tier dead collection"
            if steam_id not in total_deaths:
                total_deaths[steam_id] = 0
            total_deaths[steam_id] += player.get("deaths", 0)

    # Sort and get the bottom 3 players (those with the highest score)
    worst_players = heapq.nsmallest(3, player_stats.values(), key=lambda p: p["score"])

    # Get top tier dead collection, only the player with the most deaths
    top_tier_dead = max(total_deaths.items(), key=lambda item: item[1], default=("Unknown", 0))

    return worst_players, top_tier_dead

# Add the /beban command handler
async def beban(update: Update, context: CallbackContext):
    worst_players, top_tier_dead = get_worst_players()
    
    if worst_players:
        message = "*Top 3 Worst Players (Based on performance metrics):*\n\n"
        for idx, player in enumerate(worst_players, 1):
            message += f"{idx}. *{player['name']}* - Score: {player['score']:.2f} (Matches: {player['matches']})\n"
        
        message += "\n*Top tier dead collection*\n"
        # Display the player with the most deaths
        player_name = get_player_name(top_tier_dead[0])
        message += f"*{player_name}*: {top_tier_dead[1]} times\n"
    else:
        message = "No matches found or no data available."

    message += "\n*How we calculate:*\nKDA, GPM, XPM, Hero Damage, Tower Damage, Last Hits, Net Worth, Teamfight Participation, Wards, Death Impact, Gold/Experience Efficiency, Pings, Chat Activity."

    # Send the message to Telegram (awaited)
    await update.message.reply_text(message, parse_mode="Markdown")

def main():
    # Initialize Telegram bot
    updater = Updater(os.getenv("TELEGRAM_BOT_TOKEN"), use_context=True)
    dp = updater.dispatcher

    # Add command handler for /beban
    dp.add_handler(CommandHandler("beban", beban))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

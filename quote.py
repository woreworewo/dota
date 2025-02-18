import random
import json
import os
import asyncio
import re
from telegram import Update
from telegram.ext import CommandHandler, Application, CallbackContext
from datetime import datetime

QUOTE_FILE = "quote.json"  # Path to store quotes
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Group chat ID

# Load existing quotes from the quote.json file
def load_quotes():
    if not os.path.exists(QUOTE_FILE):
        return []
    
    try:
        with open(QUOTE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []

# Save new quotes to the quote.json file
def save_quotes(quotes):
    with open(QUOTE_FILE, "w", encoding="utf-8") as file:
        json.dump(quotes, file, indent=4)

import random
import json
import os
import asyncio
import re
from telegram import Update
from telegram.ext import CommandHandler, Application, CallbackContext
from datetime import datetime

QUOTE_FILE = "quote.json"  # Path to store quotes

# Load existing quotes from the quote.json file
def load_quotes():
    if not os.path.exists(QUOTE_FILE):
        return []
    
    try:
        with open(QUOTE_FILE, "r", encoding="utf-8") as file:
            return json.load(file) or []
    except json.JSONDecodeError:
        return []  # Return empty list if file is corrupted or empty

# Save new quotes to the quote.json file
def save_quotes(quotes):
    with open(QUOTE_FILE, "w", encoding="utf-8") as file:
        json.dump(quotes, file, indent=4)

async def add_quote(update: Update, context: CallbackContext):
    """Handle /quote command to add a new quote with a flexible author name."""
    if not context.args:
        await update.message.reply_text('Usage: /quote <author> "quote text"')
        return

    text = " ".join(context.args).strip()

    # Allow both straight (") and curly (“”)
    match = re.match(r'(.+?)\s+[“"](.+?)[”"]$', text)

    if match:
        author = match.group(1).strip()  # Capture author
        quote = match.group(2).strip()   # Capture quote text
        year = datetime.now().year       # Get current year

        quotes = load_quotes()
        quotes.append({
            "quote": quote,
            "author": author,
            "year": year,
            "timestamp": str(datetime.now())
        })
        save_quotes(quotes)

        await update.message.reply_text(f'Quote added:\n\n"{quote}"\n\n- {author} ({year})')
    else:
        await update.message.reply_text('Invalid format. Usage: /quote <author> "quote text"')

async def handle_random_quote_command(update: Update, context: CallbackContext):
    """Handle /tq command to send a random quote to the group."""
    quotes = load_quotes()
    if not quotes:
        await update.message.reply_text("No quotes available.")
        return

    random_quote = random.choice(quotes)
    message = f'"{random_quote["quote"]}"\n\n- {random_quote["author"]} ({random_quote.get("year", "Unknown")})'

    try:
        # Send the message to the group without echoing the user's message
        await context.bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as e:
        print(f"Failed to send message: {e}")

async def send_random_quote(context: CallbackContext):
    """Send a random quote from the list to the group every day."""
    quotes = load_quotes()
    if quotes:
        random_quote = random.choice(quotes)
        message = f'"{random_quote["quote"]}"\n\n- {random_quote["author"]} ({random_quote.get("year", "Unknown")})'
        await context.bot.send_message(TELEGRAM_CHAT_ID, message)

# Setup the quote command handler and scheduler
def setup_quote_command_handlers(app: Application):
    """Register /quote and /tq command handlers."""
    app.add_handler(CommandHandler("quote", add_quote))  # Register /quote command to add quotes
    app.add_handler(CommandHandler("tq", handle_random_quote_command))  # Register /tq command to send a random quote

def setup_quote_scheduler():
    """Schedule sending a random quote daily at a random time."""
    scheduler = asyncio.get_event_loop()

    # Generate a random number of seconds within 24 hours (86400 seconds)
    random_delay = random.randint(0, 86400)  # Random delay between 0 and 24 hours

    # Schedule sending a random quote after the random delay
    scheduler.call_later(random_delay, asyncio.create_task, daily_quote_task())

async def daily_quote_task():
    """Function that runs every 24 hours to send a random quote."""
    await send_random_quote()

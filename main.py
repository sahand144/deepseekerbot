import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, 
    CommandHandler, 
    MessageHandler, 
    Filters, 
    CallbackContext,
    CallbackQueryHandler
)
from transformers import pipeline
import requests
import json

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv('TELEGRAM_TOKEN')
HF_TOKEN = os.getenv('HF_TOKEN')

# Initialize Hugging Face pipeline for text generation
text_generator = pipeline('text-generation', model='gpt2', token=HF_TOKEN)

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("General Knowledge", callback_data='knowledge')],
        [InlineKeyboardButton("Crypto Market", callback_data='crypto')],
        [InlineKeyboardButton("AI Assistant", callback_data='ai')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_markup(
        f"Hi {user.first_name}! I'm your free AI Assistant.\nChoose an option:",
        reply_markup=reply_markup
    )

def button(update: Update, context: CallbackContext) -> None:
    """Handle button presses."""
    query = update.callback_query
    query.answer()
    
    if query.data == 'knowledge':
        query.edit_message_text(text="Send me any question about general knowledge!")
    elif query.data == 'crypto':
        query.edit_message_text(text="Send me a crypto symbol like BTC or ETH for price info")
    elif query.data == 'ai':
        query.edit_message_text(text="Ask me anything and I'll respond with AI!")

def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle all other messages."""
    text = update.message.text
    
    # Check if it's a crypto request (3-4 letter uppercase)
    if text.isupper() and 2 <= len(text) <= 5:
        handle_crypto(update, context, text)
    else:
        handle_ai_response(update, context, text)

def handle_crypto(update: Update, context: CallbackContext, symbol: str) -> None:
    """Get crypto price information."""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
        response = requests.get(url)
        data = response.json()
        
        if symbol.lower() in data:
            price = data[symbol.lower()]['usd']
            update.message.reply_text(f"{symbol} price: ${price}")
        else:
            update.message.reply_text(f"Couldn't find data for {symbol}. Try BTC, ETH, etc.")
    except Exception as e:
        update.message.reply_text("Error fetching crypto data. Please try later.")

def handle_ai_response(update: Update, context: CallbackContext, text: str) -> None:
    """Generate AI response using Hugging Face."""
    try:
        # For longer responses, we'll use the free Inference API
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {
            "inputs": text,
            "parameters": {"max_length": 200, "temperature": 0.7}
        }
        
        response = requests.post(
            "https://api-inference.huggingface.ai/models/gpt2",
            headers=headers,
            json=payload
        )
        
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            generated_text = result[0]['generated_text']
            update.message.reply_text(generated_text)
        else:
            update.message.reply_text("I couldn't generate a response. Please try again.")
    except Exception as e:
        update.message.reply_text("AI service is busy. Please try again later.")

def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors."""
    logger.warning(f'Update {update} caused error {context.error}')

def main() -> None:
    """Start the bot."""
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    
    # Button handler
    dispatcher.add_handler(CallbackQueryHandler(button))
    
    # Message handler
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Error handler
    dispatcher.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
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
import requests

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv('TELEGRAM_TOKEN')
HF_TOKEN = os.getenv('HF_TOKEN')

def start(update: Update, context: CallbackContext) -> None:
    """Send welcome message."""
    keyboard = [
        [InlineKeyboardButton("General Knowledge", callback_data='knowledge')],
        [InlineKeyboardButton("Crypto Market", callback_data='crypto')],
        [InlineKeyboardButton("AI Assistant", callback_data='ai')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Hi! I'm your free AI Assistant.\nChoose an option:",
        reply_markup=reply_markup
    )

def button(update: Update, context: CallbackContext) -> None:
    """Handle button presses."""
    query = update.callback_query
    query.answer()
    
    if query.data == 'knowledge':
        query.edit_message_text(text="Ask me anything about general knowledge!")
    elif query.data == 'crypto':
        query.edit_message_text(text="Send crypto symbol like BTC or ETH")
    elif query.data == 'ai':
        query.edit_message_text(text="Ask me anything and I'll respond with AI!")

def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle all messages."""
    text = update.message.text
    
    if text.isupper() and 2 <= len(text) <= 5:
        handle_crypto(update, context, text)
    else:
        handle_ai_response(update, context, text)

def handle_crypto(update: Update, context: CallbackContext, symbol: str) -> None:
    """Get crypto price."""
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
        response = requests.get(url)
        data = response.json()
        
        if symbol.lower() in data:
            price = data[symbol.lower()]['usd']
            update.message.reply_text(f"{symbol} price: ${price}")
        else:
            update.message.reply_text(f"Couldn't find {symbol}. Try BTC, ETH, etc.")
    except Exception as e:
        update.message.reply_text("Error fetching crypto data. Please try later.")

def handle_ai_response(update: Update, context: CallbackContext, text: str) -> None:
    """Generate AI response using Hugging Face API."""
    try:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {
            "inputs": text,
            "parameters": {"max_length": 150}
        }
        
        response = requests.post(
            "https://api-inference.huggingface.com/models/gpt2",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                update.message.reply_text(result[0]['generated_text'])
            else:
                update.message.reply_text("No response from AI. Try again.")
        else:
            update.message.reply_text(f"AI error: {response.text}")
    except Exception as e:
        update.message.reply_text(f"Error: {str(e)}")

def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors."""
    logger.warning(f'Update {update} caused error {context.error}')

def main() -> None:
    """Start the bot."""
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

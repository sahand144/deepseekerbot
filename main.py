import os
import logging
from datetime import datetime, timedelta
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
import json

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv('TELEGRAM_TOKEN')
HF_TOKEN = os.getenv('HF_TOKEN')

# Crypto symbol mapping
CRYPTO_MAP = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'DOGE': 'dogecoin',
    'USDT': 'tether',
    'BNB': 'binancecoin',
    'XRP': 'ripple',
    'ADA': 'cardano',
    'SOL': 'solana',
    'DOT': 'polkadot',
    'SHIB': 'shiba-inu'
}

def start(update: Update, context: CallbackContext) -> None:
    """Send welcome message."""
    keyboard = [
        [InlineKeyboardButton("General Knowledge", callback_data='knowledge')],
        [InlineKeyboardButton("Crypto Market", callback_data='crypto')],
        [InlineKeyboardButton("AI Assistant", callback_data='ai')],
        [InlineKeyboardButton("Date Help", callback_data='date')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Hi! I'm your improved AI Assistant.\nChoose an option:",
        reply_markup=reply_markup
    )

def button(update: Update, context: CallbackContext) -> None:
    """Handle button presses."""
    query = update.callback_query
    query.answer()
    
    if query.data == 'knowledge':
        query.edit_message_text(text="Ask me anything about general knowledge!")
    elif query.data == 'crypto':
        query.edit_message_text(text="Send crypto symbol like BTC or ETH (now works for 10+ coins!)")
    elif query.data == 'ai':
        query.edit_message_text(text="Ask me anything and I'll respond with AI!")
    elif query.data == 'date':
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        query.edit_message_text(text=f"Tomorrow's date is {tomorrow}")

def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle all messages."""
    text = update.message.text.strip().upper()
    
    if text in CRYPTO_MAP or (text.isalpha() and len(text) <= 5):
        handle_crypto(update, context, text)
    elif text.lower().startswith(('date', 'time', 'today', 'tomorrow')):
        handle_date_query(update, context, text)
    else:
        handle_ai_response(update, context, text)

def handle_crypto(update: Update, context: CallbackContext, symbol: str) -> None:
    """Get crypto price with improved API handling."""
    try:
        coin_id = CRYPTO_MAP.get(symbol, symbol.lower())
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            price = data['market_data']['current_price']['usd']
            change = data['market_data']['price_change_percentage_24h']
            update.message.reply_text(
                f"💰 {symbol.upper()}: ${price:,.4f}\n"
                f"24h Change: {change:.2f}%"
            )
        else:
            update.message.reply_text("Crypto data not available. Try these: BTC, ETH, DOGE, USDT, BNB, XRP, ADA, SOL, DOT, SHIB")
    except Exception as e:
        logger.error(f"Crypto error: {e}")
        update.message.reply_text("Error fetching crypto data. Please try again later.")

def handle_date_query(update: Update, context: CallbackContext, text: str) -> None:
    """Handle date/time queries locally."""
    now = datetime.now()
    if 'tomorrow' in text.lower():
        date = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        update.message.reply_text(f"Tomorrow's date is {date}")
    elif 'today' in text.lower():
        update.message.reply_text(f"Today is {now.strftime('%Y-%m-%d')}")
    else:
        update.message.reply_text(f"Current date/time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

def handle_ai_response(update: Update, context: CallbackContext, text: str) -> None:
    """Generate AI response with better error handling."""
    try:
        # First try simple local responses
        if '2+2' in text:
            return update.message.reply_text("2 + 2 equals 4")
            
        # Then fall back to Hugging Face
        headers = {
            "Authorization": f"Bearer {HF_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": text,
            "parameters": {"max_length": 150, "temperature": 0.7}
        }
        
        response = requests.post(
            "https://api-inference.huggingface.co/models/gpt2",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                reply = result[0]['generated_text'].replace(text, '').strip()
                update.message.reply_text(reply[:1000])  # Limit response length
            else:
                update.message.reply_text("I couldn't generate a response. Please try a different question.")
        else:
            logger.error(f"AI API error: {response.status_code} - {response.text}")
            update.message.reply_text("My AI service is currently unavailable. Try asking about dates or crypto prices instead.")
    except Exception as e:
        logger.error(f"AI processing error: {e}")
        update.message.reply_text("Sorry, I encountered an error. Please try again later.")

def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors and notify user."""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        update.message.reply_text("An error occurred. Please try again later.")
    except:
        pass

def main() -> None:
    """Start the bot."""
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()

def help_command(update: Update, context: CallbackContext) -> None:
    """Show help message."""
    help_text = """
    🤖 Bot Commands:
    /start - Start the bot
    /help - Show this help
    /crypto [symbol] - Check crypto price
    
    Features:
    • Crypto prices for 10+ coins (BTC, ETH, etc.)
    • Date/time information
    • AI responses when available
    """
    update.message.reply_text(help_text)

if __name__ == '__main__':
    main()

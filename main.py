import os
import logging
import requests
import wikipedia
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import redis
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Redis
r = redis.Redis(
    host=os.getenv('REDIS_URL', 'redis://localhost:6379'),
    decode_responses=True
)

class CryptoManager:
    @staticmethod
    async def get_coin_data(coin_id: str):
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower()}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Crypto API error: {e}")
        return None

class AIManager:
    @staticmethod
    async def get_ai_response(user_id: str, query: str):
        # Check cache first
        cached = r.get(f"ai:{user_id}:{query[:50]}")
        if cached:
            return cached
            
        # Try DeepInfra (DeepSeeker)
        try:
            deepseek = await AIManager._query_deepseek(query)
            if deepseek:
                r.setex(f"ai:{user_id}:{query[:50]}", 3600, deepseek)  # Cache for 1 hour
                return deepseek
        except Exception as e:
            logger.error(f"DeepSeeker error: {e}")

        # Fallback to OpenRouter (ChatGPT)
        try:
            chatgpt = await AIManager._query_chatgpt(query)
            if chatgpt:
                return chatgpt
        except Exception as e:
            logger.error(f"ChatGPT error: {e}")

        # Final fallback
        return "I couldn't generate a response right now. Please try again later."

    @staticmethod
    async def _query_deepseek(query: str):
        response = requests.post(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('DEEPINFRA_KEY')}"},
            json={
                "model": "deepseek-ai",
                "messages": [{"role": "user", "content": query}]
            },
            timeout=15
        )
        return response.json()['choices'][0]['message']['content']

    @staticmethod
    async def _query_chatgpt(query: str):
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_KEY')}"},
            json={
                "model": "openai/gpt-3.5-turbo",
                "messages": [{"role": "user", "content": query}]
            },
            timeout=15
        )
        return response.json()['choices'][0]['message']['content']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    r.set(f"user:{user_id}:menu_pref", "grid")  # Default menu style
    
    await show_main_menu(update, user_id)

async def show_main_menu(update: Update, user_id: str):
    menu_pref = r.get(f"user:{user_id}:menu_pref") or "grid"
    
    if menu_pref == "grid":
        keyboard = [
            [InlineKeyboardButton("💰 Crypto", callback_data="crypto"),
             InlineKeyboardButton("🤖 AI Chat", callback_data="ai")],
            [InlineKeyboardButton("🌐 Web Search", callback_data="search"),
             InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
    elif menu_pref == "list":
        keyboard = [
            [InlineKeyboardButton("1. Cryptocurrency Prices", callback_data="crypto")],
            [InlineKeyboardButton("2. AI Assistant", callback_data="ai")],
            [InlineKeyboardButton("3. Web Search", callback_data="search")],
            [InlineKeyboardButton("4. Bot Settings", callback_data="settings")]
        ]
    else:  # hybrid
        keyboard = [
            [InlineKeyboardButton("Crypto Markets", callback_data="crypto")],
            [InlineKeyboardButton("Chat with AI", callback_data="ai")],
            [InlineKeyboardButton("Search Online", callback_data="search"),
             InlineKeyboardButton("⚙", callback_data="settings")]
        ]

    await update.message.reply_text(
        "🔹 Main Menu 🔹",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Enter any cryptocurrency symbol or name (e.g. BTC, Ethereum):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Back", callback_data="main_menu")]
        ])
    )

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Ask me anything:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Back", callback_data="main_menu")]
        ])
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if in crypto mode
    if r.get(f"user:{user_id}:mode") == "crypto":
        coin_data = await CryptoManager.get_coin_data(text)
        if coin_data:
            message = f"""
📊 {coin_data['name']} ({coin_data['symbol'].upper()})
💰 Price: ${coin_data['market_data']['current_price']['usd']:,.4f}
📈 24h Change: {coin_data['market_data']['price_change_percentage_24h']:.2f}%
💎 Market Cap: ${coin_data['market_data']['market_cap']['usd']:,.2f}
            """
            await update.message.reply_markdown(message)
        else:
            await update.message.reply_text("Coin not found. Try symbols like BTC, ETH, SOL")
        r.delete(f"user:{user_id}:mode")
        await show_main_menu(update, user_id)
    
    # Check if in AI mode
    elif r.get(f"user:{user_id}:mode") == "ai":
        response = await AIManager.get_ai_response(user_id, text)
        await update.message.reply_text(response)
        await show_main_menu(update, user_id)
    
    # Default handling
    else:
        await update.message.reply_text("Please select an option from the menu:")
        await show_main_menu(update, user_id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "main_menu":
        await show_main_menu(update, user_id)
    elif query.data == "crypto":
        r.set(f"user:{user_id}:mode", "crypto")
        await handle_crypto(update, context)
    elif query.data == "ai":
        r.set(f"user:{user_id}:mode", "ai")
        await handle_ai(update, context)
    elif query.data.startswith("menu_"):
        style = query.data.split("_")[1]
        r.set(f"user:{user_id}:menu_pref", style)
        await show_main_menu(update, user_id)

def main():
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.run_polling()

if __name__ == "__main__":
    main()

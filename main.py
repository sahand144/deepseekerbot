import os
import logging
import requests
import redis
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
    ContextTypes,
    Application
)
from telegram.error import Conflict
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Redis
try:
    r = redis.Redis.from_url(
        os.getenv('REDIS_URL', 'redis://localhost:6379'),
        decode_responses=True,
        socket_timeout=10,
        socket_connect_timeout=5
    )
    r.ping()  # Test connection
except redis.RedisError as e:
    logger.error(f"Redis connection failed: {e}")
    raise

class CryptoManager:
    @staticmethod
    async def get_coin_data(coin_id: str):
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id.lower()}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"CoinGecko API response: {response.status_code}")
        except Exception as e:
            logger.error(f"Crypto API error: {e}")
        return None

class AIManager:
    @staticmethod
    async def get_ai_response(user_id: str, query: str):
        # Check cache first
        try:
            cached = r.get(f"ai:{user_id}:{query[:50]}")
            if cached:
                return cached
        except redis.RedisError as e:
            logger.error(f"Redis cache error: {e}")

        # Try DeepInfra (DeepSeeker)
        try:
            deepseek = await AIManager._query_deepseek(query)
            if deepseek:
                try:
                    r.setex(f"ai:{user_id}:{query[:50]}", 3600, deepseek)
                except redis.RedisError as e:
                    logger.error(f"Redis setex error: {e}")
                return deepseek
        except Exception as e:
            logger.error(f"DeepSeeker error: {e}")

        # Fallback to local response
        return "I'm currently unable to process your request. Please try again later."

    @staticmethod
    async def _query_deepseek(query: str):
        headers = {
            "Authorization": f"Bearer {os.getenv('DEEPINFRA_KEY')}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-ai",
            "messages": [{"role": "user", "content": query}],
            "max_tokens": 500
        }
        response = requests.post(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            headers=headers,
            json=payload,
            timeout=15
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        r.set(f"user:{user_id}:menu_pref", "grid")
    except redis.RedisError as e:
        logger.error(f"Redis start error: {e}")
    
    await show_main_menu(update, user_id)

async def show_main_menu(update: Update, user_id: str):
    try:
        menu_pref = r.get(f"user:{user_id}:menu_pref") or "grid"
    except redis.RedisError as e:
        logger.error(f"Redis menu pref error: {e}")
        menu_pref = "grid"

    keyboard = []
    if menu_pref == "grid":
        keyboard = [
            [InlineKeyboardButton("💰 Crypto", callback_data="crypto"),
             InlineKeyboardButton("🤖 AI Chat", callback_data="ai")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
    elif menu_pref == "list":
        keyboard = [
            [InlineKeyboardButton("1. Cryptocurrency Prices", callback_data="crypto")],
            [InlineKeyboardButton("2. AI Assistant", callback_data="ai")],
            [InlineKeyboardButton("3. Bot Settings", callback_data="settings")]
        ]
    else:  # hybrid
        keyboard = [
            [InlineKeyboardButton("Crypto Markets", callback_data="crypto")],
            [InlineKeyboardButton("Chat with AI", callback_data="ai")],
            [InlineKeyboardButton("⚙ Settings", callback_data="settings")]
        ]

    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "🔹 Main Menu 🔹",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "🔹 Main Menu 🔹",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Menu display error: {e}")

async def handle_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    try:
        r.set(f"user:{user_id}:mode", "crypto")
    except redis.RedisError as e:
        logger.error(f"Redis crypto mode error: {e}")
    
    await query.edit_message_text(
        "Enter cryptocurrency symbol (BTC, ETH, etc.):",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Back", callback_data="main_menu")]
        ])
    )

async def handle_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    try:
        r.set(f"user:{user_id}:mode", "ai")
    except redis.RedisError as e:
        logger.error(f"Redis AI mode error: {e}")
    
    await query.edit_message_text(
        "Ask me anything:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩ Back", callback_data="main_menu")]
        ])
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    try:
        current_mode = r.get(f"user:{user_id}:mode")
    except redis.RedisError as e:
        logger.error(f"Redis get mode error: {e}")
        current_mode = None
    
    if current_mode == "crypto":
        coin_data = await CryptoManager.get_coin_data(text)
        if coin_data:
            try:
                message = f"""
📊 {coin_data['name']} ({coin_data['symbol'].upper()})
💰 Price: ${coin_data['market_data']['current_price']['usd']:,.4f}
📈 24h Change: {coin_data['market_data']['price_change_percentage_24h']:.2f}%
💎 Market Cap: ${coin_data['market_data']['market_cap']['usd']:,.2f}
                """
                await update.message.reply_markdown(message)
            except Exception as e:
                logger.error(f"Message formatting error: {e}")
                await update.message.reply_text("Found coin data but formatting failed")
        else:
            await update.message.reply_text("Coin not found. Try symbols like BTC, ETH, SOL")
        
        try:
            r.delete(f"user:{user_id}:mode")
        except redis.RedisError as e:
            logger.error(f"Redis delete mode error: {e}")
        
        await show_main_menu(update, user_id)
    
    elif current_mode == "ai":
        response = await AIManager.get_ai_response(user_id, text)
        await update.message.reply_text(response)
        await show_main_menu(update, user_id)
    
    else:
        await update.message.reply_text("Please select an option from the menu:")
        await show_main_menu(update, user_id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "main_menu":
        await show_main_menu(update, user_id)
    elif query.data == "crypto":
        await handle_crypto(update, context)
    elif query.data == "ai":
        await handle_ai(update, context)
    elif query.data == "settings":
        await show_settings(update, user_id)
    elif query.data.startswith("menu_"):
        style = query.data.split("_")[1]
        try:
            r.set(f"user:{user_id}:menu_pref", style)
        except redis.RedisError as e:
            logger.error(f"Redis set menu pref error: {e}")
        await show_main_menu(update, user_id)

async def show_settings(update: Update, user_id: str):
    keyboard = [
        [InlineKeyboardButton(f"Menu Style: {style}", callback_data=f"menu_{style}")]
        for style in ["grid", "list", "hybrid"]
    ]
    keyboard.append([InlineKeyboardButton("↩ Back", callback_data="main_menu")])
    
    try:
        await update.callback_query.edit_message_text(
            "⚙ Bot Settings",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Settings display error: {e}")

def create_application() -> Application:
    return ApplicationBuilder() \
        .token(os.getenv("TELEGRAM_TOKEN")) \
        .read_timeout(30) \
        .write_timeout(30) \
        .connect_timeout(30) \
        .pool_timeout(30) \
        .build()

def main():
    # Check for existing instance
    try:
        if not r.setnx("bot:instance:lock", "1"):
            logger.error("Another instance is already running")
            exit(1)
        r.expire("bot:instance:lock", 10)
    except redis.RedisError as e:
        logger.error(f"Redis instance lock error: {e}")

    app = create_application()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            close_loop=False,
            stop_signals=None,
            relax=0.1
        )
    except Conflict:
        logger.error("Another instance is already running. Exiting.")
        exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        try:
            r.delete("bot:instance:lock")
        except redis.RedisError as e:
            logger.error(f"Redis unlock error: {e}")

if __name__ == "__main__":
    main()

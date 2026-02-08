import os
import time
import random
from datetime import datetime
import pandas as pd
import requests
from threading import Thread

# Try to import from your local 'quotexapi' folder
try:
    from quotexapi.stable_api import Quotex
except ImportError:
    print("❌ Error: 'quotexapi' folder not found! Make sure the folder is in the same directory as main.py")

try:
    from flask import Flask
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    from flask import Flask

# ==================== RENDER PORT BYPASS ====================
app = Flask('')

@app.route('/')
def home():
    return "<h1>Bot is Active and Running!</h1>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==================== SETTINGS FROM ENV ====================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAW_IDS = [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")]
TELEGRAM_CHAT_IDS = [i for i in RAW_IDS if i]

# ==================== STICKERS ====================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ==================== PAIRS ====================
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC",
    "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC", 
    "USD/MXN-OTC", "USD/PKR-OTC"
]

# ==================== FUNCTIONS ====================
def send_telegram(message, sticker=None):
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            url_msg = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url_msg, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            if sticker:
                url_stk = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker"
                requests.post(url_stk, data={"chat_id": chat_id, "sticker": sticker}, timeout=10)
        except Exception as e:
            print(f"Telegram Error: {e}")

def get_signal(pair, q):
    try:
        # Get candles: 1-min interval, 50 candles
        candles = q.get_candles(pair, 60, 50, time.time())
        if not candles: return None
        
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'])
        
        # Strategy: Moving Average 21
        ma21 = df['close'].rolling(window=21).mean().iloc[-1]
        last_close = df['close'].iloc[-1]
        
        if last_close > ma21: return "call"
        elif last_close < ma21: return "put"
        return None
    except:
        return None

def check_result(pair, signal_type, q):
    time.sleep(62) # Wait for candle to close
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        open_p = float(candles[0]['open'])
        close_p = float(candles[0]['close'])
        
        if (signal_type == "call" and close_p > open_p) or \
           (signal_type == "put" and close_p < open_p):
            return "WIN"
        return "LOSS"
    except:
        return "ERROR"

# ==================== MAIN ENGINE ====================
def start_bot():
    if not all([QUOTEX_EMAIL, QUOTEX_PASSWORD, TELEGRAM_BOT_TOKEN]):
        print("❌ Missing Env Variables in Render Settings!")
        return

    print("🔐 Connecting to Quotex...")
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    conn = q.connect()
    
    is_connected = conn[0] if isinstance(conn, tuple) else conn

    if not is_connected:
        print("❌ Login Failed!")
        return

    print("✅ Bot Connected Successfully!")
    send_telegram("🚀 <b>Quotex Signal Bot Started ✅</b>\n<i>Strategy: MA21 Trend</i>\n<i>Pairs: 20 Loaded</i>")

    while True:
        for pair in PAIRS:
            direction = get_signal(pair, q)
            if direction:
                trade_time = datetime.now().strftime("%H:%M")
                msg = f"<b>📈 Pair:</b> {pair}\n<b>⏰ Time:</b> {trade_time}\n<b>🔹 Signal:</b> {direction.upper()}"
                
                # Send Signal
                send_telegram(msg, sticker=(STICKER_UP if direction == "call" else STICKER_DOWN))
                
                # Check First Step
                result = check_result(pair, direction, q)
                
                if result == "WIN":
                    send_telegram(f"<b>📊 Result {pair}:</b> ITM ✅", sticker=STICKER_ITM)
                elif result == "LOSS":
                    send_telegram(f"<b>⚠️ {pair} OTM! Applying 1-Step MTG...</b>")
                    # Check MTG Result
                    mtg_res = check_result(pair, direction, q)
                    if mtg_res == "WIN":
                        send_telegram(f"<b>📊 Result {pair}:</b> ITM (MTG-1) ✅", sticker=STICKER_ITM)
                    else:
                        send_telegram(f"<b>📊 Result {pair}:</b> OTM ❌", sticker=STICKER_OTM)
                
                time.sleep(20) # Avoid spamming the API
        time.sleep(10)

if __name__ == "__main__":
    # Flask port bypass thread
    Thread(target=run_web, daemon=True).start()
    # Start bot logic
    start_bot()

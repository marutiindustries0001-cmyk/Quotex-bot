import os
import time
import random
from datetime import datetime
import pandas as pd
from quotexapi.stable_api import Quotex
import requests

# ==================== ENV VARIABLES ====================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Handling list of IDs from env
TELEGRAM_CHAT_IDS = [
    os.getenv("TELEGRAM_CHAT_ID1"),
    os.getenv("TELEGRAM_CHAT_ID2")
]

if not all([QUOTEX_EMAIL, QUOTEX_PASSWORD, TELEGRAM_BOT_TOKEN]):
    raise Exception("❌ Missing essential environment variables!")

# ==================== STICKERS ====================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"

# ==================== QUOTEX API STARTUP ====================
q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
check_connect, message = q.connect()

if not check_connect:
    print(f"❌ Login Failed: {message}")
    exit()

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
        if not chat_id: continue
        try:
            if sticker:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": chat_id, "sticker": sticker})
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
        except Exception as e:
            print(f"Telegram error: {e}")

def analyze_candle(pair):
    try:
        # Get last 50 candles (1-minute interval)
        candles = q.get_candles(pair, 60, 50, time.time())
        if not candles:
            return None
        
        df = pd.DataFrame(candles)
        # Ensure 'close' column is numeric for calculation
        df['close'] = pd.to_numeric(df['close'])
        
        last_close = df['close'].iloc[-1]
        ma21 = df['close'].rolling(window=21).mean().iloc[-1]
        
        if pd.isna(ma21): return None
        
        return "call" if last_close > ma21 else "put"
    except Exception as e:
        print(f"Error analyzing {pair}: {e}")
        return None

def main_loop():
    send_telegram("🚀 Quotex Signal Bot Started ✅")
    while True:
        for pair in PAIRS:
            direction = analyze_candle(pair)
            if direction:
                trade_time = datetime.now().strftime("%H:%M:%S")
                message = (
                    f"<b>📈 Pair:</b> {pair}\n"
                    f"<b>⏰ Time:</b> {trade_time}\n"
                    f"<b>🔹 Signal:</b> {direction.upper()}\n"
                    f"<b>💡 Tip:</b> 1-step MTG if needed"
                )
                sticker = STICKER_UP if direction == "call" else STICKER_DOWN
                send_telegram(message, sticker=sticker)
                
                # Wait between signals to avoid spamming/API blocks
                time.sleep(random.randint(40, 60)) 
        
        time.sleep(5) # Brief pause before restarting pair list

# ==================== START BOT ====================
if __name__ == "__main__":
    main_loop()

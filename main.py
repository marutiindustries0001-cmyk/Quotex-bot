import os
import time
import random
from datetime import datetime
import pandas as pd
from quotexapi.stable_api import Quotex
import requests

# ==================== DIRECT SETTINGS ====================
QUOTEX_EMAIL = "ENTER_YOUR_EMAIL@GMAIL.COM"
QUOTEX_PASSWORD = "ENTER_YOUR_PASSWORD"
TELEGRAM_BOT_TOKEN = "ENTER_YOUR_BOT_TOKEN"
TELEGRAM_CHAT_IDS = ["ENTER_CHAT_ID_1", "ENTER_CHAT_ID_2"]

# ==================== STICKERS ====================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ==================== QUOTEX API STARTUP ====================
q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
check_connect, message = q.connect()

if not check_connect:
    print(f"❌ Login Failed! {message}")
    exit()

# Updated Pairs List
PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC",
    "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC", 
    "USD/MXN-OTC", "USD/PKR-OTC"
]

# ==================== FUNCTIONS ====================
def send_telegram(message, sticker=None):
    for chat_id in TELEGRAM_CHAT_IDS:
        if not chat_id or "ENTER" in str(chat_id): continue
        try:
            if sticker:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": chat_id, "sticker": sticker})
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
        except Exception as e:
            print(f"Telegram Error: {e}")

def get_signal(pair):
    try:
        candles = q.get_candles(pair, 60, 50, time.time())
        if not candles: return None
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'])
        ma21 = df['close'].rolling(window=21).mean().iloc[-1]
        last_close = df['close'].iloc[-1]
        return "call" if last_close > ma21 else "put"
    except:
        return None

def check_result(pair, signal_type):
    # Wait for candle to close (1 min)
    time.sleep(62) 
    try:
        candles = q.get_candles(pair, 60, 2, time.time())
        # Candle close check
        open_p = float(candles[0]['open'])
        close_p = float(candles[0]['close'])
        
        if (signal_type == "call" and close_p > open_p) or \
           (signal_type == "put" and close_p < open_p):
            return "WIN"
        else:
            return "LOSS"
    except:
        return "ERROR"

def main_loop():
    send_telegram("🚀 <b>Quotex Signal Bot Started ✅</b>\n<i>All Pairs Updated!</i>")
    while True:
        for pair in PAIRS:
            direction = get_signal(pair)
            if direction:
                trade_time = datetime.now().strftime("%H:%M:%S")
                send_telegram(f"<b>📈 Pair:</b> {pair}\n<b>⏰ Time:</b> {trade_time}\n<b>🔹 Signal:</b> {direction.upper()}", 
                              sticker=(STICKER_UP if direction == "call" else STICKER_DOWN))
                
                # Result Check
                result = check_result(pair, direction)
                
                if result == "WIN":
                    send_telegram(f"<b>📊 Result {pair}:</b> ITM (Direct) ✅", sticker=STICKER_ITM)
                elif result == "LOSS":
                    # MTG Logic
                    send_telegram(f"<b>⚠️ {pair} Loss! Applying 1-Step MTG...</b>")
                    mtg_result = check_result(pair, direction) # Wait another min
                    if mtg_result == "WIN":
                        send_telegram(f"<b>📊 Result {pair}:</b> ITM (MTG-1) ✅", sticker=STICKER_ITM)
                    else:
                        send_telegram(f"<b>📊 Result {pair}:</b> OTM ❌", sticker=STICKER_OTM)
                
                time.sleep(10) # Gap
        time.sleep(5)

if __name__ == "__main__":
    main_loop()

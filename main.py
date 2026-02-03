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
else:
    print("✅ Successfully Connected to Quotex!")

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC"]

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
        last_close = df['close'].iloc[-1]
        ma21 = df['close'].rolling(window=21).mean().iloc[-1]
        return "call" if last_close > ma21 else "put"
    except:
        return None

def check_result(pair, signal_type, entry_price):
    # 60 seconds wait for candle to close
    time.sleep(62) 
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        exit_price = float(candles[0]['close'])
        
        if (signal_type == "call" and exit_price > entry_price) or \
           (signal_type == "put" and exit_price < entry_price):
            return "WIN", STICKER_ITM
        else:
            return "LOSS", STICKER_OTM
    except:
        return "UNKNOWN", None

def main_loop():
    send_telegram("🚀 <b>Quotex Signal Bot Started ✅</b>")
    while True:
        for pair in PAIRS:
            direction = get_signal(pair)
            if direction:
                # Entry Data
                candles = q.get_candles(pair, 60, 1, time.time())
                entry_price = float(candles[0]['close'])
                
                trade_time = datetime.now().strftime("%H:%M:%S")
                msg = f"<b>📈 Pair:</b> {pair}\n<b>⏰ Time:</b> {trade_time}\n<b>🔹 Signal:</b> {direction.upper()}"
                
                # Send Signal
                send_telegram(msg, sticker=(STICKER_UP if direction == "call" else STICKER_DOWN))
                
                # Check Result
                result, res_sticker = check_result(pair, direction, entry_price)
                result_msg = f"<b>📊 Result {pair}:</b> {result} {'✅' if result=='WIN' else '❌'}"
                send_telegram(result_msg, sticker=res_sticker)
                
                time.sleep(10) # Gap between next pair check
        time.sleep(5)

if __name__ == "__main__":
    main_loop()

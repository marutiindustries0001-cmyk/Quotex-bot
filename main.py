import os
import time
import random
from datetime import datetime
import pandas as pd
import requests
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== RENDER PORT BYPASS ====================
app = Flask('')
@app.route('/')
def home(): return "Bot is Active!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==================== SETTINGS FROM ENV ====================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAW_IDS = [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")]
TELEGRAM_CHAT_IDS = [i for i in RAW_IDS if i]

# Stickers
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

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
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
            if sticker:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": chat_id, "sticker": sticker})
        except Exception as e: print(f"Telegram Error: {e}")

def get_signal(pair, q):
    try:
        candles = q.get_candles(pair, 60, 50, time.time())
        if not candles: 
            print(f"⚠️ No data for {pair}")
            return None
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'])
        ma21 = df['close'].rolling(window=21).mean().iloc[-1]
        last_close = df['close'].iloc[-1]
        if last_close > ma21: return "call"
        elif last_close < ma21: return "put"
    except: return None

def check_result(pair, signal_type, q):
    print(f"⏳ Waiting 60s for {pair} result...")
    time.sleep(62)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        open_p, close_p = float(candles[0]['open']), float(candles[0]['close'])
        if (signal_type == "call" and close_p > open_p) or (signal_type == "put" and close_p < open_p):
            return "WIN"
        return "LOSS"
    except: return "ERROR"

# ==================== MAIN ENGINE ====================
def start_bot():
    print("🔐 Connecting to Quotex...")
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    conn = q.connect()
    is_connected = conn[0] if isinstance(conn, tuple) else conn

    if not is_connected:
        print("❌ Login Failed! System Stop.")
        return

    print("✅ Bot is Online and Scanning Pairs!")
    send_telegram("🚀 <b>Quotex Bot Live!</b>\nLogs tracking enabled.")

    while True:
        for pair in PAIRS:
            print(f"🔍 Searching Signal: {pair}") # Isse logs mein activity dikhegi
            direction = get_signal(pair, q)
            if direction:
                print(f"🎯 FOUND SIGNAL: {pair} -> {direction.upper()}")
                trade_time = datetime.now().strftime("%H:%M")
                send_telegram(f"<b>📈 Pair:</b> {pair}\n<b>⏰ Time:</b> {trade_time}\n<b>🔹 Signal:</b> {direction.upper()}", 
                              sticker=(STICKER_UP if direction == "call" else STICKER_DOWN))
                
                result = check_result(pair, direction, q)
                if result == "WIN":
                    send_telegram(f"<b>📊 Result {pair}:</b> ITM ✅", sticker=STICKER_ITM)
                else:
                    send_telegram(f"<b>⚠️ {pair} OTM! Checking MTG...</b>")
                    mtg_res = check_result(pair, direction, q)
                    if mtg_res == "WIN":
                        send_telegram(f"<b>📊 Result {pair}:</b> ITM (MTG-1) ✅", sticker=STICKER_ITM)
                    else:
                        send_telegram(f"<b>📊 Result {pair}:</b> OTM ❌", sticker=STICKER_OTM)
                time.sleep(10)
        
        print("😴 Cycle complete. Restarting in 10s...")
        time.sleep(10)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

import os
import time
from datetime import datetime
import pandas as pd
import requests
import pytz
from threading import Thread
from flask import Flask

# Local folder se import karne ke liye
try:
    from quotexapi.stable_api import Quotex
except ImportError:
    from quotexpy import Quotex 

# ==================== SETTINGS ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot is Running - SIMPLE MESSAGE MODE</h1>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Env Variables
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ID1 = os.getenv("TELEGRAM_CHAT_ID1")
ID2 = os.getenv("TELEGRAM_CHAT_ID2")
CHATS = [id for id in [ID1, ID2] if id]

# ==================== STICKERS ====================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# Pairs
REAL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"]
OTC_PAIRS = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC", "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "AUDJPY-OTC"]

def get_active_pairs():
    day = datetime.now(IST).weekday()
    return OTC_PAIRS if day >= 5 else REAL_PAIRS

# ==================== FUNCTIONS ====================
def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    for cid in CHATS:
        try:
            requests.post(f"{base_url}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
            if sticker:
                requests.post(f"{base_url}/sendSticker", data={"chat_id": cid, "sticker": sticker}, timeout=10)
        except: pass

def check_result(pair, signal_type, q):
    time.sleep(62) 
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        open_p, close_p = float(candles[0]['open']), float(candles[0]['close'])
        if (signal_type == "CALL" and close_p > open_p) or (signal_type == "PUT" and close_p < open_p):
            return "WIN"
        return "LOSS"
    except: return "ERROR"

# ==================== MAIN ENGINE ====================
def start_bot():
    print("🔐 Connecting...")
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check, msg = q.connect()
    
    if not check:
        print(f"❌ Connection Failed")
        return

    send_msg(f"🚀 <b>QUOTEX BOT ONLINE</b>\n\n✅ Connected to {len(CHATS)} Channels.")

    last_min = None
    while True:
        now = datetime.now(IST)
        
        if 20 <= now.second <= 25 and now.minute != last_min:
            pairs = get_active_pairs()
            for pair in pairs:
                try:
                    candles = q.get_candles(pair, 60, 50, time.time())
                    if not candles: continue
                    
                    df = pd.DataFrame(candles)
                    df['close'] = pd.to_numeric(df['close'])
                    ma21 = df['close'].rolling(window=21).mean().iloc[-1]
                    last_price = df['close'].iloc[-1]
                    
                    if last_price == ma21: continue
                    
                    direction = "CALL" if last_price > ma21 else "PUT"
                    sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"

                    # --- CLEAN & SIMPLE MESSAGE ---
                    msg_text = (f"🎯 <b>NEW SIGNAL ALERT</b>\n\n"
                           f"🌍 <b>Pair:</b> {pair}\n"
                           f"⏰ <b>Time:</b> {sig_time} (IST)\n"
                           f"🚀 <b>Action:</b> {direction} {'⬆️' if direction == 'CALL' else '⬇️'}")
                    
                    send_msg(msg_text, sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                    last_min = now.minute
                    
                    res = check_result(pair, direction, q)
                    if res == "WIN":
                        send_msg(f"<b>📊 {pair}:</b> ITM ✅", STICKER_ITM)
                    elif res == "LOSS":
                        send_msg(f"<b>⚠️ {pair}:</b> OTM! Checking MTG-1...")
                        mtg_res = check_result(pair, direction, q)
                        if mtg_res == "WIN":
                            send_msg(f"<b>📊 {pair}:</b> ITM (MTG-1) ✅", STICKER_ITM)
                        else:
                            send_msg(f"<b>📊 {pair}:</b> OTM ❌", STICKER_OTM)
                    break 
                except:
                    time.sleep(2)
        time.sleep(1)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

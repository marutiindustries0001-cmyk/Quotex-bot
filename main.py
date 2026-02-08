import os
import time
import pandas as pd
import requests
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== SETTINGS ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot is Running - MONITORING MODE</h1>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ID1 = os.getenv("TELEGRAM_CHAT_ID1")
ID2 = os.getenv("TELEGRAM_CHAT_ID2")
CHATS = [id for id in [ID1, ID2] if id]

STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# Pairs List Thodi Badi Kar di hai taaki chances badh jayein
OTC_PAIRS = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC", "EURGBP-OTC", "NZDUSD-OTC"]
REAL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "EURJPY", "GBPJPY"]

def get_active_pairs():
    day = datetime.now(IST).weekday()
    return OTC_PAIRS if day >= 5 else REAL_PAIRS

# ==================== OPTIMIZED STRATEGY ====================
def calculate_indicators(df):
    df['close'] = pd.to_numeric(df['close'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['ma21'] = df['close'].rolling(window=21).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper_bb'] = df['ma20'] + (df['std'] * 2)
    df['lower_bb'] = df['ma20'] - (df['std'] * 2)
    
    df['resistance'] = df['high'].rolling(window=40).max() # S/R window thoda kam kiya
    df['support'] = df['low'].rolling(window=40).min()
    return df

def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    for cid in CHATS:
        try:
            requests.post(f"{base_url}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
            if sticker:
                requests.post(f"{base_url}/sendSticker", data={"chat_id": cid, "sticker": sticker}, timeout=10)
        except: pass

def get_accurate_result(pair, signal_type, q):
    time.sleep(62)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        open_p, close_p = float(candles[0]['open']), float(candles[0]['close'])
        if signal_type == "CALL":
            return "WIN" if close_p > open_p else "LOSS"
        else:
            return "WIN" if close_p < open_p else "LOSS"
    except: return "ERROR"

# ==================== MAIN ENGINE ====================
def start_bot():
    print("🔐 Re-Connecting to Quotex...")
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check, msg = q.connect()
    
    if not check:
        print(f"❌ Connection Failed")
        return

    send_msg(f"✅ <b>BOT ACTIVE & SCANNING</b>\n\n🔍 Strategy optimized for more signals.")

    last_min = None
    is_trading = False

    while True:
        now = datetime.now(IST)
        if not is_trading:
            if 15 <= now.second <= 25 and now.minute != last_min:
                pairs = get_active_pairs()
                for pair in pairs:
                    try:
                        candles = q.get_candles(pair, 60, 60, time.time())
                        if not candles: continue
                        df = calculate_indicators(pd.DataFrame(candles))
                        last = df.iloc[-1]
                        
                        # --- DEBUG LOGS (Render mein dikhega) ---
                        # print(f"Checking {pair}: Price={last['close']}, RSI={last['rsi']:.2f}, MA21={last['ma21']:.2f}")

                        direction = None
                        
                        # Thoda relax kiya gaya logic taaki signals milein
                        if (last['close'] > last['ma21'] and last['rsi'] < 75): # Call (RSI filter thoda badhaya)
                            if last['close'] < last['resistance']:
                                direction = "CALL"
                        
                        elif (last['close'] < last['ma21'] and last['rsi'] > 25): # Put
                            if last['close'] > last['support']:
                                direction = "PUT"

                        if direction:
                            is_trading = True
                            sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                            msg_text = (f"🚀 <b>PREMIUM SIGNAL</b>\n\n🌍 <b>ASSET:</b> {pair}\n⏰ <b>TIME:</b> {sig_time} IST\n"
                                        f"👉 <b>ACTION:</b> {'🟢 UP' if direction == 'CALL' else '🔴 DOWN'}\n🕒 <b>1 MIN</b>\n\n📏 <b>1-STEP MTG IF NEEDED</b>")
                            send_msg(msg_text, sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                            last_min = now.minute
                            
                            res = get_accurate_result(pair, direction, q)
                            if res == "WIN":
                                send_msg(f"💰 <b>{pair}:</b> ITM ✅", STICKER_ITM)
                            elif res == "LOSS":
                                send_msg(f"⚠️ <b>{pair}:</b> OTM! Following MTG-1...")
                                mtg_res = get_accurate_result(pair, direction, q)
                                if mtg_res == "WIN":
                                    send_msg(f"💰 <b>{pair}:</b> MTG ITM ✅", STICKER_ITM)
                                else:
                                    send_msg(f"❌ <b>{pair}:</b> LOSS OTM", STICKER_OTM)
                            is_trading = False
                            break # Ek baar mein ek hi signal
                    except: continue
        time.sleep(1)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

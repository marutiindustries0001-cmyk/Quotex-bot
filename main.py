import os
import time
import pandas as pd
import requests
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== 1. PRE-SETS & AUTH ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot is Running - ALL SETTINGS VERIFIED ✅</h1>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ID1 = os.getenv("TELEGRAM_CHAT_ID1")
ID2 = os.getenv("TELEGRAM_CHAT_ID2")
CHATS = [id for id in [ID1, ID2] if id]

# Premium Stickers
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ==================== 2. SMART ASSET SELECTOR ====================
def get_active_pairs():
    day = datetime.now(IST).weekday()
    if day >= 5: # Saturday/Sunday
        return ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC", "EURGBP-OTC", "NZDUSD-OTC"]
    else: # Weekdays
        return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "EURGBP", "EURJPY", "GBPJPY"]

# ==================== 3. MULTI-INDICATOR STRATEGY ====================
def calculate_indicators(df):
    df['close'] = pd.to_numeric(df['close'])
    # Trend Filter (MA21)
    df['ma21'] = df['close'].rolling(window=21).mean()
    # RSI (10) for faster signal generation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=10).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=10).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
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

# ==================== 4. TRADE RESULT VERIFIER ====================
def get_accurate_result(pair, signal_type, q):
    time.sleep(61) # Precise candle close timing
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if signal_type == "CALL":
            return "WIN" if c > o else "LOSS"
        else:
            return "WIN" if c < o else "LOSS"
    except: return "ERROR"

# ==================== 5. MAIN ENGINE ====================
def start_bot():
    print("🔐 Connecting to Quotex API...")
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check, msg = q.connect()
    
    if not check:
        print("❌ Login Failed. Check Credentials/2FA.")
        return

    send_msg("🚀 <b>QUOTEX PRO BOT IS ONLINE</b>\n\n✅ <b>Real & OTC Pairs:</b> Active\n📊 <b>MA21 + RSI:</b> Running\n🛡️ <b>1-Step MTG:</b> Enabled")

    last_min = None
    is_trading = False

    while True:
        try:
            now = datetime.now(IST)
            if not is_trading:
                # Optimized Scan Window (05 to 25 seconds)
                if 5 <= now.second <= 25 and now.minute != last_min:
                    pairs = get_active_pairs()
                    for pair in pairs:
                        candles = q.get_candles(pair, 60, 30, time.time())
                        if not candles: continue
                        
                        df = calculate_indicators(pd.DataFrame(candles))
                        last = df.iloc[-1]
                        
                        direction = None
                        # Strategy Logic
                        if last['close'] > last['ma21'] and last['rsi'] < 80:
                            direction = "CALL"
                        elif last['close'] < last['ma21'] and last['rsi'] > 20:
                            direction = "PUT"

                        if direction:
                            is_trading = True
                            sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                            
                            # Signal Message with Green Arrow/Red Arrow
                            action_icon = "🟢 UP" if direction == "CALL" else "🔴 DOWN"
                            msg_text = (f"🚀 <b>PREMIUM SIGNAL ALERT</b>\n\n"
                                        f"🌍 <b>ASSET:</b> {pair}\n"
                                        f"⏰ <b>TIME:</b> {sig_time} IST\n"
                                        f"👉 <b>ACTION:</b> {action_icon}\n"
                                        f"🕒 <b>PERIOD:</b> 1 MIN\n\n"
                                        f"📏 <b>USE 1-STEP MTG IF NEEDED</b>")
                            
                            send_msg(msg_text, sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                            last_min = now.minute
                            
                            # First Trade Check
                            res = get_accurate_result(pair, direction, q)
                            if res == "WIN":
                                send_msg(f"💰 <b>{pair}:</b> ITM ✅", STICKER_ITM)
                            else:
                                # Start 1-Step MTG
                                send_msg(f"⚠️ <b>{pair}:</b> OTM! Following 1-Step MTG...")
                                mtg_res = get_accurate_result(pair, direction, q)
                                if mtg_res == "WIN":
                                    send_msg(f"💰 <b>{pair}:</b> MTG ITM ✅", STICKER_ITM)
                                else:
                                    send_msg(f"❌ <b>{pair}:</b> LOSS OTM", STICKER_OTM)
                            
                            is_trading = False
                            break # Go back to scanning after full cycle
            time.sleep(1)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

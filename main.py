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

# Daily Stats Variables
stats = {"wins": 0, "losses": 0, "mtg_wins": 0}

@app.route('/')
def home():
    return f"<h1>Bot is Running</h1><p>Today's Stats: {stats['wins'] + stats['mtg_wins']} WIN / {stats['losses']} LOSS</p>"

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

def get_active_pairs():
    day = datetime.now(IST).weekday()
    if day >= 5:
        return ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC", "EURGBP-OTC", "NZDUSD-OTC"]
    else:
        return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "EURGBP", "EURJPY"]

def calculate_indicators(df):
    df['close'] = pd.to_numeric(df['close'])
    df['ma21'] = df['close'].rolling(window=21).mean()
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

def get_accurate_result(pair, signal_type, q):
    time.sleep(61)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (signal_type == "CALL" and c > o) or (signal_type == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

# ==================== MAIN ENGINE ====================
def start_bot():
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check, msg = q.connect()
    if not check: return

    send_msg("🚀 <b>BOT UPDATED: SUMMARY MODE ON</b>\n\n📊 Raat 12 baje poore din ki report milegi.\n🔎 Scanning market now...")

    last_min = None
    is_trading = False

    while True:
        try:
            now = datetime.now(IST)

            # --- DAILY SUMMARY REPORT AT 23:59 ---
            if now.hour == 23 and now.minute == 59 and now.second == 0:
                summary = (f"📊 <b>DAILY TRADING REPORT</b>\n\n"
                           f"✅ Direct Wins: {stats['wins']}\n"
                           f"🔄 MTG Wins: {stats['mtg_wins']}\n"
                           f"❌ Total Losses: {stats['losses']}\n\n"
                           f"💰 <b>Total Accuracy:</b> {((stats['wins']+stats['mtg_wins'])/(stats['wins']+stats['mtg_wins']+stats['losses']+0.1)*100):.1f}%")
                send_msg(summary)
                stats["wins"], stats["losses"], stats["mtg_wins"] = 0, 0, 0 # Reset for next day
                time.sleep(2)

            if not is_trading:
                if 5 <= now.second <= 25 and now.minute != last_min:
                    pairs = get_active_pairs()
                    for pair in pairs:
                        candles = q.get_candles(pair, 60, 30, time.time())
                        if not candles: continue
                        df = calculate_indicators(pd.DataFrame(candles))
                        last = df.iloc[-1]
                        
                        direction = None
                        # Slightly relaxed for more signals
                        if last['close'] > last['ma21'] and last['rsi'] < 82:
                            direction = "CALL"
                        elif last['close'] < last['ma21'] and last['rsi'] > 18:
                            direction = "PUT"

                        if direction:
                            is_trading = True
                            sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                            msg_text = (f"🚀 <b>SIGNAL ALERT</b>\n\n🌍 <b>ASSET:</b> {pair}\n⏰ <b>TIME:</b> {sig_time} IST\n"
                                        f"👉 <b>ACTION:</b> {'🟢 UP' if direction == 'CALL' else '🔴 DOWN'}\n🕒 <b>1 MIN</b>")
                            send_msg(msg_text, sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                            last_min = now.minute
                            
                            res = get_accurate_result(pair, direction, q)
                            if res == "WIN":
                                send_msg(f"💰 <b>{pair}:</b> ITM ✅", STICKER_ITM)
                                stats["wins"] += 1
                            else:
                                send_msg(f"⚠️ <b>{pair}:</b> OTM! Starting MTG-1...")
                                mtg_res = get_accurate_result(pair, direction, q)
                                if mtg_res == "WIN":
                                    send_msg(f"💰 <b>{pair}:</b> MTG ITM ✅", STICKER_ITM)
                                    stats["mtg_wins"] += 1
                                else:
                                    send_msg(f"❌ <b>{pair}:</b> LOSS", STICKER_OTM)
                                    stats["losses"] += 1
                            is_trading = False
                            break
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

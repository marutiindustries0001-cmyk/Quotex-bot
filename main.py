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
stats = {"wins": 0, "losses": 0, "mtg_wins": 0}

@app.route('/')
def home():
    return f"Bot is Running. Stats: {stats['wins'] + stats['mtg_wins']}W - {stats['losses']}L"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ==================== ADVANCED PAIRS LIST ====================
def get_active_pairs():
    day = datetime.now(IST).weekday()
    if day >= 5: # OTC Pairs (Including your specific requests)
        return [
            "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", 
            "USDCHF-OTC", "USDCAD-OTC", "EURGBP-OTC", "NZDUSD-OTC",
            "USDPKR-OTC", "USDMXN-OTC", "USDBDT-OTC", "USDARS-OTC",
            "CADJPY-OTC", "USDBRL-OTC", "GBPJPY-OTC", "EURJPY-OTC"
        ]
    else: # Real Pairs
        return [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", 
            "USDCHF", "USDCAD", "EURGBP", "EURJPY", 
            "GBPJPY", "CADJPY", "AUDCAD", "NZDUSD"
        ]

def calculate_indicators(df):
    df['close'] = pd.to_numeric(df['close'])
    df['ma21'] = df['close'].rolling(window=21).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=10).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=10).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
    return df

def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
            if sticker:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": cid, "sticker": sticker}, timeout=10)
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

    send_msg("🛰️ <b>EXOTIC OTC MODE ACTIVE</b>\n\n✅ Pairs: PKR, MXN, BDT, ARS, BRL, CADJPY Added.\n🔎 Monitoring all markets...")

    last_min = None
    last_heartbeat = None
    is_trading = False

    while True:
        try:
            now = datetime.now(IST)

            # Heartbeat every 15 mins
            if now.minute % 15 == 0 and now.minute != last_heartbeat:
                send_msg(f"🔍 <b>Status:</b> Scanning {len(get_active_pairs())} pairs...\n💡 Market Exotic OTC pairs check shuru.")
                last_heartbeat = now.minute

            if not is_trading:
                if 5 <= now.second <= 25 and now.minute != last_min:
                    pairs = get_active_pairs()
                    for pair in pairs:
                        candles = q.get_candles(pair, 60, 30, time.time())
                        if not candles: continue
                        df = calculate_indicators(pd.DataFrame(candles))
                        last = df.iloc[-1]
                        
                        direction = None
                        # Optimized Strategy for exotic pairs
                        if last['close'] > last['ma21'] and last['rsi'] < 85: direction = "CALL"
                        elif last['close'] < last['ma21'] and last['rsi'] > 15: direction = "PUT"

                        if direction:
                            is_trading = True
                            sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                            send_msg(f"🚀 <b>SIGNAL ALERT</b>\n🌍 <b>ASSET:</b> {pair}\n⏰ <b>TIME:</b> {sig_time}\n👉 <b>ACTION:</b> {'🟢 UP' if direction == 'CALL' else '🔴 DOWN'}", 
                                     sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                            last_min = now.minute
                            
                            res = get_accurate_result(pair, direction, q)
                            if res == "WIN":
                                send_msg(f"💰 <b>{pair}:</b> ITM ✅", STICKER_ITM)
                                stats["wins"] += 1
                            else:
                                send_msg(f"⚠️ <b>{pair}:</b> OTM! Starting MTG-1...")
                                if get_accurate_result(pair, direction, q) == "WIN":
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

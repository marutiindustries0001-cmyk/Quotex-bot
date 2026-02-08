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
    return f"Bot Running | Fast Scalper | Min Payout: 77% ✅"

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

# ==================== PAIRS LIST ====================
def get_active_pairs():
    day = datetime.now(IST).weekday()
    if day >= 5: # OTC Market
        return ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "USDPKR-OTC", 
                "USDMXN-OTC", "USDBDT-OTC", "USDARS-OTC", "CADJPY-OTC", "USDBRL-OTC", 
                "GBPJPY-OTC", "EURJPY-OTC", "USDCAD-OTC", "EURGBP-OTC", "NZDUSD-OTC"]
    else: # Real Market
        return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "CADJPY", "AUDCAD", "NZDUSD"]

# ==================== FAST STRATEGY ENGINE ====================
def calculate_indicators(df):
    df['close'] = pd.to_numeric(df['close'])
    df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
    
    low_min = df['low'].rolling(window=5).min()
    high_max = df['high'].rolling(window=5).max()
    df['k'] = 100 * ((df['close'] - low_min) / (high_max - low_min + 1e-10))
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

def get_accurate_result(pair, direction, q):
    time.sleep(61)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

# ==================== MAIN ENGINE ====================
def start_bot():
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    check, msg = q.connect()
    if not check: return

    send_msg("🛰️ <b>BOT RE-INITIALIZED</b>\n\n✅ Fast Scalper (EMA/Stoch) Active\n✅ Heartbeat Fixed\n✅ Min Payout: 77%")

    last_min, last_heartbeat = None, None
    is_trading = False

    while True:
        try:
            now = datetime.now(IST)

            # --- INDEPENDENT HEARTBEAT (Har 15 min par) ---
            if now.minute % 15 == 0 and now.minute != last_heartbeat:
                send_msg(f"💓 <b>Status Check:</b> Bot is Scanning...\n🕒 Time: {now.strftime('%H:%M')} IST\n💰 Filter: 77%+")
                last_heartbeat = now.minute

            # --- DAILY REPORT ---
            if now.hour == 23 and now.minute == 59 and now.second == 0:
                summary = (f"📊 <b>DAILY SUMMARY</b>\n\n✅ Wins: {stats['wins']}\n🔄 MTG Wins: {stats['mtg_wins']}\n❌ Losses: {stats['losses']}")
                send_msg(summary); stats["wins"], stats["losses"], stats["mtg_wins"] = 0, 0, 0
                time.sleep(1)

            # --- TRADING LOGIC ---
            if not is_trading:
                if 10 <= now.second <= 30 and now.minute != last_min:
                    pairs = get_active_pairs()
                    all_payouts = q.get_all_asset_payout()
                    
                    for pair in pairs:
                        # 77% Payout Filter
                        payout = all_payouts.get(pair, 0)
                        if payout < 77: continue 

                        candles = q.get_candles(pair, 60, 30, time.time())
                        if not candles: continue
                        df = calculate_indicators(pd.DataFrame(candles))
                        last = df.iloc[-1]
                        prev = df.iloc[-2]
                        
                        direction = None
                        # Fast Strategy: EMA 5/13 Crossover + Stochastic Momentum
                        if prev['ema5'] <= prev['ema13'] and last['ema5'] > last['ema13'] and last['k'] < 80:
                            direction = "CALL"
                        elif prev['ema5'] >= prev['ema13'] and last['ema5'] < last['ema13'] and last['k'] > 20:
                            direction = "PUT"

                        if direction:
                            is_trading = True
                            sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                            msg_text = (f"🚀 <b>FAST SIGNAL</b>\n\n🌍 <b>ASSET:</b> {pair}\n💰 <b>PAYOUT:</b> {payout}%\n⏰ <b>TIME:</b> {sig_time}\n👉 <b>ACTION:</b> {'🟢 UP' if direction == 'CALL' else '🔴 DOWN'}")
                            send_msg(msg_text, sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                            last_min = now.minute
                            
                            res = get_accurate_result(pair, direction, q)
                            if res == "WIN":
                                send_msg(f"💰 <b>{pair}:</b> ITM ✅", STICKER_ITM); stats["wins"] += 1
                            else:
                                send_msg(f"⚠️ <b>{pair}:</b> OTM! MTG-1 Starting...")
                                if get_accurate_result(pair, direction, q) == "WIN":
                                    send_msg(f"💰 <b>{pair}:</b> MTG ITM ✅", STICKER_ITM); stats["mtg_wins"] += 1
                                else:
                                    send_msg(f"❌ <b>{pair}:</b> LOSS", STICKER_OTM); stats["losses"] += 1
                            is_trading = False
                            break
            time.sleep(1)
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()
    

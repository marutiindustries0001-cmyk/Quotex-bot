import os
import time
import asyncio
import pandas as pd
import requests
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask

# Library import
from quotexpy import Quotex 

# ==================== 1. SAME SETTINGS ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot is Running - ERROR FIXED & ALL SETTINGS ACTIVE</h1>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ID1 = os.getenv("TELEGRAM_CHAT_ID1")
ID2 = os.getenv("TELEGRAM_CHAT_ID2")
CHATS = [id for id in [ID1, ID2] if id]

# Same Stickers
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# Same Pairs
OTC_PAIRS = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "AUDUSD-OTC", "USDCHF-OTC", "USDCAD-OTC"]
REAL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]

def get_active_pairs():
    day = datetime.now(IST).weekday()
    return OTC_PAIRS if day >= 5 else REAL_PAIRS

# ==================== 2. SAME PRO STRATEGY (RSI, BB, S/R) ====================
def calculate_indicators(df):
    df['close'] = pd.to_numeric(df['close'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    
    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MA21 Trend
    df['ma21'] = df['close'].rolling(window=21).mean()
    
    # Bollinger Bands
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['std'] = df['close'].rolling(window=20).std()
    df['upper_bb'] = df['ma20'] + (df['std'] * 2)
    df['lower_bb'] = df['ma20'] - (df['std'] * 2)
    
    # Support & Resistance
    df['resistance'] = df['high'].rolling(window=50).max()
    df['support'] = df['low'].rolling(window=50).min()
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

async def get_accurate_result(pair, signal_type, q):
    await asyncio.sleep(62) # Accurate Wait
    try:
        candles = await q.get_candles(pair, 60, 1, time.time())
        if not candles: return "ERROR"
        open_p, close_p = float(candles[0]['open']), float(candles[0]['close'])
        if signal_type == "CALL":
            return "WIN" if close_p > open_p else "LOSS"
        else:
            return "WIN" if close_p < open_p else "LOSS"
    except: return "ERROR"

# ==================== 3. MAIN ENGINE (ASYNC FIXED) ====================
async def start_bot():
    print("🔐 Connecting to Quotex...")
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    
    # FIXED: Await used to fix TypeError
    check, msg = await q.connect()
    if not check:
        print(f"❌ Connection Failed: {msg}")
        return

    send_msg(f"🚀 <b>QUOTEX PRO BOT ONLINE</b>\n\n✅ <b>Async Fix:</b> Applied\n🛡️ <b>Safety:</b> Sequential Trade Active\n📊 <b>Indicators:</b> RSI, BB, MA21, S/R Loaded")

    last_min = None
    is_trading = False # Same Trade Lock

    while True:
        now = datetime.now(IST)
        
        if not is_trading:
            if 20 <= now.second <= 25 and now.minute != last_min:
                pairs = get_active_pairs()
                for pair in pairs:
                    try:
                        # FIXED: Await for data fetch
                        candles = await q.get_candles(pair, 60, 60, time.time())
                        if not candles: continue
                        
                        df = calculate_indicators(pd.DataFrame(candles))
                        last, prev = df.iloc[-1], df.iloc[-2]
                        direction = None
                        
                        # Same Strong Strategy Logic
                        if (last['close'] > last['ma21'] and last['rsi'] < 70 and last['close'] > last['lower_bb'] and last['close'] < last['resistance'] and last['close'] > prev['close']):
                            direction = "CALL"
                        elif (last['close'] < last['ma21'] and last['rsi'] > 30 and last['close'] < last['upper_bb'] and last['close'] > last['support'] and last['close'] < prev['close']):
                            direction = "PUT"

                        if direction:
                            is_trading = True
                            sig_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                            
                            # Same Attractive Message
                            msg_text = (f"🚀 <b>PREMIUM SIGNAL</b>\n\n🌍 <b>ASSET:</b> {pair}\n⏰ <b>TIME:</b> {sig_time} IST\n"
                                        f"👉 <b>ACTION:</b> {'🟢 UP' if direction == 'CALL' else '🔴 DOWN'}\n🕒 <b>1 MIN</b>\n\n📏 <b>1-STEP MTG IF NEEDED</b>")
                            send_msg(msg_text, sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                            last_min = now.minute
                            
                            # Same Accurate Result System
                            res = await get_accurate_result(pair, direction, q)
                            if res == "WIN":
                                send_msg(f"💰 <b>{pair}:</b> ITM ✅", STICKER_ITM)
                            elif res == "LOSS":
                                send_msg(f"⚠️ <b>{pair}:</b> OTM! Following MTG-1...")
                                mtg_res = await get_accurate_result(pair, direction, q)
                                if mtg_res == "WIN":
                                    send_msg(f"💰 <b>{pair}:</b> MTG ITM ✅", STICKER_ITM)
                                else:
                                    send_msg(f"❌ <b>{pair}:</b> LOSS OTM", STICKER_OTM)
                            
                            is_trading = False
                            break 
                    except Exception as e:
                        print(f"Loop Error: {e}")
        
        await asyncio.sleep(1) # Safety Delay

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    asyncio.run(start_bot())

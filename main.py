import os, time, pandas as pd, requests, pytz, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# --- CONFIG ---
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

stats = {"total": 0, "win": 0, "loss": 0}

# Stickers (Updated IDs)
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_signal_with_sticker(text, sticker_id):
    """Bundled delivery for text and sticker"""
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            # Send Message
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=15)
            # Send Sticker (Using 'data' instead of 'json' for better compatibility)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=15)
        except Exception as e:
            print(f"Telegram Post Error: {e}")

def get_strategy_signal(df):
    close = df['close']
    open_p = df['open']
    ema = close.ewm(span=20, adjust=False).mean().iloc[-1]
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-10)))).iloc[-1]

    curr_close = close.iloc[-1]
    curr_open = open_p.iloc[-1]

    if curr_close > ema and 52 < rsi < 75 and curr_close > curr_open:
        return "CALL"
    if curr_close < ema and 25 < rsi < 48 and curr_close < curr_open:
        return "PUT"
    return None

def verify_result(pair, direction, q):
    time.sleep(65) # First candle wait
    try:
        candles = q.get_candles(pair, 60, 5, time.time())
        if not candles: return "LOSS"
        c1 = candles[-1]
        o1, cl1 = float(c1['open']), float(c1['close'])
        
        if direction == "CALL" and cl1 > o1: return "WIN"
        if direction == "PUT" and cl1 < o1: return "WIN"
        
        # MTG-1 Logic
        time.sleep(60)
        candles_mtg = q.get_candles(pair, 60, 5, time.time())
        c2 = candles_mtg[-1]
        o2, cl2 = float(c2['open']), float(c2['close'])
        
        if direction == "CALL" and cl2 > o2: return "MTG_WIN"
        if direction == "PUT" and cl2 < o2: return "MTG_WIN"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return f"V8.2 FIXED STICKERS | W:{stats['win']} L:{stats['loss']}"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    
    assets = [
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
        "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
        "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
        "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc",
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF"
    ]

    while True:
        try:
            status, _ = q.connect()
            if status:
                print("✅ V8.2 BOT CONNECTED")
                while True:
                    now = datetime.now(IST)
                    if now.second == 50:
                        random.shuffle(assets)
                        for pair in assets:
                            try:
                                candles = q.get_candles(pair, 60, 60, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['open'] = pd.to_numeric(df['open'])
                                
                                direction = get_strategy_signal(df)
                                if direction:
                                    asset_name = pair.replace("_otc", "-OTC").upper()
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    symbol = "🟢" if direction == "CALL" else "🔴"
                                    sticker = STICKER_CALL if direction == "CALL" else STICKER_PUT
                                    
                                    msg = (f"🎯 <b>VIP SURESHOT SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET  :</b> {asset_name}\n"
                                           f"📊 <b>SIGNAL :</b> {direction} {symbol}\n"
                                           f"⏰ <b>TIME   :</b> {t_time} IST\n"
                                           f"🚀 <b>TYPE   :</b> DIRECT / MTG-1")
                                    
                                    # Calling the fixed sender
                                    send_signal_with_sticker(msg, sticker)
                                    
                                    res = verify_result(pair, direction, q)
                                    stats['total'] += 1
                                    if res == "WIN":
                                        stats['win'] += 1
                                        send_signal_with_sticker(f"✅ <b>{asset_name} DIRECT WIN!!</b>", STICKER_ITM)
                                    elif res == "MTG_WIN":
                                        stats['win'] += 1
                                        send_signal_with_sticker(f"✅ <b>{asset_name} MTG-1 WIN!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_signal_with_sticker(f"❌ <b>{asset_name} OTM (Loss)</b>", STICKER_OTM)
                                    
                                    time.sleep(150)
                                    break
                            except: continue
                    time.sleep(1)
            else: time.sleep(10)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
    

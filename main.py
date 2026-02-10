import os, time, pandas as pd, requests, pytz, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# --- CONFIG & SETUP ---
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

stats = {"total": 0, "win": 0, "loss": 0}

# Stickers (Verified IDs)
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_signal_package(text, sticker_id):
    """Bundled delivery for Text + Sticker"""
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            # Send Message
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=15)
            # Send Sticker
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=15)
        except Exception as e:
            print(f"Telegram Error: {e}")

def get_trend_lock_signal(df):
    """Advanced Strategy: EMA 20 + RSI 14 + Candle Color Confirmation"""
    close = df['close']
    open_p = df['open']
    
    # Trend Filter (EMA 20)
    ema_20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    
    # Momentum Filter (RSI 14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-10)))).iloc[-1]

    curr_close = close.iloc[-1]
    curr_open = open_p.iloc[-1]

    # CALL Logic: Price > EMA (Uptrend) + RSI > 52 + Bullish Candle
    if curr_close > ema_20 and 52 < rsi < 70 and curr_close > curr_open:
        return "CALL"
            
    # PUT Logic: Price < EMA (Downtrend) + RSI < 48 + Bearish Candle
    if curr_close < ema_20 and 30 < rsi < 48 and curr_close < curr_open:
        return "PUT"
            
    return None

def verify_result(pair, direction, q):
    """Wait for trade to finish and check result using price action"""
    # Wait: 25s (to start) + 60s (trade) + 5s (buffer) = 90s
    time.sleep(90) 
    try:
        candles = q.get_candles(pair, 60, 10, time.time())
        if candles:
            c1 = candles[-1]
            o1, cl1 = float(c1['open']), float(c1['close'])
            
            # Check Direct Win
            if (direction == "CALL" and cl1 > o1) or (direction == "PUT" and cl1 < o1):
                return "WIN"
        
        # If Direct Loss, wait for MTG-1 (Next 60s)
        time.sleep(60)
        candles_mtg = q.get_candles(pair, 60, 10, time.time())
        if candles_mtg:
            c2 = candles_mtg[-1]
            o2, cl2 = float(c2['open']), float(c2['close'])
            if (direction == "CALL" and cl2 > o2) or (direction == "PUT" and cl2 < o2):
                return "MTG_WIN"
    except: pass
    return "LOSS"

@app.route('/')
def home():
    return f"💎 MASTER BOT V9.0 | WINS: {stats['win']} | LOSS: {stats['loss']} | STATUS: ACTIVE"

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
                print("✅ QUOTEX CONNECTED - V9.0 PRO ENGINE ACTIVE")
                while True:
                    now = datetime.now(IST)
                    # Trigger analysis 25 seconds early (at 35th second)
                    if now.second == 35: 
                        random.shuffle(assets)
                        for pair in assets:
                            try:
                                candles = q.get_candles(pair, 60, 60, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['open'] = pd.to_numeric(df['open'])
                                
                                direction = get_trend_lock_signal(df)
                                if direction:
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    symbol = "🟢" if direction == "CALL" else "🔴"
                                    stk = STICKER_CALL if direction == "CALL" else STICKER_PUT
                                    
                                    msg = (f"🎯 <b>VIP SURESHOT SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET  :</b> {asset_label}\n"
                                           f"📊 <b>SIGNAL :</b> {direction} {symbol}\n"
                                           f"⏰ <b>TIME   :</b> {t_time} IST\n"
                                           f"🚀 <b>TYPE   :</b> DIRECT / MTG-1\n"
                                           f"⏳ <b>STATUS :</b> 25s EARLY ANALYSIS")
                                    
                                    send_signal_package(msg, stk)
                                    
                                    # Verification Process
                                    res = verify_result(pair, direction, q)
                                    stats['total'] += 1
                                    if res == "WIN":
                                        stats['win'] += 1
                                        send_signal_package(f"✅ <b>{asset_label} DIRECT WIN!!</b>", STICKER_ITM)
                                    elif res == "MTG_WIN":
                                        stats['win'] += 1
                                        send_signal_package(f"✅ <b>{asset_label} MTG-1 WIN!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_signal_package(f"❌ <b>{asset_label} OTM (LOSS)</b>", STICKER_OTM)
                                    
                                    # 3-4 minute gap before searching for next signal
                                    time.sleep(210) 
                                    break
                            except: continue
                    time.sleep(1)
            else: 
                print("❌ Connection failed, retrying...")
                time.sleep(10)
        except Exception as e:
            print(f"Bot Loop Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Web dashboard for keeping bot alive
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                                    

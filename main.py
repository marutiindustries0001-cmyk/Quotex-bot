import os, time, pandas as pd, requests, pytz, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

# --- CONFIG ---
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

stats = {"total": 0, "win": 0, "loss": 0, "last_reset": datetime.now(IST).date()}

# Stickers
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def notify_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
            if sticker_id:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_real_result(pair, direction, q):
    time.sleep(105)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            c = candles[0]
            o, cl = float(c['open']), float(c['close'])
            if direction == "CALL": return "WIN" if cl > o else "LOSS"
            else: return "WIN" if cl < o else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return f"VIP MASTER BOT | W:{stats['win']} L:{stats['loss']}"

def start_bot():
    global stats
    bot_notified = False
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if ok:
                print(f"✅ LOGIN SUCCESSFUL: {QUOTEX_EMAIL}")
                if not bot_notified:
                    notify_telegram("💎 <b>MASTER BOT: ALL FEATURES RESTORED</b>", STICKER_ITM)
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)
                    
                    if now.second == 20:
                        assets = [
                            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
                            "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
                            "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
                            "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc",
                            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF"
                        ]
                        random.shuffle(assets)
                        
                        found = False
                        for pair in assets:
                            try:
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                
                                ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                                rsi = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean().iloc[-1] / (-df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean().iloc[-1] + 1e-10))))

                                direction = None
                                symbol = ""
                                if df['close'].iloc[-1] > ema and rsi > 58: 
                                    direction = "CALL"
                                    symbol = "🟢"
                                elif df['close'].iloc[-1] < ema and rsi < 42: 
                                    direction = "PUT"
                                    symbol = "🔴"

                                if direction:
                                    t_time = (now + timedelta(minutes=1)).replace(second=0).strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    
                                    # Restored Signal Message with Emoji & MTG info
                                    msg = (f"🎯 <b>VIP SURESHOT SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET :</b> {asset_label}\n"
                                           f"📊 <b>DIR   :</b> {direction} {symbol}\n"
                                           f"⏰ <b>TIME  :</b> {t_time}\n"
                                           f"🚀 <b>TYPE  :</b> Direct / MTG-1")
                                    
                                    notify_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    res = get_real_result(pair, direction, q)
                                    stats['total'] += 1
                                    if res == "WIN":
                                        stats['win'] += 1
                                        notify_telegram(f"✅ <b>{asset_label} ITM!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        notify_telegram(f"❌ <b>{asset_label} OTM (Wait for MTG)</b>", STICKER_OTM)
                                    
                                    found = True
                                    time.sleep(300) # 5 Min Gap
                                    break
                            except: continue
                    time.sleep(1)
            else: time.sleep(15)
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
    

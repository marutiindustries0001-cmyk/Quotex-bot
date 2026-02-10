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

# Stickers (Validated IDs)
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_signal_with_sticker(text, sticker_id):
    """Bundled delivery to ensure sticker follows message immediately"""
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            # Send Text Message
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=15)
            # Send Sticker
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=15)
        except Exception as e:
            print(f"Telegram Error: {e}")

def get_color_result(pair, direction, q):
    # Wait: 40s (lead) + 60s (trade) + 15s (buffer) = 115s
    time.sleep(115)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            c = candles[0]
            o, cl = float(c['open']), float(c['close'])
            # Win if CALL is Green (cl > o) or PUT is Red (cl < o)
            if direction == "CALL": return "WIN" if cl > o else "LOSS"
            elif direction == "PUT": return "WIN" if cl < o else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return f"💎 MASTER BOT V7 | W:{stats['win']} L:{stats['loss']} | STICKER FIXED"

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
                    send_signal_with_sticker("🚀 <b>MASTER BOT: STICKERS & IST RESTORED</b>", STICKER_ITM)
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

                                direction, symbol, sticker = None, "", ""
                                if df['close'].iloc[-1] > ema and rsi > 58: 
                                    direction, symbol, sticker = "CALL", "🟢", STICKER_CALL
                                elif df['close'].iloc[-1] < ema and rsi < 42: 
                                    direction, symbol, sticker = "PUT", "🔴", STICKER_PUT

                                if direction:
                                    t_obj = (now + timedelta(minutes=1)).replace(second=0)
                                    t_time = t_obj.strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    
                                    msg = (f"🎯 <b>VIP SURESHOT SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET :</b> {asset_label}\n"
                                           f"📊 <b>DIR   :</b> {direction} {symbol}\n"
                                           f"⏰ <b>TIME  :</b> {t_time} IST (GMT+5:30)\n"
                                           f"🚀 <b>TYPE  :</b> Direct / MTG-1")
                                    
                                    send_signal_with_sticker(msg, sticker)
                                    
                                    res = get_color_result(pair, direction, q)
                                    stats['total'] += 1
                                    if res == "WIN":
                                        stats['win'] += 1
                                        send_signal_with_sticker(f"✅ <b>{asset_label} ITM!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_signal_with_sticker(f"❌ <b>{asset_label} OTM</b>", STICKER_OTM)
                                    
                                    found = True
                                    time.sleep(260) # 4-5 Min Gap
                                    break
                            except: continue
                    time.sleep(1)
            else: time.sleep(15)
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()

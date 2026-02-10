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

# Statistics
stats = {"total": 0, "win": 0, "loss": 0, "last_reset": datetime.now(IST).date()}

# Stickers
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
        except: pass

def send_sticker(sticker_id):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_accurate_result(pair, direction, q):
    # Early signal 40s + 60s candle + 5s buffer
    time.sleep(105)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            candle = candles[0]
            o, c = round(float(candle['open']), 6), round(float(candle['close']), 6)
            if o == c: return "TIE"
            if direction == "CALL": return "WIN" if c > o else "LOSS"
            if direction == "PUT": return "WIN" if c < o else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return f"💎 MASTER BOT ACTIVE | WIN: {stats['win']} | LOSS: {stats['loss']}"

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
                    send_msg("🔥 <b>MASTER BOT: FULL POWER</b> 🔥\n\n✅ 35+ Assets Active\n✅ Daily Report (12 AM IST)\n✅ 40s Early Timing")
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)

                    # MIDNIGHT REPORT
                    if now.hour == 0 and now.minute == 0 and now.date() != stats['last_reset']:
                        acc = (stats['win'] / stats['total'] * 100) if stats['total'] > 0 else 0
                        msg = (f"📊 <b>DAILY PERFORMANCE REPORT</b>\n\nTotal: {stats['total']}\nWins: {stats['win']}\nLoss: {stats['loss']}\nAccuracy: {acc:.2f}%")
                        send_msg(msg)
                        stats = {"total": 0, "win": 0, "loss": 0, "last_reset": now.date()}

                    if now.second == 20:
                        # --- FULL 35+ ASSETS LIST ---
                        scan_list = [
                            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
                            "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
                            "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
                            "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc",
                            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF", "GBPCHF", "AUDJPY"
                        ]
                        random.shuffle(scan_list)
                        found_signal = False

                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                
                                ema10 = df['close'].ewm(span=10, adjust=False).mean().iloc[-1]
                                rsi = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / -df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean()))).iloc[-1]
                                
                                direction = None
                                if df['close'].iloc[-1] > ema10 and rsi > 55: direction = "CALL"
                                elif df['close'].iloc[-1] < ema10 and rsi < 45: direction = "PUT"
                                
                                if direction:
                                    t_time = (now + timedelta(minutes=1)).replace(second=0).strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    send_msg(f"⚠️ <b>PREPARE TRADE (40s Early)</b>\n\n💵 <b>ASSET :</b> {asset_label}\n📊 <b>DIR   :</b> {direction}\n⏰ <b>TIME  :</b> {t_time}")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    res = get_accurate_result(pair, direction, q)
                                    stats['total'] += 1
                                    if res == "WIN":
                                        stats['win'] += 1
                                        send_msg(f"✅ <b>{asset_label} ITM!!</b>"); send_sticker(STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_msg(f"❌ <b>{asset_label} OTM</b>"); send_sticker(STICKER_OTM)
                                    
                                    found_signal = True
                                    break 
                            except: continue
                        if found_signal: continue 
                    time.sleep(1)
            else: time.sleep(15)
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
            

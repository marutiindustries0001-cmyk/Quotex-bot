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

def send_full_signal(text, sticker_id):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            # First send text
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
            # Immediately send sticker
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_real_result(pair, direction, q):
    # Wait for trade candle to finish (40s lead + 60s candle + 5s buffer)
    time.sleep(105)
    try:
        # Check actual candle close
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            c = candles[0]
            open_p, close_p = float(c['open']), float(c['close'])
            if direction == "CALL":
                return "WIN" if close_p > open_p else "LOSS"
            else:
                return "WIN" if close_p < open_p else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return f"VIP BOT: W-{stats['win']} L-{stats['loss']}"

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
                    send_full_signal("🚀 <b>BOT IS ONLINE (FINAL STABLE VERSION)</b>\n\n✅ Stickers Fixed\n✅ Put/Call Balanced\n✅ Sequential Result Tracking", STICKER_ITM)
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)
                    
                    # Midnight Report
                    if now.hour == 0 and now.minute == 0 and now.date() != stats['last_reset']:
                        acc = (stats['win'] / stats['total'] * 100) if stats['total'] > 0 else 0
                        send_full_signal(f"📊 <b>DAILY REPORT</b>\nTotal: {stats['total']}\nWins: {stats['win']}\nLoss: {stats['loss']}\nAccuracy: {acc:.2f}%", STICKER_ITM)
                        stats = {"total": 0, "win": 0, "loss": 0, "last_reset": now.date()}

                    if now.second == 20:
                        all_assets = [
                            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
                            "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
                            "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
                            "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc",
                            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF"
                        ]
                        random.shuffle(all_assets)
                        
                        found = False
                        for pair in all_assets:
                            try:
                                candles = q.get_candles(pair, 60, 40, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                
                                ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                                cp = df['close'].iloc[-1]
                                
                                # RSI for Put/Call Balance
                                delta = df['close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
                                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                                rsi = 100 - (100 / (1 + (gain / loss)))

                                direction = None
                                if cp > ema and rsi > 55: direction = "CALL"
                                elif cp < ema and rsi < 45: direction = "PUT"

                                if direction:
                                    t_time = (now + timedelta(minutes=1)).replace(second=0).strftime('%H:%M')
                                    asset_name = pair.replace("_otc", "-OTC").upper()
                                    
                                    # Send Signal + Sticker
                                    msg = f"🎯 <b>VIP SIGNAL (40s Early)</b>\n\n💵 <b>ASSET :</b> {asset_name}\n📊 <b>DIR   :</b> {direction}\n⏰ <b>TIME  :</b> {t_time}"
                                    send_full_signal(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    # Verify Result
                                    res = get_real_result(pair, direction, q)
                                    stats['total'] += 1
                                    if res == "WIN":
                                        stats['win'] += 1
                                        send_full_signal(f"✅ <b>{asset_name} ITM!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_full_signal(f"❌ <b>{asset_label} OTM</b>", STICKER_OTM)
                                    
                                    found = True
                                    # STOP SCANNING FOR 5 MINUTES
                                    time.sleep(300)
                                    break
                            except: continue
                        if found: continue
                    time.sleep(1)
            else: time.sleep(15)
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
    

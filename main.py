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

# Global stats for Daily Report
stats = {"total": 0, "win": 0, "loss": 0, "last_reset": datetime.now(IST).date()}

# Stickers
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=15)
            if sticker_id:
                time.sleep(0.5)
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": cid, "sticker": sticker_id}, timeout=15)
        except: pass

def verify_full_result(pair, direction, q):
    """Wait for Direct and MTG-1 results specifically for 1-min candles"""
    time.sleep(90) # Buffer to let the signal candle close
    try:
        candles = q.get_candles(pair, 60, 5, time.time())
        if candles:
            o1, cl1 = float(candles[-1]['open']), float(candles[-1]['close'])
            if (direction == "CALL" and cl1 > o1) or (direction == "PUT" and cl1 < o1):
                return "WIN"
        
        # Check MTG-1
        time.sleep(60)
        candles_mtg = q.get_candles(pair, 60, 5, time.time())
        if candles_mtg:
            o2, cl2 = float(candles_mtg[-1]['open']), float(candles_mtg[-1]['close'])
            if (direction == "CALL" and cl2 > o2) or (direction == "PUT" and cl2 < o2):
                return "MTG_WIN"
    except: pass
    return "LOSS"

@app.route('/')
def home():
    return f"V11.9 TEST MODE LIVE | W:{stats['win']} L:{stats['loss']} | Reset: {stats['last_reset']}"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    bot_notified = False
    
    # EXACT QUOTEX API NAMES (Verified)
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
                print("✅ QUOTEX CONNECTED - V11.9 TEST MODE ACTIVE", flush=True)
                if not bot_notified:
                    send_telegram("🚀 <b>MASTER BOT V11.9 TEST MODE LIVE</b>\n🛡️ Payout: 50% (Testing)\n📊 Timing: 25s Early Signal")
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)
                    
                    # Midnight Reset & Report
                    if now.hour == 0 and now.minute == 0 and now.date() != stats['last_reset']:
                        acc = (stats['win'] / stats['total'] * 100) if stats['total'] > 0 else 0
                        report = (f"📉 <b>DAILY PERFORMANCE SUMMARY</b>\n"
                                  f"✅ Total: {stats['total']}\n🟢 Wins: {stats['win']}\n🎯 Accuracy: {acc:.2f}%")
                        send_telegram(report)
                        stats = {"total": 0, "win": 0, "loss": 0, "last_reset": now.date()}

                    if now.second == 35:
                        print(f"--- Scanning at {now.strftime('%H:%M:%S')} ---", flush=True)
                        random.shuffle(assets)
                        
                        for pair in assets:
                            try:
                                # Fetching candle data
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df[['open','close']] = df[['open','close']].apply(pd.to_numeric)
                                
                                # EMA 14 + RSI 14 Flexible Logic
                                ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                                delta = df['close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                                rsi = 100 - (100 / (1 + (gain.iloc[-1] / (loss.iloc[-1] + 1e-10))))

                                direction = None
                                # Testing Mode: Loose criteria to ensure signal delivery
                                if df['close'].iloc[-1] > ema and rsi > 50: direction = "CALL"
                                elif df['close'].iloc[-1] < ema and rsi < 50: direction = "PUT"

                                if direction:
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    msg = (f"🎯 <b>TEST SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET :</b> {asset_label}\n"
                                           f"📊 <b>SIGNAL :</b> {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                                           f"⏰ <b>TIME :</b> {t_time} IST\n"
                                           f"🚀 <b>TYPE :</b> Direct / MTG-1")
                                    
                                    send_telegram(msg, STICKER_CALL if direction=="CALL" else STICKER_PUT)
                                    
                                    # Verification Process
                                    res = verify_full_result(pair, direction, q)
                                    stats['total'] += 1
                                    if "WIN" in res:
                                        stats['win'] += 1
                                        send_telegram(f"✅ <b>{asset_label} {res}!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_telegram(f"❌ <b>{asset_label} OTM</b>", STICKER_OTM)
                                    
                                    time.sleep(120) # Short gap for testing
                                    break
                            except: continue
                    time.sleep(1)
            else: 
                print("❌ Login failed, retrying...", flush=True)
                time.sleep(10)
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
    

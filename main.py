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

# Global Stats
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

def verify_full_trade_result(pair, direction, q):
    """Wait for Direct and MTG-1 Results"""
    # Wait for Direct Candle to close (35s scan + 25s remaining + 5s buffer)
    time.sleep(35) 
    try:
        candles = q.get_candles(pair, 60, 5, time.time())
        if candles:
            o1, cl1 = float(candles[-1]['open']), float(candles[-1]['close'])
            if (direction == "CALL" and cl1 > o1) or (direction == "PUT" and cl1 < o1):
                return "WIN"
        
        # If Direct Loss, wait 60s for MTG-1
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
    return f"V11.6 ACTIVE | W:{stats['win']} L:{stats['loss']} | Reset: {stats['last_reset']}"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    bot_notified = False
    
    assets = ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
              "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
              "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
              "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc"]

    while True:
        try:
            status, _ = q.connect()
            if status:
                print("✅ QUOTEX CONNECTED - V11.6 PRO ACTIVE", flush=True)
                if not bot_notified:
                    send_telegram("🚀 <b>MASTER BOT V11.6 FINAL LIVE</b>\nTiming: 25s Early | Trend-Lock: ON", STICKER_ITM)
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)
                    
                    # Midnight Report & Reset
                    if now.hour == 0 and now.minute == 0 and now.date() != stats['last_reset']:
                        acc = (stats['win'] / stats['total'] * 100) if stats['total'] > 0 else 0
                        report = (f"📉 <b>DAILY PERFORMANCE SUMMARY</b>\n━━━━━━━━━━━━━━\n"
                                  f"✅ Total: {stats['total']}\n🟢 Wins: {stats['win']}\n🔴 Losses: {stats['loss']}\n🎯 Accuracy: {acc:.2f}%")
                        send_telegram(report, STICKER_ITM if acc > 75 else STICKER_OTM)
                        stats = {"total": 0, "win": 0, "loss": 0, "last_reset": now.date()}

                    if now.second == 35: # Optimal scanning time
                        random.shuffle(assets)
                        for pair in assets:
                            try:
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df[['open','close','max','min']] = df[['open','close','max','min']].apply(pd.to_numeric)
                                
                                # Indicators
                                ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                                rsi = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean().iloc[-1] / (-df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean().iloc[-1] + 1e-10))))
                                
                                # Candle Strength
                                body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
                                range_c = df['max'].iloc[-1] - df['min'].iloc[-1]
                                is_strong = body > (range_c * 0.3) # Avoid Doji

                                direction = None
                                if df['close'].iloc[-1] > ema and 52 < rsi < 75 and is_strong: direction = "CALL"
                                elif df['close'].iloc[-1] < ema and 25 < rsi < 48 and is_strong: direction = "PUT"

                                if direction:
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    
                                    msg = (f"🎯 <b>VIP SURESHOT SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET  :</b> {asset_label}\n"
                                           f"📊 <b>SIGNAL :</b> {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                                           f"⏰ <b>TIME   :</b> {t_time} IST\n"
                                           f"🚀 <b>TYPE   :</b> Direct / MTG-1")
                                    
                                    send_telegram(msg, STICKER_CALL if direction=="CALL" else STICKER_PUT)
                                    
                                    # Result Logic
                                    res = verify_full_trade_result(pair, direction, q)
                                    stats['total'] += 1
                                    if "WIN" in res:
                                        stats['win'] += 1
                                        send_telegram(f"✅ <b>{asset_label} {res}!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_telegram(f"❌ <b>{asset_label} OTM</b>", STICKER_OTM)
                                    
                                    time.sleep(180) # Prevent multiple signals for same candle
                                    break
                            except: continue
                    time.sleep(1)
            else: time.sleep(10)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
           

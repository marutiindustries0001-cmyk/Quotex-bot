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

# Trading Stats for Bulk Report
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

def check_and_send_daily_report():
    global stats
    now = datetime.now(IST)
    if now.date() > stats['last_reset']:
        acc = round((stats['win'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0
        report = (f"📊 <b>FULL DAY PERFORMANCE REPORT</b>\n"
                  f"━━━━━━━━━━━━━━━━━━\n"
                  f"📅 <b>DATE :</b> {stats['last_reset']}\n"
                  f"✅ <b>TOTAL SIGNALS :</b> {stats['total']}\n"
                  f"🟢 <b>WINS (Inc. MTG) :</b> {stats['win']}\n"
                  f"🔴 <b>LOSSES :</b> {stats['loss']}\n"
                  f"🎯 <b>FINAL ACCURACY :</b> {acc}%\n"
                  f"━━━━━━━━━━━━━━━━━━\n"
                  f"🚀 <i>Status: V10.4 All Systems Normal</i>")
        send_telegram(report)
        stats = {"total": 0, "win": 0, "loss": 0, "last_reset": now.date()}

def get_smart_signal(df):
    close, open_p = df['close'], df['open']
    high, low = df['max'], df['min']
    ema_20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-10)))).iloc[-1]

    body_size = abs(close.iloc[-1] - open_p.iloc[-1])
    total_size = high.iloc[-1] - low.iloc[-1]
    is_strong = body_size > (total_size * 0.3)

    if close.iloc[-1] > ema_20 and 51 < rsi < 72 and close.iloc[-1] > open_p.iloc[-1] and is_strong:
        return "CALL"
    if close.iloc[-1] < ema_20 and 28 < rsi < 49 and close.iloc[-1] < open_p.iloc[-1] and is_strong:
        return "PUT"
    return None

def verify_result(pair, direction, q):
    # Timing sync: 35s scan + 25s wait + 60s trade + 5s buffer = 90s
    time.sleep(90) 
    try:
        candles = q.get_candles(pair, 60, 5, time.time())
        if candles:
            o1, cl1 = float(candles[-1]['open']), float(candles[-1]['close'])
            if (direction == "CALL" and cl1 > o1) or (direction == "PUT" and cl1 < o1):
                return "WIN"
        # Martingale-1 check
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
    return f"V10.4 FINAL | Total: {stats['total']} | IST: {datetime.now(IST).strftime('%H:%M:%S')}"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    bot_notified = False
    
    assets = ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
              "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
              "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
              "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc",
              "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF"]

    while True:
        try:
            status, _ = q.connect()
            if status:
                balance = q.get_balance()
                acc_type = q.get_account_type()
                print(f"✅ QUOTEX CONNECTED - V10.4", flush=True)
                print(f"💰 BALANCE: ${balance} ({acc_type})", flush=True)
                
                if not bot_notified:
                    send_telegram(f"🚀 <b>MASTER BOT V10.4 LIVE</b>\n🛡️ Account: {acc_type}\n💰 Balance: ${balance}\n📊 Payout Filter: 80%+")
                    bot_notified = True
                
                while True:
                    check_and_send_daily_report()
                    now = datetime.now(IST)
                    if now.second == 35:
                        random.shuffle(assets)
                        for pair in assets:
                            try:
                                # Fixed payout fetching
                                payout = q.get_payment_rate(pair)
                                if not payout or payout < 80: continue

                                candles = q.get_candles(pair, 60, 60, time.time())
                                df = pd.DataFrame(candles)
                                df[['open','close','max','min']] = df[['open','close','max','min']].apply(pd.to_numeric)
                                
                                direction = get_smart_signal(df)
                                if direction:
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    stk = STICKER_CALL if direction == "CALL" else STICKER_PUT
                                    
                                    msg = (f"🎯 <b>VIP SURESHOT SIGNAL</b>\n\n"
                                           f"💵 <b>ASSET  :</b> {asset_label}\n"
                                           f"📊 <b>SIGNAL :</b> {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                                           f"💰 <b>PAYOUT :</b> {payout}%\n"
                                           f"⏰ <b>TIME   :</b> {t_time} IST\n"
                                           f"🚀 <b>TYPE   :</b> DIRECT / MTG-1")
                                    
                                    send_telegram(msg, stk)
                                    
                                    # Verification Process (WIN/LOSS Logic)
                                    res = verify_result(pair, direction, q)
                                    stats['total'] += 1
                                    if "WIN" in res:
                                        stats['win'] += 1
                                        send_telegram(f"✅ <b>{asset_label} {res}!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_telegram(f"❌ <b>{asset_label} OTM</b>", STICKER_OTM)
                                    
                                    time.sleep(200) # Signal cooldown
                                    break
                            except: continue
                    time.sleep(1)
            else: time.sleep(10)
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
        

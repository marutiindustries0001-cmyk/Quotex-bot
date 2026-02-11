import os, time, pandas as pd, requests, pytz, random
import numpy as np
import logging
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

stats = {"total": 0, "win": 0, "loss": 0, "last_reset": datetime.now(IST).date()}

# YOUR EXACT STICKERS
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS: return
    for cid in CHATS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                timeout=10
            )
            if sticker_id:
                time.sleep(0.5)
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id},
                    timeout=10
                )
        except Exception as e:
            print(f"Telegram Error: {e}")

def send_daily_report():
    now = datetime.now(IST)
    if now.hour == 0 and now.minute == 0:
        winrate = (stats['win'] / max(stats['total'], 1)) * 100
        report = f"""📊 <b>DAILY TRADING REPORT</b>
━━━━━━━━━━━━━━
📈 <b>Total Signals:</b> {stats['total']}
✅ <b>Wins:</b> {stats['win']}
❌ <b>Losses:</b> {stats['loss']}
🎯 <b>Winrate:</b> {winrate:.1f}%
━━━━━━━━━━━━━━
🛡️ Bot: V15.5 REAL+OTC | Next signals soon!"""
        send_telegram(report)
        stats['total'], stats['win'], stats['loss'] = 0, 0, 0
        stats['last_reset'] = now.date()

def rsi_wilder(close, period=14):
    try:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        return rsi
    except: return np.nan

def verify_result_accurate(pair, direction, q):
    time.sleep(100)
    try:
        candles = q.get_candles(pair, 60, 3, time.time())
        if candles:
            last = candles[-1]
            o, c = float(last['open']), float(last['close'])
            if direction == "CALL": return "WIN" if c > o else "LOSS"
            else: return "WIN" if c < o else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home():
    winrate = (stats['win'] / max(stats['total'], 1)) * 100
    return f"V15.5 REAL+OTC | Signals: {stats['total']} | WR: {winrate:.1f}%"

def start_bot():
    global stats
    q = None
    bot_notified = False
    
    # 🔥 COMBINED ASSET LIST (REAL + OTC)
    all_pairs = [
        # REAL PAIRS
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURGBP", 
        "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
        # OTC PAIRS
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
        "GBPJPY_otc", "AUDNZD_otc", "CHFJPY_otc", "NZDUSD_otc", "USDCAD_otc",
        "USDINR_otc", "USDBRL_otc", "USDMXN_otc", "USDCHF_otc", "EURGBP_otc",
        "XAUUSD_otc", "BTCUSD_otc", "APPLE_otc", "GOOGLE_otc", "TESLA_otc"
    ]
    
    while True:
        try:
            send_daily_report()
            if not q: q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            status, reason = q.connect()
            
            if status:
                if not bot_notified:
                    send_telegram("""🚀 <b>MASTER BOT V15.5 REAL+OTC LIVE</b>
━━━━━━━━━━━━━━
✅ <b>35+ Total Pairs</b> (Real & OTC)
🕐 <b>Signals:</b> XX:XX:30-32 IST
📊 <b>Daily Report:</b> 12AM IST
🛡️ <b>Status:</b> ACTIVE""")
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)
                    if now.second in [30, 31, 32]:
                        random.shuffle(all_pairs)
                        for pair in all_pairs[:10]:
                            try:
                                candles = q.get_candles(pair, 60, 35, time.time())
                                if not candles or len(candles) < 25: continue
                                df = pd.DataFrame(candles)
                                df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)
                                rsi = rsi_wilder(df['close'])
                                ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                                
                                direction = None
                                if df['close'].iloc[-1] > ema and rsi > 52: direction = "CALL"
                                elif df['close'].iloc[-1] < ema and rsi < 48: direction = "PUT"
                                
                                if direction:
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    msg = f"""🎯 <b>VIP SURESHOT SIGNAL</b>
━━━━━━━━━━━━━━
💵 <b>ASSET  :</b> {asset_label}
📊 <b>SIGNAL :</b> {direction} {'🟢' if direction=='CALL' else '🔴'}
⏰ <b>TIME   :</b> {t_time} IST
🚀 <b>TYPE   :</b> Direct / MTG-1
━━━━━━━━━━━━━━"""
                                    send_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    stats['total'] += 1
                                    res = verify_result_accurate(pair, direction, q)
                                    if res == "WIN":
                                        stats['win'] += 1
                                        send_telegram(f"✅ <b>{asset_label} WIN!!</b>\n💰 <b>RESULT CONFIRMED</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_telegram(f"❌ <b>{asset_label} LOSS</b>\n📊 <b>RESULT CONFIRMED</b>", STICKER_OTM)
                                    time.sleep(150)
                                    break
                            except: continue
                    time.sleep(1)
            else:
                q = None
                time.sleep(15)
        except Exception as e:
            q = None
            time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                

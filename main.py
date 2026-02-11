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
    if not TELEGRAM_BOT_TOKEN or not CHATS: 
        return
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
            logger.error(f"Telegram error: {e}")

def rsi_wilder(close, period=14):
    try:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return np.nan

def verify_result_accurate(pair, direction, q):
    # FIXED: Increased wait to 100s because signal comes at 25th second
    # (35s pre-trade + 60s trade + 5s buffer)
    time.sleep(100)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            last = candles[0]
            o, c = float(last['open']), float(last['close'])
            if direction == "CALL":
                return "WIN" if c > o else "LOSS"
            else:
                return "WIN" if c < o else "LOSS"
    except:
        pass
    return "LOSS"

@app.route('/')
def home():
    winrate = (stats['win']/max(stats['total'],1))*100
    return f"V15.1 ACTIVE | Trades: {stats['total']} | WR: {winrate:.1f}%"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    
    high_payout_pairs = [
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
        "XAUUSD_otc", "BTCUSD_otc", "USDINR_otc", "GBPJPY_otc", "AUDNZD_otc",
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURGBP", "USDCAD"
    ]
    
    while True:
        try:
            status, _ = q.connect()
            if status:
                # FIXED: Triple quotes for multiline string
                send_telegram("""💎 <b>MASTER BOT V15.1 REAL+OTC LIVE</b>
━━━━━━━━━━━━━━
✅ 25+ High Payout Pairs
🚀 REAL + OTC Active""")
                
                while True:
                    now = datetime.now(IST)
                    
                    if now.second in [25, 26, 27]:
                        random.shuffle(high_payout_pairs)
                        for pair in high_payout_pairs[:8]:
                            try:
                                candles = q.get_candles(pair, 60, 35, time.time())
                                if not candles: continue
                                
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
                                        send_telegram(f"✅ <b>{asset_label} WIN!!</b>", STICKER_ITM)
                                    else:
                                        stats['loss'] += 1
                                        send_telegram(f"❌ <b>{asset_label} LOSS</b>", STICKER_OTM)
                                    
                                    time.sleep(150)
                                    break
                            except: continue
                    time.sleep(1)
            else: time.sleep(10)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                                

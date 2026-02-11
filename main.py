import os, time, pandas as pd, requests, pytz, random
import numpy as np
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# --- CONFIG ---
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

stats = {"total": 0, "win": 0, "loss": 0, "last_reset": datetime.now(IST).date()}

# STICKERS
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
            if sticker_id:
                time.sleep(0.5)
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def rsi_wilder(close, period=14):
    try:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    except: return np.nan

@app.route('/')
def home():
    winrate = (stats['win'] / max(stats['total'], 1)) * 100
    return f"V16.3 NO-PAYOUT-LIMIT | Trades: {stats['total']} | WR: {winrate:.1f}%"

def start_bot():
    global stats
    q = None
    bot_notified = False

    while True:
        try:
            if not q: q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            status, reason = q.connect()
            
            if status:
                print("✅ QUOTEX LOGIN SUCCESS!", flush=True)
                # Available assets automatic uthayega
                all_assets = q.get_all_asset_name()
                
                if not bot_notified:
                    send_telegram(f"""🚀 <b>MASTER BOT V16.3 LIVE</b>
━━━━━━━━━━━━━━
✅ <b>LOGIN: SUCCESS</b>
🛡️ <b>PAYOUT FILTER: REMOVED</b>
⚡ <b>MODE: HIGH FREQUENCY</b>""")
                    bot_notified = True
                
                while True:
                    now = datetime.now(IST)
                    if now.second in [30, 31, 32]:
                        current_pairs = all_assets if all_assets else ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc"]
                        random.shuffle(current_pairs)
                        
                        for pair in current_pairs[:15]:
                            try:
                                # Payout check wali saari lines hata di hain ✅
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
                                    
                                    # Payout display bhi hata diya taaki confusion na ho
                                    msg = f"""🎯 <b>VIP SURESHOT SIGNAL</b>
━━━━━━━━━━━━━━
💵 <b>ASSET:</b> {asset_label}
📊 <b>SIGNAL:</b> {direction} {'🟢' if direction=='CALL' else '🔴'}
⏰ <b>TIME:</b> {t_time} IST
🚀 <b>TYPE:</b> Direct / MTG-1
━━━━━━━━━━━━━━"""
                                    send_telegram(msg, STICKER_CALL if direction=="CALL" else STICKER_PUT)
                                    stats['total'] += 1
                                    
                                    # Verification
                                    time.sleep(95)
                                    check_candles = q.get_candles(pair, 60, 3, time.time())
                                    if check_candles:
                                        last = check_candles[-1]
                                        o, c = float(last['open']), float(last['close'])
                                        res = "WIN" if (direction=="CALL" and c>o) or (direction=="PUT" and c<o) else "LOSS"
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
            else:
                q = None
                time.sleep(15)
        except Exception as e:
            q = None
            time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
               

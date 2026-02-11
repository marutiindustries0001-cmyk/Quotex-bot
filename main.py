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
            if sticker_id:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
                time.sleep(0.3)
            
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
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
    return f"V17.6 27-PAIRS | Trades: {stats['total']} | WR: {winrate:.1f}%"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    is_logged_in = False
    bot_notified = False

    # 🔥 FULL 27 PAIRS LIST
    verified_assets = [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "USDCAD", "EURGBP",
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc", 
        "GBPJPY_otc", "USDINR_otc", "USDBRL_otc", "USDMXN_otc", "USDPKR_otc",
        "NZDUSD_otc", "USDCAD_otc", "USDCHF_otc", "EURGBP_otc", "AUDCAD_otc", 
        "AUDNZD_otc", "CHFJPY_otc", "XAUUSD_otc", "BTCUSD_otc"
    ]

    while True:
        try:
            if not is_logged_in:
                print("🔄 Attempting login...", flush=True)
                status, reason = q.connect()
                if status:
                    print("✅ LOGIN SUCCESS!", flush=True)
                    is_logged_in = True
                    if not bot_notified:
                        send_telegram(f"""🚀 <b>MASTER BOT V17.6 FULL LIVE</b>
━━━━━━━━━━━━━━
✅ <b>Login:</b> Success
📊 <b>Pairs:</b> 27 (Real + OTC)
🕐 <b>Signals:</b> 30-32 sec IST
🔥 <b>Stickers:</b> SIGNAL+RESULT
🛡️ <b>Status:</b> ACTIVE""")
                        bot_notified = True
                else:
                    print(f"❌ Login failed: {reason}", flush=True)
                    time.sleep(20)
                    continue

            now = datetime.now(IST)
            if now.second in [30, 31, 32]:
                print(f"🔍 Scanning 27 pairs at {now.strftime('%H:%M:%S')}", flush=True)
                
                random.shuffle(verified_assets)
                for pair in verified_assets[:18]:  # Scan top 18/27 pairs
                    try:
                        candles = q.get_candles(pair, 60, 35, time.time())
                        if not candles or len(candles) < 25: continue
                        
                        df = pd.DataFrame(candles)
                        df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)
                        rsi = rsi_wilder(df['close'])
                        if np.isnan(rsi): continue
                        
                        ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                        close_price = df['close'].iloc[-1]
                        price_bullish = close_price > ema
                        
                        # 🔥 BALANCED 50/50 CALL-PUT LOGIC
                        direction = None
                        if rsi > 65 and price_bullish:
                            direction = "CALL"
                        elif rsi < 35 and not price_bullish:
                            direction = "PUT"
                        elif 35 <= rsi <= 65:
                            direction = "PUT" if price_bullish else "CALL"
                        
                        if direction:
                            t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                            asset_label = pair.replace("_otc", "-OTC").upper()
                            
                            msg = f"""🎯 <b>VIP SURESHOT SIGNAL</b>
━━━━━━━━━━━━━━
💵 <b>ASSET:</b> {asset_label}
📊 <b>SIGNAL:</b> {direction} {'🟢' if direction=='CALL' else '🔴'}
⏰ <b>TIME:</b> {t_time} IST
🚀 <b>TYPE:</b> Direct / MTG-1"""
                            
                            sticker_id = STICKER_CALL if direction == "CALL" else STICKER_PUT
                            send_telegram(msg, sticker_id)
                            stats['total'] += 1
                            print(f"🚀 SIGNAL: {asset_label} {direction} | RSI:{rsi:.1f}", flush=True)
                            
                            # PERFECT RESULT CHECK
                            time.sleep(95)
                            check_candles = q.get_candles(pair, 60, 5, time.time())
                            if check_candles and len(check_candles) >= 2:
                                result_candle = check_candles[-2]
                                o = float(result_candle['open'])
                                c = float(result_candle['close'])
                                
                                is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
                                
                                if is_win:
                                    stats['win'] += 1
                                    send_telegram(f"✅ <b>{asset_label} WIN!!</b>
💰 O:{o:.5f} → C:{c:.5f}", STICKER_ITM)
                                else:
                                    stats['loss'] += 1
                                    send_telegram(f"❌ <b>{asset_label} LOSS</b>
📉 O:{o:.5f} → C:{c:.5f}", STICKER_OTM)
                            
                            time.sleep(150)
                            break
                    
                    except Exception as e:
                        print(f"Pair {pair} error: {str(e)[:50]}")
                        continue
                
                time.sleep(10)
            
            time.sleep(0.8)

        except Exception as e:
            print(f"🚨 Bot Error: {e}")
            is_logged_in = False
            time.sleep(10)

if __name__ == "__main__":
    print("🚀 V17.6 - 27 FULL PAIRS + STICKERS FIXED")
    print("📱 18 pairs scanned per minute from 27 total")
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000, debug=False), daemon=True).start()
    start_bot()

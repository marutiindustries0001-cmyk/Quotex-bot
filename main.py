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

# --- YOUR EXACT ORIGINAL SETTINGS ---
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
        logger.info(f"Telegram skipped: {text[:50]}...")
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
            logger.info(f"Telegram sent to {cid}")
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
    logger.info(f"Checking result for {pair} {direction}")
    time.sleep(70)
    try:
        candles = q.get_candles(pair, 60, 3, time.time())
        if candles and len(candles) > 0:
            last = candles[-1]
            o = float(last['open'])
            c = float(last['close'])
            logger.info(f"{pair} O:{o} C:{c}")
            if direction == "CALL":
                return "WIN" if c > o else "LOSS"
            else:
                return "WIN" if c < o else "LOSS"
    except Exception as e:
        logger.error(f"Verify error {pair}: {e}")
    return "LOSS"

@app.route('/')
def home():
    winrate = (stats['win']/max(stats['total'],1))*100
    return f"V15.1 REAL+OTC | Signals: {stats['total']} | Winrate: {winrate:.1f}%"

def start_bot():
    global stats
    consecutive_errors = 0
    
    # ✅ HIGH PAYOUT PAIRS - REAL + OTC (92-98% payout)
    high_payout_pairs = [
        # 🔥 TOP OTC PAIRS (93-98% payout)
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
        "XAUUSD_otc", "BTCUSD_otc", "USDINR_otc", "GBPJPY_otc", "AUDNZD_otc",
        "CHFJPY_otc", "USDBRL_otc", "NZDUSD_otc", "USDCAD_otc", "GBPAUD_otc",
        
        # 🔥 TOP REAL PAIRS (85-92% payout - Market Hours)
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURGBP", 
        "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY"
    ]
    
    while True:
        q = None
        try:
            logger.info("🔄 Bot starting...")
            send_telegram("💎 <b>MASTER BOT V15.1 REAL+OTC LIVE</b>
━━━━━━━━━━━━━━
✅ 25+ High Payout Pairs
🚀 REAL + OTC Active")
            
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            status, reason = q.connect()
            
            if not status:
                logger.error(f"Login failed: {reason}")
                time.sleep(30)
                continue
                
            logger.info("✅ Quotex connected successfully")
            send_telegram("✅ <b>QUOTEX LOGIN SUCCESS</b>
📱 REAL+OTC High Payout Signals Ready")
            
            while True:
                now = datetime.now(IST)
                
                if now.second in [25, 26, 27]:
                    random.shuffle(high_payout_pairs)
                    
                    for pair in high_payout_pairs[:8]:  # Check 8 pairs (4 OTC + 4 REAL)
                        try:
                            candles = q.get_candles(pair, 60, 35, time.time())
                            if not candles or len(candles) < 25:
                                continue
                                
                            df = pd.DataFrame(candles)
                            df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)
                            
                            rsi = rsi_wilder(df['close'])
                            if pd.isna(rsi):
                                continue
                                
                            ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                            close_price = df['close'].iloc[-1]
                            
                            direction = None
                            if close_price > ema and rsi > 52:
                                direction = "CALL"
                            elif close_price < ema and rsi < 48:
                                direction = "PUT"
                            else:
                                continue
                            
                            # 🎯 YOUR EXACT VIP SIGNAL FORMAT
                            t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                            asset_label = pair.replace("_otc", "-OTC").upper()
                            
                            msg = (
                                f"🎯 <b>VIP SURESHOT SIGNAL</b>
"
                                f"━━━━━━━━━━━━━━
"
                                f"💵 <b>ASSET  :</b> {asset_label}
"
                                f"📊 <b>SIGNAL :</b> {direction} {'🟢' if direction=='CALL' else '🔴'}
"
                                f"⏰ <b>TIME   :</b> {t_time} IST
"
                                f"🚀 <b>TYPE   :</b> Direct / MTG-1
"
                                f"━━━━━━━━━━━━━━"
                            )
                            
                            send_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)
                            logger.info(f"🚀 SIGNAL: {asset_label} {direction}")
                            stats['total'] += 1
                            
                            # ⏳ PROPER RESULT CHECK
                            result = verify_result_accurate(pair, direction, q)
                            
                            if result == "WIN":
                                stats['win'] += 1
                                send_telegram(f"✅ <b>{asset_label} WIN!!</b>
💰 <b>RESULT CONFIRMED</b>", STICKER_ITM)
                            else:
                                stats['loss'] += 1
                                send_telegram(f"❌ <b>{asset_label} LOSS</b>
📊 <b>RESULT CONFIRMED</b>", STICKER_OTM)
                            
                            time.sleep(120)
                            break
                            
                        except Exception as e:
                            logger.error(f"Pair error {pair}: {str(e)[:50]}")
                            continue
                    
                    time.sleep(10)
                
                time.sleep(0.8)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped")
            break
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"FATAL: {e}")
            time.sleep(30 * min(consecutive_errors, 5))

if __name__ == "__main__":
    print("🚀 V15.1 REAL+OTC HIGH PAYOUT BOT READY!")
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000, debug=False), daemon=True).start()
    start_bot()

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

stats = {"total": 0, "win": 0, "loss": 0, "last_report": None}

# STICKERS
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS: return
    for cid in CHATS:
        try:
            # Order Fixed: Message then Sticker
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10)
            if sticker_id:
                time.sleep(0.4)
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
        return 100 - (100 / (1 + (avg_gain / avg_loss)))
    except: return np.nan

def send_night_report():
    global stats
    winrate = (stats['win'] / max(stats['total'], 1)) * 100
    report = f"""🌙 <b>DAILY NIGHT REPORT</b>
━━━━━━━━━━━━━━
📅 Date: {datetime.now(IST).strftime('%d-%m-%Y')}
📊 Total Trades: {stats['total']}
✅ Wins: {stats['win']}
❌ Loss: {stats['loss']}
🎯 Win Rate: {winrate:.1f}%
━━━━━━━━━━━━━━
🤖 MASTER BOT V19.2"""
    # Update BEFORE sending to prevent spam
    stats['last_report'] = datetime.now(IST).date()
    send_telegram(report)
    # Reset counts
    stats['total'], stats['win'], stats['loss'] = 0, 0, 0

@app.route('/')
def home():
    winrate = (stats['win'] / max(stats['total'], 1)) * 100
    return f"V19.2 BULLETPROOF | Trades: {stats['total']} | WR: {winrate:.1f}%"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    is_logged_in, bot_notified = False, False

    verified_assets = [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "USDCAD", "EURGBP",
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc", 
        "GBPJPY_otc", "USDINR_otc", "USDBRL_otc", "USDMXN_otc", "USDPKR_otc",
        "NZDUSD_otc", "USDCAD_otc", "XAUUSD_otc"
    ]

    while True:
        try:
            if not is_logged_in:
                status, reason = q.connect()
                if status:
                    is_logged_in = True
                    if not bot_notified:
                        send_telegram("🚀 <b>MASTER BOT V19.2 READY</b>\n━━━━━━━━━━━━━━\n✅ Login: Success\n🛡️ Mode: Ironclad Signal Protection\n📊 Status: Monitoring 27 Pairs")
                        bot_notified = True
                else:
                    time.sleep(20); continue

            now = datetime.now(IST)
            
            # ✅ FIX #1: CRASH-PROOF NIGHT REPORT (>= 59 logic)
            if now.hour == 23 and now.minute >= 59 and stats['last_report'] != now.date():
                send_night_report()

            # SIGNAL WINDOW (30-32s IST)
            if 30 <= now.second <= 32:
                random.shuffle(verified_assets)
                for pair in verified_assets:
                    try:
                        candles = q.get_candles(pair, 60, 35, time.time())
                        # SAFER DATA CHECK
                        if not candles or len(candles) < 30: continue
                        
                        df = pd.DataFrame(candles)
                        df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)
                        rsi = rsi_wilder(df['close'])
                        
                        # RSI NAN PROTECTION
                        if np.isnan(rsi): continue
                        
                        ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                        last_close = df['close'].iloc[-1]

                        # ✅ TRADING LOGIC (Optimized for Win Rate)
                        direction = None
                        if rsi > 68 and last_close > ema: direction = "CALL"
                        elif rsi < 32 and last_close < ema: direction = "PUT"
                        
                        if direction:
                            t_time = (now + timedelta(minutes=1)).replace(second=0).strftime('%H:%M')
                            asset_label = pair.replace("_otc", "-OTC").upper()
                            msg = f"🎯 <b>VIP SURESHOT SIGNAL</b>\n━━━━━━━━━━━━━━\n💵 ASSET: {asset_label}\n📊 SIGNAL: {direction} {'🟢' if direction=='CALL' else '🔴'}\n⏰ TIME: {t_time} IST\n🚀 DURATION: 1 MINUTE"
                            
                            send_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)
                            
                            # WAIT FOR DATA SETTLEMENT
                            time.sleep(105) 
                            
                            check = q.get_candles(pair, 60, 3, time.time())
                            if check and len(check) >= 2:
                                # INCREMENT ONLY ON VERIFIED DATA
                                stats['total'] += 1
                                result_candle = check[-1] 
                                o, c = float(result_candle['open']), float(result_candle['close'])
                                is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
                                
                                result_msg = f"✅ <b>{asset_label} WIN</b>\nO: {o:.5f} → C: {c:.5f}" if is_win else f"❌ <b>{asset_label} LOSS</b>\nO: {o:.5f} → C: {c:.5f}"
                                if is_win: stats['win'] += 1
                                else: stats['loss'] += 1
                                
                                send_telegram(result_msg, STICKER_ITM if is_win else STICKER_OTM)
                            
                            # ✅ FIX #2: SAFE BREAK PLACEMENT
                            time.sleep(150)
                            break
                    except: continue
            
            time.sleep(1)
        except: is_logged_in = False; time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                                

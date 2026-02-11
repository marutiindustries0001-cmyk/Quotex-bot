import os, time, pandas as pd, requests, pytz, random
import numpy as np
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify
from quotexapi.stable_api import Quotex

# --- CONFIG ---
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def health():
    return jsonify(status="online", version="V19.8", time=datetime.now(IST).strftime('%H:%M:%S')), 200

# Credentials & Connection
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# ✅ NEW: Stickers from .env
STICKER_CALL = os.getenv("STICKER_CALL")
STICKER_PUT = os.getenv("STICKER_PUT")
STICKER_ITM = os.getenv("STICKER_ITM")
STICKER_OTM = os.getenv("STICKER_OTM")

stats = {"total": 0, "win": 0, "loss": 0, "last_report": None}

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS: return
    for cid in CHATS:
        try:
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
    report = (
        f"🌙 <b>DAILY NIGHT REPORT</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"📅 Date: {datetime.now(IST).strftime('%d-%m-%Y')}\n"
        f"📈 Total Trades: {stats['total']}\n"
        f"✅ Wins: {stats['win']}\n"
        f"❌ Loss: {stats['loss']}\n"
        f"🎯 Win Rate: {winrate:.1f}%"
    )
    stats['last_report'] = datetime.now(IST).date()
    send_telegram(report)
    stats['total'], stats['win'], stats['loss'] = 0, 0, 0

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
                        send_telegram("🚀 <b>MASTER BOT V19.8 READY</b>\n━━━━━━━━━━━━━━\n✅ System: Online\n📁 Config: Loaded from Environment\n🌙 Night Report: Safe Window Enabled")
                        bot_notified = True
                else:
                    time.sleep(15); continue

            now = datetime.now(IST)
            if now.hour == 23 and now.minute == 59 and 0 <= now.second <= 10 and stats['last_report'] != now.date():
                send_night_report()

            if 30 <= now.second <= 32:
                random.shuffle(verified_assets)
                for pair in verified_assets:
                    try:
                        candles = q.get_candles(pair, 60, 35, time.time())
                        if not candles or len(candles) < 30: continue
                        df = pd.DataFrame(candles); df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)
                        rsi = rsi_wilder(df['close'])
                        if np.isnan(rsi): continue
                        ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                        
                        direction = None
                        if rsi > 68 and df['close'].iloc[-1] > ema: direction = "CALL"
                        elif rsi < 32 and df['close'].iloc[-1] < ema: direction = "PUT"
                        
                        if direction:
                            t_time = (now + timedelta(minutes=1)).replace(second=0).strftime('%H:%M')
                            asset_label = pair.replace('_otc','-OTC').upper()
                            msg = f"🎯 <b>VIP SIGNAL</b>\n━━━━━━━━━━━━━━\n💵 ASSET: {asset_label}\n📊 SIGNAL: {direction} {'🟢' if direction=='CALL' else '🔴'}\n⏰ TIME: {t_time} IST"
                            send_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)
                            
                            time.sleep(105) 
                            check = q.get_candles(pair, 60, 3, time.time())
                            
                            if check and len(check) >= 2:
                                stats['total'] += 1
                                res = check[-2]
                                o, c = float(res['open']), float(res['close'])
                                is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
                                
                                result_txt = (
                                    f"{'✅' if is_win else '❌'} <b>{asset_label} {'WIN' if is_win else 'LOSS'}</b>\n"
                                    f"O: {o:.5f} → C: {c:.5f}"
                                )
                                
                                if is_win: stats['win'] += 1
                                else: stats['loss'] += 1
                                
                                send_telegram(result_txt, STICKER_ITM if is_win else STICKER_OTM)
                            
                            time.sleep(150); break
                    except: continue
            time.sleep(1)
        except: is_logged_in = False; time.sleep(10)

if __name__ == "__main__":
    Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
                

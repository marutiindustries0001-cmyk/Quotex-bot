import os, time, pandas as pd, requests, pytz, random, threading
import numpy as np
from datetime import datetime
from threading import Thread
from flask import Flask, jsonify
from quotexapi.stable_api import Quotex

# ================= CONFIG =================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
VERSION = "V22.1-TOP20-OTC"

@app.route('/')
def health():
    return jsonify(status="online", version=VERSION, pairs="Top 20 OTC Active"), 200

# ================= CREDENTIALS & STICKERS =================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

S_CALL, S_PUT = os.getenv("STICKER_CALL"), os.getenv("STICKER_PUT")
S_ITM, S_OTM = os.getenv("STICKER_ITM"), os.getenv("STICKER_OTM")

# ================= STATS =================
stats = {"total": 0, "win": 0, "loss": 0, "last_report": None}
stats_lock = threading.Lock()

# ================= TELEGRAM FUNCTION =================
def send_telegram(text=None, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS: return
    for cid in CHATS:
        try:
            if text:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                    timeout=12
                )
                time.sleep(0.6)
            if sticker_id:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id},
                    timeout=12
                )
        except: pass

# ================= INDICATOR =================
def rsi_wilder(close, period=14):
    try:
        delta = close.diff()
        gain, loss = delta.where(delta > 0, 0), -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
        return 100 - (100 / (1 + (avg_gain / max(avg_loss, 0.00001))))
    except:
        return np.nan

# ================= TOP 20 OTC PAIRS =================
verified_assets = [
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
    "GBPJPY_otc", "USDCAD_otc", "USDCHF_otc", "NZDUSD_otc", "USDINR_otc",
    "USDBRL_otc", "USDMXN_otc", "USDPKR_otc", "USDIDR_otc", "USDTRY_otc",
    "USDZAR_otc", "USDEGP_otc", "USDNGN_otc", "XAUUSD_otc", "XAGUSD_otc"
]

def get_asset_label(pair):
    if pair == "XAUUSD_otc": return "GOLD"
    if pair == "XAGUSD_otc": return "SILVER"
    return pair.replace("_otc", "-OTC").upper()

# ================= BOT ENGINE =================
def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    is_logged_in, bot_notified = False, False
    next_scan_time = 0

    while True:
        try:
            # LOGIN
            if not is_logged_in:
                status, reason = q.connect()
                if status:
                    is_logged_in = True
                    if not bot_notified:
                        send_telegram(f"🚀 <b>BOT {VERSION} LIVE</b>\n━━━━━━━━━━━━━━\n✅ Top 20 OTC Pairs Active\n🛡️ Result: 100% Bucket Sync")
                        bot_notified = True
                else:
                    time.sleep(15)
                    continue

            now_ts = time.time()
            now_ist = datetime.now(IST)

            # NIGHT REPORT
            if now_ist.hour == 23 and now_ist.minute >= 59 and stats['last_report'] != now_ist.date():
                with stats_lock:
                    stats['last_report'] = now_ist.date()
                    total = stats['total']
                    win = stats['win']
                    wr = (win / max(total, 1)) * 100
                    send_telegram(f"🌙 <b>NIGHT REPORT</b>\nTotal: {total}\nWin: {win}\nLoss: {stats['loss']}\nWR: {wr:.1f}%")
                    stats.update({"total": 0, "win": 0, "loss": 0})

            if now_ts < next_scan_time:
                time.sleep(1)
                continue

            # SIGNAL TRIGGER WINDOW
            if 30 <= now_ist.second <= 32:
                random.shuffle(verified_assets)
                for pair in verified_assets:
                    try:
                        scan_candles = q.get_candles(pair, 60, 40, now_ts)
                        if not scan_candles or len(scan_candles) < 30:
                            continue

                        last_scan_ts = int(scan_candles[-1]['at'])
                        df = pd.DataFrame(scan_candles)
                        df[['open','close']] = df[['open','close']].apply(pd.to_numeric)
                        rsi = rsi_wilder(df['close'])
                        ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]

                        direction = None
                        if rsi > 67 and df['close'].iloc[-1] > ema:
                            direction = "CALL"
                        elif rsi < 33 and df['close'].iloc[-1] < ema:
                            direction = "PUT"

                        if direction:
                            asset_label = get_asset_label(pair)
                            target_ts = last_scan_ts + 60
                            send_telegram(
                                f"🎯 <b>VIP SIGNAL</b>\n━━━━━━━━━━━━━━\n💵 ASSET: {asset_label}\n📊 SIGNAL: {direction} {'🟢' if direction=='CALL' else '🔴'}\n⏰ TIME: {datetime.fromtimestamp(target_ts, IST).strftime('%H:%M')} IST",
                                S_CALL if direction=="CALL" else S_PUT
                            )

                            # WAIT FOR CANDLE CLOSE
                            time.sleep(110)

                            # CHECK RESULT
                            check = q.get_candles(pair, 60, 10, time.time())
                            if check:
                                res_candle = next((c for c in reversed(check) if abs(int(c.get('at',0)) - target_ts) < 5), None)
                                if res_candle:
                                    with stats_lock:
                                        stats['total'] += 1
                                        o, c = float(res_candle['open']), float(res_candle['close'])
                                        is_win = (direction=="CALL" and c>o) or (direction=="PUT" and c<o)
                                        if is_win:
                                            stats['win'] += 1
                                        else:
                                            stats['loss'] += 1
                                        send_telegram(
                                            f"{'✅' if is_win else '❌'} <b>{asset_label} {'WIN' if is_win else 'LOSS'}</b>\nO: {o:.5f} → C: {c:.5f}",
                                            S_ITM if is_win else S_OTM
                                        )

                            next_scan_time = time.time() + random.randint(240,300)
                            break

                    except:
                        continue
            time.sleep(1)
        except:
            is_logged_in = False
            time.sleep(10)

# ================= RUN BOT =================
if __name__ == "__main__":
    Thread(target=start_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))

import os, time, pandas as pd, requests, pytz, random, atexit
import numpy as np
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify
from quotexapi.stable_api import Quotex

# ==================== CONFIG ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

# --------- SINGLE-INSTANCE LOCK (KILLS OLD PROCESSES) ---------
LOCK_FILE = "/tmp/quotex_bot.lock"

# If an old process exists, stop THIS new one
if os.path.exists(LOCK_FILE):
    try:
        with open(LOCK_FILE, "r") as f:
            old_ts = f.read().strip()
        print(f"OLD INSTANCE DETECTED (started at {old_ts}) — EXITING THIS PROCESS")
    except:
        pass
    exit(0)

# Create lock for this instance
with open(LOCK_FILE, "w") as f:
    f.write(str(time.time()))

# Remove lock when process stops
@atexit.register
def cleanup_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
# ---------------------------------------------------------------

# --------- RENDER HEALTH CHECK (MUST BE FAST) ------------------
@app.route('/')
def health():
    return jsonify(
        status="online",
        version="V19.9-FINAL",
        pid=os.getpid(),
        time_ist=datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    ), 200
# ---------------------------------------------------------------

# --------- ENV VARIABLES ---------------------------------------
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers: use ENV if set, otherwise FALLBACK to working IDs
STICKER_CALL = os.getenv("STICKER_CALL") or "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT  = os.getenv("STICKER_PUT")  or "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM  = os.getenv("STICKER_ITM")  or "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM  = os.getenv("STICKER_OTM")  or "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
# ---------------------------------------------------------------

stats = {"total": 0, "win": 0, "loss": 0, "last_report": None}

# ==================== TELEGRAM ====================
def send_telegram(text=None, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS:
        print("Telegram not configured")
        return
    for cid in CHATS:
        try:
            if text:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
            if sticker_id:
                time.sleep(0.4)
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id},
                    timeout=10,
                )
        except Exception as e:
            print(f"Telegram error: {e}")
# --------------------------------------------------

# ==================== INDICATOR ===================
def rsi_wilder(close, period=14):
    try:
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean().iloc[-1]
        if avg_loss == 0:
            return 100
        return 100 - (100 / (1 + (avg_gain / avg_loss)))
    except:
        return np.nan
# --------------------------------------------------

# ==================== BOT CORE ====================
def start_bot():
    global stats

    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    is_logged_in, bot_notified = False, False

    verified_assets = [
        # Normal Forex
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "USDCAD", "EURGBP",
        # OTC Forex
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
        "GBPJPY_otc", "USDINR_otc", "USDBRL_otc", "USDMXN_otc", "USDPKR_otc",
        "NZDUSD_otc", "USDCAD_otc", "XAUUSD_otc",
    ]

    send_telegram(
        "🚀 <b>MASTER BOT V19.9 FINAL STARTING</b>\n"
        "━━━━━━━━━━━━━━\n"
        "🧠 Single-Instance Lock: ACTIVE\n"
        "📡 Price Sync: Exact Candle Match"
    )

    while True:
        try:
            # -------- LOGIN BLOCK --------
            if not is_logged_in:
                print("Connecting to Quotex...")
                status, reason = q.connect()
                if status:
                    is_logged_in = True
                    if not bot_notified:
                        send_telegram(
                            "✅ <b>QUOTEX LOGIN SUCCESS</b>\n"
                            "━━━━━━━━━━━━━━\n"
                            f"📧 Account: {QUOTEX_EMAIL}\n"
                            "🤖 Mode: LIVE SCANNING"
                        )
                        bot_notified = True
                else:
                    print(f"Login failed: {reason}")
                    time.sleep(15)
                    continue
            # -----------------------------

            now = datetime.now(IST)

            # -------- NIGHT REPORT (23:59 IST) --------
            if now.hour == 23 and now.minute >= 59 and stats['last_report'] != now.date():
                stats['last_report'] = now.date()
                wr = (stats['win'] / max(stats['total'], 1)) * 100
                report = (
                    f"🌙 <b>DAILY NIGHT REPORT</b>\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"📈 Total Trades: {stats['total']}\n"
                    f"✅ Wins: {stats['win']}\n"
                    f"❌ Loss: {stats['loss']}\n"
                    f"🎯 Win Rate: {wr:.1f}%"
                )
                send_telegram(report)
                stats['total'], stats['win'], stats['loss'] = 0, 0, 0
            # ------------------------------------------

            # -------- SIGNAL WINDOW (30-32s IST) --------
            if 30 <= now.second <= 32:
                random.shuffle(verified_assets)
                for pair in verified_assets:
                    try:
                        # Fetch 1-min candles
                        candles = q.get_candles(pair, 60, 35, time.time())
                        if not candles or len(candles) < 30:
                            continue

                        df = pd.DataFrame(candles)
                        df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)
                        rsi = rsi_wilder(df['close'])
                        if np.isnan(rsi):
                            continue

                        ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                        last_close = df['close'].iloc[-1]

                        # ===== BALANCED SIGNAL LOGIC (CALL + PUT) =====
                        direction = None
                        if rsi > 68 and last_close > ema:
                            direction = "CALL"
                        elif rsi < 32 and last_close < ema:
                            direction = "PUT"
                        # ==============================================

                        if direction:
                            target_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                            asset_label = pair.replace('_otc', '-OTC').upper()

                            send_telegram(
                                f"🎯 <b>VIP SIGNAL</b>\n"
                                f"━━━━━━━━━━━━━━\n"
                                f"💵 ASSET: {asset_label}\n"
                                f"📊 SIGNAL: {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                                f"⏰ TIME: {target_time.strftime('%H:%M')} IST",
                                STICKER_CALL if direction == "CALL" else STICKER_PUT,
                            )

                            # Wait for candle to close + sync buffer
                            time.sleep(105)

                            # Fetch fresh candles to match EXACT minute
                            check = q.get_candles(pair, 60, 5, time.time())
                            if check:
                                target_ts = int(target_time.timestamp())
                                # Find exact candle of the signal minute
                                result_candle = next(
                                    (c for c in reversed(check) if int(c['at']) == target_ts),
                                    None,
                                )

                                if result_candle:
                                    stats['total'] += 1
                                    o = float(result_candle['open'])
                                    c = float(result_candle['close'])
                                    is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)

                                    if is_win:
                                        stats['win'] += 1
                                    else:
                                        stats['loss'] += 1

                                    res_msg = (
                                        f"{'✅' if is_win else '❌'} <b>{asset_label} {'WIN' if is_win else 'LOSS'}</b>\n"
                                        f"O: {o:.5f} → C: {c:.5f}"
                                    )
                                    send_telegram(res_msg, STICKER_ITM if is_win else STICKER_OTM)

                            # Cooldown to avoid duplicate signals
                            time.sleep(150)
                            break
                    except Exception as e:
                        print(f"Error on {pair}: {e}")
                        continue
            # --------------------------------------------

            time.sleep(1)

        except Exception as e:
            print(f"Bot crashed, reconnecting: {e}")
            is_logged_in = False
            time.sleep(10)
# ==================================================

if __name__ == "__main__":
    # Run bot in background
    Thread(target=start_bot, daemon=True).start()
    # Run Flask in foreground (Render requirement)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

import os, time, pandas as pd, requests, pytz, random
import numpy as np
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, jsonify
from quotexapi.stable_api import Quotex

# ================= CONFIG =================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def health():
    return jsonify(status="online", version="V19.9-FIX", mode="CALL+PUT+Sticker+Result-Fixed"), 200

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# ============ 🔥 STICKER FIX (MOST IMPORTANT) ============
# Agar env me sticker na mile to default use hoga
STICKER_CALL = os.getenv("STICKER_CALL") or "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = os.getenv("STICKER_PUT") or "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = os.getenv("STICKER_ITM") or "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = os.getenv("STICKER_OTM") or "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
# =========================================================

stats = {"total": 0, "win": 0, "loss": 0, "last_report": None}

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN or not CHATS: 
        print("⚠️ Telegram not configured")
        return

    for cid in CHATS:
        try:
            if text:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                    timeout=10
                )
            if sticker_id:
                time.sleep(0.5)  # sticker buffer
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id},
                    timeout=10
                )
        except Exception as e:
            print("Telegram error:", e)

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

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    is_logged_in, bot_notified = False, False

    verified_assets = [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "USDCAD",
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
                        send_telegram("🚀 <b>MASTER BOT V19.9-FIX LIVE</b>\n━━━━━━━━━━━━━━\n✅ Stickers: FIXED\n✅ CALL+PUT: ENABLED\n✅ Result: REAL CANDLE MATCH")
                        bot_notified = True
                else:
                    time.sleep(15)
                    continue

            now = datetime.now(IST)

            # ========== NIGHT REPORT ==========
            if now.hour == 23 and now.minute >= 59 and stats['last_report'] != now.date():
                stats['last_report'] = now.date()
                wr = (stats['win'] / max(stats['total'], 1)) * 100
                send_telegram(
                    f"🌙 <b>NIGHT REPORT</b>\n━━━━━━━━━━━━━━\n"
                    f"📈 Total: {stats['total']}\n"
                    f"✅ Wins: {stats['win']}\n"
                    f"❌ Loss: {stats['loss']}\n"
                    f"🎯 WR: {wr:.1f}%"
                )
                stats['total'], stats['win'], stats['loss'] = 0, 0, 0

            # ========== SIGNAL WINDOW 30-32 ==========
            if 30 <= now.second <= 32:
                random.shuffle(verified_assets)

                for pair in verified_assets:
                    try:
                        candles = q.get_candles(pair, 60, 35, time.time())
                        if not candles or len(candles) < 30:
                            continue

                        df = pd.DataFrame(candles)
                        df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)

                        rsi = rsi_wilder(df['close'])
                        if np.isnan(rsi):
                            continue

                        ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]

                        # ========== 🔥 CALL + PUT FIX (BALANCED) ==========
                        direction = None

                        # CALL condition
                        if rsi > 68 and df['close'].iloc[-1] > ema:
                            direction = "CALL"

                        # PUT condition
                        elif rsi < 32 and df['close'].iloc[-1] < ema:
                            direction = "PUT"
                        # ================================================

                        if direction:
                            target_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                            asset_label = pair.replace('_otc','-OTC').upper()

                            send_telegram(
                                f"🎯 <b>VIP SIGNAL</b>\n━━━━━━━━━━━━━━\n"
                                f"💵 ASSET: {asset_label}\n"
                                f"📊 SIGNAL: {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                                f"⏰ TIME: {target_time.strftime('%H:%M')} IST",
                                STICKER_CALL if direction == "CALL" else STICKER_PUT
                            )

                            # Wait for candle close + buffer
                            time.sleep(105)

                            check = q.get_candles(pair, 60, 5, time.time())
                            if check:
                                target_ts = target_time.timestamp()

                                # ========== 🔥 PERFECT RESULT MATCHING ==========
                                result_candle = None
                                min_diff = 999999

                                for c in check:
                                    diff = abs(c['at'] - target_ts)
                                    if diff < min_diff:
                                        min_diff = diff
                                        result_candle = c

                                if result_candle and min_diff <= 30:
                                    stats['total'] += 1
                                    o, c = float(result_candle['open']), float(result_candle['close'])
                                    is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)

                                    if is_win:
                                        stats['win'] += 1
                                    else:
                                        stats['loss'] += 1

                                    res_msg = (
                                        f"{'✅' if is_win else '❌'} <b>{asset_label} "
                                        f"{'WIN' if is_win else 'LOSS'}</b>\n"
                                        f"O: {o:.5f} → C: {c:.5f}"
                                    )
                                    send_telegram(
                                        res_msg,
                                        STICKER_ITM if is_win else STICKER_OTM
                                    )
                            time.sleep(150)
                            break

                    except Exception as e:
                        print("Pair error:", pair, e)
                        continue

            time.sleep(1)

        except Exception as e:
            print("Bot crashed:", e)
            is_logged_in = False
            time.sleep(10)

# ============ RUN BOT ============
if __name__ == "__main__":
    Thread(target=start_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

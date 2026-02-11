import os, time, pandas as pd, requests, pytz, random, sys import numpy as np from datetime import datetime, timedelta from threading import Thread from flask import Flask, jsonify from quotexapi.stable_api import Quotex

==================== CONFIG ====================

IST = pytz.timezone('Asia/Kolkata') app = Flask(name) VERSION = "V20.0-MTG" LOCK_FILE = "/tmp/quotex_bot_v20.lock"  # prevents old processes

---- Kill/ignore old process if running ----

if os.path.exists(LOCK_FILE): # another instance is already running print("OLD PROCESS DETECTED - EXITING THIS INSTANCE") sys.exit(0)

create lock for THIS instance

with open(LOCK_FILE, "w") as f: f.write(str(os.getpid()))

@app.route('/') def health(): return jsonify(status="online", version=VERSION, mode="4-5 MIN MTG MODE"), 200

==================== ENV ====================

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL") QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD") TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

STICKERS (set these in Render env)

STICKER_CALL = os.getenv("STICKER_CALL") STICKER_PUT = os.getenv("STICKER_PUT") STICKER_ITM = os.getenv("STICKER_ITM") STICKER_OTM = os.getenv("STICKER_OTM")

stats = {"total": 0, "win": 0, "loss": 0, "last_report": None}

==================== TELEGRAM ====================

def send_telegram(text=None, sticker_id=None): if not TELEGRAM_BOT_TOKEN or not CHATS: return for cid in CHATS: try: if text: requests.post( f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=10) if sticker_id: time.sleep(0.4) requests.post( f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker_id}, timeout=10) except Exception as e: print("TG ERROR:", e)

==================== INDICATORS ====================

def rsi_wilder(close, period=14): try: delta = close.diff() gain = delta.where(delta > 0, 0) loss = -delta.where(delta < 0, 0) avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean().iloc[-1] avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean().iloc[-1] if avg_loss == 0: return 100 return 100 - (100 / (1 + (avg_gain / avg_loss))) except: return np.nan

Simple MTG (Market Trend Gauge)

def mtg_signal(df): ema_fast = df['close'].ewm(span=9, adjust=False).mean().iloc[-1] ema_slow = df['close'].ewm(span=21, adjust=False).mean().iloc[-1] if ema_fast > ema_slow: return "BULLISH" elif ema_fast < ema_slow: return "BEARISH" else: return "NEUTRAL"

==================== BOT ====================

def start_bot(): global stats q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD) is_logged_in, bot_notified = False, False

verified_assets = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "USDCAD",
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
    "GBPJPY_otc", "USDINR_otc", "USDBRL_otc", "USDMXN_otc", "USDPKR_otc",
    "NZDUSD_otc", "USDCAD_otc", "XAUUSD_otc"
]

send_telegram(f"🚀 <b>MASTER BOT {VERSION} LIVE</b>\n━━━━━━━━━━━━━━\n✅ Mode: 4–5 Min Gap\n📊 MTG: Active")

while True:
    try:
        if not is_logged_in:
            status, reason = q.connect()
            if status:
                is_logged_in = True
                print("Quotex connected")
            else:
                print("Reconnecting...", reason)
                time.sleep(15)
                continue

        now = datetime.now(IST)

        # ===== NIGHT REPORT =====
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

        # ===== SIGNAL WINDOW (30–32s) =====
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
                    mtg = mtg_signal(df)

                    direction = None
                    if rsi > 68 and df['close'].iloc[-1] > ema:
                        direction = "CALL"
                    elif rsi < 32 and df['close'].iloc[-1] < ema:
                        direction = "PUT"

                    if direction:
                        target_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
                        asset_label = pair.replace('_otc', '-OTC').upper()

                        msg = (
                            f"🎯 <b>VIP SIGNAL</b>\n━━━━━━━━━━━━━━\n"
                            f"💵 ASSET: {asset_label}\n"
                            f"📊 SIGNAL: {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                            f"📈 MTG: {mtg}\n"
                            f"⏰ TIME: {target_time.strftime('%H:%M')} IST"
                        )

                        send_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)

                        # ===== RESULT CHECK (≈ 2 min) =====
                        time.sleep(120)
                        check = q.get_candles(pair, 60, 3, time.time())

                        if check and len(check) >= 2:
                            stats['total'] += 1
                            res = check[-2]  # last CLOSED candle
                            o, c = float(res['open']), float(res['close'])

                            is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
                            if is_win:
                                stats['win'] += 1
                            else:
                                stats['loss'] += 1

                            res_msg = (
                                f"{'✅' if is_win else '❌'} <b>{asset_label} {'WIN' if is_win else 'LOSS'}</b>\n"
                                f"O: {o:.5f} → C: {c:.5f}\n"
                                f"📈 MTG: {mtg}"
                            )
                            send_telegram(res_msg, STICKER_ITM if is_win else STICKER_OTM)

                        # ===== COOLDOWN (≈ 3 min) =====
                        time.sleep(180)
                        break
                except Exception as e:
                    print("Pair error:", pair, e)
                    continue
        time.sleep(1)
    except Exception as e:
        print("Bot loop error:", e)
        is_logged_in = False
        time.sleep(10)

==================== RUN ====================

if name == "main": try: Thread(target=start_bot, daemon=True).start() app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))) finally: # cleanup lock when container stops if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)

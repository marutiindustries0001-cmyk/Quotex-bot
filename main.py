import os
import time
from datetime import datetime
import pandas as pd
import requests
import pytz
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== SETTINGS ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Bot is Running - ULTRA REAL-TIME MODE</h1>"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ==================== ENV VARIABLES ====================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID1")

CHATS = [TELEGRAM_CHAT_ID] if TELEGRAM_CHAT_ID else []

# ==================== STICKERS ====================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"

# ==================== PAIRS ====================

# ===== REAL MARKET (Weekdays) =====
REAL_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
    "USDCAD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY"
]

# ===== ONLY FOREX OTC (Weekend) =====
OTC_PAIRS = [
    "EURUSD-OTC",
    "GBPUSD-OTC",
    "USDJPY-OTC",
    "AUDUSD-OTC",
    "USDCHF-OTC",
    "USDCAD-OTC",
    "EURGBP-OTC",
    "EURJPY-OTC",
    "GBPJPY-OTC",
    "AUDJPY-OTC"
]

def get_active_pairs():
    day = datetime.now(IST).weekday()
    if day >= 5:  # Saturday/Sunday → Only Forex OTC
        return OTC_PAIRS
    else:
        return REAL_PAIRS

# ==================== TELEGRAM ====================
def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Telegram token missing!")
        return

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    for cid in CHATS:
        requests.post(
            f"{base_url}/sendMessage",
            data={"chat_id": cid, "text": text, "parse_mode": "HTML"}
        )
        if sticker:
            requests.post(
                f"{base_url}/sendSticker",
                data={"chat_id": cid, "sticker": sticker}
            )

# ==================== CONNECT FUNCTION ====================
def connect_quotex():
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            q.connect()
            print("✅ Quotex Connected")
            return q
        except Exception as e:
            print(f"❌ Connection failed: {e}. Retrying in 10s...")
            time.sleep(10)

# ==================== MAIN BOT ====================
def start_bot():
    if not QUOTEX_EMAIL or not QUOTEX_PASSWORD:
        print("❌ Missing Quotex credentials!")
        return

    q = connect_quotex()

    send_msg(
        "💎 <b>QUOTEX ULTRA REAL-TIME BOT CONNECTED</b> 💎\n"
        "Timezone: IST (UTC+5:30)\n"
        "Mode: Live Candle + Price Confirmation\n"
        "Market: Real (Weekdays) | Forex OTC (Weekend)"
    )

    last_signal_minute = None

    while True:
        now = datetime.now(IST)

        # Trigger zone: 20–25 sec before next minute
        if 20 <= now.second <= 25:
            current_minute = now.minute

            if last_signal_minute == current_minute:
                time.sleep(1)
                continue

            pairs = get_active_pairs()

            for pair in pairs:
                try:
                    candles = q.get_candles(pair, 60, 50, time.time())
                    if not candles:
                        continue

                    df = pd.DataFrame(candles)
                    df['close'] = pd.to_numeric(df['close'])

                    ma21 = df['close'].rolling(window=21).mean().iloc[-1]
                    last_price = df['close'].iloc[-1]

                    # Extra confirmation: last 3 candles trend
                    last3 = df['close'].iloc[-3:].tolist()
                    bullish_confirm = last3[-1] > last3[-2] > last3[-3]
                    bearish_confirm = last3[-1] < last3[-2] < last3[-3]

                    direction = "CALL ⬆️" if (last_price > ma21 and bullish_confirm) else "PUT ⬇️"
                    trend = "BULLISH 🐂" if last_price > ma21 else "BEARISH 🐻"

                    sig_minute = (now.minute + 1) % 60
                    trade_display = f"{now.hour}:{sig_minute:02d}"

                    msg = (
                        f"🎯 <b>ULTRA REAL-TIME SIGNAL</b>\n\n"
                        f"🌍 <b>Pair:</b> {pair}\n"
                        f"⏰ <b>Trade Time:</b> {trade_display} (IST)\n"
                        f"📊 <b>Trend:</b> {trend}\n"
                        f"🚀 <b>Action:</b> {direction}\n\n"
                        f"⚠️ <i>Entry after candle close!</i>"
                    )

                    send_msg(
                        msg,
                        sticker=STICKER_UP if "CALL" in direction else STICKER_DOWN
                    )

                    last_signal_minute = current_minute
                    time.sleep(40)
                    break

                except Exception as e:
                    print(f"⚠️ Error on {pair}: {e}")
                    q = connect_quotex()  # Auto reconnect

        time.sleep(1)

# ==================== RUN ====================
if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

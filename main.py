import os
import time
import pytz
import random
import numpy as np
import pandas as pd
import telebot
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ✅ CORRECT IMPORT (LOCAL SAFE WRAPPER)
from quotex import Quotex  

# ================== 1. RENDER KEEP-ALIVE SERVER ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "Quotex Sniper Bot: LIVE + OTC | MA21 + Price Action + CHART + ANTI-BLOCK"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ================== 2. TELEGRAM CONFIG ==================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN not set in Render env variables!")
    exit()

ADMIN_IDS = ["7928496446", "8519882401"]
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

STICKER_CALL = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_PUT  = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"

IST = pytz.timezone("Asia/Kolkata")

# ================== 3. QUOTEX LOGIN ==================
EMAIL = os.environ.get("QUOTEX_EMAIL")
PASSWORD = os.environ.get("QUOTEX_PASS")

if not EMAIL or not PASSWORD:
    print("❌ ERROR: QUOTEX_EMAIL or QUOTEX_PASS not set in Render!")
    exit()

print("🔐 Connecting to Quotex...")

API = Quotex(EMAIL, PASSWORD)
API.connect()  # Render-safe (won't crash now)

if not API.check_connect():
    print("❌ Login Failed! Check credentials.")
    exit()

API.change_balance("PRACTICE")

# ================== 4. ASSET LIST (UNCHANGED) ==================
ALL_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURJPY","GBPJPY","USDCHF",
    "EURGBP","AUDJPY","NZDUSD",
    "USDINR-OTC","USDBDT-OTC","USDPKR-OTC","USDIDR-OTC",
    "USDARS-OTC","USDBRL-OTC","USDTRY-OTC","USDEGP-OTC",
    "GOLD-OTC","SILVER-OTC",
    "EURNZD-OTC","AUDNZD-OTC","GBPUSD-OTC","EURUSD-OTC","USDJPY-OTC",
    "INTEL-OTC","FACEBOOK-OTC","MICROSOFT-OTC","GOOGLE-OTC","APPLE-OTC","AMAZON-OTC"
]

# ================== 5. ANTI-BLOCK HELPERS ==================
def safe_sleep(min_sec=0.4, max_sec=1.2):
    time.sleep(random.uniform(min_sec, max_sec))

def ensure_connection():
    if not API.check_connect():
        print("⚠️ Connection lost — reconnecting slowly...")
        time.sleep(15)
        API.connect()
        time.sleep(5)
        API.change_balance("PRACTICE")

# ================== 6. GET CANDLES ==================
def get_candles(asset, minutes=60):
    try:
        ensure_connection()
        safe_sleep(0.5, 1.5)

        _, candles = API.get_candles(asset, 60, minutes, time.time())
        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)
        df["open"] = df["open"].astype(float)
        return df

    except Exception as e:
        print(f"❌ Candle error: {asset} - {e}")
        time.sleep(10)
        return None

# ================== 7. GENERATE CHART ==================
def save_chart(df, asset):
    plt.figure(figsize=(8,4))
    plt.plot(df["close"].values, label="Price")
    plt.plot(df["close"].rolling(21).mean().values, label="MA21")
    plt.title(f"{asset} - 1M Chart (Last 60 candles)")
    plt.legend()

    path = f"/tmp/{asset}_chart.png"
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    return path

# ================== 8. STRATEGY (UNCHANGED) ==================
def analyze_asset(asset):
    df = get_candles(asset, 60)
    if df is None or len(df) < 21:
        return None, None

    df["MA21"] = df["close"].rolling(21).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # CALL
    if (last["close"] > last["MA21"] and
        last["close"] > last["open"] and
        prev["close"] < prev["open"]):
        chart_path = save_chart(df, asset)
        return "CALL", chart_path

    # PUT
    if (last["close"] < last["MA21"] and
        last["close"] < last["open"] and
        prev["close"] > prev["open"]):
        chart_path = save_chart(df, asset)
        return "PUT", chart_path

    return None, None

# ================== 9. ENGINE ==================
def run_engine():
    print("🚀 Quotex Sniper Engine Started (IST) — ANTI-BLOCK MODE")

    while True:
        now = datetime.now(IST)

        trade_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        send_time = trade_time - timedelta(seconds=40)

        while datetime.now(IST) < send_time:
            time.sleep(0.5)

        random.shuffle(ALL_PAIRS)

        for asset in ALL_PAIRS:
            signal, chart = analyze_asset(asset)

            if signal:
                t_str = trade_time.strftime("%H:%M")
                emoji = "🟢 CALL" if signal == "CALL" else "🔴 PUT"
                sticker = STICKER_CALL if signal == "CALL" else STICKER_PUT

                msg = (
f"🔥 **QUOTEX SNIPER SIGNAL** 🔥\n"
f"━━━━━━━━━━━━━━━━━━\n"
f"📊 **ASSET** ➪ {asset}\n"
f"⏰ **ENTRY (IST)** ➪ {t_str}:00\n"
f"📈 **DIRECTION** ➪ **{emoji}**\n"
f"🔁 **MTG** ➪ Use 1 Step if needed\n"
f"⏳ **ADVANCE NOTICE** ➪ 40 seconds\n"
f"━━━━━━━━━━━━━━━━━━\n"
f"🚀 *Be Ready Before Candle Opens!*"
                )

                for cid in ADMIN_IDS:
                    try:
                        bot.send_sticker(cid, sticker)
                        bot.send_photo(cid, open(chart, "rb"))
                        bot.send_message(cid, msg)
                    except Exception as e:
                        print(f"Telegram error: {e}")

                print(f"⏳ Waiting for result: {asset}")
                time.sleep(65)

                df_after = get_candles(asset, 1)
                if df_after is None:
                    result_msg = f"⚠️ **{asset} RESULT: UNKNOWN (data issue)**"
                else:
                    last_candle = df_after.iloc[-1]
                    if (signal == "CALL" and last_candle["close"] > last_candle["open"]) or \
                       (signal == "PUT" and last_candle["close"] < last_candle["open"]):
                        result_msg = f"🎯 **{asset} RESULT: WIN ✅**"
                    else:
                        result_msg = f"❌ **{asset} RESULT: LOSS**"

                for cid in ADMIN_IDS:
                    bot.send_message(cid, result_msg)

                print("🛑 Cooling before next trade...")
                time.sleep(300)
                break

        time.sleep(5)

# ================== 10. RUN BOT ==================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=lambda: bot.polling(none_stop=True)).start()
    run_engine()

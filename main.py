import os
import time
import pytz
import random
import numpy as np
import pandas as pd
import telebot
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ================== QUOTEX API ==================
from quotexapi.stable_api import Quotex  # Vendored locally

# ================== FLASK KEEP-ALIVE ==================
app = Flask(__name__)
@app.route("/")
def home():
    return "Quotex Sniper Bot: LIVE + OTC | MA21 + Price Action | SAFE MODE"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ================== TELEGRAM ==================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_IDS = os.environ.get("ADMIN_IDS", "7928496446").split(",")

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

STICKER_UP  = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN= "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

IST = pytz.timezone("Asia/Kolkata")

# ================== QUOTEX LOGIN ==================
EMAIL = os.environ.get("QUOTEX_EMAIL")
PASSWORD = os.environ.get("QUOTEX_PASS")

API = Quotex(EMAIL, PASSWORD)
API.connect()
API.change_balance("PRACTICE")  # SAFE MODE

# ================== ASSETS ==================
ALL_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURJPY","GBPJPY","USDCHF",
    "EURGBP","AUDJPY","NZDUSD",
    "USDINR-OTC","USDBDT-OTC","USDPKR-OTC","USDIDR-OTC",
    "USDARS-OTC","USDBRL-OTC","USDTRY-OTC","USDEGP-OTC",
    "GOLD-OTC","SILVER-OTC",
    "EURNZD-OTC","AUDNZD-OTC","GBPUSD-OTC","EURUSD-OTC","USDJPY-OTC",
    "INTEL-OTC","FACEBOOK-OTC","MICROSOFT-OTC","GOOGLE-OTC","APPLE-OTC","AMAZON-OTC"
]

# ================== HELPERS ==================
def safe_sleep(min_sec=0.5, max_sec=1.2):
    time.sleep(random.uniform(min_sec, max_sec))

def ensure_connection():
    if not API.check_connect():
        print("⚠️ Reconnecting...")
        time.sleep(10)
        API.connect()
        time.sleep(5)
        API.change_balance("PRACTICE")

def get_candles(asset, minutes=60):
    try:
        ensure_connection()
        safe_sleep()
        _, candles = API.get_candles(asset, 60, minutes, time.time())
        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)
        df["open"] = df["open"].astype(float)
        return df
    except Exception as e:
        print(f"Candle error: {asset} - {e}")
        return None

# ================== STRATEGY ==================
def analyze_asset(asset):
    df = get_candles(asset, 60)
    if df is None or len(df) < 21:
        return None

    df["MA21"] = df["close"].rolling(21).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last["close"] > last["MA21"] and last["close"] > last["open"] and prev["close"] < prev["open"]:
        return "CALL"
    if last["close"] < last["MA21"] and last["close"] < last["open"] and prev["close"] > prev["open"]:
        return "PUT"
    return None

# ================== ENGINE ==================
def run_engine():
    print("🚀 Engine started (IST)")
    while True:
        now = datetime.now(IST)
        trade_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        send_time = trade_time - timedelta(seconds=40)

        while datetime.now(IST) < send_time:
            time.sleep(0.5)

        random.shuffle(ALL_PAIRS)

        for asset in ALL_PAIRS:
            signal = analyze_asset(asset)
            if signal:
                t_str = trade_time.strftime("%H:%M")
                sticker = STICKER_UP if signal=="CALL" else STICKER_DOWN
                msg = (
f"🔥 **QUOTEX SNIPER SIGNAL** 🔥\n"
f"📊 **ASSET** ➪ {asset}\n"
f"⏰ **ENTRY (IST)** ➪ {t_str}:00\n"
f"📈 **DIRECTION** ➪ **{signal}**\n"
f"🔁 MTG: Use 1 Step if needed"
                )

                for cid in ADMIN_IDS:
                    bot.send_sticker(cid, sticker)
                    bot.send_message(cid, msg)

                # Wait for candle to close before checking result
                time.sleep(65)
                df_after = get_candles(asset, 1)
                if df_after is None:
                    result_msg = f"⚠️ **{asset} RESULT: UNKNOWN**"
                else:
                    last_candle = df_after.iloc[-1]
                    if (signal=="CALL" and last_candle["close"]>last_candle["open"]) or \
                       (signal=="PUT" and last_candle["close"]<last_candle["open"]):
                        result_msg = f"🎯 **{asset} RESULT: WIN ✅**"
                        sticker_result = STICKER_ITM
                    else:
                        result_msg = f"❌ **{asset} RESULT: LOSS**"
                        sticker_result = STICKER_OTM

                    for cid in ADMIN_IDS:
                        bot.send_sticker(cid, sticker_result)
                        bot.send_message(cid, result_msg)

                print(f"Trade done: {asset} - {signal}")
                time.sleep(300)  # 5 min cooldown
                break

        time.sleep(5)

# ================== RUN BOT ==================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=lambda: bot.polling(none_stop=True)).start()
    run_engine()

import os
import time
import pytz
import random
import numpy as np
import pandas as pd
import telebot
import matplotlib.pyplot as plt
import requests
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from quotexapi.stable_api import Quotex

# ================== 1. RENDER KEEP-ALIVE SERVER ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "Quotex Sniper Bot: SAFE + RSI + MTF + S/R + News + Dashboard + MTG"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ================== 2. TELEGRAM CONFIG ==================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN not set in Render!")
    exit()

ADMIN_IDS = ["7928496446", "8519882401"]
bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

STICKER_CALL = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_PUT  = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"

IST = pytz.timezone("Asia/Kolkata")

# ================== 3. QUOTEX LOGIN (SAFE MODE) ==================
EMAIL = os.environ.get("QUOTEX_EMAIL")
PASSWORD = os.environ.get("QUOTEX_PASS")

if not EMAIL or not PASSWORD:
    print("❌ ERROR: QUOTEX_EMAIL or QUOTEX_PASS not set in Render!")
    exit()

print("🔐 Connecting to Quotex...")

API = Quotex(EMAIL, PASSWORD)
API.connect()

if not API.check_connect():
    print("❌ Login Failed! Check credentials.")
    exit()

API.change_balance("PRACTICE")

# ================== 4. ASSET LIST ==================
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
def safe_sleep(min_sec=0.5, max_sec=1.5):
    time.sleep(random.uniform(min_sec, max_sec))

def ensure_connection():
    if not API.check_connect():
        print("⚠️ Reconnecting to Quotex...")
        time.sleep(15)
        API.connect()
        time.sleep(5)
        API.change_balance("PRACTICE")

# ================== 6. GET REAL CANDLES ==================
def get_candles(asset, minutes=60, interval_sec=60):
    try:
        ensure_connection()
        safe_sleep(0.5, 1.5)

        candles = API.get_candles(asset, interval_sec, minutes, time.time())
        df = pd.DataFrame(candles)

        df["close"] = df["close"].astype(float)
        df["open"] = df["open"].astype(float)
        return df

    except Exception as e:
        print(f"❌ Candle error: {asset} - {e}")
        time.sleep(10)
        return None

# ================== 7. SAVE CHART ==================
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

# ================== 8. FILTERS ==================
def time_filter_ok():
    hour = datetime.now(IST).hour
    return (9 <= hour <= 12) or (14 <= hour <= 17)

def volatility_filter(df):
    last10 = df["close"].tail(10)
    return (last10.max() - last10.min()) / last10.mean() > 0.0006

def trend_filter(df):
    last5 = df["close"].tail(5).values
    up = all(last5[i] > last5[i-1] for i in range(1,5))
    down = all(last5[i] < last5[i-1] for i in range(1,5))
    return up, down

def rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def find_sr(df, lookback=40, tol=0.0003):
    closes = df["close"].tail(lookback).values
    support = np.percentile(closes, 20)
    resistance = np.percentile(closes, 80)
    return support, resistance

def near_level(price, level, tol=0.0003):
    return abs(price - level) <= (level * tol)

def multi_tf_check(asset):
    df_m1 = get_candles(asset, 60, 60)
    df_m5 = get_candles(asset, 60, 300)

    if df_m1 is None or df_m5 is None:
        return False

    m1_last = df_m1["close"].iloc[-1] - df_m1["open"].iloc[-1]
    m5_last = df_m5["close"].iloc[-1] - df_m5["open"].iloc[-1]

    return (m1_last * m5_last > 0)

def news_time_pause():
    try:
        res = requests.get("https://www.forexfactory.com/calendar?day=today")
        if res.status_code == 200 and "High Impact" in res.text:
            return True
        return False
    except:
        return False

# ================== 9. ANALYZE ASSET ==================
dashboard = {"last_signal":"","last_result":"","total_trades":0,"wins":0}

def analyze_asset(asset):
    if news_time_pause():
        return None, None

    df = get_candles(asset, 60)
    if df is None or len(df) < 21:
        return None, None

    if not time_filter_ok():
        return None, None

    if not volatility_filter(df):
        return None, None

    up, down = trend_filter(df)
    support, resistance = find_sr(df)

    df["MA21"] = df["close"].rolling(21).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_val = rsi(df).iloc[-1]

    if not multi_tf_check(asset):
        return None, None

    # CALL setup
    if (last["close"] > last["MA21"] and
        last["close"] > last["open"] and
        prev["close"] < prev["open"] and
        up and
        near_level(last["close"], support) and
        rsi_val < 70):

        chart_path = save_chart(df, asset)
        return "CALL", chart_path

    # PUT setup
    if (last["close"] < last["MA21"] and
        last["close"] < last["open"] and
        prev["close"] > prev["open"] and
        down and
        near_level(last["close"], resistance) and
        rsi_val > 30):

        chart_path = save_chart(df, asset)
        return "PUT", chart_path

    return None, None

# ================== 10. ENGINE ==================
def run_engine():
    print("🚀 FULL SAFE QUOTEX ENGINE STARTED")

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
f"⏳ **ADVANCE NOTICE** ➪ 40 sec\n"
f"🔁 **MTG:** Use 1 Step if needed\n"
f"━━━━━━━━━━━━━━━━━━"
                )

                for cid in ADMIN_IDS:
                    try:
                        bot.send_sticker(cid, sticker)
                        bot.send_photo(cid, open(chart, "rb"))
                        bot.send_message(cid, msg)
                    except Exception as e:
                        print(f"Telegram error: {e}")

                dashboard["last_signal"] = f"{asset} {signal} at {t_str}"
                dashboard["total_trades"] += 1

                print(f"⏳ Waiting for result: {asset}")
                time.sleep(65)

                df_after = get_candles(asset, 1)

                if df_after is None:
                    result_msg = f"⚠️ {asset} RESULT: UNKNOWN"
                else:
                    last_candle = df_after.iloc[-1]
                    if (signal == "CALL" and last_candle["close"] > last_candle["open"]) or \
                       (signal == "PUT" and last_candle["close"] < last_candle["open"]):
                        result_msg = f"🎯 {asset} RESULT: WIN ✅"
                        dashboard["wins"] += 1
                    else:
                        result_msg = f"❌ {asset} RESULT: LOSS"

                dashboard["last_result"] = result_msg
                accuracy = int((dashboard["wins"] / dashboard["total_trades"]) * 100)

                dash_msg = (
f"📊 **BOT DASHBOARD**\n"
f"Total Trades: {dashboard['total_trades']}\n"
f"Wins: {dashboard['wins']}\n"
f"Accuracy: {accuracy}%\n"
f"Last Signal: {dashboard['last_signal']}\n"
f"Last Result: {dashboard['last_result']}"
                )

                for cid in ADMIN_IDS:
                    bot.send_message(cid, result_msg)
                    bot.send_message(cid, dash_msg)

                print("🛑 Cooling 5 minutes before next trade...")
                time.sleep(300)
                break

        time.sleep(5)

# ================== 11. RUN ==================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=lambda: bot.polling(none_stop=True)).start()
    run_engine()

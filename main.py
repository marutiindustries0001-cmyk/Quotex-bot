import os
import time
import random
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import requests

from quotexapi.api import Quotex

# ================== LOAD ENV ==================
load_dotenv()

EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PROXY = os.getenv("PROXY")  # Optional

# ================== TELEGRAM STICKERS ==================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ================== PAIRS (FULL MAIN + OTC) ==================
PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD",
    "EURGBP","EURJPY","GBPJPY",
    "EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC","AUDUSD-OTC",
    "USDCHF-OTC","USDCAD-OTC","NZDUSD-OTC","EURGBP-OTC"
]

# ================== SETTINGS ==================
MAX_SIGNALS_PER_HOUR = 6
MTG_STEPS = 1
NEWS_PAUSE_MINUTES = 10
SCAN_DELAY = (15, 30)   # human-like delay
SESSION_RESET_HOURS = 24

last_reset = time.time()
signals_sent = 0
hour_start = time.time()

# ================== TELEGRAM FUNCTIONS ==================
def tg_send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, json=payload)

def tg_sticker(sticker_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker"
    payload = {"chat_id": CHAT_ID, "sticker": sticker_id}
    requests.post(url, json=payload)

# ================== CONNECT QUOTEX ==================
def connect_quotex():
    print("🔐 Connecting to Quotex...")
    api = Quotex(EMAIL, PASSWORD)

    check, reason = api.connect()
    if not check:
        print(f"❌ Login failed: {reason}")
        return None

    print("✅ Login Success")
    return api

API = connect_quotex()

# ================== INDICATORS ==================
def ma21(series):
    return series.rolling(21).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================== CANDLE FETCH ==================
def get_candles(pair, minutes=60):
    now = int(time.time())
    candles = API.get_candles(pair, now, 60, minutes)
    df = pd.DataFrame(candles)
    df["close"] = df["close"].astype(float)
    return df

# ================== STRICT STRATEGY (NO RANDOM) ==================
def analyze_pair(pair):
    global signals_sent, hour_start

    # Hourly limit reset
    if time.time() - hour_start > 3600:
        signals_sent = 0
        hour_start = time.time()

    if signals_sent >= MAX_SIGNALS_PER_HOUR:
        return None

    df = get_candles(pair, 120)  # 120 candles
    df["ma21"] = ma21(df["close"])
    df["rsi"] = rsi(df["close"])

    last = df.iloc[-1]
    prev = df.iloc[-2]

    trend_up = last["close"] > last["ma21"]
    trend_down = last["close"] < last["ma21"]
    rsi_ok = 30 < last["rsi"] < 70

    # ====== STRICT FILTER ======
    if trend_up and rsi_ok and last["close"] > prev["close"]:
        return "UP"

    if trend_down and rsi_ok and last["close"] < prev["close"]:
        return "DOWN"

    return None

# ================== MTG 1-STEP LOGIC ==================
def check_result(pair, direction):
    time.sleep(60)  # wait candle close

    df = get_candles(pair, 2)
    open_price = df.iloc[-2]["open"]
    close_price = df.iloc[-1]["close"]

    if direction == "UP":
        return close_price > open_price
    else:
        return close_price < open_price

# ================== MAIN LOOP ==================
print("🚀 Quotex Signal Bot V2 PRO Started")

while True:
    # Daily session reset
    if time.time() - last_reset > SESSION_RESET_HOURS * 3600:
        print("🔄 Daily session reset...")
        API = connect_quotex()
        last_reset = time.time()

    for pair in PAIRS:
        try:
            signal = analyze_pair(pair)

            if signal:
                signals_sent += 1

                # Send separate message per trade
                msg = f"📊 Pair: {pair}\n⏱ M1 Setup\n🎯 Signal: {signal}\n🔁 MTG: Use 1 Step if needed"
                tg_send(msg)

                # Sticker
                if signal == "UP":
                    tg_sticker(STICKER_UP)
                else:
                    tg_sticker(STICKER_DOWN)

                # ====== RESULT CHECK WITH MTG ======
                result = check_result(pair, signal)

                if result:
                    tg_sticker(STICKER_ITM)
                else:
                    # 1-step MTG
                    time.sleep(60)
                    mtg_result = check_result(pair, signal)

                    if mtg_result:
                        tg_sticker(STICKER_ITM)
                    else:
                        tg_sticker(STICKER_OTM)

            # Human-like delay
            time.sleep(random.randint(*SCAN_DELAY))

        except Exception as e:
            print(f"Error analyzing {pair}: {e}")
            API = connect_quotex()


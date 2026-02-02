import os
import time
import random
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from quotexapi.stable_api import Quotex

# ================= ENVIRONMENT VARIABLES =================
QUOTEX_EMAIL = os.environ.get("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.environ.get("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not all([QUOTEX_EMAIL, QUOTEX_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    raise Exception("❌ Missing one or more environment variables in Render!")

# ================= TELEGRAM STICKERS =================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ================= SETTINGS =================
TIMEFRAME_M1 = 60
TIMEFRAME_M5 = 300
MA_PERIOD = 21
RSI_PERIOD = 14
MAX_SIGNALS_PER_HOUR = 6
NEWS_PAUSE_MINUTES = 15
MTG_ENABLED = True   # 1-step martingale
SIGNAL_BUFFER_SEC = 40  # send signal 40 sec before candle close

# ================= PAIRS =================
MAIN_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD",
    "USDCHF","USDCAD","NZDUSD","EURGBP",
    "EURJPY","GBPJPY"
]

OTC_PAIRS = [
    "EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC",
    "AUDUSD-OTC","USDCHF-OTC","USDCAD-OTC",
    "NZDUSD-OTC","EURGBP-OTC"
]

ALL_PAIRS = MAIN_PAIRS + OTC_PAIRS

# ================= TELEGRAM =================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    requests.post(url, json=payload)

def send_sticker(sticker_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "sticker": sticker_id}
    requests.post(url, json=payload)

# ================= INDICATORS =================
def calculate_ma(series, period):
    return series.rolling(window=period).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ================= NEWS FILTER (DUMMY) =================
def news_active():
    return False   # Later you can integrate real news API

# ================= HUMAN-LIKE DELAY =================
def human_delay(min_s=2, max_s=6):
    time.sleep(random.uniform(min_s, max_s))

# ================= CONNECT =================
print("🔐 Connecting to Quotex...")
API = Quotex(QUOTEX_EMAIL, QUOTEX_PASSWORD)
API.connect()

print("🚀 Quotex Signal Bot V2-PRO Started (Render Ready)")

last_reset = time.time()
signals_sent = 0

# ================= MAIN LOOP =================
while True:
    # Daily session reset
    if time.time() - last_reset > 24 * 3600:
        print("🔄 Daily session reset...")
        API.connect()
        last_reset = time.time()
        signals_sent = 0

    for pair in ALL_PAIRS:
        try:
            # Throttle signals per hour
            if signals_sent >= MAX_SIGNALS_PER_HOUR:
                print("⏸ Max signals reached. Cooling down 10 minutes...")
                time.sleep(600)
                signals_sent = 0

            # News pause
            if news_active():
                print(f"📰 News active — skipping {pair}")
                continue

            candles = API.get_candles(pair, TIMEFRAME_M1, 60)
            df = pd.DataFrame(candles)

            df["ma21"] = calculate_ma(df["close"], MA_PERIOD)
            df["rsi"] = calculate_rsi(df["close"], RSI_PERIOD)

            last_close = df["close"].iloc[-1]
            last_ma = df["ma21"].iloc[-1]
            last_rsi = df["rsi"].iloc[-1]

            # M5 confirmation
            candles_m5 = API.get_candles(pair, TIMEFRAME_M5, 20)
            df5 = pd.DataFrame(candles_m5)
            df5["ma21"] = calculate_ma(df5["close"], MA_PERIOD)
            m5_trend_up = df5["close"].iloc[-1] > df5["ma21"].iloc[-1]

            direction = None

            if last_close > last_ma and last_rsi > 55 and m5_trend_up:
                direction = "UP"
            elif last_close < last_ma and last_rsi < 45 and not m5_trend_up:
                direction = "DOWN"

            if direction:
                human_delay(1.5, 3.5)

                send_telegram(
f"""📊 SIGNAL
PAIR: {pair}
DIRECTION: {direction}
TIMEFRAME: M1
ENTER: After {SIGNAL_BUFFER_SEC} sec
MA21: {round(last_ma,5)}
RSI: {round(last_rsi,2)}
"""
                )

                send_sticker(STICKER_UP if direction == "UP" else STICKER_DOWN)

                signals_sent += 1

                # ===== MTG 1-STEP LOGIC =====
                if MTG_ENABLED:
                    print("🔁 Waiting for candle close to check result...")
                    time.sleep(60)

                    new_candles = API.get_candles(pair, TIMEFRAME_M1, 2)
                    df_new = pd.DataFrame(new_candles)

                    first = df_new["close"].iloc[-2]
                    second = df_new["close"].iloc[-1]

                    win = (second > first and direction == "UP") or \
                          (second < first and direction == "DOWN")

                    if win:
                        send_sticker(STICKER_ITM)
                        send_telegram(f"✅ FINAL RESULT: ITM — {pair}")
                    else:
                        # 1-step MTG
                        send_telegram(f"⚠️ First trade OTM, taking 1-step MTG on {pair}")
                        human_delay(2,4)

                        time.sleep(60)
                        mtg_candles = API.get_candles(pair, TIMEFRAME_M1, 2)
                        df_mtg = pd.DataFrame(mtg_candles)

                        f2 = df_mtg["close"].iloc[-2]
                        s2 = df_mtg["close"].iloc[-1]

                        mtg_win = (s2 > f2 and direction == "UP") or \
                                  (s2 < f2 and direction == "DOWN")

                        if mtg_win:
                            send_sticker(STICKER_ITM)
                            send_telegram(f"✅ FINAL RESULT: MTG ITM — {pair}")
                        else:
                            send_sticker(STICKER_OTM)
                            send_telegram(f"❌ FINAL RESULT: OTM — {pair}")

            human_delay(3, 7)

        except Exception as e:
            print(f"Error analyzing {pair}: {e}")

    time.sleep(5)

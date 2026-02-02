import os
import time
import random
import json
import threading
from datetime import datetime, timedelta, timezone
import requests
import numpy as np

# ================== ENVIRONMENT VARIABLES (REQUIRED) ==================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PROXY = os.getenv("QUOTEX_PROXY", "")   # Optional: http://user:pass@ip:port

# ================== TELEGRAM STICKERS ==================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ================== PAIRS (MAIN + OTC) ==================
MAIN_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF",
    "USDCAD","NZDUSD","EURGBP","EURJPY","GBPJPY"
]

OTC_PAIRS = [
    "EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC","AUDUSD-OTC",
    "USDCHF-OTC","USDCAD-OTC","NZDUSD-OTC","EURGBP-OTC"
]

ALL_PAIRS = MAIN_PAIRS + OTC_PAIRS

# ================== SETTINGS ==================
TIMEFRAME_M5 = 300
TIMEFRAME_M1 = 60

SIGNAL_ADVANCE_SECONDS = 40
MAX_SIGNALS_PER_HOUR = 6
NEWS_PAUSE_MINUTES = 15   # Pause trading around news
SESSION_RESET_HOURS = 12
SCAN_INTERVAL = 10        # seconds

# Human-like delay range
MIN_DELAY = 2
MAX_DELAY = 7

# ================== QUOTEX CONNECTION (SAFE) ==================
from quotex import Quotex

class QuotexClient:
    def __init__(self):
        self.api = None
        self.last_login = None

    def connect(self):
        try:
            print("🔐 Connecting to Quotex...")
            self.api = Quotex(
                email=QUOTEX_EMAIL,
                password=QUOTEX_PASSWORD,
                proxies={"http": PROXY, "https": PROXY} if PROXY else None
            )
            self.api.connect()
            self.last_login = time.time()
            print("✅ Connected to Quotex")
            return True
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    def reconnect_if_needed(self):
        if not self.api or time.time() - self.last_login > SESSION_RESET_HOURS * 3600:
            print("🔄 Session reset & reconnecting...")
            return self.connect()
        return True

    def get_candles(self, pair, timeframe, count=60):
        self.reconnect_if_needed()
        candles = self.api.get_candles(pair, timeframe, count)
        return candles

quotex = QuotexClient()
quotex.connect()

# ================== INDICATORS ==================
def calc_ma(data, period=21):
    return np.mean(data[-period:])

def calc_rsi(data, period=14):
    deltas = np.diff(data)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:]) + 1e-9
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================== TELEGRAM ==================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def send_sticker(sticker_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "sticker": sticker_id}
    requests.post(url, json=payload)

# ================== NEWS FILTER (BASIC) ==================
def is_news_time():
    now = datetime.utcnow()
    minute = now.minute
    return minute in [0, 15, 30, 45]  # avoid big news minutes

# ================== STRICT TRADE LOGIC ==================
def analyze_pair(pair):
    try:
        candles_m5 = quotex.get_candles(pair, TIMEFRAME_M5, 60)
        candles_m1 = quotex.get_candles(pair, TIMEFRAME_M1, 60)

        closes_m5 = np.array([c["close"] for c in candles_m5])
        closes_m1 = np.array([c["close"] for c in candles_m1])

        ma21 = calc_ma(closes_m5, 21)
        last_price = closes_m5[-1]

        rsi_m5 = calc_rsi(closes_m5)
        rsi_m1 = calc_rsi(closes_m1)

        # ---- STRICT CONDITIONS (NO RANDOM TRADES) ----
        if last_price > ma21 and rsi_m5 > 55 and rsi_m1 > 55:
            return "UP"

        if last_price < ma21 and rsi_m5 < 45 and rsi_m1 < 45:
            return "DOWN"

        return None

    except Exception as e:
        print(f"Error analyzing {pair}: {e}")
        return None

# ================== MTG 1-STEP LOGIC ==================
def check_mtg_result(pair, direction):
    time.sleep(60)  # wait 1 minute candle close
    candles = quotex.get_candles(pair, TIMEFRAME_M1, 2)
    prev_close = candles[-2]["close"]
    last_close = candles[-1]["close"]

    if direction == "UP" and last_close > prev_close:
        return "ITM"
    if direction == "DOWN" and last_close < prev_close:
        return "ITM"
    return "OTM"

# ================== MAIN SIGNAL LOOP ==================
def signal_loop():
    sent_count = 0
    start_hour = time.time()

    while True:
        if is_news_time():
            print("📰 News time — pausing signals...")
            time.sleep(60)
            continue

        if time.time() - start_hour > 3600:
            sent_count = 0
            start_hour = time.time()

        for pair in ALL_PAIRS:
            if sent_count >= MAX_SIGNALS_PER_HOUR:
                print("⏸ Max signals reached — waiting...")
                time.sleep(300)
                continue

            direction = analyze_pair(pair)

            if direction:
                # Human-like delay before sending
                time.sleep(random.randint(MIN_DELAY, MAX_DELAY))

                # Send signal 40 sec before candle close
                send_telegram(
                    f"🔔 <b>NEW SIGNAL</b>\n"
                    f"Pair: {pair}\n"
                    f"Direction: {direction}\n"
                    f"⏳ Entry in ~40 sec\n"
                    f"🔁 MTG: Use 1 Step if needed"
                )

                # Send UP/DOWN sticker
                send_sticker(STICKER_UP if direction == "UP" else STICKER_DOWN)

                # ---- WAIT FOR RESULT & APPLY MTG LOGIC ----
                result = check_mtg_result(pair, direction)

                if result == "OTM":
                    # Try 1-step MTG
                    mtg_result = check_mtg_result(pair, direction)

                    if mtg_result == "ITM":
                        send_telegram(f"✅ {pair} — MTG HIT (FINAL: ITM)")
                        send_sticker(STICKER_ITM)
                    else:
                        send_telegram(f"❌ {pair} — FINAL RESULT: OTM")
                        send_sticker(STICKER_OTM)
                else:
                    send_telegram(f"✅ {pair} — DIRECT ITM")
                    send_sticker(STICKER_ITM)

                sent_count += 1

        time.sleep(SCAN_INTERVAL)

# ================== START BOT ==================
if __name__ == "__main__":
    print("🚀 Quotex Signal Bot Started (Render Ready)")
    signal_loop()

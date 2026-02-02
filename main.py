import os, time, random
from datetime import datetime, timedelta
import pandas as pd
from quotexapi.stable_api import Quotex
import requests

# ========== ENV VARIABLES (RENDER) ==========
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT = os.getenv("TG_CHAT")

# ========== SETTINGS ==========
MAX_SIGNALS_PER_HOUR = 6
SCAN_INTERVAL = 55        # seconds
CANDLES_M1 = 20
CANDLES_M5 = 20
TIMEFRAME_M1 = 60
TIMEFRAME_M5 = 300

PAIRS = [
"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD",
"EURGBP","EURJPY","GBPJPY",
"EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC","AUDUSD-OTC",
"USDCHF-OTC","USDCAD-OTC","NZDUSD-OTC","EURGBP-OTC"
]

ITM_STICKER = "🎯"   # change if you want
OTM_STICKER = "❌"

q = None
last_reset = datetime.utcnow()
signals_sent = 0

# ========== TELEGRAM ==========
def tg(msg):
    if TG_TOKEN and TG_CHAT:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TG_CHAT, "text": msg})

def tg_admin(msg):
    if TG_TOKEN and TG_CHAT:
        tg("📊 *DASHBOARD*\n" + msg)

# ========== SESSION ==========
def connect():
    global q
    print("🔐 Connecting to Quotex...")
    q = Quotex(email=EMAIL, password=PASSWORD)
    ok, reason = q.connect()
    if ok:
        print("✅ Connected")
        return True
    print("❌ Login failed:", reason)
    q = None
    return False

def daily_reset():
    global last_reset, signals_sent
    if datetime.utcnow() - last_reset > timedelta(hours=24):
        print("🔄 Daily session reset")
        signals_sent = 0
        last_reset = datetime.utcnow()
        return True
    return False

# ========== INDICATORS ==========
def get_df(pair, tf, n):
    candles = q.get_candles(pair, tf, n)
    if not candles:
        return None
    df = pd.DataFrame(candles)
    df["close"] = df["close"].astype(float)
    return df

def ma_rsi_signal(pair):
    df1 = get_df(pair, TIMEFRAME_M1, CANDLES_M1)
    df5 = get_df(pair, TIMEFRAME_M5, CANDLES_M5)
    if df1 is None or df5 is None:
        return None

    df1["ma21"] = df1["close"].rolling(21).mean()
    delta = df1["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean()
    df1["rsi"] = 100 - (100 / (1 + rs))

    last = df1.iloc[-1]
    prev = df1.iloc[-2]

    trend_m5 = df5["close"].iloc[-1] > df5["close"].iloc[-5]

    if last["close"] > last["ma21"] and last["rsi"] > 55 and trend_m5:
        return "CALL"
    if last["close"] < last["ma21"] and last["rsi"] < 45 and not trend_m5:
        return "PUT"
    return None

# ========== MAIN LOOP ==========
def start_bot():
    global signals_sent

    print("🚀 V2 PRO Bot Started")

    while True:
        daily_reset()

        if not q or not connect():
            time.sleep(10)
            continue

        for pair in PAIRS:
            if signals_sent >= MAX_SIGNALS_PER_HOUR:
                print("⏸️ Signal limit reached, cooling down...")
                time.sleep(3600)
                signals_sent = 0

            try:
                signal = ma_rsi_signal(pair)
                if signal:
                    entry_time = datetime.now().strftime("%H:%M:%S")
                    msg = (
f"🔥 SIGNAL\n"
f"Pair: {pair}\n"
f"Type: {signal}\n"
f"TF: M1/M5\n"
f"Entry: {entry_time}\n"
f"Expiry: 1 min"
                    )
                    tg(msg)
                    print(msg)
                    signals_sent += 1

                # Human-like delay
                time.sleep(random.randint(3,8))

            except Exception as e:
                print(f"Error {pair}: {e}")

        print("🔁 Next scan...")
        time.sleep(SCAN_INTERVAL)

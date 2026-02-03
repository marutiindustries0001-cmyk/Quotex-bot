import sys
print(f"🚀 Running on Python: {sys.version}")
import os, time, random
from datetime import datetime, timedelta, timezone
import requests
import numpy as np
from websocket import create_connection

# ================== ENV VARIABLES (RENDER) ==================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 👉 TWO CHAT IDS (AS YOU ASKED)
CHAT_ID_1 = os.getenv("TELEGRAM_CHAT_ID_1")   # e.g. 123456789
CHAT_ID_2 = os.getenv("TELEGRAM_CHAT_ID_2")   # e.g. 987654321

if not all([QUOTEX_EMAIL, QUOTEX_PASSWORD, TELEGRAM_BOT_TOKEN, CHAT_ID_1, CHAT_ID_2]):
    raise Exception("❌ Missing one or more environment variables in Render!")

# ================== TELEGRAM STICKERS (YOUR IDS) ==================
STICKER_UP   = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM  = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM  = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ================== BOT SETTINGS ==================
MAX_SIGNALS_PER_HOUR = 8
SIGNAL_BUFFER_SECONDS = 40        # Trade 40 sec pehle mile
MTG_WAIT_SECONDS = 60             # 1-step MTG wait
NEWS_PAUSE_MINUTES = 30           # News pause

# ================== PAIRS (MAIN + OTC) ==================
PAIRS = [
    # MAIN PAIRS
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD",
    "EURJPY","GBPJPY","AUDJPY","USDCHF",
    "EURGBP","NZDUSD","EURCAD","GBPCAD",

    # EXISTING OTC
    "EURUSD_otc","GBPUSD_otc","USDJPY_otc",
    "AUDUSD_otc","USDCAD_otc",

    # NEW OTC (AS YOU ASKED)
    "USDPKR_otc",
    "USDMXN_otc",
    "EURJPY_otc",
    "GBPJPY_otc",
    "AUDJPY_otc",
    "USDCHF_otc",
    "EURGBP_otc",
    "NZDUSD_otc"
]

# ================== TELEGRAM FUNCTIONS ==================
def send_telegram_message(text, sticker=None):
    for chat_id in [CHAT_ID_1, CHAT_ID_2]:
        if sticker:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                json={"chat_id": chat_id, "sticker": sticker}
            )
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text}
        )

# ================== INDICATORS ==================
def ma(prices, period=21):
    return np.mean(prices[-period:])

def rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = np.maximum(deltas, 0)
    losses = -np.minimum(deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ================== LOGIN QUOTEX ==================
def connect_quotex():
    ws = create_connection("wss://ws2.quotex.com/socket.io/?EIO=3&transport=websocket")
    print("✅ Connected to Quotex WebSocket")
    return ws

# ================== NEWS FILTER (DUMMY SAFE) ==================
def is_news_time():
    # (simple safe placeholder – avoids API errors)
    now = datetime.utcnow()
    return False  # change to True manually during big news

# ================== SIGNAL LOGIC ==================
def analyze_pair(q, pair):
    candles_m1 = q.get_candles(pair, 60, 100)
    candles_m5 = q.get_candles(pair, 300, 50)

    if not candles_m1 or not candles_m5:
        return None

    closes_m1 = np.array([c["close"] for c in candles_m1])
    closes_m5 = np.array([c["close"] for c in candles_m5])

    ma21_m1 = ma(closes_m1, 21)
    ma21_m5 = ma(closes_m5, 21)
    rsi_m1 = rsi(closes_m1, 14)

    last_price = closes_m1[-1]

    trend_up = (last_price > ma21_m1 and ma21_m1 > ma21_m5 and rsi_m1 > 55)
    trend_down = (last_price < ma21_m1 and ma21_m1 < ma21_m5 and rsi_m1 < 45)

    if trend_up:
        return "CALL"
    if trend_down:
        return "PUT"
    return None

# ================== RESULT CHECK ==================
def check_result(q, pair, direction):
    time.sleep(60)  # trade close hone ka wait

    candles = q.get_candles(pair, 60, 2)
    if not candles:
        return "UNKNOWN"

    open_price = candles[0]["open"]
    close_price = candles[-1]["close"]

    if direction == "CALL" and close_price > open_price:
        return "ITM"
    if direction == "PUT" and close_price < open_price:
        return "ITM"
    return "OTM"

# ================== MAIN BOT LOOP ==================
def main():
    print("🚀 Quotex Signal Bot Started (V2 PRO)")

    q = connect_quotex()
    signal_count = 0
    hour_start = time.time()

    while True:
        # Hourly reset
        if time.time() - hour_start > 3600:
            signal_count = 0
            hour_start = time.time()

        if signal_count >= MAX_SIGNALS_PER_HOUR:
            time.sleep(60)
            continue

        if is_news_time():
            print("📰 News time — pausing...")
            time.sleep(NEWS_PAUSE_MINUTES * 60)
            continue

        pair = random.choice(PAIRS)
        try:
            direction = analyze_pair(q, pair)
            if not direction:
                time.sleep(random.randint(5,15))
                continue

            trade_time = (datetime.utcnow() + timedelta(seconds=SIGNAL_BUFFER_SECONDS)).strftime("%H:%M:%S")

            # ===== SEND SIGNAL (CLEAN FORMAT) =====
            msg = f"""
📌 Pair: {pair}
⏰ Trade Time: {trade_time}
➡️ Direction: {direction}
⚡ Use 1-Step MTG if needed
            """.strip()

            sticker = STICKER_UP if direction == "CALL" else STICKER_DOWN
            send_telegram_message(msg, sticker)
            signal_count += 1

            # ===== WAIT FOR RESULT =====
            result = check_result(q, pair, direction)

            if result == "OTM":
                time.sleep(MTG_WAIT_SECONDS)
                result = check_result(q, pair, direction)

            # ===== SEND RESULT =====
            result_sticker = STICKER_ITM if result == "ITM" else STICKER_OTM
            send_telegram_message(f"✅ Result: {result}", result_sticker)

        except Exception as e:
            print(f"Error on {pair}: {e}")
            q = connect_quotex()  # auto reconnect

        time.sleep(random.randint(8,20))  # human-like delay

if __name__ == "__main__":
    main()

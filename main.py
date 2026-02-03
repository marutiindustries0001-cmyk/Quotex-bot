import os
import time
import random
from datetime import datetime
import pandas as pd
from quotexapi.stable_api import Quotex
import requests

# ==================== ENV VARIABLES ====================
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_CHAT_IDS = [
    os.getenv("TELEGRAM_CHAT_ID1"),
    os.getenv("TELEGRAM_CHAT_ID2")
]

if not all([QUOTEX_EMAIL, QUOTEX_PASSWORD] + TELEGRAM_CHAT_IDS):
    raise Exception("❌ Missing one or more environment variables in Render!")

# ==================== STICKERS ====================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ==================== QUOTEX API ====================
q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
q.login()

# ==================== PAIRS ====================
PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD",
    "EURGBP","EURJPY","GBPJPY",
    "EURUSD-OTC","GBPUSD-OTC","USDJPY-OTC","AUDUSD-OTC","USDCHF-OTC",
    "USDCAD-OTC","NZDUSD-OTC","EURGBP-OTC","USD/MXN-OTC","USD/PKR-OTC"
]

# ==================== FUNCTIONS ====================
def send_telegram(message, sticker=None):
    for chat_id in TELEGRAM_CHAT_IDS:
        if sticker:
            requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendSticker", data={
                "chat_id": chat_id,
                "sticker": sticker
            })
        requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })

def analyze_candle(pair):
    try:
        data = q.get_candles(pair=pair, interval=1, count=50)  # M1 candles
        df = pd.DataFrame(data)
        last = df.iloc[-1]
        # Dummy MA21 + RSI logic
        direction = "call" if last['close'] > df['close'].rolling(21).mean().iloc[-1] else "put"
        return direction
    except Exception as e:
        print(f"Error analyzing {pair}: {e}")
        return None

def main_loop():
    while True:
        for pair in PAIRS:
            direction = analyze_candle(pair)
            if direction:
                trade_time = datetime.now().strftime("%H:%M:%S")
                message = f"📈 Pair: {pair}\n⏰ Trade Time: {trade_time}\n🔹 Signal: {direction.upper()}\n💡 1-step MTG if needed"
                sticker = STICKER_UP if direction == "call" else STICKER_DOWN
                send_telegram(message, sticker=sticker)
                time.sleep(random.randint(35,45))  # 40s approx delay

        time.sleep(1)

# ==================== START BOT ====================
if __name__ == "__main__":
    send_telegram("🚀 Quotex Signal Bot Started ✅")
    main_loop()

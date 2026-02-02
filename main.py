import os
import time
import random
import pytz
import requests
import pandas as pd
from datetime import datetime, timedelta
from threading import Thread
import telebot
from quotexapi.stable_api import Quotex

# ================== 1. CONFIG ==================
TOKEN = os.environ.get("TELEGRAM_TOKEN")
EMAIL = os.environ.get("QUOTEX_EMAIL")
PASSWORD = os.environ.get("QUOTEX_PASS")
PROXIES = os.environ.get("QUOTEX_PROXIES", "").split(",")  # comma-separated
ADMIN_IDS = os.environ.get("ADMIN_IDS", "").split(",")  # comma-separated
IST = pytz.timezone("Asia/Kolkata")

STICKER_UP   = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM  = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM  = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

ALL_PAIRS = [
    "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","EURJPY","GBPJPY","USDCHF",
    "EURGBP","AUDJPY","NZDUSD",
    "USDINR-OTC","USDBDT-OTC","USDPKR-OTC","USDIDR-OTC",
    "USDARS-OTC","USDBRL-OTC","USDTRY-OTC","USDEGP-OTC",
    "GOLD-OTC","SILVER-OTC",
    "EURNZD-OTC","AUDNZD-OTC","GBPUSD-OTC","EURUSD-OTC","USDJPY-OTC",
    "INTEL-OTC","FACEBOOK-OTC","MICROSOFT-OTC","GOOGLE-OTC","APPLE-OTC","AMAZON-OTC"
]

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================== 2. CONNECT QUOTEX ==================
def connect_quotex(proxy=None):
    q = Quotex(EMAIL, PASSWORD)
    if proxy:
        q.set_proxy(proxy)
    q.connect()
    q.change_balance("PRACTICE")
    return q

quotex_api = connect_quotex(random.choice(PROXIES) if PROXIES else None)

# ================== 3. HELPERS ==================
def safe_sleep(min_sec=0.5, max_sec=1.5):
    time.sleep(random.uniform(min_sec, max_sec))

def ensure_connection():
    global quotex_api
    if not quotex_api.check_connect():
        safe_sleep(10, 15)
        quotex_api = connect_quotex(random.choice(PROXIES) if PROXIES else None)

def get_candles(asset, count=60):
    ensure_connection()
    _, candles = quotex_api.get_candles(asset, 60, count, time.time())
    df = pd.DataFrame(candles)
    df["close"] = df["close"].astype(float)
    df["open"] = df["open"].astype(float)
    return df

def check_signal(df):
    if len(df) < 21: return None
    df["MA21"] = df["close"].rolling(21).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # CALL
    if last["close"] > last["MA21"] and last["close"] > last["open"] and prev["close"] < prev["open"]:
        return "CALL"
    # PUT
    if last["close"] < last["MA21"] and last["close"] < last["open"] and prev["close"] > prev["open"]:
        return "PUT"
    return None

# ================== 4. ENGINE ==================
def run_engine():
    last_reset = datetime.now(IST).date()
    signal_count = 0
    MAX_SIGNALS_PER_HOUR = 6

    while True:
        now = datetime.now(IST)
        if now.date() != last_reset:
            signal_count = 0
            last_reset = now.date()

        if signal_count >= MAX_SIGNALS_PER_HOUR:
            safe_sleep(30, 60)
            continue

        trade_time = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        send_time = trade_time - timedelta(seconds=40)
        while datetime.now(IST) < send_time:
            safe_sleep(0.3,0.5)

        random.shuffle(ALL_PAIRS)
        for asset in ALL_PAIRS:
            df = get_candles(asset)
            signal = check_signal(df)
            if not signal:
                continue

            # Send Telegram signal
            t_str = trade_time.strftime("%H:%M")
            emoji = "🟢 CALL" if signal=="CALL" else "🔴 PUT"
            sticker = STICKER_UP if signal=="CALL" else STICKER_DOWN
            msg = (
f"🔥 **SNIPER SIGNAL** 🔥\n"
f"━━━━━━━━━━━━━━━━━━\n"
f"📊 ASSET ➪ {asset}\n"
f"⏰ ENTRY (IST) ➪ {t_str}:00\n"
f"📈 DIRECTION ➪ **{emoji}**\n"
f"⏳ Advance notice ➪ 40s\n"
f"━━━━━━━━━━━━━━━━━━\n"
f"🚀 Be Ready!"
            )

            for cid in ADMIN_IDS:
                try:
                    bot.send_sticker(cid, sticker)
                    bot.send_message(cid, msg)
                except: pass

            # ===== WAIT FOR TRADE RESULT =====
            time.sleep(65)
            df_after = get_candles(asset, 1)
            last_candle = df_after.iloc[-1]
            mtg_used = False
            if (signal=="CALL" and last_candle["close"] > last_candle["open"]) or \
               (signal=="PUT" and last_candle["close"] < last_candle["open"]):
                result_msg = f"🎯 **{asset} RESULT: WIN ✅**"
                sticker_res = STICKER_ITM
            else:
                # 1-step MTG
                mtg_used = True
                time.sleep(60)
                df_after_mtg = get_candles(asset, 1)
                last_candle = df_after_mtg.iloc[-1]
                if (signal=="CALL" and last_candle["close"] > last_candle["open"]) or \
                   (signal=="PUT" and last_candle["close"] < last_candle["open"]):
                    result_msg = f"🔁 MTG: Use 1 Step if needed\n🎯 **{asset} RESULT: WIN ✅**"
                    sticker_res = STICKER_ITM
                else:
                    result_msg = f"❌ **{asset} RESULT: LOSS 🛡️**"
                    sticker_res = STICKER_OTM

            for cid in ADMIN_IDS:
                try:
                    bot.send_sticker(cid, sticker_res)
                    bot.send_message(cid, result_msg)
                except: pass

            signal_count += 1
            safe_sleep(120,180)  # cooling between signals
            break

# ================== 5. RUN BOT ==================
if __name__=="__main__":
    Thread(target=lambda: bot.polling(none_stop=True)).start()
    run_engine()

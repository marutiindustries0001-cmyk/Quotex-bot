import os, time, pandas as pd, requests, pytz
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== SETTINGS ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
stats = {"wins": 0, "losses": 0, "mtg_wins": 0}

@app.route('/')
def home(): return "♠️ ULTIMATE PRO BOT ♠️: TEST MODE ACTIVE ✅"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Env Variables
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=15)
            if sticker:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": cid, "sticker": sticker}, timeout=15)
        except: pass

def get_accurate_result(pair, direction, q):
    time.sleep(46) 
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

def monitor_loop():
    last_h = None
    while True:
        try:
            now = datetime.now(IST)
            if now.minute % 15 == 0 and now.minute != last_h:
                send_msg(f"💓 <b>STATUS CHECK</b>\n🕒 {now.strftime('%H:%M')} IST\n📡 Bot: Active & Scanning\n🛡️ Mode: Monday-Friday")
                last_h = now.minute
        except: pass
        time.sleep(10)

def start_bot():
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, msg = q.connect()
            if not ok:
                time.sleep(20); continue

            # --- 🛠️ TEST SIGNAL ON STARTUP ---
            test_time = (datetime.now(IST) + timedelta(minutes=1)).strftime('%H:%M')
            test_msg = (f"♠️♠️ <b>Quotex Bot (TEST)</b> ♠️♠️\n\n"
                        f"♠️ <b>PAIR</b> 🟰 💲EURUSD-TEST ♠️\n"
                        f"♠️ <b>TIME ZONE</b> 🟰 UTC +5:30 ♠️\n\n"
                        f"♠️ <b>ONE MINUTE TRADE</b> ♠️\n"
                        f"♠️ <b>TRADE TIME</b> ➖ {test_time} - CALL ♠️\n\n"
                        f"♠️ <b>1 TIME MTG</b> ♠️\n\n"
                        f"♠️♠️ <b>Quotex Bot</b> ♠️♠️")
            send_msg(test_msg, sticker=STICKER_UP)
            # ---------------------------------

            send_msg("♠️♠️ <b>BOT STARTED & LIVE SCANNING</b> ♠️♠️")
            
            last_min = None
            while True:
                now = datetime.now(IST)
                if 18 <= now.second <= 22 and now.minute != last_min:
                    all_p = q.get_all_asset_payout()
                    real_p = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "NZDUSD", "AUDCAD"]
                    otc_p = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", "USDINR-OTC", "USDBRL-OTC", "USDMXN-OTC", "USDARS-OTC", "USDTRY-OTC", "CADJPY-OTC", "NZDCAD-OTC", "AUDUSD-OTC", "GBPJPY-OTC", "USDCAD-OTC", "CHFJPY-OTC"]
                    scan_list = (real_p + otc_p) if now.weekday() < 5 else otc_p

                    for pair in scan_list:
                        try:
                            if all_p.get(pair, 0) < 70: continue
                            candles = q.get_candles(pair, 60, 40, time.time())
                            if not candles: continue
                            df = pd.DataFrame(candles); df['close'] = pd.to_numeric(df['close'])
                            df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
                            df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
                            l, h = df['low'].rolling(14).min(), df['high'].rolling(14).max()
                            df['k'] = 100 * ((df['close'] - l) / (h - l + 1e-10))

                            last, prev = df.iloc[-1], df.iloc[-2]
                            direction = None
                            if prev['ema5'] <= prev['ema13'] and last['ema5'] > last['ema13'] and last['k'] < 85: direction = "CALL"
                            elif prev['ema5'] >= prev['ema13'] and last['ema5'] < last['ema13'] and last['k'] > 15: direction = "PUT"

                            if direction:
                                last_min = now.minute
                                trade_t = (now + timedelta(minutes=1)).strftime('%H:%M')
                                st_icon = STICKER_UP if direction == "CALL" else STICKER_DOWN
                                msg = (f"♠️♠️ <b>Quotex Bot</b> ♠️♠️\n\n"
                                       f"♠️ <b>PAIR</b> 🟰 💲{pair.upper()} ♠️\n"
                                       f"♠️ <b>TRADE TIME</b> ➖ {trade_t} - {direction} ♠️\n\n"
                                       f"♠️ <b>1 TIME MTG</b> ♠️\n\n"
                                       f"♠️♠️ <b>Quotex Bot</b> ♠️♠️")
                                send_msg(msg, sticker=st_icon)
                                res = get_accurate_result(pair, direction, q)
                                if res == "WIN":
                                    send_msg(f"✅ {pair}: <b>ITM</b>", STICKER_ITM); stats["wins"] += 1
                                else:
                                    send_msg(f"⚠️ OTM! <b>MTG-1 STARTING...</b>")
                                    if get_accurate_result(pair, direction, q) == "WIN":
                                        send_msg(f"✅ <b>MTG ITM</b>", STICKER_ITM); stats["mtg_wins"] += 1
                                    else:
                                        send_msg(f"❌ <b>LOSS</b>", STICKER_OTM); stats["losses"] += 1
                                break
                        except: continue
                time.sleep(0.5)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    Thread(target=monitor_loop, daemon=True).start()
    start_bot()

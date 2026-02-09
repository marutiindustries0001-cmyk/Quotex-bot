import os, time, pandas as pd, requests, pytz
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== CONFIGURATION ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
        except: pass

def send_sticker(sticker_id):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_accurate_result(pair, direction, q):
    time.sleep(46) 
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

@app.route('/')
def home(): return "💎 VIP BOT: MA21 FULL SCANNING LIVE ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if ok:
                if not bot_notified:
                    send_msg("🚀 <b>VIP BOT ONLINE</b> 🚀\n\n🛡️ Mode: <b>MA21 Trend Follow</b>\n📡 Scanning 32+ Assets...")
                    bot_notified = True
                
                last_min = None
                while True:
                    now = datetime.now(IST)
                    if now.second >= 15 and now.minute != last_min:
                        all_payouts = q.get_all_asset_payout()
                        scan_list = [
                            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "NZDUSD", "AUDCAD", "USDCAD",
                            "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", "USDINR-OTC", "USDBRL-OTC", 
                            "CADJPY-OTC", "NZDCAD-OTC", "AUDUSD-OTC", "GBPJPY-OTC", "USDCAD-OTC", "CHFJPY-OTC",
                            "EURGBP-OTC", "EURAUD-OTC", "USDARS-OTC", "USDMXN-OTC", "USDCOP-OTC", "USDPHP-OTC", "USDIDR-OTC"
                        ]

                        for pair in scan_list:
                            try:
                                if all_payouts.get(pair, 0) < 70: continue
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['ma21'] = df['close'].rolling(window=21).mean()
                                
                                curr_close = df['close'].iloc[-1]
                                curr_ma21 = df['ma21'].iloc[-1]
                                
                                direction = "CALL" if curr_close > curr_ma21 else "PUT"
                                last_min = now.minute
                                trade_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                
                                # Signal Display
                                send_msg(f"💰 <b>VIP SIGNAL</b> 💰\n\n💵 <b>ASSET</b>: {pair.upper()}\n⏰ <b>TIME</b>: {trade_time}\n📊 <b>DIRECTION</b>: {direction}")
                                send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                
                                # Result
                                res = get_accurate_result(pair, direction, q)
                                if res == "WIN":
                                    send_msg(f"✅ {pair}: <b>ITM</b>"); send_sticker(STICKER_ITM)
                                else:
                                    send_msg(f"⚠️ <b>OTM! MTG-1...</b>")
                                    if get_accurate_result(pair, direction, q) == "WIN":
                                        send_msg(f"✅ <b>MTG-1 ITM</b>"); send_sticker(STICKER_ITM)
                                    else:
                                        send_msg(f"❌ <b>LOSS</b>"); send_sticker(STICKER_OTM)
                                time.sleep(120); break
                            except: continue
                    time.sleep(1)
            else: time.sleep(30)
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()

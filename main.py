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
    time.sleep(50) 
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

@app.route('/')
def home(): return "💎 VIP BOT: NO-FILTER MA21 MODE LIVE ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            
            if ok:
                if not bot_notified:
                    send_msg("🚀 <b>VIP BOT ONLINE: FAST MODE</b> 🚀\n\nAb signals dhada-dhad aayenge!")
                    bot_notified = True
                
                last_min = None
                while True:
                    now = datetime.now(IST)
                    # Har minute ki 10th second par scan shuru
                    if now.second >= 10 and now.minute != last_min:
                        scan_list = [
                            "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDINR-OTC", "USDBDT-OTC", 
                            "AUDUSD-OTC", "EURJPY-OTC", "GBPJPY-OTC", "USDTRY-OTC"
                        ]

                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 40, time.time())
                                if not candles: continue
                                
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['ma21'] = df['close'].rolling(window=21).mean()
                                
                                curr_price = df['close'].iloc[-1]
                                curr_ma21 = df['ma21'].iloc[-1]
                                
                                direction = "CALL" if curr_price > curr_ma21 else "PUT"
                                last_min = now.minute
                                
                                # Signal Bhejna
                                trade_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                send_msg(f"💰 <b>VIP SIGNAL</b> 💰\n\n💵 <b>ASSET</b>: {pair.upper()}\n⏰ <b>TIME</b>: {trade_time}\n📊 <b>DIRECTION</b>: {direction}")
                                send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                
                                # Result
                                res = get_accurate_result(pair, direction, q)
                                if res == "WIN":
                                    send_msg(f"✅ {pair}: <b>ITM</b>"); send_sticker(STICKER_ITM)
                                else:
                                    send_msg(f"❌ {pair}: <b>OTM (Next signal soon)</b>"); send_sticker(STICKER_OTM)
                                
                                time.sleep(10); break # Short break to prevent spam
                            except: continue
                    time.sleep(1)
            else:
                time.sleep(30)
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()

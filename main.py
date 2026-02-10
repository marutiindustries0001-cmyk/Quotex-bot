import os, time, pandas as pd, requests, pytz, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers
STICKER_CALL, STICKER_PUT = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE", "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM, STICKER_OTM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE", "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
        except: pass

def send_sticker(sticker_id):
    if not TELEGRAM_BOT_TOKEN: return
    time.sleep(1)
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_accurate_result(pair, direction, q):
    time.sleep(118) # Deep sync for candle close
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            o, c = float(candles[0]['open']), float(candles[0]['close'])
            if o == c: return "TIE"
            if direction == "CALL": return "WIN" if c > o else "LOSS"
            if direction == "PUT": return "WIN" if c < o else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return "💎 VIP BOT: FULL VERSION ACTIVE ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if ok:
                if not bot_notified:
                    send_msg("🚀 <b>VIP BOT: FINAL POWER UPDATE</b> 🚀\n\n✅ 35+ Assets | MTG-1 Back\n✅ Trend + RSI Verification\n✅ Strict Accuracy Mode")
                    bot_notified = True
                
                last_min = None
                while True:
                    now = datetime.now(IST)
                    if now.second >= 20 and now.second < 25 and now.minute != last_min:
                        scan_list = [
                            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF",
                            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
                            "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
                            "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", 
                            "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc"
                        ]
                        random.shuffle(scan_list)

                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 60, time.time())
                                if not candles or len(candles) < 50: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['ma5'], df['ma21'] = df['close'].rolling(5).mean(), df['close'].rolling(21).mean()
                                
                                delta = df['close'].diff()
                                gain, loss = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
                                df['rsi'] = 100 - (100 / (1 + (gain / loss)))

                                last_c, last_m5, last_m21, last_rsi = df['close'].iloc[-1], df['ma5'].iloc[-1], df['ma21'].iloc[-1], df['rsi'].iloc[-1]

                                direction = None
                                if last_c > last_m5 and last_m5 > last_m21 and last_rsi > 55: direction = "CALL"
                                elif last_c < last_m5 and last_m5 < last_m21 and last_rsi < 45: direction = "PUT"
                                
                                if direction:
                                    last_min = now.minute
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    display_name = pair.replace("_otc", "-OTC").upper()
                                    
                                    send_msg(f"💎 <b>VIP SIGNAL</b> 💎\n\n💵 <b>ASSET:</b> {display_name}\n📊 <b>SIGNAL:</b> {direction}\n⏰ <b>TIME:</b> {t_time}")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    res = get_accurate_result(pair, direction, q)
                                    if res == "WIN":
                                        send_msg(f"✅ <b>{display_name} ITM!!</b>"); send_sticker(STICKER_ITM)
                                    elif res == "TIE":
                                        send_msg(f"⚖️ <b>{display_name} TIE (REFUND)</b>")
                                    else:
                                        send_msg(f"⚠️ <b>{display_name} OTM - MTG-1 START</b>")
                                        res_mtg = get_accurate_result(pair, direction, q)
                                        if res_mtg == "WIN":
                                            send_msg(f"✅ <b>{display_name} MTG-1 WIN!!</b>"); send_sticker(STICKER_ITM)
                                        else:
                                            send_msg(f"❌ <b>{display_name} LOSS</b>"); send_sticker(STICKER_OTM)
                                    time.sleep(10); break 
                            except: continue
                    time.sleep(1)
            else: time.sleep(20)
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
    

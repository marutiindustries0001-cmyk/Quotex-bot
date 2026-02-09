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
    time.sleep(1)
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_accurate_result(pair, direction, q):
    # Wait for 1 minute candle + safety sync
    time.sleep(110)
    try:
        # Get last closed candle
        candles = q.get_candles(pair, 60, 1, time.time())
        if candles:
            o = round(float(candles[0]['open']), 5)
            c = round(float(candles[0]['close']), 5)
            print(f"DEBUG Result check for {pair}: O={o}, C={c}, Dir={direction}")

            if o == c: return "TIE"
            if direction == "CALL":
                return "WIN" if c > o else "LOSS"
            if direction == "PUT":
                return "WIN" if c < o else "LOSS"
    except Exception as e:
        print(f"DEBUG Result Error: {e}")
    return "LOSS"

@app.route('/')
def home(): return "💎 VIP BOT: DIRECTION & RESULT FIXED ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if ok:
                if not bot_notified:
                    send_msg("💎 <b>VIP BOT UPDATED (RESULT FIX)</b> 💎\n\n✅ CALL & PUT Balanced\n✅ Accurate Result Check\n✅ Strong Strategy Active")
                    bot_notified = True
                
                last_min = None
                while True:
                    now = datetime.now(IST)
                    if now.second >= 20 and now.second < 25 and now.minute != last_min:
                        
                        REAL_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP"]
                        OTC_PAIRS = ["EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", "AUDUSD_otc"]
                        STOCKS_OTC = ["FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc", "AMAZON_otc"]
                        
                        scan_list = REAL_PAIRS + OTC_PAIRS + STOCKS_OTC
                        random.shuffle(scan_list)

                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 45, time.time())
                                if not candles or len(candles) < 30: continue
                                
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['ma5'] = df['close'].rolling(5).mean()
                                df['ma21'] = df['close'].rolling(21).mean()
                                
                                # RSI Calculation
                                delta = df['close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                                rsi = 100 - (100 / (1 + (gain / loss)))
                                
                                last_c = df['close'].iloc[-1]
                                last_m5 = df['ma5'].iloc[-1]
                                last_m21 = df['ma21'].iloc[-1]
                                last_rsi = rsi.iloc[-1]

                                direction = None
                                # Balanced Strong Strategy
                                if last_c > last_m5 and last_m5 > last_m21 and last_rsi > 55:
                                    direction = "CALL"
                                elif last_c < last_m5 and last_m5 < last_m21 and last_rsi < 45:
                                    direction = "PUT"
                                
                                if direction:
                                    last_min = now.minute
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    display_name = pair.replace("_otc", "-OTC").upper()
                                    
                                    send_msg(f"💎 <b>VIP PREMIUM SIGNAL</b> 💎\n\n━━━━━━━━━━━━━━━\n💵 <b>ASSET  :</b> {display_name}\n⏰ <b>TIME   :</b> {t_time}\n📊 <b>SIGNAL :</b> {direction}\n━━━━━━━━━━━━━━━")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    # Verification
                                    res = get_accurate_result(pair, direction, q)
                                    if res == "WIN":
                                        send_msg(f"✅ <b>{display_name} ITM!!</b>"); send_sticker(STICKER_ITM)
                                    elif res == "TIE":
                                        send_msg(f"⚖️ <b>{display_name} REFUND (TIE)</b>")
                                    else:
                                        send_msg(f"⚠️ <b>OTM - NEXT CANDLE MTG-1</b>")
                                        res_mtg = get_accurate_result(pair, direction, q)
                                        if res_mtg == "WIN":
                                            send_msg(f"✅ <b>{display_name} MTG-1 WIN!!</b>"); send_sticker(STICKER_ITM)
                                        else:
                                            send_msg(f"❌ <b>{display_name} LOSS</b>"); send_sticker(STICKER_OTM)
                                    
                                    time.sleep(15); break 
                            except: continue
                    time.sleep(1)
            else: time.sleep(20)
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                                        

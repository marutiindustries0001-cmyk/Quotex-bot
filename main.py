import os, time, pandas as pd, requests, pytz, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

# --- CONFIGURATION ---
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
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
        except: pass

def send_sticker(sticker_id):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def verify_result(pair, direction, q):
    # Trade candle khatam hone ka wait (62s)
    time.sleep(62)
    try:
        candles = q.get_candles(pair, 60, 2, time.time())
        if candles:
            candle = candles[-1]
            o, c = round(float(candle['open']), 6), round(float(candle['close']), 6)
            if o == c: return "TIE"
            if direction == "CALL": return "WIN" if c > o else "LOSS"
            if direction == "PUT": return "WIN" if c < o else "LOSS"
    except: pass
    return "LOSS"

@app.route('/')
def home(): return "💎 VIP BOT: BALANCED MODE LIVE ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if ok:
                if not bot_notified:
                    send_msg("🚀 <b>BALANCED SURESHOT MODE</b> 🚀\n\n✅ 1 Trade at a time\n✅ Proper Result Sequence\n✅ Balanced Accuracy")
                    bot_notified = True
                
                last_trade_min = -1
                while True:
                    now = datetime.now(IST)
                    # Har minute scan karega, lekin sequence follow karega
                    if now.second == 58 and (now.minute - last_trade_min >= 2 or last_trade_min == -1):
                        
                        scan_list = [
                            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc", 
                            "AUDUSD_otc", "FACEBOOK_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "AMAZON_otc"
                        ]
                        random.shuffle(scan_list)

                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                
                                # Strategy: EMA Cross + RSI (Balanced 55/45)
                                ema10 = df['close'].ewm(span=10, adjust=False).mean().iloc[-1]
                                ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
                                
                                delta = df['close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                                
                                direction = None
                                if df['close'].iloc[-1] > ema10 and ema10 > ema20 and rsi > 55: direction = "CALL"
                                elif df['close'].iloc[-1] < ema10 and ema10 < ema20 and rsi < 45: direction = "PUT"
                                
                                if direction:
                                    last_trade_min = now.minute
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    asset_label = pair.replace("_otc", "-OTC").upper()
                                    
                                    # Send Signal
                                    send_msg(f"🎯 <b>BALANCED SIGNAL</b>\n\n💵 <b>ASSET :</b> {asset_label}\n📊 <b>SIGNAL :</b> {direction}\n⏰ <b>TIME  :</b> {t_time}")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    # Result Check (Bot yahan wait karega, agla scan nahi karega)
                                    res = verify_result(pair, direction, q)
                                    if res == "WIN":
                                        send_msg(f"✅ <b>{asset_label} ITM!!</b>"); send_sticker(STICKER_ITM)
                                    else:
                                        send_msg(f"❌ <b>{asset_label} OTM</b>"); send_sticker(STICKER_OTM)
                                    
                                    # Trade ke baad 1 min ka extra wait taaki sequence bana rahe
                                    time.sleep(30)
                                    break 
                            except: continue
                    time.sleep(1)
            else: time.sleep(10)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                    

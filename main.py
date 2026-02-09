import os, time, pandas as pd, requests, pytz, random
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
    time.sleep(1)
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                          data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def get_accurate_result(pair, direction, q):
    # Wait: 40s (early alert) + 60s (trade) + 5s (buffer)
    time.sleep(105) 
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
def home(): 
    print(f"DEBUG: Keep-Alive at {datetime.now(IST)}")
    return "💎 VIP BOT: SUPER SCAN MODE ACTIVE ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            print(f"DEBUG: Connecting {QUOTEX_EMAIL}...")
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            
            if ok:
                print("DEBUG: LOGIN SUCCESSFUL! 🎉")
                if not bot_notified:
                    send_msg("🚀 <b>VIP BOT ONLINE (ALL PAIRS)</b> 🚀\n\n✅ 30+ Assets Scanning\n✅ Real + OTC + Stocks\n✅ Aggressive Signal Strategy")
                    bot_notified = True
                
                last_min = None
                while True:
                    # Connection check fixed
                    now = datetime.now(IST)
                    
                    if now.second == 0:
                        print(f"DEBUG: Heartbeat - {now.strftime('%H:%M:%S')}")

                    if now.second >= 20 and now.second < 25 and now.minute != last_min:
                        # MASSIVE LIST - NO PAIRS REMOVED
                        scan_list = [
                            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF",
                            "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDINR-OTC", "USDBDT-OTC", "EURJPY-OTC", 
                            "GBPJPY-OTC", "AUDUSD-OTC", "USDPKR-OTC", "USDBRL-OTC", "EURGBP-OTC", "USDTRY-OTC",
                            "Boeing-OTC", "Facebook-OTC", "Intel-OTC", "McDonald's-OTC", "Microsoft-OTC", 
                            "Netflix-OTC", "Visa-OTC", "Apple-OTC", "Google-OTC", "Amazon-OTC"
                        ]
                        random.shuffle(scan_list)

                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 40, time.time())
                                if not candles: continue
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                df['ma5'] = df['close'].rolling(5).mean()
                                df['ma21'] = df['close'].rolling(21).mean()
                                
                                last_c = df['close'].iloc[-1]
                                last_m5 = df['ma5'].iloc[-1]
                                last_m21 = df['ma21'].iloc[-1]

                                direction = None
                                # Aggressive Mode: Candle must be above/below both MAs
                                if last_c > last_m5 and last_c > last_m21: direction = "CALL"
                                elif last_c < last_m5 and last_c < last_m21: direction = "PUT"
                                
                                if direction:
                                    last_min = now.minute
                                    t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    
                                    send_msg(f"💎 <b>VIP PREMIUM SIGNAL</b> 💎\n\n━━━━━━━━━━━━━━━\n💵 <b>ASSET  :</b> {pair}\n⏰ <b>TIME   :</b> {t_time}\n📊 <b>SIGNAL :</b> {direction}\n━━━━━━━━━━━━━━━\n⚠️ Use 1-Step MTG if needed")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    res = get_accurate_result(pair, direction, q)
                                    if res == "WIN":
                                        send_msg(f"✅ <b>{pair} ITM!!</b>"); send_sticker(STICKER_ITM)
                                    elif res == "TIE":
                                        send_msg(f"⚖️ <b>{pair} REFUND (TIE)</b>")
                                    else:
                                        send_msg(f"⚠️ <b>OTM - NEXT CANDLE MTG-1</b>")
                                        res_mtg = get_accurate_result(pair, direction, q)
                                        if res_mtg == "WIN":
                                            send_msg(f"✅ <b>{pair} MTG-1 WIN!!</b>"); send_sticker(STICKER_ITM)
                                        else:
                                            send_msg(f"❌ <b>{pair} LOSS</b>"); send_sticker(STICKER_OTM)
                                    
                                    time.sleep(10); break 
                            except: continue
                    time.sleep(1)
            else:
                print("DEBUG: Connection failed. Retrying...")
                time.sleep(20)
        except Exception as e:
            print(f"DEBUG: Main Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                

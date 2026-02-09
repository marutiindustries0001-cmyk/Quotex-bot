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

def get_accurate_result(pair, direction, q, target_time):
    """Wait until the target candle closes and check result."""
    # Target time wo minute hai jab trade khatam honi chahiye
    while True:
        now = datetime.now(IST)
        if now >= target_time + timedelta(seconds=2): # Candle close hone ke 2 sec baad check karein
            break
        time.sleep(1)
        
    try:
        candles = q.get_candles(pair, 60, 1, int(time.time()))
        if candles:
            o, c = float(candles[0]['open']), float(candles[0]['close'])
            print(f"DEBUG {pair}: O:{o} C:{c}")
            if (direction == "CALL" and c > o): return "WIN"
            if (direction == "PUT" and c < o): return "WIN"
            if o == c: return "TIE"
            return "LOSS"
    except Exception as e:
        print(f"Result Error: {e}")
        return "ERROR"
    return "ERROR"

@app.route('/')
def home(): return "💎 VIP BOT: MA21 + RSI STABLE ✅"

def start_bot():
    bot_notified = False
    while True:
        try:
            print("Connecting to Quotex...")
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if ok:
                if not bot_notified:
                    send_msg("🚀 <b>VIP PREMIUM BOT ONLINE</b> 🚀\n\n✅ MA21 + RSI Strategy Active\n✅ Timing & Result Logic Fixed")
                    bot_notified = True
                
                last_min = None
                while True:
                    now = datetime.now(IST)
                    
                    # Signal scan: 20th to 25th second of each minute
                    if 20 <= now.second <= 25 and now.minute != last_min:
                        scan_list = ["EURUSD", "GBPUSD", "USDJPY", "EURUSD-OTC", "GBPUSD-OTC", "USDINR-OTC", "AUDCAD-OTC"]
                        
                        for pair in scan_list:
                            try:
                                candles = q.get_candles(pair, 60, 100, int(time.time()))
                                if not candles: continue
                                
                                df = pd.DataFrame(candles)
                                df['close'] = pd.to_numeric(df['close'])
                                
                                # Indicators
                                df['ma21'] = df['close'].rolling(window=21).mean()
                                delta = df['close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                                df['rsi'] = 100 - (100 / (1 + (gain / loss))).fillna(50)

                                last_close = df['close'].iloc[-1]
                                last_ma = df['ma21'].iloc[-1]
                                last_rsi = df['rsi'].iloc[-1]
                                
                                direction = None
                                if last_close > last_ma and last_rsi > 52: direction = "CALL"
                                elif last_close < last_ma and last_rsi < 48: direction = "PUT"
                                
                                if direction:
                                    last_min = now.minute
                                    # Trade setup
                                    signal_minute = now.replace(second=0, microsecond=0)
                                    trade_start_time = signal_minute + timedelta(minutes=1)
                                    trade_end_time = trade_start_time + timedelta(minutes=1)
                                    
                                    send_msg(f"💎 <b>VIP PREMIUM SIGNAL</b> 💎\n\n━━━━━━━━━━━━━━━\n💵 <b>ASSET  :</b> {pair}\n⏰ <b>TIME   :</b> {trade_start_time.strftime('%H:%M')}\n📊 <b>SIGNAL :</b> {direction}\n━━━━━━━━━━━━━━━")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    # Wait and check Direct result
                                    res = get_accurate_result(pair, direction, q, trade_end_time)
                                    
                                    if res == "WIN":
                                        send_msg(f"✅ <b>{pair} DIRECT ITM!!</b>"); send_sticker(STICKER_ITM)
                                    elif res == "TIE":
                                        send_msg(f"⚖️ <b>{pair} REFUND (TIE)</b>")
                                    else:
                                        # MTG Logic
                                        mtg_end_time = trade_end_time + timedelta(minutes=1)
                                        send_msg(f"⚠️ <b>{pair} OTM - PREPARING MTG-1...</b>")
                                        
                                        res_mtg = get_accurate_result(pair, direction, q, mtg_end_time)
                                        if res_mtg == "WIN":
                                            send_msg(f"✅ <b>{pair} MTG-1 WIN!!</b>"); send_sticker(STICKER_ITM)
                                        elif res_mtg == "TIE":
                                            send_msg(f"⚖️ <b>{pair} MTG REFUND</b>")
                                        else:
                                            send_msg(f"❌ <b>{pair} LOSS</b>"); send_sticker(STICKER_OTM)
                                    
                                    # Break to avoid multiple signals in same minute
                                    break 
                            except: continue
                    time.sleep(1)
            else:
                print("Login failed. Retrying...")
                time.sleep(20)
        except Exception as e:
            print(f"Bot Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Web server thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    start_bot()

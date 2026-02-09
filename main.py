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
def home(): return "💎 VIP BOT: FULLY OPTIMIZED ✅"

@app.route('/keepalive')
def keepalive(): return "running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Env Variables
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Sticker IDs
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_sticker(sticker_id):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker_id}, timeout=10)
        except: pass

def send_msg(text):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
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
            # Daily report at 11:59 PM
            if now.hour == 23 and now.minute == 59 and now.second < 15:
                rep = f"📊 <b>DAILY REPORT</b>\n\n✅ Direct ITM: {stats['wins']}\n🔄 MTG ITM: {stats['mtg_wins']}\n❌ Total Loss: {stats['losses']}"
                send_msg(rep)
                stats.update({"wins": 0, "losses": 0, "mtg_wins": 0})
                time.sleep(20)
        except: pass
        time.sleep(10)

def start_bot():
    bot_notified = False 
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            
            if ok:
                if not bot_notified:
                    send_msg("🚀 <b>VIP BOT ONLINE</b> 🚀\n\n🛡️ Mode: <b>High Accuracy SNR</b>\n📡 Scanning Market...")
                    bot_notified = True
                
                last_min = None
                while q.check_connect():
                    now = datetime.now(IST)
                    if 18 <= now.second <= 25 and now.minute != last_min:
                        all_payouts = q.get_all_asset_payout()
                        scan_list = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "NZDUSD", "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", "USDINR-OTC", "USDBRL-OTC"]

                        for pair in scan_list:
                            try:
                                if all_payouts.get(pair, 0) < 70: continue
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue
                                
                                df = pd.DataFrame(candles)
                                df['close'], df['high'], df['low'] = pd.to_numeric(df['close']), pd.to_numeric(df['high']), pd.to_numeric(df['low'])
                                df['sma21'] = df['close'].rolling(window=21).mean()
                                
                                res_val = df['high'].iloc[-20:-1].max()
                                sup_val = df['low'].iloc[-20:-1].min()
                                curr_p, curr_s = df['close'].iloc[-1], df['sma21'].iloc[-1]
                                
                                direction = None
                                # Slightly more sensitive SNR detection
                                if curr_p <= (sup_val * 1.0005) and curr_p > curr_s: direction = "CALL"
                                elif curr_p >= (res_val * 0.9995) and curr_p < curr_s: direction = "PUT"

                                if direction:
                                    last_min = now.minute
                                    trade_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                    send_msg(f"💰 <b>VIP SIGNAL</b> 💰\n\n💵 <b>ASSET</b>: {pair.upper()}\n⏰ <b>TIME</b>: {trade_time} (1 MIN)\n📊 <b>DIRECTION</b>: {direction}")
                                    send_sticker(STICKER_CALL if direction == "CALL" else STICKER_PUT)
                                    
                                    res = get_accurate_result(pair, direction, q)
                                    if res == "WIN":
                                        send_msg(f"✅ {pair}: <b>DIRECT ITM</b>"); send_sticker(STICKER_ITM); stats["wins"] += 1
                                    else:
                                        send_msg(f"⚠️ <b>OTM! PREPARING MTG-1...</b>")
                                        if get_accurate_result(pair, direction, q) == "WIN":
                                            send_msg(f"✅ <b>MTG-1 ITM</b>"); send_sticker(STICKER_ITM); stats["mtg_wins"] += 1
                                        else:
                                            send_msg(f"❌ <b>FINAL LOSS</b>"); send_sticker(STICKER_OTM); stats["losses"] += 1
                                    time.sleep(120); break 
                            except: continue
                    time.sleep(1)
            else:
                time.sleep(30) # Login fail delay
        except: time.sleep(10)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    Thread(target=monitor_loop, daemon=True).start() # Thread fixed
    start_bot()

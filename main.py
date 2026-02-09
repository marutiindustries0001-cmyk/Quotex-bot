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
def home(): return "♠️ PRO BOT ♠️: COOLING MODE ACTIVE ✅"

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

# Stickers
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                          data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
            if sticker:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", 
                              data={"chat_id": cid, "sticker": sticker}, timeout=12)
        except: pass

def get_accurate_result(pair, direction, q):
    time.sleep(45) 
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
                send_msg(f"💓 <b>SYSTEM STATUS</b>\n🕒 {now.strftime('%H:%M')} IST\n📡 Scanning All Assets...")
                last_h = now.minute
            if now.hour == 23 and now.minute == 59 and now.second < 10:
                rep = f"📊 <b>DAILY REPORT</b>\n\n✅ Direct ITM: {stats['wins']}\n🔄 MTG ITM: {stats['mtg_wins']}\n❌ Total Loss: {stats['losses']}"
                send_msg(rep)
                stats["wins"], stats["losses"], stats["mtg_wins"] = 0, 0, 0
                time.sleep(15)
        except: pass
        time.sleep(10)

def start_bot():
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, _ = q.connect()
            if not ok:
                time.sleep(10); continue

            # WELCOME MESSAGE - LOOP KE BAHAR (Only once)
            send_msg("♠️♠️ <b>QUOTEX BOT ONLINE</b> ♠️♠️\n\n✅ 30+ Pairs Scanning\n✅ 40s Early Signals\n✅ 2-Min Cooling Break Active")
            
            last_min = None
            while True:
                now = datetime.now(IST)
                if 18 <= now.second <= 22 and now.minute != last_min:
                    all_payouts = q.get_all_asset_payout()
                    
                    real_p = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "NZDUSD", "AUDCAD"]
                    otc_p = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", "USDINR-OTC", "USDBRL-OTC", "USDMXN-OTC", "USDARS-OTC", "USDTRY-OTC", "CADJPY-OTC", "NZDCAD-OTC", "AUDUSD-OTC", "GBPJPY-OTC", "USDCAD-OTC", "CHFJPY-OTC"]
                    
                    day = now.weekday()
                    scan_list = (real_p + otc_p) if day < 5 else otc_p

                    for pair in scan_list:
                        try:
                            if all_payouts.get(pair, 0) < 70: continue
                            candles = q.get_candles(pair, 60, 40, time.time())
                            if not candles: continue
                            
                            df = pd.DataFrame(candles)
                            df['close'] = pd.to_numeric(df['close'])
                            df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
                            df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
                            low_m, high_m = df['low'].rolling(14).min(), df['high'].rolling(14).max()
                            df['k'] = 100 * ((df['close'] - low_m) / (high_m - low_m + 1e-10))

                            last, prev = df.iloc[-1], df.iloc[-2]
                            direction = None
                            
                            if prev['ema5'] <= prev['ema13'] and last['ema5'] > last['ema13'] and last['k'] < 95: 
                                direction = "CALL"
                            elif prev['ema5'] >= prev['ema13'] and last['ema5'] < last['ema13'] and last['k'] > 5: 
                                direction = "PUT"

                            if direction:
                                last_min = now.minute
                                trade_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                msg = (f"♠️♠️ <b>Quotex Bot</b> ♠️♠️\n\n"
                                       f"♠️ <b>PAIR</b> 🟰 💲{pair.upper()} ♠️\n"
                                       f"♠️ <b>TIME ZONE</b> 🟰 UTC +5:30 ♠️\n\n"
                                       f"♠️ <b>ONE MINUTE TRADE</b> ♠️\n"
                                       f"♠️ <b>TRADE TIME</b> ➖ {trade_time} - {direction} ♠️\n\n"
                                       f"♠️ <b>1 TIME MTG</b> ♠️\n\n"
                                       f"♠️♠️ <b>Quotex Bot</b> ♠️♠️")
                                send_msg(msg)
                                
                                res = get_accurate_result(pair, direction, q)
                                if res == "WIN":
                                    send_msg(f"✅ {pair}: <b>ITM</b>", STICKER_ITM); stats["wins"] += 1
                                else:
                                    send_msg(f"⚠️ OTM! <b>MTG-1 STARTING...</b>")
                                    if get_accurate_result(pair, direction, q) == "WIN":
                                        send_msg(f"✅ <b>MTG ITM</b>", STICKER_ITM); stats["mtg_wins"] += 1
                                    else:
                                        send_msg(f"❌ <b>LOSS</b>", STICKER_OTM); stats["losses"] += 1
                                
                                # --- COOLING BREAK ---
                                time.sleep(120) 
                                break 
                        except: continue
                time.sleep(0.5)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    Thread(target=monitor_loop, daemon=True).start()
    start_bot()

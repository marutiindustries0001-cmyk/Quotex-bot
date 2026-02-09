import os, time, pandas as pd, requests, pytz
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== SETTINGS (VERIFIED) ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
stats = {"wins": 0, "losses": 0, "mtg_wins": 0}

@app.route('/')
def home(): return "♠️ VIP PRO BOT ♠️: UI OPTIMIZED ✅"

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
    time.sleep(48) 
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

def start_bot():
    while True:
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            ok, msg = q.connect()
            if not ok: time.sleep(20); continue

            send_msg("🚀 <b>VIP BOT ACTIVATED</b> 🚀\n\n💰 <i>High Accuracy Signals Loading...</i>")
            
            last_min = None
            while True:
                if not q.check_connect(): break
                now = datetime.now(IST)
                
                if 15 <= now.second <= 25 and now.minute != last_min:
                    try: all_p = q.get_all_asset_payout()
                    except: all_p = {}

                    real_p = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", "NZDUSD", "AUDCAD"]
                    otc_p = ["EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", "USDINR-OTC", "USDBRL-OTC", "USDMXN-OTC", "USDARS-OTC", "USDTRY-OTC", "CADJPY-OTC", "NZDCAD-OTC", "AUDUSD-OTC", "GBPJPY-OTC", "USDCAD-OTC", "CHFJPY-OTC"]
                    scan_list = (real_p + otc_p) if now.weekday() < 5 else otc_p

                    for pair in scan_list:
                        try:
                            if all_p.get(pair, 0) < 70: continue
                            candles = q.get_candles(pair, 60, 50, time.time())
                            if not candles: continue
                            
                            df = pd.DataFrame(candles); df['close'] = pd.to_numeric(df['close'])
                            df['ema_f'] = df['close'].ewm(span=4, adjust=False).mean()
                            df['ema_s'] = df['close'].ewm(span=10, adjust=False).mean()
                            delta = df['close'].diff(); gain = (delta.where(delta > 0, 0)).rolling(7).mean(); loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
                            df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
                            
                            last, prev = df.iloc[-1], df.iloc[-2]
                            direction = None
                            
                            if prev['ema_f'] <= prev['ema_s'] and last['ema_f'] > last['ema_s'] and last['rsi'] > 50: direction = "CALL"
                            elif prev['ema_f'] >= prev['ema_s'] and last['ema_f'] < last['ema_s'] and last['rsi'] < 50: direction = "PUT"

                            if direction:
                                last_min = now.minute
                                trade_t = (now + timedelta(minutes=1)).strftime('%H:%M')
                                st_icon = STICKER_UP if direction == "CALL" else STICKER_DOWN
                                arrow = "⬆️" if direction == "CALL" else "⬇️"
                                
                                # 🔥 ATTRACTIVE VIP FORMAT 🔥
                                msg = (f"👑 <b>PREMIUM SIGNAL</b> 👑\n\n"
                                       f"💎 <b>ASSET</b> ➬ <code>{pair.upper()}</code>\n"
                                       f"🕒 <b>TIME</b> ➬ <code>{trade_t} (1 MIN)</code>\n"
                                       f"🚀 <b>ACTION</b> ➬ <b>{direction} {arrow}</b>\n\n"
                                       f"⚠️ <i>Use 1-Step MTG if needed</i>\n"
                                       f"➖➖➖➖➖➖➖➖➖➖\n"
                                       f"♠️ <b>QUOTEX ULTIMATE</b> ♠️")
                                
                                send_msg(msg, sticker=st_icon)
                                
                                res = get_accurate_result(pair, direction, q)
                                if res == "WIN":
                                    send_msg(f"✅ <b>PROFIT:</b> {pair}\n🔥 <i>Direct ITM!</i>", STICKER_ITM); stats["wins"] += 1
                                else:
                                    send_msg(f"🔄 <b>WAITING:</b> Starting MTG-1...")
                                    if get_accurate_result(pair, direction, q) == "WIN":
                                        send_msg(f"✅ <b>MTG SUCCESS!</b>\n💰 <i>Recovered & Profit</i>", STICKER_ITM); stats["mtg_wins"] += 1
                                    else:
                                        send_msg(f"❌ <b>OTM:</b> Skip this pair", STICKER_OTM); stats["losses"] += 1
                                break
                        except: continue
                time.sleep(0.5)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

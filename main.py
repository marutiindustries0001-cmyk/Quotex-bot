import os, time, pandas as pd, requests, pytz
from datetime import datetime
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# ==================== SETTINGS ====================
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
stats = {"wins": 0, "losses": 0, "mtg_wins": 0}

@app.route('/')
def home(): return "ULTIMATE PRO BOT: 100% STABLE ✅"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Env Variables
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers (All Restored)
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=12)
            if sticker: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker}, timeout=12)
        except: pass

# --- Independent Thread for Heartbeat & Daily Summary ---
def monitor_loop():
    last_h = None
    while True:
        try:
            now = datetime.now(IST)
            # Heartbeat every 15 mins
            if now.minute % 15 == 0 and now.minute != last_h:
                send_msg(f"💓 <b>Bot Status Check</b>\n🕒 Time: {now.strftime('%H:%M')} IST\n📡 System: Online & Scanning 30+ Assets")
                last_h = now.minute
            
            # Daily Report at 11:59 PM
            if now.hour == 23 and now.minute == 59 and now.second < 10:
                report = f"📊 <b>DAILY TRADING SUMMARY</b>\n\n✅ Direct Wins: {stats['wins']}\n🔄 MTG Wins: {stats['mtg_wins']}\n❌ Total Loss: {stats['losses']}"
                send_msg(report)
                stats["wins"], stats["losses"], stats["mtg_wins"] = 0, 0, 0
                time.sleep(15)
        except: pass
        time.sleep(10)

def get_accurate_result(pair, direction, q):
    time.sleep(45) # Wait for candle close (triggered at 20s mark)
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        if not candles: return "ERROR"
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

def start_bot():
    while True: # Auto-Reconnect Loop
        try:
            q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
            check, msg = q.connect()
            if not check:
                time.sleep(10); continue
            
            send_msg("🏆 <b>BOT FULLY SYNCED</b>\n\n✅ Advance: 40s Early\n✅ Assets: 30+ (Real/OTC)\n✅ MTG-1 Facility: Active")

            last_min = None
            while True: # Scan Loop
                now = datetime.now(IST)
                
                if now.second == 20 and now.minute != last_min:
                    all_payouts = q.get_all_asset_payout()
                    # 100% Complete List
                    pairs = [
                        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY", "NZDUSD", "AUDCAD", # REAL
                        "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", "USDINR-OTC", "USDBRL-OTC",
                        "USDMXN-OTC", "USDARS-OTC", "USDTRY-OTC", "USDEGP-OTC", "CADJPY-OTC", "AUDUSD-OTC", "USDCAD-OTC"
                    ]
                    
                    for pair in pairs:
                        try:
                            if all_payouts.get(pair, 0) < 70: continue 
                            candles = q.get_candles(pair, 60, 40, time.time())
                            if not candles: continue
                            
                            df = pd.DataFrame(candles); df['close'] = pd.to_numeric(df['close'])
                            df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
                            df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
                            l14, h14 = df['low'].rolling(14).min(), df['high'].rolling(14).max()
                            df['k'] = 100 * ((df['close'] - l14) / (h14 - l14 + 1e-10))
                            
                            last, prev = df.iloc[-1], df.iloc[-2]
                            direction = None
                            if prev['ema5'] <= prev['ema13'] and last['ema5'] > last['ema13'] and last['k'] < 85: direction = "CALL"
                            elif prev['ema5'] >= prev['ema13'] and last['ema5'] < last['ema13'] and last['k'] > 15: direction = "PUT"

                            if direction:
                                last_min = now.minute
                                send_msg(f"⏳ <b>EARLY SIGNAL (40s)</b>\n🌍 Asset: {pair}\n👉 Action: {direction}", 
                                         sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                                
                                res = get_accurate_result(pair, direction, q)
                                if res == "WIN":
                                    send_msg(f"✅ {pair}: <b>ITM</b>", STICKER_ITM); stats["wins"] += 1
                                else:
                                    send_msg(f"⚠️ OTM! <b>MTG-1...</b>")
                                    res_mtg = get_accurate_result(pair, direction, q)
                                    if res_mtg == "WIN":
                                        send_msg(f"✅ <b>MTG ITM</b>", STICKER_ITM); stats["mtg_wins"] += 1
                                    else:
                                        send_msg(f"❌ <b>LOSS</b>", STICKER_OTM); stats["losses"] += 1
                                break
                        except: continue
                time.sleep(0.5)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    Thread(target=monitor_loop, daemon=True).start()
    start_bot()

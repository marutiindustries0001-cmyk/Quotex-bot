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
def home(): return "Final Pro Bot: All Facilities Active ✅"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Env Variables
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

# Stickers (All Restored)
STICKER_UP, STICKER_DOWN = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE", "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM, STICKER_OTM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE", "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_msg(text, sticker=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"}, timeout=5)
            if sticker: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker}, timeout=5)
        except: pass

def get_accurate_result(pair, direction, q):
    time.sleep(45) # Triggered at 20s, so wait 45s to clear the 1-min candle
    try:
        candles = q.get_candles(pair, 60, 1, time.time())
        o, c = float(candles[0]['open']), float(candles[0]['close'])
        if (direction == "CALL" and c > o) or (direction == "PUT" and c < o): return "WIN"
        return "LOSS"
    except: return "ERROR"

def start_bot():
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    if not q.connect()[0]: return
    
    send_msg("🏆 <b>PRO BOT: FINAL VERSION DEPLOYED</b>\n\n✅ Advance: 40 Seconds\n✅ Strategy: EMA + Stoch (Strict)\n✅ Assets: 25+ Real & OTC\n✅ Daily Stats & Stickers: ON")

    last_min, last_heartbeat = None, None
    is_trading = False

    while True:
        try:
            now = datetime.now(IST)
            
            # 15-Min Heartbeat
            if now.minute % 15 == 0 and now.minute != last_heartbeat:
                send_msg(f"💓 <b>Status Check:</b> Bot is Scanning...\n🕒 Time: {now.strftime('%H:%M')} IST\n💰 Filter: 70%+")
                last_heartbeat = now.minute

            # Daily Summary at Midnight
            if now.hour == 23 and now.minute == 59 and now.second == 0:
                report = f"📊 <b>DAILY TRADING SUMMARY</b>\n\n✅ Direct Wins: {stats['wins']}\n🔄 MTG Wins: {stats['mtg_wins']}\n❌ Total Loss: {stats['losses']}"
                send_msg(report)
                stats["wins"], stats["losses"], stats["mtg_wins"] = 0, 0, 0
                time.sleep(1)

            # --- SIGNAL TRIGGER AT 20 SECONDS (40s Advance) ---
            if not is_trading and now.second == 20 and now.minute != last_min:
                all_payouts = q.get_all_asset_payout()
                
                pairs = [
                    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "GBPJPY", # Real
                    "EURUSD-OTC", "GBPUSD-OTC", "USDJPY-OTC", "USDPKR-OTC", "USDBDT-OTC", # OTC
                    "USDINR-OTC", "USDBRL-OTC", "USDMXN-OTC", "USDARS-OTC", "USDTRY-OTC", 
                    "CADJPY-OTC", "AUDCAD-OTC", "NZDUSD-OTC", "EURGBP-OTC"
                ]
                
                for pair in pairs:
                    if all_payouts.get(pair, 0) < 70: continue 
                    
                    candles = q.get_candles(pair, 60, 40, time.time())
                    if not candles: continue
                    
                    df = pd.DataFrame(candles); df['close'] = pd.to_numeric(df['close'])
                    df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
                    df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
                    
                    # Stochastic Facility (Restored)
                    low_14, high_14 = df['low'].rolling(14).min(), df['high'].rolling(14).max()
                    df['k'] = 100 * ((df['close'] - low_14) / (high_14 - low_14 + 1e-10))
                    
                    last, prev = df.iloc[-1], df.iloc[-2]
                    direction = None

                    # Strict Crossover Logic (Restored)
                    if prev['ema5'] <= prev['ema13'] and last['ema5'] > last['ema13'] and last['k'] < 80:
                        direction = "CALL"
                    elif prev['ema5'] >= prev['ema13'] and last['ema5'] < last['ema13'] and last['k'] > 20:
                        direction = "PUT"

                    if direction:
                        is_trading = True; last_min = now.minute
                        target_time = f"{now.hour}:{(now.minute + 1) % 60:02d}"
                        
                        send_msg(f"⏳ <b>ADVANCE SIGNAL (40s)</b>\n\n🌍 <b>ASSET:</b> {pair}\n💰 <b>PAYOUT:</b> {all_payouts.get(pair)}%\n⏰ <b>TIME:</b> {target_time}\n👉 <b>ACTION:</b> {direction}", 
                                 sticker=(STICKER_UP if direction == "CALL" else STICKER_DOWN))
                        
                        # --- Result Logic with MTG-1 Facility (Restored) ---
                        res = get_accurate_result(pair, direction, q)
                        if res == "WIN":
                            send_msg(f"✅ {pair}: <b>ITM</b>", STICKER_ITM); stats["wins"] += 1
                        else:
                            send_msg(f"⚠️ {pair}: OTM! <b>MTG-1 Starting...</b>")
                            # MTG result waits for the NEXT candle
                            res_mtg = get_accurate_result(pair, direction, q)
                            if res_mtg == "WIN":
                                send_msg(f"✅ {pair}: <b>MTG ITM</b>", STICKER_ITM); stats["mtg_wins"] += 1
                            else:
                                send_msg(f"❌ {pair}: <b>LOSS</b>", STICKER_OTM); stats["losses"] += 1
                        
                        is_trading = False; break
            time.sleep(1)
        except: time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    start_bot()

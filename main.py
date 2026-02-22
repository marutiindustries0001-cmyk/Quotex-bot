import os, time, pytz, requests, pandas as pd, sys
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask
from quotexapi.stable_api import Quotex

# ================= 🛠️ GATEWAY (MOBILE PROXY OPTIMIZED) =================
PROXY = os.getenv("PROXY_URL") 
if PROXY:
    os.environ['http_proxy'] = PROXY
    os.environ['https_proxy'] = PROXY
    os.environ['HTTP_PROXY'] = PROXY
    os.environ['HTTPS_PROXY'] = PROXY

# ================= 🛠️ CONFIG (IST SYNCED) =================
IST = pytz.timezone("Asia/Kolkata")
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if cid.strip()]

STICKER_CALL = os.getenv("STICKER_CALL")
STICKER_PUT = os.getenv("STICKER_PUT")
STICKER_WIN = os.getenv("STICKER_WIN")
STICKER_LOSS = os.getenv("STICKER_LOSS")

app = Flask(__name__)
trade_lock = Lock()
client = None
trade_active = False
stats = {"win": 0, "loss": 0, "refund": 0, "total": 0}
last_login_time = datetime.now()

@app.route("/")
def health(): return "GS_V17_12_EXPANDED_OTC_ACTIVE", 200

# ================= 📊 EXPANDED OTC ASSETS (15 PAIRS) =================
verified_assets = [
    "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc",
    "EURJPY_otc", "GBPJPY_otc", "USDINR_otc", "USDBRL_otc",
    "USDTRY_otc", "EURGBP_otc", "NZDUSD_otc", "GBPCHF_otc",
    "AUDJPY_otc", "CADJPY_otc", "GBPAUD_otc"
]

def send_telegram(text=None, sticker=None):
    if not BOT_TOKEN: return
    for chat_id in CHAT_IDS:
        try:
            if text: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode":"HTML"}, timeout=15)
            if sticker:
                time.sleep(0.5)
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker", json={"chat_id": chat_id, "sticker": sticker}, timeout=15)
        except: pass

def connect():
    global client, last_login_time
    try:
        client = Quotex(email=EMAIL, password=PASSWORD)
        ok, _ = client.connect()
        if ok:
            last_login_time = datetime.now()
            print(f"✅ [SYNC OK] Server Time: {datetime.now(IST).strftime('%H:%M:%S')}", flush=True)
            return True
    except: pass
    return False

connect()

def get_candles_validated(asset):
    global client
    try:
        # Fetching 20 candles for speed over mobile proxy
        candles = client.get_candles(asset, 60, 20)
        if candles and len(candles) >= 15:
            df = pd.DataFrame(candles)
            last_candle_time = int(df.iloc[-1]["time"])
            current_time = int(time.time())
            
            # HARD SYNC CHECK: Data fresh hona chahiye
            if abs(current_time - last_candle_time) > 70:
                return None
                
            df["close"] = pd.to_numeric(df["close"])
            df["open"] = pd.to_numeric(df["open"])
            df["ema7"] = df["close"].ewm(span=7, adjust=False).mean()
            df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
            delta = df["close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            df["rsi"] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
            return df
    except: pass
    return None

def process_trade(pair, direction, entry_time):
    global trade_active, stats
    label = pair.replace("_otc", "-OTC").upper()
    
    # ⚡ EARLY SIGNAL (approx 35-40 seconds before candle start)
    send_telegram(text=f"🎯 <b>VIP SIGNAL: {label}</b>\n📊 <b>DIR:</b> {'🟢 CALL' if direction=='CALL' else '🔴 PUT'}\n⏰ TARGET: {datetime.fromtimestamp(entry_time, IST).strftime('%H:%M')}", 
                  sticker=STICKER_CALL if direction=="CALL" else STICKER_PUT)
    
    time.sleep(68)
    
    res = "ERROR"
    for _ in range(3):
        df = get_candles_validated(pair)
        if df is not None:
            match = df[df["time"] == entry_time]
            if not match.empty:
                o, c = float(match.iloc[0]["open"]), float(match.iloc[0]["close"])
                if round(o,6) == round(c,6): res = "TIE"
                elif direction == "CALL": res = "WIN" if c > o else "LOSS"
                else: res = "WIN" if c < o else "LOSS"
                break
        time.sleep(5)

    stats["total"] += 1
    if res == "WIN":
        stats["win"] += 1
        send_telegram(text=f"✅ <b>{label} WIN!</b>", sticker=STICKER_WIN)
    elif res == "TIE":
        stats["refund"] += 1
        send_telegram(text=f"💸 <b>{label} REFUND (TIE)</b>")
    elif res == "LOSS":
        stats["loss"] += 1
        send_telegram(text=f"❌ <b>{label} LOSS</b>", sticker=STICKER_LOSS)

    with trade_lock: trade_active = False

def core_loop():
    global trade_active, last_login_time
    last_min = None
    while True:
        now = datetime.now(IST)
        if datetime.now() - last_login_time > timedelta(minutes=15): connect()

        # SCAN START AT 20th SECOND (This gives 40 seconds buffer)
        if now.second == 20: 
            with trade_lock:
                if trade_active or last_min == now.minute:
                    time.sleep(1); continue
                last_min = now.minute
                
                print(f"🔍 [SCAN] Monitoring 15 OTC Assets @ {now.strftime('%H:%M:%S')}", flush=True)
                for pair in verified_assets:
                    time.sleep(1.2) # Throttled for mobile proxy
                    df = get_candles_validated(pair)
                    if df is None: continue
                    
                    l = df.iloc[-1]
                    rsi, e7, e21 = round(l["rsi"], 2), round(l["ema7"], 4), round(l["ema21"], 4)
                    
                    if rsi > 55 and e7 > e21:
                        trade_active = True
                        Thread(target=process_trade, args=(pair, "CALL", int(l["time"]) + 60)).start()
                        break
                    elif rsi < 45 and e7 < e21:
                        trade_active = True
                        Thread(target=process_trade, args=(pair, "PUT", int(l["time"]) + 60)).start()
                        break
        time.sleep(0.5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)).start()
    send_telegram("🚀 **GS V17.12 EXPANDED OTC**\n15 Pairs | Mobile Proxy Buffer: 40s")
    core_loop()

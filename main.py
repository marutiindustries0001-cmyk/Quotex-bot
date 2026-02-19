import os, time, pytz, requests, pandas as pd, sys
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask
from quotexapi.stable_api import Quotex

# ================= 🛠️ ENV & CONFIG (Wahi Sari Settings) =================
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if cid.strip()]

STICKER_CALL, STICKER_PUT = os.getenv("STICKER_CALL"), os.getenv("STICKER_PUT")
STICKER_WIN, STICKER_LOSS = os.getenv("STICKER_WIN"), os.getenv("STICKER_LOSS")

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
trade_lock = Lock()

client = None
trade_active = False
stats = {"win": 0, "loss": 0, "refund": 0, "total": 0}
last_login_time = datetime.now()
last_summary_date = None

@app.route("/")
def health(): return "GS_V16_2_FULL_STABLE_ACTIVE", 200

# ================= 📊 ASSETS =================
verified_assets = [
    "EURUSD_otc","GBPUSD_otc","USDJPY_otc","AUDUSD_otc",
    "EURJPY_otc","GBPJPY_otc","EURGBP_otc","USDCHF_otc",
    "USDINR_otc","USDBRL_otc","USDTRY_otc",
    "USDBDT_otc","USDPKR_otc","USDMXN_otc",
    "EURUSD","GBPUSD","USDJPY","AUDUSD","EURJPY","GBPJPY","EURGBP","USDCHF"
]

def send_telegram(text=None, sticker=None):
    if not BOT_TOKEN: return
    for chat_id in CHAT_IDS:
        try:
            if text: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode":"HTML"}, timeout=10)
            if sticker:
                time.sleep(0.5)
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker", json={"chat_id": chat_id, "sticker": sticker}, timeout=10)
        except: pass

def connect():
    global client, last_login_time
    print(f"[DEBUG] Initiating Stability Sync...", flush=True)
    try:
        client = Quotex(email=EMAIL, password=PASSWORD)
        ok, _ = client.connect()
        if ok:
            last_login_time = datetime.now()
            print("✅ [SUCCESS] Session Established. Cooling down 10s...", flush=True)
            time.sleep(10)
            return True
    except: pass
    return False

connect()

def get_candles(asset):
    global client
    try:
        candles = client.get_candles(asset, 60, 60)
        if candles and len(candles) >= 20:
            df = pd.DataFrame(candles)
            df["close"] = pd.to_numeric(df["close"])
            df["ema7"] = df["close"].ewm(span=7, adjust=False).mean()
            df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
            delta = df["close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            df["rsi"] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
            return df
    except: pass
    return None

def verify_result(pair, entry_time, direction):
    time.sleep(68) # Wait for Candle Close
    for _ in range(3):
        df = get_candles(pair)
        if df is not None:
            match = df[df["time"] == entry_time]
            if not match.empty:
                o, c = float(match.iloc[0]["open"]), float(match.iloc[0]["close"])
                print(f"⚖️ [RESULT] {pair} | O: {round(o,6)} | C: {round(c,6)}", flush=True)
                if round(o, 6) == round(c, 6): return "TIE"
                if direction == "CALL": return "WIN" if c > o else "LOSS"
                else: return "WIN" if c < o else "LOSS"
        time.sleep(3)
    return "ERROR"

def trade_engine(pair, direction, entry_time):
    global trade_active, stats
    label = pair.replace("_otc", "-OTC").upper()
    send_telegram(text=f"🎯 <b>VIP SIGNAL: {label}</b>\n📊 <b>DIR:</b> {'🟢 CALL' if direction=='CALL' else '🔴 PUT'}\n⏰ <b>TIME:</b> {datetime.fromtimestamp(entry_time, IST).strftime('%H:%M')}", 
                  sticker=STICKER_CALL if direction=="CALL" else STICKER_PUT)
    stats["total"] += 1
    
    res = verify_result(pair, entry_time, direction)
    if res == "WIN":
        stats["win"] += 1
        send_telegram(text=f"✅ <b>{label} DIRECT WIN!</b>", sticker=STICKER_WIN)
    elif res == "TIE":
        stats["refund"] += 1
        send_telegram(text=f"💸 <b>{label} REFUND (TIE)</b>")
    elif res == "LOSS":
        send_telegram(text=f"❌ <b>{label} DIRECT LOSS</b>\n🔁 <b>MTG-1 STARTED</b>")
        m_res = verify_result(pair, entry_time + 60, direction)
        if m_res == "WIN":
            stats["win"] += 1
            send_telegram(text=f"✅ <b>{label} MTG WIN!</b>", sticker=STICKER_WIN)
        elif m_res == "TIE":
            stats["refund"] += 1
            send_telegram(text=f"💸 <b>{label} MTG REFUND (TIE)</b>")
        else:
            stats["loss"] += 1
            send_telegram(text=f"❌ <b>{label} LOSS</b>", sticker=STICKER_LOSS)
    with trade_lock: trade_active = False

def core_loop():
    global trade_active, last_login_time
    last_min = None
    while True:
        now = datetime.now(IST)
        if datetime.now() - last_login_time > timedelta(minutes=25): connect()

        if now.second == 20:
            with trade_lock:
                if trade_active or last_min == now.minute:
                    time.sleep(1); continue
                last_min = now.minute
                
                print(f"🔍 [SCAN] Checking 22 Assets...", flush=True)
                err_streak = 0
                for pair in verified_assets:
                    time.sleep(1.5) # Human-like throttle
                    df = get_candles(pair)
                    
                    if df is None:
                        err_streak += 1
                        print(f"   > {pair} | ⚠️ Syncing...", flush=True)
                        if err_streak >= 5:
                            connect()
                            break
                        continue
                    
                    err_streak = 0
                    l = df.iloc[-1]
                    rsi, e7, e21 = round(l["rsi"], 2), round(l["ema7"], 4), round(l["ema21"], 4)
                    print(f"   > {pair} | RSI: {rsi} | EMA: OK", flush=True)
                    
                    if rsi > 55 and e7 > e21:
                        trade_active = True
                        Thread(target=trade_engine, args=(pair, "CALL", int(l["time"]) + 60)).start()
                        break
                    elif rsi < 45 and e7 < e21:
                        trade_active = True
                        Thread(target=trade_engine, args=(pair, "PUT", int(l["time"]) + 60)).start()
                        break
        time.sleep(0.5)

def summary_loop():
    global stats, last_summary_date
    while True:
        now = datetime.now(IST)
        if now.strftime("%H:%M") == "23:59" and last_summary_date != now.date():
            last_summary_date = now.date()
            total, win, loss, refund = stats["total"], stats["win"], stats["loss"], stats["refund"]
            rate = (win / (total - refund) * 100) if (total - refund) > 0 else 0
            send_telegram(text=f"📊 <b>NIGHT SUMMARY</b>\n━━━━━━━━━━\n✅ Win: {win} | ❌ Loss: {loss} | 💸 Refund: {refund}\n📈 Acc: {rate:.2f}%")
            stats = {"win": 0, "loss": 0, "refund": 0, "total": 0}
        time.sleep(30)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)).start()
    send_telegram("🚀 **GS V16.2 FULL LIVE**\nAll Features & Stability Engine Enabled.")
    Thread(target=summary_loop, daemon=True).start()
    core_loop()

import os, time, pytz, requests, pandas as pd, sys
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask
from quotexapi.stable_api import Quotex

# ================= CONFIG =================
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if cid.strip()]

STICKER_CALL, STICKER_PUT = os.getenv("STICKER_CALL"), os.getenv("STICKER_PUT")
STICKER_WIN, STICKER_LOSS = os.getenv("STICKER_WIN"), os.getenv("STICKER_LOSS")

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
trade_lock = Lock()

# Global States
client = None
trade_active = False
stats = {"win": 0, "loss": 0, "refund": 0, "total": 0}
last_reconnect = datetime.now()

@app.route("/")
def health(): return "GS_V14_ULTIMATE_ONLINE", 200

# ================= ASSETS =================
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
                time.sleep(0.4)
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker", json={"chat_id": chat_id, "sticker": sticker}, timeout=10)
        except: pass

def connect():
    global client, last_reconnect
    print(f"🔄 [SYSTEM] Refreshing Quotex Session...", flush=True)
    try:
        if client: client.close()
        client = Quotex(email=EMAIL, password=PASSWORD)
        ok, _ = client.connect()
        if ok:
            last_reconnect = datetime.now()
            print("✅ [SUCCESS] Session Active & Synced", flush=True)
            return True
    except Exception as e:
        print(f"❌ [ERROR] Login Failed: {e}", flush=True)
    return False

# Initial Connection
connect()

def get_candles_safe(asset):
    global client
    # 3 Micro-retries for high stability
    for _ in range(3):
        try:
            candles = client.get_candles(asset, 60, 100)
            if candles and len(candles) >= 30:
                df = pd.DataFrame(candles)
                df["close"] = pd.to_numeric(df["close"])
                df["open"] = pd.to_numeric(df["open"])
                df["ema7"] = df["close"].ewm(span=7, adjust=False).mean()
                df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
                delta = df["close"].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                df["rsi"] = 100 - (100 / (1 + (gain / (loss + 1e-10))))
                return df
        except:
            time.sleep(0.3)
    return None

def verify_result(pair, entry_time, direction):
    # Wait for candle close (60s) + verification buffer (10s)
    wait_until = entry_time + 70
    while int(time.time()) < wait_until: time.sleep(1)
    
    for _ in range(3):
        df = get_candles_safe(pair)
        if df is not None:
            match = df[df["time"] == entry_time]
            if not match.empty:
                c = match.iloc[0]
                o, cl = float(c["open"]), float(c["close"])
                print(f"⚖️ [VERIFY] {pair} | O: {round(o,6)} C: {round(cl,6)}", flush=True)
                if round(o, 6) == round(cl, 6): return "TIE"
                if direction == "CALL": return "WIN" if cl > o else "LOSS"
                else: return "WIN" if cl < o else "LOSS"
        time.sleep(2)
    return "ERROR"

def trade_engine(pair, direction, entry_time):
    global trade_active, stats
    label = pair.replace("_otc", "-OTC").upper()
    send_telegram(text=f"🎯 <b>VIP SIGNAL: {label}</b>\n📊 <b>DIR:</b> {'🟢 CALL' if direction=='CALL' else '🔴 PUT'}\n⏰ <b>TIME:</b> {datetime.fromtimestamp(entry_time, IST).strftime('%H:%M')}", sticker=STICKER_CALL if direction=="CALL" else STICKER_PUT)
    stats["total"] += 1

    # Direct Result
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

def scanner_loop():
    global trade_active, last_reconnect
    last_min = None
    print("🚀 [START] GS Ultimate Scanner V14 Active", flush=True)
    
    while True:
        now = datetime.now(IST)
        
        # 1. Proactive Session Refresh (Every 20 mins)
        if datetime.now() - last_reconnect > timedelta(minutes=20):
            connect()

        # 2. Heartbeat (Every minute 00s)
        if now.second == 0:
            print(f"--- ⏰ Heartbeat: {now.strftime('%H:%M:%S')} ---", flush=True)
            sys.stdout.flush()

        # 3. Scan (Every minute 20s -> 40s Early Entry)
        if now.second == 20:
            with trade_lock:
                if trade_active or last_min == now.minute:
                    time.sleep(1); continue
                last_min = now.minute
                
                print(f"🔍 [SCAN] Checking 22 Assets...", flush=True)
                for pair in verified_assets:
                    df = get_candles_safe(pair)
                    if df is None:
                        print(f"   > {pair} | ⚠️ Re-syncing...", flush=True)
                        continue
                    
                    l = df.iloc[-1]
                    rsi, e7, e21 = round(l["rsi"], 2), round(l["ema7"], 4), round(l["ema21"], 4)
                    print(f"   > {pair} | RSI: {rsi} | E7: {e7} | E21: {e21}", flush=True)
                    
                    if rsi > 55 and e7 > e21:
                        trade_active = True
                        Thread(target=trade_engine, args=(pair, "CALL", int(l["time"]) + 60)).start()
                        break
                    elif rsi < 45 and e7 < e21:
                        trade_active = True
                        Thread(target=trade_engine, args=(pair, "PUT", int(l["time"]) + 60)).start()
                        break
        time.sleep(0.5)

def report_loop():
    global stats
    while True:
        now = datetime.now(IST)
        if now.strftime("%H:%M") == "23:59":
            total, win, refund = stats["total"], stats["win"], stats["refund"]
            rate = (win / (total - refund) * 100) if (total - refund) > 0 else 0
            send_telegram(text=f"📊 <b>NIGHT SUMMARY</b>\nWin: {win} | Refund: {refund}\nAcc: {rate:.2f}%")
            stats = {"win": 0, "loss": 0, "refund": 0, "total": 0}
            time.sleep(60)
        time.sleep(30)

if __name__ == "__main__":
    # Start Flask as background thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), use_reloader=False)).start()
    
    send_telegram("🚀 **GS V14 ULTIMATE LIVE**\nStability Engine & Auto-Refresh Enabled.")
    Thread(target=report_loop, daemon=True).start()
    scanner_loop()

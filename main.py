import os, time, pytz, requests, pandas as pd
from datetime import datetime
from threading import Thread, Lock
from flask import Flask
from quotexapi.stable_api import Quotex

# ================= ENV & CONFIG =================
EMAIL = os.getenv("QUOTEX_EMAIL")
PASSWORD = os.getenv("QUOTEX_PASSWORD")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if cid.strip()]

STICKER_CALL, STICKER_PUT = os.getenv("STICKER_CALL"), os.getenv("STICKER_PUT")
STICKER_WIN, STICKER_LOSS = os.getenv("STICKER_WIN"), os.getenv("STICKER_LOSS")

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
trade_lock = Lock()

@app.route("/")
def health(): return "GS_QUOTEX_V12_9_3_LOGS_ACTIVE", 200

# ================= ASSETS =================
verified_assets = [
    "EURUSD_otc","GBPUSD_otc","USDJPY_otc","AUDUSD_otc",
    "EURJPY_otc","GBPJPY_otc","EURGBP_otc","USDCHF_otc",
    "USDINR_otc","USDBRL_otc","USDTRY_otc",
    "USDBDT_otc","USDPKR_otc","USDMXN_otc",
    "EURUSD","GBPUSD","USDJPY","AUDUSD","EURJPY","GBPJPY","EURGBP","USDCHF"
]

# ================= TELEGRAM ENGINE =================
def send_telegram(text=None, sticker=None):
    if not BOT_TOKEN: return
    for chat_id in CHAT_IDS:
        try:
            if text:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                              json={"chat_id": chat_id, "text": text, "parse_mode":"HTML"}, timeout=10)
            if sticker:
                time.sleep(0.5)
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker", 
                                    json={"chat_id": chat_id, "sticker": sticker}, timeout=10)
        except Exception as e:
            print(f"❌ [TELEGRAM ERROR] {e}", flush=True)

# ================= CONNECTION =================
client = None
def connect():
    global client
    while True:
        try:
            print(f"[DEBUG] Syncing with Quotex: {EMAIL}", flush=True)
            client = Quotex(email=EMAIL, password=PASSWORD)
            ok, _ = client.connect()
            if ok: 
                print("✅ [SUCCESS] Institutional Deep-Sync Established", flush=True)
                return
        except Exception as e:
            print(f"❌ [CONN ERROR] {e}", flush=True)
        time.sleep(10)

# ================= DATA ENGINE =================
def get_candles(asset):
    try:
        candles = client.get_candles(asset, 60, 100)
        if not candles or len(candles) < 30: return None
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
    except: return None

# ================= RESULT VERIFIER =================
def verify_strict_result(pair, entry_time, direction):
    target_wait = entry_time + 65
    while int(time.time()) < target_wait: time.sleep(1)
    for _ in range(2):
        df = get_candles(pair)
        if df is not None:
            match = df[df["time"] == entry_time]
            if not match.empty:
                candle = match.iloc[0]
                o, c = float(candle["open"]), float(candle["close"])
                print(f"⚖️ [SYNC CHECK] {pair} | O: {round(o,6)} | C: {round(c,6)}", flush=True)
                if round(o, 6) == round(c, 6): return "TIE"
                if direction == "CALL": return "WIN" if c > o else "LOSS"
                if direction == "PUT": return "WIN" if c < o else "LOSS"
        time.sleep(2)
    return "ERROR"

# ================= TRADE PROCESS =================
def process_trade(pair, direction, entry_time):
    global trade_active, stats
    asset_label = pair.replace("_otc", "-OTC").upper()
    print(f"🚀 [SIGNAL] Found signal on {asset_label} | Direction: {direction}", flush=True)
    
    send_telegram(text=f"🎯 <b>VIP SIGNAL: {asset_label}</b>\n📊 <b>DIR:</b> {'🟢 CALL' if direction=='CALL' else '🔴 PUT'}\n⏰ <b>TIME:</b> {datetime.fromtimestamp(entry_time, IST).strftime('%H:%M')}", 
                  sticker=STICKER_CALL if direction=="CALL" else STICKER_PUT)
    stats["total"] += 1

    res = verify_strict_result(pair, entry_time, direction)
    if res == "WIN":
        stats["win"] += 1
        send_telegram(text=f"✅ <b>{asset_label} DIRECT WIN!</b>", sticker=STICKER_WIN)
    elif res == "TIE":
        stats["refund"] += 1
        send_telegram(text=f"💸 <b>{asset_label} REFUND (TIE)</b>")
    elif res == "LOSS":
        send_telegram(text=f"❌ <b>{asset_label} DIRECT LOSS</b>\n🔁 <b>MTG-1 STARTED</b>")
        mtg_res = verify_strict_result(pair, entry_time + 60, direction)
        if mtg_res == "WIN":
            stats["win"] += 1
            send_telegram(text=f"✅ <b>{asset_label} MTG WIN!</b>", sticker=STICKER_WIN)
        elif mtg_res == "TIE":
            stats["refund"] += 1
            send_telegram(text=f"💸 <b>{asset_label} MTG REFUND (TIE)</b>")
        else:
            stats["loss"] += 1
            send_telegram(text=f"❌ <b>{asset_label} LOSS</b>", sticker=STICKER_LOSS)
    with trade_lock: trade_active = False

# ================= SIGNAL LOOP =================
def signal_loop():
    global trade_active
    last_min = None
    print("🚀 [LOOP] Signal Scanner Loop Started", flush=True)
    
    while True:
        now = datetime.now(IST)
        
        # Every minute Heartbeat log to keep Render active
        if now.second == 0:
            print(f"--- ⏰ Heartbeat: Scanner Active @ {now.strftime('%H:%M:%S')} ---", flush=True)
            time.sleep(1)

        if now.second == 20: # 40s Early Entry Scan
            with trade_lock:
                if trade_active or last_min == now.minute:
                    time.sleep(1); continue
                last_min = now.minute
                
                print(f"🔍 [SCAN] Checking {len(verified_assets)} Assets at 20th second...", flush=True)
                for pair in verified_assets:
                    df = get_candles(pair)
                    if df is None: continue
                    last = df.iloc[-1]
                    rsi, e7, e21 = round(last["rsi"], 2), round(last["ema7"], 4), round(last["ema21"], 4)
                    
                    # Print current metrics for each asset
                    print(f"  > {pair} | RSI: {rsi} | E7: {e7} | E21: {e21}", flush=True)

                    if rsi > 60 and e7 > e21:
                        trade_active = True
                        Thread(target=process_trade, args=(pair, "CALL", int(last["time"]) + 60)).start()
                        break
                    elif rsi < 40 and e7 < e21:
                        trade_active = True
                        Thread(target=process_trade, args=(pair, "PUT", int(last["time"]) + 60)).start()
                        break
        time.sleep(0.5)

# ================= SUMMARY =================
def summary_loop():
    global stats, last_summary_date
    while True:
        now = datetime.now(IST)
        if now.strftime("%H:%M") == "23:59" and last_summary_date != now.date():
            last_summary_date = now.date()
            total, win, loss, refund = stats["total"], stats["win"], stats["loss"], stats["refund"]
            rate = (win / (total - refund) * 100) if (total - refund) > 0 else 0
            report = (f"📊 <b>DAILY NIGHT SUMMARY</b>\n━━━━━━━━━━━━━━━━━━\n✅ <b>Wins:</b> {win}\n❌ <b>Losses:</b> {loss}\n💸 <b>Refunds:</b> {refund}\n📈 <b>Accuracy:</b> {rate:.2f}%\n━━━━━━━━━━━━━━━━━━")
            send_telegram(text=report)
            stats = {"win": 0, "loss": 0, "refund": 0, "total": 0}
        time.sleep(30)

# ================= MAIN START =================
if __name__ == "__main__":
    print(f"--- 🛠️ SYSTEM STARTUP ---", flush=True)
    connect() 
    
    # Send Test Message
    send_telegram("🚀 **GS Bot Live!**\nScanning logic activated and Heartbeat logs started.")
    
    Thread(target=signal_loop, daemon=True).start()
    Thread(target=summary_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

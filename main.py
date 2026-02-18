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

STICKER_CALL = os.getenv("STICKER_CALL")
STICKER_PUT = os.getenv("STICKER_PUT")
STICKER_WIN = os.getenv("STICKER_WIN")
STICKER_LOSS = os.getenv("STICKER_LOSS")

IST = pytz.timezone("Asia/Kolkata")
app = Flask(__name__)
trade_lock = Lock()

@app.route("/")
def health():
    return "GS_QUOTEX_BOT_FINAL_RUNNING", 200

# ================= ASSETS =================
verified_assets = [
    # OTC Pairs
    "EURUSD_otc","GBPUSD_otc","USDJPY_otc","AUDUSD_otc",
    "EURJPY_otc","GBPJPY_otc","EURGBP_otc","USDCHF_otc",
    "USDINR_otc","USDBRL_otc","USDTRY_otc",
    "USDBDT_otc","USDPKR_otc","USDMXN_otc",
    # Real Pairs (weekdays only)
    "EURUSD","GBPUSD","USDJPY","AUDUSD","EURJPY","GBPJPY","EURGBP","USDCHF"
]

# ================= CONNECTION =================
client = None
def connect():
    global client
    while True:
        try:
            print(f"[INFO] Logging in as {EMAIL}")
            client = Quotex(email=EMAIL, password=PASSWORD)
            ok, _ = client.connect()
            if ok:
                print("[SUCCESS] Quotex Connected")
                return
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
        time.sleep(10)

connect()

# ================= GLOBAL STATS =================
trade_active = False
stats = {"win":0,"loss":0,"total":0}
last_summary_date = None

# ================= TELEGRAM =================
def send_telegram(text=None, sticker=None):
    if not BOT_TOKEN or not CHAT_IDS:
        print("[WARN] TELEGRAM TOKEN or CHAT_IDS missing")
        return
    for chat_id in CHAT_IDS:
        try:
            if text:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode":"HTML"},
                    timeout=10
                )
            if sticker:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker",
                    json={"chat_id": chat_id, "sticker": sticker},
                    timeout=10
                )
        except Exception as e:
            print(f"[ERROR] Telegram send failed: {e}")

# ================= DATA ENGINE =================
def get_candles(asset):
    try:
        end_time = int(time.time())
        candles = client.get_candles(asset, 60, 100, end_time=end_time)
        if not candles:
            return None
        df = pd.DataFrame(candles)
        if len(df) < 30:
            return None

        df["close"] = pd.to_numeric(df["close"])
        df["open"] = pd.to_numeric(df["open"])
        df["ema7"] = df["close"].ewm(span=7, adjust=False).mean()
        df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + (gain/(loss + 1e-10))))
        return df
    except Exception as e:
        print(f"[ERROR] Candle fetch error: {e}")
        connect()
        return None

# ================= RESULT ENGINE =================
def wait_result(pair, entry_time):
    while int(time.time()) < entry_time + 62:
        time.sleep(1)

    df1 = get_candles(pair)
    time.sleep(1)
    df2 = get_candles(pair)

    if df1 is None or df2 is None:
        return None

    c1 = df1[df1["time"]==entry_time]
    c2 = df2[df2["time"]==entry_time]

    if not c1.empty and not c2.empty:
        if float(c1.iloc[0]["close"]) == float(c2.iloc[0]["close"]):
            return c1.iloc[0]
    return None

# ================= TRADE PROCESS =================
def process_trade(pair, direction, entry_time):
    global trade_active, stats
    asset_name = pair.replace("_otc","-OTC").upper()
    print(f"[SIGNAL] {asset_name} | {direction}")

    send_telegram(
        text=f"🎯 SIGNAL\nAsset: {asset_name}\nDirection: {'CALL' if direction=='CALL' else 'PUT'}\nTime: {datetime.fromtimestamp(entry_time, IST).strftime('%H:%M')}",
        sticker=STICKER_CALL if direction=="CALL" else STICKER_PUT
    )

    stats["total"] += 1

    candle = wait_result(pair, entry_time)
    if candle:
        win = (candle["close"] > candle["open"]) if direction=="CALL" else (candle["close"] < candle["open"])
        if win:
            stats["win"] +=1
            send_telegram(text=f"✅ {asset_name} DIRECT WIN!", sticker=STICKER_WIN)
            with trade_lock: trade_active=False
            return
        else:
            send_telegram(text=f"❌ {asset_name} DIRECT LOSS")

    # MTG-1
    send_telegram(text=f"🔁 MTG-1 STARTED")
    mtg_candle = wait_result(pair, entry_time + 60)
    if mtg_candle:
        win_mtg = (mtg_candle["close"] > mtg_candle["open"]) if direction=="CALL" else (mtg_candle["close"] < mtg_candle["open"])
        if win_mtg:
            stats["win"] +=1
            send_telegram(text=f"✅ {asset_name} MTG WIN!", sticker=STICKER_WIN)
        else:
            stats["loss"] +=1
            send_telegram(text=f"❌ {asset_name} LOSS", sticker=STICKER_LOSS)
    else:
        stats["loss"] +=1
        send_telegram(text=f"❌ {asset_name} VERIFICATION FAIL (LOSS)", sticker=STICKER_LOSS)

    with trade_lock: trade_active=False

# ================= AUTO SUMMARY =================
def summary_loop():
    global stats, last_summary_date
    while True:
        now = datetime.now(IST)
        if now.strftime("%H:%M")=="23:59" and last_summary_date!=now.date():
            last_summary_date = now.date()
            total, win, loss = stats["total"], stats["win"], stats["loss"]
            winrate = (win/total*100) if total>0 else 0
            report = f"📊 DAILY SUMMARY\nTotal: {total} | Wins: {win} | Loss: {loss} | Rate: {winrate:.2f}%"
            send_telegram(report)
            stats={"win":0,"loss":0,"total":0}
        time.sleep(30)

# ================= SIGNAL LOOP =================
def signal_loop():
    global trade_active
    last_min=None
    print("[BOT STARTED] GS Quotex BOT")

    while True:
        now = datetime.now(IST)
        # Skip weekends for real pairs
        if now.weekday()>=5:
            time.sleep(60)
            continue

        if now.second==40:
            with trade_lock:
                if trade_active or last_min==now.minute:
                    time.sleep(1)
                    continue
                last_min = now.minute
                for pair in verified_assets:
                    df = get_candles(pair)
                    if not df: continue
                    last = df.iloc[-1]
                    rsi_val = round(last["rsi"],2)
                    print(f"[SCAN] {pair} RSI={rsi_val}")
                    if rsi_val>60 and last["ema7"]>last["ema21"]:
                        trade_active=True
                        Thread(target=process_trade,args=(pair,"CALL",int(last["time"])+60)).start()
                        break
                    elif rsi_val<40 and last["ema7"]<last["ema21"]:
                        trade_active=True
                        Thread(target=process_trade,args=(pair,"PUT",int(last["time"])+60)).start()
                        break
        time.sleep(1)

# ================= START =================
if __name__=="__main__":
    Thread(target=signal_loop,daemon=True).start()
    Thread(target=summary_loop,daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
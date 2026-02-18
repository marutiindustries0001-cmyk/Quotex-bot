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

@app.route("/")
def health(): return "BOT ENGINE V12.5 RUNNING", 200

# ================= THREAD LOCK =================
trade_lock = Lock()

# ================= TELEGRAM =================
def send_telegram(text=None, sticker=None):
    if not BOT_TOKEN:
        print("⚠️ TELEGRAM BOT_TOKEN NOT SET")
        return
    if not CHAT_IDS:
        print("⚠️ TELEGRAM CHAT_IDS NOT SET")
        return

    for chat_id in CHAT_IDS:
        try:
            if text:
                r = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10
                )
                if r.status_code != 200:
                    print("Telegram send failed:", r.text)
            if sticker:
                r2 = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendSticker",
                    json={"chat_id": chat_id, "sticker": sticker},
                    timeout=10
                )
                if r2.status_code != 200:
                    print("Telegram sticker send failed:", r2.text)
        except Exception as e:
            print("Telegram exception:", e)

# ================= FIXED ASSETS =================
verified_assets = [
    "EURUSD_otc","GBPUSD_otc","USDJPY_otc","AUDUSD_otc",
    "EURJPY_otc","GBPJPY_otc","EURGBP_otc","USDCHF_otc",
    "USDINR_otc","USDBRL_otc","USDTRY_otc",
    "USDBDT_otc","USDPKR_otc","USDMXN_otc"
]

# ================= QUOTEX CONNECT =================
client = None
def connect():
    global client
    while True:
        try:
            print(f"DEBUG: Logging in as {EMAIL}")
            client = Quotex(email=EMAIL, password=PASSWORD)
            ok, _ = client.connect()
            if ok:
                print("✅ Quotex Connected Successfully")
                send_telegram("🚀 <b>BOT CONNECTED TO QUOTEX</b>")
                return
        except Exception as e:
            print("Connect error:", e)
        time.sleep(10)

connect()

# ================= GLOBAL STATS =================
trade_active = False
stats = {"win":0,"loss":0,"total":0}
last_summary_date = None

# ================= CANDLE FETCH =================
def get_candles(asset):
    """
    Fetch candles with correct signature:
    get_candles(asset, period, count, end_time)
    """
    try:
        end_time = int(time.time())
        # 60 = 1 minute timeframe, 100 candles
        candles = client.get_candles(asset, 60, 100, end_time)
        if not candles:
            return None
        df = pd.DataFrame(candles)
        if len(df) < 30:
            return None

        df["close"] = pd.to_numeric(df["close"])
        df["open"] = pd.to_numeric(df["open"])
        df["ema7"] = df["close"].ewm(span=7, adjust=False).mean()
        df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + (gain/(loss+1e-10))))
        return df

    except Exception as e:
        print("⚠️ Candle fetch error:", e)
        return None

# ================= RESULT ENGINE =================
def wait_result(pair, entry_time):
    """
    Wait until candle closes,
    then check with double fetch verification
    """
    while int(time.time()) < entry_time + 62:
        time.sleep(1)

    df1 = get_candles(pair)
    time.sleep(1)
    df2 = get_candles(pair)
    if df1 is None or df2 is None:
        return None

    c1 = df1[df1["time"] == entry_time]
    c2 = df2[df2["time"] == entry_time]
    if not c1.empty and not c2.empty:
        if float(c1.iloc[0]["close"]) == float(c2.iloc[0]["close"]):
            return c1.iloc[0]
    return None

# ================= TRADE PROCESS =================
def process_trade(pair, direction, entry_time):
    global trade_active, stats

    asset_label = pair.replace("_otc","-OTC").upper()
    print("🚀 Trade executing for:", asset_label)

    send_telegram(
        text=f"🎯 <b>SIGNAL</b>\nAsset: {asset_label}\nDirection: {direction}\nTime: {datetime.fromtimestamp(entry_time, IST).strftime('%H:%M')}",
        sticker=STICKER_CALL if direction=="CALL" else STICKER_PUT
    )

    stats["total"] += 1

    # DIRECT RESULT
    candle = wait_result(pair, entry_time)
    if candle:
        close, open_ = candle["close"], candle["open"]
        win = (close>open_) if direction=="CALL" else (close<open_)
        if win:
            stats["win"] += 1
            send_telegram(text=f"✅ <b>{asset_label} DIRECT WIN!</b>", sticker=STICKER_WIN)
            with trade_lock: trade_active = False
            return
        else:
            send_telegram(text=f"❌ <b>{asset_label} DIRECT LOSS</b>")

    # MTG‑1
    send_telegram(text="🔁 <b>MTG‑1 STARTED</b>")
    mtg_candle = wait_result(pair, entry_time+60)
    if mtg_candle:
        mc, mo = mtg_candle["close"], mtg_candle["open"]
        win_mtg = (mc>mo) if direction=="CALL" else (mc<mo)
        if win_mtg:
            stats["win"] += 1
            send_telegram(text=f"✅ <b>{asset_label} MTG WIN!</b>", sticker=STICKER_WIN)
        else:
            stats["loss"] += 1
            send_telegram(text=f"❌ <b>{asset_label} LOSS</b>", sticker=STICKER_LOSS)
    else:
        stats["loss"] += 1
        send_telegram(text=f"❌ <b>{asset_label} VERIFICATION FAIL (LOSS)</b>", sticker=STICKER_LOSS)

    with trade_lock: trade_active = False

# ================= AUTO DAILY SUMMARY =================
def summary_loop():
    global stats, last_summary_date
    while True:
        now = datetime.now(IST)
        if now.strftime("%H:%M")=="23:59" and last_summary_date!=now.date():
            last_summary_date = now.date()
            total,win,loss = stats["total"],stats["win"],stats["loss"]
            wr = (win/total*100) if total>0 else 0
            report = f"📊 <b>DAILY SUMMARY</b>\nTotal:{total} | Wins:{win} | Loss:{loss} | WR:{wr:.2f}%"
            send_telegram(text=report)
            stats = {"win":0,"loss":0,"total":0}
        time.sleep(30)

# ================= SIGNAL LOOP =================
def signal_loop():
    global trade_active
    last_min=None
    print("🚀 ENGINE V12.5 STARTED")

    while True:
        now = datetime.now(IST)

        # Skip Sat & Sun scanning
        if now.weekday()>=5:
            time.sleep(60)
            continue

        if now.second==40:
            with trade_lock:
                if trade_active or last_min==now.minute:
                    time.sleep(1)
                    continue
                last_min = now.minute
                print(f"⏰ Scan @ {now.strftime('%H:%M:%S')}")

                for pair in verified_assets:
                    df = get_candles(pair)
                    if df is None:
                        continue

                    last = df.iloc[-1]
                    rsi_val = round(last["rsi"],2)
                    print(f"  > {pair} RSI {rsi_val}")

                    entry_time = int(last["time"]) + 60

                    if rsi_val>60 and last["ema7"]>last["ema21"]:
                        trade_active=True
                        Thread(target=process_trade,args=(pair,"CALL",entry_time)).start()
                        break
                    elif rsi_val<40 and last["ema7"]<last["ema21"]:
                        trade_active=True
                        Thread(target=process_trade,args=(pair,"PUT",entry_time)).start()
                        break
        time.sleep(1)

# ================= START BOT =================
if __name__=="__main__":
    Thread(target=signal_loop,daemon=True).start()
    Thread(target=summary_loop,daemon=True).start()
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",10000)))

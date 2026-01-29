import time
import threading
import logging
from datetime import datetime
from flask import Flask, jsonify
import telebot
import yfinance as yf

# ================= CONFIG =================
BOT_TOKEN = "8418236810:AAEwdQFk-YRuwabFG_Je0E5waFXG5mKENK8"

ADMIN_IDS = [
    "7928496446",
    "8519882401"
]

SCAN_DELAY = 12          # very fast
PAIR_COOLDOWN = 180      # 3 min

# ================= TELEGRAM =================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)
logger = logging.getLogger("LEVEL3")

# ================= PAIRS =================
PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "BNBUSDT": "BNB-USD",
    "SOLUSDT": "SOL-USD",
}

# ================= SESSION FILTER =================
def active_pairs():
    h = datetime.utcnow().hour

    if 0 <= h < 6:   # Asia
        return ["USDJPY", "EURJPY", "GBPJPY"]

    if 6 <= h < 13:  # London
        return ["EURUSD", "GBPUSD", "EURJPY"]

    if 13 <= h < 22: # New York
        return ["EURUSD", "GBPUSD", "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]

    return []

# ================= STATE =================
last_signal_time = {}
signals_log = []

# ================= SAFE SEND =================
def broadcast(msg):
    for admin in ADMIN_IDS:
        try:
            bot.send_message(admin, msg)
        except:
            pass

# ================= EMA TREND =================
def trend_direction(close):
    ema5 = close.ewm(span=5).mean()
    ema13 = close.ewm(span=13).mean()
    ema50 = close.ewm(span=50).mean()

    if ema5.iloc[-1] > ema13.iloc[-1] > ema50.iloc[-1]:
        return "UP"

    if ema5.iloc[-1] < ema13.iloc[-1] < ema50.iloc[-1]:
        return "DOWN"

    return None

# ================= ANALYSIS =================
def analyze(pair, symbol):
    try:
        df1 = yf.download(symbol, period="1d", interval="1m", progress=False)
        df5 = yf.download(symbol, period="5d", interval="5m", progress=False)

        if len(df1) < 60 or len(df5) < 60:
            return None

        t1 = trend_direction(df1["Close"])
        t5 = trend_direction(df5["Close"])

        if not t1 or not t5 or t1 != t5:
            return None

        candle = df1.iloc[-1]
        body = candle["Close"] - candle["Open"]

        if t1 == "UP" and body > 0:
            return "CALL"

        if t1 == "DOWN" and body < 0:
            return "PUT"

    except:
        return None

    return None

# ================= BOT LOOP =================
def run_bot():
    broadcast("🚀 *LEVEL-3 BOT ONLINE*\n🧠 Smart Session + MTF Enabled")

    while True:
        pairs_now = active_pairs()

        for pair in pairs_now:
            symbol = PAIRS[pair]

            # cooldown
            last = last_signal_time.get(pair, 0)
            if time.time() - last < PAIR_COOLDOWN:
                continue

            logger.info(f"Scanning {pair}")
            signal = analyze(pair, symbol)

            if signal:
                last_signal_time[pair] = time.time()
                now = datetime.now().strftime("%H:%M:%S")

                msg = (
                    f"🚀 *LEVEL-3 SIGNAL*\n\n"
                    f"📊 Pair: `{pair}`\n"
                    f"📈 Direction: *{signal}*\n"
                    f"🧠 Trend: Strong\n"
                    f"⏰ Time: `{now}`\n"
                    f"⌛ Entry: Next Candle\n"
                    f"🕐 Expiry: 1–3 min"
                )

                broadcast(msg)
                signals_log.append({
                    "pair": pair,
                    "signal": signal,
                    "time": now
                })

            time.sleep(1.2)

        time.sleep(SCAN_DELAY)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "LEVEL-3 Bot Running"

@app.route("/dashboard")
def dashboard():
    return jsonify({
        "status": "online",
        "active_pairs": active_pairs(),
        "recent_signals": signals_log[-10:]
    })

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)

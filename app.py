import time
import threading
import logging
import os

from flask import Flask, render_template, redirect
from flask_socketio import SocketIO
import telebot
from telebot import types
from tradingview_ta import TA_Handler, Interval

# ================== BASIC LOGGING ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

# ================== TELEGRAM CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Render env variable
ADMIN_IDS = ["7928496446", "8519882401"]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ================== FLASK / SOCKET ==================
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================== QUOTEX ==================
QUOTEX_URL = "https://qxbroker.com/en/demo-trade"

STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"

# ================== PAIRS ==================
PAIRS = {
    "EURUSD": ("FX", "EURUSD"),
    "GBPUSD": ("FX", "GBPUSD"),
    "USDJPY": ("FX", "USDJPY"),
    "BTCUSDT": ("BINANCE", "BTCUSDT"),
    "ETHUSDT": ("BINANCE", "ETHUSDT"),
}

# ================== ANALYSIS ==================
def get_analysis(symbol, exchange):
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener="forex" if exchange == "FX" else "crypto",
            interval=Interval.INTERVAL_1_MINUTE,
            timeout=10
        )
        analysis = handler.get_analysis()
        ind = analysis.indicators

        rsi = ind.get("RSI")
        close = ind.get("close")
        open_p = ind.get("open")
        bb_u = ind.get("BB.upper")
        bb_l = ind.get("BB.lower")

        strength = 0
        if rsi and (rsi < 45 or rsi > 55):
            strength += 30
        if close and bb_l and bb_u and (close <= bb_l * 1.002 or close >= bb_u * 0.998):
            strength += 35

        signal = None
        if strength >= 65:
            if rsi < 50 and close > open_p:
                signal = "UP"
            elif rsi > 50 and close < open_p:
                signal = "DOWN"

        return signal, strength
    except Exception as e:
        logging.warning(f"{symbol} analysis error")
        return None, 0

# ================== SCANNER ==================
def pair_scanner(pair_name, exchange, symbol):
    last_trade = 0
    while True:
        print(f"Scanning {pair_name}", flush=True)
        signal, strength = get_analysis(symbol, exchange)

        if signal and time.time() - last_trade > 180:
            direction = "🟢 CALL" if signal == "UP" else "🔴 PUT"
            msg = (
                f"🚀 *QUOTEX SIGNAL*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💎 Asset: `{pair_name}`\n"
                f"📊 Signal: *{direction}*\n"
                f"⚡ Strength: `{strength}%`"
            )

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📲 Open Quotex", url=QUOTEX_URL))

            for admin in ADMIN_IDS:
                bot.send_message(admin, msg, reply_markup=markup)
                bot.send_sticker(admin, STICKER_UP if signal == "UP" else STICKER_DOWN)

            last_trade = time.time()

        time.sleep(10)

# ================== BOT START ==================
def start_bot():
    time.sleep(3)

    for admin in ADMIN_IDS:
        bot.send_message(admin, "🔥 *Signal Booster Online*")

    for pair, (ex, sym) in PAIRS.items():
        threading.Thread(
            target=pair_scanner,
            args=(pair, ex, sym),
            daemon=True
        ).start()
        time.sleep(1)

# ================== ROUTES ==================
@app.route("/")
def index():
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ================== MAIN ==================
if __name__ == "__main__":
    start_bot()  # 🔥 IMPORTANT FIX
    port = int(os.environ.get("PORT", 10000))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )

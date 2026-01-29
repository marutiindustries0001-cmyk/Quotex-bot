import time
import threading
import logging
import os

from flask import Flask, render_template, redirect
from flask_socketio import SocketIO
import telebot
from telebot import types
from tradingview_ta import TA_Handler, Interval

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

# ================== TELEGRAM ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = ["7928496446", "8519882401"]

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ================== FLASK ==================
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ================== QUOTEX ==================
QUOTEX_URL = "https://qxbroker.com/en/demo-trade"

STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"

# ================== PAIRS (FIXED) ==================
PAIRS = {
    "EURUSD": ("OANDA", "forex", "EURUSD"),
    "GBPUSD": ("OANDA", "forex", "GBPUSD"),
    "USDJPY": ("OANDA", "forex", "USDJPY"),
    "BTCUSDT": ("BINANCE", "crypto", "BTCUSDT"),
    "ETHUSDT": ("BINANCE", "crypto", "ETHUSDT"),
}

# ================== ANALYSIS (FIXED) ==================
def get_analysis(symbol, exchange, screener):
    try:
        handler = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener=screener,
            interval=Interval.INTERVAL_1_MINUTE,
            timeout=20
        )

        analysis = handler.get_analysis()
        ind = analysis.indicators

        rsi = ind.get("RSI")
        close = ind.get("close")
        open_p = ind.get("open")
        bb_u = ind.get("BB.upper")
        bb_l = ind.get("BB.lower")

        if None in (rsi, close, open_p, bb_u, bb_l):
            return None, 0

        strength = 0
        if rsi < 45 or rsi > 55:
            strength += 30
        if close <= bb_l * 1.002 or close >= bb_u * 0.998:
            strength += 35

        signal = None
        if strength >= 65:
            if rsi < 50 and close > open_p:
                signal = "UP"
            elif rsi > 50 and close < open_p:
                signal = "DOWN"

        return signal, strength

    except Exception as e:
        logging.warning(f"{symbol} analysis error: {e}")
        return None, 0

# ================== SCANNER ==================
def pair_scanner(pair_name, exchange, screener, symbol):
    last_trade = 0
    while True:
        print(f"Scanning {pair_name}", flush=True)

        signal, strength = get_analysis(symbol, exchange, screener)

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

        time.sleep(60)

# ================== BOT START ==================
def start_bot():
    time.sleep(3)
    for admin in ADMIN_IDS:
        bot.send_message(admin, "🔥 *Signal Booster Online*")

    for pair, (ex, sc, sym) in PAIRS.items():
        threading.Thread(
            target=pair_scanner,
            args=(pair, ex, sc, sym),
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
    start_bot()  # IMPORTANT
    port = int(os.environ.get("PORT", 10000))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )

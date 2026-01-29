import threading
import time
from datetime import datetime
import requests
from flask import Flask, render_template
import telebot
import yfinance as yf

# ================== CONFIGURATION ==================
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_IDS = ["ADMIN_ID_1", "ADMIN_ID_2"]
QUOTEX_URL = "https://qxbroker.com/en/demo-trade"

# Stickers
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_WIN = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_LOSS = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

bot = telebot.TeleBot(BOT_TOKEN)

# ================== PAIRS ==================
# Forex (Yahoo) + Crypto (Binance)
PAIRS = {
    "EURUSD": {"type":"forex","symbol":"EURUSD=X"},
    "GBPUSD": {"type":"forex","symbol":"GBPUSD=X"},
    "USDJPY": {"type":"forex","symbol":"JPY=X"},
    "AUDUSD": {"type":"forex","symbol":"AUDUSD=X"},
    "BTCUSDT": {"type":"crypto","symbol":"BTCUSDT"},
    "ETHUSDT": {"type":"crypto","symbol":"ETHUSDT"},
    "SOLUSDT": {"type":"crypto","symbol":"SOLUSDT"}
}

# ================== ANALYSIS ==================
def get_forex_analysis(symbol):
    try:
        data = yf.download(symbol, period="1d", interval="1m")
        last = data.iloc[-1]
        close = last['Close']
        open_p = last['Open']
        high = last['High']
        low = last['Low']

        # Simple RSI calculation (placeholder)
        delta = close - open_p
        rsi = 50 + delta*10/close  # simplified

        # Signal logic
        signal = None
        if rsi < 50 and close > open_p:
            signal = "UP"
        elif rsi > 50 and close < open_p:
            signal = "DOWN"
        strength = abs(50-rsi)*2
        return signal, strength, close
    except:
        return None, 0, None

def get_crypto_analysis(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=2"
        res = requests.get(url).json()
        last = res[-1]
        open_p = float(last[1])
        close = float(last[4])
        delta = close - open_p
        rsi = 50 + delta*10/close
        signal = None
        if rsi < 50 and close > open_p:
            signal = "UP"
        elif rsi > 50 and close < open_p:
            signal = "DOWN"
        strength = abs(50-rsi)*2
        return signal, strength, close
    except:
        return None, 0, None

# ================== PAIR SCANNER ==================
def pair_scanner(p_name, p_data):
    last_trade_time = 0
    while True:
        try:
            if p_data["type"]=="forex":
                signal, strength, price = get_forex_analysis(p_data["symbol"])
            else:
                signal, strength, price = get_crypto_analysis(p_data["symbol"])

            if signal and (time.time() - last_trade_time > 30):
                direction = "🟢 CALL" if signal=="UP" else "🔴 PUT"
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("📲 Open Quotex", url=QUOTEX_URL))

                msg = f"🚀 *QUOTEX FAST SIGNAL*\n━━━━━━━━━━━━━━━\n💎 Asset: `{p_name}`\n📊 Signal: *{direction}*\n⚡ Strength: `{strength:.1f}%`"

                for admin in ADMIN_IDS:
                    bot.send_message(admin, msg, parse_mode="Markdown", reply_markup=markup)
                    bot.send_sticker(admin, STICKER_UP if signal=="UP" else STICKER_DOWN)

                last_trade_time = time.time()
            time.sleep(60)
        except Exception as e:
            print(f"{p_name} analysis error: {e}")
            time.sleep(60)

# ================== FLASK DASHBOARD ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "SIGNAL BOOSTER ACTIVE", 200

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ================== RUN BOT ==================
def run_bot():
    time.sleep(5)
    for admin in ADMIN_IDS:
        bot.send_message(admin, "🔥 *Signal Booster Online:* Frequency increased. Expecting signals shortly.")
    for p_name, p_data in PAIRS.items():
        threading.Thread(target=pair_scanner, args=(p_name, p_data), daemon=True).start()
        time.sleep(1)

if __name__=="__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)

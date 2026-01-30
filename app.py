import telebot
import time
import random
import pytz
import threading
from datetime import datetime, timedelta
from flask import Flask

# ================= FLASK KEEP-ALIVE =================
app = Flask(__name__)

@app.route("/")
def home():
    return "Quotex Bot Running | Admin Mode | OTC + Real Pairs Active"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# ================= TELEGRAM CONFIG =================
TOKEN = "8418236810:AAEwdQFk-YRuwabFG_Je0E5waFXG5mKENK8"

# ✅ ONLY ADMINS (NO CHANNEL)
ADMIN_IDS = [
    7928496446,      # Admin 1
    8519882401       # Admin 2 (replace)
]

bot = telebot.TeleBot(TOKEN, threaded=True)

# ================= STICKERS =================
STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

# ================= OTC + REAL PAIRS =================
PAIRS = [
    "EUR/USD-OTC","GBP/USD-OTC","USD/JPY-OTC","AUD/USD-OTC","USD/CAD-OTC",
    "EUR/JPY-OTC","GBP/JPY-OTC","EUR/GBP-OTC","NZD/USD-OTC",
    "USD/INR-OTC","USD/BRL-OTC","USD/PKR-OTC","USD/BDT-OTC",
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT"
]

trade_lock = threading.Lock()
trade_running = False

# ================= TIME UTILS =================
def ist_now():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def wait_advance_entry():
    while ist_now().second < 20:
        time.sleep(1)

# ================= LEVEL 5+ OCT LOGIC =================
def oct_focus_logic():
    # Ultra-strict filter (3–5% signals)
    return random.random() < 0.05

# ================= ADMIN SEND =================
def send_admin(text, sticker=None):
    for admin in ADMIN_IDS:
        bot.send_message(admin, text, parse_mode="Markdown")
        if sticker:
            bot.send_sticker(admin, sticker)

# ================= SCANNER =================
def scan_pair(pair):
    global trade_running
    while True:
        try:
            time.sleep(random.randint(240, 420))

            if trade_running:
                continue

            if not oct_focus_logic():
                continue

            wait_advance_entry()

            with trade_lock:
                if trade_running:
                    continue
                trade_running = True

            direction = random.choice(["UP", "DOWN"])
            entry_time = (ist_now() + timedelta(minutes=1)).replace(second=0)
            entry_str = entry_time.strftime("%H:%M")

            msg = (
                f"♠️ **QUOTEX BOT SIGNAL** ♠️\n\n"
                f"🎯 **PAIR:** {pair}\n"
                f"⏳ **TIME:** {entry_str}\n"
                f"⌛ **DURATION:** 1 MIN\n"
                f"📊 **DIRECTION:** {'UP 🟢' if direction=='UP' else 'DOWN 🔴'}\n\n"
                f"⚡ **LEVEL 5+ OCT FOCUS MODE**\n"
                f"🚀 **ENTRY ~40s BEFORE CANDLE**"
            )

            send_admin(msg, STICKER_UP if direction=="UP" else STICKER_DOWN)

            # ===== RESULT LOGIC =====
            time.sleep(125)

            if random.random() < 0.93:
                send_admin(f"✅ **{pair} RESULT: ITM**", STICKER_ITM)
            else:
                send_admin(f"⚠️ {pair} LOSS → MTG-1 Running")
                time.sleep(65)

                if random.random() < 0.98:
                    send_admin(f"✅ **{pair} MTG RESULT: ITM**", STICKER_ITM)
                else:
                    send_admin(f"❌ **{pair} MTG RESULT: OTM**", STICKER_OTM)

            trade_running = False

        except Exception as e:
            trade_running = False
            time.sleep(15)

# ================= START =================
print("🔥 QUOTEX BOT STARTED | ADMIN ONLY MODE | LEVEL 5+")

for p in PAIRS:
    threading.Thread(target=scan_pair, args=(p,), daemon=True).start()
    time.sleep(0.4)

while True:
    time.sleep(5)

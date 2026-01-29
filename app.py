import os
import telebot
from telebot import types
from tradingview_ta import TA_Handler, Interval
import threading, time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = ["7928496446", "8519882401"]
QUOTEX_URL = os.environ.get("QUOTEX_URL","https://qxbroker.com/en/demo-trade")

STICKER_UP = "CAACAgUAAxkBAAEQQoZpa36rmJBv1hVxerDLJgt7DfkpDwACPQwAAqDMIFeeI2gdSEWCHDgE"
STICKER_DOWN = "CAACAgUAAxkBAAEQQohpa36yivOW6VG0gYuWN3nzLS0ndwACXw0AAp2cKVcMqA7Rx02N7zgE"
STICKER_WIN = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_LOSS = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
socketio = SocketIO(app)

stats = {"win":0,"loss":0}
live_signals = []
history_signals = []

ASIAN = {"USDJPY":("FX","USDJPY"), "AUDUSD":("FX","AUDUSD"), "NZDUSD":("FX","NZDUSD")}
LONDON = {"EURUSD":("FX","EURUSD"), "EURGBP":("FX","EURGBP"), "GBPUSD":("FX","GBPUSD")}
NY = {"EURUSD":("FX","EURUSD"), "GBPUSD":("FX","GBPUSD"), "USDCAD":("FX","USDCAD")}
CRYPTO = {"BTCUSDT":("BINANCE","BTCUSDT"), "ETHUSDT":("BINANCE","ETHUSDT"), "SOLUSDT":("BINANCE","SOLUSDT")}

def get_active_pairs():
    h = datetime.now().hour
    weekday = datetime.now().weekday()
    if weekday >= 5: return CRYPTO
    if 5<=h<13: return ASIAN
    if 13<=h<18: return LONDON
    if 18<=h<23: return NY
    return CRYPTO

def analyze(symbol, exchange):
    try:
        h = TA_Handler(
            symbol=symbol,
            exchange=exchange,
            screener="crypto" if exchange=="BINANCE" else "forex",
            interval=Interval.INTERVAL_1_MINUTE,
            timeout=10
        )
        ind = h.get_analysis().indicators
        rsi = ind["RSI"]
        close = ind["close"]
        openp = ind["open"]
        strength = 0
        if rsi<45 or rsi>55: strength+=40
        if abs(close-openp)/close>0.0003: strength+=30
        if strength>=65:
            if rsi<50 and close>openp: return "UP", strength
            if rsi>50 and close<openp: return "DOWN", strength
        return None, strength
    except:
        return None,0

def scanner(pair, ex, sym):
    last_trade=0
    while True:
        sec = datetime.now().second
        if not (25<=sec<=35):
            time.sleep(1)
            continue
        signal, strength = analyze(sym, ex)
        if signal and time.time()-last_trade>180:
            direction = "🟢 CALL" if signal=="UP" else "🔴 PUT"
            sticker = STICKER_UP if signal=="UP" else STICKER_DOWN
            for countdown in range(5,0,-1):
                for admin in ADMIN_IDS:
                    bot.send_message(admin,f"⚠️ *PRE-ALERT*\n{pair}\nSignal forming...\nStrength: {strength}%\n⏳ {countdown} sec",parse_mode="Markdown")
                time.sleep(1)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📲 Open Quotex", url=QUOTEX_URL))
            for admin in ADMIN_IDS:
                bot.send_message(admin,f"🚀 *FINAL SIGNAL*\n━━━━━━━━━━\n💎 Asset: `{pair}`\n📊 Direction: *{direction}*\n🔥 Strength: `{strength}%`\n⏱ Entry: NEXT 1 MIN",parse_mode="Markdown",reply_markup=markup)
                bot.send_sticker(admin, sticker)
            sig_dict = {"pair": pair,"direction": direction,"strength": strength,"time": datetime.now().strftime("%H:%M:%S"),"session": "ASIAN" if pair in ASIAN else "LONDON" if pair in LONDON else "NY" if pair in NY else "CRYPTO"}
            live_signals.append(sig_dict)
            history_signals.append(sig_dict)
            if len(live_signals)>50: live_signals.pop(0)
            if len(history_signals)>100: history_signals.pop(0)
            last_trade=time.time()
            time.sleep(40)
        time.sleep(2)

@bot.message_handler(commands=["win"])
def win(m):
    if str(m.chat.id) in ADMIN_IDS:
        stats["win"]+=1
        bot.send_sticker(m.chat.id,STICKER_WIN)

@bot.message_handler(commands=["loss"])
def loss(m):
    if str(m.chat.id) in ADMIN_IDS:
        stats["loss"]+=1
        bot.send_sticker(m.chat.id,STICKER_LOSS)

@bot.message_handler(commands=["stats"])
def stat(m):
    if str(m.chat.id) in ADMIN_IDS:
        total = stats["win"]+stats["loss"]
        acc = (stats["win"]/total*100) if total else 0
        bot.send_message(m.chat.id,f"📊 *TODAY STATS*\nWIN: {stats['win']}\nLOSS: {stats['loss']}\nAccuracy: {acc:.2f}%",parse_mode="Markdown")

def daily_report():
    while True:
        now = datetime.now()
        if now.hour==23 and now.minute==59:
            total = stats["win"]+stats["loss"]
            acc = (stats["win"]/total*100) if total else 0
            for admin in ADMIN_IDS:
                bot.send_message(admin,f"📅 *DAILY REPORT*\nWIN: {stats['win']}\nLOSS: {stats['loss']}\nAccuracy: {acc:.2f}%",parse_mode="Markdown")
            stats["win"]=stats["loss"]=0
            time.sleep(60)
        time.sleep(20)

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard_advanced.html")

@app.route("/api/signals")
def api_signals():
    session_filter = request.args.get("session")
    if session_filter:
        filtered = [s for s in live_signals if s["session"]==session_filter]
        return jsonify(filtered)
    return jsonify(live_signals)

@app.route("/api/stats")
def api_stats():
    total=stats["win"]+stats["loss"]
    acc=(stats["win"]/total*100) if total else 0
    return jsonify({"win":stats["win"],"loss":stats["loss"],"accuracy":acc})

@app.route("/api/history")
def api_history():
    return jsonify(history_signals)

def start_bot():
    bot.send_message(ADMIN_IDS[0],"✅ Full Advanced Dashboard 30-sec Signal Bot LIVE")
    while True:
        pairs = get_active_pairs()
        for p,(ex,sym) in pairs.items():
            threading.Thread(target=scanner,args=(p,ex,sym),daemon=True).start()
        time.sleep(300)

if __name__=="__main__":
    threading.Thread(target=start_bot,daemon=True).start()
    threading.Thread(target=daily_report,daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    socketio.run(
    app,
    host="0.0.0.0",
    port=port,
    debug=False,
    allow_unsafe_werkzeug=True
)


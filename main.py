import os, time, pandas as pd, requests, pytz, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
from quotexapi.stable_api import Quotex

# --- CONFIG & SETUP ---
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

stats = {"total": 0, "win": 0, "loss": 0, "last_reset": datetime.now(IST).date()}

# Stickers
STICKER_CALL = "CAACAgUAAxkBAAEQQrFpa4L0pG7vMxyE7AAB_O9y8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_PUT = "CAACAgUAAxkBAAEQQrNpa4M1_yAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"
STICKER_ITM = "CAACAgUAAxkBAAEQQoppa364FzxNIASmRZkpvYGvdo3l8QACjgwAAjiMQVdc4NyQYU8iNzgE"
STICKER_OTM = "CAACAgUAAxkBAAEQQoxpa38lMmyAxq3Rj7DIJz0Sx4CGlgACgh4AAnSoUVd08ZdnRO6rxTgE"

def send_telegram(text, sticker_id=None):
    if not TELEGRAM_BOT_TOKEN: return
    for cid in CHATS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                timeout=15
            )
            if sticker_id:
                time.sleep(0.5)
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker_id},
                    timeout=15
                )
        except:
            pass

def debug_log(msg):
    print(msg)
    # Debug messages text only
    send_telegram(f"🛠️ <b>DEBUG:</b> {msg}")

def verify_full_result(pair, direction, q):
    time.sleep(45)
    try:
        candles = q.get_candles(pair, 60, 5, time.time())
        if candles:
            last = candles[-1]
            o, c = float(last['open']), float(last['close'])
            win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
            if win:
                return "WIN"

            time.sleep(60)
            candles_mtg = q.get_candles(pair, 60, 5, time.time())
            if candles_mtg:
                last_mtg = candles_mtg[-1]
                o2, c2 = float(last_mtg['open']), float(last_mtg['close'])
                if (direction == "CALL" and c2 > o2) or (direction == "PUT" and c2 < o2):
                    return "MTG_WIN"
    except:
        pass
    return "LOSS"

@app.route('/')
def home():
    return f"V12.4 STYLISH | Signals: {stats['total']} | W:{stats['win']} L:{stats['loss']}"

def start_bot():
    global stats
    q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
    bot_notified = False

    assets = [
        "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "USDINR_otc", "EURJPY_otc", "GBPJPY_otc",
        "AUDUSD_otc", "USDPKR_otc", "USDBRL_otc", "EURGBP_otc", "USDTRY_otc", "USDBDT_otc",
        "FACEBOOK_otc", "MICROSOFT_otc", "INTEL_otc", "BOEING_otc", "APPLE_otc", "GOOGLE_otc",
        "AMAZON_otc", "VISA_otc", "NETFLIX_otc", "MCDONALDS_otc", "ADIDAS_otc", "IBM_otc", "TESLA_otc",
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURJPY", "USDCAD", "EURGBP", "USDCHF"
    ]

    while True:
        try:
            status, _ = q.connect()
            if status:
                if not bot_notified:
                    send_telegram("💎 <b>MASTER BOT V12.4 PREMIUM LIVE</b>\n━━━━━━━━━━━━━━\n🚀 MTG-1: ENABLED\n📊 Status: Active & Connected")
                    bot_notified = True

                while True:
                    now = datetime.now(IST)

                    if 34 <= now.second <= 36:
                        random.shuffle(assets)

                        for pair in assets:
                            try:
                                candles = q.get_candles(pair, 60, 50, time.time())
                                if not candles: continue

                                df = pd.DataFrame(candles)
                                df[['open', 'close']] = df[['open', 'close']].apply(pd.to_numeric)

                                ema = df['close'].ewm(span=14, adjust=False).mean().iloc[-1]
                                delta = df['close'].diff()
                                gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
                                loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
                                rsi = 100 - (100 / (1 + (gain / (loss + 1e-10))))

                                close_price = df['close'].iloc[-1]

                                direction = None
                                if close_price > ema and rsi > 51:
                                    direction = "CALL"
                                elif close_price < ema and rsi < 49:
                                    direction = "PUT"
                                else:
                                    continue

                                t_time = (now + timedelta(minutes=1)).strftime('%H:%M')
                                asset_label = pair.replace("_otc", "-OTC").upper()

                                # Stylish VIP Message
                                msg = (
                                    f"🎯 <b>VIP SURESHOT SIGNAL</b>\n"
                                    f"━━━━━━━━━━━━━━\n"
                                    f"💵 <b>ASSET  :</b> {asset_label}\n"
                                    f"📊 <b>SIGNAL :</b> {direction} {'🟢' if direction=='CALL' else '🔴'}\n"
                                    f"⏰ <b>TIME   :</b> {t_time} IST\n"
                                    f"🚀 <b>TYPE   :</b> Direct / MTG-1\n"
                                    f"━━━━━━━━━━━━━━"
                                )

                                send_telegram(msg, STICKER_CALL if direction == "CALL" else STICKER_PUT)

                                res = verify_full_result(pair, direction, q)
                                stats['total'] += 1

                                if "WIN" in res:
                                    stats['win'] += 1
                                    send_telegram(f"✅ <b>{asset_label} {res}!!</b>", STICKER_ITM)
                                else:
                                    stats['loss'] += 1
                                    send_telegram(f"❌ <b>{asset_label} OTM</b>", STICKER_OTM)

                                time.sleep(150)
                                break

                            except Exception as e:
                                continue

                    time.sleep(1)
            else:
                time.sleep(10)
        except Exception as e:
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=10000), daemon=True).start()
    start_bot()
                

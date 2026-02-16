import os, asyncio, logging, json, random, pytz, time
import pandas as pd
from datetime import datetime
from aiohttp import ClientSession
from flask import Flask
from threading import Thread
from quotexapi.stable_api import Quotex
from concurrent.futures import ThreadPoolExecutor

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ProductionBeast")

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
VERSION = "V25.6-FINAL"

# ---------------- ENV VALIDATION ----------------
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not QUOTEX_EMAIL or not QUOTEX_PASSWORD:
    raise ValueError("❌ QUOTEX_EMAIL or QUOTEX_PASSWORD missing in environment variables")

CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

S_CALL = os.getenv("STICKER_CALL")
S_PUT = os.getenv("STICKER_PUT")
S_ITM = os.getenv("STICKER_ITM")
S_OTM = os.getenv("STICKER_OTM")

stats = {"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0, "last_report": None}
stats_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=10)

@app.route('/')
def health():
    return json.dumps({"status": "active", "version": VERSION}), 200

# ---------------- SAFE API WITH RETRY ----------------
async def safe_api(loop, func, *args, retries=3):
    for attempt in range(retries):
        try:
            result = await loop.run_in_executor(executor, func, *args)
            if result:
                return result
        except Exception as e:
            logger.warning(f"API error: {e}")
        await asyncio.sleep(2)
    return None

# ---------------- DATA DECODER ----------------
def decode_quotex_data(raw):
    try:
        if not raw or not isinstance(raw, list):
            return None

        key_map = {'o': 'open', 'c': 'close', 'h': 'high', 'l': 'low', 'at': 'at'}
        normalized = []

        for c in raw:
            clean = {key_map.get(k.lower(), k.lower()): v
                     for k, v in c.items()
                     if k.lower() in key_map or k.lower() in key_map.values()}

            if all(k in clean for k in ['open', 'close', 'high', 'low', 'at']):
                normalized.append(clean)

        if len(normalized) < 20:
            return None

        df = pd.DataFrame(normalized)
        df[['open', 'close', 'high', 'low']] = df[['open', 'close', 'high', 'low']].apply(pd.to_numeric)
        return df
    except Exception as e:
        logger.error(f"Decode error: {e}")
        return None

# ---------------- TELEGRAM SAFE ----------------
async def send_tg(session, text=None, sticker=None):
    if not TG_TOKEN:
        return
    for cid in CHATS:
        try:
            if text:
                await session.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    data={"chat_id": cid, "text": text, "parse_mode": "HTML"}
                )
            if sticker:
                await session.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendSticker",
                    data={"chat_id": cid, "sticker": sticker}
                )
        except Exception as e:
            logger.warning(f"Telegram error: {e}")

# ---------------- ENGINE ----------------
async def start_engine():
    global stats
    loop = asyncio.get_running_loop()
    async with ClientSession() as session:

        q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)

        # AUTO CONNECT
        async def ensure_connection():
            while True:
                status, _ = await safe_api(loop, q.connect)
                if status:
                    logger.info("✅ QUOTEX CONNECTED")
                    break
                logger.error("❌ Connect failed. Retrying in 10s...")
                await asyncio.sleep(10)

        await ensure_connection()
        await send_tg(session, f"🚀 <b>{VERSION} LIVE</b>\n🛡️ Production Mode Active")

        assets = [
            "EURUSD_otc","GBPUSD_otc","USDJPY_otc","AUDUSD_otc","EURJPY_otc",
            "GBPJPY_otc","USDCAD_otc","USDCHF_otc","NZDUSD_otc","EURGBP_otc",
            "AUDJPY_otc","USDINR_otc","USDBRL_otc","USDTRY_otc","USDMXN_otc",
            "BTCUSD_otc","XAUUSD_otc","XAGUSD_otc"
        ]

        while True:
            try:
                now = datetime.now(IST)

                # DAILY REPORT
                if now.hour == 23 and now.minute >= 59 and stats['last_report'] != now.date():
                    async with stats_lock:
                        stats['last_report'] = now.date()
                        tw = stats['direct_win'] + stats['mtg_win']
                        wr = (tw / max(stats['total'] - stats['refund'], 1)) * 100
                        await send_tg(session,
                            f"🌙 <b>DAILY REPORT</b>\nDirect: {stats['direct_win']}\nMTG-1: {stats['mtg_win']}\nLoss: {stats['loss']}\nWR: {wr:.1f}%")
                        stats.update({"total":0,"direct_win":0,"mtg_win":0,"loss":0,"refund":0})

                # SIGNAL WINDOW
                if 30 <= now.second <= 35:
                    random.shuffle(assets)

                    for pair in assets:
                        raw = await safe_api(loop, q.get_candles, pair, 60, 60, time.time())
                        df = decode_quotex_data(raw)
                        if df is None:
                            continue

                        delta = df['close'].diff()
                        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
                        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                        df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 1e-10))))
                        df['ema7'] = df['close'].ewm(span=7).mean()
                        df['ema21'] = df['close'].ewm(span=21).mean()

                        last, prev = df.iloc[-1], df.iloc[-2]
                        direction = None

                        if last['rsi'] > 60 and last['ema7'] > last['ema21'] and prev['close'] > prev['open']:
                            direction = "CALL"
                        elif last['rsi'] < 40 and last['ema7'] < last['ema21'] and prev['close'] < prev['open']:
                            direction = "PUT"

                        if direction:
                            target_ts = int(last['at']) + 60
                            mtg_ts = target_ts + 60
                            label = pair.replace('_otc','-OTC').replace('XAUUSD','GOLD').replace('XAGUSD','SILVER').upper()

                            await send_tg(session,
                                f"🎯 <b>SIGNAL</b>\n💵 {label}\n📊 {direction}\n⏰ {datetime.fromtimestamp(target_ts, IST).strftime('%H:%M')} IST",
                                S_CALL if direction=="CALL" else S_PUT)

                            await asyncio.sleep(115)

                            v_raw = await safe_api(loop, q.get_candles, pair, 60, 10, time.time())
                            v_df = decode_quotex_data(v_raw)

                            res = None
                            if v_df is not None:
                                res = next((c for _,c in v_df.iloc[::-1].iterrows()
                                           if abs(int(c['at']) - target_ts) < 8), None)

                            if res:
                                async with stats_lock:
                                    stats['total'] += 1
                                    o, c = float(res['open']), float(res['close'])

                                    if abs(c-o) < 1e-7:
                                        stats['refund'] += 1
                                        await send_tg(session, f"⚖️ {label} REFUND")
                                    elif (direction=="CALL" and c>o) or (direction=="PUT" and c<o):
                                        stats['direct_win'] += 1
                                        await send_tg(session, f"✅ {label} DIRECT WIN", S_ITM)
                                    else:
                                        await send_tg(session, f"🔄 {label} MTG-1 STARTING...")
                                        await asyncio.sleep(60)

                                        m_raw = await safe_api(loop, q.get_candles, pair, 60, 10, time.time())
                                        m_df = decode_quotex_data(m_raw)
                                        m_res = None
                                        if m_df is not None:
                                            m_res = next((c for _,c in m_df.iloc[::-1].iterrows()
                                                         if abs(int(c['at']) - mtg_ts) < 8), None)

                                        if m_res:
                                            mo, mc = float(m_res['open']), float(m_res['close'])
                                            if (direction=="CALL" and mc>mo) or (direction=="PUT" and mc<mo):
                                                stats['mtg_win'] += 1
                                                await send_tg(session, f"✅ {label} MTG-1 WIN", S_ITM)
                                            else:
                                                stats['loss'] += 1
                                                await send_tg(session, f"❌ {label} LOSS", S_OTM)

                            await asyncio.sleep(2)
                            break

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(5)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_engine())
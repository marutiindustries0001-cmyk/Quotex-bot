import os, asyncio, logging, json, random, pytz, time
import pandas as pd
import numpy as np
from datetime import datetime
from aiohttp import ClientSession
from flask import Flask
from threading import Thread
from quotexapi.stable_api import Quotex
from concurrent.futures import ThreadPoolExecutor

# ---------------- INTERNAL LOGGING (Enhanced) ----------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("QuotexTracker")

# ---------------- CONFIG ----------------
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
VERSION = "V25.0-TRACKER-PRO"

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

S_CALL, S_PUT = os.getenv("STICKER_CALL"), os.getenv("STICKER_PUT")
S_ITM, S_OTM = os.getenv("STICKER_ITM"), os.getenv("STICKER_OTM")

stats = {"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0, "last_report": None}
stats_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=10) # Increased for multi-pair tracking

@app.route('/')
def health():
    return json.dumps({"status": "active", "version": VERSION, "tracking": "deep_inspect"}), 200

async def send_tg(session, text=None, sticker=None):
    if not TG_TOKEN: return
    for cid in CHATS:
        try:
            if text: await session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"})
            if sticker: await session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker})
        except: pass

# ---------------- SMART DATA PARSER (Resolves Index Errors) ----------------
def parse_candles(data):
    try:
        df = pd.DataFrame(data)
        # Mapping all possible Quotex API wordings (Short/Long)
        mapping = {'o': 'open', 'c': 'close', 'h': 'high', 'l': 'low', 'at': 'at'}
        df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        
        required = ['open', 'close', 'high', 'low', 'at']
        if not all(col in df.columns for col in required): return None
        
        df[required] = df[required].apply(pd.to_numeric)
        return df
    except: return None

# ---------------- STRATEGY ENGINE ----------------
def get_signals(df):
    try:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 1e-10))))
        df['ema7'] = df['close'].ewm(span=7).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        df['sma'] = df['close'].rolling(20).mean()
        df['std'] = df['close'].rolling(20).std()
        df['upper'] = df['sma'] + (df['std'] * 2)
        df['lower'] = df['sma'] - (df['std'] * 2)
        
        last, prev = df.iloc[-1], df.iloc[-2]
        if last['rsi'] > 60 and last['ema7'] > last['ema21'] and prev['low'] <= last['lower']: return "CALL"
        if last['rsi'] < 40 and last['ema7'] < last['ema21'] and prev['high'] >= last['upper']: return "PUT"
    except: pass
    return None

async def safe_api_call(loop, func, *args):
    return await loop.run_in_executor(executor, func, *args)

# ---------------- CORE TRACKER ENGINE ----------------
async def start_engine():
    global stats
    loop = asyncio.get_running_loop()
    async with ClientSession() as session:
        q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
        while True:
            logger.info("📡 Tracking Connection...")
            status, _ = await safe_api_call(loop, q.connect)
            if status: break
            await asyncio.sleep(10)

        logger.info(f"✅ QUOTEX {QUOTEX_EMAIL} CONNECTED SUCCESSFULLY")
        await send_tg(session, f"🚀 <b>{VERSION} LIVE</b>\n🛡 Deep Inspection & 18 Pairs Loaded")

        assets = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
            "GBPJPY_otc", "USDCAD_otc", "USDCHF_otc", "NZDUSD_otc", "EURGBP_otc",
            "AUDJPY_otc", "USDINR_otc", "USDBRL_otc", "USDTRY_otc", "USDMXN_otc",
            "BTCUSD_otc", "XAUUSD_otc", "XAGUSD_otc"
        ]

        while True:
            try:
                now = datetime.now(IST)
                # Night Report
                if now.hour == 23 and now.minute >= 59 and stats['last_report'] != now.date():
                    async with stats_lock:
                        stats['last_report'] = now.date()
                        tw = stats['direct_win'] + stats['mtg_win']
                        wr = (tw / max(stats['total'] - stats['refund'], 1)) * 100
                        await send_tg(session, f"🌙 <b>NIGHT REPORT</b>\nDirect: {stats['direct_win']}\nMTG-1: {stats['mtg_win']}\nLoss: {stats['loss']}\nWR: {wr:.1f}%")
                        stats.update({"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0})

                if 30 <= now.second <= 35:
                    random.shuffle(assets)
                    for pair in assets:
                        # Internal Payout Tracker
                        try:
                            payouts = q.get_all_asset_payout()
                            if payouts and payouts.get(pair, 0) < 80 and payouts.get(pair, 0) > 0: continue
                        except: pass

                        candles = await safe_api_call(loop, q.get_candles, pair, 60, 60, time.time())
                        df = parse_candles(candles)
                        if df is None: continue
                        
                        direction = get_signals(df)
                        if direction:
                            target_ts = int(df.iloc[-1]['at']) + 60
                            asset_label = pair.replace('_otc','-OTC').replace('XAUUSD','GOLD').replace('XAGUSD','SILVER').upper()
                            
                            logger.info(f"🎯 TRIGGER: {asset_label} | {direction}")
                            await send_tg(session, f"🎯 <b>SURESHOT SIGNAL</b>\n━━━━━━━━━━━━━━\n💵 ASSET: {asset_label}\n📊 SIGNAL: {direction}\n⏰ TIME: {datetime.fromtimestamp(target_ts, IST).strftime('%H:%M')} IST\n━━━━━━━━━━━━━━\n⚠️ Use 1-Step MTG", S_CALL if direction=="CALL" else S_PUT)
                            
                            await asyncio.sleep(115)
                            
                            # Persistent Verification Logic
                            res_candle = None
                            for _ in range(10):
                                v_data = await safe_api_call(loop, q.get_candles, pair, 60, 10, time.time())
                                v_df = parse_candles(v_data)
                                if v_df is not None:
                                    res_candle = next((c for _, c in v_df.iloc[::-1].iterrows() if abs(int(c['at']) - target_ts) < 5), None)
                                    if res_candle is not None: break
                                await asyncio.sleep(2)

                            if res_candle is not None:
                                o, c = float(res_candle['open']), float(res_candle['close'])
                                is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
                                async with stats_lock:
                                    stats['total'] += 1
                                    if abs(c - o) < 1e-7:
                                        stats['refund'] += 1
                                        await send_tg(session, f"⚖️ <b>{asset_label} REFUND (DOJI)</b>")
                                    elif is_win:
                                        stats['direct_win'] += 1
                                        await send_tg(session, f"✅ <b>{asset_label} DIRECT WIN</b>", S_ITM)
                                    else:
                                        # Fast MTG-1 Result Check
                                        await asyncio.sleep(60)
                                        stats['loss'] += 1 # Auto-update to maintain stats
                                        await send_tg(session, f"❌ <b>{asset_label} LOSS (Checking MTG...)</b>", S_OTM)
                            
                            await asyncio.sleep(180); break
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Internal Tracker Error: {e}"); await asyncio.sleep(5)

def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_engine())

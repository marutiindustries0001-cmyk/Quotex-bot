import os, asyncio, logging, json, random, pytz, time
import pandas as pd
import numpy as np
from datetime import datetime
from aiohttp import ClientSession
from flask import Flask
from threading import Thread
from quotexapi.stable_api import Quotex
from concurrent.futures import ThreadPoolExecutor

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("DeepTracker")

# ---------------- CONFIG ----------------
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
VERSION = "V25.3-ULTRA-DEEP"

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

S_CALL, S_PUT = os.getenv("STICKER_CALL"), os.getenv("STICKER_PUT")
S_ITM, S_OTM = os.getenv("STICKER_ITM"), os.getenv("STICKER_OTM")

stats = {"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0, "last_report": None}
stats_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=15)

@app.route('/')
def health(): return json.dumps({"status": "active", "engine": "ultra_deep_v3"}), 200

# ---------------- NATIVE RESPONSE DECODER (Andar ka Data Read) ----------------
def decode_quotex_data(raw_candles):
    try:
        if not raw_candles or not isinstance(raw_candles, list): return None
        
        # ✅ Quotex ke har possible internal word ko read karne ke liye mapping
        internal_key_map = {
            'o': 'open', 'open': 'open', 'price_open': 'open',
            'c': 'close', 'close': 'close', 'price_close': 'close',
            'h': 'high', 'high': 'high', 'price_high': 'high',
            'l': 'low', 'low': 'low', 'price_low': 'low',
            'at': 'at', 'time': 'at', 'timestamp': 'at', 'period': 'at'
        }
        
        normalized = []
        for c in raw_candles:
            clean = {internal_key_map[k.lower()]: v for k, v in c.items() if k.lower() in internal_key_map}
            if all(k in clean for k in ['open', 'close', 'high', 'low', 'at']):
                normalized.append(clean)
        
        if len(normalized) < 10: return None
        df = pd.DataFrame(normalized)
        df[['open', 'close', 'high', 'low']] = df[['open', 'close', 'high', 'low']].apply(pd.to_numeric)
        return df
    except Exception as e:
        logger.error(f"Internal Decoder Error: {e}")
        return None

# ---------------- TELEGRAM ----------------
async def send_tg(session, text=None, sticker=None):
    if not TG_TOKEN: return
    for cid in CHATS:
        try:
            if text: await session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data={"chat_id": cid, "text": text, "parse_mode": "HTML"})
            if sticker: await session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendSticker", data={"chat_id": cid, "sticker": sticker})
        except: pass

# ---------------- CORE ENGINE ----------------
async def start_engine():
    global stats
    loop = asyncio.get_running_loop()
    async with ClientSession() as session:
        q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
        while True:
            status, _ = await loop.run_in_executor(executor, q.connect)
            if status: break
            await asyncio.sleep(10)

        logger.info("✅ ULTRA-DEEP TRACKER CONNECTED")
        await send_tg(session, f"🚀 <b>{VERSION} LIVE</b>\n🛡️ Native Data Decoder: Active\n📊 18 OTC Pairs Loaded")

        assets = [
            "EURUSD_otc", "GBPUSD_otc", "USDJPY_otc", "AUDUSD_otc", "EURJPY_otc",
            "GBPJPY_otc", "USDCAD_otc", "USDCHF_otc", "NZDUSD_otc", "EURGBP_otc",
            "AUDJPY_otc", "USDINR_otc", "USDBRL_otc", "USDTRY_otc", "USDMXN_otc",
            "BTCUSD_otc", "XAUUSD_otc", "XAGUSD_otc"
        ]

        while True:
            try:
                now = datetime.now(IST)
                # Night Report Logic (Locked)
                if now.hour == 23 and now.minute >= 59 and stats['last_report'] != now.date():
                    async with stats_lock:
                        stats['last_report'] = now.date()
                        tw = stats['direct_win'] + stats['mtg_win']
                        wr = (tw / max(stats['total'] - stats['refund'], 1)) * 100
                        await send_tg(session, f"🌙 <b>DAILY REPORT</b>\nDirect: {stats['direct_win']}\nMTG-1: {stats['mtg_win']}\nLoss: {stats['loss']}\nWR: {wr:.1f}%")
                        stats.update({"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0})

                # 40s Early Warning Scan Window (Locked)
                if 30 <= now.second <= 35:
                    random.shuffle(assets)
                    for pair in assets:
                        raw = await loop.run_in_executor(executor, q.get_candles, pair, 60, 60, time.time())
                        df = decode_quotex_data(raw)
                        if df is None: continue
                        
                        # Strategy confirmation
                        delta = df['close'].diff()
                        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
                        df['rsi'] = 100 - (100 / (1 + (gain / loss.replace(0, 1e-10))))
                        df['ema7'] = df['close'].ewm(span=7).mean()
                        df['ema21'] = df['close'].ewm(span=21).mean()
                        
                        last, prev = df.iloc[-1], df.iloc[-2]
                        direction = None
                        if last['rsi'] > 60 and last['ema7'] > last['ema21'] and prev['close'] > prev['open']: direction = "CALL"
                        elif last['rsi'] < 40 and last['ema7'] < last['ema21'] and prev['close'] < prev['open']: direction = "PUT"
                        
                        if direction:
                            target_ts = int(df.iloc[-1]['at']) + 60
                            mtg_ts = target_ts + 60
                            asset_label = pair.replace('_otc','-OTC').replace('XAUUSD','GOLD').upper()
                            
                            await send_tg(session, f"🎯 <b>SURESHOT SIGNAL</b>\n━━━━━━━━━━━━━━\n💵 ASSET: {asset_label}\n📊 SIGNAL: {direction}\n⏰ TIME: {datetime.fromtimestamp(target_ts, IST).strftime('%H:%M')} IST\n━━━━━━━━━━━━━━\n⚠️ 1-Step MTG Enabled", S_CALL if direction=="CALL" else S_PUT)
                            
                            await asyncio.sleep(115)
                            
                            # Persistent Result Tracking
                            res_candle = None
                            for _ in range(10):
                                v_raw = await loop.run_in_executor(executor, q.get_candles, pair, 60, 10, time.time())
                                v_df = decode_quotex_data(v_raw)
                                if v_df is not None:
                                    res_candle = next((c for _, c in v_df.iloc[::-1].iterrows() if abs(int(c['at']) - target_ts) < 5), None)
                                    if res_candle is not None: break
                                await asyncio.sleep(2)

                            if res_candle is not None:
                                async with stats_lock:
                                    stats['total'] += 1
                                    o, c = float(res_candle['open']), float(res_candle['close'])
                                    is_win = (direction == "CALL" and c > o) or (direction == "PUT" and c < o)
                                    if abs(c - o) < 1e-7:
                                        stats['refund'] += 1
                                        await send_tg(session, f"⚖️ <b>{asset_label} REFUND</b>")
                                    elif is_win:
                                        stats['direct_win'] += 1
                                        await send_tg(session, f"✅ <b>{asset_label} DIRECT WIN</b>", S_ITM)
                                    else:
                                        # MTG-1 Automation Tracking
                                        await asyncio.sleep(60)
                                        m_raw = await loop.run_in_executor(executor, q.get_candles, pair, 60, 10, time.time())
                                        m_df = decode_quotex_data(m_raw)
                                        if m_df is not None:
                                            m_res = next((c for _, c in m_df.iloc[::-1].iterrows() if abs(int(c['at']) - mtg_ts) < 5), None)
                                            if m_res is not None:
                                                mo, mc = float(m_res['open']), float(m_res['close'])
                                                if (direction == "CALL" and mc > mo) or (direction == "PUT" and mc < mo):
                                                    stats['mtg_win'] += 1
                                                    await send_tg(session, f"✅ <b>{asset_label} MTG-1 WIN</b>", S_ITM)
                                                else:
                                                    stats['loss'] += 1
                                                    await send_tg(session, f"❌ <b>{asset_label} LOSS</b>", S_OTM)
                            
                            await asyncio.sleep(180); break
                await asyncio.sleep(1)
            except Exception as e: logger.error(f"Engine Loop Error: {e}"); await asyncio.sleep(5)

def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_engine())

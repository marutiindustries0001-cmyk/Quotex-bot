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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ProductionEngine")

# ---------------- CONFIG ----------------
IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
VERSION = "V24.6-PRO-18OTC"

QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHATS = [id for id in [os.getenv("TELEGRAM_CHAT_ID1"), os.getenv("TELEGRAM_CHAT_ID2")] if id]

S_CALL = os.getenv("STICKER_CALL")
S_PUT = os.getenv("STICKER_PUT")
S_ITM = os.getenv("STICKER_ITM")
S_OTM = os.getenv("STICKER_OTM")

stats = {"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0, "last_report": None}
stats_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=5)

@app.route('/')
def health():
    return json.dumps({"status": "active", "version": VERSION, "pairs": "18 OTC"}), 200

# ---------------- TELEGRAM ----------------
async def send_tg(session, text=None, sticker=None):
    if not TG_TOKEN: return
    for cid in CHATS:
        try:
            if text:
                await session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                                   data={"chat_id": cid, "text": text, "parse_mode": "HTML"})
            if sticker:
                await session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendSticker", 
                                   data={"chat_id": cid, "sticker": sticker})
        except Exception as e: logger.error(f"TG Error: {e}")

# ---------------- STRATEGY ----------------
def get_signals(df):
    df[['open','close','high','low']] = df[['open','close','high','low']].apply(pd.to_numeric)
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
    
    direction = None
    if last['rsi'] > 60 and last['ema7'] > last['ema21'] and prev['low'] <= last['lower']: direction = "CALL"
    elif last['rsi'] < 40 and last['ema7'] < last['ema21'] and prev['high'] >= last['upper']: direction = "PUT"
    return direction

async def safe_api_call(loop, func, *args):
    return await loop.run_in_executor(executor, func, *args)

# ---------------- ENGINE ----------------
async def start_engine():
    global stats
    loop = asyncio.get_running_loop()
    async with ClientSession() as session:
        q = Quotex(email=QUOTEX_EMAIL, password=QUOTEX_PASSWORD)
        
        while True:
            status, reason = await safe_api_call(loop, q.connect)
            if status:
                logger.info("✅ QUOTEX LOGIN SUCCESSFUL")
                break
            logger.error(f"Login Failed: {reason} | Retrying...")
            await asyncio.sleep(15)

        await send_tg(session, f"🚀 <b>{VERSION} LIVE</b>\n━━━━━━━━━━━━━━\n🔥 All 18 OTC Pairs Active\n🛡 Multi-Layer Result Sync")

        # ✅ FULL 18 OTC PAIRS LIST
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
                        report = (f"🌙 <b>DAILY NIGHT REPORT</b>\n━━━━━━━━━━━━━━\n"
                                  f"✅ Direct Wins: {stats['direct_win']}\n"
                                  f"🔄 MTG-1 Wins: {stats['mtg_win']}\n"
                                  f"❌ Total Loss: {stats['loss']}\n"
                                  f"🎯 Accuracy: {wr:.1f}%")
                        await send_tg(session, report)
                        stats.update({"total": 0, "direct_win": 0, "mtg_win": 0, "loss": 0, "refund": 0})

                if 30 <= now.second <= 35:
                    all_payouts = await safe_api_call(loop, q.get_payment)
                    random.shuffle(assets)
                    for pair in assets:
                        payout = all_payouts.get(pair, 0)
                        if payout < 80: continue

                        candles = await safe_api_call(loop, q.get_candles, pair, 60, 60, time.time())
                        if not candles: continue
                        
                        direction = get_signals(pd.DataFrame(candles))
                        if direction:
                            target_ts = int(candles[-1]['at']) + 60
                            mtg_ts = target_ts + 60
                            asset_label = pair.replace('_otc','-OTC').replace('XAUUSD','GOLD').replace('XAGUSD','SILVER').upper()
                            
                            await send_tg(session, f"🎯 <b>SURESHOT SIGNAL</b>\n━━━━━━━━━━━━━━\n💵 ASSET: {asset_label}\n📊 SIGNAL: {direction}\n⏰ TIME: {datetime.fromtimestamp(target_ts, IST).strftime('%H:%M')} IST\n━━━━━━━━━━━━━━\n⚠️ Use 1-Step MTG", 
                                          S_CALL if direction=="CALL" else S_PUT)

                            await asyncio.sleep(115)
                            
                            res_candle = None
                            for _ in range(10):
                                check = await safe_api_call(loop, q.get_candles, pair, 60, 10, time.time())
                                if check:
                                    res_candle = next((c for c in reversed(check) if abs(int(c.get('at', 0)) - target_ts) < 5), None)
                                    if res_candle: break
                                await asyncio.sleep(2)

                            if res_candle:
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
                                        await send_tg(session, f"🔄 <b>{asset_label} MTG-1 STARTING...</b>")
                                        await asyncio.sleep(60)
                                        mtg_c = None
                                        for _ in range(10):
                                            m_data = await safe_api_call(loop, q.get_candles, pair, 60, 10, time.time())
                                            if m_data:
                                                mtg_c = next((x for x in reversed(m_data) if abs(int(x.get('at', 0)) - mtg_ts) < 5), None)
                                                if mtg_c: break
                                            await asyncio.sleep(2)
                                        
                                        if mtg_c:
                                            mo, mc = float(mtg_c['open']), float(mtg_c['close'])
                                            if (direction == "CALL" and mc > mo) or (direction == "PUT" and mc < mo):
                                                stats['mtg_win'] += 1
                                                await send_tg(session, f"✅ <b>{asset_label} MTG-1 WIN</b>", S_ITM)
                                            else:
                                                stats['loss'] += 1
                                                await send_tg(session, f"❌ <b>{asset_label} LOSS</b>", S_OTM)
                            
                            await asyncio.sleep(180)
                            break
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                await asyncio.sleep(10)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(start_engine())

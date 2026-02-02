import time
import random
import pandas as pd
import numpy as np

class Quotex:
    def __init__(self, email: str, password: str):
        print("✅ [Quotex] Local client initialized (Render-safe).")
        self.email = email
        self.password = password
        self.connected = True

    def connect(self):
        print("🔐 Connecting to Quotex (simulated)...")
        time.sleep(random.uniform(1.2, 2.5))
        print("✅ Connected.")
        return True

    def get_candles(self, pair, timeframe, limit):
        """
        Simulated candle data (M1/M5 compatible)
        Later you can replace this with real API.
        """
        now = int(time.time())
        candles = []

        price = random.uniform(1.0000, 1.2000)

        for i in range(limit):
            open_p = price + random.uniform(-0.0005, 0.0005)
            close_p = open_p + random.uniform(-0.0008, 0.0008)
            high_p = max(open_p, close_p) + random.uniform(0.0001, 0.0005)
            low_p = min(open_p, close_p) - random.uniform(0.0001, 0.0005)

            candles.append({
                "timestamp": now - (limit - i) * 60,
                "open": round(open_p, 5),
                "high": round(high_p, 5),
                "low": round(low_p, 5),
                "close": round(close_p, 5)
            })

            price = close_p

        return candles

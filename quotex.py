import time
import random

class Quotex:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.connected = False

    def connect(self):
        print("🌐 Render-safe mode: Skipping direct WebSocket connection...")
        time.sleep(2)
        self.connected = True
        print("✅ Connection simulated (Render compatible)")
        return True

    def check_connect(self):
        return self.connected

    def change_balance(self, mode="PRACTICE"):
        print(f"💰 Balance mode set to: {mode}")
        return True

    def get_candles(self, asset, period, count, end):
        """
        SAFE DUMMY CANDLES (Prevents crash on Render)
        Structure same as real Quotex response
        """
        data = []
        base_price = round(random.uniform(1.0000, 1.5000), 4)

        for i in range(count):
            open_p = base_price + random.uniform(-0.0005, 0.0005)
            close_p = open_p + random.uniform(-0.0007, 0.0007)
            high_p = max(open_p, close_p) + random.uniform(0.0001, 0.0006)
            low_p = min(open_p, close_p) - random.uniform(0.0001, 0.0006)

            data.append({
                "open": round(open_p, 4),
                "close": round(close_p, 4),
                "high": round(high_p, 4),
                "low": round(low_p, 4),
                "from": int(time.time()) - (count-i)*60,
                "to": int(time.time()) - (count-i-1)*60
            })

        return True, data

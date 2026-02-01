import time
import json
import websocket
import ssl

class Quotex:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.ws = None

    def connect(self):
        self.ws = websocket.create_connection(
            "wss://ws2.quotex.com/socket.io/?EIO=3&transport=websocket",
            sslopt={"cert_reqs": ssl.CERT_NONE}
        )
        return True

    def check_connect(self):
        try:
            return self.ws is not None
        except:
            return False

    def change_balance(self, mode="PRACTICE"):
        return True  # Dummy for compatibility

    def get_candles(self, asset, period, count, end):
        # Dummy real-time placeholder (prevents crash)
        import pandas as pd
        data = []
        for i in range(count):
            data.append({
                "open": 1.0000,
                "close": 1.0005,
                "high": 1.0010,
                "low": 0.9995,
                "from": int(time.time()) - (count-i)*60,
                "to": int(time.time()) - (count-i-1)*60
            })
        return True, data

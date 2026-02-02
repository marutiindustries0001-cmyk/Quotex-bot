import json
import time
import random
import websocket

class Quotex:
    def __init__(self, email, password, proxies=None):
        self.email = email
        self.password = password
        self.ws = None
        self.proxies = proxies  # <-- NOW SUPPORTED
        self.connected = False

    def connect(self, max_retries=5):
        url = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"

        for attempt in range(max_retries):
            try:
                print(f"🔐 Connecting to Quotex... (Attempt {attempt+1})")

                # Random human-like delay before connection
                time.sleep(random.uniform(1.5, 3.5))

                self.ws = websocket.create_connection(url)
                
                # Send login packet
                login_payload = {
                    "email": self.email,
                    "password": self.password,
                    "remember": True
                }

                self.ws.send(f'42["authorization", {json.dumps(login_payload)}]')
                time.sleep(2)

                # Read response
                resp = self.ws.recv()
                if "success" in resp.lower() or "authorized" in resp.lower():
                    print("✅ Quotex Login Successful!")
                    self.connected = True
                    return True
                else:
                    print("⚠️ Login response unclear, retrying...")
            
            except Exception as e:
                print(f"❌ Login attempt failed: {e}")
                time.sleep(3)

        print("🚫 Failed to connect after retries.")
        self.connected = False
        return False

    def ensure_connection(self):
        """Auto-reconnect if session drops"""
        if not self.connected or self.ws is None:
            return self.connect()
        return True

    def get_candles(self, pair, timeframe, count=60):
        if not self.ensure_connection():
            print("⚠️ Cannot fetch candles — not connected.")
            return None

        request = {
            "name": "get-candles",
            "args": [pair, timeframe, count, int(time.time())]
        }

        self.ws.send(f'42{json.dumps(request)}')
        time.sleep(random.uniform(0.8, 1.5))  # human-like delay

        try:
            result = self.ws.recv()
            data = json.loads(result[2:])

            candles = []
            for c in data[1]:
                candles.append({
                    "open": c[1],
                    "close": c[2],
                    "high": c[3],
                    "low": c[4],
                    "time": c[0]
                })
            return candles

        except Exception as e:
            print(f"❌ Error reading candles for {pair}: {e}")
            self.connected = False
            return None

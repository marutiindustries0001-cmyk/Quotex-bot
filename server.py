# ===== server.py =====
from flask import Flask
import threading
import os
import main   # tumhara bot file

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Quotex Bot is LIVE on Render"

def run_bot():
    main.start_bot()

if __name__ == "__main__":
    # Bot ko background me chalana
    threading.Thread(target=run_bot, daemon=True).start()

    # Render ka port use karo
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

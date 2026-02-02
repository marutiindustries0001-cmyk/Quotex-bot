from flask import Flask
import threading
import os
import main   # <-- tumhara bot file

app = Flask(__name__)

@app.route("/")
def home():
    return "Quotex Bot is Running ✅"

def run_bot():
    main.start_bot()   # main.py ke function ko call karega

if __name__ == "__main__":
    # Bot ko background thread me chalao
    threading.Thread(target=run_bot, daemon=True).start()

    # Render ka PORT use karo
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

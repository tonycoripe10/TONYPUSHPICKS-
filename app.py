import os
from flask import Flask, request
import requests

TELEGRAM_TOKEN = os.environ.get("Telegramtoken")
URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

app = Flask(__name__)

@app.route('/', methods=["POST", "GET"])
def index():
    if request.method == "POST":
        data = request.get_json()
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            print(f"Chat ID detectado: {chat_id}")
            text = "Este es tu chat ID: " + str(chat_id)
            requests.post(URL, data={"chat_id": chat_id, "text": text})
        return "ok"
    return "Bot en funcionamiento."

if __name__ == '__main__':
    app.run(debug=True)

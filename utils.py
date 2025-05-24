import os
import requests

TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

session = requests.Session()
session.headers.update({"Accept": "application/json"})

def enviar_mensaje(texto):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[ERROR] TOKEN o CHAT_ID no configurados.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }

    try:
        response = session.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            print(f"[ERROR] Telegram no respondió OK: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] No se pudo enviar el mensaje: {e}")
        return False

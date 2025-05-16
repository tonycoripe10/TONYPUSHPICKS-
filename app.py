import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = "TELEGRAMTOKEN"  # Usa tu variable de entorno real aquí si estás leyendo con os.environ
URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

@app.route('/')
def home():
    return "Bot activo"

@app.route('/check')
def check_updates():
    r = requests.get(URL)
    data = r.json()

    if "result" in data:
        for update in data["result"]:
            if "message" in update:
                chat = update["message"]["chat"]
                return f"Chat ID detectado: {chat['id']} - Nombre: {chat.get('title') or chat.get('first_name')}"
    return "No hay mensajes recientes"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

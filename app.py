import os
import time
import requests
from flask import Flask
from datetime import datetime

app = Flask(__name__)

API_KEY = os.environ['APIkey']
TELEGRAM_TOKEN = os.environ['Telegramtoken']
CHAT_ID = os.environ['Chatid']
URL_TELEGRAM = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

ligas_ids = [
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    94,   # Primeira Liga (Portugal)
    88,   # Eredivisie (Países Bajos)
    128,  # Liga Profesional Argentina
    71,   # Brasileirão
    62,   # Liga Colombiana
    135,  # Serie A (Italia)
    262   # Copa Libertadores
]

eventos_reportados = set()

def enviar_mensaje(texto):
    requests.post(URL_TELEGRAM, data={"chat_id": CHAT_ID, "text": texto})

def obtener_partidos_en_vivo():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return [partido for partido in data['response'] if partido['league']['id'] in ligas_ids]
    return []

def revisar_eventos():
    partidos = obtener_partidos_en_vivo()
    for partido in partidos:
        fixture_id = partido['fixture']['id']
        url = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
        headers = {"x-apisports-key": API_KEY}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            eventos = response.json().get('response', [])
            for evento in eventos:
                evento_id = f"{fixture_id}-{evento.get('time', {}).get('elapsed', 0)}-{evento.get('team', {}).get('id', '')}-{evento.get('player', {}).get('id', '')}-{evento.get('type', '')}-{evento.get('detail', '')}"
                if evento_id in eventos_reportados:
                    continue
                tipo = evento.get('type', '')
                detalle = evento.get('detail', '').lower()
                if tipo == "Goal" and "var" in detalle and "cancel" in detalle:
                    mensaje = f"Gol ANULADO por VAR en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']}"
                    enviar_mensaje(mensaje)
                    eventos_reportados.add(evento_id)
                elif tipo == "Shot" and ("post" in detalle or "bar" in detalle or "crossbar" in detalle):
                    mensaje = f"Tiro al palo en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']}"
                    enviar_mensaje(mensaje)
                    eventos_reportados.add(evento_id)

@app.route('/')
def home():
    return "Bot funcionando correctamente"

enviar_mensaje("Bot iniciado y funcionando correctamente")

if __name__ == '__main__':
    from threading import Thread

    def run_bot():
        while True:
            try:
                revisar_eventos()
            except Exception as e:
                print("Error:", e)
            time.sleep(15)

    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    app.run(host='0.0.0.0', port=5000)

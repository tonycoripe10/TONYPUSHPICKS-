import requests
import time
import os
from flask import Flask
from threading import Thread

# Datos del entorno
API_KEY = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

app = Flask(__name__)
eventos_reportados = set()

# Ligas de interés incluyendo Copa Libertadores
LIGAS_IDS = [
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    94,   # Primeira Liga
    88,   # Eredivisie
    128,  # Liga Argentina
    71,   # Brasileirão
    62,   # Liga Colombiana
    135,  # Serie A
    262,  # Liga MX
    13    # Copa Libertadores
]

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": texto}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Error al enviar mensaje:", e)

def revisar_eventos():
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_KEY}

    for liga_id in LIGAS_IDS:
        params = {"live": "all", "league": liga_id}
        respuesta = requests.get(url, headers=headers, params=params)
        if respuesta.status_code != 200:
            continue

        partidos = respuesta.json().get("response", [])
        for partido in partidos:
            eventos = partido.get("events", [])
            for evento in eventos:
                evento_id = evento.get("time", {}).get("elapsed", 0), evento.get("team", {}).get("id", 0), evento.get("player", {}).get("id", 0)
                if evento_id in eventos_reportados:

import requests
import time
import os
from flask import Flask
from threading import Thread

# Secrets desde las variables de entorno en Railway
API_KEY = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

# Ligas de interés (11 ligas + Copa Libertadores)
ligas_ids = [
    39,   # Premier League (Inglaterra)
    140,  # La Liga (España)
    78,   # Bundesliga (Alemania)
    135,  # Serie A (Italia)
    61,   # Ligue 1 (Francia)
    94,   # Primeira Liga (Portugal)
    88,   # Eredivisie (Países Bajos)
    128,  # Liga Profesional Argentina
    71,   # Brasileirao (Brasil)
    62,   # Categoría Primera A (Colombia)
    135,  # Liga MX (México)
    13    # Copa Libertadores
]

# Función para enviar mensajes a Telegram
def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": texto}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Error enviando mensaje:", e)

# Para evitar eventos duplicados
eventos_reportados = set()

# Función para revisar eventos en vivo
def revisar_eventos():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    try:
        respuesta = requests.get(url, headers=headers)
        datos = respuesta.json()
        partidos = datos.get("response", [])
        for partido in partidos:
            fixture = partido.get("fixture", {})
            league = partido.get("league", {})
            eventos = partido.get("events", [])
            if league.get("id") not in ligas_ids:
                continue

            for evento in eventos:
                evento_id = f"{fixture.get('id')}_{evento.get('time', {}).get('elapsed')}_{evento.get('team', {}).get('id')}_{evento.get('type')}_{evento.get('detail')}"
                if evento_id in eventos_reportados:
                    continue

                tipo = evento.get("type", "").lower()
                detalle = evento.get("detail", "").lower()

                # Tiros al palo o larguero
                if tipo == "shot" and any(p in detalle for p in ["post", "crossbar"]):
                    mensaje = f"Tiro al palo en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']} minuto {evento['time']['elapsed']}"
                    enviar_mensaje(mensaje)
                    eventos_reportados.add(evento_id)

                # Gol anulado por VAR (detalles ampliados)
                elif tipo == "var" and any(p in detalle for p in ["goal cancelled", "goal disallowed", "no goal", "offside", "handball", "foul", "review", "gol anulado"]):
                    mensaje = f"Gol anulado por VAR en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']} minuto {evento['time']['elapsed']}"
                    enviar_mensaje(mensaje)
                    eventos_reportados.add(evento_id)

    except Exception as e:
        print("Error al revisar eventos:", e)

# Flask para mantener activo el bot en hosting como Railway
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot funcionando correctamente"

# Mensaje de arranque
enviar_mensaje("Bot iniciado y funcionando correctamente")

# Hilo para revisar eventos cada 15 segundos
def run_bot():
    while True:
        revisar_eventos()
        time.sleep(15)

if __name__ == '__main__':
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    app.run(host='0.0.0.0', port=5000)

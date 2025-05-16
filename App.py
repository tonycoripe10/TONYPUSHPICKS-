import requests
import time
from flask import Flask
from threading import Thread

app = Flask(__name__)

API_KEY =  ""  # Se leerá de variables de entorno (configura en Railway o Replit)
TOKEN_TELEGRAM =  ""  # Idem
CHAT_ID =  ""  # Idem

# Si usas variables de entorno, reemplaza así:
import os
API_KEY = os.getenv("APIkey")
TOKEN_TELEGRAM = os.getenv("Tokentelegram")
CHAT_ID = os.getenv("Chatid")

url_base_api = "https://v3.football.api-sports.io/"
headers = {
    "x-apisports-key": API_KEY
}

# Ligas a monitorear (IDs según API-Football)
LIGAS_IDS = [
    140,  # España - LaLiga
    39,   # Inglaterra - Premier League
    94,   # Portugal - Primeira Liga
    88,   # Holanda - Eredivisie
    61,   # Francia - Ligue 1
    135,  # Italia - Serie A
    78,   # Alemania - Bundesliga
    128,  # Argentina - Primera División
    71,   # Brasil - Serie A
    243,  # Colombia - Categoría Primera A
    262,  # México - Liga MX
    2031  # Copa Libertadores
]

eventos_reportados = set()  # Para evitar repetir alertas

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=data)
        r.raise_for_status()
    except Exception as e:
        print("Error enviando mensaje Telegram:", e)

def revisar_eventos():
    for liga_id in LIGAS_IDS:
        try:
            # Obtener partidos en vivo para la liga
            url_fixtures = f"{url_base_api}fixtures?live=all&league={liga_id}"
            response = requests.get(url_fixtures, headers=headers)
            data = response.json()

            if data["results"] > 0:
                partidos = data["response"]
                for partido in partidos:
                    fixture_id = partido["fixture"]["id"]
                    local = partido["teams"]["home"]["name"]
                    visitante = partido["teams"]["away"]["name"]
                    liga_nombre = partido["league"]["name"]

                    # Obtener eventos del partido
                    url_events = f"{url_base_api}events?fixture={fixture_id}"
                    res_events = requests.get(url_events, headers=headers)
                    eventos = res_events.json()

                    if eventos["results"] > 0:
                        for evento in eventos["response"]:
                            evento_id = evento["id"]
                            tipo = evento["type"].lower()
                            detalle = evento["detail"].lower()
                            equipo = evento["team"]["name"]

                            # Filtrar eventos tiro al palo o gol anulado por VAR
                            if evento_id not in eventos_reportados:
                                if (tipo == "shot" and ("post" in detalle or "crossbar" in detalle or "pole" in detalle or "post" in detalle)) or \
                                   (tipo == "var" and "goal cancelled" in detalle):
                                    mensaje = f"⚽ <b>{liga_nombre}</b>\n" \
                                              f"Partido: {local} vs {visitante}\n" \
                                              f"Equipo: {equipo}\n" \
                                              f"Evento: {evento['type']} - {evento['detail']}"
                                    enviar_mensaje(mensaje)
                                    eventos_reportados.add(evento_id)
        except Exception as e:
            print(f"Error en liga {liga_id}: {e}")

@app.route('/')
def home():
    return "Bot funcionando correctamente"

def bot_loop():
    while True:
        revisar_eventos()
        time.sleep(15)

if __name__ == '__main__':
    # Lanzar bot en hilo paralelo para que Flask no se bloquee
    hilo = Thread(target=bot_loop)
    hilo.daemon = True
    hilo.start()

    app.run(host='0.0.0.0', port=5000)

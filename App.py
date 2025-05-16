import os
import time
import requests
from flask import Flask
from threading import Thread

app = Flask(__name__)

API_KEY = os.getenv("APIkey")
TOKEN = os.getenv("Tokentelegram")
CHAT_ID = os.getenv("Chatid")

ligas_ids = [
    1,  # Premier League
    2,  # La Liga
    3,  # Serie A
    4,  # Bundesliga
    5,  # Ligue 1
    39, # Argentina Liga Profesional
    71, # Brasileirão
    62, # Liga BetPlay (Colombia)
    94, # Liga MX (México)
    88, # Liga Portugal
    135,# Eredivisie
    6   # Copa Libertadores
]

eventos_reportados = set()

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": texto
    }
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Error al enviar mensaje:", e)

def revisar_eventos():
    hoy = time.strftime("%Y-%m-%d")
    url_fixtures = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_KEY}

    for liga_id in ligas_ids:
        params = {"league": liga_id, "season": 2024, "date": hoy}
        try:
            res = requests.get(url_fixtures, headers=headers, params=params)
            partidos = res.json().get("response", [])

            for partido in partidos:
                fixture_id = partido["fixture"]["id"]
                url_eventos = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
                res_eventos = requests.get(url_eventos, headers=headers)
                eventos = res_eventos.json().get("response", [])

                for evento in eventos:
                    detalle = evento.get("detail", "").lower()
                    tipo = evento.get("type", "").lower()
                    evento_id = f"{fixture_id}-{evento.get('time', {}).get('elapsed', 0)}-{detalle}"

                    if evento_id not in eventos_reportados:
                        if "var" in detalle and "goal cancelled" in detalle:
                            mensaje = f"Gol anulado por VAR en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']}."
                            enviar_mensaje(mensaje)
                            eventos_reportados.add(evento_id)
                        elif "post" in detalle or "crossbar" in detalle or "larguero" in detalle:
                            mensaje = f"Tiro al palo en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']}."
                            enviar_mensaje(mensaje)
                            eventos_reportados.add(evento_id)

        except Exception as e:
            print("Error al revisar eventos:", e)

@app.route('/')
def home():
    return "Bot funcionando correctamente"

enviar_mensaje("Bot iniciado y funcionando correctamente")

if __name__ == '__main__':
    def run_bot():
        while True:
            try:
                revisar_eventos()
            except Exception as e:
                print("Error:", e)
            time.sleep(15)

    Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

import requests
import time
import os
from datetime import datetime

# Variables de entorno
API_KEY = os.environ['APIkey']
TELEGRAM_TOKEN = os.environ['Telegramtoken']
CHAT_ID = os.environ['Chatid']

# Ligas a monitorear
LEAGUES = [39, 140, 135, 78, 61, 94, 253, 262, 203, 195, 266]
URL_FIXTURES = "https://v3.football.api-sports.io/fixtures"
URL_STATS = "https://v3.football.api-sports.io/fixtures/statistics"
URL_EVENTS = "https://v3.football.api-sports.io/fixtures/events"
HEADERS = {"x-apisports-key": API_KEY}

eventos_reportados = set()

def enviar_mensaje(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")

def guardar_en_log(evento):
    with open("eventos_log.txt", "a", encoding="utf-8") as log:
        log.write(f"{datetime.utcnow().isoformat()} - {evento}\n")

def obtener_partidos_en_vivo():
    params = {"live": "all"}
    try:
        response = requests.get(URL_FIXTURES, headers=HEADERS, params=params)
        data = response.json()
        return [match for match in data["response"] if match["league"]["id"] in LEAGUES]
    except Exception as e:
        print(f"Error al obtener partidos en vivo: {e}")
        return []

def analizar_estadisticas(fixture_id, equipo_nombre):
    try:
        response = requests.get(URL_STATS, headers=HEADERS, params={"fixture": fixture_id})
        stats = response.json()["response"]
        for equipo in stats:
            if equipo["team"]["name"] == equipo_nombre:
                tiros_puerta = next((item["value"] for item in equipo["statistics"] if item["type"] == "Shots on Goal"), 0)
                xg = next((item["value"] for item in equipo["statistics"] if item["type"] == "Expected Goals"), 0)
                return tiros_puerta, float(xg) if xg else 0.0
        return 0, 0.0
    except Exception as e:
        print(f"Error al analizar estadísticas: {e}")
        return 0, 0.0

def revisar_eventos(fixture_id):
    try:
        response = requests.get(URL_EVENTS, headers=HEADERS, params={"fixture": fixture_id})
        eventos = response.json()["response"]
        for evento in eventos:
            evento_id = (evento["time"]["elapsed"], evento["team"]["id"], evento["type"], evento.get("detail", ""))
            if evento_id in eventos_reportados:
                continue
            eventos_reportados.add(evento_id)
            guardar_en_log(f"{evento['time']['elapsed']} - {evento['team']['name']} - {evento['type']} - {evento.get('detail', '')}")

            tipo = evento["type"].lower()
            detalle = evento.get("detail", "").lower()
            comentario = evento.get("comments", "").lower() if evento.get("comments") else ""

            # Gol anulado por VAR
            if tipo == "goal" and (
                "cancelled" in detalle or "disallowed" in detalle or "annulled" in detalle or
                ("var" in comentario and any(palabra in comentario for palabra in ["offside", "foul", "handball", "goalkeeper interference"]))
            ):
                enviar_mensaje(f"⚠️ Gol anulado por VAR: {evento['team']['name']} - Min {evento['time']['elapsed']}")

            # Balón al palo/larguero
            palabras_clave_palo = [
                "hit the post", "hit the bar", "off the post", "off the bar",
                "struck the post", "struck the bar", "post", "bar", "crossbar",
                "rebound off post", "rebound off bar", "post rebound", "bar rebound"
            ]
            if any(p in detalle for p in palabras_clave_palo) or any(p in comentario for p in palabras_clave_palo):
                enviar_mensaje(f"⚠️ Balón al palo/larguero: {evento['team']['name']} - Min {evento['time']['elapsed']}")

    except Exception as e:
        print(f"Error al revisar eventos: {e}")

def main():
    enviar_mensaje("✅ Bot en marcha correctamente.")
    while True:
        partidos = obtener_partidos_en_vivo()
        for partido in partidos:
            fixture_id = partido["fixture"]["id"]
            minuto = partido["fixture"]["status"]["elapsed"]
            if minuto and minuto >= 30:
                for equipo in [partido["teams"]["home"], partido["teams"]["away"]]:
                    tiros, xg = analizar_estadisticas(fixture_id, equipo["name"])
                    if tiros >= 4:
                        enviar_mensaje(f"⚠️ {equipo['name']} lleva {tiros} tiros a puerta al minuto {minuto}")
                    if xg > 1.5:
                        enviar_mensaje(f"⚠️ {equipo['name']} supera 1.50 en goles esperados (xG) al minuto {minuto}")
            revisar_eventos(fixture_id)
        time.sleep(15)

if __name__ == "__main__":
    main()

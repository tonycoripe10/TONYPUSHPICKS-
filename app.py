import requests import time from datetime import datetime import os

Configuración

TELEGRAM_TOKEN = os.getenv("Telegramtoken") CHAT_ID = os.getenv("Chatid") API_KEY = os.getenv("APIkey")

ID de ligas a monitorear

LEAGUE_IDS = [39, 140, 135, 78, 61, 94, 253, 262, 203, 80, 79]

Variables para control de alertas

eventos_reportados = set() equipos_alertados = {}

Ruta para archivo de logs

LOG_FILE = "eventos.txt"

def enviar_mensaje(mensaje): url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" data = {"chat_id": CHAT_ID, "text": mensaje} try: requests.post(url, data=data) except Exception as e: print(f"Error al enviar mensaje: {e}")

def guardar_evento_log(evento): try: with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(f"{datetime.utcnow()} - {evento}\n") except Exception as e: print(f"Error al guardar evento: {e}")

def obtener_partidos_en_vivo(): url = "https://v3.football.api-sports.io/fixtures?live=all" headers = {"x-apisports-key": API_KEY} try: response = requests.get(url, headers=headers) return response.json() except Exception as e: print(f"Error al obtener partidos en vivo: {e}") return {"response": []}

def analizar_eventos(): data = obtener_partidos_en_vivo() for partido in data.get("response", []): fixture_id = partido["fixture"]["id"] liga_id = partido["league"]["id"] minuto = partido["fixture"]["status"]["elapsed"]

if liga_id not in LEAGUE_IDS:
        continue

    # Revisar eventos del partido
    eventos = partido.get("events", [])
    for evento in eventos:
        descripcion = evento.get("detail", "").lower()
        tipo = evento.get("type", "")
        tiempo = evento.get("time", {}).get("elapsed", 0)
        id_unico = f"{fixture_id}_{evento.get('time', {}).get('elapsed', '')}_{evento.get('team', {}).get('id', '')}_{descripcion}"

        guardar_evento_log(evento)

        if id_unico in eventos_reportados:
            continue

        # GOL ANULADO POR VAR
        if tipo == "Goal" and (
            "goal cancelled" in descripcion or
            "goal disallowed" in descripcion or
            ("var" in descripcion and any(x in descripcion for x in ["offside", "foul", "handball", "goalkeeper interference"]))
        ):
            mensaje = f"Gol anulado por VAR en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']} - Motivo: {evento['detail']}"
            enviar_mensaje(mensaje)
            eventos_reportados.add(id_unico)

        # BALONES AL PALO
        if tipo in ["Shot", "Miss", "Goal"] and any(p in descripcion for p in ["post", "bar", "crossbar", "off the post", "hit the post", "off the bar", "off the crossbar", "rebound from post", "rebound from bar"]):
            mensaje = f"Balón al palo en el partido {partido['teams']['home']['name']} vs {partido['teams']['away']['name']} - Detalle: {evento['detail']}"
            enviar_mensaje(mensaje)
            eventos_reportados.add(id_unico)

    # ALERTA POR TIROS A PUERTA O xG
    for equipo in ["home", "away"]:
        stats = partido["teams"][equipo]["name"]
        team_id = partido["teams"][equipo]["id"]
        statistics = partido.get("statistics", [])
        shots_on_target = None
        xg = None

        # Buscar estadísticas en el array
        for item in statistics:
            if item.get("team", {}).get("id") == team_id:
                for stat in item.get("statistics", []):
                    if stat["type"] == "Shots on Goal":
                        shots_on_target = stat["value"]
                    elif stat["type"].lower() == "expected goals":
                        xg = stat["value"]

        key = f"{fixture_id}_{team_id}_alerta"
        if minuto >= 30 and key not in equipos_alertados:
            if (shots_on_target is not None and shots_on_target >= 4) or (xg is not None and xg >= 1.5):
                enviar_mensaje(f"{stats} tiene {shots_on_target or 'N/A'} tiros a puerta y {xg or 'N/A'} xG al minuto {minuto} en el partido contra {partido['teams']['away' if equipo == 'home' else 'home']['name']}")
                equipos_alertados[key] = True

if name == "main": while True: try: analizar_eventos() except Exception as e: print(f"Error general: {e}") time.sleep(15)


import requests
import time
import os
from datetime import datetime

# Variables de entorno
API_KEY = os.getenv("APIkey")
BOT_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

# Configuración
LIGAS_MONITOREADAS = [39, 140, 135, 78, 61, 62, 71, 94, 135, 262, 253]  # Premier, La Liga, Serie A, etc.
INTERVALO = 15  # segundos

eventos_reportados = set()

def enviar_mensaje(mensaje):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error al enviar mensaje:", e)

def guardar_evento_log(evento):
    try:
        with open("eventos.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} | {evento}\n")
    except Exception as e:
        print("Error guardando evento:", e)

def obtener_partidos_en_juego():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    try:
        respuesta = requests.get(url, headers=headers)
        data = respuesta.json()
        return data.get("response", [])
    except Exception as e:
        print("Error obteniendo partidos:", e)
        return []

def analizar_eventos(partido):
    id_partido = partido["fixture"]["id"]
    liga_id = partido["league"]["id"]
    minuto = partido["fixture"]["status"]["elapsed"]

    if liga_id not in LIGAS_MONITOREADAS:
        return

    # Eventos
    url = f"https://v3.football.api-sports.io/fixtures/events?fixture={id_partido}"
    headers = {"x-apisports-key": API_KEY}
    try:
        respuesta = requests.get(url, headers=headers)
        eventos = respuesta.json().get("response", [])
    except Exception as e:
        print("Error obteniendo eventos:", e)
        return

    for evento in eventos:
        evento_id = f"{id_partido}-{evento.get('time', {}).get('elapsed')}-{evento.get('team', {}).get('id')}-{evento.get('type')}-{evento.get('detail')}"

        if evento_id in eventos_reportados:
            continue

        eventos_reportados.add(evento_id)
        guardar_evento_log(evento)

        tipo = evento.get("type", "").lower()
        detalle = evento.get("detail", "").lower()
        comentario = evento.get("comments", "")
        equipo = evento.get("team", {}).get("name", "Desconocido")
        jugador = evento.get("player", {}).get("name", "Jugador desconocido")

        # GOL ANULADO POR VAR
        if tipo == "goal" and any(x in detalle for x in ["cancelled", "disallowed", "annulled"]):
            if any(x in comentario.lower() for x in ["var", "offside", "foul", "handball", "goalkeeper interference"]):
                mensaje = f"GOL ANULADO POR VAR en {equipo}: {jugador} ({detalle})"
                enviar_mensaje(mensaje)

        # BALÓN AL PALO / LARGUERO
        if tipo == "shot" and any(x in detalle for x in ["hit the post", "post", "bar", "crossbar", "woodwork", "off the post"]):
            mensaje = f"Tiro al palo/larguero de {equipo}: {jugador} ({detalle})"
            enviar_mensaje(mensaje)

    # ALERTA DE TIROS A PUERTA O xG AL MINUTO 30+
    if minuto >= 30:
        url_estadisticas = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={id_partido}"
        try:
            res = requests.get(url_estadisticas, headers=headers)
            estadisticas = res.json().get("response", [])
        except Exception as e:
            print("Error obteniendo estadísticas:", e)
            return

        for stats in estadisticas:
            nombre_equipo = stats["team"]["name"]
            tiros_puerta = 0
            xg = 0.0

            for item in stats["statistics"]:
                if item["type"].lower() == "shots on goal":
                    tiros_puerta = item["value"] or 0
                if item["type"].lower() == "expected goals":
                    xg = float(item["value"] or 0)

            alerta_id = f"{id_partido}-{nombre_equipo}-alerta30"

            if alerta_id not in eventos_reportados:
                if tiros_puerta >= 4 or xg > 1.5:
                    mensaje = f"Alerta Minuto {minuto}: {nombre_equipo} lleva {tiros_puerta} tiros a puerta y xG: {xg}"
                    enviar_mensaje(mensaje)
                    eventos_reportados.add(alerta_id)

# Bucle principal
enviar_mensaje("Bot de fútbol iniciado y monitoreando partidos...")
while True:
    try:
        partidos = obtener_partidos_en_juego()
        for partido in partidos:
            analizar_eventos(partido)
    except Exception as e:
        print("Error general:", e)
    time.sleep(INTERVALO)

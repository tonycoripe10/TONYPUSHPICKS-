import os
import time
import requests
from datetime import datetime
import pytz

# Variables de entorno
SPORTMONKS_TOKEN = os.getenv("Sportmonks")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

# Ligas permitidas (IDs de Sportmonks para tus competiciones)
COMPETITION_IDS = [
    501, 502,   # España 1ª y 2ª
    8, 9,       # Inglaterra 1ª y 2ª
    82,         # Alemania 1ª
    384,        # Italia 1ª
    301,        # Francia 1ª
    271,        # Holanda 1ª
    350,        # Portugal 1ª
    235,        # México 1ª
    540,        # Brasil 1ª
    591,        # Colombia 1ª
    1,          # Argentina 1ª
    1127,       # Copa Libertadores
    1130,       # Copa Sudamericana
    18640,      # MLS
    1329,       # Champions League
    1326,       # Europa League
    1322,       # Conference League
    1600        # Mundial de Clubes
]

# Eventos ya alertados para no repetir
eventos_alertados = set()

# Enviar mensaje a Telegram
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    requests.post(url, data=data)

# Verificar si un evento es relevante
def evento_relevante(evento):
    comentario = evento.get("text", "").lower()
    tipo = evento.get("type", "").lower()

    # Gol anulado por VAR
    if "var" in comentario and any(palabra in comentario for palabra in ["offside", "foul", "handball", "goalkeeper", "disallowed", "cancelled", "annulled"]):
        return "❌ <b>Gol anulado por VAR</b>\n" + evento.get("text", "")

    # Tiro al palo/larguero
    if any(palabra in comentario for palabra in ["post", "bar", "off the bar", "off the post"]):
        return "⚠️ <b>Tiro al palo/larguero</b>\n" + evento.get("text", "")

    # Tarjeta amarilla antes del minuto 9
    minuto = evento.get("minute", 0)
    if tipo == "yellowcard" and minuto <= 9:
        return f"🟨 <b>Tarjeta amarilla al {minuto}'</b>\n" + evento.get("text", "")

    return None

# Monitorear partidos en vivo
def monitorear():
    while True:
        try:
            url = f"https://api.sportmonks.com/v3/football/fixtures/live?api_token={SPORTMONKS_TOKEN}&include=state,participants,scores,events,statistics"
            response = requests.get(url)
            if response.status_code != 200:
                print("Error al consultar Sportmonks:", response.text)
                time.sleep(40)
                continue

            data = response.json()
            fixtures = data.get("data", [])

            for partido in fixtures:
                league_id = partido.get("league_id")
                if league_id not in COMPETITION_IDS:
                    continue

                fixture_id = partido["id"]
                home = next((t for t in partido["participants"] if t["meta"]["location"] == "home"), None)
                away = next((t for t in partido["participants"] if t["meta"]["location"] == "away"), None)
                score = partido["scores"]
                estado = partido["state"]["minute"]

                nombre_partido = f"{home['name']} vs {away['name']}"
                marcador = f"{score['home_score']} - {score['away_score']}"
                minuto = int(estado) if estado else 0

                # Revisar eventos
                for evento in partido.get("events", []):
                    clave_evento = f"{fixture_id}-{evento['id']}"
                    if clave_evento in eventos_alertados:
                        continue

                    alerta = evento_relevante(evento)
                    if alerta:
                        mensaje = f"{alerta}\n\n<b>{nombre_partido} ({marcador})</b>\nMinuto: {minuto}'"
                        enviar_telegram(mensaje)
                        eventos_alertados.add(clave_evento)

                # Revisar tiros a puerta antes del 30'
                if minuto <= 30:
                    for team in partido.get("statistics", []):
                        stats = team.get("statistics", [])
                        shots_on_target = next((int(s["value"]) for s in stats if s["type"] == "shots_on_target"), 0)
                        if shots_on_target >= 4:
                            clave_tiros = f"{fixture_id}-{team['participant_id']}-shots"
                            if clave_tiros not in eventos_alertados:
                                nombre_equipo = team["participant"]["name"]
                                mensaje = f"🔥 <b>{nombre_equipo} ya tiene {shots_on_target} tiros a puerta al minuto {minuto}'</b>\n\n<b>{nombre_partido} ({marcador})</b>"
                                enviar_telegram(mensaje)
                                eventos_alertados.add(clave_tiros)

        except Exception as e:
            print("Error en el bot:", e)

        time.sleep(40)

if __name__ == "__main__":
    monitorear()

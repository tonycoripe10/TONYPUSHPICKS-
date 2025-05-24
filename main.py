import os
import requests
import datetime
import time
import telegram
import pytz

# Variables
SPORTMONKS_API_KEY = os.getenv("Sportmonks")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Zonas horarias
utc = pytz.utc
local_tz = pytz.timezone("America/Bogota")

def enviar_mensaje(msg):
    try:
        bot.send_message(chat_id=CHAT_ID, text=msg)
        print(f"[TELEGRAM] {msg}")
    except Exception as e:
        print(f"[ERROR TELEGRAM] {e}")

def obtener_partido_en_colombia():
    hoy = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=participants;league.country"
    resp = requests.get(url)
    data = resp.json()

    for partido in data.get("data", []):
        pais = partido.get("league", {}).get("country", {}).get("name", "")
        status = partido.get("status", {}).get("type", "")
        if pais.lower() == "colombia" and status in ["INPLAY_1ST_HALF", "INPLAY_2ND_HALF"]:
            return partido["id"], partido["participants"]
    return None, None

def monitorear_partido(fixture_id):
    eventos_previos = set()

    while True:
        url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events"
        resp = requests.get(url)
        data = resp.json().get("data", {})
        eventos = data.get("events", [])

        for e in eventos:
            evento_id = e["id"]
            if evento_id in eventos_previos:
                continue

            tipo = e.get("type", "desconocido")
            minuto = e.get("minute", "?")
            jugador = e.get("player", {}).get("name", "Sin nombre")
            equipo = e.get("team", {}).get("name", "Equipo")

            mensaje = f"🟠 Evento: *{tipo}*\n👤 {jugador}\n🏳️ {equipo}\n⏱️ Minuto {minuto}"
            enviar_mensaje(mensaje)
            eventos_previos.add(evento_id)

            print(f"[EVENTO DETECTADO] {mensaje}")

        time.sleep(30)

if __name__ == "__main__":
    print("[INFO] Buscando partido en curso en Colombia...")
    fixture_id, participantes = obtener_partido_en_colombia()

    if fixture_id:
        print(f"[INFO] Monitoreando partido ID {fixture_id}")
        enviar_mensaje("✅ Detectado partido en curso en Colombia. Iniciando monitoreo...")
        monitorear_partido(fixture_id)
    else:
        print("[INFO] No se encontró partido en curso en Colombia.")
        enviar_mensaje("⚠️ No hay partido en curso en Colombia en este momento.")

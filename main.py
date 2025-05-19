import os
import requests
import time
import schedule
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

BASE_URL = "https://api.sportmonks.com/v3/football"
HEADERS = {"accept": "application/json"}
LIGA_ESPANOLA_ID = 140
CHECK_INTERVAL = 40
resumen_enviado_hoy = {"EU": False}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)

def fetch_live_fixtures():
    url = f"{BASE_URL}/fixtures/live"
    params = {
        "api_token": API_KEY,
        "leagues": str(LIGA_ESPANOLA_ID),
        "include": "events,statistics"
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except requests.exceptions.RequestException as e:
        print("[API] Error al obtener partidos en vivo:", e)
        print("URL:", response.url if 'response' in locals() else url)
        print("Respuesta:", response.text if 'response' in locals() else "No hay respuesta")
        return []

def fetch_daily_fixtures(league_id):
    today = datetime.utcnow().strftime('%Y-%m-%d')
    url = f"{BASE_URL}/fixtures/date/{today}"
    params = {
        "api_token": API_KEY,
        "leagues": league_id,
        "include": "participants",
        "sort": "starting_at"
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print("[API] Error al obtener partidos diarios:", e)
        return []

def crear_mensaje_resumen(fixtures):
    if not fixtures:
        return "Hoy no hay partidos en La Liga."

    mensaje = "⚽ <b>Partidos de hoy en La Liga</b> ⚽\n\n"
    for fixture in fixtures:
        start = fixture["starting_at"]["local"][:16].replace("T", " ")
        equipos = f'{fixture["participants"][0]["name"]} vs {fixture["participants"][1]["name"]}'
        mensaje += f"🕒 {start} - {equipos}\n"
    return mensaje

def enviar_resumen_europeo():
    if resumen_enviado_hoy["EU"]:
        return
    fixtures = fetch_daily_fixtures(LIGA_ESPANOLA_ID)
    mensaje = crear_mensaje_resumen(fixtures)
    send_telegram_message(mensaje)
    resumen_enviado_hoy["EU"] = True
    print("[BOT] Resumen europeo enviado.")

def check_fixtures():
    fixtures = fetch_live_fixtures()
    for fixture in fixtures:
        fixture_id = fixture["id"]
        league = "La Liga"
        home = fixture["participants"][0]["name"]
        away = fixture["participants"][1]["name"]
        minute = fixture["time"]["minute"]
        score = fixture["scores"]["local_score"], fixture["scores"]["visitor_score"]

        stats = fixture.get("statistics", [])
        events = fixture.get("events", [])

        mensaje_base = f"⚽ <b>{home} {score[0]} - {score[1]} {away}</b>\n🏆 {league}"

        # 1. Gol anulado por VAR
        for e in events:
            if e.get("type") == "goal_cancelled" or (
                "VAR" in e.get("description", "").upper() and
                any(palabra in e.get("description", "").lower() for palabra in [
                    "offside", "foul", "handball", "goalkeeper interference",
                    "goal disallowed", "goal cancelled", "goal annulled", "disallowed goal"
                ])
            ):
                mensaje = f"❌ <b>¡GOL ANULADO POR VAR!</b>\n{mensaje_base}\n🔎 {e.get('description', '')}"
                send_telegram_message(mensaje)
                break

        # 2. Tiro al palo
        for e in events:
            if "post" in e.get("description", "").lower() or "bar" in e.get("description", "").lower():
                mensaje = f"🥶 <b>¡TIRO AL PALO!</b>\n{mensaje_base}\n🔁 {e.get('description', '')}"
                send_telegram_message(mensaje)
                break

        # 3. 4+ tiros a puerta hasta el minuto 30
        if minute <= 30:
            for equipo in stats:
                name = equipo["participant"]["name"]
                shots_on_target = equipo.get("stats", {}).get("shots_on_target", 0)
                if isinstance(shots_on_target, str):
                    shots_on_target = int(shots_on_target)
                if shots_on_target >= 4:
                    mensaje = f"🔥 <b>{name} tiene {shots_on_target} remates a puerta</b>\n{mensaje_base}"
                    send_telegram_message(mensaje)

        # 4. xG superior a 1.5 hasta el minuto 30
        if minute <= 30:
            for equipo in stats:
                name = equipo["participant"]["name"]
                xg = equipo.get("stats", {}).get("expected_goals", 0)
                if isinstance(xg, str):
                    xg = float(xg)
                if xg > 1.5:
                    mensaje = f"📈 <b>{name} supera 1.5 xG</b> ({xg})\n{mensaje_base}"
                    send_telegram_message(mensaje)

        # 5. Tarjeta amarilla antes del minuto 9
        for e in events:
            if e.get("type") == "card" and e.get("card_type") == "yellow" and e.get("minute", 0) <= 9:
                jugador = e.get("player", {}).get("name", "Jugador desconocido")
                mensaje = f"🟨 <b>¡Tarjeta amarilla tempranera!</b>\n{mensaje_base}\n👤 {jugador} - {e.get('minute')} min"
                send_telegram_message(mensaje)
                break

def reiniciar_flags_resumen():
    resumen_enviado_hoy["EU"] = False

# Programar el resumen diario a las 20:10
schedule.every().day.at("20:10").do(enviar_resumen_europeo)
schedule.every().day.at("00:01").do(reiniciar_flags_resumen)

print("[BOT] Iniciado correctamente. Esperando eventos...")

while True:
    schedule.run_pending()
    check_fixtures()
    time.sleep(CHECK_INTERVAL)

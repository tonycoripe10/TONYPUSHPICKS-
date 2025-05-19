import os
import requests
import time
import datetime
import pytz
import schedule

TOKEN = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

# Competitions permitidas (IDs reales de Sportmonks 3.0)
ALLOWED_COMPETITION_IDS = [
    5, 8,    # España Primera y Segunda
    82, 9,   # Inglaterra Primera y Segunda
    23,      # Alemania Primera
    384,     # Italia Primera
    16,      # Francia Primera
    29,      # Holanda Primera
    24,      # Portugal Primera
    1075,    # México Primera
    71,      # Brasil Primera
    50,      # Colombia Primera
    68,      # Argentina Primera
    367,     # Copa Libertadores
    369,     # Copa Sudamericana
    271,     # MLS
    2,       # Champions League
    3,       # Europa League
    722,     # Conference League
    724      # Club World Cup
]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}

BASE_URL = "https://api.sportmonks.com/v3/football"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)

def get_live_matches():
    url = f"{BASE_URL}/livescores?include=participants;events;stats;state;league&per_page=50"
    try:
        response = requests.get(url, headers=HEADERS)
        data = response.json()
        if "data" in data:
            return [match for match in data["data"] if match["league"]["id"] in ALLOWED_COMPETITION_IDS]
    except Exception as e:
        print("Error al obtener partidos en vivo:", e)
    return []

def format_match_name(match):
    home = match["participants"][0]["name"]
    away = match["participants"][1]["name"]
    return f"{home} vs {away}"

def process_match(match):
    match_id = match["id"]
    match_name = format_match_name(match)
    score = f"{match['participants'][0]['score']['goals']} - {match['participants'][1]['score']['goals']}"
    minute = int(match['state']['minute']) if match['state']['minute'] else 0

    events = match.get("events", [])
    stats = match.get("stats", [])

    alerts = []

    for event in events:
        comment = event.get("comment", "").lower()
        event_type = event.get("type")

        # Gol anulado por VAR
        if "var" in comment and any(kw in comment for kw in ["offside", "foul", "handball", "disallowed", "cancelled", "annulled", "goalkeeper interference"]):
            alerts.append(f"❌ <b>GOL ANULADO POR VAR</b>\n<b>{match_name}</b>\nResultado: {score}\nComentario: {event.get('comment', '')}")

        # Tiro al palo o larguero
        if any(kw in comment for kw in ["post", "crossbar", "off the bar", "off the post"]):
            alerts.append(f"🪵 <b>Tiro al palo</b>\n<b>{match_name}</b>\nResultado: {score}\nComentario: {event.get('comment', '')}")

        # Amarilla en los primeros 9 minutos
        if event_type == "card" and event.get("card") == "yellow" and event.get("minute") <= 9:
            alerts.append(f"🟨 <b>Tarjeta amarilla temprana</b>\n<b>{match_name}</b>\nMinuto: {event.get('minute')}\nJugador: {event.get('player', {}).get('name', '')}")

    # Tiros a puerta y xG hasta el minuto 30
    if stats and minute <= 30:
        for team_stats in stats:
            team_name = team_stats.get("participant", {}).get("name", "")
            shots_on_target = int(team_stats.get("shots_on_target", 0))
            xg = float(team_stats.get("expected_goals", 0))

            if shots_on_target >= 4:
                alerts.append(f"⚠️ <b>{team_name}</b> tiene <b>{shots_on_target}</b> tiros a puerta antes del minuto 30\n<b>{match_name}</b>\nResultado: {score}")

            if xg >= 1.5:
                alerts.append(f"⚠️ <b>{team_name}</b> supera 1.5 xG antes del minuto 30\n<b>{match_name}</b>\nResultado: {score}")

    for alert in alerts:
        send_telegram_message(alert)

def live_alert_loop():
    matches = get_live_matches()
    for match in matches:
        process_match(match)

# Resumen diario
def daily_summary(leagues_ids, hora_objetivo, mensaje_cabecera):
    now = datetime.datetime.now(pytz.timezone("Europe/Madrid"))
    fecha = now.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures/date/{fecha}?include=participants;league&per_page=100"
    response = requests.get(url, headers=HEADERS)
    data = response.json()

    if "data" not in data:
        return

    partidos = [
        f"{p['starting_at']['time']} - {p['participants'][0]['name']} vs {p['participants'][1]['name']} ({p['league']['name']})"
        for p in data["data"]
        if p['league']['id'] in leagues_ids
    ]

    if partidos:
        mensaje = f"{mensaje_cabecera}\n\n" + "\n".join(sorted(partidos))
        send_telegram_message(mensaje)

def resumen_europeo():
    daily_summary(
        leagues_ids=[5, 8, 82, 9, 23, 384, 16, 29, 24, 2, 3, 722, 724],
        hora_objetivo="09:00",
        mensaje_cabecera="⚽ <b>Partidos de hoy (Ligas Europeas)</b>"
    )

def resumen_sudamericano():
    daily_summary(
        leagues_ids=[1075, 71, 50, 68, 271, 367, 369],
        hora_objetivo="00:00",
        mensaje_cabecera="⚽ <b>Partidos de hoy (Sudamérica y MLS)</b>"
    )

# Programar resúmenes diarios
schedule.every().day.at("09:00").do(resumen_europeo)
schedule.every().day.at("00:00").do(resumen_sudamericano)

# Loop principal
while True:
    schedule.run_pending()
    live_alert_loop()
    time.sleep(40)

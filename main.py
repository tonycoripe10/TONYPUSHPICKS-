import os
import time
import requests
import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

API_KEY = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

HEADERS = {"Accept": "application/json"}

# Define las ligas
LEAGUES_EUROPE = [140, 39, 61, 78, 135, 88, 94, 132]  # Ejemplo IDs de ligas Europeas en Sportmonks
LEAGUES_SOUTH_AMERICA = [154, 149, 155, 160]  # Ejemplo IDs de ligas Sudamericanas

BASE_URL = "https://api.sportmonks.com/v3/football"

def telegram_send_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, data=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def fetch_live_fixtures(league_ids):
    url = f"{BASE_URL}/fixtures/live"
    params = {
        "api_token": API_KEY,
        "leagues": ",".join(map(str, league_ids)),
        "include": "events,statistics",
    }
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    return data.get("data", [])

def fetch_fixtures_by_date(league_ids, date):
    url = f"{BASE_URL}/fixtures/date/{date}"
    params = {
        "api_token": API_KEY,
        "leagues": ",".join(map(str, league_ids)),
        "include": "localTeam,visitorTeam",
    }
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    return data.get("data", [])

def build_summary_message(fixtures):
    message = "⚽ *Resumen de partidos de hoy*\n\n"
    for f in sorted(fixtures, key=lambda x: x['time']['starting_at']['timestamp']):
        start_time = datetime.datetime.fromtimestamp(f['time']['starting_at']['timestamp']).strftime('%H:%M')
        league = f.get('league', {}).get('name', 'Liga Desconocida')
        local = f.get('localTeam', {}).get('name', 'Local')
        visitor = f.get('visitorTeam', {}).get('name', 'Visitante')
        message += f"🕒 {start_time} - {league}\n{local} vs {visitor}\n\n"
    return message.strip()

def check_and_alert_live_matches():
    fixtures = fetch_live_fixtures(LEAGUES_EUROPE + LEAGUES_SOUTH_AMERICA)
    for fixture in fixtures:
        # Extraer datos importantes
        events = fixture.get("events", [])
        statistics = fixture.get("statistics", [])

        # Variables para detectar alertas
        home_shots_on_target = 0
        away_shots_on_target = 0
        home_xg = 0.0
        away_xg = 0.0
        minute = fixture.get("time", {}).get("minute", 0)

        # Recorrer estadísticas para tiros a puerta y xG
        for stat in statistics:
            if stat.get("team_id") == fixture.get("localTeam", {}).get("id"):
                home_shots_on_target = stat.get("shots_on_goal", 0)
                home_xg = stat.get("expected_goals", 0.0)
            elif stat.get("team_id") == fixture.get("visitorTeam", {}).get("id"):
                away_shots_on_target = stat.get("shots_on_goal", 0)
                away_xg = stat.get("expected_goals", 0.0)

        # Alertas tiros a puerta >= 4 antes del minuto 30
        if minute <= 30:
            if home_shots_on_target >= 4:
                telegram_send_message(f"🎯 *Alerta tiros a puerta* ⚽\nEquipo *{fixture['localTeam']['name']}* ha alcanzado {home_shots_on_target} tiros a puerta antes del minuto 30.\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

            if away_shots_on_target >= 4:
                telegram_send_message(f"🎯 *Alerta tiros a puerta* ⚽\nEquipo *{fixture['visitorTeam']['name']}* ha alcanzado {away_shots_on_target} tiros a puerta antes del minuto 30.\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

        # Alertas goles esperados +1.5 antes del minuto 30
        if minute <= 30:
            if home_xg > 1.5:
                telegram_send_message(f"🔥 *Alerta xG* ⚽\nEquipo *{fixture['localTeam']['name']}* tiene un xG de {home_xg:.2f} antes del minuto 30.\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

            if away_xg > 1.5:
                telegram_send_message(f"🔥 *Alerta xG* ⚽\nEquipo *{fixture['visitorTeam']['name']}* tiene un xG de {away_xg:.2f} antes del minuto 30.\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

        # Revisar eventos para goles anulados por VAR, tiros al palo y tarjetas amarillas
        for event in events:
            etype = event.get("type")
            minute_event = event.get("minute", 0)
            team_name = None
            if event.get("team_id") == fixture.get("localTeam", {}).get("id"):
                team_name = fixture['localTeam']['name']
            elif event.get("team_id") == fixture.get("visitorTeam", {}).get("id"):
                team_name = fixture['visitorTeam']['name']

            # Goles anulados por VAR
            if etype == "VAR":
                detail = event.get("detail", "").lower()
                if any(x in detail for x in ["goal cancelled", "goal disallowed", "goal annulled", "goal under review"]):
                    telegram_send_message(f"🚫 *Gol anulado por VAR*\nEquipo: *{team_name}*\nMinuto: {minute_event}'\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

            # Tiros al palo o larguero
            if etype == "hit_woodwork" or ("hit woodwork" in event.get("detail", "").lower()):
                telegram_send_message(f"⚡ *Tiro al palo/larguero*\nEquipo: *{team_name}*\nMinuto: {minute_event}'\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

            # Tarjetas amarillas antes del minuto 9
            if etype == "YELLOWCARD" and minute_event <= 9:
                telegram_send_message(f"🟨 *Tarjeta amarilla temprana*\nEquipo: *{team_name}*\nMinuto: {minute_event}'\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

async def daily_summary_task():
    scheduler = AsyncIOScheduler()
    # 09:00 España (CET/CEST) -> para ligas europeas
    scheduler.add_job(send_daily_summary_europe, 'cron', hour=17, minute=0)
    # 00:00 para ligas sudamericanas
    scheduler.add_job(send_daily_summary_south_america, 'cron', hour=0, minute=0)
    scheduler.start()
    while True:
        await asyncio.sleep(3600)

def send_daily_summary_europe():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    fixtures = fetch_fixtures_by_date(LEAGUES_EUROPE, today)
    if fixtures:
        message = build_summary_message(fixtures)
        telegram_send_message(f"🌍 *Resumen diario Ligas Europeas*\n\n{message}")

def send_daily_summary_south_america():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    fixtures = fetch_fixtures_by_date(LEAGUES_SOUTH_AMERICA, today)
    if fixtures:
        message = build_summary_message(fixtures)
        telegram_send_message(f"🌎 *Resumen diario Ligas Sudamericanas*\n\n{message}")

async def main_loop():
    while True:
        check_and_alert_live_matches()
        await asyncio.sleep(40)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.create_task(daily_summary_task())
    loop.run_until_complete(main_loop())

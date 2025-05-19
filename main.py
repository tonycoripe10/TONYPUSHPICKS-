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

LEAGUES_EUROPE = [140, 39, 61, 78, 135, 88, 94, 132]
LEAGUES_SOUTH_AMERICA = [154, 149, 155, 160]

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
        print(f"[Telegram] Mensaje enviado correctamente.")
    except Exception as e:
        print(f"[Telegram] Error al enviar mensaje: {e}")

def fetch_live_fixtures(league_ids):
    url = f"{BASE_URL}/fixtures/live"
    params = {
        "api_token": API_KEY,
        "leagues": ",".join(map(str, league_ids)),
        "include": "events,statistics",
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"[API] Datos partidos en vivo obtenidos: {len(data.get('data', []))} partidos.")
        return data.get("data", [])
    except Exception as e:
        print(f"[API] Error al obtener partidos en vivo: {e}")
        return []

def fetch_fixtures_by_date(league_ids, date):
    url = f"{BASE_URL}/fixtures/date/{date}"
    params = {
        "api_token": API_KEY,
        "leagues": ",".join(map(str, league_ids)),
        "include": "localTeam,visitorTeam",
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"[API] Datos partidos para {date} obtenidos: {len(data.get('data', []))} partidos.")
        return data.get("data", [])
    except Exception as e:
        print(f"[API] Error al obtener partidos por fecha: {e}")
        return []

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
    print("[Check] Revisando partidos en vivo...")
    fixtures = fetch_live_fixtures(LEAGUES_EUROPE + LEAGUES_SOUTH_AMERICA)
    for fixture in fixtures:
        events = fixture.get("events", [])
        statistics = fixture.get("statistics", [])

        home_shots_on_target = 0
        away_shots_on_target = 0
        home_xg = 0.0
        away_xg = 0.0
        minute = fixture.get("time", {}).get("minute", 0)

        for stat in statistics:
            if stat.get("team_id") == fixture.get("localTeam", {}).get("id"):
                home_shots_on_target = stat.get("shots_on_goal", 0)
                home_xg = stat.get("expected_goals", 0.0)
            elif stat.get("team_id") == fixture.get("visitorTeam", {}).get("id"):
                away_shots_on_target = stat.get("shots_on_goal", 0)
                away_xg = stat.get("expected_goals", 0.0)

        # Alertas tiros a puerta
        if minute <= 30:
            if home_shots_on_target >= 4:
                msg = (f"🎯 *Alerta tiros a puerta* ⚽\nEquipo *{fixture['localTeam']['name']}* ha alcanzado "
                       f"{home_shots_on_target} tiros a puerta antes del minuto 30.\n*Partido:* "
                       f"{fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")
                telegram_send_message(msg)

            if away_shots_on_target >= 4:
                msg = (f"🎯 *Alerta tiros a puerta* ⚽\nEquipo *{fixture['visitorTeam']['name']}* ha alcanzado "
                       f"{away_shots_on_target} tiros a puerta antes del minuto 30.\n*Partido:* "
                       f"{fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")
                telegram_send_message(msg)

        # Alertas xG
        if minute <= 30:
            if home_xg > 1.5:
                msg = (f"🔥 *Alerta xG* ⚽\nEquipo *{fixture['localTeam']['name']}* tiene un xG de "
                       f"{home_xg:.2f} antes del minuto 30.\n*Partido:* "
                       f"{fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")
                telegram_send_message(msg)

            if away_xg > 1.5:
                msg = (f"🔥 *Alerta xG* ⚽\nEquipo *{fixture['visitorTeam']['name']}* tiene un xG de "
                       f"{away_xg:.2f} antes del minuto 30.\n*Partido:* "
                       f"{fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")
                telegram_send_message(msg)

        # Eventos especiales
        for event in events:
            etype = event.get("type")
            minute_event = event.get("minute", 0)
            team_name = None
            if event.get("team_id") == fixture.get("localTeam", {}).get("id"):
                team_name = fixture['localTeam']['name']
            elif event.get("team_id") == fixture.get("visitorTeam", {}).get("id"):
                team_name = fixture['visitorTeam']['name']

            # Gol anulado VAR
            if etype == "VAR":
                detail = event.get("detail", "").lower()
                if any(x in detail for x in ["goal cancelled", "goal disallowed", "goal annulled", "goal under review"]):
                    telegram_send_message(f"🚫 *Gol anulado por VAR*\nEquipo: *{team_name}*\nMinuto: {minute_event}'\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

            # Tiro al palo/larguero
            if etype == "hit_woodwork" or ("hit woodwork" in event.get("detail", "").lower()):
                telegram_send_message(f"⚡ *Tiro al palo/larguero*\nEquipo: *{team_name}*\nMinuto: {minute_event}'\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

            # Tarjeta amarilla temprana
            if etype == "YELLOWCARD" and minute_event <= 9:
                telegram_send_message(f"🟨 *Tarjeta amarilla temprana*\nEquipo: *{team_name}*\nMinuto: {minute_event}'\n*Partido:* {fixture['localTeam']['name']} vs {fixture['visitorTeam']['name']}")

async def send_daily_summary_provisional():
    print("[Scheduler] Programado resumen provisional para hoy 17:15")
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_summary_all, 'cron', hour=17, minute=15)
    scheduler.start()
    while True:
        await asyncio.sleep(60)

def send_daily_summary_all():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"[Resumen] Enviando resumen diario provisional para {today}...")
    fixtures_eu = fetch_fixtures_by_date(LEAGUES_EUROPE, today)
    fixtures_sa = fetch_fixtures_by_date(LEAGUES_SOUTH_AMERICA, today)
    all_fixtures = fixtures_eu + fixtures_sa
    if all_fixtures:
        message = build_summary_message(all_fixtures)
        telegram_send_message(f"🌍 *Resumen diario provisional (Europeo + Sudamericano)*\n\n{message}")
    else:
        print("[Resumen] No hay partidos para el resumen de hoy.")

async def main_loop():
    while True:
        check_and_alert_live_matches()
        await asyncio.sleep(40)

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.create_task(send_daily_summary_provisional())
    loop.run_until_complete(main_loop())

import os
import requests
import time
from datetime import datetime, timedelta
import pytz

# Variables de entorno
TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")
SPORTMONKS_TOKEN = "peOUpDOIloubqz3VJXtLJeHtZ2CaplZkVz1Ou6KiYDDV4r4zhkSArZlCcCxt"

# IDs de ligas
EUROPE_LEAGUES = [8, 384, 564, 82, 301, 271, 332]
SA_LEAGUES = [9, 501, 307, 341]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=data)

def get_live_fixtures():
    url = "https://api.sportmonks.com/v3/football/fixtures?include=events;stats&filters=live=true"
    headers = {"Authorization": f"Bearer {SPORTMONKS_TOKEN}"}
    return requests.get(url, headers=headers).json()

def format_fixture(fixture):
    home = fixture['home_team']['name']
    away = fixture['away_team']['name']
    league = fixture['league']['name']
    return f"{home} vs {away} ({league})"

def check_events(fixture, sent_alerts):
    events = fixture.get("events", [])
    fixture_id = fixture['id']
    home = fixture['home_team']['name']
    away = fixture['away_team']['name']
    score = fixture['scores']['home_score'], fixture['scores']['away_score']
    league = fixture['league']['name']

    for event in events:
        event_type = event.get('type')
        event_code = event.get('code')
        event_player = event.get('player', {}).get('name', 'Desconocido')
        comment = event.get('comment', '')
        minute = event.get('minute')

        # Goles anulados por VAR
        if event_code in ["Goal cancelled", "Goal Disallowed", "VAR"] and 'cancelled' in event.get('type', '').lower():
            key = f"var-{fixture_id}-{minute}"
            if key not in sent_alerts:
                msg = (f"🚫 <b>Gol anulado por VAR</b>\n"
                       f"<b>Partido:</b> {home} {score[0]} - {score[1]} {away}\n"
                       f"<b>Minuto:</b> {minute}'\n"
                       f"<b>Jugador:</b> {event_player}\n"
                       f"<b>Motivo:</b> {comment}\n"
                       f"<b>Liga:</b> {league}")
                send_telegram_message(msg)
                sent_alerts.add(key)

        # Remates al palo
        if event_code == "HIT_WOODWORK":
            key = f"palo-{fixture_id}-{minute}"
            if key not in sent_alerts:
                msg = (f"🪵 <b>Remate al palo</b>\n"
                       f"<b>Partido:</b> {home} {score[0]} - {score[1]} {away}\n"
                       f"<b>Minuto:</b> {minute}'\n"
                       f"<b>Jugador:</b> {event_player}\n"
                       f"<b>Liga:</b> {league}")
                send_telegram_message(msg)
                sent_alerts.add(key)

    # Tiros a puerta antes del 30'
    minute = fixture.get('time', {}).get('minute', 0)
    if minute <= 30:
        stats = fixture.get("stats", [])
        for stat in stats:
            team_name = stat.get("team", {}).get("name", "")
            shots_on_target = stat.get("shots", {}).get("on", 0)
            key = f"shots-{fixture_id}-{team_name}"
            if shots_on_target >= 4 and key not in sent_alerts:
                msg = (f"🎯 <b>{team_name} ya tiene {shots_on_target} tiros a puerta</b>\n"
                       f"<b>Partido:</b> {home} {score[0]} - {score[1]} {away}\n"
                       f"<b>Minuto:</b> {minute}'\n"
                       f"<b>Liga:</b> {league}")
                send_telegram_message(msg)
                sent_alerts.add(key)

def daily_summary(leagues, title):
    today = datetime.utcnow().date()
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{today}?include=league;teams"
    headers = {"Authorization": f"Bearer {SPORTMONKS_TOKEN}"}
    response = requests.get(url, headers=headers).json()
    fixtures = response.get("data", [])

    filtered = [f for f in fixtures if f.get('league', {}).get('id') in leagues]
    if not filtered:
        return

    message = f"📅 <b>{title}</b>\n\n"
    for f in filtered:
        league = f['league']['name']
        home = f['home_team']['name']
        away = f['away_team']['name']
        hour = f['starting_at']['time']
        message += f"<b>{league}:</b> {home} vs {away} a las {hour}\n"

    send_telegram_message(message)

def main():
    sent_alerts = set()
    while True:
        now = datetime.now(pytz.timezone("Europe/Madrid"))
        hour_min = now.strftime("%H:%M")

        if hour_min == "09:00":
            daily_summary(EUROPE_LEAGUES, "Partidos de hoy en Europa")
            time.sleep(60)

        if hour_min == "00:00":
            daily_summary(SA_LEAGUES, "Partidos de hoy en Sudamérica")
            time.sleep(60)

        try:
            data = get_live_fixtures()
            fixtures = data.get("data", [])
            for fixture in fixtures:
                check_events(fixture, sent_alerts)
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(15)

if __name__ == "__main__":
    main()

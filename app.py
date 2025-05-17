import requests
import time
import datetime
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_KEY = os.getenv("API_FOOTBALL_KEY")

LEAGUE_IDS = [
    39,   # Premier League (Inglaterra)
    78,   # Bundesliga (Alemania)
    61,   # Ligue 1 (Francia)
    135,  # Serie A (Italia)
    140,  # La Liga (España)
    94,   # Primeira Liga (Portugal)
    88,   # Eredivisie (Países Bajos)
    128,  # Liga Profesional Argentina
    71,   # Serie A Brasil
    62,   # Categoría Primera A Colombia
    135,  # Serie A Italia
    262,  # Liga MX México
    141   # Segunda División España
]

VAR_KEYWORDS = [
    'goal disallowed', 'goal cancelled', 'goal annulled', 'goal invalidated',
    'VAR', 'offside', 'foul', 'handball', 'goalkeeper interference'
]

POST_KEYWORDS = [
    'hit the post', 'off the post', 'off the bar', 'off the crossbar',
    'post', 'bar', 'crossbar', 'rebound from post', 'rebound off the bar',
    'rebound off the post', 'rebound off the crossbar'
]

alerted_matches = set()
logged_events = set()

def send_alert(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Error al enviar alerta:", e)

def log_event(event_text):
    try:
        with open("eventos.txt", "a", encoding="utf-8") as f:
            f.write(event_text + "\n")
    except Exception as e:
        print("Error al registrar evento:", e)

def get_fixtures():
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_KEY}
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    params = {"date": today, "league": ",".join(map(str, LEAGUE_IDS)), "season": 2024}
    response = requests.get(url, headers=headers, params=params)
    return response.json().get("response", [])

def get_statistics(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    return response.json().get("response", [])

def get_events(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures/events?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    return response.json().get("response", [])

def should_alert_var(event):
    if event["type"] != "Goal":
        return False
    description = (event.get("detail") or "") + " " + (event.get("comments") or "")
    description = description.lower()
    return any(keyword in description for keyword in VAR_KEYWORDS)

def should_alert_post(event):
    if event["type"] != "Shot":
        return False
    description = (event.get("detail") or "") + " " + (event.get("comments") or "")
    description = description.lower()
    return any(keyword in description for keyword in POST_KEYWORDS)

def monitor():
    fixtures = get_fixtures()
    for fixture in fixtures:
        fixture_id = fixture["fixture"]["id"]
        status = fixture["fixture"]["status"]["short"]
        minute = fixture["fixture"]["status"].get("elapsed", 0)
        if status not in ["1H", "2H"]:
            continue

        # Verificar estadísticas de remates a puerta
        if fixture_id not in alerted_matches and minute >= 30:
            stats = get_statistics(fixture_id)
            for team_stats in stats:
                for item in team_stats.get("statistics", []):
                    if item["type"] == "Shots on Goal":
                        value = item["value"]
                        if value is not None and value >= 4:
                            team_name = team_stats["team"]["name"]
                            message = f"ALERTA: {team_name} lleva {value} tiros a puerta al minuto {minute}"
                            send_alert(message)
                            alerted_matches.add(fixture_id)
                            break

        # Eventos de partido
        events = get_events(fixture_id)
        for event in events:
            key = f'{fixture_id}-{event["time"]["elapsed"]}-{event["team"]["id"]}-{event["player"]["id"]}-{event["type"]}-{event["detail"]}'
            if key not in logged_events:
                log_event(f"{fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']} | Min {event['time']['elapsed']} | {event['team']['name']} | {event['type']} | {event['detail']} | {event.get('comments', '')}")
                logged_events.add(key)

                if should_alert_var(event):
                    send_alert(f"GOL ANULADO POR VAR en {fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']} - {event['team']['name']} - {event['player']['name']} - {event['detail']} - {event.get('comments', '')}")

                elif should_alert_post(event):
                    send_alert(f"TIRO AL PALO en {fixture['teams']['home']['name']} vs {fixture['teams']['away']['name']} - {event['team']['name']} - {event['player']['name']} - {event['detail']} - {event.get('comments', '')}")

while True:
    try:
        monitor()
    except Exception as e:
        print("Error general:", e)
    time.sleep(15)

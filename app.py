import requests import time import datetime import os

TELEGRAM_TOKEN = os.getenv("Telegramtoken") CHAT_ID = os.getenv("Chatid") API_KEY = os.getenv("APIkey")

HEADERS = { "X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com" }

LEAGUES = [39, 140, 135, 78, 61, 2, 3, 71, 262, 262, 94, 88, 253]  # Añadida Segunda División de España (id: 140)

REPORTED_EVENTS = set()

def send_telegram_message(message): url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" data = {"chat_id": CHAT_ID, "text": message} requests.post(url, data=data)

def log_event(text): try: with open("eventos.txt", "a", encoding="utf-8") as f: f.write(text + "\n") except Exception as e: print(f"Error al guardar evento: {e}")

def check_matches(): now = datetime.datetime.utcnow() today = now.strftime("%Y-%m-%d") for league_id in LEAGUES: url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures?league={league_id}&season=2024&date={today}" response = requests.get(url, headers=HEADERS) try: matches = response.json().get("response", []) for match in matches: fixture_id = match["fixture"]["id"] status = match["fixture"]["status"]["short"] if status in ["1H", "2H", "ET"]: process_match(fixture_id, match) except Exception as e: print(f"Error general: {e}")

def process_match(fixture_id, match_info): url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/events?fixture={fixture_id}" response = requests.get(url, headers=HEADERS) events = response.json().get("response", []) home_team = match_info["teams"]["home"]["name"] away_team = match_info["teams"]["away"]["name"]

for event in events:
    event_id = f"{fixture_id}-{event['time']['elapsed']}-{event['team']['id']}-{event['type']}-{event.get('detail', '')}"
    if event_id in REPORTED_EVENTS:
        continue

    REPORTED_EVENTS.add(event_id)
    log_event(str(event))

    detail = event.get("detail", "").lower()
    comments = event.get("comments", "").lower() if event.get("comments") else ""

    # Goles anulados por VAR
    if event["type"] == "Goal" and (
        "goal cancelled" in detail or
        "goal disallowed" in detail or
        "goal annulled" in detail or
        ("var" in comments and any(x in comments for x in ["offside", "foul", "handball", "goalkeeper interference"]))
    ):
        message = f"Gol anulado por VAR en {home_team} vs {away_team} al minuto {event['time']['elapsed']}."
        send_telegram_message(message)

    # Balón al palo
    palo_variants = ["hit the post", "hit the bar", "post", "bar", "crossbar", "off the post", "off the bar"]
    if event["type"].lower() == "shot" and any(variant in detail for variant in palo_variants):
        message = f"Balón al palo en {home_team} vs {away_team} al minuto {event['time']['elapsed']}."
        send_telegram_message(message)

# Tiros a puerta al minuto 30+
try:
    minute = match_info["fixture"]["status"]["elapsed"]
    if minute and minute >= 30:
        stats_url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/statistics?fixture={fixture_id}"
        stats_res = requests.get(stats_url, headers=HEADERS)
        stats = stats_res.json().get("response", [])
        for team_stat in stats:
            team_name = team_stat["team"]["name"]
            for item in team_stat["statistics"]:
                if item["type"] == "Shots on Goal" and item["value"] is not None and item["value"] >= 4:
                    alert_id = f"{fixture_id}-{team_name}-shots"
                    if alert_id not in REPORTED_EVENTS:
                        REPORTED_EVENTS.add(alert_id)
                        send_telegram_message(f"{team_name} tiene {item['value']} tiros a puerta al minuto {minute} en el partido {home_team} vs {away_team}.")
except Exception as e:
    print(f"Error al verificar tiros a puerta: {e}")

if name == "main": while True: check_matches() time.sleep(15)


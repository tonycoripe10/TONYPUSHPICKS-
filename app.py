import requests
import time
import os
from datetime import datetime

API_KEY = os.getenv('APIkey')
TELEGRAM_TOKEN = os.getenv('Telegramtoken')
CHAT_ID = os.getenv('Chatid')

# IDs de las ligas que estás monitoreando
LEAGUE_IDS = [39, 140, 135, 78, 61, 88, 94, 262, 203, 253, 262]

reported_events = set()

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

def save_event_log(text):
    with open("eventos.txt", "a", encoding="utf-8") as f:
        f.write(text + "\n")

def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"X-Auth-Token": API_KEY}
    response = requests.get(url, headers=headers)
    return response.json()

def process_matches(data):
    for match in data.get("response", []):
        fixture_id = match["fixture"]["id"]
        league_id = match["league"]["id"]
        elapsed = match["fixture"]["status"]["elapsed"]

        if league_id not in LEAGUE_IDS:
            continue

        # Eventos
        events = match.get("events", [])
        for event in events:
            event_id = f"{fixture_id}_{event['time']['elapsed']}_{event['team']['id']}_{event['type']}_{event.get('detail', '')}"
            if event_id in reported_events:
                continue

            reported_events.add(event_id)

            team_name = event['team']['name']
            player = event.get("player", {}).get("name", "Desconocido")
            detail = event.get("detail", "").lower()
            event_type = event.get("type", "")

            log_text = f"{datetime.now()} - {team_name} - {event_type} - {detail}"
            save_event_log(log_text)

            # Balón al palo
            palo_keywords = ["post", "crossbar", "hits the post", "off the post", "off the crossbar"]
            if event_type == "Shot" and any(kw in detail for kw in palo_keywords):
                send_telegram_message(f"Tiro al palo de {player} ({team_name}) en el minuto {event['time']['elapsed']}")
                continue

            # Gol anulado por VAR
            var_keywords = ["goal cancelled", "goal disallowed", "goal annulled"]
            var_reasons = ["offside", "foul", "handball", "goalkeeper interference"]
            if event_type == "Goal":
                full_detail = detail.lower()
                if any(kw in full_detail for kw in var_keywords) or any(reason in full_detail for reason in var_reasons):
                    send_telegram_message(f"¡GOL ANULADO POR VAR! {team_name} - {full_detail}")
                    continue

        # Estadísticas minuto ~30
        if elapsed and 28 <= elapsed <= 32:
            stats = match.get("statistics", [])
            for team_stats in stats:
                team_name = team_stats["team"]["name"]
                values = {item["type"]: item["value"] for item in team_stats["statistics"]}

                shots_on_target = values.get("Shots on Goal")
                xg = values.get("Expected Goals")

                if shots_on_target is not None and shots_on_target >= 4:
                    send_telegram_message(f"{team_name} ha realizado {shots_on_target} tiros a puerta al minuto {elapsed}")

                if xg is not None and isinstance(xg, (int, float)) and xg >= 1.5:
                    send_telegram_message(f"{team_name} tiene {xg} goles esperados al minuto {elapsed}")

while True:
    try:
        matches = get_live_matches()
        process_matches(matches)
    except Exception as e:
        print(f"Error general: {e}")
    time.sleep(15)

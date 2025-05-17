import requests
import time
import os

API_KEY = os.getenv("API_FOOTBALL_KEY")
HEADERS = {"X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}

# Datos del partido a monitorear hoy (Mainz vs Bayer Leverkusen)
LEAGUE_ID = 78  # Bundesliga
DATE = "2025-05-17"

def get_fixtures():
    url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures"
    params = {"date": DATE, "league": LEAGUE_ID, "season": 2024}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    return data.get("response", [])

def get_events(fixture_id):
    url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/events"
    params = {"fixture": fixture_id}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    return data.get("response", [])

def main():
    fixtures = get_fixtures()
    for fixture in fixtures:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        if "Mainz" in home and "Leverkusen" in away:
            fixture_id = fixture["fixture"]["id"]
            print(f"Partido encontrado: {home} vs {away} (ID: {fixture_id})")
            print("Consultando eventos en vivo cada 15 segundos...")
            while True:
                events = get_events(fixture_id)
                print("---- EVENTOS REGISTRADOS ----")
                for event in events:
                    print(event)
                time.sleep(15)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Error general:", str(e))

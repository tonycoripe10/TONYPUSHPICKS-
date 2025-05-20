import requests

API_TOKEN = 'Sportmonks'
headers = {
    'Authorization': f'Bearer {API_TOKEN}',
    'Accept': 'application/json'
}

params = {
    'include': 'events,stats,localTeam,visitorTeam,league',
    'filters[league_id]': '8,39,46,135,61,88,109,262,71,168,78'
}

response = requests.get('https://api.sportmonks.com/v3/football/fixtures/live', headers=headers, params=params)

if response.status_code == 200:
    live_fixtures = response.json()['data']
else:
    print(f'Error al obtener partidos en vivo: {response.status_code} - {response.text}')

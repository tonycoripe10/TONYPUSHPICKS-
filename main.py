import requests
import os

SPORTMONKS_TOKEN = os.getenv("SPORTMONKS_TOKEN")  # o reemplaza con el token directamente

url = "https://api.sportmonks.com/v3/football/livescores"
params = {
    "api_token": SPORTMONKS_TOKEN,
    "include": "participants;league;events;statistics"
}

response = requests.get(url, params=params)

print("Código de estado:", response.status_code)
print("Contenido:", response.text)

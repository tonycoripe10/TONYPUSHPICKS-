import os
import requests
from datetime import datetime
from telegram import Bot

# Cargar variables de entorno desde Railway
SPORTMONKS_TOKEN = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

# IDs de las ligas que te interesan (las principales que mencionaste)
LEAGUES = [
    140,  # LaLiga
    141,  # Segunda España
    39,   # Premier League
    40,   # Championship
    78,   # Bundesliga
    135,  # Serie A
    61,   # Ligue 1
    88,   # Eredivisie
    94,   # Portugal
    262,  # México
    203,  # Brasil
    194,  # Colombia
    195,  # Argentina
    5,    # Libertadores
    6,    # Sudamericana
    253,  # MLS
    2,    # Champions
    3,    # Europa League
    4,    # Conference
    13    # Club World Cup
]

def obtener_resumen():
    hoy = datetime.utcnow().date()
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_TOKEN}&include=participants;league"
    response = requests.get(url)

    if response.status_code != 200:
        return f"Error al obtener los partidos: {response.status_code}"

    data = response.json()
    partidos = data.get("data", [])
    resumen = f"**Resumen de partidos para hoy ({hoy})**\n\n"
    partidos_filtrados = []

    for partido in partidos:
        league_id = partido.get("league_id")
        if league_id in LEAGUES:
            teams = partido.get("participants", [])
            home = next((t for t in teams if t.get("meta", {}).get("location") == "home"), {}).get("name", "Equipo local")
            away = next((t for t in teams if t.get("meta", {}).get("location") == "away"), {}).get("name", "Equipo visitante")
            hora_utc = partido.get("starting_at", {}).get("time", "")[:5]
            league_name = partido.get("league", {}).get("name", "Liga desconocida")
            partidos_filtrados.append((hora_utc, f"{hora_utc} - {home} vs {away} ({league_name})"))

    partidos_filtrados.sort()
    for p in partidos_filtrados:
        resumen += f"{p[1]}\n"

    if not partidos_filtrados:
        resumen += "No hay partidos hoy en las ligas monitoreadas."

    return resumen

def enviar_resumen():
    resumen = obtener_resumen()
    bot = Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=resumen, parse_mode="Markdown")

if __name__ == "__main__":
    enviar_resumen()

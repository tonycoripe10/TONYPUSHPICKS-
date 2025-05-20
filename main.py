import requests
import logging
from datetime import datetime
from telegram import Bot
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Variables de entorno
TELEGRAM_TOKEN = os.environ.get("Telegramtoken")
CHAT_ID = os.environ.get("Chatid")
SPORTMONKS_TOKEN = os.environ.get("Sportmonks")

bot = Bot(token=TELEGRAM_TOKEN)

def obtener_partidos():
    url = "https://api.sportmonks.com/v3/football/fixtures"
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    params = {
        "api_token": SPORTMONKS_TOKEN,
        "filters": f"date={fecha_actual}",
        "include": "localTeam;visitorTeam;league"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        fixtures = data.get("data", [])
        if not fixtures:
            logging.info("No hay partidos para hoy.")
            return "No hay partidos programados para hoy."

        mensajes = []
        for partido in fixtures:
            local = partido["localTeam"]["data"]["name"]
            visitante = partido["visitorTeam"]["data"]["name"]
            liga = partido["league"]["data"]["name"]
            hora = partido.get("time", {}).get("starting_at", {}).get("time", "Hora no disponible")
            mensajes.append(f"{local} vs {visitante} ({liga}) - {hora}")

        return "\n".join(mensajes)

    except requests.exceptions.RequestException as e:
        logging.error(f"[ERROR] Error al obtener partidos: {e}")
        return "Error al obtener los partidos."

def enviar_partidos():
    mensaje = obtener_partidos()
    logging.info(f"[INFO] Mensaje generado:\n{mensaje}")
    try:
        bot.send_message(chat_id=CHAT_ID, text=mensaje)
        logging.info("[INFO] Mensaje enviado a Telegram.")
    except Exception as e:
        logging.error(f"[ERROR] Error al enviar mensaje a Telegram: {e}")

if __name__ == "__main__":
    enviar_partidos()

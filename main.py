import requests
import logging
from datetime import datetime
from telegram import Bot
import os

# Configurar logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Variables de entorno
TELEGRAM_TOKEN   = os.environ.get("Telegramtoken")
CHAT_ID          = os.environ.get("Chatid")
SPORTMONKS_TOKEN = os.environ.get("Sportmonks")

bot = Bot(token=TELEGRAM_TOKEN)

def obtener_partidos():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = (
        f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}"
        f"?api_token={SPORTMONKS_TOKEN}"
        f"&include=localteam;visitorteam;league"
    )
    logging.info(f"Solicitando fixtures del {hoy}")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if not data:
            logging.info("No hay partidos para hoy.")
            return "No hay partidos programados para hoy."

        mensajes = []
        for f in data:
            liga   = f.get("league", {}).get("data", {}).get("name", "Liga desconocida")
            local  = f.get("localteam", {}).get("data", {}).get("name", "Equipo local")
            visit  = f.get("visitorteam", {}).get("data", {}).get("name", "Equipo visitante")
            hora   = f.get("time", {}).get("starting_at", {}).get("time", "Hora no disponible")
            mensajes.append(f"<b>{liga}</b>\n{local} vs {visit} 🕒 {hora}")

        return "\n\n".join(mensajes)

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener partidos: {e}")
        return f"Error al obtener partidos: {e}"

def enviar_partidos():
    mensaje = obtener_partidos()
    logging.info(f"Mensaje generado:\n{mensaje}")
    try:
        bot.send_message(chat_id=CHAT_ID, text=mensaje, parse_mode="HTML")
        logging.info("Mensaje enviado correctamente a Telegram.")
    except Exception as e:
        logging.error(f"Error al enviar mensaje a Telegram: {e}")

if __name__ == "__main__":
    enviar_partidos()

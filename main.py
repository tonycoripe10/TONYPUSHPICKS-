import requests
import logging
from datetime import datetime
from telegram import Bot
import os

# Configurar logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Variables de entorno (Railway)
TELEGRAM_TOKEN   = os.environ.get("Telegramtoken")
CHAT_ID          = os.environ.get("Chatid")
SPORTMONKS_TOKEN = os.environ.get("Sportmonks")

bot = Bot(token=TELEGRAM_TOKEN)

def obtener_partidos():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = (
        f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}"
        f"?api_token={SPORTMONKS_TOKEN}"
        f"&include=participants;league"
    )
    logging.info(f"Solicitando partidos del {hoy}...")

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json().get("data", [])

        if not data:
            logging.info("No hay partidos programados para hoy.")
            return "No hay partidos programados para hoy."

        mensajes = []
        for partido in data:
            liga = partido.get("league", {}).get("data", {}).get("name", "Liga desconocida")
            hora = partido.get("time", {}).get("starting_at", {}).get("time", "Hora no disponible")

            participantes = partido.get("participants", {}).get("data", [])
            local = next((p for p in participantes if p.get("meta", {}).get("location") == "home"), {})
            visitante = next((p for p in participantes if p.get("meta", {}).get("location") == "away"), {})

            local_name = local.get("name", "Equipo local")
            visitante_name = visitante.get("name", "Equipo visitante")

            mensajes.append(f"<b>{liga}</b>\n{local_name} vs {visitante_name} 🕒 {hora}")

        return "\n\n".join(mensajes)

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener partidos: {e}")
        return "Hubo un error al obtener los partidos."

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

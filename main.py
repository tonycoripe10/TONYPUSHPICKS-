import requests
import logging
from datetime import datetime
from telegram import Bot
import os

# Configuración de logs
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
        f"&include=localTeam;visitorTeam;league"
    )
    logging.info(f"Solicitando partidos del {hoy}...")

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if not data:
            return "⚽ <b>No hay partidos programados para hoy.</b>"

        mensaje = f"📅 <b>Partidos para hoy ({hoy}):</b>\n\n"
        for partido in data:
            liga = partido.get("league", {}).get("data", {}).get("name", "Liga desconocida")
            local = partido.get("localTeam", {}).get("data", {}).get("name", "Equipo local")
            visitante = partido.get("visitorTeam", {}).get("data", {}).get("name", "Equipo visitante")
            hora = partido.get("time", {}).get("starting_at", {}).get("time")

            hora_formateada = f"{hora} hs" if hora else "Hora no disponible"

            mensaje += (
                f"⚔️ <b>{local} vs {visitante}</b>\n"
                f"🏆 <i>{liga}</i>\n"
                f"⏰ <i>{hora_formateada}</i>\n"
                f"───────────────\n"
            )

        return mensaje.strip()

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al obtener partidos: {e}")
        return f"❌ Error al obtener partidos: {e}"

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

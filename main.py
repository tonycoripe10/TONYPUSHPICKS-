# main.py

import os
import requests
import time
import schedule
from datetime import datetime
import pytz
import logging

from telegram import Bot

# Configurar logs
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
logger = logging.getLogger()

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")
SPORTMONKS_TOKEN = os.getenv("APIkey")

# Ligas a monitorear (IDs reales de Sportmonks v3)
LIGAS_MONITOREADAS = {
    140, 141,  # España Primera y Segunda
    2, 3,      # Inglaterra Primera y Segunda
    82,        # Alemania Primera
    5,         # Italia Primera
    9,         # Francia Primera
    94,        # Holanda Primera
    262,       # Portugal Primera
    203,       # México Primera
    4,         # Brasil Primera
    151,       # Colombia Primera
    152,       # Argentina Primera
    235,       # Copa Libertadores
    253,       # Copa Sudamericana
    5,         # MLS
    6,         # Champions League
    7,         # Europa League
    8,         # Conference League
    13         # Club World Cup
}

# Inicializar bot de Telegram
bot = Bot(token=TELEGRAM_TOKEN)

# Emojis para notificaciones
EMOJIS = {
    "var": "\u26a0\ufe0f",
    "palo": "\ud83d\udd39",
    "remates": "\ud83c\udfcb\ufe0f",
    "xg": "\ud83d\udd22",
    "amarilla": "\ud83d\udfe1",
    "futbol": "\u26bd",
    "reloj": "\u23f0",
    "bandera": "\ud83c\udff4"
}

# Obtener partidos en vivo

def obtener_partidos_en_vivo():
    url = "https://api.sportmonks.com/v3/football/livescores/inplay"
    params = {
        "api_token": APIkey,
        "include": "events;statistics;participants;league;season"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json().get("data", [])
        partidos = [p for p in data if p.get("league_id") in LIGAS_MONITOREADAS]
        logger.info(f"Partidos en vivo: {len(partidos)}")
        return partidos
    except Exception as e:
        logger.error(f"Error al obtener partidos en vivo: {e}")
        return []

# Enviar mensaje a Telegram

def enviar_mensaje(texto):
    try:
        bot.send_message(chat_id=CHAT_ID, text=texto, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error al enviar mensaje: {e}")

# Construir alerta detallada

def construir_alerta(evento, tipo):
    fixture = evento.get("fixture_id")
    equipo = evento.get("team", {}).get("name", "Equipo desconocido")
    minuto = evento.get("minute", "?")
    comentario = evento.get("text", "")

    texto = f"{EMOJIS.get(tipo, '')} <b>{tipo.upper()}</b> en el minuto {minuto}\n"
    texto += f"{EMOJIS['futbol']} Equipo: <b>{equipo}</b>\n"
    texto += f"{EMOJIS['reloj']} Comentario: {comentario}"
    return texto

# Analizar eventos de un partido

def analizar_eventos(partido):
    eventos = partido.get("events", [])
    for evento in eventos:
        tipo = evento.get("type")
        comentario = evento.get("text", "").lower()
        minuto = evento.get("minute", 0)

        if tipo == "goal_cancelled" or (
            "var" in comentario and
            any(palabra in comentario for palabra in ["offside", "handball", "foul", "goalkeeper"])
        ):
            alerta = construir_alerta(evento, "var")
            enviar_mensaje(alerta)

        if any(p in comentario for p in ["post", "bar", "crossbar", "off the woodwork"]):
            alerta = construir_alerta(evento, "palo")
            enviar_mensaje(alerta)

        if tipo == "card" and "yellow" in comentario and minuto <= 9:
            alerta = construir_alerta(evento, "amarilla")
            enviar_mensaje(alerta)

# Verificar partidos en vivo periódicamente

def verificar_partidos():
    logger.info("Verificando partidos en vivo...")
    partidos = obtener_partidos_en_vivo()
    for partido in partidos:
        analizar_eventos(partido)

# Enviar resumen diario (provisionalmente a las 20:30 para pruebas)

def resumen_diario():
    ahora = datetime.now(pytz.timezone('Europe/Madrid')).strftime('%Y-%m-%d')
    mensaje = f"\u2728 <b>Resumen de Partidos para hoy {ahora}</b>\n"
    mensaje += f"{EMOJIS['futbol']} Ligas monitoreadas: {len(LIGAS_MONITOREADAS)}\n"
    mensaje += f"{EMOJIS['reloj']} Este es un mensaje de prueba."
    enviar_mensaje(mensaje)

# Programar tareas
schedule.every(40).seconds.do(verificar_partidos)
schedule.every().day.at("21:15").do(resumen_diario)  # horario provisional de prueba

if __name__ == "__main__":
    logger.info("[BOT] Iniciado correctamente. Esperando eventos...")
    while True:
        schedule.run_pending()
        time.sleep(1)

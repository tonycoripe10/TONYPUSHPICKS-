# main.py
import requests
import os
from datetime import datetime

# VARIABLES DESDE RAILWAY
SPORTMONKS_API_KEY = os.getenv("Sportmonks")
TELEGRAM_BOT_TOKEN = os.getenv("Telegramtoken")
TELEGRAM_CHAT_ID = os.getenv("Chatid")

LEAGUE_IDS = [
    8, 564, 384, 82, 301, 271, 556, 5, 7, 6,
    384, 262, 390, 395, 11, 12, 748, 514
]

def obtener_partidos_de_hoy():
    hoy = datetime.now().strftime('%Y-%m-%d')
    url = f'https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=league,localTeam,visitorTeam,time'

    try:
        response = requests.get(url)
        response.raise_for_status()
        datos = response.json()
        partidos = datos.get('data', [])

        mensaje = f"<b>=== Partidos del {hoy} ===</b>\n\n"

        if not partidos:
            mensaje += "No hay partidos programados para hoy."
            return mensaje

        for partido in partidos:
            liga_id = partido.get('league', {}).get('id')
            if liga_id not in LEAGUE_IDS:
                continue

            liga = partido.get('league', {}).get('name', 'Desconocida')
            local = partido.get('localTeam', {}).get('name', 'Local')
            visitante = partido.get('visitorTeam', {}).get('name', 'Visitante')
            hora = partido.get('time', {}).get('starting_at', {}).get('time', 'Hora desconocida')

            mensaje += f"<b>{liga}</b>\n"
            mensaje += f"<i>{local}</i> vs <i>{visitante}</i> 🕒 {hora}\n\n"

        return mensaje.strip()

    except requests.RequestException as e:
        return f"Error al obtener partidos: {e}"

def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': mensaje,
        'parse_mode': 'HTML'
    }

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("Mensaje enviado correctamente al grupo.")
    except requests.RequestException as e:
        print("Error al enviar mensaje a Telegram:", e)

if __name__ == "__main__":
    mensaje = obtener_partidos_de_hoy()
    enviar_mensaje_telegram(mensaje)

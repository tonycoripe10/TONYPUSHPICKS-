import os
import asyncio
import aiohttp
from datetime import datetime

TELEGRAM_TOKEN = os.getenv('Telegramtoken')
CHAT_ID = os.getenv('Chatid')
SPORTMONKS_TOKEN = os.getenv('SportmonksToken')  # Asegúrate de configurarlo en Railway

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Ligas que vamos a monitorear (puedes agregar o quitar si hace falta)
MONITORED_LEAGUES = [
    501, 502,        # España 1 y 2
    524, 525,        # Inglaterra 1 y 2
    82,              # Alemania 1
    384,             # Italia 1
    301,             # Francia 1
    194,             # Holanda 1
    153,             # Portugal 1
    244,             # México 1
    129,             # Brasil 1
    118,             # Colombia 1
    1,               # Argentina 1
    384, 906,        # Libertadores y Sudamericana
    256,             # MLS
    2, 5, 1327, 1005 # Champions, Europa, Conference, Mundial Clubes
]

async def send_telegram_message(session, text):
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    async with session.post(TELEGRAM_API_URL, data=payload) as resp:
        if resp.status != 200:
            print(f"[!] Error al enviar mensaje: {resp.status}")
        else:
            print(f"[{datetime.now()}] Mensaje enviado con éxito")

async def get_live_matches(session):
    url = f"https://api.sportmonks.com/v3/football/fixtures?include=scores,participants,league&status=LIVE"
    headers = {"Authorization": f"Bearer {SPORTMONKS_TOKEN}"}

    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            print(f"[!] Error al consultar partidos en vivo: {response.status}")
            return []

        data = await response.json()
        live_matches = []

        for match in data.get('data', []):
            league_id = match.get('league', {}).get('id')
            if league_id in MONITORED_LEAGUES:
                live_matches.append(match)

        return live_matches

async def monitor_matches():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                live_matches = await get_live_matches(session)
                if live_matches:
                    print(f"[{datetime.now()}] Partidos en vivo encontrados: {len(live_matches)}")
                else:
                    print(f"[{datetime.now()}] Sin partidos en vivo")

                # Aquí después añadiremos la lógica de alertas
                await asyncio.sleep(40)

            except Exception as e:
                print(f"[!] Error inesperado: {e}")
                await asyncio.sleep(40)

async def main():
    print("Bot iniciado. Esperando partidos en vivo...")
    await monitor_matches()

if __name__ == "__main__":
    asyncio.run(main())

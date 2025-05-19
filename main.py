import os
import asyncio
import aiohttp

TELEGRAM_TOKEN = os.getenv('Telegramtoken')
CHAT_ID = os.getenv('Chatid')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

async def send_telegram_message(session, text):
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    async with session.post(TELEGRAM_API_URL, data=payload) as resp:
        if resp.status == 200:
            print("Mensaje enviado correctamente")
        else:
            print(f"Error al enviar mensaje: {resp.status}")

async def main():
    async with aiohttp.ClientSession() as session:
        await send_telegram_message(session, "¡Bot iniciado correctamente!")

if __name__ == "__main__":
    asyncio.run(main())

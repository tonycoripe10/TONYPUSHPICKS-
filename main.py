import os
import requests
import datetime
import telegram

SPORTMONKS_API_KEY = os.getenv("Sportmonks")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
TELEGRAM_CHAT_ID = os.getenv("Chatid")

def obtener_partidos():
    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    print(f"[INFO] Solicitando partidos del {hoy}...")

    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=participants"
    response = requests.get(url)
    data = response.json()

    if "data" not in data:
        return "[ERROR] No se encontraron partidos."

    partidos = data["data"]
    if not partidos:
        return "Hoy no hay partidos programados."

    mensaje = f"Partidos para hoy ({hoy}):\n\n"
    for partido in partidos:
        participantes = partido.get("participants", [])

        local = visitante = "Por definir"
        for p in participantes:
            if p.get("meta", {}).get("location") == "home":
                local = p.get("name", "Desconocido")
            elif p.get("meta", {}).get("location") == "away":
                visitante = p.get("name", "Desconocido")

        hora = partido.get("time", {}).get("starting_at", {}).get("time", "Hora no disponible")
        mensaje += f"{local} vs {visitante} - {hora}\n"

    return mensaje.strip()

def enviar_partidos():
    mensaje = obtener_partidos()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje)

if __name__ == "__main__":
    enviar_partidos()

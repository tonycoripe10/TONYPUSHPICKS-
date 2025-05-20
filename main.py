import os
import requests
import datetime
import time
import telegram
import pytz  # Añadido para manejo de zona horaria

SPORTMONKS_API_KEY = os.getenv("Sportmonks")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
TELEGRAM_CHAT_ID = os.getenv("Chatid")

bot = telegram.Bot(token=TELEGRAM_TOKEN)
PARTIDOS_DEL_DIA = []

def obtener_partidos():
    global PARTIDOS_DEL_DIA
    hoy = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[INFO] Solicitando partidos del {hoy}...")

    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=participants;league.country"
    response = requests.get(url)
    try:
        data = response.json()
    except Exception as e:
        print(f"[ERROR] Respuesta inválida: {e}")
        return "[ERROR] No se pudieron obtener los partidos."

    if "data" not in data:
        print("[ERROR] No se encontraron datos en la respuesta.")
        return "[ERROR] No se encontraron partidos."

    partidos = data["data"]
    if not partidos:
        print("[INFO] No hay partidos programados para hoy.")
        return "📭 *Hoy no hay partidos programados.*"

    utc = pytz.utc
    madrid = pytz.timezone("Europe/Madrid")

    mensaje = f"📅 *Partidos para hoy* ({hoy}):\n\n"
    for partido in partidos:
        PARTICIPANTES = partido.get("participants", [])
        local = visitante = "Por definir"
        for p in PARTICIPANTES:
            if p.get("meta", {}).get("location") == "home":
                local = p.get("name", "Desconocido")
            elif p.get("meta", {}).get("location") == "away":
                visitante = p.get("name", "Desconocido")

        hora_iso = partido.get("starting_at", {}).get("date_time")
        hora_partido = None
        if hora_iso:
            hora_utc = datetime.datetime.fromisoformat(hora_iso.replace("Z", "+00:00"))
            hora_utc = utc.localize(hora_utc)
            hora_partido = hora_utc.astimezone(madrid)

        liga = partido.get("league", {}).get("name", "Liga desconocida")
        pais = partido.get("league", {}).get("country", {}).get("name", "País desconocido")

        mensaje += (
            f"⚽ *{local}* vs *{visitante}*\n"
            f"🏆 Liga: _{liga}_ ({pais})\n"
            f"🕒 Hora: {hora_partido.strftime('%H:%M (%Z)') if hora_partido else 'No disponible'}\n\n"
        )

        if hora_partido:
            PARTIDOS_DEL_DIA.append({
                "id": partido["id"],
                "hora": hora_partido,
                "local": local,
                "visitante": visitante
            })

        print(f"[INFO] Partido registrado: {local} vs {visitante} - ID {partido['id']}")

    return mensaje.strip()

# El resto del código permanece igual...

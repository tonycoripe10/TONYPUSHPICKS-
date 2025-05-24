import datetime
import pytz
import requests
import os
from utils import enviar_mensaje, session

SPORTMONKS_API_KEY = os.getenv("Sportmonks")
utc = pytz.utc
madrid = pytz.timezone("Europe/Madrid")

PARTIDOS_DEL_DIA = []

def obtener_partidos():
    global PARTIDOS_DEL_DIA
    hoy = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=participants;league.country"

    try:
        response = session.get(url, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"[ERROR] No se pudo obtener partidos: {e}")
        return "[ERROR] No se pudieron obtener los partidos."

    if "data" not in data or not data["data"]:
        return "📬 *Hoy no hay partidos programados.*"

    mensaje = f"🗓️ *Partidos para hoy* ({hoy}):\n\n"
    for partido in data["data"]:
        PARTICIPANTES = partido.get("participants", [])
        local = visitante = "Por definir"
        for p in PARTICIPANTES:
            if p.get("meta", {}).get("location") == "home":
                local = p.get("name", "Desconocido")
            elif p.get("meta", {}).get("location") == "away":
                visitante = p.get("name", "Desconocido")

        hora_iso = partido.get("starting_at")
        if hora_iso:
            hora_utc = datetime.datetime.fromisoformat(hora_iso.replace("Z", "+00:00"))
            hora_utc = utc.localize(hora_utc)
            hora_partido = hora_utc.astimezone(madrid)
        else:
            hora_partido = None

        liga = partido.get("league", {}).get("name", "Liga desconocida")
        pais = partido.get("league", {}).get("country", {}).get("name", "País desconocido")

        mensaje += (
            f"⚽ *{local}* vs *{visitante}*\n"
            f"🏆 Liga: _{liga}_ ({pais})\n"
            f"🕒 Hora: {hora_partido.strftime('%H:%M %Z') if hora_partido else 'No disponible'}\n\n"
        )

        if hora_partido:
            PARTIDOS_DEL_DIA.append({
                "id": partido["id"],
                "hora": hora_partido,
                "local": local,
                "visitante": visitante
            })

    return mensaje.strip()

def enviar_resumen_diario():
    mensaje = obtener_partidos()
    enviar_mensaje(mensaje)
    return PARTIDOS_DEL_DIA

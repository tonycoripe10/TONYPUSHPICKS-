import os
import requests
import datetime
import time
import telegram

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
        hora_partido = datetime.datetime.fromisoformat(hora_iso.replace("Z", "+00:00")) if hora_iso else None
        liga = partido.get("league", {}).get("name", "Liga desconocida")
        pais = partido.get("league", {}).get("country", {}).get("name", "País desconocido")

        mensaje += (
            f"⚽ *{local}* vs *{visitante}*\n"
            f"🏆 Liga: _{liga}_ ({pais})\n"
            f"🕒 Hora: {hora_partido.strftime('%H:%M UTC') if hora_partido else 'No disponible'}\n\n"
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

def monitorear_eventos():
    ya_reportados = set()
    estados_previos = {}
    partidos_pendientes = PARTIDOS_DEL_DIA.copy()
    print(f"[INFO] Monitoreo preparado para {len(partidos_pendientes)} partidos...")

    while partidos_pendientes:
        ahora = datetime.datetime.utcnow()
        for partido in partidos_pendientes[:]:
            fixture_id = partido["id"]
            hora_inicio = partido["hora"]
            if ahora < hora_inicio - datetime.timedelta(minutes=5):
                continue

            url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events"
            response = requests.get(url)
            try:
                data = response.json()
            except Exception as e:
                print(f"[ERROR] Error al obtener datos del fixture {fixture_id}: {e}")
                continue

            fixture = data.get("data", {})
            status = fixture.get("status", {}).get("type")

            # Detectar cambios de estado
            estado_anterior = estados_previos.get(fixture_id)
            if status != estado_anterior:
                if status == "live":
                    mensaje_inicio = f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado."
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje_inicio, parse_mode=telegram.ParseMode.MARKDOWN)
                    print(f"[INFO] Partido {fixture_id} ha comenzado.")
                elif status in ["finished", "cancelled"]:
                    mensaje_fin = f"✅ *{partido['local']} vs {partido['visitante']}* ha finalizado ({status})."
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje_fin, parse_mode=telegram.ParseMode.MARKDOWN)
                    print(f"[INFO] Partido {fixture_id} ha terminado ({status}).")
                    partidos_pendientes.remove(partido)

                estados_previos[fixture_id] = status

            if status != "live":
                continue

            eventos = fixture.get("events", [])
            for evento in eventos:
                evento_id = evento.get("id")
                if evento_id and evento_id not in ya_reportados:
                    tipo = evento.get("type", "Evento")
                    minuto = evento.get("minute", "¿?")
                    jugador = evento.get("player", {}).get("name", "Jugador desconocido")
                    equipo = evento.get("team", {}).get("name", "Equipo")

                    mensaje = f"📢 *{tipo}* - {equipo}\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    print(f"[EVENTO] {tipo} | {equipo} | {jugador} | Min {minuto}")
                    try:
                        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode=telegram.ParseMode.MARKDOWN)
                        print(f"[ENVIADO] Evento ID {evento_id} enviado")
                    except Exception as e:
                        print(f"[ERROR] Error al enviar evento: {e}")
                    ya_reportados.add(evento_id)

        print("[INFO] Esperando 40 segundos para siguiente verificación...")
        time.sleep(40)

def enviar_partidos():
    mensaje = obtener_partidos()
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode=telegram.ParseMode.MARKDOWN)
        print("[INFO] Resumen de partidos enviado.")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar el resumen: {e}")

if __name__ == "__main__":
    enviar_partidos()
    monitorear_eventos()

import os
import requests
import datetime
import time
import telegram
import pytz

SPORTMONKS_API_KEY = os.getenv("Sportmonks")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
TELEGRAM_CHAT_ID = os.getenv("Chatid")

bot = telegram.Bot(token=TELEGRAM_TOKEN)
PARTIDOS_DEL_DIA = []

utc = pytz.utc
madrid = pytz.timezone("Europe/Madrid")

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

        hora_iso = partido.get("starting_at")
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
            f"🕒 Hora: {hora_partido.strftime('%H:%M %Z') if hora_partido else 'No disponible'}\n\n"
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
        ahora = datetime.datetime.now(madrid)

        partidos_activos = [
            partido for partido in partidos_pendientes
            if ahora >= partido["hora"] - datetime.timedelta(minutes=5)
        ]

        if not partidos_activos:
            print("[INFO] No hay partidos en juego o próximos. Esperando 30 minutos...")
            time.sleep(1800)
            continue

        for partido in partidos_activos:
            fixture_id = partido["id"]
            hora_inicio = partido["hora"]

            url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events"
            response = requests.get(url)
            try:
                data = response.json()
            except Exception as e:
                print(f"[ERROR] Error al obtener datos del fixture {fixture_id}: {e}")
                continue

            fixture = data.get("data", {})
            status = fixture.get("status", {}).get("type")
            estado_anterior = estados_previos.get(fixture_id)

            if fixture_id not in estados_previos:
                estados_previos[fixture_id] = status
                if status and "INPLAY" in status:
                    mensaje_inicio = f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado."
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje_inicio, parse_mode=telegram.ParseMode.MARKDOWN)
                    print(f"[INFO] Partido {fixture_id} ya está en juego desde el primer chequeo.")
                continue

            if status != estado_anterior:
                if status and "INPLAY" in status:
                    mensaje_inicio = f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado."
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje_inicio, parse_mode=telegram.ParseMode.MARKDOWN)
                    print(f"[INFO] Partido {fixture_id} ha comenzado.")
                elif status in ["FT", "CANCELLED"]:
                    mensaje_fin = f"✅ *{partido['local']} vs {partido['visitante']}* ha finalizado ({status})."
                    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje_fin, parse_mode=telegram.ParseMode.MARKDOWN)
                    print(f"[INFO] Partido {fixture_id} ha terminado ({status}).")
                    partidos_pendientes.remove(partido)

                estados_previos[fixture_id] = status

            if not (status and "INPLAY" in status):
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

        print(f"[INFO] Verificación completada. Partidos activos: {len(partidos_activos)}")
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

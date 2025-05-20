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
    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
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

        hora = partido.get("starting_at", "Hora no disponible")
        liga = partido.get("league", {}).get("name", "Liga desconocida")
        pais = partido.get("league", {}).get("country", {}).get("name", "País desconocido")

        mensaje += (
            f"⚽ *{local}* vs *{visitante}*\n"
            f"🏆 Liga: _{liga}_ ({pais})\n"
            f"🕒 Hora: {hora}\n\n"
        )

        PARTIDOS_DEL_DIA.append(partido["id"])
        print(f"[INFO] Partido registrado: {local} vs {visitante} - ID {partido['id']}")

    return mensaje.strip()

def monitorear_eventos():
    ya_reportados = set()
    print(f"[INFO] Comenzando monitoreo de eventos para {len(PARTIDOS_DEL_DIA)} partidos...")

    while True:
        for fixture_id in PARTIDOS_DEL_DIA:
            url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events"
            response = requests.get(url)
            try:
                data = response.json()
            except Exception as e:
                print(f"[ERROR] Error al obtener datos del fixture {fixture_id}: {e}")
                continue

            eventos = data.get("data", {}).get("events", [])
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
                        print(f"[ENVIADO] Alerta enviada por evento ID {evento_id}")
                    except Exception as e:
                        print(f"[ERROR] No se pudo enviar mensaje Telegram: {e}")
                    ya_reportados.add(evento_id)

        print("[INFO] Esperando 40 segundos para siguiente verificación...")
        time.sleep(40)

def enviar_partidos():
    mensaje = obtener_partidos()
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode=telegram.ParseMode.MARKDOWN)
        print("[INFO] Resumen de partidos enviado por Telegram.")
    except Exception as e:
        print(f"[ERROR] No se pudo enviar el resumen de partidos: {e}")

if __name__ == "__main__":
    enviar_partidos()
    monitorear_eventos()

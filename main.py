import os
import requests
import datetime
import time
import telegram
import pytz
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Variables de entorno
SPORTMONKS_API_KEY = os.getenv("Sportmonks")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
TELEGRAM_CHAT_ID = os.getenv("Chatid")

bot = telegram.Bot(token=TELEGRAM_TOKEN)
PARTIDOS_DEL_DIA = []

# Zonas horarias
utc = pytz.utc
madrid = pytz.timezone("Europe/Madrid")

# Estados considerados como "en juego"
ESTADOS_EN_JUEGO = {"INPLAY_1ST_HALF", "INPLAY_2ND_HALF", "ET", "PEN_LIVE", "HT"}

# Sesión con reintentos
session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def enviar_mensaje(mensaje):
    try:
        print(f"[ENVÍO] Enviando mensaje Telegram:\n{mensaje}")
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode=telegram.ParseMode.MARKDOWN)
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo enviar mensaje: {e}")
        return False

def obtener_partidos():
    global PARTIDOS_DEL_DIA
    ahora_madrid = datetime.datetime.now(madrid)
    hoy_es = ahora_madrid.date()
    print(f"[INFO] Fecha en Madrid: {hoy_es}")

    fechas_consulta = [
        (ahora_madrid.astimezone(pytz.utc)).strftime("%Y-%m-%d"),
        (ahora_madrid + datetime.timedelta(days=1)).astimezone(pytz.utc).strftime("%Y-%m-%d")
    ]

    partidos_totales = []
    for fecha_utc in fechas_consulta:
        print(f"[INFO] Solicitando partidos del {fecha_utc} (UTC)...")
        url = f"https://api.sportmonks.com/v3/football/fixtures/date/{fecha_utc}?api_token={SPORTMONKS_API_KEY}&include=participants;league.country"
        try:
            response = session.get(url, timeout=10)
            data = response.json()
            partidos_totales.extend(data.get("data", []))
        except Exception as e:
            print(f"[ERROR] No se pudo obtener partidos del {fecha_utc}: {e}")

    if not partidos_totales:
        return "📬 *Hoy no hay partidos programados.*"

    mensaje = f"📆 *Partidos del día para hoy* ({hoy_es}):\n\n"

    for partido in partidos_totales:
        estado = partido.get("status", {}).get("state", "")
        if estado in ["FT", "CANCELLED", "POSTPONED", "AWARDED"]:
            continue

        hora_iso = partido.get("starting_at")
        if not hora_iso:
            continue

        hora_utc = datetime.datetime.fromisoformat(hora_iso.replace("Z", "+00:00")).astimezone(utc)
        hora_local = hora_utc.astimezone(madrid)
        if hora_local.date() != hoy_es:
            continue

        PARTICIPANTES = partido.get("participants", [])
        local = visitante = "Por definir"
        for p in PARTICIPANTES:
            if p.get("meta", {}).get("location") == "home":
                local = p.get("name", "Desconocido")
            elif p.get("meta", {}).get("location") == "away":
                visitante = p.get("name", "Desconocido")

        mensaje += (
            f"⚽ *{local}* vs *{visitante}*\n"
            f"🕒 Hora: {hora_local.strftime('%H:%M %Z')}\n\n"
        )

        PARTIDOS_DEL_DIA.append({
            "id": partido["id"],
            "hora": hora_local,
            "local": local,
            "visitante": visitante
        })

        print(f"[INFO] Partido registrado: {local} vs {visitante} - {hora_local}")

    return mensaje.strip()

def obtener_fixture(fixture_id):
    url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events;status"
    try:
        response = session.get(url, timeout=10)
        return response.json().get("data", {})
    except Exception as e:
        print(f"[ERROR] Falló la consulta del fixture {fixture_id}: {e}")
        return {}

def monitorear_eventos():
    ya_reportados = set()
    estados_previos = {}
    partidos_pendientes = PARTIDOS_DEL_DIA.copy()
    tiros_reportados = set()
    tarjetas_tempranas_reportadas = set()

    print(f"[INFO] Monitoreo preparado para {len(partidos_pendientes)} partidos...")

    while partidos_pendientes:
        ahora = datetime.datetime.now(madrid)
        print(f"[TRACE] Verificando eventos a las {ahora.strftime('%H:%M:%S')}")
        partidos_activos = []
        for p in partidos_pendientes:
            print(f"[HORA] Partido {p['id']} - Programado a {p['hora']} | Ahora: {ahora}")
            if p["hora"] - datetime.timedelta(minutes=5) <= ahora:
                partidos_activos.append(p)

        print("[TRACE] Partidos activos detectados:", [f"{p['local']} vs {p['visitante']}" for p in partidos_activos])

        if not partidos_activos:
            print(f"[INFO] Ningún partido ha empezado aún a las {ahora.strftime('%H:%M:%S')}. Reintento en 10 minutos...")
            time.sleep(600)
            continue

        for partido in partidos_activos:
            fixture_id = partido["id"]
            fixture = obtener_fixture(fixture_id)

            # ⬇️ NUEVOS PRINTS DE DEPURACIÓN
            print(f"[DEBUG] fixture completo recibido: {fixture}")
            print(f"[DEBUG] fixture.get('status'): {fixture.get('status')}")

            if not fixture:
                print(f"[AVISO] No se pudo obtener información del partido {fixture_id}. Se eliminará del monitoreo.")
                partidos_pendientes.remove(partido)
                continue

            status = fixture.get("status", {}).get("state")
            print(f"[DEPURACIÓN] Status recibido: {status} para partido {partido['local']} vs {partido['visitante']}")
            estado_anterior = estados_previos.get(fixture_id)
            print(f"[DEBUG] Estado recibido del fixture {fixture_id}: {status}")

            if fixture_id not in estados_previos:
                print(f"[TRACE] Primer estado del partido {fixture_id}: {status}")
                if status in ESTADOS_EN_JUEGO:
                    print(f"[INFO] Detectado partido EN JUEGO por primera vez: {partido['local']} vs {partido['visitante']}")
                    enviar_mensaje(f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado.")
                elif status in ["FT", "CANCELLED"]:
                    mensaje = f"⚠️ *{partido['local']} vs {partido['visitante']}* no se jugará. Estado: {status}"
                    enviar_mensaje(mensaje)
                    partidos_pendientes.remove(partido)

                estados_previos[fixture_id] = status
                continue

            if status != estado_anterior:
                print(f"[TRACE] Cambio de estado en partido {fixture_id}: {estado_anterior} -> {status}")
                if status in ESTADOS_EN_JUEGO:
                    enviar_mensaje(f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado.")
                elif status in ["FT", "CANCELLED"]:
                    enviar_mensaje(f"✅ *{partido['local']} vs {partido['visitante']}* ha finalizado ({status}).")
                    partidos_pendientes.remove(partido)
                estados_previos[fixture_id] = status

            if status not in ESTADOS_EN_JUEGO:
                continue

            for evento in fixture.get("events", []):
                print(f"[TRACE] Eventos encontrados: {len(fixture.get('events', []))}")
                evento_id = evento.get("id")
                if not evento_id or evento_id in ya_reportados:
                    continue

                tipo = evento.get("type", "evento").lower()
                minuto = evento.get("minute", 0)
                jugador = evento.get("player", {}).get("name", "Jugador desconocido")
                equipo = evento.get("team", {}).get("name", "Equipo")
                resultado = evento.get("result", "")
                detalles = evento.get("details", "")

                print(f"[TRACE] Evento detectado: {tipo} ({evento_id}) - {equipo} {minuto}'")

                if tipo == "goal":
                    if resultado == "under_review":
                        mensaje = f"😮 Posible *GOL* para *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto} *(revisión VAR)*"
                    elif resultado == "confirmed":
                        mensaje = f"✅ *GOL CONFIRMADO* de *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    elif resultado == "cancelled":
                        mensaje = f"❌ *GOL ANULADO* para *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    else:
                        mensaje = f"⚽ *GOL* de *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    if enviar_mensaje(mensaje):
                        ya_reportados.add(evento_id)
                    continue

                if tipo in ["hit-woodwork"]:
                    mensaje = f"🏕️ *{tipo.upper()}* - {equipo}\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    if enviar_mensaje(mensaje):
                        ya_reportados.add(evento_id)
                    continue

                if tipo == "yellowcard" and minuto <= 9:
                    clave = (fixture_id, equipo)
                    if clave not in tarjetas_tempranas_reportadas:
                        mensaje = f"🟨 *{equipo}* recibe tarjeta amarilla antes del minuto 10\n👤 {jugador}\n⏱️ Minuto {minuto}"
                        if enviar_mensaje(mensaje):
                            tarjetas_tempranas_reportadas.add(clave)
                        ya_reportados.add(evento_id)
                    continue

            stats_url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}/statistics?api_token={SPORTMONKS_API_KEY}"
            try:
                stats_response = session.get(stats_url, timeout=10).json()
                stats_data = stats_response.get("data", [])
                print(f"[TRACE] Estadísticas obtenidas para fixture {fixture_id}")
            except Exception as e:
                print(f"[ERROR] Fallo en estadísticas del fixture {fixture_id}: {e}")
                continue

            for stat in stats_data:
                team_name = stat.get("team", {}).get("name", "Equipo")
                stats_list = stat.get("statistics", [])
                for item in stats_list:
                    if item.get("type") == "shots_on_target":
                        cantidad = int(item.get("value", 0))
                        clave = (fixture_id, team_name)
                        if cantidad >= 4 and clave not in tiros_reportados and ahora <= partido["hora"] + datetime.timedelta(minutes=30):
                            print(f"[TRACE] {team_name} ha alcanzado {cantidad} tiros a puerta antes del minuto 30.")
                            mensaje = f"📊 *{team_name}* ha realizado 4+ tiros a puerta antes del minuto 30."
                            if enviar_mensaje(mensaje):
                                tiros_reportados.add(clave)

        print("[INFO] Verificación completada. Esperando 40 segundos...\n")
        time.sleep(40)

def enviar_partidos():
    mensaje = obtener_partidos()
    enviar_mensaje(mensaje)

if __name__ == "__main__":
    enviar_partidos()
    try:
        monitorear_eventos()
    except Exception as e:
        print(f"[CRÍTICO] El bot se ha detenido por un error inesperado: {e}") 
    

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
    hoy = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    print(f"[INFO] Solicitando partidos del {hoy}...")

    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=participants;league.country"
    try:
        response = session.get(url, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"[ERROR] No se pudo obtener partidos: {e}")
        return "[ERROR] No se pudieron obtener los partidos."

    if "data" not in data:
        print("[ERROR] Respuesta sin datos.")
        return "[ERROR] No se encontraron partidos."

    partidos = data["data"]
    if not partidos:
        return "📬 *Hoy no hay partidos programados.*"

    mensaje = f"📆 *Partidos del día para hoy* ({hoy}):\n\n"
    for partido in partidos:
        liga = partido.get("league", {}).get("name", "")
        pais = partido.get("league", {}).get("country", {}).get("name", "")
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

        mensaje += (
            f"⚽ *{local}* vs *{visitante}*\n"
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

def obtener_fixture(fixture_id):
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{fecha}?api_token=TU_API_TOKEN&include=participants;league.country"

    try:
        response = session.get(url, timeout=10)
        fixture = response.json().get("data", {})
        print(f"[DEBUG] Fixture completo:\n{fixture}")
        return fixture
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
    ahora = datetime.datetime.now(pytz.utc)

    while partidos_pendientes:
        print(f"[TRACE] Verificando eventos a las {ahora.strftime('%H:%M:%S')}")
        for p in partidos_pendientes:
            print(f"[HORA] Partido {p['id']} - Programado a {p['hora']} | Ahora: {ahora} | Diferencia: {(ahora - p['hora']).total_seconds()}s")

        partidos_activos = [p for p in partidos_pendientes if ahora >= p["hora"] - datetime.timedelta(minutes=5)]

        if not partidos_activos:
            print("[INFO] Ningún partido ha empezado aún. Reintento en 10 minutos...")
            time.sleep(600)
            ahora += datetime.timedelta(minutes=10)
            continue

        for partido in partidos_activos:
            fixture_id = partido["id"]
            fixture = obtener_fixture(fixture_id)
            print(f"[DEBUG] JSON crudo del fixture {fixture_id}:\n{fixture}")

            if not fixture:
                continue

            status = fixture.get("status", {}).get("state")
            estado_anterior = estados_previos.get(fixture_id)
            print(f"[ESTADO] Partido {fixture_id} - Estado actual: {status} | Estado anterior: {estado_anterior}")

            if fixture_id not in estados_previos:
                print(f"[TRACE] Primer estado del partido {fixture_id}: {status}")
                if status in ESTADOS_EN_JUEGO:
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
                    mensaje = f"🍅 *{tipo.upper()}* - {equipo}\n👤 {jugador}\n⏱️ Minuto {minuto}"
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
                    tipo_tiro = item.get("type")
                    valor_tiro = item.get("value")
                    print(f"[TIRO] Tipo: {tipo_tiro} | Valor: {valor_tiro} | Equipo: {team_name}")
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
    monitorear_eventos()

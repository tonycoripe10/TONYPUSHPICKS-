import os
import time
import datetime
import requests
import pytz
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")
SPORTMONKS_API_KEY = os.getenv("Sportmonks")

# Zona horaria de Madrid
madrid = pytz.timezone("Europe/Madrid")

# Estados de partido en juego
ESTADOS_EN_JUEGO = ["LIVE", "HT", "ET", "P", "BREAK", "FT_PEN", "AET"]

# Inicializar sesión global para peticiones
session = requests.Session()

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown"
    }
    try:
        response = session.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Error al enviar mensaje: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Excepción al enviar mensaje: {e}")
        return False

def obtener_partidos_hoy():
    hoy = datetime.datetime.now(madrid).strftime("%Y-%m-%d")
    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{hoy}?api_token={SPORTMONKS_API_KEY}&include=localTeam,visitorTeam"
    try:
        response = session.get(url, timeout=10).json()
        return response.get("data", [])
    except Exception as e:
        print(f"[ERROR] Excepción al obtener partidos del día: {e}")
        return []

def obtener_fixture(fixture_id):
    url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events,state"
    try:
        response = session.get(url, timeout=10).json()
        return response.get("data", {})
    except Exception as e:
        print(f"[ERROR] Excepción al obtener fixture {fixture_id}: {e}")
        return {}

def formatear_hora(utc_str):
    try:
        hora_utc = datetime.datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        hora_local = hora_utc.astimezone(madrid)
        return hora_local
    except Exception as e:
        print(f"[ERROR] Formato de hora incorrecto: {e}")
        return datetime.datetime.now(madrid)

def enviar_resumen_diario(partidos):
    mensaje = "*Resumen de partidos para hoy:*\n\n"
    for partido in partidos:
        hora_local = formatear_hora(partido["starting_at"]["date_time"])
        hora_str = hora_local.strftime("%H:%M")
        local = partido["localTeam"]["data"]["name"]
        visitante = partido["visitorTeam"]["data"]["name"]
        mensaje += f"• {hora_str} - {local} vs {visitante}\n"
    enviar_mensaje(mensaje)

def monitorear_eventos(PARTIDOS_DEL_DIA):
    ya_reportados = set()
    estados_previos = {}
    partidos_pendientes = PARTIDOS_DEL_DIA.copy()
    tiros_reportados = set()
    tarjetas_tempranas_reportadas = set()

    print(f"[INFO] Monitoreo preparado para {len(partidos_pendientes)} partidos...")

    while partidos_pendientes:
        ahora = datetime.datetime.now(madrid)
        print(f"[TRACE] Verificando eventos a las {ahora.strftime('%H:%M:%S')}")
        print(f"[DEBUG] Partidos pendientes: {[p['id'] for p in partidos_pendientes]}")
        
        partidos_activos = [p for p in partidos_pendientes if ahora >= p["hora"] - datetime.timedelta(minutes=5)]
        print(f"[DEBUG] Partidos activos: {[p['id'] for p in partidos_activos]}")

        if not partidos_activos:
            print("[INFO] Ningún partido ha empezado aún. Reintento en 10 minutos...")
            time.sleep(600)
            continue

        for partido in partidos_activos:
            print(f"[DEBUG] Procesando partido ID {partido['id']} ({partido['local']} vs {partido['visitante']})")
            fixture_id = partido["id"]
            fixture = obtener_fixture(fixture_id)

            if not fixture:
                print(f"[WARN] Fixture vacío o fallido para partido {fixture_id}")
                continue

            status = fixture.get("state", {}).get("data", {}).get("state")
            print(f"[DEBUG] Estado actual: {status}")
            estado_anterior = estados_previos.get(fixture_id)

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
                if status in ["FT", "CANCELLED", "AWARDED", "POSTPONED"]:
                    if partido in partidos_pendientes:
                        print(f"[INFO] Partido {fixture_id} finalizado o cancelado. Eliminando de seguimiento.")
                        partidos_pendientes.remove(partido)
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
                        mensaje = f"🧐 Posible *GOL* para *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto} *(revisión VAR)*"
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
                    mensaje = f"🥅 *{tipo.upper()}* - {equipo}\n👤 {jugador}\n⏱️ Minuto {minuto}"
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

# MAIN
if __name__ == "__main__":
    partidos_hoy = obtener_partidos_hoy()
    if partidos_hoy:
        enviar_resumen_diario(partidos_hoy)

        PARTIDOS_DEL_DIA = [
            {
                "id": partido["id"],
                "hora": formatear_hora(partido["starting_at"]["date_time"]),
                "local": partido["localTeam"]["data"]["name"],
                "visitante": partido["visitorTeam"]["data"]["name"]
            }
            for partido in partidos_hoy
        ]
        monitorear_eventos(PARTIDOS_DEL_DIA)
    else:
        print("[INFO] No hay partidos programados para hoy.")

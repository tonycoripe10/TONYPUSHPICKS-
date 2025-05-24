import datetime
import time
import os
from utils import enviar_mensaje, session
import pytz

SPORTMONKS_API_KEY = os.getenv("Sportmonks")
madrid = pytz.timezone("Europe/Madrid")
ESTADOS_EN_JUEGO = {"INPLAY_1ST_HALF", "INPLAY_2ND_HALF", "ET", "PEN_LIVE", "HT"}

def obtener_fixture(fixture_id):
    url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}?api_token={SPORTMONKS_API_KEY}&include=events"
    try:
        response = session.get(url, timeout=10)
        return response.json().get("data", {})
    except Exception as e:
        print(f"[ERROR] Fixture {fixture_id}: {e}")
        return {}

def iniciar_monitoreo(partidos):
    ya_reportados = set()
    estados_previos = {}
    tiros_reportados = set()
    tarjetas_tempranas_reportadas = set()
    pendientes = partidos.copy()

    while pendientes:
        ahora = datetime.datetime.now(madrid)
        activos = [p for p in pendientes if ahora >= p["hora"] - datetime.timedelta(minutes=5)]

        if not activos:
            print("[INFO] Ningún partido ha comenzado. Reintento en 10 minutos...")
            time.sleep(600)
            continue

        for partido in activos:
            fixture_id = partido["id"]
            fixture = obtener_fixture(fixture_id)

            if not fixture:
                continue

            status = fixture.get("status", {}).get("type")
            estado_anterior = estados_previos.get(fixture_id)

            if fixture_id not in estados_previos:
                estados_previos[fixture_id] = status
                if status in ESTADOS_EN_JUEGO:
                    enviar_mensaje(f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado.")
                elif status in ["FT", "CANCELLED"]:
                    enviar_mensaje(f"⚠️ *{partido['local']} vs {partido['visitante']}* no se jugará ({status}).")
                    pendientes.remove(partido)
                continue

            if status != estado_anterior:
                if status in ESTADOS_EN_JUEGO:
                    enviar_mensaje(f"🔴 *{partido['local']} vs {partido['visitante']}* ha comenzado.")
                elif status in ["FT", "CANCELLED"]:
                    enviar_mensaje(f"✅ *{partido['local']} vs {partido['visitante']}* ha finalizado ({status}).")
                    pendientes.remove(partido)
                estados_previos[fixture_id] = status

            if status not in ESTADOS_EN_JUEGO:
                continue

            for evento in fixture.get("events", []):
                evento_id = evento.get("id")
                if not evento_id or evento_id in ya_reportados:
                    continue

                tipo = evento.get("type", "").lower()
                minuto = evento.get("minute", 0)
                jugador = evento.get("player", {}).get("name", "Jugador")
                equipo = evento.get("team", {}).get("name", "Equipo")
                resultado = evento.get("result", "")

                if tipo == "goal":
                    if resultado == "under_review":
                        mensaje = f"🧐 Posible *GOL* para *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto} *(VAR)*"
                    elif resultado == "confirmed":
                        mensaje = f"✅ *GOL CONFIRMADO* de *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    elif resultado == "cancelled":
                        mensaje = f"❌ *GOL ANULADO* para *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    else:
                        mensaje = f"⚽ *GOL* de *{equipo}*\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    if enviar_mensaje(mensaje):
                        ya_reportados.add(evento_id)

                elif tipo == "hit-woodwork":
                    mensaje = f"🥅 *TIRO AL PALO* - {equipo}\n👤 {jugador}\n⏱️ Minuto {minuto}"
                    if enviar_mensaje(mensaje):
                        ya_reportados.add(evento_id)

                elif tipo == "yellowcard" and minuto <= 9:
                    clave = (fixture_id, equipo)
                    if clave not in tarjetas_tempranas_reportadas:
                        mensaje = f"🟨 *{equipo}* recibe tarjeta amarilla antes del minuto 10\n👤 {jugador}\n⏱️ Minuto {minuto}"
                        if enviar_mensaje(mensaje):
                            tarjetas_tempranas_reportadas.add(clave)
                        ya_reportados.add(evento_id)

            # Ver estadísticas
            stats_url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}/statistics?api_token={SPORTMONKS_API_KEY}"
            try:
                stats_response = session.get(stats_url, timeout=10).json()
                stats_data = stats_response.get("data", [])
            except Exception as e:
                print(f"[ERROR] Estadísticas {fixture_id}: {e}")
                continue

            for stat in stats_data:
                team_name = stat.get("team", {}).get("name", "Equipo")
                for item in stat.get("statistics", []):
                    if item.get("type") == "shots_on_target":
                        valor = int(item.get("value", 0))
                        clave = (fixture_id, team_name)
                        if valor >= 4 and clave not in tiros_reportados and ahora <= partido["hora"] + datetime.timedelta(minutes=30):
                            mensaje = f"📊 *{team_name}* ha realizado 4+ tiros a puerta antes del minuto 30."
                            if enviar_mensaje(mensaje):
                                tiros_reportados.add(clave)

        print("[INFO] Esperando 40 segundos...")
        time.sleep(40)

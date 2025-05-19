import os
import requests
import time
import datetime
import pytz
import schedule
import threading

# Variables de entorno desde Railway
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")
SPORTMONKS_TOKEN = os.getenv("APIkey")

# Configuración general
HEADERS = {"Authorization": f"Bearer {SPORTMONKS_TOKEN}"}
BASE_URL = "https://api.sportmonks.com/v3/football/livescores/inplay"
INTERVALO_SEGUNDOS = 40

# IDs de ligas a monitorear
LIGAS_MONITOREADAS = [
    140, 141, 2, 3, 5, 82, 9, 94, 262, 203, 4, 151, 152, 235, 253, 5, 6, 7, 8, 13
]

# Emojis por tipo de evento
EMOJIS = {
    "var": "❌",
    "post": "🪵",
    "shot": "🎯",
    "xg": "📊",
    "yellow": "🟨",
    "resumen": "🗓️",
    "gol": "⚽",
    "clock": "⏰",
}

# Función para enviar mensajes por Telegram
def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Error enviando mensaje:", e)

# Función para obtener partidos en vivo
def obtener_partidos_en_vivo():
    try:
        url = f"{BASE_URL}/fixtures/live?leagues={','.join(map(str, LIGAS_MONITOREADAS))}&include=events;statistics;participants"
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        print("Error al obtener partidos en vivo:", e)
        return []

# Función para procesar partidos en vivo
def procesar_partidos():
    print(f"[{datetime.datetime.now()}] Verificando partidos en vivo...")
    partidos = obtener_partidos_en_vivo()
    for partido in partidos:
        try:
            fixture_id = partido["id"]
            minuto = partido.get("time", {}).get("minute", 0)
            nombre_liga = partido["league"]["name"]
            equipos = partido["participants"]
            local = next(t for t in equipos if t["meta"]["location"] == "home")
            visitante = next(t for t in equipos if t["meta"]["location"] == "away")
            marcador = f"{local['name']} {local['meta']['score']['goals']} - {visitante['meta']['score']['goals']} {visitante['name']}"

            # Eventos
            eventos = partido.get("events", [])
            for evento in eventos:
                tipo = evento.get("type")
                detalle = evento.get("text", "").lower()
                minuto_evento = evento.get("minute", 0)

                # Gol anulado por VAR
                if "var" in detalle and any(p in detalle for p in ["offside", "foul", "handball", "disallowed", "cancelled", "annulled"]):
                    mensaje = f"{EMOJIS['var']} <b>GOL ANULADO POR VAR</b>\n{EMOJIS['gol']} {marcador}\n{EMOJIS['clock']} Minuto {minuto_evento}\n{nombre_liga}\n{detalle.capitalize()}"
                    enviar_mensaje_telegram(mensaje)

                # Tiro al palo/larguero
                elif any(p in detalle for p in ["post", "bar", "crossbar", "off the bar", "hit the post", "woodwork"]):
                    mensaje = f"{EMOJIS['post']} <b>TIRO AL PALO</b>\n{EMOJIS['gol']} {marcador}\n{EMOJIS['clock']} Minuto {minuto_evento}\n{nombre_liga}\n{detalle.capitalize()}"
                    enviar_mensaje_telegram(mensaje)

                # Tarjeta amarilla en los primeros 9 minutos
                elif tipo == "yellowcard" and minuto_evento <= 9:
                    jugador = evento.get("player_name", "Jugador desconocido")
                    mensaje = f"{EMOJIS['yellow']} <b>TARJETA TEMPRANA</b>\n{jugador}\n{EMOJIS['gol']} {marcador}\n{EMOJIS['clock']} Minuto {minuto_evento}\n{nombre_liga}"
                    enviar_mensaje_telegram(mensaje)

            # Estadísticas para remates y xG
            estadisticas = partido.get("statistics", {}).get("data", [])
            for equipo_stats in estadisticas:
                equipo_nombre = equipo_stats.get("team_name", "Equipo")
                shots_on_target = int(equipo_stats.get("stats", {}).get("shots_on_target", 0))
                xg = float(equipo_stats.get("stats", {}).get("expected_goals", 0.0))
                if minuto <= 30:
                    if shots_on_target >= 4:
                        mensaje = f"{EMOJIS['shot']} <b>{equipo_nombre} con {shots_on_target} tiros a puerta</b> en 30 minutos\n{EMOJIS['gol']} {marcador}\n{nombre_liga}"
                        enviar_mensaje_telegram(mensaje)
                    if xg >= 1.5:
                        mensaje = f"{EMOJIS['xg']} <b>{equipo_nombre} supera 1.5 xG</b> en 30 minutos\n{EMOJIS['gol']} {marcador}\n{nombre_liga}"
                        enviar_mensaje_telegram(mensaje)

        except Exception as e:
            print("Error procesando partido:", e)

# Función para obtener partidos del día (para resumen)
def obtener_partidos_del_dia(zona_horaria, ligas_ids):
    hoy = datetime.datetime.now(pytz.timezone(zona_horaria)).date()
    fecha_str = hoy.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures/date/{fecha_str}?leagues={','.join(map(str, ligas_ids))}&include=participants,league"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return sorted(response.json().get("data", []), key=lambda x: x["starting_at"]["timestamp"])
    except Exception as e:
        print("Error al obtener partidos del día:", e)
        return []

# Función para enviar resumen diario
def enviar_resumen_diario(ligas_ids, zona_horaria, titulo_resumen):
    partidos = obtener_partidos_del_dia(zona_horaria, ligas_ids)
    if not partidos:
        enviar_mensaje_telegram(f"{EMOJIS['resumen']} <b>{titulo_resumen}</b>\nNo hay partidos programados.")
        return

    mensaje = f"{EMOJIS['resumen']} <b>{titulo_resumen}</b>\n"
    for p in partidos:
        hora = datetime.datetime.fromtimestamp(p["starting_at"]["timestamp"], pytz.timezone(zona_horaria)).strftime("%H:%M")
        equipos = p["participants"]
        local = next(e for e in equipos if e["meta"]["location"] == "home")["name"]
        visitante = next(e for e in equipos if e["meta"]["location"] == "away")["name"]
        liga = p["league"]["name"]
        mensaje += f"{EMOJIS['clock']} {hora} - {local} vs {visitante} ({liga})\n"
    enviar_mensaje_telegram(mensaje)

# Programar los resúmenes diarios
schedule.every().day.at("09:00").do(lambda: enviar_resumen_diario(
    [140, 141, 2, 3, 5, 82, 9, 94, 262], "Europe/Madrid", "Resumen diario de ligas europeas"))

schedule.every().day.at("00:00").do(lambda: enviar_resumen_diario(
    [203, 4, 151, 152, 235, 253, 5, 6, 7, 8, 13], "America/Bogota", "Resumen diario Sudamérica y MLS"))

# Ejecutar resumen hoy a las 20:30 (provisional)
schedule.every().day.at("20:30").do(lambda: enviar_resumen_diario(
    [140, 141, 2, 3, 5, 82, 9, 94, 262, 203, 4, 151, 152, 235, 253, 5, 6, 7, 8, 13],
    "Europe/Madrid", "Resumen de prueba"))

# Hilo para ejecutar schedule
def ejecutar_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Loop principal de verificación en vivo
def loop_principal():
    while True:
        procesar_partidos()
        time.sleep(INTERVALO_SEGUNDOS)

# Inicio del bot
if __name__ == "__main__":
    print("[BOT] Iniciado correctamente. Esperando eventos...")
    threading.Thread(target=ejecutar_schedule).start()
    loop_principal()

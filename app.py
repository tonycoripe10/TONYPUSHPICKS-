import requests
import time
import os
from datetime import datetime

# Variables de entorno (asegúrate de tenerlas en Railway)
API_KEY = os.getenv('APIkey')
TELEGRAM_TOKEN = os.getenv('Telegramtoken')
CHAT_ID = os.getenv('Chatid')

# Variables internas
EVENTOS_REPORTADOS = set()
PARTIDOS_MONITOREADOS = set()
LOG_PATH = "eventos_log.txt"
LIGAS_MONITOREADAS = [39, 140, 135, 78, 61, 262, 88, 94, 203, 195, 253]  # Ej: Premier League, LaLiga, Serie A, etc.

# Palabras clave para detectar goles anulados por VAR
VAR_KEYWORDS = ['goal cancelled', 'goal disallowed', 'goal annulled', 'var']
VAR_CAUSES = ['offside', 'foul', 'handball', 'goalkeeper interference']

# Palabras clave para detectar balones al palo o larguero
PALOS_KEYWORDS = [
    'hits the post', 'off the post', 'off the bar', 'off the crossbar',
    'strikes the post', 'strikes the bar', 'strikes the crossbar',
    'post denies', 'bar denies', 'crossbar denies',
    'saved onto the post', 'saved onto the bar', 'saved onto the crossbar',
    'deflected onto the post', 'deflected onto the bar', 'deflected onto the crossbar'
]

def enviar_mensaje(mensaje):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': mensaje}
    requests.post(url, data=data)

def registrar_evento_log(evento):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {evento}\n")

def obtener_partidos_en_vivo():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('response', [])
    return []

def analizar_eventos():
    partidos = obtener_partidos_en_vivo()
    for partido in partidos:
        fixture_id = partido['fixture']['id']
        liga_id = partido['league']['id']
        minuto = partido['fixture']['status']['elapsed']
        eventos = partido.get('events', [])
        stats = partido.get('statistics', [])

        local = partido['teams']['home']['name']
        visitante = partido['teams']['away']['name']

        # ALERTA PROVISIONAL PARTIDO MILLONARIOS VS ENVIGADO
        if local.lower() == "millonarios" and visitante.lower() == "envigado":
            for evento in eventos:
                if (
                    evento['type'] == 'Card' and
                    evento['detail'] == 'Yellow Card' and
                    evento['time']['elapsed'] <= 90
                ):
                    clave = f"{fixture_id}-{evento['time']['elapsed']}-{evento['player']['id']}-YELLOW"
                    if clave not in EVENTOS_REPORTADOS:
                        mensaje = f"¡Amarilla en el partido Millonarios vs Envigado para {evento['player']['name']} minuto {evento['time']['elapsed']}!"
                        enviar_mensaje(mensaje)
                        EVENTOS_REPORTADOS.add(clave)
                        registrar_evento_log(mensaje)

        if liga_id not in LIGAS_MONITOREADAS:
            continue

        for evento in eventos:
            descripcion = (evento.get('comments') or '').lower()
            tipo = evento.get('type', '')
            detalle = evento.get('detail', '')
            minuto_evento = evento['time']['elapsed']
            clave_evento = f"{fixture_id}-{minuto_evento}-{tipo}-{detalle}"

            if clave_evento in EVENTOS_REPORTADOS:
                continue

            registrar_evento_log(f"Evento recibido: {tipo} - {detalle} - {descripcion}")

            # Gol anulado por VAR
            if tipo == "Goal" and any(k in descripcion for k in VAR_KEYWORDS):
                if any(causa in descripcion for causa in VAR_CAUSES):
                    mensaje = f"¡GOL ANULADO POR VAR! {local} vs {visitante} minuto {minuto_evento} - Motivo: {descripcion}"
                    enviar_mensaje(mensaje)
                    EVENTOS_REPORTADOS.add(clave_evento)
                    registrar_evento_log(mensaje)

            # Balón al palo o larguero
            elif tipo == "Shot" and any(k in descripcion for k in PALOS_KEYWORDS):
                mensaje = f"¡BALÓN AL PALO! {local} vs {visitante} minuto {minuto_evento} - {descripcion}"
                enviar_mensaje(mensaje)
                EVENTOS_REPORTADOS.add(clave_evento)
                registrar_evento_log(mensaje)

        # ALERTA por xG o tiros a puerta en el minuto 30
        if minuto and 28 <= minuto <= 32:
            stats_url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
            headers = {"x-apisports-key": API_KEY}
            res = requests.get(stats_url, headers=headers)
            if res.status_code == 200:
                datos = res.json().get('response', [])
                for equipo_stats in datos:
                    equipo = equipo_stats['team']['name']
                    estadisticas = equipo_stats['statistics']
                    tiros_puerta = next((s['value'] for s in estadisticas if s['type'] == 'Shots on Goal'), 0)
                    xg = next((s['value'] for s in estadisticas if s['type'].lower() == 'expected goals'), 0)
                    clave_alerta = f"{fixture_id}-{equipo}-min30-alerta"

                    if clave_alerta not in EVENTOS_REPORTADOS:
                        if tiros_puerta and tiros_puerta >= 4:
                            mensaje = f"¡{equipo} ya tiene {tiros_puerta} tiros a puerta al minuto {minuto}!"
                            enviar_mensaje(mensaje)
                            EVENTOS_REPORTADOS.add(clave_alerta)
                            registrar_evento_log(mensaje)

                        if xg and isinstance(xg, (float, int)) and xg >= 1.5:
                            mensaje = f"¡{equipo} supera 1.50 xG al minuto {minuto} con {xg} xG!"
                            enviar_mensaje(mensaje)
                            EVENTOS_REPORTADOS.add(clave_alerta)
                            registrar_evento_log(mensaje)

if __name__ == "__main__":
    enviar_mensaje("Bot en marcha correctamente.")
    while True:
        try:
            analizar_eventos()
            time.sleep(15)
        except Exception as e:
            registrar_evento_log(f"ERROR: {str(e)}")
            time.sleep(15)

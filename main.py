import os
import requests
import time
import logging
from datetime import datetime, timedelta
import pytz

# Configuración logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)

# Variables de entorno
API_KEY = os.getenv('APIkey')
TELEGRAM_TOKEN = os.getenv('Telegramtoken')
TELEGRAM_CHAT_ID = os.getenv('Chatid')

if not all([API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
    logging.error("Faltan variables de entorno necesarias: APIkey, Telegramtoken o Chatid")
    exit(1)

BASE_URL = 'https://api.sportmonks.com/v3/football'

# Ligas a monitorizar (ID Sportmonks, ajusta según tu cuenta)
LEAGUES_EUROPE = [
    271,  # LaLiga
    274,  # LaLiga 2
    279,  # Premier League
    775,  # Champions League
    780,  # UEFA Europa League
    777,  # Conference League
    302,  # Ligue 1
    307,  # Serie A
    308,  # Bundesliga
    313,  # Eredivisie
    328,  # Liga Portugal
]
LEAGUES_SOUTH_AMERICA = [
    310,  # Liga MX
    358,  # Liga Colombia
    356,  # Liga Argentina
    360,  # Liga Brasil
    775,  # Copa Libertadores (usar id real)
    780,  # Copa Sudamericana (usar id real)
    390,  # MLS
]
ALL_LEAGUES = LEAGUES_EUROPE + LEAGUES_SOUTH_AMERICA

# Timezones
TZ_SPAIN = pytz.timezone('Europe/Madrid')

# Alert thresholds
MINUTE_LIMIT_REMAPTES = 30
REMATES_THRESHOLD = 4
XG_THRESHOLD = 1.5
MINUTE_LIMIT_YELLOW = 9

# Helper funciones

def telegram_send_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True,
    }
    try:
        resp = requests.post(url, data=data)
        if resp.status_code != 200:
            logging.error(f"Error enviando mensaje a Telegram: {resp.text}")
        else:
            logging.info("Mensaje enviado a Telegram")
    except Exception as e:
        logging.error(f"Excepción enviando mensaje Telegram: {e}")

def get_live_fixtures():
    """Obtiene partidos en vivo de las ligas seleccionadas"""
    leagues_str = ','.join(str(l) for l in ALL_LEAGUES)
    url = f"{BASE_URL}/fixtures/live?api_token={API_KEY}&leagues={leagues_str}&include=stats,events,team.home,team.away"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'data' in data:
            return data['data']
        else:
            logging.warning("No hay datos en la respuesta de partidos en vivo")
            return []
    except Exception as e:
        logging.error(f"Error al obtener partidos en vivo: {e}")
        return []

def get_fixtures_by_date(date_str, leagues):
    """Obtiene partidos por fecha y ligas"""
    leagues_str = ','.join(str(l) for l in leagues)
    url = f"{BASE_URL}/fixtures/date/{date_str}?api_token={API_KEY}&leagues={leagues_str}&include=team.home,team.away"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if 'data' in data:
            return data['data']
        else:
            logging.warning(f"No hay datos para fecha {date_str}")
            return []
    except Exception as e:
        logging.error(f"Error al obtener partidos por fecha: {e}")
        return []

def format_fixture_summary(fixtures):
    """Formatea resumen bonito de partidos para Telegram"""
    if not fixtures:
        return "No hay partidos programados para hoy. ⚽️"

    lines = []
    for f in fixtures:
        kickoff_utc = datetime.fromisoformat(f['time']['starting_at']['date_time_utc'])
        kickoff_local = kickoff_utc.astimezone(TZ_SPAIN)
        time_str = kickoff_local.strftime('%H:%M')
        league_name = f.get('league', {}).get('name', 'Liga')
        home = f.get('localTeam', {}).get('data', {}).get('name', 'Local')
        away = f.get('visitorTeam', {}).get('data', {}).get('name', 'Visitante')

        line = f"⏰ *{time_str}* | {league_name}\n*{home}* vs *{away}*"
        lines.append(line)

    return "📅 *Resumen de partidos del día:*\n\n" + "\n\n".join(lines)

def check_alerts(fixture):
    """
    Revisa los eventos y estadísticas para enviar alertas según tus reglas:
    - Gol anulado por VAR (tipo 10 VAR con subtipos Goal cancelled, Goal disallowed, Goal annulled)
    - Tiros al palo/larguero (event code HIT_WOODWORK o similares)
    - 4+ remates a puerta (shots on target) hasta minuto 30
    - +1.5 xG hasta minuto 30
    - Tarjeta amarilla antes minuto 9
    """

    home_team = fixture['localTeam']['data']['name']
    away_team = fixture['visitorTeam']['data']['name']
    score_home = fixture['scores']['localteam_score']
    score_away = fixture['scores']['visitorteam_score']
    fixture_id = fixture['id']
    league_name = fixture.get('league', {}).get('data', {}).get('name', 'Liga')
    events = fixture.get('events', [])
    stats = fixture.get('stats', [])

    minute_now = 0
    try:
        # Obtener minuto actual del partido
        minute_now = int(fixture.get('time', {}).get('status', {}).get('elapsed', 0))
    except:
        minute_now = 0

    # Procesar eventos
    for event in events:
        event_type = event.get('type')
        event_detail = event.get('detail', '').lower()
        event_minute = event.get('minute', 0)
        event_team = event.get('team', {}).get('data', {}).get('name', '')

        # Gol anulado por VAR (event type 10 + detalle relacionado)
        if event_type == 10:
            desc = event.get('extra', {}).get('description', '').lower()
            # Tipos de VAR relacionados con gol anulado
            if any(x in desc for x in ['goal cancelled', 'goal disallowed', 'goal annulled']):
                text = (
                    f"🚫 *GOL ANULADO POR VAR*\n"
                    f"Liga: *{league_name}*\n"
                    f"Partido: *{home_team}* vs *{away_team}*\n"
                    f"Marcador: {score_home} - {score_away}\n"
                    f"Equipo: *{event_team}*\n"
                    f"Minuto: {event_minute}'\n"
                    f"Motivo: {desc.capitalize()}"
                )
                telegram_send_message(text)

        # Tiros al palo o larguero - buscar código HIT_WOODWORK o evento tipo 'hit-woodwork'
        if event.get('code') == 'HIT_WOODWORK' or 'hit_woodwork' in event.get('code', '').lower():
            text = (
                f"🏹 *TIRO AL PALO/LARGUERO*\n"
                f"Liga: *{league_name}*\n"
                f"Partido: *{home_team}* vs *{away_team}*\n"
                f"Marcador: {score_home} - {score_away}\n"
                f"Equipo: *{event_team}*\n"
                f"Minuto: {event_minute}'\n"
                f"Detalle: {event.get('detail', '')}"
            )
            telegram_send_message(text)

        # Tarjeta amarilla antes minuto 9
        if event_type == 19 and event_minute <= MINUTE_LIMIT_YELLOW:
            text = (
                f"🟨 *Tarjeta amarilla temprana*\n"
                f"Liga: *{league_name}*\n"
                f"Partido: *{home_team}* vs *{away_team}*\n"
                f"Marcador: {score_home} - {score_away}\n"
                f"Jugador: {event.get('player', {}).get('data', {}).get('fullname', 'Jugador')}\n"
                f"Equipo: *{event_team}*\n"
                f"Minuto: {event_minute}'"
            )
            telegram_send_message(text)

    # Procesar estadísticas para remates y xG
    # stats es una lista, buscamos el objeto con 'type' == 'shots_on_target' y 'expected_goals'
    shots_on_target_home = 0
    shots_on_target_away = 0
    xg_home = 0.0
    xg_away = 0.0

    for stat in stats:
        if stat.get('type') == 'shots_on_target':
            shots_on_target_home = stat.get('home', 0)
            shots_on_target_away = stat.get('away', 0)
        elif stat.get('type') == 'expected_goals':
            xg_home = float(stat.get('home', 0.0))
            xg_away = float(stat.get('away', 0.0))

    # Remates a puerta 4+ antes minuto 30
    if minute_now <= MINUTE_LIMIT_REMAPTES:
        if shots_on_target_home >= REMATES_THRESHOLD:
            text = (
                f"🎯 *{home_team}* ha realizado {shots_on_target_home} remates a puerta antes del minuto {MINUTE_LIMIT_REMAPTES}.\n"
                f"Marcador: {score_home} - {score_away}\n"
                f"Liga: *{league_name}*"
            )
            telegram_send_message(text)

        if shots_on_target_away >= REMATES_THRESHOLD:
            text = (
                f"🎯 *{away_team}* ha realizado {shots_on_target_away} remates a puerta antes del minuto {MINUTE_LIMIT_REMAPTES}.\n"
                f"Marcador: {score_home} - {score_away}\n"
                f"Liga: *{league_name}*"
            )
            telegram_send_message(text)

    # xG +1.5 antes minuto 30
    if minute_now <= MINUTE_LIMIT_REMAPTES:
        if xg_home > XG_THRESHOLD:
            text = (
                f"📊 *{home_team}* tiene un xG de {xg_home:.2f} antes del minuto {MINUTE_LIMIT_REMAPTES}.\n"
                f"Marcador: {score_home} - {score_away}\n"
                f"Liga: *{league_name}*"
            )
            telegram_send_message(text)

        if xg_away > XG_THRESHOLD:
            text = (
                f"📊 *{away_team}* tiene un xG de {xg_away:.2f} antes del minuto {MINUTE_LIMIT_REMAPTES}.\n"
                f"Marcador: {score_home} - {score_away}\n"
                f"Liga: *{league_name}*"
            )
            telegram_send_message(text)

def send_daily_summary(is_europe=True):
    """Envía resumen diario bonito a las 17:00 o 00:00 según is_europe"""
    today = datetime.now(TZ_SPAIN).date()
    date_str = today.strftime('%Y-%m-%d')
    leagues = LEAGUES_EUROPE if is

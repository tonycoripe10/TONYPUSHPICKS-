import os
import requests
import time
from datetime import datetime, timedelta
import logging

# Configuración logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)

# Variables de entorno
SPORTMONKS_TOKEN = os.getenv('Sportmonks')
TELEGRAM_TOKEN = os.getenv('Telegramtoken')
TELEGRAM_CHAT_ID = os.getenv('Chatid')

# URLs
SPORTMONKS_API_BASE = 'https://api.sportmonks.com/v3/football'
TELEGRAM_API_BASE = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}'

# Ligas y competiciones a monitorear (IDs o slugs según Sportmonks)
# Para que funcione, reemplaza por los IDs correctos de Sportmonks de estas ligas
TARGET_COMPETITIONS = [
    # Ejemplo (debes verificar IDs reales en Sportmonks)
    8,   # LaLiga Santander (España)
    39,  # Premier League (Inglaterra)
    46,  # Bundesliga (Alemania)
    135, # Serie A (Italia)
    61,  # Ligue 1 (Francia)
    88,  # Eredivisie (Holanda)
    109, # Primeira Liga (Portugal)
    262, # Liga MX (México)
    71,  # Brasileirao Serie A (Brasil)
    168, # Liga Betplay (Colombia)
    78,  # Superliga Argentina
    # Agrega más IDs según necesidad
]

# Función para enviar mensaje a Telegram
def send_telegram_message(text):
    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    try:
        r = requests.post(url, data=payload)
        r.raise_for_status()
        logging.info("Mensaje enviado a Telegram.")
    except Exception as e:
        logging.error(f"Error enviando mensaje Telegram: {e}")

# Obtener partidos en vivo de las competiciones objetivo
def get_live_matches():
    url = f"{SPORTMONKS_API_BASE}/fixtures/live"
    params = {
        'api_token': SPORTMONKS_TOKEN,
        'include': 'stats,events,localTeam,visitorTeam,league',
        'filters[league_id]': ','.join(str(c) for c in TARGET_COMPETITIONS)
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if 'data' in data:
            return data['data']
        else:
            logging.warning("Respuesta sin datos en partidos en vivo.")
            return []
    except Exception as e:
        logging.error(f"Error al obtener partidos en vivo: {e}")
        return []

# Parsear eventos para detectar alertas
def parse_events(match):
    alerts = []
    events = match.get('events', [])
    stats = match.get('stats', [])
    local_team = match['localTeam']['data']
    visitor_team = match['visitorTeam']['data']
    league = match['league']['data']

    # Variables para controlar tiros a puerta y xG
    shots_on_target = {local_team['id']: 0, visitor_team['id']: 0}
    xG = {local_team['id']: 0.0, visitor_team['id']: 0.0}

    # Para evitar repetir alertas, usamos sets
    alerted_events = set()

    # Analizar eventos
    for event in events:
        event_id = event.get('id')
        if event_id in alerted_events:
            continue
        alerted_events.add(event_id)

        minute = event.get('minute', 0)
        event_type = event.get('type', '').lower()
        detail = event.get('detail', '').lower()
        team_id = event.get('team_id')
        description = event.get('comments', '')

        # Alerta de gol anulado por VAR
        if event_type == 'goalcancelled' or ('var' in description.lower() and any(keyword in description.lower() for keyword in ['offside', 'foul', 'handball', 'goalkeeper interference', 'goal disallowed', 'goal cancelled', 'goal annulled', 'disallowed goal'])):
            text = f"🚫 *Gol anulado por VAR*\nLiga: {league['name']}\nPartido: {local_team['name']} {match['scores']['localteam_score']} - {match['scores']['visitorteam_score']} {visitor_team['name']}\nMinuto: {minute}\nDetalles: {description}"
            alerts.append(text)

        # Tiros al palo o larguero
        if event_type == 'shot' and detail in ['post', 'woodwork', 'hit the post', 'hit the bar']:
            text = f"⚡ *Tiro al palo/larguero*\nLiga: {league['name']}\nPartido: {local_team['name']} {match['scores']['localteam_score']} - {match['scores']['visitorteam_score']} {visitor_team['name']}\nMinuto: {minute}\nEquipo: {local_team['name'] if team_id == local_team['id'] else visitor_team['name']}\nDetalles: {description}"
            alerts.append(text)

        # Tiros a puerta (shots on target) para alertar si >= 4 antes minuto 30
        if event_type == 'shot' and detail in ['on target', 'saved', 'goal']:
            shots_on_target[team_id] += 1

        # xG acumulado hasta minuto 30
        xg_value = event.get('expected_goals', 0.0)
        if xg_value is not None and minute <= 30:
            xG[team_id] += float(xg_value)

        # Tarjetas amarillas en primeros 9 minutos
        if event_type == 'card' and detail == 'yellow card' and minute <= 9:
            text = f"⚠️ *Tarjeta amarilla temprana*\nLiga: {league['name']}\nPartido: {local_team['name']} {match['scores']['localteam_score']} - {match['scores']['visitorteam_score']} {visitor_team['name']}\nMinuto: {minute}\nJugador: {event.get('player', {}).get('name', 'Desconocido')}\nEquipo: {local_team['name'] if team_id == local_team['id'] else visitor_team['name']}"
            alerts.append(text)

    # Alerta tiros a puerta >=4 antes del minuto 30
    for team_id, shots in shots_on_target.items():
        if shots >= 4:
            team_name = local_team['name'] if team_id == local_team['id'] else visitor_team['name']
            text = f"🔥 *{team_name}* ha alcanzado {shots} tiros a puerta antes del minuto 30.\nLiga: {league['name']}\nMarcador: {local_team['name']} {match['scores']['localteam_score']} - {match['scores']['visitorteam_score']} {visitor_team['name']}\nMinuto: 30"
            alerts.append(text)

    # Alerta xG > 1.5 antes minuto 30
    for team_id, xg_total in xG.items():
        if xg_total > 1.5:
            team_name = local_team['name'] if team_id == local_team['id'] else visitor_team['name']
            text = f"📊 *{team_name}* tiene xG de {xg_total:.2f} antes del minuto 30.\nLiga: {league['name']}\nMarcador: {local_team['name']} {match['scores']['localteam_score']} - {match['scores']['visitorteam_score']} {visitor_team['name']}\nMinuto: 30"
            alerts.append(text)

    return alerts

# Enviar resumen diario (simplificado)
def send_daily_summary():
    now = datetime.utcnow()
    # Horarios resumen: 9:00 UTC para Europa y 00:00 UTC para Sudamérica (ajusta según zona)
    hour = now.hour
    if hour == 9:
        # Resumen Europa
        leagues_europe = [8, 39, 46, 135, 61, 88, 109]  # IDs europeos (ejemplo)
        send_summary_for_leagues(leagues_europe, "Resumen diario - Ligas Europeas")
    elif hour == 0:
        # Resumen Sudamérica + MLS
        leagues_sudamerica = [262, 71, 168, 78, 253]  # IDs sudamericanos + MLS (ejemplo)
        send_summary_for_leagues(leagues_sudamerica, "Resumen diario - Ligas Sudamericanas y MLS")

def send_summary_for_leagues(league_ids, title):
    # Obtener partidos del día para esas ligas
    today = datetime.utcnow().date()
    from_date = today.strftime('%Y-%m-%d')
    to_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    url = f"{SPORTMONKS_API_BASE}/fixtures/between/{from_date}/{to_date}"
    params = {
        'api_token': SPORTMONKS_TOKEN,
        'filters[league_id]': ','.join(str(l) for l in league_ids),
        'include': 'localTeam,visitorTeam,league',
        'sort': 'starting_at',
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        fixtures = data.get('data', [])
    except Exception as e:
        logging.error(f"Error al obtener resumen diario: {e}")
        return

    if not fixtures:
        logging.info(f"No hay partidos para enviar resumen: {title}")
        return

    text = f"📅 *{title}*\n\n"
    for f in fixtures:
        league_name = f['league']['data']['name']
        local_team = f['localTeam']['data']['name']
        visitor_team = f['visitorTeam']['data']['name']
        start_time_utc = datetime.strptime(f['starting_at'], '%Y-%m-%dT%H:%M:%S%z')
        start_time_str = start_time_utc.strftime('%H:%M UTC')
        text += f"🏆 {league_name}\n{local_team} vs {visitor_team}\n⏰ {start_time_str}\n\n"

    send_telegram_message(text)

# Main loop
def main():
    logging.info("Bot iniciado.")
    last_summary_date = None

    while True:
        now = datetime.utcnow()
        # Enviar resumen diario una vez por día en las horas definidas
        if (now.hour == 9 or now.hour == 0) and (last_summary_date != now.date()):
            send_daily_summary()
            last_summary_date = now.date()

        matches = get_live_matches()
        if not matches:
            logging.info("No hay partidos en vivo ahora.")
        else:
            for match in matches:
                alerts = parse_events(match)
                for alert in alerts:
                    send_telegram_message(alert)

        time.sleep(40)  # Esperar 40 segundos antes de la siguiente consulta

if __name__ == '__main__':
    main()

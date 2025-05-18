import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import time
import os

TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")
BESOCER_BASE_URL = "https://www.besoccer.com"
LEAGUES = [
    "liga-bbva", "premier-league", "serie-a", "bundesliga", "ligue-1", "liga-nos",
    "eredivisie", "liga-profesional-argentina", "brasileirao", "liga-mx", "liga-betplay"
]
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# --------------------------------------------
# Función para enviar mensajes a Telegram
# --------------------------------------------
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)

# --------------------------------------------
# Obtener partidos EN VIVO desde BeSoccer
# --------------------------------------------
def get_live_matches():
    matches = []
    for league in LEAGUES:
        # Ejemplo URL: https://www.besoccer.com/competition/primera-division-espana/2024/matches/live
        url = f"{BESOCER_BASE_URL}/competition/{league}/2024/matches/live"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # Los partidos en vivo están dentro de divs con clase "live-match" o similares
                live_match_containers = soup.find_all("a", class_="match-link")
                for match in live_match_containers:
                    href = match.get("href")
                    if href and href.startswith("/match/"):
                        full_url = BESOCER_BASE_URL + href
                        matches.append(full_url)
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
    return list(set(matches))  # Eliminar duplicados

# --------------------------------------------
# Obtener partidos del día desde BeSoccer
# --------------------------------------------
def get_today_matches():
    matches = []
    today = datetime.now(pytz.timezone("Europe/Madrid")).strftime("%Y-%m-%d")
    for league in LEAGUES:
        url = f"{BESOCER_BASE_URL}/competition/{league}/2024/matches"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # Buscar enlaces a partidos que incluyan la fecha de hoy en formato YYYY-MM-DD en algún atributo o texto
                for a in soup.find_all("a", href=True, class_="match-link"):
                    if today in a["href"]:
                        full_url = BESOCER_BASE_URL + a["href"]
                        matches.append(full_url)
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
    return list(set(matches))

# --------------------------------------------
# Extraer marcador actual de partido desde BeSoccer
# --------------------------------------------
def extract_score(soup):
    try:
        # En BeSoccer, marcador suele estar en div con clase "match-header__score"
        score_div = soup.find("div", class_="match-header__score")
        if score_div:
            return score_div.get_text(strip=True)
        # Alternativa: buscar marcador en el título
        title = soup.title.string if soup.title else None
        if title:
            return title.strip()
        return "Resultado no disponible"
    except:
        return "Resultado no disponible"

# --------------------------------------------
# Extraer eventos en vivo de un partido desde BeSoccer
# --------------------------------------------
def get_live_events(match_url):
    events = []
    try:
        response = requests.get(match_url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Buscar eventos en vivo dentro de la sección de eventos (puede variar)
            events_container = soup.find("div", class_="match-events")
            if not events_container:
                return events

            event_items = events_container.find_all("div", class_="match-event")
            for event in event_items:
                # Obtener texto descriptivo del evento
                text = event.get_text(separator=" ", strip=True).lower()

                # Detectar goles anulados por VAR
                if any(kw in text for kw in [
                    "gol anulado", "goal cancelled", "goal disallowed", "goal annulled", "disallowed goal", "var"
                ]):
                    if any(term in text for term in [
                        "fuera de juego", "offside", "foul", "mano", "handball", "interferencia portero", "goalkeeper interference"
                    ]) and "gol" in text:
                        score = extract_score(soup)
                        events.append(("Gol anulado por VAR", text, score))

                # Detectar tiros al palo/larguero y variantes
                if any(kw in text for kw in [
                    "palo", "travesaño", "post", "crossbar", "woodwork", "rebote del palo", "rebote en el palo"
                ]):
                    score = extract_score(soup)
                    events.append(("Tiro al palo/larguero", text, score))

            # Detección tiros a puerta antes del minuto 30
            # BeSoccer suele mostrar estadísticas en tabla o divs con clases específicas
            # Aquí intento extraer los tiros a puerta de texto visible
            stats_section = soup.find("div", class_="match-statistics")
            if stats_section:
                stats_text = stats_section.get_text(separator=" ", strip=True).lower()
                import re
                # Extraer minutos actuales
                minute_match = re.search(r'(\d{1,2})\'', stats_text)
                current_minute = int(minute_match.group(1)) if minute_match else 0

                if current_minute <= 30:
                    shots_pattern = re.search(r'tiros a puerta\s*(\d+)\s*-\s*(\d+)', stats_text)
                    if shots_pattern:
                        shots_local = int(shots_pattern.group(1))
                        shots_visit = int(shots_pattern.group(2))
                        if shots_local >= 4:
                            score = extract_score(soup)
                            events.append(("Local con 4+ tiros a puerta antes del 30'", f"Tiros a puerta: {shots_local}", score))
                        if shots_visit >= 4:
                            score = extract_score(soup)
                            events.append(("Visitante con 4+ tiros a puerta antes del 30'", f"Tiros a puerta: {shots_visit}", score))
    except Exception as e:
        print(f"Error al obtener eventos de {match_url}: {e}")
    return events

# --------------------------------------------
# Enviar resumen diario de partidos
# --------------------------------------------
def daily_summary():
    matches = get_today_matches()
    if matches:
        message = "<b>Buenos días!</b> Aquí tienes los partidos de hoy en ligas seleccionadas:\n\n"
        for m in matches:
            message += f"- <a href='{m}'>{m}</a>\n"
    else:
        message = "Hoy no hay partidos en las ligas seleccionadas."
    send_telegram_message(message)

# --------------------------------------------
# Monitoreo en vivo usando solo partidos en vivo
# --------------------------------------------
def monitor_live_matches():
    matches = get_live_matches()  # Solo partidos EN VIVO
    if not matches:
        print("No hay partidos en vivo.")
        return
    print(f"Comenzando monitoreo de {len(matches)} partidos en vivo...")
    for match_url in matches:
        events = get_live_events(match_url)
        for tipo, texto, score in events:
            msg = f"<b>{tipo}</b>\nResultado en vivo: {score}\nComentario: {texto}\n{match_url}"
            send_telegram_message(msg)

# --------------------------------------------
# Lógica de ejecución programada (monitoreo todo el día)
# --------------------------------------------
def run_scheduler():
    ejecutado_hoy_9 = False
    ejecutado_hoy_0 = False
    while True:
        ahora = datetime.now(pytz.timezone("Europe/Madrid"))
        # Envía resumen a las 9:00 solo una vez al día
        if ahora.hour == 9 and ahora.minute == 0 and not ejecutado_hoy_9:
            daily_summary()
            ejecutado_hoy_9 = True
        # Envía resumen a las 0:01 solo una vez al día
        if ahora.hour == 0 and ahora.minute == 1 and not ejecutado_hoy_0:
            daily_summary()
            ejecutado_hoy_0 = True
        # Resumen a las 14:05 (sin bandera para repetición)
        if ahora.hour == 14 and ahora.minute == 29:
            daily_summary()
        # Reset flags al cambiar de día
        if ahora.hour == 1 and ahora.minute == 0:
            ejecutado_hoy_9 = False
            ejecutado_hoy_0 = False
        # Monitorea TODO el día (sin restricción horaria)
        monitor_live_matches()
        time.sleep(60)

if __name__ == "__main__":
    print("Bot activo...")
    run_scheduler()

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import time
import os
import re

TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

ODDSPEDIA_BASE_URL = "https://oddspedia.com"

# Liga = slug para URL de liga en oddspedia, por ejemplo: "spain/la-liga"
LEAGUES = [
    "spain/la-liga", "england/premier-league", "italy/serie-a", "germany/bundesliga",
    "france/ligue-1", "portugal/primeira-liga", "netherlands/eredivisie",
    "argentina/primera-division", "brazil/serie-a", "colombia/liga-betplay",
    "mexico/liga-mx"
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)

# Obtener partidos EN VIVO desde Oddspedia (toma todos de live-scores)
def get_live_matches():
    matches = []
    url = f"{ODDSPEDIA_BASE_URL}/live-scores"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # En Oddspedia, cada partido en vivo suele estar en <a> con clase "match-row" (puede variar)
            live_match_links = soup.find_all("a", class_="match-row")
            for a in live_match_links:
                href = a.get("href")
                if href and href.startswith("/match/"):
                    full_url = ODDSPEDIA_BASE_URL + href
                    # Filtrar solo partidos de ligas que queremos
                    if any(league.split("/")[-1] in href for league in LEAGUES):
                        matches.append(full_url)
    except Exception as e:
        print(f"Error accediendo a live-scores: {e}")
    return list(set(matches))

# Obtener partidos del día para ligas seleccionadas
def get_today_matches():
    matches = []
    today = datetime.now(pytz.timezone("Europe/Madrid")).strftime("%Y-%m-%d")
    for league in LEAGUES:
        url = f"{ODDSPEDIA_BASE_URL}/football/{league}"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # En oddspedia, partidos suelen estar en <a> con clase "match-row" o similares
                for a in soup.find_all("a", class_="match-row", href=True):
                    # Oddspedia no suele poner la fecha en el href, pero podemos buscar la fecha en el texto o en un atributo data
                    parent = a.find_parent()
                    date_text = parent.find("div", class_="date")
                    if date_text:
                        fecha = date_text.get_text(strip=True)
                        # Comprobar si fecha coincide con hoy (formatear fecha si es necesario)
                        if today in fecha or fecha.lower() == "today":
                            full_url = ODDSPEDIA_BASE_URL + a["href"]
                            matches.append(full_url)
        except Exception as e:
            print(f"Error accediendo a {url}: {e}")
    return list(set(matches))

def extract_score(soup):
    try:
        # Oddspedia muestra marcador en un div con clase "score"
        score_div = soup.find("div", class_="score")
        if score_div:
            return score_div.get_text(strip=True)
        return "Resultado no disponible"
    except:
        return "Resultado no disponible"

def get_live_events(match_url):
    events = []
    try:
        response = requests.get(match_url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Oddspedia eventos en div con clase "event-item" o similar
            events_container = soup.find("div", class_="events")
            if not events_container:
                return events
            event_items = events_container.find_all("div", class_="event-item")
            for event in event_items:
                text = event.get_text(separator=" ", strip=True).lower()
                # Detectar goles anulados por VAR
                if any(kw in text for kw in [
                    "goal cancelled", "goal disallowed", "goal annulled", "disallowed goal", "var"
                ]):
                    if any(term in text for term in [
                        "offside", "foul", "handball", "goalkeeper interference"
                    ]) and "goal" in text:
                        score = extract_score(soup)
                        events.append(("Gol anulado por VAR", text, score))

                # Detectar tiros al palo/larguero y variantes
                if any(kw in text for kw in [
                    "post", "crossbar", "woodwork", "rebound"
                ]):
                    score = extract_score(soup)
                    events.append(("Tiro al palo/larguero", text, score))

            # Detección tiros a puerta antes del minuto 30
            stats_section = soup.find("div", class_="statistics")
            if stats_section:
                stats_text = stats_section.get_text(separator=" ", strip=True).lower()
                minute_match = re.search(r'(\d{1,2})\'', stats_text)
                current_minute = int(minute_match.group(1)) if minute_match else 0

                if current_minute <= 30:
                    shots_pattern = re.search(r'shots on target\s*(\d+)\s*-\s*(\d+)', stats_text)
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

def daily_summary():
    matches = get_today_matches()
    if matches:
        message = "<b>Buenos días!</b> Aquí tienes los partidos de hoy en ligas seleccionadas:\n\n"
        for m in matches:
            message += f"- <a href='{m}'>{m}</a>\n"
    else:
        message = "Hoy no hay partidos en las ligas seleccionadas."
    send_telegram_message(message)

def monitor_live_matches():
    matches = get_live_matches()
    if not matches:
        print("No hay partidos en vivo.")
        return
    print(f"Comenzando monitoreo de {len(matches)} partidos en vivo...")
    for match_url in matches:
        events = get_live_events(match_url)
        for tipo, texto, score in events:
            msg = f"<b>{tipo}</b>\nResultado en vivo: {score}\nComentario: {texto}\n{match_url}"
            send_telegram_message(msg)

def run_scheduler():
    ejecutado_hoy_9 = False
    ejecutado_hoy_0 = False
    while True:
        ahora = datetime.now(pytz.timezone("Europe/Madrid"))
        if ahora.hour == 9 and ahora.minute == 0 and not ejecutado_hoy_9:
            daily_summary()
            ejecutado_hoy_9 = True
        if ahora.hour == 0 and ahora.minute == 1 and not ejecutado_hoy_0:
            daily_summary()
            ejecutado_hoy_0 = True
        if ahora.hour == 14 and ahora.minute == 36:
            daily_summary()
        if ahora.hour == 1 and ahora.minute == 0:
            ejecutado_hoy_9 = False
            ejecutado_hoy_0 = False
        monitor_live_matches()
        time.sleep(60)

if __name__ == "__main__":
    print("Bot activo con Oddspedia...")
    run_scheduler()

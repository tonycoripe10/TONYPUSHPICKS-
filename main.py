import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import time
import os

TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

SOFASCORE_URL = "https://www.sofascore.com"

LEAGUES = [
    "spain", "england", "italy", "germany", "france", "portugal",
    "netherlands", "argentina", "brazil", "mexico", "colombia"
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
# Obtener partidos del día desde SofaScore
# --------------------------------------------
def get_today_matches():
    today = datetime.now(pytz.timezone('Europe/Madrid')).strftime("%Y-%m-%d")
    matches = []
    for league in LEAGUES:
        url = f"{SOFASCORE_URL}/{league}/football"
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    if "/" + today in a["href"] and "/" in a["href"]:
                        match_url = SOFASCORE_URL + a["href"]
                        matches.append(match_url)
        except Exception as e:
            print(f"Error al acceder a {url}: {e}")
    return list(set(matches))  # Eliminar duplicados


# --------------------------------------------
# Extraer marcador actual
# --------------------------------------------
def extract_score(soup):
    try:
        title = soup.title.string
        return title.strip()
    except:
        return "Resultado no disponible"

# --------------------------------------------
# Extraer eventos en vivo de un partido
# --------------------------------------------
def get_live_events(match_url):
    events = []
    try:
        response = requests.get(match_url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            comments = soup.find_all(string=True)
            for text in comments:
                line = text.strip().lower()
                # Gol anulado por VAR
                if any(kw in line for kw in ["goal cancelled", "goal disallowed", "goal annulled", "var"]):
                    if any(term in line for term in ["offside", "foul", "handball", "goalkeeper interference"]):
                        if "goal" in line:
                            score = extract_score(soup)
                            events.append(("Gol anulado por VAR", line, score))
                # Tiro al palo o larguero
                if any(kw in line for kw in [
                    "hits the post", "off the post", "off the crossbar", "hits the bar",
                    "strikes the post", "strikes the bar", "off the woodwork",
                    "hits the upright", "off the upright", "ricochet off the post",
                    "rebound from the post", "rebound off the post"
                ]):
                    score = extract_score(soup)
                    events.append(("Tiro al palo/larguero", line, score))
            # Tiros a puerta (detección simple)
            if "1st half" in response.text.lower():
                if "shots on target" in response.text.lower():
                    text = response.text.lower()
                    idx = text.find("shots on target")
                    subtext = text[idx:idx+300]
                    import re
                    shots = list(map(int, re.findall(r'(\d+)\s*-\s*(\d+)', subtext)[0])) if re.findall(r'(\d+)\s*-\s*(\d+)', subtext) else [0,0]
                    if any(s >= 4 for s in shots):
                        score = extract_score(soup)
                        team = "Local" if shots[0] >= 4 else "Visitante"
                        events.append((f"{team} con 4+ tiros a puerta antes del 30'", f"Tiros a puerta: {shots[0]} - {shots[1]}", score))
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
# Monitoreo en vivo (una ejecución)
# --------------------------------------------
def monitor_live_matches():
    matches = get_today_matches()
    if not matches:
        print("No hay partidos en vivo.")
        return
    print(f"Comenzando monitoreo de {len(matches)} partidos...")
    for match_url in matches:
        events = get_live_events(match_url)
        for tipo, texto, score in events:
            msg = f"<b>{tipo}</b>\nResultado en vivo: {score}\nComentario: {texto}"
            send_telegram_message(msg)


# --------------------------------------------
# Lógica de ejecución programada con ciclo no bloqueante
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

        # Resumen a las 12:41 (o la hora que desees, sin bandera para repetición)
        if ahora.hour == 13 and ahora.minute == 08:
            daily_summary()

        # Reset flags al cambiar de día, para poder enviar mensajes de nuevo
        if ahora.hour == 1 and ahora.minute == 0:
            ejecutado_hoy_9 = False
            ejecutado_hoy_0 = False

        # Monitorea partidos si está en horario de partidos (12:00 a 04:00)
        if ahora.hour >= 12 or ahora.hour <= 4:
            monitor_live_matches()

        time.sleep(60)


if __name__ == "__main__":
    print("Bot activo...")
    run_scheduler()

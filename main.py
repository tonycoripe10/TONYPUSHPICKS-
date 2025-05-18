import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import time
import os
import re

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
# Obtener partidos del día desde SofaScore (actualizado)
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
                # Extraemos todos los enlaces que contengan fecha del día y parezcan partido
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("/") and today in href and "/match/" in href:
                        full_url = SOFASCORE_URL + href
                        matches.append(full_url)
        except Exception as e:
            print(f"Error al acceder a {url}: {e}")
    return list(set(matches))  # Eliminar duplicados

# --------------------------------------------
# Extraer marcador actual (igual)
# --------------------------------------------
def extract_score(soup):
    try:
        title = soup.title.string
        return title.strip()
    except:
        return "Resultado no disponible"

# --------------------------------------------
# Extraer eventos en vivo de un partido (mejorado)
# --------------------------------------------
def get_live_events(match_url):
    events = []
    try:
        response = requests.get(match_url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Extraer marcador para alertas
            score = extract_score(soup)
            
            # Recolectamos todos los textos visibles para analizar eventos
            texts = [text.strip().lower() for text in soup.stripped_strings]

            # Filtrar textos que indican goles anulados por VAR, con muchas variantes
            var_keywords = [
                "goal cancelled", "goal disallowed", "goal annulled", "var",
                "offside", "foul", "handball", "goalkeeper interference",
                "disallowed goal", "goal cancelled by var", "goal ruled out"
            ]
            for line in texts:
                # Goles anulados por VAR (combinando keywords)
                if any(k in line for k in ["goal cancelled", "goal disallowed", "goal annulled", "disallowed goal"]) and "var" in line:
                    if any(v in line for v in ["offside", "foul", "handball", "goalkeeper interference", "var"]):
                        if "goal" in line:
                            events.append(("Gol anulado por VAR", line, score))
                elif "goal" in line and "var" in line and any(v in line for v in ["offside", "foul", "handball", "goalkeeper interference"]):
                    events.append(("Gol anulado por VAR", line, score))

            # Tiros al palo/larguero con múltiples variantes y posibles rebotes
            palo_keywords = [
                "hits the post", "off the post", "off the crossbar", "hits the bar",
                "strikes the post", "strikes the bar", "off the woodwork",
                "hits the upright", "off the upright", "ricochet off the post",
                "rebound from the post", "rebound off the post",
                "hits post", "hits bar", "hits crossbar", "hits upright"
            ]
            for line in texts:
                if any(kw in line for kw in palo_keywords):
                    events.append(("Tiro al palo/larguero", line, score))

            # Detección de tiros a puerta: buscamos patrones en el texto HTML
            page_text = response.text.lower()
            # Sólo consideramos primer tiempo (antes minuto 30)
            # Buscamos la cadena "shots on target" y extraemos números (ejemplo: "shots on target 4 - 2")
            if "1st half" in page_text or "first half" in page_text:
                match = re.search(r"shots on target.*?(\d+)\s*-\s*(\d+)", page_text)
                if match:
                    local_shots = int(match.group(1))
                    visitor_shots = int(match.group(2))
                    if local_shots >= 4:
                        events.append(("Local con 4+ tiros a puerta antes del 30'", f"Tiros a puerta: {local_shots} - {visitor_shots}", score))
                    if visitor_shots >= 4:
                        events.append(("Visitante con 4+ tiros a puerta antes del 30'", f"Tiros a puerta: {local_shots} - {visitor_shots}", score))
    except Exception as e:
        print(f"Error al obtener eventos de {match_url}: {e}")
    return events

# --------------------------------------------
# Enviar resumen diario de partidos (igual)
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
# Monitoreo en vivo (una ejecución) (igual)
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
# Lógica de ejecución programada con ciclo no bloqueante (igual)
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
        # Resumen a las 14:05 (igual que tú)
        if ahora.hour == 14 and ahora.minute == 5:
            daily_summary()
        # Reset flags al cambiar de día
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

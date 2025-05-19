import asyncio
import aiohttp
import datetime
import urllib.parse
import html

# Zona horaria para Colombia (ajusta si es necesario)
import pytz
TZ = pytz.timezone('America/Bogota')

# Variables de entorno o tus tokens aquí (reemplaza con tus datos reales)
API_KEY = "APIkey"
TELEGRAM_TOKEN = "Telegramtoken"
CHAT_ID = "Chatid"

# Competencias que quieres monitorear (IDs Sportmonks)
COMPETITION_IDS = {
    271,  # España Primera
    272,  # España Segunda
    2,    # Inglaterra Premier
    9,    # Inglaterra Championship
    8,    # Alemania Bundesliga
    11,   # Italia Serie A
    14,   # Francia Ligue 1
    16,   # Holanda Eredivisie
    18,   # Portugal Primeira Liga
    166,  # México Liga MX
    182,  # Brasil Serie A
    263,  # Colombia Primera A
    264,  # Argentina Primera Division
    61,   # Copa Libertadores
    62,   # Copa Sudamericana
    253,  # MLS
    2,    # Champions League (usa mismo id que Inglaterra Premier? verifica)
    3,    # Europa League (asegura que el id sea correcto)
    # Añade más ids si tienes
}

def escape_html(text):
    return html.escape(text)

class Bot:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def send_telegram_message(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        async with self.session.post(url, data=payload) as resp:
            if resp.status != 200:
                print(f"[Telegram] Error enviando mensaje: {resp.status}")
            else:
                print(f"[Telegram] Mensaje enviado correctamente")

    async def check_live_matches(self):
        print(f"[{datetime.datetime.now(TZ).strftime('%H:%M:%S')}] Verificando partidos en vivo...")

        filters = '{"status":"live"}'
        filters_enc = urllib.parse.quote_plus(filters)

        url = (f"https://api.sportmonks.com/v3/football/fixtures?"
               f"api_token={API_KEY}&include=events,stats,participants&filters={filters_enc}")

        print(f"[Partidos en vivo] Solicitud GET con filtro codificado: {url}")

        try:
            async with self.session.get(url) as response:
                print(f"[Partidos en vivo] Código respuesta: {response.status}")
                resp_text = await response.text()
                print(f"[Partidos en vivo] Cuerpo respuesta (primeros 500 caracteres): {resp_text[:500]}...")

                if response.status != 200:
                    print(f"[Partidos en vivo] Error HTTP {response.status}")
                    return

                data = await response.json()

                for match in data.get("data", []):
                    league_id = match.get("league_id")
                    if not isinstance(league_id, int) or league_id not in COMPETITION_IDS:
                        continue

                    participants = match.get("participants", [])
                    if len(participants) < 2:
                        continue

                    home = escape_html(participants[0].get("name", "Local"))
                    away = escape_html(participants[1].get("name", "Visitante"))
                    score = escape_html(f"{participants[0].get('score',0)} - {participants[1].get('score',0)}")
                    minute = match.get("time", {}).get("minute") or 0

                    # Eventos
                    events = match.get("events", [])
                    for event in events:
                        comment_raw = event.get("details", "")
                        comment = comment_raw.lower()
                        event_type = event.get("type", "").lower()
                        safe_comment = escape_html(comment_raw)

                        if (event_type == "goal_cancelled" or any(x in comment for x in [
                            "goal cancelled", "goal disallowed", "disallowed goal",
                            "offside", "handball", "foul", "var", "interference"
                        ])):
                            msg = (f"❌ <b>¡Gol anulado por VAR!</b>\n"
                                   f"<b>{home} vs {away}</b>\n"
                                   f"Resultado: <b>{score}</b>\n"
                                   f"<i>{safe_comment}</i>")
                            await self.send_telegram_message(msg)
                            break

                        if "post" in comment or "crossbar" in comment:
                            msg = (f"⚠️ <b>¡Tiro al palo!</b>\n"
                                   f"<b>{home} vs {away}</b>\n"
                                   f"Resultado: <b>{score}</b>\n"
                                   f"<i>{safe_comment}</i>")
                            await self.send_telegram_message(msg)
                            break

                        if event_type == "yellowcard" and minute <= 9:
                            msg = (f"🟨 <b>Tarjeta amarilla temprana</b>\n"
                                   f"<b>{home} vs {away}</b>\n"
                                   f"Minuto: <b>{minute}'</b>\n"
                                   f"<i>{safe_comment}</i>")
                            await self.send_telegram_message(msg)
                            break

                    # Estadísticas
                    stats = match.get("stats", [])
                    for stat in stats:
                        team = escape_html(stat.get("participant_name", "Equipo"))
                        shots_on_target = stat.get("shots_on_target", 0)
                        xg = stat.get("expected_goals", 0)

                        if minute <= 30:
                            if shots_on_target >= 4:
                                msg = (f"🔥 <b>{team}</b> tiene <b>{shots_on_target}</b> remates a puerta antes del minuto 30\n"
                                       f"<b>{home} vs {away}</b>\nResultado: <b>{score}</b>")
                                await self.send_telegram_message(msg)

                            if xg and float(xg) >= 1.5:
                                msg = (f"🔎 <b>{team}</b> supera 1.5 xG antes del minuto 30\n"
                                       f"<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n"
                                       f"xG: <b>{xg}</b>")
                                await self.send_telegram_message(msg)

        except Exception as e:
            print(f"[Error en partidos en vivo] {e}")

    async def run(self):
        while True:
            await self.check_live_matches()
            await asyncio.sleep(40)  # Revisa cada 40 segundos

    async def close(self):
        await self.session.close()

if __name__ == "__main__":
    bot = Bot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("Bot detenido por usuario.")
    finally:
        asyncio.run(bot.close())

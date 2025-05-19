import os
import datetime
import asyncio
import aiohttp
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import html
from dateutil import parser

API_KEY = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

TZ = pytz.timezone('Europe/Madrid')

COMPETITION_IDS = [
    8, 9, 82, 83, 184, 384, 301, 35, 39, 74, 71, 77, 66, 1005, 1013,
    179, 2, 3, 5, 196
]

def escape_html(text):
    return html.escape(str(text))

class Bot:
    def __init__(self):
        self.session = None

    async def start(self):
        if not TELEGRAM_TOKEN or not CHAT_ID or not API_KEY:
            print("ERROR: Variables de entorno no definidas correctamente")
            return

        self.session = aiohttp.ClientSession()
        await self.send_startup_message()

    async def close(self):
        if self.session:
            await self.session.close()

    async def send_telegram_message(self, text):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
        try:
            async with self.session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"[Telegram] ERROR HTTP {resp.status}")
                else:
                    print(f"[Telegram] Mensaje enviado correctamente.")
        except Exception as e:
            print(f"[Telegram Error] {e}")

    async def send_startup_message(self):
        now = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        msg = f"✅ <b>Bot en marcha</b>\nHora: <i>{now}</i>"
        await self.send_telegram_message(msg)

    async def send_daily_summary(self, region):
        now = datetime.datetime.now(TZ)
        if region == "EU":
            target_date = now.strftime('%Y-%m-%d')
            header = "📋 <b>Partidos del día (Europa)</b>\n\n"
        else:
            target_date = (now + datetime.timedelta(hours=2)).strftime('%Y-%m-%d')
            header = "🌎 <b>Partidos del día (Sudamérica y MLS)</b>\n\n"

        url = f"https://api.sportmonks.com/v3/football/fixtures/date/{target_date}?api_token={API_KEY}&include=participants,league"
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    print(f"[Resumen diario] Error HTTP {response.status}")
                    return
                data = await response.json()
                partidos = []
                for match in data.get("data", []):
                    league_id = match.get("league_id")
                    if not isinstance(league_id, int) or league_id not in COMPETITION_IDS:
                        continue
                    participants = match.get("participants", [])
                    if len(participants) < 2:
                        continue
                    home = escape_html(participants[0].get("name", "Equipo Local"))
                    away = escape_html(participants[1].get("name", "Equipo Visitante"))
                    dt_str = match.get("starting_at", {}).get("date_time")
                    if not dt_str:
                        continue
                    try:
                        start = parser.isoparse(dt_str).astimezone(TZ)
                    except Exception:
                        continue
                    partidos.append(f"🕒 <b>{start.strftime('%H:%M')}</b> - {home} vs {away}")

                partidos.sort()
                msg = header + ("\n".join(partidos) if partidos else "No hay partidos programados hoy.")
                await self.send_telegram_message(msg)

        except Exception as e:
            print(f"[Resumen diario] Error: {e}")

    async def check_live_matches(self):
        print(f"[{datetime.datetime.now(TZ).strftime('%H:%M:%S')}] Verificando partidos en vivo...")
        url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_KEY}&include=events,stats,participants&filters[status]=LIVE"
        try:
            async with self.session.get(url) as response:
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

async def main():
    bot = Bot()
    await bot.start()

    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(bot.send_daily_summary, "cron", hour=9, minute=0, args=["EU"])
    scheduler.add_job(bot.send_daily_summary, "cron", hour=0, minute=0, args=["SA"])
    scheduler.add_job(bot.check_live_matches, "interval", seconds=40)
    scheduler.start()

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot detenido manualmente.")

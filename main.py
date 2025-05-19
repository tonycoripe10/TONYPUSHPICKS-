import os
import datetime
import asyncio
import aiohttp
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Variables de entorno
API_KEY = os.getenv("APIkey")
TELEGRAM_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

# Zona horaria
TZ = pytz.timezone('Europe/Madrid')

# IDs de ligas a monitorear
COMPETITION_IDS = [
    8, 9, 82, 83, 184, 384, 301, 35, 39, 74, 71, 77, 66,
    1005, 1013, 179, 2, 3, 5, 196
]

# Enviar mensaje por Telegram
async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    print(f"[Telegram] Error {resp.status}: {await resp.text()}")
    except Exception as e:
        print(f"[Telegram Error] {e}")

# Mensaje inicial
async def send_startup_message():
    now = datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    msg = f"✅ <b>Bot en marcha</b>\nHora: <i>{now}</i>"
    await send_telegram_message(msg)

# Resumen diario
async def send_daily_summary(region):
    now = datetime.datetime.now(TZ)
    if region == "EU":
        target_date = now.strftime('%Y-%m-%d')
        header = "📋 <b>Partidos del día (Europa)</b>\n\n"
    else:
        target_date = (now + datetime.timedelta(hours=2)).strftime('%Y-%m-%d')
        header = "🌎 <b>Partidos del día (Sudamérica y MLS)</b>\n\n"

    url = f"https://api.sportmonks.com/v3/football/fixtures/date/{target_date}?api_token={API_KEY}&include=participants,league"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                partidos = []
                for match in data.get("data", []):
                    if match.get("league_id") not in COMPETITION_IDS:
                        continue
                    participants = match.get("participants", [])
                    if len(participants) < 2:
                        continue
                    home = participants[0]["name"]
                    away = participants[1]["name"]
                    start_str = match["starting_at"]["date_time"]
                    start = datetime.datetime.fromisoformat(start_str).astimezone(TZ)
                    partidos.append(f"🕒 <b>{start.strftime('%H:%M')}</b> - {home} vs {away}")

                partidos.sort()
                msg = header + ("\n".join(partidos) if partidos else "No hay partidos programados hoy.")
                await send_telegram_message(msg)
    except Exception as e:
        print(f"[Resumen Diario Error] {e}")

# Verificar partidos en vivo
async def check_live_matches():
    print(f"[{datetime.datetime.now(TZ).strftime('%H:%M:%S')}] Verificando partidos en vivo...")
    url = f"https://api.sportmonks.com/v3/football/fixtures?api_token={API_KEY}&include=events,stats,participants&filters[status]=LIVE"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()

                for match in data.get("data", []):
                    if match.get("league_id") not in COMPETITION_IDS:
                        continue

                    participants = match.get("participants", [])
                    if len(participants) < 2:
                        continue

                    home = participants[0]["name"]
                    away = participants[1]["name"]
                    score = f"{participants[0]['score']} - {participants[1]['score']}"
                    minute = match.get("time", {}).get("minute") or 0

                    alerts = []

                    # Eventos relevantes
                    for event in match.get("events", []):
                        comment = (event.get("details") or "").lower()
                        event_type = (event.get("type") or "").lower()

                        if event_type == "goal_cancelled" or any(x in comment for x in [
                            "goal cancelled", "goal disallowed", "disallowed goal",
                            "var", "offside", "handball", "foul", "interference"
                        ]):
                            alerts.append(f"❌ <b>¡Gol anulado por VAR!</b>\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n<i>{comment}</i>")
                        
                        if "post" in comment or "crossbar" in comment:
                            alerts.append(f"⚠️ <b>¡Tiro al palo!</b>\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n<i>{comment}</i>")

                        if event_type == "yellowcard" and minute <= 9:
                            alerts.append(f"🟨 <b>Tarjeta amarilla temprana</b>\n<b>{home} vs {away}</b>\nMinuto: <b>{minute}'</b>\n<i>{comment}</i>")

                    # Estadísticas relevantes
                    for stat in match.get("stats", []):
                        team = stat.get("participant_name", "Equipo")
                        shots_on_target = stat.get("shots_on_target", 0)
                        xg = stat.get("expected_goals", 0)

                        if minute <= 30:
                            if shots_on_target >= 4:
                                alerts.append(f"🔥 <b>{team}</b> tiene <b>{shots_on_target}</b> remates a puerta antes del minuto 30\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>")
                            if xg and float(xg) > 1.5:
                                alerts.append(f"⚡️ <b>{team}</b> supera 1.5 xG antes del minuto 30\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n<i>xG: {xg}</i>")

                    for alert in alerts:
                        await send_telegram_message(alert)
    except Exception as e:
        print(f"[Error en partidos en vivo] {e}")

# Ejecutar bot
async def main():
    await send_startup_message()
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(lambda: asyncio.create_task(send_daily_summary("EU")), "cron", hour=9, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(send_daily_summary("SA")), "cron", hour=0, minute=0)
    scheduler.add_job(lambda: asyncio.create_task(check_live_matches()), "interval", seconds=40)
    scheduler.start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot detenido manualmente.")

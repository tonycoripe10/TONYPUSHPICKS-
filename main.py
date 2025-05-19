import os
import time
import requests
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

# Ligas a monitorear
COMPETITION_IDS = [
    8, 9,        # España 1ª y 2ª
    82, 83,      # Inglaterra 1ª y 2ª
    184,         # Alemania 1ª
    384,         # Italia 1ª
    301,         # Francia 1ª
    35,          # Holanda 1ª
    39,          # Portugal 1ª
    74,          # México 1ª
    71,          # Brasil 1ª
    77,          # Colombia 1ª
    66,          # Argentina 1ª
    1005, 1013,  # Libertadores y Sudamericana
    179,         # MLS
    2, 3, 5,     # UCL, UEL, Conference
    196          # Mundial de Clubes
]

# Función para enviar mensaje por Telegram
async def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    print(f"[Telegram] Error {resp.status}: {await resp.text()}")
    except Exception as e:
        print(f"[Error Telegram] {e}")

# Mensaje de inicio
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
                    if match.get("league_id") in COMPETITION_IDS:
                        participants = match.get("participants", [])
                        if len(participants) >= 2:
                            home = participants[0]["name"]
                            away = participants[1]["name"]
                            start = datetime.datetime.fromisoformat(match["starting_at"]["date_time"]).astimezone(TZ)
                            partidos.append(f"🕒 <b>{start.strftime('%H:%M')}</b> - {home} vs {away}")

                partidos.sort()
                msg = header + ("\n".join(partidos) if partidos else "No hay partidos programados hoy.")
                await send_telegram_message(msg)
    except Exception as e:
        print(f"[Resumen diario] Error: {e}")

# Análisis de partidos en vivo
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
                    minute = match.get("time", {}).get("minute", 0) or 0

                    # Eventos
                    for event in match.get("events", []):
                        comment = event.get("details", "").lower()
                        event_type = event.get("type", "").lower()

                        if event_type == "goal_cancelled" or any(x in comment for x in [
                            "goal cancelled", "goal disallowed", "disallowed goal",
                            "offside", "handball", "foul", "var", "interference"
                        ]):
                            msg = f"❌ <b>¡Gol anulado por VAR!</b>\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n<i>{comment}</i>"
                            await send_telegram_message(msg)
                            break

                        if "post" in comment or "crossbar" in comment:
                            msg = f"⚠️ <b>¡Tiro al palo!</b>\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n<i>{comment}</i>"
                            await send_telegram_message(msg)
                            break

                        if event_type == "yellowcard" and minute <= 9:
                            msg = f"🟨 <b>Tarjeta amarilla temprana</b>\n<b>{home} vs {away}</b>\nMinuto: <b>{minute}'</b>\n<i>{comment}</i>"
                            await send_telegram_message(msg)
                            break

                    # Estadísticas
                    for stat in match.get("stats", []):
                        team = stat.get("participant_name", "Equipo")
                        shots_on_target = stat.get("shots_on_target", 0)
                        xg = stat.get("expected_goals", 0)

                        if minute <= 30:
                            if shots_on_target >= 4:
                                msg = f"🔥 <b>{team}</b> tiene <b>{shots_on_target}</b> remates a puerta antes del minuto 30\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>"
                                await send_telegram_message(msg)
                            if xg and float(xg) > 1.5:
                                msg = f"⚡️ <b>{team}</b> supera 1.5 xG antes del minuto 30\n<b>{home} vs {away}</b>\nResultado: <b>{score}</b>\n<i>xG: {xg}</i>"
                                await send_telegram_message(msg)
    except Exception as e:
        print(f"[Error en partidos en vivo] {e}")

# Inicialización
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

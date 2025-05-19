import aiohttp
import asyncio
import os

SPORTMONKS_TOKEN = os.getenv("APIkey")

MONITORED_LEAGUES = [
    501,  # La Liga (España)
    502,  # La Liga 2 (España)
    8,    # Premier League (Inglaterra)
    9,    # Championship (Inglaterra)
    82,   # Bundesliga (Alemania)
    384,  # Serie A (Italia)
    301,  # Ligue 1 (Francia)
    203,  # Eredivisie (Holanda)
    84,   # Primeira Liga (Portugal)
    262,  # Liga MX (México)
    186,  # Brasileirão (Brasil)
    207,  # Liga BetPlay (Colombia)
    197,  # Liga Profesional (Argentina)
    1076, # Copa Libertadores
    1077, # Copa Sudamericana
    178,  # MLS
    132,  # UEFA Champions League
    135,  # UEFA Europa League
    137,  # UEFA Conference League
    1026  # Club World Cup
]

async def get_live_matches(session):
    url = (
        "https://api.sportmonks.com/v3/football/fixtures"
        "?include=participants;league"
        "&filters[status]=LIVE"
    )
    headers = {
        "Authorization": f"Bearer {SPORTMONKS_TOKEN}"
    }

    async with session.get(url, headers=headers) as response:
        if response.status != 200:
            print(f"[!] Error al consultar partidos en vivo: {response.status}")
            error_text = await response.text()
            print(f"[!] Respuesta: {error_text}")
            return []

        data = await response.json()
        live_matches = []

        for match in data.get('data', []):
            league = match.get('league', {})
            league_id = league.get('id')
            if league_id in MONITORED_LEAGUES:
                live_matches.append(match)

        return live_matches

async def main():
    async with aiohttp.ClientSession() as session:
        live_matches = await get_live_matches(session)
        print(f"Se encontraron {len(live_matches)} partidos en vivo de ligas monitoreadas.")
        for match in live_matches:
            home = match["participants"][0]["name"]
            away = match["participants"][1]["name"]
            print(f"{home} vs {away}")

if __name__ == "__main__":
    asyncio.run(main())

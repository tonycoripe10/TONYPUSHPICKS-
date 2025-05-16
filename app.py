import requests
import time
from flask import Flask
import os

API_KEY = os.getenv("APIkey")
BOT_TOKEN = os.getenv("Telegramtoken")
CHAT_ID = os.getenv("Chatid")

app = Flask(__name__)
eventos_reportados = set()
alertas_ataque_reportadas = set()

ligas_permitidas = {
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    94,   # Primeira Liga
    88,   # Eredivisie
    128,  # Liga MX
    262,  # Liga Profesional Argentina
    71,   # Brasileirão
    239,  # Categoría Primera A (Colombia)
    13    # Copa Libertadores
}

def enviar_mensaje(texto):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto}
    requests.post(url, json=payload)

def obtener_partidos_en_vivo():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    respuesta = requests.get(url, headers=headers)
    return respuesta.json()["response"]

def revisar_eventos():
    partidos = obtener_partidos_en_vivo()
    for partido in partidos:
        fixture = partido["fixture"]
        league = partido["league"]
        teams = partido["teams"]
        eventos = partido.get("events", [])
        estadisticas = partido.get("statistics", [])

        if league["id"] not in ligas_permitidas:
            continue

        for evento in eventos:
            evento_id = f"{fixture['id']}_{evento['time']['elapsed']}_{evento['team']['id']}_{evento['type']}_{evento['detail']}"

            if evento_id in eventos_reportados:
                continue

            descripcion = evento.get("detail", "").lower()
            tipo = evento.get("type", "").lower()

            if ("post" in descripcion or "crossbar" in descripcion or "larguero" in descripcion or "palo" in descripcion) and tipo == "shot":
                mensaje = f"Tiro al palo: {evento['player']['name']} ({evento['team']['name']}) en el minuto {evento['time']['elapsed']} contra {teams['home']['name']} vs {teams['away']['name']}"
                enviar_mensaje(mensaje)
                eventos_reportados.add(evento_id)

            elif "goal cancelled" in descripcion or "goal disallowed" in descripcion or "gol anulado" in descripcion:
                mensaje = f"Gol anulado por VAR para {evento['team']['name']} en el minuto {evento['time']['elapsed']} ({teams['home']['name']} vs {teams['away']['name']})"
                enviar_mensaje(mensaje)
                eventos_reportados.add(evento_id)

        # Alerta por estadísticas ofensivas minuto 30
        tiempo_actual = partido["fixture"]["status"]["elapsed"]
        if tiempo_actual is not None and 30 <= tiempo_actual <= 35:
            for stats_equipo in estadisticas:
                equipo = stats_equipo["team"]["name"]
                stats = stats_equipo["statistics"]

                tiros_puerta = next((s["value"] for s in stats if s["type"] == "Shots on Goal"), 0) or 0
                xg = next((s["value"] for s in stats if s["type"].lower() == "expected goals"), 0) or 0

                clave_alerta = f"{fixture['id']}_{equipo}"
                if clave_alerta in alertas_ataque_reportadas:
                    continue

                if tiros_puerta >= 6 or (isinstance(xg, (int, float)) and xg > 1.5):
                    mensaje = f"¡Atención! {equipo} está dominando ofensivamente al minuto {tiempo_actual} con {tiros_puerta} tiros a puerta y un xG de {xg} ({teams['home']['name']} vs {teams['away']['name']})"
                    enviar_mensaje(mensaje)
                    alertas_ataque_reportadas.add(clave_alerta)

@app.route('/')
def home():
    return "Bot funcionando correctamente"

enviar_mensaje("Bot iniciado y funcionando correctamente")

if __name__ == '__main__':
    from threading import Thread

    def run_bot():
        while True:
            try:
                revisar_eventos()
            except Exception as e:
                print("Error:", e)
            time.sleep(15)

    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    app.run(host='0.0.0.0', port=5000)

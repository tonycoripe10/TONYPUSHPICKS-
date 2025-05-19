import os
import requests

def probar_token():
    token = os.getenv("APIkey")
    if not token:
        print("La variable de entorno 'SportmonksToken' no está configurada.")
        return

    url = f"https://api.sportmonks.com/v3/football/livescores?api_token={token}&include=participants;events;stats;state;league&per_page=50"

    try:
        response = requests.get(url)
        print("Código HTTP:", response.status_code)
        print("Contenido recibido:")
        print(response.text)
    except Exception as e:
        print("Error al hacer la petición:", e)

if __name__ == "__main__":
    probar_token()

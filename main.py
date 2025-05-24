from resumen import enviar_resumen_diario from monitoreo import iniciar_monitoreo

if name == "main": print("[INFO] Iniciando bot de fútbol...") partidos = enviar_resumen_diario() iniciar_monitoreo(partidos)


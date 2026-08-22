# Hermes Local STT

Servicio de reconocimiento de voz utilizado por Giddy. Mantiene VAD activo,
evita reintentos sobre silencio y filtra alucinaciones frecuentes de Whisper.

El despliegue local actual monta esta carpeta como `/app` en `hermes-stt` y
expone el puerto `9000`.

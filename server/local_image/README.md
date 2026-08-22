# Generador local de imagenes

Este contenedor es el respaldo sin costo por uso para Giddy. Descarga SDXL-Lightning
una sola vez en el volumen Docker `giddy-image-models`, usa la GPU NVIDIA y se elimina
al terminar cada imagen para devolver la memoria a Ollama.

```powershell
docker build -t giddy-image-local:latest .
```

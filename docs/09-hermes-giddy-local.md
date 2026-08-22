# 09 - Giddy conectado a Hermes local

Este despliegue usa a Giddy como interfaz de voz en tiempo real y a un Hermes
dedicado como cerebro. El contenedor se llama `hermes-giddy`, conserva su propia
memoria y no comparte sesiones, usuarios ni canales de WhatsApp con otros Hermes.

## Flujo

```text
Persona
  -> placa Giddy por voz
  -> servidor Giddy (WebSocket 8010)
  -> Whisper local (HTTP 9000)
  -> Hermes Giddy (API local 8664)
  -> EdgeTTS, voz es-AR-ElenaNeural
  -> placa Giddy por audio
```

Hermes recibe una clave de sesion estable mediante `X-Hermes-Session-Key`. Por
eso puede abrir una conexion nueva de voz sin perder la identidad ni la memoria
del asistente. Giddy no mantiene una segunda memoria ni interpreta herramientas:
esas dos responsabilidades quedan centralizadas en Hermes.

## Direcciones de esta instalacion

| Servicio | Direccion | Exposicion |
|---|---|---|
| WebSocket de voz | `ws://192.168.0.10:8010/xiaozhi/v1/` | Red local |
| OTA y HTTP | `http://192.168.0.10:8003/xiaozhi/ota/` | Red local |
| Hermes Giddy | `http://127.0.0.1:8664` | Solo esta PC |
| Whisper local | `http://127.0.0.1:9000` | Solo esta PC |

No hay que abrir el puerto 8664 en el router ni publicar su clave. La
configuracion privada se genera en `server/data/.config.yaml`, archivo ignorado
por Git.

## Operacion diaria

Desde `server/`:

```powershell
.\giddy.ps1 start
.\giddy.ps1 status
.\giddy.ps1 log
.\giddy.ps1 stop
```

`start` realiza tres tareas: levanta `hermes-giddy` si hace falta, espera su
endpoint de salud y hace una consulta corta de calentamiento antes de aceptar
voz. Esto evita que la primera respuesta del dia pague toda la latencia de carga
del modelo.

El inicio automatico esta registrado en el Programador de tareas de Windows como
`Giddy Hermes Voice`, con tres reintentos si Docker todavia no termino de abrir.
La misma tarea revisa el servicio una vez por hora: si Giddy murio, lo levanta;
si Giddy sigue vivo pero Hermes no responde, recupera y calienta Hermes.

Para regenerar la configuracion privada con otra IP LAN:

```powershell
.\configure-hermes.ps1 -LanIp 192.168.0.10
```

La primera vez, hay que abrir PowerShell como administrador y ejecutar:

```powershell
.\install-giddy-firewall.ps1
```

El script permite solamente los puertos 8010 y 8003 desde la subred local. No
abre Hermes ni Whisper a Internet.

## Capacidad y velocidad

- Modelo: `gpt-5.4-mini`, razonamiento bajo para conversacion rapida.
- Respuestas de voz limitadas y directas; las tareas complejas pueden continuar
  usando las herramientas completas de Hermes.
- Sesiones simultaneas del contenedor: 2.
- Herramientas disponibles: 16 grupos habilitados y 34 herramientas concretas,
  incluyendo archivos, terminal, web, navegador, memoria, vision, imagen, video,
  tareas, delegacion, cron y skills.
- Transcripcion: Whisper `small` local en CPU, `int8` y con idioma `es`; no
  consume una API paga. El modelo se conserva en el volumen Docker
  `hermes-stt-models` y el contenedor usa `unless-stopped`.
- Voz: EdgeTTS argentina femenina a velocidad `+25%`.

En la prueba de integracion de esta maquina, ya calentado, Hermes entrego el
primer fragmento en 3,10 segundos y termino la respuesta corta en 3,22 segundos.
Una accion real de memoria dio una confirmacion hablable en 3,47 segundos y
termino el trabajo en 15,08 segundos. La voz sintetizada tambien fue transcripta
correctamente por Whisper local.

Whisper `base` no se usa en produccion: con audio real del microfono llego a
interpretar "Que dia es hoy" como "Y dime, cual". Whisper `small` ocupa cerca
de 700 MB una vez caliente y tarda alrededor de 1,3 segundos en una frase
corta, un equilibrio mucho mejor entre precision, latencia y memoria.

## Aislamiento

El directorio del usuario Hermes es
`E:\HermesInstances\data\tenants\giddy`. Se copiaron skills y herramientas
aprobadas, pero no sesiones, memoria, base de estado, rutas de WhatsApp ni
historiales de otros usuarios. El contenedor tiene politica de reinicio
`unless-stopped`.

## Paso fisico pendiente

El firmware del repositorio ya apunta a `192.168.0.10:8003`, pero una placa que
tenga grabada la direccion anterior debe flashearse una vez por cable. Luego de
ese primer cambio, las proximas versiones pueden distribuirse por OTA.

Conviene reservar `192.168.0.10` para esta PC en el router. Si la direccion LAN
cambia, hay que regenerar la configuracion, actualizar el firmware y reiniciar
Giddy.

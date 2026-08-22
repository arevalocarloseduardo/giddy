# 08 — Levantar todo en la PC Windows

Los otros docs están escritos para macOS. Esta es la versión Windows, para mover el servidor a la PC con GPU (y de paso tener Hermes Agent en la misma máquina).

> Para la instalación local actual, integrada con el contenedor `hermes-giddy`,
> seguí también [09-hermes-giddy-local.md](09-hermes-giddy-local.md). Esa variante
> usa WebSocket `8010`, Whisper local y Hermes; el puerto `8000` queda libre para
> OpenVoice y no requiere claves de OpenRouter ni Groq.

> ✅ **Este repo ya trae el código**: `server/` y `firmware/` están vendorizados con nuestros cambios aplicados. No hace falta clonar el upstream ni aplicar parches.

## ⚠️ Leé esto primero: el paso que la gente olvida

La placa tiene la **dirección del servidor grabada en el firmware** (`CONFIG_OTA_URL`). Hoy apunta a la Mac (`192.168.0.51`).

Si movés el servidor a la PC, **la placa va a seguir buscando la Mac**. Hay que:

1. Darle **IP fija** a la PC en el router (si no, cambia y se rompe cada tanto)
2. Recompilar el firmware con esa IP
3. **Flashearlo una vez por cable** (esta vez sí hace falta el cable — es el cambio que habilita las futuras actualizaciones OTA)

Sin eso, Giddy no se va a conectar. Es el paso 5 de esta guía.

---

## 1. Requisitos

Con [winget](https://learn.microsoft.com/windows/package-manager/winget/) (viene en Windows 11):

```powershell
winget install Python.Python.3.10
winget install Git.Git
winget install Gyan.FFmpeg
```

Cerrá y abrí PowerShell. Verificá:

```powershell
python --version    # tiene que decir 3.10.x
git --version
ffmpeg -version
```

> 📌 **Python 3.10 específicamente.** Con 3.12+ algunas dependencias del servidor no compilan.

## 2. Clonar el repo

```powershell
cd $HOME
git clone https://github.com/arevalocarloseduardo/giddy.git
cd giddy
```

## 3. Instalar el servidor

```powershell
cd server
python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
```

> ⚠️ **El `requirements.txt` tiene un pin roto**: `vosk==0.3.45` no existe para todas las plataformas y ese único pin **aborta toda la instalación**. Instalá así:

```powershell
Select-String -Path requirements.txt -Pattern "^vosk" -NotMatch |
  ForEach-Object { $_.Line } | Set-Content requirements-win.txt
.\venv\Scripts\python.exe -m pip install -r requirements-win.txt
.\venv\Scripts\python.exe -m pip install vosk
```

(Tarda unos minutos: baja torch y compañía.)

## 4. Configurar

```powershell
New-Item -ItemType Directory -Force -Path data
Copy-Item ..\config\config.yaml.example data\.config.yaml
notepad data\.config.yaml
```

Cambiá **tres cosas**:

**a) Las claves** (los placeholders `TU_CLAVE_..._ACA`):

| Clave | De dónde | Costo |
|---|---|---|
| OpenRouter | [openrouter.ai](https://openrouter.ai) → Keys | ~US$0.35/mes |
| Groq | [console.groq.com](https://console.groq.com) → API Keys | gratis |

**b) La IP de la PC** — sacala con `ipconfig` (la IPv4 de tu red local):

```yaml
server:
  websocket: ws://192.168.0.XX:8000/xiaozhi/v1/
  vision_explain: http://192.168.0.XX:8003/mcp/vision/explain
```

**c) Rutas de modelos** — si vas a usar Vosk como fallback offline, bajalo:

```powershell
New-Item -ItemType Directory -Force -Path models\vosk
Invoke-WebRequest https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip -OutFile v.zip
Expand-Archive v.zip -DestinationPath models\vosk ; Remove-Item v.zip
```

(Si te quedás con Groq para el oído, este paso es opcional.)

## 5. Abrir los puertos en el firewall

Sin esto la placa no llega al servidor:

```powershell
# Ejecutar PowerShell como Administrador
New-NetFirewallRule -DisplayName "Giddy WebSocket" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Giddy HTTP/OTA"  -Direction Inbound -LocalPort 8003 -Protocol TCP -Action Allow
```

## 6. Arrancar

```powershell
.\giddy.ps1 start
.\giddy.ps1 status     # te muestra las URLs
.\giddy.ps1 log        # ver el log
```

Buscá en el log:

```
初始化组件: llm成功 OpenRouterLLM
初始化组件: asr成功 GroqASR
OTA接口是        http://192.168.0.XX:8003/xiaozhi/ota/
```

Probalo desde el navegador: `http://localhost:8003/xiaozhi/ota/` tiene que responder algo (no error).

## 7. Reapuntar la placa a la PC (el paso del cable)

Ahora sí, lo del principio. En `firmware/sdkconfig.defaults` cambiá la IP:

```
CONFIG_OTA_URL="http://192.168.0.XX:8003/xiaozhi/ota/"
```

Y recompilá + flasheá. Dos opciones:

### Opción A — desde la Mac (más simple, ya está todo instalado)

Cambiás la línea, `idf.py build`, y flasheás por cable. Fin.

### Opción B — compilar en Windows

Instalá el [ESP-IDF Windows Installer](https://dl.espressif.com/dl/esp-idf/) (elegí **v6.0.2**), abrí el "ESP-IDF PowerShell" del menú inicio y:

```powershell
cd $HOME\giddy\firmware
Copy-Item -Recurse ..\avatar\robot-pro_240 custom_emoji\
Copy-Item ..\avatar\generate_faces_pro.py custom_emoji\
idf.py set-target esp32s3     # ⚠️ ver nota abajo
idf.py build
idf.py -p COM3 flash          # tu puerto: revisá el Administrador de dispositivos
```

> ⚠️ En macOS `set-target` rompe cosas (ver docs/03) y usamos `IDF_TARGET=esp32s3 idf.py reconfigure`. En Windows con instalación limpia suele funcionar bien; si falla, borrá `build\` y probá el reconfigure.

Después del flasheo, la placa apunta a la PC y **las próximas actualizaciones ya van por OTA sin cable** (docs/05).

## 8. Que arranque solo con Windows (opcional)

Para no tener que arrancarlo a mano cada vez que prendés la PC:

```powershell
$acc = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-WindowStyle Hidden -File $HOME\giddy\server\giddy.ps1 start"
Register-ScheduledTask -TaskName "Giddy" -Action $acc `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn) -RunLevel Highest
```

## Problemas típicos de Windows

| Síntoma | Causa / solución |
|---|---|
| `pip install` falla compilando algo | Estás en Python 3.12+ → instalá 3.10 |
| Toda la instalación aborta | El pin `vosk==0.3.45` → usá el método del paso 3 |
| La placa no conecta | Firewall (paso 5) o la IP no coincide (paso 4b y 7) |
| Anda y a los días deja de andar | La IP de la PC cambió → ponele **IP fija** en el router |
| Giddy queda muda | `.\venv\Scripts\python.exe -m pip install -U edge-tts` |
| No encuentro el puerto COM | Administrador de dispositivos → Puertos (COM y LPT). Si no aparece, mantené **BOOT** al enchufar |

## Y después: Hermes Agent

En esta PC Hermes ya está integrado de forma nativa, sin un puente adicional.
La configuración, el aislamiento del usuario Giddy y las pruebas de operación
están en **[docs/09-hermes-giddy-local.md](09-hermes-giddy-local.md)**.

# Pruebas y operacion de Giddy

Este documento es la puerta de salida para cada cambio comercial. Una version
no se considera lista hasta completar las pruebas automaticas y los casos de
voz relevantes.

## Pruebas automaticas

Desde `server/`:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

La suite cubre reflejos sin modelo, hora y fecha, enrutamiento, limites de
contexto, aviso temprano, cache de voz persistente, eleccion explicita de
modelo, saneamiento de voz, entretenimiento seguro, sesiones estables de
Hermes, metricas privadas y acciones tactiles editables.

## Simulador de dispositivo

El simulador usa el WebSocket, TTS y audio reales. No necesita la placa.

Ruta instantanea:

```powershell
.\venv\Scripts\python.exe .\smoke-giddy.py "Hola, como estas" --expect-route instant
```

Ruta local:

```powershell
.\venv\Scripts\python.exe .\smoke-giddy.py "Contame un chiste corto y sano" --expect-route local
```

Ruta Hermes:

```powershell
.\venv\Scripts\python.exe .\smoke-giddy.py "Usa Hermes y responde circuito potente listo" --expect-route power
```

La salida confirma texto, cantidad de paquetes Opus, estados TTS, ruta elegida,
conexion inicial, latencia total y tiempo hasta el primer texto/audio. Para una
conversacion real importan `first_text_ms` y `first_audio_ms`: el dispositivo
mantiene abierto el WebSocket y no vuelve a pagar `connection_ms` en cada turno.

## Objetivos de velocidad

Con el dispositivo ya conectado y las frases precalentadas:

| Flujo | Primer texto | Primer audio |
|---|---:|---:|
| Reflejo conocido | Menos de 100 ms | Menos de 150 ms |
| Charla con modelo local | Confirmacion en menos de 100 ms | Confirmacion en menos de 150 ms |
| Trabajo Hermes | Confirmacion en menos de 100 ms | Confirmacion en menos de 150 ms |

Una frase dinamica nueva, como la hora exacta, puede necesitar una sintesis por
red la primera vez. Las repeticiones iguales se sirven desde cache. La latencia
total incluye la duracion completa del audio y no debe confundirse con el tiempo
hasta que Giddy empieza a hablar.

## Matriz de casos comerciales

| Caso | Resultado esperado |
|---|---|
| `Hola, como estas` | Instantaneo, cero tokens y audio precalentado |
| `Que hora es` | Instantaneo, hora argentina calculada en el momento |
| `Contame un chiste` | Local curado, cero tokens |
| Charla local no conocida | Responde con Qwen sin una muletilla inicial |
| `Explicame por que el cielo es azul` | Local en Ahorro; Hermes en Maxima calidad |
| `Busca el clima de hoy` | Hermes por informacion actual |
| Trabajo Hermes lento | Dice `Dame un segundo` antes de esperar el resultado |
| `Que tengo en mi agenda` | Hermes por datos personales |
| Girar el gadget 90 grados | La cara se mantiene derecha tras estabilizarse |
| Sacudirlo durante el reposo visual | Reproduce el despertar y restaura el brillo |
| `Callate`, `chau Giddy` | Duerme, cierra el canal y solo conserva la deteccion local de `Giddy` |
| `Escuchame pero no me hables` | Sigue ejecutando acciones sin sintetizar respuestas de voz |
| Pedir musica en modo silencioso | Reproduce la cancion sin anuncio hablado previo |
| Decir `Giddy` en modo silencioso | Vuelve a charla normal; si hay una orden despues, tambien la ejecuta |
| Sacudirlo dormido | Despierta, abre una conversacion nueva y vuelve a charla normal |
| Sacudirlo apagado por completo | No despierta; se usa el boton PWR |
| Consultar memoria | Usa `self.system.get_memory` y responde con datos en vivo |
| `Ayudame a decidir entre dos propuestas` | Hermes por decision compleja |
| `Arma un PDF` | Hermes por entregable |
| Modelo local apagado | Respaldo automatico en Hermes antes de emitir texto |
| Hermes reiniciando | La charla local sigue disponible |
| Giddy conserva el puerto pero no responde | El watchdog reemplaza el proceso bloqueado |
| Hermes conserva el contenedor pero no responde | Espera el arranque y reinicia el contenedor una vez |
| Reinicio de Windows | Recuperacion automatica al iniciar sesion |

## Control previo a vender

1. Ejecutar todas las pruebas unitarias.
2. Ejecutar un turno local y uno Hermes con el simulador.
3. Ejecutar un saludo instantaneo y la hora dos veces para comprobar la cache.
4. Abrir el panel en escritorio y celular.
5. Escuchar una muestra de los perfiles Robot, Joven y Natural.
6. Probar los cuatro botones tactiles en la placa.
7. Confirmar que la memoria pertenece solo al cliente correcto.
8. Confirmar que no existan plataformas o MCP heredados de otro tenant.
9. Apagar temporalmente Ollama y comprobar el respaldo antes de lanzar.
10. Revisar `server/data/watchdog.log` y el estado de la tarea programada.
11. Verificar giro y sacudida sobre la placa antes de promover una OTA a mas dispositivos.

La recuperacion se ejecuta al iniciar sesion y luego cada hora. Tiene exclusion
mutua para que dos revisiones no compitan, y no reinicia servicios saludables.

## Diagnostico rapido

```powershell
.\giddy.ps1 status
.\giddy.ps1 log
Get-Content .\data\watchdog.log -Tail 30
```

No borrar `giddy-product.json`, `giddy-setup-token.txt` ni la configuracion del
tenant para corregir una falla. El panel y los scripts son idempotentes: primero
se diagnostica, luego se reaplica la configuracion necesaria.

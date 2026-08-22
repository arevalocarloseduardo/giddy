# Guia de usabilidad y frases de Giddy

Ultima actualizacion: 2026-07-28

Esta guia reune las frases reales usadas durante el desarrollo de Giddy. No son
comandos rigidos: la persona debe poder hablar de forma natural. Cada ejemplo
indica el comportamiento esperado y tambien sirve como caso de prueba antes de
publicar una version.

## Principios de conversacion

- Giddy es un asistente cotidiano, no un personaje que propone historias o
  chistes sin que se los pidan.
- Un saludo, la hora y la fecha deben responder rapido y sin usar un modelo pago.
- Una accion clara se ejecuta directamente. No debe convertirla en una charla.
- Si un trabajo complejo tarda, puede decir una sola vez `Dame un segundo`.
- No debe comenzar las respuestas con muletillas como `A ver`.
- Debe responder siempre en espanol, salvo que la persona pida otro idioma.
- Las respuestas habladas deben ser cortas; el resultado visual o la accion
  tienen prioridad cuando fueron solicitados.

## Despertar y charla cotidiana

| Frase de ejemplo | Resultado esperado |
|---|---|
| `Giddy` | Despierta o vuelve al modo de charla. |
| `Hola, Giddy` | Saluda brevemente. |
| `Hola, como estas` | Respuesta corta e instantanea. |
| `Que dia es hoy` | Dice la fecha correcta de la zona configurada. |
| `Que hora es` | Dice la hora actual sin consultar un modelo remoto. |
| `Explicame por que el cielo es azul` | Da una explicacion clara y proporcionada. |
| `Ayudame a decidir entre estas dos propuestas` | Usa razonamiento completo y compara opciones. |
| `Que tengo en mi agenda` | Consulta la herramienta correspondiente si esta conectada. |
| `Arma un PDF con este informe` | Delega el trabajo complejo a Hermes y entrega el archivo. |

No hace falta repetir `Giddy` durante una conversacion que ya esta abierta.

## Clima

Cuando hay una ciudad configurada, Giddy debe usarla sin volver a preguntarla en
cada consulta. Se puede nombrar otra ciudad en la misma frase para reemplazarla
solo en ese pedido.

| Frase de ejemplo | Resultado esperado |
|---|---|
| `Como esta el clima hoy` | Temperatura, estado y consejo breve para la ciudad configurada. |
| `Cuantos grados va a hacer manana` | Pronostico de manana en la ciudad configurada. |
| `Va a llover manana` | Probabilidad de lluvia y consejo de paraguas cuando corresponda. |
| `Que pronostico hay para Mar del Plata manana` | Usa Mar del Plata solo para esta consulta. |
| `Como va a estar el tiempo esta tarde` | Responde sobre el periodo pedido cuando los datos lo permiten. |

Frases imperfectas del reconocimiento de voz que tambien deben funcionar:

- `Cuanto helado va a ser manana` debe entenderse como una consulta de grados.
- `Quiero un helado` no debe confundirse con una consulta del clima.
- `Necesito tiempo para terminar este trabajo` no debe abrir el pronostico.

## Musica

La musica puede pedirse por cancion, artista, genero o busqueda en YouTube. Al
comenzar la reproduccion debe aparecer el avatar musical tocando la guitarra. El
anuncio previo, cuando el modo permite voz, debe ser uno solo y corto.

| Frase de ejemplo | Resultado esperado |
|---|---|
| `Reproducime La noche sin ti` | Busca y reproduce la cancion. |
| `Poneme De musica ligera de Soda Stereo` | Reproduce la version coincidente. |
| `Pone musica de YouTube, Ji ji ji de Los Redondos` | Busca en YouTube y reproduce el audio. |
| `Busca una cancion que se llama Grupo Niche y reproducila` | Busca y reproduce en un solo pedido. |
| `Reproduci Persiana Americana` | Reproduce la cancion pedida. |
| `Reproduci desde YouTube Seminare de Seru Giran` | Usa YouTube como fuente. |
| `Poneme una cancion de rock` | Elige una coincidencia valida del genero. |
| `Daddy Yankee, Llamado de emergencia` | Usa el alias conocido aunque no se repita `reproducir`. |

Frases imperfectas del reconocimiento de voz que tambien deben funcionar:

- `Daddy Junkins llamado de emergencia` debe interpretarse como Daddy Yankee.
- `Grupo Nietzsche` debe interpretarse como Grupo Niche cuando se esta pidiendo
  musica.
- `Que musica te gusta` es una pregunta de charla y no debe iniciar reproduccion.

Durante la musica:

- La cara debe mostrar la animacion musical y la guitarra.
- El subtitulo debe conservar la misma orientacion que la cara.
- No debe aparecer texto en otro idioma por metadatos de YouTube.
- En modo silencioso reproduce sin anuncio hablado.
- `Callate`, `chau Giddy` o una despedida deben detener la interaccion y dormirlo.

## Creacion de imagenes

Giddy debe reconocer pedidos directos y tambien pedidos en dos pasos. La imagen
se genera, se adapta a la pantalla sin estirarla y se muestra en el dispositivo.

| Frase de ejemplo | Resultado esperado |
|---|---|
| `Dame la imagen de un gatito con un helado` | Genera y muestra una imagen cuadrada. |
| `Mostrame una imagen de un robot feliz` | Genera y muestra la imagen. |
| `Poneme una imagen de una ciudad futurista` | Genera y muestra la imagen. |
| `Creame una imagen vertical de un robot tocando la guitarra` | Genera una composicion vertical. |
| `Haceme un flyer horizontal con una peluqueria moderna` | Genera una composicion horizontal. |
| `Dibujame una cocina luminosa de estilo minimalista` | Genera una ilustracion cuadrada. |
| `Si me podes crear una imagen` | Pide o espera la descripcion. |
| `Un perrito comiendo helado` | Completa el pedido anterior y muestra el resultado. |

Caso real de regresion de voz:

- `Dame la imagen de un gatito con el nalado` debe activar la creacion aunque la
  ultima palabra haya sido transcripta de forma imperfecta.
- `Que es una imagen vectorial` es una pregunta y no debe generar una imagen.
- `Podes ver esta imagen` no debe generar otra imagen por accidente.

## Modos de interaccion

Giddy mantiene el estado elegido hasta que la persona lo cambie.

### Charla

Escucha, responde con voz y ejecuta acciones. Es el modo normal al despertar.

Frases para volver a charla desde escucha silenciosa:

- `Giddy`
- `Giddy, ya podes hablar`
- `Volve a hablar`
- `Hablame de nuevo`
- `Giddy, poneme musica` vuelve a charla y ejecuta la orden en el mismo turno.

### Escucha silenciosa

Escucha y ejecuta, pero no usa voz sintetizada. Puede reproducir musica, crear
imagenes y usar herramientas sin comentar el proceso.

Frases equivalentes:

- `Escuchame pero no me hables`
- `Segui escuchando sin hablar`
- `Modo silencioso`
- `No me hables`
- `Solo escucha`
- `Hace lo que te pida sin hablar`

### Dormido

Cierra la conversacion y deja de enviar audio. Solo la deteccion local de
`Giddy` o una sacudida pueden iniciar una conversacion nueva.

Frases equivalentes:

- `Callate`
- `Dormite`
- `Andate a dormir`
- `No me escuches mas`
- `Silencio`
- `Basta por hoy`
- `Chau Giddy`
- `Hasta manana`
- `Buenas noches`

## Movimiento y controles fisicos

Estas acciones no requieren una frase:

| Accion | Resultado esperado |
|---|---|
| Girar el dispositivo 90 grados | La cara y el subtitulo se acomodan juntos. |
| Sacudirlo durante el reposo visual | Despierta con su animacion y restaura el brillo. |
| Sacudirlo dormido | Abre una conversacion nueva en modo charla. |
| Mantenerlo quieto | La orientacion no debe saltar por vibraciones pequenas. |
| Apagado profundo | Solo despierta con el boton de encendido. |
| Bateria casi agotada | Muestra y dice `Urgente, cargame que me apago` una sola vez. |

Los botones tactiles configurados deben mostrar una reaccion visible inmediata y
no pueden tapar el subtitulo.

## Estado del dispositivo

| Frase de ejemplo | Resultado esperado |
|---|---|
| `Cuanta memoria tenes` | Consulta RAM interna, PSRAM y flash disponibles. |
| `Cuanta memoria te queda` | Responde con valores actuales, no estimados. |
| `Que modelo estas usando` | Explica brevemente la ruta activa sin exponer secretos. |
| `Cuanto estoy consumiendo` | Resume el tipo de uso y costo disponible en las metricas. |

## Comportamientos que no debe tener

- No proponer historias, chistes o juegos en cada respuesta.
- No reir ni reproducir sonidos extranos si no fueron pedidos.
- No responder en chino u otro idioma por una transcripcion o metadato externo.
- No repetir eternamente `Actualizando el sistema`.
- No pedir la ciudad en cada consulta si ya existe una predeterminada.
- No decir que reprodujo una cancion si el audio no comenzo.
- No decir que creo una imagen si no pudo mostrarla.
- No reemplazar el avatar por una figura generica salvo durante una recuperacion
  explicita del sistema.
- No estirar fotos o imagenes para llenar la pantalla.
- No usar voz para narrar acciones cuando esta en escucha silenciosa.

## Recorrido de prueba antes de publicar

Probar estas frases en este orden permite revisar el flujo principal sin usar
comandos tecnicos:

1. `Giddy`
2. `Hola, como estas`
3. `Que dia es hoy`
4. `Que hora es`
5. `Como esta el clima hoy`
6. `Va a llover manana`
7. `Poneme De musica ligera de Soda Stereo`
8. Confirmar audio, avatar musical, guitarra y subtitulo orientado.
9. `Escuchame pero no me hables`
10. `Reproduci Persiana Americana`
11. Confirmar que reproduce sin anuncio hablado.
12. `Giddy, ya podes hablar`
13. `Dame la imagen de un gatito con un helado`
14. Confirmar que genera, descarga y muestra la imagen sin deformarla.
15. Girar el dispositivo y confirmar que cara, imagen y subtitulo se acomodan.
16. `Cuanta memoria te queda`
17. `Chau Giddy`
18. Confirmar que duerme y deja de escuchar.
19. Sacudirlo y confirmar que despierta en una conversacion nueva.

## Registro de nuevos casos

Cada feedback de una persona debe agregarse aqui con este formato:

```markdown
### Caso: nombre corto

- Frase dicha: `texto exacto`
- Transcripcion recibida: `texto reconocido por el ASR`
- Resultado esperado: descripcion breve
- Resultado observado: descripcion breve
- Estado: pendiente / corregido / verificado
- Prueba automatica: archivo y nombre de la prueba, cuando exista
```

Conservar la frase exacta y su transcripcion permite mejorar el reconocimiento
para todas las unidades sin convertir la experiencia en una lista de comandos.

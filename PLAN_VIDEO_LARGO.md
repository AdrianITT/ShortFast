# Plan: Pipeline de video largo 16:9 (15-20 min)

Estado: **planeado, sin iniciar**. Última actualización: 2026-10-01.
Este documento permite retomar el trabajo en cualquier momento sin contexto previo.

---

## 1. Objetivo

Generar videos de 15 a 20 minutos en 16:9 (1920x1080) para YouTube, con el mismo estilo de los shorts (voz por tramos, música, texto en pantalla), de forma automática y adaptable a cualquier guion.

## 2. Reglas del proyecto

1. El código de los shorts 9:16 **no se modifica**: `main.py`, `render.py`, `guia_ia.py`, `generar_guia.py`.
2. El video largo es un pipeline paralelo, con archivos, endpoints y carpetas propios.
3. Las utilidades genéricas (`duracion`, `run`, logs/estado, transiciones) se **copian**, no se importan, para que un cambio en shorts no rompa el largo.
4. Los shorts y el video largo son producciones independientes.

## 3. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Relación con los shorts | Independientes |
| Voces | Un mp3 por tramo, como en los shorts |
| Material visual | Mezcla de imágenes (zoom/paneo) y clips de video |
| Texto en pantalla | Sí, como en los shorts |
| Origen del material | Hoy lo sube el usuario; automatización por evaluar (Fase 4) |

## 4. Contexto técnico para retomar

Lo que se sabe del servicio actual (leído del código el 2026-10-01):

- Contenedor `python:3.12-slim` + ffmpeg + FastAPI/uvicorn, puerto 8123. El Dockerfile solo copia `main.py`; `render.py` y `guia_ia.py` deben llegar por volumen (**por verificar cómo se monta**).
- Variables de entorno: `PROYECTOS` (`/data/proyectos`), `SALIDA` (`/data/salida`), `RENDER_PY`, `PLANTILLA`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `CACHE_PROBE`.
- Ruta del servidor: `/DATA/video-editor/` (proyectos, salida, plantilla).
- Flujo actual de un short: `nuevo-short` → subir archivos → `generar_guia.py` → `render-short`.
- `render.py:19` fija 1080x1920; `render.py:36` escala imágenes a 1620x2880.
- `guia_ia.py` (`normalizar`) sobrescribe `formato` a 1080x1920.
- `render.py` (`unir`) mete todos los clips en un solo comando ffmpeg con cadena de `xfade`; no escala a cientos de clips.
- Una guía de 22 KB (tabla ASCII) en una sola llamada a Gemini ya genera lentitud, saturación (429/503) y problemas de contexto.
- Cambio ya hecho aparte: caché SHA256 en `/probe` (`main.py`). Probado con stubs, **falta probarlo en Docker**.

## 5. Arquitectura propuesta

| Pieza | Función |
|---|---|
| `render_largo.py` | Render 16:9; une por bloques; soporta imágenes y clips de video |
| `guia_largo_ia.py` | Guion en texto plano a `guia.json`, por tramos pequeños, en paralelo, con reintento y avance guardado |
| Endpoints `/largo/nuevo`, `/largo/generar-guia`, `/largo/render`, `/largo/estado/{p}`, `/largo/video/{p}` | Mismo estilo que los de shorts, con prefijo propio |
| `/data/proyectos_largos/` | Carpeta separada de los shorts |
| Comandos de shell | Equivalentes a `nuevo-short` y `render-short` |

Estructura de un proyecto largo (borrador, a confirmar en Fase 0):

```
proyectos_largos/<nombre>/
  guion.md          texto plano del guion
  voz/              un mp3 por tramo
  imagenes/         material horizontal
  clips/            clips de video
  musica/
  fuentes/
  guia.json         generado
```

## 5.1 Pendientes previos (antes de la Fase 0)

- [x] Probar el caché SHA256 de `/probe` en Docker: verificado el 2026-10-02 (1ª llamada 1.57 s `cache:false`, 2ª 0.26 s `cache:true`; copia con mismo contenido reutiliza; 404 y 400 correctos)
- [x] Cómo se monta el código: verificado el 2026-10-01. `/home/adrian/ffmpeg-api` se monta en `/app` y `/DATA/video-editor` en `/data` (el Dockerfile se actualizó el 2026-10-02: ahora copia todos los `.py`; el volumen sigue siendo para el servidor actual). Los archivos nuevos se despliegan dejándolos en esta carpeta.

## 5.2 Integración con n8n (workflow `Bot-Sin-excusas`)

El control del flujo se hace desde Telegram con el workflow `Bot-Sin-excusas` (id `jUGEAozseUtsLzTp`, activo). Copia de lectura: `bot_sin_excusas.json` (2026-10-01).

**Estado actual (solo shorts).** Trigger de Telegram → filtro por chat → switch por comando. Llama a `ffmpeg-api` en `http://192.168.1.101:8123`.

| Comando | Endpoint | Notas |
|---|---|---|
| `/proyectos` | `GET /proyectos` | Lista con iconos de estado |
| `/nuevo-short n` | `POST /nuevo` | Avisa qué subir |
| `/revisar n` | `GET /revisar/{n}` | Qué falta |
| `/render-short n` | `POST /render` → espera 1 min → `GET /estado/{n}` en bucle → `GET /video/{n}` → `sendVideo` | Bucle sin tope de intentos |

**Redes.** `n8n` y `ffmpeg-api` están en la red Docker `bridge` (172.17.0.6 y 172.17.0.3). Ambos montan `/DATA/video-editor`.

**Cambios a hacer en el workflow** (no se hacen sin confirmar con el usuario):
- [ ] Comando `/generar-guia n` → `POST /generar-guia` (el endpoint ya existe en `main.py`; hoy el `guia.json` se sube a mano). Cierra el flujo de shorts.
- [ ] Comandos del video largo: `/nuevo-largo`, `/generar-guia-largo`, `/render-largo`, `/estado-largo`. Mismo patrón que los de shorts, contra `/largo/*`.
- [ ] Video largo: **no enviar el mp4 por Telegram** (límite de 50 MB para bots; un 1080p de 15-20 min lo supera). Avisar con ruta/tamaño al terminar.
- [ ] Bucle de espera con tope de intentos, e intervalo mayor para renders largos (5 min en vez de 1).
- [ ] URL base y chat ID en variables en vez de repetirlos en cada nodo (la IP `192.168.1.101:8123` está en 6 nodos).
- [ ] Borrar nodos de prueba sueltos: `HTTP Request` (`/health`) y `Send a text message1` («Hola, Habla N8N»).

**Acceso a la API de n8n.** La clave se guarda en `~/.n8n_api_key` (permisos 600) y se usa con `curl -H "X-N8N-API-KEY: $(cat ~/.n8n_api_key)" http://localhost:5678/api/v1/...`. La clave se compartió en el chat el 2026-10-01: **rotarla** cuando termine el trabajo con n8n.

## 5.3 Panel de control (agilidad)

Para no depender de muchos comandos, se añade el paquete `panel/`: menús en vez de comandos, con interfaces que se habilitan o deshabilitan en `panel.json`.

- [x] Interfaz de terminal: `python3 -m panel` (2026-10-02). Menú de proyectos con estado y acciones: revisar, generar guía (IA/local), renderizar con progreso, estado, descargar.
- [x] Acción «Generar voces (Kokoro)» en la terminal (2026-10-02): pegas el guion en la terminal (script bash o `archivo.mp3 | texto`, termina con `FIN`), se procesa en memoria y se escribe en `voz/`; no se guarda ningún archivo de guion. Pendiente: reutilizarla para los tramos del video largo.
- [ ] Interfaz Telegram con botones (`/menu`) en `Bot-Sin-excusas` (requiere confirmación para tocar n8n).
- [ ] Interfaz web (`/ui`), con autenticación si se abre fuera de la red local.
- [ ] Añadir acciones del video largo al panel cuando existan los endpoints `/largo/*` (Fase 3).

Arquitectura: `ClienteApi` (HTTP) → `ServicioProyectos` (acciones) → `Interfaz` (terminal/web/Telegram). Cada interfaz nueva es una clase registrada en `panel/interfaces/__init__.py`. Como solo usa la API, funciona desde cualquier equipo cambiando `api_url`.

## 6. Fases

Cada fase tiene entregables y un criterio de "terminado". No pasar a la siguiente sin cumplirlo.

### Fase 0: Definir formato

_En curso (2026-10-02): borrador en `FORMATO_VIDEO_LARGO.md` y `ejemplos/guia_largo_ejemplo.json`, pendiente de confirmar._
**Entregables**
- [ ] Estructura de carpetas confirmada
- [ ] Esquema de `guia.json` 16:9 (formato, escenas, tipo de medio por escena: imagen o clip)
- [ ] Reglas de nombres para emparejar voz, imagen y clip por tramo

**Terminado cuando:** existe un `guia.json` de ejemplo escrito a mano para un tramo de 1 minuto.

**Necesito del usuario:** un guion real de ejemplo y su material (voces, imágenes, clips) o un subconjunto.

### Fase 1: Render por bloques (va primero: mayor riesgo)
**Entregables**
- [x] `render_largo.py` con ancho y alto como parámetros (1920x1080) — paquete `largo/` (2026-10-02)
- [x] Escena con imagen (zoom/paneo adaptado a 16:9; verticales completas sobre fondo borroso)
- [x] Escena con clip de video (ajuste de duración a la voz: recortar, congelar, bucle)
- [x] Texto en pantalla para 16:9 (posiciones y tamaños)
- [x] Unión por bloques (grupos de 10-20 clips) y unión final
- [x] Mezcla de audio: voces + música con volumen por escena
- [x] Log y estado compatibles con el estilo de shorts (mismo formato de mensajes; falta el endpoint, Fase 3)

**Terminado cuando:**
- [x] Un proyecto de ~3 min renderiza correctamente de punta a punta (2026-10-02: 169 s en 6.9 min).
- [x] Un proyecto de ~17 min renderiza sin agotar RAM ni disco (2026-10-02, prueba sintética de 1016 s: ~40 min de video unido, RAM libre nunca bajó de 2.0 GB, disco pico 952 MB; el audio falló por la expresión de volumen y se corrigió y verificó con `--reanudar`). **Pendiente:** un render completo de 15-20 min de una sola vez con el audio corregido, y con material real, no repetido.
- [x] Se anotan tiempo de render y consumo de RAM en el registro de avance (ver abajo y `HISTORIAL.md`).

**Mediciones (4 núcleos, 7.8 GB de RAM, con los demás contenedores corriendo):**

| Prueba | Video | Render | Pico de un ffmpeg |
|---|---|---|---|
| 12 escenas, material real de `short_20` | 84.7 s | 2.6 min | 1.9 GB (bloques de 12) |
| 24 escenas (sintética) | 169 s | 6.9 min | 1.9 GB |
| 144 escenas (sintética) | 1016 s | ~42 min | 1.9 GB |

El tiempo es ~2.5x la duración del video; el pico de memoria depende del tamaño del bloque (~1 GB con `--bloque 5`, ~1.9 GB con 12), no de la duración. La unión es casi tan lenta como las escenas (el video se codifica varias veces). **Posible optimización** (no hecha): unir bloques sin recodificar todo.

### Fase 2: Guía automática por tramos
**Entregables**
- [ ] División del guion en tramos de 30-60 s
- [ ] Llamada a Gemini por tramo, en paralelo, con reintento y fallback de modelo
- [ ] Avance guardado por tramo (reanudar sin repetir)
- [ ] Ensamblado y validación por código (rutas, tamaños de texto, defaults)

**Terminado cuando:** un guion real de 15-20 min genera su `guia.json` completo, sin errores de contexto, y se puede reanudar si se interrumpe.

### Fase 3: Integración
**Entregables**
- [ ] Endpoints `/largo/*`
- [ ] Comandos de shell equivalentes a `nuevo-short` y `render-short`
- [ ] Estado y logs del render largo
- [ ] Comandos de Telegram en `Bot-Sin-excusas` (ver 5.2)

**Terminado cuando:** el flujo completo funciona desde el shell y desde Telegram, igual que el de shorts.

### Fase 4: Automatización de material visual (opcional)
Pregunta abierta: ¿se puede automatizar la obtención de imágenes y clips? Sí, pero hay que elegir. Las cifras de calidad y costo están **sin verificar**.

Flujo común: por cada tramo se produce un prompt visual o una consulta de búsqueda, el sistema trae el material y el usuario revisa antes de renderizar.

| Opción | Ventajas | Riesgos |
|---|---|---|
| Stock (Pexels, Pixabay, etc.) | Gratis o barato, rápido, hay clips reales | Relevancia floja en temas abstractos o emocionales; verificar licencias |
| Generación con IA | Estilo consistente | Costo por imagen, tiempo, consistencia entre imágenes, políticas del proveedor |
| Híbrido | Equilibrio | Más piezas que mantener |

**Pruebas pendientes**
- [ ] Elegir 1 fuente de stock y revisar sus términos de licencia para YouTube
- [ ] Probar 20 tramos de un guion real y medir qué porcentaje de material es aceptable
- [ ] Estimar costo si se usa generación con IA

**Terminado cuando:** hay datos medidos para decidir entre stock, IA o híbrido.

## 7. Riesgos y preguntas abiertas

- Tiempo y RAM del render de 20 min (se mide en Fase 1).
- Los shorts usan imágenes verticales; el largo necesita horizontales.
- Cantidad de imágenes y clips por video (decenas a cientos) y cómo nombrarlos.
- Cómo se monta el código en el contenedor (volumen vs. imagen) para desplegar los archivos nuevos.
- Seguridad: el `.env` contiene la `GEMINI_API_KEY` en texto plano; conviene regenerarla si el proyecto se comparte.

## 8. Cómo retomar

1. Leer las secciones 2 y 4 de este documento.
2. Ir a la primera fase con casillas sin marcar.
3. Pedir al usuario el material indicado en "Necesito del usuario".
4. Al terminar cada entregable, marcar la casilla y añadir una fila al registro de avance.

## 9. Registro de avance

| Fecha | Qué se hizo |
|---|---|
| 2026-10-01 | Análisis del servicio; decisiones de diseño; plan creado. Caché SHA256 en `/probe` (pendiente probar en Docker). Sin cambios en el código de shorts. |
| 2026-10-01 | Revisión del código. Nota: `main.py` (caché `/probe`, `/generar-guia`) y `generar_guia.py` (regex `IMG_`) sí tienen cambios respecto a los `.bak`; son ajustes menores, no tocan `render.py`. Verificado el montaje por volumen. Leído el workflow `Bot-Sin-excusas` vía API de n8n (solo lectura); documentada la integración en 5.2. Nada modificado en n8n. |
| 2026-10-02 | Caché de `/probe` probado en el contenedor real. `/generar-guia` en n8n: el usuario confirma que funcionó el 2026-10-01. Creados `REGLAS.md` e `HISTORIAL.md`. |
| 2026-10-02 | Creado y probado el panel de terminal (`panel/`, `panel.json`). Ver 5.3. |
| 2026-10-02 | Panel: añadida y probada la generación de voces con Kokoro desde la terminal. |
| 2026-10-02 | Voces: cambiado a modo «pegar guion» (sin `voces.txt`). Probado con Kokoro. |
| 2026-10-02 | Instalación en laptop: `docker-compose.yml`, `.env.example`, `Dockerfile` actualizado, panel con variables de entorno y `README.md`. Probado en entorno aparte. |
| 2026-10-02 | Comandos de shell portables en `comandos/` (nuevo-short, render-short, guia-short) y guía de uso en el README. Probados con compose aparte. Fase 3: los equivalentes del video largo irán en la misma carpeta. |
| 2026-10-02 | Fase 0 iniciada: borrador de estructura, reglas de nombres y esquema 16:9 en `FORMATO_VIDEO_LARGO.md`; ejemplo con nombres ficticios. Pendiente confirmación y material real. |
| 2026-10-02 | Fase 1 iniciada y escrita: paquete `largo/` + `render_largo.py`. Probado con material de `short_20` (12 escenas: OK, 3.6 min de render para 1.4 min de video) y con una prueba sintética de ~3 min (OK, 6.9 min, pico 1.9 GB). Prueba de ~20 min en curso. |
| 2026-10-02 | Fase 1 verificada con pruebas de 85 s, 169 s y 1016 s. Bug de la curva de volumen con muchas escenas corregido; añadido `--reanudar`. Pendiente: render completo de 15-20 min con material real. |
| 2026-10-02 | Optimización del render: una pasada por escena + puentes xfade + unión `-c copy` (sin bloques). Render de 16 min: de 40.9 a 14.2 min (2.9x), sin errores de decodificación. Pendiente de revisión visual del video largo y de decidir si se reduce el pico de memoria (2.6 GB). Sin commit. |
| 2026-10-02 | Calidad de shorts (opción A, solo `render.py`): volumen a -14 LUFS (de -23.4), efecto `zoom_out_lento` y animación `golpe` implementados. Regresión con `short_26`: solo cambian los fotogramas esperados. Pendiente: texto sobre el sujeto (guía), etiqueta «IMG_04» impresa en una imagen fuente, resto de mejoras de efectos (easing, supersampling, transiciones). Sin commit. |

# ffmpeg-api

Servicio que automatiza la creación de **YouTube Shorts verticales (1080x1920)**: toma tus imágenes, voces y música, y devuelve un video terminado con zoom/paneo, transiciones, texto en pantalla y mezcla de audio. Incluye un **panel web** (puerto 8090) y un panel de terminal para manejarlo sin comandos. Uso paso a paso del panel web: **`GUIA_USO.md`**.

> Estado: los shorts están en producción. El pipeline de **video largo 16:9 (15-20 min)** está planeado, aún sin iniciar (ver `PLAN_VIDEO_LARGO.md`).

---

## 1. Qué hace

| Pieza | Función |
|---|---|
| **API (`ffmpeg-api`)** | Crea proyectos, revisa qué falta, genera la guía, renderiza en segundo plano, informa el estado y entrega el mp4 |
| **Guía (`guia.json`)** | Describe escenas, efectos, textos y música. Se genera con IA (Gemini) desde un guion, o desde un borrador local sin IA |
| **Voz (Kokoro)** | Convierte texto en mp3, un archivo por tramo |
| **Panel de terminal** | Menú para usar todo lo anterior sin recordar comandos |

Flujo de un short:

```
Crear proyecto → generar voces → subir imágenes y música → generar guía → renderizar → descargar
```

### Endpoints de la API (puerto 8123)

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/health` | Comprobar que el servicio y ffmpeg responden |
| GET | `/proyectos` | Listar proyectos con su estado |
| POST | `/nuevo` | Crear proyecto (copia la plantilla) |
| GET | `/revisar/{p}` | Qué hay subido y qué falta |
| POST | `/generar-guia` | Guía con Gemini desde `guia.md` |
| POST | `/generar-guia-local` | Guía desde `guia_borrador.json`, sin IA |
| POST | `/render` | Iniciar el render (no bloquea) |
| GET | `/estado/{p}` | Progreso y últimas líneas del log |
| GET | `/video/{p}` | Descargar el mp4 |
| POST | `/probe` | Duración y resolución de un archivo (con caché) |

---

## 2. Cómo se usa

### Con el panel web (recomendado)

Abre `http://<ip-del-equipo>:8090`: proyectos, archivos, voces (generar, cortar una grabación, clonar tu voz), guía, render y biblioteca de música. Todo el flujo está en **`GUIA_USO.md`**.

### Con el panel de terminal

```bash
python3 -m panel
```

```
Menú principal
  1) Elegir un proyecto
  2) Crear proyecto nuevo
  0) Salir
```

Dentro de un proyecto:

| Opción | Qué hace |
|---|---|
| Revisar qué hay subido | Cuenta imágenes, voces y música; avisa de lo que falta |
| **Generar voces (pegar guion)** | Pegas el guion y escribes `FIN`; se generan los mp3 en `voz/` |
| Generar guía con IA (Gemini) | Crea `guia.json` desde `guia.md` |
| Generar guía desde borrador (local) | Crea `guia.json` desde `guia_borrador.json` |
| Renderizar | Inicia y muestra el progreso (Ctrl+C deja de mirar; el render sigue) |
| Ver estado del render | Estado y log |
| Descargar video | Guarda el mp4 en tu carpeta de descargas |

**Generar voces.** Acepta dos formatos y detecta cuál pegaste:

```
# Líneas
voz: em_alex
01_hook.mp3 | Tu miedo al fracaso te ha costado más... que todos tus fracasos juntos.
02_b.mp3 | El negocio que no abriste porque podía fallar.
```

o tu script de bash con `VOZ="em_alex"` y llamadas `g "01_hook.mp3" "texto"` (se lee como texto, **nunca se ejecuta**). Muestra un resumen, pide confirmar y, al terminar, avisa «Éxito» y descarta lo pegado. Si ya existen audios pregunta si sobrescribe; si un tramo falla, ofrece reintentar solo los fallidos.

### Con comandos de shell

Tres comandos, equivalentes a los del menú (instalación en la sección 3):

| Comando | Qué hace |
|---|---|
| `nuevo-short short_01_tema` | Crea el proyecto desde la plantilla (`voz/`, `imagenes/`, `musica/`, `fuentes/`) |
| `render-short short_01_tema` | Revisa que existan todos los archivos de `guia.json`, renderiza en segundo plano y muestra el progreso. **Ctrl+C solo deja de mirar; el render sigue** |
| `guia-short short_01_tema` | Genera `guia.json` desde `guia_borrador.json` y renderiza, todo en uno |

Flujo típico:

```bash
nuevo-short short_23_tema          # 1. crear
#   sube imagenes/, voz/, musica/ y guia_borrador.json a datos/proyectos/short_23_tema/
guia-short short_23_tema           # 2. guía + render        (o: render-short si ya tienes guia.json)
# resultado: datos/salida/short_23_tema.mp4   ·   log: datos/salida/logs/short_23_tema.log
```

Las voces se generan desde el panel (**Generar voces (pegar guion)**); no hay comando de shell para eso.

Si algo falla, los comandos lo dicen: nombre inválido, proyecto existente, falta `guia.json`, o la lista de archivos que faltan.

### Con Docker

```bash
docker compose up -d                  # arrancar todo
docker compose ps                     # estado de los servicios
docker compose logs -f ffmpeg-api     # ver logs de la API
docker compose restart ffmpeg-api     # reiniciar solo la API
docker compose up -d --build          # reconstruir tras cambiar código (.py)
docker compose down                   # apagar (los datos en datos/ se conservan)

# ejecutar algo dentro del contenedor, p. ej. un render a mano:
docker compose exec ffmpeg-api python /app/render.py short_01_tema
```

Si la API corre como contenedor suelto (como en el servidor original), usa `docker exec ffmpeg-api ...` y define `API_CONTENEDOR=ffmpeg-api` en `.env` para que los comandos de shell lo usen.

### Con la API directamente

```bash
curl -X POST localhost:8123/nuevo  -H 'Content-Type: application/json' -d '{"proyecto":"short_01"}'
curl -X POST localhost:8123/render -H 'Content-Type: application/json' -d '{"proyecto":"short_01"}'
curl localhost:8123/estado/short_01
curl -o short_01.mp4 localhost:8123/video/short_01
```

### Opciones de calidad de los shorts (`guia.json`)

| Campo / valor | Efecto |
|---|---|
| `"lufs": -14` (por defecto) | Normaliza el volumen final a -14 LUFS (el estándar de YouTube). Otro número lo cambia; `null` o `0` lo desactiva |
| `"efecto": "zoom_out_lento"` | Zoom de salida lento (1.08 → 1.0) |
| `"animacion": "golpe"` (en un texto) | El texto entra 18 % más grande y se asienta en 0.2 s |

Efectos disponibles en shorts: `zoom_in_lento`, `zoom_in`, `zoom_out`, `zoom_out_lento`, `paneo_der`, `paneo_rapido`, `ninguno`. Animaciones de texto: `ninguna`, `fade`, `palabra_por_palabra`, `golpe`.

### Estructura de un proyecto

```
<DATA_DIR>/proyectos/<nombre>/
  imagenes/    voz/    musica/    fuentes/
  guia.md                  guion para la IA (opcional)
  guia_borrador.json       alternativa sin IA (opcional)
  guia.json                generado
<DATA_DIR>/salida/<nombre>.mp4     video final (y logs/)
```

---

## 3. Cómo se instala

Guía completa (requisitos, CasaOS, voces, actualizar, problemas): **[GUIA_INSTALACION.md](GUIA_INSTALACION.md)**.

Requisitos: Linux x86_64 con **Docker y Docker Compose**.

```bash
git clone <este repositorio> shortfast && cd shortfast
./instalar.sh               # crea .env, construye y arranca API + panel web + las voces elegidas
```

Levanta, con Docker: las carpetas de datos, la API (8123), el **panel web** (8090) y las voces elegidas por perfiles (`supertonic`, `clonador`, `kokoro`, `edge`; por defecto Supertonic + clonador). Con CasaOS se registra además como una app «ShortFast». `./actualizar.sh` y `./desinstalar.sh` hacen lo que dicen (los datos se conservan).

El **panel de terminal** sigue disponible fuera de Docker: `python3 -m panel` con las variables de la última sección de `.env.example`.

**Comandos de shell (opcional).** Para tener `nuevo-short`, `render-short` y `guia-short` en cualquier carpeta:

```bash
./comandos/instalar.sh        # crea enlaces en ~/.local/bin (DESTINO=~/bin ./comandos/instalar.sh para otra carpeta)
```

Si el instalador avisa que esa carpeta no está en tu `PATH`, añade la línea que muestra a `~/.bashrc` y abre otra terminal. Leen el mismo `.env` que el panel (`DATA_DIR`, `API_CONTENEDOR`). Cambiar de laptop a servidor no exige editarlos.

**Plantilla (una sola vez).** Los proyectos nuevos se crean a partir de `datos/plantilla/`. Copia ahí la tuya:

```
datos/plantilla/
  fuentes/          tipografías (p. ej. montserrat/)
  imagenes/         p. ej. logo
  voz/              audios fijos (p. ej. intro/outro)
  ejemplo_guia.json guía de ejemplo (la usa la IA como modelo)
```

Comprobar que todo vive:

```bash
curl localhost:8123/health
docker compose ps
```

Comandos útiles: `docker compose logs -f ffmpeg-api` · `docker compose down` · `docker compose up -d --build` (tras cambiar código).

### Variables de entorno (`.env`)

Las leen `docker compose` y el panel. Todas son opcionales.

| Variable | Por defecto | Qué configura |
|---|---|---|
| `DATA_DIR` | `./datos` | Carpeta del equipo con `proyectos/`, `salida/` y `plantilla/` |
| `API_PORT` | `8123` | Puerto de la API en tu equipo |
| `KOKORO_PORT` | `8880` | Puerto del servicio de voz |
| `PUID` / `PGID` | `1000` | Dueño de los archivos creados (en Linux: `id -u`, `id -g`) |
| `GEMINI_API_KEY` | vacío | Clave para generar guías con IA |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Modelo de Gemini |
| `FFMPEG_API_URL` | `http://localhost:<API_PORT>` | **Solo panel**: usar una API en otro equipo |
| `TTS_URL` | `http://localhost:<KOKORO_PORT>` | **Solo panel**: usar otro servicio de voz |
| `TTS_VOZ` | `em_alex` | **Solo panel**: voz por defecto |
| `PROYECTOS_DIR` | `<DATA_DIR>/proyectos` | **Solo panel**: carpeta de proyectos que ve el panel |
| `DESCARGAS_DIR` | `~/Videos/ffmpeg-api` | **Solo panel**: dónde guarda los videos descargados |
| `API_CONTENEDOR` | vacío | **Solo comandos de shell**: nombre del contenedor de la API si no usas docker compose |

Prioridad en el panel: variables de entorno > `.env` > `panel.json` > valores por defecto. Las rutas relativas se cuentan desde la carpeta del proyecto.

### Interfaces del panel (`panel.json`)

```json
{"interfaces": {"terminal": {"habilitada": false}, "web": {"habilitada": true, "host": "0.0.0.0", "puerto": 8090}, "telegram": {"habilitada": false}}}
```

Existen `terminal` y `web` (la de Docker usa la web); `telegram` está prevista. Si habilitas una que no existe, el panel avisa y la omite.

### Usar el panel desde otro equipo

El panel solo habla con la API por HTTP. En tu laptop, con la API en un servidor:

```
FFMPEG_API_URL=http://192.168.0.25:8123
```

Limitación: la acción de **generar voces escribe directo en la carpeta de proyectos**, así que necesita acceso a ella (`PROYECTOS_DIR`, por ejemplo montada por red). El resto de acciones funcionan solo con la URL.

---

## 4. Qué usa para funcionar

| Componente | Para qué |
|---|---|
| **Python 3.12** + **FastAPI** + **Uvicorn** | La API |
| **FFmpeg / FFprobe 7.x** (dentro del contenedor) | Render, audio y análisis de archivos |
| **Docker + Docker Compose** | Empaquetado y arranque con un solo comando |
| **[Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) (CPU)** | Síntesis de voz (`ghcr.io/remsky/kokoro-fastapi-cpu`) |
| **Gemini API** (opcional) | Generar `guia.json` desde un guion |
| **Panel** (Python estándar, sin dependencias) | Menús de terminal |
| **n8n + Telegram** (opcional) | Control desde el celular con el workflow `Bot-Sin-excusas` |

### Archivos del repositorio

```
main.py            API (endpoints)
render.py          render del short
guia_ia.py         guía con Gemini
generar_guia.py    guía desde borrador local
comandos/          nuevo-short, render-short, guia-short + instalar.sh
panel/             panel de terminal (POO: config, cliente API, servicios, interfaces, voces)
Dockerfile         imagen de la API
docker-compose.yml API + Kokoro + preparación de carpetas
.env.example       plantilla de variables
REGLAS.md          reglas del proyecto
HISTORIAL.md       registro de todo lo que se hace
PLAN_VIDEO_LARGO.md  plan del video largo y de la integración con n8n
```

### Notas y seguridad

- **Nunca subas `.env`** (contiene la clave de Gemini); ya está en `.gitignore`, igual que `datos/`.
- Si ya tienes la API o Kokoro corriendo en el mismo equipo, los puertos 8123 y 8880 estarán ocupados: cambia `API_PORT` / `KOKORO_PORT` o detén los antiguos. Si ya tienes Kokoro, comenta el servicio `kokoro` en `docker-compose.yml` y pon su dirección en `TTS_URL`.
- La API no tiene autenticación: no la expongas a internet sin proteger.
- Al crear un proyecto, la respuesta de `/nuevo` incluye la ruta del servidor original (`/DATA/video-editor/...`); el panel muestra la ruta correcta de tu equipo.
- El workflow de n8n no está en el repositorio (contiene datos propios). Si lo usas desde Docker, la dirección de la API dentro de la red es `http://ffmpeg-api:8123`.

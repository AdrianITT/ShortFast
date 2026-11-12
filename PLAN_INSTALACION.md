# Plan: instalación rápida en otros equipos (con o sin CasaOS)

Última actualización: 2026-11-12.
Estado: **terminado** (2026-11-12): fases 1–5 hechas y probadas; este equipo ya usa el montaje nuevo.

Decisiones del usuario (sección 8): construir las imágenes en cada equipo, voces por defecto Supertonic + clonador, una sola app «ShortFast» en CasaOS, migrar este equipo al final.

- [x] Fase 1: compose con perfiles, panel en Docker, clave del clonador
- [x] Fase 2: `instalar.sh`, `actualizar.sh`, `desinstalar.sh`
- [x] Fase 3: modo CasaOS (`scripts/casaos.sh`)
- [x] Fase 4: `GUIA_INSTALACION.md` + README
- [x] Fase 5: migrar este equipo (2026-11-12)

## 0. Objetivo

En un equipo nuevo, con **pocos comandos**, tener funcionando todo lo que hoy existe:

| Pieza | Qué es | Puerto | Hoy en este equipo |
|---|---|---|---|
| API `ffmpeg-api` | Render de shorts y video largo | 8123 | Contenedor suelto con `--reload` y el código montado (modo desarrollo) |
| Panel web | Proyectos, voces, guía, render, biblioteca, «Mis voces» | 8090 | Proceso de Python en el equipo (`.venv`), fuera de Docker |
| Kokoro | Voz local | 8880 | App de CasaOS |
| Supertonic | Voz local (la favorita: M3) | 5200 | App de CasaOS (`supertonic-server/casaos.yml`) |
| Edge TTS | Voces de Microsoft (internet) | 5050 | Servicio del `docker-compose.yml` |
| Clonador | Voces propias (OpenVoice) | 5300 | App de CasaOS (`clonador-server/casaos.yml`) |

Meta: `git clone …` + `./instalar.sh` y listo. Con CasaOS, las piezas aparecen además en su panel.

## 1. Problemas del montaje actual que impiden copiarlo tal cual

1. **Tres formas distintas de arrancar** (compose, contenedor suelto, apps de CasaOS, proceso de Python): en otro equipo habría que repetir cada una a mano.
2. **El panel no está en Docker**: necesita Python, `.venv` y lanzarlo con `setsid`; no arranca solo al reiniciar el equipo.
3. **La API corre con `--reload`** y el código montado: gasta ~36 % de CPU sin hacer nada (ver `HISTORIAL.md`). La imagen del `Dockerfile` sí sirve para producción.
4. **Direcciones `localhost` fijas**: dentro de Docker, el panel y el clonador deben hablar con los demás por nombre de servicio (`http://supertonic:5000`), no por `localhost`.
5. **El clonador no envía la clave a Supertonic**: si se pone `TTS_API_KEY` en todas las voces, el clonador falla. Hay que reenviarla.
6. **Imágenes que solo existen en este equipo** (`supertonic-server:1.0`, `clonador-server:1.0`, `edge-tts-server`): en otro equipo hay que construirlas (Supertonic ~1.5 min, clonador ~7 min y 3 GB) o descargarlas de un registro (decisión 8.1).
7. **Seguridad del repositorio**: había una clave SSH privada (`041999`) sin ignorar en la raíz. **Ya añadida a `.gitignore`** (2026-11-12); conviene moverla a `~/.ssh/` (decisión del usuario). Restos sueltos en la raíz: `*.bak`, `prueba.mp3`.

## 2. Diseño: un solo `docker-compose.yml` con perfiles

Todo en **un compose**, con [perfiles](https://docs.docker.com/compose/how-tos/profiles/) para elegir qué voces instalar:

| Perfil | Servicios | Siempre |
|---|---|---|
| (base) | `preparar-datos`, `ffmpeg-api`, `panel` | sí |
| `supertonic` | `supertonic` | recomendado |
| `kokoro` | `kokoro` | opcional |
| `edge` | `edge-tts` | opcional (internet) |
| `clonador` | `clonador` (necesita `supertonic`) | opcional (3 GB de imagen, ~1 GB de RAM) |

Cambios:

1. **Panel en Docker**: `panel/Dockerfile` (python:3.12-slim + `panel/requirements.txt`), servicio `panel` con la carpeta de datos montada, `restart: unless-stopped`, y las direcciones por nombre de servicio en el entorno: `FFMPEG_API_URL=http://ffmpeg-api:8123`, `KOKORO_URL=http://kokoro:8880`, `SUPERTONIC_URL=http://supertonic:5000`, `EDGE_TTS_URL=http://edge-tts:5050`, `CLONADOR_URL=http://clonador:5000`. `PROYECTOS_DIR=/data/proyectos`. La config del panel ya lee todo esto (`panel/config.py`); no hay que tocar código.
2. **`supertonic` y `clonador` en el compose** (`build: ./supertonic-server`, `build: ./clonador-server`), con volumen `${DATA_DIR}/voces_propias:/datos` para el clonador. Los `casaos.yml` se mantienen para el modo CasaOS (sección 4).
3. **Clonador**: reenviar `Authorization: Bearer` a Supertonic cuando haya `API_KEY` (cambio de pocas líneas en `clonador-server/server.py`).
4. **API sin `--reload`**: el compose ya usa la imagen del `Dockerfile` (sin `--reload`). Revisar que el `Dockerfile` copie todo lo que la API importa hoy.
5. **Servicios de voz solo dentro de la red de Docker** por defecto: el panel los usa por la red interna, así no quedan abiertos en la red local. Publicar sus puertos solo si se pide (`PUBLICAR_VOCES=1`), por ejemplo para n8n.
6. Una sola clave `TTS_API_KEY` (la genera el instalador) para Edge, Supertonic y el clonador; `PANEL_CLAVE` opcional para proteger el panel.

## 3. Instalador `instalar.sh` (Linux, con o sin CasaOS)

Uso previsto:

```bash
git clone <repositorio> shortfast && cd shortfast
./instalar.sh                      # pregunta qué voces instalar
./instalar.sh --voces supertonic,clonador --datos /DATA/video-editor   # sin preguntas
```

Qué hace, en orden (y se puede repetir sin romper nada; repetirlo = actualizar):

1. **Comprueba**: Docker y `docker compose`, arquitectura `x86_64`, RAM y disco libres (avisa si el clonador no cabe), puertos ocupados (propone otros).
2. **`.env`**: si no existe, lo crea desde `.env.example`; genera `TTS_API_KEY` (y `PANEL_CLAVE` si se pide) con `openssl rand`; pide `GEMINI_API_KEY` (opcional, para la guía con IA) sin mostrarla. Nunca sobrescribe un `.env` existente.
3. **Carpeta de datos** (`DATA_DIR`, por defecto `./datos`; en CasaOS se propone `/DATA/video-editor`).
4. **Construye/descarga** las imágenes de los perfiles elegidos y arranca: `docker compose --profile … up -d --build`.
5. **Espera** a que cada servicio responda (`/health`) y muestra un resumen con las direcciones (`http://<ip>:8090` …) y qué falló si algo falló.
6. **Si detecta CasaOS** (`casaos-cli`): ofrece registrarlo para que aparezca en su panel (sección 4).
7. Opcional: `comandos/instalar.sh` (nuevo-short, render-short, guia-short en el PATH).

Otros scripts: `desinstalar.sh` (apaga y borra contenedores e imágenes; **los datos se quedan** salvo que se pida `--borrar-datos` con confirmación) y `actualizar.sh` (`git pull` + `instalar.sh` con lo ya elegido).

## 4. Modo CasaOS

CasaOS no construye imágenes, pero sí instala apps desde un compose con `x-casaos` (`casaos-cli app-management install -f …`, ya probado con Supertonic y el clonador).

Opción propuesta: el instalador construye las imágenes y registra **una sola app de CasaOS «ShortFast»** generada a partir del mismo compose (con `x-casaos`, icono, puerto del panel como web principal y `pull_policy: never`). Así se gestiona todo desde CasaOS (parar, arrancar, ver logs) y el compose del repo sigue siendo la única fuente.

Alternativa: una app por pieza (como ahora). Más botones en CasaOS, pero se puede parar cada voz por separado.

## 5. Guía (`GUIA_INSTALACION.md`)

Para alguien no técnico, en español, con capturas de comandos:

1. Requisitos (Linux x86_64, Docker, RAM/disco por voz; cómo instalar Docker en Ubuntu/Debian en dos comandos).
2. Instalación rápida (3 comandos) y qué esperar (tiempos de la primera vez).
3. Elegir voces (tabla: calidad, velocidad, RAM, internet sí/no).
4. Con CasaOS: qué cambia y dónde aparece.
5. Primer uso: abrir el panel, crear un proyecto, generar voces, renderizar.
6. Actualizar, desinstalar, copias de seguridad (qué carpeta guardar: datos + `.env`).
7. Llevar los proyectos de un equipo a otro.
8. Problemas frecuentes (puerto ocupado, poca RAM, Kokoro tarda en arrancar, Edge sin internet, el clonador tarda).

El `README.md` enlazará a la guía y se actualizará su sección 3 («Cómo se instala»).

## 6. Pruebas

1. **Instalación limpia en este equipo sin tocar lo que ya funciona**: en una carpeta temporal, con `COMPOSE_PROJECT_NAME` y puertos distintos, carpeta de datos temporal; cada perfil por separado y todos juntos; `instalar.sh` dos veces seguidas (idempotente); `desinstalar.sh` deja los datos.
2. **Modo CasaOS**: `--dry-run` de `casaos-cli` y una instalación real con nombre de prueba, luego desinstalada.
3. **Flujo completo** en la instalación de prueba: crear proyecto → voces con Supertonic → «Mis voces» → render de un short.
4. **Sin internet** (solo para comprobar que Supertonic/Kokoro/clonador funcionan y Edge falla con un mensaje claro).
5. No se puede probar en otro equipo real desde aquí: la guía incluirá una lista de comprobación para hacerlo.

## 7. Fases

1. Compose con perfiles + panel en Docker + reenvío de clave en el clonador. Pruebas 6.1 y 6.3.
2. `instalar.sh`, `desinstalar.sh`, `actualizar.sh`. Prueba 6.1.
3. Modo CasaOS. Prueba 6.2.
4. `GUIA_INSTALACION.md` + README.
5. (Opcional, decisión del usuario) Migrar **este** equipo al montaje nuevo, retirando el contenedor con `--reload`, el panel con `setsid` y las apps sueltas de CasaOS, sin perder datos ni voces.

Cada fase: entrada en `HISTORIAL.md`. Sin commits ni push salvo que el usuario lo pida.

## 8. Decisiones del usuario

1. **De dónde sale el código y las imágenes en otro equipo**: `git clone` del repositorio (¿es privado? entonces ese equipo necesita acceso) y **construir** las imágenes allí (lento la primera vez), **o** además publicar imágenes listas en un registro (p. ej. GHCR) para que solo se descarguen (rápido, pero es publicar fuera).
2. **Voces por defecto** del instalador (propuesta: Supertonic; las demás, a elegir).
3. **CasaOS**: una sola app «ShortFast» o una app por pieza.
4. **Migrar este equipo** al montaje nuevo (fase 5) o dejarlo como está.
5. **Clave SSH `041999`**: moverla a `~/.ssh/` (recomendado) o dejarla donde está (ya ignorada por git).

# Guía de instalación de ShortFast

ShortFast junta todo lo necesario para hacer shorts y videos largos: la **API de render** (ffmpeg), el **panel web** (proyectos, voces, guía, render, biblioteca de música, «Mis voces») y las **voces**. Todo corre en Docker, en tu equipo, y se instala con un script.

---

## 1. Requisitos

| | Mínimo | Recomendado |
|---|---|---|
| Sistema | Linux **x86_64** (Ubuntu, Debian, CasaOS…) | Ubuntu 24.04 / Debian 12 |
| RAM libre | 2 GB (solo Supertonic) | 4 GB (Supertonic + clonador) |
| Disco libre | 5 GB | 10 GB + tus proyectos |
| Programas | Docker con `docker compose` y `git` | — |

No hace falta GPU. Los equipos ARM (Raspberry Pi, Mac M1/M2…) **no están probados**.

### Instalar Docker (si no lo tienes)

En Ubuntu o Debian, dos comandos (luego **cierra la sesión y vuelve a entrar**):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

En CasaOS, Docker ya viene instalado.

---

## 2. Instalación rápida

```bash
git clone git@github.com:AdrianITT/ShortFast.git shortfast
cd shortfast
./instalar.sh
```

> El repositorio puede ser privado: el equipo necesita acceso a GitHub (tu clave SSH o un token). **Sin git**: copia la carpeta del proyecto por USB o zip **sin** el archivo `.env` ni la carpeta `datos/`, y ejecuta `./instalar.sh` dentro.

El instalador pregunta tres cosas (Enter = la respuesta recomendada):

1. **Voces** a instalar: por defecto `supertonic,clonador` (ver sección 3).
2. **Carpeta de datos**: dónde se guardan proyectos, videos y voces creadas. Por defecto `./datos`; con CasaOS, `/DATA/shortfast`.
3. **Clave de Gemini** (opcional): solo para generar guías con IA. Se escribe oculta.

Si hay CasaOS, pregunta además si registrarlo como app (sección 4).

Al terminar muestra las direcciones:

```
== Listo ==
  Panel:  http://192.168.1.50:8090
  API:    http://192.168.1.50:8123
```

Abre el **Panel** en el navegador de cualquier equipo de tu red.

**Cuánto tarda la primera vez:** construye las imágenes en el equipo, de 5 a 15 minutos según la conexión y el procesador (el clonador es lo más lento: ~7 min y ~3 GB). Las siguientes veces, menos de un minuto.

### Sin preguntas (para scripts o varios equipos)

```bash
./instalar.sh -y --voces supertonic,clonador --datos /ruta/a/mis/datos
```

Opciones: `--voces LISTA`, `--datos RUTA`, `--casaos` / `--sin-casaos`, `-y` (sin preguntas), `--ayuda`.

---

## 3. Elegir voces

| Voz | Calidad en español | Velocidad (en un i5 antiguo) | RAM | Internet | Notas |
|---|---|---|---|---|---|
| **supertonic** | Muy buena (44 kHz) | ≈ lo que dura el audio | ~0.5 GB | No | La recomendada; voces F1–F5 y M1–M5 (M3 por defecto) |
| **clonador** | Copia el timbre de una grabación | ~3× lo que dura el audio | ~1 GB | No | «Mis voces» en el panel; necesita supertonic |
| **kokoro** | Correcta | Rápida | ~2.2 GB | No | Más voces en inglés |
| **edge** | Muy natural | Rápida | ~50 MB | **Sí** | Voces de Microsoft (servicio no oficial: puede fallar) |

Para cambiar las voces más tarde: `./instalar.sh --voces supertonic,edge` (las que quites se paran; las voces creadas y tus datos se quedan).

---

## 4. Con CasaOS

Si el equipo tiene CasaOS, el instalador ofrece registrar **una sola app «ShortFast»**:

- Aparece en el panel de CasaOS con su botón para abrir el panel web.
- Desde CasaOS puedes pararla, arrancarla y ver sus registros.
- Los datos van por defecto a `/DATA/shortfast`.
- Actualizar y cambiar voces se hace igual, con los scripts (CasaOS no construye imágenes).

> Desinstalar la app desde el panel de CasaOS **no borra tus datos**; aun así, mejor usar `./desinstalar.sh`.

---

## 5. Primer uso

0. **Plantilla (una sola vez).** Los proyectos nuevos se crean copiando `plantilla/` de la carpeta de datos: tipografías (`fuentes/`, p. ej. Montserrat), logo (`imagenes/`), audios fijos (`voz/`) y `ejemplo_guia.json` (modelo para la IA). En un equipo nuevo está vacía: **cópiala desde el equipo donde ya trabajas** (`<datos>/plantilla/`) antes de crear proyectos.
1. Abre el **Panel** (`http://<ip-del-equipo>:8090`).
2. **Nuevo proyecto** (botón arriba en la portada).
3. **Archivos**: sube imágenes, música y, si las tienes, voces grabadas.
4. **Voces**: pega el guion (`archivo.mp3 | texto`, una línea por audio), elige **Servicio** y **Voz**, revisa y genera.
5. **Guía**: guarda el borrador y genera la guía (local o con IA).
6. **Render**: el video aparece al terminar, con vista previa.

Paso a paso de cada pantalla: **`GUIA_USO.md`**.

**Tu propia voz:** menú **Mis voces** → sube 20–60 s de grabación limpia (una sola persona, sin música), ponle nombre y elige la voz base (M = hombre, F = mujer). Tarda unos minutos. Después aparece en **Voces → Servicio «Mi voz»**. Solo tu voz o la de alguien que te dé permiso.

---

## 6. Actualizar, desinstalar y copias de seguridad

```bash
./actualizar.sh                   # trae el código nuevo (git pull) y reinstala con lo ya elegido
./desinstalar.sh                  # quita los contenedores; datos, imágenes y .env se quedan
./desinstalar.sh --imagenes       # además libera ~6 GB de imágenes
./desinstalar.sh --borrar-datos   # además BORRA la carpeta de datos (pide escribir BORRAR)
```

**Copia de seguridad:** guarda la **carpeta de datos** (proyectos, videos, `voces_propias/`) y el archivo **`.env`** (tus claves). Con eso puedes reinstalar en cualquier equipo.

### Llevar todo a otro equipo

1. En el equipo viejo: `./desinstalar.sh` (para que nada escriba mientras copias).
2. Copia la carpeta de datos y el `.env` al equipo nuevo (por ejemplo con `rsync -a` o un disco).
3. En el equipo nuevo: clona el proyecto, pon el `.env` en su carpeta, ajusta `DATA_DIR` a donde copiaste los datos y ejecuta `./instalar.sh -y`.

---

## 7. Comandos útiles

```bash
docker compose ps                     # estado de cada pieza
docker compose logs -f panel          # registros del panel (o ffmpeg-api, supertonic, clonador…)
docker compose restart panel          # reiniciar una pieza
./comandos/instalar.sh                # instala nuevo-short, render-short y guia-short en tu PATH
```

---

## 8. Problemas frecuentes

| Problema | Solución |
|---|---|
| `El puerto 8090 (PANEL_PORT) está ocupado` | Otro programa usa ese puerto. Cambia `PANEL_PORT` (o el que diga) en `.env` y repite `./instalar.sh -y`. |
| `No puedo usar Docker con tu usuario` | `sudo usermod -aG docker $USER`, cierra la sesión y vuelve a entrar. |
| Aviso de poca RAM | Instala menos voces (`--voces supertonic`) o cierra otros programas. |
| Un servicio «no responde» al terminar | Puede seguir arrancando (Kokoro y el clonador tardan). Espera un minuto y repite `./instalar.sh -y`. Si sigue: `docker compose logs <servicio>`. |
| Edge falla al generar | Necesita internet y depende de Microsoft; reintenta o usa Supertonic. |
| Crear una voz en «Mis voces» tarda | Es normal: 1–4 minutos (más la primera vez). No cierres la página. |
| La voz clonada no se parece | Usa una grabación más limpia y larga, o prueba otra voz base del mismo tipo (M/F). |

---

## 9. Lista de comprobación en un equipo nuevo

- [ ] `./instalar.sh` termina con «== Listo ==» y sin avisos de servicios
- [ ] La carpeta `plantilla/` de los datos tiene tus fuentes, logo y `ejemplo_guia.json`
- [ ] El panel abre desde otro equipo de la red
- [ ] Voces → Supertonic → M3 genera un audio
- [ ] Mis voces → crear una voz con una grabación y escuchar la muestra
- [ ] Render de un proyecto de prueba hasta el final
- [ ] (CasaOS) La app «ShortFast» aparece y se puede parar y arrancar

---

## 10. Para usarlo desde fuera del equipo

- **Panel:** se abre en toda la red local. Para protegerlo con contraseña, pon `PANEL_CLAVE=tu_contraseña` en `.env` y repite `./instalar.sh -y`; el navegador pedirá usuario (cualquiera) y esa contraseña.
- **Voces:** solo se publican en el propio equipo (`127.0.0.1`). Para usarlas desde otro equipo o desde n8n: `VOCES_IP=0.0.0.0` en `.env` (llevan la clave `TTS_API_KEY`).
- **Desde internet:** no abras puertos en el router; usa Tailscale o un túnel (por ejemplo Cloudflare).

# Plan: clonar una voz a partir de un audio

Última actualización: 2026-11-12.
Estado: **fases 1 y 2 terminadas** (2026-11-12). La fase 0 funcionó técnicamente; las muestras con voz sintética no convencieron, pero el usuario quiere probar con su propia voz. Pendiente: que el usuario cree su voz y decida si hace falta la fase 3.

- [x] Fase 1: `clonador-server/` + app de CasaOS `clonador-tts` (puerto 5300)
- [x] Fase 2: servicio «Mi voz» en el selector + página «Mis voces»

## 0. Idea y por qué así

Supertonic (ya instalado, app de CasaOS `supertonic-tts`, puerto 5200) no puede clonar: la pieza que crea un perfil de voz a partir de un audio no se publicó y su servicio Voice Builder cerró. Solo trae 10 voces fijas (F1–F5, M1–M5).

Solución: **dos pasos en cadena**, todo local y gratis.

1. **Supertonic** genera el texto con una voz base (la más parecida: mujer u hombre). Pone la pronunciación, el ritmo y la entonación.
2. **OpenVoice v2 (solo el conversor de timbre)** cambia el timbre de ese audio al de la grabación de referencia. Pone *cómo suena* la persona.

```
guion ─► Supertonic (voz base F/M) ─► wav ─► OpenVoice: timbre de la referencia ─► mp3
                                                   ▲
                       grabación de referencia ─► "huella" de voz (.pth, se calcula una vez)
```

Lo que se espera y lo que no:

- Se parece al **timbre** (grave/agudo, color de la voz). El **acento y la forma de hablar** siguen siendo los de Supertonic.
- Calidad: buena con referencias limpias; puede sonar algo metálica. Se decide escuchando en la fase 0.

Datos comprobados (lectura de los repositorios, sin instalar nada):

- OpenVoice: licencia **MIT** (uso comercial permitido), repositorio `myshell-ai/OpenVoice` sin cambios desde abril de 2025 → hay que fijar versiones.
- Modelo del conversor: `myshell-ai/OpenVoiceV2` → `converter/checkpoint.pth` (131 MB) + `config.json`. No hace falta MeloTTS (la voz base la pone Supertonic).
- `ToneColorConverter(..., enable_watermark=False)` evita la marca de agua (`wavmark`). `extract_se([wavs])` calcula la huella sin Whisper; los cortes de la referencia se hacen con ffmpeg (`silencedetect`, como ya hace `panel/cortador.py`).
- Dependencias: PyTorch CPU, librosa, soundfile, numpy, el paquete `openvoice` instalado sin sus dependencias (`--no-deps`) a un commit fijo.

## 1. Fase 0 — Prueba de viabilidad (sin instalar nada en el sistema)

Objetivo: saber si funciona en este equipo y si suena bien **antes** de construir.

1. Entorno temporal en el scratchpad: PyTorch CPU + OpenVoice (commit fijo) + checkpoint v2.
2. Con una grabación del usuario (20–30 s, voz sola, sin música ni ruido): calcular la huella.
3. Generar 2–3 frases con Supertonic (voz base F y M) y convertirlas al timbre de la referencia, probando `tau` 0.3 y 0.5.
4. Medir: tiempo por frase, RAM, y si PyTorch funciona en este CPU **sin AVX2** (riesgo principal).
5. Dejar las muestras en `/DATA/video-editor/pruebas_voz/clon/` para escuchar; borrar el entorno temporal.

**Criterio para seguir:** funciona en el CPU, tarda menos de ~3× la duración del audio, y al usuario le convence cómo suena. Si no: ver la sección 6.

Necesita del usuario: **la grabación de referencia**.

## 2. Fase 1 — Servicio `clonador` (app de CasaOS)

Contenedor propio, separado de Supertonic (PyTorch es pesado y así Supertonic sigue simple). Mismo patrón que `supertonic-server/`.

Carpeta `clonador-server/`:

- `server.py` (FastAPI):
  - `POST /v1/voces` (multipart: `nombre`, `audio`, `voz_base`): convierte la referencia a wav mono con ffmpeg, la corta en trozos por silencios, calcula la huella y guarda `/datos/voces/<nombre>/{referencia.wav, huella.pth, meta.json}`. Valida nombre (`[a-z0-9_-]`), duración (10 s – 3 min) y que no exista.
  - `GET /v1/voces` y `DELETE /v1/voces/{nombre}`.
  - `GET /v1/audio/voices` → `{"voices":[{"id":"<nombre>"}]}` (formato que ya lee el panel).
  - `POST /v1/audio/speech` (`input`, `voice`, `speed`): pide el audio a Supertonic con la `voz_base` de esa voz, convierte el timbre y devuelve mp3. La huella de cada voz base de Supertonic se calcula una vez y se guarda en caché.
  - `GET /health` abierto; `Bearer` opcional con `API_KEY`.
- `Dockerfile`: `python:3.12-slim` + ffmpeg + PyTorch **CPU** + versiones fijas; checkpoint descargado en la imagen (sin internet al usarlo).
- `casaos.yml`: app `clonador-tts`, puerto **5300**, volumen persistente `/DATA/AppData/clonador-tts:/datos` (las voces sobreviven a actualizaciones), `extra_hosts: host.docker.internal:host-gateway` y `SUPERTONIC_URL=http://host.docker.internal:5200`, límite de memoria 2–3 GB.

Pruebas: crear/listar/borrar voz, nombre inválido, audio demasiado corto, voz inexistente, Supertonic caído (error claro), tiempo y RAM.

## 3. Fase 2 — Panel web

1. **Servicio en el selector:** «Mi voz» en `Configuracion.servicios_tts` (`CLONADOR_URL` / `CLONADOR_PORT`, defecto 5300). Las voces clonadas aparecen en el selector como cualquier otra; generar, velocidad, «Revisar» y reintento funcionan sin cambios.
2. **Página «Mis voces»** (`/voces-propias`, enlace en la cabecera y en la pantalla de Voces):
   - Subir la grabación (zona de subida de `base.html`), nombre y voz base (Mujer/Hombre, o elegir F1–M5).
   - Consejos visibles: 20–60 s, una sola persona, sin música, micrófono cerca.
   - Lista de voces con ▶ para escuchar una muestra corta y botón **Borrar** (con confirmación).
3. Clase nueva `ClienteClonador` en `panel/clonador.py` (crear, listar, borrar, muestra), inyectada en `ServicioProyectos` como parámetro opcional (`clonador=None`). Los endpoints solo orquestan (regla 1.1).
4. **Terminal sin cambios** (regla 1.0.1): la voz clonada ya se puede usar ahí si `TTS_URL` apunta al clonador; crear voces desde la terminal queda para después si hace falta.

## 4. Fase 3 — Mejoras (solo si hacen falta al escuchar)

- Varias grabaciones por voz (se promedian las huellas): más parecido.
- Ajuste `tau` por voz (más parecido ↔ más natural).
- Limpieza de la referencia (quitar ruido de fondo con ffmpeg `afftdn`, normalizar volumen).
- Elegir automáticamente la voz base más parecida (comparando huellas con F1–M5).

## 5. Recursos y riesgos

| Riesgo | Qué se hace |
|---|---|
| PyTorch no funciona o va muy lento sin AVX2 | Se detecta en la fase 0 antes de construir nada |
| OpenVoice sin mantenimiento y con dependencias antiguas | Versiones fijas, instalar sin sus dependencias, solo el conversor |
| RAM: Kokoro 2.2 GB + Supertonic 0.5 GB + clonador ~1 GB, con ~3 GB libres | Límite de memoria en CasaOS; si falta, parar Kokoro cuando no se use |
| Suena metálico o poco parecido | Probar `tau`, otra voz base y una referencia más limpia en la fase 0 |
| Uso indebido | Solo con la voz propia o con permiso de la persona (aviso en la página) |

Coste: **gratis** (MIT + OpenRAIL-M, todo local). Disco: imagen ~2–3 GB.

## 6. Si la fase 0 no convence

- **XTTS-v2**: clona directamente con español natural, pero en este CPU es lento y su licencia no permite uso comercial.
- **Entrenar una voz propia** con GPU alquilada por horas (requiere 1–2 h de grabación).
- **Con GPU NVIDIA**: F5-TTS, Chatterbox o VoiceStudio.
- **Nube de pago**: ElevenLabs.

## 7. Orden de trabajo

1. El usuario entrega la grabación de referencia.
2. Fase 0 → muestras → **decisión del usuario**.
3. Fase 1 (servicio + app de CasaOS) con pruebas.
4. Fase 2 (selector + «Mis voces») con pruebas en el panel real.
5. Fase 3 solo si hace falta.

Cada paso: pruebas en carpetas temporales y una entrada en `HISTORIAL.md`.

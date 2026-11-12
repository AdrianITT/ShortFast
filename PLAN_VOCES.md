# Plan: calidad de voz y elección de voz (Kokoro)

Última actualización: 2026-11-11.
Estado: **solo planeación**, nada implementado todavía.

## 0. Punto de partida

Dónde se crea la voz hoy:

- **Web:** `GET /proyecto/{nombre}/voces` (`panel/interfaces/web.py`, ~línea 159). Plantillas `voces.html`, `voces_confirmar.html`, `voces_resultado.html`. El usuario pega el guion; no hay ningún selector de voz.
- **Terminal:** acción «Generar voces (Kokoro)» de `InterfazTerminal`.
- **Lógica (compartida):** `panel/voces.py` (`GuionVoces`, `AnalizadorBash`, `AnalizadorLineas`, `GeneradorVoces`) y `panel/tts.py` (`ClienteKokoro.sintetizar`).

Por qué solo sale una voz:

- La voz sale de `TTS_VOZ` (`panel/config.py:52`, defecto `em_alex`) o de una línea `voz: nombre` / `VOZ=nombre` escrita a mano en el guion.
- En la web la plantilla `voces.html` solo menciona esa sintaxis; no hay forma visible de elegir.
- `ClienteKokoro.sintetizar` envía `voice` y `response_format`, pero **no envía `speed`**, así que la velocidad siempre es la de por defecto.

Lo que comprobé contra el Kokoro que tienes levantado (`localhost:8880`, solo lecturas y pruebas en la carpeta temporal del scratchpad):

- `GET /v1/audio/voices` devuelve **54 voces** (en, es, fr, it, ja, pt, hi, zh…). Las de español son `ef_dora`, `em_alex`, `em_santa`, `pf_dora`, `pm_alex`, `pm_santa`.
- `POST /v1/audio/speech` con `"speed": 0.9` responde 200 y genera mp3 válido. `em_alex` y `ef_dora` responden bien con texto en español.

## 1. Elección de voz

Objetivo: elegir la voz desde la web y desde la terminal, sin tener que escribir `voz:` a mano.

1. **Listar voces desde Kokoro, no a mano.** `ClienteKokoro.voces()` lee `GET /v1/audio/voices` y devuelve los ids. Se filtran por idioma con el prefijo del id (`e` = español, `f` = francés…); el usuario ve las de español primero. Si Kokoro no responde, se usa una lista fija de respaldo con las 6 voces de español.
2. **Web:** en `voces.html`, un `<select>` con las voces (por defecto `TTS_VOZ`). Se envía junto al guion en `POST .../voces/preparar` y `.../voces/generar`, igual que el guion ya viaja oculto entre pantallas. Si el guion trae `voz:` o `VOZ=`, esa línea **gana** sobre el select (así no se rompe lo que ya funciona), y `voces_confirmar.html` muestra la voz que de verdad se usará.
3. **Terminal:** al generar voces, pregunta la voz con la lista numerada (Enter = la de defecto). Mismo patrón que la acción actual; `InterfazTerminal` sigue funcionando igual si no se elige nada (regla 1.0.1 de `REGLAS.md`).
4. **Cambio de voz por tramo (opcional, fase posterior):** permitir `voz:` por línea (`archivo.mp3 | voz=em_santa | texto`). Útil para diálogos, pero no hace falta para el primer paso.

Archivos que se tocan: `panel/tts.py` (+`voces()`), `panel/voces.py` (ninguna lógica nueva: `GuionVoces` ya tiene `voz`), `panel/interfaces/web.py` (leer el select y pasarlo), `voces.html` / `voces_confirmar.html`, y la parte de voz de `InterfazTerminal`.

Criterio de aceptación: elegir `em_santa` en la web genera mp3 con esa voz (comprobado escuchando una muestra y mirando la duración); con el guion `voz:` escrito a mano, el guion sigue ganando.

## 2. Calidad de voz

Por orden de coste/beneficio (el primero es el más barato):

1. **Velocidad (`speed`).** Hoy no se envía. Añadir un parámetro `velocidad` a `ClienteKokoro.sintetizar` (defecto `1.0`) y exponerlo en `panel.json`/`.env` (`TTS_VELOCIDAD`). Probado: `0.9` funciona. Recomendación inicial: `0.92`–`0.95` para voz de tutorial/short, a validar con oído.
2. **Voz por defecto mejor.** Comparar `em_alex`, `em_santa`, `ef_dora` con el mismo texto (3 muestras, 20 s cada una) y elegir una. Es una decisión de oído del usuario; yo preparo las muestras.
3. **Texto antes de sintetizar (normalización).** Kokoro lee mal números, años, siglas y símbolos (`%`, `€`, `2026`, `3x`, `IA`). Añadir una función pura `normalizar_texto(texto)` en `panel/voces.py` (o una clase `NormalizadorTexto` para mantener POO) que escriba números y símbolos en palabras y separe frases largas. Es la mejora de calidad con más impacto percibido.
4. **Partir textos largos por frases.** Puede que Kokoro tenga un límite de longitud por petición que no he comprobado; un tramo largo podría perder prosodia o cortarse. Dividir en frases (`. ! ?`), sintetizar cada una y unir los bytes mp3 con ffmpeg (`concat`), o concatenar en `render`. Solo si la normalización no basta; se mide primero con los tramos reales de `proyectos_largos/largo_prueba_guion`.
5. **Formato de salida.** Hoy se pide `mp3` (Kokoro por defecto). Probar `wav` para el paso intermedio sin pérdida; el render final ya re-codifica. Coste: más disco (~10×). Solo si el mp3 se nota en la mezcla.
6. **Ajuste de volumen (loudness).** Normalizar cada voz a un nivel fijo (ej. -16 LUFS) con ffmpeg `loudnorm`, en la generación o en el render del largo (`largo/medios.py`). Evita que una voz suene más baja que la música. Revisar primero si el render ya normaliza audio: si ya lo hace, no se añade nada.

Qué no se toca: el formato del guion, `AnalizadorBash`/`AnalizadorLineas` y el flujo de reintento.

## 3. Orden de trabajo propuesto

1. Muestras de voz (3 voces × mismo texto) → el usuario elige la voz por defecto. *(Sin cambios de código.)*
2. Parámetro `speed` en `ClienteKokoro` + `TTS_VELOCIDAD`. Probar 2 velocidades con oído.
3. Lista de voces desde Kokoro + select en la web + opción en la terminal.
4. Normalización de texto (números, siglas, símbolos) con pruebas de entrada → salida.
5. Solo si hace falta según el oído: partir frases largas; formato wav; loudnorm.

Cada paso: prueba contra Kokoro real en carpeta temporal (como en las fases anteriores), y entrada en `HISTORIAL.md`.

## 4. Riesgos y decisiones abiertas

- **Decisión del usuario:** qué voz es la de defecto (paso 1) y qué velocidad le suena bien (paso 2).
- La normalización puede cambiar el texto que se oye; hay que revisar tramos con cifras antes de aceptarla.
- El select de voz y la línea `voz:` pueden contradecirse; la regla propuesta es que la línea del guion gana, y se muestra en la confirmación.
- No se ha probado todavía la calidad real de las voces por oído; las notas de Kokoro (`overall_grade`) son orientativas (`em_alex` no aparece con nota, `em_santa` tampoco).
- Kokoro en CPU tarda: 917 s para 54 tramos (HISTORIAL 2026-10-02). Cualquier cambio de calidad que añada pasos (partir frases, wav) alarga ese tiempo; hay que medirlo.

## 5. Investigación: cómo subir la calidad con estos recursos (2026-11-11)

Equipo: 4 vCPU, 7.7 GB RAM (~3 GB libres con todo lo demás levantado), **sin GPU**.

Hallazgos clave:

- **Acento de las voces españolas de Kokoro:** `ef_dora`, `em_alex`, `em_santa` están entrenadas con acento latinoamericano, no castellano. Según un issue de GitHub, cambiar el locale de eSpeak (es_ES / es_MX) y mezclar voces no lo arregla. Si tu público es de España, esto pesa más que cualquier ajuste.
- **Kokoro, límites oficiales:** rinde peor con frases muy cortas y se «atropella» en textos largos (más de ~400 tokens). Mitigación oficial: trocear el texto y bajar la velocidad. Así confirmo que el troceo de frases del punto 2 sí tiene base.
- **Piper:** muy ligero en CPU (muy por encima del tiempo real), voces `es_ES` (sharvard, davefx) y `es_MX` (ald, claude). Calidad percibida por debajo de Kokoro según las fuentes (MOS comunitario ~3.5 frente a ~4.2). Sirve si la velocidad importa más que la calidad; no es una mejora de calidad.
- **Supertonic 3:** modelo de ~99M parámetros en ONNX, pensado para CPU, 31 idiomas. Un usuario de Reddit afirma que suena mejor que Kokoro en español (anecdótico). El soporte de español **no lo he podido confirmar** en las fuentes: hay que verlo en la ficha de Hugging Face. Es el candidato más prometedor para probar aquí.
- **MeloTTS:** MIT, incluye español, unas 6× tiempo real en CPU. Calidad en español sin verificar; prioridad baja.
- **Chatterbox Multilingual / XTTS v2 / F5-TTS:** mejor clonación, pero necesitan GPU (~3.5 GB VRAM o más) o son impracticables en CPU. No encajan con tus recursos. F5-TTS además tiene licencia no comercial.
- **Edge-TTS (voces neuronales de Microsoft, `es-ES-AlvaroNeural`, `ElviraNeural`…):** probablemente la mejor calidad en español de las gratuitas y cero coste de CPU. **Ya tienes un contenedor `edge-tts-api` levantado en el puerto 5050** (API compatible con OpenAI). Pega dos problemas: pide una API key (no la he leído) y el servicio usa el endpoint no oficial de Edge, sin garantía de estabilidad ni clara licencia para uso comercial. Para uso personal puede servir; para venta, el camino limpio es Azure Speech (de pago, con términos explícitos).
- **Ajustar Kokoro a castellano:** requiere ~20 h de audio y entrenamiento con GPU. Fuera de alcance.

Recomendación, de más barato a más caro:

1. **Sin cambiar de motor (coste cero de RAM):** velocidad 0.9–0.95, troceo por frases (<400 tokens, evitar frases de 1–2 palabras) y post-proceso con ffmpeg (filtro paso alto para quitar graves sucios, `loudnorm`, compresión suave). Es lo primero que haría.
2. **Probar Supertonic 3** en local con las mismas 3 frases de prueba: si el español es bueno y va a tiempo real en tu CPU, es la mejora de calidad más realista sin GPU.
3. **Edge-TTS** si el uso es personal: la voz más natural de las opciones gratuitas, y ya la tienes montada. Decide tú si aceptas el endpoint no oficial.
4. Piper solo si necesitas velocidad extrema; MeloTTS solo si Supertonic no convence.

Cómo medir sin fiarse de las fuentes: 3 frases (una con cifras, una larga, una con preguntas) × cada motor; anotar tiempo de generación y escuchar. Solo cambia el motor si gana al oído.

Preguntas abiertas para ti: ¿tu audiencia es de España o de Latinoamérica? ¿El uso es personal o para vender/monetizar? La respuesta decide si Edge-TTS entra en la lista o no.

## 6. Decisión sobre Supertonic y estado (2026-11-11)

Contexto aclarado por el usuario: shorts de YouTube para **Latinoamérica**, y posiblemente videos en **inglés** más adelante.

Supertonic 3 vs Kokoro, lo que se pudo verificar:

- **Calidad:** no hay evidencia de que Supertonic suene mejor. Un [benchmark de terceros](https://github.com/gauravvij/kokoro-tts-vs-supertonic-3-tts) (UTMOS, en inglés, nota predicha por modelo, no por personas) da Kokoro ≈ 4.45 y Supertonic 3 ≈ 4.32–4.38. El WER oficial de Supertonic 3 en español es 1.13 (inglés 2.06), pero Kokoro no aparece en esa tabla. La afirmación de Reddit de «mejor en español» era anecdótica.
- **Velocidad:** Supertonic gana claro en CPU (ficha antigua: ~900–1260 caracteres/s frente a ~100–117 de Kokoro en un M4 Pro).
- **Riesgos:** el repositorio de Supertonic está **archivado** (sin más desarrollo ni soporte); el español no distingue variante latinoamericana; no hay parámetro de velocidad documentado.
- **Decisión:** se queda **Kokoro**. Su acento español ya es latinoamericano (coincide con el público) y cubre inglés. Supertonic solo se prueba si la velocidad llega a ser un problema, con una escucha ciega de 3 frases latinoamericanas.

Implementado (paso 2 y 3 del orden de trabajo):

- [x] `ClienteKokoro`: parámetro `velocidad` (se envía como `speed`), `voces()` (lee `GET /v1/audio/voices`, con lista de respaldo si Kokoro no responde) y `agrupar()` (Español / Inglés / Otros idiomas).
- [x] Configuración: `TTS_VELOCIDAD` (env/`.env`) o `tts_velocidad` en `panel.json`; por defecto `1.0`.
- [x] Web: selector de voz agrupado en `voces.html`; viaja por `preparar` → `generar`; la voz escrita en el guion (`voz:` / `VOZ=`) manda sobre el selector.
- [x] Terminal: si el guion no trae voz, ofrece lista numerada (número o nombre; Enter = la de por defecto). Sin elegir, el comportamiento es el de siempre (regla 1.0.1).

Pendiente (no implementado): normalización de texto, troceo por frases, ajuste de volumen con ffmpeg, voz por tramo, muestras para elegir la voz y velocidad por defecto. Se decide tras escuchar con la velocidad 0.9–0.95 ya disponible.

### Actualización (2026-11-11): velocidad desde la interfaz

- [x] Velocidad elegible por generación (rango 0.5–1.5, valida el servidor): campo en el paso 1 y en la confirmación de la web, y pregunta en la terminal (Enter = la de `TTS_VELOCIDAD`, por defecto 1.0). El reintento de tramos fallidos conserva la velocidad usada. Comprobado con Kokoro real: el mismo texto dura 4.25 s a 0.8 y 3.05 s a 1.2.
- [x] La confirmación permite cambiar la voz aunque el guion traiga `VOZ=`; la del guion queda preseleccionada.


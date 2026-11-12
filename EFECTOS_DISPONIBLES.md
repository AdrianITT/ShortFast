# Efectos disponibles (render.py y largo/)

Referencia de todo lo que acepta `guia.json`, para generar guías (a mano o con otro agente/IA).
Aplica igual a shorts 9:16 (`render.py`) y a video largo 16:9 (`largo/`), salvo donde se indique.

Nombres mal escritos: el video largo rechaza la guía y dice qué valor está mal; los shorts renderizan igual pero muestran un aviso `⚠️` al inicio con lo que se usará en su lugar (efecto → `ninguno`, transición → `fade`/`dissolve`, animación → sin animación).

## 1. Efecto de cámara sobre una imagen (`efecto`)

Va en cada imagen (shorts: `escenas[].efecto`; largo: `medios[].efecto`, solo para `tipo: "imagen"`).
Todos con movimiento suave (ease-in-out): arrancan y frenan sin golpe, no a velocidad constante.

| Nombre | Qué hace |
|---|---|
| `ninguno` | Imagen fija, sin movimiento de cámara |
| `zoom_in_lento` | Acercamiento suave y lento (8% a lo largo de la escena) |
| `zoom_in` | Acercamiento más notorio (15%) |
| `zoom_out` | Alejamiento notorio (empieza 15% más cerca y se aleja) |
| `zoom_out_lento` | Alejamiento suave (8%) |
| `paneo_der` | Cámara fija en zoom (15%), se desplaza de izquierda a derecha |
| `paneo_izq` | Igual que `paneo_der` pero de derecha a izquierda |
| `paneo_arriba` | Zoom fijo (15%), desplazamiento de abajo hacia arriba |
| `paneo_abajo` | Zoom fijo (15%), desplazamiento de arriba hacia abajo |
| `paneo_rapido` | Paneo horizontal (der) con más zoom (25%), más dinámico |
| `deriva` | Sin zoom ni paneo: ligera rotación de cámara (±0.86°), efecto "cámara en mano" sutil |

## 2. Transición entre escenas (`transicion_salida.tipo`)

Cómo termina una escena y empieza la siguiente. Se define en la escena que **sale** (`transicion_salida: {"tipo": ..., "duracion": segundos}`).

| Nombre | Qué hace |
|---|---|
| `corte` | Corte duro, sin transición (duración fija de 1 frame) |
| `fade` | Disolución a través de un fundido (crossfade) |
| `fadeblack` | Fundido a negro y luego aparece la siguiente |
| `fadewhite` | Fundido a blanco (efecto "flash") y luego aparece la siguiente |
| `dissolve` | Disolución simple entre ambas imágenes/clips |
| `wipeleft`, `wiperight`, `wipeup`, `wipedown` | Cortinilla: la siguiente barre a la anterior con un borde recto |
| `slideleft`, `slideright`, `slideup`, `slidedown` | Deslizamiento: la anterior sale empujada y entra la siguiente |
| `smoothleft`, `smoothright`, `smoothup`, `smoothdown` | Como la cortinilla pero con borde suave |
| `circleopen`, `circleclose` | Círculo que se abre (o cierra) desde el centro; borde muy difuminado |
| `radial` | Barrido circular tipo manecilla de reloj |
| `zoomin` | La anterior se acerca y se funde con la siguiente |
| `hblur` | Fundido con desenfoque horizontal |
| `pixelize` | Se pixela, cambia de imagen y se aclara |
| `fadegrays` | Pasa a gris en la mitad y vuelve con color la siguiente |
| `distance` | Fundido por diferencia de color (efecto "fantasma") |

Las de la segunda parte (desde `wipeleft`) son de 2026-11-11. **Shorts:** solo se respetan si se escriben a mano en `guia.json`; la guía generada por IA (`guia_ia.py`, que no se modifica) las cambia a `corte`.

`duracion` (segundos, por defecto 0.5): cuánto dura la transición.

## 3. Animación del texto (`textos[].animacion`)

| Nombre | Qué hace |
|---|---|
| `ninguna` | El texto aparece y desaparece de golpe, sin animación |
| `fade` | El texto se desvanece (fade in) en 0.5 s al aparecer |
| `golpe` | El texto entra 18% más grande y se asienta a su tamaño normal en 0.2 s (sensación de "impacto") |
| `palabra_por_palabra` | Las palabras van apareciendo una a una, repartidas según la duración de la voz (estilo karaoke/subtítulo dinámico) |

## 4. Posición del texto (`textos[].posicion`)

| Nombre | Dónde va |
|---|---|
| `centro` | Centrado vertical y horizontalmente (por defecto) |
| `arriba` | Cerca del borde superior |
| `abajo` | Cerca del borde inferior |
| `abajo_firma` | Más abajo todavía, pensado para un crédito/firma pequeña |
| `izquierda` | Mitad izquierda de la pantalla, ancho de línea más angosto |
| `derecha` | Mitad derecha de la pantalla, ancho de línea más angosto |

Otros campos de texto: `contenido` (el texto), `fuente` (clave en `fuentes`), `tamano` (px, sobre 1080 de alto), `color` (nombre o `#hex`), `inicio`/`duracion` o `inicio_desde_final`/`fin_desde_final` (segundos).

## 5. Encuadre de imagen — solo video largo (`medios[].encuadre`)

Qué hacer cuando la imagen no tiene las proporciones del cuadro 16:9.

| Nombre | Qué hace |
|---|---|
| `auto` (por defecto) | Decide solo: imágenes verticales/altas usan `ajustar`, las demás `cubrir` |
| `cubrir` | Llena todo el cuadro, recortando lo que sobre |
| `ajustar` | Muestra la imagen completa (sin recortar) centrada sobre un fondo borroso de la misma imagen |

En shorts, `ajustar` también existe como caso especial para logos (imagen centrada sobre fondo negro).

## 6. Ajuste de clip de video — solo video largo (`medios[].ajuste`)

Qué hacer cuando un clip de video no dura exactamente el tiempo asignado.

| Nombre | Qué hace |
|---|---|
| `recortar` (por defecto) | Si el clip es más corto de lo necesario, se congela el último frame (y el render avisa) |
| `congelar` | El último frame se mantiene fijo hasta completar el tiempo asignado |
| `bucle` | El clip se repite en bucle hasta cubrir el tiempo asignado |

## 7. Filtros de estilo globales (raíz de `guia.json`)

Afectan a todo el video. Salvo `lufs`, son opt-in (si no se ponen, no se aplican); los de imagen van antes del texto en cada escena.

| Campo | Valores | Qué hace |
|---|---|---|
| `lufs` | número, por defecto `-14`; `null`/`0` para desactivar | Normaliza el volumen final del video a ese nivel LUFS. Es el único de esta tabla que está activo aunque no se ponga (shorts y, desde 2026-11-11, también video largo) |
| `vineta` | `true`/`false` (por defecto `false`) | Oscurece ligeramente las esquinas del cuadro (viñeta de cámara) |
| `grano` | `true`/`false` (por defecto `false`) | Añade grano fino de película sobre la imagen |
| `lut` | ruta de un archivo `.cube` dentro del proyecto (p. ej. `"luts/calido.cube"`) | Aplica ese tono de color (LUT 3D) a todas las escenas, para que imágenes de distinto origen se vean del mismo "look". Se aplica antes de viñeta y grano (2026-11-11) |

## 8. Otros campos de escena (contexto, no son "efectos")

- `musica_vol` (0–1, por defecto 0.15): volumen de la música de fondo durante esa escena, relativo a `musica.volumen` general.
- `duracion` (segundos, opcional): fuerza la duración de la escena; si no se indica, se calcula a partir de la voz.
- `voz`: archivo de audio de la voz de esa escena (o `null` si no tiene).

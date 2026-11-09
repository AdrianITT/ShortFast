# Formato del video largo 16:9 (Fase 0)

Estado: **borrador, pendiente de confirmar**. Fecha: 2026-10-02.
Base: el formato de los shorts (`guia.json` de `render.py`), adaptado a 1920x1080 y a clips de video.

## 1. Estructura de carpetas

```
<DATA_DIR>/proyectos_largos/<nombre>/
  guion.md          texto plano del guion
  guia.json         generado (Fase 2) o escrito a mano
  voz/              un mp3 por tramo
  imagenes/         material horizontal
  clips/            clips de video
  musica/
  fuentes/          copiadas de la plantilla
<DATA_DIR>/salida_largos/<nombre>.mp4     (+ logs/ y tmp_<nombre>/)
```

Carpetas separadas de los shorts (`proyectos/`, `salida/`) para que ninguno afecte al otro.

## 2. Reglas de nombres

Cada tramo del guion tiene un **id de 3 dígitos** (`001`…`999`). El id empareja todo el material del tramo:

| Material | Nombre | Ejemplo |
|---|---|---|
| Voz | `NNN.mp3` (se permite `NNN_texto.mp3`) | `012.mp3`, `012_el_miedo.mp3` |
| Imagen | `NNN_<letra>.jpg\|png` | `012_a.jpg`, `012_b.png` |
| Clip | `NNN_<letra>.mp4` | `012_c.mp4` |

- La **letra** (`a`, `b`, `c`…) es el orden en que aparece el material dentro del tramo.
- Imágenes y clips pueden mezclarse en un mismo tramo (`012_a.jpg`, `012_b.mp4`).
- Un tramo sin material usa fondo negro con texto, como en los shorts.
- Con 3 dígitos caben 999 tramos; un video de 20 min con tramos de 30-60 s necesita unos 20-40.

## 3. Esquema de `guia.json` 16:9

Igual al de los shorts, salvo lo marcado como **nuevo**.

```json
{
  "proyecto": "largo_01_tema",
  "formato": {"ancho": 1920, "alto": 1080, "fps": 30},
  "fuentes": {"bold": "fuentes/montserrat/Montserrat-Bold.ttf"},
  "voz_retraso": 0.3,
  "pausa_entre_escenas": 0.4,
  "duracion_max": 1260,
  "musica": {"archivo": "musica/fondo.mp3", "volumen": 0.6, "fade_out": 3},
  "escenas": [
    {
      "id": "001",
      "voz": "voz/001.mp3",
      "medios": [
        {"tipo": "imagen", "archivo": "imagenes/001_a.jpg", "efecto": "zoom_in_lento", "duracion": 6},
        {"tipo": "clip", "archivo": "clips/001_b.mp4", "ajuste": "recortar", "inicio": 2.0}
      ],
      "textos": [
        {"contenido": "TÍTULO", "fuente": "bold", "tamano": 90, "color": "white",
         "posicion": "centro", "animacion": "fade", "inicio": 0}
      ],
      "musica_vol": 0.15,
      "transicion_salida": {"tipo": "fade", "duracion": 0.5}
    }
  ]
}
```

### Qué cambia respecto a los shorts

| Campo | Shorts | Largo | Nota |
|---|---|---|---|
| `formato` | 1080x1920 (fijo en el código) | 1920x1080, **parámetro** | **nuevo**: el render lo lee de la guía |
| `imagenes` (lista) | rutas de imagen | `medios` (lista de objetos) | **nuevo**: mezcla imagen y clip |
| `medios[].tipo` | — | `imagen` o `clip` | **nuevo** |
| `medios[].duracion` | `cortes_voz` (proporciones de la voz) | segundos, opcional | **nuevo**: lo que no se indique se reparte en partes iguales entre los medios sin duración |
| `medios[].efecto` | por escena | por medio (solo imágenes) | zoom_in_lento, zoom_in, zoom_out, paneo_der, paneo_rapido, ninguno |
| `medios[].ajuste` | — | `recortar` (por defecto), `congelar`, `bucle` | **nuevo**: qué hacer si el clip dura distinto al tiempo asignado |
| `medios[].inicio` | — | segundo del clip donde empieza | **nuevo** |
| `medios[].encuadre` | `encuadre` por escena | `auto` (por defecto), `cubrir`, `ajustar` (solo imágenes) | **nuevo**: `cubrir` llena el cuadro recortando; `ajustar` muestra la imagen completa sobre un fondo borroso. En `auto`, las imágenes verticales usan `ajustar` y las horizontales `cubrir` |
| `escenas[].id` | texto libre | id de 3 dígitos | **nuevo**: empareja el material |
| `textos`, `musica`, `transicion_salida` | igual | igual | `tamano` en píxeles sobre 1080 de alto |

Reglas de los clips (implementadas en la Fase 1):
- Siempre se escalan para cubrir el cuadro 16:9 (recortando si no son 16:9) y se descarta su audio.
- `recortar`: si el clip no alcanza el tiempo asignado, se congela el último frame y el render avisa.
- `bucle`: el clip se repite hasta cubrir el tiempo asignado.

Decisiones tomadas en el borrador (a confirmar):
- **Los clips van sin su audio propio**: manda la voz del tramo y la música.
- Duración de la escena: `voz_retraso` + duración de la voz + `pausa_entre_escenas`, igual que en los shorts.
- Posiciones de texto: las mismas (`arriba`, `centro`, `abajo`, `abajo_firma`, `izquierda`, `derecha`), recalculadas para 16:9 en la Fase 1.

## 4. Cómo se renderiza (Fase 1)

```bash
docker exec ffmpeg-api python /app/render_largo.py <proyecto> [--bloque 12] [--conservar-tmp] [--reanudar]
```

Lee `proyectos_largos/<proyecto>/guia.json` y escribe `salida_largos/<proyecto>.mp4`. Cada medio se renderiza a su propio segmento, las escenas se unen por bloques (`--bloque`, 12 por defecto) y los bloques entre sí; al terminar se borran los temporales (salvo `--conservar-tmp`). Si un render falla después de unir el video, `--reanudar` salta directo al audio. Un bloque más pequeño gasta menos memoria (~1 GB con `--bloque 5`, ~1.9 GB con 12). El código está en el paquete `largo/`.

## 5. Ejemplo de 1 minuto

`ejemplos/guia_largo_ejemplo.json`: 3 escenas (~20 s cada una) con nombres de archivos ficticios. Sirve para validar el formato; se reemplazará por uno con material real.

## 6. Pendiente para cerrar la Fase 0

- [ ] El usuario confirma estructura, reglas de nombres y esquema (o pide cambios).
- [ ] Guion real de ejemplo y subconjunto de su material (voces, imágenes, clips).
- [ ] `guia.json` de ejemplo con material real, de 1 minuto, validado.

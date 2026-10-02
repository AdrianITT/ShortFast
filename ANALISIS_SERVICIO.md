# Análisis: FFmpeg API - Microservicio de Automatización de Videos Cortos

## 📋 Resumen Ejecutivo

**FFmpeg API** es un microservicio especializado en la **automatización completa de la creación de YouTube Shorts y videos cortos de formato vertical**. Proporciona una API REST que orquesta todo el pipeline: desde la gestión de proyectos hasta el renderizado final de videos de alta calidad, integrando IA (Gemini) para la generación inteligente de guías de composición.

**Stack:** Python 3.12 + FastAPI + FFmpeg/FFprobe + Gemini API

---

## 🎯 Función Principal

El microservicio automatiza el flujo de creación de videos cortos mediante:

1. **Generación automática de guías (guide.json)** usando Gemini: Convierte una descripción textual de un video en un archivo JSON estructurado con metadatos de composición (escenas, transiciones, efectos, duración, etc.)

2. **Renderizado no-bloqueante**: Procesa proyectos de forma asincrónica, permitiendo múltiples renders simultáneos sin bloquear la API

3. **Gestión de proyectos**: Organiza archivos (imágenes, voces, música) en una estructura estandarizada con validación automática

4. **Composición avanzada de video**: Combina imágenes, voces sincronizadas, música de fondo, efectos de zoom/paneo y texto dinámico

---

## 🏗️ Arquitectura del Servicio

### **Contenedor Docker**
```
ffmpeg-api (Python 3.12)
├── ffmpeg (cli) - Procesamiento de video
├── ffprobe (cli) - Análisis de metadatos
├── FastAPI server (puerto 8123)
└── Gemini API client (cloud)
```

### **Volúmenes Montados**
```
/data/
├── proyectos/          # Proyectos en progreso
│   ├── short_01/
│   │   ├── guia.json      # Especificación del video
│   │   ├── imagenes/      # Assets visuales
│   │   ├── voz/           # Archivos de audio de voz
│   │   ├── musica/        # Pistas de música de fondo
│   │   └── fuentes/       # Tipografías (.ttf, .otf)
│   └── short_02/
├── salida/             # Videos renderizados
│   ├── short_01.mp4
│   ├── logs/           # Logs de renderizado
│   └── tmp_short_01/   # Clips intermedios (debug)
└── plantilla/          # Template para nuevos proyectos
```

---

## 🔌 Endpoints API

### **Health Check**
```http
GET /health
```
Verifica que ffmpeg esté disponible.

### **Gestión de Proyectos**
```http
POST /nuevo                    # Crear nuevo proyecto
GET  /proyectos                # Listar proyectos con estado
GET  /revisar/{proyecto}       # Inspeccionar contenido del proyecto
```

### **Análisis de Archivos**
```http
POST /probe
```
Inspecciona metadatos de video (duración, resolución, codec) usando ffprobe.

### **Generación de Guía**
```http
POST /generar-guia             # IA → JSON guía
```
Usa Gemini para convertir `guia.md` en `guia.json`. Incluye normalización y validación de archivos.

### **Renderizado**
```http
POST   /render                 # Inicia renderizado
GET    /estado/{proyecto}      # Monitorea progreso (logs en vivo)
GET    /video/{proyecto}       # Descarga video final
```

---

## 📊 Flujo de Trabajo Completo

```
1. Usuario crea proyecto
   POST /nuevo → estructura carpetas + copia plantilla

2. Usuario sube assets
   imagenes/, voz/, musica/, y escribe guia.md

3. Generación automática de guía
   POST /generar-guia
   ├─ Lee guia.md + lista archivos
   ├─ Prompt a Gemini con instrucciones detalladas
   ├─ Extrae + normaliza JSON
   ├─ Valida referencias a archivos
   └─ Guarda guia.json

4. Validación del proyecto
   GET /revisar/{proyecto}
   ├─ Cuenta archivos subidos
   └─ Detecta archivos faltantes

5. Renderizado
   POST /render
   ├─ Validación (guia.json existe, archivos completos)
   ├─ Inicia proceso en background (start_new_session=True)
   └─ Retorna inmediatamente (no bloqueante)

6. Monitoreo
   GET /estado/{proyecto} (polling)
   ├─ Lee log en vivo
   ├─ Detecta: en progreso, completado, error
   └─ Retorna últimas 12 líneas + estado

7. Descarga
   GET /video/{proyecto}
   └─ Sirve MP4 listo (+ faststart para streaming)
```

---

## 🎬 Proceso de Renderizado (render.py)

### **Fase 1: Planificación**
- Lee `guia.json`
- Mide duración de cada audio (voz.mp3)
- Calcula frame count para cada escena
- Genera plan con timing de inicio/fin de cada elemento

### **Fase 2: Renderizado por Escena** (paralelo por clip)
Para cada escena genera un MP4 con:
- **Imágenes**: Scale/crop a 1620x2880, zoom/paneo dinámico
- **Transiciones internas**: Cross-dissolve entre imágenes dentro de una escena
- **Textos**: Multi-capa con animaciones (fade, word-by-word, fade golpe)
- **Codec**: H.264, preset veryfast (rápido), CRF 18 (alta calidad)

### **Fase 3: Composición de Video**
- Concatena clips con transiciones (fade/fadeblack/dissolve/corte)
- Re-encoda a CRF 20 (balance velocidad/calidad)

### **Fase 4: Audio**
- Sincroniza múltiples voces con delays precisos
- Mezcla con música de fondo (volumen variable por escena)
- Fade out de música al final

### **Fase 5: Exportación**
- Mux video + audio con codec AAC
- Agrega `faststart` flag (streaming desde inicio)
- Duración total: 30-60s típica

**Salida**: `/data/salida/{proyecto}.mp4` (1080x1920 @ 30fps, vertical)

---

## 🤖 Generación de Guía (guia_ia.py)

### **Prompt a Gemini**
El sistema construye un prompt detallado que incluye:

1. **Instrucciones de formato**: Estructura exacta del JSON esperado
2. **Catálogo de efectos**: zoom_in, zoom_out, paneo_der, paneo_rapido, ninguno
3. **Transiciones**: corte, fade, fadeblack, fadewhite, dissolve
4. **Campos de escena**: id, efecto, musica_vol, transicion_salida, textos (con posición, fuente, tamaño, animación)
5. **Archivos disponibles**: Lista real de imagenes/, voz/, musica/
6. **Ejemplo funcional**: Una guía JSON de otro proyecto que ya funciona

### **Normalización Posterior**
```python
- Corrige mayúsculas de nombres de archivo
- Valida rutas contra archivos reales
- Calcula cortes de video (proporciones) para montajes
- Ajusta tamaños de texto según ancho disponible
- Valida que no falten archivos críticos
- Estima duración final
```

### **Manejo de Errores**
- Guarda respuesta cruda de Gemini para debug
- Si hay archivos faltantes: genera `guia_borrador.json` (revisable)
- Resintenta con backoff en caso de limit rate (429, 503)

---

## 📈 Oportunidades de Optimización

### **Nivel 1: Rápidas (impacto alto, riesgo bajo)**

1. **Caché de análisis de ffprobe**
   - Los metadatos de video no cambian
   - Guardar resultado en Redis/JSON local (TTL: 24h)
   - Ahorro: -0.5-1s por proyecto en /probe

2. **Paralización de renderizado de escenas**
   - Actualmente secuencial: escena 1 → 2 → 3
   - Usar `concurrent.futures.ThreadPoolExecutor` para multi-core
   - Ahorro: 30-50% en tiempo total (si máquina tiene 4+ cores)

3. **Pre-compilación de filtros FFmpeg**
   - Los mismos efectos (zoom, fade) se repiten
   - Compilar filter graph una vez, reutilizar parámetros
   - Ahorro: ~10-15% (optimización compilador FFmpeg)

4. **Compresión de logs**
   - Logs crecen 100KB+ por render
   - Rotación + gzip después de 48h
   - Ahorro: -70% almacenamiento

### **Nivel 2: Medianas (impacto medio-alto, algo de riesgo)**

5. **Cache de Gemini con checksums**
   - Si guia.md no cambió → reutilizar guia.json anterior
   - Checksum SHA256 de archivos + contenido
   - Ahorro: -3-5s (evita latencia API Gemini)

6. **Downsampling de assets en preview**
   - Opción `/render?quality=draft` (720p en vez de 1080p)
   - Para preview/debug de layouts
   - Ahorro: -60% tiempo renderizado

7. **Rendering incremental**
   - Detectar qué escenas cambiaron desde último render
   - Re-renderizar solo esas + transiciones adyacentes
   - Ahorro: -70-80% si cambios son puntuales

8. **Caché distribuido (Redis)**
   - Estado de proyectos en memoria
   - Logs en stream (en vez de archivos)
   - Facilita escalado horizontal
   - Ahorro: -I/O disco, +responsividad

### **Nivel 3: Largas (impacto alto, mayor complejidad)**

9. **GPU encoding**
   - `libx264` → `h264_nvenc` (NVIDIA) o `hevc_videotoolbox` (Mac)
   - Si servidor tiene GPU dedicada
   - Ahorro: -70-80% tiempo renderizado (pero requiere hardware)

10. **Generación progresiva de clips**
    - Empezar a renderizar mientras aún se reciben assets
    - WebSocket para feedback en vivo
    - UX: usuario ve progreso real-time

11. **Marketplace de estilos**
    - Template reutilizables (plantilla → guia.json predefinida)
    - Reducir dependencia de Gemini
    - Ahorro: evita latencia + costo API

---

## ⚠️ Limitaciones Actuales

| Aspecto | Situación | Impacto |
|---------|-----------|--------|
| **Renderizado** | Secuencial (escenas 1 por 1) | 5-10 min para video 60s |
| **IA Guía** | Latencia Gemini 2-5s | Cuellos de botella |
| **Almacenamiento** | Sin limpieza automática | tmp_* crece indefinido |
| **Logs** | Sin rotación | Disk fill risk |
| **Error handling** | Timeout fijo 20 min | Renders largos mueren |
| **Scalabilidad** | Una sola instancia | No horizontal |
| **Validación guia.json** | Post-generación | Re-trabajo si falla |

---

## 📝 Recomendaciones de Arquitectura

### **Corto Plazo (2-3 sprints)**
- ✅ Paralizar renderizado de escenas (Nivel 1.2)
- ✅ Implementar caché local de ffprobe (Nivel 1.1)
- ✅ Rotación de logs (Nivel 1.4)

### **Mediano Plazo (1-2 trimestres)**
- ✅ Agregar Redis para estado distribuido (Nivel 2.8)
- ✅ Cache Gemini con checksums (Nivel 2.5)
- ✅ Opción de preview/draft (Nivel 2.6)

### **Largo Plazo (roadmap)**
- ✅ GPU encoding (si presupuesto permite)
- ✅ Sistema de estilos/templates
- ✅ WebSocket para rendering progresivo

---

## 🔧 Tech Stack Actual

| Componente | Versión | Rol |
|------------|---------|-----|
| Python | 3.12 | Runtime |
| FastAPI | Latest | HTTP API |
| Uvicorn | Latest | ASGI server |
| FFmpeg | 6.x+ | Video encoding |
| Gemini API | 3.8-flash | IA generativa |

---

## 📚 Flujos de Datos Clave

### **JSON guia.json**
```json
{
  "proyecto": "short_01",
  "formato": {"ancho": 1080, "alto": 1920, "fps": 30},
  "fuentes": {"bold": "...", "serif": "..."},
  "voz_retraso": 0.3,           // delay antes de empezar voz
  "pausa_entre_escenas": 0.3,   // gap entre escenas
  "duracion_max": 90,           // validación
  "musica": {
    "archivo": "musica/bg.mp3",
    "volumen": 0.6,
    "fade_out": 2.0
  },
  "escenas": [
    {
      "id": "1",
      "imagenes": ["imagenes/img_01.jpg"],
      "voz": "voz/01_intro.mp3",
      "efecto": "zoom_in_lento",
      "musica_vol": 0.15,
      "textos": [
        {
          "contenido": "Hook de gancho",
          "fuente": "bold",
          "tamano": 100,
          "posicion": "centro",
          "color": "white",
          "animacion": "fade",
          "inicio": 0
        }
      ],
      "transicion_salida": {"tipo": "corte"}
    }
  ]
}
```

---

## 🎯 Puntos Críticos de Mejora

| # | Mejora | Esfuerzo | Impacto | Prioridad |
|----|--------|----------|---------|-----------|
| 1 | Paralizar escenas | 1 día | -50% tiempo | 🔴 Crítica |
| 2 | Cache ffprobe | 2h | -0.5s | 🟡 Alta |
| 3 | Rotación logs | 2h | +estabilidad | 🟡 Alta |
| 4 | Redis cache | 1-2 días | +escalabilidad | 🟠 Media |
| 5 | GPU encoding | 3-5 días | -70% tiempo | 🟠 Media |
| 6 | WebSocket progreso | 2 días | +UX | 🟢 Baja |

---

## 💡 Conclusión

**FFmpeg API es un sistema bien diseñado para automatización de shorts**, con puntos de entrada claros para optimización. Las mejoras de mayor impacto (paralización, caché, logs) son implementables en 1-2 sprints sin riesgo, y liberarían un 40-60% de tiempo de renderizado actual.

**Recomendación:** Comenzar con paralización de escenas (máximo beneficio/mínimo esfuerzo), luego agregar cache distribuido para escalabilidad.

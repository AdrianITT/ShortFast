# Plan: interfaz web (`panel/interfaces/web.py`)

Última actualización: 2026-11-08.

## 0. Punto de partida

No es un proyecto nuevo: `panel/` ya separa la lógica de negocio (`ServicioProyectos`, `GeneradorVoces`, `ClienteKokoro`, `ClienteApi`) de la interfaz (`Interfaz` abstracta, `InterfazTerminal`). La web es una segunda `Interfaz` que reutiliza esas mismas clases sin tocarlas. Se activa en `panel.json` (`web.habilitada: true`) junto con la terminal, sin reemplazarla.

## 1. Objetivo y alcance

Un panel web, usable desde PC y celular, dentro y fuera de la red (acceso remoto exige autenticación, regla ya registrada en `HISTORIAL.md` del 2026-10-02), para:

1. Elegir o crear un proyecto (short 9:16 o video largo 16:9 — pipelines independientes, mismo panel).
2. Subir archivos: imágenes, música, fuentes — arrastrar/soltar o seleccionar, destino `imagenes/`, `musica/`, `fuentes/` del proyecto.
3. Voz: dos caminos, igual que hoy en terminal —
   - pegar guion (detecta formato bash o líneas) y generar con Kokoro;
   - subir archivos de audio ya grabados directamente a `voz/`.
4. Guía: generar con IA (Gemini) o desde borrador local; ver/editar el JSON resultante antes de renderizar.
5. Renderizar: lanzar, ver progreso en vivo (igual que `seguir_render`, por polling o websocket) y log.
6. Descargar el video final.
7. Música reutilizable entre proyectos (sección 5).

Fuera de alcance de esta fase: Telegram (ya planeado como paso intermedio en `HISTORIAL.md` pero no es parte de este plan), edición visual de la guía tipo editor de timeline.

## 2. Arquitectura

```
Navegador (HTML/JS, sin framework pesado)
        │  fetch / fetch+SSE
        ▼
InterfazWeb (panel/interfaces/web.py)   ← nueva, hereda de Interfaz
        │  llama directamente a
        ▼
ServicioProyectos / GeneradorVoces / ClienteKokoro   ← YA EXISTEN, sin modificar
        │  HTTP
        ▼
ffmpeg-api (main.py / render_largo.py)   ← YA EXISTE, sin modificar
```

- `InterfazWeb` levanta un servidor HTTP propio (FastAPI, ya es dependencia del proyecto vía `ffmpeg-api`, o `http.server` si se quiere cero dependencias nuevas — a decidir en 3.1) en el puerto que indique `panel.json`.
- `en_segundo_plano = True`: a diferencia de la terminal, la web puede correr junto con otras interfaces activas simultáneamente (regla ya prevista en el diseño de `Interfaz`).
- No se duplica lógica: cada endpoint de `InterfazWeb` es una llamada fina a `ServicioProyectos`, igual que hace `InterfazTerminal`.
- Sigue las reglas de POO de `REGLAS.md` 1.1: la interfaz solo orquesta HTTP ↔ servicio.

## 3. Decisiones a confirmar con el usuario antes de picar código

### 3.1 Framework del servidor web
- **FastAPI + Jinja2** (recomendado): consistente con `main.py`, permite subida de archivos (`UploadFile`) y streaming de progreso (`EventSource`/SSE) sin librerías extra.
- Alternativa: `http.server` puro (cero dependencias) — más trabajo para subir archivos grandes y progreso en vivo.

### 3.2 Autenticación para acceso remoto
Pendiente del diseño de acceso remoto fuera de la red (mencionado en `HISTORIAL.md` pero no implementado). Opciones simples: contraseña única por variable de entorno + cookie de sesión, o Basic Auth. Se decide antes de exponer el puerto fuera de la red local.

### 3.3 Progreso de render en vivo
`ServicioProyectos.seguir_render` ya es un generador por polling cada N segundos. Para la web: Server-Sent Events (push simple) en vez de que el navegador haga polling — reusa el mismo generador, solo cambia quién lo consume.

## 4. Fases de implementación

- [x] **Fase 1 — servidor mínimo y lista de proyectos**: `InterfazWeb.iniciar()`, ruta `/` con lista de proyectos (reusa `ServicioProyectos.listar`), elegir/crear proyecto. Sin autenticación todavía (solo red local).
- [x] **Fase 2 — subida de archivos**: formulario de subida para imágenes/música/fuentes/voz grabada, validando extensión y tamaño, igual de estricto que `GeneradorVoces` con los nombres (sin rutas, sin sobrescribir sin confirmar).
- [x] **Fase 3 — voz con Kokoro desde la web**: textarea para pegar guion (reusa `GuionVoces`/`AnalizadorBash`/`AnalizadorLineas` sin tocarlos), vista previa del resumen, confirmar, progreso por tramo, reintento de fallidos — mismo flujo que terminal, en HTML.
- [x] **Fase 4 — guía**: botones "Generar con IA" / "Generar desde borrador", vista del `guia.json` resultante (solo lectura). Incluye lo pedido por el usuario: crear/editar `guia_borrador.json` directamente desde la web.
- [x] **Fase 5 — render y descarga**: lanzar render, barra/log de progreso vía SSE, botón de descarga cuando termina.
- [x] **Fase 6 — música reutilizable** (ver sección 5).
- [x] **Fase 7 — autenticación para acceso remoto**: HTTP Basic Auth, activa solo si `PANEL_CLAVE` está puesta en el entorno/`.env`. Sin esa variable, la web sigue sin autenticación (uso en red local).

Cada fase se prueba contra la API real en un proyecto de prueba antes de pasar a la siguiente, como se ha hecho con el resto del servicio (ver convención en `HISTORIAL.md`).

## 5. Música reutilizable entre proyectos

Problema a resolver: hoy la música vive solo dentro de `musica/` de cada proyecto; no hay forma de "ya usé esta pista en otro short, úsala de nuevo" sin volver a subirla.

Propuesta:
- Carpeta compartida `datos/musica_biblioteca/` (fuera de cada proyecto), poblada automáticamente: cada vez que se sube una pista nueva a un proyecto, se ofrece "guardar también en la biblioteca" (copia, no symlink, para no romper nada si se borra el proyecto).
- En el selector de música del proyecto: dos pestañas — "Subir nueva" y "Elegir de la biblioteca" (lista con nombre, duración vía `/probe` ya cacheado, y cuántas veces se ha usado).
- Elegir de la biblioteca = copiar el archivo a `musica/` del proyecto actual (mismo comportamiento que subir, para no introducir rutas compartidas en `guia.json` entre proyectos).
- No se decide todavía si vale la pena indexar también por "canción usada en short X" automáticamente desde `HISTORIAL.md`/`guia.json` existentes — se revisa en la Fase 6 con el usuario.

## 6. Qué NO cambia

- `main.py`, `guia_ia.py`, `generar_guia.py`: protegidos (regla 1 de `REGLAS.md`), la web no los toca.
- `render.py`, `largo/*`: la web no renderiza nada ella misma, solo llama a la API, igual que la terminal.
- `InterfazTerminal` sigue funcionando igual; ambas interfaces pueden estar activas a la vez.

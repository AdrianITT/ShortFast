# Reglas del proyecto ffmpeg-api

Última actualización: 2026-11-12.

## 1. Código
1. El código de los shorts 9:16 **no se modifica**: `main.py`, `guia_ia.py`, `generar_guia.py`. **Excepción (2026-10-02, decisión del usuario): `render.py` puede modificarse para mejorar la calidad de los shorts**, siempre con copia de seguridad, re-render de un short antes y después, y comparación de que no cambia nada que no deba.
2. El video largo es un pipeline paralelo, con archivos, endpoints y carpetas propios (`render_largo.py`, `guia_largo_ia.py`, `/largo/*`, `/data/proyectos_largos/`).
3. Las utilidades genéricas (`duracion`, `run`, logs/estado, transiciones) se **copian**, no se importan.
4. Shorts y video largo son producciones independientes.

## 1.0.1 Terminal del panel (`InterfazTerminal`)
El usuario sigue usando la terminal del panel a diario. Cualquier cambio en `ServicioProyectos` o en clases compartidas (archivos, biblioteca, guía, voces) debe mantener su comportamiento actual intacto para `InterfazTerminal`: no romperla ni retirarle opciones. Una función nueva (ej. acciones de biblioteca) se añade sin tocar el flujo ya existente, y si tiene sentido usarla también desde la terminal, se ofrece ahí, no solo en la web.

## 1.1 Estructura y POO
1. Mantener una estructura de proyecto limpia: cada archivo y carpeta con una sola responsabilidad, sin duplicados ni restos (`.bak`, scripts sueltos) en código nuevo.
2. El código nuevo sigue programación orientada a objetos: clases con responsabilidad única, encapsulación, bajo acoplamiento y dependencias inyectadas (no globales).
3. Los endpoints solo orquestan: la lógica vive en clases (por ejemplo proyecto, guía, renderizador, escena, estado/log).
4. Nombres claros y consistentes; un módulo por clase o grupo cohesivo de clases.
5. Esta regla aplica al código nuevo (video largo); el código de shorts no se reestructura, solo se corrige y mejora en `render.py` (ver la excepción en la sección Código).

## 2. n8n
1. No se modifica ningún workflow sin confirmación explícita del usuario.
2. La lectura (consultar workflows, ejecuciones) está permitida.
3. La clave de API vive en `~/.n8n_api_key` (permisos 600). Nunca se copia a archivos del repo ni se muestra en pantalla.
4. Rotar la clave de n8n al terminar el trabajo con n8n (se compartió en el chat el 2026-10-01).
5. El video largo **no se envía por Telegram** (límite de 50 MB); se avisa con ruta y tamaño.

## 3. Seguridad
1. `.env` (con `GEMINI_API_KEY`) no se sube a git ni se imprime; si el proyecto se comparte, regenerar la clave.
2. Los valores de secretos se ocultan al mostrar archivos de configuración.

## 4. Proceso de trabajo
1. **Todo movimiento se registra en `HISTORIAL.md`**: cambios de código, de archivos, de n8n, pruebas, despliegues y decisiones. Una fila por acción, con fecha, tipo y detalle.
2. Las reglas nuevas o modificadas se anotan en este archivo y su cambio, en `HISTORIAL.md`.
3. Se avanza por fases (ver `PLAN_VIDEO_LARGO.md`); no se pasa a la siguiente sin cumplir el criterio de "terminado".
4. Al completar un entregable se marca su casilla en el plan.
5. Commits y pushes solo cuando el usuario lo pida.
6. Antes de borrar o sobrescribir, revisar el contenido del objetivo.

## 5. Despliegue
Desde el 2026-11-12 (`PLAN_INSTALACION.md`, fase 5):
- Todo corre con `docker-compose.yml` (proyecto `shortfast`), registrado en CasaOS como **una app «ShortFast»**: API (8123), panel web (8090) y voces (Supertonic 5200, clonador 5300, Kokoro 8880, Edge 5050; solo en 127.0.0.1). `/DATA/video-editor` se monta en `/data`.
- El código va **dentro de las imágenes**: tras cambiar código (API, panel o voces) hay que reconstruir y aplicar con `./instalar.sh -y` (antes bastaba con guardar el archivo). Probar los cambios antes en un proyecto de compose aparte (otro `COMPOSE_PROJECT_NAME` y otros puertos), como en las pruebas de la instalación.
- Instalar en otro equipo: `GUIA_INSTALACION.md`. Copia del `.env` anterior a la migración en `~/respaldo_shortfast/`.

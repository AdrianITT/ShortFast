# Guía de uso de ShortFast

Cómo hacer un short de principio a fin con el **panel web**. Para instalar, ver `GUIA_INSTALACION.md`; para la terminal, los comandos de shell y la API, ver `README.md` (sección 2).

Abre el panel en `http://<ip-del-equipo>:8090`. Pide contraseña: cualquier usuario y la clave `PANEL_CLAVE` del `.env`.

Arriba siempre tienes el menú **Proyectos · Biblioteca de música · Mis voces**. Dentro de un proyecto, la cabecera muestra los cuatro pasos (**1 Archivos · 2 Voces · 3 Guía · 4 Render**), con ✓ en los que ya están hechos; puedes saltar a cualquiera con un clic.

---

## 0. Antes del primer proyecto: la plantilla

Cada proyecto nuevo se crea copiando `<datos>/plantilla/`: tipografías (`fuentes/`), logo (`imagenes/`), audios fijos (`voz/`, p. ej. el «suscríbanse») y `ejemplo_guia.json` (modelo para la IA). En un equipo nuevo está vacía: cópiala del equipo donde ya trabajas. Lo que pongas ahí aparecerá en todos los proyectos nuevos.

## 1. Proyectos (portada)

- **Buscar:** escribe en la barra (atajo: tecla `/`). Con una sola coincidencia, `Enter` la abre; `Esc` borra.
- Los proyectos salen en dos grupos: **Pendientes** (sin render o con error) y **Listos**. Los listos antiguos se ocultan; «Ver los N» los muestra.
- Cada tarjeta indica el estado: *Sin render*, *Renderizando* (punto que late), *Listo* o *Error*, y «sin guía» si aún no la tiene.
- **+ Nuevo proyecto:** nombre sin espacios, solo letras, números, `-` y `_` (convención: `short_82_tema`). Se crea desde la plantilla y te lleva a él.

## 2. Archivos

La pantalla del proyecto te dice **qué falta** y te ofrece un solo botón con el paso que toca (Generar voces → Crear guía → Renderizar video).

Hay una tarjeta por carpeta, con cuántos archivos tiene («Ver archivos» los lista):

| Carpeta | Formatos | Máximo por archivo |
|---|---|---|
| Imágenes | jpg, jpeg, png, webp | 25 MB |
| Música | mp3, wav, m4a, aac | 50 MB |
| Voz | mp3 | 25 MB |
| Fuentes | ttf, otf | 10 MB |

- Arrastra los archivos sobre la tarjeta o pulsa «Elegir o soltar archivos», y luego **Subir**. El resultado sale arriba, en la misma pantalla.
- **Reemplazar si ya existe:** sin marcar, un archivo con el mismo nombre no se pisa.
- **Música → Guardar en la biblioteca:** además de subirla al proyecto, la deja disponible para otros proyectos.
- **Música → Elegir de la biblioteca:** copia al proyecto una pista que ya usaste (ver sección 6).

## 3. Voces

Necesitas un mp3 por escena en `voz/`. Hay tres formas:

### a) Generarlas a partir del guion (lo habitual)

1. Pega el guion, **una línea por audio**:
   ```
   01_hook.mp3 | Tu miedo al fracaso te ha costado más... que todos tus fracasos juntos.
   02_lugar.mp3 | Atenas, siglo quinto antes de Cristo.
   ```
   También acepta tu script de bash (`VOZ="..."` y `g "01_hook.mp3" "texto"`); solo se lee, nunca se ejecuta.
2. Elige **Servicio**, **Voz** y **Velocidad**. Manda lo que elijas aquí, aunque el guion diga otra voz.

   | Servicio | Cómo suena | Notas |
   |---|---|---|
   | Supertonic | Natural, la recomendada (M3) | 10 voces: M1–M5 hombre, F1–F5 mujer |
   | Kokoro | Buena, algo más sintética | Voces `em_`/`ef_` en español |
   | Edge | Voces de Microsoft | Necesita internet |
   | Mi voz | Tu voz clonada | Antes hay que crearla en «Mis voces» (sección 7) |

   Solo aparecen los servicios instalados en ese equipo.
3. **Revisar antes de generar:** muestra cada audio con su texto. Si alguno ya existe, se queda como está salvo que marques **Regenerarlos**. «Editar el guion» vuelve atrás sin perder lo escrito.
4. **Generar N audios.** Si algún tramo falla, te ofrece reintentar solo los fallidos.

### b) Cortar una grabación tuya

Si grabaste todo el guion de corrido en un solo audio: en Voces, «Subir la grabación y cortarla en tramos».

1. Sube la grabación (mp3, wav, m4a…). Deja **medio segundo o más de silencio entre escena y escena**.
2. Pega el guion (da nombre a cada audio) o di solo cuántos audios salen.
3. **Detectar cortes.** Si no acierta, ajusta la sensibilidad (umbral en dB y pausa mínima) y «Volver a detectar».
4. Escucha cada tramo con ▶ y corrige los segundos de inicio y fin si hace falta.
5. **Guardar N audios.**

### c) Subirlas ya hechas

Súbelas en la tarjeta **Voz** de Archivos, con los mismos nombres que usará la guía.

## 4. Guía

La guía (`guia.json`) dice qué imagen, voz, texto, efecto y música va en cada escena. Dos formas de crearla:

- **Desde el borrador (local, sin IA):** pega o edita el JSON del borrador (`guia_borrador.json`) y pulsa **Guardar y generar guía**. Se valida antes de guardar y se enlaza con los archivos reales del proyecto (por ejemplo, `IMG_01.png` en el borrador encuentra `IMG_01_f0253c2a.jpg`). «Guardar borrador» guarda sin generar.
- **Generar con IA (Gemini):** usa el `guia.md` del proyecto (tu guion/mapa de escenas) y `ejemplo_guia.json` de la plantilla como modelo. No usa el borrador. Necesita `GEMINI_API_KEY` en el `.env`.

Abajo ves la **Guía final** («ver contenido»). Cuando existe, aparece **Siguiente: renderizar**.

Referencia de campos: efectos de imagen, animaciones de texto, transiciones y opciones de calidad en `EFECTOS_DISPONIBLES.md` y en `README.md` («Opciones de calidad de los shorts»).

## 5. Render

1. **Iniciar render.** Antes comprueba que existan todos los archivos que nombra la guía; si falta alguno, lo dice.
2. El progreso y el registro se ven en vivo. **Puedes cerrar la página: el render sigue en el servidor.** Un short de ~1 min tarda unos 3–4 minutos.
3. Al terminar: **vista previa** en la misma página, **Descargar video** y **Renderizar de nuevo** (tras cambiar la guía o los archivos).
4. Si sale *Error*, el registro dice por qué; corrige y pulsa **Reintentar**.

El video queda también en `<datos>/salida/<proyecto>.mp4` y el log en `<datos>/salida/logs/`.

## 6. Biblioteca de música

Pistas compartidas entre todos los proyectos (menú **Biblioteca de música**).

- **Subir pistas a la biblioteca:** arrastra una o varias.
- **Indexar música de proyectos:** recorre los proyectos y añade a la biblioteca la música que usan sus `guia.json`. Útil la primera vez.
- La tabla muestra duración y cuántos proyectos usan cada pista; el buscador filtra por nombre.
- Desde un proyecto, **Música → Elegir de la biblioteca → Usar** copia la pista al proyecto.

## 7. Mis voces (clonar una voz)

1. Menú **Mis voces → Nueva voz**.
2. Sube **20 s a 1 min** de voz hablando con naturalidad (mejor leyendo algo parecido a tus guiones): una sola persona, sin música, poco ruido y el micrófono cerca. Mínimo 10 s de voz sin contar silencios.
3. Ponle **nombre** (minúsculas, números, `_` y `-`) y elige la **voz base** de Supertonic (M = hombre, F = mujer): pone la pronunciación, y el clonador le pone tu timbre.
4. **Crear voz.** Tarda de segundos a unos minutos (más la primera vez con cada voz base). No cierres la página.
5. Escucha la muestra con ▶. Si no te convence, bórrala y prueba otra voz base o una grabación más limpia.
6. Úsala en **Voces → Servicio «Mi voz»**.

**Solo tu voz o la de alguien que te dé permiso.** No uses voces de terceros (ni las de bibliotecas como ElevenLabs).

---

## Flujo rápido (resumen)

1. Portada → **+ Nuevo proyecto** (`short_82_tema`).
2. **Archivos:** sube imágenes y música (o elígela de la biblioteca).
3. **Voces:** pega el guion → Supertonic M3 → Revisar → Generar.
4. **Guía:** pega el borrador → Guardar y generar guía (o Generar con IA).
5. **Render:** Iniciar → revisar la vista previa → Descargar.

## Problemas frecuentes

| Síntoma | Qué hacer |
|---|---|
| «Falta: …» en el proyecto | Sube lo que indica o genera las voces que faltan |
| Render en *Error* por archivo que no existe | El nombre en la guía no coincide con el subido; corrige uno de los dos y reintenta |
| Un servicio de voz no aparece | No está instalado en ese equipo (`GUIA_INSTALACION.md`, «Elegir voces») |
| «Mi voz» dice que no tiene voces | Crea una en **Mis voces** |
| «Generar con IA» falla | Falta `guia.md` en el proyecto o `GEMINI_API_KEY` en el `.env` |
| Los cortes de la grabación salen mal | Más silencio entre escenas al grabar, o ajusta umbral y pausa mínima |
| Proyecto nuevo sin fuentes ni logo | La plantilla está vacía (sección 0) |

"""Interfaz web del panel.

Solo orquesta HTTP -> ServicioProyectos, igual que InterfazTerminal.
Autenticación (fase 7): si la variable de entorno PANEL_CLAVE está puesta,
todas las rutas exigen HTTP Basic Auth con esa clave (usuario libre). Si no
está puesta, no hay autenticación -> solo usar dentro de la red local.
"""
import json
import re
import os
import secrets
from urllib.parse import quote
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from ..archivos import CATEGORIAS
from ..biblioteca import ErrorBiblioteca
from ..clonador import ClienteClonador, ErrorClonador
from ..cliente_api import ErrorApi
from ..cortador import SILENCIO_MIN, UMBRAL_DB, ErrorCorte
from ..guia import ErrorGuia
from ..voces import ErrorGuionVoces
from .base import Interfaz

CARPETA_TEMPLATES = Path(__file__).parent / "templates"

ETIQUETAS_CATEGORIA = {
    "imagenes": "Imágenes",
    "musica": "Música",
    "fuentes": "Fuentes",
    "voz": "Voz (archivos ya grabados)",
}

ETIQUETAS_ESTADO = {"ok": "Listo", "renderizando": "Renderizando", "error": "Error", "sin_render": "Sin render"}


class InterfazWeb(Interfaz):
    nombre = "web"
    en_segundo_plano = True

    def iniciar(self):
        app = self._construir_app()
        host = self.opciones.get("host", "0.0.0.0")
        puerto = int(self.opciones.get("puerto", 8090))
        uvicorn.run(app, host=host, port=puerto, log_level="warning")

    def _construir_app(self):
        servicio = self.servicio
        templates = Jinja2Templates(directory=str(CARPETA_TEMPLATES))
        templates.env.globals["etiqueta_estado"] = ETIQUETAS_ESTADO
        templates.env.filters["partes_nombre"] = _partes_nombre
        templates.env.globals["hay_clonador"] = servicio.clonador is not None  # enlaces a «Mis voces»

        clave = os.environ.get("PANEL_CLAVE")
        dependencias = [Depends(_verificar_clave(clave))] if clave else []
        app = FastAPI(dependencies=dependencias)

        @app.get("/")
        def index(request: Request):
            try:
                proyectos = servicio.listar()
                error = None
            except ErrorApi as e:
                proyectos, error = [], str(e)
            return templates.TemplateResponse(
                request, "index.html", {"proyectos": proyectos, "error": error}
            )

        @app.post("/crear")
        def crear(request: Request, nombre: str = Form(...)):
            try:
                servicio.crear(nombre)
            except ErrorApi as e:
                return templates.TemplateResponse(
                    request, "index.html", {"proyectos": servicio.listar(), "error": str(e)}
                )
            return RedirectResponse(f"/proyecto/{nombre}", status_code=303)

        def _pagina_proyecto(request, nombre, resultados=None, titulo_resultados=None):
            try:
                revision = servicio.revisar(nombre)
                error = None
            except ErrorApi as e:
                revision, error = None, str(e)
            categorias = [
                {"id": c, "etiqueta": ETIQUETAS_CATEGORIA[c],
                 "extensiones": ", ".join(sorted(extensiones)),
                 "archivos": servicio.listar_archivos(nombre, c)}
                for c, (extensiones, _tamano_maximo) in CATEGORIAS.items()
            ]
            return templates.TemplateResponse(
                request, "proyecto.html",
                {"nombre": nombre, "revision": revision, "error": error, "categorias": categorias,
                 "resultados": resultados, "titulo_resultados": titulo_resultados},
            )

        @app.get("/proyecto/{nombre}")
        def proyecto(request: Request, nombre: str):
            return _pagina_proyecto(request, nombre)

        @app.post("/proyecto/{nombre}/subir/{categoria}")
        async def subir(request: Request, nombre: str, categoria: str,
                         archivos: list[UploadFile] = File(...), sobrescribir: bool = Form(False),
                         guardar_en_biblioteca: bool = Form(False)):
            if categoria not in CATEGORIAS:
                resultados = [(f.filename, "error", f"Categoría desconocida «{categoria}»") for f in archivos]
            else:
                datos = [(f.filename, await f.read()) for f in archivos if f.filename]
                resultados = servicio.subir_archivos(nombre, categoria, datos, sobrescribir, guardar_en_biblioteca)
            return _pagina_proyecto(request, nombre, resultados,
                                    f"Subida a {ETIQUETAS_CATEGORIA.get(categoria, categoria).lower()}")

        @app.get("/proyecto/{nombre}/musica/biblioteca")
        def musica_biblioteca(request: Request, nombre: str):
            return templates.TemplateResponse(
                request, "biblioteca.html",
                {"nombre": nombre, "pistas": servicio.listar_biblioteca()},
            )

        @app.post("/proyecto/{nombre}/musica/desde-biblioteca")
        def musica_desde_biblioteca(request: Request, nombre: str, archivo: str = Form(...),
                                     sobrescribir: bool = Form(False)):
            try:
                estado = servicio.usar_de_biblioteca(nombre, archivo, sobrescribir)
                resultados = [(archivo, estado, "")]
            except ErrorBiblioteca as e:
                resultados = [(archivo, "error", str(e))]
            return _pagina_proyecto(request, nombre, resultados, "Música desde la biblioteca")

        @app.get("/biblioteca")
        def biblioteca_pagina(request: Request):
            return templates.TemplateResponse(
                request, "biblioteca.html", {"nombre": None, "pistas": servicio.listar_biblioteca()}
            )

        @app.post("/biblioteca/indexar")
        def biblioteca_indexar(request: Request, nombre: str = Form("")):
            resultados = servicio.indexar_biblioteca()
            return templates.TemplateResponse(
                request, "biblioteca.html",
                {"nombre": nombre or None, "pistas": servicio.listar_biblioteca(), "resultado_indexado": resultados},
            )

        @app.post("/biblioteca/subir")
        async def biblioteca_subir(request: Request, archivos: list[UploadFile] = File(...), nombre: str = Form("")):
            resultados = []
            for f in archivos:
                if not f.filename:
                    continue
                try:
                    servicio.guardar_en_biblioteca(f.filename, await f.read())
                    resultados.append((f.filename, "guardado", ""))
                except ErrorBiblioteca as e:
                    resultados.append((f.filename, "error", str(e)))
            return templates.TemplateResponse(
                request, "biblioteca.html",
                {"nombre": nombre or None, "pistas": servicio.listar_biblioteca(), "resultados": resultados},
            )

        # ── voces propias: clonar una voz a partir de una grabación (servicio clonador-tts) ──
        def _pagina_voces_propias(request, mensaje="", error="", nombre_voz="", voz_base="M3"):
            try:
                voces = servicio.listar_voces_propias()
            except ErrorClonador as e:
                voces, error = [], error or str(e)
            return templates.TemplateResponse(
                request, "voces_propias.html",
                {"voces": voces, "mensaje": mensaje, "error": error, "nombre_voz": nombre_voz,
                 "voz_base": voz_base, "voces_base": ClienteClonador.VOCES_BASE},
            )

        @app.get("/voces-propias")
        def voces_propias(request: Request, mensaje: str = ""):
            return _pagina_voces_propias(request, mensaje)

        @app.post("/voces-propias")
        async def voces_propias_crear(request: Request, nombre_voz: str = Form(...), voz_base: str = Form("M3"),
                                      grabacion: UploadFile = File(...)):
            try:
                datos = servicio.crear_voz_propia(nombre_voz, voz_base, await grabacion.read())
            except ErrorClonador as e:
                return _pagina_voces_propias(request, error=str(e), nombre_voz=nombre_voz, voz_base=voz_base)
            mensaje = f"Voz «{datos['nombre']}» creada con {datos['duracion']} s de voz. Escucha la muestra."
            return RedirectResponse(f"/voces-propias?mensaje={quote(mensaje)}", status_code=303)

        @app.get("/voces-propias/{voz}/muestra")
        def voces_propias_muestra(voz: str):
            try:
                return Response(servicio.muestra_voz_propia(voz), media_type="audio/mpeg")
            except ErrorClonador as e:
                raise HTTPException(502, str(e)) from None

        @app.post("/voces-propias/{voz}/borrar")
        def voces_propias_borrar(request: Request, voz: str):
            try:
                servicio.borrar_voz_propia(voz)
            except ErrorClonador as e:
                return _pagina_voces_propias(request, error=str(e))
            return RedirectResponse(f"/voces-propias?mensaje={quote(f'Voz «{voz}» borrada.')}", status_code=303)

        def _motor(motor):
            """(nombre del servicio de voz elegido, su GeneradorVoces); vacío o desconocido = el de por defecto."""
            nombre_motor = motor if motor in servicio.motores_voz else next(iter(servicio.motores_voz))
            return nombre_motor, servicio.voces_de(nombre_motor)

        def _contexto_voz(motor, voz, velocidad, cambia_voz=False):
            nombre_motor, g = _motor(motor)
            grupos = g.voces_disponibles()
            if cambia_voz and voz not in {i for _, ids in grupos for i in ids}:
                voz = ""  # al cambiar de servicio, una voz del otro no sirve: se usa la de por defecto
            primera = grupos[0][1][0] if grupos else ""  # servicios sin voz fija («Mi voz»): la primera de la lista
            return {"motor": nombre_motor, "motores": list(servicio.motores_voz), "grupos": grupos,
                    "voz": voz or g.voz_por_defecto or primera, "velocidad": velocidad or g.velocidad_por_defecto}

        def _pagina_voces(request, nombre, error, texto, voz="", velocidad="", motor="", cambia_voz=False):
            return templates.TemplateResponse(
                request, "voces.html",
                {"nombre": nombre, "error": error, "texto": texto,
                 **_contexto_voz(motor, voz, velocidad, cambia_voz)},
            )

        @app.get("/proyecto/{nombre}/voces")
        def voces_formulario(request: Request, nombre: str, error: str = ""):
            return _pagina_voces(request, nombre, error, "")

        @app.post("/proyecto/{nombre}/voces/preparar")
        def voces_preparar(request: Request, nombre: str, texto: str = Form(...), voz: str = Form(""),
                           velocidad: str = Form(""), motor: str = Form("")):
            _, g = _motor(motor)
            try:
                guion = g.preparar(texto)
                v = g.velocidad_valida(velocidad)
            except ErrorGuionVoces as e:
                return _pagina_voces(request, nombre, str(e), texto, voz, velocidad, motor)
            # manda la voz del selector; la del guion (VOZ= / voz:) solo si no llega ninguna, y se avisa si difieren
            voz_guion = guion.voz if guion.voz and voz and guion.voz != voz else ""
            guion.voz = voz or guion.voz or None
            existentes = set(g.existentes(nombre, guion))
            tramos = [{"archivo": t.archivo, "caracteres": len(t.texto), "ya_existe": t.archivo in existentes}
                      for t in guion.tramos]
            return templates.TemplateResponse(
                request, "voces_confirmar.html",
                {"nombre": nombre, "tramos": tramos, "hay_existentes": bool(existentes), "texto": texto,
                 "voz_guion": voz_guion, **_contexto_voz(motor, guion.voz, v)},
            )

        @app.post("/proyecto/{nombre}/voces/editar")
        def voces_editar(request: Request, nombre: str, texto: str = Form(""), voz: str = Form(""),
                         velocidad: str = Form(""), motor: str = Form("")):
            # volver al guion desde «Revisar», o al cambiar de servicio, sin perder el texto, la voz ni la velocidad
            return _pagina_voces(request, nombre, "", texto, voz, velocidad, motor, cambia_voz=True)

        @app.post("/proyecto/{nombre}/voces/generar")
        def voces_generar(request: Request, nombre: str, texto: str = Form(...),
                           sobrescribir: bool = Form(False), voz: str = Form(""), velocidad: str = Form(""),
                           motor: str = Form("")):
            nombre_motor, g = _motor(motor)
            try:
                guion = g.preparar(texto)
                v = g.velocidad_valida(velocidad)
            except ErrorGuionVoces as e:
                return _pagina_voces(request, nombre, str(e), texto, voz, velocidad, motor)
            guion.voz = voz or guion.voz  # lo elegido al confirmar manda sobre la voz escrita en el guion
            resultados = list(g.generar(nombre, guion, sobrescribir, v))
            archivos_fallidos = {r.archivo for r in resultados if r.estado == "error"}
            tramos_fallidos = [t for t in guion.tramos if t.archivo in archivos_fallidos]
            texto_reintento = _texto_reintento(guion.voz, tramos_fallidos) if tramos_fallidos else ""
            return templates.TemplateResponse(
                request, "voces_resultado.html",
                {"nombre": nombre, "resultados": resultados, "texto_reintento": texto_reintento, "velocidad": v or "",
                 "motor": nombre_motor},
            )

        # ── cortar una grabación completa en un audio por tramo (alternativa a generar con TTS) ──
        def _pagina_cortar(request, nombre, error="", guion="", tramos="", umbral=UMBRAL_DB,
                           silencio=SILENCIO_MIN, propuesta=None, nombres=None):
            return templates.TemplateResponse(
                request, "voces_cortar.html",
                {"nombre": nombre, "error": error, "guion": guion, "tramos": tramos, "umbral": umbral,
                 "silencio": silencio, "propuesta": propuesta, "nombres": nombres or [],
                 "hay_grabacion": bool(servicio.cortador.grabacion(nombre)),
                 "existentes": set(servicio.listar_archivos(nombre, "voz"))},
            )

        @app.get("/proyecto/{nombre}/voces/cortar")
        def voces_cortar_formulario(request: Request, nombre: str):
            try:
                return _pagina_cortar(request, nombre)
            except ErrorCorte as e:
                raise HTTPException(404, str(e)) from None

        @app.post("/proyecto/{nombre}/voces/cortar")
        async def voces_cortar_detectar(request: Request, nombre: str, grabacion: UploadFile | None = File(None),
                                        guion: str = Form(""), tramos: str = Form(""),
                                        umbral: float = Form(UMBRAL_DB), silencio: float = Form(SILENCIO_MIN)):
            datos = dict(guion=guion, tramos=tramos, umbral=umbral, silencio=silencio)
            try:
                if grabacion and grabacion.filename:
                    servicio.cortador.guardar_grabacion(nombre, grabacion.filename, await grabacion.read())
                if guion.strip():  # los nombres salen del mismo guion que se usa para generar voces
                    nombres = [t.archivo for t in servicio.voces.preparar(guion).tramos]
                elif tramos.strip().isdigit() and int(tramos) > 0:
                    nombres = [f"{i:02d}.mp3" for i in range(1, int(tramos) + 1)]
                else:
                    raise ErrorCorte("Pega el guion (para usar sus nombres) o indica cuántos audios quieres")
                propuesta = servicio.cortador.proponer(nombre, len(nombres), umbral, silencio)
            except (ErrorCorte, ErrorGuionVoces) as e:
                return _pagina_cortar(request, nombre, str(e), **datos)
            return _pagina_cortar(request, nombre, propuesta=propuesta, nombres=nombres, **datos)

        @app.get("/proyecto/{nombre}/voces/grabacion")
        def voces_grabacion(nombre: str):
            try:
                ruta = servicio.cortador.grabacion(nombre)
            except ErrorCorte:
                ruta = None
            if not ruta:
                raise HTTPException(404, "Este proyecto no tiene grabación")
            return FileResponse(ruta)  # admite Range: el reproductor puede saltar a cada tramo

        @app.post("/proyecto/{nombre}/voces/cortar/guardar")
        def voces_cortar_guardar(request: Request, nombre: str, archivo: list[str] = Form(...),
                                 inicio: list[float] = Form(...), fin: list[float] = Form(...),
                                 sobrescribir: bool = Form(False)):
            try:
                resultados = list(servicio.cortador.cortar(nombre, zip(archivo, inicio, fin), sobrescribir))
            except ErrorCorte as e:
                return _pagina_cortar(request, nombre, str(e))
            return templates.TemplateResponse(
                request, "voces_resultado.html",
                {"nombre": nombre, "resultados": resultados, "texto_reintento": "", "velocidad": ""},
            )

        def _pagina_guia(request, nombre, borrador=None, mensaje=None, error=None):
            return templates.TemplateResponse(
                request, "guia.html",
                {
                    "nombre": nombre,
                    "borrador": borrador if borrador is not None else servicio.leer_guia_borrador(nombre),
                    "guia_json": servicio.leer_guia(nombre),
                    "mensaje": mensaje,
                    "error": error,
                },
            )

        @app.get("/proyecto/{nombre}/guia")
        def guia_pagina(request: Request, nombre: str):
            return _pagina_guia(request, nombre)

        @app.post("/proyecto/{nombre}/guia/borrador")
        def guia_guardar_borrador(request: Request, nombre: str, texto: str = Form(...)):
            try:
                servicio.guardar_guia_borrador(nombre, texto)
            except ErrorGuia as e:
                return _pagina_guia(request, nombre, borrador=texto, error=str(e))
            return _pagina_guia(request, nombre, mensaje="Borrador guardado.")

        @app.post("/proyecto/{nombre}/guia/generar-local")
        def guia_generar_local(request: Request, nombre: str, texto: str | None = Form(None)):
            if texto is not None:  # «Guardar y generar»: guarda el borrador del formulario antes de generar
                try:
                    servicio.guardar_guia_borrador(nombre, texto)
                except ErrorGuia as e:
                    return _pagina_guia(request, nombre, borrador=texto, error=str(e))
            try:
                r = servicio.generar_guia_local(nombre)
            except ErrorApi as e:
                return _pagina_guia(request, nombre, error=str(e))
            avisos = r.get("avisos") or []
            mensaje = "Guía generada desde el borrador." + (" Avisos: " + "; ".join(avisos) if avisos else "")
            return _pagina_guia(request, nombre, mensaje=mensaje)

        @app.post("/proyecto/{nombre}/guia/generar-ia")
        def guia_generar_ia(request: Request, nombre: str):
            try:
                servicio.generar_guia_ia(nombre)
            except ErrorApi as e:
                return _pagina_guia(request, nombre, error=str(e))
            return _pagina_guia(request, nombre, mensaje="Guía generada con IA.")

        @app.get("/proyecto/{nombre}/render")
        def render_pagina(request: Request, nombre: str):
            try:
                estado = servicio.estado(nombre)
                error = None
            except ErrorApi as e:
                estado, error = None, str(e)
            return templates.TemplateResponse(
                request, "render.html",
                {"nombre": nombre, "estado": estado, "error": error},
            )

        @app.post("/proyecto/{nombre}/render")
        def render_iniciar(request: Request, nombre: str):
            try:
                servicio.renderizar(nombre)
            except ErrorApi as e:
                return templates.TemplateResponse(
                    request, "render.html",
                    {"nombre": nombre, "estado": None, "error": str(e)},
                )
            return RedirectResponse(f"/proyecto/{nombre}/render", status_code=303)

        @app.get("/proyecto/{nombre}/render/eventos")
        def render_eventos(nombre: str):
            def generar():
                try:
                    for e in servicio.seguir_render(nombre):
                        yield f"data: {json.dumps(e)}\n\n"
                except ErrorApi as ex:
                    yield f"data: {json.dumps({'estado': 'error', 'log': str(ex)})}\n\n"
            return StreamingResponse(generar(), media_type="text/event-stream")

        @app.get("/proyecto/{nombre}/video")
        def descargar_video(nombre: str):
            try:
                flujo = servicio.abrir_video(nombre)
            except ErrorApi as e:
                raise HTTPException(status_code=502, detail=str(e)) from None
            return StreamingResponse(
                flujo, media_type="video/mp4",
                headers={"Content-Disposition": f'attachment; filename="{nombre}.mp4"'},
            )

        return app


def _verificar_clave(clave):
    seguridad = HTTPBasic()

    def verificar(credenciales: HTTPBasicCredentials = Depends(seguridad)):
        if not secrets.compare_digest(credenciales.password, clave):
            raise HTTPException(status_code=401, detail="Clave incorrecta",
                                 headers={"WWW-Authenticate": "Basic"})

    return verificar


def _texto_reintento(voz, tramos_fallidos):
    """Reconstruye un guion de solo líneas con los tramos fallidos, para el botón «reintentar»."""
    cabecera = f"voz: {voz}\n" if voz else ""
    return cabecera + "\n".join(f"{t.archivo} | {t.texto}" for t in tramos_fallidos)


def _partes_nombre(nombre):
    """«short_79_julio_cano» -> ("79", "julio cano") para mostrarlo legible; otros nombres -> ("", nombre)."""
    m = re.fullmatch(r"short_(\d+)_(.+)", nombre)
    return (m[1], m[2].replace("_", " ")) if m else ("", nombre)

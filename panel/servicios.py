"""Acciones de negocio sobre los proyectos. Las interfaces solo llaman a esta clase."""
import time
from pathlib import Path

from .archivos import ErrorArchivo
from .biblioteca import ErrorBiblioteca
from .cliente_api import ErrorApi
from .clonador import ErrorClonador


class ServicioProyectos:
    def __init__(self, cliente, carpeta_descargas, carpeta_proyectos, generador_voces,
                 gestor_archivos=None, gestor_guia=None, biblioteca_musica=None, cortador_voz=None,
                 motores_voz=None, clonador=None):
        self.cliente = cliente
        self.clonador = clonador  # ClienteClonador (voces propias); opcional: la terminal no lo usa
        self.carpeta_proyectos = Path(carpeta_proyectos)
        self.voces = generador_voces
        self.motores_voz = motores_voz or {"Voz": generador_voces}  # {nombre del servicio: GeneradorVoces}
        self.archivos = gestor_archivos
        self.guia = gestor_guia
        self.biblioteca = biblioteca_musica
        self.cortador = cortador_voz
        self.carpeta_descargas = Path(carpeta_descargas)

    def voces_de(self, motor):
        """El generador del servicio de voz elegido; si no existe, el de por defecto."""
        return self.motores_voz.get(motor, self.voces)

    # ── voces propias (clonadas): delegan en el clonador; ErrorClonador llega a la interfaz ──
    def _clonador(self):
        if self.clonador is None:
            raise ErrorClonador("El clonador de voz no está instalado (perfil «clonador» del instalador)")
        return self.clonador

    def listar_voces_propias(self):
        return self._clonador().listar()

    def crear_voz_propia(self, nombre, voz_base, audio):
        return self._clonador().crear(nombre, voz_base, audio)

    def borrar_voz_propia(self, nombre):
        self._clonador().borrar(nombre)

    def muestra_voz_propia(self, nombre):
        return self._clonador().muestra(nombre)

    def listar(self):
        return self.cliente.get("/proyectos")

    def crear(self, nombre):
        self.cliente.post("/nuevo", {"proyecto": nombre})
        return self.carpeta_proyectos / nombre

    def revisar(self, nombre):
        return self.cliente.get(f"/revisar/{nombre}")

    def generar_guia_ia(self, nombre):
        return self.cliente.post("/generar-guia", {"proyecto": nombre}, tiempo_espera=600)

    def generar_guia_local(self, nombre):
        return self.cliente.post("/generar-guia-local", {"proyecto": nombre})

    def renderizar(self, nombre):
        return self.cliente.post("/render", {"proyecto": nombre})

    def estado(self, nombre):
        return self.cliente.get(f"/estado/{nombre}")

    def seguir_render(self, nombre, intervalo=10):
        """Entrega el estado cada `intervalo` segundos hasta que el render termina."""
        while True:
            e = self.estado(nombre)
            yield e
            if e["estado"] != "renderizando":
                return
            time.sleep(intervalo)

    def listar_archivos(self, nombre, categoria):
        return self.archivos.listar(nombre, categoria)

    def subir_archivos(self, nombre, categoria, archivos, sobrescribir=False, guardar_en_biblioteca=False):
        """archivos: iterable de (nombre_archivo, contenido). Un fallo en uno no detiene los demás."""
        resultados = []
        for nombre_archivo, contenido in archivos:
            try:
                estado = self.archivos.guardar(nombre, categoria, nombre_archivo, contenido, sobrescribir)
                detalle = ""
                if estado == "guardado" and categoria == "musica" and guardar_en_biblioteca:
                    try:
                        self.biblioteca.guardar(nombre_archivo, contenido)
                        detalle = "añadido también a la biblioteca"
                    except ErrorBiblioteca as e:
                        detalle = f"no se pudo añadir a la biblioteca: {e}"
                resultados.append((nombre_archivo, estado, detalle))
            except ErrorArchivo as e:
                resultados.append((nombre_archivo, "error", str(e)))
        return resultados

    def listar_biblioteca(self):
        pistas = self.biblioteca.listar()
        for p in pistas:
            try:
                info = self.cliente.post("/probe", {"ruta": p["ruta_contenedor"]})
                p["duracion"] = info.get("duracion")
            except ErrorApi:
                p["duracion"] = None
        return pistas

    def guardar_en_biblioteca(self, nombre_archivo, contenido):
        self.biblioteca.guardar(nombre_archivo, contenido)

    def indexar_biblioteca(self):
        return self.biblioteca.indexar_proyectos(self.carpeta_proyectos)

    def usar_de_biblioteca(self, nombre_proyecto, nombre_archivo, sobrescribir=False):
        contenido = self.biblioteca.leer(nombre_archivo)
        estado = self.archivos.guardar(nombre_proyecto, "musica", nombre_archivo, contenido, sobrescribir)
        if estado == "guardado":
            self.biblioteca.registrar_uso(nombre_archivo)
        return estado

    def leer_guia_borrador(self, nombre):
        return self.guia.leer_borrador(nombre)

    def guardar_guia_borrador(self, nombre, texto):
        self.guia.guardar_borrador(nombre, texto)

    def leer_guia(self, nombre):
        return self.guia.leer_guia(nombre)

    def descargar_video(self, nombre):
        self.carpeta_descargas.mkdir(parents=True, exist_ok=True)
        destino = self.carpeta_descargas / f"{nombre}.mp4"
        self.cliente.descargar(f"/video/{nombre}", destino)
        return destino

    def abrir_video(self, nombre):
        """Flujo abierto del mp4 para reenviarlo tal cual (ej. a un navegador); quien llama lo cierra."""
        return self.cliente.abrir(f"/video/{nombre}")

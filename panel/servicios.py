"""Acciones de negocio sobre los proyectos. Las interfaces solo llaman a esta clase."""
import time
from pathlib import Path


class ServicioProyectos:
    def __init__(self, cliente, carpeta_descargas, carpeta_proyectos, generador_voces):
        self.cliente = cliente
        self.carpeta_proyectos = Path(carpeta_proyectos)
        self.voces = generador_voces
        self.carpeta_descargas = Path(carpeta_descargas)

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

    def descargar_video(self, nombre):
        self.carpeta_descargas.mkdir(parents=True, exist_ok=True)
        destino = self.carpeta_descargas / f"{nombre}.mp4"
        self.cliente.descargar(f"/video/{nombre}", destino)
        return destino

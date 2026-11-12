"""Lectura y edición de guia_borrador.json / guia.json en el proyecto.

Mismo patrón que GestorArchivos: lee y escribe directo en el disco
compartido con la API, con escritura atómica. No reimplementa
generar_guia.py ni guia_ia.py: solo da acceso al JSON de borrador para
crearlo/editarlo a mano, y al guia.json ya generado para verlo.
"""
import json
from pathlib import Path

NOMBRE_BORRADOR = "guia_borrador.json"
NOMBRE_GUIA = "guia.json"


class ErrorGuia(Exception):
    pass


class GestorGuia:
    def __init__(self, carpeta_proyectos):
        self.carpeta_proyectos = Path(carpeta_proyectos)

    def leer_borrador(self, proyecto):
        return self._leer(proyecto, NOMBRE_BORRADOR)

    def guardar_borrador(self, proyecto, texto):
        try:
            json.loads(texto)
        except json.JSONDecodeError as e:
            raise ErrorGuia(f"JSON inválido: {e}") from None
        carpeta = self.carpeta_proyectos / proyecto
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / NOMBRE_BORRADOR
        temporal = destino.with_suffix(".tmp")
        temporal.write_text(texto, encoding="utf-8")
        temporal.replace(destino)

    def leer_guia(self, proyecto):
        return self._leer(proyecto, NOMBRE_GUIA)

    def _leer(self, proyecto, nombre_archivo):
        ruta = self.carpeta_proyectos / proyecto / nombre_archivo
        return ruta.read_text(encoding="utf-8") if ruta.is_file() else ""

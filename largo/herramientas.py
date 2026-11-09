"""Utilidades de ffmpeg/ffprobe y registro. (Copiadas y adaptadas de render.py; no se importan.)"""
import subprocess
import sys


class ErrorRender(Exception):
    """Falla controlada del render, con un mensaje pensado para el usuario."""


class Registro:
    def __call__(self, mensaje):
        print(mensaje, file=sys.stdout, flush=True)


class Ffmpeg:
    def __init__(self, registro):
        self.registro = registro

    def ejecutar(self, comando):
        r = subprocess.run(comando, capture_output=True, text=True)
        if r.returncode != 0:
            self.registro(r.stderr[-4000:])
            raise ErrorRender(f"Falló el comando: {' '.join(comando[:8])} ...")
        return r

    def duracion(self, ruta):
        r = self.ejecutar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "csv=p=0", str(ruta)])
        return float(r.stdout.strip())

    def dimensiones(self, ruta):
        r = self.ejecutar(["ffprobe", "-v", "error", "-select_streams", "v:0",
                           "-show_entries", "stream=width,height", "-of", "csv=p=0", str(ruta)])
        ancho, alto = r.stdout.strip().split(",")[:2]
        return int(ancho), int(alto)


def par(valor):
    """Redondea al entero par más cercano (H.264 exige dimensiones pares)."""
    return max(2, int(round(valor / 2)) * 2)

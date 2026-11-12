"""Subida de archivos a las carpetas del proyecto (imágenes, música, fuentes, voz grabada).

Mismo patrón que GeneradorVoces: escribe directo en el disco compartido con
la API (carpeta_proyectos), con escritura atómica y sin sobrescribir sin
que se pida explícitamente.
"""
import re
from pathlib import Path

NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_\-]+\.[A-Za-z0-9]+$")

# subcarpeta -> (extensiones permitidas, tamaño máximo en bytes)
CATEGORIAS = {
    "imagenes": ({".jpg", ".jpeg", ".png", ".webp"}, 25 * 1024 * 1024),
    "musica": ({".mp3", ".wav", ".m4a", ".aac"}, 50 * 1024 * 1024),
    "fuentes": ({".ttf", ".otf"}, 10 * 1024 * 1024),
    "voz": ({".mp3"}, 25 * 1024 * 1024),
}


class ErrorArchivo(Exception):
    pass


class GestorArchivos:
    def __init__(self, carpeta_proyectos):
        self.carpeta_proyectos = Path(carpeta_proyectos)

    def listar(self, proyecto, categoria):
        carpeta = self._carpeta(proyecto, categoria)
        if not carpeta.is_dir():
            return []
        return sorted(f.name for f in carpeta.iterdir() if f.is_file())

    def guardar(self, proyecto, categoria, nombre, contenido, sobrescribir=False):
        """Valida nombre, extensión y tamaño; escribe de forma atómica. Devuelve 'guardado' u 'omitido'."""
        extensiones, tamano_maximo = self._validar_categoria(categoria)
        if not NOMBRE_VALIDO.match(nombre):
            raise ErrorArchivo(f"Nombre de archivo inválido «{nombre}» (usa letras, números, _ y -)")
        if Path(nombre).suffix.lower() not in extensiones:
            raise ErrorArchivo(f"«{nombre}»: extensión no permitida en {categoria} ({', '.join(sorted(extensiones))})")
        if len(contenido) > tamano_maximo:
            raise ErrorArchivo(f"«{nombre}» pesa más de {tamano_maximo // (1024 * 1024)} MB")
        if not contenido:
            raise ErrorArchivo(f"«{nombre}» está vacío")

        carpeta = self._carpeta(proyecto, categoria)
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / nombre
        if destino.exists() and not sobrescribir:
            return "omitido"
        temporal = destino.with_suffix(destino.suffix + ".tmp")
        temporal.write_bytes(contenido)
        temporal.replace(destino)
        return "guardado"

    @staticmethod
    def _validar_categoria(categoria):
        try:
            return CATEGORIAS[categoria]
        except KeyError:
            raise ErrorArchivo(f"Categoría desconocida «{categoria}»") from None

    def _carpeta(self, proyecto, categoria):
        self._validar_categoria(categoria)
        return self.carpeta_proyectos / proyecto / categoria

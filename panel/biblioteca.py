"""Biblioteca de música compartida entre proyectos.

Vive fuera de cualquier proyecto (carpeta propia dentro de DATA_DIR, para
que la API —que monta el mismo DATA_DIR en /data— pueda hacerle /probe).
Un índice (indice.json) cuenta cuántas veces se usó cada pista.
"""
import json
from pathlib import Path

from .archivos import CATEGORIAS

EXTENSIONES_MUSICA, TAMANO_MAXIMO = CATEGORIAS["musica"]
NOMBRE_INDICE = "indice.json"


class ErrorBiblioteca(Exception):
    pass


class BibliotecaMusica:
    def __init__(self, carpeta, prefijo_contenedor="/data/musica_biblioteca"):
        self.carpeta = Path(carpeta)
        self.prefijo_contenedor = prefijo_contenedor.rstrip("/")

    def listar(self):
        if not self.carpeta.is_dir():
            return []
        indice = self._leer_indice()
        archivos = sorted(f.name for f in self.carpeta.iterdir()
                           if f.is_file() and f.name != NOMBRE_INDICE)
        return [{"nombre": a, "usos": indice.get(a, {}).get("usos", 0),
                 "ruta_contenedor": f"{self.prefijo_contenedor}/{a}"} for a in archivos]

    def guardar(self, nombre, contenido):
        """Añade (o reemplaza) una pista en la biblioteca. Validación igual que para 'musica' en archivos.py."""
        if Path(nombre).suffix.lower() not in EXTENSIONES_MUSICA:
            raise ErrorBiblioteca(f"«{nombre}»: extensión no permitida ({', '.join(sorted(EXTENSIONES_MUSICA))})")
        if not contenido:
            raise ErrorBiblioteca(f"«{nombre}» está vacío")
        if len(contenido) > TAMANO_MAXIMO:
            raise ErrorBiblioteca(f"«{nombre}» pesa más de {TAMANO_MAXIMO // (1024 * 1024)} MB")
        self.carpeta.mkdir(parents=True, exist_ok=True)
        destino = self.carpeta / nombre
        temporal = destino.with_suffix(destino.suffix + ".tmp")
        temporal.write_bytes(contenido)
        temporal.replace(destino)
        indice = self._leer_indice()
        indice.setdefault(nombre, {"usos": 0})
        self._guardar_indice(indice)

    def leer(self, nombre):
        ruta = self.carpeta / nombre
        if not ruta.is_file():
            raise ErrorBiblioteca(f"«{nombre}» no está en la biblioteca")
        return ruta.read_bytes()

    def registrar_uso(self, nombre):
        indice = self._leer_indice()
        indice.setdefault(nombre, {"usos": 0})
        indice[nombre]["usos"] += 1
        self._guardar_indice(indice)

    def _leer_indice(self):
        ruta = self.carpeta / NOMBRE_INDICE
        if not ruta.is_file():
            return {}
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _guardar_indice(self, indice):
        ruta = self.carpeta / NOMBRE_INDICE
        temporal = ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(ruta)

    def indexar_proyectos(self, carpeta_proyectos):
        """Recorre los proyectos existentes y añade a la biblioteca la música que
        usa cada `guia.json` (campo `musica.archivo`), si no está ya. Cada proyecto
        que la referencia suma un uso, exista ya en la biblioteca o se añada ahora.
        Devuelve una lista de (proyecto, pista, resultado).

        shortcut: ejecutarlo varias veces vuelve a sumar un uso por proyecto ya contado;
        pensado como acción puntual, no repetida. Si hace falta repetirla sin inflar el
        contador, habría que guardar qué proyectos ya se indexaron."""
        resultados = []
        for proyecto in sorted(Path(carpeta_proyectos).iterdir()):
            if not proyecto.is_dir():
                continue
            guia_json = proyecto / "guia.json"
            if not guia_json.is_file():
                continue
            try:
                guia = json.loads(guia_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                resultados.append((proyecto.name, None, "guia.json inválido"))
                continue
            nombre = (guia.get("musica") or {}).get("archivo")
            if not nombre:
                continue
            origen = proyecto / "musica" / nombre
            if not origen.is_file():
                resultados.append((proyecto.name, nombre, "no está en musica/ del proyecto"))
                continue
            try:
                if not (self.carpeta / nombre).is_file():
                    self.guardar(nombre, origen.read_bytes())
                    resultados.append((proyecto.name, nombre, "añadida"))
                else:
                    resultados.append((proyecto.name, nombre, "ya estaba"))
                self.registrar_uso(nombre)
            except ErrorBiblioteca as e:
                resultados.append((proyecto.name, nombre, f"error: {e}"))
        return resultados

"""Corta una grabación de voz completa en un audio por tramo, usando los silencios.

No toca la generación de voces con TTS: escribe en la misma carpeta `voz/` del
proyecto, con los mismos nombres, para que la guía y el render no cambien.
La grabación original se guarda en `<proyecto>/grabacion/` para poder volver a
detectar o recortar sin subirla otra vez.
"""
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .voces import NOMBRE_MP3, ResultadoTramo

EXTENSIONES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
TAMANO_MAXIMO = 200 * 1024 * 1024
NOMBRE_PROYECTO = re.compile(r"^[A-Za-z0-9_\-]+$")
MARGEN = 0.15  # segundos de silencio que se conservan a cada lado del corte, para que la voz no suene cortada
UMBRAL_DB, SILENCIO_MIN = -35.0, 0.4


class ErrorCorte(Exception):
    pass


@dataclass
class Propuesta:
    duracion: float
    segmentos: list  # [(inicio, fin)] en segundos
    pausas: int  # pausas encontradas dentro de la grabación
    avisos: list = field(default_factory=list)


class CortadorVoz:
    def __init__(self, carpeta_proyectos):
        self.carpeta_proyectos = Path(carpeta_proyectos)

    # ── grabación original ──
    def guardar_grabacion(self, proyecto, nombre_archivo, contenido):
        ext = Path(nombre_archivo or "").suffix.lower()
        if ext not in EXTENSIONES:
            raise ErrorCorte(f"Formato no admitido «{ext or nombre_archivo}» (usa {', '.join(sorted(EXTENSIONES))})")
        if not contenido:
            raise ErrorCorte("El archivo está vacío")
        if len(contenido) > TAMANO_MAXIMO:
            raise ErrorCorte(f"La grabación pesa más de {TAMANO_MAXIMO // (1024 * 1024)} MB")
        carpeta = self._proyecto(proyecto) / "grabacion"
        carpeta.mkdir(exist_ok=True)
        destino = carpeta / f"original{ext}"
        temporal = destino.with_name(destino.name + ".tmp")
        temporal.write_bytes(contenido)
        temporal.replace(destino)
        for viejo in carpeta.glob("original.*"):  # solo se guarda una grabación por proyecto
            if viejo != destino:
                viejo.unlink()
        return destino

    def grabacion(self, proyecto):
        carpeta = self._proyecto(proyecto) / "grabacion"
        archivos = [p for p in carpeta.glob("original.*") if p.suffix.lower() in EXTENSIONES] if carpeta.is_dir() else []
        return archivos[0] if archivos else None

    # ── detección ──
    def proponer(self, proyecto, tramos, umbral_db=UMBRAL_DB, silencio_min=SILENCIO_MIN):
        """Elige las `tramos - 1` pausas más largas como cortes."""
        ruta = self._grabacion_obligatoria(proyecto)
        if tramos < 1:
            raise ErrorCorte("Indica cuántos audios quieres (al menos 1)")
        duracion = _duracion(ruta)
        silencios = _silencios(ruta, umbral_db, silencio_min, duracion)
        return dividir(duracion, silencios, tramos)

    # ── corte ──
    def cortar(self, proyecto, segmentos, sobrescribir=False):
        """segmentos: [(nombre.mp3, inicio, fin)]. Entrega un ResultadoTramo por segmento."""
        ruta = self._grabacion_obligatoria(proyecto)
        duracion = _duracion(ruta)
        destino = self._proyecto(proyecto) / "voz"
        destino.mkdir(exist_ok=True)
        for nombre, ini, fin in segmentos:
            if not NOMBRE_MP3.match(nombre):
                yield ResultadoTramo(nombre, "error", "nombre inválido (usa letras, números, _ y -, y .mp3)")
                continue
            if not 0 <= ini < fin <= duracion + 0.05:
                yield ResultadoTramo(nombre, "error", f"tiempos inválidos ({ini:.2f}–{fin:.2f} s; la grabación dura {duracion:.2f} s)")
                continue
            salida = destino / nombre
            if salida.exists() and not sobrescribir:
                yield ResultadoTramo(nombre, "omitido")
                continue
            temporal = salida.with_name(salida.stem + ".tmp.mp3")
            largo = fin - ini
            r = subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(ruta),
                 "-ss", f"{ini:.3f}", "-to", f"{fin:.3f}", "-vn",
                 # fundidos de milisegundos: evitan el «clic» del corte
                 "-af", f"afade=t=in:d=0.01,afade=t=out:st={max(0, largo - 0.03):.3f}:d=0.03",
                 "-c:a", "libmp3lame", "-q:a", "2", "-ar", "44100", str(temporal)],
                capture_output=True, text=True)
            if r.returncode != 0:
                temporal.unlink(missing_ok=True)
                yield ResultadoTramo(nombre, "error", r.stderr.strip()[-300:] or "ffmpeg falló")
                continue
            temporal.replace(salida)
            yield ResultadoTramo(nombre, "generado")

    def _proyecto(self, proyecto):
        carpeta = self.carpeta_proyectos / proyecto
        if not NOMBRE_PROYECTO.match(proyecto) or not carpeta.is_dir():
            raise ErrorCorte(f"No existe el proyecto «{proyecto}»")
        return carpeta

    def _grabacion_obligatoria(self, proyecto):
        ruta = self.grabacion(proyecto)
        if not ruta:
            raise ErrorCorte("Primero sube la grabación")
        return ruta


def dividir(duracion, silencios, tramos):
    """Lógica pura: [(ini, fin)] de silencios -> Propuesta con `tramos` segmentos (o menos si faltan pausas)."""
    borde = 0.05
    inicio = next((f for i, f in silencios if i <= borde), 0.0)  # silencio al principio
    final = next((i for i, f in silencios if f >= duracion - borde), duracion)  # silencio al final
    inicio, final = max(0.0, inicio - MARGEN), min(duracion, final + MARGEN)
    interiores = [(i, f) for i, f in silencios if i > borde and f < duracion - borde]
    elegidos = sorted(sorted(interiores, key=lambda s: s[1] - s[0], reverse=True)[:tramos - 1])
    avisos = []
    if len(elegidos) < tramos - 1:
        avisos.append(f"Solo encontré {len(interiores)} pausa(s) y necesito {tramos - 1}. "
                      "Baja el silencio mínimo, sube el umbral o ajusta los tiempos a mano.")
    segmentos, ini = [], inicio
    for s_ini, s_fin in elegidos:
        mitad = (s_ini + s_fin) / 2
        segmentos.append((ini, min(s_ini + MARGEN, mitad)))
        ini = max(s_fin - MARGEN, mitad)
    segmentos.append((ini, final))
    return Propuesta(duracion, [(round(a, 2), round(b, 2)) for a, b in segmentos], len(interiores), avisos)


def _duracion(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise ErrorCorte("No pude leer la grabación: ¿es un archivo de audio válido?") from None


def _silencios(ruta, umbral_db, silencio_min, duracion):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-vn",
                        "-af", f"silencedetect=noise={umbral_db}dB:d={silencio_min}", "-f", "null", "-"],
                       capture_output=True, text=True)
    inicios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    fines = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    fines += [duracion] * (len(inicios) - len(fines))  # silencio que llega hasta el final
    return [(max(0.0, i), f) for i, f in zip(inicios, fines)]


if __name__ == "__main__":  # autocomprobación de la lógica de corte
    p = dividir(10.0, [(0.0, 0.5), (2.0, 2.3), (4.0, 5.0), (7.0, 7.6), (9.5, 10.0)], 3)
    assert p.segmentos == [(0.35, 4.15), (4.85, 7.15), (7.45, 9.65)], p.segmentos
    p = dividir(10.0, [(4.0, 5.0)], 3)
    assert len(p.segmentos) == 2 and p.avisos
    assert dividir(5.0, [], 1).segmentos == [(0.0, 5.0)]
    print("dividir OK")

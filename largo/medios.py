"""Fuentes visuales de una escena (imagen o clip). Cada una aporta sus entradas de ffmpeg y su cadena de
filtros; la escena las junta todas en un solo comando."""
import os
from abc import ABC, abstractmethod

from .herramientas import par

PRESET = "veryfast"
CRF = "19"


def codificacion(fps):
    return ["-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-pix_fmt", "yuv420p", "-r", str(fps), "-an"]


class Efectos:
    """Movimiento de cámara para las imágenes (zoompan)."""

    @staticmethod
    def zoompan(efecto, n, ancho, alto, fps):
        cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        # ease-in-out (smoothstep) en vez de on/n lineal: el movimiento arranca y frena suave, no en seco
        ease = f"(3*pow(on/{n},2)-2*pow(on/{n},3))"
        if efecto == "deriva":  # ligera rotación de cámara, sin zoom ni paneo (look "cámara en mano")
            dur = n / fps
            t_ease = f"(3*pow(t/{dur:.4f},2)-2*pow(t/{dur:.4f},3))"
            angulo = f"(-1+2*{t_ease})*0.015"  # ±0.86° a lo largo de la escena
            return (f"zoompan=z='1.06':x='{cx}':y='{cy}':d={n}:s={ancho}x{alto}:fps={fps},"
                    f"rotate=a='{angulo}':ow=iw:oh=ih:c=black")
        z, x, y = {
            "zoom_in_lento": (f"1+0.08*{ease}", cx, cy),
            "zoom_in": (f"1+0.15*{ease}", cx, cy),
            "zoom_out": (f"1.15-0.15*{ease}", cx, cy),
            "zoom_out_lento": (f"1.08-0.08*{ease}", cx, cy),
            "paneo_der": ("1.15", f"(iw-iw/zoom)*{ease}", cy),
            "paneo_izq": ("1.15", f"(iw-iw/zoom)*(1-{ease})", cy),
            "paneo_arriba": ("1.15", cx, f"(ih-ih/zoom)*(1-{ease})"),
            "paneo_abajo": ("1.15", cx, f"(ih-ih/zoom)*{ease}"),
            "paneo_rapido": ("1.25", f"(iw-iw/zoom)*{ease}", cy),
        }.get(efecto, ("1", "0", "0"))
        return f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={ancho}x{alto}:fps={fps}"


class Segmento(ABC):
    num_entradas = 1

    def __init__(self, medio, carpeta, formato, ffmpeg, registro):
        self.medio, self.formato, self.ffmpeg, self.registro = medio, formato, ffmpeg, registro
        self.ruta = os.path.join(carpeta, medio.archivo)

    def preparar(self):
        """Consulta lo que haga falta del archivo antes de armar el comando."""
        return self

    @abstractmethod
    def entradas(self, n_frames):
        """Argumentos de entrada de ffmpeg (`-i ...`) de este medio."""

    @abstractmethod
    def filtro(self, primera, n_frames, etiqueta):
        """Cadena de filtros que termina en [etiqueta] con exactamente `n_frames` frames."""

    @staticmethod
    def _exacto(n_frames, relleno=1):
        # relleno con el último frame y corte exacto, para que la suma de frames de la escena sea la planeada
        return f"tpad=stop_mode=clone:stop_duration={relleno:.4f},trim=end_frame={n_frames},setpts=PTS-STARTPTS"


class SegmentoImagen(Segmento):
    ESCALA_BASE = 1.5  # se trabaja a 1.5x para que el zoom no se vea a saltos

    def preparar(self):
        iw, ih = self.ffmpeg.dimensiones(self.ruta)
        e = self.medio.encuadre
        if e == "auto":
            # imágenes mucho más altas que el cuadro (p. ej. verticales) se muestran completas sobre fondo borroso
            e = "ajustar" if iw / ih < (self.formato.ancho / self.formato.alto) * 0.8 else "cubrir"
        self.encuadre, self.iw, self.ih = e, iw, ih
        self.num_entradas = 1 if e == "cubrir" else 2
        return self

    def entradas(self, n_frames):
        f = self.formato
        if self.encuadre == "cubrir":
            return ["-i", self.ruta]
        return ["-i", self.ruta, "-loop", "1", "-framerate", str(f.fps),
                "-t", f"{n_frames / f.fps:.4f}", "-i", self.ruta]

    def filtro(self, primera, n_frames, etiqueta):
        f, efecto = self.formato, self.medio.efecto
        if self.encuadre == "cubrir":
            bw, bh = par(f.ancho * self.ESCALA_BASE), par(f.alto * self.ESCALA_BASE)
            return (f"[{primera}:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                    f"{Efectos.zoompan(efecto, n_frames, f.ancho, f.alto, f.fps)},setsar=1,format=yuv420p,"
                    f"{self._exacto(n_frames)}[{etiqueta}]")
        k = min(f.ancho / self.iw, f.alto / self.ih)
        fw, fh = par(self.iw * k), par(self.ih * k)
        bw, bh = par(fw * self.ESCALA_BASE), par(fh * self.ESCALA_BASE)
        return (f"[{primera + 1}:v]scale={f.ancho // 8}:{f.alto // 8}:force_original_aspect_ratio=increase,"
                f"crop={f.ancho // 8}:{f.alto // 8},boxblur=4:2,scale={f.ancho}:{f.alto},"
                f"eq=brightness=-0.15[fondo_{etiqueta}];"
                f"[{primera}:v]scale={bw}:{bh},{Efectos.zoompan(efecto, n_frames, fw, fh, f.fps)}[frente_{etiqueta}];"
                f"[fondo_{etiqueta}][frente_{etiqueta}]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p,"
                f"{self._exacto(n_frames)}[{etiqueta}]")


class SegmentoClip(Segmento):
    def preparar(self):
        self.ajuste = self.medio.ajuste
        self._disponible = self.ffmpeg.duracion(self.ruta) - self.medio.inicio
        return self

    def entradas(self, n_frames):
        necesario = n_frames / self.formato.fps
        if self.ajuste == "recortar" and self._disponible + 0.05 < necesario:
            self.registro(f"   ⚠ {self.medio.archivo} dura {self._disponible:.1f}s desde el segundo "
                          f"{self.medio.inicio:g} y se necesitan {necesario:.1f}s: se congela el último frame")
            self.ajuste = "congelar"
        previo = ["-stream_loop", "-1"] if self.ajuste == "bucle" else []
        return previo + ["-ss", f"{self.medio.inicio:.3f}", "-i", self.ruta]

    def filtro(self, primera, n_frames, etiqueta):
        f = self.formato
        relleno = n_frames / f.fps if self.ajuste == "congelar" else 1
        return (f"[{primera}:v]scale={f.ancho}:{f.alto}:force_original_aspect_ratio=increase,"
                f"crop={f.ancho}:{f.alto},setsar=1,fps={f.fps},format=yuv420p,"
                f"{self._exacto(n_frames, relleno)}[{etiqueta}]")


def crear_segmento(medio, carpeta, formato, ffmpeg, registro):
    clase = SegmentoImagen if medio.tipo == "imagen" else SegmentoClip
    return clase(medio, carpeta, formato, ffmpeg, registro).preparar()

"""Renderiza una escena en UNA sola pasada de ffmpeg: medios en secuencia + texto, cortada en piezas.

Cada escena se divide en cabeza (se mezcla con la escena anterior), cuerpo (va tal cual al video final)
y cola (se mezcla con la escena siguiente). Así las transiciones solo recodifican unos pocos frames.
"""
import os
from dataclasses import dataclass

from .medios import codificacion, crear_segmento


@dataclass
class PiezasEscena:
    cabeza: str | None
    cuerpo: str
    cola: str | None


class RenderizadorEscena:
    def __init__(self, guia, carpeta, tmp, ffmpeg, registro, generador_texto):
        self.guia, self.carpeta, self.tmp = guia, carpeta, tmp
        self.ffmpeg, self.registro, self.texto = ffmpeg, registro, generador_texto

    def renderizar(self, plan, indice, es_ultima):
        f = self.guia.formato
        entradas, filtros, etiquetas = self._medios(plan)
        textos = self.texto.filtros(plan)
        filtros.append(f"{''.join(etiquetas)}concat=n={len(etiquetas)}:v=1:a=0[c]" if len(etiquetas) > 1
                       else f"{etiquetas[0]}null[c]")
        filtros.append("[c]" + (",".join(textos) if textos else "null") + "[t]")

        # (nombre, primer frame, frame final exclusivo); de la última escena no hace falta la cola
        h, c = plan.td_prev_frames, plan.frames_cuerpo
        cortes = [("cabeza", 0, h)] if h else []
        cortes.append(("cuerpo", h, h + c))
        if not es_ultima:
            cortes.append(("cola", h + c, plan.n))

        base = os.path.join(self.tmp, f"escena_{indice:03d}")
        rutas = {nombre: f"{base}_{nombre}.mp4" for nombre, _, _ in cortes}
        if len(cortes) == 1:
            filtros.append(f"[t]trim=end_frame={cortes[0][2]},setpts=PTS-STARTPTS[o0]")
        else:
            filtros.append(f"[t]split={len(cortes)}" + "".join(f"[s{k}]" for k in range(len(cortes))))
            filtros += [f"[s{k}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[o{k}]"
                        for k, (_, a, b) in enumerate(cortes)]
        salidas = []
        for k, (nombre, _, _) in enumerate(cortes):
            salidas += ["-map", f"[o{k}]"] + codificacion(f.fps) + [rutas[nombre]]
        self.ffmpeg.ejecutar(["ffmpeg", "-y"] + entradas + ["-filter_complex", ";".join(filtros)] + salidas)
        return PiezasEscena(rutas.get("cabeza"), rutas["cuerpo"], rutas.get("cola"))

    def _medios(self, plan):
        """Entradas, filtros y etiquetas de los medios de la escena (o un fondo negro si no hay)."""
        f = self.guia.formato
        if not plan.escena.medios:
            return (["-f", "lavfi", "-i", f"color=c=black:s={f.ancho}x{f.alto}:r={f.fps}:d={plan.dur + 1:.4f}"],
                    [f"[0:v]trim=end_frame={plan.n},setpts=PTS-STARTPTS,format=yuv420p[m0]"], ["[m0]"])
        entradas, filtros, etiquetas, siguiente = [], [], [], 0
        for k, (medio, n) in enumerate(zip(plan.escena.medios, plan.frames_medios)):
            seg = crear_segmento(medio, self.carpeta, f, self.ffmpeg, self.registro)
            entradas += seg.entradas(n)
            filtros.append(seg.filtro(siguiente, n, f"m{k}"))
            siguiente += seg.num_entradas
            etiquetas.append(f"[m{k}]")
        return entradas, filtros, etiquetas

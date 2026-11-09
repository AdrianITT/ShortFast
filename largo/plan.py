"""Plan de tiempos: cuánto dura cada escena y cada medio, según la voz."""
import os
from dataclasses import dataclass, field

from .guia import Escena


@dataclass
class PlanEscena:
    escena: Escena
    voz: str | None
    voz_dur: float
    td_frames: int      # frames de la transición de salida
    n: int              # frames de la escena (incluye la transición, para no comerse contenido)
    dur: float
    td_prev_frames: int = 0   # frames de la transición de entrada (= salida de la escena anterior)
    inicio: float = 0.0
    frames_medios: list = field(default_factory=list)

    @property
    def td(self):
        return self.td_frames / (self.n / self.dur)

    @property
    def frames_cuerpo(self):
        """Frames que la escena aporta sola, sin mezclarse con sus vecinas."""
        return self.n - self.td_prev_frames - self.td_frames


class Planificador:
    def __init__(self, guia, carpeta, ffmpeg):
        self.guia, self.carpeta, self.ffmpeg = guia, carpeta, ffmpeg
        self.fps = guia.formato.fps

    def frames(self, segundos):
        return max(1, round(segundos * self.fps))

    def _transicion_frames(self, tr):
        return 1 if tr.tipo == "corte" else self.frames(tr.duracion)

    def construir(self):
        g, plan = self.guia, []
        for e in g.escenas:
            voz = os.path.join(self.carpeta, e.voz) if e.voz else None
            vd = self.ffmpeg.duracion(voz) if voz else 0
            td = self._transicion_frames(e.transicion_salida)
            base = e.duracion if e.duracion else g.voz_retraso + vd + g.pausa_entre_escenas
            n = self.frames(base + td / self.fps)
            p = PlanEscena(escena=e, voz=voz, voz_dur=vd, td_frames=td, n=n, dur=n / self.fps)
            p.frames_medios = self._repartir(e, n)
            plan.append(p)
        for anterior, p in zip(plan, plan[1:]):
            p.td_prev_frames = anterior.td_frames
        t = 0.0
        for p in plan:
            if p.frames_cuerpo < 1:
                raise ValueError(f"Escena {p.escena.id}: dura {p.dur:.1f}s y es demasiado corta para sus "
                                 f"transiciones de entrada y salida")
            p.inicio = t
            t += p.dur - p.td
        return plan, t

    def _repartir(self, escena, n):
        """Frames de cada medio. Los que tienen `duracion` la respetan; el resto se reparte en partes
        iguales; si todos tienen duración, el último absorbe la diferencia."""
        medios = escena.medios
        if not medios:
            return []
        fijos = [self.frames(m.duracion) if m.duracion else None for m in medios]
        libres = [i for i, f in enumerate(fijos) if f is None]
        suma_fijos = sum(f for f in fijos if f)
        if libres:
            resto = n - suma_fijos
            if resto < len(libres):
                raise ValueError(f"Escena {escena.id}: los medios con duración fija ({suma_fijos / self.fps:.1f}s) "
                                 f"no dejan tiempo a los demás (la escena dura {n / self.fps:.1f}s)")
            base, extra = divmod(resto, len(libres))
            for k, i in enumerate(libres):
                fijos[i] = base + (1 if k < extra else 0)
        else:
            fijos[-1] = n - sum(fijos[:-1])
            if fijos[-1] < 1:
                raise ValueError(f"Escena {escena.id}: los medios pasan de lo que dura la escena ({n / self.fps:.1f}s)")
        return fijos

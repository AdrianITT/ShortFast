"""Unión de las escenas sin recodificar el video completo.

video = cuerpo₁ + puente₁₂ + cuerpo₂ + puente₂₃ + ... + cuerpoₙ
Cada puente mezcla (xfade) la cola de una escena con la cabeza de la siguiente: solo unos cuantos frames.
Las piezas se pegan con `-c copy`, de modo que el costo no crece con la duración total.
"""
import os

XFADE = {"fade": "fade", "fadeblack": "fadeblack", "fadewhite": "fadewhite", "dissolve": "dissolve"}


class Ensamblador:
    def __init__(self, ffmpeg, fps, registro, codificacion, conservar_tmp=False):
        self.ffmpeg, self.fps, self.registro = ffmpeg, fps, registro
        self.codificacion = codificacion
        self.conservar_tmp = conservar_tmp

    def unir(self, piezas, plan, tmp):
        partes, temporales = [], []
        for i, (pz, p) in enumerate(zip(piezas, plan)):
            partes.append(pz.cuerpo)
            temporales.append(pz.cuerpo)
            if i + 1 < len(piezas):
                puente = self._puente(pz, piezas[i + 1], p, os.path.join(tmp, f"puente_{i + 1:03d}.mp4"))
                partes.append(puente)
                temporales += [puente, pz.cola, piezas[i + 1].cabeza]
        self.registro(f"🔗 Uniendo {len(piezas)} escenas ({len(piezas) - 1} transiciones)...")
        video = os.path.join(tmp, "video.mp4")
        lista = os.path.join(tmp, "partes.txt")
        with open(lista, "w", encoding="utf-8") as f:
            f.writelines("file '{}'\n".format(r.replace("'", "'\\''")) for r in partes)
        self.ffmpeg.ejecutar(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", video])
        if not self.conservar_tmp:
            for r in set(temporales):
                if r and os.path.exists(r):
                    os.remove(r)
        return video

    def _puente(self, saliente, entrante, plan_saliente, destino):
        tipo = plan_saliente.escena.transicion_salida.tipo
        if tipo == "corte":  # corte duro: el único frame de transición es el primero de la escena que entra
            return entrante.cabeza
        d = plan_saliente.td_frames / self.fps
        norm = f"settb=AVTB,fps={self.fps},format=yuv420p,setsar=1"
        fc = (f"[0:v]{norm}[a];[1:v]{norm}[b];"
              f"[a][b]xfade=transition={XFADE[tipo]}:duration={d:.4f}:offset=0[v]")
        self.ffmpeg.ejecutar(["ffmpeg", "-y", "-i", saliente.cola, "-i", entrante.cabeza,
                              "-filter_complex", fc, "-map", "[v]"] + self.codificacion + [destino])
        return destino

"""Mezcla de audio: voces en su lugar + música con volumen por escena."""
import os


class MezclaAudio:
    def __init__(self, guia, carpeta, ffmpeg):
        self.guia, self.carpeta, self.ffmpeg = guia, carpeta, ffmpeg

    ESCENAS_POR_VENTANA = 20  # ffmpeg rechaza expresiones con cientos de `if` anidados

    @staticmethod
    def _valor(k, inicios, vols, rampa):
        if k == 0:
            return f"{vols[0]}"
        d = vols[k] - vols[k - 1]
        return f"{vols[k - 1]}+({d:.3f})*min(1,(t-{inicios[k]:.3f})/{rampa})"

    @classmethod
    def _expr_ventana(cls, desde, hasta, inicios, vols, rampa=0.5):
        """Curva de volumen de las escenas [desde, hasta), con tiempos absolutos."""
        e = cls._valor(hasta - 1, inicios, vols, rampa)
        for k in range(hasta - 2, desde - 1, -1):
            e = f"if(lt(t,{inicios[k + 1]:.3f}),{cls._valor(k, inicios, vols, rampa)},{e})"
        return e

    @classmethod
    def filtros_volumen(cls, inicios, vols, total):
        """Un filtro `volume` por ventana de escenas; cada uno solo actúa dentro de su ventana."""
        filtros, n = [], len(vols)
        for desde in range(0, n, cls.ESCENAS_POR_VENTANA):
            hasta = min(desde + cls.ESCENAS_POR_VENTANA, n)
            t0 = inicios[desde] if desde else 0
            t1 = inicios[hasta] if hasta < n else total + 1
            filtros.append(f"volume='{cls._expr_ventana(desde, hasta, inicios, vols)}':eval=frame:"
                           f"enable='between(t,{t0:.3f},{t1:.3f})'")
        return ",".join(filtros)

    def mezclar(self, plan, total, tmp):
        g = self.guia
        voces = [(p.voz, p.inicio + g.voz_retraso) for p in plan if p.voz]
        musica = os.path.join(self.carpeta, g.musica["archivo"])
        fade_out = g.musica.get("fade_out", 2)
        factor = g.musica.get("volumen", 1.0)
        vols = [round(p.escena.musica_vol * factor, 4) for p in plan]
        inicios = [p.inicio for p in plan]

        cmd = ["ffmpeg", "-y"]
        for v, _ in voces:
            cmd += ["-i", v]
        cmd += ["-stream_loop", "-1", "-i", musica]
        fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
        fc, etiquetas = [], ""
        for i, (_, ini) in enumerate(voces):
            fc.append(f"[{i}:a]{fmt},adelay={int(ini * 1000)}:all=1[a{i}]")
            etiquetas += f"[a{i}]"
        fc.append(f"{etiquetas}amix=inputs={len(voces)}:normalize=0:duration=longest[voz]")
        m = len(voces)
        fc.append(f"[{m}:a]{fmt},atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
                  f"{self.filtros_volumen(inicios, vols, total)},"
                  f"afade=t=out:st={max(0, total - fade_out):.3f}:d={fade_out}[mus]")
        fc.append(f"[voz][mus]amix=inputs=2:normalize=0:duration=longest,"
                  f"atrim=0:{total:.3f},alimiter=limit=0.95[out]")
        salida = os.path.join(tmp, "audio.wav")
        self.ffmpeg.ejecutar(cmd + ["-filter_complex", ";".join(fc), "-map", "[out]",
                                    "-t", f"{total:.3f}", "-c:a", "pcm_s16le", salida])
        return salida

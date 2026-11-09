"""Orquestador del render de un video largo."""
import os
import resource
import shutil
import time

from .audio import MezclaAudio
from .ensamblado import Ensamblador
from .medios import codificacion
from .escena import RenderizadorEscena
from .guia import Guia
from .herramientas import ErrorRender, Ffmpeg, Registro
from .plan import Planificador
from .texto import GeneradorTexto


class RenderLargo:
    def __init__(self, nombre, carpeta_proyectos, carpeta_salida, conservar_tmp=False, reanudar=False, registro=None):
        self.nombre = nombre
        self.carpeta = os.path.join(carpeta_proyectos, nombre)
        self.salida = carpeta_salida
        self.tmp = os.path.join(carpeta_salida, f"tmp_{nombre}")
        self.conservar_tmp = conservar_tmp
        self.reanudar = reanudar
        self.registro = registro or Registro()
        self.ffmpeg = Ffmpeg(self.registro)

    def ejecutar(self):
        log, t_ini = self.registro, time.time()
        guia = Guia.cargar(os.path.join(self.carpeta, "guia.json"))
        faltan = guia.archivos_faltantes(self.carpeta)
        if faltan:
            raise ErrorRender("Faltan archivos:\n" + "\n".join(f"   - {r}" for r in faltan))
        os.makedirs(self.tmp, exist_ok=True)
        f = guia.formato

        log("📏 Midiendo audios...")
        plan, total = Planificador(guia, self.carpeta, self.ffmpeg).construir()
        log(f"{len(plan)} escenas · {f.ancho}x{f.alto}@{f.fps} · TOTAL: {total:.1f}s ({total / 60:.1f} min)")
        if total > guia.duracion_max:
            log(f"⚠️  Pasa de duracion_max ({guia.duracion_max}s)")

        video = os.path.join(self.tmp, "video.mp4")
        tiempos, t_fase = {}, time.time()
        if self.reanudar and os.path.isfile(video):
            log("♻️  Reanudando: se reutiliza el video ya unido de la ejecución anterior")
        else:
            escenas = RenderizadorEscena(guia, self.carpeta, self.tmp, self.ffmpeg, log,
                                         GeneradorTexto(guia, self.carpeta, self.tmp))
            piezas = []
            for i, p in enumerate(plan, 1):
                log(f"🎬 Escena {i}/{len(plan)} ({p.dur:.1f}s)...")
                piezas.append(escenas.renderizar(p, i, es_ultima=i == len(plan)))
            tiempos["escenas"] = time.time() - t_fase
            t_fase = time.time()
            video = Ensamblador(self.ffmpeg, f.fps, log, codificacion(f.fps), self.conservar_tmp).unir(piezas, plan, self.tmp)
            esperado = sum(p.frames_cuerpo for p in plan) + sum(p.td_frames for p in plan[:-1])
            real = self.ffmpeg.duracion(video) * f.fps
            if abs(real - esperado) > 1.5:
                log(f"⚠️  El video unido tiene {real:.0f} frames y se esperaban {esperado}")
        tiempos["unión"] = time.time() - t_fase
        t_fase = time.time()
        log("🎵 Mezclando voz y música...")
        audio = MezclaAudio(guia, self.carpeta, self.ffmpeg).mezclar(plan, total, self.tmp)

        tiempos["audio"] = time.time() - t_fase
        log("📦 Exportando...")
        final = os.path.join(self.salida, f"{self.nombre}.mp4")
        self.ffmpeg.ejecutar(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a",
                              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                              "-movflags", "+faststart", final])

        pico_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
        tmp_mb = self._tamano_mb(self.tmp)
        if not self.conservar_tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
        log(f"\n✅ Listo: {final}")
        log(f"   Duración: {self.ffmpeg.duracion(final):.1f}s | Tardó: {(time.time() - t_ini) / 60:.1f} min | "
            f"Archivo: {os.path.getsize(final) / 1e6:.0f} MB")
        log("   Tiempo por fase: " + " · ".join(f"{k} {v / 60:.1f} min" for k, v in tiempos.items()))
        log(f"   Memoria máxima de un proceso ffmpeg: {pico_mb:.0f} MB | Temporales: {tmp_mb:.0f} MB"
            + (" (conservados)" if self.conservar_tmp else " (borrados)"))

    @staticmethod
    def _tamano_mb(carpeta):
        return sum(os.path.getsize(os.path.join(d, a)) for d, _, archivos in os.walk(carpeta) for a in archivos) / 1e6

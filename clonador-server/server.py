"""Clonación de voz local: Supertonic genera el texto y OpenVoice v2 le pone el timbre de una grabación de referencia.

API compatible con el panel (/v1/audio/speech, /v1/audio/voices) más la gestión de voces (/v1/voces).
"""
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import soundfile as sf
import torch
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from openvoice.api import OpenVoiceBaseClass, ToneColorConverter
from pydantic import BaseModel

CLAVE = os.environ.get("API_KEY", "")
SUPERTONIC_URL = os.environ.get("SUPERTONIC_URL", "http://host.docker.internal:5200").rstrip("/")
CLAVE_SUPERTONIC = os.environ.get("SUPERTONIC_API_KEY", CLAVE)  # misma clave que este servicio salvo que se indique otra
DATOS = Path(os.environ.get("CARPETA_DATOS", "/datos"))
MODELO = Path(os.environ.get("CARPETA_MODELO", "/modelo/converter"))
TAU = float(os.environ.get("TAU", "0.3"))  # más bajo = más parecido a la referencia, más alto = más natural
VOCES, BASES = DATOS / "voces", DATOS / "bases"
NOMBRE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
VOZ_BASE = re.compile(r"^[FM][1-5]$")  # voces de Supertonic
DURACION_MIN, DURACION_MAX = 10, 300  # segundos de voz útil (sin silencios) / de archivo subido
TROZO = 8  # segundos por trozo para calcular la huella
TEXTO_BASE = ("Hoy quiero contarte una historia sobre la paciencia. Hace muchos años, un hombre sabio vivía en las "
              "montañas y cada mañana caminaba hasta el río. Allí observaba el agua durante horas, sin prisa y sin "
              "miedo. Decía que el río le enseñaba que todo pasa y que la calma es la mayor de las fuerzas.")
TEXTO_MUESTRA = "Hola, esta es una muestra de mi voz. ¿Qué te parece cómo suena?"


class Conversor(ToneColorConverter):
    """ToneColorConverter sin marca de agua: el original pasa `enable_watermark` a la clase base, que no lo acepta."""

    def __init__(self, config, device):
        OpenVoiceBaseClass.__init__(self, config, device=device)
        self.watermark_model = None  # add_watermark devuelve el audio tal cual
        self.version = getattr(self.hps, "_version_", "v1")


def autorizar(authorization: str = Header("")):
    # Sin API_KEY el servicio queda abierto: úsalo solo en tu red local.
    if CLAVE and not secrets.compare_digest(authorization, f"Bearer {CLAVE}"):
        raise HTTPException(401, "Invalid API key")


torch.set_num_threads(os.cpu_count() or 4)
conversor = Conversor(str(MODELO / "config.json"), device="cpu")
conversor.load_ckpt(str(MODELO / "checkpoint.pth"))
TASA = conversor.hps.data.sampling_rate
VOCES.mkdir(parents=True, exist_ok=True)
BASES.mkdir(parents=True, exist_ok=True)
app = FastAPI()
protegido = [Depends(autorizar)]  # /health queda abierto para monitoreo
_candado = threading.Lock()  # una conversión a la vez: el CPU es pequeño


class Peticion(BaseModel):
    input: str
    voice: str
    speed: float = 1.0
    model: str = "clonador"
    response_format: str = "mp3"


def ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True)
    if r.returncode:
        raise HTTPException(400, f"ffmpeg no pudo procesar el audio: {r.stderr.strip()[:200]}")


def supertonic(texto, voz, velocidad, destino):
    """Pide el audio a Supertonic y lo deja como wav mono a la frecuencia del conversor."""
    cuerpo = json.dumps({"input": texto, "voice": voz, "speed": velocidad}).encode()
    cabeceras = {"Content-Type": "application/json"}
    if CLAVE_SUPERTONIC:
        cabeceras["Authorization"] = f"Bearer {CLAVE_SUPERTONIC}"
    peticion = urllib.request.Request(SUPERTONIC_URL + "/v1/audio/speech", data=cuerpo, method="POST",
                                      headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=600) as r:
            mp3 = r.read()
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"Supertonic respondió [{e.code}]: {e.read().decode('utf-8', 'replace')[:200]}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise HTTPException(502, f"No se pudo conectar con Supertonic en {SUPERTONIC_URL}: {getattr(e, 'reason', e)}") from None
    origen = destino.with_suffix(".mp3")
    origen.write_bytes(mp3)
    ffmpeg("-i", str(origen), "-ac", "1", "-ar", str(TASA), str(destino))


def huella_de(wav, carpeta):
    """Huella de voz (media de trozos de TROZO s; los trozos de menos de 2 s se descartan)."""
    ffmpeg("-i", str(wav), "-f", "segment", "-segment_time", str(TROZO), str(carpeta / "trozo_%03d.wav"))
    trozos = [str(t) for t in sorted(carpeta.glob("trozo_*.wav")) if sf.info(str(t)).duration >= 2]
    return conversor.extract_se(trozos)


def huella_base(voz):
    """Huella de una voz de Supertonic; se calcula una vez y queda guardada."""
    ruta = BASES / f"{voz}.pth"
    if not ruta.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "base.wav"
            supertonic(TEXTO_BASE, voz, 1.0, wav)
            torch.save(huella_de(wav, Path(tmp)), ruta)
    return torch.load(ruta)


def meta(nombre):
    ruta = VOCES / nombre / "meta.json"
    if not NOMBRE.match(nombre) or not ruta.is_file():  # el nombre valida antes de tocar el disco
        raise HTTPException(404, f"La voz «{nombre}» no existe")
    return json.loads(ruta.read_text(encoding="utf-8"))


def hablar_con(nombre, texto, velocidad):
    """mp3 del texto con la voz clonada `nombre`."""
    datos = meta(nombre)
    with _candado, tempfile.TemporaryDirectory() as tmp:
        base, clon, mp3 = Path(tmp) / "base.wav", Path(tmp) / "clon.wav", Path(tmp) / "clon.mp3"
        supertonic(texto, datos["voz_base"], velocidad, base)
        conversor.convert(str(base), huella_base(datos["voz_base"]), torch.load(VOCES / nombre / "huella.pth"),
                          output_path=str(clon), tau=datos.get("tau", TAU))
        ffmpeg("-i", str(clon), "-c:a", "libmp3lame", "-q:a", "2", str(mp3))
        return mp3.read_bytes()


@app.get("/health")
def salud():
    return {"ok": True, "voces": len(list(VOCES.glob("*/meta.json"))), "tau": TAU, "supertonic": SUPERTONIC_URL}


@app.get("/v1/audio/voices", dependencies=protegido)
def voces_tts():
    return {"voices": [{"id": p.parent.name} for p in sorted(VOCES.glob("*/meta.json"))]}


@app.post("/v1/audio/speech", dependencies=protegido)
def hablar(p: Peticion):
    if not p.input.strip():
        raise HTTPException(400, "input vacío")
    if not 0.5 <= p.speed <= 2.0:
        raise HTTPException(400, "speed debe estar entre 0.5 y 2.0")
    return Response(hablar_con(p.voice, p.input, p.speed), media_type="audio/mpeg")


@app.get("/v1/voces", dependencies=protegido)
def listar():
    return {"voces": [json.loads(p.read_text(encoding="utf-8")) for p in sorted(VOCES.glob("*/meta.json"))]}


@app.post("/v1/voces", dependencies=protegido)
async def crear(request: Request, nombre: str, voz_base: str = "M3"):
    """Crea una voz a partir del audio enviado como cuerpo de la petición (cualquier formato que lea ffmpeg)."""
    if not NOMBRE.match(nombre):
        raise HTTPException(400, "Nombre inválido: 2–40 caracteres, minúsculas, números, _ y -")
    if not VOZ_BASE.match(voz_base):
        raise HTTPException(400, "voz_base debe ser una voz de Supertonic: F1–F5 o M1–M5")
    if (VOCES / nombre).exists():
        raise HTTPException(409, f"Ya existe una voz llamada «{nombre}»")
    audio = await request.body()
    if not audio:
        raise HTTPException(400, "No llegó ningún audio")
    with _candado, tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "subido").write_bytes(audio)
        ffmpeg("-t", str(DURACION_MAX), "-i", str(tmp / "subido"), "-ac", "1", "-ar", str(TASA), "-af",
               "highpass=f=70,silenceremove=stop_periods=-1:stop_duration=0.6:stop_threshold=-40dB,loudnorm",
               str(tmp / "referencia.wav"))
        duracion = sf.info(str(tmp / "referencia.wav")).duration
        if duracion < DURACION_MIN:
            raise HTTPException(400, f"Hay {duracion:.0f} s de voz (sin silencios); hacen falta al menos {DURACION_MIN} s")
        huella = huella_de(tmp / "referencia.wav", tmp)
        huella_base(voz_base)  # se calcula ya para que el primer uso sea rápido y falle aquí si Supertonic no responde
        carpeta = tmp / "voz"
        carpeta.mkdir()
        torch.save(huella, carpeta / "huella.pth")
        shutil.copy(tmp / "referencia.wav", carpeta / "referencia.wav")
        datos = {"nombre": nombre, "voz_base": voz_base, "duracion": round(duracion, 1),
                 "creada": time.strftime("%Y-%m-%d %H:%M"), "tau": TAU}
        (carpeta / "meta.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(carpeta), VOCES / nombre)  # la voz aparece completa o no aparece
    return datos


@app.delete("/v1/voces/{nombre}", dependencies=protegido)
def borrar(nombre: str):
    meta(nombre)  # 404 si no existe; el nombre ya no puede salir de VOCES
    shutil.rmtree(VOCES / nombre)
    return {"borrada": nombre}


@app.get("/v1/voces/{nombre}/muestra", dependencies=protegido)
def muestra(nombre: str):
    """Frase corta con la voz; se genera una vez y se guarda."""
    ruta = VOCES / meta(nombre)["nombre"] / "muestra.mp3"
    if not ruta.is_file():
        ruta.write_bytes(hablar_con(nombre, TEXTO_MUESTRA, 1.0))
    return Response(ruta.read_bytes(), media_type="audio/mpeg")

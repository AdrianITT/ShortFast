"""Servidor mínimo compatible con OpenAI (/v1/audio/speech) sobre Supertonic 3 (voz local, sin internet)."""
import os
import secrets
import threading
from pathlib import Path

import lameenc
import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from helper import load_text_to_speech, load_voice_style  # código oficial archivado, versión fijada en el Dockerfile

CLAVE = os.environ.get("API_KEY", "")
MODELO = Path(os.environ.get("CARPETA_MODELO", "/modelo"))
VOZ_DEFECTO = os.environ.get("VOZ_DEFECTO", "F1")
IDIOMA = os.environ.get("IDIOMA", "es")
PASOS = int(os.environ.get("PASOS", "8"))  # 5 = más rápido, 8 = normal, 12 = más calidad (el doble de lento)


def autorizar(authorization: str = Header("")):
    # Sin API_KEY el servicio queda abierto: úsalo solo en tu red local.
    if CLAVE and not secrets.compare_digest(authorization, f"Bearer {CLAVE}"):
        raise HTTPException(401, "Invalid API key")


app = FastAPI()
protegido = [Depends(autorizar)]  # /health queda abierto para monitoreo
tts = load_text_to_speech(str(MODELO / "onnx"))
_estilos = {}
_candado = threading.Lock()  # una síntesis a la vez: el CPU es pequeño


class Peticion(BaseModel):
    input: str
    voice: str = VOZ_DEFECTO
    speed: float = 1.0
    model: str = "supertonic-3"
    response_format: str = "mp3"


def ids_voces():
    return sorted(p.stem for p in (MODELO / "voice_styles").glob("*.json"))


def a_mp3(audio):
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    codificador = lameenc.Encoder()
    codificador.set_bit_rate(192)
    codificador.set_in_sample_rate(tts.sample_rate)
    codificador.set_channels(1)
    codificador.set_quality(2)
    return bytes(codificador.encode(pcm) + codificador.flush())  # lameenc da bytearray; Response quiere bytes


@app.get("/health")
def salud():
    return {"ok": True, "voces": len(ids_voces()), "idioma": IDIOMA, "pasos": PASOS}


@app.get("/v1/audio/voices", dependencies=protegido)
def voces():
    return {"voices": [{"id": v} for v in ids_voces()]}


@app.post("/v1/audio/speech", dependencies=protegido)
def hablar(p: Peticion):
    if not p.input.strip():
        raise HTTPException(400, "input vacío")
    if not 0.5 <= p.speed <= 2.0:
        raise HTTPException(400, "speed debe estar entre 0.5 y 2.0")
    if p.voice not in ids_voces():
        raise HTTPException(400, f"Voz «{p.voice}» no encontrada. Disponibles: {', '.join(ids_voces())}")
    with _candado:
        if p.voice not in _estilos:
            _estilos[p.voice] = load_voice_style([str(MODELO / "voice_styles" / f"{p.voice}.json")])
        wav, duracion = tts(p.input, IDIOMA, _estilos[p.voice], PASOS, p.speed)
    audio = wav[0, : int(tts.sample_rate * float(duracion[0]))]
    if not audio.size:
        raise HTTPException(502, "Supertonic devolvió audio vacío")
    return Response(a_mp3(audio), media_type="audio/mpeg")

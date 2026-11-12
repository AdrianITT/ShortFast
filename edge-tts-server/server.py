"""Servidor mínimo compatible con OpenAI (/v1/audio/speech) sobre la librería edge-tts."""
import os
import secrets

import edge_tts
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

CLAVE = os.environ.get("API_KEY", "")
VOZ_DEFECTO = os.environ.get("VOZ_DEFECTO", "es-MX-DaliaNeural")


def autorizar(authorization: str = Header("")):
    # Sin API_KEY el servicio queda abierto: úsalo solo en tu red local.
    if CLAVE and not secrets.compare_digest(authorization, f"Bearer {CLAVE}"):
        raise HTTPException(401, "Invalid API key")


app = FastAPI()
protegido = [Depends(autorizar)]  # /health queda abierto para monitoreo


class Peticion(BaseModel):
    input: str
    voice: str = VOZ_DEFECTO
    speed: float = 1.0
    model: str = "edge"
    response_format: str = "mp3"


@app.get("/health")
def salud():
    return {"ok": True}


@app.get("/v1/audio/voices", dependencies=protegido)
async def voces():
    return {"voices": [{"id": v["ShortName"]} for v in await edge_tts.list_voices()]}


@app.post("/v1/audio/speech", dependencies=protegido)
async def hablar(p: Peticion):
    if not p.input.strip():
        raise HTTPException(400, "input vacío")
    ritmo = f"{round((p.speed - 1) * 100):+d}%"  # speed 0.93 -> -7%
    audio = b""
    try:
        async for trozo in edge_tts.Communicate(p.input, p.voice, rate=ritmo).stream():
            if trozo["type"] == "audio":
                audio += trozo["data"]
    except Exception as e:  # sin internet, voz inexistente o límite del servicio
        raise HTTPException(502, f"edge-tts falló: {e}") from None
    if not audio:
        raise HTTPException(502, "edge-tts devolvió audio vacío")
    return Response(audio, media_type="audio/mpeg")

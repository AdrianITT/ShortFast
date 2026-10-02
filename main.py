from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess, json, os, re, time, shutil
import guia_ia, shutil, hashlib, threading
import generar_guia

app = FastAPI()

PROYECTOS = os.environ.get("PROYECTOS", "/data/proyectos")
SALIDA = os.environ.get("SALIDA", "/data/salida")
RENDER_PY = os.environ.get("RENDER_PY", "/app/render.py")
LOGS = os.path.join(SALIDA, "logs")
PLANTILLA = os.environ.get("PLANTILLA", os.path.join(os.path.dirname(PROYECTOS), "plantilla"))
RUTA_HOST = "/DATA/video-editor/proyectos"  # cómo se ve la carpeta desde el servidor
NOMBRE_OK = re.compile(r"^[A-Za-z0-9_\-]+$")
MINUTOS_SIN_AVANCE = 20  # si el log no cambia en este tiempo, el render se da por muerto
CACHE_PROBE = os.environ.get("CACHE_PROBE", os.path.join(SALIDA, "cache_probe.json"))
_cache_lock = threading.Lock()


class ProbeIn(BaseModel):
    ruta: str


class RenderIn(BaseModel):
    proyecto: str


# ─────────────────────────── utilidades ───────────────────────────

def carpeta_proyecto(nombre):
    if not NOMBRE_OK.match(nombre):
        raise HTTPException(status_code=400, detail="Nombre de proyecto inválido")
    d = os.path.join(PROYECTOS, nombre)
    if not os.path.isdir(d):
        raise HTTPException(status_code=404, detail=f"No existe el proyecto {nombre}")
    return d


def archivos_faltantes(d):
    try:
        g = json.load(open(os.path.join(d, "guia.json"), encoding="utf-8"))
    except FileNotFoundError:
        return ["guia.json"]
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"guia.json tiene un error: {e}")
    rutas = [g["musica"]["archivo"]] + list(g["fuentes"].values())
    for e in g["escenas"]:
        rutas += e.get("imagenes") or []
        if e.get("voz"):
            rutas.append(e["voz"])
    return [r for r in rutas if not os.path.isfile(os.path.join(d, r))]


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_cache_probe():
    try:
        with open(CACHE_PROBE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_cache_probe(cache):
    os.makedirs(os.path.dirname(CACHE_PROBE), exist_ok=True)
    tmp = CACHE_PROBE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(tmp, CACHE_PROBE)  # escritura atómica: nunca queda un JSON a medias


def leer_estado(nombre):
    log = os.path.join(LOGS, f"{nombre}.log")
    if not os.path.isfile(log):
        return {"proyecto": nombre, "estado": "sin_render", "log": ""}

    texto = open(log, encoding="utf-8", errors="replace").read()
    ultimas = "\n".join(texto.strip().splitlines()[-12:])
    salida = re.search(r"__EXIT__=(\d+)", texto)

    # Acepta tanto los logs de este endpoint como los de render-short
    if (salida and salida.group(1) == "0") or "TERMINADO OK" in texto:
        estado = "ok"
    elif salida or "TERMINÓ CON ERROR" in texto:
        estado = "error"
    elif time.time() - os.path.getmtime(log) > MINUTOS_SIN_AVANCE * 60:
        estado = "error"
        ultimas += "\n(El render se interrumpió: el log dejó de avanzar)"
    else:
        estado = "renderizando"

    r = {"proyecto": nombre, "estado": estado, "log": ultimas}
    if estado == "ok":
        r["video"] = os.path.join(SALIDA, f"{nombre}.mp4")
    return r


# ─────────────────────────── endpoints ───────────────────────────

@app.get("/health")
def health():
    v = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    return {"ok": True, "ffmpeg": v.stdout.splitlines()[0]}


@app.post("/probe")
def probe(body: ProbeIn):
    if not body.ruta.startswith("/data/"):
        raise HTTPException(status_code=400, detail="Ruta no permitida")
    if not os.path.isfile(body.ruta):
        raise HTTPException(status_code=404, detail="No hay archivos")
    # La clave es el hash del contenido: mismo nombre con otro contenido = otra entrada,
    # y el mismo archivo en otra carpeta reutiliza el resultado.
    huella = sha256_archivo(body.ruta)
    with _cache_lock:
        cache = leer_cache_probe()
    if huella in cache:
        return {"ruta": body.ruta, **cache[huella], "cache": True}

    resultado = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "format=duration:stream=codec_type,width,height",
         "-of", "json", body.ruta],
        capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise HTTPException(status_code=422, detail=f"ffprobe falló: {resultado.stderr.strip()}")
    datos = json.loads(resultado.stdout)
    streams = datos.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    duracion = datos.get("format", {}).get("duration")
    info = {
        "duracion": float(duracion) if duracion else None,
        "ancho": video.get("width") if video else None,
        "alto": video.get("height") if video else None,
        "tiene_audio": any(s.get("codec_type") == "audio" for s in streams),
    }
    with _cache_lock:
        cache = leer_cache_probe()
        cache[huella] = info
        guardar_cache_probe(cache)
    return {"ruta": body.ruta, **info, "cache": False}


@app.get("/proyectos")
def proyectos():
    """Lista los proyectos y su estado, del más reciente al más viejo."""
    if not os.path.isdir(PROYECTOS):
        return []
    nombres = [n for n in os.listdir(PROYECTOS) if os.path.isdir(os.path.join(PROYECTOS, n))]
    nombres.sort(key=lambda n: os.path.getmtime(os.path.join(PROYECTOS, n)), reverse=True)
    return [{
        "proyecto": n,
        "tiene_guia": os.path.isfile(os.path.join(PROYECTOS, n, "guia.json")),
        "estado": leer_estado(n)["estado"],
    } for n in nombres]


@app.post("/render")
def render(body: RenderIn):
    nombre = body.proyecto.strip()
    d = carpeta_proyecto(nombre)

    falta = archivos_faltantes(d)
    if falta:
        raise HTTPException(status_code=422, detail={"mensaje": "Faltan archivos", "faltan": falta})
    if leer_estado(nombre)["estado"] == "renderizando":
        raise HTTPException(status_code=409, detail=f"{nombre} ya se está renderizando")

    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, f"{nombre}.log"), "w") as log:
        # start_new_session: el render sigue aunque uvicorn se reinicie por --reload
        subprocess.Popen(
            ["sh", "-c", f'python "{RENDER_PY}" "$1"; echo "__EXIT__=$?"', "_", nombre],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    return {"proyecto": nombre, "estado": "renderizando"}


@app.get("/estado/{proyecto}")
def estado(proyecto: str):
    carpeta_proyecto(proyecto)
    return leer_estado(proyecto)


@app.get("/video/{proyecto}")
def video(proyecto: str):
    carpeta_proyecto(proyecto)
    ruta = os.path.join(SALIDA, f"{proyecto}.mp4")
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="Todavía no hay video para este proyecto")
    return FileResponse(ruta, media_type="video/mp4", filename=f"{proyecto}.mp4")


@app.post("/nuevo")
def nuevo(body: RenderIn):
    """Lo mismo que el comando nuevo-short: crea carpetas y copia la plantilla."""
    nombre = body.proyecto.strip()
    if not NOMBRE_OK.match(nombre):
        raise HTTPException(status_code=400, detail="Nombre inválido: usa solo letras, números, _ y -")
    d = os.path.join(PROYECTOS, nombre)
    if os.path.exists(d):
        raise HTTPException(status_code=409, detail=f"Ya existe el proyecto {nombre}")
    if not os.path.isdir(PLANTILLA):
        raise HTTPException(status_code=500, detail=f"No existe la plantilla en {PLANTILLA}")

    for sub in ("voz", "imagenes", "musica"):
        os.makedirs(os.path.join(d, sub))
    if os.path.isdir(os.path.join(PLANTILLA, "fuentes")):
        shutil.copytree(os.path.join(PLANTILLA, "fuentes"), os.path.join(d, "fuentes"))
    for sub in ("imagenes", "voz"):
        origen = os.path.join(PLANTILLA, sub)
        if os.path.isdir(origen):
            for f in os.listdir(origen):
                shutil.copy2(os.path.join(origen, f), os.path.join(d, sub, f))

    return {"proyecto": nombre, "carpeta": f"{RUTA_HOST}/{nombre}"}


@app.get("/revisar/{proyecto}")
def revisar(proyecto: str):
    """Qué hay subido y, si ya hay guía, qué archivos faltan."""
    d = carpeta_proyecto(proyecto)
    contar = lambda sub: len([f for f in os.listdir(os.path.join(d, sub))
                              if not f.startswith(".")]) if os.path.isdir(os.path.join(d, sub)) else 0
    tiene_guia = os.path.isfile(os.path.join(d, "guia.json"))
    return {
        "proyecto": proyecto,
        "imagenes": contar("imagenes"),
        "voces": contar("voz"),
        "musica": contar("musica"),
        "tiene_guia": tiene_guia,
        "faltan": archivos_faltantes(d) if tiene_guia else [],
    }


@app.post("/generar-guia-local")
def generar_guia_local(body: RenderIn):
    """Flujo real de los shorts: convierte guia_borrador.json (con claves tipo
    '2A', 'OUTRO', 'MUSICA') en guia.json, buscando los archivos reales del
    proyecto. No usa Gemini. Ver generar_guia.py."""
    nombre = body.proyecto.strip()
    d = carpeta_proyecto(nombre)
    if not os.path.isfile(os.path.join(d, "guia_borrador.json")):
        raise HTTPException(status_code=404, detail="No hay guia_borrador.json en el proyecto")
    try:
        r = generar_guia.generar(d)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"guia_borrador.json inválido: {e}")
    if not r["ok"]:
        raise HTTPException(status_code=422, detail={"mensaje": "Faltan archivos o datos", "avisos": r["avisos"]})
    return {"proyecto": nombre, "ok": True, "avisos": r["avisos"]}


@app.post("/generar-guia")
def generar_guia_ia(body: RenderIn):
    """Arma el guia.json con Gemini a partir de guia.md y los archivos del proyecto."""
    nombre = body.proyecto.strip()
    d = carpeta_proyecto(nombre)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="Falta GEMINI_API_KEY en el contenedor")
    modelo = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    try:
        return guia_ia.generar(nombre, d, PLANTILLA, PROYECTOS, key, modelo)
    except guia_ia.ErrorGuia as e:
        mensaje = str(e) + ("\n• " + "\n• ".join(e.detalles) if e.detalles else "")
        raise HTTPException(status_code=422, detail=mensaje)

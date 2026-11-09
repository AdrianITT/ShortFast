"""Configuración del panel. Prioridad: variables de entorno > .env > panel.json > valores por defecto."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_POR_DEFECTO = RAIZ / "panel.json"


@dataclass
class ConfigInterfaz:
    habilitada: bool = False
    opciones: dict = field(default_factory=dict)


class Configuracion:
    def __init__(self, api_url, carpeta_descargas, interfaces, carpeta_proyectos, tts_url, tts_voz):
        self.api_url = api_url.rstrip("/")
        self.carpeta_descargas = Path(carpeta_descargas).expanduser()
        self.interfaces = interfaces
        self.carpeta_proyectos = Path(carpeta_proyectos).expanduser()
        self.tts_url = tts_url.rstrip("/")
        self.tts_voz = tts_voz

    @classmethod
    def cargar(cls, ruta=None, entorno=None):
        ruta = Path(ruta or RUTA_POR_DEFECTO)
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
        env = {**_leer_dotenv(RAIZ / ".env"), **(os.environ if entorno is None else entorno)}

        def valor(clave_env, clave_json, defecto):
            return env.get(clave_env) or datos.get(clave_json) or defecto

        interfaces = {
            nombre: ConfigInterfaz(
                habilitada=bool(v.get("habilitada", False)),
                opciones={k: x for k, x in v.items() if k != "habilitada"},
            )
            for nombre, v in datos.get("interfaces", {"terminal": {"habilitada": True}}).items()
        }
        datos_dir = _absoluta(env.get("DATA_DIR") or "datos")
        return cls(
            api_url=valor("FFMPEG_API_URL", "api_url", f"http://localhost:{env.get('API_PORT', '8123')}"),
            carpeta_descargas=valor("DESCARGAS_DIR", "carpeta_descargas", "~/Videos/ffmpeg-api"),
            interfaces=interfaces,
            carpeta_proyectos=_absoluta(env.get("PROYECTOS_DIR")) if env.get("PROYECTOS_DIR")
            else datos.get("carpeta_proyectos") or datos_dir / "proyectos",
            tts_url=valor("TTS_URL", "tts_url", f"http://localhost:{env.get('KOKORO_PORT', '8880')}"),
            tts_voz=valor("TTS_VOZ", "tts_voz", "em_alex"),
        )


def _absoluta(ruta):
    """Las rutas relativas se entienden desde la raíz del proyecto, igual que en docker compose."""
    p = Path(ruta).expanduser()
    return p if p.is_absolute() else RAIZ / p


def _leer_dotenv(ruta):
    valores = {}
    if ruta.is_file():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, _, v = linea.partition("=")
                valores[clave.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
    return valores

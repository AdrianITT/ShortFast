"""Configuración del panel. Prioridad: variables de entorno > .env > panel.json > valores por defecto."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_POR_DEFECTO = RAIZ / "panel.json"
SERVICIO_CLONADOR = "Mi voz"  # nombre del servicio de voces clonadas en el selector de la web
# nombre en la web -> id del perfil de docker compose (SERVICIOS_VOZ / COMPOSE_PROFILES)
IDS_SERVICIO = {"Kokoro": "kokoro", "Supertonic": "supertonic", "Edge": "edge", SERVICIO_CLONADOR: "clonador"}


@dataclass
class ConfigInterfaz:
    habilitada: bool = False
    opciones: dict = field(default_factory=dict)


class Configuracion:
    def __init__(self, api_url, carpeta_descargas, interfaces, carpeta_proyectos, tts_url, tts_voz,
                 carpeta_musica_biblioteca, tts_velocidad=1.0, tts_clave=None,
                 kokoro_url="http://localhost:8880", edge_url="http://localhost:5050", edge_voz="es-MX-DaliaNeural",
                 supertonic_url="http://localhost:5200", supertonic_voz="F1", clonador_url="http://localhost:5300",
                 servicios_voz=None):
        self.api_url = api_url.rstrip("/")
        self.carpeta_descargas = Path(carpeta_descargas).expanduser()
        self.interfaces = interfaces
        self.carpeta_proyectos = Path(carpeta_proyectos).expanduser()
        self.tts_url = tts_url.rstrip("/")
        self.tts_voz = tts_voz
        self.tts_velocidad = float(tts_velocidad)
        self.tts_clave = tts_clave
        self.kokoro_url = kokoro_url.rstrip("/")
        self.edge_url = edge_url.rstrip("/")
        self.supertonic_url = supertonic_url.rstrip("/")
        self.supertonic_voz = supertonic_voz
        self.clonador_url = clonador_url.rstrip("/")
        # "supertonic,clonador" (los perfiles de docker compose) -> {"supertonic", "clonador"}; None = todas
        self.servicios_voz = None if servicios_voz is None else {
            s.strip().lower() for s in str(servicios_voz).split(",") if s.strip()}
        self.edge_voz = edge_voz
        self.carpeta_musica_biblioteca = Path(carpeta_musica_biblioteca).expanduser()

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
            carpeta_musica_biblioteca=datos_dir / "musica_biblioteca",
            tts_velocidad=valor("TTS_VELOCIDAD", "tts_velocidad", 1.0),
            tts_clave=valor("TTS_API_KEY", "tts_api_key", None),
            kokoro_url=valor("KOKORO_URL", "kokoro_url", f"http://localhost:{env.get('KOKORO_PORT', '8880')}"),
            edge_url=valor("EDGE_TTS_URL", "edge_tts_url", f"http://localhost:{env.get('EDGE_TTS_PORT', '5050')}"),
            edge_voz=valor("EDGE_TTS_VOZ", "edge_tts_voz", "es-MX-DaliaNeural"),
            supertonic_url=valor("SUPERTONIC_URL", "supertonic_url", f"http://localhost:{env.get('SUPERTONIC_PORT', '5200')}"),
            supertonic_voz=valor("SUPERTONIC_VOZ", "supertonic_voz", "F1"),
            clonador_url=valor("CLONADOR_URL", "clonador_url", f"http://localhost:{env.get('CLONADOR_PORT', '5300')}"),
            servicios_voz=valor("SERVICIOS_VOZ", "servicios_voz", None),
        )

    @property
    def servicios_tts(self):
        """{nombre: (url, voz por defecto)} para elegir en la web. El primero es el de TTS_URL
        (el que usa la terminal) y lleva TTS_VOZ; si TTS_URL no es Kokoro ni Edge, aparece como «Otro»."""
        conocidos = {"Kokoro": (self.kokoro_url, "em_alex"), "Supertonic": (self.supertonic_url, self.supertonic_voz),
                     "Edge": (self.edge_url, self.edge_voz),
                     SERVICIO_CLONADOR: (self.clonador_url, "")}  # sin voz por defecto: se usa la primera creada
        if self.servicios_voz is not None:  # instalación con solo algunas voces: el resto no se ofrece
            conocidos = {n: s for n, s in conocidos.items() if IDS_SERVICIO[n] in self.servicios_voz}
        principal = next((n for n, (u, _) in conocidos.items() if u == self.tts_url), None)
        if principal is None:
            if self.servicios_voz is not None and conocidos:
                return conocidos  # TTS_URL no es ninguna instalada: manda la primera con su voz
            principal = "Otro"
        return {principal: (self.tts_url, self.tts_voz),
                **{n: s for n, s in conocidos.items() if n != principal}}


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

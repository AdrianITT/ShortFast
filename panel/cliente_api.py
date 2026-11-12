"""Cliente HTTP de ffmpeg-api. Es la única clase que sabe hablar con la red."""
import json
import shutil
import urllib.error
import urllib.request


class ErrorApi(Exception):
    """La API respondió con error, o no se pudo conectar."""


class ClienteApi:
    def __init__(self, url_base, tiempo_espera=30):
        self.url_base = url_base.rstrip("/")
        self.tiempo_espera = tiempo_espera

    def get(self, ruta):
        return self._pedir("GET", ruta)

    def post(self, ruta, cuerpo=None, tiempo_espera=None):
        return self._pedir("POST", ruta, cuerpo, tiempo_espera)

    def descargar(self, ruta, destino):
        with self._abrir("GET", ruta, None, 600) as r, open(destino, "wb") as f:
            shutil.copyfileobj(r, f)

    def abrir(self, ruta, tiempo_espera=600):
        """Como descargar(), pero entrega el flujo abierto para reenviarlo (quien llama lo cierra)."""
        return self._abrir("GET", ruta, None, tiempo_espera)

    def _pedir(self, metodo, ruta, cuerpo=None, tiempo_espera=None):
        with self._abrir(metodo, ruta, cuerpo, tiempo_espera) as r:
            return json.loads(r.read().decode("utf-8"))

    def _abrir(self, metodo, ruta, cuerpo, tiempo_espera):
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        peticion = urllib.request.Request(
            self.url_base + ruta, data=datos, method=metodo,
            headers={"Content-Type": "application/json"} if datos else {},
        )
        try:
            return urllib.request.urlopen(peticion, timeout=tiempo_espera or self.tiempo_espera)
        except urllib.error.HTTPError as e:
            raise ErrorApi(self._texto_error(e)) from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorApi(f"No se pudo conectar con {self.url_base}: {getattr(e, 'reason', e)}") from None

    @staticmethod
    def _texto_error(e):
        try:
            detalle = json.loads(e.read().decode("utf-8")).get("detail", "")
        except (ValueError, AttributeError):
            detalle = ""
        if isinstance(detalle, dict):
            partes = [str(detalle.get("mensaje", ""))]
            for clave in ("faltan", "avisos"):
                partes += [f"  • {x}" for x in detalle.get(clave, [])]
            detalle = "\n".join(p for p in partes if p)
        return f"[{e.code}] {detalle or e.reason}"

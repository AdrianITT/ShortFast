"""Cliente del servicio de voz Kokoro (API compatible con OpenAI /v1/audio/speech)."""
import json
import urllib.error
import urllib.request


class ErrorTts(Exception):
    pass


class ClienteKokoro:
    # Respaldo si Kokoro no responde al listar: las voces de español.
    VOCES_RESPALDO = ("ef_dora", "em_alex", "em_santa")
    # Prefijo del id (Kokoro: ef_…, Edge: es-MX-…, Supertonic: F1…M5) -> grupo; las voces con otro prefijo van a «Otros idiomas».
    GRUPOS = (("Español", ("ef_", "em_", "es-")), ("Inglés", ("af_", "am_", "bf_", "bm_", "en-")),
              ("Mujer", ("F",)), ("Hombre", ("M",)))  # Supertonic: solo mayúsculas, ningún otro servicio las usa

    def __init__(self, url_base, modelo="kokoro", tiempo_espera=120, velocidad=1.0, clave=None):
        self.url_base = url_base.rstrip("/")
        self.modelo = modelo
        self.tiempo_espera = tiempo_espera
        self.velocidad = velocidad
        self.clave = clave  # servicios con clave (p. ej. edge-tts-api); Kokoro no la usa

    def _cabeceras(self):
        cabeceras = {"Content-Type": "application/json"}
        if self.clave:
            cabeceras["Authorization"] = f"Bearer {self.clave}"
        return cabeceras

    def voces(self):
        """Ids de las voces de Kokoro; si no responde, la lista de respaldo."""
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url_base + "/v1/audio/voices", headers=self._cabeceras()), timeout=10) as r:
                ids = [v["id"] for v in json.load(r)["voices"]]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError):
            return list(self.VOCES_RESPALDO)
        return ids or list(self.VOCES_RESPALDO)

    @classmethod
    def agrupar(cls, ids):
        """[(titulo, [ids])] con español primero, luego inglés y el resto; omite grupos vacíos."""
        grupos = [(t, [i for i in ids if i.startswith(p)]) for t, p in cls.GRUPOS]
        usados = {i for _, g in grupos for i in g}
        grupos.append(("Otros idiomas", [i for i in ids if i not in usados]))
        return [(t, g) for t, g in grupos if g]

    def sintetizar(self, texto, voz, velocidad=None):
        """Devuelve el audio mp3 (bytes) del texto con la voz indicada (velocidad: la de por defecto si es None)."""
        cuerpo = json.dumps({"model": self.modelo, "voice": voz, "input": texto,
                             "response_format": "mp3", "speed": velocidad or self.velocidad}).encode("utf-8")
        peticion = urllib.request.Request(
            self.url_base + "/v1/audio/speech", data=cuerpo, method="POST",
            headers=self._cabeceras())
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo_espera) as r:
                audio = r.read()
        except urllib.error.HTTPError as e:
            raise ErrorTts(f"El servicio de voz respondió [{e.code}]: {e.read().decode('utf-8', 'replace')[:200]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorTts(f"No se pudo conectar con el servicio de voz en {self.url_base}: {getattr(e, 'reason', e)}") from None
        if not audio:
            raise ErrorTts("El servicio de voz devolvió un audio vacío")
        return audio

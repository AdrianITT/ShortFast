"""Cliente del servicio de voz Kokoro (API compatible con OpenAI /v1/audio/speech)."""
import json
import urllib.error
import urllib.request


class ErrorTts(Exception):
    pass


class ClienteKokoro:
    def __init__(self, url_base, modelo="kokoro", tiempo_espera=120):
        self.url_base = url_base.rstrip("/")
        self.modelo = modelo
        self.tiempo_espera = tiempo_espera

    def sintetizar(self, texto, voz):
        """Devuelve el audio mp3 (bytes) del texto con la voz indicada."""
        cuerpo = json.dumps({"model": self.modelo, "voice": voz, "input": texto,
                             "response_format": "mp3"}).encode("utf-8")
        peticion = urllib.request.Request(
            self.url_base + "/v1/audio/speech", data=cuerpo, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=self.tiempo_espera) as r:
                audio = r.read()
        except urllib.error.HTTPError as e:
            raise ErrorTts(f"Kokoro respondió [{e.code}]: {e.read().decode('utf-8', 'replace')[:200]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorTts(f"No se pudo conectar con Kokoro en {self.url_base}: {getattr(e, 'reason', e)}") from None
        if not audio:
            raise ErrorTts("Kokoro devolvió un audio vacío")
        return audio

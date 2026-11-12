"""Cliente del servicio de clonación de voz (clonador-server): genera como cualquier servicio de voz y gestiona las voces."""
import json
import urllib.error
import urllib.parse
import urllib.request

from .tts import ClienteKokoro

NOMBRE_MAX = 40


class ErrorClonador(Exception):
    pass


class ClienteClonador(ClienteKokoro):
    VOCES_RESPALDO = ()  # sin voces creadas, la lista queda vacía (no se ofrecen voces de Kokoro)
    VOCES_BASE = tuple(f"{g}{n}" for g in "MF" for n in range(1, 6))  # voces de Supertonic que ponen la pronunciación

    @classmethod
    def agrupar(cls, ids):
        return [("Mis voces", list(ids))] if ids else []

    @staticmethod
    def nombre_valido(texto):
        """'Mi Voz 1' -> 'mi_voz_1' (lo que acepta el servicio: minúsculas, números, _ y -)."""
        nombre = "".join(c if c.isalnum() or c in "_-" else "_" for c in texto.strip().lower())
        nombre = "_".join(p for p in nombre.split("_") if p)[:NOMBRE_MAX]
        if len(nombre) < 2 or not nombre.isascii():
            raise ErrorClonador("Pon un nombre de al menos 2 letras o números, sin acentos ni ñ")
        return nombre

    def _pedir(self, ruta, metodo="GET", datos=None, tipo="application/json", tiempo=None):
        cabeceras = {**self._cabeceras(), "Content-Type": tipo}
        peticion = urllib.request.Request(self.url_base + ruta, data=datos, method=metodo, headers=cabeceras)
        try:
            with urllib.request.urlopen(peticion, timeout=tiempo or self.tiempo_espera) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", "replace")
            try:
                cuerpo = json.loads(cuerpo).get("detail", cuerpo)
            except (ValueError, AttributeError):
                pass
            raise ErrorClonador(str(cuerpo)[:300]) from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorClonador(f"No se pudo conectar con el clonador en {self.url_base}: {getattr(e, 'reason', e)}") from None

    def listar(self):
        return json.loads(self._pedir("/v1/voces"))["voces"]

    def crear(self, nombre, voz_base, audio):
        """Crea la voz `nombre` desde los bytes de una grabación (tarda: ffmpeg + huella + voz base)."""
        if voz_base not in self.VOCES_BASE:
            raise ErrorClonador(f"Voz base inválida «{voz_base}»")
        if not audio:
            raise ErrorClonador("No se recibió ningún audio")
        consulta = urllib.parse.urlencode({"nombre": self.nombre_valido(nombre), "voz_base": voz_base})
        return json.loads(self._pedir(f"/v1/voces?{consulta}", "POST", audio, "application/octet-stream", 900))

    def borrar(self, nombre):
        self._pedir(f"/v1/voces/{urllib.parse.quote(nombre)}", "DELETE")

    def muestra(self, nombre):
        """mp3 de una frase corta con la voz (la primera vez se genera)."""
        return self._pedir(f"/v1/voces/{urllib.parse.quote(nombre)}/muestra", tiempo=600)


if __name__ == "__main__":  # autocomprobación: python -m panel.clonador
    assert ClienteClonador.nombre_valido(" Mi Voz 1 ") == "mi_voz_1"
    assert ClienteClonador.nombre_valido("adrian-2") == "adrian-2"
    for malo in ("", "a", "  ", "ñandú"):
        try:
            ClienteClonador.nombre_valido(malo)
            raise AssertionError(malo)
        except ErrorClonador:
            pass
    assert ClienteClonador.agrupar([]) == [] and ClienteClonador.agrupar(["yo"]) == [("Mis voces", ["yo"])]
    assert ClienteClonador("http://127.0.0.1:9").voces() == []  # servicio caído: lista vacía, no voces de Kokoro
    print("ok")

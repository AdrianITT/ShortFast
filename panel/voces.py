"""Generación de voces por tramo a partir de un guion pegado como texto (nada se guarda en disco)."""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

NOMBRE_MP3 = re.compile(r"^[A-Za-z0-9_\-]+\.mp3$")
VELOCIDAD_MIN, VELOCIDAD_MAX = 0.5, 1.5


class ErrorGuionVoces(Exception):
    pass


@dataclass
class Tramo:
    archivo: str
    texto: str


@dataclass
class ResultadoTramo:
    archivo: str
    estado: str  # 'generado' | 'omitido' | 'error'
    detalle: str = ""


class GuionVoces:
    def __init__(self, voz, tramos):
        self.voz = voz
        self.tramos = tramos

    @classmethod
    def validado(cls, voz, tramos):
        if not tramos:
            raise ErrorGuionVoces("No se encontró ningún tramo en el texto pegado")
        vistos = set()
        for t in tramos:
            if not NOMBRE_MP3.match(t.archivo):
                raise ErrorGuionVoces(f"Nombre de archivo inválido «{t.archivo}» (usa letras, números, _ y -, y .mp3)")
            if t.archivo in vistos:
                raise ErrorGuionVoces(f"El archivo «{t.archivo}» está repetido")
            if not t.texto.strip():
                raise ErrorGuionVoces(f"El tramo «{t.archivo}» no tiene texto")
            vistos.add(t.archivo)
        return cls(voz, tramos)


class AnalizadorGuion(ABC):
    """Un formato de texto reconocido. Para soportar otro, crear una subclase y añadirla a ANALIZADORES."""

    nombre = ""

    @abstractmethod
    def reconoce(self, texto): ...

    @abstractmethod
    def analizar(self, texto): ...


class AnalizadorBash(AnalizadorGuion):
    """Script de bash con llamadas `g "archivo.mp3" "texto"`. Se lee como texto: nunca se ejecuta."""

    nombre = "script bash"
    _LLAMADA = re.compile(r'^[ \t]*g[ \t]+"([^"]+)"(?:[ \t]|\\\n)*"((?:[^"\\]|\\.)*)"', re.M)
    _VOZ = re.compile(r'^[ \t]*VOZ=["\']?([A-Za-z0-9_\-]+)', re.M)

    def reconoce(self, texto):
        return bool(self._LLAMADA.search(texto))

    def analizar(self, texto):
        voz = self._VOZ.search(texto)
        tramos = [Tramo(m.group(1), re.sub(r"\\(.)", r"\1", m.group(2)))
                  for m in self._LLAMADA.finditer(texto)]
        return GuionVoces.validado(voz.group(1) if voz else None, tramos)


class AnalizadorLineas(AnalizadorGuion):
    """Una línea por tramo: `archivo.mp3 | texto`, con `voz: nombre` opcional y `#` para comentarios."""

    nombre = "líneas «archivo.mp3 | texto»"

    def reconoce(self, texto):
        return any("|" in l and not l.lstrip().startswith("#") for l in texto.splitlines())

    def analizar(self, texto):
        voz, tramos = None, []
        for n, linea in enumerate(texto.splitlines(), 1):
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if linea.lower().startswith("voz:"):
                voz = linea.split(":", 1)[1].strip()
                continue
            archivo, separador, contenido = (p.strip() for p in linea.partition("|"))
            if not separador:
                raise ErrorGuionVoces(f"Línea {n}: se esperaba «archivo.mp3 | texto»")
            tramos.append(Tramo(archivo, contenido))
        return GuionVoces.validado(voz, tramos)


ANALIZADORES = (AnalizadorBash(), AnalizadorLineas())


class GeneradorVoces:
    def __init__(self, cliente_tts, carpeta_proyectos, voz_por_defecto):
        self.tts = cliente_tts
        self.carpeta_proyectos = Path(carpeta_proyectos)
        self.voz_por_defecto = voz_por_defecto

    @property
    def velocidad_por_defecto(self):
        return self.tts.velocidad

    @staticmethod
    def velocidad_valida(valor):
        """Texto -> float entre VELOCIDAD_MIN y VELOCIDAD_MAX; vacío = None (usa la de por defecto)."""
        if valor is None or not str(valor).strip():
            return None
        try:
            v = float(str(valor).replace(",", "."))
        except ValueError:
            raise ErrorGuionVoces(f"Velocidad inválida «{valor}»: usa un número, por ejemplo 0.93") from None
        if not VELOCIDAD_MIN <= v <= VELOCIDAD_MAX:
            raise ErrorGuionVoces(f"La velocidad debe estar entre {VELOCIDAD_MIN} y {VELOCIDAD_MAX}")
        return v

    def voces_disponibles(self):
        """[(grupo, [ids])] de las voces que ofrece el servicio de voz."""
        return self.tts.agrupar(self.tts.voces())

    @staticmethod
    def preparar(texto):
        """Convierte el texto pegado en un GuionVoces, detectando el formato."""
        for analizador in ANALIZADORES:
            if analizador.reconoce(texto):
                return analizador.analizar(texto)
        raise ErrorGuionVoces("No reconozco el formato. Usa líneas «archivo.mp3 | texto» o un script con g \"archivo.mp3\" \"texto\"")

    def existentes(self, proyecto, guion):
        voz = self.carpeta_proyectos / proyecto / "voz"
        return [t.archivo for t in guion.tramos if (voz / t.archivo).is_file()]

    def generar(self, proyecto, guion, sobrescribir=False, velocidad=None):
        """Entrega un ResultadoTramo por tramo; un fallo en uno no detiene los demás."""
        destino = self.carpeta_proyectos / proyecto / "voz"
        destino.mkdir(parents=True, exist_ok=True)
        voz = guion.voz or self.voz_por_defecto
        for t in guion.tramos:
            ruta = destino / t.archivo
            if ruta.exists() and not sobrescribir:
                yield ResultadoTramo(t.archivo, "omitido")
                continue
            try:
                audio = self.tts.sintetizar(t.texto, voz, velocidad)
            except Exception as e:  # ErrorTts u otro: se informa por tramo
                yield ResultadoTramo(t.archivo, "error", str(e))
                continue
            temporal = ruta.with_suffix(".tmp")
            temporal.write_bytes(audio)
            temporal.replace(ruta)  # nunca queda un mp3 a medias
            yield ResultadoTramo(t.archivo, "generado")

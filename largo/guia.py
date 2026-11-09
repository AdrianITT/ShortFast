"""Modelo y validación de guia.json 16:9 (ver FORMATO_VIDEO_LARGO.md)."""
import json
import os
from dataclasses import dataclass, field

EFECTOS = {"zoom_in_lento", "zoom_in", "zoom_out", "zoom_out_lento", "paneo_der", "paneo_rapido", "ninguno"}
TRANSICIONES = {"corte", "fade", "fadeblack", "fadewhite", "dissolve"}
ANIMACIONES = {"ninguna", "fade", "palabra_por_palabra", "golpe"}  # golpe se muestra como ninguna, igual que en shorts
POSICIONES = {"arriba", "centro", "abajo", "abajo_firma", "izquierda", "derecha"}
AJUSTES = {"recortar", "congelar", "bucle"}
ENCUADRES = {"auto", "cubrir", "ajustar"}
TIPOS_MEDIO = {"imagen", "clip"}


class ErrorGuia(Exception):
    pass


def _elegir(valor, permitidos, campo, donde):
    if valor not in permitidos:
        raise ErrorGuia(f"{donde}: {campo} «{valor}» no es válido. Opciones: {', '.join(sorted(permitidos))}")
    return valor


@dataclass
class Formato:
    ancho: int = 1920
    alto: int = 1080
    fps: int = 30


@dataclass
class Transicion:
    tipo: str = "corte"
    duracion: float = 0.5


@dataclass
class Medio:
    tipo: str
    archivo: str
    efecto: str = "ninguno"
    duracion: float | None = None
    ajuste: str = "recortar"
    inicio: float = 0.0
    encuadre: str = "auto"


@dataclass
class Texto:
    contenido: str
    fuente: str = "bold"
    tamano: int = 80
    color: str = "white"
    posicion: str = "centro"
    animacion: str = "ninguna"
    inicio: float = 0.0
    duracion: float | None = None
    inicio_desde_final: float | None = None
    fin_desde_final: float | None = None


@dataclass
class Escena:
    id: str
    voz: str | None
    medios: list[Medio]
    textos: list[Texto]
    musica_vol: float = 0.15
    transicion_salida: Transicion = field(default_factory=Transicion)
    duracion: float | None = None


@dataclass
class Guia:
    proyecto: str
    formato: Formato
    fuentes: dict
    voz_retraso: float
    pausa_entre_escenas: float
    duracion_max: float
    musica: dict
    escenas: list[Escena]

    @classmethod
    def cargar(cls, ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                d = json.load(f)
        except FileNotFoundError:
            raise ErrorGuia(f"No existe {ruta}") from None
        except json.JSONDecodeError as e:
            raise ErrorGuia(f"guia.json tiene un error: {e}") from None
        try:
            return cls._desde_dict(d)
        except KeyError as e:
            raise ErrorGuia(f"Falta el campo {e} en guia.json") from None
        except TypeError as e:
            raise ErrorGuia(f"Campo desconocido o mal escrito en guia.json: {e}") from None

    @classmethod
    def _desde_dict(cls, d):
        fmt = Formato(**d.get("formato", {}))
        escenas, ids = [], set()
        for e in d["escenas"]:
            esc_id = str(e["id"])
            if esc_id in ids:
                raise ErrorGuia(f"El id de escena «{esc_id}» está repetido")
            ids.add(esc_id)
            donde = f"Escena {esc_id}"
            medios = []
            for m in e.get("medios", []):
                medio = Medio(**m)
                _elegir(medio.tipo, TIPOS_MEDIO, "tipo", donde)
                _elegir(medio.efecto, EFECTOS, "efecto", donde)
                _elegir(medio.ajuste, AJUSTES, "ajuste", donde)
                _elegir(medio.encuadre, ENCUADRES, "encuadre", donde)
                medios.append(medio)
            textos = []
            for t in e.get("textos", []):
                texto = Texto(**t)
                _elegir(texto.animacion, ANIMACIONES, "animacion", donde)
                _elegir(texto.posicion, POSICIONES, "posicion", donde)
                if texto.fuente not in d["fuentes"]:
                    raise ErrorGuia(f"{donde}: la fuente «{texto.fuente}» no está en «fuentes»")
                textos.append(texto)
            tr = Transicion(**e["transicion_salida"]) if e.get("transicion_salida") else Transicion()
            _elegir(tr.tipo, TRANSICIONES, "transicion_salida.tipo", donde)
            escenas.append(Escena(id=esc_id, voz=e.get("voz"), medios=medios, textos=textos,
                                  musica_vol=e.get("musica_vol", 0.15), transicion_salida=tr,
                                  duracion=e.get("duracion")))
        if not escenas:
            raise ErrorGuia("La guía no tiene escenas")
        return cls(proyecto=d["proyecto"], formato=fmt, fuentes=d["fuentes"],
                   voz_retraso=d.get("voz_retraso", 0.3),
                   pausa_entre_escenas=d.get("pausa_entre_escenas", 0.4),
                   duracion_max=d.get("duracion_max", 1800), musica=d["musica"], escenas=escenas)

    def archivos_faltantes(self, carpeta):
        rutas = [self.musica["archivo"]] + list(self.fuentes.values())
        for e in self.escenas:
            rutas += [m.archivo for m in e.medios]
            if e.voz:
                rutas.append(e.voz)
        return [r for r in rutas if not os.path.isfile(os.path.join(carpeta, r))]

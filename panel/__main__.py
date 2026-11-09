"""Punto de entrada: `python3 -m panel`. Arranca las interfaces habilitadas en panel.json."""
import sys
import threading

from .cliente_api import ClienteApi
from .config import Configuracion
from .interfaces import DISPONIBLES
from .servicios import ServicioProyectos
from .tts import ClienteKokoro
from .voces import GeneradorVoces


def construir_interfaces(config, servicio):
    activas = []
    for nombre, cfg in config.interfaces.items():
        if not cfg.habilitada:
            continue
        if nombre not in DISPONIBLES:
            print(f"⚠ La interfaz '{nombre}' está habilitada pero aún no existe; se omite.")
            continue
        activas.append(DISPONIBLES[nombre](servicio, cfg.opciones))
    return activas


def main():
    config = Configuracion.cargar()
    voces = GeneradorVoces(ClienteKokoro(config.tts_url), config.carpeta_proyectos, config.tts_voz)
    servicio = ServicioProyectos(ClienteApi(config.api_url), config.carpeta_descargas,
                              config.carpeta_proyectos, voces)
    activas = construir_interfaces(config, servicio)
    if not activas:
        sys.exit("No hay ninguna interfaz habilitada. Revisa panel.json.")

    for i in (i for i in activas if i.en_segundo_plano):
        threading.Thread(target=i.iniciar, daemon=True).start()
    en_primer_plano = [i for i in activas if not i.en_segundo_plano]
    if en_primer_plano:
        en_primer_plano[0].iniciar()
    else:
        threading.Event().wait()  # solo servidores: mantener vivo el proceso


if __name__ == "__main__":
    main()

"""Punto de entrada: `python3 -m panel`. Arranca las interfaces habilitadas en panel.json."""
import sys
import threading

from .archivos import GestorArchivos
from .biblioteca import BibliotecaMusica
from .cliente_api import ClienteApi
from .clonador import ClienteClonador
from .config import SERVICIO_CLONADOR, Configuracion
from .cortador import CortadorVoz
from .guia import GestorGuia
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
    clientes = {nombre: (ClienteClonador if nombre == SERVICIO_CLONADOR else ClienteKokoro)(
                    url, velocidad=config.tts_velocidad, clave=config.tts_clave)
                for nombre, (url, _) in config.servicios_tts.items()}
    motores_voz = {nombre: GeneradorVoces(clientes[nombre], config.carpeta_proyectos, voz)
                   for nombre, (_, voz) in config.servicios_tts.items()}
    voces = next(iter(motores_voz.values()))  # el de TTS_URL: el que usa la terminal, como antes
    archivos = GestorArchivos(config.carpeta_proyectos)
    guia = GestorGuia(config.carpeta_proyectos)
    biblioteca = BibliotecaMusica(config.carpeta_musica_biblioteca)
    servicio = ServicioProyectos(ClienteApi(config.api_url), config.carpeta_descargas,
                              config.carpeta_proyectos, voces, archivos, guia, biblioteca,
                              CortadorVoz(config.carpeta_proyectos), motores_voz, clientes.get(SERVICIO_CLONADOR))
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

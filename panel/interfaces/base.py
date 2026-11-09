from abc import ABC, abstractmethod


class Interfaz(ABC):
    """Una forma de interactuar con el servicio (terminal, web, Telegram...)."""

    nombre = ""
    en_segundo_plano = False  # True: servidor que corre en un hilo; False: toma la consola

    def __init__(self, servicio, opciones):
        self.servicio = servicio
        self.opciones = opciones

    @abstractmethod
    def iniciar(self):
        """Arranca la interfaz. Bloquea hasta que el usuario termina."""

"""Registro de interfaces disponibles. Para añadir una (web, Telegram), crear su clase y registrarla aquí."""
from .terminal import InterfazTerminal

DISPONIBLES = {cls.nombre: cls for cls in (InterfazTerminal,)}

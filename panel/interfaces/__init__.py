"""Registro de interfaces disponibles. Para añadir una (web, Telegram), crear su clase y registrarla aquí."""
from .terminal import InterfazTerminal

_CLASES = [InterfazTerminal]

try:
    from .web import InterfazWeb  # requiere las dependencias de panel/requirements.txt
    _CLASES.append(InterfazWeb)
except ImportError:
    pass  # panel.json puede seguir habilitando "web"; se avisa al arrancar (ver __main__.py)

DISPONIBLES = {cls.nombre: cls for cls in _CLASES}

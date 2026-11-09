#!/usr/bin/env python3
"""
Render de un video largo 16:9 a partir de su guia.json.

Uso (desde el servidor):
    docker exec ffmpeg-api python /app/render_largo.py largo_01_tema [--conservar-tmp] [--reanudar]

Lee:    /data/proyectos_largos/<nombre>/guia.json
Genera: /data/salida_largos/<nombre>.mp4
"""
import argparse
import os
import sys

from largo.guia import ErrorGuia
from largo.herramientas import ErrorRender
from largo.render import RenderLargo

PROYECTOS_LARGOS = os.environ.get("PROYECTOS_LARGOS", "/data/proyectos_largos")
SALIDA_LARGOS = os.environ.get("SALIDA_LARGOS", "/data/salida_largos")


def main():
    ap = argparse.ArgumentParser(description="Render de video largo 16:9")
    ap.add_argument("proyecto")
    ap.add_argument("--conservar-tmp", action="store_true", help="no borrar los temporales (depuración)")
    ap.add_argument("--reanudar", action="store_true",
                    help="si una ejecución anterior dejó el video unido en los temporales, saltar directo al audio")
    args = ap.parse_args()
    os.makedirs(SALIDA_LARGOS, exist_ok=True)
    try:
        RenderLargo(args.proyecto, PROYECTOS_LARGOS, SALIDA_LARGOS, args.conservar_tmp, args.reanudar).ejecutar()
    except (ErrorGuia, ErrorRender, ValueError) as e:
        sys.exit(f"❌ {e}")


if __name__ == "__main__":
    main()

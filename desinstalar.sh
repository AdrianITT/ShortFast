#!/usr/bin/env bash
# Desinstala ShortFast: para y quita los contenedores (y la app de CasaOS si existe).
# Por defecto los DATOS (proyectos, videos, voces creadas), las imágenes y el .env se conservan.
#   ./desinstalar.sh                    # quita contenedores
#   ./desinstalar.sh --imagenes         # además borra las imágenes construidas (libera ~6 GB)
#   ./desinstalar.sh --borrar-datos     # además borra la carpeta de datos (pide escribir BORRAR)
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
IMAGENES=0 DATOS=0
for a in "$@"; do
  case "$a" in
    --imagenes) IMAGENES=1 ;;
    --borrar-datos) DATOS=1 ;;
    -h|--ayuda) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $a" >&2; exit 1 ;;
  esac
done
leer_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }

if command -v casaos-cli >/dev/null && [ -x scripts/casaos.sh ]; then scripts/casaos.sh desinstalar || true; fi
COMPOSE_PROFILES=supertonic,clonador,kokoro,edge docker compose down --remove-orphans
echo "✔ Contenedores quitados"

if [ "$DATOS" = 1 ]; then
  datos="$(leer_env DATA_DIR)"; datos="${datos:-./datos}"
  if [ -d "$datos" ]; then
    real="$(readlink -f "$datos")"
    case "$real" in /|/home|/DATA|/root|/tmp|"$HOME"|"$(pwd)") echo "✘ No borro «$real»: es una carpeta del sistema o la del proyecto" >&2; exit 1 ;; esac
    echo "Se borrará TODO lo que hay en: $real ($(du -sh "$real" 2>/dev/null | cut -f1))"
    read -r -p "Escribe BORRAR para confirmar: " r
    if [ "$r" = BORRAR ]; then
      # voces_propias/ es de root (la escribe el contenedor del clonador): se vacía desde un contenedor
      img=shortfast-api; docker image inspect "$img" >/dev/null 2>&1 || img=alpine
      docker run --rm --entrypoint sh -v "$real":/d "$img" -c 'rm -rf /d/* /d/.[!.]* 2>/dev/null; true'
      rmdir "$real" 2>/dev/null || true
      echo "✔ Datos borrados"
    else echo "Cancelado; los datos se conservan."; fi
  else echo "No existe la carpeta de datos «$datos»"; fi
fi

if [ "$IMAGENES" = 1 ]; then
  docker image rm shortfast-api shortfast-panel shortfast-supertonic shortfast-clonador shortfast-edge-tts 2>/dev/null || true
  echo "✔ Imágenes borradas (Kokoro se descarga de fuera y no se toca)"
fi
echo "El .env se conserva (tiene tus claves). Para reinstalar: ./instalar.sh"

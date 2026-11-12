#!/usr/bin/env bash
# Actualiza ShortFast: trae el código nuevo (si es un clon de git) y reinstala con lo ya elegido en .env.
# Los datos, las voces creadas y el .env se conservan.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
if [ -d .git ]; then
  git pull --ff-only || { echo "✘ git pull falló (¿cambios locales?). Revisa 'git status' y repite." >&2; exit 1; }
fi
exec ./instalar.sh -y "$@"

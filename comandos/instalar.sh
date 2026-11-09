#!/bin/bash
# Pone nuevo-short, render-short y guia-short en tu PATH (enlaces simbólicos).
# Uso: ./comandos/instalar.sh            (instala en ~/.local/bin)
#      DESTINO=~/bin ./comandos/instalar.sh
AQUI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DESTINO="${DESTINO:-$HOME/.local/bin}"
mkdir -p "$DESTINO"
for c in nuevo-short render-short guia-short; do
  chmod +x "$AQUI/$c"
  ln -sf "$AQUI/$c" "$DESTINO/$c"
  echo "✅ $DESTINO/$c"
done
case ":$PATH:" in *":$DESTINO:"*) ;; *) echo "⚠ $DESTINO no está en tu PATH. Añade a ~/.bashrc:  export PATH=\"$DESTINO:\$PATH\"" ;; esac

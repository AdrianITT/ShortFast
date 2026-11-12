#!/usr/bin/env bash
# Registra ShortFast como UNA app de CasaOS generada desde docker-compose.yml (sin un segundo archivo que mantener).
#   scripts/casaos.sh instalar      # instala o aplica cambios (las imágenes deben estar construidas: docker compose build)
#   scripts/casaos.sh desinstalar   # quita la app; nunca borra datos (--no-remove-config)
# Lo usan instalar.sh y desinstalar.sh; no hace falta llamarlo a mano.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")/.."
command -v casaos-cli >/dev/null || { echo "✘ No está casaos-cli" >&2; exit 1; }
leer_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }
APP="${COMPOSE_PROJECT_NAME:-$(leer_env COMPOSE_PROJECT_NAME)}"; APP="${APP:-shortfast}"
instalada() { casaos-cli app-management list apps 2>/dev/null | awk 'NR>2 {print $1}' | grep -qx "$APP"; }

case "${1:-}" in
  instalar)
    command -v python3 >/dev/null || { echo "✘ Hace falta python3 para generar la app de CasaOS" >&2; exit 1; }
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT; chmod 700 "$tmp"  # lleva las claves ya resueltas
    docker compose config --format json > "$tmp/compose.json"
    APP="$APP" PANEL_PORT="$(leer_env PANEL_PORT)" python3 - "$tmp/compose.json" "$tmp/app.yml" <<'EOF'
import json, os, sys
c = json.load(open(sys.argv[1]))
c["name"] = os.environ["APP"]
for nombre, s in c["services"].items():
    s.pop("profiles", None)  # `config` ya dejó solo las voces elegidas; CasaOS no activa perfiles y las saltaría
    if s.pop("build", None) is not None:   # CasaOS no construye: usa las imágenes ya construidas en este equipo
        s["pull_policy"] = "never"
c["x-casaos"] = {
    "author": "self", "category": "self", "hostname": "", "scheme": "http", "index": "/",
    "port_map": os.environ.get("PANEL_PORT") or "8090", "store_app_id": os.environ["APP"],
    "main": "panel", "is_uncontrolled": False,
    "title": {"custom": "ShortFast", "en_us": "ShortFast"},
    "description": {"en_us": "Shorts y video largo con ffmpeg: panel web, API de render y voces locales."},
}
json.dump(c, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)  # JSON es YAML válido
EOF
    # validar primero (install comprueba puertos libres; en una app ya instalada sus puertos son suyos: apply)
    if instalada; then accion=(apply "$APP"); else accion=(install); fi
    casaos-cli app-management "${accion[@]}" -f "$tmp/app.yml" --dry-run >/dev/null
    casaos-cli app-management "${accion[@]}" -f "$tmp/app.yml"
    # CasaOS aplica en segundo plano y puede tardar varios minutos (en este equipo, ~5 la primera vez):
    # esperar a que el panel esté en marcha antes de devolver el control
    echo "• Esperando a que CasaOS cree los contenedores (puede tardar varios minutos)…"
    for _ in $(seq 1 300); do
      [ "$(docker ps --filter "label=com.docker.compose.project=$APP" --filter name=panel -q | wc -l)" -gt 0 ] && break; sleep 2
    done
    echo "✔ App de CasaOS «$APP» registrada"
    ;;
  desinstalar)
    if instalada; then
      casaos-cli app-management uninstall "$APP" --no-remove-config
      for _ in $(seq 1 60); do [ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$APP")" ] && break; sleep 2; done
      echo "✔ App de CasaOS «$APP» quitada (datos intactos)"
    fi
    ;;
  *) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac

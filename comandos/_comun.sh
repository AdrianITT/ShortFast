# Configuración compartida por los comandos. Se carga con `source`; no se ejecuta sola.
# Prioridad: variables de entorno > .env de la raíz del proyecto > valores por defecto.

RAIZ="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"

# Lee una clave del .env sin ejecutarlo (los valores nunca se interpretan como código).
_env() {
  local clave="$1" defecto="$2" actual="${!1}" linea
  [ -n "$actual" ] && { printf '%s' "$actual"; return; }
  if [ -f "$RAIZ/.env" ]; then
    linea="$(grep -E "^[[:space:]]*${clave}=" "$RAIZ/.env" | tail -n1)"
    if [ -n "$linea" ]; then
      linea="${linea#*=}"; linea="${linea%% #*}"; linea="${linea%\"}"; linea="${linea#\"}"
      [ -n "$linea" ] && { printf '%s' "$linea"; return; }
    fi
  fi
  printf '%s' "$defecto"
}

DATA_DIR="$(_env DATA_DIR datos)"
case "$DATA_DIR" in /*) ;; ~*) DATA_DIR="${DATA_DIR/#\~/$HOME}" ;; *) DATA_DIR="$RAIZ/$DATA_DIR" ;; esac
PROYECTOS="$DATA_DIR/proyectos"
SALIDA="$DATA_DIR/salida"
PLANTILLA="$DATA_DIR/plantilla"
API_CONTENEDOR="$(_env API_CONTENEDOR "")"

# Ejecuta un comando dentro del contenedor de la API.
# Con API_CONTENEDOR definido usa ese contenedor; si no, el servicio de docker compose.
en_api() {
  if [ -n "$API_CONTENEDOR" ]; then
    docker exec "$API_CONTENEDOR" "$@"
  else
    docker compose -f "$RAIZ/docker-compose.yml" exec -T ffmpeg-api "$@"
  fi
}

#!/usr/bin/env bash
# Instala (o actualiza, si se repite) ShortFast con Docker: API de render, panel web y las voces elegidas.
# Uso:
#   ./instalar.sh                                   # pregunta lo necesario
#   ./instalar.sh -y                                # sin preguntas (usa .env o los valores por defecto)
#   ./instalar.sh --voces supertonic,clonador --datos /DATA/video-editor --casaos
# Opciones: --voces LISTA  --datos RUTA  --casaos | --sin-casaos  -y|--si  -h|--ayuda
# Guía completa: GUIA_INSTALACION.md
set -euo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$RAIZ"
VOCES_VALIDAS="supertonic clonador kokoro edge"
TODOS_LOS_PERFILES="supertonic,clonador,kokoro,edge"
VOCES="" DATOS="" CASAOS="" SI=0

ok()    { printf '\033[32m✔\033[0m %s\n' "$*"; }
info()  { printf '\033[36m•\033[0m %s\n' "$*"; }
aviso() { printf '\033[33m⚠\033[0m %s\n' "$*" >&2; }
error() { printf '\033[31m✘ %s\033[0m\n' "$*" >&2; exit 1; }
preguntar() {  # preguntar "texto" "por defecto" -> respuesta (con -y devuelve el valor por defecto)
  local r; if [ "$SI" = 1 ] || [ ! -t 0 ]; then echo "$2"; return; fi
  read -r -p "$1 [$2]: " r; echo "${r:-$2}"
}
leer_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }
poner_env() {  # poner_env CLAVE VALOR: reemplaza la línea o la añade; nunca toca el resto del archivo
  if grep -qE "^$1=" .env; then
    local tmp; tmp="$(mktemp)"; awk -v k="$1" -v v="$2" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' .env > "$tmp"
    cat "$tmp" > .env; rm -f "$tmp"
  else printf '%s=%s\n' "$1" "$2" >> .env; fi
}
dc() { docker compose "$@"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --voces) VOCES="${2:?falta la lista de voces}"; shift 2 ;;
    --datos) DATOS="${2:?falta la ruta}"; shift 2 ;;
    --casaos) CASAOS=si; shift ;;
    --sin-casaos) CASAOS=no; shift ;;
    -y|--si) SI=1; shift ;;
    -h|--ayuda) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) error "Opción desconocida: $1 (usa --ayuda)" ;;
  esac
done

echo "== ShortFast: instalación =="

# ── 1. Comprobaciones ──
command -v docker >/dev/null || error "No está Docker. En Ubuntu/Debian: curl -fsSL https://get.docker.com | sh  (ver GUIA_INSTALACION.md)"
docker compose version >/dev/null 2>&1 || error "Falta 'docker compose' (plugin v2). Instala docker-compose-plugin."
docker info >/dev/null 2>&1 || error "No puedo usar Docker con tu usuario. Ejecuta: sudo usermod -aG docker \$USER  y vuelve a entrar en la sesión."
[ "$(uname -m)" = "x86_64" ] || error "Solo está probado en equipos x86_64 (este es $(uname -m))."
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) y compose disponibles"

# ── 2. .env (nunca se sobrescribe; solo se añaden o cambian las claves de abajo) ──
ENV_NUEVO=0
if [ ! -f .env ]; then cp .env.example .env; chmod 600 .env; ENV_NUEVO=1; ok ".env creado desde .env.example"; else info "Uso el .env existente"; fi
[ -n "$VOCES" ] || VOCES="$(leer_env COMPOSE_PROFILES)"
[ -n "$VOCES" ] || VOCES="supertonic,clonador"
VOCES="$(preguntar "Voces a instalar ($VOCES_VALIDAS)" "$VOCES" | tr -d ' ')"
for v in ${VOCES//,/ }; do case " $VOCES_VALIDAS " in *" $v "*) ;; *) error "Voz desconocida: $v (válidas: $VOCES_VALIDAS)";; esac; done
case ",$VOCES," in *,clonador,*) case ",$VOCES," in *,supertonic,*) ;; *) VOCES="supertonic,$VOCES"; info "El clonador necesita Supertonic: lo añado";; esac;; esac
poner_env COMPOSE_PROFILES "$VOCES"

if [ -z "$DATOS" ]; then  # sin --datos: la del .env; en la primera instalación con CasaOS se propone /DATA/shortfast
  DATOS="$(leer_env DATA_DIR)"; DATOS="${DATOS:-./datos}"
  if [ "$ENV_NUEVO" = 1 ] && [ -d /DATA ] && command -v casaos-cli >/dev/null; then DATOS="/DATA/shortfast"; fi
  DATOS="$(preguntar "Carpeta de datos (proyectos, videos, voces)" "$DATOS")"
fi
poner_env DATA_DIR "$DATOS"
mkdir -p "$DATOS" 2>/dev/null || aviso "No pude crear $DATOS con tu usuario; Docker la creará"

[ -n "$(leer_env PUID)" ] && [ "$(leer_env PUID)" != "1000" ] || poner_env PUID "$(id -u)"
[ -n "$(leer_env PGID)" ] && [ "$(leer_env PGID)" != "1000" ] || poner_env PGID "$(id -g)"
if [ -z "$(leer_env TTS_API_KEY)" ]; then poner_env TTS_API_KEY "$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"; ok "Clave de los servicios de voz generada (en .env, no se muestra)"; fi
if [ -z "$(leer_env GEMINI_API_KEY)" ] && [ "$SI" = 0 ] && [ -t 0 ]; then
  read -r -s -p "Clave de Gemini para generar guías con IA (opcional, Enter = sin IA): " g; echo
  [ -n "$g" ] && poner_env GEMINI_API_KEY "$g" && ok "Clave de Gemini guardada"
fi
chmod 600 .env

# ── 3. Recursos y puertos ──
ram_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
necesita=600
case ",$VOCES," in *,supertonic,*) necesita=$((necesita+600));; esac
case ",$VOCES," in *,clonador,*) necesita=$((necesita+1000));; esac
case ",$VOCES," in *,kokoro,*) necesita=$((necesita+2300));; esac
[ "$ram_mb" -ge "$necesita" ] || aviso "RAM libre: ${ram_mb} MB; estas voces usan ~${necesita} MB. Puede ir lento o fallar."
disco_mb=$(df -Pm "$RAIZ" | awk 'NR==2 {print $4}')
[ "$disco_mb" -ge 8000 ] || aviso "Disco libre: ${disco_mb} MB; las imágenes ocupan hasta ~6 GB."

proyecto="${COMPOSE_PROJECT_NAME:-$(leer_env COMPOSE_PROJECT_NAME)}"; proyecto="${proyecto:-shortfast}"
puerto_ocupado() {  # libre si nadie escucha o si es un contenedor de este mismo proyecto
  ss -ltnH "( sport = :$1 )" 2>/dev/null | grep -q . || return 1
  docker ps --filter "label=com.docker.compose.project=$proyecto" --format '{{.Ports}}' | grep -q ":$1->" && return 1
  return 0
}
comprobar_puerto() { local p; p="$(leer_env "$1")"; p="${p:-$2}"; ! puerto_ocupado "$p" || error "El puerto $p ($1) está ocupado. Cambia $1 en .env y repite."; }
comprobar_puerto API_PORT 8123; comprobar_puerto PANEL_PORT 8090
case ",$VOCES," in *,supertonic,*) comprobar_puerto SUPERTONIC_PORT 5200;; esac
case ",$VOCES," in *,clonador,*) comprobar_puerto CLONADOR_PORT 5300;; esac
case ",$VOCES," in *,kokoro,*) comprobar_puerto KOKORO_PORT 8880;; esac
case ",$VOCES," in *,edge,*) comprobar_puerto EDGE_TTS_PORT 5050;; esac
ok "Puertos libres"

# ── 4. CasaOS ──
[ -n "$CASAOS" ] || CASAOS="$(leer_env INSTALAR_CASAOS)"  # lo elegido la vez anterior (actualizar.sh lo mantiene)
if [ -z "$CASAOS" ]; then
  if command -v casaos-cli >/dev/null; then
    [ "$(preguntar "CasaOS detectado. ¿Registrar ShortFast como app de CasaOS? (si/no)" si)" = si ] && CASAOS=si || CASAOS=no
  else CASAOS=no; fi
fi
poner_env INSTALAR_CASAOS "$CASAOS"

# ── 5. Construir y arrancar ──
info "Construyendo imágenes (la primera vez tarda: el clonador ~7 min)…"
dc build
if [ "$CASAOS" = si ]; then
  command -v casaos-cli >/dev/null || error "Pediste --casaos pero no está casaos-cli"
  "$RAIZ/scripts/casaos.sh" instalar
else
  dc up -d
  # voces que ya no están en la lista: se paran y se quitan sus contenedores (las imágenes y los datos se quedan)
  for v in $VOCES_VALIDAS; do
    case ",$VOCES," in *",$v,"*) continue;; esac
    s="$v"; [ "$v" = edge ] && s=edge-tts
    COMPOSE_PROFILES="$TODOS_LOS_PERFILES" dc rm -sf "$s" >/dev/null 2>&1 || true
  done
fi

# ── 6. Esperar a que respondan ──
esperar() {  # esperar nombre url segundos
  local i; for i in $(seq 1 "$3"); do curl -fs -o /dev/null "$2" && { ok "$1 listo ($2)"; return 0; }; sleep 2; done
  aviso "$1 no responde en $2 (mira: docker compose logs $1)"; return 1
}
puerto() { local p; p="$(leer_env "$1")"; echo "${p:-$2}"; }
fallos=0
esperar ffmpeg-api "http://localhost:$(puerto API_PORT 8123)/health" 60 || fallos=1
esperar panel "http://localhost:$(puerto PANEL_PORT 8090)/" 60 || fallos=1
case ",$VOCES," in *,supertonic,*) esperar supertonic "http://localhost:$(puerto SUPERTONIC_PORT 5200)/health" 90 || fallos=1;; esac
case ",$VOCES," in *,clonador,*) esperar clonador "http://localhost:$(puerto CLONADOR_PORT 5300)/health" 150 || fallos=1;; esac
case ",$VOCES," in *,kokoro,*) esperar kokoro "http://localhost:$(puerto KOKORO_PORT 8880)/v1/models" 150 || fallos=1;; esac
case ",$VOCES," in *,edge,*) esperar edge-tts "http://localhost:$(puerto EDGE_TTS_PORT 5050)/health" 60 || fallos=1;; esac

ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "== Listo =="
echo "  Panel:  http://${ip:-localhost}:$(puerto PANEL_PORT 8090)"
echo "  API:    http://${ip:-localhost}:$(puerto API_PORT 8123)"
echo "  Voces:  $VOCES"
echo "  Datos:  $(leer_env DATA_DIR)"
[ "$CASAOS" = si ] && echo "  CasaOS: app «ShortFast» en el panel de CasaOS"
echo "  Actualizar: ./actualizar.sh · Desinstalar: ./desinstalar.sh"
[ "$fallos" = 0 ] || { aviso "Algún servicio no respondió a tiempo; puede seguir arrancando. Repite ./instalar.sh -y para comprobar."; exit 1; }

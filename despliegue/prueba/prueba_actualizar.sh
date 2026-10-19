#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Prueba de `asvs actualizar` en una raiz FALSA, sin tocar el servidor.
#
#  systemctl, curl, npm, pip, chown y sleep son dobles que apuntan lo que se
#  les pide; el codigo «nuevo» es un tar hecho aqui. Se comprueba lo que la
#  revision del 16-10-2026 encontro roto:
#
#    A. pip falla        -> no se toca nada: ni se para el estudio ni cambia app/
#    B. npm falla        -> igual, y el error de npm se ENSENA (antes se tragaba)
#    C. la version nueva no contesta en /api/salud -> se vuelve a la anterior
#    D. todo bien        -> codigo nuevo, reglas.json y cache intactos, mandos
#                           instalados, repositorio apuntado; y la configuracion
#                           del servidor al dia: la unidad que cambia se instala
#                           (con daemon-reload) y la que no, ni se toca; el
#                           snippet de nginx nuevo entra (nginx -t y reload); el
#                           sitio que edito certbot queda tal cual; al entorno se
#                           le ANADEN las variables que faltan sin tocar las demas
#    E. nginx -t falla   -> los snippets vuelven a los de antes y nginx no se
#                           recarga; el resto de la actualizacion sigue
#    C (ademas)          -> al deshacer, unidades, lanzador y entorno vuelven
#
#      bash despliegue/prueba/prueba_actualizar.sh
#
#  Hay que correrla como root (asvs lo exige); no escribe fuera de su carpeta
#  temporal: los mandos van a ASVS_BIN, systemd a ASVS_SYSTEMD y nginx a
#  ASVS_NGINX, que apuntan dentro. Un asvs que nombre /etc sin admitirlas NO
#  se corre (la vez anterior, uno sin ASVS_BIN dejo dobles en /usr/local/bin).
# -----------------------------------------------------------------------------
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASVS="${ASVS_A_PROBAR:-$AQUI/../asvs}"
# Un asvs sin ASVS_BIN instalaria sus mandos en /usr/local/bin DE VERDAD
# (paso al comprobar que esta prueba falla con el asvs viejo): no se corre.
grep -q 'ASVS_BIN' "$ASVS" || { echo "este asvs no admite ASVS_BIN: no se prueba, para no tocar /usr/local/bin"; exit 2; }
if grep -q '/etc/systemd' "$ASVS" && ! grep -q 'ASVS_SYSTEMD' "$ASVS"; then
  echo "este asvs escribe en /etc/systemd sin admitir ASVS_SYSTEMD: no se prueba"; exit 2
fi
if grep -q '/etc/nginx' "$ASVS" && ! grep -q 'ASVS_NGINX' "$ASVS"; then
  echo "este asvs escribe en /etc/nginx sin admitir ASVS_NGINX: no se prueba"; exit 2
fi
T="$(mktemp -d "${TMPDIR:-/tmp}/prueba_asvs.XXXXXX")"
trap '[ -n "${ASVS_TRAZA:-}" ] && tail -n 25 "$T/salida"; rm -rf "$T"' EXIT
FALLOS=0
COMPROBACIONES=0

ok() {
  COMPROBACIONES=$((COMPROBACIONES + 1))
  if eval "$1"; then echo "  ok   $2"; else echo "    FALLO: $2"; FALLOS=$((FALLOS + 1)); fi
}

# ------------------------------------------------------------- los dobles
mkdir -p "$T/bin"
cat > "$T/bin/systemctl" <<'EOF'
#!/bin/sh
echo "systemctl $*" >> "$PRUEBA/llamadas"
[ "$1" = "daemon-reload" ] && [ -f "$PRUEBA/daemon_roto" ] && exit 1
exit 0
EOF
cat > "$T/bin/curl" <<'EOF'
#!/bin/sh
destino=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) destino="$2"; shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
case "$url" in
  *codeload*) cp "$PRUEBA/nuevo.tgz" "$destino" ;;
  */api/trabajos*) echo '{"trabajos":[]}' ;;
  */api/salud*)
    # la version «nueva» no arranca si asi lo pide el escenario
    if grep -q v2 "$RAIZ_FALSA/app/app.py" && [ -f "$PRUEBA/nueva_rota" ]; then exit 7; fi
    echo '{"ok":true}' ;;
  */api/health*) echo ok ;;
  *) exit 6 ;;
esac
EOF
cat > "$T/bin/npm" <<'EOF'
#!/bin/sh
echo "npm $* en $(pwd)" >> "$PRUEBA/llamadas"
if [ -f "$PRUEBA/npm_roto" ]; then echo "npm ERR! sin red (falso)" >&2; exit 1; fi
mkdir -p node_modules/nuevo && echo nuevo > node_modules/nuevo/index.js
EOF
cat > "$T/bin/nginx" <<'EOF'
#!/bin/sh
echo "nginx $*" >> "$PRUEBA/llamadas"
[ -f "$PRUEBA/nginx_roto" ] && { echo "nginx: [emerg] falso" >&2; exit 1; }
exit 0
EOF
printf '#!/bin/sh\nexit 0\n' > "$T/bin/chown"
printf '#!/bin/sh\nexit 0\n' > "$T/bin/sleep"
if ! command -v rsync >/dev/null 2>&1; then
  printf '#!/bin/sh\nexec python3 "%s" "$@"\n' "$AQUI/rsync_falso.py" > "$T/bin/rsync"
fi
chmod +x "$T"/bin/*
export PRUEBA="$T" PATH="$T/bin:$PATH"

# --------------------------------------------------- el codigo nuevo (v2)
mkdir -p "$T/fuente/repo-main/motores/reglas" "$T/fuente/repo-main/despliegue/login"
echo "print('v2')" > "$T/fuente/repo-main/app.py"
echo "fastapi" > "$T/fuente/repo-main/requirements.txt"
echo '{"de_fabrica": true}' > "$T/fuente/repo-main/motores/reglas/reglas.json"
echo "login v2" > "$T/fuente/repo-main/despliegue/login/server.js"
printf '#!/bin/sh\necho asvs v2\n' > "$T/fuente/repo-main/despliegue/asvs"
printf '#!/bin/sh\necho clave v2\n' > "$T/fuente/repo-main/despliegue/estudio-clave"
# LAS PLANTILLAS DE VERDAD: las del arbol que se esta probando
DESPL="$AQUI/.."
for f in plantillas.sh as-video-studio.service as-video-login.service \
         asvs-proxy.conf asvs-proxy-largo.conf estudio-edge nginx-sitio.conf; do
  cp "$DESPL/$f" "$T/fuente/repo-main/despliegue/$f"
done
tar -czf "$T/nuevo.tgz" -C "$T/fuente" repo-main

# ---------------------------------------------- una instalacion v1 de pie
montar() {
  local R="$T/raiz"
  rm -rf "$R" "$T/llamadas" "$T/npm_roto" "$T/nueva_rota" "$T/pip_roto" "$T/binarios" \
         "$T/etc" "$T/nginx_roto" "$T/viejo" "$T/daemon_roto"
  mkdir -p "$R/app/motores/reglas" "$R/app/cache" "$R/app/despliegue/login" \
           "$R/login/node_modules/viejo" "$R/login/datos" "$R/datos" "$R/venv/bin" "$T/binarios"
  echo "print('v1')" > "$R/app/app.py"
  echo "solo en v1" > "$R/app/viejo.py"
  echo '{"aprendido": true}' > "$R/app/motores/reglas/reglas.json"
  echo "cache" > "$R/app/cache/algo"
  echo "login v1" > "$R/login/server.js"
  echo "db" > "$R/login/datos/usuarios.db"
  printf 'PORT=3000\nAPP_URL=http://ejemplo.test\nSECRETO=x\n' > "$R/login/.env"
  # el entorno de un servidor viejo: con un valor cambiado a mano y una
  # variable propia, y sin las que trajo una version posterior
  printf 'PUERTO=8110\nESTUDIO_LOTES=3\nPROPIA=la_mia\n' > "$R/datos/entorno"

  # LA CONFIGURACION DEL SISTEMA, en la raiz falsa
  . "$DESPL/plantillas.sh"
  mkdir -p "$T/etc/systemd/system" "$T/etc/nginx/snippets" \
           "$T/etc/nginx/sites-available" "$T/etc/nginx/sites-enabled" "$T/viejo"
  # la unidad del estudio, de una version anterior (sin una linea)
  grep -v '^TimeoutStopSec' "$DESPL/as-video-studio.service" > "$T/viejo/studio.service"
  plantilla_unidad "$T/viejo/studio.service" "$R" studio > "$T/etc/systemd/system/as-video-studio.service"
  # la del login, ya al dia
  plantilla_unidad "$DESPL/as-video-login.service" "$R" studio > "$T/etc/systemd/system/as-video-login.service"
  touch -d '2001-01-01' "$T/etc/systemd/system/as-video-login.service"
  cp "$DESPL/asvs-proxy.conf" "$T/etc/nginx/snippets/"
  touch -d '2001-01-01' "$T/etc/nginx/snippets/asvs-proxy.conf"
  echo "# snippet viejo" > "$T/etc/nginx/snippets/asvs-proxy-largo.conf"
  cp "$T/etc/nginx/snippets/asvs-proxy-largo.conf" "$T/viejo/largo.conf"
  # el sitio, como lo deja certbot --nginx despues del instalador
  plantilla_sitio "$DESPL/nginx-sitio.conf" ejemplo.test 8110 3000 > "$T/etc/nginx/sites-available/as-video-studio"
  cat >> "$T/etc/nginx/sites-available/as-video-studio" <<'EOF'
    listen 443 ssl http2; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/ejemplo.test/fullchain.pem; # managed by Certbot
server {
    if ($host = ejemplo.test) { return 301 https://$host$request_uri; } # managed by Certbot
}
EOF
  cp "$T/etc/nginx/sites-available/as-video-studio" "$T/viejo/sitio"
  # el lanzador del navegador, de una version anterior
  printf '#!/bin/sh\nexec /usr/bin/navegador-falso --no-sandbox "$@"\n' > "$T/binarios/estudio-edge"
  cp "$T/binarios/estudio-edge" "$T/viejo/edge"
  cp "$R/datos/entorno" "$T/viejo/entorno"
  cat > "$R/venv/bin/pip" <<'EOF'
#!/bin/sh
echo "pip $*" >> "$PRUEBA/llamadas"
[ -f "$PRUEBA/pip_roto" ] && { echo "ERROR: sin red (falso)" >&2; exit 1; }
exit 0
EOF
  chmod +x "$R/venv/bin/pip"
  touch "$T/llamadas"
}

correr() {
  ASVS_RAIZ="$T/raiz" RAIZ_FALSA="$T/raiz" ASVS_BIN="$T/binarios" ASVS_REPO="yo/estudio" \
    ASVS_SYSTEMD="$T/etc/systemd/system" ASVS_NGINX="$T/etc/nginx" ASVS_FUENTES="/fuentes/falsas" \
    bash ${ASVS_TRAZA:-} "$ASVS" actualizar > "$T/salida" 2>&1
}

echo "[A] pip falla: no se toca nada"
montar; touch "$T/pip_roto"; correr; codigo=$?
ok '[ $codigo -ne 0 ]' "sale con error"
ok 'grep -q "v1" "$T/raiz/app/app.py"' "el codigo sigue siendo el de antes"
ok '! grep -q "systemctl stop" "$T/llamadas"' "y el estudio no se ha parado"

echo "[B] npm falla: no se toca nada, y se dice por que"
montar; touch "$T/npm_roto"; correr; codigo=$?
ok '[ $codigo -ne 0 ]' "sale con error"
ok 'grep -q "v1" "$T/raiz/app/app.py" && grep -q "login v1" "$T/raiz/login/server.js"' \
   "el codigo y el login siguen como estaban"
ok '! grep -q "systemctl stop" "$T/llamadas"' "y el estudio no se ha parado"
ok 'grep -q "npm ERR! sin red" "$T/salida"' "el error de npm se ensena, no se traga"

echo "[C] la version nueva no contesta: se vuelve a la anterior"
montar; touch "$T/nueva_rota"; correr; codigo=$?
ok '[ $codigo -ne 0 ]' "sale con error"
ok 'grep -q "v1" "$T/raiz/app/app.py" && [ -f "$T/raiz/app/viejo.py" ]' \
   "el codigo vuelve a ser el de antes, entero"
ok 'grep -q "login v1" "$T/raiz/login/server.js" && [ -d "$T/raiz/login/node_modules/viejo" ]' \
   "y el login con sus librerias de antes"
ok 'grep -q aprendido "$T/raiz/app/motores/reglas/reglas.json"' "reglas.json intacto"
ok '[ -f "$T/raiz/login/datos/usuarios.db" ] && grep -q SECRETO "$T/raiz/login/.env"' \
   "los datos y el .env del login, intactos"
ok '[ ! -f "$T/binarios/asvs" ]' "y no se instalan los mandos de la version rota"
ok '[ "$(grep -c "systemctl restart" "$T/llamadas")" -ge 2 ]' "se re-arranca tras deshacer"
ok 'cmp -s "$T/etc/systemd/system/as-video-studio.service" <(plantilla_unidad "$T/viejo/studio.service" "$T/raiz" studio)' \
   "la unidad vuelve a la de antes"
ok 'cmp -s "$T/etc/nginx/snippets/asvs-proxy-largo.conf" "$T/viejo/largo.conf"' "el snippet, al de antes"
ok 'cmp -s "$T/binarios/estudio-edge" "$T/viejo/edge" && cmp -s "$T/raiz/datos/entorno" "$T/viejo/entorno"' \
   "y el lanzador y el entorno, como estaban"
ok '[ "$(grep -c "systemctl daemon-reload" "$T/llamadas")" -ge 2 ]' "con daemon-reload tambien al deshacer"

echo "[D] todo bien"
montar; correr; codigo=$?
ok '[ $codigo -eq 0 ]' "sale bien ($(tail -n 3 "$T/salida" | tr '\n' ' '))"
ok 'grep -q "v2" "$T/raiz/app/app.py" && [ ! -f "$T/raiz/app/viejo.py" ]' "el codigo es el nuevo"
ok 'grep -q aprendido "$T/raiz/app/motores/reglas/reglas.json"' "reglas.json no se pisa"
ok '[ -f "$T/raiz/app/cache/algo" ]' "la cache sigue"
ok 'grep -q "login v2" "$T/raiz/login/server.js" && [ -d "$T/raiz/login/node_modules/nuevo" ]' \
   "el login nuevo, con las librerias instaladas"
ok '[ -f "$T/raiz/login/datos/usuarios.db" ] && grep -q SECRETO "$T/raiz/login/.env"' \
   "los datos y el .env del login, intactos"
ok '[ ! -d "$T/raiz/app/despliegue/login/node_modules" ]' "las librerias no se cuelan en app/"
ok '[ -x "$T/binarios/asvs" ] && [ -x "$T/binarios/estudio-clave" ]' "los mandos, instalados"
ok 'grep -q "yo/estudio" "$T/raiz/datos/repositorio"' "y se apunta de donde vino"
ok '[ "$(grep -n "pip install" "$T/llamadas" | head -1 | cut -d: -f1)" -lt "$(grep -n "systemctl stop" "$T/llamadas" | head -1 | cut -d: -f1)" ]' \
   "pip va ANTES de parar el estudio"
# la profundidad 2.5D (18-10): su pip de onnxruntime tambien va antes de parar
# (sin red son minutos de reintentos y no pueden ser minutos de web caida), y
# una descarga del modelo que falla no para la actualizacion (ya sale bien arriba)
ok '! grep -q "onnxruntime" "$T/llamadas" || [ "$(grep -n "onnxruntime" "$T/llamadas" | tail -1 | cut -d: -f1)" -lt "$(grep -n "systemctl stop" "$T/llamadas" | head -1 | cut -d: -f1)" ]' \
   "la librería de la profundidad, también antes de parar"
ok 'grep -q "onnxruntime" "$T/llamadas"' "y se intenta instalar si falta"
ok 'cmp -s "$T/etc/systemd/system/as-video-studio.service" <(plantilla_unidad "$DESPL/as-video-studio.service" "$T/raiz" studio)' \
   "la unidad que cambio se instala nueva"
ok 'grep -q "systemctl daemon-reload" "$T/llamadas"' "y se hace daemon-reload"
ok '[ "$(grep -n "daemon-reload" "$T/llamadas" | head -1 | cut -d: -f1)" -lt "$(grep -n "systemctl restart" "$T/llamadas" | head -1 | cut -d: -f1)" ]' \
   "antes de re-arrancar los servicios"
ok '[ "$(date -r "$T/etc/systemd/system/as-video-login.service" +%Y)" = 2001 ]' \
   "la unidad que no cambia ni se toca"
ok 'cmp -s "$T/etc/nginx/snippets/asvs-proxy-largo.conf" "$DESPL/asvs-proxy-largo.conf" && [ "$(date -r "$T/etc/nginx/snippets/asvs-proxy.conf" +%Y)" = 2001 ]' \
   "el snippet que cambio entra; el otro, ni se toca"
ok 'grep -q "nginx -t" "$T/llamadas" && grep -q "systemctl reload nginx" "$T/llamadas"' "nginx -t y reload"
ok 'cmp -s "$T/etc/nginx/sites-available/as-video-studio" "$T/viejo/sitio"' \
   "el sitio que edito certbot queda tal cual (443, certificado, redireccion)"
ok 'grep -q "^exec /usr/bin/navegador-falso --no-sandbox --disable-dev-shm-usage" "$T/binarios/estudio-edge"' \
   "el lanzador del navegador, al dia y con el MISMO navegador"
ok 'grep -qx "ESTUDIO_LOTES=3" "$T/raiz/datos/entorno" && grep -qx "PROPIA=la_mia" "$T/raiz/datos/entorno" && [ "$(grep -c "^PUERTO=" "$T/raiz/datos/entorno")" = 1 ] && [ "$(grep -c "^ESTUDIO_LOTES=" "$T/raiz/datos/entorno")" = 1 ]' \
   "el entorno conserva lo que tenia (ESTUDIO_LOTES=3, PROPIA, un solo PUERTO)"
ok 'grep -qx "ESTUDIO_EDGE=/usr/local/bin/estudio-edge" "$T/raiz/datos/entorno" && grep -qx "HOME=$T/raiz/home" "$T/raiz/datos/entorno"' \
   "y se le anaden las variables que faltaban"
ok '[ -f "$T/raiz/anterior/config/lista" ] && [ "$(wc -l < "$T/raiz/anterior/config/lista")" -ge 4 ]' \
   "con copia de cada fichero cambiado en anterior/config"

echo "[E] nginx -t falla: los snippets vuelven y nginx sigue como estaba"
montar; touch "$T/nginx_roto"; correr; codigo=$?
ok '[ $codigo -eq 0 ]' "la actualizacion del codigo sigue adelante"
ok 'cmp -s "$T/etc/nginx/snippets/asvs-proxy-largo.conf" "$T/viejo/largo.conf"' "el snippet vuelve al de antes"
ok '! grep -q "systemctl reload nginx" "$T/llamadas"' "y nginx no se recarga"
ok 'grep -q "nginx NO acepta" "$T/salida"' "y se dice claramente"
ok 'cmp -s "$T/etc/nginx/sites-available/as-video-studio" "$T/viejo/sitio"' "el sitio, intacto"

echo "[F] falla algo al poner la configuracion (daemon-reload): se deshace y el estudio vuelve"
montar; touch "$T/daemon_roto"; correr; codigo=$?
ok '[ $codigo -ne 0 ]' "sale con error"
ok 'grep -q "v1" "$T/raiz/app/app.py"' "el codigo vuelve a ser el de antes"
ok 'grep -q "systemctl restart" "$T/llamadas"' "y el estudio se vuelve a arrancar (no se queda parado)"
ok 'cmp -s "$T/etc/systemd/system/as-video-studio.service" <(plantilla_unidad "$T/viejo/studio.service" "$T/raiz" studio)' \
   "con la unidad de antes"

echo "[G] no hay lanzador del navegador: se avisa y se sigue"
montar; rm -f "$T/binarios/estudio-edge"; correr; codigo=$?
ok '[ $codigo -eq 0 ]' "sale bien ($(tail -n 2 "$T/salida" | tr '\n' ' '))"
ok 'grep -q "v2" "$T/raiz/app/app.py"' "con el codigo nuevo"

echo
if [ "$FALLOS" -gt 0 ]; then
  echo "PRUEBA ACTUALIZAR CON FALLOS: $FALLOS de $COMPROBACIONES comprobaciones"
  exit 1
fi
echo "PRUEBA ACTUALIZAR OK: $COMPROBACIONES comprobaciones pasan"

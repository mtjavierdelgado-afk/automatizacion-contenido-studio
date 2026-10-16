#!/usr/bin/env bash
# -----------------------------------------------------------------------------
#  Prueba de `estudio-clave --nueva`: el .env del login se LEE, no se ejecuta.
#
#  estudio-clave corre como root y el .env es del usuario del servicio. Con
#  `. ./.env`, una linea como  X=$(orden)  se ejecutaba como root (revision
#  16-10-2026). Aqui `sudo` es un doble que apunta el entorno que recibe, y el
#  .env lleva dos lineas trampa: ninguna puede dejar su fichero.
#
#      bash despliegue/prueba/prueba_estudio_clave.sh
# -----------------------------------------------------------------------------
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAVE="${CLAVE_A_PROBAR:-$AQUI/../estudio-clave}"
T="$(mktemp -d "${TMPDIR:-/tmp}/prueba_clave.XXXXXX")"
trap 'rm -rf "$T"' EXIT
FALLOS=0
COMPROBACIONES=0
ok() {
  COMPROBACIONES=$((COMPROBACIONES + 1))
  if eval "$1"; then echo "  ok   $2"; else echo "    FALLO: $2"; FALLOS=$((FALLOS + 1)); fi
}

mkdir -p "$T/bin" "$T/login" "$T/claves"
cat > "$T/bin/sudo" <<'EOF'
#!/bin/sh
cat > /dev/null
env > "$PRUEBA/entorno_de_node"
exit 0
EOF
chmod +x "$T/bin/sudo"
cat > "$T/login/.env" <<EOF
# un comentario
NODE_ENV=production
DATA_DIR=$T/login/datos
SESSION_SECRET="con comillas"
TRAMPA=\$(touch $T/ejecutado_1)
\`touch $T/ejecutado_2\`
OTRA=1; touch $T/ejecutado_3
PATH=$T/trampa
LD_PRELOAD=$T/trampa.so
SUDO_BIN=$T/trampa_sudo
EOF

PRUEBA="$T" ESTUDIO_SUDO="$T/bin/sudo" ESTUDIO_LOGIN_APP="$T/login" ESTUDIO_USUARIO=nadie \
  ESTUDIO_CLAVES="$T/claves" bash "$CLAVE" --nueva prueba < /dev/null > "$T/salida" 2>&1
codigo=$?

ok '[ $codigo -eq 0 ]' "cambia la contrasena ($(tail -n 1 "$T/salida"))"
ok '[ ! -e "$T/ejecutado_1" ] && [ ! -e "$T/ejecutado_2" ] && [ ! -e "$T/ejecutado_3" ]' \
   "ninguna linea del .env se ejecuta como orden"
ok 'grep -qx "DATA_DIR=$T/login/datos" "$T/entorno_de_node"' "node recibe DATA_DIR del .env"
ok 'grep -qx "SESSION_SECRET=con comillas" "$T/entorno_de_node"' "con las comillas quitadas"
ok 'grep -qx "NODE_ENV=production" "$T/entorno_de_node"' "y el resto de variables"
ok '[ -f "$T/claves/clave-prueba.txt" ]' "y guarda la copia de la contrasena"
ok '! grep -q "^LD_PRELOAD=" "$T/entorno_de_node" && ! grep -q "^PATH=$T/trampa" "$T/entorno_de_node"' \
   "ni PATH ni LD_PRELOAD del .env llegan a sudo (escalada a root)"

echo
if [ "$FALLOS" -gt 0 ]; then
  echo "PRUEBA ESTUDIO-CLAVE CON FALLOS: $FALLOS de $COMPROBACIONES comprobaciones"
  exit 1
fi
echo "PRUEBA ESTUDIO-CLAVE OK: $COMPROBACIONES comprobaciones pasan"

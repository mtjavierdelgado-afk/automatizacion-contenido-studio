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
#                           instalados, repositorio apuntado
#
#      bash despliegue/prueba/prueba_actualizar.sh
#
#  Hay que correrla como root (asvs lo exige); no escribe fuera de su carpeta
#  temporal: los mandos van a ASVS_BIN, que apunta dentro.
# -----------------------------------------------------------------------------
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASVS="${ASVS_A_PROBAR:-$AQUI/../asvs}"
# Un asvs sin ASVS_BIN instalaria sus mandos en /usr/local/bin DE VERDAD
# (paso al comprobar que esta prueba falla con el asvs viejo): no se corre.
grep -q 'ASVS_BIN' "$ASVS" || { echo "este asvs no admite ASVS_BIN: no se prueba, para no tocar /usr/local/bin"; exit 2; }
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
tar -czf "$T/nuevo.tgz" -C "$T/fuente" repo-main

# ---------------------------------------------- una instalacion v1 de pie
montar() {
  local R="$T/raiz"
  rm -rf "$R" "$T/llamadas" "$T/npm_roto" "$T/nueva_rota" "$T/pip_roto" "$T/binarios"
  mkdir -p "$R/app/motores/reglas" "$R/app/cache" "$R/app/despliegue/login" \
           "$R/login/node_modules/viejo" "$R/login/datos" "$R/datos" "$R/venv/bin" "$T/binarios"
  echo "print('v1')" > "$R/app/app.py"
  echo "solo en v1" > "$R/app/viejo.py"
  echo '{"aprendido": true}' > "$R/app/motores/reglas/reglas.json"
  echo "cache" > "$R/app/cache/algo"
  echo "login v1" > "$R/login/server.js"
  echo "db" > "$R/login/datos/usuarios.db"
  printf 'PORT=3000\nAPP_URL=http://ejemplo.test\nSECRETO=x\n' > "$R/login/.env"
  echo "PUERTO=8110" > "$R/datos/entorno"
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

echo
if [ "$FALLOS" -gt 0 ]; then
  echo "PRUEBA ACTUALIZAR CON FALLOS: $FALLOS de $COMPROBACIONES comprobaciones"
  exit 1
fi
echo "PRUEBA ACTUALIZAR OK: $COMPROBACIONES comprobaciones pasan"

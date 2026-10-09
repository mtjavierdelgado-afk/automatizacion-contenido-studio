#!/usr/bin/env bash
# Las suites en seco, con una linea por suite. El gemelo de pruebas.ps1 para
# Linux (el VPS, o un clon en cualquier maquina sin PowerShell).
#
#     bash pruebas.sh
#     PYTHON=/opt/as-video-studio/venv/bin/python bash pruebas.sh
#     bash pruebas.sh --solo prueba_api.py      # una suite suelta
#
# Lo mismo que avisa pruebas.ps1 vale aqui:
#   - prueba_pasos_visuales necesita el navegador (ESTUDIO_EDGE, o
#     microsoft-edge / google-chrome en el PATH). Sin el, falla diciendolo.
#   - prueba_pasos_voz sale a Cartesia de verdad SI hay clave.
#   - prueba_login llama al CLI de claude de verdad.
#   - NINGUNA paga una imagen (ver la cabecera de pasos/prueba_piezas.py).
#
# Codigos de salida de cada suite: 0 bien, 3 sin cupo de la suscripcion de
# Claude (se dice y NO se cuenta como fallo), cualquier otro es un fallo.
set -u

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x /opt/as-video-studio/venv/bin/python ]; then
    PYTHON=/opt/as-video-studio/venv/bin/python
  else
    PYTHON="$(command -v python3 || command -v python || true)"
  fi
fi
[ -n "$PYTHON" ] || { echo "no encuentro python: pasalo con PYTHON=/ruta/a/python"; exit 2; }
echo "interprete: $PYTHON"

TMP_BASE="${TMPDIR:-/tmp}"
# La carpeta que prueba_pasos_visuales reutiliza entre ejecuciones: si una
# pasada se corto a medias, la siguiente fallaria por estado sucio.
sucio="$TMP_BASE/estudio_prueba_visual"
rm -rf "$sucio" 2>/dev/null
[ -e "$sucio" ] && echo "AVISO  no se ha podido borrar $sucio: prueba_pasos_visuales puede fallar por estado sucio."

# El historico de tiempos, a una copia para toda la tanda (ver pruebas.ps1).
export ESTUDIO_ESTADISTICAS="$TMP_BASE/estudio_pruebas_estadisticas.json"
rm -f "$ESTUDIO_ESTADISTICAS"

suites=(
  prueba_api.py prueba_coste_capturas.py
  nucleo/prueba_nucleo.py nucleo/prueba_adversarial.py
  nucleo/prueba_manifiestos.py
  pasos/prueba_ajustes.py pasos/prueba_login.py
  pasos/prueba_asistente.py pasos/prueba_salud_cli.py
  pasos/prueba_enrutar_estilo.py
  pasos/prueba_p1.py pasos/prueba_p2.py pasos/prueba_p3.py
  pasos/prueba_cta.py
  pasos/prueba_pasos_guion.py pasos/prueba_marcas_tts.py
  pasos/prueba_pasos_voz.py pasos/prueba_pasos_visuales.py
  pasos/prueba_repaso.py
  pasos/prueba_piezas.py pasos/prueba_conservar.py
  pasos/prueba_encuadres.py pasos/prueba_presets.py
  pasos/prueba_presets_light.py
)

if [ "${1:-}" = "--solo" ] && [ -n "${2:-}" ]; then
  suites=("$2")
fi

fallos=0
for s in "${suites[@]}"; do
  salida="$("$PYTHON" "$s" 2>&1)"
  codigo=$?
  if [ "$codigo" -eq 0 ]; then
    linea="$(printf '%s\n' "$salida" | grep -E 'comprobaciones|pasan' | tail -1)"
    printf 'OK    %-32s %s\n' "$s" "$(echo "$linea" | sed 's/^[[:space:]]*//')"
  elif [ "$codigo" -eq 3 ]; then
    linea="$(printf '%s\n' "$salida" | grep -m1 'CUPO' || echo 'sin cupo de suscripcion')"
    printf 'CUPO  %-32s %s\n' "$s" "$linea"
  else
    fallos=$((fallos + 1))
    printf 'FALLA %-32s (codigo %s)\n' "$s" "$codigo"
    printf '%s\n' "$salida" | tail -14 | sed 's/^/        /'
  fi
done

# Las herramientas de analisis: una llamada a algo que ya no existe y una
# funcion que nadie alcanza son fallos que ninguna prueba ve.
echo
for h in herramientas/indefinidos_py.py herramientas/indefinidos_js.py \
         herramientas/huerfanas_js.py herramientas/sin_llamar_js.py \
         herramientas/alcanzables_js.py herramientas/atributos_py.py \
         herramientas/plantillas_py.py herramientas/repetidas_py.py \
         herramientas/css_sin_usar.py; do
  [ -f "$h" ] || continue
  resumen="$("$PYTHON" "$h" 2>&1 | grep -m1 -E ':|NO |NADIE|SOSPECHOSAS' || echo 'sin nada que decir')"
  printf 'ANAL  %-32s %s\n' "$h" "$resumen"
done

echo
if [ "$fallos" -gt 0 ]; then
  echo "$fallos suite(s) EN ROJO"
  exit 1
fi
echo "todas las suites en verde"
exit 0

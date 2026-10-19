# -----------------------------------------------------------------------------
#  Las plantillas de la configuracion del servidor, en UN sitio.
#
#  Las usan `instalar.sh` (al instalar) y `asvs actualizar` (para traer al dia
#  lo que cambie de una version a otra). Antes solo existian dentro del
#  instalador, asi que una unidad de systemd o un snippet de nginx nuevos no
#  llegaban NUNCA a un servidor ya instalado (revision 16-10-2026).
#
#  Solo define funciones: no escribe nada. Cada una saca el fichero por la
#  salida estandar y quien llama decide donde va.
#
#  LO QUE NO ESTA AQUI, A PROPOSITO: el sitio de nginx
#  (/etc/nginx/sites-available/as-video-studio). El instalador lo escribe desde
#  `nginx-sitio.conf` y despues `certbot --nginx` lo EDITA EN SU SITIO (el
#  `listen 443 ssl`, las lineas `ssl_certificate` y el bloque que redirige de
#  http a https), y `_http2` le anade `http2`. Regenerarlo borraria el
#  certificado. Lo que cambie de proxy va en los snippets, que si son enteros
#  del instalador.
# -----------------------------------------------------------------------------

# Los snippets de nginx que incluye el sitio. Se instalan tal cual.
SNIPPETS_NGINX="asvs-proxy.conf asvs-proxy-largo.conf"

# Las dos unidades de systemd.
UNIDADES="as-video-studio as-video-login"

# plantilla_unidad <plantilla.service> <raiz> <usuario>
plantilla_unidad() {
  sed "s|/opt/as-video-studio|$2|g; s|^User=studio|User=$3|; s|^Group=studio|Group=$3|" "$1"
}

# plantilla_edge <plantilla estudio-edge> <binario del navegador>
plantilla_edge() {
  sed "s|__NAVEGADOR__|$2|" "$1"
}

# plantilla_sitio <nginx-sitio.conf> <dominio> <puerto estudio> <puerto login>
# (solo la usa el instalador: ver la cabecera)
plantilla_sitio() {
  sed "s|__DOMINIO__|$2|g; s|127\.0\.0\.1:8110|127.0.0.1:$3|g; s|127\.0\.0\.1:3000|127.0.0.1:$4|g" "$1"
}

# plantilla_entorno <raiz> <puerto estudio> <carpeta de fuentes> <lotes>
# El entorno de fabrica del estudio. `asvs actualizar` solo AÑADE las
# variables que falten en el de un servidor; nunca cambia un valor puesto.
plantilla_entorno() {
  cat <<ENTORNO
# El entorno del estudio. Cada variable manda una cosa a su sitio; los datos
# viven fuera del codigo para que actualizar no los toque.
PUERTO=$2
ESTUDIO_PROYECTOS=$1/datos/proyectos
ESTUDIO_PRESETS=$1/datos/presets.json
ESTUDIO_BANCO=$1/datos/banco
ESTUDIO_BANCO_PRESETS=$1/datos/banco/presets
ESTUDIO_SECRETOS=$1/datos/secretos
ESTUDIO_ENV=$1/datos/secretos/.env
ESTUDIO_RECETAS=$1/datos/recetas.json
ESTUDIO_AJUSTES=$1/datos/ajustes.json
ESTUDIO_TARIFAS=$1/datos/tarifas.json
ESTUDIO_ESTADISTICAS=$1/datos/estadisticas.json
ESTUDIO_COSTE_GLOBAL=$1/datos/coste_global.jsonl
ESTUDIO_BITACORA_GLOBAL=$1/datos/bitacora_global.jsonl
ESTUDIO_MOTORES=$1/app/motores
# Las fuentes y el navegador son ficheros del sistema, no datos de nadie. Que
# las fuentes sean LAS MISMAS con las que se midio es el invariante.
ESTUDIO_FUENTES=$3
ESTUDIO_EDGE=/usr/local/bin/estudio-edge
# El modelo de la profundidad 2.5D (lo baja instalar_profundidad, abajo).
ESTUDIO_MODELO_PROFUNDIDAD=$1/datos/modelos/depth_anything_vits14.onnx
HOME=$1/home
# Cuantos planos se rasterizan a la vez. Medido en una maquina de 8 nucleos:
# con 4 procesos van 6,75 fotogramas/s y con 8 van 10,40. La regla automatica
# del estudio pide la mitad de los nucleos y deja media maquina parada.
ESTUDIO_LOTES=$4
ENTORNO
}

# instalar_profundidad <raiz> <usuario>
# LA PROFUNDIDAD 2.5D DEL MONTAJE (18-10-2026): la libreria `onnxruntime` y el
# modelo Depth Anything (vits14, ~99 MB, Apache 2.0) en <raiz>/datos/modelos.
# NUNCA FALLA: sin ella el Studio funciona igual y la casilla dice que falta.
# Por eso no va en requirements.txt: un pip que no encuentra la rueda para esta
# maquina pararia la actualizacion entera por una opcion del montaje.
MODELO_PROFUNDIDAD_URL="https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v1.0.0/depth_anything_vits14.onnx"
MODELO_PROFUNDIDAD_SHA256="21e149bdc73d9173c2dfe0dce9a2b7d0d3bcf9be06440ad987a703b7ce30ea54"
ONNXRUNTIME_VERSION="1.29.0"
instalar_profundidad() {
  local raiz="$1" usuario="$2" carpeta modelo temporal huella
  if ! "$raiz/venv/bin/python" -c "import onnxruntime" >/dev/null 2>&1; then
    "$raiz/venv/bin/pip" install --quiet --timeout 30 --retries 1 "onnxruntime==$ONNXRUNTIME_VERSION" >/dev/null 2>&1 \
      || "$raiz/venv/bin/pip" install --quiet --timeout 30 --retries 1 "onnxruntime<2" >/dev/null 2>&1 \
      || { echo "  (profundidad 2.5D: no se ha podido instalar onnxruntime; el resto va igual)"; return 0; }
  fi
  carpeta="$raiz/datos/modelos"
  modelo="$carpeta/depth_anything_vits14.onnx"
  mkdir -p "$carpeta"
  huella="$(sha256sum "$modelo" 2>/dev/null | cut -d' ' -f1 || true)"
  if [ "$huella" != "$MODELO_PROFUNDIDAD_SHA256" ]; then
    echo "Bajando el modelo de la profundidad 2.5D (unos 100 MB, una sola vez)..."
    temporal="$modelo.bajando"
    # con plazo: una descarga atascada no puede dejar la actualizacion colgada
    if curl -fsSL --connect-timeout 20 --max-time 900 "$MODELO_PROFUNDIDAD_URL" -o "$temporal" \
        && [ "$(sha256sum "$temporal" | cut -d' ' -f1)" = "$MODELO_PROFUNDIDAD_SHA256" ]; then
      mv -f "$temporal" "$modelo"
    else
      rm -f "$temporal"
      echo "  (profundidad 2.5D: no se ha podido bajar el modelo; el resto va igual)"
      return 0
    fi
  fi
  chown -R "$usuario:$usuario" "$carpeta" 2>/dev/null || true
  return 0
}

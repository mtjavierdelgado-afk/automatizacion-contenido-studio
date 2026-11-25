"""Los iconos de Gráficas (rama graficas-3c-extras, 25-11-2026).

Una capa `icono` lleva el id de un icono de `web/iconos/` (Lucide, licencia ISC,
y unos propios), su color (una referencia del Kit, como cualquier capa) y el
grosor del trazo. Se pinta como un SVG con ese color: sin fondo, nítido en
cualquier tamaño y sin pedir nada a internet.

Un icono que ya no esté en la carpeta no rompe nada: la capa se guarda y se
abre igual, y no se pinta (una pieza guardada nunca deja de abrirse).
"""
import base64
import os
import re

CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "iconos")
RE_ID = re.compile(r"^[a-z0-9-]{1,40}$")

#: id -> nombre en español (el orden es el de la pantalla).
NOMBRES = {
    "check": "Check", "x": "Cruz", "circle-check": "Check en círculo", "circle-x": "Cruz en círculo",
    "star": "Estrella", "heart": "Corazón", "thumbs-up": "Me gusta", "smile": "Sonrisa", "sparkles": "Brillos",
    "flame": "Fuego", "zap": "Rayo", "trophy": "Trofeo", "crown": "Corona", "target": "Diana", "rocket": "Cohete",
    "lightbulb": "Idea", "trending-up": "Sube", "percent": "Porcentaje", "tag": "Etiqueta", "ticket": "Entrada",
    "gift": "Regalo", "party-popper": "Fiesta", "cake": "Torta", "music": "Música", "headphones": "Audífonos",
    "gamepad-2": "Mando", "joystick": "Palanca", "tv": "Televisor", "monitor": "Pantalla", "wifi": "Wifi",
    "camera": "Cámara", "phone": "Teléfono", "mail": "Correo", "message-circle": "Mensaje", "map-pin": "Ubicación",
    "clock": "Reloj", "calendar": "Calendario", "truck": "Envío", "house": "Casa", "users": "Personas",
    "user": "Persona", "hand": "Mano", "shield-check": "Garantía", "shopping-cart": "Carrito",
    "credit-card": "Tarjeta", "wallet": "Billetera", "bookmark": "Guardar", "share-2": "Compartir",
    "arrow-right": "Flecha", "arrow-down": "Flecha abajo", "flecha-curva": "Flecha curva",
    "flecha-abajo-curva": "Flecha curva abajo", "info": "Información", "circle-help": "Pregunta",
    "triangle-alert": "Atención",
}
#: De dónde sale cada uno (para el crédito y la licencia).
ORIGEN = {"flecha-curva": "propios", "flecha-abajo-curva": "propios"}

_MEMO = {}


def _ruta(icono):
    return os.path.join(CARPETA, ORIGEN.get(icono, "lucide"), f"{icono}.svg")


def interior(icono):
    """Lo de dentro del <svg> (sus trazos), o "" si ese icono no está."""
    if not isinstance(icono, str) or not RE_ID.fullmatch(icono) or icono not in NOMBRES:
        return ""
    if icono not in _MEMO:
        try:
            with open(_ruta(icono), encoding="utf-8") as fh:
                texto = fh.read()
        except OSError:
            texto = ""
        m = re.search(r"<svg\b[^>]*>(.*)</svg>", texto, re.S)
        cuerpo = m.group(1) if m else ""
        # solo trazos: nada de scripts, enlaces ni estilos que vengan en un fichero raro
        _MEMO[icono] = "" if re.search(r"<(script|style|a|foreignObject|image|use)\b|on\w+=|href", cuerpo, re.I) \
            else " ".join(cuerpo.split())
    return _MEMO[icono]


def catalogo():
    """-> [{id, nombre, svg}] (svg: lo de dentro, para que la pantalla lo pinte)."""
    return [{"id": i, "nombre": n, "svg": interior(i)} for i, n in NOMBRES.items() if interior(i)]


def svg(icono, color_hex, alfa=1.0, grosor=2.0):
    """El SVG entero del icono con su color y su trazo, o "" si no está."""
    dentro = interior(icono)
    if not dentro:
        return ""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color_hex}" stroke-opacity="{alfa:g}" stroke-width="{grosor:g}" '
            f'stroke-linecap="round" stroke-linejoin="round">{dentro}</svg>')


def data_uri(icono, color_hex, alfa=1.0, grosor=2.0):
    cuerpo = svg(icono, color_hex, alfa, grosor)
    return "data:image/svg+xml;base64," + base64.b64encode(cuerpo.encode("utf-8")).decode("ascii") if cuerpo else ""

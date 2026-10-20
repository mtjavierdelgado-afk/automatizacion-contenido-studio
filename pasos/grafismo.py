"""El GRAFISMO: los elementos que se ponen ENCIMA de una imagen para que llame
la atencion (portadas, rama `portadas`) o para que un plano no se haga largo
(dentro del video, rama `elementos-video`).

    svg = grafismo.lienzo(1080, 1920, fondo, [elemento, ...], efectos)
    fragmento = grafismo.elemento({"tipo": "texto", "texto": "DISEÑO", ...}, 1080, 1920)

Por que en capas y no dentro de la imagen
-----------------------------------------
La IA de imagenes escribe mal (letras cambiadas, tildes que no estan) y cada
intento se paga. Un texto en capa sale EXACTO, se cambia gratis y al momento,
y es el mismo motor que pinta los subtitulos y las cartelas del video (el
navegador del render): lo que se ve en la pantalla es lo que sale. La opcion
de que la IA meta el texto dentro existe (ver `portadas.portada_ia`), pero es
la otra, la que se paga.

Las medidas
-----------
Todo elemento va en coordenadas RELATIVAS: `x`, `y` de 0 a 1 sobre el cuadro y
los tamanos como fraccion del lado CORTO (`base`). Asi el mismo diseno sirve en
9:16, 16:9, 4:5 y 1:1 sin rehacerlo: lo que cambia es donde cae, no lo que es.

Las fuentes
-----------
Las de las miniaturas (Anton, Bebas Neue, Luckiest Guy, Bangers, Archivo
Black, Montserrat) son de licencia libre (OFL/Apache) y NO vienen con el
sistema. Se bajan UNA vez al servidor desde el repositorio de Google Fonts
(`asegurar_fuentes`) y van DENTRO del SVG como data URI: un SVG pintado por el
navegador como imagen no carga ficheros de fuera. Si no estan (sin red, o
todavia bajando), cada familia cae a una negrita del sistema y el diseno sale
igual de colocado, con otra letra.
"""
import base64
import hashlib
import math
import os
import re
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

#: Donde se guardan las fuentes bajadas. `ESTUDIO_FUENTES_GRAFISMO` manda; si
#: no, la carpeta de sistema de los proyectos (la pone quien llama con
#: `fijar_carpeta`) y, a falta de todo, una junto a este fichero.
_CARPETA = {"ruta": os.environ.get("ESTUDIO_FUENTES_GRAFISMO") or ""}

_BASE_GF = "https://raw.githubusercontent.com/google/fonts/main/"

#: Las fuentes de impacto: id -> ficha. `ancho` es lo que mide de media una
#: letra MAYUSCULA en fracciones del cuerpo (para partir renglones sin abrir
#: la fuente); se afina con el TTF si esta bajado.
FUENTES = {
    "anton": {"nombre": "Anton", "fichero": "Anton-Regular.ttf",
              "url": _BASE_GF + "ofl/anton/Anton-Regular.ttf", "ancho": 0.46,
              "licencia": "OFL", "que": "condensada y muy gruesa: la de las miniaturas de YouTube"},
    "bebas": {"nombre": "Bebas Neue", "fichero": "BebasNeue-Regular.ttf",
              "url": _BASE_GF + "ofl/bebasneue/BebasNeue-Regular.ttf", "ancho": 0.42,
              "licencia": "OFL", "que": "alta y limpia, muy legible en el movil"},
    "luckiest": {"nombre": "Luckiest Guy", "fichero": "LuckiestGuy-Regular.ttf",
                 "url": _BASE_GF + "apache/luckiestguy/LuckiestGuy-Regular.ttf", "ancho": 0.66,
                 "licencia": "Apache 2.0", "que": "redonda y divertida: fiestas, ninos, juegos"},
    "bangers": {"nombre": "Bangers", "fichero": "Bangers-Regular.ttf",
                "url": _BASE_GF + "ofl/bangers/Bangers-Regular.ttf", "ancho": 0.5,
                "licencia": "OFL", "que": "de comic, inclinada: energia y humor"},
    "archivo": {"nombre": "Archivo Black", "fichero": "ArchivoBlack-Regular.ttf",
                "url": _BASE_GF + "ofl/archivoblack/ArchivoBlack-Regular.ttf", "ancho": 0.7,
                "licencia": "OFL", "que": "ancha y seria: precios, datos, negocios"},
    "montserrat": {"nombre": "Montserrat", "fichero": "Montserrat-Variable.ttf",
                   "url": _BASE_GF + "ofl/montserrat/Montserrat%5Bwght%5D.ttf", "ancho": 0.68,
                   "licencia": "OFL", "peso": 900, "que": "geometrica en su peso mas negro: moderna"},
    "lilita": {"nombre": "Lilita One", "fichero": "LilitaOne-Regular.ttf",
               "url": _BASE_GF + "ofl/lilitaone/LilitaOne-Regular.ttf", "ancho": 0.56,
               "licencia": "OFL", "que": "redonda y pesada: amable, para todo publico"},
    "marker": {"nombre": "Permanent Marker", "fichero": "PermanentMarker-Regular.ttf",
               "url": _BASE_GF + "apache/permanentmarker/PermanentMarker-Regular.ttf", "ancho": 0.62,
               "licencia": "Apache 2.0", "que": "de rotulador: anotaciones a mano, antes/despues"},
    "russo": {"nombre": "Russo One", "fichero": "RussoOne-Regular.ttf",
              "url": _BASE_GF + "ofl/russoone/RussoOne-Regular.ttf", "ancho": 0.64,
              "licencia": "OFL", "que": "tecnologica: gamer, tecnologia"},
    "sistema": {"nombre": "Verdana", "fichero": "", "url": "", "ancho": 0.72,
                "licencia": "del sistema", "que": "la del resto del video (no hay que bajar nada)"},
}

#: A que se cae si la de impacto no esta: negritas que hay en el servidor.
RESPALDO_CSS = "'Arial Black', Impact, 'Verdana', 'DejaVu Sans', sans-serif"

_LOCK = threading.Lock()
_BAJANDO = {"hilo": None}


def fijar_carpeta(ruta):
    """Donde guardar las fuentes bajadas (la llama app.py al arrancar)."""
    if ruta and not os.environ.get("ESTUDIO_FUENTES_GRAFISMO"):
        _CARPETA["ruta"] = ruta


def carpeta_fuentes():
    """FUERA DEL CODIGO a proposito: `asvs actualizar` sincroniza la carpeta del
    codigo con `--delete`, y unas fuentes bajadas ahi se borrarian en cada
    actualizacion (revision 19-10). En la carpeta del usuario del servicio
    duran, y el render (p7) y la pantalla (app.py) ven las mismas."""
    ruta = _CARPETA["ruta"] or os.path.join(os.path.expanduser("~"), ".local", "share",
                                            "estudio", "fuentes_grafismo")
    return os.path.abspath(ruta)


def ruta_fuente(fid):
    ficha = FUENTES.get(fid) or {}
    if not ficha.get("fichero"):
        return ""
    ruta = os.path.join(carpeta_fuentes(), ficha["fichero"])
    return ruta if os.path.isfile(ruta) and os.path.getsize(ruta) > 1000 else ""


def fuentes_estado():
    """Las fuentes para la pantalla: [{id, nombre, que, licencia, lista}]."""
    return [{"id": k, "nombre": v["nombre"], "que": v["que"], "licencia": v["licencia"],
             "lista": k == "sistema" or bool(ruta_fuente(k))} for k, v in FUENTES.items()]


def asegurar_fuentes(descargar=True, tiempo_s=20):
    """Baja las fuentes que falten. -> {id: ruta}. Nunca lanza: una que no baja
    se queda con el respaldo. Las bajadas se escriben de forma atomica."""
    hechas = {}
    if os.environ.get("ESTUDIO_SIN_DESCARGAS"):
        descargar = False
    for fid, ficha in FUENTES.items():
        if not ficha.get("fichero"):
            continue
        ruta = ruta_fuente(fid)
        if ruta:
            hechas[fid] = ruta
            continue
        if not descargar:
            continue
        try:
            import requests                                   # noqa: PLC0415
            r = requests.get(ficha["url"], timeout=tiempo_s)
            datos = r.content if r.status_code == 200 else b""
            # una fuente de verdad empieza por la firma de TrueType u OpenType
            if len(datos) < 1000 or datos[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                continue
            os.makedirs(carpeta_fuentes(), exist_ok=True)
            destino = os.path.join(carpeta_fuentes(), ficha["fichero"])
            temporal = f"{destino}.{os.getpid()}.{threading.get_ident()}.tmp"
            with open(temporal, "wb") as fh:
                fh.write(datos)
            os.replace(temporal, destino)
            hechas[fid] = destino
        except Exception:                                     # noqa: BLE001
            continue
    return hechas


def asegurar_fuentes_en_segundo_plano():
    """Lanza la bajada una vez, sin esperar (la pantalla no se queda colgada)."""
    with _LOCK:
        hilo = _BAJANDO["hilo"]
        if hilo is not None and hilo.is_alive():
            return False
        if all(ruta_fuente(k) for k, v in FUENTES.items() if v.get("fichero")):
            return False
        hilo = threading.Thread(target=asegurar_fuentes, daemon=True, name="fuentes-grafismo")
        _BAJANDO["hilo"] = hilo
        hilo.start()
        return True


def familia_css(fid):
    """La lista CSS de una fuente, con su respaldo detras."""
    ficha = FUENTES.get(fid) or FUENTES["anton"]
    if fid == "sistema":
        return "'Verdana', 'DejaVu Sans', sans-serif"
    return f"'{ficha['nombre']}', {RESPALDO_CSS}"


def peso_css(fid):
    return (FUENTES.get(fid) or {}).get("peso") or (900 if fid in ("sistema", "montserrat") else 400)


_CACHE_B64 = {}


def css_fuentes(ids):
    """El <style> con las @font-face de las fuentes usadas que esten bajadas."""
    reglas = []
    for fid in sorted(set(i for i in ids if i in FUENTES)):
        ruta = ruta_fuente(fid)
        if not ruta:
            continue
        clave = (ruta, os.path.getmtime(ruta))
        if clave not in _CACHE_B64:
            with open(ruta, "rb") as fh:
                _CACHE_B64[clave] = base64.b64encode(fh.read()).decode("ascii")
        reglas.append(f"@font-face{{font-family:'{FUENTES[fid]['nombre']}';"
                      f"src:url(data:font/ttf;base64,{_CACHE_B64[clave]}) format('truetype');}}")
    return f"<style>{''.join(reglas)}</style>" if reglas else ""


# ------------------------------------------------------------------ medir

_MEDIDORES = {}


def _medidor(fid, tam):
    ruta = ruta_fuente(fid)
    if not ruta:
        return None
    clave = (ruta, int(tam))
    if clave not in _MEDIDORES:
        try:
            from PIL import ImageFont                         # noqa: PLC0415
            _MEDIDORES[clave] = ImageFont.truetype(ruta, int(tam))
        except Exception:                                     # noqa: BLE001
            _MEDIDORES[clave] = False
    return _MEDIDORES[clave] or None


def _medidor_respaldo(tam):
    """La negrita del sistema con la que se dibuja cuando falta la de impacto."""
    clave = ("respaldo", int(tam))
    if clave not in _MEDIDORES:
        _MEDIDORES[clave] = False
        try:
            from PIL import ImageFont                         # noqa: PLC0415
            import tipografia                                 # noqa: PLC0415
            for ruta in (tipografia.FUENTES["verdana"][1], tipografia.FUENTES["arial"][1]):
                if os.path.isfile(ruta):
                    _MEDIDORES[clave] = ImageFont.truetype(ruta, int(tam))
                    break
        except Exception:                                     # noqa: BLE001
            pass
    return _MEDIDORES[clave] or None


def medir(texto, fid, tam):
    """Lo que mide de ancho un renglon, en px. Con el TTF si esta; si no, una
    estimacion por la anchura media de la fuente (un poco por lo alto: es
    mejor que sobre sitio a que se salga)."""
    medidor = _medidor(fid, max(4, tam))
    if medidor is None:
        # SIN LA FUENTE BAJADA SE DIBUJA CON EL RESPALDO (una negrita ancha del
        # sistema): se mide con ESA, o un titulo que cabia en Anton se sale
        medidor = _medidor_respaldo(max(4, tam))
    if medidor is not None:
        try:
            return float(medidor.getlength(texto)) * 1.03
        except Exception:                                     # noqa: BLE001
            pass
    ancho = (FUENTES.get(fid) or FUENTES["anton"])["ancho"] if ruta_fuente(fid) else 0.8
    total = 0.0
    for c in str(texto):
        if c == " ":
            total += 0.3
        elif c in "il.,:;!|'":
            total += ancho * 0.45
        elif c.islower():
            total += ancho * 0.88
        else:
            total += ancho
    # con el respaldo (Arial Black/Verdana) las letras son mas anchas que en
    # una condensada: se cuenta con lo peor
    return total * tam * 1.05


def partir(texto, fid, tam, ancho_max):
    palabras = str(texto or "").split()
    lineas, actual = [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if actual and medir(prueba, fid, tam) > ancho_max:
            lineas.append(actual)
            actual = palabra
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return lineas


def encajar(texto, fid, tam, ancho_max, lineas_max=3, minimo=0.1):
    """(lineas, tam): baja el cuerpo hasta que quepa en `lineas_max` renglones
    y ningun renglon (ni una palabra sola) pase de `ancho_max`."""
    tam = float(tam)
    piso = tam * minimo
    while True:
        lineas = partir(texto, fid, tam, ancho_max)
        cabe = len(lineas) <= lineas_max and all(medir(l, fid, tam) <= ancho_max for l in lineas)
        if cabe or tam <= piso:
            return lineas, tam
        tam *= 0.92


# ------------------------------------------------------------------ util

def escapar(texto):
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def color(valor, defecto="#ffffff"):
    valor = str(valor or "").strip()
    return valor if _COLOR.match(valor) else defecto


def _num(valor, defecto, minimo=None, maximo=None):
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return defecto
    if math.isnan(x) or math.isinf(x):
        return defecto
    if minimo is not None:
        x = max(minimo, x)
    if maximo is not None:
        x = min(maximo, x)
    return x


def _uid(el, extra=""):
    return "g" + hashlib.sha1((repr(sorted((el or {}).items())) + extra).encode("utf-8")).hexdigest()[:8]


def luminancia(hexa):
    h = color(hexa, "#000000")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste_de(hexa):
    """Negro o blanco, el que mas se lee sobre `hexa`."""
    return "#111111" if luminancia(hexa) > 0.55 else "#ffffff"


# ------------------------------------------------------------------ el catalogo

#: Los estilos de un texto, que se pueden sumar.
ESTILOS_TEXTO = {
    "contorno": "un trazo grueso alrededor de cada letra: se lee sobre cualquier fondo",
    "sombra": "sombra dura desplazada hacia abajo y a la derecha",
    "brillo": "un halo de luz del color de acento alrededor (neón)",
    "degradado": "relleno en degradado de arriba abajo",
    "extruido": "un relieve 3D de varias capas detras",
    "caja": "un fondo de color detras de cada renglon",
    "inclinado": "inclinado unos grados, con energia",
    "tachado": "una raya roja encima (el precio de antes, el mito)",
}

#: Los elementos que se pueden poner. La pantalla los ofrece desde aqui.
ELEMENTOS = {
    "texto": "Un texto de impacto: título, antetítulo, cifra…",
    "insignia": "Un círculo, estallido o pastilla con texto corto (VS, -50 %, NUEVO, 1)",
    "flecha": "Una flecha gruesa que señala algo",
    "circulo": "Un círculo dibujado a mano alrededor de algo",
    "rayo": "Un rayo de luz que parte la imagen (como en un versus)",
    "icono": "Un icono: estrella, check, cruz, corazón, fuego, dinero, reloj, exclamación, pregunta, rayo, pulgar",
    "etiqueta": "Una pastilla con texto (precio, «GRATIS», «NUEVO»)",
    "banda": "Una banda de color de lado a lado con texto",
    "marco": "Un marco de color alrededor de todo",
    "subrayado": "Un trazo de rotulador bajo una palabra",
    "estrellas": "Cinco estrellas de valoración (testimonios, reseñas)",
    "cinta": "Una cinta cruzada en una esquina (URGENTE, NUEVO, -50 %)",
    "rafaga": "Rayos de sol desde un punto, detrás de todo (energía, celebración)",
}

ICONOS = ("estrella", "check", "cruz", "corazon", "fuego", "dinero", "reloj",
          "exclamacion", "pregunta", "rayo", "pulgar", "flecha")


# ------------------------------------------------------------------ los defs

def defs(uid, acento="#ffd84d"):
    """Filtros y degradados de un elemento, con ids propios (no se pisan)."""
    acento = color(acento, "#ffd84d")
    return (f'<defs>'
            f'<filter id="{uid}-sombra" x="-20%" y="-20%" width="140%" height="160%">'
            f'<feDropShadow dx="0" dy="0.04em" stdDeviation="0" flood-color="#000" flood-opacity="0.85"/>'
            f'</filter>'
            f'<filter id="{uid}-brillo" x="-40%" y="-40%" width="180%" height="180%">'
            f'<feGaussianBlur in="SourceAlpha" stdDeviation="14" result="b"/>'
            f'<feFlood flood-color="{acento}" flood-opacity="0.95"/>'
            f'<feComposite in2="b" operator="in" result="halo"/>'
            f'<feMerge><feMergeNode in="halo"/><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/></feMerge>'
            f'</filter>'
            f'<filter id="{uid}-suave" x="-50%" y="-50%" width="200%" height="200%">'
            f'<feGaussianBlur stdDeviation="6"/></filter>'
            f'</defs>')


# ------------------------------------------------------------------ elementos

def _transformar(interior, cx, cy, rot=0.0, escala=1.0):
    partes = []
    if rot:
        partes.append(f"rotate({rot:.1f} {cx:.1f} {cy:.1f})")
    if escala != 1.0:
        partes.append(f"translate({cx:.1f} {cy:.1f}) scale({escala:.3f}) translate({-cx:.1f} {-cy:.1f})")
    return f'<g transform="{" ".join(partes)}">{interior}</g>' if partes else interior


def texto(el, W, H):
    """Un texto de impacto. Campos: texto, x, y (centro, 0-1), tam (fraccion
    del lado corto), ancho (fraccion del ancho que puede ocupar), lineas,
    fuente, color, contorno (color), estilos [..], acento (para brillo,
    degradado y la palabra resaltada), resaltar [palabras], alinear
    (centro|izquierda|derecha), mayusculas, rot."""
    base = min(W, H)
    contenido = str(el.get("texto") or "").strip()
    if not contenido:
        return ""
    if el.get("mayusculas", True):
        contenido = contenido.upper()
    fid = el.get("fuente") if el.get("fuente") in FUENTES else "anton"
    tam = _num(el.get("tam"), 0.12, 0.02, 0.6) * base
    ancho_max = _num(el.get("ancho"), 0.9, 0.1, 1.0) * W
    lineas_max = int(_num(el.get("lineas"), 2, 1, 6))
    lineas, tam = encajar(contenido, fid, tam, ancho_max, lineas_max)
    x = _num(el.get("x"), 0.5, 0, 1) * W
    y = _num(el.get("y"), 0.5, 0, 1) * H
    alinear = el.get("alinear") if el.get("alinear") in ("izquierda", "derecha") else "centro"
    ancla = {"centro": "middle", "izquierda": "start", "derecha": "end"}[alinear]
    relleno = color(el.get("color"), "#ffffff")
    contorno = color(el.get("contorno"), "#000000")
    acento = color(el.get("acento"), "#ffd84d")
    estilos = set(el.get("estilos") or ["contorno", "sombra"]) & set(ESTILOS_TEXTO)
    resaltar = {re.sub(r"[^\w]", "", str(p).upper()) for p in (el.get("resaltar") or []) if str(p).strip()}
    uid = _uid(el, f"{W}x{H}")
    interlineado = tam * 1.02
    alto_total = interlineado * len(lineas)
    y0 = y - alto_total / 2 + tam * 0.82
    familia = familia_css(fid)
    peso = peso_css(fid)
    grosor = max(2.0, tam * 0.085)
    piezas = [defs(uid, acento)]
    if "degradado" in estilos:
        piezas.append(f'<defs><linearGradient id="{uid}-deg" x1="0" y1="0" x2="0" y2="1">'
                      f'<stop offset="0" stop-color="{relleno}"/>'
                      f'<stop offset="1" stop-color="{acento}"/></linearGradient></defs>')

    def renglon(linea, yy, desplaza=(0, 0), solo_trazo=None, filtro=""):
        trozos = []
        for i, palabra in enumerate(linea.split(" ")):
            llano = re.sub(r"[^\w]", "", palabra)
            rell = acento if llano in resaltar else (f"url(#{uid}-deg)" if "degradado" in estilos else relleno)
            if solo_trazo:
                rell = solo_trazo
            trozos.append(f'<tspan fill="{rell}">{escapar(palabra)}{" " if i < len(linea.split(" ")) - 1 else ""}</tspan>')
        trazo = (f' stroke="{solo_trazo or contorno}" stroke-width="{grosor:.1f}" '
                 f'stroke-linejoin="round" paint-order="stroke"') if ("contorno" in estilos or solo_trazo) else ""
        return (f'<text x="{x + desplaza[0]:.1f}" y="{yy + desplaza[1]:.1f}" text-anchor="{ancla}" '
                f'font-family="{familia}" font-weight="{peso}" font-size="{tam:.1f}" '
                f'letter-spacing="{tam * 0.01:.1f}"{trazo}{filtro} xml:space="preserve">{"".join(trozos)}</text>')

    for n, linea in enumerate(lineas):
        yy = y0 + n * interlineado
        if "caja" in estilos:
            ancho = medir(linea, fid, tam) + tam * 0.5
            x_caja = {"middle": x - ancho / 2, "start": x - tam * 0.25, "end": x - ancho + tam * 0.25}[ancla]
            piezas.append(f'<rect x="{x_caja:.1f}" y="{yy - tam * 0.92:.1f}" width="{ancho:.1f}" '
                          f'height="{tam * 1.08:.1f}" rx="{tam * 0.12:.1f}" fill="{acento}"/>')
        if "extruido" in estilos:
            for k in range(6, 0, -1):
                d = tam * 0.012 * k
                piezas.append(renglon(linea, yy, (d, d), solo_trazo=contorno))
        if "sombra" in estilos:
            d = tam * 0.06
            piezas.append(renglon(linea, yy, (d, d), solo_trazo="#000000").replace(
                "<text ", '<text opacity="0.75" ', 1))
        filtro = f' filter="url(#{uid}-brillo)"' if "brillo" in estilos else ""
        piezas.append(renglon(linea, yy, filtro=filtro))
        if "tachado" in estilos:
            ancho = medir(linea, fid, tam)
            xa = {"middle": x - ancho / 2, "start": x, "end": x - ancho}[ancla]
            piezas.append(f'<line x1="{xa - tam * 0.1:.1f}" y1="{yy - tam * 0.2:.1f}" '
                          f'x2="{xa + ancho + tam * 0.1:.1f}" y2="{yy - tam * 0.45:.1f}" '
                          f'stroke="#ff1f1f" stroke-width="{tam * 0.11:.1f}" stroke-linecap="round"/>')
    rot = _num(el.get("rot"), -4.0 if "inclinado" in estilos else 0.0, -45, 45)
    return _transformar("".join(piezas), x, y, rot)


def insignia(el, W, H):
    """Circulo, estallido o pastilla con texto corto. forma: circulo|estallido|pastilla|escudo."""
    base = min(W, H)
    x = _num(el.get("x"), 0.5, 0, 1) * W
    y = _num(el.get("y"), 0.5, 0, 1) * H
    r = _num(el.get("tam"), 0.12, 0.02, 0.5) * base
    fondo = color(el.get("color"), "#e53935")
    borde = color(el.get("contorno"), "#ffffff")
    letra = color(el.get("color_texto"), contraste_de(fondo))
    forma = el.get("forma") if el.get("forma") in ("circulo", "estallido", "pastilla", "escudo") else "circulo"
    contenido = str(el.get("texto") or "").strip().upper()[:12]
    uid = _uid(el, f"{W}x{H}")
    piezas = [defs(uid, color(el.get("acento"), "#ffffff"))]
    sombra = f'<g opacity="0.45" transform="translate({r * 0.06:.1f} {r * 0.08:.1f})">'
    if forma == "estallido":
        puntas = 14
        pts = []
        for i in range(puntas * 2):
            ang = math.pi * i / puntas - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.78
            pts.append(f"{x + rr * math.cos(ang):.1f},{y + rr * math.sin(ang):.1f}")
        cuerpo = f'<polygon points="{" ".join(pts)}"'
    elif forma == "pastilla":
        an, al = r * 2.6, r * 1.1
        cuerpo = (f'<rect x="{x - an / 2:.1f}" y="{y - al / 2:.1f}" width="{an:.1f}" '
                  f'height="{al:.1f}" rx="{al / 2:.1f}"')
    elif forma == "escudo":
        cuerpo = (f'<path d="M{x:.1f},{y - r:.1f} L{x + r * 0.9:.1f},{y - r * 0.6:.1f} '
                  f'L{x + r * 0.75:.1f},{y + r * 0.4:.1f} L{x:.1f},{y + r:.1f} '
                  f'L{x - r * 0.75:.1f},{y + r * 0.4:.1f} L{x - r * 0.9:.1f},{y - r * 0.6:.1f} Z"')
    else:
        cuerpo = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"'
    piezas.append(sombra + cuerpo + ' fill="#000000"/></g>')
    piezas.append(cuerpo + f' fill="{fondo}" stroke="{borde}" stroke-width="{max(2, r * 0.09):.1f}"'
                  + (f' filter="url(#{uid}-brillo)"' if el.get("brillo") else "") + "/>")
    if contenido:
        fid = el.get("fuente") if el.get("fuente") in FUENTES else "anton"
        ancho = r * (2.2 if forma == "pastilla" else 1.45)
        _l, tam = encajar(contenido, fid, r * 0.95, ancho, 1)
        piezas.append(f'<text x="{x:.1f}" y="{y + tam * 0.36:.1f}" text-anchor="middle" '
                      f'font-family="{familia_css(fid)}" font-weight="{peso_css(fid)}" '
                      f'font-size="{tam:.1f}" fill="{letra}" stroke="#000000" '
                      f'stroke-width="{max(1.5, tam * 0.05):.1f}" paint-order="stroke">'
                      f'{escapar(contenido)}</text>')
    rot = _num(el.get("rot"), -8.0 if forma in ("estallido", "pastilla") else 0.0, -45, 45)
    return _transformar("".join(piezas), x, y, rot)


def flecha(el, W, H):
    """Flecha gruesa curva de (x,y) a (x2,y2), con contorno."""
    base = min(W, H)
    x1, y1 = _num(el.get("x"), 0.3, 0, 1) * W, _num(el.get("y"), 0.3, 0, 1) * H
    x2, y2 = _num(el.get("x2"), 0.6, 0, 1) * W, _num(el.get("y2"), 0.6, 0, 1) * H
    grosor = _num(el.get("tam"), 0.025, 0.005, 0.1) * base
    relleno = color(el.get("color"), "#ff3b30")
    borde = color(el.get("contorno"), "#ffffff")
    curva = _num(el.get("curva"), 0.25, -1, 1)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    cx, cy = mx - dy * curva, my + dx * curva
    # la punta mira en la direccion de la curva al llegar
    ang = math.atan2(y2 - cy, x2 - cx)
    largo = grosor * 3.2
    pa = (x2 - largo * math.cos(ang - 0.5), y2 - largo * math.sin(ang - 0.5))
    pb = (x2 - largo * math.cos(ang + 0.5), y2 - largo * math.sin(ang + 0.5))
    fin = (x2 - largo * 0.7 * math.cos(ang), y2 - largo * 0.7 * math.sin(ang))
    camino = f"M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {fin[0]:.1f},{fin[1]:.1f}"
    punta = f"M{x2:.1f},{y2:.1f} L{pa[0]:.1f},{pa[1]:.1f} L{pb[0]:.1f},{pb[1]:.1f} Z"
    return (f'<path d="{camino}" fill="none" stroke="{borde}" stroke-width="{grosor * 1.5:.1f}" '
            f'stroke-linecap="round"/>'
            f'<path d="{punta}" fill="{borde}" stroke="{borde}" stroke-width="{grosor * 0.5:.1f}" '
            f'stroke-linejoin="round"/>'
            f'<path d="{camino}" fill="none" stroke="{relleno}" stroke-width="{grosor:.1f}" '
            f'stroke-linecap="round"/>'
            f'<path d="{punta}" fill="{relleno}"/>')


def circulo(el, W, H):
    """Un circulo a mano alzada alrededor de (x,y) de radio tam (dos vueltas
    que no cierran: parece hecho con rotulador)."""
    base = min(W, H)
    x, y = _num(el.get("x"), 0.5, 0, 1) * W, _num(el.get("y"), 0.5, 0, 1) * H
    rx = _num(el.get("tam"), 0.15, 0.02, 0.6) * base
    ry = rx * _num(el.get("aspecto"), 0.75, 0.3, 2)
    grosor = max(3.0, base * 0.012)
    trazo = color(el.get("color"), "#ff3b30")
    puntos = []
    for i in range(0, 380, 10):
        a = math.radians(i - 20)
        w = 1 + 0.06 * math.sin(i / 40)
        puntos.append(f"{x + rx * w * math.cos(a):.1f},{y + ry * w * math.sin(a):.1f}")
    return (f'<polyline points="{" ".join(puntos)}" fill="none" stroke="#000000" opacity="0.35" '
            f'stroke-width="{grosor * 1.8:.1f}" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<polyline points="{" ".join(puntos)}" fill="none" stroke="{trazo}" '
            f'stroke-width="{grosor:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')


def zigzag(x1, y1, x2, y2, quiebros=7, amplitud=0.035, semilla=1):
    """Los puntos de un rayo entre dos puntos (deterministas por semilla)."""
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy) or 1
    nx, ny = -dy / largo, dx / largo
    pts = [(x1, y1)]
    for i in range(1, quiebros):
        t = i / quiebros
        lado = 1 if (i + semilla) % 2 else -1
        a = largo * amplitud * (0.6 + 0.4 * ((i * 37 + semilla * 11) % 7) / 6)
        pts.append((x1 + dx * t + nx * a * lado, y1 + dy * t + ny * a * lado))
    pts.append((x2, y2))
    return pts


def rayo(el, W, H):
    """Un rayo de luz de (x,y) a (x2,y2): blanco por dentro y con halo del
    color de acento, como el que parte un versus."""
    base = min(W, H)
    x1, y1 = _num(el.get("x"), 0.55, 0, 1) * W, _num(el.get("y"), 0.0, -0.1, 1.1) * H
    x2, y2 = _num(el.get("x2"), 0.45, 0, 1) * W, _num(el.get("y2"), 1.0, -0.1, 1.1) * H
    acento = color(el.get("color"), "#8a7dff")
    grosor = _num(el.get("tam"), 0.012, 0.002, 0.05) * base
    pts = zigzag(x1, y1, x2, y2, int(_num(el.get("quiebros"), 9, 3, 20)), 0.04,
                 int(_num(el.get("semilla"), 1, 0, 99)))
    camino = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    uid = _uid(el, f"{W}x{H}")
    return (f'<defs><filter id="{uid}-halo" x="-50%" y="-50%" width="200%" height="200%">'
            f'<feGaussianBlur stdDeviation="{grosor * 1.6:.1f}"/></filter></defs>'
            f'<polyline points="{camino}" fill="none" stroke="{acento}" stroke-width="{grosor * 4:.1f}" '
            f'stroke-linejoin="miter" filter="url(#{uid}-halo)" opacity="0.9"/>'
            f'<polyline points="{camino}" fill="none" stroke="{acento}" stroke-width="{grosor * 2:.1f}" '
            f'stroke-linejoin="miter"/>'
            f'<polyline points="{camino}" fill="none" stroke="#ffffff" stroke-width="{grosor:.1f}" '
            f'stroke-linejoin="miter"/>')


def _icono_camino(nombre, x, y, r):
    """El dibujo de un icono, centrado en (x,y) y de radio r."""
    if nombre == "estrella":
        pts = []
        for i in range(10):
            a = math.pi * i / 5 - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.45
            pts.append(f"{x + rr * math.cos(a):.1f},{y + rr * math.sin(a):.1f}")
        return f'<polygon points="{" ".join(pts)}"', "#ffd400"
    if nombre == "check":
        return (f'<path d="M{x - r * 0.8:.1f},{y:.1f} L{x - r * 0.25:.1f},{y + r * 0.6:.1f} '
                f'L{x + r * 0.85:.1f},{y - r * 0.6:.1f}" fill="none" stroke-linecap="round" '
                f'stroke-linejoin="round"', "#22c55e")
    if nombre == "cruz":
        return (f'<path d="M{x - r * 0.65:.1f},{y - r * 0.65:.1f} L{x + r * 0.65:.1f},{y + r * 0.65:.1f} '
                f'M{x + r * 0.65:.1f},{y - r * 0.65:.1f} L{x - r * 0.65:.1f},{y + r * 0.65:.1f}" '
                f'fill="none" stroke-linecap="round"', "#ef4444")
    if nombre == "corazon":
        return (f'<path d="M{x:.1f},{y + r * 0.85:.1f} C{x - r * 1.4:.1f},{y - r * 0.1:.1f} '
                f'{x - r * 0.6:.1f},{y - r * 1.1:.1f} {x:.1f},{y - r * 0.35:.1f} '
                f'C{x + r * 0.6:.1f},{y - r * 1.1:.1f} {x + r * 1.4:.1f},{y - r * 0.1:.1f} '
                f'{x:.1f},{y + r * 0.85:.1f} Z"', "#ff2d55")
    if nombre == "fuego":
        return (f'<path d="M{x:.1f},{y - r:.1f} C{x + r * 0.2:.1f},{y - r * 0.4:.1f} '
                f'{x + r * 0.9:.1f},{y - r * 0.2:.1f} {x + r * 0.8:.1f},{y + r * 0.35:.1f} '
                f'C{x + r * 0.7:.1f},{y + r * 0.9:.1f} {x - r * 0.7:.1f},{y + r * 0.9:.1f} '
                f'{x - r * 0.8:.1f},{y + r * 0.35:.1f} C{x - r * 0.85:.1f},{y - r * 0.1:.1f} '
                f'{x - r * 0.3:.1f},{y - r * 0.3:.1f} {x:.1f},{y - r:.1f} Z"', "#ff7a00")
    if nombre == "rayo":
        return (f'<polygon points="{x + r * 0.15:.1f},{y - r:.1f} {x - r * 0.6:.1f},{y + r * 0.1:.1f} '
                f'{x - r * 0.05:.1f},{y + r * 0.1:.1f} {x - r * 0.2:.1f},{y + r:.1f} '
                f'{x + r * 0.6:.1f},{y - r * 0.15:.1f} {x + r * 0.05:.1f},{y - r * 0.15:.1f}"', "#ffd400")
    if nombre == "reloj":
        return (f'<path d="M{x:.1f},{y - r * 0.55:.1f} L{x:.1f},{y:.1f} L{x + r * 0.45:.1f},{y + r * 0.25:.1f}" '
                f'fill="none" stroke-linecap="round"', "#ffffff")
    if nombre == "flecha":
        return (f'<polygon points="{x - r:.1f},{y - r * 0.3:.1f} {x + r * 0.1:.1f},{y - r * 0.3:.1f} '
                f'{x + r * 0.1:.1f},{y - r * 0.75:.1f} {x + r:.1f},{y:.1f} {x + r * 0.1:.1f},{y + r * 0.75:.1f} '
                f'{x + r * 0.1:.1f},{y + r * 0.3:.1f} {x - r:.1f},{y + r * 0.3:.1f}"', "#ffd400")
    if nombre == "pulgar":
        return (f'<path d="M{x - r * 0.75:.1f},{y - r * 0.1:.1f} L{x - r * 0.35:.1f},{y - r * 0.1:.1f} '
                f'L{x - r * 0.05:.1f},{y - r * 0.9:.1f} C{x + r * 0.25:.1f},{y - r:.1f} '
                f'{x + r * 0.3:.1f},{y - r * 0.5:.1f} {x + r * 0.15:.1f},{y - r * 0.2:.1f} '
                f'L{x + r * 0.8:.1f},{y - r * 0.2:.1f} L{x + r * 0.6:.1f},{y + r * 0.8:.1f} '
                f'L{x - r * 0.75:.1f},{y + r * 0.8:.1f} Z"', "#ffd400")
    # con letra: dinero, exclamacion, pregunta
    return None, {"dinero": "#22c55e", "exclamacion": "#ff3b30", "pregunta": "#3b82f6"}.get(nombre, "#ffd400")


def icono(el, W, H):
    base = min(W, H)
    x, y = _num(el.get("x"), 0.5, 0, 1) * W, _num(el.get("y"), 0.5, 0, 1) * H
    r = _num(el.get("tam"), 0.07, 0.01, 0.4) * base
    nombre = el.get("icono") if el.get("icono") in ICONOS else "estrella"
    camino, defecto = _icono_camino(nombre, x, y, r)
    relleno = color(el.get("color"), defecto)
    borde = color(el.get("contorno"), "#000000")
    if camino is None:
        letra = {"dinero": "$", "exclamacion": "!", "pregunta": "?"}[nombre]
        disco = color(el.get("color"), defecto)
        return _transformar(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{disco}" stroke="{borde}" '
            f'stroke-width="{r * 0.1:.1f}"/>'
            f'<text x="{x:.1f}" y="{y + r * 0.42:.1f}" text-anchor="middle" font-family="{familia_css("anton")}" '
            f'font-size="{r * 1.3:.1f}" fill="{contraste_de(disco)}">{letra}</text>',
            x, y, _num(el.get("rot"), 0, -45, 45))
    con_trazo = 'fill="none"' in camino
    rot = _num(el.get("rot"), 0, -45, 45)
    if nombre == "reloj":
        return _transformar(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#111111" stroke="{relleno}" '
            f'stroke-width="{r * 0.14:.1f}"/>' + camino + f' stroke="{relleno}" stroke-width="{r * 0.18:.1f}"/>',
            x, y, rot)
    if con_trazo:
        return _transformar(camino + f' stroke="{borde}" stroke-width="{r * 0.6:.1f}"/>'
                            + camino + f' stroke="{relleno}" stroke-width="{r * 0.38:.1f}"/>', x, y, rot)
    return _transformar(camino + f' fill="{relleno}" stroke="{borde}" stroke-width="{max(2, r * 0.1):.1f}" '
                        f'stroke-linejoin="round"/>', x, y, rot)


def etiqueta(el, W, H):
    """Una pastilla con texto (precio, GRATIS…): fondo de color, letra de contraste."""
    base = min(W, H)
    contenido = str(el.get("texto") or "").strip().upper()
    if not contenido:
        return ""
    x, y = _num(el.get("x"), 0.5, 0, 1) * W, _num(el.get("y"), 0.5, 0, 1) * H
    fid = el.get("fuente") if el.get("fuente") in FUENTES else "anton"
    lineas, tam = encajar(contenido, fid, _num(el.get("tam"), 0.06, 0.02, 0.3) * base,
                          _num(el.get("ancho"), 0.6, 0.1, 1) * W, 1)
    ancho = medir(lineas[0], fid, tam) + tam * 0.9
    alto = tam * 1.35
    fondo = color(el.get("color"), "#ffd400")
    letra = color(el.get("color_texto"), contraste_de(fondo))
    cuerpo = (f'<rect x="{x - ancho / 2 + tam * 0.08:.1f}" y="{y - alto / 2 + tam * 0.1:.1f}" width="{ancho:.1f}" '
              f'height="{alto:.1f}" rx="{alto * 0.22:.1f}" fill="#000000" opacity="0.5"/>'
              f'<rect x="{x - ancho / 2:.1f}" y="{y - alto / 2:.1f}" width="{ancho:.1f}" '
              f'height="{alto:.1f}" rx="{alto * 0.22:.1f}" fill="{fondo}" '
              f'stroke="{color(el.get("contorno"), "#000000")}" stroke-width="{max(2, tam * 0.06):.1f}"/>'
              f'<text x="{x:.1f}" y="{y + tam * 0.36:.1f}" text-anchor="middle" '
              f'font-family="{familia_css(fid)}" font-weight="{peso_css(fid)}" font-size="{tam:.1f}" '
              f'fill="{letra}">{escapar(lineas[0])}</text>')
    return _transformar(cuerpo, x, y, _num(el.get("rot"), -3, -45, 45))


def banda(el, W, H):
    """Una banda de lado a lado con texto (arriba, abajo o donde se diga)."""
    base = min(W, H)
    y = _num(el.get("y"), 0.88, 0, 1) * H
    alto = _num(el.get("tam"), 0.1, 0.03, 0.4) * base
    fondo = color(el.get("color"), "#111111")
    letra = color(el.get("color_texto"), contraste_de(fondo))
    contenido = str(el.get("texto") or "").strip().upper()
    fid = el.get("fuente") if el.get("fuente") in FUENTES else "anton"
    piezas = [f'<rect x="0" y="{y - alto / 2:.1f}" width="{W}" height="{alto:.1f}" fill="{fondo}" '
              f'opacity="{_num(el.get("opacidad"), 0.92, 0.1, 1):.2f}"/>']
    if contenido:
        lineas, tam = encajar(contenido, fid, alto * 0.7, W * 0.92, 1)
        piezas.append(f'<text x="{W / 2:.1f}" y="{y + tam * 0.36:.1f}" text-anchor="middle" '
                      f'font-family="{familia_css(fid)}" font-weight="{peso_css(fid)}" '
                      f'font-size="{tam:.1f}" fill="{letra}">{escapar(lineas[0])}</text>')
    return _transformar("".join(piezas), W / 2, y, _num(el.get("rot"), 0, -15, 15))


def subrayado(el, W, H):
    """Un trazo de rotulador bajo algo: de (x,y) con ancho `ancho`."""
    base = min(W, H)
    x, y = _num(el.get("x"), 0.5, 0, 1) * W, _num(el.get("y"), 0.6, 0, 1) * H
    ancho = _num(el.get("ancho"), 0.4, 0.05, 1) * W
    grosor = _num(el.get("tam"), 0.018, 0.004, 0.08) * base
    trazo = color(el.get("color"), "#ffd400")
    return (f'<path d="M{x - ancho / 2:.1f},{y:.1f} Q{x:.1f},{y + grosor * 1.4:.1f} {x + ancho / 2:.1f},{y - grosor * 0.4:.1f}" '
            f'fill="none" stroke="{trazo}" stroke-width="{grosor:.1f}" stroke-linecap="round"/>')


def marco(el, W, H):
    base = min(W, H)
    grosor = _num(el.get("tam"), 0.02, 0.003, 0.08) * base
    trazo = color(el.get("color"), "#ffd400")
    return (f'<rect x="{grosor / 2:.1f}" y="{grosor / 2:.1f}" width="{W - grosor:.1f}" '
            f'height="{H - grosor:.1f}" fill="none" stroke="{trazo}" stroke-width="{grosor:.1f}" '
            f'rx="{grosor * 1.5:.1f}"/>')


def estrellas(el, W, H):
    """Cinco estrellas de valoracion (las llenas, segun `valor` de 0 a 5)."""
    base = min(W, H)
    x, y = _num(el.get("x"), 0.5, 0, 1) * W, _num(el.get("y"), 0.5, 0, 1) * H
    r = _num(el.get("tam"), 0.04, 0.01, 0.2) * base
    llenas = _num(el.get("valor"), 5, 0, 5)
    relleno = color(el.get("color"), "#ffd400")
    piezas = []
    for i in range(5):
        cx = x + (i - 2) * r * 2.25
        camino, _d = _icono_camino("estrella", cx, y, r)
        piezas.append(camino + f' fill="{relleno if i < llenas else "#555555"}" stroke="#000000" '
                      f'stroke-width="{max(1.5, r * 0.12):.1f}" stroke-linejoin="round"/>')
    return "".join(piezas)


def cinta(el, W, H):
    """Una cinta cruzada en una esquina con texto (URGENTE, NUEVO, -50 %)."""
    base = min(W, H)
    esquina = el.get("esquina") if el.get("esquina") in ("si", "sd", "ii", "id") else "si"
    largo = base * 0.62
    alto = _num(el.get("tam"), 0.07, 0.03, 0.2) * base
    fondo = color(el.get("color"), "#e10600")
    letra = color(el.get("color_texto"), contraste_de(fondo))
    cx = {"si": base * 0.16, "sd": W - base * 0.16, "ii": base * 0.16, "id": W - base * 0.16}[esquina]
    cy = {"si": base * 0.16, "sd": base * 0.16, "ii": H - base * 0.16, "id": H - base * 0.16}[esquina]
    rot = {"si": -45, "sd": 45, "ii": 45, "id": -45}[esquina]
    contenido = str(el.get("texto") or "").strip().upper()
    fid = el.get("fuente") if el.get("fuente") in FUENTES else "anton"
    piezas = [f'<rect x="{cx - largo / 2:.1f}" y="{cy - alto / 2:.1f}" width="{largo:.1f}" '
              f'height="{alto:.1f}" fill="{fondo}" stroke="#ffffff" stroke-width="{alto * 0.06:.1f}"/>']
    if contenido:
        lineas, tam = encajar(contenido, fid, alto * 0.7, largo * 0.6, 1)
        piezas.append(f'<text x="{cx:.1f}" y="{cy + tam * 0.36:.1f}" text-anchor="middle" '
                      f'font-family="{familia_css(fid)}" font-weight="{peso_css(fid)}" '
                      f'font-size="{tam:.1f}" fill="{letra}">{escapar(lineas[0])}</text>')
    return f'<g transform="rotate({rot} {cx:.1f} {cy:.1f})">{"".join(piezas)}</g>'


def rafaga(el, W, H):
    """Rayos de sol desde un punto (energia, celebracion), detras de lo demas."""
    x, y = _num(el.get("x"), 0.5, 0, 1) * W, _num(el.get("y"), 0.5, 0, 1) * H
    rayos = int(_num(el.get("rayos"), 18, 6, 48))
    largo = math.hypot(W, H)
    relleno = color(el.get("color"), "#ffffff")
    piezas = []
    for i in range(rayos):
        a0 = 2 * math.pi * i / rayos
        a1 = a0 + math.pi / rayos
        piezas.append(f"M{x:.1f},{y:.1f} L{x + largo * math.cos(a0):.1f},{y + largo * math.sin(a0):.1f} "
                      f"L{x + largo * math.cos(a1):.1f},{y + largo * math.sin(a1):.1f} Z")
    return (f'<path d="{" ".join(piezas)}" fill="{relleno}" '
            f'opacity="{_num(el.get("opacidad"), 0.18, 0.02, 1):.2f}"/>')


_DIBUJANTES = {"estrellas": estrellas, "cinta": cinta, "rafaga": rafaga, "texto": texto, "insignia": insignia, "flecha": flecha, "circulo": circulo,
               "rayo": rayo, "icono": icono, "etiqueta": etiqueta, "banda": banda,
               "marco": marco, "subrayado": subrayado}


def elemento(el, W, H):
    """El SVG de un elemento (vacio si no se sabe dibujar o no tiene nada)."""
    if not isinstance(el, dict) or el.get("oculto"):
        return ""
    dibujar = _DIBUJANTES.get(el.get("tipo"))
    if dibujar is None:
        return ""
    try:
        return dibujar(el, W, H)
    except Exception:                                         # noqa: BLE001
        return ""


def fuentes_de(elementos):
    return {e.get("fuente") or "anton" for e in elementos or [] if isinstance(e, dict)}


# ------------------------------------------------------------------ validar

#: Los campos que se aceptan en un elemento, con su tipo. Lo demas se quita:
#: lo que viene de la pantalla o de Claude no entra tal cual.
_CAMPOS = {"tipo": str, "texto": str, "x": float, "y": float, "x2": float, "y2": float,
           "tam": float, "ancho": float, "lineas": float, "fuente": str, "color": str,
           "contorno": str, "acento": str, "color_texto": str, "estilos": list,
           "resaltar": list, "alinear": str, "mayusculas": bool, "rot": float,
           "forma": str, "icono": str, "curva": float, "aspecto": float,
           "quiebros": float, "semilla": float, "opacidad": float, "brillo": bool,
           "oculto": bool, "rol": str, "valor": float, "esquina": str, "rayos": float}

MAX_ELEMENTOS = 24


def limpiar_elementos(lista):
    """La lista de elementos, validada: solo tipos y campos conocidos, textos
    cortos, numeros finitos. -> list (nunca lanza)."""
    salida = []
    for crudo in (lista or [])[:MAX_ELEMENTOS]:
        if not isinstance(crudo, dict) or crudo.get("tipo") not in _DIBUJANTES:
            continue
        el = {}
        for campo, tipo in _CAMPOS.items():
            if campo not in crudo:
                continue
            valor = crudo[campo]
            if tipo is str:
                el[campo] = str(valor or "")[:160]
            elif tipo is float:
                x = _num(valor, None)
                if x is not None:
                    el[campo] = round(x, 4)
            elif tipo is bool:
                el[campo] = bool(valor)
            elif tipo is list and isinstance(valor, list):
                el[campo] = [str(v)[:40] for v in valor[:12]]
        salida.append(el)
    return salida


# ------------------------------------------------------------------ el lienzo

def efectos_de_imagen(uid, efectos):
    """El filtro de la foto de fondo: contraste, saturacion y brillo, para que
    la miniatura destaque entre las demas (lo que hacen a mano los editores)."""
    e = efectos or {}
    contraste = _num(e.get("contraste"), 1.0, 0.5, 1.8)
    saturacion = _num(e.get("saturacion"), 1.0, 0.0, 2.0)
    brillo = _num(e.get("brillo"), 1.0, 0.5, 1.6)
    if contraste == 1 and saturacion == 1 and brillo == 1:
        return "", ""
    b = brillo
    c = contraste
    inter = 0.5 - 0.5 * c
    return (f'<filter id="{uid}-foto"><feColorMatrix type="saturate" values="{saturacion:.2f}"/>'
            f'<feComponentTransfer>'
            f'<feFuncR type="linear" slope="{b * c:.3f}" intercept="{inter:.3f}"/>'
            f'<feFuncG type="linear" slope="{b * c:.3f}" intercept="{inter:.3f}"/>'
            f'<feFuncB type="linear" slope="{b * c:.3f}" intercept="{inter:.3f}"/>'
            f'</feComponentTransfer></filter>', f' filter="url(#{uid}-foto)"')


def vineta(W, H, fuerza):
    fuerza = _num(fuerza, 0, 0, 1)
    if not fuerza:
        return ""
    return (f'<defs><radialGradient id="vineta" cx="50%" cy="50%" r="72%">'
            f'<stop offset="0.55" stop-color="#000" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="#000" stop-opacity="{0.85 * fuerza:.2f}"/>'
            f'</radialGradient></defs><rect width="{W}" height="{H}" fill="url(#vineta)"/>')


def degradado_inferior(W, H, fuerza):
    """Oscurece la parte de abajo (o la de arriba) para que el texto se lea."""
    fuerza = _num(fuerza, 0, 0, 1)
    if not fuerza:
        return ""
    return (f'<defs><linearGradient id="oscuro" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0.45" stop-color="#000" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="#000" stop-opacity="{0.8 * fuerza:.2f}"/>'
            f'</linearGradient></defs><rect width="{W}" height="{H}" fill="url(#oscuro)"/>')


def imagen_cubre(href, x, y, w, h, filtro="", foco="xMidYMid"):
    """Una imagen que llena su caja recortando lo que sobre (como `cover`)."""
    return (f'<image href="{escapar(href)}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'preserveAspectRatio="{foco} slice"{filtro}/>')


def data_uri(ruta):
    """Una imagen del disco como data URI (el SVG pintado no carga ficheros)."""
    with open(ruta, "rb") as fh:
        datos = fh.read()
    tipo = "image/png" if datos[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{tipo};base64,{base64.b64encode(datos).decode('ascii')}"


def lienzo(W, H, fondo_svg, elementos, efectos=None, fondo_color="#111111"):
    """El SVG entero: fondo (ya hecho), efectos de encima y los elementos."""
    efectos = efectos or {}
    piezas = [f'<rect width="{W}" height="{H}" fill="{color(fondo_color, "#111111")}"/>',
              fondo_svg or "",
              degradado_inferior(W, H, efectos.get("oscurecer")),
              vineta(W, H, efectos.get("vineta"))]
    piezas += [elemento(e, W, H) for e in elementos or []]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(W)}" height="{int(H)}" '
            f'viewBox="0 0 {int(W)} {int(H)}">{css_fuentes(fuentes_de(elementos))}'
            f'{"".join(piezas)}</svg>')

"""GRÁFICAS: el Kit de marca de cada cliente y las piezas (rama graficas-1,
05-11-2026).

    kit = graficas.leer_kit(raiz, cid)
    png = graficas.renderizar(pieza, kit, destino=...)

Por que asi
-----------
- El texto NUNCA lo dibuja la IA de imagenes: es HTML y lo pinta el mismo
  navegador que monta los videos (`medios.edge()`). No hay que instalar nada.
- Nada de aqui toca videos, params ni firmas (regla 1 de CLAUDE.md): todo vive
  en `<proyectos>/_sistema/graficas/`. Sin kit ni piezas el Studio no cambia.
- La pagina no puede salir de si misma: se pinta sin JavaScript, sin fichero de
  disco (fuentes e imagenes van DENTRO como data URI) y con la red cortada. Por
  eso NO se reutiliza `p8_render.Navegador`, que abre el acceso a ficheros a
  proposito para las transiciones.
- Se pilota por CDP: con `--screenshot` por linea de ordenes el navegador se
  llego a colgar mas de tres minutos en una sola pieza (medido el 04-11).
"""
import base64
import hashlib
import html as html_mod
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time

try:
    from . import graficas_plantillas as _PL
    from . import grafismo, medios
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import graficas_plantillas as _PL
    import grafismo
    import medios

_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

#: id -> familia y ficheros (url relativa, nombre, pesos). Solo licencias libres
#: (OFL). Se bajan una vez, a la carpeta de fuentes del grafismo.
FUENTES = {
    "anton": ("Anton", [("anton/Anton-Regular.ttf", "Anton-Regular.ttf", "400 900", "normal")]),
    "archivo": ("Archivo Black", [("archivoblack/ArchivoBlack-Regular.ttf", "ArchivoBlack-Regular.ttf", "400 900", "normal")]),
    "bebas": ("Bebas Neue", [("bebasneue/BebasNeue-Regular.ttf", "BebasNeue-Regular.ttf", "400 900", "normal")]),
    "dmserif": ("DM Serif Display", [("dmserifdisplay/DMSerifDisplay-Regular.ttf", "DMSerifDisplay-Regular.ttf", "400 900", "normal")]),
    "inter": ("Inter", [("inter/Inter%5Bopsz,wght%5D.ttf", "Inter-Variable.ttf", "100 900", "normal")]),
    "lora": ("Lora", [("lora/Lora%5Bwght%5D.ttf", "Lora-Variable.ttf", "400 700", "normal")]),
    "montserrat": ("Montserrat", [("montserrat/Montserrat%5Bwght%5D.ttf", "Montserrat-Variable.ttf", "100 900", "normal")]),
    "nunito": ("Nunito", [("nunito/Nunito%5Bwght%5D.ttf", "Nunito-Variable.ttf", "200 1000", "normal")]),
    "oswald": ("Oswald", [("oswald/Oswald%5Bwght%5D.ttf", "Oswald-Variable.ttf", "200 700", "normal")]),
    "playfair": ("Playfair Display", [("playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf", "PlayfairDisplay-Variable.ttf", "400 900", "normal"),
                                      ("playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf", "PlayfairDisplay-Italic-Variable.ttf", "400 900", "italic")]),
    "poppins": ("Poppins", [("poppins/Poppins-Medium.ttf", "Poppins-Medium.ttf", "400 600", "normal"),
                            ("poppins/Poppins-ExtraBold.ttf", "Poppins-ExtraBold.ttf", "700 900", "normal")]),
    "raleway": ("Raleway", [("raleway/Raleway%5Bwght%5D.ttf", "Raleway-Variable.ttf", "100 900", "normal")]),
    "spacegrotesk": ("Space Grotesk", [("spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf", "SpaceGrotesk-Variable.ttf", "300 700", "normal")]),
    "syne": ("Syne", [("syne/Syne%5Bwght%5D.ttf", "Syne-Variable.ttf", "400 800", "normal")]),
}

#: Las medidas y lo que tapa o recorta cada red, en % del lado (investigado el
#: 04-11; las de TikTok, aproximadas hasta una publicacion de prueba).
FORMATOS = [
    {"id": "v45", "nombre": "Post vertical 4:5", "W": 1080, "H": 1350, "zT": 0, "zR": 3.2, "zB": 0, "zL": 3.2,
     "redes": "Instagram, Facebook, LinkedIn, X, Threads, TikTok",
     "nota": "Se ve entero en el feed. La cuadrícula de Instagram (3:4) corta un poco los lados."},
    {"id": "v34", "nombre": "Instagram 3:4", "W": 1080, "H": 1440, "zT": 0, "zR": 0, "zB": 0, "zL": 0,
     "redes": "Instagram, Threads", "nota": "No se recorta ni en el feed ni en la cuadrícula."},
    {"id": "c11", "nombre": "Cuadrado 1:1", "W": 1080, "H": 1080, "zT": 0, "zR": 12.5, "zB": 0, "zL": 12.5,
     "redes": "Facebook, LinkedIn, X, Threads, Instagram",
     "nota": "La cuadrícula de Instagram corta un 12,5 % por cada lado."},
    {"id": "h916", "nombre": "Historia 9:16", "W": 1080, "H": 1920, "zT": 16, "zR": 0, "zB": 18, "zL": 0,
     "redes": "Instagram, Facebook, estado de WhatsApp",
     "nota": "Arriba y abajo los tapan el perfil y la barra de respuesta."},
    {"id": "tt", "nombre": "TikTok foto", "W": 1080, "H": 1920, "zT": 8, "zR": 14, "zB": 22, "zL": 0,
     "redes": "TikTok", "nota": "Descarga el JPG: TikTok no acepta PNG. Zonas aproximadas."},
    {"id": "pin", "nombre": "Pinterest 2:3", "W": 1000, "H": 1500, "zT": 0, "zR": 0, "zB": 0, "zL": 0,
     "redes": "Pinterest", "nota": "En carrusel, de 2 a 5 imágenes del mismo tamaño."},
    {"id": "h19", "nombre": "Horizontal 1,91:1", "W": 1200, "H": 627, "zT": 0, "zR": 0, "zB": 0, "zL": 0,
     "redes": "LinkedIn, Facebook, enlaces compartidos", "nota": "El diseño pasa a dos columnas."},
    {"id": "h169", "nombre": "X 16:9", "W": 1600, "H": 900, "zT": 0, "zR": 0, "zB": 0, "zL": 0,
     "redes": "X", "nota": "Máximo 4 imágenes por tuit."},
]
FORMATO_DEFECTO = "v45"

#: n -> nombre, para que, campos que usa (el formulario solo pide esos).
CATALOGO = [
    (1, "Titular gigante", "Sin foto. Para una idea fuerte.", ("marca", "titulo", "apoyo", "cta")),
    (2, "Foto a sangre", "Cuando la imagen vende por sí sola.", ("kicker", "titulo", "cta", "marca")),
    (3, "Tarjeta flotante", "Foto protagonista con texto limpio.", ("kicker", "titulo", "cta")),
    (4, "Corte diagonal", "Dinámico: promociones y lanzamientos.", ("titulo", "apoyo", "cta")),
    (5, "Marco de color", "Destaca en el feed con la marca muy presente.", ("marca", "titulo")),
    (6, "Revista", "Elegante: artículos, novedades y consejos.", ("marca", "tipo", "kicker", "titulo")),
    (7, "Oferta con sello", "Descuentos y promociones.", ("marca", "titulo", "cta", "oferta", "oferta_txt")),
    (8, "Bloques", "Moderno: varios datos a la vez.", ("titulo", "oferta", "oferta_txt", "cta", "marca")),
    (9, "Testimonio", "Opiniones de clientes.", ("cita", "autor", "marca")),
    (10, "Neón nocturno", "Eventos, juegos y tecnología.", ("kicker", "titulo", "cta", "marca")),
    (11, "Círculo", "Amable y juvenil, con foto recortada.", ("kicker", "titulo", "cta", "marca")),
    (12, "Pasos", "Explicar cómo funciona algo.", ("titulo", "i1", "i2", "i3")),
    (13, "Evento con fecha", "Flyers, invitaciones y webinars.", ("dia", "mes", "titulo", "lugar", "marca")),
    (14, "Minimal de lujo", "Marcas premium: mucho aire y poco texto.", ("marca", "titulo", "cta")),
]
#: campo -> (etiqueta, largo maximo)
CAMPOS = {
    "marca": ("Nombre o logo", 40), "tipo": ("Tipo de negocio", 40), "kicker": ("Antetítulo", 40),
    "titulo": ("Titular", 90), "apoyo": ("Texto de apoyo", 140), "cta": ("Llamada a la acción", 40),
    "oferta": ("Oferta (corta)", 8), "oferta_txt": ("Texto de la oferta", 40),
    "dia": ("Día", 6), "mes": ("Mes", 20), "lugar": ("Lugar", 50),
    "i1": ("Paso 1", 50), "i2": ("Paso 2", 50), "i3": ("Paso 3", 50),
    "cita": ("Testimonio", 180), "autor": ("Quién lo dice", 50),
}
#: Los colores de partida cuando el cliente aun no tiene kit.
COLORES_DEFECTO = {"principal": "#5B2EFF", "secundario": "#FFD60A", "acento": "#FF2E7E",
                   "oscuro": "#120A33", "claro": "#F6F3FF"}
ROLES = tuple(COLORES_DEFECTO)
LARGOS_KIT = {"estilo_imagen": 600, "reglas": 1200}
MAX_BYTES_IMAGEN = 15 * 1024 * 1024
LADO_MAX_IMAGEN = 2400
ESCALA_MINIMA = 0.6
_RE_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_RE_CID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_RE_PIEZA = re.compile(r"^[0-9a-f]{12}$")
_RE_IMAGEN = re.compile(r"^img_[0-9a-f]{16}\.jpg$")
_CERROJO_DISCO = threading.Lock()
#: UNA pagina a la vez: es lo que hace de cola (0,1 s por pieza; una vista son 2 s)
_TURNO = threading.Lock()


class ErrorGraficas(Exception):
    """Lo que se le puede decir al usuario tal cual."""


# ------------------------------------------------------------------ rutas

def carpeta(raiz):
    return os.path.join(raiz, "_sistema", "graficas")


def _cid(cid):
    cid = str(cid or "")
    if not _RE_CID.match(cid):
        raise ErrorGraficas("ese proyecto no existe")
    return cid


def _ruta_kit(raiz, cid):
    return os.path.join(carpeta(raiz), "kit", f"{_cid(cid)}.json")


def _carpeta_imagenes(raiz, cid):
    return os.path.join(carpeta(raiz), "imagenes", _cid(cid))


def _carpeta_piezas(raiz, cid):
    return os.path.join(carpeta(raiz), "piezas", _cid(cid))


def _carpeta_pieza(raiz, cid, pieza_id):
    if not _RE_PIEZA.match(str(pieza_id or "")):
        raise ErrorGraficas("esa pieza no está")
    return os.path.join(_carpeta_piezas(raiz, cid), pieza_id)


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = f"{ruta}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(temporal, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    os.replace(temporal, ruta)


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else None
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as fallo:
        raise ErrorGraficas(f"no se puede leer {os.path.basename(ruta)}: {fallo}") from fallo


# ------------------------------------------------------------------ el kit

def _limpiar_colores(valor):
    salida = {}
    if valor is not None and not isinstance(valor, dict):
        raise ErrorGraficas("los colores no tienen la forma esperada")
    for rol in ROLES:
        color = str((valor or {}).get(rol) or "").strip()
        if not color:
            continue
        if not _RE_COLOR.match(color):
            raise ErrorGraficas(f"el color «{rol}» tiene que ser como #FF5A00")
        salida[rol] = color.upper()
    return salida


def _limpiar_fuente(valor, que):
    fid = str(valor or "")
    if fid and fid not in FUENTES:
        raise ErrorGraficas(f"esa tipografía de {que} no está en la lista")
    return fid


def leer_kit(raiz, cid):
    """El kit guardado, o None. Leer no escribe nada."""
    return _leer_json(_ruta_kit(raiz, cid))


def guardar_kit(raiz, cid, datos):
    datos = datos if isinstance(datos, dict) else {}
    kit = {
        "colores": _limpiar_colores(datos.get("colores")),
        "fuente_titulos": _limpiar_fuente(datos.get("fuente_titulos"), "títulos"),
        "fuente_texto": _limpiar_fuente(datos.get("fuente_texto"), "texto"),
        "logo_oscuro": os.path.basename(str(datos.get("logo_oscuro") or "")),
    }
    for clave, largo in LARGOS_KIT.items():
        kit[clave] = str(datos.get(clave) or "").strip()[:largo]
    _escribir_json(_ruta_kit(raiz, cid), kit)
    return kit


# ------------------------------------------------------------------ colores

def _luz(color):
    canales = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(uno, otro):
    a, b = sorted((_luz(uno), _luz(otro)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _tinta_para(fondo, oscuro, claro):
    """El texto legible sobre `fondo`: el oscuro o claro del kit y, si ninguno
    llega, negro o blanco. Asi un color del cliente no deja un texto ilegible."""
    mejor = max((oscuro, claro), key=lambda c: contraste(fondo, c))
    if contraste(fondo, mejor) >= 4.5:
        return mejor
    return max(("#000000", "#FFFFFF"), key=lambda c: contraste(fondo, c))


def colores_finales(kit, pieza):
    finales = dict(COLORES_DEFECTO)
    finales.update((kit or {}).get("colores") or {})
    finales.update(_limpiar_colores((pieza or {}).get("colores")))
    return finales


# ------------------------------------------------------------------ fuentes

def _ruta_fuente(fichero):
    ruta = os.path.join(grafismo.carpeta_fuentes(), fichero)
    return ruta if os.path.isfile(ruta) and os.path.getsize(ruta) > 1000 else None


def fuente_lista(fid):
    return all(_ruta_fuente(f[1]) for f in FUENTES[fid][1])


_BAJANDO = {"hilo": None}


def asegurar_fuentes(esperar=False):
    """Baja en segundo plano las que falten. Sin red, el diseno sale con una
    fuente del sistema y lo avisa: nunca se cae por una fuente."""
    if os.environ.get("ESTUDIO_SIN_DESCARGAS"):
        return

    def bajar():
        import requests                                     # noqa: PLC0415
        os.makedirs(grafismo.carpeta_fuentes(), exist_ok=True)
        for _, ficheros in FUENTES.values():
            for url, fichero, _, _ in ficheros:
                if _ruta_fuente(fichero):
                    continue
                try:
                    r = requests.get(_GF + url, timeout=30)
                    datos = r.content if r.status_code == 200 else b""
                    if len(datos) < 1000 or datos[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                        continue
                    destino = os.path.join(grafismo.carpeta_fuentes(), fichero)
                    temporal = f"{destino}.{os.getpid()}.tmp"
                    with open(temporal, "wb") as fh:
                        fh.write(datos)
                    os.replace(temporal, destino)
                except Exception:                           # noqa: BLE001
                    continue

    hilo = _BAJANDO["hilo"]
    if hilo is None or not hilo.is_alive():
        if all(fuente_lista(f) for f in FUENTES):
            return
        hilo = threading.Thread(target=bajar, daemon=True, name="graficas-fuentes")
        _BAJANDO["hilo"] = hilo
        hilo.start()
    if esperar:
        hilo.join()


_CSS_FUENTES = {}


def _css_de_fuente(fid):
    """@font-face con la fuente DENTRO: la pagina no lee nada de disco."""
    familia, ficheros = FUENTES[fid]
    partes = []
    for _, fichero, pesos, estilo in ficheros:
        ruta = _ruta_fuente(fichero)
        if not ruta:
            continue
        clave = (ruta, os.path.getmtime(ruta))
        if clave not in _CSS_FUENTES:
            with open(ruta, "rb") as fh:
                _CSS_FUENTES[clave] = base64.b64encode(fh.read()).decode("ascii")
        partes.append(f"@font-face{{font-family:'{familia}';font-weight:{pesos};font-style:{estilo};"
                      f"src:url(data:font/ttf;base64,{_CSS_FUENTES[clave]})}}")
    return "".join(partes)


def _fuentes_de_plantilla(cuerpo):
    familias = set(re.findall(r"var\(--ft, '([^']+)'\)", cuerpo))
    return [fid for fid, (familia, _) in FUENTES.items() if familia in familias]


# ------------------------------------------------------------------ imagenes

def guardar_imagen(raiz, cid, contenido):
    """Normaliza a JPG (lado maximo 2400) y la guarda por su huella."""
    from PIL import Image, ImageOps                         # noqa: PLC0415
    if not contenido or len(contenido) > MAX_BYTES_IMAGEN:
        raise ErrorGraficas("la imagen tiene que pesar menos de 15 MB")
    try:
        imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido)))
        imagen.load()
    except Exception as fallo:                              # noqa: BLE001
        raise ErrorGraficas("ese fichero no es una imagen que se pueda abrir") from fallo
    if imagen.mode in ("RGBA", "LA", "P"):
        imagen = imagen.convert("RGBA")
        fondo = Image.new("RGB", imagen.size, "#FFFFFF")
        fondo.paste(imagen, mask=imagen.getchannel("A"))
        imagen = fondo
    else:
        imagen = imagen.convert("RGB")
    imagen.thumbnail((LADO_MAX_IMAGEN, LADO_MAX_IMAGEN))
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", quality=90)
    datos = salida.getvalue()
    nombre = f"img_{hashlib.sha1(datos).hexdigest()[:16]}.jpg"
    destino = os.path.join(_carpeta_imagenes(raiz, cid), nombre)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as fh:
        fh.write(datos)
    return nombre


def ruta_imagen(raiz, cid, nombre):
    nombre = str(nombre or "")
    if not _RE_IMAGEN.match(nombre):
        return None
    ruta = os.path.join(_carpeta_imagenes(raiz, cid), nombre)
    return ruta if os.path.isfile(ruta) else None


def _data_uri(ruta):
    extension = os.path.splitext(ruta)[1].lower().lstrip(".")
    tipo = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(extension, "jpeg")
    with open(ruta, "rb") as fh:
        return f"data:image/{tipo};base64,{base64.b64encode(fh.read()).decode('ascii')}"


# ------------------------------------------------------------------ el HTML

def formato(fid):
    for f in FORMATOS:
        if f["id"] == fid:
            return f
    raise ErrorGraficas("ese tamaño no está en la lista")


def _variables(f, colores):
    """Lo que cambia por formato y por cliente: todo son variables de CSS."""
    horiz = f["W"] / f["H"] > 1.3
    cuad = f["W"] == f["H"]
    k = 0.8 if cuad else 1
    mg = 5 if horiz else 6
    p_t, p_b = max(mg, f["zT"] + 2), max(mg, f["zB"] + 2)
    p_l, p_r = max(mg, f["zL"] + 2), max(mg, f["zR"] + 2)
    a, b, d, l, x = (colores[r] for r in ("principal", "secundario", "oscuro", "claro", "acento"))
    variables = {
        "a": a, "b": b, "d": d, "l": l, "x": x,
        "ta": _tinta_para(a, d, l), "tb": _tinta_para(b, d, l),
        "pad": f"{p_t}cqh {p_r}cqw {p_b}cqh {p_l}cqw",
        # el marco de color va pegado al borde: lo que evita lo que tapa la red es el TEXTO
        "marco": f"{mg}cqmin",
        "dir": "row" if horiz else "column",
        "ladoTexto": "46%" if horiz else "100%",
        "tarjetaLado": "flex-end" if horiz else "flex-start",
        "tarjetaAncho": "52%" if horiz else "100%",
        "mitad": "46%" if horiz else "100%",
        "mitadC": "48%" if horiz else "100%",
        "corte": "polygon(0 0, 58% 0, 48% 100%, 0 100%)" if horiz
                 else "polygon(0 50%, 100% 38%, 100% 100%, 0 100%)",
        "corte2": "polygon(0 0, 61% 0, 51% 100%, 0 100%)" if horiz
                  else "polygon(0 47%, 100% 35%, 100% 100%, 0 100%)",
        "dR": f"{p_r}cqw", "dT": f"{p_t}cqh",
        "gCol": "minmax(0, 1.5fr) minmax(0, 1fr) minmax(0, 1fr)" if horiz else "repeat(2, minmax(0, 1fr))",
        "gFil": "minmax(0, 1fr) auto" if horiz else "minmax(0, 1fr) minmax(0, 1fr) auto",
        "gTit": "1 / 2" if horiz else "1 / 3",
        "gPie": "1 / 4" if horiz else "1 / 3",
        "cirT": "86cqmin" if horiz else ("56cqmin" if cuad else "72cqmin"),
        "cirR": "4cqw" if horiz else (f"{f['zR'] + 2}cqw" if f["zR"] > 5 else "-8cqmin"),
        "cirA": "7cqh" if horiz else (f"{f['zT'] + 1}cqh" if f["zT"] > 5 else "-8cqmin"),
        "padEv": "5cqh 5cqw 5cqh 5cqw" if horiz else f"3cqh {p_r}cqw {p_b}cqh {p_l}cqw",
    }
    # en horizontal el lado corto es poco: la letra pequena sube para leerse
    k_chica = 1.35 if horiz else k
    for nombre, talla in (("xl", 16), ("l", 11.5), ("m", 9.2), ("s", 8)):
        variables[f"s-{nombre}"] = f"{talla * k:.2f}cqmin"
    for nombre, talla in (("a", 3.6), ("c", 3.3), ("k", 2.8)):
        variables[f"s-{nombre}"] = f"{talla * k_chica:.2f}cqmin"
    return variables, (p_t, p_r, p_b, p_l)


def limpiar_pieza(datos):
    """La pieza tal como se guarda: solo campos conocidos y con su largo."""
    datos = datos if isinstance(datos, dict) else {}
    n = datos.get("plantilla", 2)
    if not isinstance(n, int) or isinstance(n, bool) or n not in _PL.PLANTILLAS:
        raise ErrorGraficas("esa plantilla no existe")
    formato(datos.get("formato") or FORMATO_DEFECTO)
    textos = {}
    crudos = datos.get("textos") or {}
    if not isinstance(crudos, dict):
        raise ErrorGraficas("los textos no tienen la forma esperada")
    for campo, (_, largo) in CAMPOS.items():
        valor = " ".join(str(crudos.get(campo) or "").split())
        if valor:
            textos[campo] = valor[:largo]
    imagen = str(datos.get("imagen") or "")
    if imagen and not _RE_IMAGEN.match(imagen):
        raise ErrorGraficas("esa imagen no está")
    capas = _limpiar_capas(datos.get("capas"))
    encuadre = _limpiar_encuadre(datos.get("encuadre"))
    return {"plantilla": n, "formato": datos.get("formato") or FORMATO_DEFECTO, "textos": textos,
            "imagen": imagen, "capas": capas, "encuadre": encuadre,
            "colores": _limpiar_colores(datos.get("colores")),
            "fuente_titulos": _limpiar_fuente(datos.get("fuente_titulos"), "títulos"),
            "fuente_texto": _limpiar_fuente(datos.get("fuente_texto"), "texto"),
            "nombre": str(datos.get("nombre") or "").strip()[:80]}


def _numero(valor, minimo, maximo, defecto):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return defecto
    if numero != numero:                                    # NaN
        return defecto
    return max(minimo, min(maximo, numero))


def _limpiar_capas(valor):
    """Los retoques de cada texto: `{campo: {x, y, escala, negrita, cursiva,
    subrayado, color, fondo, oculto}}`. x e y, en % del lienzo."""
    if valor is None:
        return {}
    if not isinstance(valor, dict):
        raise ErrorGraficas("los retoques del texto no tienen la forma esperada")
    salida = {}
    for campo, capa in valor.items():
        if campo not in CAMPOS or not isinstance(capa, dict):
            continue
        limpia = {}
        for eje in ("x", "y"):
            if capa.get(eje):
                limpia[eje] = round(_numero(capa[eje], -100, 100, 0), 2)
        if capa.get("escala") not in (None, 1, 1.0):
            limpia["escala"] = round(_numero(capa["escala"], 0.4, 3, 1), 2)
        for marca in ("negrita", "cursiva", "subrayado", "oculto"):
            if isinstance(capa.get(marca), bool):
                limpia[marca] = capa[marca]
        for tinte in ("color", "fondo"):
            if capa.get(tinte):
                if not _RE_COLOR.match(str(capa[tinte])):
                    raise ErrorGraficas("un color del texto tiene que ser como #FF5A00")
                limpia[tinte] = str(capa[tinte]).upper()
        if limpia:
            salida[campo] = limpia
    return salida


def _limpiar_encuadre(valor):
    """Qué parte de la foto se ve: x e y de 0 a 100 y zoom de 1 a 4."""
    if not isinstance(valor, dict):
        return {}
    encuadre = {"x": round(_numero(valor.get("x"), 0, 100, 50), 2),
                "y": round(_numero(valor.get("y"), 0, 100, 50), 2),
                "zoom": round(_numero(valor.get("zoom"), 1, 4, 1), 2)}
    return {} if encuadre == {"x": 50, "y": 50, "zoom": 1} else encuadre


def _css_encuadre(encuadre):
    """`object-view-box` recorta la foto ANTES de encajarla: asi el zoom nunca se
    sale de su hueco, sea cual sea el diseno."""
    if not encuadre:
        return ""
    x, y, zoom = encuadre["x"], encuadre["y"], encuadre["zoom"]
    lado = 100 / zoom
    izq, arr = (100 - lado) * x / 100, (100 - lado) * y / 100
    return (f".lienzo img:not(.logo){{object-position:{x}% {y}%;"
            f"object-view-box:inset({arr:.3f}% {100 - lado - izq:.3f}% {100 - lado - arr:.3f}% {izq:.3f}%)}}")


def _css_capas(capas):
    partes = []
    for campo, capa in capas.items():
        reglas = []
        if capa.get("x") or capa.get("y"):
            reglas.append(f"translate:{capa.get('x', 0)}cqw {capa.get('y', 0)}cqh")
        if "negrita" in capa:
            reglas.append(f"font-weight:{800 if capa['negrita'] else 400}!important")
        if "cursiva" in capa:
            reglas.append(f"font-style:{'italic' if capa['cursiva'] else 'normal'}!important")
        if "subrayado" in capa:
            reglas.append(f"text-decoration:{'underline' if capa['subrayado'] else 'none'}!important")
        if capa.get("color"):
            reglas.append(f"color:{capa['color']}!important")
        if capa.get("fondo"):
            reglas.append(f"background:{capa['fondo']}!important;padding:.12em .3em")
        if capa.get("oculto"):
            reglas.append("display:none!important")
        if reglas:
            partes.append(f'[data-e="{campo}"]{{{";".join(reglas)}}}')
    return "".join(partes)


def _aplicar_tamanos(cuerpo, capas):
    """El tamano de cada texto, multiplicando el suyo en SU etiqueta."""
    for campo, capa in capas.items():
        escala = capa.get("escala")
        if not escala:
            continue

        def retocar(m, esc=escala):
            etiqueta = m.group(0)
            if "font-size:" in etiqueta:
                return re.sub(r"font-size: ([^;\"]+(?:\([^\"]*?\))?)", lambda f: f"font-size: calc(({f.group(1)})*{esc})", etiqueta, count=1)
            return etiqueta.replace('style="', f'style="zoom: {esc}; ', 1)
        cuerpo = re.sub(rf'<div class="t" data-e="{campo}" style="[^"]*">', retocar, cuerpo)
    return cuerpo


def _sustituir_imagen(cuerpo, uri):
    if uri:
        return cuerpo.replace("«img»", uri)
    # sin foto: un bloque de color con la misma medida, nunca una imagen rota
    def bloque(m):
        estilo = m.group(1)
        return f'<div aria-hidden="true" style="{estilo}; background: linear-gradient(135deg, var(--a), var(--b))"></div>'
    return re.sub(r'<img src="«img»" alt="[^"]*" style="([^"]*)">', bloque, cuerpo)


def html_de(pieza, kit=None, imagen=None, logo=None, logo_oscuro=None):
    """El documento entero. `imagen`, `logo`, `logo_oscuro`: rutas de disco."""
    pieza = limpiar_pieza(pieza)
    f = formato(pieza["formato"])
    colores = colores_finales(kit, pieza)
    variables, margenes = _variables(f, colores)
    cuerpo = _PL.PLANTILLAS[pieza["plantilla"]]
    cuerpo = _sustituir_imagen(cuerpo, _data_uri(imagen) if imagen else "")
    cuerpo = _aplicar_tamanos(cuerpo, pieza["capas"])
    # el logo: el normal, o el de fondo oscuro si la caja cae sobre color oscuro
    fondo_marca = {1: "a", 2: "d", 5: "d", 6: "l", 7: "b", 8: "l", 9: "d", 10: "d", 13: "a", 14: "l"}.get(pieza["plantilla"], "l")
    logo_ruta = logo
    if logo_oscuro and _luz(variables[fondo_marca]) < 0.3:
        logo_ruta = logo_oscuro
    textos = pieza["textos"]
    if logo_ruta and os.path.isfile(logo_ruta):
        marca = f'<img class="logo" alt="" src="{_data_uri(logo_ruta)}">'
    else:
        marca = html_mod.escape(textos.get("marca", ""))
    cuerpo = cuerpo.replace("«logo»", marca)
    for campo in CAMPOS:
        # `oferta_txt` en la plantilla se llama ofertaTxt
        for token in {campo, "ofertaTxt" if campo == "oferta_txt" else campo}:
            cuerpo = cuerpo.replace(f"«{token}»", html_mod.escape(textos.get(campo, "")))
    # las fuentes: la de la pieza manda sobre la del kit, y esa sobre la del diseno
    usadas = set(_fuentes_de_plantilla(cuerpo)) | {"poppins"}
    fuente_t = pieza["fuente_titulos"] or (kit or {}).get("fuente_titulos") or ""
    fuente_b = pieza["fuente_texto"] or (kit or {}).get("fuente_texto") or ""
    if fuente_t in FUENTES:
        variables["ft"] = f"'{FUENTES[fuente_t][0]}'"
        usadas.add(fuente_t)
    familia_texto = "'Poppins'"
    if fuente_b in FUENTES:
        familia_texto = f"'{FUENTES[fuente_b][0]}'"
        usadas.add(fuente_b)
    faltan = [FUENTES[u][0] for u in usadas if not fuente_lista(u)]
    caras = "".join(_css_de_fuente(u) for u in sorted(usadas))
    raiz = ";".join(f"--{k}:{v}" for k, v in variables.items())
    documento = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8"><style>'
        f"{caras}*{{box-sizing:border-box}}"
        f":root{{{raiz};--esc:1}}"
        "html,body{margin:0;width:100vw;height:100vh;overflow:hidden}"
        f".lienzo{{position:relative;overflow:hidden;width:100vw;height:100vh;container-type:size;"
        f"font-family:{familia_texto},sans-serif;background:var(--d)}}"
        ".t:empty{display:none}.logo{display:block;max-height:9cqmin;max-width:34cqmin;object-fit:contain}"
        f"{_css_encuadre(pieza['encuadre'])}{_css_capas(pieza['capas'])}"
        f"</style></head><body><div class=\"lienzo\">{cuerpo}</div></body></html>")
    return documento, f, margenes, faltan


# ------------------------------------------------------------------ el navegador

def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Pincel:
    """Un navegador sin scripts ni red, una pagina a la vez."""

    def __init__(self):
        import websocket                                    # noqa: PLC0415
        try:
            navegador = medios.edge()
        except Exception as fallo:                          # noqa: BLE001
            raise ErrorGraficas("no encuentro el navegador que pinta las gráficas") from fallo
        self.perfil = tempfile.mkdtemp(prefix="graficas_")
        self.ws = None
        puerto = _puerto_libre()
        try:
            self.proceso = subprocess.Popen(
                [navegador, "--headless=new", "--disable-gpu", "--no-first-run",
                 "--disable-extensions", "--hide-scrollbars", "--mute-audio",
                 "--force-device-scale-factor=1", f"--user-data-dir={self.perfil}",
                 "--remote-allow-origins=*", f"--remote-debugging-port={puerto}",
                 # la red, cortada: nada de lo que hay en la pieza puede salir
                 "--host-resolver-rules=MAP * ~NOTFOUND", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **medios.SIN_VENTANA)
        except OSError as fallo:
            shutil.rmtree(self.perfil, ignore_errors=True)
            raise ErrorGraficas("el navegador no ha arrancado") from fallo
        try:
            self.ws = websocket.create_connection(self._url(puerto), timeout=60)
            self._id = 0
            self.llamar("Page.enable")
            self.llamar("Emulation.setScriptExecutionDisabled", value=True)
        except Exception:
            self.cerrar()
            raise

    def _url(self, puerto):
        import requests                                     # noqa: PLC0415
        limite = time.time() + 30
        while time.time() < limite:
            if self.proceso.poll() is not None:
                raise ErrorGraficas("el navegador no ha arrancado")
            try:
                sin_proxy = {"http": None, "https": None}
                for pestana in requests.get(f"http://127.0.0.1:{puerto}/json", timeout=2, proxies=sin_proxy).json():
                    if pestana.get("type") == "page":
                        return pestana["webSocketDebuggerUrl"]
            except Exception:                               # noqa: BLE001
                pass
            time.sleep(0.1)
        raise ErrorGraficas("el navegador no ha contestado")

    def llamar(self, metodo, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": metodo, "params": params}))
        while True:
            mensaje = json.loads(self.ws.recv())
            if mensaje.get("id") != self._id:
                continue
            if "error" in mensaje:
                raise RuntimeError(f"{metodo}: {mensaje['error']}")
            return mensaje.get("result", {})

    def evaluar(self, expresion):
        r = self.llamar("Runtime.evaluate", expression=expresion, returnByValue=True, awaitPromise=True)
        return (r.get("result") or {}).get("value")

    def abrir(self, documento, ancho, alto):
        self.llamar("Emulation.setDeviceMetricsOverride", width=int(ancho), height=int(alto),
                    deviceScaleFactor=1, mobile=False)
        marco = self.llamar("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.llamar("Page.setDocumentContent", frameId=marco, html=documento)
        self.evaluar("(async()=>{await document.fonts.ready;"
                     "await Promise.all([...document.images].map(i=>i.decode().catch(()=>0)));"
                     "return true})()")

    def capturar(self):
        datos = self.llamar("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        return base64.b64decode(datos["data"])

    def cerrar(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:                                   # noqa: BLE001
            pass
        self.proceso.terminate()
        try:
            self.proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proceso.kill()
        shutil.rmtree(self.perfil, ignore_errors=True)


_MEDIR = """(() => {
  const W = innerWidth, H = innerHeight, m = %s;
  const seg = {l: m[3] / 100 * W - 1, r: W - m[1] / 100 * W + 1, t: m[0] / 100 * H - 1, b: H - m[2] / 100 * H + 1};
  const cajas = [...document.querySelectorAll('.t')].filter(e => (e.textContent || e.querySelector('img')) && e.getClientRects().length);
  const fuera = [], choca = [], rect = [];
  for (const e of cajas) {
    const r = document.createRange(); r.selectNodeContents(e);
    const b0 = r.getBoundingClientRect();
    // la caja de la letra sobresale de su linea cuando el interlineado es justo:
    // eso es aire, no texto
    const fs = parseFloat(getComputedStyle(e).fontSize) * 0.2;
    const c = {left: b0.left, right: b0.right, top: b0.top + fs, bottom: b0.bottom - fs};
    rect.push(c);
    if (c.left < seg.l || c.right > seg.r || c.top < seg.t || c.bottom > seg.b) fuera.push((e.textContent || 'logo').slice(0, 30));
    else if (e.scrollWidth > e.clientWidth + 2) fuera.push((e.textContent || 'logo').slice(0, 30));
  }
  for (let i = 0; i < rect.length; i++) for (let j = i + 1; j < rect.length; j++) {
    const a = rect[i], b = rect[j];
    const x = Math.min(a.right, b.right) - Math.max(a.left, b.left), y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (x > 4 && y > 4 && !cajas[i].contains(cajas[j]) && !cajas[j].contains(cajas[i])) choca.push([(cajas[i].textContent||'').slice(0,20), (cajas[j].textContent||'').slice(0,20)]);
  }
  return {fuera, choca};
})()"""


_CAJAS = """(() => {
  const W = innerWidth, H = innerHeight, salida = {};
  for (const e of document.querySelectorAll('[data-e]')) {
    if (!e.getClientRects().length || !(e.textContent || e.querySelector('img'))) continue;
    const c = e.getBoundingClientRect();
    salida[e.dataset.e] = {x: c.left / W * 100, y: c.top / H * 100, w: c.width / W * 100, h: c.height / H * 100};
  }
  const f = [...document.images].filter(i => !i.classList.contains('logo'))
    .map(i => i.getBoundingClientRect()).sort((a, b) => b.width * b.height - a.width * a.height)[0];
  return {cajas: salida, hueco: f && f.height ? f.width / f.height : null};
})()"""


def _ajustar(pincel, margenes, retocada=False):
    """Baja la letra hasta que el texto cabe y queda fuera de lo que tapa la red.
    Con textos retocados a mano solo mide: manda lo que la persona ha decidido."""
    expresion = _MEDIR % json.dumps(list(margenes))
    if retocada:
        return 1.0, pincel.evaluar(expresion) or {"fuera": [], "choca": []}
    escala = 1.0
    while True:
        medida = pincel.evaluar(expresion) or {"fuera": [], "choca": []}
        if (not medida["fuera"] and not medida["choca"]) or escala <= ESCALA_MINIMA:
            return escala, medida
        escala = round(escala - 0.05, 2)
        pincel.evaluar(f"document.documentElement.style.setProperty('--esc','{escala}');"
                       "document.fonts.ready.then(()=>true)")


def _avisos(medida, escala, faltan, retocada=False):
    avisos = []
    if (medida["fuera"] or medida["choca"]) and retocada:
        avisos.append("Un texto queda en lo que tapa la red o pisa a otro: revísalo con «Ver lo que tapa la red».")
    elif medida["fuera"] or medida["choca"]:
        avisos.append("El texto no cabe bien en este diseño y tamaño: acórtalo o elige otro.")
    elif escala < 1:
        avisos.append(f"Letra reducida al {round(escala * 100)} % para que quepa el texto.")
    if faltan:
        avisos.append(f"Aún no está la tipografía {', '.join(sorted(faltan))}: se ve una parecida.")
    return avisos


def pintar(pincel, pieza, kit=None, imagen=None, logo=None, logo_oscuro=None):
    """-> (png en bytes, avisos, medida)."""
    documento, f, margenes, faltan = html_de(pieza, kit, imagen, logo, logo_oscuro)
    pincel.abrir(documento, f["W"], f["H"])
    retocada = any(k in c for c in limpiar_pieza(pieza)["capas"].values() for k in ("x", "y", "escala"))
    escala, medida = _ajustar(pincel, margenes, retocada)
    return pincel.capturar(), _avisos(medida, escala, faltan, retocada), medida


def a_jpg(png, ancho=None, calidad=92):
    from PIL import Image                                   # noqa: PLC0415
    imagen = Image.open(io.BytesIO(png)).convert("RGB")
    if ancho and imagen.width > ancho:
        imagen = imagen.resize((ancho, round(imagen.height * ancho / imagen.width)), Image.LANCZOS)
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", quality=calidad, optimize=True)
    return salida.getvalue()


def _con_turno(funcion):
    if not _TURNO.acquire(timeout=90):
        raise ErrorGraficas("el motor de Gráficas está ocupado: prueba otra vez en un momento")
    try:
        pincel = Pincel()
        try:
            return funcion(pincel)
        finally:
            pincel.cerrar()
    finally:
        _TURNO.release()


def vistas(raiz, cid, pieza, plantillas, logo=None, logo_oscuro=None):
    """Las miniaturas de varios disenos con estos mismos datos, y en grande la
    plantilla de la pieza. Se paga 0: no llama a ninguna IA."""
    pieza = limpiar_pieza(pieza)
    kit = leer_kit(raiz, cid)
    imagen = ruta_imagen(raiz, cid, pieza["imagen"])

    def trabajar(pincel):
        salida = []
        grande = None
        for n in plantillas:
            # lo arrastrado es de ESTE diseno: en los otros, cada texto en su sitio
            otra = pieza if n == pieza["plantilla"] else dict(
                pieza, plantilla=n, capas={c: {k: v for k, v in d.items() if k not in ("x", "y")}
                                           for c, d in pieza["capas"].items()})
            png, avisos, _ = pintar(pincel, otra, kit, imagen, logo, logo_oscuro)
            if n == pieza["plantilla"]:
                grande = dict(pincel.evaluar(_CAJAS) or {}, img=_uri_jpg(a_jpg(png, 1080, 88)), avisos=avisos)
            salida.append({"n": n, "img": _uri_jpg(a_jpg(png, 420, 80)), "avisos": avisos})
        return {"vistas": salida, "grande": grande}
    return _con_turno(trabajar)


def _uri_jpg(datos):
    return "data:image/jpeg;base64," + base64.b64encode(datos).decode("ascii")


# ------------------------------------------------------------------ las piezas

def _ficha(raiz, cid, pieza_id):
    return _leer_json(os.path.join(_carpeta_pieza(raiz, cid, pieza_id), "pieza.json"))


def listar_piezas(raiz, cid):
    carpeta_cliente = _carpeta_piezas(raiz, cid)
    salida = []
    if not os.path.isdir(carpeta_cliente):
        return salida
    for pieza_id in os.listdir(carpeta_cliente):
        if not _RE_PIEZA.match(pieza_id):
            continue
        try:
            ficha = _ficha(raiz, cid, pieza_id)
        except ErrorGraficas:
            continue
        if ficha:
            salida.append(ficha)
    salida.sort(key=lambda p: p.get("cambiada") or "", reverse=True)
    return salida


def leer_pieza(raiz, cid, pieza_id):
    ficha = _ficha(raiz, cid, pieza_id)
    if not ficha:
        raise ErrorGraficas("esa pieza no está")
    return ficha


def guardar_pieza(raiz, cid, datos, pieza_id=None, logo=None, logo_oscuro=None):
    """Guarda los datos y pinta el PNG y el JPG finales."""
    pieza = limpiar_pieza(datos)
    if pieza_id:
        leer_pieza(raiz, cid, pieza_id)
    else:
        pieza_id = secrets.token_hex(6)
    destino = _carpeta_pieza(raiz, cid, pieza_id)
    kit = leer_kit(raiz, cid)
    imagen = ruta_imagen(raiz, cid, pieza["imagen"])
    png, avisos, _ = _con_turno(lambda p: pintar(p, pieza, kit, imagen, logo, logo_oscuro))
    os.makedirs(destino, exist_ok=True)
    for nombre, contenido in (("pieza.png", png), ("pieza.jpg", a_jpg(png))):
        temporal = os.path.join(destino, f"{nombre}.tmp")
        with open(temporal, "wb") as fh:
            fh.write(contenido)
        os.replace(temporal, os.path.join(destino, nombre))
    f = formato(pieza["formato"])
    ficha = dict(pieza, id=pieza_id, cid=cid, avisos=avisos, medida=f"{f['W']}×{f['H']}",
                 cambiada=time.strftime("%Y-%m-%dT%H:%M:%S"), sello=secrets.token_hex(4))
    ficha["nombre"] = pieza["nombre"] or pieza["textos"].get("titulo") or pieza["textos"].get("cita") or "Pieza sin título"
    _escribir_json(os.path.join(destino, "pieza.json"), ficha)
    return ficha


def ruta_final(raiz, cid, pieza_id, extension):
    if extension not in ("png", "jpg"):
        raise ErrorGraficas("eso solo se descarga en PNG o JPG")
    ruta = os.path.join(_carpeta_pieza(raiz, cid, pieza_id), f"pieza.{extension}")
    if not os.path.isfile(ruta):
        raise ErrorGraficas("esa pieza no está")
    return ruta


def borrar_pieza(raiz, cid, pieza_id):
    leer_pieza(raiz, cid, pieza_id)
    shutil.rmtree(_carpeta_pieza(raiz, cid, pieza_id), ignore_errors=True)


def catalogo():
    return {
        "plantillas": [{"n": n, "nombre": nombre, "uso": uso, "campos": list(campos)} for n, nombre, uso, campos in CATALOGO],
        "formatos": FORMATOS, "formato_defecto": FORMATO_DEFECTO,
        "campos": {k: {"etiqueta": v[0], "largo": v[1]} for k, v in CAMPOS.items()},
        "fuentes": [{"id": k, "nombre": v[0]} for k, v in sorted(FUENTES.items(), key=lambda x: x[1][0])],
        "colores_defecto": COLORES_DEFECTO, "roles": list(ROLES),
    }

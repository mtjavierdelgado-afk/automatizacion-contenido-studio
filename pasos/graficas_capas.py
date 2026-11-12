"""GRÁFICAS CON CAPAS (rama graficas-2-capas, 11-11-2026).

Una pieza en capas es un documento («versión 2») con láminas, y cada lámina una
lista de capas sueltas: texto, foto, logo o forma. La plantilla deja de ser un
molde fijo y pasa a ser el punto de partida: `convertir` pinta la pieza de
siempre y apunta cada parte como una capa, de forma que la pieza en capas sale
igual que la de antes (lo comprueba `prueba_graficas_capas`, píxel a píxel).

Por qué así
-----------
- **Las piezas de antes no se tocan nunca.** Lo nuevo va en `capas.json`,
  `capas.png` y `capas.jpg`, al lado de `pieza.json`, `pieza.png` y
  `pieza.jpg`. Así, si el servidor vuelve a `main`, `main` sigue leyendo y
  descargando sus piezas como siempre. `capas.json` apunta el `sello` del
  `pieza.json` del que salió: si alguien vuelve a guardar la pieza con el
  editor de antes, el sello cambia y la versión en capas deja de valer (manda
  la más nueva).
- **Nada se guarda como CSS libre.** Cada capa son números acotados, colores
  `#RRGGBB` o referencias al Kit (`kit:principal`, `tinta:principal`), y
  textos que se escapan. El HTML lo arma `html_capas` a partir de esos datos:
  sin JavaScript, sin red y sin ficheros de disco (todo va dentro), como el
  motor de siempre (`graficas.Pincel`).
- **Los colores se guardan como color del Kit** siempre que la parte usaba uno:
  si el cliente cambia su Kit, sus piezas cambian con él, igual que antes. Para
  saber qué color del Kit pinta cada parte, la conversión pinta la plantilla con
  colores «testigo» (únicos) y los reconoce.
- **Las medidas van en % del lienzo** (x, ancho: del ancho; y, alto: del alto)
  y las longitudes (letra, márgenes, esquinas, bordes) en centésimas del lado
  corto (`cqmin`). Una capa no depende del tamaño en píxeles.
- **Nada de esto toca vídeos, params ni firmas** (regla 1): todo vive en
  `<proyectos>/_sistema/graficas/`. Abrir, convertir y comparar no escriben.
"""
import html as html_mod
import io
import json
import math
import os
import re
import secrets
import threading
import time

try:
    from . import graficas as G
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import graficas as G

ErrorGraficas = G.ErrorGraficas

VERSION = 2
MAX_LAMINAS = 20
MAX_CAPAS = 60
MAX_FOTOS = 8
MAX_LOGOS = 4
MAX_TEXTO = 600
MAX_PUNTOS = 12
MAX_SOMBRAS = 4

#: rol del Kit -> la variable que usan las plantillas
ROL_VAR = {"principal": "a", "secundario": "b", "oscuro": "d", "claro": "l", "acento": "x"}
VAR_ROL = {v: k for k, v in ROL_VAR.items()}
#: Los colores «testigo»: únicos, para reconocer qué parte usa qué color del Kit.
TESTIGOS = {
    "kit:principal": "#03070B", "kit:secundario": "#030715", "kit:oscuro": "#03071F",
    "kit:claro": "#030729", "kit:acento": "#030733",
    "tinta:principal": "#03073D", "tinta:secundario": "#030747",
}
_TESTIGO_VAR = {"kit:principal": "a", "kit:secundario": "b", "kit:oscuro": "d", "kit:claro": "l",
                "kit:acento": "x", "tinta:principal": "ta", "tinta:secundario": "tb"}
_DE_TESTIGO = {v: k for k, v in TESTIGOS.items()}

TIPOS = ("texto", "imagen", "logo", "forma")
_RE_ID = re.compile(r"^[a-z0-9]{1,12}$")
_RE_ROL = re.compile(r"^[a-z0-9_]{0,20}$")
_RE_REF = re.compile(r"^(?:#[0-9A-F]{6}|kit:(?:principal|secundario|oscuro|claro|acento)"
                     r"|tinta:(?:principal|secundario|oscuro|claro|acento))$")
_RE_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")


# ====================================================================== limpieza

def _num(valor, minimo, maximo, defecto=0.0, decimales=6):
    try:
        n = float(valor)
    except (TypeError, ValueError, OverflowError):
        return defecto
    if not math.isfinite(n):
        return defecto
    return round(max(minimo, min(maximo, n)), decimales)


def _bool(valor):
    return valor is True


def _ref(valor, defecto=None):
    """Un color: #RRGGBB o una referencia al Kit. Cualquier otra cosa se rechaza."""
    if valor in (None, ""):
        return defecto
    texto = str(valor).strip()
    if texto.startswith("#"):
        texto = texto.upper()
    if not _RE_REF.match(texto):
        raise ErrorGraficas("un color de una capa tiene que ser como #FF5A00 o un color del Kit")
    return texto


def _relleno(valor):
    """{"color", "alfa"} o {"degradado": {"ang", "paradas": [{color, alfa, pos}]}}."""
    if not isinstance(valor, dict):
        return None
    deg = valor.get("degradado")
    if isinstance(deg, dict):
        paradas = []
        for p in (deg.get("paradas") if isinstance(deg.get("paradas"), list) else [])[:6]:
            if not isinstance(p, dict):
                continue
            pos = p.get("pos")
            paradas.append({"color": _ref(p.get("color"), "#000000"), "alfa": _num(p.get("alfa", 1), 0, 1, 1),
                            "pos": None if pos is None else _num(pos, -100, 200, 0)})
        if len(paradas) < 2:
            return None
        return {"degradado": {"ang": _num(deg.get("ang", 180), -360, 360, 180), "paradas": paradas}}
    color = _ref(valor.get("color"))
    if not color:
        return None
    return {"color": color, "alfa": _num(valor.get("alfa", 1), 0, 1, 1)}


def _borde(valor):
    if not isinstance(valor, dict):
        return None
    anchos = valor.get("anchos")
    if not isinstance(anchos, list) or len(anchos) != 4:
        return None
    anchos = [_num(a, 0, 20, 0) for a in anchos]
    if not any(anchos):
        return None
    return {"anchos": anchos, "color": _ref(valor.get("color"), "#000000"), "alfa": _num(valor.get("alfa", 1), 0, 1, 1)}


def _sombras(valor):
    salida = []
    for s in (valor if isinstance(valor, list) else [])[:MAX_SOMBRAS]:
        if not isinstance(s, dict):
            continue
        salida.append({"x": _num(s.get("x"), -50, 50), "y": _num(s.get("y"), -50, 50),
                       "blur": _num(s.get("blur"), 0, 50), "spread": _num(s.get("spread"), -20, 20),
                       "color": _ref(s.get("color"), "#000000"), "alfa": _num(s.get("alfa", 1), 0, 1, 1)})
    return salida


def _radio(valor):
    if valor == "elipse":
        return "elipse"
    return _num(valor, 0, 200, 0)


def _origen(valor):
    """El punto de giro, en % de la propia caja ([50, 50] es el centro)."""
    if not isinstance(valor, list) or len(valor) != 2:
        return [50, 50]
    return [_num(valor[0], -1000, 1000, 50), _num(valor[1], -1000, 1000, 50)]


def _recorte(valor):
    """La caja que corta lo que se sale de la capa (en % del lienzo), como la
    casilla de una plantilla que esconde un texto movido fuera de ella."""
    if not isinstance(valor, dict):
        return None
    return {"x": _num(valor.get("x"), -200, 300), "y": _num(valor.get("y"), -200, 300),
            "w": _num(valor.get("w"), 0, 400), "h": _num(valor.get("h"), 0, 400), "radio": _radio(valor.get("radio"))}


def _cuatro(valor, maximo):
    if not isinstance(valor, list) or len(valor) != 4:
        return [0, 0, 0, 0]
    return [_num(v, 0, maximo, 0) for v in valor]


def _limpiar_capa(capa, vistos):
    if not isinstance(capa, dict) or capa.get("tipo") not in TIPOS:
        raise ErrorGraficas("una capa no tiene la forma esperada")
    cid = str(capa.get("id") or "")
    if not _RE_ID.fullmatch(cid) or cid in vistos:
        cid = "c" + secrets.token_hex(4)
    vistos.add(cid)
    rol = str(capa.get("rol") or "")
    if not _RE_ROL.fullmatch(rol):
        rol = ""
    tipo = capa["tipo"]
    limpia = {
        "id": cid, "tipo": tipo, "rol": rol, "nombre": " ".join(str(capa.get("nombre") or "")[:200].split())[:40],
        "x": _num(capa.get("x"), -200, 300), "y": _num(capa.get("y"), -200, 300),
        "w": _num(capa.get("w"), 0, 400), "h": _num(capa.get("h"), 0, 400),
        "giro": _num(capa.get("giro"), -360, 360), "opac": _num(capa.get("opac", 1), 0, 1, 1),
        "origen": _origen(capa.get("origen")), "recorte": _recorte(capa.get("recorte")),
        "oculto": _bool(capa.get("oculto")), "bloqueado": _bool(capa.get("bloqueado")),
    }
    if tipo == "texto":
        # se corta ANTES de limpiar: un texto de 50 MB no tiene por qué recorrerse entero
        texto = _RE_CONTROL.sub("", str(capa.get("txt") or "")[:MAX_TEXTO * 2].replace("\r\n", "\n"))[:MAX_TEXTO]
        fuente = capa.get("fuente") if isinstance(capa.get("fuente"), dict) else {}
        fid = str(fuente.get("id") or "")
        if fid not in G.FUENTES:
            # una tipografía que ya no está en la lista vuelve a la de su papel:
            # así una pieza guardada nunca deja de abrirse por una letra quitada
            fid = ""
        rol_f = fuente.get("rol") if fuente.get("rol") in ("titulos", "texto", "fija") else "texto"
        alin = capa.get("alin") if capa.get("alin") in ("izq", "centro", "der") else "izq"
        valign = capa.get("valign") if capa.get("valign") in ("arriba", "centro", "abajo") else "arriba"
        limpia.update({
            "txt": texto,
            "fuente": {"rol": rol_f, "id": fid, "serif": _bool(fuente.get("serif"))},
            "tam": _num(capa.get("tam"), 0.3, 60, 4), "peso": int(_num(capa.get("peso", 400), 100, 1000, 400, 0)),
            "cursiva": _bool(capa.get("cursiva")), "subrayado": _bool(capa.get("subrayado")),
            "mayus": _bool(capa.get("mayus")), "espaciado": _num(capa.get("espaciado"), -0.2, 1),
            "interlineado": _num(capa.get("interlineado"), 0, 3), "alin": alin, "valign": valign,
            "color": _ref(capa.get("color"), "#FFFFFF"), "alfa": _num(capa.get("alfa", 1), 0, 1, 1),
            "fondo": _relleno(capa.get("fondo")), "relleno": _cuatro(capa.get("relleno"), 30),
            "borde": _borde(capa.get("borde")), "radio": _radio(capa.get("radio")),
            "sombra": _sombras(capa.get("sombra")), "sombra_texto": _sombras(capa.get("sombra_texto")),
            "ajusta": _bool(capa.get("ajusta")),
        })
    elif tipo == "imagen":
        src = str(capa.get("src") or "")
        if src and not G._RE_IMAGEN.fullmatch(src):
            raise ErrorGraficas("esa imagen no está")
        enc = capa.get("encuadre") if isinstance(capa.get("encuadre"), dict) else {}
        limpia.update({
            "src": src, "encuadre": {"x": _num(enc.get("x", 50), 0, 100, 50), "y": _num(enc.get("y", 50), 0, 100, 50),
                                     "zoom": _num(enc.get("zoom", 1), 1, 4, 1)},
            "radio": _radio(capa.get("radio")), "borde": _borde(capa.get("borde")),
            "sombra": _sombras(capa.get("sombra")),
        })
    elif tipo == "logo":
        variante = capa.get("variante") if capa.get("variante") in ("auto", "normal", "oscuro") else "auto"
        fondo = capa.get("fondo_auto") if isinstance(capa.get("fondo_auto"), str) and capa.get("fondo_auto") in VAR_ROL else "l"
        limpia.update({"variante": variante, "fondo_auto": fondo})
    else:
        figura = capa.get("figura") if capa.get("figura") in ("rect", "elipse", "poligono") else "rect"
        puntos = []
        if figura == "poligono":
            for p in (capa.get("puntos") if isinstance(capa.get("puntos"), list) else [])[:MAX_PUNTOS]:
                if isinstance(p, list) and len(p) == 2:
                    puntos.append([_num(p[0], -100, 200), _num(p[1], -100, 200)])
            if len(puntos) < 3:
                figura, puntos = "rect", []
        limpia.update({"figura": figura, "puntos": puntos, "relleno": _relleno(capa.get("relleno")),
                       "borde": _borde(capa.get("borde")), "radio": _radio(capa.get("radio")),
                       "sombra": _sombras(capa.get("sombra"))})
    return limpia


def limpiar_doc(datos):
    """El documento en capas tal como se guarda. Rechaza lo que no se entiende
    y acota todo lo demás: es lo único que llega a `html_capas`."""
    if not isinstance(datos, dict):
        raise ErrorGraficas("las capas no tienen la forma esperada")
    if datos.get("version", VERSION) != VERSION:
        raise ErrorGraficas("esa versión de capas no la conozco")
    if not isinstance(datos.get("formato") or "", str):
        raise ErrorGraficas("ese tamaño no está en la lista")
    G.formato(datos.get("formato") or G.FORMATO_DEFECTO)
    laminas = datos.get("laminas")
    if not isinstance(laminas, list) or not 1 <= len(laminas) <= MAX_LAMINAS:
        raise ErrorGraficas(f"una pieza tiene de 1 a {MAX_LAMINAS} láminas")
    vistos = set()
    limpias = []
    for lamina in laminas:
        capas = (lamina or {}).get("capas") if isinstance(lamina, dict) else None
        if not isinstance(capas, list):
            raise ErrorGraficas("una lámina no tiene la forma esperada")
        if len(capas) > MAX_CAPAS:
            raise ErrorGraficas(f"una lámina admite hasta {MAX_CAPAS} capas")
        try:
            capas = [_limpiar_capa(c, vistos) for c in capas]
        except (TypeError, ValueError, KeyError, AttributeError) as fallo:
            # lo que llegue con una forma que no se espera es un 400, nunca un 500
            raise ErrorGraficas("una capa no tiene la forma esperada") from fallo
        if sum(1 for c in capas if c["tipo"] == "imagen" and c["src"]) > MAX_FOTOS:
            raise ErrorGraficas(f"una lámina admite hasta {MAX_FOTOS} fotos")
        if sum(1 for c in capas if c["tipo"] == "logo") > MAX_LOGOS:
            raise ErrorGraficas(f"una lámina admite hasta {MAX_LOGOS} logos")
        limpias.append({"capas": capas})
    origen = datos.get("origen") if isinstance(datos.get("origen"), dict) else {}
    plantilla = origen.get("plantilla")
    return {
        "version": VERSION, "formato": datos.get("formato") or G.FORMATO_DEFECTO,
        "nombre": " ".join(str(datos.get("nombre") or "")[:400].split())[:80],
        "colores": G._limpiar_colores(datos.get("colores")),
        # una tipografía que ya no está en la lista vuelve a la del Kit: la pieza
        # se sigue abriendo (como las de cada capa)
        "fuente_titulos": datos.get("fuente_titulos") if datos.get("fuente_titulos") in G.FUENTES else "",
        "fuente_texto": datos.get("fuente_texto") if datos.get("fuente_texto") in G.FUENTES else "",
        "origen": {"plantilla": plantilla if type(plantilla) is int and plantilla in G._PL.PLANTILLAS else None,
                   "sello": re.sub(r"[^0-9a-f]", "", str(origen.get("sello") or "")[:64])[:16],
                   "guardado": re.sub(r"[^0-9a-f]", "", str(origen.get("guardado") or "")[:64])[:16],
                   "nacida": _bool(origen.get("nacida"))},
        "laminas": limpias,
    }


# ====================================================================== pintar

def _f(n):
    """Un número para CSS: corto y sin notación científica."""
    texto = f"{n:.6f}".rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto


def _hex_a_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def resolver_color(ref, colores):
    """La referencia de una capa -> #RRGGBB con los colores de esta pieza."""
    if ref.startswith("#"):
        return ref
    tipo, rol = ref.split(":")
    if tipo == "kit":
        return colores[rol]
    return G._tinta_para(colores[rol], colores["oscuro"], colores["claro"])


def _css_color(ref, alfa, colores):
    color = resolver_color(ref, colores)
    if alfa >= 1:
        return color
    r, g, b = _hex_a_rgb(color)
    return f"rgba({r},{g},{b},{_f(alfa)})"


def _css_relleno(relleno, colores):
    if not relleno:
        return ""
    if "degradado" in relleno:
        d = relleno["degradado"]
        paradas = ", ".join(_css_color(p["color"], p["alfa"], colores) + ("" if p["pos"] is None else f" {_f(p['pos'])}%")
                            for p in d["paradas"])
        return f"background:linear-gradient({_f(d['ang'])}deg, {paradas});"
    return f"background:{_css_color(relleno['color'], relleno['alfa'], colores)};"


def _css_borde(borde, colores):
    if not borde:
        return ""
    # el navegador redondea los bordes HACIA ABAJO a píxeles enteros: sin la
    # centésima, 7 px guardados como 0,648148 cqmin salían de 6 px
    anchos = " ".join(f"calc({_f(a)}cqmin + 0.01px)" if a else "0" for a in borde["anchos"])
    return f"border-style:solid;border-width:{anchos};border-color:{_css_color(borde['color'], borde['alfa'], colores)};"


def _css_radio(radio):
    if radio == "elipse":
        return "border-radius:50%;"
    return f"border-radius:{_f(radio)}cqmin;" if radio else ""


def _css_sombras(sombras, colores, propiedad):
    if not sombras:
        return ""
    partes = []
    for s in sombras:
        color = _css_color(s["color"], s["alfa"], colores)
        if propiedad == "box-shadow":
            partes.append(f"{color} {_f(s['x'])}cqmin {_f(s['y'])}cqmin {_f(s['blur'])}cqmin {_f(s['spread'])}cqmin")
        else:
            partes.append(f"{color} {_f(s['x'])}cqmin {_f(s['y'])}cqmin {_f(s['blur'])}cqmin")
    return f"{propiedad}:{', '.join(partes)};"


def _css_caja(capa, f, alto_fijo=True, holgura=0.0):
    # + 2 milésimas de píxel: el navegador mide en 1/64 de píxel y redondea
    # hacia abajo; sin ellas, una posición que vuelve de % con un error de una
    # millonésima caía 1/64 más arriba o a la izquierda y cambiaba el suavizado
    estilo = (f"position:absolute;box-sizing:border-box;left:calc({_f(capa['x'])}cqw + {_f(0.002 - holgura)}px);"
              f"top:calc({_f(capa['y'])}cqh + 0.002px);width:calc({_f(capa['w'])}cqw + 0.002px);")
    estilo += f"height:calc({_f(capa['h'])}cqh + 0.002px);" if alto_fijo else ""
    if capa["giro"]:
        estilo += f"transform:rotate({_f(capa['giro'])}deg);"
        # el punto de giro, medido desde la esquina de la caja SIN la holgura del
        # texto (si fuera en % de la caja, esa décima de píxel lo movería)
        ox, oy = capa["origen"][0] / 100 * capa["w"], capa["origen"][1] / 100 * capa["h"]
        estilo += f"transform-origin:calc({_f(ox)}cqw + {_f(holgura)}px) {_f(oy)}cqh;"
    if capa["opac"] < 1:
        estilo += f"opacity:{_f(capa['opac'])};"
    return estilo


def _familia(capa, doc, kit):
    fuente = capa["fuente"]
    fid = fuente["id"]
    if fuente["rol"] == "titulos":
        fid = doc["fuente_titulos"] or (kit or {}).get("fuente_titulos") or fid
    elif fuente["rol"] == "texto":
        fid = doc["fuente_texto"] or (kit or {}).get("fuente_texto") or fid or "poppins"
    fid = fid if fid in G.FUENTES else "poppins"
    return fid, f"'{G.FUENTES[fid][0]}', {'serif' if fuente['serif'] else 'sans-serif'}"


_TAMANOS_IMAGEN = {}


def _tamano_imagen(ruta):
    from PIL import Image                                   # noqa: PLC0415
    clave = (ruta, os.path.getmtime(ruta))
    if clave not in _TAMANOS_IMAGEN:
        with Image.open(ruta) as im:
            _TAMANOS_IMAGEN[clave] = im.size
    return _TAMANOS_IMAGEN[clave]


def encaje(capa, f, iw, ih):
    """Dónde va la foto dentro de su caja: el mismo recorte que hacía
    `object-view-box` (encuadre y zoom), hecho con posición y tamaño para que
    salga igual en cualquier navegador. En % de la caja de dentro del borde."""
    minimo = min(f["W"], f["H"]) / 100
    anchos = (capa.get("borde") or {}).get("anchos") or [0, 0, 0, 0]
    bw = capa["w"] / 100 * f["W"] - (anchos[1] + anchos[3]) * minimo
    bh = capa["h"] / 100 * f["H"] - (anchos[0] + anchos[2]) * minimo
    if bw <= 0 or bh <= 0 or not iw or not ih:
        return 0, 0, 100, 100
    enc = capa["encuadre"]
    sw, sh = iw / enc["zoom"], ih / enc["zoom"]
    sx, sy = (iw - sw) * enc["x"] / 100, (ih - sh) * enc["y"] / 100
    k = max(bw / sw, bh / sh)
    ox, oy = (bw - sw * k) * enc["x"] / 100, (bh - sh * k) * enc["y"] / 100
    return ((ox - sx * k) / bw * 100, (oy - sy * k) / bh * 100, iw * k / bw * 100, ih * k / bh * 100)


def _uri(ruta, memo):
    """El fichero dentro de la página (data URI), leído UNA vez por pintado
    aunque lo usen varias capas."""
    if ruta not in memo:
        memo[ruta] = G._data_uri(ruta)
    return memo[ruta]


def _html_capa(capa, doc, kit, colores, f, imagen_de, logos, usadas, memo):
    if capa["oculto"]:
        return ""
    recorte = capa.get("recorte")
    if recorte:
        # la capa va dentro de una caja que corta lo que se sale, con su
        # posición contada desde esa caja (las medidas cq siguen siendo del lienzo)
        dentro = dict(capa, recorte=None, x=capa["x"] - recorte["x"], y=capa["y"] - recorte["y"])
        html = _html_capa(dentro, doc, kit, colores, f, imagen_de, logos, usadas, memo)
        if not html:
            return ""
        caja = (f"position:absolute;overflow:hidden;left:calc({_f(recorte['x'])}cqw + 0.002px);"
                f"top:calc({_f(recorte['y'])}cqh + 0.002px);width:calc({_f(recorte['w'])}cqw + 0.002px);"
                f"height:calc({_f(recorte['h'])}cqh + 0.002px);{_css_radio(recorte['radio'])}")
        return f'<div data-recorte="{capa["id"]}" style="{caja}">{html}</div>'

    tipo = capa["tipo"]
    if tipo == "forma":
        estilo = _css_caja(capa, f) + _css_relleno(capa["relleno"], colores) + _css_borde(capa["borde"], colores)
        estilo += _css_sombras(capa["sombra"], colores, "box-shadow")
        if capa["figura"] == "elipse":
            estilo += "border-radius:50%;"
        else:
            estilo += _css_radio(capa["radio"])
        if capa["figura"] == "poligono":
            puntos = ", ".join(f"{_f(x)}% {_f(y)}%" for x, y in capa["puntos"])
            estilo += f"clip-path:polygon({puntos});"
        return f'<div data-c="{capa["id"]}" data-r="{capa["rol"]}" style="{estilo}"></div>'
    if tipo == "imagen":
        estilo = _css_caja(capa, f) + _css_borde(capa["borde"], colores) + _css_radio(capa["radio"])
        estilo += _css_sombras(capa["sombra"], colores, "box-shadow") + "overflow:hidden;"
        ruta = imagen_de(capa["src"]) if capa["src"] else None
        if not ruta:
            # sin foto: un bloque de color, nunca una imagen rota (como el motor de siempre)
            estilo += f"background:linear-gradient(135deg, {colores['principal']}, {colores['secundario']});"
            return f'<div data-c="{capa["id"]}" data-r="{capa["rol"]}" style="{estilo}"></div>'
        # el mismo método que el motor de siempre (object-fit y object-view-box):
        # así la foto sale con los mismos píxeles. La pantalla del editor, que
        # puede no ser Chromium, usa `encaje` (la misma cuenta con posición y tamaño).
        enc = capa["encuadre"]
        recorte = ""
        if enc["zoom"] > 1:
            lado = 100 / enc["zoom"]
            izq, arr = (100 - lado) * enc["x"] / 100, (100 - lado) * enc["y"] / 100
            recorte = (f"object-view-box:inset({_f(arr)}% {_f(100 - lado - izq)}% "
                       f"{_f(100 - lado - arr)}% {_f(izq)}%);")
        # la foto ES la capa (con su borde y sus esquinas), como en las plantillas
        estilo = estilo.replace("overflow:hidden;", "")
        return (f'<img data-c="{capa["id"]}" data-r="{capa["rol"]}" alt="" src="{_uri(ruta, memo)}" '
                f'style="{estilo}display:block;max-width:none;object-fit:cover;'
                f'object-position:{_f(enc["x"])}% {_f(enc["y"])}%;{recorte}">')
    if tipo == "logo":
        normal, oscuro = logos
        ruta = normal
        if oscuro and (capa["variante"] == "oscuro" or (
                capa["variante"] == "auto" and G._luz(colores[VAR_ROL[capa["fondo_auto"]]]) < 0.3)):
            ruta = oscuro
        if not ruta or not os.path.isfile(ruta):
            return ""
        return (f'<div data-c="{capa["id"]}" data-r="{capa["rol"]}" style="{_css_caja(capa, f)}">'
                f'<img class="logo" alt="" src="{_uri(ruta, memo)}" style="display:block;width:100%;height:100%;'
                f'max-width:none;max-height:none;object-fit:contain"></div>')
    # texto
    if not capa["txt"].strip():
        return ""
    fid, familia = _familia(capa, doc, kit)
    usadas.add(fid)
    alto_px = capa["h"] / 100 * f["H"]
    # 2/64 de píxel de holgura en el ancho (el navegador mide en 1/64 de píxel):
    # el texto se parte en las mismas líneas. Se reparte hacia donde no mueve
    # las letras: a la derecha si va a la izquierda, a los dos lados si va
    # centrado, a la izquierda si va a la derecha.
    holgura = {"izq": 0, "centro": 0.015625, "der": 0.03125}[capa["alin"]]
    estilo = _css_caja(capa, f, alto_fijo=False, holgura=holgura)
    estilo = estilo.replace(f"width:calc({_f(capa['w'])}cqw + 0.002px);", f"width:calc({_f(capa['w'])}cqw + 0.03325px);")
    estilo += f"min-height:calc({_f(capa['h'])}cqh + 0.002px);display:flex;flex-direction:column;"
    estilo += "justify-content:" + {"arriba": "flex-start", "centro": "center", "abajo": "flex-end"}[capa["valign"]] + ";"
    estilo += "text-align:" + {"izq": "left", "centro": "center", "der": "right"}[capa["alin"]] + ";"
    estilo += f"font-family:{familia};font-size:calc({_f(capa['tam'])}cqmin * var(--e, 1));font-weight:{capa['peso']};"
    estilo += f"font-style:{'italic' if capa['cursiva'] else 'normal'};"
    estilo += f"text-decoration:{'underline' if capa['subrayado'] else 'none'};"
    if capa["mayus"]:
        estilo += "text-transform:uppercase;"
    if capa["espaciado"]:
        estilo += f"letter-spacing:{_f(capa['espaciado'])}em;"
    estilo += f"line-height:{_f(capa['interlineado']) if capa['interlineado'] else 'normal'};"
    estilo += f"color:{_css_color(capa['color'], capa['alfa'], colores)};white-space:pre-line;"
    if any(capa["relleno"]):
        estilo += "padding:" + " ".join(f"{_f(p)}cqmin" for p in capa["relleno"]) + ";"
    estilo += _css_relleno(capa["fondo"], colores) + _css_borde(capa["borde"], colores) + _css_radio(capa["radio"])
    estilo += _css_sombras(capa["sombra"], colores, "box-shadow")
    estilo += _css_sombras(capa["sombra_texto"], colores, "text-shadow")
    # como en las plantillas: solo los campos de texto llevan clase «t» y data-e
    # (lo que miden los avisos y la comparación); un adorno de texto, no
    clase = f' class="t" data-e="{capa["rol"]}"' if capa["rol"] in G.CAMPOS else ""
    ajuste = f' data-ajusta="{_f(alto_px)}"' if capa["ajusta"] else ""
    return (f'<div{clase} data-c="{capa["id"]}" data-r="{capa["rol"]}"{ajuste} '
            f'style="{estilo}">{html_mod.escape(capa["txt"].strip())}</div>')


def html_capas(doc, kit=None, imagen_de=None, logo=None, logo_oscuro=None, lamina=0):
    """El documento de una lámina. `imagen_de(nombre) -> ruta o None`."""
    doc = limpiar_doc(doc)
    f = G.formato(doc["formato"])
    colores = G.colores_finales(kit, doc)
    _, margenes = G._variables(f, colores)
    if not 0 <= lamina < len(doc["laminas"]):
        raise ErrorGraficas("esa lámina no está")
    usadas = set()
    imagen_de = imagen_de or (lambda _n: None)
    memo = {}
    cuerpo = "".join(_html_capa(c, doc, kit, colores, f, imagen_de, (logo, logo_oscuro), usadas, memo)
                     for c in doc["laminas"][lamina]["capas"])
    faltan = [G.FUENTES[u][0] for u in usadas if not G.fuente_lista(u)]
    caras = "".join(G._css_de_fuente(u) for u in sorted(usadas))
    documento = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8"><style>'
        f"{caras}*{{box-sizing:border-box}}"
        "html,body{margin:0;width:100vw;height:100vh;overflow:hidden}"
        ".lienzo{position:relative;overflow:hidden;width:100vw;height:100vh;container-type:size;"
        f"font-family:'Poppins',sans-serif;background:{colores['oscuro']}}}"
        f"</style></head><body><div class=\"lienzo\">{cuerpo}</div></body></html>")
    return documento, f, margenes, faltan


_AJUSTAR = """(() => {
  let n = 0;
  for (const e of document.querySelectorAll('[data-ajusta]')) {
    const max = parseFloat(e.dataset.ajusta);
    let s = 1;
    while ((e.offsetHeight > max + 2 || e.scrollWidth > e.clientWidth + 2) && s > 0.6) {
      s = Math.round((s - 0.05) * 100) / 100;
      e.style.setProperty('--e', s);
      n++;
    }
  }
  return n;
})()"""


def pintar(pincel, doc, kit=None, imagen_de=None, logo=None, logo_oscuro=None, lamina=0):
    """-> (png, avisos, medida). Cada texto que «ajusta» baja su letra hasta
    caber en su caja (como el motor de siempre, con el mismo mínimo)."""
    documento, f, margenes, faltan = html_capas(doc, kit, imagen_de, logo, logo_oscuro, lamina)
    pincel.abrir(documento, f["W"], f["H"])
    reducidos = pincel.evaluar(_AJUSTAR) or 0
    medida = pincel.evaluar(G._MEDIR % (json.dumps(list(margenes)), "[]")) or {"fuera": [], "choca": []}
    avisos = []
    if medida["fuera"] or medida["choca"]:
        avisos.append("Un texto queda en lo que tapa la red o pisa a otro: revísalo con «Ver lo que tapa la red».")
    elif reducidos:
        avisos.append("Letra reducida en algún texto para que quepa en su caja.")
    if faltan:
        avisos.append(f"Aún no está la tipografía {', '.join(sorted(faltan))}: se ve una parecida.")
    return pincel.capturar(), avisos, medida


# ====================================================================== convertir

#: Lo que el navegador cuenta de cada elemento de la plantilla ya pintada.
_EXTRAER = r"""(() => {
  const L = document.querySelector('.lienzo');
  const todos = [L, ...L.querySelectorAll('*')];
  const indice = new Map(todos.map((e, i) => [e, i]));
  const salida = [];
  for (const e of todos) {
    const c = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    let texto = '';
    for (const n of e.childNodes) if (n.nodeType === 3) texto += n.textContent;
    let ff = '';
    for (let a = e; a && a !== document.body; a = a.parentElement) {
      const m = /font-family\s*:\s*([^;]+)/.exec(a.getAttribute('style') || '');
      if (m) { ff = m[1].trim(); break; }
    }
    let lineas = 0;
    if (texto.trim()) {
      const rg = document.createRange(); rg.selectNodeContents(e);
      lineas = new Set([...rg.getClientRects()].map(q => Math.round(q.top))).size;
    }
    salida.push({
      i: indice.get(e), padre: e === L ? -1 : indice.get(e.parentElement), tag: e.tagName.toLowerCase(),
      logo: e.classList.contains('logo'), de: e.dataset.e || '', t: e.classList.contains('t'),
      visible: e.getClientRects().length > 0 && c.visibility !== 'hidden',
      rect: [r.left, r.top, r.width, r.height], zoom: e.currentCSSZoom || 1,
      texto, ff, lineas, rect0: null,
      css: {display: c.display, position: c.position, transform: c.transform, translate: c.translate,
            rotate: c.rotate, scale: c.scale, zIndex: c.zIndex, opacity: c.opacity, overflow: c.overflow,
            flexDirection: c.flexDirection, justifyContent: c.justifyContent, alignItems: c.alignItems,
            color: c.color, bgc: c.backgroundColor, bgi: c.backgroundImage,
            bw: [c.borderTopWidth, c.borderRightWidth, c.borderBottomWidth, c.borderLeftWidth],
            bs: [c.borderTopStyle, c.borderRightStyle, c.borderBottomStyle, c.borderLeftStyle],
            bc: [c.borderTopColor, c.borderRightColor, c.borderBottomColor, c.borderLeftColor],
            radio: c.borderTopLeftRadius, boxShadow: c.boxShadow, textShadow: c.textShadow,
            fontSize: c.fontSize, fontWeight: c.fontWeight, fontStyle: c.fontStyle,
            fontFamily: c.fontFamily, deco: c.textDecorationLine, tt: c.textTransform,
            ls: c.letterSpacing, lh: c.lineHeight, ta: c.textAlign, clip: c.clipPath,
            pad: [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft]},
    });
  }
  // la caja SIN GIRAR de cada elemento: se quita el giro un instante y se vuelve a poner
  const girados = todos.filter(e => { const c = getComputedStyle(e); return c.transform !== 'none' || c.rotate !== 'none'; });
  const guardado = girados.map(e => ['transform', 'rotate'].map(p => [p, e.style.getPropertyValue(p), e.style.getPropertyPriority(p)]));
  for (const e of girados) { e.style.setProperty('transform', 'none', 'important'); e.style.setProperty('rotate', 'none', 'important'); }
  for (const e of todos) { const r = e.getBoundingClientRect(); salida[indice.get(e)].rect0 = [r.left, r.top, r.width, r.height]; }
  girados.forEach((e, i) => { for (const [p, v, pr] of guardado[i]) { if (v) e.style.setProperty(p, v, pr); else e.style.removeProperty(p); } });
  return salida;
})()"""

_RE_RGB = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)")


def _color_css(texto):
    """'rgb(…)'/'rgba(…)' -> (referencia, alfa)."""
    m = _RE_RGB.search(texto or "")
    if not m:
        return None, 0.0
    r, g, b = (int(round(float(m.group(i)))) for i in (1, 2, 3))
    alfa = m.group(4)
    alfa = 1.0 if alfa is None else (float(alfa[:-1]) / 100 if alfa.endswith("%") else float(alfa))
    color = f"#{r:02X}{g:02X}{b:02X}"
    return _DE_TESTIGO.get(color, color), round(alfa, 4)


def _px(texto):
    try:
        return float(str(texto).replace("px", ""))
    except ValueError:
        return 0.0


def _partir(texto):
    """Parte por comas de primer nivel (fuera de paréntesis)."""
    partes, nivel, actual = [], 0, ""
    for ch in texto:
        if ch == "(":
            nivel += 1
        elif ch == ")":
            nivel -= 1
        if ch == "," and nivel == 0:
            partes.append(actual.strip())
            actual = ""
        else:
            actual += ch
    if actual.strip():
        partes.append(actual.strip())
    return partes


def _degradado(texto):
    m = re.match(r"^linear-gradient\((.*)\)$", (texto or "").strip())
    if not m:
        return None
    partes = _partir(m.group(1))
    ang = 180.0
    if partes and not _RE_RGB.search(partes[0]):
        cabeza = partes.pop(0)
        if cabeza.endswith("deg"):
            ang = float(cabeza[:-3])
        else:
            ang = {"to top": 0, "to right": 90, "to bottom": 180, "to left": 270}.get(cabeza, 180)
    paradas = []
    for p in partes:
        color, alfa = _color_css(p)
        resto = _RE_RGB.sub("", p).strip()
        pos = float(resto[:-1]) if resto.endswith("%") else None
        paradas.append({"color": color or "#000000", "alfa": alfa, "pos": pos})
    # un tramo transparente toma el color del vecino: el navegador mezcla así
    for i, p in enumerate(paradas):
        if p["alfa"] == 0:
            vecino = next((q for q in paradas[i + 1:] + paradas[:i][::-1] if q["alfa"] > 0), None)
            if vecino:
                p["color"] = vecino["color"]
    return {"degradado": {"ang": ang, "paradas": paradas}} if len(paradas) >= 2 else None


def _sombras_css(texto, escala, caja):
    if not texto or texto == "none":
        return []
    salida = []
    for parte in _partir(texto):
        color, alfa = _color_css(parte)
        numeros = [_px(n) for n in re.findall(r"-?[\d.]+px", _RE_RGB.sub("", parte))]
        numeros += [0.0] * (4 - len(numeros))
        s = {"x": numeros[0] * escala, "y": numeros[1] * escala, "blur": numeros[2] * escala,
             "spread": numeros[3] * escala if caja else 0, "color": color or "#000000", "alfa": alfa}
        salida.append(s)
    return salida


def _giro(css):
    m = re.match(r"matrix\(([^)]+)\)", css.get("transform") or "")
    giro = 0.0
    if m:
        a, b = (float(v) for v in m.group(1).split(",")[:2])
        giro = math.degrees(math.atan2(b, a))
    rot = css.get("rotate") or "none"
    if rot.endswith("deg"):
        giro += float(rot[:-3])
    return giro


def _es_contexto(r):
    css = r["css"]
    return (css["position"] != "static" or css["transform"] != "none" or css["translate"] != "none"
            or css["rotate"] != "none" or css["scale"] != "none" or float(css["opacity"]) < 1
            or css["zIndex"] != "auto")


def _fuente_de(r):
    """De qué tipografía sale el texto: la de títulos del Kit, la de texto o una fija."""
    ff = r["ff"]
    serif = "serif" in ff and "sans-serif" not in ff
    m = re.search(r"var\(--ft,\s*'([^']+)'\)", ff)
    por_nombre = {v[0]: k for k, v in G.FUENTES.items()}
    if m:
        return {"rol": "titulos", "id": por_nombre.get(m.group(1), ""), "serif": serif}
    if ff and not ff.startswith("var("):
        familia = ff.split(",")[0].strip().strip("'\"")
        if familia in por_nombre:
            return {"rol": "fija", "id": por_nombre[familia], "serif": serif}
    return {"rol": "texto", "id": "", "serif": serif}


class _Convertidor:
    def __init__(self, registros, f, plantilla):
        self.r = registros
        self.W, self.H = f["W"], f["H"]
        self.uno = min(self.W, self.H) / 100           # 1 cqmin en px
        self.hijos = {}
        for r in registros:
            self.hijos.setdefault(r["padre"], []).append(r)
        self.plantilla = plantilla
        self.n = 0

    def _id(self):
        self.n += 1
        return f"c{self.n}"

    def _cadena(self, r):
        while r["padre"] >= 0:
            r = self.r[r["padre"]]
            yield r

    def _giro_total(self, r):
        return _giro(r["css"]) + sum(_giro(a["css"]) for a in self._cadena(r))

    def _opac_total(self, r):
        o = float(r["css"]["opacity"])
        for a in self._cadena(r):
            o *= float(a["css"]["opacity"])
        return o

    def _cq(self, px, r):
        return px * r["zoom"] / self.uno

    def _base(self, r, tipo, rol, nombre):
        giro = self._giro_total(r)
        L, T, A, B = r["rect0"]
        x, y, w, h = L / self.W * 100, T / self.H * 100, A / self.W * 100, B / self.H * 100
        origen = [50, 50]
        # si el giro viene de una caja de fuera (el sello entero), la capa gira
        # alrededor del centro de ESA caja: es el mismo giro que pinta el navegador
        girada = None
        for a in [r, *self._cadena(r)]:
            if abs(_giro(a["css"])) > 0.001:
                girada = a
        if girada is not None and girada is not r and A and B:
            gl, gt, ga, gb = girada["rect0"]
            origen = [(gl + ga / 2 - L) / A * 100, (gt + gb / 2 - T) / B * 100]
        return {"_i": r["i"], "id": self._id(), "tipo": tipo, "rol": rol, "nombre": nombre, "x": x, "y": y, "w": w, "h": h,
                "giro": round(giro, 6), "opac": round(self._opac_total(r), 6), "oculto": False, "bloqueado": False,
                "origen": origen}

    def _borde_de(self, r):
        css = r["css"]
        anchos = [self._cq(_px(a), r) if css["bs"][i] not in ("none", "hidden") else 0 for i, a in enumerate(css["bw"])]
        if not any(anchos):
            return None
        lado = next(i for i, a in enumerate(anchos) if a)
        color, alfa = _color_css(css["bc"][lado])
        return {"anchos": anchos, "color": color or "#000000", "alfa": alfa}

    def _radio_de(self, r):
        radio = r["css"]["radio"]
        if radio.endswith("%"):
            return "elipse" if float(radio[:-1]) >= 50 else self._cq(float(radio[:-1]) / 100 * min(r["rect"][2], r["rect"][3]) / r["zoom"], r)
        return self._cq(_px(radio.split()[0]), r)

    def _relleno_de(self, r):
        css = r["css"]
        if css["bgi"] and css["bgi"] != "none":
            return _degradado(css["bgi"])
        color, alfa = _color_css(css["bgc"])
        return {"color": color, "alfa": alfa} if color and alfa > 0 else None

    def _nombre(self, rol, defecto):
        return G.CAMPOS[rol][0] if rol in G.CAMPOS else defecto

    def _con_recorte(self, r, capa):
        """Si la capa sale de una caja que corta lo que se sale y de verdad se
        sale, la capa se lleva ese corte."""
        if capa is None:
            return None
        caja = next((a for a in self._cadena(r) if a["padre"] >= 0 and a["css"]["overflow"] in ("hidden", "clip")), None)
        if caja is None or abs(_giro(caja["css"])) > 0.001:
            return capa
        bordes = [_px(b) * caja["zoom"] for b in caja["css"]["bw"]]
        L, T, A, B = caja["rect0"]
        cl, ct, cr, cb = L + bordes[3], T + bordes[0], L + A - bordes[1], T + B - bordes[2]
        x0, y0, w0, h0 = r["rect"]
        if x0 >= cl - 0.5 and y0 >= ct - 0.5 and x0 + w0 <= cr + 0.5 and y0 + h0 <= cb + 0.5:
            return capa
        radio = self._radio_de(caja)
        if radio != "elipse" and radio:
            radio = max(0.0, radio - max(bordes) / self.uno)
        capa["recorte"] = {"x": cl / self.W * 100, "y": ct / self.H * 100, "w": (cr - cl) / self.W * 100,
                           "h": (cb - ct) / self.H * 100, "radio": radio}
        return capa

    def capa_de(self, r):
        """La capa de un elemento, o None si no pinta nada por sí mismo."""
        return self._con_recorte(r, self._capa_de(r))

    def _capa_de(self, r):
        css = r["css"]
        if r["tag"] == "img" and r["logo"]:
            capa = self._base(r, "logo", "logo", "Logo")
            capa.update({"variante": "auto", "fondo_auto": G.FONDO_MARCA.get(self.plantilla, "l")})
            return capa
        if r["tag"] == "img":
            capa = self._base(r, "imagen", "foto", "Foto")
            radio, borde = self._radio_de(r), self._borde_de(r)
            # la foto suele ir dentro de una caja que la recorta (esquinas, círculo)
            for a in self._cadena(r):
                if a["padre"] < 0:
                    break
                if a["css"]["overflow"] in ("hidden", "clip"):
                    rad = self._radio_de(a)
                    if rad == "elipse":
                        radio = "elipse"
                    elif rad and not radio:
                        bordes = self._borde_de(a)
                        radio = max(0.0, rad - max((bordes or {}).get("anchos") or [0]))
                    break
            capa.update({"src": "", "encuadre": {"x": 50, "y": 50, "zoom": 1}, "radio": radio,
                         "borde": borde, "sombra": _sombras_css(css["boxShadow"], r["zoom"] / self.uno, True)})
            return capa
        texto = " ".join(r["texto"].split())
        if texto:
            rol = r["de"] or "deco"
            fuente = _fuente_de(r)
            tam_px = _px(css["fontSize"])
            alin = {"center": "centro", "right": "der", "end": "der"}.get(css["ta"], "izq")
            valign = "arriba"
            if css["display"] in ("flex", "inline-flex"):
                if css["flexDirection"].startswith("column"):
                    valign = {"center": "centro", "flex-end": "abajo", "end": "abajo"}.get(css["justifyContent"], "arriba")
                else:
                    valign = {"center": "centro", "flex-end": "abajo", "end": "abajo"}.get(css["alignItems"], "arriba")
                    if css["justifyContent"] == "center" and alin == "izq":
                        alin = "centro"
            color, alfa = _color_css(css["color"])
            lh = css["lh"]
            capa = self._base(r, "texto", rol, self._nombre(rol, "Texto"))
            capa.update({
                "txt": texto, "fuente": fuente, "tam": self._cq(tam_px, r),
                "peso": int(float(css["fontWeight"])), "cursiva": css["fontStyle"] == "italic",
                "subrayado": "underline" in css["deco"], "mayus": css["tt"] == "uppercase",
                "espaciado": 0 if css["ls"] == "normal" else round(_px(css["ls"]) / tam_px, 4),
                "interlineado": 0 if lh == "normal" else round(_px(lh) / tam_px, 4),
                "alin": alin, "valign": valign, "color": color or "#FFFFFF", "alfa": alfa,
                "fondo": self._relleno_de(r), "relleno": [self._cq(_px(p), r) for p in css["pad"]],
                "borde": self._borde_de(r), "radio": self._radio_de(r),
                "sombra": _sombras_css(css["boxShadow"], r["zoom"] / self.uno, True),
                "sombra_texto": _sombras_css(css["textShadow"], r["zoom"] / self.uno, False),
                "ajusta": r["t"] or r["de"] in G.CAMPOS,
            })
            return capa
        relleno, borde = self._relleno_de(r), self._borde_de(r)
        sombra = _sombras_css(css["boxShadow"], r["zoom"] / self.uno, True)
        if not (relleno or borde or sombra):
            return None
        rol = r["de"] or ("fondo" if r["padre"] < 0 else "deco")
        capa = self._base(r, "forma", rol, "Fondo" if rol == "fondo" else self._nombre(rol, "Forma"))
        radio = self._radio_de(r)
        figura, puntos = ("elipse" if radio == "elipse" else "rect"), []
        clip = re.match(r"polygon\((.*)\)$", css["clip"] or "")
        if clip:
            ancho_px, alto_px = capa["w"] / 100 * self.W / r["zoom"], capa["h"] / 100 * self.H / r["zoom"]
            for par in _partir(clip.group(1)):
                cx, cy = par.split()[-2:]
                puntos.append([float(cx[:-1]) if cx.endswith("%") else _px(cx) / ancho_px * 100,
                               float(cy[:-1]) if cy.endswith("%") else _px(cy) / alto_px * 100])
            figura = "poligono"
        capa.update({"figura": figura, "puntos": puntos, "relleno": relleno, "borde": borde,
                     "radio": 0 if radio == "elipse" else radio, "sombra": sombra})
        return capa

    def pintar_grupo(self, raiz):
        """Las capas de un grupo en el orden en que el navegador lo pinta:
        fondos de las cajas normales, luego textos, fotos y cajas de flex/grid
        (enteras y en orden), y al final lo posicionado, en orden."""
        salida = [self.capa_de(raiz)]
        fondos, contenido, encima = [], [], []

        def recorrer(nodo):
            for h in self.hijos.get(nodo["i"], []):
                if not h["visible"]:
                    continue
                if _es_contexto(h):
                    encima.append(h)
                    continue
                padre_flex = nodo["css"]["display"] in ("flex", "inline-flex", "grid", "inline-grid")
                if padre_flex or h["css"]["display"].startswith("inline-"):
                    contenido.append(("grupo", h))
                elif h["tag"] == "img" or " ".join(h["texto"].split()):
                    contenido.append(("hoja", h))
                else:
                    fondos.append(self.capa_de(h))
                    recorrer(h)
        recorrer(raiz)
        salida += fondos
        for clase, h in contenido:
            salida += self.pintar_grupo(h) if clase == "grupo" else [self.capa_de(h)]
        for h in encima:
            salida += self.pintar_grupo(h)
        return [c for c in salida if c]


def _imagen_de_muestra():
    """Una foto pequeña para pintar la plantilla con sus huecos de foto (las
    piezas sin foto se pintan con un bloque de color que ocupa lo mismo)."""
    from PIL import Image                                   # noqa: PLC0415
    salida = io.BytesIO()
    Image.new("RGB", (4, 4), (128, 128, 128)).save(salida, "JPEG")
    import base64                                            # noqa: PLC0415
    return "data:image/jpeg;base64," + base64.b64encode(salida.getvalue()).decode("ascii")


def convertir(pincel, pieza, kit=None, logo=None, logo_oscuro=None):
    """La pieza de siempre -> documento en capas. No escribe nada. Si `pieza`
    es una ficha guardada, el doc lleva su sello (para guardar sin pisar nada)."""
    sello = str((pieza or {}).get("sello") or "") if isinstance(pieza, dict) else ""
    pieza = G.limpiar_pieza(pieza)
    f = G.formato(pieza["formato"])
    testigos = {"imagen_uri": _imagen_de_muestra(),
                "variables": {_TESTIGO_VAR[ref]: color for ref, color in TESTIGOS.items()}}
    # lo oculto con el editor de antes: se pinta aparte para no perder su capa
    ocultos = [c for c, d in pieza["capas"].items() if d.get("oculto")]

    def pasada(p):
        documento, _f2, margenes, _ = G.html_de(p, kit, None, logo, logo_oscuro, _testigos=testigos)
        pincel.abrir(documento, f["W"], f["H"])
        retocados = [c for c, d in p["capas"].items() if any(k in d for k in ("x", "y", "escala"))]
        G._ajustar(pincel, margenes, retocados)
        conv = _Convertidor(pincel.evaluar(_EXTRAER), f, p["plantilla"])
        raiz = conv.r[0]
        return conv.pintar_grupo(raiz)

    capas = pasada(pieza)
    if ocultos:
        # se pinta otra vez con todo visible: lo que sale ahí y no en la pieza
        # (lo oculto y TODO lo que cuelga de ello, como los textos del sello) se
        # guarda como capa oculta y EN SU SITIO; lo demás, con la medida de la
        # pieza tal como está. El elemento de origen es el mismo en las dos
        # pasadas (ocultar no quita nada de la página).
        visibles = dict(pieza, capas={c: {k: v for k, v in d.items() if k != "oculto"} for c, d in pieza["capas"].items()})
        de_la_pieza = {c["_i"]: c for c in capas}
        todas = []
        for capa in pasada(visibles):
            if capa["_i"] in de_la_pieza:
                todas.append(de_la_pieza.pop(capa["_i"]))
            else:
                capa["oculto"] = True
                todas.append(capa)
        capas = todas + list(de_la_pieza.values())
        for n, capa in enumerate(capas, 1):
            capa["id"] = f"c{n}"
    for capa in capas:
        if capa["tipo"] == "imagen":
            capa["src"] = pieza["imagen"]
            if pieza["encuadre"]:
                capa["encuadre"] = dict(pieza["encuadre"])
        if capa["rol"] == "fondo":
            capa["bloqueado"] = True
    return limpiar_doc({
        "version": VERSION, "formato": pieza["formato"], "nombre": pieza["nombre"],
        "colores": pieza["colores"], "fuente_titulos": pieza["fuente_titulos"],
        "fuente_texto": pieza["fuente_texto"],
        "origen": {"plantilla": pieza["plantilla"], "sello": sello}, "laminas": [{"capas": capas}],
    })


# ====================================================================== comparar

_MEDIR_TEXTOS = r"""(() => {
  const W = innerWidth, H = innerHeight, salida = {};
  for (const e of document.querySelectorAll('[data-e]')) {
    let texto = ''; for (const n of e.childNodes) if (n.nodeType === 3) texto += n.textContent;
    if (!texto.trim() || !e.getClientRects().length || salida[e.dataset.e]) continue;
    const rg = document.createRange(); rg.selectNodeContents(e);
    const q = [...rg.getClientRects()], b = rg.getBoundingClientRect();
    salida[e.dataset.e] = {lineas: new Set(q.map(x => Math.round(x.top))).size, caja: [b.left, b.top, b.width, b.height],
                           texto: texto.replace(/\s+/g, ' ').trim()};
  }
  return salida;
})()"""


def diferencia(png_a, png_b, umbral=8):
    """Qué parte de los píxeles cambia (de 0 a 1): cuenta como distinto el que
    tiene algún canal que se aleja más de `umbral` sobre 255."""
    from PIL import Image, ImageChops                       # noqa: PLC0415
    a = Image.open(io.BytesIO(png_a)).convert("RGB")
    b = Image.open(io.BytesIO(png_b)).convert("RGB")
    if a.size != b.size:
        return 1.0
    canales = ImageChops.difference(a, b).split()
    mayor = ImageChops.lighter(ImageChops.lighter(canales[0], canales[1]), canales[2])
    distintos = mayor.point(lambda v: 255 if v > umbral else 0).histogram()[255]
    return distintos / (a.size[0] * a.size[1])


def diferencia_visible(png_a, png_b, umbral=24):
    """Como `diferencia`, pero sin contar el suavizado de los bordes: un píxel
    solo cuenta si no se parece a NINGUNO de sus vecinos en la otra imagen.
    Caza lo que se ve (algo movido, que falta o de otro color) y no el medio
    píxel con que el navegador suaviza distinto un texto girado suelto que
    dentro de su caja (medido el 11-11: 0,4 % con el mismo texto en el mismo sitio)."""
    from PIL import Image, ImageChops, ImageFilter          # noqa: PLC0415
    a = Image.open(io.BytesIO(png_a)).convert("RGB")
    b = Image.open(io.BytesIO(png_b)).convert("RGB")
    if a.size != b.size:
        return 1.0
    total = None
    for x, y in ((a, b), (b, a)):
        bajo = y.filter(ImageFilter.MinFilter(3))
        alto = y.filter(ImageFilter.MaxFilter(3))
        fuera = ImageChops.lighter(ImageChops.subtract(bajo, x), ImageChops.subtract(x, alto))
        c = fuera.split()
        mayor = ImageChops.lighter(ImageChops.lighter(c[0], c[1]), c[2]).point(lambda v: 255 if v > umbral else 0)
        total = mayor if total is None else ImageChops.lighter(total, mayor)
    return total.histogram()[255] / (a.size[0] * a.size[1])


def comparar(pincel, pieza, kit=None, imagen=None, logo=None, logo_oscuro=None, imagen_de=None, _tocar=None):
    """Pinta la pieza como siempre y convertida en capas, y las compara. No escribe.
    «igual»: lo visible cambia en menos del 0,1 % de los píxeles, lo estricto
    en menos del 2 %, ningún texto cambia de número de líneas y ninguna caja de
    texto se mueve más de 1 px, y están los mismos textos diciendo lo mismo. Lo estricto no llega a 0 en dos casos, medidos
    el 11-11 con las letras en el mismo sitio: el texto girado dentro de una
    caja girada (el sello, hasta 0,32 %) y un texto movido con el editor de
    antes (su desplazamiento no cae en la rejilla de 1/64 de píxel: 9 milésimas
    de píxel, hasta 1,4 % en un titular girado). Un cambio de color, por
    pequeño que sea, pasa del 2 % en cuanto toca algo más que un borde.
    -> {"igual", "diferencia", "visible", "lineas", "faltan", "movidos", "doc", "png_antes", "png_capas"}"""
    antes, _avisos, _m = G.pintar(pincel, pieza, kit, imagen, logo, logo_oscuro)
    textos_antes = pincel.evaluar(_MEDIR_TEXTOS) or {}
    doc = convertir(pincel, pieza, kit, logo, logo_oscuro)
    if _tocar:                       # solo las pruebas: ¿caza la comparación un cambio?
        _tocar(doc)
    if imagen_de is None:
        imagen_de = lambda nombre: imagen if nombre else None   # noqa: E731
    despues, _a, _m2 = pintar(pincel, doc, kit, imagen_de, logo, logo_oscuro)
    textos_despues = pincel.evaluar(_MEDIR_TEXTOS) or {}
    lineas, movidos = [], []
    # un texto que falta, sobra o dice otra cosa no es «igual», aunque sea tan
    # pequeño que en píxeles no llegue al tope (visto en la revisión del 11-11:
    # sin la marca «Alba» la diferencia visible se quedaba en 0,06-0,1 %)
    faltan = sorted(set(textos_antes) ^ set(textos_despues))
    faltan += sorted(r for r in set(textos_antes) & set(textos_despues)
                     if textos_antes[r]["texto"] != textos_despues[r]["texto"])
    for rol, a in textos_antes.items():
        b = textos_despues.get(rol)
        if not b:
            continue
        if a["lineas"] != b["lineas"]:
            lineas.append(rol)
        if max(abs(x - y) for x, y in zip(a["caja"], b["caja"])) > 1:
            movidos.append(rol)
    dif, visible = diferencia(antes, despues), diferencia_visible(antes, despues)
    return {"igual": visible <= 0.001 and dif <= 0.02 and not lineas and not movidos and not faltan,
            "diferencia": dif, "visible": visible, "lineas": lineas, "faltan": faltan,
            "movidos": movidos, "doc": doc, "png_antes": antes, "png_capas": despues}


# ====================================================================== editor
# (rama graficas-2-editor, 12-11-2026). Lo que necesita el editor con capas
# libres además de leer, pintar y guardar. Nada de esto escribe en disco.

#: Cuántas líneas ocupa cada texto en la vista final (por id de capa): el
#: editor lo compara con lo que pinta la pantalla y avisa si un salto cambia.
_LINEAS_POR_CAPA = r"""(() => {
  const salida = {};
  for (const e of document.querySelectorAll('[data-c]')) {
    let texto = ''; for (const n of e.childNodes) if (n.nodeType === 3) texto += n.textContent;
    if (!texto.trim() || !e.getClientRects().length) continue;
    const rg = document.createRange(); rg.selectNodeContents(e);
    salida[e.dataset.c] = new Set([...rg.getClientRects()].map(q => Math.round(q.top))).size;
  }
  return salida;
})()"""


def contar_lineas(pincel):
    """-> {id de capa: líneas} de la página que el pincel tiene abierta."""
    lineas = pincel.evaluar(_LINEAS_POR_CAPA) or {}
    return {str(k): int(v) for k, v in lineas.items() if _RE_ID.fullmatch(str(k)) and isinstance(v, (int, float))}


#: los roles que pone la conversión a lo que sale de una plantilla
_ROLES_DE_PLANTILLA = frozenset(G.CAMPOS) | {"deco", "fondo", "foto", "logo"}


def montar(pincel, plantilla, formato, doc=None, textos=None, kit=None, logo=None, logo_oscuro=None, lamina=0):
    """«Volver a montar» y «Empezar de»: la plantilla `plantilla` en el tamaño
    `formato`, convertida en capas, con los textos y colores de `doc`.

    - Cada campo de la plantilla lleva el texto que tenía en la pieza (con sus
      saltos de línea) o, si no lo tenía, el de `textos` (lo que propone el
      editor). Si su color era uno propio (#RRGGBB) lo conserva; si era del
      Kit, toma el de la plantilla nueva, que es el que se lee sobre su fondo.
    - La primera foto de la pieza pasa a la foto de la plantilla, con su encuadre.
    - Lo que añadiste tú (capas sin papel de plantilla) y los campos que la
      plantilla nueva no usa se quedan encima, tal cual: no se pierde nada.
    - El resto del documento (nombre, colores, letras, las otras láminas y el
      sello para guardar sin pisar nada) no cambia.
    Solo cambia la lámina `lamina`. No escribe nada."""
    if type(plantilla) is not int or plantilla not in G._PL.PLANTILLAS:
        raise ErrorGraficas("esa plantilla no existe")
    G.formato(formato if isinstance(formato, str) else "")
    doc = limpiar_doc(doc) if doc is not None else limpiar_doc(
        {"formato": formato, "laminas": [{"capas": []}]})
    if type(lamina) is not int or not 0 <= lamina < len(doc["laminas"]):
        raise ErrorGraficas("esa lámina no está")
    textos = textos if isinstance(textos, dict) else {}
    capas = doc["laminas"][lamina]["capas"]
    de_la_pieza = {}
    for capa in capas:
        if capa["tipo"] == "texto" and capa["rol"] in G.CAMPOS and capa["txt"].strip():
            de_la_pieza.setdefault(capa["rol"], capa)
    # la foto de la plantilla; si no hay, la primera que añadiste tú
    foto = (next((c for c in capas if c["tipo"] == "imagen" and c["src"] and c["rol"] == "foto"), None)
            or next((c for c in capas if c["tipo"] == "imagen" and c["src"]), None))
    pieza_textos = {}
    for campo, (_, largo) in G.CAMPOS.items():
        crudo = de_la_pieza[campo]["txt"] if campo in de_la_pieza else str(textos.get(campo) or "")
        if crudo.strip():
            pieza_textos[campo] = crudo
    pieza = {"plantilla": plantilla, "formato": formato, "textos": pieza_textos,
             "imagen": foto["src"] if foto else "", "encuadre": dict(foto["encuadre"]) if foto else {},
             "colores": doc["colores"], "fuente_titulos": doc["fuente_titulos"],
             "fuente_texto": doc["fuente_texto"], "nombre": doc["nombre"]}
    nuevo = convertir(pincel, pieza, kit, logo, logo_oscuro)
    nuevas = nuevo["laminas"][0]["capas"]
    usados = set()
    for capa in nuevas:
        if capa["tipo"] == "texto" and capa["rol"] in G.CAMPOS:
            usados.add(capa["rol"])
            original = de_la_pieza.get(capa["rol"])
            crudo = original["txt"] if original else str(textos.get(capa["rol"]) or "")
            if crudo.strip():
                # el texto entero, con sus saltos (la plantilla lo midió en una línea)
                capa["txt"] = crudo
            if original and original["color"].startswith("#"):
                # un color propio (elegido a mano) se conserva; uno del Kit no:
                # el de la plantilla nueva es el que se lee sobre su fondo
                capa["color"], capa["alfa"] = original["color"], original["alfa"]
    sueltas = [c for c in capas if c["rol"] not in _ROLES_DE_PLANTILLA
               or (c["rol"] in G.CAMPOS and c["rol"] not in usados and c["tipo"] == "texto")]
    # una plantilla sin foto: la foto no se pierde; queda abajo del todo y
    # oculta (a sangre taparía la plantilla entera), lista para enseñarla
    con_foto = any(c["tipo"] == "imagen" for c in nuevas)
    abajo = [dict(foto, oculto=True)] if foto and not con_foto and foto["rol"] == "foto" else []
    if con_foto and foto is not None:
        # la foto que ha pasado a la plantilla no se queda también suelta
        sueltas = [c for c in sueltas if c is not foto]
    # ids únicos en todo el documento: las capas nuevas estrenan los suyos
    otras = {c["id"] for i, l in enumerate(doc["laminas"]) if i != lamina for c in l["capas"]}
    otras |= {c["id"] for c in sueltas + abajo}
    for capa in nuevas:
        while capa["id"] in otras:
            capa["id"] = "c" + secrets.token_hex(4)
        otras.add(capa["id"])
    doc["laminas"][lamina] = {"capas": (abajo + nuevas + sueltas)[:MAX_CAPAS]}
    doc["formato"] = formato
    doc["origen"]["plantilla"] = plantilla
    return limpiar_doc(doc)


# ====================================================================== guardar

class ErrorConflicto(ErrorGraficas):
    """La pieza cambió desde que se abrió: guardar pisaría lo más nuevo."""


def _rutas(raiz, cid, pieza_id):
    carpeta = G._carpeta_pieza(raiz, cid, pieza_id)
    rutas = {k: os.path.join(carpeta, f"capas.{k}") for k in ("json", "png", "jpg")}
    rutas["meta"] = os.path.join(carpeta, "capas.sello.json")
    return rutas


def leer(raiz, cid, pieza_id):
    """-> (ficha, doc o None). El doc solo si sigue valiendo, y con el sello
    de la pieza de la que salió (hay que devolverlo al guardar). Si vale pero
    no se puede leer, es un error: convertir de nuevo una pieza nacida en capas
    daría una plantilla vacía, y guardarla borraría el diseño. No escribe."""
    with G.cerrojo_pieza(cid, pieza_id):     # nunca a mitad de un guardado
        return _leer(raiz, cid, pieza_id)


def _estado(raiz, cid, pieza_id, ficha):
    """-> (vale, guardado, doc crudo), con la misma regla que la lista y la
    descarga (`graficas.capas_que_valen`), mirando siempre `capas.json`: se
    escribe antes que la ficha pequeña y tiene el número de verdad del último
    guardado (3.ª y 4.ª revisión del 11-11)."""
    vale = G.capas_que_valen(raiz, cid, pieza_id, ficha, exacto=True)
    try:
        crudo = G._leer_json(_rutas(raiz, cid, pieza_id)["json"])
    except ErrorGraficas:
        crudo = None
    return vale is not None, (vale or {}).get("guardado") or "", crudo


def _leer(raiz, cid, pieza_id):
    ficha = G.leer_pieza(raiz, cid, pieza_id)
    vale, guardado, crudo = _estado(raiz, cid, pieza_id, ficha)
    if not vale:
        if ficha.get("nacida_en_capas"):
            # su ficha es mínima: convertirla daría una plantilla vacía, y
            # guardarla borraría el diseño (visto en la revisión del 11-11)
            raise ErrorGraficas("la versión en capas de esta pieza no se puede leer")
        return ficha, None
    try:
        doc = limpiar_doc(crudo)
    except ErrorGraficas as fallo:
        raise ErrorGraficas("la versión en capas de esta pieza no se puede leer") from fallo
    doc["origen"]["sello"] = ficha["sello"]
    doc["origen"]["guardado"] = guardado
    return ficha, doc


def _escribir_bytes(ruta, contenido):
    temporal = f"{ruta}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(temporal, "wb") as fh:
        fh.write(contenido)
    os.replace(temporal, ruta)


def guardar(raiz, cid, doc, pieza_id=None, logo=None, logo_oscuro=None):
    """Guarda una pieza en capas. Con `pieza_id`, al lado de su pieza de siempre
    (que no se toca). Sin él, nace una pieza nueva solo en capas, con una ficha
    mínima y una copia en pieza.png/jpg para que la lista y la descarga de
    siempre (y `main`) la vean.

    El doc trae lo que se abrió: el sello de la pieza (`origen.sello`) y el
    número del último guardado en capas (`origen.guardado`; vacío si se abrió
    convertida). Lo dan `leer`, `convertir` y el propio `guardar`. Si la pieza
    cambió desde entonces —otro guardado con el editor de antes, o en capas
    desde otra pestaña—, no se guarda y se avisa (`ErrorConflicto`, un 409), en
    vez de pisar lo más nuevo en silencio. Cada guardado estrena número.

    Orden: pintar fuera del cerrojo (puede esperar su turno); con el cerrojo
    de la pieza, se vuelve a mirar el sello y se escriben PNG, JPG, el JSON y,
    lo último, `capas.sello.json`, que es lo que hace que la versión valga."""
    doc = limpiar_doc(doc)
    kit = G.leer_kit(raiz, cid)
    nueva = pieza_id is None
    sello_doc, guardado_doc = doc["origen"]["sello"], doc["origen"]["guardado"]

    def comprobar(ficha_actual):
        _vale, ultimo, _crudo = _estado(raiz, cid, pieza_id, ficha_actual)
        if ficha_actual.get("sello") != sello_doc or ultimo != guardado_doc:
            raise ErrorConflicto("esta pieza ha cambiado desde que la abriste: vuelve a abrirla y repite el cambio")

    if nueva:
        pieza_id = secrets.token_hex(6)
    else:
        comprobar(G.leer_pieza(raiz, cid, pieza_id))

    def imagen_de(nombre):
        return G.ruta_imagen(raiz, cid, nombre)

    png, avisos, _ = G._con_turno(lambda p: pintar(p, doc, kit, imagen_de, logo, logo_oscuro))
    jpg = G.a_jpg(png)
    f = G.formato(doc["formato"])
    ahora = time.strftime("%Y-%m-%dT%H:%M:%S")
    rutas = _rutas(raiz, cid, pieza_id)
    destino = G._carpeta_pieza(raiz, cid, pieza_id)
    with G.cerrojo_pieza(cid, pieza_id):
        ficha = None if nueva else G.leer_pieza(raiz, cid, pieza_id)
        if ficha is not None:
            comprobar(ficha)
        nacida = nueva or bool(ficha.get("nacida_en_capas"))
        if nacida:
            # la ficha mínima: la pieza sale en la lista y se descarga con el
            # código de antes, y se pone al día en cada guardado (mismo sello)
            ficha = dict(ficha or {}, plantilla=2, formato=doc["formato"], textos={}, imagen="", capas={},
                         encuadre={}, colores=doc["colores"], fuente_titulos=doc["fuente_titulos"],
                         fuente_texto=doc["fuente_texto"], nombre=doc["nombre"] or "Pieza en capas",
                         id=pieza_id, cid=cid, avisos=avisos, medida=f"{f['W']}×{f['H']}", cambiada=ahora,
                         nacida_en_capas=True)
            # sello nuevo en cada guardado: la miniatura de la lista se renueva
            ficha["sello"] = secrets.token_hex(4)
        os.makedirs(destino, exist_ok=True)
        if nacida:
            _escribir_bytes(os.path.join(destino, "pieza.png"), png)
            _escribir_bytes(os.path.join(destino, "pieza.jpg"), jpg)
        _escribir_bytes(rutas["png"], png)
        _escribir_bytes(rutas["jpg"], jpg)
        doc["origen"].update(sello=ficha["sello"], nacida=nacida, guardado=secrets.token_hex(8))
        G._escribir_json(rutas["json"], dict(doc, avisos=avisos, cambiada=ahora, medida=f"{f['W']}×{f['H']}"))
        meta = {"sello": ficha["sello"], "guardado": doc["origen"]["guardado"], "cambiada": ahora,
                "nombre": doc["nombre"] or ficha.get("nombre") or ""}
        if nacida:
            # en una nacida el sello cambia: primero la ficha (con el sello nuevo) y
            # luego la ficha pequeña; una nueva no sale en la lista hasta su ficha
            G._escribir_json(os.path.join(destino, "pieza.json"), ficha)
        G._escribir_json(rutas["meta"], meta)
    return {"id": pieza_id, "doc": doc, "avisos": avisos, "cambiada": ahora}

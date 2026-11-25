"""Las familias de carrusel de Gráficas (rama graficas-3-carrusel, 19-11-2026).

Cada plantilla de Gráficas es una FAMILIA: su portada es la plantilla de
siempre (`graficas_capas.montar`) y las láminas de dentro hablan su mismo
idioma —la letra de títulos y de texto, el adorno, la forma del botón y los
colores del Kit—. Hay 8 tipos de lámina:

    portada   el gancho (la plantilla)
    punto     un número grande, un titular y una frase
    lista     de 3 a 5 viñetas numeradas
    dato      una cifra gigante
    antes_despues  dos columnas que comparan
    pasos     1-2-3, unidos por una línea
    cita      un testimonio
    cierre    la llamada a la acción y «Guárdalo»

Todo son capas del documento versión 2: se mueven y se escriben en el editor
como cualquier otra. Cada campo lleva su `rol` (numero, titulo, texto, v1…v5,
cifra, antes, despues, cita, autor, cta), así «Volver a montar» pasa cada texto
a su sitio en otra familia o en otro tamaño. Lo que no tiene rol de campo (lo
que añadiste tú y las copias «en todas») se queda tal cual.

Los colores se eligen con el Kit de cada cliente: el texto, el que se lee sobre
su fondo (`tinta:`); el de acento, el primero que llega al contraste (4,5:1 en
lo pequeño, 3:1 en lo grande) o, si ninguno, el que se lee. Nada de esto llama
a una IA ni escribe nada: solo compone.
"""
import re
import secrets
import unicodedata

import graficas as G
import graficas_capas as C
from graficas import ErrorGraficas

TIPOS = ("portada", "punto", "lista", "dato", "antes_despues", "pasos", "cita",
         "mito", "pregunta", "ranking", "checklist", "comparativa", "precio", "cierre")
NOMBRES_TIPO = {"portada": "Portada", "punto": "Punto", "lista": "Lista", "dato": "Dato",
                "antes_despues": "Antes / después", "pasos": "Pasos", "cita": "Cita",
                "mito": "Mito / Realidad", "pregunta": "Pregunta", "ranking": "Ranking", "checklist": "Checklist",
                "comparativa": "Comparativa", "precio": "Precio / oferta", "cierre": "Cierre"}
#: Los que tienen composición en horizontal (1,91:1 y 16:9). Los demás no caben bien.
TIPOS_HORIZONTAL = ("portada", "punto", "dato", "cita", "cierre")
#: Los campos de texto de las láminas de dentro (lo que «Volver a montar» lleva a su sitio).
ROLES = ("numero", "titulo", "texto", "v1", "v2", "v3", "v4", "v5", "cifra", "antes", "despues",
         "etiqueta1", "etiqueta2", "cita", "autor", "cta", "guardalo",
         # graficas-3c-extras: los tipos nuevos
         "mito", "realidad", "pregunta", "precio", "precio_antes")
#: Las capas «en todas» que pone un carrusel nuevo (un rol propio: «Volver a
#: montar» con plantilla las deja tal cual, y al cambiar de familia toman su estilo).
ROLES_EN_TODAS = ("en_marca", "en_numero", "en_desliza")
#: La letra mínima de cualquier texto (unos 30 px de 1080).
LETRA_MINIMA = 2.8
MAX_VINETAS = 5

#: n -> la ficha de estilo de su familia. `ft`/`fb`: letras de títulos y de
#: texto (las del Kit mandan si las tiene, como en las plantillas); `fondo`:
#: el de portada y cierre; `alterno`: el de dentro; `acento`: el preferido para
#: números y etiquetas (si no se lee, otro); `deco`: el adorno.
FAMILIAS = {
    1: dict(ft="anton", fb="poppins", mayus=True, fondo="principal", alterno="oscuro", acento="secundario",
            deco="circulo", radio=2.5, boton="relleno"),
    2: dict(ft="archivo", fb="poppins", mayus=False, fondo="oscuro", alterno="oscuro", acento="secundario",
            deco="barra", radio=1.5, boton="relleno"),
    3: dict(ft="poppins", fb="poppins", peso_t=800, mayus=False, fondo="principal", alterno="principal", tarjeta="claro",
            acento="principal", deco="tarjeta", radio=3, boton="relleno"),
    4: dict(ft="montserrat", fb="poppins", peso_t=900, mayus=True, fondo="principal", alterno="principal",
            acento="secundario", deco="franja", radio=1, boton="oscuro"),
    5: dict(ft="bebas", fb="poppins", mayus=True, fondo="claro", alterno="claro", marco="principal", acento="principal",
            deco="marco_color", radio=0, boton="relleno"),
    6: dict(ft="playfair", fb="lora", cursiva=True, mayus=False, fondo="claro", alterno="claro", acento="principal",
            deco="linea", radio=0, boton="linea"),
    7: dict(ft="anton", fb="poppins", mayus=True, fondo="secundario", alterno="claro", acento="principal",
            deco="sello", radio=2, boton="relleno"),
    8: dict(ft="spacegrotesk", fb="inter", mayus=False, fondo="claro", alterno="claro", acento="principal",
            deco="caja", radio=3, boton="relleno"),
    9: dict(ft="dmserif", fb="inter", mayus=False, fondo="claro", alterno="claro", acento="principal",
            deco="linea", radio=0, boton="contorno"),
    10: dict(ft="bebas", fb="poppins", mayus=True, fondo="oscuro", alterno="oscuro", acento="acento",
             deco="brillo", radio=5, boton="contorno"),
    11: dict(ft="syne", fb="nunito", peso_t=800, mayus=False, fondo="claro", alterno="claro", acento="principal",
             deco="circulo", radio=6, boton="relleno"),
    12: dict(ft="poppins", fb="poppins", peso_t=800, mayus=False, fondo="claro", alterno="claro", acento="principal",
             deco="barra", radio=2, boton="relleno"),
    13: dict(ft="montserrat", fb="montserrat", peso_t=900, mayus=True, fondo="oscuro", alterno="oscuro",
             acento="secundario", deco="banda", radio=1.5, boton="relleno"),
    14: dict(ft="playfair", fb="montserrat", mayus=False, fondo="claro", alterno="claro", acento="principal",
             deco="marco", radio=0, boton="linea", marca_espaciada=True),
    # graficas-3c-extras: Publicación (como un post, sin nada de ninguna red) y Gamer (esquinas de pantalla de juego)
    15: dict(ft="inter", fb="inter", peso_t=800, mayus=False, fondo="principal", alterno="principal", tarjeta="claro",
             acento="principal", deco="tarjeta", radio=3, boton="relleno"),
    16: dict(ft="oswald", fb="inter", peso_t=700, mayus=True, fondo="oscuro", alterno="oscuro", acento="secundario",
             deco="hud", radio=0, boton="relleno"),
}


def familia(n):
    if type(n) is not int or n not in FAMILIAS:
        raise ErrorGraficas("esa familia de carrusel no existe")
    nombre = next((nom for k, nom, _u, _c in G.CATALOGO if k == n), f"Familia {n}")
    return dict(FAMILIAS[n], n=n, nombre=nombre)


def catalogo():
    """Lo que la pantalla necesita para ofrecer familias y tipos."""
    return {"familias": [{"n": n, "nombre": familia(n)["nombre"]} for n in sorted(FAMILIAS)],
            "tipos": [{"id": t, "nombre": NOMBRES_TIPO[t], "horizontal": t in TIPOS_HORIZONTAL} for t in TIPOS],
            "max_vinetas": MAX_VINETAS}


# ====================================================================== colores

def _contraste(a, b):
    return G.contraste(a, b)


def _ref_legible(fondo_rol):
    return f"tinta:{fondo_rol}"


def _acento_sobre(fam, fondo_rol, colores, grande):
    """El color de acento que se lee sobre `fondo_rol`: el de la familia o, si no
    llega al contraste (3:1 grande, 4,5:1 pequeño), otro del Kit; si ninguno, el
    texto que se lee. Así el amarillo pequeño sobre morado nunca sale."""
    minimo = 3 if grande else 4.5
    fondo = colores[fondo_rol]
    for rol in (fam["acento"], "principal", "secundario", "acento"):
        if rol != fondo_rol and _contraste(colores[rol], fondo) >= minimo:
            return f"kit:{rol}"
    return _ref_legible(fondo_rol)


def _hay_comun(fam, fondos, colores):
    return any(all(_contraste(c, colores[f]) >= 4.5 for f in fondos)
               for c in [colores[r] for r in ROLES_KIT] + ["#FFFFFF", "#000000"])


ROLES_KIT = ("principal", "secundario", "acento", "claro", "oscuro")


def _legible_en_todos(fam, fondos, colores, grande, primero=None):
    """Un color que se lea sobre TODOS los `fondos` (una capa «en todas» es la
    misma en la portada, dentro y en el cierre, que pueden tener otro fondo):
    el preferido si llega, otro del Kit si no, y si ninguno, negro o blanco."""
    minimo = 3 if grande else 4.5
    for rol in ([primero] if primero else []) + [fam["acento"], "principal", "secundario", "acento", "claro", "oscuro"]:
        if all(rol != f and _contraste(colores[rol], colores[f]) >= minimo for f in fondos):
            return f"kit:{rol}"
    return max(("#FFFFFF", "#000000"), key=lambda c: min(_contraste(c, colores[f]) for f in fondos))


# ====================================================================== piezas

class _Lienzo:
    """Lo que hace falta para colocar: el tamaño, la caja útil y los ids."""

    def __init__(self, fam, formato_id, colores, marca):
        self.fam = fam
        self.f = G.formato(formato_id)
        self.colores = colores
        self.marca = marca or ""
        self.horiz = self.f["W"] / self.f["H"] > 1.3
        self.cuad = self.f["W"] == self.f["H"]
        self.vertical = self.f["H"] / self.f["W"] > 1.7
        f = self.f
        mg = 5 if self.horiz else 6
        self.m = {"t": max(mg, f["zT"] + 2), "r": max(mg, f["zR"] + 2), "b": max(mg, f["zB"] + 2), "l": max(mg, f["zL"] + 2)}
        extra = {"marco": 4, "marco_color": 5}.get(fam["deco"], 0)
        if extra:
            # dentro del marco: el marco va pegado al borde, el texto se aparta
            kx, ky = extra, extra * f["W"] / f["H"] if not self.horiz else extra
            self.m = {"t": self.m["t"] + ky, "r": self.m["r"] + kx, "b": self.m["b"] + ky, "l": self.m["l"] + kx}
        if fam["deco"] == "barra":
            self.m["l"] += 3
        self.ids = set()

    def id(self):
        nuevo = "c" + secrets.token_hex(4)
        while nuevo in self.ids:
            nuevo = "c" + secrets.token_hex(4)
        self.ids.add(nuevo)
        return nuevo

    # el alto en % del alto que corresponde a `x` % del ancho (para lo redondo)
    def alto_de(self, ancho):
        return ancho * self.f["W"] / self.f["H"]

    def tam(self, t):
        """El tamaño de letra para este formato (cqmin), nunca por debajo del mínimo."""
        # en historias (9:16) hay más alto que llenar: la letra, un poco mayor
        k = 0.86 if self.cuad else (0.9 if self.horiz else (1.18 if self.vertical else 1))
        return max(LETRA_MINIMA, round(t * k, 2))

    def texto(self, txt, x, y, w, h, tam, rol="", titulo=False, color=None, peso=None, alin="izq", valign="arriba",
              mayus=None, fondo=None, relleno=None, radio=0, borde=None, interlineado=None, espaciado=0.0,
              cursiva=None, brillo=False, nombre="", ajusta=None):
        fam = self.fam
        sombra = []
        if brillo and fam["deco"] == "brillo":
            sombra = [{"x": 0, "y": 0, "blur": 1.6, "color": f"kit:{fam['acento']}", "alfa": 1},
                      {"x": 0, "y": 0, "blur": 4, "color": f"kit:{fam['acento']}", "alfa": 0.9}]
        return {"id": self.id(), "tipo": "texto", "rol": rol, "nombre": nombre, "txt": txt,
                "x": x, "y": y, "w": w, "h": h,
                "fuente": {"rol": "titulos" if titulo else "texto", "id": fam["ft"] if titulo else fam["fb"], "serif": False},
                "tam": self.tam(tam), "peso": peso or (fam.get("peso_t", 700) if titulo else 500),
                "mayus": (fam["mayus"] if mayus is None else bool(mayus)) if titulo else bool(mayus),
                "cursiva": (fam.get("cursiva", False) if cursiva is None else bool(cursiva)) if titulo else bool(cursiva),
                "color": color, "alfa": 1, "alin": alin, "valign": valign, "fondo": fondo,
                "relleno": relleno or [0, 0, 0, 0], "radio": radio, "borde": borde,
                "interlineado": interlineado if interlineado is not None else (1.05 if titulo else 1.3),
                "espaciado": espaciado, "sombra": [], "sombra_texto": sombra,
                "ajusta": titulo if ajusta is None else ajusta}

    def forma(self, x, y, w, h, color, figura="rect", radio=0, alfa=1.0, borde=None, puntos=None, nombre="", rol="deco"):
        return {"id": self.id(), "tipo": "forma", "rol": rol, "nombre": nombre, "figura": figura, "x": x, "y": y, "w": w, "h": h,
                "relleno": {"color": color, "alfa": alfa} if color else None, "radio": radio, "borde": borde,
                "puntos": puntos or [], "sombra": []}


def _caja_util(L):
    """La caja de dentro donde va el contenido (en % del lienzo), dejando arriba
    la franja de la marca y el número y abajo la del «Desliza →» y el adorno."""
    m = L.m
    cabecera = L.alto_de(7) if not L.horiz else 11
    pie = L.alto_de(8) if not L.horiz else 12
    reserva = {"circulo": L.alto_de(14) if not L.horiz else 0, "franja": _alto_franja(L) + pie - (L.m["b"] - 0),
               "sello": L.alto_de(10)}.get(L.fam["deco"], 0)
    x0, y0 = m["l"], m["t"] + cabecera
    x1, y1 = 100 - m["r"], 100 - m["b"] - max(pie, reserva)
    return x0, y0, x1 - x0, y1 - y0


def _fondo_y_adorno(L, tipo):
    """-> (capas de fondo y adorno, el rol del color sobre el que va el texto)."""
    fam, f = L.fam, L.f
    base = fam["fondo"] if tipo in ("portada", "cierre") else fam["alterno"]
    capas = [L.forma(0, 0, 100, 100, f"kit:{base}", nombre="Fondo", rol="fondo")]
    sobre = base
    d = fam["deco"]
    if d == "circulo":
        lado = 42 if not L.horiz else 30
        capas.append(L.forma(-lado * 0.35, 100 - L.alto_de(lado) * 0.42, lado, L.alto_de(lado),
                             f"kit:{_rol_visible(fam, base, L.colores)}", "elipse", nombre="Círculo"))
    elif d == "linea":
        y = L.m["t"] + (L.alto_de(6) if not L.horiz else 9.5)
        capas.append(L.forma(L.m["l"], y, 100 - L.m["l"] - L.m["r"], 0.25 * f["W"] / f["H"] if not L.horiz else 0.4,
                             f"tinta:{base}", nombre="Filete"))
    elif d == "marco":
        k = 4
        ky = L.alto_de(k) if not L.horiz else k
        capas.append(L.forma(k, ky, 100 - 2 * k, 100 - 2 * ky, None, nombre="Marco",
                             borde={"anchos": [0.25] * 4, "color": f"tinta:{base}", "alfa": 1}))
    elif d == "marco_color":
        capas.append(L.forma(0, 0, 100, 100, None, nombre="Marco de color",
                             borde={"anchos": [3.2] * 4, "color": f"kit:{fam['marco']}", "alfa": 1}))
    elif d == "franja":
        alto = _alto_franja(L)
        capas.append(L.forma(0, 100 - alto, 100, alto, f"kit:{_rol_visible(fam, base, L.colores)}", "poligono",
                             puntos=[[0, 45], [100, 0], [100, 100], [0, 100]], nombre="Franja"))
    elif d == "barra":
        capas.append(L.forma(L.m["l"] - 4, L.m["t"], 1.2, 100 - L.m["t"] - L.m["b"],
                             f"kit:{_rol_visible(fam, base, L.colores)}", nombre="Barra"))
    elif d == "banda":
        alto = L.m["t"] + (L.alto_de(5.4) if not L.horiz else 9)
        capas.append(L.forma(0, 0, 100, alto, f"kit:{_rol_visible(fam, base, L.colores)}", nombre="Banda"))
    elif d == "sello":
        # abajo a la izquierda: a la derecha va el «Desliza →»
        lado = 26 if not L.horiz else 18
        capas.append(L.forma(-lado * 0.3, 100 - L.alto_de(lado) * 0.62, lado, L.alto_de(lado),
                             f"kit:{_rol_visible(fam, base, L.colores)}", "elipse", nombre="Sello"))
    elif d == "hud":
        # cuatro esquinas en L, como el marco de una pantalla de juego (familia Gamer)
        lado, grosor = (11 if not L.horiz else 7), 1.1
        lado_y = L.alto_de(lado)
        color = f"kit:{_rol_visible(fam, base, L.colores)}"
        k, ky = 2.6, L.alto_de(2.6)
        for nombre, x, y, anchos in (("arriba izquierda", k, ky, [grosor, 0, 0, grosor]),
                                     ("arriba derecha", 100 - k - lado, ky, [grosor, grosor, 0, 0]),
                                     ("abajo izquierda", k, 100 - ky - lado_y, [0, 0, grosor, grosor]),
                                     ("abajo derecha", 100 - k - lado, 100 - ky - lado_y, [0, grosor, grosor, 0])):
            capas.append(L.forma(x, y, lado, lado_y, None, nombre=f"Esquina {nombre}",
                                 borde={"anchos": anchos, "color": color, "alfa": 1}))
    elif d == "tarjeta" and tipo not in ("portada",):
        x0, y0, w, h = _caja_util(L)
        # arriba, solo un poco de aire: más alto tapaba la marca «en todas» (visto en 9:16, 25-11)
        capas.append(L.forma(x0 - 2.5, y0 - L.alto_de(1.2), w + 5, h + L.alto_de(3.7), f"kit:{fam['tarjeta']}",
                             radio=fam["radio"], nombre="Tarjeta"))
        sobre = fam["tarjeta"]
    elif d == "caja" and tipo not in ("portada", "cierre"):
        x0, y0, w, h = _caja_util(L)
        lleno = tipo == "dato"
        color = f"kit:{_rol_visible(fam, base, L.colores)}"
        capas.append(L.forma(x0 - 2, y0 - L.alto_de(1.5), w + 4, h + L.alto_de(3), color, radio=fam["radio"],
                             alfa=1 if lleno else 0.12, nombre="Caja"))
        if lleno:
            sobre = _rol_visible(fam, base, L.colores)
    return capas, sobre


def _alto_franja(L):
    return L.alto_de(10) if not L.horiz else 14


def _rol_visible(fam, base, colores):
    """El rol del Kit para un adorno que se vea sobre `base` (no el mismo color)."""
    for rol in (fam["acento"], "principal", "secundario", "acento"):
        if rol != base and _contraste(colores[rol], colores[base]) >= 1.5:
            return rol
    return "claro" if base != "claro" else "oscuro"


def _color_de_cabecera(L, tipo):
    """El color de la marca y el número: sobre la banda, el que se lee sobre ella."""
    fam = L.fam
    base = fam["fondo"] if tipo in ("portada", "cierre") else fam["alterno"]
    if fam["deco"] == "banda":
        return _ref_legible(_rol_visible(fam, base, L.colores))
    return _ref_legible(base)


def en_todas(L, tipo_ref="punto"):
    """Las capas «en todas» de un carrusel nuevo: la marca (no en la portada,
    que trae la suya), el número y «Desliza →» (ni en la portada ni en la
    última; nunca en historias, TikTok ni el PDF)."""
    fam, m = L.fam, L.m
    base = fam["alterno"]
    fondos = sorted({fam["alterno"], fam["fondo"]})
    # si ningún color se lee a la vez sobre el fondo de dentro y el del cierre
    # (Kits de poco contraste), lo «en todas» no sale en el cierre
    sin_cierre = fam["fondo"] != base and not _hay_comun(fam, fondos, L.colores)
    if sin_cierre:
        fondos = [base]
    if fam["deco"] == "banda":
        color = _color_de_cabecera(L, tipo_ref)          # sobre la banda, que va en todas
    else:
        # la tinta del fondo de dentro si se lee también sobre el de la portada y el cierre
        legible = _ref_legible(base).split(":")[1]
        tinta = G._tinta_para(L.colores[base], L.colores["oscuro"], L.colores["claro"])
        color = (_ref_legible(base) if all(_contraste(tinta, L.colores[f]) >= 4.5 for f in fondos)
                 else _legible_en_todos(fam, fondos, L.colores, False, legible if legible in L.colores else None))
    y = m["t"] + (0.6 if not L.horiz else 1)
    alto = L.alto_de(4.5) if not L.horiz else 7
    marca = L.texto(L.marca or "Tu marca", m["l"], y, 55, alto, 3.0, rol="en_marca", peso=800, color=color,
                    mayus=bool(fam.get("marca_espaciada")), espaciado=0.25 if fam.get("marca_espaciada") else 0,
                    nombre="Marca (en todas)", ajusta=True)
    numero = L.texto("{n}/{total}", 100 - m["r"] - 22, y, 22, alto, 2.9, rol="en_numero", peso=700, alin="der",
                     color=_legible_en_todos(fam, fondos, L.colores, False) if fam["deco"] != "banda" else color,
                     nombre="Número (en todas)")
    pie_y = 100 - m["b"] - (L.alto_de(4.2) if not L.horiz else 6.5)
    if fam["deco"] == "franja":
        # encima de la franja, sobre el fondo (nunca a medias sobre ella)
        pie_y = 100 - _alto_franja(L) - (L.alto_de(5.4) if not L.horiz else 8)
    color_pie = _legible_en_todos(fam, fondos, L.colores, False)
    desliza = L.texto("Desliza  →", 100 - m["r"] - 40, pie_y, 40, L.alto_de(4.2) if not L.horiz else 6.5, 2.9,
                      rol="en_desliza", peso=700, alin="der", color=color_pie, nombre="Desliza (en todas)")
    fuera = ["primera", "ultima"] if sin_cierre else ["primera"]
    marca.update(enlace="m" + secrets.token_hex(4), salvo=fuera)
    numero.update(enlace="n" + secrets.token_hex(4), salvo=fuera, solo_horizontal=True)
    desliza.update(enlace="d" + secrets.token_hex(4), salvo=["primera", "ultima", "pdf"], solo_horizontal=True)
    return [marca, numero, desliza]


# ====================================================================== los tipos

#: Textos de muestra por tipo (español de Perú). Al descargar o publicar se avisa si siguen igual.
MUESTRA = {
    "punto": {"numero": "01", "titulo": "Una idea clara por lámina", "texto": "Explícala en una o dos frases cortas."},
    "lista": {"titulo": "Lo que no puede faltar", "v1": "Primera cosa", "v2": "Segunda cosa", "v3": "Tercera cosa"},
    "dato": {"cifra": "8 de 10", "texto": "clientes vuelven a pedirlo (cambia esta cifra por una tuya y real)"},
    "antes_despues": {"titulo": "La diferencia", "etiqueta1": "Antes", "etiqueta2": "Después",
                      "antes": "Cómo era antes", "despues": "Cómo es ahora"},
    "pasos": {"titulo": "Así de fácil", "v1": "Primer paso", "v2": "Segundo paso", "v3": "Tercer paso"},
    "cita": {"cita": "«Lo que dice un cliente, con sus palabras»", "autor": "Nombre, quién es"},
    # graficas-3c-extras: los 6 tipos nuevos
    "mito": {"etiqueta1": "Mito", "mito": "Lo que mucha gente cree", "etiqueta2": "Realidad",
             "realidad": "Lo que pasa de verdad (cámbialo por lo tuyo)"},
    "pregunta": {"pregunta": "¿Sabes cuál es el error más común?", "texto": "La respuesta, en la siguiente"},
    "ranking": {"titulo": "Nuestro top 3", "v1": "El primero", "v2": "El segundo", "v3": "El tercero"},
    "checklist": {"titulo": "Antes de empezar, revisa", "v1": "Primera cosa", "v2": "Segunda cosa", "v3": "Tercera cosa"},
    "comparativa": {"titulo": "¿Por qué nosotros?", "etiqueta1": "Nosotros", "etiqueta2": "Otros",
                    "v1": "Primera ventaja", "v2": "Segunda ventaja", "v3": "Tercera ventaja"},
    "precio": {"titulo": "Tu producto o servicio", "precio_antes": "S/ 120", "precio": "S/ 99",
               "texto": "Hasta el 30 de noviembre (pon tus condiciones)", "cta": "Resérvalo"},
    "cierre": {"titulo": "¿Te sirvió?", "texto": "Guárdalo para tenerlo a mano.", "cta": "Escríbenos",
               "guardalo": "Guárdalo y compártelo"},
}


def _componer(L, tipo, t):
    """Las capas de contenido de una lámina de tipo `tipo` con los textos `t`."""
    fam, colores = L.fam, L.colores
    capas, sobre = _fondo_y_adorno(L, tipo)
    x0, y0, w, h = _caja_util(L)
    tinta = _ref_legible(sobre)
    acento_g = _acento_sobre(fam, sobre, colores, True)
    acento_p = _acento_sobre(fam, sobre, colores, False)
    brillo = fam["deco"] == "brillo"

    def fila(fy, fh):
        return y0 + fy * h, fh * h

    if L.horiz:
        if tipo not in TIPOS_HORIZONTAL:
            raise ErrorGraficas(f"una lámina «{NOMBRES_TIPO[tipo]}» no cabe bien en horizontal: elige un tamaño vertical o cuadrado")
        izq, der = w * 0.34, w * 0.6
        if tipo == "punto":
            capas.append(L.texto(t.get("numero", ""), x0, y0, izq, h * 0.7, 26, rol="numero", titulo=True, color=acento_g,
                                 mayus=False, cursiva=False, brillo=brillo, valign="centro", nombre="Número grande"))
            capas.append(L.texto(t.get("titulo", ""), x0 + w - der, y0, der, h * 0.5, 8, rol="titulo", titulo=True,
                                 color=tinta, brillo=brillo, valign="abajo"))
            capas.append(L.texto(t.get("texto", ""), x0 + w - der, y0 + h * 0.56, der, h * 0.44, 4.6, rol="texto",
                                 color=tinta, ajusta=True))
        elif tipo == "dato":
            capas.append(L.texto(t.get("cifra", ""), x0, y0, w * 0.48, h, 22, rol="cifra", titulo=True, color=acento_g,
                                 mayus=False, cursiva=False, brillo=brillo, valign="centro", nombre="Cifra"))
            capas.append(L.texto(t.get("texto", ""), x0 + w * 0.52, y0, w * 0.48, h, 5.4, rol="texto", color=tinta,
                                 peso=600, valign="centro", ajusta=True))
        elif tipo == "cita":
            capas.append(L.texto(t.get("cita", ""), x0, y0, w * 0.86, h * 0.72, 6.6, rol="cita", titulo=True,
                                 mayus=False, color=tinta, brillo=brillo, valign="centro"))
            capas.append(L.texto(t.get("autor", ""), x0, y0 + h * 0.78, w * 0.7, h * 0.2, 3.8, rol="autor",
                                 color=acento_p, peso=700, ajusta=True))
        elif tipo == "cierre":
            capas.append(L.texto(t.get("titulo", ""), x0, y0, w * 0.55, h * 0.6, 9, rol="titulo", titulo=True,
                                 color=tinta, brillo=brillo, valign="abajo"))
            capas.append(L.texto(t.get("texto", ""), x0, y0 + h * 0.66, w * 0.55, h * 0.34, 4.4, rol="texto",
                                 color=tinta, ajusta=True))
            capas += _boton(L, t, x0 + w * 0.6, y0 + h * 0.3, w * 0.4, h * 0.22, sobre)
            capas.append(L.texto(t.get("guardalo", ""), x0 + w * 0.6, y0 + h * 0.6, w * 0.4, h * 0.18, 3.2,
                                 rol="guardalo", color=acento_p, peso=600, ajusta=True))
        return capas

    if tipo == "punto":
        y, alto = fila(0, 0.24)
        capas.append(L.texto(t.get("numero", ""), x0, y, w * 0.6, alto, 21, rol="numero", titulo=True, color=acento_g,
                             mayus=False, cursiva=False, brillo=brillo, nombre="Número grande"))
        y, alto = fila(0.28, 0.36)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 8.4, rol="titulo", titulo=True, color=tinta, brillo=brillo))
        y, alto = fila(0.67, 0.33)
        capas.append(L.texto(t.get("texto", ""), x0, y, w * 0.94, alto, 4.4, rol="texto", color=tinta, ajusta=True))
    elif tipo in ("lista", "pasos"):
        y, alto = fila(0, 0.2)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 7.2 if tipo == "lista" else 7, rol="titulo",
                             titulo=True, color=tinta, brillo=brillo))
        items = [t.get(f"v{i}", "") for i in range(1, MAX_VINETAS + 1)]
        items = [x for x in items if x.strip()] or [""]
        n = len(items)
        # se reparten según cuántas haya: ni apretadas ni media lámina vacía
        paso = min(0.76 / n, 0.2 if tipo == "lista" else 0.22)
        arriba = 0.24 + (0.76 - paso * n) / 2 * (0.5 if n < 4 else 0)
        for i, item in enumerate(items):
            y, alto = fila(arriba + i * paso, paso * 0.86)
            if tipo == "lista":
                lado = min(7.5, alto * L.f["H"] / L.f["W"] * 0.7)
                bola = _acento_rol(fam, sobre, colores)
                capas.append(L.forma(x0, y + (alto - L.alto_de(lado)) / 2, lado, L.alto_de(lado), f"kit:{bola}",
                                     "elipse" if fam["radio"] else "rect", nombre=f"Viñeta {i + 1}"))
                capas.append(L.texto(str(i + 1), x0, y + (alto - L.alto_de(lado)) / 2, lado, L.alto_de(lado), 3.2,
                                     rol="deco", peso=800, alin="centro", valign="centro", color=_ref_legible(bola), nombre=f"Número {i + 1}"))
                capas.append(L.texto(item, x0 + lado + 3.5, y, w - lado - 3.5, alto, 4.6, rol=f"v{i + 1}", color=tinta,
                                     peso=600, valign="centro", ajusta=True))
            else:
                ancho_n = 16 if not L.cuad else 14
                capas.append(L.texto(f"{i + 1:02d}", x0, y, ancho_n, alto, 8.5, rol="deco", titulo=True, color=acento_g, mayus=False,
                                     cursiva=False, brillo=brillo, valign="centro", nombre=f"Paso {i + 1}", ajusta=True))
                capas.append(L.forma(x0 + ancho_n + 1, y + alto * 0.12, 0.5, alto * 0.76, f"kit:{_acento_rol(fam, sobre, colores)}",
                                     nombre=f"Línea {i + 1}"))
                capas.append(L.texto(item, x0 + ancho_n + 4, y, w - ancho_n - 4, alto, 4.6, rol=f"v{i + 1}", color=tinta,
                                     peso=600, valign="centro", ajusta=True))
    elif tipo == "dato":
        y, alto = fila(0.04, 0.42)
        capas.append(L.texto(t.get("cifra", ""), x0, y, w, alto, 26, rol="cifra", titulo=True, color=acento_g,
                             mayus=False, cursiva=False, brillo=brillo, alin="centro", valign="abajo", nombre="Cifra"))
        y, alto = fila(0.52, 0.42)
        capas.append(L.texto(t.get("texto", ""), x0 + w * 0.06, y, w * 0.88, alto, 5.2, rol="texto", color=tinta,
                             peso=600, alin="centro", ajusta=True))
    elif tipo == "antes_despues":
        y, alto = fila(0, 0.18)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 6.8, rol="titulo", titulo=True, color=tinta, brillo=brillo))
        hueco = 3
        col = (w - hueco) / 2
        y, alto = fila(0.24, 0.74)
        rol_lleno = _acento_rol(fam, sobre, colores)
        for i, (eti, campo) in enumerate((("etiqueta1", "antes"), ("etiqueta2", "despues"))):
            x = x0 + i * (col + hueco)
            if i:
                capas.append(L.forma(x, y, col, alto, f"kit:{rol_lleno}", radio=fam["radio"], nombre="Columna después"))
                color = _ref_legible(rol_lleno)
            else:
                capas.append(L.forma(x, y, col, alto, None, radio=fam["radio"], nombre="Columna antes",
                                     borde={"anchos": [0.35] * 4, "color": tinta, "alfa": 0.5}))
                color = tinta
            capas.append(L.texto(t.get(eti, ""), x + 3, y + L.alto_de(3), col - 6, L.alto_de(6), 3.4, rol=eti, peso=800,
                                 mayus=True, espaciado=0.08, color=color, ajusta=True))
            capas.append(L.texto(t.get(campo, ""), x + 3, y + L.alto_de(11), col - 6, alto - L.alto_de(14), 4.4,
                                 rol=campo, peso=600, color=color, ajusta=True))
    elif tipo == "cita":
        y, alto = fila(0, 0.18)
        capas.append(L.texto("“", x0, y, 22, alto, 18, rol="deco", titulo=True, color=acento_g, mayus=False, cursiva=False,
                             nombre="Comillas", ajusta=False, interlineado=1))
        y, alto = fila(0.28, 0.5)
        capas.append(L.texto(t.get("cita", ""), x0, y, w, alto, 6.8, rol="cita", titulo=True, mayus=False, color=tinta,
                             brillo=brillo))
        y, alto = fila(0.82, 0.14)
        capas.append(L.texto(t.get("autor", ""), x0, y, w * 0.9, alto, 3.8, rol="autor", color=acento_p, peso=700, ajusta=True))
    elif tipo == "mito":
        rol_lleno = _acento_rol(fam, sobre, colores)
        for i, (eti, campo, cual) in enumerate((("etiqueta1", "mito", "cruz"), ("etiqueta2", "realidad", "check"))):
            y, alto = fila(0 if not i else 0.53, 0.47)
            if i:
                capas.append(L.forma(x0, y, w, alto, f"kit:{rol_lleno}", radio=fam["radio"], nombre="Caja realidad"))
                color = _ref_legible(rol_lleno)
            else:
                capas.append(L.forma(x0, y, w, alto, None, radio=fam["radio"], nombre="Caja mito",
                                     borde={"anchos": [0.35] * 4, "color": tinta, "alfa": 0.5}))
                color = tinta
            lado = 7 if not L.cuad else 6
            capas.append(_simbolo(L, cual, x0 + 4, y + L.alto_de(3.5), lado, color, nombre="Cruz" if not i else "Check"))
            capas.append(L.texto(t.get(eti, ""), x0 + 4 + lado + 3, y + L.alto_de(3.5), w - lado - 11, L.alto_de(lado), 4,
                                 rol=eti, peso=800, mayus=True, espaciado=0.08, color=color, valign="centro", ajusta=True))
            arriba = L.alto_de(3.5 + lado + 3)
            capas.append(L.texto(t.get(campo, ""), x0 + 4, y + arriba, w - 8, alto - arriba - L.alto_de(3), 5.4 if i else 4.8,
                                 rol=campo, titulo=bool(i), mayus=False, cursiva=False, peso=None if i else 600,
                                 color=color, ajusta=True))
    elif tipo == "pregunta":
        y, alto = fila(0.04, 0.36)
        signo = L.texto("?", x0, y, w * 0.5, alto, 20, rol="deco", titulo=True, color=acento_g, mayus=False,
                        cursiva=False, brillo=brillo, nombre="Signo de pregunta", ajusta=False, interlineado=1)
        # que el signo quepa entero en su caja: ni sube hasta la marca ni baja hasta el titular
        signo["tam"] = round(min(40, 0.7 * alto * L.f["H"] / min(L.f["W"], L.f["H"])), 2)
        capas.append(signo)
        y, alto = fila(0.44, 0.38)
        capas.append(L.texto(t.get("pregunta", ""), x0, y, w, alto, 8, rol="pregunta", titulo=True, color=tinta, brillo=brillo))
        y, alto = fila(0.86, 0.12)
        lado = 9
        capas.append(L.texto(t.get("texto", ""), x0, y, w - lado - 3, alto, 4.2, rol="texto", color=acento_p, peso=700,
                             valign="centro", ajusta=True))
        capas.append(_simbolo(L, "flecha", x0 + w - lado, y + (alto - L.alto_de(lado * 0.6)) / 2, lado, acento_p,
                              alto=L.alto_de(lado * 0.6), nombre="Flecha"))
    elif tipo in ("ranking", "checklist"):
        y, alto = fila(0, 0.2)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 7, rol="titulo", titulo=True, color=tinta, brillo=brillo))
        items = [x for x in (t.get(f"v{i}", "") for i in range(1, MAX_VINETAS + 1)) if x.strip()] or [""]
        n = len(items)
        paso = min(0.76 / n, 0.19)
        arriba = 0.24
        for i, item in enumerate(items):
            y, alto = fila(arriba + i * paso, paso * 0.86)
            if tipo == "ranking":
                ancho_n = 18 if not L.cuad else 15
                if i == 0:
                    capas.append(L.forma(x0 - 1.5, y, w + 3, alto, f"kit:{_acento_rol(fam, sobre, colores)}", alfa=0.14,
                                         radio=fam["radio"], nombre="Fondo del primero"))
                capas.append(L.texto(f"#{i + 1}", x0, y, ancho_n, alto, 9.5 if n <= 3 else 8, rol="deco", titulo=True,
                                     color=acento_g, mayus=False, cursiva=False, brillo=brillo, valign="centro",
                                     nombre=f"Puesto {i + 1}", ajusta=True))
                capas.append(L.texto(item, x0 + ancho_n + 3, y, w - ancho_n - 4, alto, 5 if n <= 3 else 4.4, rol=f"v{i + 1}",
                                     color=tinta, peso=700, valign="centro", ajusta=True))
            else:
                lado = min(7, alto * L.f["H"] / L.f["W"] * 0.62)
                cy = y + (alto - L.alto_de(lado)) / 2
                capas.append(L.forma(x0, cy, lado, L.alto_de(lado), None, radio=1 if fam["radio"] else 0, nombre=f"Casilla {i + 1}",
                                     borde={"anchos": [0.45] * 4, "color": tinta, "alfa": 1}))
                capas.append(_simbolo(L, "check", x0 + lado * 0.15, cy + L.alto_de(lado * 0.1), lado * 0.85,
                                      acento_p, nombre=f"Check {i + 1}"))
                capas.append(L.texto(item, x0 + lado + 3.5, y, w - lado - 3.5, alto, 4.6, rol=f"v{i + 1}", color=tinta,
                                     peso=600, valign="centro", ajusta=True))
    elif tipo == "comparativa":
        y, alto = fila(0, 0.16)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 6.8, rol="titulo", titulo=True, color=tinta, brillo=brillo))
        # «NOSOTROS» tiene que caber sin bajar de la letra mínima, también en 1:1 (sin espaciar),
        # y a la izquierda, sitio para 5 ventajas largas
        cols = ((x0 + w * 0.555, "etiqueta1", "check"), (x0 + w * 0.78, "etiqueta2", "cruz"))
        ancho_c = w * 0.22
        items = [x for x in (t.get(f"v{i}", "") for i in range(1, MAX_VINETAS + 1)) if x.strip()] or [""]
        n = len(items)
        paso = min(0.69 / n, 0.15)
        y_tabla, alto_tabla = fila(0.19, 0.1 + paso * n + 0.01)
        rol_lleno = _acento_rol(fam, sobre, colores)
        capas.append(L.forma(cols[0][0], y_tabla, ancho_c, alto_tabla, f"kit:{rol_lleno}", alfa=0.16, radio=fam["radio"],
                             nombre="Columna destacada"))
        y, alto = fila(0.2, 0.08)
        for cx, eti, _cual in cols:
            capas.append(L.texto(t.get(eti, ""), cx, y, ancho_c, alto, 3.6, rol=eti, peso=800, mayus=False, espaciado=0,
                                 alin="centro", valign="centro", color=tinta, ajusta=True))
        for i, item in enumerate(items):
            y, alto = fila(0.3 + i * paso, paso * 0.9)
            capas.append(L.texto(item, x0, y, w * 0.53, alto, 4.4, rol=f"v{i + 1}", color=tinta, peso=600, valign="centro",
                                 ajusta=True))
            lado = min(5.5, alto * L.f["H"] / L.f["W"] * 0.6)
            for k, (cx, _eti, cual) in enumerate(cols):
                capas.append(_simbolo(L, cual, cx + (ancho_c - lado) / 2, y + (alto - L.alto_de(lado)) / 2, lado,
                                      acento_p if not k else tinta, alfa=1 if not k else 0.6,
                                      nombre=f"{'Sí' if not k else 'No'} {i + 1}"))
            if i < n - 1:
                capas.append(L.forma(x0, y + alto + (paso * 0.1 * h) / 2, w, 0.15 if not L.horiz else 0.3, tinta, alfa=0.2,
                                     nombre=f"Raya {i + 1}"))
    elif tipo == "precio":
        y, alto = fila(0, 0.2)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 6.6, rol="titulo", titulo=True, color=tinta, brillo=brillo))
        y, alto = fila(0.24, 0.13)
        antes = L.texto(t.get("precio_antes", ""), x0, y, w * 0.6, alto, 7, rol="precio_antes", color=tinta, peso=600,
                        valign="abajo", ajusta=True, nombre="Precio de antes (tachado)")
        antes["tachado"] = True
        capas.append(antes)
        y, alto = fila(0.37, 0.28)
        # la letra baja antes que partir el precio en dos líneas (árbitro del 25-11: «S/ 1 299,90» en TikTok):
        # la caja tiene el alto de UNA línea, así «ajusta» la achica hasta que quepa a lo ancho
        # y la letra de partida, según lo largo que es el precio («ajusta» solo baja hasta el 60 %)
        lado = min(L.f["W"], L.f["H"]) / 100
        letras = max(len(t.get("precio", "").strip()), 1)
        tam = max(LETRA_MINIMA, min(L.tam(22), (w * L.f["W"] / 100) / (letras * 0.62) / lado))
        una_linea = tam * lado / L.f["H"] * 100 * 1.18
        alto_precio = min(alto, una_linea)
        precio = L.texto(t.get("precio", ""), x0, y + (alto - alto_precio) / 2, w, alto_precio, 22, rol="precio",
                         titulo=True, color=acento_g, mayus=False, cursiva=False, brillo=brillo, valign="centro",
                         nombre="Precio", ajusta=True, interlineado=1.05)
        precio["tam"] = round(tam, 2)
        capas.append(precio)
        y, alto = fila(0.67, 0.13)
        capas.append(L.texto(t.get("texto", ""), x0, y, w * 0.94, alto, 4, rol="texto", color=tinta, ajusta=True))
        # el botón, ancho y bajo: su texto cabe en UNA línea (la letra baja antes que partirse)
        y, alto = fila(0.83, 0.16)
        capas += _boton(L, t, x0, y, w * 0.92, alto, sobre)
    elif tipo == "cierre":
        y, alto = fila(0.02, 0.36)
        capas.append(L.texto(t.get("titulo", ""), x0, y, w, alto, 9.5, rol="titulo", titulo=True, color=tinta, brillo=brillo))
        y, alto = fila(0.42, 0.2)
        capas.append(L.texto(t.get("texto", ""), x0, y, w * 0.94, alto, 4.4, rol="texto", color=tinta, ajusta=True))
        y, alto = fila(0.66, 0.14)
        capas += _boton(L, t, x0, y, w * 0.72, alto, sobre)
        y, alto = fila(0.86, 0.12)
        capas.append(L.texto(t.get("guardalo", ""), x0, y, w, alto, 3.2, rol="guardalo", color=acento_p, peso=600, ajusta=True))
    return capas


def _acento_rol(fam, sobre, colores):
    """El rol de un relleno de acento que se distinga de su fondo."""
    return _rol_visible(fam, sobre, colores)


def _boton(L, t, x, y, w, h, sobre):
    """La llamada a la acción con la forma de botón de la familia."""
    fam, colores = L.fam, L.colores
    estilo = fam["boton"]
    if estilo in ("relleno", "oscuro"):
        rol = "oscuro" if estilo == "oscuro" and sobre != "oscuro" else _acento_rol(fam, sobre, colores)
        return [L.texto(t.get("cta", ""), x, y, w, h, 4.4, rol="cta", peso=800, color=_ref_legible(rol),
                        fondo={"color": f"kit:{rol}", "alfa": 1}, relleno=[2.2, 4, 2.2, 4],
                        radio=fam["radio"] * 2 if fam["radio"] else 0, valign="centro", ajusta=True, nombre="Botón")]
    if estilo == "contorno":
        color = _acento_sobre(fam, sobre, colores, False)
        return [L.texto(t.get("cta", ""), x, y, w, h, 4.4, rol="cta", peso=800, color=color,
                        borde={"anchos": [0.4] * 4, "color": color, "alfa": 1}, relleno=[2.2, 4, 2.2, 4],
                        radio=fam["radio"] * 2, valign="centro", ajusta=True, nombre="Botón")]
    color = _acento_sobre(fam, sobre, colores, False)
    return [L.texto(t.get("cta", ""), x, y, w, h * 0.8, 4.6, rol="cta", peso=800, color=color, valign="centro",
                    ajusta=True, nombre="Botón"),
            L.forma(x, y + h * 0.82, min(w, 30), 0.3, color, nombre="Subrayado del botón")]


#: Los símbolos, DIBUJADOS (no letras: ✓, ✗ y → no están en todas las
#: tipografías y salían con la del sistema, distinta en el servidor y en Windows).
#: Puntos en % de su caja.
SIMBOLOS = {
    "check": [[6, 52], [20, 38], [40, 58], [80, 16], [94, 30], [40, 86]],
    "cruz": [[20, 6], [50, 36], [80, 6], [94, 20], [64, 50], [94, 80], [80, 94], [50, 64], [20, 94], [6, 80], [36, 50], [6, 20]],
    "flecha": [[0, 38], [58, 38], [58, 10], [100, 50], [58, 90], [58, 62], [0, 62]],
}


def _simbolo(L, cual, x, y, lado, color, alfa=1.0, alto=None, nombre=""):
    """Un ✓, una ✗ o una →, como forma del color `color` (una referencia de color)."""
    return L.forma(x, y, lado, L.alto_de(lado) if alto is None else alto, color, "poligono", alfa=alfa,
                   puntos=[list(p) for p in SIMBOLOS[cual]], nombre=nombre or cual.capitalize())


# ====================================================================== montar

def _textos_de(lamina):
    """Los textos de una lámina por su papel (para volver a montarla)."""
    salida = {}
    for c in lamina.get("capas") or []:
        rol = {"apoyo": "texto"}.get(c.get("rol"), c.get("rol"))     # de una portada: su texto de apoyo
        if c.get("tipo") == "texto" and rol in ROLES and str(c.get("txt") or "").strip():
            salida.setdefault(rol, c["txt"])
    return salida


def lamina(n, tipo, formato_id, colores, textos=None, marca="", previa=None):
    """Una lámina de tipo `tipo` de la familia `n` (no la portada: esa es la
    plantilla y la monta `graficas_capas.montar`). Con `previa` (la lámina que
    había), sus textos van a su sitio y lo que no es de la familia —lo añadido
    a mano, las copias «en todas»— se queda encima tal cual."""
    fam = familia(n)
    if tipo not in TIPOS or tipo == "portada":
        raise ErrorGraficas("ese tipo de lámina no existe")
    L = _Lienzo(fam, formato_id, colores, marca)
    previos = _textos_de(previa) if previa else {}
    t = dict(MUESTRA[tipo])
    textos = textos if isinstance(textos, dict) else {}
    t.update({k: v for k, v in textos.items() if k in ROLES and isinstance(v, str)})
    t.update(previos)
    if tipo == "cierre" and previos:
        t["guardalo"] = previos.get("guardalo", t["guardalo"])
    if previa:
        for c in previa.get("capas") or []:
            L.ids.add(c.get("id"))
    capas = _componer(L, tipo, t)
    sueltas = []
    if previa:
        # lo de la familia (campos, fondo, adornos) y lo de una plantilla (si era
        # la portada) se rehace; lo añadido a mano y lo «en todas» se queda
        sueltas = [c for c in previa.get("capas") or []
                   if c.get("rol") not in ROLES and c.get("rol") not in C._ROLES_DE_PLANTILLA]
        # las «en todas» de un carrusel toman el estilo de la familia nueva
        sueltas = [_restilar_en_todas(L, c) if c.get("rol") in ROLES_EN_TODAS else c for c in sueltas]
    salida = {"tipo": tipo, "familia": n, "capas": capas + sueltas}
    for k in ("id", "alt"):
        if previa and previa.get(k):
            salida[k] = previa[k]
    if len(salida["capas"]) > C.MAX_CAPAS:
        raise ErrorGraficas(f"con este tipo serían {len(salida['capas'])} capas y caben {C.MAX_CAPAS}")
    return salida


def _restilar_en_todas(L, capa):
    """Una copia «en todas» (marca, número, «Desliza»): con la letra, el color
    y el sitio de la familia; conserva su enlace, su texto, su «ocultar aquí» y
    dónde no sale."""
    modelo = next(c for c in en_todas(L) if c["rol"] == capa["rol"])
    nueva = dict(modelo, id=capa["id"], txt=capa.get("txt", modelo["txt"]), enlace=capa.get("enlace"),
                 oculto=capa.get("oculto", False), nombre=capa.get("nombre") or modelo["nombre"])
    for k in ("salvo", "solo_horizontal"):
        if k in capa:
            nueva[k] = capa[k]
        else:
            nueva.pop(k, None)
    if not nueva.get("enlace"):
        nueva.pop("enlace", None)
    return nueva


def montar_lamina(pincel, doc, indice, n, tipo, kit=None, logo=None, logo_oscuro=None, textos=None, marca=""):
    """«Volver a montar» una lámina de un carrusel con la familia `n` y el tipo
    `tipo` (la portada, con su plantilla). -> el documento entero, limpio."""
    textos = textos if isinstance(textos, dict) else {}
    doc = C.limpiar_doc(doc)
    if type(indice) is not int or not 0 <= indice < len(doc["laminas"]):
        raise ErrorGraficas("esa lámina no está")
    familia(n)
    previa = doc["laminas"][indice]
    if tipo == "portada":
        # lo que la plantilla nueva llama de otra manera: el titular es la cita
        # de la Testimonio (9) y al revés; los pasos de la 12, los titulares de
        # las láminas que siguen (árbitro del 24-11: sin esto, de la 1 a la 9 la
        # portada se quedaba vacía)
        faltan = _textos_que_faltan(doc, indice, n)
        # un campo oculto de antes toma el texto que se ve con otro nombre
        # (cambiaste la cita en la 9: al volver, el titular es la cita nueva)
        doc["laminas"][indice] = dict(previa, capas=[
            dict(c, txt=faltan[c["rol"]]) if c.get("oculto") and c["tipo"] == "texto" and c.get("rol") in faltan else c
            for c in previa["capas"]])
        textos = dict(faltan, **textos)
        nuevo = C.montar(pincel, n, doc["formato"], doc, textos, kit, logo, logo_oscuro, indice,
                         ocultar_sin_sitio=True)
        lam = nuevo["laminas"][indice]
        lam["tipo"], lam["familia"] = "portada", n
        if len(nuevo["laminas"]) > 1:
            lam["capas"] = [_restilar_en_todas(_Lienzo(familia(n), doc["formato"], G.colores_finales(kit, doc), marca), c)
                            if c.get("rol") in ROLES_EN_TODAS else c for c in lam["capas"]]
        return C.limpiar_doc(nuevo)
    colores = G.colores_finales(kit, doc)
    doc["laminas"][indice] = lamina(n, tipo, doc["formato"], colores, textos, marca, previa)
    _ids_unicos(doc, indice)
    return C.limpiar_doc(doc)


def _textos_que_faltan(doc, indice, n):
    """Los campos de la portada de la familia `n` sacados de los que ya hay con
    otro nombre (C.montar usa antes los que ya están con su nombre)."""
    hay = {}
    for oculto in (False, True):            # lo que se ve manda; si no, lo oculto
        for c in doc["laminas"][indice]["capas"]:
            if c["tipo"] == "texto" and bool(c.get("oculto")) == oculto and c["rol"] in G.CAMPOS and c["txt"].strip():
                hay.setdefault(c["rol"], c["txt"])
    visibles = {c["rol"] for c in doc["laminas"][indice]["capas"]
                if c["tipo"] == "texto" and not c.get("oculto") and c["txt"].strip()}
    salida = {}
    pares = (("titulo", "cita"), ("apoyo", "autor")) if n == 9 else (("cita", "titulo"), ("autor", "apoyo"))
    for de, a in pares:
        # solo si el texto de origen se ve, o si el de destino no existe
        if de in hay and (de in visibles or a not in hay):
            salida[a] = hay[de]
    if n == 12:
        siguientes = []
        for i, lam in enumerate(doc["laminas"]):
            if i == indice or lam.get("tipo") not in ("punto", "lista", "pasos", "dato"):
                continue
            t = next((c["txt"] for c in lam["capas"] if c["tipo"] == "texto" and not c.get("oculto")
                      and c["rol"] in ("titulo", "cifra") and c["txt"].strip()), "")
            if t:
                siguientes.append(" ".join(t.split())[:50])
        for k, v in enumerate(siguientes[:3], 1):
            salida[f"i{k}"] = v
    return salida


def montar_todas(pincel, doc, n, kit=None, logo=None, logo_oscuro=None, marca=""):
    """«Volver a montar a todas»: cada lámina con familia (o tipo) vuelve a
    montarse con la familia `n`; las «En blanco» se quedan como están."""
    doc = C.limpiar_doc(doc)
    familia(n)
    for i, lam in enumerate(doc["laminas"]):
        tipo = lam.get("tipo")
        if tipo not in TIPOS:
            continue
        doc = montar_lamina(pincel, doc, i, n, tipo, kit, logo, logo_oscuro, None, marca)
    return doc


#: El tamaño de las historias («Hacer también las historias»).
FORMATO_HISTORIAS = "h916"


def historias(pincel, doc, kit=None, logo=None, logo_oscuro=None, marca=""):
    """«Hacer también las historias» (graficas-3c-extras, B3): el mismo
    carrusel en 9:16, como pieza aparte (la pantalla la abre sin guardar).
    Cada lámina con familia se vuelve a montar con su familia y su tipo, así
    cada texto va a su sitio y lo que tapa la red de las historias queda
    libre; lo añadido a mano conserva su sitio en %, y lo redondo, los logos
    y los QR conservan su forma (un QR estirado no se lee). -> el documento."""
    doc = C.limpiar_doc(doc)
    viejo, nuevo = G.formato(doc["formato"]), G.formato(FORMATO_HISTORIAS)
    if viejo["H"] / viejo["W"] > 1.7:
        raise ErrorGraficas("este carrusel ya es vertical 9:16: ya vale para historias")
    for lam in doc["laminas"]:
        for c in lam["capas"]:
            forma_fija = (c["tipo"] in ("logo", "icono") or (c["tipo"] == "forma" and c.get("figura") == "elipse")
                          or (c["tipo"] == "imagen" and (c.get("radio") == "elipse" or c.get("nombre") == "QR")))
            if not forma_fija or not c["w"]:
                continue
            proporcion = (c["h"] / 100 * viejo["H"]) / (c["w"] / 100 * viejo["W"])
            centro = c["y"] + c["h"] / 2
            c["h"] = round(proporcion * c["w"] / 100 * nuevo["W"] / nuevo["H"] * 100, 6)
            c["y"] = round(centro - c["h"] / 2, 6)
    doc["formato"] = FORMATO_HISTORIAS
    for i, lam in enumerate(doc["laminas"]):
        n, tipo = lam.get("familia"), lam.get("tipo")
        if tipo in TIPOS and n in FAMILIAS:
            # lo que estaba vacío sigue vacío: sin esto, volvía el texto de muestra
            vacios = {c["rol"]: "" for c in lam["capas"]
                      if c["tipo"] == "texto" and c.get("rol") in ROLES and not c["txt"].strip()}
            doc = montar_lamina(pincel, doc, i, n, tipo, kit, logo, logo_oscuro, vacios if tipo != "portada" else None, marca)
    doc["nombre"] = f"{doc.get('nombre') or 'Carrusel'} (historias)"[:80]
    return C.limpiar_doc(doc)


def _ids_unicos(doc, indice):
    otras = {c["id"] for i, lam in enumerate(doc["laminas"]) if i != indice for c in lam["capas"]}
    for c in doc["laminas"][indice]["capas"]:
        while c["id"] in otras:
            c["id"] = "c" + secrets.token_hex(4)
        otras.add(c["id"])


# ====================================================================== partir un texto

_RE_VINETA = re.compile(r"^\s*(?:[-•·*–—]|\d{1,2}[.)])\s+")
_RE_CIFRA = re.compile(r"^[\s\d.,%+\-–xX/:$€S]*\d[\s\d.,%+\-–xX/:$€S]*(?:de\s+\d+)?\s*%?$")


def _es_cifra(linea):
    """«8 de 10», «-20 %», «S/ 190», «3x»: una primera línea que es casi solo una cifra."""
    linea = linea.strip()
    return 0 < len(linea) <= 12 and bool(re.search(r"\d", linea)) and bool(_RE_CIFRA.match(linea))


def partir(texto):
    """Un texto pegado -> [(tipo, textos)], sin IA. Cada párrafo es una lámina:
    el primero, la portada; uno con viñetas, una Lista (más de 5, en varias);
    uno que empieza por una cifra corta, un Dato; el resto, Puntos numerados
    01, 02… Al final va el cierre. Avisos: lo que no cabe (20 láminas) o un
    párrafo de más de 600 letras. -> (laminas, avisos)"""
    parrafos = [p.strip() for p in re.split(r"\n\s*\n", str(texto or "").replace("\r\n", "\n")) if p.strip()]
    avisos = []
    if not parrafos:
        raise ErrorGraficas("pega un texto: cada párrafo será una lámina")
    salida = []
    largos = []                     # las láminas que salen de un párrafo que no cabe
    lineas0 = [x.strip() for x in parrafos[0].split("\n") if x.strip()]
    apoyo0 = " ".join(lineas0[1:])
    if len(lineas0[0]) > C.MAX_TEXTO or len(apoyo0) > C.MAX_TEXTO:
        largos.append(0)
    salida.append(("portada", {"titulo": lineas0[0][:C.MAX_TEXTO], "apoyo": apoyo0[:C.MAX_TEXTO]}))
    numero = 0
    for p in parrafos[1:]:
        lineas = [x.strip() for x in p.split("\n") if x.strip()]
        vinetas = [_RE_VINETA.sub("", x) for x in lineas if _RE_VINETA.match(x)]
        if len(vinetas) >= 2:
            titulo = next((x for x in lineas if not _RE_VINETA.match(x)), "")
            grupos = [vinetas[i:i + MAX_VINETAS] for i in range(0, len(vinetas), MAX_VINETAS)]
            if len(grupos) > 1:
                avisos.append(f"Una lista tiene {len(vinetas)} viñetas: va en {len(grupos)} láminas (caben {MAX_VINETAS} en cada una).")
            if len(titulo) > C.MAX_TEXTO or any(len(v) > C.MAX_TEXTO for v in vinetas):
                largos.append(len(salida))
            for k, grupo in enumerate(grupos):
                t = {"titulo": titulo[:C.MAX_TEXTO - 8] + (" (sigue)" if k else "")}
                t.update({f"v{i + 1}": v[:C.MAX_TEXTO] for i, v in enumerate(grupo)})
                salida.append(("lista", t))
        elif _es_cifra(lineas[0]) and len(lineas) > 1:
            if len(" ".join(lineas[1:])) > C.MAX_TEXTO:
                largos.append(len(salida))
            salida.append(("dato", {"cifra": lineas[0], "texto": " ".join(lineas[1:])[:C.MAX_TEXTO]}))
        else:
            numero += 1
            if len(lineas[0]) > C.MAX_TEXTO or len(" ".join(lineas[1:])) > C.MAX_TEXTO:
                largos.append(len(salida))
            salida.append(("punto", {"numero": f"{numero:02d}", "titulo": lineas[0][:C.MAX_TEXTO],
                                     "texto": " ".join(lineas[1:])[:C.MAX_TEXTO]}))
    salida.append(("cierre", {}))
    if len(salida) > C.MAX_LAMINAS:
        avisos.append(f"Salen {len(salida)} láminas y caben {C.MAX_LAMINAS}: se han quedado fuera las del final (menos el cierre).")
        salida = salida[:C.MAX_LAMINAS - 1] + [salida[-1]]
    cortados = sum(1 for i in largos if i < len(salida) - 1)
    if cortados:
        avisos.append(f"{'Un párrafo no cabe' if cortados == 1 else f'{cortados} párrafos no caben'}: "
                      f"caben {C.MAX_TEXTO} letras por texto y se ha cortado lo que sobra.")
    return salida, avisos


def textos_de_portada(n, t, piezas=(), marca=""):
    """Los campos de la plantilla `n` para la portada: cada plantilla pide los
    suyos (la de Testimonio, una cita; la de Pasos, tres pasos), y ninguno se
    queda vacío ni con un texto de muestra que no se pidió."""
    titulo, apoyo = t.get("titulo", ""), t.get("apoyo", "")
    textos = {"titulo": titulo, "apoyo": apoyo, "marca": marca or "Tu marca", "cta": "Desliza →", "kicker": "",
              "tipo": "", "oferta": "", "oferta_txt": "", "dia": "", "mes": "", "lugar": "", "i1": "", "i2": "", "i3": "",
              "cita": "", "autor": "", "usuario": ""}
    if n == 15:
        # la tarjeta de «Publicación»: el @usuario sale del nombre de la marca
        sin_tildes = "".join(ch for ch in unicodedata.normalize("NFD", (marca or "").lower())
                             if unicodedata.category(ch) != "Mn")
        nombre = re.sub(r"[^a-z0-9_.]", "", sin_tildes.replace(" ", ""))
        textos["usuario"] = f"@{nombre}"[:30] if nombre else "@tumarca"
    if n == 9:
        textos.update(cita=titulo, autor=apoyo or marca or "")
    if n == 12:
        # los pasos de la portada: los titulares de las láminas que vienen
        siguientes = [x[1].get("titulo") or " ".join(filter(None, (x[1].get("cifra"), x[1].get("texto"))))[:50]
                      for x in piezas if x[0] in ("punto", "lista", "pasos", "dato")]
        siguientes = [v for v in siguientes if v]
        for i, v in enumerate(siguientes[:3], 1):
            textos[f"i{i}"] = v
    return textos


def carrusel_desde_texto(pincel, doc, n, texto, modo="sustituir", kit=None, logo=None, logo_oscuro=None, marca=""):
    """«Partir un texto en láminas». `modo`: «sustituir» (todas las láminas
    nuevas) o «anadir» (antes del cierre, si lo hay). -> (doc, avisos)"""
    doc = C.limpiar_doc(doc)
    familia(n)
    if modo not in ("sustituir", "anadir"):
        raise ErrorGraficas("¿sustituir las láminas o añadirlas?")
    piezas, avisos = partir(texto)
    colores = G.colores_finales(kit, doc)
    L = _Lienzo(familia(n), doc["formato"], colores, marca)
    ya_enlazadas = [c for lam in doc["laminas"] for c in lam["capas"] if c.get("enlace")]
    if modo == "anadir":
        # sin portada (ya la hay): el primer párrafo es un punto más, numerado
        # detrás de los que ya hay; el cierre, solo si no hay uno
        hay_cierre = doc["laminas"][-1].get("tipo") == "cierre"
        ya = sum(1 for lam in doc["laminas"] if lam.get("tipo") == "punto")
        convertidas = []
        for tipo, t in piezas:
            if tipo == "portada":
                tipo, t = "punto", {"numero": "", "titulo": t.get("titulo", ""), "texto": t.get("apoyo", "")}
            if tipo == "cierre" and hay_cierre:
                continue
            if tipo == "punto":
                ya += 1
                t = dict(t, numero=f"{ya:02d}")
            convertidas.append((tipo, t))
        piezas = convertidas
        if len(doc["laminas"]) + len(piezas) > C.MAX_LAMINAS:
            sobran = len(doc["laminas"]) + len(piezas) - C.MAX_LAMINAS
            avisos.append(f"Solo caben {C.MAX_LAMINAS} láminas: se han quedado fuera {sobran}.")
            piezas = piezas[:max(0, len(piezas) - sobran)]
    if G.formato(doc["formato"])["W"] / G.formato(doc["formato"])["H"] > 1.3:
        # en horizontal no hay Lista: sus viñetas van en el texto de un Punto
        convertidas = 0
        for i, (tipo, t) in enumerate(piezas):
            if tipo == "lista":
                vinetas = [t[f"v{k}"] for k in range(1, MAX_VINETAS + 1) if t.get(f"v{k}")]
                piezas[i] = ("punto", {"numero": "", "titulo": t.get("titulo", ""),
                                       "texto": "\n".join(f"• {v}" for v in vinetas)[:C.MAX_TEXTO]})
                convertidas += 1
        if convertidas:
            avisos.append("En horizontal las listas van como un punto con sus viñetas en el texto.")
    nuevas = []
    for tipo, t in piezas:
        if tipo == "portada":
            base = C.limpiar_doc({"version": 2, "formato": doc["formato"], "colores": doc["colores"],
                                  "fuente_titulos": doc["fuente_titulos"], "fuente_texto": doc["fuente_texto"],
                                  "laminas": [{"capas": []}]})
            textos = textos_de_portada(n, t, piezas, marca)
            m = C.montar(pincel, n, doc["formato"], base, textos, kit, logo, logo_oscuro, 0)
            lam = dict(m["laminas"][0], tipo="portada", familia=n)
            apoyo = (t.get("apoyo") or "").strip()
            if apoyo and n != 9 and not any(c.get("rol") == "apoyo" for c in lam["capas"]):
                avisos.append(f"La portada de la familia {n} no lleva texto de apoyo: «{apoyo[:60]}» no sale. "
                              "Elige otra familia o ponlo en la lámina 2.")
        else:
            lam = lamina(n, tipo, doc["formato"], colores, t, marca)
        nuevas.append(lam)
    # lo «en todas»: el de antes (si se añade) o uno nuevo de la familia
    if modo == "anadir" and ya_enlazadas:
        grupos = {}
        for c in ya_enlazadas:
            grupos.setdefault(c["enlace"], c)
        for lam in nuevas:
            lam["capas"] += [dict(c, id="c" + secrets.token_hex(4), oculto=False) for c in grupos.values()]
        hay_cierre = doc["laminas"][-1].get("tipo") == "cierre"
        donde = len(doc["laminas"]) - (1 if hay_cierre else 0)
        doc["laminas"][donde:donde] = nuevas
    else:
        comunes = en_todas(L)
        for lam in nuevas:
            lam["capas"] += [dict(c, id="c" + secrets.token_hex(4)) for c in comunes]
        doc["laminas"] = nuevas if modo == "sustituir" else doc["laminas"] + nuevas
    for i in range(len(doc["laminas"])):
        _ids_unicos(doc, i)
    return C.limpiar_doc(doc), avisos


def nueva_lamina(pincel, doc, donde, n, tipo, kit=None, logo=None, logo_oscuro=None, marca=""):
    """Una lámina nueva de tipo `tipo` en la posición `donde`, con la familia
    `n` y una copia de cada grupo «en todas» (de la primera lámina que lo
    tenga). -> el documento entero."""
    doc = C.limpiar_doc(doc)
    if len(doc["laminas"]) >= C.MAX_LAMINAS:
        raise ErrorGraficas(f"un carrusel tiene como mucho {C.MAX_LAMINAS} láminas")
    if type(donde) is not int or not 0 <= donde <= len(doc["laminas"]):
        raise ErrorGraficas("ahí no se puede poner una lámina")
    familia(n)
    if tipo == "portada":
        base = C.limpiar_doc({"version": 2, "formato": doc["formato"], "colores": doc["colores"],
                              "fuente_titulos": doc["fuente_titulos"], "fuente_texto": doc["fuente_texto"],
                              "laminas": [{"capas": []}]})
        m = C.montar(pincel, n, doc["formato"], base, textos_de_portada(n, {"titulo": "Tu gancho aquí"}, (), marca),
                     kit, logo, logo_oscuro, 0)
        lam = dict(m["laminas"][0], tipo="portada", familia=n)
    else:
        lam = lamina(n, tipo, doc["formato"], G.colores_finales(kit, doc), None, marca)
    grupos = {}
    for otra in doc["laminas"]:
        for c in otra["capas"]:
            if c.get("enlace") and c["enlace"] not in grupos:
                grupos[c["enlace"]] = c
    lam["capas"] += [dict(c, id="c" + secrets.token_hex(4), oculto=False) for c in grupos.values()]
    lam["id"] = "l" + secrets.token_hex(4)
    doc["laminas"].insert(donde, lam)
    _ids_unicos(doc, donde)
    return C.limpiar_doc(doc)


def avisos_del_carrusel(doc):
    """La nota del carrusel, sin IA (A3, A4, A6): -> [{nivel, texto}] con
    nivel «bien», «aviso» o «mal». Lo que se mira:
    - la portada: 10 palabras o menos en su titular;
    - la segunda lámina se entiende sola (Instagram la vuelve a enseñar a
      quien no deslizó): tiene titular y no empieza por «y», «además»…;
    - una idea por lámina (un titular cada una, y no muy largo);
    - el número n/total en las láminas;
    - el cierre con UNA sola petición;
    - el texto alternativo de cada lámina;
    - los textos de muestra que siguen igual;
    - cuántas láminas: solo un aviso suave fuera de 7–10 (nunca rojo).
    Lo que tapa la red, el contraste y la cuadrícula 3:4 los mide la vista."""
    doc = C.limpiar_doc(doc)
    L = doc["laminas"]
    salida = []

    def nota(nivel, texto):
        salida.append({"nivel": nivel, "texto": texto})

    def titular(lam):
        for c in lam["capas"]:
            if c["tipo"] == "texto" and not c.get("oculto") and c["rol"] in ("titulo", "cita", "cifra") and c["txt"].strip():
                return c["txt"].strip()
        return ""
    if len(L) < 2:
        return [{"nivel": "aviso", "texto": "Es una sola lámina: la nota es para carruseles."}]
    # lo oculto que no se ve en ninguna lámina (los pasos de la 12 son los
    # titulares de las siguientes: esos no cuentan), cada texto una vez
    a_la_vista = {" ".join(c["txt"].split()) for lam in L for c in lam["capas"]
                  if c["tipo"] == "texto" and not c.get("oculto")}
    ocultos = sorted({" ".join(c["txt"].split()) for c in L[0]["capas"]
                      if c["tipo"] == "texto" and c.get("oculto") and c["rol"] in G.CAMPOS and c["txt"].strip()}
                     - a_la_vista)
    if ocultos:
        nota("aviso", f"La portada tiene {len(ocultos)} texto(s) oculto(s) que esta familia no usa "
                      f"(«{ocultos[0][:40]}»…): el ojo de la lista de capas los enseña.")
    portada = titular(L[0])
    palabras = len(portada.split())
    if not portada:
        nota("mal", "La portada no tiene titular: es el gancho, lo primero que se ve.")
    elif palabras > 10:
        nota("aviso", f"El titular de la portada tiene {palabras} palabras: con 10 o menos se lee de un vistazo.")
    else:
        nota("bien", f"Portada corta ({palabras} palabras).")
    segunda = titular(L[1])
    if not segunda:
        nota("aviso", "La lámina 2 no tiene titular: a quien no deslizó, Instagram le puede enseñar la 2 como si fuera la portada.")
    elif re.match(r"^(y|además|también|pero|entonces|por eso)\b", segunda, re.I):
        nota("aviso", f"La lámina 2 empieza por «{segunda.split()[0]}»: que se entienda sola, puede salir como portada.")
    else:
        nota("bien", "La lámina 2 se entiende sola (segunda portada).")
    largos = [i + 1 for i, lam in enumerate(L[1:-1], 1) if len(titular(lam).split()) > 14]
    if largos:
        nota("aviso", f"Mucho texto en el titular de la lámina {', '.join(map(str, largos))}: una idea por lámina.")
    con_numero = any("{n}" in c.get("txt", "") for lam in L for c in lam["capas"] if c["tipo"] == "texto")
    nota("bien" if con_numero else "aviso", "Cada lámina lleva su número (n/total)." if con_numero
         else "Sin número de lámina: ayuda a saber cuánto falta (pon {n}/{total} en todas).")
    cierre = L[-1]
    llamadas = [c for c in cierre["capas"] if c["tipo"] == "texto" and c["rol"] == "cta" and c["txt"].strip()]
    if cierre.get("tipo") != "cierre" and not llamadas:
        nota("aviso", "La última lámina no pide nada: termina con UNA petición (guardar, enviar o comentar).")
    elif len(llamadas) > 1:
        nota("aviso", "El cierre pide varias cosas a la vez: mejor UNA sola (guardar, enviar o comentar).")
    else:
        nota("bien", "El cierre pide una sola cosa.")
    sin_alt = [i + 1 for i, lam in enumerate(L) if not lam.get("alt")]
    if sin_alt:
        nota("aviso", f"Sin texto alternativo: lámina {', '.join(map(str, sin_alt[:8]))}{'…' if len(sin_alt) > 8 else ''}. "
                      "Si no lo escribes, sale de sus textos.")
    else:
        nota("bien", "Todas las láminas tienen texto alternativo.")
    # el número, las etiquetas «Antes»/«Después» y «Guárdalo y compártelo» sirven tal cual:
    # «01» de un punto que escribiste no es un texto de muestra (prueba del 24-11)
    sirven = {"numero", "etiqueta1", "etiqueta2", "guardalo"}
    muestras = {v for t in MUESTRA.values() for k, v in t.items() if k not in sirven} | {"Tu gancho aquí", "Tu titular aquí"}
    # «La respuesta, en la siguiente» de una Pregunta también sirve tal cual (graficas-3c-extras)
    muestras.discard(MUESTRA["pregunta"]["texto"])
    con_muestra = sorted({i + 1 for i, lam in enumerate(L) for c in lam["capas"]
                          if c["tipo"] == "texto" and not c.get("oculto") and c["txt"].strip() in muestras})
    if con_muestra:
        nota("mal", f"Siguen textos de muestra en la lámina {', '.join(map(str, con_muestra))}: cámbialos antes de publicar.")
    tachados = sorted({i + 1 for i, lam in enumerate(L) for c in lam["capas"]
                       if c["tipo"] == "texto" and c.get("tachado") and not c.get("oculto") and c["txt"].strip()})
    if tachados:
        nota("aviso", f"Precio tachado en la lámina {', '.join(map(str, tachados))}: el precio de antes tiene que ser real "
                      "(el que cobrabas de verdad). En Perú lo exige el Código de Protección y Defensa del Consumidor.")
    if not 7 <= len(L) <= 10:
        nota("aviso", f"{len(L)} láminas. Hay datos (sin verificar) de que entre 7 y 10 funcionan bien; no es una regla.")
    return salida

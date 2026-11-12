"""Las comprobaciones de Gráficas en capas (rama graficas-2-capas, 11-11-2026).

    python pasos/prueba_graficas_capas.py              # lo de siempre (~2 min)
    python pasos/prueba_graficas_capas.py --completo   # todas las variantes en los 8 tamaños

Lo importante: que cada plantilla convertida en capas sale IGUAL que la pieza
de siempre (14 plantillas × 8 tamaños, y variantes: sin foto, textos largos,
Kit con logo, colores de la pieza y retoques del editor de antes); que la
comparación de verdad caza un cambio (si no, «igual» no probaría nada); que
lo guardado en capas no toca la pieza de siempre; y que nada que llegue de
fuera puede colar código en la página que pinta.

Necesita el navegador (ESTUDIO_EDGE, o microsoft-edge / google-chrome en el
PATH), como `prueba_graficas`. No baja nada ni llama a ninguna IA.
"""
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ["ESTUDIO_SIN_DESCARGAS"] = "1"

import graficas as G  # noqa: E402
import graficas_capas as C  # noqa: E402

CUENTA = {"ok": 0, "mal": 0}
FORMATOS = [f["id"] for f in G.FORMATOS]


def ok(cond, que):
    CUENTA["ok" if cond else "mal"] += 1
    if not cond:
        print(f"  MAL: {que}")
    return cond


def falla(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except G.ErrorGraficas:
        return True
    return False


TEXTOS = {"marca": "Café Alba", "tipo": "Cafetería de especialidad", "kicker": "Nuevo en Barranco",
          "titulo": "Café de altura, tostado esta misma mañana", "apoyo": "Granos de Cajamarca y Junín, molidos al momento.",
          "cta": "Pide el tuyo", "oferta": "-30%", "oferta_txt": "solo este fin de semana", "dia": "24",
          "mes": "Noviembre", "lugar": "Av. Grau 123, Barranco", "i1": "Elige tu grano",
          "i2": "Lo molemos al momento", "i3": "Recógelo caliente",
          "cita": "El mejor café que he probado en Lima, y el trato es de diez.", "autor": "María Quispe"}
LARGOS = dict(TEXTOS, titulo="Café de altura de Cajamarca y Junín, tostado esta misma mañana en nuestro tostador de Barranco",
              cita="El mejor café que he probado en Lima, el trato es de diez y siempre vuelvo con mis amigos los domingos.")
KIT = {"colores": {"principal": "#0F7B6C", "secundario": "#FFC93C", "acento": "#FF5A36", "oscuro": "#10202B",
                   "claro": "#F7F4EE"}, "fuente_titulos": "oswald", "fuente_texto": "inter"}
RETOQUES = {"titulo": {"x": 3, "y": -4, "escala": 1.2, "negrita": True, "color": "#FF0000"},
            "cta": {"fondo": "#00AA00", "subrayado": True}, "marca": {"cursiva": True}, "kicker": {"oculto": True},
            "sello": {"x": -5, "escala": 0.8}}


def foto_de_prueba(carpeta):
    """Una foto con formas (círculos sobre un degradado): si el recorte o el
    encuadre cambiaran un píxel, se notaría."""
    from PIL import Image, ImageDraw
    ruta = os.path.join(carpeta, "img_0123456789abcdef.jpg")
    im = Image.new("RGB", (1600, 1200))
    d = ImageDraw.Draw(im)
    for y in range(1200):
        d.line([(0, y), (1600, y)], fill=(40 + y // 8, 90, 200 - y // 8))
    for i in range(12):
        d.ellipse([i * 130, 300 + (i % 3) * 200, i * 130 + 180, 480 + (i % 3) * 200], fill=(240, 200 - i * 10, 40 + i * 15))
    im.save(ruta, quality=92)
    return ruta


def foto_vertical(carpeta):
    from PIL import Image, ImageDraw
    ruta = os.path.join(carpeta, "img_fedcba9876543210.jpg")
    im = Image.new("RGB", (900, 1600), (30, 120, 90))
    d = ImageDraw.Draw(im)
    for i in range(8):
        d.rectangle([60 + i * 40, 100 + i * 180, 500 + i * 40, 220 + i * 180], fill=(250, 160 - i * 15, 30 + i * 25))
    im.save(ruta, quality=92)
    return ruta


def logos_de_prueba(carpeta):
    from PIL import Image, ImageDraw
    rutas = []
    for nombre, color in (("logo.png", (20, 20, 60, 255)), ("logo_oscuro.png", (250, 250, 250, 255))):
        im = Image.new("RGBA", (600, 160), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([10, 10, 150, 150], fill=color)
        d.rectangle([180, 50, 580, 110], fill=color)
        ruta = os.path.join(carpeta, nombre)
        im.save(ruta)
        rutas.append(ruta)
    return rutas


def capa_texto(**extra):
    base = {"id": "t1", "tipo": "texto", "rol": "titulo", "x": 10, "y": 10, "w": 80, "h": 10, "txt": "Hola",
            "fuente": {"rol": "titulos", "id": "anton"}, "tam": 8, "color": "kit:claro"}
    base.update(extra)
    return base


def doc_de(capas, **extra):
    capas = capas or [capa_texto()]
    base = {"version": 2, "formato": "v45", "laminas": [{"capas": capas}]}
    base.update(extra)
    return base


# ====================================================================== sin navegador

def limpieza_y_seguridad():
    print("lo que llega de fuera se limpia")
    ok(falla(C.limpiar_doc, None), "un documento que no es un objeto se rechaza")
    ok(falla(C.limpiar_doc, doc_de([], version=3)), "otra versión se rechaza")
    ok(falla(C.limpiar_doc, {"version": 2, "laminas": []}), "sin láminas se rechaza")
    ok(falla(C.limpiar_doc, doc_de([], formato="zz")), "un tamaño que no existe se rechaza")
    ok(falla(C.limpiar_doc, {"version": 2, "laminas": [{"capas": []}] * (C.MAX_LAMINAS + 1)}),
       f"más de {C.MAX_LAMINAS} láminas se rechaza")
    ok(falla(C.limpiar_doc, doc_de([capa_texto(id=f"c{i}") for i in range(C.MAX_CAPAS + 1)])),
       f"más de {C.MAX_CAPAS} capas en una lámina se rechaza")
    fotos = [{"id": f"f{i}", "tipo": "imagen", "src": "img_0123456789abcdef.jpg", "w": 10, "h": 10}
             for i in range(C.MAX_FOTOS + 1)]
    ok(falla(C.limpiar_doc, doc_de(fotos)), f"más de {C.MAX_FOTOS} fotos en una lámina se rechaza")
    ok(falla(C.limpiar_doc, doc_de([{"tipo": "video"}])), "un tipo de capa desconocido se rechaza")
    for color in ("red", "#fff", "#FF0000;}body{x", "url(http://x)", "kit:rojo", "tinta:", "var(--a)"):
        ok(falla(C.limpiar_doc, doc_de([capa_texto(color=color)])), f"el color {color!r} se rechaza")
    ok(falla(C.limpiar_doc, doc_de([capa_texto(fondo={"color": "#00000g"})])), "un fondo con color raro se rechaza")
    ok(falla(C.limpiar_doc, doc_de([{"tipo": "forma", "relleno": {"degradado": {"paradas": [
        {"color": "#000000"}, {"color": "blue"}]}}}])), "un degradado con un color raro se rechaza")
    for src in ("../secreto.jpg", "http://x/y.jpg", "img_0123.jpg", "/etc/passwd", "img_0123456789abcdef.jpg\n"):
        ok(falla(C.limpiar_doc, doc_de([{"tipo": "imagen", "src": src}])), f"la foto {src!r} se rechaza")
    raro_f = C.limpiar_doc(doc_de([capa_texto(fuente={"rol": "fija", "id": "../comic"})]))
    ok(raro_f["laminas"][0]["capas"][0]["fuente"]["id"] == "",
       "una tipografía fuera de la lista (o quitada de ella) vuelve a la de su papel, sin romper la pieza")
    logos = [{"id": f"l{i}", "tipo": "logo", "w": 10, "h": 5} for i in range(C.MAX_LOGOS + 1)]
    ok(falla(C.limpiar_doc, doc_de(logos)), f"más de {C.MAX_LOGOS} logos en una lámina se rechaza")
    # visto en la revisión del 11-11: estas formas daban un 500 en vez de un 400
    for nombre, capa in (
            ("paradas como objeto", {"tipo": "forma", "relleno": {"degradado": {"paradas": {"a": 1}}}}),
            ("paradas como número", {"tipo": "forma", "relleno": {"degradado": {"paradas": 7}}}),
            ("puntos como objeto", {"tipo": "forma", "figura": "poligono", "puntos": {"a": 1}}),
            ("fondo_auto como lista", {"tipo": "logo", "fondo_auto": [1]}),
            ("borde con anchos raros", {"tipo": "forma", "borde": {"anchos": [{}, [], None, "x"]}}),
            ("fuente como texto", capa_texto(fuente="anton")),
            ("relleno como lista", {"tipo": "forma", "relleno": [1, 2]}),
            ("encuadre como lista", {"tipo": "imagen", "encuadre": [1]}),
            ("sombra con basura", capa_texto(sombra=[{"x": {}, "color": "#000000"}, 5, "x"]))):
        try:
            C.limpiar_doc(doc_de([capa]))
            ok(True, nombre)
        except G.ErrorGraficas:
            ok(True, nombre)
        except Exception as fallo:                          # noqa: BLE001
            ok(False, f"{nombre}: da {type(fallo).__name__} (sería un 500) en vez de un error claro")
    import random
    azar = random.Random(11)
    basura = [None, 1, -1e308, "x", [], {}, [1, "a"], {"a": None}, True, float("nan"), "#FF0000", "kit:principal"]
    claves = ["tipo", "id", "rol", "x", "y", "w", "h", "giro", "origen", "recorte", "txt", "fuente", "tam", "peso",
              "color", "fondo", "relleno", "borde", "radio", "sombra", "sombra_texto", "src", "encuadre", "variante",
              "fondo_auto", "figura", "puntos", "alin", "valign", "espaciado", "interlineado"]
    raros = 0
    for _ in range(400):
        capa = {k: azar.choice(basura) for k in azar.sample(claves, azar.randint(1, 12))}
        capa["tipo"] = azar.choice(list(C.TIPOS))
        try:
            C.html_capas(doc_de([capa]))
        except G.ErrorGraficas:
            pass
        except Exception as fallo:                          # noqa: BLE001
            raros += 1
            if raros == 1:
                print(f"    p. ej. {capa} -> {type(fallo).__name__}: {fallo}")
    ok(raros == 0, f"400 capas hechas de basura: o se limpian o se rechazan, nunca un fallo raro ({raros} raros)")

    raro = C.limpiar_doc(doc_de([capa_texto(id='"><script>', rol="x y", x=float("nan"), y=float("inf"),
                                            w=1e9, tam=-5, peso="mucho", giro=1e6, opac=7,
                                            txt="a\x00b\x07c" + "x" * 2000, nombre="<b>n</b>" * 20,
                                            alin="justify", valign="lado", espaciado="1;}")]))
    capa = raro["laminas"][0]["capas"][0]
    ok(re.match(r"^[a-z0-9]{1,12}$", capa["id"]), "un id raro se cambia por uno limpio")
    ok(capa["rol"] == "", "un papel con caracteres raros se vacía")
    ok(capa["x"] == 0 and capa["y"] == 0, "NaN e infinito no pasan: se quedan en 0")
    ok(capa["w"] == 400 and capa["tam"] == 0.3 and capa["giro"] == 360 and capa["opac"] == 1,
       "los números se acotan a su rango")
    ok(capa["peso"] == 400, "un grosor que no es un número vuelve al normal")
    ok("\x00" not in capa["txt"] and "\x07" not in capa["txt"] and len(capa["txt"]) == C.MAX_TEXTO,
       "los caracteres de control se quitan y el texto se corta en su máximo")
    ok(len(capa["nombre"]) <= 40 and capa["alin"] == "izq" and capa["valign"] == "arriba" and capa["espaciado"] == 0,
       "nombre acotado; alineación y espaciado raros vuelven al defecto")
    dos = C.limpiar_doc(doc_de([capa_texto(id="a1"), capa_texto(id="a1")]))
    ok(len({c["id"] for c in dos["laminas"][0]["capas"]}) == 2, "dos capas con el mismo id acaban con ids distintos")
    ok(C.limpiar_doc(C.limpiar_doc(raro)) == C.limpiar_doc(raro), "limpiar dos veces da lo mismo")
    ok(C.limpiar_doc(doc_de([], origen={"plantilla": True}))["origen"]["plantilla"] is None,
       "«True» no pasa por un número de plantilla")

    print("la página que pinta no puede salir de sí misma")
    malo = '</div><script>alert(1)</script><img src=x onerror=alert(2)>"\'&'
    capas = [capa_texto(txt=malo, nombre="<script>nombre</script>"),
             {"tipo": "forma", "relleno": {"degradado": {"ang": 45, "paradas": [{"color": "#FF0000", "alfa": 0.5},
                                                                               {"color": "kit:principal"}]}},
              "figura": "poligono", "puntos": [[0, 0], [100, 0], [50, 100]], "w": 50, "h": 50},
             {"tipo": "imagen", "src": "", "w": 30, "h": 30, "radio": "elipse"},
             {"tipo": "logo", "variante": "auto", "w": 20, "h": 5}]
    documento, f, margenes, _ = C.html_capas(doc_de(capas))
    ok("<script" not in documento.lower(), "el texto no puede meter un <script>")
    ok("onerror" not in documento.replace("onerror=alert(2)&gt;", ""), "ni un atributo con código")
    ok("&lt;/div&gt;&lt;script&gt;" in documento, "el texto sale escapado")
    ok("nombre</script>" not in documento and "&lt;script&gt;nombre" not in documento,
       "el nombre de la capa no entra en la página")
    ok(not re.search(r"url\((?!data:)", documento), "nada se carga de fuera (solo data: dentro)")
    ok("<link" not in documento and "@import" not in documento, "ni hojas de estilo de fuera")
    ok(f["W"] == 1080 and len(margenes) == 4, "el documento sabe su tamaño y sus márgenes")
    ok("clip-path:polygon(0% 0%, 100% 0%, 50% 100%)" in documento, "la figura con puntos se pinta con sus puntos")


def colores_del_kit():
    print("los colores siguen al Kit")
    colores = G.colores_finales(KIT, {})
    ok(C.resolver_color("kit:principal", colores) == "#0F7B6C", "kit:principal es el principal del Kit")
    ok(C.resolver_color("#ABCDEF", colores) == "#ABCDEF", "un color fijo se queda como está")
    ok(C.resolver_color("tinta:secundario", colores) == G._tinta_para("#FFC93C", "#10202B", "#F7F4EE"),
       "tinta:secundario es el texto legible sobre el secundario, como en las plantillas")
    a, _f, _m, _ = C.html_capas(doc_de([capa_texto(color="kit:principal")]), KIT)
    otro = dict(KIT, colores=dict(KIT["colores"], principal="#123456"))
    b, _f, _m, _ = C.html_capas(doc_de([capa_texto(color="kit:principal")]), otro)
    ok("#0F7B6C" in a and "#123456" in b, "si el cliente cambia su Kit, la pieza cambia con él")
    c, _f, _m, _ = C.html_capas(doc_de([capa_texto(color="kit:principal")], colores={"principal": "#654321"}), otro)
    ok("#654321" in c, "y el color propio de la pieza manda sobre el del Kit (como antes)")


# ====================================================================== con navegador

def plantillas_iguales(pincel, foto, completo):
    print("las 14 plantillas, convertidas en capas, salen iguales en los 8 tamaños")
    peor = (0, "")
    for fid in FORMATOS:
        for n in range(1, 15):
            pieza = {"plantilla": n, "formato": fid, "textos": TEXTOS, "imagen": os.path.basename(foto)}
            r = C.comparar(pincel, pieza, None, foto)
            ok(r["igual"], f"plantilla {n} en {fid}: dif {r['diferencia']*100:.3f} %, visible "
                           f"{r['visible']*100:.3f} %, líneas {r['lineas']}, textos {r['faltan']}, movidos {r['movidos']}")
            peor = max(peor, (r["visible"], f"{n}/{fid}"))
    print(f"  (la mayor diferencia visible: {peor[0]*100:.3f} % en {peor[1]})")

    print("y con variantes: sin foto, textos largos, Kit con logo, colores de la pieza y retoques")
    variantes = [("sin foto", {"imagen": ""}, None, False), ("textos largos", {"textos": LARGOS}, None, False),
                 ("Kit con logo", {}, KIT, True),
                 ("colores de la pieza", {"colores": {"principal": "#222222", "claro": "#FFEEDD"},
                                          "fuente_titulos": "lora"}, None, False),
                 ("retoques de antes", {"capas": RETOQUES, "encuadre": {"x": 30, "y": 70, "zoom": 2.2}}, None, False)]
    vertical = foto_vertical(os.path.dirname(foto))
    variantes.append(("foto vertical", {"imagen": os.path.basename(vertical),
                                        "encuadre": {"x": 50, "y": 20, "zoom": 1.5}}, None, False))
    logo, logo_oscuro = logos_de_prueba(os.path.dirname(foto))
    for i, (nombre, extra, kit, con_logo) in enumerate(variantes):
        formatos = FORMATOS if completo else [FORMATOS[(i * 3) % len(FORMATOS)], FORMATOS[(i * 3 + 6) % len(FORMATOS)]]
        for fid in formatos:
            for n in range(1, 15):
                pieza = dict({"plantilla": n, "formato": fid, "textos": TEXTOS, "imagen": os.path.basename(foto)}, **extra)
                r = C.comparar(pincel, pieza, kit, (vertical if "fedcba" in pieza["imagen"] else foto) if pieza["imagen"] else None,
                               logo if con_logo else None, logo_oscuro if con_logo else None)
                ok(r["igual"], f"{nombre}, plantilla {n} en {fid}: dif {r['diferencia']*100:.3f} %, visible "
                               f"{r['visible']*100:.3f} %, líneas {r['lineas']}, textos {r['faltan']}, movidos {r['movidos']}")
    # visto el 11-11: el titular movido fuera de su casilla (plantilla 8) la casilla
    # lo corta; sin «recorte», en capas se veía entero
    r = C.comparar(pincel, {"plantilla": 8, "formato": "tt", "textos": TEXTOS, "capas": RETOQUES,
                            "imagen": os.path.basename(foto)}, None, foto)
    ok(r["igual"], f"un texto movido fuera de su casilla sigue recortado por ella (visible {r['visible']*100:.3f} %)")
    ok(any(c.get("recorte") for c in r["doc"]["laminas"][0]["capas"] if c["rol"] == "titulo"),
       "y su capa lleva el recorte de la casilla")
    r = C.comparar(pincel, {"plantilla": 2, "textos": TEXTOS, "capas": RETOQUES, "imagen": ""})
    ocultas = [c for c in r["doc"]["laminas"][0]["capas"] if c["oculto"]]
    ok([c["rol"] for c in ocultas] == ["kicker"], "lo oculto con el editor de antes sigue ahí, como capa oculta")
    ok(ocultas and ocultas[0]["txt"] == TEXTOS["kicker"], "con su texto, para poder volver a enseñarlo")
    # visto en la revisión del 11-11: al ocultar el sello se perdían sus textos, y
    # lo oculto quedaba al final (encima de todo) en vez de en su sitio
    r = C.comparar(pincel, {"plantilla": 7, "textos": TEXTOS, "capas": {"sello": {"oculto": True}},
                            "imagen": os.path.basename(foto)}, None, foto)
    capas = r["doc"]["laminas"][0]["capas"]
    roles = [c["rol"] for c in capas]
    ok(r["igual"], f"con el sello oculto la pieza sale igual (visible {r['visible']*100:.3f} %)")
    ok({"sello", "oferta", "oferta_txt"} <= {c["rol"] for c in capas if c["oculto"]},
       "el sello oculto conserva sus dos textos, ocultos con él")
    ok(roles.index("sello") < roles.index("oferta") < roles.index("oferta_txt") and roles[-1] == "oferta_txt",
       "y en su sitio de siempre (el sello debajo de sus textos)")
    ok(len({c["id"] for c in capas}) == len(capas), "sin ids repetidos")

    print("la pieza convertida sigue los colores del Kit")
    # solo los colores: con otra letra el texto ocupa otro sitio y las cajas de
    # la conversión ya están fijadas (eso lo recoloca «Volver a montar» del editor)
    otro = dict(KIT, colores={"principal": "#8E24AA", "secundario": "#00BFA5", "acento": "#FF6D00",
                              "oscuro": "#1A1A1A", "claro": "#FFFDE7"})
    for n in (1, 7, 10, 13):
        pieza = {"plantilla": n, "textos": TEXTOS, "imagen": os.path.basename(foto)}
        doc = C.convertir(pincel, pieza, KIT)
        antes = G.pintar(pincel, pieza, otro, foto)[0]
        despues = C.pintar(pincel, doc, otro, lambda _n: foto)[0]
        vis = C.diferencia_visible(antes, despues)
        ok(vis <= 0.001, f"plantilla {n}: convertida con un Kit y pintada con otro, sale como la de siempre con "
                         f"el otro (visible {vis*100:.3f} %)")


def la_comparacion_caza(pincel, foto):
    """Si «igual» no detectara un cambio pequeño, no probaría nada."""
    print("la comparación caza un cambio de verdad")
    # visto en la revisión del 11-11: sin un texto corto la diferencia en píxeles
    # no llegaba al tope; ahora se comparan también los textos
    corta = dict(TEXTOS, marca="Alba", autor="Ana")
    for n, fid, rol in ((2, "h169", "marca"), (9, "h169", "autor"), (14, "h169", "marca")):
        def quitar(doc, rol=rol):
            doc["laminas"][0]["capas"] = [c for c in doc["laminas"][0]["capas"] if c["rol"] != rol]
        r = C.comparar(pincel, {"plantilla": n, "formato": fid, "textos": corta, "imagen": ""}, _tocar=quitar)
        ok(not r["igual"] and rol in r["faltan"], f"quitar «{rol}» (un texto corto) en la plantilla {n} se nota")

        def cambiar(doc, rol=rol):
            for c in doc["laminas"][0]["capas"]:
                if c["rol"] == rol:
                    c["txt"] = c["txt"][::-1]
        r = C.comparar(pincel, {"plantilla": n, "formato": fid, "textos": corta, "imagen": ""}, _tocar=cambiar)
        ok(not r["igual"] and rol in r["faltan"], f"cambiar lo que dice «{rol}» en la plantilla {n} se nota")
    pieza = {"plantilla": 2, "textos": TEXTOS, "imagen": os.path.basename(foto)}
    antes, _a, _m = G.pintar(pincel, pieza, None, foto)
    doc = C.convertir(pincel, pieza)

    def pintado(cambio):
        otro = copy.deepcopy(doc)
        cambio(otro["laminas"][0]["capas"])
        return C.pintar(pincel, otro, None, lambda _n: foto)[0]

    def por_rol(rol):
        return lambda capas: next(c for c in capas if c["rol"] == rol)

    def mover(capas):
        por_rol("titulo")(capas)["x"] += 2 / 1080 * 100           # 2 px
    def color(capas):
        por_rol("cta")(capas)["fondo"] = {"color": "#E0C000", "alfa": 1}
    def ocultar(capas):
        por_rol("marca")(capas)["oculto"] = True
    def letra(capas):
        por_rol("titulo")(capas)["tam"] *= 1.02
    def fondo(capas):
        por_rol("deco")(capas)["relleno"]["degradado"]["paradas"][-1]["alfa"] = 0.9
    for nombre, cambio in (("mover el titular 2 px", mover), ("cambiar un poco el color del botón", color),
                           ("ocultar la marca", ocultar), ("la letra del titular un 2 % más grande", letra),
                           ("el degradado un 10 % más claro", fondo)):
        despues = pintado(cambio)
        dif, vis = C.diferencia(antes, despues), C.diferencia_visible(antes, despues)
        ok(vis > 0.001 or dif > 0.02, f"{nombre} se nota (dif {dif*100:.3f} %, visible {vis*100:.3f} %)")


def el_pintado(pincel, foto, carpeta):
    print("pintar capas")
    largo = capa_texto(txt="Un titular larguísimo que no cabe de ninguna manera en una caja tan baja", h=4, w=40,
                       ajusta=True)
    png, avisos, _ = C.pintar(pincel, doc_de([largo]))
    alto = pincel.evaluar("parseFloat(getComputedStyle(document.querySelector('[data-c=t1]')).getPropertyValue('--e'))")
    ok(alto and alto < 1, "un texto que no cabe en su caja baja la letra (como antes)")
    ok(any("reducida" in a or "tapa" in a for a in avisos), "y lo avisa")
    fijo = dict(largo, ajusta=False)
    C.pintar(pincel, doc_de([fijo]))
    sin = pincel.evaluar("getComputedStyle(document.querySelector('[data-c=t1]')).getPropertyValue('--e')")
    ok(not sin, "uno que no «ajusta» deja su letra como está")
    png2, _a, _m = C.pintar(pincel, doc_de([capa_texto(oculto=True), capa_texto(id="t2", txt="   ")]))
    ok(pincel.evaluar("document.querySelectorAll('[data-c]').length") == 0, "lo oculto y lo vacío no se pintan")
    from PIL import Image
    im = Image.open(io.BytesIO(png2))
    ok(im.size == (1080, 1350), "la lámina sale a su medida exacta")
    logo, logo_oscuro = logos_de_prueba(carpeta)
    capa_logo = {"id": "l1", "tipo": "logo", "x": 10, "y": 10, "w": 30, "h": 8, "fondo_auto": "d"}
    for variante, esperado in (("auto", logo_oscuro), ("normal", logo), ("oscuro", logo_oscuro)):
        documento, *_ = C.html_capas(doc_de([dict(capa_logo, variante=variante)]), KIT, None, logo, logo_oscuro)
        ok(G._data_uri(esperado) in documento, f"logo «{variante}»: sale el que toca")
    documento, *_ = C.html_capas(doc_de([dict(capa_logo, fondo_auto="l")]), KIT, None, logo, logo_oscuro)
    ok(G._data_uri(logo) in documento, "en automático sobre un fondo claro sale el logo normal")
    documento, *_ = C.html_capas(doc_de([dict(capa_logo)]), KIT, None, None, None)
    ok("<img" not in documento, "sin logo en el Kit, la capa de logo no pinta nada (ni una imagen rota)")
    foto_capa = {"id": "f1", "tipo": "imagen", "src": os.path.basename(foto), "x": 0, "y": 0, "w": 100, "h": 50,
                 "encuadre": {"x": 20, "y": 80, "zoom": 2}}
    documento, *_ = C.html_capas(doc_de([foto_capa]), None, lambda _n: foto)
    ok("object-view-box:inset(" in documento and "object-position:20% 80%" in documento,
       "la foto lleva su encuadre y su zoom")
    documento, *_ = C.html_capas(doc_de([foto_capa]), None, lambda _n: None)
    ok("<img" not in documento and "linear-gradient(135deg" in documento,
       "una foto que ya no está sale como bloque de color, nunca rota")
    x, y, w, h = C.encaje(C._limpiar_capa(foto_capa, set()), G.formato("v45"), 1600, 1200)
    # caja 1080×675, foto 1600×1200 con zoom 2: se ve un trozo de 800×600 ampliado ×1,35
    ok(abs(w - 200) < 1e-6 and abs(h - 240) < 1e-6,
       f"«encaje» (la cuenta para la pantalla del editor) amplía la foto con el zoom ({w:.2f} × {h:.2f} %)")
    ok(x <= 0 and y <= 0 and x + w >= 100 - 1e-6 and y + h >= 100 - 1e-6, "y la foto cubre toda su caja")


def guardar_y_leer(carpeta, foto):
    print("guardar en capas no toca la pieza de siempre")
    raiz = os.path.join(carpeta, "proyectos")
    os.makedirs(raiz)
    nombre_foto = G.guardar_imagen(raiz, "cli", open(foto, "rb").read())
    ficha = G.guardar_pieza(raiz, "cli", {"plantilla": 3, "textos": TEXTOS, "imagen": nombre_foto})
    pid = ficha["id"]
    carpeta_pieza = G._carpeta_pieza(raiz, "cli", pid)

    def huella(carpeta_=carpeta_pieza):
        return {n: open(os.path.join(carpeta_, n), "rb").read() for n in sorted(os.listdir(carpeta_))}

    antes = huella()
    ok(C.leer(raiz, "cli", pid)[1] is None, "sin guardar en capas, no hay versión en capas")
    doc = G._con_turno(lambda p: C.convertir(p, ficha))
    ok(doc["origen"]["sello"] == ficha["sello"], "la conversión lleva el sello de la pieza de la que sale")
    ok(huella() == antes, "leer y convertir no escriben nada")
    ok(not G.listar_piezas(raiz, "cli")[0]["en_capas"], "la lista dice que aún no está en capas")
    doc["nombre"] = "Versión en capas"
    doc["laminas"][0]["capas"][-1]["txt"] = "Ahora en capas"
    guardado = C.guardar(raiz, "cli", doc, pid)
    despues = huella()
    ok(all(despues[n] == antes[n] for n in antes), "pieza.json, pieza.png y pieza.jpg siguen byte a byte iguales")
    ok({"capas.json", "capas.png", "capas.jpg", "capas.sello.json"} <= set(despues),
       "lo nuevo va en capas.json, capas.png, capas.jpg y capas.sello.json")
    ok(not [n for n in despues if n.endswith(".tmp")], "sin ficheros temporales olvidados")
    _f, leido = C.leer(raiz, "cli", pid)
    ok(leido and leido["origen"]["sello"] == ficha["sello"], "lo leído lleva el sello de la pieza de la que salió")
    ok(leido and leido["laminas"][0]["capas"][-1]["txt"] == "Ahora en capas", "y se lee lo que se guardó")
    ok(guardado["id"] == pid, "guardar devuelve la misma pieza")
    lista = G.listar_piezas(raiz, "cli")[0]
    ok(lista["en_capas"] and lista["nombre"] == "Versión en capas" and lista["cambiada"] == guardado["cambiada"],
       "la lista dice que está en capas, con su nombre y su fecha")
    ok(G.ruta_final(raiz, "cli", pid, "png").endswith("capas.png"), "y se descarga la versión en capas (la última)")
    otra_vez = C.guardar(raiz, "cli", leido, pid)
    ok(otra_vez["id"] == pid, "lo leído se puede volver a guardar")
    # visto en la 2.ª revisión del 11-11: dos pestañas con la pieza abierta se pisaban sin aviso
    try:
        C.guardar(raiz, "cli", leido, pid)
        ok(False, "guardar otra vez lo abierto ANTES del último guardado en capas tendría que avisar")
    except C.ErrorConflicto:
        ok(True, "la otra pestaña, con lo abierto antes del último guardado en capas, recibe el aviso")
    ok(C.guardar(raiz, "cli", otra_vez["doc"], pid)["id"] == pid,
       "lo que devuelve un guardado sirve para el siguiente (lleva el número nuevo)")
    _f, leido = C.leer(raiz, "cli", pid)

    print("el editor de antes no descarta en silencio la versión en capas")
    # 3.ª revisión del 11-11: guardar con el editor de antes dejaba sin valor,
    # sin avisar, la versión en capas (más nueva)
    ok(falla(G.guardar_pieza, raiz, "cli", dict(ficha, textos=dict(TEXTOS, titulo="Cambiado")), pid),
       "guardar encima con el editor de antes avisa en vez de descartarla")
    ok(G.capas_vigentes(raiz, "cli", pid), "y la versión en capas sigue valiendo")
    print("si se pide descartarla a propósito, manda la más nueva")
    G.guardar_pieza(raiz, "cli", dict(ficha, textos=dict(TEXTOS, titulo="Cambiado con el editor de antes"),
                                     descartar_capas=True), pid)
    ok(C.leer(raiz, "cli", pid)[1] is None, "la versión en capas deja de valer (otro sello)")
    ok(not G.listar_piezas(raiz, "cli")[0]["en_capas"], "la lista ya no la da por buena")
    ok(G.ruta_final(raiz, "cli", pid, "jpg").endswith("pieza.jpg"), "y se descarga la pieza de siempre")
    ok(os.path.isfile(os.path.join(carpeta_pieza, "capas.json")), "capas.json no se borra: solo deja de valer")
    # visto en la revisión del 11-11: guardar lo abierto antes pisaba en silencio lo más nuevo
    try:
        C.guardar(raiz, "cli", leido, pid)
        ok(False, "guardar lo que se abrió ANTES del otro guardado tendría que avisar")
    except C.ErrorConflicto:
        ok(True, "guardar lo abierto antes del otro guardado avisa (no pisa lo más nuevo)")
    ok(not G.capas_vigentes(raiz, "cli", pid), "y no escribe nada")

    print("si otro guarda mientras se pinta, tampoco se pisa")
    ficha2 = G.leer_pieza(raiz, "cli", pid)
    doc2 = G._con_turno(lambda p: C.convertir(p, ficha2))
    real = C.pintar

    def con_otro_guardado(*args, **kwargs):
        salida = real(*args, **kwargs)
        G._escribir_json(os.path.join(carpeta_pieza, "pieza.json"), dict(ficha2, sello="abcdef01"))
        return salida
    C.pintar = con_otro_guardado
    try:
        antes = huella()
        try:
            C.guardar(raiz, "cli", doc2, pid)
            ok(False, "un guardado que llega mientras se pinta tendría que avisar")
        except C.ErrorConflicto:
            ok(True, "un guardado que llega mientras se pinta avisa")
        ok({k: v for k, v in huella().items() if k != "pieza.json"} == {k: v for k, v in antes.items() if k != "pieza.json"},
           "y no deja nada a medias")
    finally:
        C.pintar = real
    G._escribir_json(os.path.join(carpeta_pieza, "pieza.json"), ficha2)

    print("varios guardados a la vez de la misma pieza")
    import threading
    doc3 = G._con_turno(lambda p: C.convertir(p, ficha2))
    errores = []

    def guardar_uno(n):
        try:
            d = copy.deepcopy(doc3)
            d["nombre"] = f"Hilo {n}"
            C.guardar(raiz, "cli", d, pid)
        except Exception as fallo:                          # noqa: BLE001
            errores.append(f"{type(fallo).__name__}: {fallo}")
    hilos = [threading.Thread(target=guardar_uno, args=(n,)) for n in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    conflictos = [e for e in errores if e.startswith("ErrorConflicto")]
    ok(len(conflictos) == 3 and len(errores) == 3,
       f"cuatro pestañas guardan lo mismo a la vez: una entra y las otras tres reciben el aviso ({errores})")
    ok(not [n for n in os.listdir(carpeta_pieza) if n.endswith(".tmp")], "sin temporales olvidados")
    _f, final = C.leer(raiz, "cli", pid)
    meta = G.meta_capas(raiz, "cli", pid)
    ok(final and final["nombre"] == meta["nombre"], "el JSON y su ficha pequeña son del mismo guardado")

    print("una pieza que nace en capas")
    nueva = C.guardar(raiz, "cli", doc_de([capa_texto(txt="Nacida en capas")], nombre="Mi pieza"))
    nid = nueva["id"]
    ficha_nueva = G.leer_pieza(raiz, "cli", nid)
    ok(ficha_nueva.get("nacida_en_capas") and ficha_nueva["nombre"] == "Mi pieza", "tiene su ficha mínima")
    ok(G.limpiar_pieza(ficha_nueva)["plantilla"] == 2, "una ficha que el código de antes lee sin romperse")
    ok(any(p["id"] == nid and p["en_capas"] for p in G.listar_piezas(raiz, "cli")), "sale en la lista")
    for ext in ("png", "jpg"):
        ok(os.path.isfile(G.ruta_final(raiz, "cli", nid, ext)), f"y se descarga en {ext.upper()}")
    carpeta_nueva = G._carpeta_pieza(raiz, "cli", nid)
    png_antes = open(os.path.join(carpeta_nueva, "pieza.png"), "rb").read()
    _f, abierta = C.leer(raiz, "cli", nid)
    abierta["nombre"] = "Mi pieza cambiada"
    abierta["laminas"][0]["capas"][0]["txt"] = "Otro texto bien distinto"
    time.sleep(1.1)
    C.guardar(raiz, "cli", abierta, nid)
    ficha_nueva2 = G.leer_pieza(raiz, "cli", nid)
    # visto en la revisión del 11-11: volver a guardar una nacida no ponía al día pieza.png ni la ficha
    ok(open(os.path.join(carpeta_nueva, "pieza.png"), "rb").read() != png_antes,
       "volver a guardarla pone al día pieza.png (lo que ve y descarga main)")
    ok(ficha_nueva2["nombre"] == "Mi pieza cambiada" and ficha_nueva2["cambiada"] > ficha_nueva["cambiada"],
       "y su ficha: nombre y fecha")
    ok(ficha_nueva2["sello"] != ficha_nueva["sello"], "con sello nuevo (la miniatura de la lista se renueva)")
    try:
        C.guardar(raiz, "cli", abierta, nid)
        ok(False, "guardar otra vez lo abierto antes tendría que avisar también en una nacida")
    except C.ErrorConflicto:
        ok(True, "en una nacida, lo abierto antes del último guardado también recibe el aviso")
    ok(G.listar_piezas(raiz, "cli")[0]["id"] == nid, "la última guardada sale la primera en la lista")
    ok(falla(G.guardar_pieza, raiz, "cli", ficha_nueva2, nid),
       "el editor de antes no puede guardar encima de una pieza nacida en capas (borraría el diseño)")
    ok(falla(G.guardar_pieza, raiz, "cli", ficha_nueva2),
       "ni «Duplicar» con el editor de antes una nacida (saldría una plantilla vacía)")

    print("si algo falla a medias, no queda nada a medio escribir")

    def roto(*_a, **_k):
        raise G.ErrorGraficas("el navegador se ha caído")
    _f, buena = C.leer(raiz, "cli", nid)
    C.pintar = roto
    try:
        antes = huella(carpeta_nueva)
        ok(falla(C.guardar, raiz, "cli", buena, nid), "el fallo llega como error")
        ok(huella(carpeta_nueva) == antes, "y la carpeta queda como estaba")
        cuantas = len(G.listar_piezas(raiz, "cli"))
        ok(falla(C.guardar, raiz, "cli", doc_de([capa_texto()])), "una pieza nueva que falla…")
        ok(len(G.listar_piezas(raiz, "cli")) == cuantas, "…no deja una pieza a medias en la lista")
    finally:
        C.pintar = real
    ok(falla(C.guardar, raiz, "cli", doc_de([capa_texto()]), "000000000000"), "guardar en una pieza que no existe falla")
    ok(falla(C.guardar, raiz, "cli", doc_de([capa_texto()]), "../../x"), "y en una ruta rara también")
    ok(falla(C.guardar, raiz, "cli", {"version": 2}), "un documento sin láminas no se guarda")

    print("si el servidor se cae a mitad de guardar, la pieza no se queda bloqueada")
    _f, antes_del_corte = C.leer(raiz, "cli", nid)
    escribir = G._escribir_json

    def se_cae(ruta, datos):
        if ruta.endswith("capas.sello.json"):
            raise OSError("el servidor se ha caído")
        return escribir(ruta, datos)
    G._escribir_json = se_cae
    try:
        antes_del_corte["nombre"] = "Guardada justo antes del corte"
        try:
            C.guardar(raiz, "cli", antes_del_corte, nid)
        except OSError:
            pass
    finally:
        G._escribir_json = escribir
    _f, tras_el_corte = C.leer(raiz, "cli", nid)
    ok(tras_el_corte and tras_el_corte["nombre"] == "Guardada justo antes del corte",
       "se abre la última versión completa (la de capas.json)")
    ok(C.guardar(raiz, "cli", tras_el_corte, nid)["id"] == nid, "y se puede volver a guardar sin aviso de conflicto")
    ok(falla(C.guardar, raiz, "cli", antes_del_corte, nid), "lo abierto antes del corte sigue recibiendo el aviso")

    # 4.ª revisión del 11-11: el PRIMER guardado en capas de una pieza normal,
    # cortado antes de la ficha pequeña; la lista, la descarga y el editor de
    # antes tienen que ver lo mismo que «abrir»
    otra = G.guardar_pieza(raiz, "cli", {"plantilla": 1, "textos": TEXTOS})
    doc_otra = G._con_turno(lambda p: C.convertir(p, otra))
    doc_otra["nombre"] = "Cortada en el primer guardado"
    G._escribir_json = se_cae
    try:
        try:
            C.guardar(raiz, "cli", doc_otra, otra["id"])
        except OSError:
            pass
    finally:
        G._escribir_json = escribir
    _f, abierta_otra = C.leer(raiz, "cli", otra["id"])
    en_lista = next(p for p in G.listar_piezas(raiz, "cli") if p["id"] == otra["id"])
    ok(abierta_otra is not None and en_lista["en_capas"] and en_lista["nombre"] == "Cortada en el primer guardado",
       "tras un corte en el primer guardado, abrir y la lista dicen lo mismo")
    ok(G.ruta_final(raiz, "cli", otra["id"], "png").endswith("capas.png"), "la descarga también")
    ok(falla(G.guardar_pieza, raiz, "cli", dict(otra, textos=dict(TEXTOS, titulo="x")), otra["id"]),
       "y el editor de antes no la descarta en silencio")
    G.borrar_pieza(raiz, "cli", otra["id"])

    print("una tipografía quitada de la lista no deja la pieza sin abrir")
    meta_ruta = os.path.join(carpeta_nueva, "capas.json")
    datos = json.load(open(meta_ruta, encoding="utf-8"))
    datos["fuente_titulos"] = "ya-no-existe"
    json.dump(datos, open(meta_ruta, "w", encoding="utf-8"))
    _f, con_rara = C.leer(raiz, "cli", nid)
    ok(con_rara and con_rara["fuente_titulos"] == "", "se abre, y la tipografía vuelve a la del Kit")

    print("una ficha estropeada no rompe la descarga")
    sello_ruta = os.path.join(carpeta_nueva, "capas.sello.json")
    bueno = open(sello_ruta, "rb").read()
    with open(sello_ruta, "w", encoding="utf-8") as fh:
        fh.write("{roto")
    _f, sin_ficha = C.leer(raiz, "cli", nid)
    ok(sin_ficha and sin_ficha["laminas"][0]["capas"][0]["txt"] == "Otro texto bien distinto",
       "una nacida con su ficha pequeña rota abre su diseño de verdad (de capas.json), no una plantilla vacía")
    json_bueno = open(meta_ruta, "rb").read()
    with open(meta_ruta, "w", encoding="utf-8") as fh:
        fh.write("{roto")
    ok(falla(C.leer, raiz, "cli", nid),
       "y si también capas.json está roto, da error: nunca se abre convertida en una plantilla vacía")
    with open(sello_ruta, "wb") as fh:
        fh.write(bueno)
    with open(meta_ruta, "wb") as fh:
        fh.write(json_bueno)
    with open(os.path.join(carpeta_nueva, "capas.json"), "w", encoding="utf-8") as fh:
        fh.write('{"version": 2, "laminas": "roto"}')
    ok(falla(C.leer, raiz, "cli", nid), "una versión en capas que vale pero no se lee es un error (no una conversión vacía)")
    with open(os.path.join(carpeta_pieza, "pieza.json"), "w", encoding="utf-8") as fh:
        fh.write("{roto")
    try:
        ruta = G.ruta_final(raiz, "cli", pid, "png")
        ok(ruta.endswith("pieza.png"), "con pieza.json ilegible se descarga la pieza de siempre")
    except Exception as fallo:                              # noqa: BLE001
        ok(False, f"con pieza.json ilegible la descarga falla: {fallo}")
    print("borrar espera a que termine un guardado")
    import threading
    cerrojo = G.cerrojo_pieza("cli", nid)
    cerrojo.acquire()
    hilo = threading.Thread(target=G.borrar_pieza, args=(raiz, "cli", nid))
    hilo.start()
    time.sleep(0.3)
    ok(os.path.exists(carpeta_nueva), "mientras alguien guarda, la pieza no se borra")
    cerrojo.release()
    hilo.join(10)
    ok(not os.path.exists(carpeta_nueva), "y al terminar se borra, con sus capas")


class _Peticion:
    headers = {}


def las_rutas(carpeta, foto):
    print("las rutas del servidor")
    sys.path.insert(0, os.path.dirname(AQUI))
    import app as servidor                                  # noqa: PLC0415
    import clientes                                         # noqa: PLC0415
    raiz = os.path.join(carpeta, "rutas")
    os.makedirs(raiz)
    antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(raiz)
    try:
        cid = clientes.crear(raiz, "Café Alba")["id"]
        nombre_foto = G.guardar_imagen(raiz, cid, open(foto, "rb").read())
        ficha = G.guardar_pieza(raiz, cid, {"plantilla": 10, "textos": TEXTOS, "imagen": nombre_foto})
        pid = ficha["id"]
        carpeta_pieza = G._carpeta_pieza(raiz, cid, pid)
        listado = sorted(os.listdir(carpeta_pieza))
        r = servidor.graficas_leer_capas(cid, pid, _Peticion())
        ok(r["origen"] == "convertida" and r["doc"]["version"] == 2, "leer las capas de una pieza de antes la convierte")
        ok(sorted(os.listdir(carpeta_pieza)) == listado, "y no escribe nada")
        c = servidor.graficas_comparar_capas(cid, pid, _Peticion())
        ok(c["igual"] is True and set(c) == {"igual", "diferencia", "visible", "lineas", "faltan", "movidos"},
           f"comparar dice que sale igual ({c})")
        v = servidor.graficas_vista_capas(cid, _Peticion(), {"doc": r["doc"]})
        ok(v["img"].startswith("data:image/jpeg;base64,"), "la vista previa devuelve la imagen")
        ok(sorted(os.listdir(carpeta_pieza)) == listado, "comparar y la vista previa no escriben nada")
        g = servidor.graficas_guardar_capas(cid, pid, _Peticion(), {"doc": r["doc"]})
        ok(g["id"] == pid and os.path.isfile(os.path.join(carpeta_pieza, "capas.json")), "guardar escribe capas.json")
        r2 = servidor.graficas_leer_capas(cid, pid, _Peticion())
        ok(r2["origen"] == "guardada", "y al volver a leer sale la guardada")
        n = servidor.graficas_crear_en_capas(cid, _Peticion(), {"doc": r["doc"]})
        ok(n["id"] != pid, "una pieza nueva en capas tiene su propio id")

        def codigo(funcion, *args):
            try:
                funcion(*args)
                return 200
            except servidor.ErrorApi as fallo:
                return fallo.codigo
        ok(codigo(servidor.graficas_comparar_capas, cid, n["id"], _Peticion()) == 400,
           "comparar una pieza nacida en capas da 400 (no hay versión de antes)")
        ok(codigo(servidor.graficas_leer_capas, cid, "000000000000", _Peticion()) == 404,
           "una pieza que no existe da 404")
        ok(codigo(servidor.graficas_cambiar_pieza, cid, pid, _Peticion(), dict(ficha, textos=dict(TEXTOS, titulo="Otro"))) == 400,
           "el editor de antes no puede guardar encima de la versión en capas (400 con explicación)")
        G.guardar_pieza(raiz, cid, dict(ficha, textos=dict(TEXTOS, titulo="Otro"), descartar_capas=True), pid)
        ok(codigo(servidor.graficas_guardar_capas, cid, pid, _Peticion(), {"doc": r2["doc"]}) == 409,
           "guardar lo abierto antes de otro guardado da 409")
        for funcion, args, que in (
                (servidor.graficas_vista_capas, (cid, _Peticion(), {"doc": {"version": 2}}), "una vista sin láminas"),
                (servidor.graficas_vista_capas, (cid, _Peticion(), {"doc": r["doc"], "lamina": 5}), "una lámina que no está"),
                (servidor.graficas_vista_capas, (cid, _Peticion(), {"doc": r["doc"], "lamina": True}), "una lámina rara"),
                (servidor.graficas_guardar_capas, (cid, "zzz", _Peticion(), {"doc": r["doc"]}), "una pieza con id raro"),
                (servidor.graficas_leer_capas, ("otro", pid, _Peticion()), "un proyecto que no existe")):
            try:
                funcion(*args)
                ok(False, f"{que} tendría que dar error")
            except servidor.ErrorApi as fallo:
                ok(fallo.codigo in (400, 404), f"{que} da {fallo.codigo}")
        real = servidor.GRAFICAS_CAPAS
        servidor.GRAFICAS_CAPAS = None
        try:
            ok(codigo(servidor.graficas_leer_capas, cid, pid, _Peticion()) == 503,
               "si las capas no cargan, sus rutas dan 503…")
            ok(isinstance(servidor.graficas_piezas(cid, _Peticion()), dict), "…y el resto de Gráficas sigue funcionando")
        finally:
            servidor.GRAFICAS_CAPAS = real
        clientes.cambiar(raiz, cid, clave="1234")
        try:
            servidor.graficas_leer_capas(cid, pid, _Peticion())
            ok(False, "un proyecto con clave tendría que pedirla")
        except servidor.ErrorApi as fallo:
            ok(fallo.codigo == 403, "un proyecto con clave, cerrado, da 403 (como el resto de Gráficas)")
    finally:
        servidor.fijar_raiz_proyectos(antes)


def main():
    completo = "--completo" in sys.argv
    inicio = time.time()
    carpeta = tempfile.mkdtemp(prefix="graficas_capas_")
    try:
        limpieza_y_seguridad()
        colores_del_kit()
        foto = foto_de_prueba(carpeta)
        pincel = G.Pincel()
        try:
            plantillas_iguales(pincel, foto, completo)
            la_comparacion_caza(pincel, foto)
            el_pintado(pincel, foto, carpeta)
        finally:
            pincel.cerrar()
        guardar_y_leer(carpeta, foto)
        las_rutas(carpeta, foto)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal ({time.time() - inicio:.0f} s)")
    sys.exit(1 if CUENTA["mal"] else 0)


if __name__ == "__main__":
    main()

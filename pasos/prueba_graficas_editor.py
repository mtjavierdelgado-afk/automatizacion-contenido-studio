"""Las comprobaciones del editor con capas de Gráficas (rama graficas-2-editor, 12-11-2026).

    python pasos/prueba_graficas_editor.py

Lo del servidor que usa el editor —«Volver a montar», las líneas de cada texto
en la vista final, «Ver la versión anterior», las letras y el logo— y que la
pantalla haga LAS MISMAS CUENTAS que el servidor: cada color, borde, sombra y
caja que pinta `web/graficas_editor.js` se compara, con Node, con lo que pinta
`graficas_capas.py` para cientos de capas al azar. La pantalla entera la recorre
`pruebas/recorrido/graficas_2_editor.py` (con Chromium).

Necesita el navegador que pinta las gráficas (ESTUDIO_EDGE, como
`prueba_graficas_capas`) y Node para la parte de las cuentas (sin Node, esa
parte se omite y lo dice). No baja nada ni llama a ninguna IA.
"""
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI)
os.environ["ESTUDIO_SIN_DESCARGAS"] = "1"

import graficas as G  # noqa: E402
import graficas_capas as C  # noqa: E402

CUENTA = {"ok": 0, "mal": 0}
EDITOR_JS = os.path.join(RAIZ, "web", "graficas_editor.js")


def ok(cond, que):
    CUENTA["ok" if cond else "mal"] += 1
    if not cond:
        print(f"  MAL: {que}")


def foto_de_prueba(carpeta):
    from PIL import Image                                   # noqa: PLC0415
    ruta = os.path.join(carpeta, "foto.png")
    img = Image.new("RGB", (800, 600), (40, 120, 200))
    for x in range(0, 800, 40):
        for y in range(0, 600, 40):
            if (x // 40 + y // 40) % 2:
                img.paste((230, 140, 40), (x, y, x + 40, y + 40))
    img.save(ruta)
    return ruta


def _capas(doc, lamina=0):
    return doc["laminas"][lamina]["capas"]


def _rol(doc, rol):
    return next((c for c in _capas(doc) if c["rol"] == rol), None)


# ================================================================ montar

def montar(pincel, raiz, cid, foto):
    print("«Volver a montar» y «Empezar de»")
    nombre_foto = G.guardar_imagen(raiz, cid, open(foto, "rb").read())
    antes = sorted(os.walk(raiz))
    nuevo = C.montar(pincel, 1, "v45", None, {"titulo": "Hola\nmundo", "marca": "Alba", "nada": "x"})
    ok(sorted(os.walk(raiz)) == antes, "montar no escribe nada")
    ok(nuevo["formato"] == "v45" and nuevo["origen"]["plantilla"] == 1, "una pieza nueva sale con su plantilla y su tamaño")
    ok(_rol(nuevo, "titulo")["txt"] == "Hola\nmundo", "el texto entra entero, con su salto de línea")
    ok(_rol(nuevo, "marca")["txt"] == "Alba", "y cada campo con el suyo")
    ids = [c["id"] for c in _capas(nuevo)]
    ok(len(ids) == len(set(ids)), "sin ids repetidos")

    # la pieza tal como la deja el editor: un texto con color propio, otra capa añadida y la foto
    doc = json.loads(json.dumps(nuevo))
    _rol(doc, "titulo")["color"] = "#123456"
    _rol(doc, "marca")["color"] = "kit:acento"
    doc["laminas"][0]["capas"].append({"tipo": "forma", "id": "mia1", "rol": "", "nombre": "Mía", "x": 5, "y": 5, "w": 10, "h": 10,
                                       "relleno": {"color": "kit:acento"}})
    doc["laminas"][0]["capas"].append({"tipo": "imagen", "id": "foto1", "rol": "", "x": 50, "y": 50, "w": 40, "h": 30,
                                       "src": nombre_foto, "encuadre": {"x": 20, "y": 80, "zoom": 1.5}})
    doc["laminas"].append({"capas": [{"tipo": "forma", "id": "otra1", "x": 0, "y": 0, "w": 50, "h": 50}]})
    doc["origen"].update(sello="abcd1234", guardado="0011223344556677")
    m = C.montar(pincel, 2, "h916", doc, {"kicker": "Novedad", "cta": "Ven"})
    ok(m["formato"] == "h916" and m["origen"]["plantilla"] == 2, "otra plantilla en otro tamaño")
    ok(m["origen"]["sello"] == "abcd1234" and m["origen"]["guardado"] == "0011223344556677",
       "conserva el sello para guardar sin pisar nada")
    ok(_rol(m, "titulo")["txt"] == "Hola\nmundo", "conserva el texto de cada campo")
    ok(_rol(m, "titulo")["color"] == "#123456", "y un color elegido a mano")
    limpia2 = C.montar(pincel, 2, "h916", None, {"marca": "Alba"})
    ok(_rol(m, "marca")["color"] == _rol(limpia2, "marca")["color"], "un color del Kit toma el de la plantilla nueva")
    ok(_rol(m, "kicker")["txt"] == "Novedad", "un campo que no tenía sale con el texto propuesto")
    mia = next((c for c in _capas(m) if c["id"] == "mia1"), None)
    ok(mia is not None and mia["nombre"] == "Mía", "lo añadido se queda, tal cual")
    fotos = [c for c in _capas(m) if c["tipo"] == "imagen"]
    ok(len(fotos) == 1 and fotos[0]["rol"] == "foto" and fotos[0]["src"] == nombre_foto,
       "la foto añadida pasa a ser la de la plantilla, sin quedarse repetida")
    ok(fotos[0]["encuadre"] == {"x": 20, "y": 80, "zoom": 1.5}, "con su encuadre")
    ok(m["laminas"][1] == C.limpiar_doc(doc)["laminas"][1], "las otras láminas no se tocan")
    ids = [c["id"] for lam in m["laminas"] for c in lam["capas"]]
    ok(len(ids) == len(set(ids)), "ids únicos en todo el documento")

    # de una plantilla con foto a una sin foto: la foto no se pierde
    m2 = C.montar(pincel, 1, "c11", m)
    fotos = [c for c in _capas(m2) if c["tipo"] == "imagen"]
    ok(len(fotos) == 1 and fotos[0]["oculto"] and _capas(m2)[0]["tipo"] == "imagen",
       "con una plantilla sin foto, la foto queda abajo del todo y oculta")
    ok(_rol(m2, "kicker") is not None and _rol(m2, "kicker")["txt"] == "Novedad",
       "y el campo que la plantilla nueva no usa se queda, con su texto")
    m3 = C.montar(pincel, 2, "v45", m2)
    ok(sum(1 for c in _capas(m3) if c["tipo"] == "imagen") == 1, "volver a una con foto no la duplica")

    for args, que in (((99, "v45", doc), "una plantilla que no existe"), (("2", "v45", doc), "una plantilla que no es un número"),
                      ((2, "zz", doc), "un tamaño que no existe"), ((2, None, doc), "sin tamaño"),
                      ((2, "v45", {"version": 2}), "un documento sin láminas")):
        try:
            C.montar(pincel, *args)
            ok(False, f"{que} tendría que dar error")
        except G.ErrorGraficas:
            ok(True, que)
    try:
        C.montar(pincel, 2, "v45", doc, None, lamina=7)
        ok(False, "una lámina que no está tendría que dar error")
    except G.ErrorGraficas:
        ok(True, "una lámina que no está da error")
    lleno = json.loads(json.dumps(doc))
    lleno["laminas"][0]["capas"] += [{"tipo": "forma", "id": f"x{i}", "x": 0, "y": 0, "w": 1, "h": 1} for i in range(60 - len(_capas(lleno)))]
    ok(len(_capas(C.montar(pincel, 7, "v45", lleno))) <= C.MAX_CAPAS, "nunca pasa del tope de capas")
    return m


def lineas(pincel, doc):
    print("las líneas de cada texto en la vista final")
    _rol(doc, "titulo")["txt"] = "Una línea\nY otra"
    C.pintar(pincel, doc)
    n = C.contar_lineas(pincel)
    ok(n.get(_rol(doc, "titulo")["id"]) == 2, f"un texto con un salto ocupa 2 líneas ({n})")
    ok(all(isinstance(v, int) for v in n.values()) and all(re.fullmatch(r"[a-z0-9]{1,12}", k) for k in n),
       "solo ids de capa y números")


# ================================================================ rutas y ficheros

class _Peticion:
    headers = {}
    query_params = {}


def rutas(carpeta, foto):
    print("las rutas del editor")
    sys.path.insert(0, RAIZ)
    import app as servidor                                  # noqa: PLC0415
    import clientes                                         # noqa: PLC0415
    raiz = os.path.join(carpeta, "rutas")
    os.makedirs(raiz)
    antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(raiz)

    def codigo(funcion, *args, **kw):
        try:
            funcion(*args, **kw)
            return 200
        except servidor.ErrorApi as fallo:
            return fallo.codigo
    try:
        cid = clientes.crear(raiz, "Café Alba")["id"]
        nombre_foto = G.guardar_imagen(raiz, cid, open(foto, "rb").read())
        ficha = G.guardar_pieza(raiz, cid, {"plantilla": 2, "textos": {"titulo": "Hola", "kicker": "Ya"}, "imagen": nombre_foto})
        pid = ficha["id"]
        r = servidor.graficas_montar_capas(cid, _Peticion(), {"plantilla": 3, "formato": "c11", "textos": {"titulo": "Uno"}})
        ok(r["doc"]["formato"] == "c11" and _rol(r["doc"], "titulo")["txt"] == "Uno", "POST capas/montar devuelve la pieza montada")
        for cuerpo, que in (({"plantilla": 0, "formato": "c11"}, "una plantilla rara"), ({"plantilla": 3, "formato": "?"}, "un tamaño raro"),
                            ({"plantilla": 3, "formato": "c11", "doc": "nada"}, "un documento raro"),
                            ({"plantilla": 3, "formato": "c11", "lamina": "x"}, "una lámina rara")):
            ok(codigo(servidor.graficas_montar_capas, cid, _Peticion(), cuerpo) == 400, f"montar con {que} da 400")
        leida = servidor.graficas_leer_capas(cid, pid, _Peticion())
        v = servidor.graficas_vista_capas(cid, _Peticion(), {"doc": leida["doc"]})
        ok(isinstance(v.get("lineas"), dict) and v["lineas"].get(_rol(leida["doc"], "titulo")["id"]) == 1,
           "la vista dice cuántas líneas ocupa cada texto")
        # la versión anterior
        ok(codigo(servidor.graficas_fichero, cid, pid, "jpg", _Peticion(), antes=1) == 200, "?antes=1 de una pieza de antes: su JPG")
        servidor.graficas_guardar_capas(cid, pid, _Peticion(), {"doc": leida["doc"]})
        ruta_capas = G.ruta_final(raiz, cid, pid, "jpg")
        ruta_antes = G.ruta_final(raiz, cid, pid, "jpg", antes=True)
        ok(ruta_capas.endswith("capas.jpg") and ruta_antes.endswith("pieza.jpg"),
           "con versión en capas, la descarga da la de capas y ?antes=1 la de antes")
        nacida = servidor.graficas_crear_en_capas(cid, _Peticion(), {"doc": leida["doc"]})
        ok(codigo(servidor.graficas_fichero, cid, nacida["id"], "jpg", _Peticion(), antes=1) == 404,
           "una pieza nacida en capas no tiene versión anterior (404)")
        ok(codigo(servidor.graficas_fichero, cid, "000000000000", "jpg", _Peticion(), antes=1) == 404, "una pieza que no está: 404")
        ok(codigo(servidor.graficas_fichero, cid, pid, "gif", _Peticion()) == 400, "un formato raro: 400")
        # el logo
        ok(codigo(servidor.graficas_logo, cid, "normal", _Peticion()) == 404, "sin logo subido, el logo da 404")
        ok(codigo(servidor.graficas_logo, cid, "../../x", _Peticion()) == 404, "una variante rara da 404")
        logos = os.path.join(raiz, "_logo_prueba.png")
        shutil.copy(foto, logos)
        real = servidor._logos_de_graficas
        servidor._logos_de_graficas = lambda ficha, kit: (logos, None)
        try:
            ok(codigo(servidor.graficas_logo, cid, "normal", _Peticion()) == 200, "con logo, se sirve")
            ok(codigo(servidor.graficas_logo, cid, "oscuro", _Peticion()) == 404, "y el oscuro, si no hay, 404")
        finally:
            servidor._logos_de_graficas = real
        # las letras
        una = G.FUENTES["anton"][1][0][1]
        ok(codigo(servidor.graficas_tipografia, "../../etc/passwd", _Peticion()) == 404, "una letra con ruta da 404")
        ok(codigo(servidor.graficas_tipografia, "loquesea.ttf", _Peticion()) == 404, "una letra que no es de la lista da 404")
        if G._ruta_fuente(una):
            r = servidor.graficas_tipografia(una, _Peticion())
            ok(getattr(r, "media_type", "") == "font/ttf", "una letra de la lista se sirve")
        cat = G.catalogo()
        ok(set(cat["caras"]) == set(G.FUENTES) and set(cat["familias"]) == set(G.FUENTES),
           "el catálogo trae cada letra con sus ficheros")
        ok(all(cara["fichero"] and cara["pesos"] for caras in cat["caras"].values() for cara in caras), "y cada cara con sus pesos")
        # con clave
        clientes.cambiar(raiz, cid, clave="1234")
        for funcion, args, que in ((servidor.graficas_montar_capas, (cid, _Peticion(), {"plantilla": 3, "formato": "c11"}), "montar"),
                                   (servidor.graficas_logo, (cid, "normal", _Peticion()), "el logo"),
                                   (servidor.graficas_fichero, (cid, pid, "jpg", _Peticion()), "la versión anterior")):
            ok(codigo(funcion, *args) == 403, f"un proyecto con clave, cerrado: {que} da 403")
    finally:
        servidor.fijar_raiz_proyectos(antes)


def sellado():
    print("los ficheros del editor, en su sitio y sellados")
    sys.path.insert(0, RAIZ)
    import app as servidor                                  # noqa: PLC0415
    ok(set(servidor.ASSETS_SELLADOS) >= {"graficas_editor.js", "graficas_editor.css"}, "los dos ficheros del editor se sellan")
    portada = servidor._portada_sellada().body.decode("utf-8")
    for nombre in ("graficas_editor.js", "graficas_editor.css"):
        sello = servidor._sello_asset(nombre)
        ok(f'"{nombre}?v={sello}"' in portada, f"la portada nombra {nombre} con su sello")
    js = open(EDITOR_JS, encoding="utf-8").read()
    css = open(os.path.join(RAIZ, "web", "graficas_editor.css"), encoding="utf-8").read()
    codigo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    ok("setAttribute('style'" not in codigo and 'style="' not in codigo and "style: '" not in codigo,
       "el editor no usa atributos style (la CSP los bloquea)")
    ok(not re.search(r"#[0-9a-fA-F]{3,6}\b", re.sub(r"/\*.*?\*/", "", css, flags=re.S)),
       "el CSS del editor no lleva colores escritos a mano (todo con las variables)")
    ok("createObjectURL" not in js, "las imágenes van como data: (la CSP no deja blob: en <img>)")
    app_js = open(os.path.join(RAIZ, "web", "app.js"), encoding="utf-8").read()
    ok("data-editor-js" in open(os.path.join(RAIZ, "web", "index.html"), encoding="utf-8").read()
       and "dataset.editorJs" in app_js, "app.js carga el editor por el nombre sellado de index.html")


# ================================================================ las mismas cuentas

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const ctx = { window: {}, document: {}, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[process.argv.length - 1], 'utf8'), ctx);
const K = ctx.window.EditorCapas._cuentas;
const casos = JSON.parse(fs.readFileSync(0, 'utf8'));
const salida = casos.map(c => {
  const col = K.coloresFinales(c.defecto, c.kit, c.doc);
  return {
    colores: col,
    tinta: K.tintaPara(c.fondo, c.oscuro, c.claro),
    f6: c.numeros.map(K.f6),
    color: K.cssColor(c.capa.color, c.capa.alfa, col),
    relleno: K.cssRelleno(c.capa.relleno, col),
    borde: K.cssBorde(c.capa.borde, col),
    radio: K.cssRadio(c.capa.radio),
    sombra: K.cssSombras(c.capa.sombra, col, 'box-shadow'),
    sombraTexto: K.cssSombras(c.capa.sombra, col, 'text-shadow'),
    caja: K.cssCaja(c.capa, true, 0),
    cajaTexto: K.cssCaja(c.capa, false, c.holgura),
  };
});
process.stdout.write(JSON.stringify({ salida, limites: K.LIMITES, muestra: Object.keys(K.CAMPOS_DE_MUESTRA) }));
"""


def _color_al_azar(rnd):
    if rnd.random() < 0.5:
        return rnd.choice(["kit:principal", "kit:secundario", "kit:oscuro", "kit:claro", "kit:acento",
                           "tinta:principal", "tinta:secundario", "tinta:oscuro", "tinta:claro", "tinta:acento"])
    return "#" + "".join(rnd.choice("0123456789ABCDEF") for _ in range(6))


def cuentas():
    print("la pantalla hace las mismas cuentas que el servidor")
    node = shutil.which("node")
    if not node:
        print("  (sin Node: esta parte se omite)")
        return
    rnd = random.Random(1112)
    casos, esperado = [], []
    for _ in range(400):
        hexa = lambda: "#" + "".join(rnd.choice("0123456789ABCDEF") for _ in range(6))  # noqa: E731
        kit = {"colores": {r: hexa() for r in G.ROLES if rnd.random() < 0.6}}
        doc_col = {r: hexa() for r in G.ROLES if rnd.random() < 0.3}
        capa = {"tipo": "forma", "id": "a1", "x": rnd.uniform(-50, 120), "y": rnd.uniform(-50, 120), "w": rnd.uniform(0, 120),
                "h": rnd.uniform(0, 120), "giro": rnd.choice([0, 0, rnd.uniform(-360, 360)]), "opac": rnd.choice([1, rnd.random()]),
                "origen": [rnd.uniform(-100, 200), rnd.uniform(-100, 200)],
                "relleno": rnd.choice([None, {"color": _color_al_azar(rnd), "alfa": rnd.choice([1, rnd.random()])},
                                       {"degradado": {"ang": rnd.uniform(-360, 360), "paradas": [
                                           {"color": _color_al_azar(rnd), "alfa": rnd.random(), "pos": rnd.choice([None, rnd.uniform(0, 100)])}
                                           for _ in range(rnd.randint(2, 4))]}}]),
                "borde": rnd.choice([None, {"anchos": [rnd.choice([0, rnd.uniform(0, 5)]) for _ in range(4)], "color": _color_al_azar(rnd), "alfa": rnd.random()}]),
                "radio": rnd.choice([0, "elipse", rnd.uniform(0, 50)]),
                "sombra": [{"x": rnd.uniform(-5, 5), "y": rnd.uniform(-5, 5), "blur": rnd.uniform(0, 9), "spread": rnd.uniform(-2, 2),
                            "color": _color_al_azar(rnd), "alfa": rnd.random()} for _ in range(rnd.randint(0, 2))]}
        limpia = C._limpiar_capa(capa, set())
        if limpia["borde"] is None:
            capa["borde"] = None
        capa = dict(limpia, tipo="forma")
        fondo, oscuro, claro = hexa(), hexa(), hexa()
        numeros = [rnd.uniform(-1000, 1000), rnd.uniform(-1, 1) * 1e-7, 0.0, -0.0000001, 12.5, rnd.random()]
        holgura = rnd.choice([0, 0.015625, 0.03125])
        casos.append({"defecto": G.COLORES_DEFECTO, "kit": kit, "doc": {"colores": doc_col}, "fondo": fondo, "oscuro": oscuro,
                      "claro": claro, "numeros": numeros, "capa": capa, "holgura": holgura})
        col = G.colores_finales(kit, {"colores": doc_col})
        esperado.append({
            "colores": col, "tinta": G._tinta_para(fondo, oscuro, claro), "f6": [C._f(n) for n in numeros],
            "relleno": C._css_relleno(capa["relleno"], col), "borde": C._css_borde(capa["borde"], col),
            "radio": C._css_radio(capa["radio"]), "sombra": C._css_sombras(capa["sombra"], col, "box-shadow"),
            "sombraTexto": C._css_sombras(capa["sombra"], col, "text-shadow"),
            "caja": C._css_caja(capa, None, True, 0.0), "cajaTexto": C._css_caja(capa, None, False, holgura),
        })
        # un color suelto, con su opacidad (lo que lleva un texto)
        casos[-1]["capa"]["color"] = _color_al_azar(rnd)
        casos[-1]["capa"]["alfa"] = rnd.choice([1, rnd.random()])
        esperado[-1]["color"] = C._css_color(casos[-1]["capa"]["color"], casos[-1]["capa"]["alfa"], col)
    r = subprocess.run([node, "-e", _NODE, EDITOR_JS], input=json.dumps(casos), capture_output=True, text=True, timeout=120)
    if r.returncode:
        ok(False, f"Node no ha podido correr las cuentas del editor: {r.stderr[-400:]}")
        return
    datos = json.loads(r.stdout)
    for clave, que in (("colores", "los colores de la pieza (Kit y propios)"), ("tinta", "el texto que se lee sobre un color"),
                       ("f6", "los números del CSS"), ("color", "un color con su opacidad"), ("relleno", "los rellenos y degradados"),
                       ("borde", "los bordes"), ("radio", "las esquinas"), ("sombra", "las sombras"),
                       ("sombraTexto", "las sombras de las letras"), ("caja", "la caja, el giro y la opacidad"),
                       ("cajaTexto", "la caja de un texto (con su holgura)")):
        malos = [i for i, (a, b) in enumerate(zip(datos["salida"], esperado)) if a[clave] != b[clave]]
        ok(not malos, f"{que}: igual en la pantalla y en el PNG"
           + (f" (caso {malos[0]}: {datos['salida'][malos[0]][clave]!r} != {esperado[malos[0]][clave]!r})" if malos else ""))
    ok(datos["limites"] == {"capas": C.MAX_CAPAS, "fotos": C.MAX_FOTOS, "texto": C.MAX_TEXTO},
       "los topes de la pantalla son los del servidor")
    ok(set(datos["muestra"]) == set(G.CAMPOS), "los textos de muestra cubren todos los campos de las plantillas")


def main():
    carpeta = tempfile.mkdtemp(prefix="graficas_editor_")
    try:
        cuentas()
        sellado()
        foto = foto_de_prueba(carpeta)
        raiz = os.path.join(carpeta, "proyectos")
        os.makedirs(raiz)
        cid = "cafe"
        pincel = G.Pincel()
        try:
            doc = montar(pincel, raiz, cid, foto)
            lineas(pincel, doc)
        finally:
            pincel.cerrar()
        rutas(carpeta, foto)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

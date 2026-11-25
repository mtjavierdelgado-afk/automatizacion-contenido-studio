"""Las comprobaciones de los carruseles de Gráficas (rama graficas-3-carrusel, 19-11-2026).

    python pasos/prueba_graficas_carrusel.py

Una pieza con varias láminas: el formato (id, tipo y familia de cada lámina,
las copias «en todas» con `enlace`, `salvo` y `solo_horizontal`, el texto
alternativo), el número automático {n}/{total} y que la pantalla del editor
haga las mismas cuentas que el servidor. Y lo más importante: una pieza de una
sola lámina se guarda y se pinta EXACTAMENTE igual que antes de la rama.

Necesita el navegador que pinta las gráficas (ESTUDIO_EDGE, como
`prueba_graficas_capas`) y Node para comparar con el editor (sin Node, esa parte
se omite y lo dice). No baja nada ni llama a ninguna IA.
"""
import json
import os
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


def _texto(cid, txt, **extra):
    return dict({"tipo": "texto", "id": cid, "rol": "", "x": 10, "y": 10, "w": 80, "h": 10, "txt": txt}, **extra)


def _forma(cid, **extra):
    return dict({"tipo": "forma", "id": cid, "x": 0, "y": 0, "w": 100, "h": 100, "relleno": {"color": "kit:oscuro"}}, **extra)


def carrusel(formato="v45"):
    """Tres láminas con lo de un carrusel: número, «Desliza →» y la marca, en todas."""
    def lamina(i, tipo):
        return {"id": f"lam{i}", "tipo": tipo, "familia": 1, "alt": f"Lámina {i}", "capas": [
            _forma(f"f{i}"),
            _texto(f"t{i}", f"Idea {i}"),
            _texto(f"n{i}", "{n}/{total}", enlace="num", salvo=["primera"], solo_horizontal=True),
            _texto(f"d{i}", "Desliza →", enlace="des", salvo=["primera", "ultima", "pdf"], solo_horizontal=True),
            _texto(f"m{i}", "Marca", enlace="mar", salvo=["primera"]),
        ]}
    return {"version": 2, "formato": formato, "nombre": "Carrusel",
            "laminas": [lamina(1, "portada"), lamina(2, "punto"), lamina(3, "cierre")]}


# ================================================================ formato

def formato_del_documento():
    print("el formato: láminas, copias enlazadas y texto alternativo")
    # una pieza de siempre: ni una clave nueva al limpiarla
    vieja = {"version": 2, "formato": "v45", "nombre": "x", "origen": {"plantilla": 3},
             "laminas": [{"capas": [_texto("a1", "Hola"), _forma("b1")]}]}
    limpia = C.limpiar_doc(vieja)
    ok(set(limpia["laminas"][0]) == {"capas"}, "una pieza de una lámina no gana claves nuevas (ni id)")
    ok(all(not ({"enlace", "salvo", "solo_horizontal"} & set(c)) for c in limpia["laminas"][0]["capas"]),
       "ni sus capas")
    ok(set(limpia["origen"]) == {"plantilla", "sello", "guardado", "nacida"}, "ni su origen")
    ok(C.limpiar_doc(limpia) == limpia, "limpiar dos veces da lo mismo")

    doc = C.limpiar_doc(carrusel())
    ok([lam["id"] for lam in doc["laminas"]] == ["lam1", "lam2", "lam3"], "cada lámina guarda su id")
    ok([lam["tipo"] for lam in doc["laminas"]] == ["portada", "punto", "cierre"], "y su tipo")
    ok(all(lam["familia"] == 1 for lam in doc["laminas"]), "y su familia")
    ok(doc["laminas"][1]["alt"] == "Lámina 2", "y su texto alternativo")
    num = next(c for c in doc["laminas"][0]["capas"] if c["id"] == "n1")
    ok(num["enlace"] == "num" and num["salvo"] == ["primera"] and num["solo_horizontal"] is True,
       "una copia «en todas» guarda su enlace, dónde no sale y si solo va en horizontal")
    ok(C.limpiar_doc(doc) == doc, "un carrusel limpio se limpia igual")

    # lo que no vale se tira, sin romper nada
    raro = carrusel()
    raro["laminas"][0].update(id="NO VALE", tipo="nada", familia=99, alt="x\x00" * 500)
    raro["laminas"][1]["id"] = "lam1"                          # repetido
    raro["laminas"][0]["capas"][2].update(enlace="NO VALE!", salvo=["medio", "ultima", "ultima"], solo_horizontal="no")
    r = C.limpiar_doc(raro)
    ids = [lam["id"] for lam in r["laminas"]]
    ok(len(set(ids)) == 3 and all(C._RE_ID.fullmatch(i) for i in ids), f"con varias láminas todas tienen un id válido y distinto ({ids})")
    ok(C.limpiar_doc(raro) == r, "y el mismo documento da los mismos ids (no al azar)")
    ok("tipo" not in r["laminas"][0] and "familia" not in r["laminas"][0], "un tipo o una familia que no existen se quitan")
    ok(len(r["laminas"][0]["alt"]) <= C.MAX_ALT and "\x00" not in r["laminas"][0]["alt"], "el texto alternativo se acota y se limpia")
    capa = r["laminas"][0]["capas"][2]
    ok("enlace" not in capa and capa["salvo"] == ["ultima"] and "solo_horizontal" not in capa,
       "un enlace raro se quita; «salvo» solo con lo que existe y sin repetir; un «no» escrito no es un sí")
    ok("envio" not in C.limpiar_doc(carrusel())["origen"], "el origen solo lleva «envio» si llega")
    ok(C.limpiar_doc(dict(carrusel(), origen={"envio": "ABCdef12zz"}))["origen"]["envio"] == "def12",
       "y lo deja en hexadecimal")
    try:
        C.limpiar_doc(dict(carrusel(), laminas=carrusel()["laminas"] * 7))
        ok(False, "más de 20 láminas se rechazan")
    except C.ErrorGraficas:
        ok(True, "más de 20 láminas se rechazan")


# ================================================================ lo que se pinta

def capas_por_lamina():
    print("lo que sale en cada lámina")
    doc = C.limpiar_doc(carrusel())
    f = G.formato("v45")
    vistos = [[c["id"] for c in C.capas_de_lamina(doc, i, f)] for i in range(3)]
    ok(vistos[0] == ["f1", "t1"], f"la portada no lleva número, «Desliza» ni marca enlazada ({vistos[0]})")
    ok(vistos[1] == ["f2", "t2", "n2", "d2", "m2"], f"una lámina del medio lleva todo ({vistos[1]})")
    ok(vistos[2] == ["f3", "t3", "n3", "m3"], f"la última no lleva «Desliza» ({vistos[2]})")
    textos = {c["id"]: c.get("txt") for i in range(3) for c in C.capas_de_lamina(doc, i, f)}
    ok(textos["n2"] == "2/3" and textos["n3"] == "3/3", "{n}/{total} pone el número de cada lámina")
    ok(doc["laminas"][1]["capas"][2]["txt"] == "{n}/{total}", "sin tocar lo guardado")
    historia = C.limpiar_doc(carrusel("h916"))
    ids = [c["id"] for c in C.capas_de_lamina(historia, 1, G.formato("h916"))]
    ok("n2" not in ids and "d2" not in ids and "m2" in ids, "en historias no sale ni el número ni «Desliza» (la marca sí)")
    ids = [c["id"] for c in C.capas_de_lamina(C.limpiar_doc(carrusel("tt")), 1, G.formato("tt"))]
    ok("n2" not in ids and "d2" not in ids, "ni en TikTok foto")
    sola = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [{"capas": [_texto("a1", "Oferta {n} de {total}")]}]})
    ok(C.capas_de_lamina(sola, 0, f)[0]["txt"] == "Oferta {n} de {total}", "con una sola lámina, {n} y {total} se dejan tal cual")
    # en el HTML que va al navegador
    html, *_ = C.html_capas(doc, lamina=1)
    ok(">2/3<" in html and "{n}" not in html, "el número llega así al PNG")
    html, *_ = C.html_capas(doc, lamina=0)
    ok('data-c="n1"' not in html and 'data-c="d1"' not in html, "y lo que no va en la portada no se pinta")


def pieza_de_siempre_igual(pincel):
    print("una pieza de una lámina se pinta igual que antes de la rama")
    # lo mismo que hace prueba_graficas_capas con las 112 combinaciones, aquí
    # con una muestra: el HTML de una lámina sola no lleva nada nuevo
    for n in sorted(G._PL.PLANTILLAS)[:4]:
        for fid in ("v45", "h916"):
            doc = C.montar(pincel, n, fid, None, {"titulo": "Hola {n}", "marca": "Alba"})
            html, *_ = C.html_capas(doc)
            capas = doc["laminas"][0]["capas"]
            antes = "".join(C._html_capa(c, C.limpiar_doc(doc), None, G.colores_finales(None, doc), G.formato(fid),
                                         lambda _n: None, (None, None), set(), {}) for c in capas)
            ok(antes in html, f"plantilla {n} en {fid}: el cuerpo es el de siempre, con «{{n}}» tal cual")


# ================================================================ la pantalla

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const ctx = { window: {}, document: {}, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[process.argv.length - 1], 'utf8'), ctx);
const K = ctx.window.EditorCapas._cuentas;
const casos = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(casos.map(c => ({
  fuera: K.fueraDeLamina(c.capa, c.i, c.total, c.f),
  txt: K.textoDeLamina(c.capa, c.i, c.total),
}))));
"""


def pantalla_igual():
    print("la pantalla quita y numera lo mismo que el servidor")
    node = shutil.which("node")
    if not node:
        print("  (sin Node: esta parte se omite)")
        return
    casos, esperado = [], []
    for fid in ("v45", "c11", "h916", "tt", "h191"):
        f = G.formato(fid) if any(x["id"] == fid for x in G.FORMATOS) else None
        if not f:
            continue
        for total in (1, 2, 5):
            for i in range(total):
                for salvo in ([], ["primera"], ["ultima"], ["primera", "ultima"]):
                    for horiz in (False, True):
                        capa = _texto("a1", "Va {n} de {total} {n}", salvo=salvo, solo_horizontal=horiz)
                        limpia = C._limpiar_capa(capa, set())
                        doc = {"laminas": [{"capas": [limpia]}] * total}
                        sale = C.capas_de_lamina(doc, i, f)
                        casos.append({"capa": limpia, "i": i, "total": total, "f": {"W": f["W"], "H": f["H"]}})
                        esperado.append({"fuera": not sale, "txt": sale[0]["txt"] if sale else
                                         (limpia["txt"].replace("{n}", str(i + 1)).replace("{total}", str(total))
                                          if total > 1 else limpia["txt"])})
    r = subprocess.run([node, "-e", _NODE, EDITOR_JS], input=json.dumps(casos), capture_output=True, text=True, timeout=120)
    if r.returncode:
        ok(False, f"Node no ha podido correr las cuentas del editor: {r.stderr[-400:]}")
        return
    salida = json.loads(r.stdout)
    malos = [i for i, (a, b) in enumerate(zip(salida, esperado)) if a != b]
    ok(len(salida) == len(esperado) and not malos,
       f"{len(casos)} casos iguales en la pantalla y en el PNG" + (f" (caso {malos[0]}: {salida[malos[0]]} != {esperado[malos[0]]})" if malos else ""))


_NODE_TAPADO = r"""
const fs = require('fs'), vm = require('vm');
const ctx = { window: {}, document: {}, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[process.argv.length - 1], 'utf8'), ctx);
const K = ctx.window.EditorCapas._cuentas;
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0, 'utf8')).map(l => K.fondoTapado(l))));
"""


def fondo_tapado(pincel):
    """«Este fondo a todas» no toca una lámina cuyo fondo tapa otra capa (las
    portadas de plantilla llevan su propio fondo encima, prueba del 24-11). La
    verdad sale de pintar: si cambiar el color del fondo no cambia la imagen,
    está tapado."""
    print("«Este fondo a todas»: qué láminas tienen el fondo tapado")
    node = shutil.which("node")
    if not node:
        print("  (sin Node: esta parte se omite)")
        return
    import graficas_carrusel as K                           # noqa: PLC0415
    texto = "Titular de prueba\nY su apoyo\n\nUn punto\nCon su texto."
    laminas, verdad = [], []
    for n in range(1, 15):
        base = {"version": 2, "formato": "v45", "nombre": "x", "laminas": [{"capas": []}]}
        d, _ = K.carrusel_desde_texto(pincel, base, n, texto, "sustituir", None, None, None, "Alba")
        for i in (0, 1):
            antes = C.pintar(pincel, d, None, lambda _n: None, lamina=i)[0]
            otro = json.loads(json.dumps(d))
            otro["laminas"][i]["capas"][0]["relleno"] = {"color": "#00FF00", "alfa": 1}
            despues = C.pintar(pincel, otro, None, lambda _n: None, lamina=i)[0]
            laminas.append(d["laminas"][i])
            verdad.append(antes == despues)
    r = subprocess.run([node, "-e", _NODE_TAPADO, EDITOR_JS], input=json.dumps(laminas), capture_output=True,
                       text=True, timeout=120)
    if r.returncode:
        ok(False, f"Node no ha podido correr fondoTapado: {r.stderr[-400:]}")
        return
    dice = json.loads(r.stdout)
    malos = [(i // 2 + 1, "portada" if i % 2 == 0 else "dentro") for i, (a, b) in enumerate(zip(dice, verdad)) if a != b]
    ok(not malos, f"el editor sabe qué fondos tapa el diseño, igual que el PNG ({len(dice)} láminas; distintas: {malos})")
    ok(not any(dice[1::2]), "en las láminas de dentro de las 14 familias el fondo nunca está tapado")


# ================================================================ guardar

def guardar(carpeta):
    print("guardar un carrusel: solo lo que cambió, una carpeta por guardado")
    raiz = os.path.join(carpeta, "proyectos")
    os.makedirs(raiz, exist_ok=True)
    cid = "cafe"
    pasos = []
    doc = carrusel()
    r = C.guardar(raiz, cid, doc, None, avisar=lambda h, t: pasos.append((h, t)))
    pid, guardado = r["id"], r["doc"]["origen"]["guardado"]
    destino = G._carpeta_pieza(raiz, cid, pid)
    carpeta1 = C.carpeta_laminas(raiz, cid, pid, guardado)
    ok(sorted(os.listdir(carpeta1)) == ["01.jpg", "01.png", "02.jpg", "02.pdf.jpg", "02.png", "03.jpg", "03.png", "huellas.json"],
       "cada lámina en PNG y JPG, numeradas, en la carpeta de este guardado")
    ok(open(os.path.join(destino, "capas.png"), "rb").read() == open(os.path.join(carpeta1, "01.png"), "rb").read(),
       "capas.png es la lámina 1 (la lista, la miniatura y `main` la ven)")
    ok(pasos[0] == (0, 3) and pasos[-1] == (3, 3), f"avisa de cómo va ({pasos})")
    meta = G.meta_capas(raiz, cid, pid)
    ok(meta.get("laminas") == 3, "la ficha pequeña dice cuántas láminas hay")
    pieza = next(p for p in G.listar_piezas(raiz, cid) if p["id"] == pid)
    ok(pieza.get("laminas") == 3 and pieza.get("en_capas"), "y la lista también")
    ok(len(r["avisos_laminas"]) == 3, "con los avisos de cada lámina")
    pngs = [open(os.path.join(carpeta1, f"0{n}.png"), "rb").read() for n in (1, 2, 3)]
    ok(len(set(pngs)) == 3, "cada lámina es distinta (su número, su «Desliza»)")

    # otra vez, cambiando solo la lámina 2: se reutilizan las otras dos
    _ficha, leido = C.leer(raiz, cid, pid)
    leido["laminas"][1]["capas"][1]["txt"] = "Idea cambiada"
    leido["origen"]["envio"] = "abc123"
    pasos.clear()
    r2 = C.guardar(raiz, cid, leido, pid, avisar=lambda h, t: pasos.append((h, t)))
    ok(pasos[0] == (2, 3), f"solo vuelve a pintar la lámina que cambió ({pasos})")
    carpeta2 = C.carpeta_laminas(raiz, cid, pid, r2["doc"]["origen"]["guardado"])
    ok(not os.path.exists(carpeta1) and os.path.isdir(carpeta2), "la carpeta del guardado anterior se borra")
    ok(open(os.path.join(carpeta2, "01.png"), "rb").read() == pngs[0], "la lámina 1, igual que antes")
    ok(open(os.path.join(carpeta2, "02.png"), "rb").read() != pngs[1], "la 2, con el cambio")
    ok(G.meta_capas(raiz, cid, pid).get("envio") == "abc123", "el sello dice quién guardó (para no confundirlo con otra pestaña)")
    ok(C.leer(raiz, cid, pid)[1]["origen"].get("envio") == "abc123", "y el documento también")

    # una huella con otro pintor no se reutiliza
    viejo = C.PINTOR
    try:
        C.PINTOR = "otro"
        _f, leido = C.leer(raiz, cid, pid)
        pasos.clear()
        C.guardar(raiz, cid, leido, pid, avisar=lambda h, t: pasos.append((h, t)))
        ok(pasos[0] == (0, 3), "si cambia el pintor, se vuelve a pintar todo")
    finally:
        C.PINTOR = viejo

    # otra pestaña ya guardó: 409, sin escribir nada
    _f, viejo_doc = C.leer(raiz, cid, pid)
    C.guardar(raiz, cid, viejo_doc, pid)
    antes = sorted(os.listdir(destino))
    try:
        C.guardar(raiz, cid, viejo_doc, pid)
        ok(False, "guardar sobre lo de otra pestaña da conflicto")
    except C.ErrorConflicto:
        ok(sorted(os.listdir(destino)) == antes, "guardar sobre lo de otra pestaña da conflicto y no escribe nada")

    # volver a una lámina: las carpetas de láminas sobran
    _f, leido = C.leer(raiz, cid, pid)
    leido["laminas"] = leido["laminas"][:1]
    C.guardar(raiz, cid, leido, pid)
    ok(not [n for n in os.listdir(destino) if n.startswith("capas_")], "con una sola lámina no queda ninguna carpeta de láminas")
    ok("laminas" not in G.meta_capas(raiz, cid, pid), "ni el número de láminas en el sello")


def descargas(carpeta):
    print("descargar: ZIP, PDF de LinkedIn y una lámina suelta")
    import io                                               # noqa: PLC0415
    import zipfile                                          # noqa: PLC0415
    raiz = os.path.join(carpeta, "descargas")
    os.makedirs(raiz, exist_ok=True)
    cid = "cafe"
    doc = dict(carrusel(), nombre="Mi carrusel: 3 ideas ñandú")
    r = C.guardar(raiz, cid, doc, None)
    pid = r["id"]
    guardado = r["doc"]["origen"]["guardado"]
    carpeta1 = C.carpeta_laminas(raiz, cid, pid, guardado)
    ok(os.path.isfile(os.path.join(carpeta1, "02.pdf.jpg")), "la lámina con «Desliza →» tiene su versión para el PDF")
    ok(not os.path.exists(os.path.join(carpeta1, "03.pdf.jpg")), "la que no lo lleva, no (sale igual)")

    contenido, nombre = C.zip_laminas(raiz, cid, pid, "jpg")
    z = zipfile.ZipFile(io.BytesIO(contenido))
    ok(nombre == "mi-carrusel-3-ideas-nandu.zip", f"el ZIP se llama como la pieza, sin tildes ({nombre})")
    ok(z.namelist() == ["mi-carrusel-3-ideas-nandu-01.jpg", "mi-carrusel-3-ideas-nandu-02.jpg",
                        "mi-carrusel-3-ideas-nandu-03.jpg", "textos-alternativos.txt"],
       f"con las láminas en orden y los textos alternativos ({z.namelist()})")
    ok(z.read("mi-carrusel-3-ideas-nandu-02.jpg") == open(os.path.join(carpeta1, "02.jpg"), "rb").read(),
       "cada lámina tal cual se guardó")
    ok("Lámina 2: Lámina 2" in z.read("textos-alternativos.txt").decode(), "el texto alternativo de cada una")
    contenido, _ = C.zip_laminas(raiz, cid, pid, "png")
    ok(zipfile.ZipFile(io.BytesIO(contenido)).namelist()[0].endswith("-01.png"), "también en PNG")
    try:
        C.zip_laminas(raiz, cid, pid, "gif")
        ok(False, "un formato raro se rechaza")
    except C.ErrorGraficas:
        ok(True, "un formato raro se rechaza")

    sola, nombre = C.lamina_suelta(raiz, cid, pid, 3, "png")
    ok(sola == open(os.path.join(carpeta1, "03.png"), "rb").read() and nombre.endswith("-03.png"), "una lámina suelta, con su número")
    for malo in (0, 4, "2"):
        try:
            C.lamina_suelta(raiz, cid, pid, malo, "png")
            ok(False, f"la lámina {malo!r} no existe")
        except C.ErrorGraficas:
            ok(True, f"la lámina {malo!r} no existe")

    pdf, nombre = C.pdf_laminas(raiz, cid, pid)
    ok(nombre.endswith(".pdf") and pdf.startswith(b"%PDF-1.4"), "el PDF de LinkedIn")
    jpg2_pdf = open(os.path.join(carpeta1, "02.pdf.jpg"), "rb").read()
    ok(jpg2_pdf in pdf and open(os.path.join(carpeta1, "01.jpg"), "rb").read() in pdf,
       "lleva los JPG tal cual (sin volver a comprimir), y el de la 2 es el de sin «Desliza →»")
    ok(open(os.path.join(carpeta1, "02.jpg"), "rb").read() not in pdf, "no el de con «Desliza →»")
    try:
        import pypdf                                        # noqa: PLC0415
        lector = pypdf.PdfReader(io.BytesIO(pdf))
        ok(len(lector.pages) == 3, "con una página por lámina")
        ok(lector.metadata.title == "Mi carrusel: 3 ideas ñandú", f"y el título de la pieza, con tildes ({lector.metadata.title!r})")
        caja = lector.pages[0].mediabox
        ok(abs(float(caja.width) / float(caja.height) - 1080 / 1350) < 1e-3, "páginas con la forma de la lámina")
    except ImportError:
        print("  (sin pypdf: el PDF solo se comprueba por dentro)")

    # una pieza de una lámina descarga lo de siempre
    una = C.guardar(raiz, cid, dict(carrusel(), laminas=carrusel()["laminas"][:1]), None)
    contenido, _ = C.zip_laminas(raiz, cid, una["id"], "jpg")
    ok(len(zipfile.ZipFile(io.BytesIO(contenido)).namelist()) == 1, "una pieza de una lámina: un ZIP con una")

    # sin la carpeta (guardado desde main): la descarga no pinta, pide prepararlas
    import shutil as sh                                     # noqa: PLC0415
    sh.rmtree(carpeta1)
    try:
        C.zip_laminas(raiz, cid, pid, "jpg")
        ok(False, "sin las láminas pintadas, pide prepararlas")
    except C.ErrorSinLaminas as fallo:
        ok("Preparar las láminas" in str(fallo), "sin las láminas pintadas, pide prepararlas (y no pinta nada)")

    # la ficha pequeña la escribió main (sin «laminas»): sigue siendo un carrusel (árbitro del 24-11)
    # (main no borra la carpeta de láminas que había: aquí se borró arriba, vuelve vacía)
    os.makedirs(carpeta1)
    ruta_meta = os.path.join(G._carpeta_pieza(raiz, cid, pid), "capas.sello.json")
    meta = G._leer_json(ruta_meta)
    meta.pop("laminas", None)
    with open(ruta_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    de_la_lista = next(p for p in G.listar_piezas(raiz, cid) if p["id"] == pid)
    ok(de_la_lista.get("laminas") == 3, f"sin «laminas» en la ficha pequeña, se cuentan en capas.json ({de_la_lista.get('laminas')})")
    try:
        C.zip_laminas(raiz, cid, pid, "jpg")
        ok(False, "y la descarga pide preparar las láminas, no da solo la primera")
    except C.ErrorSinLaminas:
        ok(True, "y la descarga pide preparar las láminas, no da solo la primera")

    # el texto alternativo vacío sale de los textos de la lámina, de arriba abajo
    sin_alt = carrusel()
    for lam in sin_alt["laminas"]:
        lam.pop("alt")
    sin_alt["laminas"][1]["capas"].insert(1, _texto("arriba", "Primero esto.", y=2))
    sin_alt["laminas"][1]["capas"].append(_texto("deco1", "“", rol="deco"))
    limpio = C.limpiar_doc(sin_alt)
    alt = C.alt_de_textos(limpio, 1)
    ok(alt == "Primero esto. Idea 2", f"el texto alternativo vacío sale de sus textos, sin lo «en todas» ni adornos ({alt!r})")
    r2 = C.guardar(raiz, cid, sin_alt, None)
    contenido, _ = C.zip_laminas(raiz, cid, r2["id"], "jpg")
    txt = zipfile.ZipFile(io.BytesIO(contenido)).read("textos-alternativos.txt").decode()
    ok("Lámina 3: Idea 3" in txt, f"y va en el ZIP ({txt!r})")


# ================================================================ las familias

KITS = {
    "de siempre": None,
    "oscuro": {"colores": {"principal": "#0E7C66", "secundario": "#F2B705", "acento": "#E4572E", "oscuro": "#0B0B0F", "claro": "#FAFAF7"}},
    # el que más cuesta: principal y secundario casi iguales, acento flojo
    "poco contraste": {"colores": {"principal": "#7A6FF0", "secundario": "#8C83F2", "acento": "#C9C3FF", "oscuro": "#2B2A40", "claro": "#EEEDFB"}},
}

#: Lo que la pantalla mide de cada texto de una lámina: su caja de letras,
#: si se sale de su caja, su letra, su color y el del fondo que tiene debajo.
_MEDIR_LAMINA = r"""(() => {
  const W = innerWidth, H = innerHeight;
  const rgb = s => { const m = (s || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return { c: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }; };
  const fondoDe = (n, x, y) => {
    for (const e of document.elementsFromPoint(x, y)) {
      if (e === n || n.contains(e)) continue;
      const b = rgb(getComputedStyle(e).backgroundColor);
      if (b && b.a > 0.5) return b.c;
    }
    return null;
  };
  const textos = [], adornos = [];
  for (const n of document.querySelectorAll('[data-c]')) {
    const cs = getComputedStyle(n);
    if (n.tagName === 'DIV' && n.textContent.trim() && !n.querySelector('img')) {
      const r = document.createRange(); r.selectNodeContents(n);
      const b = r.getBoundingClientRect();
      const fs = parseFloat(cs.fontSize);
      const caja = { l: b.left, r: b.right, t: b.top + fs * 0.2, b: b.bottom - fs * 0.2 };
      const propio = rgb(cs.backgroundColor);
      textos.push({ id: n.dataset.c, rol: n.dataset.r, txt: n.textContent.trim().slice(0, 30), caja, fs,
        // se sale si las letras (sin su aire) pasan de su caja, o si no caben a lo ancho
        // (con una décima de la letra de margen: hay letras, como Anton, que dibujan por encima de su línea)
        sale: n.scrollWidth > n.clientWidth + 2 || caja.b > n.getBoundingClientRect().bottom + fs * 0.12 || caja.t < n.getBoundingClientRect().top - fs * 0.12,
        color: rgb(cs.color).c, fondo: propio && propio.a > 0.5 ? propio.c : fondoDe(n, (b.left + b.right) / 2, (b.top + b.bottom) / 2) });
    }
  }
  return { W, H, textos };
})()"""


def _lum(c):
    def k(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def _contraste(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def familias(pincel):
    print("las 14 familias: cada tipo, en cada tamaño y con 3 Kits")
    import graficas_carrusel as K                           # noqa: PLC0415
    cat = K.catalogo()
    ok(len(cat["familias"]) == 14 and [t["id"] for t in cat["tipos"]] == list(K.TIPOS), "14 familias y 8 tipos")
    combinaciones, malas = 0, []
    adornos_vistos = set()
    formatos = [("v45", list(KITS)), ("c11", ["de siempre"]), ("h916", ["de siempre"]), ("h19", ["de siempre"])]
    for fid, kits in formatos:
        f = G.formato(fid)
        horiz = f["W"] / f["H"] > 1.3
        m = K._Lienzo(K.familia(1), fid, G.COLORES_DEFECTO, "").m
        seguro = {"l": m["l"] / 100 * f["W"] - 1, "r": f["W"] - m["r"] / 100 * f["W"] + 1,
                  "t": m["t"] / 100 * f["H"] - 1, "b": f["H"] - m["b"] / 100 * f["H"] + 1}
        for kit_n in kits:
            kit = KITS[kit_n]
            for n in sorted(K.FAMILIAS):
                for tipo in K.TIPOS[1:]:
                    if horiz and tipo not in K.TIPOS_HORIZONTAL:
                        try:
                            K.lamina(n, tipo, fid, G.colores_finales(kit, {}), None, "Marca")
                            malas.append(f"{n}/{tipo}/{fid}: en horizontal debía decir que no cabe")
                        except C.ErrorGraficas:
                            pass
                        continue
                    colores = G.colores_finales(kit, {})
                    lam = K.lamina(n, tipo, fid, colores, None, "EstadoPlay")
                    lam["capas"] += [dict(c) for c in K.en_todas(K._Lienzo(K.familia(n), fid, colores, "EstadoPlay"))]
                    # el cierre se pinta como la ÚLTIMA lámina (lo «salvo última» no sale), el resto en medio
                    laminas = [{"capas": []}, lam] + ([] if tipo == "cierre" else [{"capas": []}])
                    doc = C.limpiar_doc({"version": 2, "formato": fid, "laminas": laminas})
                    documento, ff, margenes, faltan = C.html_capas(doc, kit, lambda _n: None, None, None, 1)
                    pincel.abrir(documento, ff["W"], ff["H"])
                    pincel.evaluar(C._AJUSTAR)
                    medida = pincel.evaluar(_MEDIR_LAMINA)
                    combinaciones += 1
                    adornos = [c for c in lam["capas"] if c["tipo"] == "forma" and c.get("nombre") in
                               ("Círculo", "Sello", "Franja", "Barra", "Filete")]
                    adornos_vistos |= {c["nombre"] for c in adornos}
                    etiqueta = f"{K.familia(n)['nombre']} · {tipo} · {fid} · Kit {kit_n}"
                    tx = medida["textos"]
                    minimo = K.LETRA_MINIMA / 100 * min(ff["W"], ff["H"]) * 0.95
                    for t in tx:
                        c = t["caja"]
                        if c["l"] < seguro["l"] or c["r"] > seguro["r"] or c["t"] < seguro["t"] or c["b"] > seguro["b"]:
                            malas.append(f"{etiqueta}: «{t['txt']}» se sale de lo útil")
                        if t.get("sale"):
                            malas.append(f"{etiqueta}: «{t['txt']}» no cabe en su caja")
                        if t["fs"] < minimo:
                            malas.append(f"{etiqueta}: «{t['txt']}» con letra de {t['fs']:.0f} px (mínimo {minimo:.0f})")
                        if t.get("fondo"):
                            grande = t["fs"] >= 0.05 * min(ff["W"], ff["H"]) or t["rol"] in ("numero", "cifra", "titulo", "cita")
                            if _contraste(t["color"], t["fondo"]) < (3 if grande else 4.5):
                                malas.append(f"{etiqueta}: «{t['txt']}» con poco contraste ({_contraste(t['color'], t['fondo']):.1f}:1)")
                        for a in adornos:
                            ax0, ay0 = a["x"] / 100 * ff["W"], a["y"] / 100 * ff["H"]
                            ax1, ay1 = ax0 + a["w"] / 100 * ff["W"], ay0 + a["h"] / 100 * ff["H"]
                            if a["nombre"] == "Franja" and t["rol"] == "en_desliza":
                                continue                  # el «Desliza» va sobre la franja, con su color
                            dx = min(c["r"], ax1) - max(c["l"], ax0)
                            dy = min(c["b"], ay1) - max(c["t"], ay0)
                            if dx > 3 and dy > 3 and (a["figura"] != "elipse" or _dentro_de_elipse(c, ax0, ay0, ax1, ay1)):
                                malas.append(f"{etiqueta}: «{t['txt']}» cruza el adorno «{a['nombre']}»")
                    for i in range(len(tx)):
                        for j in range(i + 1, len(tx)):
                            a, b = tx[i]["caja"], tx[j]["caja"]
                            dx = min(a["r"], b["r"]) - max(a["l"], b["l"])
                            dy = min(a["b"], b["b"]) - max(a["t"], b["t"])
                            if dx > 4 and dy > 4:
                                malas.append(f"{etiqueta}: «{tx[i]['txt']}» pisa a «{tx[j]['txt']}»")
    ok(combinaciones >= 500, f"{combinaciones} láminas pintadas y medidas")
    for mala in malas[:25]:
        print("   ", mala)
    ok(not malas, f"ningún texto se sale, pisa a otro, cruza un adorno, se lee mal ni baja de la letra mínima ({len(malas)} fallos)")
    ok(adornos_vistos >= {"Círculo", "Sello", "Franja", "Barra", "Filete"}, f"y se midieron todos los adornos ({sorted(adornos_vistos)})")


def _dentro_de_elipse(c, x0, y0, x1, y1):
    """¿Toca la caja `c` la elipse (no solo su recuadro)? Por el punto de la caja más cercano al centro."""
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    px, py = min(max(cx, c["l"]), c["r"]), min(max(cy, c["t"]), c["b"])
    return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 < 0.96


def partir_y_montar(pincel):
    print("partir un texto, montar por tipo y la nota del carrusel")
    import graficas_carrusel as K                           # noqa: PLC0415
    texto = ("5 errores al alquilar una consola\nY cómo evitarlos\n\n"
             "No probar los mandos\nPruébalos antes.\n\n"
             "Lo que no falta\n- Uno\n- Dos\n- Tres\n- Cuatro\n- Cinco\n- Seis\n- Siete\n\n"
             "8 de 10\nfiestas terminan tarde\n\n"
             "Otro punto\nCon su texto.")
    # prueba en el servidor del 24-11: con la familia 10 (sin texto de apoyo) el
    # apoyo de la portada se quedaba encima del botón «Desliza →»
    base = {"version": 2, "formato": "v45", "nombre": "x", "laminas": [{"capas": []}]}
    d1, _av = K.carrusel_desde_texto(pincel, base, 1, texto, "sustituir", None, None, None, "Alba")
    d10 = K.montar_todas(pincel, d1, 10, None, None, None, "Alba")
    apoyo = [c for c in d10["laminas"][0]["capas"] if c.get("rol") == "apoyo"]
    ok(len(apoyo) == 1 and apoyo[0].get("oculto") and apoyo[0]["txt"] == "Y cómo evitarlos",
       "una portada cuya familia no tiene sitio para el apoyo lo conserva, pero oculto (no pisa el botón)")
    d1b = K.montar_todas(pincel, d10, 1, None, None, None, "Alba")
    apoyo = [c for c in d1b["laminas"][0]["capas"] if c.get("rol") == "apoyo"]
    ok(len(apoyo) == 1 and not apoyo[0].get("oculto") and apoyo[0]["txt"] == "Y cómo evitarlos",
       "y al volver a una familia con sitio, sale otra vez (sin duplicarse)")
    nota10 = " ".join(a["texto"] for a in K.avisos_del_carrusel(d10))
    ok("texto(s) oculto(s)" in nota10 and "Y cómo evitarlos" in nota10, f"y la nota lo dice ({nota10[:120]})")
    # la Testimonio (9) lleva cita y autor: el titular y el apoyo pasan ahí, y vuelven
    def vistos(d):
        return {c["rol"]: c["txt"] for c in d["laminas"][0]["capas"] if c["tipo"] == "texto" and not c.get("oculto")}
    d9 = K.montar_todas(pincel, d1, 9, None, None, None, "Alba")
    ok(vistos(d9).get("cita") == "5 errores al alquilar una consola" and vistos(d9).get("autor") == "Y cómo evitarlos",
       f"de la familia 1 a la 9, el titular es la cita y el apoyo el autor ({vistos(d9)})")
    for c in d9["laminas"][0]["capas"]:
        if c.get("rol") == "cita":
            c["txt"] = "Mi cita cambiada"
    d9b = K.montar_todas(pincel, d9, 1, None, None, None, "Alba")
    ok(vistos(d9b).get("titulo") == "Mi cita cambiada" and vistos(d9b).get("apoyo") == "Y cómo evitarlos",
       f"y al volver, el titular es la cita (con lo que cambiaste) y el apoyo se ve ({vistos(d9b)})")
    ok(not any("oculto" in a["texto"] for a in K.avisos_del_carrusel(d9b)),
       "lo oculto que repite lo que se ve no se cuenta en la nota")
    d12 = K.montar_todas(pincel, d1, 12, None, None, None, "Alba")
    ok(vistos(d12).get("i1") == "No probar los mandos", f"la portada de Pasos (12) lleva los titulares que siguen ({vistos(d12).get('i1')!r})")
    _d, av = K.carrusel_desde_texto(pincel, base, 10, texto, "sustituir", None, None, None, "Alba")
    ok(any("no lleva texto de apoyo" in a for a in av), "partir con esa familia avisa de que el apoyo no sale")
    import re as _re                                        # noqa: PLC0415
    nota = " ".join(a["texto"] for a in K.avisos_del_carrusel(d1))
    m = _re.search(r"textos de muestra en la lámina ([\d, ]+)", nota)
    con_muestra = {int(x) for x in m.group(1).split(",")} if m else set()
    puntos = {i + 1 for i, lam in enumerate(d1["laminas"]) if lam.get("tipo") == "punto"}
    ok(not (con_muestra & puntos), f"los números de los puntos («01», «02») no cuentan como texto de muestra ({nota[:160]})")

    piezas, avisos = K.partir(texto)
    ok([p[0] for p in piezas] == ["portada", "punto", "lista", "lista", "dato", "punto", "cierre"],
       f"cada párrafo a su tipo, y al final el cierre ({[p[0] for p in piezas]})")
    ok(piezas[1][1]["numero"] == "01" and piezas[5][1]["numero"] == "02", "los puntos, numerados 01, 02…")
    ok(piezas[2][1]["v5"] == "Cinco" and piezas[3][1]["v1"] == "Seis" and "(sigue)" in piezas[3][1]["titulo"],
       "más de 5 viñetas se reparten en otra lámina")
    ok(any("7 viñetas" in a for a in avisos), "y lo avisa")
    ok(piezas[4][1]["cifra"] == "8 de 10", "«8 de 10» es un dato")
    ok(not K._es_cifra("Hola 1 2 3 4 5 6 7 8") and K._es_cifra("-20 %") and K._es_cifra("S/ 190"), "qué es una cifra corta")
    _p, av = K.partir("\n\n".join(f"Punto {i}\nTexto" for i in range(30)))
    ok(len(_p) == 20 and _p[-1][0] == "cierre" and any("caben 20" in a for a in av), "más de 20 láminas: se cortan, con el cierre, y se avisa")
    _p, av = K.partir("\n\n".join(["x" * 700] * 30))
    ok(len([a for a in av if "no caben" in a or "no cabe" in a]) == 1 and any("19 párrafos" in a for a in av),
       f"los párrafos que no caben se avisan una vez, y solo los que quedan ({av})")
    _p, av = K.partir("T" * 700 + "\n\nhola")
    ok(len(_p[0][1]["titulo"]) == C.MAX_TEXTO and any("Un párrafo no cabe" in a for a in av),
       "una portada demasiado larga también avisa")
    _p, av = K.partir("Título\n\n" + "\n".join("- " + "a" * 200 for _ in range(5)))
    ok(not av, f"una lista larga con viñetas que caben no avisa ({av})")
    _p, av = K.partir("Título\n\n" + "t" * 316 + "\n" + "x" * 400)
    ok(not av, f"un párrafo largo cuyo titular y texto caben por separado no avisa ({av})")
    try:
        K.partir("   ")
        ok(False, "un texto vacío se rechaza")
    except C.ErrorGraficas:
        ok(True, "un texto vacío se rechaza")

    base = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [{"capas": []}]})
    doc, _a = K.carrusel_desde_texto(pincel, base, 6, texto, "sustituir", None, None, None, "Alba")
    ok(len(doc["laminas"]) == 7 and doc["laminas"][0]["tipo"] == "portada" and doc["laminas"][0]["familia"] == 6,
       "«Partir» hace el carrusel con la portada de la plantilla de la familia")
    grupos = {c["enlace"] for lam in doc["laminas"] for c in lam["capas"] if c.get("enlace")}
    ok(len(grupos) == 3 and all(sum(1 for c in lam["capas"] if c.get("enlace")) == 3 for lam in doc["laminas"]),
       "con la marca, el número y «Desliza →» en todas (3 grupos)")
    num = next(c for c in doc["laminas"][1]["capas"] if c.get("rol") == "en_numero")
    ok(num["txt"] == "{n}/{total}" and num["salvo"] == ["primera"] and num.get("solo_horizontal"), "el número: no en la portada ni en historias")
    des = next(c for c in doc["laminas"][1]["capas"] if c.get("rol") == "en_desliza")
    ok(des["salvo"] == ["primera", "ultima", "pdf"], "«Desliza →»: ni en la portada, ni en la última, ni en el PDF")
    titulo = next(c for c in doc["laminas"][1]["capas"] if c.get("rol") == "titulo")
    ok(titulo["txt"] == "No probar los mandos", "el titular de cada punto, su primera línea")
    ids = [c["id"] for lam in doc["laminas"] for c in lam["capas"]]
    ok(len(ids) == len(set(ids)), "sin ids repetidos en todo el carrusel")

    # añadir
    doc2, _a = K.carrusel_desde_texto(pincel, doc, 6, "Nueva\nCon texto", "anadir", None, None, None, "Alba")
    ok(len(doc2["laminas"]) == 8 and doc2["laminas"][-2]["capas"][-1].get("enlace") and doc2["laminas"][-1]["tipo"] == "cierre",
       "«Añadir» las pone antes del cierre, con lo «en todas» de antes")
    # volver a montar con otra familia: textos y lo añadido se conservan
    lam = doc["laminas"][1]
    lam["capas"].append({"tipo": "forma", "id": "mia9", "rol": "", "nombre": "Mía", "x": 1, "y": 1, "w": 5, "h": 5})
    lam["capas"][-1]["relleno"] = {"color": "kit:acento"}
    lam["alt"] = "Mi texto alternativo"
    r = K.montar_lamina(pincel, doc, 1, 10, "punto", None, None, None, [1, 2], "Alba")
    nueva = r["laminas"][1]
    ok(nueva["familia"] == 10, "unos textos que no son una lista de campos se ignoran (no un error 500)")
    r = K.montar_lamina(pincel, doc, 1, 10, "punto", None, None, None, None, "Alba")
    nueva = r["laminas"][1]
    ok(nueva["familia"] == 10 and nueva["tipo"] == "punto", "«Volver a montar» con otra familia")
    ok(next(c for c in nueva["capas"] if c.get("rol") == "titulo")["txt"] == "No probar los mandos", "conserva los textos")
    ok(any(c["id"] == "mia9" for c in nueva["capas"]) and nueva.get("alt") == "Mi texto alternativo" and nueva.get("id") == lam.get("id"),
       "y lo añadido, el texto alternativo y el id de la lámina")
    en = [c for c in nueva["capas"] if c.get("rol") in K.ROLES_EN_TODAS]
    ok(len(en) == 3 and all(c.get("enlace") for c in en) and all(c["fuente"]["id"] == "poppins" for c in en),
       "lo «en todas» se queda en su grupo, con la letra de la familia nueva")
    cita = K.nueva_lamina(pincel, doc, 1, 6, "cita", None, None, None, "Alba")
    otra = K.montar_lamina(pincel, cita, 1, 10, "cita", None, None, None, None, "Alba")
    ok(sum(1 for c in otra["laminas"][1]["capas"] if c.get("nombre") == "Comillas") == 1,
       "volver a montar una cita no deja dos comillas (los adornos de la familia se rehacen)")
    lista = K.montar_lamina(pincel, K.nueva_lamina(pincel, doc, 1, 6, "lista", None, None, None, "Alba"), 1, 6, "lista",
                            None, None, None, None, "Alba")
    ok(sum(1 for c in lista["laminas"][1]["capas"] if c.get("nombre") == "Número 1") == 1, "ni dos números en una lista")
    r = K.montar_lamina(pincel, doc, 1, 6, "lista", None, None, None, None, "Alba")
    ok(next(c for c in r["laminas"][1]["capas"] if c.get("rol") == "titulo")["txt"] == "No probar los mandos",
       "cambiar de tipo lleva el titular a su sitio")
    todas = K.montar_todas(pincel, dict(doc, laminas=doc["laminas"] + [{"id": "blanca", "tipo": "blanco", "capas": [
        {"tipo": "forma", "id": "zz1", "x": 0, "y": 0, "w": 100, "h": 100}]}]), 14, None, None, None, "Alba")
    ok(all(lam.get("familia") == 14 for lam in todas["laminas"][:-1]), "«… y todas» monta todas con la familia nueva")
    ok(todas["laminas"][-1]["capas"][0]["id"] == "zz1", "menos las «En blanco»")
    portada = K.montar_lamina(pincel, doc, 0, 3, "portada", None, None, None, None, "Alba")["laminas"][0]
    ok(portada["tipo"] == "portada" and portada["familia"] == 3 and len([c for c in portada["capas"] if c.get("enlace")]) == 3,
       "la portada se vuelve a montar con su plantilla, sin perder lo «en todas»")
    nuevo = K.nueva_lamina(pincel, doc, 2, 6, "cita", None, None, None, "Alba")
    ok(len(nuevo["laminas"]) == 8 and nuevo["laminas"][2]["tipo"] == "cita" and
       len([c for c in nuevo["laminas"][2]["capas"] if c.get("enlace")]) == 3, "añadir una lámina de un tipo, con lo «en todas»")
    try:
        K.lamina(6, "nada", "v45", G.COLORES_DEFECTO)
        ok(False, "un tipo que no existe se rechaza")
    except C.ErrorGraficas:
        ok(True, "un tipo que no existe se rechaza")

    nota = K.avisos_del_carrusel(doc)
    textos = " ".join(n["texto"] for n in nota)
    ok(any(n["nivel"] == "bien" and "Portada corta" in n["texto"] for n in nota), "la nota: la portada corta, bien")
    ok("Siguen textos de muestra" in textos, "avisa de los textos de muestra que siguen (el cierre)")
    ok("Sin texto alternativo" in textos, "y de las láminas sin texto alternativo")
    ok(not any(n["nivel"] == "mal" and "láminas." in n["texto"] for n in nota), "el número de láminas nunca es rojo")
    doc["laminas"][1]["capas"] = [c for c in doc["laminas"][1]["capas"] if c.get("rol") != "titulo"]
    ok("lámina 2 no tiene titular" in " ".join(n["texto"] for n in K.avisos_del_carrusel(doc)), "la segunda portada: sin titular, avisa")


# ================================================================ por la API

def _arrancar(carpeta):
    import socket                                           # noqa: PLC0415
    import time                                             # noqa: PLC0415
    import requests                                         # noqa: PLC0415
    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        puerto = sonda.getsockname()[1]
    entorno = dict(os.environ, ESTUDIO_SIMULAR="1", PYTHONIOENCODING="utf-8")
    for var, nombre in (("ESTUDIO_PRESETS", "presets.json"), ("ESTUDIO_BANCO_PRESETS", "banco_presets"),
                        ("ESTUDIO_SECRETOS", "secretos"), ("ESTUDIO_RECETAS", "recetas.json"),
                        ("ESTUDIO_AJUSTES", "ajustes.json"), ("ESTUDIO_ESTADISTICAS", "estadisticas.json")):
        entorno[var] = os.path.join(carpeta, nombre)
    os.makedirs(entorno["ESTUDIO_SECRETOS"], exist_ok=True)
    proceso = subprocess.Popen([sys.executable, os.path.join(RAIZ, "app.py"), "--puerto", str(puerto), "--proyectos",
                                os.path.join(carpeta, "proyectos")], cwd=RAIZ, env=entorno,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            raise RuntimeError("el Studio no arranca")
        try:
            if requests.get(base + "/api/salud", timeout=2).status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el Studio no contesta")


def por_la_api(carpeta):
    print("guardar un carrusel por la API: un trabajo con barra")
    import time                                             # noqa: PLC0415
    import requests                                         # noqa: PLC0415
    os.makedirs(os.path.join(carpeta, "proyectos"), exist_ok=True)
    proceso, base = _arrancar(carpeta)
    try:
        r = requests.post(base + "/api/clientes", json={"nombre": "Carrusel"}, timeout=30)
        d = r.json()
        cid = d.get("id") or (d.get("cliente") or {}).get("id")
        ok(r.status_code in (200, 201) and cid, "un proyecto para probar")
        # una lámina: como siempre, en la misma petición
        una = dict(carrusel(), laminas=carrusel()["laminas"][:1])
        r = requests.post(base + f"/api/graficas/{cid}/capas", json={"doc": una}, timeout=60)
        ok(r.status_code == 201 and r.json().get("id"), "una pieza de una lámina se guarda como siempre (201)")
        # tres láminas: un trabajo
        r = requests.post(base + f"/api/graficas/{cid}/capas", json={"doc": carrusel()}, timeout=60)
        ok(r.status_code == 202 and r.json().get("trabajo") and r.json().get("total") == 3,
           f"un carrusel devuelve un trabajo al momento (202): {r.status_code}")
        tid = r.json().get("trabajo")
        vistas, estado = set(), {}
        limite = time.time() + 120
        while time.time() < limite:
            estado = requests.get(base + f"/api/graficas/{cid}/capas/trabajo/{tid}", timeout=30).json()
            vistas.add((estado.get("hechas"), estado.get("total")))
            if estado.get("estado") != "pintando":
                break
            time.sleep(0.2)
        ok(estado.get("estado") == "listo" and (estado.get("resultado") or {}).get("id"),
           f"el trabajo acaba con lo que devuelve un guardado ({estado.get('estado')}, {estado.get('error')})")
        ok((3, 3) in vistas, f"y dice cuántas láminas lleva ({sorted(vistas, key=str)})")
        pid = (estado.get("resultado") or {}).get("id")
        piezas = requests.get(base + f"/api/graficas/{cid}/piezas", timeout=30).json()["piezas"]
        ok(any(p["id"] == pid and p.get("laminas") == 3 for p in piezas), "la lista dice que tiene 3 láminas")
        # guardar otra vez con el documento de antes: el trabajo acaba en 409
        def esperar(t):
            fin = time.time() + 120
            while time.time() < fin:
                e = requests.get(base + f"/api/graficas/{cid}/capas/trabajo/{t}", timeout=30).json()
                if e.get("estado") != "pintando":
                    return e
                time.sleep(0.2)
            return {}
        doc = (estado.get("resultado") or {}).get("doc")
        r = requests.put(base + f"/api/graficas/{cid}/piezas/{pid}/capas", json={"doc": doc}, timeout=60)
        ok(esperar(r.json().get("trabajo")).get("estado") == "listo", "volver a guardar con lo último guardado vale")
        r = requests.put(base + f"/api/graficas/{cid}/piezas/{pid}/capas", json={"doc": doc}, timeout=60)
        e2 = esperar(r.json().get("trabajo"))
        ok(e2.get("estado") == "error" and e2.get("codigo") == 409, f"un guardado que pisaría a otro acaba en 409 ({e2})")
        r = requests.get(base + f"/api/graficas/{cid}/piezas/{pid}/laminas.zip?formato=png", timeout=60)
        ok(r.status_code == 200 and r.headers.get("content-type") == "application/zip"
           and "attachment" in r.headers.get("content-disposition", ""), "el ZIP se descarga por la API")
        r = requests.get(base + f"/api/graficas/{cid}/piezas/{pid}/laminas.pdf", timeout=60)
        ok(r.status_code == 200 and r.content.startswith(b"%PDF"), "el PDF también")
        r = requests.get(base + f"/api/graficas/{cid}/piezas/{pid}/lamina/2.jpg", timeout=60)
        ok(r.status_code == 200 and r.headers.get("content-type") == "image/jpeg", "y una lámina suelta")
        r = requests.get(base + f"/api/graficas/{cid}/piezas/{pid}/lamina/9.jpg", timeout=60)
        ok(r.status_code == 404, "una lámina que no hay: 404")
        # se borra la carpeta: 409 y «Preparar las láminas» la rehace
        import shutil as sh                                 # noqa: PLC0415
        destino = G._carpeta_pieza(os.path.join(carpeta, "proyectos"), cid, pid)
        for nombre in os.listdir(destino):
            if nombre.startswith("capas_"):
                sh.rmtree(os.path.join(destino, nombre))
        r = requests.get(base + f"/api/graficas/{cid}/piezas/{pid}/laminas.zip", timeout=60)
        ok(r.status_code == 409 and "Preparar" in r.text, "sin las láminas, la descarga dice que hay que prepararlas (409)")
        r = requests.post(base + f"/api/graficas/{cid}/piezas/{pid}/laminas/preparar", timeout=60)
        ok(r.status_code == 202 and esperar(r.json().get("trabajo")).get("estado") == "listo", "«Preparar las láminas» es un trabajo")
        r = requests.get(base + f"/api/graficas/{cid}/piezas/{pid}/laminas.zip", timeout=60)
        ok(r.status_code == 200, "y después se descarga")
        r = requests.get(base + f"/api/graficas/{cid}/capas/trabajo/nohayeso", timeout=30)
        ok(r.status_code == 404 and "Vuelve a pulsar" in r.text, "un trabajo que no existe dice que se vuelva a guardar")
        r = requests.get(base + f"/api/graficas/otro/capas/trabajo/{tid}", timeout=30)
        ok(r.status_code in (403, 404), "un trabajo solo se ve desde su proyecto")
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()


def main():
    formato_del_documento()
    capas_por_lamina()
    pantalla_igual()
    pincel = G.Pincel()
    try:
        pieza_de_siempre_igual(pincel)
        partir_y_montar(pincel)
        fondo_tapado(pincel)
        familias(pincel)
    finally:
        pincel.cerrar()
    carpeta = tempfile.mkdtemp(prefix="graficas_carrusel_")
    try:
        guardar(carpeta)
        descargas(carpeta)
        por_la_api(os.path.join(carpeta, "api"))
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

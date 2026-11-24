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

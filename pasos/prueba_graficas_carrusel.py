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
            _texto(f"d{i}", "Desliza →", enlace="des", salvo=["primera", "ultima"], solo_horizontal=True),
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


def main():
    formato_del_documento()
    capas_por_lamina()
    pantalla_igual()
    pincel = G.Pincel()
    try:
        pieza_de_siempre_igual(pincel)
    finally:
        pincel.cerrar()
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

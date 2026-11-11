"""Rama gv-sitios: en modo «guion», el reparto y los sitios salen de las LINEAS.

La prueba real del 09-11-2026 (ZV01, un video musical en modo «guion» con 19
lineas «Visual:» aprobadas): la voz era la letra de una cancion que hablaba de
escenario y pista; el catalogo se escribio leyendo esa voz, invento un
backstage y lo puso de sitio OBLIGATORIO en todos los planos, delante de la
linea. Las lineas pedian calle, azotea y auto. Y «el artista» no estaba en el
reparto: sin hoja, cada plano invento una cara.

Lo que se comprueba, sin pagar nada y sin llamar a Claude (su respuesta es una
fija):

  1] la instruccion del catalogo: con lineas las lleva y pide su sitio y su
     gente; sin lineas es la de siempre, byte a byte;
  2] la respuesta se limpia: un sitio que solo usan las lineas no se tira, una
     linea con un sitio inventado se queda sin sitio y lo dice;
  3] EL FALLO, reproducido: con el catalogo leido de la voz, el backstage va
     delante de cada linea y no sale nadie del reparto;
  4] EL ARREGLO: con el catalogo repartido desde las lineas, cada prompt EMPIEZA
     por su linea, ningun sitio contradice su linea y el artista sale en sus
     planos con su hoja;
  5] lo de antes no se mueve: un catalogo sin 'desde_lineas' (todos los videos
     ya hechos) da los mismos prompts, y en modo «voz» las lineas no cuentan.

    python pasos/prueba_gv_sitios.py
"""
import copy
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))
os.environ.setdefault("ESTUDIO_SIMULAR", "1")

from nucleo.estado import Estado  # noqa: E402
from nucleo.proyecto import Proyecto  # noqa: E402

import catalogo_visual as C  # noqa: E402
import medios  # noqa: E402
import p6_assets as P6  # noqa: E402

_fallos = []
_cuenta = [0]


def ok(condicion, texto):
    _cuenta[0] += 1
    if condicion:
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLO {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto} (sale {obtenido!r}, se esperaba {esperado!r})")


def seccion(titulo):
    print(f"\n[{titulo}]")


# ------------------------------------------------------------ el video de prueba
#
# LA VOZ HABLA DE UN ESCENARIO (es la letra) y LAS LINEAS NO: calle, azotea y
# auto, con «el artista» en varias. Es ZV01 en pequeño.
BLOQUES = [
    ("B001", "Subo al escenario y la pista se enciende, el publico grita mi nombre "
             "bajo los reflectores."),
    ("B002", "Detras del telon me espera el backstage, el DJ sube el volumen y la "
             "noche no termina."),
    ("B003", "Cuando se apagan las luces del escenario me quedo solo con mi cancion."),
]

LINEAS = [
    {"bloque": "B001", "visual": "El artista camina solo por una calle mojada de noche, "
                                 "con las manos en los bolsillos", "camara": "plano general"},
    {"bloque": "B001", "visual": "Primer plano del rostro serio del artista bajo una farola"},
    {"bloque": "B002", "visual": "El artista sentado en el borde de una azotea mirando la "
                                 "ciudad iluminada"},
    {"bloque": "B002", "visual": "Las luces de la ciudad desde la azotea, sin nadie en el plano"},
    {"bloque": "B003", "visual": "El artista al volante de un auto, la cara iluminada por el "
                                 "salpicadero", "camara": "plano medio"},
    {"bloque": "B003", "visual": "Las luces traseras del auto alejandose por la avenida"},
]

#: Lo que devolvio el catalogo LEYENDO LA VOZ (el de ZV01): un solo sitio, el
#: backstage, y nadie en el reparto que sea «el artista».
CATALOGO_DE_LA_VOZ = {
    "sets": {"pasillo_backstage": {
        "descripcion": "A long backstage corridor lit by work lamps, a bright stage "
                       "opening at the far end",
        "luz": "harsh stage spill light from the far end",
        "palabras": ["backstage", "escenario"], "rotulo": ""}},
    "reparto": {"publico": {"nombre": "El publico", "papel": "la gente del concierto",
                            "descripcion": "a crowd of young concert goers",
                            "palabras": ["publico"], "grupo": True}},
    "beats": [{"desde": "B001", "hasta": "B003", "set": "pasillo_backstage",
               "personajes": ["publico"], "tono": "tenso", "accion": "a concert night",
               "palabras": []}],
}

#: La respuesta FIJA de Claude con las lineas delante: tres sitios (los de las
#: lineas), el artista como UN personaje y cada linea con su sitio y su gente.
#: Trae a proposito un sitio que solo nombra la voz (sin ninguna linea ni
#: tramo), una linea con un sitio que no declaro y una linea que se le olvido.
RESPUESTA_DESDE_LINEAS = {
    "reparto": {"artista": {
        "nombre": "El artista", "papel": "el cantante del video",
        "descripcion": "a man in his late twenties, slim, short black hair, light "
                       "stubble, black hoodie and dark jeans",
        "palabras": ["el artista"], "grupo": False}},
    "sets": {
        "calle_mojada": {"descripcion": "a wet city street at night, puddles reflecting "
                                        "street lamps", "luz": "night, sodium street lamps",
                         "palabras": ["calle"], "rotulo": ""},
        "azotea": {"descripcion": "a flat rooftop over a lit city", "luz": "night, city glow",
                   "palabras": ["azotea"], "rotulo": ""},
        "interior_auto": {"descripcion": "the inside of a car at night",
                          "luz": "night, dashboard glow", "palabras": ["auto"], "rotulo": ""},
        "escenario": {"descripcion": "a concert stage", "luz": "stage lights",
                      "palabras": ["escenario"], "rotulo": ""},
    },
    "beats": [
        {"desde": "B001", "hasta": "B001", "set": "calle_mojada", "personajes": ["artista"],
         "tono": "tenso", "accion": "walking alone"},
        {"desde": "B002", "hasta": "B002", "set": "azotea", "personajes": ["artista"],
         "tono": "neutro", "accion": "on the rooftop"},
        {"desde": "B003", "hasta": "B003", "set": "interior_auto", "personajes": ["artista"],
         "tono": "triste", "accion": "driving"},
    ],
    "lineas": [
        {"id": "V001", "set": "calle_mojada", "personajes": ["artista"]},
        {"id": "V002", "set": "calle_mojada", "personajes": ["artista"]},
        {"id": "V003", "set": "azotea", "personajes": ["artista"]},
        {"id": "V004", "set": "azotea_inventada", "personajes": []},
        {"id": "V005", "set": "interior_auto", "personajes": ["artista", "nadie"]},
    ],
    "avisos": [],
}


def _guardar_falso(respuesta, apuntes):
    def falso(instruccion, modelo, esfuerzo, cwd, avance=None):
        apuntes.append(instruccion)
        return json.dumps(respuesta), {}
    return falso


def _proponer(lineas=None, respuesta=None, **extra):
    apuntes = []
    original = C._llamar_claude                                   # noqa: SLF001
    C._llamar_claude = _guardar_falso(respuesta or RESPUESTA_DESDE_LINEAS, apuntes)
    try:
        ficha = C.proponer([{"id": b, "texto": t} for b, t in BLOQUES],
                           brief={"titulo": "Video musical"}, lineas=lineas, **extra)
    finally:
        C._llamar_claude = original                               # noqa: SLF001
    return apuntes[0], ficha


def prueba_instruccion():
    seccion("1] la instruccion del catalogo")
    sin, _ = _proponer(None)
    con, _ = _proponer([dict(x, id=f"V{i + 1:03d}") for i, x in enumerate(LINEAS)])
    ok("LO QUE SE VE LO DICEN LAS LINEAS VISUALES" not in sin and '"lineas"' not in sin,
       "sin lineas, la instruccion no las nombra")
    ok(con.startswith(sin[:sin.index(C.ANCLA_GUION)]),
       "con lineas, todo lo de antes del guion es igual")
    ok("LO QUE SE VE LO DICEN LAS LINEAS VISUALES, NO LA VOZ" in con, "y lleva el bloque de las lineas")
    ok("V003 | B002 | - | El artista sentado en el borde de una azotea" in con,
       "cada linea con su id, su bloque, su camara y lo que se ve")
    ok(con.index("LINEAS VISUALES, EN ORDEN") < con.index(C.ANCLA_GUION),
       "las lineas van delante del guion")
    ok('"lineas": [' in con and con.index('"lineas": [') > con.index('"avisos"'),
       "y la salida pide 'lineas' detras de 'avisos'")
    igual(sin.replace("\n", "").count("GUION COMPLETO"), 1, "el guion entra una sola vez")
    con_espacio, _ = _proponer(LINEAS, espacio_fijo={"sitio": "Mi local",
                                                     "descripcion": "a small shop"})
    ok("LO QUE SE VE LO DICEN" not in con_espacio,
       "con espacio fijo las lineas no se usan (el sitio ya esta fijado)")
    vacio, ficha = _proponer([])
    igual(vacio, sin, "con una lista de lineas vacia, la instruccion de siempre")
    ok("desde_lineas" not in ficha and "lineas" not in ficha,
       "y el catalogo sin lineas no trae ninguna clave nueva (regla 1)")


def prueba_limpieza():
    seccion("2] lo que devuelve Claude, limpio")
    lineas = [dict(x, id=f"V{i + 1:03d}") for i, x in enumerate(LINEAS)]
    _, ficha = _proponer(lineas)
    ok(ficha.get("desde_lineas") is True, "el catalogo dice que se repartio desde las lineas")
    igual(sorted(ficha["reparto"]), ["artista"], "el artista es UN personaje del reparto")
    ok("escenario" not in ficha["sets"],
       "el escenario que solo nombraba la voz se ha quitado (nadie lo usa)")
    ok({"calle_mojada", "azotea", "interior_auto"} <= set(ficha["sets"]),
       "los sitios de las lineas se quedan")
    por_id = {x["id"]: x for x in ficha["lineas"]}
    igual(len(ficha["lineas"]), 6, "una entrada por linea, tambien la olvidada")
    igual(por_id["V001"]["set"], "calle_mojada", "V001 en la calle")
    igual(por_id["V004"]["set"], None, "V004 con un sitio inventado se queda sin sitio")
    igual(por_id["V005"]["personajes"], ["artista"], "V005: solo la gente del reparto")
    igual(por_id["V006"]["set"], None, "V006, olvidada: sin sitio")
    ok(por_id["V003"]["visual"].startswith("El artista sentado"), "cada entrada guarda su linea")
    avisos = " ".join(ficha["avisos"])
    ok("azotea_inventada" in avisos and "V006" in avisos and "nadie" in avisos,
       "y lo raro se dice en los avisos")


# ------------------------------------------------------------- el plan de p6

def _locucion():
    paso, reloj, bloques, sueltas = 1 / 2.4, 0.0, [], []
    for bid, texto in BLOQUES:
        inicio = reloj
        for cruda in texto.split():
            sueltas.append({"w": cruda, "s": round(reloj, 3), "e": round(reloj + paso * 0.85, 3)})
            reloj += paso
        bloques.append({"id": bid, "texto": texto, "narracion": texto,
                        "t_in": round(inicio, 3), "t_out": round(reloj - paso * 0.15, 3),
                        "palabras": len(texto.split())})
        reloj += 1.0
    total = round(reloj - 1.0, 3)
    return {"bloques": bloques, "palabras": sueltas, "duracion": total,
            "transcript": " ".join(t for _b, t in BLOQUES),
            "secciones": [{"id": "SB001", "bloques": [b for b, _t in BLOQUES],
                           "t_in": 0.0, "t_out": total}]}, total


def _proyecto(carpeta):
    proyecto = Proyecto.crear(carpeta, "Prueba gv-sitios")
    estado = Estado(proyecto)
    for paso in ("ingesta", "brief"):
        medios.escribir_json(os.path.join(proyecto.ruta_trabajo(paso), f"{paso}.json"), {})
        estado.set_params(paso, {"texto": "letra"} if paso == "ingesta" else {})
        estado.completar(paso, {})
    medios.escribir_json(os.path.join(proyecto.ruta_trabajo("guion"), "guion.json"),
                         {"guion": [{"id": b, "texto": t} for b, t in BLOQUES]})
    estado.set_params("guion", {"idioma": "es"})
    estado.completar("guion", {"guion": "guion.json"})
    meta, segundos = _locucion()
    medios.escribir_json(os.path.join(proyecto.ruta_trabajo("voz"), "audio_meta.json"), meta)
    estado.set_params("voz", {"voz": "prueba"})
    estado.completar("voz", {"meta": "audio_meta.json", "duracion": segundos})
    return proyecto


def _params(catalogo, modo="guion"):
    return {"calidad": "low", "min_s": 2.0, "max_s": 6.0, "semilla": 7,
            "imagenes": modo,
            "guion_visual": {"origen": "manual", "aprobado": True, "planos": copy.deepcopy(LINEAS)},
            "catalogo": copy.deepcopy(catalogo),
            "estilo": {"prompt": "flat vector illustration", "referencias": []}}


def _planos(proyecto, params):
    plan = P6.planificar(proyecto, params)
    return [e for e in plan["escenas"] if e.get("prompt")]


def prueba_el_fallo_y_el_arreglo(proyecto):
    seccion("3] EL FALLO: el catalogo leido de la voz")
    viejos = _planos(proyecto, _params(CATALOGO_DE_LA_VOZ))
    igual(len(viejos), len(LINEAS), "un plano por linea")
    ok(all(e["prompt"].startswith("A long backstage corridor") for e in viejos),
       "como en ZV01: el backstage va DELANTE de cada linea")
    ok(not any(e.get("personajes") for e in viejos),
       "y no sale nadie del reparto (ninguna hoja para el artista)")
    ok(not any(e.get("linea_manda") for e in viejos),
       "un catalogo de antes no se reparte por lineas (los videos hechos no cambian)")

    seccion("4] EL ARREGLO: el catalogo repartido desde las lineas")
    lineas = [dict(x, id=f"V{i + 1:03d}") for i, x in enumerate(LINEAS)]
    _, propuesta = _proponer(lineas)
    catalogo = {k: propuesta[k] for k in ("reparto", "sets", "beats", "lineas", "desde_lineas")}
    nuevos = _planos(proyecto, _params(catalogo))
    igual(len(nuevos), len(LINEAS), "un plano por linea")
    for escena, linea in zip(nuevos, LINEAS):
        ok(escena["prompt"].startswith(linea["visual"]),
           f"{escena['id']}: el prompt EMPIEZA por su linea")
    ok(not any("backstage" in e["prompt"].lower() or "concert stage" in e["prompt"].lower()
               for e in nuevos), "ningun prompt lleva el backstage ni el escenario")
    sitio_de = {"calle": "calle_mojada", "farola": "calle_mojada", "azotea": "azotea",
                "volante": "interior_auto"}
    for i, (escena, linea) in enumerate(zip(nuevos, LINEAS)):
        if i == 3:
            continue      # V004: Claude le dio un sitio inventado (se mira abajo)
        palabra = next((p for p in sitio_de if p in linea["visual"].lower()), None)
        if palabra:
            igual(escena.get("set"), sitio_de[palabra],
                  f"{escena['id']}: su sitio encaja con su linea ({palabra})")
    igual(nuevos[3].get("set"), None, "la linea con el sitio inventado va sin sitio")
    ok("Where it happens" not in nuevos[3]["prompt"], "y su prompt no nombra ningun sitio")
    con_artista = [e for e, l in zip(nuevos, LINEAS) if "artista" in l["visual"].lower()]
    ok(con_artista and all(e.get("personajes") == ["artista"] for e in con_artista),
       f"el artista sale en sus {len(con_artista)} planos (con su hoja: es del reparto)")
    ok(all("'artista'" in e["prompt"] or "artista" in e["prompt"] for e in con_artista),
       "y su prompt lo cita por su hoja")
    igual(nuevos[0].get("luz"), "night, sodium street lamps", "la luz es la del sitio de su linea")
    ok(not any(e.get("luz") == "harsh stage spill light from the far end" for e in nuevos),
       "ninguna luz de escenario")
    return catalogo


def prueba_lo_de_antes(proyecto, catalogo_nuevo):
    seccion("5] lo de antes no se mueve")
    sin_marca = {k: v for k, v in catalogo_nuevo.items() if k not in ("lineas", "desde_lineas")}
    a = [e["prompt"] for e in _planos(proyecto, _params(sin_marca))]
    b = [e["prompt"] for e in _planos(proyecto, _params(dict(sin_marca, lineas=[])))]
    igual(a, b, "sin 'desde_lineas', los prompts son los de siempre")
    ok(not any(p.startswith(LINEAS[0]["visual"]) for p in a[:1]),
       "y el sitio va delante como antes (nada se reordena en un video hecho)")
    voz_con = [e["prompt"] for e in _planos(proyecto, _params(catalogo_nuevo, modo="voz"))]
    voz_sin = [e["prompt"] for e in _planos(proyecto, _params(sin_marca, modo="voz"))]
    igual(voz_con, voz_sin, "en modo voz, las lineas del catalogo no cambian ningun prompt")


def prueba_el_servidor():
    seccion("6] el servidor: el aviso, «desde las líneas» y guardar")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    base = tempfile.mkdtemp(prefix="estudio_gvs_")
    servidor.fijar_raiz_proyectos(base)
    bloques = [{"id": b, "texto": t} for b, t in BLOQUES]
    real_bloques, real_catalogo = servidor._bloques_del_guion, servidor._correr_catalogo
    servidor._bloques_del_guion = lambda _ctx: bloques
    pedidas = []

    def catalogo_falso(avisar, ctx, ajuste, peticion):
        pedidas.append(servidor._lineas_para_catalogo(ctx, bloques))
        _, ficha = _proponer([dict(x, id=f"V{i + 1:03d}") for i, x in enumerate(LINEAS)])
        return ficha
    servidor._correr_catalogo = catalogo_falso
    try:
        pid = Proyecto.crear(base, "zv01").id
        Estado(servidor.contexto(pid).proyecto)
        ctx = servidor.contexto(pid)
        viejo = dict(copy.deepcopy(CATALOGO_DE_LA_VOZ), reales=[],
                     _firma_guion=servidor._firma_del_guion(ctx))
        ctx.estado.actualizar_params("assets", {
            "imagenes": "guion", "catalogo": viejo,
            "guion_visual": {"origen": "manual", "aprobado": True, "planos": copy.deepcopy(LINEAS)}})
        params = ctx.estado.params("assets")
        aviso = servidor._sitios_y_lineas(ctx, params, params["catalogo"])
        ok(aviso.get("de_la_voz") is True and aviso.get("lineas") == 6,
           "un reparto leído de la voz en modo guion se avisa antes de generar")
        ctx.estado.actualizar_params("assets", {"imagenes": "voz"})
        params = ctx.estado.params("assets")
        igual(servidor._sitios_y_lineas(ctx, params, params["catalogo"]), {},
              "en modo voz no hay nada que avisar")
        igual(servidor._lineas_para_catalogo(ctx, bloques), None, "ni lineas que pasar al catalogo")
        ctx.estado.actualizar_params("assets", {"imagenes": "guion"})
        servidor._correr_escenarios(lambda *a, **k: None, ctx, {}, "", True)
        ok(not pedidas, "«rehacer» con el guion igual NO vuelve a repartir (como siempre)")
        servidor._correr_escenarios(lambda *a, **k: None, ctx, {}, "", True, desde_lineas=True)
        igual(len(pedidas), 1, "«desde las líneas» sí vuelve a repartir")
        igual([x["visual"] for x in (pedidas[0] or [])], [x["visual"] for x in LINEAS],
              "y le pasa al catálogo las líneas del vídeo")
        guardado = (ctx.estado.params("assets") or {}).get("catalogo") or {}
        ok(guardado.get("desde_lineas") is True and len(guardado.get("lineas") or []) == 6,
           "el catálogo guardado trae el sitio y la gente de cada línea")
        params = ctx.estado.params("assets")
        igual(servidor._sitios_y_lineas(ctx, params, guardado).get("nuevas"), [],
              "y ya no hay nada que avisar")
        sin_marca = {k: v for k, v in guardado.items() if k not in ("lineas", "desde_lineas")}
        servidor.guardar_catalogo(pid, {"catalogo": sin_marca})
        guardado = (ctx.estado.params("assets") or {}).get("catalogo") or {}
        ok(guardado.get("desde_lineas") is True and guardado.get("lineas"),
           "corregir el reparto a mano (PUT /catalogo) conserva lo de cada línea")
        mas = copy.deepcopy(LINEAS) + [{"bloque": "B003", "visual": "Una línea nueva"}]
        ctx.estado.actualizar_params("assets", {
            "guion_visual": {"origen": "manual", "aprobado": True, "planos": mas}})
        params = ctx.estado.params("assets")
        igual(servidor._sitios_y_lineas(ctx, params, guardado).get("nuevas"), ["V007"],
              "una línea añadida después de repartir se avisa")
    finally:
        servidor._bloques_del_guion, servidor._correr_catalogo = real_bloques, real_catalogo
        shutil.rmtree(base, ignore_errors=True)


def main():
    carpeta = tempfile.mkdtemp(prefix="gv_sitios_")
    try:
        prueba_instruccion()
        prueba_limpieza()
        proyecto = _proyecto(os.path.join(carpeta, "video"))
        catalogo = prueba_el_fallo_y_el_arreglo(proyecto)
        prueba_lo_de_antes(proyecto, catalogo)
        prueba_el_servidor()
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print()
    if _fallos:
        print(f"GV SITIOS: FALLAN {len(_fallos)} de {_cuenta[0]} comprobaciones")
        for texto in _fallos:
            print(f"  - {texto}")
        return 1
    print(f"GV SITIOS OK: {_cuenta[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

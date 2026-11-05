"""
DIAGRAMAS POR CONTENIDO (rama diagramas-por-contenido, 28-10-2026).

Lo que se comprueba:

  1. EL AJUSTE: los cuatro modos, sus alias, y que el del vídeo manda sobre el
     del estilo. Un valor raro guardado a mano se lee como sin ajuste.
  2. SIN AJUSTE, TODO IGUAL (regla 1): el criterio del catálogo, lo que
     devuelve el catálogo, el reparto de cartas y las cartas de p6, byte a byte.
  3. LOS TRAMOS QUE EXPLICAN se validan contra los bloques del guion.
  4. LOS GRÁFICOS: solo si cada cifra está escrita en el guion (con dígitos o
     con letras); con una que no está, el gráfico entero fuera. Y un tope.
  5. LAS CARTAS: el «diagrama» deja de salir por sorteo y sale en los tramos
     que explican, con su tope (1 de cada 8 / 1 de cada 4); lo forzado a mano,
     las cartelas, los componentes y las líneas del guion visual con cámara no
     se tocan. Las demás cartas, las de siempre. En foto no cambia nada.
  6. EL MOTOR dibuja los cuatro gráficos, con las barras a escala.
  7. EL PRESET de Estilo guarda `diagramas`, lo lleva y lo quita.

En memoria, sin el CLI y sin pagar nada.

    python pasos/prueba_diagramas.py
"""
import copy
import json
import os
import sys
import tempfile
import xml.dom.minidom

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

# las estadísticas de esta prueba, en un fichero suyo
os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(
    tempfile.mkdtemp(prefix="diagramas_"), "estadisticas.jsonl")

import diagramas as DG  # noqa: E402
import encuadres as E  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"      FALLO: {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}\n             esperado {esperado!r}\n             obtenido {obtenido!r}")


def seccion(titulo):
    print(f"\n{titulo}")


def _motor_grafico():
    import importlib.util                                         # noqa: PLC0415
    ruta = os.path.join(RAIZ, "motores", "capa_vectorial", "grafico.py")
    spec = importlib.util.spec_from_file_location("grafico_prueba", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


BLOQUES = [
    {"id": "B001", "texto": "Bienvenidos a la sala de juegos del barrio."},
    {"id": "B002", "texto": "Una hora de PS5 cuesta 12 soles y una de simulador, 25 soles."},
    {"id": "B003", "texto": "El treinta y cinco por ciento de los clientes reserva por WhatsApp."},
    {"id": "B004", "texto": "Primero eliges la consola, luego la hora y al final pagas."},
    {"id": "B005", "texto": "Y si vienes en grupo, el precio baja."},
    {"id": "B006", "texto": "Te esperamos este sábado."},
]
GUION = "\n".join(b["texto"] for b in BLOQUES)
IDS = [b["id"] for b in BLOQUES]

GRAFICO_BUENO = {
    "tipo": "grafico", "palabras": ["12 soles", "25 soles"],
    "config": {"clase": "barras", "titulo": "Precio por hora", "unidad": "S/",
               "datos": [{"etiqueta": "PS5", "valor": 12,
                          "cita": "Una hora de PS5 cuesta 12 soles"},
                         {"etiqueta": "Simulador", "valor": 25,
                          "cita": "una de simulador, 25 soles"}]}}
GRAFICO_EN_LETRAS = {
    "tipo": "grafico", "palabras": ["por ciento"],
    "config": {"clase": "proporcion", "titulo": "Reservan por WhatsApp",
               "datos": [{"etiqueta": "de los clientes", "valor": 35,
                          "cita": "El treinta y cinco por ciento de los clientes"}]}}
GRAFICO_INVENTADO = {
    "tipo": "grafico", "palabras": ["grupo"],
    "config": {"clase": "comparacion", "titulo": "Grupo",
               "datos": [{"etiqueta": "Solo", "valor": 12, "cita": "cuesta 12 soles"},
                         {"etiqueta": "Grupo", "valor": 9, "cita": "el precio baja"}]}}

RESPUESTA = {
    "reparto": {"dueno": {"nombre": "Dueño", "descripcion": "a young owner",
                          "palabras": ["bienvenidos"]}},
    "sets": {"sala": {"descripcion": "a game room", "palabras": ["sala"], "luz": "night"}},
    "beats": [{"desde": "B001", "hasta": "B006", "set": "sala",
               "personajes": ["dueno"], "accion": "people play"}],
    "componentes": {"grafico_precios": GRAFICO_BUENO},
    "explicativos": [{"desde": "B002", "hasta": "B003", "clase": "comparacion",
                      "que": "prices compared"},
                     {"desde": "B004", "clase": "paso_a_paso", "que": "booking steps"}],
}


# ---------------------------------------------------------------------------
def prueba_el_ajuste():
    seccion("1] el ajuste")
    igual(DG.MODOS, ("ninguna", "solo_si_lo_pide", "equilibrada", "didactica"),
          "cuatro modos, en orden")
    for crudo, esperado in ((None, ""), ("", ""), ("Equilibrado", "equilibrada"),
                            ("didáctico", "didactica"), ("solo si lo pide", "solo_si_lo_pide"),
                            ("ninguno", "ninguna"), ("solo_si_lo_pide", "solo_si_lo_pide")):
        igual(DG.normalizar(crudo), esperado, f"«{crudo}» se lee {esperado or 'sin ajuste'}")
    for malo in ("muchos", 3):
        try:
            DG.normalizar(malo)
            ok(False, f"«{malo}» tendría que dar ValueError")
        except ValueError:
            ok(True, f"«{malo}» no es un ajuste: ValueError")
    igual(DG.modo_de({}), "", "sin nada, sin ajuste")
    igual(DG.modo_de({"estilo": {"diagramas": "didactica"}}), "didactica", "el del estilo")
    igual(DG.modo_de({"diagramas": "ninguna", "estilo": {"diagramas": "didactica"}}),
          "ninguna", "el del vídeo manda sobre el del estilo")
    igual(DG.modo_de({"diagramas": "raro", "estilo": {}}), "",
          "un valor raro guardado a mano se lee como sin ajuste")
    igual([o["id"] for o in DG.opciones()], list(DG.MODOS), "las opciones del selector")


def prueba_sin_ajuste_igual():
    seccion("2] sin ajuste, todo igual (regla 1)")
    import catalogo_visual as C                                   # noqa: PLC0415
    criterio = C._criterio(40, 4, 8)                              # noqa: SLF001
    ok(DG.con_tramo(criterio, "") is criterio, "el criterio sin ajuste es el MISMO texto")
    igual(DG.con_tramo(criterio, "ninguna"), criterio, "con «ninguna», también")
    con = DG.con_tramo(criterio, "equilibrada")
    ok("DIAGRAMAS —" in con and con.index("DIAGRAMAS —") > con.index("COMPONENTES —")
       and con.index("DIAGRAMAS —") < con.index("LUGARES —"),
       "con ajuste, su tramo va tras COMPONENTES y antes de LUGARES")
    corte = criterio.index(DG.ANCLA)
    ok(con.startswith(criterio[:corte].rstrip("\n")) and con.endswith(criterio[corte:]),
       "y el resto del criterio no se mueve")

    antes = C._limpiar(copy.deepcopy(RESPUESTA), IDS)             # noqa: SLF001
    despues = C._limpiar(copy.deepcopy(RESPUESTA), IDS, diagramas="", guion=GUION)  # noqa: SLF001
    igual(json.dumps(despues, sort_keys=True), json.dumps(antes, sort_keys=True),
          "lo que devuelve el catálogo sin ajuste, byte a byte")
    ok("explicativos" not in antes and "diagramas" not in antes,
       "sin una clave de más")
    igual(antes["componentes"], {}, "y el gráfico con cifras, sin ajuste, fuera como siempre")

    pedidas = []

    def falso(instruccion, *_a, **_k):
        pedidas.append(instruccion)
        return json.dumps(RESPUESTA), {}
    original = C._llamar_claude                                   # noqa: SLF001
    C._llamar_claude = falso                                      # noqa: SLF001
    try:
        sin = C.proponer(BLOQUES, planos=6, min_s=4, max_s=8)
        vacio = C.proponer(BLOQUES, planos=6, min_s=4, max_s=8, diagramas="")
        con = C.proponer(BLOQUES, planos=6, min_s=4, max_s=8, diagramas="didactica")
    finally:
        C._llamar_claude = original                               # noqa: SLF001
    igual(pedidas[1], pedidas[0], "lo que se le pide a Claude sin ajuste, idéntico")
    ok("DIAGRAMAS —" not in pedidas[0] and "DIAGRAMAS —" in pedidas[2],
       "y con ajuste lleva su tramo")
    quitar = ("segundos",)
    igual({k: v for k, v in vacio.items() if k not in quitar},
          {k: v for k, v in sin.items() if k not in quitar},
          "y el catálogo que devuelve, el mismo")
    ok("explicativos" not in sin and len(con.get("explicativos") or []) == 2
       and "grafico_precios" in con["componentes"],
       "con ajuste trae sus tramos y su gráfico")

    escenas = [{"id": f"S{i:03d}"} for i in range(1, 61)]
    base = E.repartir(escenas, semilla=7)
    igual(E.sin_arrastrar(escenas, base, semilla=7), base, "retocar sin nada que quitar ni poner, igual")

    import p6_assets as P6                                        # noqa: PLC0415
    for estilo in ({}, {"modo": "foto"}):
        p = {"semilla": 3, "estilo": dict(estilo), "catalogo": {}}
        a = [dict(e) for e in escenas]
        b = [dict(e) for e in escenas]
        P6._asignar_cartas(a, p)                                   # noqa: SLF001
        p2 = dict(p, estilo=dict(estilo, diagramas=""))
        P6._asignar_cartas(b, p2)                                  # noqa: SLF001
        igual(a, b, f"las cartas de p6 sin ajuste ({estilo.get('modo') or 'ilustración'})")


def prueba_explicativos():
    seccion("3] los tramos que explican")
    avisos = []
    tramos = DG.limpiar_explicativos(
        [{"desde": "B003", "hasta": "B002", "clase": "Comparación", "que": "x"},
         {"desde": "B009", "clase": "medida"},
         {"desde": "B005", "hasta": "B099", "clase": "inventada"},
         "no es un dict"], IDS, avisos, "equilibrada")
    igual([(t["desde"], t["hasta"], t["clase"]) for t in tramos],
          [("B002", "B003", "comparacion"), ("B005", "B005", "proceso")],
          "al revés se da la vuelta; un final que no existe se queda en el inicio; "
          "una clase rara es «proceso»")
    igual(tramos[0]["bloques"], ["B002", "B003"], "con sus bloques expandidos")
    ok(any("B009" in a for a in avisos), "el bloque que no existe se dice")
    igual(DG.limpiar_explicativos(RESPUESTA["explicativos"], IDS, [], "ninguna"), [],
          "con «ninguna», ninguno")
    import catalogo_visual as C                                   # noqa: PLC0415
    ficha = C._limpiar(copy.deepcopy(RESPUESTA), IDS, diagramas="equilibrada",  # noqa: SLF001
                       guion=GUION)
    igual(len(ficha["explicativos"]), 2, "el catálogo con ajuste trae sus tramos")
    igual(ficha["diagramas"], "equilibrada", "y con qué ajuste se dedujeron")


def prueba_graficos():
    seccion("4] los gráficos: cada cifra, en el guion")
    avisos = []
    bueno = DG.limpiar_grafico("grafico_precios", GRAFICO_BUENO, GUION, avisos)
    ok(bueno is not None and bueno["config"]["clase"] == "barras",
       "cifras con dígitos que están en el guion: vale")
    letras = DG.limpiar_grafico("g2", GRAFICO_EN_LETRAS, GUION, avisos)
    ok(letras is not None, "«treinta y cinco por ciento» vale por 35")
    igual(DG.limpiar_grafico("g3", GRAFICO_INVENTADO, GUION, avisos), None,
          "una cifra que no está en el guion tumba el gráfico entero")
    ok(any("9" in a and "no esta escrita" in a for a in avisos), "y se dice cuál")
    malo = copy.deepcopy(GRAFICO_BUENO)
    malo["config"]["datos"][0]["cita"] = "una hora cuesta 12 soles en el centro"
    igual(DG.limpiar_grafico("g4", malo, GUION, []), None,
          "una cita que no está tal cual en el guion, fuera")
    for clase, datos in (("proporcion", GRAFICO_BUENO["config"]["datos"]),
                         ("nube", GRAFICO_BUENO["config"]["datos"])):
        raro = copy.deepcopy(GRAFICO_BUENO)
        raro["config"]["clase"] = clase
        raro["config"]["datos"] = datos
        igual(DG.limpiar_grafico("g5", raro, GUION, []), None,
              f"«{clase}» con {len(datos)} datos, fuera")
    for texto, valor, sale in (("veinte por ciento de", 100, False),
                               ("una casa en la playa", 1, False),
                               ("la media de edad", 0.5, False),
                               ("son dos tres veces", 5, False),
                               ("cuesta 1.500 soles", 1, False),
                               ("un millón de personas", 1000000, True),
                               ("doscientos treinta y cuatro metros", 234, True),
                               ("cuesta 1.500 soles", 1500, True),
                               ("sube un 2,5 % al año", 2.5, True),
                               ("dos mil personas", 2000, True),
                               ("en 2024 abrimos 3 tiendas", 3, True),
                               ("cuesta 1.500 soles", 15, False)):
        igual(DG.cifra_en_guion(valor, texto, DG.para_buscar(texto)), sale,
              f"{valor:g} en «{texto}»: {'sí' if sale else 'no'}")

    import catalogo_visual as C                                   # noqa: PLC0415
    crudo = copy.deepcopy(RESPUESTA)
    crudo["componentes"] = {"grafico_precios": GRAFICO_BUENO, "g2": GRAFICO_EN_LETRAS,
                            "g3": GRAFICO_INVENTADO}
    ficha = C._limpiar(crudo, IDS, diagramas="equilibrada", guion=GUION)  # noqa: SLF001
    igual(sorted(ficha["componentes"]), ["g2", "grafico_precios"],
          "el catálogo con ajuste se queda con los dos que valen")
    ficha = C._limpiar(copy.deepcopy(crudo), IDS, diagramas="ninguna", guion=GUION)  # noqa: SLF001
    igual(ficha["componentes"], {}, "con «ninguna», ningún gráfico")
    muchos = {f"g{i}": GRAFICO_BUENO for i in range(6)}
    igual(len(DG.recortar_graficos(muchos, "equilibrada", [])), DG.MAX_GRAFICOS["equilibrada"],
          "como mucho tres en «equilibrada»")
    mapa = {"tipo": "mapa", "config": {"region": "america"}}
    igual(len(DG.recortar_graficos(dict(muchos, mapa_ruta=mapa), "equilibrada", [])),
          DG.MAX_GRAFICOS["equilibrada"] + 1, "y los mapas no cuentan")


def prueba_solo_los_diagramas():
    seccion("4b] en un vídeo ya repartido: solo los diagramas, sin tocar los sitios")
    import catalogo_visual as C                                   # noqa: PLC0415
    pedidas = []

    def falso(instruccion, *_a, **_k):
        pedidas.append(instruccion)
        return json.dumps({"explicativos": RESPUESTA["explicativos"],
                           "componentes": {"grafico_precios": GRAFICO_BUENO,
                                           "g3": GRAFICO_INVENTADO,
                                           "mapa_ruta": {"tipo": "mapa", "config": {}}},
                           "sets": {"otro": {}}}), {}
    original = C._llamar_claude                                   # noqa: SLF001
    C._llamar_claude = falso                                      # noqa: SLF001
    try:
        ficha = C.proponer_diagramas(BLOQUES, "Equilibrado")
        try:
            C.proponer_diagramas(BLOQUES, "ninguna")
            ok(False, "«ninguna» no tendría que llamar a Claude")
        except ValueError:
            ok(True, "«ninguna» no llama a Claude: no hay nada que leer")
    finally:
        C._llamar_claude = original                               # noqa: SLF001
    igual(len(pedidas), 1, "una sola llamada")
    ok("NO se tocan" in pedidas[0] and "DIAGRAMAS —" in pedidas[0],
       "le dice que el reparto y los sitios no se tocan, y lleva el tramo")
    igual(sorted(ficha), ["avisos", "componentes", "diagramas", "explicativos"],
          "devuelve solo lo de los diagramas: ni sitios ni reparto")
    igual(list(ficha["componentes"]), ["grafico_precios"],
          "solo los gráficos que valen (ni el inventado ni el mapa)")
    igual(len(ficha["explicativos"]), 2, "y sus tramos")


def prueba_donde_va_el_grafico():
    seccion("4c] el gráfico va en el plano cuya voz dice sus cifras")
    import p6_assets as P6                                        # noqa: PLC0415
    grafico = DG.limpiar_grafico("grafico_precios", GRAFICO_BUENO, GUION, [])
    catalogo = {"reparto": {}, "sets": {"sala": {"descripcion": "a room", "palabras": ["sala"]}},
                "beats": [], "lugares": {}, "componentes": {"grafico_precios": grafico}}
    escenas = [{"id": "S001", "narracion": "Bienvenidos a la sala de juegos."},
               {"id": "S002", "narracion": "Una hora de PS5 cuesta 12 soles"},
               {"id": "S003", "narracion": "y una de simulador, 25 soles."},
               {"id": "S004", "narracion": "Una hora de PS5 cuesta 12 soles y una de simulador, 25 soles."}]
    igual(DG.planos_de_graficos(escenas, catalogo["componentes"], "equilibrada"),
          {"S004": "grafico_precios"}, "el plano que dice las dos cifras")
    igual(DG.planos_de_graficos(escenas, catalogo["componentes"], ""), {}, "sin ajuste, ninguno")
    igual(DG.planos_de_graficos(escenas, catalogo["componentes"], "ninguna"), {},
          "con «ninguna», ninguno")
    vacio = dict(catalogo, componentes={})
    sin = copy.deepcopy(escenas)
    P6._asignar_sets(sin, copy.deepcopy(vacio), {"semilla": 1})     # noqa: SLF001
    con = copy.deepcopy(escenas)
    P6._asignar_sets(con, copy.deepcopy(catalogo), {"semilla": 1, "diagramas": "equilibrada"})  # noqa: SLF001
    igual([(e["set"], e["componente"]) for e in con],
          [(s["set"], s["componente"]) for s in sin[:3]] + [(None, "grafico_precios")],
          "en p6, ese plano lleva el gráfico y los demás, su sitio de siempre")
    a, b = copy.deepcopy(escenas), copy.deepcopy(escenas)
    P6._asignar_sets(a, copy.deepcopy(vacio), {"semilla": 1})       # noqa: SLF001
    P6._asignar_sets(b, copy.deepcopy(vacio), {"semilla": 1, "estilo": {}})  # noqa: SLF001
    igual(a, b, "y sin gráficos ni ajuste, el reparto de sitios de siempre")


def _escenas(n, explica=()):
    """n planos repartidos en los bloques; los de 'explica', en B004."""
    escenas = []
    for i in range(n):
        sid = f"S{i + 1:03d}"
        bloque = "B004" if i in explica else "B001"
        escenas.append({"id": sid, "origen": {"bloque": bloque, "indice": 0}})
    return escenas


def prueba_cartas():
    seccion("5] las cartas: el diagrama, por contenido")
    escenas = [{"id": f"S{i:03d}"} for i in range(1, 121)]
    base = E.repartir(escenas, semilla=11)
    sin = E.sin_arrastrar(escenas, base, semilla=11, quitar=("diagrama",))
    diag = [e["id"] for e in escenas if base[e["id"]]["id"] == "diagrama"]
    ok(diag, f"sin quitar, el sorteo saca diagramas ({len(diag)})")
    ok(all(c["id"] != "diagrama" for c in sin.values()), "quitado, ninguno por sorteo")
    igual(sorted(s for s in sin if sin[s]["id"] != base[s]["id"]), sorted(diag),
          "y SOLO cambian los planos que lo habían sacado: nada se arrastra")
    ids = [e["id"] for e in escenas]
    choques = [s for i, s in enumerate(ids) if s in diag and any(
        sin[ids[j]]["familia"] == sin[s]["familia"]
        for j in range(max(0, i - 2), min(len(ids), i + 3)) if j != i)]
    igual(choques, [], "y la sustituta no repite la familia de ningún vecino")
    puesto = E.sin_arrastrar(escenas, base, semilla=11, quitar=("diagrama",),
                             poner={"S005": "diagrama"}, fijas={diag[0]})
    igual((puesto["S005"]["id"], puesto[diag[0]]["id"]), ("diagrama", "diagrama"),
          "el puesto por contenido lleva diagrama, y el forzado a mano no se toca")
    igual(sorted(s for s in puesto if puesto[s]["id"] != base[s]["id"]),
          sorted(set(diag[1:]) | ({"S005"} if base["S005"]["id"] != "diagrama" else set())),
          "y no cambia nada más")

    tramos = [{"desde": "B004", "hasta": "B004", "bloques": ["B004"]}]
    planos = _escenas(16, explica=range(4, 10))
    eq = DG.cartas_de_diagrama(planos, tramos, "equilibrada")
    igual(len(eq), 1, "equilibrada: uno por tramo")
    di = DG.cartas_de_diagrama(planos, tramos, "didactica")
    igual(len(di), 2, "didáctica: dos por tramo")
    ok(all(planos[int(s[1:]) - 1]["origen"]["bloque"] == "B004" for s in di),
       "siempre en los planos del tramo que explica")
    muchos = [{"desde": f"B{i}", "hasta": f"B{i}", "bloques": [f"B{i}"]} for i in range(10)]
    planos = [{"id": f"S{i:03d}", "origen": {"bloque": f"B{i // 2}"}} for i in range(20)]
    igual(len(DG.cartas_de_diagrama(planos, muchos, "equilibrada")), 3,
          "tope 1 de cada 8: con 20 planos, 3")
    igual(len(DG.cartas_de_diagrama(planos, muchos, "didactica")), 5,
          "tope 1 de cada 4: con 20 planos, 5")
    igual(DG.cartas_de_diagrama(planos, muchos, "ninguna"), {}, "«ninguna»: ninguno")
    igual(DG.cartas_de_diagrama(planos, muchos, ""), {}, "sin ajuste: ninguno")
    raros = _escenas(4, explica=range(4))
    raros[0]["cartela"] = {"plantilla": "x"}
    raros[1]["componente"] = "grafico_precios"
    raros[2]["linea_gv"] = {"camara": "close-up"}
    elegidos = DG.cartas_de_diagrama(raros, tramos, "didactica", {"S004": "aereo"})
    igual(elegidos, {}, "cartela, componente, línea con cámara y carta forzada: no se tocan")

    import p6_assets as P6                                        # noqa: PLC0415
    planos = _escenas(24, explica=(9, 10, 11))
    p = {"semilla": 5, "estilo": {}, "diagramas": "equilibrada",
         "catalogo": {"explicativos": tramos}}
    P6._asignar_cartas(planos, p)                                 # noqa: SLF001
    con = [e["id"] for e in planos if e.get("carta") == "diagrama"]
    ok(len(con) == 1 and planos[int(con[0][1:]) - 1]["origen"]["bloque"] == "B004",
       f"en p6, el diagrama sale en el tramo que explica ({con})")
    ok(all(planos[int(s[1:]) - 1].get("abstracta") for s in con),
       "y es abstracto, como siempre")
    base = _escenas(24, explica=(9, 10, 11))
    P6._asignar_cartas(base, {"semilla": 5, "estilo": {}, "catalogo": {}})  # noqa: SLF001
    sorteados = {e["id"] for e in base if e.get("carta") == "diagrama"}
    cambian = {a["id"] for a, b in zip(planos, base) if a.get("carta") != b.get("carta")}
    ok(cambian <= sorteados | set(con),
       f"en p6, solo cambian el del tramo y los que lo sacaban por sorteo ({sorted(cambian)})")
    cat = {"sets": {}, "componentes": {"m": {"tipo": "mapa"}}}
    ok(DG.sin_diagramas(cat) is cat, "sin nada de diagramas, el catálogo para los servicios es el mismo")
    con_dg = dict(cat, explicativos=[1], diagramas="didactica",
                  componentes={"m": {"tipo": "mapa"}, "g": GRAFICO_BUENO})
    igual(DG.sin_diagramas(con_dg), cat, "y con ellos, se le quitan antes de mirar los servicios")
    foto = _escenas(24, explica=(9, 10, 11))
    foto_sin = copy.deepcopy(foto)
    P6._asignar_cartas(foto, dict(p, estilo={"modo": "foto"}))     # noqa: SLF001
    P6._asignar_cartas(foto_sin, {"semilla": 5, "estilo": {"modo": "foto"},  # noqa: SLF001
                                  "catalogo": {}})
    igual(foto, foto_sin, "en foto no cambia nada todavía")


def prueba_motor():
    seccion("6] el motor de los gráficos")
    G = _motor_grafico()
    for nombre, ficha in (("barras", GRAFICO_BUENO), ("proporcion", GRAFICO_EN_LETRAS)):
        svg = G.construir(ficha["config"])
        xml.dom.minidom.parseString(svg)
        ok(True, f"«{nombre}» es un SVG que se lee")
    svg = G.construir(GRAFICO_BUENO["config"])
    ok("S/ 12" in svg and "S/ 25" in svg, "las cifras salen escritas con su unidad")
    doc = xml.dom.minidom.parseString(svg)
    altos = [float(r.getAttribute("height")) for r in doc.getElementsByTagName("rect")
             if r.getAttribute("class") == "barra"]
    ok(len(altos) == 2 and abs(altos[1] / altos[0] - 25 / 12) < 0.01,
       "las barras miden lo que dicen las cifras")
    for clase, datos in (("comparacion", [{"etiqueta": "A", "valor": 35},
                                          {"etiqueta": "B", "valor": 80}]),
                         ("antes_despues", [{"etiqueta": "Antes", "valor": 40},
                                            {"etiqueta": "Después", "valor": 5}])):
        svg = G.construir({"clase": clase, "unidad": "%", "datos": datos})
        xml.dom.minidom.parseString(svg)
        ok(True, f"«{clase}» es un SVG que se lee")
    svg = G.construir({"clase": "barras", "titulo": "<raro> & cía",
                       "datos": [{"etiqueta": "a<b", "valor": 1}, {"etiqueta": "c", "valor": 2}]})
    xml.dom.minidom.parseString(svg)
    ok("&lt;RARO&gt;" in svg, "los textos raros se escapan")
    igual(G._cifra(1500, ""), "1.500", "1500 se escribe 1.500")              # noqa: SLF001
    igual(G._cifra(2.5, "%"), "2,5 %", "2.5 % se escribe 2,5 %")              # noqa: SLF001


def prueba_presets():
    seccion("7] el preset de Estilo guarda `diagramas`")
    import presets_canal as PC                                    # noqa: PLC0415
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "diagramas": "Didáctico"}),  # noqa: SLF001
          {"calidad": "low", "diagramas": "didactica"}, "normalizado")
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "diagramas": ""}),         # noqa: SLF001
          {"calidad": "low"}, "sin ajuste no se guarda")
    try:
        PC._limpiar_datos("estilo", {"calidad": "low", "diagramas": "muchos"})      # noqa: SLF001
        ok(False, "un ajuste que no existe tiene que dar ErrorPreset")
    except PC.ErrorPreset:
        ok(True, "un ajuste que no existe da ErrorPreset")
    datos = PC.datos_de_params({"assets": {"estilo": {"referencias": [],
                                                      "diagramas": "equilibrada"}}})
    igual((datos.get("estilo") or {}).get("diagramas"), "equilibrada",
          "guardar el estilo de un vídeo lo lleva")
    sin = PC.datos_de_params({"assets": {"estilo": {"referencias": []}}})
    ok("diagramas" not in (sin.get("estilo") or {}), "y uno sin él no lo inventa")
    ficha = {"tipo": "estilo", "datos": {"referencias": [], "diagramas": "didactica"}}
    cambios = PC.cambios_para(ficha, {"assets": {"estilo": {}}})
    igual(cambios["assets"]["estilo"].get("diagramas"), "didactica", "aplicarlo lo pone")
    ficha = {"tipo": "estilo", "datos": {"referencias": []}}
    cambios = PC.cambios_para(ficha, {"assets": {"estilo": {"diagramas": "didactica"}}})
    ok("diagramas" not in cambios["assets"]["estilo"], "y uno sin él lo quita")
    ficha = {"tipo": "estilo", "datos": {"referencias": []}}
    cambios = PC.cambios_para(ficha, {"assets": {"estilo": {}}})
    ok("diagramas" not in cambios["assets"]["estilo"], "a un vídeo sin él no se le escribe nada")


def main():
    print("PRUEBA DE LOS DIAGRAMAS POR CONTENIDO")
    prueba_el_ajuste()
    prueba_sin_ajuste_igual()
    prueba_explicativos()
    prueba_graficos()
    prueba_solo_los_diagramas()
    prueba_donde_va_el_grafico()
    prueba_cartas()
    prueba_motor()
    prueba_presets()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"DIAGRAMAS OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

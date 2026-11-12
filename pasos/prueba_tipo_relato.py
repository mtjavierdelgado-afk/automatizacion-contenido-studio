"""
EL TIPO DE RELATO y la IMAGEN BASE QUE SE EDITA (rama tipo-de-relato, 20-10-2026).

Pedido del dueño: congruencia de lugar. En un Reel sobre un baño cada imagen
salia con un baño distinto. Con un tipo de relato EXPLICITO:

  1. el catalogo reparte UN solo sitio y, en «un espacio que cambia», dice que
     cambia en cada tramo (`cambio`, `estado`);
  2. cada plano de ese sitio (salvo los de detalle) se genera EDITANDO la imagen
     base aprobada: la base va la PRIMERA, sin el plano anterior y sin SHOT TYPE;
  3. el revisor compara cada plano editado con su base;
  4. la Parrilla lee «Tipo de relato:» y el preset de Estilo guarda `relato`.

Y LA REGLA DE ORO (regla 1 de CLAUDE.md): sin tipo de relato explicito --sin
nada, con «documental», o con un espacio fijo sin modo-- la instruccion del
catalogo, las referencias, el prompt y la firma de cada imagen son BYTE A BYTE
los de antes de esta rama.

En memoria, sin el CLI y sin pagar nada.

    python pasos/prueba_tipo_relato.py
"""
import copy
import json
import os
import re
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

_TEMPORAL = tempfile.mkdtemp(prefix="estudio_tipo_relato_")
if not os.environ.get("ESTUDIO_ESTADISTICAS"):
    os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(_TEMPORAL, "estadisticas.json")

import catalogo_visual as C  # noqa: E402
import tipo_relato as T  # noqa: E402

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


# ------------------------------------------------------------------ datos

BLOQUES = [
    {"id": "B001", "texto": "La mampara de batiente choca con el inodoro."},
    {"id": "B002", "texto": "Cada mañana la puerta golpea la tapa."},
    {"id": "B003", "texto": "La solución: una mampara corrediza."},
    {"id": "B004", "texto": "Ahora entra sin chocar con nada."},
]

#: La descripcion y la luz de la prueba de aceptacion a) (D01-1).
ESPACIO = {
    "sitio": "bano_mampara",
    "descripcion": ("small apartment bathroom in Lima, 1.5 x 2.4 m, rectangular; toilet on "
                    "the left wall, wall-hung vanity with a single basin and rectangular "
                    "mirror on the back wall, walk-in shower at the far end on the right; "
                    "door in the near short wall; same layout, same camera height and same "
                    "proportions in every shot; large light-grey porcelain tiles on the "
                    "floor, white walls, chrome fittings"),
    "luz": "day, soft cool daylight from a small high window plus warm ceiling downlight",
    "secundarios": [],
}

RESPUESTA = {
    "reparto": {},
    "sets": {
        "bano": {"rotulo": "El baño", "descripcion": "a small bathroom with white tiles",
                 "palabras": ["baño"], "luz": "day"},
        "tienda": {"rotulo": "La tienda", "descripcion": "a shower-screen shop",
                   "palabras": ["tienda"], "luz": "day"},
    },
    "lugares": {"lima": "LIMA"},
    "beats": [
        {"desde": "B001", "hasta": "B002", "set": "bano", "personajes": [], "tono": "neutro",
         "accion": "the hinged door hits the toilet", "cambio": "", "estado": "antes"},
        {"desde": "B003", "hasta": "B003", "set": "tienda", "personajes": [], "tono": "neutro",
         "accion": "a sliding screen", "cambio": "the hinged shower door is replaced by a "
                                                 "sliding glass door", "estado": "despues"},
        {"desde": "B004", "hasta": "B004", "set": "bano", "personajes": [], "tono": "alegre",
         "accion": "someone walks in", "cambio": "otra cosa que se ignora", "estado": "despues"},
    ],
    "avisos": [],
}


def _proponer(**extra):
    vistas = []

    def claude_falso(instruccion, *_a, **_k):
        vistas.append(instruccion)
        return json.dumps(RESPUESTA), {}

    real = C._llamar_claude                       # noqa: SLF001
    C._llamar_claude = claude_falso               # noqa: SLF001
    try:
        ficha = C.proponer(copy.deepcopy(BLOQUES), brief={"titulo": "Mampara", "resumen": "baño"},
                           planos=10, min_s=2, max_s=4, **extra)
    finally:
        C._llamar_claude = real                   # noqa: SLF001
    return vistas[0], ficha


# ------------------------------------------------------------------ pruebas

def prueba_modos_y_lineas():
    seccion("1] los modos: clave o nombre visible, con o sin tildes")
    igual(T.modo_de_texto("Un espacio que cambia"), "espacio_que_cambia", "por el nombre visible")
    igual(T.modo_de_texto("ESPACIO_QUE_CAMBIA"), "espacio_que_cambia", "por la clave en mayúsculas")
    igual(T.modo_de_texto("escenario y apoyos"), "escenario_y_apoyos", "con espacios")
    igual(T.modo_de_texto("telenovela"), None, "lo que no es un modo, None")
    igual(T.leer_linea("espacio_que_cambia (acabados)"),
          {"modo": "espacio_que_cambia", "cambia": "acabados"}, "la línea de la Parrilla")
    igual(T.leer_linea("Un espacio que cambia — Los acabados"),
          {"modo": "espacio_que_cambia", "cambia": "acabados"}, "con el nombre visible y raya")
    igual(T.leer_linea("Producto"), {"modo": "producto"}, "un modo sin subtipo")
    igual(T.leer_linea("espacio que cambia"), {"modo": "espacio_que_cambia", "cambia": "objeto"},
          "sin subtipo, «objeto» por defecto")
    igual(T.leer_linea("Recorrido (acabados)"), {"modo": "recorrido"},
          "el subtipo solo vale en un espacio que cambia")
    for malo in ("", "telenovela", "espacio_que_cambia (colores raros)"):
        try:
            T.leer_linea(malo)
            ok(False, f"{malo!r} tiene que dar ValueError")
        except ValueError:
            ok(True, f"{malo!r} da ValueError")
    igual(T.normalizar(None), {}, "nada guardado es {}")
    igual(T.normalizar({"modo": "Un espacio que cambia", "cambia": "La hora"}),
          {"modo": "espacio_que_cambia", "cambia": "hora"}, "se guarda por clave")
    for malo in ({"modo": "x"}, {"modo": "producto", "bases": {"bano": {"imagen": "../x.png"}}},
                 {"modo": "producto", "bases": "x"}, "producto"):
        try:
            T.normalizar(malo)
            ok(False, f"{str(malo)[:40]!r} tiene que dar ValueError")
        except ValueError:
            ok(True, f"{str(malo)[:40]!r} da ValueError")
    igual(T.normalizar_de_estilo({"modo": "documental"}), {},
          "en el estilo, documental es no tenerlo (no mueve firmas)")


def prueba_resolver():
    seccion("2] qué manda (opción B): vídeo > estilo > espacio fijo implícito > documental")
    igual(T.resolver({}), {"modo": "documental", "cambia": "", "explicito": False, "origen": ""},
          "sin nada, documental implícito")
    igual(T.resolver({"espacio_fijo": ESPACIO})["modo"], "escenario_y_apoyos",
          "con espacio fijo, escenario y apoyos")
    ok(not T.resolver({"espacio_fijo": ESPACIO})["explicito"],
       "y es IMPLÍCITO: no corre nada nuevo (los vídeos de hoy con espacio fijo, idénticos)")
    con_estilo = {"espacio_fijo": ESPACIO, "estilo": {"relato": {"modo": "producto"}}}
    igual((T.resolver(con_estilo)["modo"], T.resolver(con_estilo)["origen"]),
          ("producto", "estilo"), "el estilo manda sobre el espacio fijo implícito")
    con_video = dict(con_estilo, tipo_relato={"modo": "espacio_que_cambia", "cambia": "acabados"})
    igual((T.resolver(con_video)["modo"], T.resolver(con_video)["cambia"],
           T.resolver(con_video)["origen"]),
          ("espacio_que_cambia", "acabados", "video"), "y el del vídeo manda sobre todo")
    igual(T.resolver({"estilo": {"relato": {"modo": "documental"}}, "espacio_fijo": ESPACIO})["modo"],
          "escenario_y_apoyos", "un estilo documental no pisa el espacio fijo")
    ok(not T.activo(T.resolver({"tipo_relato": {"modo": "documental"}})),
       "documental explícito tampoco activa nada")
    igual(T.resolver({"tipo_relato": {"modo": "basura"}})["modo"], "documental",
          "un valor guardado roto no tumba nada: documental")


def prueba_catalogo_igual_sin_modo():
    seccion("3] sin modo explícito, la instrucción y el catálogo son BYTE A BYTE los de antes")
    base_instr, base_ficha = _proponer()
    for relato in (None, T.resolver({}), T.resolver({"tipo_relato": {"modo": "documental"}})):
        instr, ficha = _proponer(relato=relato)
        igual(instr, base_instr, f"sin espacio, relato={relato and relato['modo']}: instrucción igual")
        igual(ficha, base_ficha, "y el catálogo igual")
    esp_instr, esp_ficha = _proponer(espacio_fijo=copy.deepcopy(ESPACIO))
    instr, ficha = _proponer(espacio_fijo=copy.deepcopy(ESPACIO),
                             relato=T.resolver({"espacio_fijo": ESPACIO}))
    igual(instr, esp_instr, "con espacio fijo y su escenario y apoyos implícito: instrucción igual")
    igual(ficha, esp_ficha, "y el catálogo igual (sin 'relato', sin 'cambio' en los tramos)")
    ok("relato" not in esp_ficha and all("cambio" not in b for b in esp_ficha["beats"]),
       "ningún campo nuevo")


def prueba_catalogo_con_modo():
    seccion("4] «un espacio que cambia (objeto)» con espacio fijo")
    relato = T.resolver({"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"}})
    instr, ficha = _proponer(espacio_fijo=copy.deepcopy(ESPACIO), relato=relato)
    ok("UN ESPACIO QUE CAMBIA" in instr and "un OBJETO concreto" in instr,
       "el criterio dice qué cambia y pide cambio/estado por tramo")
    ok("ESTE VIDEO TIENE UN ESPACIO FIJO" in instr and ESPACIO["descripcion"] in instr,
       "con el espacio fijo literal")
    ok("COMO MINIMO" not in instr and "como mucho por sitio seguido" not in instr,
       "sin presión de sitios (PLANOS_POR_SET no aplica)")
    ok(not re.search(r"\{[a-z_]+\}", instr), "sin ningún {hueco} sin rellenar")
    igual(list(ficha["sets"]), ["bano_mampara"], "un solo sitio")
    igual(ficha["sets"]["bano_mampara"]["rotulo"], "", "rótulo vacío")
    igual(ficha["lugares"], {}, "ningún lugar que rotular")
    igual([b["estado"] for b in ficha["beats"]], ["antes", "despues", "despues"],
          "cada tramo con su estado")
    igual(ficha["beats"][0]["cambio"], "", "el «antes» no cambia nada")
    igual(ficha["beats"][2]["cambio"], ficha["beats"][1]["cambio"],
          "dos tramos con el mismo estado comparten el cambio (el del primero)")
    igual(ficha["relato"], {"modo": "espacio_que_cambia", "cambia": "objeto"},
          "y el catálogo dice con qué modo se repartió")

    seccion("5] un modo de un solo sitio SIN espacio fijo: Claude declara el sitio")
    instr, ficha = _proponer(relato=T.resolver({"tipo_relato": {"modo": "producto"}}))
    ok("ESTE VIDEO PASA EN UN SOLO SITIO" in instr and "PRODUCTO — el producto manda" in instr,
       "el criterio pide UN sitio y explica el modo")
    igual(len(ficha["sets"]), 1, "y se impone por código un único sitio")
    igual({b["set"] for b in ficha["beats"]}, set(ficha["sets"]), "con todos los tramos en él")
    ok(all("cambio" not in b for b in ficha["beats"]), "producto no lleva cambio por tramo")

    seccion("6] un catálogo ya guardado: los cambios de cada tramo se piden aparte")
    vistas = []

    def claude_falso(instruccion, *_a, **_k):
        vistas.append(instruccion)
        return json.dumps({"beats": [
            {"desde": "B001", "hasta": "B002", "cambio": "", "estado": "antes"},
            {"desde": "B003", "hasta": "B004", "cambio": "sliding door", "estado": "despues"}]}), {}

    real = C._llamar_claude                       # noqa: SLF001
    C._llamar_claude = claude_falso               # noqa: SLF001
    try:
        guardado = {"sets": {"bano": {"descripcion": "a bathroom"}},
                    "beats": [{"desde": "B001", "hasta": "B002", "set": "bano", "accion": "a"},
                              {"desde": "B003", "hasta": "B004", "set": "bano", "accion": "b"}]}
        nuevo, _ = C.proponer_cambios(BLOQUES, guardado, relato)
    finally:
        C._llamar_claude = real                   # noqa: SLF001
    ok("LOS TRAMOS (no los cambies" in vistas[0] and "- B003-B004: b" in vistas[0],
       "la instrucción lista los tramos de siempre")
    igual([b["cambio"] for b in nuevo["beats"]], ["", "sliding door"], "y les pega su cambio")
    try:
        C.proponer_cambios(BLOQUES, guardado, T.resolver({"tipo_relato": {"modo": "producto"}}))
        ok(False, "fuera de «un espacio que cambia» tiene que dar ValueError")
    except ValueError:
        ok(True, "fuera de «un espacio que cambia» da ValueError")


def _p6_y_dirs():
    from PIL import Image                                    # noqa: PLC0415
    import p6_assets as P6                                   # noqa: PLC0415
    carpeta = os.path.join(_TEMPORAL, "proyecto_p6")
    for sub in ("escenas", "reparto", "cache", "espacio_fijo", "estilo"):
        os.makedirs(os.path.join(carpeta, sub), exist_ok=True)
    base = os.path.join(carpeta, "espacio_fijo", "a1b2c3d4e5f60718.png")
    Image.new("RGB", (64, 40), (200, 200, 210)).save(base)
    estilo = os.path.join(carpeta, "estilo", "ref.png")
    Image.new("RGB", (64, 40), (30, 90, 160)).save(estilo)
    previa = os.path.join(carpeta, "escenas", "S001.png")
    Image.new("RGB", (64, 40), (10, 200, 10)).save(previa)
    dirs = {"escenas": os.path.join(carpeta, "escenas"), "reparto": os.path.join(carpeta, "reparto"),
            "cache": os.path.join(carpeta, "cache"), "espacio_fijo": None,
            "bases": {"bano_mampara": base}}
    return P6, carpeta, dirs, estilo, base


def prueba_referencias_y_prompt():
    seccion("7] p6: la base va la PRIMERA, sin plano anterior y sin SHOT TYPE")
    P6, carpeta, dirs, estilo, base = _p6_y_dirs()
    beat = {"cambio": "the hinged shower door is replaced by a sliding glass door",
            "estado": "despues"}
    relato_crudo = {"modo": "espacio_que_cambia", "cambia": "objeto",
                    "bases": {"bano_mampara": {
                        "imagen": "espacio_fijo/a1b2c3d4e5f60718.png", "aprobada": True,
                        # UN ESTADO, UNA IMAGEN (prueba real del 21-10)
                        "estados": {"despues": {"imagen": "espacio_fijo/b2c3d4e5f6071829.png",
                                                "aprobada": True, "cambio": beat["cambio"]}}}}}
    p = {"estilo": {"referencias": [estilo]}, "espacio_fijo": dict(ESPACIO),
         "tipo_relato": relato_crudo, "unidades": {}}
    relato = T.resolver(p)
    catalogo = {"beats": [dict(beat, set="bano_mampara")]}
    dirs = dict(dirs, bases={"bano_mampara": base, "bano_mampara#despues": base})
    escenas = [
        {"id": "S001", "set": "bano_mampara", "personajes": [], "narracion": "choca",
         "carta": "general", "encuadre": "a wide establishing shot"},
        {"id": "S002", "set": "bano_mampara", "personajes": [], "narracion": "corrediza",
         "carta": "general", "encuadre": "a wide establishing shot"},
        {"id": "S003", "set": "bano_mampara", "personajes": [], "narracion": "detalle",
         "carta": "detalle", "encuadre": "an extreme close-up"},
    ]
    for e in escenas:
        P6._marcar_edicion(e, beat, relato, "bano_mampara", "ilustracion",   # noqa: SLF001
                           T.bases_aprobadas(p, catalogo))
    ok(escenas[0].get("editar_base") and escenas[1].get("editar_base"),
       "los planos generales del sitio se editan")
    ok(not escenas[2].get("editar_base"), "el de detalle NO (va con la base como referencia)")
    igual(escenas[1].get("base"), "espacio_fijo/b2c3d4e5f6071829.png",
          "el plano lleva la ruta de la imagen de SU ESTADO (para la fase 5)")
    igual(escenas[1].get("base_clave"), "bano_mampara#despues", "y su clave «sitio#estado»")
    otra = T.bases_aprobadas(p, {"beats": [dict(beat, cambio="a curtain instead")]})
    ok("bano_mampara#despues" not in otra and "bano_mampara" in otra,
       "si Claude reescribe el cambio, la imagen del estado deja de valer (la base no)")
    otro_sitio = {"beats": [dict(beat, set="patio", cambio="the gate is open"),
                            dict(beat, set="bano_mampara")]}
    ok("bano_mampara#despues" in T.bases_aprobadas(p, otro_sitio),
       "el mismo estado en otro sitio, con otro cambio, no tapa el de este (revisión del 21-10)")
    ok(not P6._con_encuadre(escenas[1]) and P6._con_encuadre(escenas[2]),   # noqa: SLF001
       "el plano editado no lleva SHOT TYPE; el de detalle sí")
    plan = {"escenas": escenas, "assets": {}}
    refs = P6._referencias_escena(escenas[1], plan, dirs, p, dirs["cache"],   # noqa: SLF001
                                  {"S001": os.path.join(dirs["escenas"], "S001.png")},
                                  anteriores=["S001"])
    igual([r["papel"] for r in refs][:2], ["base", "estilo"], "la base primero, el estilo detrás")
    ok("continuidad" not in [r["papel"] for r in refs],
       "y sin el plano anterior (arrastraría su cambio)")
    texto = P6._prompt_completo(escenas[1], refs, p["estilo"])               # noqa: SLF001
    ok("Reference image 1 is THE SHOT TO EDIT ('bano_mampara')" in texto,
       "el prompt presenta la imagen 1 como la que se edita")
    ok("Change ONLY: nothing in the room itself" in texto
       and "Change ONLY: the hinged" not in texto,
       "la imagen del estado YA trae el cambio: el plano no lo vuelve a pedir")
    ok("Only that object changes" in texto, "y la frase del subtipo «objeto»")
    ok(texto.rstrip().endswith("No watermarks.") and "FINAL CHECK" in texto
       and texto.index("FINAL CHECK") > texto.index("Change ONLY"),
       "y cierra con el recordatorio de la edición, DETRÁS de la escena (la línea que más pesa)")
    refs_det = P6._referencias_escena(escenas[2], plan, dirs, p, dirs["cache"], {},  # noqa: SLF001
                                      anteriores=[])
    igual([r["papel"] for r in refs_det][:2], ["estilo", "espacio"],
          "el de detalle lleva la base como referencia del sitio")
    igual(P6.planos_sin_base(plan, dirs), {}, "con la base aprobada no falta ninguna")
    igual(P6.planos_sin_base(plan, dict(dirs, bases={})), {"bano_mampara#despues": ["S002"]},
          "sin ella, se dice qué planos ESPERAN: los que no tienen imagen (S001 ya la tiene)")
    igual(P6.planos_sin_base(plan, dict(dirs, bases={"bano_mampara": base})),
          {"bano_mampara#despues": ["S002"]},
          "con la base aprobada pero sin la de su estado, también esperan")
    igual(P6.planos_sin_base(plan, dict(dirs, bases={}), unidades=["escena:S001"]),
          {"bano_mampara#despues": ["S001"]}, "o los pedidos, aunque tengan imagen")
    igual(P6.planos_sin_base(plan, dict(dirs, bases={}), unidades=["escena:S003"]), {},
          "y rehacer un plano que no se edita no se bloquea")
    igual(P6.planos_sin_base(plan, dict(dirs, bases={}), rehacer=True),
          {"bano_mampara#despues": ["S001", "S002"]}, "con «rehacer todo», todos los editados")
    antes = dict(escenas[0])
    P6._marcar_edicion(antes, {"cambio": "", "estado": "antes"}, relato,   # noqa: SLF001
                       "bano_mampara", "ilustracion", T.bases_aprobadas(p, catalogo))
    ok(antes.get("editar_base") and "base_clave" not in antes
       and antes.get("base") == "espacio_fijo/a1b2c3d4e5f60718.png",
       "un tramo sin cambio (el «antes») edita la base del sitio, sin estado")
    texto_e = T.prompt_imagen_estado(beat["cambio"])
    ok(beat["cambio"] in texto_e and "No people" in texto_e and "rigid" in texto_e,
       "la imagen del estado: la base con UN cambio, vacía, rígida y a escala")

    seccion("8] sin modo explícito, las referencias y el prompt son los de siempre")
    sin = {"estilo": {"referencias": [estilo]}, "espacio_fijo": dict(ESPACIO), "unidades": {}}
    limpias = [dict(e) for e in escenas]
    for e in limpias:
        for clave in ("editar_base", "cambio", "estado", "base"):
            e.pop(clave, None)
    plan_sin = {"escenas": limpias, "assets": {}}
    previas = {"S001": os.path.join(dirs["escenas"], "S001.png")}
    con_bases = P6._referencias_escena(limpias[1], plan_sin, dict(dirs, bases={}), sin,  # noqa: SLF001
                                       dirs["cache"], previas, anteriores=["S001"])
    igual([r["papel"] for r in con_bases], ["estilo", "continuidad"],
          "estilo y continuidad, como siempre")
    ok("FINAL CHECK" not in P6._prompt_completo(limpias[1], con_bases, sin["estilo"]),  # noqa: SLF001
       "y sin base, ningún cierre de edición")
    # rutas_de_bases no da nada sin modo explicito (aunque haya bases guardadas)

    class _Proyecto:
        def ruta(self, *partes):
            return os.path.join(carpeta, *partes)

    igual(P6.rutas_de_bases(_Proyecto(), dict(sin, tipo_relato={
        "bases": relato_crudo["bases"]})), {},
          "una base guardada de un modo que ya no rige no se adjunta a nadie")
    igual(P6.rutas_de_bases(_Proyecto(), p), {"bano_mampara": base},
          "con el modo explícito, la base aprobada")


def prueba_revisor():
    seccion("9] el revisor compara cada plano editado con su base")
    import revisor_imagenes as R                             # noqa: PLC0415
    P6, carpeta, dirs, estilo, base = _p6_y_dirs()

    class _Proyecto:
        raiz = carpeta

        def ruta(self, *partes):
            return os.path.join(carpeta, *partes)

    normal = {"id": "S001", "set": "bano_mampara", "narracion": "x", "prompt": "p"}
    imagenes = {"S001": os.path.join(dirs["escenas"], "S001.png")}
    sin = R._planos_legibles(_Proyecto(), [normal], imagenes, {})           # noqa: SLF001
    ok("EDITADO DESDE LA IMAGEN BASE" not in sin, "un plano normal, como siempre")
    editado = dict(normal, editar_base=True, cambio="sliding door")
    con = R._planos_legibles(_Proyecto(), [editado], imagenes, {})          # noqa: SLF001
    ok("EDITADO DESDE LA IMAGEN BASE de «bano_mampara»; lo unico que se pidio cambiar: sliding door"
       in con, "el editado dice de qué base sale y qué se pidió cambiar")
    bloque = R._referencia_base(_Proyecto(), [editado], {"bano_mampara": base})  # noqa: SLF001
    ok("LA IMAGEN BASE DE «bano_mampara»" in bloque and '"congruencia" con gravedad "alta"' in bloque,
       "y la instrucción trae la base: un cambio fuera de lo pedido es congruencia alta")
    igual(R._referencia_base(_Proyecto(), [normal], {"bano_mampara": base}), "",   # noqa: SLF001
          "sin planos editados, nada")


def prueba_parrilla():
    seccion("10] la Parrilla: «Tipo de relato:» se lee, y la de hoy se lee igual")
    import parrilla as P                                     # noqa: PLC0415
    hoy = ("G01 — Mampara\nUso: exacto\nFormato: vertical\nDuración: 30 s\n\n"
           "ESCENA 1\nVisual: un baño\nVoz: «La mampara choca»\n\n"
           "PARA EL ENCARGO\n- Material: La mampara choca.\n- Llamadas a la acción: escríbenos")
    g = P.leer_guion(hoy)
    ok("tipo_relato" not in g and "tipo_relato" not in P.encargo_de(g),
       "sin la línea, ni el guion ni el encargo ganan ninguna clave")
    con = hoy.replace("Duración: 30 s\n", "Duración: 30 s\nTipo de relato: Un espacio que cambia (objeto)\n")
    igual(P.encargo_de(P.leer_guion(con))["tipo_relato"],
          {"modo": "espacio_que_cambia", "cambia": "objeto"}, "con la línea, va al Encargo")
    igual(P.leer_guion(con)["duracion_s"], 30, "y el resto de la cabecera se sigue leyendo")
    malo = hoy.replace("Duración: 30 s\n", "Duración: 30 s\nTipo de relato: culebrón\n")
    enc = P.encargo_de(P.leer_guion(malo))
    ok("tipo_relato" not in enc and any("Tipo de relato" in a for a in enc["avisos"]),
       "uno que no se entiende se avisa y no se aplica")
    plantilla = P.encargo_de(P.leer_guion(P.plantilla_vacia()))
    ok("tipo_relato" not in plantilla, "la plantilla vacía (con las opciones) no fija ninguno")


def prueba_presets():
    seccion("11] el preset de Estilo guarda `relato` y lo lleva y lo quita")
    import presets_canal as PC                               # noqa: PLC0415
    limpio = PC._limpiar_datos("estilo", {"relato": {"modo": "Un espacio que cambia",  # noqa: SLF001
                                                     "cambia": "acabados"}})
    igual(limpio["relato"], {"modo": "espacio_que_cambia", "cambia": "acabados"}, "normalizado")
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "relato": {"modo": "documental"}}),  # noqa: SLF001
          {"calidad": "low"}, "documental no se guarda")
    try:
        PC._limpiar_datos("estilo", {"relato": {"modo": "x"}})                       # noqa: SLF001
        ok(False, "un modo que no existe tiene que dar ErrorPreset")
    except PC.ErrorPreset:
        ok(True, "un modo que no existe da ErrorPreset")
    params = {"assets": {"estilo": {"referencias": [], "relato": {"modo": "producto"}}}}
    datos = PC.datos_de_params(params)
    igual((datos.get("estilo") or {}).get("relato"), {"modo": "producto"},
          "guardar un estilo desde un vídeo se lleva el relato")
    sin = PC.datos_de_params({"assets": {"estilo": {"referencias": []}}})
    ok("relato" not in (sin.get("estilo") or {}), "y uno sin relato no lo inventa")


def prueba_imagen_base():
    seccion("12] el prompt de la imagen base: el sitio vacío, entero y en su estado inicial")
    texto = T.prompt_imagen_base(ESPACIO, T.resolver({"tipo_relato": {"modo": "espacio_que_cambia",
                                                                       "cambia": "objeto"}}))
    ok(ESPACIO["descripcion"] in texto and ESPACIO["luz"] in texto, "con la descripción y la luz")
    ok("INITIAL state" in texto and "No people" in texto, "vacío y en el «antes»")
    ok("MUST already be in this picture" not in texto, "sin «inicial», nada de lo que cambia")
    puerta = "a hinged glass door on the shower's left edge, opening toward the toilet"
    relato = dict(T.resolver({"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"}}),
                  inicial=puerta)
    ok(puerta in T.prompt_imagen_base(ESPACIO, relato),
       "con «inicial», lo que luego cambia sale YA en la base, donde va (prueba real 21-10)")
    ok("rigid object at its true size" in T.prompt_imagen_base(ESPACIO, relato),
       "quieto, recto y a escala: ni torcido ni a medio abrir (la hoja en ángulo del 21-10)")
    hora = dict(T.resolver({"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "hora"}}),
                inicial=puerta)
    ok(puerta not in T.prompt_imagen_base(ESPACIO, hora), "y en «hora» no se pinta")
    import catalogo_visual as CV                                  # noqa: PLC0415
    cat = CV._aplicar_relato({"sets": {"b": {"descripcion": "a bathroom"}},     # noqa: SLF001
                              "beats": [{"desde": "B01", "hasta": "B01", "set": "b"}]},
                             [{"desde": "B01", "hasta": "B01", "cambio": "", "estado": "antes"}],
                             relato, {"sitio": "b"}, ["B01"], "  " + puerta + "  ")
    igual(cat["relato"].get("inicial"), puerta, "el catálogo guarda el «inicial» de Claude")


def prueba_ambientes_y_camara():
    import p6_assets as P6                                   # noqa: PLC0415
    seccion("13] recorrido y clase: varios ambientes del mismo lugar (tipo-de-relato-2)")
    relato = T.resolver({"tipo_relato": {"modo": "recorrido"}})
    instr, ficha = _proponer(relato=relato)
    ok("VARIOS AMBIENTES DE UN MISMO LUGAR" in instr and "ESTE VIDEO PASA EN UN SOLO SITIO" not in instr,
       "el criterio pide varios ambientes, no un solo sitio")
    ok(not re.search(r"\{[a-z_]+\}", instr), "sin ningún {hueco} sin rellenar")
    igual(sorted(ficha["sets"]), ["bano", "tienda"], "los dos ambientes que usa algún tramo se quedan")
    igual(next(iter(ficha["sets"])), "bano", "el principal es el más usado")
    igual({s["luz"] for s in ficha["sets"].values()}, {ficha["sets"]["bano"]["luz"]},
          "la misma luz en todos los ambientes")
    igual({s["rotulo"] for s in ficha["sets"].values()}, {""}, "sin rótulos de sitio")
    instr_c, ficha_c = _proponer(relato=T.resolver({"tipo_relato": {"modo": "clase"}}))
    ok("VARIOS AMBIENTES" in instr_c and len(ficha_c["sets"]) == 2, "la clase, igual")
    instr_p, _f = _proponer(relato=T.resolver({"tipo_relato": {"modo": "producto"}}))
    ok("ESTE VIDEO PASA EN UN SOLO SITIO" in instr_p, "producto sigue siendo un solo sitio")
    params = {"tipo_relato": {"modo": "recorrido"}, "catalogo": ficha}
    ambientes = P6.ambientes_del_relato(None, params)
    igual([a["sitio"] for a in ambientes], ["bano", "tienda"], "los ambientes, el principal primero")
    ok(all(a["espacio"]["descripcion"] for a in ambientes), "cada uno con su descripción")
    igual(P6.ambientes_del_relato(None, {"tipo_relato": {"modo": "producto"}, "catalogo": ficha}), [],
          "fuera de recorrido y clase, ninguno")
    igual(P6.ambientes_del_relato(None, {"catalogo": ficha}), [], "sin tipo de relato, ninguno (regla 1)")
    frase = P6.frase_de_referencia(2, {"papel": "casa", "nombre": "bano"})
    ok("ANOTHER room of the same place" in frase and "never copy its layout" in frase,
       "la base del principal, al dibujar otro ambiente, solo da materiales y luz")

    seccion("14] modo guion: la cámara de la línea decide si el plano edita la base")
    igual(P6._familia_del_plano({"linea_gv": {"camara": "close-up of the door edge"}}, "foto"),  # noqa: SLF001
          "cerca", "un primer plano pedido no edita la base")
    igual(P6._familia_del_plano({"linea_gv": {"camara": "wide shot from the doorway"}}, "foto"),  # noqa: SLF001
          "lejos", "un plano general la edita")
    igual(P6._familia_del_plano({"linea_gv": {"camara": "wide shot, detailed tiles"}}, "foto"),  # noqa: SLF001
          "lejos", "«detailed» no es un detalle")
    ec = {"modo": "espacio_que_cambia", "cambia": "estado"}
    igual(P6._familia_del_plano({"linea_gv": {"camara": "medium shot, detailed tiles"}}, "foto", ec),  # noqa: SLF001
          "cerca", "un plano medio de un espacio que cambia respeta su cámara (decisión del 12-11)")
    igual(P6._familia_del_plano({"linea_gv": {"camara": "medium shot of the jar"}}, "foto",  # noqa: SLF001
                                {"modo": "producto"}),
          "lejos", "en «producto» el plano medio sigue editando la base (copia el producto)")
    igual(P6._familia_del_plano({"linea_gv": {"camara": "medium-wide shot of the room"}}, "foto", ec),  # noqa: SLF001
          "lejos", "un «medium-wide» enseña la habitación: edita")
    igual(P6._familia_del_plano({"linea_gv": {"visual": "Medium close-up of the mirror"}}, "foto"),  # noqa: SLF001
          "", "sin relato y sin cámara, un medio como antes")
    for camara, esperada in (("medium shot moving into a close-up of the label", "cerca"),
                             ("close-up of the label, mid-shot framing", "cerca"),
                             ("medium close-up of the jar", "lejos")):
        igual(P6._familia_del_plano({"linea_gv": {"camara": camara}}, "foto",  # noqa: SLF001
                                    {"modo": "producto"}), esperada,
              f"en «producto», «{camara}» sale como en main ({esperada})")
    igual(P6._familia_del_plano({"carta": "detalle"}, "ilustracion"), "cerca",  # noqa: SLF001
          "sin línea, la familia de su carta, como siempre")
    rel = T.resolver({"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"}})
    escena = {"id": "S002", "set": "bano", "linea_gv": {"camara": "close-up of the hinge"}}
    P6._marcar_edicion(escena, {"cambio": "the door open", "estado": "abierta"}, rel,  # noqa: SLF001
                       "bano", "foto", {"bano": "espacio_fijo/a.png", "bano#abierta": "espacio_fijo/b.png"})
    ok("editar_base" not in escena, "el primer plano no se edita")
    igual(escena.get("ref_clave"), "bano#abierta", "y su referencia es la imagen de SU estado")
    sin_linea = {"id": "S003", "set": "bano", "carta": "detalle"}
    P6._marcar_edicion(sin_linea, {"cambio": "the door open", "estado": "abierta"}, rel,  # noqa: SLF001
                       "bano", "ilustracion", {"bano": "espacio_fijo/a.png"})
    ok("ref_clave" not in sin_linea, "sin línea (modo voz), el detalle como siempre")


def prueba_revision_03_11():
    import guion_visual as G                                  # noqa: PLC0415
    import p6_assets as P6                                    # noqa: PLC0415
    seccion("15] lo que encontró la revisión del 03-11")
    for camara, esperada in (("detalle de la bisagra", "cerca"), ("tight shot of the handle", "cerca"),
                             ("insert of the key", "cerca"), ("ECU of the hinge", "cerca"),
                             ("plano corto del grifo", "cerca"), ("medium close-up of Ana in the kitchen", "cerca"),
                             ("plano medio de la cocina", "cerca"), ("medium shot from the shower side", "cerca"), ("wide shot from the door", "lejos")):
        igual(P6._familia_del_plano({"linea_gv": {"camara": camara}}, "foto",  # noqa: SLF001
                                    {"modo": "espacio_que_cambia"}), esperada,
              f"la cámara «{camara}» es {esperada}")
    # el principal de un recorrido es el primero que declaró Claude, aunque otro tenga más tramos
    cat = {"sets": {"cocina": {"descripcion": "an oak kitchen", "luz": "day"},
                    "sala": {"descripcion": "an oak living room", "luz": "day"}},
           "beats": [{"set": "cocina", "desde": "B001", "hasta": "B001"},
                     {"set": "sala", "desde": "B002", "hasta": "B002"},
                     {"set": "sala", "desde": "B003", "hasta": "B003"}]}
    igual(C.espacio_del_catalogo(cat, ambientes=True)["sitio"], "cocina", "con ambientes, el principal es el primero")
    igual(C.espacio_del_catalogo(cat)["sitio"], "sala", "sin ambientes, el más usado (como siempre)")
    # «Aplicar» un recorrido no junta los ambientes en uno
    ajustado, _avisos = C.ajustar_catalogo(cat, C.espacio_del_catalogo(cat, ambientes=True), ["B001", "B002", "B003"])
    igual(sorted(ajustado["sets"]), ["cocina", "sala"], "ajustar con los ambientes conserva los dos")
    # el guion visual sabe de los otros ambientes
    fijo = G._fijo_legible({"descripcion": "an oak kitchen", "luz": "day",  # noqa: SLF001
                            "secundarios": [{"nombre": "Sala", "descripcion": "an oak living room"}]}, {}, {})
    ok("OTRO AMBIENTE DEL MISMO LUGAR (Sala): an oak living room" in fijo, "lo fijo del guion visual lleva los ambientes")
    igual(G._fijo_legible({"descripcion": "a bathroom", "luz": "day"}, {}, {}),  # noqa: SLF001
          "SITIO: a bathroom (luz: day)", "con un solo sitio, igual que antes")


def prueba_retoque_acotado():
    seccion("16] rehacer con nota un plano que edita su estado (rama retoque-acotado)")
    import shutil                                            # noqa: PLC0415
    P6, carpeta, dirs, estilo, base = _p6_y_dirs()
    beat = {"cambio": "the walls are painted in palette 2", "estado": "paleta_2"}
    p = {"estilo": {"referencias": [estilo], "modo": "foto"}, "espacio_fijo": dict(ESPACIO),
         "tipo_relato": {"modo": "espacio_que_cambia", "cambia": "acabados", "bases": {"bano_mampara": {
             "imagen": "espacio_fijo/a1b2c3d4e5f60718.png", "aprobada": True,
             "estados": {"paleta_2": {"imagen": "espacio_fijo/b2c3d4e5f6071829.png",
                                      "aprobada": True, "cambio": beat["cambio"]}}}}},
         "unidades": {"escena:S002": {"feedback": "the towel rail is missing", "alcance": "retoque"}}}
    relato = T.resolver(p)
    dirs = dict(dirs, bases={"bano_mampara": base, "bano_mampara#paleta_2": base})
    escena = {"id": "S002", "set": "bano_mampara", "personajes": [], "narracion": "paleta 2",
              "carta": "general", "encuadre": "a wide establishing shot", "prompt": "the bathroom"}
    P6._marcar_edicion(escena, beat, relato, "bano_mampara", "foto",   # noqa: SLF001
                       T.bases_aprobadas(p, {"beats": [dict(beat, set="bano_mampara")]}))
    shutil.copy(os.path.join(dirs["escenas"], "S001.png"), os.path.join(dirs["escenas"], "S002.png"))
    plan = {"escenas": [escena], "assets": {}}
    refs = P6._referencias_escena(escena, plan, dirs, p, dirs["cache"], {}, anteriores=[])  # noqa: SLF001
    igual([r["papel"] for r in refs], ["base", "estilo", "rechazada"],
          "la imagen del estado primero y la rechazada al final")
    igual(refs[-1].get("de_edicion"), 1, "la rechazada sabe que se edita la imagen 1")
    texto = P6._prompt_completo(escena, refs, p["estilo"], feedback="the towel rail is missing")  # noqa: SLF001
    ok("PREVIOUS ATTEMPT" in texto and "Recreate it as it is" not in texto,
       "la rechazada es el intento anterior: de ella solo la gente, nunca el sitio")
    ok("OVERRIDES anything above" not in texto and "INSIDE the edit of reference image 1" in texto,
       "la nota se aplica DENTRO de la edición, sin mandar sobre la composición")
    ok(texto.index("the towel rail is missing") < texto.index("FINAL CHECK")
       and texto.rstrip().endswith("No watermarks."),
       "y el FINAL CHECK va detrás de la nota (lo que más pesa)")
    sin_editar = {"id": "S009", "set": "otro", "personajes": [], "narracion": "x", "prompt": "a street"}
    refs_sin = P6._referencias_escena(sin_editar, {"escenas": [sin_editar], "assets": {}},  # noqa: SLF001
                                      dirs, {"estilo": p["estilo"], "unidades": {}}, dirs["cache"], {},
                                      anteriores=[])
    texto_sin = P6._prompt_completo(sin_editar, refs_sin, p["estilo"], feedback="fix the hands")  # noqa: SLF001
    ok("HIGHEST PRIORITY" in texto_sin and "INSIDE the edit" not in texto_sin,
       "un plano que no edita, con la nota de siempre (byte a byte como hoy)")
    elegidas = [{"papel": "continuidad", "ruta": "/x/S001.png"},
                {"papel": "rechazada", "ruta": os.path.join(dirs["escenas"], "S002.png")},
                {"papel": "reparto", "nombre": "ana", "ruta": "/x/ana.png"},
                {"papel": "adjunta", "ruta": "/x/v3/escenas/S002.png"}]
    filtradas = P6._elegidas_en_edicion(elegidas, escena, dirs, p)  # noqa: SLF001
    igual([r["papel"] for r in filtradas], ["rechazada", "reparto"],
          "del corrector se quedan la rechazada y el reparto; fuera vecinos y versiones viejas")
    igual(filtradas[0].get("de_edicion"), 1, "y la rechazada, como intento anterior")


def prueba_base_fiel():
    seccion("17] las imágenes de referencia siguen la descripción (rama base-fiel)")
    import inspect                                           # noqa: PLC0415
    import moodboard                                         # noqa: PLC0415
    P6, carpeta, dirs, estilo, base = _p6_y_dirs()
    est = {"referencias": [estilo], "modo": "foto"}
    refs_estilo = [{"papel": "estilo", "ruta": estilo}]
    ref_escena = {"id": "BASE", "prompt": "the empty room", "personajes": [], "set": "sala",
                  "narracion": "", "referencia": "base", "ejes": list(T.EJES_REFERENCIA)}
    plano = {"id": "S001", "prompt": "the room", "personajes": [], "set": "sala", "narracion": "x"}
    t_ref = P6._prompt_completo(ref_escena, refs_estilo, est, formato="vertical")   # noqa: SLF001
    t_plano = P6._prompt_completo(plano, refs_estilo, est, formato="vertical")      # noqa: SLF001
    ok(T.cuadro_referencia("foto") in t_ref and "middle two thirds" not in t_ref,
       "la imagen de referencia pide la habitación entera, sin el «tercio central»")
    ok("middle two thirds" in t_plano and "reference of a whole room" not in t_plano,
       "un plano sigue con la línea del cuadro vertical de siempre")
    t_apaisado = P6._prompt_completo(ref_escena, refs_estilo, est, formato="apaisado")  # noqa: SLF001
    ok("reference of a whole room" not in t_apaisado, "y en apaisado no hay línea de cuadro")
    t_dibujo = P6._prompt_completo(ref_escena, refs_estilo, {"referencias": [estilo]},  # noqa: SLF001
                                   formato="vertical")
    ok(T.cuadro_referencia("ilustracion") in t_dibujo and "photograph" not in T.cuadro_referencia("ilustracion"),
       "en un vídeo de dibujo la referencia no se pide como fotografía")
    cambio = "the walls are warm white and the vanity is light oak"
    ref_base = {"papel": "base", "principal": True, "nombre": "Baño", "ruta": base,
                "modo": "espacio_que_cambia", "cambia": "acabados", "cambio": cambio}
    estado_esc = {"id": "ESTADO_paleta_1", "prompt": T.prompt_imagen_estado(cambio),
                  "personajes": [], "set": "bano", "narracion": "", "referencia": "estado"}
    con = P6._prompt_completo(estado_esc, [dict(ref_base, fijos=True)] + refs_estilo, est)  # noqa: SLF001
    sin = P6._prompt_completo(estado_esc, [ref_base] + refs_estilo, est)                    # noqa: SLF001
    fijos = T.FIJOS_ACABADOS.format(indice=1)
    igual(con.count(fijos), 2, "el estado de acabados: lo que no se nombra conserva su acabado "
                                "(en la presentación de la base y en el FINAL CHECK)")
    ok(fijos not in sin, "sin la clave `fijos` (los planos) no se añade nada")
    t_estado = P6._prompt_completo(estado_esc, [ref_base] + refs_estilo, est, formato="vertical")  # noqa: SLF001
    ok(T.CUADRO_ESTADO in t_estado and "reference of a whole room" not in t_estado,
       "un estado conserva el cuadro de la imagen que edita (sin gran angular nuevo)")
    otro = P6._prompt_completo(estado_esc, [dict(ref_base, fijos=True, cambia="estado")]  # noqa: SLF001
                               + refs_estilo, est)
    ok(fijos not in otro, "y en un estado que no es de acabados tampoco")
    igual(moodboard.ejes_de_plano(ref_escena), list(T.EJES_REFERENCIA),
          "la lámina de una referencia: exterior y objeto, sin caras, cuerpos ni la sala amueblada")
    import tempfile                                          # noqa: PLC0415
    from PIL import Image                                    # noqa: PLC0415
    carpeta_l = tempfile.mkdtemp()
    laminas = []
    for eje in ("cara", "cuerpos", "interior", "exterior", "objeto", "diagrama"):
        ruta_l = os.path.join(carpeta_l, f"{eje}_ab12cd34ef.png")
        Image.new("RGB", (64, 40), (30, 60, 90)).save(ruta_l)
        laminas.append(ruta_l)
    est_l = {"estilo": {"referencias": laminas, "modo": "foto"}}
    cache_l = tempfile.mkdtemp()
    ref_l = P6._referencias_estilo(est_l, cache_l, ref_escena)            # noqa: SLF001
    plano_l = P6._referencias_estilo(est_l, cache_l, dict(plano))         # noqa: SLF001
    igual(ref_l[0].get("cuantas"), 2, "sin moodboard, la referencia solo lleva las láminas exterior y objeto")
    igual(plano_l[0].get("cuantas"), 6, "y un plano, las seis como siempre")
    ok("no TV cabinet" in T.prompt_imagen_base({"descripcion": "a living room"}, {"modo": "recorrido"}),
       "la base prohíbe lo que la descripción no nombra (la tele, el mueble de TV)")
    ok("cara" in moodboard.ejes_de_plano({"set": "sala"}),
       "la de un plano, como siempre")
    amb = dict(ref_escena, referencia="ambiente")
    t_amb = P6._prompt_completo(amb, refs_estilo, est, formato="vertical")  # noqa: SLF001
    ok(T.cuadro_referencia("foto", True) in t_amb and "from the entrance" not in t_amb,
       "un ambiente secundario: la cámara dentro de él, no en la entrada (la cocina abierta)")
    igual(T.prompt_imagen_base({"descripcion": "a kitchen"}, {"modo": "recorrido"}).count(T.ENCUADRE_BASE), 1,
          "la base de siempre conserva su encuadre")
    ok(T.ENCUADRE_AMBIENTE in T.prompt_imagen_base({"descripcion": "a kitchen"}, {"modo": "recorrido"},
                                                   ambiente=True),
       "y la de un ambiente secundario lleva el suyo")
    ok("nota" in inspect.signature(P6.generar_imagen_estado).parameters
       and "nota" in inspect.signature(P6.prompt_y_refs_de_estado).parameters,
       "la imagen de un estado acepta la corrección de esta vez")


def main():
    print("PRUEBA DEL TIPO DE RELATO")
    prueba_modos_y_lineas()
    prueba_resolver()
    prueba_catalogo_igual_sin_modo()
    prueba_catalogo_con_modo()
    prueba_referencias_y_prompt()
    prueba_revisor()
    prueba_parrilla()
    prueba_presets()
    prueba_imagen_base()
    prueba_ambientes_y_camara()
    prueba_retoque_acotado()
    prueba_base_fiel()
    prueba_revision_03_11()
    import shutil                                            # noqa: PLC0415
    shutil.rmtree(_TEMPORAL, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"TIPO DE RELATO OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

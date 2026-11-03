"""
ESTADOS Y ENCUADRE DE LAS LINEAS «VISUAL:» DE LA PARRILLA (rama parrilla-estados, 03-11-2026).

La prueba real del P01 del Lote 15 («Imágenes: guion», «un espacio que cambia
(objeto)»): la toma 5 puso el espejo nuevo en el baño del «antes» y la 6 salió
idéntica a la 1, porque las líneas de la Parrilla llegaban sin estado y cada
plano editaba la base con «nada cambia»; y una línea sin cámara recibía una
carta sorteada (un retrato, unas manos) que metía a una persona en el plano.

Lo que se comprueba, en memoria y sin el CLI ni pagar nada:

  1. LA PARRILLA lee «Estado:» en cada escena y la sección ESTADOS DEL ESPACIO.
  2. EL ENCARGO recibe el estado de cada escena y los estados, con sus avisos.
  3. EL GUION VISUAL guarda los estados y cada plano casado lleva el de su escena.
  4. LOS ESTADOS DE LA PARRILLA MANDAN sobre los del catálogo, y solo en modo guion.
  5. EL PLANO edita la imagen de SU estado.
  6. SIN CÁMARA, SIN CARTA SORTEADA, solo en los vídeos nuevos (`sin_sorteo`).
  7. AL CREAR el vídeo (app.py): se guardan los estados y `sin_sorteo`; sin
     líneas «Visual:», nada (regla 1). Y editar un estado de la Parrilla en
     español lo cambia en el guion visual.

    python pasos/prueba_parrilla_estados.py
"""
import copy
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import guion_visual as G  # noqa: E402
import parrilla as P  # noqa: E402
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


GUION = """P01 — El espejo que cambia el baño
Cliente / proyecto: Casas con diseño
Uso: exacto
Formato: vertical
Duración: 35 s
Tipo de relato: espacio_que_cambia (objeto)
Imágenes: guion

ESPACIO FIJO
- Sitio: Baño pequeño
- Descripción: a small bathroom with white tiles

ESTADOS DEL ESPACIO
- antes: [vacío: es la imagen base tal cual]
- Después: the old mirror is replaced by a round backlit mirror,
  and the vanity light is warm

ESCENA 1
Estado: antes
Visual: The bathroom as it is, wide shot. No people in the shot.
Voz: «Tu baño se ve pequeño.»

ESCENA 2
Estado: Después
Visual: The new round mirror glowing. No people in the shot.
Visual: Close-up of the backlit edge.
Voz: «Un espejo redondo lo cambia todo.»

ESCENA 3
Visual: The bathroom again, wide.
Voz: «Escríbenos.»

PARA EL ENCARGO
- Material: Tu baño se ve pequeño. Un espejo redondo lo cambia todo. Escríbenos.
- Duración: 35 s · Formato: vertical

AVISOS
- ninguno
"""


def prueba_parrilla():
    seccion("1] la Parrilla lee «Estado:» y ESTADOS DEL ESPACIO")
    g = P.leer_guion(GUION)
    igual(G.normalizar_estados(g["estados"]), {"antes": "", "despues": "the old mirror is replaced by a round backlit mirror, "
                                                "and the vanity light is warm"},
          "los estados: «vacío» es la base, una línea que sigue se suma, sin tildes en la etiqueta")
    igual([e.get("estado") for e in g["escenas"]], ["antes", "despues", ""], "cada escena con su estado")
    igual([len(e["visual"]) for e in g["escenas"]], [1, 2, 1], "las líneas «Visual:» siguen como siempre")
    ok(g["duracion_s"] == 35 and g["uso"] == "exacto", "y la cabecera, igual")
    plantilla = P.leer_guion(GUION.replace("Estado: antes", "Estado: … (solo con ESTADOS DEL ESPACIO; si no, quita la línea)"))
    igual(plantilla["escenas"][0]["estado"], "", "el hueco de plantilla no es un estado")
    sin = P.leer_guion(GUION.split("ESTADOS DEL ESPACIO")[0] + "ESCENA 1\nVisual: algo\nVoz: «hola»\n")
    igual(sin["estados"], {}, "un guion sin la sección: sin estados")
    formato = P.prompt_para_otra_ia()
    ok("ESTADOS DEL ESPACIO" in formato and "Estado:" in formato, "el formato que se le pide a la IA los explica")

    seccion("2] el Encargo recibe el estado de cada escena")
    enc = P.encargo_de(g)
    igual([v.get("estado") for v in enc["visuales"]], ["antes", "despues", None], "las escenas, con su estado")
    igual(sorted(enc["estados"]), ["antes", "despues"], "y los estados")
    ok(not any("ESTADOS" in a for a in enc["avisos"]), f"sin avisos de estados ({enc['avisos']})")
    raro = P.encargo_de(P.leer_guion(GUION.replace("Estado: Después", "Estado: obra")))
    ok(any("obra" in a for a in raro["avisos"]), "un estado que no está en la sección: lo avisa")
    voz = P.encargo_de(P.leer_guion(GUION.replace("Imágenes: guion\n", "")))
    ok(any("solo se usan" in a for a in voz["avisos"]), "con estados pero sin «Imágenes: guion»: lo avisa")
    sueltos = P.encargo_de(P.leer_guion(GUION.split("ESTADOS DEL ESPACIO")[0] + GUION.split("ESCENA 1", 1)[1].join(["ESCENA 1", ""])))
    ok(any("falta la sección" in a for a in sueltos["avisos"]), "con «Estado:» y sin la sección: lo avisa")
    viejo = P.encargo_de(P.leer_guion(GUION.split("ESTADOS DEL ESPACIO")[0]
                                      + "ESCENA 1\nVisual: algo\nVoz: «hola»\n"))
    ok("estados" not in viejo and all("estado" not in v for v in viejo["visuales"]),
       "un guion de los de antes llega igual que antes (regla 1)")
    return enc


def prueba_guion_visual(enc):
    seccion("3] el guion visual guarda los estados y casa cada plano con el suyo")
    igual(G.normalizar_estados({"Antes": "(none)", "Después": "a round mirror", "": "x", "paleta 1": "sage"}),
          {"antes": "", "despues": "a round mirror", "paleta_1": "sage"}, "normalizar los estados")
    igual(G.normalizar_estados("no es un dict"), {}, "lo que no es un objeto: nada")
    visuales = G.normalizar_visuales(enc["visuales"])
    igual([v.get("estado") for v in visuales], ["antes", "despues", None], "normalizar_visuales conserva el estado")
    gv = G.normalizar({"origen": "parrilla", "planos": [], "visuales": visuales, "estados": enc["estados"],
                       "sin_sorteo": True})
    ok(gv["estados"] == G.normalizar_estados(enc["estados"]) and gv["sin_sorteo"] is True, "se guardan")
    igual(set(G.normalizar({"origen": "parrilla", "planos": [], "visuales": visuales})),
          {"origen", "planos", "aprobado", "visuales"}, "sin estados ni sin_sorteo, ninguna clave de más (regla 1)")
    bloques = [{"id": "B001", "texto": "Tu baño se ve pequeño."},
               {"id": "B002", "texto": "Un espejo redondo lo cambia todo."},
               {"id": "B003", "texto": "Escríbenos."}]
    planos, avisos = G.casar(visuales, bloques)
    igual([(p["bloque"], p.get("estado")) for p in planos],
          [("B001", "antes"), ("B002", "despues"), ("B002", "despues"), ("B003", None)],
          f"cada plano con el estado de su escena ({avisos})")
    ef, origen = G.efectivo({"imagenes": "guion", "guion_visual": gv}, bloques)
    ok(origen == "parrilla" and [p.get("estado") for p in ef] == ["antes", "despues", "despues", None],
       "y valen solas, con su estado")
    return gv


def prueba_mandan(gv):
    import p6_assets as P6
    seccion("4] los estados de la Parrilla mandan, y solo en modo guion")
    catalogo = {"beats": [{"set": "bano", "cambio": "a square mirror", "estado": "reforma"},
                          {"set": "bano", "cambio": "", "estado": ""}]}
    igual(T.estados_del_catalogo(catalogo, "bano"), {"reforma": "a square mirror"},
          "sin la Parrilla, los del catálogo (como siempre)")
    cambia = {"modo": "espacio_que_cambia", "cambia": "objeto"}
    con = P6._catalogo_de({"imagenes": "guion", "guion_visual": gv, "catalogo": catalogo, "tipo_relato": cambia}, None)
    igual(T.estados_del_catalogo(con, "bano"), {"despues": gv["estados"]["despues"]},
          "con la Parrilla, solo los suyos (el «antes» vacío es la base: no lleva imagen)")
    voz = P6._catalogo_de({"guion_visual": gv, "catalogo": catalogo, "tipo_relato": cambia}, None)
    ok("estados_fijos" not in voz, "si las imágenes siguen la voz, no se meten")
    sin = P6._catalogo_de({"imagenes": "guion", "guion_visual": dict(gv, estados={}), "catalogo": catalogo,
                           "tipo_relato": cambia}, None)
    ok("estados_fijos" not in sin, "sin estados en la Parrilla, el catálogo sale sin una clave de más (regla 1)")
    ok("estados_fijos" not in catalogo, "y el catálogo guardado no se toca")
    return con


def prueba_plano(gv, con):
    import p6_assets as P6
    seccion("5] el plano edita la imagen de SU estado")
    estados = T.estados_del_catalogo(con, "bano")
    beat = G.estado_de_linea({"estado": "despues"}, estados)
    igual(beat["estado"], "despues", "la línea «despues» lleva su estado")
    ok("round backlit mirror" in beat["cambio"], "y su cambio, el de la Parrilla")
    igual(G.estado_de_linea({"estado": "antes"}, estados), {"cambio": "", "estado": ""},
          "la línea «antes»: la base tal cual")
    relato = T.resolver({"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"}})
    escena = {"id": "S002", "set": "bano"}
    P6._marcar_edicion(escena, beat, relato, "bano", "ilustracion", {"bano#despues": "relato/despues.png"})
    ok(escena.get("editar_base") and escena.get("base_clave") == "bano#despues"
       and escena.get("base") == "relato/despues.png", f"edita la imagen del «después» ({escena})")
    escena = {"id": "S001", "set": "bano"}
    P6._marcar_edicion(escena, G.estado_de_linea({"estado": "antes"}, estados), relato, "bano", "ilustracion",
                       {"bano": "relato/base.png"})
    ok(escena.get("editar_base") and not escena.get("base_clave") and escena.get("base") == "relato/base.png",
       "y la del «antes», la base")


def prueba_sin_sorteo():
    import p6_assets as P6
    seccion("6] una línea sin cámara no recibe carta sorteada (solo en los vídeos nuevos)")

    def escenas():
        return [{"id": "S001", "carta": "retrato", "encuadre": "portrait of a person", "abstracta": True,
                 "linea_gv": {"visual": "the bathroom, no people"}},
                {"id": "S002", "carta": "manos", "encuadre": "hands close-up",
                 "linea_gv": {"visual": "the mirror", "camara": "wide shot from the door"}},
                {"id": "S003", "carta": "manos", "encuadre": "hands close-up",
                 "linea_gv": {"visual": "the tap"}},
                {"id": "S004", "carta": "aereo", "encuadre": "aerial view"}]

    viejas = escenas()
    P6._aplicar_lineas_gv(viejas, {})
    igual([(e.get("carta"), e.get("encuadre")) for e in viejas],
          [("retrato", "portrait of a person"), ("manos", "wide shot from the door"),
           ("manos", "hands close-up"), ("aereo", "aerial view")],
          "un vídeo de antes: la carta sorteada se queda (sus imágenes no cambian)")
    nuevas = escenas()
    P6._aplicar_lineas_gv(nuevas, {}, sin_sorteo=True, forzadas={"S003"})
    igual([(e.get("carta"), e.get("encuadre")) for e in nuevas],
          [(None, None), ("manos", "wide shot from the door"), ("manos", "hands close-up"),
           ("aereo", "aerial view")],
          "uno nuevo: sin cámara no hay carta; con cámara, la suya; la forzada a mano y el plano sin línea, igual")
    ok(not P6._con_encuadre(nuevas[0]), "y sin carta el prompt no lleva SHOT TYPE")
    ok(not nuevas[0].get("abstracta") and nuevas[0]["personajes"] == [], "ni abstracta ni gente que la línea no pide")
    relato = T.resolver({"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"}})
    ok(T.plano_se_edita(dict(nuevas[0], set="bano"), relato, "bano",
                        P6._familia_del_plano(nuevas[0], "ilustracion")),
       "sin la carta de retrato, en un espacio que cambia el plano edita la base (misma cámara)")
    detalle = {"id": "S009", "linea_gv": {"visual": "Close-up of the new mirror's brass frame. No people."}}
    igual(P6._familia_del_plano(detalle, "ilustracion"), "cerca",
          "sin cámara ni carta, una línea «Close-up of…» es un detalle (no edita la base)")
    igual(P6._familia_del_plano({"id": "S010", "carta": "retrato", "linea_gv": {"visual": "Close-up of x"}},
                                "ilustracion"), P6._familia_de_carta("retrato", "ilustracion"),
          "con su carta (vídeos de antes), la de la carta, como siempre")


def prueba_al_crear():
    seccion("7] al crear el vídeo y al editar un estado (app.py)")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    from nucleo import Estado, Proyecto                           # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_pe_")
    servidor.fijar_raiz_proyectos(base)
    bloques = [{"id": "B001", "texto": "Tu baño se ve pequeño."},
               {"id": "B002", "texto": "Un espejo redondo lo cambia todo."}]
    real = servidor._bloques_del_guion
    servidor._bloques_del_guion = lambda _ctx: bloques
    try:
        pid = Proyecto.crear(base, "sin lineas").id
        Estado(servidor.contexto(pid).proyecto)
        ctx = servidor.contexto(pid)
        servidor._opciones_al_crear(ctx, "", {"estados": {"despues": "a mirror"}})
        ok("guion_visual" not in (ctx.estado.params("assets") or {}),
           "estados sin líneas «Visual:»: no se escribe nada (regla 1)")
        pid = Proyecto.crear(base, "con lineas").id
        Estado(servidor.contexto(pid).proyecto)
        ctx = servidor.contexto(pid)
        servidor._opciones_al_crear(ctx, "", {"imagenes": "guion", "estados": {"antes": "", "despues": "a mirror"},
                                              "visuales": [
            {"voz": "Tu baño se ve pequeño.", "visual": ["the bathroom"], "estado": "antes"},
            {"voz": "Un espejo redondo lo cambia todo.", "visual": ["the mirror"], "estado": "despues"}]})
        gv = (ctx.estado.params("assets") or {}).get("guion_visual") or {}
        ok(gv.get("sin_sorteo") is True and gv.get("estados") == {"antes": "", "despues": "a mirror"},
           "con líneas: se guardan los estados y que no se sortee la carta")
        f = servidor._ficha_guion_visual(ctx)
        igual([p.get("estado") for p in f["propuesta"]], ["antes", "despues"], "la propuesta casada lleva el estado")
        # guardar el guion visual a mano conserva los estados
        servidor.guardar_guion_visual(pid, {"planos": [{"bloque": "B001", "visual": "otra", "estado": "despues"}]})
        gv = (ctx.estado.params("assets") or {}).get("guion_visual") or {}
        ok(gv.get("estados") == {"antes": "", "despues": "a mirror"} and gv.get("sin_sorteo") is True,
           "guardar el guion visual a mano no pierde los estados")
        # editar un estado de la Parrilla en español: cambia el del guion visual
        import p6_assets as P6                                    # noqa: PLC0415
        params = copy.deepcopy(ctx.estado.params("assets") or {})
        params["tipo_relato"] = {"modo": "espacio_que_cambia", "cambia": "objeto"}
        params["espacio_fijo"] = {"sitio": "Baño", "descripcion": "a small bathroom"}
        ctx.estado.set_params("assets", params)
        sitio, pedidos = P6.estados_del_relato(ctx.proyecto, ctx.estado.params("assets"))
        igual(pedidos, {"despues": "a mirror"}, "el vídeo pide la imagen del «después» de la Parrilla")
        mod = servidor._traducciones()
        reales = (mod.al_ingles, mod.guardar)
        mod.al_ingles = lambda es, anterior="", cwd=None: "a round backlit mirror"
        mod.guardar = lambda raiz, textos: None
        lanzar_real = servidor._lanzar_traduccion

        def en_el_acto(ctx_, tipo, correr, estado_relato=None):
            correr()
            return True
        servidor._lanzar_traduccion = en_el_acto
        try:
            servidor.editar_estado_relato(pid, {"estado": "despues", "es": "un espejo redondo con luz"})
        finally:
            mod.al_ingles, mod.guardar = reales
            servidor._lanzar_traduccion = lanzar_real
        gv = (ctx.estado.params("assets") or {}).get("guion_visual") or {}
        igual(gv.get("estados", {}).get("despues"), "a round backlit mirror",
              "editar en español el estado de la Parrilla lo cambia en el guion visual")
        ok(not ((ctx.estado.params("assets") or {}).get("catalogo") or {}).get("beats"),
           "sin tocar ningún tramo del reparto")
    finally:
        servidor._bloques_del_guion = real


def prueba_revision():
    import p6_assets as P6
    seccion("8] lo que encontró la revisión del 03-11")
    for texto in ("(vacío)", "vacío: es la imagen base tal cual", "No changes.", "empty", "N/A",
                  "same as base", "[la base tal cual]", "—", "none"):
        igual(G.normalizar_estados({"antes": texto}), {"antes": ""}, f"«{texto}» es la base tal cual")
    for texto in ("nada de azulejos viejos: white tiles everywhere", "base cabinet painted sage green"):
        igual(G.normalizar_estados({"despues": texto})["despues"], texto, f"«{texto[:30]}…» es un cambio de verdad")
    g = P.leer_guion(GUION.replace("- antes: [vacío: es la imagen base tal cual]", "- antes: (vacío)"))
    igual(G.normalizar_estados(P.encargo_de(g)["estados"]).get("antes"), "",
          "el «antes» con «(vacío)» no pide una imagen de pago")
    sin_vineta = GUION.replace("- antes: [vacío: es la imagen base tal cual]\n- Después:", "antes:\n2. Después:")
    igual(sorted(P.leer_guion(sin_vineta)["estados"]), ["antes", "despues"], "los estados sin viñeta o numerados también")
    g = P.leer_guion(GUION.replace("Estado: Después", "Estado: después — espejo nuevo"))
    igual(g["escenas"][1]["estado"], "despues", "«Estado: después — espejo nuevo» es «despues»")
    gv = G.normalizar({"origen": "parrilla", "planos": [], "estados": {"despues": "a mirror"}})
    producto = P6._catalogo_de({"imagenes": "guion", "guion_visual": gv,
                                "tipo_relato": {"modo": "producto"}, "catalogo": {"beats": []}}, None)
    ok("estados_fijos" not in producto, "en «producto» los estados de la Parrilla no se usan (lo que avisa el Encargo)")
    cambia = P6._catalogo_de({"imagenes": "guion", "guion_visual": gv,
                              "tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"}, "catalogo": {"beats": []}}, None)
    ok("estados_fijos" in cambia, "en «un espacio que cambia», sí")
    # la lectura guardada de antes de esta rama se renueva al pasar al Encargo
    raiz = tempfile.mkdtemp(prefix="estudio_pe_parrilla_")
    cid = "cl_estados"
    P._anadir_textos(raiz, cid, "", "Lote", [GUION], {"tipo": "pedir"})
    datos = P._leer(raiz, cid)
    g0 = datos["matrices"][0]["guiones"][0]
    viejo = dict(g0.get("leido") or P.leer_guion(GUION))
    viejo.pop("estados", None)
    g0["leido"] = viejo
    P._guardar(raiz, cid, datos)
    enc = P.pasar_al_encargo(raiz, cid, g0["id"])
    ok("despues" in (enc.get("estados") or {}), "un guion leído antes de esta rama pasa al Encargo con sus estados")


def main():
    print("PRUEBA DE LOS ESTADOS Y EL ENCUADRE DE LA PARRILLA")
    enc = prueba_parrilla()
    gv = prueba_guion_visual(enc)
    con = prueba_mandan(gv)
    prueba_plano(gv, con)
    prueba_sin_sorteo()
    prueba_al_crear()
    prueba_revision()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PARRILLA ESTADOS OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

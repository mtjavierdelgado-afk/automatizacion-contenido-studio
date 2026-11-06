"""
LA «MARCA: ✗ / ✓» DE LAS ESCENAS DE LA PARRILLA (rama parrilla-marca, 05-11-2026).

Una escena que enseña lo que NO se hace (✗) o lo que SÍ (✓) lleva en sus
planos una cruz roja o un check verde, arriba en una esquina, que salta con la
primera palabra («pop»). Se mueve, se cambia de tamaño o se quita a mano en
«✨ Elementos de esta imagen». Nunca redibuja una imagen, y un vídeo sin
«Marca:» sale igual que antes (regla 1).

Lo que se comprueba, en memoria y sin el CLI ni pagar nada:

  1. LA PARRILLA lee «Marca:» en cada escena (con signo o con palabra), y el
     hueco de la plantilla no es una marca.
  2. LAS INSTRUCCIONES: la regla 13 y la línea del formato, iguales en la
     Parrilla y en la guía «El formato del guion».
  3. EL ENCARGO recibe la marca de cada escena, con sus avisos; un guion de los
     de antes llega igual.
  4. EL GUION VISUAL la guarda y cada plano casado lleva la de su escena; no
     entra en el prompt de ninguna imagen.
  5. EL ELEMENTO: la cruz o el check, arriba a la derecha, en la primera
     palabra y con «pop»; lo guardado manda (también una lista vacía).
  6. LAS RUTAS de «✨ Elementos de esta imagen» (app.py): la enseñan, guardarla
     tal cual no escribe nada, quitarla se queda quitada y sumar no la pierde.

    python pasos/prueba_parrilla_marca.py
"""
import copy
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import elementos_video as EV  # noqa: E402
import guion_visual as G  # noqa: E402
import parrilla as P  # noqa: E402

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


GUION = """P07 — Cómo colgar un cuadro
Cliente / proyecto: Ferretería Lima
Uso: exacto
Formato: vertical
Duración: 20 s
Imágenes: guion

ESCENA 1
Marca: ✗
Visual: A man hammering a nail straight into a tiled wall, cracks appear.
Visual: Close-up of the cracked tile.
Voz: «Así no se cuelga un cuadro.»

ESCENA 2
Marca: ✓
Visual: The same man drilling with a tile bit and a plug.
Voz: «Con taco y la broca de azulejo, sin romper nada.»

ESCENA 3
Visual: The picture hanging straight on the wall.
Voz: «Escríbenos.»

PARA EL ENCARGO
- Material: Así no se cuelga un cuadro. Con taco y la broca de azulejo. Escríbenos.
"""


def prueba_parrilla():
    seccion("1] la Parrilla lee «Marca:» en cada escena")
    for valor, esperado in (("✗", "no"), ("✘", "no"), ("❌ mal hecho", "no"), ("x", "no"), ("X", "no"),
                            ("no", "no"), ("✓", "si"), ("✔️", "si"), ("✅ (bien)", "si"), ("sí", "si"),
                            ("bien", "si"), ("✗ o ✓ (solo si la escena enseña lo que no se hace o lo que sí; "
                                             "si no, quita la línea)", ""),
                            ("✗ | ✓", ""), ("…", ""), ("", ""), ("quizá", ""), ("xbox", "")):
        igual(P.marca_de_escena(valor), esperado, f"«{valor[:30]}» -> «{esperado}»")
    g = P.leer_guion(GUION)
    igual([e.get("marca") for e in g["escenas"]], ["no", "si", ""], "cada escena con su marca")
    igual([len(e["visual"]) for e in g["escenas"]], [2, 1, 1], "las líneas «Visual:» siguen como siempre")
    igual(g["escenas"][0]["voz"], "«Así no se cuelga un cuadro.»", "y la voz, igual")
    ok(g["marca"] == {"mostrar": "", "evitar": "", "otras": ""} or not any(g["marca"].values()),
       "«Marca:» de una escena no se confunde con MARCA DEL CLIENTE")
    con_estado = P.leer_guion(GUION.replace("ESCENA 1\nMarca: ✗", "ESCENA 1\nEstado: antes\nMarca: ✗"))
    igual((con_estado["escenas"][0]["estado"], con_estado["escenas"][0]["marca"]), ("antes", "no"),
          "con «Estado:» y «Marca:» a la vez, las dos")

    seccion("2] las instrucciones, iguales en la Parrilla y en la guía")
    formato = P.prompt_para_otra_ia()
    ok("13. \"Marca\"" in formato and "Marca: ✗ o ✓" in formato, "la regla 13 y la línea del formato")
    ok(formato.index("Estado: …") < formato.index("Marca: ✗ o ✓") < formato.index("Visual: …"),
       "en el formato, «Marca:» va después de «ESCENA n» y antes de «Visual»")
    import guias                                                  # noqa: PLC0415
    igual(guias.GUIAS["guion_parrilla"]["prompt_ia"], formato, "la copia de la guía «El formato del guion», idéntica")
    plantilla = P.leer_guion(GUION.replace("Marca: ✗\n", "Marca: ✗ o ✓ (solo si la escena enseña lo que no se "
                                           "hace o lo que sí; si no, quita la línea)\n"))
    igual(plantilla["escenas"][0]["marca"], "", "el hueco de la plantilla tal cual no es una marca")


def prueba_encargo():
    seccion("3] el Encargo recibe la marca de cada escena")
    enc = P.encargo_de(P.leer_guion(GUION))
    igual([v.get("marca") for v in enc["visuales"]], ["no", "si", None], "las escenas, con su marca")
    ok(not any("Marca" in a for a in enc["avisos"]), f"sin avisos de marca ({enc['avisos']})")
    voz = P.encargo_de(P.leer_guion(GUION.replace("Imágenes: guion\n", "")))
    ok(any("solo salen si las imágenes siguen el guion" in a for a in voz["avisos"]),
       "con marcas pero sin «Imágenes: guion»: lo avisa")
    sin_visual = P.encargo_de(P.leer_guion(GUION.replace(
        "ESCENA 3\nVisual: The picture hanging straight on the wall.\n", "ESCENA 3\nMarca: ✓\n")))
    ok(any("sin líneas «Visual:»" in a for a in sin_visual["avisos"]), "una marca sin «Visual:»: lo avisa")
    viejo = P.encargo_de(P.leer_guion(GUION.replace("Marca: ✗\n", "").replace("Marca: ✓\n", "")))
    ok(all("marca" not in v for v in viejo["visuales"]), "un guion sin «Marca:» llega igual que antes (regla 1)")
    # la lectura guardada de antes de esta rama se renueva al leer y al pasar al Encargo
    raiz = tempfile.mkdtemp(prefix="estudio_pm_parrilla_")
    cid = "cl_marca"
    P._anadir_textos(raiz, cid, "", "Lote", [GUION], {"tipo": "pedir"})
    datos = P._leer(raiz, cid)
    g0 = datos["matrices"][0]["guiones"][0]
    viejo = copy.deepcopy(g0.get("leido") or P.leer_guion(GUION))
    for e in viejo["escenas"]:
        e.pop("marca", None)
    g0["leido"] = viejo
    P._guardar(raiz, cid, datos)
    ficha = P.leer(raiz, cid, g0["id"])
    igual([v.get("marca") for v in ficha["encargo"][0]["visuales"]], ["no", "si", None],
          "un guion leído antes de esta rama enseña sus marcas en la ficha")
    enc2 = P.pasar_al_encargo(raiz, cid, g0["id"])
    igual([v.get("marca") for v in enc2["visuales"]], ["no", "si", None], "y pasa al Encargo con ellas")
    return enc


def prueba_guion_visual(enc):
    seccion("4] el guion visual la guarda y cada plano lleva la de su escena")
    visuales = G.normalizar_visuales(enc["visuales"])
    igual([v.get("marca") for v in visuales], ["no", "si", None], "normalizar las escenas conserva la marca")
    igual(G.normalizar_visuales([{"voz": "x", "visual": ["y"], "marca": "quizá"}])[0].get("marca"), None,
          "una marca rara se descarta")
    igual([v.get("marca") for v in G.visuales_de_parrilla(P.leer_guion(GUION)["escenas"])], ["no", "si", None],
          "desde las escenas de la Parrilla, también")
    bloques = [{"id": "B001", "texto": "Así no se cuelga un cuadro."},
               {"id": "B002", "texto": "Con taco y la broca de azulejo, sin romper nada."},
               {"id": "B003", "texto": "Escríbenos."}]
    planos, avisos = G.casar(visuales, bloques)
    igual([(p["bloque"], p.get("marca")) for p in planos],
          [("B001", "no"), ("B001", "no"), ("B002", "si"), ("B003", None)],
          "casar: cada plano con la marca de SU escena (las dos líneas de la escena 1)")
    gv = G.normalizar({"origen": "parrilla", "planos": planos, "aprobado": True})
    igual([p.get("marca") for p in gv["planos"]], ["no", "no", "si", None], "guardar los planos conserva la marca")
    efectivos, origen = G.efectivo({"imagenes": "guion", "guion_visual": {"origen": "parrilla", "visuales": visuales}},
                                   bloques)
    igual([p.get("marca") for p in efectivos or []], ["no", "no", "si", None],
          f"los planos que mandan (de la Parrilla, {origen}) llevan la marca")
    # LA MARCA NO ENTRA EN EL PROMPT DE NINGUNA IMAGEN (ni en su firma)
    import p6_assets as P6                                       # noqa: PLC0415
    import inspect                                               # noqa: PLC0415
    fuente = inspect.getsource(P6)
    ok("marca\"" not in fuente.replace("marcas\"", "") and "[\"marca\"]" not in fuente,
       "p6 (prompts, firmas) no lee la marca en ningún sitio")


def prueba_elemento():
    seccion("5] el elemento: cruz o check, arriba a la derecha, en la primera palabra")
    cruz = EV.de_marca({"linea_gv": {"visual": "x", "marca": "no"}})
    igual([(e["tipo"], e["icono"], e["color"], e["palabra"], e["entrada"]) for e in cruz],
          [("icono", "cruz", "alerta", 0, "pop")], "✗ -> cruz roja (alerta), en la primera palabra, con «pop»")
    check = EV.de_marca({"linea_gv": {"visual": "x", "marca": "si"}}, vertical=True)
    igual([(e["icono"], e["color"]) for e in check], [("check", "bien")], "✓ -> check verde (bien)")
    igual((cruz[0]["x"], cruz[0]["y"]), EV.POSICIONES["horizontal"]["arriba_derecha"], "arriba a la derecha (horizontal)")
    igual((check[0]["x"], check[0]["y"]), EV.POSICIONES["vertical"]["arriba_derecha"], "y en vertical, la suya")
    igual(EV.de_marca({"linea_gv": {"visual": "x"}}), [], "sin marca, nada")
    igual(EV.de_marca({}), [], "sin línea del guion, nada")
    ok(cruz[0]["icono"] in __import__("grafismo").ICONOS and check[0]["icono"] in __import__("grafismo").ICONOS,
       "los dos iconos existen en el grafismo")
    escena = {"id": "S001", "t_in": 2.0, "t_out": 5.0, "narracion": "Así no se cuelga",
              "marcas": [[2.4, 2.6], [2.6, 2.8], [2.8, 3.0], [3.0, 3.4]],
              "linea_gv": {"visual": "x", "marca": "no"}}
    desde, hasta = EV.momento(cruz[0], escena, 3.0)
    ok(abs(desde - 0.4) < 1e-6 and abs(hasta - 2.96) < 1e-6,
       f"salta en la primera palabra y se queda el plano entero ({desde}–{hasta})")
    svg = EV.fragmento(escena, cruz, (1080, 1920), {}, 3.0)
    ok(svg and "#ff3b30" in svg, "dibujada: un svg con el rojo de «alerta»")
    seccion("   lo guardado manda")
    uid = "escena:S001"
    igual(EV.de_plano_o_marca({}, uid, escena), cruz, "sin elementos guardados: la marca")
    igual(EV.de_plano_o_marca({"unidades": {uid: {"montaje": {"movimiento": "vivo"}}}}, uid, escena), cruz,
          "con otro ajuste del plano pero sin elementos: la marca")
    igual(EV.de_plano_o_marca({"unidades": {uid: {"elementos": []}}}, uid, escena), [],
          "con la lista vacía guardada (la quitaron): nada")
    movida = [dict(cruz[0], x=0.2, tam=0.3)]
    igual(EV.de_plano_o_marca({"unidades": {uid: {"elementos": movida}}}, uid, escena), EV.limpiar(movida),
          "movida o con otro tamaño: la guardada")
    sin = dict(escena, linea_gv={"visual": "x"})
    for params in ({}, {"unidades": {uid: {"elementos": movida}}}, {"unidades": {uid: {"montaje": {}}}},
                   {"unidades": {uid: {"elementos": []}}}):
        igual(EV.de_plano_o_marca(params, uid, sin), EV.de_plano(params, uid),
              f"sin «Marca:», lo mismo que antes ({list((params.get('unidades') or {}).get(uid, {}))})")


def prueba_rutas():
    seccion("6] «✨ Elementos de esta imagen» (app.py)")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    from nucleo import Estado, Proyecto                           # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_pm_")
    servidor.fijar_raiz_proyectos(base)
    escenas = [{"id": "S001", "t_in": 0.0, "t_out": 2.0, "narracion": "Así no se cuelga",
                "linea_gv": {"visual": "x", "marca": "no"}},
               {"id": "S002", "t_in": 2.0, "t_out": 4.0, "narracion": "Con taco",
                "linea_gv": {"visual": "y", "marca": "si"}},
               {"id": "S003", "t_in": 4.0, "t_out": 6.0, "narracion": "Escríbenos",
                "linea_gv": {"visual": "z"}}]
    plan = {"formato": "horizontal", "escenas": escenas}
    reales = (servidor._escenas_del_video, servidor._es_vertical)
    servidor._escenas_del_video = lambda _ctx: (plan, escenas)
    servidor._es_vertical = lambda _ctx, _plan: False
    try:
        pid = Proyecto.crear(base, "marca").id
        Estado(servidor.contexto(pid).proyecto)
        ctx = servidor.contexto(pid)
        antes = copy.deepcopy(ctx.estado.params("callouts"))
        leido = servidor.leer_elementos_de_planos(pid)
        igual(sorted(leido["planos"]), ["S001", "S002"], "salen la cruz y el check, y en S003 nada")
        igual(leido["planos"]["S001"][0]["icono"], "cruz", "en S001, la cruz")
        igual(ctx.estado.params("callouts"), antes, "enseñarlos no escribe nada (regla 1)")
        r = servidor.cambiar_elementos_de_plano(pid, "S001", {"elementos": leido["planos"]["S001"]})
        ok(not r["cambiado"] and ctx.estado.params("callouts") == antes,
           "guardar la marca tal cual sale no escribe nada (la firma no se mueve)")
        movida = [dict(leido["planos"]["S001"][0], x=0.3, tam=0.25)]
        servidor.cambiar_elementos_de_plano(pid, "S001", {"elementos": movida})
        guardados = ((ctx.estado.params("callouts") or {}).get("unidades") or {}).get("escena:S001", {})
        igual(guardados.get("elementos"), EV.limpiar(movida), "moverla o cambiarle el tamaño se guarda en ese plano")
        r = servidor.cambiar_elementos_de_plano(pid, "S002", {"elementos": []})
        guardados = ((ctx.estado.params("callouts") or {}).get("unidades") or {}).get("escena:S002", {})
        ok(r["cambiado"] and guardados == {"elementos": []}, "quitarla guarda la lista vacía")
        igual(sorted(servidor.leer_elementos_de_planos(pid)["planos"]), ["S001"],
              "y quitada se queda quitada: no vuelve a salir")
        r = servidor.cambiar_elementos_de_plano(pid, "S003", {"elementos": []})
        ok(not r["cambiado"] and "escena:S003" not in ((ctx.estado.params("callouts") or {}).get("unidades") or {}),
           "en un plano sin marca, vaciar lo que no hay no escribe nada (como antes)")
        # sumar a lo que se ve: con la marca de la Parrilla y sin guardar nada antes
        pid2 = Proyecto.crear(base, "marca 2").id
        Estado(servidor.contexto(pid2).proyecto)
        ctx2 = servidor.contexto(pid2)
        texto = {"tipo": "texto", "texto": "OJO", "x": 0.5, "y": 0.5}
        servidor.aplicar_elementos(pid2, {"planos": {"S001": [texto]}})
        guardados = ((ctx2.estado.params("callouts") or {}).get("unidades") or {}).get("escena:S001", {})
        igual([e["tipo"] for e in guardados.get("elementos") or []], ["icono", "texto"],
              "aplicar elementos de Claude SUMA a la cruz: no la pierde")
        servidor.aplicar_elementos(pid2, {"planos": {"S002": []}, "reemplazar": True})
        guardados = ((ctx2.estado.params("callouts") or {}).get("unidades") or {}).get("escena:S002", {})
        igual(guardados, {"elementos": []}, "reemplazar por nada quita el check y se queda quitado")
    finally:
        servidor._escenas_del_video, servidor._es_vertical = reales


def main():
    print("PRUEBA DE LA MARCA ✗ / ✓ DE LA PARRILLA")
    prueba_parrilla()
    enc = prueba_encargo()
    prueba_guion_visual(enc)
    prueba_elemento()
    prueba_rutas()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PARRILLA MARCA OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

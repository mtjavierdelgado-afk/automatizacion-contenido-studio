"""
QUE DIBUJAN LAS IMAGENES: LA VOZ O EL GUION (rama guion-visual, 22-10-2026).

Lo que se comprueba, en memoria y sin el CLI ni pagar nada:

  1. EL MODO: «voz» es no tenerlo; el del video manda sobre el del estilo; un
     valor raro no rompe nada.
  2. EL GUION VISUAL se valida y se numera (V001…); sin aprobar no manda.
  3. LA PARRILLA: «Imágenes: guion» y las lineas «Visual:» llegan al Encargo, y
     se casan con los bloques del guion por la voz de cada escena.
  4. EL CORTE: un plano por linea visual, sobre el reloj de la voz; un bloque
     sin lineas sigue viendo la anterior.
  5. EL PROMPT: con linea visual, la frase de la voz NO llega al dibujante, la
     linea va como direccion y la camara como encuadre; sin linea, como siempre.
  6. EL ESTADO del objeto sale de la linea, no del tramo de voz.
  7. EL ESTILO guarda «imagenes» solo si es «guion».

    python pasos/prueba_guion_visual.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import guion_visual as G  # noqa: E402

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


def prueba_modo():
    seccion("1] el modo")
    igual(G.modo_de({}), "voz", "sin nada, la voz (como siempre)")
    igual(G.modo_de({"imagenes": "guion"}), "guion", "el vídeo dice guion")
    igual(G.modo_de({"estilo": {"imagenes": "guion"}}), "guion", "el estilo dice guion")
    igual(G.modo_de({"imagenes": "voz", "estilo": {"imagenes": "guion"}}), "voz",
          "el vídeo dice voz explícitamente: manda sobre el estilo")
    igual(G.modo_de({"imagenes": "telenovela"}), "voz", "un valor raro guardado no rompe: voz")
    igual(G.normalizar_modo("Lo que dice el guion"), "guion", "por el nombre visible")
    igual(G.normalizar_modo("voz"), "", "voz es no tenerlo")
    try:
        G.normalizar_modo("telenovela")
        ok(False, "un modo que no existe tiene que dar ValueError")
    except ValueError:
        ok(True, "un modo que no existe da ValueError")


PLANOS = [{"bloque": "B001", "visual": "wide shot: the hinged door hits the toilet",
           "camara": "wide shot from the doorway", "estado": "abierta"},
          {"bloque": "B001", "visual": "close-up of the hinge"},
          {"bloque": "B002", "visual": "the sliding door, closed", "estado": "corrediza"}]


def prueba_guion_visual():
    seccion("2] el guion visual")
    gv = G.normalizar({"origen": "claude", "planos": PLANOS, "aprobado": True})
    igual([p["id"] for p in gv["planos"]], ["V001", "V002", "V003"], "se numera en orden")
    igual(gv["planos"][0]["estado"], "abierta", "con su estado")
    ok(gv["aprobado"], "aprobado")
    igual(G.activo({"imagenes": "guion", "guion_visual": gv}), gv["planos"], "en modo guion y aprobado, manda")
    ok(G.activo({"guion_visual": gv}) is None, "en modo voz no manda aunque exista")
    ok(G.activo({"imagenes": "guion", "guion_visual": dict(gv, aprobado=False)}) is None,
       "sin aprobar no manda")
    for malo in ({"planos": [{"bloque": "B1"}]}, {"planos": "x"}, {"origen": "x", "planos": []}):
        try:
            G.normalizar(malo)
            ok(False, f"{malo!r} tiene que dar ValueError")
        except ValueError:
            ok(True, f"mal formado da ValueError ({str(malo)[:30]})")
    try:
        G.normalizar({"planos": PLANOS}, {"B001"})
        ok(False, "un bloque que no existe tiene que dar ValueError")
    except ValueError:
        ok(True, "un bloque que no existe da ValueError")
    igual(G.normalizar({"planos": [], "aprobado": True}).get("aprobado"), False,
          "uno vacío no puede estar aprobado")


def prueba_parrilla():
    seccion("3] la Parrilla")
    import parrilla as P                                          # noqa: PLC0415
    guion = ("D01 — Mampara\nUso: exacto\nImágenes: guion\n\nESCENA 1 (0-5 s)\n"
             "Visual: plano general; la batiente choca con el inodoro\n"
             "Voz: «Este error de mampara te deja sin espacio.»\n\n"
             "ESCENA 2 (5-10 s)\nVisual: la corrediza cerrada\nVisual: detalle del riel\n"
             "Voz: «Una corrediza te devuelve el espacio.»\n")
    g = P.leer_guion(guion)
    enc = P.encargo_de(g)
    igual(enc.get("imagenes"), "guion", "«Imágenes: guion» llega al Encargo")
    igual([len(v["visual"]) for v in enc.get("visuales") or []], [1, 2], "y las líneas «Visual:», por escena")
    sin = P.encargo_de(P.leer_guion(guion.replace("Imágenes: guion\n", "")))
    ok("imagenes" not in sin and sin.get("visuales"), "sin la línea, las líneas viajan pero no se elige nada")
    ok(any("Lo que dice el guion" in a for a in sin["avisos"]), "y se avisa de que no se usarán")
    for linea in ("Imágenes: … (opcional: «guion» si cada imagen sigue su línea «Visual:»; si no, quita la línea)",
                  "Imágenes: voz | guion  (opcional)"):
        ok(not P.leer_guion("X — t\n" + linea + "\n").get("imagenes"),
           f"la plantilla sin rellenar no elige nada ({linea[:22]}…)")
    igual(P.leer_guion("X — t\nImágenes: voz\n").get("imagenes"), "voz",
          "«Imágenes: voz» explícito se guarda (manda sobre un estilo que diga guion)")
    bloques = [{"id": "B001", "texto": "Este error de mampara te deja sin espacio."},
               {"id": "B002", "texto": "Una corrediza te devuelve el espacio."}]
    planos, avisos = G.casar(G.normalizar_visuales(enc["visuales"]), bloques)
    igual([(p["bloque"], p["visual"][:10]) for p in planos],
          [("B001", "plano gene"), ("B002", "la corredi"), ("B002", "detalle de")],
          "cada línea va al bloque cuya voz se parece a la de su escena")
    igual(avisos, [], "sin avisos")


def _palabras(n, desde=0.0):
    return [{"w": f"w{i}", "s": desde + i * 0.5, "e": desde + i * 0.5 + 0.4} for i in range(n)]


def prueba_corte():
    seccion("4] el corte: un plano por línea")
    palabras = _palabras(12)
    bloque_de = ["B001"] * 6 + ["B002"] * 4 + ["B003"] * 2
    planos = G.normalizar({"planos": PLANOS, "aprobado": True})["planos"]
    segs, lineas, avisos = G.segmentos(palabras, bloque_de, planos)
    igual([len(s[2]) for s in segs], [3, 3, 6], "B001 se parte en dos líneas; B002+B003 sigue la del B002")
    igual([l["id"] for l in lineas], ["V001", "V002", "V003"], "y cada trozo con su línea")
    igual(segs[0][0], 0.0, "empieza en la primera palabra")
    igual(avisos, [], "sin avisos")
    segs, lineas, avisos = G.segmentos(_palabras(2), ["B001", "B001"],
                                       G.normalizar({"planos": PLANOS[:1] * 3})["planos"])
    igual(len(segs), 2, "más líneas que palabras: se quedan tantas como palabras")
    ok(avisos, "y se avisa")
    # revisión del 22-10: los bordes
    dos = G.normalizar({"planos": [{"bloque": "B002", "visual": "a"},
                                   {"bloque": "B003", "visual": "b"}]})["planos"]
    segs, lineas, _a = G.segmentos(_palabras(9), ["B001"] * 3 + ["B002"] * 3 + ["B003"] * 3, dos)
    igual([l["visual"] for l in lineas], ["a", "b"],
          "un bloque del principio sin líneas va con el primer plano, sin repetirlo")
    igual([len(x[2]) for x in segs], [6, 3], "y le suma sus palabras")
    segs, lineas, _a = G.segmentos(_palabras(7), ["", "B002", "B002", "", "B002", "B003", "B003"], dos)
    igual([l["visual"] for l in lineas], ["a", "b"],
          "una palabra sin bloque (redondeo, hueco) no parte su bloque en dos")
    segs, lineas, avisos = G.segmentos(_palabras(4), ["B009"] * 4, dos)
    ok(not segs and avisos, "ninguna línea casa con la voz: no hay corte y se dice")
    igual(G.fuera_de_la_voz(dos, ["B002"]), ["B003"], "los bloques que ya no están en la voz")


def prueba_prompt_y_estado():
    seccion("5] y 6] el prompt y el estado")
    import p6_assets as P6                                        # noqa: PLC0415
    escena = {"id": "S001", "narracion": "una corrediza te devuelve el espacio",
              "set": "bano", "linea_gv": {"visual": "the hinged door hits the toilet"}}
    igual(P6._con_narracion("BASE.", escena), "BASE.",                       # noqa: SLF001
          "con línea visual, la frase de la voz NO llega al dibujante")
    sin = dict(escena)
    sin.pop("linea_gv")
    ok("corrediza" in P6._con_narracion("BASE.", sin),                       # noqa: SLF001
       "sin línea, la frase entra como siempre")
    escenas = [dict(escena, linea_gv={"visual": "x", "camara": "close-up of the hinge",
                                      "personajes": ["mujer", "fantasma"]}, abstracta=True)]
    P6._aplicar_lineas_gv(escenas, {"reparto": {"mujer": {}}})                 # noqa: SLF001
    igual(escenas[0]["encuadre"], "close-up of the hinge", "la cámara de la línea es el encuadre")
    ok("abstracta" not in escenas[0], "y el plano deja de ser abstracto")
    igual(escenas[0]["personajes"], ["mujer"], "solo los personajes que están en el reparto")
    estados = {"abierta": "the hinged door swung open", "corrediza": "a sliding door"}
    igual(G.estado_de_linea({"estado": "corrediza"}, estados),
          {"cambio": "a sliding door", "estado": "corrediza"}, "el estado sale de la línea")
    igual(G.estado_de_linea({"estado": "volando"}, estados), {"cambio": "", "estado": ""},
          "un estado que no existe: la base")
    igual(G.estado_de_linea({}, estados), {"cambio": "", "estado": ""}, "sin estado: la base")


def prueba_estilo():
    seccion("7] el estilo")
    import presets_canal as PC                                    # noqa: PLC0415
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "imagenes": "Lo que dice el guion"}),  # noqa: SLF001
          {"calidad": "low", "imagenes": "guion"}, "«guion» se guarda normalizado")
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "imagenes": "voz"}),    # noqa: SLF001
          {"calidad": "low"}, "«voz» no se guarda (regla 1)")
    datos = PC.datos_de_params({"assets": {"estilo": {"referencias": [], "imagenes": "guion"}}})
    igual((datos.get("estilo") or {}).get("imagenes"), "guion", "guardar el estilo de un vídeo lo lleva")
    sin = PC.datos_de_params({"assets": {"estilo": {"referencias": []}}})
    ok("imagenes" not in (sin.get("estilo") or {}), "y uno sin él no lo inventa")


def main():
    print("PRUEBA DEL GUION VISUAL")
    prueba_modo()
    prueba_guion_visual()
    prueba_parrilla()
    prueba_corte()
    prueba_prompt_y_estado()
    prueba_estilo()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"GUION VISUAL OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

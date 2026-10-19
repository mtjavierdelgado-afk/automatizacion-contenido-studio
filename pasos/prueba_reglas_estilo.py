"""Prueba de las REGLAS DEL ESTILO (pasos/reglas_estilo.py).

Lo que se comprueba es lo que costaria dinero o se perderia sin avisar:

  - un estilo SIN reglas da el prompt de cada plano byte a byte igual que
    antes (si no, todas las imagenes de todos los videos saldrian obsoletas);
  - con reglas, entran solo en los planos a los que aplican (sus palabras);
  - el preset las valida, las guarda y las lleva al video (y las quita si el
    estilo nuevo no tiene), y congelar desde params no las pierde;
  - el revisor y el corrector las reciben con su gravedad.

    python pasos/prueba_reglas_estilo.py
"""
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(RAIZ))

_TMP = tempfile.mkdtemp(prefix="prueba_reglas_")
os.environ.setdefault("ESTUDIO_PRESETS", os.path.join(_TMP, "presets.json"))
os.environ.setdefault("ESTUDIO_SECRETOS", os.path.join(_TMP, "secretos"))
os.environ.setdefault("ESTUDIO_ESTADISTICAS", os.path.join(_TMP, "estadisticas.json"))

import reglas_estilo as rs                                  # noqa: E402
import presets_canal                                        # noqa: E402
import p6_assets                                            # noqa: E402
import revisor_imagenes                                     # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        return True
    _fallos.append(mensaje)
    print(f"      FALLO: {mensaje}")
    return False


def igual(obtenido, esperado, mensaje):
    return ok(obtenido == esperado,
              f"{mensaje} (esperaba {esperado!r}, llego {obtenido!r})")


def seccion(titulo):
    print(f"\n  {titulo}")


MIRAN = {"nombre": "Los jugadores miran la pantalla",
         "texto": "Quien juega mira siempre la pantalla, nunca a cámara.",
         "palabras": ["jugador", "mandos", "partida"], "gravedad": "alta",
         "en": "Whoever is playing always looks at the screen, never at the camera."}
SIEMPRE = {"nombre": "Luz cálida", "texto": "Luz cálida de noche en todos los planos.",
           "gravedad": "media"}


def prueba_normalizar():
    seccion("validar")
    igual(rs.normalizar(None), [], "sin reglas, lista vacia")
    igual(rs.normalizar([{"texto": "   "}]), [], "una regla sin texto es un borrador y se descarta")
    reglas = rs.normalizar([MIRAN, SIEMPRE])
    igual([r["id"] for r in reglas], ["r1", "r2"], "ids propios")
    igual(reglas[1]["gravedad"], "media", "gravedad")
    ok("palabras" not in reglas[1], "sin palabras no se escribe la clave")
    fmt = rs.normalizar([{"nombre": "{logo}", "texto": "con llaves {0} y }{", "palabras": ["{x}"]}])
    ok(rs.para_revisor(fmt) and rs.para_prompt(fmt, "{x}"), "las llaves en el texto no rompen nada")
    ok(revisor_imagenes.BLOQUE_REGLAS_ESTILO.format(reglas=rs.para_revisor(fmt)), "ni en el revisor")
    ids = [r["id"] for r in rs.normalizar([{"texto": "nueva"}, {"id": "r1", "texto": "vieja"}])]
    ok(ids[1] == "r1" and ids[0] != "r1",
       f"una regla sin id no le quita el suyo a la que ya lo tenia ({ids})")
    igual([r["id"] for r in rs.normalizar([{"id": "nueva17", "texto": "a"}, {"id": "nueva17", "texto": "b"}])],
          ["nueva17", "r2"], "un id repetido se cambia en la segunda")
    igual(rs.normalizar([{"texto": "x", "palabras": "jugador, Jugador ,mandos"}])[0]["palabras"],
          ["jugador", "mandos"], "palabras desde texto con comas, sin repetidas")
    for malo, que in (([{"texto": "x", "gravedad": "enorme"}], "gravedad rara"),
                      ([{"texto": "y" * 900}], "texto largo"),
                      ([{"texto": f"r{i}"} for i in range(rs.MAX_REGLAS + 1)], "demasiadas"),
                      ("no es lista", "no lista")):
        try:
            rs.normalizar(malo)
            ok(False, f"{que} tenia que rechazarse")
        except rs.ReglaInvalida:
            ok(True, "")


def prueba_aplica():
    seccion("cuando aplica")
    regla = rs.normalizar([MIRAN])[0]
    ok(rs.aplica(regla, "Dos JUGADORES con sus mandos"), "por el principio de la palabra, sin mayusculas")
    ok(rs.aplica(regla, "la última partida"), "otra palabra")
    ok(not rs.aplica(regla, "el público aplaude"), "un plano que no habla de eso")
    ok(not rs.aplica(regla, "un conjugador"), "no casa a mitad de palabra")
    ok(rs.aplica(rs.normalizar([SIEMPRE])[0], "lo que sea"), "sin palabras, siempre")


def prueba_prompt():
    seccion("el prompt de un plano")
    escena = {"id": "S001", "prompt": "two players with white controllers on a sofa",
              "narracion": "cada partida dura cinco minutos", "personajes": [], "set": ""}
    publico = {"id": "S002", "prompt": "people clapping", "narracion": "todos aplauden",
               "personajes": [], "set": ""}
    estilo = {"prompt": "", "referencias": [], "modo": "foto",
              "guia": {"guia": "warm documentary photo"}}
    base = p6_assets._prompt_completo(escena, [], estilo)                    # noqa: SLF001
    igual(p6_assets._prompt_completo(escena, [], dict(estilo, reglas=[])), base,  # noqa: SLF001
          "reglas vacias = sin reglas, byte a byte")
    ok("RULES OF THIS STYLE" not in base, "sin reglas no sale el bloque")
    con = dict(estilo, reglas=rs.normalizar([MIRAN, SIEMPRE]))
    texto = p6_assets._prompt_completo(escena, [], con)                      # noqa: SLF001
    ok(MIRAN["en"] in texto and SIEMPRE["texto"] in texto,
       "con reglas: la version afinada si la hay, el texto si no")
    ok(texto.index("RULES OF THIS STYLE") < texto.index("Scene:"),
       "las reglas van delante de la escena")
    otro = p6_assets._prompt_completo(publico, [], con)                      # noqa: SLF001
    ok(MIRAN["en"] not in otro and SIEMPRE["texto"] in otro,
       "un plano del publico solo lleva la que aplica siempre")
    ok(MIRAN["en"] in p6_assets._prompt_completo(                            # noqa: SLF001
        publico, [], con, feedback="que el jugador mire la tele"),
       "la nota tambien cuenta para decidir si aplica")
    corr = rs.para_corrector(rs.de_estilo(con))
    ok("REGLAS DEL ESTILO" in corr and MIRAN["en"] in corr, "el corrector las recibe")


def prueba_preset():
    seccion("el preset y el video")
    limpio = presets_canal._limpiar_datos("estilo", {"guia": {"guia": "x"},  # noqa: SLF001
                                                     "reglas": [MIRAN, {"texto": ""}]})
    igual(len(limpio["reglas"]), 1, "el preset valida y limpia las reglas")
    sin = presets_canal._limpiar_datos("estilo", {"guia": {"guia": "x"}, "reglas": []})  # noqa: SLF001
    ok("reglas" not in sin, "una lista vacia no se guarda")
    try:
        presets_canal._limpiar_datos("estilo", {"reglas": [{"texto": "x", "gravedad": "?"}]})  # noqa: SLF001
        ok(False, "una regla mala no se guarda")
    except presets_canal.ErrorPreset:
        ok(True, "")
    ficha = {"tipo": "estilo", "datos": {"guia": {"guia": "x"}, "reglas": limpio["reglas"]}}
    cambios = presets_canal.cambios_para(ficha, {"assets": {"estilo": {"prompt": ""}}})
    igual(cambios["assets"]["estilo"]["reglas"], limpio["reglas"], "viajan al video")
    sin_reglas = {"tipo": "estilo", "datos": {"guia": {"guia": "x"}}}
    cambios = presets_canal.cambios_para(
        sin_reglas, {"assets": {"estilo": {"prompt": "", "reglas": limpio["reglas"]}}})
    ok("reglas" not in cambios["assets"]["estilo"], "un estilo sin reglas las quita del video")
    cambios = presets_canal.cambios_para(sin_reglas, {"assets": {"estilo": {"prompt": ""}}})
    igual(cambios["assets"]["estilo"], {"prompt": "", "guia": {"guia": "x"}},
          "a un video sin reglas y un estilo sin reglas no se le escribe la clave")
    datos = presets_canal.datos_de_params(
        {"assets": {"estilo": {"guia": {"guia": "x"}, "reglas": limpio["reglas"]}}},
        incluir=("estilo",))
    igual(datos["estilo"]["reglas"], limpio["reglas"], "datos_de_params las conserva")


def prueba_revisor():
    seccion("el revisor")
    texto = rs.para_revisor(rs.normalizar([MIRAN, SIEMPRE]))
    ok("gravedad ALTA" in texto and "jugador, mandos, partida" in texto,
       "con su gravedad y su condicion")
    ok("regla" in revisor_imagenes.TIPOS, "el revisor tiene el tipo «regla»")
    bloque = revisor_imagenes.BLOQUE_REGLAS_ESTILO.format(reglas=texto)
    ok("LAS REGLAS DEL ESTILO" in bloque, "y su hueco en la instruccion")
    igual(rs.para_revisor([]), "", "sin reglas, nada")


def prueba_afinar():
    seccion("afinar con Claude (simulado)")
    original = rs.cli_claude.ejecutar
    pedido = {}

    def doble(instruccion, **kw):
        pedido["i"] = instruccion
        return json.dumps({"nombre": "Miran la pantalla", "en": "Players look at the screen.",
                           "en_es": "Los jugadores miran la pantalla.",
                           "palabras": ["jugadores"], "gravedad": "alta"}), {}
    rs.cli_claude.ejecutar = doble
    try:
        p = rs.afinar("que los jugadores miren la tele")
        igual((p["nombre"], p["en"], p["palabras"], p["gravedad"]),
              ("Miran la pantalla", "Players look at the screen.", ["jugadores"], "alta"),
              "la propuesta, validada")
        ok("que los jugadores miren la tele" in pedido["i"], "con el texto de la persona")
        igual(p.get("en_es"), "Los jugadores miran la pantalla.", "con su traduccion para leerla")
        ok("en_es" not in rs.normalizar([{"texto": "x", "en_es": "y"}])[0],
           "sin version afinada no se guarda traduccion")
        try:
            rs.afinar("  ")
            ok(False, "sin texto no se afina")
        except rs.ReglaInvalida:
            ok(True, "")
    finally:
        rs.cli_claude.ejecutar = original


def main():
    prueba_normalizar()
    prueba_aplica()
    prueba_prompt()
    prueba_preset()
    prueba_revisor()
    prueba_afinar()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"REGLAS DEL ESTILO OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

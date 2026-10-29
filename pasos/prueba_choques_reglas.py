"""Prueba de «¿CHOCAN LAS REGLAS?» (pasos/choques_reglas.py, rama reglas-claras).

Lo que se comprueba:

  - la pista gratis encuentra el caso del dueño (la tele «sobre un mueble» en
    la ficha y «nunca sobre un mueble» en el estilo) y no marca reglas que no
    comparten nada;
  - la respuesta de Claude se limpia: tipos raros, índices que no existen y
    pares repetidos se tiran, y los índices salen desde 0;
  - la pregunta lleva las dos listas, numeradas, con sus «solo si…»;
  - sin reglas en alguna de las dos listas no se llama a Claude;
  - con ESTUDIO_SIMULAR no se llama al CLI.

    python pasos/prueba_choques_reglas.py
"""
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(RAIZ))

_TMP = tempfile.mkdtemp(prefix="prueba_choques_")
os.environ.setdefault("ESTUDIO_SECRETOS", os.path.join(_TMP, "secretos"))
os.environ.setdefault("ESTUDIO_ESTADISTICAS", os.path.join(_TMP, "estadisticas.json"))
os.environ.pop("ESTUDIO_SIMULAR", None)

import choques_reglas as cr                                 # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
    else:
        _fallos.append(mensaje)
        print(f"  FALLA  {mensaje}")


def igual(a, b, mensaje):
    ok(a == b, f"{mensaje}: {a!r} != {b!r}")


def seccion(titulo):
    print(f"\n--- {titulo}")


NEGOCIO = [
    {"texto": "Los mandos se sujetan con las dos manos, del derecho y con los pulgares en los sticks.",
     "palabras": ["mando", "consola"]},
    {"texto": "Cada tele va en su trípode o sobre un mueble, nunca flotando ni en el suelo.",
     "palabras": ["consola"]},
]
ESTILO = [
    {"texto": "La tele va siempre en su trípode negro, nunca sobre un mueble."},
    {"texto": "Luz cálida de salón de fiestas, sin focos de estudio."},
    {"texto": "Los jugadores miran a la pantalla, nunca a cámara."},
    {"texto": "Los mandos se cogen con las dos manos."},
]


def prueba_pista_gratis():
    seccion("la pista gratis: reglas que hablan de lo mismo")
    pares = cr.hablan_de_lo_mismo(NEGOCIO, ESTILO)
    claves = {(p["negocio"], p["estilo"]) for p in pares}
    ok((1, 0) in claves, "la tele del negocio y la del estilo salen juntas")
    ok((0, 3) in claves, "los mandos con las dos manos salen juntos")
    ok((0, 1) not in claves and (1, 1) not in claves, "la luz de salón no sale con nada")
    tele = next(p for p in pares if (p["negocio"], p["estilo"]) == (1, 0))
    ok({"tele", "trípode", "mueble"} <= set(tele["palabras"]),
       f"y se dicen las palabras como se escriben: {tele['palabras']}")
    ok(not cr.hablan_de_lo_mismo([], ESTILO), "sin reglas del negocio, nada")
    ok("nunca" not in cr.raices("nunca siempre cada sobre"), "las palabras vacías no cuentan")
    igual(cr.raices("mandos") & cr.raices("mando"), {"mando"}, "mandos y mando casan")


def prueba_limpiar():
    seccion("la respuesta de Claude, limpia")
    crudo = {"pares": [
        {"tipo": "contradicen", "negocio": 2, "estilo": 1, "por_que": "  una deja  el mueble ",
         "que_cambiar": "quita «o sobre un mueble»"},
        {"tipo": "repiten", "negocio": 1, "estilo": 4},
        {"tipo": "contradicen", "negocio": 2, "estilo": 1},           # repetido
        {"tipo": "raro", "negocio": 1, "estilo": 1},                   # tipo que no existe
        {"tipo": "repiten", "negocio": 9, "estilo": 1},                # índice inventado
        {"tipo": "repiten", "negocio": "x", "estilo": 1},              # no es un número
        "no soy un objeto",
    ]}
    pares = cr.limpiar(crudo, len(NEGOCIO), len(ESTILO))
    igual(len(pares), 2, "quedan los dos pares que valen")
    igual((pares[0]["tipo"], pares[0]["negocio"], pares[0]["estilo"]), ("contradicen", 1, 0),
          "los índices salen desde 0")
    igual(pares[0]["por_que"], "una deja el mueble", "las frases, sin espacios de sobra")
    igual(pares[1]["que_cambiar"], "", "sin frase, vacía (no None)")
    igual(cr.limpiar(None, 2, 2), [], "una respuesta vacía no rompe")
    igual(cr.limpiar({"pares": "x"}, 2, 2), [], "ni una lista que no es lista")


def prueba_revisar():
    seccion("revisar con Claude (doble del CLI)")
    original = cr.cli_claude.ejecutar
    pedido = {}

    def doble(instruccion, **kw):
        pedido["i"] = instruccion
        pedido["kw"] = kw
        return json.dumps({"pares": [{"tipo": "contradicen", "negocio": 2, "estilo": 1,
                                      "por_que": "chocan", "que_cambiar": "cambia una"}]}), {}
    cr.cli_claude.ejecutar = doble
    try:
        r = cr.revisar(NEGOCIO, ESTILO)
        igual([(p["negocio"], p["estilo"]) for p in r["pares"]], [(1, 0)], "el par que dice Claude")
        igual(r["simulado"], False, "no es simulado")
        ok("N2. Cada tele va en su trípode" in pedido["i"], "la pregunta numera las del negocio")
        ok("E1. La tele va siempre" in pedido["i"], "y las del estilo")
        ok("solo si el plano habla de: consola" in pedido["i"], "con sus «solo si…»")
        ok("Write" in (pedido["kw"].get("herramientas_vetadas") or ()), "sin poder escribir nada")
        llamadas = []
        cr.cli_claude.ejecutar = lambda *a, **k: llamadas.append(1) or ("{}", {})
        for negocio, estilo in (([], ESTILO), (NEGOCIO, []), ([{"texto": "  "}], ESTILO)):
            try:
                cr.revisar(negocio, estilo)
                ok(False, "sin reglas en las dos listas no se revisa")
            except ValueError:
                ok(True, "")
        igual(llamadas, [], "y no se llama a Claude")
        os.environ["ESTUDIO_SIMULAR"] = "1"
        try:
            r = cr.revisar(NEGOCIO, ESTILO)
        finally:
            os.environ.pop("ESTUDIO_SIMULAR", None)
        igual(llamadas, [], "simulado, tampoco se llama al CLI")
        ok(r["simulado"] and r["pares"] and r["pares"][0]["tipo"] == "contradicen",
           "y el doble devuelve pares")
    finally:
        cr.cli_claude.ejecutar = original


def main():
    prueba_pista_gratis()
    prueba_limpiar()
    prueba_revisar()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"CHOQUES DE REGLAS OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

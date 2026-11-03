"""
LO QUE SE MANDA A DIBUJAR, EN ESPAÑOL (rama estados-en-espanol, 22-10-2026).

Pedido del dueño: ver y retocar en español los cambios de cada estado del tipo
de relato, que por dentro siguen en inglés. Aquí se prueba `pasos/traducciones.py`:

  1. lo traducido se guarda por la HUELLA del inglés, en un fichero del
     proyecto, y solo casa con ESE texto (si el inglés cambia, vuelve a faltar);
  2. guardar no deja un fichero roto y un fichero roto se lee como vacío;
  3. `al_espanol` y `al_ingles` piden el JSON a Claude, lo leen aunque venga
     envuelto, reintentan una vez si sale roto y no inventan lo que falta.

En memoria, sin el CLI (se dobla `cli_claude.ejecutar`) y sin pagar nada.

    python pasos/prueba_traducciones.py
"""
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

_TEMPORAL = tempfile.mkdtemp(prefix="estudio_traducciones_")
if not os.environ.get("ESTUDIO_ESTADISTICAS"):
    os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(_TEMPORAL, "estadisticas.json")

import cli_claude  # noqa: E402
import traducciones as T  # noqa: E402

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


PUERTA = "the hinged shower door is a sliding door"
SUELO = "floor and all walls in the same large-format ivory porcelain tile"


def prueba_guardar_y_leer():
    seccion("1. SE GUARDA POR LA HUELLA DEL INGLÉS, Y SOLO CASA CON ESE TEXTO")
    raiz = tempfile.mkdtemp(dir=_TEMPORAL)
    igual(T.de(raiz, [PUERTA]), {PUERTA: ""}, "sin fichero, nada traducido")
    igual(T.faltan(raiz, [PUERTA, SUELO, "", None]), [PUERTA, SUELO],
          "faltan los dos (los vacíos no cuentan)")
    igual(T.guardar(raiz, {PUERTA: "la mampara batiente es corrediza", "": "x", SUELO: " "}), 1,
          "se guarda solo lo que tiene los dos lados")
    igual(T.de(raiz, ["  the hinged  shower door is a sliding door "]),
          {PUERTA: "la mampara batiente es corrediza"},
          "los espacios de más no cambian la huella")
    igual(T.faltan(raiz, [PUERTA, SUELO]), [SUELO], "ya solo falta el otro")
    otro = PUERTA + " made of clear glass"
    igual(T.de(raiz, [otro]), {otro: ""},
          "si el inglés cambia, su traducción vieja NO se enseña")
    T.guardar(raiz, {PUERTA: "la mampara es corrediza"})
    igual(T.de(raiz, [PUERTA])[PUERTA], "la mampara es corrediza", "guardar otra vez la pisa")
    with open(T.ruta(raiz), encoding="utf-8") as fh:
        datos = json.load(fh)
    igual(len(datos), 1, "una entrada por texto")
    # una huella que coincide con otro inglés (fichero editado a mano) no casa
    datos[T.huella(SUELO)] = {"en": "something else", "es": "otra cosa"}
    with open(T.ruta(raiz), "w", encoding="utf-8") as fh:
        json.dump(datos, fh)
    igual(T.de(raiz, [SUELO]), {SUELO: ""}, "una huella con OTRO inglés guardado no casa")
    ok(not [n for n in os.listdir(raiz) if n.startswith(".traducciones-")],
       "no quedan temporales")


def prueba_fichero_roto():
    seccion("2. UN FICHERO ROTO SE LEE COMO VACÍO, Y GUARDAR LO ARREGLA")
    raiz = tempfile.mkdtemp(dir=_TEMPORAL)
    with open(T.ruta(raiz), "w", encoding="utf-8") as fh:
        fh.write("{roto")
    igual(T.de(raiz, [PUERTA]), {PUERTA: ""}, "roto: nada traducido, sin lanzar")
    T.guardar(raiz, {PUERTA: "mampara corrediza"})
    igual(T.de(raiz, [PUERTA])[PUERTA], "mampara corrediza", "y guardar lo deja bien")
    with open(T.ruta(raiz), "w", encoding="utf-8") as fh:
        fh.write("[1, 2]")
    igual(T.de(raiz, [PUERTA]), {PUERTA: ""}, "una lista en vez de un objeto, también vacío")


class _Doble:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.vistas = []

    def __call__(self, instruccion, **kwargs):
        self.vistas.append((instruccion, kwargs))
        return self.respuestas.pop(0), {}


def _con_doble(respuestas, funcion):
    real = cli_claude.ejecutar
    doble = _Doble(respuestas)
    cli_claude.ejecutar = doble
    try:
        return funcion(), doble
    except Exception as fallo:                               # noqa: BLE001
        return fallo, doble
    finally:
        cli_claude.ejecutar = real


def prueba_al_espanol():
    seccion("3. AL ESPAÑOL: UNA LLAMADA, EL JSON AUNQUE VENGA ENVUELTO, Y NADA INVENTADO")
    salida, doble = _con_doble(
        ['```json\n{"traducciones": {"0": "la mampara es corrediza", "1": ""}}\n```'],
        lambda: T.al_espanol([PUERTA, SUELO, PUERTA, ""]))
    igual(salida, {PUERTA: "la mampara es corrediza"},
          "vuelve lo traducido; lo que sale vacío se queda fuera")
    igual(len(doble.vistas), 1, "una sola llamada, sin repetir el texto duplicado")
    instruccion, kwargs = doble.vistas[0]
    ok("<traducir_al_espanol>" in instruccion and PUERTA in instruccion
       and instruccion.count(PUERTA) == 1, "la instrucción lleva cada texto una vez")
    igual((kwargs.get("modelo"), kwargs.get("esfuerzo")), (T.MODELO, T.ESFUERZO),
          "con el modelo ligero (sonnet, poco esfuerzo)")
    salida, doble = _con_doble(["no es json", '{"traducciones": {"0": "corrediza"}}'],
                               lambda: T.al_espanol([PUERTA]))
    igual(salida, {PUERTA: "corrediza"}, "un JSON roto se pide otra vez y la segunda vale")
    salida, doble = _con_doble(["roto", "roto otra vez"], lambda: T.al_espanol([PUERTA]))
    ok(isinstance(salida, T.ErrorTraduccion) and len(doble.vistas) == 2,
       "roto dos veces: ErrorTraduccion, sin un tercer intento")
    salida, doble = _con_doble([], lambda: T.al_espanol(["", None]))
    igual((salida, len(doble.vistas)), ({}, 0), "sin textos no se llama a Claude")


def prueba_al_ingles():
    seccion("4. AL INGLÉS: CON LA INSTRUCCIÓN ANTERIOR DELANTE, Y NUNCA VACÍO")
    salida, doble = _con_doble(['{"ingles": "the shower door is a clear sliding door"}'],
                               lambda: T.al_ingles("la mampara es corrediza y transparente",
                                                   anterior=PUERTA))
    igual(salida, "the shower door is a clear sliding door", "devuelve el inglés")
    instruccion = doble.vistas[0][0]
    ok("<pasar_al_ingles>" in instruccion and PUERTA in instruccion
       and "transparente" in instruccion, "lleva el español y la instrucción anterior")
    salida, _d = _con_doble(['{"ingles": ""}'], lambda: T.al_ingles("algo", anterior=PUERTA))
    ok(isinstance(salida, T.ErrorTraduccion), "un inglés vacío lanza ErrorTraduccion")
    salida, doble = _con_doble([], lambda: T.al_ingles("   "))
    ok(isinstance(salida, T.ErrorTraduccion) and not doble.vistas,
       "sin español no se llama a Claude")
    largo = "x" * 900
    salida, _d = _con_doble([json.dumps({"ingles": largo})], lambda: T.al_ingles("algo"))
    ok(isinstance(salida, T.ErrorTraduccion),
       "un inglés más largo que el tope de un cambio (400) se rechaza, no se recorta")


def prueba_describir():
    seccion("5. LO QUE SE PIDIÓ DIBUJAR (rama descripcion-planos): OTRO FICHERO, POR LOTES")
    raiz = tempfile.mkdtemp(dir=_TEMPORAL)
    prompt = ("A small bathroom with grey tiles, wide shot from the doorway. This shot "
              "accompanies the narration line: \"Este baño era el más feo\".")
    T.guardar(raiz, {prompt: "una traducción literal"})
    igual(T.de(raiz, [prompt], T.FICHERO_DESCRIPCIONES), {prompt: ""},
          "las descripciones no leen el fichero de las traducciones")
    igual(T.guardar(raiz, {prompt: "Un baño pequeño de baldosas grises, visto desde la puerta."},
                    T.FICHERO_DESCRIPCIONES), 1, "se guardan en su propio fichero")
    ok(os.path.exists(os.path.join(raiz, "descripciones.json")), "que es descripciones.json")
    igual(T.de(raiz, [prompt])[prompt], "una traducción literal",
          "y la traducción de antes sigue en el suyo, sin pisarse")
    igual(T.faltan(raiz, [prompt, prompt + " Close-up."], T.FICHERO_DESCRIPCIONES),
          [prompt + " Close-up."], "un prompt que cambia vuelve a faltar")
    salida, doble = _con_doble(
        ['{"descripciones": {"0": "Un baño pequeño visto desde la puerta.", "1": ""}}'],
        lambda: T.describir([prompt, "otro prompt", prompt, ""]))
    igual(salida, {prompt: "Un baño pequeño visto desde la puerta."},
          "vuelve lo descrito; lo vacío se queda fuera")
    instruccion, kwargs = doble.vistas[0]
    ok("<describir_en_espanol>" in instruccion and instruccion.count("grey tiles") == 1,
       "una sola llamada con cada prompt una vez")
    igual((kwargs.get("modelo"), kwargs.get("esfuerzo")), (T.MODELO, T.ESFUERZO),
          "con el modelo ligero")
    muchos = [f"prompt numero {i}" for i in range(T.POR_LLAMADA_PLANOS + 5)]
    respuestas = [json.dumps({"descripciones": {str(i): f"d{i}" for i in range(T.POR_LLAMADA_PLANOS)}}),
                  json.dumps({"descripciones": {str(i): f"e{i}" for i in range(5)}})]
    salida, doble = _con_doble(respuestas, lambda: T.describir(muchos))
    igual((len(doble.vistas), len(salida)), (2, T.POR_LLAMADA_PLANOS + 5),
          f"{T.POR_LLAMADA_PLANOS + 5} planos van en dos llamadas y vuelven todos")
    salida, doble = _con_doble(["roto", "roto"], lambda: T.describir([prompt]))
    ok(isinstance(salida, T.ErrorTraduccion), "roto dos veces: ErrorTraduccion")
    largo = "x" * (T.MAX_PROMPT + 500)
    _s, doble = _con_doble(['{"descripciones": {}}'], lambda: T.describir([largo]))
    ok(("x" * T.MAX_PROMPT) in doble.vistas[0][0] and ("x" * (T.MAX_PROMPT + 1)) not in doble.vistas[0][0],
       "un prompt larguísimo se manda recortado")


def main():
    print("PRUEBA DE LAS TRADUCCIONES")
    prueba_guardar_y_leer()
    prueba_fichero_roto()
    prueba_al_espanol()
    prueba_al_ingles()
    prueba_describir()
    shutil.rmtree(_TEMPORAL, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"TRADUCCIONES OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

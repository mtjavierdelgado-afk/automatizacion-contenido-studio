"""
INSERTAR UNA IMAGEN NUEVA DENTRO DE UN PLANO (rama insertar-imagen, 26-10-2026).

Lo que se prueba de `pasos/insertar_planos.py`, en memoria y sin pagar nada:

  1. guardar, leer y deshacer: por el TEXTO del plano, su `n` y la palabra;
  2. partir: el de antes conserva su prompt y su `narracion_imagen`, la nueva
     lleva las palabras de después, sus tiempos, su dirección y su prompt;
  3. dos imágenes en el mismo plano (S004B y S004C);
  4. lo que no se parte: cartelas, continuaciones, una palabra fuera de rango,
     marcas que no cuadran, un plano que ya lleva la voz de un quitado;
  5. una frase repetida: se parte la que se pulsó;
  6. sin fichero, nada cambia.

    python pasos/prueba_insertar_planos.py
"""
import copy
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

_TEMPORAL = tempfile.mkdtemp(prefix="estudio_insertar_planos_")
if not os.environ.get("ESTUDIO_ESTADISTICAS"):
    os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(_TEMPORAL, "estadisticas.json")

import cli_claude  # noqa: E402
import insertar_planos as I  # noqa: E402

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


def clave(e):
    return " ".join(str(e.get("narracion_imagen") or e.get("narracion") or "").lower().split())


def sin_imagen(e):
    return bool(e.get("cartela")) and (e.get("cartela") or {}).get("fondo") != "imagen"


def tipo_de_corte(palabra):
    return "fuerte" if palabra.endswith(".") else "ninguno"


def preparar(nueva, partida):
    nueva["prompt"] = f"prompt nuevo: {nueva['direccion']}"


def plano(sid, texto, t_in, **extra):
    palabras = texto.split()
    marcas = [[round(t_in + i * 0.5, 3), round(t_in + i * 0.5 + 0.4, 3)] for i in range(len(palabras))]
    t_out = round(t_in + len(palabras) * 0.5, 3)
    return dict({"id": sid, "narracion": texto, "marcas": marcas, "t_in": t_in, "t_out": t_out,
                 "duracion": round(t_out - t_in, 3), "corte": "fuerte", "prompt": f"prompt de {sid}",
                 "set": "bano", "personajes": ["ana"], "encuadre": "wide", "camara": {"zoom": 1.1},
                 "capa_vectorial": [{"tipo": "nombre"}]}, **extra)


def video():
    return [plano("S001", "Este baño era el más feo con baldosas grises.", 0.0),
            plano("S002", "Y así quedó.", 4.5),
            plano("S003", "El más bonito de la casa.", 6.5)]


def nueva_raiz():
    return tempfile.mkdtemp(dir=_TEMPORAL)


TEXTO = "este baño era el más feo con baldosas grises."


def prueba_guardar():
    seccion("1. SE GUARDA POR EL TEXTO, SU N Y LA PALABRA")
    raiz = nueva_raiz()
    igual(I.leer(raiz), [], "sin fichero, nada insertado")
    I.insertar(raiz, TEXTO, 0, 6, "S001", que="las baldosas grises de cerca",
               direccion="close-up of the grey tiles")
    igual(I.leer(raiz), [{"texto": TEXTO, "n": 0, "palabra": 6, "id": "S001", "letra": "B",
                          "que": "las baldosas grises de cerca",
                          "direccion": "close-up of the grey tiles"}], "apuntada con todo")
    I.insertar(raiz, TEXTO, 0, 6, "S001", que="otra", direccion="another")
    igual([e["que"] for e in I.leer(raiz)], ["otra"], "otra vez en la misma palabra la pisa")
    for nombre, args in (("sin texto", ("", 0, 3)), ("en la primera palabra", (TEXTO, 0, 0)),
                         ("sin dirección", (TEXTO, 0, 3))):
        try:
            I.insertar(raiz, *args, direccion="" if nombre == "sin dirección" else "x")
            ok(False, f"{nombre}: tenía que fallar")
        except ValueError:
            ok(True, f"{nombre}: se rechaza")
    igual(I.deshacer(raiz, TEXTO, 0, 9), None, "deshacer otra palabra: nada")
    ok(I.deshacer(raiz, TEXTO, 0, 6) is not None and not os.path.exists(I.ruta(raiz)),
       "deshacer la quita y, sin nada, no queda fichero")
    with open(I.ruta(raiz), "w", encoding="utf-8") as fh:
        fh.write("{roto")
    igual(I.leer(raiz), [], "un fichero roto se lee como vacío")


def prueba_partir():
    seccion("2. PARTIR: EL DE ANTES CONSERVA SU DIBUJO, LA NUEVA LLEVA EL RESTO")
    raiz = nueva_raiz()
    I.insertar(raiz, TEXTO, 0, 6, "S001", que="las baldosas de cerca",
               direccion="close-up of the grey tiles")
    escenas = video()
    hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
    igual(hecho["insertados"], ["S001B"], "S001B insertada")
    igual([e["id"] for e in escenas], ["S001", "S001B", "S002", "S003"], "detrás de su plano, sin renumerar")
    s1, s1b = escenas[0], escenas[1]
    igual(s1["narracion"], "Este baño era el más feo", "S001 se queda con las palabras de antes")
    igual(s1["narracion_imagen"], "Este baño era el más feo con baldosas grises.",
          "y se le sigue reconociendo por la frase para la que se dibujó")
    igual((s1["prompt"], s1["encuadre"]), ("prompt de S001", "wide"), "su prompt y su encuadre no cambian")
    igual((s1["t_in"], s1["t_out"], s1["duracion"]), (0.0, 3.0, 3.0), "dura hasta que empieza «con»")
    igual(s1["corte"], "ninguno", "y su corte de salida es el de su última palabra («feo»)")
    igual(s1["partida_en"], ["S001B"], "dice en qué se partió")
    igual(s1b["narracion"], "con baldosas grises.", "S001B dice el resto")
    igual(len(s1b["marcas"]), 3, "con sus tres marcas")
    igual((s1b["t_in"], s1b["t_out"], s1b["corte"]), (3.0, 4.5, "fuerte"),
          "desde «con» hasta el final, con el corte de salida del plano entero")
    igual((s1b["set"], s1b["personajes"], s1b["camara"]), ("bano", ["ana"], {"zoom": 1.1}),
          "mismo sitio, reparto y cámara")
    ok("narracion_imagen" not in s1b and s1b["capa_vectorial"] == [],
       "sin narracion_imagen (es suya) y sin rótulos")
    igual((s1b["direccion"], s1b["prompt"]), ("close-up of the grey tiles", "prompt nuevo: close-up of the grey tiles"),
          "con su dirección y su prompt nuevo")
    igual(s1b["insertada"], {"en": "S001", "texto": TEXTO, "n": 0, "palabra": 6, "que": "las baldosas de cerca"},
          "y dice de dónde sale, para deshacerla")


def prueba_dos():
    seccion("3. DOS IMÁGENES EN EL MISMO PLANO")
    raiz = nueva_raiz()
    I.insertar(raiz, TEXTO, 0, 7, "S001", direccion="the tiles")
    I.insertar(raiz, TEXTO, 0, 3, "S001", direccion="the ugly bathroom")
    escenas = video()
    hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
    igual([e["id"] for e in escenas[:3]], ["S001", "S001C", "S001B"],
          "la letra es la de cuando se pidió (S001B fue antes): insertar otra no le cambia el nombre")
    igual([e["narracion"] for e in escenas[:3]],
          ["Este baño era", "el más feo con", "baldosas grises."], "cada una con su trozo, en orden")
    igual([e["direccion"] for e in escenas[1:3]], ["the ugly bathroom", "the tiles"],
          "y van en el orden de la frase")
    igual(escenas[1]["t_out"], escenas[2]["t_in"], "una empieza donde acaba la otra")
    igual(hecho["insertados"], ["S001C", "S001B"], "y se dicen las dos")
    try:
        for palabra in range(1, 12):
            I.insertar(raiz, TEXTO, 0, palabra, "S001", direccion="x")
        ok(False, "más imágenes que letras tenía que fallar")
    except ValueError:
        ok(True, "más imágenes que letras en un plano: se rechaza")


def prueba_lo_que_no():
    seccion("4. LO QUE NO SE PARTE")
    casos = [("una cartela", {"cartela": {"fondo": "negro"}}),
             ("una continuación", {"sigue_a": "S000"}),
             ("un plano con la voz de un quitado", {"absorbe": [{"id": "S000"}]}),
             ("marcas que no cuadran", {"marcas": [[0, 1]]})]
    for nombre, extra in casos:
        raiz = nueva_raiz()
        I.insertar(raiz, TEXTO, 0, 3, "S001", direccion="x")
        escenas = video()
        escenas[0].update(extra)
        hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
        ok(not hecho["insertados"] and len(escenas) == 3 and hecho["sin_casar"], f"{nombre}: no se parte")
    raiz = nueva_raiz()
    I.insertar(raiz, TEXTO, 0, 9, "S001", direccion="x")
    escenas = video()
    hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
    ok(not hecho["insertados"], "una palabra más allá del final: nada")
    raiz = nueva_raiz()
    I.insertar(raiz, TEXTO, 0, 3, "S001", direccion="x")
    escenas = video()
    escenas.insert(1, dict(plano("S002", "segunda mitad", 4.0), sigue_a="S001"))
    hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
    ok(not hecho["insertados"], "un plano con su continuación detrás: no (su imagen sigue en la otra)")
    raiz = nueva_raiz()
    I.insertar(raiz, "una frase que se reescribió", 0, 1, "S009", direccion="x")
    escenas = video()
    hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
    ok(not hecho["insertados"] and len(hecho["sin_casar"]) == 1, "un texto que ya no está: no casa, y se dice")


def prueba_repetida():
    seccion("5. UNA FRASE REPETIDA")
    raiz = nueva_raiz()
    escenas = video()
    escenas[2] = plano("S003", "Este baño era el más feo con baldosas grises.", 6.5)
    I.insertar(raiz, TEXTO, 1, 6, "S003", direccion="x")
    hecho = I.aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)
    igual(hecho["insertados"], ["S003B"], "se parte la segunda vez que se dice, no la primera")


def prueba_sin_fichero():
    seccion("6. SIN FICHERO, NADA CAMBIA")
    escenas = video()
    antes = copy.deepcopy(escenas)
    hecho = I.aplicar(escenas, nueva_raiz(), clave, sin_imagen, preparar, tipo_de_corte)
    igual((escenas, hecho), (antes, {"insertados": [], "sin_casar": []}), "ni una clave cambia")
    I.aplicar(escenas, None, clave, sin_imagen, preparar, tipo_de_corte)
    igual(escenas, antes, "sin carpeta de proyecto, tampoco")


def _con_doble(respuestas, funcion):
    vistas = []

    def doble(instruccion, **kwargs):
        vistas.append((instruccion, kwargs))
        return respuestas.pop(0), {}
    real = cli_claude.ejecutar
    cli_claude.ejecutar = doble
    try:
        return funcion(), vistas
    except Exception as fallo:                               # noqa: BLE001
        return fallo, vistas
    finally:
        cli_claude.ejecutar = real


def prueba_al_ingles():
    seccion("7. LO QUE SE VE, DEL ESPAÑOL AL INGLÉS (con Claude doblado)")
    salida, vistas = _con_doble(['```json\n{"direccion": "Close-up of the grey tiles."}\n```'],
                                lambda: I.al_ingles("las baldosas grises de cerca",
                                                    prompt="A small bathroom", narracion="con baldosas"))
    igual(salida, "Close-up of the grey tiles.", "devuelve la dirección, aunque venga envuelta")
    instruccion, kwargs = vistas[0]
    ok("<imagen_nueva>" in instruccion and "las baldosas grises de cerca" in instruccion
       and "A small bathroom" in instruccion and "con baldosas" in instruccion,
       "la instrucción lleva el español, el prompt de la imagen de origen y la frase")
    igual((kwargs.get("modelo"), kwargs.get("esfuerzo")), (I.MODELO, I.ESFUERZO), "con el modelo ligero")
    salida, vistas = _con_doble([], lambda: I.al_ingles("   "))
    ok(isinstance(salida, I.ErrorDireccion) and not vistas, "sin español no se llama a Claude")
    salida, _v = _con_doble(['{"direccion": ""}'], lambda: I.al_ingles("algo"))
    ok(isinstance(salida, I.ErrorDireccion), "una dirección vacía lanza ErrorDireccion")
    salida, vistas = _con_doble(["roto", "roto"], lambda: I.al_ingles("algo"))
    ok(isinstance(salida, I.ErrorDireccion) and len(vistas) == 2, "roto dos veces: error, sin tercer intento")
    salida, _v = _con_doble(['{"direccion": "%s"}' % ("x" * 500)], lambda: I.al_ingles("algo"))
    ok(isinstance(salida, I.ErrorDireccion), "demasiado larga: se rechaza, no se recorta")


def main():
    print("PRUEBA DE INSERTAR IMÁGENES")
    prueba_guardar()
    prueba_partir()
    prueba_dos()
    prueba_lo_que_no()
    prueba_repetida()
    prueba_sin_fichero()
    prueba_al_ingles()
    shutil.rmtree(_TEMPORAL, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"INSERTAR IMÁGENES OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

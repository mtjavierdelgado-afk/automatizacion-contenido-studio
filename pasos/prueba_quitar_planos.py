"""
QUITAR UNA IMAGEN Y PASAR SU VOZ AL VECINO (rama unir-planos, 25-10-2026).

Lo que se prueba de `pasos/quitar_planos.py`, en memoria y sin pagar nada:

  1. guardar, leer y devolver: por el TEXTO del plano, no por su número;
  2. juntar hacia el anterior y hacia el siguiente: la voz, las marcas, los
     tiempos y el corte de salida del que se queda;
  3. el que se queda conserva la frase para la que se dibujó
     (`narracion_imagen`), que es con la que se le sigue reconociendo;
  4. lo que no se puede: cartelas, continuaciones, capítulos, sin vecino;
  5. cadenas (S001 -> S002 -> S003) y entradas que ya no casan;
  6. sin fichero, nada cambia (el corte es el de siempre).

    python pasos/prueba_quitar_planos.py
"""
import copy
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import quitar_planos as Q  # noqa: E402

_ok = 0
_fallos = []
_TEMPORAL = tempfile.mkdtemp(prefix="estudio_quitar_planos_")


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


def plano(sid, texto, t_in, t_out, **extra):
    marcas = [[t_in + i * 0.1, t_in + i * 0.1 + 0.05] for i in range(len(texto.split()))]
    return dict({"id": sid, "narracion": texto, "marcas": marcas, "t_in": t_in, "t_out": t_out,
                 "duracion": round(t_out - t_in, 3), "corte": f"corte-{sid}",
                 "prompt": f"prompt de {sid}"}, **extra)


def video():
    return [plano("S001", "Este baño era el más feo", 0.0, 2.0),
            plano("S002", "con baldosas grises", 2.0, 4.0),
            plano("S003", "Y así quedó", 4.0, 6.0),
            plano("S004", "el más bonito de la casa", 6.0, 8.0)]


def nueva_raiz():
    return tempfile.mkdtemp(dir=_TEMPORAL)


def prueba_guardar():
    seccion("1. SE GUARDA POR EL TEXTO, Y SE DEVUELVE")
    raiz = nueva_raiz()
    igual(Q.leer(raiz), [], "sin fichero, nada quitado")
    Q.quitar(raiz, "este baño era el más feo", "siguiente", "S001")
    igual(Q.leer(raiz), [{"texto": "este baño era el más feo", "hacia": "siguiente", "id": "S001"}],
          "apuntado con su texto, su lado y el número que tenía")
    Q.quitar(raiz, "este baño era el más feo", "anterior", "S001")
    igual(len(Q.leer(raiz)), 1, "volver a quitarlo cambia el lado, no duplica")
    for malo in (("x", "arriba"), ("", "siguiente")):
        try:
            Q.quitar(raiz, malo[0], malo[1])
            ok(False, f"{malo} tenía que fallar")
        except ValueError:
            ok(True, f"{malo} se rechaza")
    ok(Q.devolver(raiz, "este baño era el más feo"), "deshacer lo devuelve")
    ok(not os.path.exists(Q.ruta(raiz)), "sin nada quitado no queda fichero")
    ok(not Q.devolver(raiz, "otra cosa"), "deshacer algo que no estaba: False")
    with open(Q.ruta(raiz), "w", encoding="utf-8") as fh:
        fh.write("{roto")
    igual(Q.leer(raiz), [], "un fichero roto se lee como vacío")


def prueba_juntar():
    seccion("2-3. JUNTAR: LA VOZ PASA, EL DIBUJO SE QUEDA")
    raiz = nueva_raiz()
    Q.quitar(raiz, "este baño era el más feo", "siguiente", "S001")
    escenas = video()
    hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
    igual(hecho["absorbidos"], ["S001"], "S001 quitado")
    igual([e["id"] for e in escenas], ["S002", "S003", "S004"], "sin renumerar")
    s2 = escenas[0]
    igual(s2["narracion"], "Este baño era el más feo con baldosas grises",
          "S002 dice lo de los dos, en orden")
    igual((s2["t_in"], s2["t_out"], s2["duracion"]), (0.0, 4.0, 4.0), "y dura los dos")
    igual(len(s2["marcas"]), 9, "con las marcas de las nueve palabras")
    ok(s2["marcas"][0][0] == 0.0, "la primera marca es la de S001")
    igual(s2["narracion_imagen"], "con baldosas grises", "se le reconoce por lo que se dibujó")
    igual(s2["prompt"], "prompt de S002", "su dibujo (prompt) no cambia")
    igual(s2["corte"], "corte-S002", "su corte de salida sigue siendo el suyo")
    igual(s2["absorbe"], [{"id": "S001", "lado": "antes", "narracion": "Este baño era el más feo"}],
          "y dice de quién lleva la voz")

    raiz = nueva_raiz()
    Q.quitar(raiz, "y así quedó", "anterior", "S003")
    escenas = video()
    Q.aplicar(escenas, raiz, clave, sin_imagen)
    s2 = next(e for e in escenas if e["id"] == "S002")
    igual((s2["narracion"], s2["t_out"], s2["corte"]),
          ("con baldosas grises Y así quedó", 6.0, "corte-S003"),
          "hacia el anterior: se alarga por detrás y sale con el corte del quitado")


def prueba_lo_que_no():
    seccion("4. LO QUE NO SE QUITA")
    casos = [
        ("una cartela", {"cartela": {"fondo": "negro"}}),
        ("una continuación de un plano largo", {"sigue_a": "S001"}),
        ("un plano que abre capítulo", {"capa_vectorial": [{"tipo": "capitulo"}]}),
    ]
    for nombre, extra in casos:
        raiz = nueva_raiz()
        Q.quitar(raiz, "con baldosas grises", "siguiente", "S002")
        escenas = video()
        escenas[1].update(extra)
        hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
        ok(not hecho["absorbidos"] and len(escenas) == 4, f"{nombre}: se queda")
    raiz = nueva_raiz()
    Q.quitar(raiz, "este baño era el más feo", "anterior", "S001")
    escenas = video()
    hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
    ok(not hecho["absorbidos"] and hecho["sin_casar"], "el primero hacia el anterior: no hay vecino")
    raiz = nueva_raiz()
    Q.quitar(raiz, "este baño era el más feo", "siguiente", "S001")
    escenas = video()
    escenas[1]["cartela"] = {"fondo": "negro"}
    hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
    ok(not hecho["absorbidos"], "hacia una cartela de fondo negro: no (no tiene imagen)")
    raiz = nueva_raiz()
    Q.quitar(raiz, "este baño era el más feo", "siguiente", "S001")
    escenas = video()
    escenas[1]["cartela"] = {"fondo": "imagen"}
    hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
    ok(not hecho["absorbidos"], "hacia una cartela sobre imagen: tampoco (su texto va a su ritmo)")


def prueba_cadenas():
    seccion("5. CADENAS Y LO QUE YA NO CASA")
    raiz = nueva_raiz()
    Q.quitar(raiz, "este baño era el más feo", "siguiente", "S001")
    Q.quitar(raiz, "con baldosas grises", "siguiente", "S002")
    escenas = video()
    hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
    igual(hecho["absorbidos"], ["S001", "S002"], "S001 va a S002 y S002 a S003")
    s3 = escenas[0]
    igual((s3["id"], s3["narracion"], s3["t_in"]),
          ("S003", "Este baño era el más feo con baldosas grises Y así quedó", 0.0),
          "S003 lleva las tres frases desde el principio")
    igual([a["id"] for a in s3["absorbe"]], ["S001", "S002"], "y dice de quién")
    raiz = nueva_raiz()
    Q.quitar(raiz, "una frase que se reescribió", "siguiente", "S009")
    escenas = video()
    hecho = Q.aplicar(escenas, raiz, clave, sin_imagen)
    ok(not hecho["absorbidos"] and len(hecho["sin_casar"]) == 1,
       "una entrada cuyo texto ya no está no quita nada (y se dice)")


def prueba_sin_fichero():
    seccion("6. SIN FICHERO, EL CORTE ES EL DE SIEMPRE")
    escenas = video()
    antes = copy.deepcopy(escenas)
    hecho = Q.aplicar(escenas, nueva_raiz(), clave, sin_imagen)
    igual(escenas, antes, "ni una clave cambia")
    igual(hecho, {"absorbidos": [], "sin_casar": []}, "y no informa de nada")
    escenas = video()
    Q.aplicar(escenas, None, clave, sin_imagen)
    igual(escenas, antes, "sin carpeta de proyecto, tampoco")


def main():
    print("PRUEBA DE QUITAR IMÁGENES")
    prueba_guardar()
    prueba_juntar()
    prueba_lo_que_no()
    prueba_cadenas()
    prueba_sin_fichero()
    shutil.rmtree(_TEMPORAL, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"QUITAR IMÁGENES OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

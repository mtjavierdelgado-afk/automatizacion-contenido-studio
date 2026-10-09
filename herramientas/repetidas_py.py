"""Funciones y constantes definidas DOS VECES en el mismo modulo de Python.

    python herramientas/repetidas_py.py

La segunda definicion pisa a la primera sin un solo error, y todo lo que
llamaba a la primera pasa a llamar a la segunda. Es el gemelo de
`sin_llamar_js.repetidas()` para el JavaScript.

Paso de verdad al anadir las notas de mejoras: `_ruta_notas()` ya existia en
app.py (las notas del repaso, con un argumento) y la nueva, sin argumentos, la
piso. Guardar la nota de un video terminado empezo a dar un 500.
"""
import ast
import collections
import glob
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ficheros():
    for patron in ("app.py", "generar_api.py", "pasos/*.py", "nucleo/*.py",
                   "motores/**/*.py", "herramientas/*.py"):
        yield from sorted(glob.glob(os.path.join(RAIZ, patron), recursive=True))


def repetidas(ruta):
    with open(ruta, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read(), ruta)
    lineas = collections.defaultdict(list)
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            lineas[nodo.name].append(nodo.lineno)
        elif isinstance(nodo, ast.Assign):
            for destino in nodo.targets:
                # solo las CONSTANTES (en mayusculas): una variable de modulo
                # que se reasigna a proposito es otra cosa
                if isinstance(destino, ast.Name) and destino.id.isupper():
                    lineas[destino.id].append(nodo.lineno)
    return {nombre: n for nombre, n in lineas.items() if len(n) > 1}


def main():
    total = 0
    cuantos = 0
    for ruta in ficheros():
        cuantos += 1
        for nombre, n in repetidas(ruta).items():
            total += 1
            print(f"  {os.path.relpath(ruta, RAIZ)}  {nombre}: lineas "
                  f"{', '.join(map(str, n))}")
    if total:
        print(f"NO: {total} nombre(s) definidos dos veces en el mismo modulo")
        return 1
    print(f"OK: {cuantos} ficheros, ningun nombre definido dos veces")
    return 0


if __name__ == "__main__":
    sys.exit(main())

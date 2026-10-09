"""
Huecos de plantilla que nadie rellena.

    python herramientas/plantillas_py.py

Busca las llamadas `PLANTILLA.format(clave=..., ...)` donde PLANTILLA es una
cadena de modulo, y comprueba que cada hueco `{nombre}` de la plantilla recibe
su valor. Uno que falte es un KeyError, pero solo cuando se ejecuta esa linea,
y ninguna prueba lo ve si nadie pasa por ahi.

Paso de verdad: al retirar los personajes fijos del canal se quito el codigo
que rellenaba `{fijos}` y el hueco se quedo en la instruccion del catalogo
visual (`pasos/catalogo_visual.py`). «Generar imagenes» moria al instante con
«KeyError: 'fijos'» en todos los proyectos.

Se saltan las llamadas con argumentos posicionales o con `**datos`: ahi no se
puede saber desde el codigo que claves llegan.
"""
import ast
import glob
import os
import string
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ficheros():
    for patron in ("app.py", "pasos/*.py", "nucleo/*.py", "motores/**/*.py"):
        for ruta in sorted(glob.glob(os.path.join(RAIZ, patron), recursive=True)):
            if not os.path.basename(ruta).startswith("prueba"):
                yield ruta


def huecos(plantilla):
    campos = set()
    for _, campo, _, _ in string.Formatter().parse(plantilla):
        if campo:
            campos.add(campo.split(".")[0].split("[")[0])
    return campos


def revisar(ruta):
    with open(ruta, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read(), ruta)
    plantillas = {}
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and isinstance(nodo.value, ast.Constant) \
                and isinstance(nodo.value.value, str):
            for destino in nodo.targets:
                if isinstance(destino, ast.Name):
                    plantillas[destino.id] = nodo.value.value
    fallos = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "format"
                and isinstance(nodo.func.value, ast.Name)
                and nodo.func.value.id in plantillas):
            continue
        if nodo.args or any(k.arg is None for k in nodo.keywords):
            continue
        nombre = nodo.func.value.id
        try:
            faltan = huecos(plantillas[nombre]) - {k.arg for k in nodo.keywords}
        except ValueError as fallo:
            fallos.append(f"{nombre}: la plantilla no se puede leer ({fallo})")
            continue
        if faltan:
            fallos.append(f"linea {nodo.lineno}: {nombre}.format() no rellena "
                          f"{', '.join('{' + c + '}' for c in sorted(faltan))}")
    return fallos


def main():
    total, cuantos = 0, 0
    for ruta in ficheros():
        cuantos += 1
        for fallo in revisar(ruta):
            total += 1
            print(f"  {os.path.relpath(ruta, RAIZ)}  {fallo}")
    if total:
        print(f"NO: {total} hueco(s) de plantilla sin rellenar")
        return 1
    print(f"OK: {cuantos} ficheros, ningun hueco de plantilla sin rellenar")
    return 0


if __name__ == "__main__":
    sys.exit(main())

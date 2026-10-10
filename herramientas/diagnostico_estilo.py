"""Que videos apuntan a imagenes de estilo que ya no estan, y a cual repuntarlas.

SOLO LEE. No escribe nada en ningun proyecto ni en el banco.

Para que
--------
Hasta el 09-10-2026, volver a guardar un preset de estilo anteponia otro «00_»
a los nombres de sus imagenes (`presets_canal.nombre_numerado` lo arregla) y
borraba la carpeta vieja. Los videos creados con ese estilo guardan la ruta
ABSOLUTA de cada imagen en `params.assets.estilo.referencias`, asi que se
quedaban apuntando a un nombre que ya no existe:

    ninguna de las imagenes de estilo existe en el disco del servidor:
    .../banco/presets/pr1a12036e22d/00_00_00_00_00_00_cara.png

Esto recorre los proyectos, busca en sus params rutas del banco de presets que
no existen, y para cada una propone la imagen de la MISMA carpeta con el mismo
nombre sin prefijos (y el mismo numero de orden si hay varias). Al final imprime
la orden de `mudar_proyecto.py` que haria el cambio -- en SIMULACRO: es esa
herramienta la que muda las rutas y re-sella SOLO lo que la mudanza movio (ver
«Copiar un proyecto...» en CLAUDE.md). Nada de esto regenera ni cobra nada.

Uso (en el servidor, como el usuario del servicio y con su entorno):

    python herramientas/diagnostico_estilo.py [carpeta_de_un_proyecto ...]

Sin argumentos mira todos los de ESTUDIO_PROYECTOS.
"""
from __future__ import annotations

import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

_PREFIJO = re.compile(r"^((\d{2})_)+")


def _base(nombre):
    return _PREFIJO.sub("", nombre)


def _orden(nombre):
    encaje = re.match(r"^(\d{2})_", nombre)
    return encaje.group(1) if encaje else None


def _cadenas(dato, camino=""):
    """(camino, cadena) de todas las cadenas de una estructura."""
    if isinstance(dato, dict):
        for k, v in dato.items():
            yield from _cadenas(v, f"{camino}.{k}" if camino else str(k))
    elif isinstance(dato, list):
        for i, v in enumerate(dato):
            yield from _cadenas(v, f"{camino}[{i}]")
    elif isinstance(dato, str):
        yield camino, dato


def candidata(ruta):
    """La imagen que existe en la misma carpeta y es «la misma». -> ruta o None"""
    carpeta, nombre = os.path.split(ruta)
    if not os.path.isdir(carpeta):
        return None
    base, orden = _base(nombre), _orden(nombre)
    iguales = sorted(f for f in os.listdir(carpeta) if _base(f) == base)
    if len(iguales) == 1:
        return os.path.join(carpeta, iguales[0])
    mismo_orden = [f for f in iguales if _orden(f) == orden]
    if len(mismo_orden) == 1:
        return os.path.join(carpeta, mismo_orden[0])
    return None


def revisar(carpeta):
    """-> [(paso, camino, ruta_rota, candidata o None)]"""
    ruta_estado = os.path.join(carpeta, "estado.json")
    if not os.path.isfile(ruta_estado):
        return []
    with open(ruta_estado, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    rotas = []
    for paso, datos in (doc.get("pasos") or {}).items():
        for camino, cadena in _cadenas((datos or {}).get("params") or {}):
            if f"{os.sep}presets{os.sep}" not in cadena.replace("/", os.sep):
                continue
            if not re.search(r"\.(png|jpe?g|webp)$", cadena, re.I):
                continue
            if os.path.exists(cadena):
                continue
            rotas.append((paso, camino, cadena, candidata(cadena)))
    return rotas


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        carpetas = [os.path.abspath(a) for a in argv]
    else:
        raiz = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")
        carpetas = sorted(os.path.join(raiz, n) for n in os.listdir(raiz)
                          if os.path.isdir(os.path.join(raiz, n)))
    total = 0
    for carpeta in carpetas:
        rotas = revisar(carpeta)
        if not rotas:
            continue
        total += len(rotas)
        print(f"\n== {os.path.basename(carpeta)}: {len(rotas)} rutas de estilo que no existen")
        reglas = []
        for paso, camino, rota, nueva in rotas:
            print(f"  {paso}.{camino}")
            print(f"     guarda:   {rota}")
            print(f"     en disco: {nueva or 'NINGUNA que encaje (hay que mirarla a mano)'}")
            if nueva:
                reglas.append((rota, nueva))
        carpeta_preset = os.path.dirname(rotas[0][2])
        if os.path.isdir(carpeta_preset):
            print(f"  ficheros en {carpeta_preset}:")
            for f in sorted(os.listdir(carpeta_preset)):
                print(f"     {f}")
        if reglas and len(reglas) == len(rotas):
            print("  PROPUESTA (simulacro; con los servicios parados y añadiendo "
                  "--aplicar solo cuando el simulacro cuadre):")
            print(f"    python herramientas/mudar_proyecto.py {carpeta} \\")
            for i, (rota, nueva) in enumerate(reglas):
                cola = " \\" if i < len(reglas) - 1 else ""
                print(f'      --regla "{rota}={nueva}"{cola}')
    print(f"\n{total} rutas rotas en {len(carpetas)} proyectos mirados. No se ha escrito nada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pasa las novedades de cada rama (docs/novedades/) a docs/NOVEDADES.md.

    python herramientas/plegar_novedades.py            # pliega y dice cuáles
    python herramientas/plegar_novedades.py --ver      # solo dice cuáles hay

Lo que se ve en Configuración -> Novedades es EXACTAMENTE lo mismo antes y
después: esto solo ordena los ficheros. Se corre en `main` después de unir,
nunca en una rama (escribir arriba de NOVEDADES.md en una rama es justo lo que
hacía chocar). Ver pasos/novedades.py.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import novedades  # noqa: E402


def main(argv):
    trozos = novedades.fragmentos(RAIZ)
    if not trozos:
        print("No hay novedades sueltas en docs/novedades/: nada que plegar.")
        return 0
    if "--ver" in argv:
        print("Novedades sueltas, de la más nueva a la más antigua:")
        for nombre, _t in trozos:
            print(f"  {nombre}")
        return 0
    antes = novedades.texto(RAIZ)
    plegadas = novedades.plegar(RAIZ)
    despues = novedades.texto(RAIZ)
    if antes != despues:
        print("OJO: el texto ha cambiado al plegar; revisa docs/NOVEDADES.md con git diff.")
        return 1
    print(f"Plegadas {len(plegadas)} en docs/NOVEDADES.md (lo que se ve no cambia):")
    for nombre in plegadas:
        print(f"  {nombre}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

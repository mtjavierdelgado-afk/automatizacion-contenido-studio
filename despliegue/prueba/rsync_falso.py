#!/usr/bin/env python3
"""Un rsync minimo para la prueba de `asvs actualizar` (-a, --delete, --exclude).

Solo lo que usa `asvs`: copia local de carpeta a carpeta. Un excluido ni se
copia ni se borra en el destino, como en rsync.
"""
import fnmatch
import os
import shutil
import sys


def excluido(rel, es_dir, patrones):
    base = rel.rsplit("/", 1)[-1]
    for crudo in patrones:
        solo_dir = crudo.endswith("/")
        patron = crudo.rstrip("/")
        if solo_dir and not es_dir:
            continue
        if "/" in patron:
            if fnmatch.fnmatch(rel, patron) or fnmatch.fnmatch(rel, "*/" + patron):
                return True
        elif fnmatch.fnmatch(base, patron):
            return True
    return False


def main(argv):
    borrar, patrones, rutas = False, [], []
    for arg in argv:
        if arg == "--delete":
            borrar = True
        elif arg.startswith("--exclude="):
            patrones.append(arg.split("=", 1)[1].strip("'"))
        elif arg.startswith("-"):
            continue
        else:
            rutas.append(arg)
    origen, destino = rutas
    origen, destino = origen.rstrip("/"), destino.rstrip("/")
    os.makedirs(destino, exist_ok=True)
    vistos = set()
    for raiz, carpetas, ficheros in os.walk(origen):
        rel_raiz = os.path.relpath(raiz, origen)
        rel_raiz = "" if rel_raiz == "." else rel_raiz.replace(os.sep, "/")
        for c in list(carpetas):
            rel = f"{rel_raiz}/{c}".lstrip("/")
            if excluido(rel, True, patrones):
                carpetas.remove(c)
                continue
            vistos.add(rel)
            os.makedirs(os.path.join(destino, rel), exist_ok=True)
        for f in ficheros:
            rel = f"{rel_raiz}/{f}".lstrip("/")
            if excluido(rel, False, patrones):
                continue
            vistos.add(rel)
            shutil.copy2(os.path.join(raiz, f), os.path.join(destino, rel))
    if borrar:
        for raiz, carpetas, ficheros in os.walk(destino, topdown=True):
            rel_raiz = os.path.relpath(raiz, destino)
            rel_raiz = "" if rel_raiz == "." else rel_raiz.replace(os.sep, "/")
            for c in list(carpetas):
                rel = f"{rel_raiz}/{c}".lstrip("/")
                if excluido(rel, True, patrones):
                    carpetas.remove(c)
                elif rel not in vistos:
                    shutil.rmtree(os.path.join(raiz, c))
                    carpetas.remove(c)
            for f in ficheros:
                rel = f"{rel_raiz}/{f}".lstrip("/")
                if not excluido(rel, False, patrones) and rel not in vistos:
                    os.remove(os.path.join(raiz, f))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

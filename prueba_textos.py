#!/usr/bin/env python3
"""LOS TEXTOS QUE SE LEEN, CON SUS TILDES.

La pantalla (`web/app.js`) y los mensajes de error que manda el servidor
(`app.py`, los de `ErrorApi`) se escribieron durante meses sin tildes, como los
comentarios del código, y la persona los leía así: «Calidad de las imagenes»,
«no hay nada asi en la papelera». Se corrigieron el 11-10-2026 (107 textos) y
esto vigila que no vuelvan: busca, SOLO en las cadenas que se enseñan, las
palabras que casi siempre llevan tilde.

No es un corrector: una lista corta de palabras que en castellano NO existen
sin tilde (o casi nunca se escriben así en una frase para leer). Lo que no
encaje aquí lo revisa una persona (o el corrector de `pasos/ortografia.py`).

    python prueba_textos.py
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))

#: Palabras que en una frase para leer van con tilde. Sin «esta»/«este»
#: (demostrativos), «solo» y «guion» (correctos sin tilde) ni «video» suelto
#: (es también el nombre de una vista y de un paso en el código).
SIN_TILDE = r"""imagenes|musica|subtitulos?|tambien|despues|segun|codigo|numero|pagina|
titulo|ultim[oa]s?|rapid[oa]s?|camara|guias?|accion|version|estan|todavia|razon|tamanos?|
aqui|ademas|ningun|algun|catalogo|almacen|pestanas?|configuracion|implementacion|
descripcion|ejecucion|generacion|conservacion|valoracion|sesion|contrasena|maquina|
facil|util|dificil|automatica|automaticamente|imagenes|laminas?|grafico|diseno|
volveria|saldria|montaria|daria|habra|mas barat[oa]|esta al dia|esta puesta|
no esta|ya esta|asi que|asi en|videos nuevos|los videos|del video|el video|un video|
este video|tu video""".replace("\n", "")
PATRON = re.compile(rf"\b({SIN_TILDE})\b", re.I)

FALLOS = []
HECHAS = [0]


def ok(condicion, mensaje):
    HECHAS[0] += 1
    print(("  ok   " if condicion else "  FALLO ") + mensaje)
    if not condicion:
        FALLOS.append(mensaje)


def _sin_comentarios_js(texto):
    texto = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), texto, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", l) for l in texto.split("\n"))


def cadenas_js(ruta):
    """(linea, cadena) de los literales con pinta de frase (llevan espacio)."""
    texto = _sin_comentarios_js(open(ruta, encoding="utf-8").read())
    for numero, linea in enumerate(texto.split("\n"), 1):
        for m in re.finditer(r"'((?:[^'\\]|\\.)*)'|`((?:[^`\\]|\\.)*)`", linea):
            cadena = m.group(1) if m.group(1) is not None else m.group(2)
            if " " in cadena and len(cadena) > 6 and not re.search(r"/api|=>|\.json|\$\{BASE", cadena):
                if cadena.lstrip().startswith((".", "#")):
                    continue                     # un selector de CSS, no una frase
                # lo de dentro de ${...} es código, no texto
                cadena = re.sub(r"\$\{[^{}]*(\{[^{}]*\}[^{}]*)*\}", " ", cadena)
                trozos = cadena.split()
                if all(re.fullmatch(r"[a-z0-9_-]*", t) for t in trozos) and any("-" in t for t in trozos):
                    continue                     # clases de CSS («caja-info trabajo-laminas»)
                yield numero, cadena


def mensajes_api(ruta):
    """(linea, mensaje) de los ErrorApi(..., "mensaje") de app.py."""
    texto = open(ruta, encoding="utf-8").read()
    for m in re.finditer(r"ErrorApi\(\s*\d{3}\s*,((?:\s*f?\"(?:[^\"\\]|\\.)*\"\s*)+)", texto):
        mensaje = " ".join(re.findall(r"f?\"((?:[^\"\\]|\\.)*)\"", m.group(1)))
        # las claves de la API entre comillas no se corrigen ('pestanas', «comun»)
        mensaje = re.sub(r"'[^']*'|«[^»]*»|\{[^}]*\}|/[\w/{}.-]+|\b\w+: $", "", mensaje)
        yield texto.count("\n", 0, m.start()) + 1, mensaje


def main():
    print("[textos] la pantalla y los errores del servidor, con sus tildes")
    malos = [(n, c, PATRON.search(c).group(0)) for n, c in cadenas_js(os.path.join(RAIZ, "web", "app.js"))
             if PATRON.search(c)]
    ok(not malos, "web/app.js: ningún texto visible sin sus tildes"
       + "".join(f"\n        línea {n}: «{p}» en {c[:90]!r}" for n, c, p in malos[:15]))
    malos = [(n, c, PATRON.search(c).group(0)) for n, c in mensajes_api(os.path.join(RAIZ, "app.py"))
             if PATRON.search(c)]
    ok(not malos, "app.py: ningún mensaje de error sin sus tildes"
       + "".join(f"\n        línea {n}: «{p}» en {c[:90]!r}" for n, c, p in malos[:15]))
    html = open(os.path.join(RAIZ, "web", "index.html"), encoding="utf-8").read()
    visibles = re.findall(r'title="([^"]*)"|>([^<>]{3,})<', html)
    malos = [t for par in visibles for t in par if t and PATRON.search(t)]
    ok(not malos, f"web/index.html: ningún texto sin tildes {malos[:5]}")
    print()
    if FALLOS:
        print(f"TEXTOS CON FALLOS: {len(FALLOS)} de {HECHAS[0]} comprobaciones")
        return 1
    print(f"TEXTOS OK: {HECHAS[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

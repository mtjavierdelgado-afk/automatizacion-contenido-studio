#!/usr/bin/env python3
"""EL INVENTARIO DE LO QUE SE PUEDE PULSAR en `web/app.js`.

Saca cada `h('button', …)` (y los `<a class="boton">`) con el TEXTO que lleva
escrito, para que el recorrido (`prueba_recorrido.py`) pueda decir cuántos ha
pulsado de cuántos hay. Un botón cuyo texto se arma en tiempo de ejecución
(`cond ? 'A' : 'B'`) aporta sus dos textos; uno que solo lleva una variable no
tiene texto que buscar y se cuenta aparte, como «sin texto fijo».

    python herramientas/inventario_botones.py            # el resumen
    python herramientas/inventario_botones.py --json     # la lista entera

Lo usa `prueba_recorrido.py --cobertura`: lo que no ha visto ningún escenario
sale en una lista, y esa lista es la que dice dónde falta un escenario.
"""
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(RAIZ, "web", "app.js")


def _llamada(texto, inicio):
    """El trozo de `h(` hasta su paréntesis de cierre, saltando cadenas."""
    nivel, i, n = 0, inicio, len(texto)
    while i < n:
        c = texto[i]
        if c in "'\"`":
            fin = i + 1
            while fin < n and texto[fin] != c:
                fin += 2 if texto[fin] == "\\" else 1
            i = fin + 1
            continue
        if c == "/" and texto[i + 1:i + 2] == "/":
            i = texto.find("\n", i)
            if i < 0:
                break
            continue
        if c == "/" and texto[i + 1:i + 2] == "*":
            i = texto.find("*/", i) + 2
            continue
        if c in "([{":
            nivel += 1
        elif c in ")]}":
            nivel -= 1
            if nivel == 0:
                return texto[inicio:i + 1]
        i += 1
    return texto[inicio:]


def _hijos(llamada):
    """Lo que va DESPUÉS del objeto de props: los hijos del botón."""
    # se salta `h(` + 'button' + , + {props}
    cuerpo = llamada[2:-1]
    nivel, i, partes, actual = 0, 0, [], ""
    while i < len(cuerpo):
        c = cuerpo[i]
        if c in "'\"`":
            fin = i + 1
            while fin < len(cuerpo) and cuerpo[fin] != c:
                fin += 2 if cuerpo[fin] == "\\" else 1
            actual += cuerpo[i:fin + 1]
            i = fin + 1
            continue
        if c in "([{":
            nivel += 1
        elif c in ")]}":
            nivel -= 1
        if c == "," and nivel == 0:
            partes.append(actual.strip())
            actual = ""
        else:
            actual += c
        i += 1
    if actual.strip():
        partes.append(actual.strip())
    return partes[2:]


LITERAL = re.compile(r"'((?:[^'\\]|\\.)*)'|`((?:[^`\\]|\\.)*)`")


def _textos(hijo):
    """Los textos fijos de un hijo: literales sueltos o las ramas de un ?:"""
    salida = []
    if hijo.startswith("h(") or hijo.startswith("icono"):
        return salida
    # fuera las llamadas anidadas (`h('img', …)`, `x.includes('fallo')`): sus
    # cadenas son argumentos, no texto del botón
    limpio, i = "", 0
    while i < len(hijo):
        encaje = re.match(r"[A-Za-z_$][\w$.]*\(", hijo[i:])
        if encaje and (i == 0 or not re.match(r"[\w$]", hijo[i - 1])):
            trozo = _llamada(hijo, i + encaje.end() - 1)
            i += encaje.end() - 1 + len(trozo)
            limpio += " "
            continue
        limpio += hijo[i]
        i += 1
    hijo = re.sub(r"(===|!==|==|!=)\s*('[^']*'|`[^`]*`)", " ", limpio)
    hijo = re.sub(r"('[^']*'|`[^`]*`)\s*(===|!==|==|!=)", " ", hijo)
    for encaje in LITERAL.finditer(hijo):
        crudo = encaje.group(1) if encaje.group(1) is not None else encaje.group(2)
        # de una plantilla se queda lo fijo de delante: es por lo que se busca
        crudo = re.split(r"\$\{", crudo)[0]
        crudo = crudo.replace("\\'", "'").strip()
        if len(crudo) >= 2 and not crudo.startswith(("mini", "primario", "fantasma")):
            salida.append(crudo)
    return salida


def inventario():
    with open(APP_JS, encoding="utf-8") as fh:
        texto = fh.read()
    botones = []
    for encaje in re.finditer(r"\bh\('button'", texto):
        llamada = _llamada(texto, encaje.start() + 0)
        linea = texto.count("\n", 0, encaje.start()) + 1
        textos = []
        for hijo in _hijos(llamada):
            textos.extend(_textos(hijo))
        clase = re.search(r"clase:\s*'([^']*)'", llamada[:300])
        botones.append({"linea": linea, "textos": textos,
                        "clase": clase.group(1) if clase else ""})
    return botones


def main():
    botones = inventario()
    if "--json" in sys.argv:
        print(json.dumps(botones, ensure_ascii=False, indent=1))
        return 0
    con = [b for b in botones if b["textos"]]
    print(f"{len(botones)} botones en app.js: {len(con)} con texto fijo, "
          f"{len(botones) - len(con)} sin texto fijo (iconos o variables)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

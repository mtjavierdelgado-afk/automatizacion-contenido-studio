"""Clases de CSS que ESCONDEN y que la pantalla usa como si solo marcaran.

    python prueba_clases_css.py

Paso de verdad (10-10-2026): la tarjeta de un proyecto oculto llevaba la clase
`oculto` para pintarse atenuada, y `estilo.css` ya tenia `.oculto { display:
none }` para los <input type=file>. Pulsar «Ver los ocultos» la pintaba... y
la escondia. Ningun error, ninguna prueba en rojo: solo no salia.

Esto busca las clases cuya regla SUELTA esconde el elemento (display:none,
visibility:hidden, o el recorte de «solo lectores de pantalla») y avisa si:

  - el JS las pone pegadas a otra clase («'tarjeta' + ' oculto'»), que es como
    se escribe un MODIFICADOR y no un «escondeme»;
  - el CSS las combina con otra (`.tarjeta.oculto`), que es lo mismo visto
    desde el otro lado: alguien la penso como estado.
"""
import io
import os
import re
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {mensaje}")
    else:
        _fallos.append(mensaje)
        print(f"  FALLO {mensaje}")


def reglas(css):
    """[(selector, cuerpo)] de primer nivel (y dentro de @media)."""
    sin_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(s.strip(), c) for s, c in re.findall(r"([^{}]+)\{([^{}]*)\}", sin_comentarios)]


ESCONDE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|clip\s*:\s*rect\(0")


def clases_que_esconden(css):
    salida = set()
    for selector, cuerpo in reglas(css):
        if not ESCONDE.search(cuerpo):
            continue
        for trozo in selector.split(","):
            trozo = trozo.strip()
            if re.fullmatch(r"\.[a-zA-Z][\w-]*", trozo):
                salida.add(trozo[1:])
    return salida


def main():
    css = io.open(os.path.join(RAIZ, "web", "estilo.css"), encoding="utf-8").read()
    js = io.open(os.path.join(RAIZ, "web", "app.js"), encoding="utf-8").read()
    esconden = clases_que_esconden(css)
    print(f"PRUEBA DE CLASES QUE ESCONDEN ({', '.join(sorted(esconden)) or 'ninguna'})")
    ok(bool(esconden), "se encuentran las clases que esconden (la prueba mira algo)")
    for clase in sorted(esconden):
        # 'x' + ' clase'  /  `x ${...} clase`  /  clase: 'otra clase'
        pegada = re.findall(r"""['"`][^'"`\n]*\b\w[\w-]*\s+%s\b[^'"`\n]*['"`]|['"`]\s+%s['"`]"""
                            % (re.escape(clase), re.escape(clase)), js)
        ok(not pegada, f"«{clase}» no se usa como modificador en app.js"
           + (f" -- {pegada[:3]}" if pegada else ""))
        combinada = [s for s, _ in reglas(css)
                     if re.search(r"[\w-]\.%s\b" % re.escape(clase), s)]
        ok(not combinada, f"«{clase}» no se combina con otra clase en estilo.css"
           + (f" -- {combinada[:3]}" if combinada else ""))
    ok(re.search(r"\[hidden\]\s*\{[^}]*display\s*:\s*none\s*!important", css),
       "el atributo hidden esconde aunque la clase ponga display (regla global)")
    # LA CSP DEL PROXY bloquea los atributos style="" (tambien puestos con
    # setAttribute): `h()` los aplica por CSSOM y nadie los escribe a mano
    ok("setAttribute('style'" not in js and 'setAttribute("style"' not in js,
       "app.js no pone estilos como atributo (la CSP los bloquearía)")
    ok("n.style.cssText = valor" in js, "y `h()` aplica `estilo` por CSSOM")
    html = io.open(os.path.join(RAIZ, "web", "index.html"), encoding="utf-8").read()
    ok(" style=" not in html, "index.html no lleva atributos style")
    print()
    if _fallos:
        print(f"CLASES CON FALLOS: {len(_fallos)} de {_ok + len(_fallos)}")
        return 1
    print(f"CLASES OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

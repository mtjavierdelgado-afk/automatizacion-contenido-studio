"""Prueba de RAMAS SIN CHOQUES: novedades por rama, escenarios del recorrido
por rama y docs/API.md sin choques (rama ramas-sin-choques, 05-11-2026).

Lo que se comprueba de las novedades (pasos/novedades.py):

  - sin ficheros en docs/novedades/ el texto es NOVEDADES.md byte a byte (lo
    que se ve hoy no cambia);
  - las entradas de la carpeta salen debajo del primer titulo de version, de la
    mas nueva a la mas antigua, y despues todo lo de antes;
  - un fichero que abre version («## V…») va encima de la version de antes;
  - LEEME.md, los vacios y los nombres sin fecha no salen;
  - plegar deja el MISMO texto, escribe NOVEDADES.md y borra los ficheros;
  - la pantalla (/api/sistema/novedades) y el asistente leen el texto junto;
  - en el repo de verdad, cada fichero de la carpeta tiene la forma buena y sale.

Del recorrido (prueba_recorrido.cargar_escenarios_de_ramas):

  - un fichero de pruebas/recorrido/ registra su escenario en la MISMA lista,
    detras de los de prueba_recorrido.py, y usa sus mismas funciones;
  - los que empiezan por «_» no se cargan; uno roto es un FALLO, no se calla;
  - los de pruebas/recorrido/ del repo cargan todos.

De docs/API.md: .gitattributes lo une sin choques (merge=union).

    python pasos/prueba_ramas_sin_choques.py
"""
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
RAIZ_ESTUDIO = os.path.dirname(RAIZ)
sys.path.insert(0, RAIZ)

import novedades  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"    FALLO: {texto}")


BASE = """# Novedades de CrearIA Studio

Lo que ha cambiado.

---

## V5.1 · octubre de 2026

**Lo de antes (4 de noviembre)**
- una vineta

**Lo de mas antes (3 de noviembre)**
- otra

## V3.1 · octubre de 2026

**Lo viejo**
"""


def _raiz(fragmentos=None, base=BASE):
    raiz = tempfile.mkdtemp(prefix="prueba_novedades_")
    os.makedirs(os.path.join(raiz, "docs", "novedades"))
    with open(os.path.join(raiz, "docs", "NOVEDADES.md"), "w", encoding="utf-8") as fh:
        fh.write(base)
    for nombre, texto in (fragmentos or {}).items():
        with open(os.path.join(raiz, "docs", "novedades", nombre), "w", encoding="utf-8") as fh:
            fh.write(texto)
    return raiz


def prueba_sin_ficheros():
    print("\n[1] sin ficheros sueltos, lo de siempre")
    raiz = _raiz({"LEEME.md": "# no sale\n"})
    ok(novedades.texto(raiz) == BASE, "el texto es NOVEDADES.md byte a byte")
    ok(novedades.fragmentos(raiz) == [], "LEEME.md no cuenta")
    vacia = tempfile.mkdtemp(prefix="prueba_novedades_vacia_")
    ok(novedades.texto(vacia) == "", "sin docs/ no revienta: texto vacio")
    shutil.rmtree(raiz)
    shutil.rmtree(vacia)


def prueba_en_su_sitio():
    print("\n[2] cada rama en su fichero, en su sitio")
    raiz = _raiz({
        "2026-11-05-rama-b.md": "**Lo de la rama B (5 de noviembre)**\n- b\n",
        "2026-11-06-rama-c.md": "\n\n**Lo de la rama C (6 de noviembre)**\n- c\n\n\n",
        "2026-11-05-rama-a.md": "**Lo de la rama A (5 de noviembre)**\n- a\n",
        "2026-11-07-vacia.md": "   \n",
        "sin-fecha.md": "**No sale**\n",
    })
    texto = novedades.texto(raiz)
    nombres = [n for n, _t in novedades.fragmentos(raiz)]
    ok(nombres == ["2026-11-06-rama-c.md", "2026-11-05-rama-b.md", "2026-11-05-rama-a.md"],
       f"de la mas nueva a la mas antigua, sin vacios ni nombres sin fecha ({nombres})")
    i_titulo = texto.index("## V5.1")
    i_c, i_b, i_a = (texto.index(f"Lo de la rama {x}") for x in "CBA")
    i_antes = texto.index("Lo de antes")
    ok(i_titulo < i_c < i_b < i_a < i_antes,
       "debajo del primer titulo de version y encima de lo que ya habia")
    ok("No sale" not in texto, "lo que no tiene fecha no sale")
    ok(texto.startswith(BASE[:BASE.index("## V5.1")]), "la cabecera queda igual")
    ok(texto.endswith(BASE[BASE.index("**Lo de antes"):]), "y lo de antes, entero y sin tocar")
    ok("\n\n\n" not in texto, "sin huecos de mas entre entradas")
    ok(texto.count("## V5.1") == 1, "el titulo de version, una sola vez")
    shutil.rmtree(raiz)


def prueba_version_nueva():
    print("\n[3] un fichero que abre version va encima")
    raiz = _raiz({
        "2026-11-10-v52.md": "## V5.2 · noviembre de 2026\n\n**Lo nuevo de la 5.2 (10 de noviembre)**\n- x\n",
        "2026-11-09-suelta.md": "**Una suelta (9 de noviembre)**\n- y\n",
    })
    texto = novedades.texto(raiz)
    ok(texto.index("## V5.2") < texto.index("## V5.1") < texto.index("Una suelta") < texto.index("Lo de antes"),
       "la 5.2 encima de la 5.1, y la suelta dentro de la 5.1 (la de NOVEDADES.md)")
    shutil.rmtree(raiz)


def prueba_sin_titulo():
    print("\n[4] un NOVEDADES.md sin titulo de version")
    raiz = _raiz({"2026-11-05-a.md": "**A**\n- a\n"}, base="# Novedades\n\nnada\n")
    texto = novedades.texto(raiz)
    ok(texto.startswith("# Novedades\n\nnada\n") and texto.rstrip().endswith("- a"),
       "las entradas van detras, sin perder nada")
    shutil.rmtree(raiz)


def prueba_plegar():
    print("\n[5] plegar no cambia lo que se ve")
    raiz = _raiz({
        "2026-11-05-rama-b.md": "**B**\n- b\n",
        "2026-11-06-rama-c.md": "**C**\n- c\n",
        "LEEME.md": "# se queda\n",
    })
    antes = novedades.texto(raiz)
    plegadas = novedades.plegar(raiz)
    ok(plegadas == ["2026-11-06-rama-c.md", "2026-11-05-rama-b.md"], f"pliega las dos ({plegadas})")
    with open(os.path.join(raiz, "docs", "NOVEDADES.md"), encoding="utf-8") as fh:
        escrito = fh.read()
    ok(escrito == antes, "NOVEDADES.md queda con el texto de antes, entero")
    ok(novedades.texto(raiz) == antes, "y lo que se ve es identico")
    ok(sorted(os.listdir(os.path.join(raiz, "docs", "novedades"))) == ["LEEME.md"],
       "los ficheros plegados se borran; LEEME.md se queda")
    ok(not os.path.exists(os.path.join(raiz, "docs", "NOVEDADES.md.plegando")), "sin temporales")
    ok(novedades.plegar(raiz) == [], "plegar otra vez no hace nada")
    shutil.rmtree(raiz)


def prueba_pantalla_y_asistente():
    print("\n[6] la pantalla y el asistente leen lo mismo")
    raiz = _raiz({"2026-11-05-rama-x.md": "**Lo de la rama X (5 de noviembre)**\n- x\n"})
    import asistente  # noqa: PLC0415
    docs = dict(asistente.documentos(raiz))
    ok("Lo de la rama X" in docs.get("docs/NOVEDADES.md", ""),
       "el asistente lee NOVEDADES.md con la entrada de la carpeta dentro")
    ok(docs.get("docs/NOVEDADES.md") == novedades.texto(raiz), "el mismo texto que la pantalla")
    shutil.rmtree(raiz)
    os.environ.setdefault("ESTUDIO_SIMULAR", "1")
    try:
        sys.path.insert(0, RAIZ_ESTUDIO)
        from fastapi.testclient import TestClient  # noqa: PLC0415
        import app as servidor  # noqa: PLC0415
    except Exception as fallo:  # noqa: BLE001
        print(f"  (sin servidor de prueba: {type(fallo).__name__}; se omite la ruta)")
        return
    respuesta = TestClient(servidor.app).get("/api/sistema/novedades")
    ok(respuesta.status_code == 200, "GET /api/sistema/novedades responde 200")
    ok(respuesta.json().get("texto") == novedades.texto(RAIZ_ESTUDIO),
       "y da el texto junto del repo")


def prueba_repo_de_verdad():
    print("\n[7] la carpeta del repo")
    carpeta = os.path.join(RAIZ_ESTUDIO, "docs", "novedades")
    ok(os.path.isfile(os.path.join(carpeta, "LEEME.md")), "docs/novedades/LEEME.md explica cómo se escribe")
    raros = [n for n in os.listdir(carpeta)
             if n != "LEEME.md" and not novedades._NOMBRE.match(n)]
    ok(not raros, f"todo fichero de la carpeta se llama AAAA-MM-DD-<rama>.md ({raros or 'ninguno raro'})")
    texto = novedades.texto(RAIZ_ESTUDIO)
    for nombre, trozo in novedades.fragmentos(RAIZ_ESTUDIO):
        ok(trozo in texto, f"{nombre} sale en las novedades")
        ok(trozo.startswith("**") or trozo.startswith("## "),
           f"{nombre} empieza por un título en negrita o de versión")


def prueba_cargador_del_recorrido():
    print("\n[8] los escenarios de cada rama, en su fichero")
    sys.path.insert(0, RAIZ_ESTUDIO)
    try:
        import prueba_recorrido as pr  # noqa: PLC0415
    except Exception as fallo:  # noqa: BLE001
        ok(False, f"prueba_recorrido.py se importa ({type(fallo).__name__}: {fallo})")
        return
    carpeta = tempfile.mkdtemp(prefix="prueba_cargador_")
    with open(os.path.join(carpeta, "b_rama.py"), "w", encoding="utf-8") as fh:
        fh.write("from prueba_recorrido import escenario, ok, ESCENARIOS  # noqa: F401\n"
                 "import prueba_recorrido as _pr\n"
                 "MISMO = _pr\n"
                 "@escenario\n"
                 "def escenario_de_la_rama_b(navegador, datos):\n"
                 "    pass\n")
    with open(os.path.join(carpeta, "a_rama.py"), "w", encoding="utf-8") as fh:
        fh.write("from prueba_recorrido import escenario\n"
                 "@escenario\n"
                 "def escenario_de_la_rama_a(navegador, datos):\n"
                 "    pass\n")
    with open(os.path.join(carpeta, "_apagado.py"), "w", encoding="utf-8") as fh:
        fh.write("from prueba_recorrido import escenario\n"
                 "@escenario\n"
                 "def no_debe_salir(navegador, datos):\n"
                 "    pass\n")
    with open(os.path.join(carpeta, "notas.txt"), "w", encoding="utf-8") as fh:
        fh.write("no es python\n")
    antes = list(pr.ESCENARIOS)
    fallos_antes = len(pr._fallos)
    cargados = pr.cargar_escenarios_de_ramas(carpeta)
    nuevos = [f.__name__ for f in pr.ESCENARIOS[len(antes):]]
    ok(cargados == ["a_rama.py", "b_rama.py"], f"carga los dos, en orden de nombre ({cargados})")
    ok(nuevos == ["escenario_de_la_rama_a", "escenario_de_la_rama_b"],
       f"y sus escenarios van DETRAS de los del recorrido, en la misma lista ({nuevos})")
    ok(pr.ESCENARIOS[:len(antes)] == antes, "los de prueba_recorrido.py no se mueven")
    ok("no_debe_salir" not in nuevos, "los que empiezan por «_» no se cargan")
    ok(sys.modules["recorrido_b_rama"].MISMO is sys.modules["prueba_recorrido"],
       "el fichero de la rama recibe el MISMO recorrido, no una copia")
    ok(len(pr._fallos) == fallos_antes, "sin fallos al cargar los buenos")
    with open(os.path.join(carpeta, "c_rota.py"), "w", encoding="utf-8") as fh:
        fh.write("def esto no es python(\n")
    del pr.ESCENARIOS[len(antes):]
    for nombre in ("recorrido_a_rama", "recorrido_b_rama"):
        sys.modules.pop(nombre, None)
    _salida = sys.stdout
    try:
        sys.stdout = open(os.devnull, "w")
        sys.stderr, _err = sys.stdout, sys.stderr
        pr.cargar_escenarios_de_ramas(carpeta)
    finally:
        sys.stdout.close()
        sys.stdout, sys.stderr = _salida, _err
    ok(len(pr._fallos) == fallos_antes + 1 and "c_rota.py" in pr._fallos[-1],
       "uno roto sale como FALLO del recorrido, no se calla")
    del pr._fallos[fallos_antes:]
    del pr.ESCENARIOS[len(antes):]
    shutil.rmtree(carpeta)
    # los del repo de verdad
    repo = os.path.join(RAIZ_ESTUDIO, "pruebas", "recorrido")
    ok(os.path.isfile(os.path.join(repo, "LEEME.md")), "pruebas/recorrido/LEEME.md explica cómo se escribe")
    de_verdad = sorted(n for n in os.listdir(repo) if n.endswith(".py") and not n.startswith("_"))
    cargados = pr.cargar_escenarios_de_ramas(repo)
    ok(cargados == de_verdad and len(pr._fallos) == fallos_antes,
       f"los de pruebas/recorrido/ del repo cargan todos ({len(de_verdad)})")
    del pr.ESCENARIOS[len(antes):]


def prueba_api_sin_choques():
    print("\n[9] docs/API.md y docs/NOVEDADES.md se unen sin choques")
    ruta = os.path.join(RAIZ_ESTUDIO, ".gitattributes")
    try:
        with open(ruta, encoding="utf-8") as fh:
            lineas = [x.split() for x in fh.read().splitlines() if x.strip() and not x.startswith("#")]
    except OSError:
        lineas = []
    reglas = {x[0]: x[1:] for x in lineas if x}
    ok("merge=union" in reglas.get("docs/API.md", []),
       "docs/API.md se une sumando los dos lados (se regenera con generar_api.py)")
    ok("merge=union" in reglas.get("docs/NOVEDADES.md", []),
       "docs/NOVEDADES.md también, para las ramas que aún escriben ahí")


if __name__ == "__main__":
    print("PRUEBA DE RAMAS SIN CHOQUES")
    prueba_sin_ficheros()
    prueba_en_su_sitio()
    prueba_version_nueva()
    prueba_sin_titulo()
    prueba_plegar()
    prueba_pantalla_y_asistente()
    prueba_repo_de_verdad()
    prueba_cargador_del_recorrido()
    prueba_api_sin_choques()
    print()
    if _fallos:
        print(f"RAMAS SIN CHOQUES CON FALLOS: {len(_fallos)} de {_ok + len(_fallos)} comprobaciones")
        for f in _fallos:
            print(f"  - {f}")
        sys.exit(1)
    print(f"RAMAS SIN CHOQUES OK: {_ok} comprobaciones pasan")

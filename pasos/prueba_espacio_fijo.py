"""
El ESPACIO FIJO del catalogo visual (rama espacio-fijo, 20-10-2026).

Pedido del dueño: un video que pasa entero en un mismo sitio no se reparte en
sitios. Con `espacio_fijo`, `catalogo_visual.proponer`:

  1. pide UN sitio con la descripcion LITERAL, sin la cuenta de «2 planos por
     sitio» ni el minimo de sitios, y sin lugares que rotular;
  2. y lo IMPONE por codigo sobre lo que conteste el modelo: un sitio principal
     con esa descripcion y esa luz, todos los tramos en el salvo los de los
     secundarios listados, fuera los demas sitios, rotulos vacios, sin lugares;
  3. y sin `espacio_fijo`, el prompt y el resultado son los de siempre.

En memoria y sin el CLI: `_llamar_claude` se sustituye por un doble que apunta
la instruccion y devuelve un catalogo con varios sitios y rotulos.

    python pasos/prueba_espacio_fijo.py
"""
import copy
import json
import os
import re
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

# proponer() anota su tiempo en el historico: que no sea el de verdad
_TEMPORAL = tempfile.mkdtemp(prefix="estudio_espacio_fijo_")
if not os.environ.get("ESTUDIO_ESTADISTICAS"):
    os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(_TEMPORAL, "estadisticas.json")

import catalogo_visual as C  # noqa: E402

_ok = 0
_fallos = []


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


BLOQUES = [
    {"id": "B001", "texto": "Madrid, mayo. Abrimos la persiana del local."},
    {"id": "B002", "texto": "Dentro, el horno ya esta caliente."},
    {"id": "B003", "texto": "En el almacen quedan tres sacos de harina."},
    {"id": "B004", "texto": "Y en la puerta, la cola da la vuelta a la esquina."},
    {"id": "B005", "texto": "Escribenos y te guardamos una barra."},
]

# Lo que contesta el modelo: CUATRO sitios con su rotulo, lugares que rotular,
# y un tramo que no cubre el ultimo bloque.
RESPUESTA = {
    "reparto": {"rosa": {"nombre": "Rosa", "papel": "la panadera",
                         "descripcion": "a woman in her fifties, grey bun, white apron",
                         "palabras": ["Rosa"]}},
    "sets": {
        "calle_madrid": {"rotulo": "Madrid, mayo", "descripcion": "aerial view of Madrid",
                         "palabras": ["Madrid"], "luz": "dawn, cold light"},
        "obrador": {"rotulo": "El obrador", "descripcion": "a big bakery with ovens",
                    "palabras": ["horno"], "luz": "night, warm oven glow"},
        "almacen": {"rotulo": "El almacen", "descripcion": "a dim storeroom with flour sacks",
                    "palabras": ["almacen"], "luz": "dim bulb"},
        "fachada": {"rotulo": "La puerta", "descripcion": "a shop front invented by the model",
                    "palabras": ["puerta"], "luz": "day, sun"},
    },
    "lugares": {"madrid": "MADRID"},
    "beats": [
        {"desde": "B001", "hasta": "B001", "set": "calle_madrid", "personajes": ["rosa"],
         "tono": "neutro", "accion": "Rosa sube la persiana"},
        {"desde": "B002", "hasta": "B002", "set": "obrador", "personajes": ["rosa"],
         "tono": "alegre", "accion": "el horno abierto"},
        {"desde": "B003", "hasta": "B003", "set": "almacen", "personajes": [],
         "tono": "neutro", "accion": "tres sacos"},
        {"desde": "B004", "hasta": "B004", "set": "fachada", "personajes": [],
         "tono": "alegre", "accion": "la cola en la puerta"},
    ],
    "avisos": [],
}

ESPACIO = {
    "sitio": "Panadería Rosa",
    "descripcion": "a small bakery with wooden shelves full of bread and a white counter",
    "luz": "morning, warm window light",
    "secundarios": [
        {"nombre": "Fachada", "descripcion": "a shop front with a pink awning"},
        {"nombre": "Almacén", "descripcion": ""},
        {"nombre": "Terraza", "descripcion": "a tiny terrace"},
    ],
}


def _proponer(**extra):
    """proponer() con el CLI doblado. -> (instruccion, catalogo)"""
    vistas = []

    def claude_falso(instruccion, *_a, **_k):
        vistas.append(instruccion)
        return json.dumps(RESPUESTA), {}

    real = C._llamar_claude                       # noqa: SLF001
    C._llamar_claude = claude_falso               # noqa: SLF001
    try:
        ficha = C.proponer(copy.deepcopy(BLOQUES), brief={"titulo": "Pan", "resumen": "pan"},
                           planos=12, min_s=3, max_s=6, **extra)
    finally:
        C._llamar_claude = real                   # noqa: SLF001
    return vistas[0], ficha


def prueba_sin_espacio():
    seccion("1] sin espacio fijo, todo como siempre")
    instruccion, ficha = _proponer()
    # el criterio de siempre, armado como se armaba antes de esta rama
    criterio = C.CRITERIO.format(planos_por_set=C.PLANOS_POR_SET,
                                 cuantos_planos=C._cuantos_planos(12, 3, 6),  # noqa: SLF001
                                 regiones_mapa=", ".join(C.regiones_de_mapa()) or "ninguna")
    guion, _ = C.comun.recortar(C._guion_legible(BLOQUES), 90000,     # noqa: SLF001
                                "[...guion recortado por longitud...]")
    esperada = C.INSTRUCCION.format(titulo="Pan", tema="pan", peticion="", especie="",
                                    criterio=criterio, guion=guion)
    igual(instruccion, esperada, "la instrucción es byte a byte la de siempre")
    for vacio in (None, {}, {"sitio": "x", "descripcion": "  "}):
        igual(_proponer(espacio_fijo=vacio)[0], esperada,
              f"y con espacio_fijo={vacio!r} (sin descripción) también")
    limpio = C._limpiar(copy.deepcopy(RESPUESTA), [b["id"] for b in BLOQUES])  # noqa: SLF001
    for clave in ("sets", "beats", "lugares", "reparto", "cobertura", "avisos"):
        igual(ficha[clave], limpio[clave], f"y el resultado es el de _limpiar ({clave})")
    ok("como mucho por sitio seguido" in instruccion and "COMO MINIMO" in instruccion,
       "y lleva la presión de planos por sitio")


def prueba_con_espacio():
    seccion("2] con espacio fijo")
    instruccion, ficha = _proponer(espacio_fijo=copy.deepcopy(ESPACIO))
    ok("ESTE VIDEO TIENE UN ESPACIO FIJO" in instruccion, "el prompt dice que hay un espacio fijo")
    ok(ESPACIO["descripcion"] in instruccion and "LITERAL" in instruccion,
       "con la descripción literal")
    ok("'panaderia_rosa'" in instruccion, "y el id derivado del nombre del sitio")
    ok("'morning, warm window light'" in instruccion, "y la luz dada")
    ok("'fachada' (Fachada): <<<a shop front with a pink awning>>>" in instruccion
       and "'almacen' (Almacén)" in instruccion, "y los secundarios con su id y su descripción")
    ok("como mucho por sitio seguido" not in instruccion and "COMO MINIMO" not in instruccion
       and "SE GENEROSO CON LOS SITIOS" not in instruccion,
       "sin la presión de 2 planos por sitio ni el mínimo de sitios")
    ok("devuelve 'lugares'\nvacio" in instruccion and "el rotulo que situa" not in instruccion,
       "y sin lugares que rotular")
    ok("REALES — lo que existe" in instruccion and "BEATS — el guion en su contexto" in instruccion,
       "el resto del criterio se queda")
    ok(not re.search(r"\{[a-z_]+\}", instruccion), "sin ningún {hueco} sin rellenar")

    igual(sorted(ficha["sets"]), ["almacen", "fachada", "panaderia_rosa"],
          "un solo sitio principal más los secundarios usados (fuera los demás y la terraza)")
    principal = ficha["sets"]["panaderia_rosa"]
    igual((principal["descripcion"], principal["luz"]),
          (ESPACIO["descripcion"], ESPACIO["luz"]), "el principal con la descripción y la luz dadas")
    igual(ficha["sets"]["fachada"]["descripcion"], "a shop front with a pink awning",
          "un secundario con descripción la lleva literal, no la del modelo")
    igual(ficha["sets"]["almacen"]["descripcion"], "a dim storeroom with flour sacks",
          "uno sin descripción se queda con la del modelo")
    igual({s: f["rotulo"] for s, f in ficha["sets"].items()},
          {"almacen": "", "fachada": "", "panaderia_rosa": ""}, "rótulos vacíos en todos")
    igual(ficha["lugares"], {}, "ningún lugar que rotular")
    igual([(b["desde"], b["hasta"], b["set"]) for b in ficha["beats"]],
          [("B001", "B001", "panaderia_rosa"), ("B002", "B002", "panaderia_rosa"),
           ("B003", "B003", "almacen"), ("B004", "B004", "fachada"),
           ("B005", "B005", "panaderia_rosa")],
          "todos los tramos al principal salvo los de secundarios, y el hueco cubierto")
    igual(ficha["cobertura"], 1.0, "cobertura entera")
    ok(any("espacio fijo" in a for a in ficha["avisos"]), "y lo dice en los avisos")
    igual(ficha["reparto"], C._limpiar(copy.deepcopy(RESPUESTA),               # noqa: SLF001
                                       [b["id"] for b in BLOQUES])["reparto"],
          "el reparto no se toca")

    # sin secundarios: TODO al principal; sin luz, la del modelo
    solo = {"sitio": "", "descripcion": "a plain white studio"}
    instruccion, ficha = _proponer(espacio_fijo=solo)
    ok("Todos, sin excepcion." in instruccion and "'espacio_fijo'" in instruccion,
       "sin secundarios ni nombre: todos al sitio 'espacio_fijo'")
    igual(list(ficha["sets"]), ["espacio_fijo"], "un único sitio")
    igual({b["set"] for b in ficha["beats"]}, {"espacio_fijo"}, "y todos los tramos en él")
    ok(ficha["sets"]["espacio_fijo"]["luz"], "sin luz dada se queda una del modelo")


def prueba_normalizar():
    seccion("3] lo que se acepta y lo que no")
    igual(C.normalizar_espacio_fijo(None), {}, "nada es nada")
    igual(C.normalizar_espacio_fijo({"sitio": "Cocina"}), {}, "sin descripción no hay espacio")
    igual(C.normalizar_espacio_fijo({"descripcion": "  a  kitchen ", "secundarios": ["Patio"]}),
          {"sitio": "", "descripcion": "a kitchen", "luz": "",
           "secundarios": [{"nombre": "Patio", "descripcion": ""}]},
          "se limpian los espacios y un secundario puede ser solo el nombre")
    for malo in ("una cocina", {"descripcion": 3}, {"descripcion": "x", "secundarios": "patio"},
                 {"descripcion": "x" * (C.MAX_DESCRIPCION_SITIO + 1)},
                 {"descripcion": "x", "secundarios": [{"nombre": "a"}] * (C.MAX_SECUNDARIOS + 1)},
                 {"descripcion": "x", "secundarios": [7]}):
        try:
            C.normalizar_espacio_fijo(malo)
            ok(False, f"{str(malo)[:40]!r} tiene que dar ValueError")
        except ValueError:
            ok(True, f"{str(malo)[:40]!r} da ValueError")
    principal, secundarios = C.ids_del_espacio(
        {"sitio": "Patio", "secundarios": [{"nombre": "Patio"}, {"nombre": "Patio"}]})
    igual((principal, list(secundarios)), ("patio", ["patio_2", "patio_3"]),
          "los ids no chocan entre sí")


def main():
    print("PRUEBA DEL ESPACIO FIJO DEL CATÁLOGO")
    prueba_sin_espacio()
    prueba_con_espacio()
    prueba_normalizar()
    import shutil                                            # noqa: PLC0415
    shutil.rmtree(_TEMPORAL, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"ESPACIO FIJO OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

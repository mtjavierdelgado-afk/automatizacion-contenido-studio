"""
EL NEGOCIO DE CADA CLIENTE (rama dominio-negocio y Etapa Foto C, 21-10-2026).

Decisión del dueño: «nada de un cliente metido en el código». El Studio solo
trae un tipo de negocio, el GENERAL; el de cada cliente es una FICHA que se
llena en su proyecto (`dominios.guardar_de_cliente`). Lo que se comprueba:

  1. NINGÚN CLIENTE EN EL CÓDIGO: de fábrica solo «general»; ni el fichero de
     datos ni las reglas de foto nombran consolas, mandos ni EstadoPlay.
  2. SIN FICHA, LO GENERAL: la escalera general de foto, ninguna regla de un
     negocio y el revisor general; en ilustración el reparto es el de antes.
  3. LA FICHA DE UN CLIENTE: se guarda en su fichero; sus reglas entran SOLO en
     los estilos que la llevan, en su hueco y con sus «solo si…»; sus láminas
     también; el revisor vigila lo que se escribió; las cartas son las generales.
  4. BORRARLA: deja de poder fijarse, pero un vídeo ya hecho con ella saca el
     mismo prompt; un fichero roto no tumba nada.
  5. LO QUE NO VALE se rechaza con su motivo.
  6. EL PRESET DE ESTILO guarda `dominio` y lo lleva y lo quita.

En memoria, sin el CLI y sin pagar nada.

    python pasos/prueba_dominios.py
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

# las fichas de esta prueba, en un fichero suyo: nunca en el de verdad
os.environ["ESTUDIO_DOMINIOS"] = os.path.join(tempfile.mkdtemp(prefix="dominios_"),
                                              "dominios.json")

import dominios as D  # noqa: E402
import encuadres as E  # noqa: E402

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


#: El commit de `main` con el que se abrió la rama dominio-negocio: lo de ANTES.
ANTES = "9b2f114"


def _de_antes(ruta, nombre):
    """El módulo `ruta` tal como estaba en `ANTES`, o None si no hay git."""
    try:
        codigo = subprocess.run(["git", "-C", RAIZ, "show", f"{ANTES}:{ruta}"],
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    carpeta = tempfile.mkdtemp(prefix="dominios_antes_")
    destino = os.path.join(carpeta, f"{nombre}.py")
    with open(destino, "w", encoding="utf-8") as fh:
        fh.write(codigo)
    spec = importlib.util.spec_from_file_location(f"{nombre}_antes", destino)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


#: Lo que delata a un cliente concreto metido en los datos del Studio.
DE_UN_CLIENTE = re.compile(r"consol|mando|controller|tripod|tr[ií]pode|gaming|"
                           r"karaoke|simulador|estado ?play", re.IGNORECASE)

ESTILO_FOTO = {"referencias": ["a.png"], "modo": "foto",
               "guia": {"guia": "natural light photography", "resumen_es": "foto"}}
LAMINA = [{"papel": "lamina", "cuantas": 6, "ruta": "l.png"}]
BANOS = {"prompt": "a couple chooses a glass shower screen in a small bathroom",
         "luz": "morning"}
PLANTAS = {"prompt": "a woman waters the plants", "luz": "morning"}
MANDOS = {"prompt": "two kids hold game controllers in front of the TV", "luz": "night"}


def _prompt(escena, estilo):
    import p6_assets as P6                                        # noqa: PLC0415
    return P6._prompt_completo(escena, LAMINA, estilo)             # noqa: SLF001


def prueba_ningun_cliente():
    seccion("1] ningún cliente en el código")
    igual(list(D.DE_FABRICA), ["general"], "de fábrica solo hay «general»")
    with open(D.RUTA_FABRICA, encoding="utf-8") as fh:
        datos = json.load(fh)
    igual(DE_UN_CLIENTE.findall(json.dumps(datos["dominios"], ensure_ascii=False)), [],
          "el fichero de datos no nombra consolas, mandos ni EstadoPlay")
    with open(os.path.join(RAIZ, "motores", "reglas", "reglas_foto.json"), encoding="utf-8") as fh:
        foto = json.load(fh)
    igual(DE_UN_CLIENTE.findall(json.dumps(foto["reglas"], ensure_ascii=False)), [],
          "ni las reglas de foto de la casa")
    ok(any(r.get("hueco") == "negocio" for r in foto["reglas"]),
       "que guardan el hueco donde entran las de la ficha del negocio")
    igual((E.SERVICIOS, E.SERVICIOS_EN_TEXTO, E.ESCALERA_FOTO), ((), {}, ()),
          "encuadres no trae servicios ni cartas de ningún negocio")


def prueba_sin_ficha():
    seccion("2] sin ficha, lo general")
    import medios                                                 # noqa: PLC0415
    import revisor_imagenes as R                                  # noqa: PLC0415
    reglas = medios.motor("reglas/reglas.py")
    igual(D.reglas_de_foto({}), [], "ninguna regla de un negocio")
    igual(D.de_estilo({}, "dos mandos y una consola")[0]["id"], "general",
          "aunque el texto hable de consolas: el general")
    igual(D.frases_revisor({}, "consolas"), dict(D.REVISOR_GENERAL), "y el revisor general")
    for escena, nombre in ((MANDOS, "mandos"), (PLANTAS, "plantas")):
        texto = _prompt(escena, ESTILO_FOTO)
        ok("GAME CONTROLLERS" not in texto and "GAMING EQUIPMENT" not in texto,
           f"un plano de {nombre} no recibe reglas de consolas")
    escenas = [{"id": f"S{i:03d}"} for i in range(1, 41)]
    for texto in ("una fiesta con consolas y mandos", "un baño con mampara"):
        cartas = E.repartir(escenas, semilla=3, modo="foto",
                            servicios=list(E.servicios_en_texto(texto)))
        ok(all(c["id"].startswith("foto_g_") for c in cartas.values()),
           f"«{texto}»: cartas de la escalera general de foto")
    antes = _de_antes("pasos/encuadres.py", "encuadres")
    if antes is None:
        ok(False, "no se ha podido leer encuadres.py de antes (¿sin git?)")
        return
    for semilla in (0, 7, 12345):
        ahora = {k: v["id"] for k, v in E.repartir(escenas, semilla=semilla).items()}
        vieja = {k: v["id"] for k, v in antes.repartir(escenas, semilla=semilla).items()}
        igual(ahora, vieja, f"ilustración, semilla {semilla}: las mismas cartas que antes")
    for semilla in (0, 7):
        ahora = {k: v["id"] for k, v in E.repartir(escenas, semilla=semilla, modo="foto").items()}
        vieja = {k: v["id"] for k, v in antes.repartir(escenas, semilla=semilla, modo="foto").items()}
        igual(ahora, vieja, f"foto sin servicios, semilla {semilla}: las mismas cartas que antes")
    ok("GAME CONTROLLERS" not in reglas.bloque_prompt(
        "prompt_imagen", modo="foto", contexto="game controllers",
        extra=D.reglas_de_foto({})), "el bloque de reglas de la casa tampoco")
    import moodboard as M                                         # noqa: PLC0415
    igual(DE_UN_CLIENTE.findall(M._reglas_de(reglas, ESTILO_FOTO)), [],  # noqa: SLF001
          "ni las láminas")
    import revisor_imagenes                                       # noqa: PLC0415,F401
    igual(R._frases({}, {"escenas": [{"prompt": "players with controllers"}]}),  # noqa: SLF001
          dict(D.REVISOR_GENERAL), "el revisor de imágenes usa las frases generales")


FICHA_SUYU = {
    "nombre": "Mamparas y baños a medida",
    "reglas": [
        {"texto": "Las mamparas son de vidrio templado transparente, con perfiles finos.",
         "en": "SHOWER SCREENS ARE CLEAR TEMPERED GLASS with thin metal profiles.",
         "palabras": ["mampara", "shower screen"]},
        {"texto": "Los baños están limpios y ordenados, sin botes de marca.",
         "en": "BATHROOMS ARE CLEAN AND TIDY, no branded bottles."}],
    "revisor": {"equipo": "la mampara no es de vidrio o los perfiles son gruesos"},
}


def prueba_ficha_de_cliente():
    seccion("3] la ficha del negocio de un cliente")
    import medios                                                 # noqa: PLC0415
    import moodboard as M                                         # noqa: PLC0415
    import p6_assets as P6                                        # noqa: PLC0415
    import revisor_imagenes as R                                  # noqa: PLC0415
    reglas = medios.motor("reglas/reglas.py")
    igual(D.de_cliente("cl1"), None, "un proyecto sin ficha: None")
    sin_ficha = {n: _prompt(e, ESTILO_FOTO) for n, e in (("banos", BANOS), ("plantas", PLANTAS))}
    lamina_antes = M._reglas_de(reglas, ESTILO_FOTO)               # noqa: SLF001

    ficha = D.guardar_de_cliente("cl1", FICHA_SUYU)
    igual(ficha["id"], "cliente-cl1", "su id sale del proyecto")
    ok(os.path.exists(os.environ["ESTUDIO_DOMINIOS"]), "y se guarda en su fichero")
    igual(D.de_cliente("cl1")["nombre"], "Mamparas y baños a medida", "se lee")
    igual(D.normalizar("Cliente-CL1"), "cliente-cl1", "un estilo puede llevarla")
    igual({n: _prompt(e, ESTILO_FOTO) for n, e in (("banos", BANOS), ("plantas", PLANTAS))},
          sin_ficha, "guardarla NO cambia ni una letra de un estilo que no la lleva")
    igual(M._reglas_de(reglas, ESTILO_FOTO), lamina_antes, "ni de sus láminas")  # noqa: SLF001

    fijo = dict(ESTILO_FOTO, dominio="cliente-cl1")
    texto = _prompt(BANOS, fijo)
    ok("SHOWER SCREENS ARE CLEAR TEMPERED GLASS" in texto,
       "con la ficha: su regla «solo si mampara» entra en un plano de mamparas")
    ok("BATHROOMS ARE CLEAN AND TIDY" in texto, "y la que no tiene «solo si», también")
    texto = _prompt(PLANTAS, fijo)
    ok("SHOWER SCREENS" not in texto and "BATHROOMS ARE CLEAN" in texto,
       "en un plano sin mamparas, solo la que entra siempre")
    ok(texto.index("HANDS ARE PHOTOGRAPHED") < texto.index("BATHROOMS ARE CLEAN")
       < texto.index(reglas.para("prompt_imagen", modo="foto")[-1][:40]),
       "y entran en su hueco, entre las de la casa")
    ok("BATHROOMS ARE CLEAN" in M._reglas_de(reglas, fijo), "sus láminas también")  # noqa: SLF001
    igual(_prompt(BANOS, dict(fijo, modo="ilustracion")),
          _prompt(BANOS, dict(ESTILO_FOTO, modo="ilustracion")),
          "en ilustración la ficha no cambia el prompt")
    escenas = [{"id": f"S{i:03d}", "prompt": "mampara"} for i in range(1, 30)]
    P6._asignar_cartas(escenas, P6._con_defectos({"semilla": 4, "estilo": fijo}),  # noqa: SLF001
                       "mamparas")
    ok({e["carta"] for e in escenas} <= {c["id"] for c in E.ESCALERA_FOTO_GENERAL},
       "sus cartas son las de la escalera general de foto")
    frases = R._frases(fijo, {"escenas": [{"prompt": "x"}]})        # noqa: SLF001
    igual(frases["equipo"], "la mampara no es de vidrio o los perfiles son gruesos",
          "el revisor vigila lo que se escribió del equipo")
    igual(frases["manos"], D.REVISOR_GENERAL["manos"], "y lo demás, como el general")
    D.guardar_de_cliente("cl1", dict(FICHA_SUYU, reglas=[]))
    ok("BATHROOMS ARE CLEAN" not in _prompt(BANOS, fijo), "cambiarla cambia lo que entra")
    D.guardar_de_cliente("cl1", FICHA_SUYU)
    ok(any(t["id"] == "cliente-cl1" and not t["de_fabrica"] for t in D.listar()),
       "listar la enseña, detrás del general")


def prueba_borrar():
    seccion("4] borrar la ficha")
    fijo = dict(ESTILO_FOTO, dominio="cliente-cl1")
    antes = _prompt(BANOS, fijo)
    ok(D.borrar_de_cliente("cl1"), "se borra")
    igual(D.de_cliente("cl1"), None, "el proyecto se queda sin ficha")
    try:
        D.normalizar("cliente-cl1")
        ok(False, "una ficha borrada no se puede fijar")
    except ValueError:
        ok(True, "una ficha borrada no se puede fijar")
    igual(_prompt(BANOS, fijo), antes,
          "pero un vídeo ya hecho con ella saca el MISMO prompt: nada queda para rehacer")
    ok(not D.borrar_de_cliente("cl1"), "borrar una que no está: False")
    with open(os.environ["ESTUDIO_DOMINIOS"], "w", encoding="utf-8") as fh:
        fh.write("{roto")
    igual(D.de_usuario(), {}, "un fichero roto no tumba nada")
    igual(_prompt(BANOS, fijo), _prompt(BANOS, ESTILO_FOTO), "y el vídeo sale como general")
    os.remove(os.environ["ESTUDIO_DOMINIOS"])


def prueba_lo_que_no_vale():
    seccion("5] lo que no vale")
    for malo, motivo in (({"nombre": ""}, "sin decir qué hace"),
                         ({"nombre": "x" * 200}, "demasiado largo"),
                         ({"nombre": "Otro", "reglas": [{"texto": "x", "gravedad": "rara"}]},
                          "una regla rara"),
                         ({"nombre": "Otro", "revisor": "no"}, "revisor que no es objeto"),
                         ("no es un objeto", "no es un objeto")):
        try:
            D.guardar_de_cliente("cl2", malo)
            ok(False, f"{motivo}: tenía que rechazarse")
        except ValueError:
            ok(True, f"{motivo}: se rechaza")
    for cid in ("", "../x", "   "):
        try:
            D.guardar_de_cliente(cid, {"nombre": "x"}) if cid.strip("./") else D.id_de_cliente(cid)
            ok(cid == "../x", f"proyecto {cid!r}: se limpia o se rechaza")
        except ValueError:
            ok(True, f"proyecto {cid!r}: se rechaza")
    igual(D.id_de_cliente("../X"), "cliente-x", "el id se limpia: nada de rutas")
    for malo in ("telenovela", 3):
        try:
            D.normalizar(malo)
            ok(False, f"{malo!r} tiene que dar ValueError")
        except ValueError:
            ok(True, f"{malo!r} da ValueError")
    igual([D.normalizar(x) for x in (None, " ", "Auto", " General ")], ["", "", "", "general"],
          "automático y general se limpian")
    igual(D.fijado("no es un dict"), None, "un estilo que no es un objeto: automático")
    igual(D.fijado({"dominio": "basura"}), None, "un valor guardado roto es automático")


def prueba_presets():
    seccion("6] el preset de Estilo guarda `dominio`")
    import presets_canal as PC                                    # noqa: PLC0415
    D.guardar_de_cliente("cl3", {"nombre": "Clínica dental"})
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "dominio": "Cliente-CL3"}),  # noqa: SLF001
          {"calidad": "low", "dominio": "cliente-cl3"}, "normalizado")
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "dominio": ""}),         # noqa: SLF001
          {"calidad": "low"}, "automático no se guarda")
    try:
        PC._limpiar_datos("estilo", {"calidad": "low", "dominio": "x"})          # noqa: SLF001
        ok(False, "una ficha que no existe tiene que dar ErrorPreset")
    except PC.ErrorPreset:
        ok(True, "una ficha que no existe da ErrorPreset")
    datos = PC.datos_de_params({"assets": {"estilo": {"referencias": [], "dominio": "cliente-cl3"}}})
    igual((datos.get("estilo") or {}).get("dominio"), "cliente-cl3",
          "guardar el estilo de un vídeo la lleva")
    sin = PC.datos_de_params({"assets": {"estilo": {"referencias": []}}})
    ok("dominio" not in (sin.get("estilo") or {}), "y uno sin ella no la inventa")


def main():
    print("PRUEBA DEL NEGOCIO DE CADA CLIENTE")
    prueba_ningun_cliente()
    prueba_sin_ficha()
    prueba_ficha_de_cliente()
    prueba_borrar()
    prueba_lo_que_no_vale()
    prueba_presets()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo.splitlines()[0]}")
        return 1
    print(f"DOMINIOS OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

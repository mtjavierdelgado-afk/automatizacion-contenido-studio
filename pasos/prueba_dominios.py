"""
EL DOMINIO DE UN NEGOCIO (rama dominio-negocio, 21-10-2026).

Lo de EstadoPlay salió del código a `pasos/dominios.py`. Lo que se comprueba:

  1. LOS MISMOS DATOS: la escalera de foto de servicios, los servicios y sus
     patrones son los de antes, y la escalera expandida por peso es idéntica en
     longitud y en orden (de eso depende el sorteo de cartas: `carta_de`).
  2. SIN DOMINIO FIJADO, EL MISMO REPARTO: para muchos vídeos de prueba, las
     cartas que salen son las mismas que con el `encuadres` de antes de la rama.
  3. CON DOMINIO FIJADO: «general» reparte la escalera general aunque el texto
     hable de consolas; «estadoplay» la de servicios aunque no las nombre.
  4. EL REVISOR: con EstadoPlay, la instrucción es letra por letra la de antes;
     en un vídeo que no es de consolas, sin televisores ni mandos.
  5. EL PRESET DE ESTILO guarda `dominio` y lo lleva y lo quita.

Y de la Etapa Foto C (tipos de negocio como datos, editables):

  6. LAS REGLAS DE FOTO SIGUEN AL TIPO: en automático, el bloque de reglas de
     cada encargo es letra por letra el de antes (las de consolas salieron de
     `reglas_foto.json` a su tipo y vuelven a entrar en el mismo sitio);
     fijado en general, ninguna de consolas; fijado en EstadoPlay, las suyas.
  7. LOS TIPOS DEL DUEÑO: se crean, se cambian y se borran en su fichero; sus
     reglas entran SOLO si un estilo los fija, con sus «solo si…»; crear uno
     no cambia ni una letra de un vídeo en automático; los de fábrica no se
     tocan; lo que no vale se rechaza con su motivo.

En memoria, sin el CLI y sin pagar nada.

    python pasos/prueba_dominios.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

# los tipos del dueño de esta prueba, en un fichero suyo: nunca en el de verdad
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


#: El commit de `main` con el que se abrió la rama: lo de ANTES.
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


TEXTOS = [
    "",
    "una fiesta con consolas y mandos para todos",
    "un baño pequeño con mampara corrediza",
    "simuladores de carreras con volante y pedales, y realidad virtual",
    "karaoke en la sala, con PS5 y Xbox",
    "plantas de interior junto a una ventana",
]


def prueba_mismos_datos(antes):
    seccion("1] los datos de EstadoPlay son los de antes")
    if antes is None:
        ok(False, "no se ha podido leer encuadres.py de antes (¿sin git?)")
        return
    igual(E.ESCALERA_FOTO, antes.ESCALERA_FOTO, "la escalera de foto de servicios, igual")
    igual(E.ESCALERA_FOTO_GENERAL, antes.ESCALERA_FOTO_GENERAL, "la general, igual")
    igual(E.ESCALERA, antes.ESCALERA, "la de ilustración, igual")
    igual(E.SERVICIOS, antes.SERVICIOS, "los servicios, igual")
    igual(E.SERVICIOS_EN_TEXTO, antes.SERVICIOS_EN_TEXTO, "y sus patrones, igual")
    igual([c["id"] for c in E._repartidas(E.ESCALERA_FOTO)],             # noqa: SLF001
          [c["id"] for c in antes._repartidas(antes.ESCALERA_FOTO)],     # noqa: SLF001
          "la escalera expandida por peso: misma longitud y mismo orden")
    ok(D.ESTADOPLAY["escalera"] is E.ESCALERA_FOTO, "y encuadres usa el MISMO objeto del dominio")


def prueba_mismo_reparto(antes):
    seccion("2] sin dominio fijado, las cartas son las de antes")
    if antes is None:
        return
    escenas = [{"id": f"S{i:03d}"} for i in range(1, 41)]
    for modo in ("ilustracion", "foto"):
        for texto in TEXTOS:
            servicios = list(E.servicios_en_texto(texto))
            for semilla in (0, 7, 12345):
                ahora = {k: v["id"] for k, v in E.repartir(
                    escenas, semilla=semilla, modo=modo, servicios=servicios).items()}
                vieja = {k: v["id"] for k, v in antes.repartir(
                    escenas, semilla=semilla, modo=modo, servicios=servicios).items()}
                if ahora != vieja:
                    ok(False, f"{modo}, «{texto[:30]}», semilla {semilla}: cartas distintas")
                    return
    ok(True, "40 planos × 2 modos × 6 textos × 3 semillas: las mismas cartas")
    for texto in TEXTOS:
        igual(D.servicios_en_texto(texto), antes.servicios_en_texto(texto),
              f"servicios de «{texto[:30]}», los mismos")


def prueba_dominio_fijado():
    seccion("3] con el dominio fijado en el estilo")
    import p6_assets as P6                                        # noqa: PLC0415
    general = {"estilo": {"dominio": "general", "prompt": "una fiesta con consolas y mandos"}}
    igual(P6.servicios_del_video(general, "consolas por todas partes"), [],
          "«general»: ningún servicio aunque el texto hable de consolas")
    igual(E.escalera_para("foto", [], D.GENERAL), E.ESCALERA_FOTO_GENERAL,
          "y la escalera es la general")
    ep = {"estilo": {"dominio": "estadoplay", "prompt": "un cumpleaños"}}
    igual(P6.servicios_del_video(ep, "tarta y globos"), ["consolas"],
          "«estadoplay» sin servicios nombrados: los suyos de siempre (consolas)")
    igual(P6.servicios_del_video(ep, "con simuladores de carreras"), ["simuladores"],
          "y si nombra otro, ese")
    auto = {"estilo": {"prompt": "un cumpleaños"}}
    igual(P6.servicios_del_video(auto, "tarta y globos"), [],
          "sin fijar y sin servicios en el texto: ninguno, como antes")
    igual(D.de_estilo({}, "con mandos")[0]["id"], "estadoplay", "automático: el texto delata EstadoPlay")
    igual(D.de_estilo({}, "un baño")[0]["id"], "general", "automático: y si no, general")
    for malo in ("telenovela", 3):
        try:
            D.normalizar(malo)
            ok(False, f"{malo!r} tiene que dar ValueError")
        except ValueError:
            ok(True, f"{malo!r} da ValueError")
    igual(D.normalizar(None), "", "sin nada, automático")
    igual([D.normalizar(x) for x in (" ", "Auto", "AUTOMATICO", " General ")], ["", "", "", "general"],
          "se limpia antes de comparar")
    igual(D.fijado("no es un dict"), None, "un estilo que no es un objeto: automático")
    igual(D.fijado({"dominio": "basura"}), None, "un valor guardado roto es automático, no un fallo")


def prueba_revisor():
    seccion("4] el revisor: las frases del negocio")
    import revisor_imagenes as R                                  # noqa: PLC0415
    antes = _de_antes("pasos/revisor_imagenes.py", "revisor_imagenes")
    huecos = dict(n=3, titulo="t", formato="vertical", estilo="e", guia="g", encargo="x",
                  reglas="r", reglas_estilo="", referencia="", planos="p", tipos="a | b")
    if antes is None:
        ok(False, "no se ha podido leer revisor_imagenes.py de antes")
        return
    ep = D.REVISOR_ESTADOPLAY
    igual(R.INSTRUCCION.format(**huecos, f_equipo=ep["equipo"], f_congruencia=ep["congruencia"],
                               f_manos=ep["manos"], f_orientacion=ep["orientacion"]),
          antes.INSTRUCCION.format(**huecos),
          "con EstadoPlay, la instrucción es letra por letra la de antes")
    igual(R.REFERENCIA.format(continuidad=ep["continuidad"], plano="P"),
          antes.REFERENCIA.format(plano="P"), "y la referencia del plano de antes también")
    general = R._frases({"prompt": "un baño con mampara"},                # noqa: SLF001
                        {"escenas": [{"prompt": "a small bathroom"}]})
    texto = R.INSTRUCCION.format(**huecos, f_equipo=general["equipo"],
                                 f_congruencia=general["congruencia"],
                                 f_manos=general["manos"], f_orientacion=general["orientacion"])
    ok("tripode" not in texto and "mandos" not in texto and "consola" not in texto,
       "un vídeo de baños: sin trípodes, mandos ni consolas en el criterio")
    igual(R._frases({"prompt": "fiesta"}, {}, guia="Sala:\nconsolas en fila")["equipo"],  # noqa: SLF001
          ep["equipo"], "la guía en texto, con saltos de línea, también delata las consolas")
    igual(R._frases({"prompt": "fiesta"},                                  # noqa: SLF001
                    {"escenas": [{"prompt": "two players with controllers"}]})["equipo"],
          ep["equipo"], "y uno de consolas, el criterio de EstadoPlay")


def prueba_presets():
    seccion("5] el preset de Estilo guarda `dominio`")
    import presets_canal as PC                                    # noqa: PLC0415
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "dominio": "General"}),  # noqa: SLF001
          {"calidad": "low", "dominio": "general"}, "normalizado")
    igual(PC._limpiar_datos("estilo", {"calidad": "low", "dominio": ""}),         # noqa: SLF001
          {"calidad": "low"}, "automático no se guarda")
    try:
        PC._limpiar_datos("estilo", {"calidad": "low", "dominio": "x"})          # noqa: SLF001
        ok(False, "un dominio que no existe tiene que dar ErrorPreset")
    except PC.ErrorPreset:
        ok(True, "un dominio que no existe da ErrorPreset")
    datos = PC.datos_de_params({"assets": {"estilo": {"referencias": [], "dominio": "general"}}})
    igual((datos.get("estilo") or {}).get("dominio"), "general", "guardar el estilo de un vídeo lo lleva")
    sin = PC.datos_de_params({"assets": {"estilo": {"referencias": []}}})
    ok("dominio" not in (sin.get("estilo") or {}), "y uno sin dominio no lo inventa")


def _reglas_de_antes():
    """`motores/reglas/reglas.py` y `reglas_foto.json` de `ANTES`, juntos."""
    carpeta = tempfile.mkdtemp(prefix="reglas_antes_")
    try:
        for nombre in ("reglas.py", "reglas_foto.json"):
            codigo = subprocess.run(
                ["git", "-C", RAIZ, "show", f"{ANTES}:motores/reglas/{nombre}"],
                capture_output=True, text=True, check=True).stdout
            with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as fh:
                fh.write(codigo)
    except (OSError, subprocess.CalledProcessError):
        return None
    spec = importlib.util.spec_from_file_location("reglas_antes",
                                                  os.path.join(carpeta, "reglas.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


CONTEXTOS = ["", "a woman waters the plants", "four kids hold game controllers",
             "Fiesta con CONSOLAS en Lima", "gamers at an e-sports final",
             "a racing wheel and pedals", "un baño con mampara",
             "que se vea una consola en la mesa"]


def prueba_reglas_siguen_al_tipo():
    seccion("6] las reglas de foto siguen al tipo de negocio")
    import medios                                                 # noqa: PLC0415
    reglas = medios.motor("reglas/reglas.py")
    antes = _reglas_de_antes()
    if antes is None:
        ok(False, "no se ha podido leer reglas.py de antes")
        return
    for ambito in ("prompt_imagen", "reparto"):
        for contexto in CONTEXTOS:
            if reglas.bloque_prompt(ambito, modo="foto", contexto=contexto,
                                    extra=D.reglas_de_foto({})) != \
                    antes.bloque_prompt(ambito, modo="foto", contexto=contexto):
                ok(False, f"{ambito}, «{contexto}»: el bloque de reglas cambió")
                break
        else:
            ok(True, f"{ambito}: en automático, {len(CONTEXTOS)} encargos con el "
                     "bloque de reglas letra por letra el de antes")
    ok(not any(r.get("solo_si") for r in reglas.cargar("foto")["reglas"]),
       "en reglas_foto.json no queda ninguna regla de un negocio")
    ok(any(r.get("hueco") == "negocio" for r in reglas.cargar("foto")["reglas"]),
       "y queda el hueco donde entran las del tipo")
    mandos = "four kids hold game controllers"
    igual(reglas.bloque_prompt("prompt_imagen", modo="foto", contexto=mandos,
                               extra=D.reglas_de_foto({"dominio": "general"})),
          reglas.bloque_prompt("prompt_imagen", modo="foto", contexto=""),
          "fijado en «general»: ni una regla de consolas aunque el plano tenga mandos")
    ok("GAME CONTROLLERS" in reglas.bloque_prompt(
        "prompt_imagen", modo="foto", contexto=mandos,
        extra=D.reglas_de_foto({"dominio": "estadoplay"})),
       "fijado en «estadoplay»: las suyas, con su «solo si»")


def _prompt(escena, estilo):
    import p6_assets as P6                                        # noqa: PLC0415
    lamina = [{"papel": "lamina", "cuantas": 6, "ruta": "l.png"}]
    return P6._prompt_completo(escena, lamina, estilo)             # noqa: SLF001


def prueba_tipos_del_dueno():
    seccion("7] los tipos de negocio del dueño")
    import p6_assets as P6                                        # noqa: PLC0415
    import moodboard as M                                         # noqa: PLC0415
    import medios                                                 # noqa: PLC0415
    import revisor_imagenes as R                                  # noqa: PLC0415
    reglas = medios.motor("reglas/reglas.py")
    estilo = {"referencias": ["a.png"], "modo": "foto",
              "guia": {"guia": "natural light photography", "resumen_es": "foto"}}
    banos = {"prompt": "a couple chooses a glass shower screen in a small bathroom",
             "luz": "morning"}
    plantas = {"prompt": "a woman waters the plants", "luz": "morning"}
    sin_tipos = {(n, k): _prompt(e, dict(estilo, prompt=k))
                 for n, e in (("banos", banos), ("plantas", plantas))
                 for k in ("", "bathroom remodeling")}
    lamina_antes = M._reglas_de(reglas, estilo)                    # noqa: SLF001
    igual(D.de_usuario(), {}, "sin fichero: ningún tipo propio")

    creado = D.guardar({
        "nombre": "Mamparas y baños", "descripcion": "reformas de baño",
        "palabras": "mampara, baño, ducha",
        "reglas": [
            {"texto": "Las mamparas son de vidrio templado transparente, con perfiles finos.",
             "en": "SHOWER SCREENS ARE CLEAR TEMPERED GLASS with thin metal profiles.",
             "palabras": ["mampara", "shower screen"]},
            {"texto": "Los baños están limpios y ordenados, sin botes de marca.",
             "en": "BATHROOMS ARE CLEAN AND TIDY, no branded bottles."}],
        "revisor": {"equipo": "las mamparas no son de vidrio o los perfiles son gruesos"}})
    igual(creado["id"], "mamparas-y-banos", "se crea con un id sacado del nombre")
    ok(os.path.exists(os.environ["ESTUDIO_DOMINIOS"]), "y se guarda en su fichero")
    igual(D.normalizar("Mamparas-y-Banos"), "mamparas-y-banos", "un estilo puede fijarlo")

    cambiado = {k: _prompt(e, dict(estilo, prompt=p)) for k, e, p in
                [(k, banos if k[0] == "banos" else plantas, k[1]) for k in sin_tipos]}
    igual(cambiado, sin_tipos,
          "crear un tipo NO cambia ni una letra de un vídeo en automático, "
          "aunque el texto nombre sus palabras")
    igual(M._reglas_de(reglas, estilo), lamina_antes,               # noqa: SLF001
          "ni de sus láminas")

    fijo = dict(estilo, dominio="mamparas-y-banos")
    texto = _prompt(banos, fijo)
    ok("SHOWER SCREENS ARE CLEAR TEMPERED GLASS" in texto,
       "fijado: su regla con «solo si mampara/shower screen» entra en un plano de mamparas")
    ok("BATHROOMS ARE CLEAN AND TIDY" in texto, "y la que no tiene «solo si», también")
    texto = _prompt(plantas, fijo)
    ok("SHOWER SCREENS" not in texto and "BATHROOMS ARE CLEAN" in texto,
       "en un plano sin mamparas, solo la que entra siempre")
    ok(texto.index("HANDS ARE PHOTOGRAPHED") < texto.index("BATHROOMS ARE CLEAN")
       < texto.index(reglas.para("prompt_imagen", modo="foto")[-1][:40]),
       "y entran en su hueco, entre las de la casa")
    ok("GAME CONTROLLERS" not in _prompt({"prompt": "kids with game controllers"}, fijo),
       "un tipo propio no arrastra las reglas de consolas")
    ok("BATHROOMS ARE CLEAN" in M._reglas_de(reglas, fijo),        # noqa: SLF001
       "sus láminas también llevan sus reglas")
    igual(_prompt(banos, dict(fijo, modo="ilustracion")),
          _prompt(banos, {k: v for k, v in fijo.items() if k not in ("modo", "dominio")}
                  | {"modo": "ilustracion"}),
          "en ilustración el tipo no cambia el prompt")

    escenas = [{"id": f"S{i:03d}", "prompt": "mampara"} for i in range(1, 30)]
    P6._asignar_cartas(escenas, P6._con_defectos({"semilla": 4, "estilo": fijo}),  # noqa: SLF001
                       "mamparas")
    general = {e["carta"] for e in escenas}
    ok(general <= {c["id"] for c in E.ESCALERA_FOTO_GENERAL},
       "sus cartas son las de la escalera general de foto")
    frases = R._frases(fijo, {"escenas": [{"prompt": "x"}]})          # noqa: SLF001
    igual(frases["equipo"], "las mamparas no son de vidrio o los perfiles son gruesos",
          "el revisor vigila lo que se escribió del equipo")
    igual(frases["manos"], D.REVISOR_GENERAL["manos"], "y lo demás, como el general")
    igual(R._frases({}, {"escenas": [{"prompt": "una ducha nueva"}]})["equipo"],  # noqa: SLF001
          "las mamparas no son de vidrio o los perfiles son gruesos",
          "en automático, el revisor lo reconoce por sus palabras (con o sin tildes)")
    igual(R._frases({}, {"escenas": [{"prompt": "consolas y una ducha"}]})["equipo"],  # noqa: SLF001
          D.REVISOR_ESTADOPLAY["equipo"], "pero los de fábrica van primero, como antes")

    D.guardar({"nombre": "Mamparas y baños", "palabras": ["mampara"],
               "reglas": []}, "mamparas-y-banos")
    ok("BATHROOMS ARE CLEAN" not in _prompt(banos, fijo), "cambiarlo cambia lo que entra")
    for malo, motivo in (({"nombre": ""}, "sin nombre"),
                         ({"nombre": "x" * 90}, "nombre largo"),
                         ({"nombre": "Otro", "palabras": ["p"] * 0 + [f"p{i}" for i in range(40)]},
                          "demasiadas palabras"),
                         ({"nombre": "Otro", "reglas": [{"texto": "x", "gravedad": "rara"}]},
                          "una regla rara"),
                         ({"nombre": "General (cualquier negocio)"}, "nombre de uno de fábrica"),
                         ({"nombre": "mamparas y baños"}, "nombre repetido"),
                         ("no es un objeto", "no es un objeto")):
        try:
            D.guardar(malo)
            ok(False, f"{motivo}: tenía que rechazarse")
        except ValueError:
            ok(True, f"{motivo}: se rechaza")
    for tid in ("estadoplay", "general"):
        try:
            D.guardar({"nombre": "Cambio"}, tid)
            ok(False, f"{tid}: un tipo de fábrica no se cambia")
        except ValueError:
            ok(True, f"{tid}: un tipo de fábrica no se cambia")
        try:
            D.borrar(tid)
            ok(False, f"{tid}: ni se borra")
        except ValueError:
            ok(True, f"{tid}: ni se borra")
    otro = D.guardar({"nombre": "Mamparas & baños!"})
    ok(otro["id"] != "mamparas-y-banos", f"dos nombres con el mismo id se separan ({otro['id']})")
    ok(any(t["id"] == otro["id"] and not t["de_fabrica"] for t in D.listar()),
       "listar enseña los del dueño")
    ok([t["id"] for t in D.listar()][:2] == ["general", "estadoplay"],
       "con los de fábrica delante")

    ok(D.borrar("mamparas-y-banos"), "se borra")
    igual(D.fijado(fijo), None, "y un estilo que lo tenía fijado vuelve a automático")
    igual(_prompt(banos, fijo), _prompt(banos, estilo), "con el prompt de automático")
    ok(not D.borrar("mamparas-y-banos"), "borrar uno que no está: False")

    with open(os.environ["ESTUDIO_DOMINIOS"], "w", encoding="utf-8") as fh:
        fh.write("{roto")
    igual(D.de_usuario(), {}, "un fichero roto no tumba nada: ningún tipo propio")
    igual(_prompt(banos, estilo), sin_tipos[("banos", "")], "y los vídeos salen como siempre")
    os.remove(os.environ["ESTUDIO_DOMINIOS"])


def main():
    print("PRUEBA DE LOS DOMINIOS")
    antes = _de_antes("pasos/encuadres.py", "encuadres")
    prueba_mismos_datos(antes)
    prueba_mismo_reparto(antes)
    prueba_dominio_fijado()
    prueba_revisor()
    prueba_presets()
    prueba_reglas_siguen_al_tipo()
    prueba_tipos_del_dueno()
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

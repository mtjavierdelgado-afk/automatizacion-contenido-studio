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


def main():
    print("PRUEBA DE LOS DOMINIOS")
    antes = _de_antes("pasos/encuadres.py", "encuadres")
    prueba_mismos_datos(antes)
    prueba_mismo_reparto(antes)
    prueba_dominio_fijado()
    prueba_revisor()
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

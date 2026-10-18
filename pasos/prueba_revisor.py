"""Prueba del REVISOR DE IMAGENES (pasos/revisor_imagenes.py).

Sin CLI de verdad y sin pagar nada: `cli_claude.ejecutar` se sustituye por un
doble que contesta lo que diria el revisor. Lo que se comprueba es lo que
cuesta dinero si falla:

  - que una imagen ya revisada NO se vuelve a revisar mientras no cambie;
  - que las notas del revisor entran en el repaso como las de una persona
    (pantalla «imagenes», con su plano, su segundo y su alcance, que p6 lee) y
    que las de las personas no se tocan;
  - que `elegir` respeta el modo, los topes de imagenes y de dolares y los
    intentos por plano: es lo unico que separa «corrige solo» de «se gasta el
    saldo en un bucle»;
  - que los ajustes del revisor se validan.

    python pasos/prueba_revisor.py
"""
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

_TMP = tempfile.mkdtemp(prefix="prueba_revisor_")
# nada de esta suite escribe en los ajustes ni en el almacen de verdad
os.environ["ESTUDIO_AJUSTES"] = os.path.join(_TMP, "ajustes.json")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(_TMP, "secretos")
os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(_TMP, "estadisticas.json")

from PIL import Image                                       # noqa: E402

import ajustes                                              # noqa: E402
import repaso                                               # noqa: E402
import revisor_imagenes as rev                              # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        return True
    _fallos.append(mensaje)
    print(f"      FALLO: {mensaje}")
    return False


def igual(obtenido, esperado, mensaje):
    return ok(obtenido == esperado,
              f"{mensaje} (esperaba {esperado!r}, llego {obtenido!r})")


def seccion(titulo):
    print(f"\n  {titulo}")


class Proyecto:
    """Lo unico que el revisor y el repaso piden de un proyecto."""

    def __init__(self, raiz):
        self.raiz = raiz
        self.id = os.path.basename(raiz)

    def ruta(self, nombre):
        return os.path.join(self.raiz, nombre)


class Doble:
    """El CLI: contesta lo que se le prepare y apunta lo que se le pide."""

    def __init__(self):
        self.respuestas = []
        self.llamadas = []

    def ejecutar(self, instruccion, **kw):
        self.llamadas.append({"instruccion": instruccion, **kw})
        if not self.respuestas:
            raise RuntimeError("el doble no tiene respuesta preparada")
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return json.dumps(respuesta), {}


def _png(ruta, color):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    Image.new("RGB", (1024, 1536), color).save(ruta)


def _montar():
    raiz = os.path.join(_TMP, "video")
    shutil.rmtree(raiz, ignore_errors=True)
    os.makedirs(raiz)
    proyecto = Proyecto(raiz)
    carpeta = os.path.join(raiz, "pasos", "assets", "v3", "escenas")
    imagenes = {}
    for sid, color in (("S001", "red"), ("S002", "green"), ("S003", "blue")):
        imagenes[sid] = os.path.join(carpeta, f"{sid}.png")
        _png(imagenes[sid], color)
    plan = {"titulo": "Torneo de 8 en menos de una hora", "formato": "vertical",
            "bloques": [{"id": "B1", "texto": "Ocho jugadores, una estación."}],
            "escenas": [
                {"id": "S001", "t_in": 0.0, "t_out": 3.0, "origen": {"bloque": "B1"},
                 "narracion": "Ocho jugadores y una sola estación.",
                 "prompt": "Eight young adults around a TV on a black tripod stand",
                 "encuadre": "plano general"},
                {"id": "S002", "t_in": 3.0, "t_out": 6.0, "origen": {"bloque": "B1"},
                 "narracion": "Cuartos de final en diez minutos.",
                 "prompt": "Two players with white DualSense controllers",
                 "encuadre": "plano medio"},
                {"id": "S003", "t_in": 6.0, "t_out": 9.0, "origen": {"bloque": "B1"},
                 "narracion": "Y la final, con todos mirando.",
                 "prompt": "Everyone facing the TV", "encuadre": "plano general"}]}
    return proyecto, plan, imagenes


def _veredicto(sid, veredicto="bien", gravedad="", nota="", alcance=""):
    return {"id": sid, "veredicto": veredicto, "gravedad": gravedad,
            "problemas": ([{"tipo": "equipo", "detalle": "la tele va en un mueble"}]
                          if veredicto == "corregir" else []),
            "nota": nota, "alcance": alcance}


def prueba_revisar_y_apuntar(doble):
    seccion("revisar y apuntar en el repaso")
    proyecto, plan, imagenes = _montar()
    # una nota de una PERSONA en el mismo plano: no se toca
    persona = repaso.anadir(proyecto, "que el chico de la izquierda sonría", 1.0,
                            plano="S001", pantalla="imagenes")
    ok("autor" not in persona and "alcance" not in persona and "gravedad" not in persona,
       "una nota de persona se escribe como siempre, sin campos nuevos")
    igual(rev.sin_revisar(proyecto, imagenes), ["S001", "S002", "S003"],
          "al principio no hay nada revisado")
    doble.respuestas = [{"planos": [
        _veredicto("S001", "corregir", "alta",
                   "Conserva a los ocho jugadores. Pon la tele en su rack de trípode "
                   "negro, no en un mueble.", "sustituye"),
        _veredicto("S002"),
        _veredicto("S003", "corregir", "media",
                   "Que los jugadores miren a la tele, no a cámara.", "retoque"),
        _veredicto("S999", "corregir", "alta", "un plano que no existe", "retoque"),
        "basura"]}]
    veredictos = rev.revisar(proyecto, plan, imagenes, ["S001", "S002", "S003"],
                             estilo={"prompt": "Foto realista. Estación: rack de trípode negro."},
                             encargo="Torneo en casa", reglas="  - foto-manos-con-mandos",
                             guia="  Style guide", formato="vertical")
    igual(len(doble.llamadas), 1, "tres planos caben en una llamada")
    llamada = doble.llamadas[-1]
    igual(llamada.get("cwd"), proyecto.raiz, "el agente corre en la raiz del proyecto")
    igual(tuple(llamada.get("herramientas_permitidas") or ()), ("Read",),
          "el agente solo puede leer")
    ok("Bash" in (llamada.get("herramientas_vetadas") or ()), "Bash vetado")
    for sid in ("S001", "S002", "S003"):
        ok(f"revisor/{sid}.jpg" in llamada["instruccion"],
           f"la instruccion nombra la copia de {sid} dentro del proyecto")
        copia = os.path.join(proyecto.raiz, "revisor", f"{sid}.jpg")
        ok(os.path.isfile(copia), f"la copia de {sid} existe")
        with Image.open(copia) as im:
            ok(max(im.size) <= rev.LADO, f"la copia de {sid} es pequeña ({im.size})")
    ok("Ocho jugadores y una sola estación." in llamada["instruccion"],
       "la instruccion lleva lo que dice la voz")
    ok("rack de trípode negro" in llamada["instruccion"],
       "la instruccion lleva las indicaciones del estilo")
    igual(sorted(veredictos), ["S001", "S002", "S003"],
          "los ids que no son de la tanda y la basura se ignoran")

    resumen = rev.apuntar(proyecto, plan, veredictos)
    igual(resumen["revisados"], 3, "tres revisados")
    igual(resumen["bien"], 1, "uno bien")
    notas = repaso.leer(proyecto)["notas"]
    del_revisor = [n for n in notas if n.get("autor") == "revisor"]
    igual(len(del_revisor), 2, "dos notas del revisor")
    s1 = next(n for n in del_revisor if n["plano"] == "S001")
    igual(repaso.pantalla_de(s1), "imagenes", "la nota es de la pantalla Imágenes")
    igual(s1["alcance"], "sustituye", "el alcance viaja en la nota (lo lee p6)")
    igual(s1["gravedad"], "alta", "la gravedad viaja en la nota")
    igual(s1["t"], 0.0, "la nota va al segundo de su plano")
    igual(s1["ancla"], "Ocho jugadores y una sola estación.",
          "la nota se ancla a la narracion del plano")
    igual(s1["estado"], "pendiente", "la nota queda pendiente")
    ok(any(n["id"] == persona["id"] and "autor" not in n for n in notas),
       "la nota de la persona sigue ahi, intacta")
    igual(rev.sin_revisar(proyecto, imagenes), [],
          "lo revisado no se vuelve a revisar")
    igual(rev.sin_revisar(proyecto, imagenes, forzar=True), ["S001", "S002", "S003"],
          "con forzar, todo otra vez")

    seccion("una imagen que cambia se vuelve a mirar")
    _png(imagenes["S003"], "yellow")
    igual(rev.sin_revisar(proyecto, imagenes), ["S003"], "solo la que cambio")
    doble.respuestas = [{"planos": [_veredicto("S003")]}]
    rev.apuntar(proyecto, plan, rev.revisar(proyecto, plan, imagenes, ["S003"]))
    ok(not any(n.get("autor") == "revisor" and n["plano"] == "S003"
               for n in repaso.leer(proyecto)["notas"]),
       "ahora esta bien: su nota pendiente del revisor se quita")

    seccion("una nota pendiente se reescribe, no se duplica")
    _png(imagenes["S001"], "purple")
    doble.respuestas = [{"planos": [_veredicto(
        "S001", "corregir", "media", "Mandos DualSense blancos, no negros.", "retoque")]}]
    rev.apuntar(proyecto, plan, rev.revisar(proyecto, plan, imagenes, ["S001"]))
    s1s = [n for n in repaso.leer(proyecto)["notas"]
           if n.get("autor") == "revisor" and n["plano"] == "S001"]
    igual(len(s1s), 1, "sigue habiendo una sola nota del revisor en S001")
    igual(s1s[0]["texto"], "Mandos DualSense blancos, no negros.", "con el texto nuevo")
    igual(s1s[0]["alcance"], "retoque", "y el alcance nuevo")

    seccion("si el agente falla, no se marca nada como revisado")
    _png(imagenes["S002"], "white")
    doble.respuestas = [RuntimeError("sin cupo")]
    veredictos = rev.revisar(proyecto, plan, imagenes, ["S002"])
    ok(veredictos.get("_fallos"), "el fallo se devuelve")
    rev.apuntar(proyecto, plan, veredictos)
    igual(rev.sin_revisar(proyecto, imagenes), ["S002"],
          "lo que no se pudo mirar se mira la proxima vez")
    return proyecto, plan, imagenes


def prueba_elegir(proyecto):
    seccion("elegir que se rehace solo")
    # deja dos notas del revisor: S001 alta (sustituye) y S003 media (retoque)
    plan = {"escenas": [{"id": "S001", "t_in": 0.0, "narracion": "a"},
                        {"id": "S003", "t_in": 6.0, "narracion": "c"}]}
    rev.apuntar(proyecto, plan, {
        "S001": {"veredicto": "corregir", "gravedad": "alta", "nota": "nota uno",
                 "alcance": "sustituye", "huella": "x"},
        "S003": {"veredicto": "corregir", "gravedad": "media", "nota": "nota tres",
                 "alcance": "retoque", "huella": "y"}})
    ids = {n["plano"]: n["id"] for n in repaso.leer(proyecto)["notas"]
           if n.get("autor") == "revisor" and n.get("estado") != "aplicado"}
    igual(rev.elegir(proyecto, "manual", 10, 1.0, 0.05)[:2], ([], []),
          "manual: nada se rehace solo")
    igual(rev.elegir(proyecto, "autonomo", 10, 1.0, 0.05)[:2], ([], [ids["S001"]]),
          "autonomo: solo lo grave")
    igual(rev.elegir(proyecto, "automatico", 10, 1.0, 0.05)[:2],
          ([ids["S003"]], [ids["S001"]]), "automatico: todo, separado por alcance")
    retoque, sustituye, porque = rev.elegir(proyecto, "automatico", 1, 1.0, 0.05)
    igual((retoque, sustituye), ([], [ids["S001"]]),
          "tope de imagenes: primero lo grave")
    ok("tope" in porque, "y se dice por que se quedan las demas")
    igual(rev.elegir(proyecto, "automatico", 10, 0.06, 0.05)[:2], ([], [ids["S001"]]),
          "tope de dolares: 0,06 $ dan para una imagen de 0,05 $")
    igual(rev.elegir(proyecto, "automatico", 0, 1.0, 0.05)[:2], ([], []),
          "tope cero: nada")
    igual(rev.elegir(proyecto, "automatico", 10, 1.0, 0.05, planos=["S003"])[:2],
          ([ids["S003"]], []), "acotado a lo que dibujo la tanda: las demas no")
    igual(rev.elegir(proyecto, "automatico", 10, 1.0, 0.05, planos=[])[:2], ([], []),
          "una tanda que no dibujo nada marcado no rehace nada")
    retoque, sustituye, porque = rev.elegir(proyecto, "automatico", 10, 1.0, 0.0)
    igual((retoque, sustituye), ([], []), "sin precio conocido no se rehace nada solo")
    ok("no se sabe" in porque, "y se dice por que")
    igual(rev.contar_intento(proyecto, [ids["S001"]], 0.05), 1, "cuenta un plano")
    estado = rev.leer_estado(proyecto)
    igual(estado["intentos"].get("S001"), 1, "se cuenta el intento")
    igual(estado["gastado_usd"], 0.05, "y su coste")
    igual(rev.elegir(proyecto, "automatico", 10, 0.06, 0.05)[:2], ([], []),
          "lo gastado cuenta contra el tope del video")
    rev.contar_intento(proyecto, [ids["S001"]], 0.0)
    retoque, sustituye, porque = rev.elegir(proyecto, "automatico", 10, 5.0, 0.05)
    igual((retoque, sustituye), ([ids["S003"]], []),
          f"un plano rehecho {rev.INTENTOS_POR_PLANO} veces espera a una persona")
    ok("esperan a una persona" in porque, "y se dice")

    seccion("descartar")
    ok(rev.descartar(proyecto, "S003"), "descartar quita la nota pendiente")
    ok(not any(n.get("autor") == "revisor" and n["plano"] == "S003"
               and n.get("estado") != "aplicado"
               for n in repaso.leer(proyecto)["notas"]), "ya no esta")
    igual(rev.leer_estado(proyecto)["revisadas"]["S003"]["veredicto"], "bien",
          "queda como bien")
    resumen = rev.resumen(proyecto)
    igual([p["plano"] for p in resumen["pendientes"]], ["S001"],
          "el resumen ensena lo que queda")


def prueba_ajustes():
    seccion("los ajustes del revisor")
    leidos = ajustes.leer()
    igual(leidos["revisor_modo"], "manual", "de fabrica, manual")
    igual(leidos["revisor_max_imagenes"], 10, "tope de imagenes de fabrica")
    igual(leidos["revisor_max_usd"], 1.0, "tope de dolares de fabrica")
    guardados = ajustes.guardar({"revisor_modo": "automatico", "revisor_max_usd": "2.5",
                                 "revisor_vueltas": 3})
    igual(guardados["revisor_modo"], "automatico", "se guarda el modo")
    igual(guardados["revisor_max_usd"], 2.5, "el tope se guarda como numero")
    for malo in ({"revisor_modo": "siempre"}, {"revisor_vueltas": 9},
                 {"revisor_max_imagenes": -1}, {"revisor_max_usd": True},
                 {"revisor_max_usd": "mucho"}):
        try:
            ajustes.guardar(malo)
            ok(False, f"{malo} tenia que rechazarse")
        except ValueError:
            ok(True, "")
    with open(os.environ["ESTUDIO_AJUSTES"], "w", encoding="utf-8") as fh:
        json.dump({"revisor_modo": "raro", "revisor_vueltas": 99}, fh)
    leidos = ajustes.leer()
    igual((leidos["revisor_modo"], leidos["revisor_vueltas"]), ("manual", 2),
          "un fichero roto se lee con los valores de fabrica")


def main():
    doble = Doble()
    original = rev.cli_claude.ejecutar
    rev.cli_claude.ejecutar = doble.ejecutar
    try:
        proyecto, _plan, _imagenes = prueba_revisar_y_apuntar(doble)
        prueba_elegir(proyecto)
        prueba_ajustes()
    finally:
        rev.cli_claude.ejecutar = original
        shutil.rmtree(_TMP, ignore_errors=True)

    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PRUEBA REVISOR OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

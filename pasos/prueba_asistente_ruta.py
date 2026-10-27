"""Prueba del asistente de la Ruta (pasos/asistente_ruta.py).

No llama al CLI: se sustituye por un doble. Lo que se comprueba es lo que se
puede romper en silencio:

  - que el prompt de sistema quepa en una linea, en ASCII (va como argumento);
  - que la orden de verdad NO deje leer ficheros ni ejecutar nada, corra fuera
    del Studio y solo permita buscar en internet;
  - que sin clave el asistente este APAGADO (503) y con clave rechace la mala;
  - que el primer turno lleve el contexto y los siguientes reanuden la sesion,
    y que al no poder reanudar se empiece otra con lo ultimo pegado;
  - que un cupo agotado no se reintente, un turno a la vez, y el tope diario.

    python pasos/prueba_asistente_ruta.py
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TMP = tempfile.mkdtemp(prefix="prueba_ruta_")
os.environ["ESTUDIO_SECRETOS"] = TMP          # antes de importar claves
os.environ.pop("ESTUDIO_RUTA_CLAVE", None)

import asistente_ruta as A  # noqa: E402
import cli_claude  # noqa: E402

FALLOS = []
N = [0]


def comprobar(condicion, texto):
    N[0] += 1
    print(("  ok   " if condicion else "  FALLO ") + texto)
    if not condicion:
        FALLOS.append(texto)


def esperar(charla, segundos=5):
    fin = time.time() + segundos
    while time.time() < fin:
        v = charla.ver()
        if v["estado"] != "pensando":
            return v
        time.sleep(0.02)
    return charla.ver()


def codigo_de(fn, *args):
    try:
        fn(*args)
    except A.ErrorRuta as fallo:
        return fallo.codigo
    return 200


def main():
    print("1. el prompt de sistema")
    s = A.sistema()
    comprobar("\n" not in s and "\r" not in s, "una sola linea")
    comprobar(s.isascii(), "solo ASCII")
    comprobar('"' not in s, "sin comillas dobles")
    comprobar("NO das las respuestas de los examenes" in s, "veta las respuestas de examen")
    comprobar("113" in s, "lleva la linea de ayuda")

    print("2. la orden de verdad")
    visto = {}

    def falso_ejecutar(mensaje, **kw):
        visto.update(kw, mensaje=mensaje)
        return "hola", {"session_id": "s1"}
    original = cli_claude.ejecutar
    cli_claude.ejecutar = falso_ejecutar
    try:
        A.ejecutar_cli("=== PREGUNTA ===\nhola")
    finally:
        cli_claude.ejecutar = original
    for h in ("Read", "Bash", "Write", "Edit", "Glob", "Grep"):
        comprobar(h in visto["herramientas_vetadas"], f"{h} vetada")
    comprobar(set(visto["herramientas_permitidas"]) == {"WebSearch", "WebFetch"},
              "solo WebSearch/WebFetch permitidas")
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    comprobar(not os.path.abspath(visto["cwd"]).startswith(raiz),
              "no corre dentro del Studio")
    comprobar(os.listdir(visto["cwd"]) == [], "su carpeta esta vacia")

    print("3. la clave")
    comprobar(A.clave_configurada() == "", "de fabrica no hay clave")
    comprobar(codigo_de(A.comprobar_clave, "x") == 503, "sin clave: 503 (apagado)")
    clave, nueva = A.generar_clave()
    comprobar(nueva and len(clave) >= 32, "genera una clave larga")
    comprobar(oct(os.stat(A.fichero_clave()).st_mode)[-3:] == "600" or os.name == "nt",
              "el fichero es 600")
    comprobar(A.generar_clave() == (clave, False), "no la pisa si ya existe")
    comprobar(codigo_de(A.comprobar_clave, "mala") == 401, "clave mala: 401")
    comprobar(codigo_de(A.comprobar_clave, "") == 401, "sin cabecera: 401")
    comprobar(codigo_de(A.comprobar_clave, clave) == 200, "clave buena: pasa")

    print("4. la charla")
    os.environ["ESTUDIO_SIMULAR"] = "1"
    v = A.preguntar("", "¿qué es la DGAC?", "TAREAS: f1 ...")
    ch = A.obtener(v["charla"])
    comprobar(ch is not None and v["estado"] == "pensando", "abre charla y piensa")
    r = esperar(ch)
    comprobar(r["estado"] == "listo" and "arranque" in r["texto"], "contesta el arranque")
    comprobar("DGAC" in r["texto"], "le llega la pregunta")
    r2 = esperar(A.obtener(A.preguntar(ch.id, "y la ley 30740?")["charla"]))
    comprobar("reanudando" in r2["texto"], "el segundo turno reanuda la sesion")
    comprobar(A.preguntar("zzz-no-hex", "hola")["charla"] != ch.id,
              "un id raro abre otra charla")
    comprobar(codigo_de(A.preguntar, ch.id, "   ") == 400, "pregunta vacia: 400")
    comprobar(codigo_de(A.preguntar, ch.id, "x" * 5000) == 400, "pregunta enorme: 400")

    print("5. reanudar falla, cupo y un turno a la vez")
    llamadas = []

    def doble(mensaje, extra=()):
        llamadas.append((mensaje, list(extra)))
        if "--resume" in extra:
            raise RuntimeError("No conversation found with session ID")
        return "otra vez", {"session_id": "nueva"}
    A.ejecutor = lambda: doble
    r3 = esperar(A.obtener(A.preguntar(ch.id, "sigues ahi?")["charla"]))
    comprobar(r3["estado"] == "listo" and len(llamadas) == 2, "reempieza al no poder reanudar")
    comprobar("LO ÚLTIMO QUE HABLARON" in llamadas[1][0], "con lo ultimo pegado")
    comprobar(ch.sesion == "nueva", "y se queda con la sesion nueva")

    llamadas.clear()

    def cupo(mensaje, extra=()):
        llamadas.append(1)
        raise RuntimeError("Claude usage limit reached")
    A.ejecutor = lambda: cupo
    r4 = esperar(A.obtener(A.preguntar(ch.id, "otra")["charla"]))
    comprobar(r4["estado"] == "error" and len(llamadas) == 1, "el cupo no se reintenta")
    comprobar("límite" in r4["texto"], "y lo explica")

    import threading
    suelta = threading.Event()

    def lento(mensaje, extra=()):
        suelta.wait(3)
        return "ya", {"session_id": "nueva"}
    A.ejecutor = lambda: lento
    A.preguntar(ch.id, "una")
    comprobar(codigo_de(A.preguntar, ch.id, "dos") == 409, "segunda a la vez: 409")
    suelta.set()
    esperar(ch)

    print("6. el tope diario")
    A.ejecutor = lambda: (lambda m, extra=(): ("ok", {"session_id": "t"}))
    tope = A.TOPE_DIARIO
    A.TOPE_DIARIO = A._CUENTA_DIA["n"] + 1
    try:
        c = A.obtener(A.preguntar("", "la ultima de hoy")["charla"])
        esperar(c)
        comprobar(codigo_de(A.preguntar, c.id, "una mas") == 429, "pasado el tope: 429")
    finally:
        A.TOPE_DIARIO = tope

    shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{N[0]} comprobaciones, {len(FALLOS)} fallos")
    sys.exit(1 if FALLOS else 0)


if __name__ == "__main__":
    main()

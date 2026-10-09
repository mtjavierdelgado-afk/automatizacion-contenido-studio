"""Prueba del asistente (pasos/asistente.py) y de la marca de la guia de inicio.

No llama al CLI: se sustituye por un doble. Lo que se comprueba es lo que se
puede romper en silencio:

  - que el prompt de sistema quepa en una linea y no lleve acentos (va como
    argumento de claude.cmd, ver la cabecera del modulo);
  - que `secretos/`, el .env y los claves.json queden VETADOS para Read, en la
    orden de verdad que se le pasa a cli_claude;
  - que el primer turno lleve la documentacion y los siguientes reanuden la
    sesion (`--resume`), y que al no poder reanudar se vuelva a empezar con la
    conversacion pegada en vez de perderla;
  - que un cupo agotado o un plazo vencido NO se reintenten;
  - que una charla admita un turno a la vez y se pueda cancelar;
  - que `onboarding_visto` se lea, se guarde y rechace lo que no sea booleano.

    C:\\IA\\venvs\\cartoon\\Scripts\\python.exe pasos\\prueba_asistente.py
"""
import os
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asistente  # noqa: E402
import cli_claude  # noqa: E402

FALLOS = []


def comprobar(condicion, texto):
    print(("  ok   " if condicion else "  FALLO ") + texto)
    if not condicion:
        FALLOS.append(texto)


def igual(obtenido, esperado, texto):
    comprobar(obtenido == esperado,
              texto if obtenido == esperado
              else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def seccion(titulo):
    print(f"\n[{titulo}]")


def esperar(charla, segundos=10):
    """Hasta que el ultimo turno deje de pensar."""
    limite = time.time() + segundos
    while time.time() < limite and charla.ocupada():
        time.sleep(0.02)
    return charla.ver()


class Doble:
    """Un `ejecutar` que apunta lo que recibe y contesta lo que se le diga."""

    def __init__(self, respuestas=None):
        self.llamadas = []
        self.respuestas = list(respuestas or [])
        self.bloqueo = None            # un Event: si esta, espera a que se abra

    def __call__(self, mensaje, extra=(), avance=None, raiz=None, carpetas_extra=(),
                 proyecto=""):
        self.llamadas.append({"mensaje": mensaje, "extra": list(extra or []),
                              "avance": avance, "raiz": raiz,
                              "carpetas": tuple(carpetas_extra or ()),
                              "proyecto": proyecto})
        if self.bloqueo is not None:
            if avance is not None:
                avance.al_cancelar = lambda: self.bloqueo.set()
            self.bloqueo.wait(10)
            if avance is not None and avance.cancelado:
                raise RuntimeError("matado")
        respuesta = self.respuestas.pop(0) if self.respuestas else "vale"
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta, {"session_id": f"ses-{len(self.llamadas)}",
                           "usage": {"input_tokens": 12, "output_tokens": 3},
                           "_ajuste": {"cuenta": "la mia"}}


def prueba_prompt():
    seccion("1] el prompt de sistema y los vetos")
    sistema = asistente.sistema()
    comprobar("\n" not in sistema and "\r" not in sistema,
              "el prompt de sistema cabe en una linea (claude.cmd parte la orden)")
    comprobar(all(ord(c) < 128 for c in sistema),
              "y no lleva acentos ni enies: va como argumento y la consola lo recodifica")
    comprobar("secretos" in sistema and "Configuracion" in sistema,
              "dice que no lea secretos y donde se cambian las claves")

    vetos = asistente.vetos_de_lectura("C:/estudio")
    comprobar("Read(./secretos/**)" in vetos, "veta secretos/ relativa al cwd")
    comprobar(any(v.startswith("Read(//") and "secretos" in v for v in vetos),
              f"y en forma absoluta: {vetos}")
    comprobar("Read(**/.env)" in vetos and "Read(**/claves.json)" in vetos,
              "y el .env y claves.json por nombre, esten donde esten")
    comprobar(all("," not in v for v in vetos),
              "ninguna regla lleva comas: la orden las une con comas")


def prueba_orden():
    seccion("2] lo que de verdad se le pasa a cli_claude")
    recibido = {}

    def falso(instruccion, **kw):
        recibido.update(kw)
        recibido["instruccion"] = instruccion
        return "hola", {"session_id": "s1", "usage": {}}

    original = cli_claude.ejecutar
    cli_claude.ejecutar = falso
    try:
        carpeta = tempfile.mkdtemp(prefix="asist_")
        try:
            texto, sobre = asistente.ejecutar_cli(
                "pregunta", extra=["--resume", "abc"], raiz="C:/estudio",
                carpetas_extra=(carpeta, "C:/no/existe/seguro"))
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
    finally:
        cli_claude.ejecutar = original
    igual(texto, "hola", "devuelve lo que contesta el CLI")
    permitidas = tuple(recibido["herramientas_permitidas"])
    igual(permitidas[:3], ("Read", "Grep", "Glob"), "puede LEER: Read, Grep y Glob")
    comprobar(all(p.startswith("mcp__estudio__") for p in permitidas[3:]) and len(permitidas) > 3,
              f"y las herramientas del Estudio, pre-autorizadas: {permitidas[3:]}")
    comprobar("--mcp-config" not in recibido["extra"],
              "sin ESTUDIO_API no se carga ningun servidor MCP")
    primera = dict(recibido)
    os.environ["ESTUDIO_API"] = "http://127.0.0.1:65000"
    cli_claude.ejecutar = falso
    try:
        asistente.ejecutar_cli("pregunta", raiz="C:/estudio", proyecto="p7")
    finally:
        cli_claude.ejecutar = original
        os.environ.pop("ESTUDIO_API", None)
    extra_mcp = recibido["extra"]
    # lo que sigue comprueba la PRIMERA llamada (la que reanudaba)
    recibido.clear()
    recibido.update(primera)
    comprobar("--mcp-config" in extra_mcp, "con ESTUDIO_API se carga el servidor estudio")
    import json as _json
    config = _json.load(open(extra_mcp[extra_mcp.index("--mcp-config") + 1], encoding="utf-8"))
    servidor = config["mcpServers"]["estudio"]
    comprobar(servidor["args"][0].endswith("mcp_estudio.py")
              and servidor["env"]["ESTUDIO_API"] == "http://127.0.0.1:65000"
              and servidor["env"]["ESTUDIO_PROYECTO_ABIERTO"] == "p7",
              f"y el fichero apunta al servidor, a la API y al proyecto abierto: {servidor}")
    vetadas = recibido["herramientas_vetadas"]
    comprobar("Bash" in vetadas and "Write" in vetadas and "WebFetch" in vetadas,
              "Bash, Write y WebFetch van vetadas")
    comprobar("Read(./secretos/**)" in vetadas,
              "y el veto de secretos/ viaja en la MISMA lista, no en otra")
    igual(recibido["modelo"], asistente.MODELO, "con el modelo del asistente")
    igual(recibido["esfuerzo"], asistente.ESFUERZO, "y su esfuerzo")
    igual(recibido["cwd"], os.path.abspath("C:/estudio"), "corre en la raiz del Estudio")
    extra = recibido["extra"]
    comprobar(extra[:2] == ["--resume", "abc"], f"reanuda la sesion que se le dice: {extra}")
    comprobar("--add-dir" in extra and extra.count("--add-dir") == 1,
              "y anade la carpeta de proyectos que existe, y NO la que no existe")
    comprobar(recibido["tiempo_max_s"] == asistente.TIEMPO_MAX_S, "con su techo de tiempo")

    # el orden completo tiene que poder construirse con esas listas
    orden = cli_claude.construir_orden(
        asistente.MODELO, asistente.ESFUERZO, sistema=asistente.sistema(),
        herramientas_vetadas=tuple(asistente.HERRAMIENTAS_VETADAS)
        + tuple(asistente.vetos_de_lectura()),
        herramientas_permitidas=asistente.HERRAMIENTAS_PERMITIDAS)
    comprobar("--allowedTools" in orden and "--disallowedTools" in orden,
              "construir_orden acepta las dos listas")
    comprobar("--strict-mcp-config" in orden, "y sin servidores MCP")


def prueba_mensajes():
    seccion("3] los mensajes: arranque con documentacion, turnos que reanudan")
    arranque = asistente.mensaje_de_arranque("FOTO", "que pasa", asistente.RAIZ_ESTUDIO)
    comprobar("=== DOCUMENTO CLAUDE.md ===" in arranque, "el arranque lleva CLAUDE.md")
    comprobar("=== DOCUMENTO README.md ===" in arranque, "y README.md")
    comprobar("docs/API.md" in arranque, "y la API")
    comprobar(arranque.index("DOCUMENTO") < arranque.index("ESTADO DEL ESTUDIO")
              < arranque.index("=== PREGUNTA ==="),
              "en orden: documentacion, estado, pregunta")
    comprobar("CONVERSACION ANTERIOR" not in arranque,
              "sin conversacion anterior en una charla nueva")

    historia = [{"quien": "tu", "texto": f"p{i}"} for i in range(30)]
    con = asistente.mensaje_de_arranque("FOTO", "otra", asistente.RAIZ_ESTUDIO, historia)
    comprobar("CONVERSACION ANTERIOR" in con, "al reempezar va la conversacion pegada")
    comprobar("[PERSONA] p29" in con and "[PERSONA] p0" not in con,
              f"pero solo los ultimos {asistente.TURNOS_AL_REEMPEZAR} turnos")

    turno = asistente.mensaje_de_turno("FOTO", "que pasa")
    comprobar("DOCUMENTO" not in turno and "FOTO" in turno and "que pasa" in turno,
              "un turno que reanuda lleva la foto y la pregunta, no la documentacion")
    comprobar(len(asistente.documentos("C:/no/existe")) == 0,
              "sin carpeta de documentos no revienta: contesta sin ellos")


def prueba_charla():
    seccion("4] una charla: primer turno, reanudar, y volver a empezar si no se puede")
    asistente.olvidar_todas()
    doble = Doble(["primera", "segunda"])
    charla = asistente.nueva()
    ficha = charla.preguntar("hola", "FOTO1", raiz=asistente.RAIZ_ESTUDIO,
                             ejecutar=doble, pid="p1")
    igual(len(ficha["turnos"]), 2, "preguntar deja dos turnos: el tuyo y el suyo pensando")
    igual(ficha["turnos"][1]["estado"], "pensando", "el suyo esta pensando")
    ficha = esperar(charla)
    igual(ficha["turnos"][1]["estado"], "listo", "y termina listo")
    igual(ficha["turnos"][1]["texto"], "primera", "con lo que contesto el doble")
    igual(ficha["turnos"][1]["cuenta"], "la mia", "y con que cuenta")
    comprobar(ficha["reanuda"], "la charla se acuerda de la sesion del CLI")
    igual(doble.llamadas[0]["extra"], [], "el primer turno NO reanuda nada")
    comprobar("=== DOCUMENTO" in doble.llamadas[0]["mensaje"],
              "y lleva la documentacion")
    igual(ficha["proyecto"], "p1", "y apunta el proyecto desde el que se pregunto")

    charla.preguntar("y ahora", "FOTO2", raiz="C:/estudio", ejecutar=doble)
    ficha = esperar(charla)
    igual(len(doble.llamadas), 2, "el segundo turno es UNA llamada")
    igual(doble.llamadas[1]["extra"][:2], ["--resume", "ses-1"],
          "que reanuda la sesion del primero")
    comprobar("=== DOCUMENTO" not in doble.llamadas[1]["mensaje"]
              and "FOTO2" in doble.llamadas[1]["mensaje"],
              "sin la documentacion y con la foto NUEVA")
    igual(ficha["turnos"][3]["texto"], "segunda", "y contesta")

    # reanudar falla -> se vuelve a empezar con la conversacion pegada
    doble = Doble([RuntimeError("No conversation found with session ID"), "tercera"])
    charla.preguntar("tercera pregunta", "FOTO3", raiz="C:/estudio", ejecutar=doble)
    ficha = esperar(charla)
    igual(len(doble.llamadas), 2, "si reanudar falla se llama dos veces")
    comprobar("--resume" not in doble.llamadas[1]["extra"],
              "la segunda ya no reanuda")
    comprobar("CONVERSACION ANTERIOR" in doble.llamadas[1]["mensaje"]
              and "[ASISTENTE] segunda" in doble.llamadas[1]["mensaje"],
              "y lleva la conversacion anterior pegada")
    igual(ficha["turnos"][5]["estado"], "listo", "la persona no ve el tropiezo")
    igual(ficha["turnos"][5]["texto"], "tercera", "solo la respuesta")

    # un cupo agotado o un plazo vencido NO se reintentan
    for fallo, nombre in ((cli_claude.LimiteAgotado("se acabo el cupo"), "cupo agotado"),
                          (cli_claude.TiempoAgotado("vencio"), "plazo vencido")):
        doble = Doble([fallo, "no deberia"])
        charla.preguntar("otra", "FOTO", raiz="C:/estudio", ejecutar=doble)
        ficha = esperar(charla)
        igual(len(doble.llamadas), 1, f"un {nombre} al reanudar NO vuelve a empezar")
        igual(ficha["turnos"][-1]["estado"], "error", "sale como error")
        comprobar(str(fallo) in ficha["turnos"][-1]["texto"], "con su motivo")

    comprobar(not charla.cancelar(), "cancelar sin nada en marcha dice que no habia")


def prueba_ocupada_y_cancelar():
    seccion("5] un turno a la vez, y se puede parar")
    charla = asistente.nueva()
    doble = Doble(["tarde"])
    doble.bloqueo = threading.Event()
    charla.preguntar("lenta", "FOTO", raiz="C:/estudio", ejecutar=doble)
    time.sleep(0.1)
    comprobar(charla.ocupada(), "mientras contesta, la charla esta ocupada")
    try:
        charla.preguntar("otra", "FOTO", raiz="C:/estudio", ejecutar=doble)
        comprobar(False, "preguntar mientras contesta tenia que fallar")
    except asistente.Ocupada as fallo:
        comprobar("cancelala" in str(fallo), "preguntar mientras contesta da Ocupada")
    except asistente.ErrorAsistente:
        comprobar(False, "tenia que ser Ocupada, no un ErrorAsistente a secas")
    comprobar(charla.cancelar(), "cancelar dice que habia algo en marcha")
    ficha = esperar(charla)
    igual(ficha["turnos"][-1]["estado"], "cancelado", "y el turno queda cancelado")
    igual(len(doble.llamadas), 1, "sin reintentar")

    try:
        charla.preguntar("", "FOTO", ejecutar=doble)
        comprobar(False, "una pregunta vacia tenia que fallar")
    except asistente.ErrorAsistente:
        comprobar(True, "una pregunta vacia da ErrorAsistente")
    try:
        charla.preguntar("x" * (asistente.MAX_PREGUNTA + 1), "FOTO", ejecutar=doble)
        comprobar(False, "una pregunta enorme tenia que fallar")
    except asistente.ErrorAsistente as fallo:
        comprobar("log" in str(fallo), "y una enorme dice que pegue solo el trozo")


def prueba_registro():
    seccion("6] el registro de charlas")
    asistente.olvidar_todas()
    a = asistente.nueva()
    comprobar(asistente.obtener(a.id) is a, "una charla nueva se reencuentra por su id")
    comprobar(asistente.obtener("no") is None, "y una que no existe da None")
    a.tocada = time.time() - asistente.CADUCIDAD_CHARLA_S - 1
    comprobar(asistente.obtener(a.id) is None, "una charla caducada se olvida sola")
    ids = [asistente.nueva().id for _ in range(asistente.MAX_CHARLAS + 5)]
    comprobar(len(asistente._CHARLAS) <= asistente.MAX_CHARLAS + 1,
              f"por encima de {asistente.MAX_CHARLAS} se van las mas viejas")
    comprobar(asistente.obtener(ids[-1]) is not None, "y la ultima sigue")
    comprobar(asistente.olvidar(ids[-1]) and not asistente.olvidar(ids[-1]),
              "olvidar dice si habia algo")
    asistente.olvidar_todas()
    igual(len(asistente._CHARLAS), 0, "olvidar_todas vacia el registro")

    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        comprobar(asistente.ejecutor() is asistente.ejecutar_simulado,
                  "con ESTUDIO_SIMULAR el ejecutor es el doble")
        texto, sobre = asistente.ejecutar_simulado(
            asistente.mensaje_de_turno("F", "hola?"), extra=["--resume", "z9"])
        comprobar("hola?" in texto and sobre["session_id"] == "z9",
                  "el doble repite la pregunta y conserva la sesion al reanudar")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)
    comprobar(asistente.ejecutor() is asistente.ejecutar_cli,
              "y sin ella, el CLI de verdad")


def prueba_historial():
    seccion("6b] el historial: las charlas sobreviven a reiniciar el servicio")
    carpeta = tempfile.mkdtemp(prefix="asist_hist_")
    antes = asistente.CARPETA_HISTORIAL
    asistente.CARPETA_HISTORIAL = carpeta
    try:
        asistente.olvidar_todas()
        vacia = asistente.nueva()
        igual(asistente.listar(), [], "una charla sin preguntas no entra en el historial")
        comprobar(not os.listdir(carpeta), "ni deja fichero")

        charla = asistente.nueva()
        charla.preguntar("como se parte un bloque?", "FOTO", raiz=asistente.RAIZ_ESTUDIO,
                         ejecutar=Doble(["asi se parte"]), pid="p9")
        esperar(charla)
        charla._hilo.join(5)
        ruta = os.path.join(carpeta, f"{charla.id}.json")
        comprobar(os.path.isfile(ruta), "al contestar, la charla queda en el disco")

        asistente.olvidar_todas()          # lo que pasa al reiniciar el servicio
        de_vuelta = asistente.obtener(charla.id)
        comprobar(de_vuelta is not None, "y se reencuentra aunque no este en memoria")
        igual([t["texto"] for t in de_vuelta.turnos],
              ["como se parte un bloque?", "asi se parte"], "con sus turnos")
        igual(de_vuelta.session_id, "ses-1", "y con la sesion para poder reanudarla")
        igual(de_vuelta.pid, "p9", "y el proyecto")
        lista = asistente.listar()
        igual([r["id"] for r in lista], [charla.id], "el historial la lista")
        igual(lista[0]["titulo"], "como se parte un bloque?",
              "con la primera pregunta como titulo")

        # se puede seguir hablando en ella
        doble = Doble(["segunda respuesta"])
        de_vuelta.preguntar("y despues?", "FOTO", raiz="C:/estudio", ejecutar=doble)
        esperar(de_vuelta)
        de_vuelta._hilo.join(5)            # hasta que haya guardado
        igual(doble.llamadas[0]["extra"][:2], ["--resume", "ses-1"],
              "y continuarla reanuda la sesion de antes")

        # una que se quedo pensando al reiniciar no se queda ocupada para siempre
        import json as _json
        with open(ruta, encoding="utf-8") as fh:
            datos = _json.load(fh)
        datos["turnos"][-1]["estado"] = "pensando"
        with open(ruta, "w", encoding="utf-8") as fh:
            _json.dump(datos, fh)
        asistente.olvidar_todas()
        recuperada = asistente.obtener(charla.id)
        comprobar(not recuperada.ocupada(),
                  "un turno a medias de antes de reiniciar no deja la charla ocupada")
        igual(recuperada.turnos[-1]["estado"], "error", "sale como error, y se dice")

        comprobar(asistente.obtener("../../secretos/claves") is None,
                  "un id con ruta no sale de la carpeta del historial")
        comprobar(asistente.borrar(charla.id), "borrar dice que habia algo")
        comprobar(not os.path.exists(ruta), "y quita el fichero")
        comprobar(asistente.obtener(charla.id) is None, "ya no se reencuentra")

        tope = asistente.MAX_HISTORIAL
        asistente.MAX_HISTORIAL = 3
        try:
            for n in range(5):
                otra = asistente.nueva()
                otra.preguntar(f"pregunta {n}", "FOTO", raiz="C:/estudio",
                               ejecutar=Doble([f"r{n}"]))
                esperar(otra)
                otra._hilo.join(5)
                time.sleep(0.02)
            comprobar(len(os.listdir(carpeta)) <= 3,
                      "por encima del tope se borran las mas viejas")
        finally:
            asistente.MAX_HISTORIAL = tope
        del vacia
    finally:
        asistente.olvidar_todas()
        asistente.CARPETA_HISTORIAL = antes
        shutil.rmtree(carpeta, ignore_errors=True)


def prueba_dictado():
    seccion("6c] el dictado: el audio a OpenAI con su formato, y el respaldo")
    import dictado
    import requests

    class Respuesta:
        def __init__(self, codigo, datos):
            self.status_code, self._datos, self.text = codigo, datos, str(datos)

        def json(self):
            return self._datos

    llamadas = []
    guion = []

    def post(url, headers=None, files=None, data=None, timeout=None):
        llamadas.append({"url": url, "headers": headers, "files": files, "data": data})
        return guion.pop(0)

    original_post, original_claves = requests.post, dictado._claves
    simular = os.environ.pop("ESTUDIO_SIMULAR", None)
    requests.post = post
    dictado._claves = lambda: ["sk-uno", "sk-dos"]
    try:
        guion[:] = [Respuesta(200, {"text": " ¿Por qué la voz sale obsoleta? "})]
        r = dictado.transcribir(b"audio", "dictado", "audio/webm;codecs=opus", "es-419")
        igual(r["texto"], "¿Por qué la voz sale obsoleta?", "devuelve el texto limpio")
        igual(llamadas[0]["files"]["file"][0], "dictado.webm",
              "el nombre lleva la extension: OpenAI decide el formato por ella")
        igual(llamadas[0]["data"]["language"], "es", "y el idioma en dos letras")
        igual(llamadas[0]["data"]["model"], dictado.MODELO, "con el modelo barato")

        llamadas.clear()
        guion[:] = [Respuesta(404, {"error": {"message": "The model does not exist"}}),
                    Respuesta(200, {"text": "hola"})]
        r = dictado.transcribir(b"audio", "d.m4a", "audio/mp4")
        igual([c["data"]["model"] for c in llamadas], [dictado.MODELO, "whisper-1"],
              "si la cuenta no tiene ese modelo, se cae a whisper-1")
        igual(r["modelo"], "whisper-1", "y dice con cual salio")

        llamadas.clear()
        guion[:] = [Respuesta(401, {"error": {"message": "bad key"}}),
                    Respuesta(200, {"text": "con la segunda"})]
        r = dictado.transcribir(b"audio")
        igual([c["headers"]["Authorization"] for c in llamadas],
              ["Bearer sk-uno", "Bearer sk-dos"], "una clave mala pasa a la siguiente")
        igual(r["texto"], "con la segunda", "y contesta con ella")

        guion[:] = [Respuesta(200, {"text": "  "})]
        try:
            dictado.transcribir(b"audio")
            comprobar(False, "un audio sin voz tenia que fallar")
        except dictado.ErrorDictado as fallo:
            comprobar("no se ha entendido" in str(fallo), "sin voz lo dice en castellano")
        try:
            dictado.transcribir(b"x" * (dictado.MAX_BYTES + 1))
            comprobar(False, "un audio enorme tenia que fallar")
        except dictado.ErrorDictado:
            comprobar(True, "un audio por encima del tope se rechaza antes de mandarlo")
        dictado._claves = lambda: []
        try:
            dictado.transcribir(b"audio")
            comprobar(False, "sin clave tenia que fallar")
        except dictado.ErrorDictado as fallo:
            comprobar("Configuración" in str(fallo), "sin clave dice donde ponerla")
    finally:
        requests.post = original_post
        dictado._claves = original_claves
        if simular is not None:
            os.environ["ESTUDIO_SIMULAR"] = simular


def prueba_onboarding_visto():
    seccion("7] la marca de la guia de inicio, en los ajustes")
    carpeta = tempfile.mkdtemp(prefix="asist_aj_")
    os.environ["ESTUDIO_AJUSTES"] = os.path.join(carpeta, "ajustes.json")
    try:
        import importlib
        import ajustes
        importlib.reload(ajustes)
        comprobar(ajustes.leer()["onboarding_visto"] is False,
                  "de fabrica la guia no se ha visto")
        igual(ajustes.guardar({"onboarding_visto": True})["onboarding_visto"], True,
              "se marca como vista")
        comprobar(ajustes.leer()["onboarding_visto"] is True, "y se queda guardada")
        try:
            ajustes.guardar({"onboarding_visto": "si"})
            comprobar(False, "una marca que no es booleana tenia que fallar")
        except ValueError:
            comprobar(True, "una marca que no es booleana da ValueError")
        comprobar(ajustes.leer()["calidad_imagen"] == "low",
                  "y la calidad de imagen sigue con su defecto")
    finally:
        os.environ.pop("ESTUDIO_AJUSTES", None)
        shutil.rmtree(carpeta, ignore_errors=True)


def main():
    prueba_prompt()
    prueba_orden()
    prueba_mensajes()
    prueba_charla()
    prueba_ocupada_y_cancelar()
    prueba_registro()
    prueba_historial()
    prueba_dictado()
    prueba_onboarding_visto()
    print()
    if FALLOS:
        print(f"PRUEBA ASISTENTE CON FALLOS: {len(FALLOS)}")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print("PRUEBA ASISTENTE OK: todas las comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

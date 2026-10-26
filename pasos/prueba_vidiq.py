"""Prueba de vidIQ desde el Claude del Studio (rama `vidiq-1`, 25-10-2026).

Sin red, sin CLI y sin gastar créditos: el CLI se dobla (`cli_claude.ejecutar`
y `guionista.EJECUTAR`) y lo que se comprueba es lo que se le MANDA (el
fichero MCP, la lista blanca, los vetos) y lo que se hace con lo que vuelve.

    python pasos/prueba_vidiq.py
"""
import json
import os
import shutil
import stat
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="vidiq_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
os.environ["ESTUDIO_GUIONISTA_AISLADO"] = os.path.join(CARPETA, "aislado_chat")
os.environ.pop("ESTUDIO_SIMULAR", None)
os.environ.pop("ESTUDIO_VIDIQ_SIMULADO", None)

import claves as CLAVES  # noqa: E402
import cli_claude  # noqa: E402
import guionista as G  # noqa: E402
import vidiq as V  # noqa: E402

_ok = 0
_fallos = []
CLAVE = "vq_clave_de_prueba_123456"


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLA {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto} (esperado {esperado!r}, salió {obtenido!r})")


def seccion(titulo):
    print(f"\n[{titulo}")


def lanza(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as fallo:                              # noqa: BLE001
        return fallo
    return None


def poner_clave(valor):
    CLAVES.guardar({"vidiq": {"clave": valor}})


class Doble:
    """El `cli_claude.ejecutar` de mentira: apunta lo que recibe y mira el
    fichero MCP MIENTRAS existe (después tiene que estar borrado)."""

    def __init__(self, respuesta="{}", fallo=None):
        self.respuesta, self.fallo, self.llamadas = respuesta, fallo, []

    def __call__(self, instruccion, **kw):
        extra = list(kw.get("extra") or [])
        ruta = extra[extra.index("--mcp-config") + 1] if "--mcp-config" in extra else ""
        contenido = None
        if ruta and os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as fh:
                contenido = json.load(fh)
            modo = stat.S_IMODE(os.stat(ruta).st_mode)
        else:
            modo = None
        self.llamadas.append({"instruccion": instruccion, "kw": kw, "ruta": ruta,
                              "contenido": contenido, "modo": modo})
        if self.fallo:
            raise self.fallo
        return self.respuesta, {"_coste_anotado": True}


def prueba_lista_y_fichero():
    seccion("1] lo que se autoriza y lo que se veta")
    permitidas = V.permitidas_cli(V.CONSULTAR + ("vidiq_video_upload", "Bash"))
    ok(all(p.startswith("mcp__vidiq__") for p in permitidas), "todas con el prefijo del servidor")
    ok("mcp__vidiq__vidiq_video_upload" not in permitidas and not any("Bash" in p for p in permitidas),
       "lo que no está en la lista blanca no se autoriza aunque se pida")
    ok(not set(V.permitidas_cli(V.CONSULTAR)) & set(V.VETADAS), "ninguna autorizada está vetada")
    for peligrosa in ("vidiq_video_upload", "vidiq_update_video", "vidiq_instagram_publish_reel",
                      "vidiq_generate_thumbnail", "vidiq_generate_video", "vidiq_update_competitors"):
        ok(V.PREFIJO + peligrosa in V.VETADAS, f"«{peligrosa}» va vetada por su nombre")
    for usos in (V.PARA_PROBAR, V.PARA_TITULO, V.PARA_IDEAS):
        ok(set(usos) <= set(V.CONSULTAR), "cada uso pide solo de la lista blanca")
    ok("vidiq_score_thumbnail" not in V.PARA_TITULO + V.PARA_IDEAS, "la portada no entra en esta fase")

    seccion("2] el fichero MCP")
    ruta = V.fichero_mcp(CLAVE)
    with open(ruta, encoding="utf-8") as fh:
        datos = json.load(fh)
    servidor = datos["mcpServers"]["vidiq"]
    igual((servidor["type"], servidor["url"]), ("http", "https://mcp.vidiq.com/mcp"), "el servidor de vidIQ por HTTP")
    igual(servidor["headers"]["Authorization"], f"Bearer {CLAVE}", "con la clave en la cabecera")
    igual(list(datos["mcpServers"]), ["vidiq"], "y ningún otro servidor")
    if os.name != "nt":
        igual(stat.S_IMODE(os.stat(ruta).st_mode), 0o600, "legible solo por el servicio")
    V.borrar_fichero(ruta)
    ok(not os.path.exists(ruta), "y se borra")
    V.borrar_fichero(ruta)
    ok(True, "borrar dos veces no falla")
    viejo = V.fichero_mcp(CLAVE)
    os.utime(viejo, (0, 0))
    nuevo = V.fichero_mcp(CLAVE)
    ok(not os.path.exists(viejo) and os.path.exists(nuevo),
       "el que dejó una llamada cortada de golpe se barre al crear el siguiente")
    V.borrar_fichero(nuevo)
    if os.name != "nt":
        igual(stat.S_IMODE(os.stat(os.path.dirname(nuevo)).st_mode), 0o700, "en una carpeta propia (0700)")

    seccion("3] la clave no sale nunca en un mensaje")
    texto = V.tachar(f"401 para {CLAVE}: Authorization: Bearer {CLAVE}", CLAVE)
    ok(CLAVE not in texto and "•••" in texto, f"tachada: {texto}")
    ok("Bearer •••" in V.tachar("Authorization: Bearer otra-cosa-cualquiera", ""), "y el «Bearer …» siempre")


def prueba_almacen():
    seccion("4] el almacén de claves")
    igual(CLAVES.vidiq(), "", "sin poner")
    ok(not V.puesta(), "vidiq.puesta() dice que no")
    resumen = CLAVES.guardar({"vidiq": {"clave": f"  {CLAVE}  "}})
    igual(resumen["vidiq"]["puesta"], True, "se guarda")
    ok(CLAVE not in json.dumps(resumen), "el resumen no lleva la clave")
    ok(resumen["vidiq"]["cola"] and resumen["vidiq"]["cola"] != CLAVE, "solo su cola")
    igual(CLAVES.vidiq(), CLAVE, "sin los espacios")
    CLAVES.guardar({"youtube": {"clave": "AIza-otra"}})
    igual(CLAVES.vidiq(), CLAVE, "guardar otra clave no la borra")
    CLAVES.guardar({"vidiq": {"clave": CLAVES.CONSERVAR}})
    igual(CLAVES.vidiq(), CLAVE, "«conservar» la deja como estaba")
    env = os.path.join(os.environ["ESTUDIO_SECRETOS"], ".env")
    texto_env = open(env, encoding="utf-8").read() if os.path.exists(env) else ""
    ok(CLAVE not in texto_env, "no va al .env")
    poner_clave("")
    igual(CLAVES.vidiq(), "", "«Quitar» la borra")


def prueba_probar():
    seccion("5] probar la clave")
    raiz = os.path.join(CARPETA, "probar")
    igual(V.probar(raiz)["estado"], "sin_clave", "sin clave no llama a nadie")
    poner_clave(CLAVE)
    viejo = cli_claude.ejecutar
    doble = Doble('Aquí tienes: {"saldo": "1,234", "plan": "Boost"}')
    cli_claude.ejecutar = doble
    try:
        r = V.probar(raiz)
        igual((r["estado"], r["saldo"]), ("ok", 1234), "dice los créditos que quedan")
        ok("Boost" in r["mensaje"], "y el plan")
        k = doble.llamadas[-1]["kw"]
        igual(k["herramientas_permitidas"], ("mcp__vidiq__vidiq_balance",), "solo con «vidiq_balance»")
        igual((k["modelo"], k["esfuerzo"]), ("haiku", "low"), "con haiku: es una palabra")
        extra = k["extra"]
        igual(extra[extra.index("--max-turns") + 1], str(V.VUELTAS["probar"]), "con tope de vueltas")
        ok("--strict-mcp-config" not in (k["extra"] or []), "(el estricto ya lo pone cli_claude)")
        igual(doble.llamadas[-1]["contenido"]["mcpServers"]["vidiq"]["headers"]["Authorization"],
              f"Bearer {CLAVE}", "el fichero llevaba la clave mientras se llamaba")
        ok(not os.path.exists(doble.llamadas[-1]["ruta"]), "y se borró después")
        igual(V.estado(raiz)["saldo"], 1234, "el saldo queda apuntado para la pantalla")
        ok(os.path.exists(os.path.join(V.carpeta(raiz), "registro.jsonl")), "y la consulta en el registro")
        doble.respuesta = '{"error": "la herramienta no existe"}'
        r = V.probar(raiz)
        igual(r["estado"], "error", "un error de vidIQ se dice")
        cli_claude.ejecutar = Doble(fallo=RuntimeError(f"HTTP 401 Bearer {CLAVE} no vale"))
        r = V.probar(raiz)
        ok(r["estado"] == "error" and CLAVE not in r["mensaje"], f"un fallo con la clave dentro sale tachado: {r['mensaje']}")
    finally:
        cli_claude.ejecutar = viejo
    estado = V.estado(raiz)
    ok(CLAVE not in json.dumps(estado), "el estado nunca lleva la clave")


def prueba_titulo():
    seccion("6] «Mejorar con vidIQ»")
    raiz = os.path.join(CARPETA, "titulo")
    datos = {"nombre": "Cumple gamer", "palabra": "consolas para fiestas", "titulo": "Cumple con consolas",
             "guion": "Una fiesta con consolas en casa."}
    poner_clave("")
    e = lanza(V.lanzar_titulo, raiz, "v1", datos, en_hilo=False)
    ok(isinstance(e, V.ErrorVidiq) and e.codigo == 409, "sin clave: 409")
    poner_clave(CLAVE)
    e = lanza(V.lanzar_titulo, raiz, "v1", dict(datos, palabra="  "), en_hilo=False)
    ok(isinstance(e, V.ErrorVidiq) and e.codigo == 409 and "palabra clave" in str(e),
       "sin palabra clave no se gastan créditos a ciegas: 409")
    e = lanza(V.lanzar_titulo, raiz, "../x", datos, en_hilo=False)
    ok(isinstance(e, V.ErrorVidiq) and e.codigo == 404, "un id raro: 404")
    respuesta = json.dumps({
        "palabra": {"frase": "consolas para fiestas", "volumen": "2,400", "competencia": 30, "puntuacion": 61,
                    "texto": "buena"},
        "relacionadas": [{"frase": "alquiler de consolas", "volumen": 900}, {"frase": ""}, "nada"],
        "titulo_actual": {"texto": "Cumple con consolas", "nota": 38, "consejos": ["uno", "", "dos"]},
        "alternativas": [{"titulo": "🎮 Consolas para fiestas", "nota": 70, "porque": "x"},
                         {"titulo": "🎮 Consolas para fiestas", "nota": 70},
                         {"titulo": "B"}, {"titulo": "C"}, {"titulo": "D"}],
        "saldo": 980})
    viejo = cli_claude.ejecutar
    doble = Doble(respuesta)
    cli_claude.ejecutar = doble
    try:
        v = V.lanzar_titulo(raiz, "v1", datos, en_hilo=False)
        r = v["resultado"]
        igual(r["palabra"]["volumen"], 2400, "las cifras con coma de miles se leen")
        igual([x["frase"] for x in r["relacionadas"]], ["alquiler de consolas"], "lo vacío o raro se tira")
        igual(r["relacionadas"][0]["competencia"], None, "lo que vidIQ no dio queda en None, no en 0")
        igual(r["titulo_actual"]["consejos"], ["uno", "dos"], "consejos sin vacíos")
        igual([a["titulo"] for a in r["alternativas"]], ["🎮 Consolas para fiestas", "B", "C"],
              "tres alternativas, sin repetidas")
        igual((v["error"], v["palabra"], v["trabajando"]), ("", "consolas para fiestas", None),
              "queda guardado con la palabra con la que se consultó")
        igual(V.estado(raiz)["saldo"], 980, "y el saldo")
        k = doble.llamadas[-1]["kw"]
        igual(set(k["herramientas_permitidas"]), set(V.permitidas_cli(V.PARA_TITULO)),
              "solo las cuatro herramientas del título")
        ok(all(x in k["herramientas_vetadas"] for x in V.VETADAS + ("Bash", "Read", "WebFetch", "Agent")),
           "con todo lo demás vetado")
        ok("--no-session-persistence" in k["extra"], "sin dejar sesión guardada")
        igual(k["extra"][k["extra"].index("--max-turns") + 1], str(V.VUELTAS["titulo"]),
              "con tope de vueltas: no puede seguir consultando (y gastando) sin fin")
        ok("ListMcpResourcesTool" in k["herramientas_vetadas"] and "ReadMcpResourceTool" in k["herramientas_vetadas"],
           "ni leer recursos MCP")
        igual(k["cwd"], V.carpeta_aislada(), "en una carpeta vacía (sin CLAUDE.md de arriba)")
        ok(k["sistema"] and "\n" not in k["sistema"], "el sistema cabe en una línea")
        ins = doble.llamadas[-1]["instruccion"]
        ok("«consolas para fiestas»" in ins and "«Cumple con consolas»" in ins, "la instrucción lleva palabra y título")
        ok("ninguna más" in ins and "emojis" in ins, "fija las consultas y pide emojis")
        ok(not os.path.exists(doble.llamadas[-1]["ruta"]), "el fichero MCP se borra")
        # sin título actual, no se pide su nota
        V.lanzar_titulo(raiz, "v2", dict(datos, titulo=""), en_hilo=False)
        ok("sáltate este paso" in doble.llamadas[-1]["instruccion"], "sin título no se puntúa ninguno")
        # un fallo no borra lo bueno de antes
        cli_claude.ejecutar = Doble(fallo=RuntimeError(f"se cayó con {CLAVE}"))
        v = V.lanzar_titulo(raiz, "v1", datos, en_hilo=False)
        ok(v["error"] and CLAVE not in v["error"], f"el fallo se dice, tachado: {v['error']}")
        igual(v["resultado"]["palabra"]["frase"], "consolas para fiestas", "y lo de antes sigue ahí")
        cli_claude.ejecutar = Doble("{}")
        v = V.lanzar_titulo(raiz, "v3", datos, en_hilo=False)
        ok("nada que se pueda usar" in v["error"], "una respuesta vacía es un fallo, no un «listo» en blanco")
        # dos a la vez sobre el mismo vídeo, no
        with V._LOCK:
            V._TRABAJANDO["v1"] = {"desde": "ya"}
        try:
            e = lanza(V.lanzar_titulo, raiz, "v1", datos, en_hilo=False)
            ok(isinstance(e, V.ErrorVidiq) and e.codigo == 409, "el mismo vídeo dos veces a la vez: 409")
            ok(V.ver_video(raiz, "v1")["trabajando"], "y se ve que está trabajando")
        finally:
            V._TRABAJANDO.pop("v1", None)
    finally:
        cli_claude.ejecutar = viejo
    # si no se puede arrancar el hilo, el vídeo no se queda en 409 para siempre
    import threading as _th
    viejo_hilo = V.threading.Thread

    class SinHilo:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("sin hilos")
    V.threading.Thread = SinHilo
    try:
        ok(lanza(V.lanzar_titulo, raiz, "v5", datos) is not None, "un hilo que no arranca da error")
        ok("v5" not in V._TRABAJANDO, "y suelta el vídeo")
    finally:
        V.threading.Thread = viejo_hilo
    ok(V.threading.Thread is _th.Thread, "(el hilo de verdad vuelve)")
    seccion("7] simulado")
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        v = V.lanzar_titulo(raiz, "v9", datos, en_hilo=False)
        igual(len(v["resultado"]["alternativas"]), 3, "el simulado da tres títulos")
        igual(V.probar(raiz)["estado"], "ok", "y «Probar» contesta sin llamar a nadie")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)


def prueba_parrilla():
    seccion("8] la Parrilla: «Ideas con vidIQ»")
    permitidas, vetadas = G.herramientas(False, os.path.join(CARPETA, "aislada"), False)
    ok(not any(p.startswith("mcp__vidiq__") for p in permitidas), "sin pedirlo, nada de vidIQ")
    permitidas, vetadas = G.herramientas(False, os.path.join(CARPETA, "aislada"), False, True)
    igual(set(permitidas), set(V.permitidas_cli(V.PARA_IDEAS)), "con vidIQ, solo sus herramientas de consultar")
    ok(all(x in vetadas for x in V.VETADAS) and "Bash" in vetadas and "WebFetch" in vetadas,
       "y lo que publica o gasta mucho, vetado (y lo de siempre)")
    ok(G.AVISO_VIDIQ in G.anexos_del_turno(False, "", [], "", True), "Claude sabe que tiene vidIQ y su límite")
    ok("como mucho 3" in G.AVISO_VIDIQ and "⚠ dato de vidIQ" in G.AVISO_VIDIQ, "con el tope y el aviso ⚠")
    ok(G.AVISO_VIDIQ not in G.anexos_del_turno(False, "", []), "sin pedirlo, no se le dice")

    raiz = os.path.join(CARPETA, "parrilla")
    os.makedirs(raiz)
    llamadas = []

    def doble(mensaje, extra, cwd, permitidas, vetadas, modelo, avance=None):
        ruta = extra[extra.index("--mcp-config") + 1] if "--mcp-config" in extra else ""
        llamadas.append({"mensaje": mensaje, "extra": list(extra), "permitidas": permitidas,
                         "ruta": ruta, "existia": bool(ruta) and os.path.exists(ruta)})
        if "falla con la clave" in mensaje:
            raise RuntimeError(f"401 Authorization: Bearer {CLAVE}")
        return "Ideas (vidIQ): …", {"session_id": "s-vq", "usage": {}}

    G.EJECUTAR = doble
    try:
        poner_clave("")
        chat = G.nueva(raiz, "c1", "sonnet")
        e = lanza(chat.escribir, "ideas", vidiq=True, en_hilo=False)
        ok(isinstance(e, G.ErrorGuionista) and e.codigo == 409, "sin clave, «Ideas con vidIQ» da 409")
        igual(llamadas, [], "y no llama a nadie")
        poner_clave(CLAVE)
        v = chat.escribir("dame ideas", vidiq=True, en_hilo=False)
        primera = llamadas[-1]
        ok(primera["existia"] and primera["extra"][:1] == ["--mcp-config"], "el turno carga vidIQ con su fichero")
        ok("--max-turns" in primera["extra"], "con tope de vueltas")
        ok(not os.path.exists(primera["ruta"]), "que se borra al acabar el turno")
        ok(G.AVISO_VIDIQ in primera["mensaje"], "con el aviso de vidIQ")
        ok(any(t.get("vidiq") for t in v["turnos"] if t["quien"] == "tu"), "el turno queda marcado «con vidIQ»")
        chat.escribir("y ahora sin vidIQ", en_hilo=False)
        segunda = llamadas[-1]
        igual(segunda["extra"], ["--resume", "s-vq"], "el siguiente, sin pedirlo, no lo carga")
        ok(not any(p.startswith("mcp__vidiq__") for p in segunda["permitidas"]), "ni lo autoriza")
        chat.escribir("otra vez con", vidiq=True, en_hilo=False)
        tercera = llamadas[-1]
        ok(tercera["extra"][:2] == ["--resume", "s-vq"] and "--mcp-config" in tercera["extra"],
           "al reanudar también lo carga")
        ok(not os.path.exists(tercera["ruta"]), "y también lo borra")
        otro = G.nueva(raiz, "c1", "sonnet")
        v = otro.escribir("esto falla con la clave", vidiq=True, en_hilo=False)
        error = [t for t in v["turnos"] if t["quien"] == "claude"][-1]["texto"]
        ok(error.startswith("no ha podido contestar") and CLAVE not in error,
           f"un fallo del turno con vidIQ no enseña la clave: {error[:80]}")
        ok(not os.path.exists(llamadas[-1]["ruta"]), "y su fichero también se borra")
        texto, _s = G.ejecutar_simulado("MI MENSAJE\nhola", ["--mcp-config", "x"], raiz,
                                        V.permitidas_cli(V.PARA_IDEAS), (), "opus")
        ok("vidIQ: sí" in texto, "el simulado dice que lleva vidIQ")
    finally:
        G.EJECUTAR = None
        poner_clave("")


def main():
    print("PRUEBA DE VIDIQ")
    try:
        prueba_lista_y_fichero()
        prueba_almacen()
        prueba_probar()
        prueba_titulo()
        prueba_parrilla()
    finally:
        shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"VIDIQ OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

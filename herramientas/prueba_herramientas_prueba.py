#!/usr/bin/env python3
"""Prueba de las herramientas de prueba: `revisar.py` y `prueba_completa.py`.

Sin Studio de verdad, sin red y sin gastar: un servidor HTTP de mentira hace de
API (lo justo que usa la prueba completa), dos pruebas hijas de mentira hacen
de `prueba_real.py` y `prueba_relato.py`, y Claude (el juez) se dobla.

    python herramientas/prueba_herramientas_prueba.py
"""
import builtins
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))

import prueba_completa as PC  # noqa: E402
import prueba_real as PR      # noqa: E402
import revisar as RV          # noqa: E402

FALLOS = []
CUENTA = [0]


def ok(condicion, que):
    CUENTA[0] += 1
    if condicion:
        print(f"  ok   {que}")
    else:
        FALLOS.append(que)
        print(f"  FALLO {que}")


# ------------------------------------------------------------ revisar.py

def prueba_revisar():
    print("\n[revisar: la lista, la barra y el informe]")
    raiz = os.path.dirname(AQUI)
    suites = RV.suites_de(os.path.join(raiz, "pruebas.sh"))
    ok(len(suites) > 20 and suites[0] == "prueba_api.py", f"lee las {len(suites)} suites de pruebas.sh")
    ok("prueba_recorrido.py" in suites, "y el recorrido está entre ellas")
    ok(RV.barra(0) .startswith("[░") and RV.barra(1).endswith("100 %"), "la barra va de 0 a 100 %")
    ok(RV.barra(2).endswith("100 %") and RV.barra(-1).endswith("  0 %"), "y no se sale por los lados")
    ok(RV.minutos(30) == "menos de 1 min" and RV.minutos(3720) == "1 h 02 min", "los minutos se leen bien")

    m = RV.Marcador(["a.py", "b.py"], {"a.py": 10, "b.py": 30})
    ok(abs(m.fraccion()) < 0.05, "al empezar la barra está casi vacía")
    m.termina("a.py", "OK")
    ok(0.2 <= m.fraccion() <= 0.35, "con la primera hecha va por su peso (10 de 40 s)")
    cuadro = m.linea()
    ok("▶ b.py" in cuadro and "1 de 2" in cuadro, "dice cuál va ahora y cuántas van")
    ok(all(f"│ {e}" in cuadro for e in ("Avance", "Tiempo", "Hecho", "Ahora", "Pendiente")),
       "el cuadro trae avance, tiempo, hecho, ahora y pendiente")
    ok("1 bien ✓" in cuadro and "termina ≈" in cuadro, "cuenta lo bien hecho y da la hora de fin")
    m3 = RV.Marcador(["a.py", "b.py", "c.py"], {})
    m3.termina("a.py", "FALLA")
    ok("1 con fallo ✗ (a.py)" in m3.linea() and "Pendiente  1: c.py" in m3.linea(),
       "nombra lo que falló y lo pendiente sin contar la que va ahora")
    m.termina("b.py", "FALLA")
    ok(m.fraccion() == 1 and not m.actual, "al acabar, 100 % y nada en marcha")

    texto = RV.informe_final(m, {"b.py": ["        Running as root without --no-sandbox is not supported"]},
                             ["herramientas/x.py     OK: nada", "herramientas/y.py   RARO: 3"], 1)
    ok("CON FALLOS" in texto and "1 bien, 1 con fallos" in texto, "el informe cuenta bien y mal")
    ok("asvs revisar" in texto, "y para el fallo de root dice qué hacer")
    ok("RARO: 3" in texto and "OK: nada" not in texto, "las herramientas: solo lo que no es de siempre")
    m2 = RV.Marcador(["a.py"], {})
    m2.termina("a.py", "OK")
    texto = RV.informe_final(m2, {}, ["herramientas/atributos_py.py     ATRIBUTOS QUE NO EXISTEN: 2"], 0)
    ok("TODO EN VERDE" in texto and "asvs probar completo" in texto, "todo bien: lo dice y sugiere la completa")
    ok("ATRIBUTOS" not in texto, "lo de siempre de las herramientas no se repite")


# ------------------------------------------------------------ la API de mentira

class Mundo:
    """Lo que la API de mentira recuerda entre peticiones."""

    def __init__(self):
        self.peticiones = []
        self.coste = {"vid_basica": 0.8, "vid_relato": 2.1}
        self.escribiendo = 0
        self.investigando = 0
        self.enviado = False
        self.refrescos = 0
        self.portada = ""
        self.cliente = ""
        self.redes = []
        self.textos = {}
        self.montado = {"vid_basica": True, "vid_relato": True}
        self.perfil = "studio_estadoplay"
        self.salud = 200


def servidor(mundo):
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _responder(self, codigo, datos):
            cuerpo = json.dumps(datos).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def _cuerpo(self):
            largo = int(self.headers.get("Content-Length") or 0)
            try:
                return json.loads(self.rfile.read(largo) or b"{}")
            except ValueError:
                return {}

        def _ficha(self, pid):
            envios = []
            if mundo.enviado:
                estado = "publicado" if mundo.refrescos >= 2 else "publicando"
                envios = [{"id": f"e{r}", "red": r, "estado": estado,
                           "url": f"https://{r}.example/v1" if estado == "publicado" else "",
                           "error": ""} for r in mundo.redes]
            return {"pid": pid, "montado": mundo.montado.get(pid, False),
                    "escribiendo": mundo.escribiendo > 0, "error_textos": "",
                    "textos": mundo.textos,
                    "portada": {"imagen": mundo.portada},
                    "seo": {"palabra": "baño pequeño", "real": {"busquedas": ["baño pequeño ideas"]}
                            if mundo.investigando == 0 else {},
                            "trabajando": {"investigar": {}} if mundo.investigando > 0 else {},
                            "errores": {}},
                    "envios": envios, "ajustes": {"perfil": mundo.perfil}}

        def do_GET(self):
            mundo.peticiones.append(("GET", self.path))
            ruta = self.path
            if ruta == "/api/salud":
                return self._responder(mundo.salud, {"ok": mundo.salud == 200})
            if ruta == "/api/publicar/estado":
                return self._responder(200, {"clave": {"puesta": True}})
            if ruta == "/api/publicar/proyectos":
                return self._responder(200, {"proyectos": [
                    {"id": "_sin", "nombre": "Vídeos sin proyecto", "ajustes": {"perfil": "studio_sin"}},
                    {"id": "c1", "nombre": "EstadoPlay", "ajustes": {"perfil": "studio_estadoplay"}},
                    {"id": "c2", "nombre": "Suyu", "ajustes": {"perfil": "studio_suyu"}}]})
            m = re.match(r"^/api/proyectos/([^/]+)/coste$", ruta)
            if m:
                return self._responder(200, {"total_usd": mundo.coste.get(m.group(1), 0)})
            m = re.match(r"^/api/publicar/videos/([^/]+)/portada/proponer/(\w+)$", ruta)
            if m:
                return self._responder(200, {"estado": "listo", "propuestas": [
                    {"diseno": {"plantilla": "titular"}, "por_que": "x"}]})
            m = re.match(r"^/api/publicar/videos/([^/]+)$", ruta)
            if m:
                if mundo.escribiendo > 0:
                    mundo.escribiendo -= 1
                    if mundo.escribiendo == 0:
                        mundo.textos = {r: {"titulo": "Baño pequeño, el más bonito 🛁✨",
                                            "descripcion": "Mismos metros, otro baño 🚿"} for r in mundo.redes}
                if mundo.investigando > 0:
                    mundo.investigando -= 1
                return self._responder(200, self._ficha(m.group(1)))
            return self._responder(404, {"detail": f"no hay {ruta}"})

        def do_POST(self):
            cuerpo = self._cuerpo()
            mundo.peticiones.append(("POST", self.path, cuerpo))
            ruta = self.path
            if ruta == "/api/claves/probar":
                return self._responder(200, {"pruebas": [
                    {"proveedor": p, "estado": "ok"} for p in ("openai", "cartesia", "claude")]})
            if ruta == "/api/publicar/probar":
                return self._responder(200, {"ok": True, "mensaje": "Upload-Post acepta la clave"})
            m = re.match(r"^/api/publicar/proyectos/(\w+)/cuentas$", ruta)
            if m:
                cuentas = ({"tiktok": {"usuario": "estadoplay"}, "youtube": {"usuario": "EstadoPlay"},
                            "instagram": None, "facebook": {"usuario": "x", "reconectar": True}}
                           if m.group(1) in ("c1", "_sin") else {"tiktok": None})
                return self._responder(200, {"existe": True, "ajustes": {"cuentas": cuentas}})
            m = re.match(r"^/api/publicar/videos/([^/]+)/(.+)$", ruta)
            if m:
                que = m.group(2)
                if que == "portada/proponer":
                    return self._responder(202, {"id": "r1", "estado": "pensando"})
                if que == "portada/usar":
                    mundo.portada = "sello123"
                    return self._responder(200, self._ficha(m.group(1)))
                if que == "textos":
                    mundo.escribiendo = 2
                    return self._responder(202, {"escribiendo": True})
                if que == "seo/investigar":
                    mundo.investigando = 1
                    return self._responder(202, {"trabajando": True})
                if que == "enviar":
                    ok(cuerpo.get("confirmado") is True and cuerpo.get("modo") == "ahora",
                       "publica con modo «ahora» y confirmado")
                    mundo.enviado = True
                    return self._responder(202, {"envios": []})
            if ruta == "/api/publicar/refrescar":
                mundo.refrescos += 1
                return self._responder(200, {})
            return self._responder(404, {"detail": f"no hay {ruta}"})

        def do_PUT(self):
            cuerpo = self._cuerpo()
            mundo.peticiones.append(("PUT", self.path, cuerpo))
            m = re.match(r"^/api/clientes/videos/([^/]+)$", self.path)
            if m:
                mundo.cliente = cuerpo.get("cliente")
                return self._responder(200, {"video": m.group(1), "cliente": mundo.cliente})
            m = re.match(r"^/api/publicar/videos/([^/]+)$", self.path)
            if m:
                mundo.redes = cuerpo.get("redes") or []
                return self._responder(200, self._ficha(m.group(1)))
            return self._responder(404, {"detail": "no"})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


HIJO = '''#!/usr/bin/env python3
import datetime, json, os, sys
carpeta = os.path.join(os.environ["ESTUDIO_PROYECTOS"], "_sistema", "pruebas_reales")
os.makedirs(carpeta, exist_ok=True)
fecha = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "args_" + NOMBRE + ".txt"), "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\\n")
print("  ✓ algo de " + NOMBRE, flush=True)
datos = DATOS
with open(os.path.join(carpeta, PREFIJO + fecha + ".json"), "w") as fh:
    json.dump(datos, fh)
sys.exit(0)
'''


def _hijos(carpeta, basica, relato):
    os.makedirs(carpeta, exist_ok=True)
    for nombre, prefijo, datos in (("prueba_real.py", "", basica), ("prueba_relato.py", "relato_", relato)):
        codigo = (HIJO.replace("NOMBRE", repr(nombre)).replace("PREFIJO", repr(prefijo))
                  .replace("DATOS", repr(datos)))
        with open(os.path.join(carpeta, nombre), "w", encoding="utf-8") as fh:
            fh.write(codigo)


def _correr(argv, entradas=None):
    """main() de la prueba completa en este proceso. -> (código, salida)."""
    viejo_argv, viejo_input = sys.argv, builtins.input
    cola = list(entradas or [])
    sys.argv = ["prueba_completa.py"] + argv
    builtins.input = lambda texto="": (print(texto + (cola[0] if cola else "")) or (cola.pop(0) if cola else ""))
    salida = io.StringIO()
    try:
        with redirect_stdout(salida):
            codigo = PC.main()
    finally:
        sys.argv, builtins.input = viejo_argv, viejo_input
    return codigo, salida.getvalue()


def prueba_completa():
    print("\n[prueba completa: preparar, las partes y el informe]")
    temporal = tempfile.mkdtemp(prefix="prueba_completa_")
    proyectos = os.path.join(temporal, "proyectos")
    os.makedirs(proyectos)
    os.environ["ESTUDIO_PROYECTOS"] = proyectos
    mundo = Mundo()
    srv = servidor(mundo)
    api = f"http://127.0.0.1:{srv.server_address[1]}"
    hijos = os.path.join(temporal, "hijos")
    _hijos(hijos,
           {"veredicto": "APROBADA", "fallos": 0, "avisos": 1, "proyecto": "vid_basica", "lineas": []},
           {"veredicto": "APROBADA", "fallos": 0, "avisos": 0, "proyectos": {"a": "vid_relato"},
            "gastado_usd": 2.1, "lineas": []})
    _hijos(hijos,
           {"veredicto": "APROBADA", "fallos": 0, "avisos": 1, "proyecto": "vid_basica", "lineas": []},
           {"veredicto": "APROBADA", "fallos": 0, "avisos": 0, "proyectos": {"c": "vid_relato"},
            "gastado_usd": 2.1, "lineas": []})
    juicios = []
    viejo_juez = PR._juez                                           # noqa: SLF001
    PR._juez = lambda instruccion, cwd: (juicios.append(instruccion) or                 # noqa: SLF001
                                         {"atractivo": "si", "emojis": "si", "ortografia": "si",
                                          "formato": "si", "por_que": "bien"})
    try:
        # preparar: cancelar no lanza nada
        codigo, salida = _correr(["--api", api, "--preparar"], ["1", "1", "", "no"])
        ok(codigo == 1 and "No confirmado" in salida, "preparar sin escribir SI no lanza nada")
        ok(not os.path.exists(PC._ruta_config(proyectos)), "y no deja configuración")     # noqa: SLF001
        ok("EstadoPlay" in salida and "Suyu" not in salida.split("¿En qué cuenta")[1].split("0)")[0],
           "solo ofrece proyectos con alguna cuenta conectada")
        ok("Vídeos sin proyecto" not in salida, "«Vídeos sin proyecto» no se ofrece (no se puede mover ahí)")
        ok("facebook" not in salida.split("Redes de")[1].split("¿En cuáles")[0],
           "una cuenta que pide reconectar no se ofrece")
        # preparar: elegir EstadoPlay, solo TikTok, confirmar
        codigo, salida = _correr(["--api", api, "--preparar", "--tope", "5"], ["2", "1", "1", "SI"])
        config = PR.json.load(open(PC._ruta_config(proyectos), encoding="utf-8"))          # noqa: SLF001
        ok(codigo == 0 and config["publicar"]["cid"] == "c1" and config["publicar"]["redes"] == ["tiktok"],
           "preparar guarda la cuenta y las redes elegidas")
        ok(config["tope"] == 5, "y el tope")
        ok(config["escenario"] == "c", "y el tema del vídeo de foto (la sala de eventos)")
        ok("PUBLICAR DE VERDAD" in salida, "y avisa de que se publica de verdad")
        # una respuesta que no es una opción
        codigo, _s = _correr(["--api", api, "--preparar"], ["1", "9"])
        ok(codigo == 1, "un número que no está en la lista no lanza nada")
        os.makedirs(os.path.dirname(PC._ruta_config(proyectos)), exist_ok=True)          # noqa: SLF001
        PC._escribir_json(PC._ruta_config(proyectos), config)                            # noqa: SLF001

        # LA PRUEBA ENTERA
        codigo, salida = _correr(["--api", api, "--hijos", hijos, "--pausa", "0.01", "--cada", "0"])
        print("\n".join("      " + l for l in salida.splitlines()[-14:]))
        ok(codigo == 0 and "PRUEBA COMPLETA APROBADA" in salida, "la prueba entera sale APROBADA")
        ok("%" in salida and "▶ parte 6: Publicar de verdad" in salida, "enseña el cuadro hasta la última parte")
        ok("2,90 $ de 5,00 $ (quedan 2,10 $)" in salida, "y el gasto de los vídeos de prueba frente al tope")
        ok("✓ El servidor y las claves · ✓ Un vídeo normal" in salida, "lo hecho, parte por parte con ✓")
        ok("Pendiente  La portada" in salida, "y lo pendiente por su nombre")
        args_relato = open(os.path.join(hijos, "args_prueba_relato.py.txt")).read()
        ok("--tope 4.20" in args_relato and "--solo c" in args_relato,
           "la prueba de foto recibe lo que queda del tope (5 - 0,80) y el tema elegido")
        ok("--seguir" not in args_relato, "y no se retoma si no estaba empezada")
        ok(mundo.cliente == "c1", "el vídeo pasa al proyecto de la cuenta elegida")
        ok(mundo.redes == ["tiktok"], "se publica solo en las redes elegidas")
        usados = [p for p in mundo.peticiones if p[0] == "POST" and "/portada/usar" in p[1]]
        ok(usados and usados[0][2].get("diseno") == {"plantilla": "titular"}, "usa la primera portada propuesta")
        ok(any("/api/publicar/videos/vid_relato/" in p[1] for p in mundo.peticiones),
           "lo de publicar se hace con el vídeo de foto (vertical)")
        ok("tiktok: publicado → https://tiktok.example/v1" in salida, "espera a que salga y da el enlace")
        ok("LO PUBLICADO" in salida, "y al final recuerda qué se publicó para poder borrarlo")
        ok(juicios and "community manager" in juicios[0], "Claude juzga los textos")
        informes = [n for n in os.listdir(os.path.join(proyectos, "_sistema", "pruebas_reales"))
                    if re.fullmatch(r"completa_\d{4}-\d{2}-\d{2}_\d{4}\.json", n)]
        ok(len(informes) == 1, "deja el informe completa_<fecha>.json")
        ok(not os.path.exists(PC._ruta_estado(proyectos)), "y borra el estado a medias")           # noqa: SLF001

        # EL TOPE: si no queda para la de foto, no la lanza
        mundo2 = Mundo()
        mundo2.coste["vid_basica"] = 4.0
        srv2 = servidor(mundo2)
        _hijos(hijos, {"veredicto": "APROBADA", "fallos": 0, "avisos": 0, "proyecto": "vid_basica",
                       "lineas": []}, {"fallos": 0, "proyectos": {}})
        os.remove(os.path.join(hijos, "args_prueba_relato.py.txt"))
        codigo, salida = _correr(["--api", f"http://127.0.0.1:{srv2.server_address[1]}", "--hijos", hijos,
                                  "--pausa", "0.01", "--sin-publicar"])
        ok("PARADA POR EL TOPE antes de la prueba de foto" in salida, "sin tope para la de foto, para y lo dice")
        ok(not os.path.exists(os.path.join(hijos, "args_prueba_relato.py.txt")), "y no la lanza")
        ok("sin publicar" in salida and not mundo2.enviado, "--sin-publicar no sube nada")
        ok(any("/api/publicar/videos/vid_basica/textos" in p[1] for p in mundo2.peticiones),
           "sin la de foto, lo de publicar sigue con el vídeo normal")
        ok(codigo == 1, "y la prueba sale CON FALLOS (el tope cuenta como fallo)")
        srv2.shutdown()

        # RETOMAR: una parte empezada (y sin informe todavía) se sigue con --seguir
        est = {"inicio": 0, "tope": 5, "publicar": None, "hechas": ["claves", "basica"],
               "empezadas": {"relato": __import__("time").time() + 60}, "lineas": [], "videos": {"basica": "vid_basica"},
               "resultados": {}}
        PC._escribir_json(PC._ruta_estado(proyectos), est)                                  # noqa: SLF001
        _hijos(hijos, {"fallos": 0, "proyecto": "vid_basica"},
               {"fallos": 0, "proyectos": {"a": "vid_relato"}, "lineas": []})
        mundo3 = Mundo()
        srv3 = servidor(mundo3)
        codigo, salida = _correr(["--api", f"http://127.0.0.1:{srv3.server_address[1]}", "--hijos", hijos,
                                  "--pausa", "0.01", "--seguir"])
        ok("RETOMANDO" in salida, "retoma una prueba cortada")
        ok("algo de 'prueba_real.py'" not in salida, "lo ya hecho (el vídeo normal) no se repite")
        ok("--seguir" in open(os.path.join(hijos, "args_prueba_relato.py.txt")).read().splitlines()[-1],
           "y la parte que estaba empezada se sigue con --seguir")
        srv3.shutdown()

        # EL STUDIO NO CONTESTA AL RETOMAR: pausa, y el estado NO se borra
        est = {"inicio": 0, "tope": 5, "publicar": None, "hechas": ["claves", "basica"],
               "empezadas": {"basica": 1.0}, "lineas": [], "videos": {"basica": "vid_basica"},
               "resultados": {}}
        PC._escribir_json(PC._ruta_estado(proyectos), est)                                  # noqa: SLF001
        mundo4 = Mundo()
        mundo4.salud = 503
        srv4 = servidor(mundo4)
        codigo, salida = _correr(["--api", f"http://127.0.0.1:{srv4.server_address[1]}", "--hijos", hijos,
                                  "--pausa", "0.01", "--seguir"])
        ok(codigo == 2 and "EN PAUSA" in salida, "si el Studio no contesta, la prueba queda en pausa")
        ok(os.path.exists(PC._ruta_estado(proyectos)), "y lo hecho se conserva para retomarla")      # noqa: SLF001
        srv4.shutdown()

        # UNA HIJA QUE YA TERMINÓ antes del corte: se usa su informe, no se relanza
        est = {"inicio": 0, "tope": 5, "publicar": None, "hechas": ["claves", "basica"],
               "empezadas": {"relato": 1.0}, "lineas": [], "videos": {"basica": "vid_basica"},
               "resultados": {}}
        PC._escribir_json(PC._ruta_estado(proyectos), est)                                  # noqa: SLF001
        carpeta_inf = os.path.join(proyectos, "_sistema", "pruebas_reales")
        PC._escribir_json(os.path.join(carpeta_inf, "relato_2099-01-01_0000.json"),           # noqa: SLF001
                          {"fallos": 0, "proyectos": {"a": "vid_relato"}, "lineas": []})
        os.remove(os.path.join(hijos, "args_prueba_relato.py.txt"))
        mundo5 = Mundo()
        srv5 = servidor(mundo5)
        codigo, salida = _correr(["--api", f"http://127.0.0.1:{srv5.server_address[1]}", "--hijos", hijos,
                                  "--pausa", "0.01", "--seguir"])
        ok("ya había terminado antes del corte" in salida, "una parte ya terminada usa su informe")
        ok(not os.path.exists(os.path.join(hijos, "args_prueba_relato.py.txt")),
           "y no vuelve a lanzar (ni a pagar) la prueba de foto")
        srv5.shutdown()

        # EL PERFIL CAMBIÓ desde que se confirmó: no se publica
        PC._escribir_json(PC._ruta_config(proyectos), config)                              # noqa: SLF001
        mundo6 = Mundo()
        mundo6.perfil = "otro_perfil"
        srv6 = servidor(mundo6)
        codigo, salida = _correr(["--api", f"http://127.0.0.1:{srv6.server_address[1]}", "--hijos", hijos,
                                  "--pausa", "0.01"])
        ok("ha cambiado desde que lo confirmaste" in salida and not mundo6.enviado,
           "si el perfil cambió desde la confirmación, no publica")
        srv6.shutdown()
    finally:
        PR._juez = viejo_juez                                         # noqa: SLF001
        srv.shutdown()
        os.environ.pop("ESTUDIO_PROYECTOS", None)
        shutil.rmtree(temporal, ignore_errors=True)


def main():
    prueba_revisar()
    prueba_completa()
    print()
    if FALLOS:
        print(f"HERRAMIENTAS DE PRUEBA CON FALLOS: {len(FALLOS)} de {CUENTA[0]} comprobaciones")
        for f in FALLOS:
            print(f"  - {f}")
        return 1
    print(f"HERRAMIENTAS DE PRUEBA OK: {CUENTA[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

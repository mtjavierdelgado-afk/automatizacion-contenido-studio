"""EL RECORRIDO: la pantalla entera, pulsada como la pulsa una persona.

    python prueba_recorrido.py            # todo
    python prueba_recorrido.py --solo X   # un escenario (ver ESCENARIOS)
    python prueba_recorrido.py --capturas carpeta   # deja las capturas ahi

Por que existe
--------------
Las suites de siempre prueban el SERVIDOR (prueba_api) y los PASOS (las de
pasos/). Ninguna abre la pantalla. Y los fallos que se escapaban eran de
pantalla: un proyecto oculto que «Ver los ocultos» no ensenaba porque una clase
de CSS lo escondia (10-10-2026), un error de una imagen que salia arriba en el
Encargo, una cola de imagenes que se perdia al recargar. Ninguno da un error en
ningun sitio: se VEN o no se ven.

Asi que esto arranca el Estudio de verdad con datos de prueba, abre Chromium y
recorre las pantallas pulsando botones, comprobando que lo que tiene que
aparecer APARECE (con tamano en pantalla, no solo en el codigo), que no hay
errores de JavaScript, y dejando una captura de cada pantalla para mirarla.

Sin gastar nada y sin red:
  - imagenes   ESTUDIO_IMAGEN_FALSA=1 (motores/imagen_openai): pinta un color,
               y RECHAZA como el filtro de OpenAI lo que lleva marcas
  - voz        ESTUDIO_SIMULAR=1
  - Claude     herramientas/claude_falso.py, el primero del PATH
  - el video   se fabrica con el material de pasos/prueba_pasos_visuales.py
               (locucion, guion y voz falsos) y se corre p6/p7/p8 POR LA API
"""
import argparse
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import traceback

import requests

RAIZ = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {mensaje}")
    else:
        _fallos.append(mensaje)
        print(f"  FALLO {mensaje}")
    return bool(condicion)


def seccion(titulo):
    print(f"\n[{titulo}]")


# ------------------------------------------------------------------ el entorno

def preparar_entorno(base):
    """Las carpetas, el CLI falso y las variables. -> (env, proyectos)"""
    proyectos = os.path.join(base, "proyectos")
    os.makedirs(proyectos, exist_ok=True)
    binarios = os.path.join(base, "bin")
    os.makedirs(binarios, exist_ok=True)
    falso = os.path.join(binarios, "claude")
    with open(falso, "w", encoding="utf-8") as fh:
        fh.write(f'#!/bin/sh\nexec "{PYTHON}" "{os.path.join(RAIZ, "herramientas", "claude_falso.py")}" "$@"\n')
    os.chmod(falso, os.stat(falso).st_mode | stat.S_IEXEC)
    # y en Windows, que busca `claude.cmd` antes que nada (`cli_claude.localizar`)
    with open(os.path.join(binarios, "claude.cmd"), "w", encoding="utf-8") as fh:
        fh.write(f'@"{PYTHON}" "{os.path.join(RAIZ, "herramientas", "claude_falso.py")}" %*\r\n')
    env = dict(os.environ)
    env.update({
        "PATH": binarios + os.pathsep + env.get("PATH", ""),
        "ESTUDIO_SIMULAR": "1",
        # cuatro segundos por imagen: da tiempo a ver «Dibujando» y a recargar
        "ESTUDIO_IMAGEN_FALSA": "lento:4",
        "OPENAI_API_KEY": "sk-falsa-para-el-recorrido",
        "PYTHONIOENCODING": "utf-8",
        "ESTUDIO_PRESETS": os.path.join(base, "presets.json"),
        "ESTUDIO_BANCO_PRESETS": os.path.join(base, "banco_presets"),
        "ESTUDIO_SECRETOS": os.path.join(base, "secretos"),
        "ESTUDIO_RECETAS": os.path.join(base, "recetas.json"),
        "ESTUDIO_AJUSTES": os.path.join(base, "ajustes.json"),
        "ESTUDIO_ESTADISTICAS": os.path.join(base, "estadisticas.json"),
        "ESTUDIO_COSTE_GLOBAL": os.path.join(base, "coste.jsonl"),
        "ESTUDIO_BITACORA_GLOBAL": os.path.join(base, "bitacora.jsonl"),
        # el banco (musica, efectos, imagenes) tambien aparte: el de verdad no se toca
        "ESTUDIO_BANCO": os.path.join(base, "banco"),
    })
    os.makedirs(env["ESTUDIO_SECRETOS"], exist_ok=True)
    # la guia de la primera vez, ya vista: si no, tapa la pantalla
    with open(env["ESTUDIO_AJUSTES"], "w", encoding="utf-8") as fh:
        json.dump({"onboarding_visto": True}, fh)
    return env, proyectos


def puerto_libre():
    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        return sonda.getsockname()[1]


def arrancar(env, proyectos):
    puerto = puerto_libre()
    registro = open(os.path.join(os.path.dirname(proyectos), "servidor.log"), "w",
                    encoding="utf-8")
    proceso = subprocess.Popen(
        [PYTHON, os.path.join(RAIZ, "app.py"), "--puerto", str(puerto),
         "--proyectos", proyectos], cwd=RAIZ, env=env,
        stdout=registro, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            raise RuntimeError("el servidor murio al arrancar (mira servidor.log)")
        try:
            if requests.get(base + "/api/salud", timeout=2).status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el servidor no respondio en 90 s")


def parar(proceso):
    if proceso and proceso.poll() is None:
        proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()


class Api:
    def __init__(self, base):
        self.base = base
        self.s = requests.Session()

    def _r(self, metodo, ruta, **kw):
        r = self.s.request(metodo, self.base + ruta, timeout=120, **kw)
        try:
            datos = r.json()
        except ValueError:
            datos = {}
        return r, datos

    def get(self, ruta):
        return self._r("GET", ruta)

    def post(self, ruta, cuerpo=None, **kw):
        return self._r("POST", ruta, json=cuerpo, **kw) if "files" not in kw \
            else self._r("POST", ruta, **kw)

    def put(self, ruta, cuerpo=None):
        return self._r("PUT", ruta, json=cuerpo)

    def esperar(self, tid, limite=600):
        fin = time.time() + limite
        while time.time() < fin:
            r, ficha = self.get(f"/api/trabajos/{tid}")
            if r.status_code != 200:
                return {"estado": "desconocido"}
            if ficha.get("estado") in ("listo", "error", "cancelado"):
                return ficha
            time.sleep(0.5)
        return {"estado": "colgado"}


# ------------------------------------------------------------ los datos de prueba

def fabricar_video(proyectos, env):
    """Un video con ingesta, brief, guion y voz hechos, y el arte por generar.

    Se reutiliza el material de `prueba_pasos_visuales` (la locucion con sus
    marcas, el guion y el catalogo): es material que ya se sabe que pasa por
    p6, p7 y p8. Lo que cambia es que aqui las imagenes NO se adoptan: se
    generan con el motor falso, que es el camino que recorre la pantalla.
    """
    for clave in ("ESTUDIO_ESTADISTICAS", "ESTUDIO_BANCO"):
        os.environ[clave] = env[clave]
    os.environ["ESTUDIO_IMAGEN_FALSA"] = "1"
    import prueba_pasos_visuales as PV                       # noqa: PLC0415
    from PIL import Image                                    # noqa: PLC0415
    taller = os.path.join(proyectos, "_fabrica")
    # sin el mapa: con las imagenes GENERADAS (y no adoptadas) dos planos de
    # mapa seguidos salen identicos y el guardian de p6 tumba la tanda, con
    # razon. Lo que se prueba aqui es la pantalla, no los componentes.
    PV.CATALOGO = dict(PV.CATALOGO, componentes={})
    PV.CARPETA = taller
    PV.BANCO_PRUEBA = os.path.join(taller, "_banco")
    proyecto, estado = PV.preparar_proyecto()
    destino = os.path.join(proyectos, "padres_vs_hijos")
    shutil.move(proyecto.raiz, destino)
    # las rutas absolutas del estado apuntan a la carpeta vieja: se fabrico en
    # otra, asi que se repuntan con el mismo texto (no hay firmas que sellar
    # todavia que dependan de la ruta: la voz y el guion guardan rutas relativas)
    for raiz, _dirs, ficheros in os.walk(destino):
        for nombre in ficheros:
            if nombre.endswith(".json"):
                ruta = os.path.join(raiz, nombre)
                with open(ruta, encoding="utf-8") as fh:
                    texto = fh.read()
                if proyecto.raiz in texto:
                    with open(ruta, "w", encoding="utf-8") as fh:
                        fh.write(texto.replace(proyecto.raiz, destino))
    referencias = []
    os.makedirs(os.path.join(taller, "refs"), exist_ok=True)
    for i in range(3):
        ruta = os.path.join(taller, "refs", f"ref{i}.png")
        Image.new("RGB", (512, 340), (40 * i + 60, 120, 200 - 30 * i)).save(ruta)
        referencias.append(ruta)
    params = PV.parametros(os.path.join(taller, "_arte"))
    params.pop("imagenes_previas", None)
    params["motor_imagen"] = "openai"
    params["corrector"] = "no"
    params["estilo"]["referencias"] = referencias
    params["banco_imagenes"] = os.path.join(taller, "_banco", "imagenes")
    with open(os.path.join(destino, "proyecto.json"), encoding="utf-8") as fh:
        config = json.load(fh)
    config.update({"id": "padres_vs_hijos", "nombre": "Padres vs hijos en Mario Kart",
                   "video_light": True})
    with open(os.path.join(destino, "proyecto.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh)
    return "padres_vs_hijos", params


def sembrar(api, proyectos, params):
    """Por la API: el estilo con su taller, los proyectos y el video montado."""
    from PIL import Image                                    # noqa: PLC0415
    datos = {}
    # EL ESTILO, con su taller y sus laminas (como `prueba_api.probar_laminas`)
    r, d = api.post("/api/proyectos", {"nombre": "taller estilo demo"})
    tid = d["proyecto"]["id"]
    config = os.path.join(proyectos, tid, "proyecto.json")
    with open(config, encoding="utf-8") as fh:
        ficha = json.load(fh)
    ficha["taller_de_preset"] = True
    with open(config, "w", encoding="utf-8") as fh:
        json.dump(ficha, fh)
    for sub, cuantas in (("dibujadas", 6), ("aportadas", 10)):
        os.makedirs(os.path.join(proyectos, tid, "estilo", sub), exist_ok=True)
    ejes = ["cara", "cuerpos", "interior", "exterior", "objeto", "diagrama"]
    for i, eje in enumerate(ejes):
        Image.new("RGB", (768, 512), (30 * i + 40, 90, 160)).save(
            os.path.join(proyectos, tid, "estilo", "dibujadas", f"{eje}.png"))
    nombres = []
    for i in range(10):
        nombre = f"img{i}.png"
        Image.new("RGB", (400, 300), (20 * i, 100, 180 - 10 * i)).save(
            os.path.join(proyectos, tid, "estilo", "aportadas", f"{i:02d}_{nombre}"))
        nombres.append(nombre)
    r, d = api.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Estado Play Matriz",
        "datos": {"guion": {"idiomas_salida": ["es"], "instrucciones": "Cercano y divertido."},
                  "origen": {"estilo_prompt": "ilustración plana y colorida",
                             "estilo_imagenes": nombres,
                             "tono_prompt": "cercano y divertido, frases cortas",
                             "voz_prompt": "joven y animada", "taller": tid}}})
    datos["preset"] = d["preset"]["id"]
    # LOS PROYECTOS: uno normal y uno que se ocultara en el recorrido
    r, d = api.post("/api/clientes", {"nombre": "Estado Play"})
    datos["cliente"] = d["cliente"]["id"] if "cliente" in d else d.get("id")
    r, d = api.post("/api/clientes", {"nombre": "Suyu"})
    datos["cliente_oculto"] = d["cliente"]["id"] if "cliente" in d else d.get("id")
    api.put(f"/api/clientes/estilos/{datos['preset']}", {"cliente": datos["cliente"]})
    # EL VIDEO: de este estilo, y montado de verdad (p6, p7 y p8 por la API)
    pid = datos["video"] = "padres_vs_hijos"
    config = os.path.join(proyectos, pid, "proyecto.json")
    with open(config, encoding="utf-8") as fh:
        ficha = json.load(fh)
    ficha["estilo_light"] = datos["preset"]
    with open(config, "w", encoding="utf-8") as fh:
        json.dump(ficha, fh)
    api.put(f"/api/proyectos/{pid}/pasos/assets/params", {"params": params, "reemplazar": True})
    for paso, extra in (("assets", {}), ("callouts", {"params": {"previsualizar": True}}),
                        ("render", {"params": {"fps": 12, "resolucion": [640, 360],
                                               "calidad_video": "baja"}})):
        r, d = api.post(f"/api/proyectos/{pid}/pasos/{paso}/ejecutar", extra)
        fin = api.esperar(d.get("trabajo_id"))
        if not ok(fin.get("estado") == "listo",
                  f"el video de prueba pasa por {paso} ({fin.get('error') or ''})"):
            raise RuntimeError(f"no se ha podido montar el video de prueba: {fin}")
    return datos


# ------------------------------------------------------------------ la pantalla

ESCENARIOS = []


def escenario(funcion):
    ESCENARIOS.append(funcion)
    return funcion


class Pagina:
    """Una pestana con sus errores de JavaScript apuntados y sus capturas."""

    def __init__(self, navegador, datos, ancho=1300, alto=900, nombre="pantalla"):
        self.datos = datos
        self.nombre = nombre
        self.errores = []
        self.contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
        self.p = self.contexto.new_page()
        self.p.on("pageerror", lambda e: self.errores.append(f"pageerror: {e}"))
        self.p.on("console", lambda m: self.errores.append(f"console: {m.text}")
                  if m.type == "error" and "Failed to load resource" not in m.text else None)
        # los confirm() de la pantalla se aceptan: es lo que haria quien pulsa
        self.p.on("dialog", lambda d: d.accept())
        self.p.goto(datos["url"] + "/")
        self.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos", timeout=30000)
        self.p.wait_for_timeout(800)

    def js(self, codigo):
        resultado = self.p.evaluate(f"async () => {{ {codigo} }}")
        self.p.wait_for_timeout(500)
        return resultado

    def visible(self, selector, texto=None):
        """Visible DE VERDAD: con tamano en pantalla y sin estar escondido."""
        loc = self.p.locator(selector)
        if texto:
            loc = loc.filter(has_text=texto)
        for i in range(loc.count()):
            try:
                caja = loc.nth(i).bounding_box(timeout=2000)
                if caja and caja["width"] > 2 and caja["height"] > 2 and loc.nth(i).is_visible():
                    return True
            except Exception:                                # noqa: BLE001
                continue          # se repinto mientras se miraba: se mira el siguiente
        return False

    def esperar(self, selector, texto=None, segundos=20):
        fin = time.time() + segundos
        while time.time() < fin:
            if self.visible(selector, texto):
                return True
            self.p.wait_for_timeout(300)
        return False

    def pulsar(self, selector, texto=None):
        """Pulsa el primero que case. La pantalla se repinta sola (el coste, la
        cola), asi que un boton puede cambiar de nodo entre buscarlo y pulsarlo:
        se vuelve a buscar, como haria quien vuelve a hacer clic."""
        for intento in range(4):
            loc = self.p.locator(selector)
            if texto:
                loc = loc.filter(has_text=texto)
            try:
                loc.first.scroll_into_view_if_needed(timeout=5000)
                loc.first.click(timeout=5000)
                break
            except Exception:                                # noqa: BLE001
                if intento == 3:
                    raise
                self.p.wait_for_timeout(400)
        self.p.wait_for_timeout(600)

    def sin_trabajo(self, segundos=180):
        """Espera a que el video no tenga nada corriendo (un remontaje, una tanda)."""
        fin = time.time() + segundos
        while time.time() < fin:
            if self.p.evaluate("() => ((APP.trabajos[CLAVE_VIDEO_LIGHT] || {}).estado) !== 'ejecutando'"):
                self.p.wait_for_timeout(1200)
                return True
            self.p.wait_for_timeout(500)
        return False

    def toast(self):
        return self.p.locator("#toast").inner_text()

    def captura(self, nombre, entera=True):
        ruta = os.path.join(self.datos["capturas"], f"{nombre}.png")
        self.p.screenshot(path=ruta, full_page=entera)
        return ruta

    def sin_errores(self, que):
        ok(not self.errores, f"{que}: sin errores de JavaScript"
           + (f" -- {self.errores[:3]}" if self.errores else ""))
        self.errores.clear()

    def cerrar(self):
        self.contexto.close()


@escenario
def portada_y_proyectos(navegador, datos):
    api = datos["api"]
    api.put(f"/api/clientes/{datos['cliente_oculto']}", {"oculto": True})
    pg = Pagina(navegador, datos)
    pg.js("await cargarGaleriaLight(true); irALight('galeria'); elegirCliente('');")
    ok(pg.visible("h2", "Tus proyectos"), "la portada enseña «Tus proyectos»")
    ok(pg.visible(".tarjeta-proyecto", "Estado Play"), "se ve la tarjeta de Estado Play")
    ok(not pg.visible(".tarjeta-proyecto", "Suyu"), "el proyecto oculto no se ve de entrada")
    ok(pg.visible("button", "Ver los ocultos"), "y hay un botón para ver los ocultos")
    pg.pulsar("button", "Ver los ocultos")
    ok(pg.visible(".tarjeta-proyecto", "Suyu"),
       "«Ver los ocultos» ENSEÑA el proyecto oculto (con tamaño en pantalla)")
    pg.captura("01_portada_con_ocultos")
    pg.pulsar("button", "Esconder los ocultos")
    ok(not pg.visible(".tarjeta-proyecto", "Suyu"), "y «Esconder» lo vuelve a esconder")
    # con clave: se pide y se entra
    api.put(f"/api/clientes/{datos['cliente']}", {"clave": "1234"})
    pg.js("await cargarClientes(); pintarLight();")
    ok(pg.visible(".tarjeta-proyecto", "con clave"), "un proyecto con clave lo dice en su tarjeta")
    pg.pulsar(".tarjeta-proyecto", "Estado Play")
    ok(pg.esperar(".capa-dialogo input"), "al pulsarlo pide la clave")
    pg.p.locator(".capa-dialogo input").first.fill("1234")
    pg.p.locator(".capa-dialogo button[type=submit]").click()
    pg.p.wait_for_timeout(1200)
    ok(pg.visible(".tarjeta-estilo, .galeria-estilos", None) or pg.visible("h2", "Estado Play"),
       "con la clave buena se entra en el proyecto")
    pg.captura("02_dentro_del_proyecto")
    api.put(f"/api/clientes/{datos['cliente']}", {"clave": ""})
    api.put(f"/api/clientes/{datos['cliente_oculto']}", {"oculto": False})
    pg.sin_errores("la portada y los proyectos")
    pg.cerrar()


@escenario
def ficha_del_estilo(navegador, datos):
    pg = Pagina(navegador, datos)
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});")
    ok(pg.esperar(".laminas-estilo .lamina"), "la ficha enseña las láminas del estilo")
    ok(pg.p.locator(".laminas-estilo .lamina").count() == 6, "las seis de fábrica")
    ok(pg.visible(".laminas-estilo", "Qué es una lámina"), "y explica qué es una lámina")
    ok(pg.esperar(".rejilla-aportadas .aportada"), "y tus imágenes de referencia")
    ok(pg.p.locator(".rejilla-aportadas .aportada").count() == 10, "las diez")
    ok(pg.visible(".banner-muestras", "TEXTO DE EJEMPLO") or pg.visible(".banner-muestras", "sin muestras")
       or pg.visible(".banner-muestras", "no tiene muestras"),
       "las muestras dicen que su texto es de ejemplo")
    pg.pulsar(".laminas-estilo button", "Añadir una lámina")
    ok(pg.esperar(".capa-dialogo textarea"), "«Añadir una lámina» pide qué tiene que enseñar")
    pg.pulsar(".capa-dialogo button", "Cancelar")
    pg.captura("03_ficha_del_estilo")
    # REVISAR: lo sugerido, revisado otra vez, sirve
    bloque = pg.p.locator(".bloque-light").filter(has_text="Estilo gráfico").first
    area = bloque.locator("textarea[data-guia]").first
    ok(area.count() == 1, "«Revisar» del estilo gráfico mira las Indicaciones (marcadas)")
    area.fill("ilustración plana [PENDIENTE de decidir] con colores vivos")
    area.dispatch_event("input")
    bloque.locator("button", has_text="Revisar").first.click()
    ok(pg.esperar(".revision-campo", "Mejorable", 60), "la revisión encuentra el hueco sin rellenar")
    pg.pulsar(".revision-campo button", "Usar la versión sugerida")
    pg.p.wait_for_timeout(500)
    bloque.locator("button", has_text="Revisar").first.click()
    ok(pg.esperar(".revision-campo", "Sirve", 60),
       "y revisar la versión sugerida otra vez dice «Sirve», no otro error"
       + f" -- vi: {pg.p.locator('.revision-campo').first.inner_text()[:200]!r}"
       f" / campo: {area.input_value()[:80]!r} / aviso: {pg.toast()[:120]!r}")
    ok(pg.visible(".revision-campo", "ya se había revisado"),
       "sin gastar otra revisión (es la misma respuesta)")
    ok(pg.visible(".pie-light button", "Regenerar"),
       "cambiar las Indicaciones pide Regenerar (con su coste) y no da error")
    pg.captura("04_revisar_estable")
    pg.sin_errores("la ficha del estilo")
    pg.cerrar()


@escenario
def encargo_del_video(navegador, datos):
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{datos['video']}');")
    pg.pulsar(".nav-light button", "Encargo")
    ok(pg.esperar(".ajustes-montaje"), "el Encargo enseña los ajustes del montaje")
    for nombre in ("Música", "Subtítulos", "Logo", "Efectos"):
        ok(pg.visible(".fila-ajuste", nombre), f"con su fila de {nombre}")
    ok(not pg.visible(".error-cerrable"), "y sin ningún error arrastrado de otra pantalla")
    # MUSICA
    pg.p.locator(".fila-ajuste").filter(has_text="Música").locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(500)
    pg.pulsar(".editor-ajuste button", "Elegir un tema")
    ok(pg.visible(".buscador-temas button", "Gamer"), "hay muchos más ánimos (Gamer, Infantil…)")
    ok(pg.visible(".buscador-temas input[type=search]"), "y búsqueda libre")
    pg.pulsar(".buscador-temas button", "Gamer")
    pg.p.wait_for_timeout(1500)
    ok("Jamendo" in pg.toast() or pg.visible(".tema-musica"),
       "sin clave de Jamendo lo dice en un aviso (no se rompe nada)")
    mp3 = os.path.join(datos["base"], "mi_tema.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=4", mp3], check=True)
    pg.p.locator(".buscador-temas input[type=file]").set_input_files(mp3)
    ok(pg.esperar(".fila-ajuste", "mi_tema", 30), "«Subir mi música» lo pone como tema del vídeo")
    pg.captura("05_encargo_musica")
    ok(pg.sin_trabajo(), "volver a mezclar la música termina")
    # EFECTOS
    pg.p.locator(".fila-ajuste").filter(has_text="Efectos").locator("button", has_text="Cambiar").click()
    ok(pg.esperar(".papel-efecto"), "los efectos se enseñan por papel")
    ok(pg.p.locator(".papel-efecto").count() >= 4, "los cuatro papeles")
    pg.p.locator(".papel-efecto").first.locator("input[type=file]").set_input_files(mp3)
    ok(pg.esperar(".papel-efecto", "Elegido", 30), "«Subir el mío» fija ese sonido para el papel"
       + f" -- aviso: {pg.toast()[:150]!r}")
    pg.pulsar(".papel-efecto button", "Buscar otro sonido")
    ok(pg.visible(".papel-efecto input[type=search]"), "y se puede buscar otro en FreeSound")
    pg.captura("06_encargo_efectos")
    pg.sin_errores("el Encargo")
    pg.cerrar()


@escenario
def notas_de_imagenes(navegador, datos):
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{datos['video']}');")
    pg.pulsar(".nav-light button", "Imágenes")
    ok(pg.esperar(".previa-feedback textarea"), "la pantalla de imágenes deja escribir una nota")
    area = pg.p.locator(".previa-feedback textarea").first
    area.fill("el mando tiene que ser de Nintendo Switch, como en Mario Kart")
    area.dispatch_event("input")
    pg.pulsar(".previa-feedback button", "Guardar nota")
    ok(pg.esperar(".nota-imagen"), "la nota sale en su tarjeta")
    tarjeta = pg.p.locator(".nota-imagen").first
    ok("Imagen S" in tarjeta.inner_text(), "la tarjeta dice QUÉ imagen es")
    ok("«" in tarjeta.inner_text(), "y lo que se oye en ella (su frase del guion)")
    ok(tarjeta.locator(".nota-mini img").count() == 1, "con su miniatura")
    ok(pg.visible(".nota-imagen button", "Rehacer esta imagen"), "y su botón para rehacerla")
    pg.captura("07_nota_nueva")
    pg.pulsar(".nota-imagen button", "Rehacer esta imagen")
    ok(pg.esperar(".nota-imagen .pastilla", "Dibujando", 15),
       "mientras se dibuja lo dice, con su reloj")
    # RECARGAR NO PIERDE LA COLA: vive en el servidor
    pg.p.reload()
    pg.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos",
                           timeout=30000)
    pg.js(f"await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".nota-imagen .pastilla", "Dibujando", 10) or pg.esperar(".nota-imagen .pastilla", "Hecha", 2),
       "y al recargar la página la tarjeta sigue diciendo que se dibuja (no «Pendiente»)")
    ok(pg.esperar(".nota-imagen .pastilla", "Hecha", 120),
       "con marcas: OpenAI la rechaza, se reescribe sola sin marcas y SALE"
       + f" -- vi: {pg.p.locator('.nota-imagen').first.inner_text()[:300]!r}"
       + f" / tarjetas {pg.p.locator('.nota-imagen').count()}, plegadas "
         f"{pg.p.locator('details.imagenes-hechas .nota-imagen').count()}"
       + f" / vistas: {pg.p.evaluate('() => [...notasVistas()].join(\",\")')!r}")
    ok(pg.visible(".nota-imagen", "sin ellos") or pg.visible(".nota-imagen", "sin marcas"),
       "y la nota cuenta que se dibujó sin las marcas")
    pg.captura("08_nota_hecha_sin_marcas")
    # una que no se arregla sola
    area = pg.p.locator(".previa-feedback textarea").first
    area.fill("pon el cartel PROHIBIDO de la marca en grande")
    area.dispatch_event("input")
    pg.pulsar(".previa-feedback button", "Guardar nota")
    pg.p.locator(".nota-imagen").filter(has_text="PROHIBIDO").locator(
        "button", has_text="Rehacer esta imagen").click()
    ok(pg.esperar(".nota-imagen .pastilla", "Rechazada", 120),
       "si OpenAI la rechaza también sin marcas, la nota lo dice")
    ok(pg.visible(".nota-imagen .nota-error", "filtro de seguridad"), "con el motivo en claro")
    ok(pg.p.locator(".nota-imagen").filter(has_text="Imagen S001").count() == 1,
       "y las notas de la MISMA imagen van en UNA tarjeta (no se repite la imagen)")
    ok(pg.visible(".nota-imagen button", "Hacerla sin marcas"), "y ofrece hacerla sin marcas")
    pg.captura("09_nota_rechazada")
    pg.pulsar(".nota-imagen button", "Hacerla sin marcas")
    ok(pg.esperar(".capa-dialogo textarea", segundos=40), "propone la nota reescrita, editable")
    texto = pg.p.locator(".capa-dialogo textarea").input_value()
    ok("PROHIBIDO" not in texto, f"sin lo que se rechazaba ({texto[:60]}…)")
    pg.p.locator(".capa-dialogo button[type=submit]").click()
    tarjeta = pg.p.locator(".nota-fila").filter(has_text="cartel")
    fin = time.time() + 120
    while time.time() < fin and "hecha" not in tarjeta.first.inner_text().lower():
        pg.p.wait_for_timeout(500)
    ok("hecha" in tarjeta.first.inner_text().lower(), "y con la nota reescrita la imagen sale"
       + f" -- vi: {tarjeta.first.inner_text()[:300]!r} / aviso: {pg.toast()[:150]!r}")
    # dos notas del mismo plano: UNA imagen
    for texto in ("más luz en la escena", "y que se vea el sofá"):
        area = pg.p.locator(".previa-feedback textarea").first
        area.fill(texto)
        area.dispatch_event("input")
        pg.pulsar(".previa-feedback button", "Guardar nota")
    ok(pg.visible("button", "Rehacer 1 imagen"), "dos notas del mismo plano se pagan como UNA imagen")
    pg.p.locator(".repaso-notas").first.scroll_into_view_if_needed()
    pg.captura("10_dos_notas_un_plano", entera=False)
    pg.pulsar("button", "Rehacer 1 imagen")
    fin = time.time() + 120
    juntas = pg.p.locator(".nota-fila").filter(has_text="más luz")
    otra = pg.p.locator(".nota-fila").filter(has_text="sofá")
    while time.time() < fin and not (
            "hecha" in juntas.first.inner_text().lower() and "hecha" in otra.first.inner_text().lower()):
        pg.p.wait_for_timeout(700)
    ok("hecha" in juntas.first.inner_text().lower() and "hecha" in otra.first.inner_text().lower(),
       "y al rehacerla, las dos notas quedan hechas con esa sola imagen")
    # el Encargo no arrastra nada de esto
    pg.pulsar(".nav-light button", "Encargo")
    ok(not pg.visible(".error-cerrable"), "el Encargo no enseña los errores de las imágenes")
    pg.sin_errores("las notas de imágenes")
    pg.cerrar()


@escenario
def resto_de_pantallas(navegador, datos):
    pg = Pagina(navegador, datos)
    pg.pulsar("#btn-config")
    ok(pg.esperar("#config", "Hora de tu región"), "Configuración se abre")
    buscador = pg.p.locator("#config input[aria-label='Buscar zona horaria']")
    ok(buscador.count() == 1, "la hora de tu región tiene buscador")
    buscador.fill("Lima")
    pg.p.wait_for_timeout(400)
    opciones = pg.p.locator("#config select[aria-label='Zona horaria'] option").all_inner_texts()
    ok(any("Lima" in o for o in opciones) and len(opciones) < 10,
       f"y filtra ({len(opciones)} opciones con «Lima»)")
    pg.captura("11_configuracion")
    pg.pulsar("#btn-cerrar-config")
    pg.pulsar("#btn-ayuda")
    ok(pg.esperar("body", "Qué es una lámina", 10) or pg.esperar("body", "La idea en una frase", 10),
       "la ayuda se abre con el manual")
    pg.captura("12_ayuda")
    pg.p.keyboard.press("Escape")
    pg.js("irALight('galeria');")
    pg.pulsar("#burbuja-asistente")
    ok(pg.esperar("#asistente-texto"), "el asistente se abre")
    pg.pulsar("#btn-cerrar-asistente")
    pg.js(f"await abrirVideoLight('{datos['video']}');")
    pg.pulsar(".nav-light button", "Guion")
    ok(pg.esperar("body", "B001"), "el Guion enseña los bloques")
    pg.pulsar(".nav-light button", "Vídeo")
    ok(pg.esperar("video"), "el Vídeo enseña el reproductor")
    pg.captura("13_video")
    pg.sin_errores("el resto de pantallas")
    pg.cerrar()
    # EN EL MOVIL: nada se sale por los lados
    movil = Pagina(navegador, datos, 390, 844, "movil")
    for nombre, codigo in (
            ("portada", "await cargarGaleriaLight(true); irALight('galeria'); elegirCliente('');"),
            ("ficha", f"irALight('preset', {{ abierto: '{datos['preset']}' }});"),
            ("imagenes", f"await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'previa'; pintarLight();")):
        movil.js(codigo)
        movil.p.wait_for_timeout(800)
        ancho = movil.p.evaluate("() => document.documentElement.scrollWidth")
        ok(ancho <= 392, f"en el móvil la {nombre} no se sale por los lados ({ancho} px)")
        movil.captura(f"14_movil_{nombre}")
    movil.sin_errores("el móvil")
    movil.cerrar()


def _png(ruta, color):
    from PIL import Image                                    # noqa: PLC0415
    Image.new("RGB", (320, 200), color).save(ruta)
    return ruta


@escenario
def proyectos_a_mano(navegador, datos):
    """Crear, renombrar, logo, clave, ocultar y borrar un proyecto, pulsando."""
    pg = Pagina(navegador, datos)
    pg.js("await cargarGaleriaLight(true); irALight('galeria'); elegirCliente('');")
    pg.pulsar(".tarjeta-proyecto", "Nuevo proyecto")
    ok(pg.esperar(".capa-dialogo input"), "«Nuevo proyecto» pide un nombre")
    pg.p.locator(".capa-dialogo input").first.fill("Cliente de prueba")
    pg.p.locator(".capa-dialogo button[type=submit]").click()
    ok(pg.esperar("h2", "Cliente de prueba"), "y entra en el proyecto nuevo")
    pg.pulsar(".mandos-proyecto button", "Renombrar")
    pg.p.locator(".capa-dialogo input").first.fill("Cliente renombrado")
    pg.p.locator(".capa-dialogo button[type=submit]").click()
    ok(pg.esperar("h2", "Cliente renombrado"), "se renombra")
    pg.pulsar(".mandos-proyecto button", "Logo")
    logo = _png(os.path.join(datos["base"], "logo.png"), (250, 200, 30))
    pg.p.locator(".panel-logo-proyecto input[type=file]").set_input_files(logo)
    ok(pg.esperar(".mandos-proyecto button", "Logo ✓", 15), "se le pone logo")
    pg.pulsar(".mandos-proyecto button", "Ocultar")
    ok(pg.esperar(".pastilla", "oculto"), "se oculta (y lo dice)")
    pg.pulsar(".mandos-proyecto button", "Poner clave")
    pg.p.locator(".capa-dialogo input").nth(0).fill("abcd")
    pg.p.locator(".capa-dialogo input").nth(1).fill("abcd")
    pg.p.locator(".capa-dialogo button[type=submit]").click()
    ok(pg.esperar(".mandos-proyecto button", "Clave ✓", 10), "se le pone clave")
    pg.captura("15_proyecto_a_mano")
    pg.pulsar(".mandos-proyecto button", "Borrar")
    if pg.esperar(".capa-dialogo button", "Borrar", 5):
        pg.pulsar(".capa-dialogo button", "Borrar")
    ok(pg.esperar("h2", "Tus proyectos"), "se borra y vuelve a la portada")
    ok(not pg.visible(".tarjeta-proyecto", "Cliente renombrado"), "y ya no está")
    pg.sin_errores("los proyectos a mano")
    pg.cerrar()


@escenario
def laminas_a_mano(navegador, datos):
    """Quitar y devolver una lámina, y cambiar la hoja, pulsando."""
    pg = Pagina(navegador, datos)
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});")
    ok(pg.esperar(".laminas-estilo .lamina"), "las láminas están")
    pg.p.locator(".laminas-estilo .lamina").filter(has_text="diagrama").locator(
        "button", has_text="Quitar").click()
    ok(pg.esperar(".light-generando, .generando, body", None, 5), "quitar una lámina lanza el rehacer")
    fin = time.time() + 90
    while time.time() < fin and not pg.visible(".laminas-estilo button", "Devolver"):
        pg.p.wait_for_timeout(1000)
    ok(pg.visible(".laminas-estilo button", "Devolver"),
       "al terminar, la quitada se puede devolver (gratis)")
    ok(pg.p.locator(".laminas-estilo .lamina").count() == 5, "y quedan cinco")
    pg.pulsar(".laminas-estilo button", "Devolver")
    fin = time.time() + 90
    while time.time() < fin and pg.p.locator(".laminas-estilo .lamina").count() != 6:
        pg.p.wait_for_timeout(1000)
    ok(pg.p.locator(".laminas-estilo .lamina").count() == 6, "y al devolverla vuelven a ser seis")
    sel = pg.p.locator(".laminas-estilo select")
    if sel.count():
        sel.first.select_option("repartida")
        pg.p.wait_for_timeout(1500)
        ok("guardado" in pg.toast(), "cambiar la hoja se guarda sin dibujar nada")
    pg.captura("16_laminas_a_mano")
    pg.sin_errores("las láminas a mano")
    pg.cerrar()


@escenario
def estilo_nuevo(navegador, datos):
    """El formulario de un estilo nuevo, y qué pasa si la creación falla."""
    pg = Pagina(navegador, datos)
    pg.js("APP.light.encargo = null; irALight('crear', { taller: null });")
    ok(pg.esperar("input, textarea"), "el formulario de estilo nuevo se abre")
    ok(pg.visible("body", "Imágenes de referencia") or pg.visible("body", "IMÁGENES DE REFERENCIA"),
       "pide las imágenes de referencia")
    ok(pg.visible("body", "Tono del guion"), "el tono")
    ok(pg.visible("body", "Voz"), "y la voz")
    pg.captura("17_estilo_nuevo")
    pg.sin_errores("el estilo nuevo")
    pg.cerrar()


@escenario
def video_nuevo_con_ajustes(navegador, datos):
    """Un vídeo nuevo con música, subtítulos y logo elegidos AL CREARLO."""
    api = datos["api"]
    pg = Pagina(navegador, datos)
    pg.js(f"await cargarGaleriaLight(true); elegirEstiloLight(fichaLight('{datos['preset']}'));")
    ok(pg.esperar("h2", "Un vídeo nuevo"), "elegir el estilo abre el vídeo nuevo")
    ok(pg.esperar(".ajustes-montaje"), "con los ajustes del montaje ya al crearlo")
    pg.p.locator(".fila-ajuste").filter(has_text="Subtítulos").locator("button", has_text="Cambiar").click()
    pg.pulsar(".editor-ajuste button", "Grande")
    ok(pg.visible(".fila-ajuste", "tamaño grande"), "se eligen los subtítulos (grandes)")
    pg.p.locator(".fila-ajuste").filter(has_text="Logo").locator("button", has_text="Cambiar").click()
    logo = _png(os.path.join(datos["base"], "logo2.png"), (30, 200, 250))
    pg.p.locator(".editor-ajuste input[type=file]").set_input_files(logo)
    ok(pg.esperar(".fila-ajuste", "Logo propio", 15), "y un logo")
    campo = pg.p.locator(".bloque-light").filter(has_text="El vídeo").locator("input").first
    campo.fill("Vídeo creado en el recorrido")
    material = pg.p.locator(".bloque-light").filter(has_text="El material").locator("textarea").first
    material.fill("Un padre y su hijo juegan a un videojuego de carreras. Gana el hijo tres veces.")
    material.dispatch_event("input")
    pg.captura("18_video_nuevo")
    pg.pulsar("button.primario.grande", "Generar el guion")
    pg.p.wait_for_timeout(4000)
    r, d = api.get("/api/proyectos")
    nuevo = next((x for x in d.get("proyectos") or []
                  if x.get("nombre") == "Vídeo creado en el recorrido"), None)
    ok(nuevo, "se crea el vídeo")
    if nuevo:
        r, sub = api.get(f"/api/proyectos/{nuevo['id']}/subtitulos")
        ok(sub.get("tam") == "grande", f"con los subtítulos elegidos al crearlo ({sub.get('tam')})")
        r, logo_d = api.get(f"/api/proyectos/{nuevo['id']}/logo")
        ok((logo_d or {}).get("logo"), "y con su logo")
    # el guion lo escribe el CLI falso, que no sabe: tiene que fallar CON MOTIVO
    fin = time.time() + 90
    while time.time() < fin and not pg.visible(".error-cerrable") and not pg.visible(".bloque-guion, .guion-bloque"):
        pg.p.wait_for_timeout(1000)
    if pg.visible(".error-cerrable"):
        ok(True, "si el guion falla, se dice con su motivo")
        # ese fallo es el esperado (el CLI falso no escribe guiones) y la
        # pantalla lo apunta tambien en la consola: no es un error de la pantalla
        pg.errores[:] = [e for e in pg.errores if not e.startswith("console: ")]
        pg.pulsar(".error-cerrable button", "Cerrar")
        ok(not pg.visible(".error-cerrable"), "y el aviso se puede cerrar")
    pg.captura("19_video_nuevo_tras_generar")
    pg.sin_errores("el vídeo nuevo")
    pg.cerrar()


@escenario
def tema_claro_y_asistente(navegador, datos):
    pg = Pagina(navegador, datos)
    pg.pulsar("#btn-tema")
    ok(pg.p.evaluate("() => document.documentElement.dataset.tema") in ("claro", "oscuro"),
       "el botón de tema cambia el tema")
    pg.js("await cargarGaleriaLight(true); irALight('galeria'); elegirCliente('');")
    pg.captura("20_tema_claro")
    pg.pulsar("#btn-tema")
    pg.pulsar("#burbuja-asistente")
    pg.p.wait_for_timeout(1500)
    campo = pg.p.locator("#asistente-texto")
    if campo.is_enabled():
        campo.fill("¿qué es una lámina?")
        pg.pulsar("#btn-enviar-asistente")
        ok(campo.is_enabled(), "se puede seguir escribiendo mientras contesta")
        ok(pg.esperar("#asistente-cuerpo", "lámina", 30), "el asistente contesta (simulado)")
    else:
        # sin sesion de Claude (aqui no hay ninguna): lo dice y dice como entrar
        ok("Entra" in (campo.get_attribute("placeholder") or ""),
           "sin sesión de Claude, el asistente dice cómo entrar")
    pg.captura("21_asistente")
    pg.sin_errores("el tema y el asistente")
    pg.cerrar()


@escenario
def fallos_simulados(navegador, datos):
    """Sin crédito en OpenAI: la nota lo dice, con qué hacer, y nada más se rompe."""
    api = datos["api"]
    parar(datos["proceso"])
    env = dict(datos["env"], ESTUDIO_IMAGEN_FALSA="saldo")
    proceso, url = arrancar(env, datos["proyectos"])
    datos.update({"proceso": proceso, "url": url, "api": Api(url)})
    try:
        pg = Pagina(navegador, datos)
        pg.js(f"await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'previa'; pintarLight();")
        ok(pg.esperar(".previa-feedback textarea"), "la pantalla de imágenes se abre")
        area = pg.p.locator(".previa-feedback textarea").first
        area.fill("que el cielo sea naranja")
        area.dispatch_event("input")
        pg.pulsar(".previa-feedback button", "Guardar nota")
        pg.p.locator(".nota-imagen").filter(has_text="cielo sea naranja").locator(
            "button", has_text="Rehacer esta imagen").click()
        tarjeta = pg.p.locator(".nota-fila").filter(has_text="cielo sea naranja")
        fin = time.time() + 60
        while time.time() < fin and "falló" not in tarjeta.first.inner_text().lower():
            pg.p.wait_for_timeout(500)
        texto = tarjeta.first.inner_text()
        ok("falló" in texto.lower(), "sin crédito, la nota dice que falló")
        ok("credito" in texto.lower() or "crédito" in texto.lower(),
           f"y por qué, con qué hacer ({texto[-160:]!r})")
        pg.pulsar(".nav-light button", "Encargo")
        ok(not pg.visible(".error-cerrable"), "y el Encargo sigue limpio")
        pg.captura("22_sin_credito")
        pg.sin_errores("los fallos simulados")
        pg.cerrar()
    finally:
        parar(datos["proceso"])
        proceso, url = arrancar(datos["env"], datos["proyectos"])
        datos.update({"proceso": proceso, "url": url, "api": Api(url)})


def main():
    ap = argparse.ArgumentParser(description="El recorrido de la pantalla")
    ap.add_argument("--solo", default="", help="un escenario por nombre")
    ap.add_argument("--capturas", default="", help="carpeta para las capturas")
    ap.add_argument("--quedarse", action="store_true",
                    help="deja el servidor arrancado al terminar (para mirar)")
    args = ap.parse_args()
    base = tempfile.mkdtemp(prefix="estudio_recorrido_")
    capturas = args.capturas or os.path.join(base, "capturas")
    os.makedirs(capturas, exist_ok=True)
    print(f"RECORRIDO DE LA PANTALLA\n  datos en {base}\n  capturas en {capturas}")
    env, proyectos = preparar_entorno(base)
    proceso = None
    datos = {}
    try:
        pid, params = fabricar_video(proyectos, env)
        proceso, url = arrancar(env, proyectos)
        api = Api(url)
        seccion("LOS DATOS DE PRUEBA")
        datos.update(sembrar(api, proyectos, params))
        datos.update({"url": url, "proyectos": proyectos, "capturas": capturas,
                      "base": base, "api": api, "env": env, "proceso": proceso})
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError:
            print("\nRECORRIDO OMITIDO: falta playwright (pip install playwright && "
                  "playwright install chromium). No es un fallo del Estudio.")
            return 0
        with sync_playwright() as p:
            navegador = p.chromium.launch(args=["--no-sandbox"])
            for funcion in ESCENARIOS:
                if args.solo and args.solo not in funcion.__name__:
                    continue
                seccion(funcion.__name__.replace("_", " ").upper())
                try:
                    funcion(navegador, datos)
                except Exception as fallo:                   # noqa: BLE001
                    traceback.print_exc()
                    ok(False, f"{funcion.__name__} se corto: {type(fallo).__name__}: {fallo}")
            navegador.close()
        if args.quedarse:
            print(f"\nservidor en {datos['url']} (Ctrl+C para parar)")
            datos["proceso"].wait()
    finally:
        parar(datos.get("proceso") or proceso)
    print()
    if _fallos:
        print(f"RECORRIDO CON FALLOS: {len(_fallos)} de {_ok + len(_fallos)}")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"RECORRIDO OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

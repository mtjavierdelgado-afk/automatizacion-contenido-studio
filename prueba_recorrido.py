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

import re

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

    def libre(self, pid, limite=300):
        """Espera a que el video no tenga NINGUN trabajo en el servidor (un
        remontaje de la musica lanzado por el servidor no lo sigue la pagina)."""
        fin = time.time() + limite
        while time.time() < fin:
            _r, d = self.get(f"/api/trabajos?proyecto={pid}&activos=1")
            lista = d if isinstance(d, list) else (d.get("trabajos") or [])
            if not lista:
                return True
            time.sleep(1)
        return False

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
    # LA VOZ CON LAS TILDES ROTAS, como la de los videos grabados antes del
    # 10-10-2026 (Cartesia leida como Latin-1): «zarpó» llego «zarpÃ³». Es lo
    # que hay en los videos de verdad, y la pantalla tiene que aguantarlo.
    meta = os.path.join(destino, "pasos", "voz", "v1", "audio_meta.json")
    with open(meta, encoding="utf-8") as fh:
        voz = json.load(fh)
    rotas = {"zarpo": "zarpÃ³", "manana": "maÃ±ana", "tripulacion": "tripulaciÃ³n"}
    for palabra in voz.get("palabras") or []:
        if isinstance(palabra, dict) and palabra.get("w") in rotas:
            palabra["w"] = rotas[palabra["w"]]
    with open(meta, "w", encoding="utf-8") as fh:
        json.dump(voz, fh, ensure_ascii=False)
    referencias = []
    # EN EL BANCO DE PRESETS y con el prefijo repetido de antes del 09-10-2026,
    # como las de los videos de verdad: `reparar_estilo_perdido` las «pierde»
    # renombrandolas y comprueba que «Reparar» las vuelve a encontrar
    carpeta_refs = os.path.join(taller, "banco", "presets", "pr_prueba")
    os.makedirs(carpeta_refs, exist_ok=True)
    for i, eje in enumerate(("cara", "interior", "objeto")):
        ruta = os.path.join(carpeta_refs, f"00_00_{eje}.png")
        Image.new("RGB", (512, 340), (40 * i + 60, 120, 200 - 30 * i)).save(ruta)
        referencias.append(ruta)
    params = PV.parametros(os.path.join(taller, "_arte"))
    params.pop("imagenes_previas", None)
    params["motor_imagen"] = "openai"
    params["corrector"] = "no"
    params["estilo"]["referencias"] = referencias
    params["banco_imagenes"] = os.path.join(taller, "_banco", "imagenes")
    # COMO UN VIDEO DE VERDAD: uno hecho desde la pantalla ya tiene su guia de
    # estilo y la direccion de sus planos. Sin ellas, «Regenerar Vídeo» las
    # pedia al modelo (falso) y el montaje se caia por algo que en un video
    # real no pasa (11-10-2026).
    params["estilo"]["guia"] = {
        "guia": "Ilustración plana, contornos negros gruesos, luz difusa sin sombras duras.",
        "paleta": ["#2b2a33", "#c9a66b", "#7a9e7e", "#e8e1cf", "#b5523b"],
        "trazo": "contorno negro grueso y uniforme", "relleno": "colores planos"}
    params["unidades"] = dict(params.get("unidades") or {})
    for plano in ("S001", "S002", "S004"):
        unidad = dict(params["unidades"].get(f"escena:{plano}") or {})
        unidad["direccion"] = "plano medio, el sujeto a la izquierda mirando al horizonte"
        params["unidades"][f"escena:{plano}"] = unidad
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
    # SU MUSICA, subida (como hace quien no tiene clave de Jamendo): sin tema,
    # el montaje desde la pantalla pide uno a Jamendo y aqui no hay clave
    tema = os.path.join(proyectos, "_fabrica", "tema.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=330:duration=20", tema], check=True)
    with open(tema, "rb") as fh:
        r, d = api.post("/api/sonido/subir?familia=musica",
                        files={"f": ("tema de prueba.mp3", fh.read(), "audio/mpeg")})
    if d.get("ficha"):
        api.put(f"/api/proyectos/{pid}/sonido", {"musica": d["ficha"]})
    ok(bool(d.get("ficha")), "el vídeo de prueba lleva su música (subida)")
    # Y SUS EFECTOS, uno subido por papel: un video hecho desde la pantalla ya
    # los tiene surtidos, y sin ellos montar pide FreeSound (sin clave aqui)
    golpe = os.path.join(proyectos, "_fabrica", "golpe.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=880:duration=0.6", golpe], check=True)
    for papel in ("transicion_suave", "transicion_acento", "tecla", "retorno"):
        with open(golpe, "rb") as fh:
            r, d = api.post("/api/sonido/subir?familia=efectos",
                            files={"f": (f"{papel}.mp3", fh.read(), "audio/mpeg")})
        if d.get("ficha"):
            api.put(f"/api/proyectos/{pid}/sonido/efecto", {"papel": papel, "efecto": d["ficha"]})
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


#: Se mete en cada pestaña: apunta el texto de cada botón que llega a verse y
#: de cada uno que se pulsa. Con eso y `herramientas/inventario_botones.py`
#: sale la cobertura: cuántos botones del código ha visto y pulsado el recorrido.
ESPIA_DE_BOTONES = """
(() => {
  window.__vistos = new Set(); window.__pulsados = new Set();
  const texto = b => (b.innerText || b.textContent || '').replace(/\\s+/g, ' ').trim();
  const mirar = () => document.querySelectorAll('button, a.boton').forEach(b => {
    if (b.offsetParent !== null || b.getClientRects().length) {
      const t = texto(b); if (t) window.__vistos.add(t);
    }
  });
  document.addEventListener('click', ev => {
    const b = ev.target.closest && ev.target.closest('button, a.boton');
    if (b) { const t = texto(b); if (t) window.__pulsados.add(t); }
  }, true);
  setInterval(mirar, 700);
})();
"""
BOTONES_VISTOS = set()
BOTONES_PULSADOS = set()


def informe_de_cobertura(carpeta):
    """Cuántos botones del código ha visto y pulsado el recorrido."""
    sys.path.insert(0, os.path.join(RAIZ, "herramientas"))
    import inventario_botones                                # noqa: PLC0415
    botones = [b for b in inventario_botones.inventario() if b["textos"]]

    def casa(textos, conjunto):
        return any(any(v.startswith(t) or t in v for v in conjunto) for t in textos)
    vistos = [b for b in botones if casa(b["textos"], BOTONES_VISTOS)]
    pulsados = [b for b in botones if casa(b["textos"], BOTONES_PULSADOS)]
    nunca = [b for b in botones if b not in vistos]
    print(f"\nCOBERTURA: {len(vistos)} de {len(botones)} botones con texto se han VISTO, "
          f"{len(pulsados)} se han PULSADO")
    with open(os.path.join(carpeta, "cobertura.json"), "w", encoding="utf-8") as fh:
        json.dump({"vistos": len(vistos), "pulsados": len(pulsados), "total": len(botones),
                   "nunca_vistos": nunca,
                   "sin_pulsar": [b for b in vistos if b not in pulsados]},
                  fh, ensure_ascii=False, indent=1)
    print(f"  la lista de los que faltan: {os.path.join(carpeta, 'cobertura.json')}")


class Pagina:
    """Una pestana con sus errores de JavaScript apuntados y sus capturas."""

    def __init__(self, navegador, datos, ancho=1300, alto=900, nombre="pantalla"):
        self.datos = datos
        self.nombre = nombre
        self.errores = []
        self.contexto = navegador.new_context(viewport={"width": ancho, "height": alto})
        # LO QUE SE VE Y LO QUE SE PULSA, para la cobertura (`--cobertura`)
        self.contexto.add_init_script(ESPIA_DE_BOTONES)
        self.p = self.contexto.new_page()
        self.p.on("pageerror", lambda e: self.errores.append(f"pageerror: {e}"))
        self.p.on("console", lambda m: self.errores.append(f"console: {m.text}")
                  if m.type == "error" and "Failed to load resource" not in m.text else None)
        # los confirm() de la pantalla se aceptan: es lo que haria quien pulsa
        self.aceptar = True
        self.dialogos = []
        self.p.on("dialog", self._dialogo)
        self.p.goto(datos["url"] + "/")
        self.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos", timeout=30000)
        self.p.wait_for_timeout(800)
        # TODOS LOS AVISOS, no solo el último: uno de un trabajo que acaba
        # puede tapar al que se busca
        self.p.evaluate("() => { window.__avisos = []; const _t = toast; "
                        "toast = function (t) { window.__avisos.push(String(t)); "
                        "return _t.apply(this, arguments); }; }")

    def avisos(self):
        return self.p.evaluate("() => window.__avisos || []")

    def sin_trabajo_del_estilo(self, segundos=180):
        """Espera a que el taller del estilo no tenga nada corriendo."""
        fin = time.time() + segundos
        while time.time() < fin:
            if self.p.evaluate("() => ((APP.trabajos[CLAVE_LIGHT] || {}).estado) !== 'ejecutando'"
                               " && APP.light.vista !== 'generando'"):
                self.p.wait_for_timeout(1200)
                return True
            self.p.wait_for_timeout(500)
        return False

    def _dialogo(self, dialogo):
        self.dialogos.append(dialogo.message)
        if self.aceptar:
            dialogo.accept()
        else:
            dialogo.dismiss()

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
        try:
            vistos, pulsados = self.p.evaluate(
                "() => [[...(window.__vistos || [])], [...(window.__pulsados || [])]]")
            BOTONES_VISTOS.update(vistos)
            BOTONES_PULSADOS.update(pulsados)
        except Exception:                                    # noqa: BLE001
            pass
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
    # DEJAR DE OCULTARLO desde la portada (11-10-2026: «lo mantiene como un
    # oculto visible»)
    pg.pulsar("button", "Ver los ocultos")
    ok(pg.visible(".ocultos-portada button", "Dejar de ocultar"),
       "con los ocultos a la vista, cada uno tiene «Dejar de ocultar»")
    pg.pulsar(".ocultos-portada button", "Dejar de ocultar")
    pg.p.wait_for_timeout(1000)
    _r, d = api.get("/api/clientes")
    ok(not any(c.get("oculto") for c in d.get("clientes") or [] if c.get("id") == datos["cliente_oculto"]),
       "y deja de estar oculto de verdad")
    ok(pg.visible(".tarjeta-proyecto", "Suyu") and "oculto" not in
       pg.p.locator(".tarjeta-proyecto", has_text="Suyu").first.inner_text().lower(),
       "su tarjeta sale en la portada sin la marca «oculto»")
    pg.js("APP.light.verOcultos = false; pintarLight();")
    ok(pg.visible(".tarjeta-proyecto", "Suyu"), "y sigue saliendo aunque no se pidan los ocultos")
    api.put(f"/api/clientes/{datos['cliente_oculto']}", {"oculto": True})
    pg.js("await cargarClientes(); pintarLight();")
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
    pg.pulsar(".revision-campo button", "Aplicar la versión sugerida")
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
    # el segundo de «Qué música»: «Elegir un tema…» o, si ya tiene uno, su nombre
    pg.p.locator(".editor-ajuste .herramientas button").filter(
        has_text=re.compile(r"^\s*(«|Elegir un tema)")).first.click()
    pg.p.wait_for_timeout(600)
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
    ok(pg.esperar(".papel-efecto", "«mi_tema»", 30), "«Subir el mío» fija ese sonido para el papel"
       + f" -- aviso: {pg.toast()[:150]!r}")
    pg.pulsar(".papel-efecto button", "Buscar otro sonido")
    ok(pg.visible(".papel-efecto input[type=search]"), "y se puede buscar otro en FreeSound")
    # EL VOLUMEN DE LOS EFECTOS (11-10-2026)
    ok(pg.visible(".editor-ajuste button", "Altos"), "los efectos tienen su volumen (Bajos/Normales/Altos)")
    pg.sin_trabajo()          # subir el efecto vuelve a mezclar: con eso en marcha, 409
    datos["api"].libre(datos["video"])
    pg.pulsar(".editor-ajuste button", "Altos")
    pg.p.wait_for_timeout(1500)
    _r, sonido = datos["api"].get(f"/api/proyectos/{datos['video']}/sonido")
    ok(sonido.get("efectos_volumen") == "altos", f"«Altos» se guarda ({sonido.get('efectos_volumen')})")
    pg.sin_trabajo()
    pg.pulsar(".editor-ajuste button", "Normales")
    pg.p.wait_for_timeout(1500)
    pg.sin_trabajo()
    # Y LOS QUE ELIGIÓ EL AUTOMÁTICO, PARA OÍRLOS Y DESCARTARLOS: el segundo
    # papel no tiene ninguno fijado a mano
    automatico = pg.p.locator(".papel-efecto").filter(has_text="Automático")
    if automatico.count() and automatico.first.locator(".efecto-surtido").count():
        ok(automatico.first.locator(".efecto-surtido audio").count() > 0,
           "cada efecto automático se puede escuchar")
        ok(automatico.first.locator("button", has_text="Descartar").count() > 0,
           "y descartar")
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
    ok(tarjeta.locator(".nota-mini:not(.nota-antes) img").count() == 1, "con su miniatura")
    ok(pg.visible(".nota-imagen button", "Rehacer esta imagen"), "y su botón para rehacerla")
    pg.captura("07_nota_nueva")
    # mientras se monta el vídeo (el remontaje de la música del Encargo) no se
    # rehace ninguna imagen: el servidor contesta que espere
    ok(datos["api"].libre(datos["video"]), "el vídeo termina de montarse antes de rehacer")
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
def lo_que_sale_a_veces(navegador, datos):
    """Los botones que solo salen en una situación concreta y que el resto del
    recorrido no veía (ver la cobertura): la papelera, duplicar un estilo,
    quitar y devolver una lámina, la guía de un campo, las notas de mejoras,
    la guía de inicio, el color del subtítulo y partir un bloque del guion."""
    api, pid = datos["api"], datos["video"]
    pg = Pagina(navegador, datos)
    # LA PAPELERA: un estilo borrado se puede devolver desde la pantalla
    r, d = api.post(f"/api/presets-light/{datos['preset']}/duplicar", {})
    copia = (d.get("preset") or {}).get("id")
    ok(bool(copia), "se duplica el estilo (para borrar la copia)")
    api._r("DELETE", f"/api/presets-light/{copia}")
    pg.js("elegirCliente(''); recordarVideoLight(''); await cargarGaleriaLight(true); irALight('galeria');")
    ok(pg.esperar("button", "Papelera"), "la portada tiene la Papelera a la vista")
    pg.pulsar("button", "Papelera")
    ok(pg.esperar("#papelera button", "Devolver", 15), "la papelera enseña el estilo borrado con «Devolver»")
    ok("taller" not in pg.p.locator("#papelera").inner_text(),
       "sin su taller suelto (vuelve con el estilo, no aparte)")
    pg.captura("15_papelera", entera=False)
    pg.pulsar("#papelera button", "Devolver")
    pg.p.wait_for_timeout(1200)
    pg.pulsar("#papelera .cab button", "×")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate(f"() => presetsLight().some(p => p.id === '{copia}')"),
       "al cerrarla, el estilo devuelto vuelve a salir en la galería")
    r, d = api.get("/api/presets-light")
    taller = next((((x.get("datos") or {}).get("origen") or {}).get("taller")
                   for x in (d.get("presets") or []) if x.get("id") == copia), "")
    ok(taller and os.path.isdir(os.path.join(datos["proyectos"], taller)),
       f"y con él su taller (sus láminas y su escucha): {taller!r}")
    # LA GUIA DE UN CAMPO: «Usar en el campo» y «Copiar»
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});")
    pg.p.wait_for_timeout(1200)
    bloque = pg.p.locator(".bloque-light").filter(has_text="Tono del guion").first
    if bloque.count():
        bloque.locator("button", has_text="Guía").first.click()
        ok(pg.esperar("button", "Copiar", 15), "«✦ Guía» abre la guía con su «Copiar»")
        pg.pulsar("button", "Copiar")
        ok(any("copiado" in a for a in pg.avisos()), "y «Copiar» copia (lo dice)")
        if pg.visible("button", "Usar en el campo"):
            pg.pulsar("button", "Usar en el campo")
            ok(True, "«Usar en el campo» se deja pulsar")
        pg.p.keyboard.press("Escape")
        pg.p.evaluate("() => document.querySelectorAll('#ventana-guia, .capa-dialogo').forEach(x => x.remove())")
    # QUITAR UNA LAMINA Y DEVOLVERLA (gratis: ya está dibujada)
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});")
    ok(pg.esperar(".laminas-estilo .lamina"), "la ficha enseña las láminas")
    antes = pg.p.locator(".laminas-estilo .lamina").count()
    pg.p.locator(".laminas-estilo .lamina").last.locator("button", has_text="Quitar").click()
    pg.p.wait_for_timeout(1000)
    ok(pg.sin_trabajo_del_estilo(), "quitar una lámina rehace la hoja del estilo y termina")
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});")
    pg.esperar(".laminas-estilo .lamina")
    ok(pg.p.locator(".laminas-estilo .lamina").count() == antes - 1, "«Quitar» quita la lámina")
    ok(pg.visible(".laminas-estilo button", "Devolver"), "y ofrece devolverla")
    pg.pulsar(".laminas-estilo button", "Devolver")
    pg.p.wait_for_timeout(1000)
    ok(pg.sin_trabajo_del_estilo(), "devolverla termina")
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});")
    pg.esperar(".laminas-estilo .lamina")
    ok(pg.p.locator(".laminas-estilo .lamina").count() == antes, "«Devolver» la vuelve a poner")
    # LAS NOTAS DE MEJORAS (Configuración)
    pg.js("conmutarConfig(true);")
    pg.p.wait_for_timeout(1200)
    area = pg.p.locator("#config textarea").first
    area.fill("que el subtítulo vaya más arriba en vertical")
    area.dispatch_event("input")
    pg.pulsar("#config button", "Añadir")
    ok(pg.esperar("#config", "más arriba en vertical", 10), "una nota de mejoras se añade")
    ok(pg.visible("#config button", "Copiar todas"), "y sale «Copiar todas»")
    pg.pulsar("#config button", "Copiar todas")
    ok(any("copiad" in a.lower() for a in pg.avisos()), f"que copia la lista ({pg.avisos()[-3:]!r})")
    pg.js("conmutarConfig(false);")
    # LA GUIA DE INICIO
    pg.js("abrirInicio(0);")
    ok(pg.esperar("#inicio button", "Vamos", 10), "la guía de inicio se abre (con «Vamos»)")
    pg.pulsar("#inicio button", "Vamos")
    ok(pg.visible("#inicio button", "Atrás"), "y avanza (con «‹ Atrás»)")
    pg.pulsar("#inicio button", "Atrás")
    ok(pg.visible("#inicio button", "Saltar"), "vuelve atrás, y se puede saltar")
    pg.pulsar("#inicio button", "Saltar")
    ok(not pg.visible("#inicio"), "«Saltar por ahora» la cierra")
    # EL COLOR DEL SUBTITULO
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'encargo_video'; pintarLight();")
    pg.p.wait_for_timeout(1500)
    pg.p.locator(".fila-ajuste").filter(has_text="Subtítulos").locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(800)
    color = pg.p.locator(".editor-ajuste input[type=color]").first
    ok(color.count() == 1, "los subtítulos dejan elegir el color")
    color.evaluate("x => { x.value = '#ff8800'; x.dispatchEvent(new Event('change', { bubbles: true })); }")
    ok(pg.esperar(".editor-ajuste button", "Quitar mi color", 15), "elegido, sale «Quitar mi color»")
    pg.pulsar(".editor-ajuste button", "Quitar mi color")
    ok(pg.esperar(".editor-ajuste", "el del estilo", 15), "y quitarlo vuelve al del estilo")
    pg.sin_trabajo(300)
    # PARTIR UN BLOQUE DEL GUION (se abre y se cancela: partir regraba la voz)
    pg.pulsar(".nav-light button", "Guion")
    pg.p.wait_for_timeout(1200)
    # los botones de cada bloque salen al pasar el ratón (en táctil, siempre)
    pg.p.locator(".parrafo-guion").first.hover()
    partir = pg.p.locator(".parrafo-guion button", has_text="Partir").first
    fin = time.time() + 120
    while time.time() < fin and not (partir.count() and partir.is_enabled()):
        pg.p.wait_for_timeout(1000)
    partir.click()
    pg.p.wait_for_timeout(800)
    ok(pg.visible("button", "Cortar aquí") or pg.visible("button", "Corta al menos"),
       "«Partir» abre el editor para cortar el bloque")
    pg.captura("16_partir_bloque", entera=False)
    pg.sin_errores("lo que sale a veces")
    pg.cerrar()


def _montar_desde_video(pg):
    """Pulsa «Regenerar/Generar Vídeo» en la pantalla del vídeo y espera."""
    pg.pulsar(".nav-light button", "Vídeo")
    pg.p.wait_for_timeout(1500)
    boton = pg.p.locator(".pie-guion button").filter(has_text="Vídeo").first
    if boton.is_enabled():
        boton.click()
        pg.p.wait_for_timeout(1500)
    return pg.sin_trabajo(300)


def _version_de(datos, paso, plano):
    ruta = os.path.join(datos["proyectos"], datos["video"], "pasos", paso, "activa.json")
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


@escenario
def rehacer_y_verlo_en_el_video(navegador, datos):
    """«Regenero imágenes pero no veo los cambios» (11-10-2026). Tres cosas:
    la imagen nueva al lado de la de antes, «Desde cero» que NO le pone delante
    la de ahora (con ella delante el generador la retoca y sale casi igual), y
    el Vídeo diciendo que su MP4 es de antes, SIN recargar la página."""
    pid = datos["video"]
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado al día")
    pg.pulsar(".nav-light button", "Imágenes")
    pg.p.wait_for_timeout(1000)
    pg.js("PREVIA.i = 3; repintarVideo();")
    area = pg.p.locator(".previa-feedback textarea").first
    area.fill("que salga un faro en el horizonte")
    area.dispatch_event("input")
    pg.pulsar(".previa-feedback button", "Guardar nota")
    tarjeta = lambda: pg.p.locator(".nota-imagen").filter(has_text="Imagen S004").first
    ok(tarjeta().locator("button", has_text="Desde cero").count() == 1,
       "la nota ofrece «Desde cero» además de «Rehacer esta imagen»")
    tarjeta().locator("button", has_text="Rehacer esta imagen").click()
    fin = time.time() + 150
    while time.time() < fin and "hecha" not in tarjeta().inner_text().lower():
        pg.p.wait_for_timeout(800)
    pg.p.wait_for_timeout(2500)
    ok("hecha" in tarjeta().inner_text().lower(), "la imagen se rehace")
    ok(tarjeta().locator(".nota-antes img").count() == 1,
       "y la tarjeta enseña cómo era ANTES al lado de la nueva")
    src_antes = tarjeta().locator(".nota-antes img").get_attribute("src") or ""
    src_ahora = tarjeta().locator(".nota-mini:not(.nota-antes) img").first.get_attribute("src") or ""
    ok(src_antes.split("?")[0] != src_ahora.split("?")[0],
       f"y son dos imágenes distintas ({src_antes.split('?')[0][-30:]} / {src_ahora.split('?')[0][-30:]})")
    pg.captura("14_antes_y_ahora", entera=False)
    # «Desde cero»: la ficha del plano dibujado no lleva la imagen rechazada
    tarjeta().locator("button", has_text="Desde cero").click()
    pg.p.wait_for_timeout(1500)
    fin = time.time() + 150
    while time.time() < fin and not ("hecha" in tarjeta().inner_text().lower()
                                     and "dibujando" not in tarjeta().inner_text().lower()):
        pg.p.wait_for_timeout(800)
    pg.p.wait_for_timeout(2500)
    activa = _version_de(datos, "assets", "S004")
    version = activa.get("activa") or activa.get("n") or activa.get("version")
    ficha = os.path.join(datos["proyectos"], pid, "pasos", "assets", f"v{version}",
                         "escenas", "S004.json")
    try:
        with open(ficha, encoding="utf-8") as fh:
            papeles = [r.get("papel") for r in json.load(fh).get("referencias") or []]
    except (OSError, ValueError) as fallo:
        papeles = [f"no se pudo leer {ficha}: {fallo}"]
    ok("rechazada" not in papeles and papeles,
       f"«Desde cero» la dibuja SIN la imagen de antes delante ({papeles})")
    # EL VIDEO, sin recargar
    pg.pulsar(".nav-light button", "Vídeo")
    pg.p.wait_for_timeout(1500)
    ok(pg.visible(".caja-aviso", "ANTES de tus últimos cambios"),
       "el Vídeo dice que su MP4 es de antes de las imágenes rehechas (sin recargar)")
    ok(pg.visible(".pastilla.obsoleto"), "con su «Obsoleto»")
    src_video = pg.p.locator("video").first.get_attribute("src") or ""
    boton = pg.p.locator(".pie-guion button").filter(has_text="Vídeo").first
    ok(boton.is_enabled(), "y «Regenerar Vídeo» se puede pulsar")
    tandas = []
    pg.p.on("request", lambda r: tandas.append(r.post_data or "")
            if r.method == "POST" and r.url.endswith("/generar") else None)
    boton.click()
    pg.p.wait_for_timeout(800)
    ok(tandas and all('"pendientes"' in t for t in tandas),
       f"y monta SOLO lo que quedó viejo (modo «pendientes», nunca «todo»): {tandas[:2]}")
    pg.p.wait_for_timeout(1500)
    ok(pg.sin_trabajo(300), "el vídeo se vuelve a montar")
    pg.p.wait_for_timeout(1500)
    nuevo = pg.p.locator("video").first.get_attribute("src") or ""
    ok(nuevo and nuevo != src_video, f"y el reproductor carga el MP4 NUEVO ({src_video[-28:]} → {nuevo[-28:]})")
    ok(not pg.visible(".caja-aviso", "ANTES de tus últimos cambios"), "y el aviso se va")
    # LAS TILDES ROTAS DE LA VOZ: la tarjeta las enseña bien y el Vídeo ofrece
    # volver a dibujar los subtítulos sin pagar nada
    pg.pulsar(".nav-light button", "Imágenes")
    pg.p.wait_for_timeout(1200)
    guion = " ".join(pg.p.locator(".nota-imagen .nota-guion").all_inner_texts()) + " " + \
        " ".join(pg.p.locator(".previa-feedback .meta").all_inner_texts())
    ok("Ã" not in pg.p.locator("#panel").inner_text(),
       "en Imágenes ninguna frase sale con «Ã» (la voz llegó rota y se enseña bien)")
    ok(not pg.visible(".caja-aviso", "tildes rotas"),
       "un vídeo cuyos subtítulos ya se dibujaron con el arreglo NO enseña el aviso")
    # COMO UN VIDEO MONTADO ANTES DEL ARREGLO: su subtítulo dibujado dice «zarpÃ³»
    activa = _version_de(datos, "callouts", "")
    capas = os.path.join(datos["proyectos"], pid, "pasos", "callouts",
                         f"v{activa.get('activa')}", "capas_fijas")
    for nombre in os.listdir(capas):
        ruta = os.path.join(capas, nombre)
        with open(ruta, encoding="utf-8") as fh:
            svg = fh.read()
        if "zarpó" in svg:
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write(svg.replace("zarpó", "zarpÃ³"))
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar(".caja-aviso", "tildes rotas", 10), "el Vídeo avisa de los subtítulos con tildes rotas")
    pg.pulsar(".caja-aviso button", "Arreglar los subtítulos")
    pg.p.wait_for_timeout(1500)
    ok(pg.sin_trabajo(300), "«Arreglar los subtítulos» monta el vídeo otra vez")
    pg.p.wait_for_timeout(2000)
    ok(not pg.visible(".caja-aviso", "tildes rotas"), "y el aviso ya no sale")
    capa = ""
    for raiz, _d, ficheros in os.walk(os.path.join(datos["proyectos"], pid, "pasos", "callouts")):
        for nombre in ficheros:
            if nombre.endswith(".svg") and "S001" in nombre:
                with open(os.path.join(raiz, nombre), encoding="utf-8", errors="replace") as fh:
                    capa += fh.read()
    ok("zarpó" in capa or "Zarpó" in capa or "ZARPÓ" in capa,
       "y el subtítulo dibujado dice «zarpó», no «zarpÃ³»")
    # REHACER UNA IMAGEN MIENTRAS SE MONTA: entra en la cola y espera sola
    api = datos["api"]
    api.libre(pid)
    r, d = api.post(f"/api/proyectos/{pid}/subtitulos/rehacer", {})
    ok(r.status_code == 202, "se lanza un montaje (los subtítulos)")
    r, d = api.post(f"/api/proyectos/{pid}/repaso", {"texto": "un faro más grande", "t": 9,
                                                      "plano": "S003", "pantalla": "imagenes"})
    nid = (d.get("nota") or {}).get("id")
    r, d = api.post(f"/api/proyectos/{pid}/imagenes/rehacer", {"notas": [nid]})
    ok(r.status_code == 202 and d.get("esperando"),
       f"rehacer una imagen mientras se monta ya no da error: espera en la cola ({r.status_code}, {d.get('esperando')!r})")
    fin = time.time() + 400
    hecha = False
    while time.time() < fin and not hecha:
        time.sleep(3)
        _r, rep = api.get(f"/api/proyectos/{pid}/repaso")
        hecha = any(n.get("id") == nid and n.get("estado") == "aplicado" for n in rep.get("notas") or [])
    ok(hecha, "y la imagen se dibuja sola en cuanto termina el montaje")
    pg.sin_errores("rehacer y verlo en el vídeo")
    pg.cerrar()


@escenario
def lo_que_se_vio_el_10_de_octubre(navegador, datos):
    """Lo que encontro el dueno abriendo un video de verdad (10-10-2026), y que
    el recorrido no miraba: la referencia adjunta a una nota a tamano real,
    pulsar la miniatura o «Ver como quedo» sin que se viera nada, la narracion
    con «TÃº», «Estilos» dentro de un video yendo a la portada y «Revisar» sin
    poder aplicar lo que propone."""
    import io                                                # noqa: PLC0415
    from PIL import Image                                    # noqa: PLC0415
    api, pid = datos["api"], datos["video"]
    # UNA NOTA CON UNA FOTO GRANDE ADJUNTA (como el Joy-Con de la captura)
    crudo = io.BytesIO()
    Image.new("RGB", (2400, 1600), (200, 60, 60)).save(crudo, "PNG")
    r, d = api.post(f"/api/proyectos/{pid}/repaso/imagenes",
                    files={"f": ("joycon.png", crudo.getvalue(), "image/png")})
    nombre = ((d.get("imagenes") or [{}])[0]).get("nombre")
    ok(bool(nombre), "se sube la referencia de la nota")
    api.post(f"/api/proyectos/{pid}/repaso", {"texto": "que el mando sea rojo y azul", "t": 5,
                                               "plano": "S003", "imagenes": [nombre],
                                               "pantalla": "imagenes"})
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    pg.pulsar(".nav-light button", "Imágenes")
    ok(pg.esperar(".nota-imagen .tira-aportadas img"), "la nota enseña su referencia")
    pg.p.wait_for_timeout(800)
    caja = pg.p.locator(".nota-imagen .tira-aportadas img").first.bounding_box()
    ok(caja and caja["width"] <= 200 and caja["height"] <= 150,
       f"y en MINIATURA, no a su tamaño real (2400x1600): {caja}")
    tarjeta = pg.p.locator(".nota-imagen").filter(has_text="Imagen S003").first
    tcaja = tarjeta.bounding_box()
    ok(tcaja and tcaja["height"] < 600, f"la tarjeta no se come la pantalla: {tcaja}")
    pg.captura("11_nota_con_referencia", entera=False)
    # PULSAR LA MINIATURA LLEVA A LA IMAGEN Y SE VE
    tarjeta.locator(".nota-mini:not(.nota-antes)").click()
    pg.p.wait_for_timeout(1200)
    ok(pg.p.evaluate("() => ((PREVIA.ficha || {}).escenas || [])[PREVIA.i].id") == "S003",
       "pulsar la miniatura pone esa imagen en el visor")
    dentro = pg.p.evaluate("""() => { const m = document.querySelector('.previa-marco');
        if (!m) return false; const r = m.getBoundingClientRect();
        return r.top < window.innerHeight * 0.5 && r.bottom > 80; }""")
    ok(dentro, "y el visor queda A LA VISTA (antes cambiaba fuera de la pantalla)")
    # «VER CÓMO QUEDÓ» de una imagen ya rehecha (la del recorrido de notas, S001)
    if pg.p.locator("button", has_text="Ver cómo quedó").count():
        pg.p.locator("details.imagenes-hechas").evaluate_all("ds => ds.forEach(d => d.open = true)")
        pg.p.locator("button", has_text="Ver cómo quedó").first.scroll_into_view_if_needed()
        pg.p.locator("button", has_text="Ver cómo quedó").first.click()
        pg.p.wait_for_timeout(1200)
        dentro = pg.p.evaluate("""() => { const m = document.querySelector('.previa-marco');
            const r = m.getBoundingClientRect(); return r.top < window.innerHeight * 0.5 && r.bottom > 80; }""")
        ok(dentro, "«Ver cómo quedó» también lleva al visor")
    # LA NARRACION QUE LLEGO COMO LATIN-1 SE LEE BIEN
    ok(pg.p.evaluate("() => legible('«TÃº no dices nada, papÃ¡» Â«yaÂ»')")
       == "«Tú no dices nada, papá» «ya»", "la narración con «TÃº» se enseña como «Tú»")
    ok(pg.p.evaluate("() => legible('año Ángel € normal')") == "año Ángel € normal",
       "y un texto sano no se toca")
    # «ESTILOS» DENTRO DE UN VÍDEO: EL ESTILO DE ESE VÍDEO
    pg.pulsar(".nav-light button", "Estilo")
    ok(pg.esperar(".light-preset h2", "Estado Play Matriz"),
       "«Estilos» desde un vídeo abre el estilo con el que se hizo")
    ok(pg.visible(".light-preset button", "Volver al vídeo"), "con «Volver al vídeo»")
    pg.captura("12_estilos_desde_el_video", entera=False)
    pg.pulsar(".light-preset button", "Volver al vídeo")
    ok(pg.p.evaluate("() => APP.light.vista === 'elegido' && APP.light.video.pid") == pid,
       "y vuelve a ese vídeo")
    pg.sin_trabajo()
    # «REVISAR» EN EL ENCARGO, CON LA PANTALLA REPINTÁNDOSE MIENTRAS
    pg.pulsar(".nav-light button", "Encargo")
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    area = bloque.locator("textarea").first
    original = area.input_value()
    area.fill(original + " [PENDIENTE]")
    area.dispatch_event("input")
    bloque.locator("button", has_text="Revisar").first.click()
    pg.js("pintarLight();")     # lo que hace el guardado al quedar el guion obsoleto
    ok(pg.esperar(".bloque-light .revision-campo", "Mejorable", 60),
       "la revisión del material sale aunque la pantalla se haya repintado")
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    ok(bloque.locator("button", has_text="Aplicar la versión sugerida").count() == 1,
       "y ofrece aplicar la versión sugerida")
    pg.js("pintarLight();")
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    ok(bloque.locator("button", has_text="Aplicar la versión sugerida").count() == 1,
       "y sigue ahí después de otro repintado")
    bloque.locator("button", has_text="Aplicar la versión sugerida").first.click()
    pg.p.wait_for_timeout(2500)
    valor = pg.p.locator(".bloque-light").filter(has_text="El material").first.locator(
        "textarea").first.input_value()
    ok("PENDIENTE" not in valor and "(revisado)" in valor,
       f"aplicarla cambia el material ({valor[-60:]!r})")
    pg.captura("13_revisar_en_el_encargo", entera=False)
    # se deja el material como estaba: lo que viene detras no tiene que verlo
    area = pg.p.locator(".bloque-light").filter(has_text="El material").first.locator("textarea").first
    area.fill(original)
    area.dispatch_event("input")
    pg.p.wait_for_timeout(2500)
    pg.sin_errores("lo que se vio el 10 de octubre")
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
    ok(pg.esperar(".trabajo-laminas", "Rehaciendo las láminas", 10),
       "quitar una lámina lo rehace AHÍ MISMO, con su barra (sin salir de la ficha)")
    ok(pg.p.evaluate("() => APP.light.vista") == "preset", "y la ficha no se va a la pantalla de generar")
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


#: Lo que el recorrido de TODOS LOS BOTONES no pulsa: lo que lanza trabajos
#: largos, borra o sale. Lo demás se pulsa todo (los confirm() se CANCELAN en
#: este escenario, así que lo que pregunta antes no llega a hacer nada).
NO_PULSAR = re.compile(r"(Borrar|Eliminar|papelera|Regenerar|Generar|Rehacer|Desde cero|"
                       r"Montar|Aplicar|Arreglar|Salir|Descargar|Traer|Restablecer|Revertir|"
                       r"Parar|Reintentar|Duplicar|Crear|Guardar|Subir|Probar|Entrar|"
                       r"Pedir otro enlace|Ocultar|Esconder|Apartar|Mover|Quitar|Ver ocultos|"
                       r"Hacerla sin marcas|Usar|Partir|Añadir|Nuevo|Nueva|Volver a la versi|\+)", re.I)

#: Firma de «algo ha cambiado» tras un clic: el DOM, el aviso, lo abierto.
FIRMA_JS = """() => {
  const t = document.querySelector('#toast');
  // un hash del DOM entero y no su largo: cambiar la clase «activo» de un botón
  // a otro deja el largo igual
  const html = document.body.innerHTML;
  let hash = 5381;
  for (let i = 0; i < html.length; i += 1) hash = ((hash * 33) ^ html.charCodeAt(i)) | 0;
  const valores = [...document.querySelectorAll('input, textarea, select')]
    .map(x => x.type === 'checkbox' || x.type === 'radio' ? (x.checked ? 1 : 0) : x.value).join('¦');
  return [hash, valores, window.__toasts || 0, document.querySelectorAll('*').length,
          t ? t.innerText + t.className : '', document.querySelector('#panel').scrollTop,
          (document.activeElement || {}).id || '', document.body.className,
          [...document.querySelectorAll('details')].map(d => d.open ? 1 : 0).join('')].join('|');
}"""

#: Dónde se está: si un clic saca de la pantalla, se vuelve a ella.
DONDE_JS = """() => JSON.stringify([APP.light.vista, (APP.light.video || {}).pid,
  (APP.light.video || {}).vista, APP.light.abierto || '',
  document.querySelector('#config') && !document.querySelector('#config').classList.contains('plegado')])"""


def _botones_visibles(pg):
    # con un cajón abierto (Configuración) solo cuenta lo de dentro: lo de
    # detrás está tapado A PROPÓSITO y se cierra con la ×
    return pg.p.evaluate("""() => {
      const cajon = document.querySelector('#config:not(.plegado)');
      return [...document.querySelectorAll('button, a.boton')]
      .filter(b => (b.offsetParent !== null || b.getClientRects().length) && !b.disabled
              && !b.closest('#asistente') && b.id !== 'burbuja-asistente'
              && (!cajon || cajon.contains(b))
              && b.getAttribute('aria-current') !== 'page')
      .map(b => (b.innerText || b.textContent || b.title || '').replace(/\\s+/g, ' ').trim()
                || ('[' + (b.title || b.getAttribute('aria-label') || b.className) + ']')); }""")


def _buscar_boton(pg, texto, n):
    """El n-ésimo botón visible con ese texto, o None."""
    candidatos = pg.p.locator("button:visible, a.boton:visible")
    visto = 0
    for i in range(candidatos.count()):
        try:
            b = candidatos.nth(i)
            t = (b.inner_text(timeout=500) or b.get_attribute("title") or "").split()
            t = " ".join(t) or "[" + (b.get_attribute("title") or b.get_attribute("aria-label")
                                      or b.get_attribute("class") or "") + "]"
        except Exception:                                    # noqa: BLE001
            continue
        if t == texto:
            if visto == n:
                return b
            visto += 1
    return None


def _pantallas(datos):
    """Cada pantalla de la aplicación y cómo se llega a ella (JavaScript)."""
    pid = datos["video"]
    return [
        ("portada", "elegirCliente(''); recordarVideoLight(''); await cargarGaleriaLight(true); irALight('galeria');"),
        ("proyecto", f"elegirCliente('{datos['cliente']}'); recordarVideoLight(''); irALight('galeria');"),
        ("ficha del estilo", f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{datos['preset']}' }});"),
        ("estilo nuevo", "irALight('crear');"),
        ("encargo", f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'encargo_video'; pintarLight();"),
        ("guion", f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'guion'; pintarLight();"),
        ("imágenes", f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();"),
        ("vídeo", f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();"),
        ("configuración", "conmutarConfig(true);"),
        ("guía de inicio", "abrirInicio(0);"),
    ]


#: Lo que no puede salir NUNCA en un texto de la pantalla.
TEXTOS_MALOS = re.compile(r"\bundefined\b|\bNaN\b|\[object Object\]|\bnull\b|Ã[\u0080-\u00bf]|Â[«»¿¡]")

MEDIR_JS = """() => {
  const ancho = document.documentElement.clientWidth;
  const fuera = [];
  document.querySelectorAll('#panel *, #config *, #inicio *, header *, .nav-light *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const st = getComputedStyle(e);
    if (st.position === 'fixed' && e.closest('#asistente')) return;
    // dentro de algo que ya hace scroll horizontal a propósito, no cuenta
    let p = e.parentElement, enScroll = false;
    while (p && p !== document.body) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden') { enScroll = true; break; }
      p = p.parentElement;
    }
    if (!enScroll && r.right > ancho + 2) fuera.push((e.className || e.tagName) + ' ' + Math.round(r.right));
  });
  const grandes = [...document.querySelectorAll('#panel img, #config img')].filter(i => {
    const r = i.getBoundingClientRect(); return r.width > ancho + 2;
  }).map(i => i.src.slice(-40));
  // LO QUE TAPA LA BURBUJA DEL ASISTENTE: un botón que no se puede pulsar
  // porque la burbuja está encima (y no hay forma de apartarlo con el scroll)
  const burbuja = document.querySelector('#burbuja-asistente');
  const tapados = [];
  if (burbuja && burbuja.getClientRects().length) {
    const alto = document.documentElement.clientHeight;
    const panel = document.querySelector('#panel');
    const antes = panel.scrollTop;
    // dos miradas: arriba del todo y abajo del todo. Tapado en las dos = no hay
    // forma de pulsarlo (lo que está a media página se aparta con el scroll)
    const mirar = () => {
      const salen = new Set();
      document.querySelectorAll('#panel button, #panel a.boton').forEach(b => {
        const r = b.getBoundingClientRect();
        if (!r.width || r.bottom > alto || r.top < 0) return;
        // los que solo salen al pasar el ratón (y en táctil, siempre: ver
        // estilo.css «hover: none») están escondidos: no hay nada que tapar
        if (getComputedStyle(b).visibility === 'hidden') return;
        const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        if (e && burbuja.contains(e)) salen.add(b);
      });
      return salen;
    };
    panel.scrollTop = 0;
    const arriba = mirar();
    panel.scrollTop = panel.scrollHeight;
    const abajo = mirar();
    panel.scrollTop = antes;
    abajo.forEach(b => {
      // tapado abajo y además es lo último (no se puede subir más)
      tapados.push(((b.innerText || b.title || b.getAttribute('aria-label') || '').trim()
        || `<${b.tagName.toLowerCase()} class="${b.className}">`).slice(0, 40));
    });
    if (panel.scrollHeight <= panel.clientHeight + 2) arriba.forEach(b => {
      if (!abajo.has(b)) tapados.push((b.innerText || b.title || '').trim().slice(0, 30));
    });
  }
  return { scroll: document.documentElement.scrollWidth - ancho, fuera: fuera.slice(0, 6),
           grandes, tapados, texto: (document.body.innerText || '') };
}"""

TEXTOS_DE_PANTALLA = {}


@escenario
def tamanos_temas_y_textos(navegador, datos):
    """Cada pantalla en móvil, tableta y ordenador, y en los dos temas: nada se
    sale por los lados, ninguna imagen es más ancha que la pantalla y ningún
    texto dice «undefined», «NaN», «null» ni sale con las tildes rotas. Los
    textos de todas las pantallas quedan en `textos_de_pantalla.txt` para
    leerlos de corrido."""
    problemas = []
    for ancho, alto, tema in ((390, 844, "oscuro"), (820, 1180, "claro"), (1300, 900, "oscuro"),
                              (1300, 900, "claro")):
        for nombre, ir in _pantallas(datos):
            pg = Pagina(navegador, datos, ancho=ancho, alto=alto, nombre=nombre)
            if tema == "claro":
                pg.js("document.documentElement.dataset.tema = 'claro';")
            pg.aceptar = False
            pg.js(ir)
            pg.p.wait_for_timeout(1800)
            m = pg.p.evaluate(MEDIR_JS)
            donde = f"{nombre} a {ancho}px ({tema})"
            if m["scroll"] > 2:
                problemas.append(f"{donde}: la página se sale {m['scroll']}px por la derecha "
                                 f"({m['fuera'][:3]})")
            if m["tapados"]:
                problemas.append(f"{donde}: la burbuja del asistente tapa {m['tapados'][:3]}")
            if m["grandes"]:
                problemas.append(f"{donde}: imágenes más anchas que la pantalla {m['grandes'][:2]}")
            # el aviso de los subtítulos rotos pone el ejemplo a propósito
            m["texto"] = m["texto"].replace("«TÃº» en vez de «Tú»", "")
            malos = sorted(set(x.group(0) for x in TEXTOS_MALOS.finditer(m["texto"])))
            if malos:
                trozo = TEXTOS_MALOS.search(m["texto"])
                problemas.append(f"{donde}: texto con {malos} («…{m['texto'][max(0, trozo.start() - 40):trozo.end() + 20]}…»)")
            if ancho == 1300 and tema == "oscuro":
                TEXTOS_DE_PANTALLA[nombre] = m["texto"]
            if ancho == 390 or (ancho == 1300 and tema == "claro"):
                pg.captura(f"tam_{ancho}_{tema}_{nombre.replace(' ', '_')}", entera=False)
            if pg.errores:
                problemas.append(f"{donde}: errores de JavaScript {pg.errores[:2]}")
            pg.cerrar()
    with open(os.path.join(datos["capturas"], "textos_de_pantalla.txt"), "w", encoding="utf-8") as fh:
        for nombre, texto in TEXTOS_DE_PANTALLA.items():
            fh.write(f"\n\n========== {nombre.upper()} ==========\n\n{texto}\n")
    print(f"  (40 combinaciones de pantalla, tamaño y tema; textos en "
          f"{os.path.join(datos['capturas'], 'textos_de_pantalla.txt')})")
    ok(not problemas, f"todas las pantallas caben y se leen bien ({len(problemas)}) -- "
       + " | ".join(problemas[:12]))


@escenario
def abrir_no_escribe_nada(navegador, datos):
    """REGLA 1 DE CLAUDE.md: abrir una pantalla no escribe nada. Un param «por
    defecto» escrito al abrir mueve la firma y la pantalla ofrece regenerar (y
    pagar) el vídeo entero. Se abren todas las pantallas SIN tocar nada,
    mirando cada petición que sale, y se comparan los estados de los pasos."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    _r, antes = api.get(f"/api/proyectos/{pid}")
    firmas_antes = {p.get("id"): (p.get("estado"), p.get("firma")) for p in antes.get("pasos") or []}
    escrituras = []
    for nombre, ir in _pantallas(datos):
        pg = Pagina(navegador, datos, nombre=nombre)
        pg.p.on("request", lambda r, nombre=nombre: escrituras.append(f"{nombre}: {r.method} {r.url.split('/api/', 1)[-1]}")
                if r.method in ("PUT", "POST", "DELETE", "PATCH") and "/api/" in r.url
                and not re.search(r"/api/(asistente|sistema/revis|me$|logout|ortografia|estimacion$|presets-light/plan$)",
                                  r.url) else None)
        pg.js(ir)
        pg.p.wait_for_timeout(2500)
        pg.cerrar()
    ok(not escrituras, f"abrir las {len(_pantallas(datos))} pantallas sin tocar nada no escribe nada -- {escrituras[:6]}")
    _r, despues = api.get(f"/api/proyectos/{pid}")
    firmas = {p.get("id"): (p.get("estado"), p.get("firma")) for p in despues.get("pasos") or []}
    ok(firmas == firmas_antes, "y ningún paso cambia de estado ni de firma"
       + ("" if firmas == firmas_antes else f" -- {[(k, firmas_antes.get(k), v) for k, v in firmas.items() if firmas_antes.get(k) != v]}"))


@escenario
def escape_cierra_lo_abierto(navegador, datos):
    """Escape cierra la guía de inicio, Configuración, el asistente y el detalle
    del coste, sin errores (se rompió el 11-10-2026 al quitar el menú de
    proyectos: el atajo llamaba a una función borrada)."""
    pg = Pagina(navegador, datos)
    pg.js("abrirInicio(0);")
    ok(pg.visible("#inicio"), "la guía de inicio está abierta")
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(500)
    ok(not pg.visible("#inicio"), "Escape cierra la guía de inicio")
    pg.js("conmutarConfig(true);")
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(500)
    ok(pg.p.evaluate("() => document.querySelector('#config').classList.contains('plegado')"),
       "Escape cierra Configuración")
    pg.p.locator("#burbuja-asistente").click()
    pg.p.wait_for_timeout(500)
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(500)
    ok(not pg.p.evaluate("() => ASISTENTE.abierto"), "Escape cierra el asistente")
    pg.sin_errores("Escape")
    pg.cerrar()


@escenario
def repintar_no_pierde_nada(navegador, datos):
    """La pantalla se repinta sola (el coste, un trabajo que avanza, el guardado
    de otro campo). Lo que se está escribiendo NO puede perderse por eso: fue
    lo que dejaba a «Revisar» sin su botón de aplicar. En cada pantalla se
    escribe en cada campo, se fuerza un repintado y se mira que siga ahí."""
    perdidos = []
    for nombre, ir in _pantallas(datos):
        if nombre in ("guía de inicio",):
            continue
        pg = Pagina(navegador, datos, nombre=nombre)
        pg.aceptar = False
        pg.js(ir)
        pg.p.wait_for_timeout(1500)
        campos = pg.p.locator("#panel textarea:visible, #panel input[type=text]:visible, "
                              "#panel input[type=search]:visible, #config textarea:visible")
        originales = []
        for i in range(min(campos.count(), 12)):
            campo = campos.nth(i)
            try:
                originales.append((i, campo.input_value()))
                campo.fill(f"{campo.input_value()} ZQX{i}")
                campo.dispatch_event("input")
            except Exception:                                # noqa: BLE001
                continue
        pg.p.wait_for_timeout(300)
        pg.js("pintarLight();")
        pg.p.wait_for_timeout(1500)
        pg.js("pintarLight();")
        pg.p.wait_for_timeout(800)
        valores = pg.p.evaluate("() => [...document.querySelectorAll('textarea, input')].map(x => x.value).join(' ')")
        for i, _ in originales:
            if f"ZQX{i}" not in valores:
                perdidos.append(f"{nombre}: el campo {i + 1} pierde lo escrito al repintarse")
        # se deja todo como estaba
        campos = pg.p.locator("#panel textarea:visible, #panel input[type=text]:visible, "
                              "#panel input[type=search]:visible, #config textarea:visible")
        # EXACTAMENTE lo que había (no «quitando lo añadido»: un espacio de
        # menos deja el encargo distinto y el guion obsoleto para los demás)
        originales_por_indice = dict(originales)
        for i in range(min(campos.count(), 12)):
            try:
                campo = campos.nth(i)
                if "ZQX" in campo.input_value() and i in originales_por_indice:
                    campo.fill(originales_por_indice[i])
                    campo.dispatch_event("input")
            except Exception:                                # noqa: BLE001
                continue
        pg.p.wait_for_timeout(2500)
        pg.sin_errores(f"repintar {nombre}")
        pg.cerrar()
    ok(not perdidos, f"repintar la pantalla no se lleva nada de lo escrito -- {perdidos[:10]}")


@escenario
def todos_los_botones(navegador, datos):
    """Cada pantalla, CADA botón: pulsarlo tiene que cambiar algo que se vea
    (la pantalla, un aviso, un diálogo) y no dar ningún error. Un botón que no
    hace nada al pulsarlo es el fallo más tonto de encontrar a mano y el más
    fácil de dejar pasar: así salieron «Ver cómo quedó» y la miniatura."""
    # la guía de inicio no: sus botones van tarjeta a tarjeta y se prueban en otro sitio
    pantallas = [x for x in _pantallas(datos) if x[0] != 'guía de inicio']
    muertos, rotos, pulsados = [], [], 0
    for nombre, ir in pantallas:
        pg = Pagina(navegador, datos, nombre=nombre)
        pg.aceptar = False           # lo que pregunta antes de hacer algo, se cancela
        dialogos = pg.dialogos
        abiertos = []
        pg.p.on("filechooser", lambda f: abiertos.append(1))
        pg.p.on("popup", lambda p_: abiertos.append(1))
        # cada aviso cuenta como «ha hecho algo», aunque diga lo mismo que el anterior
        pg.js("window.__toasts = 0; const _toast = toast; "
              "toast = function (...a) { window.__toasts += 1; return _toast.apply(this, a); };")
        pg.js(ir)
        pg.p.wait_for_timeout(1500)
        donde = pg.p.evaluate(DONDE_JS)
        textos = _botones_visibles(pg)
        vistos = {}
        for texto in textos:
            n = vistos.get(texto, 0)
            vistos[texto] = n + 1
            if NO_PULSAR.search(texto):
                continue
            if pg.p.evaluate(DONDE_JS) != donde:
                pg.js(ir)
                pg.p.wait_for_timeout(1200)
            objetivo = _buscar_boton(pg, texto, n)
            if objetivo is None:
                continue
            try:
                # apagado A PROPÓSITO por lo pulsado antes (la novena ★ con ocho
                # ya marcadas): no es un botón roto
                if not objetivo.is_enabled():
                    continue
            except Exception:                                # noqa: BLE001
                continue
            try:
                ya_puesto = objetivo.evaluate(
                    "b => /\\b(activo|puesta|activa)\\b/.test(b.className) || b.getAttribute('aria-pressed') === 'true'")
            except Exception:                                # noqa: BLE001
                ya_puesto = False
            antes = pg.p.evaluate(FIRMA_JS)
            n_dialogos, n_abiertos, n_errores = len(dialogos), len(abiertos), len(pg.errores)
            try:
                try:
                    objetivo.click(timeout=3000)
                except Exception:                            # noqa: BLE001
                    # se repintó mientras (un aviso encima, la rejilla rehecha):
                    # se vuelve a buscar y se pulsa otra vez, como haría alguien
                    pg.p.wait_for_timeout(1500)
                    # y si algo quedó abierto encima (una guía, un cajón), se
                    # vuelve a la pantalla limpia
                    pg.p.keyboard.press("Escape")
                    pg.p.evaluate("() => document.querySelectorAll('#lupa, .capa-dialogo, "
                                  "#ventana-guia, #papelera').forEach(x => x.remove())")
                    pg.js(ir)
                    pg.p.wait_for_timeout(1200)
                    objetivo = _buscar_boton(pg, texto, n)
                    if objetivo is None:
                        continue
                    objetivo.click(timeout=3000)
            except Exception as fallo:                       # noqa: BLE001
                motivo = re.search(r"(<[^>]{0,120}> (?:from <[^>]{0,80}> subtree )?intercepts pointer events"
                                   r"|element is not visible|element is outside of the viewport"
                                   r"|element is not stable)", str(fallo))
                rotos.append(f"{nombre} · «{texto}»: no se deja pulsar "
                             f"({motivo.group(1) if motivo else str(fallo)[:80]})")
                continue
            pulsados += 1
            pg.p.wait_for_timeout(900)
            despues = pg.p.evaluate(FIRMA_JS)
            # solo las EXCEPCIONES sin recoger: un console.error es la pantalla
            # contando un fallo que ya enseña (la tanda que murió, una clave)
            nuevos = [e for e in pg.errores[n_errores:] if e.startswith("pageerror")]
            if nuevos:
                rotos.append(f"{nombre} · «{texto}»: {nuevos[:2]}")
            # pulsar la opción que YA está elegida no tiene por qué hacer nada
            if antes == despues and len(dialogos) == n_dialogos and len(abiertos) == n_abiertos \
                    and not ya_puesto:
                muertos.append(f"{nombre} · «{texto}»")
            # se cierra lo que haya abierto encima (lupa, diálogos propios)
            pg.p.keyboard.press("Escape")
            pg.p.evaluate("() => document.querySelectorAll('#lupa, .capa-dialogo, #ventana-guia, #papelera').forEach(x => x.remove())")
        pg.errores.clear()
        pg.cerrar()
    print(f"  ({pulsados} botones pulsados en {len(pantallas)} pantallas)")
    ok(not rotos, f"ningún botón da error al pulsarlo -- {rotos[:8]}")
    ok(not muertos, f"ningún botón se queda sin hacer nada al pulsarlo ({len(muertos)}) -- {muertos[:30]}")
    DATOS_BOTONES["muertos"] = muertos
    DATOS_BOTONES["rotos"] = rotos


DATOS_BOTONES = {}


@escenario
def ortografia_de_los_subtitulos(navegador, datos):
    """El corrector de ortografía: propone las tildes que faltan en los
    subtítulos, aplica las marcadas como texto del subtítulo de cada plano
    (sin tocar voz ni imágenes) y el vídeo montado otra vez las lleva."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar(".panel-ortografia button", "Revisar la ortografía", 15),
       "la pantalla Vídeo tiene «Revisar la ortografía» de los subtítulos")
    pg.pulsar(".panel-ortografia button", "Revisar la ortografía")
    ok(pg.esperar(".panel-ortografia", "con faltas", 90), "propone correcciones")
    # en minúsculas: el estilo del subtítulo puede ir en MAYÚSCULAS («GRÚAS»)
    texto = pg.p.locator(".panel-ortografia").first.inner_text().lower()
    ok("→" in texto and any(x in texto for x in ("grúas", "mercancía", "idénticas", "más")),
       f"con las tildes que faltan («gruas → grúas»…) ({texto[:200]!r})")
    pg.js("pintarLight();")
    ok(pg.visible(".panel-ortografia button", "Aplicar las marcadas"),
       "y lo propuesto sigue ahí aunque la pantalla se repinte")
    _r, antes = api.get(f"/api/proyectos/{pid}")
    estado_assets = {p.get("id"): p.get("estado") for p in antes.get("pasos") or []}.get("assets")
    pg.captura("18_ortografia", entera=False)
    pg.pulsar(".panel-ortografia button", "Aplicar las marcadas")
    pg.p.wait_for_timeout(2000)
    _r, despues = api.get(f"/api/proyectos/{pid}")
    estados = {p.get("id"): p.get("estado") for p in despues.get("pasos") or []}
    ok(estados.get("assets") == estado_assets and estados.get("voz") != "obsoleto",
       f"aplicarlas no toca ni la voz ni las imágenes ({estados})")
    ok(pg.esperar(".caja-aviso", "ANTES de tus últimos cambios", 15),
       "y el Vídeo dice que hay que volver a montarlo")
    ok("No se dibuja ninguna imagen" in pg.p.locator(".caja-aviso").filter(
        has_text="ANTES de tus").first.inner_text(), "sin dibujar ninguna imagen")
    # se monta por la API (el botón depende de lo que hayan dejado otros escenarios)
    r, d = api.post(f"/api/proyectos/{pid}/generar", {"tanda": "render", "modo": "pendientes"})
    fin_montaje = api.esperar(d.get("trabajo_id") or (d.get("trabajo") or {}).get("id"), 600)
    ok(fin_montaje.get("estado") == "listo", f"se vuelve a montar ({fin_montaje.get('estado')})")
    activa = _version_de(datos, "callouts", "").get("activa")
    capa = ""
    carpeta = os.path.join(datos["proyectos"], pid, "pasos", "callouts", f"v{activa}", "capas_fijas")
    for nombre in os.listdir(carpeta) if os.path.isdir(carpeta) else []:
        with open(os.path.join(carpeta, nombre), encoding="utf-8", errors="replace") as fh:
            capa += fh.read()
    ok(any(x in capa.lower() for x in ("grúas", "mercancía", "idénticas", "decía")),
       "y el subtítulo dibujado ya lleva las tildes corregidas («grúas», «mercancía»…)")
    # EL GUION, por la API (el vídeo de prueba ya tiene la voz grabada)
    r, d = api.post(f"/api/proyectos/{pid}/ortografia/revisar",
                    {"fuente": "guion", "textos": {"B001": "una manana de octubre"}})
    rid = d.get("id")
    fin = time.time() + 60
    while time.time() < fin:
        _r, ficha = api.get(f"/api/proyectos/{pid}/ortografia/{rid}")
        if ficha.get("estado") != "pensando":
            break
        time.sleep(1)
    ok(any(p.get("despues") == "una mañana de octubre" for p in ficha.get("propuestas") or []),
       "el guion también se revisa (antes de grabar la voz)")
    # LA REVISIÓN VA CON SU VÍDEO Y SU FUENTE: una revisión del guion (o de
    # otro vídeo) no se puede aplicar como subtítulos de estos planos
    r, _d = api.post(f"/api/proyectos/{pid}/ortografia/aplicar",
                     {"cambios": {"S001": "otra cosa"}, "rid": rid})
    ok(r.status_code == 409, f"aplicar con una revisión que no es de estos subtítulos: 409 ({r.status_code})")
    with open(os.path.join(datos["proyectos"], pid, "estado.json"), encoding="utf-8") as fh:
        unidades = ((json.load(fh).get("pasos") or {}).get("callouts") or {}).get("params", {}).get("unidades") or {}
    puestas = [u for u in unidades.values() if isinstance(u, dict) and u.get("subtitulo_texto")]
    ok(any(u.get("subtitulo_ancla") for u in puestas),
       f"cada subtítulo corregido guarda la narración contra la que se corrigió ({len(puestas)})")
    pg.sin_errores("la ortografía de los subtítulos")
    pg.cerrar()


@escenario
def reparar_estilo_perdido(navegador, datos):
    """«Capas de luz en baño»: un vídeo cuyo estilo se volvió a guardar antes
    del 09-10-2026 apunta a imágenes que ya no se llaman así. La portada lo
    avisa y «Reparar» las vuelve a apuntar SIN regenerar nada y sin dejar
    nada obsoleto (re-sella solo lo que movió)."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    _r, antes = api.get(f"/api/proyectos/{pid}")
    estados_antes = {p.get("id"): p.get("estado") for p in (antes.get("pasos") or [])}
    carpeta = os.path.join(datos["proyectos"], "_fabrica", "banco", "presets", "pr_prueba")
    for nombre in os.listdir(carpeta):
        if nombre.startswith("00_00_"):
            os.rename(os.path.join(carpeta, nombre), os.path.join(carpeta, nombre[3:]))
    _r, d = api.get("/api/sistema/estilos-perdidos")
    ok(any(v.get("id") == pid and v.get("reparable") for v in d.get("videos") or []),
       "el vídeo con las imágenes de estilo perdidas se detecta (y se puede reparar)")
    pg = Pagina(navegador, datos)
    pg.js("elegirCliente(''); recordarVideoLight(''); await cargarGaleriaLight(true); irALight('galeria');")
    ok(pg.esperar(".aviso-perdidos button", "Reparar", 15), "la portada lo avisa con «Reparar»")
    pg.captura("17_estilo_perdido", entera=False)
    pg.pulsar(".aviso-perdidos button", "Reparar")
    ok(pg.esperar("#toast", "reparado", 20) or any("reparado" in a for a in pg.avisos()),
       f"«Reparar» lo repara ({pg.avisos()[-2:]!r})")
    _r, d = api.get("/api/sistema/estilos-perdidos")
    ok(not any(v.get("id") == pid for v in d.get("videos") or []), "y deja de salir como perdido")
    _r, despues = api.get(f"/api/proyectos/{pid}")
    estados = {p.get("id"): p.get("estado") for p in (despues.get("pasos") or [])}
    cambiados = {k: (estados_antes.get(k), v) for k, v in estados.items() if estados_antes.get(k) != v}
    ok(not cambiados, f"sin dejar NADA obsoleto: ni imágenes que volver a pagar ({cambiados})")
    pg.sin_errores("reparar el estilo perdido")
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
        datos["api"].libre(datos["video"])
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


@escenario
def coste_en_detalle(navegador, datos):
    """Pulsar el coste de arriba enseña TODO lo gastado del vídeo, desglosado;
    y la ficha del estilo, lo que costó hacerlo (11-10-2026)."""
    api, pid = datos["api"], datos["video"]
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'guion'; pintarLight();")
    ok(pg.esperar("button.coste-light", None, 15), "el coste de arriba se puede pulsar")
    pg.pulsar("button.coste-light")
    ok(pg.esperar("#coste-video", "Coste del vídeo", 15), "y abre el coste del vídeo")
    texto = pg.p.locator("#coste-video").inner_text()
    for parte in ("Imágenes nuevas", "Imágenes rehechas", "Personajes", "Voz", "Claude",
                  "Música", "Efectos", "Su estilo"):
        ok(parte in texto, f"con «{parte}»")
    _r, total = api.get(f"/api/proyectos/{pid}/coste")
    ok(f"{float(total.get('total_usd') or 0):.2f}" in texto or f"{float(total.get('total_usd') or 0):.3f}" in texto,
       f"y el mismo total que la cabecera ({total.get('total_usd')})")
    pg.captura("21_coste_del_video", entera=False)
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(400)
    ok(not pg.visible("#coste-video"), "Escape lo cierra")
    pg.js(f"irALight('preset', {{ abierto: '{datos['preset']}', feedback: {{}} }});")
    ok(pg.esperar(".light-preset button", "Lo que costó", 15), "la ficha del estilo tiene «Lo que costó»")
    pg.pulsar(".light-preset button", "Lo que costó")
    ok(pg.esperar("#coste-video", "Coste del estilo", 15), "y abre lo que costó el estilo")
    pg.p.keyboard.press("Escape")
    pg.sin_errores("el coste en detalle")
    pg.cerrar()


@escenario
def descargar_por_partes(navegador, datos):
    """«Por partes…» junto a «Descargar»: el vídeo sin música, un audio suelto
    o todo en un ZIP, sin tocar el proyecto (11-10-2026)."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    _r, antes = api.get(f"/api/proyectos/{pid}")
    estados_antes = {p.get("id"): p.get("estado") for p in antes.get("pasos") or []}
    if estados_antes.get("render") != "listo":
        # con cambios sin montar se pide montar antes (409): se monta
        r, d = api.post(f"/api/proyectos/{pid}/exportar", {"que": "zip"})
        ok(r.status_code == 409, f"con cambios sin montar, descargar por partes pide montar antes ({r.status_code})")
        r, d = api.post(f"/api/proyectos/{pid}/generar", {"tanda": "render", "modo": "pendientes"})
        api.esperar(d.get("trabajo_id") or (d.get("trabajo") or {}).get("id"), 600)
        api.libre(pid)
        _r, antes = api.get(f"/api/proyectos/{pid}")
        estados_antes = {p.get("id"): p.get("estado") for p in antes.get("pasos") or []}
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar("button", "Por partes", 20), "junto a «Descargar» está «Por partes…»")
    pg.pulsar("button", "Por partes")
    ok(pg.esperar("#coste-video", "Descargar por partes", 10), "y abre la descarga por partes")
    pg.p.locator("#coste-video label", has_text="Música").locator("input").uncheck()
    pg.p.wait_for_timeout(300)
    ok("voz + efectos" in pg.p.locator("#coste-video").inner_text(), "dice lo que va a llevar")
    with pg.p.expect_download(timeout=180000) as bajada:
        pg.pulsar("#coste-video button", "Descargar el vídeo")
    ruta = bajada.value.path()
    nombre = bajada.value.suggested_filename
    ok(nombre.endswith("video_voz-efectos.mp4"), f"baja el vídeo sin música ({nombre})")
    salida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                             "-of", "csv=p=0", ruta], capture_output=True, text=True).stdout.split()
    ok("video" in salida and "audio" in salida, f"con imagen y sonido ({salida})")
    with pg.p.expect_download(timeout=180000) as bajada:
        pg.pulsar("#coste-video button", "Efectos")
    ok(bajada.value.suggested_filename.endswith("efectos.wav"), "y un audio suelto, en WAV")
    _r, despues = api.get(f"/api/proyectos/{pid}")
    estados = {p.get("id"): p.get("estado") for p in despues.get("pasos") or []}
    ok(estados == estados_antes, f"sin tocar el proyecto ({estados})")
    pg.captura("22_por_partes", entera=False)
    pg.sin_errores("descargar por partes")
    pg.cerrar()


@escenario
def salir_y_cada_video_lo_suyo(navegador, datos):
    """Lo que el dueño encontró el 11-10-2026 por la noche:

    - dentro de un vídeo no había forma de volver al inicio;
    - el montaje de un vídeo bloqueaba (y enseñaba su barra en) todos los demás;
    - «Ver cómo quedó» no hacía nada desde el Guion;
    - y no había forma de volver a una versión anterior desde la pantalla.
    """
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    r, d = api.post(f"/api/presets-light/{datos['preset']}/video", {
        "nombre": "Otro vídeo de prueba", "duracion_objetivo_s": 30,
        "material": "Un segundo vídeo, para comprobar que cada uno va a lo suyo."})
    otro = (d.get("proyecto") or {}).get("id") or ""
    ok(r.status_code == 201 and otro, f"se crea un segundo vídeo ({r.status_code})")
    pg = Pagina(navegador, datos)

    # 1. LAS TRES SALIDAS AL INICIO
    salidas = (("«‹ Mis vídeos»", lambda: pg.pulsar(".migas-video button", "Mis vídeos")),
               ("«Inicio» en la barra de abajo", lambda: pg.pulsar(".nav-light button", "Inicio")),
               ("el logo", lambda: pg.p.click("#cabecera .marca")))
    for vista in ("guion", "previa", "video"):
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = '{vista}'; pintarLight();")
        ok(pg.esperar(".migas-video button", "Mis vídeos", 15),
           f"en la pantalla «{vista}» del vídeo está «‹ Mis vídeos»")
    for como, accion in salidas:
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
        pg.esperar(".migas-video", None, 15)
        accion()
        pg.p.wait_for_timeout(1200)
        ok(pg.p.evaluate("() => APP.light.vista !== 'elegido' && !APP.light.video.pid"),
           f"{como} saca del vídeo al inicio")
    pg.captura("19_inicio", entera=False)

    # 2. CADA VÍDEO CON SU TRABAJO
    # algo que montar sin dibujar: un subtítulo corregido (gratis)
    api.post(f"/api/proyectos/{pid}/ortografia/aplicar", {"cambios": {"S001": "Texto corregido de prueba."}})
    r, d = api.post(f"/api/proyectos/{pid}/generar", {"tanda": "render", "modo": "pendientes"})
    tid = d.get("trabajo_id") or (d.get("trabajo") or {}).get("id")
    ok(r.status_code == 202 and tid, f"se monta el primer vídeo ({r.status_code})")
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar("button", "Parar", 20), "en el vídeo que se monta se ve su barra")
    pg.js(f"await abrirVideoLight('{otro}');")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate("() => trabajoVideoLight() === null"),
       "en otro vídeo, el montaje del primero no cuenta como suyo")
    ok(not pg.visible("button", "Parar"), "ni enseña su barra ni su «Parar»")
    pg.captura("20_otro_video_mientras_se_monta", entera=False)
    fin = api.esperar(tid, 600)
    pg.p.wait_for_timeout(2500)
    ok(fin.get("estado") == "listo", f"el montaje del primero termina ({fin.get('estado')})")
    ok(pg.p.evaluate("() => APP.light.video.pid") == otro,
       "y al terminar NO te saca del vídeo que estás mirando")

    # 3. «VER CÓMO QUEDÓ» DESDE EL GUION
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'guion'; pintarLight();")
    pg.p.evaluate("() => irAlMomentoDeLaNota({plano: 'S002', pantalla: 'imagenes'})")
    pg.p.wait_for_timeout(3000)
    ok(pg.p.evaluate("() => APP.light.video.vista === 'previa' && "
                     "((PREVIA.ficha || {}).escenas || [])[PREVIA.i].id === 'S002'"),
       "«Ver cómo quedó» desde el Guion lleva a Imágenes con ese plano a la vista")

    # 4. VOLVER A LA VERSIÓN ANTERIOR (de las imágenes: gratis)
    _r, ficha = api.get(f"/api/proyectos/{pid}/pasos/assets")
    if len(ficha.get("versiones") or []) < 2:
        # solo (con --solo) el vídeo tiene una: se rehace una imagen para tener dos
        r, d = api.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                        {"unidades": ["escena:S002"], "rehacer": True})
        api.esperar(d.get("trabajo_id"), 300)
        _r, ficha = api.get(f"/api/proyectos/{pid}/pasos/assets")
    versiones = sorted((v.get("n") for v in ficha.get("versiones") or []), reverse=True)
    activa = next((v.get("n") for v in ficha.get("versiones") or [] if v.get("activa")), None)
    if len(versiones) >= 2 and activa:
        anterior = max(n for n in versiones if n < activa)
        _r, antes = api.get(f"/api/proyectos/{pid}")
        voz_antes = {p.get("id"): p.get("estado") for p in antes.get("pasos") or []}.get("voz")
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
        ok(pg.esperar(".bloque-versiones summary", "Versiones de las imágenes", 15),
           "en Imágenes está la lista de versiones")
        pg.pulsar(".bloque-versiones summary")
        pg.pulsar(".bloque-versiones button", "Volver a la versión anterior")
        pg.p.wait_for_timeout(2500)
        _r, ficha2 = api.get(f"/api/proyectos/{pid}/pasos/assets")
        nueva = next((v.get("n") for v in ficha2.get("versiones") or [] if v.get("activa")), None)
        igual_n = nueva == anterior
        ok(igual_n, f"«Volver a la versión anterior» activa la v{anterior} (está la v{nueva})")
        ok(any("v" in d and ("gratis" in d or "sin pagar" in d) for d in pg.dialogos[-1:]),
           f"y antes avisa de lo que pasa ({pg.dialogos[-1:]})")
        _r, despues = api.get(f"/api/proyectos/{pid}")
        estados = {p.get("id"): p.get("estado") for p in despues.get("pasos") or []}
        ok(estados.get("voz") == voz_antes, f"sin tocar la voz ({estados})")
        # y se deja como estaba, para los escenarios que vengan detrás
        api.post(f"/api/proyectos/{pid}/pasos/assets/revertir", {"version": activa})
    else:
        ok(False, f"el vídeo de prueba tiene al menos dos versiones de imágenes ({versiones})")
    pg.sin_errores("salir al inicio y cada vídeo lo suyo")
    pg.cerrar()


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
        informe_de_cobertura(capturas)
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

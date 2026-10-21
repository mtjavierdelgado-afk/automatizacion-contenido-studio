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
    # UN FRENO PARA FFMPEG (arreglos-19oct): mientras exista `ffmpeg_lento` al
    # lado de los proyectos, el montaje final (el concat) tarda 20 s, que es lo
    # que da tiempo a pulsar «Parar». Sin el fichero es el ffmpeg de siempre.
    real = shutil.which("ffmpeg")
    if real and os.name != "nt":
        freno = os.path.join(binarios, "ffmpeg_con_freno")
        with open(freno, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/bash\n"
                     f'if [ -f "{os.path.join(base, "ffmpeg_lento")}" ] '
                     '&& [[ " $* " == *" concat "* ]]; then sleep 20; fi\n'
                     f'exec "{real}" "$@"\n')
        os.chmod(freno, os.stat(freno).st_mode | stat.S_IEXEC)
        env["ESTUDIO_FFMPEG"] = freno
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

    def __init__(self, navegador, datos, ancho=1300, alto=900, nombre="pantalla", entrada="crear"):
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
        # AL ENTRAR SE ABRE EL INICIO (diseno-crearia, 19-10-2026); los
        # escenarios empiezan en Crear, como siempre, con `?entrada=crear`
        self.p.goto(datos["url"] + ("/?entrada=crear" if entrada == "crear" else "/"))
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


def ir_al_paso(pg, nombre):
    """El carril de Crear (rediseño, 20-10-2026): pulsa el paso de ese nombre
    (Estilo, Encargo, Guion, Voz, Imágenes, Vídeo). Sustituye a la barra de
    pasos de abajo («.nav-light»). El paso en el que ya se está va apagado
    (no lleva a ningún sitio): entonces no hay nada que pulsar."""
    if pg.p.locator(".pasos-carril button.actual").filter(has_text=nombre).count():
        return
    pg.pulsar(".pasos-carril button", nombre)


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
def voz_del_estilo_se_guarda_entera(navegador, datos):
    """N4 de las notas de mejoras (13-10-2026): «los ajustes de voz no están
    sincronizando en la muestra en estilo». Dos fallos: tocar dos mandos de voz
    seguidos (en menos de los 0,9 s del autoguardado) guardaba solo el último,
    y la escucha se apuntaba con la clave de la ficha que tenía el botón al
    pintarse, no con la que el servidor había guardado: tras cambiar el ritmo
    (que mueve el aire de la voz) el play servía la muestra de antes."""
    api = datos["api"]
    pid = datos["preset"]

    def voz_guardada():
        return dict((ficha_guardada().get("datos") or {}).get("voz") or {})

    def ficha_guardada():
        _r, d = api.get("/api/presets-light")
        return next((p for p in d.get("presets") or [] if p.get("id") == pid), {})

    # EL ESTILO DE PRUEBA NO TRAE ni voz ni bloque de estilo, y uno de verdad
    # lleva los dos: sin fotogramas el ritmo no se puede guardar. Se le ponen
    # aquí y se le devuelve lo suyo al final, para no cambiar los demás escenarios.
    original = ficha_guardada()
    from PIL import Image                                    # noqa: PLC0415
    fotogramas = []
    for i in range(3):
        ruta = os.path.join(datos["base"], f"fotograma_voz_{i}.png")
        Image.new("RGB", (64, 48), (40 * i, 120, 200)).save(ruta)
        fotogramas.append(ruta)
    api.post("/api/presets-canal", {
        "tipo": "canal", "nombre": original.get("nombre"), "id": pid,
        "datos": dict(original.get("datos") or {},
                      estilo={"referencias": fotogramas},
                      voz={"voz_id": "voz-de-prueba"})})
    pg = Pagina(navegador, datos)
    escuchas = []

    def al_pedir(peticion):
        # en el momento en que la pantalla pide la muestra, lo que el servidor
        # tiene guardado es con lo que la va a sintetizar
        if peticion.method == "POST" and "/voz/previsualizar" in peticion.url:
            escuchas.append(voz_guardada())

    pg.p.on("request", al_pedir)
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{pid}' }});")
    # la ficha va en pestañas (rediseño de Crear): la voz está en «Cómo suena»
    pg.pulsar(".pestanas-estilo button", "Cómo suena")
    ok(pg.esperar(".bloque-voz button.escuchar", "Escuchar"), "la ficha enseña la voz con su «Escuchar»")
    pg.pulsar(".bloque-voz summary", "la velocidad")
    velocidad = pg.p.locator(".bloque-voz select").filter(
        has=pg.p.locator("option[value=fastest]")).first
    # DOS MANDOS SEGUIDOS, y el play enseguida: todo dentro de los 0,9 s
    velocidad.select_option("fastest")
    pg.p.locator(".bloque-voz button.mini", has_text="surprise").first.click()
    pg.p.locator(".bloque-voz button.escuchar", has_text="Escuchar").first.click()
    pg.p.wait_for_timeout(2500)
    guardada = voz_guardada()
    ok(guardada.get("velocidad") == "fastest" and guardada.get("emociones") == ["surprise"],
       f"tocar velocidad y color seguidos guarda LOS DOS (guardado: {guardada})")
    ok(len(escuchas) == 1 and escuchas[0].get("velocidad") == "fastest"
       and escuchas[0].get("emociones") == ["surprise"],
       f"y la escucha se pide con los dos ya guardados ({escuchas})")
    for _ in range(40):                         # que termine la síntesis
        if pg.p.evaluate("() => Object.keys(APP.light.escuchas || {}).length > 0"):
            break
        pg.p.wait_for_timeout(500)
    claves = pg.p.evaluate(f"() => [Object.keys(APP.light.escuchas || {{}}), "
                           f"claveEscucha(fichaLight('{pid}'), '')]")
    ok(claves[1] in claves[0],
       f"la muestra queda apuntada con la clave de lo GUARDADO -- {claves}")

    # EL RITMO MUEVE EL AIRE DE LA VOZ en el servidor, sin repintar la voz
    pg.pulsar(".pestanas-estilo button", "Ritmo")
    antes = voz_guardada().get("hueco_minimo")
    barra = pg.p.locator("input.ritmo").first
    actual = int(barra.input_value())
    maximo = int(barra.get_attribute("max") or 0)
    otro = 0 if actual != 0 else maximo
    barra.evaluate("(b, v) => { b.value = String(v); b.dispatchEvent(new Event('input')); }", otro)
    despues = antes
    for _ in range(30):                         # el PUT sale a los 0,9 s
        pg.p.wait_for_timeout(500)
        despues = voz_guardada().get("hueco_minimo")
        if despues is not None and despues != antes:
            break
    ok(despues is not None and despues != antes,
       f"cambiar el ritmo cambia el aire guardado de la voz ({antes} -> {despues})"
       f" -- aviso: {pg.toast()[:150]!r}")
    pg.pulsar(".pestanas-estilo button", "Cómo suena")
    pg.p.locator(".bloque-voz button.escuchar", has_text="Escuchar").first.click()
    pg.p.wait_for_timeout(2500)
    ok(len(escuchas) == 2,
       "y el «Escuchar» de después pide una muestra NUEVA, no sirve la de antes"
       f" ({len(escuchas)} peticiones)")
    pg.p.remove_listener("request", al_pedir)
    api.post("/api/presets-canal", {"tipo": "canal", "nombre": original.get("nombre"),
                                    "id": pid, "datos": original.get("datos") or {}})
    pg.sin_errores("la voz del estilo")
    pg.cerrar()


@escenario
def del_video_a_su_estilo_y_de_vuelta(navegador, datos):
    """N3 de las notas de mejoras (13-10-2026): «cuando regreso a estilos en
    proyecto avanzado me bota al menú». Desde el rediseño de Crear (20-10-2026)
    el estilo de un vídeo es su paso «Estilo» del carril: se abre su ficha sin
    salir del vídeo, se vuelve por el carril, regenerar el estilo no pierde el
    camino, «‹ Tus proyectos» es la única salida, y si el estilo ya no está el
    paso lo dice y ofrece cambiarlo, sin sacar del vídeo."""
    pid = datos["video"]
    pg = Pagina(navegador, datos)
    pg.js("await cargarGaleriaLight(true); elegirCliente(''); irALight('galeria');")
    ok(pg.visible("h2", "Tus proyectos"), "se empieza en la portada de proyectos")
    ok(pg.esperar(".video-light button.abrir", "Padres vs hijos"),
       "el vídeo de prueba sale en «Últimos vídeos»")
    pg.pulsar(".video-light button.abrir", "Padres vs hijos")
    pg.esperar(".pasos-carril button", "Estilo")
    pg.p.wait_for_timeout(1000)
    ir_al_paso(pg, "Estilo")
    ok(pg.esperar(".light-preset .light-cab h2", "Estado Play Matriz"),
       "«Estilo» del carril abre el estilo del vídeo")
    ok(pg.visible(".paso-carril.actual", "Estilo") and pg.visible(".cab-video", "Padres vs hijos"),
       "sin salir del vídeo: el carril y la cabecera del vídeo siguen ahí")
    ok(pg.visible(".bloque-light", "Su estilo"), "y arriba, «Su estilo» (lo que el vídeo tiene del estilo)")
    ir_al_paso(pg, "Encargo")
    pg.p.wait_for_timeout(1000)
    ok(pg.p.evaluate(f"() => APP.light.vista === 'elegido' && APP.light.video.pid === '{pid}'"),
       "el carril vuelve a ese vídeo")
    ir_al_paso(pg, "Estilo")
    # LA SALIDA VUELVE AL PROYECTO DEL VÍDEO, no a la portada (N3: «me bota
    # al menú»; revisión del rediseño, 21-10-2026), y lleva su nombre
    ok(pg.esperar(".salida-crear", "‹ Estado Play", 10),
       "dentro del vídeo, la salida lleva el nombre de su proyecto («‹ Estado Play»)")
    pg.pulsar(".salida-crear", "Estado Play")
    pg.p.wait_for_timeout(1200)
    ok(not pg.visible("h2", "Tus proyectos") and pg.visible("h2", "Estado Play")
       and pg.p.evaluate("() => !APP.light.video.pid"),
       "«‹ Estado Play» enseña los estilos del proyecto del vídeo, no «Tus proyectos» (y cierra el vídeo)")
    ok(pg.visible(".ficha-estilo", "Estado Play Matriz") or pg.visible(".tarjeta-estilo", "Estado Play Matriz"),
       "con el estilo del vídeo entre ellos")
    pg.captura("05_salida_desde_el_estilo", entera=False)
    pg.pulsar(".salida-crear", "Tus proyectos")
    pg.p.wait_for_timeout(800)
    ok(pg.visible("h2", "Tus proyectos"), "y desde el proyecto, «‹ Tus proyectos» lleva a la portada")
    # REGENERAR EL ESTILO pasa por «generando» y vuelve a la ficha: el camino
    # de vuelta al vídeo tiene que seguir ahí (sin gastar: solo las vistas)
    pg.js(f"await abrirVideoLight('{pid}');")
    ir_al_paso(pg, "Estilo")
    pg.js(f"irALight('generando', {{ plan: null, abierto: '{datos['preset']}' }}); "
          f"irALight('preset', {{ abierto: '{datos['preset']}', taller: null, feedback: {{}} }});")
    ok(pg.esperar(".paso-carril.actual", "Estilo", 10),
       "después de regenerar el estilo sigue dentro del vídeo, en su paso Estilo")
    # UN ESTILO QUE YA NO ESTÁ: lo dice y te quedas en el vídeo
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.estilo = 'estilo_que_no_existe'; pintarLight();")
    ir_al_paso(pg, "Estilo")
    ok(pg.p.evaluate(f"() => APP.light.video.pid === '{pid}' && pasoDelCarril() === 'estilo'"),
       "si el estilo del vídeo no está, «Estilo» no saca del vídeo")
    ok(pg.esperar(".light-preset .caja-info", "ya no está", 10), "y lo dice")
    ok(pg.esperar(".cambio-de-estilo select", None, 10), "y ofrece «Cambiar de estilo…»")
    pg.sin_errores("del vídeo a su estilo y de vuelta")
    pg.cerrar()


@escenario
def encargo_del_video(navegador, datos):
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{datos['video']}');")
    ir_al_paso(pg, "Encargo")
    ok(pg.esperar(".ajustes-montaje"), "el Encargo enseña los ajustes del montaje")
    for nombre in ("Música", "Subtítulos", "Logo", "Efectos", "Movimiento y efectos"):
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
    pg.p.locator(".fila-ajuste").filter(has_text="✨ Efectos").locator("button", has_text="Cambiar").click()
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
    ir_al_paso(pg, "Imágenes")
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
    # ESPERANDO, no mirando en el instante: la pastilla y el motivo llegan en
    # repintados distintos, y con la máquina cargada el motivo tardaba un
    # poco más (falló así una vez el 17-10; repetida sola, pasaba)
    ok(pg.esperar(".nota-imagen .nota-error", "filtro de seguridad", 15), "con el motivo en claro")
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
    ok(pg.visible(".barra-accion button", "Aplicar 2 notas · 1 imagen"),
       "dos notas del mismo plano se pagan como UNA imagen («Aplicar 2 notas · 1 imagen»)")
    pg.p.locator(".repaso-notas").first.scroll_into_view_if_needed()
    pg.captura("10_dos_notas_un_plano", entera=False)
    pg.pulsar(".barra-accion button", "Aplicar 2 notas")
    fin = time.time() + 120
    juntas = pg.p.locator(".nota-fila").filter(has_text="más luz")
    otra = pg.p.locator(".nota-fila").filter(has_text="sofá")
    while time.time() < fin and not (
            "hecha" in juntas.first.inner_text().lower() and "hecha" in otra.first.inner_text().lower()):
        pg.p.wait_for_timeout(700)
    ok("hecha" in juntas.first.inner_text().lower() and "hecha" in otra.first.inner_text().lower(),
       "y al rehacerla, las dos notas quedan hechas con esa sola imagen")
    # el Encargo no arrastra nada de esto
    ir_al_paso(pg, "Encargo")
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
    pg.pulsar(".pestanas-estilo button", "Cómo se cuenta")
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
    pg.js(f"await cargarGaleriaLight(true); irALight('galeria'); irALight('preset', {{ abierto: '{datos['preset']}' }});")
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
    pg.p.locator(".fila-ajuste").filter(has_text="💬 Subtítulos").locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(800)
    color = pg.p.locator(".editor-ajuste input[type=color]").first
    ok(color.count() == 1, "los subtítulos dejan elegir el color")
    color.evaluate("x => { x.value = '#ff8800'; x.dispatchEvent(new Event('change', { bubbles: true })); }")
    ok(pg.esperar(".editor-ajuste button", "Quitar mi color", 15), "elegido, sale «Quitar mi color»")
    pg.pulsar(".editor-ajuste button", "Quitar mi color")
    ok(pg.esperar(".editor-ajuste", "el del estilo", 15), "y quitarlo vuelve al del estilo")
    pg.sin_trabajo(300)
    # PARTIR UN BLOQUE DEL GUION (se abre y se cancela: partir regraba la voz)
    ir_al_paso(pg, "Guion")
    pg.p.wait_for_timeout(1200)
    # los mandos de cada bloque se ven siempre (rediseño de Crear)
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
    """Pulsa «Montar el vídeo» en la barra de acción del paso Vídeo (si lo
    ofrece: con el vídeo al día la barra dice «Enviar a Publicar ›») y espera."""
    ir_al_paso(pg, "Vídeo")
    pg.p.wait_for_timeout(1500)
    boton = pg.p.locator(".barra-accion button").filter(has_text="Montar el vídeo").first
    if boton.count() and boton.is_enabled():
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
    ir_al_paso(pg, "Imágenes")
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
    ir_al_paso(pg, "Vídeo")
    pg.p.wait_for_timeout(1500)
    ok(pg.visible(".caja-aviso", "ANTES de tus últimos cambios"),
       "el Vídeo dice que su MP4 es de antes de las imágenes rehechas (sin recargar)")
    ok(pg.visible(".barra-accion .estado", "Vídeo obsoleto"), "con su «Vídeo obsoleto» en la barra")
    ok(pg.visible(".paso-carril", "Vídeo obsoleto"), "y en el carril")
    src_video = pg.p.locator("video").first.get_attribute("src") or ""
    boton = pg.p.locator(".barra-accion button").filter(has_text="Montar el vídeo").first
    ok(boton.is_enabled(), "y «Montar el vídeo» se puede pulsar")
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
    ir_al_paso(pg, "Imágenes")
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
def imagenes_en_otra_calidad(navegador, datos):
    """D6 (auditoria del coste, 15-10-2026): cambiar la calidad de un video con
    imagenes hechas NO las redibuja. Decision del dueño: «que lo diga y
    pregunte». Las diapositivas dicen «N imágenes siguen en otra calidad» con
    su precio; SIN PULSAR no se lanza nada (ni cancelando el confirm), y al
    confirmar se rehacen SOLO esas, en la calidad nueva."""
    pid = datos["video"]
    api = datos["api"]

    def igual(obtenido, esperado, mensaje):
        return ok(obtenido == esperado, f"{mensaje} (esperaba {esperado!r}, llegó {obtenido!r})")
    api.libre(pid)
    _r, ficha = api.get(f"/api/proyectos/{pid}/pasos/assets")
    calidad = (ficha.get("params") or {}).get("calidad") or "low"
    # C3: lo que queda por pagar cuenta lo que la tanda VA A REDIBUJAR. Con un
    # plano sucio (su nota cambio) la tanda se lo pide a p6 y lo paga aunque
    # su PNG exista; decia «0 imágenes por generar»
    params_antes = ficha.get("params") or {}
    unidades = dict(params_antes.get("unidades") or {})
    unidades["escena:S002"] = dict(unidades.get("escena:S002") or {},
                                   feedback="que se vea el puerto")
    api.put(f"/api/proyectos/{pid}/pasos/assets/params", {"params": {"unidades": unidades}})
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=video")
    coste = plan.get("coste") or {}
    igual(coste.get("imagenes_por_generar"), 1,
          "con UN plano sucio, «Poner al día» cuenta esa imagen por pagar")
    api.put(f"/api/proyectos/{pid}/pasos/assets/params",
            {"params": params_antes, "reemplazar": True})
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=video")
    igual((plan.get("coste") or {}).get("imagenes_por_generar"), 0,
          "y quitada la nota, ninguna")
    nueva = "medium" if calidad != "medium" else "high"
    r, _d = api.put(f"/api/proyectos/{pid}/pasos/assets/params", {"params": {"calidad": nueva}})
    ok(r.status_code == 200, f"la calidad del vídeo pasa de {calidad} a {nueva}")
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=video")
    otra = (plan.get("coste") or {}).get("otra_calidad") or {}
    ok(otra.get("imagenes", 0) > 0 and otra.get("por_calidad", {}).get(calidad),
       f"el plan de las imágenes dice cuántas siguen en {calidad}: {otra}")
    ok(abs(float(otra.get("usd") or 0) - otra.get("imagenes", 0)
           * float(plan["coste"]["usd_por_imagen"])) < 0.01,
       "con su precio: cuántas por lo que cuesta una en la calidad nueva")
    ruta_coste = os.path.join(datos["proyectos"], pid, "coste.jsonl")

    def imagenes_pagadas():
        try:
            with open(ruta_coste, encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if '"openai"' in l]
        except OSError:
            return []
    antes = len(imagenes_pagadas())
    pg = Pagina(navegador, datos)
    pedidas = []
    pg.p.on("request", lambda q: pedidas.append(q.url)
            if q.method == "POST" and ("/imagenes/calidad" in q.url or q.url.endswith("/generar"))
            else None)
    pg.js(f"await abrirVideoLight('{pid}');")
    ir_al_paso(pg, "Imágenes")
    ok(pg.esperar(".otra-calidad", "siguen en calidad", 15),
       "las diapositivas dicen que hay imágenes en otra calidad")
    boton = pg.p.locator(".otra-calidad button").first
    ok(boton.count() == 1 and "$" in (boton.inner_text() or ""),
       f"con un botón que dice lo que cuesta: «{boton.inner_text() if boton.count() else ''}»")
    pg.captura("otra_calidad", entera=False)
    pg.p.wait_for_timeout(3000)
    igual(pedidas, [], "SIN PULSAR no se lanza nada")
    pg.aceptar = False
    pg.pulsar(".otra-calidad button")
    pg.p.wait_for_timeout(1500)
    ok(pg.dialogos and "$" in pg.dialogos[-1],
       f"pulsar pide confirmación con el precio: {pg.dialogos[-1:] }")
    igual(pedidas, [], "y si se cancela, tampoco se lanza nada")
    igual(len(imagenes_pagadas()), antes, "ni se paga ninguna imagen")
    pg.aceptar = True
    pg.pulsar(".otra-calidad button")
    pg.p.wait_for_timeout(1500)
    igual(len([u for u in pedidas if "/imagenes/calidad" in u]), 1,
          "al confirmar se lanza UNA petición de rehacerlas")
    ok(pg.sin_trabajo(400), "y se rehacen")
    pg.p.wait_for_timeout(2000)
    nuevas = imagenes_pagadas()[antes:]
    unidades = sorted({e.get("unidad") for e in nuevas})
    igual(len(nuevas), otra["imagenes"], f"se pagan exactamente las {otra['imagenes']} ofrecidas")
    ok(all(str(u).startswith("escena:") for u in unidades),
       f"todas de plano, ninguna hoja de reparto ({unidades[:4]}...)")
    igual(sorted({(e.get("detalle") or {}).get("calidad") for e in nuevas}), [nueva],
          f"y todas en {nueva}")
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=video")
    ok(not (plan.get("coste") or {}).get("otra_calidad"),
       "después ya no queda ninguna en otra calidad")
    ok(not pg.esperar(".otra-calidad", None, 6), "y el aviso se va")
    pg.sin_errores("imágenes en otra calidad")
    # se deja el video montado al dia para los escenarios que vienen detras
    ok(_montar_desde_video(pg), "el vídeo se vuelve a montar con las imágenes nuevas")
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
    ir_al_paso(pg, "Imágenes")
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
    ir_al_paso(pg, "Estilo")
    ok(pg.esperar(".light-preset h2", "Estado Play Matriz"),
       "«Estilo» desde un vídeo abre el estilo con el que se hizo")
    ok(pg.visible(".pasos-carril button", "Imágenes"), "con el carril para volver al vídeo")
    pg.captura("12_estilos_desde_el_video", entera=False)
    ir_al_paso(pg, "Imágenes")
    ok(pg.p.evaluate("() => APP.light.vista === 'elegido' && APP.light.video.pid") == pid,
       "y vuelve a ese vídeo")
    pg.sin_trabajo()
    # «REVISAR» EN EL ENCARGO, CON LA PANTALLA REPINTÁNDOSE MIENTRAS
    ir_al_paso(pg, "Encargo")
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
    # «SIRVE» CON PROBLEMAS (N5 de las notas de mejoras, 13-10-2026): la
    # revision listaba mejoras y no salia ningun boton para aplicarlas
    area = pg.p.locator(".bloque-light").filter(has_text="El material").first.locator("textarea").first
    area.fill(original + " BORRADOR")
    area.dispatch_event("input")
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    bloque.locator("button", has_text="Revisar").first.click()
    ok(pg.esperar(".bloque-light .revision-campo", "dos cosas que mejorar", 60),
       "la revisión «Sirve» con problemas se pinta")
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    ok(bloque.locator("button", has_text="Aplicar la versión sugerida").count() == 1,
       "«Sirve» con problemas también ofrece aplicar la versión sugerida")
    ok(bloque.locator("button", has_text="Aplicar esta mejora").count() == 1,
       "y un «Aplicar» para la mejora cuyo trozo está en el campo")
    ok(bloque.locator(".revision-campo", has_text="ya no está tal cual").count() == 1,
       "y dice que el trozo de la otra mejora no está en el campo")
    if bloque.locator("button", has_text="Aplicar esta mejora").count():
        bloque.locator("button", has_text="Aplicar esta mejora").first.click()
    pg.p.wait_for_timeout(2500)
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    valor = bloque.locator("textarea").first.input_value()
    ok("BORRADOR" not in valor and valor.endswith("versión final"),
       f"aplicar la mejora cambia SOLO ese trozo del material ({valor[-60:]!r})")
    ok(bloque.locator(".revision-campo", has_text="Mejora aplicada").count() == 1,
       "y la mejora queda marcada como aplicada")
    # SE GUARDA como cualquier edicion del encargo
    _r, d = api.get(f"/api/proyectos/{pid}")
    ok("versión final" in json.dumps(d, ensure_ascii=False),
       "y la mejora aplicada queda guardada en el proyecto")
    # SIN TEXTO ENTERO, QUE LO DIGA: la misma revision sin «sugerida»
    pg.js("""REVISION_VIVA.forEach(v => { if (v.resultado && v.resultado.resumen
               === 'Sirve, aunque hay dos cosas que mejorar.') v.resultado.sugerida = ''; });
             pintarLight();""")
    bloque = pg.p.locator(".bloque-light").filter(has_text="El material").first
    ok(bloque.locator(".revision-campo", has_text="no ha propuesto un texto entero").count() == 1,
       "con problemas y sin texto entero, dice que no hay versión entera que aplicar")
    pg.captura("13b_sirve_con_problemas", entera=False)
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
    ir_al_paso(pg, "Guion")
    ok(pg.esperar("body", "B001"), "el Guion enseña los bloques")
    ir_al_paso(pg, "Vídeo")
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
def cancelar_y_doble_toque_en_el_taller(navegador, datos):
    """Lo que vio el dueño el 18-10-2026: cancelar un «Rehacer» y, al volver a
    pulsar, «este estilo se está generando». Tres cosas de pantalla:

      - «Regenerar» con la petición en camino se apaga y dice «Leyendo tu
        corrección…»: el segundo toque no sale (antes salían dos peticiones);
      - «Cancelar» pasa a «Cancelando…», apagado, EN EL ACTO;
      - un 409 que trae el trabajo que ocupa el taller se engancha a él.

    El servidor se sustituye con `route`: lo que se mira es la pantalla (el
    servidor lo comprueba `prueba_api.probar_cancelar_en_el_taller`)."""
    import json as _json                                      # noqa: PLC0415
    pg = Pagina(navegador, datos)
    preset = datos["preset"]
    pedidas = []

    def regenerar(ruta):
        pedidas.append(ruta.request.url)
        ruta.fulfill(status=409, content_type="application/json",
                     body=_json.dumps({"error": "ya se está preparando un cambio de "
                                                "este estilo", "trabajo_id": "",
                                       "preparando": True}))
    pg.p.route("**/api/presets-light/*/regenerar", regenerar)
    pg.js(f"await cargarGaleriaLight(true); irALight('preset', {{ abierto: '{preset}' }});"
          "APP.light.feedback = { tono: 'más cercano' }; repintarPieDeEstilo();")
    ok(pg.esperar(".pie-light button", "Regenerar"), "con algo pedido sale «Regenerar»")
    # la petición tarda (Claude lee la frase): se retiene un momento
    pg.p.unroute("**/api/presets-light/*/regenerar")

    def regenerar_lento(ruta):
        pedidas.append(ruta.request.url)
        estado["retenida"] = ruta
    estado = {}
    pg.p.route("**/api/presets-light/*/regenerar", regenerar_lento)
    pg.p.evaluate("() => { const b = document.querySelector('.pie-light button.primario');"
                  " b.click(); b.click(); }")
    pg.p.wait_for_timeout(400)
    igual = (lambda a, b, m: ok(a == b, f"{m} (obtenido {a!r}, esperado {b!r})"))
    igual(len(pedidas), 1, "dos toques en «Regenerar» mandan UNA petición")
    ok(pg.visible(".pie-light button", "Leyendo tu corrección"),
       "y mientras va, el botón dice «Leyendo tu corrección…»")
    ok(pg.p.evaluate("() => !!document.querySelector('.pie-light button.primario').disabled"),
       "y está apagado")
    if estado.get("retenida"):
        estado["retenida"].fulfill(status=409, content_type="application/json",
                                   body=_json.dumps({"error": "ya se está preparando un "
                                                     "cambio de este estilo",
                                                     "trabajo_id": "", "preparando": True}))
    pg.p.wait_for_timeout(600)
    ok(pg.visible(".pie-light button", "Regenerar"), "al contestar, vuelve a «Regenerar»")
    pg.p.unroute("**/api/presets-light/*/regenerar")

    # ---- «Cancelando…» en el acto
    sondeos = {"n": 0}

    def cancelar(ruta):
        estado["cancelar"] = ruta              # el servidor tarda en contestar

    def ficha_falsa(ruta):
        sondeos["n"] += 1
        fin = sondeos["n"] > 6
        ruta.fulfill(status=200, content_type="application/json", body=_json.dumps({
            "id": "falso", "nombre": "preset_light", "estado": "cancelado" if fin else "ejecutando",
            "cancelando": not fin, "progreso": 0.3, "mensaje": "", "publico": "",
            "segundos": 12}))
    pg.p.route("**/api/trabajos/falso/cancelar", cancelar)
    pg.p.route("**/api/trabajos/falso/eventos", lambda ruta: ruta.abort())
    pg.p.route("**/api/trabajos/falso", ficha_falsa)
    pg.js(f"APP.trabajos[CLAVE_LIGHT] = {{ id: 'falso', estado: 'ejecutando', progreso: 0.3,"
          f" inicio: Date.now() - 82000 }};"
          f"irALight('generando', {{ plan: {{ segundos: 284, tareas: [] }}, abierto: '{preset}' }});")
    # «Cancelar» va en la barra de acción (rediseño de Crear, 20-10-2026)
    ok(pg.esperar(".pie-generando button", "Cancelar"), "la pantalla de rehacer tiene «Cancelar»")
    pg.p.evaluate("() => document.querySelector('.pie-generando button.peligro').click()")
    pg.p.wait_for_timeout(300)
    ok(pg.visible(".light-generando h2", "Cancelando"),
       "al pulsar, el título dice «Cancelando…» sin esperar al servidor")
    ok(pg.p.evaluate("() => { const b = document.querySelector('.pie-generando button.peligro');"
                     " return !!b && b.disabled && b.textContent.includes('Cancelando'); }"),
       "y el botón se apaga con «Cancelando…» (no se puede volver a pedir)")
    pg.captura("16b_cancelando")
    if estado.get("cancelar"):
        estado["cancelar"].fulfill(status=200, content_type="application/json",
                                   body=_json.dumps({"trabajo_id": "falso",
                                                     "cancelacion_pedida": True,
                                                     "estado": "ejecutando"}))
    pg.p.wait_for_timeout(500)

    # ---- un 409 que trae el trabajo: la pantalla se engancha a él
    sondeos["n"] = 0
    pg.js(f"APP.trabajos[CLAVE_LIGHT] = null; soltarSeguimiento(CLAVE_LIGHT);"
          f"irALight('preset', {{ abierto: '{preset}' }});"
          "APP.light.feedback = { tono: 'más cercano' }; repintarPieDeEstilo();")
    pg.p.route("**/api/presets-light/*/regenerar", lambda ruta: ruta.fulfill(
        status=409, content_type="application/json", body=_json.dumps({
            "error": "se está cancelando lo anterior: termina en unos segundos",
            "trabajo_id": "falso", "cancelando": True, "segundos": 30})))
    pg.pulsar(".pie-light button", "Regenerar")
    ok(pg.esperar(".light-generando h2", "Cancelando", 5),
       "un 409 con su trabajo lleva a ese trabajo, diciendo «Cancelando…»")
    fin = time.time() + 30
    while time.time() < fin and pg.p.evaluate("() => APP.light.vista") == "generando":
        pg.p.wait_for_timeout(500)
    ok(pg.p.evaluate("() => APP.light.vista") == "preset",
       "y cuando el trabajo acaba cancelado, vuelve a la ficha")
    ok(any("cancelado" in a for a in pg.p.evaluate("() => window.__avisos || []")),
       "con el aviso «cancelado», no un error")
    pg.p.unroute("**/api/presets-light/*/regenerar")
    pg.js("APP.light.feedback = {};")

    # ---- las láminas: un 409 se queda en la ficha, y se avisa UNA vez
    avisos_antes = len(pg.p.evaluate("() => window.__avisos || []"))
    pg.p.route("**/api/presets-light/*/laminas", lambda ruta: ruta.fulfill(
        status=409, content_type="application/json", body=_json.dumps({
            "error": "ya se está preparando un cambio de este estilo",
            "trabajo_id": "", "preparando": True}))
        if ruta.request.method == "POST" else ruta.fallback())
    pg.js(f"await accionLaminas(fichaLight('{preset}'), {{ accion: 'quitar', lamina: 'cara' }});")
    avisos = pg.p.evaluate("() => window.__avisos || []")[avisos_antes:]
    igual(sum(1 for a in avisos if "preparando un cambio" in a), 1,
          "un 409 de las láminas sin trabajo avisa UNA vez (antes: dos)")
    pg.p.unroute("**/api/presets-light/*/laminas")
    sondeos["n"] = 0
    pg.p.route("**/api/presets-light/*/laminas", lambda ruta: ruta.fulfill(
        status=409, content_type="application/json", body=_json.dumps({
            "error": "este estilo se está generando", "trabajo_id": "falso",
            "cancelando": False, "segundos": 3}))
        if ruta.request.method == "POST" else ruta.fallback())
    pg.js(f"APP.trabajos[CLAVE_LIGHT] = null; soltarSeguimiento(CLAVE_LIGHT);"
          f"await accionLaminas(fichaLight('{preset}'), {{ accion: 'quitar', lamina: 'cara' }});")
    igual(pg.p.evaluate("() => APP.light.vista"), "preset",
          "un 409 de las láminas con su trabajo NO salta a «generando»: se sigue ahí")
    igual(pg.p.evaluate("() => (APP.light.trabajoLaminas || {}).id || ''"), "falso",
          "y se sigue en las propias láminas")
    pg.p.unroute("**/api/presets-light/*/laminas")
    fin = time.time() + 20
    while time.time() < fin and pg.p.evaluate("() => !!APP.light.trabajoLaminas"):
        pg.p.wait_for_timeout(400)

    # ---- con una lámina en camino, el botón no dice «Leyendo tu corrección…»
    pg.js(f"irALight('preset', {{ abierto: '{preset}' }});"
          "APP.light.feedback = { tono: 'más cercano' }; APP.light.lanzando = 'laminas';"
          "repintarPieDeEstilo();")
    ok(not pg.visible(".pie-light button", "Leyendo tu corrección"),
       "con una lámina en camino, «Regenerar» no dice «Leyendo tu corrección…»")
    ok(pg.p.evaluate("() => !!document.querySelector('.pie-light button.primario').disabled"),
       "pero sí está apagado")

    # ---- la parte encadenada no se pierde si había una petición en camino
    encadenadas = []

    def regenerar_encadenada(ruta):
        encadenadas.append(1)
        ruta.fulfill(status=200, content_type="application/json",
                     body=_json.dumps({"trabajo_id": "", "sin_cambios": True,
                                       "aviso": "nada que rehacer"}))
    pg.p.route("**/api/presets-light/*/regenerar", regenerar_encadenada)
    pg.p.evaluate(f"() => {{ APP.light.cola = ['tono'];"
                  f" alTerminarLight({{ estado: 'listo', resultado: {{ preset: '{preset}' }} }}); }}")
    pg.p.wait_for_timeout(1500)
    pg.p.evaluate("() => { APP.light.lanzando = null; }")
    fin = time.time() + 10
    while time.time() < fin and not encadenadas:
        pg.p.wait_for_timeout(300)
    igual(len(encadenadas), 1, "la parte que quedaba en cola se lanza al quedar libre "
                               "(antes: se descartaba en silencio)")
    pg.p.unroute("**/api/presets-light/*/regenerar")
    pg.js("APP.light.feedback = {}; APP.light.lanzando = null;")
    pg.sin_errores("cancelar y doble toque en el taller")
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
    pg.p.locator(".fila-ajuste").filter(has_text="💬 Subtítulos").locator("button", has_text="Cambiar").click()
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
    pg.pulsar(".barra-accion button", "Generar el guion")
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
    # N1 de las notas de mejoras (13-10-2026): el SIGUIENTE vídeo nuevo salía
    # con el nombre y el material del que se acababa de crear, y se podía
    # crear otro vídeo con ellos y pagar su guion y su voz
    pg.js("irAInicioLight();")
    pg.p.wait_for_timeout(800)
    pg.js(f"await cargarGaleriaLight(true); elegirEstiloLight(fichaLight('{datos['preset']}'));")
    ok(pg.esperar("h2", "Un vídeo nuevo"), "después de crear uno, «Un vídeo nuevo» se vuelve a abrir")
    nombre_otra_vez = pg.p.locator(".bloque-light").filter(has_text="El vídeo").locator("input").first.input_value()
    material_otra_vez = pg.p.locator(".bloque-light").filter(has_text="El material").locator("textarea").first.input_value()
    ok(nombre_otra_vez == "" and material_otra_vez == "",
       f"y empieza VACÍO, sin el nombre ni el material del vídeo anterior "
       f"(nombre={nombre_otra_vez!r}, material={material_otra_vez[:40]!r})")
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


#: Un reconocimiento de voz FALSO que, al arrancar, emite la tanda de eventos
#: que se le dé (cada uno: [resultIndex, [[texto, esFinal], ...]]) y termina.
DICTADO_FALSO_JS = """(tanda) => {
  window.__dictadoAcabado = false;
  function Falso() {}
  Falso.prototype.start = function () {
    const yo = this;
    let i = 0;
    const siguiente = () => {
      if (i >= tanda.length) { window.__dictadoAcabado = true; if (yo.onend) yo.onend(); return; }
      const [indice, lista] = tanda[i++];
      const results = lista.map(([texto, final]) => {
        const r = [{ transcript: texto, confidence: 0.9 }]; r.isFinal = final; return r;
      });
      yo.onresult({ resultIndex: indice, results });
      setTimeout(siguiente, 30);
    };
    setTimeout(siguiente, 30);
  };
  Falso.prototype.stop = function () {};
  window.SpeechRecognition = Falso;
  window.webkitSpeechRecognition = Falso;
}"""

#: Lo que manda Chrome de ESCRITORIO: cada final es un trozo nuevo y
#: resultIndex apunta al primero que cambia.
DICTADO_ESCRITORIO = [
    [0, [["hola", False]]],
    [0, [["hola que tal", True]]],
    [1, [["hola que tal", True], [" quiero", False]]],
    [1, [["hola que tal", True], [" quiero un video", True]]],
]
#: Lo que manda Chrome en ANDROID con `continuous`: vuelve a mandar los
#: finales ya dados con resultIndex 0, y cada final trae la frase acumulada.
DICTADO_ANDROID = [
    [0, [["hola", False]]],
    [0, [["hola que tal", True]]],
    [0, [["hola que tal", True], ["hola que tal quiero", False]]],
    [0, [["hola que tal", True], ["hola que tal quiero un video", True]]],
]


@escenario
def dictado_del_navegador_sin_repetir(navegador, datos):
    """N8 de las notas de mejoras, 13-10-2026: «el dictado repite palabras».
    Sin clave de OpenAI se dicta con el navegador; en Android Chrome repite los
    finales acumulados y salía «hola que talhola que tal…»."""
    pg = Pagina(navegador, datos)
    pg.js("await cargarGaleriaLight(true); irALight('galeria'); elegirCliente('');")
    pg.pulsar("#burbuja-asistente")
    pg.p.wait_for_timeout(800)
    casos = [("escritorio", DICTADO_ESCRITORIO, "", "hola que tal quiero un video"),
             ("Android", DICTADO_ANDROID, "", "hola que tal quiero un video"),
             ("Android, con texto escrito antes", DICTADO_ANDROID, "Oye:",
              "Oye: hola que tal quiero un video")]
    for nombre, tanda, antes, esperado in casos:
        pg.p.evaluate(DICTADO_FALSO_JS, tanda)
        # con ESTUDIO_SIMULAR el servidor da el dictado de OpenAI por disponible:
        # se deja como sin clave (o con «navegador» elegido en Configuración)
        pg.p.evaluate("() => { if (ASISTENTE.estado) ASISTENTE.estado.dictado = false; }")
        ok(pg.p.evaluate("() => motorDictado()") == "navegador",
           f"dictado ({nombre}): sin clave de OpenAI va por el navegador")
        pg.p.evaluate("(t) => { DICTADO.estado = ''; $('#asistente-texto').value = t; "
                      "conmutarDictado(); }", antes)
        pg.p.wait_for_function("() => window.__dictadoAcabado", timeout=10000)
        texto = pg.p.evaluate("() => $('#asistente-texto').value")
        ok(texto == esperado, f"dictado ({nombre}): el campo queda «{esperado}» "
                              f"sin repetir (queda «{texto}»)")
    pg.p.evaluate("() => { $('#asistente-texto').value = ''; }")
    pg.sin_errores("el dictado del navegador")
    pg.cerrar()


#: Un pegado SINTÉTICO, como el de Ctrl+V: un ClipboardEvent con su
#: DataTransfer (texto, una imagen PNG dibujada en un lienzo, o las dos) sobre
#: `selector` (o el body). Devuelve si alguien lo atendió (defaultPrevented).
PEGAR_JS = """async ({ selector, texto, color }) => {
  const dt = new DataTransfer();
  if (texto) dt.setData('text/plain', texto);
  if (color) {
    // de 320×240 y de dos colores: el servidor no acepta como referencia
    // una imagen diminuta ni una lisa (`_motivo_para_no_aceptar`)
    const c = document.createElement('canvas'); c.width = 320; c.height = 240;
    const x = c.getContext('2d'); x.fillStyle = color; x.fillRect(0, 0, 320, 240);
    x.fillStyle = '#ffffff'; x.fillRect(40, 40, 120, 90);
    const blob = await new Promise(r => c.toBlob(r, 'image/png'));
    dt.items.add(new File([blob], 'image.png', { type: 'image/png' }));
  }
  const destino = selector ? document.querySelector(selector) : document.body;
  if (selector && destino.focus) destino.focus();
  const ev = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
  if (!ev.clipboardData) Object.defineProperty(ev, 'clipboardData', { value: dt });
  destino.dispatchEvent(ev);
  return ev.defaultPrevented;
}"""


def _subidas(pg):
    """Apunta la ruta de cada POST de imágenes o logos que sale de la pestaña."""
    lista = []
    pg.p.on("request", lambda r: lista.append(r.url.split("?")[0])
            if r.method == "POST" and ("/imagenes" in r.url or "/logos" in r.url) else None)
    return lista


def _png_dibujada(ruta, color):
    """Como `_png`, pero con un recuadro blanco: las referencias de estilo
    no pueden ser de un solo color."""
    from PIL import Image, ImageDraw                         # noqa: PLC0415
    imagen = Image.new("RGB", (320, 200), color)
    ImageDraw.Draw(imagen).rectangle((40, 40, 160, 130), fill=(255, 255, 255))
    imagen.save(ruta)
    return ruta


def _esperar_cuenta(pg, selector, n, segundos=15):
    fin = time.time() + segundos
    while time.time() < fin:
        if pg.p.locator(selector).count() >= n:
            return True
        pg.p.wait_for_timeout(300)
    return False


@escenario
def pegar_imagenes_del_portapapeles(navegador, datos):
    """N10 de las notas de mejoras, 15-10-2026: «permitir copiar/pegar imágenes
    directo del portapapeles». Pegar va por EL MISMO camino que elegir el
    fichero (misma ruta, mismos topes) y no le roba el pegado al texto."""
    pg = Pagina(navegador, datos)
    pg.contexto.grant_permissions(["clipboard-read", "clipboard-write"], origin=datos["url"])
    subidas = _subidas(pg)
    pg.js("APP.light.encargo = null; irALight('crear', { taller: null });")
    ok(pg.esperar(".zona-suelta"), "el estilo nuevo tiene su zona de imágenes de referencia")
    ok(pg.visible("button.pista-pegar", "pega una imagen"),
       "y debajo dice «o pega una imagen (Ctrl+V)»")
    tira = ".campo.aportadas .tira-aportadas .aportada"
    antes = pg.p.locator(tira).count()

    # 1) PEGAR TEXTO en un campo de texto: el pegado de siempre, nada se sube
    campo = pg.p.locator(".bloque-light textarea").first
    campo.fill("")
    campo.focus()
    pg.p.evaluate("() => navigator.clipboard.writeText('texto copiado de otra parte')")
    pg.p.keyboard.press("Control+V")
    pg.p.wait_for_timeout(800)
    ok("texto copiado de otra parte" in campo.input_value(),
       f"pegar TEXTO en un campo lo escribe como siempre ({campo.input_value()[:40]!r})")
    # y con texto Y una imagen a la vez (copiar de una web), el campo se queda el texto
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": ".bloque-light textarea",
                                        "texto": "hola", "color": "#c03030"})
    pg.p.wait_for_timeout(1200)
    ok(not atendido, "con texto e imagen y el foco en un campo, el pegado no se toca")
    ok(not subidas and pg.p.locator(tira).count() == antes,
       f"y no se sube nada al pegar texto (subidas: {subidas})")

    # 2) 16-10-2026: NO SE ADIVINA LA ZONA. Una imagen SOLA con el cursor en
    # un campo que no es de imágenes no va a ninguna zona (iba a «la única a
    # la vista», que podía ser el logo)
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": ".bloque-light textarea",
                                        "texto": "", "color": "#2060d0"})
    pg.p.wait_for_timeout(1200)
    ok(not atendido and not subidas and pg.p.locator(tira).count() == antes,
       f"una imagen pegada en un campo de texto que no es de imágenes no se sube (subidas: {subidas})")
    ok("zona de imágenes" in pg.toast(), f"y dice que se pulse antes en la zona ({pg.toast()!r})")
    # sin foco y sin haber tocado ninguna zona, tampoco: ni la única a la vista
    pg.p.evaluate("() => document.activeElement && document.activeElement.blur()")
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#2060d0"})
    pg.p.wait_for_timeout(1200)
    ok(not atendido and not subidas,
       f"sin tocar ninguna zona, una imagen pegada no va a «la única a la vista» (subidas: {subidas})")
    # tocada pero FUERA de la ventana (pintada más abajo), tampoco
    pg.p.evaluate("""() => { const z = document.querySelector('.zona-suelta');
      const relleno = document.createElement('div'); relleno.id = 'relleno-pegado';
      relleno.style.height = (window.innerHeight * 3) + 'px';
      z.parentNode.insertBefore(relleno, z);
      z.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); }""")
    fuera = pg.p.evaluate("() => document.querySelector('.zona-suelta').getBoundingClientRect().top"
                          " >= window.innerHeight")
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#2060d0"})
    pg.p.wait_for_timeout(1200)
    ok(fuera and not atendido and not subidas,
       f"la zona tocada pero fuera de la ventana no recibe el pegado (fuera: {fuera}, subidas: {subidas})")
    pg.p.evaluate("() => document.querySelector('#relleno-pegado').remove()")

    # PEGAR UNA IMAGEN (Ctrl+V) tras tocar la zona, a la vista: se sube
    pg.p.evaluate("() => document.querySelector('.zona-suelta').dispatchEvent("
                  "new PointerEvent('pointerdown', { bubbles: true }))")
    pg.p.evaluate("() => document.activeElement && document.activeElement.blur()")
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#2060d0"})
    ok(atendido, "pegar una imagen tras tocar la zona lo atiende la zona de imágenes")
    ok(_esperar_cuenta(pg, tira, antes + 1), "y la imagen pegada sale en la tira, como una elegida")
    ok(subidas and subidas[-1].endswith("/api/presets-light/imagenes"),
       f"por la MISMA ruta que el explorador ({subidas[-1:] if subidas else 'ninguna'})")
    # la misma, por el explorador: la misma ruta y otra miniatura
    pg.p.locator(".campo.aportadas input[type=file]").first.set_input_files(
        _png_dibujada(os.path.join(datos["base"], "pegar_ref.png"), (200, 120, 40)))
    ok(_esperar_cuenta(pg, tira, antes + 2), "elegir el fichero sigue funcionando")
    ok(len(set(subidas)) == 1 and len(subidas) == 2,
       f"pegar y elegir llaman a la misma ruta ({subidas})")
    pg.captura("41_pegar_en_estilo_nuevo", entera=False)

    # 3) EL ASISTENTE: con el foco dentro de su cajón la imagen va a sus
    # adjuntos, aunque la zona del estilo siga a la vista detrás
    pg.pulsar("#burbuja-asistente")
    pg.p.wait_for_timeout(1200)
    adj = "#asistente-adjuntos .adjunto"
    pg.p.evaluate("() => $('#asistente-cuerpo').dispatchEvent("
                  "new PointerEvent('pointerdown', { bubbles: true }))")
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#30a050"})
    ok(atendido and _esperar_cuenta(pg, adj, 1),
       "con el asistente tocado el último, la imagen pegada va a sus adjuntos")
    ok(subidas[-1].endswith("/api/asistente/imagenes"),
       f"por la ruta de los adjuntos del asistente ({subidas[-1]})")
    ok(pg.p.locator(tira).count() == antes + 2, "y no a la zona del estilo de detrás")
    if pg.p.locator("#asistente-texto").is_enabled():
        pg.p.evaluate(PEGAR_JS, {"selector": "#asistente-texto", "texto": "", "color": "#a03090"})
        ok(_esperar_cuenta(pg, adj, 2), "pegar con el foco en la caja del asistente también adjunta")
    n_adj = pg.p.locator(adj).count()
    pg.p.locator("#asistente-pie input[type=file]").set_input_files(
        _png_dibujada(os.path.join(datos["base"], "pegar_adj.png"), (90, 90, 200)))
    ok(_esperar_cuenta(pg, adj, n_adj + 1), "y el clip 📎 sigue adjuntando")
    ok(subidas[-1] == subidas[-2], "pegar y el clip van a la misma ruta")
    pg.captura("42_pegar_en_el_asistente", entera=False)
    pg.p.evaluate("() => { ADJUNTOS_ASISTENTE.length = 0; pintarAdjuntosAsistente(); }")
    pg.pulsar("#btn-cerrar-asistente")

    # 4) LAS NOTAS DE UNA IMAGEN: la zona tocada la última recibe la imagen, y
    # el texto de la nota se pega en la nota sin subir nada
    pg.js(f"await abrirVideoLight('{datos['video']}');")
    ir_al_paso(pg, "Imágenes")
    ok(pg.esperar(".previa-feedback .zona-suelta"), "la nota de una imagen tiene su zona de imágenes")
    n_subidas = len(subidas)
    nota = pg.p.locator(".previa-feedback textarea").first
    nota.fill("")
    nota.focus()
    pg.p.evaluate("() => navigator.clipboard.writeText('más luz a la izquierda')")
    pg.p.keyboard.press("Control+V")
    pg.p.wait_for_timeout(800)
    ok("más luz a la izquierda" in nota.input_value(), "pegar texto en la nota lo escribe")
    ok(len(subidas) == n_subidas, "y no sube nada")
    nota.fill("")
    nota.dispatch_event("input")
    # se toca como lo toca una persona: a la vista (la zona de debajo de la
    # ventana no recibe nada)
    pg.p.evaluate("() => { const z = document.querySelector('.previa-feedback .zona-suelta');"
                  " z.scrollIntoView({ block: 'center' });"
                  " z.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true })); }")
    pg.p.evaluate("() => document.activeElement && document.activeElement.blur()")
    pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#d0d030"})
    ok(_esperar_cuenta(pg, ".previa-feedback .tira-aportadas .aportada", 1),
       "pegar una imagen tras tocar la zona de la nota la adjunta a la nota")
    ok(len(subidas) > n_subidas and subidas[-1].endswith("/repaso/imagenes"),
       f"por la ruta de las imágenes de las notas ({subidas[-1:]})")
    # escribiendo la nota (foco en SU campo), la imagen va a SUS adjuntos
    n_aportadas = pg.p.locator(".previa-feedback .tira-aportadas .aportada").count()
    pg.p.evaluate(PEGAR_JS, {"selector": ".previa-feedback textarea", "texto": "", "color": "#30d0d0"})
    ok(_esperar_cuenta(pg, ".previa-feedback .tira-aportadas .aportada", n_aportadas + 1),
       "con el cursor en la nota, la imagen pegada va a los adjuntos de esa nota")
    pg.captura("43_pegar_en_la_nota", entera=False)

    # 5) EL LOGO: solo recibe lo que se pega cuando se ha tocado. Con el cursor
    # en el nombre del vídeo, o sin tocar nada, la imagen NO acaba en el logo
    pg.js(f"await cargarGaleriaLight(true); elegirEstiloLight(fichaLight('{datos['preset']}'));")
    ok(pg.esperar("h2", "Un vídeo nuevo"), "el vídeo nuevo, con su logo")
    pg.p.locator(".fila-ajuste").filter(has_text="Logo").locator("button", has_text="Cambiar").click()
    ok(pg.esperar(".editor-ajuste.acepta-pegado"), "el editor del logo es una zona de pegar")
    pg.p.evaluate("() => document.querySelector('.editor-ajuste.acepta-pegado').scrollIntoView({ block: 'center' })")
    pg.p.evaluate("""() => { const i = [...document.querySelectorAll('.bloque-light')]
      .filter(b => /El vídeo/.test(b.innerText)).map(b => b.querySelector('input[type=text], input:not([type])'))
      .find(Boolean); if (i) i.id = 'campo-prueba-pegado'; }""")
    logos = [u for u in subidas if "/logos" in u]
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": "#campo-prueba-pegado", "texto": "", "color": "#e08020"})
    pg.p.wait_for_timeout(1500)
    ok(not atendido and [u for u in subidas if "/logos" in u] == logos,
       f"con el cursor en el nombre del vídeo, la imagen pegada NO va al logo (subidas: {subidas[-2:]})")
    pg.p.evaluate("() => document.activeElement && document.activeElement.blur()")
    # poner el foco en el nombre sube la pantalla hasta él: el logo se vuelve
    # a poner a la vista (en el carril, «El vídeo» y el logo quedan lejos)
    pg.p.evaluate("() => document.querySelector('.editor-ajuste.acepta-pegado').scrollIntoView({ block: 'center' })")
    pg.p.wait_for_timeout(500)
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#e08020"})
    pg.p.wait_for_timeout(1500)
    ok(not atendido and [u for u in subidas if "/logos" in u] == logos,
       "sin tocar el logo, aunque sea la única zona a la vista, no lo recibe")
    pg.p.evaluate("() => document.querySelector('.editor-ajuste.acepta-pegado').dispatchEvent("
                  "new PointerEvent('pointerdown', { bubbles: true }))")
    atendido = pg.p.evaluate(PEGAR_JS, {"selector": None, "texto": "", "color": "#e08020"})
    fin = time.time() + 15
    while time.time() < fin and [u for u in subidas if "/logos" in u] == logos:
        pg.p.wait_for_timeout(300)
    ok(atendido and len([u for u in subidas if "/logos" in u]) == len(logos) + 1,
       "tocado el logo, la imagen pegada sí es el logo")
    pg.sin_errores("pegar imágenes")
    pg.cerrar()


#: Una respuesta del asistente con un bloque de código, como las de verdad.
RESPUESTA_CON_CODIGO = ("Pon esto en **Indicaciones**:\n\n```\nluz cálida de tarde\nsin gente al fondo\n```\n"
                        "Y luego pulsa `Regenerar`.")


@escenario
def copiar_respuestas_del_asistente(navegador, datos):
    """N11 y N12 de las notas de mejoras: «Copiar» en los bloques de código de
    las respuestas del asistente y en la respuesta entera."""
    for ancho, alto, nombre in ((1300, 900, "ordenador"), (390, 844, "móvil")):
        pg = Pagina(navegador, datos, ancho=ancho, alto=alto)
        pg.p.evaluate("() => { window.__copiado = null; Object.defineProperty(navigator, 'clipboard', "
                      "{ configurable: true, value: { writeText: t => { window.__copiado = t; "
                      "return Promise.resolve(); } } }); }")
        pg.pulsar("#burbuja-asistente")
        pg.p.wait_for_timeout(1500)
        pg.p.evaluate("(t) => { ASISTENTE.verHistorial = false; ASISTENTE.charla = { id: 'prueba-copiar', "
                      "turnos: [{ quien: 'tu', texto: '¿qué pongo?' }, "
                      "{ quien: 'asistente', estado: 'hecho', texto: t, segundos: 3 }] }; "
                      "pintarAsistente(); }", RESPUESTA_CON_CODIGO)
        ok(pg.esperar("#asistente .turno.asistente pre", "luz cálida"),
           f"{nombre}: la respuesta con un bloque de código se pinta")
        ok(pg.visible("#asistente .bloque-codigo button", "Copiar"),
           f"{nombre}: el bloque de código lleva su «Copiar»")
        ok(pg.visible("#asistente .turno.asistente .pie-turno button", "Copiar"),
           f"{nombre}: y la respuesta entera también")
        # que no los tape la burbuja
        tapado = pg.p.evaluate("""() => [...document.querySelectorAll('#asistente .copiar-bloque, #asistente .copiar-turno')]
          .some(b => { const r = b.getBoundingClientRect();
                       const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                       return !e || !b.contains(e); })""")
        ok(not tapado, f"{nombre}: nada tapa los «Copiar»")
        # y el «Copiar» del bloque no tapa la primera línea del código
        pisa = pg.p.evaluate("""() => { const b = document.querySelector('#asistente .copiar-bloque');
          const pre = b.parentNode.querySelector('pre');
          const texto = pre.getBoundingClientRect().top + parseFloat(getComputedStyle(pre).paddingTop);
          return b.getBoundingClientRect().bottom > texto + 1; }""")
        ok(not pisa, f"{nombre}: el «Copiar» del bloque no tapa la primera línea del código")
        pg.pulsar("#asistente .bloque-codigo button", "Copiar")
        copiado = pg.p.evaluate("() => window.__copiado")
        ok(copiado == "luz cálida de tarde\nsin gente al fondo",
           f"{nombre}: «Copiar» del bloque copia SOLO el código ({copiado!r})")
        ok("copiado" in pg.avisos(), f"{nombre}: y dice «copiado»")
        pg.pulsar("#asistente .pie-turno button", "Copiar")
        copiado = pg.p.evaluate("() => window.__copiado") or ""
        ok(copiado.startswith("Pon esto en Indicaciones:") and "luz cálida de tarde" in copiado
           and copiado.endswith("Y luego pulsa Regenerar.") and "**" not in copiado
           and "\x60" not in copiado,
           f"{nombre}: «Copiar» de la respuesta la copia entera, en texto llano ({copiado!r})")
        pg.captura(f"44_copiar_asistente_{nombre}", entera=False)
        pg.sin_errores(f"copiar del asistente ({nombre})")
        pg.cerrar()


#: Lo que el recorrido de TODOS LOS BOTONES no pulsa: lo que lanza trabajos
#: largos, borra o sale. Lo demás se pulsa todo (los confirm() se CANCELAN en
#: este escenario, así que lo que pregunta antes no llega a hacer nada).
NO_PULSAR = re.compile(r"(Borrar|Eliminar|papelera|Regenerar|Generar|Rehacer|Desde cero|"
                       r"Montar|Aplicar|Arreglar|Salir|Descargar|Traer|Restablecer|Revertir|"
                       r"Parar|Reintentar|Duplicar|Crear|Guardar|Subir|Probar|Entrar|"
                       r"Pedir otro enlace|Ocultar|Esconder|Apartar|Mover|Quitar|Ver ocultos|"
                       r"Hacerla sin marcas|Usar|Partir|Añadir|Nuevo|Nueva|Volver a la versi|"
                       # los nombres del rediseño de Crear (20-10-2026) que pagan o lanzan
                       r"Grabar|Redibujar|Poner al día|Retomar|\+)", re.I)

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
        ("voz", f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'voz'; pintarLight();"),
        ("vídeo nuevo", f"recordarVideoLight(''); elegirEstiloLight(fichaLight('{datos['preset']}'));"),
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
        // dentro de un <details> cerrado: Chromium le deja su caja (content-
        // visibility) pero no se pinta ni se puede pulsar; no hay nada tapado
        const plegado = b.closest('details:not([open])');
        if (plegado && !b.closest('summary')) return;
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
def ortografia_en_el_guion_y_en_los_campos(navegador, datos):
    """18-10-2026, lo que pidió el dueño tras ver el corrector con error en
    Vídeo: «debería estar activo para revisar el guion, no cuando ya todo está
    montado», y «también en todos los campos con texto que se publica o se ve».

      - el panel del guion sale también con la voz grabada, y lo dice;
      - sin voz, el guion se revisa SOLO al quedarse quieto;
      - lo ya revisado no vuelve a Claude: el proyecto lo recuerda;
      - un campo suelto (CTA, Parrilla…) se revisa con su botón y «Poner las
        correcciones» lo cambia por el mismo camino que escribir, línea a línea."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'guion'; pintarLight();")
    ok(pg.esperar(".panel-ortografia", "Ortografía del guion", 15),
       "el guion tiene su panel de ortografía también con la voz grabada")
    ok(pg.visible(".panel-ortografia", "la voz ya está grabada"),
       "y dice que la voz ya está grabada")
    pg.p.wait_for_timeout(5000)
    ok(pg.js(f"return !ORTOGRAFIA_VIVA.get(claveOrtografia('{pid}', 'guion'));"),
       "con la voz grabada NO se revisa sola (corregir ahí es regrabar)")
    # SIN VOZ: se revisa sola. La voz se quita solo en la pantalla (el vídeo
    # de prueba la tiene grabada); se vuelve a abrir al acabar.
    pg.js(f"""ORTOGRAFIA_SOLA.clear(); ORTOGRAFIA_VIVA.delete(claveOrtografia('{pid}', 'guion'));
      APP.light.video.audio = null; pintarLight();""")
    ok(pg.esperar(".panel-ortografia", "se revisa sola", 10), "sin voz, el panel dice que se revisa sola")
    fin = time.time() + 60
    estado = None
    while time.time() < fin:
        estado = pg.js(f"APP.light.video.audio = null; return (ORTOGRAFIA_VIVA.get(claveOrtografia('{pid}', 'guion')) || {{}}).estado;")
        if estado in ("listo", "error"):
            break
        pg.p.wait_for_timeout(700)
    ok(estado == "listo", f"el guion se ha revisado solo, sin pulsar nada ({estado})")
    memoria = os.path.join(datos["proyectos"], pid, "ortografia.json")
    ok(os.path.isfile(memoria), "y lo revisado queda apuntado en el proyecto (ortografia.json)")
    pg.js(f"""ORTOGRAFIA_VIVA.delete(claveOrtografia('{pid}', 'guion'));""")
    pg.js("APP.light.video.audio = null; await revisarOrtografia('guion');")
    ficha = pg.js(f"return ORTOGRAFIA_VIVA.get(claveOrtografia('{pid}', 'guion')) || {{}};")
    ok(ficha.get("estado") == "listo" and ficha.get("de_memoria", 0) >= 1
       and ficha.get("de_memoria") == ficha.get("revisados"),
       f"la segunda vez todo sale de la memoria, sin preguntar a Claude ({ficha.get('de_memoria')} de {ficha.get('revisados')})")
    pg.js(f"ORTOGRAFIA_VIVA.delete(claveOrtografia('{pid}', 'guion')); await abrirVideoLight('{pid}');")
    # UN CAMPO SUELTO: la pieza común, montada en la pantalla
    pg.js("""window.__puesto = null; window.__texto = 'Una vez mas\\nsegunda linea bien';
      const caja = ortografiaDeCampo('prueba-recorrido', { leer: () => window.__texto,
        poner: t => { window.__puesto = t; } });
      caja.classList.add('ortografia-de-prueba');
      // DENTRO DE LA PANTALLA, como un campo de verdad: colgado de <body>
      // quedaba debajo del menú lateral fijo de CrearIA y no se podía pulsar
      (document.querySelector('#panel') || document.querySelector('#cuerpo') || document.body).appendChild(caja);""")
    ok(pg.esperar(".ortografia-de-prueba button", "Revisar ortografía", 10), "el campo trae «Revisar ortografía»")
    pg.pulsar(".ortografia-de-prueba button", "Revisar ortografía")
    ok(pg.esperar(".ortografia-de-prueba button", "Poner las correcciones", 60), "propone la corrección del campo")
    ok(pg.visible(".ortografia-de-prueba", "más"), "con la tilde que faltaba")
    # SE SIGUE ESCRIBIENDO después de revisar: «Poner» no se lleva lo escrito
    pg.js("window.__texto = 'Una vez mas\\nsegunda linea bien y algo nuevo';")
    pg.pulsar(".ortografia-de-prueba button", "Poner las correcciones")
    ok(pg.js("return window.__puesto;") is None,
       "si el texto cambió después de revisar, «Poner» no lo pisa: se revisa otra vez")
    pg.js("window.__texto = 'Una vez mas\\nsegunda linea bien';")
    pg.pulsar(".ortografia-de-prueba button", "Revisar ortografía")
    ok(pg.esperar(".ortografia-de-prueba button", "Poner las correcciones", 60), "vuelve a proponer")
    pg.pulsar(".ortografia-de-prueba button", "Poner las correcciones")
    puesto = pg.js("return window.__puesto;")
    ok(puesto == "Una vez más\nsegunda linea bien",
       f"y la pone por el camino del campo, con los saltos de línea donde estaban ({puesto!r})")
    # VARIOS CAMPOS A LA VEZ (lo de una red en Publicar): cada corrección a su campo
    pg.js("""window.__partes = null;
      const caja = ortografiaDeCampo('prueba-partes', { etiquetas: { titulo: 'Título', descripcion: 'Texto' },
        partes: () => ({ titulo: 'Las gruas del puerto', descripcion: 'bien escrito\\nuna vez mas' }),
        ponerPartes: n => { window.__partes = n; } });
      caja.classList.add('ortografia-de-partes');
      (document.querySelector("#panel") || document.querySelector("#cuerpo") || document.body).appendChild(caja);""")
    pg.pulsar(".ortografia-de-partes button", "Revisar ortografía")
    ok(pg.esperar(".ortografia-de-partes button", "Poner las correcciones", 60), "revisa varios campos juntos")
    ok(pg.visible(".ortografia-de-partes", "Título"), "y dice de qué campo es cada corrección")
    pg.pulsar(".ortografia-de-partes button", "Poner las correcciones")
    partes = pg.js("return window.__partes;")
    ok(partes == {"titulo": "Las grúas del puerto", "descripcion": "bien escrito\nuna vez más"},
       f"y pone cada una en su campo, sin tocar las demás líneas ({partes!r})")
    pg.sin_errores("la ortografía en el guion y en los campos")
    pg.cerrar()


@escenario
def ortografia_por_palabra_entera(navegador, datos):
    """N6 de las notas de mejoras (13-10-2026). Al poner una corrección en un
    bloque con marcas de la voz, «esta → está» cambiaba la «esta» de dentro de
    «estaba»; el aviso rojo de «corrígelo a mano» lo tapaba al instante el de
    «puestas»; y lo que no se pudo revisar (una tanda con el JSON roto) no se
    decía. Se llama a las funciones de la pantalla y se pinta el panel con
    cada estado."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar(".panel-ortografia", "Ortografía", 15), "el panel de ortografía está")
    r = pg.js("""return [
      sustituirPalabra('estaba esta casa', 'esta', 'está'),
      sustituirPalabra('estaba aqui', 'esta', 'está'),
      sustituirPalabra('<break time="1s"/> time', 'time', 'tiempo'),
      ortografiaSobreCrudo('Ella estaba <break time="900ms"/> y esta aqui',
        { despues: 'Ella estaba y está aquí', cambios: [['esta', 'está'], ['aqui', 'aquí']] }),
      ortografiaSobreCrudo('Ella estaba <break time="900ms"/> bien',
        { despues: 'Ella estába bien', cambios: [['esta', 'está']] })];""")
    ok(r[0] == "estaba está casa", f"«esta → está» no toca la de dentro de «estaba» ({r[0]!r})")
    ok(r[1] is None, f"si solo está dentro de otra palabra, no se pone ({r[1]!r})")
    ok(r[2] == '<break time="1s"/> tiempo', f"ni dentro de una marca de la voz ({r[2]!r})")
    ok(r[3] == 'Ella estaba <break time="900ms"/> y está aquí',
       f"con marcas, cada pareja va a su palabra y las pausas se quedan ({r[3]!r})")
    ok(r[4] is None, f"lo que no encaja vuelve como «a mano» (null), no como puesto ({r[4]!r})")
    # lo que se quedó sin revisar se dice, y «Sin faltas» no lo cuenta
    pg.js(f"""ORTOGRAFIA_VIVA.set(claveOrtografia('{pid}', 'subtitulos'),
      {{ estado: 'listo', revisados: 10, sin_revisar: 3, propuestas: [] }}); pintarLight();""")
    texto = pg.p.locator(".panel-ortografia").last.inner_text()
    ok("3 texto(s) se han quedado sin revisar" in texto and "Sin faltas en 7 textos" in texto,
       f"los textos sin revisar se dicen y no cuentan como revisados ({texto[:220]!r})")
    # la respuesta rota en todas las tandas: el titular es para la persona
    pg.js(f"""ORTOGRAFIA_VIVA.set(claveOrtografia('{pid}', 'subtitulos'), {{ estado: 'error',
      error: 'El corrector devolvió una respuesta rota; pulsa «Revisar otra vez». No se ha cambiado nada.\\n\\n'
        + "la revision de ortografia no es un JSON legible: Expecting ',' delimiter" }}); pintarLight();""")
    titular = pg.p.locator(".panel-ortografia .caja-error .titular").last.inner_text()
    ok(titular.startswith("El corrector devolvió") and "JSON" not in titular,
       f"el titular del error no es el texto técnico ({titular!r})")
    # lo aplicado a medias: UN aviso con las dos cuentas, y lo de a mano a la vista
    pg.js(f"""ORTOGRAFIA_VIVA.set(claveOrtografia('{pid}', 'subtitulos'), {{ estado: 'aplicada',
      aviso: '2 corrección(es) puestas; 1 hay que corregirla(s) a mano (B003): llevan pausas',
      aMano: [{{ id: 'B003', despues: 'Ella está bien', cambios: [['esta', 'está']] }}] }}); pintarLight();""")
    texto = pg.p.locator(".panel-ortografia").last.inner_text()
    ok("2 corrección(es) puestas; 1 hay que corregirla(s) a mano" in texto and "Ella está bien" in texto,
       f"lo que queda a mano se queda en el panel con su texto ({texto[:220]!r})")
    pg.js(f"ORTOGRAFIA_VIVA.delete(claveOrtografia('{pid}', 'subtitulos')); pintarLight();")
    pg.sin_errores("la ortografía por palabra entera")
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
        ir_al_paso(pg, "Encargo")
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

    # 1. LAS SALIDAS: la de Crear (desde el rediseño, 20-10-2026; vuelve al
    # proyecto del vídeo y lleva su nombre, revisión del 21-10) y el logo
    salidas = (("«‹ Estado Play»", lambda: pg.pulsar(".salida-crear", "Estado Play")),
               ("el logo", lambda: pg.p.click("#cabecera .marca")))
    for vista in ("encargo_video", "guion", "voz", "previa", "video"):
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = '{vista}'; pintarLight();")
        ok(pg.esperar(".salida-crear", "‹ Estado Play", 15),
           f"en la pantalla «{vista}» del vídeo está la salida a su proyecto («‹ Estado Play»)")
    for como, accion in salidas:
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
        pg.esperar(".cab-video", None, 15)
        accion()
        pg.p.wait_for_timeout(1200)
        ok(pg.p.evaluate("() => APP.light.vista !== 'elegido' && !APP.light.video.pid"),
           f"{como} saca del vídeo")
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


@escenario
def musica_efectos_y_subtitulos_en_el_video(navegador, datos):
    """N9 de las notas de mejoras (13-10-2026): «que cuando el vídeo esté
    generado me pueda mostrar la música, los efectos y los subtítulos para
    modificarlos, sin regenerar las imágenes ni la voz». Debajo del vídeo
    montado salen los ajustes del montaje; el volumen fino guarda su valor y
    lanza SOLO una remezcla; y el ánimo de la automática se ofrece (montarlo
    pide Jamendo, que aquí no hay: lo de servidor va en prueba_api)."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado al día")
    pg.p.wait_for_timeout(1500)
    ok(pg.esperar(".ajustes-en-video .ajustes-cab", "Ajustes del montaje", 15),
       "debajo del vídeo montado salen los «Ajustes del montaje» (el mismo panel que en el Encargo)")
    ok(pg.visible(".ajustes-en-video .ajustes-cab", "nada de esto paga imágenes"),
       "y dice que cambiarlo no paga ninguna imagen")
    for fila in ("Música", "Efectos", "Subtítulos"):
        ok(pg.esperar(".ajustes-en-video .fila-ajuste-cab", fila, 10),
           f"con la fila de {fila.lower()} (la misma que en el Encargo)")
    _r, antes = api.get(f"/api/trabajos?proyecto={pid}")
    vistos = {t.get("id") for t in antes.get("trabajos") or []}
    assets_antes = _version_de(datos, "assets", "").get("activa")
    voz_antes = _version_de(datos, "voz", "").get("activa")
    render_antes = _version_de(datos, "render", "").get("activa")
    pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="Música").first \
        .locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(800)
    ok(pg.visible(".ajustes-en-video input.volumen-fino"), "la música trae un ajuste fino del volumen")
    ok(pg.visible(".ajustes-en-video select.animo-automatica"),
       "y un selector del ánimo para la música automática")
    ok(not pg.p.locator(".ajustes-en-video select.animo-automatica").first.is_enabled()
       and pg.visible(".ajustes-en-video .pista", "clave de Jamendo"),
       "que sin la clave de Jamendo no deja elegirlo (y lo dice)")
    pg.captura("n9_ajustes_en_el_video", entera=False)
    # EL VOLUMEN FINO: se suelta en −4 dB
    pg.p.evaluate("""() => { const r = document.querySelector('.ajustes-en-video input.volumen-fino');
      r.value = -4; r.dispatchEvent(new Event('input', { bubbles: true }));
      r.dispatchEvent(new Event('change', { bubbles: true })); }""")
    pg.p.wait_for_timeout(2500)
    _r, sonido = api.get(f"/api/proyectos/{pid}/sonido")
    igual_db = sonido.get("musica_db") == -4.0
    ok(igual_db, f"el volumen fino queda guardado en −4 dB ({sonido.get('musica_db')!r})")
    # DECISIÓN 9 (rediseño de Crear, 20-10-2026): tocar un ajuste NO monta
    _r, sin_montar = api.get(f"/api/trabajos?proyecto={pid}")
    ok(not [t for t in sin_montar.get("trabajos") or [] if t.get("id") not in vistos],
       "tocar el ajuste lo guarda SIN montar el vídeo (decisión 9)")
    ok(pg.esperar(".ajustes-en-video .franja-sin-aplicar", "Hay 1 cambio del montaje sin aplicar", 10),
       "sale «Hay 1 cambio del montaje sin aplicar»")
    ok(pg.visible(".ajustes-en-video .fila-ajuste-cab", "sin aplicar todavía"),
       "y la fila de la música dice «sin aplicar todavía»")
    ok(pg.visible(".barra-accion button", "Montar el vídeo con 1 cambio · gratis"),
       "y la barra ofrece «Montar el vídeo con 1 cambio · gratis»")
    pg.captura("n9_un_cambio_sin_aplicar", entera=False)
    # EL BOTÓN APLICA (`POST /montaje/aplicar`), y lo pendiente es SOLO la
    # mezcla: el servidor lo dice en `solo_mezcla` (con él, el trabajo es
    # volver a mezclar sobre los clips que hay, sin capas ni montaje nuevo)
    with pg.p.expect_response(lambda r: "/montaje/aplicar" in r.url and r.request.method == "POST",
                              timeout=20000) as respuesta:
        _montar_los_cambios(pg)
    aplicado = respuesta.value.json() if respuesta.value.ok else {}
    ok(aplicado.get("solo_mezcla") is True,
       f"el botón aplica los cambios y es SOLO volver a mezclar (solo_mezcla={aplicado.get('solo_mezcla')!r})")
    pg.p.wait_for_timeout(1500)
    ok(api.libre(pid), "la remezcla termina")
    pg.sin_trabajo(300)
    _r, despues = api.get(f"/api/trabajos?proyecto={pid}")
    nuevos = [t for t in despues.get("trabajos") or [] if t.get("id") not in vistos]
    ok(len(nuevos) == 1 and all(t.get("paso") == "render" and t.get("id") == aplicado.get("trabajo_id")
                                for t in nuevos),
       f"y el botón lanza SOLO esa remezcla del render ({[(t.get('nombre'), t.get('paso')) for t in nuevos]})")
    ok(not any(t.get("paso") in ("assets", "voz", "callouts") for t in nuevos),
       "ningún trabajo de imágenes, voz ni rótulos")
    igual_versiones = (_version_de(datos, "assets", "").get("activa"),
                       _version_de(datos, "voz", "").get("activa"))
    ok(igual_versiones == (assets_antes, voz_antes),
       f"las imágenes y la voz siguen en su versión ({(assets_antes, voz_antes)} → {igual_versiones})")
    ok(_version_de(datos, "render", "").get("activa") != render_antes,
       "y el MP4 se ha vuelto a montar")
    pg.p.wait_for_timeout(1500)
    ok(pg.esperar(".ajustes-en-video .fila-ajuste-cab", "−4 dB", 15),
       "y la fila de la música dice el ajuste (−4 dB)")
    # se deja como estaba para quien venga detrás
    api.put(f"/api/proyectos/{pid}/sonido", {"musica_db": 0, "remontar": True})
    api.libre(pid)
    pg.sin_errores("música, efectos y subtítulos en el vídeo")
    pg.cerrar()


@escenario
def montar_los_cambios_no_paga_imagenes(navegador, datos):
    """Revisión del rediseño de Crear (21-10-2026), DINERO: con imágenes que se
    han quedado viejas y un ajuste del montaje cambiado, «Montar el vídeo con 1
    cambio · gratis» del Encargo lanzaba la tanda del vídeo, que las redibuja
    y se paga, sin preguntar. Ahora aplica (`POST /montaje/aplicar`, ni una
    imagen) y montar con las imágenes viejas es otro botón con su precio, que
    pregunta antes. Aquí no se lanza nada de verdad: las dos peticiones se
    cortan y el plan de la tanda dice que hay 3 imágenes por dibujar."""
    pid, api = datos["video"], datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado al día")
    pedidas = []
    falso = {"animo": ""}
    plan_viejo = {"tareas": 3, "segundos": 120, "coste": {
        "imagenes": 3, "imagenes_por_generar": 3, "imagenes_hechas": 0,
        "usd_por_generar": 0.25, "usd_total": 0.25}}

    def al_pedir(ruta):
        req = ruta.request
        if req.method == "POST" and ("/generar" in req.url or "/montaje/aplicar" in req.url):
            pedidas.append((req.url, req.post_data or ""))
            # no se lanza nada de verdad: el servidor «contesta» que no
            ruta.fulfill(status=409, content_type="application/json",
                         body=json.dumps({"detail": "prueba: no se lanza nada"}))
        elif req.method == "GET" and "/generar?tanda=render" in req.url:
            ruta.fulfill(status=200, content_type="application/json", body=json.dumps(plan_viejo))
        elif req.method == "PUT" and "/musica/animo" in req.url and falso["animo"]:
            # la banda «se monta» con un trabajo que ya terminó: así se ve qué
            # viene DESPUÉS sin buscar temas en Jamendo
            pedidas.append((req.url, req.post_data or ""))
            ruta.fulfill(status=200, content_type="application/json", body=json.dumps(
                {"trabajo_id": falso["animo"], "animo": "alegre", "remontando": False}))
        else:
            ruta.continue_()
    pg.p.route("**/api/proyectos/**", al_pedir)
    try:
        ir_al_paso(pg, "Encargo")
        pg.p.wait_for_timeout(1500)
        # un ajuste guardado sin montar (lo que apunta la pantalla al guardarlo)
        # y las imágenes viejas
        pg.js("const est = estadoAjustes({ tipo: 'video', pid: APP.light.video.pid, diferir: true });"
              " est.montaje = Object.assign({}, est.montaje, { montado: true });"
              " apuntarCambioDeMontaje(est, 'musica');"
              " APP.light.video.fichas.assets = Object.assign({}, APP.light.video.fichas.assets, { estado: 'obsoleto' });"
              " await refrescarPlanLight('render', true); repintarBarra();")
        pg.p.wait_for_timeout(600)
        ok(pg.visible(".barra-accion button", "Montar el vídeo con 1 cambio · gratis"),
           "el Encargo ofrece «Montar el vídeo con 1 cambio · gratis»")
        pg.pulsar(".barra-accion button", "Montar el vídeo con 1 cambio")
        pg.p.wait_for_timeout(1500)
        ok(not any("/generar" in u for u, _d in pedidas),
           f"y NO lanza la tanda del vídeo, que redibujaría las imágenes viejas ({pedidas})")
        ok(any("/montaje/aplicar" in u for u, _d in pedidas),
           f"lo que hace es aplicar los cambios, gratis ({pedidas})")
        # en Vídeo: los dos botones, cada uno con lo que cuesta
        del pedidas[:]
        pg.js("const est = estadoAjustes({ tipo: 'video', pid: APP.light.video.pid, diferir: true });"
              " est.aplicando = false; apuntarCambioDeMontaje(est, 'musica');"
              " APP.light.video.vista = 'video'; pintarLight();")
        pg.p.wait_for_timeout(1200)
        pg.js("await refrescarPlanLight('render', true); repintarBarra();")
        pg.p.wait_for_timeout(600)
        ok(pg.visible(".barra-accion button", "Montar el vídeo con 1 cambio · gratis")
           and pg.visible(".barra-accion button", "Montar el vídeo · ≈ 0.25 $"),
           "en Vídeo: aplicar los cambios (gratis) y, aparte, montar con las imágenes viejas con su precio")
        pg.aceptar = False
        antes = len(pg.dialogos)
        pg.pulsar(".barra-accion button", "Montar el vídeo · ≈")
        pg.p.wait_for_timeout(1500)
        ok(len(pg.dialogos) > antes and "3 imágenes" in pg.dialogos[-1],
           f"el de pago pregunta antes, con cuántas imágenes y su precio ({pg.dialogos[antes:]})")
        ok(not any("/generar" in u for u, _d in pedidas),
           f"y diciendo que no, no lanza nada ({pedidas})")
        pg.aceptar = True
        # (6) SIN MP4 Y CON SOLO EL ÁNIMO PEDIDO: el botón monta el VÍDEO, con
        # el ánimo dentro (antes montaba la música y ahí se quedaba), y como
        # hay imágenes viejas, pregunta antes
        _r, hechos = api.get(f"/api/trabajos?proyecto={pid}")
        falso["animo"] = next((t.get("id") for t in hechos.get("trabajos") or []
                               if t.get("estado") == "listo"), "")
        del pedidas[:]
        pg.js("const v = APP.light.video; const est = estadoAjustes({ tipo: 'video', pid: v.pid });"
              " est.aplicando = false; olvidarCambiosDelMontaje(est, v.pid); est.animoPedido = 'alegre';"
              " v.fichas.render = Object.assign({}, v.fichas.render, { salidas: {} });"
              " v.vista = 'video'; pintarLight(); await refrescarPlanLight('render', true); repintarBarra();")
        pg.p.wait_for_timeout(800)
        ok(pg.visible(".barra-accion button", "Montar el vídeo · ≈ 0.25 $")
           and not pg.visible(".barra-accion button", "Montar el vídeo con"),
           "sin MP4 y con el ánimo pedido, la barra ofrece montar el vídeo, con su precio")
        antes = len(pg.dialogos)
        pg.pulsar(".barra-accion button", "Montar el vídeo · ≈")
        pg.p.wait_for_timeout(4000)
        ok(len(pg.dialogos) > antes, "pregunta antes (hay imágenes viejas que dibujar)")
        ok(any("/musica/animo" in u for u, _d in pedidas)
           and any("/generar" in u and '"render"' in d for u, d in pedidas),
           f"y monta la música con el ánimo y DESPUÉS el vídeo ({[u.rsplit('/', 2)[-2:] for u, _d in pedidas]})")
        # el 409 de mentira de arriba se apunta en la consola como cualquier
        # tanda que no se puede lanzar: ese no es un fallo de la pantalla
        pg.errores[:] = [e for e in pg.errores if "prueba: no se lanza nada" not in e]
    finally:
        pg.p.unroute("**/api/proyectos/**")
    pg.js("const est = estadoAjustes({ tipo: 'video', pid: APP.light.video.pid, diferir: true });"
          " est.aplicando = false; olvidarCambiosDelMontaje(est, APP.light.video.pid);")
    pg.sin_errores("montar los cambios no paga imágenes")
    pg.cerrar()


@escenario
def los_cambios_del_montaje_no_se_pierden(navegador, datos):
    """Revisión del rediseño de Crear (21-10-2026). (2) El ánimo de la música
    pedido y sin montar se borraba en silencio cada vez que se releía el vídeo
    (`cargarVideoLight`, treinta sitios): ahora se queda, también al recargar
    la página, y salir del vídeo con él avisa. (5) Lo apuntado lo recoge
    CUALQUIER montaje (aquí, «Montar el vídeo» de Imágenes): el contador baja,
    pero el ánimo, que no está en el servidor, sigue pendiente."""
    pid, api = datos["video"], datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado al día")
    pg.p.wait_for_timeout(1500)

    def barra():
        return pg.p.evaluate("() => [...document.querySelectorAll('.barra-accion button')]"
                             ".map(b => b.innerText).join(' | ')")
    # EL ÁNIMO, pedido en su selector (sin Jamendo está apagado: se enciende)
    pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="Música").first \
        .locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(800)
    pg.js("const est = estadoAjustes({ tipo: 'video', pid: APP.light.video.pid });"
          " est.hayJamendo = true; est.repintar();")
    animo = pg.p.evaluate("() => { const u = animoUnicoDe(estadoAjustes({ tipo: 'video', "
                          "pid: APP.light.video.pid })); return ANIMOS_MUSICA.find(a => a[0] !== u)[0]; }")
    pg.p.locator(".ajustes-en-video select.animo-automatica").first.select_option(animo)
    pg.p.wait_for_timeout(800)
    ok("Montar el vídeo con 1 cambio" in barra(), f"pedir un ánimo es 1 cambio sin aplicar ({barra()})")
    pg.js("await recargarVideoAbierto(); pintarLight();")
    pg.p.wait_for_timeout(1500)
    ok("Montar el vídeo con 1 cambio" in barra(),
       f"releer el vídeo NO borra el ánimo pedido ({barra()})")
    # RECARGAR LA PÁGINA: sigue ahí (guardado en el navegador, por vídeo)
    pg.p.reload()
    pg.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos", timeout=30000)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    pg.p.wait_for_timeout(2000)
    ok("Montar el vídeo con 1 cambio" in barra(),
       f"y recargar la página tampoco ({barra()})")
    ok(pg.p.evaluate("() => estadoAjustes({ tipo: 'video', pid: APP.light.video.pid }).animoPedido") == animo,
       "con el mismo ánimo pedido")
    # SALIR CON ÉL avisa; diciendo que no, te quedas
    pg.aceptar = False
    antes = len(pg.dialogos)
    pg.pulsar(".salida-crear")
    pg.p.wait_for_timeout(800)
    ok(len(pg.dialogos) > antes and "sin aplicar" in pg.dialogos[-1],
       f"salir del vídeo con cambios sin aplicar avisa ({pg.dialogos[antes:]})")
    ok(pg.p.evaluate(f"() => APP.light.video.pid === '{pid}'"), "y diciendo que no, sigue en el vídeo")
    pg.aceptar = True
    try:
        # (5) UN AJUSTE DE OTRA FILA, montado por OTRO camino que el botón de la
        # barra (aquí, por la API: como la tanda de Imágenes o aplicar las notas,
        # la pantalla no se entera de quién lo lanzó)
        pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="💬 Subtítulos").first \
            .locator("button", has_text="Cambiar").click()
        pg.p.wait_for_timeout(800)
        pg.p.locator(".ajustes-en-video .editor-ajuste .campo").filter(
            has=pg.p.locator("label", has_text="Dónde va")).first.locator("button", has_text="Arriba").click()
        pg.p.wait_for_timeout(2000)
        ok("Montar el vídeo con 2 cambios" in barra(), f"los subtítulos son otro cambio: 2 ({barra()})")
        r, _d = api.post(f"/api/proyectos/{pid}/montaje/aplicar", {})
        ok(r.status_code == 202, f"el vídeo se monta por otro camino ({r.status_code})")
        ok(api.libre(pid, 600), "el montaje termina")
        pg.js("await recargarVideoAbierto(); pintarLight();")
        pg.p.wait_for_timeout(2000)
        ir_al_paso(pg, "Vídeo")
        pg.p.wait_for_timeout(2500)
        ok("Montar el vídeo con 1 cambio" in barra(),
           f"ese montaje recoge los subtítulos; el ánimo, que no está en el servidor, sigue pendiente ({barra()})")
    finally:
        # se deja como estaba para quien venga detrás, pase lo que pase
        pg.js("const est = estadoAjustes({ tipo: 'video', pid: APP.light.video.pid });"
              " est.animoPedido = ''; olvidarCambiosDelMontaje(est, APP.light.video.pid);")
        api.libre(pid)
        api.put(f"/api/proyectos/{pid}/subtitulos", {"posicion": "auto"})
        api.post(f"/api/proyectos/{pid}/montaje/aplicar", {})
        api.libre(pid)
    pg.sin_errores("los cambios del montaje no se pierden")
    pg.cerrar()


@escenario
def regrabar_un_tramo_dice_la_verdad(navegador, datos):
    """Revisión del rediseño de Crear (21-10-2026), DINERO: «Regrabar este
    tramo · ≈ X» del paso Voz graba ese tramo Y TODOS los que tienen cambios
    sin grabar (`p4_voz.plan_regrabado`), y su precio era una proporción del de
    la toma entera. Ahora el botón dice cuántos más se graban, el precio es el
    del servidor (y ninguno si no lo hay) y la pregunta trae la cifra real,
    pedida antes. Aquí no se graba nada: el plan del servidor se finge y el
    POST se corta."""
    pid, api = datos["video"], datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    # la toma de prueba es UN tramo: en la pantalla se parte en dos (el
    # servidor, que es quien diría qué se graba, se finge abajo)
    secciones = pg.p.evaluate("""() => { const a = APP.light.video.audio || {};
      const bl = ((a.secciones || [])[0] || {}).bloques || [];
      if (bl.length < 2) return [];
      a.secciones = [{ id: 'SB001', bloques: bl.slice(0, 1) }, { id: 'SB002', bloques: bl.slice(1) }];
      return ['SB001', 'SB002']; }""")
    ok(len(secciones) >= 2, f"la toma de prueba se puede partir en dos tramos ({secciones})")
    if len(secciones) < 2:
        pg.cerrar()
        return
    pedida, otra = secciones[0], secciones[1]
    pedidas = []

    def al_pedir(ruta):
        req = ruta.request
        if req.method == "GET" and "/guion/bloques?seccion=" in req.url:
            ruta.fulfill(status=200, content_type="application/json", body=json.dumps({"regrabar": {
                "posible": True, "pendientes": [otra], "orden": [pedida, otra],
                "cambiados": {otra: []}, "caracteres": 400, "usd": 0.09}}))
        elif req.method == "POST" and "/regrabar" in req.url:
            pedidas.append(req.url)
            ruta.fulfill(status=409, content_type="application/json",
                         body=json.dumps({"detail": "prueba: no se graba nada"}))
        else:
            ruta.continue_()
    pg.p.route("**/api/proyectos/**", al_pedir)
    try:
        # el servidor dice que OTRO tramo tiene cambios sin grabar (0,05 $)
        pg.js(f"const v = APP.light.video; v.estructura = Object.assign({{}}, v.estructura, {{ regrabar: "
              f"{{ posible: true, pendientes: ['{otra}'], orden: ['{otra}'], cambiados: {{}}, usd: 0.05 }} }});"
              " v.vista = 'voz'; pintarLight();")
        pg.p.wait_for_timeout(1000)
        boton_pedida = pg.p.locator(f".tramo-voz[data-seccion='{pedida}'] button").filter(has_text="Regrabar").first
        boton_otra = pg.p.locator(f".tramo-voz[data-seccion='{otra}'] button").filter(has_text="Regrabar").first
        texto_pedida = boton_pedida.inner_text() if boton_pedida.count() else ""
        texto_otra = boton_otra.inner_text() if boton_otra.count() else ""
        ok("y 1 más con cambios" in texto_pedida and "$" not in texto_pedida,
           f"el botón de un tramo dice que se graba con el otro pendiente, sin precio inventado ({texto_pedida!r})")
        ok(texto_otra.startswith("Regrabar este tramo") and "0.050 $" in texto_otra and "más" not in texto_otra,
           f"el del tramo pendiente lleva el precio del servidor ({texto_otra!r})")
        pg.aceptar = False
        antes = len(pg.dialogos)
        boton_pedida.click()
        pg.p.wait_for_timeout(1500)
        dicho = " ".join(pg.dialogos[antes:])
        ok("1 tramo más" in dicho and "0.090 $" in dicho,
           f"la pregunta dice los dos tramos y la cifra real del servidor ({dicho[:160]!r})")
        ok(not pedidas, f"y diciendo que no, no graba nada ({pedidas})")
        pg.aceptar = True
    finally:
        pg.p.unroute("**/api/proyectos/**")
    pg.js(f"await abrirVideoLight('{pid}');")
    pg.sin_errores("regrabar un tramo dice la verdad")
    pg.cerrar()


@escenario
def menores_de_la_revision_de_crear(navegador, datos):
    """Revisión del rediseño de Crear (21-10-2026), lo menor: (a) con la cola
    de notas dibujando, Imágenes no ofrece «Poner al día N imágenes» (sale
    apagado); (b) de dos peticiones de los cambios del estilo solo escribe la
    última; (c) un repintado no guarda el nombre a medias de la cabecera."""
    pid, api = datos["video"], datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    apagado = pg.p.evaluate("""() => { const v = APP.light.video;
      v.planes.video = { tareas: 2, coste: { imagenes: 3, imagenes_por_generar: 2, imagenes_hechas: 1,
        usd_por_generar: 0.1, usd_total: 0.15 } };
      const antes = [COLA_IMG.pid, COLA_IMG.actual];
      COLA_IMG.pid = v.pid; COLA_IMG.actual = { plano: 'S001' };
      const boton = n => (n.tagName === 'BUTTON' ? n : n.querySelector('button'));
      const con = boton(accionDeLasImagenes().botones[0]);
      COLA_IMG.pid = antes[0]; COLA_IMG.actual = antes[1];
      const sin = boton(accionDeLasImagenes().botones[0]);
      return [con.innerText || con.textContent, con.disabled, sin.disabled]; }""")
    ok("Poner al día" in apagado[0] and apagado[1] and not apagado[2],
       f"(a) con la cola de notas dibujando, «Poner al día» sale apagado; sin ella, no ({apagado})")
    ultima = pg.p.evaluate("""async () => { const v = APP.light.video;
      const r = await Promise.all([cargarCambiosDelEstilo(v), cargarCambiosDelEstilo(v)]);
      return r; }""")
    ok(ultima == [False, True], f"(b) de dos peticiones de los cambios del estilo solo escribe la última ({ultima})")
    _r, ficha = api.get(f"/api/proyectos/{pid}")
    nombre = (ficha.get("proyecto") or {}).get("nombre") or ""
    pg.pulsar(".cab-video button.renombrar")
    pg.p.wait_for_timeout(400)
    campo = pg.p.locator(".cab-video input.renombrar-campo").first
    campo.fill("Nombre a me")
    campo.dispatch_event("input")
    pg.js("pintarLight();")
    pg.p.wait_for_timeout(800)
    _r, ficha = api.get(f"/api/proyectos/{pid}")
    sigue = pg.p.evaluate("() => (document.querySelector('.cab-video input.renombrar-campo') || {}).value")
    ok(((ficha.get("proyecto") or {}).get("nombre") or "") == nombre and sigue == "Nombre a me",
       f"(c) un repintado no guarda el nombre a medias, y lo escrito sigue en el campo ({sigue!r})")
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(500)
    _r, ficha = api.get(f"/api/proyectos/{pid}")
    ok(((ficha.get("proyecto") or {}).get("nombre") or "") == nombre, "y Escape lo deja como estaba")
    pg.sin_errores("lo menor de la revisión de Crear")
    pg.cerrar()


def _montar_los_cambios(pg):
    """«Montar el vídeo con N cambios» (decisión 9 del rediseño de Crear): el
    único botón que monta lo cambiado en los ajustes del montaje."""
    pg.pulsar(".barra-accion button", "Montar el vídeo con")


def _capas_fijas_del_video(datos):
    """El texto de las capas quietas (los subtitulos) de la version activa."""
    activa = _version_de(datos, "callouts", "").get("activa")
    carpeta = os.path.join(datos["proyectos"], datos["video"], "pasos", "callouts",
                           f"v{activa}", "capas_fijas")
    textos = []
    for nombre in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
        if nombre.endswith(".svg"):
            with open(os.path.join(carpeta, nombre), encoding="utf-8") as fh:
                textos.append(fh.read())
    return "".join(textos)


@escenario
def movimiento_y_efectos_en_el_video(navegador, datos):
    """Rama montaje-movimiento (18-10-2026): debajo del vídeo montado sale
    «Movimiento y efectos»; pasar a dinámico guarda SOLO lo que cambia,
    «Aplicar ahora» rehace las capas y el MP4 con trayectos de cámara, y ni
    las imágenes ni la voz se mueven. Se deja como estaba."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado al día")
    pg.p.wait_for_timeout(1500)
    fila = pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="Movimiento y efectos").first
    ok(fila.count() > 0, "debajo del vídeo sale la fila «Movimiento y efectos»")
    fila.locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(1200)
    ok(pg.visible(".editor-montaje label", "Movimiento de cámara"),
       "con el movimiento de cámara para elegir")
    ok(pg.visible(".editor-montaje .casilla", "Barra de progreso"),
       "los interruptores (gancho, cifras, barra)")
    ok(pg.visible(".editor-montaje summary", "Transiciones"), "y las transiciones")
    assets_antes = _version_de(datos, "assets", "").get("activa")
    voz_antes = _version_de(datos, "voz", "").get("activa")
    render_antes = _version_de(datos, "render", "").get("activa")
    pg.p.locator(".editor-montaje button", has_text="Dinámico").first.click()
    pg.p.wait_for_timeout(1500)
    _r, montaje = api.get(f"/api/proyectos/{pid}/montaje")
    _r, callouts = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    ok(((callouts.get("params") or {}).get("montaje") or {}).get("movimiento") == "dinamico",
       f"pulsar «Dinámico» lo guarda ({(callouts.get('params') or {}).get('montaje')})")
    ok(montaje.get("pendiente"), "y queda pendiente de aplicar")
    ok(pg.p.evaluate("() => ((APP.trabajos[CLAVE_VIDEO_LIGHT] || {}).estado) !== 'ejecutando'"),
       "sin montar nada todavía (decisión 9)")
    ok(pg.esperar(".barra-accion button", "Montar el vídeo con 1 cambio", 10),
       "con «Montar el vídeo con 1 cambio» en la barra")
    pg.captura("montaje_dinamico", entera=False)
    _montar_los_cambios(pg)
    pg.p.wait_for_timeout(2500)
    ok(api.libre(pid, 600), "el montaje termina")
    pg.sin_trabajo(600)
    activa = _version_de(datos, "callouts", "").get("activa")
    ruta_mov = os.path.join(datos["proyectos"], pid, "pasos", "callouts",
                            f"v{activa}", "movimiento.json")
    try:
        with open(ruta_mov, encoding="utf-8") as fh:
            mov = json.load(fh)
    except (OSError, ValueError):
        mov = {}
    movs = mov.get("movimientos") or {}
    movs = list(movs.values()) if isinstance(movs, dict) else list(movs)
    con_trayecto = [e for e in movs if isinstance(e, dict) and e.get("trayecto")]
    ok(con_trayecto, "las capas nuevas llevan trayectos de cámara")
    ok((_version_de(datos, "assets", "").get("activa"),
        _version_de(datos, "voz", "").get("activa")) == (assets_antes, voz_antes),
       "ni una imagen ni la voz se han rehecho")
    ok(_version_de(datos, "render", "").get("activa") != render_antes,
       "y el MP4 se ha vuelto a montar")
    # LAS TRANSICIONES (18-10, visto en el móvil): marcar una no cierra la
    # lista, y las muestras se pintan todas (antes, una WebGL por tarjeta y el
    # navegador tiraba las viejas: carita triste en vez de la muestra).
    pg.p.locator(".editor-montaje summary", has_text="Transiciones").first.click()
    pg.p.wait_for_timeout(800)
    pg.p.locator(".tarjeta-transicion input").first.click()
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate("() => !!(document.querySelector('.transiciones-montaje') || {}).open"),
       "marcar una transición no cierra la lista")
    vacias = pg.p.evaluate("""() => [...document.querySelectorAll('canvas.muestra-transicion')]
      .slice(0, 4).filter(c => { c.scrollIntoView(); return false; }).length""")
    pg.p.wait_for_timeout(1200)
    pintadas = pg.p.evaluate("""() => [...document.querySelectorAll('canvas.muestra-transicion')]
      .slice(0, 4).filter(c => { const d = c.getContext('2d').getImageData(0, 0, 160, 90).data;
        let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n > 1000; }).length""")
    ok(pintadas >= 1 and vacias == 0, f"las muestras de las transiciones se pintan ({pintadas})")
    # se deja como estaba para quien venga detrás
    api.put(f"/api/proyectos/{pid}/montaje", {"transiciones": []})
    # se deja como estaba para quien venga detrás
    api.put(f"/api/proyectos/{pid}/montaje", {"montaje": {"movimiento": "sobrio"}})
    _r, callouts = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    ok("montaje" not in (callouts.get("params") or {}),
       "volver a sobrio quita la clave (regla 1)")
    api.post(f"/api/proyectos/{pid}/montaje/aplicar", {})
    api.libre(pid, 600)
    pg.sin_errores("movimiento y efectos en el vídeo")
    pg.cerrar()


@escenario
def fuente_y_sitio_de_los_subtitulos(navegador, datos):
    """N9 de las notas de mejoras, paso 4: «a los subtítulos corregir fuente,
    estilos, color…, correcciones que no pasen por regenerar las imágenes ni
    la voz». La fuente y el sitio se eligen en el editor de subtítulos, se
    aplican rehaciendo SOLO las capas y el montaje, y «Automática» / «La del
    diseño» quitan la elección: la firma vuelve a la de antes."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado al día")
    _r, antes = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    assets_antes = _version_de(datos, "assets", "").get("activa")
    voz_antes = _version_de(datos, "voz", "").get("activa")
    pg.p.wait_for_timeout(1500)
    pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="💬 Subtítulos").first \
        .locator("button", has_text="Cambiar").click()
    pg.p.wait_for_timeout(800)
    for etiqueta in ("Fuente", "Dónde va"):
        ok(pg.visible(".ajustes-en-video .editor-ajuste label", etiqueta),
           f"el editor de subtítulos trae «{etiqueta}»")
    fila = lambda texto: pg.p.locator(".ajustes-en-video .editor-ajuste .campo").filter(  # noqa: E731
        has=pg.p.locator("label", has_text=texto)).first
    ok(fila("Fuente").locator("button.activo", has_text="La del diseño").count() == 1,
       "sin tocar, «La del diseño» está marcada")
    ok(fila("Dónde va").locator("button.activo", has_text="Automática").count() == 1,
       "y «Automática» también")
    fila("Fuente").locator("button", has_text="Georgia").click()
    pg.p.wait_for_timeout(1200)
    fila("Dónde va").locator("button", has_text="Arriba").click()
    pg.p.wait_for_timeout(1200)
    _r, sub = api.get(f"/api/proyectos/{pid}/subtitulos")
    ok((sub.get("fuente"), sub.get("posicion")) == ("Georgia", "arriba"),
       f"Georgia y arriba quedan guardados ({sub.get('fuente')!r}, {sub.get('posicion')!r})")
    ok(fila("Fuente").locator("button.activo", has_text="Georgia").count() == 1
       and fila("Dónde va").locator("button.activo", has_text="Arriba").count() == 1,
       "y se ven marcados")
    ok(pg.visible(".ajustes-en-video .fila-ajuste", "en Georgia, arriba"),
       "y el resumen de la fila lo dice («en Georgia, arriba»)")
    pg.captura("n9_fuente_y_sitio_de_los_subtitulos", entera=False)
    ok(pg.visible(".barra-accion button", "Montar el vídeo con 1 cambio"),
       "con el vídeo montado, la barra ofrece «Montar el vídeo con 1 cambio»")
    _montar_los_cambios(pg)
    pg.p.wait_for_timeout(2000)
    ok(api.libre(pid), "rehacer capas y montaje termina")
    pg.sin_trabajo(300)
    capas = _capas_fijas_del_video(datos)
    ok('font-family="Georgia"' in capas, "los subtítulos del vídeo ya van en Georgia")
    ok((_version_de(datos, "assets", "").get("activa"), _version_de(datos, "voz", "").get("activa"))
       == (assets_antes, voz_antes), "y las imágenes y la voz siguen en su versión: ni una se paga")
    # VOLVER A SIN ELEGIR: las claves se van y la firma es la de antes
    pg.p.wait_for_timeout(1200)
    if not pg.visible(".ajustes-en-video .editor-ajuste label", "Fuente"):
        pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="💬 Subtítulos").first \
            .locator("button", has_text="Cambiar").click()
        pg.p.wait_for_timeout(800)
    fila("Fuente").locator("button", has_text="La del diseño").click()
    pg.p.wait_for_timeout(1200)
    fila("Dónde va").locator("button", has_text="Automática").click()
    pg.p.wait_for_timeout(1200)
    _r, paso = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    params = paso.get("params") or {}
    ok("subtitulo_fuente" not in params and "subtitulo_posicion" not in params,
       "«La del diseño» y «Automática» quitan las claves (regla 1)")
    ok(paso.get("firma") == antes.get("firma"),
       "y la firma de los subtítulos vuelve a ser la de antes")
    if pg.visible(".barra-accion button", "Montar el vídeo con"):
        _montar_los_cambios(pg)
        pg.p.wait_for_timeout(2000)
    api.libre(pid)
    pg.sin_trabajo(300)
    pg.sin_errores("fuente y sitio de los subtítulos")
    pg.cerrar()


@escenario
def atras_del_movil_dentro_del_studio(navegador, datos):
    """N3 de las notas de mejoras, el resto: el «atrás» del teléfono salía del
    Studio desde cualquier pantalla. Ahora vuelve a la pantalla anterior:
    portada → estilo → portada, y vídeo → parada anterior → portada; y
    «adelante» lo deshace."""
    pid = datos["video"]
    pg = Pagina(navegador, datos)
    pg.js("await cargarGaleriaLight(true); elegirCliente(''); irALight('galeria');")
    pg.p.wait_for_timeout(500)
    ok(pg.visible("h2", "Tus proyectos"), "se empieza en la portada")
    portada = pg.p.evaluate("() => history.length")
    pg.pulsar(".video-light button.abrir", "Padres vs hijos")
    pg.esperar(".pasos-carril button", "Vídeo")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate("() => history.length") > portada,
       "abrir un vídeo deja una entrada en el historial del navegador")
    ir_al_paso(pg, "Guion")
    pg.p.wait_for_timeout(800)
    ir_al_paso(pg, "Vídeo")
    pg.p.wait_for_timeout(800)
    pg.p.go_back()
    pg.p.wait_for_timeout(1000)
    ok(pg.p.evaluate(f"() => APP.light.vista === 'elegido' && APP.light.video.pid === '{pid}'"
                     " && APP.light.video.vista === 'guion'"),
       "«atrás» desde el Vídeo vuelve al Guion del mismo vídeo")
    ok(pg.p.url.startswith(datos["url"]), "sin salir del Studio")
    pg.p.go_back()
    pg.p.wait_for_timeout(1000)
    pg.p.go_back()
    pg.p.wait_for_timeout(1200)
    ok(pg.p.evaluate("() => APP.light.vista === 'galeria'") and pg.visible("h2", "Tus proyectos"),
       "y otro «atrás» vuelve a la portada")
    ok(pg.p.evaluate("() => !APP.light.video.pid"), "con el vídeo cerrado, como «Inicio»")
    pg.p.go_forward()
    pg.p.wait_for_timeout(2500)
    ok(pg.p.evaluate(f"() => APP.light.vista === 'elegido' && APP.light.video.pid === '{pid}'"),
       "«adelante» vuelve a abrir el vídeo")
    # EL ESTILO: desde él, «atrás» vuelve al vídeo y «adelante», al paso Estilo
    ir_al_paso(pg, "Estilo")
    ok(pg.esperar(".light-preset .light-cab h2", "Estado Play Matriz"), "se abre el estilo del vídeo")
    pg.p.go_back()
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate(f"() => APP.light.vista === 'elegido' && APP.light.video.pid === '{pid}'"),
       "«atrás» desde el estilo vuelve al vídeo")
    pg.p.go_forward()
    pg.p.wait_for_timeout(1200)
    ok(pg.esperar(".paso-carril.actual", "Estilo", 10),
       "y «adelante» vuelve al estilo, dentro del vídeo (su paso Estilo)")
    # DOS «ATRÁS» SEGUIDOS mientras el vídeo se abre: manda el último
    pg.js("recordarVideoLight(''); irALight('galeria');")
    pg.p.wait_for_timeout(500)
    pg.js(f"volverAlSitio({{ vista: 'elegido', pid: '{pid}', sub: 'video', cliente: clienteElegido() }}); "
          "volverAlSitio({ vista: 'galeria', cliente: clienteElegido() });")
    pg.p.wait_for_timeout(3000)
    ok(pg.p.evaluate("() => APP.light.vista === 'galeria'"),
       "dos «atrás» seguidos mientras se abre un vídeo acaban donde dice el último")
    # VOLVER A «CREAR» NO BORRA EL TALLER: sin él saldría «Generar» y se pagaría otra vez
    pg.js("APP.light.taller = 'taller_de_prueba'; "
          "volverAlSitio({ vista: 'crear', taller: '', cliente: clienteElegido() });")
    pg.p.wait_for_timeout(800)
    ok(pg.p.evaluate("() => APP.light.taller === 'taller_de_prueba'"),
       "volver a la pantalla de crear conserva el intento a medias («Retomar», no «Generar»)")
    pg.js("APP.light.taller = null; irALight('galeria');")
    pg.sin_errores("atrás del móvil dentro del Studio")
    pg.cerrar()


@escenario
def como_se_pronuncia(navegador, datos):
    """«Cómo se pronuncia» (15-10-2026): la voz leía con acento español las
    marcas en inglés del bloque de los extras («simrace con volante Logitech,
    Meta Quest, Just Dance»). En Configuración hay una lista que se edita en
    una copia y solo se guarda al pulsar «Guardar»."""
    api = datos["api"]
    pg = Pagina(navegador, datos)
    pg.js("conmutarConfig(true);")
    ok(pg.esperar("#config h3", "Cómo se pronuncia", 15), "Configuración trae «Cómo se pronuncia»")
    pg.p.wait_for_timeout(800)
    valores = pg.p.evaluate("""() => [...document.querySelectorAll('.fila-pronunciacion input')]
      .map(i => i.value)""")
    ok("Just Dance" in valores and "Yast Dans" in valores and "Logitech" in valores,
       "ya viene con las marcas de los vídeos (Just Dance, Logitech…)")
    ok(not pg.p.locator(".boton-guardar-pronunciacion").is_enabled(),
       "sin tocar nada, «Guardar» está apagado")
    _r, antes = api.get("/api/pronunciaciones")
    pg.pulsar(".seccion-pronunciacion button", "Añadir una palabra")
    pg.p.wait_for_timeout(300)
    filas = pg.p.locator(".fila-pronunciacion")
    ultima = filas.nth(filas.count() - 1)
    ultima.locator("input").nth(0).fill("Call of Duty")
    ultima.locator("input").nth(1).fill("Col of Diúti")
    pg.p.wait_for_timeout(300)
    _r, sin_guardar = api.get("/api/pronunciaciones")
    ok(sin_guardar.get("lista") == antes.get("lista"), "escribir no guarda nada todavía")
    ok(pg.p.locator(".boton-guardar-pronunciacion").is_enabled(), "y enciende «Guardar»")
    pg.captura("como_se_pronuncia", entera=False)
    pg.p.locator(".boton-guardar-pronunciacion").click()
    pg.p.wait_for_timeout(1200)
    _r, guardada = api.get("/api/pronunciaciones")
    ok({"escrito": "Call of Duty", "dicho": "Col of Diúti"} in (guardada.get("lista") or []),
       "al pulsar «Guardar» queda guardada")
    ok(not pg.p.locator(".boton-guardar-pronunciacion").is_enabled(), "y «Guardar» se apaga")
    # se deja como estaba para quien venga detrás
    api.put("/api/pronunciaciones", {"lista": antes.get("lista")})
    pg.sin_errores("cómo se pronuncia")
    pg.cerrar()

@escenario
def regenerar_audio_dice_su_precio(navegador, datos):
    """D5 (16-10-2026): «Regenerar Audio» vuelve a grabar la voz ENTERA (modo
    'todo') y su precio salía del plan 'pendientes', que con la voz al día era
    0 $. El botón pide el plan del modo con el que lanza, y lo dice. Desde el
    rediseño de Crear (20-10-2026) es «Regrabar la voz entera», en el paso Voz."""
    api, pid = datos["api"], datos["video"]
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=voz&modo=todo")
    entera = float(((plan or {}).get("coste") or {}).get("usd_tts") or 0)
    ok(entera > 0, f"la voz entera tiene precio ({entera} $)")
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'voz'; pintarLight();")
    ok(pg.esperar(".light-voz button", "Regrabar la voz entera", 15),
       "con audio, el paso Voz ofrece «Regrabar la voz entera»")
    pg.p.wait_for_timeout(4500)
    pg.js("pintarLight();")
    pg.p.wait_for_timeout(800)
    visto = pg.p.evaluate("""() => {
      const p = (APP.light.video.planes || {})['voz:todo'] || null;
      return p ? { modo: p.modo, usd: (p.coste || {}).usd_por_generar } : null; }""")
    ok(visto and visto.get("modo") == "todo",
       f"la pantalla pide el plan con el modo con el que lanza ('todo'): {visto}")
    ok(visto and abs(float(visto.get("usd") or 0) - round(entera, 3)) < 1e-6,
       f"y ese plan cobra la voz entera, no 0 $: {visto}")
    # LO QUE SE LEE: con el botón encendido (algo que grabar en 'pendientes',
    # sin tocar el vídeo de las demás escenas), el precio de la voz entera
    pg.js("const v = APP.light.video; "
          "v.planes.voz = Object.assign({}, v.planes.voz, { tareas: 2 }); "
          "PLANES_LIGHT.ultima[v.pid + ':voz'] = Date.now() + 60000; pintarLight();")
    pg.p.wait_for_timeout(500)
    ayuda = pg.p.evaluate("""() => { const b = [...document.querySelectorAll('.light-voz button')]
      .find(x => x.textContent.trim().startsWith('Regrabar la voz entera'));
      const a = b && b.closest('.ayuda-de'); return a ? a.getAttribute('data-ayuda') : ''; }""")
    precio = f"≈ {entera:.2f} $"
    ok(precio in (ayuda or ""), f"la ayuda del botón dice {precio!r}: {ayuda!r}")
    ok("cache" not in (ayuda or ""), "y ya no promete que lo que no cambió sale de la cache")
    pg.sin_errores("regenerar audio dice su precio")
    pg.cerrar()


@escenario
def revertir_y_oir_las_imagenes(navegador, datos):
    """Lo que el dueño encontró el 16-10-2026: «cuando las imágenes regresan a
    una versión anterior no se ven ni se escuchan; "Todo seguido" y "Oírla" no
    funcionan».

    - un solo fallo al pedir las diapositivas las dejaba sin imagen ni mandos
      hasta recargar (ni revertir lo arreglaba): ahora hay «Reintentar»;
    - volver a una versión vuelve a la escena que se miraba, se ve y suena;
    - «Oírla» suena y vuelve a decir «Oírla» al acabar la escena;
    - «Todo seguido» suena con la música de verdad (antes nunca la tuvo);
    - sin voz, «Oírla» lo dice en vez de no hacer nada;
    - una carga vieja no pisa a la nueva;
    - los planes de un vídeo no se quedan en el siguiente;
    - un trabajo que el servidor ya no conoce se da por perdido.
    """
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    # dos versiones de imágenes, para poder volver a la anterior
    _r, ficha = api.get(f"/api/proyectos/{pid}/pasos/assets")
    if len(ficha.get("versiones") or []) < 2:
        r, d = api.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                        {"unidades": ["escena:S002"], "rehacer": True})
        api.esperar(d.get("trabajo_id"), 300)
        _r, ficha = api.get(f"/api/proyectos/{pid}/pasos/assets")
    versiones = sorted(v.get("n") for v in ficha.get("versiones") or [])
    activa = next((v.get("n") for v in ficha.get("versiones") or [] if v.get("activa")), None)
    if not ok(len(versiones) >= 2 and activa,
              f"el vídeo tiene dos versiones de imágenes ({versiones})"):
        return
    anterior = max((n for n in versiones if n < activa), default=None) or \
        next(n for n in versiones if n != activa)

    pg = Pagina(navegador, datos)
    imagen_y_mandos = ("() => { const i = document.querySelector('.previa-marco img');"
                       " return !!(i && i.complete && i.naturalWidth > 0)"
                       " && !!document.querySelector('.previa-mandos'); }")

    def esperar_js(expresion, segundos=20):
        fin = time.time() + segundos
        while time.time() < fin:
            try:
                if pg.p.evaluate(expresion):
                    return True
            except Exception:                                # noqa: BLE001
                pass
            pg.p.wait_for_timeout(300)
        return False

    # 1. UN FALLO AL PEDIRLAS, Y «REINTENTAR»
    cortadas = {"n": 0}

    def cortar_la_primera(ruta):
        cortadas["n"] += 1
        if cortadas["n"] == 1:
            ruta.abort("connectionreset")
        else:
            ruta.continue_()
    pg.p.route("**/previsualizacion", cortar_la_primera)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".caja-error", None, 20), "un microcorte al pedir las imágenes se dice")
    ok(pg.esperar(".light-previa button", "Reintentar", 5),
       "y la caja del error trae «Reintentar»")
    if pg.visible(".light-previa button", "Reintentar"):
        pg.pulsar(".light-previa button", "Reintentar")
    if not ok(esperar_js(imagen_y_mandos), "y al reintentar se ven la imagen y sus mandos"):
        # sin el arreglo solo quedaba recargar la pagina: se recarga para poder
        # mirar lo demas (cada cosa falla por lo suyo, no por arrastre)
        pg.p.unroute("**/previsualizacion")
        pg.p.reload()
        pg.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos",
                               timeout=30000)
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
        esperar_js(imagen_y_mandos)
    pg.p.unroute("**/previsualizacion")

    # 2. VOLVER A LA VERSIÓN ANTERIOR: se ve, suena y sigue en la misma escena
    try:
        pg.p.evaluate("() => { PREVIA.i = 2; repintarVideo(); }")
        escena = pg.p.evaluate("() => escenaPrevia().id")
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();"
              " await refrescarPlanosLight();")
        pg.js("APP.light.video.vista = 'previa'; pintarLight();")
        esperar_js(imagen_y_mandos)
        pg.p.evaluate(f"() => {{ PREVIA.i = PREVIA.ficha.escenas.findIndex(x => x.id === '{escena}'); "
                      "repintarVideo(); }")
        # se espia si la tira se vuelve a pedir: la carpeta que devuelve puede
        # ser la de trabajo (una tanda cortada en otro escenario la deja)
        pg.p.evaluate("() => { window.__tiras = 0; const pedirTira = refrescarPlanosLight; "
                      "refrescarPlanosLight = function () { window.__tiras += 1; "
                      "return pedirTira.apply(this, arguments); }; }")
        pg.p.evaluate(f"async () => {{ await volverAVersionLight('assets', {anterior}); }}")
        ok(esperar_js(imagen_y_mandos), "después de volver a la versión anterior se ve la imagen")
        ok(pg.p.evaluate(f"() => ((PREVIA.ficha || {{}}).escenas || []).some(x => "
                         f"String(x.imagen || '').includes('/v{anterior}/'))"),
           f"y es la de la v{anterior}")
        ok(pg.p.evaluate(f"() => (escenaPrevia() || {{}}).id === '{escena}'"),
           f"y sigue en la escena que se miraba ({escena})")
        pg.p.wait_for_timeout(1500)
        rutas = pg.p.evaluate("() => (APP.light.video.planos || []).map(x => String(x.ruta || ''))")
        ok(pg.p.evaluate("() => window.__tiras") >= 1 and rutas
           and not any(f"/v{activa}/" in r for r in rutas),
           f"y la tira de planos del vídeo se vuelve a pedir: ya no es la de la v{activa} ({rutas[:2]})")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"2. VOLVER A LA VERSIÓN ANTERIOR: se ve, suena y sigue en la misma escena: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    # 3. «OÍRLA» suena, y al acabar la escena el botón vuelve a decir «Oírla»
    try:
        pg.pulsar(".previa-mandos button", "Oírla")
        ok(esperar_js("() => PREVIA.audio && !PREVIA.audio.paused && PREVIA.audio.currentTime > 0", 8),
           "«Oírla» suena después de volver a la versión anterior")
        ok(pg.p.evaluate("() => String(PREVIA.audio.src).includes('/pasos/voz/')"),
           "con la voz del corte (la del render)")
        dura = pg.p.evaluate("() => escenaPrevia().t_out - escenaPrevia().t_in")
        pg.p.wait_for_timeout(int((dura + 1.5) * 1000))
        ok(pg.p.evaluate("() => PREVIA.audio.paused"), "y se para al acabar su escena")
        ok(pg.visible(".previa-mandos button", "Oírla") and not pg.visible(".previa-mandos button", "Parar"),
           "y el botón vuelve a decir «Oírla», no «Parar»")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"3. «OÍRLA» suena, y al acabar la escena el botón vuelve a decir «Oírla»: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    # 4. «TODO SEGUIDO», con la música de verdad
    try:
        # DESDE UNA ESCENA DEL FINAL: el tema subido dura 20 s y el vídeo más,
        # así que la música tiene que ir en bucle, como en el render
        pg.p.evaluate("() => { PREVIA.i = Math.max(0, PREVIA.ficha.escenas.length - 2); "
                      "repintarVideo(); }")
        pg.pulsar(".previa-mandos button", "Todo seguido")
        ok(esperar_js("() => PREVIA.seguido && PREVIA.audio && !PREVIA.audio.paused", 8),
           "«Todo seguido» suena")
        hay_musica = pg.p.evaluate("() => !!(PREVIA.ficha || {}).musica")
        ok(hay_musica, "el vídeo de prueba, con su música subida, la lleva en «Todo seguido»")
        if hay_musica:
            ok(esperar_js("() => PREVIA.musica && !PREVIA.musica.paused && PREVIA.musica.currentTime > 0", 8),
               "y la música suena debajo de la voz")
        if pg.visible(".previa-mandos button", "Parar"):
            pg.pulsar(".previa-mandos button", "Parar")
        ok(pg.p.evaluate("() => PREVIA.audio.paused && (!PREVIA.musica || PREVIA.musica.paused)"),
           "«Parar» lo para todo")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"4. «TODO SEGUIDO», con la música de verdad: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    # 5. SIN VOZ, LO DICE
    try:
        pg.p.evaluate("() => { PREVIA.ficha.audio = null; window.__avisos = []; }")
        pg.pulsar(".previa-mandos button", "Oírla")
        ok(any("no tiene voz" in a for a in pg.avisos()),
           f"sin voz, «Oírla» dice que no hay nada que oír ({pg.avisos()[-1:]})")
        ok(pg.p.evaluate("() => !PREVIA.audio.getAttribute('src')"),
           "y no se queda con la voz de antes")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"5. SIN VOZ, LO DICE: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    # 6. UNA CARGA VIEJA NO PISA A LA NUEVA
    try:
        retenidas = []

        def retener_la_primera(ruta):
            if not retenidas:
                retenidas.append(ruta)
            else:
                ruta.continue_()
        pg.p.route("**/previsualizacion", retener_la_primera)
        pg.p.evaluate("() => { PREVIA.ficha = null; PREVIA.cargando = false; cargarPreviaLight(); }")
        pg.p.wait_for_timeout(800)
        # otra carga mientras la primera sigue en el aire (lo que hace volver a una
        # versión, o cambiar de vídeo): la de antes no vale ya
        pg.p.evaluate("() => { PREVIA.ficha = null; PREVIA.cargando = false; cargarPreviaLight(); }")
        esperar_js("() => !!PREVIA.ficha", 15)
        if retenidas:
            vieja = retenidas[0].fetch()
            cuerpo = vieja.json()
            for x in cuerpo.get("escenas") or []:
                x["id"] = "VIEJA"
            retenidas[0].fulfill(response=vieja, json=cuerpo)
        pg.p.wait_for_timeout(2500)
        ok(pg.p.evaluate("() => !((PREVIA.ficha || {}).escenas || []).some(x => x.id === 'VIEJA')"),
           "una carga que llega tarde no pisa la de después")
        pg.p.unroute("**/previsualizacion")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"6. UNA CARGA VIEJA NO PISA A LA NUEVA: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    # 7. LOS PLANES DE UN VÍDEO NO SE QUEDAN EN EL SIGUIENTE
    try:
        r, d = api.post(f"/api/presets-light/{datos['preset']}/video", {
            "nombre": "Vídeo para cambiar", "duracion_objetivo_s": 30,
            "material": "Un vídeo más, para comprobar que no hereda nada del anterior."})
        otro = (d.get("proyecto") or {}).get("id") or ""
        if ok(bool(otro), f"se crea otro vídeo ({r.status_code})"):
            pg.p.evaluate("() => { APP.light.video.planes = { video: { coste: "
                          "{ otra_calidad: { imagenes: 7, calidad: 'low' } } } }; }")
            quedo = pg.p.evaluate(f"async () => {{ await cargarVideoLight('{otro}'); "
                                  "const p = (APP.light.video.planes || {}).video || {}; "
                                  "return (((p.coste || {}).otra_calidad) || {}).imagenes || 0; }")
            ok(quedo != 7, "al abrir otro vídeo no hereda el aviso de calidad del anterior")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"7. LOS PLANES DE UN VÍDEO NO SE QUEDAN EN EL SIGUIENTE: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    # 8. UN TRABAJO QUE EL SERVIDOR YA NO CONOCE
    try:
        pg.p.evaluate("() => seguirTrabajo('prueba_perdido', 'no-existe-ya', async () => {})")
        ok(esperar_js("() => (APP.trabajos.prueba_perdido || {}).estado === 'error'", 30),
           "un trabajo que el servidor ya no conoce se da por perdido (no se queda «en marcha»)")
        pg.p.evaluate("() => soltarSeguimiento('prueba_perdido')")
        # el error de ese trabajo se dice tambien en la consola: es el que se busca
        pg.errores[:] = [e for e in pg.errores if "ya no conoce este trabajo" not in e]
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"8. UN TRABAJO QUE EL SERVIDOR YA NO CONOCE: se cortó ({type(fallo).__name__}: {str(fallo)[:160]})")

    pg.captura("revertir_y_oir_las_imagenes", entera=False)
    pg.sin_errores("revertir y oír las imágenes")
    pg.cerrar()
    # y se deja como estaba, para lo que venga detrás
    api.post(f"/api/proyectos/{pid}/pasos/assets/revertir", {"version": activa})


@escenario
def editar_a_mano_conserva_la_pausa(navegador, datos):
    """Nota del 16-10-2026: corregir a mano un bloque le quitaba la pausa del
    final (la pastilla «⏸» y su marca: la de sección, la del gancho). Editar
    conserva esa pausa y quita las demás anotaciones, como antes; «Quitar
    pausa» la sigue quitando. Y no deja por regrabar más bloques que antes."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    _r, guion = api.get(f"/api/proyectos/{pid}/pasos/guion")
    params_antes = guion.get("params") or {}
    bid = "B004"
    _r, est = api.get(f"/api/proyectos/{pid}/guion/bloques")
    texto_de = {b.get("id"): b for b in (est.get("bloques") or [])}
    if not ok(bid in texto_de, f"el vídeo de prueba tiene el bloque {bid}"):
        return
    # EL BLOQUE CON SU PAUSA DE FINAL, como sale del redactor en un cambio de
    # tramo: el texto efectivo de ahora más el silencio de cola
    pausa = '<break time="900ms"/>'
    carpeta_voz = os.path.join(datos["proyectos"], pid, "pasos", "voz")
    with open(os.path.join(carpeta_voz, "activa.json"), encoding="utf-8") as fh:
        activa = json.load(fh)["activa"]
    meta = os.path.join(carpeta_voz, f"v{activa}", "audio_meta.json")
    with open(meta, encoding="utf-8") as fh:
        grabado = next(b.get("texto") for b in json.load(fh).get("bloques") or []
                       if b.get("id") == bid)
    bloques = dict((params_antes.get("bloques") or {}))
    bloques[bid] = {"texto": f"{grabado}{pausa}"}
    api.put(f"/api/proyectos/{pid}/pasos/guion/params", {"params": {"bloques": bloques}})

    def por_regrabar():
        _r, e = api.get(f"/api/proyectos/{pid}/guion/bloques")
        cambiados = ((e.get("regrabar") or {}).get("cambiados")) or {}
        return sorted({b for lista in cambiados.values() for b in lista})

    antes = por_regrabar()
    pg = Pagina(navegador, datos)
    try:
        pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'guion'; pintarLight();")
        tarjeta = f'.parrafo-guion[data-bloque="{bid}"]'

        def pulsar_en_bloque(texto):
            # los botones del bloque salen al pasar por encima, como con el ratón
            pg.p.locator(tarjeta).first.hover()
            pg.pulsar(f"{tarjeta} button", texto)
        ok(pg.esperar(f"{tarjeta} .pastilla.pausa", "al final", 20),
           f"{bid} enseña su pausa del final antes de tocarlo")
        pulsar_en_bloque("Editar a mano")
        area = pg.p.locator(f"{tarjeta} textarea").first
        area.fill(area.input_value().rstrip(".") + ", corregido a mano.")
        pg.p.wait_for_timeout(1200)
        pulsar_en_bloque("Hecho")
        pg.p.wait_for_timeout(1500)
        ok(pg.esperar(f"{tarjeta} .pastilla.pausa", "al final", 15),
           "después de editar a mano, el bloque conserva la pastilla de su pausa del final")
        _r, guion = api.get(f"/api/proyectos/{pid}/pasos/guion")
        guardado = (((guion.get("params") or {}).get("bloques") or {}).get(bid) or {}).get("texto") or ""
        ok("corregido a mano" in guardado and guardado.endswith(pausa),
           f"y lo guardado es lo escrito más esa pausa: {guardado[-80:]!r}")
        despues = por_regrabar()
        ok(set(despues) <= set(antes) | {bid},
           f"y no deja por regrabar más bloques que antes ({antes} -> {despues})")
        # LA CORRECCIÓN DE ORTOGRAFÍA guarda el texto CON sus marcas (la pausa
        # ya va dentro): no se le pega otra (revisión independiente del 16-10)
        pg.js(f"guardarBloqueLight('{bid}', {json.dumps(guardado.replace('corregido a mano', 'corregido por ortografía'))}, undefined, false);")
        pg.p.wait_for_timeout(2000)
        _r, guion = api.get(f"/api/proyectos/{pid}/pasos/guion")
        orto = (((guion.get("params") or {}).get("bloques") or {}).get(bid) or {}).get("texto") or ""
        ok("por ortografía" in orto and orto.count("<break") == 1,
           f"corregir la ortografía no duplica la pausa: {orto[-90:]!r}")
        # «QUITAR PAUSA» LA SIGUE QUITANDO, y una edición después no la resucita
        pulsar_en_bloque("Quitar pausa")
        pg.p.wait_for_timeout(2500)
        ok(not pg.visible(f"{tarjeta} .pastilla.pausa"), "«Quitar pausa» la quita")
        pulsar_en_bloque("Editar a mano")
        area = pg.p.locator(f"{tarjeta} textarea").first
        area.fill(area.input_value() + " Otra vez.")
        pg.p.wait_for_timeout(1200)
        pulsar_en_bloque("Hecho")
        pg.p.wait_for_timeout(1500)
        ok(not pg.visible(f"{tarjeta} .pastilla.pausa"),
           "y editar después no la vuelve a poner")
        pg.sin_errores("editar a mano conserva la pausa")
    finally:
        pg.cerrar()
        # se deja el guion como estaba, para lo que venga detrás
        api.put(f"/api/proyectos/{pid}/pasos/guion/params",
                {"params": params_antes, "reemplazar": True})


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


# ======================================================================
# PUBLICAR (rama `publicar-redes-1`, 16-10-2026). Tramo propio y al final,
# para no chocar con las otras ramas que tocan este fichero. El servidor del
# recorrido corre con ESTUDIO_SIMULAR=1: Upload-Post es el SIMULADO y los
# textos los escribe el doble de Claude, así que nada sale a ninguna red.

@escenario
def publicar_en_redes(navegador, datos):
    """La barra de módulos (Crear sigue siendo lo que se abre), «Enviar a
    Publicar» debajo del vídeo montado, la ficha con los textos por red,
    programar con su confirmación delante, la cola y el calendario, las
    cuentas, y volver a Crear donde se dejó. Y en el móvil, que cabe."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    ok(pg.esperar("#barra-modulos .boton-modulo", "Publicar"), "arriba sale la barra de módulos")
    ok(pg.visible("#barra-modulos .boton-modulo.activo", "Crear"),
       "y se abre en Crear, la pantalla de siempre")
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado")
    ok(pg.esperar(".bloque-publicar-video a", "Enviar a Publicar", 15),
       "debajo del vídeo montado sale «Enviar a Publicar»")
    pg.pulsar(".bloque-publicar-video a", "Enviar a Publicar")
    ok(pg.esperar(".ficha-publicar .nombre-ficha", segundos=15), "abre la ficha del vídeo en Publicar")
    ok(not pg.visible("#panel"), "y el panel de Crear queda escondido detrás")
    ok(pg.visible("#barra-modulos .boton-modulo.activo", "Publicar"), "con «Publicar» marcado")
    ok(pg.visible(".caja-aviso", "SIMULADO"), "avisa de que Upload-Post es el simulado")

    # el perfil del proyecto del vídeo, por la API (Cuentas y ajustes se mira abajo)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    r, _d = api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    ok(r.status_code == 200, f"el proyecto del vídeo tiene perfil de Upload-Post ({r.status_code})")
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok", "instagram", "youtube"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    pg.js("await cargarPublicar();")
    ok(pg.esperar(".ficha-publicar .caja-aviso", "sin cuenta conectada", 10),
       "una red sin cuenta conectada (Facebook) se avisa")
    pg.p.locator(".casilla-red", has_text="Facebook").locator("input").first.uncheck()
    pg.p.wait_for_timeout(1200)

    pg.pulsar(".ficha-publicar button", "Que Claude escriba los textos")
    fin = time.time() + 25
    while time.time() < fin and not pg.p.evaluate(
            "() => !!(PUB.ficha && !PUB.ficha.escribiendo && PUB.ficha.textos && PUB.ficha.textos.tiktok)"):
        pg.p.wait_for_timeout(500)
    pg.p.wait_for_timeout(800)
    ok(pg.esperar(".texto-red h3", "TikTok", 10), "un bloque de texto por red elegida")
    valor = pg.p.evaluate("() => (document.querySelector('.texto-red[data-red=tiktok] textarea') || {}).value || ''")
    ok(valor.startswith("[TikTok]"), f"con el texto que escribió Claude (el doble): {valor[:40]!r}")
    ok(pg.visible(".texto-red button", "Copiar texto"), "cada red con su «Copiar texto»")
    # la guía y «Revisar» de cada red, como los campos de Crear
    pg.p.locator('.texto-red[data-red="tiktok"] .boton-guia').first.click()
    ok(pg.esperar("#ventana-guia h2", "Texto para TikTok", 10), "«✦ Guía» abre la guía de TikTok")
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(400)
    pg.p.locator('.texto-red[data-red="tiktok"] button', has_text="Revisar").first.click()
    ok(pg.esperar('.texto-red[data-red="tiktok"] .revision-publicar', segundos=40),
       "«✓ Revisar» enseña la revisión del texto contra su guía")
    pg.p.wait_for_timeout(2500)
    pg.p.locator('.texto-red[data-red="tiktok"]').first.scroll_into_view_if_needed()
    pg.captura("publicar_revisar")
    ok(pg.visible(".ficha-publicar a.boton-enlace", "Descargar MP4"), "y «Descargar MP4»")

    # editar a mano se guarda solo
    caja = pg.p.locator(".texto-red[data-red=instagram] textarea").first
    caja.fill("Reel escrito a mano para la prueba")
    pg.p.locator(".ficha-publicar h3").first.click()
    pg.p.wait_for_timeout(2000)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    ok((ficha.get("textos", {}).get("instagram") or {}).get("descripcion") == "Reel escrito a mano para la prueba",
       "lo escrito a mano se guarda solo")
    ok(pg.visible(".texto-red .ortografia-campo button", "Revisar ortografía"),
       "cada red trae «Revisar ortografía» de lo que se publica")

    # programar, con la confirmación delante
    manana = pg.p.evaluate("() => PUB.ficha.hora_sugerida")
    ok(bool(manana), f"propone la hora por defecto del proyecto: {manana}")
    antes = len(pg.dialogos)
    pg.pulsar(".cuando-publicar button", "Programar")
    ok(len(pg.dialogos) > antes and "hora de Lima" in pg.dialogos[-1],
       "antes de enviar pide confirmarlo, con las redes y la hora de Lima")
    # desde el 20-10 la ficha se cierra al programar y vuelve a la cola con un
    # aviso; «Volver a la ficha» la abre otra vez (publicar_arreglos_del_20_10)
    ok(pg.esperar(".aviso-tras-envio button", "Volver a la ficha", 20), "al programar vuelve a la cola, con su aviso")
    pg.pulsar(".aviso-tras-envio button", "Volver a la ficha")
    fin = time.time() + 20
    while time.time() < fin and not pg.visible(".ficha-publicar .fila-envio .pastilla", "programado"):
        pg.p.wait_for_timeout(500)
    ok(pg.visible(".ficha-publicar .fila-envio .pastilla", "programado"), "y queda programado en la lista de envíos")
    ok(pg.visible(".ficha-publicar .fila-envio button", "Cancelar"), "con su «Cancelar»")
    pg.captura("publicar_ficha")

    # la cola y el calendario
    pg.pulsar(".pestanas-publicar button", "Cola y calendario")
    ok(pg.esperar(".calendario-publicar .dia-publicar", segundos=10), "la semana, día a día")
    # un domingo después de la hora del proyecto, lo programado cae el lunes:
    # en la semana SIGUIENTE (fallaba solo los domingos por la noche, 18-10)
    if not pg.esperar(".calendario-publicar .envio-dia", segundos=5):
        pg.pulsar('button[title="Semana siguiente"]')
    ok(pg.esperar(".calendario-publicar .envio-dia", segundos=10), "con lo programado en su día")
    ok(pg.visible(".fila-listo", ""), "y los vídeos listos para publicar")
    pg.captura("publicar_cola")

    # resultados (las métricas)
    pg.pulsar(".pestanas-publicar button", "Resultados")
    ok(pg.esperar(".cifras-publicar .cifra", segundos=10), "Resultados: las cifras del proyecto")
    ok(pg.visible(".resultados-publicar button", "Actualizar"), "con su «Actualizar»")
    ok(pg.visible(".tabla-redes .fila-red", "TikTok"), "y una fila por red")
    pg.captura("publicar_resultados")

    # cuentas y ajustes
    pg.pulsar(".pestanas-publicar button", "Cuentas y ajustes")
    ok(pg.esperar(".proyecto-publicar h3", segundos=10), "cada proyecto con su perfil y sus cuentas")
    ok(pg.visible(".cuentas-proyecto .pastilla", "TikTok"), "y qué cuentas tiene conectadas")
    pg.p.locator(".ajustes-fijos > summary").first.click()
    ok(pg.esperar(".ajustes-fijos .boton-guia", segundos=5), "el tono de los textos tiene su «✦ Guía»")
    ok(pg.visible(".ajustes-fijos button", "Revisar"), "y su «✓ Revisar»")
    tono = pg.p.locator(".ajustes-fijos textarea[data-tono]").first
    tono.fill("CÓMO SUENA: de tú, cercano. EMOJIS: uno.")
    pg.p.wait_for_timeout(1600)
    pg.p.locator(".ajustes-fijos button", has_text="Revisar").first.click()
    ok(pg.esperar(".ajustes-fijos .revision-publicar", segundos=40),
       "«Revisar» el tono: el bloque sigue abierto y enseña la revisión")
    ok(pg.p.locator(".ajustes-fijos textarea[data-tono]").first.input_value().startswith("CÓMO SUENA: de tú"),
       "y el tono escrito sigue ahí tras repintar")
    pg.captura("publicar_cuentas")

    # la clave, en Configuración
    pg.js("conmutarConfig(true);")
    ok(pg.esperar("#cuerpo-config h3", "Publicar en redes", 10),
       "Configuración tiene la casilla de la clave de Upload-Post")
    pg.js("conmutarConfig(false);")

    # Inicio y Automatizar
    pg.pulsar("#barra-modulos .boton-modulo", "Inicio")
    # desde `diseno-crearia` (19-10-2026), el panel mixto
    ok(pg.esperar(".inicio-modulos .tarjeta-saludo h1", "Hola", 10), "Inicio: el saludo del panel")
    ok(pg.esperar(".inicio-modulos h3", "Te necesitan", 10), "y «Te necesitan»")
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    # desde la rama `parrilla` (17-10), Automatizar es la Parrilla de guiones
    ok(pg.esperar(".automatizar.parrilla", segundos=10), "Automatizar abre la Parrilla")

    # de vuelta a Crear: SIEMPRE «Tus proyectos» (decisión del dueño, 19-10-2026;
    # hasta entonces volvía al vídeo donde se había dejado)
    pg.pulsar("#barra-modulos .boton-modulo", "Crear")
    ok(pg.esperar("h2", "Tus proyectos", 10), "volver a Crear abre «Tus proyectos»")
    ok(not pg.p.evaluate("() => (APP.light.video || {}).pid"), "con ningún vídeo abierto")

    # «atrás» del móvil vuelve a Publicar
    pg.p.go_back()
    pg.p.wait_for_timeout(1200)
    ok(pg.p.evaluate("() => MODULOS.actual") != "crear", "«atrás» vuelve al módulo de antes")
    pg.sin_errores("publicar en redes")
    pg.cerrar()

    # en el móvil
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="publicar móvil")
    for seccion_pub in ("cola", "cuentas", "resultados"):
        pg.js(f"PUB.seccion = '{seccion_pub}'; irAModulo('publicar');")
        pg.p.wait_for_timeout(1500)
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(ancho <= 2, f"Publicar ({seccion_pub}) cabe en un móvil sin salirse por los lados ({ancho}px)")
    pg.js(f"abrirPublicarVideo('{pid}');")
    pg.p.wait_for_timeout(2000)
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"y la ficha de un vídeo también ({ancho}px)")
    caja = pg.p.evaluate("() => { const b = document.querySelector('#barra-modulos'); "
                         "return b ? [b.scrollWidth, b.clientWidth] : [0, 0]; }")
    ok(caja[0] <= caja[1] + 2, f"la barra de módulos cabe entera en 390 px ({caja})")
    pg.captura("publicar_movil", entera=False)
    texto = pg.p.evaluate("() => document.querySelector('#modulo').innerText")
    malos = sorted(set(x.group(0) for x in TEXTOS_MALOS.finditer(texto)))
    ok(not malos, f"sin «undefined», «NaN» ni «null» en Publicar ({malos})")
    pg.sin_errores("publicar en el móvil")
    pg.cerrar()


# Lo que salió probando Publicar en el servidor el 16-10-2026 (rama
# `publicar-arreglos-1`): cada fallo, como comprobación.
@escenario
def publicar_lo_del_16_de_octubre(navegador, datos):
    """El perfil se apunta con lo escrito y la tarjeta se repinta sola (sin F5
    salían igual «Crear perfil» y nada de «Ver cuentas»); «Que Claude escriba
    los textos» enseña que escribe y su fallo con «Reintentar»; «Publicar»
    dice por qué no se puede; la portada; dónde ya salió; y la cola con
    filtros y mes."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    # se sostiene solo (--solo): perfil con cuentas, tres redes y algo programado
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok", "instagram", "youtube"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok", "instagram", "youtube"]})
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    if not any(e.get("estado") == "programado" for e in ficha.get("envios", [])):
        api.put(f"/api/publicar/videos/{pid}", {"textos": {
            "tiktok": {"descripcion": "TikTok de prueba"}, "instagram": {"descripcion": "Reel de prueba"},
            "youtube": {"titulo": "Vídeo de prueba", "descripcion": "YouTube de prueba"}}})
        api.post(f"/api/publicar/videos/{pid}/enviar", {"redes": ["tiktok"], "modo": "programar",
                                                         "cuando": ficha.get("hora_sugerida"), "confirmado": True})
        time.sleep(2)
    original = (ficha.get("ajustes") or {}).get("perfil") or ""
    ok(bool(original), f"se parte de un proyecto con perfil ({original})")
    pg = Pagina(navegador, datos)

    # --- el perfil, sin recargar
    api.put(f"/api/publicar/proyectos/{cid}", {"perfil": ""})
    pg.js("PUB.seccion = 'cuentas'; irAModulo('publicar');")
    pg.p.wait_for_timeout(1500)
    tarjeta = f'.proyecto-publicar:has(input[data-perfil="{cid}"])'
    ok(pg.esperar(f"{tarjeta} button", "Crear perfil", 10), "sin perfil: «Crear perfil»")
    ok(not pg.visible(f"{tarjeta} button", "Ver cuentas"), "y todavía sin «Ver cuentas»")
    pg.p.locator(f'input[data-perfil="{cid}"]').fill("Recorrido_Perfil")
    pg.pulsar(f"{tarjeta} button", "Crear perfil")
    ok(pg.esperar(f"{tarjeta} button", "Ver cuentas", 10),
       "«Crear perfil» con el nombre escrito: «Ver cuentas» sale SIN recargar")
    ok(pg.visible(f"{tarjeta} button", "Conectar"), "y «Conectar» también")
    _r, ajustes = api.get("/api/publicar/proyectos")
    fila = next((x for x in ajustes.get("proyectos", []) if x["id"] == cid), {})
    ok((fila.get("ajustes") or {}).get("perfil") == "Recorrido_Perfil",
       "se creó con lo escrito en el campo (no el cuerpo vacío)")
    # elegir el de antes del desplegable de la cuenta
    pg.pulsar(f"{tarjeta} button", "Elegir de mi cuenta")
    ok(pg.esperar(f"{tarjeta} select[data-elegir-perfil]", segundos=10),
       "«Elegir de mi cuenta»: el desplegable con los perfiles de Upload-Post")
    pg.p.locator(f"{tarjeta} select[data-elegir-perfil]").select_option(original)
    pg.p.wait_for_timeout(1500)
    ok(pg.p.locator(f'input[data-perfil="{cid}"]').input_value() == original,
       "elegir uno lo apunta y la tarjeta se repinta con él")
    ok(pg.esperar(f"{tarjeta} .cuentas-proyecto .pastilla", "TikTok", 10), "con sus cuentas, ya miradas")
    # escrito en mayúsculas y con Enter: lo encuentra
    campo = pg.p.locator(f'input[data-perfil="{cid}"]')
    campo.fill(original.upper())
    campo.press("Enter")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.locator(f'input[data-perfil="{cid}"]').input_value() == original,
       "«Usar este perfil» (Enter) en mayúsculas encuentra el de Upload-Post")
    pg.p.locator(f"{tarjeta} .ajustes-fijos > summary").first.click()
    ok(pg.esperar(f"{tarjeta} .ajustes-fijos .ajuste-emojis", "Emojis en los textos", 5),
       "en lo fijo, el nivel de «Emojis en los textos» (rama textos-emojis: antes un sí/no)")
    pg.captura("publicar_perfil")

    # --- los textos: escribiendo y el fallo con «Reintentar»
    marca = os.path.join(datos["proyectos"], "_sistema", "publicar", "_fallar_textos")
    os.makedirs(os.path.dirname(marca), exist_ok=True)
    with open(marca, "w", encoding="utf-8") as fh:
        fh.write("1")
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".ficha-publicar .nombre-ficha", segundos=15), "la ficha del vídeo")
    pg.pulsar(".ficha-publicar button", "Que Claude escriba los textos")
    ok(pg.esperar(".estado-textos .escribiendo-textos", "Claude está escribiendo", 5),
       "mientras escribe, se ve «Claude está escribiendo los textos…»")
    ok(pg.esperar(".estado-textos .caja-error", "no se han podido escribir", 20),
       "si falla, el motivo se ve…")
    ok(pg.visible(".estado-textos button", "Reintentar"), "…con «Reintentar»")
    os.remove(marca)
    pg.pulsar(".estado-textos button", "Reintentar")
    fin = time.time() + 20
    while time.time() < fin and (pg.visible(".estado-textos .caja-error")
                                 or pg.visible(".estado-textos .escribiendo-textos")):
        pg.p.wait_for_timeout(500)
    ok(not pg.visible(".estado-textos .caja-error") and not pg.visible(".estado-textos .escribiendo-textos"),
       "«Reintentar» los escribe y el aviso se va")
    ok(pg.visible(".texto-red .meta", "PRIMERA LÍNEA"),
       "Instagram y TikTok explican que su «título» es la primera línea")

    # --- «Publicar» dice por qué no, antes de pulsar
    pg.p.locator(".cuando-publicar input[type=radio]").first.check()
    pg.p.wait_for_timeout(600)
    caja = pg.p.locator(".texto-red[data-red=instagram] textarea").first
    caja.fill("")
    pg.p.locator(".ficha-publicar h3").first.click()
    pg.p.wait_for_timeout(1800)
    ok(pg.esperar(".motivo-no-publicar", "Falta el texto de Instagram", 5),
       "sin texto de Instagram, el motivo se ve al lado del botón")
    ok(pg.p.locator(".cuando-publicar button.primario").first.is_disabled(),
       "y «Publicar ahora» está desactivado")
    caja = pg.p.locator(".texto-red[data-red=instagram] textarea").first
    caja.fill("Reel otra vez escrito")
    pg.p.locator(".ficha-publicar h3").first.click()
    pg.p.wait_for_timeout(1800)
    ok(not pg.visible(".motivo-no-publicar", "Instagram"), "con el texto, el motivo se va")

    # --- la portada
    ok(pg.esperar(".portada-publicar img.vista-portada", segundos=10), "la portada, con su vista")
    cargada = pg.p.evaluate("() => new Promise(ok => { const i = document.querySelector('.vista-portada'); "
                            "if (i.complete) ok(i.naturalWidth); else { i.onload = () => ok(i.naturalWidth); "
                            "i.onerror = () => ok(0); } })")
    ok(cargada > 0, f"la vista es un fotograma de verdad ({cargada}px)")
    pg.p.evaluate("() => { const r = document.querySelector('.portada-publicar input[type=range]'); "
                  "r.value = 1000; r.dispatchEvent(new Event('input')); }")
    pg.pulsar(".portada-publicar button", "Usar este fotograma")
    pg.p.wait_for_timeout(1200)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    ok((ficha.get("portada") or {}).get("ms") == 1000, "«Usar este fotograma» lo guarda")
    ok(pg.visible(".portada-publicar .meta", "Fotograma del segundo 1.0"), "y lo dice")

    # --- dónde ya salió (lo programado en el tramo de antes)
    ok(pg.esperar(".resumen-publicado", "En camino", 10),
       "la ficha dice arriba lo que ya va a salir y en qué redes")
    ok(pg.visible(".redes-ficha .pastilla", "programado"), "y cada red, su último estado al lado")
    pg.captura("publicar_ficha_arreglos")

    # --- la cola: filtros, buscador y mes
    pg.pulsar(".pestanas-publicar button", "Cola y calendario")
    ok(pg.esperar(".filtros-cola input.buscar-cola", segundos=10), "la cola tiene buscador")
    ok(pg.visible(".filtros-cola select", ""), "y filtros por proyecto, estilo, estado y fecha")
    pg.p.locator(".filtros-cola input.buscar-cola").fill("zzzz-no-existe")
    pg.p.wait_for_timeout(900)
    ok(pg.esperar(".cola-publicar .meta", "Ningún vídeo cumple", 5), "buscar algo que no hay lo dice")
    ok(pg.p.evaluate("() => document.activeElement && document.activeElement.classList.contains('buscar-cola')"),
       "y se puede seguir escribiendo (el buscador no pierde el foco)")
    pg.p.locator(".filtros-cola input.buscar-cola").fill("")
    pg.p.wait_for_timeout(900)
    ok(pg.esperar(".fila-listo", segundos=5), "al borrar, vuelven los vídeos")
    pg.pulsar(".vista-cal button", "Mes")
    ok(pg.esperar(".calendario-mes .cab-semana", segundos=10), "la vista de mes")
    n = pg.p.locator(".calendario-mes .dia-publicar").count()
    ok(n == 42, f"seis semanas, como un calendario de pared ({n} días)")
    ok(pg.esperar(".calendario-mes .envio-dia", segundos=5), "con lo programado en su día")
    pg.captura("publicar_mes")
    pg.pulsar(".vista-cal button", "Semana")
    ok(pg.esperar(".calendario-publicar:not(.calendario-mes) .dia-publicar", segundos=10), "y de vuelta a la semana")
    pg.sin_errores("lo del 16 de octubre")
    pg.cerrar()

    # el mes en el móvil
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="publicar mes móvil")
    pg.js("PUB.seccion = 'cola'; PUB.vistaCal = 'mes'; PUB.mes = ''; PUB.desde = ''; irAModulo('publicar');")
    pg.p.wait_for_timeout(1500)
    pg.js("PUB.mes = mesDeHoyPublicar(); PUB.desde = inicioCalendarioPublicar('mes', PUB.mes); await cargarPublicar();")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"el mes cabe en un móvil ({ancho}px)")
    pg.js("PUB.vistaCal = 'semana'; PUB.desde = '';")
    pg.sin_errores("el mes en el móvil")
    pg.cerrar()


@escenario
def publicar_textos_con_el_cursor_en_un_campo(navegador, datos):
    """17-10, en el servidor: Claude escribió los textos (lo dice el log) y la
    ficha siguió vacía con «Claude está escribiendo…». Con el cursor en un
    campo de texto mientras escribe, los textos tienen que aparecer igual."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok", "instagram"], "textos": {
        "tiktok": {"descripcion": ""}, "instagram": {"descripcion": ""}}})
    marca = os.path.join(datos["proyectos"], "_sistema", "publicar", "_textos_lentos")
    os.makedirs(os.path.dirname(marca), exist_ok=True)
    with open(marca, "w", encoding="utf-8") as fh:
        fh.write("1")
    pg = Pagina(navegador, datos)
    try:
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".ficha-publicar .nombre-ficha", segundos=15), "la ficha del vídeo")
        pg.pulsar(".ficha-publicar button", "Que Claude escriba los textos")
        ok(pg.esperar(".escribiendo-textos", "lleva", 5), "«escribiendo», con cuánto lleva desde el principio")
        # el cursor en el texto de Instagram mientras Claude escribe
        pg.p.locator(".texto-red[data-red=instagram] textarea").first.click()
        fin = time.time() + 25
        valor = ""
        while time.time() < fin:
            valor = pg.p.evaluate("() => (document.querySelector('.texto-red[data-red=tiktok] textarea') || {}).value || ''")
            if valor:
                break
            pg.p.wait_for_timeout(500)
        ok(valor.startswith("[TikTok]"), f"los textos aparecen aunque haya un campo con el cursor: {valor[:30]!r}")
        ok(not pg.visible(".escribiendo-textos"), "y el aviso de «escribiendo» se va")
        pg.sin_errores("textos con el cursor en un campo")
    finally:
        os.remove(marca)
        pg.cerrar()


# ======================================================================
# PARRILLA (rama `parrilla`, 17-10-2026). Tramo propio y al final, como el
# de Publicar. El servidor corre con ESTUDIO_SIMULAR=1: los guiones los
# convierte y los escribe el doble de Claude (`parrilla._claude_simulado`).

def _docx_de_prueba(ruta, parrafos):
    import zipfile                                           # noqa: PLC0415
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    cuerpo = "".join(f"<w:p><w:r><w:t>{x}</w:t></w:r></w:p>" for x in parrafos)
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{cuerpo}</w:body></w:document>')


@escenario
def parrilla_de_guiones(navegador, datos):
    """Automatizar → Parrilla: escribir uno con la plantilla, pedir guiones a
    Claude, subir un Word, la ficha (cambiar el uso, la guía) y «Pasar al
    Encargo», que llena «Un vídeo nuevo» en Crear sin crear nada. Y en el
    móvil con el tema claro, que cabe."""
    api = datos["api"]
    cid = datos["cliente"]
    _r, antes = api.get("/api/proyectos")
    n_antes = len((antes or {}).get("proyectos") or [])
    pg = Pagina(navegador, datos)
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    ok(pg.esperar(".parrilla h2", "Automatizar"), "Automatizar abre la Parrilla (ya no es una pestaña vacía)")
    ok(pg.visible(".parrilla .pestanas-publicar button", "Piloto automático"),
       "el piloto automático sale como «próximamente»")
    ok(pg.visible(".parrilla-opcional", "opcional"), "y dice que la Parrilla es opcional")
    pg.js(f"elegirProyectoParrilla('{cid}');")
    pg.p.wait_for_timeout(800)
    ok(pg.esperar(".vacio-parrilla h3", "Todavía no hay guiones"), "un proyecto sin guiones lo dice")

    # escribir uno con la plantilla, sin Claude
    pg.pulsar(".vacio-parrilla button", "Añadir guiones")
    pg.pulsar(".origen-parrilla button", "Escribir o pegar")
    pg.pulsar(".anadir-parrilla button", "Escribir uno con la plantilla")
    valor = pg.p.evaluate("() => (document.querySelector('#modulo [data-foco=parrilla-pegar]') || {}).value || ''")
    ok(valor.startswith("G01 — [Título]"), f"la plantilla del formato en la caja: {valor[:24]!r}")
    ok(pg.p.locator(".anadir-parrilla input[type=checkbox]").first.is_checked(),
       "y marcado «Ya está en el formato»")
    guion = ("EP01 — Fregadero simple o doble\nCliente / proyecto: Cocinas\nUso: exacto\nRed: TikTok\n"
             "Formato: vertical\nDuración: 45 s\nObjetivo: medidas\nCTA: Escríbenos\nTono: cercano\n\n"
             "ESCENA 1\nVisual: una bandeja\nVoz: «Por fuera miden igual.»\n\n"
             "PARA EL ENCARGO\n- Material: Por fuera miden igual. Por dentro, no.\n"
             "- Indicaciones: una sola idea\n- Llamadas a la acción: Escríbenos\n"
             "- Duración: 45 s · Formato: vertical\n\nAVISOS\n- ninguno")
    pg.p.locator("#modulo [data-foco=parrilla-pegar]").fill(guion)
    pg.p.locator(".anadir-parrilla input[data-foco=parrilla-nombre]").fill("Octubre")
    pg.pulsar(".anadir-parrilla button.primario", "Guardar en la Parrilla")
    ok(pg.esperar(".fila-guion .titulo-guion", "EP01 — Fregadero simple o doble", 10),
       "guardado en la Parrilla, en su matriz")
    ok(pg.visible(".cab-matriz h3", "Octubre"), "con el nombre de la matriz")
    ok(pg.visible(".fila-guion .pastilla", "pendiente"), "pendiente")

    # pedir a Claude (el doble)
    pg.pulsar(".filtros-parrilla button", "Añadir guiones")
    pg.pulsar(".origen-parrilla button", "Pedir a Claude")
    pg.p.locator("#modulo [data-foco=parrilla-peticion]").fill("ideas de alquiler de consolas para fiestas")
    pg.p.locator("#modulo [data-foco=parrilla-cuantos]").fill("3")
    pg.pulsar(".anadir-parrilla button.primario", "Pedir a Claude")
    ok(pg.esperar(".trabajo-parrilla", "guardados", 25), "Claude los escribe y lo dice")
    ok(pg.p.locator(".fila-guion").count() >= 4, "salen en la Parrilla")

    # subir un Word
    docx = os.path.join(datos["base"], "matriz_parrilla.docx")
    _docx_de_prueba(docx, ["Cumpleaños con consola", "---", "Karaoke en casa"])
    pg.pulsar(".filtros-parrilla button", "Añadir guiones")
    pg.pulsar(".origen-parrilla button", "Subir un documento")
    pg.p.set_input_files(".anadir-parrilla input[type=file]", docx)
    pg.p.wait_for_timeout(400)
    ok(pg.visible(".anadir-parrilla .meta", "matriz_parrilla.docx"), "el Word elegido se ve")
    pg.pulsar(".anadir-parrilla button.primario", "Subir y convertir")
    ok(pg.esperar(".cab-matriz h3", "matriz_parrilla", 25), "convertido, en una matriz con el nombre del fichero")
    pg.captura("parrilla_lista")

    # la ficha
    pg.pulsar(".fila-guion .titulo-guion", "EP01")
    ok(pg.esperar(".ficha-parrilla h3", "EP01"), "la ficha del guion")
    ok(pg.visible(".encargo-parrilla .material-parrilla", "Por dentro, no."), "con lo que irá al Encargo")
    ok(pg.visible(".encargo-parrilla .pista", "Esto YA es el guion"), "uso exacto: «Esto YA es el guion»")
    pg.p.locator(".ficha-parrilla .rejilla-parrilla select").first.select_option("adaptar")
    pg.p.wait_for_timeout(1200)
    texto = pg.p.evaluate("() => (document.querySelector('#modulo [data-foco=parrilla-texto]') || {}).value || ''")
    ok("Uso: adaptar" in texto, "cambiar el uso cambia su línea en el texto")
    ok(pg.visible(".encargo-parrilla .dato-encargo", "Escríbenos"), "y la llamada a la acción pasa a ir «al final»")
    pg.p.locator(".ficha-parrilla .boton-guia").first.click()
    ok(pg.esperar("#ventana-guia h2", "El formato del guion", 10), "«✦ Guía» abre la guía del formato")
    ok(pg.visible("#ventana-guia pre", "GUION ORIGINAL"), "con el prompt del anexo para otra IA")
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(300)
    pg.captura("parrilla_ficha")

    # pasar al Encargo: llena «Un vídeo nuevo» y no crea nada
    pg.p.locator(".pasar-encargo select").first.select_option(datos["preset"])
    pg.pulsar(".pasar-encargo button", "Pasar al Encargo")
    fin = time.time() + 10
    while time.time() < fin and not pg.p.evaluate("() => MODULOS.actual === 'crear' && APP.light.vista === 'elegido'"):
        pg.p.wait_for_timeout(300)
    ok(pg.p.evaluate("() => MODULOS.actual === 'crear' && APP.light.vista === 'elegido'"),
       "lleva a Crear → «Un vídeo nuevo»")
    material = pg.p.evaluate("() => (document.querySelector('[data-foco=encargo-material]') || {}).value || ''")
    ok(material == "Por fuera miden igual. Por dentro, no.", f"con el material del guion: {material[:40]!r}")
    ok(pg.p.evaluate("() => APP.light.video.encargo.duracion_objetivo_s") == 45, "la duración")
    ok(pg.p.evaluate("() => APP.light.video.encargo.formato") == "vertical", "el formato")
    ok(pg.p.evaluate("() => APP.light.video.encargo.cta.cta_final.puesto"), "y la llamada a la acción al final")
    ok(any("Encargo lleno" in a for a in pg.avisos()), "y lo dice")
    _r, despues = api.get("/api/proyectos")
    ok(len((despues or {}).get("proyectos") or []) == n_antes, "sin crear ningún vídeo")
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    ok(pg.esperar(".ficha-parrilla .pastilla", "usado", 10) or pg.esperar(".fila-guion .pastilla", "usado", 10),
       "el guion queda «usado»")
    pg.sin_errores("la Parrilla")
    pg.cerrar()

    # el móvil, con el tema claro
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="movil")
    pg.js("document.documentElement.dataset.tema = 'claro';")
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    pg.js(f"elegirProyectoParrilla('{cid}');")
    ok(pg.esperar(".fila-guion", segundos=10), "en el móvil se ven los guiones")
    for seccion_ in ("parrilla", "anadir"):
        pg.js(f"irASeccionParrilla('{seccion_}');")
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth")
        ok(ancho <= 391, f"«{seccion_}» cabe a lo ancho en el móvil ({ancho} px)")
    pg.pulsar(".pestanas-publicar button", "Parrilla")
    pg.pulsar(".fila-guion button", "Abrir")
    ok(pg.esperar(".ficha-parrilla", segundos=10), "la ficha en el móvil")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth")
    ok(ancho <= 391, f"y cabe ({ancho} px)")
    pg.captura("parrilla_movil")
    pg.sin_errores("la Parrilla en el móvil")
    pg.cerrar()


# publicar-redes-2 (17-10-2026): lo que faltaba de las métricas. La retención,
# esta semana y este mes, «Lo que mejor funcionó» y la línea de Inicio. Todo se
# lee de lo guardado: las cifras se piden solo con «Actualizar».
@escenario
def publicar_resultados_y_lo_mejor(navegador, datos):
    """Publicar → Resultados enseña esta semana y este mes frente al anterior,
    la retención (TikTok la da; Instagram no, y no sale «0 %»), «Lo que mejor
    funcionó» con su orden, e Inicio una línea con lo mejor de la semana."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    # se sostiene solo (--solo): perfil con cuentas y algo publicado ya
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok", "youtube"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    publicados = lambda f: [e for e in f.get("envios", [])  # noqa: E731
                            if e.get("estado") == "publicado" and e.get("lote")]
    if not publicados(ficha):
        api.put(f"/api/publicar/videos/{pid}", {"textos": {
            "tiktok": {"descripcion": "TikTok de prueba"},
            "youtube": {"titulo": "Vídeo de prueba", "descripcion": "YouTube de prueba"}}})
        api.post(f"/api/publicar/videos/{pid}/enviar", {"redes": ["tiktok", "youtube"], "modo": "ahora",
                                                         "confirmado": True, "repetir": True})
        for _ in range(15):
            time.sleep(4)
            api.post("/api/publicar/refrescar")
            _r, ficha = api.get(f"/api/publicar/videos/{pid}")
            if len(publicados(ficha)) >= 2:
                break
    ok(len(publicados(ficha)) >= 1, "se parte de algo publicado por Upload-Post (el simulado)")
    # dos lecturas: TikTok no da cifras la primera vez
    api.post(f"/api/publicar/videos/{pid}/metricas", {"forzar": True})
    _r, r = api.post(f"/api/publicar/videos/{pid}/metricas", {"forzar": True})
    tiktok = [e for e in (r.get("ficha") or {}).get("envios", []) if e.get("red") == "tiktok"
              and (e.get("metricas") or {}).get("vista_entera") is not None]
    ok(bool(tiktok), "TikTok trae la fracción que lo vio hasta el final")
    _r, lq = api.get("/api/publicar/lo-que-funciono?dias=7&cuantos=3")
    ok(bool(lq.get("posts")) and all("dia" in p and "hora" in p for p in lq["posts"]),
       "el punto de lectura «lo que funcionó» da los posts con su día y su hora")

    pg = Pagina(navegador, datos)
    pg.js("irAModulo('inicio');")
    ok(pg.esperar(".linea-mejor-semana", "Lo mejor de los últimos 7 días", 10),
       "Inicio: la línea de lo mejor de los últimos 7 días")
    ok(pg.esperar(".linea-mejor-semana button", segundos=10), "con el vídeo, que lleva a su ficha")
    pg.captura("inicio_lo_mejor")
    pg.js("PUB.seccion = 'resultados'; irAModulo('publicar');")
    ok(pg.esperar(".periodos-publicar .tarjeta-periodo", "Esta semana", 10), "Resultados: esta semana")
    ok(pg.visible(".periodos-publicar .tarjeta-periodo", "Este mes"), "y este mes, frente al anterior")
    ok(pg.esperar(".mejores-publicar .fila-mejor", segundos=10), "«Lo que mejor funcionó», con sus posts")
    ok(pg.visible(".resultados-publicar", "lo vio hasta el final"), "la retención, donde la red la da")
    ok(not pg.p.evaluate("() => /(^|[^0-9,])0 % (lo vio hasta el final|visto de media)/.test("
                         "document.querySelector('.resultados-publicar').innerText)"),
       "y nunca un «0 %» inventado")
    pg.p.select_option(".mejores-publicar select", "vista_entera")
    pg.p.wait_for_timeout(2500)
    filas = pg.p.locator(".mejores-publicar .fila-mejor").all_inner_texts()
    # LA LISTA SE REPINTA (fallo visto en la revisión: con el desplegable
    # enfocado se quedaba en el orden de antes): por «hasta el final» solo
    # salen posts que lo dan, y de más a menos
    ok(filas and all("hasta el final" in f for f in filas),
       f"al ordenar por «hasta el final», la lista cambia de verdad ({len(filas)} fila(s))")
    ok(pg.p.eval_on_selector(".mejores-publicar select", "s => s.value") == "vista_entera",
       "y el orden elegido se queda")
    pg.captura("publicar_resultados_redes2")
    pg.sin_errores("resultados y lo mejor")
    pg.cerrar()

    # en el móvil y con el tema claro
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="resultados móvil claro")
    pg.js("document.documentElement.setAttribute('data-tema', 'claro');"
          " PUB.seccion = 'resultados'; irAModulo('publicar');")
    ok(pg.esperar(".periodos-publicar .tarjeta-periodo", segundos=10), "en el móvil también")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"Resultados cabe en un móvil ({ancho}px)")
    pg.js("irAModulo('inicio');")
    ok(pg.esperar(".linea-mejor-semana", segundos=10), "y la línea de Inicio")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"Inicio cabe en un móvil ({ancho}px)")
    pg.captura("inicio_lo_mejor_movil")
    pg.sin_errores("resultados en el móvil")
    pg.cerrar()


# publicar-seo (18-10-2026): el SEO de Publicar. Con el doble de Claude.
@escenario
def publicar_seo(navegador, datos):
    """SEO del proyecto (palabra clave, ubicación que no es un número,
    «Proponer palabras clave»), y en la ficha la nota SEO de cada red,
    «Optimizar SEO con Claude» con su antes/después y «Dame 3 ganchos». En el
    móvil y en los dos temas."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram", "youtube"], "textos": {
        "instagram": {"descripcion": "Reel para el SEO", "cta": "Escríbenos", "hashtags": ["lima"]},
        "youtube": {"titulo": "Un vídeo", "descripcion": "Descripción", "hashtags": ["lima"]}}})
    pg = Pagina(navegador, datos)
    pg.js("PUB.seccion = 'cuentas'; irAModulo('publicar');")
    pg.p.wait_for_timeout(1500)
    tarjeta = f'.proyecto-publicar:has(input[data-perfil="{cid}"])'
    pg.p.locator(f"{tarjeta} .seo-proyecto > summary").first.click()
    ok(pg.esperar(f"{tarjeta} .seo-proyecto button", "Proponer palabras clave", 5),
       "Cuentas y ajustes → SEO de este proyecto, con «Proponer palabras clave»")
    campo = pg.p.locator(f'{tarjeta} input[data-seo="palabra_clave"]').first
    campo.fill("alquiler de consolas en Lima")
    campo.press("Tab")
    pg.p.wait_for_timeout(1200)
    _r, proyectos = api.get("/api/publicar/proyectos")
    fila = next((x for x in proyectos["proyectos"] if x["id"] == cid), {})
    ok((fila.get("ajustes") or {}).get("palabra_clave") == "alquiler de consolas en Lima",
       "la palabra clave del proyecto se guarda")
    ubic = pg.p.locator(f'{tarjeta} input[data-seo="ig_ubicacion"]').first
    ubic.fill("Lima centro")
    ubic.press("Tab")
    pg.p.wait_for_timeout(1000)
    ok("número" in pg.toast().lower(), f"una ubicación de Instagram que no es un número se dice: {pg.toast()[:60]!r}")
    ok(pg.visible(f"{tarjeta} .seo-proyecto select option", "Entretenimiento") or
       pg.p.locator(f"{tarjeta} .seo-proyecto select").count() >= 3, "las categorías e idiomas de YouTube")
    pg.pulsar(f"{tarjeta} .seo-proyecto button", "Proponer palabras clave")
    ok(pg.esperar(f"{tarjeta} .propuesta-palabras", "alquiler de consolas en Lima", 20),
       "Claude propone la principal, las secundarias y la zona, con su porqué")
    ok(pg.visible(f"{tarjeta} .propuesta-palabras .meta", "YouTube sugiere"), "y lo que sugiere YouTube")
    pg.captura("publicar_seo_proyecto")

    # la ficha
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".seo-video h3", "SEO", 15), "la ficha tiene su bloque SEO")
    ok(pg.esperar(".texto-red[data-red=instagram] .nota-seo .pastilla", "SEO", 5), "cada red con su nota SEO")
    pg.p.locator(".texto-red[data-red=instagram] .nota-seo > summary").first.click()
    ok(pg.visible(".texto-red[data-red=instagram] .punto-seo", "primera línea"), "y el porqué de la nota")
    ok(pg.visible(".texto-red[data-red=instagram] .meta", "texto alternativo"),
       "Instagram dice que no admite texto alternativo")
    pg.pulsar(".seo-video button", "Optimizar SEO con Claude")
    ok(pg.esperar(".propuesta-seo .cambio-seo", segundos=20), "«Optimizar SEO»: la propuesta campo a campo")
    ok(pg.visible(".propuesta-seo .antes-despues .despues", "[SEO]"), "con el antes y el después")
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    ok(ficha["textos"]["instagram"]["descripcion"] == "Reel para el SEO", "sin tocar todavía el texto")
    pg.pulsar('.cambio-seo[data-red="instagram"][data-campo="descripcion"] button', "Aceptar")
    pg.p.wait_for_timeout(1200)
    valor = pg.p.evaluate("() => (document.querySelector('.texto-red[data-red=instagram] textarea') || {}).value || ''")
    ok(valor.startswith("[SEO]"), f"«Aceptar» lo pone en el texto: {valor[:30]!r}")
    pg.pulsar(".texto-red[data-red=instagram] .seo-red button", "Dame 3 ganchos")
    ok(pg.esperar(".texto-red[data-red=instagram] .gancho-seo", segundos=20), "«Dame 3 ganchos»")
    pg.pulsar(".texto-red[data-red=instagram] .gancho-seo button", "Usar este")
    pg.p.wait_for_timeout(1200)
    valor = pg.p.evaluate("() => (document.querySelector('.texto-red[data-red=instagram] textarea') || {}).value || ''")
    ok(valor.startswith("¿instagram 1?"), f"«Usar este» lo pone de primera línea: {valor[:30]!r}")
    pg.captura("publicar_seo_ficha")
    pg.sin_errores("el SEO de Publicar")
    pg.cerrar()

    # en el móvil y en los dos temas
    for tema in ("oscuro", "claro"):
        pg = Pagina(navegador, datos, ancho=390, alto=844, nombre=f"seo móvil {tema}")
        pg.js(f"document.documentElement.dataset.tema = '{tema}'; abrirPublicarVideo('{pid}');")
        pg.p.wait_for_timeout(2500)
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(ancho <= 2, f"la ficha con el SEO cabe en un móvil, tema {tema} ({ancho}px)")
        pg.js("PUB.seccion = 'cuentas'; PUB.seoAbierto = {}; irAModulo('publicar');")
        pg.p.wait_for_timeout(1500)
        pg.js("document.querySelectorAll('.seo-proyecto').forEach(d => { d.open = true; });")
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(ancho <= 2, f"y el SEO del proyecto, tema {tema} ({ancho}px)")
        texto = pg.p.evaluate("() => document.querySelector('#modulo').innerText")
        malos = sorted(set(x.group(0) for x in TEXTOS_MALOS.finditer(texto)))
        ok(not malos, f"sin «undefined», «NaN» ni «null» ({malos})")
        pg.captura(f"publicar_seo_movil_{tema}", entera=False)
        pg.sin_errores(f"el SEO en el móvil ({tema})")
        pg.cerrar()


@escenario
def publicar_mas(navegador, datos):
    """publicar-mas (18-10-2026): las cifras automáticas (apagadas de fábrica,
    el coste antes de guardar y la confirmación, que se puede cancelar), «Redes
    de este proyecto» con sus ajustes, las redes nuevas en la ficha (título,
    texto alternativo, el motivo si falta el tablero), la hora sugerida con
    «Usar», palabras y ganchos, horarios y el informe del mes. Y en el móvil."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar",
             {"redes": ["tiktok", "instagram", "youtube", "linkedin", "pinterest"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    api.put("/api/publicar/metricas-auto", {"frecuencia": "apagada"})
    api.put(f"/api/publicar/proyectos/{cid}", {"redes_visibles": ["tiktok", "instagram", "youtube", "facebook"],
                                                "pinterest_tablero": ""})
    pg = Pagina(navegador, datos)
    pg.js("PUB.seccion = 'cuentas'; irAModulo('publicar');")
    ok(pg.esperar(".metricas-auto .pastilla", "apagadas", 10), "las cifras automáticas, apagadas de fábrica")
    pg.pulsar(".metricas-auto button", "Encender: una vez al día, últimos 30")
    ok(pg.esperar(".metricas-auto .coste-auto", "Si guardas", 10), "al elegir, el coste ANTES de guardar")
    coste = pg.p.locator(".metricas-auto .coste-auto").inner_text()
    ok("0 $" in coste and "cupo" in coste, f"dice que no cuesta dinero y lo que gasta del cupo: {coste[:90]!r}")
    pg.aceptar = False
    pg.pulsar(".metricas-auto button", "Guardar")
    pg.p.wait_for_timeout(800)
    ok(pg.dialogos and "0 $" in pg.dialogos[-1], "«Guardar» pide confirmar enseñando el coste")
    _r, auto = api.get("/api/publicar/metricas-auto")
    ok(auto.get("frecuencia") == "apagada", "cancelado: no se guarda nada")
    pg.aceptar = True
    pg.pulsar(".metricas-auto button", "Guardar")
    pg.p.wait_for_timeout(1200)
    _r, auto = api.get("/api/publicar/metricas-auto")
    ok((auto.get("frecuencia"), auto.get("posts")) == ("diaria", 30), "aceptado: una vez al día, los últimos 30")
    ok(pg.esperar(".metricas-auto .pastilla", "una vez al día", 10), "y la tarjeta lo dice, con la próxima vuelta")
    ok(pg.visible(".metricas-auto .meta", "próxima"), "con la próxima vuelta")
    pg.p.locator(".eleccion-auto select").first.select_option("apagada")
    ok(pg.esperar(".metricas-auto .coste-auto", "no se gasta nada", 10), "apagarlas: lo dice antes de guardar")
    pg.pulsar(".metricas-auto button", "Guardar")
    pg.p.wait_for_timeout(1200)
    _r, auto = api.get("/api/publicar/metricas-auto")
    ok(auto.get("frecuencia") == "apagada", "y se pueden apagar")
    pg.captura("publicar_mas_cifras_auto")

    # «Redes de este proyecto»
    tarjeta = f'.proyecto-publicar:has(input[data-perfil="{cid}"])'
    pg.p.locator(f"{tarjeta} .redes-proyecto > summary").first.click()
    pg.p.locator(f'{tarjeta} .redes-de-proyecto input[data-red="linkedin"]').check()
    pg.p.wait_for_timeout(1200)
    pg.p.locator(f'{tarjeta} .redes-de-proyecto input[data-red="pinterest"]').check()
    pg.p.wait_for_timeout(1200)
    _r, proyectos = api.get("/api/publicar/proyectos")
    fila = next((x for x in proyectos["proyectos"] if x["id"] == cid), {})
    vis = (fila.get("ajustes") or {}).get("redes_visibles") or []
    ok("linkedin" in vis and "pinterest" in vis, f"marcar LinkedIn y Pinterest las pone a la vista ({vis})")
    ok(pg.esperar(f"{tarjeta} .redes-proyecto .aviso-red", "tablero", 10), "Pinterest avisa de que falta el tablero")
    ok(pg.visible(f"{tarjeta} .redes-proyecto .ajustes-red b", "LinkedIn"), "y LinkedIn enseña su página y quién lo ve")
    pg.pulsar(f"{tarjeta} .redes-proyecto button", "Elegir tablero")
    ok(pg.esperar(f"{tarjeta} select[data-tablero]", segundos=10) and
       "Fiestas" in pg.p.locator(f"{tarjeta} select[data-tablero]").inner_text(),
       f"«Elegir tablero»: los tableros de la cuenta de Pinterest ({pg.toast()[:60]!r})")
    pg.p.locator(f"{tarjeta} select[data-tablero]").select_option("1001")
    pg.p.wait_for_timeout(1200)
    _r, proyectos = api.get("/api/publicar/proyectos")
    fila = next((x for x in proyectos["proyectos"] if x["id"] == cid), {})
    ok((fila.get("ajustes") or {}).get("pinterest_tablero") == "1001", "elegir uno lo guarda")
    api.put(f"/api/publicar/proyectos/{cid}", {"pinterest_tablero": ""})
    pg.js("PUB.tableros = {}; cargarPublicar();")
    pg.p.wait_for_timeout(1200)
    pg.captura("publicar_mas_redes_proyecto")

    # la ficha
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".redes-ficha .casilla-red", "LinkedIn", 15), "la ficha enseña LinkedIn")
    ok(not pg.visible(".redes-ficha .casilla-red", "Mastodon"), "y no las que no se pidieron")
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram", "linkedin", "pinterest"], "textos": {
        "instagram": {"descripcion": "Reel"}, "linkedin": {"descripcion": "Post de LinkedIn"},
        "pinterest": {"descripcion": "Pin"}}})
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".texto-red[data-red=linkedin] .etiqueta-campo", "Título (", 15), "LinkedIn con su título (400)")
    ok(pg.visible(".texto-red[data-red=pinterest] .etiqueta-campo", "Texto alternativo"),
       "Pinterest con su texto alternativo")
    ok(not pg.visible(".texto-red[data-red=instagram] .etiqueta-campo", "Texto alternativo"),
       "Instagram sin él (no lo admite)")
    ok(pg.esperar(".motivo-no-publicar", "tablero", 10), "«Publicar» dice que falta el tablero de Pinterest")
    pg.p.locator(".texto-red[data-red=pinterest] input[data-foco=pinterest-alt]").fill("Una consola en una fiesta")
    pg.p.wait_for_timeout(1800)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    ok((ficha["textos"].get("pinterest") or {}).get("alt") == "Una consola en una fiesta",
       "el texto alternativo se guarda")
    pg.js("PUB.modoEnvio = 'programar'; pintarModulo();")
    ok(pg.esperar(".sugerencias-cuando .sugerencia-hora", "LinkedIn", 15), "Cuándo propone hora para cada red")
    ok(pg.visible(".sugerencias-cuando .meta", "punto de partida general"),
       "sin datos propios lo dice: es un punto de partida general")
    pg.pulsar(".sugerencias-cuando .sugerencia-hora:has-text('LinkedIn') button", "Usar")
    pg.p.wait_for_timeout(600)
    valor = pg.p.locator(".cuando-publicar input[type=datetime-local]").input_value()
    ok(bool(valor) and valor == pg.p.evaluate("() => PUB.cuandoEnvio"), f"«Usar» pone esa hora ({valor})")
    pg.captura("publicar_mas_ficha")
    pg.sin_errores("las redes nuevas en la ficha")

    # Resultados
    pg.js("PUB.verInforme = false; irASeccionPublicar('resultados');")
    ok(pg.esperar(".palabras-ganchos h3", "Palabras clave", 15), "Resultados: palabras clave y ganchos")
    ok(pg.esperar(".horarios-publicar .fila-horario", "LinkedIn", 10), "y cuándo publicar en cada red")
    ok(pg.visible(".linea-auto", "apagadas"), "y si las cifras automáticas están encendidas")
    pg.pulsar(".resultados-publicar button", "Informe del mes")
    ok(pg.esperar(".informe-publicar .titulo-informe", segundos=15), "«Informe del mes»")
    ok(pg.visible(".informe-publicar button", "Copiar resumen") and
       pg.visible(".informe-publicar button", "Imprimir o guardar en PDF"), "con «Copiar resumen» e «Imprimir»")
    pg.captura("publicar_mas_informe")
    pg.pulsar(".informe-publicar button", "← Resultados")
    ok(pg.esperar(".palabras-ganchos", segundos=10), "y se vuelve a Resultados")
    pg.sin_errores("Resultados e informe")
    pg.cerrar()

    for tema in ("oscuro", "claro"):
        pg = Pagina(navegador, datos, ancho=390, alto=844, nombre=f"publicar-mas móvil {tema}")
        pg.js(f"document.documentElement.dataset.tema = '{tema}'; PUB.redesAbiertas = {{}}; "
              "PUB.seccion = 'cuentas'; irAModulo('publicar');")
        pg.p.wait_for_timeout(2000)
        pg.js("document.querySelectorAll('.redes-proyecto').forEach(d => { d.open = true; });")
        pg.p.wait_for_timeout(300)
        for nombre, preparar in (("cuentas", ""),
                                 ("ficha", f"PUB.modoEnvio = 'programar'; abrirPublicarVideo('{pid}');"),
                                 ("resultados", "PUB.verInforme = false; irASeccionPublicar('resultados');"),
                                 ("informe", "PUB.verInforme = true; PUB.informe = null; cargarPublicar();")):
            if preparar:
                pg.js(preparar)
                pg.p.wait_for_timeout(2500)
            ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(ancho <= 2, f"{nombre} cabe en un móvil, tema {tema} ({ancho}px)")
            texto = pg.p.evaluate("() => document.querySelector('#modulo').innerText")
            malos = sorted(set(x.group(0) for x in TEXTOS_MALOS.finditer(texto)))
            ok(not malos, f"{nombre}: sin «undefined», «NaN» ni «null» ({malos})")
        pg.captura(f"publicar_mas_movil_{tema}", entera=False)
        pg.sin_errores(f"publicar-mas en el móvil ({tema})")
        pg.cerrar()
    # como estaba, para los escenarios de después
    api.put(f"/api/publicar/proyectos/{cid}", {"redes_visibles": ["tiktok", "instagram", "youtube", "facebook"]})
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram", "youtube"]})


@escenario
def publicar_lo_que_se_mando(navegador, datos):
    """19-10-2026, en producción: los posts salían solo con la primera línea
    (el «title» general llevaba solo esa línea). Ahora el «title» es el texto
    completo y la ficha enseña «Ver lo que se mandó» por red."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok", "instagram", "youtube"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    largo = "Primera línea del Reel\n\nSegunda parte del texto, la que se perdía.\n\nTercera parte."
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram"], "textos": {
        "instagram": {"descripcion": largo, "hashtags": ["fiestaslima"]}}})
    api.post(f"/api/publicar/videos/{pid}/enviar", {"redes": ["instagram"], "modo": "ahora",
                                                     "confirmado": True, "repetir": True})
    pg = Pagina(navegador, datos)
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".lo-mandado > summary", "Ver lo que se mandó a Reels", 20),
       "cada envío tiene «Ver lo que se mandó»")
    # EL envío de este escenario (en la batería entera el vídeo ya trae otros
    # de Instagram, y el primero de la lista puede ser uno programado de antes)
    propio = '.lo-mandado:has(pre:has-text("Tercera parte."))'
    ok(pg.esperar(propio, segundos=20) or pg.p.locator(propio).count() > 0,
       "el envío de ahora tiene lo que se mandó")
    pg.p.locator(f"{propio} > summary").first.click()
    pg.p.wait_for_timeout(500)
    texto = pg.p.locator(propio).first.inner_text()
    ok("instagram_title" in texto and "Tercera parte." in texto and "#fiestaslima" in texto,
       "con el texto entero que se mandó a Instagram (y sus hashtags)")
    ok("title (" in texto and texto.count("Tercera parte.") >= 2,
       "y el «title» común también lleva el texto entero, no solo la primera línea")
    pg.p.wait_for_timeout(5000)
    ok(pg.visible(f"{propio} pre", "Tercera parte."), "y se queda abierto aunque la ficha se repinte")
    pg.captura("publicar_lo_que_se_mando")
    pg.sin_errores("«Ver lo que se mandó»")
    pg.cerrar()


@escenario
def parrilla_marca_chat_y_resultados(navegador, datos):
    """parrilla-2 (18-10-2026): la marca del cliente, «Conversar con Claude» (el
    doble del recorrido) con captura e internet, guardar su guion en la
    Parrilla, y «Desde mis resultados» (sin cifras lo dice). Y en el móvil."""
    cid = datos["cliente"]
    pg = Pagina(navegador, datos)
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    pg.js(f"elegirProyectoParrilla('{cid}');")
    pg.pulsar(".pestanas-publicar button", "Marca del cliente")
    ok(pg.esperar(".marca-parrilla [data-foco=marca-quien]", segundos=10), "la pestaña de la marca del cliente")
    pg.p.locator("[data-foco=marca-quien]").fill("EstadoPlay, consolas para fiestas en Lima")
    pg.p.locator("[data-foco=marca-cta]").fill("Escríbenos por WhatsApp")
    pg.pulsar(".marca-parrilla button", "Guardar la marca")
    ok(pg.esperar(".marca-parrilla .pista", "guardada el", 10), "se guarda")
    _r, marca = datos["api"].get(f"/api/parrilla/proyectos/{cid}/marca")
    ok(((marca or {}).get("marca") or {}).get("cta") == "Escríbenos por WhatsApp", "y queda en el servidor")

    pg.pulsar(".pestanas-publicar button", "Añadir guiones")
    pg.pulsar(".origen-parrilla button", "Conversar con Claude")
    ok(pg.esperar(".chat-parrilla .chat-vacio", segundos=10), "el chat, vacío, explica qué se puede hacer")
    png = os.path.join(datos["base"], "captura_chat.png")
    _png(png, (200, 80, 120))
    pg.p.locator("[data-foco=parrilla-chat]").fill("Hazme un guion para un cumpleaños infantil")
    pg.p.set_input_files(".oculto-chat", png)
    pg.p.wait_for_timeout(300)
    ok(pg.visible(".capturas-chat .pastilla", "captura_chat"), "la captura adjunta se ve")
    pg.p.locator(".interruptor-chat input").first.check()
    pg.pulsar(".mandos-chat button.primario", "Enviar")
    ok(pg.esperar(".chat-turno.de-claude .guion-en-chat", segundos=20), "Claude (el doble) contesta con un guion")
    ok(pg.visible(".chat-turno.tuyo .quien-chat", "con internet"), "el mensaje dice que fue con internet")
    ok(pg.visible(".chat-turno.de-claude .texto-chat", "Capturas: sí"), "y con la captura")
    pg.pulsar(".guardar-chat button", "en la Parrilla")
    ok(pg.esperar(".guardar-chat .pastilla", "en la Parrilla", 10), "«Guardar en la Parrilla» lo guarda")
    pg.captura("parrilla_chat")

    pg.pulsar(".origen-parrilla button", "Desde mis resultados")
    ok(pg.esperar(".anadir-parrilla .caja-aviso", "Actualizar", 10) or pg.esperar(".post-parrilla", segundos=5),
       "«Desde mis resultados» enseña los vídeos o dice cómo tenerlos")
    pg.pulsar(".pestanas-publicar button", "Parrilla")
    ok(pg.esperar(".cab-matriz h3", "Conversación", 10), "el guion del chat está en la Parrilla")
    pg.sin_errores("la marca, el chat y los resultados")
    pg.cerrar()

    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="movil")
    pg.js("document.documentElement.dataset.tema = 'claro';")
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    pg.js(f"elegirProyectoParrilla('{cid}'); PAR.form.origen = 'chat'; irASeccionParrilla('anadir');")
    ok(pg.esperar(".chat-parrilla", segundos=10), "el chat en el móvil")
    pg.p.wait_for_timeout(800)
    for que in ("anadir", "marca"):
        pg.js(f"irASeccionParrilla('{que}');")
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth")
        ok(ancho <= 391, f"«{que}» cabe a lo ancho en el móvil ({ancho} px)")
    pg.captura("parrilla_chat_movil")
    pg.sin_errores("el chat en el móvil")
    pg.cerrar()


@escenario
def parrilla_analizar_una_cuenta(navegador, datos):
    """analizar-cuentas (18-10-2026), con las fuentes simuladas: poner las
    conexiones, traer una cuenta de Instagram personal (pasa a Apify, que
    pregunta antes de pagar), analizarla, escribir guiones con ella y llevarla
    al chat. Y en el móvil."""
    cid = datos["cliente"]
    pg = Pagina(navegador, datos)
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    pg.js(f"elegirProyectoParrilla('{cid}');")
    pg.pulsar(".pestanas-publicar button", "Analizar una cuenta")
    ok(pg.esperar(".conexiones-cuentas", segundos=10), "la pestaña con sus Conexiones")
    ok(pg.visible(".conexiones-cuentas .caja-aviso", "SIMULADO"), "avisa de que es simulado")
    pg.p.locator("[data-foco=conexion-apify_token]").fill("apify_api_recorrido_1234")
    pg.p.locator(".conexion-cuenta").nth(2).locator("button", has_text="Guardar").click()
    ok(pg.esperar(".conexion-cuenta .pastilla", "1234", 10), "el token de Apify, puesto (solo sus 4 últimos)")
    pg.p.locator("[data-foco=conexion-meta_token]").fill("EAABrecorrido5678")
    pg.p.locator(".conexion-cuenta").nth(1).locator("button", has_text="Guardar").click()
    ok(pg.esperar(".conexion-cuenta .meta", "micuenta_studio", 10), "el token de Meta encuentra tu Instagram")

    pg.p.locator("[data-foco=cuenta-texto]").fill("https://www.instagram.com/personal_lucia/")
    pg.dialogos.clear()
    pg.pulsar(".traer-cuenta button.primario", "Traer sus vídeos")
    ok(pg.esperar(".cab-cuenta h3", "@personal_lucia", 20), "trae la cuenta")
    ok(pg.visible(".cuenta-abierta > .meta", "Apify"), "por Apify (no es profesional)")
    ok(any("Pagar" in d and "$" in d for d in pg.dialogos),
       f"y antes de pagar PREGUNTÓ, con el precio (revisión del 18-10): {pg.dialogos[-1:]}")
    ok(pg.esperar(".video-cuenta", segundos=5), "con sus vídeos")
    pg.pulsar(".analisis-cuenta button", "Que Claude la analice")
    ok(pg.esperar(".texto-analisis", "QUÉ LE FUNCIONA", 20), "el análisis")
    pg.captura("cuenta_analizada")
    pg.pulsar(".guiones-cuenta button.primario", "Escribir guiones")
    ok(pg.esperar(".cab-matriz .meta", "con lo que le funciona a @personal_lucia", 25),
       "los guiones van a la Parrilla, diciendo de qué cuenta salen")
    pg.pulsar(".pestanas-publicar button", "Analizar una cuenta")
    pg.pulsar(".cuentas-guardadas button", "personal_lucia")
    pg.pulsar(".guiones-cuenta button", "Hablar de ella en el chat")
    ok(pg.esperar(".chat-parrilla", segundos=10), "«Hablar de ella en el chat» abre el chat")
    ok(pg.p.evaluate("() => (document.querySelector('.cuenta-chat') || {}).value") == "instagram:personal_lucia",
       "con la cuenta elegida")
    pg.sin_errores("analizar una cuenta")
    pg.cerrar()

    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="movil")
    pg.js("document.documentElement.dataset.tema = 'claro';")
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    pg.js("irASeccionParrilla('cuentas');")
    ok(pg.esperar(".cuentas-guardadas button", segundos=10), "en el móvil")
    pg.pulsar(".cuentas-guardadas button", "personal_lucia")
    pg.p.wait_for_timeout(800)
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth")
    ok(ancho <= 391, f"la cuenta cabe a lo ancho en el móvil ({ancho} px)")
    pg.sin_errores("analizar una cuenta en el móvil")
    pg.cerrar()


# ======================================================================
# EL MOVIMIENTO DE CADA IMAGEN (rama `montaje-por-plano`, 19-10-2026). Tramo
# propio y al final, para no chocar con las otras ramas.

@escenario
def movimiento_de_cada_imagen(navegador, datos):
    """En la diapositiva de Imágenes, «🎬 Esta imagen» elige el movimiento y la
    2.5D de ESE plano: «Quieta» lo guarda en su unidad, deja pendiente solo
    ese plano y, al montar, su trayecto es un encuadre fijo. «Como el vídeo»
    lo quita y la firma vuelve a la de antes."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    # «todos_los_botones» ya ha pulsado estos botones: se parte de cada imagen
    # «como el vídeo», y con el vídeo montado así
    _r, leido = api.get(f"/api/proyectos/{pid}/planos/montaje")
    if leido.get("planos"):
        for sid_ in leido["planos"]:
            api.put(f"/api/proyectos/{pid}/planos/{sid_}/montaje",
                    {"movimiento": None, "profundidad": None})
        api.post(f"/api/proyectos/{pid}/montaje/aplicar", {})
        api.libre(pid, 600)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".montaje-plano", "Esta imagen", 15), "la diapositiva trae «🎬 Esta imagen»")
    _r, leido = api.get(f"/api/proyectos/{pid}/planos/montaje")
    for _vuelta in range(len(leido.get("planos_del_video") or [])):
        if pg.p.evaluate("() => escenaPrevia().id") not in (leido.get("no_aplica") or []):
            break
        pg.js("irAEscenaPrevia(1);")
        pg.p.wait_for_timeout(400)
    sid = pg.p.evaluate("() => escenaPrevia().id")
    ok(sid not in (leido.get("no_aplica") or []), f"se mira un plano con imagen ({sid})")
    ok(pg.visible(".montaje-plano button.activo", "Como el vídeo"),
       "de partida, «Como el vídeo» (no se escribe nada al abrir)")
    _r, callouts = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    firma_antes = callouts.get("firma")
    sucias_antes = set(callouts.get("unidades_obsoletas") or [])
    ok(f"escena:{sid}" not in ((callouts.get("params") or {}).get("unidades") or {})
       or "montaje" not in (((callouts.get("params") or {}).get("unidades") or {}).get(f"escena:{sid}") or {}),
       "abrir la diapositiva no escribe el montaje del plano (regla 1)")
    pg.p.locator(".montaje-plano button", has_text="Quieta").first.click()
    ok(pg.esperar(".montaje-plano button.activo", "Quieta", 10), "«Quieta» queda marcada")
    _r, leido = api.get(f"/api/proyectos/{pid}/planos/montaje")
    ok((leido.get("planos") or {}).get(sid) == {"movimiento": "quieto"},
       f"y se guarda solo en ese plano ({leido.get('planos')})")
    _r, callouts = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    ok(set(callouts.get("unidades_obsoletas") or []) - sucias_antes == {f"escena:{sid}"},
       "deja pendiente ese plano y ninguno más")
    ok(pg.esperar(".barra-accion button", "Montar el vídeo", 10),
       "y abajo sale «Montar el vídeo»")
    pg.js("document.querySelector('.montaje-plano').scrollIntoView({block: 'center'});")
    pg.captura("movimiento_de_una_imagen", entera=False)
    assets_antes = _version_de(datos, "assets", "").get("activa")
    api.post(f"/api/proyectos/{pid}/montaje/aplicar", {})
    ok(api.libre(pid, 600), "el montaje termina")
    activa = _version_de(datos, "callouts", "").get("activa")
    ruta_mov = os.path.join(datos["proyectos"], pid, "pasos", "callouts",
                            f"v{activa}", "movimiento", f"{sid}.json")
    try:
        with open(ruta_mov, encoding="utf-8") as fh:
            mov = json.load(fh)
    except (OSError, ValueError):
        mov = {}
    tramos = (mov.get("trayecto") or {}).get("tramos") or []
    ok(len(tramos) == 1 and tramos[0].get("ini") == tramos[0].get("fin"),
       f"montado, el plano {sid} va quieto: un solo encuadre fijo")
    ok(_version_de(datos, "assets", "").get("activa") == assets_antes, "y ni una imagen rehecha")
    pg.js("pintarLight();")
    pg.p.wait_for_timeout(800)
    pg.p.locator(".montaje-plano-fila", has_text="Movimiento").locator(
        "button", has_text="Como el vídeo").first.click()
    ok(pg.esperar(".montaje-plano button.activo", "Como el vídeo", 10),
       "«Como el vídeo» lo devuelve")
    _r, callouts = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    ok("montaje" not in (((callouts.get("params") or {}).get("unidades") or {}).get(f"escena:{sid}") or {}),
       "y quita la clave del plano")
    api.post(f"/api/proyectos/{pid}/montaje/aplicar", {})
    api.libre(pid, 600)
    _r, callouts = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    ok(callouts.get("firma") == firma_antes, "y la firma de las capas vuelve a la de antes")
    pg.sin_errores("movimiento de cada imagen")
    pg.cerrar()


# ======================================================================
# ARREGLOS V2H (18-10-2026): lo que seguía de los informes del 10 y 13-10.
# Tramo propio y al final, como los demás.

@escenario
def lo_de_v2h_en_la_pantalla(navegador, datos):
    """U1, U2, U4, U5, M2, B1, B3, B4, B5, B7, B9 y B10: cada uno como se vio."""
    # B3 + U5 · «Un estilo nuevo» no pregunta al servidor con el nombre vacío
    pg = Pagina(navegador, datos)
    planes = []
    pg.p.on("request", lambda r: planes.append(r.url) if "presets-light/plan" in r.url else None)
    pg.js("APP.light.encargo = null; irALight('crear', { taller: null });")
    ok(pg.esperar("input, textarea"), "«Un estilo nuevo» se abre")
    pg.p.wait_for_timeout(1500)
    ok(not planes, f"B3: abrirlo no manda ninguna petición del plan con el nombre vacío ({len(planes)})")
    ok(pg.visible(".pie-light .aviso", "nombre al estilo"), "U5: y dice «ponle un nombre al estilo»")
    ok(not pg.visible(".pie-light", "canal") and not pg.visible(".pie-light", "preset"),
       "U5: sin «canal» ni «preset»")
    # M2 · cambiar el tipo de imagen con referencias puestas lo avisa
    pg.js("encargoLight().estilo_imagenes = [{nombre: 'x.png'}]; pintarLight();")
    pg.p.locator(".campo").filter(has_text="Tipo de imagen").locator("select").first.select_option("foto")
    pg.p.wait_for_timeout(400)
    ok(any("Foto realista" in a and "fotos" in a for a in pg.avisos()),
       f"M2: con imágenes puestas, pasar a Foto realista avisa de que deberían ser fotos: {pg.avisos()[-1:]}")
    pg.js("encargoLight().estilo_imagenes = []; APP.light.encargo = null;")
    pg.sin_errores("«Un estilo nuevo»")
    pg.cerrar()

    # B4 + B5 + B7 · «Un vídeo nuevo»
    pg = Pagina(navegador, datos)
    pg.js(f"await cargarGaleriaLight(true); elegirEstiloLight(fichaLight('{datos['preset']}'));")
    ok(pg.esperar("h2", "Un vídeo nuevo"), "«Un vídeo nuevo» se abre")
    ok(pg.visible(".paso-carril.actual", "Encargo"), "B4: con «Encargo» marcado en el carril")
    ok(pg.visible(".meta", "de 10 s a 30 min"), "B5: el rótulo de la duración dice el mínimo de verdad (10 s)")
    ok(pg.visible("body", "el redactor lee") and not pg.visible("body", "documentalista"),
       "B7: habla del redactor, no del documentalista")
    pg.sin_errores("«Un vídeo nuevo»")
    pg.cerrar()

    # U2 · sin login, «Salir» no está ni se alcanza con el tabulador
    pg = Pagina(navegador, datos)
    ok(pg.p.evaluate("() => getComputedStyle(document.querySelector('#cuenta')).display") == "none",
       "U2: sin login la pastilla de la cuenta no se pinta")
    vistos = []
    for _ in range(40):
        pg.p.keyboard.press("Tab")
        vistos.append(pg.p.evaluate("() => document.activeElement && document.activeElement.id"))
    ok("btn-salir" not in vistos, "U2: y el tabulador no pasa por «Salir»")

    # U4 · el recuento del guion cuenta lo editado a mano
    pg.js(f"await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'guion'; pintarLight();")
    pg.p.wait_for_timeout(800)
    cuenta = pg.p.evaluate("""() => { const v = APP.light.video; const b = (v.guion.bloques || [])[0];
      if (!b) return null;
      const leer = () => { pintarLight(); const m = document.querySelector('.light-guion .light-cab .meta');
        return Number(((m && m.textContent.match(/([\\d.]+) palabras/)) || [0, 'NaN'])[1].replace(/\\./g, '')); };
      const antes = leer();
      const ficha = (v.fichas.guion = v.fichas.guion || {}); ficha.params = ficha.params || {};
      const previo = (ficha.params.bloques || {})[b.id];
      ficha.params.bloques = Object.assign({}, ficha.params.bloques, {[b.id]: {texto: b.texto + ' una dos tres'}});
      const despues = leer();
      if (previo === undefined) delete ficha.params.bloques[b.id]; else ficha.params.bloques[b.id] = previo;
      leer(); return despues - antes; }""")
    ok(cuenta == 3, f"U4: el recuento de palabras sube con lo editado a mano ({cuenta})")

    # U3 · la ayuda de «Generar imágenes» nombra la parada que existe
    ayuda = pg.p.evaluate("() => ayudaDiapositivas(false, false, false)")
    ok("«Imágenes»" in ayuda and "Diapositivas" not in ayuda,
       f"U3: la ayuda manda a «Imágenes», no a «Diapositivas» ({ayuda[:70]!r})")

    # B8 · «La pausa ... se hace» con una sola
    frase = pg.p.evaluate("""() => { const v = APP.light.video, antes = v.estructura;
      v.estructura = {pausas: {total: 0, tope: 3, al_final: ['B001']}};
      const n = barraPausasLight(); v.estructura = antes; return n ? n.textContent : ''; }""")
    ok("se hace al montar" in frase and "se hacen" not in frase,
       f"B8: con una pausa, «se hace» ({frase[:80]!r})")

    # B1 · el tiempo restante no dice minutos con la barra al 99 %
    texto = pg.p.evaluate("""() => { const v = APP.light.video, antes = [v.planDe, v.plan];
      v.planDe = 'b1'; v.plan = {segundos: 720};
      const t = restanteTandaLight({id: 'b1', inicio: Date.now() - 60000}, 0.99);
      v.planDe = antes[0]; v.plan = antes[1]; return t; }""")
    ok(texto == "", f"B1: al 99 % tras un minuto no promete minutos ({texto!r})")

    # B9 · el mismo trabajo no sale dos veces en la cabecera
    veces = pg.p.evaluate("""() => { const antes = APP.trabajos;
      APP.trabajos = {receta: {id: 'mismo', estado: 'ejecutando', progreso: 0.08},
                      [CLAVE_VIDEO_LIGHT]: {id: 'mismo', estado: 'ejecutando', progreso: 0.08,
                                            pid: APP.light.video.pid}};
      pintarFaro(); const n = (document.querySelector('#faro').textContent.match(/%/g) || []).length;
      APP.trabajos = antes; pintarFaro(); return n; }""")
    ok(veces == 1, f"B9: un trabajo reenganchado en dos ranuras sale UNA vez ({veces})")
    pg.sin_errores("la cuenta, el guion y la cabecera")
    pg.cerrar()

    # U1 + B10 · en el móvil
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="movil v2h")
    pg.js(f"await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".previa-mandos"), "la pantalla de Imágenes en el móvil")
    burbuja = pg.p.locator(".burbuja-asistente").bounding_box()
    siguiente = pg.p.locator(".previa-mandos button", has_text="Siguiente").first.bounding_box()
    ok(burbuja and siguiente and burbuja["y"] + burbuja["height"] <= siguiente["y"],
       f"B10: la burbuja no pisa «Siguiente ›» ({burbuja and burbuja['y'] + burbuja['height']} "
       f"frente a {siguiente and siguiente['y']})")
    pg.pulsar(".burbuja-asistente")
    ok(pg.esperar("#asistente:not(.plegado)", segundos=5), "el asistente se abre a pantalla completa")
    ok(not pg.visible(".minimizar-burbuja"), "U1: y el «–» de la burbuja no queda encima del chat")
    pg.sin_errores("el móvil")
    pg.cerrar()


@escenario
def portadas_disenadas(navegador, datos):
    """Rama `portadas` (19-10-2026): diseñar la portada de un vídeo en Publicar.
    Abrir el editor no guarda nada; cada plantilla pinta su vista; Claude
    propone tres; el fondo se hace con la IA (simulada) solo tras confirmar el
    precio; «Usar como portada» la deja como la imagen que va a las redes."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    r, cat = api.get("/api/portadas/catalogo")
    ok(r.status_code == 200 and len(cat.get("plantillas") or []) >= 20,
       f"el catálogo trae las plantillas ({len(cat.get('plantillas') or [])})")
    r, ficha = api.get(f"/api/publicar/videos/{pid}/portada/diseno")
    ok(r.status_code == 200 and ficha.get("guardado") is False and ficha.get("diseno"),
       "abrir el diseño da uno de partida SIN guardarlo")
    ruta = os.path.join(datos["proyectos"], "_sistema", "publicar", "portadas", f"{pid}.diseno.json")
    ok(not os.path.exists(ruta), "y no escribe nada en el disco")
    pg = Pagina(navegador, datos, nombre="portadas")
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".portada-publicar button", "Diseñar portada", 20), "el bloque Portada trae «Diseñar portada»")
    pg.pulsar(".portada-publicar button", "Diseñar portada")
    ok(pg.esperar(".capa-portada", "Diseñar portada", 15), "se abre el editor de portadas")
    ok(pg.esperar(".vista-portada-grande img", segundos=30), "con la vista pintada")
    texto = pg.p.locator(".capa-portada").inner_text()
    malos = sorted(set(x.group(0) for x in TEXTOS_MALOS.finditer(texto)))
    ok(not malos, f"sin «null», «undefined» ni tildes rotas en el editor ({malos})")
    primera = pg.p.evaluate("() => PORT.vista")
    pg.pulsar(".capa-portada .plantilla-portada", "Versus")
    pg.p.wait_for_timeout(600)
    pg.p.locator(".capa-portada input[data-foco=portada-izquierda]").fill("Diseño")
    pg.p.locator(".capa-portada input[data-foco=portada-derecha]").fill("Función")
    fin = time.time() + 30
    while time.time() < fin and pg.p.evaluate("() => PORT.vista") == primera:
        pg.p.wait_for_timeout(500)
    ok(pg.p.evaluate("() => PORT.vista") != primera, "al cambiar de plantilla y textos se vuelve a pintar")
    ok(pg.p.evaluate("() => PORT.diseno.fondo.disposicion") == "diagonal",
       "el versus parte el fondo en diagonal")
    pg.captura("portada_versus", entera=False)
    # Claude propone (el CLI falso contesta tres)
    pg.pulsar(".capa-portada button", "Proponer 3 portadas")
    ok(pg.esperar(".propuesta-portada", "PS5", 60), "Claude propone portadas")
    ok(pg.p.locator(".propuesta-portada").count() == 3, "tres")
    pg.p.locator(".propuesta-portada button", has_text="Usar esta").nth(1).click()
    pg.p.wait_for_timeout(800)
    ok(pg.p.evaluate("() => PORT.diseno.plantilla") == "oferta", "y se puede usar una")
    # el fondo con IA, con el precio delante (motor de imágenes simulado)
    antes = len(pg.dialogos)
    pg.pulsar(".capa-portada button", "Hacer el fondo con IA")
    fin = time.time() + 90
    while time.time() < fin and pg.p.evaluate("() => (PORT.diseno.fondo || {}).tipo") != "ia":
        pg.p.wait_for_timeout(700)
    ok(len(pg.dialogos) > antes and "$" in pg.dialogos[-1], "antes de pagar enseña el precio y pregunta")
    ok(pg.p.evaluate("() => PORT.diseno.fondo.tipo") == "ia" and pg.p.evaluate("() => !!PORT.diseno.fondo.imagen"),
       "el fondo hecho con IA queda puesto")
    hecho = pg.p.evaluate("() => PORT.diseno.fondo.imagen")
    _r, d = api.get(f"/api/publicar/videos/{pid}/portada/diseno")
    ok(hecho in (d.get("fondos") or []), "y queda entre los «fondos ya hechos» del vídeo (lo pagado no se pierde)")
    # cambiar la paleta no se lleva lo hecho a mano
    n_antes = pg.p.evaluate("() => PORT.diseno.elementos.length")
    pg.p.evaluate("() => { PORT.diseno.elementos.push({tipo: 'icono', icono: 'fuego', x: 0.1, y: 0.1}); }")
    pg.p.locator(".capa-portada select").nth(1).select_option("fiesta")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate("() => PORT.diseno.elementos.length") == n_antes + 1
       and pg.p.evaluate("() => PORT.diseno.paleta") == "fiesta",
       "cambiar la paleta deja los elementos añadidos a mano")
    # usarla como portada
    pg.pulsar(".capa-portada button", "Usar como portada")
    fin = time.time() + 40
    while time.time() < fin and pg.visible(".capa-portada"):
        pg.p.wait_for_timeout(500)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    ok(((ficha.get("portada") or {}).get("imagen") or ""), "«Usar como portada» la deja como la imagen de portada")
    ok(os.path.exists(ruta), "y guarda el diseño para retocarlo otro día")
    _r, d = api.get(f"/api/publicar/videos/{pid}/portada/diseno")
    ok(d.get("guardado") and d["diseno"]["plantilla"] == "oferta", "al volver a abrirlo sale el guardado")
    pg.sin_errores("las portadas diseñadas")
    pg.cerrar()
    # en el móvil, cabe
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="portadas móvil")
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".portada-publicar button", "Diseñar portada", 20), "en el móvil también está")
    pg.pulsar(".portada-publicar button", "Diseñar portada")
    ok(pg.esperar(".capa-portada .vista-portada-grande img", segundos=30), "y se abre")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"sin salirse por los lados ({ancho}px)")
    pg.captura("portada_movil", entera=False)
    pg.sin_errores("las portadas en el móvil")
    pg.cerrar()
# ======================================================================
# NOTAS DEL 19-10-2026 (rama `notas-19oct`). Tramo propio, al final.

@escenario
def notas_del_19_10(navegador, datos):
    """Crear → Tus proyectos, el tope de las láminas a la vista, el asistente
    en ámbar con un fallo pasajero y el ajuste fino de la música en el vídeo nuevo."""
    pg = Pagina(navegador, datos)
    # CREAR SIEMPRE ABRE «TUS PROYECTOS», aunque se dejara un vídeo abierto
    pg.js(f"await abrirVideoLight('{datos['video']}');")
    pg.pulsar("#barra-modulos .boton-modulo", "Inicio")
    pg.pulsar("#barra-modulos .boton-modulo", "Crear")
    ok(pg.esperar("h2", "Tus proyectos", 10), "CREAR: abre «Tus proyectos», no el último vídeo")
    pg.pulsar("#barra-modulos .boton-modulo", "Inicio")
    # desde `diseno-crearia` (19-10-2026), el botón «Tus proyectos» del saludo del panel
    pg.pulsar(".saludo-botones button", "Tus proyectos")
    ok(pg.esperar("h2", "Tus proyectos", 10), "CREAR: también desde el Inicio («Tus proyectos»)")

    # LÁMINAS: el campo dice su tope y cuenta
    pg.js(f"nuevaLamina(fichaLight('{datos['preset']}'), '');")
    ok(pg.esperar(".dialogo textarea", segundos=5), "LÁMINAS: «Una lámina más» abre su diálogo")
    tope = pg.p.locator(".dialogo textarea").first.get_attribute("maxlength")
    ok(tope and int(tope) >= 1500, f"LÁMINAS: el campo admite 1.500 caracteres ({tope})")
    pg.p.locator(".dialogo textarea").first.fill("una sala de eventos amplia " * 20)
    ok(pg.visible(".dialogo .cuenta-caracteres", "de 1500"), "LÁMINAS: y cuenta lo escrito «N de 1500»")
    pg.pulsar(".dialogo button", "Cancelar")

    # ASISTENTE: con sesión y un fallo pasajero, ámbar y no rojo
    clases = pg.p.evaluate("""() => { const antes = ASISTENTE.estado;
      ASISTENTE.estado = {listo: true, aviso: 'mia: un guion tardó', cuentas: [], cuenta: {correo: 'a@b.c'}};
      pintarAsistente(); const b = document.querySelector('#burbuja-asistente');
      const c = [b.classList.contains('dudosa'), b.classList.contains('sin-sesion')];
      ASISTENTE.estado = antes; pintarAsistente(); return c; }""")
    ok(clases == [True, False], f"ASISTENTE: un fallo pasajero se pinta ámbar, no «sin sesión» ({clases})")

    # MÚSICA: el ajuste fino, ya en el encargo de un vídeo nuevo
    pg.js(f"await cargarGaleriaLight(true); elegirEstiloLight(fichaLight('{datos['preset']}'));")
    ok(pg.esperar("h2", "Un vídeo nuevo", 10), "MÚSICA: «Un vídeo nuevo» se abre")
    pg.p.locator(".fila-ajuste").filter(has_text="Música").locator("button", has_text="Cambiar").first.click()
    ok(pg.esperar(".editor-ajuste input.volumen-fino", segundos=5),
       "MÚSICA: el ajuste fino en dB sale en el vídeo nuevo (antes, solo en uno ya creado)")
    pg.p.evaluate("""() => { const r = document.querySelector('.editor-ajuste input.volumen-fino');
      r.value = -4; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); }""")
    pg.p.wait_for_timeout(1200)
    enviado = pg.p.evaluate("() => opcionesParaCrear(APP.light.video.encargo || encargoLight()).musica_db")
    ok(enviado == -4, f"MÚSICA: y viaja al crear el vídeo ({enviado})")
    pg.sin_errores("las notas del 19-10")
    pg.cerrar()


@escenario
def publicar_notas_del_19_10(navegador, datos):
    """Las notas del dueño del 19-10 en Publicar, como se vieron: UNA nota SEO
    con un botón por punto (palabra clave, portada, ubicación), la revisión de
    Claude sin su «X/100» y con «con estos cambios: A → B», sin «Aceptar todo»
    vacío; los hashtags que no caben se dicen; la pastilla de guardado y lo
    tecleado que ya no se pierde al cambiar de vídeo; y los fallos que se
    quitan desde Inicio, con los descartados plegados en la ficha."""
    import datetime as _dt                                   # noqa: PLC0415
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.put(f"/api/publicar/proyectos/{cid}", {"palabra_clave": "", "ig_ubicacion": ""})
    muchos = [f"tag{i}" for i in range(35)]
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram"], "palabra_clave": "",
                                             "portada": {"ms": None, "quitar_imagen": True},
                                             "textos": {"instagram": {"descripcion": "Reel de las notas",
                                                                      "cta": "", "hashtags": muchos}}})
    ruta_ficha = os.path.join(datos["proyectos"], "_sistema", "publicar", "videos", f"{pid}.json")

    def tocar_ficha(fn):
        with open(ruta_ficha, encoding="utf-8") as fh:
            guardada = json.load(fh)
        fn(guardada)
        with open(ruta_ficha, "w", encoding="utf-8") as fh:
            json.dump(guardada, fh, ensure_ascii=False)
    tocar_ficha(lambda g: (g.pop("palabra_propuesta", None), g.pop("seo_propuesta", None)))

    # CADA PARTE POR SU LADO: si una se corta (sin el arreglo, un botón que no
    # está), las demás se miran igual
    def parte(nombre, fn):
        try:
            fn()
        except Exception as fallo:                           # noqa: BLE001
            traceback.print_exc()
            ok(False, f"{nombre} se cortó: {type(fallo).__name__}: {str(fallo)[:120]}")

    def parte_nota():
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".texto-red[data-red=instagram] .nota-seo", segundos=15), "la ficha con su nota SEO")
        # --- los hashtags que no caben, dichos
        ok(pg.visible(".texto-red[data-red=instagram] .aviso-red", "5 hashtags no caben en Instagram"),
           "35 hashtags en Instagram: los 5 que no caben se dicen (antes se cortaban a 15 sin aviso)")
        # --- un botón por punto
        pg.js("PUB.notaAbierta = {instagram: true}; pintarModulo();")
        nota = ".texto-red[data-red=instagram] .nota-seo"
        ok(pg.visible(f'{nota} .punto-seo[data-punto="palabra"] button', "Escribir palabra clave"),
           "sin palabra clave: «Escribir palabra clave»")
        pg.pulsar(f'{nota} .punto-seo[data-punto="palabra"] button')
        foco = pg.p.evaluate("() => document.activeElement && document.activeElement.dataset.foco")
        ok(foco == "seo-palabra-video", f"lleva el cursor al campo «Palabra clave de este vídeo» ({foco})")
        pg.js("document.activeElement.blur(); PUB.notaAbierta = {instagram: true}; pintarModulo();")
        ok(pg.visible(f'{nota} .punto-seo[data-punto="portada"] button', "Elegir portada"), "sin portada: «Elegir portada»")
        pg.pulsar(f'{nota} .punto-seo[data-punto="portada"] button')
        dentro = pg.p.evaluate("() => !!(document.activeElement && document.activeElement.closest('.portada-publicar'))")
        ok(dentro, "lleva al bloque de la portada")
        pg.js("document.activeElement.blur(); PUB.notaAbierta = {instagram: true}; pintarModulo();")
        ok(pg.visible(f"{nota} .pista-punto-seo", "NÚMERO del Lugar"), "sin ubicación: la pista de qué poner")
        texto = pg.p.evaluate("() => document.querySelector('#modulo').innerText")
        ok("Lo fijo → SEO" not in texto and "Cuentas y ajustes → SEO de este proyecto" in texto,
           "dónde está cada cosa, con el nombre de verdad de la pantalla")
        # la palabra que propone Claude, con su «Usar»
        tocar_ficha(lambda g: g.update(palabra_propuesta="consolas en Lima"))
        pg.js("await cargarPublicar(true); PUB.notaAbierta = {instagram: true}; pintarModulo();")
        ok(pg.visible(f'{nota} .punto-seo[data-punto="palabra"] button', "Usar «consolas en Lima»"),
           "con una propuesta de Claude: «Usar \"consolas en Lima\"»")
        pg.pulsar(f'{nota} .punto-seo[data-punto="palabra"] button', "Usar")
        pg.p.wait_for_timeout(800)
        _r, ficha = api.get(f"/api/publicar/videos/{pid}")
        ok(ficha["seo"]["palabra_propia"] == "consolas en Lima", "«Usar» la pone como palabra clave del vídeo")
        # la ubicación: un enlace que abre «SEO de este proyecto» con el cursor en el campo
        pg.js("PUB.notaAbierta = {instagram: true}; pintarModulo();")
        pg.pulsar(f'{nota} .punto-seo[data-punto="ubicacion"] a')
        fin = time.time() + 10
        foco = ""
        while time.time() < fin and foco != f"seo-ig_ubicacion-{cid}":
            pg.p.wait_for_timeout(300)
            foco = pg.p.evaluate("() => (document.activeElement && document.activeElement.dataset.foco) || ''")
        ok(foco == f"seo-ig_ubicacion-{cid}" and pg.visible(".seo-proyecto[open] summary", "SEO de este proyecto"),
           f"la ubicación: abre «SEO de este proyecto» con el cursor en su campo ({foco})")
        pg.sin_errores("los botones de la nota SEO")
        pg.cerrar()

    def parte_revision():
        # --- la revisión de Claude: una sola nota
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".seo-video button", "Optimizar SEO con Claude", 15), "de vuelta en la ficha")
        pg.pulsar(".seo-video button", "Optimizar SEO con Claude")
        ok(pg.esperar(".propuesta-seo .cambio-seo", segundos=20), "«Optimizar SEO»: la propuesta")
        texto = pg.p.evaluate("() => document.querySelector('#modulo').innerText")
        ok("según Claude" not in texto.lower() and "SEGÚN CLAUDE" not in texto,
           "sin el «X/100 según Claude»: la nota es una")
        ok(pg.visible(".propuesta-seo .nota-con-cambios", "con estos cambios:"),
           "«con estos cambios: A → B», con la nota del Studio")
        ok(not any("primera línea no dice la palabra clave" in x for x in
                   pg.p.evaluate("() => [...document.querySelectorAll('.propuesta-seo .meta')].map(x => x.textContent)")),
           "lo que Claude repite de la nota no sale dos veces")
        ok(pg.visible(".propuesta-seo button", "Aceptar todo"), "con cambios, «Aceptar todo»")
        tocar_ficha(lambda g: g.update(seo_propuesta={"al": "2026-10-19T10:00:00", "redes": {
            "instagram": {"campos": {}, "fallos": ["el texto no dice para qué tipo de fiesta es"]}}}))
        pg.js("await cargarPublicar(true); pintarModulo();")
        ok(pg.esperar(".propuesta-seo", "no propone cambios", 5) and not pg.visible(".propuesta-seo button", "Aceptar todo"),
           "sin cambios que aceptar, no hay «Aceptar todo»")
        pg.pulsar(".propuesta-seo button", "Cerrarla")
        pg.sin_errores("la revisión SEO")
        pg.cerrar()

    def parte_guardado():
        # --- la pastilla de guardado
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}');")
        caja = ".texto-red[data-red=instagram] textarea"
        ok(pg.esperar(caja, segundos=15), "la ficha para escribir")
        ok(pg.visible(".guardado-publicar"), "la pastilla de guardado, junto a los textos")
        pg.p.locator(caja).first.fill("Uno")
        ok(pg.visible(".guardado-publicar", "Sin guardar"), "al teclear: «Sin guardar…»")
        ok(pg.esperar(".guardado-publicar", "Guardado", 8), "y al poco «✓ Guardado hh:mm»")
        ok(bool(re.search(r"Guardado \d\d:\d\d", pg.p.locator(".guardado-publicar").first.inner_text(), re.I)),
           f"con su hora ({pg.p.locator('.guardado-publicar').first.inner_text()!r})")
        # sale mal: lo dice, con «Reintentar»
        pg.p.route("**/api/publicar/videos/*", lambda ruta: ruta.fulfill(status=500, body='{"detail": "caído"}',
                                                                           content_type="application/json")
                   if ruta.request.method == "PUT" else ruta.continue_())
        pg.p.locator(caja).first.fill("Dos")
        ok(pg.esperar(".guardado-publicar", "No se ha guardado", 8), "si falla: «No se ha guardado»")
        hay = pg.p.evaluate("""() => { const ev = new Event('beforeunload', {cancelable: true});
          window.dispatchEvent(ev); return ev.defaultPrevented; }""")
        ok(hay, "y cerrar la pestaña con algo sin guardar lo pregunta el navegador")
        pg.p.unroute("**/api/publicar/videos/*")
        pg.pulsar(".guardado-publicar button", "Reintentar")
        ok(pg.esperar(".guardado-publicar", "Guardado", 8), "«Reintentar» lo guarda")
        _r, ficha = api.get(f"/api/publicar/videos/{pid}")
        ok(ficha["textos"]["instagram"]["descripcion"] == "Dos", "y llega al servidor")
        hay = pg.p.evaluate("""() => { const ev = new Event('beforeunload', {cancelable: true});
          window.dispatchEvent(ev); return ev.defaultPrevented; }""")
        ok(not hay, "con todo guardado, cerrar no pregunta nada")
        pg.sin_errores("la pastilla de guardado")
        pg.cerrar()

    def parte_cambio():
        # cambiar de vídeo enseguida ya no pierde lo último (por su lado: sin
        # el arreglo, la pastilla no existe y la parte de arriba se corta)
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}');")
        caja = ".texto-red[data-red=instagram] textarea"
        ok(pg.esperar(caja, segundos=15), "la ficha, para escribir y cambiar de vídeo")
        _r, lista = api.get("/api/proyectos")
        otros = [x.get("id") or x.get("pid") for x in (lista if isinstance(lista, list) else lista.get("proyectos") or [])]
        otro = next((x for x in otros if x and x != pid), "otro_video")
        pg.p.locator(caja).first.fill("Tres, y me voy")
        pg.js(f"await irASeccionPublicar('ficha', '{otro}');")
        _r, ficha = api.get(f"/api/publicar/videos/{pid}")
        ok(ficha["textos"]["instagram"]["descripcion"] == "Tres, y me voy",
           f"cambiar de vídeo antes de 0,9 s guarda antes lo tecleado ({ficha['textos']['instagram']['descripcion']!r})")
        pg.sin_errores("cambiar de vídeo")
        pg.cerrar()

    ahora = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-5))).strftime("%Y-%m-%dT%H:%M:%S")

    def envio(i, red, estado):
        return {"id": f"n19e{i}", "red": red, "estado": estado, "cuando": ahora, "lote": f"n19l{i}",
                "perfil": "p", "modo": "ahora", "error": "falló adrede" if estado != "publicado" else ""}

    def parte_fallos():
        # --- los fallos: se quitan desde Inicio
        tocar_ficha(lambda g: g.update(envios=[envio(1, "instagram", "fallido"), envio(2, "instagram", "publicado"),
                                               envio(3, "tiktok", "fallido")]))
        pg = Pagina(navegador, datos)
        pg.js("PUB.pid = 'otro_video'; irAModulo('inicio');")
        ok(pg.esperar('.fila-envio[data-envio="n19e3"] button', "Quitar de la lista", 15),
           "Inicio: el fallo trae «Quitar de la lista»")
        ok(pg.visible('.fila-envio[data-envio="n19e1"]', "ya salió en otro envío")
           and not pg.visible('.fila-envio[data-envio="n19e1"] button', "Quitar"),
           "el que se reenvió y salió lo dice, sin pedir nada")
        antes = pg.p.evaluate("() => PUB.avisos")
        pg.pulsar('.fila-envio[data-envio="n19e3"] button', "Quitar de la lista")
        fin = time.time() + 8
        while time.time() < fin and pg.visible('.fila-envio[data-envio="n19e3"] button', "Quitar"):
            pg.p.wait_for_timeout(300)
        _r, cola = api.get("/api/publicar/cola")
        ok(not any(e["id"] == "n19e3" for e in cola["fallidos"]),
           "«Quitar» lo saca de la lista, con el vídeo de LA FILA (no el último abierto)")
        ok(not any(e["id"] == "n19e1" for e in cola["fallidos"]), "el que salió después ya no contaba")
        despues = pg.p.evaluate("() => PUB.avisos")
        ok(despues == antes - 1, f"y el contador de la barra baja ({antes} → {despues})")
        pg.sin_errores("los fallos que se quitan")
        pg.cerrar()

    def parte_descartados():
        # --- en la ficha, los descartados van plegados
        tocar_ficha(lambda g: g.update(envios=[envio(1, "instagram", "fallido"), envio(2, "instagram", "publicado"),
                                               dict(envio(3, "tiktok", "cancelado"), nota="fallo descartado")]))
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".envios-descartados > summary", "1 descartado", 15), "en la ficha: «1 descartado», plegado")
        ok(not pg.visible(".envios-descartados .fila-envio"), "sin abrirlo, el descartado no sale mezclado")
        pg.pulsar(".envios-descartados > summary")
        ok(pg.visible(".envios-descartados .fila-envio", "falló adrede"), "y al abrirlo, ahí está")
        pg.sin_errores("los descartados")
        pg.cerrar()

    parte("la nota SEO con un botón por punto", parte_nota)
    parte("la revisión de Claude", parte_revision)
    parte("la pastilla de guardado", parte_guardado)
    parte("cambiar de vídeo enseguida", parte_cambio)
    parte("los fallos que se quitan", parte_fallos)
    parte("los descartados, plegados", parte_descartados)
    tocar_ficha(lambda g: g.update(envios=[]))


@escenario
def elementos_en_el_video(navegador, datos):
    """Rama elementos-video (19-10-2026): el grafismo encima de cada imagen, al
    ritmo de la voz. Se añade y se guarda en la diapositiva, Claude lo propone
    para todo el vídeo, solo queda pendiente el montaje (ni una imagen), y al
    montar los elementos van en la capa del plano. La opción de pedir la imagen
    con el texto dentro apunta una nota (se paga al aplicarla, no antes)."""
    api, pid = datos["api"], datos["video"]
    api.libre(pid)
    _r, antes = api.get(f"/api/proyectos/{pid}")
    assets_antes = {p.get("id"): (p.get("estado"), p.get("firma")) for p in antes.get("pasos") or []}.get("assets")
    pg = Pagina(navegador, datos, nombre="elementos")
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".elementos-plano", "Elementos de esta imagen", 20), "la diapositiva trae «Elementos de esta imagen»")
    sid = pg.p.evaluate("() => (PREVIA.ficha && PREVIA.ficha.escenas[PREVIA.indice || 0] || {}).id")
    pg.pulsar(".elementos-plano button", "Añadir")
    ok(pg.esperar(".elemento-plano", segundos=10) and pg.visible(".elementos-plano", "sin guardar"),
       "«Añadir» pone uno, sin guardar todavía")
    pg.p.locator(".elemento-plano input[type=text]").first.fill("¡GRATIS!")
    pg.pulsar(".elementos-plano button", "Ver cómo queda")
    ok(pg.esperar(".vista-elementos", segundos=30), "«Ver cómo queda» pinta la imagen con el elemento encima")
    pg.pulsar(".elementos-plano button", "Guardar")
    fin = time.time() + 20
    guardados = {}
    while time.time() < fin:
        _r, d = api.get(f"/api/proyectos/{pid}/planos/elementos")
        guardados = d.get("planos") or {}
        if guardados:
            break
        pg.p.wait_for_timeout(500)
    ok(any(e.get("texto") == "¡GRATIS!" for l in guardados.values() for e in l),
       f"«Guardar» lo deja en el plano ({list(guardados)[:3]}, {sid})")
    _r, despues = api.get(f"/api/proyectos/{pid}")
    estados = {p.get("id"): (p.get("estado"), p.get("firma")) for p in despues.get("pasos") or []}
    ok(estados.get("assets") == assets_antes, "ni una imagen queda pendiente (no se paga nada)")
    ok(estados.get("callouts", ("",))[0] == "obsoleto", "solo queda pendiente el montaje")
    # Claude, para todo el vídeo (CLI falso)
    pg.js("pintarLight();")
    pg.pulsar(".elementos-video button", "Proponer para todo el vídeo")
    ok(pg.esperar(".elementos-video .caja-aviso", "Claude propone", 60), "Claude propone elementos para todo el vídeo")
    pg.pulsar(".elementos-video button", "Aplicar sumando")
    fin = time.time() + 20
    while time.time() < fin:
        _r, d = api.get(f"/api/proyectos/{pid}/planos/elementos")
        if len(d.get("planos") or {}) > 1:
            break
        pg.p.wait_for_timeout(500)
    planos = d.get("planos") or {}
    ok(len(planos) > 1 and "NOEXISTE" not in planos, f"se aplican a varias imágenes ({len(planos)}) y no a planos que no existen")
    ok(any(e.get("texto") == "¡GRATIS!" for e in planos.get(sid, [])), "sumando: lo que ya había se queda")
    # montar y mirarlo en la capa
    r, dd = api.post(f"/api/proyectos/{pid}/generar", {"tanda": "render", "modo": "pendientes"})
    fin_montaje = api.esperar(dd.get("trabajo_id") or (dd.get("trabajo") or {}).get("id"), 600)
    ok(fin_montaje.get("estado") == "listo", f"se vuelve a montar ({fin_montaje.get('estado')})")
    activa = _version_de(datos, "callouts", "").get("activa")
    carpeta = os.path.join(datos["proyectos"], pid, "pasos", "callouts", f"v{activa}", "capas_fijas")
    capa = ""
    if os.path.isfile(os.path.join(carpeta, f"{sid}.svg")):
        with open(os.path.join(carpeta, f"{sid}.svg"), encoding="utf-8") as fh:
            capa = fh.read()
    ok("¡GRATIS!" in capa and "animateTransform" in capa, "al montar, el elemento va en la capa del plano, animado")
    # la otra opción: texto dentro de la imagen (nota, se paga al aplicarla)
    _r, rep = api.get(f"/api/proyectos/{pid}/repaso")
    notas_antes = len(rep.get("notas") or [])
    pg.js("APP.light.video.vista = 'previa'; pintarLight();")
    pg.pulsar(".elementos-plano button", "Texto dentro de la imagen")
    ok(pg.esperar(".capa-dialogo", "Texto dentro de la imagen", 10), "pide el texto y avisa de que se paga")
    pg.p.locator(".capa-dialogo input").first.fill("OFERTA")
    pg.pulsar(".capa-dialogo button", "Apuntar la nota")
    pg.p.wait_for_timeout(1500)
    _r, rep = api.get(f"/api/proyectos/{pid}/repaso")
    nuevas = [n for n in rep.get("notas") or [] if "OFERTA" in str(n.get("texto") or "")]
    ok(len(rep.get("notas") or []) == notas_antes + 1 and nuevas and nuevas[0].get("estado") != "aplicado",
       "queda como nota de esa imagen, sin aplicar (no se ha pagado nada)")
    _r, fin_estado = api.get(f"/api/proyectos/{pid}")
    ok({p.get("id"): (p.get("estado"), p.get("firma")) for p in fin_estado.get("pasos") or []}.get("assets") == assets_antes,
       "y las imágenes siguen igual")
    # dejarlo como estaba para los escenarios de después
    api.post(f"/api/proyectos/{pid}/elementos/aplicar", {"planos": {k: [] for k in planos}, "reemplazar": True})
    for n in nuevas:
        api._r("DELETE", f"/api/proyectos/{pid}/repaso/{n.get('id')}")
    pg.sin_errores("los elementos del vídeo")
    pg.cerrar()


# ------------------------------------------------------- arreglos-19oct (segunda tanda)

#: Dónde está el scroll de cada caja que lo lleva (la ventana no se mueve nunca).
SCROLL = "(() => ({panel: ($('#panel')||{}).scrollTop, modulo: ($('#modulo')||{}).scrollTop}))()"


@escenario
def la_pantalla_no_salta(navegador, datos):
    """Notas del dueño del 19-10: al terminar un remontaje lanzado desde el
    Encargo, al «Traer» el estilo y al cambiar los días de Resultados, la
    pantalla volvía arriba del todo. El scroll se conserva (±20 px)."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    pg.p.wait_for_timeout(1500)
    pg.js("APP.light.video.vista = 'encargo_video'; pintarLight();")
    ok(pg.esperar(".fila-ajuste", "Música", 20), "SCROLL: el Encargo enseña los ajustes del montaje")

    # 1) el Encargo bajado, se cambia la música y se espera al montaje
    pg.p.locator(".fila-ajuste").filter(has_text="Música").locator(".fila-ajuste-cab button").first.click()
    pg.p.wait_for_timeout(600)
    boton = ("() => [...document.querySelectorAll('.editor-ajuste .herramientas button')]"
             ".find(x => x.innerText.trim() === 'Suave')")
    pg.p.evaluate(f"() => ({boton})().scrollIntoView({{block: 'center'}})")
    pg.p.wait_for_timeout(500)
    antes = pg.p.evaluate(SCROLL)["panel"]
    pg.p.evaluate(f"() => ({boton})().click()")
    pg.p.wait_for_timeout(1500)
    # desde el Encargo se monta con «Montar el vídeo con N cambios», en la
    # barra (decisión 9 del rediseño de Crear)
    pg.p.evaluate("() => { const b = [...document.querySelectorAll('.barra-accion button')]"
                  ".find(x => /Montar el vídeo con/.test(x.innerText)); if (b) b.click(); }")
    pg.p.wait_for_timeout(1500)
    pg.sin_trabajo()
    pg.p.wait_for_timeout(2500)
    despues = pg.p.evaluate(SCROLL)["panel"]
    ok(antes > 100 and abs(despues - antes) <= 20,
       f"SCROLL: tras el montaje lanzado desde el Encargo, la pantalla sigue donde estaba ({antes} → {despues})")

    # 2) «Traer» del estilo (el vídeo de prueba, como uno de verdad, ya tiene
    # algo del estilo sin traer; si no, se le cambian los rótulos al estilo)
    _r, cambios = api.get(f"/api/proyectos/{pid}/estilo/cambios")
    if not any(p.get("cambia") for p in cambios.get("partes") or []):
        api.put(f"/api/presets-light/{datos['preset']}", {"instrucciones": "Cercano y con humor."})
    # «Su estilo» vive en el paso Estilo desde el rediseño de Crear
    pg.js("await recargarVideoAbierto(); irAPasoDelCarril('estilo');")
    pg.p.wait_for_timeout(3000)
    hay = pg.p.evaluate("() => { const c = document.querySelector('.estilo-del-video input[type=checkbox]');"
                        " if (!c) return false; if (!c.checked) c.click(); return true; }")
    ok(hay, "SCROLL: «Su estilo» ofrece algo que traer")
    if hay:
        pg.p.wait_for_timeout(600)
        pg.p.evaluate("() => document.querySelector('.estilo-del-video').scrollIntoView({block: 'center'})")
        # en el paso Estilo «Su estilo» va arriba del todo: se baja un poco
        # para que subir la pantalla se note
        pg.p.evaluate("() => { const p = $('#panel'); if (p.scrollTop < 150) p.scrollTop = 200; }")
        pg.p.wait_for_timeout(500)
        antes = pg.p.evaluate(SCROLL)["panel"]
        pg.p.evaluate("() => [...document.querySelectorAll('.estilo-del-video button')]"
                      ".find(b => /Traer/.test(b.innerText)).click()")
        pg.p.wait_for_timeout(3500)
        despues = pg.p.evaluate(SCROLL)["panel"]
        ok(antes > 100 and abs(despues - antes) <= 20,
           f"SCROLL: «Traer» del estilo no sube la pantalla ({antes} → {despues})")

    # 3) Publicar → Resultados → los días
    pg.js("irAModulo('publicar'); irASeccionPublicar('resultados');")
    pg.p.wait_for_timeout(3000)
    pg.p.evaluate("() => { const m = $('#modulo'); m.scrollTop = Math.min(400, m.scrollHeight - m.clientHeight); }")
    pg.p.wait_for_timeout(400)
    antes = pg.p.evaluate(SCROLL)["modulo"]
    pg.p.evaluate("""() => { const s = [...document.querySelectorAll('#modulo select')]
      .find(y => [...y.options].some(o => /días/.test(o.text)));
      s.selectedIndex = (s.selectedIndex + 1) % s.options.length;
      s.dispatchEvent(new Event('change', {bubbles: true})); }""")
    pg.p.wait_for_timeout(3000)
    despues = pg.p.evaluate(SCROLL)["modulo"]
    ok(antes > 100 and abs(despues - antes) <= 20,
       f"SCROLL: cambiar los días de Resultados no sube la pantalla ({antes} → {despues})")
    # ir a otra sección sí va arriba
    pg.js("irASeccionPublicar('cola');")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.evaluate(SCROLL)["modulo"] < 5, "SCROLL: ir a otra sección sí empieza arriba")
    pg.sin_errores("la pantalla no salta")
    pg.cerrar()


@escenario
def encargo_un_solo_montaje(navegador, datos):
    """Notas del dueño del 19-10: en el Encargo cada cambio del montaje volvía
    a montar el vídeo y el siguiente daba «el vídeo se está montando ahora».
    Ahora se guardan sin montar y una franja los aplica todos de una vez."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    pg.p.wait_for_timeout(1500)
    pg.js("APP.light.video.vista = 'encargo_video'; pintarLight();")
    ok(pg.esperar(".fila-ajuste", "Música", 20), "ENCARGO: se ven los ajustes del montaje")
    pg.p.locator(".fila-ajuste").filter(has_text="Música").locator(".fila-ajuste-cab button").first.click()
    pg.p.wait_for_timeout(600)
    antes = len(pg.avisos())
    for nivel in ("Alta", "Suave"):
        pg.p.evaluate(f"""() => [...document.querySelectorAll('.editor-ajuste .herramientas button')]
          .find(x => x.innerText.trim() === '{nivel}').click()""")
        pg.p.wait_for_timeout(900)
    pg.p.evaluate("""() => { const r = document.querySelector('.editor-ajuste input.volumen-fino');
      r.value = -2; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change')); }""")
    pg.p.wait_for_timeout(1800)
    avisos = pg.avisos()[antes:]
    ok(not any("montando ahora" in a for a in avisos),
       f"ENCARGO: tres cambios seguidos sin ningún «se está montando ahora» ({avisos})")
    ok(pg.p.evaluate("() => ((APP.trabajos[CLAVE_VIDEO_LIGHT] || {}).estado) !== 'ejecutando'"),
       "ENCARGO: y sin lanzar ningún montaje")
    ok(pg.esperar(".franja-sin-aplicar", "sin aplicar", 5),
       "ENCARGO: sale la franja «Hay cambios del montaje sin aplicar»")
    _r, trabajos_antes = api.get(f"/api/trabajos?proyecto={pid}")
    vistos = {x.get("id") for x in trabajos_antes.get("trabajos") or []}
    ok(pg.visible(".franja-sin-aplicar", "se montan con"),
       "ENCARGO: y la franja dice con qué botón se montan")
    _montar_los_cambios(pg)
    pg.p.wait_for_timeout(800)
    _r, trabajos = api.get(f"/api/trabajos?proyecto={pid}")
    nuevos = [t for t in trabajos.get("trabajos") or [] if t.get("id") not in vistos]
    ok(len(nuevos) == 1, f"ENCARGO: «Montar el vídeo con N cambios» lanza UN solo montaje ({[t.get('nombre') for t in nuevos]})")
    pg.sin_trabajo(600)
    # en el recorrido entero lo de antes (el «Traer» de la_pantalla_no_salta)
    # deja también las capas por rehacer: es un montaje largo, no una mezcla
    api.libre(pid, 600)
    pg.p.wait_for_timeout(2500)
    ok(not pg.visible(".franja-sin-aplicar"), "ENCARGO: al terminar, la franja se va")
    _r, render = api.get(f"/api/proyectos/{pid}/pasos/render")
    ok(render.get("estado") == "listo", f"ENCARGO: y el vídeo queda montado y al día ({render.get('estado')})")
    pg.sin_errores("varios cambios del Encargo, un solo montaje")
    pg.cerrar()


@escenario
def parar_un_montaje(navegador, datos):
    """Notas del dueño del 19-10: «Parar» un montaje esperaba a que ffmpeg
    acabara y el botón no decía nada. Ahora dice «Cancelando…», se para en el
    acto y el vídeo sigue siendo el de antes, sin caja de error."""
    if os.name == "nt":
        print("  (el freno de ffmpeg es de bash: se salta en Windows)")
        return
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, render = api.get(f"/api/proyectos/{pid}/pasos/render")
    version_antes = render.get("version_activa") or render.get("activa")
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    pg.p.wait_for_timeout(1500)
    pg.js("APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar(".ajustes-en-video .fila-ajuste", "Música", 20), "PARAR: la pantalla Vídeo con sus ajustes")
    freno = os.path.join(os.path.dirname(datos["proyectos"]), "ffmpeg_lento")
    with open(freno, "w", encoding="utf-8") as fh:
        fh.write("1")
    try:
        pg.p.locator(".ajustes-en-video .fila-ajuste").filter(has_text="Música") \
            .locator(".fila-ajuste-cab button").first.click()
        pg.p.wait_for_timeout(600)
        pg.p.evaluate("""() => { const b = [...document.querySelectorAll('.ajustes-en-video .editor-ajuste .herramientas button')]
          .find(x => x.innerText.trim() === 'Alta' && !x.classList.contains('activo'))
          || [...document.querySelectorAll('.ajustes-en-video .editor-ajuste .herramientas button')]
          .find(x => x.innerText.trim() === 'Suave'); b.click(); }""")
        pg.p.wait_for_timeout(1500)
        # tocar el ajuste no monta (decisión 9): monta el botón de la barra
        ok(not pg.visible("button.peligro", "Parar"), "PARAR: cambiar la música no monta el vídeo sola")
        _montar_los_cambios(pg)
        ok(pg.esperar("button.peligro", "Parar", 15),
           f"PARAR: el montaje arranca y sale «Parar» ({pg.avisos()[-2:]})")
        pg.p.wait_for_timeout(2500)
        t0 = time.time()
        # se mira en el MISMO instante del clic: el montaje se para tan rápido
        # que «Cancelando…» dura menos de lo que tarda en mirarse otra vez
        tras = pg.p.evaluate("""() => {
          [...document.querySelectorAll('button.peligro')].find(x => x.innerText.trim() === 'Parar').click();
          const b = [...document.querySelectorAll('button.peligro')].find(x => /Cancelando/.test(x.innerText));
          return b ? {texto: b.innerText.trim(), apagado: b.disabled} : null; }""")
        ok(tras and tras["texto"] == "Cancelando…", f"PARAR: el botón dice «Cancelando…» ({tras})")
        ok(tras and tras["apagado"], "PARAR: y está apagado")
        pg.sin_trabajo(30)
        tardo = time.time() - t0
        ok(tardo < 8, f"PARAR: se para en el acto ({tardo:.1f} s con un montaje de 20 s)")
    finally:
        os.remove(freno)
    pg.p.wait_for_timeout(1500)
    avisos = pg.avisos()
    ok(any("sigue siendo el de antes" in a for a in avisos),
       f"PARAR: el aviso dice que el vídeo sigue siendo el de antes ({avisos[-2:]})")
    ok(not pg.visible(".caja-error"), "PARAR: sin caja de error")
    ok(pg.visible("video"), "PARAR: el reproductor sigue ahí")
    _r, render = api.get(f"/api/proyectos/{pid}/pasos/render")
    ok((render.get("version_activa") or render.get("activa")) == version_antes,
       f"PARAR: la versión del vídeo no cambia ({version_antes})")
    trabajo = os.path.join(datos["proyectos"], pid, "pasos", "render", "trabajo")
    ok(not os.path.exists(trabajo), "PARAR: y no queda nada en trabajo/")
    # y volver a montar es solo volver a mezclar
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=render")
    render_plan = [t for f in plan.get("fases") or [] for t in f.get("tareas") or [] if t.get("id") == "render"]
    ok(render_plan and render_plan[0].get("solo_mezcla"),
       f"PARAR: «Montar el vídeo» promete solo volver a mezclar ({render_plan[:1]})")
    pg.sin_errores("parar un montaje")
    pg.cerrar()


@escenario
def video_huerfano_cambia_de_estilo(navegador, datos):
    """Notas del dueño del 19-10: un vídeo cuyo estilo se borró se quedaba
    sin forma de adoptar otro. «Su estilo» ofrece ahora «Restaurarlo» (si está
    en la papelera) y «Cambiar de estilo…», con la vista previa y su coste; y
    la parada «Estilo» lleva ahí."""
    api = datos["api"]
    _r, d = api.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Estilo que se va",
        "datos": {"guion": {"idioma_salida": "es", "instrucciones": "Seco y directo."},
                  "voz": {"voz_id": "v-de-prueba", "idioma": "es", "velocidad": "normal"},
                  "origen": {"tono_prompt": "serio", "estilo_prompt": "plano"}}})
    viejo = (d.get("preset") or {}).get("id") or ""
    _r, creado = api.post(f"/api/presets-light/{viejo}/video", {
        "nombre": "Vídeo que se queda huérfano", "duracion_objetivo_s": 60,
        "material": "Un hecho.\n\nY otro."})
    vid = (creado.get("proyecto") or {}).get("id") or ""
    ok(bool(viejo and vid), "HUÉRFANO: un estilo y un vídeo hecho con él")
    api._r("DELETE", f"/api/presets-canal/{viejo}")          # a la papelera
    pg = Pagina(navegador, datos)
    pg.js("await cargarGaleriaLight(true);")
    pg.js(f"await abrirVideoLight('{vid}');")
    pg.p.wait_for_timeout(1500)
    # el paso «Estilo» del carril no deja al vídeo sin salida: enseña «Su estilo»
    ir_al_paso(pg, "Estilo")
    pg.p.wait_for_timeout(1500)
    ok(pg.esperar(".cambio-de-estilo button", "Restaurarlo", 15),
       "HUÉRFANO: con el estilo en la papelera, «Su estilo» ofrece «Restaurarlo»")
    ok(pg.esperar(".cambio-de-estilo select", None, 5),
       "HUÉRFANO: y el paso «Estilo» abre «Cambiar de estilo…» con la lista de estilos")
    # «Restaurarlo» lo devuelve a tus estilos
    pg.pulsar(".cambio-de-estilo button", "Restaurarlo")
    pg.p.wait_for_timeout(2500)
    ok(any("restaurado" in a for a in pg.avisos()), f"HUÉRFANO: «Restaurarlo» lo dice ({pg.avisos()[-1:]})")
    _r, lista = api.get("/api/presets-canal")
    ok(not any(f.get("id") == viejo for f in lista.get("papelera") or []),
       "HUÉRFANO: y el estilo sale de la papelera")
    ok(not pg.visible(".cambio-de-estilo button", "Restaurarlo"), "HUÉRFANO: el botón se va")
    # y se purga: ahora sí, huérfano de verdad
    api._r("DELETE", f"/api/presets-canal/{viejo}")
    api._r("DELETE", f"/api/presets-canal/papelera/{viejo}?confirmar=1")
    pg.js("await cargarGaleriaLight(true); APP.light.video.cambiosEstilo = null;"
          " APP.light.video.cambioEstilo = {pid: APP.light.video.pid, abierto: true, partes: {}}; pintarLight();")
    pg.p.wait_for_timeout(2000)
    ok(pg.visible(".estilo-del-video", "ya no existe") and pg.esperar(".cambio-de-estilo select", None, 10),
       "HUÉRFANO: con el estilo borrado del todo, «Su estilo» lo dice y deja elegir otro")
    # se elige otro estilo: la vista previa, sin escribir nada
    _r, brief_antes = api.get(f"/api/proyectos/{vid}/pasos/brief")
    pg.p.evaluate(f"""() => {{ const s = document.querySelector('.cambio-de-estilo select');
      s.value = '{datos["preset"]}'; s.dispatchEvent(new Event('change', {{bubbles: true}})); }}""")
    ok(pg.esperar(".cambio-de-estilo .parte-estilo", None, 15),
       "HUÉRFANO: la vista previa enseña las partes que cambiarían, con su coste")
    _r, brief = api.get(f"/api/proyectos/{vid}/pasos/brief")
    ok(brief.get("firma") == brief_antes.get("firma"), "HUÉRFANO: mirar no escribe nada")
    pg.pulsar(".cambio-de-estilo button", "Pasar a este estilo")
    pg.p.wait_for_timeout(2500)
    _r, cambios = api.get(f"/api/proyectos/{vid}/estilo/cambios")
    ok((cambios.get("estilo") or {}).get("id") == datos["preset"],
       f"HUÉRFANO: el vídeo pasa al estilo elegido ({cambios.get('estilo')})")
    ok(any("Ahora es del estilo" in a for a in pg.avisos()),
       f"HUÉRFANO: y lo dice ({pg.avisos()[-2:]})")
    ok(not pg.visible(".cambio-de-estilo button", "Restaurarlo"),
       "HUÉRFANO: «Restaurarlo» ya no sale (su estilo no está en la papelera)")
    ok(pg.visible(".cambio-de-estilo button", "Cambiar de estilo"),
       "HUÉRFANO: «Cambiar de estilo…» sigue a mano")
    pg.sin_errores("vídeo huérfano")
    pg.cerrar()


@escenario
def revision_editorial_del_guion(navegador, datos):
    """Notas del dueño del 19-10: una revisión de sintaxis y redacción del
    guion, como la de un corrector editorial. «Revisión editorial» junto a la
    ortografía; las propuestas se aceptan o rechazan una a una o todas, y
    aceptar cambia el bloque como si se escribiera a mano (con la voz grabada,
    avisa de que hay que regrabar)."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}');")
    pg.p.wait_for_timeout(1500)
    pg.js("APP.light.video.vista = 'guion'; pintarLight();")
    ok(pg.esperar(".revisar-guion button", "Redacción (editorial)", 20),
       "EDITORIAL: «Revisar el guion» tiene la pestaña «Redacción (editorial)», junto a «Ortografía»")
    pg.pulsar(".revisar-guion button", "Redacción (editorial)")
    ok(pg.esperar(".panel-ortografia button", "Revisión editorial", 20),
       "EDITORIAL: y en ella, «Revisión editorial»")
    pg.pulsar(".panel-ortografia button", "Revisión editorial")
    ok(pg.esperar(".panel-editorial .fila-editorial", None, 60),
       "EDITORIAL: salen las propuestas, cada una con su trozo, la propuesta y el motivo")
    filas = pg.p.evaluate("() => [...document.querySelectorAll('.panel-editorial .fila-editorial')].map(f => f.innerText)")
    ok(len(filas) == 4 and all("→" in f for f in filas), f"EDITORIAL: cuatro propuestas ({filas})")

    def en_fila(trozo, boton):
        pg.p.evaluate(f"""() => {{ const f = [...document.querySelectorAll('.panel-editorial .fila-editorial')]
          .find(x => x.innerText.includes({trozo!r}));
          [...f.querySelectorAll('button')].find(b => b.innerText.trim() === {boton!r}).click(); }}""")
        pg.p.wait_for_timeout(2500)

    def bloques():
        _r, guion = api.get(f"/api/proyectos/{pid}/pasos/guion")
        return json.dumps((guion.get("params") or {}).get("bloques") or {}, ensure_ascii=False)

    antes_dialogos = len(pg.dialogos)
    en_fila("descargan el patio", "Rechazar")
    ok("vacían" not in bloques(), "EDITORIAL: rechazar no cambia nada")
    en_fila("el buque atraca", "Aceptar")
    ok("el buque atracó" in bloques(), "EDITORIAL: aceptar una la pone en su bloque (como escrita a mano)")
    ok(any("regrabar" in d for d in pg.dialogos[antes_dialogos:]),
       f"EDITORIAL: con la voz grabada, pregunta antes y dice que habrá que regrabar ({pg.dialogos[-1:]})")
    pg.pulsar(".panel-editorial button", "Aceptar todas")
    pg.p.wait_for_timeout(3000)
    texto = bloques()
    ok("La marina llegó" in texto and "todo quedó incautado" in texto,
       "EDITORIAL: «Aceptar todas» pone las dos del mismo bloque, encadenadas")
    ok(pg.esperar(".panel-editorial", "Decididas las 4", 10), "EDITORIAL: y el panel dice que están todas decididas")
    _r, voz = api.get(f"/api/proyectos/{pid}/pasos/voz")
    ok(voz.get("estado") == "obsoleto", f"EDITORIAL: la voz queda por regrabar ({voz.get('estado')})")
    pg.sin_errores("revisión editorial")
    pg.cerrar()

# ======================================================================
# EL DISEÑO CREARIA (rama `diseno-crearia`, 19-10-2026). Tramo propio y al
# final: el logo y el nombre, el pie, las cuatro paletas (y que se recuerdan),
# el Inicio con «Arma tu panel» (y que se recuerda), el panel de Ayuda del «?».

@escenario
def diseno_crearia(navegador, datos):
    pg = Pagina(navegador, datos)
    ok(pg.visible("#cabecera .marca .marca-logo"), "la cabecera lleva el logo (la C con el bucle)")
    ok(pg.visible("#cabecera .marca", "CrearIA Studio")
       and pg.visible("#cabecera .marca", "Automatización de contenido"),
       "y el nombre «CrearIA Studio · Automatización de contenido»")
    ok(pg.p.title() == "CrearIA Studio", f"el título de la pestaña ({pg.p.title()!r})")
    ok(pg.esperar(".pie-sistema", "© 2026 Agencia Redes Botánica", 10), "el pie con los derechos, en Crear")
    ok(pg.visible(".pie-sistema a", "Términos de uso") and pg.visible(".pie-sistema a", "Contacto"),
       "con Novedades, Guía, Términos de uso y Contacto")
    pg.p.locator(".pie-sistema a", has_text="Términos de uso").first.click()
    ok(pg.esperar(".ventana-texto", "Agencia Redes Botánica", 5)
       and pg.visible(".ventana-texto", "República del Perú")
       and pg.visible(".ventana-texto", "Última actualización: 19 de octubre de 2026"),
       "Términos abre los términos de uso (titular, ley peruana, fecha)")
    pg.p.keyboard.press("Escape")
    ok(pg.p.eval_on_selector(".pie-sistema a:has-text('Contacto')", "a => a.getAttribute('href')")
       == "mailto:agencia.redes.botanica@gmail.com", "Contacto es un mailto a la agencia")

    # LAS CUATRO PALETAS: cada una cambia una variable visible y se recuerda
    fondo = "() => getComputedStyle(document.body).backgroundColor"
    vistos = {}
    pg.js("conmutarConfig(true);")
    ok(pg.esperar("#cuerpo-config h3", "Aspecto", 10), "Configuración trae la elección de paleta")
    for paleta in ("aurora", "brasa", "dia", "nocturno"):
        pg.pulsar(f'.eleccion-paleta[data-paleta="{paleta}"]')
        vistos[paleta] = pg.p.evaluate("() => getComputedStyle(document.documentElement)"
                                       ".getPropertyValue('--bg').trim()")
    ok(len(set(vistos.values())) == 4, f"las cuatro paletas ponen un fondo distinto ({vistos})")
    ok(vistos["dia"] == "#f6f4ff" and vistos["nocturno"] == "#0a0913", "Día es la clara y Nocturno la de siempre")
    pg.pulsar('.eleccion-paleta[data-paleta="brasa"]')
    pg.js("conmutarConfig(false);")
    pg.p.reload()
    pg.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos", timeout=30000)
    ok(pg.p.evaluate("() => document.documentElement.dataset.paleta") == "brasa",
       "la paleta elegida se recuerda al recargar")
    pg.pulsar("#btn-tema")
    ok(pg.p.evaluate("() => document.documentElement.dataset.tema") == "claro",
       "el sol y la luna pasan a Día (el tema claro)")
    pg.pulsar("#btn-tema")
    ok(pg.p.evaluate("() => document.documentElement.dataset.paleta") == "brasa",
       "y vuelven a tu oscura (Brasa)")
    pg.js("aplicarPaleta('nocturno');")
    pg.captura("crearia_crear")

    # EL INICIO Y «ARMA TU PANEL»
    pg.js("localStorage.removeItem('inicio.panel');")
    pg.pulsar("#barra-modulos .boton-modulo", "Inicio")
    for clase, que in (("saludo", "el saludo"), ("cifras", "las cifras"), ("necesitan", "Te necesitan"),
                       ("semana", "la semana"), ("recientes", "los recientes"), ("marcha", "En marcha"),
                       ("mejor", "lo mejor de 7 días")):
        ok(pg.esperar(f".tarjeta-inicio.tarjeta-{clase}", segundos=10), f"el Inicio pinta {que}")
    ok(pg.esperar(".cifra-inicio", "Vídeos este mes", 10), "con «Vídeos este mes»")
    ok(pg.visible("#modulo .pie-sistema", "© 2026"), "y el pie también en los módulos")
    ok(pg.visible(".barra-modulos .gasto-menu", "Gasto del mes"), "el menú lateral trae el gasto del mes")
    ok(pg.visible(".barra-modulos .boton-modulo", "Configuración"), "y Configuración")
    for paleta in ("nocturno", "aurora", "brasa", "dia"):
        pg.js(f"aplicarPaleta('{paleta}');")
        pg.p.wait_for_timeout(300)
        pg.captura(f"crearia_inicio_{paleta}", entera=False)
    pg.js("aplicarPaleta('nocturno');")
    pg.pulsar(".chip-personalizar")
    ok(pg.esperar(".arma-tu-panel h2", "Arma tu panel", 5), "«✎ Personalizar panel» abre «Arma tu panel»")
    ok(pg.p.locator(".interruptor-tarjeta").count() == 12, "con las 12 tarjetas del catálogo")
    ok(pg.visible(".arma-tu-panel .chip-vista", "Mínima"), "y las cuatro vistas de partida")
    pg.pulsar('.tarjeta-inicio.editable[data-tarjeta="semana"] button.quitar-tarjeta')
    ok(not pg.visible('.tarjeta-inicio[data-tarjeta="semana"]'), "✕ quita «Esta semana»")
    pg.pulsar('.tarjeta-inicio.editable[data-tarjeta="necesitan"] button.tam-boton', "L")
    ok(pg.visible('.tarjeta-inicio.editable.tam-L[data-tarjeta="necesitan"]'), "S/M/L le cambia el tamaño")
    orden = lambda: pg.p.evaluate("() => [...document.querySelectorAll('.rejilla-inicio .tarjeta-inicio')].map(t => t.dataset.tarjeta)")
    antes = orden()
    pg.p.locator('.tarjeta-inicio.editable[data-tarjeta="recientes"] button[title="Subirla un puesto"]').click()
    pg.p.wait_for_timeout(500)
    despues = orden()
    ok(despues.index("recientes") == antes.index("recientes") - 1, f"↑ la sube un puesto ({despues[:5]})")
    pg.captura("crearia_personalizar")
    pg.pulsar(".aviso-editando button", "Listo")
    pg.p.wait_for_timeout(800)
    pg.p.reload()
    pg.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos", timeout=30000)
    pg.js("irAModulo('inicio');")
    ok(pg.esperar(".tarjeta-inicio.tarjeta-saludo", segundos=10), "tras recargar, el Inicio")
    ok(not pg.visible('.tarjeta-inicio[data-tarjeta="semana"]') and pg.visible('.tarjeta-inicio.tam-L[data-tarjeta="necesitan"]'),
       "se recuerda sin «Esta semana» y con «Te necesitan» grande")
    pg.pulsar(".chip-personalizar")
    pg.pulsar(".aviso-editando button", "Volver al original")
    pg.p.wait_for_timeout(1200)
    ok(pg.esperar('.tarjeta-inicio[data-tarjeta="semana"]', segundos=10), "«Volver al original» la devuelve")
    ok(pg.p.evaluate("() => localStorage.getItem('inicio.panel')") is None, "y borra lo guardado")

    # el panel, por usuario en el servidor
    api = datos["api"]
    r, d = api.put("/api/inicio/panel", {"usuario": "javier", "panel": {"tarjetas": [{"id": "saludo", "tam": "L"}],
                                                                       "tope_usd": 50}})
    ok(r.status_code == 200 and d["panel"]["tope_usd"] == 50, "PUT /api/inicio/panel guarda el de un usuario")
    _r, d = api.get("/api/inicio/panel?usuario=javier")
    ok(d["panel"]["tarjetas"] == [{"id": "saludo", "tam": "L"}], "y GET lo devuelve")
    r, _d = api.put("/api/inicio/panel", {"usuario": "javier", "panel": {"tarjetas": [{"id": "nada"}]}})
    ok(r.status_code == 400, "una tarjeta que no existe es un 400")
    api.put("/api/inicio/panel", {"usuario": "javier", "panel": None})
    _r, d = api.get("/api/salud")
    ok(d.get("version") == "3.1", f"la versión es la 3.1 ({d.get('version')})")
    _r, d = api.get("/api/sistema/novedades")
    ok(d.get("version") == "3.1" and "## V3.1" in d.get("texto", ""), "y Novedades empieza por la V3.1")
    _r, d = api.get("/api/inicio/resumen")
    ok(isinstance(d.get("gasto_mes_usd"), (int, float)) and d.get("videos", 0) >= 1 and d.get("recientes"),
       f"/api/inicio/resumen: gasto del mes, vídeos y recientes ({d.get('gasto_mes_usd')}, {d.get('videos')})")

    # EL «?»: el panel de Ayuda, en el apartado de la pantalla
    pg.pulsar("#btn-ayuda")
    ok(pg.esperar("#ayuda .ayuda-pantalla h3", "Inicio", 10), "el «?» abre la Ayuda en el apartado de Inicio")
    ok(pg.esperar("#ayuda .lista-guias button", segundos=10), "con la lista de las guías")
    ok(pg.visible("#ayuda button", "Guía de inicio") and pg.visible("#ayuda button", "Novedades"),
       "la guía de inicio y las novedades")
    ok(pg.p.evaluate("() => document.querySelector('#config').classList.contains('plegado')"),
       "y sin abrir Configuración")
    pg.p.locator("#ayuda .lista-guias button").first.click()
    ok(pg.esperar("#ventana-guia h2", segundos=5), "cada guía se abre")
    pg.p.keyboard.press("Escape")
    pg.p.keyboard.press("Escape")
    pg.p.wait_for_timeout(400)
    ok(not pg.visible("#ayuda"), "Escape la cierra")
    pg.js("irAModulo('automatizar');")
    pg.pulsar("#btn-ayuda")
    ok(pg.esperar("#ayuda .ayuda-pantalla h3", "Automatizar", 10), "en Automatizar, el apartado de Automatizar")
    pg.captura("crearia_ayuda", entera=False)
    pg.js("conmutarAyuda(false); entrarEnCrear();")
    pg.pulsar("#btn-ayuda")
    ok(pg.esperar("#ayuda .ayuda-pantalla", "Qué es una lámina", 10), "y en Crear, el de los estilos")
    pg.js("conmutarAyuda(false);")
    pg.sin_errores("el diseño CrearIA")
    pg.cerrar()

    # LA ENTRADA Y LA NAVEGACIÓN (decisión del dueño, 19-10-2026)
    pg = Pagina(navegador, datos, nombre="crearia entrada", entrada="inicio")
    ok(pg.esperar(".tarjeta-inicio.tarjeta-saludo", segundos=10)
       and pg.p.evaluate("() => MODULOS.actual") == "inicio", "al entrar en el Studio se abre el Inicio")
    pg.js(f"irAModulo('crear'); await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar(".salida-crear", "‹ Estado Play", 15), "un vídeo abierto trae arriba la salida a su proyecto")
    pg.pulsar(".salida-crear", "Estado Play")
    ok(pg.esperar("h2", "Estado Play", 10) and not pg.visible("h2", "Tus proyectos"),
       "que lleva a su proyecto")
    pg.pulsar(".salida-crear", "Tus proyectos")
    ok(pg.esperar("h2", "Tus proyectos", 10), "y desde ahí, a Tus proyectos")
    pg.js("PUB.seccion = 'resultados'; irAModulo('publicar');")
    ok(pg.esperar(".volver-modulo button", "Volver", 10), "Publicar → Resultados trae «‹ Volver»")
    pg.pulsar(".volver-modulo button", "Volver")
    ok(pg.p.evaluate("() => PUB.seccion") == "cola", "que lleva a la cola")
    pg.pulsar(".volver-modulo button", "Volver")
    ok(pg.p.evaluate("() => MODULOS.actual") == "inicio", "y desde la cola, al Inicio")
    pg.js("PAR.seccion = 'marca'; irAModulo('automatizar');")
    ok(pg.esperar(".volver-modulo button", "Volver", 10), "Automatizar → Marca del cliente trae «‹ Volver»")
    pg.js(f"irAModulo('crear'); await abrirVideoLight('{datos['video']}'); APP.light.video.vista = 'guion'; pintarLight();")
    pg.esperar(".cab-video", None, 15)
    url = pg.p.url
    salio = False
    for _ in range(14):
        try:
            pg.p.go_back(timeout=5000)
        except Exception:                                    # noqa: BLE001
            pass
        pg.p.wait_for_timeout(700)
        if not pg.p.url.startswith(datos["url"]):
            salio = True
            break
    ok(not salio, f"catorce «atrás» seguidos no sacan del Studio ({pg.p.url[:60]})")
    ok(pg.esperar("h2", "Tus proyectos", 5) or pg.esperar(".tarjeta-inicio.tarjeta-saludo", segundos=5),
       "y se queda en Tus proyectos o en el Inicio")
    ok(url.startswith(datos["url"]), "(la página es la del Studio)")
    pg.sin_errores("la entrada y el atrás")
    pg.cerrar()

    # en el móvil: cabe, y el Inicio y la Ayuda se ven
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="crearia móvil")
    pg.js("irAModulo('inicio');")
    ok(pg.esperar(".tarjeta-inicio.tarjeta-saludo", segundos=10), "en el móvil, el Inicio")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"cabe en 390 px ({ancho}px)")
    caja = pg.p.evaluate("() => { const b = document.querySelector('#barra-modulos'); return [b.scrollWidth, b.clientWidth]; }")
    ok(caja[0] <= caja[1] + 2, f"la barra de módulos cabe entera ({caja})")
    pg.captura("crearia_inicio_movil")
    pg.pulsar(".chip-personalizar")
    pg.p.wait_for_timeout(400)
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"«Arma tu panel» cabe en el móvil ({ancho}px)")
    pg.captura("crearia_personalizar_movil")
    pg.pulsar(".aviso-editando button", "Listo")
    pg.pulsar("#btn-ayuda")
    ok(pg.esperar("#ayuda .ayuda-pantalla h3", "Inicio", 10), "y la Ayuda")
    pg.captura("crearia_ayuda_movil", entera=False)
    pg.sin_errores("el diseño CrearIA en el móvil")
    pg.cerrar()



# ======================================================================
# TEXTOS CON EMOJIS (rama `textos-emojis`, 20-10-2026). Tramo propio al final.

def _igual_emojis(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


@escenario
def publicar_emojis(navegador, datos):
    """El nivel de emojis del proyecto (Ninguno · Sobrio · Normal · Vistoso,
    de fábrica Vistoso) y los emojis de la marca en «Cuentas y ajustes»; en la
    ficha, el aviso de un texto con menos emojis de los pedidos y «✨ Más
    emojis», que cambia el texto (sin tocar sus palabras) y lo guarda."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.put(f"/api/publicar/proyectos/{cid}", {"emojis": "vistoso", "emojis_marca": ""})
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok", "youtube"], "textos": {
        "tiktok": {"descripcion": "Fiesta en casa con consola\n\nReserva ya #consolas"},
        "youtube": {"titulo": "Alquiler de consolas en Lima", "descripcion": "Hola"}}})
    pg = Pagina(navegador, datos)

    # --- Cuentas y ajustes: el nivel y los de la marca
    pg.js("PUB.seccion = 'cuentas'; irAModulo('publicar');")
    tarjeta = f'.proyecto-publicar:has(input[data-perfil="{cid}"])'
    ok(pg.esperar(tarjeta, segundos=15), "la tarjeta del proyecto en Cuentas y ajustes")
    pg.p.locator(f"{tarjeta} .ajustes-fijos > summary").first.click()
    niveles = f"{tarjeta} .ajuste-emojis .niveles-emojis"
    ok(pg.esperar(niveles, segundos=5), "el selector «Emojis en los textos»")
    textos = pg.p.locator(f"{niveles} button").all_inner_texts()
    _igual_emojis(textos, ["Ninguno", "Sobrio", "Normal", "Vistoso"], "con sus cuatro niveles")
    ok(pg.visible(f"{niveles} button.elegido", "Vistoso"), "y Vistoso elegido de fábrica")
    pg.pulsar(f"{niveles} button", "Sobrio")
    pg.p.wait_for_timeout(1200)
    _r, proyectos = api.get("/api/publicar/proyectos")
    fila = next((x for x in proyectos.get("proyectos", []) if x["id"] == cid), {})
    _igual_emojis((fila.get("ajustes") or {}).get("emojis"), "sobrio", "pulsar «Sobrio» lo guarda")
    if not pg.visible(f"{tarjeta} .ajuste-emojis input[data-emojis-marca]"):
        pg.p.locator(f"{tarjeta} .ajustes-fijos > summary").first.click()
    ok(pg.visible(f"{niveles} button.elegido", "Sobrio"), "y se ve elegido tras repintar")
    pg.pulsar(f"{niveles} button", "Vistoso")
    pg.p.wait_for_timeout(1200)
    if not pg.visible(f"{tarjeta} .ajuste-emojis input[data-emojis-marca]"):
        pg.p.locator(f"{tarjeta} .ajustes-fijos > summary").first.click()
    campo = pg.p.locator(f"{tarjeta} .ajuste-emojis input[data-emojis-marca]")
    ok(campo.count() == 1, "el campo «Emojis de la marca»")
    campo.fill("🕹️ 🎉")
    campo.press("Tab")
    pg.p.wait_for_timeout(1200)
    _r, proyectos = api.get("/api/publicar/proyectos")
    fila = next((x for x in proyectos.get("proyectos", []) if x["id"] == cid), {})
    _igual_emojis(((fila.get("ajustes") or {}).get("emojis"), (fila.get("ajustes") or {}).get("emojis_marca")),
          ("vistoso", "🕹️ 🎉"), "el nivel vuelve a Vistoso y los de la marca se guardan")
    pg.captura("publicar_emojis_ajustes")

    # --- la ficha: el aviso y «✨ Más emojis»
    pg.js(f"abrirPublicarVideo('{pid}');")
    red = ".texto-red[data-red=tiktok]"
    ok(pg.esperar(f"{red} .aviso-emojis", "menos emojis de los pedidos", 15),
       "un texto sin emojis avisa: «va con menos emojis de los pedidos»")
    ok(pg.visible(".texto-red[data-red=youtube] .aviso-emojis", "Este título"),
       "y el título de YouTube sin emoji, también")
    ok(pg.visible(f'{red} button[data-emojis="tiktok-descripcion"]', "Más emojis"),
       "«✨ Más emojis» junto al texto")
    ok(pg.visible('.texto-red[data-red=youtube] button[data-emojis="youtube-titulo"]', "Más emojis"),
       "y junto al título")
    pg.pulsar(f'{red} button[data-emojis="tiktok-descripcion"]')
    hecho = False
    for _ in range(30):
        pg.p.wait_for_timeout(500)
        valor = pg.p.locator(f"{red} textarea").first.input_value()
        if valor != "Fiesta en casa con consola\n\nReserva ya #consolas":
            hecho = True
            break
    ok(hecho and "🕹️" in valor and "Fiesta en casa con consola" in valor and "#consolas" in valor,
       f"«✨ Más emojis» cambia el texto, con los de la marca y sin tocar sus palabras ({valor!r})")
    ok(pg.esperar(".guardado-publicar .pastilla.ok", "Guardado", 10), "y se guarda: «✓ Guardado»")
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    _igual_emojis(ficha["textos"]["tiktok"]["descripcion"], valor, "en el servidor está el texto con emojis")
    ok(not pg.visible(f"{red} .aviso-emojis"), "y el aviso se va")
    pg.pulsar('.texto-red[data-red=youtube] button[data-emojis="youtube-titulo"]')
    pg.p.wait_for_timeout(2500)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    titulo = ficha["textos"]["youtube"]["titulo"]
    ok(titulo.startswith("Alquiler de consolas en Lima") and titulo != "Alquiler de consolas en Lima",
       f"el título también, con el emoji al final ({titulo!r})")
    # con Ninguno no se ofrece
    api.put(f"/api/publicar/proyectos/{cid}", {"emojis": "ninguno"})
    pg.js(f"abrirPublicarVideo('{pid}');")
    pg.p.wait_for_timeout(1500)
    ok(pg.esperar(f"{red} textarea", segundos=10) and not pg.visible(f"{red} button[data-emojis]")
       and not pg.visible(f"{red} .aviso-emojis"), "con «Ninguno» ni el botón ni el aviso")
    api.put(f"/api/publicar/proyectos/{cid}", {"emojis": "vistoso", "emojis_marca": ""})
    pg.captura("publicar_emojis_ficha")
    pg.sin_errores("los emojis de Publicar")


# ======================================================================
# IMÁGENES: DESCARGAR Y LEER LO QUE DICE (rama `imagenes-texto`, 20-10-2026).
# Tramo propio y al final, como los demás.

_TEXTO_ESPERADO_JS = ("() => { const e = escenaPrevia(); return sinMarcasTts(legible(e.narracion))"
                      ".replace(/\\s+/g, ' ').trim(); }")
_TEXTO_VISTO_JS = ("() => { const c = document.querySelector('.texto-del-plano'); "
                   "return c ? c.innerText.replace(/\\s+/g, ' ').trim() : null; }")


@escenario
def descargar_y_leer_lo_que_dice(navegador, datos):
    """En la diapositiva de Imágenes: «⬇ Descargar» baja el PNG original del
    plano con un nombre útil, «⬇ Descargar todas» apunta al .zip, y el cuadro
    enseña lo que dice la voz en ESE plano, cambia al pasar de plano, marca el
    tramo que suena con «Oírla» y se oculta (y se recuerda) sin escribir nada
    en el vídeo."""
    from nucleo.proyecto import identificador  # noqa: PLC0415
    pid = datos["video"]
    api = datos["api"]
    pg = Pagina(navegador, datos, nombre="descargar y leer")
    pg.js("try { localStorage.removeItem('previa.texto_del_plano'); } catch (_) {} "
          "if (typeof TEXTO_DEL_PLANO !== 'undefined') TEXTO_DEL_PLANO.oculto = null;")
    api.libre(pid)
    estado_json = os.path.join(datos["proyectos"], pid, "estado.json")
    with open(estado_json, "rb") as fh:
        estado_antes = fh.read()
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".plano-texto-y-descarga", segundos=20), "debajo de la imagen salen las descargas y el texto")
    # a un plano que tenga imagen y voz
    total = pg.p.evaluate("() => (PREVIA.ficha.escenas || []).length")
    for _vuelta in range(total):
        if pg.p.evaluate("() => !!escenaPrevia().imagen") and pg.p.evaluate(_TEXTO_ESPERADO_JS):
            break
        pg.js("irAEscenaPrevia(1); pararPrevia();")
    sid = pg.p.evaluate("() => escenaPrevia().id")
    nombre = pg.p.evaluate("() => videoAbierto().nombre || videoAbierto().pid")
    esperado = f"{identificador(nombre)[:60]}_{sid}.png"
    enlace = pg.p.locator(".plano-texto-cab a", has_text="Descargar").filter(has_not_text="todas").first
    ok(enlace.count() == 1 and enlace.is_visible(), f"se ve «⬇ Descargar» en el plano {sid}")
    href = enlace.get_attribute("href") or ""
    ok(re.search(rf"/a/{re.escape(pid)}/pasos/assets/v\d+/escenas/{sid}\.png$", href) is not None,
       f"y apunta al PNG original de la versión activa, sin miniatura ({href})")
    ok(enlace.get_attribute("download") == esperado,
       f"con un nombre útil: {enlace.get_attribute('download')!r} (se esperaba {esperado!r})")
    try:
        with pg.p.expect_download(timeout=10000) as bajada:
            enlace.click()
        ok(bajada.value.suggested_filename == esperado,
           f"pulsarlo baja el fichero con ese nombre ({bajada.value.suggested_filename})")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"pulsar «⬇ Descargar» baja el PNG: se cortó ({type(fallo).__name__}: {str(fallo)[:120]})")
    todas = pg.p.locator(".plano-texto-cab a", has_text="Descargar todas").first
    ok(todas.count() == 1 and todas.is_visible(), "y «⬇ Descargar todas»")
    ok((todas.get_attribute("href") or "").endswith(f"/api/proyectos/{pid}/imagenes/zip"),
       f"que apunta al .zip ({todas.get_attribute('href')})")
    ok(todas.get_attribute("download") == f"{identificador(nombre)[:60]}_imagenes.zip",
       f"con el nombre del vídeo ({todas.get_attribute('download')})")
    estado_zip = pg.p.evaluate("async () => { const r = await fetch(document.querySelector("
                               "'.plano-texto-cab a[href$=\"/imagenes/zip\"]').href); "
                               "return [r.status, r.headers.get('content-type')]; }")
    ok(estado_zip == [200, "application/zip"], f"y el .zip se sirve ({estado_zip})")

    # EL CUADRO: el texto del plano que se ve, y cambia con el plano
    visto, texto = pg.p.evaluate(_TEXTO_VISTO_JS), pg.p.evaluate(_TEXTO_ESPERADO_JS)
    ok(bool(texto) and visto == texto, f"el cuadro dice lo que dice la voz en {sid}: {visto!r} (guion: {texto!r})")
    ok(pg.p.evaluate("() => document.querySelector('.texto-del-plano').dataset.plano") == sid,
       "y es el del plano que se ve")
    pg.captura("imagenes_texto_escritorio", entera=False)
    otro = None
    for _vuelta in range(total):
        if pg.p.evaluate("() => PREVIA.i >= PREVIA.ficha.escenas.length - 1"):
            break
        pg.js("irAEscenaPrevia(1); pararPrevia();")
        pg.p.wait_for_timeout(300)
        nuevo = pg.p.evaluate(_TEXTO_ESPERADO_JS)
        if nuevo and nuevo != texto:
            otro = nuevo
            break
    sid2 = pg.p.evaluate("() => escenaPrevia().id")
    ok(otro is not None and pg.p.evaluate(_TEXTO_VISTO_JS) == otro,
       f"al pasar de plano ({sid} → {sid2}) el cuadro cambia a su texto: {pg.p.evaluate(_TEXTO_VISTO_JS)!r}")
    ok((pg.p.locator(".plano-texto-cab a", has_text="Descargar").filter(has_not_text="todas")
        .first.get_attribute("download") or "").endswith(f"_{sid2}.png"),
       "y «⬇ Descargar» es ya la imagen de ese plano")

    # «OÍRLA» MARCA EL TRAMO QUE SUENA
    pg.pulsar(".previa-mandos button", "Oírla")
    marcado = False
    for _vuelta in range(30):
        if pg.p.locator(".texto-del-plano .tramo-del-plano.sonando").count():
            marcado = True
            break
        pg.p.wait_for_timeout(250)
    ok(marcado, "mientras suena «Oírla», el tramo que se oye va resaltado")
    pg.js("pararPrevia(); repintarVideo();")
    ok(pg.p.locator(".texto-del-plano .tramo-del-plano.sonando").count() == 0, "y al parar se apaga")

    # OCULTAR Y RECORDARLO
    pg.pulsar(".plano-texto-cab button", "Ocultar el texto")
    ok(not pg.visible(".texto-del-plano") and pg.visible(".plano-texto-cab button", "Ver el texto"),
       "«Ocultar el texto» lo quita y deja «Ver el texto»")
    ok(pg.visible(".plano-texto-cab a", "Descargar"), "y las descargas siguen a mano")
    pg.p.reload()
    pg.p.wait_for_function("() => typeof APP !== 'undefined' && APP.light && APP.light.datos", timeout=30000)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
    pg.esperar(".plano-texto-y-descarga", segundos=20)
    ok(not pg.visible(".texto-del-plano") and pg.visible(".plano-texto-cab button", "Ver el texto"),
       "al recargar se recuerda oculto")
    pg.pulsar(".plano-texto-cab button", "Ver el texto")
    ok(pg.esperar(".texto-del-plano", segundos=5), "y «Ver el texto» lo devuelve")
    api.libre(pid)
    with open(estado_json, "rb") as fh:
        ok(fh.read() == estado_antes, "mirar, descargar y ocultar no escriben nada en el vídeo (regla 1)")
    pg.sin_errores("descargar y leer lo que dice")
    pg.cerrar()

    # EN EL MÓVIL: cabe, y se lee
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="descargar y leer móvil")
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'previa'; pintarLight();")
    ok(pg.esperar(".texto-del-plano", segundos=20), "en el móvil se ve el cuadro del texto")
    ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(ancho <= 2, f"y cabe en 390 px ({ancho}px)")
    pg.js("document.querySelector('.plano-texto-y-descarga').scrollIntoView({block: 'center'});")
    pg.captura("imagenes_texto_movil", entera=False)
    pg.sin_errores("descargar y leer en el móvil")
    pg.cerrar()


# espacio-fijo (20-10-2026): un guion de la Parrilla con ESPACIO FIJO llena el
# campo «El espacio fijo» de «Un vídeo nuevo», y eso es lo que se manda al crear.
@escenario
def parrilla_con_espacio_fijo(navegador, datos):
    """La Parrilla con un guion con ESPACIO FIJO → «Pasar al Encargo» → el
    campo aparece relleno en el vídeo nuevo → `opcionesParaCrear().espacio_fijo`
    correcto. Y a mano: sin descripción no viaja."""
    api = datos["api"]
    cid = datos["cliente"]
    guion = ("EF01 — Pan del día\nCliente / proyecto: Panadería\nUso: adaptar\nRed: Reels\n"
             "Formato: vertical\nDuración: 30 s\nObjetivo: que pidan\nCTA: Escríbenos\n"
             "Tono: cercano\n\n"
             "ESPACIO FIJO\n- Sitio: Panadería Rosa\n"
             "- Descripción: a small bakery with wooden shelves full of bread\n"
             "- Luz: morning, warm window light\n"
             "- Secundarios: Fachada: a shop front with a pink awning; Almacén\n\n"
             "ESCENA 1\nVisual: el mostrador\nVoz: «Recién hecho.»\n\n"
             "PARA EL ENCARGO\n- Material: Recién hecho, cada mañana.\n"
             "- Indicaciones: cercano\n- Llamadas a la acción: Escríbenos\n"
             "- Duración: 30 s · Formato: vertical\n\nAVISOS\n- ninguno")
    r, hecho = api.post(f"/api/parrilla/proyectos/{cid}/guiones",
                        {"texto": guion, "nombre": "Espacio fijo"})
    ok(r.status_code == 201 and (hecho or {}).get("guiones"),
       f"el guion con ESPACIO FIJO se guarda ({r.status_code})")
    pg = Pagina(navegador, datos, nombre="espacio fijo")
    pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
    pg.js(f"elegirProyectoParrilla('{cid}');")
    pg.p.wait_for_timeout(800)
    pg.pulsar(".fila-guion .titulo-guion", "EF01")
    ok(pg.esperar(".ficha-parrilla h3", "EF01"), "su ficha")
    pg.p.locator(".pasar-encargo select").first.select_option(datos["preset"])
    pg.pulsar(".pasar-encargo button", "Pasar al Encargo")
    fin = time.time() + 10
    while time.time() < fin and not pg.p.evaluate(
            "() => MODULOS.actual === 'crear' && APP.light.vista === 'elegido'"):
        pg.p.wait_for_timeout(300)
    ok(pg.esperar(".bloque-light h3", "El espacio fijo", 10), "«Un vídeo nuevo» trae el bloque «El espacio fijo»")
    valores = pg.p.evaluate("""() => {
        const caja = document.querySelector('.espacio-fijo');
        if (!caja) return null;
        const ent = caja.querySelectorAll('input');
        return {sitio: ent[0] ? ent[0].value : '', luz: ent[1] ? ent[1].value : '',
                desc: (caja.querySelector('[data-foco=espacio-fijo-descripcion]') || {}).value || '',
                sec: (caja.querySelector('[data-foco=espacio-fijo-secundarios]') || {}).value || ''};
    }""")
    ok(valores == {"sitio": "Panadería Rosa", "luz": "morning, warm window light",
                   "desc": "a small bakery with wooden shelves full of bread",
                   "sec": "Fachada: a shop front with a pink awning\nAlmacén"},
       f"relleno con lo que dice el guion: {valores}")
    enviado = pg.p.evaluate("() => opcionesParaCrear(APP.light.video.encargo).espacio_fijo || null")
    ok(enviado == {"sitio": "Panadería Rosa",
                   "descripcion": "a small bakery with wooden shelves full of bread",
                   "luz": "morning, warm window light",
                   "secundarios": [{"nombre": "Fachada", "descripcion": "a shop front with a pink awning"},
                                   {"nombre": "Almacén", "descripcion": ""}]},
       f"y es lo que se manda al crear (opciones.espacio_fijo): {enviado}")
    pg.captura("espacio_fijo_encargo")

    # a mano: cambiar la luz se manda; sin descripción, no viaja nada
    pg.p.locator(".espacio-fijo input").nth(1).fill("night, neon sign")
    ok(pg.p.evaluate("() => opcionesParaCrear(APP.light.video.encargo).espacio_fijo.luz")
       == "night, neon sign", "lo escrito a mano es lo que viaja")
    pg.p.locator("[data-foco=espacio-fijo-descripcion]").fill("")
    ok(pg.p.evaluate("() => !('espacio_fijo' in opcionesParaCrear(APP.light.video.encargo))"),
       "sin descripción no se manda espacio fijo (regla 1)")
    pg.sin_errores("el espacio fijo")
    pg.cerrar()


def _huellas_de_planos(datos, pid):
    """{plano: sha1 de su PNG} en la versión activa de assets."""
    import hashlib as _hl                                    # noqa: PLC0415
    activa = _version_de(datos, "assets", "")
    version = activa.get("activa") or activa.get("n") or activa.get("version")
    carpeta = os.path.join(datos["proyectos"], pid, "pasos", "assets", f"v{version}", "escenas")
    salida = {}
    for nombre in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
        if nombre.endswith(".png"):
            with open(os.path.join(carpeta, nombre), "rb") as fh:
                salida[nombre[:-4]] = _hl.sha1(fh.read()).hexdigest()
    return salida


# espacio-fijo (20-10-2026, ampliación): el espacio fijo aplicado a un vídeo
# YA HECHO, como corrección. Aplicar no dibuja ni paga; después se elige qué
# planos rehacer y solo se rehacen esos.
@escenario
def espacio_fijo_en_un_video_hecho(navegador, datos):
    """Encargo de un vídeo hecho → «El espacio fijo» con su imagen → «Aplicar»
    no lanza nada ni deja imágenes por pagar → la lista de planos que cambian →
    «Solo los marcados» rehace SOLO ese plano."""
    api = datos["api"]
    pid = datos["video"]
    pg = Pagina(navegador, datos, nombre="espacio fijo del vídeo")
    pg.sin_trabajo(300)
    antes = _huellas_de_planos(datos, pid)
    ok(len(antes) >= 2, f"el vídeo de prueba tiene sus imágenes ({len(antes)})")
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'encargo_video'; pintarLight();")
    ok(pg.esperar(".bloque-light h3", "El espacio fijo", 15), "el Encargo del vídeo trae «El espacio fijo»")
    ok(pg.esperar(".espacio-fijo-del-video button", "Aplicar el espacio fijo", 15), "con «Aplicar el espacio fijo»")
    pg.p.locator(".espacio-fijo-del-video input").nth(0).fill("Salón de casa")
    pg.p.locator("[data-foco=video-espacio-descripcion]").fill(
        "a cosy living room with a green sofa, a wooden table and a big window")
    foto = os.path.join(datos["base"], "salon.png")
    _png(foto, (90, 140, 70))
    pg.p.set_input_files(".espacio-fijo-del-video .oculto-espacio-fijo", foto)
    ok(pg.esperar(".espacio-fijo-del-video .miniatura-espacio-fijo", segundos=10),
       "la imagen elegida se ve antes de aplicar")
    pg.pulsar(".espacio-fijo-del-video button", "Aplicar el espacio fijo")
    ok(pg.esperar(".cambios-espacio-fijo", segundos=20), "aplicado, dice qué cambia")
    _r, vivos = api.get(f"/api/trabajos?proyecto={pid}&activos=1")
    lista = vivos if isinstance(vivos, list) else (vivos.get("trabajos") or [])
    ok(not lista, f"aplicar no lanza ningún trabajo ({len(lista)})")
    _r, plan = api.get(f"/api/proyectos/{pid}/generar?tanda=video")
    ok((plan.get("coste") or {}).get("imagenes_por_generar") == 0,
       f"y no deja ninguna imagen por pagar: {(plan.get('coste') or {}).get('imagenes_por_generar')}")
    ok(_huellas_de_planos(datos, pid) == antes, "ni ha tocado ninguna imagen")
    _r, ef = api.get(f"/api/proyectos/{pid}/espacio_fijo")
    cambios = (ef or {}).get("cambios") or {}
    planos = [x["id"] for x in cambios.get("planos") or []]
    ok(len(planos) >= 2 and (ef.get("espacio_fijo") or {}).get("imagen"),
       f"el servidor guarda el espacio con su imagen y ofrece {len(planos)} planos")
    ok(pg.visible(".cambios-espacio-fijo button", f"Rehacer los {len(planos)}"),
       "«Rehacer los N» con su precio")
    pg.captura("espacio_fijo_video")
    # deja marcado SOLO el primero
    casillas = pg.p.locator(".lista-espacio-fijo input[type=checkbox]")
    for i in range(1, casillas.count()):
        casillas.nth(i).uncheck()
    pg.p.wait_for_timeout(400)
    ok(pg.visible(".cambios-espacio-fijo button", "Solo los marcados (1)"), "«Solo los marcados (1)»")
    pg.pulsar(".cambios-espacio-fijo button", "Solo los marcados (1)")
    pg.p.wait_for_timeout(1500)
    _r, todos = api.get(f"/api/trabajos?proyecto={pid}")
    trabajos = todos if isinstance(todos, list) else (todos.get("trabajos") or [])
    suyo = next((t for t in trabajos if t.get("nombre") == "espacio_fijo"), {})
    ok(suyo.get("unidades") and [u for u in suyo["unidades"] if u.split(":")[-1] == planos[0]]
       and all(u.split(":")[-1] == planos[0] or "sigue" in u or u.split(":")[-1] not in planos
               for u in suyo["unidades"]),
       f"rehace SOLO el marcado (y su segunda mitad si la tiene): {suyo.get('unidades')}")
    pg.sin_trabajo(300)
    despues = _huellas_de_planos(datos, pid)
    cambiados = sorted(k for k in antes if despues.get(k) != antes[k])
    ok(planos[0] in cambiados and not [k for k in cambiados if k in planos[1:]],
       f"solo cambia la imagen pedida: {cambiados}")
    activa = _version_de(datos, "assets", "")
    version = activa.get("activa") or activa.get("n") or activa.get("version")
    ficha = os.path.join(datos["proyectos"], pid, "pasos", "assets", f"v{version}", "escenas",
                         f"{planos[0]}.json")
    try:
        with open(ficha, encoding="utf-8") as fh:
            papeles = [r.get("papel") for r in json.load(fh).get("referencias") or []]
    except (OSError, ValueError):
        papeles = []
    ok("espacio" in papeles, f"y lleva adjunta la imagen del sitio: {papeles}")
    pg.sin_errores("el espacio fijo de un vídeo hecho")
    pg.cerrar()


# ======================================================================
# PUBLICAR: ARREGLOS DEL 20 DE OCTUBRE (rama `publicar-20oct`). Tramo propio
# y al final, como los demás. Lo que el dueño vio en el servidor: la ficha no
# se cerraba al programar, lo programado que ya salió seguía «programado» y el
# calendario cambiaba con los filtros. Y el Short frente al vídeo normal.

def _sim_uploadpost(datos):
    return os.path.join(datos["proyectos"], "_sistema", "publicar", "uploadpost_simulado.json")


@escenario
def publicar_arreglos_del_20_10(navegador, datos):
    """(3) Programar o dejar esperando el OK cierra la ficha y vuelve a la cola
    con «Programado para … ✓»; guardar textos a secas no la cierra. (4) Lo
    programado cuya hora pasó se pregunta solo y pasa a publicado; si Upload-
    Post no da su estado, «debería haber salido a las …» con «Comprobar».
    (5) El calendario enseña todo aunque haya filtros. (2) YouTube dice si
    sale como Short o como vídeo normal."""
    import datetime as _dt                                   # noqa: PLC0415
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok", "instagram", "youtube", "facebook"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok", "youtube"], "textos": {
        "tiktok": {"descripcion": "Fiesta del 20 de octubre"},
        "youtube": {"titulo": "Consolas para tu fiesta", "descripcion": "Fiesta del 20 de octubre"}}})
    ruta_ficha = os.path.join(datos["proyectos"], "_sistema", "publicar", "videos", f"{pid}.json")

    def parte(nombre, fn):
        try:
            fn()
        except Exception as fallo:                           # noqa: BLE001
            traceback.print_exc()
            ok(False, f"{nombre} se cortó: {type(fallo).__name__}: {str(fallo)[:120]}")

    pg = Pagina(navegador, datos, nombre="publicar 20-10")
    pg.js(f"await abrirVideoLight('{pid}');")
    ok(_montar_desde_video(pg), "se parte de un vídeo montado")

    def parte_short():
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".ficha-publicar .formato-youtube .tipo-youtube", segundos=15),
           "(2) con YouTube marcado, la ficha dice cómo sale en YouTube")
        _r, f = api.get(f"/api/publicar/videos/{pid}")
        tipo = ((f.get("encaje") or {}).get("youtube") or {}).get("tipo")
        ok(pg.visible(".formato-youtube .tipo-youtube", "Short" if tipo == "Short" else "Vídeo normal"),
           f"(2) «YouTube · {tipo}», lo mismo que el servidor")
        if f.get("formato") == "vertical":
            ok(pg.visible(".formato-youtube select"), "(2) en un vertical se puede elegir Short o vídeo normal")
            pg.p.locator(".formato-youtube select").select_option("video")
            pg.p.wait_for_timeout(1500)
            _r, f = api.get(f"/api/publicar/videos/{pid}")
            ok(f.get("youtube_formato") == "video", "(2) y elegirlo se guarda")
            pg.p.locator(".formato-youtube select").select_option("auto")
            pg.p.wait_for_timeout(1200)
        else:
            ok(not pg.visible(".formato-youtube select"), "(2) en un horizontal no hay nada que elegir")
        pg.captura("publicar_20oct_formato_youtube")

    def parte_cerrar():
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".ficha-publicar .nombre-ficha", segundos=15), "(3) la ficha abierta")
        # guardar textos a secas NO cierra
        caja = pg.p.locator(".texto-red[data-red=tiktok] textarea").first
        caja.fill("Fiesta del 20 de octubre, escrita a mano")
        pg.p.locator(".ficha-publicar h3").first.click()
        ok(pg.esperar(".guardado-publicar .pastilla.ok", "Guardado", 10), "(3) el texto se guarda solo")
        ok(pg.visible(".ficha-publicar .nombre-ficha"), "(3) y guardar a secas deja la ficha abierta")
        # programar: se cierra y vuelve a la cola con el aviso
        pg.js("PUB.modoEnvio = 'programar'; PUB.cuandoEnvio = PUB.ficha.hora_sugerida; pintarModulo();")
        pg.pulsar(".cuando-publicar button", "Programar")
        ok(pg.esperar(".cola-publicar .aviso-tras-envio", "Programado para", 20),
           "(3) al programar vuelve a la cola con «Programado para … ✓»")
        ok(not pg.visible(".ficha-publicar"), "(3) y la ficha ya no se ve")
        ok(pg.p.evaluate("() => PUB.seccion") == "cola", "(3) estamos en «Cola y calendario»")
        _r, f = api.get(f"/api/publicar/videos/{pid}")
        ok((f["textos"].get("tiktok") or {}).get("descripcion") == "Fiesta del 20 de octubre, escrita a mano",
           "(3) y no se perdió lo escrito")
        pg.captura("publicar_20oct_vuelve_a_la_cola")
        pg.pulsar(".aviso-tras-envio button", "Volver a la ficha")
        ok(pg.esperar(".ficha-publicar .nombre-ficha", segundos=15), "(3) «Volver a la ficha» la abre otra vez")
        # «Dejar esperando mi OK» también la cierra (en Instagram, que no se ha mandado)
        api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram"], "textos": {
            "instagram": {"descripcion": "Reel del 20 de octubre"}}})
        pg.js("await cargarPublicar(true);")
        pg.pulsar(".cuando-publicar button", "Dejar esperando mi OK")
        ok(pg.esperar(".cola-publicar .aviso-tras-envio", "esperando tu OK", 20),
           "(3) «Dejar esperando mi OK» también vuelve a la cola, con su aviso")
        # lo programado arriba termina de subir (pasa de «enviando» a «programado»)
        fin = time.time() + 30
        while time.time() < fin:
            with open(ruta_ficha, encoding="utf-8") as fh:
                if not any(e.get("estado") == "enviando" for e in json.load(fh)["envios"]):
                    break
            pg.p.wait_for_timeout(1000)

    def parte_programado_vencido():
        # un envío programado para hace tres horas, que Upload-Post ya publicó
        hace = (_dt.datetime.now(_dt.timezone(_dt.timedelta(hours=-5))).replace(tzinfo=None)
                - _dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
        with open(ruta_ficha, encoding="utf-8") as fh:
            guardada = json.load(fh)
        programados = [e for e in guardada["envios"] if e.get("estado") == "programado"]
        ok(programados, "(4) hay envíos programados (de la parte de arriba)")
        lotes = {e["lote"] for e in programados}
        for e in programados:
            e["cuando"] = hace
        # y uno que Upload-Post no conoce: debería haber salido y nadie lo sabe
        guardada["envios"].append({"id": "fantasma2010", "red": "facebook", "lote": "fa20fa20fa20fa20",
                                   "estado": "programado", "modo": "programado", "job_id": "no_existe",
                                   "cuando": hace, "creado": hace, "mp4_huella": ""})
        with open(ruta_ficha, "w", encoding="utf-8") as fh:
            json.dump(guardada, fh, ensure_ascii=False)
        with open(_sim_uploadpost(datos), encoding="utf-8") as fh:
            sim = json.load(fh)
        for lote in lotes:
            if lote in sim["trabajos"]:
                sim["trabajos"][lote]["cuando_utc"] = (_dt.datetime.now(_dt.timezone.utc)
                                                       - _dt.timedelta(hours=3)).isoformat()
        with open(_sim_uploadpost(datos), "w", encoding="utf-8") as fh:
            json.dump(sim, fh)
        pg.js("PUB.desde = ''; PUB.vistaCal = 'semana'; irASeccionPublicar('cola');")
        ok(pg.esperar(".cola-publicar .fila-envio .debio-salir", "debería haber salido a las", 15),
           "(4) lo que ya debió salir lo dice: «debería haber salido a las …»")
        ok(pg.visible(".cola-publicar .fila-envio button", "Comprobar"), "(4) con su «Comprobar»")
        pg.captura("publicar_20oct_debio_salir")
        antes = len(pg.avisos())
        boton = '.cola-publicar .fila-envio[data-envio="fantasma2010"] button'
        if pg.visible(boton, "Comprobar"):
            pg.pulsar(boton, "Comprobar")
            pg.p.wait_for_timeout(2500)
        ok(len(pg.avisos()) > antes, f"(4) «Comprobar» dice cómo quedó: {pg.avisos()[antes:]}")
        # sin pulsar nada: el reloj de la cola le pregunta a Upload-Post y cambia
        fin = time.time() + 60
        publicados = False
        while time.time() < fin and not publicados:
            pg.p.wait_for_timeout(2000)
            with open(ruta_ficha, encoding="utf-8") as fh:
                ahora = json.load(fh)["envios"]
            publicados = all(e.get("estado") == "publicado" for e in ahora if e.get("lote") in lotes)
        ok(publicados, "(4) pasada su hora, la pantalla pregunta sola y lo programado pasa a «publicado»")
        ok(pg.esperar(".calendario-publicar .envio-dia", segundos=10), "(4) y el calendario lo enseña")

    def parte_calendario():
        pg.js("PUB.desde = ''; PUB.vistaCal = 'semana'; irASeccionPublicar('cola');")
        ok(pg.esperar(".calendario-publicar .envio-dia", segundos=15), "(5) el calendario con lo de la semana")
        cuantos = pg.p.locator(".calendario-publicar .envio-dia").count()
        pg.js("cambiarFiltroCola('texto', 'zzz-ningun-video-se-llama-asi');")
        pg.p.wait_for_timeout(800)
        ok(pg.visible(".cola-publicar .meta", "Ningún vídeo cumple estos filtros"), "(5) la lista sí se filtra")
        igual_n = pg.p.locator(".calendario-publicar .envio-dia").count()
        ok(igual_n == cuantos and cuantos > 0,
           f"(5) y el calendario NO: sigue enseñando todo ({igual_n} de {cuantos})")
        ok(pg.visible(".cola-publicar .nota-filtros-cola", "el calendario enseña siempre todo"),
           "(5) y se dice que los filtros son de la lista")
        proyecto = pg.p.locator('.filtros-cola select[data-filtro="proyecto"] option').all()
        if len(proyecto) > 1:
            pg.js("cambiarFiltroCola('texto', '');")
            pg.p.locator('.filtros-cola select[data-filtro="proyecto"]').select_option(index=len(proyecto) - 1)
            pg.p.wait_for_timeout(800)
            ok(pg.p.locator(".calendario-publicar .envio-dia").count() == cuantos,
               "(5) con un proyecto elegido, el calendario tampoco cambia")
        pg.captura("publicar_20oct_calendario_con_filtros")
        pg.js("PUB.filtros = Object.assign({}, FILTROS_COLA_DEFECTO); cambiarFiltroCola('texto', '');")

    parte("el formato de YouTube", parte_short)
    parte("cerrar la ficha", parte_cerrar)
    parte("lo programado que ya salió", parte_programado_vencido)
    parte("el calendario y los filtros", parte_calendario)
    pg.sin_errores("los arreglos de Publicar del 20-10")
    pg.cerrar()



@escenario
def publicar_seo_real(navegador, datos):
    """Rama seo-real (20-10): la nota SEO en tres partes (Relevancia, Demanda,
    Tu historial) con la forma aparte, «Investigar búsquedas» con su tabla y
    «Usar», la palabra del proyecto que el vídeo no trata fuera, y la casilla
    de la clave de YouTube en Configuración. En el móvil, sin salirse."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    # una palabra del proyecto que este vídeo NO trata: no tiene que salir
    api.put(f"/api/publicar/proyectos/{cid}", {"palabra_clave": "clases de guitarra eléctrica"})
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram"], "palabra_clave": "", "textos": {
        "instagram": {"descripcion": "Un reel para el SEO de verdad", "cta": "Escríbenos",
                      "hashtags": ["lima", "fiesta", "consolas"]}}})
    pg = Pagina(navegador, datos)
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(pg.esperar(".seo-video .busquedas-seo", "Búsquedas reales", 15), "la ficha tiene «Búsquedas reales»")
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    if ficha["seo"].get("proyecto_fuera"):
        ok(pg.visible(".seo-video .meta", "no se usa aquí"),
           "la palabra del proyecto que el vídeo no trata se dice que no se usa")
    ok(ficha["seo"]["palabra"] != "clases de guitarra eléctrica" or not ficha["seo"].get("proyecto_fuera"),
       "y no es la palabra del vídeo")
    pg.js("PUB.notaAbierta = {instagram: true}; pintarModulo();")
    nota = ".texto-red[data-red=instagram] .nota-seo"
    ok(pg.esperar(f"{nota} .parte-seo b", "Relevancia", 5), "la nota trae la parte de Relevancia")
    ok(pg.visible(f"{nota} .parte-seo b", "Demanda") and pg.visible(f"{nota} .parte-seo b", "Tu historial"),
       "y la de Demanda y Tu historial")
    ok(pg.visible(f"{nota} .parte-seo .meta", "Investigar búsquedas"), "sin investigar, dice cómo medir la demanda")
    ok(pg.visible(f"{nota} .titulo-forma-seo", "no cuentan"), "los detalles de forma, aparte y sin contar")
    pg.pulsar('.busquedas-seo button[data-accion="investigar-busquedas"]')
    ok(pg.esperar(".tabla-busquedas tbody tr", segundos=20), "«Investigar búsquedas»: la tabla de frases")
    ok(pg.visible(".tabla-busquedas th", "Demanda"), "con su demanda, competencia, historial y total")
    pg.pulsar(".tabla-busquedas tbody tr button", "Usar")
    pg.p.wait_for_timeout(1500)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    ok(bool(ficha["seo"]["palabra_propia"]), f"«Usar» la deja como palabra del vídeo: {ficha['seo']['palabra_propia']!r}")
    ok(pg.esperar(".tabla-busquedas .pastilla", "en uso", 8), "y la tabla la marca «en uso»")
    pg.js("PUB.notaAbierta = {instagram: true}; pintarModulo();")
    pg.p.wait_for_timeout(500)
    ok(not pg.visible(f"{nota} .parte-seo .meta", "sin investigar"), "la nota ya tiene la demanda investigada")
    pg.captura("publicar_seo_real")
    pg.sin_errores("el SEO de verdad")
    pg.cerrar()
    # la clave de YouTube en Configuración
    pg = Pagina(navegador, datos)
    pg.js("conmutarConfig(true);")
    ok(pg.esperar("#cuerpo-config h3", "YouTube (búsquedas SEO)", 10),
       "Configuración tiene la casilla de la clave de YouTube")
    ok(pg.visible("#cuerpo-config .pista", "YouTube Data API v3"), "y dice qué API activar")
    pg.sin_errores("la clave de YouTube en Configuración")
    pg.cerrar()
    for tema in ("oscuro", "claro"):
        pg = Pagina(navegador, datos, ancho=390, alto=844, nombre=f"seo real móvil {tema}")
        pg.js(f"document.documentElement.dataset.tema = '{tema}'; abrirPublicarVideo('{pid}');")
        pg.p.wait_for_timeout(2500)
        pg.js("PUB.notaAbierta = {instagram: true}; PUB.busquedasAbiertas = true; pintarModulo();")
        pg.p.wait_for_timeout(500)
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(ancho <= 2, f"las búsquedas y la nota caben en un móvil, tema {tema} ({ancho}px)")
        texto = pg.p.evaluate("() => document.querySelector('#modulo').innerText")
        malos = sorted(set(x.group(0) for x in TEXTOS_MALOS.finditer(texto)))
        ok(not malos, f"sin «undefined», «NaN» ni «null» ({malos})")
        pg.captura(f"publicar_seo_real_movil_{tema}", entera=False)
        pg.sin_errores(f"el SEO de verdad en el móvil ({tema})")
        pg.cerrar()
    api.put(f"/api/publicar/proyectos/{cid}", {"palabra_clave": ""})
    api.put(f"/api/publicar/videos/{pid}", {"palabra_clave": ""})

if __name__ == "__main__":
    sys.exit(main())

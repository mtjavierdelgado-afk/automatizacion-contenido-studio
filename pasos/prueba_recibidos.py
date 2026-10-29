"""Prueba de ENVIAR AL STUDIO (rama enviar-al-studio, 28-10-2026).

Sin red y sin claves de verdad:

  1. las piezas: de qué red es un enlace, las cifras tal como se ven («1,2 mil»,
     «12K»…) y la captura (por sus bytes, con tope);
  2. el código de envío: solo se guarda su huella, uno nuevo invalida el viejo;
  3. los recibidos: guardar, listar, leer, marcar usado, borrar, el tope y el
     mensaje para el chat (marcado como referencia, no como instrucciones);
  4. la extensión: el manifiesto (MV3, sin permisos de más), que todo lo que
     nombra existe y el ZIP que se descarga;
  5. el lector de la página (extension/lector.js) en un Chromium de verdad,
     con páginas de cada red servidas aquí (si hay Playwright);
  6. el Studio por HTTP (si hay fastapi): el código, el envío, la lista, la
     captura y el ZIP.

    python pasos/prueba_recibidos.py
"""
import base64
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="recibidos_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")

import recibidos as R  # noqa: E402

_ok = 0
_fallos = []
EXT = os.path.join(RAIZ, "extension")
#: Un PNG de 1×1 de verdad (para que la captura pase por sus bytes).
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLO {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def lanza(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except R.ErrorRecibidos as fallo:
        return fallo
    return None


def seccion(titulo):
    print(f"\n[{titulo}]")


# ------------------------------------------------------------- 1. piezas

def prueba_piezas():
    seccion("1] piezas: la red, las cifras y la captura")
    redes = {"https://www.instagram.com/reel/abc/": "instagram", "https://vm.tiktok.com/x": "tiktok",
             "https://youtu.be/abc": "youtube", "https://m.youtube.com/shorts/x": "youtube",
             "https://web.facebook.com/x": "facebook", "https://fb.watch/x": "facebook",
             "https://www.linkedin.com/feed/update/x": "linkedin", "https://x.com/ana/status/1": "x",
             "https://twitter.com/ana": "x", "https://www.threads.net/@ana": "threads",
             "https://es.pinterest.com/pin/1": "pinterest", "https://ejemplo.com/a": "web",
             "https://instagram.com.malo.net/": "web", "no es un enlace": "web"}
    igual({u: R.red_de(u) for u in redes}, redes, "cada enlace, a su red (y un dominio falso no cuela)")
    cifras = {"1,2 mil": 1200, "12,5K": 12500, "3 M": 3_000_000, "2,5 mill.": 2_500_000, "1.5M": 1_500_000,
              "1.234": 1234, "1,234 likes": 1234, "12 345 vistas": 12345, "1.234.567": 1234567,
              "45 mil millones": 45_000_000_000, "987": 987, "Me gusta: 3,4 k": 3400, "0": 0,
              "3,1 mil reproducciones": 3100, "sin cifras": None, "": None}
    igual({t: R.numero_visto(t) for t in cifras}, cifras, "las cifras como se ven, a número (español e inglés)")
    datos, tipo = R._captura_de("data:image/png;base64," + base64.b64encode(PNG).decode())
    igual((datos, tipo), (PNG, "png"), "una captura en data URL")
    ok(lanza(R._captura_de, base64.b64encode(b"<html>hola</html>").decode()) is not None,
       "lo que no es una imagen (por sus bytes), no")
    grande = base64.b64encode(b"\xff\xd8\xff" + b"0" * (R.MAX_CAPTURA + 10)).decode()
    f = lanza(R._captura_de, grande)
    ok(f is not None and f.codigo == 413, "una captura de más de 4 MB, 413")


# ------------------------------------------------------------- 2. código

def prueba_codigo():
    seccion("2] el código de envío")
    igual(R.estado_codigo()["puesto"], False, "de fábrica no hay código")
    ok(not R.comprobar("env_loquesea"), "y ninguno vale")
    nuevo = R.crear_codigo()
    ok(nuevo["codigo"].startswith("env_") and len(nuevo["codigo"]) > 20, "uno nuevo, largo")
    with open(R._ruta_codigo(), encoding="utf-8") as fh:
        crudo = fh.read()
    ok(nuevo["codigo"] not in crudo, "en el disco solo su huella, nunca el código")
    ok(R._ruta_codigo().startswith(os.environ["ESTUDIO_SECRETOS"]), "en la carpeta de secretos")
    if os.name == "posix":
        igual(oct(os.stat(R._ruta_codigo()).st_mode & 0o777), "0o600", "solo lo lee el servicio")
    ok(R.comprobar(nuevo["codigo"]) and R.comprobar(f"  {nuevo['codigo']} "), "el bueno vale (aunque traiga espacios)")
    ok(not R.comprobar(nuevo["codigo"] + "x") and not R.comprobar(""), "otro, o ninguno, no")
    est = R.estado_codigo()
    ok(est["puesto"] and est["cola"] == "…" + nuevo["codigo"][-4:] and "codigo" not in est,
       "lo que ve la pantalla: puesto y sus 4 últimos")
    otro = R.crear_codigo()
    ok(R.comprobar(otro["codigo"]) and not R.comprobar(nuevo["codigo"]), "uno nuevo deja sin valer el de antes")


# --------------------------------------------------------- 3. recibidos

def prueba_recibidos():
    seccion("3] los recibidos")
    raiz = os.path.join(CARPETA, "proyectos")
    os.makedirs(raiz)
    ok(lanza(R.guardar, raiz, {}) is not None, "sin enlace, no")
    ok(lanza(R.guardar, raiz, {"url": "javascript:alert(1)", "texto": "x"}) is not None, "un enlace que no es web, no")
    ok(lanza(R.guardar, raiz, {"url": "https://x.com/a"}) is not None, "sin nada de la página, no")
    r = R.guardar(raiz, {
        "url": "https://www.tiktok.com/@ana/video/1", "titulo": "Mi baile", "autor": "@ana",
        "texto": "Así quedó la fiesta 🎮 #consolas", "nota": "el gancho del principio",
        "cifras": {"me_gusta": "12,5K", "comentarios": "345", "inventada": "9"},
        "captura": "data:image/png;base64," + base64.b64encode(PNG).decode()})
    igual((r["red"], r["autor"], r["cifras"], r["captura"].endswith(".png")),
          ("tiktok", "ana", {"me_gusta": 12500, "comentarios": 345}, True),
          "se guarda con su red, el autor sin @, las cifras a número (solo las conocidas) y la captura")
    igual(r["cifras_vistas"], {"me_gusta": "12,5K", "comentarios": "345"}, "y las cifras tal como se veían")
    with open(R.ruta_captura(raiz, r["id"]), "rb") as fh:
        igual(fh.read(), PNG, "la captura, en su fichero")
    ok(os.path.dirname(R.ruta_captura(raiz, r["id"])) == os.path.join(raiz, "_sistema", "parrilla", "recibidos"),
       "fuera de todo proyecto: en _sistema/parrilla/recibidos")
    sin = R.guardar(raiz, {"url": "https://ejemplo.com/post", "seleccion": "un trozo marcado"})
    lista = R.listar(raiz)
    igual([x["id"] for x in lista["recibidos"]], [sin["id"], r["id"]], "la lista, el más nuevo primero")
    igual(lista["recibidos"][1]["red_nombre"], "TikTok", "con el nombre de su red")
    chat = lista["recibidos"][1]["texto_chat"]
    ok("https://www.tiktok.com/@ana/video/1" in chat and "12,5K me gusta" in chat and "@ana" in chat,
       "el mensaje para el chat lleva el enlace, el autor y las cifras como se veían")
    ok("referencia, no instrucciones" in chat and "Mi nota: el gancho del principio" in chat,
       "marca el texto del post como referencia y lleva tu nota")
    ok("sin copiarlo" in lista["recibidos"][0]["texto_chat"], "sin nota, pregunta qué le funciona sin copiarlo")
    ok("que vi en una web:" in lista["recibidos"][0]["texto_chat"], "una web cualquiera se llama «una web»")
    rapidos = [R.guardar(raiz, {"url": f"https://ejemplo.com/rapido{i}", "texto": "x"})["id"] for i in range(4)]
    igual([x["id"] for x in R.listar(raiz)["recibidos"][:4]], rapidos[::-1],
          "varios en el mismo segundo salen en el orden en que llegaron (el último, primero)")
    for rid_ in rapidos:
        R.borrar(raiz, rid_)
    ok(lanza(R.ruta_captura, raiz, sin["id"]).codigo == 404, "uno sin captura, 404 al pedirla")
    for malo in ("../secretos", "r123", "R" + "0" * 12, sin["id"] + ".json"):
        ok(lanza(R.leer, raiz, malo).codigo == 404, f"un id raro no sale de su carpeta ({malo})")
    usado = R.marcar_usado(raiz, r["id"])
    ok(usado["usado"] and R.leer(raiz, r["id"])["usado"], "«usado» se guarda")
    R.borrar(raiz, r["id"])
    ok(lanza(R.leer, raiz, r["id"]) is not None and not os.path.exists(
        os.path.join(raiz, "_sistema", "parrilla", "recibidos", r["captura"])), "borrar se lleva el texto y la captura")
    largo = R.guardar(raiz, {"url": "https://ejemplo.com", "texto": "x" * 9000})
    igual(len(largo["texto"]), R.MAX_TEXTO, "un texto enorme se recorta")
    antes = R.MAX_RECIBIDOS
    R.MAX_RECIBIDOS = 3
    try:
        for i in range(5):
            R.guardar(raiz, {"url": f"https://ejemplo.com/{i}", "texto": f"n{i}"})
        igual(R.listar(raiz)["total"], 3, "al pasar el tope se borran los más viejos")
        archivos = os.listdir(os.path.join(raiz, "_sistema", "parrilla", "recibidos"))
        igual(len([a for a in archivos if a.endswith(".json")]), 3, "(también del disco)")
    finally:
        R.MAX_RECIBIDOS = antes


# --------------------------------------------------------- 4. la extensión

def prueba_extension():
    seccion("4] la extensión: el manifiesto y el ZIP")
    with open(os.path.join(EXT, "manifest.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    igual(m.get("manifest_version"), 3, "Manifest V3 (lo que Chrome acepta hoy)")
    igual(sorted(m.get("permissions") or []), ["activeTab", "scripting", "storage"],
          "permisos mínimos: la pestaña que pulsas, inyectar el lector y guardar tus ajustes")
    ok("host_permissions" not in m and set(m.get("optional_host_permissions") or []) <= {"https://*/*", "http://*/*"},
       "ningún permiso fijo sobre webs: el de tu Studio se pide al guardar")
    nombrados = [m["action"]["default_popup"]] + list(m["icons"].values()) + list(m["action"]["default_icon"].values())
    ok(all(os.path.isfile(os.path.join(EXT, n)) for n in nombrados), "todo lo que nombra el manifiesto existe")
    with open(os.path.join(EXT, "popup.html"), encoding="utf-8") as fh:
        popup = fh.read()
    ok('src="popup.js"' in popup and "<script>" not in popup and "onclick" not in popup,
       "el popup no lleva código en línea (la CSP de las extensiones lo bloquea)")
    with open(os.path.join(EXT, "popup.js"), encoding="utf-8") as fh:
        js = fh.read()
    ok("files: ['lector.js']" in js and "X-Estudio-Envio" in js and "captureVisibleTab" in js,
       "el popup inyecta el lector, captura y manda el código")
    ok("eval(" not in js and "innerHTML" not in js, "sin eval ni innerHTML")
    if shutil.which("node"):
        for nombre in ("popup.js", "lector.js"):
            r = subprocess.run(["node", "--check", os.path.join(EXT, nombre)], capture_output=True, text=True)
            ok(r.returncode == 0, f"{nombre} es JavaScript válido {r.stderr.strip()[:200]}")
    datos = R.zip_extension()
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombres = z.namelist()
        dentro = json.loads(z.read("crearia-enviar-al-studio/manifest.json"))
    ok("crearia-enviar-al-studio/manifest.json" in nombres and "crearia-enviar-al-studio/lector.js" in nombres,
       "el ZIP trae la carpeta lista para «Cargar descomprimida»")
    ok(not any("/." in n or n.endswith(".pyc") for n in nombres), "sin ficheros ocultos")
    igual(dentro["version"], R.version_extension(), "y su versión")
    vacia = os.path.join(CARPETA, "sin_extension")
    os.makedirs(vacia)
    ok(lanza(R.zip_extension, vacia).codigo == 503, "sin la carpeta, lo dice (503)")


# --------------------------------------------------------- 5. el lector

PAGINAS = {
    "https://www.tiktok.com/@ana_baila/video/7300": """<html><head><title>TikTok</title>
      <meta property="og:title" content="Ana en TikTok"></head><body>
      <a data-e2e="browse-username">ana_baila</a>
      <h1 data-e2e="browse-video-desc">Así quedó la fiesta 🎮 #consolas</h1>
      <strong data-e2e="like-count">12.5K</strong><strong data-e2e="comment-count">345</strong>
      <strong data-e2e="share-count">1,2 mil</strong><strong data-e2e="undefined-count">980</strong></body></html>""",
    "https://www.instagram.com/reel/Cabc/": """<html><head><title>Instagram</title>
      <meta property="og:description" content='1.234 Me gusta, 56 comentarios - estadoplay el 3 de octubre de 2026: "Así quedó la fiesta 🎮"'>
      </head><body><article><span>12,3 mil reproducciones</span></article></body></html>""",
    "https://www.youtube.com/watch?v=abc": """<html><head><title>Vídeo - YouTube</title>
      <meta itemprop="interactionCount" content="45678"></head><body>
      <h1 class="ytd-watch-metadata">Cómo montar una fiesta gamer</h1>
      <ytd-channel-name><a>Canal Ana</a></ytd-channel-name>
      <like-button-view-model><button aria-label="Indicar que te gusta este vídeo junto con 1.234 personas más">1,2 K</button></like-button-view-model>
      <div id="description-inline-expander">Todo lo que necesitas para tu fiesta.</div></body></html>""",
    "https://x.com/ana_r/status/123": """<html><head><title>X</title></head><body>
      <article data-testid="tweet" tabindex="-1"><div data-testid="User-Name">Ana R @ana_r</div>
      <div data-testid="tweetText">Un hilo sobre fiestas gamer 🧵</div>
      <div role="group" aria-label="12 respuestas, 34 reposts, 560 Me gusta, 89012 visualizaciones"></div>
      </article></body></html>""",
    "https://www.linkedin.com/feed/update/urn:li:activity:1/": """<html><head><title>LinkedIn</title></head><body>
      <span class="update-components-actor__name">Empresa SAC</span>
      <div class="update-components-text">Cinco ideas para eventos corporativos.</div>
      <div class="social-details-social-counts"><span class="social-details-social-counts__reactions-count">1.024</span>
      <span>38 comentarios</span> · <span>12 veces compartido</span></div></body></html>""",
    "https://www.facebook.com/estadoplay/posts/1": """<html><head><title>Facebook</title>
      <meta property="og:description" content="Fiesta del sábado"></head><body>
      <h2><strong><a>EstadoPlay</a></strong></h2><div data-ad-preview="message">Así fue la fiesta del sábado</div>
      <span aria-label="345 reacciones"></span><span aria-label="28 comentarios"></span></body></html>""",
    "https://blog.ejemplo.com/ideas-fiesta": """<html><head><title>Ideas para tu fiesta</title>
      <meta property="og:title" content="10 ideas para una fiesta gamer">
      <meta property="og:description" content="Las mejores ideas, probadas."></head>
      <body><p id="p">Un párrafo que el dueño marca.</p></body></html>""",
}


def prueba_lector():
    seccion("5] el lector de la página, en Chromium")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  OMITIDA: falta Playwright en este entorno")
        return
    with open(os.path.join(EXT, "lector.js"), encoding="utf-8") as fh:
        lector = fh.read()
    resultados = {}
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = navegador.new_page()
            pagina.route("**/*", lambda ruta: ruta.fulfill(
                status=200, content_type="text/html; charset=utf-8",
                body=PAGINAS.get(ruta.request.url, "<html><body>nada</body></html>")))
            for url in PAGINAS:
                pagina.goto(url)
                if "blog.ejemplo" in url:
                    pagina.evaluate("() => { const r = document.createRange(); r.selectNodeContents(document.getElementById('p'));"
                                    " getSelection().removeAllRanges(); getSelection().addRange(r); }")
                resultados[url] = pagina.evaluate(lector)
            navegador.close()
    except Exception as fallo:                          # noqa: BLE001
        print(f"  OMITIDA: no arranca Chromium ({str(fallo)[:160]})")
        return
    t = resultados["https://www.tiktok.com/@ana_baila/video/7300"]
    igual((t["red"], t["autor"], t["texto"]), ("tiktok", "ana_baila", "Así quedó la fiesta 🎮 #consolas"), "TikTok: autor y texto")
    igual(t["cifras"], {"me_gusta": "12.5K", "comentarios": "345", "compartidos": "1,2 mil", "guardados": "980"},
          "TikTok: sus cuatro cifras")
    i = resultados["https://www.instagram.com/reel/Cabc/"]
    igual((i["red"], i["autor"], i["texto"]), ("instagram", "estadoplay", "Así quedó la fiesta 🎮"),
          "Instagram: autor y texto desde la descripción de la página")
    igual(i["cifras"], {"me_gusta": "1.234", "comentarios": "56", "vistas": "12,3 mil"},
          "Instagram: me gusta, comentarios y reproducciones")
    y = resultados["https://www.youtube.com/watch?v=abc"]
    igual((y["red"], y["titulo"], y["autor"], y["cifras"].get("vistas"), y["cifras"].get("me_gusta")),
          ("youtube", "Cómo montar una fiesta gamer", "Canal Ana", "45678", "1,2 K"), "YouTube: título, canal, vistas y me gusta")
    x = resultados["https://x.com/ana_r/status/123"]
    igual((x["red"], x["autor"], x["texto"]), ("x", "ana_r", "Un hilo sobre fiestas gamer 🧵"), "X: autor y texto")
    igual(x["cifras"], {"vistas": "89012", "me_gusta": "560", "comentarios": "12", "compartidos": "34"},
          "X: las cuatro cifras de su etiqueta")
    li = resultados["https://www.linkedin.com/feed/update/urn:li:activity:1/"]
    igual((li["red"], li["autor"], li["cifras"]), ("linkedin", "Empresa SAC",
          {"me_gusta": "1.024", "comentarios": "38", "compartidos": "12"}), "LinkedIn: autor y cifras")
    fb = resultados["https://www.facebook.com/estadoplay/posts/1"]
    igual((fb["red"], fb["texto"], fb["cifras"]), ("facebook", "Así fue la fiesta del sábado",
          {"me_gusta": "345", "comentarios": "28"}), "Facebook: texto y cifras de sus etiquetas")
    w = resultados["https://blog.ejemplo.com/ideas-fiesta"]
    igual((w["red"], w["titulo"], w["texto"], w["seleccion"]),
          ("web", "10 ideas para una fiesta gamer", "Las mejores ideas, probadas.", "Un párrafo que el dueño marca."),
          "cualquier otra web: lo genérico y lo seleccionado")
    raiz = os.path.join(CARPETA, "proyectos")
    r = R.guardar(raiz, x)
    igual(r["cifras"], {"vistas": 89012, "me_gusta": 560, "comentarios": 12, "compartidos": 34},
          "lo que lee la extensión se guarda con sus cifras en número")


# ------------------------------------------------- 5b. el botón (popup.js)

#: Lo que la página del botón ve de Chrome, de mentira: la pestaña activa, el
#: lector, la captura, los ajustes y (si se pide) una pestaña del Studio abierta.
CHROME_FALSO = """
window.__estado = { guardado: {studio: 'https://studio.prueba/', codigo: 'env_bueno'}, pestanasStudio: [] };
window.chrome = {
  storage: { local: {
    get: async () => Object.assign({}, window.__estado.guardado),
    set: async o => { Object.assign(window.__estado.guardado, o); },
  } },
  tabs: {
    query: async q => q.active
      ? [{ id: 1, windowId: 1, url: 'https://www.tiktok.com/@ana/video/1', title: 'TikTok' }]
      : window.__estado.pestanasStudio,
    captureVisibleTab: async () => 'data:image/png;base64,""" + base64.b64encode(PNG).decode() + """',
  },
  scripting: { executeScript: async o => o.files
    ? [{ result: { url: 'https://www.tiktok.com/@ana/video/1', red: 'tiktok', autor: 'ana', titulo: 'Ana',
                   texto: 'Así quedó la fiesta', cifras: { me_gusta: '12K' } } }]
    : [{ result: await o.func(...o.args) }] },
  permissions: { request: async () => true },
};
"""


def prueba_boton():
    seccion("5b] el botón: leer, capturar y enviar (con un Chrome de mentira)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  OMITIDA: falta Playwright en este entorno")
        return
    llegadas = []
    respuestas = []

    def servir(ruta):
        url = ruta.request.url
        if url.startswith("https://studio.prueba/") and "/api/" in url:
            llegadas.append((ruta.request.method, url, ruta.request.headers.get("x-estudio-envio"),
                             ruta.request.post_data))
            estado, cuerpo, cabeceras = respuestas.pop(0) if respuestas else (201, {"ok": True}, {})
            return ruta.fulfill(status=estado, headers=dict({"Content-Type": "application/json"}, **cabeceras),
                                body=json.dumps(cuerpo))
        nombre = url.split("studio.prueba/", 1)[-1].split("?")[0] or "popup.html"
        ruta_local = os.path.join(EXT, nombre)
        if not os.path.isfile(ruta_local):
            return ruta.fulfill(status=404, body="")
        tipo = {"html": "text/html", "js": "text/javascript", "css": "text/css", "png": "image/png"}[nombre.rsplit(".", 1)[-1]]
        with open(ruta_local, "rb") as fh:
            return ruta.fulfill(status=200, headers={"Content-Type": tipo}, body=fh.read())

    def abrir(navegador):
        pagina = navegador.new_page(viewport={"width": 360, "height": 640})
        pagina.add_init_script(CHROME_FALSO)
        pagina.route("**/*", servir)
        pagina.goto("https://studio.prueba/popup.html")
        pagina.wait_for_selector("#envio:not([hidden])", timeout=5000)
        return pagina

    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = abrir(navegador)
            igual((pagina.inner_text("#red"), pagina.inner_text("#autor"), pagina.inner_text("#cifras")),
                  ("TikTok", "@ana", "12K me gusta"), "al abrirlo enseña lo que leyó de la pestaña")
            pagina.fill("#nota", "el gancho")
            pagina.click("#enviar")
            try:
                pagina.wait_for_function("document.getElementById('estado').textContent.includes('Enviado')", timeout=5000)
            except Exception:
                print("   estado:", pagina.inner_text("#estado"))
                raise
            metodo, url, codigo, cuerpo = llegadas[-1]
            enviado = json.loads(cuerpo)
            ok(metodo == "POST" and url == "https://studio.prueba/api/recibidos" and codigo == "env_bueno",
               "manda a <Studio>/api/recibidos con el código en su cabecera")
            ok(enviado["nota"] == "el gancho" and enviado["captura"].startswith("data:image/png;base64,")
               and enviado["cifras"] == {"me_gusta": "12K"}, "con la nota, la captura y las cifras")
            ok(R.guardar(os.path.join(CARPETA, "proyectos"), enviado)["cifras"] == {"me_gusta": 12000},
               "y eso es justo lo que el Studio sabe guardar")
            pagina.close()

            # sin sesión (el login redirige) y SIN pestaña del Studio: lo dice
            pagina = abrir(navegador)
            respuestas.append((302, {}, {"Location": "https://studio.prueba/login"}))
            pagina.click("#enviar")
            pagina.wait_for_function("document.getElementById('estado').classList.contains('mal')", timeout=5000)
            ok("Abre tu Studio en otra pestaña" in pagina.inner_text("#estado"),
               "sin sesión ni pestaña del Studio, pide abrirlo e iniciar sesión")
            ok(not pagina.is_disabled("#enviar"), "y deja volver a pulsar")
            # ...y con una pestaña del Studio abierta, lo manda desde ella
            pagina.evaluate("window.__estado.pestanasStudio = [{id: 7, url: 'https://studio.prueba/'}]")
            respuestas.extend([(302, {}, {"Location": "https://studio.prueba/login"}), (201, {"ok": True}, {})])
            antes = len(llegadas)
            pagina.click("#enviar")
            pagina.wait_for_function("document.getElementById('estado').textContent.includes('Enviado')", timeout=5000)
            igual(len(llegadas) - antes, 2, "sin sesión directa, se repite desde la pestaña del Studio y llega")
            pagina.close()

            # un código que ya no vale
            pagina = abrir(navegador)
            respuestas.append((401, {"error": "el código de envío no vale"}, {}))
            pagina.click("#enviar")
            pagina.wait_for_function("document.getElementById('estado').classList.contains('mal')", timeout=5000)
            ok("código de envío no vale" in pagina.inner_text("#estado"), "un código que no vale: dice cómo arreglarlo")
            pagina.close()

            # sin ajustes: primero la dirección y el código; «Probar» llama al ping
            pagina = navegador.new_page(viewport={"width": 360, "height": 640})
            pagina.add_init_script(CHROME_FALSO + "window.__estado.guardado = {};")
            pagina.route("**/*", servir)
            pagina.goto("https://studio.prueba/popup.html")
            pagina.wait_for_selector("#config:not([hidden])", timeout=5000)
            ok(True, "sin ajustes, abre en la dirección y el código")
            pagina.fill("#studio", "https://studio.prueba/v2/")
            pagina.fill("#codigo", "env_nuevo")
            respuestas.append((200, {"ok": True}, {}))
            pagina.click("#probar")
            try:
                pagina.wait_for_function("document.getElementById('estadoConfig').textContent.includes('Conectado')",
                                         timeout=5000)
            except Exception:
                print("   estadoConfig:", pagina.inner_text("#estadoConfig"))
                raise
            igual(llegadas[-1][1:3], ("https://studio.prueba/v2/api/recibidos/ping", "env_nuevo"),
                  "«Probar» llama al ping de un Studio en una carpeta (/v2/) con el código nuevo")
            pagina.close()
            navegador.close()
    except Exception as fallo:                          # noqa: BLE001
        ok(False, f"el botón: {str(fallo)[:300]} · llegadas={[l[:2] for l in llegadas]}")


# --------------------------------------------------------- 6. por HTTP

def _arrancar(carpeta):
    import requests
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    entorno = dict(os.environ)
    entorno.update({"PYTHONIOENCODING": "utf-8", "ESTUDIO_SIMULAR": "1",
                    "ESTUDIO_SECRETOS": os.path.join(carpeta, "secretos"),
                    "ESTUDIO_AJUSTES": os.path.join(carpeta, "ajustes.json"),
                    "ESTUDIO_PRESETS": os.path.join(carpeta, "presets.json"),
                    "ESTUDIO_BANCO_PRESETS": os.path.join(carpeta, "banco"),
                    "ESTUDIO_RECETAS": os.path.join(carpeta, "recetas.json"),
                    "ESTUDIO_ESTADISTICAS": os.path.join(carpeta, "estadisticas.json"),
                    "ESTUDIO_COSTE_GLOBAL": os.path.join(carpeta, "coste_global.jsonl")})
    os.makedirs(entorno["ESTUDIO_SECRETOS"], exist_ok=True)
    proceso = subprocess.Popen(
        [sys.executable, os.path.join(RAIZ, "app.py"), "--puerto", str(puerto),
         "--proyectos", os.path.join(carpeta, "proyectos")],
        cwd=RAIZ, env=entorno, stdout=open(os.path.join(carpeta, "servidor.log"), "w"),
        stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            with open(os.path.join(carpeta, "servidor.log"), encoding="utf-8", errors="replace") as fh:
                raise RuntimeError("el servidor murió al arrancar:\n" + fh.read()[-3000:])
        try:
            if requests.get(base + "/api/salud", timeout=2).status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el servidor no respondió en 90 s")


def prueba_studio():
    import requests
    seccion("6] el Studio por HTTP")
    carpeta = os.path.join(CARPETA, "studio")
    os.makedirs(os.path.join(carpeta, "proyectos"))
    proceso, base = _arrancar(carpeta)
    s = requests.Session()
    try:
        r = s.get(base + "/api/recibidos").json()
        igual((r["recibidos"], r["codigo"]["puesto"], bool(r["version_extension"])), ([], False, True),
              "GET /api/recibidos: vacío, sin código y con la versión de la extensión")
        igual(s.get(base + "/api/recibidos/ping").status_code, 401, "sin código, ping 401")
        cuerpo = {"url": "https://www.tiktok.com/@ana/video/1", "texto": "hola", "cifras": {"vistas": "1,2 mil"},
                  "captura": "data:image/png;base64," + base64.b64encode(PNG).decode()}
        igual(s.post(base + "/api/recibidos", json=cuerpo).status_code, 401, "sin código no se guarda nada (401)")
        codigo = s.post(base + "/api/recibidos/codigo", json={}).json()
        ok(codigo["codigo"].startswith("env_") and codigo["puesto"], "crear el código lo enseña una vez")
        ok(codigo["codigo"] not in json.dumps(s.get(base + "/api/recibidos").json()), "y ninguna otra ruta lo devuelve")
        cab = {"X-Estudio-Envio": codigo["codigo"]}
        igual(s.get(base + "/api/recibidos/ping", headers={"X-Estudio-Envio": "env_malo"}).status_code, 401,
              "con uno malo, 401")
        igual(s.get(base + "/api/recibidos/ping", headers=cab).json()["ok"], True, "con el bueno, ping")
        r = s.post(base + "/api/recibidos", json=cuerpo, headers=cab)
        igual((r.status_code, r.json()["red"]), (201, "tiktok"), "POST /api/recibidos con el código: 201")
        rid = r.json()["id"]
        lista = s.get(base + "/api/recibidos").json()
        igual((lista["total"], lista["recibidos"][0]["cifras"]["vistas"]), (1, 1200), "y sale en la lista, con sus cifras")
        cap = s.get(base + f"/api/recibidos/{rid}/captura")
        igual((cap.status_code, cap.headers.get("content-type"), cap.content), (200, "image/png", PNG), "su captura")
        igual(s.post(base + f"/api/recibidos/{rid}/usado", json={}).status_code, 200, "marcarlo usado")
        igual(s.get(base + "/api/recibidos/r000000000000/captura").status_code, 404, "uno que no existe, 404")
        z = s.get(base + "/api/recibidos/extension.zip")
        ok(z.status_code == 200 and z.headers.get("content-type") == "application/zip"
           and "crearia-enviar-al-studio.zip" in z.headers.get("content-disposition", ""), "descargar la extensión")
        with zipfile.ZipFile(io.BytesIO(z.content)) as zz:
            ok("crearia-enviar-al-studio/manifest.json" in zz.namelist(), "(con su manifiesto)")
        igual(s.delete(base + f"/api/recibidos/{rid}").status_code, 200, "borrarlo")
        igual(s.get(base + "/api/recibidos").json()["total"], 0, "y ya no está")
        nuevo = s.post(base + "/api/recibidos/codigo", json={}).json()
        igual(s.get(base + "/api/recibidos/ping", headers=cab).status_code, 401, "un código nuevo deja sin valer el viejo")
        igual(s.get(base + "/api/recibidos/ping", headers={"X-Estudio-Envio": nuevo["codigo"]}).status_code, 200,
              "y vale el nuevo")
    finally:
        proceso.terminate()
        try:
            proceso.wait(10)
        except subprocess.TimeoutExpired:
            proceso.kill()


def main():
    print("PRUEBA DE ENVIAR AL STUDIO")
    prueba_piezas()
    prueba_codigo()
    prueba_recibidos()
    prueba_extension()
    prueba_lector()
    prueba_boton()
    try:
        import fastapi  # noqa: F401
        import requests  # noqa: F401
        hay_servidor = True
    except ImportError:
        hay_servidor = False
    if hay_servidor:
        prueba_studio()
    else:
        print("\n[6] OMITIDA: falta fastapi en este entorno (en el servidor sí corre)")
    shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"RECIBIDOS OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

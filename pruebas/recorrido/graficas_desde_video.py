"""Recorrido de la rama graficas-desde-video: «Crear desde un vídeo» y la foto tenue de fondo.

Con el vídeo de prueba del recorrido («padres_vs_hijos», del proyecto Estado
Play, montado de verdad): la lista de sus planos; otro proyecto no puede leerlo
ni usarlo (403 al leer, al escribir y al crear); «+ Crear» → Carrusel → desde el
vídeo → «Escríbelo por mí desde el vídeo» (Claude simulado) → cambiar la imagen
de una parte a «sin foto» → estilo → Crear → cada imagen con su foto tenue y la
portada con la suya → quitar una → «Otro estilo» la deja debajo de los textos →
«← Cambiar tema» vuelve con el vídeo y sus imágenes. Y en el móvil, una
publicación desde el vídeo.
"""
import json

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401


def _esperar_js(pg, expresion, segundos=20, arg=None):
    try:
        pg.p.wait_for_function(expresion, arg=arg, timeout=segundos * 1000)
        return True
    except Exception:                                        # noqa: BLE001
        return False


def _ed(pg, expresion):
    return pg.p.evaluate(f"() => {{ const E = EditorCapas._estado(); return JSON.parse(JSON.stringify({expresion})); }}")


class _ConTacto:
    def __init__(self, navegador):
        self.n = navegador

    def new_context(self, **kw):
        kw.update(has_touch=True, is_mobile=True)
        return self.n.new_context(**kw)


ORDEN_OK = """() => { const E = EditorCapas._estado();
  const tapa = c => c.tipo === 'forma' && !c.oculto && c.figura === 'rect' && c.x <= 0.5 && c.y <= 0.5 && c.x + c.w >= 99.5
    && c.y + c.h >= 99.5 && c.relleno && !c.relleno.degradado && c.relleno.alfa * (c.opac === undefined ? 1 : c.opac) >= 0.99;
  return E.doc.laminas.every(l => { const i = l.capas.findIndex(c => c.rol === 'foto_fondo');
    if (i < 0) return true; const t = l.capas.findIndex(c => c.tipo === 'texto');
    return (t < 0 || i < t) && !l.capas.slice(i + 1, t < 0 ? undefined : t).some(tapa); }); }"""


@escenario
def graficas_desde_video(navegador, datos):
    api, cid, pid = datos["api"], datos["cliente"], datos["video"]
    r, d = api.get(f"/api/graficas/{cid}/videos/{pid}/planos")
    ok(r.status_code == 200 and d.get("vale") and len(d.get("planos", [])) >= 3,
       f"el vídeo de prueba tiene planos con imagen y voz ({len(d.get('planos', []))})")
    planos = [p["sid"] for p in d.get("planos", [])]
    r, otro = api.post("/api/clientes", {"nombre": "Otro proyecto"})
    otro = otro.get("id") or (otro.get("cliente") or {}).get("id")
    ok(api.get(f"/api/graficas/{otro}/videos/{pid}/planos")[0].status_code == 403, "otro proyecto no puede leer sus planos (403)")
    r, _ = api.post(f"/api/graficas/{otro}/escribir", {"que": "carrusel", "tema": "x", "pid": pid})
    ok(r.status_code == 403, "ni escribir desde él (403)")
    r, _ = api.post(f"/api/graficas/{otro}/capas/crear", {"que": "carrusel", "familia": 2, "pid": pid,
                                                          "piezas": [["portada", {"titulo": "Hola", "plano": planos[0]}], ["cierre", {}]]})
    ok(r.status_code == 403, "ni crear con sus imágenes (403)")
    r, _ = api.post(f"/api/graficas/{cid}/capas/crear", {"que": "carrusel", "familia": 2, "pid": pid,
                                                         "piezas": [["portada", {"titulo": "Hola", "plano": "no_es_un_plano"}], ["cierre", {}]]})
    ok(r.status_code == 400, "un plano que no está en su lista: 400")

    pg = Pagina(navegador, datos, ancho=1500, alto=1000, nombre="desde_video")
    try:
        pg.js("try { localStorage.removeItem('crearia.graficas.modo'); } catch (_) {}")
        pg.js(f"elegirCliente({json.dumps(cid)});")
        ok(pg.esperar(".seccion-graficas .crear-en-graficas", "+ Crear", 30), "el proyecto del vídeo tiene «+ Crear»")
        pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
        pg.pulsar("#crear-grafica .gc-que-carrusel")
        ok(pg.esperar("#crear-grafica .gc-video-base", segundos=10), "el paso 2 ofrece «O créalo desde uno de tus vídeos»")
        pg.p.select_option("#crear-grafica .gc-video-base", pid)
        ok(pg.esperar("#crear-grafica .gc-desde-video", "imágenes con voz", 30), "dice cuántas imágenes con voz tiene")
        ok(pg.esperar("#crear-grafica .gc-desde-video", "siempre en español", 2), "y que los textos van en español")
        pg.pulsar("#crear-grafica .gc-escribir", "desde el vídeo")
        ok(pg.esperar("#crear-grafica .gc-propuesta-video", "cada una con su imagen", 60), "Claude (simulado) escribe desde el vídeo")
        piezas = pg.p.evaluate("() => EditorCapas._asistente().piezas")
        con_plano = [x["plano"] for _t, x in piezas if x.get("plano")]
        ok(len(con_plano) >= 2 and len(set(con_plano)) == len(con_plano) and all(s in planos for s in con_plano),
           f"cada imagen con un plano del vídeo, sin repetir ({con_plano})")
        ok(pg.p.locator("#crear-grafica .gc-cambiar-plano img").count() >= 2, "la propuesta enseña la imagen de cada parte")
        ok(_esperar_js(pg, "() => !!EditorCapas._asistente().foto", 20), "la foto de la portada sale del vídeo (para las miniaturas)")
        # cambiar la imagen de la parte 2 a «sin foto»
        pg.pulsar('#crear-grafica .gc-cambiar-plano[data-i="1"]')
        ok(pg.esperar(".ce-modal h2", "Otra imagen del vídeo", 5), "tocar una imagen deja elegir otra")
        ok(pg.p.locator(".ce-modal .gc-plano-video:disabled").count() >= 1, "las que ya usa otra parte no se pueden repetir")
        pg.pulsar(".ce-modal .gc-sin-foto", "Sin foto")
        ok(pg.p.evaluate("() => EditorCapas._asistente().piezas[1][1].plano") == "", "o ninguna")
        ok(_esperar_js(pg, "() => document.querySelectorAll('#crear-grafica .gc-estilo img').length >= 4", 90), "las miniaturas de estilo")
        pg.pulsar('#crear-grafica .gc-estilo[data-n="1"]')
        pg.captura("desde-video-paso2")
        pg.pulsar("#crear-grafica .gc-crear", "Crear")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return E && E.sencillo && E.lienzo.querySelector('[data-c]'); }", 90),
           "se crea y abre en el modo sencillo")
        laminas = _ed(pg, "E.doc.laminas.map(l => l.capas.filter(c => c.rol === 'foto_fondo').map(c => c.opac))")
        con_foto = [i for i, f in enumerate(laminas) if f]
        ok(0 in con_foto, "la portada del estilo 1 (sin hueco grande) lleva su foto de fondo")
        ok(1 not in con_foto, "la parte que quedó «sin foto» va sin foto")
        ok(len(con_foto) >= 2 and all(0.1 <= f[0] <= 0.35 for f in laminas if f), f"las demás, tenues (opacidades {laminas})")
        ok(pg.p.evaluate(ORDEN_OK), "siempre justo encima del Fondo, debajo de los textos")
        ok(all(_ed(pg, f"E.doc.laminas[{i}].alt || ''") for i in con_foto), "y con su texto alternativo")
        pg.captura("desde-video-editor")
        # quitar una foto desde el panel
        otra = [i for i in con_foto if i > 0][0]
        pg.js(f"document.querySelectorAll('#editor-capas .ce-tira-lamina')[{otra}].click();")
        ok(pg.esperar("#editor-capas .ce-s-foto-tenue", "tenue", 5), "el panel explica la foto tenue")
        pg.pulsar("#editor-capas .ce-s-quitar-foto", "Quitar la foto")
        ok(not _ed(pg, f"E.doc.laminas[{otra}].capas.some(c => c.rol === 'foto_fondo')"), "«Quitar la foto» la quita")
        # tocar el lienzo no elige la foto de fondo
        primera = [i for i in con_foto if i > 0 and i != otra]
        if primera:
            pg.js(f"document.querySelectorAll('#editor-capas .ce-tira-lamina')[{primera[0]}].click();")
            caja = pg.p.evaluate("() => { const r = EditorCapas._estado().lienzo.getBoundingClientRect(); return [r.left + 8, r.top + r.height - 8]; }")
            pg.p.mouse.click(*caja)
            ok(not _ed(pg, "E.sel.some(id => E.doc.laminas[E.lamina].capas.find(c => c.id === id && c.rol === 'foto_fondo'))"),
               "tocar el lienzo no elige la foto de fondo")
        # otro estilo: las fotos siguen debajo de los textos
        pg.pulsar("#editor-capas .ce-s-otro-estilo", "Otro estilo")
        ok(_esperar_js(pg, "() => document.querySelectorAll('.ce-modal-estilos .gc-estilo img').length >= 4", 90), "«Otro estilo» con miniaturas")
        pg.pulsar('.ce-modal-estilos .gc-estilo[data-n="2"]')
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[0].familia === 2", 60), "se pone el estilo 2")
        ok(pg.p.evaluate(ORDEN_OK), "y las fotos siguen debajo de los textos")
        ok(_ed(pg, "E.doc.laminas[0].capas.some(c => c.rol === 'foto' && c.src && !c.oculto) && !E.doc.laminas[0].capas.some(c => c.rol === 'foto_fondo')"),
           "la foto de la portada pasa al hueco grande del estilo 2 (una sola)")
        # volver al paso 2: con el vídeo y sus imágenes
        pg.pulsar("#editor-capas .ce-volver-crear", "Cambiar tema")
        ok(pg.esperar("#crear-grafica .gc-propuesta-video", segundos=15), "«← Cambiar tema» vuelve con la propuesta del vídeo")
        ok(pg.p.locator("#crear-grafica .gc-video-base").input_value() == pid, "y con el vídeo elegido")
        ok(pg.p.evaluate("() => EditorCapas._asistente().piezas[1][1].plano") == "", "y lo elegido en cada parte")
        pg.p.keyboard.press("Escape")
        pg.sin_errores("crear desde un vídeo")
    finally:
        pg.cerrar()

    # el móvil: una publicación desde el vídeo
    pg = Pagina(_ConTacto(navegador), datos, ancho=390, alto=844, nombre="desde_video_movil")
    try:
        pg.js("document.documentElement.dataset.tema = 'claro';")
        pg.js(f"elegirCliente({json.dumps(cid)});")
        ok(pg.esperar(".seccion-graficas .crear-en-graficas", "+ Crear", 30), "en el móvil, «+ Crear»")
        pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
        pg.pulsar("#crear-grafica .gc-que-publicacion")
        pg.p.select_option("#crear-grafica .gc-video-base", pid)
        ok(pg.esperar("#crear-grafica .gc-desde-video", "imágenes con voz", 30), "elige el vídeo")
        pg.pulsar("#crear-grafica .gc-escribir", "desde el vídeo")
        ok(pg.esperar("#crear-grafica .gc-titular", segundos=60) and pg.p.locator("#crear-grafica .gc-titular").input_value().strip() != "",
           "la IA escribe el titular desde el vídeo, y se puede cambiar")
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth")
        ok(ancho <= 392, f"cabe a lo ancho del móvil ({ancho} px)")
        ok(_esperar_js(pg, "() => document.querySelectorAll('#crear-grafica .gc-estilo img').length >= 4", 90), "las miniaturas")
        pg.captura("desde-video-movil")
        pg.pulsar("#crear-grafica .gc-crear", "Crear")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return E && E.sencillo && E.doc.laminas.length === 1; }", 90),
           "la publicación desde el vídeo abre en el editor sencillo")
        ok(_ed(pg, "E.doc.laminas[0].capas.some(c => c.tipo === 'imagen' && c.src && !c.oculto)"), "con su foto del vídeo")
        pg.sin_errores("publicación desde un vídeo en el móvil")
    finally:
        pg.cerrar()

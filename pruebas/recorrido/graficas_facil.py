"""Recorrido de la rama graficas-facil: «+ Crear» en 3 pasos y el modo sencillo del editor.

Carrusel en el ordenador (tema oscuro): «+ Crear» → Carrusel → tema →
«Escríbelo por mí» (Claude simulado) → foto subida → estilo elegido en las
miniaturas → Crear → tocar un texto lo escribe y no lo mueve → «＋ Pegatina» →
«Otro estilo» y «Volver al estilo de antes» → «Añadir una imagen» → Guardar →
Descargar el ZIP → «Hacer también las historias» → «Edición avanzada» y volver.
Publicación en el móvil con el dedo (tema claro) e Historia en el ordenador
(tema claro), y las puertas avanzadas del primer paso.
"""
import io
import json

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401

CLAVE_MODO = "crearia.graficas.modo"


def _esperar_js(pg, expresion, segundos=20, arg=None):
    try:
        pg.p.wait_for_function(expresion, arg=arg, timeout=segundos * 1000)
        return True
    except Exception:                                        # noqa: BLE001
        return False


def _ed(pg, expresion):
    return pg.p.evaluate(f"() => {{ const E = EditorCapas._estado(); return JSON.parse(JSON.stringify({expresion})); }}")


def _png_de_prueba():
    from PIL import Image                                   # noqa: PLC0415
    salida = io.BytesIO()
    Image.new("RGB", (120, 90), (200, 80, 40)).save(salida, "PNG")
    return salida.getvalue()


class _ConTacto:
    """El navegador, con pantallas que se tocan con el dedo (para el móvil)."""

    def __init__(self, navegador):
        self.n = navegador

    def new_context(self, **kw):
        kw.update(has_touch=True, is_mobile=True)
        return self.n.new_context(**kw)


def _centro_de_capa(pg, rol):
    """El centro en pantalla del texto de la portada con ese papel."""
    return pg.p.evaluate("""rol => { const E = EditorCapas._estado();
      const c = E.doc.laminas[E.lamina].capas.find(x => x.tipo === 'texto' && x.rol === rol && !x.oculto);
      if (!c) return null;
      const n = E.lienzo.querySelector(`[data-c="${c.id}"]`);
      const r = n.getBoundingClientRect();
      return { id: c.id, x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 20), cx: c.x, cy: c.y }; }""", rol)


def _capa(pg, cid):
    return pg.p.evaluate("""id => { const E = EditorCapas._estado();
      const c = E.doc.laminas[E.lamina].capas.find(x => x.id === id); return c ? { x: c.x, y: c.y, txt: c.txt } : null; }""", cid)


def _se_lee(pg, selector):
    """El texto y su fondo no son del mismo color (sirve en los dos temas)."""
    return pg.p.evaluate("""sel => { const n = document.querySelector(sel); if (!n) return false;
      const c = getComputedStyle(n).color; let f = n, fondo = 'rgba(0, 0, 0, 0)';
      while (f && (fondo === 'rgba(0, 0, 0, 0)' || fondo === 'transparent')) { fondo = getComputedStyle(f).backgroundColor; f = f.parentElement; }
      const rgb = x => (x.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
      const [a, b] = [rgb(c), rgb(fondo)];
      return a.length === 3 && b.length === 3 && Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]) + Math.abs(a[2] - b[2]) > 200; }""", selector)


def _abrir_crear(pg, que):
    pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
    ok(pg.esperar(f"#crear-grafica .gc-que-{que}", segundos=20), f"«+ Crear» pregunta qué crear ({que})")
    pg.pulsar(f"#crear-grafica .gc-que-{que}")
    ok(pg.esperar("#crear-grafica .gc-crear", segundos=10), "el paso 2: de qué trata")


def _esperar_miniaturas(pg, cuantas=16, segundos=90):
    return _esperar_js(pg, f"() => document.querySelectorAll('#crear-grafica .gc-estilo img').length >= {cuantas}", segundos)


@escenario
def graficas_facil(navegador, datos):
    api = datos["api"]
    r, d = api.post("/api/clientes", {"nombre": "Cliente Fácil"})
    ok(r.status_code in (200, 201), "un proyecto para probar «+ Crear»")
    cid = d.get("id") or (d.get("cliente") or {}).get("id")

    # ------------------------------------------------------------ carrusel en el ordenador, tema oscuro
    pg = Pagina(navegador, datos, ancho=1500, alto=1000, nombre="facil")
    try:
        pg.js(f"try {{ localStorage.removeItem({json.dumps(CLAVE_MODO)}); }} catch (_) {{}}")
        pg.js(f"elegirCliente({json.dumps(cid)});")
        ok(pg.esperar(".seccion-graficas .crear-en-graficas", "+ Crear", 20), "la sección Gráficas tiene UNA puerta: «+ Crear»")
        ok(pg.p.locator(".seccion-graficas .nueva-en-capas, .seccion-graficas .lote-en-capas").count() == 0,
           "ya no salen «+ Diseño en capas» ni «+ Carruseles en lote» en la sección")
        ok(pg.esperar(".crear-grafica", "+ Crear gráfica", 5), "y en la cabecera del proyecto, «+ Crear gráfica»")
        ok(pg.esperar(".seccion-graficas .pista", "+ Crear", 5), "sin piezas, la pista dice «+ Crear»")

        pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
        ok(pg.esperar("#crear-grafica .gc-que-publicacion", "Publicación", 20), "paso 1: Publicación")
        ok(pg.esperar("#crear-grafica .gc-que-carrusel", "Carrusel", 2) and pg.esperar("#crear-grafica .gc-que-historia", "Historia", 2),
           "paso 1: Carrusel e Historia")
        for clase, texto in ((".lote-en-capas", "varios carruseles"), (".nueva-en-capas", "en blanco"), (".nueva-grafica", "clásico")):
            ok(pg.esperar(f"#crear-grafica .gc-avanzado {clase}", texto, 2), f"«Avanzado»: {texto}")
        pg.captura("facil-1-que")
        # Esc sin haber escrito nada cierra sin preguntar
        pg.p.keyboard.press("Escape")
        ok(_esperar_js(pg, "() => !document.getElementById('crear-grafica')", 5), "Esc cierra «+ Crear»")

        _abrir_crear(pg, "carrusel")
        ok(pg.esperar("#crear-grafica .gc-pasos li.actual", "De qué trata", 3), "los pasos dicen dónde estás")
        ok(pg.p.locator("#crear-grafica .gc-crear").is_disabled(), "«Crear» espera a que haya textos")
        ok(pg.esperar("#crear-grafica .gc-pronto", "Pronto: crear la imagen con IA", 3), "la imagen con IA se anuncia, sin botón muerto")
        ok(_esperar_miniaturas(pg, 4, 60), "las primeras miniaturas de estilo llegan")
        pg.p.fill("#crear-grafica .gc-tema", "5 errores al alquilar una consola para tu fiesta")
        pg.pulsar("#crear-grafica .gc-escribir", "Escríbelo por mí")
        ok(pg.esperar("#crear-grafica .gc-propuesta", "Textos listos", 60), "«Escríbelo por mí» trae los textos (Claude simulado)")
        tipos = pg.p.evaluate("() => EditorCapas._asistente().piezas.map(p => p[0])")
        ok(tipos[0] == "portada" and tipos[-1] == "cierre" and "cita" not in tipos, f"portada, cierre y sin citas: {tipos}")
        # la foto, subida
        pg.p.set_input_files("#gc-subir-foto", files=[{"name": "foto.png", "mimeType": "image/png", "buffer": _png_de_prueba()}])
        ok(pg.esperar("#crear-grafica .gc-foto-elegida img", segundos=20), "la foto subida se ve")
        ok(_esperar_miniaturas(pg, 16, 120), "las 16 miniaturas, con la foto")
        orden = pg.p.evaluate("() => EditorCapas._asistente().orden")
        ok(len(orden) == 16, "el orden trae los 16 estilos")
        pg.pulsar('#crear-grafica .gc-estilo[data-n="15"]')
        ok(pg.p.evaluate("() => EditorCapas._asistente().familia") == 15, "se elige el estilo en su miniatura")
        pg.js("document.documentElement.dataset.tema = 'oscuro';")
        pg.captura("facil-2-tema-oscuro")
        ok(_se_lee(pg, "#crear-grafica .gc-pregunta") and _se_lee(pg, "#crear-grafica .gc-estilo-nombre"), "en el tema oscuro, los textos se leen")
        ok(not pg.p.locator("#crear-grafica .gc-crear").is_disabled(), "«Crear» ya se puede pulsar")
        pg.pulsar("#crear-grafica .gc-crear", "Crear")
        ok(pg.esperar("#editor-capas.ce-sencillo .ce-lienzo [data-c]", segundos=60), "paso 3: el editor, en modo sencillo")
        ok(not pg.p.locator("#editor-capas .ce-izq").is_visible(), "sin el panel de capas")
        ok(pg.esperar("#editor-capas .ce-der h2", "Tu carrusel", 5), "el panel dice «Tu carrusel»")
        ok(pg.esperar("#editor-capas .ce-tira-cuenta", "Imagen 1 de", 5), "la tira habla de imágenes, no de láminas")
        ok(pg.esperar("#editor-capas .ce-estado", "Sin guardar", 5), "lo creado aún no está guardado")
        n = _ed(pg, "E.doc.laminas.length")
        ok(n >= 4, f"el carrusel trae sus {n} imágenes")
        ok(_ed(pg, "E.doc.laminas[0].familia") == 15, "con el estilo elegido")

        # tocar un texto lo escribe; arrastrarlo no lo mueve
        t = _centro_de_capa(pg, "titulo")
        ok(t is not None, "la portada tiene su titular")
        pg.p.mouse.move(t["x"], t["y"])
        pg.p.mouse.down()
        pg.p.mouse.move(t["x"] + 80, t["y"] + 60, steps=6)
        pg.p.mouse.up()
        pg.p.wait_for_timeout(300)
        c = _capa(pg, t["id"])
        ok(abs(c["x"] - t["cx"]) < 1e-6 and abs(c["y"] - t["cy"]) < 1e-6, "arrastrar el titular no lo mueve en el modo sencillo")
        ok(_ed(pg, "E.editando") is None, "y arrastrar no empieza a escribir")
        pg.p.mouse.click(t["x"], t["y"])
        ok(_esperar_js(pg, f"() => EditorCapas._estado().editando === {json.dumps(t['id'])}", 5), "un toque en el titular lo escribe")
        pg.p.keyboard.press("Control+End")
        pg.p.keyboard.type(" YA")
        pg.p.mouse.click(5, 300)                                  # fuera del lienzo, en el escenario
        ok(_esperar_js(pg, "() => !EditorCapas._estado().editando", 5), "tocar fuera termina")
        c = _capa(pg, t["id"])
        ok(c["txt"].endswith("YA") and abs(c["x"] - t["cx"]) < 1e-6, f"el texto cambió y sigue en su sitio ({c})")
        # el teclado tampoco mueve ni borra lo de la plantilla
        pg.p.keyboard.press("ArrowRight")
        pg.p.keyboard.press("ArrowDown")
        pg.p.wait_for_timeout(500)
        c = _capa(pg, t["id"])
        ok(abs(c["x"] - t["cx"]) < 1e-6 and abs(c["y"] - t["cy"]) < 1e-6, "las flechas no mueven el titular en el modo sencillo")
        foto = pg.p.evaluate("""() => { const E = EditorCapas._estado();
          const c = E.doc.laminas[0].capas.find(x => x.tipo === 'imagen' && x.rol);
          if (!c) return null; E.sel = [c.id]; return c.id; }""")
        if foto:
            pg.p.keyboard.press("Delete")
            pg.p.wait_for_timeout(300)
            ok(_capa(pg, foto) is not None, "Supr no borra la foto del diseño en el modo sencillo")
            pg.js("EditorCapas._estado().sel = [];")
        # el panel, con el texto elegido
        pg.p.mouse.click(t["x"], t["y"])
        pg.p.keyboard.press("Escape")
        ok(pg.esperar("#editor-capas .ce-der .ce-s-texto", segundos=5), "el panel enseña el texto elegido")

        # un adorno
        antes = len(_ed(pg, "E.doc.laminas[E.lamina].capas"))
        pg.pulsar("#editor-capas .ce-der .ce-anadir button", "Pegatina")
        ok(pg.esperar(".ce-menu-pegatinas button", "Nuevo", 3), "«＋ Pegatina» ofrece sus pegatinas")
        pg.pulsar(".ce-menu-pegatinas button", "Nuevo")
        ok(len(_ed(pg, "E.doc.laminas[E.lamina].capas")) == antes + 1, "la pegatina se añade")

        # otro estilo y volver
        pg.pulsar("#editor-capas .ce-s-otro-estilo", "Otro estilo")
        ok(pg.esperar(".ce-modal-estilos h2", "Elige otro estilo", 5), "«Otro estilo» abre la rejilla")
        ok(_esperar_js(pg, "() => document.querySelectorAll('.ce-modal-estilos .gc-estilo img').length >= 4", 60), "con miniaturas de tus textos")
        pg.captura("facil-3-otro-estilo")
        pg.pulsar('.ce-modal-estilos .gc-estilo[data-n="3"]')
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[0].familia === 3", 30), "se pone el estilo nuevo en todas")
        ok(_ed(pg, "E.doc.laminas.every(l => !l.tipo || l.familia === 3)"), "en todas las imágenes")
        ok(pg.esperar("#editor-capas .ce-s-volver-estilo", "Volver al estilo de antes", 5), "«Volver al estilo de antes» a la vista")
        pg.pulsar("#editor-capas .ce-s-volver-estilo")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[0].familia === 15", 5), "y vuelve al de antes")
        ok(pg.p.locator("#editor-capas .ce-s-volver-estilo").count() == 0, "el botón se va al volver")

        # añadir una imagen
        n = _ed(pg, "E.doc.laminas.length")
        pg.p.select_option("#editor-capas .ce-s-tipo", "pregunta")
        pg.pulsar("#editor-capas .ce-s-anadir")
        ok(_esperar_js(pg, f"() => EditorCapas._estado().doc.laminas.length === {n + 1}", 20), "«Añadir una imagen» suma una")
        ok(_ed(pg, "E.doc.laminas[E.lamina].tipo") == "pregunta", "del tipo elegido")
        ok(pg.p.locator("#editor-capas .ce-s-tipo option[value='cita']").count() == 0, "sin la Cita en el modo sencillo")

        # guardar y descargar
        ok(pg.p.locator("#editor-capas .ce-s-zip").is_disabled(), "descargar espera a guardar")
        pg.pulsar("#editor-capas .ce-s-guardar", "Guardar")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return !!E.piezaId && !E.guardando; }", 120), "se guarda")
        ok(_esperar_js(pg, "() => !document.querySelector('#editor-capas .ce-s-zip').disabled", 5), "y ya se puede descargar")
        with pg.p.expect_download(timeout=60000) as bajada:
            pg.pulsar("#editor-capas .ce-s-zip")
        ok(bajada.value.suggested_filename.endswith(".zip"), f"el ZIP baja ({bajada.value.suggested_filename})")

        # la historia, aparte
        pid = _ed(pg, "E.piezaId")
        pg.pulsar("#editor-capas .ce-s-historia", "historias")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return E && E.doc.formato === 'h916' && !E.piezaId; }", 60),
           "«Hacer también las historias» abre otra pieza en 9:16")
        ok(pg.esperar("#editor-capas.ce-sencillo", segundos=3), "también en modo sencillo")
        ok(pg.p.locator("#editor-capas .ce-s-historia").count() == 0, "una historia no ofrece otra historia")

        # edición avanzada y volver (se recuerda en el navegador)
        pg.pulsar("#editor-capas .ce-cambiar-modo", "Edición avanzada")
        ok(_esperar_js(pg, "() => !document.querySelector('#editor-capas').classList.contains('ce-sencillo')", 3), "«Edición avanzada» abre lo de siempre")
        ok(pg.p.locator("#editor-capas .ce-izq").is_visible(), "con el panel de capas")
        ok(pg.p.evaluate(f"() => localStorage.getItem({json.dumps(CLAVE_MODO)})") == "avanzado", "y se recuerda en el navegador")
        ok(_ed(pg, "Object.keys(E.doc).filter(k => /modo|sencillo/.test(k))") == [], "nunca en el documento")
        pg.pulsar("#editor-capas .ce-cambiar-modo", "Modo sencillo")
        ok(_esperar_js(pg, "() => document.querySelector('#editor-capas').classList.contains('ce-sencillo')", 3), "«Modo sencillo» vuelve")
        pg.pulsar("#editor-capas .ce-volver")                         # sin guardar: confirm aceptado
        ok(_esperar_js(pg, "() => !document.getElementById('editor-capas')", 5), "se cierra")
        ok(pg.esperar(".seccion-graficas .tarjeta-pieza", segundos=20), "el carrusel guardado sale en la lista")
        ok(api.get(f"/api/graficas/{cid}/piezas")[1]["piezas"][0]["id"] == pid, "y es la pieza guardada")
        pg.sin_errores("«+ Crear» un carrusel")

        # ------------------------------------------------------------ historia en el ordenador, tema claro
        pg.js("document.documentElement.dataset.tema = 'claro';")
        _abrir_crear(pg, "historia")
        ok(pg.p.locator("#crear-grafica .gc-tamano").input_value() == "h916", "la historia, en 9:16")
        pg.p.fill("#crear-grafica .gc-titular", "Tu fiesta con consola")
        pg.pulsar("#crear-grafica .gc-escribir", "Escríbelo por mí")
        ok(_esperar_js(pg, "() => { const S = EditorCapas._asistente(); return S && !S.escribiendo; }", 60), "escribe el titular")
        ok(pg.p.locator("#crear-grafica .gc-titular").input_value().strip() != "", "el titular queda escrito y se puede cambiar")
        ok(_se_lee(pg, "#crear-grafica .gc-pregunta") and _se_lee(pg, "#crear-grafica .gc-escribir"), "en el tema claro, los textos se leen")
        ok(_esperar_miniaturas(pg, 4, 60), "las miniaturas en vertical")
        pg.captura("facil-4-historia-claro")
        pg.pulsar("#crear-grafica .gc-crear", "Crear")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return E && E.doc.formato === 'h916' && E.sencillo; }", 60), "la historia abre en el editor sencillo")
        ok(pg.esperar("#editor-capas .ce-der h2", "Tu historia", 5), "«Tu historia»")
        ok(_ed(pg, "E.doc.laminas.length") == 1 and _ed(pg, "E.doc.laminas[0].capas.filter(c => c.enlace).length") == 0,
           "una sola imagen, sin la marca ni el «Desliza» de un carrusel")
        ok(pg.p.locator("#editor-capas .ce-tira").is_hidden(), "sin tira de imágenes")
        pg.pulsar("#editor-capas .ce-volver")
        ok(_esperar_js(pg, "() => !document.getElementById('editor-capas')", 5), "se cierra sin guardar")

        # las puertas avanzadas llevan a lo de siempre
        pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
        pg.pulsar("#crear-grafica .gc-avanzado .lote-en-capas")
        ok(pg.esperar(".dialogo h3", "Carruseles en lote", 5), "«Hacer varios a la vez» abre el lote de siempre")
        pg.p.keyboard.press("Escape")
        pg.p.wait_for_timeout(400)
        # una pieza sin estilo (empezada en blanco) no ofrece «Otro estilo»: rellenaría sus huecos
        # con textos de muestra (una cita, un descuento) que nadie escribió; lo dice
        pg.js(f"localStorage.setItem({json.dumps(CLAVE_MODO)}, 'sencillo');")
        pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
        pg.pulsar("#crear-grafica .gc-avanzado .nueva-en-capas", "Empezar en blanco")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return E && E.sencillo && E.lienzo.querySelector('[data-c]'); }", 40),
           "«Empezar en blanco», en el modo recordado (sencillo)")
        ok(_ed(pg, "E.doc.laminas.every(l => !l.familia)"), "una pieza sin estilo")
        ok(pg.esperar("#editor-capas .ce-s-sin-estilo", "Volver a montar", 5) and pg.p.locator("#editor-capas .ce-s-otro-estilo").count() == 0,
           "no ofrece «Otro estilo» y explica dónde recolocarla")
        pg.pulsar("#editor-capas .ce-volver")
        ok(_esperar_js(pg, "() => !document.getElementById('editor-capas')", 5), "se cierra")
        pg.sin_errores("«+ Crear» una historia")
        pg.js(f"try {{ localStorage.removeItem({json.dumps(CLAVE_MODO)}); }} catch (_) {{}}")
    finally:
        pg.cerrar()

    # ------------------------------------------------------------ publicación en el móvil, con el dedo
    pg = Pagina(_ConTacto(navegador), datos, ancho=390, alto=844, nombre="facil-movil")
    try:
        pg.js("document.documentElement.dataset.tema = 'claro';")
        pg.js(f"elegirCliente({json.dumps(cid)});")
        ok(pg.esperar(".seccion-graficas .crear-en-graficas", "+ Crear", 20), "en el móvil, «+ Crear»")
        _abrir_crear(pg, "publicacion")
        ancho = pg.p.evaluate("() => document.documentElement.scrollWidth")
        ok(ancho <= 392, f"el paso 2 cabe a lo ancho del móvil ({ancho} px)")
        pg.p.fill("#crear-grafica .gc-titular", "Alquila tu consola sin sorpresas")
        pg.p.fill("#crear-grafica .gc-apoyo", "Te la llevamos a casa")
        ok(_esperar_miniaturas(pg, 4, 60), "las miniaturas en el móvil")
        pg.captura("facil-5-movil-paso2")
        pg.pulsar("#crear-grafica .gc-crear", "Crear")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return E && E.sencillo && E.lienzo && E.lienzo.querySelector('[data-c]'); }", 60),
           "la publicación abre en el editor sencillo")
        ok(pg.esperar("#editor-capas .ce-der h2", "Tu publicación", 5), "«Tu publicación»")
        pg.p.wait_for_timeout(500)
        t = _centro_de_capa(pg, "titulo")
        pg.p.touchscreen.tap(t["x"], t["y"])
        ok(_esperar_js(pg, f"() => EditorCapas._estado().editando === {json.dumps(t['id'])}", 5), "con el dedo, un toque escribe el titular")
        c = _capa(pg, t["id"])
        ok(abs(c["x"] - t["cx"]) < 1e-6 and abs(c["y"] - t["cy"]) < 1e-6, "y no lo mueve")
        pg.captura("facil-6-movil-editor")
        ancho = pg.p.evaluate("() => document.getElementById('editor-capas').scrollWidth")
        ok(ancho <= 392, f"el editor sencillo cabe a lo ancho del móvil ({ancho} px)")
        pg.p.keyboard.type("!")
        pg.pulsar("#editor-capas .ce-s-guardar", "Guardar")
        ok(_esperar_js(pg, "() => { const E = EditorCapas._estado(); return !!E.piezaId && !E.guardando && !E.editando; }", 60),
           "se guarda en el móvil " + str(_ed(pg, "[E.piezaId, E.guardando, E.editando, E.aviso.textContent, E.estado.textContent]")))
        ok(pg.p.locator("#editor-capas .ce-s-png").is_enabled() and pg.p.locator("#editor-capas .ce-s-historia").count() == 1,
           "y ofrece descargar y hacer también la historia")
        pg.pulsar("#editor-capas .ce-volver")
        pg.sin_errores("«+ Crear» en el móvil")
    finally:
        pg.cerrar()

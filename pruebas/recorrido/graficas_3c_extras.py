"""Recorrido de la rama graficas-3c-extras: lo nuevo del carrusel, pulsando como una persona.

La familia Gamer y los tipos nuevos desde «＋ Lámina», el botón «Tachado»,
«＋ Icono» (y cambiarlo), «＋ Pegatina» (el globo), «＋ QR» (con un número que no
vale y luego uno que sí), «＋ De un vídeo» (los planos de un vídeo del
proyecto), guardar y «Hacer también las historias», y «+ Carruseles en lote»
desde la sección de Gráficas del proyecto.
"""
import base64
import io
import json

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401

QUIETO = """() => { const e = window.EditorCapas && EditorCapas._estado();
  return !!e && !e.arrastre && !e.guardando && Object.values(e.letras).every(v => v !== 'cargando'); }"""


def _esperar_js(pg, expresion, segundos=20, arg=None):
    try:
        pg.p.wait_for_function(expresion, arg=arg, timeout=segundos * 1000)
        return True
    except Exception:                                        # noqa: BLE001
        return False


def _ed(pg, expresion):
    return pg.p.evaluate(f"() => {{ const E = EditorCapas._estado(); return JSON.parse(JSON.stringify({expresion})); }}")


def _capas(pg):
    return _ed(pg, "E.doc.laminas[E.lamina].capas")


def _png_de_prueba():
    from PIL import Image                                   # noqa: PLC0415
    salida = io.BytesIO()
    Image.new("RGB", (64, 36), (40, 160, 90)).save(salida, "PNG")
    return salida.getvalue()


@escenario
def graficas_3c_extras(navegador, datos):
    api = datos["api"]
    r, d = api.post("/api/clientes", {"nombre": "Cliente Extras"})
    ok(r.status_code in (200, 201), "un proyecto para probar los extras del carrusel")
    cid = d.get("id") or (d.get("cliente") or {}).get("id")
    # una imagen ya en Gráficas: la que «devuelve» el plano del vídeo simulado
    r = api.s.post(api.base + f"/api/graficas/{cid}/imagen", files={"imagen": ("plano.png", _png_de_prueba(), "image/png")}, timeout=30)
    ok(r.status_code == 201, "una imagen de prueba en el proyecto")
    imagen = r.json().get("nombre", "")

    pg = Pagina(navegador, datos, ancho=1600, alto=1100, nombre="extras")
    try:
        pg.js(f"elegirCliente({json.dumps(cid)});")
        ok(pg.esperar(".seccion-graficas .crear-en-graficas", segundos=20), "el proyecto ofrece «+ Crear»")
        # el editor, con un vídeo del proyecto simulado (sus planos) para «Foto de un vídeo»
        pg.p.route("**/imagen/de-plano", lambda ruta: ruta.fulfill(status=201, content_type="application/json",
                                                                    body=json.dumps({"nombre": imagen})))
        pg.js(f"""abrirEditorCapas({json.dumps(cid)}, null, {{
            videos: () => [{{ id: 'v-prueba', nombre: 'Vídeo de prueba' }}],
            planos: async () => [{{ sid: 's1', texto: 'Plano 1' }}, {{ sid: 's2', texto: 'Plano 2' }}],
            miniatura: (img) => {{ img.src = 'data:image/png;base64,{base64.b64encode(_png_de_prueba()).decode()}'; }} }});""")
        ok(pg.esperar("#editor-capas .ce-lienzo [data-c]", segundos=40), "se abre el editor")
        _esperar_js(pg, QUIETO)

        # 1. FAMILIA GAMER Y UN TIPO NUEVO
        pg.pulsar(".ce-der button", "Partir un texto en láminas")
        pg.p.locator(".ce-partir-texto").fill("5 errores al alquilar una consola\n\nNo probar los mandos\nPruébalos antes.")
        pg.pulsar(".ce-modal button", "Hacer el carrusel")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas.length === 3", 30), "un carrusel corto para empezar")
        pg.p.select_option(".ce-der select[aria-label='Familia del carrusel']", "16")
        pg.pulsar(".ce-der button", "y todas con esta familia")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas.every(l => l.familia === 16)", 40), "todas con la familia Gamer")
        ok(any(c.get("nombre", "").startswith("Esquina") for c in _ed(pg, "E.doc.laminas[1].capas")), "con sus esquinas")
        pg.p.locator(".ce-tira-lamina").nth(1).click()
        _esperar_js(pg, "() => EditorCapas._estado().lamina === 1", 3)
        pg.pulsar(".ce-tira-acciones button", "Lámina")
        for tipo in ("Mito / Realidad", "Pregunta", "Ranking", "Checklist", "Comparativa", "Precio / oferta"):
            ok(pg.esperar(".ce-tira-menu button", tipo, 3), f"«＋ Lámina» ofrece «{tipo}»")
        pg.pulsar(".ce-tira-menu button", "Precio / oferta")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas.some(l => l.tipo === 'precio')", 30), "«Precio / oferta» añade su lámina")
        antes = next((c for c in _capas(pg) if c.get("rol") == "precio_antes"), None)
        ok(antes is not None and antes.get("tachado") is True, "con el precio de antes tachado")

        # 2. EL BOTÓN «TACHADO»
        _esperar_js(pg, QUIETO)
        pg.p.locator(f".ce-capas [data-id='{antes['id']}'] .ce-capa-nombre").click()
        ok(pg.esperar(".ce-der button[title='Tachado'][aria-pressed='true']", segundos=3), "el texto tachado tiene su botón «Tachado» pulsado")
        pg.p.locator(".ce-der button[title='Tachado']").click()
        ok(_esperar_js(pg, f"() => !EditorCapas._estado().doc.laminas[EditorCapas._estado().lamina].capas.find(c => c.id === '{antes['id']}').tachado", 3),
           "y al pulsarlo, se quita")
        pg.p.keyboard.press("Control+z")
        ok(_esperar_js(pg, f"() => EditorCapas._estado().doc.laminas[EditorCapas._estado().lamina].capas.find(c => c.id === '{antes['id']}').tachado === true", 3),
           "Ctrl+Z lo vuelve a tachar")
        pg.p.keyboard.press("Escape")

        # 3. ＋ ICONO
        pg.pulsar(".ce-anadir button", "Icono")
        ok(pg.esperar(".ce-modal .ce-icono", segundos=10), "«＋ Icono» enseña los iconos")
        ok(pg.p.locator(".ce-modal .ce-icono").count() >= 50, "más de 50, con su nombre")
        pg.pulsar(".ce-modal .ce-icono", "Estrella")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[EditorCapas._estado().lamina].capas.some(c => c.tipo === 'icono' && c.icono === 'star')", 5),
           "la estrella entra en la lámina")
        ok(pg.esperar(".ce-lienzo [data-c] img[src^='data:image/svg+xml']", segundos=5), "y se pinta en el lienzo")
        ok(pg.esperar(".ce-der h2", "Icono: Estrella", 3), "su panel dice qué icono es")
        pg.pulsar(".ce-der button", "Cambiar el icono")
        pg.pulsar(".ce-modal .ce-icono", "Trofeo")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[EditorCapas._estado().lamina].capas.some(c => c.icono === 'trophy')", 5),
           "«Cambiar el icono» lo cambia")

        # 4. ＋ PEGATINA: EL GLOBO
        pg.pulsar(".ce-anadir button", "Pegatina")
        ok(pg.esperar(".ce-menu-pegatinas button", "Globo de diálogo", 3), "«＋ Pegatina» ofrece el globo, «Nuevo», «Guárdalo» y la flecha")
        pg.pulsar(".ce-menu-pegatinas button", "Globo de diálogo")
        ok(_esperar_js(pg, "() => EditorCapas._estado().sel.length === 2", 3), "el globo y su pico entran elegidos juntos")

        # 5. ＋ QR
        pg.pulsar(".ce-anadir button", "QR")
        ok(pg.esperar(".ce-modal h2", "Poner un QR", 3), "«＋ QR» pregunta qué lleva")
        pg.p.locator(".ce-modal .ce-qr-valor").first.fill("llámame")
        pg.pulsar(".ce-modal button", "Hacer el QR")
        ok(pg.esperar(".ce-modal .ce-pista.malo", "número", 10), "un WhatsApp que no es un número se explica")
        pg.p.locator(".ce-modal .ce-qr-valor").first.fill("999 888 777")
        pg.pulsar(".ce-modal button", "Hacer el QR")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[EditorCapas._estado().lamina].capas.some(c => c.tipo === 'imagen' && c.nombre === 'QR' && c.src)", 20),
           "el QR entra como una capa")
        ok(any("wa.me/51999888777" in a for a in pg.avisos()) or pg.esperar(".ce-aviso", "wa.me/51999888777", 3),
           "y dice a dónde lleva")

        # 6. ＋ DE UN VÍDEO (una foto ya pagada de un vídeo del proyecto)
        pg.pulsar(".ce-anadir button", "De un vídeo")
        ok(pg.esperar(".ce-modal .ce-plano", segundos=10), "con un solo vídeo, enseña sus planos directamente")
        pg.p.locator(".ce-modal .ce-plano").first.click()
        ok(_esperar_js(pg, f"() => EditorCapas._estado().doc.laminas[EditorCapas._estado().lamina].capas.some(c => c.tipo === 'imagen' && c.src === '{imagen}')", 20),
           "el plano elegido entra como foto, gratis")

        # 7. GUARDAR Y «HACER TAMBIÉN LAS HISTORIAS»
        pg.p.keyboard.press("Escape")
        _esperar_js(pg, QUIETO)
        pg.p.mouse.click(5, 5)
        pg.p.keyboard.press("Escape")
        pg.pulsar(".ce-der button", "Hacer también las historias")
        ok(any("Guarda primero" in a for a in pg.avisos()) or pg.esperar(".ce-aviso", "Guarda primero", 3),
           "sin guardar, pide guardar antes")
        pg.p.locator(".ce-barra .ce-primario").click()
        ok(pg.esperar(".ce-estado", "Guardado", 90), "se guarda el carrusel")
        original = _ed(pg, "E.piezaId")
        ok(_ed(pg, "E.doc.nombre") == "5 errores al alquilar una consola", "sin nombre, se llama como el titular de la portada (no el de la lámina abierta)")
        pg.pulsar(".ce-der button", "Hacer también las historias")
        ok(_esperar_js(pg, "() => EditorCapas._estado().doc.formato === 'h916' && !EditorCapas._estado().piezaId", 60),
           "se abren las historias en 9:16, como pieza nueva sin guardar")
        ok(_ed(pg, "E.doc.nombre") == "5 errores al alquilar una consola (historias)", "con «(historias)» en el nombre")
        pg.p.locator(".ce-barra .ce-primario").click()
        ok(pg.esperar(".ce-estado", "Guardado", 90), "y se guardan aparte")
        _r, lista = api.get(f"/api/graficas/{cid}/piezas")
        ids = [p["id"] for p in lista.get("piezas", [])]
        ok(original in ids and _ed(pg, "E.piezaId") in ids and _ed(pg, "E.piezaId") != original, "las dos piezas están en la lista")
        pg.captura("extras_editor")
        pg.sin_errores("los extras del editor")
    finally:
        pg.cerrar()

    # 8. CARRUSELES EN LOTE
    pg = Pagina(navegador, datos, ancho=1400, alto=1000, nombre="extras_lote")
    try:
        pg.js(f"elegirCliente({json.dumps(cid)});")
        ok(pg.esperar(".seccion-graficas .crear-en-graficas", segundos=20), "«+ Crear» en el proyecto (el lote, en su «Avanzado»)")
        _r, lista = api.get(f"/api/graficas/{cid}/piezas")
        antes = len(lista.get("piezas", []))
        pg.pulsar(".seccion-graficas .crear-en-graficas", "+ Crear")
        pg.pulsar("#crear-grafica .gc-avanzado .lote-en-capas", "varios carruseles")
        ok(pg.esperar(".dialogo h3", "Carruseles en lote", 5), "pregunta los carruseles")
        pg.p.locator(".dialogo textarea").fill("Familia: Gamer\nTorneo de fin de mes\n\nInscríbete\nCupos limitados.\n---\n"
                                               "Tres juegos para fiestas\n\n- Uno\n- Dos\n- Tres")
        pg.p.select_option(".dialogo select >> nth=0", "15")
        pg.pulsar(".dialogo button[type=submit]", "Hacer los carruseles")
        ok(_esperar_js(pg, "() => (window.__avisos || []).some(a => /2 carruseles hechos/.test(a))", 120), "hace los 2 carruseles con barra")
        _r, lista = api.get(f"/api/graficas/{cid}/piezas")
        nuevas = [p for p in lista.get("piezas", [])]
        ok(len(nuevas) == antes + 2, f"y salen en la lista ({len(nuevas)} piezas, antes {antes})")
        ok(pg.esperar(".tarjeta-pieza", "Torneo de fin de mes", 15), "con su nombre en la tarjeta")
        pg.captura("extras_lote")
        pg.sin_errores("los carruseles en lote")
    finally:
        pg.cerrar()

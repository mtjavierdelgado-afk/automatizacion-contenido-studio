"""Recorrido de la rama graficas-2-editor: el editor con capas de Gráficas.

Abre una pieza de antes «en capas» (solo si sale igual), la pantalla pinta lo
mismo que el PNG, mover, asas, girar, imán, varias a la vez, deshacer, escribir
en el lienzo, otro tamaño, «Volver a montar», guardar, el 409 de otra pestaña,
«Ver la versión anterior», una pieza nueva en capas y el móvil.
"""
import base64
import io
import json
import os
import sys

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401

AQUI = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(AQUI, "pasos"))


def _doc(pg):
    return pg.p.evaluate("() => JSON.parse(JSON.stringify(EditorCapas._estado().doc))")


def _capas(pg):
    return _doc(pg)["laminas"][0]["capas"]


def _por_rol(pg, rol):
    return next((c for c in _capas(pg) if c["rol"] == rol), None)


def _centro(pg, selector):
    caja = pg.p.locator(selector).first.bounding_box()
    return caja["x"] + caja["width"] / 2, caja["y"] + caja["height"] / 2


def _arrastrar(pg, x0, y0, x1, y1, pasos=6, tecla=None):
    pg.p.mouse.move(x0, y0)
    if tecla:
        pg.p.keyboard.down(tecla)
    pg.p.mouse.down()
    pg.p.mouse.move(x1, y1, steps=pasos)
    pg.p.mouse.up()
    if tecla:
        pg.p.keyboard.up(tecla)
    pg.p.wait_for_timeout(150)


def _esperar_js(pg, expresion, segundos=20):
    try:
        pg.p.wait_for_function(expresion, timeout=segundos * 1000)
        return True
    except Exception:                                        # noqa: BLE001
        return False


def _png_de_uri(uri):
    return base64.b64decode(uri.split(",", 1)[1])


@escenario
def graficas_2_editor(navegador, datos):
    api = datos["api"]
    r, d = api.post("/api/clientes", {"nombre": "Cliente Capas"})
    ok(r.status_code in (200, 201), "un proyecto para probar el editor con capas")
    cid = d.get("id") or (d.get("cliente") or {}).get("id")
    r, pieza = api.post(f"/api/graficas/{cid}/piezas", {
        "plantilla": 3, "formato": "v45", "nombre": "Pieza de antes",
        "textos": {"kicker": "Novedad", "titulo": "Sabor que te hace volver", "cta": "Reserva ya"}})
    ok(r.status_code in (200, 201) and pieza.get("id"), "una pieza hecha con el editor de siempre")
    pid = pieza.get("id")
    jpg_antes = api.s.get(api.base + f"/api/graficas/{cid}/piezas/{pid}/fichero.jpg", timeout=30).content

    pg = Pagina(navegador, datos, ancho=1700, alto=1650, nombre="editor_capas")
    pg.js(f"elegirCliente({json.dumps(cid)});")
    ok(pg.esperar(".tarjeta-pieza .abrir-en-capas", "Abrir en capas", 20), "la pieza ofrece «Abrir en capas»")
    ok(pg.esperar(".seccion-graficas .nueva-en-capas", segundos=5), "y el proyecto, «+ Diseño en capas»")
    pg.pulsar(".tarjeta-pieza .abrir-en-capas", "Abrir en capas")
    ok(pg.esperar("#editor-capas .ce-lienzo [data-c]", segundos=40), "se abre el editor con las capas")
    ok(pg.esperar("#editor-capas .ce-migra", "versión anterior se queda intacta", 5), "y avisa de que la pieza de antes no se toca")
    _r, lista = api.get(f"/api/graficas/{cid}/piezas")
    ok(not (lista.get("piezas") or [{}])[0].get("en_capas"), "abrirla no guarda nada")
    ok(_esperar_js(pg, "() => { const i = document.querySelector('.ce-vista-img'); return i && i.complete && i.naturalWidth > 0; }", 40),
       "la vista final del servidor se pinta sola")
    ok(_esperar_js(pg, "() => Object.values(EditorCapas._estado().letras).every(v => v !== 'cargando')", 20),
       "las letras llegan del Studio")

    # 1. LA PANTALLA PINTA LO MISMO QUE EL PNG (a tamaño real: zoom 100 %)
    pg.p.evaluate("() => { EditorCapas._estado().zoom = 1; window.dispatchEvent(new Event('resize')); }")
    pg.p.wait_for_timeout(800)
    ancho = pg.p.evaluate("() => document.querySelector('.ce-lienzo').clientWidth")
    ok(ancho == 1080, f"a zoom 100 % el lienzo mide lo que la pieza ({ancho} px)")
    pantalla = pg.p.locator(".ce-lienzo").screenshot()
    r, vista = api.post(f"/api/graficas/{cid}/capas/vista", {"doc": dict(_doc(pg), origen={}), "lamina": 0})
    servidor = _png_de_uri(vista.get("img", "data:,"))
    try:
        from PIL import Image                                # noqa: PLC0415
        import graficas_capas as C                           # noqa: PLC0415
        a = Image.open(io.BytesIO(pantalla)).convert("RGB")
        b = Image.open(io.BytesIO(servidor)).convert("RGB").resize(a.size)
        buf_a, buf_b = io.BytesIO(), io.BytesIO()
        a.save(buf_a, "PNG")
        b.save(buf_b, "PNG")
        visible = C.diferencia_visible(buf_a.getvalue(), buf_b.getvalue())
        ok(visible < 0.01, f"la pantalla y el PNG salen iguales (cambia un {visible * 100:.3f} % de lo que se ve)")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"comparar la pantalla con el PNG: {fallo}")
    ok(isinstance(vista.get("lineas"), dict) and vista["lineas"], "la vista dice cuántas líneas ocupa cada texto")
    pg.p.locator(".ce-barra button[title='Que quepa entero']").click()
    pg.p.wait_for_timeout(400)

    # 2. ELEGIR Y MOVER, CON IMÁN; DESHACER Y REHACER
    titulo = _por_rol(pg, "titulo")
    ok(titulo is not None, "el titular es una capa")
    sel_t = f".ce-lienzo [data-c='{titulo['id']}']"
    x, y = _centro(pg, sel_t)
    pg.p.mouse.click(x, y)
    ok(pg.esperar(".ce-marcas .ce-elegida", segundos=3), "pulsar una capa la elige (con su recuadro)")
    ok(pg.esperar(".ce-der h2", "Texto", 3), "y enseña sus propiedades")
    antes = _por_rol(pg, "titulo")
    _arrastrar(pg, x, y, x + 60, y + 40)
    despues = _por_rol(pg, "titulo")
    ok(despues["x"] > antes["x"] + 1 and despues["y"] > antes["y"] + 1, "arrastrarla la mueve")
    ok(pg.esperar(".ce-estado", "Sin guardar", 3), "y avisa de que hay cambios sin guardar")
    pg.p.keyboard.press("Control+z")
    vuelta = _por_rol(pg, "titulo")
    ok(abs(vuelta["x"] - antes["x"]) < 1e-6 and abs(vuelta["y"] - antes["y"]) < 1e-6, "Ctrl+Z la devuelve a su sitio")
    pg.p.keyboard.press("Control+y")
    ok(abs(_por_rol(pg, "titulo")["x"] - despues["x"]) < 1e-6, "Ctrl+Y la vuelve a mover")
    pasos = pg.p.evaluate("() => EditorCapas._estado().hist.length")
    pg.p.mouse.click(x + 60, y + 40)
    ok(pg.p.evaluate("() => EditorCapas._estado().hist.length") == pasos, "pulsar sin mover no cuenta como un cambio")
    # el imán: cerca del centro se pega al centro
    lienzo = pg.p.locator(".ce-lienzo").bounding_box()
    k = pg.p.locator(".ce-marcas .ce-elegida").bounding_box()
    cx_capa = k["x"] + k["width"] / 2
    objetivo = lienzo["x"] + lienzo["width"] / 2 + 3
    sx, sy = _centro(pg, ".ce-marcas .ce-elegida")
    pg.p.mouse.move(sx, sy)
    pg.p.mouse.down()
    pg.p.mouse.move(sx + (objetivo - cx_capa), sy + 1, steps=8)
    guias = pg.p.locator(".ce-guia").count()
    pg.p.mouse.up()
    k = pg.p.locator(".ce-marcas .ce-elegida").bounding_box()
    ok(guias > 0, "al arrastrar salen las guías")
    ok(abs(k["x"] + k["width"] / 2 - (lienzo["x"] + lienzo["width"] / 2)) < 1.5, "y el imán la pega al centro")
    # flechas
    x_antes = _por_rol(pg, "titulo")["x"]
    pg.p.keyboard.press("ArrowRight")
    pg.p.keyboard.press("Shift+ArrowRight")
    pg.p.wait_for_timeout(600)
    ok(abs((_por_rol(pg, "titulo")["x"] - x_antes) / 100 * 1080 - 11) < 0.05, "las flechas mueven 1 px y 10 con Mayús")
    # las teclas del editor no llegan a los atajos del Studio (árbitro, 12-11)
    pg.p.evaluate("() => { window.__teclasStudio = 0; document.addEventListener('keydown', () => { window.__teclasStudio++; }); }")
    for tecla in ("ArrowLeft", "Control+s", "Escape", " "):
        pg.p.keyboard.press(tecla)
    pg.p.locator(".ce-der input, .ce-der textarea").first.press("Escape")
    ok(pg.p.evaluate("() => window.__teclasStudio") == 0, "las teclas del editor no llegan a los atajos del Studio")
    pg.p.wait_for_timeout(500)
    pg.p.mouse.click(*_centro(pg, sel_t))

    # 3. ASAS: la esquina de un texto cambia la letra; el lado, el ancho
    tam0, w0 = _por_rol(pg, "titulo")["tam"], _por_rol(pg, "titulo")["w"]
    ax, ay = _centro(pg, ".ce-asa-se")
    _arrastrar(pg, ax, ay, ax + 40, ay + 20)
    t = _por_rol(pg, "titulo")
    ok(t["tam"] > tam0 * 1.03 and t["w"] > w0, f"la esquina de un texto agranda la letra y la caja ({tam0} -> {t['tam']}, {w0} -> {t['w']})")
    ax, ay = _centro(pg, ".ce-asa-e")
    tam1, w1 = t["tam"], t["w"]
    _arrastrar(pg, ax, ay, ax - 50, ay)
    t = _por_rol(pg, "titulo")
    ok(t["w"] < w1 and abs(t["tam"] - tam1) < 1e-6, "el lado de un texto solo cambia el ancho")

    # 4. GIRAR (con Mayús, de 15 en 15)
    gx, gy = _centro(pg, ".ce-girar")
    k = pg.p.locator(".ce-marcas .ce-elegida").bounding_box()
    _arrastrar(pg, gx, gy, k["x"] + k["width"] + 80, k["y"] + k["height"] / 2, tecla="Shift")
    giro = _por_rol(pg, "titulo")["giro"]
    ok(giro and abs(giro / 15 - round(giro / 15)) < 1e-6, f"girar con Mayús va de 15 en 15° ({giro}°)")

    # 5. ESCRIBIR EN EL LIENZO (doble clic)
    x, y = _centro(pg, ".ce-marcas .ce-elegida")
    pg.p.mouse.dblclick(x, y)
    ok(pg.esperar(".ce-lienzo .ce-escribiendo", segundos=3), "doble clic en un texto deja escribirlo ahí")
    pg.p.keyboard.type("Hola de nuevo")
    pg.p.keyboard.press("Control+Enter")
    ok(_por_rol(pg, "titulo")["txt"] == "Hola de nuevo", "lo escrito queda en la capa")
    pg.p.mouse.dblclick(*_centro(pg, ".ce-marcas .ce-elegida"))
    pg.p.keyboard.type("se descarta")
    pg.p.keyboard.press("Escape")
    ok(_por_rol(pg, "titulo")["txt"] == "Hola de nuevo", "Escape deja el texto como estaba")
    # una letra o una foto que llega mientras se escribe repinta el lienzo: no corta la edición (árbitro, 12-11)
    pg.p.mouse.dblclick(*_centro(pg, ".ce-marcas .ce-elegida"))
    pg.p.keyboard.type("ABC")
    pg.p.evaluate("() => window.dispatchEvent(new Event('resize'))")
    pg.p.wait_for_timeout(300)
    pg.p.keyboard.type("XYZ")
    ok(pg.p.evaluate("() => EditorCapas._estado().editando") is not None, "repintar mientras se escribe no corta la edición")
    pg.p.keyboard.press("Control+Enter")
    ok(_por_rol(pg, "titulo")["txt"] == "ABCXYZ", f"y no se pierde lo escrito ({_por_rol(pg, 'titulo')['txt']!r})")
    pg.p.keyboard.press("Control+z")
    ok(_por_rol(pg, "titulo")["txt"] == "Hola de nuevo", "Ctrl+Z vuelve al texto de antes")
    pg.p.keyboard.press("Escape")
    ok(pg.p.locator(".ce-marcas .ce-elegida").count() == 0, "Escape quita la selección")
    ok(pg.p.locator("#editor-capas").count() == 1, "y no cierra el editor")

    # 6. AÑADIR, VARIAS A LA VEZ, ALINEAR, DUPLICAR Y BORRAR
    n0 = len(_capas(pg))
    pg.pulsar(".ce-anadir button", "Rectángulo")
    pg.pulsar(".ce-anadir button", "Círculo")
    pg.pulsar(".ce-anadir button", "Texto")
    ok(len(_capas(pg)) == n0 + 3, "«＋ Rectángulo», «＋ Círculo» y «＋ Texto» añaden capas")
    nuevas = _capas(pg)[-3:]
    circulo = nuevas[1]
    ok(abs(circulo["w"] / 100 * 1080 - circulo["h"] / 100 * 1350) < 1, "el círculo sale redondo")
    pg.p.keyboard.press("Control+a")
    elegidas = pg.p.evaluate("() => EditorCapas._estado().sel.length")
    ok(elegidas >= 3, f"Ctrl+A elige todas las que se pueden mover ({elegidas})")
    pg.p.keyboard.press("Escape")
    # recuadro sobre el rectángulo y el círculo
    pg.p.evaluate("ids => { const e = EditorCapas._estado(); e.sel = ids; }", [nuevas[0]["id"], nuevas[1]["id"]])
    pg.p.locator(f".ce-capas [data-id='{nuevas[1]['id']}'] .ce-capa-nombre").click(modifiers=["Shift"])
    pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}'] .ce-capa-nombre").click()
    pg.p.locator(f".ce-capas [data-id='{nuevas[1]['id']}'] .ce-capa-nombre").click(modifiers=["Shift"])
    ok(pg.esperar(".ce-der h2", "2 capas elegidas", 3), "Mayús en la lista elige varias")
    pg.pulsar(".ce-der button", "Izquierda")
    cs = {c["id"]: c for c in _capas(pg)}
    ok(abs(cs[nuevas[0]["id"]]["x"] - cs[nuevas[1]["id"]]["x"]) < 0.01, "«Izquierda» las alinea entre ellas")
    pg.p.keyboard.press("Control+d")
    ok(len(_capas(pg)) == n0 + 5, "Ctrl+D duplica las dos")
    pg.p.keyboard.press("Delete")
    ok(len(_capas(pg)) == n0 + 3, "Supr borra las elegidas")
    # el recuadro con el ratón, desde un hueco del escenario
    esc = pg.p.locator(".ce-escenario").bounding_box()
    lienzo = pg.p.locator(".ce-lienzo").bounding_box()
    _arrastrar(pg, esc["x"] + 4, esc["y"] + 4, lienzo["x"] + lienzo["width"] - 2, lienzo["y"] + lienzo["height"] - 2)
    ok(pg.p.evaluate("() => EditorCapas._estado().sel.length") >= 3, "arrastrar en un hueco elige con un recuadro")
    pg.p.keyboard.press("Escape")

    # 7. OCULTAR, BLOQUEAR, ORDEN Y NOMBRE
    fila = pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}']")
    fila.locator("button[title='Ocultar']").click()
    ok(pg.p.locator(f".ce-lienzo [data-c='{nuevas[0]['id']}']").count() == 0, "«Ocultar» lo quita del lienzo")
    pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}'] button[title='Enseñar']").click()
    ok(pg.p.locator(f".ce-lienzo [data-c='{nuevas[0]['id']}']").count() == 1, "y «Enseñar» lo vuelve a poner")
    pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}'] .ce-capa-nombre").click()
    pg.pulsar(".ce-orden button", "Al fondo")
    ok(_capas(pg)[0]["id"] == nuevas[0]["id"], "«Al fondo» la pone la primera")
    pg.pulsar(".ce-orden button", "Al frente")
    ok(_capas(pg)[-1]["id"] == nuevas[0]["id"], "«Al frente» la pone la última")
    pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}'] .ce-capa-nombre").dblclick()
    pg.p.locator(".ce-renombrar").fill("Banda de color")
    pg.p.keyboard.press("Enter")
    ok(next(c for c in _capas(pg) if c["id"] == nuevas[0]["id"])["nombre"] == "Banda de color", "doble clic en la lista la renombra")
    pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}'] .ce-capa-nombre").dblclick()
    pg.p.locator(".ce-renombrar").fill("NO GUARDAR")
    pg.p.keyboard.press("Escape")
    ok(next(c for c in _capas(pg) if c["id"] == nuevas[0]["id"])["nombre"] == "Banda de color", "Escape al renombrar no cambia el nombre")

    # 8. PROPIEDADES CON LOS COLORES DEL KIT
    pg.p.locator(f".ce-capas [data-id='{nuevas[0]['id']}'] .ce-capa-nombre").click()
    pg.p.locator(".ce-der .ce-muestra[aria-label='Color: Acento']").first.click()
    ok(next(c for c in _capas(pg) if c["id"] == nuevas[0]["id"])["relleno"]["color"] == "kit:acento",
       "un color del Kit se guarda como color del Kit")
    pg.p.locator(".ce-der .ce-casilla", has_text="Con sombra").first.locator("input").check()
    ok(next(c for c in _capas(pg) if c["id"] == nuevas[0]["id"])["sombra"], "«Con sombra» le pone sombra")

    # 9. OTRO TAMAÑO: los círculos siguen redondos y avisa de lo que se sale
    pg.p.keyboard.press("Escape")
    pg.p.select_option(".ce-der select[aria-label='Tamaño']", "h916")
    circ = next(c for c in _capas(pg) if c["id"] == circulo["id"])
    ok(abs(circ["w"] / 100 * 1080 - circ["h"] / 100 * 1920) < 1, "en 9:16 el círculo sigue redondo")
    ok(_esperar_js(pg, "() => document.querySelector('.ce-lienzo').clientHeight / document.querySelector('.ce-lienzo').clientWidth > 1.7", 5),
       "y el lienzo toma la forma nueva")

    # 10. VOLVER A MONTAR
    antes_de_montar = _doc(pg)
    pg.p.select_option(".ce-der select[aria-label='Plantilla']", "11")
    pg.pulsar(".ce-der button", "Volver a montar")
    ok(_esperar_js(pg, "() => EditorCapas._estado().doc.laminas[0].capas.some(c => c.rol === 'foto' && c.radio === 'elipse')", 30),
       "«Volver a montar» pone la plantilla (11, la foto en círculo)")
    t = _por_rol(pg, "titulo")
    ok(t and t["txt"] == "Hola de nuevo", "y conserva el texto escrito")
    ok(any(c["nombre"] == "Banda de color" for c in _capas(pg)), "y lo añadido")
    pg.p.keyboard.press("Control+z")
    ok(_doc(pg) == antes_de_montar, "Ctrl+Z deshace el montaje")
    pg.p.keyboard.press("Control+y")

    # 11. GUARDAR
    pg.p.locator(".ce-barra .ce-primario").click()
    ok(pg.esperar(".ce-estado", "Guardado", 40), "«Guardar» guarda")
    _r, lista = api.get(f"/api/graficas/{cid}/piezas")
    p0 = next(p for p in lista.get("piezas", []) if p["id"] == pid)
    ok(p0.get("en_capas"), "y la pieza queda en capas")
    ok(p0.get("plantilla") == 3, "sin tocar la pieza de antes")
    ok(pg.p.locator(".ce-barra .ce-primario").is_disabled(), "sin cambios, «Guardar» se apaga")
    jpg_despues = api.s.get(api.base + f"/api/graficas/{cid}/piezas/{pid}/fichero.jpg?antes=1", timeout=30).content
    ok(jpg_despues == jpg_antes, "la imagen de la pieza de antes sigue idéntica")
    # lo que se cambia MIENTRAS se guarda sigue «sin guardar» (árbitro, 12-11)
    pg.pulsar(".ce-anadir button", "Rectángulo")
    pg.p.evaluate("() => { document.querySelector('.ce-barra .ce-primario').click(); document.querySelector('.ce-anadir button:nth-child(2)').click(); }")
    ok(pg.esperar(".ce-estado", "Sin guardar", 40) and _esperar_js(pg, "() => !EditorCapas._estado().guardando", 40),
       "lo añadido mientras se guarda sigue sin guardar")
    pg.p.locator(".ce-barra .ce-primario").click()
    ok(pg.esperar(".ce-estado", "Guardado", 40), "y se guarda al volver a pulsar")

    # 12. VER LA VERSIÓN ANTERIOR
    pg.pulsar(".ce-barra button", "Ver la versión anterior")
    ok(_esperar_js(pg, "() => { const i = document.querySelector('.ce-anterior'); return i && i.complete && i.naturalWidth > 0; }", 20),
       "«Ver la versión anterior» enseña la pieza de antes")
    pg.p.keyboard.press("Escape")
    ok(pg.p.locator(".ce-modal").count() == 0, "y Escape la cierra")

    # 13. OTRA PESTAÑA GUARDA ANTES: 409 y «Guardar como pieza nueva»
    _r, otra = api.get(f"/api/graficas/{cid}/piezas/{pid}/capas")
    r = api.put(f"/api/graficas/{cid}/piezas/{pid}/capas", {"doc": dict(otra["doc"], nombre="Desde otra pestaña")})
    ok(r[0].status_code == 200, "otra pestaña guarda la misma pieza")
    pg.pulsar(".ce-anadir button", "Línea")
    pg.p.locator(".ce-barra .ce-primario").click()
    ok(pg.esperar(".ce-conflicto", "ha cambiado", 20), "guardar aquí no pisa lo de la otra pestaña y lo dice")
    pg.pulsar(".ce-conflicto button", "Guardar como pieza nueva")
    ok(pg.esperar(".ce-estado", "Guardado", 40), "«Guardar como pieza nueva» la guarda aparte")
    _r, lista = api.get(f"/api/graficas/{cid}/piezas")
    ok(len(lista.get("piezas") or []) == 2, "y ahora hay dos piezas")
    ok(any(p["nombre"] == "Desde otra pestaña" for p in lista["piezas"]), "sin perder la de la otra pestaña")
    pg.captura("editor_capas")
    pg.sin_errores("editor con capas")

    # 14. CERRAR Y LA PIEZA NUEVA EN CAPAS
    pg.pulsar(".ce-barra .ce-volver", "Volver")
    ok(pg.p.locator("#editor-capas").count() == 0, "«Volver» cierra el editor")
    # dos clics seguidos al abrir: un solo editor (árbitro, 12-11)
    pg.p.evaluate(f"() => {{ abrirEditorCapas({json.dumps(cid)}, null); abrirEditorCapas({json.dumps(cid)}, null); }}")
    ok(pg.esperar("#editor-capas .ce-lienzo [data-c]", segundos=40), "abrir dos veces seguidas")
    pg.p.wait_for_timeout(1500)
    ok(pg.p.locator("#editor-capas").count() == 1 and pg.p.evaluate("() => EditorCapas._estado().hist.length") == 1,
       "abre un solo editor, con su historial limpio")
    pg.pulsar(".ce-barra .ce-volver", "Volver")
    pg.p.evaluate("() => window.dispatchEvent(new Event('resize'))")
    pg.p.wait_for_timeout(300)
    ok(pg.esperar(".tarjeta-pieza .meta", "en capas", 15), "la lista dice qué piezas están en capas")
    pg.pulsar(".seccion-graficas .nueva-en-capas", "Diseño en capas")
    ok(pg.esperar("#editor-capas .ce-lienzo [data-c]", segundos=40), "«+ Diseño en capas» abre una pieza nueva")
    ok(pg.p.locator(".ce-migra").count() == 0, "sin el aviso de pieza de antes")
    ok(not pg.p.locator(".ce-barra .ce-primario").is_disabled(), "y se puede guardar")
    pg.p.locator(".ce-barra .ce-primario").click()
    ok(pg.esperar(".ce-estado", "Guardado", 40), "se guarda")
    _r, lista = api.get(f"/api/graficas/{cid}/piezas")
    ok(len(lista.get("piezas") or []) == 3 and any(p.get("nacida_en_capas") for p in lista["piezas"]), "y nace en capas")
    pg.pulsar(".ce-barra .ce-volver", "Volver")
    pg.sin_errores("pieza nueva en capas")
    pg.cerrar()

    # 15. EN EL MÓVIL
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="editor_capas_movil")
    pg.js("document.documentElement.dataset.tema = 'claro';")
    pg.js(f"elegirCliente({json.dumps(cid)});")
    ok(pg.esperar(".tarjeta-pieza .abrir-pieza", segundos=20), "en el móvil")
    pg.p.locator(".tarjeta-pieza .abrir-pieza").first.click()
    ok(pg.esperar("#editor-capas .ce-lienzo [data-c]", segundos=40), "el editor abre en el móvil")
    medidas = pg.p.evaluate("() => [document.querySelector('.ce-lienzo').getBoundingClientRect().width, document.documentElement.scrollWidth, innerWidth,"
                            " document.querySelector('#editor-capas').scrollWidth]")
    ok(medidas[0] <= 390 and medidas[3] <= medidas[2] + 1, f"y cabe a lo ancho ({medidas})")
    pg.captura("editor_capas_movil")
    pg.sin_errores("editor con capas en el móvil")
    pg.cerrar()

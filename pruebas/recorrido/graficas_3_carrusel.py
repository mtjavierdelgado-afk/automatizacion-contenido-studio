"""Recorrido de la rama graficas-3-carrusel: un carrusel en el editor con capas.

Añadir láminas desde la tira, ir de una a otra, «En todas las láminas» (y que
un cambio en una llegue a las demás), «Ocultar aquí», borrar una capa «en
todas» (pregunta), duplicar y mover láminas (botones y Alt+flechas), deshacer,
«Este fondo a todas», guardar como trabajo con barra, la tarjeta con «N
láminas» y sus descargas (ZIP y PDF), «Ver como en el móvil» y el móvil.
"""
import io
import json
import zipfile

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


def _laminas(pg):
    return _ed(pg, "E.doc.laminas")


def _elegir_por_lista(pg, cid):
    _esperar_js(pg, QUIETO)
    pg.p.locator(f".ce-capas [data-id='{cid}'] .ce-capa-nombre").click()
    return _esperar_js(pg, "id => EditorCapas._estado().sel.length === 1 && EditorCapas._estado().sel[0] === id", 5, arg=cid)


def _tira(pg):
    return pg.p.locator(".ce-tira .ce-tira-lamina").count()


@escenario
def graficas_3_carrusel(navegador, datos):
    api = datos["api"]
    r, d = api.post("/api/clientes", {"nombre": "Cliente Carrusel"})
    ok(r.status_code in (200, 201), "un proyecto para probar el carrusel")
    cid = d.get("id") or (d.get("cliente") or {}).get("id")

    pg = Pagina(navegador, datos, ancho=1600, alto=1100, nombre="carrusel")
    pg.js(f"elegirCliente({json.dumps(cid)});")
    ok(pg.esperar(".seccion-graficas .nueva-en-capas", segundos=20), "el proyecto ofrece «+ Diseño en capas»")
    pg.pulsar(".seccion-graficas .nueva-en-capas", "Diseño en capas")
    ok(pg.esperar("#editor-capas .ce-lienzo [data-c]", segundos=40), "se abre el editor")
    ok(pg.esperar(".ce-tira .ce-tira-lamina", segundos=5) and _tira(pg) == 1, "debajo del lienzo, la tira con una lámina")
    ok(pg.esperar(".ce-tira-cuenta", "Una lámina", 3), "y dice que es una lámina")
    _esperar_js(pg, QUIETO)

    # 1. AÑADIR LÁMINAS
    pg.pulsar(".ce-tira-acciones button", "Lámina")
    ok(pg.esperar(".ce-tira-menu button", "En blanco", 3), "«＋ Lámina» ofrece «En blanco» y «Copia de esta»")
    pg.pulsar(".ce-tira-menu button", "En blanco")
    ok(_tira(pg) == 2 and _ed(pg, "E.lamina") == 1, "«En blanco» añade una lámina detrás y la abre")
    lams = _laminas(pg)
    ok(lams[1]["tipo"] == "blanco" and lams[1]["capas"][0]["w"] == 100, "con su fondo, del tamaño de la lámina")
    ok(len({lam["id"] for lam in lams}) == 2, "cada lámina con su id")
    ok(pg.esperar(".ce-tira-cuenta", "Lámina 2 de 2", 3), "la tira dice «Lámina 2 de 2»")
    ok(pg.p.locator(".ce-tira-lamina.actual").get_attribute("aria-label") == "Lámina 2 de 2, En blanco",
       "y un lector de pantalla oye qué lámina es")

    # 2. IR A LA PRIMERA Y PONER EL TITULAR «EN TODAS»
    pg.p.locator(".ce-tira-lamina").first.click()
    ok(_esperar_js(pg, "() => EditorCapas._estado().lamina === 0", 3), "pulsar una miniatura abre esa lámina")
    titulo = next(c for c in _laminas(pg)[0]["capas"] if c["rol"] == "titulo")
    ok(_elegir_por_lista(pg, titulo["id"]), "se elige el titular")
    ok(pg.esperar(".ce-der h3", "Carrusel", 3), "el panel de la capa tiene la parte del carrusel")
    pg.p.locator(".ce-der .ce-casilla", has_text="En todas las láminas").locator("input").click()
    lams = _laminas(pg)
    grupo = next(c for c in lams[0]["capas"] if c["id"] == titulo["id"]).get("enlace")
    copia2 = [c for c in lams[1]["capas"] if c.get("enlace") == grupo]
    ok(grupo and len(copia2) == 1 and copia2[0]["id"] != titulo["id"], "«En todas las láminas» pone una copia enlazada en la otra")
    ok(pg.esperar(".ce-der .ce-casilla", "Menos en la primera", 3), "y ofrece dónde no sale")

    # 3. UN CAMBIO EN UNA LLEGA A LAS DEMÁS
    pg.p.locator(".ce-der .ce-muestra[aria-label='Color: Acento']").first.click()
    lams = _laminas(pg)
    ok(next(c for c in lams[1]["capas"] if c.get("enlace") == grupo)["color"] == "kit:acento",
       "cambiar el color en una lámina lo cambia en la otra")
    x0 = next(c for c in lams[1]["capas"] if c.get("enlace") == grupo)["x"]
    pg.p.keyboard.press("Shift+ArrowRight")
    _esperar_js(pg, "([g, x]) => { const c = EditorCapas._estado().doc.laminas[1].capas.find(c => c.enlace === g); return c && c.x !== x; }",
                5, arg=[grupo, x0])
    ok(next(c for c in _laminas(pg)[1]["capas"] if c.get("enlace") == grupo)["x"] != x0, "y moverla también")

    # 4. OCULTAR AQUÍ Y BORRAR UNA ENLAZADA
    pg.p.locator(".ce-tira-lamina").nth(1).click()
    _esperar_js(pg, "() => EditorCapas._estado().lamina === 1", 3)
    otra = next(c for c in _laminas(pg)[1]["capas"] if c.get("enlace") == grupo)
    pg.p.locator(f".ce-capas [data-id='{otra['id']}'] button[title='Ocultar']").click()
    lams = _laminas(pg)
    ok(next(c for c in lams[1]["capas"] if c["id"] == otra["id"])["oculto"] is True
       and next(c for c in lams[0]["capas"] if c["id"] == titulo["id"])["oculto"] is False,
       "el ojo la oculta solo en esta lámina")
    pg.p.locator(f".ce-capas [data-id='{otra['id']}'] button[title='Enseñar']").click()
    _elegir_por_lista(pg, otra["id"])
    pg.p.keyboard.press("Delete")
    ok(pg.esperar(".ce-modal", "Está en todas las láminas", 3), "Supr sobre una capa «en todas» pregunta")
    pg.pulsar(".ce-modal button", "Ocultarla solo aquí")
    lams = _laminas(pg)
    ok(len([c for c in lams[0]["capas"] + lams[1]["capas"] if c.get("enlace") == grupo]) == 2, "«Ocultarla solo aquí» no borra ninguna")

    # 5. DUPLICAR, MOVER Y DESHACER
    pg.pulsar(".ce-tira-acciones button", "Lámina")
    pg.pulsar(".ce-tira-menu button", "Copia de esta")
    lams = _laminas(pg)
    ok(len(lams) == 3 and _ed(pg, "E.lamina") == 2, "«Copia de esta» la duplica detrás")
    ok(len([c for c in lams[2]["capas"] if c.get("enlace") == grupo]) == 1, "con su copia «en todas» en el mismo grupo")
    ids = [lam["id"] for lam in lams]
    pg.pulsar(".ce-tira-acciones button", "← Mover")
    ok([lam["id"] for lam in _laminas(pg)] == [ids[0], ids[2], ids[1]] and _ed(pg, "E.lamina") == 1, "«← Mover» la adelanta")
    pg.p.mouse.click(*_hueco(pg))
    pg.p.keyboard.press("Alt+ArrowRight")
    ok([lam["id"] for lam in _laminas(pg)] == ids, "Alt+→ la devuelve a su sitio")
    pg.p.keyboard.press("Control+z")
    ok([lam["id"] for lam in _laminas(pg)] == [ids[0], ids[2], ids[1]], "Ctrl+Z deshace el cambio de orden")
    pg.p.keyboard.press("Control+y")
    pg.p.keyboard.press("PageUp")
    ok(_ed(pg, "E.lamina") == 1, "RePág va a la lámina de antes")

    # 6. EL NÚMERO {n}/{total} Y «ESTE FONDO A TODAS»
    pg.p.locator(".ce-tira-lamina").first.click()
    _esperar_js(pg, "() => EditorCapas._estado().lamina === 0", 3)
    pg.pulsar(".ce-anadir button", "Texto")
    nuevo = _ed(pg, "E.sel[0]")
    area = pg.p.locator(".ce-der textarea").first
    area.fill("{n}/{total}")
    area.press("Tab")
    pg.p.locator(".ce-der .ce-casilla", has_text="En todas las láminas").locator("input").click()
    ok(_esperar_js(pg, "id => document.querySelector(`.ce-lienzo [data-c='${id}']`).textContent === '1/3'", 5, arg=nuevo),
       "{n}/{total} pone «1/3» en el lienzo")
    pg.p.locator(".ce-tira-lamina").nth(2).click()
    ok(_esperar_js(pg, "() => [...document.querySelectorAll('.ce-lienzo [data-c]')].some(n => n.textContent === '3/3')", 5),
       "y «3/3» en la tercera")
    pg.p.locator(".ce-tira-lamina").first.click()
    _esperar_js(pg, "() => EditorCapas._estado().lamina === 0", 3)
    fondo = _laminas(pg)[0]["capas"][0]
    _elegir_por_lista(pg, fondo["id"])
    if pg.esperar(".ce-der button", "Este fondo a todas", 3):
        pg.pulsar(".ce-der button", "Este fondo a todas")
        lams = _laminas(pg)
        ok(all(lam["capas"][0].get("relleno") == fondo.get("relleno") and lam["capas"][0]["tipo"] == fondo["tipo"] for lam in lams),
           "«Este fondo a todas» pone el mismo fondo en todas")
    else:
        ok(False, "el fondo de la portada ofrece «Este fondo a todas»")

    # 7. GUARDAR: UN TRABAJO CON BARRA
    pg.p.locator(".ce-barra .ce-primario").click()
    ok(pg.esperar(".ce-estado", "Guardado", 60), "«Guardar» guarda el carrusel")
    pid = _ed(pg, "E.piezaId")
    _r, lista = api.get(f"/api/graficas/{cid}/piezas")
    pieza = next((p for p in lista.get("piezas", []) if p["id"] == pid), {})
    ok(pieza.get("laminas") == 3, f"la pieza queda con sus 3 láminas ({pieza.get('laminas')})")
    r = api.s.get(api.base + f"/api/graficas/{cid}/piezas/{pid}/laminas.zip", timeout=60)
    nombres = zipfile.ZipFile(io.BytesIO(r.content)).namelist() if r.status_code == 200 else []
    ok(len([n for n in nombres if n.endswith(".jpg")]) == 3, f"y su ZIP trae las 3 ({nombres})")

    # 8. VER COMO EN EL MÓVIL
    pg.pulsar(".ce-tira-acciones button", "Ver como en el móvil")
    ok(pg.esperar(".ce-modal .ce-movil", segundos=3), "«Ver como en el móvil» enseña el carrusel")
    ok(pg.p.locator(".ce-movil .ce-movil-lamina").count() == 3 and pg.p.locator(".ce-movil-puntos span").count() == 3,
       "con sus 3 láminas y sus puntos")
    pg.pulsar(".ce-modal button", "→")
    ok(pg.esperar(".ce-modal [role=status]", "2 de 3", 3), "la flecha pasa a la siguiente")
    pg.p.keyboard.press("Escape")
    ok(pg.p.locator(".ce-modal").count() == 0, "Escape la cierra")
    pg.captura("carrusel_editor")
    pg.sin_errores("el carrusel en el editor")

    # 9. LA TARJETA: «3 LÁMINAS» Y SUS DESCARGAS
    pg.pulsar(".ce-barra .ce-volver", "Volver")
    ok(pg.esperar(".tarjeta-pieza .meta", "3 láminas", 15), "la tarjeta dice «3 láminas»")
    ok(pg.esperar(".tarjeta-pieza .descargar-pdf", "PDF LinkedIn", 3), "y ofrece el ZIP y el PDF de LinkedIn")
    with pg.p.expect_download(timeout=30000) as bajada:
        pg.p.locator(".tarjeta-pieza .descargar-zip").first.click()
    ok(bajada.value.suggested_filename.endswith(".zip"), f"el ZIP se descarga ({bajada.value.suggested_filename})")
    with pg.p.expect_download(timeout=30000) as bajada:
        pg.p.locator(".tarjeta-pieza .descargar-pdf").first.click()
    ok(bajada.value.suggested_filename.endswith(".pdf"), "y el PDF")
    pg.sin_errores("la tarjeta del carrusel")
    pg.cerrar()

    # 10. EN EL MÓVIL: la tira justo debajo del lienzo, sin salirse
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="carrusel_movil")
    pg.js(f"elegirCliente({json.dumps(cid)});")
    ok(pg.esperar(".tarjeta-pieza .abrir-pieza", segundos=20), "en el móvil")
    pg.p.locator(".tarjeta-pieza .abrir-pieza").first.click()
    ok(pg.esperar("#editor-capas .ce-tira .ce-tira-lamina", segundos=40), "el editor abre con su tira")
    medidas = pg.p.evaluate("""() => { const e = document.querySelector('.ce-escenario').getBoundingClientRect();
        const t = document.querySelector('.ce-tira').getBoundingClientRect();
        const d = document.querySelector('.ce-der').getBoundingClientRect();
        return [t.top >= e.bottom - 1, d.top >= t.bottom - 1, document.querySelector('#editor-capas').scrollWidth <= innerWidth + 1]; }""")
    ok(all(medidas), f"la tira va entre el lienzo y los paneles, sin salirse ({medidas})")
    pg.captura("carrusel_movil")
    pg.sin_errores("el carrusel en el móvil")
    pg.cerrar()


def _hueco(pg):
    """Un punto del escenario fuera del lienzo (para quitar el foco de un botón)."""
    e = pg.p.locator(".ce-escenario").bounding_box()
    return e["x"] + 6, e["y"] + 6

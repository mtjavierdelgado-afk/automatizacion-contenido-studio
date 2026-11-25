"""Recorrido de la rama publicar-redes-3 (la aprobación del cliente por enlace):
1. En «Cuándo», «Pedir aprobación al cliente» da un enlace /cliente/<token>.
2. El cliente lo abre SIN el Studio (en un móvil): ve el vídeo, los textos y
   la fecha; «Pedir cambios» pide decir qué, y después lo aprueba.
3. La ficha del dueño ve la respuesta, el vídeo no sale mientras espera, y
   «Por publicar» enseña lo que han contestado.
4. Anulado, el enlace ya no abre."""
import os

from prueba_recorrido import Pagina, escenario, ok, _paso_ficha  # noqa: F401


def _cliente(navegador, url):
    """Una pestaña aparte, de móvil, sin nada del Studio: lo que ve el cliente."""
    contexto = navegador.new_context(viewport={"width": 390, "height": 844})
    pagina = contexto.new_page()
    errores = []
    pagina.on("pageerror", lambda e: errores.append(f"pageerror: {e}"))
    pagina.on("console", lambda m: errores.append(m.text)
              if m.type == "error" and "Failed to load resource" not in m.text else None)
    pagina.goto(url)
    return contexto, pagina, errores


def _ver(pagina, selector, texto=None, segundos=10):
    loc = pagina.locator(selector)
    if texto:
        loc = loc.filter(has_text=texto)
    try:
        loc.first.wait_for(state="visible", timeout=segundos * 1000)
        return True
    except Exception:                                        # noqa: BLE001
        return False


@escenario
def aprobacion_del_cliente(navegador, datos):
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok"], "textos": {
        "tiktok": {"descripcion": "Texto para que lo apruebe el cliente"}}})
    pg = Pagina(navegador, datos, nombre="aprobacion cliente")
    contexto = None
    try:
        pg.js("irAModulo('publicar');")
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".pasos-publicar .paso-carril", segundos=15), "abre la ficha del vídeo en Publicar")
        ok(_paso_ficha(pg, "cuando"), "el paso «Cuándo»")
        ok(pg.esperar(".aprob-cliente", "Aprobación del cliente", 10),
           "en «Cuándo» está el bloque «Aprobación del cliente»")
        pg.pulsar(".aprob-cliente button", "aprobación al cliente")
        ok(pg.esperar(".aprob-enlace input", segundos=10), "pedirlo enseña el enlace")
        url = pg.p.locator(".aprob-enlace input").first.input_value()
        ok("/cliente/" in url and len(url.rsplit("/", 1)[-1]) >= 40, f"es un enlace /cliente/<token> ({url[:60]}…)")
        ok(pg.visible(".aprob-enlace button", "Copiar") and pg.visible(".aprob-enlace a", "WhatsApp"),
           "con «Copiar» y «WhatsApp»")
        ok(pg.visible(".aprob-estado", "Esperando al cliente"), "y dice que espera al cliente")
        pg.captura("aprobacion_ficha_enlace")
        pg.sin_errores("la ficha con el enlace")

        r, d = api.post(f"/api/publicar/videos/{pid}/enviar",
                        {"redes": ["tiktok"], "modo": "ahora", "confirmado": True})
        ok(r.status_code == 409 and "cliente" in (d.get("error") or ""),
           f"mientras espera al cliente, «Publicar ahora» da 409 ({r.status_code})")

        contexto, cl, errores = _cliente(navegador, url)
        ok(_ver(cl, "h1"), "el cliente abre la página")
        ok(_ver(cl, "video.cl-video"), "ve el vídeo")
        ok(_ver(cl, ".cl-red", "Texto para que lo apruebe el cliente"), "y el texto de la red")
        ok(_ver(cl, "h2", "¿Lo publicamos así?"), "y la pregunta")
        ok(cl.evaluate("() => !document.querySelector('[style]') && typeof APP === 'undefined'"),
           "sin estilos en línea y sin nada del Studio")
        texto = cl.evaluate("() => document.body.innerText")
        ok(not any(m in texto for m in ("null", "undefined", "NaN", "[object")),
           "sin «null», «undefined» ni «NaN» en lo que lee el cliente")
        ok(cl.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"),
           "y no se sale por los lados en el móvil")
        cl.screenshot(path=os.path.join(datos["capturas"], "aprobacion_cliente_movil.png"), full_page=True)
        cl.locator(".cl-boton", has_text="Pedir cambios").first.click()
        cl.locator(".cl-boton.cl-principal").first.click()
        ok(_ver(cl, ".cl-nota.cl-mal", "Cuéntanos"), "pedir cambios sin decir cuáles lo pide")
        cl.locator("#cl-comentario").fill("La música más baja, por favor")
        cl.locator(".cl-boton.cl-principal").first.click()
        ok(_ver(cl, ".cl-nota", "Pediste cambios"), "con el comentario, queda enviado")

        pg.js(f"cargarAprobacion('{pid}', true);")
        ok(pg.esperar(".aprob-estado", "pidió cambios", 10) and pg.visible(".aprob-comentario", "música más baja"),
           "la ficha del dueño ve «pidió cambios» con el comentario")

        cl.locator(".cl-boton", has_text="Cambiar mi respuesta").first.click()
        cl.locator(".cl-boton", has_text="Aprobar").first.click()
        cl.locator(".cl-boton.cl-principal").first.click()
        ok(_ver(cl, ".cl-nota.cl-bien", "Lo aprobaste"), "después lo aprueba")
        ok(not errores, f"la página del cliente, sin errores de JavaScript {errores[:3]}")

        pg.js(f"cargarAprobacion('{pid}', true);")
        ok(pg.esperar(".aprob-estado", "lo aprobó", 10), "la ficha lo ve aprobado")
        pg.js("APROB.respuestas = null; irASeccionPublicar('porpublicar');")
        ok(pg.esperar(".aprob-respuestas", "Aprobado", 10), "«Por publicar» enseña lo que contestó el cliente")
        pg.captura("aprobacion_por_publicar")

        pg.js(f"abrirPublicarVideo('{pid}');")
        _paso_ficha(pg, "cuando")
        pg.esperar(".aprob-cliente button", "Anular", 10)
        pg.pulsar(".aprob-cliente button", "Anular el enlace")
        ok(pg.esperar(".aprob-estado", "anulado", 10), "anularlo lo dice")
        cl.reload()
        ok(_ver(cl, ".cl-nota.cl-mal", "ya no vale"), "y el cliente ya no puede abrirlo")
        pg.sin_errores("la aprobación del cliente")
    finally:
        # que no quede ningún enlace vivo para los escenarios que vienen detrás
        _r, d = api.get(f"/api/publicar/videos/{pid}/aprobacion")
        enlace = (d or {}).get("enlace") or {}
        if enlace.get("vigente"):
            api._r("DELETE", f"/api/publicar/videos/{pid}/aprobacion/{enlace['id']}")
        if contexto is not None:
            contexto.close()
        pg.cerrar()

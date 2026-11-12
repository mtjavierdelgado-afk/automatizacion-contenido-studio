"""Recorrido de la rama publicar-ok-envios (pedido del dueño, 12-11-2026):
1. El día y la hora de «Cuándo» se confirman con «OK» (o Intro) sin tener que
   pulsar fuera del campo, y la barra dice la hora nueva en el acto.
2. El paso «Envíos» de la ficha solo sale cuando el vídeo ya tiene algún envío.
Cada comprobación se vio fallar SIN el arreglo (la barra seguía con la hora de
antes mientras el campo tenía el foco; «Envíos» salía con el vídeo sin envíos)."""
import datetime as dt

from prueba_recorrido import Pagina, escenario, ok, _paso_ficha, _panel_casa  # noqa: F401


def _texto_barra(pg):
    return pg.p.locator(".barra-publicar button.principal").first.inner_text()


@escenario
def publicar_ok_y_envios(navegador, datos):
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok"], "textos": {
        "tiktok": {"descripcion": "Prueba del OK de la hora"}}})
    pg = Pagina(navegador, datos, nombre="ok y envios")
    try:
        pg.js("irAModulo('publicar');")
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".pasos-publicar .paso-carril", segundos=15), "abre la ficha del vídeo en Publicar")
        tenia = bool(ficha.get("envios"))
        hay_paso = pg.visible('.pasos-publicar .paso-carril[data-paso="envios"]')
        ok(hay_paso == tenia,
           f"«Envíos» sale solo si el vídeo ya tiene envíos (tiene: {tenia}, se ve: {hay_paso})")

        # 1 · el OK del día y la hora
        ok(_paso_ficha(pg, "cuando"), "el paso «Cuándo»")
        pg.pulsar('.opcion-modo-publicar[data-modo="programar"]')
        campo = pg.p.locator('input[type="datetime-local"][data-foco="cuando"]').first
        ok(pg.visible(".ok-cuando-publicar", "OK"), "al lado del día y la hora hay un botón «OK»")
        dia = (dt.date.today() + dt.timedelta(days=40)).isoformat()
        nuevo = f"{dia}T18:45"
        legible = pg.p.evaluate(f"() => cuandoLegible('{nuevo}')")
        antes = _texto_barra(pg)
        campo.click()
        campo.fill(nuevo)
        pg.p.wait_for_timeout(600)
        ok(legible not in _texto_barra(pg) or legible in antes,
           "(sin OK y con el campo en uso, la barra aún no se repinta: era la molestia)")
        pg.pulsar(".ok-cuando-publicar")
        ok(pg.esperar(".barra-publicar button.principal", f"Programar para {legible}", 5),
           f"con «OK» la barra dice la hora nueva en el acto ({legible})")
        ok(pg.visible(".cuando-confirmado", "Guardado"), "y una línea «✓ Guardado: …» lo confirma")
        ok(pg.p.evaluate("() => document.activeElement && document.activeElement.dataset.foco !== 'cuando'"),
           "y el campo suelta el foco (el selector se cierra)")
        # Intro hace lo mismo
        otro = f"{dia}T20:15"
        legible2 = pg.p.evaluate(f"() => cuandoLegible('{otro}')")
        campo = pg.p.locator('input[type="datetime-local"][data-foco="cuando"]').first
        campo.click()
        campo.fill(otro)
        campo.press("Enter")
        ok(pg.esperar(".barra-publicar button.principal", f"Programar para {legible2}", 5),
           "Intro en el campo hace lo mismo que «OK»")
        pg.captura("publicar_ok_cuando")
        # en el móvil, el «OK» se ve entero
        pg.p.set_viewport_size({"width": 390, "height": 800})
        pg.p.wait_for_timeout(500)
        caja = pg.p.locator(".ok-cuando-publicar").first.bounding_box()
        ok(caja and caja["x"] >= 0 and caja["x"] + caja["width"] <= 390,
           f"en el móvil el «OK» cabe en la pantalla ({caja})")
        pg.captura("publicar_ok_cuando_movil", entera=False)
        pg.p.set_viewport_size({"width": 1280, "height": 900})
        pg.p.wait_for_timeout(500)

        # 2 · programar con esa hora: ahora sí sale «Envíos»
        pg.pulsar(".barra-publicar button.principal", "Programar para")
        texto = _panel_casa(pg)
        ok(legible2.split(" a las")[0] in texto or "hora de Lima" in texto,
           f"se confirma en el panel ({texto[:80]!r})")
        _r, ficha = api.get(f"/api/publicar/videos/{pid}")
        programados = [e for e in ficha.get("envios", []) if e.get("cuando", "").startswith(otro)]
        ok(programados, f"queda programado a la hora elegida con Intro ({otro})")
        if pg.esperar(".aviso-tras-envio button", "Volver a la ficha", 20):
            pg.pulsar(".aviso-tras-envio button", "Volver a la ficha")
        ok(pg.esperar('.pasos-publicar .paso-carril[data-paso="envios"]', segundos=15),
           "con un envío hecho, el paso «Envíos» aparece")
        _paso_ficha(pg, "envios")
        ok(pg.esperar(".ficha-publicar .fila-envio", segundos=15), "y enseña el envío")
        # se cancela para no dejar nada programado a los escenarios de detrás
        for e in programados:
            api.post(f"/api/publicar/videos/{pid}/envios/{e['id']}/cancelar", {})
        pg.sin_errores("el OK de la hora y el paso Envíos")
    finally:
        pg.cerrar()

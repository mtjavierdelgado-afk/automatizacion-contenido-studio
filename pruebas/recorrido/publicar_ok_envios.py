"""Recorrido de la rama publicar-ok-envios (pedido del dueño, 12-11-2026):
1. El día y la hora de «Cuándo» se confirman con «OK» (o Intro) sin tener que
   pulsar fuera del campo, y la barra dice la hora nueva en el acto.
2. El paso «Envíos» de la ficha solo sale cuando el vídeo ya tiene algún envío.
Cada comprobación se vio fallar SIN el arreglo (la barra seguía con la hora de
antes mientras el campo tenía el foco; «Envíos» salía con el vídeo sin envíos)."""
import datetime as dt
import time

from prueba_recorrido import Pagina, escenario, ok, _paso_ficha, _panel_casa  # noqa: F401


def _texto_barra(pg):
    return pg.p.locator(".barra-publicar button.principal").first.inner_text()


def _cancelar_vivos(api, pid, red="tiktok", segundos=40):
    """Cancela lo programado de esa red (los escenarios de antes programan en
    el mismo vídeo). La ficha no enseña el número de trabajo: mientras
    Upload-Post no lo ha dado, cancelar contesta 409 y se reintenta. Devuelve
    el código final de cada envío cancelado."""
    codigos = {}
    fin = time.time() + segundos
    while time.time() < fin:
        _r, f = api.get(f"/api/publicar/videos/{pid}")
        vivos = [e for e in f.get("envios", []) if e.get("red") == red
                 and e.get("estado") in ("programado", "enviando", "comprobar")]
        if not vivos:
            return list(codigos.values())
        for e in vivos:
            if e.get("estado") == "programado":
                r, _d = api.post(f"/api/publicar/videos/{pid}/envios/{e['id']}/cancelar", {})
                codigos[e["id"]] = r.status_code
        time.sleep(1)
    return list(codigos.values()) + ["sin cancelar"]


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
    _cancelar_vivos(api, pid)
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok"], "textos": {
        "tiktok": {"descripcion": "Prueba del OK de la hora"}}})
    pg = Pagina(navegador, datos, nombre="ok y envios")
    try:
        pg.js("irAModulo('publicar');")
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(pg.esperar(".pasos-publicar .paso-carril", segundos=15), "abre la ficha del vídeo en Publicar")
        _r, ficha = api.get(f"/api/publicar/videos/{pid}")
        tenia = any(e.get("estado") != "cancelado" for e in ficha.get("envios", []))
        hay_paso = pg.visible('.pasos-publicar .paso-carril[data-paso="envios"]')
        ok(hay_paso == tenia,
           f"«Envíos» sale solo si el vídeo tiene envíos no cancelados (tiene: {tenia}, se ve: {hay_paso})")

        # 1 · el OK del día y la hora
        ok(_paso_ficha(pg, "cuando"), "el paso «Cuándo»")
        pg.pulsar('.opcion-modo-publicar[data-modo="programar"]')
        campo = pg.p.locator('input[type="datetime-local"][data-foco="cuando"]').first
        ok(pg.visible(".ok-cuando-publicar", "OK"), "al lado del día y la hora hay un botón «OK»")
        dia = (dt.date.today() + dt.timedelta(days=40)).isoformat()
        nuevo = f"{dia}T18:45"
        legible = pg.p.evaluate(f"() => cuandoLegible('{nuevo}')")
        campo.click()
        campo.fill(nuevo)
        pg.p.wait_for_timeout(600)
        pg.pulsar(".ok-cuando-publicar")
        ok(pg.esperar(".barra-publicar button.principal", f"Programar para {legible}", 5),
           f"con «OK» la barra dice la hora nueva en el acto ({legible})")
        ok(pg.visible(".cuando-confirmado", "Hora elegida"),
           "y una línea «✓ Hora elegida: …» dice que falta programarlo abajo")
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
        # campo vacío + OK: lo dice, y no se queda con una hora que no se ve
        campo = pg.p.locator('input[type="datetime-local"][data-foco="cuando"]').first
        campo.fill("")
        pg.pulsar(".ok-cuando-publicar")
        ok(pg.esperar(".cuando-confirmado.vacio", "Elige el día", 5), "OK con el campo vacío pide elegir la hora")
        campo = pg.p.locator('input[type="datetime-local"][data-foco="cuando"]').first
        campo.fill(otro)
        pg.pulsar(".ok-cuando-publicar")
        pg.pulsar(".barra-publicar button.principal", "Programar para")
        textos = []
        for _ in range(3):
            t = _panel_casa(pg, segundos=6)
            if not t:
                break
            textos.append(t)
        ok(any("hora de Lima" in t for t in textos), f"se confirma en el panel, con la hora ({[t[:60] for t in textos]})")
        programados = []
        for _ in range(20):
            _r, ficha = api.get(f"/api/publicar/videos/{pid}")
            programados = [e for e in ficha.get("envios", []) if e.get("cuando", "").startswith(otro)]
            if programados:
                break
            time.sleep(1)
        ok(programados, f"queda programado a la hora elegida con Intro ({otro})")
        if pg.esperar(".aviso-tras-envio button", "Volver a la ficha", 20):
            pg.pulsar(".aviso-tras-envio button", "Volver a la ficha")
        ok(pg.esperar('.pasos-publicar .paso-carril[data-paso="envios"]', segundos=15),
           "con un envío hecho, el paso «Envíos» aparece")
        _paso_ficha(pg, "envios")
        ok(pg.esperar(".ficha-publicar .fila-envio", segundos=15), "y enseña el envío")
        # se cancela para no dejar nada programado a los escenarios de detrás
        codigos = _cancelar_vivos(api, pid)
        ok(codigos and all(c == 200 for c in codigos), f"y se cancela al terminar ({codigos})")
        # estando en «Envíos», cancelar el último no hace saltar la ficha a otro paso
        pg.js(f"abrirPublicarVideo('{pid}');")
        pg.p.wait_for_timeout(2000)
        ok(pg.visible('.pasos-publicar .paso-carril.actual[data-paso="envios"]'),
           "tras cancelar el último, la ficha sigue en «Envíos» (no salta sola de paso)")
        pg.sin_errores("el OK de la hora y el paso Envíos")
    finally:
        pg.cerrar()

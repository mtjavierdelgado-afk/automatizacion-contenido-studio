"""Recorrido de la rama otro-idioma (11-11-2026): «Hacer este vídeo en otro
idioma». Primero dice lo que cuesta y espera el OK; con el OK duplica, traduce
plano a plano, graba la voz en el otro idioma y monta con LAS MISMAS imágenes,
sin pagar ninguna. En la copia traducida, pedir a Claude que reescriba el guion
avisa antes. El vídeo de origen no cambia en nada (regla 1)."""
import json
import os
import time

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401


def _huellas_de_imagenes(datos, pid):
    """{plano: md5} de las imágenes del plan activo de un vídeo."""
    import hashlib                                              # noqa: PLC0415
    base = os.path.join(datos["proyectos"], pid, "pasos", "assets")
    try:
        with open(os.path.join(base, "activa.json"), encoding="utf-8") as fh:
            activa = json.load(fh).get("activa")
    except (OSError, ValueError):
        return {}
    carpeta = os.path.join(base, f"v{activa}", "escenas")
    salida = {}
    for nombre in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
        if nombre.endswith(".png"):
            with open(os.path.join(carpeta, nombre), "rb") as fh:
                salida[nombre[:-4]] = hashlib.md5(fh.read()).hexdigest()
    return salida


def _foto_del_estado(datos, pid):
    try:
        with open(os.path.join(datos["proyectos"], pid, "estado.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {paso: (d.get("params"), d.get("firma"), d.get("activa"))
            for paso, d in (doc.get("pasos") or {}).items()}


@escenario
def video_en_otro_idioma(navegador, datos):
    """«Hacer este vídeo en otro idioma»: primero dice lo que cuesta y espera el
    OK; con el OK duplica, traduce plano a plano (el Claude falso pone «EN:»),
    graba la voz en inglés y monta con LAS MISMAS imágenes, sin dibujar ninguna.
    El vídeo de origen no cambia en nada (regla 1)."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid, 600)
    # LOS ESCENARIOS DE ANTES DEJAN EL VÍDEO CON CAMBIOS SIN GENERAR: así no se
    # deja pasar (la copia heredaría lo pendiente y lo pagaría). Se pone al día
    # aquí con los motores simulados, como haría el dueño, y entonces se prueba
    r, d = api.get(f"/api/proyectos/{pid}/pasos/assets")
    r_v, d_v = api.get(f"/api/proyectos/{pid}/pasos/voz")
    if d.get("estado") != "listo" or d_v.get("estado") != "listo":
        r, d = api.post(f"/api/proyectos/{pid}/otro_idioma",
                        {"idioma": "en", "confirmado": True})
        ok(r.status_code == 409 and "pon al día" in str(d),
           f"con la voz o las imágenes sin generar no se deja pasar ({r.status_code})")
        for tanda in ("voz", "video"):
            r, d = api.post(f"/api/proyectos/{pid}/generar", {"tanda": tanda, "modo": "pendientes"})
            tid = d.get("trabajo_id") or (d.get("trabajo") or {}).get("id")
            if tid:
                api.esperar(tid, 900)
        api.libre(pid, 600)
        r, d = api.get(f"/api/proyectos/{pid}/pasos/assets")
        r_v, d_v = api.get(f"/api/proyectos/{pid}/pasos/voz")
        ok(d.get("estado") == "listo" and d_v.get("estado") == "listo",
           f"puesto al día, la voz y las imágenes están listas ({d_v.get('estado')}, {d.get('estado')})")
    antes = _foto_del_estado(datos, pid)
    imagenes = _huellas_de_imagenes(datos, pid)
    ok(imagenes, f"el vídeo de prueba tiene imágenes ({len(imagenes)})")

    r, info = api.get(f"/api/proyectos/{pid}/otro_idioma")
    ok(r.status_code == 200 and info.get("origen") == "es", f"sabe de qué idioma sale ({info.get('origen')})")
    ok("en" in [i["id"] for i in info.get("idiomas") or []] and
       "es" not in [i["id"] for i in info.get("idiomas") or []],
       "ofrece el inglés y no el español")
    r, info = api.get(f"/api/proyectos/{pid}/otro_idioma?idioma=en")
    est = info.get("estimacion") or {}
    ok(r.status_code == 200 and (est.get("voz") or {}).get("caracteres", 0) > 0,
       f"dice cuántos caracteres va a locutar ({(est.get('voz') or {}).get('caracteres')})")
    ok((est.get("claude") or {}).get("usd") == 0 and (est.get("imagenes") or {}).get("a_dibujar") == 0,
       "Claude va con la suscripción y no hay imágenes que dibujar")
    ok((est.get("imagenes") or {}).get("reutilizadas", 0) > 0, "y las imágenes se reutilizan")
    ok("(EN)" in str(info.get("nombre_sugerido")), f"propone un nombre ({info.get('nombre_sugerido')})")
    r, _d = api.post(f"/api/proyectos/{pid}/otro_idioma", {"idioma": "en"})
    ok(r.status_code == 400, "sin el OK no hace nada (400)")
    # CON UNA IMAGEN QUITADA A MANO NO SE OFRECE: se reconoce por su frase en
    # español, y en inglés volvería a salir (y se dibujaría)
    quitados = os.path.join(datos["proyectos"], pid, "planos_quitados.json")
    with open(quitados, "w", encoding="utf-8") as fh:
        json.dump({"quitados": [{"texto": "algo"}]}, fh)
    r, info_q = api.get(f"/api/proyectos/{pid}/otro_idioma?idioma=en")
    ok(r.status_code == 409 and "quitadas" in str(info_q),
       f"con imágenes quitadas a mano no se ofrece, y dice qué hacer ({r.status_code})")
    os.remove(quitados)
    ok(_foto_del_estado(datos, pid) == antes, "y preguntar no escribe nada en el vídeo")

    # LA PANTALLA: el botón debajo del vídeo, el cuadro con lo que cuesta y el OK
    pg = Pagina(navegador, datos)
    pg.js(f"await abrirVideoLight('{pid}'); APP.light.video.vista = 'video'; pintarLight();")
    ok(pg.esperar(".otro-idioma-video button", "Hacer este vídeo en otro idioma", 20),
       "debajo del vídeo está «🌐 Hacer este vídeo en otro idioma»")
    pg.p.locator(".otro-idioma-video button").first.click()
    ok(pg.esperar(".otro-idioma-idiomas button", "inglés", 20), "pregunta a qué idioma")
    ok(not pg.visible(".otro-idioma button.primario"), "y no ofrece hacerlo sin elegir antes")
    pg.p.locator(".otro-idioma-idiomas button", has_text="inglés").first.click()
    ok(pg.esperar(".otro-idioma h2", "Lo que cuesta", 20), "dice lo que cuesta antes de hacer nada")
    texto = pg.p.locator("#coste-video").inner_text()
    ok("Claude" in texto and "0 $" in texto and "reutilizadas" in texto and "caracteres" in texto,
       "la voz por caracteres, Claude 0 $ y las imágenes reutilizadas")
    ok(pg.visible(".otro-idioma button.primario", "Sí, hacerlo"), "con su «Sí, hacerlo»")
    pg.captura("otro_idioma_coste", entera=False)
    ok(_foto_del_estado(datos, pid) == antes, "abrir el cuadro no ha escrito nada")
    pg.p.locator(".otro-idioma button.primario").first.click()
    copia = ""
    for _i in range(600):
        copia = pg.p.evaluate("() => (APP.light.video || {}).pid || ''")
        if copia and copia != pid:
            break
        pg.p.wait_for_timeout(1000)
    ok(copia and copia != pid, f"al acabar se abre el vídeo nuevo ({copia})")
    if not copia or copia == pid:
        # sin copia, lo de abajo miraría el ORIGEN y daría fallos que no son
        pg.captura("otro_idioma_sin_copia", entera=False)
        pg.cerrar()
        return
    pg.captura("otro_idioma_copia_abierta", entera=False)
    ok(api.libre(copia, 1500), "la tanda de la copia termina sola")
    pg.js(f"await abrirVideoLight('{copia}'); APP.light.video.vista = 'video'; pintarLight();")
    pg.p.wait_for_timeout(3000)
    rotas = pg.p.evaluate("""() => [...document.querySelectorAll('main img, #contenido img')]
      .filter(i => i.complete && i.getAttribute('src') && !i.naturalWidth).map(i => i.getAttribute('src'))""")
    ok(not rotas, f"el vídeo nuevo se ve con sus imágenes (rotas: {rotas[:3]})")
    pg.captura("otro_idioma_copia_montada", entera=False)
    # REESCRIBIR CON CLAUDE EN LA COPIA AVISA ANTES: lo devolvería al idioma de
    # origen. Se dice que no y no se escribe ni se lanza nada
    pg.aceptar = False
    vistos = len(pg.dialogos)
    _r, g_antes = api.get(f"/api/proyectos/{copia}/pasos/guion")
    pg.js("APP.light.video.promptGeneral = 'más directo'; await reescribirGuionLight();")
    pg.js("await lanzarTandaLight('guion', 'pendientes'); APP.light.video.promptGeneral = '';")
    pg.p.wait_for_timeout(500)
    avisos = pg.dialogos[vistos:]
    ok(len(avisos) == 2 and all("traducción al inglés" in a and "se perderá" in a for a in avisos),
       f"en la copia, reescribir el guion con Claude avisa antes ({len(avisos)}: {avisos[:1]})")
    _r, g_despues = api.get(f"/api/proyectos/{copia}/pasos/guion")
    ok(not ((g_despues.get("params") or {}).get("instruccion_vuelta"))
       and g_despues.get("params") == g_antes.get("params")
       and not [t for t in api.get(f"/api/proyectos/{copia}")[1].get("trabajos") or []],
       "y al decir que no, no escribe ni lanza nada")
    pg.js(f"await abrirVideoLight('{pid}');")
    sin_aviso = pg.p.evaluate("() => seguirConGuionTraducido('el guion')")
    ok(sin_aviso is True and len(pg.dialogos) == vistos + 2, "en el vídeo original no avisa")
    pg.aceptar = True
    pg.sin_errores("el vídeo en otro idioma")
    pg.cerrar()
    ok(_foto_del_estado(datos, pid) == antes, "el vídeo de origen no ha cambiado en nada (params, firmas, versiones)")

    r, c_guion = api.get(f"/api/proyectos/{copia}/pasos/guion")
    bloques = (c_guion.get("params") or {}).get("bloques") or {}
    ok(bloques and all(str(t).startswith("EN:") for t in bloques.values()),
       f"el guion de la copia está traducido bloque a bloque ({len(bloques)})")
    # el guion de la copia queda COMO EL DEL ORIGEN: la traducción entra como
    # corrección a mano y no lo deja obsoleto (si el origen ya lo estaba por
    # los escenarios de antes, la copia lo hereda tal cual)
    _r, o_guion = api.get(f"/api/proyectos/{pid}/pasos/guion")
    ok(c_guion.get("estado") == o_guion.get("estado"),
       f"y el guion no pide reescribirse por traducirlo ({c_guion.get('estado')}, "
       f"el origen {o_guion.get('estado')})")
    r, c_voz = api.get(f"/api/proyectos/{copia}/pasos/voz")
    ok((c_voz.get("params") or {}).get("idioma") == "en" and c_voz.get("estado") == "listo",
       f"la voz se ha grabado en inglés ({c_voz.get('estado')})")
    r, c_call = api.get(f"/api/proyectos/{copia}/pasos/callouts")
    ok((c_call.get("params") or {}).get("idioma") == "en",
       "y los subtítulos de la copia saben que van en inglés (árbitro 12-11: «once» no es «11»)")
    r, o_call = api.get(f"/api/proyectos/{pid}/pasos/callouts")
    ok("idioma" not in (o_call.get("params") or {}), "en el original no se ha escrito nada")
    r, c_render = api.get(f"/api/proyectos/{copia}/pasos/render")
    ok(c_render.get("estado") == "listo", f"y está montada ({c_render.get('estado')})")
    nuevas = _huellas_de_imagenes(datos, copia)
    ok(nuevas == imagenes, f"con LAS MISMAS imágenes, byte a byte ({len(nuevas)} de {len(imagenes)})")
    base = os.path.join(datos["proyectos"], copia, "pasos", "assets")
    with open(os.path.join(base, "activa.json"), encoding="utf-8") as fh:
        activa = json.load(fh).get("activa")
    with open(os.path.join(base, f"v{activa}", "plan.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    escenas = plan.get("escenas") or []
    ok(len(escenas) == len([e for e in escenas]) and escenas and
       all("EN:" in str(e.get("narracion")) for e in escenas if e.get("narracion")),
       "cada plano dice lo suyo en inglés")
    fichas = []
    for e in escenas:
        ruta = os.path.join(base, f"v{activa}", "escenas", f"{e['id']}.json")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as fh:
                fichas.append(json.load(fh))
    ok(fichas and len(fichas) == len(escenas), "cada plano conserva la ficha de su imagen")
    imagenes_pagadas = 0
    try:
        with open(os.path.join(datos["base"], "coste.jsonl"), encoding="utf-8") as fh:
            for linea in fh:
                try:
                    gasto = json.loads(linea)
                except ValueError:
                    continue
                if gasto.get("proyecto") == copia and gasto.get("operacion") == "imagen":
                    imagenes_pagadas += 1
    except OSError:
        pass
    ok(imagenes_pagadas == 0, f"ninguna imagen se ha dibujado ni pagado ({imagenes_pagadas})")
    with open(os.path.join(datos["proyectos"], copia, "bitacora.jsonl"), encoding="utf-8") as fh:
        bitacora = fh.read()
    ok("otro_idioma_planos_ok" in bitacora,
       "antes de montar comprobó que la voz nueva corta en los mismos planos")
    r, c_assets = api.get(f"/api/proyectos/{copia}/pasos/assets")
    ok(not (c_assets.get("unidades_obsoletas") or []),
       f"y ninguna sale obsoleta ({len(c_assets.get('unidades_obsoletas') or [])})")
    with open(os.path.join(datos["proyectos"], copia, "proyecto.json"), encoding="utf-8") as fh:
        config = json.load(fh)
    ok((config.get("traduccion_de") or {}).get("video") == pid and config.get("video_light"),
       "la copia sabe de qué vídeo sale y es un vídeo como los demás")
    capas = os.path.join(datos["proyectos"], copia, "pasos", "callouts")
    with open(os.path.join(capas, "activa.json"), encoding="utf-8") as fh:
        activa_c = json.load(fh).get("activa")
    textos = ""
    carpeta = os.path.join(capas, f"v{activa_c}", "capas_fijas")
    for nombre in sorted(os.listdir(carpeta))[:6]:
        with open(os.path.join(carpeta, nombre), encoding="utf-8") as fh:
            textos += fh.read()
    ok("EN:" in textos or "EN" in textos, "los subtítulos salen en inglés")

    # LA RED DE SEGURIDAD, DE VERDAD: a la copia en portugués se le quita una
    # imagen mientras graba la voz. Tiene que pararse antes de montar, sin
    # dibujar nada, y dejar su plan cortado con la voz nueva (gratis), para que
    # lo que cueste «Generar» en ella se cuente sobre los planos de verdad.
    r, info_pt = api.get(f"/api/proyectos/{pid}/otro_idioma?idioma=pt")
    est_pt = info_pt.get("estimacion") or {}
    r, lanzado = api.post(f"/api/proyectos/{pid}/otro_idioma", {
        "idioma": "pt", "confirmado": True,
        "visto": {"a_dibujar": (est_pt.get("imagenes") or {}).get("a_dibujar")}})
    ok(r.status_code == 202, f"se lanza en portugués ({r.status_code})")
    r2, _d = api.post(f"/api/proyectos/{pid}/otro_idioma", {"idioma": "pt", "confirmado": True})
    ok(r2.status_code == 409, f"un segundo clic mientras tanto no hace otra copia ({r2.status_code})")
    # en cuanto la copia aparece en disco, se le quita la imagen del primer plano
    # (antes de que su voz termine: la comprobación va después de la voz)
    from nucleo.proyecto import LARGO_MAXIMO_ID, identificador  # noqa: PLC0415
    copia_pt = identificador(str(info_pt.get("nombre_sugerido") or ""))[:LARGO_MAXIMO_ID].strip("_")
    base_pt = os.path.join(datos["proyectos"], copia_pt, "pasos", "assets")
    quitada, activa_pt = "", None
    for _i in range(6000):
        try:
            with open(os.path.join(base_pt, "activa.json"), encoding="utf-8") as fh:
                activa_pt = json.load(fh).get("activa")
            carpeta_pt = os.path.join(base_pt, f"v{activa_pt}", "escenas")
            pngs = sorted(n for n in os.listdir(carpeta_pt) if n.endswith(".png"))
            if pngs:
                os.remove(os.path.join(carpeta_pt, pngs[0]))
                quitada = pngs[0][:-4]
                break
        except (OSError, ValueError):
            pass
        time.sleep(0.05)
    ok(quitada, f"a la copia se le quita una imagen mientras graba ({quitada})")
    ficha_a = api.esperar(lanzado.get("trabajo_id"), 600)
    ok(ficha_a.get("estado") == "listo", f"la copia en portugués se crea ({copia_pt})")
    pngs = [quitada + ".png"]
    ok(api.libre(copia_pt, 900), "el trabajo de la copia termina")
    ok((_foto_del_estado(datos, copia_pt).get("render") or (0, 0, None))[2]
       == (antes.get("render") or (0, 0, None))[2], "no la ha montado (el render sigue en su versión copiada)")
    with open(os.path.join(datos["proyectos"], copia_pt, "bitacora.jsonl"), encoding="utf-8") as fh:
        bit_pt = fh.read()
    ok("otro_idioma_parado" in bit_pt and pngs[0][:-4] in bit_pt,
       f"se ha parado antes de montar y dice qué plano ({pngs[0][:-4]})")
    with open(os.path.join(datos["proyectos"], copia_pt, "proyecto.json"), encoding="utf-8") as fh:
        ok((json.load(fh).get("traduccion_de") or {}).get("parado"), "la copia apunta que se paró")
    pagadas_pt = 0
    with open(os.path.join(datos["base"], "coste.jsonl"), encoding="utf-8") as fh:
        for linea in fh:
            try:
                gasto = json.loads(linea)
            except ValueError:
                continue
            if gasto.get("proyecto") == copia_pt and gasto.get("operacion") == "imagen":
                pagadas_pt += 1
    ok(pagadas_pt == 0, f"y no ha dibujado ni pagado ninguna imagen ({pagadas_pt})")
    with open(os.path.join(base_pt, "activa.json"), encoding="utf-8") as fh:
        activa_pt2 = json.load(fh).get("activa")
    with open(os.path.join(base_pt, f"v{activa_pt2}", "plan.json"), encoding="utf-8") as fh:
        plan_pt = json.load(fh)
    ok(activa_pt2 != activa_pt and plan_pt.get("escenas"),
       f"el plan se ha vuelto a cortar gratis con la voz nueva (v{activa_pt} → v{activa_pt2})")
    ok(_foto_del_estado(datos, pid) == antes, "y el original sigue sin cambiar")

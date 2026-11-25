"""Recorrido de la rama retencion-meta (19-11-2026): la retención de Instagram y
Facebook que llega de la API de Meta, en «Más cifras» de cada envío."""
import time

from prueba_recorrido import Pagina, escenario, ok, _paso_ficha  # noqa: F401


def _publicados(ficha, red):
    return [e for e in ficha.get("envios", []) if e.get("estado") == "publicado" and e.get("red") == red]


@escenario
def publicar_retencion_meta(navegador, datos):
    """Un Reel de Instagram y un vídeo de Facebook publicados (Upload-Post y Meta
    simulados): tras «Actualizar», el de Instagram dice cuánto se vio de media y
    cuántos lo saltaron en los 3 primeros segundos; el de Facebook, su curva."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["instagram", "facebook"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    if not (_publicados(ficha, "instagram") and _publicados(ficha, "facebook")):
        api.put(f"/api/publicar/videos/{pid}", {"redes": ["instagram", "facebook"], "textos": {
            "instagram": {"descripcion": "Reel de prueba"},
            "facebook": {"titulo": "Vídeo de prueba", "descripcion": "Vídeo de prueba"}}})
        api.post(f"/api/publicar/videos/{pid}/enviar", {"redes": ["instagram", "facebook"], "modo": "ahora",
                                                         "confirmado": True, "repetir": True})
        for _ in range(15):
            time.sleep(4)
            api.post("/api/publicar/refrescar")
            _r, ficha = api.get(f"/api/publicar/videos/{pid}")
            if _publicados(ficha, "instagram") and _publicados(ficha, "facebook"):
                break
    ok(_publicados(ficha, "instagram") and _publicados(ficha, "facebook"),
       "se parte de un Reel y un vídeo de Facebook publicados (simulados)")
    _r, r = api.post(f"/api/publicar/videos/{pid}/metricas", {"forzar": True})
    envios = (r.get("ficha") or {}).get("envios", [])
    ig = next((e.get("metricas") or {} for e in envios if e.get("red") == "instagram"
               and (e.get("metricas") or {}).get("meta_al")), {})
    fb = next((e.get("metricas") or {} for e in envios if e.get("red") == "facebook"
               and (e.get("metricas") or {}).get("meta_al")), {})
    ok(isinstance(ig.get("tiempo_medio_s"), (int, float)) and isinstance(ig.get("salto_3s"), (int, float)),
       f"Instagram trae de Meta el tiempo medio y el salto de 3 s ({ {k: ig.get(k) for k in ('tiempo_medio_s', 'salto_3s', 'reposts')} })")
    ok(bool(fb.get("curva")) and isinstance(fb.get("tiempo_medio_s"), (int, float)),
       "Facebook trae de Meta su curva y el tiempo medio")

    pg = Pagina(navegador, datos, nombre="retencion meta")
    try:
        pg.js("irAModulo('publicar');")
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(_paso_ficha(pg, "envios"), "la ficha, en su paso «Envíos»")
        ok(pg.esperar(".ficha-publicar .fila-envio", segundos=15), "con los envíos")
        texto = pg.p.locator(".ficha-publicar").first.inner_text()
        ok("lo saltó en los 3 primeros segundos" in texto, "el Reel dice cuántos lo saltaron en los 3 primeros segundos")
        ok("s de media" in texto, "y cuánto se vio de media")
        for det in pg.p.locator(".mas-cifras-envio > summary").all():
            det.click()
        pg.p.wait_for_timeout(400)
        ok(pg.p.locator(".mas-cifras-envio[open] svg.curva-retencion polyline").count() >= 1,
           "el vídeo de Facebook enseña su curva en «Más cifras»")
        ok(not pg.visible(".mas-cifras-envio[open]", "lo último que da TikTok")
           or pg.visible(".mas-cifras-envio[open]", "La mitad deja"),
           "la frase de la curva no le atribuye a TikTok la de Facebook")
        frase = pg.p.evaluate("""() => { const d = detalleMetricasEnvio({red: 'facebook', metricas: {
            curva: [[0, 1], [10, 0.8], [20, 0.6]]}}); return d ? d.textContent : ''; }""")
        ok("lo último que da Facebook" in frase and "TikTok" not in frase,
           f"una curva de Facebook que no baja de la mitad dice «lo último que da Facebook» ({frase[-80:]!r})")
        pg.captura("publicar_retencion_meta")
        pg.sin_errores("la retención de Instagram y Facebook")
    finally:
        pg.cerrar()

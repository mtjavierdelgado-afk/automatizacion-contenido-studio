"""Recorrido de la rama metricas-completas (11-11-2026): las cifras que
Upload-Post ya daba y no se veían, en Resultados y en «Más cifras» de un envío."""
import time

from prueba_recorrido import Pagina, escenario, ok, _paso_ficha  # noqa: F401


@escenario
def publicar_metricas_completas(navegador, datos):
    """Las cifras que Upload-Post ya daba y no se veían: en Resultados, los
    guardados y los seguidores nuevos en las cifras grandes y, aparte, las
    impresiones y el alcance «sumado»; en la ficha, «Más cifras» de un envío de
    TikTok con su curva de retención y de dónde vinieron las vistas."""
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["tiktok", "instagram"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    publicados = lambda f, red: [e for e in f.get("envios", [])  # noqa: E731
                                 if e.get("estado") == "publicado" and e.get("red") == red]
    if not (publicados(ficha, "tiktok") and publicados(ficha, "instagram")):
        api.put(f"/api/publicar/videos/{pid}", {"redes": ["tiktok", "instagram"], "textos": {
            "tiktok": {"descripcion": "TikTok de prueba"}, "instagram": {"descripcion": "Reel de prueba"}}})
        api.post(f"/api/publicar/videos/{pid}/enviar", {"redes": ["tiktok", "instagram"], "modo": "ahora",
                                                         "confirmado": True, "repetir": True})
        for _ in range(15):
            time.sleep(4)
            api.post("/api/publicar/refrescar")
            _r, ficha = api.get(f"/api/publicar/videos/{pid}")
            if publicados(ficha, "tiktok") and publicados(ficha, "instagram"):
                break
    ok(publicados(ficha, "tiktok") and publicados(ficha, "instagram"),
       "se parte de un TikTok y un Reel publicados (Upload-Post simulado)")
    api.post(f"/api/publicar/videos/{pid}/metricas", {"forzar": True})
    _r, r = api.post(f"/api/publicar/videos/{pid}/metricas", {"forzar": True})
    tt = next((e.get("metricas") or {} for e in (r.get("ficha") or {}).get("envios", [])
               if e.get("red") == "tiktok" and (e.get("metricas") or {}).get("curva")), {})
    ok(bool(tt.get("curva")) and bool(tt.get("fuentes")), "TikTok trae su curva y de dónde vinieron las vistas")

    pg = Pagina(navegador, datos, nombre="metricas completas")
    pg.js(f"PUB.proyectoResultados = '{cid}'; PUB.seccion = 'resultados'; irAModulo('publicar');")
    ok(pg.esperar(".cifras-grandes-publicar .cifra", "seguidores nuevos", 15),
       "Resultados: los seguidores nuevos en las cifras grandes")
    ok(pg.visible(".cifras-grandes-publicar .cifra", "guardados"), "y los guardados")
    ok(pg.esperar(".cifras-aparte", "impresiones", 5) and pg.visible(".cifras-aparte", "(sumado)"),
       "y, aparte, las impresiones y el alcance «sumado»")
    # revisión del 12-11: cada total dice de cuántas publicaciones sale
    ok(pg.visible(".cifras-grandes-publicar .cifra", "seguidores nuevos · 1 de 2"),
       "los seguidores nuevos (solo TikTok) dicen de cuántas publicaciones salen")
    ok(pg.visible(".cifras-aparte", "publicaciones)"), "y las impresiones (solo Instagram), también")
    ok(pg.visible(".cifras-aparte", "vistas de tus Reels en Facebook"),
       "lo visto de los Reels en Facebook sale en el total")
    ok(pg.p.evaluate("() => [porcentaje(0.0005), porcentaje(0.00001), porcentaje(0.05), porcentaje(0.184)].join('|')")
       == "0,05 %|menos de 0,01 %|5,0 %|18 %", "los porcentajes pequeños no salen como «0,0 %»")
    pg.captura("publicar_metricas_completas_resultados")
    pg.js(f"abrirPublicarVideo('{pid}');")
    ok(_paso_ficha(pg, "envios"), "la ficha, en su paso «Envíos»")
    ok(pg.esperar(".mas-cifras-envio > summary", "Más cifras", 15), "«Más cifras» en el envío")
    pg.p.locator(".mas-cifras-envio > summary").first.click()
    pg.p.wait_for_timeout(400)
    ok(pg.p.locator(".mas-cifras-envio[open] svg.curva-retencion polyline").count() >= 1,
       "con la curva de retención de TikTok dibujada")
    ok(pg.visible(".mas-cifras-envio[open] .curva-envio", "segundo")
       and not pg.visible(".mas-cifras-envio[open] .curva-envio", "hasta el final"),
       "y lo que dice la curva en una frase (sin «hasta el final», que podía contradecir la retención)")
    ok(pg.visible(".mas-cifras-envio[open]", "De dónde vinieron las vistas") and pg.visible(".mas-cifras-envio[open]", "Para ti"),
       "y de dónde vinieron las vistas, en español («Para ti», no «For You»)")
    pg.captura("publicar_metricas_completas_ficha")
    pg.sin_errores("las métricas completas")
    pg.cerrar()

"""Recorrido de la rama extras-youtube (12-11-2026): la pista de subtítulos de
YouTube. En Ajustes → Textos, «Subir los subtítulos a YouTube» (encendido de
fábrica) y, al publicar en YouTube, el envío dice «Subtítulos: Español»."""
import time

from prueba_recorrido import Pagina, escenario, ok, _ajustes_de, _paso_ficha  # noqa: F401


@escenario
def publicar_subtitulos_youtube(navegador, datos):
    pid = datos["video"]
    api = datos["api"]
    api.libre(pid)
    _r, ficha = api.get(f"/api/publicar/videos/{pid}")
    cid = ficha.get("cliente") or "_sin"
    api.post(f"/api/publicar/proyectos/{cid}/perfil", {})
    api.post(f"/api/publicar/proyectos/{cid}/conectar", {"redes": ["youtube"]})
    api.post(f"/api/publicar/proyectos/{cid}/cuentas")
    pg = Pagina(navegador, datos, nombre="subtitulos youtube")
    try:
        pg.js("irAModulo('publicar');")
        ok(_ajustes_de(pg, cid, "textos"), "Ajustes del proyecto, pestaña Textos")
        casilla = f'.proyecto-publicar[data-proyecto="{cid}"] input[data-ajuste="subtitulos_youtube"]'
        ok(pg.esperar(casilla, segundos=10), "la casilla «Subir los subtítulos a YouTube»")
        ok(pg.p.locator(casilla).is_checked(), "encendida de fábrica")
        pg.p.locator(casilla).uncheck()
        pg.p.wait_for_timeout(1200)
        _r, proyectos = api.get("/api/publicar/proyectos")
        fila = next((x for x in proyectos.get("proyectos", []) if x["id"] == cid), {})
        ok((fila.get("ajustes") or {}).get("subtitulos_youtube") is False, "apagarla lo guarda")
        pg.p.locator(casilla).check()
        pg.p.wait_for_timeout(1200)
        _r, proyectos = api.get("/api/publicar/proyectos")
        fila = next((x for x in proyectos.get("proyectos", []) if x["id"] == cid), {})
        ok((fila.get("ajustes") or {}).get("subtitulos_youtube") is True, "y encenderla también")
        pg.captura("publicar_subtitulos_ajuste")
        # un envío a YouTube lleva la pista (si el vídeo de prueba da subtítulos)
        api.put(f"/api/publicar/videos/{pid}", {"redes": ["youtube"], "textos": {
            "youtube": {"titulo": "Vídeo de prueba", "descripcion": "YouTube de prueba"}}})
        api.post(f"/api/publicar/videos/{pid}/enviar", {"redes": ["youtube"], "modo": "ahora",
                                                         "confirmado": True, "repetir": True})
        con_subs = []
        # el envío corre en segundo plano (la portada y el .srt van antes de la
        # subida): se espera a que se apunte, como mucho un minuto
        for _ in range(30):
            time.sleep(2)
            _r, ficha = api.get(f"/api/publicar/videos/{pid}")
            con_subs = [e for e in ficha.get("envios", []) if e.get("red") == "youtube" and e.get("subtitulos")]
            if con_subs:
                break
        ok(con_subs and con_subs[-1]["subtitulos"] == "Español",
           "el envío a YouTube se apunta con «Subtítulos: Español»")
        pg.js(f"abrirPublicarVideo('{pid}');")
        ok(_paso_ficha(pg, "envios"), "la ficha, en su paso «Envíos»")
        ok(pg.esperar(".subtitulos-envio", "Subtítulos: Español", 15), "y se ve en el envío")
        pg.captura("publicar_subtitulos_envio")
        pg.sin_errores("los subtítulos de YouTube")
    finally:
        pg.cerrar()

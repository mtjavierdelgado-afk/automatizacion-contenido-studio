"""Recorrido de la rama vidiq-2: «Dónde se mide lo que busca la gente» en
«SEO de este proyecto», la ficha que dice dónde se midió y el aviso cuando el
proyecto cambia de sitio después de investigar."""
from prueba_recorrido import Pagina, escenario, ok, _paso_ficha  # noqa: F401


@escenario
def publico_de_las_busquedas(navegador, datos):
    pid = datos["video"]
    api = datos["api"]
    cid = datos["cliente"]
    api.libre(pid)
    api.put(f"/api/publicar/videos/{pid}", {"redes": ["youtube"], "palabra_clave": "consolas para fiestas",
                                            "textos": {"youtube": {"titulo": "Cumple con consolas",
                                                                   "descripcion": "Un vídeo para probar dónde se busca"}}})
    try:
        # 1. sin elegir: Perú, y leerlo no escribe nada
        _r, lista = api.get("/api/publicar/proyectos")
        fila = next((f for f in (lista or {}).get("proyectos") or [] if f.get("id") == cid), {})
        ok((fila.get("ajustes") or {}).get("pais_busquedas") == "pe", "sin elegir, el proyecto mide en Perú")
        ok(any(v == "mundo" for v, _t in ((lista or {}).get("seo_opciones") or {}).get("paises") or []),
           "y la lista trae «Todo el mundo»")

        # 2. en «SEO de este proyecto», el selector; elegir «Todo el mundo»
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicoBusquedas('{cid}');")
        sel = f'select[data-foco="seo-pais_busquedas-{cid}"]'
        ok(pg.esperar(sel, segundos=15), "«SEO de este proyecto» tiene «Dónde se mide lo que busca la gente»")
        ok(pg.p.locator(sel).first.input_value() == "pe", "con Perú elegido")
        ok(pg.visible(".publico-busquedas .meta", "vidIQ"), "y dice quién lo usa")
        pg.p.locator(sel).first.select_option("mundo")
        pg.p.wait_for_timeout(1200)
        _r, lista = api.get("/api/publicar/proyectos")
        fila = next((f for f in (lista or {}).get("proyectos") or [] if f.get("id") == cid), {})
        ok((fila.get("ajustes") or {}).get("pais_busquedas") == "mundo", "elegir «Todo el mundo» se guarda")
        pg.captura("vidiq2_selector")
        pg.sin_errores("el selector de dónde se busca")
        pg.cerrar()

        # 3. la ficha: dónde se mide, investigar y que lo diga
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}'); PUB.busquedasAbiertas = true;")
        _paso_ficha(pg, "seo")
        ok(pg.esperar(".busquedas-seo .publico-linea", "todo el mundo hispano", 15),
           "la ficha dice «Búsquedas medidas en todo el mundo hispano»")
        pg.pulsar(".busquedas-seo button[data-accion=investigar-busquedas]")
        ok(pg.esperar(".tabla-busquedas th", "Frase", 25), "investigar termina solo y enseña la tabla")
        ok(pg.visible(".busquedas-seo .meta", "hace 3 meses en todo el mundo hispano"),
           "y la tendencia dice dónde se mide")
        _r, ficha = api.get(f"/api/publicar/videos/{pid}")
        ok((((ficha.get("seo") or {}).get("real") or {}).get("publico") or {}).get("pais") == "mundo",
           "la investigación guarda dónde se midió")
        pg.captura("vidiq2_ficha")
        pg.sin_errores("investigar en todo el mundo")
        pg.cerrar()

        # 4. el proyecto vuelve a Perú: lo investigado avisa de que es de otro sitio
        api.put(f"/api/publicar/proyectos/{cid}", {"pais_busquedas": "pe"})
        pg = Pagina(navegador, datos)
        pg.js(f"abrirPublicarVideo('{pid}'); PUB.busquedasAbiertas = true;")
        _paso_ficha(pg, "seo")
        ok(pg.esperar(".busquedas-seo .caja-aviso.publico-linea", "se investigó en todo el mundo hispano", 15),
           "si el proyecto cambia de sitio, avisa de que lo investigado es de otro")
        pg.pulsar(".busquedas-seo a[data-accion=cambiar-publico]")
        ok(pg.esperar(sel, segundos=15), "«Cambiar» lleva al selector del proyecto")
        ok(pg.p.evaluate("() => medidoEnBusquedas({al: '2026-10-01'})") == "Perú"
           and pg.p.evaluate("() => medidoEnBusquedas({})") == "",
           "lo investigado antes de esta rama se lee como Perú (no como el sitio de ahora)")
        pg.captura("vidiq2_aviso")
        pg.sin_errores("el aviso de otro sitio")
        pg.cerrar()
    finally:
        api.put(f"/api/publicar/proyectos/{cid}", {"pais_busquedas": "pe"})

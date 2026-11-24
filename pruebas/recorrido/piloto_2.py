"""Recorrido de la rama piloto-2 (24-11-2026): el piloto automático, niveles 2 y 3.

(1) La página del móvil (aprobar.html) a 390 px, en los dos temas: el vídeo
    que espera tu OK se puede editar y aprobar; uno ya programado dice «Ya está
    aprobado» y no deja editar; un 409 de «otro sitio» se dice.
(2) La Parrilla: el resumen del piloto automático del proyecto, la ficha
    «🤖 Piloto automático» (calendario, nivel, próximos 7 días) y que «Guardar»
    es lo único que escribe; la etiqueta viva de un guion y su bloque en la ficha.
(3) Configuración: los pasos para conectar Telegram.

El servidor del piloto automático se dobla aquí (lo de verdad lo prueba
`pasos/prueba_piloto_auto.py`): lo que se mira es la pantalla."""
import json

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401


def _video(paso="espera_ok", clave="espera_ok", texto="⏳ espera tu OK · iría el jue 26 a las 19:00"):
    return {
        "id": "abcdefabcdef", "pid": "video_de_prueba", "titulo": "PA1 — Cumpleaños gamer sin estrés",
        "proyecto": "Cliente", "cid": "c1", "gid": "g_auto", "indice": 0, "paso": paso, "rev": 3, "modo": 2,
        "estado_piloto": "listo", "mensaje": "", "vivo": {"clave": clave, "texto": texto},
        "hueco": "2026-11-26T19:00", "hueco_texto": "jue 26 a las 19:00", "hueco_fijado": False,
        "sin_hueco": False, "redes": ["tiktok", "youtube"], "editable": paso == "espera_ok", "terminado": True,
        "por_red": {}, "fallidas": [], "comprobar": [],
        "razones": [{"clave": "imagenes", "texto": "el revisor sigue marcando 2 imágenes",
                     "que_hacer": "míralas; si están bien, apruébalo"}] if paso == "espera_ok" else [],
        "huecos_libres": [{"cuando": "2026-11-28T19:00", "texto": "sáb 28 a las 19:00"}],
        "publicar": {"textos": {"tiktok": {"descripcion": "¿Cumpleaños gamer? 🎮"},
                                "youtube": {"titulo": "Cumpleaños gamer sin estrés", "descripcion": "Alquila…"}},
                     "antes": {"tiktok": "a", "youtube": "b"},
                     "formato_redes": {"tiktok": {"titulo": 0, "limite": 2200},
                                       "youtube": {"titulo": 100, "limite": 5000}},
                     "encaje": {}, "portada": {}, "titulos": {}, "trabajando": {}, "escribiendo": False,
                     "error_textos": ""},
        "video": "", "portadas": [], "portada_puesta": "", "aprobado_por": "", "aprobado_el": "",
        "telegram": True, "nombres_red": {"tiktok": "TikTok", "youtube": "YouTube"},
    }


@escenario
def piloto_2_pagina_movil(navegador, datos):
    estado = {"video": _video(), "publicados": 0, "conflicto": False}

    def rutas(ruta):
        url = ruta.request.url
        if ruta.request.method == "POST" and url.endswith("/publicar"):
            if estado["conflicto"]:
                ruta.fulfill(status=409, content_type="application/json",
                             body=json.dumps({"error": "Esto se cambió en otro sitio hace un momento: mira lo nuevo"}))
                return
            estado["publicados"] += 1
            estado["video"] = _video("programado", "programado", "📅 programado para el jue 26 a las 19:00")
        ruta.fulfill(status=200, content_type="application/json", body=json.dumps(estado["video"]))

    for tema in ("oscuro", "claro"):
        pg = Pagina(navegador, datos, ancho=390, alto=844, nombre=f"piloto_2_movil_{tema}")
        try:
            pg.p.route("**/api/aprobar/**", rutas)
            if tema == "claro":
                pg.p.evaluate("() => localStorage.setItem('paleta', 'dia')")
            estado.update(video=_video(), publicados=0, conflicto=False)
            pg.p.goto(datos["url"] + "/aprobar.html?video=abcdefabcdef")
            ok(pg.esperar("h1", "PA1"), f"[{tema}] la página del móvil abre con el vídeo")
            ok(pg.visible(".ap-estado", "espera tu OK"), f"[{tema}] dice «espera tu OK»")
            ok(pg.visible(".ap-razones li", "revisor"), f"[{tema}] y por qué mirarlo antes")
            ok(pg.visible("details.ap-red summary", "YouTube"), f"[{tema}] los textos de cada red")
            ok(pg.visible(".ap-barra button", "Publicar así") and pg.visible(".ap-barra button", "No publicar"),
               f"[{tema}] los botones «✓ Publicar así» y «No publicar»")
            ancho = pg.p.evaluate("document.documentElement.scrollWidth")
            ok(ancho <= 390, f"[{tema}] nada se sale por los lados ({ancho} px)")
            texto = pg.p.inner_text("body")
            ok(not any(x in texto for x in ("undefined", "NaN", "null")), f"[{tema}] sin «undefined» ni «NaN»")
            pg.captura(f"piloto_2_movil_{tema}_espera")
            estado["conflicto"] = True
            pg.pulsar(".ap-barra button", "Publicar así")
            ok(pg.esperar(".ap-mensaje", "otro sitio"), f"[{tema}] un 409 dice «Esto se cambió en otro sitio»")
            estado["conflicto"] = False
            pg.pulsar(".ap-barra button", "Publicar así")
            ok(pg.esperar(".ap-estado", "Ya está aprobado"), f"[{tema}] tras aprobar: «Ya está aprobado»")
            ok(estado["publicados"] == 1, f"[{tema}] se aprobó una vez")
            ok(not pg.visible(".ap-barra button", "Publicar así"), f"[{tema}] y ya no ofrece «Publicar así»")
            ok(not pg.visible("details.ap-red"), f"[{tema}] ni editar textos (ya está en Upload-Post)")
            ok(pg.visible(".ap-barra button", "Cambiar fecha"), f"[{tema}] pero sí cambiar la fecha")
            pg.captura(f"piloto_2_movil_{tema}_programado")
            pg.sin_errores(f"piloto-2 móvil {tema}")
        finally:
            pg.cerrar()


@escenario
def piloto_2_ficha_y_parrilla(navegador, datos):
    cid = datos["cliente"]
    escrito = {"put": 0, "vista": 0}

    def ficha_auto(guardada=False, activo=False):
        return {"ficha": {"activo": activo, "modo": 2, "huecos": [{"dias": [1, 3, 5], "hora": "19:00", "redes": ["tiktok"]}],
                          "estilo": "", "anticipacion_h": 24, "max_pendientes": 2, "aviso_guiones_dias": 3,
                          "avanzado": {}, "rev": 1 if guardada else 0, "guardada": guardada},
                "estilos": [{"id": "e1", "nombre": "Estilo de prueba", "cliente": cid}],
                "redes": [{"id": "tiktok", "nombre": "TikTok"}, {"id": "youtube", "nombre": "YouTube"}],
                "modos": [{"id": 2, "nombre": "Nivel 2 · con tu OK", "frase": "Te avisa y espera tu OK."},
                          {"id": 3, "nombre": "Nivel 3 · publica solo", "frase": "Lo programa solo."}],
                "proximos": {"huecos": [{"cuando": "2026-11-25T19:00", "texto": "mié 25 a las 19:00",
                                         "redes": ["tiktok"], "guion": "PA1 — Cumpleaños", "usd": 1.2}],
                             "usd_total": 1.2},
                "repetidas": [], "videos": [], "programados": 0, "bloqueo": None, "saltadas": [],
                "telegram": {"conectado": False}, "ajustes_piloto": {"si_falla": "mezcla", "umbral_pct": 25,
                                                                     "vueltas": 2, "tope_usd": 5, "portadas": "ambas"},
                "limites": {}}

    def rutas(ruta):
        metodo = ruta.request.method
        if metodo == "PUT":
            escrito["put"] += 1
            ruta.fulfill(status=200, content_type="application/json", body=json.dumps(ficha_auto(True, True)))
        elif ruta.request.url.endswith("/vista"):
            escrito["vista"] += 1
            ruta.fulfill(status=200, content_type="application/json",
                         body=json.dumps({"proximos": ficha_auto()["proximos"], "repetidas": []}))
        else:
            ruta.fulfill(status=200, content_type="application/json", body=json.dumps(ficha_auto()))

    pg = Pagina(navegador, datos, nombre="piloto_2_ficha")
    try:
        pg.p.route("**/api/piloto/auto/**", rutas)
        pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
        pg.js(f"elegirProyectoParrilla({json.dumps(cid)});")
        pg.p.wait_for_timeout(1500)
        ok(pg.esperar(".resumen-auto", "apagado", 15), "el panel del piloto dice que el automático está apagado")
        pg.pulsar(".resumen-auto button", "Configurar")
        ok(pg.esperar(".dialogo-auto h3", "Piloto automático"), "la ficha «🤖 Piloto automático» abre")
        ok(escrito["put"] == 0, "abrirla no escribe nada (regla 1)")
        ok(pg.visible(".dialogo-auto .linea-auto .dia-auto.puesto", "L"), "el calendario trae su línea (L-X-V)")
        ok(pg.visible(".dialogo-auto .lista-proximos-auto", "PA1"), "y qué guion iría en cada hueco, con su coste")
        pg.pulsar(".dialogo-auto button", "Añadir hora")
        ok(pg.p.locator(".dialogo-auto .linea-auto").count() == 2, "«+ Añadir hora» pone otra línea")
        pg.pulsar(".dialogo-auto .opcion-piloto", "Nivel 3")
        ok(pg.visible(".dialogo-auto .pista", "NO publica solo"), "en nivel 3 explica cuándo NO publica solo")
        ok(escrito["put"] == 0, "tocarla tampoco escribe nada")
        pg.p.select_option(".dialogo-auto select", "e1")
        pg.captura("piloto_2_ficha_abierta", entera=False)
        pg.pulsar(".dialogo-auto .acciones-dialogo button", "Guardar")
        ok(escrito["put"] == 1, "«Guardar» es lo que escribe")
        ok(not pg.visible(".dialogo-auto"), "y la ficha se cierra")
        pg.captura("piloto_2_ficha")
        # la etiqueta viva de un guion (la calcula el servidor al listar)
        pg.js("const g = ((PAR.datos || {}).matrices || []).flatMap(m => m.guiones || [])[0];"
              " if (g) { g.auto = { id: 'abcdefabcdef', clave: 'espera_ok', texto: '⏳ espera tu OK' }; }"
              " pintarModulo();")
        if pg.p.evaluate("() => ((PAR.datos || {}).matrices || []).some(m => (m.guiones || []).length)"):
            ok(pg.esperar(".tarjeta-guion .pastilla", "espera tu OK"), "el guion lleva su etiqueta viva en la Parrilla")
        pg.sin_errores("piloto-2 ficha")
    finally:
        pg.cerrar()


@escenario
def piloto_2_ficha_en_el_movil(navegador, datos):
    """La ficha también se usa desde el móvil: a 390 px nada se sale."""
    cid = datos["cliente"]
    pg = Pagina(navegador, datos, ancho=390, alto=844, nombre="piloto_2_ficha_movil")
    try:
        cuerpo = {"ficha": {"activo": True, "modo": 3, "huecos": [{"dias": [1, 2, 3, 4, 5, 6, 7], "hora": "09:00",
                                                                   "redes": ["tiktok", "youtube", "instagram"]}],
                            "estilo": "", "anticipacion_h": 24, "max_pendientes": 2, "aviso_guiones_dias": 3,
                            "avanzado": {}, "rev": 1, "guardada": True},
                  "estilos": [], "redes": [{"id": r, "nombre": n} for r, n in
                                           (("tiktok", "TikTok"), ("youtube", "YouTube"), ("instagram", "Instagram Reels"))],
                  "modos": [{"id": 2, "nombre": "Nivel 2 · con tu OK", "frase": "x"},
                            {"id": 3, "nombre": "Nivel 3 · publica solo", "frase": "y"}],
                  "proximos": {"huecos": [], "usd_total": 0}, "repetidas": [], "videos": [], "programados": 0,
                  "bloqueo": {"gid": "g1", "indice": 0, "codigo": "PA9", "titulo": "", "hacer_igual": True,
                              "razones": [{"texto": "al guion le falta la llamada a la acción ([FALTA CTA])"}]},
                  "saltadas": [], "telegram": {"conectado": True, "chat_nombre": "Javier"},
                  "ajustes_piloto": {"si_falla": "mezcla", "umbral_pct": 25, "vueltas": 2, "tope_usd": 5,
                                     "portadas": "ambas"}, "limites": {}}
        pg.p.route("**/api/piloto/auto/**", lambda r: r.fulfill(status=200, content_type="application/json",
                                                               body=json.dumps(cuerpo)))
        pg.js("irAModulo('automatizar');")
        pg.js(f"elegirProyectoParrilla({json.dumps(cid)});")
        pg.p.wait_for_timeout(1500)
        ok(pg.esperar(".resumen-auto", "Encendido", 15), "en el móvil: el resumen dice «Encendido · nivel 3»")
        ok(pg.visible(".resumen-auto .caja-aviso", "PA9") and pg.visible(".resumen-auto button", "Hacer igualmente"),
           "lo que frena el siguiente vídeo, con «Hacer igualmente»")
        pg.pulsar(".resumen-auto button", "Ajustar")
        ok(pg.esperar(".dialogo-auto h3"), "la ficha abre en el móvil")
        ancho = pg.p.evaluate("Math.max(document.documentElement.scrollWidth, "
                              "document.querySelector('.dialogo-auto').scrollWidth)")
        ok(ancho <= 390, f"a 390 px nada se sale por los lados ({ancho} px)")
        pg.captura("piloto_2_ficha_movil", entera=False)
        pg.sin_errores("piloto-2 ficha en el móvil")
    finally:
        pg.cerrar()


@escenario
def piloto_2_telegram(navegador, datos):
    pg = Pagina(navegador, datos, nombre="piloto_2_telegram")
    try:
        pg.p.route("**/api/telegram", lambda r: r.fulfill(status=200, content_type="application/json",
                   body=json.dumps({"token_puesto": False, "conectado": False})))
        pg.js("conmutarConfig(true);")
        ok(pg.esperar(".tarjeta-telegram h3", "Telegram", 15), "Configuración tiene «📲 Avisos al móvil (Telegram)»")
        ok(pg.visible(".tarjeta-telegram li", "@BotFather"), "con los pasos para crear el bot")
        ok(pg.visible(".tarjeta-telegram button", "Conectar"), "y dónde pegar el token")
        pg.sin_errores("piloto-2 telegram")
    finally:
        pg.cerrar()

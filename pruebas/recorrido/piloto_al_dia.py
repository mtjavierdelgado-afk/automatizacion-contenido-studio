"""Recorrido de la rama piloto-al-dia (12-11-2026, X01 e Y05 del servidor).

(1) Una tarjeta del piloto que falló pero cuyo vídeo ya se terminó a mano dice
«Terminado a mano», va con los listos, ofrece «Publicar ›» y no «Reintentar».
El servidor del piloto se dobla aquí (lo de verdad lo prueba
`pasos/prueba_piloto.py`): lo que se mira es la pantalla.
(2) El guion visual avisa de las líneas con un estado que no es ninguno de los
del espacio (lo del plan lo prueba `pasos/prueba_piloto_al_dia.py`)."""
import json

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401


@escenario
def piloto_terminado_a_mano(navegador, datos):
    cid = datos["cliente"]

    def lista():
        fallado = {"id": "pm1", "cid": cid, "gid": "g_mano", "estado": "error", "etapa": "imagenes",
                   "nombre": "PM1 — Arreglado a mano", "pid": "video_de_prueba", "portadas": [], "revisar": [],
                   "porque": "dos o mas planos han acabado con la MISMA imagen", "terminado_a_mano": True,
                   "salio": False}
        sigue = dict(fallado, id="pm2", gid="g_fallo", nombre="PM2 — Sigue fallando", terminado_a_mano=False)
        sigue.pop("terminado_a_mano")
        return {"videos": [fallado, sigue], "cuenta": {"error": 2}, "a_revisar": 1, "ajustes": {},
                "estados": {"error": "Falló", "listo": "Listo para publicar"},
                "etapas": [{"id": "imagenes", "nombre": "Imágenes y revisor"}], "modos": [], "limites": {}}

    def rutas(ruta):
        if ruta.request.method == "GET" and "/api/piloto/videos/" not in ruta.request.url:
            ruta.fulfill(status=200, content_type="application/json", body=json.dumps(lista()))
        else:
            ruta.fulfill(status=404, content_type="application/json", body=json.dumps({"error": "no"}))

    pg = Pagina(navegador, datos, nombre="piloto_al_dia")
    try:
        pg.p.route("**/api/piloto**", rutas)
        pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
        pg.js(f"elegirProyectoParrilla({json.dumps(cid)});")
        pg.p.wait_for_timeout(1500)
        pg.js("PIL.huella = ''; pintarModulo();")
        ok(pg.esperar(".tarjeta-piloto .titulo-piloto", "PM1", 15), "la tarjeta del vídeo arreglado a mano sale")
        mano = ".tarjeta-piloto:has-text('PM1')"
        ok(pg.visible(f"{mano} .pastilla", "Terminado a mano"), "dice «Terminado a mano», no «Falló»")
        ok(pg.visible(f"{mano} button", "Publicar"), "ofrece «Publicar ›»")
        ok(not pg.visible(f"{mano} button", "Reintentar"), "y no «Reintentar» (podría volver a pagar el revisor)")
        ok(pg.visible(".grupo-listos .tarjeta-piloto", "PM1") and not pg.visible(".grupo-revisar .tarjeta-piloto", "PM1"),
           "va con los listos para publicar, y no también en «Necesita revisión»")
        ok(pg.visible(".grupo-revisar .tarjeta-piloto", "PM2") and pg.visible(".tarjeta-piloto:has-text('PM2') button", "Reintentar"),
           "el que sigue fallando, igual que siempre")
        # el guion visual avisa de un estado que no es ninguno del espacio
        texto = pg.js("const video = APP.light.video;"
                      " APP.light.video = { pid: 'x', gv: { pid: 'x', cargado: true, ocupado: true, copia: [], tocado: false,"
                      " ficha: { modo: 'guion', bloques: [], estados: ['blanco_frio'], estados_sin_casar: [{ plano: 'V004',"
                      " estado: 'rojo', opciones: ['antes', 'blanco_frio'] }] } } };"
                      " let n = null; try { n = editorGuionVisual(); } finally { APP.light.video = video; }"
                      " return n ? n.textContent : '';") or ""
        ok("V004" in texto and "«rojo»" in texto and "«blanco_frio»" in texto and "no se dibujan" in texto,
           "el guion visual avisa de la línea con un estado que no es ninguno del espacio")
        pg.captura("piloto_terminado_a_mano")
        pg.sin_errores("piloto-al-dia")
    finally:
        pg.cerrar()

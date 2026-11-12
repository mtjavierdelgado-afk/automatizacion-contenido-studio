"""Recorrido de la rama extension-2: la bandeja «Recibidos de Chrome» con
proyectos (revisión del 12-11-2026). El filtro «De este proyecto», «✍️ Escribir
el guion» (una conversación nueva, sin internet ni vidIQ, y tu borrador
intacto), que un estilo de otro proyecto no se acepta, y «Borrar todos los
archivados» (lo hace el servidor)."""
import json

from prueba_recorrido import Pagina, escenario, ok  # noqa: F401


@escenario
def extension_2_recibidos(navegador, datos):
    api = datos["api"]
    _r, c = api.post("/api/recibidos/codigo", {})
    codigo = (c or {}).get("codigo", "")
    ok(codigo.startswith("env_"), "un código de envío para la prueba")
    nombre = "Recibidos de la extensión"
    _r, cl = api.post("/api/clientes", {"nombre": nombre})
    cid = ((cl or {}).get("cliente") or {}).get("id")
    ok(cid, "un proyecto al que anexarlos")
    cabecera = {"X-Estudio-Envio": codigo}
    ids = []
    for i, (autor, proyecto) in enumerate((("ext2_uno", cid), ("ext2_dos", cid), ("ext2_suelto", ""))):
        r, d = api.post("/api/recibidos", {"url": f"https://www.instagram.com/reel/EXT2x{i}/", "autor": autor,
                                           "texto": f"el post de {autor}", "proyecto": proyecto}, headers=cabecera)
        ok(r.status_code == 201, f"llega {autor} ({r.status_code})")
        ids.append((d or {}).get("id"))
    r, _d = api.post(f"/api/recibidos/{ids[0]}/proyecto", {"proyecto": cid, "estilo": "no-es-de-este-proyecto"})
    ok(r.status_code == 400, f"un estilo que no es de ese proyecto no se acepta ({r.status_code})")
    r, _d = api.post(f"/api/parrilla/proyectos/{cid}/chats", {"estilo": "no-es-de-este-proyecto"})
    ok(r.status_code == 400, f"ni una conversación con un estilo de otro proyecto ({r.status_code})")

    pg = Pagina(navegador, datos, nombre="extension-2")
    try:
        pg.pulsar("#barra-modulos .boton-modulo", "Automatizar")
        pg.js(f"elegirProyectoParrilla({json.dumps(cid)});")
        pg.js("irASeccionParrilla('recibidos');")
        ok(pg.esperar(".tarjeta-recibido", "@ext2_uno", 15), "los recibidos del proyecto salen en la bandeja")
        pg.pulsar(".filtros-recibidos button", f"De {nombre}")
        ok(pg.esperar(".tarjeta-recibido", "@ext2_dos", 10) and not pg.visible(".tarjeta-recibido", "@ext2_suelto"),
           "«De este proyecto»: solo los suyos")
        ok(not pg.visible(".recibidos-parrilla .meta", "Se ven los"), "sin «se ven los N de M» cuando caben todos")
        # «✍️ Escribir el guion»: lo que se manda, sin internet ni vidIQ, y tu borrador no se toca
        pg.js("PAR.chatTexto = 'mi borrador'; PAR.chatWeb = true; window.__envio = [];"
              " const o = FormData.prototype.append; FormData.prototype.append = function (k, v) {"
              " window.__envio.push([k, typeof v === 'string' ? v : '(fichero)']); return o.apply(this, arguments); };")
        pg.pulsar(".tarjeta-recibido:has-text('@ext2_uno') button", "Escribir el guion")
        ok(pg.esperar(".chat-parrilla", segundos=10), "«✍️ Escribir el guion» lleva al chat del proyecto")
        envio = dict(pg.js("return window.__envio;") or [])
        ok(envio.get("web") == "0" and "vidiq" not in envio and "Te paso una referencia" in envio.get("texto", ""),
           f"le pide el guion a Claude sin «Buscar en internet» ni vidIQ ({sorted(envio)})")
        ok(pg.js("return PAR.chatTexto;") == "mi borrador", "y lo que tenías a medio escribir sigue ahí")
        # archivar dos y «Borrar todos los archivados»
        pg.js("irASeccionParrilla('recibidos');")
        for autor in ("@ext2_uno", "@ext2_dos"):
            ok(pg.esperar(".tarjeta-recibido", autor, 10), f"{autor} en la bandeja")
            pg.pulsar(f".tarjeta-recibido:has-text('{autor}') button", "Archivar")
            pg.p.wait_for_timeout(800)
        pg.pulsar(".filtros-recibidos button", "Archivados")
        ok(pg.esperar(".tarjeta-recibido", "@ext2_dos", 10), "los dos, en «Archivados»")
        pg.pulsar(".filtros-recibidos button", "Borrar todos los archivados")
        pg.pulsar(".capa-dialogo button", "Borrar")
        pg.p.wait_for_timeout(1500)
        _r, lista = api.get("/api/recibidos?filtro=archivados")
        ok(not any(str(x.get("autor", "")).startswith("ext2_") for x in (lista or {}).get("recibidos", [])),
           "«Borrar todos los archivados» los borra")
        pg.captura("extension_2_recibidos")
        pg.sin_errores("extension-2: recibidos con proyecto")
    finally:
        pg.cerrar()
        for rid in ids:
            if rid:
                api.s.delete(api.base + f"/api/recibidos/{rid}")

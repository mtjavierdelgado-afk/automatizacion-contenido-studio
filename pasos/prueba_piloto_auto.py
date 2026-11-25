"""Prueba de pasos/piloto_auto.py: el piloto automático (niveles 2 y 3).

Sin servidor, sin red y sin gastar nada: el calendario, los huecos, qué guion
toca, las razones para esperar y cómo se lee el estado de los envíos. Lo que
lo encadena (el vigía de app.py, `_auto_*`) lo prueba la segunda parte con el
servidor de verdad, un Upload-Post falso y un Telegram falso.

    python pasos/prueba_piloto_auto.py
"""
import datetime as dt
import os
import shutil
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

import piloto as P  # noqa: E402
import piloto_auto as A  # noqa: E402

REDES = ("tiktok", "instagram", "youtube", "facebook")
_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        return True
    _fallos.append(mensaje)
    print(f"      FALLO: {mensaje}")
    return False


def igual(obtenido, esperado, mensaje):
    return ok(obtenido == esperado, f"{mensaje} (esperaba {esperado!r}, llegó {obtenido!r})")


def lanza(fn, *args, codigo=None, **kwargs):
    try:
        fn(*args, **kwargs)
    except (A.ErrorAuto, P.ErrorPiloto) as fallo:
        return codigo is None or fallo.codigo == codigo
    return False


# lunes 23-11-2026, 08:00 (Lima)
LUNES = dt.datetime(2026, 11, 23, 8, 0)


def ficha_lmv(**mas):
    f = dict(A.FICHA_DEFECTO, activo=True, estilo="e1",
             huecos=[{"dias": [1, 3, 5], "hora": "19:00", "redes": ["tiktok", "youtube"]}])
    f.update(mas)
    return f


def video_auto(hueco, paso="preparando", estado="en_cola", cid="c1", gid="g1", indice=0,
               redes=("tiktok",)):
    return {"id": "a" * 12, "estado": estado, "cid": cid, "gid": gid, "indice": indice,
            "auto": {"cid": cid, "gid": gid, "indice": indice, "hueco": hueco, "paso": paso,
                     "redes": list(redes), "rev": 0, "envios_antes": []}}


def probar_huecos():
    print("\n  LOS HUECOS")
    f = ficha_lmv()
    hs = A.huecos_de(f, LUNES, 7)
    igual([h["cuando"] for h in hs][:3],
          ["2026-11-23T19:00", "2026-11-25T19:00", "2026-11-27T19:00"],
          "lunes, miércoles y viernes a las 19:00")
    igual(hs[0]["redes"], ["tiktok", "youtube"], "cada hueco lleva sus redes")
    f2 = ficha_lmv(huecos=[{"dias": [1], "hora": "09:00", "redes": ["tiktok"]},
                           {"dias": [1], "hora": "19:00", "redes": ["youtube"]},
                           {"dias": [1], "hora": "19:00", "redes": ["instagram"]}])
    hs = A.huecos_de(f2, LUNES, 1)
    igual([h["cuando"] for h in hs], ["2026-11-23T09:00", "2026-11-23T19:00"],
          "varios vídeos el mismo día; dos líneas a la misma hora son UN hueco")
    igual(hs[1]["redes"], ["youtube", "instagram"], "con la unión de sus redes")
    igual(A.horas_repetidas(f2), ["L 19:00"], "y la ficha sabe decir cuál se repite")
    tarde = LUNES.replace(hour=20)
    igual(A.huecos_de(f, tarde, 2)[0]["cuando"], "2026-11-25T19:00",
          "un hueco que ya pasó hoy no sale")
    domingo = dt.datetime(2026, 11, 29, 23, 0)
    igual(A.huecos_de(f, domingo, 2)[0]["cuando"], "2026-11-30T19:00", "cambia de semana bien")
    con_zona = LUNES.replace(tzinfo=dt.timezone(dt.timedelta(hours=-5)))
    igual(A.huecos_de(f, con_zona, 1)[0]["cuando"], "2026-11-23T19:00",
          "con la hora de Lima con zona (como la da publicar.ahora_lima) también")

    print("\n  EL HUECO LIBRE")
    libre = A.hueco_libre(f, [], "c1", LUNES)
    igual(libre["cuando"], "2026-11-23T19:00", "sin vídeos, el primero")
    ocupado = [video_auto("2026-11-23T19:00")]
    igual(A.hueco_libre(f, ocupado, "c1", LUNES)["cuando"], "2026-11-25T19:00",
          "con el lunes ocupado, el miércoles")
    igual(A.hueco_libre(f, ocupado, "otro", LUNES)["cuando"], "2026-11-23T19:00",
          "el hueco de OTRO proyecto no cuenta")
    igual(A.hueco_libre(f, ocupado, "c1", LUNES, quitar="2026-11-23T19:00")["cuando"],
          "2026-11-23T19:00", "el propio hueco del vídeo no se cuenta como ocupado")
    no_pub = [video_auto("2026-11-23T19:00", paso="no_publicar")]
    igual(A.hueco_libre(f, no_pub, "c1", LUNES)["cuando"], "2026-11-23T19:00",
          "uno que no se publica suelta su hueco")
    cancel = [video_auto("2026-11-23T19:00", estado="cancelado")]
    igual(A.hueco_libre(f, cancel, "c1", LUNES)["cuando"], "2026-11-23T19:00",
          "uno parado por ti («Parar») suelta su hueco")
    fallo = [video_auto("2026-11-23T19:00", paso="fallo", estado="listo")]
    igual(A.hueco_libre(f, fallo, "c1", LUNES)["cuando"], "2026-11-25T19:00",
          "uno con una red fallida NO suelta su hueco (nunca se rehace)")
    casi = LUNES.replace(hour=18, minute=55)
    igual(A.hueco_libre(f, [], "c1", casi)["cuando"], "2026-11-25T19:00",
          f"a menos de {A.MARGEN_MIN} min ya no vale ese hueco")
    ok(A.vencido("2026-11-23T19:00", casi), "y se da por vencido")
    ok(not A.vencido("2026-11-23T19:00", LUNES), "con tiempo, no")
    igual(A.hueco_libre(f, [], "c1", LUNES, despues="2026-11-25T19:00")["cuando"],
          "2026-11-27T19:00", "«después de» uno, el siguiente")
    igual(A.hueco_libre(dict(f, huecos=[]), [], "c1", LUNES), None, "sin calendario, ninguno")
    ok(A.toca_preparar("2026-11-24T07:00", LUNES, 24), "a 23 h de su hueco toca prepararlo (24 h)")
    ok(not A.toca_preparar("2026-11-25T19:00", LUNES, 24), "a 59 h, todavía no")


def probar_ficha(raiz):
    print("\n  LA FICHA")
    igual(A.leer_ficha(raiz, "c1"), None, "sin guardar no hay ficha (abrir no escribe)")
    prop = A.ficha_para_pantalla(raiz, "c1", "20:30", ["tiktok"])
    igual(prop["huecos"][0]["hora"], "20:30", "la propuesta toma la hora de Publicar")
    ok(not prop["guardada"] and not prop["activo"], "y no está guardada ni encendida")
    ok(not os.path.exists(A._ruta(raiz)), "enseñar la propuesta no crea el fichero")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"activo": True}, REDES),
       "encender sin calendario ni estilo no se deja")
    g = A.guardar_ficha(raiz, "c1", {"activo": True, "modo": 3, "estilo": "e1",
                                     "huecos": prop["huecos"]}, REDES, rev=0)
    igual((g["activo"], g["modo"], g["rev"]), (True, 3, 1), "se guarda y sube el rev")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"modo": 2}, REDES, rev=0, codigo=409),
       "con un rev viejo: «se cambió en otro sitio» (409)")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"modo": 4}, REDES), "modo 4 no existe")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"huecos": [{"dias": [1], "hora": "25:00",
                                                        "redes": ["tiktok"]}]}, REDES),
       "una hora imposible no se deja")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"huecos": [{"dias": [], "hora": "19:00",
                                                        "redes": ["tiktok"]}]}, REDES),
       "una línea sin días no se deja")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"huecos": [{"dias": [1], "hora": "19:00",
                                                        "redes": ["myspace"]}]}, REDES),
       "una red que no existe no se deja")
    ok(lanza(A.guardar_ficha, raiz, "c1", {"inventado": 1}, REDES), "un campo inventado no")
    g = A.guardar_ficha(raiz, "c1", {"anticipacion_h": 999}, REDES, rev=1)
    igual(g["anticipacion_h"], 72, "la anticipación se acota (72 h)")
    igual(list(A.proyectos_activos(raiz)), ["c1"], "los activos")
    A.apagar(raiz, "c1", "porque sí")
    igual(A.proyectos_activos(raiz), {}, "apagar lo saca de los activos")
    A.guardar_ficha(raiz, "_sin", {"activo": False}, REDES)
    ok(A.leer_ficha(raiz, "") is not None, "«» y «_sin» son el mismo proyecto")
    with open(A._ruta(raiz), "w", encoding="utf-8") as f:
        f.write("{roto")
    ok(lanza(A.leer_ficha, raiz, "c1", codigo=503), "un fichero roto es un 503, no una ficha vacía")
    os.remove(A._ruta(raiz))


def parrilla(*guiones):
    return {"matrices": [{"id": "m1", "guiones": [
        {"id": gid, "estado": estado, "encargos": n, "codigo": gid.upper()}
        for gid, estado, n in guiones]}]}


def probar_guiones(raiz):
    print("\n  QUÉ GUION TOCA")
    par = parrilla(("g1", "usado", 1), ("g2", "publicado", 1), ("g3", "pendiente", 1),
                   ("g4", "pendiente", 2))
    cand = A.unidades_candidatas(par, "c1", {})
    igual([(c["gid"], c["indice"]) for c in cand], [("g3", 0), ("g4", 0), ("g4", 1)],
          "al encender: SOLO los pendientes; lo hecho a mano o con el nivel 1 no se toca")
    A.apuntar_unidad(raiz, "c1", "g4", 0, "v1")
    par = parrilla(("g3", "pendiente", 1), ("g4", "usado", 2))
    cand = A.unidades_candidatas(par, "c1", A.historial(raiz))
    igual([(c["gid"], c["indice"]) for c in cand], [("g3", 0), ("g4", 1)],
          "un guion «usado» por el automático sigue con su siguiente encargo")
    par = parrilla(("g4", "publicado", 2))
    igual([(c["gid"], c["indice"]) for c in A.unidades_candidatas(par, "c1", A.historial(raiz))],
          [("g4", 1)], "también si el guion ya está «publicado»")
    igual(A.unidades_candidatas(par, "c2", A.historial(raiz)), [],
          "el historial de un proyecto no vale para otro")
    ok(A.devolver_unidad(raiz, "c1", "g4", 0), "«Devolver a la lista» un encargo")
    igual([(c["gid"], c["indice"]) for c in A.unidades_candidatas(par, "c1", A.historial(raiz))],
          [("g4", 0), ("g4", 1)], "y vuelve a la lista (solo ese)")
    ok(not A.devolver_unidad(raiz, "c1", "g9", 0), "devolver uno que nunca se hizo no hace nada")

    print("\n  SE ACABAN LOS GUIONES")
    f = ficha_lmv(aviso_guiones_dias=7)
    falta = A.faltan_guiones(f, [{"gid": "g1"}], [], "c1", LUNES)
    ok(falta and falta["huecos"] == 4 and falta["guiones"] == 1, f"4 huecos en 7 días, 1 guion: {falta}")
    ok(A.faltan_guiones(f, [{"gid": "g"}] * 4, [], "c1", LUNES) is None, "con 4 guiones, no avisa")
    ok(A.faltan_guiones(f, [], [], "c1", LUNES)["ninguno"], "sin ninguno, lo dice")

    print("\n  LOS AVISOS DE PROYECTO NO SE REPITEN")
    ok(not A.ya_avisado(raiz, "guiones|c1"), "la primera vez se avisa")
    A.apuntar_aviso(raiz, "guiones|c1")
    ok(A.ya_avisado(raiz, "guiones|c1"), "la segunda, en el mismo día, no")
    A.olvidar_aviso(raiz, "guiones|c1")
    ok(not A.ya_avisado(raiz, "guiones|c1"), "si el motivo se fue, la próxima vez vuelve a avisar")


def claves(razones):
    return [r["clave"] for r in razones]


def probar_razones():
    print("\n  LAS RAZONES PARA ESPERAR")
    igual(A.razones_antes_de_gastar({}), [], "sin problemas, ninguna")
    r = A.razones_antes_de_gastar({"avisos_encargo": ["⚠ algo", "[FALTA CTA] falta"]})
    igual(claves(r), ["cta"], "«[FALTA CTA]» frena; los demás avisos del guion no")
    ok(r[0]["salta"], "y «Hacer igualmente» lo salta")
    r = A.razones_antes_de_gastar({"estilo_existe": True, "estilo_del_proyecto": False,
                                   "freno": {"pendientes": 2, "max": 2},
                                   "perfil": False, "redes_sin_cuenta": ["TikTok"]})
    igual(claves(r), ["estilo_ajeno", "perfil", "cuentas", "freno"],
          "estilo de otro proyecto, sin perfil, red sin cuenta y el freno")
    ok(not any(x["salta"] for x in r), "ninguna de esas la salta «Hacer igualmente»")
    igual(claves(A.razones_antes_de_gastar({"freno": {"pendientes": 1, "max": 2}})), [],
          "por debajo del freno, sigue")

    print("\n  DURANTE EL VÍDEO")
    igual(claves(A.razones_durante({"estado": "parado", "tipo_parada": "tope"})), ["tope"],
          "el tope de $")
    igual(claves(A.razones_durante({"estado": "parado", "tipo_parada": "interruptor"})),
          ["imagenes"], "el interruptor de imágenes")
    r = A.razones_durante({"estado": "interrumpido"})
    ok("reinició" in r[0]["texto"] and "Reintentar" in r[0]["que_hacer"],
       "interrumpido lo dice en una línea y qué hacer")
    lineas = [{"que": "El guion visual lo aprobó el piloto", "tipo": "aprobado_por_piloto"},
              {"que": "Del guion: ⚠ x", "tipo": "del_guion"},
              {"que": "La portada con IA no se hizo", "tipo": "portada_ia_tope"}]
    igual(A.razones_durante({"estado": "revisar", "revisar": lineas}), [],
          "lo rutinario de «Para revisar» NO frena el nivel 3")
    lineas.append({"que": "3 imágenes siguen marcadas", "tipo": "imagen_marcada"})
    igual(claves(A.razones_durante({"estado": "revisar", "revisar": lineas})), ["revisar"],
          "una imagen que el revisor sigue marcando, sí")
    igual(claves(A.razones_durante({"estado": "revisar", "revisar": [{"que": "viejo"}]})),
          ["revisar"], "una línea sin tipo (de antes) frena, por prudencia")

    print("\n  ANTES DE PUBLICAR")
    igual(A.razones_antes_de_publicar({}), [], "todo bien, ninguna")
    r = A.razones_antes_de_publicar({"portada": False, "textos_faltan": ["TikTok"],
                                     "mp4_cambiado": True, "guion_cambiado": True,
                                     "salio": "ya está programado", "cliente_ok": False,
                                     "desactualizada": True, "encaje_malo": ["YouTube: largo"]})
    igual(claves(r), ["portada", "textos", "encaje", "desactualizada", "mp4", "guion", "salio",
                      "cliente"], "cada una con su clave")


def envio(red, estado, eid=None, creado="2026-11-23T10:00:00", lote="l1"):
    return {"id": eid or f"{red}-{estado}", "red": red, "estado": estado, "creado": creado,
            "lote": lote}


def probar_envios():
    print("\n  LEER LOS ENVÍOS")
    auto = {"paso": "programado", "redes": ["tiktok", "youtube"], "envios_antes": ["viejo"]}
    viejo = envio("tiktok", "publicado", "viejo")
    igual(A.reconciliar(auto, [viejo])["paso"], None,
          "un envío de ANTES del intento no cuenta (se distingue por id)")
    todos = [envio("tiktok", "publicado"), envio("youtube", "publicado")]
    igual(A.reconciliar(auto, todos)["paso"], "publicado", "todas publicadas → publicado")
    mixto = [envio("tiktok", "publicado"), envio("youtube", "fallido")]
    r = A.reconciliar(auto, mixto)
    igual((r["paso"], r["aviso"]), ("fallo", "fallido"), "una fallida → fallo y aviso")
    reintento = mixto + [envio("youtube", "programado", "yt2", creado="2026-11-23T11:00:00")]
    igual(A.reconciliar(dict(auto, paso="fallo"), reintento)["paso"], "programado",
          "reintentar esa red (envío nuevo) → vuelve a programado")
    igual(A.reconciliar(auto, [envio("tiktok", "comprobar"), envio("youtube", "programado")])
          ["aviso"], "comprobar", "una subida cortada a medias avisa, sin marcar fallo")
    canc = [envio("tiktok", "cancelado"), envio("youtube", "cancelado")]
    r = A.reconciliar(auto, canc)
    igual((r["paso"], r["aviso"]), ("espera_ok", "cancelado_en_publicar"),
          "todo cancelado desde Publicar → espera tu OK, nunca vuelve a preparar")
    igual(A.reconciliar(dict(auto, paso="no_publicar"), canc)["paso"], None,
          "pero un «no publicar» con todo cancelado NO resucita")
    igual(A.reconciliar(dict(auto, paso="publicando"), [])["accion"], "sin_envios",
          "«publicando» sin ningún envío: se sabe (reinicio antes de apuntar)")
    parcial = [envio("tiktok", "programado")]
    r = A.reconciliar(dict(auto, paso="publicando"), parcial)
    igual((r["paso"], r["aviso"]), ("programado", "faltan_redes"),
          "si solo salió una red: programado, y avisa de la que falta")

    print("\n  CANCELAR (No publicar / Cambiar fecha)")
    ret = dict(auto, paso="retirando")
    igual(A.reconciliar(ret, [envio("tiktok", "programado"), envio("youtube", "programado")])
          ["accion"], "cancelar", "con programados: cancelarlos")
    igual(A.reconciliar(ret, [envio("tiktok", "enviando")])["accion"], "esperar",
          "con uno subiéndose: esperar a la siguiente vuelta")
    r = A.reconciliar(ret, [envio("tiktok", "comprobar"), envio("youtube", "cancelado")])
    igual((r["paso"], r["aviso"], r["accion"]), (None, "comprobar", "refrescar"),
          "con uno en «comprobar» NO se da por cancelado: se mira en Upload-Post y se avisa")
    igual(A.reconciliar(ret, canc)["paso"], "no_publicar", "todo cancelado → no se publica")
    r = A.reconciliar(ret, [envio("tiktok", "publicado"), envio("youtube", "cancelado")])
    igual(r["aviso"], "ya_salio", "si algo ya salió, lo dice")
    rep = dict(auto, paso="reprogramando")
    igual(A.reconciliar(rep, canc)["accion"], "programar", "reprogramando con todo cancelado → programar")
    igual(A.reconciliar(rep, [envio("tiktok", "comprobar")])["accion"], "refrescar",
          "y con un «comprobar», nunca programa otra vez (saldría dos veces)")

    print("\n  PROGRAMADO A MANO DESDE PUBLICAR (el piloto se pone al día)")
    a = {"paso": "programado", "redes": ["tiktok"], "hueco": "2026-11-24T21:00", "envios_antes": []}
    mano = [envio(r, "programado", f"m{r}") for r in ("tiktok", "instagram", "youtube")]
    for e in mano:
        e["cuando"] = "2026-11-25T16:00:00"
    c = A.sincronizar(a, mano)
    igual(c.get("redes"), ["tiktok", "instagram", "youtube"], "toma las redes que de verdad tiene Upload-Post")
    igual(c.get("hueco"), "2026-11-25T16:00", "y la hora de verdad")
    igual(A.sincronizar(dict(a, redes=["tiktok", "instagram", "youtube"], hueco="2026-11-25T16:00"), mano), {},
          "si ya casa, no toca nada")
    igual(A.sincronizar(a, []), {}, "sin envíos, nada")
    viejo = envio("facebook", "programado", "mviejo")
    viejo["cuando"] = "2026-11-20T10:00:00"
    c = A.sincronizar(a, mano + [viejo], LUNES, REDES)
    igual(c.get("hueco"), "2026-11-25T16:00", "un envío viejo sin refrescar no pone una hora pasada")
    igual(c.get("redes"), ["tiktok", "instagram", "youtube", "facebook"], "las redes en el orden de siempre")
    igual(c.get("hueco_calendario"), "2026-11-24T21:00", "y recuerda el hueco del calendario que tenía")
    f = {"id": "x" * 12, "estado": "listo", "auto": dict(a, **c, cid="c1")}
    ok("2026-11-24T21:00" in A.ocupados([f], "c1"),
       "ese hueco sigue tomado: cambiar la hora en Publicar no hace (ni paga) otro vídeo")

    print("\n  LO QUE SE ENSEÑA")
    v = video_auto("2026-11-26T19:00", paso="programado", estado="listo",
                   redes=("tiktok", "youtube"))
    e = A.estado_vivo(v, [envio("tiktok", "programado"), envio("youtube", "programado")])
    igual(e["clave"], "programado", "programado")
    ok("jue 26 a las 19:00" in e["texto"], f"con su fecha bonita: {e['texto']}")
    igual(A.estado_vivo(v, todos)["clave"], "publicado",
          "si los envíos dicen publicado, se enseña publicado aunque el paso guardado sea viejo")
    igual(A.estado_vivo(video_auto("x", estado="trabajando"))["clave"], "haciendo", "haciendo")
    igual(A.estado_vivo(video_auto("x", estado="error"))["clave"], "detenido", "detenido")
    igual(A.estado_vivo(video_auto("x", paso="espera_ok", estado="listo"))["clave"], "espera_ok",
          "espera tu OK")


def probar_piloto_con_auto(raiz):
    print("\n  EL BLOQUE «auto» EN LA COLA DEL PILOTO")
    f = P.encolar(raiz, {"cid": "c1", "gid": "g1", "estilo": "e1",
                         "auto": {"hueco": "2026-11-26T19:00", "paso": "preparando", "rev": 0}})
    igual(f["auto"]["hueco"], "2026-11-26T19:00", "la ficha guarda su bloque auto")
    n = P.encolar(raiz, {"cid": "c1", "gid": "g2", "estilo": "e1"})
    ok("auto" not in n, "uno del nivel 1 no lo lleva")
    c = P.cambiar_auto(raiz, f["id"], {"paso": "espera_ok"}, rev=0)
    igual((c["auto"]["paso"], c["auto"]["rev"]), ("espera_ok", 1), "cambia y sube el rev")
    try:
        P.cambiar_auto(raiz, f["id"], {"paso": "programado"}, rev=0)
        ok(False, "un rev viejo tenía que fallar")
    except P.RevVieja as fallo:
        ok(fallo.codigo == 409 and fallo.ficha["auto"]["paso"] == "espera_ok",
           "un rev viejo: 409 con la ficha de ahora")
    igual(P.cambiar_auto(raiz, f["id"], {"paso": "publicando"}, si_paso=("preparando",)), None,
          "con `si_paso` que no casa, no toca nada")
    ok(lanza(P.cambiar_auto, raiz, n["id"], {"paso": "x"}, codigo=409),
       "a uno del nivel 1 no se le pone paso")
    P.apuntar_revision(raiz, f["id"], "lo aprobó el piloto", "Vídeo", tipo="aprobado_por_piloto")
    igual(P.leer(raiz, f["id"])["revisar"][-1]["tipo"], "aprobado_por_piloto",
          "«Para revisar» guarda el tipo")
    # la poda no se lleva un automático vivo
    datos = P._leer(raiz)
    for i in range(P.MAX_VIDEOS + 5):
        datos["videos"].insert(0, {"id": f"{i:012x}", "estado": "listo"})
    P.cambiar(raiz, f["id"], estado="listo")
    datos = P._leer(raiz)
    for i in range(P.MAX_VIDEOS + 5):
        datos["videos"].insert(0, {"id": f"{i:012x}", "estado": "listo"})
    P._guardar(raiz, datos)
    ok(any(v["id"] == f["id"] for v in P.listar(raiz)),
       "al podar los 300, el automático que espera tu OK se queda")


# ====================================================== CON EL SERVIDOR (app.py)

class _Pet:
    headers = {}


def probar_con_el_servidor(raiz_padre):
    """El vigía y las rutas de app.py con Upload-Post, Telegram y la Parrilla
    de mentira: lo que el árbitro pidió comprobar (publicar una sola vez, nunca
    sin OK en nivel 2, «No publicar» de verdad, avisos que no se quedan…)."""
    print("\n  CON EL SERVIDOR: EL VIGÍA Y LAS RUTAS")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"      (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    from nucleo import Estado, Proyecto                           # noqa: PLC0415
    base = os.path.join(raiz_padre, "servidor")
    os.makedirs(base)
    servidor.fijar_raiz_proyectos(base)
    PUB = servidor._publicar()
    PAR = servidor._parrilla()
    pet = _Pet()
    reloj = {"ahora": dt.datetime(2026, 11, 23, 8, 0, tzinfo=dt.timezone(dt.timedelta(hours=-5)))}
    llamadas = {"enviar": [], "cancelar": [], "telegram": [], "editar": []}
    hechos_falsos = {}
    guiones = {"g1": {"estado": "pendiente"}, "g2": {"estado": "pendiente"},
               "g3": {"estado": "pendiente"}}

    pid1 = Proyecto.crear(base, "auto uno").id
    pid2 = Proyecto.crear(base, "auto dos").id
    for p_ in (pid1, pid2):
        Estado(servidor.contexto(p_).proyecto)

    def leer_envios(pid):
        return PUB._leer_video(base, pid)

    def enviar_falso(raiz, info, ajustes, cuerpo, en_hilo=True):
        llamadas["enviar"].append((info["pid"], tuple(cuerpo["redes"]), cuerpo.get("cuando")))
        datos = leer_envios(info["pid"])
        if hechos_falsos.get("enviar_falla"):
            raise PUB.ErrorPublicar(hechos_falsos["enviar_falla"], 409)
        for red in cuerpo["redes"]:
            if any(e["red"] == red and e["estado"] in PUB.VIVOS for e in datos["envios"]):
                raise PUB.ErrorPublicar("este vídeo ya está publicado o programado en X. Si de "
                                        "verdad quieres publicarlo otra vez, confírmalo.", 409)
        nuevos = []
        for red in cuerpo["redes"]:
            nuevos.append({"id": f"e{len(llamadas['enviar'])}{red[:2]}", "red": red,
                           "estado": "programado", "lote": f"l{len(llamadas['enviar'])}",
                           "job_id": "j1", "cuando": cuerpo.get("cuando") + ":00",
                           "creado": "2026-11-23T08:00:00"})
        datos["envios"].extend(nuevos)
        PUB._escribir(PUB._ruta_video(base, info["pid"]), datos)
        return nuevos

    def cancelar_falso(raiz, pid, eid):
        llamadas["cancelar"].append(eid)
        datos = leer_envios(pid)
        e = next(x for x in datos["envios"] if x["id"] == eid)
        if e["estado"] == "programado" and hechos_falsos.get("cancelar_espera"):
            raise PUB.ErrorPublicar("Upload-Post todavía no le ha dado número de trabajo", 409)
        lote = e.get("lote")
        for x in datos["envios"]:
            if x.get("lote") == lote and x["estado"] in ("programado", "espera_ok", "comprobar"):
                x["estado"] = "cancelado"
        PUB._escribir(PUB._ruta_video(base, pid), datos)
        return {}

    def poner_envios(pid, *estados):
        datos = leer_envios(pid)
        for e in datos["envios"]:
            for red, estado in estados:
                if e["red"] == red:
                    e["estado"] = estado
        PUB._escribir(PUB._ruta_video(base, pid), datos)

    def hechos_publicar(raiz, ficha):
        hechos = {"portada": True, "textos_faltan": [], "encaje_malo": [], "desactualizada": False,
                  "mp4_cambiado": False, "guion_cambiado": False, "salio": "",
                  "cliente_ok": True, "clave_upload": True, "perfil": True, "redes_sin_cuenta": []}
        hechos.update(hechos_falsos.get("publicar") or {})
        return hechos, {"pid": ficha["pid"], "cliente": "c1"}, {}

    def parrilla_listar(raiz, cid):
        return {"matrices": [{"id": "m1", "guiones": [
            {"id": g, "estado": d["estado"], "encargos": 1, "codigo": g.upper(), "titulo": "",
             "duracion_s": 60} for g, d in guiones.items()]}]}

    def parrilla_leer(raiz, cid, gid):
        if gid not in guiones:
            raise PAR.ErrorParrilla("ese guion ya no existe", 404)
        return {"id": gid, "estilo": "", "leido": {"codigo": gid.upper(), "titulo": ""},
                "encargo": [{"material": f"material {gid}", "avisos": guiones[gid].get("avisos", []),
                             "duracion_objetivo_s": 60, "formato": "vertical"}]}

    class TelegramFalso:
        ErrorTelegram = RuntimeError

        @staticmethod
        def conectado():
            return True

        @staticmethod
        def base_url():
            return "https://studio.test"

        @staticmethod
        def enviar(texto, silencioso=False, respetar_pausa=True):
            llamadas["telegram"].append(texto)
            return str(len(llamadas["telegram"]))

        @staticmethod
        def editar(mensaje, texto):
            llamadas["editar"].append((mensaje, texto))
            return True

        @staticmethod
        def estado():
            return {"conectado": True}

    cambios = {
        (servidor, "_auto_ahora"): lambda: reloj["ahora"],
        (servidor, "_auto_hechos_publicar"): hechos_publicar,
        (servidor, "_auto_existe_video"): lambda pid: pid not in hechos_falsos.get("borrados", ()),
        (servidor, "_auto_proyectos"): lambda: {"c1": "Cliente uno", "": "Sin proyecto"},
        (servidor, "_auto_estilos"): lambda: {"e1": "c1", "e2": "otro"},
        (servidor, "_auto_refrescar"): lambda lotes=(): None,
        (servidor, "publicar_ficha"): lambda pid, peticion: {},
        (servidor, "_proyecto_parrilla"): lambda cid, peticion: cid,
        # el vigía de verdad NO corre aquí: cada vuelta la da la prueba
        (servidor, "_piloto_despertar"): lambda: None,
        (servidor, "TELEGRAM"): TelegramFalso,
        (PUB, "enviar"): enviar_falso,
        (PUB, "cancelar"): cancelar_falso,
        (PUB, "estado_clave"): lambda: {"puesta": True},
        (PUB, "ajustes_de"): lambda raiz, cid: {"perfil": "p", "redes": ["tiktok"]},
        (PAR, "listar"): parrilla_listar,
        (PAR, "leer"): parrilla_leer,
    }
    viejos = {k: getattr(k[0], k[1]) for k in cambios}
    for (obj, nombre), valor in cambios.items():
        setattr(obj, nombre, valor)
    try:
        _escenarios(servidor, base, pet, reloj, llamadas, hechos_falsos, guiones, pid1, pid2,
                    poner_envios)
    finally:
        for (obj, nombre), valor in viejos.items():
            setattr(obj, nombre, valor)


def _escenarios(servidor, base, pet, reloj, llamadas, hechos_falsos, guiones, pid1, pid2,
                poner_envios):
    vuelta = servidor._auto_vuelta
    A.guardar_ficha(base, "c1", {"activo": True, "modo": 3, "estilo": "e1", "anticipacion_h": 24,
                                 "huecos": [{"dias": [1, 3, 5], "hora": "19:00",
                                             "redes": ["tiktok", "youtube"]}]}, REDES)

    def autos():
        return [f for f in P.listar(base) if A.es_automatico(f)]

    vuelta()
    igual(len(autos()), 1, "encendido en nivel 3: el vigía encola UN vídeo para el hueco de hoy")
    f1 = autos()[0]
    igual((f1["gid"], f1["auto"]["hueco"], f1["auto"]["redes"]),
          ("g1", "2026-11-23T19:00", ["tiktok", "youtube"]),
          "el primer guion pendiente, para el lunes 19:00, con las redes del hueco")
    vuelta()
    igual(len(autos()), 1, "el siguiente hueco (miércoles) aún no toca: fuera de las 24 h")
    ok("g1" not in [c["gid"] for c in A.unidades_candidatas(
        servidor._parrilla().listar(base, "c1"), "c1", A.historial(base))],
       "y g1 queda en el historial: no se vuelve a hacer")

    # el nivel 1 «termina» el vídeo
    P.cambiar(base, f1["id"], estado="listo", pid=pid1)
    import threading as _th                                       # noqa: PLC0415
    hilos = [_th.Thread(target=vuelta) for _ in range(3)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    igual(len(llamadas["enviar"]), 1, "tres vueltas a la vez: UN solo `enviar` (nunca dos veces)")
    igual(P.leer(base, f1["id"])["auto"]["paso"], "programado", "y queda programado")
    ok(any("Programado" in t for t in llamadas["telegram"]), "con su aviso (silencioso) por Telegram")
    vuelta()
    igual(len(llamadas["enviar"]), 1, "otra vuelta no lo vuelve a mandar")

    print("\n  NIVEL 2 (Y LA FICHA CAMBIADA A MITAD)")
    reloj["ahora"] = reloj["ahora"].replace(day=25)
    vuelta()                                 # encola g2 para el miércoles
    f2 = [f for f in autos() if f["gid"] == "g2"][0]
    A.guardar_ficha(base, "c1", {"modo": 2}, REDES)
    P.cambiar(base, f2["id"], estado="listo", pid=pid2)
    antes = len(llamadas["enviar"])
    vuelta()
    f2 = P.leer(base, f2["id"])
    igual(f2["auto"]["paso"], "espera_ok",
          "encolado en nivel 3 pero la ficha pasó a nivel 2: NO se publica solo, espera tu OK")
    igual(len(llamadas["enviar"]), antes, "y no se llamó a `enviar`")
    ok(any("espera tu OK" in t for t in llamadas["telegram"]), "avisa por Telegram con su enlace")
    ok(any("aprobar.html?video=" + f2["id"] in t for t in llamadas["telegram"]),
       "el enlace lleva a la página del móvil de ESE vídeo")
    vista = servidor.aprobar_ver(f2["id"], pet)
    igual((vista["vivo"]["clave"], vista["editable"]), ("espera_ok", True),
          "la página dice «espera tu OK» y deja editar")
    try:
        servidor.aprobar_publicar(f2["id"], pet, {"rev": vista["rev"] - 1})
        ok(False, "un rev viejo tenía que dar 409")
    except servidor.ErrorApi as fallo:
        ok(fallo.codigo == 409 and "otro sitio" in fallo.mensaje,
           "con un rev viejo: «Esto se cambió en otro sitio»")
    servidor.aprobar_publicar(f2["id"], pet, {"rev": vista["rev"], "desde": "movil"})
    igual(len(llamadas["enviar"]), antes + 1, "«✓ Publicar así» lo programa")
    try:
        servidor.aprobar_publicar(f2["id"], pet, {"rev": P.leer(base, f2["id"])["auto"]["rev"]})
        ok(False, "un segundo OK tenía que dar 409")
    except servidor.ErrorApi as fallo:
        ok(fallo.codigo == 409 and "Ya está aprobado" in fallo.mensaje,
           "un segundo OK (el otro sitio): «Ya está aprobado», sin volver a mandarlo")
    igual(len(llamadas["enviar"]), antes + 1, "sigue siendo un solo envío")
    igual(P.leer(base, f2["id"])["auto"]["aprobado_por"], "movil", "se apunta desde dónde se aprobó")

    print("\n  NO PUBLICAR (CON UNA SUBIDA A MEDIAS)")
    poner_envios(pid2, ("tiktok", "comprobar"))
    rev = P.leer(base, f2["id"])["auto"]["rev"]
    servidor.aprobar_no_publicar(f2["id"], pet, {"rev": rev})
    vuelta()
    f2 = P.leer(base, f2["id"])
    igual(f2["auto"]["paso"], "retirando",
          "con TikTok en «comprobar» NO se da por retirado (Upload-Post quizá lo tiene)")
    ok(any("No sé si salió" in t or "Ya lo miré" in t for t in llamadas["telegram"]),
       "y avisa de mirarlo en Upload-Post («Ya lo miré»)")
    servidor.aprobar_ya_lo_mire(f2["id"], pet, {"rev": f2["auto"]["rev"]})
    vuelta()
    vuelta()
    igual(P.leer(base, f2["id"])["auto"]["paso"], "no_publicar",
          "tras «Ya lo miré», se cancela lo demás y queda «no se publica»")
    vuelta()
    igual(P.leer(base, f2["id"])["auto"]["paso"], "no_publicar",
          "y no resucita en «espera tu OK» (todo cancelado a propósito)")

    print("\n  LA RED QUE FALLA")
    poner_envios(pid1, ("youtube", "fallido"))
    vuelta()
    f1 = P.leer(base, f1["id"])
    igual(f1["auto"]["paso"], "fallo", "YouTube falló: paso «fallo»")
    ok(any("falló" in t for t in llamadas["telegram"]), "con su aviso")
    ok(A.ocupa_hueco(f1), "y sigue ocupando su hueco (nunca se rehace el vídeo)")
    antes = len(llamadas["enviar"])
    servidor.aprobar_reintentar_red(f1["id"], pet, {"rev": f1["auto"]["rev"], "red": "youtube"})
    igual(llamadas["enviar"][-1][1], ("youtube",), "«Reintentar esta red» manda SOLO YouTube")
    igual(len(llamadas["enviar"]), antes + 1, "una vez")
    vuelta()
    igual(P.leer(base, f1["id"])["auto"]["paso"], "programado", "y vuelve a programado")
    poner_envios(pid1, ("tiktok", "publicado"), ("youtube", "publicado"))
    vuelta()
    igual(P.leer(base, f1["id"])["auto"]["paso"], "publicado", "todo publicado → publicado")
    ok(any(t.startswith("✓ Publicado") for t in llamadas["telegram"]), "y lo dice")

    print("\n  LA PARRILLA AL DÍA (SIN AVISOS VIEJOS)")
    lista = parrilla = servidor._parrilla().listar(base, "c1")
    servidor._auto_en_parrilla(lista, "c1")
    etiquetas = {g["id"]: (g.get("auto") or {}).get("clave") for g in parrilla["matrices"][0]["guiones"]}
    igual(etiquetas.get("g1"), "publicado", "g1: «✓ publicado»")
    igual(etiquetas.get("g2"), "no_publicar", "g2: «✗ no se publica»")
    g3 = [f for f in autos() if f["gid"] == "g3"]
    ok(etiquetas.get("g3") in (None, "esperando_turno", "haciendo"),
       f"g3: {etiquetas.get('g3')} {[(f['estado'], f['auto']['paso'], f.get('mensaje')) for f in g3]}")

    print("\n  PUBLICANDO SIN ENVÍOS (REINICIO A MITAD) Y EL 409 DE «YA PROGRAMADO»")
    v = P.encolar(base, {"cid": "c1", "gid": "gx", "estilo": "e1",
                         "auto": {"cid": "c1", "gid": "gx", "indice": 0, "hueco": "2026-11-27T19:00",
                                  "redes": ["tiktok"], "modo": 3, "paso": "publicando", "rev": 0,
                                  "envios_antes": []}})
    pid3 = __import__("nucleo").Proyecto.crear(base, "auto tres").id
    P.cambiar(base, v["id"], estado="listo", pid=pid3)
    antes = len(llamadas["enviar"])
    vuelta()
    igual(len(llamadas["enviar"]), antes + 1, "«publicando» sin ningún envío: se vuelve a mandar")
    igual(P.leer(base, v["id"])["auto"]["paso"], "programado", "y queda programado")
    P.cambiar_auto(base, v["id"], {"paso": "publicando"})
    vuelta()
    igual(len(llamadas["enviar"]), antes + 1,
          "«publicando» CON envíos suyos: se reconcilia, no se manda otra vez")
    igual(P.leer(base, v["id"])["auto"]["paso"], "programado", "programado")

    print("\n  RAZONES PARA ESPERAR Y CLIENTE CAMBIADO")
    guiones["g4"] = {"estado": "pendiente", "avisos": ["falta la llamada a la acción ([FALTA CTA])"]}
    A.guardar_ficha(base, "c1", {"modo": 3}, REDES)
    hechos_falsos["publicar"] = {"cliente_ok": False}
    w = P.encolar(base, {"cid": "c1", "gid": "gy", "estilo": "e1",
                         "auto": {"cid": "c1", "gid": "gy", "indice": 0, "hueco": "2026-11-30T19:00",
                                  "redes": ["tiktok"], "modo": 3, "paso": "preparando", "rev": 0}})
    pid4 = __import__("nucleo").Proyecto.crear(base, "auto cuatro").id
    P.cambiar(base, w["id"], estado="listo", pid=pid4)
    antes = len(llamadas["enviar"])
    vuelta()
    igual(P.leer(base, w["id"])["auto"]["paso"], "espera_ok",
          "el vídeo ya no es de este proyecto: nivel 3 NO lo publica (espera tu OK)")
    igual(len(llamadas["enviar"]), antes, "sin llamar a `enviar`")
    try:
        servidor.aprobar_publicar(w["id"], pet, {"rev": P.leer(base, w["id"])["auto"]["rev"]})
        ok(False, "tenía que negarse")
    except servidor.ErrorApi as fallo:
        ok(fallo.codigo == 409, "ni con tu OK lo publica en las cuentas de otro cliente")
    hechos_falsos["publicar"] = {}

    print("\n  HORA VENCIDA Y VÍDEO BORRADO")
    reloj["ahora"] = reloj["ahora"].replace(day=30, hour=19, minute=5)
    vuelta()
    w2 = P.leer(base, w["id"])
    ok(w2["auto"]["hueco"] > "2026-11-30T19:05", f"espera tu OK y su hora pasó: se mueve ({w2['auto']['hueco']})")
    ok(any("Nueva hora" in t for t in llamadas["telegram"]), "y avisa de la nueva hora")
    hechos_falsos["borrados"] = (pid4,)
    vuelta()
    igual(P.leer(base, w["id"])["auto"]["paso"], "no_publicar",
          "el vídeo se borró del Studio: «no se publica» y suelta su hueco")
    hechos_falsos["borrados"] = ()

    print("\n  ANTES DE GASTAR: [FALTA CTA] Y «HACER IGUALMENTE»")
    for f in autos():
        if f["auto"].get("paso") in A.SIN_PROGRAMAR:
            P.cambiar_auto(base, f["id"], {"paso": "no_publicar"})
    guiones["g3"]["estado"] = "usado"           # g3 «hecho a mano»: no se toca
    reloj["ahora"] = reloj["ahora"].replace(day=30, hour=8, minute=0) + dt.timedelta(days=4)
    n = len(autos())
    vuelta()
    igual(len(autos()), n, "g4 sin CTA: no se empieza (no se gasta)")
    ok(servidor._AUTO_BLOQUEOS.get("c1", {}).get("gid") == "g4", "y queda dicho qué lo frena")
    servidor.piloto_auto_hacer_igual("c1", pet, {"gid": "g4", "indice": 0})
    vuelta()
    igual(len(autos()), n + 1, "con «Hacer igualmente» sí se hace")
    igual(servidor._AUTO_BLOQUEOS.get("c1"), None, "y el freno desaparece (sin aviso viejo)")

    print("\n  LO QUE ENCONTRÓ EL ÁRBITRO DEL CÓDIGO (ronda 1)")
    PUB = servidor._publicar()
    # G2: YouTube publicado a mano desde Publicar mientras esperaba el OK
    pid5 = __import__("nucleo").Proyecto.crear(base, "auto cinco").id
    v5 = P.encolar(base, {"cid": "c1", "gid": "gz", "estilo": "e1",
                          "auto": {"cid": "c1", "gid": "gz", "indice": 0, "hueco": "2026-12-09T19:00",
                                   "redes": ["tiktok", "youtube"], "modo": 2, "paso": "espera_ok", "rev": 0,
                                   "envios_antes": []}})
    P.cambiar(base, v5["id"], estado="listo", pid=pid5)
    datos5 = PUB._leer_video(base, pid5)
    datos5["envios"].append({"id": "manual", "red": "youtube", "estado": "programado", "lote": "lm",
                             "creado": "2026-12-01T10:00:00", "cuando": "2026-12-09T19:00:00"})
    PUB._escribir(PUB._ruta_video(base, pid5), datos5)
    vuelta()
    igual(P.leer(base, v5["id"])["auto"]["paso"], "espera_ok",
          "con solo YouTube publicado a mano, sigue esperando tu OK (falta TikTok)")
    antes = len(llamadas["enviar"])
    servidor.aprobar_publicar(v5["id"], pet, {"rev": P.leer(base, v5["id"])["auto"]["rev"]})
    igual(llamadas["enviar"][antes:], [(pid5, ("tiktok",), "2026-12-09T19:00")],
          "«Publicar así» manda SOLO la red que faltaba (TikTok), no YouTube otra vez")
    # G3: el vídeo pasa a otro proyecto y se le cambia la fecha: no se programa allí
    hechos_falsos["publicar"] = {"cliente_ok": False}
    P.cambiar_auto(base, v5["id"], {"paso": "reprogramando"})
    for e in PUB._leer_video(base, pid5)["envios"]:
        pass
    datos5 = PUB._leer_video(base, pid5)
    for e in datos5["envios"]:
        e["estado"] = "cancelado"
    PUB._escribir(PUB._ruta_video(base, pid5), datos5)
    antes = len(llamadas["enviar"])
    vuelta()
    igual(len(llamadas["enviar"]), antes,
          "reprogramar un vídeo que ya no es de este proyecto NO llama a `enviar` (todas las vías)")
    igual(P.leer(base, v5["id"])["auto"]["paso"], "espera_ok", "y espera tu OK con el aviso")
    hechos_falsos["publicar"] = {}
    # G4: «No publicar» y después «Reintentar» del nivel 1: no se rehace
    v6 = P.encolar(base, {"cid": "c1", "gid": "gw", "estilo": "e1",
                          "auto": {"cid": "c1", "gid": "gw", "indice": 0, "hueco": "2026-12-11T19:00",
                                   "redes": ["tiktok"], "modo": 2, "paso": "preparando", "rev": 0}})
    servidor.aprobar_no_publicar(v6["id"], pet, {"rev": 0})
    try:
        servidor.piloto_seguir(v6["id"], pet, {})
        ok(False, "«Reintentar» de un «No publicar» tenía que negarse")
    except servidor.ErrorApi as fallo:
        ok(fallo.codigo == 409 and "Devolver" in fallo.mensaje,
           "«Reintentar» tras «No publicar» se niega y dice «Devolver a la lista»")
    # G1: Publicar en un vídeo sin textos: el `antes` no da 409 falso
    with open(servidor.__file__, encoding="utf-8") as fh:
        fuente = fh.read()
    ok('for r in _publicar().REDES}' in fuente.split("def publicar_ficha", 1)[1].split("\ndef ", 1)[0],
       "las huellas de Publicar traen TODAS las redes (también las que aún no tienen texto)")
    ok(A.huella({}) == A.huella({}) and A.huella({}) != "", "la huella de una red vacía es estable")
    # ronda 2, G1: «No publicar» + devolver un vídeo TERMINADO: se vuelve a hacer
    guiones["gv"] = {"estado": "pendiente"}
    for f in autos():
        if f["auto"].get("paso") in A.SIN_PROGRAMAR:
            P.cambiar_auto(base, f["id"], {"paso": "no_publicar"})
    for g in list(guiones):
        if g != "gv":
            guiones[g]["estado"] = "usado"
    A.guardar_ficha(base, "c1", {"max_pendientes": 5}, REDES)
    vuelta()
    hechos_v = [f for f in autos() if f["gid"] == "gv"]
    igual(len(hechos_v), 1, "el guion gv se encola")
    P.cambiar(base, hechos_v[0]["id"], estado="listo", pid=pid5)
    P.cambiar_auto(base, hechos_v[0]["id"], {"paso": "espera_ok", "envios_antes": [
        e["id"] for e in PUB._leer_video(base, pid5)["envios"]]})
    r = servidor.aprobar_no_publicar(hechos_v[0]["id"], pet,
                                     {"rev": P.leer(base, hechos_v[0]["id"])["auto"]["rev"], "devolver": True})
    ok(r.get("devuelto"), "«No publicar» con la casilla: devuelto")
    vuelta()
    igual(len([f for f in autos() if f["gid"] == "gv"]), 2,
          "y el encargo devuelto SE VUELVE A HACER (aunque el vídeo viejo esté terminado)")
    # ronda 2, m1: un «pendiente» sin ficha (reinicio a mitad) vuelve a la lista
    A.apuntar_unidad(base, "c1", "gq", 0, "pendiente")
    A.limpiar_pendientes(base, P.listar(base))
    ok(A.historial(base)[A.clave_unidad("c1", "gq", 0)]["devuelto"],
       "un encargo apuntado sin vídeo (reinicio entre apuntar y encolar) vuelve a la lista")
    # ronda 3: CON vídeo (reinicio entre encolar y apuntar su id): no se devuelve
    guiones["gp"] = {"estado": "pendiente"}
    vp = P.encolar(base, {"cid": "c1", "gid": "gp", "estilo": "e1",
                          "auto": {"cid": "c1", "gid": "gp", "indice": 0, "hueco": "2026-12-20T19:00",
                                   "redes": ["tiktok"], "modo": 2, "paso": "preparando", "rev": 0}})
    A.apuntar_unidad(base, "c1", "gp", 0, "pendiente")
    vuelta()
    entrada = A.historial(base)[A.clave_unidad("c1", "gp", 0)]
    ok(entrada["vid"] == vp["id"] and not entrada["devuelto"],
       "un «pendiente» CON vídeo se queda con su vídeo, sin devolverlo")
    servidor.aprobar_no_publicar(vp["id"], pet, {"rev": P.leer(base, vp["id"])["auto"]["rev"], "devolver": False})
    vuelta()
    igual(len([f for f in autos() if f["gid"] == "gp"]), 1,
          "y «No publicar» sin devolver NO lo vuelve a hacer")
    # redes desde la página del móvil (pedido del dueño, 24-11)
    escritos = []
    viejo_pf, viejo_et = servidor.publicar_ficha, servidor.publicar_escribir_textos
    estado_pf = {"escribiendo": False}
    servidor.publicar_ficha = lambda pid, peticion: {
        "textos": {"tiktok": {"descripcion": "hola"}, "facebook": {"descripcion": "sin título"}},
        "redes_visibles": ["tiktok", "youtube", "facebook"], "escribiendo": estado_pf["escribiendo"]}
    servidor.publicar_escribir_textos = lambda pid, peticion, cuerpo: escritos.append(cuerpo["redes"])
    try:
        v7 = P.encolar(base, {"cid": "c1", "gid": "gr", "estilo": "e1",
                              "auto": {"cid": "c1", "gid": "gr", "indice": 0, "hueco": "2026-12-22T19:00",
                                       "redes": ["tiktok"], "modo": 2, "paso": "espera_ok", "rev": 0}})
        pid7 = __import__("nucleo").Proyecto.crear(base, "auto siete").id
        P.cambiar(base, v7["id"], estado="listo", pid=pid7)
        r = servidor.aprobar_redes(v7["id"], pet, {"rev": 0, "redes": ["youtube", "tiktok"]})
        igual(P.leer(base, v7["id"])["auto"]["redes"], ["tiktok", "youtube"],
              "«Guardar redes» cambia en qué redes sale el vídeo")
        igual(escritos, [["youtube"]], "y Claude escribe el texto SOLO de la red nueva")
        igual(r.get("escribiendo_redes"), ["youtube"], "la página sabe que se está escribiendo")
        try:
            servidor.aprobar_redes(v7["id"], pet, {"rev": 0, "redes": ["tiktok"]})
            ok(False, "un rev viejo tenía que dar 409")
        except servidor.ErrorApi as fallo:
            ok(fallo.codigo == 409, "con un rev viejo, 409 «otro sitio»")
        rev7 = P.leer(base, v7["id"])["auto"]["rev"]
        try:
            servidor.aprobar_redes(v7["id"], pet, {"rev": rev7, "redes": ["instagram"]})
            ok(False, "una red que el proyecto no tiene tenía que negarse")
        except servidor.ErrorApi as fallo:
            ok(fallo.codigo == 400, "una red que no es del proyecto no se deja")
        estado_pf["escribiendo"] = True
        try:
            servidor.aprobar_redes(v7["id"], pet, {"rev": rev7, "redes": ["tiktok", "youtube", "facebook"]})
            ok(False, "con Claude escribiendo tenía que esperar")
        except servidor.ErrorApi as fallo:
            ok(fallo.codigo == 409 and "escribiendo" in fallo.mensaje,
               "con Claude escribiendo, otra red espera (no se queda sin texto)")
        igual(P.leer(base, v7["id"])["auto"]["redes"], ["tiktok", "youtube"], "y no se tocó nada")
        estado_pf["escribiendo"] = False
        escritos.clear()
        servidor.aprobar_redes(v7["id"], pet, {"rev": rev7, "redes": ["tiktok", "youtube", "facebook"]})
        igual(escritos, [["youtube", "facebook"]],
              "una red con título que solo trae descripción también se manda a escribir")
        P.cambiar_auto(base, v7["id"], {"paso": "programado"})
        try:
            servidor.aprobar_redes(v7["id"], pet, {"rev": P.leer(base, v7["id"])["auto"]["rev"], "redes": ["tiktok"]})
            ok(False, "ya programado no se cambian las redes")
        except servidor.ErrorApi as fallo:
            ok(fallo.codigo == 409, "ya programado no se cambian las redes aquí")
    finally:
        servidor.publicar_ficha, servidor.publicar_escribir_textos = viejo_pf, viejo_et
    # m7: un aviso de Telegram no sube el rev (no da un «otro sitio» falso)
    rev = P.leer(base, v6["id"])["auto"]["rev"]
    servidor._auto_avisar(base, P.leer(base, v6["id"]), "razon", "prueba", clave="prueba_rev")
    igual(P.leer(base, v6["id"])["auto"]["rev"], rev, "mandar un aviso no cambia el rev de la página")


def main():
    raiz = tempfile.mkdtemp(prefix="prueba_piloto_auto_")
    try:
        probar_huecos()
        probar_ficha(raiz)
        probar_guiones(raiz)
        probar_razones()
        probar_envios()
        probar_piloto_con_auto(raiz)
        probar_con_el_servidor(raiz)
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    print(f"\n  {_ok} comprobaciones bien, {len(_fallos)} fallos")
    return 1 if _fallos else 0


if __name__ == "__main__":
    sys.exit(main())

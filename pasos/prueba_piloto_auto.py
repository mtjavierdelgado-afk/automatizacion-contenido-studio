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


def main():
    raiz = tempfile.mkdtemp(prefix="prueba_piloto_auto_")
    try:
        probar_huecos()
        probar_ficha(raiz)
        probar_guiones(raiz)
        probar_razones()
        probar_envios()
        probar_piloto_con_auto(raiz)
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    print(f"\n  {_ok} comprobaciones bien, {len(_fallos)} fallos")
    return 1 if _fallos else 0


if __name__ == "__main__":
    sys.exit(main())

"""Prueba de pasos/piloto.py: la cola, los ajustes y el interruptor.

Sin servidor, sin red y sin gastar nada: solo los datos y las decisiones. Lo
que encadena los pasos (app.py, bloque PILOTO) lo prueba `prueba_api.py`
(sección «EL PILOTO»).

    python pasos/prueba_piloto.py
"""
import os
import shutil
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

import piloto as P  # noqa: E402

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
    except P.ErrorPiloto as fallo:
        return codigo is None or fallo.codigo == codigo
    return False


def probar_interruptor():
    print("\n  EL INTERRUPTOR")
    igual(P.decidir("seguir", 0, 40)[0], "seguir", "sin marcadas se sigue en «seguir»")
    igual(P.decidir("parar", 0, 40)[0], "seguir", "sin marcadas se sigue también en «parar»")
    igual(P.decidir("mezcla", 0, 40)[0], "seguir", "y en «mezcla»")
    igual(P.decidir("seguir", 30, 40)[0], "seguir", "«seguir» monta aunque queden muchas")
    igual(P.decidir("parar", 1, 40)[0], "parar", "«parar» para con una sola marcada")
    igual(P.decidir("mezcla", 2, 40, 25)[0], "seguir", "«mezcla»: 2 de 40 (5 %) sigue")
    igual(P.decidir("mezcla", 10, 40, 25)[0], "seguir", "«mezcla»: 10 de 40 es justo el 25 %: sigue")
    igual(P.decidir("mezcla", 11, 40, 25)[0], "parar", "«mezcla»: 11 de 40 (27,5 %) para")
    igual(P.decidir("mezcla", 3, 10, 50)[0], "seguir", "el umbral se puede cambiar (30 % de 50 %)")
    igual(P.decidir("mezcla", 1, 0, 25)[0], "parar", "sin planos que contar, una marcada para")
    porque = P.decidir("mezcla", 11, 40, 25)[1]
    ok("27 %" in porque or "28 %" in porque, f"el motivo dice el porcentaje: {porque}")
    ok("1 imagen sigue marcada" in P.decidir("seguir", 1, 9)[1], "en singular con una")
    ok(P.da_vistos_buenos("seguir") and P.da_vistos_buenos("mezcla")
       and not P.da_vistos_buenos("parar"),
       "los vistos buenos los da el piloto en «seguir» y «mezcla», no en «parar»")


def probar_ajustes(raiz):
    print("\n  LOS AJUSTES")
    a = P.ajustes(raiz)
    igual(a["si_falla"], "mezcla", "de fábrica, la mezcla con regla")
    igual(a["umbral_pct"], 25, "con el 25 %")
    igual(a["portadas"], "ambas", "y las dos portadas (opción C)")
    igual(a["tope_usd"], 5.0, "el tope por vídeo, 5 $")
    nuevos = P.guardar_ajustes(raiz, {"si_falla": "parar", "umbral_pct": 40, "vueltas": 9,
                                      "tope_usd": "3.5"})
    igual(nuevos["si_falla"], "parar", "se guarda el interruptor")
    igual(nuevos["vueltas"], 5, "las rondas se recortan a su máximo (5)")
    igual(nuevos["tope_usd"], 3.5, "el tope acepta texto con número")
    ok(lanza(P.guardar_ajustes, raiz, {"si_falla": "a veces"}), "un modo que no existe no se guarda")
    ok(lanza(P.guardar_ajustes, raiz, {"otra_cosa": 1}), "un ajuste que no existe tampoco")
    ok(lanza(P.guardar_ajustes, raiz, {"tope_usd": "nan"}), "ni un NaN")
    igual(P.ajustes(raiz)["si_falla"], "parar", "y lo bueno guardado sigue ahí")
    P.guardar_ajustes(raiz, {"si_falla": "mezcla", "vueltas": 2, "tope_usd": 5, "umbral_pct": 25})


def probar_cola(raiz):
    print("\n  LA COLA")
    ok(lanza(P.encolar, raiz, {"gid": "g1"}), "sin estilo no entra")
    ok(lanza(P.encolar, raiz, {"estilo": "e1"}), "sin guion tampoco")
    ok(lanza(P.encolar, raiz, {"gid": "g1", "estilo": "e1", "formato": "cuadrado"}),
       "un formato que no existe no entra")
    ok(lanza(P.encolar, raiz, {"gid": "g1", "estilo": "e1", "duracion_s": 2}),
       "una duración de 2 s no entra")
    a = P.encolar(raiz, {"cid": "c1", "gid": "g1", "estilo": "e1", "duracion_s": 30,
                         "formato": "vertical", "ajustes": {"si_falla": "seguir", "a_la_vez": 4}})
    igual(a["estado"], "en_cola", "un vídeo nuevo entra en cola")
    igual(a["ajustes"], {"si_falla": "seguir"}, "con SUS ajustes (y sin «a la vez», que es de todos)")
    igual(P.ajustes_del_video(raiz, a)["si_falla"], "seguir", "que mandan sobre los generales")
    ok(lanza(P.encolar, raiz, {"cid": "c1", "gid": "g1", "estilo": "e1"}, codigo=409),
       "el mismo guion no entra dos veces a la vez (sería pagar dos vídeos)")
    b = P.encolar(raiz, {"cid": "c1", "gid": "g2", "estilo": "e1"})
    c = P.encolar(raiz, {"cid": "c1", "gid": "g3", "estilo": "e1"})
    igual([v["id"] for v in P.siguientes(raiz, 2)], [a["id"], b["id"]],
          "con dos a la vez arrancan los dos primeros, por orden de llegada")
    P.cambiar(raiz, a["id"], estado="trabajando")
    igual([v["id"] for v in P.siguientes(raiz, 2)], [b["id"]], "con uno trabajando, queda un hueco")
    ok(lanza(P.quitar, raiz, a["id"], codigo=409), "uno trabajando no se quita sin pararlo")
    ok(lanza(P.cambiar, raiz, a["id"], estado="volando"), "un estado que no existe no se escribe")
    ok(lanza(P.cambiar, raiz, a["id"], gid="otro"), "ni un campo que no se cambia desde fuera")
    P.apuntar_revision(raiz, a["id"], "mira S003", "Imágenes")
    P.apuntar_revision(raiz, a["id"], "mira S003", "Imágenes")
    igual(len(P.leer(raiz, a["id"])["revisar"]), 1, "«Para revisar» no repite la misma línea")
    # el reinicio del servicio
    igual(P.al_arrancar(raiz), 1, "al reiniciar, lo que trabajaba pasa a interrumpido")
    igual(P.leer(raiz, a["id"])["estado"], "interrumpido", "y no arranca solo")
    ok(lanza(P.preparar_reintento, raiz, b["id"], codigo=409), "uno en cola no se «retoma»")
    r = P.preparar_reintento(raiz, a["id"], forzar_seguir=True)
    igual((r["estado"], r["saltar"]), ("en_cola", ""),
          "«Seguir igualmente» sin una parada con tipo no salta nada")
    P.cambiar(raiz, a["id"], estado="parado", tipo_parada="tope")
    r = P.preparar_reintento(raiz, a["id"], forzar_seguir=True)
    igual((r["estado"], r["saltar"]), ("en_cola", "tope"),
          "«Seguir igualmente» tras el tope salta SOLO el tope")
    P.cambiar(raiz, a["id"], estado="error")
    igual(P.preparar_reintento(raiz, a["id"])["saltar"], "",
          "y «Reintentar» (sin forzar) no salta nada")
    ok(P.arrancar(raiz, a["id"]) is not None, "arrancar lo pasa a trabajando")
    ok(P.arrancar(raiz, a["id"]) is None, "y no arranca dos veces")
    P.cambiar(raiz, b["id"], estado="cancelado")
    ok(P.arrancar(raiz, b["id"]) is None, "uno parado entre mirar y arrancar no arranca")
    ok(lanza(P.encolar, raiz, {"cid": "c1", "gid": "g2", "estilo": "e1"}, codigo=409),
       "un guion con un vídeo parado no crea otro (se retoma el que hay)")
    P.cambiar(raiz, b["id"], estado="en_cola")
    P.cambiar(raiz, a["id"], estado="trabajando")
    P.cambiar(raiz, c["id"], estado="parado")
    s = P.resumen(raiz)
    igual(s["cuenta"]["parado"], 1, "el resumen cuenta los parados")
    igual(s["a_revisar"], 1, "y los que van a «Necesita revisión»")
    igual(s["videos"][0]["id"], c["id"], "lo más nuevo primero")
    P.quitar(raiz, c["id"])
    ok(all(v["id"] != c["id"] for v in P.listar(raiz)), "quitar lo quita de la lista")
    ok(lanza(P.leer, raiz, "../etc", codigo=404), "un id raro es un 404, no una ruta")


def probar_fichero_roto(raiz):
    print("\n  UN FICHERO ROTO NO SE PISA")
    ruta = os.path.join(P.carpeta(raiz), "piloto.json")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("{ esto no es json")
    ok(lanza(P.encolar, raiz, {"gid": "g9", "estilo": "e1"}, codigo=503),
       "con el fichero ilegible no se encola (se escribiría una cola vacía encima)")
    with open(ruta, "r", encoding="utf-8") as fh:
        ok(fh.read().startswith("{ esto"), "y el fichero sigue como estaba")
    igual(P.al_arrancar(raiz), 0, "al arrancar con el fichero roto no se toca nada")


def probar_la_lista(raiz_padre):
    """Rama piloto-lista (11-11-2026): lo que ya salió sale solo de la lista, y
    una parada por «tiene algo en marcha» se retoma sola cuando acaba."""
    print("\n  LA LISTA: LO QUE YA SALIÓ Y LO QUE ESPERABA (app.py)")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"      (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    from nucleo import Estado, Proyecto                           # noqa: PLC0415
    base = os.path.join(raiz_padre, "lista")
    os.makedirs(base)
    servidor.fijar_raiz_proyectos(base)
    PUB = servidor._publicar()
    pid = Proyecto.crear(base, "y12 cuatro cambios").id
    Estado(servidor.contexto(pid).proyecto)
    ok(not servidor._video_salio(pid), "un vídeo sin nada en Publicar no ha salido")
    PUB.marcar_copiado(base, pid, "tiktok")
    ok(servidor._video_salio(pid), "copiar sus textos para publicar a mano cuenta como salido")
    ok("tiktok" in (PUB._leer_video(base, pid).get("copiado") or {}),
       "y se apunta en su ficha de Publicar, por red")
    otro = Proyecto.crear(base, "y13 entrada").id
    Estado(servidor.contexto(otro).proyecto)
    ficha = PUB._leer_video(base, otro)
    for estado, sale in (("espera_ok", False), ("fallido", False), ("programado", True),
                         ("publicado", True), ("a_mano", True)):
        ficha["envios"] = [{"id": "e1", "red": "youtube", "estado": estado}]
        PUB._escribir(PUB._ruta_video(base, otro), ficha)
        igual(servidor._video_salio(otro), sale, f"un envío «{estado}» {'sí' if sale else 'no'} cuenta como salido")
    ficha["envios"] = [{"id": "e1", "red": "youtube", "estado": "comprobar"}]
    PUB._escribir(PUB._ruta_video(base, otro), ficha)
    ok(not servidor._video_salio(otro), "uno «comprobar» (subida cortada, hay que mirarlo) NO cuenta")
    ficha["envios"] = [{"id": "e1", "red": "youtube", "estado": "publicado"}]
    PUB._escribir(PUB._ruta_video(base, otro), ficha)
    v = P.encolar(base, {"cid": "c1", "gid": "gl1", "estilo": "e1"})
    P.cambiar(base, v["id"], estado="listo", pid=otro)
    igual(servidor._piloto_para_pantalla(P.leer(base, v["id"])).get("salio"), True,
          "la pantalla recibe «salio» de un vídeo listo y publicado")
    P.cambiar(base, v["id"], estado="error")
    ok("salio" not in servidor._piloto_para_pantalla(P.leer(base, v["id"])),
       "uno con error no se aparta aunque esté publicado (sigue necesitándote)")
    P.cambiar(base, v["id"], estado="listo")
    w = P.encolar(base, {"cid": "c1", "gid": "gl2", "estilo": "e1"})
    P.cambiar(base, w["id"], estado="trabajando", pid=pid)
    ok("salio" not in servidor._piloto_para_pantalla(P.leer(base, w["id"])),
       "uno trabajando no se mira (no hace falta leer Publicar cada dos segundos)")
    # la parada por «ocupado» se retoma sola; las demás no
    libre = Proyecto.crear(base, "y14 sin publicar").id
    Estado(servidor.contexto(libre).proyecto)
    P.cambiar(base, w["id"], estado="parado", tipo_parada="ocupado", porque="tiene algo en marcha",
              pid=libre)
    x = P.encolar(base, {"cid": "c1", "gid": "gl3", "estilo": "e1"})
    P.cambiar(base, x["id"], estado="parado", tipo_parada="tope", pid=pid, porque="el tope")
    real = servidor._piloto_ocupado
    try:
        servidor._piloto_ocupado = lambda _pid: False
        servidor._piloto_retomar_ocupados(P, base)
        igual(P.leer(base, w["id"])["estado"], "parado",
              "una parada de antes de un reinicio NO se retoma sola (la decide una persona)")
        ok(servidor._piloto_para_pantalla(P.leer(base, w["id"])).get("espera_sola") is False,
           "y la pantalla no dice «sigue solo»")
        servidor._PILOTO_ESPERAS.add(w["id"])          # como si se hubiera parado aquí
        servidor._PILOTO_ESPERAS.add(x["id"])
        ok(servidor._piloto_para_pantalla(P.leer(base, w["id"])).get("espera_sola") is True,
           "una de este proceso sí dice «sigue solo»")
        servidor._piloto_ocupado = lambda _pid: True
        servidor._piloto_retomar_ocupados(P, base)
        igual(P.leer(base, w["id"])["estado"], "parado", "mientras el vídeo sigue ocupado, espera")
        servidor._piloto_ocupado = lambda _pid: False
        servidor._piloto_retomar_ocupados(P, base)
        igual(P.leer(base, w["id"])["estado"], "en_cola",
              "en cuanto termina lo que tenía en marcha, vuelve solo a la cola")
        ok("retomado solo" in P.leer(base, w["id"])["mensaje"], "y lo dice")
        igual(P.leer(base, x["id"])["estado"], "parado",
              "una parada por el tope NO se retoma sola (la decide el dueño)")
        igual(P.preparar_reintento(base, x["id"], solo_si_tipo="ocupado"), None,
              "y retomar «solo si sigue ocupado» no toca una parada por otra cosa")
        y = P.encolar(base, {"cid": "c1", "gid": "gl4", "estilo": "e1"})
        P.cambiar(base, y["id"], estado="parado", tipo_parada="ocupado", pid=otro)
        servidor._PILOTO_ESPERAS.add(y["id"])
        servidor._piloto_retomar_ocupados(P, base)
        igual(P.leer(base, y["id"])["estado"], "parado",
              "uno que ya salió en Publicar no se retoma (no se vuelve a montar ni a escribir)")
    finally:
        servidor._piloto_ocupado = real
    # TERMINADO A MANO (rama piloto-al-dia, X01 e Y05 del 12-11): falló antes del
    # montaje, alguien lo arregló y lo montó; la tarjeta lo dice y no pide «Reintentar»
    igual(servidor._piloto_render_al_dia(libre), False, "un vídeo sin montar no tiene el montaje al día")
    igual(servidor._piloto_render_al_dia("no_existe_este_video"), False, "uno que no existe, tampoco")
    # el de verdad, con un vídeo de mentira: render «listo», «obsoleto» y con algo en marcha
    real_ctx = servidor.contexto
    falso = {"render": "listo", "activos": []}

    class _Est:
        def estado_de(self, paso):
            return falso["render"] if paso == "render" else "listo"

    class _Ges:
        def listar(self, activos=False):
            return list(falso["activos"])

    ctx_falso = type("Ctx", (), {"estado": _Est(), "gestor": _Ges()})()
    try:
        servidor.contexto = lambda _pid: ctx_falso
        servidor._PILOTO_RENDER.clear()
        igual(servidor._piloto_render_al_dia(libre), True, "con el render «listo» y nada en marcha, al día")
        falso["activos"] = [{"id": "t1"}]
        igual(servidor._piloto_render_al_dia(libre), False,
              "con algo en marcha, NO (aunque su estado.json no haya cambiado: se mira cada vez)")
        falso["activos"] = []
        servidor._PILOTO_RENDER.clear()
        falso["render"] = "obsoleto"
        igual(servidor._piloto_render_al_dia(libre), False, "con el render «obsoleto», NO")
        falso["render"] = "listo"
        igual(servidor._piloto_render_al_dia(libre), False,
              "(lo recuerda mientras su estado.json no cambie: no se abre en cada vuelta)")
    finally:
        servidor.contexto = real_ctx
        servidor._PILOTO_RENDER.clear()
    t = P.encolar(base, {"cid": "c1", "gid": "gl5", "estilo": "e1"})
    P.cambiar(base, t["id"], estado="error", etapa="imagenes", pid=libre,
              porque="dos o mas planos han acabado con la MISMA imagen")
    real_al_dia = servidor._piloto_render_al_dia
    try:
        servidor._piloto_render_al_dia = lambda _pid: False
        ok("terminado_a_mano" not in servidor._piloto_para_pantalla(P.leer(base, t["id"])),
           "falló y su vídeo NO está montado: sigue en «Falló»")
        servidor._piloto_render_al_dia = lambda _pid: True
        pantalla = servidor._piloto_para_pantalla(P.leer(base, t["id"]))
        ok(pantalla.get("terminado_a_mano") is True and pantalla.get("salio") is False,
           "falló en las imágenes y su vídeo ya está montado al día: «Terminado a mano», por publicar")
        igual(P.leer(base, t["id"])["estado"], "error", "(y la ficha del piloto no se toca: solo se lee)")
        P.cambiar(base, t["id"], etapa="portadas")
        ok("terminado_a_mano" not in servidor._piloto_para_pantalla(P.leer(base, t["id"])),
           "uno que falló DESPUÉS del montaje (portadas) no es «terminado a mano»: le falta eso")
        P.cambiar(base, t["id"], estado="parado", etapa="vistos", tipo_parada="tope")
        ok(servidor._piloto_para_pantalla(P.leer(base, t["id"])).get("terminado_a_mano") is True,
           "una parada antes del montaje y luego montado a mano, también")
        P.cambiar(base, t["id"], estado="cancelado")
        ok("terminado_a_mano" not in servidor._piloto_para_pantalla(P.leer(base, t["id"])),
           "uno parado por ti se queda como lo dejaste")
        P.cambiar(base, t["id"], estado="error", etapa="imagenes")
        peticion = type("Pet", (), {"headers": {}})()
        servidor._piloto_render_al_dia = lambda _pid: _pid == libre
        con_mano = servidor.piloto_estado(peticion)["a_revisar"]
        servidor._piloto_render_al_dia = lambda _pid: False
        sin_mano = servidor.piloto_estado(peticion)["a_revisar"]
        igual(sin_mano - con_mano, 1, "y no cuenta en «N para revisar»")
    finally:
        servidor._piloto_render_al_dia = real_al_dia
    ok(not servidor._piloto_ocupado(pid), "un vídeo sin trabajos no está ocupado")
    ok(servidor._piloto_ocupado("no_existe_este_video"), "uno que no existe se da por ocupado (no se retoma)")


def main():
    raiz = tempfile.mkdtemp(prefix="prueba_piloto_")
    try:
        probar_interruptor()
        probar_ajustes(raiz)
        probar_cola(raiz)
        probar_fichero_roto(raiz)
        probar_la_lista(raiz)
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    print(f"\n  {_ok} comprobaciones bien, {len(_fallos)} fallos")
    return 1 if _fallos else 0


if __name__ == "__main__":
    sys.exit(main())

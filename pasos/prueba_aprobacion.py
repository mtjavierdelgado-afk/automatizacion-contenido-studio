"""Prueba de la APROBACIÓN DEL CLIENTE POR ENLACE (rama publicar-redes-3).

    python pasos/prueba_aprobacion.py

Sin red y sin claves: el módulo (`pasos/aprobacion.py`), el bloqueo en
`publicar.enviar` y las rutas del dueño y del cliente con el servidor de
verdad (TestClient) sobre una carpeta de proyectos temporal.
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))
CARPETA = tempfile.mkdtemp(prefix="estudio_aprobacion_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_AJUSTES"] = os.path.join(CARPETA, "ajustes.json")
os.environ.pop("UPLOADPOST_API_KEY", None)
os.environ.setdefault("ESTUDIO_SIMULAR", "1")

from pasos import aprobacion as A  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
    else:
        _fallos.append(mensaje)
        print(f"      FALLO: {mensaje}")


def _raiz():
    return tempfile.mkdtemp(prefix="aprob_", dir=CARPETA)


def _fichero(raiz):
    with open(os.path.join(raiz, "_sistema", "publicar", "aprobaciones.json"), encoding="utf-8") as fh:
        return fh.read()


def _caducar(raiz, token):
    datos = json.loads(_fichero(raiz))
    datos["enlaces"][A.huella_token(token)]["caduca"] = "2000-01-01T00:00:00"
    with open(os.path.join(raiz, "_sistema", "publicar", "aprobaciones.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh)


def prueba_modulo():
    print("\n[1] el enlace: token, huella, caducidad y anular")
    raiz = _raiz()
    hecho = A.crear(raiz, "v1", huella="h1")
    token = hecho["token"]
    ok(len(token) >= 40 and A._FORMA_TOKEN.match(token), "el token es largo y de letras seguras")
    ok(token not in _fichero(raiz), "en disco NO está el token")
    ok(A.huella_token(token) in _fichero(raiz), "en disco está solo su huella")
    ok("token" not in hecho["enlace"] and A.huella_token(token) not in json.dumps(hecho["enlace"]),
       "lo que ve la pantalla no lleva ni el token ni la huella")
    ok(A.de_token(raiz, token)["pid"] == "v1", "el token abre su vídeo")
    ok(A.de_token(raiz, token[:-1] + ("a" if token[-1] != "a" else "b")) is None, "uno parecido, no")
    ok(A.de_token(raiz, "../../etc/passwd") is None and A.de_token(raiz, "") is None
       and A.de_token(raiz, None) is None, "uno mal formado, tampoco (sin error)")
    caduca = dt.datetime.fromisoformat(hecho["enlace"]["caduca"])
    creado = dt.datetime.fromisoformat(hecho["enlace"]["creado"])
    ok((caduca - creado).days == A.DIAS_DEFECTO, f"dura {A.DIAS_DEFECTO} días por defecto")
    for malos in (0, 31, "x", -1):
        try:
            A.crear(raiz, "v1", dias=malos)
            ok(False, f"días={malos!r} no se acepta")
        except A.ErrorAprobacion:
            ok(True, "")
    ok(A.de_token(raiz, token) is not None, "un intento malo no anula el bueno")
    otro = A.crear(raiz, "v1", dias=3, huella="h1")
    ok(A.de_token(raiz, token) is None, "pedir otro enlace anula el anterior")
    ok(A.de_token(raiz, otro["token"]) is not None, "y el nuevo vale")
    ok(A.de_video(raiz, "v1")["id"] == otro["enlace"]["id"], "la ficha ve el último")
    A.anular(raiz, "v1", otro["enlace"]["id"])
    ok(A.de_token(raiz, otro["token"]) is None, "anulado, ya no abre")
    ok(A.de_video(raiz, "v1")["vigente"] is False, "y la ficha lo dice")
    try:
        A.anular(raiz, "otro", otro["enlace"]["id"])
        ok(False, "no se anula el enlace de otro vídeo")
    except A.ErrorAprobacion as fallo:
        ok(fallo.codigo == 404, "anular el enlace de otro vídeo es 404")
    tercero = A.crear(raiz, "v1")
    _caducar(raiz, tercero["token"])
    ok(A.de_token(raiz, tercero["token"]) is None, "caducado, ya no abre")
    ok(A.espera_al_cliente(raiz, "v1") == "", "y caducado ya no para el vídeo")
    try:
        A.responder(raiz, tercero["token"], "aprobado")
        ok(False, "un enlace caducado no puede responder")
    except A.ErrorAprobacion as fallo:
        ok(fallo.codigo == 404, "responder con un enlace caducado es 404")
    datos = json.loads(_fichero(raiz))
    datos["enlaces"][A.huella_token(tercero["token"])]["caduca"] = "2000-01-01T00:00:00"
    with open(os.path.join(raiz, "_sistema", "publicar", "aprobaciones.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh)
    A.crear(raiz, "v1")
    ok(A.huella_token(tercero["token"]) not in _fichero(raiz), "lo caducado hace mucho se olvida al pedir otro")


def prueba_respuestas():
    print("\n[2] el cliente contesta, y lo que para al vídeo")
    raiz = _raiz()
    token = A.crear(raiz, "v2", huella="h1")["token"]
    ok(A.espera_al_cliente(raiz, "v2", "h1") == "pendiente", "sin contestar: espera")
    ok(A.espera_al_cliente(raiz, "otro", "h1") == "", "otro vídeo no espera nada")
    try:
        A.responder(raiz, token, "cambios", "   ")
        ok(False, "pedir cambios sin decir cuáles no vale")
    except A.ErrorAprobacion:
        ok(True, "")
    try:
        A.responder(raiz, token, "quizas")
        ok(False, "solo aprobar o pedir cambios")
    except A.ErrorAprobacion:
        ok(True, "")
    H1 = {"tiktok": "t1", "instagram": "i1"}
    A.responder(raiz, token, "cambios", "la música más baja", huella="h1")
    ok(A.espera_al_cliente(raiz, "v2", H1, ["tiktok"]) == "cambios", "pidió cambios: sigue parado")
    ok(A.de_video(raiz, "v2")["comentario"] == "la música más baja", "la ficha ve el comentario")
    A.responder(raiz, token, "aprobado", "", huella="h1", huellas=H1)
    ok(A.espera_al_cliente(raiz, "v2", H1, ["tiktok", "instagram"]) == "", "aprobado: ya puede salir")
    ok(A.espera_al_cliente(raiz, "v2", {"tiktok": "t2", "instagram": "i1"}, ["tiktok"]) == "cambiado",
       "si cambia lo de una red, esa red ya no vale")
    ok(A.espera_al_cliente(raiz, "v2", {"tiktok": "t2", "instagram": "i1"}, ["instagram"]) == "",
       "y las demás siguen aprobadas")
    ok(A.espera_al_cliente(raiz, "v2", dict(H1, youtube="y1"), ["youtube"]) == "cambiado",
       "una red que el cliente no vio no sale")
    largo = A.responder(raiz, token, "aprobado", "x" * 5000, huella="h1")
    ok(len(largo["comentario"]) == A.TOPE_COMENTARIO, "el comentario se corta en su tope")
    for _ in range(A.TOPE_HISTORIAL + 5):
        A.responder(raiz, token, "aprobado", "", huella="h1")
    registro = json.loads(_fichero(raiz))["enlaces"][A.huella_token(token)]
    ok(len(registro["historial"]) == A.TOPE_HISTORIAL, "el historial no crece sin fin")
    ok([r["pid"] for r in A.respuestas(raiz)] == ["v2"], "la Cola ve la respuesta")
    try:
        A.responder(raiz, token, "aprobado", huella="")
        ok(False, "sin vídeo que ver no se aprueba")
    except A.ErrorAprobacion as fallo:
        ok(fallo.codigo == 409, "sin vídeo que ver, aprobar da 409")
    otro = A.crear(raiz, "v9", huella="")["token"]
    A.responder(raiz, otro, "cambios", "algo", huella="")
    datos = json.loads(_fichero(raiz))
    datos["enlaces"][A.huella_token(otro)].update(estado="aprobado", huella_aprobada="")
    with open(os.path.join(raiz, "_sistema", "publicar", "aprobaciones.json"), "w", encoding="utf-8") as fh:
        json.dump(datos, fh)
    ok(A.espera_al_cliente(raiz, "v9", {"tiktok": "hX"}, ["tiktok"]) == "cambiado",
       "un «sí» sin vídeo delante no vale cuando el vídeo ya está")
    ok(A.normalizar_decision(" Aprobado ") == "aprobado", "«Aprobado» con mayúscula es aprobar")
    t1 = {"instagram": {"titulo": "", "texto": "a #x"}}
    t2 = {"instagram": {"titulo": "", "texto": "a #y"}}
    ok(A.huellas_por_red("m", t1) != A.huellas_por_red("m", t2), "un hashtag distinto cambia la huella")
    ok(A.huellas_por_red("m", t1) != A.huellas_por_red("m2", t1), "otro montaje también")
    ok(A.huellas_por_red("", t1) == {} and A.huella_de_lo_que_ve("", {}, ["instagram"]) == ""
       and A.huella_de_lo_que_ve("m", {}, []) != "", "sin MP4 no hay huella (sin textos, sí)")
    ok(A.redes_que_ve({"redes": ["instagram", "tiktok"]}, {"tiktok": 1}, ["tiktok", "instagram"]) == ["tiktok"],
       "ve las redes elegidas que tienen texto")
    ok(A.redes_que_ve({"redes": []}, {"instagram": 1, "tiktok": 1}, ["tiktok", "instagram"]) == ["tiktok", "instagram"],
       "y sin elegir, las que tienen texto")
    ok(A.respuestas(raiz, pids=set()) == [], "y solo de los vídeos que se pueden ver")
    A.marcar_visto(raiz, token)
    ok(A.de_video(raiz, "v2")["visto"] is True, "abrirlo queda apuntado")
    # (árbitro del tren, 25-11) un fichero DAÑADO no es «no hay enlaces»
    ruta = os.path.join(raiz, "_sistema", "publicar", "aprobaciones.json")
    with open(ruta, encoding="utf-8") as fh:
        bueno = fh.read()
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(bueno[: len(bueno) // 2])
    for nombre, hacer in (("mirar si espera", lambda: A.espera_al_cliente(raiz, "v2", {}, [])),
                          ("crear otro", lambda: A.crear(raiz, "v8", huella="h")),
                          ("responder", lambda: A.responder(raiz, token, "aprobado", "", "h", {}))):
        try:
            hacer()
            ok(False, f"con el fichero dañado, «{nombre}» no sigue como si nada")
        except A.ErrorAprobacion as fallo:
            ok(fallo.codigo == 503, f"con el fichero dañado, «{nombre}» da 503")
    with open(ruta, encoding="utf-8") as fh:
        ok(fh.read() == bueno[: len(bueno) // 2], "y no se escribe encima (no se pierden los enlaces)")
    import publicar as P  # noqa: PLC0415
    ok(P._espera_al_cliente(raiz, "v2", {"mp4_huella": "h1"}, {}, ["tiktok"]) == "ilegible",
       "publicar lo lee como «no puedo leerlo» y NO deja salir el vídeo (falla cerrado)")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("[]")
    try:
        A.espera_al_cliente(raiz, "v2", {}, [])
        ok(False, "un JSON que no es lo nuestro tampoco es «no hay enlaces»")
    except A.ErrorAprobacion as fallo:
        ok(fallo.codigo == 503, "un JSON que no es lo nuestro ([]) también da 503")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(bueno)


def _error_de(P, raiz, info, ajustes, redes):
    try:
        P.enviar(raiz, info, ajustes, {"redes": redes, "modo": "ahora", "confirmado": True}, en_hilo=False)
        return ""
    except P.ErrorPublicar as fallo:
        return str(fallo)


def prueba_sin_textos():
    print("\n[3b] el vídeo se puede aprobar antes de escribir los textos")
    import publicar as P  # noqa: PLC0415
    raiz = _raiz()
    mp4 = os.path.join(raiz, "v.mp4")
    with open(mp4, "wb") as fh:
        fh.write(b"mp4")
    info = {"pid": "v4", "montado": True, "mp4": mp4, "mp4_huella": "h1",
            "formato": "vertical", "duracion_s": 20}
    token = A.crear(raiz, "v4", huella="h1")["token"]
    por_red = P.textos_para_el_cliente(P._leer_video(raiz, "v4"), {}, info)
    ok(por_red == {}, "todavía sin textos")
    huella = A.huella_de_lo_que_ve("h1", {}, [])
    try:
        A.responder(raiz, token, "aprobado", "", huella, {})
        ok(True, "")
    except A.ErrorAprobacion as fallo:
        ok(False, f"sin textos, el vídeo se aprueba ({fallo})")
    datos = P._leer_video(raiz, "v4")
    datos["textos"] = {"tiktok": {"descripcion": "texto escrito después"}}
    P._escribir(P._ruta_video(raiz, "v4"), datos)
    ok("cliente" in _error_de(P, raiz, info, {"perfil": "x"}, ["tiktok"]),
       "y el texto escrito después ya no lo vio: no sale sin que lo apruebe")


def prueba_enviar_espera():
    print("\n[3] publicar.enviar no saca un vídeo que espera al cliente")
    import publicar as P  # noqa: PLC0415
    raiz = _raiz()
    mp4 = os.path.join(raiz, "v.mp4")
    with open(mp4, "wb") as fh:
        fh.write(b"mp4")
    info = {"pid": "v3", "montado": True, "mp4": mp4, "mp4_huella": "h1",
            "formato": "vertical", "duracion_s": 20}
    ajustes = {"perfil": "x", "firma": "— Estado Play"}
    datos = P._leer_video(raiz, "v3")
    datos["redes"] = ["tiktok", "youtube"]
    datos["textos"] = {"tiktok": {"descripcion": "Texto TikTok", "cta": "Reserva ya"},
                       "youtube": {"descripcion": "Texto YouTube", "titulo": "Título"}}
    P._escribir(P._ruta_video(raiz, "v3"), datos)
    token = A.crear(raiz, "v3", huella="h1")["token"]

    def aprobar(decision="aprobado", comentario=""):
        por_red = P.textos_para_el_cliente(P._leer_video(raiz, "v3"), ajustes, info)
        redes = A.redes_que_ve(P._leer_video(raiz, "v3"), por_red, P.REDES)
        huellas = A.huellas_por_red("h1", {r: por_red[r] for r in redes})
        A.responder(raiz, token, decision, comentario, A.huella_de_lo_que_ve("h1", huellas, redes), huellas)

    por_red = P.textos_para_el_cliente(P._leer_video(raiz, "v3"), ajustes, info)
    ok("Reserva ya" in por_red["tiktok"]["texto"] and "Estado Play" in por_red["tiktok"]["texto"],
       "el cliente ve el texto que SALE (con su llamada a la acción y la firma)")

    def sale(redes, mp4_huella="h1", ajustes_=None):
        try:
            P.enviar(raiz, dict(info, mp4_huella=mp4_huella), ajustes_ or ajustes,
                     {"redes": redes, "modo": "ahora", "confirmado": True}, en_hilo=False)
            return ""
        except P.ErrorPublicar as fallo:
            return str(fallo) if "cliente" in str(fallo) else ""

    for modo, extra in (("ahora", {}), ("programar", {"cuando": "2099-01-01T10:00"})):
        try:
            P.enviar(raiz, info, ajustes,
                     {"redes": ["tiktok"], "modo": modo, "confirmado": True, **extra}, en_hilo=False)
            ok(False, f"«{modo}» con el cliente sin contestar no sale")
        except P.ErrorPublicar as fallo:
            ok(fallo.codigo == 409 and "todavía no ha aprobado" in str(fallo)
               and "anula" in str(fallo), f"«{modo}»: 409 y dice qué hacer ({fallo})")
    hechos = P.enviar(raiz, info, {}, {"redes": ["tiktok"], "modo": "pendiente"}, en_hilo=False)
    ok(hechos and hechos[0]["estado"] == "espera_ok", "dejarlo en «espera tu OK», sí")
    aprobar("cambios", "otro final")
    ok("pedido cambios" in sale(["youtube"]), "con cambios pedidos no sale, y lo dice")
    aprobar()
    ok(sale(["youtube"], mp4_huella="h2"), "otro montaje del aprobado no sale")
    ok(sale(["youtube"], ajustes_=dict(ajustes, firma="otra firma")),
       "otra firma del proyecto tampoco (el cliente vio la de antes)")
    # la llamada a la acción de TikTok cambia: TikTok ya no vale, YouTube sí
    datos = P._leer_video(raiz, "v3")
    datos["textos"]["tiktok"]["cta"] = "Escríbenos"
    P._escribir(P._ruta_video(raiz, "v3"), datos)
    ok("no ha aprobado lo que saldría" in sale(["tiktok"]),
       "cambiar la llamada a la acción después de aprobar lo vuelve a parar")
    # quitar una red no bloquea las demás
    datos = P._leer_video(raiz, "v3")
    datos["redes"] = ["youtube"]
    P._escribir(P._ruta_video(raiz, "v3"), datos)
    ok(sale(["youtube"]) == "", "quitar una red no le quita el «sí» a las demás")
    datos = P._leer_video(raiz, "v3")
    datos["textos"]["instagram"] = {"descripcion": "texto de Instagram que no vio"}
    P._escribir(P._ruta_video(raiz, "v3"), datos)
    ok(sale(["instagram"]) != "", "y una red que el cliente no vio no sale")
    ok("falta el texto" in _error_de(P, raiz, info, ajustes, ["facebook"]),
       "una red sin texto dice «falta el texto», no lo del cliente")
    # (árbitro del tren) lo que el cliente ve es lo que SALE: YouTube con su #Shorts
    yt = P.textos_para_el_cliente(P._leer_video(raiz, "v3"), ajustes, info).get("youtube") or {}
    ok("#Shorts" in (yt.get("titulo", "") + yt.get("texto", "")),
       "el cliente ve el texto compuesto como se manda (YouTube con su #Shorts)")
    # (árbitro del tren) un texto cambiado entre «Publicar» y la subida no se cuela
    aprobar()
    hechos = P.enviar(raiz, info, ajustes, {"redes": ["youtube"], "modo": "pendiente"}, en_hilo=False)
    datos = P._leer_video(raiz, "v3")
    datos["textos"]["youtube"]["descripcion"] = "cambiado justo antes de subir"
    P._escribir(P._ruta_video(raiz, "v3"), datos)
    lote = next(e["lote"] for e in P._leer_video(raiz, "v3")["envios"] if e["id"] == hechos[0]["id"])
    P._subir_lote(raiz, info, ajustes, lote, en_hilo=False)
    e = next(e for e in P._leer_video(raiz, "v3")["envios"] if e["id"] == hechos[0]["id"])
    ok(e["estado"] == "fallido" and "no se ha mandado" in e.get("error", ""),
       f"la subida vuelve a mirar con los textos que manda: no se cuela ({e['estado']}, {e.get('error')!r})")
    # reintentar un envío «comprobar» también espera al cliente
    datos = P._leer_video(raiz, "v3")
    datos["envios"].append({"id": "e-comprobar", "red": "tiktok", "lote": "abc123abc123",
                            "estado": "comprobar", "modo": "ahora", "cuando": "2099-01-01T10:00:00"})
    P._escribir(P._ruta_video(raiz, "v3"), datos)
    try:
        P.reintentar(raiz, info, ajustes, "e-comprobar", en_hilo=False)
        ok(False, "reintentar no se salta al cliente")
    except P.ErrorPublicar as fallo:
        ok(fallo.codigo == 409 and "cliente" in str(fallo), f"reintentar tampoco sale ({fallo})")


def _video_montado(servidor, base, nombre):
    from nucleo import Estado, Proyecto  # noqa: PLC0415
    from nucleo.estado import PASOS  # noqa: PLC0415
    pid = Proyecto.crear(base, nombre).id
    estado = Estado(servidor.contexto(pid).proyecto)
    for paso in PASOS:
        estado.completar(paso["id"], {})
    proyecto = servidor.contexto(pid).proyecto
    ruta = proyecto.ruta_paso("render", proyecto.version_activa("render"))
    with open(os.path.join(ruta, "video.mp4"), "wb") as fh:
        fh.write(b"0123456789" * 100)
    return pid


def prueba_rutas():
    print("\n[4] las rutas: el dueño pide el enlace y el cliente lo usa")
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415
        import app as servidor  # noqa: PLC0415
    except Exception as fallo:  # noqa: BLE001
        ok(False, f"el servidor no carga: {type(fallo).__name__}: {fallo}")
        return
    base = tempfile.mkdtemp(prefix="proyectos_", dir=CARPETA)
    antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(base)
    try:
        c = TestClient(servidor.app)
        pid = _video_montado(servidor, base, "Reel de diciembre")
        P = servidor._publicar()
        datos = P._leer_video(base, pid)
        datos["redes"] = ["instagram", "tiktok"]
        datos["textos"] = {"instagram": {"descripcion": "Texto de Instagram", "hashtags": ["uno", "dos"]},
                           "tiktok": {"descripcion": "Texto de TikTok"}}
        P._escribir(P._ruta_video(base, pid), datos)

        r = c.get(f"/api/publicar/videos/{pid}/aprobacion")
        ok(r.status_code == 200 and r.json()["enlace"] is None, "sin pedir aún: no hay enlace")
        r = c.post(f"/api/publicar/videos/{pid}/aprobacion", json={"dias": 5})
        ok(r.status_code == 200, f"pedir el enlace ({r.status_code} {r.text[:200]})")
        token = r.json()["token"]
        ok(r.json()["espera"] == "pendiente", "y desde ya el vídeo espera al cliente")
        r = c.get(f"/api/publicar/videos/{pid}/aprobacion")
        ok(token not in r.text and A.huella_token(token) not in r.text, "verlo otra vez NO da el token")

        r = c.get(f"/cliente/{token}")
        ok(r.status_code == 200 and "text/html" in r.headers["content-type"], "la página del cliente sale")
        ok(r.headers.get("cache-control") == "no-store" and "noindex" in r.headers.get("x-robots-tag", "")
           and r.headers.get("referrer-policy") == "no-referrer", "sin caché, sin indexar, sin Referer")
        ok("_/cliente.js?v=" in r.text and "_/cliente.css?v=" in r.text, "con sus ficheros sellados")
        ok("app.js" not in r.text and "estilo.css" not in r.text, "y nada del Studio")
        for nombre in ("cliente.js", "cliente.css"):
            ok(c.get(f"/cliente/_/{nombre}").status_code == 200, f"{nombre} se sirve bajo /cliente/")
        ok(c.get("/cliente/_/app.js").status_code == 404 and c.get("/cliente/_/..%2Fapp.py").status_code == 404,
           "y bajo /cliente/_/ no sale nada más")

        r = c.get(f"/cliente/{token}/datos")
        ok(r.status_code == 200, f"los datos ({r.status_code} {r.text[:200]})")
        d = r.json()
        ok(d["video"] == "Reel de diciembre" and [x["red"] for x in d["redes"]] == ["tiktok", "instagram"],
           f"el nombre y las redes elegidas ({d.get('video')}, {[x['red'] for x in d['redes']]})")
        ok(d["redes"][1]["texto"].endswith("#uno #dos"), "el texto que sale, con sus hashtags")
        ok(d["estado"] == "pendiente" and d["fecha"] == "", "pendiente y aún sin fecha")
        texto = r.text
        ok(pid not in texto and base not in texto and "mp4_rel" not in texto and "perfil" not in texto,
           "no lleva ni el id del vídeo, ni rutas, ni perfiles")
        ok(A.de_video(base, pid)["visto"] is True, "la ficha sabe que lo abrió")

        r = c.get(f"/cliente/{token}/video.mp4")
        ok(r.status_code == 200 and len(r.content) == 1000, "el vídeo se ve")
        r = c.get(f"/cliente/{token}/video.mp4", headers={"Range": "bytes=10-19"})
        ok(r.status_code == 206 and r.content == b"0123456789", "y se puede saltar (Range)")
        ok(r.headers.get("cache-control") == "no-store", "el vídeo tampoco se guarda en cachés")

        r = c.post(f"/cliente/{token}/respuesta", json={"decision": "aprobado", "v": "viejo"})
        ok(r.status_code == 409 and "recarga" in r.json()["error"], "aprobar un montaje que ya no está: 409")
        r = c.post(f"/cliente/{token}/respuesta", json={"decision": "cambios", "comentario": ""})
        ok(r.status_code == 400, "pedir cambios sin decir cuáles: 400")
        r = c.post(f"/cliente/{token}/respuesta", json={"decision": "cambios", "comentario": "más corto"})
        ok(r.status_code == 200 and r.json()["estado"] == "cambios", "pedir cambios con un comentario")
        r = c.post(f"/api/publicar/videos/{pid}/enviar",
                   json={"redes": ["tiktok"], "modo": "ahora", "confirmado": True})
        ok(r.status_code == 409 and "cambios" in r.json()["error"], "con cambios pedidos, «Publicar» da 409")
        r = c.post(f"/cliente/{token}/respuesta", json={"decision": " Aprobado ", "v": "viejo"})
        ok(r.status_code == 409, "«Aprobado» con mayúscula tampoco se salta el «recarga»")
        pub = {"X-Asvs-Publico": "1"}
        ok(c.get(f"/cliente/{token}/datos", headers=pub).status_code == 200,
           "por la puerta pública, la ruta del cliente pasa")
        ok(c.get(f"/api/publicar/videos/{pid}/aprobacion", headers=pub).status_code == 404
           and c.get("/api/proyectos", headers=pub).status_code == 404,
           "por la puerta pública, nada del Studio pasa (aunque nginx se equivocara)")
        ok(c.get(f"/cliente/{token}/datos?x=1", headers=pub).status_code == 200, "con su ?v= también")
        # (CIS 1b) un fallo imprevisto en /cliente/<token>… no lleva el token al registro
        import contextlib  # noqa: PLC0415
        import io  # noqa: PLC0415
        original_ficha = servidor._ficha_para_cliente
        servidor._ficha_para_cliente = lambda registro: 1 / 0
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                r = TestClient(servidor.app, raise_server_exceptions=False).get(f"/cliente/{token}/datos")
        finally:
            servidor._ficha_para_cliente = original_ficha
        ok(r.status_code == 500 and token not in err.getvalue() and "sin el token" in err.getvalue()
           and token not in r.text, f"un 500 en /cliente/ no apunta el token ({r.status_code})")
        r = c.post(f"/cliente/{token}/respuesta", json={"decision": "aprobado", "v": d["v"]})
        ok(r.status_code == 200 and r.json()["estado"] == "aprobado", "aprobar lo que vio")
        r = c.get(f"/api/publicar/videos/{pid}/aprobacion")
        ok(r.json()["espera"] == "" and r.json()["enlace"]["estado"] == "aprobado", "el dueño lo ve aprobado")
        r = c.get("/api/publicar/aprobaciones")
        ok([x["pid"] for x in r.json()["respuestas"]] == [pid], "y la Cola también")

        malo = "A" * 43
        respuestas = [c.get(f"/cliente/{malo}/datos"), c.get(f"/cliente/{malo}/video.mp4"),
                      c.post(f"/cliente/{malo}/respuesta", json={"decision": "aprobado"})]
        ok(all(x.status_code == 404 for x in respuestas), "un token que no existe: 404 en todo")
        ok(len({x.json()["error"] for x in respuestas}) == 1, "y siempre el mismo texto")
        ok(c.get(f"/cliente/{malo}").status_code == 200, "la página sale igual (la dice al cargar)")

        ruta_ap = os.path.join(base, "_sistema", "publicar", "aprobaciones.json")
        with open(ruta_ap, encoding="utf-8") as fh:
            guardado = fh.read()
        with open(ruta_ap, "w", encoding="utf-8") as fh:
            fh.write("{roto")
        r = c.get(f"/cliente/{token}/datos")
        ok(r.status_code == 503 and "más tarde" in r.json().get("error", "")
           and "Studio" not in r.json().get("error", "") and "fichero" not in r.json().get("error", ""),
           f"con el fichero dañado, el cliente ve «inténtalo más tarde» y nada de dentro ({r.status_code})")
        r = c.post(f"/api/publicar/videos/{pid}/enviar", json={"redes": ["tiktok"], "modo": "ahora",
                                                                "confirmado": True})
        ok(r.status_code == 409 and "no puedo leer" in r.json().get("error", ""),
           "y «Publicar» no sale: dice que no puede leer las aprobaciones")
        ok(c.get(f"/api/publicar/videos/{pid}/aprobacion").status_code == 503, "la ficha da 503 con su texto")
        with open(ruta_ap, "w", encoding="utf-8") as fh:
            fh.write(guardado)
        ident = A.de_video(base, pid)["id"]
        r = c.delete(f"/api/publicar/videos/{pid}/aprobacion/{ident}")
        ok(r.status_code == 200 and r.json()["enlace"]["vigente"] is False, "el dueño lo anula")
        ok(c.get(f"/cliente/{token}/datos").status_code == 404
           and c.get(f"/cliente/{token}/video.mp4").status_code == 404, "y ya no abre ni el vídeo")
        ok(c.post(f"/cliente/{token}/respuesta", json={"decision": "aprobado"}).status_code == 404,
           "ni deja contestar")

        r = c.post(f"/api/publicar/videos/{pid}/aprobacion", json={"dias": 99})
        ok(r.status_code == 400, "un enlace de 99 días no se da")
        sin_mp4 = servidor.contexto(pid).proyecto
        os.remove(os.path.join(sin_mp4.ruta_paso("render", sin_mp4.version_activa("render")), "video.mp4"))
        r = c.post(f"/api/publicar/videos/{pid}/aprobacion", json={})
        ok(r.status_code == 409 and "montado" in r.json()["error"], "sin vídeo montado, no hay enlace")
    finally:
        servidor.fijar_raiz_proyectos(antes)


def main():
    try:
        prueba_modulo()
        prueba_respuestas()
        prueba_enviar_espera()
        prueba_sin_textos()
        prueba_rutas()
    finally:
        shutil.rmtree(CARPETA, ignore_errors=True)
    print(f"\n  {_ok} comprobaciones bien, {len(_fallos)} mal")
    if _fallos:
        for f in _fallos:
            print("   -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

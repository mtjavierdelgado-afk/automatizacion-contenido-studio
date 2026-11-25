"""Prueba de la RETENCIÓN DE INSTAGRAM Y FACEBOOK (rama retencion-meta, 19-11-2026).

Sin red y sin tokens de verdad:

  1. el motor (`motores/metricas_meta/cliente.py`) contra un Meta falso que
     corre aquí en un hilo, con las respuestas y unidades que dio Meta el 12-11:
     lotes, lote roto → uno a uno, una métrica retirada, Reel o vídeo, los
     errores (#190, #200, cupo) y que ningún token sale nunca en una URL ni en
     un mensaje;
  2. Publicar (`pasos/publicar.py`): una fuente por cifra (lo de Meta no lo
     pisa Upload-Post, en vivo ni en la lectura guardada, y al revés), el
     respiro, sin token, la escritura bajo el cerrojo con Upload-Post
     escribiendo a la vez, y el hilo dentro de «Actualizar».

    python pasos/prueba_metricas_meta.py
"""
import http.server
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.parse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="meta_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
for _v in ("ESTUDIO_SIMULAR", "ESTUDIO_UPLOADPOST_SIMULADO", "ESTUDIO_META_SIMULADO_FALLO"):
    os.environ.pop(_v, None)

from motores.metricas_meta import cliente as MM  # noqa: E402
from motores.metricas_meta import simulado as MS  # noqa: E402
import publicar as P  # noqa: E402

TOKEN = "EAABTOKENDEUSUARIO0987654321"
TOKEN_PAGINA = "EAABTOKENDEPAGINA1122334455"
PAGINA = "1318345554704332"

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLO {texto}")


def igual(a, b, texto):
    ok(a == b, f"{texto} (esperaba {b!r}, llegó {a!r})" if a != b else texto)


def seccion(t):
    print(f"\n== {t}")


# ------------------------------------------------------------- Meta falso

ESTADO = {"modo": "", "retirada": "", "uso": 0, "retraso": 0.0, "peticiones": []}


def _insights(pares):
    return {"data": [{"name": n, "period": "lifetime", "values": [{"value": v}]} for n, v in pares]}


IG = {
    "reel1": ("REELS", {"ig_reels_avg_watch_time": 6712, "ig_reels_video_view_total_time": 1543862,
                        "reels_skip_rate": 51.3, "reposts": 2}),
    "reel2": ("REELS", {"ig_reels_avg_watch_time": 3000, "ig_reels_video_view_total_time": 90000,
                        "reels_skip_rate": 20, "reposts": 0}),
    "foto1": ("FEED", {}),
}
FB_REEL = {"post_video_avg_time_watched": 4500, "post_video_view_time": 120000,
           "post_video_followers": 3,
           "post_video_retention_graph": {str(i): round(1 - i * 0.02, 3) for i in range(40)}}
FB_VIDEO = {"total_video_avg_time_watched": 9000, "total_video_view_total_time": 300000,
            "total_video_retention_graph": {str(i): round(100 - i * 2.4, 1) for i in range(40)}}


class Falso(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _responder(self, codigo, cuerpo, cabeceras=None):
        crudo = json.dumps(cuerpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(crudo)

    def _error(self, num, mensaje, codigo=400):
        self._responder(codigo, {"error": {"message": mensaje, "type": "OAuthException",
                                           "code": num}})

    def do_GET(self):
        if ESTADO["retraso"]:
            time.sleep(ESTADO["retraso"])
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        auth = self.headers.get("Authorization") or ""
        ESTADO["peticiones"].append({"ruta": self.path, "auth": auth})
        cab = {"X-App-Usage": json.dumps({"call_count": ESTADO["uso"], "total_time": 1})}
        modo = ESTADO["modo"]
        if modo == "caducado":
            return self._error(190, "Error validating access token: Session has expired")
        if modo == "permiso":
            return self._error(200, "(#200) Requires read_insights permission")
        if modo == "cupo":
            return self._error(4, "(#4) Application request limit reached")
        partes = [p for p in url.path.split("/") if p]
        if not partes or partes[0] != MM.VERSION_METRICAS:
            return self._error(2500, "version desconocida")
        ruta = partes[1:]
        campos = q.get("fields", "")
        retirada = ESTADO["retirada"]
        if retirada and retirada in campos:
            return self._error(100, f"(#100) metric[2] must be one of the following values: x; "
                                    f"{retirada} is not valid")
        if ruta == ["me", "accounts"]:
            if auth != f"Bearer {TOKEN}":
                return self._error(190, "token raro")
            return self._responder(200, {"data": [
                {"id": PAGINA, "name": "SUYU", "access_token": TOKEN_PAGINA,
                 "instagram_business_account": {"id": "1784", "username": "casas_con_diseno"}},
                {"id": "999", "name": "Otra", "access_token": "EAABOTRAPAGINA00000000"}]}, cab)
        if not ruta and "ids" in q:
            if auth != f"Bearer {TOKEN}":
                return self._error(190, "token raro")
            ids = q["ids"].split(",")
            if any(i.startswith("bad") for i in ids):
                return self._error(100, f"(#100) Tried accessing nonexisting field (bad id {ids})")
            salida = {}
            for i in ids:
                tipo, m = IG.get(i, ("REELS", {}))
                nodo = {"id": i, "media_product_type": tipo,
                        "permalink": f"https://www.instagram.com/reel/{i}/"}
                if tipo == "REELS":
                    pedidas = campos.split("metric(")[1].split(")")[0].split(",")
                    nodo["insights"] = _insights([(n, m[n]) for n in pedidas if n in m])
                salida[i] = nodo
            return self._responder(200, salida, cab)
        if len(ruta) == 1:
            ident = ruta[0]
            if auth != f"Bearer {TOKEN_PAGINA}":
                return self._error(190, "se esperaba el token de la página")
            if "attachments" in campos:
                return self._responder(200, {"id": ident, "attachments": {"data": [
                    {"media_type": "video", "target": {"id": "reel77"}}]}}, cab)
            if "video_insights" in campos:
                if ident.startswith("vid") and "post_video" in campos:
                    return self._error(100, "(#100) The value must be a valid insights metric: "
                                            "post_video_avg_time_watched")
                fuente = FB_VIDEO if ident.startswith("vid") else FB_REEL
                pedidas = campos.split("metric(")[1].split(")")[0].split(",")
                return self._responder(200, {"id": ident, "length": 25.0, "video_insights":
                                             _insights([(n, fuente[n]) for n in pedidas
                                                        if n in fuente])}, cab)
        return self._error(803, "ruta desconocida")


def arrancar():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), Falso)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor, f"http://127.0.0.1:{puerto}"


def nada_de_tokens(texto, donde):
    texto = str(texto)
    ok(TOKEN not in texto and TOKEN_PAGINA not in texto
       and urllib.parse.quote(TOKEN) not in texto, f"ningún token entero en {donde}")


# ------------------------------------------------------------------ 1 motor

def prueba_motor(base):
    seccion("1] el motor de Meta contra un Meta falso")
    ESTADO.update(modo="", retirada="", uso=0, peticiones=[])
    cli = MM.ClienteMeta(TOKEN, base=base)
    r = cli.instagram(["reel1", "reel2"])
    igual(len(ESTADO["peticiones"]), 1, "dos Reels en UNA llamada (?ids=)")
    igual((r["reel1"]["tiempo_medio_s"], r["reel1"]["tiempo_total_s"], r["reel1"]["salto_3s"],
           r["reel1"]["reposts"]), (6.7, 1543.9, 0.513, 2),
          "milisegundos a segundos y el % de salto en fracción (las unidades del 12-11)")
    ok(all("access_token" not in p["ruta"] and TOKEN not in p["ruta"] for p in ESTADO["peticiones"])
       and all(p["auth"] == f"Bearer {TOKEN}" for p in ESTADO["peticiones"]),
       "el token va en la cabecera Authorization, nunca en la URL")
    r = cli.instagram(["foto1"])
    ok("error" in r["foto1"] and "Reel" in r["foto1"]["error"], "una foto dice que no es un Reel")

    ESTADO["peticiones"] = []
    r = cli.instagram(["reel1", "bad9", "reel2"])
    ok(r["reel1"].get("tiempo_medio_s") == 6.7 and r["reel2"].get("tiempo_medio_s") == 3.0
       and "error" in r["bad9"], "un id malo tumba el lote: se repite de uno en uno y los buenos llegan")
    igual(len(ESTADO["peticiones"]), 4, "el lote y después los tres de uno en uno")

    ESTADO["retirada"] = "reels_skip_rate"
    cli2 = MM.ClienteMeta(TOKEN, base=base)
    r = cli2.instagram(["reel1"])
    ESTADO["retirada"] = ""
    ok(r["reel1"].get("tiempo_medio_s") == 6.7 and r["reel1"].get("salto_3s") is None
       and cli2.retiradas == ["reels_skip_rate"],
       "si Meta retira una métrica se pide sin ella UNA vez y queda dicho")

    for modo, motivo in (("caducado", "caducado"), ("permiso", "sin_permiso"), ("cupo", "cupo")):
        ESTADO["modo"] = modo
        try:
            MM.ClienteMeta(TOKEN, base=base).instagram(["reel1"])
            ok(False, f"«{modo}» lanza")
        except MM.ErrorMeta as fallo:
            igual(fallo.motivo, motivo, f"«{modo}» se entiende como {motivo}")
            nada_de_tokens(fallo, f"el error «{modo}»")
    ESTADO["modo"] = ""
    try:
        MM.ClienteMeta("", base=base).instagram(["reel1"])
        ok(False, "sin token lanza")
    except MM.ErrorMeta as fallo:
        igual(fallo.motivo, "sin_token", "sin token: «sin_token», sin llamar a nadie")
    try:
        MM.ClienteMeta(TOKEN, base="http://127.0.0.1:1", plazo=1).instagram(["reel1"])
        ok(False, "sin red lanza")
    except MM.ErrorMeta as fallo:
        igual(fallo.motivo, "red", "sin red: «red»")

    ESTADO["uso"] = 95
    cli3 = MM.ClienteMeta(TOKEN, base=base)
    cli3.instagram(["reel1"])
    ok(cli3.cerca_del_cupo, "una cabecera de uso al 95 % para las llamadas siguientes")
    ESTADO["uso"] = 0

    cli = MM.ClienteMeta(TOKEN, base=base)
    paginas = cli.paginas()
    ok(paginas[0]["token"] == TOKEN_PAGINA and paginas[0]["ig_usuario"] == "casas_con_diseno",
       "me/accounts da las páginas con su token y su Instagram")
    igual(cli.resolver_fb(TOKEN_PAGINA, f"{PAGINA}_555"), "reel77",
          "un post de página («pagina_post») lleva a su vídeo")
    r = cli.facebook(TOKEN_PAGINA, [("reel77", 20)])["reel77"]
    igual((r["tipo"], r["tiempo_medio_s"], r["tiempo_total_s"], r["nuevos_seguidores"], r["media_vista"]),
          ("reel", 4.5, 120.0, 3, 0.225), "un Reel de Facebook: visto de media, minutos, seguidores")
    ok(r["curva"] and r["curva"][0] == [0.0, 1.0] and r["mitad_s"] == 12.5,
       f"y su curva en segundos con la duración del envío, y en qué segundo se va la mitad ({r['mitad_s']})")
    v = cli.facebook(TOKEN_PAGINA, [("vid5", None)])["vid5"]
    ok(v["tipo"] == "video" and v["tiempo_medio_s"] == 9.0 and v["duracion_s"] == 25.0
       and v["curva"] and 0 < v["curva"][1][1] < 1,
       "un vídeo (no Reel): si no acepta las de Reel, las de vídeo; sin duración, la que da Meta; "
       "la curva en % pasa a fracción")
    ESTADO["modo"] = "permiso"
    try:
        cli.facebook(TOKEN_PAGINA, [("reel77", 20)])
        ok(False, "sin read_insights lanza")
    except MM.ErrorMeta as fallo:
        igual(fallo.motivo, "sin_permiso", "Facebook sin read_insights: «sin_permiso»")
        nada_de_tokens(fallo, "el error de Facebook")
    ESTADO["modo"] = ""

    curva, mitad = MM.curva_de({str(i): 1 - i / 500 for i in range(400)}, 200)
    ok(len(curva) <= MM.TOPE_CURVA and curva[-1][0] > 199, "una curva larga se aligera y conserva el final")
    igual(MM.curva_de({"0": 1}, 10), (None, None), "una curva de un punto no es una curva")
    igual(MM.curva_de({"0": 1, "1": 0.5}, None), (None, None), "sin duración no hay segundos")
    igual(MM.tachar(f"x {TOKEN} y {urllib.parse.quote(TOKEN)}", [TOKEN]).count("…4321"), 2,
          "tachar quita el token entero y escapado, y deja su cola")
    ok(MM.es_pagina_post("1_2") and not MM.es_pagina_post("12"), "pagina_post se reconoce")
    s = MS.SimuladoMeta().instagram(["in1"])["in1"]
    ok(0 < s["salto_3s"] < 1 and s["tiempo_medio_s"] > 0, "el simulado da la misma forma")


# ------------------------------------------------------------- 2 Publicar

def _video(raiz, pid, envios):
    datos = P._leer_video(raiz, pid)
    datos["envios"] = envios
    P._escribir(P._ruta_video(raiz, pid), datos)


def _envio(raiz, pid, ident):
    return next(e for e in P._leer_video(raiz, pid)["envios"] if e["id"] == ident)


def _poner_token(valor):
    os.makedirs(os.environ["ESTUDIO_SECRETOS"], exist_ok=True)
    with open(os.path.join(os.environ["ESTUDIO_SECRETOS"], "lectura_redes.json"), "w") as f:
        json.dump({"meta_token": valor}, f)


def prueba_publicar(base):
    seccion("2] Publicar: una fuente por cifra, el respiro y el cerrojo")
    raiz = os.path.join(CARPETA, "proyectos")
    os.makedirs(raiz, exist_ok=True)
    os.environ["ESTUDIO_META_BASE"] = base
    ESTADO.update(modo="", retirada="", uso=0, peticiones=[])
    os.makedirs(os.path.dirname(P._ruta_ajustes(raiz)), exist_ok=True)
    with open(P._ruta_ajustes(raiz), "w") as f:
        json.dump({"proyectos": {"cl1": {"perfil": "perfil1", "facebook_pagina": PAGINA}}}, f)
    _video(raiz, "v1", [
        {"id": "e_ig", "red": "instagram", "estado": "publicado", "post_id": "reel1", "perfil": "perfil1",
         "lote": "L1", "duracion_s": 20.0, "cuando": P._iso_lima(),
         "metricas": {"vistas": 272, "tiempo_medio_s": 1.0, "al": P._iso_lima()}},
        {"id": "e_fb", "red": "facebook", "estado": "publicado", "post_id": f"{PAGINA}_555",
         "perfil": "perfil1", "lote": "L1", "duracion_s": 20.0, "cuando": P._iso_lima(),
         "metricas": {"vistas": 50}},
        {"id": "e_tt", "red": "tiktok", "estado": "publicado", "post_id": "tt1", "lote": "L1",
         "metricas": {"vistas": 9, "tiempo_medio_s": 2.0}},
    ])
    _poner_token("")
    r = P.medir_meta(raiz, ["v1"])
    ok(any("token de Meta" in x for x in r["errores"]) and r.get("motivo") == "sin_token"
       and not ESTADO["peticiones"], "sin token: se dice una vez y no se llama a Meta")
    ok("meta_al" not in (_envio(raiz, "v1", "e_ig")["metricas"]), "y no se escribe nada")

    _poner_token(TOKEN)
    r = P.medir_meta(raiz, ["v1"])
    ig = _envio(raiz, "v1", "e_ig")
    fb = _envio(raiz, "v1", "e_fb")
    m = ig["metricas"]
    igual((m["tiempo_medio_s"], m["salto_3s"], m["reposts"], m["vistas"]), (6.7, 0.513, 2, 272),
          "Instagram: Meta pone el tiempo medio (pisa el 1,0 de Upload-Post), el salto y los reposts; "
          "las vistas de Upload-Post siguen")
    igual(m["media_vista"], 0.335, "y el visto de media en % con la duración del MP4 que se mandó")
    ok(m.get("meta_al") and m.get("meta_error") == "" and ig.get("meta_id") == "reel1",
       "con su reloj propio (meta_al) y su id")
    mf = fb["metricas"]
    ok(fb.get("meta_id") == "reel77" and fb.get("meta_tipo") == "reel" and mf["nuevos_seguidores"] == 3
       and mf["curva"] and mf["mitad_s"] == 12.5 and mf["vistas"] == 50,
       "Facebook: el post de la página lleva a su Reel, con la curva y los seguidores ganados")
    tt = _envio(raiz, "v1", "e_tt")
    ok("meta_al" not in tt["metricas"], "TikTok no se toca")
    igual((r["leidos"], r["actualizados"]), (2, 2), "dos leídos, dos apuntados")
    with open(P._ruta_video(raiz, "v1")) as f:
        nada_de_tokens(f.read(), "la ficha del vídeo")

    # Upload-Post en vivo despues: lo suyo se actualiza, lo de Meta se queda
    P._apuntar_metricas(raiz, [("v1", ig), ("v1", fb)], {
        "instagram": {"vistas": 300, "tiempo_medio_s": 99.0, "media_vista": 0.9, "error": ""},
        "facebook": {"vistas": 60, "curva": [[0, 1], [5, 0.2]], "mitad_s": 2.0, "error": ""}})
    m = _envio(raiz, "v1", "e_ig")["metricas"]
    igual((m["vistas"], m["tiempo_medio_s"], m["media_vista"], m["salto_3s"]), (300, 6.7, 0.335, 0.513),
          "Upload-Post después: las vistas cambian; el tiempo medio, el % y el salto de Meta no")
    ok(m.get("meta_al"), "y el reloj de Meta sigue")
    mf = _envio(raiz, "v1", "e_fb")["metricas"]
    ok(mf["vistas"] == 60 and mf["mitad_s"] == 12.5 and mf["curva"][0] == [0.0, 1.0],
       "en Facebook la curva de Upload-Post (si un día la manda) no pisa la de Meta")

    # la lectura guardada tampoco
    ig = _envio(raiz, "v1", "e_ig")
    futuro = (P.ahora_lima() + P.dt.timedelta(minutes=5)).isoformat()
    P._apuntar_guardadas(raiz, [("v1", ig)], {("instagram", "id", "reel1"): {
        "red": "instagram", "post_id": "reel1", "al": futuro, "vistas": 310, "tiempo_medio_s": 77.0}})
    m = _envio(raiz, "v1", "e_ig")["metricas"]
    igual((m["vistas"], m["tiempo_medio_s"]), (310, 6.7), "la lectura guardada: vistas sí, tiempo medio no")

    # el respiro: una segunda vuelta enseguida no pregunta
    ESTADO["peticiones"] = []
    r = P.medir_meta(raiz, ["v1"])
    ok(r["leidos"] == 0 and not ESTADO["peticiones"], "leído hace un momento: no se vuelve a preguntar")
    r = P.medir_meta(raiz, ["v1"], forzar=True)
    igual(r["leidos"], 2, "con «forzar», sí")

    # el token caducado: el aviso y nada borrado
    ESTADO["modo"] = "caducado"
    r = P.medir_meta(raiz, ["v1"], forzar=True)
    ESTADO["modo"] = ""
    ok(any("caducado" in x for x in r["errores"]) and r.get("motivo") == "caducado",
       "token caducado: se dice que hay que generar otro")
    ok(_envio(raiz, "v1", "e_ig")["metricas"]["tiempo_medio_s"] == 6.7, "y lo que se sabía no se borra")
    for x in r["errores"]:
        nada_de_tokens(x, "los avisos")

    # Meta aún sin cifras (Reel recién subido): no borra lo de antes
    IG["reel1"] = ("REELS", {})
    P.medir_meta(raiz, ["v1"], forzar=True)
    IG["reel1"] = ("REELS", {"ig_reels_avg_watch_time": 6712, "ig_reels_video_view_total_time": 1543862,
                             "reels_skip_rate": 51.3, "reposts": 2})
    ok(_envio(raiz, "v1", "e_ig")["metricas"]["salto_3s"] == 0.513,
       "una lectura sin cifras no borra las de antes («no lo sé» no es cero)")

    # el cerrojo: Upload-Post escribe MIENTRAS Meta lee
    original = MM.ClienteMeta.instagram

    def lento(self, ids):
        P._apuntar_metricas(raiz, [("v1", _envio(raiz, "v1", "e_ig"))],
                            {"instagram": {"vistas": 999, "me_gusta": 7, "error": ""}})
        return original(self, ids)
    MM.ClienteMeta.instagram = lento
    try:
        P.medir_meta(raiz, ["v1"], forzar=True)
    finally:
        MM.ClienteMeta.instagram = original
    m = _envio(raiz, "v1", "e_ig")["metricas"]
    ok(m["vistas"] == 999 and m["me_gusta"] == 7 and m["salto_3s"] == 0.513,
       "Upload-Post escribe mientras Meta lee: no se pierde ni lo uno ni lo otro")

    # una foto de Instagram: se dice, y no se vuelve a preguntar enseguida
    _video(raiz, "v2", [{"id": "e_foto", "red": "instagram", "estado": "a_mano", "post_id": "foto1",
                         "metricas": {}}])
    P.medir_meta(raiz, ["v2"])
    m = _envio(raiz, "v2", "e_foto")["metricas"]
    ok("Reel" in m.get("meta_error", "") and m.get("meta_al"), "una foto: «no es un Reel», con su reloj")

    seccion("3] dentro de «Actualizar» (`medir`)")
    # Upload-Post aquí no existe: su parte contesta vacía (la suya se prueba en prueba_publicar)
    vacia = {"consultados": 0, "actualizados": 0, "pendientes": 0, "errores": []}
    antes_up, antes_g = P.actualizar_metricas, P.leer_guardadas
    P.actualizar_metricas = lambda *a, **k: dict(vacia)
    P.leer_guardadas = lambda *a, **k: {"leidos": 0, "actualizados": 0, "errores": []}
    r = P.medir(raiz, ["v1"], forzar=True)
    ok(r.get("meta", {}).get("leidos") == 2, f"«Actualizar» trae también lo de Meta ({r.get('meta')})")
    P.actualizar_metricas = lambda *a, **k: {"consultados": 0, "actualizados": 0, "pendientes": 0,
                                             "ocupado": True, "errores": ["Upload-Post ocupado"]}
    r = P.medir(raiz, ["v1"], forzar=True)
    P.actualizar_metricas = lambda *a, **k: dict(vacia)
    ok(r.get("meta", {}).get("leidos") == 2, "con Upload-Post ocupado (o pidiendo esperar), Meta corre igual")
    antes_meta, antes_tope = P.medir_meta, P.TOPE_VUELTA_S
    P.medir_meta = lambda *a, **k: (time.sleep(3), {"leidos": 1, "actualizados": 1, "errores": []})[1]
    P.TOPE_VUELTA_S = 1.0
    try:
        inicio = time.time()
        r = P.medir(raiz, ["v1"])
        tardo = time.time() - inicio
    finally:
        P.medir_meta, P.TOPE_VUELTA_S = antes_meta, antes_tope
    ok(tardo < 2.5 and r.get("meta", {}).get("a_medias")
       and any("no dio tiempo" in x for x in r["errores"]),
       f"si Meta tarda más que la franja, «Actualizar» no espera ({tardo:.1f} s) y lo dice")
    P.medir_meta(raiz, ["v1"], forzar=True)
    ok(not P._LOCK_META.locked(), "tras una lectura de Meta, su cerrojo queda libre")
    # recién publicado: el número del post lo trae Upload-Post en la MISMA
    # vuelta en la que Meta ya ha empezado sin él → segunda vuelta para ese
    ig_ok = next(e for e in P._leer_video(raiz, "v1")["envios"] if e["red"] == "instagram")
    _video(raiz, "v3", [{"id": "e_nuevo", "red": "instagram", "estado": "publicado",
                         "lote": "l3", "perfil": "p", "metricas": {}}])

    def up_trae_el_numero(*_a, **_k):
        datos = P._leer_video(raiz, "v3")
        datos["envios"][0]["post_id"] = ig_ok.get("meta_id") or ig_ok.get("post_id")
        P._escribir(P._ruta_video(raiz, "v3"), datos)
        return dict(vacia)
    P.actualizar_metricas = up_trae_el_numero
    r = P.medir(raiz, ["v3"])
    P.actualizar_metricas = lambda *a, **k: dict(vacia)
    m = _envio(raiz, "v3", "e_nuevo")["metricas"]
    ok(m.get("meta_al") and m.get("salto_3s") is not None,
       f"recién publicado: el número llega de Upload-Post y Meta lo lee en la misma «Actualizar» ({r.get('meta')})")
    # dos «Actualizar» a la vez no lanzan dos lecturas de Meta
    P._LOCK_META.acquire()
    try:
        igual(P.medir_meta(raiz, ["v1"]).get("ocupado"), True, "con otra lectura de Meta en marcha: ocupado")
    finally:
        P._LOCK_META.release()
    P.actualizar_metricas, P.leer_guardadas = antes_up, antes_g
    os.environ.pop("ESTUDIO_META_BASE", None)


def main():
    servidor, base = arrancar()
    try:
        prueba_motor(base)
        prueba_publicar(base)
    finally:
        servidor.shutdown()
        shutil.rmtree(CARPETA, ignore_errors=True)
    print()
    if _fallos:
        print(f"METRICAS META: {len(_fallos)} FALLOS de {_ok + len(_fallos)} comprobaciones")
        for f in _fallos:
            print(f"  - {f}")
        sys.exit(1)
    print(f"METRICAS META OK: {_ok} comprobaciones pasan")


if __name__ == "__main__":
    main()

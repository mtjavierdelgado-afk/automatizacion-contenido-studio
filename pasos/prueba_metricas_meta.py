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

ESTADO = {"modo": "", "retirada": "", "uso": 0, "retraso": 0.0, "retraso_lote": 0.0, "retraso_fb": 0.0,
          "peticiones": []}


def _insights(pares):
    return {"data": [{"name": n, "period": "lifetime", "values": [{"value": v}]} for n, v in pares]}


IG = {
    "reel1": ("REELS", {"ig_reels_avg_watch_time": 6712, "ig_reels_video_view_total_time": 1543862,
                        "reels_skip_rate": 51.3, "reposts": 2}),
    "reel2": ("REELS", {"ig_reels_avg_watch_time": 3000, "ig_reels_video_view_total_time": 90000,
                        "reels_skip_rate": 20, "reposts": 0}),
    "foto1": ("FEED", {}),
    # el id de verdad de un Reel cuyo envío trae otro (el de Upload-Post)
    "17900000000000001": ("REELS", {"ig_reels_avg_watch_time": 4200, "ig_reels_video_view_total_time": 50000,
                                    "reels_skip_rate": 33.3, "reposts": 1}),
}
FB_REEL = {"post_video_avg_time_watched": 4500, "post_video_view_time": 120000,
           "post_video_followers": 3,
           "post_video_retention_graph": {str(i): round(1 - i * 0.02, 3) for i in range(40)}}
FB_VIDEO = {"total_video_avg_time_watched": 9000, "total_video_view_total_time": 300000,
            "total_video_retention_graph": {str(i): round(100 - i * 2.4, 1) for i in range(40)}}


class Falso(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    _captura = None

    def _responder(self, codigo, cuerpo, cabeceras=None):
        if self._captura is not None:       # una petición DENTRO de un lote
            self._captura.append((codigo, cuerpo))
            return
        crudo = json.dumps(cuerpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(crudo)

    def _error(self, num, mensaje, codigo=400, sub=None):
        err = {"message": mensaje, "type": "OAuthException", "code": num}
        if sub:
            err["error_subcode"] = sub
        self._responder(codigo, {"error": err})

    def do_POST(self):
        """La Batch API de Graph: `batch=[{method, relative_url}]`; cada GET de
        dentro se contesta como si fuera suelto."""
        if ESTADO["retraso"] or ESTADO["retraso_lote"]:
            time.sleep(ESTADO["retraso"] or ESTADO["retraso_lote"])
        largo = int(self.headers.get("Content-Length") or 0)
        form = dict(urllib.parse.parse_qsl(self.rfile.read(largo).decode("utf-8")))
        auth = self.headers.get("Authorization") or ""
        peticiones = json.loads(form.get("batch") or "[]")
        ESTADO["peticiones"].append({"ruta": f"{self.path} (lote de {len(peticiones)})", "auth": auth,
                                     "lote": [p.get("relative_url") for p in peticiones]})
        salida, ruta_antes = [], self.path
        for p in peticiones:
            self._captura = []
            self.path = f"/{MM.VERSION_METRICAS}/{p.get('relative_url', '')}"
            try:
                self.do_GET()
            finally:
                self.path = ruta_antes
            codigo, cuerpo = self._captura[0] if self._captura else (500, {"error": {"message": "nada"}})
            self._captura = None
            salida.append({"code": codigo, "body": json.dumps(cuerpo)})
        cab = {"X-App-Usage": json.dumps({"call_count": ESTADO["uso"], "total_time": 1})}
        return self._responder(200, salida, cab)

    def do_GET(self):
        dentro = self._captura is not None
        if ESTADO["retraso"] and not dentro:
            time.sleep(ESTADO["retraso"])
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        auth = self.headers.get("Authorization") or ""
        if not dentro:
            ESTADO["peticiones"].append({"ruta": self.path, "auth": auth})
        if ESTADO["retraso_fb"] and auth == f"Bearer {TOKEN_PAGINA}" and "video_insights" in self.path:
            time.sleep(ESTADO["retraso_fb"])
        cab = {"X-App-Usage": json.dumps({"call_count": ESTADO["uso"], "total_time": 1})}
        modo = ESTADO["modo"]
        if modo == "caducado":
            return self._error(190, "Error validating access token: Session has expired")
        if modo == "permiso":
            return self._error(200, "(#200) Requires read_insights permission")
        if modo == "cupo":
            return self._error(4, "(#4) Application request limit reached")
        if modo == "permiso100":
            return self._error(100, "(#100) Tried accessing nonexisting field (insights) on node type "
                                    "(IGMedia): requires the instagram_manage_insights permission")
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
        if "ids" in q:
            # lo que contesta Meta desde v26.0 (servidor, 25-11)
            return self._error(100, "The ids query parameter is deprecated in v26.0+.", codigo=500)
        if len(ruta) == 1 and auth == f"Bearer {TOKEN}":
            # un medio de Instagram, de uno en uno: GET /<id>?fields=…
            ids = [ruta[0]]
            if modo == "permiso_ig":
                return self._error(10, "(#10) Application does not have permission for this action")
            if any(i.startswith("antes") for i in ids) and "insights" in campos:
                return self._error(10, "(#10) Media posted before business account conversion",
                                   sub=2108006)
            if any(i.startswith("borrado") for i in ids):
                # lo que da Meta de un id borrado (#100, subcódigo 33)
                return self._error(100, "Unsupported get request. Object with ID 'borrado1' does not "
                                        "exist, cannot be loaded due to missing permissions, or does "
                                        "not support this operation")
            if any(i.startswith("bad") for i in ids):
                return self._error(100, f"(#100) Tried accessing nonexisting field (bad id {ids})")
            # como Meta: las métricas de Reel pedidas para una foto o un
            # carrusel tumban la llamada entera con un #100 que NOMBRA la métrica
            if "insights" in campos and any(IG.get(i, ("REELS", {}))[0] != "REELS" for i in ids):
                return self._error(100, "(#100) The Media Insights API does not support the "
                                        "reels_skip_rate metric for this media product type")
            salida = {}
            for i in ids:
                tipo, m = IG.get(i, ("REELS", {}))
                nodo = {"id": i, "media_product_type": tipo,
                        "permalink": f"https://www.instagram.com/reel/{i}/"}
                if tipo == "REELS" and "metric(" in campos:
                    pedidas = campos.split("metric(")[1].split(")")[0].split(",")
                    nodo["insights"] = _insights([(n, m[n]) for n in pedidas if n in m])
                salida[i] = nodo
            return self._responder(200, salida[ids[0]], cab)
        if len(ruta) == 2 and ruta[1] == "media":
            # los medios de la cuenta de Instagram (para dar con el id de un Reel)
            if auth != f"Bearer {TOKEN}":
                return self._error(190, "token raro")
            ESTADO.setdefault("medios_pedidos", []).append(ruta[0])
            return self._responder(200, {"data": [
                {"id": "17900000000000001", "shortcode": "DCodigo_1", "media_product_type": "REELS",
                 "permalink": "https://www.instagram.com/reel/DCodigo_1/"},
                {"id": "17900000000000002", "shortcode": "OtroReel", "media_product_type": "REELS",
                 "permalink": "https://www.instagram.com/reel/OtroReel/"}], "paging": {}}, cab)
        if len(ruta) == 1:
            ident = ruta[0]
            if auth != f"Bearer {TOKEN_PAGINA}":
                return self._error(190, "se esperaba el token de la página")
            if "attachments" in campos:
                if ident.endswith("_999"):
                    # un post de página borrado (#100, subcódigo 33)
                    return self._error(100, f"Unsupported get request. Object with ID '{ident}' does "
                                            "not exist, cannot be loaded due to missing permissions, "
                                            "or does not support this operation", sub=33)
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
    igual(len(ESTADO["peticiones"]), 1, "dos Reels en UNA llamada (por lotes: Meta ya no acepta ?ids=)")
    ok(not any("ids=" in p["ruta"] for p in ESTADO["peticiones"])
       and ESTADO["peticiones"][0].get("lote") and all(r.startswith(("reel1?", "reel2?"))
                                                        for r in ESTADO["peticiones"][0]["lote"]),
       "y nunca con ?ids=: un GET /<id> por Reel dentro del lote")
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
       and "error" in r["bad9"], "un id malo no estropea a los demás: los buenos llegan")
    # el malo, solo, se pregunta además por su tipo (¿foto o métrica retirada?)
    igual(len(ESTADO["peticiones"]), 2, "el lote y el tipo del malo")
    ok(MM.ClienteMeta(TOKEN, base=base).instagram(["../me/accounts"])["../me/accounts"].get("error"),
       "un id con barras no llega a la ruta de la llamada")

    ESTADO["retirada"] = "reels_skip_rate"
    cli2 = MM.ClienteMeta(TOKEN, base=base)
    r = cli2.instagram(["reel1"])
    ESTADO["retirada"] = ""
    ok(r["reel1"].get("tiempo_medio_s") == 6.7 and r["reel1"].get("salto_3s") is None
       and cli2.retiradas == ["reels_skip_rate"],
       "si Meta retira una métrica se pide sin ella UNA vez y queda dicho")

    # árbitro, 24-11: una foto en un lote de Reels NO es «métrica retirada»
    cli3 = MM.ClienteMeta(TOKEN, base=base)
    r = cli3.instagram(["reel1", "foto1", "reel2"])
    ok(r["reel1"].get("salto_3s") is not None and r["reel2"].get("tiempo_medio_s") is not None
       and "Reel" in r["foto1"].get("error", "") and cli3.retiradas == [],
       f"una foto en el lote no retira ninguna métrica a los Reels ({cli3.retiradas})")
    ok(all("#" not in (v.get("error") or "") and "Tried" not in (v.get("error") or "")
           for v in cli.instagram(["bad9"]).values()),
       "lo que se guarda de un error va en castellano, sin el mensaje crudo de Meta")
    # árbitro, 24-11: si Meta pide esperar a mitad del «uno a uno», lo leído se queda
    cli5 = MM.ClienteMeta(TOKEN, base=base)
    llamadas = {"n": 0}
    original = cli5._get

    def con_cupo(ruta, params=None, token=None):
        llamadas["n"] += 1
        if llamadas["n"] == 1:       # (el lote va aparte) aquí, el tipo de bad9
            raise MM.ErrorMeta("Meta pide esperar", "cupo")
        return original(ruta, params, token)
    cli5._get = con_cupo
    r = cli5.instagram(["reel1", "bad9", "reel2"])
    ok(r.get("reel1", {}).get("tiempo_medio_s") == 6.7 and cli5.cerca_del_cupo,
       "si Meta pide esperar a mitad del lote, lo ya leído se queda y se dice")
    # árbitro, 24-11: el cliente no empieza una llamada que no quepa en la franja
    ESTADO["peticiones"] = []
    cli4 = MM.ClienteMeta(TOKEN, base=base, hasta=time.time() + 1)
    r = cli4.instagram(["reel1", "reel2"])
    ok(r == {} and cli4.sin_tiempo and not ESTADO["peticiones"],
       "sin tiempo para una llamada entera no se empieza ninguna, y queda dicho")

    ESTADO["modo"] = "cupo"
    cli6 = MM.ClienteMeta(TOKEN, base=base)
    ok(cli6.instagram(["reel1"]) == {} and cli6.cerca_del_cupo,
       "«cupo» en Instagram no lanza: corta con lo leído y queda dicho (cerca_del_cupo)")
    for modo, motivo in (("caducado", "caducado"), ("permiso", "sin_permiso")):
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
    # prueba del servidor, 25-11: un token sin instagram_manage_insights. La
    # tarjeta del Reel tiene que decir lo del permiso, no «no ha devuelto»,
    # aunque ya trajera ese texto de antes, y sin reloj (se reintenta en cuanto
    # haya un token bueno)
    _video(raiz, "v6", [{"id": "e_perm", "red": "instagram", "estado": "a_mano", "post_id": "reel2",
                         "metricas": {"meta_error": "Meta no ha devuelto las cifras de este vídeo"}}])
    for modo in ("permiso100", "permiso"):
        ESTADO["modo"] = modo
        try:
            r6 = P.medir_meta(raiz, ["v6"], forzar=True)
        finally:
            ESTADO["modo"] = ""
        m = _envio(raiz, "v6", "e_perm")["metricas"]
        ok(r6.get("motivo") == "sin_permiso" and "instagram_manage_insights" in m.get("meta_error", "")
           and not m.get("meta_al"),
           f"sin permiso ({modo}): la tarjeta lo dice, sin reloj ({m.get('meta_error')!r})")
    # árbitro: un Reel BORRADO («missing permissions» en su mensaje) es cosa de
    # ese vídeo, no del token: los demás se leen y nadie recibe el aviso de permiso
    _video(raiz, "v7", [{"id": "e_borr", "red": "instagram", "estado": "a_mano", "post_id": "borrado1",
                         "metricas": {}},
                        {"id": "e_bien", "red": "instagram", "estado": "a_mano", "post_id": "reel1",
                         "metricas": {}}])
    r7 = P.medir_meta(raiz, ["v7"], forzar=True)
    mb, mo = _envio(raiz, "v7", "e_borr")["metricas"], _envio(raiz, "v7", "e_bien")["metricas"]
    ok(not r7.get("motivo") and mo.get("tiempo_medio_s") is not None
       and "permiso" not in mb.get("meta_error", "") and mb.get("meta_al"),
       f"un Reel borrado no corta la vuelta ni dice «falta un permiso» ({mb.get('meta_error')!r})")
    # prueba del servidor (CIS 1b, 25-11): Instagram no contestaba NINGÚN Reel
    # con el id del envío. Se busca su enlace en los medios de la cuenta y se
    # pide con el id de verdad; lo que dijo Meta se guarda, sin tokens
    _video(raiz, "v11", [{"id": "i_up", "red": "instagram", "estado": "publicado", "post_id": "borradoUP77",
                          "url": "https://www.instagram.com/reel/DCodigo_1/?igsh=xyz", "metricas": {}},
                         {"id": "i_nada", "red": "instagram", "estado": "publicado", "post_id": "borradoUP78",
                          "url": "https://www.instagram.com/reel/NoEstaEnLaCuenta/", "metricas": {}}])
    r11 = P.medir_meta(raiz, ["v11"], forzar=True)
    e_up, e_nada = _envio(raiz, "v11", "i_up"), _envio(raiz, "v11", "i_nada")
    ok(e_up.get("meta_id") == "17900000000000001" and e_up["metricas"].get("tiempo_medio_s") == 4.2
       and e_up["metricas"].get("salto_3s") == 0.333 and not e_up["metricas"].get("meta_error"),
       f"un Reel con otro id se encuentra por su enlace y trae sus cifras ({e_up.get('meta_id')}, "
       f"{e_up['metricas'].get('meta_error')!r})")
    ok(e_nada["metricas"].get("meta_error") and "Unsupported" in e_nada["metricas"].get("meta_detalle", "")
       and "#100" in e_nada["metricas"]["meta_detalle"],
       f"el que no aparece se queda con su error y con lo que dijo Meta aparte ({e_nada['metricas'].get('meta_detalle')!r})")
    with open(P._ruta_video(raiz, "v11")) as f:
        nada_de_tokens(f.read(), "el detalle guardado")
    ok(set(ESTADO.get("medios_pedidos") or []) == {"1784"},
       "la lista de medios solo se pide a la cuenta de Instagram que hay")
    r11b = P.medir_meta(raiz, ["v11"], forzar=True)
    ok(_envio(raiz, "v11", "i_up")["metricas"].get("tiempo_medio_s") == 4.2
       and not any("borradoUP77" in x["ruta"] for x in ESTADO["peticiones"][-6:]),
       "la vuelta siguiente usa el id de verdad (no vuelve al de Upload-Post)")
    ok("búsqueda por enlace" in e_nada["metricas"].get("meta_busqueda", "")
       and "@casas_con_diseno" in e_nada["metricas"]["meta_busqueda"],
       "y dice dónde se buscó su enlace sin encontrarlo")
    ok(e_nada["metricas"].get("meta_busqueda_al"), "con la hora de la búsqueda")
    # (árbitro) la búsqueda va DESPUÉS de Facebook: no lo deja sin leer
    ESTADO["peticiones"] = []
    _video(raiz, "v12", [{"id": "i_x", "red": "instagram", "estado": "publicado", "post_id": "borradoUP90",
                          "url": "https://www.instagram.com/reel/DCodigo_1/", "metricas": {}},
                         {"id": "f_x", "red": "facebook", "estado": "publicado", "post_id": f"{PAGINA}_555",
                          "duracion_s": 20, "metricas": {}}])
    P.medir_meta(raiz, ["v12"], forzar=True)
    rutas = [x["ruta"] for x in ESTADO["peticiones"]]
    i_media = next((i for i, x in enumerate(rutas) if "/1784/media" in x), 99)
    i_fb = next((i for i, x in enumerate(rutas) if "video_insights" in x), 99)
    ok(i_fb < i_media < 99 and _envio(raiz, "v12", "f_x")["metricas"].get("curva"),
       f"la búsqueda por enlace va después de leer Facebook ({i_fb} < {i_media})")
    ok(sum("me/accounts" in x for x in rutas) == 1, "y la lista de páginas se pide una vez por vuelta")
    # (árbitro) una búsqueda por envío y respiro, aunque se pulse seguido
    ok("búsqueda por enlace" in _envio(raiz, "v11", "i_nada")["metricas"].get("meta_busqueda", ""),
       "lo que se vio al buscarlo sigue mientras no se vuelve a buscar")
    antes = sum("/media" in x["ruta"] for x in ESTADO["peticiones"])
    P.medir_meta(raiz, ["v11"], forzar=True)
    ok(sum("/media" in x["ruta"] for x in ESTADO["peticiones"]) == antes,
       "el que no se encontró no se vuelve a buscar en cada «Actualizar»")
    # (árbitro) un error nuevo sin detalle no deja el detalle viejo
    P._apuntar_meta(raiz, {"i_nada": ("v11", {"error": "no es un Reel", "tipo": "FEED"}, {})})
    m_n = _envio(raiz, "v11", "i_nada")["metricas"]
    ok("meta_detalle" not in m_n and m_n.get("meta_busqueda", "").startswith("búsqueda por enlace"),
       "un error nuevo sin detalle borra lo viejo de Meta (lo de la búsqueda, en su clave, se queda)")
    # (árbitro, 2.ª vuelta) una búsqueda cortada a medias no cuenta como hecha
    original = MM.ClienteMeta.medios_ig
    MM.ClienteMeta.medios_ig = lambda self, ig_id, paginas_max=4: ([], False)
    try:
        _video(raiz, "v13", [{"id": "i_m", "red": "instagram", "estado": "publicado", "post_id": "borradoUP91",
                              "url": "https://www.instagram.com/reel/DCodigo_1/", "metricas": {}}])
        for _ in range(3):
            r13 = P.medir_meta(raiz, ["v13"], forzar=True)
    finally:
        MM.ClienteMeta.medios_ig = original
    m13 = _envio(raiz, "v13", "i_m")["metricas"]
    ok(m13.get("meta_busqueda", "").count("a medias") == 1 and not m13.get("meta_busqueda_al")
       and "búsqueda" not in m13.get("meta_detalle", ""),
       f"una búsqueda a medias lo dice UNA vez (tres vueltas) y se repite la próxima vez ({m13.get('meta_busqueda')!r})")
    # (árbitro, 3.ª vuelta) Meta no deja leer los medios de la cuenta (#10)
    def sin_permiso_medios(self, ig_id, paginas_max=4):
        raise MM.ErrorMeta("(#10) sin permiso", "otro", detalle="HTTP 403 #10/ Application does not have permission")
    MM.ClienteMeta.medios_ig = sin_permiso_medios
    try:
        _video(raiz, "v14", [{"id": "i_p", "red": "instagram", "estado": "publicado", "post_id": "borradoUP92",
                              "url": "https://www.instagram.com/reel/DCodigo_1/", "metricas": {}}])
        P.medir_meta(raiz, ["v14"], forzar=True)
        m14 = _envio(raiz, "v14", "i_p")["metricas"]
        ok("no deja leer sus medios" in m14.get("meta_busqueda", "") and "#10" in m14["meta_busqueda"]
           and m14.get("meta_busqueda_al"),
           f"si Meta no deja leer los medios, se dice con su #10 y lleva su respiro ({m14.get('meta_busqueda')!r})")
    finally:
        MM.ClienteMeta.medios_ig = original
    ok(not any("tiempo" in x for x in r13.get("errores", [])),
       "y cortar la búsqueda no avisa de «no dio tiempo» (lo demás se leyó)")
    ok(MM.shortcode_ig("https://www.instagram.com/usuario/reel/DCodigo_1/") == "DCodigo_1"
       and MM.shortcode_ig("https://instagram.com/p/AbC-12_x/") == "AbC-12_x"
       and MM.shortcode_ig("17900000000000001") == "" and MM.shortcode_ig("") == "",
       "el código corto sale del enlace (reel, p) y un id de números no lo es")
    # (árbitro, 25-11) MUCHOS Reels: de 50 en 50 por lotes, y a Facebook le
    # queda franja (con una llamada por Reel no se leía nunca)
    ESTADO["peticiones"] = []
    muchos = [{"id": f"m{i}", "red": "instagram", "estado": "publicado", "post_id": f"reel{i + 100}",
               "metricas": {}} for i in range(60)]
    muchos.append({"id": "m_fb", "red": "facebook", "estado": "publicado", "post_id": f"{PAGINA}_555",
                   "duracion_s": 20, "metricas": {}})
    _video(raiz, "v15", muchos)
    r15 = P.medir_meta(raiz, ["v15"], forzar=True, hasta=time.time() + P.TOPE_META_S)
    lotes = [x for x in ESTADO["peticiones"] if x.get("lote") is not None]
    ok(len(lotes) == 3 and sum(len(x["lote"]) for x in lotes) == 60,
       f"60 Reels en 3 llamadas por lotes de 25 ({[len(x['lote']) for x in lotes]})")
    ok(_envio(raiz, "v15", "m_fb")["metricas"].get("curva") and not r15.get("motivo"),
       f"y Facebook se lee igual ({r15.get('motivo')!r})")
    # (árbitro) un fallo de red en el 2.º lote no tira lo leído en el 1.º
    original_lote = MM.ClienteMeta._lote
    cuenta = {"n": 0}

    def segundo_falla(self, rutas, token=None):
        cuenta["n"] += 1
        if cuenta["n"] == 2:
            raise MM.ErrorMeta("no se ha podido hablar con Meta", "red")
        return original_lote(self, rutas, token)
    MM.ClienteMeta._lote = segundo_falla
    try:
        for e in muchos:
            e["metricas"] = {}
        _video(raiz, "v16", [dict(e, id=e["id"] + "b") for e in muchos[:60]])
        P.medir_meta(raiz, ["v16"], forzar=True)
    finally:
        MM.ClienteMeta._lote = original_lote
    leidos16 = [e for e in P._leer_video(raiz, "v16")["envios"] if (e.get("metricas") or {}).get("meta_al")
                and not e["metricas"].get("meta_error")]
    ok(len(leidos16) >= 25 and all(not e["id"].startswith(tuple(f"m{i}b" for i in range(25, 50)))
                                   for e in leidos16 if e["id"] in {f"m{i}b" for i in range(25, 50)}),
       f"un fallo de red en el 2.º lote guarda los 25 del 1.º ({len(leidos16)})")
    # (árbitro) un lote que tarda más que su plazo no deja sin leer Facebook
    cuenta["n"] = 0

    def segundo_lento(self, rutas, token=None):
        cuenta["n"] += 1
        if cuenta["n"] == 2:
            raise MM.ErrorMeta("no se ha podido hablar con Meta: timed out", "lento")
        return original_lote(self, rutas, token)
    MM.ClienteMeta._lote = segundo_lento
    try:
        _video(raiz, "v17", [dict(e, id=e["id"] + "c", metricas={}) for e in muchos])
        r17 = P.medir_meta(raiz, ["v17"], forzar=True)
    finally:
        MM.ClienteMeta._lote = original_lote
    ok(_envio(raiz, "v17", "m_fbc")["metricas"].get("curva") and r17.get("motivo") != "red",
       f"y Facebook se lee igual ({r17.get('motivo')!r})")
    # (árbitro, 3.ª vuelta) con TIEMPO DE VERDAD: un lote de Instagram que se
    # pasa de plazo no deja sin leer Facebook (va antes)
    original_cm = P.cliente_meta
    P.cliente_meta = lambda: MM.ClienteMeta(TOKEN, base=base, plazo=1)
    ESTADO["retraso_lote"] = 2.5
    try:
        _video(raiz, "v18", [dict(e, id=e["id"] + "d", metricas={}) for e in muchos])
        r18 = P.medir_meta(raiz, ["v18"], forzar=True, hasta=time.time() + 6.5)
    finally:
        P.cliente_meta = original_cm
        ESTADO["retraso_lote"] = 0.0
    ok(_envio(raiz, "v18", "m_fbd")["metricas"].get("curva") and r18.get("motivo") != "red",
       f"con un lote lento de verdad, Facebook se lee igual ({r18.get('motivo')!r}, {r18.get('errores')})")
    ok(MM._TOPE_LOTE_ACTUAL < MM.TOPE_LOTE,
       f"y las vueltas siguientes piden lotes más pequeños ({MM._TOPE_LOTE_ACTUAL})")
    MM._TOPE_LOTE_ACTUAL = MM.TOPE_LOTE
    # (árbitro, 4.ª vuelta) un vídeo de Facebook LENTO no deja a Instagram sin leer
    original_fb = MM.ClienteMeta._facebook_uno

    def fb_lento(self, token_pagina, ident, duracion):
        raise MM.ErrorMeta("no se ha podido hablar con Meta: timed out", "lento")
    MM.ClienteMeta._facebook_uno = fb_lento
    try:
        _video(raiz, "v19", [{"id": "s_ig", "red": "instagram", "estado": "publicado", "post_id": "reel1",
                              "metricas": {}},
                             {"id": "s_fb", "red": "facebook", "estado": "publicado",
                              "post_id": f"{PAGINA}_555", "duracion_s": 20, "metricas": {}}])
        r19 = P.medir_meta(raiz, ["v19"], forzar=True)
    finally:
        MM.ClienteMeta._facebook_uno = original_fb
    m_ig, m_fb = _envio(raiz, "v19", "s_ig")["metricas"], _envio(raiz, "v19", "s_fb")["metricas"]
    ok(m_ig.get("tiempo_medio_s") is not None and not r19.get("motivo"),
       f"un vídeo de Facebook lento no deja a Instagram sin leer ({r19.get('motivo')!r})")
    ok("tardó demasiado" in m_fb.get("meta_error", "") and m_fb.get("meta_al"),
       f"y ese vídeo lo dice, con su reloj ({m_fb.get('meta_error')!r})")
    # (árbitro, 5.ª vuelta) lo mismo con TIEMPO DE VERDAD: Facebook espera de
    # verdad su plazo; el vídeo queda apuntado (con reloj) y la vuelta
    # siguiente lee Instagram
    original_cm = P.cliente_meta
    P.cliente_meta = lambda: MM.ClienteMeta(TOKEN, base=base, plazo=1)
    ESTADO["retraso_fb"] = 1.6
    plazo_antes, MM.PLAZO_S = MM.PLAZO_S, 1      # la misma proporción que 6 s / 12 s
    try:
        _video(raiz, "v20", [{"id": "t_ig", "red": "instagram", "estado": "publicado", "post_id": "reel2",
                              "metricas": {}},
                             {"id": "t_fb", "red": "facebook", "estado": "publicado",
                              "post_id": f"{PAGINA}_555", "duracion_s": 20, "metricas": {}}])
        P.medir_meta(raiz, ["v20"], forzar=True, hasta=time.time() + 1.8)
        m_fb = _envio(raiz, "v20", "t_fb")["metricas"]
        ok("tardó demasiado" in m_fb.get("meta_error", "") and m_fb.get("meta_al"),
           f"con Facebook lento DE VERDAD, ese vídeo queda apuntado con su reloj ({m_fb.get('meta_error')!r})")
        P.medir_meta(raiz, ["v20"], hasta=time.time() + 1.8)
        ok(_envio(raiz, "v20", "t_ig")["metricas"].get("tiempo_medio_s") is not None,
           "y la vuelta siguiente lee Instagram (no se queda sin leer para siempre)")
    finally:
        P.cliente_meta = original_cm
        ESTADO["retraso_fb"] = 0.0
        MM.PLAZO_S = plazo_antes
    # (árbitro, 5.ª vuelta) un medio del lote con 200 y HTML, por el lector de verdad
    cli11 = MM.ClienteMeta(TOKEN, base=base)
    original_pedir = cli11._pedir
    cli11._pedir = lambda metodo, url, cuerpo, token: (
        [{"code": 200, "body": "<html>error</html>"}] if metodo == "POST" else original_pedir(metodo, url, cuerpo, token))
    r11 = cli11.instagram(["reel1"])
    ok("JSON" in r11.get("reel1", {}).get("detalle", "") and not cli11.sin_tiempo,
       "un 200 con HTML en el lote de verdad es un error con reloj, no «no dio tiempo»")
    # (árbitro) con el cupo cerca o un fatal a mitad, lo bueno del lote se queda
    cli7 = MM.ClienteMeta(TOKEN, base=base)
    bueno = {"id": "x", "media_product_type": "REELS",
             "insights": _insights([("ig_reels_avg_watch_time", 5000)])}

    def lote_mezclado(rutas, token=None):
        cli7.cerca_del_cupo = True
        return [(200, dict(bueno, id="a1")), (400, {"error": {"code": 1, "message": "raro"}}),
                (200, dict(bueno, id="a3")), (200, "<html>no es json</html>")]
    cli7._lote = lote_mezclado
    r7 = cli7.instagram(["a1", "a2", "a3", "a4"])
    ok(r7.get("a1", {}).get("tiempo_medio_s") == 5.0 and r7.get("a3", {}).get("tiempo_medio_s") == 5.0,
       f"con el cupo cerca, lo que ya llegó en el lote se queda ({sorted(r7)})")
    ok("error" in r7.get("a4", {}) and "JSON" in r7["a4"].get("detalle", ""),
       "un 200 que no es JSON es un error con su reloj, no «no dio tiempo»")
    cli8 = MM.ClienteMeta(TOKEN, base=base)
    cli8._lote = lambda rutas, token=None: [(200, dict(bueno, id="b1")),
                                             (400, {"error": {"code": 4, "message": "(#4) limit"}}),
                                             (200, dict(bueno, id="b3"))]
    r8 = cli8.instagram(["b1", "b2", "b3"])
    ok(cli8.cerca_del_cupo and r8.get("b1", {}).get("tiempo_medio_s") == 5.0
       and r8.get("b3", {}).get("tiempo_medio_s") == 5.0,
       f"un «espera» de Meta a mitad del lote para, y lo de antes Y de después se queda ({sorted(r8)})")
    cli10 = MM.ClienteMeta(TOKEN, base=base)
    cli10._lote = lambda rutas, token=None: [(200, dict(bueno, id="c1")),
                                              (401, {"error": {"code": 190, "message": "expired"}}),
                                              (200, dict(bueno, id="c3"))]
    try:
        cli10.instagram(["c1", "c2", "c3"])
        ok(False, "un token caducado a mitad del lote se lanza")
    except MM.ErrorMeta as fallo:
        ok(fallo.motivo == "caducado" and set(getattr(fallo, "parcial", {})) == {"c1", "c3"},
           f"un token caducado a mitad del lote se lanza con lo leído ({sorted(getattr(fallo, 'parcial', {}))})")
    # (árbitro) Meta retira una métrica: UN lote más, no dos llamadas por medio
    ESTADO.update(retirada="reels_skip_rate", peticiones=[])
    cli9 = MM.ClienteMeta(TOKEN, base=base)
    r9b = cli9.instagram([f"reel{i}" for i in range(200, 210)])
    ESTADO["retirada"] = ""
    ok(len(ESTADO["peticiones"]) == 2 and cli9.retiradas == ["reels_skip_rate"]
       and all("error" not in v for v in r9b.values()),
       f"una métrica retirada: 2 llamadas para 10 Reels y apuntada una vez "
       f"({len(ESTADO['peticiones'])}, {cli9.retiradas})")
    # árbitro del tren, 25-11 (1): un post de página BORRADO no corta Facebook
    _video(raiz, "v9", [{"id": "f_borr", "red": "facebook", "estado": "a_mano",
                         "post_id": f"{PAGINA}_999", "metricas": {}},
                        {"id": "f_bien", "red": "facebook", "estado": "a_mano",
                         "post_id": f"{PAGINA}_555", "duracion_s": 20, "metricas": {}}])
    r9 = P.medir_meta(raiz, ["v9"], forzar=True)
    mb, mo = _envio(raiz, "v9", "f_borr")["metricas"], _envio(raiz, "v9", "f_bien")["metricas"]
    ok(not r9.get("motivo") and mo.get("curva") and mb.get("meta_error") and mb.get("meta_al")
       and "Unsupported" not in mb["meta_error"] and not any("Unsupported" in x for x in r9["errores"]),
       f"un post de Facebook borrado se apunta en su tarjeta (en castellano, con reloj) y el otro se lee "
       f"({r9.get('motivo')!r}, {mb.get('meta_error')!r})")
    # (2) un #10 de UN Reel (publicado antes de pasar a profesional) no es del token
    _video(raiz, "v10", [{"id": "i_antes", "red": "instagram", "estado": "a_mano", "post_id": "antes1",
                          "metricas": {}},
                         {"id": "i_bien", "red": "instagram", "estado": "a_mano", "post_id": "reel2",
                          "metricas": {}}])
    r10 = P.medir_meta(raiz, ["v10"], forzar=True)
    ma, mo = _envio(raiz, "v10", "i_antes")["metricas"], _envio(raiz, "v10", "i_bien")["metricas"]
    ok(not r10.get("motivo") and mo.get("salto_3s") is not None and "profesional" in ma.get("meta_error", "")
       and ma.get("meta_al"),
       f"un Reel de antes de la cuenta profesional se dice en su tarjeta y los demás se leen ({ma.get('meta_error')!r})")
    # (3) sin instagram_manage_insights, Facebook se lee igual y sus tarjetas no se tocan
    _video(raiz, "v11", [{"id": "i_np", "red": "instagram", "estado": "a_mano", "post_id": "reel1",
                          "metricas": {}},
                         {"id": "f_np", "red": "facebook", "estado": "a_mano",
                          "post_id": f"{PAGINA}_555", "duracion_s": 20, "metricas": {}}])
    ESTADO["modo"] = "permiso_ig"
    try:
        r11 = P.medir_meta(raiz, ["v11"], forzar=True)
    finally:
        ESTADO["modo"] = ""
    mi, mf = _envio(raiz, "v11", "i_np")["metricas"], _envio(raiz, "v11", "f_np")["metricas"]
    ok("instagram_manage_insights" in mi.get("meta_error", "") and mf.get("curva")
       and not mf.get("meta_error") and any("Instagram" in x and "instagram_manage_insights" in x
                                           for x in r11["errores"]),
       f"sin el permiso de Instagram, Facebook se lee igual y solo Instagram lo dice ({r11['errores']})")
    # con el token caducado, también las tarjetas de Facebook lo dicen
    _video(raiz, "v14", [{"id": "i_cad", "red": "instagram", "estado": "a_mano", "post_id": "reel1",
                          "metricas": {}},
                         {"id": "f_cad", "red": "facebook", "estado": "a_mano",
                          "post_id": f"{PAGINA}_555", "metricas": {}}])
    ESTADO["modo"] = "caducado"
    try:
        P.medir_meta(raiz, ["v14"], forzar=True)
    finally:
        ESTADO["modo"] = ""
    ok("caducado" in _envio(raiz, "v14", "f_cad")["metricas"].get("meta_error", "")
       and "caducado" in _envio(raiz, "v14", "i_cad")["metricas"].get("meta_error", ""),
       "token caducado: las tarjetas de las dos redes lo dicen")
    # sin token a secas, ninguna tarjeta se toca (basta el aviso general)
    _poner_token("")
    _video(raiz, "v8", [{"id": "e_st", "red": "instagram", "estado": "a_mano", "post_id": "reel1",
                         "metricas": {}}])
    r8 = P.medir_meta(raiz, ["v8"], forzar=True)
    _poner_token(TOKEN)
    ok(r8.get("motivo") == "sin_token" and not _envio(raiz, "v8", "e_st")["metricas"],
       "sin token: el aviso general, y las tarjetas sin tocar")
    # un id que Meta no contesta tampoco va el primero de la cola en cada vuelta
    _video(raiz, "v4", [{"id": "e_malo", "red": "instagram", "estado": "a_mano", "post_id": "bad7",
                         "metricas": {}},
                        {"id": "e_carrusel", "red": "instagram", "estado": "a_mano", "post_id": "reel1",
                         "tipo": "Carrusel", "metricas": {}}])
    P.medir_meta(raiz, ["v4"])
    m = _envio(raiz, "v4", "e_malo")["metricas"]
    ok(m.get("meta_error") and m.get("meta_al"), "un id que Meta no contesta guarda su reloj (respiro)")
    igual([e for _p, e in P._envios_meta(raiz, ["v4"], False)], [],
          "y no se vuelve a pedir enseguida; un carrusel no se le pregunta a Meta")
    ok(not _envio(raiz, "v4", "e_carrusel")["metricas"], "el carrusel queda sin tocar")

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
    # (4) la segunda vuelta no tumba «Actualizar» si algo raro falla dentro
    _video(raiz, "v12", [{"id": "e_12", "red": "instagram", "estado": "publicado", "lote": "l12",
                          "metricas": {}}])

    def up_trae_otro(*_a, **_k):
        datos = P._leer_video(raiz, "v12")
        datos["envios"][0]["post_id"] = "reel2"
        P._escribir(P._ruta_video(raiz, "v12"), datos)
        return dict(vacia)
    llamadas_raras = {"n": 0}
    antes_mm = P.medir_meta

    def medir_raro(*a, **k):
        llamadas_raras["n"] += 1
        if llamadas_raras["n"] == 2:
            raise RuntimeError("algo raro")
        return antes_mm(*a, **k)
    P.actualizar_metricas, P.medir_meta = up_trae_otro, medir_raro
    try:
        r12 = P.medir(raiz, ["v12"])
    finally:
        P.actualizar_metricas, P.medir_meta = (lambda *a, **k: dict(vacia)), antes_mm
    ok(llamadas_raras["n"] == 2 and any("algo raro" in x for x in r12.get("errores", [])),
       "si la segunda vuelta falla, «Actualizar» contesta igual y lo dice")
    # (8) con otra lectura de Meta en marcha, la respuesta lo dice
    P._LOCK_META.acquire()
    try:
        r13 = P.medir(raiz, ["v12"], forzar=True)
    finally:
        P._LOCK_META.release()
    ok(any("otro «Actualizar» en marcha" in x for x in r13.get("errores", [])),
       "con Meta ya leyéndose desde otra pestaña, «Actualizar» lo dice")
    # si la primera vuelta ya dijo que no (caducado, cupo…), no hay segunda
    llamadas = []
    antes_meta2 = P.medir_meta
    P.medir_meta = lambda *a, **k: (llamadas.append(1), {"leidos": 0, "actualizados": 0, "pendientes": 0,
                                                           "errores": ["cupo"], "motivo": "cupo"})[1]
    _video(raiz, "v5", [{"id": "e_n5", "red": "instagram", "estado": "publicado", "post_id": "reel2",
                         "metricas": {}}])
    try:
        r5 = P.medir(raiz, ["v5"])
    finally:
        P.medir_meta = antes_meta2
    ok(len(llamadas) == 1 and r5.get("meta", {}).get("motivo") == "cupo",
       f"con «cupo» en la primera vuelta no se vuelve a llamar a Meta ({len(llamadas)} llamadas)")
    total = {"posts": 0}
    P._suma(total, {"vistas": 1000, "media_vista": 0.5})
    P._suma(total, {"vistas": 10, "salto_3s": 0.9})
    P._medias(total)
    igual(total.get("salto_3s"), None, "en un total, el salto de un Reel de 10 vistas no cuenta")
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

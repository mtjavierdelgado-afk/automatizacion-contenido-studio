"""Prueba de ANALIZAR UNA CUENTA (rama analizar-cuentas, 18-10-2026).

Sin red, sin claves de verdad y sin pagar nada:

  1. las piezas: entender un enlace, el coste, leer lo que devuelve cada actor
     de Apify, el resumen para Claude;
  2. las TRES fuentes de verdad (`motores/lectura_redes/lectores.py`) contra
     un YouTube, un Meta y un Apify falsos que corren aquí en un hilo: lo que se
     pide, lo que se lee, los errores y que ninguna clave sale en un mensaje;
  3. el orden y el dinero (`pasos/cuentas_ajenas.py`): primero gratis, Apify
     de respaldo, «no existe» no se paga, el tope al mes, la caché de 24 h;
  4. Claude: el análisis y los guiones desde una cuenta (con un doble);
  5. el Studio por HTTP (si hay fastapi), en modo simulado.

    python pasos/prueba_cuentas.py
"""
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="cuentas_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
os.environ["ESTUDIO_GUIONISTA_AISLADO"] = os.path.join(CARPETA, "aislado")
os.environ.pop("ESTUDIO_SIMULAR", None)

import cuentas_ajenas as C  # noqa: E402
import guionista as G  # noqa: E402
import parrilla as P  # noqa: E402
from motores.lectura_redes import lectores as F  # noqa: E402

_ok = 0
_fallos = []
CLAVE_YT = "AIzaSyCLAVEDEPRUEBA1234567890"
TOKEN_META = "EAABTOKENDEPRUEBA0987654321"
TOKEN_META_STUDIO = "EAABTOKENDELSTUDIO1122334455"
TOKEN_APIFY = "apify_api_TOKENDEPRUEBA5555"


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLO {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def seccion(titulo):
    print(f"\n[{titulo}]")


def lanza(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except (C.ErrorCuentas, F.ErrorLectura) as fallo:
        return fallo
    return None


# ------------------------------------------------------------- 1. piezas

def prueba_piezas():
    seccion("1] piezas")
    igual(C.entender("https://www.tiktok.com/@unafiesta.lima?lang=es"), ("tiktok", "unafiesta.lima"),
          "un enlace de TikTok")
    igual(C.entender("https://www.instagram.com/estadoplay/"), ("instagram", "estadoplay"), "uno de Instagram")
    for raro in ("https://www.instagram.com/explore/tags/fiesta/", "https://www.instagram.com/accounts/login/",
                 "https://www.youtube.com/c/Canal", "https://vm.tiktok.com/ZMabc/"):
        ok(lanza(C.entender, raro) is not None, f"no se toma por un perfil: {raro}")
    igual(C.entender("https://www.youtube.com/@MrBeast/videos"), ("youtube", "MrBeast"), "uno de YouTube (@)")
    igual(C.entender("https://youtube.com/channel/UCX6OQ3DkcsbYNE6H8uQQuVA"),
          ("youtube", "UCX6OQ3DkcsbYNE6H8uQQuVA"), "uno de YouTube (canal)")
    igual(C.entender("@ana_lopez", "instagram"), ("instagram", "ana_lopez"), "un @usuario con su red")
    ok(lanza(C.entender, "https://www.instagram.com/reel/ABC123/") is not None, "el enlace de un vídeo, no")
    ok(lanza(C.entender, "https://example.com/x") is not None, "un enlace de otra web, no")
    ok(lanza(C.entender, "@ana") is not None, "sin red, no")
    ok(lanza(C.entender, "ana; rm -rf /", "tiktok") is not None, "un usuario raro, no")
    igual(F.coste_apify("tiktok", 1000), 1.7, "TikTok: 1,70 $ cada 1.000 vídeos")
    igual(F.coste_apify("instagram", 30), 0.078, "30 de Instagram: unos 8 céntimos")
    igual([F._duracion("PT1M5S"), F._duracion("1:05"), F._duracion(65), F._duracion("nada")],
          [65, 65.0, 65.0, None], "las duraciones")
    tk = F.leer_items_apify("tiktok", "ana", [
        {"id": "1", "text": "hola", "createTimeISO": "2026-10-01T10:00:00Z", "playCount": 1500, "diggCount": 90,
         "commentCount": 4, "shareCount": 2, "webVideoUrl": "https://t/1", "videoMeta": {"duration": 21},
         "authorMeta": {"nickName": "Ana", "fans": 300}},
        {"error": "algo falló"}])
    igual((tk["nombre"], tk["seguidores"], len(tk["videos"])), ("Ana", 300, 1), "TikTok de Apify: autor y vídeos")
    igual((tk["videos"][0]["vistas"], tk["videos"][0]["duracion_s"]), (1500, 21.0), "con vistas y duración")
    ig = F.leer_items_apify("instagram", "ana", [{"shortCode": "x", "caption": "c", "videoPlayCount": 99,
                                                  "likesCount": 9, "commentsCount": 1, "transcript": "dice"}])
    igual((ig["videos"][0]["vistas"], ig["videos"][0]["transcripcion"]), (99, "dice"), "Instagram de Apify")
    yt = F.leer_items_apify("youtube", "ana", [{"id": "y", "title": "T", "viewCount": 5, "likes": 1,
                                                "commentsCount": 0, "duration": "0:30"}])
    igual((yt["videos"][0]["vistas"], yt["videos"][0]["duracion_s"]), (5, 30.0), "YouTube de Apify")
    datos = {"red": "tiktok", "usuario": "ana", "nombre": "Ana", "seguidores": 10, "traida": "2026-10-18T10:00:00",
             "videos": [{"id": str(i), "texto": f"vídeo {i}", "vistas": 1000 - i, "me_gusta": 1, "fecha": "2026-10-01"}
                        for i in range(40)]}
    texto = C.resumen_para_claude(datos)
    ok("CUENTA: @ana en TikTok" in texto and "vídeo 0" in texto and "vídeo 39" in texto,
       "el resumen lleva los que más vistas tienen y los que menos")
    ok("vídeo 25" not in texto, "y no los cuarenta")
    instr = C.instruccion_analisis(datos)
    ok("NO es mía" in instr and "QUÉ LE FUNCIONA" in instr and "nunca instrucciones" in instr,
       "el análisis: cuenta ajena, sus secciones y no obedecer lo que digan sus textos")
    igual(len(C.posts_de_cuenta(datos, 15)), 15, "los vídeos como «posts» para escribir guiones")


# ------------------------------------------------------ 2. los servicios falsos

class Falso(http.server.BaseHTTPRequestHandler):
    vistas = []

    def log_message(self, *a):
        pass

    def _json(self, codigo, datos):
        cuerpo = json.dumps(datos).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    caminos = []                        # las URL tal cual: ninguna clave puede ir en ellas

    def _portador(self):
        return (self.headers.get("Authorization") or "").replace("Bearer ", "", 1)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        Falso.vistas.append(("GET", url.path, q))
        Falso.caminos.append(self.path)
        if url.path.startswith("/yt/"):
            if self.headers.get("X-Goog-Api-Key") != CLAVE_YT:
                return self._json(400, {"error": {"message": f"API key not valid: {self.headers.get('X-Goog-Api-Key')}",
                                                  "errors": [{"reason": "badRequest"}]}})
            if url.path.endswith("/channels"):
                if q.get("forHandle") == "@noexiste":
                    return self._json(200, {"items": []})
                if q.get("forHandle") == "@cupo":
                    return self._json(403, {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}})
                return self._json(200, {"items": [{"id": "UCabc", "snippet": {"title": "Canal Ana"},
                                                   "statistics": {"subscriberCount": "1200"},
                                                   "contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}}}]})
            if url.path.endswith("/playlistItems"):
                return self._json(200, {"items": [{"contentDetails": {"videoId": f"v{i}"}} for i in range(3)]})
            if url.path.endswith("/videos"):
                ids = q["id"].split(",")
                return self._json(200, {"items": [{"id": i, "snippet": {"title": f"Título {i}", "description": "d",
                                                                        "publishedAt": "2026-10-01T10:00:00Z"},
                                                   "statistics": {"viewCount": str(100 * (n + 1)), "likeCount": "5",
                                                                  "commentCount": "1"},
                                                   "contentDetails": {"duration": "PT45S"}} for n, i in enumerate(ids)]})
        if url.path.startswith("/meta/"):
            if self._portador() not in (TOKEN_META, TOKEN_META_STUDIO):
                return self._json(400, {"error": {"code": 190, "message": f"Invalid OAuth token {self._portador()}"}})
            if url.path.endswith("/me/accounts") and self._portador() == TOKEN_META_STUDIO:
                return self._json(200, {"data": [{"name": "Studio", "instagram_business_account":
                                                  {"id": "178419999", "username": "studio_mirador"}}]})
            if url.path.endswith("/me/accounts"):
                return self._json(200, {"data": [{"name": "EstadoPlay", "instagram_business_account":
                                                  {"id": "178414000", "username": "estadoplay"}}]})
            campos = q.get("fields", "")
            if "personal_" in campos:
                return self._json(400, {"error": {"code": 110, "message": "Invalid user id"}})
            return self._json(200, {"business_discovery": {
                "username": "competencia", "name": "La Competencia", "followers_count": 5000,
                "media": {"data": [{"id": "m1", "caption": "Reel 1", "like_count": 50, "comments_count": 3,
                                    "view_count": 4000, "timestamp": "2026-10-02T20:00:00+0000",
                                    "permalink": "https://instagram.com/p/m1", "media_product_type": "REELS"}]}}})
        return self._json(404, {})

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        Falso.vistas.append(("POST", url.path, q, cuerpo))
        Falso.caminos.append(self.path)
        if url.path.startswith("/apify/"):
            if self._portador() != TOKEN_APIFY:
                return self._json(401, {"error": {"message": f"token {self._portador()} no vale"}})
            usuario = (cuerpo.get("profiles") or cuerpo.get("username") or ["?"])[0]
            if usuario == "sincredito":
                return self._json(402, {"error": {"message": "Not enough credit"}})
            if usuario == "tarda":
                return self._json(408, {"error": {"message": "Run timed out"}})
            if usuario == "camposraros":       # el actor cambió de nombres: cobra y no se entiende nada
                return self._json(201, [{"loQueSea": i} for i in range(6)])
            if usuario.startswith("noexiste"):
                return self._json(201, [])
            if "tiktok" in url.path:
                return self._json(201, [{"id": str(i), "text": f"tiktok {i}", "playCount": 900 - i, "diggCount": 10,
                                         "createTimeISO": "2026-10-01T00:00:00Z", "authorMeta": {"nickName": usuario}}
                                        for i in range(4)])
            return self._json(201, [{"shortCode": "s1", "caption": "por apify", "videoPlayCount": 777,
                                     "likesCount": 7, "commentsCount": 1}])
        return self._json(404, {})


def arrancar_falso():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), Falso)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{puerto}"
    return servidor, {F.BASE_YOUTUBE: base + "/yt", F.BASE_META: base + "/meta", F.BASE_APIFY: base + "/apify"}


def prueba_fuentes(bases):
    seccion("2] las tres fuentes, contra servicios falsos")
    r = F.youtube(CLAVE_YT, "@ana", 3, bases=bases)
    igual((r["nombre"], r["seguidores"], len(r["videos"]), r["fuente"], r["coste_usd"]),
          ("Canal Ana", 1200, 3, "youtube_api", 0.0), "YouTube: el canal y sus vídeos, gratis")
    igual((r["videos"][2]["vistas"], r["videos"][0]["duracion_s"]), (300, 45), "con vistas y duración")
    pedidas = [v for v in Falso.vistas if v[1].startswith("/yt/")]
    igual([v[1].rsplit("/", 1)[-1] for v in pedidas[-3:]], ["channels", "playlistItems", "videos"],
          "tres llamadas (3 unidades), sin search.list")
    igual(pedidas[-3][2].get("forHandle"), "@ana", "busca por @handle")
    F.youtube(CLAVE_YT, "UCX6OQ3DkcsbYNE6H8uQQuVA", 3, bases=bases)
    igual([v for v in Falso.vistas if v[1].endswith("/channels")][-1][2].get("id"), "UCX6OQ3DkcsbYNE6H8uQQuVA",
          "o por id de canal")
    f = lanza(F.youtube, CLAVE_YT, "noexiste", 3, bases=bases)
    igual(getattr(f, "motivo", ""), "no_encontrada", "un canal que no existe")
    f = lanza(F.youtube, CLAVE_YT, "cupo", 3, bases=bases)
    igual(getattr(f, "motivo", ""), "limite", "sin cupo diario")
    f = lanza(F.youtube, "AIzaOTRACLAVEMALA1234", "ana", 3, bases=bases)
    ok(f is not None and f.motivo == "clave" and "AIzaOTRACLAVEMALA1234" not in str(f),
       f"una clave mala, sin la clave en el mensaje: {f}")
    igual(getattr(lanza(F.youtube, "", "ana"), "motivo", ""), "sin_clave", "sin clave")

    r = F.instagram(TOKEN_META, "178414000", "competencia", 10, bases=bases)
    igual((r["nombre"], r["seguidores"], r["videos"][0]["vistas"], r["videos"][0]["tipo"]),
          ("La Competencia", 5000, 4000, "REELS"), "Instagram oficial: con las vistas de sus Reels")
    campos = [v for v in Falso.vistas if v[1].endswith("/178414000")][-1][2]["fields"]
    ok("business_discovery.username(competencia)" in campos and "view_count" in campos, "pide business_discovery con view_count")
    f = lanza(F.instagram, TOKEN_META, "178414000", "personal_ana", 10, bases=bases)
    igual(getattr(f, "motivo", ""), "no_profesional", "una cuenta personal: no_profesional")
    f = lanza(F.instagram, "EAABMALO99999999", "178414000", "x", 10, bases=bases)
    ok(f is not None and f.motivo == "clave" and "EAABMALO99999999" not in str(f), "un token malo, sin el token en el mensaje")
    ok(lanza(F.instagram, TOKEN_META, "1", "x; drop", 10, bases=bases) is not None, "un usuario raro no se manda")
    igual(F.instagram_mi_cuenta(TOKEN_META, bases=bases), [{"id": "178414000", "usuario": "estadoplay", "pagina": "EstadoPlay"}],
          "«Buscar mi cuenta» con el token")

    r = F.apify(TOKEN_APIFY, "tiktok", "ana", 4, bases=bases)
    igual((len(r["videos"]), r["fuente"], r["coste_usd"]), (4, "apify", 0.0068), "Apify TikTok, con su coste")
    pedido = [v for v in Falso.vistas if v[0] == "POST"][-1]
    ok("clockworks~tiktok-scraper" in pedido[1] and pedido[3].get("profiles") == ["ana"]
       and pedido[3].get("shouldDownloadVideos") is False, "el actor de TikTok, sin descargar vídeos")
    f = lanza(F.apify, TOKEN_APIFY, "tiktok", "sincredito", 4, bases=bases)
    igual(getattr(f, "motivo", ""), "limite", "sin crédito en Apify")
    f = lanza(F.apify, "apify_api_MALO_1234567", "tiktok", "ana", 4, bases=bases)
    ok(f is not None and f.motivo == "clave" and "apify_api_MALO_1234567" not in str(f), "un token malo de Apify, sin el token")
    f = lanza(F.apify, TOKEN_APIFY, "tiktok", "noexiste_x", 4, bases=bases)
    igual(getattr(f, "motivo", ""), "no_encontrada", "una cuenta sin vídeos públicos")


# ------------------------------------------------------ 3. el orden y el dinero

def prueba_orden(bases):
    seccion("3] primero gratis, luego de pago, con tope y caché")
    raiz = os.path.join(CARPETA, "orden")
    os.makedirs(raiz)
    os.environ["ESTUDIO_LECTURA_BASES"] = json.dumps(bases)
    try:
        pub = C.claves_publicas()
        igual((pub["youtube"]["puesta"], pub["pago"], pub["tope_usd"]), (False, True, 5.0),
              "de fábrica: sin claves, el pago permitido y 5 $ de tope")
        f = lanza(C.leer, raiz, "tiktok", "ana", 10)
        ok(f is not None and f.codigo == 409 and "Apify" in str(f), "sin ninguna clave, dice qué falta")
        C.guardar_claves({"youtube_clave": CLAVE_YT, "meta_token": TOKEN_META, "apify_token": TOKEN_APIFY})
        pub = C.claves_publicas()
        ok(CLAVE_YT not in json.dumps(pub) and TOKEN_META not in json.dumps(pub) and pub["apify"]["cola"] == "…5555",
           "las claves no bajan a la pantalla: solo sus 4 últimos")
        ok(pub["meta"]["caduca"], "el token de Meta dice cuándo caduca (60 días)")
        with open(C._ruta_claves(), encoding="utf-8") as fh:
            ok(TOKEN_APIFY in fh.read(), "y se guardan en la carpeta de secretos")
        ok(C._ruta_claves().startswith(os.environ["ESTUDIO_SECRETOS"]), "(la de ESTUDIO_SECRETOS)")
        cuentas = C.buscar_mi_instagram()
        igual((cuentas[0]["usuario"], C.claves_publicas()["meta"]["ig_id"]), ("estadoplay", "178414000"),
              "«Buscar mi cuenta» guarda tu id si hay una sola")
        # No queda atado a una cuenta: el dueño cambiará la de EstadoPlay por una del Studio.
        C.guardar_claves({"meta_token": TOKEN_META_STUDIO})
        igual(C.claves_publicas()["meta"]["ig_id"], "", "un token nuevo olvida la cuenta de antes")
        cuentas = C.buscar_mi_instagram()
        igual((cuentas[0]["usuario"], C.claves_publicas()["meta"]["ig_id"]), ("studio_mirador", "178419999"),
              "y «Volver a buscar» encuentra la nueva: cambiar de cuenta es pegar otro token")
        d = C.leer(raiz, "instagram", "competencia", 10)
        igual(d["fuente"], "instagram_oficial", "la cuenta nueva mira igual que la vieja")
        C.borrar(raiz, "instagram", "competencia")
        C.guardar_claves({"meta_token": TOKEN_META})
        C.buscar_mi_instagram()
        ok(lanza(C.guardar_claves, {"ig_id": "abc"}) is not None, "un id de Instagram con letras, no")
        ok(lanza(C.guardar_claves, {"tope_usd": 9999}) is not None, "un tope absurdo, no")

        d = C.leer(raiz, "youtube", "ana", 10)
        igual((d["fuente"], C.gasto_del_mes(raiz)), ("youtube_api", 0.0), "YouTube va por la API gratis")
        d = C.leer(raiz, "instagram", "competencia", 10)
        igual((d["fuente"], C.gasto_del_mes(raiz)), ("instagram_oficial", 0.0), "una cuenta profesional, por la vía oficial")
        n = len([v for v in Falso.vistas if v[0] == "POST"])
        f = lanza(C.leer, raiz, "instagram", "personal_ana", 10)
        ok(f is not None and f.codigo == 402 and f.pide_pago and f.pide_pago["coste_usd"] == F.coste_apify("instagram", 10),
           "si lo gratis no sirve, PREGUNTA antes de pagar (con el precio)")
        ok(len([v for v in Falso.vistas if v[0] == "POST"]) == n and C.gasto_del_mes(raiz) == 0,
           "y sin el «sí» no se llama a Apify")
        d = C.leer(raiz, "instagram", "personal_ana", 10, pagar=True)
        igual(d["fuente"], "apify", "con el «sí», una cuenta personal pasa a Apify")
        q = [v for v in Falso.vistas if v[0] == "POST"][-1][2]
        igual((q.get("maxItems"), "maxTotalChargeUsd" in q), ("10", True),
              "con techo del lado de Apify: tantos resultados y lo que queda del tope")
        ok(any("profesional" in x for x in d["intentos"]), "y dice por qué")
        gasto = C.gasto_del_mes(raiz)
        ok(gasto > 0, f"lo gastado se apunta ({gasto} $)")
        d = C.leer(raiz, "instagram", "personal_ana", 10)
        ok(d.get("de_cache") and C.gasto_del_mes(raiz) == gasto, "la misma cuenta, el mismo día: de la caché, sin pagar")
        d = C.leer(raiz, "instagram", "personal_ana", 10, forzar=True, pagar=True)
        ok(C.gasto_del_mes(raiz) > gasto, "«Volver a traer» sí paga")
        ok(not C.plan(raiz, "instagram", "personal_ana", 30)["guardada"]["sirve"],
           "pedir más vídeos de los guardados hoy: la copia no sirve (y la pantalla preguntará)")
        ok(C.plan(raiz, "instagram", "personal_ana", 10)["guardada"]["sirve"], "los mismos, sí")
        ok(C.plan(raiz, "tiktok", "x", "50")["vias"], "un «cuántos» escrito como texto no rompe el plan")
        d = C.leer(raiz, "tiktok", "ana", 10, pagar=True)
        igual(d["fuente"], "apify", "TikTok, por Apify")
        igual([v["vistas"] for v in d["videos"]], [900, 899, 898, 897], "los vídeos, de más a menos vistas")
        n = len([v for v in Falso.vistas if v[0] == "POST"])
        f = lanza(C.leer, raiz, "youtube", "noexiste", 10)
        ok(f is not None and len([v for v in Falso.vistas if v[0] == "POST"]) == n,
           "una cuenta que no existe no se intenta pagando")

        # lo que Apify cobra aunque falle también cuenta para el tope
        antes = C.gasto_del_mes(raiz)
        lanza(C.leer, raiz, "tiktok", "tarda", 10, pagar=True)
        igual(round(C.gasto_del_mes(raiz) - antes, 4), F.coste_apify("tiktok", 10),
              "un actor que se pasa de tiempo: lo reservado se queda apuntado")
        antes = C.gasto_del_mes(raiz)
        f = lanza(C.leer, raiz, "tiktok", "camposraros", 10, pagar=True)
        ok(f is not None, "resultados que no se entienden: no hay cuenta")
        igual(round(C.gasto_del_mes(raiz) - antes, 4), F.coste_apify("tiktok", 6),
              "pero los 6 resultados cobrados se apuntan")
        antes = C.gasto_del_mes(raiz)
        C.guardar_claves({"apify_token": "apify_api_malo_000000"})
        lanza(C.leer, raiz, "tiktok", "otra", 10, pagar=True)
        igual(C.gasto_del_mes(raiz), antes, "un token de Apify malo no cobra: la reserva se devuelve")
        C.guardar_claves({"apify_token": TOKEN_APIFY})

        # una clave gratis que no vale no es motivo para pagar
        C.guardar_claves({"youtube_clave": "AIzaMALA0000000000"})
        n = len([v for v in Falso.vistas if v[0] == "POST"])
        f = lanza(C.leer, raiz, "youtube", "pepe", 10, pagar=True)
        ok(f is not None and "Arregla" in str(f) and len([v for v in Falso.vistas if v[0] == "POST"]) == n,
           "una clave de YouTube mala para y lo dice: no pasa a Apify")
        C.guardar_claves({"youtube_clave": CLAVE_YT})

        # dos lecturas a la vez cerca del tope: solo cabe una
        gastado = C.gasto_del_mes(raiz)
        C.guardar_claves({"tope_usd": round(gastado + F.coste_apify("tiktok", 10) * 1.5, 2)})
        salidas = []
        hilos = [threading.Thread(target=lambda u=u: salidas.append(lanza(C.leer, raiz, "tiktok", u, 10, pagar=True)))
                 for u in ("par_uno", "par_dos")]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        igual(sum(1 for x in salidas if x is None), 1, "dos lecturas a la vez cerca del tope: solo pasa una")
        ok(C.gasto_del_mes(raiz) <= C.claves_publicas()["tope_usd"] + 1e-9, "y el tope no se pasa")

        C.guardar_claves({"tope_usd": 0})
        f = lanza(C.leer, raiz, "tiktok", "otra", 10, pagar=True)
        ok(f is not None and "tope" in str(f), "con el tope gastado, no se paga y se dice")
        C.guardar_claves({"tope_usd": 5, "pago": False})
        f = lanza(C.leer, raiz, "tiktok", "otra", 10, pagar=True)
        ok(f is not None and "apagado" in str(f), "con el pago apagado, tampoco")
        C.guardar_claves({"pago": True})
        ok(Falso.caminos and not any(k in c for c in Falso.caminos for k in (CLAVE_YT, TOKEN_META, TOKEN_APIFY)),
           "ninguna clave va en una URL (van en cabeceras)")
        plan = C.plan(raiz, "tiktok", "otra", 30)
        ok(plan["vias"][0]["fuente"] == "apify" and plan["vias"][0]["coste_usd"] == F.coste_apify("tiktok", 30),
           "el plan dice que irá por Apify y cuánto costará")
        ok(plan["queda_usd"] < 5, "y cuánto queda del tope")
        plan = C.plan(raiz, "tiktok", "ana", 10)
        ok(plan["guardada"] and plan["guardada"]["fresca"], "y si ya está leída de hoy")

        lista = C.cuentas(raiz)
        ok({(c["red"], c["usuario"]) for c in lista} >= {("tiktok", "ana"), ("youtube", "ana"), ("instagram", "competencia")},
           "las cuentas leídas, en la lista")
        C.borrar(raiz, "youtube", "ana")
        ok(lanza(C.cuenta, raiz, "youtube", "ana").codigo == 404, "«Olvidar» una cuenta")
    finally:
        os.environ.pop("ESTUDIO_LECTURA_BASES", None)


# ------------------------------------------------------------- 4. Claude

def prueba_claude(bases):
    seccion("4] el análisis y los guiones desde una cuenta")
    raiz = os.path.join(CARPETA, "orden")
    os.environ["ESTUDIO_LECTURA_BASES"] = json.dumps(bases)
    pedidos = []
    P.LLAMAR_CLAUDE = lambda i, para: pedidos.append(i) or (
        "QUÉ LE FUNCIONA\n- preguntas" if "[[TAREA:analisis_cuenta]]" in i
        else f"{P.SEPARADOR}\n" + P._guion_simulado(1, "Como ella", "Voz", "adaptar"))
    try:
        t = C.lanzar_analisis(raiz, "tiktok", "ana", en_hilo=False)
        igual(t["estado"], "listo", "el análisis se lanza y acaba")
        d = C.cuenta(raiz, "tiktok", "ana")
        igual(d["analisis"], "QUÉ LE FUNCIONA\n- preguntas", "y se guarda con la cuenta")
        ok("tiktok 0" in pedidos[-1], "con sus vídeos dentro")
        C.leer(raiz, "tiktok", "ana", 10, forzar=True, pagar=True)
        d = C.cuenta(raiz, "tiktok", "ana")
        ok(d.get("analisis") and d.get("analisis_viejo"), "volver a traerla conserva el análisis, marcado como viejo")
        t = C.lanzar_lectura(raiz, "tiktok", "ana", 10, en_hilo=False)
        igual((t["estado"], t["de_cache"]), ("listo", True), "lanzar una lectura de hoy: de la caché")
        ok(lanza(C.lanzar_analisis, raiz, "tiktok", "nadie") is not None, "analizar una cuenta no leída, no")

        posts = C.posts_de_cuenta(d, 15)
        t = P.lanzar(raiz, "c1", "resultados", {"posts": posts, "cuantos": 2, "modo": "adaptar",
                                                 "ajena": "@ana en TikTok", "analisis": d["analisis"]}, en_hilo=False)
        igual(t["estado"], "listo", "guiones desde la cuenta")
        ultimo = pedidos[-1]
        ok("@ana en TikTok, una cuenta de referencia que NO es mía" in ultimo and "nunca copies" in ultimo,
           "como cuenta ajena: aprender sin copiar")
        ok("LO QUE YA SE ANALIZÓ DE ESA CUENTA" in ultimo and "preguntas" in ultimo, "con su análisis")
        m = [x for x in P.listar(raiz, "c1")["matrices"] if x["id"] == t["matriz"]][0]
        igual((m["origen"]["tipo"], m["origen"]["cuenta"]), ("cuenta", "@ana en TikTok"),
              "la matriz recuerda de qué cuenta salió")
    finally:
        P.LLAMAR_CLAUDE = None
        os.environ.pop("ESTUDIO_LECTURA_BASES", None)

    llamadas = []
    G.EJECUTAR = lambda m, e, cwd, per, vet, mod, av=None: llamadas.append(m) or ("vale", {"session_id": "s"})
    try:
        chat = G.nueva(raiz, "c1")
        v = chat.escribir("¿qué le funciona?", cuenta_texto=C.resumen_para_claude(d), cuenta="@ana (TikTok)", en_hilo=False)
        ok("UNA CUENTA DE REFERENCIA QUE NO ES MÍA" in llamadas[-1] and "CUENTA: @ana en TikTok" in llamadas[-1],
           "el chat recibe la cuenta como referencia")
        igual(v["turnos"][-2]["cuenta"], "@ana (TikTok)", "y el mensaje lo dice")
    finally:
        G.EJECUTAR = None

    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        r2 = os.path.join(CARPETA, "sim")
        os.makedirs(r2)
        d = C.leer(r2, "instagram", "personal_x", 10, pagar=True)
        igual(d["fuente"], "apify", "simulado: una cuenta personal también pasa a Apify")
        d = C.analizar(r2, "instagram", "personal_x")
        ok("QUÉ LE FUNCIONA" in d["analisis"], "simulado: el análisis")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)


# ------------------------------------------------------------ 5. el Studio

def _arrancar(carpeta):
    import requests
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    entorno = dict(os.environ)
    entorno.update({"PYTHONIOENCODING": "utf-8", "ESTUDIO_SIMULAR": "1",
                    "ESTUDIO_SECRETOS": os.path.join(carpeta, "secretos"),
                    "ESTUDIO_AJUSTES": os.path.join(carpeta, "ajustes.json"),
                    "ESTUDIO_PRESETS": os.path.join(carpeta, "presets.json"),
                    "ESTUDIO_BANCO_PRESETS": os.path.join(carpeta, "banco"),
                    "ESTUDIO_RECETAS": os.path.join(carpeta, "recetas.json"),
                    "ESTUDIO_ESTADISTICAS": os.path.join(carpeta, "estadisticas.json"),
                    "ESTUDIO_COSTE_GLOBAL": os.path.join(carpeta, "coste_global.jsonl")})
    os.makedirs(entorno["ESTUDIO_SECRETOS"], exist_ok=True)
    proceso = subprocess.Popen(
        [sys.executable, os.path.join(RAIZ, "app.py"), "--puerto", str(puerto),
         "--proyectos", os.path.join(carpeta, "proyectos")],
        cwd=RAIZ, env=entorno, stdout=open(os.path.join(carpeta, "servidor.log"), "w"),
        stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            with open(os.path.join(carpeta, "servidor.log"), encoding="utf-8", errors="replace") as fh:
                raise RuntimeError("el servidor murió al arrancar:\n" + fh.read()[-3000:])
        try:
            if requests.get(base + "/api/salud", timeout=2).status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el servidor no respondió en 90 s")


def _esperar(s, url, segundos=30):
    limite = time.time() + segundos
    datos = {}
    while time.time() < limite:
        datos = s.get(url, timeout=30).json()
        if datos.get("estado") != "trabajando":
            return datos
        time.sleep(0.3)
    return datos


def prueba_studio():
    import requests
    seccion("5] el Studio por HTTP (simulado)")
    carpeta = os.path.join(CARPETA, "studio")
    os.makedirs(os.path.join(carpeta, "proyectos"))
    proceso, base = _arrancar(carpeta)
    s = requests.Session()
    try:
        r = s.get(base + "/api/parrilla/cuentas").json()
        igual((r["cuentas"], r["conexiones"]["simulado"]), ([], True), "GET /api/parrilla/cuentas")
        r = s.put(base + "/api/parrilla/cuentas/conexiones", json={"apify_token": "apify_api_HTTP_99999"}).json()
        igual(r["conexiones"]["apify"]["cola"], "…9999", "guardar una conexión, sin devolverla entera")
        ok("apify_api_HTTP_99999" not in json.dumps(s.get(base + "/api/parrilla/cuentas").json()),
           "ninguna ruta la devuelve")
        r = s.post(base + "/api/parrilla/cuentas/conexiones/instagram", json={}).json()
        igual(r["conexiones"]["meta"]["ig_id"], "17841400000000000", "«Buscar mi cuenta» (simulado)")
        r = s.post(base + "/api/parrilla/cuentas/plan", json={"texto": "https://www.tiktok.com/@ana"}).json()
        igual((r["red"], r["usuario"], r["vias"][0]["fuente"]), ("tiktok", "ana", "apify"), "el plan de un enlace de TikTok")
        igual(s.post(base + "/api/parrilla/cuentas/plan", json={"texto": "https://x.com/ana"}).status_code, 400,
              "un enlace de otra web, 400")
        r = s.post(base + "/api/parrilla/cuentas/leer", json={"texto": "@ana", "red": "tiktok", "cuantos": 10})
        t = _esperar(s, base + f"/api/parrilla/cuentas/trabajos/{r.json()['id']}")
        ok(t["estado"] == "error" and (t.get("pide_pago") or {}).get("coste_usd"),
           "sin «pagar», el trabajo acaba pidiendo permiso con el precio")
        r = s.post(base + "/api/parrilla/cuentas/leer", json={"texto": "@ana", "red": "tiktok", "cuantos": 10,
                                                             "forzar": "false", "pagar": True})
        igual(r.status_code, 202, "leer una cuenta: 202 y un trabajo")
        t = _esperar(s, base + f"/api/parrilla/cuentas/trabajos/{r.json()['id']}")
        igual(t["estado"], "listo", "y acaba")
        d = s.get(base + "/api/parrilla/cuentas/tiktok/ana").json()
        ok(len(d["videos"]) > 0 and d["fuente"] == "apify", "la cuenta leída")
        igual(s.get(base + "/api/parrilla/cuentas/tiktok/nadie").status_code, 404, "una no leída, 404")
        r = s.post(base + "/api/parrilla/cuentas/tiktok/ana/analizar", json={})
        t = _esperar(s, base + f"/api/parrilla/cuentas/trabajos/{r.json()['id']}")
        ok(t["estado"] == "listo" and s.get(base + "/api/parrilla/cuentas/tiktok/ana").json().get("analisis"),
           "el análisis")
        r = s.post(base + "/api/parrilla/proyectos/_sin/desde-cuenta",
                   json={"red": "tiktok", "usuario": "ana", "cuantos": 2, "modo": "adaptar"})
        igual(r.status_code, 202, "guiones desde la cuenta para un proyecto")
        t = _esperar(s, base + f"/api/parrilla/trabajos/{r.json()['id']}")
        igual((t["estado"], len(t["guiones"])), ("listo", 2), "y van a su Parrilla")
        chid = s.post(base + "/api/parrilla/proyectos/_sin/chats", json={}).json()["id"]
        r = s.post(base + f"/api/parrilla/proyectos/_sin/chats/{chid}/mensajes",
                   data={"texto": "¿qué le funciona?", "cuenta": "tiktok:ana"})
        igual(r.status_code, 202, "un mensaje del chat con la cuenta")
        igual(r.json()["turnos"][-2].get("cuenta"), "@ana (TikTok)", "que el mensaje la lleva")
        igual(s.post(base + f"/api/parrilla/proyectos/_sin/chats/{chid}/mensajes",
                     data={"texto": "x", "cuenta": "tiktok:nadie"}).status_code, 404, "con una cuenta no leída, 404")
        igual(s.delete(base + "/api/parrilla/cuentas/tiktok/ana").status_code, 200, "olvidar la cuenta")
    finally:
        proceso.terminate()
        proceso.wait(timeout=15)


def main():
    print("PRUEBA DE ANALIZAR UNA CUENTA")
    prueba_piezas()
    servidor, bases = arrancar_falso()
    try:
        prueba_fuentes(bases)
        prueba_orden(bases)
        prueba_claude(bases)
    finally:
        servidor.shutdown()
    try:
        import fastapi  # noqa: F401
        import requests  # noqa: F401
        hay_servidor = True
    except ImportError:
        hay_servidor = False
    if hay_servidor:
        prueba_studio()
    else:
        print("\n[5] OMITIDA: falta fastapi en este entorno (en el servidor sí corre)")
    shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"CUENTAS OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

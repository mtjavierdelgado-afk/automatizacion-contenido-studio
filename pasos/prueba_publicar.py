"""Prueba de PUBLICAR: textos por red, el cliente de Upload-Post y los envios.

Sin red, sin claves y sin publicar nada en ninguna red:

  1. las piezas sueltas de `pasos/publicar.py` (encaje de formato, capitulos,
     textos, lo que se manda a cada red, ajustes del proyecto);
  2. el cliente DE VERDAD (`motores/publicar_uploadpost/cliente.py`) contra un
     Upload-Post falso que corre aqui mismo en un hilo: cabecera, multipart en
     streaming, idempotencia, programar con hora de Lima, estados, errores sin
     la clave dentro;
  3. el Studio entero por HTTP con el Upload-Post SIMULADO: ficha, textos (con
     el doble de Claude), perfil y cuentas, enviar ya / programar / esperar tu
     OK, una red que falla y las demas siguen, no repetir sin querer, cancelar,
     a mano, la cola y el calendario, y que un proyecto con clave no se ve.

    python pasos/prueba_publicar.py
"""
import datetime as dt
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

CARPETA = tempfile.mkdtemp(prefix="publicar_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ.pop("UPLOADPOST_API_KEY", None)
os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)
os.environ.pop("ESTUDIO_SIMULAR", None)
# lo que apunta Publicar en la bitacora global no va a la de verdad
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")

import publicar as P  # noqa: E402
from motores.publicar_uploadpost import cliente as UP  # noqa: E402

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


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def seccion(titulo):
    print(f"\n[{titulo}]")


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ------------------------------------------------------------- 1. piezas

INFO = {"pid": "fiesta", "nombre": "Fiesta en casa", "formato": "vertical",
        "duracion_s": 45, "guion": [{"id": "B001", "texto": "Alquila tu consola."}],
        "capitulos_base": [], "mp4_huella": "abc", "montado": True}


def prueba_piezas():
    seccion("1] piezas sueltas")
    igual(P.encaje("youtube", "vertical", 50)["tipo"], "Short", "vertical corto es un Short")
    igual(P.encaje("youtube", "vertical", 400)["nivel"], "aviso",
          "vertical largo en YouTube avisa de que no es Short")
    igual(P.encaje("tiktok", "horizontal", 60)["nivel"], "aviso", "horizontal en TikTok avisa")
    igual(P.encaje("tiktok", "vertical", 700)["nivel"], "error", "más de 10 min en TikTok no se deja")
    igual(P.encaje("instagram", "vertical", 1000)["nivel"], "error", "más de 15 min en Reels no se deja")
    igual(P.encaje("facebook", "vertical", 60)["tipo"], "Reel", "Facebook vertical corto es Reel")
    igual(P.encaje("facebook", "vertical", 200)["tipo"], "vídeo", "y largo, vídeo")

    escenas = [{"t_in": 0.4, "narracion": "hola", "origen": {"bloque": "B001"}},
               {"t_in": 4, "narracion": "sigue", "origen": {"bloque": "B001"}},
               {"t_in": 12, "narracion": "dos", "origen": {"bloque": "B002"}},
               {"t_in": 15, "narracion": "corto", "origen": {"bloque": "B003"}},
               {"t_in": 40, "narracion": "tres", "origen": {"bloque": "B004"}},
               {"t_in": 70, "narracion": "cuatro", "origen": {"bloque": "B005"}}]
    caps = P.capitulos_base(escenas, 100)
    igual([c["t"] for c in caps], [0, 12, 40, 70], "capítulos: uno por bloque, el primero en 0:00")
    ok("corto" in caps[1]["texto"], "y el bloque de menos de 10 s se junta con el anterior")
    igual(P.capitulos_base(escenas[:3], 20), [], "con menos de tres tramos no hay capítulos")

    igual(P._limpiar_hashtags(["#Fiesta", "fiesta", "lima peru", "", "#ñandú"]),
          ["Fiesta", "limaperu", "ñandú"], "hashtags sin #, sin repetidos y sin espacios")
    textos, capitulos = P.normalizar_textos(
        {"tiktok": {"titulo": "no va", "descripcion": "Hola", "cta": "Escríbenos",
                    "hashtags": "a b"},
         "youtube": {"titulo": "x" * 200, "descripcion": "D"},
         "capitulos": ["Uno", "Dos"]},
        ["tiktok", "youtube"], [{"t": 0}, {"t": 30}, {"t": 60}])
    igual(textos["tiktok"]["titulo"], "", "TikTok no lleva título aparte")
    igual(len(textos["youtube"]["titulo"]), 100, "el título de YouTube se corta en 100")
    igual(capitulos, [], "capítulos a medias no valen")

    ajustes = dict(P.AJUSTES_DEFECTO, firma="— EstadoPlay", hashtags="#estadoplay #fiesta")
    tk = P.componer("tiktok", {"descripcion": "Hola", "cta": "Escríbenos",
                                "hashtags": ["fiesta", "lima"]}, ajustes, INFO)
    igual(tk["texto"], "Hola\n\nEscríbenos\n\n— EstadoPlay\n\n#fiesta #lima #estadoplay",
          "el texto de TikTok: texto, CTA, firma y hashtags sin repetir")
    igual(tk["campos"]["tiktok_title"], tk["texto"], "y va en tiktok_title")
    igual(tk["campos"].get("is_aigc"), True, "marcado como IA")
    yt = P.componer("youtube", {"titulo": "Mi <vídeo>", "descripcion": "D <b>",
                                 "hashtags": ["uno"]}, ajustes,
                    dict(INFO, formato="horizontal", duracion_s=300),
                    [{"t": 0, "titulo": "Inicio"}, {"t": 75, "titulo": "Final"}])
    igual(yt["campos"]["youtube_title"], "Mi vídeo", "YouTube sin «<» ni «>» en el título")
    ok("<" not in yt["campos"]["youtube_description"], "ni en la descripción")
    ok("0:00 Inicio\n1:15 Final" in yt["texto"], "con los capítulos en la descripción")
    igual(yt["campos"]["tags[]"], ["uno", "estadoplay", "fiesta"], "los hashtags hacen de etiquetas")
    igual(yt["campos"]["containsSyntheticMedia"], True, "y se declara contenido sintético")
    fb = P.componer("facebook", {"titulo": "T", "descripcion": "D"},
                    dict(ajustes, marcar_ia=False, facebook_pagina="123"), INFO)
    igual(fb["campos"]["facebook_media_type"], "REELS", "Facebook vertical corto va como Reel")
    igual(fb["campos"].get("facebook_page_id"), "123", "con la página del proyecto")
    ok("facebook_is_ai_generated" not in fb["campos"], "sin marcar IA si el proyecto no quiere")
    largo = P.componer("instagram", {"descripcion": "x" * 3000}, ajustes, INFO)
    igual(len(largo["texto"]), 2200, "un texto demasiado largo se corta al límite de la red")
    ok(largo["avisos"], "y se avisa")

    for malo, campo in (({"hora": "25:00"}, "hora"), ({"redes": ["myspace"]}, "redes"),
                        ({"marcar_ia": "si"}, "marcar_ia"), ({"perfil": "a/b"}, "perfil"),
                        ({"privacidad_youtube": "todos"}, "privacidad")):
        try:
            P._validar_ajustes(malo)
            ok(False, f"un ajuste malo ({campo}) se rechaza")
        except P.ErrorPublicar:
            ok(True, f"un ajuste malo ({campo}) se rechaza")
    igual(P._validar_ajustes({"redes": ["youtube", "tiktok"], "cuentas": {"x": 1}}),
          {"redes": ["tiktok", "youtube"]}, "las redes en su orden, y «cuentas» no se escribe desde fuera")
    hora = P.proxima_hora("19:00")
    ok(hora.endswith("T19:00") and P._leer_momento(hora) > P.ahora_lima(),
       "la hora sugerida es la próxima vez que son las 19:00 en Lima")


# ---------------------------------------------- 2. el cliente de verdad

class _FalsoUploadPost(http.server.BaseHTTPRequestHandler):
    vistas = []
    clave = "up_clave_de_prueba_123456"

    def log_message(self, *_a):
        pass

    def _responder(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _ver(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo) if largo else b""
        self.vistas.append({"metodo": self.command, "ruta": self.path,
                            "cabeceras": dict(self.headers), "cuerpo": cuerpo})
        if self.headers.get("Authorization") != f"Apikey {self.clave}":
            self._responder(401, {"success": False,
                                  "message": f"Invalid API key {self.headers.get('Authorization')}"})
            return None
        return cuerpo

    def do_GET(self):
        if self._ver() is None:
            return
        ruta = urllib.parse.urlparse(self.path)
        if ruta.path == "/api/uploadposts/me":
            self._responder(200, {"success": True, "email": "yo@x.com", "plan": "basic"})
        elif ruta.path == "/api/uploadposts/users":
            self._responder(200, {"success": True, "limit": 5, "plan": "basic", "profiles": [
                {"username": "studio_a", "social_accounts": {
                    "tiktok": {"display_name": "A TikTok", "username": "atk",
                               "social_images": "https://img"},
                    "instagram": "", "youtube": None}}]})
        elif ruta.path == "/api/uploadposts/post-analytics/cached":
            # la lectura guardada: dos paginas con cursor (publicar-redes-2)
            q = urllib.parse.parse_qs(ruta.query)
            if q.get("cursor") == ["pag2"]:
                self._responder(200, {"success": True, "source": "snapshot_cache", "posts": [
                    {"post_id": "yt_9", "platform": "youtube", "captured_at": "2026-10-17T15:00:00Z",
                     "post_url": "https://youtube.com/watch?v=9",
                     "metrics": {"views": 900, "likes": 30, "average_view_percentage": 45.3,
                                 "average_view_duration_seconds": 31}}],
                    "has_more": False, "next_cursor": None})
            else:
                self._responder(200, {"success": True, "source": "snapshot_cache", "posts": [
                    {"post_id": "tt_1", "platform": "tiktok", "captured_at": "2026-10-17T14:00:00Z",
                     "post_url": "https://tiktok.com/v/1",
                     "metrics": {"views": 1500, "full_video_watched_rate": 0.184,
                                 "average_time_watched": 7.5}},
                    {"post_id": "x", "platform": "myspace", "metrics": {"views": 1}}],
                    "has_more": True, "next_cursor": "pag2"})
        elif ruta.path == "/api/uploadposts/post-analytics/req_ret":
            self._responder(200, {"success": True, "platforms": {
                "tiktok": {"success": True, "platform_post_id": "tt_1",
                           "post_url": "https://tiktok.com/v/1",
                           "post_metrics": {"views": 1400, "likes": 90, "full_video_watched_rate": 0.21,
                                            "average_time_watched": 8.25, "total_time_watched": 11550,
                                            "retention": [{"second": "1", "percentage": 0.9}]}}}})
        elif ruta.path.startswith("/api/uploadposts/post-analytics/"):
            self._responder(200, {"success": True, "platforms": {
                "youtube": {"success": True, "post_url": "https://youtube.com/watch?v=V",
                            "post_metrics": {"views": 5200, "likes": 120, "comments": 8, "favorites": 3}},
                "tiktok": {"success": True, "post_metrics_error":
                           "TikTok video not found (ID: 7). The token may need to be refreshed."}}})
        elif ruta.path.startswith("/api/analytics/"):
            self._responder(200, {"instagram": {"followers": 47, "reach": 1250, "views": 3400},
                                  "facebook": {"followers": 0, "reach": 0, "impressions": 0}})
        elif ruta.path == "/api/uploadposts/status":
            q = urllib.parse.parse_qs(ruta.query)
            if q.get("job_id"):
                self._responder(200, {"status": "completed", "results": [
                    {"platform": "tiktok", "success": True, "post_url": "https://tiktok.com/v/1"},
                    {"platform": "youtube", "success": False, "message": "quota"}]})
            else:
                self._responder(200, {"status": "processing", "results": [
                    {"platform": "tiktok", "status": "processing"}]})
        else:
            self._responder(404, {"success": False, "message": "no"})

    def do_POST(self):
        cuerpo = self._ver()
        if cuerpo is None:
            return
        if self.path == "/api/uploadposts/users":
            datos = json.loads(cuerpo or b"{}")
            self._responder(201, {"success": True, "profile": {
                "username": datos.get("username"), "social_accounts": {"tiktok": ""}}})
        elif self.path == "/api/uploadposts/users/generate-jwt":
            self._responder(200, {"success": True,
                                  "access_url": "https://app.upload-post.com/connect?token=J",
                                  "duration": "48h"})
        elif self.path == "/api/upload":
            if b'name="user"\r\n\r\ncae' in cuerpo:
                self._responder(524, {"success": False, "message": "A timeout occurred"})
            elif b'name="scheduled_date"' in cuerpo:
                self._responder(202, {"success": True, "job_id": "job_9",
                                      "scheduled_date": "2026-12-01T00:00:00Z"})
            else:
                self._responder(200, {"success": True, "request_id": "req_1",
                                      "message": "Upload initiated"})
        else:
            self._responder(404, {"success": False, "message": "no"})

    def do_DELETE(self):
        if self._ver() is None:
            return
        self._responder(200, {"success": True, "message": "cancelado"})


def prueba_cliente():
    seccion("2] el cliente de Upload-Post contra uno falso")
    puerto = puerto_libre()
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), _FalsoUploadPost)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{puerto}"
    cli = UP.ClienteUploadPost(_FalsoUploadPost.clave, base=base)
    try:
        r = cli.probar()
        igual(r, {"ok": True, "email": "yo@x.com", "plan": "basic"}, "probar lee la cuenta")
        igual(_FalsoUploadPost.vistas[-1]["cabeceras"].get("Authorization"),
              f"Apikey {_FalsoUploadPost.clave}", "la clave va en «Authorization: Apikey …»")
        perfiles = cli.perfiles()["perfiles"]
        igual(perfiles[0]["perfil"], "studio_a", "perfiles: el nombre")
        igual(perfiles[0]["cuentas"]["tiktok"]["nombre"], "A TikTok", "y la cuenta conectada")
        igual(perfiles[0]["cuentas"]["instagram"], None, "una cuenta sin conectar es None («»)")
        igual(perfiles[0]["cuentas"]["youtube"], None, "y también con null")
        igual(cli.crear_perfil("studio_b")["perfil"], "studio_b", "crear un perfil")
        igual(cli.enlace_conectar("studio_b", redes=["tiktok", "myspace"])["url"],
              "https://app.upload-post.com/connect?token=J", "el enlace para conectar")
        igual(json.loads(_FalsoUploadPost.vistas[-1]["cuerpo"])["platforms"], ["tiktok"],
              "con solo las redes que existen")

        mp4 = os.path.join(CARPETA, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(os.urandom(300_000))
        r = cli.publicar("studio_b", ["tiktok", "youtube", "reddit"], mp4,
                         {"tiktok_title": "Hola ñ", "tags[]": ["a", "b"], "is_aigc": True},
                         id_propio="lote123")
        igual(r["modo"], "en_cola", "subir ya: en segundo plano")
        igual(r["request_id"], "req_1", "con su request_id")
        vista = _FalsoUploadPost.vistas[-1]
        cuerpo = vista["cuerpo"]
        igual(vista["cabeceras"].get("Idempotency-Key"), "lote123", "lleva su clave de idempotencia")
        igual(cuerpo.count(b'name="platform[]"'), 2, "una línea platform[] por red, sin las que no existen")
        igual(cuerpo.count(b'name="tags[]"'), 2, "y una por etiqueta")
        ok(b'name="async_upload"\r\n\r\ntrue' in cuerpo, "async_upload=true")
        ok("Hola ñ".encode() in cuerpo, "el texto con su ñ")
        ok(b'name="is_aigc"\r\n\r\ntrue' in cuerpo, "los sí/no van como true")
        with open(mp4, "rb") as fh:
            ok(fh.read() in cuerpo, "el MP4 llega entero (subido en streaming)")
        igual(int(vista["cabeceras"].get("Content-Length")), len(cuerpo),
              "con su Content-Length exacto")

        try:
            cli.publicar("cae", ["tiktok"], mp4, {})
            ok(False, "un 5xx en la subida falla")
        except UP.ErrorUploadPost as fallo:
            ok(fallo.sin_respuesta, "un 5xx en la subida (el 524 de Cloudflare) es «no se sabe», no «falló»")
        r = cli.publicar("studio_b", ["tiktok"], mp4, {}, cuando="2026-12-01T19:00:00")
        igual((r["modo"], r["job_id"]), ("programado", "job_9"), "programar: devuelve el job_id")
        cuerpo = _FalsoUploadPost.vistas[-1]["cuerpo"]
        ok(b'name="timezone"\r\n\r\nAmerica/Lima' in cuerpo, "con la zona de Lima")
        ok(b"async_upload" not in cuerpo, "y sin async_upload")

        e = cli.estado(job_id="job_9")
        igual(e["redes"]["tiktok"], {"estado": "publicado", "url": "https://tiktok.com/v/1", "error": "",
                                     "texto": ""},
              "estado: publicado con su enlace")
        igual(e["redes"]["youtube"]["estado"], "fallido", "y la red que falló, fallida")
        igual(e["redes"]["youtube"]["error"], "quota", "con el motivo")
        igual(cli.estado(request_id="req_1")["redes"]["tiktok"]["estado"], "procesando",
              "un envío a medias está procesando")
        igual(cli.cancelar("job_9"), {"ok": True}, "cancelar")
        igual(_FalsoUploadPost.vistas[-1]["ruta"], "/api/uploadposts/schedule/job_9",
              "con DELETE a la ruta del trabajo")
        m = cli.metricas_post("req_1")
        igual(m["youtube"]["vistas"], 5200, "métricas: las vistas de YouTube")
        igual(m["youtube"]["guardados"], 3, "«favorites» cuenta como guardados")
        igual(m["youtube"]["compartidos"], None, "lo que no viene, None")
        ok(m["tiktok"]["error"].startswith("TikTok video not found"), "y el error de la red que no las da")
        # la retencion y el id del post en la red (publicar-redes-2)
        igual(m["youtube"]["vista_entera"], None, "YouTube no da retención en vivo: None")
        m = cli.metricas_post("req_ret")
        igual(m["tiktok"]["vista_entera"], 0.21, "TikTok: la fracción que lo vio entero")
        igual(m["tiktok"]["tiempo_medio_s"], 8.2, "y el tiempo medio en segundos")
        igual(m["tiktok"]["post_id"], "tt_1", "y el id del post en la red")
        g = cli.metricas_guardadas("studio_a", desde="2026-10-10", hasta="2026-10-17")
        primera = next(v for v in _FalsoUploadPost.vistas if "cached" in v["ruta"])
        ok("user=studio_a" in primera["ruta"] and "limit=200" in primera["ruta"]
           and "since=2026-10-10" in primera["ruta"],
           f"la lectura guardada va con user, limit y since: {primera['ruta']}")
        ok(any("cursor=pag2" in v["ruta"] for v in _FalsoUploadPost.vistas),
           "y sigue el cursor a la página siguiente")
        igual(g["completo"], True, "hasta que no hay más")
        igual(sorted(p["red"] for p in g["posts"]), ["tiktok", "youtube"],
              "solo las redes que el Studio conoce")
        yt = next(p for p in g["posts"] if p["red"] == "youtube")
        igual((yt["vista_entera"], yt["media_vista"]), (None, 0.453),
              "el porcentaje medio de YouTube va aparte (no es «hasta el final») y en fracción")
        igual(yt["tiempo_medio_s"], 31.0, "y su duración media")
        igual((yt["post_id"], yt["al"]), ("yt_9", "2026-10-17T15:00:00Z"), "con su id y su hora")
        g = cli.metricas_guardadas("studio_a", paginas=1)
        igual(g["completo"], False, "con una sola página dice que no está completo")
        igual(UP.ClienteUploadPost._retencion({"full_video_watched_rate": 18.4})["vista_entera"],
              0.184, "una fracción que llega en tanto por cien se entiende")
        igual(UP.ClienteUploadPost._retencion({"full_video_watched_rate": True,
                                                "average_time_watched": "nan"}),
              {"vista_entera": None, "media_vista": None, "tiempo_medio_s": None},
              "lo que no es un número no cuenta")
        igual(UP.ClienteUploadPost._retencion({"average_view_percentage": 135})["media_vista"], 1.35,
              "un Short visto más de una vez (más del 100 %) se guarda, no se tira")
        a = cli.analiticas_perfil("studio_a", ["instagram", "facebook"], pagina_facebook="99")
        igual(a["instagram"]["seguidores"], 47, "los seguidores de la cuenta")
        igual(a["facebook"]["seguidores"], 0, "un cero de verdad se queda en cero")
        ok("page_id=99" in _FalsoUploadPost.vistas[-1]["ruta"], "Facebook con su página")

        malo = UP.ClienteUploadPost("otra_clave_secreta_999", base=base)
        try:
            malo.probar()
            ok(False, "una clave mala falla")
        except UP.ErrorUploadPost as fallo:
            igual(fallo.codigo, 401, "una clave mala falla con 401")
            ok("otra_clave_secreta_999" not in str(fallo), "y el mensaje no lleva la clave")
            ok("no acepta la clave" in str(fallo), f"y lo dice en castellano: {fallo}")
    finally:
        servidor.shutdown()
    try:
        UP.ClienteUploadPost("x" * 20, base=base).probar()
        ok(False, "sin servicio falla")
    except UP.ErrorUploadPost as fallo:
        ok(fallo.sin_respuesta, "sin servicio: «sin respuesta» (una subida así no se reintenta)")
    try:
        UP.ClienteUploadPost("")
        ok(False, "sin clave no hay cliente")
    except UP.ErrorUploadPost:
        ok(True, "sin clave no hay cliente")


# ------------------------------------------------- 3. el Studio por HTTP

def _sembrar_video(raiz, pid, vertical=True, segundos=4):
    """Un vídeo montado de mentira: proyecto, guion y un MP4 de verdad."""
    from nucleo.proyecto import Proyecto, escribir_json
    proyecto = Proyecto.crear(raiz, pid)
    proyecto.config["estilo_light"] = "estilo_x"
    proyecto.config["video_light"] = True
    proyecto.guardar_config()
    guion = proyecto.ruta_paso("guion", 1, crear=True)
    escribir_json(os.path.join(guion, "guion.json"), {"bloques_detalle": [
        {"id": "B001", "texto": "Alquila la consola para tu fiesta en Lima."},
        {"id": "B002", "texto": "Escríbenos y te la llevamos."}]})
    proyecto.fijar_version_activa("guion", 1)
    render = proyecto.ruta_paso("render", 1, crear=True)
    tam = "360x640" if vertical else "640x360"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=blue:s={tam}:d={segundos}", "-pix_fmt", "yuv420p",
                    os.path.join(render, "video.mp4")], check=True)
    proyecto.fijar_version_activa("render", 1)
    return proyecto


def _arrancar(carpeta, entorno_extra):
    import requests
    puerto = puerto_libre()
    entorno = dict(os.environ)
    entorno.update({"PYTHONIOENCODING": "utf-8",
                    "ESTUDIO_SECRETOS": os.path.join(carpeta, "secretos"),
                    "ESTUDIO_AJUSTES": os.path.join(carpeta, "ajustes.json"),
                    "ESTUDIO_PRESETS": os.path.join(carpeta, "presets.json"),
                    "ESTUDIO_BANCO_PRESETS": os.path.join(carpeta, "banco"),
                    "ESTUDIO_RECETAS": os.path.join(carpeta, "recetas.json"),
                    "ESTUDIO_ESTADISTICAS": os.path.join(carpeta, "estadisticas.json"),
                    "ESTUDIO_COSTE_GLOBAL": os.path.join(carpeta, "coste_global.jsonl")})
    entorno.update(entorno_extra)
    os.makedirs(entorno["ESTUDIO_SECRETOS"], exist_ok=True)
    proceso = subprocess.Popen(
        [sys.executable, os.path.join(RAIZ, "app.py"), "--puerto", str(puerto),
         "--proyectos", os.path.join(carpeta, "proyectos")],
        cwd=RAIZ, env=entorno, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace")
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            raise RuntimeError("el servidor murió al arrancar:\n" + proceso.stdout.read())
        try:
            if requests.get(base + "/api/salud", timeout=2).status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el servidor no respondió en 90 s")


def _esperar(sesion, url, condicion, segundos=20):
    limite = time.time() + segundos
    datos = {}
    while time.time() < limite:
        datos = sesion.get(url, timeout=30).json()
        if condicion(datos):
            return datos
        time.sleep(0.3)
    return datos


def prueba_studio():
    import requests
    seccion("5] el Studio por HTTP, con Upload-Post simulado")
    carpeta = os.path.join(CARPETA, "studio")
    raiz = os.path.join(carpeta, "proyectos")
    os.makedirs(raiz)
    _sembrar_video(raiz, "fiesta", vertical=True)
    _sembrar_video(raiz, "largo", vertical=False, segundos=6)
    from nucleo.proyecto import Proyecto
    Proyecto.crear(raiz, "sin montar")
    simulador = os.path.join(carpeta, "uploadpost.json")
    # sin ESTUDIO_SIMULAR primero: sin clave no se puede enviar, se dice antes
    proceso, base = _arrancar(carpeta, {"ESTUDIO_UPLOADPOST_SIMULADO": "",
                                        "ESTUDIO_SIMULAR": ""})
    s = requests.Session()
    try:
        r = s.get(base + "/api/publicar/estado").json()
        igual(r["clave"]["puesta"], False, "sin clave lo dice")
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok"], "modo": "ahora", "confirmado": True})
        igual(r.status_code, 409, "sin perfil (ni clave) no se envía")
    finally:
        proceso.terminate()
        proceso.wait(timeout=15)

    with open(os.path.join(carpeta, "secretos", ".env"), "w", encoding="utf-8") as fh:
        fh.write("UPLOADPOST_API_KEY=up_secreta_del_env_987654\n")
    proceso, base = _arrancar(carpeta, {"ESTUDIO_UPLOADPOST_SIMULADO": "",
                                        "ESTUDIO_SIMULAR": ""})
    try:
        r = s.get(base + "/api/publicar/estado").json()
        igual((r["clave"]["puesta"], r["clave"]["origen"]), (True, "env"),
              "con UPLOADPOST_API_KEY en el .env de secretos la ve")
        ok("up_secreta_del_env_987654" not in json.dumps(r), "y la clave no baja entera")
        igual(r["clave"]["cola"], "…7654", "solo los cuatro últimos")
        c = s.get(base + "/api/claves").json()
        igual((c.get("uploadpost") or {}).get("puesta"), True,
              "Configuración la enseña como puesta (la del .env cuenta)")
        ok("up_secreta_del_env_987654" not in json.dumps(c), "sin bajar entera")
        s.put(base + "/api/claves", json={"jamendo": {"clave": "jamendo_de_prueba_1234"}})
        with open(os.path.join(carpeta, "secretos", ".env"), encoding="utf-8") as fh:
            env = fh.read()
        ok("UPLOADPOST_API_KEY=up_secreta_del_env_987654" in env,
           "guardar otra clave no borra la de Upload-Post del .env")
        r = s.put(base + "/api/claves", json={"uploadpost": {"clave": "up_desde_configuracion_5555"}})
        igual((r.json().get("uploadpost") or {}).get("cola"), "…5555", "se cambia desde Configuración")
        r = s.get(base + "/api/publicar/estado").json()
        igual(r["clave"]["origen"], "almacen", "y queda en el almacén de claves")
        with open(os.path.join(carpeta, "secretos", ".env"), encoding="utf-8") as fh:
            ok("UPLOADPOST_API_KEY=up_desde_configuracion_5555" in fh.read(), "espejada en el .env")
        s.put(base + "/api/claves", json={"uploadpost": {"clave": ""}})
        r = s.get(base + "/api/publicar/estado").json()
        igual(r["clave"]["puesta"], False, "«Quitar» la quita de verdad (también del .env)")
    finally:
        proceso.terminate()
        proceso.wait(timeout=15)

    proceso, base = _arrancar(carpeta, {"ESTUDIO_UPLOADPOST_SIMULADO": simulador,
                                        "ESTUDIO_SIMULAR": "1",
                                        "ESTUDIO_PUBLICAR_RESPIRO": "0"})
    try:
        f = s.get(base + "/api/publicar/videos/fiesta").json()
        igual(f["montado"], True, "la ficha sabe que el vídeo está montado")
        igual(f["formato"], "vertical", "y su formato, medido en el MP4")
        ok(3.5 <= f["duracion_s"] <= 4.5, f"y su duración real: {f['duracion_s']}")
        igual(f["encaje"]["youtube"]["tipo"], "Short", "en YouTube sale como Short")
        igual(f["redes"], list(P.REDES_CLASICAS), "de fábrica, las cuatro redes de siempre")
        ok(f["mp4"].endswith("video.mp4"), "con la ruta del MP4 para descargarlo")
        igual(s.get(base + "/api/publicar/videos/sin_montar").json()["montado"], False,
              "un vídeo sin montar lo dice")
        igual(s.get(base + "/api/publicar/videos/noexiste").status_code, 404, "uno que no existe, 404")
        igual(s.get(base + "/api/publicar/videos/_sistema").status_code, 404,
              "y las carpetas del sistema no son vídeos")

        r = s.post(base + "/api/publicar/videos/sin_montar/textos", json={"redes": ["tiktok"]})
        igual(r.status_code, 409, "sin montar no se escriben textos")
        r = s.post(base + "/api/publicar/videos/fiesta/textos", json={"redes": ["tiktok", "youtube"]})
        igual(r.status_code, 202, "Claude escribe los textos (en segundo plano)")
        r2 = s.post(base + "/api/publicar/videos/fiesta/textos", json={"redes": ["tiktok"]})
        igual(r2.status_code, 409, "dos a la vez, no")
        f = _esperar(s, base + "/api/publicar/videos/fiesta", lambda d: not d["escribiendo"])
        ok(f["textos"]["tiktok"]["descripcion"].startswith("[TikTok]"), "los textos de TikTok")
        ok(f["textos"]["youtube"]["titulo"], "y el título de YouTube")
        igual(f["desactualizada"], False, "recién escritos, al día")
        ok("#prueba" in f["compuestos"]["tiktok"]["texto"], "lo que sale en la red, con sus hashtags")

        r = s.put(base + "/api/publicar/videos/fiesta", json={
            "redes": ["tiktok", "instagram"],
            "textos": {"instagram": {"descripcion": "Reel a mano", "hashtags": "#a #b"}}})
        f = r.json()
        igual(f["redes"], ["tiktok", "instagram"], "elegir las redes")
        igual(f["textos"]["instagram"]["hashtags"], ["a", "b"], "editar el texto a mano")
        igual(f["editado"], True, "y queda como editado")
        igual(s.put(base + "/api/publicar/videos/fiesta", json={"redes": ["myspace"]}).status_code,
              400, "una red que no existe se rechaza")

        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok"], "modo": "ahora"})
        igual(r.status_code, 400, "sin confirmar no sale nada")
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok"], "modo": "ahora", "confirmado": True})
        igual(r.status_code, 409, "sin perfil de Upload-Post tampoco")

        p = s.get(base + "/api/publicar/proyectos").json()
        igual(p["proyectos"][0]["id"], P.SIN_PROYECTO, "los vídeos sin proyecto tienen sus ajustes")
        r = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/perfil", json={})
        igual(r.status_code, 200, "crear el perfil en Upload-Post")
        perfil = r.json()["ajustes"]["perfil"]
        ok(perfil.startswith("studio_"), f"con el nombre sugerido: {perfil}")
        r = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/perfil", json={})
        igual(r.status_code, 200, "si ya existe allí, solo se apunta")
        igual(r.json().get("como"), "adoptado", "y dice que lo adoptó")
        # lo escrito en el campo es lo que se manda (16-10: iba el cuerpo vacío)
        r = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/perfil",
                   json={"perfil": perfil.upper(), "crear": False})
        igual((r.status_code, r.json()["ajustes"]["perfil"]), (200, perfil),
              "«Usar este perfil» con otras mayúsculas apunta el de Upload-Post")
        r = s.get(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/perfiles")
        igual(r.status_code, 200, "la lista de perfiles de la cuenta, para el desplegable")
        ok(any(x["perfil"] == perfil and x["propio"] for x in r.json()["perfiles"]),
           "con el de este proyecto marcado")
        r = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/conectar",
                   json={"redes": ["tiktok", "instagram", "youtube"], "volver_a": "javascript:x"})
        ok(r.json().get("url", "").startswith("https://app.upload-post.com/connect"),
           "el enlace para que el cliente conecte sus cuentas")
        a = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/cuentas").json()
        igual(a["existe"], True, "las cuentas del perfil")
        ok(a["ajustes"]["cuentas"]["tiktok"] and a["ajustes"]["cuentas"]["facebook"] is None,
           "TikTok conectado y Facebook no")
        r = s.put(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}",
                  json={"firma": "— EstadoPlay", "hashtags": "#estadoplay", "hora": "20:30"})
        igual(r.json()["ajustes"]["hora"], "20:30", "guardar lo fijo del proyecto")
        igual(s.put(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}", json={"hora": "8"}).status_code,
              400, "una hora mal escrita se rechaza")
        igual(s.put(base + "/api/publicar/proyectos/cl_noexiste", json={}).status_code, 404,
              "un proyecto que no existe, 404")
        f = s.get(base + "/api/publicar/videos/fiesta").json()
        ok(f["compuestos"]["tiktok"]["texto"].endswith("#prueba #tiktok #estadoplay"),
           "la firma y los hashtags fijos entran en el texto")
        ok(f["hora_sugerida"].endswith("T20:30"), "y la hora de programar es la del proyecto")

        # --- la portada: el fotograma, guardarlo, una imagen subida
        r = s.get(base + "/api/publicar/videos/fiesta/fotograma?ms=1500")
        igual((r.status_code, r.headers.get("content-type")), (200, "image/jpeg"),
              "el fotograma del segundo 1,5 para la vista de la portada")
        ok(r.content[:2] == b"\xff\xd8", "es un JPEG de verdad")
        igual(s.get(base + "/api/publicar/videos/fiesta/fotograma?ms=999000").status_code, 400,
              "un momento fuera del vídeo se dice")
        f = s.put(base + "/api/publicar/videos/fiesta", json={"portada": {"ms": 1500}}).json()
        igual(f["portada"]["ms"], 1500, "«Usar este fotograma» se guarda en la ficha")
        igual(s.put(base + "/api/publicar/videos/fiesta", json={"portada": {"ms": -3}}).status_code,
              400, "un fotograma negativo no")
        png = os.path.join(carpeta, "portada.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=1080x1920",
                        "-frames:v", "1", png], check=True)
        with open(png, "rb") as fh:
            r = s.post(base + "/api/publicar/videos/fiesta/portada", files={"portada": ("p.png", fh, "image/png")})
        igual(r.status_code, 200, "subir una imagen de portada")
        ok(bool(r.json()["portada"]["imagen"]), "y queda en la ficha")
        r = s.get(base + "/api/publicar/videos/fiesta/portada.jpg")
        ok(r.status_code == 200 and r.content[:2] == b"\xff\xd8" and len(r.content) <= 2 * 1024 * 1024,
           "pasada a JPEG de menos de 2 MB (la miniatura de YouTube)")
        r = s.post(base + "/api/publicar/videos/fiesta/portada",
                   files={"portada": ("p.gif", b"GIF89a", "image/gif")})
        igual(r.status_code, 400, "un GIF no vale como portada")
        f = s.put(base + "/api/publicar/videos/fiesta",
                  json={"portada": {"quitar_imagen": True}}).json()
        igual((f["portada"]["imagen"], f["portada"]["ms"]), ("", 1500),
              "«Quitar la imagen» vuelve al fotograma elegido")

        # --- ya
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok", "instagram", "facebook"], "modo": "ahora",
                         "confirmado": True})
        igual(r.status_code, 409, "Facebook sin cuenta conectada: no sale y se dice por qué")
        ok("Facebook no tiene cuenta" in r.json().get("error", ""), r.json().get("error", ""))
        s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/conectar", json={"redes": ["facebook"]})
        s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/cuentas")
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok", "instagram", "facebook"], "modo": "ahora",
                         "confirmado": True})
        igual(r.status_code, 409, "conectada, pero sin texto de Facebook: tampoco, y se dice por qué")
        ok("falta el texto de Facebook" in r.json().get("error", ""), r.json().get("error", ""))
        with open(simulador, encoding="utf-8") as fh:
            sim = json.load(fh)
        sim["fallar"] = {"instagram": "el vídeo no cumple las normas"}
        with open(simulador, "w", encoding="utf-8") as fh:
            json.dump(sim, fh)
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok", "instagram"], "modo": "ahora", "confirmado": True})
        igual(r.status_code, 202, "publicar ya en TikTok e Instagram")
        igual([e["estado"] for e in r.json()["envios"]], ["enviando", "enviando"],
              "un envío por red, «enviando»")
        f = _esperar(s, base + "/api/publicar/videos/fiesta",
                     lambda d: all(e["estado"] != "enviando" for e in d["envios"]))
        igual(sorted(e["estado"] for e in f["envios"]), ["publicando", "publicando"],
              "subido: «publicando»")
        with open(simulador, encoding="utf-8") as fh:
            sim = json.load(fh)
        subida = sim["subidas"][-1]
        igual(subida["redes"], ["tiktok", "instagram"], "UNA subida con las dos redes")
        ok(subida["campos"].get("instagram_title", "").startswith("Reel a mano"),
           "con el texto editado a mano")
        ok(subida["bytes"] > 1000, "y el MP4 de verdad")
        igual((subida["campos"].get("thumb_offset"), subida["campos"].get("cover_timestamp")),
              ("1500", 1500), "la portada: el fotograma elegido en Instagram y TikTok")
        igual(subida["campos"].get("title"), subida["campos"].get("tiktok_title"),
              "y el «title» general es el texto COMPLETO de la primera red (19-10: salía solo la primera línea)")
        f_env = s.get(base + "/api/publicar/videos/fiesta").json()
        env_ig = next(e for e in f_env["envios"] if e["red"] == "instagram")
        igual((env_ig.get("enviado") or {}).get("instagram_title"), subida["campos"]["instagram_title"],
              "la ficha guarda lo que se mandó a cada red, tal cual")
        ok("tiktok_title" not in (env_ig.get("enviado") or {}), "y solo lo de esa red (más el «title» común)")
        for _ in range(4):
            s.post(base + "/api/publicar/refrescar")
            f = s.get(base + "/api/publicar/videos/fiesta").json()
            if all(e["estado"] in ("publicado", "fallido") for e in f["envios"]):
                break
        por_red = {e["red"]: e for e in f["envios"]}
        igual(por_red["tiktok"]["estado"], "publicado", "TikTok publicado")
        ok(por_red["tiktok"]["url"].startswith("https://"), "con el enlace al post")
        igual(por_red["instagram"]["estado"], "fallido", "Instagram falló…")
        igual(por_red["instagram"]["error"], "el vídeo no cumple las normas", "…con su motivo")

        # --- métricas por HTTP
        r = s.post(base + "/api/publicar/videos/fiesta/metricas", json={"forzar": True})
        igual(r.status_code, 200, "pedir las cifras de lo publicado")
        igual(r.json().get("consultados"), 1, "una consulta para el envío publicado")
        ok(any(e.get("metricas") for e in r.json()["ficha"]["envios"]),
           "y la ficha vuelve con las cifras")
        res = s.get(base + "/api/publicar/resultados", params={"proyecto": P.SIN_PROYECTO}).json()
        igual(res["total"]["posts"], 1, "el resumen del proyecto cuenta lo publicado")
        r = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/metricas", json={})
        igual(r.status_code, 200, "actualizar todo el proyecto")
        res = s.get(base + "/api/publicar/resultados", params={"proyecto": P.SIN_PROYECTO}).json()
        ok(res["seguidores"].get("tiktok", {}).get("seguidores"), "y trae los seguidores de las cuentas")
        igual(s.get(base + "/api/publicar/resultados", params={"proyecto": "cl_no"}).status_code, 404,
              "un proyecto que no existe, 404")
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["tiktok"], "modo": "ahora", "confirmado": True})
        igual(r.status_code, 409, "el mismo MP4 otra vez en TikTok pide confirmarlo")
        r = s.post(base + "/api/publicar/videos/fiesta/enviar",
                   json={"redes": ["instagram"], "modo": "ahora", "confirmado": True})
        igual(r.status_code, 202, "pero reintentar Instagram (que falló) se deja")

        # --- programar
        ayer = (P.ahora_lima() - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        r = s.post(base + "/api/publicar/videos/largo/enviar", json={
            "redes": ["youtube"], "modo": "programar", "cuando": ayer, "confirmado": True})
        igual(r.status_code, 400, "programar en el pasado, no")
        r = s.put(base + "/api/publicar/videos/largo",
                  json={"textos": {"youtube": {"titulo": "Largo", "descripcion": "D"}}})
        manana = (P.ahora_lima() + dt.timedelta(days=1)).replace(hour=19, minute=0)
        r = s.post(base + "/api/publicar/videos/largo/enviar", json={
            "redes": ["youtube"], "modo": "programar",
            "cuando": manana.strftime("%Y-%m-%dT%H:%M"), "confirmado": True})
        igual(r.status_code, 202, "programar YouTube para mañana a las 19:00")
        f = _esperar(s, base + "/api/publicar/videos/largo",
                     lambda d: d["envios"] and d["envios"][0]["estado"] != "enviando")
        igual(f["envios"][0]["estado"], "programado", "queda «programado»")
        igual(f["envios"][0]["cuando"], manana.strftime("%Y-%m-%dT%H:%M:00"), "a su hora de Lima")
        with open(simulador, encoding="utf-8") as fh:
            ultima = json.load(fh)["subidas"][-1]
        igual((ultima["cuando"], ultima["zona"]), (manana.strftime("%Y-%m-%dT%H:%M:00"), "America/Lima"),
              "y así se le pide a Upload-Post")
        c = s.get(base + "/api/publicar/cola", params={"desde": P.ahora_lima().strftime("%Y-%m-%d")}).json()
        ok(any(e["pid"] == "largo" and e["estado"] == "programado" for e in c["envios"]),
           "la cola de la semana lo enseña")
        igual(sorted(v["pid"] for v in c["listos"]), ["fiesta", "largo"],
              "los vídeos listos para publicar (no el que no está montado)")
        igual(c["listos"][0]["envios"].get("tiktok") if c["listos"][0]["pid"] == "fiesta"
              else next(v for v in c["listos"] if v["pid"] == "fiesta")["envios"].get("tiktok"),
              "publicado", "cada vídeo con el estado de cada red")
        igual(len(c["dias"]), 7, "una semana de días en el calendario")
        eid = f["envios"][0]["id"]
        r = s.post(base + f"/api/publicar/videos/largo/envios/{eid}/cancelar")
        igual(r.status_code, 200, "cancelar lo programado")
        f = s.get(base + "/api/publicar/videos/largo").json()
        igual(f["envios"][0]["estado"], "cancelado", "queda cancelado")
        igual(s.post(base + f"/api/publicar/videos/largo/envios/{eid}/cancelar").status_code, 409,
              "y no se cancela dos veces")

        # --- espera tu OK
        r = s.post(base + "/api/publicar/videos/largo/enviar", json={
            "redes": ["youtube"], "modo": "pendiente",
            "cuando": manana.strftime("%Y-%m-%dT%H:%M")})
        igual(r.status_code, 202, "dejar un envío esperando tu OK (sin confirmar)")
        pendiente = r.json()["envios"][0]
        igual(pendiente["estado"], "espera_ok", "en «espera tu OK»")
        c = s.get(base + "/api/publicar/cola").json()
        ok(any(e["id"] == pendiente["id"] for e in c["esperan_ok"]), "la cola lo pone aparte")
        ok(all("estilo" in v and "estilo_nombre" in v for v in c["listos"]),
           "cada vídeo listo trae su estilo, para filtrar por estilo")
        igual(s.get(base + "/api/publicar/cola", params={"dias": 42}).json()["dias"].__len__(), 42,
              "la vista de mes pide seis semanas")
        r = s.post(base + f"/api/publicar/videos/largo/envios/{pendiente['id']}/confirmar", json={})
        igual(r.status_code, 400, "confirmar pide confirmado: true")
        r = s.post(base + f"/api/publicar/videos/largo/envios/{pendiente['id']}/confirmar",
                   json={"confirmado": True})
        igual(r.status_code, 202, "y con tu OK sale")
        f = _esperar(s, base + "/api/publicar/videos/largo",
                     lambda d: all(e["estado"] != "enviando" for e in d["envios"]))
        estados = sorted(e["estado"] for e in f["envios"])
        igual(estados, ["cancelado", "cancelado", "programado"],
              "el que esperaba queda resuelto y el nuevo programado")

        # --- a mano
        r = s.post(base + "/api/publicar/videos/largo/a-mano",
                   json={"red": "facebook", "url": "https://facebook.com/p/1"})
        igual(r.json()["envio"]["estado"], "a_mano", "«lo he subido yo» queda en el historial")
        igual(s.post(base + "/api/publicar/videos/largo/a-mano",
                     json={"red": "facebook", "url": "ftp://x"}).status_code, 400,
              "con un enlace de verdad o ninguno")

        # --- desactualizada
        f = s.get(base + "/api/publicar/videos/fiesta").json()
        igual(f["desactualizada"], False, "antes de cambiar nada, al día")
        from nucleo.proyecto import escribir_json
        guion = os.path.join(raiz, "fiesta", "pasos", "guion", "v1", "guion.json")
        escribir_json(guion, {"bloques_detalle": [{"id": "B001", "texto": "Otro guion distinto."}]})
        f = s.get(base + "/api/publicar/videos/fiesta").json()
        igual(f["desactualizada"], True, "si cambia el guion, la ficha queda desactualizada")

        # --- las firmas no se tocan
        ok(not os.path.exists(os.path.join(raiz, "fiesta", "publicar")),
           "nada de publicar se escribe dentro de la carpeta del vídeo")
        ok(os.path.isfile(os.path.join(raiz, "_sistema", "publicar", "videos", "fiesta.json")),
           "vive en _sistema/publicar")

        # --- SEO por HTTP
        p = s.get(base + "/api/publicar/proyectos").json()
        ok(("24", "Entretenimiento") in [tuple(x) for x in p["seo_opciones"]["categorias"]],
           "las categorías de YouTube, con su nombre en castellano")
        igual(s.put(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}", json={"ig_ubicacion": "Lima"}).status_code,
              400, "una ubicación de Instagram que no es un número se rechaza por HTTP")
        s.put(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}", json={"palabra_clave": "consolas en Lima"})
        r = s.post(base + "/api/publicar/videos/fiesta/optimizar", json={"redes": ["tiktok"]})
        igual(r.status_code, 202, "«Optimizar SEO con Claude» se lanza")
        f = _esperar(s, base + "/api/publicar/videos/fiesta",
                     lambda d: not d["seo"]["trabajando"].get("optimizar"))
        ok("tiktok" in f["seo"]["propuesta"].get("redes", {}), "y deja su propuesta en la ficha")
        ok(f["seo"]["notas"]["tiktok"]["puntos"], "la ficha trae la nota SEO de cada red")
        igual(s.post(base + "/api/publicar/videos/fiesta/ganchos", json={"red": "tiktok"}).status_code, 202,
              "«Dame 3 ganchos» se lanza")
        r = s.post(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/palabras")
        igual(r.status_code, 202, "«Proponer palabras clave» se lanza")

        # --- proyecto con clave
        r = s.post(base + "/api/clientes", json={"nombre": "Cliente secreto"})
        cid = r.json()["cliente"]["id"]
        r = s.post(base + f"/api/publicar/proyectos/{cid}/perfil", json={"perfil": perfil})
        igual(r.status_code, 409, "un proyecto no puede adoptar el perfil de otro")
        igual(s.put(base + f"/api/publicar/proyectos/{cid}", json={"perfil": perfil}).status_code, 409,
              "ni escribiéndolo a mano")
        igual(s.post(base + f"/api/publicar/proyectos/{cid}/perfil",
                     json={"perfil": "studio_secreto"}).status_code, 200, "el proyecto secreto con su perfil")
        s.put(base + f"/api/clientes/{cid}", json={"clave": "1234"})
        s.put(base + "/api/clientes/videos/fiesta", json={"cliente": cid})
        lista = s.get(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/perfiles").json()
        ok(all(x["perfil"] != "studio_secreto" for x in lista["perfiles"]) and lista["ocultos"] >= 1,
           "el desplegable no enseña el perfil de un proyecto con clave cerrado (solo cuántos hay)")
        ok(all(not isinstance(x.get("de_otro"), str) for x in lista["perfiles"]),
           "ni el id de otro proyecto")
        igual(s.get(base + "/api/publicar/videos/fiesta/fotograma?ms=500").status_code, 404,
              "ni su fotograma")
        igual(s.get(base + "/api/publicar/videos/fiesta").status_code, 404,
              "un vídeo de un proyecto con clave no se ve sin abrirlo")
        c = s.get(base + "/api/publicar/cola").json()
        ok(all(v["pid"] != "fiesta" for v in c["listos"]), "ni en la cola")
        ok(all(p["id"] != cid for p in s.get(base + "/api/publicar/proyectos").json()["proyectos"]),
           "ni sus ajustes")
        igual(s.get(base + "/api/publicar/resultados", params={"proyecto": cid}).status_code, 404,
              "ni sus resultados")
        res = s.get(base + "/api/publicar/resultados", params={"proyecto": P.SIN_PROYECTO}).json()
        ok(all(v["pid"] != "fiesta" for v in res["videos"]),
           "y sus vídeos no salen en el resumen de otro proyecto")
        pase = s.post(base + f"/api/clientes/{cid}/abrir", json={"clave": "1234"}).json()["pase"]
        cab = {"X-Estudio-Abiertos": f"{cid}.{pase}"}
        igual(s.get(base + "/api/publicar/videos/fiesta", headers=cab).status_code, 200,
              "con el proyecto abierto, sí")
        igual(s.get(base + "/api/publicar/videos/fiesta/fotograma?ms=500", headers=cab).status_code, 200,
              "y su fotograma, con el pase (la pantalla lo pide con fetch, no con <img src>)")
        lista = s.get(base + f"/api/publicar/proyectos/{P.SIN_PROYECTO}/perfiles", headers=cab).json()
        fila = next((x for x in lista["perfiles"] if x["perfil"] == "studio_secreto"), {})
        ok(fila.get("de_otro") is True and fila.get("de_otro_nombre") == "Cliente secreto",
           "abierto, sale marcado como de su proyecto")
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()


def prueba_envios_sueltos():
    seccion("3] envíos: reintentar sin duplicar, no reconocidos, perfiles")
    raiz = os.path.join(CARPETA, "sueltos")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_sueltos.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_x")
        cli.enlace_conectar("studio_x", ["tiktok"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        info = dict(INFO, pid="suelto", mp4=mp4, mp4_huella="h1")
        ajustes = dict(P.AJUSTES_DEFECTO, perfil="studio_x")
        P.guardar_ficha(raiz, "suelto", {"textos": {"tiktok": {"descripcion": "Hola"}}})
        nuevos = P.enviar(raiz, info, ajustes, {"redes": ["tiktok"], "modo": "ahora",
                                                "confirmado": True}, en_hilo=False)
        lote = nuevos[0]["lote"]
        # como si la respuesta se hubiera perdido: el envío queda en «comprobar»
        P._actualizar_lote(raiz, "suelto", lote, lambda e: e.update(estado="comprobar"))
        with open(simulador, encoding="utf-8") as fh:
            subidas_antes = len(json.load(fh)["subidas"])
        P.reintentar(raiz, info, ajustes, nuevos[0]["id"], en_hilo=False)
        with open(simulador, encoding="utf-8") as fh:
            subidas = len(json.load(fh)["subidas"])
        igual(subidas, subidas_antes, "reintentar con la misma clave NO sube el vídeo otra vez")
        igual(P._leer_video(raiz, "suelto")["envios"][0]["estado"], "publicando",
              "y el envío vuelve a seguirse")
        try:
            P.reintentar(raiz, info, ajustes, nuevos[0]["id"], en_hilo=False)
            ok(False, "solo se reintenta lo que está en «comprobar»")
        except P.ErrorPublicar:
            ok(True, "solo se reintenta lo que está en «comprobar»")
        try:
            P.enviar(raiz, dict(info, mp4_huella="h2"), ajustes,
                     {"redes": ["tiktok"], "modo": "ahora", "confirmado": True}, en_hilo=False)
            ok(False, "otro montaje del mismo vídeo en la misma red también pide confirmarlo")
        except P.ErrorPublicar as fallo:
            ok("montaje anterior" in str(fallo),
               f"otro montaje del mismo vídeo en la misma red también pide confirmarlo: {fallo}")

        # un envío que Upload-Post no conoce acaba «fallido» (no se queda colgado)
        P.RESPIRO_CONSULTA_S = 0
        hace_una_hora = (P.ahora_lima() - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        datos = P._leer_video(raiz, "suelto")
        datos["envios"].append({"id": "perdido1", "red": "instagram", "lote": "nunca_llego",
                                "estado": "comprobar", "modo": "ahora", "cuando": hace_una_hora,
                                "creado": hace_una_hora, "mp4_huella": "h1"})
        P._escribir(P._ruta_video(raiz, "suelto"), datos)
        for _ in range(P.VECES_NO_LO_CONOCE):
            P.refrescar(raiz)
        perdido = next(e for e in P._leer_video(raiz, "suelto")["envios"] if e["id"] == "perdido1")
        igual(perdido["estado"], "fallido", "un envío que Upload-Post no conoce acaba «fallido»")
        datos = P._leer_video(raiz, "suelto")
        datos["envios"].append({"id": "perdido2", "red": "youtube", "lote": "programado_perdido",
                                "estado": "comprobar", "modo": "programado", "cuando": hace_una_hora,
                                "creado": hace_una_hora, "mp4_huella": "h1"})
        P._escribir(P._ruta_video(raiz, "suelto"), datos)
        for _ in range(P.VECES_NO_LO_CONOCE + 1):
            P.refrescar(raiz)
        perdido = next(e for e in P._leer_video(raiz, "suelto")["envios"] if e["id"] == "perdido2")
        igual(perdido["estado"], "comprobar",
              "pero uno programado se queda en «comprobar»: puede seguir programado allí")
        c = P.cola(raiz, [{"pid": "suelto", "nombre": "Suelto", "montado": True}],
                   desde=(P.ahora_lima() + dt.timedelta(days=30)).strftime("%Y-%m-%d"))
        ok(any(e["id"] == "perdido1" for e in c["fallidos"]),
           "lo que falló sale en «Te necesitan» aunque sea de otra semana")
        P.cancelar(raiz, "suelto", "perdido1")
        c = P.cola(raiz, [{"pid": "suelto", "nombre": "Suelto", "montado": True}])
        ok(not any(e["id"] == "perdido1" for e in c["fallidos"]), "y se puede quitar de la lista")

        # un perfil es un cliente
        P.guardar_ajustes(raiz, "cl_a", {"perfil": "studio_a"})
        try:
            P.guardar_ajustes(raiz, "cl_b", {"perfil": "STUDIO_A"})
            ok(False, "dos proyectos no comparten perfil")
        except P.ErrorPublicar:
            ok(True, "dos proyectos no comparten perfil de Upload-Post")
        P.recordar_cuentas(raiz, "cl_a", {"tiktok": {"nombre": "A"}})
        a = P.guardar_ajustes(raiz, "cl_a", {"perfil": "studio_a2"})
        igual((a["cuentas"], a["cuentas_vistas"]), ({}, ""),
              "cambiar de perfil olvida las cuentas del anterior")
        P.recordar_cuentas(raiz, "cl_a", {"tiktok": {"nombre": "A", "reconectar": True}})
        try:
            P.enviar(raiz, dict(info, pid="otro"), P.ajustes_de(raiz, "cl_a"),
                     {"redes": ["tiktok"], "modo": "ahora", "confirmado": True}, en_hilo=False)
            ok(False, "una cuenta que pide reconectarse no cuenta como conectada")
        except P.ErrorPublicar as fallo:
            ok("no tiene cuenta" in str(fallo), "una cuenta que pide reconectarse no cuenta como conectada")
        sin_aviso = P.componer("youtube", {"titulo": "T", "descripcion": "D"}, P.AJUSTES_DEFECTO, INFO)
        ok("notifySubscribers" not in sin_aviso["campos"],
           "avisar a los suscriptores (lo de fábrica) no manda ningún campo")
        con = P.componer("youtube", {"titulo": "T", "descripcion": "D"},
                         dict(P.AJUSTES_DEFECTO, avisar_youtube=False), INFO)
        igual(con["campos"].get("notifySubscribers"), False, "no avisar sí lo manda")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_metricas():
    seccion("4] métricas: las cifras de lo publicado y el resumen por proyecto")
    raiz = os.path.join(CARPETA, "metricas")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_metricas.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_m")
        cli.enlace_conectar("studio_m", ["tiktok", "youtube"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        info = dict(INFO, pid="medido", mp4=mp4, mp4_huella="h1")
        ajustes = dict(P.AJUSTES_DEFECTO, perfil="studio_m")
        P.guardar_ficha(raiz, "medido", {"textos": {"tiktok": {"descripcion": "T"},
                                                    "youtube": {"titulo": "Y", "descripcion": "Y"}}})
        P.enviar(raiz, info, ajustes, {"redes": ["tiktok", "youtube"], "modo": "ahora",
                                       "confirmado": True}, en_hilo=False)
        r = P.actualizar_metricas(raiz, ["medido"])
        igual(r["consultados"], 0, "lo que aún no está publicado no se mide")
        P.RESPIRO_CONSULTA_S = 0
        for _ in range(3):
            P.refrescar(raiz)
        estados = sorted(e["estado"] for e in P._leer_video(raiz, "medido")["envios"])
        igual(estados, ["publicado", "publicado"], "publicado en las dos redes")
        r = P.actualizar_metricas(raiz, ["medido"])
        # desde `publicar-partir-subida` (19-10) YouTube va en SU subida cuando
        # va con otras redes: son dos envíos, así que dos consultas
        igual((r["consultados"], r["actualizados"]), (2, 2),
              "UNA consulta por subida: YouTube va en la suya, así que dos")
        envios = {e["red"]: e for e in P._leer_video(raiz, "medido")["envios"]}
        ok(envios["youtube"]["metricas"]["vistas"] > 0, "YouTube trae sus vistas")
        igual(envios["youtube"]["metricas"]["guardados"], None,
              "lo que la red no da se queda en None (no es cero)")
        igual(envios["tiktok"]["metricas"]["vistas"], None, "TikTok aún sin cifras la primera vez")
        ok(envios["tiktok"]["metricas"]["error"], "y lo dice")
        r = P.actualizar_metricas(raiz, ["medido"])
        igual(r["consultados"], 0, "lo mirado hace nada no se vuelve a pedir (respiro)")
        vistas_antes = envios["youtube"]["metricas"]["vistas"]
        r = P.actualizar_metricas(raiz, ["medido"], forzar=True)
        envios = {e["red"]: e for e in P._leer_video(raiz, "medido")["envios"]}
        ok(envios["tiktok"]["metricas"]["vistas"], "forzado, TikTok ya trae las suyas")
        ok(envios["youtube"]["metricas"]["vistas"] > vistas_antes, "y las de YouTube crecen")
        ficha = P.ficha(raiz, info, ajustes)
        ok(all(e.get("metricas") for e in ficha["envios"]), "la ficha enseña las cifras de cada envío")
        P.marcar_a_mano(raiz, info, "facebook", "")
        res = P.resultados(raiz, [{"pid": "medido", "nombre": "Medido", "cliente": ""}], "")
        igual(res["total"]["posts"], 3, "el resumen cuenta lo publicado (también a mano)")
        igual(res["total"]["vistas"], envios["tiktok"]["metricas"]["vistas"]
              + envios["youtube"]["metricas"]["vistas"], "y suma las vistas")
        igual(res["sin_cifras"], 1, "la subida a mano no tiene cifras y se cuenta aparte")
        igual(res["videos"][0]["pid"], "medido", "los vídeos, de más a menos vistos")
        res = P.resultados(raiz, [{"pid": "medido", "nombre": "Medido", "cliente": "cl_otro"}], "")
        igual(res["total"]["posts"], 0, "lo de otro proyecto no entra en el resumen")
        P.guardar_ajustes(raiz, "", {"perfil": "studio_m"})
        P.recordar_cuentas(raiz, "", {"tiktok": {"nombre": "t"}, "youtube": {"nombre": "y"},
                                      "instagram": None, "facebook": None})
        a = P.actualizar_seguidores(raiz, "")
        ok(a["seguidores"]["tiktok"]["seguidores"] > 0, "los seguidores de cada cuenta conectada")
        ok("instagram" not in a["seguidores"], "solo de las conectadas")
        # un envío con request_id propio de Upload-Post se pregunta por ESE id
        datos = P._leer_video(raiz, "medido")
        igual(sorted(P._lotes_publicados(raiz, ["medido"])),
              sorted({P._id_de_envio(e) for e in datos["envios"] if e.get("lote")}),
              "las cifras se piden con el id que devolvió Upload-Post")
        # dos a la vez: la segunda no gasta consultas
        P._LOCK_METRICAS.acquire()
        try:
            igual(P.actualizar_metricas(raiz, ["medido"], forzar=True).get("ocupado"), True,
                  "dos «Actualizar» a la vez: el segundo espera")
        finally:
            P._LOCK_METRICAS.release()
        # el resumen: dos envíos a la misma red se suman también en el vídeo
        datos["envios"].append(dict(next(e for e in datos["envios"] if e["red"] == "youtube"),
                                    id="otro_yt", lote="otro_lote"))
        P._escribir(P._ruta_video(raiz, "medido"), datos)
        res = P.resultados(raiz, [{"pid": "medido", "nombre": "Medido", "cliente": ""}], "")
        v = res["videos"][0]
        igual(v["redes"]["youtube"]["vistas"] + v["redes"]["tiktok"]["vistas"], v["vistas"],
              "el detalle por red de un vídeo cuadra con su suma")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_metricas_auto():
    seccion("4c] cifras automáticas: frecuencia, coste antes de confirmar, apagadas de fábrica")
    import publicar_auto as A
    raiz = os.path.join(CARPETA, "auto")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_auto.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    espacio, A.ESPACIO_S = A.ESPACIO_S, 0
    try:
        c0 = A.leer(raiz)
        igual(c0["frecuencia"], "apagada", "apagadas de fábrica")
        igual(c0["proxima"], "", "apagadas no tienen próxima vuelta")
        ok(not os.path.exists(A._ruta(raiz)), "leer no escribe nada (regla 1)")
        igual(A.coste(raiz)["consultas_vuelta"], 0, "sin nada publicado no gasta")
        ok("no se gasta nada" in A.coste(raiz)["texto"], "apagadas: lo dice")
        for malo in ({"frecuencia": "cada rato"}, {"posts": 7}, {"hora": "25:00"}):
            try:
                A.guardar(raiz, malo)
                ok(False, f"rechaza {malo}")
            except P.ErrorPublicar:
                ok(True, f"rechaza {malo}")
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_a")
        cli.enlace_conectar("studio_a", ["tiktok", "youtube"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        ajustes = dict(P.AJUSTES_DEFECTO, perfil="studio_a")
        P.RESPIRO_CONSULTA_S = 0
        for i, pid in enumerate(("auto_a", "auto_b", "auto_c")):
            info = dict(INFO, pid=pid, mp4=mp4, mp4_huella=f"h{i}")
            P.guardar_ficha(raiz, pid, {"textos": {"tiktok": {"descripcion": "T"}}})
            P.enviar(raiz, info, ajustes, {"redes": ["tiktok"], "modo": "ahora",
                                           "confirmado": True}, en_hilo=False)
            for _ in range(3):
                P.refrescar(raiz)
            datos = P._leer_video(raiz, pid)
            for e in datos["envios"]:
                e["cuando"] = f"2026-10-1{i}T10:00:00"     # auto_c, el más nuevo
            P._escribir(P._ruta_video(raiz, pid), datos)
        P.guardar_ajustes(raiz, "", {"perfil": "studio_a"})
        P.recordar_cuentas(raiz, "", {"tiktok": {"nombre": "t"}, "youtube": {"nombre": "y"},
                                      "instagram": None, "facebook": None})
        c = A.coste(raiz, {"frecuencia": "diaria", "posts": 10})
        igual((c["publicados"], c["en_vivo"], c["perfiles"]), (3, 3, 1),
              "el coste cuenta lo publicado y los proyectos con cuentas")
        igual(c["consultas_vuelta"], 3, "una consulta del cupo por envío (los seguidores no gastan cupo)")
        igual(c["consultas_dia"], 3, "diaria: una vuelta al día")
        igual(A.coste(raiz, {"frecuencia": "6h", "posts": 10})["consultas_dia"], 12,
              "cada 6 horas: cuatro vueltas")
        igual(c["dinero"], 0, "sin coste en dinero")
        ok("0 $" in c["texto"] and "100 consultas" in c["texto"], "y el texto lo explica con el cupo")
        ok("no gastan cupo" in c["texto"], "y dice que los seguidores no gastan cupo")
        ok(not os.path.exists(A._ruta(raiz)), "calcular el coste no guarda nada")
        g = A.guardar(raiz, {"frecuencia": "diaria", "hora": "04:00", "posts": 10})
        igual(g["frecuencia"], "diaria", "se guarda la frecuencia")
        ok(g["activada_al"] and g["proxima"], "y se calcula la próxima vuelta")
        ok(not A.toca(raiz), "recién encendida no corre ya: espera a su hora")
        manana = P._leer_momento(g["proxima"]) + dt.timedelta(minutes=1)
        ok(A.toca(raiz, manana), "a su hora, toca")
        # una vuelta: solo los últimos N
        r = A.correr(raiz, "prueba")
        igual(r["consultados"], 3, "la vuelta pide los tres envíos")
        ok(r["fin"] and not r["errores"], f"y termina sin avisos ({r.get('errores')})")
        igual(r["seguidores"], 1, "y los seguidores del proyecto")
        ok(all(e.get("metricas", {}).get("al") for pid in ("auto_a", "auto_b", "auto_c")
               for e in P._leer_video(raiz, pid)["envios"]), "las cifras quedan en cada envío")
        leida = A.leer(raiz)
        igual(leida["ultima"]["motivo"], "prueba", "la última vuelta queda apuntada")
        igual(len(leida["historial"]), 1, "y en el historial")
        ok(P._leer_momento(leida["proxima"]) > P._leer_momento(leida["ultima"]["empezo"]),
           "la próxima es después de la última")
        # con posts=10 pero respiro: no repite lo recién mirado
        r = A.correr(raiz, "otra")
        igual(r["consultados"], 0, "lo recién mirado no se vuelve a pedir")
        # solo los últimos N: con 1, solo el más nuevo
        for pid in ("auto_a", "auto_b", "auto_c"):
            datos = P._leer_video(raiz, pid)
            for e in datos["envios"]:
                e["metricas"] = {}
            P._escribir(P._ruta_video(raiz, pid), datos)
        lotes = A._publicados(raiz)
        nuevo = lotes[0][1]
        ok(any(e.get("lote") == nuevo or e.get("request_id") == nuevo
               for e in P._leer_video(raiz, "auto_c")["envios"]), "el más nuevo va primero")
        A.POSTS = A.POSTS + (1,)
        A.guardar(raiz, {"posts": 1})
        r = A.correr(raiz, "uno")
        igual(r["consultados"], 1, "con «los últimos 1», una sola consulta")
        ok(P._leer_video(raiz, "auto_c")["envios"][0].get("metricas", {}).get("al"),
           "y es la del post más nuevo")
        ok(not P._leer_video(raiz, "auto_a")["envios"][0].get("metricas", {}).get("al"),
           "el viejo se queda para otra")
        A.POSTS = A.POSTS[:-1]
        # una vuelta a medias (el servicio se reinició) no bloquea nada
        datos = A._leer(raiz)
        datos["ultima"] = {"empezo": P._iso_lima(), "motivo": "programada"}
        P._escribir(A._ruta(raiz), datos)
        leida = A.leer(raiz)
        ok(not leida["corriendo"] and leida["ultima"].get("cortada"),
           "una vuelta sin terminar y sin nadie haciéndola: cortada, no «en marcha»")
        historial_antes = len(leida["historial"])
        A.correr(raiz, "tras reinicio")
        leida = A.leer(raiz)
        ok(any(x.get("cortada") for x in leida["historial"]) and
           len(leida["historial"]) == historial_antes + 2, "y la cortada pasa al historial marcada")
        # en marcha en este proceso
        A._LOCK.acquire()
        try:
            ok(A.leer(raiz)["corriendo"], "con una vuelta en marcha, lo dice")
            try:
                A.correr_ya(raiz)
                ok(False, "«Pedirlas ahora» con una vuelta en marcha: 409")
            except P.ErrorPublicar as fallo:
                igual(fallo.codigo, 409, "«Pedirlas ahora» con una vuelta en marcha: 409")
            igual(A.correr(raiz).get("ocupado"), True, "y la programada tampoco la pisa")
        finally:
            A._LOCK.release()
        # en marcha en OTRO proceso (dos servicios con la misma carpeta)
        if A.fcntl is not None:
            import fcntl
            fh = open(A._ruta_cerrojo(raiz), "a+")
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                ok(A.en_marcha(raiz), "la de otro proceso también cuenta")
                igual(A.correr(raiz).get("ocupado"), True, "y no se hace dos veces")
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
                fh.close()
        # apagarlas a mitad: la programada se para antes de gastar
        for pid in ("auto_a", "auto_b", "auto_c"):
            datos = P._leer_video(raiz, pid)
            for e in datos["envios"]:
                e["metricas"] = {}
            P._escribir(P._ruta_video(raiz, pid), datos)
        A.guardar(raiz, {"frecuencia": "apagada"})
        r = A.correr(raiz, "programada")
        igual(r["consultados"], 0, "apagadas mientras corre: la programada no gasta más")
        ok(any("apagaron" in A._texto_aviso(e) for e in r["errores"]), "y lo dice")
        # la manual sí corre aunque estén apagadas; la programada de justo
        # después no repite lo que pidió la manual (respiro de media vuelta)
        respiro, P.RESPIRO_METRICAS_S = P.RESPIRO_METRICAS_S, 0
        try:
            A.guardar(raiz, {"posts": 10})
            r = A.correr(raiz, "a mano")
            igual(r["consultados"], 3, "«Pedirlas ahora» corre con ellas apagadas")
            A.guardar(raiz, {"frecuencia": "diaria"})
            r = A.correr(raiz, "programada")
            igual(r["consultados"], 0, "la programada justo después no repite lo que pidió la manual")
        finally:
            P.RESPIRO_METRICAS_S = respiro
        # lo que no puede ver quien pregunta no sale
        datos = A._leer(raiz)
        datos["ultima"]["errores"] = [{"texto": "seguidores de cl_secreto: algo", "proyecto": "cl_secreto"},
                                      "Upload-Post: el perfil studio_a no responde"]
        P._escribir(A._ruta(raiz), datos)
        tapada = A.leer(raiz, ocultar={"cl_secreto", ""})
        textos = [A._texto_aviso(e) for e in tapada["ultima"]["errores"]]
        ok(not any("cl_secreto" in t for t in textos), "el aviso de un proyecto cerrado no sale")
        ok(textos and "studio_a" not in textos[0] and "proyecto con clave" in textos[0],
           f"y su perfil se tapa en los demás ({textos})")
        # apagarlas
        A.guardar(raiz, {"frecuencia": "apagada"})
        ok(not A.toca(raiz, P.ahora_lima() + dt.timedelta(days=30)), "apagadas no corren nunca")
        # el reloj: no arranca con ESTUDIO_METRICAS_AUTO=0
        os.environ["ESTUDIO_METRICAS_AUTO"] = "0"
        igual(A.arrancar(lambda: raiz), None, "con ESTUDIO_METRICAS_AUTO=0 el reloj no arranca")
        os.environ.pop("ESTUDIO_METRICAS_AUTO", None)
        ok(not any(k in json.dumps(A.leer(raiz)) for k in ("api_key", "Apikey")),
           "nada de la clave en lo que se enseña")
    finally:
        A.ESPACIO_S = espacio
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_redes_nuevas():
    seccion("4d] las redes nuevas: a la vista por proyecto, campos, texto alternativo y Google Business")
    import publicar_redes as RD
    raiz = os.path.join(CARPETA, "redes_nuevas")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_redes.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        a = P.ajustes_de(raiz, "cl_r")
        igual(a["redes_visibles"], list(P.REDES_CLASICAS), "un proyecto nuevo enseña las cuatro de siempre")
        igual(P.redes_visibles(a), list(P.REDES_CLASICAS), "y nada más")
        a = P.guardar_ajustes(raiz, "cl_r", {"redes_visibles": ["tiktok", "linkedin", "pinterest",
                                                                "google_business", "x"]})
        igual(a["redes"], ["tiktok"], "quitar una red de la vista la quita de las marcadas de fábrica")
        a = P.guardar_ajustes(raiz, "cl_r", {"redes": ["tiktok", "threads"]})
        ok("threads" in a["redes_visibles"], "marcar una de fábrica la pone a la vista")
        datos = {"redes": ["bluesky"], "redes_puestas": True, "envios": [{"red": "discord"}]}
        vis = P.redes_visibles(a, datos)
        ok("bluesky" in vis and "discord" in vis, "una red marcada en el vídeo o con envío no desaparece")
        igual(vis, [r for r in P.REDES if r in vis], "en el orden de la pantalla")
        try:
            P.guardar_ajustes(raiz, "cl_r", {"redes_visibles": []})
            ok(False, "sin ninguna red a la vista no se deja")
        except P.ErrorPublicar:
            ok(True, "sin ninguna red a la vista no se deja")
        try:
            P.guardar_ajustes(raiz, "cl_r", {"redes_visibles": ["reddit"]})
            ok(False, "Reddit no se deja poner")
        except P.ErrorPublicar:
            ok(True, "Reddit no se deja poner")
        # campos de cada red
        info = dict(INFO, pid="redes1", nombre="El vídeo")
        aj = dict(P.AJUSTES_DEFECTO, perfil="studio_r", pinterest_tablero="123",
                  linkedin_visibilidad="CONNECTIONS", gbp_cta="BOOK", gbp_cta_url="https://x.pe")
        t = {"descripcion": "Hola mundo", "titulo": "Título LinkedIn", "alt": "Una persona  juega."}
        c = P.componer("linkedin", t, aj, info, [], {})["campos"]
        igual((c.get("linkedin_title"), c.get("linkedin_visibility")), ("Título LinkedIn", "CONNECTIONS"),
              "LinkedIn: título y quién lo ve")
        ok(c.get("linkedin_description", "").startswith("Hola mundo"), "y su texto")
        c = P.componer("pinterest", t, aj, info, [], {})["campos"]
        igual((c.get("pinterest_board_id"), c.get("pinterest_alt_text")), ("123", "Una persona juega."),
              "Pinterest: tablero y texto alternativo limpio")
        c = P.componer("x", dict(t, descripcion="ver https://a.pe"), aj, info, [], {})
        ok(any("enlaces" in x for x in c["avisos"]), "X avisa de que quita los enlaces")
        c = P.componer("google_business", t, aj, info, [], {})["campos"]
        igual((c.get("gbp_cta_type"), c.get("gbp_cta_url")), ("BOOK", "https://x.pe"),
              "Google Business: botón con su enlace")
        ok("linkedin_title" not in P.componer("tiktok", t, aj, info, [], {})["campos"],
           "lo de una red no se cuela en otra")
        igual(RD.falta("pinterest", dict(aj, pinterest_tablero="")) != "", True,
              "Pinterest sin tablero: falta")
        igual(P.encaje("google_business", "vertical", 45)["nivel"], "error",
              "Google Business no acepta más de 30 s")
        # ficha: lo que la pantalla necesita
        ok(P.LIMITES["x"] == 280 and P.LIMITES["bluesky"] == 300, "los límites de X y Bluesky")
        # el envío: Google Business en su propia subida, y Pinterest sin tablero no sale
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_r")
        cli.enlace_conectar("studio_r", ["linkedin", "google_business", "pinterest", "discord"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        info = dict(info, mp4=mp4, mp4_huella="hr", duracion_s=20, formato="vertical")
        P.guardar_ficha(raiz, "redes1", {"textos": {r: {"descripcion": f"Texto {r}", "alt": "Se ve algo"}
                                                     for r in ("linkedin", "google_business",
                                                               "pinterest", "discord")}})
        try:
            P.enviar(raiz, info, dict(aj, pinterest_tablero=""),
                     {"redes": ["pinterest"], "modo": "ahora", "confirmado": True}, en_hilo=False)
            ok(False, "Pinterest sin tablero no se envía")
        except P.ErrorPublicar as fallo:
            ok("tablero" in str(fallo), "Pinterest sin tablero no se envía, y dice por qué")
        P.enviar(raiz, info, aj, {"redes": ["linkedin", "google_business", "discord"], "modo": "ahora",
                                  "confirmado": True}, en_hilo=False)
        subidas = json.load(open(simulador))["subidas"]
        igual(len(subidas), 2, "Google Business va en su propia subida")
        gbp = next(x for x in subidas if "google_business" in x["redes"])
        otra = next(x for x in subidas if "google_business" not in x["redes"])
        igual(gbp["redes"], ["google_business"], "sola")
        ok(str(gbp["campos"].get("title", "")).startswith("Texto google_business"),
           "con su texto en el «title» común")
        igual(sorted(otra["redes"]), ["discord", "linkedin"], "las otras, juntas")
        ok(otra["campos"].get("discord_alt_text") == "Se ve algo", "Discord lleva su texto alternativo")
        # cifras: un envío que solo fue a Discord no gasta consultas
        for _ in range(3):
            P.refrescar(raiz)
        lotes = P._lotes_publicados(raiz, ["redes1"])
        redes_medidas = sorted({e["red"] for envs in lotes.values() for _p, e in envs})
        igual(redes_medidas, ["linkedin"], "Discord y Google Business no se preguntan por cifras por post")
        P.guardar_ajustes(raiz, "cl_r", {"perfil": "studio_r"})
        P.recordar_cuentas(raiz, "cl_r", {r: {"nombre": r} for r in
                                          ("linkedin", "google_business", "discord")})
        igual([t["id"] for t in P.tableros_pinterest(raiz, "cl_r")["tableros"]], ["1001", "1002"],
              "los tableros de Pinterest del perfil")
        seg = P.actualizar_seguidores(raiz, "cl_r")["seguidores"]
        ok("discord" not in seg, "Discord no da seguidores: no se pregunta")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_informe():
    seccion("4e] palabras y ganchos, horarios por red e informe del mes")
    import publicar_informe as I
    raiz = os.path.join(CARPETA, "informe")
    os.makedirs(raiz)
    ahora = P.ahora_lima()
    lunes = (ahora - dt.timedelta(days=ahora.weekday() + 7)).replace(hour=19, minute=10, second=0)

    def envio(red, cuando, vistas, palabra="", linea="", me_gusta=None):
        return {"id": f"e{red}{cuando.strftime('%m%d%H')}{vistas}", "red": red, "estado": "publicado",
                "lote": "l", "cuando": P._iso_lima(cuando), "palabra": palabra,
                "primera_linea": linea,
                "metricas": {"vistas": vistas, "me_gusta": me_gusta, "al": P._iso_lima()}}
    envios = []
    # TikTok: los lunes a las 19 h van el triple que el resto
    for i in range(4):
        envios.append(envio("tiktok", lunes - dt.timedelta(days=7 * i), 3000, "fiesta infantil",
                            "¿Tu hijo cumple años?", me_gusta=300))
    for i in range(4):
        envios.append(envio("tiktok", lunes - dt.timedelta(days=7 * i - 2, hours=10), 1000,
                            "decoración", "Mira esta decoración", me_gusta=20))
    envios.append(envio("instagram", lunes, 500, "fiesta infantil", "Otra cosa"))
    P._escribir(P._ruta_video(raiz, "inf1"), {"envios": envios, "textos": {}, "redes": []})
    videos = [{"pid": "inf1", "nombre": "Fiesta", "cliente": ""}]
    pg = I.palabras_y_ganchos(raiz, videos, "", dias=60)
    igual([p["palabra"] for p in pg["palabras"]][:2], ["fiesta infantil", "decoración"],
          "la palabra que mejor fue, primero (por la mediana)")
    fi = pg["palabras"][0]
    igual((fi["posts"], fi["mediana"]), (5, 3000), "con sus publicaciones y su mediana")
    ok(abs(fi["interaccion"] - 0.1) < 0.01, f"y su interacción ({fi['interaccion']})")
    igual(pg["ganchos"][0]["gancho"], "¿Tu hijo cumple años?", "el gancho con más vistas, primero")
    igual(pg["ganchos"][0]["veces"], 4, "la misma primera línea cuenta una vez (salió 4 veces)")
    igual(len({g["gancho"] for g in pg["ganchos"]}), len(pg["ganchos"]), "sin ganchos repetidos")
    hor = I.horarios(raiz, videos, "")
    tt = hor["redes"]["tiktok"]
    ok(tt["propios"], "TikTok tiene datos propios (8 publicaciones)")
    igual((tt["mejores"][0]["dia"], tt["mejores"][0]["franja"]), (0, "18–21 h"),
          "el mejor hueco de TikTok: lunes de 18 a 21 h")
    igual(tt["mejores"][0]["hora"], "19:00", "y la hora que se propone")
    prox = P._leer_momento(tt["mejores"][0]["proxima"])
    ok(prox > ahora and prox.weekday() == 0 and prox.hour == 19, "«Usar» lleva al próximo lunes a las 19:00")
    ok(all(m["indice"] > 1 for m in tt["mejores"]), "solo huecos por encima de lo normal")
    ig = hor["redes"]["instagram"]
    ok(not ig["propios"] and ig["faltan"] == 5, "Instagram con una sola: no se inventa nada y dice cuántas faltan")
    ok(ig["general"]["texto"] and P._leer_momento(ig["general"]["proxima"]) > ahora,
       "y da el punto de partida general")
    # informe del mes
    mes = lunes.strftime("%Y-%m")
    inf = I.informe_mensual(raiz, videos, "", mes=mes, nombre="Fiestas Suyu")
    del_mes = [e for e in envios if e["cuando"].startswith(mes)]
    igual(inf["total"]["posts"], len(del_mes), "el informe cuenta lo publicado ese mes")
    igual(inf["total"]["vistas"], sum(e["metricas"]["vistas"] for e in del_mes), "y suma sus vistas")
    ok(inf["mejores"][0]["metricas"]["vistas"] == 3000, "lo mejor del mes, primero")
    ok("Fiestas Suyu" in inf["resumen"] and inf["nombre_mes"] in inf["resumen"], "el resumen para copiar")
    ok("undefined" not in inf["resumen"] and "None" not in inf["resumen"], "sin huecos raros en el resumen")
    ok(mes in inf["meses"], "y el mes sale en la lista para elegir")
    # el mes en curso, frente a los MISMOS días del anterior
    hoy_mes = ahora.strftime("%Y-%m")
    ini_mes = ahora.replace(day=1, hour=0, minute=0, second=0)
    antes_ini = (ini_mes - dt.timedelta(days=1)).replace(day=1)
    tarde = antes_ini + (ahora - ini_mes) + dt.timedelta(hours=2)    # después del mismo tramo
    temprano = antes_ini + dt.timedelta(hours=1)
    P._escribir(P._ruta_video(raiz, "inf2"), {"envios": [
        envio("youtube", temprano, 100), envio("youtube", tarde, 5000)] if tarde.month == antes_ini.month
        else [envio("youtube", temprano, 100)], "textos": {}, "redes": []})
    inf = I.informe_mensual(raiz, [{"pid": "inf2", "nombre": "B", "cliente": ""}], "", mes=hoy_mes, nombre="B")
    ok(inf["en_curso"], "el mes de hoy sale como en curso")
    igual(inf["anterior"]["posts"], 1, "y se compara con el mismo tramo del mes anterior, no con el entero")
    vacio = I.informe_mensual(raiz, videos, "", mes="2020-01", nombre="X")
    igual(vacio["total"]["posts"], 0, "un mes sin nada: cero, sin fallar")
    try:
        I.informe_mensual(raiz, videos, "", mes="octubre")
        ok(False, "un mes mal escrito: error claro")
    except P.ErrorPublicar:
        ok(True, "un mes mal escrito: error claro")
    otro = I.palabras_y_ganchos(raiz, [dict(videos[0], cliente="cl_otro")], "", dias=60)
    igual(otro["palabras"], [], "lo de otro proyecto no entra")


def prueba_titulo_completo():
    seccion("4f] el «title» general lleva el texto completo (19-10: los posts salían solo con la primera línea)")
    raiz = os.path.join(CARPETA, "titulo")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_titulo.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_t")
        cli.enlace_conectar("studio_t", ["tiktok", "instagram", "youtube", "facebook", "google_business"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        ajustes = dict(P.AJUSTES_DEFECTO, perfil="studio_t", firma="EstadoPlay", hashtags="#lima")
        largo = ("¿Tu fiesta necesita algo distinto? 🎮\n\nLlevamos la consola, los mandos y "
                 "los juegos a tu casa, en cualquier distrito.\n\nTe lo dejamos funcionando.")
        textos = {"instagram": {"descripcion": largo, "cta": "Escríbenos", "hashtags": ["fiestas"]},
                  "tiktok": {"descripcion": "TikTok: " + largo, "hashtags": ["consolas"]},
                  "youtube": {"titulo": "Consolas para tu fiesta", "descripcion": largo}}

        def subir(pid, redes):
            info = dict(INFO, pid=pid, mp4=mp4, mp4_huella=pid)
            P.guardar_ficha(raiz, pid, {"textos": textos})
            P.enviar(raiz, info, ajustes, {"redes": redes, "modo": "ahora", "confirmado": True},
                     en_hilo=False)
            with open(simulador, encoding="utf-8") as fh:
                return json.load(fh)["subidas"][-1]["campos"], P._leer_video(raiz, pid)

        c, datos = subir("t_ig", ["instagram"])
        igual(c["title"], c["instagram_title"], "solo Instagram: «title» = el texto completo de Instagram")
        ok("\n" in c["title"] and "#fiestas" in c["title"] and "EstadoPlay" in c["title"]
           and "Escríbenos" in c["title"], "con los saltos de línea, la llamada, la firma y los hashtags")
        ok(len(c["title"]) > 100, f"y sin cortar a 100 ({len(c['title'])} caracteres)")
        env = datos["envios"][0]
        igual(env["enviado"]["instagram_title"], c["instagram_title"], "el envío guarda lo que se mandó")
        igual(env["enviado"]["title"], c["title"], "también el «title» común")
        ok(not any("key" in k.lower() or "apikey" in str(v).lower() for k, v in env["enviado"].items()),
           "y nada de la clave")
        c, _d = subir("t_igtt", ["instagram", "tiktok"])
        with open(simulador, encoding="utf-8") as fh:
            primera = json.load(fh)["subidas"][-1]["redes"][0]
        igual(c["title"], c[f"{primera}_title"],
              f"Instagram + TikTok: el texto completo de la primera red de la subida ({primera})")
        ok(c["tiktok_title"].startswith("TikTok: "), "y cada red con el suyo")
        # INSTAGRAM + YOUTUBE: dos subidas (19-10, tarde). En una sola, el «title»
        # común era el título de YouTube y Instagram podía salir solo con él.
        with open(simulador, encoding="utf-8") as fh:
            antes = len(json.load(fh)["subidas"])
        _c, datos = subir("t_yt", ["instagram", "youtube"])
        with open(simulador, encoding="utf-8") as fh:
            nuevas = json.load(fh)["subidas"][antes:]
        igual(len(nuevas), 2, "Instagram + YouTube: dos subidas a Upload-Post")
        yt = next((s for s in nuevas if "youtube" in s["redes"]), {})
        ig = next((s for s in nuevas if "instagram" in s["redes"]), {})
        igual(yt.get("redes"), ["youtube"], "YouTube va sola")
        igual(ig.get("redes"), ["instagram"], "Instagram va sola")
        # (el vídeo es vertical de 45 s: un Short, y desde el 20-10 lleva «#Shorts»)
        igual(yt["campos"]["title"], "Consolas para tu fiesta #Shorts",
              "con YouTube, «title» sigue siendo su título")
        igual(yt["campos"]["youtube_title"], "Consolas para tu fiesta #Shorts", "y su campo propio igual")
        igual(ig["campos"]["title"], ig["campos"]["instagram_title"],
              "y la de Instagram lleva su texto completo en «title», no el título de YouTube")
        ok("instagram_title" not in yt["campos"] and "youtube_title" not in ig["campos"],
           "lo de una red no va en la subida de la otra")
        lotes = {e["red"]: e["lote"] for e in datos["envios"]}
        ok(lotes["instagram"] != lotes["youtube"], "cada una con su lote (Reintentar va por su lado)")
        # YouTube + Facebook, sin otras: juntas (las dos tienen título propio)
        with open(simulador, encoding="utf-8") as fh:
            antes = len(json.load(fh)["subidas"])
        P.guardar_ficha(raiz, "t_ytfb", {"textos": dict(textos, facebook={
            "titulo": "Fiestas con consolas", "descripcion": largo})})
        P.enviar(raiz, dict(INFO, pid="t_ytfb", mp4=mp4, mp4_huella="t_ytfb"), ajustes,
                 {"redes": ["youtube", "facebook"], "modo": "ahora", "confirmado": True},
                 en_hilo=False)
        with open(simulador, encoding="utf-8") as fh:
            nuevas = json.load(fh)["subidas"][antes:]
        igual(len(nuevas), 1, "YouTube + Facebook solas: una subida (las dos llevan su título)")
        # Google Business + YouTube + Instagram: tres subidas, cada una con su «title»
        with open(simulador, encoding="utf-8") as fh:
            antes = len(json.load(fh)["subidas"])
        P.guardar_ficha(raiz, "t_tres", {"textos": dict(textos, google_business={
            "descripcion": "Consolas para tu fiesta en Lima. Escríbenos."})})
        P.enviar(raiz, dict(INFO, pid="t_tres", mp4=mp4, mp4_huella="t_tres", duracion_s=20),
                 ajustes, {"redes": ["google_business", "youtube", "instagram"], "modo": "ahora",
                           "confirmado": True}, en_hilo=False)
        with open(simulador, encoding="utf-8") as fh:
            nuevas = json.load(fh)["subidas"][antes:]
        igual(sorted(tuple(s_["redes"]) for s_ in nuevas),
              [("google_business",), ("instagram",), ("youtube",)],
              "Google Business + YouTube + Instagram: tres subidas, cada red en la suya")
        ig = next(s_ for s_ in nuevas if s_["redes"] == ["instagram"])
        igual(ig["campos"]["title"], ig["campos"]["instagram_title"],
              "y la de Instagram sigue con su texto completo")
        lotes = {e["red"]: e["lote"] for e in P._leer_video(raiz, "t_tres")["envios"]}
        igual(len(set(lotes.values())), 3, "tres lotes distintos")
        # lo que devuelve la red, comparado con lo mandado
        e = {"red": "instagram", "enviado": {"instagram_title": "x" * 300}}
        P.comparar_publicado(e, "x" * 120)
        ok("recortó" in e.get("recortado", "") and "120 de 300" in e["recortado"],
           f"si la red lo devuelve más corto, se avisa: {e.get('recortado')!r}")
        P.comparar_publicado(e, "x" * 300)
        ok("recortado" not in e, "entero, sin aviso")
        r = UP.ClienteUploadPost._resultados([{"platform": "instagram", "status": "completed",
                                                "post_url": "https://instagram.com/p/1",
                                                "caption": "texto de la red"}])
        igual(r["instagram"]["texto"], "texto de la red", "el cliente recoge el texto que devuelve Upload-Post")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_perfiles():
    """Lo que salió en el servidor el 16-10: «Crear perfil» sin el nombre
    escrito, el plan lleno con el perfil YA en Upload-Post, y «Suyu» frente
    a «suyu» al ver las cuentas."""
    seccion("6] perfiles: el nombre escrito, el plan lleno, mayúsculas")
    raiz = os.path.join(CARPETA, "perfiles")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_perfiles.json")
    # el plan gratis, lleno: dos perfiles, «Suyu» (con Instagram) y otro
    with open(simulador, "w", encoding="utf-8") as fh:
        json.dump({"limite": 2, "perfiles": {
            "Suyu": {"instagram": {"display_name": "Suyu IG", "username": "suyu"}},
            "studio_otro": {}}}, fh)
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        igual(P.norma_perfil(" Su yu "), "suyu", "comparar sin mayúsculas ni espacios")
        ok(P.buscar_perfil([{"perfil": "Suyu"}], "suyu") is not None, "«suyu» encuentra «Suyu»")
        ok(P.buscar_perfil([{"perfil": "Suyu"}], "suyu2") is None, "y no confunde otro nombre")
        # adoptar con el plan lleno: no se intenta crear
        ajustes, como = P.usar_perfil(raiz, "cl_suyu", "suyu")
        igual(como, "adoptado", "con el plan lleno, un perfil que ya existe se adopta")
        igual(ajustes["perfil"], "Suyu", "con el nombre exacto de Upload-Post")
        ok(isinstance(ajustes["cuentas"].get("instagram"), dict), "y sus cuentas (Instagram)")
        ok(bool(ajustes["cuentas_vistas"]), "ya miradas")
        with open(simulador, encoding="utf-8") as fh:
            igual(len(json.load(fh)["perfiles"]), 2, "sin crear ningún perfil nuevo")
        # crear uno nuevo con el plan lleno: el mensaje en castellano, antes de pedirlo
        try:
            P.usar_perfil(raiz, "cl_nuevo", "studio_nuevo")
            ok(False, "con el plan lleno no se crea")
        except P.ErrorPublicar as fallo:
            ok("Tu plan de Upload-Post ya tiene 2 perfiles" in str(fallo), f"plan lleno, en castellano: {fallo}")
            igual(fallo.codigo, 409, "como 409")
        # el mensaje de alli también se traduce (si la lista no trae el limite)
        try:
            raise P.UP.ErrorUploadPost("You have reached the limit of 2 profiles", 403)
        except P.UP.ErrorUploadPost as fallo:
            ok(P._PLAN_LLENO.search(str(fallo)) is not None, "reconoce el mensaje de Upload-Post")
        igual(P.norma_perfil("Mi Cliente"), "micliente", "los espacios no cuentan al comparar")
        ok(P.perfil_de_otro(raiz, "S U Y U", "cl_x") == "cl_suyu",
           "y «S U Y U» también es el perfil de otro proyecto")
        # usar sin crear un perfil que no existe: dice que no está
        try:
            P.usar_perfil(raiz, "cl_nuevo", "no_existe", crear=False)
            ok(False, "«Usar este perfil» no crea nada")
        except P.ErrorPublicar as fallo:
            igual(fallo.codigo, 404, f"«Usar este perfil» con uno que no existe: {fallo}")
        # otro proyecto no puede adoptar el mismo, ni escrito distinto
        try:
            P.usar_perfil(raiz, "cl_otro", "SUYU")
            ok(False, "dos proyectos no comparten perfil")
        except P.ErrorPublicar as fallo:
            igual(fallo.codigo, 409, "«SUYU» ya es de otro proyecto")
        # la lista para el desplegable marca de quién es cada uno
        lista = P.perfiles_de_la_cuenta(raiz, "cl_otro")
        nombres = {x["perfil"]: x for x in lista["perfiles"]}
        igual(sorted(nombres), ["Suyu", "studio_otro"], "el desplegable trae los perfiles de verdad")
        igual(nombres["Suyu"]["de_otro"], "cl_suyu", "marcando el que ya usa otro proyecto")
        igual(nombres["Suyu"]["redes"], ["instagram"], "con sus redes conectadas")
        igual(lista["limite"], 2, "y el límite del plan")
        ok(P.perfiles_de_la_cuenta(raiz, "cl_suyu")["perfiles"][0]["propio"], "el propio sale marcado")
        # «Ver cuentas» con el nombre guardado en otras mayúsculas
        P.guardar_ajustes(raiz, "cl_minus", {"perfil": "studio_otro"})
        P.guardar_ajustes(raiz, "cl_minus", {"perfil": "STUDIO_OTRO "})
        visto = P.ver_cuentas(raiz, "cl_minus")
        igual(visto["existe"], True, "«Ver cuentas» encuentra el perfil escrito en mayúsculas")
        igual(visto["ajustes"]["perfil"], "studio_otro", "y apunta el nombre de Upload-Post")
        # con sitio en el plan, «Crear perfil» crea el nombre escrito
        with open(simulador, encoding="utf-8") as fh:
            datos = json.load(fh)
        datos["limite"] = 5
        with open(simulador, "w", encoding="utf-8") as fh:
            json.dump(datos, fh)
        ajustes, como = P.usar_perfil(raiz, "cl_nuevo", "Mi_Cliente")
        igual((como, ajustes["perfil"]), ("creado", "Mi_Cliente"), "crear usa el nombre escrito")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_textos():
    """«Que Claude escriba los textos»: el estado mientras escribe, el fallo que
    se ve (y se apunta), y lo que se le pide (emojis, gancho, cada red)."""
    seccion("7] textos: escribiendo, el fallo, los emojis")
    raiz = os.path.join(CARPETA, "textos")
    os.makedirs(raiz)
    a = P.ajustes_de(raiz, "cl_t")
    igual(a["usar_emojis"], True, "los emojis vienen puestos de fábrica")
    igual(P.guardar_ajustes(raiz, "cl_t", {"usar_emojis": False})["usar_emojis"], False,
          "y se pueden quitar")
    try:
        P.guardar_ajustes(raiz, "cl_t", {"usar_emojis": "no"})
        ok(False, "«usar_emojis» es sí o no")
    except P.ErrorPublicar:
        ok(True, "«usar_emojis» es sí o no")
    # en horizontal: un vídeo normal de YouTube (el Short tiene sus reglas, 12b)
    con = P.instruccion_textos(dict(INFO, formato="horizontal"), ["tiktok", "instagram", "youtube"],
                               P.AJUSTES_DEFECTO)
    sin = P.instruccion_textos(INFO, ["tiktok"], dict(P.AJUSTES_DEFECTO, usar_emojis=False))
    ok("nivel «Vistoso»" in con and "Instagram Reels: 5 a 9" in con, "con emojis: cuántos por red")
    ok("NINGUNO" in sin and "Emojis: sí" not in sin, "sin emojis: se le dice que ninguno")
    ok("gancho" in con and "70 caracteres" in con, "pide gancho y el título de YouTube de 70 como mucho")
    ok("SIN SONIDO" not in con, "las reglas de Facebook solo si se pide Facebook")
    ok(P.MODELO != "sonnet" or P.ESFUERZO != "low", f"más modelo que sonnet/low: {P.MODELO}/{P.ESFUERZO}")
    # escribiendo: la ficha lo dice, con desde cuándo y qué redes
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        P._ESCRIBIENDO["fiesta"] = {"desde": P._iso_lima(), "redes": ["tiktok"]}
        f = P.ficha(raiz, INFO, P.AJUSTES_DEFECTO)
        ok(f["escribiendo"] and f["escribiendo_desde"] and f["escribiendo_redes"] == ["tiktok"],
           "mientras escribe, la ficha dice desde cuándo y qué redes")
        P._ESCRIBIENDO.pop("fiesta", None)
        # el fallo: se ve en la ficha y se apunta en la bitácora
        os.makedirs(P.carpeta(raiz), exist_ok=True)
        with open(os.path.join(P.carpeta(raiz), "_fallar_textos"), "w") as fh:
            fh.write("1")
        P.lanzar_textos(raiz, INFO, ["tiktok"], P.AJUSTES_DEFECTO, en_hilo=False)
        f = P.ficha(raiz, INFO, P.AJUSTES_DEFECTO)
        ok(not f["escribiendo"] and "no se han podido escribir" in f["error_textos"],
           f"si falla, la ficha lo dice: {f['error_textos'][:60]}")
        igual(f["error_redes"], ["tiktok"],
              "y con qué redes: «Reintentar» no reescribe las que no se pidieron")
        with open(os.environ["ESTUDIO_BITACORA_GLOBAL"], encoding="utf-8") as fh:
            ok("publicar_textos_fallo" in fh.read(), "y queda apuntado en la bitácora")
        # reintentar, ya sin fallo
        os.remove(os.path.join(P.carpeta(raiz), "_fallar_textos"))
        P.lanzar_textos(raiz, INFO, ["tiktok"], P.AJUSTES_DEFECTO, en_hilo=False)
        f = P.ficha(raiz, INFO, P.AJUSTES_DEFECTO)
        ok(not f["error_textos"] and f["textos"]["tiktok"]["descripcion"], "«Reintentar» los escribe")
        # 17-10, en el servidor: Claude contestó con «Instagram Reels» de clave
        t, _c = P.normalizar_textos({"Instagram Reels": {"description": "Hola IG", "Hashtags": ["a"]},
                                     "TikTok": {"texto": "Hola TT"}}, ["instagram", "tiktok"])
        igual((t["instagram"]["descripcion"], t["tiktok"]["descripcion"], t["instagram"]["hashtags"]),
              ("Hola IG", "Hola TT", ["a"]), "las claves con el nombre de la red y otros nombres de campo valen")
        t, _c = P.normalizar_textos({"textos": {"youtube": {"title": "T", "descripcion": "D"}}}, ["youtube"])
        igual((t["youtube"]["titulo"], t["youtube"]["descripcion"]), ("T", "D"), "y envueltas en «textos»")
        ok("\"instagram\"" in P.instruccion_textos(INFO, ["instagram"], P.AJUSTES_DEFECTO),
           "la instrucción dice las claves exactas")
        # una respuesta sin textos: fallo que se ve, y lo que había no se pisa
        original = P._textos_simulados
        P._textos_simulados = lambda info, redes, raiz=None: (json.dumps({"Otra cosa": {}}), {"_coste_anotado": True})
        try:
            P.lanzar_textos(raiz, INFO, ["tiktok"], P.AJUSTES_DEFECTO, en_hilo=False)
        finally:
            P._textos_simulados = original
        f2 = P.ficha(raiz, INFO, P.AJUSTES_DEFECTO)
        ok("sin ningún texto" in f2["error_textos"], f"sin textos, se dice: {f2['error_textos'][:50]}")
        igual(f2["textos"]["tiktok"]["descripcion"], f["textos"]["tiktok"]["descripcion"],
              "y el texto que había sigue ahí")
        P._textos_simulados = lambda info, redes, raiz=None: (json.dumps({"tiktok": {"descripcion": "Solo TT"}}),
                                                               {"_coste_anotado": True})
        try:
            P.lanzar_textos(raiz, INFO, ["tiktok", "instagram"], P.AJUSTES_DEFECTO, en_hilo=False)
        finally:
            P._textos_simulados = original
        f3 = P.ficha(raiz, INFO, P.AJUSTES_DEFECTO)
        ok(f3["textos"]["tiktok"]["descripcion"] == "Solo TT" and "Instagram" in f3["error_textos"]
           and f3["error_redes"] == ["instagram"], "a medias: lo que vino se guarda y lo que falta se dice")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)


def prueba_emojis():
    """Rama `textos-emojis` (20-10): el nivel por proyecto (y el sí/no de antes
    leído igual), los emojis de la marca en el prompt, el contador, el aviso
    de la ficha (fuera de la nota SEO) y «✨ Más emojis», que rechaza lo que
    cambie una palabra."""
    seccion("11] emojis: nivel, marca, contador, aviso y «✨ Más emojis»")
    import publicar_seo as SEO                              # noqa: PLC0415
    raiz = os.path.join(CARPETA, "emojis")
    os.makedirs(raiz)
    # EL NIVEL: de fábrica vistoso; el sí/no de antes guardado se respeta
    igual(P.ajustes_de(raiz, "nuevo")["emojis"], "vistoso", "un proyecto sin nada guardado: Vistoso")
    os.makedirs(os.path.dirname(P._ruta_ajustes(raiz)), exist_ok=True)
    P._escribir(P._ruta_ajustes(raiz), {"proyectos": {"viejo_no": {"usar_emojis": False},
                                                      "viejo_si": {"usar_emojis": True}}})
    with open(P._ruta_ajustes(raiz), "rb") as fh:
        antes = fh.read()
    igual(P.ajustes_de(raiz, "viejo_no")["emojis"], "ninguno",
          "«usar_emojis: false» guardado se lee como Ninguno (se respeta lo que eligió)")
    igual(P.ajustes_de(raiz, "viejo_no")["usar_emojis"], False, "y sigue diciendo que no a quien lee el sí/no")
    igual(P.ajustes_de(raiz, "viejo_si")["emojis"], "vistoso", "«usar_emojis: true» guardado: Vistoso")
    with open(P._ruta_ajustes(raiz), "rb") as fh:
        ok(fh.read() == antes, "leer los ajustes no escribe nada (solo se guarda si el dueño toca)")
    igual(P.guardar_ajustes(raiz, "viejo_no", {"emojis": "normal"})["emojis"], "normal",
          "el nivel se cambia y manda sobre el sí/no de antes")
    for malo, que in (("mucho", "un nivel que no existe"), (3, "un número")):
        try:
            P.guardar_ajustes(raiz, "viejo_no", {"emojis": malo})
            ok(False, f"«emojis» no acepta {que}")
        except P.ErrorPublicar:
            ok(True, f"«emojis» no acepta {que}")
    igual(P.guardar_ajustes(raiz, "viejo_no", {"emojis_marca": "🎮, 🕹️ 🎉 🎮"})["emojis_marca"],
          "🎮 🕹️ 🎉", "los emojis de la marca se guardan limpios y sin repetir")
    try:
        P.guardar_ajustes(raiz, "viejo_no", {"emojis_marca": "🎮 consolas"})
        ok(False, "en los emojis de la marca no van letras")
    except P.ErrorPublicar:
        ok(True, "en los emojis de la marca no van letras")

    # EL PROMPT
    redes = ["tiktok", "instagram", "youtube", "linkedin"]
    vistoso = P.instruccion_textos(INFO, redes, dict(P.AJUSTES_DEFECTO, emojis_marca="🎮 🕹️"))
    ok("SIEMPRE con emojis" in vistoso and "EMPIEZA con un emoji" in vistoso,
       "en Vistoso el prompt EXIGE emojis, con el gancho empezando por uno")
    ok("🎮 🕹️" in vistoso and "firma" in vistoso, "y lleva los emojis de la marca como su firma")
    ok("TEMA" in vistoso and "comodines" in vistoso, "pide emojis del tema del vídeo, no comodines")
    ok("🎮➕🎉" in vistoso, "y combinaciones de dos para contar algo (los emojis «propios»)")
    ok("TikTok: 3 a 6" in vistoso and "LinkedIn: 2 a 4" in vistoso and "en el título 1." in vistoso,
       "con su número por red (LinkedIn más sobrio, YouTube uno en el título)")
    ok("que aporten, no que decoren" not in vistoso, "sin la frase que le daba permiso para no poner ninguno")
    sobrio = P.instruccion_textos(INFO, ["tiktok"], dict(P.AJUSTES_DEFECTO, emojis="sobrio"))
    ok("TikTok: 1 a 2" in sobrio and "SIEMPRE con emojis" not in sobrio, "en Sobrio, pocos")
    viejo = P.instruccion_textos(INFO, ["tiktok"], P.ajustes_de(raiz, "viejo_si"))
    ok("SIEMPRE con emojis" in viejo, "un proyecto con el sí de antes recibe el prompt de Vistoso")
    P._escribir(P._ruta_ajustes(raiz), {"proyectos": {"viejo_no": {"usar_emojis": False}}})
    nada = P.instruccion_textos(INFO, ["tiktok"], P.ajustes_de(raiz, "viejo_no"))
    ok("NINGUNO" in nada and "SIEMPRE" not in nada, "y uno con el no de antes, Ninguno")
    ok("EMPIEZAN con un emoji" in P._emojis_de_ganchos(P.AJUSTES_DEFECTO)
       and P._emojis_de_ganchos(dict(P.AJUSTES_DEFECTO, emojis="ninguno")) == "Sin emojis.",
       "los ganchos siguen el nivel")
    ok("los emojis" in SEO.INSTRUCCION_OPTIMIZAR, "«Optimizar SEO» no quita los emojis al reescribir")

    # EL CONTADOR
    for texto, n, que in (("Hola", 0, "sin emojis"), ("🎮 Fiesta 🎉", 2, "dos sueltos"),
                          ("👨‍👩‍👧 familia", 1, "una familia con ZWJ es uno"),
                          ("🇵🇪 Lima 🇲🇽", 2, "cada bandera es una"),
                          ("👍🏽👍🏿", 2, "con tono de piel, uno cada uno"),
                          ("❤️ y ❤", 2, "con y sin selector de variante"),
                          ("1️⃣ 2️⃣ #3 en 2026", 2, "las teclas, sí; un número suelto, no"),
                          ("© → ↔️ ™️", 2, "©/→ sin selector son texto; con él, emoji"),
                          ("🎮➕🎉", 3, "una combinación son sus emojis"),
                          ("🏳️‍🌈", 1, "la bandera del arcoíris es una")):
        igual(P.contar_emojis(texto), n, f"contar: {que}")
    igual(P.quitar_emojis("🎮 Fiesta 👨‍👩‍👧 en 🇵🇪 ❤️"), " Fiesta  en  ", "quitar emojis deja solo el texto")

    # EL AVISO: por debajo del mínimo del nivel, y SIN tocar la nota SEO
    textos = {"tiktok": {"descripcion": "Fiesta en casa con consola 🎮"},
              "youtube": {"titulo": "Alquiler de consolas en Lima", "descripcion":
                          "🎮 Uno\n\n🎉 Dos\n\n📍 Lima\n\n👉 Reserva"},
              "instagram": {"descripcion": ""}}
    e = P.emojis_de_ficha(textos, P.AJUSTES_DEFECTO, ["tiktok", "youtube", "instagram"])
    ok(e["redes"]["tiktok"]["descripcion"]["faltan"] and e["redes"]["tiktok"]["descripcion"]["minimo"] == 3,
       "TikTok con 1 de 3: la ficha avisa")
    ok(e["redes"]["youtube"]["titulo"]["faltan"] and not e["redes"]["youtube"]["descripcion"]["faltan"],
       "el título de YouTube sin emoji avisa; su texto con 4, no")
    ok(not e["redes"]["instagram"]["descripcion"]["faltan"], "un texto vacío no avisa de emojis")
    ok(not any(c["faltan"] for r in P.emojis_de_ficha(textos, dict(P.AJUSTES_DEFECTO, emojis="ninguno"),
                                                       ["tiktok", "youtube"])["redes"].values()
               for c in r.values()), "en Ninguno no avisa nunca")
    comp = P.componer("tiktok", textos["tiktok"], P.AJUSTES_DEFECTO, INFO)
    nota_v = SEO.nota("tiktok", textos["tiktok"], comp, P.AJUSTES_DEFECTO, {}, INFO, "consolas")
    nota_n = SEO.nota("tiktok", textos["tiktok"], comp, dict(P.AJUSTES_DEFECTO, emojis="ninguno"), {}, INFO,
                      "consolas")
    igual(nota_v, nota_n, "la nota SEO no cambia por los emojis que falten")
    ok("emoji" not in json.dumps(nota_v, ensure_ascii=False).lower(), "ni habla de emojis")

    # «✨ MÁS EMOJIS»
    P._escribir(P._ruta_video(raiz, "fiesta"), dict(P._leer_video(raiz, "fiesta"), textos={
        "tiktok": {"descripcion": "Fiesta en casa\nReserva ya #consolas"},
        "youtube": {"titulo": "Alquiler de consolas en Lima", "descripcion": "Hola"}}))
    original = P._hablar_con_claude
    pedido = {}

    def falso(respuesta):
        def hablar(instruccion, sistema, proyecto, cwd, para, simulado, **kw):
            pedido.update(kw, instruccion=instruccion)
            return json.dumps({"texto": respuesta}, ensure_ascii=False), {"_coste_anotado": True}
        return hablar
    try:
        P._hablar_con_claude = falso("🎮 Fiesta en casa\n👉 Reserva ya #consolas 🎉")
        r = P.vestir_con_emojis(raiz, INFO, "tiktok", "descripcion", None,
                                dict(P.AJUSTES_DEFECTO, emojis_marca="🎮"))
        igual((r["texto"], r["antes"], r["despues"]), ("🎮 Fiesta en casa\n👉 Reserva ya #consolas 🎉", 0, 3),
              "«Más emojis» acepta el mismo texto con emojis añadidos")
        igual((pedido.get("modelo"), pedido.get("esfuerzo")), ("haiku", "low"), "y es barato: haiku, esfuerzo bajo")
        ok(pedido.get("tiempo_max_s", 99) <= 55, "con un tope por debajo del corte del proxy")
        ok("🎮" in pedido["instruccion"] and "Fiesta en casa" in pedido["instruccion"],
           "el prompt lleva los emojis de la marca y el texto")
        igual(P._leer_video(raiz, "fiesta")["textos"]["tiktok"]["descripcion"], "Fiesta en casa\nReserva ya #consolas",
              "y no guarda nada: lo guarda la pantalla por el camino de siempre")
        for respuesta, que in (("🎮 Fiesta en tu casa\nReserva ya #consolas", "cambia una palabra"),
                               ("🎮 Fiesta en casa\nReserva ya 🎉", "quita un hashtag"),
                               ("Fiesta casa 🎮\nReserva ya #consolas", "quita una palabra"),
                               ("Fiesta en casa\nReserva ya #consolas", "no añade ningún emoji"),
                               ("", "no devuelve nada")):
            P._hablar_con_claude = falso(respuesta)
            try:
                P.vestir_con_emojis(raiz, INFO, "tiktok", "descripcion", "Fiesta en casa\nReserva ya #consolas",
                                    P.AJUSTES_DEFECTO)
                ok(False, f"«Más emojis» rechaza una respuesta que {que}")
            except P.ErrorPublicar as fallo:
                ok(fallo.codigo == 422, f"«Más emojis» rechaza una respuesta que {que} ({str(fallo)[:40]}…)")
        P._hablar_con_claude = falso("Alquiler de consolas en Lima 🎮")
        r = P.vestir_con_emojis(raiz, INFO, "youtube", "titulo", None, P.AJUSTES_DEFECTO)
        igual(r["texto"], "Alquiler de consolas en Lima 🎮", "también con el título")
        ok("al final" in pedido["instruccion"], "y en YouTube pide el emoji al final del título")
        for red, campo, que in (("tiktok", "titulo", "TikTok no tiene título"), ("nada", "descripcion", "una red que no existe"),
                                ("youtube", "cta", "un campo que no es título ni texto")):
            try:
                P.vestir_con_emojis(raiz, INFO, red, campo, None, P.AJUSTES_DEFECTO)
                ok(False, f"«Más emojis» no vale con {que}")
            except P.ErrorPublicar:
                ok(True, f"«Más emojis» no vale con {que}")
    finally:
        P._hablar_con_claude = original
    # el doble del Studio (ESTUDIO_SIMULAR) también pasa la comprobación
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        r = P.vestir_con_emojis(raiz, INFO, "tiktok", "descripcion", "Uno\n\nDos", P.AJUSTES_DEFECTO)
        ok(r["texto"].startswith("🎮 Uno\n\n🎉 Dos") and P.contar_emojis(r["texto"]) >= 3
           and P.quitar_emojis(r["texto"]).replace(" ", "") == "Uno\n\nDos",
           f"el doble pone uno por párrafo y llega al mínimo de TikTok en Vistoso: {r['texto']!r}")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)


def prueba_portada():
    """Qué campo de portada va a cada red según lo elegido."""
    seccion("8] portada: qué va a cada red")
    raiz = os.path.join(CARPETA, "portada")
    os.makedirs(raiz)
    mp4 = os.path.join(raiz, "v.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=3",
                    "-pix_fmt", "yuv420p", mp4], check=True)
    info = dict(INFO, mp4=mp4, formato="horizontal", duracion_s=3)
    todas = ["tiktok", "instagram", "youtube", "facebook"]
    campos, ficheros = P.campos_portada(raiz, info, {}, todas)
    igual((campos, ficheros), ({}, []), "sin elegir nada no se manda nada: cada red pone la suya")
    datos = {"portada": {"ms": 2000}}
    campos, ficheros = P.campos_portada(raiz, info, datos, todas)
    igual(campos, {"thumb_offset": "2000", "cover_timestamp": 2000},
          "un fotograma: thumb_offset en Instagram y cover_timestamp en TikTok")
    igual([c for c, _r in ficheros], ["facebook_thumbnail"],
          "Facebook (como vídeo) recibe el fotograma; YouTube no sin marcarlo")
    campos, _f = P.campos_portada(raiz, info, {"portada": {"ms": 40000}}, ["instagram", "tiktok"])
    igual(campos, {"thumb_offset": "2900", "cover_timestamp": 2900},
          "un momento pasado el final (se volvió a montar más corto) se recorta al vídeo")
    datos["portada"]["youtube"] = True
    _c, ficheros = P.campos_portada(raiz, info, datos, todas)
    igual(sorted(c for c, _r in ficheros), ["facebook_thumbnail", "thumbnail"],
          "con «también a YouTube», su miniatura")
    vertical = dict(info, formato="vertical", duracion_s=3)
    _c, ficheros = P.campos_portada(raiz, vertical, datos, ["facebook"])
    igual(ficheros, [], "un Reel de Facebook no lleva miniatura")
    for contenido, que in ((b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\nfile:///etc/passwd\n", "una lista HLS"),
                           (b"no soy una imagen", "texto")):
        try:
            P.guardar_imagen_portada(raiz, "fiesta", contenido, ".png")
            ok(False, f"{que} con nombre .png no pasa como portada")
        except P.ErrorPublicar:
            ok(True, f"{que} con nombre .png no pasa como portada (manda el contenido, no el nombre)")
    sobras = [n for n in os.listdir(os.path.join(P.carpeta(raiz), "portadas"))
              if "subida" in n or n.count(".") > 1] if os.path.isdir(os.path.join(P.carpeta(raiz), "portadas")) else []
    igual(sobras, [], "y no deja ficheros a medias")
    # una imagen subida
    png = os.path.join(raiz, "p.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=800x800",
                    "-frames:v", "1", png], check=True)
    with open(png, "rb") as fh:
        P.guardar_imagen_portada(raiz, "fiesta", fh.read(), ".png")
    datos = P._leer_video(raiz, "fiesta")
    datos["portada"]["ms"] = 2000
    campos, ficheros = P.campos_portada(raiz, info, datos, todas)
    nombres = sorted(c for c, _r in ficheros)
    igual(nombres, ["cover_image", "facebook_thumbnail"],
          "una imagen: cover_image en Instagram y Facebook")
    igual(campos, {"cover_timestamp": 2000}, "y TikTok sigue con el fotograma si no se marca")
    datos["portada"].update(tiktok_imagen=True, youtube=True)
    campos, ficheros = P.campos_portada(raiz, info, datos, todas)
    igual(sorted(c for c, _r in ficheros), ["cover_image", "facebook_thumbnail", "thumbnail",
                                            "tiktok_cover_image"], "y a TikTok y YouTube si se marcan")
    igual(campos, {}, "sin campos de momento cuando va la imagen")
    # el cliente las manda en el multipart
    cuerpo = UP._Multipart([("user", "x")], [("video", mp4), ("cover_image", png)])
    todo = b""
    while True:
        trozo = cuerpo.read()
        if not trozo:
            break
        todo += trozo
    ok(b'name="cover_image"; filename="p.png"' in todo, "el multipart lleva la imagen con su campo")
    igual(len(todo), cuerpo.longitud, "y su longitud cuadra")


def prueba_retencion_y_resumenes():
    seccion("4b] retención, lectura guardada, semana y mes, lo que mejor funcionó")
    raiz = os.path.join(CARPETA, "retencion")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_retencion.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_r")
        cli.enlace_conectar("studio_r", ["tiktok", "youtube"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        info = dict(INFO, pid="ret", mp4=mp4, mp4_huella="h1")
        ajustes = dict(P.AJUSTES_DEFECTO, perfil="studio_r")
        P.guardar_ficha(raiz, "ret", {"textos": {"tiktok": {"descripcion": "Texto de TikTok"},
                                                 "youtube": {"titulo": "Título YT", "descripcion": "Y"}}})
        P.enviar(raiz, info, ajustes, {"redes": ["tiktok", "youtube"], "modo": "ahora",
                                       "confirmado": True}, en_hilo=False)
        P.RESPIRO_CONSULTA_S = 0
        for _ in range(3):
            P.refrescar(raiz)
        P.actualizar_metricas(raiz, ["ret"])              # TikTok aún sin cifras
        r = P.medir(raiz, ["ret"], forzar=True)
        envios = {e["red"]: e for e in P._leer_video(raiz, "ret")["envios"]}
        tt, yt = envios["tiktok"]["metricas"], envios["youtube"]["metricas"]
        ok(isinstance(tt.get("vista_entera"), float) and 0 < tt["vista_entera"] < 1,
           f"TikTok guarda la fracción que lo vio entero: {tt.get('vista_entera')}")
        ok(tt.get("tiempo_medio_s"), "y el tiempo medio")
        ok(envios["tiktok"].get("post_id") and envios["youtube"].get("post_id"),
           "cada envío guarda el id de su post en la red")
        ok(isinstance(yt.get("media_vista"), float) and yt.get("vista_entera") is None,
           "la retención de YouTube (lo visto de media) llega por la lectura guardada, en su campo")
        # EL FALLO DE LA REVISIÓN: Upload-Post sella su lectura un momento ANTES
        # que la nuestra; comparada con nuestra hora, la retención de YouTube no
        # cambiaba nunca después de la primera. Un segundo «Actualizar» la mueve.
        primera = yt["media_vista"]
        P.medir(raiz, ["ret"], forzar=True)
        yt2 = {e["red"]: e for e in P._leer_video(raiz, "ret")["envios"]}["youtube"]["metricas"]
        ok(yt2["media_vista"] != primera,
           f"un segundo «Actualizar» trae la retención nueva de YouTube ({primera} → {yt2['media_vista']})")
        ok(yt2.get("guardada_al"), "con su propio reloj, aparte del de las cifras")
        # (2.ª revisión) una lectura EN VIVO no borra ese reloj: si lo borrara,
        # una lectura guardada más vieja volvería a pisar la retención
        P.actualizar_metricas(raiz, ["ret"], forzar=True)
        yt3 = {e["red"]: e for e in P._leer_video(raiz, "ret")["envios"]}["youtube"]["metricas"]
        igual(yt3.get("guardada_al"), yt2["guardada_al"], "la lectura en vivo conserva el reloj de la guardada")
        envio_yt = next(e for e in P._leer_video(raiz, "ret")["envios"] if e["red"] == "youtube")
        indice = {("youtube", "id", envio_yt["post_id"]): {
            "red": "youtube", "post_id": envio_yt["post_id"], "media_vista": 0.01,
            "al": "2020-01-01T00:00:00+00:00"}}
        P._apuntar_guardadas(raiz, [("ret", envio_yt)], indice)
        yt4 = {e["red"]: e for e in P._leer_video(raiz, "ret")["envios"]}["youtube"]["metricas"]
        igual(yt4["media_vista"], yt3["media_vista"], "una lectura guardada más vieja no pisa la retención")
        ok(r["guardadas"] >= 1, f"«medir» hace también la lectura guardada: {r}")
        igual(yt.get("guardada"), True, "y lo apunta")
        # una lectura guardada MÁS VIEJA no pisa las cifras de la lectura en vivo
        vistas = {e["red"]: e for e in P._leer_video(raiz, "ret")["envios"]}["tiktok"]["metricas"]["vistas"]
        datos_sim = json.load(open(simulador, encoding="utf-8"))
        for trabajo in datos_sim["trabajos"].values():
            for red, g in (trabajo.get("guardadas") or {}).items():
                g.update(al="2020-01-01T00:00:00+00:00", vistas=1)
        json.dump(datos_sim, open(simulador, "w", encoding="utf-8"))
        P.leer_guardadas(raiz, ["ret"])
        envios = {e["red"]: e for e in P._leer_video(raiz, "ret")["envios"]}
        igual(envios["tiktok"]["metricas"]["vistas"], vistas, "las vistas de TikTok siguen igual")
        # una lectura guardada sin perfil en el envío no se pide
        igual(P.leer_guardadas(raiz, ["no_existe_aun"]), {"leidos": 0, "actualizados": 0, "errores": []},
              "sin nada publicado no se pregunta a nadie")

        # el resumen: la retención se PROMEDIA y lo que no la da no cuenta como cero
        P.marcar_a_mano(raiz, info, "facebook", "")
        res = P.resultados(raiz, [{"pid": "ret", "nombre": "Ret", "cliente": ""}], "")
        igual(res["total"]["vista_entera"], envios["tiktok"]["metricas"]["vista_entera"],
              "«hasta el final» solo lo da TikTok: no se mezcla con lo de YouTube")
        igual(res["total"]["media_vista"], envios["youtube"]["metricas"]["media_vista"],
              "y lo visto de media, solo YouTube")
        igual(res["total"]["vista_entera_posts"], 1, "de un post (ni YouTube ni el subido a mano)")
        igual(res["por_red"]["facebook"]["vista_entera"], None, "una red sin retención: None, no 0")
        ok(not any(k.startswith("_") for k in res["total"]), "sin restos de la cuenta interna")
        # la media pondera por vistas: 100k vistas pesan más que 50
        acum = {}
        P._suma(acum, {"vistas": 100000, "vista_entera": 0.1})
        P._suma(acum, {"vistas": 50, "vista_entera": 0.9})
        igual(round(P._medias(acum)["vista_entera"], 3), 0.1,
              "la retención media se pondera por vistas (un post de 50 no pesa como uno de 100.000)")
        acum = {}
        P._suma(acum, {"vistas": 1000, "vista_entera": 0.1})
        P._suma(acum, {"vista_entera": 0.9})
        cerrado = P._medias(acum)
        igual((cerrado["vista_entera"], cerrado["vista_entera_posts"]), (0.1, 1),
              "el número de posts cuadra con los que entran en la media")

        # semana y mes, con envíos en fechas conocidas
        ahora = P._leer_momento("2026-10-15T12:00")            # jueves
        datos = P._leer_video(raiz, "ret")
        base = dict(datos["envios"][0])
        datos["envios"] = []
        for i, (cuando, vistas_x) in enumerate((("2026-10-13T10:00", 100), ("2026-10-15T09:00", 50),
                                                ("2026-10-08T10:00", 70), ("2026-10-01T08:00", 40),
                                                ("2026-09-10T08:00", 500), ("2026-08-31T08:00", 9))):
            datos["envios"].append(dict(base, id=f"e{i}", red="tiktok", estado="publicado",
                                        cuando=cuando, metricas={"vistas": vistas_x, "me_gusta": 1}))
        P._escribir(P._ruta_video(raiz, "ret"), datos)
        videos = [{"pid": "ret", "nombre": "Ret", "cliente": ""}]
        per = P.periodos(raiz, videos, "", ahora=ahora)
        igual(per["semana"]["desde"], "2026-10-12", "la semana empieza el lunes")
        igual((per["semana"]["actual"]["posts"], per["semana"]["actual"]["vistas"]), (2, 150),
              "esta semana: lo publicado desde el lunes")
        igual((per["semana"]["anterior"]["posts"], per["semana"]["anterior"]["vistas"]), (1, 70),
              "la semana pasada hasta el mismo momento (el miércoles 8 entra)")
        tarde = P._leer_momento("2026-10-13T08:00")       # martes temprano
        per_lunes = P.periodos(raiz, videos, "", ahora=tarde)
        igual(per_lunes["semana"]["anterior"]["posts"], 0,
              "un martes temprano no se compara con la semana pasada ENTERA (el miércoles 8 no entra)")
        igual((per["mes"]["actual"]["posts"], per["mes"]["actual"]["vistas"]), (4, 260),
              "este mes, desde el día 1")
        igual((per["mes"]["anterior"]["posts"], per["mes"]["anterior"]["vistas"]), (1, 500),
              "el mes pasado hasta el día 15 (sin lo de agosto)")
        igual(P.periodos(raiz, videos, "", ahora=P._leer_momento("2026-10-05T12:00"))["mes"]["anterior"]["posts"],
              0, "el día 5 se compara con el 1–5 del mes pasado (el 10 no entra)")
        fin_de_mes = P.periodos(raiz, videos, "", ahora=P._leer_momento("2026-10-31T12:00"))
        igual(fin_de_mes["mes"]["anterior_hasta"], "2026-10-01T00:00:00",
              "el 31 frente a un mes de 30 días: el mes pasado entero, sin pasarse")
        igual(P.periodos(raiz, videos, "cl_otro", ahora=ahora)["mes"]["actual"]["posts"], 0,
              "lo de otro proyecto no entra")

        # lo que mejor funcionó: el punto de lectura para la Parrilla y el piloto
        hoy = P.ahora_lima()
        datos["envios"] = []
        filas = [("tiktok", 1, {"vistas": 1000, "me_gusta": 10, "comentarios": 0, "vista_entera": 0.1}),
                 ("tiktok", 2, {"vistas": 200, "me_gusta": 60, "comentarios": 20, "vista_entera": 0.5}),
                 ("youtube", 3, {"vistas": 20, "me_gusta": 19, "vista_entera": 0.9}),
                 ("youtube", 40, {"vistas": 99999, "me_gusta": 1}),
                 ("instagram", 4, {"vistas": None, "me_gusta": 3})]
        for i, (red, hace, m) in enumerate(filas):
            datos["envios"].append(dict(base, id=f"m{i}", red=red, estado="publicado",
                                        cuando=P._iso_lima(hoy - dt.timedelta(days=hace)), metricas=m))
        P._escribir(P._ruta_video(raiz, "ret"), datos)
        lq = P.lo_que_funciono(raiz, videos, None, dias=30)
        igual([p["metricas"]["vistas"] for p in lq["posts"]], [1000, 200, 20],
              "por vistas, de más a menos, sin lo de hace más de 30 días ni lo que no tiene vistas")
        primero = lq["posts"][0]
        igual((primero["red"], primero["descripcion"]), ("tiktok", "Texto de TikTok"),
              "cada post trae su red y el texto con que salió")
        ok(primero["dia"] in P._DIAS_SEMANA and len(primero["hora"]) == 5, "y el día y la hora de Lima")
        lq = P.lo_que_funciono(raiz, videos, None, por="interaccion")
        igual([p["metricas"]["vistas"] for p in lq["posts"]], [200, 1000],
              "por interacción: la proporción manda, y con menos de 50 vistas no entra")
        igual(lq["posts"][0]["interaccion"], 0.4, "la interacción es (me gusta + comentarios…)/vistas")
        lq = P.lo_que_funciono(raiz, videos, None, por="vista_entera")
        igual([p["metricas"]["vista_entera"] for p in lq["posts"]], [0.5, 0.1], "por retención")
        igual(len(P.lo_que_funciono(raiz, videos, None, red="youtube")["posts"]), 1, "filtrado por red")
        igual(len(P.lo_que_funciono(raiz, videos, "cl_otro")["posts"]), 0, "y por proyecto")
        igual(len(P.lo_que_funciono(raiz, videos, None, cuantos=1)["posts"]), 1, "y cuántos")
        igual(P.lo_que_funciono(raiz, videos, None, por="raro", cuantos="x", dias="y")["por"], "vistas",
              "lo que no se entiende vuelve a lo de siempre")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_seo():
    """publicar-seo (18-10-2026): la palabra clave, los campos que van a cada
    red, la nota SEO, y que «Optimizar» no pise lo editado."""
    seccion("9] SEO: palabra clave, campos por red, nota y optimizar")
    S = P.SEO
    raiz = os.path.join(CARPETA, "seo")
    os.makedirs(raiz)
    ajustes = dict(P.AJUSTES_DEFECTO, palabra_clave="alquiler de consolas en Lima",
                   secundarias="fiestas infantiles, eventos corporativos", zona="Lima, Perú",
                   ig_ubicacion="106042326099451", tt_ubicacion_id="lima123",
                   tt_ubicacion_nombre="Lima", yt_categoria="24")
    # --- ajustes
    for malo, que in (({"ig_ubicacion": "Lima"}, "una ubicación de Instagram que no es un número"),
                      ({"yt_categoria": "99"}, "una categoría de YouTube que no existe"),
                      ({"yt_para_ninos": "no"}, "«hecho para niños» que no es sí o no")):
        try:
            P.guardar_ajustes(raiz, "cl_s", malo)
            ok(False, f"{que} se rechaza")
        except P.ErrorPublicar:
            ok(True, f"{que} se rechaza")
    a = P.guardar_ajustes(raiz, "cl_s", {"palabra_clave": " alquiler de  consolas en Lima ",
                                         "ig_ubicacion": "106042326099451"})
    igual(a["palabra_clave"], "alquiler de consolas en Lima", "la palabra clave se guarda limpia")
    igual((a["yt_categoria"], a["yt_idioma_audio"], a["yt_para_ninos"]), ("22", "es-US", False),
          "de fábrica: Gente y blogs, español de Latinoamérica y NO hecho para niños")
    # --- lo que se pide a Claude
    bloque = S.bloque_instruccion(ajustes, "consolas para cumpleaños", ["instagram"],
                                  recientes=["gaming"], aprendido=["Instagram, 900 vistas: «¿Fiesta?»"])
    ok("consolas para cumpleaños" in bloque and "PRIMERA LÍNEA" in bloque and "Lima, Perú" in bloque,
       "la instrucción lleva la palabra del vídeo, dónde ponerla y la zona")
    ok("gaming" in bloque and "900 vistas" in bloque, "y lo ya usado y lo que mejor funcionó")
    igual(S.bloque_instruccion(P.AJUSTES_DEFECTO, "", ["instagram"]), "",
          "sin palabra clave ni zona, la instrucción es la de antes")
    inst = P.instruccion_textos(INFO, ["instagram"], ajustes, bloque)
    ok("primer_comentario" in inst and "palabra_clave" in inst, "el JSON pide primer comentario y palabra")
    t, _c = P.normalizar_textos({"instagram": {"descripcion": "x", "first_comment": "¿Y tú?"}}, ["instagram"])
    igual(t["instagram"]["primer_comentario"], "¿Y tú?", "el primer comentario se entiende")
    # --- lo que va a cada red
    textos = {"titulo": "Alquiler de consolas en Lima para tu fiesta", "descripcion":
              "Alquiler de consolas en Lima: la fiesta que no acaba\nTe lo llevamos.",
              "cta": "Escríbenos", "hashtags": ["lima", "fiestas", "gaming", "consolas", "cumple"],
              "primer_comentario": "¿Cuál juego elegirías?"}
    datos = {"colaboradores": "@marca1, @marca2", "etiquetas": "@cliente"}
    c = P.componer("instagram", textos, ajustes, INFO, None, datos)["campos"]
    igual((c.get("location_id"), c.get("collaborators"), c.get("user_tags"), c.get("instagram_first_comment")),
          ("106042326099451", "marca1,marca2", "cliente", "¿Cuál juego elegirías?"),
          "Instagram: ubicación, colaboradores, etiquetas y primer comentario")
    c = P.componer("youtube", textos, ajustes, dict(INFO, formato="horizontal", duracion_s=300), None, {})["campos"]
    igual((c.get("categoryId"), c.get("defaultLanguage"), c.get("defaultAudioLanguage"),
           c.get("selfDeclaredMadeForKids")), ("24", "es", "es-US", False), "YouTube: categoría, idiomas, no niños")
    ok(c.get("tags[]", [None])[0] == "alquiler de consolas en Lima" and "fiestas infantiles" in c["tags[]"],
       f"YouTube: las etiquetas empiezan por la palabra clave: {c.get('tags[]')}")
    r = P.componer("tiktok", textos, ajustes, INFO, None, {})
    ok("tiktok_location_id" not in r["campos"] and "tiktok_first_comment" not in r["campos"]
       and len(r["avisos"]) >= 2, "TikTok sin las funciones de la cuenta: ni ubicación ni comentario, y se avisa")
    c = P.componer("tiktok", textos, dict(ajustes, tt_ubicacion_puede=True, tt_comentarios_puede=True),
                   INFO, None, {})["campos"]
    igual((c.get("tiktok_location_id"), c.get("tiktok_location_name"), c.get("tiktok_first_comment")),
          ("lima123", "Lima", "¿Cuál juego elegirías?"), "con ellas, sí")
    igual(S.nombre_fichero("alquiler de consolas en Lima", "Fiesta en casa", "fiesta"),
          "alquiler-de-consolas-en-lima-fiesta-en-casa.mp4", "el MP4 se sube con la palabra clave en el nombre")
    # --- la nota SEO, sin Claude
    comp = P.componer("youtube", textos, ajustes, INFO, None, {})
    n = S.nota("youtube", textos, comp, ajustes, {}, INFO, "alquiler de consolas en Lima")
    puntos = {x["texto"]: x["ok"] for x in n["puntos"]}
    ok(puntos.get("palabra clave al principio del título") and puntos.get("palabra clave en la primera línea"),
       f"la nota ve la palabra clave en el título y en la primera línea ({n['nota']}/100)")
    ok(any(not v and "portada" in k for k, v in puntos.items()), "y que falta la portada")
    n7 = S.nota("tiktok", dict(textos, hashtags=["a", "b", "c", "d", "e", "f", "g"]), {}, ajustes, {}, INFO, "")
    ok(not next(x for x in n7["puntos"] if "hashtags (" in x["texto"])["ok"],
       "7 hashtags en TikTok no suman: están fuera de rango")
    malo = dict(textos, titulo="Una fiesta increíble", descripcion="Hola\nadiós", cta="",
                hashtags=["fyp", "viral"])
    n2 = S.nota("youtube", malo, P.componer("youtube", malo, ajustes, INFO, None, {}), ajustes, {}, INFO,
                "alquiler de consolas en Lima")
    textos_malos = " | ".join(x["texto"] for x in n2["puntos"] if not x["ok"])
    ok(n2["nota"] < n["nota"] and "fyp" in textos_malos and "llamada a la acción" in textos_malos,
       f"un texto flojo saca menos y dice por qué: {n2['nota']} — {textos_malos[:120]}")
    # --- optimizar, ganchos y palabras (con el doble de Claude)
    os.environ["ESTUDIO_SIMULAR"] = "1"
    simulador = os.path.join(CARPETA, "sim_seo.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        info = dict(INFO, pid="seo1")
        P.guardar_ficha(raiz, "seo1", {"textos": {"instagram": {"descripcion": "Texto mío", "cta": "Ven"}}})
        P.lanzar_optimizar(raiz, info, ["instagram"], ajustes, en_hilo=False)
        f = P.ficha(raiz, info, ajustes)
        prop = f["seo"]["propuesta"]["redes"]["instagram"]
        ok("descripcion" in prop["campos"] and f["textos"]["instagram"]["descripcion"] == "Texto mío",
           "«Optimizar» deja una propuesta y NO toca el texto")
        P.guardar_ficha(raiz, "seo1", {"textos": {"instagram": {"descripcion": "Texto mío cambiado"}}})
        try:
            P.guardar_ficha(raiz, "seo1", {"aceptar_seo": {"instagram": ["descripcion"]}})
            ok(False, "aceptar no pisa lo editado después de pedir la revisión")
        except P.ErrorPublicar as fallo:
            igual(fallo.codigo, 409, f"aceptar no pisa lo editado después de pedir la revisión: {fallo}")
        f = P.ficha(raiz, info, ajustes)
        igual(f["textos"]["instagram"]["descripcion"], "Texto mío cambiado", "y lo editado sigue ahí")
        P.guardar_ficha(raiz, "seo1", {"aceptar_seo": {"instagram": ["primer_comentario"]}})
        f = P.ficha(raiz, info, ajustes)
        igual(f["textos"]["instagram"]["primer_comentario"], "¿Cuál elegirías tú?", "aceptar un campo lo pone")
        P.guardar_ficha(raiz, "seo1", {"rechazar_seo": {"instagram": ["descripcion"]}})
        igual(P.ficha(raiz, info, ajustes)["seo"]["propuesta"], {}, "«Dejar el mío» lo quita de la propuesta")
        # revisión del 18-10: lo que se retoca MIENTRAS Claude revisa no se pisa
        original = P._optimizar_simulado

        vueltas = []

        def tocando(datos_video, redes):
            vueltas.append(1)
            P.guardar_ficha(raiz, "seo1", {"textos": {"instagram": {
                "descripcion": f"Retocado mientras {len(vueltas)}"}}})
            return original(datos_video, redes)
        P._optimizar_simulado = tocando
        try:
            P.lanzar_optimizar(raiz, info, ["instagram"], ajustes, en_hilo=False)
            try:
                P.guardar_ficha(raiz, "seo1", {"aceptar_seo": {"instagram": ["descripcion"]}})
                ok(False, "aceptar no pisa lo retocado mientras Claude revisaba")
            except P.ErrorPublicar as fallo:
                igual(fallo.codigo, 409, "aceptar no pisa lo retocado mientras Claude revisaba")
            P.guardar_ficha(raiz, "seo1", {"descartar_seo": True})
            P._optimizar(raiz, info, ["instagram"], ajustes, None, None, aplicar=True)
            igual(P.ficha(raiz, info, ajustes)["textos"]["instagram"]["descripcion"], "Retocado mientras 2",
                  "ni con «optimizar al escribir»")
        finally:
            P._optimizar_simulado = original
        P.guardar_ficha(raiz, "seo1", {"descartar_seo": True})
        P._ESCRIBIENDO["seo1"] = {"desde": P._iso_lima(), "redes": ["instagram"]}
        try:
            P.lanzar_optimizar(raiz, info, ["instagram"], ajustes, en_hilo=False)
            ok(False, "no se optimiza mientras Claude escribe los textos")
        except P.ErrorPublicar as fallo:
            igual(fallo.codigo, 409, "no se optimiza mientras Claude escribe los textos")
        finally:
            P._ESCRIBIENDO.pop("seo1", None)
        # ganchos
        P.lanzar_ganchos(raiz, info, "instagram", ajustes, en_hilo=False)
        ganchos = P.ficha(raiz, info, ajustes)["seo"]["ganchos"]["instagram"]
        igual(len(ganchos), 3, "«Dame 3 ganchos» deja tres")
        for malo in (-1, True, "1", 9):
            try:
                P.usar_gancho(raiz, "seo1", "instagram", malo)
                ok(False, f"un gancho {malo!r} no existe")
            except P.ErrorPublicar:
                ok(True, f"un gancho {malo!r} no existe")
        f = P.usar_gancho(raiz, "seo1", "instagram", 1)
        ok(f["textos"]["instagram"]["descripcion"].startswith(ganchos[1]) and "cambiado" not in
           f["textos"]["instagram"]["descripcion"].splitlines()[0],
           "«Usar este» lo pone de primera línea y quita la que había")
        # palabras clave del proyecto
        P.lanzar_palabras(raiz, "cl_s", "EstadoPlay", "EstadoPlay", "Encargo: fiestas", en_hilo=False)
        pr = P.ajustes_de(raiz, "cl_s")["propuesta_palabras"]
        ok(pr["principal"]["frase"] and pr["principal"]["porque"] and pr["internet"] is True
           and pr["principal"].get("sugerencias"), "«Proponer palabras clave»: principal con su porqué y sugerencias")
        igual(P.ajustes_de(raiz, "cl_s")["palabra_clave"], "alquiler de consolas en Lima",
              "proponer no cambia la palabra clave: la elige la persona")
        try:
            P.guardar_ajustes(raiz, "cl_s", {"propuesta_palabras": {"principal": "x"}})
            ok(P.ajustes_de(raiz, "cl_s")["propuesta_palabras"]["principal"] != "x",
               "la propuesta no se escribe desde fuera")
        except P.ErrorPublicar:
            ok(True, "la propuesta no se escribe desde fuera")
        # optimizar al escribir: las dos pasadas seguidas, aplicadas
        info2 = dict(INFO, pid="seo2")
        P.lanzar_textos(raiz, info2, ["instagram"], dict(ajustes, optimizar_al_escribir=True), en_hilo=False)
        f = P.ficha(raiz, info2, ajustes)
        ok(f["textos"]["instagram"]["descripcion"].startswith("[SEO]") and not f["seo"]["propuesta"],
           "«Optimizar SEO al escribir»: la revisión queda aplicada sola")
        igual(f["seo"]["palabra_propuesta"], "consolas para fiestas en casa",
              "Claude propone una palabra clave para este vídeo")
        # si la segunda pasada falla, los textos siguen escritos y se dice aparte
        info3 = dict(INFO, pid="seo3")
        P._optimizar_simulado = lambda d, r: (_ for _ in ()).throw(RuntimeError("sin cupo"))
        try:
            P.lanzar_textos(raiz, info3, ["instagram"], dict(ajustes, optimizar_al_escribir=True), en_hilo=False)
        finally:
            P._optimizar_simulado = original
        f = P.ficha(raiz, info3, ajustes)
        ok(f["textos"]["instagram"]["descripcion"] and not f["error_textos"]
           and "revisión SEO falló" in f["seo"]["errores"].get("optimizar", ""),
           "si falla la revisión SEO automática, los textos quedan y el fallo es solo de la revisión")
        # el nombre del fichero en la subida
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_seo")
        cli.enlace_conectar("studio_seo", ["instagram"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        P.enviar(raiz, dict(info2, mp4=mp4, nombre="Fiesta en casa"), dict(ajustes, perfil="studio_seo"),
                 {"redes": ["instagram"], "modo": "ahora", "confirmado": True}, en_hilo=False)
        with open(simulador, encoding="utf-8") as fh:
            subida = json.load(fh)["subidas"][-1]
        igual(subida["fichero"], "alquiler-de-consolas-en-lima-fiesta-en-casa.mp4",
              "el MP4 se sube con el nombre de la palabra clave")
        igual(subida["campos"].get("location_id"), "106042326099451", "y con la ubicación de Instagram")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_notas_19oct():
    """Las notas del dueño del 19-10 en Publicar: UNA nota SEO con un id por
    punto, la revisión de Claude sin nota propia y sin repetir la del Studio,
    los hashtags que no caben se dicen (y no se cortan a 15), y un fallo que
    ya salió en otro envío deja de contar en la cola."""
    seccion("10] notas del 19-10: una nota SEO, hashtags que no caben, fallos superados")
    S = P.SEO
    raiz = os.path.join(CARPETA, "notas19")
    os.makedirs(raiz)
    # --- la nota: cada punto con su id, y dónde se pone cada cosa con su nombre de verdad
    textos = {"descripcion": "Una fiesta increíble\nTe lo llevamos.", "cta": "",
              "hashtags": ["fiesta", "consolas", "lima", "gaming", "cumple"]}
    n = S.nota("instagram", textos, {}, dict(P.AJUSTES_DEFECTO, zona="Lima"), {}, INFO, "")
    ids = {x.get("id"): x for x in n["puntos"]}
    ok(all(x.get("id") for x in n["puntos"]), f"cada punto de la nota lleva su id: {sorted(ids)}")
    ok({"palabra", "ubicacion", "portada", "cta"} <= {i for i, x in ids.items() if not x["ok"]},
       "sin palabra clave, ubicación, portada ni CTA: los cuatro restan con su id")
    ok({"hashtags", "hashtags_vacios", "hashtags_repetidos", "hashtag_local", "primera_linea"} <= set(ids),
       "y los demás puntos también llevan el suyo")
    ok(all("Lo fijo" not in x["texto"] for x in n["puntos"])
       and "Cuentas y ajustes → SEO de este proyecto" in ids["ubicacion"]["texto"]
       and "Cuentas y ajustes → SEO de este proyecto" in ids["palabra"]["texto"],
       "dónde se pone la ubicación y la palabra clave, con el nombre real de la pantalla")
    con = S.nota("youtube", dict(textos, titulo="Fiesta"), {}, P.AJUSTES_DEFECTO, {}, INFO, "consolas en Lima")
    ok({"palabra_titulo", "palabra_primera", "palabra_descripcion", "titulo_largo"} <=
       {x.get("id") for x in con["puntos"]}, "con palabra clave: título, primera línea y descripción, cada uno el suyo")
    # --- lo que se pide a Claude: sin nota suya, con la palabra clave del vídeo
    ok('"nota"' not in S.INSTRUCCION_OPTIMIZAR and "0-100" not in S.INSTRUCCION_OPTIMIZAR,
       "a Claude ya no se le pide una nota propia")
    ok('"palabra_clave"' in S.INSTRUCCION_OPTIMIZAR, "y sí la palabra clave para este vídeo")
    norm = S.normalizar_optimizacion({"instagram": {"nota": 80, "fallos": ["x"], "campos": {}}}, ["instagram"])
    ok("nota" not in norm["instagram"], "si Claude la pone igual, no se guarda")
    # --- «Optimizar»: lo que repite de la nota no sale, la palabra y «con estos cambios»
    ajustes = dict(P.AJUSTES_DEFECTO, palabra_clave="alquiler de consolas en Lima")
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        info = dict(INFO, pid="n19")
        P.guardar_ficha(raiz, "n19", {"textos": {"instagram": {
            "descripcion": "Texto mío sin la palabra", "cta": "Ven", "hashtags": ["lima"]}}})
        original = P._optimizar_simulado

        def con_palabra(datos_video, redes):
            # el doble de siempre, con un texto que SÍ dice la palabra clave
            respuesta, sobre = original(datos_video, redes)
            bruto = json.loads(respuesta)
            bruto["instagram"]["nota"] = 80               # una nota suya, por si la pone
            bruto["instagram"]["campos"]["descripcion"]["despues"] = "Alquiler de consolas en Lima para tu fiesta"
            return json.dumps(bruto, ensure_ascii=False), sobre
        P._optimizar_simulado = con_palabra
        try:
            P.lanzar_optimizar(raiz, info, ["instagram"], ajustes, en_hilo=False)
        finally:
            P._optimizar_simulado = original
        f = P.ficha(raiz, info, ajustes)
        prop = f["seo"]["propuesta"]["redes"]["instagram"]
        ok("nota" not in prop, "la propuesta guardada no lleva nota de Claude")
        prop.setdefault("fallos", [])
        ok(not any("palabra clave" in x for x in prop["fallos"]),
           f"lo que Claude repite de la nota (la primera línea sin la palabra) no sale dos veces: {prop['fallos']}")
        ok(any("tipo de fiesta" in x for x in prop["fallos"]), "lo que la nota no dice, sí")
        igual(f["seo"]["palabra_propuesta"], "consolas para fiestas en casa",
              "la palabra clave que propone la revisión queda para «Usar»")
        nuevos = dict(f["textos"]["instagram"], **{c: v["despues"] for c, v in prop["campos"].items()})
        datos = P._leer_video(raiz, "n19")
        esperada = S.nota("instagram", nuevos, P.componer("instagram", nuevos, ajustes, info, None, datos),
                          ajustes, datos, info, S.palabra_del_video(datos, ajustes))["nota"]
        igual(f["seo"].get("notas_con_propuesta", {}).get("instagram"), esperada,
              "«con estos cambios»: la nota del Studio sobre los textos propuestos")
        ok(esperada > f["seo"]["notas"]["instagram"]["nota"],
           f"y sube: {f['seo']['notas']['instagram']['nota']} → {esperada}")
        P.guardar_ficha(raiz, "n19", {"aceptar_seo": {"instagram": list(prop["campos"])}})
        igual(P.ficha(raiz, info, ajustes)["seo"].get("notas_con_propuesta"), {},
              "aceptado todo, no queda «con estos cambios»")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)
    # --- hashtags: el tope de cada red, y lo que sobra se dice
    muchos = [f"tag{i}" for i in range(35)]
    f = P.guardar_ficha(raiz, "n19h", {"textos": {"instagram": {"descripcion": "Hola", "hashtags": muchos},
                                                 "tiktok": {"descripcion": "Hola", "hashtags": muchos[:20]},
                                                 "youtube": {"descripcion": "Hola", "hashtags": muchos}}})
    igual(len(f["textos"]["instagram"]["hashtags"]), 35, "guardar no corta los hashtags (antes, a 15 sin decirlo)")
    r = P.componer("instagram", f["textos"]["instagram"], P.AJUSTES_DEFECTO, INFO, None, {})
    igual(len(r["tags"]), 30, "a Instagram van 30, su tope")
    ok(any("5 hashtags no caben en Instagram" in a for a in r["avisos"]),
       f"y los 5 que sobran se dicen: {r['avisos']}")
    r = P.componer("tiktok", f["textos"]["tiktok"], dict(P.AJUSTES_DEFECTO, hashtags="#marca #ciudad"), INFO, None, {})
    ok(len(r["tags"]) == 22 and not any("no cabe" in a for a in r["avisos"]),
       f"20 de la red y 2 fijos del proyecto en TikTok van todos ({len(r['tags'])}; antes se cortaban a 15)")
    r = P.componer("youtube", f["textos"]["youtube"], P.AJUSTES_DEFECTO, dict(INFO, formato="horizontal"), None, {})
    igual(len(r["tags"]), 35, "YouTube admite hasta 60")
    r = P.componer("instagram", dict(f["textos"]["instagram"], hashtags=muchos[:29]),
                   dict(P.AJUSTES_DEFECTO, hashtags="#marca #ciudad"), INFO, None, {})
    ok(any("1 hashtag no cabe en Instagram" in a and "contando los fijos" in a for a in r["avisos"]),
       f"29 de la red y 2 fijos: el que no cabe se dice, contando los fijos ({r['avisos']})")
    t, _c = P.normalizar_textos({"instagram": {"descripcion": "x", "hashtags": muchos}}, ["instagram"])
    igual(len(t["instagram"]["hashtags"]), 30, "lo que escribe Claude se queda en el tope de la red")
    # --- la cola: un fallo que se reenvió y salió ya no te necesita
    ahora = P._iso_lima()

    def envio(i, red, estado):
        return {"id": f"e{i}", "red": red, "estado": estado, "cuando": ahora, "lote": f"l{i}",
                "perfil": "p", "modo": "ahora"}
    datos = P._leer_video(raiz, "n19c")
    datos["envios"] = [envio(1, "instagram", "fallido"), envio(2, "instagram", "publicado"),
                       envio(3, "tiktok", "fallido"), envio(4, "youtube", "publicado"),
                       envio(5, "youtube", "comprobar"), envio(6, "facebook", "fallido"),
                       envio(7, "facebook", "programado"), envio(8, "x", "comprobar"),
                       envio(9, "x", "programado")]
    P._escribir(P._ruta_video(raiz, "n19c"), datos)
    c = P.cola(raiz, [{"pid": "n19c", "nombre": "Cola", "cliente": "", "montado": True}])
    fallidos = sorted(e["id"] for e in c["fallidos"])
    igual(fallidos, ["e3", "e5", "e8"], "«Te necesitan» no cuenta el fallo que luego salió (ni el que va programado), "
          "y sí el que sigue solo o el que falló después de publicar")
    ok(next(e for e in c["envios"] if e["id"] == "e1").get("superado") is True,
       "el superado sigue en la semana, marcado para que la pantalla lo diga")
    igual([next(e for e in c["envios"] if e["id"] == i).get("superado_como") for i in ("e1", "e6")],
          ["salio", "reenviado"], "y dice si salió o solo se volvió a mandar")
    ok(any(e["id"] == "e8" for e in c["fallidos"]),
       "un «comprobar» con otro solo PROGRAMADO detrás sigue en «Te necesitan» (podría salir dos veces)")
    viejo = P._leer_video(raiz, "n19c")
    for e in viejo["envios"]:
        e["cuando"] = "2020-01-06T10:00:00"
    P._escribir(P._ruta_video(raiz, "n19c"), viejo)
    c = P.cola(raiz, [{"pid": "n19c", "nombre": "Cola", "cliente": "", "montado": True}])
    igual(sorted(e["id"] for e in c["envios"]), ["e3", "e5", "e8"],
          "de otra semana solo sale lo que te necesita: el fallo superado, no")
    P.cancelar(raiz, "n19c", "e3")
    igual([e["id"] for e in P.cola(raiz, [{"pid": "n19c", "nombre": "Cola", "cliente": "",
                                          "montado": True}])["fallidos"]], ["e5", "e8"],
          "«Quitar de la lista» lo saca de los fallidos")


# ------------------------------------------- 12. arreglos del 20 de octubre

def prueba_20oct_idioma():
    """El Short no subía: Upload-Post rechaza «es-419» en defaultAudioLanguage."""
    seccion("12a] 20-10: el idioma del audio de YouTube va como lo acepta Upload-Post")
    tabla = {"es-419": "es-US", "es": "es-ES", "en": "en-US", "pt": "pt-BR", "pt-br": "pt-BR",
             "es-ES": "es-ES", "es-MX": "es-MX", "en-US": "en-US", "es_us": "es-US",
             "": "", "xx-1-2": "", "español": ""}
    traducir = getattr(UP, "idioma_audio_youtube", None)
    para_enviar = getattr(UP, "campos_para_enviar", None)
    ok(traducir and para_enviar, "el cliente tiene UN sitio que traduce el idioma antes de mandar")
    if traducir and para_enviar:
        for entrada, esperado in tabla.items():
            igual(traducir(entrada), esperado, f"«{entrada}» se manda como «{esperado}»")
        campos = para_enviar({"defaultAudioLanguage": "es-419", "defaultLanguage": "es"})
        igual(campos, {"defaultAudioLanguage": "es-US", "defaultLanguage": "es"},
              "solo cambia el idioma del AUDIO (el del título sigue en «es», que sí vale)")
        ok("defaultAudioLanguage" not in para_enviar({"defaultAudioLanguage": "klingon"}),
           "lo que no se sabe traducir no se manda (sin él YouTube lo deduce; con uno malo falla todo)")
    forma = getattr(UP, "FORMA_IDIOMA_AUDIO", None) or __import__("re").compile(r"^[a-z]{2}-[A-Z]{2}$")
    ok(all(forma.match(c) for c, _n in P.SEO.IDIOMAS_AUDIO),
       "todo lo que se puede elegir en la pantalla tiene la forma idioma-PAÍS")
    igual(P.SEO.AJUSTES_SEO["yt_idioma_audio"], "es-US", "y lo de fábrica también")
    try:
        igual(P.SEO.validar("yt_idioma_audio", "es-419"), "es-US",
              "un «es-419» que llegue de antes se guarda ya traducido")
    except P.SEO.ErrorSeo as fallo:
        ok(False, f"un «es-419» que llegue de antes se guarda ya traducido: {fallo}")

    # el cliente DE VERDAD, contra el Upload-Post falso: lo que sale por el cable
    puerto = puerto_libre()
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), _FalsoUploadPost)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        cli = UP.ClienteUploadPost(_FalsoUploadPost.clave, base=f"http://127.0.0.1:{puerto}")
        mp4 = os.path.join(CARPETA, "idioma.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 5000)
        ajustes_viejos = dict(P.AJUSTES_DEFECTO, yt_idioma_audio="es-419")   # guardado antes del 20-10
        comp = P.componer("youtube", {"titulo": "Short", "descripcion": "Hola"}, ajustes_viejos, INFO)
        cli.publicar("studio_b", ["youtube"], mp4, comp["campos"], id_propio="idioma1")
        cuerpo = _FalsoUploadPost.vistas[-1]["cuerpo"]
        ok(b"es-419" not in cuerpo, "al cable de Upload-Post no sale nunca «es-419»")
        ok(b'name="defaultAudioLanguage"\r\n\r\nes-US' in cuerpo, "sale «es-US»")
    finally:
        servidor.shutdown()

    # y el Studio entero con el simulador, que contesta lo mismo que Upload-Post
    raiz = os.path.join(CARPETA, "idioma20")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_idioma20.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    try:
        sim = P.cliente(raiz)
        sim.crear_perfil("studio_i")
        sim.enlace_conectar("studio_i", ["youtube"])
        info = dict(INFO, pid="idioma", mp4=mp4, mp4_huella="i1")
        P.guardar_ficha(raiz, "idioma", {"textos": {"youtube": {"titulo": "Fiesta", "descripcion": "Hola"}}})
        P.enviar(raiz, info, dict(ajustes_viejos, perfil="studio_i"),
                 {"redes": ["youtube"], "modo": "ahora", "confirmado": True}, en_hilo=False)
        envio = P._leer_video(raiz, "idioma")["envios"][-1]
        ok(envio["estado"] != "fallido", f"el Short sale (estado {envio['estado']}, {envio.get('error')})")
        with open(simulador, encoding="utf-8") as fh:
            igual(json.load(fh)["subidas"][-1]["campos"].get("defaultAudioLanguage"), "es-US",
                  "y lo que recibe Upload-Post es «es-US»")
    finally:
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_20oct_short():
    """Short frente a vídeo largo: antes salían igual (mismo texto, sin #Shorts)."""
    seccion("12b] 20-10: Short o vídeo normal en YouTube")
    vert = dict(INFO, formato="vertical", duracion_s=45)
    largo_v = dict(INFO, formato="vertical", duracion_s=240)
    horiz = dict(INFO, formato="horizontal", duracion_s=300)
    e = P.encaje("youtube", "vertical", 45)
    igual((e["tipo"], e["nivel"], e.get("puede_elegir")), ("Short", "ok", True),
          "vertical de 45 s: Short, y como es vertical se puede elegir")
    e = P.encaje("youtube", "horizontal", 300)
    igual((e["tipo"], e.get("puede_elegir")), ("vídeo", False), "horizontal: vídeo normal, sin elegir")
    e = P.encaje("youtube", "vertical", 240)
    igual((e["tipo"], e["nivel"], e.get("puede_elegir")), ("vídeo", "aviso", True),
          "vertical de 4 min: vídeo normal, con aviso, y se puede elegir (el caso dudoso)")
    try:
        e = P.encaje("youtube", "vertical", 240, "short")
        igual((e["tipo"], e["nivel"]), ("Short", "aviso"), "elegido Short con 4 min: Short, avisando de YouTube")
        ok("3 minutos" in e["texto"], f"y dice por qué: {e['texto']}")
        e = P.encaje("youtube", "vertical", 45, "video")
        igual((e["tipo"], e["nivel"]), ("vídeo", "aviso"), "elegido vídeo con 45 s: vídeo, avisando")
        e = P.encaje("youtube", "horizontal", 300, "short")
        igual(e["tipo"], "vídeo", "un horizontal nunca es Short, se elija lo que se elija")
    except TypeError:
        ok(False, "encaje acepta lo elegido en la ficha (Short o vídeo)")
    caps = [{"t": 0, "titulo": "Intro"}, {"t": 60, "titulo": "Juegos"}, {"t": 120, "titulo": "Precios"}]
    textos = {"titulo": "Consolas para tu fiesta", "descripcion": "Llega la fiesta", "hashtags": ["lima"]}
    short = P.componer("youtube", textos, P.AJUSTES_DEFECTO, vert, caps, {})
    igual(short["campos"]["youtube_title"], "Consolas para tu fiesta #Shorts", "el Short lleva #Shorts en el título")
    ok("0:00 Intro" not in short["campos"]["youtube_description"], "y ningún capítulo")
    normal = P.componer("youtube", textos, P.AJUSTES_DEFECTO, horiz, caps, {})
    ok("#Shorts" not in normal["campos"]["youtube_title"] + normal["campos"]["youtube_description"],
       "el vídeo normal no lleva #Shorts")
    ok("0:00 Intro" in normal["campos"]["youtube_description"], "y sí sus capítulos")
    elegido = P.componer("youtube", textos, P.AJUSTES_DEFECTO, largo_v, caps, {"youtube_formato": "short"})
    ok("#Shorts" in elegido["campos"]["youtube_title"] and "0:00 Intro" not in elegido["campos"]["youtube_description"],
       "un vertical largo elegido como Short sale como Short (con #Shorts y sin capítulos)")
    marcar = getattr(P, "marcar_short", None)
    ok(marcar is not None, "hay una pieza que pone «#Shorts»")
    if marcar:
        t, d = marcar("x" * 95, "Texto")
        igual((t, d), ("x" * 95, "Texto\n\n#Shorts"), "si no cabe en el título, va al final de la descripción")
        igual(marcar("Hola #shorts", "Texto"), ("Hola #shorts", "Texto"), "y nunca dos veces")
    inst_s = P.instruccion_textos(vert, ["youtube"], P.AJUSTES_DEFECTO)
    inst_v = P.instruccion_textos(horiz, ["youtube"], P.AJUSTES_DEFECTO)
    ok("SHORT" in inst_s and "30 a 60" in inst_s, "a Claude se le piden textos de Short para un Short")
    ok("40 a 70" in inst_v and "30 a 60" not in inst_v, "y de vídeo largo para un vídeo")
    # la ficha guarda lo elegido y lo usa
    raiz = os.path.join(CARPETA, "short20")
    os.makedirs(raiz)
    try:
        P.guardar_ficha(raiz, "corto", {"youtube_formato": "video"})
        ok(True, "la ficha guarda «youtube_formato»")
    except P.ErrorPublicar as fallo:
        ok(False, f"la ficha guarda «youtube_formato»: {fallo}")
    f = P.ficha(raiz, dict(vert, pid="corto"), P.AJUSTES_DEFECTO)
    igual((f["encaje"]["youtube"]["tipo"], f.get("youtube_formato")), ("vídeo", "video"),
          "y la ficha lo enseña: vídeo normal")
    try:
        P.guardar_ficha(raiz, "corto", {"youtube_formato": "reel"})
        ok(False, "un formato que no existe se rechaza")
    except P.ErrorPublicar:
        ok(True, "un formato que no existe se rechaza")
    P.guardar_ficha(raiz, "corto", {"youtube_formato": "auto"})
    ok("youtube_formato" not in P._leer_video(raiz, "corto"), "«auto» no deja nada escrito (lo de siempre)")


def prueba_20oct_programado():
    """Lo programado que ya salió seguía «programado» (a las 12:22, los de las 09:00)."""
    seccion("12c] 20-10: lo programado cuya hora pasó se pregunta y cambia de estado")
    raiz = os.path.join(CARPETA, "prog20")
    os.makedirs(raiz)
    simulador = os.path.join(CARPETA, "sim_prog20.json")
    os.environ["ESTUDIO_UPLOADPOST_SIMULADO"] = simulador
    respiro = P.RESPIRO_CONSULTA_S
    try:
        cli = P.cliente(raiz)
        cli.crear_perfil("studio_p")
        cli.enlace_conectar("studio_p", ["tiktok", "youtube"])
        mp4 = os.path.join(raiz, "v.mp4")
        with open(mp4, "wb") as fh:
            fh.write(b"0" * 2000)
        info = dict(INFO, pid="prog", mp4=mp4, mp4_huella="p1")
        ajustes = dict(P.AJUSTES_DEFECTO, perfil="studio_p")
        P.guardar_ficha(raiz, "prog", {"textos": {"tiktok": {"descripcion": "Hola"},
                                                  "youtube": {"titulo": "T", "descripcion": "Hola"}}})
        luego = (P.ahora_lima() + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        nuevos = P.enviar(raiz, info, ajustes, {"redes": ["tiktok", "youtube"], "modo": "programar",
                                                "cuando": luego, "confirmado": True}, en_hilo=False)
        envios = P._leer_video(raiz, "prog")["envios"]
        igual(sorted(e["estado"] for e in envios), ["programado", "programado"], "programados para dentro de 2 h")
        c = P.cola(raiz, [{"pid": "prog", "nombre": "Prog", "montado": True}])
        ok(all(e.get("debio_salir") is False for e in c["envios"]), "a su hora todavía no: no «debió salir»")
        # pasa el tiempo: la hora era las 09:00 y son las 12:22 (en el almacén y en el simulador)
        hace = P.ahora_lima() - dt.timedelta(hours=3, minutes=22)
        for lote in {e["lote"] for e in nuevos}:
            P._actualizar_lote(raiz, "prog", lote, lambda e: e.update(cuando=hace.strftime("%Y-%m-%dT%H:%M:%S")))
        with open(simulador, encoding="utf-8") as fh:
            sim = json.load(fh)
        for t in sim["trabajos"].values():
            t["cuando_utc"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).isoformat()
        with open(simulador, "w", encoding="utf-8") as fh:
            json.dump(sim, fh)
        c = P.cola(raiz, [{"pid": "prog", "nombre": "Prog", "montado": True}])
        ok(c["envios"] and all(e.get("debio_salir") for e in c["envios"]),
           "pasada su hora, la cola dice que DEBIÓ salir (la pantalla: «debería haber salido a las …»)")
        f = P.ficha(raiz, info, ajustes)
        ok(all(e.get("debio_salir") for e in f["envios"]), "y la ficha también")
        # «Comprobar»: ese lote, ya, sin esperar el respiro
        P.RESPIRO_CONSULTA_S = 3600
        lote = nuevos[0]["lote"]
        try:
            r1 = P.refrescar(raiz, lote=lote)
            r2 = P.refrescar(raiz, lote=lote)
            ok(r1["consultados"] == 1 and r2["consultados"] == 1,
               f"«Comprobar» pregunta ya, aunque se acabe de preguntar: {r1} {r2}")
            igual(r2.get("estados"), ["publicado"], "y dice cómo quedó: publicado")
        except TypeError:
            ok(False, "«Comprobar» pregunta por un envío concreto (refrescar con lote)")
        P.RESPIRO_CONSULTA_S = 0
        for _ in range(3):
            P.refrescar(raiz)
        envios = P._leer_video(raiz, "prog")["envios"]
        igual(sorted(e["estado"] for e in envios), ["publicado", "publicado"], "las dos redes pasan a publicado")
        ok(all(e.get("url") for e in envios), "con su enlace")
        # uno programado del que Upload-Post no sabe nada: «comprobar», nunca «programado» para siempre
        datos = P._leer_video(raiz, "prog")
        datos["envios"].append({"id": "fantasma", "red": "facebook", "lote": "lote_fantasma",
                                "estado": "programado", "modo": "programado", "job_id": "no_existe",
                                "cuando": hace.strftime("%Y-%m-%dT%H:%M:%S"),
                                "creado": hace.strftime("%Y-%m-%dT%H:%M:%S"), "mp4_huella": "p1"})
        P._escribir(P._ruta_video(raiz, "prog"), datos)
        for _ in range(P.VECES_NO_LO_CONOCE + 1):
            P._ULTIMA_CONSULTA.pop("lote_fantasma", None)
            P.refrescar(raiz)
        fantasma = next(e for e in P._leer_video(raiz, "prog")["envios"] if e["id"] == "fantasma")
        igual(fantasma["estado"], "comprobar",
              "si Upload-Post no da su estado, pasa a «comprobar» (no sigue «programado»)")
        ok("debería haber salido" in (fantasma.get("error") or ""), f"y lo dice: {fantasma.get('error')}")
        try:
            P.enviar(raiz, info, ajustes, {"redes": ["facebook"], "modo": "ahora", "confirmado": True},
                     en_hilo=False)
            ok(False, "y no se deja publicar otra vez sin preguntar")
        except P.ErrorPublicar:
            ok(True, "y no se deja publicar otra vez sin preguntar")
    finally:
        P.RESPIRO_CONSULTA_S = respiro
        os.environ.pop("ESTUDIO_UPLOADPOST_SIMULADO", None)


def prueba_portada_mandada():
    """portadas-2 (21-10): el envío dice qué portada se mandó a cada red, para
    saber si la que no salió es cosa de aquí o de la red."""
    seccion("4g] qué portada se mandó a cada red (portadas-2)")
    import publicar as P
    ok(P.portada_mandada("instagram", {}, [("cover_image", "/x.jpg")]) == "tu imagen de portada",
       "Instagram con imagen: «tu imagen de portada»")
    ok("segundo 3,5" in P.portada_mandada("instagram", {"thumb_offset": "3500"}, []), "o el fotograma, en segundos")
    ok("cover_image" in P.portada_mandada("tiktok", {}, [("tiktok_cover_image", "/x.jpg")]),
       "TikTok con imagen avisa de que necesita el permiso «cover_image»")
    ok("verificado" in P.portada_mandada("youtube", {}, [("thumbnail", "/x.jpg")]), "YouTube, del canal verificado")
    ok(P.portada_mandada("youtube", {}, []) == "" and P.portada_mandada("facebook", {}, []) == "",
       "sin nada, vacío: la puso la red")
    ok(P.portada_mandada("linkedin", {}, []) is None, "una red sin portada no dice «ninguna»: no dice nada")
    ok("portada" in P._envio_publico_campos({"portada": "tu imagen de portada"}),
       "y la ficha del envío lo enseña")


def main():
    print("PRUEBA DE PUBLICAR")
    prueba_piezas()
    prueba_cliente()
    prueba_envios_sueltos()
    prueba_metricas()
    prueba_metricas_auto()
    prueba_redes_nuevas()
    prueba_informe()
    prueba_titulo_completo()
    prueba_retencion_y_resumenes()
    prueba_perfiles()
    prueba_textos()
    prueba_seo()
    prueba_notas_19oct()
    prueba_emojis()
    prueba_20oct_idioma()
    prueba_20oct_short()
    prueba_20oct_programado()
    prueba_portada_mandada()
    if shutil.which("ffmpeg"):
        prueba_portada()
    if shutil.which("ffmpeg"):
        prueba_studio()
    else:
        print("\n[5] OMITIDA: falta ffmpeg para hacer un MP4 de prueba")
    shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PUBLICAR OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

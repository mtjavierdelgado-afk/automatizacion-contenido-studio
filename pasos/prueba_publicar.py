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
                        ({"marcar_ia": "si"}, "marcar_ia"), ({"perfil": "a b"}, "perfil"),
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
        r = cli.publicar("studio_b", ["tiktok", "youtube", "x"], mp4,
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
        igual(e["redes"]["tiktok"], {"estado": "publicado", "url": "https://tiktok.com/v/1", "error": ""},
              "estado: publicado con su enlace")
        igual(e["redes"]["youtube"]["estado"], "fallido", "y la red que falló, fallida")
        igual(e["redes"]["youtube"]["error"], "quota", "con el motivo")
        igual(cli.estado(request_id="req_1")["redes"]["tiktok"]["estado"], "procesando",
              "un envío a medias está procesando")
        igual(cli.cancelar("job_9"), {"ok": True}, "cancelar")
        igual(_FalsoUploadPost.vistas[-1]["ruta"], "/api/uploadposts/schedule/job_9",
              "con DELETE a la ruta del trabajo")

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
    seccion("4] el Studio por HTTP, con Upload-Post simulado")
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
        igual(f["redes"], list(P.REDES), "de fábrica, las cuatro redes")
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

        # --- proyecto con clave
        r = s.post(base + "/api/clientes", json={"nombre": "Cliente secreto"})
        cid = r.json()["cliente"]["id"]
        r = s.post(base + f"/api/publicar/proyectos/{cid}/perfil", json={"perfil": perfil})
        igual(r.status_code, 409, "un proyecto no puede adoptar el perfil de otro")
        igual(s.put(base + f"/api/publicar/proyectos/{cid}", json={"perfil": perfil}).status_code, 409,
              "ni escribiéndolo a mano")
        s.put(base + f"/api/clientes/{cid}", json={"clave": "1234"})
        s.put(base + "/api/clientes/videos/fiesta", json={"cliente": cid})
        igual(s.get(base + "/api/publicar/videos/fiesta").status_code, 404,
              "un vídeo de un proyecto con clave no se ve sin abrirlo")
        c = s.get(base + "/api/publicar/cola").json()
        ok(all(v["pid"] != "fiesta" for v in c["listos"]), "ni en la cola")
        ok(all(p["id"] != cid for p in s.get(base + "/api/publicar/proyectos").json()["proyectos"]),
           "ni sus ajustes")
        pase = s.post(base + f"/api/clientes/{cid}/abrir", json={"clave": "1234"}).json()["pase"]
        cab = {"X-Estudio-Abiertos": f"{cid}.{pase}"}
        igual(s.get(base + "/api/publicar/videos/fiesta", headers=cab).status_code, 200,
              "con el proyecto abierto, sí")
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


def main():
    print("PRUEBA DE PUBLICAR")
    prueba_piezas()
    prueba_cliente()
    prueba_envios_sueltos()
    if shutil.which("ffmpeg"):
        prueba_studio()
    else:
        print("\n[4] OMITIDA: falta ffmpeg para hacer un MP4 de prueba")
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

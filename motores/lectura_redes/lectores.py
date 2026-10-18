"""Las tres fuentes para leer los vídeos públicos de una cuenta AJENA.

    youtube(clave, usuario, cuantos)                     YouTube Data API v3 (gratis)
    instagram(token, ig_id, usuario, cuantos, version)   Business Discovery de Meta (gratis)
    apify(token, red, usuario, cuantos)                  Apify, de pago (TikTok, y respaldo)
    instagram_mi_cuenta(token, version)                  qué cuenta profesional da ese token

Todas devuelven lo mismo:

    {"red", "usuario", "nombre", "seguidores", "fuente", "coste_usd",
     "videos": [{"id", "url", "texto", "fecha", "vistas", "me_gusta",
                 "comentarios", "compartidos", "duracion_s", "transcripcion"}]}

y lanzan `ErrorLectura(mensaje, motivo)`, donde `motivo` es lo que decide si se
prueba la siguiente fuente:

    sin_clave        no hay clave de esa fuente
    no_profesional   Instagram: la cuenta no es profesional (Business Discovery no la ve)
    no_encontrada    la cuenta no existe o es privada
    limite           cupo o crédito agotado
    clave            la clave no vale
    red              no se ha podido hablar con el servicio

Por qué estas tres y no otras: documento `estado/analizar_cuentas_ajenas_2026-10-18.md`
del Proyecto. El resumen: OAuth («iniciar sesión con…») solo da los datos de la
cuenta que inicia sesión; YouTube y Business Discovery son las dos vías oficiales
para ver cuentas ajenas, y para TikTok no hay ninguna al alcance de un negocio.

LO QUE ESTE MÓDULO NO HACE (como todo motor, `motores/README.md`)
- No lee claves de ningún sitio: llegan como argumento.
- Nunca pone una clave en un mensaje de error (`_tachar`).
- No guarda nada en disco ni decide si se paga: eso es `pasos/cuentas_ajenas.py`.

LOS CAMPOS DE APIFY NO ESTÁN MEDIDOS con una clave de verdad (18-10-2026): los
nombres salen de la documentación de cada actor, y el mapeo (`_primero`) prueba
varios nombres por campo. Si un actor cambia de nombres, se arregla aquí.
"""
import http.client
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

PLAZO_S = 30
#: Apify ejecuta el actor y espera: una cuenta tarda de 20 s a 2 min.
PLAZO_APIFY_S = 280
VERSION_META = "v23.0"

#: Los actores de Apify por red. Precio aproximado por cada 1.000 resultados
#: (sus páginas, 10-2026), para el tope de gasto: se usa el más caro del rango.
ACTORES = {
    "tiktok": ("clockworks~tiktok-scraper", 1.70),
    "instagram": ("apify~instagram-reel-scraper", 2.60),
    "youtube": ("streamers~youtube-scraper", 5.00),
}

BASE_YOUTUBE = "https://www.googleapis.com/youtube/v3"
BASE_META = "https://graph.facebook.com"
BASE_APIFY = "https://api.apify.com/v2"


class ErrorLectura(RuntimeError):
    """`cobrado`: en Apify, si el fallo llega DESPUÉS de que el actor corriera
    (un plazo vencido, un 5xx, resultados sin ningún vídeo): Apify ya ha
    cobrado y el gasto se tiene que apuntar igual. Solo un token malo o sin
    crédito no cobra."""

    def __init__(self, mensaje, motivo="red", cobrado=False, resultados=0):
        super().__init__(mensaje)
        self.motivo = motivo
        self.cobrado = cobrado
        self.resultados = resultados


def _tachar(texto, *claves):
    texto = str(texto or "")
    for clave in claves:
        clave = str(clave or "")
        if len(clave) >= 6:
            texto = texto.replace(clave, "…" + clave[-4:])
            texto = texto.replace(urllib.parse.quote(clave, safe=""), "…" + clave[-4:])
    return texto


def _pedir(url, metodo="GET", cuerpo=None, plazo=PLAZO_S, claves=(), bases=None, cabeceras_extra=None):
    """-> (codigo, json). Los errores HTTP devuelven su cuerpo; la red lanza.

    Las claves van en CABECERAS (`cabeceras_extra`), no en la URL: una URL
    acaba en los registros de cualquier proxy por el que pase."""
    datos = None
    cabeceras = {"Accept": "application/json", "User-Agent": "AutomatizacionContenidoStudio/1"}
    cabeceras.update(cabeceras_extra or {})
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    if bases:
        for antigua, nueva in bases.items():
            if url.startswith(antigua):
                url = nueva + url[len(antigua):]
    peticion = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=plazo) as respuesta:
            crudo = respuesta.read()
            codigo = respuesta.status
    except urllib.error.HTTPError as fallo:
        crudo = fallo.read() or b""
        codigo = fallo.code
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
            http.client.HTTPException, OSError) as fallo:
        raise ErrorLectura(_tachar(f"no se ha podido hablar con el servicio: {fallo}", *claves), "red") from None
    try:
        return codigo, json.loads(crudo.decode("utf-8") or "null")
    except ValueError:
        return codigo, {"_crudo": _tachar(crudo[:300].decode("utf-8", "replace"), *claves)}


def _entero(valor):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _primero(d, *claves):
    """El primer valor que exista, mirando claves con puntos («authorMeta.fans»)."""
    for clave in claves:
        actual = d
        for parte in clave.split("."):
            actual = actual.get(parte) if isinstance(actual, dict) else None
            if actual is None:
                break
        if actual not in (None, ""):
            return actual
    return None


def _duracion_iso(texto):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(texto or ""))
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _duracion(valor):
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor or "")
    if texto.startswith("P"):
        return _duracion_iso(texto)
    partes = texto.split(":")
    if all(p.isdigit() for p in partes) and partes != [""]:
        total = 0
        for p in partes:
            total = total * 60 + int(p)
        return float(total)
    return None


def _video(id_, url, texto, fecha, vistas=None, me_gusta=None, comentarios=None,
           compartidos=None, duracion_s=None, transcripcion=""):
    return {"id": str(id_ or ""), "url": str(url or ""), "texto": str(texto or "")[:2200],
            "fecha": str(fecha or ""), "vistas": _entero(vistas), "me_gusta": _entero(me_gusta),
            "comentarios": _entero(comentarios), "compartidos": _entero(compartidos),
            "duracion_s": duracion_s, "transcripcion": str(transcripcion or "")[:4000]}


# ------------------------------------------------------------------ YouTube

def youtube(clave, usuario, cuantos=30, bases=None):
    """Canal por @handle o por id (UC…). Cuesta 3 unidades de las 10.000 diarias
    gratis: no usa `search.list`, que va aparte y con tope."""
    if not clave:
        raise ErrorLectura("falta la clave de YouTube", "sin_clave")
    usuario = str(usuario or "").strip()
    cuantos = max(1, min(int(cuantos or 30), 50))
    parametros = {"part": "snippet,statistics,contentDetails"}
    cab = {"X-Goog-Api-Key": clave}
    if re.fullmatch(r"UC[\w-]{22}", usuario):
        parametros["id"] = usuario
    else:
        parametros["forHandle"] = "@" + usuario.lstrip("@")
    codigo, datos = _pedir(f"{BASE_YOUTUBE}/channels?{urllib.parse.urlencode(parametros)}",
                           claves=(clave,), bases=bases, cabeceras_extra=cab)
    _error_google(codigo, datos, clave)
    canales = (datos or {}).get("items") or []
    if not canales:
        raise ErrorLectura(f"no hay ningún canal de YouTube «{usuario}»", "no_encontrada")
    canal = canales[0]
    subidas = (((canal.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads"))
    if not subidas:
        raise ErrorLectura(f"el canal «{usuario}» no tiene vídeos subidos", "no_encontrada")
    codigo, datos = _pedir(f"{BASE_YOUTUBE}/playlistItems?" + urllib.parse.urlencode(
        {"part": "contentDetails", "playlistId": subidas, "maxResults": cuantos}),
        claves=(clave,), bases=bases, cabeceras_extra=cab)
    _error_google(codigo, datos, clave)
    ids = [((i.get("contentDetails") or {}).get("videoId")) for i in (datos or {}).get("items") or []]
    ids = [i for i in ids if i]
    videos = []
    if ids:
        codigo, datos = _pedir(f"{BASE_YOUTUBE}/videos?" + urllib.parse.urlencode(
            {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)}),
            claves=(clave,), bases=bases, cabeceras_extra=cab)
        _error_google(codigo, datos, clave)
        for v in (datos or {}).get("items") or []:
            sn, st = v.get("snippet") or {}, v.get("statistics") or {}
            texto = (sn.get("title") or "") + ("\n" + sn["description"] if sn.get("description") else "")
            videos.append(_video(v.get("id"), f"https://www.youtube.com/watch?v={v.get('id')}", texto,
                                 sn.get("publishedAt"), st.get("viewCount"), st.get("likeCount"),
                                 st.get("commentCount"), None,
                                 _duracion_iso((v.get("contentDetails") or {}).get("duration"))))
    sn, st = canal.get("snippet") or {}, canal.get("statistics") or {}
    return {"red": "youtube", "usuario": usuario.lstrip("@"), "nombre": sn.get("title") or usuario,
            "seguidores": _entero(st.get("subscriberCount")), "fuente": "youtube_api",
            "coste_usd": 0.0, "videos": videos}


def _error_google(codigo, datos, clave):
    if codigo < 400:
        return
    error = (datos or {}).get("error") or {}
    razon = " ".join(str(e.get("reason") or "") for e in error.get("errors") or [])
    mensaje = _tachar(str(error.get("message") or datos)[:300], clave)
    if "quota" in razon.lower():
        raise ErrorLectura("se ha acabado el cupo diario de YouTube (vuelve mañana)", "limite")
    if codigo in (400, 403) and ("key" in razon.lower() or "API key" in mensaje):
        raise ErrorLectura(f"la clave de YouTube no vale: {mensaje}", "clave")
    raise ErrorLectura(f"YouTube ha contestado {codigo}: {mensaje}", "red")


# ---------------------------------------------------------------- Instagram

def instagram(token, ig_id, usuario, cuantos=30, version=VERSION_META, bases=None):
    """Business Discovery: los Reels y posts de una cuenta PROFESIONAL ajena,
    con `view_count` (las vistas de sus Reels), vista desde la tuya."""
    if not token or not ig_id:
        raise ErrorLectura("falta el token de Meta o el id de tu cuenta de Instagram", "sin_clave")
    usuario = str(usuario or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", usuario):
        raise ErrorLectura(f"«{usuario}» no es un usuario de Instagram", "no_encontrada")
    cuantos = max(1, min(int(cuantos or 30), 50))
    campos = (f"business_discovery.username({usuario}){{username,name,followers_count,media_count,"
              f"media.limit({cuantos}){{id,caption,like_count,comments_count,view_count,timestamp,"
              f"permalink,media_type,media_product_type}}}}")
    url = (f"{BASE_META}/{version}/{urllib.parse.quote(str(ig_id))}?"
           + urllib.parse.urlencode({"fields": campos}))
    codigo, datos = _pedir(url, claves=(token,), bases=bases, cabeceras_extra={"Authorization": f"Bearer {token}"})
    if codigo >= 400 or (isinstance(datos, dict) and datos.get("error")):
        error = (datos or {}).get("error") or {}
        mensaje = _tachar(str(error.get("message") or datos)[:300], token)
        cod = error.get("code")
        if cod == 190:
            raise ErrorLectura(f"el token de Meta no vale o ha caducado: {mensaje}", "clave")
        if cod in (4, 17, 32, 613):
            raise ErrorLectura("Meta pide esperar (límite de consultas)", "limite")
        if cod == 110 or "business" in mensaje.lower() or "username" in mensaje.lower():
            raise ErrorLectura(f"Instagram no da los datos de @{usuario} por la vía oficial: no es "
                               "una cuenta profesional, es privada o no existe", "no_profesional")
        raise ErrorLectura(f"Meta ha contestado {codigo}: {mensaje}", "red")
    bd = (datos or {}).get("business_discovery") or {}
    videos = []
    for m in ((bd.get("media") or {}).get("data") or []):
        videos.append(_video(m.get("id"), m.get("permalink"), m.get("caption"), m.get("timestamp"),
                             m.get("view_count"), m.get("like_count"), m.get("comments_count")))
        videos[-1]["tipo"] = str(m.get("media_product_type") or m.get("media_type") or "")
    return {"red": "instagram", "usuario": bd.get("username") or usuario, "nombre": bd.get("name") or usuario,
            "seguidores": _entero(bd.get("followers_count")), "fuente": "instagram_oficial",
            "coste_usd": 0.0, "videos": videos}


def instagram_mi_cuenta(token, version=VERSION_META, bases=None):
    """[{id, usuario, pagina}] de las cuentas profesionales de Instagram a las
    que llega este token (por las Páginas de Facebook que administra)."""
    if not token:
        raise ErrorLectura("falta el token de Meta", "sin_clave")
    url = (f"{BASE_META}/{version}/me/accounts?" + urllib.parse.urlencode(
        {"fields": "name,instagram_business_account{id,username}"}))
    codigo, datos = _pedir(url, claves=(token,), bases=bases, cabeceras_extra={"Authorization": f"Bearer {token}"})
    if codigo >= 400 or (isinstance(datos, dict) and datos.get("error")):
        mensaje = _tachar(str(((datos or {}).get("error") or {}).get("message") or datos)[:300], token)
        raise ErrorLectura(f"Meta no acepta ese token: {mensaje}", "clave")
    salida = []
    for p in (datos or {}).get("data") or []:
        ig = p.get("instagram_business_account") or {}
        if ig.get("id"):
            salida.append({"id": str(ig["id"]), "usuario": ig.get("username") or "", "pagina": p.get("name") or ""})
    return salida


# -------------------------------------------------------------------- Apify

def entrada_apify(red, usuario, cuantos):
    """Lo que se le manda a cada actor (sus esquemas de entrada, 10-2026)."""
    usuario = str(usuario or "").strip().lstrip("@")
    if red == "tiktok":
        return {"profiles": [usuario], "resultsPerPage": cuantos, "profileScrapeSections": ["videos"],
                "shouldDownloadVideos": False, "shouldDownloadCovers": False}
    if red == "instagram":
        return {"username": [usuario], "resultsLimit": cuantos}
    if red == "youtube":
        handle = usuario if usuario.startswith("UC") else "@" + usuario
        ruta = f"channel/{usuario}" if usuario.startswith("UC") else handle
        return {"startUrls": [{"url": f"https://www.youtube.com/{ruta}/videos"}], "maxResults": cuantos,
                "maxResultsShorts": cuantos}
    raise ErrorLectura(f"el servicio de pago no lee {red}", "no_encontrada")


def leer_items_apify(red, usuario, items):
    """Los resultados de un actor, al formato común (tolerante con los nombres)."""
    videos, nombre, seguidores = [], "", None
    for it in items or []:
        if not isinstance(it, dict) or it.get("error"):
            continue
        if red == "tiktok":
            nombre = nombre or _primero(it, "authorMeta.nickName", "authorMeta.name") or ""
            seguidores = seguidores or _entero(_primero(it, "authorMeta.fans", "authorMeta.followers"))
            videos.append(_video(it.get("id"), _primero(it, "webVideoUrl", "url"), it.get("text"),
                                 _primero(it, "createTimeISO", "createTime"),
                                 _primero(it, "playCount", "stats.playCount"),
                                 _primero(it, "diggCount", "stats.diggCount"),
                                 _primero(it, "commentCount", "stats.commentCount"),
                                 _primero(it, "shareCount", "stats.shareCount"),
                                 _duracion(_primero(it, "videoMeta.duration", "duration"))))
        elif red == "instagram":
            nombre = nombre or _primero(it, "ownerFullName", "ownerUsername") or ""
            videos.append(_video(_primero(it, "id", "shortCode"), it.get("url"), it.get("caption"),
                                 it.get("timestamp"), _primero(it, "videoPlayCount", "videoViewCount", "playCount"),
                                 _primero(it, "likesCount", "likes"), _primero(it, "commentsCount", "comments"),
                                 None, _duracion(_primero(it, "videoDuration", "duration")),
                                 _primero(it, "transcript", "transcription") or ""))
        else:
            nombre = nombre or _primero(it, "channelName", "channel.name") or ""
            seguidores = seguidores or _entero(_primero(it, "numberOfSubscribers", "channel.subscribers"))
            texto = (it.get("title") or "") + ("\n" + it["text"] if it.get("text") else "")
            videos.append(_video(it.get("id"), it.get("url"), texto, _primero(it, "date", "uploadDate"),
                                 _primero(it, "viewCount", "views"), _primero(it, "likes", "likeCount"),
                                 _primero(it, "commentsCount", "commentCount"), None,
                                 _duracion(it.get("duration"))))
    # un resultado sin id ni enlace es que el actor ha cambiado de nombres: no es un vídeo
    videos = [v for v in videos if v["id"] or v["url"]]
    return {"red": red, "usuario": str(usuario).lstrip("@"), "nombre": nombre or str(usuario).lstrip("@"),
            "seguidores": seguidores, "fuente": "apify", "videos": videos}


def coste_apify(red, resultados):
    """Lo que cuesta (aprox.) traer `resultados` vídeos de esa red."""
    _actor, por_mil = ACTORES.get(red, ("", 5.0))
    return round(max(1, resultados) * por_mil / 1000.0, 4)


def apify(token, red, usuario, cuantos=30, bases=None, plazo=PLAZO_APIFY_S, max_usd=None):
    """Ejecuta el actor de esa red y espera sus resultados (de pago).

    `maxItems` y `maxTotalChargeUsd` son el techo DEL LADO DE APIFY: aunque el
    actor quisiera devolver más (el de YouTube cuenta vídeos y Shorts por
    separado), no cobra más de `cuantos` resultados ni más de `max_usd`."""
    if not token:
        raise ErrorLectura("falta el token de Apify", "sin_clave")
    if red not in ACTORES:
        raise ErrorLectura(f"el servicio de pago no lee {red}", "no_encontrada")
    cuantos = max(1, min(int(cuantos or 30), 50))
    actor, _p = ACTORES[red]
    parametros = {"timeout": plazo - 20, "clean": "true", "maxItems": cuantos}
    if max_usd is not None:
        parametros["maxTotalChargeUsd"] = f"{max(0.01, float(max_usd)):.2f}"
    url = f"{BASE_APIFY}/acts/{actor}/run-sync-get-dataset-items?" + urllib.parse.urlencode(parametros)
    try:
        codigo, datos = _pedir(url, "POST", entrada_apify(red, usuario, cuantos), plazo=plazo,
                               claves=(token,), bases=bases,
                               cabeceras_extra={"Authorization": f"Bearer {token}"})
    except ErrorLectura as fallo:
        fallo.cobrado = True               # el actor pudo correr: se apunta igual
        raise
    if codigo in (401, 403):
        raise ErrorLectura("el token de Apify no vale", "clave")
    if codigo == 402:
        raise ErrorLectura("Apify: se ha acabado el crédito de la cuenta", "limite")
    if codigo == 408:
        raise ErrorLectura("Apify ha tardado demasiado: prueba con menos vídeos", "red", cobrado=True)
    if codigo >= 400:
        mensaje = _tachar(str(((datos or {}).get("error") or {}).get("message") or datos)[:300], token)
        raise ErrorLectura(f"Apify ha contestado {codigo}: {mensaje}", "red", cobrado=codigo >= 500)
    items = datos if isinstance(datos, list) else []
    salida = leer_items_apify(red, usuario, items)
    if not salida["videos"]:
        raise ErrorLectura(f"no se ha encontrado ningún vídeo público de «{usuario}» en {red} "
                           "(¿existe?, ¿es privada?)", "no_encontrada", cobrado=bool(items),
                           resultados=len(items))
    salida["coste_usd"] = coste_apify(red, len(items))
    return salida

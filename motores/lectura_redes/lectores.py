"""Las tres fuentes para leer los vídeos públicos de una cuenta AJENA.

    youtube(clave, usuario, cuantos)                     YouTube Data API v3 (gratis)
    instagram(token, ig_id, usuario, cuantos, version)   Business Discovery de Meta (gratis)
    apify(token, red, usuario, cuantos)                  Apify, de pago (TikTok, y respaldo)
    instagram_mi_cuenta(token, version)                  qué cuenta profesional da ese token

Todas devuelven lo mismo:

    {"red", "usuario", "nombre", "seguidores", "fuente", "coste_usd",
     "videos": [{"id", "url", "texto", "fecha", "vistas", "me_gusta",
                 "comentarios", "compartidos", "duracion_s", "transcripcion",
                 "tipo"?, "coautores"?, "media_url"?}]}

`tipo` (rama cuentas-gustan-2) es la clase de publicación ya normalizada: reel,
publicacion, carrusel, video, short, fotos (`TIPOS`). `coautores`, las cuentas
con las que se publicó en colaboración (si la fuente lo dice). `media_url`, el
enlace del vídeo en Instagram por la vía oficial: caduca, solo sirve para medir
su duración con ffprobe al leerla y no se guarda.

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
import time
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

    def __init__(self, mensaje, motivo="red", cobrado=False, resultados=0, coste_usd=None):
        super().__init__(mensaje)
        self.motivo = motivo
        self.cobrado = cobrado
        self.resultados = resultados
        # lo que Apify dice que ha cobrado de verdad (`usageTotalUsd`), si lo dijo
        self.coste_usd = coste_usd


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
    cabeceras = {"Accept": "application/json", "User-Agent": "CrearIAStudio/5.1"}
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
           compartidos=None, duracion_s=None, transcripcion="", tipo="", coautores=None):
    v = {"id": str(id_ or ""), "url": str(url or ""), "texto": str(texto or "")[:2200],
         "fecha": str(fecha or ""), "vistas": _entero(vistas), "me_gusta": _entero(me_gusta),
         "comentarios": _entero(comentarios), "compartidos": _entero(compartidos),
         "duracion_s": duracion_s, "transcripcion": str(transcripcion or "")[:4000]}
    if tipo:
        v["tipo"] = tipo
    coautores = [str(c).lstrip("@")[:60] for c in (coautores or []) if str(c or "").strip()]
    if coautores:
        v["coautores"] = coautores[:10]
    return v


#: Las clases de publicación, ya normalizadas (rama cuentas-gustan-2).
TIPOS = {"reel": "Reel", "publicacion": "Publicación", "carrusel": "Carrusel",
         "video": "Vídeo", "short": "Short", "fotos": "Fotos"}


def tipo_instagram(product_type="", media_type=""):
    """REELS/FEED/STORY y VIDEO/IMAGE/CAROUSEL_ALBUM (vía oficial) o
    clips/Video/Sidecar/Image (Apify) -> una clave de `TIPOS`."""
    p, m = str(product_type or "").lower(), str(media_type or "").lower()
    if p in ("reels", "clips") or m == "clips":
        return "reel"
    if m in ("carousel_album", "sidecar"):
        return "carrusel"
    if m in ("image", "graphimage"):
        return "publicacion"
    if m in ("video", "graphvideo"):
        return "reel" if p != "feed" else "video"
    return ""


def tipo_youtube(url="", texto="", duracion_s=None):
    """Short o vídeo. Un Short dura hasta 3 min, pero un vídeo normal también
    puede: sin «/shorts/» ni «#shorts», solo se afirma con 60 s o menos."""
    if "/shorts/" in str(url or "") or "#shorts" in str(texto or "").lower():
        return "short"
    if isinstance(duracion_s, (int, float)):
        return "short" if duracion_s <= 60 else "video" if duracion_s > 180 else ""
    return ""


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
            duracion = _duracion_iso((v.get("contentDetails") or {}).get("duration"))
            url_v = f"https://www.youtube.com/watch?v={v.get('id')}"
            videos.append(_video(v.get("id"), url_v, texto,
                                 sn.get("publishedAt"), st.get("viewCount"), st.get("likeCount"),
                                 st.get("commentCount"), None, duracion,
                                 tipo=tipo_youtube(url_v, texto, duracion)))
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
              f"permalink,media_type,media_product_type,media_url}}}}")
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
                             m.get("view_count"), m.get("like_count"), m.get("comments_count"),
                             tipo=tipo_instagram(m.get("media_product_type"), m.get("media_type"))))
        if m.get("media_url") and str(m.get("media_type") or "").upper() == "VIDEO":
            videos[-1]["media_url"] = str(m["media_url"])
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
                                 _duracion(_primero(it, "videoMeta.duration", "duration")),
                                 tipo="fotos" if (it.get("isSlideshow") or it.get("imagePost")) else "video"))
        elif red == "instagram":
            nombre = nombre or _primero(it, "ownerFullName", "ownerUsername") or ""
            videos.append(_video(_primero(it, "id", "shortCode"), it.get("url"), it.get("caption"),
                                 it.get("timestamp"), _primero(it, "videoPlayCount", "videoViewCount", "playCount"),
                                 _primero(it, "likesCount", "likes"), _primero(it, "commentsCount", "comments"),
                                 None, _duracion(_primero(it, "videoDuration", "duration")),
                                 _primero(it, "transcript", "transcription") or "",
                                 tipo=tipo_instagram(it.get("productType"), it.get("type")),
                                 coautores=[(c or {}).get("username") if isinstance(c, dict) else c
                                            for c in (it.get("coauthorProducers") or [])]))
        else:
            nombre = nombre or _primero(it, "channelName", "channel.name") or ""
            seguidores = seguidores or _entero(_primero(it, "numberOfSubscribers", "channel.subscribers"))
            texto = (it.get("title") or "") + ("\n" + it["text"] if it.get("text") else "")
            duracion = _duracion(it.get("duration"))
            videos.append(_video(it.get("id"), it.get("url"), texto, _primero(it, "date", "uploadDate"),
                                 _primero(it, "viewCount", "views"), _primero(it, "likes", "likeCount"),
                                 _primero(it, "commentsCount", "commentCount"), None, duracion,
                                 tipo=("short" if str(it.get("type") or "").lower() == "shorts"
                                       else tipo_youtube(it.get("url"), texto, duracion))))
    # un resultado sin id ni enlace es que el actor ha cambiado de nombres: no es un vídeo
    videos = [v for v in videos if v["id"] or v["url"]]
    return {"red": red, "usuario": str(usuario).lstrip("@"), "nombre": nombre or str(usuario).lstrip("@"),
            "seguidores": seguidores, "fuente": "apify", "videos": videos}


def _error_de_items(items):
    """El error que el actor puso en sus resultados («error», «errorMessage»,
    «message»), en una línea y corto. "" si no trae ninguno."""
    for it in items or []:
        if not isinstance(it, dict):
            continue
        for clave in ("error", "errorMessage", "errorDescription", "message"):
            valor = it.get(clave)
            if isinstance(valor, dict):
                valor = valor.get("message") or valor.get("type")
            if valor:
                return " ".join(str(valor).split())[:200]
    return ""


def coste_apify(red, resultados):
    """Lo que cuesta (aprox.) traer `resultados` vídeos de esa red."""
    _actor, por_mil = ACTORES.get(red, ("", 5.0))
    return round(max(1, resultados) * por_mil / 1000.0, 4)


#: Los estados de una ejecución de Apify que ya no van a cambiar.
TERMINADOS_APIFY = ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED")
#: Cuánto espera Apify cada vez que se le pregunta (su máximo es 60 s).
ESPERA_APIFY_S = 60
#: Por debajo de esta parte de la tabla, la cifra de Apify no se da por buena:
#: un cuarto o menos de lo que la tabla dice para esos resultados es que el
#: campo no trae el precio por resultado (y se queda la reserva o la tabla)
MINIMO_FIABLE_APIFY = 0.25


def _cobrado_apify(run, red=None, resultados=0):
    """Lo que la ejecución ha cobrado de verdad (`usageTotalUsd`: «lo que pagas»,
    también los eventos de un actor de pago por evento), o None si no se puede
    fiar uno de la cifra (y entonces manda la reserva o la tabla).

    SOLO DE UNA EJECUCIÓN TERMINADA (revisión del 12-11): mientras corre (o se
    está abortando) la cifra es una foto que aún va a crecer; apuntarla devolvía
    la reserva y el tope dejaba de ver un gasto que seguía corriendo. Y una cifra
    de 0, o muy por debajo de la tabla con resultados (en algunos actores de
    pago por resultado ese precio puede no entrar en el campo), tampoco se toma."""
    run = run or {}
    if str(run.get("status") or "") not in TERMINADOS_APIFY:
        return None
    try:
        valor = round(float(run.get("usageTotalUsd")), 4)
    except (TypeError, ValueError):
        return None
    if valor <= 0:
        return None
    if red and resultados and valor < MINIMO_FIABLE_APIFY * coste_apify(red, resultados):
        return None
    return valor


def apify(token, red, usuario, cuantos=30, bases=None, plazo=PLAZO_APIFY_S, max_usd=None):
    """Ejecuta el actor de esa red, espera a que acabe y trae sus resultados (de pago).

    `maxItems` y `maxTotalChargeUsd` son el techo DEL LADO DE APIFY: aunque el
    actor quisiera devolver más (el de YouTube cuenta vídeos y Shorts por
    separado), no cobra más de `cuantos` resultados ni más de `max_usd`.

    LO COBRADO DE VERDAD (rama apify-coste-real, 12-11-2026): antes se usaba la
    llamada síncrona, que solo devuelve los resultados, y el gasto era una
    estimación por tabla. Ahora se lanza la ejecución, se espera (de 60 en 60 s,
    hasta `plazo`) y se lee su `usageTotalUsd`. Si Apify no lo da, la tabla de
    siempre. Si se acaba el plazo, la ejecución se aborta (para que no siga
    cobrando) y se apunta lo que haya cobrado."""
    if not token:
        raise ErrorLectura("falta el token de Apify", "sin_clave")
    if red not in ACTORES:
        raise ErrorLectura(f"el servicio de pago no lee {red}", "no_encontrada")
    cuantos = max(1, min(int(cuantos or 30), 50))
    actor, _p = ACTORES[red]
    auth = {"Authorization": f"Bearer {token}"}
    limite = time.monotonic() + plazo
    parametros = {"timeout": max(10, plazo - 20), "maxItems": cuantos,
                  "waitForFinish": min(ESPERA_APIFY_S, max(1, int(plazo)))}
    if max_usd is not None:
        parametros["maxTotalChargeUsd"] = f"{max(0.01, float(max_usd)):.2f}"
    url = f"{BASE_APIFY}/acts/{actor}/runs?" + urllib.parse.urlencode(parametros)
    try:
        codigo, datos = _pedir(url, "POST", entrada_apify(red, usuario, cuantos), plazo=ESPERA_APIFY_S + 15,
                               claves=(token,), bases=bases, cabeceras_extra=auth)
    except ErrorLectura as fallo:
        fallo.cobrado = True               # pudo arrancar: se apunta lo reservado
        raise
    if codigo in (401, 403):
        raise ErrorLectura("el token de Apify no vale", "clave")
    if codigo == 402:
        raise ErrorLectura("Apify: se ha acabado el crédito de la cuenta", "limite")
    if codigo >= 400:
        mensaje = _tachar(str(((datos or {}).get("error") or {}).get("message") or datos)[:300], token)
        raise ErrorLectura(f"Apify ha contestado {codigo}: {mensaje}", "red", cobrado=codigo >= 500)
    run = (datos or {}).get("data") if isinstance(datos, dict) else None
    if not isinstance(run, dict) or not run.get("id"):
        raise ErrorLectura("Apify no ha devuelto la ejecución", "red", cobrado=True)
    rid = urllib.parse.quote(str(run["id"]), safe="")
    # ESPERAR A QUE ACABE: Apify espera hasta 60 s por pregunta
    while str(run.get("status") or "") not in TERMINADOS_APIFY and time.monotonic() < limite:
        espera = int(min(ESPERA_APIFY_S, max(1, limite - time.monotonic() - 5)))
        antes = time.monotonic()
        try:
            codigo, datos = _pedir(f"{BASE_APIFY}/actor-runs/{rid}?waitForFinish={espera}", plazo=espera + 5,
                                   claves=(token,), bases=bases, cabeceras_extra=auth)
        except ErrorLectura:
            codigo, datos = 0, None
        if codigo == 200 and isinstance((datos or {}).get("data"), dict):
            run = datos["data"]
        if str(run.get("status") or "") not in TERMINADOS_APIFY and time.monotonic() - antes < 1:
            time.sleep(min(2.0, max(0.0, limite - time.monotonic())))
    if str(run.get("status") or "") not in TERMINADOS_APIFY:
        # SE ACABÓ EL PLAZO: se aborta para que no siga cobrando
        try:
            codigo, datos = _pedir(f"{BASE_APIFY}/actor-runs/{rid}/abort", "POST", {}, claves=(token,),
                                   bases=bases, cabeceras_extra=auth)
            if codigo == 200 and isinstance((datos or {}).get("data"), dict):
                run = datos["data"]
        except ErrorLectura:
            pass
        # sin terminar, la cifra no vale: se queda la reserva (`_cobrado_apify`)
        raise ErrorLectura("Apify ha tardado demasiado: prueba con menos vídeos", "red", cobrado=True,
                           coste_usd=_cobrado_apify(run, red, cuantos))
    # en los fallos se mide contra lo pedido (`cuantos`): una cifra por debajo de
    # un cuarto de la tabla no se cree y se queda la reserva (revisión del 12-11)
    cobrado = _cobrado_apify(run, red, cuantos)
    if run.get("status") != "SUCCEEDED":
        motivo = "Apify ha tardado demasiado: prueba con menos vídeos" \
            if run.get("status") == "TIMED-OUT" else f"la ejecución de Apify ha acabado en {run.get('status')}"
        raise ErrorLectura(motivo, "red", cobrado=True, coste_usd=cobrado)
    dsid = urllib.parse.quote(str(run.get("defaultDatasetId") or ""), safe="")
    try:
        codigo, datos = _pedir(f"{BASE_APIFY}/datasets/{dsid}/items?clean=true&format=json&limit={cuantos}",
                               claves=(token,), bases=bases, cabeceras_extra=auth)
    except ErrorLectura as fallo:
        fallo.cobrado, fallo.coste_usd = True, cobrado
        raise
    if codigo >= 400:
        raise ErrorLectura(f"Apify no ha dado los resultados ({codigo})", "red", cobrado=True, coste_usd=cobrado)
    items = datos if isinstance(datos, list) else []
    cobrado = _cobrado_apify(run, red, len(items))
    salida = leer_items_apify(red, usuario, items)
    if not salida["videos"] and items:
        # EL ACTOR CONTESTÓ, PERO CON UN ERROR (prueba real del 12-11: TikTok
        # devolvía un resultado que se tiraba y se decía «¿existe?, ¿es
        # privada?»). Se dice lo que dijo Apify y NO como «no existe», que
        # además cortaba los demás intentos.
        dicho = _error_de_items(items) or _tachar(str(run.get("statusMessage") or ""), token)[:200]
        claves = sorted({k for it in items if isinstance(it, dict) for k in it})[:12]
        raise ErrorLectura(f"Apify ha devuelto {len(items)} resultado(s) sin ningún vídeo de «{usuario}» "
                           f"en {red}" + (f": {dicho}" if dicho else f" (campos: {', '.join(claves)})"),
                           "red", cobrado=True, resultados=len(items), coste_usd=cobrado)
    if not salida["videos"]:
        raise ErrorLectura(f"no se ha encontrado ningún vídeo público de «{usuario}» en {red} "
                           "(¿existe?, ¿es privada?)", "no_encontrada", cobrado=bool(items) or bool(cobrado),
                           resultados=len(items), coste_usd=cobrado)
    salida["coste_usd"] = cobrado if cobrado is not None else coste_apify(red, len(items))
    salida["coste_real"] = cobrado is not None
    return salida

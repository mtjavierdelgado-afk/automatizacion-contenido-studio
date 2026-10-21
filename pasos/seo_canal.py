"""El canal de YouTube conectado y Google Trends (rama `seo-real-3`, 21-10-2026).

La fase 3 del SEO de verdad (las fases 1 y 2 son `seo_real.py`):

- **El canal conectado con OAuth (YouTube Analytics).** La persona crea en
  Google Cloud un «ID de cliente de OAuth» (aplicación web), lo pega en
  Configuración con su secreto, y pulsa «Conectar mi canal». Google le pregunta
  si deja leer sus estadísticas y vuelve a `/api/publicar/youtube/oauth/vuelta`
  con un código; aquí se cambia por un token de refresco, que se guarda en el
  almacén de claves (`claves.py`, entrada `youtube_oauth`). Con él:
    · las BÚSQUEDAS DE YOUTUBE que ya traen vistas al canal (los últimos 90
      días): candidatas para «Investigar búsquedas» y un dato más de «Tu
      historial»;
    · por cada vídeo publicado en YouTube, con qué búsquedas lo encontraron y
      cuánto se vio (retención).
  Mientras la app de Google Cloud esté «en prueba», Google caduca el token a
  los 7 días: se ve como `invalid_grant`, se apunta (`caido`) y la pantalla
  ofrece «Volver a conectar».

- **Google Trends (experimental).** Si una frase SUBE o BAJA en Perú en los
  últimos 12 meses, en Google y en YouTube. La API oficial de Trends está en
  alfa y es por invitación, así que se usa la de la web (la misma que la
  página de Trends): sin clave, puede contestar 429 si se le pregunta mucho, y
  si falla la columna se queda sin dato y se dice. Caché de 7 días.

Nada de aquí entra en ninguna firma. Los datos viven en
`<proyectos>/_sistema/publicar/` (`seo_canal.json`) y en la ficha de publicar
de cada vídeo; la caché se borra a los 30 días como la de `seo_real`.
"""

import datetime as dt
import http.cookiejar
import json
import os
import re
import secrets
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from . import claves as CLAVES
    from . import seo_real as SR
except ImportError:                                   # corriendo desde pasos/
    import claves as CLAVES
    import seo_real as SR

ESCOPOS = ("https://www.googleapis.com/auth/yt-analytics.readonly "
           "https://www.googleapis.com/auth/youtube.readonly")
URL_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
URL_DATOS = "https://www.googleapis.com/youtube/v3"
URL_TRENDS = "https://trends.google.com/trends/api"
TIEMPO_S = 10

#: Días que mira el canal (las búsquedas que te traen vistas).
DIAS_CANAL = 90
#: Las búsquedas del canal se vuelven a pedir pasado esto.
CADUCA_CANAL_S = 24 * 3600
#: Trends: viejo a los 7 días, borrado a los 30 (como la caché de seo_real).
CADUCA_TRENDS_S = 7 * 86400
BORRA_S = 30 * 86400
#: Un intento de conexión vale 15 minutos.
CADUCA_INTENTO_S = 900

_LOCK = threading.RLock()
_INTENTOS = {}          # state -> {"redireccion", "t"}
_TOKEN = {}             # "access", "hasta", "refresh" (el refresh con el que se pidió)


class ErrorCanal(Exception):
    def __init__(self, mensaje, codigo=400, caido=False):
        super().__init__(mensaje)
        self.codigo = int(codigo)
        self.caido = caido


# ------------------------------------------------------------------------ HTTP

_GALLETAS = http.cookiejar.CookieJar()
_ABRIDOR = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_GALLETAS))


def _http_real(metodo, url, datos=None, cabeceras=None, timeout=TIEMPO_S):
    """(código, texto). Fallo de red -> (0, motivo) sin la URL ni el cuerpo."""
    cuerpo = None
    if datos is not None:
        cuerpo = urllib.parse.urlencode(datos).encode()
    peticion = urllib.request.Request(url, data=cuerpo, method=metodo, headers=dict(
        {"User-Agent": "Mozilla/5.0 (Estudio SEO)"}, **(cabeceras or {})))
    try:
        with _ABRIDOR.open(peticion, timeout=timeout) as r:            # noqa: S310
            juego = r.headers.get_content_charset() or "utf-8"
            return r.status, r.read().decode(juego, errors="replace")
    except urllib.error.HTTPError as fallo:
        try:
            texto = fallo.read().decode("utf-8", errors="replace")
        except Exception:                                   # noqa: BLE001
            texto = ""
        return fallo.code, texto
    except Exception as fallo:                              # noqa: BLE001
        return 0, f"sin conexión ({type(fallo).__name__})"


#: Lo que hace las peticiones. Las pruebas lo cambian por un doble.
HTTP = _http_real


def simulado():
    """Como `seo_real.simulado`: con ESTUDIO_SIMULAR, sin salir a ningún sitio
    (un doble puesto en `HTTP` manda sobre esto)."""
    if HTTP is not _http_real:
        return False
    if os.environ.get("ESTUDIO_SEO_SIMULADO"):
        return True
    return str(os.environ.get("ESTUDIO_SIMULAR", "")).strip().lower() in ("1", "si", "true")


def _json(texto):
    try:
        return json.loads(texto) if texto else {}
    except ValueError:
        return {}


def _tachar(texto, *valores):
    texto = str(texto or "")
    for v in valores:
        if v and len(str(v)) >= 8:
            texto = texto.replace(str(v), "…")
    return texto


# -------------------------------------------------------------------- ficheros

def _ruta(raiz_p):
    return os.path.join(raiz_p, "_sistema", "publicar", "seo_canal.json")


def _leer(raiz_p):
    try:
        with open(_ruta(raiz_p), "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _escribir(raiz_p, datos):
    ruta = _ruta(raiz_p)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = f"{ruta}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)
    os.replace(tmp, ruta)


def _de_cache(raiz_p, clave, caduca_s):
    if not raiz_p:
        return None
    with _LOCK:
        datos = _leer(raiz_p)
        ahora = time.time()
        viejos = [k for k, v in datos.items()
                  if not isinstance(v, dict) or ahora - float(v.get("t") or 0) >= BORRA_S]
        if viejos:
            for k in viejos:
                datos.pop(k, None)
            _escribir(raiz_p, datos)
        dato = datos.get(clave)
    if isinstance(dato, dict) and time.time() - float(dato.get("t") or 0) < caduca_s:
        return dato.get("v")
    return None


def _a_cache(raiz_p, clave, valor):
    if not raiz_p:
        return
    with _LOCK:
        datos = _leer(raiz_p)
        datos[clave] = {"t": time.time(), "v": valor}
        _escribir(raiz_p, datos)


def olvidar_canal(raiz_p):
    """Al desconectar: fuera todo lo que vino del canal (no lo de Trends)."""
    if not raiz_p:
        return
    with _LOCK:
        datos = {k: v for k, v in _leer(raiz_p).items() if not k.startswith("canal|")}
        _escribir(raiz_p, datos)


# ------------------------------------------------------------------- la conexión

def oauth():
    return dict(CLAVES.leer().get("youtube_oauth") or {})


def estado():
    """Lo que la pantalla puede saber (sin secreto ni token)."""
    return (CLAVES.resumen().get("youtube_oauth") or {})


def redireccion_valida(url):
    """La dirección de vuelta: la de ESTE Studio, terminada en la ruta de vuelta."""
    url = str(url or "").strip()
    partes = urllib.parse.urlparse(url)
    return (partes.scheme in ("https", "http") and partes.netloc
            and partes.path.endswith("/api/publicar/youtube/oauth/vuelta")
            and not partes.query and not partes.fragment)


def empezar(redireccion):
    """-> URL de Google a la que mandar a la persona. Guarda el intento."""
    datos = oauth()
    if not (datos.get("cliente_id") and datos.get("secreto")):
        raise ErrorCanal("pega antes el ID de cliente y el secreto de Google Cloud "
                         "(Configuración → YouTube: tu canal)", 409)
    if not redireccion_valida(redireccion):
        raise ErrorCanal("la dirección de vuelta no es la de este Studio", 400)
    estado_ = secrets.token_urlsafe(24)
    with _LOCK:
        ahora = time.time()
        for k in [k for k, v in _INTENTOS.items() if ahora - v["t"] > CADUCA_INTENTO_S]:
            _INTENTOS.pop(k, None)
        _INTENTOS[estado_] = {"redireccion": redireccion, "t": ahora}
    return f"{URL_AUTH}?" + urllib.parse.urlencode({
        "client_id": datos["cliente_id"], "redirect_uri": redireccion,
        "response_type": "code", "scope": ESCOPOS, "access_type": "offline",
        "prompt": "consent", "include_granted_scopes": "true", "state": estado_})


def terminar(estado_, codigo, raiz_p=None):
    """La vuelta de Google: cambia el código por el token y apunta el canal.
    -> resumen de la conexión. ErrorCanal con un texto para la persona."""
    with _LOCK:
        intento = _INTENTOS.pop(str(estado_ or ""), None)
    if not intento or time.time() - intento["t"] > CADUCA_INTENTO_S:
        raise ErrorCanal("este intento de conexión ya no vale (pasaron más de 15 minutos o "
                         "el servicio se reinició): vuelve a pulsar «Conectar mi canal»")
    if not codigo:
        raise ErrorCanal("Google no ha devuelto el permiso (¿pulsaste «Cancelar»?)")
    datos = oauth()
    if simulado():
        respuesta = {"access_token": "simulado", "refresh_token": "refresco-simulado",
                     "expires_in": 3600}
    else:
        cod, texto = HTTP("POST", URL_TOKEN, {
            "code": codigo, "client_id": datos.get("cliente_id"),
            "client_secret": datos.get("secreto"), "redirect_uri": intento["redireccion"],
            "grant_type": "authorization_code"})
        respuesta = _json(texto)
        if cod != 200 or not respuesta.get("refresh_token"):
            motivo = respuesta.get("error_description") or respuesta.get("error") or f"HTTP {cod}"
            raise ErrorCanal("Google no ha dado el acceso: "
                             + _tachar(motivo, datos.get("secreto"), codigo)
                             + (". Comprueba que la «URI de redireccionamiento autorizada» de tu "
                                "cliente es exactamente la que enseña Configuración"
                                if "redirect" in str(motivo).lower() else ""))
    with _LOCK:
        _TOKEN.clear()
        _TOKEN.update({"access": respuesta.get("access_token"), "refresh": respuesta["refresh_token"],
                       "hasta": time.time() + int(respuesta.get("expires_in") or 3600) - 60})
    canal, canal_id = _nombre_del_canal(respuesta.get("access_token"))
    if raiz_p:
        olvidar_canal(raiz_p)
    return CLAVES.conexion_youtube(
        refresh=respuesta["refresh_token"], canal=canal, canal_id=canal_id, caido="",
        conectado=dt.datetime.now().strftime("%Y-%m-%dT%H:%M"))


def desconectar(raiz_p=None):
    """Olvida el token (Google lo sigue teniendo dado: se quita en
    myaccount.google.com → Seguridad → Aplicaciones de terceros)."""
    datos = oauth()
    if datos.get("refresh") and not simulado():
        HTTP("POST", "https://oauth2.googleapis.com/revoke", {"token": datos["refresh"]})
    with _LOCK:
        _TOKEN.clear()
    olvidar_canal(raiz_p)
    return CLAVES.conexion_youtube(refresh="", canal="", canal_id="", conectado="", caido="")


def _nombre_del_canal(access):
    if simulado():
        return "Canal simulado", "UCsimulado"
    cod, texto = HTTP("GET", f"{URL_DATOS}/channels?part=snippet&mine=true",
                      cabeceras={"Authorization": f"Bearer {access}"})
    items = _json(texto).get("items") or [] if cod == 200 else []
    if not items:
        return "", ""
    return str((items[0].get("snippet") or {}).get("title") or "")[:120], str(items[0].get("id") or "")


def _acceso():
    """Un access token vivo, pedido con el refresh si hace falta."""
    datos = oauth()
    refresh = datos.get("refresh")
    if not refresh:
        raise ErrorCanal("el canal de YouTube no está conectado", 409)
    with _LOCK:
        if _TOKEN.get("access") and _TOKEN.get("refresh") == refresh and \
                time.time() < float(_TOKEN.get("hasta") or 0):
            return _TOKEN["access"]
    if simulado():
        return "simulado"
    cod, texto = HTTP("POST", URL_TOKEN, {
        "refresh_token": refresh, "client_id": datos.get("cliente_id"),
        "client_secret": datos.get("secreto"), "grant_type": "refresh_token"})
    respuesta = _json(texto)
    if cod != 200 or not respuesta.get("access_token"):
        error = str(respuesta.get("error") or "")
        if error in ("invalid_grant", "unauthorized_client", "invalid_client"):
            # el token caducó (app «en prueba»: 7 días) o se quitó el permiso
            CLAVES.conexion_youtube(caido=dt.datetime.now().strftime("%Y-%m-%dT%H:%M"))
            raise ErrorCanal("Google ha cortado la conexión con tu canal (si tu app de Google "
                             "Cloud está «en prueba», lo hace cada 7 días): pulsa «Volver a "
                             "conectar» en Configuración", 409, caido=True)
        raise ErrorCanal(f"Google no da acceso al canal ahora mismo ({error or 'HTTP ' + str(cod)})",
                         502)
    with _LOCK:
        _TOKEN.update({"access": respuesta["access_token"], "refresh": refresh,
                       "hasta": time.time() + int(respuesta.get("expires_in") or 3600) - 60})
    if datos.get("caido"):
        CLAVES.conexion_youtube(caido="")
    return respuesta["access_token"]


def conectado():
    return bool(oauth().get("refresh"))


# ------------------------------------------------------------- YouTube Analytics

def _informe(params):
    """Una consulta de YouTube Analytics -> {columnas, filas}. ErrorCanal si falla."""
    access = _acceso()
    params = dict({"ids": "channel==MINE"}, **params)
    cod, texto = HTTP("GET", f"{URL_ANALYTICS}?{urllib.parse.urlencode(params)}",
                      cabeceras={"Authorization": f"Bearer {access}"})
    datos = _json(texto)
    if cod == 401:
        with _LOCK:
            _TOKEN.clear()
        raise ErrorCanal("Google no acepta el acceso al canal: vuelve a conectarlo", 409, caido=True)
    if cod != 200:
        motivo = ((datos.get("error") or {}).get("message") if isinstance(datos.get("error"), dict)
                  else datos.get("error")) or f"HTTP {cod}"
        if "has not been used" in str(motivo) or "disabled" in str(motivo):
            motivo = ("activa la «YouTube Analytics API» en tu proyecto de Google Cloud (y la "
                      "«YouTube Data API v3»)")
        raise ErrorCanal(f"YouTube Analytics: {_tachar(motivo, access)}", 502)
    columnas = [c.get("name") for c in datos.get("columnHeaders") or []]
    return {"columnas": columnas, "filas": datos.get("rows") or []}


def _fechas(dias):
    hoy = dt.date.today()
    return (hoy - dt.timedelta(days=dias)).isoformat(), (hoy - dt.timedelta(days=1)).isoformat()


def _simuladas_del_canal():
    return [{"termino": "alquiler de consolas", "vistas": 320},
            {"termino": "fiesta infantil con videojuegos", "vistas": 180},
            {"termino": "consolas para fiestas lima", "vistas": 95},
            {"termino": "karaoke para fiestas", "vistas": 40}]


def busquedas_del_canal(raiz_p, forzar=False):
    """[{termino, vistas}] — las búsquedas de YouTube que trajeron vistas al
    canal en los últimos 90 días (las 25 primeras). [] sin conexión.
    Puede lanzar ErrorCanal (la pantalla lo enseña)."""
    if not conectado():
        return []
    clave = "canal|busquedas"
    if not forzar:
        guardada = _de_cache(raiz_p, clave, CADUCA_CANAL_S)
        if guardada is not None:
            return guardada
    if simulado():
        filas = _simuladas_del_canal()
    else:
        desde, hasta = _fechas(DIAS_CANAL)
        inf = _informe({"startDate": desde, "endDate": hasta, "metrics": "views",
                        "dimensions": "insightTrafficSourceDetail",
                        "filters": "insightTrafficSourceType==YT_SEARCH",
                        "sort": "-views", "maxResults": 25})
        filas = [{"termino": " ".join(str(f[0]).split())[:80], "vistas": int(f[1] or 0)}
                 for f in inf["filas"] if f and f[0]]
    _a_cache(raiz_p, clave, filas)
    return filas


def id_de_youtube(url):
    """El id de un vídeo de YouTube de su URL (watch, shorts o youtu.be)."""
    url = str(url or "")
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def como_te_encontraron(raiz_p, video_id):
    """Del vídeo publicado: sus vistas, retención y las búsquedas de YouTube
    que lo trajeron. -> {vistas, duracion_media_s, porcentaje_visto, busquedas:
    [{termino, vistas}], desde, al}. ErrorCanal si falla."""
    if not video_id:
        raise ErrorCanal("este vídeo todavía no tiene un enlace de YouTube", 409)
    desde, hasta = _fechas(365)
    if simulado():
        resumen = {"vistas": 812, "duracion_media_s": 21.4, "porcentaje_visto": 47.5}
        busquedas = [{"termino": "fiesta infantil con consolas", "vistas": 60},
                     {"termino": "alquiler de consolas lima", "vistas": 22}]
    else:
        inf = _informe({"startDate": desde, "endDate": hasta,
                        "metrics": "views,averageViewDuration,averageViewPercentage",
                        "filters": f"video=={video_id}"})
        fila = (inf["filas"] or [[0, 0, 0]])[0]
        resumen = {"vistas": int(fila[0] or 0), "duracion_media_s": round(float(fila[1] or 0), 1),
                   "porcentaje_visto": round(float(fila[2] or 0), 1)}
        inf = _informe({"startDate": desde, "endDate": hasta, "metrics": "views",
                        "dimensions": "insightTrafficSourceDetail",
                        "filters": f"video=={video_id};insightTrafficSourceType==YT_SEARCH",
                        "sort": "-views", "maxResults": 25})
        busquedas = [{"termino": " ".join(str(f[0]).split())[:80], "vistas": int(f[1] or 0)}
                     for f in inf["filas"] if f and f[0]]
    return dict(resumen, busquedas=busquedas, video_id=video_id, desde=desde,
                al=dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))


def vistas_del_canal_para(frase, filas):
    """Las vistas que trajeron al canal las búsquedas que SON esta frase (todas
    sus palabras con significado). -> (vistas, [terminos])"""
    ts = SR.terminos(frase)
    if not ts:
        return 0, []
    total, cuales = 0, []
    for f in filas or []:
        suyos = set(SR.terminos(f.get("termino")))
        if suyos and all(t in suyos for t in ts) or (suyos and all(t in ts for t in suyos)
                                                     and len(suyos) >= 2):
            total += int(f.get("vistas") or 0)
            cuales.append(f.get("termino"))
    return total, cuales


def con_el_canal(candidata, filas):
    """Suma a «Tu historial» de una candidata lo que dice el canal: si esa
    búsqueda ya te trae vistas en YouTube. Cambia la candidata en su sitio."""
    vistas, cuales = vistas_del_canal_para(candidata.get("frase"), filas)
    if not filas:
        return candidata
    candidata["canal"] = {"vistas": vistas, "terminos": cuales[:5]}
    if not vistas:
        return candidata
    total = sum(int(f.get("vistas") or 0) for f in filas) or 1
    # 100 si trae una cuarta parte de lo que llega por búsqueda; 60 con algo
    valor = round(min(100, 60 + 160 * vistas / total))
    h = dict(candidata.get("historial") or {})
    texto = (f"ya te trae {vistas} vista{'s' if vistas != 1 else ''} desde la búsqueda de YouTube "
             f"(últimos {DIAS_CANAL} días)")
    if h.get("valor") is None:
        h.update(valor=valor, texto=texto)
    else:
        h["valor"] = max(int(h["valor"]), valor)
        h["texto"] = f"{h.get('texto') or ''}; {texto}".strip("; ")
    candidata["historial"] = h
    return candidata


# ---------------------------------------------------------------- Google Trends

def _sin_prefijo(texto):
    """Trends antepone «)]}'» (y a veces una coma) para que no se lea como JS."""
    return re.sub(r"^\)\]\}',?\s*", "", str(texto or "").lstrip())


def _trends_simulado(frases):
    salida = {}
    for i, f in enumerate(frases):
        semilla = sum(ord(c) for c in SR.normal(f)) or 1
        base = 20 + semilla % 50
        cambio = ((semilla % 7) - 3) * 12
        salida[f] = {"indice": base, "cambio": cambio}
    return salida


def _serie(frases, propiedad):
    """{frase: [valores semana a semana]} de Trends para Perú, 12 meses."""
    peticion = {"comparisonItem": [{"keyword": f, "geo": SR.PAIS.upper(), "time": "today 12-m"}
                                   for f in frases],
                "category": 0, "property": propiedad}
    url = f"{URL_TRENDS}/explore?" + urllib.parse.urlencode({
        "hl": "es-419", "tz": "300", "req": json.dumps(peticion, ensure_ascii=False)})
    cod, texto = HTTP("GET", url)
    if cod == 429 or cod == 0 or cod != 200:
        # la primera vez Trends pide una galleta: se coge en la portada y se reintenta
        HTTP("GET", f"https://trends.google.com/trends/explore?geo={SR.PAIS.upper()}")
        cod, texto = HTTP("GET", url)
    if cod != 200:
        raise ErrorCanal("Google Trends no contesta ahora" + (" (demasiadas preguntas: 429)"
                                                               if cod == 429 else ""), 502)
    widgets = _json(_sin_prefijo(texto)).get("widgets") or []
    linea = next((w for w in widgets if w.get("id") == "TIMESERIES"), None)
    if not linea:
        raise ErrorCanal("Google Trends ha cambiado su respuesta", 502)
    url = f"{URL_TRENDS}/widgetdata/multiline?" + urllib.parse.urlencode({
        "hl": "es-419", "tz": "300", "req": json.dumps(linea.get("request") or {}, ensure_ascii=False),
        "token": linea.get("token") or ""})
    cod, texto = HTTP("GET", url)
    if cod != 200:
        raise ErrorCanal("Google Trends no ha dado los datos", 502)
    puntos = ((_json(_sin_prefijo(texto)).get("default") or {}).get("timelineData")) or []
    series = {f: [] for f in frases}
    for p in puntos:
        valores = p.get("value") or []
        for i, f in enumerate(frases):
            if i < len(valores):
                series[f].append(float(valores[i] or 0))
    return series


def _medir(serie):
    """{indice 0-100 (media de las 12 últimas semanas), cambio % (12 últimas
    frente a las 12 anteriores)} o None si no hay serie."""
    if not serie or len(serie) < 8:
        return None
    ultimas = serie[-12:]
    previas = serie[-24:-12] or serie[:len(serie) // 2]
    indice = round(statistics.mean(ultimas))
    antes = statistics.mean(previas) if previas else 0
    if antes <= 0:
        cambio = 100 if indice > 0 else 0
    else:
        cambio = round(100 * (statistics.mean(ultimas) - antes) / antes)
    return {"indice": indice, "cambio": max(-100, min(300, cambio))}


def tendencias(frases, raiz_p=None):
    """{frase: {youtube: {indice, cambio} | None, google: {...} | None,
    texto, sentido: sube|baja|estable|""}} para hasta 5 frases (Trends
    compara 5 a la vez: el índice es relativo ENTRE ellas). Lo que falla
    queda en None con `error` en la salida, sin lanzar."""
    frases = [" ".join(str(f).split())[:80] for f in frases if str(f or "").strip()][:5]
    salida = {"frases": {}, "error": ""}
    if not frases:
        return salida
    clave = "trends|" + "|".join(sorted(SR.normal(f) for f in frases))
    guardada = _de_cache(raiz_p, clave, CADUCA_TRENDS_S)
    if guardada is not None:
        return guardada
    por_fuente = {}
    for fuente, propiedad in (("google", ""), ("youtube", "youtube")):
        try:
            if simulado():
                medidas = _trends_simulado(frases)
            else:
                series = _serie(frases, propiedad)
                medidas = {f: _medir(series.get(f)) for f in frases}
            por_fuente[fuente] = medidas
        except ErrorCanal as fallo:
            salida["error"] = str(fallo)
            por_fuente[fuente] = {}
    for f in frases:
        g = por_fuente.get("google", {}).get(f)
        y = por_fuente.get("youtube", {}).get(f)
        base = y or g
        sentido, texto = "", ""
        if base:
            cambio = base["cambio"]
            sentido = "sube" if cambio >= 20 else "baja" if cambio <= -20 else "estable"
            donde = "en YouTube" if y else "en Google"
            texto = {"sube": f"sube {donde} (+{cambio} % en los últimos 3 meses)",
                     "baja": f"baja {donde} ({cambio} % en los últimos 3 meses)",
                     "estable": f"estable {donde} en el último año"}[sentido]
        salida["frases"][f] = {"google": g, "youtube": y, "sentido": sentido, "texto": texto}
    # solo se guarda si algo vino (un 429 no se queda una semana)
    if any(v["sentido"] for v in salida["frases"].values()):
        _a_cache(raiz_p, clave, salida)
    return salida


def con_tendencia(candidata, t):
    """Pone la tendencia en la candidata y ajusta un poco su demanda (±8)."""
    if not t or not t.get("sentido"):
        return candidata
    candidata["tendencia"] = t
    dem = dict(candidata.get("demanda") or {})
    if dem.get("valor") is not None:
        ajuste = {"sube": 8, "baja": -8}.get(t["sentido"], 0)
        dem["valor"] = max(0, min(100, int(dem["valor"]) + ajuste))
        dem["nivel"] = SR.nivel(dem["valor"])
        dem["textos"] = list(dem.get("textos") or []) + [f"Google Trends: {t['texto']}"]
        candidata["demanda"] = dem
    return candidata

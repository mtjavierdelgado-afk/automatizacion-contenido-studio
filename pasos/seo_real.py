"""El SEO de verdad de Publicar (rama `seo-real`, 20-10-2026).

Lo que había antes (`publicar_seo.nota`) era una lista de comprobaciones de
FORMA: ¿está la palabra clave en el título?, ¿cuántos hashtags? Y la palabra
clave salía del proyecto aunque el vídeo no tratara de eso: el dueño se
encontraba la nota pidiéndole meter «alquiler de consolas en Lima» en un vídeo
de otra cosa. Esto mide lo que de verdad importa, en tres partes:

- **Relevancia**: ¿la palabra clave sale en el vídeo (guion, material, título)?
  Y, si sale, ¿está donde la lee el buscador (título, primera línea)? Una
  palabra que el vídeo no trata no se propone nunca, por mucho que se busque.
- **Demanda**: ¿la busca alguien? El autocompletado de YouTube y de Google para
  Perú en español (no es una API oficial: se guarda en caché y, si no contesta,
  la parte se queda sin dato, sin romper nada). Con la clave de la API de datos
  de YouTube (opcional, Configuración), además la competencia: qué vistas
  tienen los diez primeros resultados y cuántos son canales pequeños.
- **Tu historial**: ¿cómo le fue a esta palabra en TU cuenta? Las vistas de los
  posts con ella frente a lo normal de cada red en la cuenta (mediana), con un
  mínimo de posts para no fiarse de uno solo.

Los detalles de forma (largo del título, número de hashtags, CTA…) siguen
saliendo, pero aparte y SIN contar en la nota: no inflan un vídeo mal
posicionado.

Nada de esto entra en ninguna firma: vive en `<proyectos>/_sistema/publicar/`
(la caché, el cupo de YouTube) y en la ficha de publicar de cada vídeo
(`seo_real`, la última investigación). Los datos de YouTube no se guardan más
de 30 días (lo pide su política de la API): la caché los da por viejos a los
7 y los borra a los 30, y la investigación de un vídeo pierde su competencia
a los 30.
"""

import datetime as dt
import json
import math
import os
import re
import statistics
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

# ------------------------------------------------------------------ constantes

#: Una palabra clave es «del vídeo» si al menos este % de sus palabras con
#: significado sale en el guion, el material o el título: dos de dos, tres de
#: tres o tres de cuatro («fiesta infantil precio» no es de un vídeo que no
#: habla de precios).
RELEVANTE = 70
#: Con menos palabras que estas en el vídeo no se puede decir si algo es
#: relevante (un vídeo sin guion ni material): la relevancia queda sin dato.
MINIMO_CORPUS = 12

PESOS = {"relevancia": 45, "demanda": 35, "historial": 20}
NOMBRES_PARTE = {"relevancia": "Relevancia", "demanda": "Demanda",
                 "historial": "Tu historial"}

#: El autocompletado: se pregunta a Perú en español.
PAIS, IDIOMA = "pe", "es"
URL_SUGERENCIAS = "https://suggestqueries.google.com/complete/search"
URL_YOUTUBE = "https://www.googleapis.com/youtube/v3"
TIEMPO_S = 6

#: La caché: viejo a los 7 días (se vuelve a preguntar), borrado a los 30.
CADUCA_S = 7 * 86400
BORRA_S = 30 * 86400

#: El cupo de la API de YouTube: 10.000 unidades al día; una búsqueda cuesta
#: 100 (y los datos de sus vídeos y canales, 1 cada uno). Se deja margen.
LIMITE_UNIDADES = int(os.environ.get("ESTUDIO_YT_UNIDADES") or 9000)
COSTE_BUSQUEDA = 102
#: Por investigación, como mucho estas frases van a la API (las mejores).
MAX_COMPETENCIA = 5
#: Por investigación, como mucho estas candidatas.
MAX_CANDIDATAS = 10
#: Un canal con menos suscriptores que esto es «pequeño».
CANAL_PEQUENO = 10000

#: Para «Tu historial»: posts con la palabra y posts de la cuenta.
MINIMO_POSTS_PALABRA = 3
MINIMO_POSTS_CUENTA = 5

STOP = set("""
a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque
bajo bien cada como con contra cual cuales cuando de del desde donde dos e el
ella ellas ellos en entre era eres es esa esas ese eso esos esta estan estas
este esto estos fue ha hace hacen hasta hay la las le les lo los mas me mi mis
mucho muy nada ni no nos o otra otro para pero poco por porque que quien se
sea ser si sin sobre son su sus tambien te tiene tienen todo todos tu tus un
una unas uno unos y ya yo vs the and of to in for on with your you how what
es eso esto ese aca alli ahi hoy aqui ver hacer tener mejor mejores
""".split())

_LOCK = threading.RLock()

# --------------------------------------------------------------- texto y raíces


def normal(texto):
    """Sin tildes, en minúsculas y con un espacio entre palabras."""
    t = unicodedata.normalize("NFD", str(texto or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.findall(r"[a-z0-9]+", t))


def raiz(palabra):
    """Una raíz ligera para que «consolas» y «consola», o «clases» y «clase»,
    cuenten como la misma: fuera la «s» final y luego la «e»."""
    p = palabra
    if len(p) > 3 and p.endswith("s"):
        p = p[:-1]
    if len(p) > 4 and p.endswith("e"):
        p = p[:-1]
    return p


def palabras(texto):
    """Las palabras con significado, normalizadas (sin raíz)."""
    return [w for w in normal(texto).split()
            if (len(w) > 2 or w.isdigit()) and w not in STOP]


def terminos(texto):
    """Las raíces de las palabras con significado, sin repetir y en orden."""
    vistos, salida = set(), []
    for w in palabras(texto):
        r = raiz(w)
        if r not in vistos:
            vistos.add(r)
            salida.append(r)
    return salida


def corpus_del_video(info):
    """Todo lo que el vídeo DICE: nombre, título, material, instrucciones y
    guion. No los textos de redes: esos pueden llevar ya la palabra metida a
    la fuerza, que es justo lo que se quiere detectar."""
    info = info or {}
    trozos = [info.get("nombre"), info.get("titulo"), info.get("material"),
              info.get("instrucciones")]
    trozos += [b.get("texto") for b in (info.get("guion") or []) if isinstance(b, dict)]
    return "\n".join(str(t) for t in trozos if t)


class Corpus:
    """Las raíces del vídeo con cuántas veces salen, calculadas una vez."""

    def __init__(self, info, zona=""):
        cuenta = {}
        for w in palabras(corpus_del_video(info)):
            r = raiz(w)
            cuenta[r] = cuenta.get(r, 0) + 1
        self.cuenta = cuenta
        self.total = sum(cuenta.values())
        # la zona del proyecto vale aunque el vídeo no la diga: el negocio
        # está ahí («consolas en Lima» es del vídeo aunque no diga «Lima»)
        self.zona = set(terminos(zona))

    @property
    def sabe(self):
        return self.total >= MINIMO_CORPUS

    def tiene(self, termino):
        if termino in self.cuenta or termino in self.zona:
            return True
        # una raíz que empieza igual (consol / consolas) con al menos 5 letras
        if len(termino) >= 5:
            return any(len(r) >= 5 and (r.startswith(termino) or termino.startswith(r))
                       for r in self.cuenta)
        return False


_CORPUS = {}
_MAX_CORPUS = 64


def corpus_de(info, zona=""):
    """El Corpus del vídeo, guardado por su texto: la ficha se pregunta cada
    pocos segundos y cada red lo pedía otra vez (revisión del 20-10: ~30 por
    petición, 150-300 ms en un guion largo)."""
    clave = (hash(corpus_del_video(info)), str(zona or ""))
    with _LOCK:
        hecho = _CORPUS.get(clave)
    if hecho is not None:
        return hecho
    hecho = Corpus(info, zona)
    with _LOCK:
        if len(_CORPUS) >= _MAX_CORPUS:
            _CORPUS.clear()
        _CORPUS[clave] = hecho
    return hecho


def relevancia(frase, info=None, zona="", corpus=None):
    """{valor 0-100 | None, estan, faltan}: cuánto de la frase sale en el vídeo.
    None si no hay frase o el vídeo no tiene bastante texto para saberlo."""
    corpus = corpus or corpus_de(info, zona)
    ts = terminos(frase)
    if not ts or not corpus.sabe:
        return {"valor": None, "estan": [], "faltan": []}
    originales = {}
    for w in palabras(frase):
        originales.setdefault(raiz(w), w)
    estan = [originales.get(t, t) for t in ts if corpus.tiene(t)]
    faltan = [originales.get(t, t) for t in ts if not corpus.tiene(t)]
    return {"valor": round(100 * len(estan) / len(ts)), "estan": estan, "faltan": faltan}


def es_relevante(frase, info=None, zona="", corpus=None):
    """¿Es del vídeo? Sin dato (un vídeo sin texto) se da por buena: es lo que
    pasaba antes, y no hay con qué decir que no."""
    v = relevancia(frase, info, zona, corpus)["valor"]
    return v is None or v >= RELEVANTE


def frases_del_video(info, cuantas=3):
    """Las parejas de palabras que más repite el vídeo («fiesta infantil»),
    para buscar cuando no hay ninguna palabra clave que sirva."""
    texto = corpus_del_video(info)
    cuenta, primera = {}, {}
    for linea in re.split(r"[\n.!?;:]+", texto):
        ws = [w for w in normal(linea).split()]
        for a, b in zip(ws, ws[1:]):
            if a in STOP or b in STOP or len(a) < 3 or len(b) < 3 or a.isdigit() or b.isdigit():
                continue
            clave = f"{a} {b}"
            cuenta[clave] = cuenta.get(clave, 0) + 1
            primera.setdefault(clave, len(primera))
    orden = sorted(cuenta, key=lambda k: (-cuenta[k], primera[k]))
    return [k for k in orden if cuenta[k] >= 2][:cuantas] or orden[:1]


# -------------------------------------------------------------------- ficheros

def _carpeta(raiz_p):
    return os.path.join(raiz_p, "_sistema", "publicar")


def _ruta_cache(raiz_p):
    return os.path.join(_carpeta(raiz_p), "seo_cache.json")


def _ruta_cupo(raiz_p):
    return os.path.join(_carpeta(raiz_p), "youtube_cupo.json")


def _leer(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = f"{ruta}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False)
    os.replace(tmp, ruta)


def _de_cache(raiz_p, clave):
    if not raiz_p:
        return None
    with _LOCK:
        ruta = _ruta_cache(raiz_p)
        datos = _leer(ruta)
        ahora = time.time()
        viejos = [k for k, v in datos.items()
                  if not isinstance(v, dict) or ahora - float(v.get("t") or 0) >= BORRA_S]
        if viejos:
            # también al leer: los datos de YouTube no pasan de 30 días aunque
            # nadie vuelva a guardar nada en la caché
            for k in viejos:
                datos.pop(k, None)
            _escribir(ruta, datos)
        dato = datos.get(clave)
    if isinstance(dato, dict) and time.time() - float(dato.get("t") or 0) < CADUCA_S:
        return dato.get("v")
    return None


def _a_cache(raiz_p, clave, valor):
    """Guarda y, de paso, borra todo lo que pase de 30 días."""
    if not raiz_p:
        return
    with _LOCK:
        ruta = _ruta_cache(raiz_p)
        datos = _leer(ruta)
        ahora = time.time()
        datos = {k: v for k, v in datos.items()
                 if isinstance(v, dict) and ahora - float(v.get("t") or 0) < BORRA_S}
        datos[clave] = {"t": ahora, "v": valor}
        _escribir(ruta, datos)


# ------------------------------------------------------------------------ HTTP

def _http_real(url, timeout=TIEMPO_S):
    """(código, texto). Fallo de red -> (0, motivo) sin la URL (lleva la clave)."""
    peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Estudio SEO)"})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as r:     # noqa: S310
            crudo = r.read()
            juego = r.headers.get_content_charset() or "utf-8"
            return r.status, crudo.decode(juego, errors="replace")
    except urllib.error.HTTPError as fallo:
        try:
            cuerpo = fallo.read().decode("utf-8", errors="replace")
        except Exception:                                   # noqa: BLE001
            cuerpo = ""
        return fallo.code, cuerpo
    except Exception as fallo:                              # noqa: BLE001
        return 0, f"sin conexión ({type(fallo).__name__})"


#: Lo que hace las peticiones. Las pruebas lo cambian por un doble.
HTTP = _http_real


def simulado():
    """Sin salir a internet: en las suites (ESTUDIO_SIMULAR=1) o con
    ESTUDIO_SEO_SIMULADO. Un doble puesto en `HTTP` manda sobre esto."""
    if HTTP is not _http_real:
        return False
    if os.environ.get("ESTUDIO_SEO_SIMULADO"):
        return True
    return str(os.environ.get("ESTUDIO_SIMULAR", "")).strip().lower() in ("1", "si", "true")


def _simuladas(frase, fuente):
    base = " ".join(normal(frase).split())
    if not base:
        return []
    colas = (("en lima", "precio", "para niños", "cerca de mi") if fuente == "youtube"
             else ("precio", "lima"))
    return [base] + [f"{base} {c}" for c in colas]


def _leer_sugerencias(texto):
    """[q, [sugerencias]] (o el JSONP de client=youtube) -> [sugerencias]."""
    texto = (texto or "").strip()
    m = re.match(r"^[\w.]+\((.*)\)\s*;?\s*$", texto, re.S)
    if m:
        texto = m.group(1)
    datos = json.loads(texto)
    if not isinstance(datos, list) or len(datos) < 2 or not isinstance(datos[1], list):
        raise ValueError("forma desconocida")
    salida = []
    for s in datos[1]:
        if isinstance(s, list) and s:
            s = s[0]
        if isinstance(s, str) and s.strip():
            salida.append(" ".join(s.split()))
    return salida


def sugerencias(frase, fuente="youtube", raiz_p=None):
    """Lo que el buscador propone al escribir `frase` -> [str] o None si no se
    ha podido preguntar (sin red, cambió la forma…). `fuente`: youtube|google."""
    frase = " ".join(str(frase or "").split())
    if not frase:
        return []
    clave = f"sug|{fuente}|{normal(frase)}"
    guardada = _de_cache(raiz_p, clave)
    if guardada is not None:
        return guardada
    if simulado():
        lista = _simuladas(frase, fuente)
    else:
        params = {"client": "firefox", "hl": IDIOMA, "gl": PAIS, "ie": "utf-8",
                  "oe": "utf-8", "q": frase}
        if fuente == "youtube":
            params["ds"] = "yt"
        codigo, texto = HTTP(f"{URL_SUGERENCIAS}?{urllib.parse.urlencode(params)}")
        if codigo != 200:
            return None
        try:
            lista = _leer_sugerencias(texto)
        except (ValueError, TypeError):
            return None
    _a_cache(raiz_p, clave, lista)
    return lista


def _puntos_fuente(frase_n, lista, lista_prefijo):
    """0-100 de demanda de una fuente con sus sugerencias."""
    if lista is None:
        return None
    normales = [normal(s) for s in lista]
    exacta = frase_n in normales
    extensiones = sum(1 for s in normales if s.startswith(frase_n + " "))
    pos = None
    for i, s in enumerate(normal(x) for x in (lista_prefijo or [])):
        if s == frase_n or s.startswith(frase_n + " "):
            pos = i
            break
    if pos is not None:
        return 95 if pos < 3 else 85
    if exacta and extensiones >= 3 or extensiones >= 5:
        return 65
    if extensiones >= 2 or exacta:
        return 45
    if extensiones >= 1:
        return 30
    return 10


def nivel(valor):
    if valor is None:
        return ""
    return "alta" if valor >= 80 else "media" if valor >= 55 else "baja" if valor >= 30 else "casi nula"


def _prefijo(frase):
    ws = str(frase).split()
    if len(ws) >= 2:
        return " ".join(ws[:-1])
    return frase[:max(3, len(frase) - 2)]


def demanda(frase, raiz_p=None):
    """{valor 0-100 | None, nivel, youtube, google, sugerencias, textos}."""
    frase_n = normal(frase)
    yt = sugerencias(frase, "youtube", raiz_p)
    goo = sugerencias(frase, "google", raiz_p)
    yt_p = sugerencias(_prefijo(frase), "youtube", raiz_p) if yt is not None else None
    p_yt = _puntos_fuente(frase_n, yt, yt_p)
    p_g = _puntos_fuente(frase_n, goo, None)
    if p_yt is None and p_g is None:
        return {"valor": None, "nivel": "", "youtube": None, "google": None, "sugerencias": [],
                "textos": ["no se ha podido preguntar al buscador (se reintenta en la "
                           "próxima investigación)"]}
    if p_yt is None:
        valor = p_g
    elif p_g is None:
        valor = p_yt
    else:
        valor = round(0.6 * p_yt + 0.4 * p_g)
    textos = []
    if p_yt is not None:
        if p_yt >= 85:
            textos.append(f"YouTube la propone al escribir «{_prefijo(frase)}…»: se busca")
        elif p_yt >= 45:
            textos.append("YouTube la completa con otras búsquedas: hay quien la busca")
        else:
            textos.append("YouTube casi no la propone: poca gente la escribe así")
    if p_g is not None and p_g >= 45:
        textos.append("también se busca en Google")
    return {"valor": valor, "nivel": nivel(valor), "youtube": p_yt, "google": p_g,
            "sugerencias": (yt or [])[:8], "textos": textos}


# ------------------------------------------------------- la API de YouTube y su cupo

def _dia_pacifico():
    try:
        from zoneinfo import ZoneInfo                       # noqa: PLC0415
        zona = ZoneInfo("America/Los_Angeles")
    except Exception:                                       # noqa: BLE001
        zona = dt.timezone(dt.timedelta(hours=-8))
    return dt.datetime.now(zona).strftime("%Y-%m-%d")


def cupo(raiz_p):
    """{usadas, limite, busquedas, agotado}: lo gastado HOY (el cupo de YouTube
    se renueva a medianoche del Pacífico)."""
    datos = _leer(_ruta_cupo(raiz_p)) if raiz_p else {}
    hoy = _dia_pacifico()
    usadas = int(datos.get("unidades") or 0) if datos.get("dia") == hoy else 0
    agotado = bool(datos.get("agotado")) if datos.get("dia") == hoy else False
    quedan = 0 if agotado else max(0, (LIMITE_UNIDADES - usadas) // COSTE_BUSQUEDA)
    return {"usadas": usadas, "limite": LIMITE_UNIDADES, "busquedas": quedan,
            "agotado": agotado}


def gastar(raiz_p, unidades, agotado=False):
    """Apunta unidades gastadas fuera de una búsqueda («Probar» la clave)."""
    _gastar(raiz_p, unidades, agotado)


def _gastar(raiz_p, unidades, agotado=False):
    if not raiz_p:
        return
    with _LOCK:
        ruta = _ruta_cupo(raiz_p)
        datos = _leer(ruta)
        hoy = _dia_pacifico()
        if datos.get("dia") != hoy:
            datos = {"dia": hoy, "unidades": 0}
        datos["unidades"] = int(datos.get("unidades") or 0) + int(unidades)
        if agotado:
            datos["agotado"] = True
        _escribir(ruta, datos)


def _api(ruta, params, clave):
    """(datos | None, error). El error nunca lleva la clave."""
    params = dict(params, key=clave)
    codigo, texto = HTTP(f"{URL_YOUTUBE}/{ruta}?{urllib.parse.urlencode(params)}")
    try:
        datos = json.loads(texto) if texto else {}
    except ValueError:
        datos = {}
    if codigo == 200 and isinstance(datos, dict):
        return datos, ""
    motivo = ""
    if isinstance(datos, dict) and isinstance(datos.get("error"), dict):
        motivo = str(datos["error"].get("message") or "")
        razones = [str(e.get("reason") or "") for e in datos["error"].get("errors") or []
                   if isinstance(e, dict)]
        cupo_razones = ("quota", "dailylimitexceeded", "ratelimitexceeded")
        if any(any(c in r.lower() for c in cupo_razones) for r in razones) \
                or "quota" in motivo.lower():
            return None, "cupo"
    if clave and clave in motivo:
        motivo = motivo.replace(clave, "…")
    return None, (f"YouTube contesta {codigo}: {motivo[:200]}" if codigo else
                  "no se ha podido hablar con YouTube")


def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _competencia_simulada(frase):
    semilla = sum(ord(c) for c in normal(frase)) or 1
    vistas = [((semilla * (i + 3)) % 90 + 1) * 1000 for i in range(10)]
    return {"vistas": vistas, "dias": [30 + (semilla + i * 17) % 400 for i in range(10)],
            "subs": [((semilla * (i + 7)) % 60) * 1000 for i in range(10)],
            "titulos": [f"{frase} ({i + 1})" for i in range(10)],
            "canales": [f"Canal {i + 1}" for i in range(10)],
            "ids": [f"sim{i}" for i in range(10)], "total": 1000 + semilla % 5000}


def competencia(frase, raiz_p, clave):
    """{valor 0-100 (más = más difícil), nivel, interes 0-100, mediana_vistas,
    mediana_vistas_dia, pequenos, recientes, total, top} o {"error": ...}.
    None si no hay clave. Gasta ~102 unidades del cupo (si no está en caché)."""
    if not clave:
        return None
    ck = f"comp|{normal(frase)}"
    guardada = _de_cache(raiz_p, ck)
    if guardada is not None:
        return guardada
    if simulado():
        bruto = _competencia_simulada(frase)
    else:
        if cupo(raiz_p)["busquedas"] <= 0:
            return {"error": "cupo", "texto": "el cupo de búsquedas de YouTube de hoy está "
                                              "gastado (se renueva a medianoche del Pacífico)"}
        busqueda, error = _api("search", {"part": "snippet", "type": "video", "maxResults": 10,
                                          "q": frase, "regionCode": PAIS.upper(),
                                          "relevanceLanguage": IDIOMA}, clave)
        if busqueda is None:
            # una clave mala o la API sin activar no gasta cupo: no se apunta
            # (antes se apuntaban 100 por frase y el cupo «se acababa» solo)
            if error == "cupo":
                _gastar(raiz_p, 0, agotado=True)
            return {"error": error, "texto": ("el cupo de YouTube de hoy está gastado"
                                              if error == "cupo" else error)}
        ids = [((it.get("id") or {}).get("videoId")) for it in busqueda.get("items") or []]
        ids = [i for i in ids if i]
        total = _num((busqueda.get("pageInfo") or {}).get("totalResults")) or 0
        videos, error = (_api("videos", {"part": "statistics,snippet", "id": ",".join(ids)},
                              clave) if ids else ({"items": []}, ""))
        _gastar(raiz_p, 101 if ids else 100)
        if videos is None:
            return {"error": error, "texto": error}
        items = videos.get("items") or []
        canales_ids = sorted({(it.get("snippet") or {}).get("channelId") for it in items} - {None})
        subs_de = {}
        if canales_ids:
            canales, _e = _api("channels", {"part": "statistics", "id": ",".join(canales_ids)},
                               clave)
            _gastar(raiz_p, 1)
            for c in (canales or {}).get("items") or []:
                est = c.get("statistics") or {}
                subs_de[c.get("id")] = (None if est.get("hiddenSubscriberCount")
                                        else _num(est.get("subscriberCount")))
        ahora = dt.datetime.now(dt.timezone.utc)
        bruto = {"vistas": [], "dias": [], "subs": [], "titulos": [], "canales": [],
                 "ids": [], "total": total}
        for it in items:
            sn = it.get("snippet") or {}
            try:
                publicado = dt.datetime.fromisoformat(str(sn.get("publishedAt")).replace("Z", "+00:00"))
                dias = max(1, (ahora - publicado).days)
            except ValueError:
                dias = 365
            bruto["vistas"].append(_num((it.get("statistics") or {}).get("viewCount")) or 0)
            bruto["dias"].append(dias)
            bruto["subs"].append(subs_de.get(sn.get("channelId")))
            bruto["titulos"].append(str(sn.get("title") or "")[:120])
            bruto["canales"].append(str(sn.get("channelTitle") or "")[:80])
            bruto["ids"].append(it.get("id"))
    resultado = _medir_competencia(bruto)
    _a_cache(raiz_p, ck, resultado)
    return resultado


def _medir_competencia(b):
    vistas = b.get("vistas") or []
    if not vistas:
        return {"valor": 5, "nivel": "baja", "interes": 0, "mediana_vistas": 0,
                "mediana_vistas_dia": 0, "pequenos": 0, "recientes": 0,
                "total": b.get("total") or 0, "top": [], "vacia": True,
                "al": dt.datetime.now().strftime("%Y-%m-%d")}
    por_dia = [v / max(1, d) for v, d in zip(vistas, b.get("dias") or [])]
    med = statistics.median(vistas)
    med_dia = statistics.median(por_dia) if por_dia else 0
    pequenos = sum(1 for s in b.get("subs") or [] if s is not None and s < CANAL_PEQUENO)
    recientes = sum(1 for d in b.get("dias") or [] if d <= 90)
    base = max(0.0, min(100.0, (math.log10(med + 1) - 2) / 4 * 100))   # 100 vistas: 0 · 1M: 100
    valor = round(max(0.0, min(100.0, base - 5 * pequenos)))
    interes = round(max(0.0, min(100.0, math.log10(med_dia + 1) / 3 * 100)))  # 1.000/día: 100
    top = []
    for i in range(min(3, len(vistas))):
        top.append({"titulo": (b.get("titulos") or [""] * 10)[i],
                    "canal": (b.get("canales") or [""] * 10)[i],
                    "vistas": vistas[i], "subs": (b.get("subs") or [None] * 10)[i],
                    "url": f"https://www.youtube.com/watch?v={(b.get('ids') or [''] * 10)[i]}"})
    return {"valor": valor, "nivel": "alta" if valor >= 65 else "media" if valor >= 35 else "baja",
            "interes": interes, "mediana_vistas": int(med), "mediana_vistas_dia": round(med_dia, 1),
            "pequenos": pequenos, "recientes": recientes, "total": b.get("total") or 0,
            "top": top, "al": dt.datetime.now().strftime("%Y-%m-%d")}


def oportunidad(dem, comp):
    """0-100: hay quien la busca (demanda e interés) y no está copada."""
    if not comp or comp.get("error") or dem is None:
        return None
    return round(0.55 * dem + 0.20 * (comp.get("interes") or 0) + 0.25 * (100 - comp["valor"]))


def _cifra(n):
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M".replace(".", ",")
    if n >= 1000:
        return f"{round(n / 1000)} mil"
    return str(n)


def textos_competencia(comp):
    if not comp:
        return []
    if comp.get("error"):
        return [comp.get("texto") or "no se ha podido medir la competencia"]
    if comp.get("vacia"):
        return ["YouTube no devuelve vídeos con esta búsqueda: nadie compite, pero mira "
                "que la demanda sea de verdad"]
    t = [f"competencia {comp['nivel']}: los 10 primeros de YouTube tienen una mediana de "
         f"{_cifra(comp['mediana_vistas'])} vistas"]
    if comp.get("pequenos"):
        uno = comp["pequenos"] == 1
        t.append(f"{comp['pequenos']} de ellos {'es un canal pequeño' if uno else 'son canales pequeños'}"
                 f" (menos de {_cifra(CANAL_PEQUENO)} suscriptores): se puede entrar")
    return t


# ----------------------------------------------------------------- tu historial

def historial(frase, posts):
    """Cómo le fue a esta palabra en la cuenta. `posts`: [{red, vistas,
    palabra, gancho}] de lo publicado con cifras.
    -> {valor 0-100 | None, posts, veces, texto}"""
    posts = [p for p in posts or [] if isinstance(p.get("vistas"), (int, float))]
    if len(posts) < MINIMO_POSTS_CUENTA:
        return {"valor": None, "posts": 0, "veces": None,
                "texto": f"aún no hay bastantes publicaciones con métricas en la cuenta "
                         f"({len(posts)} de {MINIMO_POSTS_CUENTA})"}
    por_red = {}
    for p in posts:
        por_red.setdefault(p.get("red"), []).append(float(p["vistas"]))
    todas = statistics.median(float(p["vistas"]) for p in posts) or 1.0
    mediana_red = {r: (statistics.median(v) if len(v) >= 3 else todas) or 1.0
                   for r, v in por_red.items()}
    ts = terminos(frase)
    if not ts:
        return {"valor": None, "posts": 0, "veces": None, "texto": "sin palabra clave"}
    razones = []
    for p in posts:
        suyos = set(terminos(f"{p.get('palabra') or ''} {p.get('gancho') or ''}"))
        if 100 * sum(1 for t in ts if t in suyos) / len(ts) >= RELEVANTE:
            razones.append(float(p["vistas"]) / mediana_red.get(p.get("red"), todas))
    if len(razones) < MINIMO_POSTS_PALABRA:
        return {"valor": None, "posts": len(razones), "veces": None,
                "texto": (f"solo {len(razones)} publicación{'es' if len(razones) != 1 else ''} "
                          f"con esta palabra: hacen falta {MINIMO_POSTS_PALABRA} para fiarse")}
    veces = statistics.median(razones)
    valor = round(max(0.0, min(100.0, 50 + 25 * math.log2(max(veces, 0.01)))))
    cuanto = f"{veces:.1f}".replace(".", ",")
    return {"valor": valor, "posts": len(razones), "veces": round(veces, 2),
            "texto": (f"tus {len(razones)} publicaciones con esta palabra tienen {cuanto}× "
                      "las vistas normales de tu cuenta" + (
                          " (mejor que tu media)" if veces >= 1.15 else
                          " (peor que tu media)" if veces <= 0.85 else " (como tu media)"))}


# ------------------------------------------------------------------ la puntuación

def combinar(partes):
    """La media de las partes CON dato, con sus pesos. None si ninguna tiene."""
    con = [(PESOS[i], v) for i, v in partes.items() if v is not None]
    if not con:
        return None
    return round(sum(p * v for p, v in con) / sum(p for p, _ in con))


def candidata(frase, info, zona, raiz_p, posts, corpus=None, origen=""):
    """Una frase investigada (sin la competencia, que va aparte por el cupo)."""
    rel = relevancia(frase, info, zona, corpus)
    dem = demanda(frase, raiz_p)
    hist = historial(frase, posts) if posts is not None else None
    return {"frase": " ".join(str(frase).split())[:80], "origen": origen,
            "relevancia": rel, "demanda": dem, "competencia": None, "oportunidad": None,
            "historial": hist}


def _puntuar(c):
    dem = (c.get("demanda") or {}).get("valor")
    op = c.get("oportunidad")
    c["puntuacion"] = combinar({
        "relevancia": (c.get("relevancia") or {}).get("valor"),
        "demanda": op if op is not None else dem,
        "historial": (c.get("historial") or {}).get("valor")})
    return c


def investigar(info, ajustes, datos_video, raiz_p, posts=None, clave_yt="",
               espera_s=0.15):
    """La investigación de un vídeo: las frases candidatas, de las semillas del
    vídeo y lo que el buscador completa, solo las que el vídeo trata."""
    ajustes = ajustes or {}
    datos_video = datos_video or {}
    zona = str(ajustes.get("zona") or "")
    corpus = corpus_de(info, zona)
    avisos = []

    def limpia(x):
        return " ".join(str(x or "").split())[:80]

    semillas = []
    propia = limpia(datos_video.get("palabra_clave"))
    if propia:
        semillas.append((propia, "la tuya"))
    for frase, origen in ([(datos_video.get("palabra_propuesta"), "propuesta de Claude"),
                           (ajustes.get("palabra_clave"), "del proyecto")]
                          + [(s, "secundaria del proyecto")
                             for s in re.split(r"[,\n;]+", str(ajustes.get("secundarias") or ""))]):
        frase = limpia(frase)
        if not frase:
            continue
        if not es_relevante(frase, corpus=corpus):
            if origen in ("del proyecto",):
                avisos.append(f"«{frase}» (del proyecto) no se usa: el vídeo no trata de eso")
            continue
        semillas.append((frase, origen))
    if len(semillas) < 2:
        semillas += [(f, "del guion") for f in frases_del_video(info)]
    vistas, unicas = set(), []
    for frase, origen in semillas:
        if normal(frase) and normal(frase) not in vistas:
            vistas.add(normal(frase))
            unicas.append((frase, origen))
    unicas = unicas[:5]

    candidatas = []
    sugeridas = []
    for frase, origen in unicas:
        c = candidata(frase, info, zona, raiz_p, posts, corpus, origen)
        candidatas.append(c)
        for s in c["demanda"].get("sugerencias") or []:
            n = normal(s)
            if n in vistas or not 2 <= len(n.split()) <= 6:
                continue
            if relevancia(s, corpus=corpus)["valor"] is not None and es_relevante(s, corpus=corpus):
                vistas.add(n)
                sugeridas.append(s)
        if espera_s and not simulado() and HTTP is _http_real:
            time.sleep(espera_s)
    for s in sugeridas[:max(0, MAX_CANDIDATAS - len(candidatas))]:
        candidatas.append(candidata(s, info, zona, raiz_p, posts, corpus, "la gente busca"))
        if espera_s and not simulado() and HTTP is _http_real:
            time.sleep(espera_s)
    for c in candidatas:
        _puntuar(c)
    if clave_yt:
        orden = sorted(candidatas, key=lambda c: -(c.get("puntuacion") or 0))
        for c in [c for c in orden if es_relevante(c["frase"], corpus=corpus)][:MAX_COMPETENCIA]:
            comp = competencia(c["frase"], raiz_p, clave_yt)
            c["competencia"] = comp
            if comp and comp.get("error"):
                # cualquier fallo de la API para la tanda: si es la clave, las
                # demás frases fallarían igual
                avisos.append("el cupo de YouTube de hoy se ha gastado: el resto sin competencia"
                              if comp["error"] == "cupo" else
                              f"YouTube no ha contestado ({comp.get('texto') or comp['error']}): "
                              "la competencia queda sin dato; mira «Probar» en Configuración")
                break
            c["oportunidad"] = oportunidad((c["demanda"] or {}).get("valor"), comp)
            _puntuar(c)
    candidatas.sort(key=lambda c: (-(c.get("puntuacion") or -1), c["origen"] != "la tuya"))
    mejor = next((c for c in candidatas
                  if (c["relevancia"].get("valor") is None or c["relevancia"]["valor"] >= RELEVANTE)
                  and (c["demanda"].get("valor") or 0) >= 30), None)
    if mejor:
        mejor["recomendada"] = True
    sin_red = all(c["demanda"].get("valor") is None for c in candidatas)
    if sin_red and candidatas:
        avisos.append("el buscador no ha contestado: la demanda queda sin dato esta vez")
    return {"al": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "candidatas": candidatas,
            # «con_youtube»: hay datos de YouTube guardados (caducan a los 30 días)
            "con_youtube": any(c.get("competencia") and not c["competencia"].get("error")
                               for c in candidatas),
            "clave_youtube": bool(clave_yt), "avisos": avisos,
            "cupo": cupo(raiz_p) if clave_yt and raiz_p else None,
            "sin_corpus": not corpus.sabe}


def caducada(real, ahora=None):
    """¿Tiene más de 30 días? (los datos de YouTube no pueden guardarse más)."""
    try:
        al = dt.datetime.fromisoformat(str((real or {}).get("al")))
    except ValueError:
        return True
    return ((ahora or dt.datetime.now()) - al).total_seconds() > BORRA_S


def sin_youtube(real):
    """La investigación sin lo que vino de la API de YouTube (al caducar)."""
    real = json.loads(json.dumps(real or {}))
    for c in real.get("candidatas") or []:
        c["competencia"] = None
        c["oportunidad"] = None
        _puntuar(c)
    real["con_youtube"] = False
    real["youtube_caducado"] = True
    return real


def buscar(real, frase):
    """La candidata de la investigación que es esta frase (o None)."""
    n = normal(frase)
    if not n:
        return None
    for c in (real or {}).get("candidatas") or []:
        if normal(c.get("frase")) == n:
            return c
    return None


# -------------------------------------------------------------- la nota de una red

#: Los puntos de forma que dicen dónde está la palabra: entran en Relevancia.
PUNTOS_DE_SITIO = ("palabra_titulo", "palabra_primera", "palabra_descripcion")


def nota(forma, palabra, info, ajustes, real):
    """La nota SEO de una red: {nota, partes, puntos, forma, sin_investigar}.

    `forma` es lo de `publicar_seo.nota` (los puntos de siempre, con sus
    botones): los de sitio de la palabra cuentan dentro de Relevancia; el
    resto son detalles de forma que se enseñan y NO cuentan."""
    forma = forma or {"nota": 0, "puntos": []}
    puntos = list(forma.get("puntos") or [])
    if any(p.get("id") == "texto" for p in puntos):
        return {"nota": 0, "partes": [], "puntos": puntos, "forma": forma.get("nota", 0),
                "sin_investigar": not real}
    zona = str((ajustes or {}).get("zona") or "")
    partes = []

    # 1. relevancia y sitio
    sitio = [p for p in puntos if p.get("id") in PUNTOS_DE_SITIO]
    if not palabra:
        # el porqué lo dice el punto «palabra» de la forma, con su botón
        partes.append({"id": "relevancia", "nombre": NOMBRES_PARTE["relevancia"], "valor": 0,
                       "textos": []})
    else:
        rel = relevancia(palabra, info, zona)
        textos = []
        if rel["valor"] is None:
            textos.append("el vídeo no tiene guion ni material con que comprobar si trata de "
                          f"«{palabra}»")
        elif rel["valor"] >= RELEVANTE:
            textos.append(f"«{palabra}» es de este vídeo: sale en el guion o el material")
        else:
            textos.append(f"«{palabra}» casi no sale en el vídeo (faltan "
                          + ", ".join(f"«{f}»" for f in rel["faltan"][:4])
                          + "): quien la busque no encontrará lo que espera")
        hecho = [p for p in sitio if p.get("ok")]
        textos += [p["texto"] for p in sitio]
        sitio_v = round(100 * len(hecho) / len(sitio)) if sitio else None
        if rel["valor"] is None:
            valor = sitio_v
        elif sitio_v is None:
            valor = rel["valor"]
        else:
            # sin relevancia, el sitio no salva nada
            valor = round(rel["valor"] * (0.6 + 0.4 * sitio_v / 100))
        partes.append({"id": "relevancia", "nombre": NOMBRES_PARTE["relevancia"],
                       "valor": valor, "textos": textos})

    # 2. demanda (y competencia)
    c = buscar(real, palabra) if palabra else None
    if not palabra:
        partes.append({"id": "demanda", "nombre": NOMBRES_PARTE["demanda"], "valor": None,
                       "textos": ["sin palabra clave no hay búsqueda que medir"]})
    elif not real:
        partes.append({"id": "demanda", "nombre": NOMBRES_PARTE["demanda"], "valor": None,
                       "textos": ["sin investigar: pulsa «Investigar búsquedas» para saber si "
                                  "alguien la busca"]})
    elif not c:
        partes.append({"id": "demanda", "nombre": NOMBRES_PARTE["demanda"], "valor": None,
                       "textos": ["esta palabra no estaba en la última investigación: vuelve a "
                                  "pulsar «Investigar búsquedas»"]})
    else:
        dem = c.get("demanda") or {}
        op = c.get("oportunidad")
        valor = op if op is not None else dem.get("valor")
        textos = list(dem.get("textos") or [])
        if dem.get("nivel"):
            textos.insert(0, f"demanda {dem['nivel']}")
        textos += textos_competencia(c.get("competencia"))
        if op is not None:
            textos.append(f"oportunidad {op}/100 (se busca y no está copada)" if op >= 60 else
                          f"oportunidad {op}/100")
        partes.append({"id": "demanda", "nombre": NOMBRES_PARTE["demanda"], "valor": valor,
                       "textos": textos})

    # 3. tu historial
    h = (c or {}).get("historial") if c else None
    if h:
        partes.append({"id": "historial", "nombre": NOMBRES_PARTE["historial"],
                       "valor": h.get("valor"), "textos": [h.get("texto") or ""]})
    else:
        partes.append({"id": "historial", "nombre": NOMBRES_PARTE["historial"], "valor": None,
                       "textos": ["sale al investigar: cómo le fue a esta palabra en tu cuenta"
                                  if palabra else "sin palabra clave"]})

    total = combinar({p["id"]: p["valor"] for p in partes})
    return {"nota": total or 0, "partes": partes, "puntos": puntos,
            "forma": forma.get("nota", 0), "sin_investigar": not real,
            "con_dato": sum(1 for p in partes if p["valor"] is not None)}


def nota_como_texto(notas):
    """Las notas en texto para Claude: la nota, sus partes y la forma aparte."""
    lineas = []
    for red, n in (notas or {}).items():
        partes = "; ".join(f"{p['nombre']} {p['valor'] if p['valor'] is not None else 'sin dato'}"
                           f" ({' · '.join(t for t in p['textos'] if t)[:240]})"
                           for p in n.get("partes") or [])
        forma = [p["texto"] for p in n.get("puntos", []) if not p["ok"]
                 and p.get("id") not in PUNTOS_DE_SITIO]
        lineas.append(f"- {red}: {n.get('nota')}/100" + (f" — {partes}" if partes else "")
                      + (f". Forma (no cuenta): {'; '.join(forma)}" if forma else ""))
    return "\n".join(lineas) or "—"


def resumen_para_claude(real, palabra, cuantas=6):
    """Las búsquedas reales para la instrucción de Claude (texto)."""
    if not real or not real.get("candidatas"):
        return ""
    lineas = []
    for c in real["candidatas"][:cuantas]:
        rel = (c.get("relevancia") or {}).get("valor")
        if rel is not None and rel < RELEVANTE:
            continue
        dem = c.get("demanda") or {}
        trozos = [f"demanda {dem.get('nivel') or 'sin dato'}"]
        comp = c.get("competencia")
        if comp and not comp.get("error"):
            trozos.append(f"competencia {comp.get('nivel')}")
        h = c.get("historial") or {}
        if h.get("veces") is not None:
            trozos.append(f"en tu cuenta {str(h['veces']).replace('.', ',')}× lo normal")
        marca = " ← la que se usa" if normal(c["frase"]) == normal(palabra) else ""
        lineas.append(f"- «{c['frase']}»: " + ", ".join(trozos) + marca)
    return "\n".join(lineas)

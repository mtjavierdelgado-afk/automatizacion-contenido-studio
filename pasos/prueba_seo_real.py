"""Prueba del SEO de verdad de Publicar (`pasos/seo_real.py`, rama seo-real).

Sin red y sin claves de verdad: el autocompletado y la API de YouTube los
contesta un doble (`seo_real.HTTP`). Comprueba:

  1. la relevancia: una palabra que el vídeo no trata no se usa ni se pide a
     Claude ni va en las etiquetas de YouTube (lo que el dueño vio el 20-10);
  2. el autocompletado: su forma (JSON y JSONP), Perú en español, la demanda,
     la caché (7 días) y que nada pase de 30 días guardado;
  3. la competencia con la API de YouTube: lo que mide, el cupo del día, el
     cupo gastado y que la clave no salga en ningún mensaje;
  4. tu historial: frente a la mediana de cada red de la cuenta, con mínimos;
  5. la nota en tres partes, con la forma aparte y sin contar;
  6. la investigación entera en la ficha de publicar, y que caduque lo de
     YouTube a los 30 días.

    python pasos/prueba_seo_real.py
"""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.parse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="seo_real_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
for _v in ("ESTUDIO_SIMULAR", "ESTUDIO_SEO_SIMULADO", "YOUTUBE_API_KEY", "UPLOADPOST_API_KEY"):
    os.environ.pop(_v, None)

import seo_real as SR  # noqa: E402
import publicar_seo as S  # noqa: E402
import publicar as P  # noqa: E402

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


#: Un vídeo de una fiesta infantil con consolas (de un proyecto de alquiler
#: de consolas que también da clases de guitarra: la palabra del proyecto NO
#: es de este vídeo).
INFO = {"pid": "fiesta", "nombre": "Fiesta infantil con consolas", "formato": "vertical",
        "duracion_s": 40, "montado": True, "mp4_huella": "x", "capitulos_base": [],
        "titulo": "La fiesta infantil más divertida",
        "material": "Alquiler de consolas para fiestas infantiles en casa, en Lima.",
        "guion": [{"id": "B001", "texto": "Organiza la fiesta infantil de tu hijo con consolas."},
                  {"id": "B002", "texto": "Las consolas llegan a tu casa listas para jugar."},
                  {"id": "B003", "texto": "Juegos para niños de todas las edades en la fiesta infantil."}]}
GUITARRA = {"palabra_clave": "clases de guitarra", "zona": "Lima, Perú",
            "secundarias": "profesor de guitarra, consolas para fiestas"}


class Doble:
    """Contesta como el autocompletado y la API de YouTube, y apunta lo pedido."""

    def __init__(self):
        self.pedidas = []
        self.sugerencias = {}          # (fuente, q) -> [..]
        self.caido = False
        self.cupo_gastado = False
        self.clave = "AIzaSECRETA1234567890"

    def __call__(self, url, timeout=6):
        self.pedidas.append(url)
        if self.caido:
            return 0, "sin conexión (URLError)"
        partes = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(partes.query))
        if "suggestqueries" in partes.netloc:
            fuente = "youtube" if q.get("ds") == "yt" else "google"
            lista = self.sugerencias.get((fuente, q["q"]))
            if lista is None:
                lista = [q["q"], q["q"] + " en lima", q["q"] + " para niños"]
            if fuente == "youtube":
                # la forma JSONP de client=youtube, para ver que se entiende
                return 200, f'window.google.ac.h({json.dumps([q["q"], [[s, 0] for s in lista]])})'
            return 200, json.dumps([q["q"], lista])
        if "googleapis" in partes.netloc:
            if self.cupo_gastado:
                return 403, json.dumps({"error": {"message": f"quota exceeded for key {q.get('key')}",
                                                  "errors": [{"reason": "quotaExceeded"}]}})
            if partes.path.endswith("/search"):
                return 200, json.dumps({"pageInfo": {"totalResults": 12000},
                                        "items": [{"id": {"videoId": f"v{i}"}} for i in range(10)]})
            if partes.path.endswith("/videos"):
                hace = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                return 200, json.dumps({"items": [
                    {"id": f"v{i}", "statistics": {"viewCount": str(5000 * (i + 1))},
                     "snippet": {"channelId": f"c{i % 5}", "title": f"Vídeo {i}",
                                 "channelTitle": f"Canal {i % 5}", "publishedAt": hace}}
                    for i in range(10)]})
            if partes.path.endswith("/channels"):
                return 200, json.dumps({"items": [
                    {"id": f"c{i}", "statistics": {"subscriberCount": str(3000 if i < 2 else 500000)}}
                    for i in range(5)]})
        return 404, ""


def con_doble():
    doble = Doble()
    SR.HTTP = doble
    return doble


def prueba_relevancia():
    seccion("1] relevancia: lo que el vídeo no trata no se usa")
    rel = SR.relevancia("clases de guitarra", INFO, "Lima")
    igual(rel["valor"], 0, "«clases de guitarra» no sale en un vídeo de una fiesta con consolas")
    igual(SR.relevancia("alquiler de consolas en Lima", INFO, "Lima")["valor"], 100,
          "«alquiler de consolas en Lima» sí (consola/consolas cuentan como la misma)")
    igual(SR.relevancia("consolas en Lima", INFO, "")["valor"], 100,
          "la zona vale aunque el vídeo solo la diga en el material")
    ok(not SR.es_relevante("fiesta infantil precio", INFO),
       "una frase con una palabra que el vídeo no dice («precio») no es de este vídeo")
    vacio = {"pid": "x", "nombre": "Vídeo", "guion": []}
    igual(SR.relevancia("clases de guitarra", vacio)["valor"], None,
          "un vídeo sin guion ni material: sin dato (no se puede saber)")
    ok(SR.es_relevante("clases de guitarra", vacio), "y sin dato se da por buena, como antes")
    # la palabra que manda en el vídeo
    igual(S.palabra_del_video({}, GUITARRA, INFO), "",
          "la palabra del proyecto que el vídeo no trata NO es la del vídeo")
    igual(S.palabra_del_video({"palabra_propuesta": "consolas para fiesta infantil"}, GUITARRA, INFO),
          "consolas para fiesta infantil", "en su lugar, la que propuso Claude al leer el vídeo")
    igual(S.palabra_del_video({"palabra_clave": "mi frase"}, GUITARRA, INFO), "mi frase",
          "la que escribe la persona manda siempre")
    igual(S.palabra_del_video({}, GUITARRA), "clases de guitarra",
          "sin el vídeo a mano (la cuenta de lo publicado), la de antes")
    igual(S.palabra_del_video({}, dict(GUITARRA, palabra_clave="alquiler de consolas"), INFO),
          "alquiler de consolas", "la del proyecto, si el vídeo sí la trata")
    # lo que se pide a Claude y las etiquetas
    bloque = S.bloque_instruccion(GUITARRA, "", ["instagram"], info=INFO,
                                  busquedas="- «fiesta infantil en lima»: demanda alta")
    ok("profesor de guitarra" not in bloque and "consolas para fiestas" in bloque,
       "las secundarias que el vídeo no trata no se piden a Claude; las que sí, sí")
    ok("NUNCA metas una palabra clave de algo que el vídeo no trata" in bloque,
       "y se le dice que no fuerce palabras que el vídeo no trata")
    ok("fiesta infantil en lima" in bloque and "no tiene palabra clave todavía" in bloque,
       "con las búsquedas reales y, sin palabra, que elija la del vídeo")
    etiquetas = S.etiquetas_youtube(GUITARRA, "fiesta infantil", ["fiesta"], INFO)
    ok("clases de guitarra" not in etiquetas and "profesor de guitarra" not in etiquetas
       and "fiesta infantil" in etiquetas, f"las etiquetas de YouTube, sin lo que no es del vídeo: {etiquetas}")
    ok("clases de guitarra" in S.etiquetas_youtube(GUITARRA, "x", [], None),
       "sin el vídeo, las de antes")
    ok("busquedas_reales" in S.INSTRUCCION_OPTIMIZAR and "{guion}" in S.INSTRUCCION_OPTIMIZAR,
       "«Optimizar SEO» lleva el guion y las búsquedas reales")


def prueba_autocompletado():
    seccion("2] autocompletado: forma, demanda, caché y 30 días")
    raiz = os.path.join(CARPETA, "auto")
    doble = con_doble()
    doble.sugerencias[("youtube", "fiesta")] = ["fiesta infantil", "fiesta de cumpleaños"]
    lista = SR.sugerencias("fiesta infantil", "youtube", raiz)
    ok(lista and lista[0] == "fiesta infantil", f"el JSONP de YouTube se entiende: {lista}")
    url = doble.pedidas[-1]
    ok("gl=pe" in url and "hl=es" in url and "ds=yt" in url, "se pregunta a Perú en español, en YouTube")
    igual(SR.sugerencias("fiesta infantil", "google", raiz)[1], "fiesta infantil en lima",
          "y el JSON de Google")
    antes = len(doble.pedidas)
    SR.sugerencias("fiesta infantil", "youtube", raiz)
    igual(len(doble.pedidas), antes, "la segunda vez sale de la caché (no se vuelve a preguntar)")
    dem = SR.demanda("fiesta infantil", raiz)
    ok(dem["youtube"] >= 85, f"YouTube la propone al escribir «fiesta…»: demanda alta ({dem})")
    ok(dem["nivel"] in ("alta", "media") and dem["textos"], "con su nivel y su porqué")
    doble.sugerencias[("youtube", "zzz qqq")] = []
    doble.sugerencias[("google", "zzz qqq")] = []
    doble.sugerencias[("youtube", "zzz")] = []
    igual(SR.demanda("zzz qqq", raiz)["nivel"], "casi nula", "lo que nadie busca, casi nula")
    doble.caido = True
    sin = SR.demanda("algo sin cache", raiz)
    igual(sin["valor"], None, "sin red: la demanda queda sin dato, no se inventa")
    doble.caido = False
    # la caché: viejo a los 7 días, borrado a los 30
    ruta = os.path.join(raiz, "_sistema", "publicar", "seo_cache.json")
    datos = json.load(open(ruta, encoding="utf-8"))
    clave = next(k for k in datos if k.startswith("sug|youtube|fiesta infantil"))
    datos[clave]["t"] = time.time() - 8 * 86400
    datos["sug|youtube|viejisima"] = {"t": time.time() - 31 * 86400, "v": ["x"]}
    json.dump(datos, open(ruta, "w", encoding="utf-8"))
    antes = len(doble.pedidas)
    SR.sugerencias("fiesta infantil", "youtube", raiz)
    igual(len(doble.pedidas), antes + 1, "a los 7 días se vuelve a preguntar")
    ok("sug|youtube|viejisima" not in json.load(open(ruta, encoding="utf-8")),
       "y lo que pasa de 30 días se borra al guardar")


def prueba_competencia():
    seccion("3] competencia con la API de YouTube: lo que mide y el cupo")
    raiz = os.path.join(CARPETA, "comp")
    doble = con_doble()
    igual(SR.competencia("fiesta infantil", raiz, ""), None, "sin clave no se pregunta nada")
    comp = SR.competencia("fiesta infantil", raiz, doble.clave)
    igual(comp["mediana_vistas"], 27500, "la mediana de vistas de los 10 primeros")
    igual(comp["pequenos"], 4, "cuántos son de canales pequeños (menos de 10 mil suscriptores)")
    igual(comp["recientes"], 10, "y cuántos son de los últimos 90 días")
    ok(comp["nivel"] in ("alta", "media", "baja") and len(comp["top"]) == 3, "con su nivel y los tres primeros")
    url = next(u for u in doble.pedidas if "/search" in u)
    ok("regionCode=PE" in url and "relevanceLanguage=es" in url, "la búsqueda es la de Perú en español")
    c = SR.cupo(raiz)
    igual(c["usadas"], 102, "el cupo apunta 102 unidades (búsqueda, vídeos y canales)")
    antes = len(doble.pedidas)
    SR.competencia("fiesta infantil", raiz, doble.clave)
    igual(len(doble.pedidas), antes, "la misma frase otra vez, de la caché: no gasta cupo")
    op = SR.oportunidad(80, comp)
    ok(op is not None and 0 <= op <= 100, f"la oportunidad junta demanda e interés y resta competencia: {op}")
    doble.cupo_gastado = True
    gastado = SR.competencia("otra frase", raiz, doble.clave)
    igual(gastado.get("error"), "cupo", "con el cupo gastado lo dice")
    ok(SR.cupo(raiz)["agotado"] and SR.cupo(raiz)["busquedas"] == 0,
       "y no se vuelve a intentar hoy")
    ok(doble.clave not in json.dumps(gastado, ensure_ascii=False), "la clave no sale en el mensaje")
    antes = len(doble.pedidas)
    SR.competencia("y otra", raiz, doble.clave)
    igual(len(doble.pedidas), antes, "cupo agotado: ni se pregunta")
    doble.cupo_gastado = False


def prueba_historial():
    seccion("4] tu historial: frente a lo normal de cada red de la cuenta")
    igual(SR.historial("fiesta infantil", [{"red": "tiktok", "vistas": 100}])["valor"], None,
          "con menos de 5 publicaciones medidas, sin dato")
    posts = [{"red": "tiktok", "vistas": 1000, "palabra": "otra cosa", "gancho": ""} for _ in range(6)]
    posts += [{"red": "tiktok", "vistas": 3000, "palabra": "fiesta infantil", "gancho": ""} for _ in range(3)]
    posts += [{"red": "youtube", "vistas": 50, "palabra": "x", "gancho": ""} for _ in range(4)]
    h = SR.historial("fiesta infantil", posts)
    ok(h["valor"] is not None and h["valor"] > 50 and h["veces"] > 1.5,
       f"tres posts con la palabra que triplican lo normal de su red: {h}")
    ok("mejor que tu media" in h["texto"], "y lo dice en claro")
    h2 = SR.historial("clases de guitarra", posts)
    igual(h2["valor"], None, "una palabra sin posts suyos: sin dato")
    ok("hacen falta 3" in h2["texto"], "y dice cuántos hacen falta")


def prueba_nota():
    seccion("5] la nota en tres partes, con la forma aparte")
    raiz = os.path.join(CARPETA, "nota")
    con_doble()
    textos = {"descripcion": "Fiesta infantil con consolas en casa\nTe las llevamos.",
              "cta": "", "hashtags": ["fiesta"]}
    forma = S.nota("instagram", textos, {}, GUITARRA, {}, INFO, "fiesta infantil")
    sin = SR.nota(forma, "fiesta infantil", INFO, GUITARRA, None)
    igual([p["id"] for p in sin["partes"]], ["relevancia", "demanda", "historial"],
          "tres partes: Relevancia, Demanda y Tu historial")
    igual(sin["con_dato"], 1, "sin investigar, solo la relevancia tiene dato")
    ok("Investigar búsquedas" in " ".join(sin["partes"][1]["textos"]), "y la demanda dice cómo conseguirlo")
    igual(sin["nota"], 100, "la palabra es del vídeo y está en la primera línea: la relevancia es 100")
    ok(any(not p["ok"] for p in sin["puntos"]), "los detalles de forma (CTA, hashtags…) siguen saliendo")
    igual(sin["nota"], SR.nota(dict(forma, puntos=[p for p in forma["puntos"]
                                                    if p["id"] in SR.PUNTOS_DE_SITIO]),
                               "fiesta infantil", INFO, GUITARRA, None)["nota"],
          "y NO cuentan: con o sin ellos, la misma nota")
    mala = SR.nota(S.nota("instagram", dict(textos, descripcion="Clases de guitarra en Lima\n."), {},
                          GUITARRA, {}, INFO, "clases de guitarra"),
                   "clases de guitarra", INFO, GUITARRA, None)
    ok(mala["nota"] < 50 and "casi no sale en el vídeo" in mala["partes"][0]["textos"][0],
       f"una palabra que el vídeo no trata hunde la nota aunque esté bien puesta: {mala['nota']}")
    real = SR.investigar(INFO, GUITARRA, {"palabra_clave": "fiesta infantil"}, raiz, posts=[])
    con = SR.nota(forma, "fiesta infantil", INFO, GUITARRA, real)
    igual(con["con_dato"], 2, "investigada: también la demanda")
    ok(con["partes"][1]["valor"] is not None and con["partes"][1]["textos"],
       f"con su valor y su porqué: {con['partes'][1]}")
    vacia = SR.nota(S.nota("tiktok", {}, {}, {}, {}, INFO, ""), "", INFO, {}, None)
    igual(vacia["nota"], 0, "sin texto, 0")
    txt = SR.nota_como_texto({"instagram": con})
    ok("Relevancia" in txt and "Demanda" in txt and "0-100" not in txt, "y en texto para Claude")


def prueba_investigar_en_la_ficha():
    seccion("6] «Investigar búsquedas» en la ficha, y lo de YouTube caduca a los 30 días")
    raiz = os.path.join(CARPETA, "ficha")
    doble = con_doble()
    doble.sugerencias[("youtube", "fiesta infantil")] = ["fiesta infantil", "fiesta infantil en casa",
                                                         "fiesta infantil precio",
                                                         "clases de guitarra para niños"]
    P.guardar_ficha(raiz, "fiesta", {"textos": {"instagram": {
        "descripcion": "Fiesta infantil con consolas\nTe las llevamos.", "cta": "Escríbenos",
        "hashtags": ["fiesta", "consolas", "lima", "cumple", "niños"]}}})
    # la clave de YouTube, en el almacén (como la guarda Configuración)
    import claves as C  # noqa: PLC0415
    C.guardar({"youtube": {"clave": doble.clave}})
    igual(P.clave_youtube(), doble.clave, "la clave de YouTube se lee del almacén")
    ok(C.resumen()["youtube"]["puesta"] and doble.clave not in json.dumps(C.resumen()),
       "y la pantalla solo ve que está puesta (y su cola), nunca la clave")
    P.lanzar_investigar(raiz, INFO, GUITARRA, [], "", en_hilo=False)
    f = P.ficha(raiz, INFO, GUITARRA)
    real = f["seo"]["real"]
    frases = [c["frase"] for c in real["candidatas"]]
    ok(frases, f"la investigación queda en la ficha: {frases}")
    ok("clases de guitarra" not in frases and not any("guitarra" in x for x in frases),
       "ni la palabra del proyecto ni ninguna sugerencia que el vídeo no trate")
    ok("fiesta infantil precio" not in frases, "ni las que añaden algo que el vídeo no dice")
    ok(any("no se usa" in a for a in real["avisos"]), f"y dice por qué no usa la del proyecto: {real['avisos']}")
    ok(any(c.get("recomendada") for c in real["candidatas"]), "una sale como la recomendada")
    ok(any(c.get("competencia") for c in real["candidatas"]), "con la clave, se mide la competencia")
    ok(f["seo"]["proyecto_fuera"], "la ficha dice que la palabra del proyecto se ha dejado fuera")
    ok(f["seo"]["con_youtube"] and f["seo"]["cupo_youtube"]["usadas"] > 0,
       "y lo que va gastado del cupo de YouTube hoy")
    ok(doble.clave not in json.dumps(f, ensure_ascii=False), "la ficha no lleva la clave por ningún sitio")
    # usar una frase: es la palabra del vídeo, y la nota la tiene investigada
    frase = real["candidatas"][0]["frase"]
    P.guardar_ficha(raiz, "fiesta", {"palabra_clave": frase})
    f = P.ficha(raiz, INFO, GUITARRA)
    igual(f["seo"]["palabra"], frase, "«Usar» deja la frase como palabra clave del vídeo")
    igual(f["seo"]["notas"]["instagram"]["con_dato"] >= 2, True,
          "y la nota de cada red ya tiene la demanda medida")
    # las etiquetas de YouTube que se mandarían
    comp = P.componer("youtube", {"descripcion": f"{frase}\nx", "titulo": frase, "hashtags": []},
                      GUITARRA, INFO, None, P._leer_video(raiz, "fiesta"))
    ok("clases de guitarra" not in (comp["campos"].get("tags[]") or []),
       "lo que se manda a YouTube no lleva la palabra del proyecto que el vídeo no trata")
    # 30 días: fuera lo de YouTube
    with P._lock("fiesta"):
        datos = P._leer_video(raiz, "fiesta")
        datos["seo_real"]["al"] = (dt.datetime.now() - dt.timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%S")
        P._escribir(P._ruta_video(raiz, "fiesta"), datos)
    f = P.ficha(raiz, INFO, GUITARRA)
    ok(all(c.get("competencia") is None for c in f["seo"]["real"]["candidatas"]),
       "a los 30 días la ficha ya no enseña lo de YouTube")
    guardado = P._leer_video(raiz, "fiesta")["seo_real"]
    ok(all(c.get("competencia") is None for c in guardado["candidatas"]) and guardado.get("youtube_caducado"),
       "y tampoco queda guardado (la política de la API: 30 días como mucho)")
    # sin red: se dice, no se inventa
    doble.caido = True
    P.guardar_ficha(raiz, "fiesta", {"palabra_clave": "otra cosa nueva de consolas"})
    try:
        os.remove(os.path.join(raiz, "_sistema", "publicar", "seo_cache.json"))
    except OSError:
        pass
    P.lanzar_investigar(raiz, INFO, GUITARRA, [], "", en_hilo=False)
    real = P.ficha(raiz, INFO, GUITARRA)["seo"]["real"]
    ok(any("no ha contestado" in a for a in real["avisos"]), "sin red, la investigación lo dice")
    doble.caido = False
    C.guardar({"youtube": {"clave": ""}})
    igual(P.clave_youtube(), "", "«Quitar» la clave la quita")
    # en simulado (las suites del Studio), sin salir a ningún sitio
    SR.HTTP = SR._http_real
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        ok(SR.simulado() and SR.sugerencias("fiesta", "youtube", None)[0] == "fiesta",
           "con ESTUDIO_SIMULAR no se sale a internet")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)


def prueba_probar_clave():
    seccion("7] «Probar» la clave de YouTube, sin enseñarla")
    import comprobar_claves as CC  # noqa: PLC0415

    class Resp:
        def __init__(self, codigo, datos):
            self.status_code, self._d = codigo, datos
            self.text = json.dumps(datos)

        def json(self):
            return self._d

    secreta = "AIzaQUENOSESALGA123456"

    def falso(metodo, url, **kw):
        clave = kw["params"]["key"]
        if clave == secreta:
            return Resp(200, {"items": []}), ""
        if clave == "cupo":
            return Resp(403, {"error": {"message": "The request cannot be completed because you have exceeded your quota."}}), ""
        return Resp(400, {"error": {"message": f"API key not valid: {clave}"}}), ""
    original = CC._pedir
    CC._pedir = falso
    try:
        igual(CC.probar_youtube(secreta)["estado"], "ok", "una clave buena da ok")
        igual(CC.probar_youtube("")["estado"], "sin_clave", "sin clave, lo dice (es opcional)")
        mala = CC._tachar([CC.probar_youtube("AIzaMALAMALAMALA1234")], {"youtube": {"clave": "AIzaMALAMALAMALA1234"}})[0]
        ok(mala["estado"] == "mal" and "AIzaMALA" not in mala["mensaje"] and "YouTube Data API v3" in mala["mensaje"],
           f"una mala dice qué activar, sin repetir la clave: {mala['mensaje']}")
        ok("cupo" in CC.probar_youtube("cupo")["mensaje"], "el cupo gastado no es una clave mala")
    finally:
        CC._pedir = original
    igual(CC.NOMBRES.get("youtube"), "YouTube (búsquedas SEO)", "con su nombre en el resumen")


def main():
    print("PRUEBA DEL SEO DE VERDAD")
    try:
        prueba_relevancia()
        prueba_autocompletado()
        prueba_competencia()
        prueba_historial()
        prueba_nota()
        prueba_investigar_en_la_ficha()
        prueba_probar_clave()
    finally:
        SR.HTTP = SR._http_real
        shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"SEO REAL OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

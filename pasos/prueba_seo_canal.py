"""Prueba de la fase 3 del SEO (`pasos/seo_canal.py`, rama seo-real-3).

Sin red ni cuentas de verdad: Google (OAuth, YouTube Analytics, la API de
datos) y Google Trends los contesta un doble (`seo_canal.HTTP`). Comprueba:

  1. el cliente de Google en el almacén de claves: el secreto y el token no
     bajan nunca a la pantalla, y cambiar de cliente olvida la conexión;
  2. conectar el canal: la URL de Google, el intento que caduca, el cambio del
     código por el token, y que el secreto no sale en ningún mensaje;
  3. cuando Google corta (app «en prueba», 7 días): se apunta y se dice;
  4. YouTube Analytics: las búsquedas que traen vistas al canal y «cómo te
     encontraron» de un vídeo; el id de un enlace de YouTube;
  5. Google Trends: la respuesta con su prefijo, sube/baja, y un 429 que se
     dice y no se guarda;
  6. todo junto en Publicar: «Investigar búsquedas» con el canal y Trends,
     «Cómo te encontraron» y desconectar.

    python pasos/prueba_seo_canal.py
"""
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

CARPETA = tempfile.mkdtemp(prefix="seo_canal_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
for _v in ("ESTUDIO_SIMULAR", "ESTUDIO_SEO_SIMULADO", "YOUTUBE_API_KEY", "UPLOADPOST_API_KEY"):
    os.environ.pop(_v, None)

import claves as C  # noqa: E402
import seo_real as SR  # noqa: E402
import seo_canal as SC  # noqa: E402
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


CLIENTE = "12345-abc.apps.googleusercontent.com"
SECRETO = "GOCSPX-secretoMUYsecreto123"
VUELTA = "https://estudio.ejemplo.pe/v2/api/publicar/youtube/oauth/vuelta"

INFO = {"pid": "fiesta", "nombre": "Fiesta infantil con consolas", "formato": "vertical",
        "duracion_s": 40, "montado": True, "mp4_huella": "x", "capitulos_base": [],
        "titulo": "La fiesta infantil más divertida",
        "material": "Alquiler de consolas para fiestas infantiles en casa, en Lima.",
        "guion": [{"id": "B001", "texto": "Organiza la fiesta infantil de tu hijo con consolas."},
                  {"id": "B002", "texto": "Las consolas llegan a tu casa listas para jugar."},
                  {"id": "B003", "texto": "Juegos para niños de todas las edades en la fiesta infantil."}]}
AJUSTES = {"palabra_clave": "fiesta infantil", "zona": "Lima, Perú"}


class Google:
    """El doble de Google: OAuth, Analytics, la API de datos y Trends."""

    def __init__(self):
        self.pedidas = []
        self.refresh_malo = False
        self.trends_429 = False
        self.token_eco_secreto = False

    def __call__(self, metodo, url, datos=None, cabeceras=None, timeout=10):
        self.pedidas.append((metodo, url, dict(datos or {}), dict(cabeceras or {})))
        partes = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(partes.query))
        if url.startswith(SC.URL_TOKEN):
            if datos.get("grant_type") == "authorization_code":
                if self.token_eco_secreto:
                    return 400, json.dumps({"error": "invalid_request",
                                            "error_description": f"bad secret {datos['client_secret']}"})
                if datos.get("code") != "codigo-bueno":
                    return 400, json.dumps({"error": "invalid_grant", "error_description": "Bad Request"})
                return 200, json.dumps({"access_token": "acc-1", "refresh_token": "ref-1", "expires_in": 3600})
            if self.refresh_malo:
                return 400, json.dumps({"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
            return 200, json.dumps({"access_token": "acc-2", "expires_in": 3600})
        if "revoke" in url:
            return 200, "{}"
        if partes.path.endswith("/channels") and q.get("mine") == "true":
            return 200, json.dumps({"items": [{"id": "UC123", "snippet": {"title": "EstadoPlay"}}]})
        if url.startswith(SC.URL_ANALYTICS):
            filtros = q.get("filters", "")
            if "insightTrafficSourceDetail" in q.get("dimensions", ""):
                if "video==" in filtros:
                    return 200, json.dumps({"columnHeaders": [{"name": "insightTrafficSourceDetail"}, {"name": "views"}],
                                            "rows": [["fiesta infantil con consolas", 41], ["consolas lima", 12]]})
                return 200, json.dumps({"columnHeaders": [{"name": "insightTrafficSourceDetail"}, {"name": "views"}],
                                        "rows": [["fiesta infantil en casa", 300], ["clases de guitarra", 120],
                                                 ["consolas para fiestas", 80]]})
            return 200, json.dumps({"columnHeaders": [{"name": "views"}, {"name": "averageViewDuration"},
                                                      {"name": "averageViewPercentage"}],
                                    "rows": [[520, 19.6, 43.27]]})
        if "trends.google.com" in url:
            if self.trends_429:
                return 429, "Too Many Requests"
            if "/api/explore" in url:
                return 200, ")]}'\n" + json.dumps({"widgets": [{"id": "TIMESERIES", "token": "tok",
                                                                "request": {"x": 1}}]})
            if "/widgetdata/multiline" in url:
                req = json.loads(q.get("req") or "{}")
                n = 5
                puntos = []
                for semana in range(52):
                    # la primera frase sube; las demás bajan
                    puntos.append({"value": [10 + semana if i == 0 else max(0, 80 - semana) for i in range(n)]})
                return 200, ")]}',\n" + json.dumps({"default": {"timelineData": puntos}, "_req": req})
            return 200, ""
        return 404, ""


class Sugerencias:
    """El doble del autocompletado (la firma de `seo_real.HTTP`)."""

    def __call__(self, url, timeout=6):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        if "suggestqueries" in url:
            return 200, json.dumps([q["q"], [q["q"], q["q"] + " en casa"]])
        return 404, ""


def prueba_claves():
    seccion("1] el cliente de Google en el almacén de claves")
    try:
        C.guardar({"youtube_oauth": {"cliente_id": "esto-no-es-un-id", "secreto": "x"}})
        ok(False, "un ID de cliente que no es de Google se rechaza")
    except C.ErrorClaves as fallo:
        ok("apps.googleusercontent.com" in str(fallo), f"un ID de cliente que no es de Google se rechaza: {fallo}")
    r = C.guardar({"youtube_oauth": {"cliente_id": CLIENTE, "secreto": SECRETO}})
    yo = r["youtube_oauth"]
    ok(yo["puesta"] and not yo["conectado"], "guardado: puesto y sin conectar")
    ok(SECRETO not in json.dumps(r), "la pantalla no ve el secreto")
    r = C.guardar({"youtube_oauth": {"cliente_id": CLIENTE, "secreto": C.CONSERVAR}})
    igual(C.leer()["youtube_oauth"]["secreto"], SECRETO, "«conservar» deja el secreto que había")
    C.conexion_youtube(refresh="ref-x", canal="Canal X")
    C.guardar({"openai": []})
    igual(C.leer()["youtube_oauth"]["refresh"], "ref-x", "guardar otra clave no toca la conexión")
    C.guardar({"youtube_oauth": {"cliente_id": "999-otro.apps.googleusercontent.com", "secreto": "otro"}})
    igual(C.leer()["youtube_oauth"]["refresh"], "", "cambiar de cliente olvida la conexión (era de otro)")
    try:
        C.guardar({"youtube_oauth": {"cliente_id": "777-x.apps.googleusercontent.com", "secreto": C.CONSERVAR}})
        ok(False, "otro cliente con el secreto de antes se rechaza")
    except C.ErrorClaves:
        ok(True, "otro cliente con el secreto de antes se rechaza (cada cliente, su secreto)")
    C.guardar({"youtube_oauth": {"cliente_id": CLIENTE, "secreto": SECRETO,
                                 "refresh": "inyectado", "canal": "falso"}})
    igual(C.leer()["youtube_oauth"]["refresh"], "", "la pantalla no puede escribir el token")
    ok("refresh" not in json.dumps(C.resumen()["youtube_oauth"]) or
       C.resumen()["youtube_oauth"].get("refresh") is None, "y el resumen no lo trae")


def prueba_conectar():
    seccion("2] conectar el canal")
    g = Google()
    SC.HTTP = g
    try:
        SC.empezar("https://otro.sitio/robar")
        ok(False, "una dirección de vuelta que no es la del Studio se rechaza")
    except SC.ErrorCanal:
        ok(True, "una dirección de vuelta que no es la del Studio se rechaza")
    url = SC.empezar(VUELTA)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    igual(SC.volver_de(q["state"]), "https://estudio.ejemplo.pe/v2/",
          "«Volver al Studio» sale de la vuelta del intento (con su /v2/)")
    ok(url.startswith(SC.URL_AUTH) and q["client_id"] == CLIENTE and q["redirect_uri"] == VUELTA,
       "la URL de Google lleva el cliente y la vuelta")
    ok("yt-analytics.readonly" in q["scope"] and q["access_type"] == "offline" and q["prompt"] == "consent",
       "pide solo leer (Analytics y el canal), sin caducar al cerrar, y el token de refresco")
    ok(SECRETO not in url, "el secreto no va en la URL")
    try:
        SC.terminar("estado-inventado", "codigo-bueno")
        ok(False, "un estado que no es de un intento se rechaza")
    except SC.ErrorCanal as fallo:
        ok("ya no vale" in str(fallo), "un estado que no es de un intento se rechaza")
    r = SC.terminar(q["state"], "codigo-bueno", CARPETA)
    ok(r["youtube_oauth"]["conectado"] and r["youtube_oauth"]["canal"] == "EstadoPlay",
       "con el código bueno: conectado, con el nombre del canal")
    token = next(p for p in g.pedidas if p[1].startswith(SC.URL_TOKEN))
    igual(token[2].get("redirect_uri"), VUELTA, "el cambio del código usa la misma vuelta")
    ok("ref-1" not in json.dumps(C.resumen()) and C.leer()["youtube_oauth"]["refresh"] == "ref-1",
       "el token se guarda en el almacén y no baja a la pantalla")
    try:
        SC.terminar(q["state"], "codigo-bueno")
        ok(False, "un intento se usa una sola vez")
    except SC.ErrorCanal:
        ok(True, "un intento se usa una sola vez")
    # un error de Google que repite el secreto
    g.token_eco_secreto = True
    url = SC.empezar(VUELTA)
    estado_ = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["state"]
    try:
        SC.terminar(estado_, "codigo-x")
        ok(False, "un error de Google se dice")
    except SC.ErrorCanal as fallo:
        ok(SECRETO not in str(fallo), f"un error de Google se dice sin el secreto: {fallo}")
    g.token_eco_secreto = False
    # el intento caduca
    url = SC.empezar(VUELTA)
    estado_ = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["state"]
    SC._INTENTOS[estado_]["t"] -= SC.CADUCA_INTENTO_S + 1
    try:
        SC.terminar(estado_, "codigo-bueno")
        ok(False, "un intento de hace más de 15 minutos no vale")
    except SC.ErrorCanal:
        ok(True, "un intento de hace más de 15 minutos no vale")


def prueba_caido():
    seccion("3] cuando Google corta la conexión")
    g = Google()
    SC.HTTP = g
    SC._TOKEN.clear()
    g.refresh_malo = True
    try:
        SC.busquedas_del_canal(CARPETA, forzar=True)
        ok(False, "un token caducado se dice")
    except SC.ErrorCanal as fallo:
        ok(fallo.caido and "Volver a conectar" in str(fallo), f"un token caducado se dice: {fallo}")
    ok(bool(C.resumen()["youtube_oauth"]["caido"]), "y queda apuntado para la pantalla")
    # una conexión nueva mientras otro hilo refrescaba con la vieja: no se marca
    C.conexion_youtube(caido="")
    original = SC.oauth
    llamadas = {"n": 0}

    def cambia_en_medio():
        llamadas["n"] += 1
        datos = original()
        if llamadas["n"] > 2:   # conectado() y _acceso leen el viejo; al fallar, ya hay otro
            datos["refresh"] = "ref-nuevo"
        return datos
    SC.oauth = cambia_en_medio
    SC._TOKEN.clear()
    try:
        SC.busquedas_del_canal(CARPETA, forzar=True)
    except SC.ErrorCanal:
        pass
    finally:
        SC.oauth = original
    igual(C.resumen()["youtube_oauth"]["caido"], "",
          "si el token cambió mientras tanto (se volvió a conectar), no se marca cortada")
    g.refresh_malo = False
    SC.busquedas_del_canal(CARPETA, forzar=True)
    igual(C.resumen()["youtube_oauth"]["caido"], "", "cuando vuelve a funcionar, se borra la marca")


def prueba_analytics():
    seccion("4] YouTube Analytics: lo que trae vistas")
    g = Google()
    SC.HTTP = g
    filas = SC.busquedas_del_canal(CARPETA, forzar=True)
    igual(filas[0], {"termino": "fiesta infantil en casa", "vistas": 300}, "las búsquedas que traen vistas al canal")
    pedida = next(p for p in g.pedidas if p[1].startswith(SC.URL_ANALYTICS))
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(pedida[1]).query))
    ok(q["filters"] == "insightTrafficSourceType==YT_SEARCH" and q["ids"] == "channel==MINE",
       "solo las de la búsqueda de YouTube, de tu canal")
    ok(pedida[3].get("Authorization", "").startswith("Bearer "), "con el token, en la cabecera")
    antes = len(g.pedidas)
    SC.busquedas_del_canal(CARPETA)
    igual(len(g.pedidas), antes, "la segunda vez, de la caché (un día)")
    for url, vid in (("https://www.youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
                     ("https://youtube.com/shorts/ABCDEFGHIJK?feature=x", "ABCDEFGHIJK"),
                     ("https://youtu.be/a1b2c3d4e5f", "a1b2c3d4e5f"), ("https://tiktok.com/x", "")):
        igual(SC.id_de_youtube(url), vid, f"el id de {url}")
    res = SC.como_te_encontraron(CARPETA, "abcdefghijk")
    ok(res["vistas"] == 520 and res["porcentaje_visto"] == 43.3 and res["busquedas"][0]["vistas"] == 41,
       f"«cómo te encontraron»: vistas, % visto y búsquedas del vídeo: {res}")
    c = {"frase": "fiesta infantil en casa", "historial": {"valor": None, "texto": "x"}}
    SC.con_el_canal(c, filas)
    ok(c["historial"]["valor"] and c["historial"]["valor"] >= 60 and "ya te trae 300 vistas" in c["historial"]["texto"],
       f"una frase que ya te trae vistas sube «Tu historial»: {c['historial']}")
    c2 = {"frase": "piñatas de cumpleaños", "historial": {"valor": None}}
    SC.con_el_canal(c2, filas)
    igual(c2["historial"]["valor"], None, "una que no, no")


def prueba_trends():
    seccion("5] Google Trends (experimental)")
    g = Google()
    SC.HTTP = g
    raiz = os.path.join(CARPETA, "trends")
    t = SC.tendencias(["fiesta infantil", "consolas lima"], raiz)
    a, b = t["frases"]["fiesta infantil"], t["frases"]["consolas lima"]
    igual(a["sentido"], "sube", "la que crece semana a semana: sube")
    igual(b["sentido"], "baja", "la que cae: baja")
    ok(a["youtube"] and a["google"], "en Google y en YouTube")
    explore = next(p for p in g.pedidas if "/api/explore" in p[1])
    req = json.loads(dict(urllib.parse.parse_qsl(urllib.parse.urlparse(explore[1]).query))["req"])
    ok(req["comparisonItem"][0]["geo"] == "PE" and req["comparisonItem"][0]["time"] == "today 12-m",
       "Perú, el último año")
    antes = len(g.pedidas)
    SC.tendencias(["consolas lima", "fiesta infantil"], raiz)
    igual(len(g.pedidas), antes, "la misma consulta, de la caché")
    g.trends_429 = True
    t = SC.tendencias(["otra frase"], raiz)
    ok("429" in t["error"] and not t["frases"]["otra frase"]["sentido"], "un 429 se dice y la tendencia queda sin dato")
    g.trends_429 = False
    t = SC.tendencias(["otra frase"], raiz)
    ok(t["frases"]["otra frase"]["sentido"], "y no se guardó: la siguiente vez se vuelve a preguntar")
    igual(SC._medir([0.0] * 52), None, "una frase de nicho en ceros es «sin dato», no «estable»")
    igual(SC._medir([0.0] * 50 + [1.0, 0.0]), None, "y casi en ceros tampoco sube «+100 %»")
    c = {"frase": "x", "demanda": {"valor": 50, "nivel": "baja", "textos": []}}
    SC.con_tendencia(c, {"sentido": "sube", "texto": "sube en YouTube"})
    ok(c["demanda"]["valor"] == 58 and "Google Trends" in c["demanda"]["textos"][-1],
       "si sube, la demanda sube un poco y lo dice")


def prueba_en_publicar():
    seccion("6] en Publicar: investigar con el canal, cómo te encontraron y desconectar")
    g = Google()
    SC.HTTP = g
    SR.HTTP = Sugerencias()
    raiz = os.path.join(CARPETA, "publicar")
    P.guardar_ficha(raiz, "fiesta", {"textos": {"instagram": {
        "descripcion": "Fiesta infantil con consolas\nTe las llevamos.", "cta": "Escríbenos",
        "hashtags": ["fiesta", "consolas", "lima", "cumple", "niños"]}}})
    P.lanzar_investigar(raiz, INFO, AJUSTES, [], "", en_hilo=False)
    f = P.ficha(raiz, INFO, AJUSTES)
    real = f["seo"]["real"]
    origenes = {c["frase"]: c["origen"] for c in real["candidatas"]}
    igual(origenes.get("fiesta infantil en casa"), "ya te trae vistas",
          "lo que ya te trae vistas (y el vídeo trata) entra como candidata")
    ok("clases de guitarra" not in origenes, "lo que te trae vistas pero el vídeo no trata, no")
    ok(any(c.get("tendencia") for c in real["candidatas"]), "las mejores llevan su tendencia")
    ok(real.get("con_canal"), "y la investigación dice que usó tu canal")
    ok(f["seo"]["canal"]["conectado"] and f["seo"]["canal"]["canal"] == "EstadoPlay", "la ficha sabe que está conectado")
    ok(SECRETO not in json.dumps(f) and "ref-1" not in json.dumps(f), "la ficha no lleva el secreto ni el token")
    igual(f["seo"]["en_youtube"], False, "sin publicar en YouTube, no hay «Cómo te encontraron»")
    try:
        P.lanzar_encontraron(raiz, INFO, en_hilo=False)
        ok(False, "«Cómo te encontraron» sin publicar se dice")
    except P.ErrorPublicar as fallo:
        ok("no está publicado" in str(fallo), "«Cómo te encontraron» sin publicar se dice")
    with P._lock("fiesta"):
        datos = P._leer_video(raiz, "fiesta")
        datos["envios"].append({"red": "youtube", "estado": "publicado",
                                "url": "https://www.youtube.com/shorts/abcdefghijk", "cuando": "2026-10-10T10:00"})
        P._escribir(P._ruta_video(raiz, "fiesta"), datos)
    P.lanzar_encontraron(raiz, INFO, en_hilo=False)
    f = P.ficha(raiz, INFO, AJUSTES)
    ok(f["seo"]["en_youtube"] and f["seo"]["encontraron"]["busquedas"][0]["termino"] == "fiesta infantil con consolas",
       "publicado: «Cómo te encontraron» trae las búsquedas del vídeo")
    # desconectar
    r = SC.desconectar(raiz)
    ok(not r["youtube_oauth"]["conectado"] and any("revoke" in p[1] for p in g.pedidas),
       "desconectar quita el permiso en Google y en el almacén")
    ok(not any(k.startswith("canal|") for k in SC._leer(raiz)), "y olvida lo que vino del canal")
    try:
        P.lanzar_encontraron(raiz, INFO, en_hilo=False)
        ok(False, "sin canal, «Cómo te encontraron» lo dice")
    except P.ErrorPublicar as fallo:
        ok("conecta" in str(fallo), "sin canal, «Cómo te encontraron» lo dice")
    P.lanzar_investigar(raiz, INFO, AJUSTES, [], "", en_hilo=False)
    real = P.ficha(raiz, INFO, AJUSTES)["seo"]["real"]
    ok(not real.get("con_canal") and real["candidatas"], "sin canal, «Investigar búsquedas» sigue funcionando")
    # en simulado (las suites del Studio)
    SC.HTTP = SC._http_real
    SR.HTTP = SR._http_real
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        ok(SC.simulado() and SC.tendencias(["a b"], None)["frases"]["a b"]["sentido"],
           "con ESTUDIO_SIMULAR no se sale a internet")
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)


def main():
    print("PRUEBA DEL SEO · FASE 3 (canal y Trends)")
    try:
        prueba_claves()
        prueba_conectar()
        prueba_caido()
        prueba_analytics()
        prueba_trends()
        prueba_en_publicar()
    finally:
        SC.HTTP = SC._http_real
        SR.HTTP = SR._http_real
        shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"SEO CANAL OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

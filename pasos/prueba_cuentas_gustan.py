"""Prueba de «CUENTAS QUE TE GUSTAN» 2 (rama cuentas-gustan-2, 01-11-2026).

Sin red, sin claves de verdad, sin Claude y sin pagar nada:

  1. las cifras de una cuenta (`cuentas_metricas`): mediana, «me gusta» y
     comentarios por 100 vistas, vistas por rango de duración, dudosos y la
     duración sugerida solo con 8 vídeos o más;
  2. la duración con ffprobe sobre un vídeo de verdad hecho aquí, y completarla
     con Apify (simulado): pide permiso antes, respeta el tope y solo rellena
     la duración;
  3. varias cuentas juntas (`cuentas_conjunto`): de 2 a 10, el plan con el
     cupo, que con el cupo al 90 % avisa y sigue si se dice que sí, las pruebas comprobadas;
  4. los temas (`temas_cuentas`): duplicados unidos, cruce con la Parrilla y
     los vídeos, variedad (3 por cuenta, 2 por fórmula, espacio distinto),
     aprobar/editar/descartar, «Incluir igualmente»;
  5. escribir SOLO los aprobados (`parrilla.lanzar(tipo='temas')`): un guion
     por tema, su origen, el aviso de frases copiadas;
  6. el Studio por HTTP (si hay fastapi), en modo simulado.

    python pasos/prueba_cuentas_gustan.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="cuentas_gustan_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
os.environ["ESTUDIO_SIMULAR"] = "1"
os.makedirs(os.environ["ESTUDIO_SECRETOS"], exist_ok=True)

import consumo_claude as CC  # noqa: E402
import cuentas_ajenas as C  # noqa: E402
import cuentas_conjunto as CJ  # noqa: E402
import cuentas_metricas as M  # noqa: E402
import parrilla as P  # noqa: E402
import temas_cuentas as T  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLA {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, f"{texto} (obtenido {obtenido!r}, esperado {esperado!r})")


def seccion(titulo):
    print(f"\n[{titulo}]")


def lanza(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as fallo:                              # noqa: BLE001
        return fallo
    return None


def _video(i, vistas, me_gusta, duracion=None, texto=None, **extra):
    v = {"id": f"v{i}", "url": f"https://www.instagram.com/reel/COD{i}/", "texto": texto or f"vídeo {i} de prueba",
         "fecha": "2026-10-01", "vistas": vistas, "me_gusta": me_gusta, "comentarios": vistas // 100 if vistas is not None else None,
         "duracion_s": duracion}
    v.update(extra)
    return v


# ------------------------------------------------------------ 1. las cifras

def prueba_metricas():
    seccion("1] las cifras de una cuenta, relativas a ella")
    videos = [_video(i, 1000, 50, 20 if i < 5 else 45) for i in range(10)]
    videos.append(_video(10, 9000, 9, 20))                                   # promoción
    videos.append(_video(11, 4000, 200, 20, texto="Colab con @otra: el truco"))  # colaboración
    videos.append(_video(12, 3000, 150, 20, coautores=["amiga"]))
    datos = {"red": "instagram", "usuario": "ana", "videos": videos, "traida": "2026-11-01"}
    m = M.metricas(datos)
    igual(m["mediana_vistas"], 1000.0, "la mediana de vistas (la media se la llevaría el viral)")
    v10 = m["videos"][10]
    igual((v10["rel"], v10["mg100"]), (9.0, 0.1), "×9 su mediana y 0,1 «me gusta» por 100 vistas")
    ok(v10["dudoso"] and "promoción" in v10["motivo"], f"muchas vistas y casi nadie reacciona: dudoso ({v10['motivo']})")
    ok(m["videos"][11]["dudoso"] and "colaboración" in m["videos"][11]["motivo"], "el texto dice colab: dudoso")
    ok(m["videos"][12]["dudoso"] and "@amiga" in m["videos"][12]["motivo"], "con coautores: dudoso, y dice con quién")
    ok(not m["videos"][0]["dudoso"], "un vídeo normal no es dudoso")
    igual(m["dudosos"], 3, "tres dudosos")
    igual(m["mediana_mg100"], 5.0, "la vara de «me gusta» se mide sin los dudosos")
    igual(m["videos"][0]["com100"], 1.0, "comentarios por 100 vistas")
    rangos = {r["rango"]: r for r in m["rangos"]}
    igual((rangos["15–30 s"]["videos"], rangos["30–60 s"]["videos"]), (5, 5),
          "vistas por rango de duración, sin los dudosos")
    igual(m["con_duracion"], 13, "cuántos tienen duración")
    ok(m["mejor_rango"] is not None, "con 10 vídeos con duración, sugiere un rango")
    pocos = M.metricas({"videos": [_video(i, 1000 + i, 50, 20) for i in range(7)]})
    igual(pocos["mejor_rango"], None, "con menos de 8 vídeos con duración, ninguna sugerencia (decisión del dueño)")
    sin = M.metricas({"videos": [_video(i, None, None) for i in range(3)]})
    ok(sin["mediana_vistas"] is None and all(v["rel"] is None for v in sin["videos"]), "sin vistas, sin cifras (sin inventar)")
    texto = M.linea_video(m["videos"][10], "ana")
    ok(texto.startswith("@ana#11 ·") and "DUDOSO" in texto and "×9,0 su mediana" in texto,
       "la línea para Claude lleva su referencia, lo relativo y el aviso")
    resumen = C.resumen_para_claude(datos)
    ok("Su mediana: 1.000 vistas" in resumen and "Vistas por duración" in resumen and "@ana#13" in resumen,
       "el resumen para Claude: mediana, rangos y TODOS los vídeos")
    ok(M.nombre_tipo("reel") == "Reel" and M.nombre_tipo("nada") == "", "los nombres de los tipos")


# --------------------------------------------------------- 2. la duración

def prueba_duracion():
    seccion("2] la duración: ffprobe sin bajar el vídeo, y Apify si falta")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and shutil.which("ffprobe"):
        ruta = os.path.join(CARPETA, "corto.mp4")
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=3", "-y", ruta],
                       check=True, timeout=60)
        segundos = C.duracion_ffprobe(ruta)
        ok(segundos is not None and abs(segundos - 3.0) < 0.2, f"ffprobe lee la duración ({segundos} s)")
        videos = [{"id": "a", "media_url": ruta}, {"id": "b", "media_url": "", "duracion_s": None},
                  {"id": "c", "media_url": ruta, "duracion_s": 12}]
        igual(C.duraciones_con_ffprobe(videos), 1, "solo mide los que no tienen duración y traen enlace")
        igual((videos[0].get("duracion_fuente"), videos[2]["duracion_s"]), ("ffprobe", 12), "y no pisa lo que ya había")
    else:
        print("  (sin ffmpeg/ffprobe aquí: se salta la medida real)")
    igual(C.duracion_ffprobe("ftp://no"), None, "un enlace raro no se mide")
    igual(C.duracion_ffprobe(os.path.join(CARPETA, "no_existe.mp4")), None, "un vídeo que no está: None, sin error")

    raiz = os.path.join(CARPETA, "dur")
    os.makedirs(raiz)
    C.guardar_claves({"meta_token": "EAABx", "ig_id": "1", "apify_token": "apify_api_x"})
    d = C.leer(raiz, "instagram", "estudio_ana", 10)
    igual(d["fuente"], "instagram_oficial", "Instagram por la vía oficial (simulada)")
    ok(all(not v.get("duracion_s") for v in d["videos"]) and not any("media_url" in v for v in d["videos"]),
       "sin duración, y el enlace caducable no se guarda")
    p = C.plan_duraciones(raiz, "instagram", "estudio_ana")
    ok(p["se_puede"] and p["faltan"] == len(d["videos"]) and p["coste_usd"] > 0, f"el plan: faltan {p['faltan']}, ≈{p['coste_usd']} $")
    f = lanza(C.completar_duraciones, raiz, "instagram", "estudio_ana")
    ok(isinstance(f, C.ErrorCuentas) and f.codigo == 402 and f.pide_pago, "sin «pagar», pide permiso con el precio")
    ok(C.gasto_del_mes(raiz) == 0, "y no ha gastado nada")
    vistas_antes = [v["vistas"] for v in d["videos"]]
    t = C.lanzar_duraciones(raiz, "instagram", "estudio_ana", pagar=True, en_hilo=False)
    igual(t["estado"], "listo", "con «pagar», completa")
    d2 = C.cuenta(raiz, "instagram", "estudio_ana")
    ok(all(v.get("duracion_s") for v in d2["videos"]), "todos con duración")
    igual([v["vistas"] for v in d2["videos"]], vistas_antes, "y las demás cifras no cambian")
    ok(C.gasto_del_mes(raiz) > 0, "el gasto queda apuntado")
    igual(C.plan_duraciones(raiz, "instagram", "estudio_ana")["faltan"], 0, "ya no falta ninguna")
    C.guardar_claves({"tope_usd": 0.0001})
    d3 = C.leer(raiz, "instagram", "estudio_bea", 10)
    p = C.plan_duraciones(raiz, "instagram", "estudio_bea")
    ok(not p["se_puede"] and "tope" in p["motivo"], f"pasado el tope, no se ofrece ({p['motivo']})")
    ok(lanza(C.completar_duraciones, raiz, "instagram", "estudio_bea", True) is not None and d3, "ni se puede forzar")
    C.guardar_claves({"tope_usd": 5})
    p = C.plan_duraciones(raiz, "tiktok", "x", datos={"videos": [{"duracion_s": None}]})
    ok(not p["se_puede"] and "vuelve a traer" in p["motivo"], "en TikTok la duración llega con la lectura")
    c = C.cuenta_con_metricas(raiz, "instagram", "estudio_ana")
    ok(c["metricas"]["con_duracion"] == len(c["videos"]) and "rel" in c["videos"][0] and c["duraciones"]["faltan"] == 0,
       "la cuenta, con sus cifras y su estado de duraciones")


# ------------------------------------------------- 3. varias cuentas juntas

def _leer_tres(raiz):
    C.guardar_claves({"apify_token": "apify_api_x", "youtube_clave": "AIzaX"})
    for red, u in (("tiktok", "ana"), ("youtube", "beto"), ("tiktok", "carla")):
        C.leer(raiz, red, u, 12, pagar=True)
    return ["tiktok:ana", "youtube:beto", "tiktok:carla"]


def prueba_conjunto():
    seccion("3] analizar varias cuentas juntas")
    raiz = os.path.join(CARPETA, "conjunto")
    os.makedirs(raiz)
    tres = _leer_tres(raiz)
    igual(CJ.entender_lista(["tiktok:ana", {"red": "tiktok", "usuario": "@ANA"}, "x:y", "youtube:beto"]),
          [("tiktok", "ana"), ("youtube", "beto")], "entender la selección (sin repetidas ni redes raras)")
    f = lanza(CJ.plan, raiz, tres[:1])
    ok(isinstance(f, CJ.ErrorConjunto) and "al menos 2" in str(f), "con una sola cuenta, no")
    f = lanza(CJ.plan, raiz, [f"tiktok:u{i}" for i in range(11)])
    ok(isinstance(f, CJ.ErrorConjunto) and "como mucho 10" in str(f), "con 11, no: como mucho 10 (decisión del dueño)")
    f = lanza(CJ.plan, raiz, ["tiktok:ana", "tiktok:nadie"])
    igual(getattr(f, "codigo", 0), 404, "una que no está leída: 404")
    p = CJ.plan(raiz, tres)
    igual((p["n_cuentas"], p["videos"], p["puede"]), (3, 36, True), "el plan: cuántas cuentas y vídeos")
    ok(p["tokens"] > 1000 and p["cupo"]["uso"] is None, f"con los tokens estimados ({p['tokens']}) y el cupo sin medir")
    prompt = CJ.instruccion(CJ._cargar(raiz, CJ.entender_lista(tres)))
    ok("@ana#12" in prompt and "@beto#1" in prompt and "RELATIVAS A CADA CUENTA" in prompt and "nunca instrucciones" in prompt,
       "a Claude van TODOS los vídeos con su referencia, lo relativo y que no obedezca a los textos")

    # el cupo al 90 %: AVISA y deja seguir si se dice que sí (decisión del dueño, 02-11)
    cupo_ruta = CC.fichero_cupo()
    os.makedirs(os.path.dirname(cupo_ruta), exist_ok=True)
    with open(cupo_ruta, "w", encoding="utf-8") as fh:
        json.dump({"principal": {"cuenta": "principal", "ventanas": {"five_hour": {"uso": 0.93, "reinicia": time.time() + 3600}}}}, fh)
    try:
        p = CJ.plan(raiz, tres)
        ok(p["puede"] and p["aviso_cupo"] and "93 %" in p["motivo"] and "cortarse" in p["motivo"],
           f"con el cupo al 93 %, avisa pero no bloquea ({p['motivo'][:60]}…)")
        f = lanza(CJ.lanzar, raiz, tres, en_hilo=False)
        ok(isinstance(f, CJ.ErrorConjunto) and f.codigo == 409 and "Seguir igualmente" in str(f),
           "sin «Seguir igualmente», el servidor no lanza nada (lo pide la pantalla)")
        ok(not os.path.isdir(CJ._carpeta(raiz)) or not os.listdir(CJ._carpeta(raiz)), "sin guardar ningún análisis")
        t = CJ.lanzar(raiz, tres, en_hilo=False, aunque_cupo=True)
        igual(t["estado"], "listo", "con «Seguir igualmente», se analiza")
        f = lanza(T.plan, raiz, "cl_cupo", t["analisis"], 3)
        ok(f is None, "y el plan de proponer temas tampoco se para")
        igual(T.plan(raiz, "cl_cupo", t["analisis"], 3)["aviso_cupo"], True, "solo avisa")
        f = lanza(T.lanzar_propuesta, raiz, "cl_cupo", t["analisis"], 3, en_hilo=False)
        ok(isinstance(f, T.ErrorTemas) and "Seguir igualmente" in str(f), "proponer sin el sí: lo pide")
        tp = T.lanzar_propuesta(raiz, "cl_cupo", t["analisis"], 3, en_hilo=False, aunque_cupo=True)
        igual(tp["estado"], "listo", "y con el sí, propone")
    finally:
        os.remove(cupo_ruta)
    shutil.rmtree(CJ._carpeta(raiz), ignore_errors=True)

    t = CJ.lanzar(raiz, tres, en_hilo=False)
    igual(t["estado"], "listo", "el análisis (simulado) acaba")
    a = CJ.analisis(raiz, t["analisis"])
    r = a["resultado"]
    ok(r["formulas_comunes"] and len(r["formulas_comunes"][0]["cuentas"]) >= 2, "una fórmula común, con pruebas de varias cuentas")
    ok(all(p["url"] for f in r["formulas_comunes"] for p in f["pruebas"]), "cada prueba lleva el enlace del vídeo")
    ok(r["temas_libres"] and all(p["ref"] != "@nadie#99" for p in r["temas_libres"][0]["pruebas"]),
       "una referencia que no existe se quita")
    igual(CJ.ultimo(raiz, list(reversed(tres)))["id"], a["id"], "el último análisis de esa misma selección (en cualquier orden)")
    igual(CJ.ultimo(raiz, tres[:2]), None, "otra selección no lo reusa")
    limpio = CJ.limpiar({"formulas_comunes": [{"nombre": "X", "pruebas": ["@ana#2"]}],
                         "temas_saturados": [{"tema": "Y", "pruebas": ["@ana#999"]}]},
                        CJ._cargar(raiz, CJ.entender_lista(tres)))
    ok(limpio["formulas_unicas"] and not limpio["formulas_comunes"], "una «común» con pruebas de una sola cuenta pasa a «única»")
    igual((limpio["temas_saturados"], limpio["quitadas"]), ([], 1), "y una conclusión sin pruebas válidas no se enseña")
    dud = [k for k, v in CJ.indice_de_videos(CJ._cargar(raiz, CJ.entender_lista(tres))).items() if v["dudoso"]]
    igual(CJ.pruebas_validas([f"@{dud[0]}"], CJ.indice_de_videos(CJ._cargar(raiz, CJ.entender_lista(tres)))), [],
          "un vídeo dudoso no sirve de prueba")
    ok(isinstance(lanza(CJ.leer_json_de, "lo siento"), CJ.ErrorConjunto), "una respuesta sin JSON: error claro")
    return raiz, a


# ------------------------------------------------------------ 4. los temas

def prueba_temas(raiz, a):
    seccion("4] proponer temas: duplicados, cruce, variedad")
    cid = "cl_prueba_1"
    ok(isinstance(lanza(T.proponer, raiz, "_sin", a["id"]), T.ErrorTemas), "sin proyecto, no se proponen temas")
    ok(isinstance(lanza(T.plan, raiz, cid, a["id"], 99), T.ErrorTemas), "más de 30 temas, no")
    P._anadir_textos(raiz, cid, "", "Ya hechos", [P._guion_simulado(1, "Simulador de carreras para bodas",
                                                                       "invitados aburridos con carreras", "adaptar")], {"tipo": "pedir"})
    videos = [{"id": "v1", "nombre": "Baile con sensores", "texto": "clases monótonas en el gimnasio, baile con sensores"}]
    p = T.plan(raiz, cid, a["id"], 6, videos)
    igual((p["existentes"], p["puede"]), (2, True), "el plan cuenta lo que ya tiene el proyecto (un guion y un vídeo)")
    d = T.proponer(raiz, cid, a["id"], 6, videos)
    temas = d["temas"]
    por_tema = {t["tema"]: t for t in temas}
    ok("Torneo relámpago de karaoke, versión para empresas" not in por_tema
       and por_tema["Torneo relámpago de karaoke"].get("unido_con"), "el duplicado redactado de otra forma se une")
    ok(por_tema["Simulador de carreras para bodas"]["grupo"] == "repetido"
       and "Simulador" in por_tema["Simulador de carreras para bodas"]["cruce"]["con"], "lo que ya está en la Parrilla: repetido, con cuál")
    ok(por_tema["Baile con sensores"]["cruce"]["nivel"] in ("repetido", "parecido")
       and por_tema["Baile con sensores"]["cruce"]["tipo"] == "video", "y se cruza también con los vídeos ya creados")
    propuesta = [t for t in temas if t["grupo"] == "propuesta"]
    ok(1 <= len(propuesta) <= 6, f"como mucho los que se pidieron ({len(propuesta)})")
    cuentas = {}
    formulas = {}
    for t in propuesta:
        cuentas[t["referencias"][0]["cuenta"]] = cuentas.get(t["referencias"][0]["cuenta"], 0) + 1
        formulas[t["formula"]] = formulas.get(t["formula"], 0) + 1
    ok(max(cuentas.values()) <= 3 and max(formulas.values()) <= 2, f"variedad: ≤3 por cuenta {cuentas}, ≤2 por fórmula {formulas}")
    espacios = [T._clave_corta(t["espacio"]) for t in propuesta]
    igual(len(espacios), len(set(espacios)), "un espacio distinto en cada tema")
    ok(all(t["referencias"] and t["referencias"][0]["url"] for t in temas), "cada tema con sus vídeos de referencia")
    ok(all(t["duracion"] for t in propuesta), "duración sugerida (hay 8 vídeos o más con ese dato)")
    ok(any(t["grupo"] == "variedad" and t["motivo"] for t in temas), "los que no entran por variedad dicen por qué")

    t0 = propuesta[0]
    d = T.editar(raiz, cid, t0["id"], {"gancho": "Un gancho mío", "estado": "aprobado"})
    t = next(x for x in d["temas"] if x["id"] == t0["id"])
    igual((t["gancho"], t["estado"], t["editado"]), ("Un gancho mío", "aprobado", True), "editar y aprobar un tema")
    rep = next(x for x in temas if x["grupo"] == "repetido")
    ok(isinstance(lanza(T.editar, raiz, cid, rep["id"], {"estado": "aprobado"}), T.ErrorTemas),
       "un repetido no se aprueba sin «Incluir igualmente»")
    d = T.editar(raiz, cid, rep["id"], {"incluir": True})
    igual(next(x for x in d["temas"] if x["id"] == rep["id"])["grupo"], "propuesta", "«Incluir igualmente» lo mete en la propuesta")
    T.editar(raiz, cid, propuesta[1]["id"], {"estado": "descartado"})
    if len(propuesta) > 2:
        T.editar(raiz, cid, propuesta[2]["id"], {"estado": "aprobado"})
    ok(isinstance(lanza(T.editar, raiz, cid, t0["id"], {"tema": " "}), T.ErrorTemas), "el tema no queda vacío")
    ok(isinstance(lanza(T.editar, raiz, cid, "t99", {}), T.ErrorTemas), "un tema que no existe: error")
    return cid


# ----------------------------------------------- 5. escribir los aprobados

def prueba_escribir(raiz, cid):
    seccion("5] escribir SOLO los aprobados, con su origen")
    datos, lista = T.para_escribir(raiz, cid)
    aprobados = [t for t in datos["temas"] if t["estado"] == "aprobado"]
    igual(len(lista), len(aprobados), "solo los aprobados")
    ok(lista[0]["fuentes"] and lista[0]["origen"]["propuesta"] == datos["id"], "con los textos originales (para no copiarlos) y su origen")
    t = P.lanzar(raiz, cid, "temas", {"temas": lista, "modo": "adaptar", "nombre": "Ideas de cuentas"}, en_hilo=False)
    igual((t["estado"], len(t["guiones"])), ("listo", len(lista)), "un guion por tema aprobado")
    g = P.leer(raiz, cid, t["guiones"][0])
    o = g["origen"]
    ok(o["tipo"] == "temas" and o["cuentas"] and o["videos"] and o["formula"] and o["analisis_al"],
       "cada guion guarda su origen: cuentas, vídeos, fórmula y fecha del análisis")
    ok(o.get("avisos_copia"), f"el que repite una frase de un vídeo original lleva el aviso ({o.get('avisos_copia')})")
    g2 = P.leer(raiz, cid, t["guiones"][-1])
    ok(len(t["guiones"]) >= 2 and g2["origen"]["tema_id"] != o["tema_id"], "y cada uno el SUYO")
    d = T.leer(raiz, cid)
    ok(all(x["guion"] for x in d["temas"] if x["estado"] == "aprobado"), "los temas quedan marcados como escritos")
    ok(isinstance(lanza(T.para_escribir, raiz, cid), T.ErrorTemas), "y no se vuelven a escribir")
    igual(P.frases_copiadas("hola mundo uno dos tres cuatro cinco seis siete ocho nueve",
                            ["dijo uno dos tres cuatro cinco seis siete ocho y se fue"]),
          ["uno dos tres cuatro cinco seis siete ocho"], "las frases copiadas: 8 palabras seguidas")
    igual(P.frases_copiadas("uno dos tres cuatro cinco seis siete", ["uno dos tres cuatro cinco seis siete"]), [],
          "7 palabras no cuentan")
    igual(P.frases_copiadas("Ünó DOS tres, cuatro cinco seis siete ocho", ["uno dos tres cuatro cinco seis siete ocho"]),
          ["uno dos tres cuatro cinco seis siete ocho"], "sin mirar tildes, mayúsculas ni comas")


# ------------------------------------------------------------ 6. el Studio

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
        cwd=RAIZ, env=entorno, stdout=open(os.path.join(carpeta, "servidor.log"), "w"), stderr=subprocess.STDOUT)
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


def _esperar(s, url, segundos=40):
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
    seccion("6] el Studio por HTTP (simulado)")
    carpeta = os.path.join(CARPETA, "studio")
    os.makedirs(os.path.join(carpeta, "proyectos"))
    proceso, base = _arrancar(carpeta)
    s = requests.Session()
    try:
        s.put(base + "/api/parrilla/cuentas/conexiones", json={"apify_token": "apify_api_HTTP_1", "meta_token": "EAABx",
                                                               "ig_id": "1"})
        for red, u in (("tiktok", "ana"), ("tiktok", "beto"), ("instagram", "estudio_c")):
            r = s.post(base + "/api/parrilla/cuentas/leer", json={"texto": "@" + u, "red": red, "cuantos": 12, "pagar": True})
            _esperar(s, base + f"/api/parrilla/cuentas/trabajos/{r.json()['id']}")
        d = s.get(base + "/api/parrilla/cuentas/instagram/estudio_c").json()
        ok(d["metricas"]["total"] == 12 and d["duraciones"]["faltan"] == 12 and "mg100" in d["videos"][0],
           "GET de una cuenta: con sus cifras y lo que falta de duración")
        r = s.post(base + "/api/parrilla/cuentas/instagram/estudio_c/duraciones", json={})
        t = _esperar(s, base + f"/api/parrilla/cuentas/trabajos/{r.json()['id']}")
        ok(t["estado"] == "error" and (t.get("pide_pago") or {}).get("coste_usd"), "completar la duración sin «pagar»: pide permiso")
        r = s.post(base + "/api/parrilla/cuentas/instagram/estudio_c/duraciones", json={"pagar": True})
        igual(_esperar(s, base + f"/api/parrilla/cuentas/trabajos/{r.json()['id']}")["estado"], "listo", "y con «pagar», listo")
        igual(s.get(base + "/api/parrilla/cuentas/instagram/estudio_c").json()["duraciones"]["faltan"], 0, "ya tienen duración")

        sel = ["tiktok:ana", "tiktok:beto", "instagram:estudio_c"]
        igual(s.post(base + "/api/parrilla/conjuntos/plan", json={"cuentas": sel[:1]}).status_code, 400, "plan con una sola: 400")
        p = s.post(base + "/api/parrilla/conjuntos/plan", json={"cuentas": sel}).json()
        igual((p["n_cuentas"], p["videos"], p["puede"]), (3, 36, True), "POST /api/parrilla/conjuntos/plan")
        igual(s.post(base + "/api/parrilla/conjuntos/ultimo", json={"cuentas": sel}).json()["analisis"], None, "sin análisis previo")
        r = s.post(base + "/api/parrilla/conjuntos", json={"cuentas": sel})
        igual(r.status_code, 202, "analizar seleccionadas: 202 y un trabajo")
        t = _esperar(s, base + f"/api/parrilla/conjuntos/trabajos/{r.json()['id']}")
        igual(t["estado"], "listo", "y acaba")
        a = s.get(base + f"/api/parrilla/conjuntos/{t['analisis']}").json()
        ok(a["resultado"]["formulas_comunes"], "GET del análisis")
        igual(s.get(base + "/api/parrilla/conjuntos/a0000000000").status_code, 404, "uno que no existe: 404")
        igual(s.post(base + "/api/parrilla/conjuntos/ultimo", json={"cuentas": sel}).json()["analisis"]["id"], a["id"],
              "y ahora sí hay uno de esa selección")
        h = s.get(base + "/api/parrilla/conjuntos/historial").json()
        igual([x["id"] for x in h["analisis"]], [a["id"]], "GET /api/parrilla/conjuntos/historial")
        c = s.get(base + f"/api/parrilla/conjuntos/{a['id']}/comparar").json()
        igual(c["con"], None, "comparar sin anterior: con null")
        igual(s.get(base + f"/api/parrilla/conjuntos/{a['id']}/comparar?con={a['id']}").status_code, 400,
              "comparar consigo mismo: 400")

        cid = s.post(base + "/api/clientes", json={"nombre": "Proyecto de temas"}).json()["cliente"]["id"]
        igual(s.get(base + f"/api/parrilla/proyectos/{cid}/cuentas-propias").json()["cuentas"], [], "sin cuentas propias")
        r = s.put(base + f"/api/parrilla/proyectos/{cid}/cuentas-propias", json={"cuentas": ["tiktok:nadie"]})
        igual(r.status_code, 404, "una cuenta propia sin leer: 404")
        r = s.put(base + f"/api/parrilla/proyectos/{cid}/cuentas-propias", json={"cuentas": ["instagram:estudio_c"]})
        ok(r.status_code == 200 and r.json()["cuentas"][0]["leida"], "PUT de las cuentas propias")
        igual(s.get(base + "/api/parrilla/proyectos/no_existe/cuentas-propias").status_code, 404, "de un proyecto que no existe: 404")
        igual(s.get(base + f"/api/parrilla/proyectos/{cid}/temas").json()["propuesta"], None, "sin propuesta todavía")
        p = s.post(base + f"/api/parrilla/proyectos/{cid}/temas/plan", json={"analisis": a["id"], "cuantos": 5}).json()
        ok(p["puede"] and p["tokens"] > 0 and p["publicados"] == 12, "el plan de los temas (con lo publicado en la cuenta propia)")
        igual(s.post(base + "/api/parrilla/proyectos/_sin/temas/plan", json={"analisis": a["id"], "cuantos": 5}).status_code, 409,
              "sin proyecto, no")
        r = s.post(base + f"/api/parrilla/proyectos/{cid}/temas", json={"analisis": a["id"], "cuantos": 5})
        igual(r.status_code, 202, "proponer temas: 202")
        t = _esperar(s, base + f"/api/parrilla/temas/trabajos/{r.json()['id']}")
        igual(t["estado"], "listo", "y acaba")
        prop = s.get(base + f"/api/parrilla/proyectos/{cid}/temas").json()["propuesta"]
        uno = next(x for x in prop["temas"] if x["grupo"] == "propuesta")
        r = s.put(base + f"/api/parrilla/proyectos/{cid}/temas/{uno['id']}", json={"estado": "aprobado", "espacio": "Una azotea"})
        ok(r.status_code == 200 and next(x for x in r.json()["propuesta"]["temas"] if x["id"] == uno["id"])["estado"] == "aprobado",
           "aprobar y editar por HTTP")
        igual(s.post(base + f"/api/parrilla/proyectos/{cid}/temas/escribir", json={}).status_code, 409,
              "escribir sin confirmar: 409, no se escribe nada")
        igual(s.post(base + "/api/parrilla/proyectos/_sin/temas/escribir", json={"confirmado": True}).status_code, 409,
              "sin proyecto: 409")
        cupo_ruta = os.path.join(carpeta, "secretos", "cupo_claude.json")
        with open(cupo_ruta, "w", encoding="utf-8") as fh:
            json.dump({"p": {"cuenta": "principal", "ventanas": {"five_hour": {"uso": 0.95, "reinicia": time.time() + 3600}}}}, fh)
        r = s.post(base + f"/api/parrilla/proyectos/{cid}/temas/escribir", json={"confirmado": True})
        ok(r.status_code == 409 and "Seguir igualmente" in r.text, "con el cupo al 95 %, escribir pide «Seguir igualmente»")
        ok(s.get(base + f"/api/parrilla/proyectos/{cid}/temas").json()["cupo"]["malo"], "y la pantalla sabe que el cupo va lleno")
        r = s.post(base + f"/api/parrilla/proyectos/{cid}/temas/escribir", json={"confirmado": True, "aunque_cupo": True})
        os.remove(cupo_ruta)
        igual(r.status_code, 202, "con el sí, escribe los aprobados: 202")
        t = _esperar(s, base + f"/api/parrilla/trabajos/{r.json()['id']}")
        igual((t["estado"], len(t["guiones"])), ("listo", 1), "un guion, en la Parrilla del proyecto")
        g = s.get(base + f"/api/parrilla/proyectos/{cid}/guiones/{t['guiones'][0]}").json()
        ok(g["origen"]["tipo"] == "temas" and g["origen"]["tema_id"] == uno["id"], "con su origen")
        prop = s.get(base + f"/api/parrilla/proyectos/{cid}/temas").json()["propuesta"]
        ok(next(x for x in prop["temas"] if x["id"] == uno["id"])["guion"] == t["guiones"][0], "y el tema, marcado como escrito")
    finally:
        proceso.terminate()
        proceso.wait(timeout=15)


# ------------------------------------------- 7. lo que encontró la revisión

def prueba_revision():
    seccion("7] lo que encontró la revisión independiente (01-11)")
    m = M.metricas({"videos": [_video(i, 1000, 50, 20, texto=t) for i, t in
                               enumerate(["Nuestros colaboradores te cuentan", "Colabora con nosotros", "colab con @x",
                                          "feat. Juan", "normal"])]})
    igual([v["dudoso"] for v in m["videos"]], [False, False, True, True, False],
          "«colaboradores» y «colabora» no son colaboración; «colab» y «feat.» sí")
    igual((M.nombre_tipo("REELS"), M.nombre_tipo("CAROUSEL_ALBUM")), ("Reel", "Carrusel"),
          "el tipo en bruto de las cuentas leídas antes, con su nombre")
    datos = {"videos": [_video(0, 1000, 50, None, tipo="publicacion"), _video(1, 1000, 50, None, tipo="carrusel"),
                        _video(2, 1000, 50, None, tipo="reel")]}
    raiz = os.path.join(CARPETA, "rev")
    os.makedirs(raiz)
    C.guardar_claves({"apify_token": "apify_api_x", "pago": True, "tope_usd": 5})
    igual(C.plan_duraciones(raiz, "instagram", "x", datos=datos)["faltan"], 1, "las fotos y los carruseles no cuentan como «falta la duración»")
    datos["duraciones_apify"] = {"sin": ["COD2"]}
    p = C.plan_duraciones(raiz, "instagram", "x", datos=datos)
    ok(p["faltan"] == 0 and not p["se_puede"], "lo que Apify ya no supo rellenar no se vuelve a ofrecer (ni a pagar)")

    # el mismo @ en dos redes son dos cuentas
    C.guardar_claves({"apify_token": "apify_api_x"})
    for red in ("tiktok", "instagram"):
        C.leer(raiz, red, "marca", 12, pagar=True)
    C.leer(raiz, "tiktok", "otra", 12, pagar=True)
    cargadas = CJ._cargar(raiz, CJ.entender_lista(["tiktok:marca", "instagram:marca", "tiktok:otra"]))
    indice = CJ.indice_de_videos(cargadas)
    ok("@marca/tiktok#2" in CJ.texto_cuentas(cargadas) and "@otra#2" in CJ.texto_cuentas(cargadas),
       "con el mismo @ en dos redes, las referencias llevan la red")
    pr = CJ.pruebas_validas(["@marca/tiktok#2", "@marca/instagram#2", "@marca#2"], indice)
    igual([(x["red"], x["n"]) for x in pr], [("tiktok", 2), ("instagram", 2)], "y cada una va a su vídeo (la ambigua no se adivina)")
    limpio = CJ.limpiar({"formulas_comunes": [{"nombre": "X", "pruebas": ["@marca/tiktok#2", "@marca/instagram#3"]}]}, cargadas)
    ok(limpio["formulas_comunes"], "una fórmula que está en las dos redes del mismo @ sigue siendo común")

    # el cupo: con una cuenta de respaldo con cupo, no se bloquea
    with open(CC.fichero_cupo(), "w", encoding="utf-8") as fh:
        json.dump({"a": {"cuenta": "principal", "ventanas": {"five_hour": {"uso": 0.95, "reinicia": time.time() + 3600}}},
                   "b": {"cuenta": "respaldo", "ventanas": {"five_hour": {"uso": 0.20, "reinicia": time.time() + 3600}}}}, fh)
    try:
        cupo = CJ.estado_cupo()
        ok(not cupo["malo"] and cupo["uso"] == 0.2, f"con la de respaldo al 20 %, se puede ({cupo})")
    finally:
        os.remove(CC.fichero_cupo())

    # una cuenta vuelta a traer después del análisis
    a = CJ.analizar(raiz, ["tiktok:marca", "tiktok:otra"])
    time.sleep(1.1)                     # «traida» va al segundo
    C.leer(raiz, "tiktok", "otra", 12, forzar=True, pagar=True)
    f = lanza(T.plan, raiz, "cl_rev", a["id"], 3)
    ok(isinstance(f, T.ErrorTemas) and "volvió a traer" in str(f), "si una cuenta se volvió a traer, pide analizar otra vez")

    # Claude se salta un guion: cada uno va a SU tema por el código
    temas = [{"id": "t01", "tema": "Uno", "origen": {"tema_id": "t01"}}, {"id": "t02", "tema": "Dos", "origen": {"tema_id": "t02"}},
             {"id": "t03", "tema": "Tres", "origen": {"tema_id": "t03"}}]
    P.LLAMAR_CLAUDE = lambda i, para: "\n".join(f"{P.SEPARADOR}\n" + P._guion_simulado(1, t, "voz", "adaptar").replace("S01 — ", f"{c} — ", 1)
                                                for c, t in (("T01", "Uno"), ("T03", "Tres")))
    try:
        t = P.lanzar(raiz, "cl_rev", "temas", {"temas": temas, "modo": "adaptar"}, en_hilo=False)
    finally:
        P.LLAMAR_CLAUDE = None
    ids = [P.leer(raiz, "cl_rev", g)["origen"].get("tema_id") for g in t["guiones"]]
    igual(ids, ["t01", "t03"], "si Claude se salta el 2.º, el 3.º va al tema 3 (no al 2)")
    ok("devolvió 2 de 3" in (t.get("aviso") or ""), "y avisa de que falta uno")


# ------------------------------------ 8. tercera vuelta (cuentas-gustan-3)

def prueba_tercera(raiz, a):
    seccion("8] temas agrupados, ganchos, historial y comparar, cuentas propias")
    r = a["resultado"]
    temas = r["temas"]
    igual([t["tema"] for t in temas], ["Cumpleaños con consola", "Torneos en la oficina"],
          "los temas agrupados: el mismo nombre se une y el que no tiene pruebas se quita")
    cumple = temas[0]
    ok(cumple["n_cuentas"] == 3 and cumple["cuentas"] == sorted(cumple["cuentas"]),
       f"con las cuentas que lo hacen ({cumple['cuentas']})")
    suma = sum(p["vistas"] for p in cumple["pruebas"])
    igual(cumple["vistas_total"], suma, "la suma de vistas la calcula el Studio con sus vídeos de prueba")
    igual(cumple["n_videos"], 7, "incluidos los del tema repetido con otra mayúscula")
    ok(temas[0]["n_cuentas"] >= temas[1]["n_cuentas"], "primero el que hacen más cuentas")
    ganchos = r["ganchos"]
    ok(len(ganchos) == 2 and all(g["ejemplos"] and g["ejemplos"][0]["url"] for g in ganchos),
       "los ganchos, con ejemplos enlazados")
    ok(ganchos[0]["rel_media"] >= ganchos[1]["rel_media"], "del que mejor funciona al que menos")
    prompt = CJ.instruccion(CJ._cargar(raiz, CJ.entender_lista([c["red"] + ":" + c["usuario"] for c in a["cuentas"]])))
    ok('"temas"' in prompt and '"ganchos"' in prompt and "AGRUPADOS" in prompt, "a Claude se le piden temas agrupados y ganchos")
    viejo = CJ.limpiar({"temas_libres": [{"tema": "Z", "pruebas": ["@ana#3"]}]},
                       CJ._cargar(raiz, CJ.entender_lista(["tiktok:ana", "youtube:beto"])))
    igual((viejo["temas"], viejo["ganchos"]), ([], []), "sin temas ni ganchos en la respuesta: listas vacías, sin error")

    # C: historial y comparar
    sel = [c["red"] + ":" + c["usuario"] for c in a["cuentas"]]
    igual(CJ.comparar(raiz, a["id"])["con"], None, "el primero no tiene con qué compararse")
    time.sleep(1.1)
    b = CJ.analisis(raiz, CJ.lanzar(raiz, sel, en_hilo=False)["analisis"])
    h = CJ.historial(raiz)
    ok(h[0]["id"] == b["id"] and a["id"] in [x["id"] for x in h], "el historial: el más nuevo primero")
    ok(h[0]["temas"] == 2 and h[0]["ganchos"] == 2 and h[0]["cuentas"], "cada uno con cuántos temas, ganchos y cuentas")
    c = CJ.comparar(raiz, b["id"])
    igual((c["con"]["id"], c["misma_seleccion"]), (a["id"], True), "por defecto, contra el anterior de la misma selección")
    sec = c["secciones"]["temas"]
    igual((len(sec["siguen"]), sec["aparecen"], sec["desaparecen"]), (2, [], []), "mismos temas: siguen los dos")
    # uno con otro tema y sin ganchos (como los de antes de esta rama)
    ruta = os.path.join(CJ._carpeta(raiz), f"{a['id']}.json")
    d = json.load(open(ruta, encoding="utf-8"))
    d["resultado"]["temas"] = [dict(d["resultado"]["temas"][0]), {"tema": "Karaoke en hoteles", "vistas_total": 10}]
    d["resultado"].pop("ganchos")
    json.dump(d, open(ruta, "w", encoding="utf-8"))
    c = CJ.comparar(raiz, b["id"], a["id"])
    sec = c["secciones"]["temas"]
    ok([x["nombre"] for x in sec["aparecen"]] == ["Torneos en la oficina"]
       and [x["nombre"] for x in sec["desaparecen"]] == ["Karaoke en hoteles"]
       and [x["nombre"] for x in sec["siguen"]] == ["Cumpleaños con consola"], "aparece uno, desaparece otro y sigue uno")
    ok(c["secciones"]["ganchos"]["antes_sin_datos"], "un análisis viejo sin ganchos: lo dice, no los da por nuevos sin más")
    ok(isinstance(lanza(CJ.comparar, raiz, b["id"], b["id"]), CJ.ErrorConjunto), "consigo mismo, no")
    ok(isinstance(lanza(CJ.comparar, raiz, b["id"], "a0000000000"), CJ.ErrorConjunto), "con uno que no existe, 404")
    time.sleep(1.1)
    otra = CJ.analisis(raiz, CJ.lanzar(raiz, sel[:2], en_hilo=False)["analisis"])
    igual(CJ.anterior_de(raiz, otra)["id"], b["id"], "sin anterior de la misma selección, el que comparte más cuentas")

    # D: las cuentas propias
    cid = "cl_propias"
    igual(T.cuentas_propias(raiz, cid)["cuentas"], [], "sin cuentas propias al principio")
    ok(isinstance(lanza(T.guardar_cuentas_propias, raiz, cid, ["tiktok:nadie"]), T.ErrorTemas), "una sin leer: no")
    ok(isinstance(lanza(T.guardar_cuentas_propias, raiz, "_sin", ["tiktok:ana"]), T.ErrorTemas), "sin proyecto: no")
    ok(isinstance(lanza(T.guardar_cuentas_propias, raiz, cid, [f"tiktok:u{i}" for i in range(6)]), T.ErrorTemas),
       "como mucho 5")
    p0 = T.plan(raiz, cid, b["id"], 5)
    igual(p0["publicados"], 0, "sin cuentas propias no hay publicados en el cruce")
    d = T.guardar_cuentas_propias(raiz, cid, ["tiktok:carla"])
    ok(d["cuentas"][0]["leida"] and d["cuentas"][0]["videos"] == 12, "guardar una cuenta propia (leída)")
    p1 = T.plan(raiz, cid, b["id"], 5)
    igual((p1["publicados"], p1["existentes"]), (12, p0["existentes"] + 12), "lo publicado en ella entra en el cruce")
    carla = C.cuenta(raiz, "tiktok", "carla")
    texto = carla["videos"][0]["texto"]
    _c, cargadas, existentes, _m = T.preparar(raiz, cid, b["id"])
    ok(any(e["tipo"] == "publicado" and e["texto"] == " ".join(texto.split())[:400] for e in existentes),
       "con su texto, como «publicado»")
    ideas = [{"tema": texto[:120], "gancho": "", "problema": "", "referencias": ["@ana#2"]}]
    orden = T.ordenar(ideas, _c, cargadas, existentes, 5)
    ok(orden and orden[0]["cruce"]["nivel"] == "repetido" and orden[0]["cruce"]["tipo"] == "publicado",
       "una idea igual a algo que ya publicaste sale como «ya lo tienes» (repetido, publicado)")
    ok("lo publicado en mis cuentas" in T.instruccion(_c, cargadas, existentes, 5), "y Claude sabe que eso ya está")
    igual(T.guardar_cuentas_propias(raiz, cid, [])["cuentas"], [], "[] las quita")


def main():
    print("PRUEBA DE CUENTAS QUE TE GUSTAN 2")
    prueba_metricas()
    prueba_duracion()
    raiz, a = prueba_conjunto()
    cid = prueba_temas(raiz, a)
    prueba_escribir(raiz, cid)
    prueba_tercera(raiz, a)
    prueba_revision()
    try:
        import fastapi  # noqa: F401
        import requests  # noqa: F401
        hay_servidor = True
    except ImportError:
        hay_servidor = False
    if hay_servidor:
        prueba_studio()
    else:
        print("\n[6] OMITIDA: falta fastapi en este entorno (en el servidor sí corre)")
    shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"CUENTAS GUSTAN OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

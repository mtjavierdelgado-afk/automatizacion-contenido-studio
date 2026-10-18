"""PUBLICAR: los textos por red, las cuentas de cada proyecto y los envios.

Lo que el Studio hace con un video YA MONTADO para que llegue a las redes
(TikTok, Instagram Reels, YouTube y Facebook), a mano o con Upload-Post, ya o
programado en hora de Lima. Decidido por el dueño entre el 13 y el 16-10-2026
(documento `estado/redes_parrilla_publicar_2026-10-15.md` del Proyecto).

    ajustes_de(raiz, cid)            lo fijo de un proyecto: perfil, redes,
    guardar_ajustes(raiz, cid, ...)  hora, firma, hashtags, tono, IA...
    ficha(raiz, info, ajustes)       la ficha de publicar de un video
    guardar_ficha(raiz, pid, ...)    redes elegidas y textos editados a mano
    lanzar_textos(...)               Claude escribe los textos (en un hilo)
    enviar(...)                      prepara los envios y los sube (en un hilo)
    refrescar(raiz)                  pregunta a Upload-Post por lo pendiente
    cola(raiz, videos, desde, dias)  la cola y el calendario
    actualizar_metricas(...)         las cifras de lo publicado (Upload-Post)
    leer_guardadas(raiz, pids)       lo que Upload-Post ya tiene leido (gratis)
    resultados(raiz, videos, cid)    el resumen por proyecto
    periodos(raiz, videos, cid)      esta semana y este mes, frente al anterior
    lo_que_funciono(raiz, videos)    los posts que mejor fueron: para la
                                     pantalla, la Parrilla y el piloto

DONDE VIVE
----------
Todo en `<proyectos>/_sistema/publicar/`, FUERA de la carpeta de cada video, a
proposito:

  - nada de aqui entra en ninguna firma: escribir un texto para TikTok no
    puede dejar obsoleto el render (regla 1 de CLAUDE.md). Lo unico que toca
    la carpeta del video son dos REGISTROS que ya existen para eso: los
    tokens de Claude de los textos en su `coste.jsonl` (sin dolares: van
    contra la suscripcion) y una linea en su bitacora por cada envio;
  - duplicar un video no duplica sus envios (una copia que «ya esta publicada»
    en TikTok seria mentira), y copiar su carpeta a mano tampoco (R4);
  - `asvs actualizar` no lo toca: son datos, como las notas.

    _sistema/publicar/ajustes.json         {"proyectos": {cid: {...}}}
    _sistema/publicar/videos/<pid>.json    {"redes", "textos", "capitulos",
                                            "huella", "envios": [...]}

LO QUE NO SE NEGOCIA
--------------------
1. **Nada sale sin confirmacion.** La pantalla pregunta antes de enviar y el
   servidor exige `confirmado: true` (no se puede desactivar: lo pidio el
   dueño). Un piloto automatico futuro dejara los envios en «espera tu OK».
2. **Una subida no se reintenta sola.** Si Upload-Post no contesta a mitad, el
   envio queda en «comprobar»: reenviar podria publicarlo dos veces en la red
   de un cliente. Lo mismo un envio que ya esta publicado o programado en esa
   red con ese mismo MP4: repetirlo pide decirlo (`repetir`).
3. **Si una red falla, las demas siguen.** Cada red es su propio envio, con su
   estado y su enlace.
4. **La clave nunca baja a la pantalla.** Se pone en Configuracion → Publicar
   en redes (el almacen de `pasos/claves.py`, espejada en el `.env` de
   secretos como `UPLOADPOST_API_KEY`); la pantalla solo ve los cuatro
   ultimos caracteres.
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid

try:
    from . import claves as CLAVES
    from . import cli_claude, comun
except ImportError:                                   # corriendo desde pasos/
    import claves as CLAVES
    import cli_claude
    import comun

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys                                            # noqa: E402
if RAIZ_ESTUDIO not in sys.path:
    sys.path.insert(0, RAIZ_ESTUDIO)
from motores.publicar_uploadpost import cliente as UP  # noqa: E402
from motores.publicar_uploadpost import simulado as UP_SIMULADO  # noqa: E402
from nucleo.proyecto import escribir_json, leer_json  # noqa: E402

ZONA = "America/Lima"
REDES = UP.REDES
NOMBRE_RED = {"tiktok": "TikTok", "instagram": "Instagram Reels",
              "youtube": "YouTube", "facebook": "Facebook"}

#: Clave de los ajustes de los videos que no estan en ningun proyecto.
SIN_PROYECTO = "_sin"

#: Estados de un envio. «espera_ok» es uno preparado y sin confirmar.
ESTADOS = ("espera_ok", "enviando", "programado", "publicando", "publicado",
           "fallido", "cancelado", "comprobar", "a_mano")
#: Los que todavia pueden cambiar solos (se preguntan a Upload-Post).
PENDIENTES = ("enviando", "programado", "publicando", "comprobar")
#: Los que cuentan como «ya va a salir o salio» para no repetir sin querer.
VIVOS = ("enviando", "programado", "publicando", "publicado", "comprobar", "a_mano")

#: Los textos son lo que se lee del vídeo: van con opus/medium (16-10-2026; con
#: sonnet/low salían planos). Se cambia con ESTUDIO_PUBLICAR_MODELO/_ESFUERZO.
MODELO = os.environ.get("ESTUDIO_PUBLICAR_MODELO") or "opus"
ESFUERZO = os.environ.get("ESTUDIO_PUBLICAR_ESFUERZO") or "medium"
#: Tope de UNA llamada para los textos. Sin el, opus/medium daba ~16 minutos
#: de techo y un CLI colgado dejaba la ficha «escribiendo» todo ese rato. En el
#: servidor tardan 10-20 s (17-10-2026).
TECHO_TEXTOS_S = int(os.environ.get("ESTUDIO_PUBLICAR_TECHO_S") or 240)
MAX_MATERIAL = 6000
MAX_GUION = 9000
#: Cada cuanto se puede volver a preguntar por el mismo envio, en segundos.
RESPIRO_CONSULTA_S = float(os.environ.get("ESTUDIO_PUBLICAR_RESPIRO") or 15)
#: Un envio «enviando» sin hilo vivo (el servicio se reinicio a mitad) pasa a
#: «comprobar» despues de esto.
HUERFANO_S = 900

_LOCKS = {}
_LOCK_LOCKS = threading.Lock()
_ESCRIBIENDO = {}              # pid -> {"desde", "redes"}
_ERRORES_TEXTOS = {}           # pid -> mensaje del ultimo fallo
_REDES_FALLIDAS = {}           # pid -> las redes de ese intento (para «Reintentar»)
_SUBIENDO = set()              # lotes con hilo vivo
_ULTIMA_CONSULTA = {}          # lote -> time.time()
_NO_LO_CONOCE = {}             # lote -> cuantas veces seguidas Upload-Post dijo 404
#: Tras tantas consultas seguidas en las que Upload-Post no conoce un envio (y
#: con media hora de margen desde que se creo), se da por no llegado.
VECES_NO_LO_CONOCE = 5
_ESTADO_CLAVE = {"probada": None}


class ErrorPublicar(ValueError):
    """Lo pedido no se puede hacer, con el motivo en castellano. `codigo` HTTP."""

    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = int(codigo)


def _lock(clave):
    with _LOCK_LOCKS:
        if clave not in _LOCKS:
            _LOCKS[clave] = threading.RLock()
        return _LOCKS[clave]


def _zona():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(ZONA)
    except Exception:                                   # noqa: BLE001
        return dt.timezone(dt.timedelta(hours=-5))      # Lima no cambia de hora


def ahora_lima():
    return dt.datetime.now(_zona()).replace(microsecond=0)


def _iso_lima(momento=None):
    return (momento or ahora_lima()).strftime("%Y-%m-%dT%H:%M:%S")


def _leer_momento(texto):
    """«2026-10-17T19:00» en hora de Lima -> datetime con zona, o None."""
    texto = str(texto or "").strip()
    if not texto:
        return None
    try:
        momento = dt.datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=_zona())
    return momento.astimezone(_zona())


# ------------------------------------------------------------------- ficheros

def carpeta(raiz):
    return os.path.join(raiz, "_sistema", "publicar")


def _ruta_ajustes(raiz):
    return os.path.join(carpeta(raiz), "ajustes.json")


def _ruta_video(raiz, pid):
    if not re.match(r"^[a-z0-9_]+$", str(pid or "")) or str(pid).startswith("_"):
        raise ErrorPublicar("ese vídeo no existe", 404)
    return os.path.join(carpeta(raiz), "videos", f"{pid}.json")


def _escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    escribir_json(ruta, datos)


def _leer_video(raiz, pid):
    datos = leer_json(_ruta_video(raiz, pid), {}) or {}
    datos = datos if isinstance(datos, dict) else {}
    datos.setdefault("redes", [])
    datos.setdefault("textos", {})
    datos.setdefault("capitulos", [])
    datos.setdefault("envios", [])
    return datos


# ---------------------------------------------------------------------- clave

def clave():
    """(clave, de donde sale). Nunca se devuelve por la API: solo el origen.

    La casilla de Configuracion la guarda en el almacen de claves
    (`pasos/claves.py`), que la espeja en el .env de secretos; una puesta a mano
    en ese .env tambien vale. `UPLOADPOST_API_KEY` en el entorno del servicio,
    la ultima."""
    try:
        bruto = CLAVES._leer_json(CLAVES.FICHERO, {}) or {}
        propia = str(((bruto.get("uploadpost") or {}).get("clave")) or "").strip()
        if propia:
            return propia, "almacen"
        guardada = str(CLAVES.leer()["uploadpost"]["clave"] or "").strip()
        if guardada:
            return guardada, "env"
    except Exception:                                   # noqa: BLE001
        pass
    entorno = str(os.environ.get("UPLOADPOST_API_KEY") or "").strip()
    if entorno:
        return entorno, "entorno"
    return "", ""


def simulado():
    """Sin Upload-Post de verdad: con ESTUDIO_UPLOADPOST_SIMULADO, o con
    ESTUDIO_SIMULAR=1, que en las suites quiere decir «ningun servicio de fuera»."""
    return bool(os.environ.get("ESTUDIO_UPLOADPOST_SIMULADO")) or _simular_todo()


def _simular_todo():
    return str(os.environ.get("ESTUDIO_SIMULAR", "")).strip().lower() in ("1", "si", "true")


def cliente(raiz=None):
    """El cliente de Upload-Post que toca: el simulado o el de verdad."""
    if simulado():
        ruta = os.environ.get("ESTUDIO_UPLOADPOST_SIMULADO") or ""
        if not ruta and raiz:
            ruta = os.path.join(carpeta(raiz), "uploadpost_simulado.json")
        return UP_SIMULADO.SimuladoUploadPost(ruta or None)
    valor, _origen = clave()
    if not valor:
        raise ErrorPublicar(
            "falta la clave de Upload-Post: ponla en Configuración → Publicar en "
            "redes (nunca en un chat). Sin clave puedes publicar a mano: copia "
            "los textos y descarga el MP4.", 409)
    return UP.ClienteUploadPost(valor)


def estado_clave():
    valor, origen = clave()
    return {"puesta": bool(valor) or simulado(), "origen": "simulado" if simulado() else origen,
            "cola": CLAVES.tapar(valor) if valor and not simulado() else "",
            "simulado": simulado(), "probada": _ESTADO_CLAVE["probada"]}


def probar_clave(raiz=None):
    try:
        r = cliente(raiz).probar()
    except UP.ErrorUploadPost as fallo:
        _ESTADO_CLAVE["probada"] = {"ok": False, "mensaje": str(fallo), "cuando": _iso_lima()}
        return dict(_ESTADO_CLAVE["probada"])
    _ESTADO_CLAVE["probada"] = {"ok": True, "mensaje": "Upload-Post acepta la clave"
                                + (f" · plan {r['plan']}" if r.get("plan") else ""),
                                "cuando": _iso_lima()}
    return dict(_ESTADO_CLAVE["probada"])


def _por_upload_post(fn, *args, **kwargs):
    """Llama al cliente y convierte su fallo en uno de los nuestros."""
    try:
        return fn(*args, **kwargs)
    except UP.ErrorUploadPost as fallo:
        raise _convertir(fallo) from None


def _convertir(fallo):
    codigo = 502 if fallo.codigo in (0, 500, 502, 503) else (
        409 if fallo.codigo in (401, 403, 429) else 400)
    return ErrorPublicar(str(fallo), codigo)


# -------------------------------------------------------------------- ajustes

AJUSTES_DEFECTO = {
    "perfil": "",                       # el perfil de Upload-Post de este proyecto
    "redes": list(REDES),               # las que salen marcadas en un video nuevo
    "hora": "19:00",                    # hora de Lima por defecto al programar
    "firma": "",                        # se añade al final de cada texto
    "hashtags": "",                     # los fijos del proyecto
    "tono": "",                         # como escribe los textos Claude
    "marcar_ia": True,                  # avisar en cada red de que es IA
    "usar_emojis": True,                # que Claude ponga emojis en los textos
    "avisar_youtube": True,             # notificar a los suscriptores
    "privacidad_youtube": "public",
    "facebook_pagina": "",              # id de la pagina, si hay mas de una
    "cuentas": {},                      # lo ultimo que dijo Upload-Post del perfil
    "cuentas_vistas": "",
    "seguidores": {},                   # lo ultimo que dijo de cada cuenta
    "seguidores_al": "",
}
LARGOS = {"firma": 400, "hashtags": 400, "tono": 600, "perfil": 60,
          "facebook_pagina": 40}


def _clave_proyecto(cid):
    cid = str(cid or "").strip()
    return cid or SIN_PROYECTO


def ajustes_de(raiz, cid):
    datos = leer_json(_ruta_ajustes(raiz), {}) or {}
    propio = ((datos.get("proyectos") or {}).get(_clave_proyecto(cid))) or {}
    salida = json.loads(json.dumps(AJUSTES_DEFECTO))
    if isinstance(propio, dict):
        salida.update({k: v for k, v in propio.items() if k in AJUSTES_DEFECTO})
    return salida


def todos_los_ajustes(raiz):
    datos = leer_json(_ruta_ajustes(raiz), {}) or {}
    return {k: ajustes_de(raiz, k) for k in (datos.get("proyectos") or {})}


def _validar_ajustes(cambios):
    limpios = {}
    for k, v in (cambios or {}).items():
        if k not in AJUSTES_DEFECTO or k in ("cuentas", "cuentas_vistas",
                                             "seguidores", "seguidores_al"):
            continue
        if k in ("marcar_ia", "avisar_youtube", "usar_emojis"):
            if not isinstance(v, bool):
                raise ErrorPublicar(f"«{k}» es sí o no")
            limpios[k] = v
        elif k == "redes":
            if not isinstance(v, list) or any(r not in REDES for r in v):
                raise ErrorPublicar("las redes son: " + ", ".join(REDES))
            limpios[k] = [r for r in REDES if r in v]
        elif k == "hora":
            if not isinstance(v, str) or not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", v):
                raise ErrorPublicar("la hora va como 19:00")
            limpios[k] = v
        elif k == "privacidad_youtube":
            if v not in ("public", "unlisted", "private"):
                raise ErrorPublicar("en YouTube: public, unlisted o private")
            limpios[k] = v
        else:
            if not isinstance(v, str):
                raise ErrorPublicar(f"«{k}» es un texto")
            v = v.strip()
            if len(v) > LARGOS.get(k, 400):
                raise ErrorPublicar(f"«{k}» pasa de {LARGOS.get(k, 400)} caracteres")
            if k == "perfil" and v and not re.match(r"^[A-Za-z0-9_.\- ]+$", v):
                raise ErrorPublicar("el perfil lleva letras, números, espacios, «_», «-» o «.»")
            limpios[k] = v
    return limpios


def perfil_de_otro(raiz, perfil, cid):
    """El proyecto (otro que `cid`) que ya usa ese perfil de Upload-Post, o ""."""
    perfil = norma_perfil(perfil)
    if not perfil:
        return ""
    datos = leer_json(_ruta_ajustes(raiz), {}) or {}
    for otro, ficha in (datos.get("proyectos") or {}).items():
        if otro != _clave_proyecto(cid) and isinstance(ficha, dict) \
                and norma_perfil(ficha.get("perfil")) == perfil:
            return otro
    return ""


def guardar_ajustes(raiz, cid, cambios, internos=None):
    limpios = _validar_ajustes(cambios)
    if internos:
        limpios.update(internos)
    with _lock("ajustes"):
        # UN PERFIL ES UN CLIENTE: dos proyectos con el mismo perfil publicarian
        # los videos de uno en las cuentas del otro
        if limpios.get("perfil") and perfil_de_otro(raiz, limpios["perfil"], cid):
            raise ErrorPublicar("ese perfil de Upload-Post ya es de otro proyecto: cada "
                                "cliente necesita el suyo", 409)
        datos = leer_json(_ruta_ajustes(raiz), {}) or {}
        proyectos = datos.setdefault("proyectos", {})
        propio = proyectos.setdefault(_clave_proyecto(cid), {})
        # otro perfil = otras cuentas: las vistas del anterior ya no valen
        if "perfil" in limpios and limpios["perfil"] != propio.get("perfil") \
                and "cuentas" not in limpios:
            propio["cuentas"] = {}
            propio["cuentas_vistas"] = ""
            propio["seguidores"] = {}
            propio["seguidores_al"] = ""
        propio.update(limpios)
        _escribir(_ruta_ajustes(raiz), datos)
    return ajustes_de(raiz, cid)


def perfil_sugerido(cid, nombre):
    base = re.sub(r"[^a-z0-9]+", "_", str(nombre or cid or "studio").lower()).strip("_")
    return (f"studio_{base}"[:40]).strip("_") or "studio"


def recordar_cuentas(raiz, cid, cuentas):
    return guardar_ajustes(raiz, cid, {}, internos={
        "cuentas": cuentas or {}, "cuentas_vistas": _iso_lima()})


# ------------------------------------------------- los perfiles de Upload-Post
#
# Lo que salio en el servidor (16-10-2026): «Crear perfil» mandaba el cuerpo
# vacio, con el plan gratis lleno (2/2) Upload-Post decia «You have reached the
# limit of 2 profiles» aunque el perfil escrito YA existia alli, y «Ver cuentas»
# comparaba el nombre con == y daba por inexistente «Suyu» guardado como «suyu».
# Ahora: se lista antes de crear, se compara sin mayusculas ni espacios, y lo
# que exista se ADOPTA (con su nombre exacto de alli) en vez de crearse.

_PLAN_LLENO = re.compile(r"limit\s+of\s+(\d+)\s+profiles?", re.I)


def norma_perfil(nombre):
    """El nombre de un perfil para comparar: sin mayusculas ni espacios."""
    return re.sub(r"\s+", "", str(nombre or "")).lower()


def buscar_perfil(lista, nombre):
    """El perfil de `lista` (los de `cliente.perfiles()`) que es `nombre`, o None."""
    buscado = norma_perfil(nombre)
    if not buscado:
        return None
    return next((p for p in lista or [] if norma_perfil(p.get("perfil")) == buscado), None)


def mensaje_plan_lleno(n):
    return (f"Tu plan de Upload-Post ya tiene {n} perfiles; usa uno existente "
            "o mejora el plan")


def _log(evento, datos):
    """A la salida del servicio (journalctl -u as-video-studio) y a la bitacora."""
    try:
        print(f"[publicar] {evento} {json.dumps(datos, ensure_ascii=False)}",
              file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass
    try:
        from nucleo.bitacora import anotar_global
        anotar_global(f"publicar_{evento}", datos)
    except Exception:  # noqa: BLE001 - la bitacora nunca tumba una peticion
        pass


def _redes_conectadas(cuentas):
    return [r for r in REDES if isinstance((cuentas or {}).get(r), dict)]


def perfiles_de_la_cuenta(raiz, cid):
    """Los perfiles que hay de verdad en Upload-Post, para el desplegable:
    {perfiles: [{perfil, redes, de_otro, propio}], limite, plan}. `de_otro` es
    el proyecto de aqui que ya lo usa (no se puede elegir)."""
    lista = _por_upload_post(cliente(raiz).perfiles)
    _log("perfiles_vistos", {"proyecto": _clave_proyecto(cid),
                             "nombres": [p["perfil"] for p in lista["perfiles"]]})
    propio = norma_perfil(ajustes_de(raiz, cid).get("perfil"))
    salida = []
    for p in lista["perfiles"]:
        salida.append({"perfil": p["perfil"], "redes": _redes_conectadas(p["cuentas"]),
                       "de_otro": perfil_de_otro(raiz, p["perfil"], cid),
                       "propio": bool(propio) and norma_perfil(p["perfil"]) == propio})
    return {"perfiles": salida, "limite": lista.get("limite"), "plan": lista.get("plan") or ""}


def usar_perfil(raiz, cid, perfil, crear=True):
    """Apunta `perfil` como el de este proyecto: si ya existe en Upload-Post (sin
    mirar mayusculas ni espacios) lo adopta con su nombre exacto y sus cuentas;
    si no, y `crear`, lo crea. Devuelve (ajustes, "adoptado"|"creado")."""
    perfil = _validar_ajustes({"perfil": perfil}).get("perfil") or ""
    if not perfil:
        raise ErrorPublicar("escribe el nombre del perfil de Upload-Post")
    cli = cliente(raiz)
    lista = None
    try:
        lista = cli.perfiles()
    except UP.ErrorUploadPost as fallo:
        if fallo.codigo in (401, 403):
            raise ErrorPublicar(str(fallo), 409) from None
        # sin lista se intenta crear igual: un 409 de alli dira si ya existia
    if lista is not None:
        _log("perfiles_vistos", {"proyecto": _clave_proyecto(cid), "buscado": perfil,
                                 "nombres": [p["perfil"] for p in lista["perfiles"]]})
        hallado = buscar_perfil(lista["perfiles"], perfil)
        if hallado:
            if perfil_de_otro(raiz, hallado["perfil"], cid):
                raise ErrorPublicar("ese perfil de Upload-Post ya es de otro proyecto: "
                                    "elige otro para este", 409)
            return guardar_ajustes(raiz, cid, {"perfil": hallado["perfil"]}, internos={
                "cuentas": hallado["cuentas"], "cuentas_vistas": _iso_lima()}), "adoptado"
        if not crear:
            raise ErrorPublicar(f"Upload-Post no tiene ningún perfil «{perfil}»: elige uno "
                                "de la lista o pulsa «Crear perfil»", 404)
        limite = lista.get("limite")
        if isinstance(limite, int) and limite > 0 and len(lista["perfiles"]) >= limite:
            raise ErrorPublicar(mensaje_plan_lleno(len(lista["perfiles"])), 409)
    elif not crear:
        raise ErrorPublicar("no he podido pedir la lista de perfiles a Upload-Post; "
                            "prueba otra vez en un momento", 502)
    if perfil_de_otro(raiz, perfil, cid):
        raise ErrorPublicar("ese perfil de Upload-Post ya es de otro proyecto: "
                            "escribe otro nombre para este", 409)
    try:
        hecho = cli.crear_perfil(perfil)
    except UP.ErrorUploadPost as fallo:
        lleno = _PLAN_LLENO.search(str(fallo))
        if lleno:
            raise ErrorPublicar(mensaje_plan_lleno(lleno.group(1)), 409) from None
        if fallo.codigo != 409:
            raise _convertir(fallo) from None
        # ya existia alli (y la lista no lo traia): sus cuentas, con «Ver cuentas»
        return guardar_ajustes(raiz, cid, {"perfil": perfil}, internos={
            "cuentas": {}, "cuentas_vistas": ""}), "adoptado"
    _log("perfil_creado", {"proyecto": _clave_proyecto(cid), "perfil": hecho["perfil"]})
    return guardar_ajustes(raiz, cid, {"perfil": hecho["perfil"]}, internos={
        "cuentas": hecho["cuentas"], "cuentas_vistas": _iso_lima()}), "creado"


def ver_cuentas(raiz, cid):
    """Pregunta a Upload-Post por las cuentas del perfil del proyecto. Si alli
    se escribe distinto (mayusculas), se apunta el nombre de alli."""
    ajustes = ajustes_de(raiz, cid)
    if not ajustes.get("perfil"):
        raise ErrorPublicar("este proyecto todavía no tiene perfil de Upload-Post", 409)
    lista = _por_upload_post(cliente(raiz).perfiles)
    nombres = [p["perfil"] for p in lista["perfiles"]]
    _log("ver_cuentas", {"proyecto": _clave_proyecto(cid), "buscado": ajustes["perfil"],
                         "nombres": nombres})
    propio = buscar_perfil(lista["perfiles"], ajustes["perfil"])
    if propio is None:
        return {"existe": False, "ajustes": ajustes}
    if propio["perfil"] != ajustes["perfil"]:
        return {"existe": True, "ajustes": guardar_ajustes(
            raiz, cid, {"perfil": propio["perfil"]},
            internos={"cuentas": propio["cuentas"], "cuentas_vistas": _iso_lima()})}
    return {"existe": True, "ajustes": recordar_cuentas(raiz, cid, propio["cuentas"])}


# ---------------------------------------------------------------- el video

def medir_mp4(ruta):
    """{duracion, ancho, alto} del MP4 con ffprobe, o {} si no se puede."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not ruta or not os.path.isfile(ruta):
        return {}
    try:
        salida = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", ruta],
            capture_output=True, text=True, timeout=20, check=False).stdout
        datos = json.loads(salida or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    flujo = (datos.get("streams") or [{}])[0]
    try:
        return {"duracion": round(float((datos.get("format") or {}).get("duration") or 0), 2),
                "ancho": int(flujo.get("width") or 0), "alto": int(flujo.get("height") or 0)}
    except (TypeError, ValueError):
        return {}


def huella_mp4(ruta):
    try:
        info = os.stat(ruta)
    except OSError:
        return ""
    return hashlib.sha256(f"{info.st_size}:{int(info.st_mtime)}".encode()).hexdigest()[:12]


def huella_origen(info):
    """De qué salen los textos: el guion final y el MP4. Si cambia, la ficha
    queda «desactualizada» (los textos hablan de otro vídeo)."""
    trozos = [b.get("texto", "") for b in (info.get("guion") or [])]
    trozos += [str(info.get("mp4_huella") or ""), str(round(float(info.get("duracion_s") or 0)))]
    return hashlib.sha256("\n".join(trozos).encode("utf-8")).hexdigest()[:16]


def encaje(red, formato, duracion):
    """Si el vídeo encaja en la red y cómo sale. -> {tipo, nivel, texto}

    `nivel`: ok (sale como debe), aviso (sale, pero no como se espera) o error
    (la red no lo acepta: no se deja enviar)."""
    d = float(duracion or 0)
    vertical = formato == "vertical"
    if red == "tiktok":
        if d > 600:
            return {"tipo": "", "nivel": "error",
                    "texto": "TikTok no acepta por API vídeos de más de 10 minutos"}
        if not vertical:
            return {"tipo": "vídeo", "nivel": "aviso",
                    "texto": "es horizontal: en TikTok se verá pequeño, con bandas"}
        return {"tipo": "vídeo vertical", "nivel": "ok", "texto": ""}
    if red == "instagram":
        if d > 900:
            return {"tipo": "", "nivel": "error",
                    "texto": "Instagram no acepta Reels de más de 15 minutos"}
        if not vertical:
            return {"tipo": "Reel", "nivel": "aviso",
                    "texto": "es horizontal: como Reel se verá pequeño, con bandas"}
        if d > 180:
            return {"tipo": "Reel", "nivel": "aviso",
                    "texto": "pasa de 3 minutos: Instagram lo enseña poco a quien no te sigue"}
        return {"tipo": "Reel", "nivel": "ok", "texto": ""}
    if red == "youtube":
        if vertical and d <= 180:
            return {"tipo": "Short", "nivel": "ok", "texto": ""}
        if vertical:
            return {"tipo": "vídeo", "nivel": "aviso",
                    "texto": "vertical de más de 3 minutos: no sale como Short, sino como vídeo normal"}
        return {"tipo": "vídeo", "nivel": "ok", "texto": ""}
    if red == "facebook":
        if vertical and d <= 90:
            return {"tipo": "Reel", "nivel": "ok", "texto": ""}
        return {"tipo": "vídeo", "nivel": "aviso" if vertical else "ok",
                "texto": "pasa de 90 s: sale como vídeo, no como Reel" if vertical else ""}
    return {"tipo": "", "nivel": "error", "texto": "red desconocida"}


def capitulos_base(escenas, duracion):
    """Los capítulos posibles de YouTube: un bloque del guion, uno. Se juntan los
    de menos de 10 s (YouTube los pide así) y hacen falta tres o no hay."""
    puntos = []
    for e in escenas or []:
        bloque = str(((e.get("origen") or {}).get("bloque")) or "")
        try:
            t = float(e.get("t_in") or 0)
        except (TypeError, ValueError):
            continue
        if not puntos or (bloque and bloque != puntos[-1]["bloque"]):
            puntos.append({"bloque": bloque, "t": t, "texto": str(e.get("narracion") or "")})
        else:
            puntos[-1]["texto"] += " " + str(e.get("narracion") or "")
    if not puntos:
        return []
    puntos[0]["t"] = 0.0
    juntos = []
    for p in puntos:
        if juntos and p["t"] - juntos[-1]["t"] < 10:
            juntos[-1]["texto"] += " " + p["texto"]
        else:
            juntos.append(dict(p))
    if juntos and float(duracion or 0) - juntos[-1]["t"] < 10 and len(juntos) > 1:
        ultimo = juntos.pop()
        juntos[-1]["texto"] += " " + ultimo["texto"]
    if len(juntos) < 3:
        return []
    return [{"t": round(p["t"]), "texto": " ".join(p["texto"].split())[:400]} for p in juntos]


def _marca_de_tiempo(segundos):
    s = int(round(float(segundos or 0)))
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------- los textos

REGLAS_RED = {
    "tiktok": ("Pie de TikTok (no hay título aparte: la primera línea hace de título). "
               "CORTO: 1 a 3 líneas, máximo unos 300 caracteres antes de los hashtags. "
               "La primera línea es un gancho que para el dedo (una pregunta, un dato "
               "que sorprende, una promesa concreta). Usa las palabras clave que se "
               "DICEN en el vídeo, tal cual: TikTok busca por lo que se dice y por lo "
               "que se escribe. CTA corto y directo (comenta, guárdalo, link en bio, "
               "escríbenos). Hashtags: 3 a 5, mezclando 1-2 amplios del tema y 2-3 de "
               "nicho o de la ciudad/zona si el material la nombra."),
    "instagram": ("Pie de un Reel (no hay título aparte: la primera línea hace de "
                  "título). La PRIMERA LÍNEA es lo único que se ve sin pulsar «más»: "
                  "tiene que enganchar sola, en menos de 125 caracteres. Después, 2 a 4 "
                  "párrafos muy cortos separados por una línea en blanco, con frases "
                  "cortas que se lean de un vistazo (puedes usar viñetas con emoji). "
                  "CTA claro: guárdalo, compártelo con quien lo necesita, escríbenos por "
                  "DM, link en bio. Hashtags: 5 a 8, mezclando amplios, de nicho y "
                  "locales si el material nombra la zona."),
    "youtube": ("YouTube: TÍTULO de 40 a 70 caracteres (nunca más de 70: se corta en "
                "el móvil), con la palabra clave principal al principio, claro y "
                "buscable, sin clickbait engañoso y sin «<» ni «>». DESCRIPCIÓN pensada "
                "para el buscador: las dos primeras líneas repiten la palabra clave y "
                "resumen la promesa del vídeo (es lo que sale en los resultados); "
                "después 1 a 3 párrafos cortos con las palabras clave secundarias "
                "dichas con naturalidad. CTA: suscribirse o el enlace de la "
                "descripción. Hashtags: 3 a 5 (los tres primeros salen encima del "
                "título)."),
    "facebook": ("Facebook: TÍTULO corto (hasta 80 caracteres) y DESCRIPCIÓN que se "
                 "entienda SIN SONIDO (mucha gente lo ve en silencio): di en el texto "
                 "lo que pasa en el vídeo. Gancho en la primera línea, párrafos cortos "
                 "y fáciles de leer, tono cercano. CTA: enviar mensaje, llamar o "
                 "comentar. Hashtags: 2 a 4."),
}
#: Cuántos emojis y cómo, por red, cuando el proyecto los quiere.
EMOJIS_RED = {
    "tiktok": "1 a 3 emojis, en el gancho o al final de la línea; nunca en lugar de palabras clave",
    "instagram": "3 a 6 emojis: uno en el gancho, como viñetas de los párrafos y en el CTA",
    "youtube": "en la descripción, 1 a 3 como viñetas; en el TÍTULO, ninguno o uno como mucho",
    "facebook": "1 a 3 emojis que acompañen, sin recargar",
}
LIMITES = {"tiktok": 2200, "instagram": 2200, "youtube": 5000, "facebook": 5000}

SISTEMA = ("Eres un redactor de redes sociales con oficio: escribes los textos con "
           "los que se publica un vídeo para que la gente pare, lo vea entero y haga "
           "algo. Escribes en el idioma del guion, con el tono pedido, con frases "
           "cortas y saltos de línea que se lean en el móvil. Cada red tiene su "
           "texto: no copies el mismo con otro formato. Nunca inventas datos "
           "(teléfonos, precios, enlaces, fechas, direcciones) que no estén en el "
           "material, y no prometes lo que el vídeo no enseña. Contestas únicamente "
           "con el JSON pedido.")

INSTRUCCION = """Este vídeo ya está montado y hay que publicarlo en: {redes}.

<video>
Nombre: {nombre}
Formato: {formato} · Duración real: {duracion}
Cómo sale en cada red: {encajes}
</video>

<encargo>
Título del encargo: {titulo}
Indicaciones: {instrucciones}
Llamadas a la acción pedidas en el vídeo: {cta}
Material (resumido):
{material}
</encargo>

<guion_final>
{guion}
</guion_final>

<proyecto>
Tono de los textos: {tono}
(La firma y los hashtags fijos del proyecto los añade el Studio después: no los repitas.)
</proyecto>

CÓMO SE ESCRIBE (todas las redes)
- La primera línea es el gancho: lo que hace parar. Nada de «En este vídeo…».
- Frases cortas. Una idea por línea. Línea en blanco entre bloques (en el JSON, "\\n\\n").
- Un solo CTA, claro, con verbo: qué tiene que hacer quien lo ve.
- Hashtags sin almohadilla, mezclando amplios del tema con otros de nicho o de
  la zona (si el material la nombra). Nada de hashtags genéricos vacíos
  («viral», «fyp», «parati») salvo que el tono lo pida.
- {emojis}

REGLAS POR RED
{reglas}

{capitulos}

Devuelve SOLO este JSON, con EXACTAMENTE estas claves de red, en minúsculas y
tal cual: {claves}
{{
  "<red>": {{
    "titulo": "solo YouTube y Facebook; vacío en las demás",
    "descripcion": "el texto principal (gancho en la primera línea), sin hashtags ni CTA",
    "cta": "una frase de llamada a la acción",
    "hashtags": ["sin almohadilla", "..."]
  }}{capitulos_json}
}}
"""


def _cta_como_texto(cta):
    if isinstance(cta, dict):
        return "; ".join(str((v or {}).get("texto") or "") for v in cta.values()
                         if isinstance(v, dict) and v.get("puesto") and v.get("texto")) or "ninguna"
    return str(cta or "ninguna")


def instruccion_textos(info, redes, ajustes):
    encajes = {r: encaje(r, info.get("formato"), info.get("duracion_s")) for r in redes}
    guion = "\n".join(f"- {b.get('texto', '')}" for b in (info.get("guion") or []))
    caps = info.get("capitulos_base") or []
    con_caps = "youtube" in redes and encajes.get("youtube", {}).get("tipo") == "vídeo" and caps
    capitulos = ""
    if con_caps:
        lista = "\n".join(f"{i + 1}. [{_marca_de_tiempo(c['t'])}] {c['texto'][:240]}"
                          for i, c in enumerate(caps))
        capitulos = ("CAPÍTULOS DE YOUTUBE: estos son los tramos del vídeo, con su hora. "
                     "Pon a cada uno un título de 2 a 6 palabras, en el mismo orden:\n" + lista)
    return INSTRUCCION.format(
        redes=", ".join(NOMBRE_RED[r] for r in redes),
        nombre=info.get("nombre") or "", formato=info.get("formato") or "horizontal",
        duracion=_marca_de_tiempo(info.get("duracion_s") or 0),
        encajes="; ".join(f"{NOMBRE_RED[r]}: {e['tipo'] or '—'}" for r, e in encajes.items()),
        titulo=info.get("titulo") or "—", instrucciones=(info.get("instrucciones") or "—")[:1500],
        cta=_cta_como_texto(info.get("cta")),
        material=(info.get("material") or "—")[:MAX_MATERIAL],
        guion=guion[:MAX_GUION] or "—",
        tono=ajustes.get("tono") or "el del guion",
        emojis=("Emojis: sí, bien usados (que aporten, no que decoren): "
                + "; ".join(f"{NOMBRE_RED[r]}, {EMOJIS_RED[r]}" for r in redes) + "."
                if ajustes.get("usar_emojis", True) else
                "Emojis: NINGUNO (el proyecto no los quiere), ni en el título ni en el texto."),
        reglas="\n".join(f"- {NOMBRE_RED[r]}: {REGLAS_RED[r]}" for r in redes),
        capitulos=capitulos,
        claves=", ".join(f'"{r}"' for r in redes),
        capitulos_json=(',\n  "capitulos": ["título del tramo 1", "..."]' if con_caps else ""))


def _limpiar_hashtags(lista):
    salida = []
    for h in (lista if isinstance(lista, list) else re.split(r"[\s,]+", str(lista or ""))):
        h = re.sub(r"[^\w]", "", str(h or "").lstrip("#"), flags=re.U)[:40]
        if h and h.lower() not in {x.lower() for x in salida}:
            salida.append(h)
    return salida[:15]


#: Como puede llamar Claude a cada red y a cada campo. EL 17-10, EN EL
#: SERVIDOR: «textos_escritos» en el log y la ficha vacía. Claude contestaba con
#: la clave «Instagram Reels» (el nombre que lee en la instrucción) en vez de
#: «instagram», y aquí se buscaba solo la exacta: todo salía vacío sin error.
_ALIAS_RED = {"tiktok": ("tiktok", "tik tok"),
              "instagram": ("instagram", "instagramreels", "instagram reels", "reels", "ig"),
              "youtube": ("youtube", "youtubeshorts", "youtube shorts", "shorts", "yt"),
              "facebook": ("facebook", "fb", "facebookreels")}
_ALIAS_CAMPO = {"titulo": ("titulo", "título", "title"),
                "descripcion": ("descripcion", "descripción", "description", "texto",
                                "caption", "pie", "copy", "text"),
                "cta": ("cta", "llamada", "llamada_a_la_accion", "call_to_action"),
                "hashtags": ("hashtags", "etiquetas", "tags")}


def _clave_suelta(texto):
    return re.sub(r"[^a-z0-9]", "", str(texto or "").lower()
                  .translate(str.maketrans("áéíóú", "aeiou")))


def _bloque_de_red(datos, red):
    # tambien si viene envuelto: {"textos": {...}} o {"redes": {...}}
    for envoltorio in ("textos", "redes", "networks"):
        if isinstance(datos.get(envoltorio), dict) and not any(
                isinstance(datos.get(r), dict) for r in REDES):
            datos = datos[envoltorio]
            break
    buscadas = {_clave_suelta(a) for a in _ALIAS_RED[red]}
    for clave, valor in datos.items():
        if isinstance(valor, dict) and _clave_suelta(clave) in buscadas:
            return valor
    return {}


def _campo(bruto, campo):
    buscadas = {_clave_suelta(a) for a in _ALIAS_CAMPO[campo]}
    for clave, valor in bruto.items():
        if _clave_suelta(clave) in buscadas and valor not in (None, ""):
            return valor
    return ""


def normalizar_textos(datos, redes, caps_base=None):
    datos = datos if isinstance(datos, dict) else {}
    textos = {}
    for red in redes:
        bruto = _bloque_de_red(datos, red)
        textos[red] = {
            "titulo": " ".join(str(_campo(bruto, "titulo") or "").split())[:100]
            if red in ("youtube", "facebook") else "",
            "descripcion": str(_campo(bruto, "descripcion") or "").strip()[:LIMITES[red]],
            "cta": " ".join(str(_campo(bruto, "cta") or "").split())[:300],
            "hashtags": _limpiar_hashtags(_campo(bruto, "hashtags")),
        }
    capitulos = []
    titulos = datos.get("capitulos") if isinstance(datos.get("capitulos"), list) else []
    for i, c in enumerate(caps_base or []):
        titulo = " ".join(str(titulos[i] if i < len(titulos) else "").split())[:80]
        if titulo:
            capitulos.append({"t": c["t"], "titulo": titulo})
    if capitulos and len(capitulos) != len(caps_base or []):
        capitulos = []           # a medias no valen: YouTube los quiere todos
    return textos, capitulos


def _textos_simulados(info, redes, raiz=None):
    """El doble de Claude con ESTUDIO_SIMULAR=1: textos fijos sacados del guion,
    con la misma forma que la respuesta de verdad. Ni CLI ni tokens. Con el
    fichero `_sistema/publicar/_fallar_textos` falla, como el CLI sin cupo."""
    if raiz and os.path.exists(os.path.join(carpeta(raiz), "_fallar_textos")):
        time.sleep(2)             # que se vea «Claude está escribiendo» antes del fallo
        raise RuntimeError("el CLI de Claude no ha contestado (simulado)")
    primera = ((info.get("guion") or [{}])[0].get("texto") or info.get("nombre") or "")
    datos = {}
    for red in redes:
        datos[red] = {"titulo": (info.get("nombre") or "Vídeo")[:90]
                      if red in ("youtube", "facebook") else "",
                      "descripcion": f"[{NOMBRE_RED[red]}] {primera}"[:500],
                      "cta": "Escríbenos para reservar.",
                      "hashtags": ["prueba", red]}
    caps = info.get("capitulos_base") or []
    if caps:
        datos["capitulos"] = [f"Parte {i + 1}" for i in range(len(caps))]
    # con `_textos_lentos`, como el CLI de verdad (10-20 s en el servidor)
    lento = raiz and os.path.exists(os.path.join(carpeta(raiz), "_textos_lentos"))
    time.sleep(6 if lento else 0.3)
    return json.dumps(datos, ensure_ascii=False), {"usage": {}, "_coste_anotado": True}


def _escribir_textos(raiz, info, redes, ajustes, proyecto, cwd):
    """El hilo que habla con Claude. Apunta los tokens en el vídeo."""
    pid = info["pid"]
    inicio = time.time()
    try:
        coste = None
        try:
            from nucleo import coste as coste_mod          # noqa: PLC0415
            coste = coste_mod
        except Exception:                                   # noqa: BLE001
            coste = None
        instruccion = instruccion_textos(info, redes, ajustes)

        def llamar():
            return cli_claude.ejecutar(
                instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
                base_tiempo_s=180, tiempo_max_s=TECHO_TEXTOS_S, sistema=SISTEMA,
                extra=["--no-session-persistence"], para="los textos para redes")

        if _simular_todo():
            llamar = lambda: _textos_simulados(info, redes, raiz)  # noqa: E731
        if coste is not None and proyecto is not None:
            with coste.contexto(proyecto, "render"):
                respuesta, sobre = llamar()
                if isinstance(sobre, dict) and not sobre.get("_coste_anotado"):
                    coste.reportar_claude(sobre, operacion="los textos para redes")
                    sobre["_coste_anotado"] = True
        else:
            respuesta, sobre = llamar()
        datos = comun.extraer_json(respuesta, "los textos para redes")
        textos, capitulos = normalizar_textos(datos, redes, info.get("capitulos_base"))
        # LO QUE VINO VACÍO NO PISA NADA, y si no vino nada es un fallo que se
        # ve (con «Reintentar»), no un «escritos» con la ficha en blanco
        vacias = [r for r in redes if not textos[r]["descripcion"]]
        claves = sorted(datos.keys())[:12] if isinstance(datos, dict) else []
        if vacias:
            _log("textos_incompletos", {"video": pid, "vacias": vacias, "claves": claves,
                                         "respuesta": str(respuesta)[:600]})
        textos = {r: t for r, t in textos.items() if t["descripcion"]}
        if not textos:
            raise RuntimeError("Claude ha contestado sin ningún texto que se pueda usar "
                               f"(vino con: {', '.join(map(str, claves)) or 'nada'})")
        with _lock(pid):
            ficha = _leer_video(raiz, pid)
            ficha["textos"].update(textos)
            if "youtube" in redes:
                ficha["capitulos"] = capitulos
            ficha["huella"] = huella_origen(info)
            ficha["escritos"] = _iso_lima()
            ficha["editado"] = False
            _escribir(_ruta_video(raiz, pid), ficha)
        _ERRORES_TEXTOS.pop(pid, None)
        if vacias:
            # unas sí y otras no: lo que falta se dice, con «Reintentar» solo de esas
            _ERRORES_TEXTOS[pid] = ("Claude no ha devuelto el texto de "
                                    + ", ".join(NOMBRE_RED[r] for r in vacias)
                                    + ": pulsa «Reintentar»")
            _REDES_FALLIDAS[pid] = vacias
        _log("textos_escritos", {"video": pid, "redes": list(textos), "modelo": MODELO,
                                 "segundos": round(time.time() - inicio, 1)})
    except Exception as fallo:                              # noqa: BLE001
        # SE APUNTA: el 16-10 fallo en el servidor sin dejar rastro en ningun log
        import traceback                                    # noqa: PLC0415
        _log("textos_fallo", {"video": pid, "redes": redes, "modelo": MODELO,
                              "tipo": type(fallo).__name__, "error": str(fallo)[:800],
                              "traza": traceback.format_exc()[-1500:]})
        _ERRORES_TEXTOS[pid] = (f"no se han podido escribir los textos: "
                                f"{str(fallo)[:400]}")
        _REDES_FALLIDAS[pid] = list(redes)
    finally:
        _ESCRIBIENDO.pop(pid, None)


def lanzar_textos(raiz, info, redes, ajustes, proyecto=None, cwd=None, en_hilo=True):
    """Claude escribe los textos de las redes pedidas. Va en un hilo: detrás del
    proxy una petición de más de un minuto se corta."""
    pid = info["pid"]
    redes = [r for r in (redes or []) if r in REDES]
    if not redes:
        raise ErrorPublicar("elige al menos una red")
    if not info.get("montado"):
        raise ErrorPublicar("este vídeo todavía no está montado", 409)
    with _lock(pid):
        if pid in _ESCRIBIENDO:
            raise ErrorPublicar("ya se están escribiendo los textos de este vídeo", 409)
        _ESCRIBIENDO[pid] = {"desde": _iso_lima(), "redes": redes}
    _ERRORES_TEXTOS.pop(pid, None)
    if not en_hilo:
        _escribir_textos(raiz, info, redes, ajustes, proyecto, cwd)
        return
    threading.Thread(target=_escribir_textos, name=f"textos-{pid}", daemon=True,
                     args=(raiz, info, redes, ajustes, proyecto, cwd)).start()


def _texto_para(textos_red, ajustes, extra=""):
    partes = [str(textos_red.get("descripcion") or "").strip()]
    if extra:
        partes.append(extra)
    if textos_red.get("cta"):
        partes.append(str(textos_red["cta"]).strip())
    if ajustes.get("firma"):
        partes.append(str(ajustes["firma"]).strip())
    tags = _limpiar_hashtags(list(textos_red.get("hashtags") or [])
                             + _limpiar_hashtags(ajustes.get("hashtags") or ""))
    if tags:
        partes.append(" ".join(f"#{t}" for t in tags))
    return "\n\n".join(p for p in partes if p), tags


def componer(red, textos_red, ajustes, info, capitulos=None):
    """Lo que sale en la red: el texto para copiar y los campos de Upload-Post."""
    textos_red = textos_red or {}
    titulo = str(textos_red.get("titulo") or "").strip()
    extra = ""
    # los capitulos, solo en un video de YouTube de verdad: un Short no los usa
    if red == "youtube" and capitulos and \
            encaje(red, info.get("formato"), info.get("duracion_s")).get("tipo") == "vídeo":
        extra = "\n".join(f"{_marca_de_tiempo(c['t'])} {c['titulo']}" for c in capitulos)
    texto, tags = _texto_para(textos_red, ajustes, extra)
    limite = LIMITES[red]
    avisos = []
    if len(texto) > limite:
        avisos.append(f"el texto pasa de {limite} caracteres: se corta al enviarlo")
        texto = texto[:limite]
    if red == "instagram" and len(tags) > 30:
        avisos.append("Instagram acepta como mucho 30 hashtags")
    campos = {}
    ia = bool(ajustes.get("marcar_ia"))
    tipo = encaje(red, info.get("formato"), info.get("duracion_s")).get("tipo")
    if red == "tiktok":
        campos["tiktok_title"] = texto
        if ia:
            campos["is_aigc"] = True
    elif red == "instagram":
        campos["instagram_title"] = texto
        campos["media_type"] = "REELS"
        if ia:
            campos["is_ai_generated"] = True
    elif red == "youtube":
        titulo = re.sub(r"[<>]", "", titulo or info.get("nombre") or "Vídeo")[:100]
        campos["youtube_title"] = titulo
        campos["youtube_description"] = re.sub(r"[<>]", "", texto)
        etiquetas, largo = [], 0
        for t in tags:
            if largo + len(t) + 1 > 450:
                break
            etiquetas.append(t)
            largo += len(t) + 1
        if etiquetas:
            campos["tags[]"] = etiquetas
        campos["privacyStatus"] = ajustes.get("privacidad_youtube") or "public"
        # YouTube avisa de fabrica: solo se manda cuando NO se quiere (el campo
        # no esta en la documentacion de Upload-Post que se leyo; ver NOVEDADES)
        if not ajustes.get("avisar_youtube"):
            campos["notifySubscribers"] = False
        if ia:
            campos["containsSyntheticMedia"] = True
        if not titulo.strip():
            avisos.append("YouTube necesita título")
    elif red == "facebook":
        campos["facebook_title"] = titulo[:255]
        campos["facebook_description"] = texto
        campos["facebook_media_type"] = "REELS" if tipo == "Reel" else "VIDEO"
        if ajustes.get("facebook_pagina"):
            campos["facebook_page_id"] = ajustes["facebook_pagina"]
        if ia:
            campos["facebook_is_ai_generated"] = True
    if not str(textos_red.get("descripcion") or "").strip():
        avisos.append("sin texto todavía")
    return {"texto": texto, "titulo": titulo if red in ("youtube", "facebook") else "",
            "campos": campos, "avisos": avisos}


# ----------------------------------------------------------- textos a mano

def guardar_ficha(raiz, pid, cambios):
    cambios = cambios if isinstance(cambios, dict) else {}
    with _lock(pid):
        ficha = _leer_video(raiz, pid)
        if "redes" in cambios:
            redes = cambios["redes"]
            if not isinstance(redes, list) or any(r not in REDES for r in redes):
                raise ErrorPublicar("las redes son: " + ", ".join(REDES))
            ficha["redes"] = [r for r in REDES if r in redes]
            ficha["redes_puestas"] = True
        if "textos" in cambios:
            textos = cambios["textos"]
            if not isinstance(textos, dict):
                raise ErrorPublicar("«textos» va por red")
            for red, valor in textos.items():
                if red not in REDES or not isinstance(valor, dict):
                    raise ErrorPublicar(f"red desconocida: {red}")
                actual = dict(ficha["textos"].get(red) or {})
                for campo in ("titulo", "descripcion", "cta"):
                    if campo in valor:
                        if not isinstance(valor[campo], str):
                            raise ErrorPublicar(f"«{campo}» es un texto")
                        actual[campo] = valor[campo][:LIMITES[red]]
                if "hashtags" in valor:
                    actual["hashtags"] = _limpiar_hashtags(valor["hashtags"])
                ficha["textos"][red] = actual
            ficha["editado"] = True
        if "capitulos" in cambios:
            caps = cambios["capitulos"]
            if not isinstance(caps, list):
                raise ErrorPublicar("«capitulos» es una lista")
            limpios = []
            for c in caps[:60]:
                if isinstance(c, dict) and str(c.get("titulo") or "").strip():
                    try:
                        limpios.append({"t": max(0, int(c.get("t") or 0)),
                                        "titulo": " ".join(str(c["titulo"]).split())[:80]})
                    except (TypeError, ValueError):
                        raise ErrorPublicar("cada capítulo lleva su segundo y su título") from None
            ficha["capitulos"] = limpios
        if "portada" in cambios:
            ficha["portada"] = _validar_portada(cambios["portada"], ficha.get("portada"))
            if cambios["portada"].get("quitar_imagen"):
                try:
                    os.remove(ruta_portada(raiz, pid))
                except OSError:
                    pass
                ficha["portada"]["imagen"] = ""
        _escribir(_ruta_video(raiz, pid), ficha)
    return ficha


# ------------------------------------------------------------------ la portada
#
# Lo que cada red acepta (docs de Upload-Post, 16-10-2026):
#   Instagram: thumb_offset (ms) o cover_image (JPEG, 8 MB)
#   TikTok:    cover_timestamp (ms) o tiktok_cover_image (solo con la funcion
#              «cover_image» en la cuenta: por eso va aparte y apagado)
#   YouTube:   thumbnail (2 MB; solo canales VERIFICADOS: aparte y apagado)
#   Facebook:  facebook_thumbnail (10 MB), solo si sale como VIDEO, no Reel
# Sin nada elegido no se manda nada y cada red pone la suya.

PORTADA_DEFECTO = {"ms": None, "imagen": "", "youtube": False, "tiktok_imagen": False}
MAX_BYTES_PORTADA = 15 * 1024 * 1024
#: YouTube no acepta una miniatura de mas de 2 MB.
MAX_BYTES_MINIATURA = 2 * 1024 * 1024


def portada_de(datos):
    salida = dict(PORTADA_DEFECTO)
    if isinstance((datos or {}).get("portada"), dict):
        salida.update({k: v for k, v in datos["portada"].items() if k in PORTADA_DEFECTO})
    return salida


def _validar_portada(cambios, actual):
    if not isinstance(cambios, dict):
        raise ErrorPublicar("«portada» va como {ms, youtube, tiktok_imagen}")
    salida = portada_de({"portada": actual})
    if "ms" in cambios:
        ms = cambios["ms"]
        if ms is None or ms == "":
            salida["ms"] = None
        else:
            try:
                ms = int(ms)
            except (TypeError, ValueError):
                raise ErrorPublicar("el fotograma de la portada va en milisegundos") from None
            if ms < 0 or ms > 4 * 3600 * 1000:
                raise ErrorPublicar("ese fotograma no está en el vídeo")
            salida["ms"] = ms
    for k in ("youtube", "tiktok_imagen"):
        if k in cambios:
            if not isinstance(cambios[k], bool):
                raise ErrorPublicar(f"«{k}» es sí o no")
            salida[k] = cambios[k]
    return salida


def ruta_portada(raiz, pid, cual="imagen"):
    """`cual`: "imagen" (la subida) o el lote cuyo fotograma se manda: cada
    lote el suyo, para que dos envios a la vez no se pisen."""
    _ruta_video(raiz, pid)                         # valida el pid
    nombre = f"{pid}.jpg" if cual == "imagen" else \
        f"{pid}_fotograma_{re.sub(r'[^a-z0-9]', '', str(cual).lower())[:16]}.jpg"
    return os.path.join(carpeta(raiz), "portadas", nombre)


def _ffmpeg():
    ruta = shutil.which("ffmpeg")
    if not ruta:
        raise ErrorPublicar("falta ffmpeg en el servidor", 500)
    return ruta


def fotograma(mp4, ms, destino, ancho=0, calidad=3):
    """Saca el fotograma del segundo ms/1000 a un JPEG. Devuelve `destino`."""
    if not mp4 or not os.path.isfile(mp4):
        raise ErrorPublicar("no encuentro el MP4 del vídeo", 404)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    temporal = f"{destino}.{uuid.uuid4().hex[:6]}.jpg"
    orden = [_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0, int(ms or 0)) / 1000:.3f}",
             "-i", mp4, "-frames:v", "1"]
    if ancho:
        orden += ["-vf", f"scale={int(ancho)}:-2"]
    orden += ["-q:v", str(calidad), temporal]
    try:
        subprocess.run(orden, capture_output=True, timeout=40, check=False)
        if not os.path.isfile(temporal) or os.path.getsize(temporal) == 0:
            # pasado el final ffmpeg no saca nada
            raise ErrorPublicar("ese momento está fuera del vídeo", 400)
        os.replace(temporal, destino)
    except (OSError, subprocess.SubprocessError) as fallo:
        raise ErrorPublicar(f"no he podido sacar el fotograma: {fallo}", 500) from None
    finally:
        _quitar(temporal)
    return destino


def _quitar(ruta):
    try:
        os.remove(ruta)
    except OSError:
        pass


def guardar_imagen_portada(raiz, pid, contenido, extension):
    """La imagen subida, pasada a JPEG de 1920 px como mucho y menos de 2 MB
    (lo mas estricto: la miniatura de YouTube)."""
    if extension not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ErrorPublicar("la portada tiene que ser JPG, PNG o WebP")
    if not contenido or len(contenido) > MAX_BYTES_PORTADA:
        raise ErrorPublicar("la portada tiene que pesar menos de 15 MB")
    # EL FORMATO LO DICEN LOS BYTES, y ffmpeg lo lee SOLO como imagen: si
    # adivinara, un «.png» que fuera una lista HLS podria leer ficheros del
    # servidor y devolverlos en la portada.
    if contenido[:8] == b"\x89PNG\r\n\x1a\n":
        lector = "png_pipe"
    elif contenido[:3] == b"\xff\xd8\xff":
        lector = "jpeg_pipe"
    elif contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        lector = "webp_pipe"
    else:
        raise ErrorPublicar("esa imagen no es un JPG, PNG o WebP de verdad")
    destino = ruta_portada(raiz, pid)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    original = f"{destino}.{uuid.uuid4().hex[:8]}.subida"
    with open(original, "wb") as fh:
        fh.write(contenido)
    try:
        for calidad in (3, 6, 10, 16):
            temporal = f"{destino}.{uuid.uuid4().hex[:6]}.jpg"
            subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", lector, "-i", original,
                            "-frames:v", "1",
                            "-vf", "scale='min(1920,iw)':-2", "-q:v", str(calidad), temporal],
                           capture_output=True, timeout=40, check=False)
            try:
                if not os.path.isfile(temporal) or not os.path.getsize(temporal):
                    raise ErrorPublicar("esa imagen no se puede leer")
                if os.path.getsize(temporal) <= MAX_BYTES_MINIATURA or calidad == 16:
                    os.replace(temporal, destino)
                    break
            finally:
                _quitar(temporal)
    except (OSError, subprocess.SubprocessError) as fallo:
        raise ErrorPublicar(f"no he podido guardar la portada: {fallo}", 500) from None
    finally:
        _quitar(original)
    sello = hashlib.sha1(contenido).hexdigest()[:10]
    with _lock(pid):
        ficha = _leer_video(raiz, pid)
        ficha["portada"] = dict(portada_de(ficha), imagen=sello)
        _escribir(_ruta_video(raiz, pid), ficha)
    return ficha["portada"]


def campos_portada(raiz, info, datos, redes, lote="vista"):
    """(campos, ficheros) de la portada para Upload-Post, segun lo elegido."""
    portada = portada_de(datos)
    campos, ficheros = {}, []
    imagen = ruta_portada(raiz, info["pid"]) if portada["imagen"] else ""
    if imagen and not os.path.isfile(imagen):
        imagen = ""
    ms = portada["ms"]
    if not imagen and ms is None:
        return campos, ficheros
    # SIEMPRE DENTRO DEL VIDEO: si se volvio a montar mas corto, el momento
    # elegido podria caer fuera y la red rechazar la subida
    try:
        duracion_ms = int(float(info.get("duracion_s") or 0) * 1000)
    except (TypeError, ValueError):
        duracion_ms = 0
    if ms is not None and duracion_ms > 0:
        ms = max(0, min(int(ms), duracion_ms - 100))
    foto = imagen
    if not foto and (("youtube" in redes and portada["youtube"]) or "facebook" in redes):
        try:
            foto = fotograma(info.get("mp4"), ms, ruta_portada(raiz, info["pid"], lote))
        except ErrorPublicar:
            foto = ""            # sin el fotograma, cada red pone la suya
    if "instagram" in redes:
        if imagen:
            ficheros.append(("cover_image", imagen))
        else:
            campos["thumb_offset"] = str(ms)
    if "tiktok" in redes:
        if imagen and portada["tiktok_imagen"]:
            ficheros.append(("tiktok_cover_image", imagen))
        elif ms is not None:
            campos["cover_timestamp"] = int(ms)
    if "youtube" in redes and portada["youtube"] and foto \
            and os.path.getsize(foto) <= MAX_BYTES_MINIATURA:
        ficheros.append(("thumbnail", foto))
    if "facebook" in redes and foto and \
            encaje("facebook", info.get("formato"), info.get("duracion_s")).get("tipo") != "Reel":
        ficheros.append(("facebook_thumbnail", foto))
    return campos, ficheros


# -------------------------------------------------------------- la ficha

def _envio_publico(e):
    return {k: e.get(k) for k in (
        "id", "red", "estado", "modo", "cuando", "creado", "actualizado", "url",
        "error", "lote", "perfil", "mp4_huella", "nota", "programado_para", "sin_hora",
        "metricas")}


def ficha(raiz, info, ajustes):
    """Todo lo que la pantalla de un vídeo necesita para publicarlo."""
    pid = info["pid"]
    datos = _leer_video(raiz, pid)
    redes = datos["redes"] if datos.get("redes_puestas") else list(ajustes.get("redes") or REDES)
    huella = huella_origen(info) if info.get("montado") else ""
    hay_textos = any(str((datos["textos"].get(r) or {}).get("descripcion") or "").strip()
                     for r in REDES)
    desactualizada = bool(hay_textos and datos.get("huella") and huella
                          and datos["huella"] != huella)
    compuestos = {r: componer(r, datos["textos"].get(r), ajustes, info, datos.get("capitulos"))
                  for r in REDES}
    for r in compuestos:
        compuestos[r].pop("campos", None)
    envios = [_envio_publico(e) for e in datos["envios"]]
    viejos = [e for e in datos["envios"] if e.get("estado") == "programado"
              and e.get("mp4_huella") and info.get("mp4_huella")
              and e["mp4_huella"] != info["mp4_huella"]]
    return {
        "pid": pid, "nombre": info.get("nombre") or pid,
        "cliente": info.get("cliente") or "", "cliente_nombre": info.get("cliente_nombre") or "",
        "montado": bool(info.get("montado")), "mp4": info.get("mp4_rel") or "",
        "formato": info.get("formato") or "horizontal",
        "duracion_s": info.get("duracion_s") or 0,
        "redes": redes, "textos": datos["textos"], "capitulos": datos.get("capitulos") or [],
        "capitulos_posibles": len(info.get("capitulos_base") or []),
        "compuestos": compuestos,
        "encaje": {r: encaje(r, info.get("formato"), info.get("duracion_s")) for r in REDES},
        "desactualizada": desactualizada, "escritos": datos.get("escritos") or "",
        "editado": bool(datos.get("editado")),
        "portada": portada_de(datos),
        "escribiendo": pid in _ESCRIBIENDO, "error_textos": _ERRORES_TEXTOS.get(pid, ""),
        "error_redes": _REDES_FALLIDAS.get(pid, []) if pid in _ERRORES_TEXTOS else [],
        "escribiendo_desde": (_ESCRIBIENDO.get(pid) or {}).get("desde", ""),
        "escribiendo_redes": (_ESCRIBIENDO.get(pid) or {}).get("redes", []),
        "envios": sorted(envios, key=lambda e: str(e.get("cuando") or ""), reverse=True),
        "programados_viejos": len(viejos),
        "ajustes": {k: v for k, v in ajustes.items() if k != "cuentas"},
        "cuentas": ajustes.get("cuentas") or {},
        "clave": estado_clave(), "hora_sugerida": proxima_hora(ajustes.get("hora")),
        "ahora": _iso_lima(),
    }


def proxima_hora(hora):
    """La próxima vez que el reloj de Lima marca esa hora (hoy o mañana)."""
    try:
        h, m = [int(x) for x in str(hora or "19:00").split(":")]
    except ValueError:
        h, m = 19, 0
    ahora = ahora_lima()
    momento = ahora.replace(hour=h, minute=m, second=0)
    if momento <= ahora + dt.timedelta(minutes=5):
        momento += dt.timedelta(days=1)
    return momento.strftime("%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------- enviar

def enviar(raiz, info, ajustes, cuerpo, en_hilo=True):
    """Prepara un envío por red y, si está confirmado, lo sube.

    cuerpo = {redes: [...], modo: ahora|programar|pendiente, cuando: «AAAA-MM-DDTHH:MM»,
              confirmado: bool, repetir: bool}
    """
    pid = info["pid"]
    cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
    redes = cuerpo.get("redes")
    if not isinstance(redes, list) or not redes or any(r not in REDES for r in redes):
        raise ErrorPublicar("elige al menos una red")
    redes = [r for r in REDES if r in redes]
    modo = cuerpo.get("modo")
    if modo not in ("ahora", "programar", "pendiente"):
        raise ErrorPublicar("«modo» es ahora, programar o pendiente")
    if not info.get("montado") or not info.get("mp4") or not os.path.isfile(info["mp4"]):
        raise ErrorPublicar("este vídeo todavía no está montado: móntalo antes de publicarlo", 409)
    if modo != "pendiente" and cuerpo.get("confirmado") is not True:
        raise ErrorPublicar("falta confirmar el envío: nada sale sin tu OK", 400)
    cuando = None
    if modo in ("programar", "pendiente") and cuerpo.get("cuando"):
        momento = _leer_momento(cuerpo.get("cuando"))
        if momento is None:
            raise ErrorPublicar("la fecha va como 2026-10-17T19:00 (hora de Lima)")
        if momento <= ahora_lima() + dt.timedelta(minutes=2):
            raise ErrorPublicar("esa hora ya ha pasado (o es ahora mismo): elige una futura")
        if momento > ahora_lima() + dt.timedelta(days=364):
            raise ErrorPublicar("Upload-Post programa como mucho con un año de antelación")
        cuando = momento.strftime("%Y-%m-%dT%H:%M:%S")
    elif modo == "programar":
        raise ErrorPublicar("falta el día y la hora")
    perfil = str(ajustes.get("perfil") or "").strip()
    if modo != "pendiente" and not perfil:
        raise ErrorPublicar("este proyecto no tiene perfil de Upload-Post: ponlo en "
                            "Publicar → Cuentas y ajustes (o publica a mano)", 409)
    if modo != "pendiente":
        cliente(raiz)                      # sin clave, se dice ANTES de apuntar nada
    errores = [f"{NOMBRE_RED[r]}: {encaje(r, info.get('formato'), info.get('duracion_s'))['texto']}"
               for r in redes
               if encaje(r, info.get("formato"), info.get("duracion_s"))["nivel"] == "error"]
    if errores:
        raise ErrorPublicar("; ".join(errores))
    # UNA RED SIN CUENTA CONECTADA gastaria una subida del mes para nada (Upload-
    # Post la salta). Solo si ya se miraron las cuentas: sin mirar, no se sabe.
    cuentas = ajustes.get("cuentas") or {}
    if modo != "pendiente" and ajustes.get("cuentas_vistas"):
        sin_cuenta = [NOMBRE_RED[r] for r in redes if r in cuentas and (
            not cuentas.get(r) or (cuentas.get(r) or {}).get("reconectar"))]
        if sin_cuenta:
            raise ErrorPublicar(
                ", ".join(sin_cuenta) + " no tiene cuenta conectada en Upload-Post. Conéctala "
                "(Cuentas y ajustes → Conectar y después «Ver cuentas») o quítala de este envío.", 409)
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        if not cuerpo.get("repetir"):
            # CUALQUIER envio vivo de este video en esa red, sea cual sea el MP4:
            # volver a montar (un subtitulo) cambia el fichero, no el video
            vivos = [e for e in datos["envios"]
                     if e.get("red") in redes and e.get("estado") in VIVOS]
            if vivos:
                nombres = ", ".join(sorted({NOMBRE_RED[e["red"]] for e in vivos}))
                otro = any(e.get("mp4_huella") != info.get("mp4_huella") for e in vivos)
                raise ErrorPublicar(
                    f"este vídeo ya está publicado o programado en {nombres}"
                    + (" (con un montaje anterior)" if otro else "")
                    + ". Si de verdad quieres publicarlo otra vez, confírmalo.", 409)
        sin_texto = [NOMBRE_RED[r] for r in redes
                     if not str((datos["textos"].get(r) or {}).get("descripcion") or "").strip()]
        if sin_texto and modo != "pendiente":
            raise ErrorPublicar("falta el texto de " + ", ".join(sin_texto)
                                + ": escríbelo o pide que lo escriba Claude", 409)
        lote = uuid.uuid4().hex[:20]
        nuevos = []
        for red in redes:
            nuevos.append({
                "id": uuid.uuid4().hex[:12], "red": red, "lote": lote, "perfil": perfil,
                "estado": "espera_ok" if modo == "pendiente" else "enviando",
                "modo": "ahora" if modo == "ahora" else "programado",
                "cuando": cuando or _iso_lima(), "creado": _iso_lima(),
                "actualizado": _iso_lima(), "url": "", "error": "",
                "mp4_huella": info.get("mp4_huella") or "",
                "sin_hora": modo == "pendiente" and not cuando,
            })
        datos["envios"].extend(nuevos)
        _escribir(_ruta_video(raiz, pid), datos)
    if modo != "pendiente":
        _subir_lote(raiz, info, ajustes, lote, en_hilo=en_hilo)
    return [_envio_publico(e) for e in nuevos]


def confirmar(raiz, info, ajustes, eid, cuerpo, en_hilo=True):
    """Un envío en «espera tu OK» sale ya (o a su hora)."""
    cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
    if cuerpo.get("confirmado") is not True:
        raise ErrorPublicar("falta confirmar el envío: nada sale sin tu OK")
    pid = info["pid"]
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        envio = next((e for e in datos["envios"] if e.get("id") == eid), None)
        if envio is None:
            raise ErrorPublicar("ese envío no existe", 404)
        if envio.get("estado") != "espera_ok":
            raise ErrorPublicar("ese envío ya no espera confirmación", 409)
    # se rehace como un envío nuevo con lo que se pida ahora: la hora puede
    # haber pasado mientras esperaba
    pedido = {"redes": [envio["red"]], "confirmado": True,
              "repetir": bool(cuerpo.get("repetir")),
              "modo": cuerpo.get("modo") or ("programar" if not envio.get("sin_hora") else "ahora"),
              "cuando": cuerpo.get("cuando") or (envio.get("cuando") if not envio.get("sin_hora") else "")}
    nuevos = enviar(raiz, info, ajustes, pedido, en_hilo=en_hilo)
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        for e in datos["envios"]:
            if e.get("id") == eid:
                e["estado"] = "cancelado"
                e["nota"] = "confirmado: sigue en el envío nuevo"
                e["actualizado"] = _iso_lima()
        _escribir(_ruta_video(raiz, pid), datos)
    return nuevos


def _actualizar_lote(raiz, pid, lote, fn):
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        tocados = 0
        for e in datos["envios"]:
            if e.get("lote") == lote:
                fn(e)
                e["actualizado"] = _iso_lima()
                tocados += 1
        if tocados:
            _escribir(_ruta_video(raiz, pid), datos)
        return tocados


def _subir_lote(raiz, info, ajustes, lote, en_hilo=True):
    pid = info["pid"]
    datos = _leer_video(raiz, pid)
    envios = [e for e in datos["envios"] if e.get("lote") == lote]
    if not envios:
        return
    redes = [e["red"] for e in envios]
    campos = {}
    titulo_general = ""
    for e in envios:
        comp = componer(e["red"], datos["textos"].get(e["red"]), ajustes, info,
                        datos.get("capitulos"))
        campos.update(comp["campos"])
        if comp.get("titulo") and not titulo_general:
            titulo_general = comp["titulo"]
    if not titulo_general:
        # sin YouTube ni Facebook: la primera línea del texto (en Instagram y
        # TikTok el «título» es eso), o el nombre del vídeo
        for e in envios:
            primera = str((datos["textos"].get(e["red"]) or {}).get("descripcion") or "").strip()
            if primera:
                titulo_general = primera.splitlines()[0].strip()
                break
    campos["title"] = (titulo_general or info.get("nombre") or "Vídeo")[:100]
    try:
        extra, ficheros = campos_portada(raiz, info, datos, redes, lote)
    except Exception as fallo:                              # noqa: BLE001
        # la portada nunca deja un envio colgado: sale sin ella
        _log("portada_fallo", {"video": pid, "error": str(fallo)[:300]})
        extra, ficheros = {}, []
    campos.update(extra)
    cuando = envios[0]["cuando"] if envios[0].get("modo") == "programado" else None
    perfil = envios[0].get("perfil") or ajustes.get("perfil")

    _SUBIENDO.add(lote)          # ANTES del hilo: /refrescar no lo da por huerfano

    def trabajo():
        try:
            r = cliente(raiz).publicar(perfil, redes, info["mp4"], campos, cuando=cuando,
                                       zona=ZONA, id_propio=lote, ficheros=ficheros)
        except UP.ErrorUploadPost as fallo:
            mensaje = str(fallo)
            if fallo.sin_respuesta:
                _actualizar_lote(raiz, pid, lote, lambda e: e.update(
                    estado="comprobar", error=f"{mensaje}. No se reenvía solo, para no "
                    "publicarlo dos veces: se sigue preguntando por él."))
            else:
                _actualizar_lote(raiz, pid, lote, lambda e: e.update(
                    estado="fallido", error=mensaje))
            return
        except ErrorPublicar as fallo:
            _actualizar_lote(raiz, pid, lote, lambda e: e.update(
                estado="fallido", error=str(fallo)))
            return
        except Exception as fallo:                          # noqa: BLE001
            _actualizar_lote(raiz, pid, lote, lambda e: e.update(
                estado="comprobar", error=f"fallo inesperado al subir: {str(fallo)[:300]}"))
            return
        finally:
            _SUBIENDO.discard(lote)
            for _campo, ruta in ficheros:
                if os.path.basename(ruta).startswith(f"{pid}_fotograma_"):
                    _quitar(ruta)
        resultados = r.get("resultados") or {}

        def aplicar(e):
            e["request_id"] = r.get("request_id") or ""
            e["job_id"] = r.get("job_id") or ""
            if r.get("programado_para"):
                e["programado_para"] = r["programado_para"]
            propio = resultados.get(e["red"])
            if propio:
                e["estado"] = propio["estado"] if propio["estado"] in ESTADOS else "publicando"
                e["url"] = propio.get("url") or ""
                e["error"] = propio.get("error") or ""
            else:
                e["estado"] = "programado" if r.get("modo") == "programado" else "publicando"
                e["error"] = ""
            if r.get("avisos"):
                e["nota"] = "; ".join(r["avisos"])[:500]
        _actualizar_lote(raiz, pid, lote, aplicar)

    if en_hilo:
        threading.Thread(target=trabajo, name=f"subida-{lote}", daemon=True).start()
    else:
        trabajo()


def reintentar(raiz, info, ajustes, eid, en_hilo=True):
    """Vuelve a mandar un envío en «comprobar» CON SU MISMA clave de idempotencia:
    si Upload-Post ya lo tenía, devuelve el mismo trabajo y no se publica dos veces."""
    pid = info["pid"]
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        envio = next((e for e in datos["envios"] if e.get("id") == eid), None)
        if envio is None:
            raise ErrorPublicar("ese envío no existe", 404)
        if envio.get("estado") != "comprobar" or not envio.get("lote"):
            raise ErrorPublicar("solo se reintenta un envío que quedó sin confirmar "
                                "(«comprobar»); lo demás se publica otra vez como envío nuevo", 409)
        if envio["lote"] in _SUBIENDO:
            raise ErrorPublicar("ese envío se está subiendo ahora mismo", 409)
        if envio.get("modo") == "programado":
            momento = _leer_momento(envio.get("cuando"))
            if momento and momento <= ahora_lima() + dt.timedelta(minutes=2):
                raise ErrorPublicar("su hora ya pasó: mira en Upload-Post si salió, y si no, "
                                    "publícalo como envío nuevo", 409)
        cliente(raiz)
        # mirar y pasar a «enviando» bajo el MISMO cerrojo: dos clics, una subida
        for e in datos["envios"]:
            if e.get("lote") == envio["lote"]:
                e.update(estado="enviando", error="", nota="reintentado con la misma clave",
                         reintentado=_iso_lima(), actualizado=_iso_lima())
        _escribir(_ruta_video(raiz, pid), datos)
        _SUBIENDO.add(envio["lote"])
    _NO_LO_CONOCE.pop(envio["lote"], None)
    _subir_lote(raiz, info, ajustes, envio["lote"], en_hilo=en_hilo)
    return {"lote": envio["lote"]}


def cancelar(raiz, pid, eid):
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        envio = next((e for e in datos["envios"] if e.get("id") == eid), None)
    if envio is None:
        raise ErrorPublicar("ese envío no existe", 404)
    estado = envio.get("estado")
    if estado == "programado":
        if not envio.get("job_id"):
            raise ErrorPublicar("Upload-Post todavía no le ha dado número de trabajo a este "
                                "envío: espera un momento y vuelve a intentarlo", 409)
        hermanos = [e for e in datos["envios"] if e.get("lote") == envio.get("lote")
                    and e.get("estado") == "programado"]
        _por_upload_post(cliente(raiz).cancelar, envio["job_id"])
        # Upload-Post cancela el TRABAJO entero: todas las redes de ese envío
        _actualizar_lote(raiz, pid, envio["lote"], lambda e: e.update(
            estado="cancelado", nota="cancelado antes de salir") if e.get("estado") == "programado" else None)
        return {"cancelados": [e["red"] for e in hermanos]}
    if estado == "espera_ok":
        with _lock(pid):
            datos = _leer_video(raiz, pid)
            for e in datos["envios"]:
                if e.get("id") == eid:
                    e["estado"] = "cancelado"
                    e["actualizado"] = _iso_lima()
            _escribir(_ruta_video(raiz, pid), datos)
        return {"cancelados": [envio["red"]]}
    if estado in ("fallido", "comprobar"):
        # «Quitar de la lista»: un fallo ya visto (o un «comprobar» que ya se
        # miro en Upload-Post) no se queda en «Te necesitan» para siempre
        with _lock(pid):
            datos = _leer_video(raiz, pid)
            for e in datos["envios"]:
                if e.get("id") == eid:
                    e["nota"] = ("fallo descartado" if estado == "fallido"
                                 else "quitado de la lista tras mirarlo en Upload-Post")
                    e["estado"] = "cancelado"
                    e["actualizado"] = _iso_lima()
            _escribir(_ruta_video(raiz, pid), datos)
        return {"cancelados": [envio["red"]]}
    raise ErrorPublicar("solo se cancela lo que está programado o esperando tu OK "
                        "(y un fallo se quita de la lista)", 409)


def marcar_a_mano(raiz, info, red, url=""):
    """«Lo he subido yo»: queda en el historial con su enlace, si lo hay."""
    if red not in REDES:
        raise ErrorPublicar("red desconocida")
    url = str(url or "").strip()
    if url and not re.match(r"^https?://\S+$", url):
        raise ErrorPublicar("el enlace empieza por https://")
    pid = info["pid"]
    with _lock(pid):
        datos = _leer_video(raiz, pid)
        envio = {"id": uuid.uuid4().hex[:12], "red": red, "lote": "", "perfil": "",
                 "estado": "a_mano", "modo": "manual", "cuando": _iso_lima(),
                 "creado": _iso_lima(), "actualizado": _iso_lima(), "url": url[:500],
                 "error": "", "mp4_huella": info.get("mp4_huella") or ""}
        datos["envios"].append(envio)
        _escribir(_ruta_video(raiz, pid), datos)
    return _envio_publico(envio)


# ------------------------------------------------------------- refrescar

def _videos_con_ficha(raiz):
    base = os.path.join(carpeta(raiz), "videos")
    try:
        nombres = sorted(os.listdir(base))
    except OSError:
        return []
    return [n[:-5] for n in nombres if n.endswith(".json") and re.match(r"^[a-z0-9_]+\.json$", n)]


_LOCK_REFRESCO = threading.Lock()


def refrescar(raiz, limite=8):
    """Pregunta a Upload-Post por lo que sigue en el aire. -> {consultados, cambios}

    De uno en uno: con dos pestañas abiertas, el segundo no pregunta lo mismo."""
    if not _LOCK_REFRESCO.acquire(blocking=False):
        return {"consultados": 0, "cambios": 0, "ocupado": True}
    try:
        return _refrescar(raiz, limite)
    finally:
        _LOCK_REFRESCO.release()


def _refrescar(raiz, limite):
    pendientes = {}
    ahora = ahora_lima()
    for pid in _videos_con_ficha(raiz):
        for e in _leer_video(raiz, pid)["envios"]:
            estado = e.get("estado")
            if estado not in PENDIENTES or not e.get("lote"):
                continue
            if estado == "enviando":
                if e["lote"] in _SUBIENDO:
                    continue
                creado = _leer_momento(e.get("reintentado") or e.get("creado"))
                if creado and (ahora - creado).total_seconds() > HUERFANO_S:
                    _actualizar_lote(raiz, pid, e["lote"], lambda x: x.update(
                        estado="comprobar", error="la subida se cortó a medias (el "
                        "servicio se reinició): no se reenvía sola; mira en Upload-Post"))
                continue
            if estado == "programado" and e.get("job_id"):
                momento = _leer_momento(e.get("cuando"))
                if momento and momento > ahora:
                    continue
            pendientes.setdefault(e["lote"], (pid, e))
    if not pendientes:
        return {"consultados": 0, "cambios": 0}
    try:
        cli = cliente(raiz)
    except ErrorPublicar:
        return {"consultados": 0, "cambios": 0, "sin_clave": True}
    # EL RESPIRO ANTES DE CORTAR, y primero lo que hace mas que no se mira: con
    # el corte primero, ocho envios atascados dejaban sin mirar a todos los demas
    listos = [(lote, par) for lote, par in pendientes.items()
              if time.time() - _ULTIMA_CONSULTA.get(lote, 0) >= RESPIRO_CONSULTA_S]
    listos.sort(key=lambda x: _ULTIMA_CONSULTA.get(x[0], 0))
    consultados = cambios = 0
    for lote, (pid, e) in listos[:limite]:
        _ULTIMA_CONSULTA[lote] = time.time()
        consultados += 1
        try:
            if e.get("job_id"):
                r = cli.estado(job_id=e["job_id"])
            else:
                r = cli.estado(request_id=e.get("request_id") or lote)
        except UP.ErrorUploadPost as fallo:
            if fallo.codigo == 404:
                veces = _NO_LO_CONOCE.get(lote, 0) + 1
                _NO_LO_CONOCE[lote] = veces
                creado = _leer_momento(e.get("creado"))
                viejo = creado is None or (ahora - creado).total_seconds() > 1800
                # SOLO lo que era para «ya»: de una programada no esta claro que
                # Upload-Post responda por request_id, y darla por no llegada
                # dejaria publicarla otra vez mientras sigue programada alli
                if veces >= VECES_NO_LO_CONOCE and viejo and e.get("modo") == "ahora" \
                        and e.get("estado") in ("comprobar", "publicando"):
                    _actualizar_lote(raiz, pid, lote, lambda x: x.update(
                        estado="fallido", error="Upload-Post no conoce este envío: no llegó. "
                        "Puedes publicarlo otra vez."))
                    _NO_LO_CONOCE.pop(lote, None)
                    cambios += 1
            continue
        _NO_LO_CONOCE.pop(lote, None)
        redes = r.get("redes") or {}
        general = r.get("estado") or ""
        nuevo_job = r.get("job_id") or ""

        def aplicar(x, redes=redes, general=general, nuevo_job=nuevo_job):
            if nuevo_job and not x.get("job_id"):
                x["job_id"] = nuevo_job
            propio = redes.get(x["red"])
            if general in ("cancelled", "canceled"):
                x["estado"] = "cancelado"
                return
            if general in ("scheduled", "pending", "queued") and x.get("modo") == "programado" \
                    and x["estado"] in ("publicando", "comprobar"):
                x["estado"] = "programado"
                x["error"] = ""
                return
            if propio:
                nuevo = propio["estado"]
                if nuevo == "procesando":
                    nuevo = "publicando"
                if nuevo == "publicando" and x["estado"] == "programado":
                    momento = _leer_momento(x.get("cuando"))
                    if momento and momento > ahora:
                        nuevo = "programado"        # aun no es su hora
                if nuevo in ESTADOS and nuevo != x["estado"]:
                    x["estado"] = nuevo
                if propio.get("url"):
                    x["url"] = propio["url"]
                if propio.get("error"):
                    x["error"] = propio["error"]
                elif nuevo == "publicado":
                    x["error"] = ""
            elif general == "completed" and x["estado"] in ("publicando", "comprobar", "programado"):
                x["estado"] = "publicado"
                x["error"] = ""
            elif general == "failed":
                x["estado"] = "fallido"
                x["error"] = r.get("mensaje") or "Upload-Post dice que falló"
            elif general in ("processing", "in_progress") and x["estado"] == "comprobar":
                x["estado"] = "publicando"
                x["error"] = ""

        antes = json.dumps(_leer_video(raiz, pid)["envios"], sort_keys=True)
        _actualizar_lote(raiz, pid, lote, aplicar)
        if json.dumps(_leer_video(raiz, pid)["envios"], sort_keys=True) != antes:
            cambios += 1
    # las memorias de consulta no crecen sin fin
    vivos = set(pendientes)
    for memoria in (_ULTIMA_CONSULTA, _NO_LO_CONOCE):
        for lote in [k for k in memoria if k not in vivos]:
            memoria.pop(lote, None)
    return {"consultados": consultados, "cambios": cambios}


# ------------------------------------------------------------------ cola

def cola(raiz, videos, desde=None, dias=7):
    """Los vídeos listos para publicar y los envíos de la semana.

    `videos` = [{pid, nombre, cliente, cliente_nombre, montado, actualizado}] de
    los que quien pregunta PUEDE ver (los de un proyecto con clave cerrado ya
    vienen quitados)."""
    try:
        dias = max(1, min(int(dias or 7), 42))
    except (TypeError, ValueError):
        dias = 7
    inicio = _leer_momento(desde) if desde else None
    hoy = ahora_lima().replace(hour=0, minute=0, second=0)
    if inicio is None:
        inicio = hoy - dt.timedelta(days=hoy.weekday())       # el lunes
    inicio = inicio.replace(hour=0, minute=0, second=0)
    fin = inicio + dt.timedelta(days=dias)
    visibles = {v["pid"]: v for v in videos}
    con_ficha = set(_videos_con_ficha(raiz))
    listos, envios = [], []
    for v in videos:
        datos = _leer_video(raiz, v["pid"]) if v["pid"] in con_ficha else None
        propios = (datos or {}).get("envios") or []
        resumen, salio = {}, {}
        for e in propios:                      # en orden: el ultimo manda
            if e.get("estado") == "cancelado":
                continue
            resumen[e["red"]] = e.get("estado")
            if e.get("estado") in ("publicado", "a_mano"):
                salio[e["red"]] = e["estado"]
        resumen.update({r: est for r, est in salio.items()
                        if resumen.get(r) not in ("programado", "enviando", "publicando")})
        if v.get("montado"):
            listos.append(dict(v, envios=resumen,
                               redes_elegidas=(datos or {}).get("redes")
                               if (datos or {}).get("redes_puestas") else None,
                               textos=bool(datos and any(
                                   (datos.get("textos") or {}).get(r, {}).get("descripcion")
                                   for r in REDES))))
        for e in propios:
            momento = _leer_momento(e.get("cuando"))
            if momento is None:
                continue
            # lo que te necesita sale aunque sea de otra semana
            if inicio <= momento < fin or e.get("estado") in ("espera_ok", "fallido", "comprobar"):
                envios.append(dict(_envio_publico(e), pid=v["pid"],
                                   video=visibles[v["pid"]].get("nombre") or v["pid"],
                                   cliente=v.get("cliente") or "",
                                   cliente_nombre=v.get("cliente_nombre") or ""))
    envios.sort(key=lambda e: str(e.get("cuando") or ""))
    listos.sort(key=lambda v: str(v.get("actualizado") or ""), reverse=True)
    dias_lista = [(inicio + dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias)]
    hoy_txt = hoy.strftime("%Y-%m-%d")
    return {"listos": listos, "envios": envios, "dias": dias_lista,
            "desde": inicio.strftime("%Y-%m-%d"), "hoy": hoy_txt, "ahora": _iso_lima(),
            "de_hoy": [e for e in envios if str(e.get("cuando") or "").startswith(hoy_txt)],
            "esperan_ok": [e for e in envios if e.get("estado") == "espera_ok"],
            "fallidos": [e for e in envios if e.get("estado") in ("fallido", "comprobar")],
            "clave": estado_clave()}


# ----------------------------------------------------------------- metricas
#
# LAS CIFRAS DE LO PUBLICADO (rama publicar-redes-1, segunda parte). Upload-Post
# las pide EN VIVO a cada red y deja 100 consultas cada 5 minutos por cuenta,
# asi que aqui se piden solo al pulsar «Actualizar», como mucho LOTES_POR_VUELTA
# envios por vez, y un envio que se miro hace menos de RESPIRO_METRICAS_S no se
# vuelve a pedir. Lo ultimo que se supo se guarda en el propio envio
# (`metricas`, con su hora), y de ahi sale todo lo que se ensena: la ficha, el
# resumen por proyecto y, mas adelante, la Parrilla y el piloto.
#
# Un numero que la red no da se queda en None: «no lo dice» no es «cero».

METRICAS = ("vistas", "me_gusta", "comentarios", "compartidos", "guardados")
#: La retencion (publicar-redes-2): no se suma, se promedia PONDERADA POR VISTAS
#: (un post de 50 vistas no pesa lo mismo que uno de 100.000). Son tres medidas
#: distintas que no se mezclan (ver el cliente): `vista_entera` (TikTok: la
#: fraccion que lo vio hasta el final), `media_vista` (YouTube: que parte se ve
#: de media; pasa de 1 si se vuelve a ver) y `tiempo_medio_s`.
RETENCION = ("vista_entera", "media_vista", "tiempo_medio_s")
LOTES_POR_VUELTA = 30
RESPIRO_METRICAS_S = float(os.environ.get("ESTUDIO_METRICAS_RESPIRO") or 600)


def _id_de_envio(e):
    """Con que id se le pregunta a Upload-Post por un envio: el que DEVOLVIO al
    subirlo, y si no devolvio ninguno, el que le mandamos (el lote)."""
    return e.get("request_id") or e.get("lote") or ""


def _lotes_publicados(raiz, pids):
    """{id del envio: [(pid, envio)]} de lo publicado por Upload-Post (los «a
    mano» no tienen numero de envio y no se pueden preguntar)."""
    lotes = {}
    for pid in pids:
        for e in _leer_video(raiz, pid)["envios"]:
            if e.get("estado") == "publicado" and e.get("lote"):
                lotes.setdefault(_id_de_envio(e), []).append((pid, e))
    return lotes


def _mirado_hace(envios):
    momentos = [_leer_momento((e.get("metricas") or {}).get("al")) for _p, e in envios]
    momentos = [m for m in momentos if m]
    if len(momentos) < len(envios) or not momentos:
        return None
    return (ahora_lima() - min(momentos)).total_seconds()


_LOCK_METRICAS = threading.Lock()
#: Tope de tiempo de una vuelta: detras del proxy una peticion de mas de 60 s
#: se corta. Lo que no de tiempo queda en `pendientes` para la siguiente.
TOPE_VUELTA_S = float(os.environ.get("ESTUDIO_METRICAS_TOPE") or 40)
#: Plazo de cada consulta en vivo: una consulta no se EMPIEZA si no cabe entera
#: dentro del tope (antes una empezada a los 39 s con plazo de 30 llegaba a ~70 s
#: y el proxy cortaba la peticion de la pantalla a los 60).
PLAZO_METRICAS_S = 15


def actualizar_metricas(raiz, pids, forzar=False, limite=LOTES_POR_VUELTA):
    """Pide a Upload-Post las cifras de lo publicado de estos videos.
    -> {"consultados", "actualizados", "pendientes", "errores": [...], "ocupado"?}

    De una en una (dos pestañas no gastan el doble del cupo de consultas)."""
    if not _LOCK_METRICAS.acquire(blocking=False):
        return {"consultados": 0, "actualizados": 0, "pendientes": 0, "ocupado": True,
                "errores": ["ya se están pidiendo las cifras: espera un momento"]}
    try:
        return _actualizar_metricas(raiz, pids, forzar, limite)
    finally:
        _LOCK_METRICAS.release()


def _actualizar_metricas(raiz, pids, forzar, limite):
    lotes = _lotes_publicados(raiz, pids)
    candidatos = []
    for lote, envios in lotes.items():
        hace = _mirado_hace(envios)
        if not forzar and hace is not None and hace < RESPIRO_METRICAS_S:
            continue
        candidatos.append((hace if hace is not None else float("inf"), lote, envios))
    # primero lo que nunca se miro, despues lo que hace mas que no
    candidatos.sort(key=lambda x: -x[0])
    if not candidatos:
        return {"consultados": 0, "actualizados": 0, "pendientes": 0, "errores": []}
    cli = cliente(raiz)
    consultados = actualizados = 0
    errores = []
    arranque = time.time()
    for _hace, lote, envios in candidatos[:limite]:
        if time.time() - arranque > TOPE_VUELTA_S - PLAZO_METRICAS_S:
            break
        try:
            cifras = cli.metricas_post(lote, plazo=PLAZO_METRICAS_S)
        except UP.ErrorUploadPost as fallo:
            if fallo.codigo == 429:
                errores.append("Upload-Post pide esperar unos minutos (demasiadas consultas)")
                break
            consultados += 1
            errores.append(str(fallo)[:200])
            # la consulta entera fallo: se apunta el motivo, pero NO la hora,
            # para que el respiro no impida volver a intentarlo
            _apuntar_metricas(raiz, envios, None, error=str(fallo)[:300])
            if fallo.sin_respuesta:
                break                       # Upload-Post no contesta: no seguir
            continue
        consultados += 1
        actualizados += _apuntar_metricas(raiz, envios, cifras)
    return {"consultados": consultados, "actualizados": actualizados,
            "pendientes": max(0, len(candidatos) - consultados), "errores": errores[:5]}


def _apuntar_metricas(raiz, envios, cifras, error=""):
    """Guarda en cada envio lo que trae `cifras` (o solo el error). -> cuantos"""
    al = _iso_lima()
    por_pid = {}
    for pid, e in envios:
        por_pid.setdefault(pid, set()).add(e["id"])
    hechos = 0
    for pid, ids in por_pid.items():
        with _lock(pid):
            datos = _leer_video(raiz, pid)
            for e in datos["envios"]:
                if e.get("id") not in ids:
                    continue
                viejas = e.get("metricas") or {}
                if cifras is None:
                    e["metricas"] = dict(viejas, error=error)
                    continue
                propias = cifras.get(e["red"])
                if propias is None:
                    e["metricas"] = dict(viejas, al=al,
                                         error="Upload-Post no trae cifras de esta red")
                    continue
                nuevas = {k: propias.get(k) for k in METRICAS + ("alcance",) + RETENCION}
                # una consulta sin cifras (TikTok las completa en horas) no
                # borra las que ya se sabian
                for k in nuevas:
                    if nuevas[k] is None and viejas.get(k) is not None:
                        nuevas[k] = viejas[k]
                nuevas.update(al=al, error=propias.get("error") or "")
                # el reloj de la lectura guardada es suyo: una lectura en vivo no
                # lo borra (sin el, una guardada MAS VIEJA volvia a pisar la
                # retencion de YouTube)
                for k in ("guardada_al", "guardada"):
                    if k in viejas:
                        nuevas[k] = viejas[k]
                e["metricas"] = nuevas
                if propias.get("url") and not e.get("url"):
                    e["url"] = propias["url"]
                if propias.get("post_id"):
                    e["post_id"] = propias["post_id"]
                hechos += 1
            _escribir(_ruta_video(raiz, pid), datos)
    return hechos


# LA LECTURA GUARDADA (publicar-redes-2, 17-10-2026). Upload-Post guarda lo
# ultimo que leyo EN VIVO de cada post y lo devuelve por otra ruta que NO gasta
# del limite de consultas. No sustituye a la lectura en vivo (solo trae posts que
# ya se leyeron alguna vez), pero es el unico sitio donde YouTube da su
# retencion, y recoge lo leido desde la web de Upload-Post. Se pide tras cada
# «Actualizar», una vez por perfil, y solo pisa lo que sabemos si es MAS NUEVO.

_LOCK_GUARDADAS = threading.Lock()


def _momento_utc(texto):
    """Un `captured_at` de Upload-Post (ISO con zona, o sin ella = UTC)."""
    texto = str(texto or "").strip().replace("Z", "+00:00")
    if not texto:
        return None
    try:
        momento = dt.datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=dt.timezone.utc)
    return momento.astimezone(_zona()).replace(microsecond=0)


def leer_guardadas(raiz, pids, dias=90, paginas=None, plazo=None, hasta_momento=None):
    """Completa las cifras de lo publicado con la lectura guardada de Upload-Post.
    -> {"leidos", "actualizados", "errores", "ocupado"?}. No gasta consultas del
    limite. `hasta_momento` (time.time()): no se empieza otro perfil despues.

    Sin `until` a proposito: Upload-Post filtra por el dia de captura (en UTC) y
    desde las 19:00 de Lima ya es mañana alli; con «hoy en Lima» se quedaba fuera
    justo la lectura que se acababa de hacer."""
    if not _LOCK_GUARDADAS.acquire(blocking=False):
        return {"leidos": 0, "actualizados": 0, "errores": [], "ocupado": True}
    try:
        por_perfil = {}
        for pid in pids:
            for e in _leer_video(raiz, pid)["envios"]:
                if e.get("estado") == "publicado" and e.get("lote") and e.get("perfil") \
                        and (e.get("post_id") or e.get("url")):
                    por_perfil.setdefault(e["perfil"], []).append((pid, e))
        if not por_perfil:
            return {"leidos": 0, "actualizados": 0, "errores": []}
        cli = cliente(raiz)
        hoy = ahora_lima()
        # un dia de mas: el filtro de Upload-Post va por el dia en UTC
        desde = (hoy - dt.timedelta(days=dias + 1)).strftime("%Y-%m-%d")
        leidos = actualizados = 0
        errores = []
        for perfil, envios in por_perfil.items():
            if hasta_momento is not None and time.time() >= hasta_momento:
                errores.append("lectura guardada: no dio tiempo a todos los perfiles; "
                               "vuelve a pulsar «Actualizar»")
                break
            try:
                extra = {k: v for k, v in (("paginas", paginas), ("plazo", plazo)) if v}
                r = cli.metricas_guardadas(perfil, desde=desde, **extra)
            except UP.ErrorUploadPost as fallo:
                errores.append(f"lectura guardada: {str(fallo)[:200]}")
                if fallo.sin_respuesta:
                    break
                continue
            posts = r.get("posts") or []
            leidos += len(posts)
            # por (red, id del post) y, si no hay id, por (red, enlace); si un
            # post sale dos veces, se queda la lectura mas nueva
            indice = {}
            nunca = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
            for post in posts:
                for clave_post in ((post["red"], "id", post.get("post_id")),
                                   (post["red"], "url", post.get("url"))):
                    if not clave_post[2]:
                        continue
                    viejo = indice.get(clave_post)
                    if viejo is None or (_momento_utc(post.get("al")) or nunca) > \
                            (_momento_utc(viejo.get("al")) or nunca):
                        indice[clave_post] = post
            actualizados += _apuntar_guardadas(raiz, envios, indice)
        return {"leidos": leidos, "actualizados": actualizados, "errores": errores[:5]}
    finally:
        _LOCK_GUARDADAS.release()


def _apuntar_guardadas(raiz, envios, indice):
    por_pid = {}
    for pid, e in envios:
        por_pid.setdefault(pid, set()).add(e["id"])
    hechos = 0
    for pid, ids in por_pid.items():
        with _lock(pid):
            datos = _leer_video(raiz, pid)
            cambio = False
            for e in datos["envios"]:
                if e.get("id") not in ids:
                    continue
                post = (indice.get((e["red"], "id", e.get("post_id"))) if e.get("post_id") else None) \
                    or (indice.get((e["red"], "url", e.get("url"))) if e.get("url") else None)
                if not post:
                    continue
                viejas = e.get("metricas") or {}
                cuando = _momento_utc(post.get("al"))
                if cuando is None:
                    continue
                # DOS RELOJES. Las cifras (vistas, me gusta…) tambien llegan en
                # vivo: lo guardado solo las pisa si es MAS NUEVO que nuestra
                # ultima lectura (`al`). La retencion de YouTube solo llega por
                # aqui, y Upload-Post sella su lectura un momento ANTES de que
                # nosotros apuntemos la nuestra: comparada con `al` nunca seria
                # «mas nueva» y se quedaria para siempre en la primera cifra. Lleva
                # su propio reloj (`guardada_al`): manda la lectura guardada mas
                # reciente.
                sabido = _leer_momento(viejas.get("al"))
                cifras_nuevas = sabido is None or cuando > sabido
                guardada = _leer_momento(viejas.get("guardada_al"))
                retencion_nueva = guardada is None or cuando >= guardada
                nuevas = dict(viejas)
                tocado = False
                for k in METRICAS + ("alcance",) + RETENCION:
                    valor = post.get(k)
                    if valor is None:
                        continue
                    manda = retencion_nueva if k in RETENCION else cifras_nuevas
                    # lo que no sabiamos se pone, aunque la lectura sea mas vieja
                    if (manda or viejas.get(k) is None) and nuevas.get(k) != valor:
                        nuevas[k] = valor
                        tocado = True
                if retencion_nueva and nuevas.get("guardada_al") != _iso_lima(cuando):
                    nuevas["guardada_al"] = _iso_lima(cuando)
                if not tocado:
                    if nuevas != viejas:
                        e["metricas"] = nuevas      # solo el reloj: sin contarlo
                        cambio = True
                    continue
                if cifras_nuevas:
                    nuevas["al"] = _iso_lima(cuando)
                    nuevas["error"] = ""
                nuevas["guardada"] = True
                e["metricas"] = nuevas
                if post.get("post_id") and not e.get("post_id"):
                    e["post_id"] = post["post_id"]
                cambio = True
                hechos += 1
            if cambio:
                _escribir(_ruta_video(raiz, pid), datos)
    return hechos


#: Tras la lectura en vivo, la guardada se pide solo si queda tiempo de sobra
#: en la peticion (detras del proxy se corta a los 60 s), con plazo corto y de
#: los ultimos dias: lo recien leido en vivo esta ahi con fecha de hoy.
MARGEN_GUARDADAS_S = 15
PLAZO_GUARDADAS_S = 12
#: Los seguidores (ruta del proyecto) se piden solo si no han pasado mas de
#: estos segundos: su consulta puede tardar 30 y el proxy corta a los 60.
TOPE_SEGUIDORES_S = 20


def medir(raiz, pids, forzar=False):
    """«Actualizar» entero: la lectura en vivo (con su limite) y, despues, la
    guardada (sin limite) para la retencion de YouTube y lo leido en otro sitio.
    -> lo de `actualizar_metricas` mas {"guardadas": n}"""
    arranque = time.time()
    r = actualizar_metricas(raiz, pids, forzar=forzar)
    r["guardadas"] = 0
    r["arranque"] = arranque
    if r.get("ocupado"):
        return r
    if time.time() - arranque > TOPE_VUELTA_S - MARGEN_GUARDADAS_S:
        return r
    # el tope cuenta tambien la ultima consulta: se empieza un perfil solo si
    # da tiempo a esperarlo entero
    g = leer_guardadas(raiz, pids, dias=7, paginas=1, plazo=PLAZO_GUARDADAS_S,
                       hasta_momento=arranque + TOPE_VUELTA_S - PLAZO_GUARDADAS_S)
    r["guardadas"] = g["actualizados"]
    r["errores"] = (r.get("errores") or []) + g["errores"]
    return r


def actualizar_seguidores(raiz, cid):
    """Seguidores, alcance y vistas de las cuentas del perfil del proyecto. Lo
    que una red no de esta vez no borra lo ultimo que se supo de ella."""
    ajustes = ajustes_de(raiz, cid)
    perfil = ajustes.get("perfil")
    if not perfil:
        raise ErrorPublicar("este proyecto todavía no tiene perfil de Upload-Post", 409)
    cuentas = ajustes.get("cuentas") or {}
    if not ajustes.get("cuentas_vistas"):
        raise ErrorPublicar("pulsa antes «Ver cuentas» en Cuentas y ajustes: así se sabe "
                            "qué cuentas tiene conectadas", 409)
    conectadas = [r for r in REDES if cuentas.get(r)]
    pagina = ajustes.get("facebook_pagina") or None
    if "facebook" in conectadas and not pagina:
        conectadas.remove("facebook")      # Upload-Post pide la pagina para Facebook
    if not conectadas:
        return ajustes
    cifras = _por_upload_post(cliente(raiz).analiticas_perfil, perfil, conectadas,
                              pagina_facebook=pagina)
    with _lock("ajustes"):
        ahora = ajustes_de(raiz, cid)
        if ahora.get("perfil") != perfil:
            return ahora                    # cambio el perfil mientras: no son suyas
        juntas = dict(ahora.get("seguidores") or {})
        for red, nuevo in cifras.items():
            viejo = juntas.get(red) or {}
            mezcla = dict(nuevo)
            for k in ("seguidores", "alcance", "vistas"):
                if mezcla.get(k) is None and viejo.get(k) is not None:
                    mezcla[k] = viejo[k]
            juntas[red] = mezcla
        return guardar_ajustes(raiz, cid, {}, internos={"seguidores": juntas,
                                                         "seguidores_al": _iso_lima()})


def _suma(destino, metricas):
    for k in METRICAS:
        v = (metricas or {}).get(k)
        if isinstance(v, (int, float)):
            destino[k] = (destino.get(k) or 0) + int(v)
    vistas = (metricas or {}).get("vistas")
    peso = float(vistas) if isinstance(vistas, (int, float)) and vistas > 0 else 0.0
    for k in RETENCION:
        v = (metricas or {}).get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            destino[f"_n_{k}"] = (destino.get(f"_n_{k}") or 0) + 1
            destino[f"_s_{k}"] = (destino.get(f"_s_{k}") or 0) + float(v)
            # la media ponderada por vistas; sin vistas, la media simple
            destino[f"_ps_{k}"] = (destino.get(f"_ps_{k}") or 0) + float(v) * peso
            destino[f"_p_{k}"] = (destino.get(f"_p_{k}") or 0) + peso
            if peso:
                destino[f"_pn_{k}"] = (destino.get(f"_pn_{k}") or 0) + 1


def _medias(destino):
    """Cierra una suma: la retencion pasa a ser la media de los posts que la
    dan (no de todos: los que no la dan no cuentan como cero)."""
    for k in RETENCION:
        n = destino.pop(f"_n_{k}", 0)
        suma = destino.pop(f"_s_{k}", 0)
        suma_pesada = destino.pop(f"_ps_{k}", 0)
        pesos = destino.pop(f"_p_{k}", 0)
        con_peso = destino.pop(f"_pn_{k}", 0)
        valor = (suma_pesada / pesos) if pesos else (suma / n if n else None)
        destino[k] = round(valor, 1 if k == "tiempo_medio_s" else 4) if valor is not None else None
        # cuantos posts entran DE VERDAD en esa media: con vistas, solo los que
        # pesan; sin ninguna vista, todos
        destino[f"{k}_posts"] = con_peso if pesos else n
    return destino


def _de_proyecto(videos, cid):
    """Los videos de un proyecto (cid None: todos los que se pueden ver)."""
    if cid is None:
        return list(videos)
    return [v for v in videos if (v.get("cliente") or SIN_PROYECTO) == (cid or SIN_PROYECTO)]


def _publicados(raiz, videos, desde, hasta=None):
    """[(video, envio)] de lo publicado (tambien a mano) entre `desde` y
    `hasta` (la hora de publicar), de los videos dados."""
    con_ficha = set(_videos_con_ficha(raiz))
    salida = []
    for v in videos:
        if v["pid"] not in con_ficha:
            continue
        for e in _leer_video(raiz, v["pid"])["envios"]:
            if e.get("estado") not in ("publicado", "a_mano"):
                continue
            momento = _leer_momento(e.get("cuando"))
            if momento is None or momento < desde or (hasta is not None and momento >= hasta):
                continue
            salida.append((v, e))
    return salida


def resultados(raiz, videos, cid, dias=30):
    """El resumen de un proyecto: lo publicado en los ultimos `dias` dias, con
    las cifras que se sepan. `videos` son los que quien pregunta puede ver."""
    try:
        dias = max(1, min(int(dias or 30), 365))
    except (TypeError, ValueError):
        dias = 30
    desde = ahora_lima() - dt.timedelta(days=dias)
    por_red = {r: {"posts": 0} for r in REDES}
    total = {"posts": 0}
    filas, sin_cifras, mirado = {}, 0, None
    for v, e in _publicados(raiz, _de_proyecto(videos, cid), desde):
        m = e.get("metricas") or {}
        por_red[e["red"]]["posts"] += 1
        total["posts"] += 1
        _suma(por_red[e["red"]], m)
        _suma(total, m)
        fila = filas.setdefault(v["pid"], {"pid": v["pid"], "nombre": v.get("nombre") or v["pid"],
                                           "redes": {}, "_suma": {}})
        _suma(fila["_suma"], m)
        # dos envios a la misma red (un reenvio, uno a mano) se SUMAN aqui
        # igual que en el total: el detalle cuadra con la suma
        propia = fila["redes"].setdefault(e["red"], {"url": ""})
        _suma(propia, m)
        if e.get("url"):
            propia["url"] = e["url"]
        if not any(isinstance(m.get(k), (int, float)) for k in METRICAS):
            sin_cifras += 1
        al = _leer_momento(m.get("al"))
        if al and (mirado is None or al > mirado):
            mirado = al
    lista = []
    for fila in filas.values():
        suma = _medias(fila.pop("_suma"))
        for propia in fila["redes"].values():
            _medias(propia)
        lista.append(dict(fila, **{k: suma.get(k) for k in METRICAS + RETENCION}))
    lista.sort(key=lambda f: (f.get("vistas") or 0), reverse=True)
    for r in por_red.values():
        _medias(r)
    _medias(total)
    ajustes = ajustes_de(raiz, cid)
    return {"proyecto": cid or SIN_PROYECTO, "dias": dias, "desde": desde.strftime("%Y-%m-%d"),
            "total": total, "por_red": por_red, "videos": lista[:50],
            "sin_cifras": sin_cifras, "mirado": mirado.strftime("%Y-%m-%dT%H:%M") if mirado else "",
            "seguidores": ajustes.get("seguidores") or {},
            "seguidores_al": ajustes.get("seguidores_al") or "",
            "perfil": ajustes.get("perfil") or "", "clave": estado_clave()}


# ---------------------------------------------------- semana, mes y lo mejor
#
# Todo esto se calcula con lo que YA se sabe (las cifras guardadas en cada
# envio): no pregunta a nadie y no gasta consultas. Lo de «esta semana» es lo
# PUBLICADO esta semana, con sus cifras de hoy; no las vistas ganadas en la semana
# (Upload-Post no da el historico dia a dia de cada post).

def _totales(pares):
    total = {"posts": 0}
    for _v, e in pares:
        total["posts"] += 1
        _suma(total, e.get("metricas") or {})
    return _medias(total)


def _inicio_semana(momento):
    return (momento - dt.timedelta(days=momento.weekday())).replace(hour=0, minute=0, second=0)


def _inicio_mes(momento):
    return momento.replace(day=1, hour=0, minute=0, second=0)


def periodos(raiz, videos, cid, ahora=None):
    """Esta semana (desde el lunes) y este mes (desde el dia 1), frente al MISMO
    TRAMO del periodo anterior, en hora de Lima: un jueves a mediodia se compara
    con la semana pasada hasta el jueves a mediodia, no con la semana entera
    (comparado con la entera, cada lunes salia «−80 %»). -> {"semana", "mes"}"""
    ahora = ahora or ahora_lima()
    propios = _de_proyecto(videos, cid)
    salida = {}
    semana = _inicio_semana(ahora)
    mes = _inicio_mes(ahora)
    mes_antes = _inicio_mes(mes - dt.timedelta(days=1))
    # el mismo dia del mes pasado (el 31 de un mes de 30 dias se queda en su ultimo)
    dias_mes_antes = (mes - mes_antes).days
    tope_mes = mes_antes + min(ahora - mes, dt.timedelta(days=dias_mes_antes))
    for nombre, desde, antes, tope in (
            ("semana", semana, semana - dt.timedelta(days=7), ahora - dt.timedelta(days=7)),
            ("mes", mes, mes_antes, tope_mes)):
        pares = _publicados(raiz, propios, antes)
        este = [(v, e) for v, e in pares if _leer_momento(e.get("cuando")) >= desde]
        previo = [(v, e) for v, e in pares if _leer_momento(e.get("cuando")) < min(desde, tope)]
        salida[nombre] = {"desde": desde.strftime("%Y-%m-%d"),
                          "anterior_desde": antes.strftime("%Y-%m-%d"),
                          "anterior_hasta": _iso_lima(min(desde, tope)),
                          "actual": _totales(este), "anterior": _totales(previo)}
    return salida


#: Por que se puede ordenar «lo que funciono». `interaccion` es (me gusta +
#: comentarios + compartidos + guardados) / vistas; con pocas vistas no dice nada,
#: asi que un post entra en esa lista (y en la de retencion) solo con
#: MIN_VISTAS_PROPORCION vistas o mas.
ORDENES = ("vistas", "interaccion", "vista_entera", "media_vista")
MIN_VISTAS_PROPORCION = 50
_DIAS_SEMANA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _interaccion(m):
    vistas = m.get("vistas")
    if not isinstance(vistas, (int, float)) or vistas <= 0:
        return None
    partes = [m.get(k) for k in ("me_gusta", "comentarios", "compartidos", "guardados")]
    partes = [p for p in partes if isinstance(p, (int, float))]
    if not partes:
        return None
    return round(sum(partes) / vistas, 4)


def lo_que_funciono(raiz, videos, cid=None, dias=30, red=None, por="vistas", cuantos=10):
    """EL PUNTO DE LECTURA de los resultados: los posts que mejor fueron, con
    lo que hace falta para repetirlos (red, dia y hora de Lima, textos, cifras).
    Lo usan Publicar → Resultados, la linea de Inicio y, mas adelante, la
    Parrilla («Desde mis resultados») y el piloto. Solo lee lo guardado.

    `cid` None: todos los videos dados (ya filtrados por lo que se puede ver).
    -> {"por", "dias", "red", "posts": [{pid, nombre, cliente, red, cuando, dia,
        hora, url, titulo, descripcion, metricas, interaccion}]}"""
    try:
        dias = max(1, min(int(dias or 30), 365))
    except (TypeError, ValueError):
        dias = 30
    try:
        cuantos = max(1, min(int(cuantos or 10), 50))
    except (TypeError, ValueError):
        cuantos = 10
    por = por if por in ORDENES else "vistas"
    red = red if red in REDES else None
    desde = ahora_lima() - dt.timedelta(days=dias)
    filas = []
    textos_de = {}
    for v, e in _publicados(raiz, _de_proyecto(videos, cid), desde):
        if red and e["red"] != red:
            continue
        m = e.get("metricas") or {}
        vistas = m.get("vistas")
        if not isinstance(vistas, (int, float)):
            continue
        interaccion = _interaccion(m)
        if por != "vistas" and vistas < MIN_VISTAS_PROPORCION:
            continue
        valor = vistas if por == "vistas" else (interaccion if por == "interaccion"
                                               else m.get(por))
        if not isinstance(valor, (int, float)):
            continue
        if v["pid"] not in textos_de:
            textos_de[v["pid"]] = _leer_video(raiz, v["pid"])["textos"]
        texto = textos_de[v["pid"]].get(e["red"]) or {}
        momento = _leer_momento(e.get("cuando"))
        filas.append((valor, {
            "pid": v["pid"], "nombre": v.get("nombre") or v["pid"],
            "cliente": v.get("cliente") or "", "red": e["red"],
            "cuando": _iso_lima(momento), "dia": _DIAS_SEMANA[momento.weekday()],
            "hora": momento.strftime("%H:%M"), "url": e.get("url") or "",
            "titulo": str(texto.get("titulo") or "")[:200],
            "descripcion": str(texto.get("descripcion") or "")[:600],
            "metricas": {k: m.get(k) for k in METRICAS + RETENCION},
            "interaccion": interaccion, "mirado": m.get("al") or ""}))
    filas.sort(key=lambda x: x[0], reverse=True)
    return {"por": por, "dias": dias, "red": red or "", "desde": desde.strftime("%Y-%m-%d"),
            "minimo_vistas": MIN_VISTAS_PROPORCION if por != "vistas" else 0,
            "posts": [f for _v, f in filas[:cuantos]]}


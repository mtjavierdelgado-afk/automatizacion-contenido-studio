"""La APROBACIÓN DEL CLIENTE POR ENLACE (rama `publicar-redes-3`, 25-11-2026;
plan aprobado por el dueño: `estado/plan_aprobacion_cliente_2026-11-11.md`).

El dueño pide en la ficha de Publicar un ENLACE PRIVADO para un vídeo y se lo
manda al cliente (WhatsApp, correo). El cliente, sin entrar a nada, ve el
vídeo, los textos de cada red y la fecha prevista, y pulsa «Aprobar» o «Pedir
cambios» con un comentario. Mientras el cliente no apruebe, ese vídeo NO sale:
`publicar.enviar` lo para (salvo «espera tu OK», que tampoco sale solo).

LO PÚBLICO ES EL ENLACE, Y NADA MÁS:
- el token son 32 bytes aleatorios (`secrets.token_urlsafe`); en disco solo
  se guarda su huella SHA-256 (quien lea el fichero no puede abrir enlaces);
- un enlace es de UN vídeo, caduca (7 días por defecto) y se puede anular;
  pedir otro para el mismo vídeo anula los anteriores;
- se busca por la huella y se compara en tiempo constante;
- un token caducado, anulado, mal formado o que no existe dan lo mismo (None):
  quien pruebe enlaces no aprende nada de la respuesta.

Datos: `<proyectos>/_sistema/publicar/aprobaciones.json`, fuera del código.
Nada de params ni firmas de vídeo (regla 1): esto no toca ningún proyecto.
"""
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import threading

try:
    from nucleo.proyecto import escribir_json, leer_json
except ImportError:                                         # pragma: no cover
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from nucleo.proyecto import escribir_json, leer_json

#: Días que vale un enlace si no se elige otra cosa, y los límites
DIAS_DEFECTO = 7
DIAS_MAXIMO = 30
#: Un comentario del cliente, como mucho
TOPE_COMENTARIO = 2000
#: Respuestas guardadas por enlace (el cliente puede cambiar de opinión)
TOPE_HISTORIAL = 20
#: Lo que deja un token bien formado (token_urlsafe(32) son 43 caracteres)
_FORMA_TOKEN = re.compile(r"^[A-Za-z0-9_-]{40,64}$")
DECISIONES = ("aprobado", "cambios")

_LOCK = threading.RLock()


class ErrorAprobacion(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = int(codigo)


def _zona():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Lima")
    except Exception:                                       # noqa: BLE001
        return dt.timezone(dt.timedelta(hours=-5))


def _ahora():
    return dt.datetime.now(_zona()).replace(microsecond=0)


def _iso(momento):
    return momento.strftime("%Y-%m-%dT%H:%M:%S")


def _leer_momento(texto):
    try:
        m = dt.datetime.fromisoformat(str(texto or ""))
    except ValueError:
        return None
    return m.replace(tzinfo=_zona()) if m.tzinfo is None else m


def _ruta(raiz):
    return os.path.join(raiz, "_sistema", "publicar", "aprobaciones.json")


def _leer(raiz):
    datos = leer_json(_ruta(raiz), {}) or {}
    datos = datos if isinstance(datos, dict) else {}
    if not isinstance(datos.get("enlaces"), dict):
        datos["enlaces"] = {}
    return datos


def _escribir(raiz, datos):
    os.makedirs(os.path.dirname(_ruta(raiz)), exist_ok=True)
    escribir_json(_ruta(raiz), datos)


def huella_token(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def redes_que_ve(datos_publicar, por_red, orden):
    """Las redes cuyo texto ve el cliente: las elegidas en la ficha que tienen
    texto (o, sin elegir, todas las que lo tienen), en el orden de la pantalla.
    `por_red` es `publicar.textos_para_el_cliente`."""
    elegidas = (datos_publicar or {}).get("redes") or []
    return [r for r in orden if r in elegidas and r in por_red] or \
        [r for r in orden if r in por_red]


def _sello(*partes):
    bruto = json.dumps(list(partes), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:16]


def huellas_por_red(mp4_huella, por_red):
    """{red: huella} del montaje MÁS el texto que sale en ESA red. Lo aprobado
    se guarda así, red a red: cambiar el vídeo o el texto de una red le quita
    el «sí» a esa red; quitar una red no bloquea las demás. {} sin MP4."""
    if not mp4_huella:
        return {}
    return {red: _sello(str(mp4_huella), red, contenido) for red, contenido in (por_red or {}).items()}


def huella_de_lo_que_ve(huellas, redes):
    """Una sola huella de todo lo que ve en la página (para «recarga, que ha
    cambiado» al contestar). "" sin MP4."""
    if not huellas:
        return ""
    return _sello([[r, huellas.get(r, "")] for r in redes])


#: Un enlace caducado o anulado se olvida pasado este tiempo (al pedir otro)
DIAS_HASTA_OLVIDAR = 90


def _olvidar_viejos(datos, ahora):
    limite = ahora - dt.timedelta(days=DIAS_HASTA_OLVIDAR)
    for clave in list(datos["enlaces"]):
        registro = datos["enlaces"][clave]
        if _vigente(registro, ahora):
            continue
        caduca = _leer_momento(registro.get("caduca")) or ahora
        respondido = _leer_momento(registro.get("respondido_al"))
        ultimo = max([m for m in (caduca, respondido) if m] or [ahora])
        if ultimo < limite:
            del datos["enlaces"][clave]


def _vigente(registro, ahora=None):
    if not isinstance(registro, dict) or registro.get("anulado"):
        return False
    caduca = _leer_momento(registro.get("caduca"))
    return bool(caduca and (ahora or _ahora()) < caduca)


def _publico(registro):
    """Lo que la pantalla del dueño ve de un enlace (nunca la huella)."""
    if not registro:
        return None
    return {k: registro.get(k) for k in (
        "id", "pid", "creado", "caduca", "anulado", "estado", "comentario",
        "respondido_al", "visto", "visto_al", "nota", "huella", "huella_aprobada")} | {"vigente": _vigente(registro)}


# ------------------------------------------------------------- el dueño

def crear(raiz, pid, dias=None, nota="", huella=""):
    """Un enlace nuevo para este vídeo (anula los anteriores del mismo vídeo).
    -> {"token": … (solo esta vez), "enlace": {…}}"""
    try:
        dias = int(dias) if dias not in (None, "") else DIAS_DEFECTO
    except (TypeError, ValueError):
        raise ErrorAprobacion("los días van en número, de 1 a 30") from None
    if not 1 <= dias <= DIAS_MAXIMO:
        raise ErrorAprobacion("un enlace dura de 1 a 30 días")
    token = secrets.token_urlsafe(32)
    ahora = _ahora()
    registro = {
        "id": secrets.token_hex(6), "pid": str(pid), "creado": _iso(ahora),
        "caduca": _iso(ahora + dt.timedelta(days=dias)), "anulado": False,
        "estado": "pendiente", "comentario": "", "respondido_al": "",
        "visto": False, "visto_al": "", "nota": str(nota or "")[:300], "historial": [],
        # el montaje que se le pide aprobar: si se vuelve a montar, lo aprobado
        # deja de valer (`espera_al_cliente` dice «cambiado»)
        "huella": str(huella or ""), "huella_aprobada": "",
    }
    with _LOCK:
        datos = _leer(raiz)
        for otro in datos["enlaces"].values():
            if otro.get("pid") == str(pid) and not otro.get("anulado"):
                otro["anulado"] = True
                otro["anulado_por"] = "otro enlace"
        datos["enlaces"][huella_token(token)] = registro
        _olvidar_viejos(datos, ahora)
        _escribir(raiz, datos)
    return {"token": token, "enlace": _publico(registro)}


def anular(raiz, pid, ident):
    """Anula un enlace de este vídeo (el cliente deja de poder abrirlo y el
    vídeo deja de esperarle). -> el enlace"""
    with _LOCK:
        datos = _leer(raiz)
        for registro in datos["enlaces"].values():
            if registro.get("pid") == str(pid) and registro.get("id") == str(ident):
                registro["anulado"] = True
                registro["anulado_por"] = "dueño"
                _escribir(raiz, datos)
                return _publico(registro)
    raise ErrorAprobacion("ese enlace no existe", 404)


def de_video(raiz, pid):
    """El último enlace del vídeo (vigente o no), para la ficha. None si nunca."""
    datos = _leer(raiz)
    propios = [r for r in datos["enlaces"].values() if r.get("pid") == str(pid)]
    if not propios:
        return None
    propios.sort(key=lambda r: str(r.get("creado") or ""))
    return _publico(propios[-1])


def espera_al_cliente(raiz, pid, huellas=None, redes=()):
    """¿Espera este vídeo al cliente para salir en `redes`? Mientras sí, no
    sale (`publicar.enviar`). `huellas` es `huellas_por_red` de AHORA.
    -> "pendiente" (aún no contesta), "cambios" (pidió cambios), "cambiado"
    (lo aprobó, pero el vídeo o el texto de alguna de esas redes cambió, o esa
    red no la vio) o "" (puede salir). Solo cuenta el enlace VIGENTE."""
    ahora = _ahora()
    huellas = huellas or {}
    for registro in _leer(raiz)["enlaces"].values():
        if registro.get("pid") != str(pid) or not _vigente(registro, ahora):
            continue
        if registro.get("estado") != "aprobado":
            return registro.get("estado") or "pendiente"
        aprobadas = registro.get("huellas_aprobadas") or {}
        for red in redes:
            if not aprobadas.get(red) or aprobadas.get(red) != huellas.get(red):
                return "cambiado"
    return ""


def respuestas(raiz, pids=None):
    """Los vídeos con respuesta del cliente (para la Cola): el último enlace
    de cada uno que el cliente haya contestado. -> [{…}]"""
    ultimos = {}
    for registro in _leer(raiz)["enlaces"].values():
        if pids is not None and registro.get("pid") not in pids:
            continue
        previo = ultimos.get(registro.get("pid"))
        if previo is None or str(registro.get("creado") or "") > str(previo.get("creado") or ""):
            ultimos[registro.get("pid")] = registro
    salida = [_publico(r) for r in ultimos.values() if r.get("respondido_al")]
    salida.sort(key=lambda r: str(r.get("respondido_al") or ""), reverse=True)
    return salida


# ------------------------------------------------------------ el cliente

def de_token(raiz, token):
    """El enlace de este token si vale (bien formado, existe, no anulado, no
    caducado). None en cualquier otro caso, sin decir cuál."""
    token = str(token or "")
    if not _FORMA_TOKEN.match(token):
        return None
    buscada = huella_token(token)
    for clave, registro in _leer(raiz)["enlaces"].items():
        if hmac.compare_digest(clave, buscada):
            return dict(registro) if _vigente(registro) else None
    return None


def marcar_visto(raiz, token):
    """La primera vez que el cliente abre el enlace (la ficha lo dice)."""
    buscada = huella_token(token)
    with _LOCK:
        datos = _leer(raiz)
        registro = datos["enlaces"].get(buscada)
        if registro and _vigente(registro) and not registro.get("visto"):
            registro["visto"] = True
            registro["visto_al"] = _iso(_ahora())
            _escribir(raiz, datos)


def normalizar_decision(decision):
    return str(decision or "").strip().lower()


def responder(raiz, token, decision, comentario="", huella="", huellas=None):
    """«aprobado» o «cambios», con un comentario (obligatorio si pide
    cambios). Puede cambiar de opinión mientras el enlace valga."""
    decision = normalizar_decision(decision)
    if decision not in DECISIONES:
        raise ErrorAprobacion("elige «Aprobar» o «Pedir cambios»")
    comentario = str(comentario or "").strip()[:TOPE_COMENTARIO]
    if decision == "cambios" and not comentario:
        raise ErrorAprobacion("cuéntanos qué cambiarías")
    buscada = huella_token(token)
    with _LOCK:
        datos = _leer(raiz)
        registro = datos["enlaces"].get(buscada)
        if not _FORMA_TOKEN.match(str(token or "")) or not _vigente(registro):
            raise ErrorAprobacion("este enlace ya no vale", 404)
        if decision == "aprobado" and not huella:
            raise ErrorAprobacion("todavía no hay vídeo que aprobar: vuelve a mirarlo más tarde", 409)
        ahora = _iso(_ahora())
        registro["estado"] = decision
        registro["comentario"] = comentario
        registro["respondido_al"] = ahora
        # lo que vio al contestar: aprobar ESTE montaje, no el que venga
        registro["huella_aprobada"] = str(huella or "") if decision == "aprobado" else ""
        # y red a red, lo que vio de cada una (lo que mira `espera_al_cliente`)
        registro["huellas_aprobadas"] = dict(huellas or {}) if decision == "aprobado" else {}
        historial = registro.setdefault("historial", [])
        historial.append({"estado": decision, "comentario": comentario, "al": ahora})
        del historial[:-TOPE_HISTORIAL]
        _escribir(raiz, datos)
        return {"estado": decision, "comentario": comentario, "respondido_al": ahora}

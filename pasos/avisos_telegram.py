"""AVISOS AL MÓVIL POR TELEGRAM (rama `piloto-2`, 24-11-2026).

El piloto automático avisa al móvil del dueño con un bot de Telegram: un
mensaje corto y un enlace a la página del vídeo (`aprobar.html`). Gratis.

    estado()                       lo que enseña Configuración (sin el token)
    poner_token(token)             lo comprueba con getMe y lo guarda
    buscar_chats()                 quién ha escrito «/start» al bot (getUpdates)
    confirmar_chat(id, nombre, base_url)
    desconectar()
    enviar(texto, silencioso)      -> id del mensaje
    editar(mensaje, texto)         -> bool

SIN BOTONES DENTRO DE TELEGRAM y sin webhook: nada entra al servidor desde
Telegram. Todo se decide en la página, detrás del mismo login que el Studio.

EL TOKEN ES UN SECRETO: vive en `<secretos>/telegram.json` (la misma carpeta
que `claves.json`, que el asistente tiene vetada), nunca en el repo ni en la
foto del asistente. Como `cuentas_ajenas.py` con Meta, va en su propio fichero
para no tocar `claves.json`.

Las llamadas tienen un plazo corto (8 s). Si Telegram falla, el vigía no
insiste en cada vuelta: espera cada vez más (hasta 10 min) antes de volver a
intentarlo (`_PAUSA`). `ESTUDIO_TELEGRAM_API` apunta a un Telegram falso en las
pruebas.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

PLAZO_S = 8
_LOCK = threading.RLock()
_PAUSA = {"hasta": 0.0, "fallos": 0}


class ErrorTelegram(RuntimeError):
    def __init__(self, mensaje, codigo=502):
        super().__init__(mensaje)
        self.codigo = int(codigo)


def _carpeta():
    return os.environ.get("ESTUDIO_SECRETOS") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secretos")


def _ruta():
    return os.path.join(_carpeta(), "telegram.json")


def _api():
    return (os.environ.get("ESTUDIO_TELEGRAM_API") or "https://api.telegram.org").rstrip("/")


def _leer():
    try:
        with open(_ruta(), encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar(datos):
    os.makedirs(_carpeta(), exist_ok=True)
    tmp = _ruta() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, _ruta())


def _llamar(token, metodo, campos=None, plazo=PLAZO_S):
    """Una llamada a la API de bots. -> result. Lanza ErrorTelegram."""
    if not token:
        raise ErrorTelegram("Telegram no está conectado", 409)
    url = f"{_api()}/bot{token}/{metodo}"
    cuerpo = json.dumps(campos or {}).encode("utf-8")
    peticion = urllib.request.Request(url, data=cuerpo,
                                      headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=plazo) as r:
            datos = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as fallo:
        try:
            datos = json.loads(fallo.read().decode("utf-8") or "{}")
        except (ValueError, OSError):
            datos = {}
        texto = str(datos.get("description") or fallo.reason or "")
        if fallo.code == 401:
            raise ErrorTelegram("Telegram no reconoce ese token: cópialo otra vez de @BotFather",
                                400) from None
        error = ErrorTelegram(f"Telegram dijo: {texto or fallo.code}", 502)
        error.http = int(fallo.code or 0)
        raise error from None
    except (urllib.error.URLError, OSError, ValueError) as fallo:
        raise ErrorTelegram(f"no se pudo hablar con Telegram ({fallo})", 502) from None
    if not datos.get("ok"):
        raise ErrorTelegram(f"Telegram dijo: {datos.get('description') or 'error'}", 502)
    return datos.get("result")


# ================================================================ CONFIGURACIÓN

def estado():
    """Lo que enseña la pantalla. Nunca el token."""
    d = _leer()
    return {"token_puesto": bool(d.get("token")), "bot": d.get("bot") or "",
            "conectado": bool(d.get("token") and d.get("chat")),
            "chat_nombre": d.get("chat_nombre") or "", "base_url": d.get("base_url") or "",
            "conectado_el": d.get("conectado_el") or ""}


def poner_token(token):
    token = str(token or "").strip()
    if not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{20,80}", token):
        raise ErrorTelegram("eso no parece un token de bot: es como 123456789:AAH… "
                            "(cópialo entero del mensaje de @BotFather)", 400)
    yo = _llamar(token, "getMe")
    with _LOCK:
        _guardar({"token": token, "bot": (yo or {}).get("username") or "", "chat": "",
                  "chat_nombre": "", "base_url": "", "conectado_el": ""})
    return estado()


def buscar_chats():
    """Quién ha escrito al bot hace poco, el último primero. Se enseña el
    NOMBRE para que el dueño confirme que es él (cualquiera puede escribir al
    bot). -> [{id, nombre}]"""
    d = _leer()
    resultado = _llamar(d.get("token"), "getUpdates", {"timeout": 0, "limit": 50}) or []
    vistos, salida = set(), []
    for u in reversed(resultado):
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private" or chat.get("id") in vistos:
            continue
        vistos.add(chat["id"])
        nombre = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x)
        if chat.get("username"):
            nombre = f"{nombre} (@{chat['username']})".strip()
        salida.append({"id": str(chat["id"]), "nombre": nombre or str(chat["id"])})
    return salida


def confirmar_chat(chat_id, nombre, base_url):
    chat_id = str(chat_id or "").strip()
    if not re.fullmatch(r"-?\d{1,20}", chat_id):
        raise ErrorTelegram("ese chat no es válido", 400)
    base_url = str(base_url or "").strip().rstrip("/")
    if base_url and not re.fullmatch(r"https?://[^\s\"'<>]{3,300}", base_url):
        raise ErrorTelegram("la dirección del Studio no es válida", 400)
    with _LOCK:
        d = _leer()
        if not d.get("token"):
            raise ErrorTelegram("primero pega el token del bot", 409)
        d.update(chat=chat_id, chat_nombre=str(nombre or "")[:120], base_url=base_url,
                 conectado_el=time.strftime("%Y-%m-%dT%H:%M"))
        _guardar(d)
    _PAUSA.update(hasta=0.0, fallos=0)
    return estado()


def desconectar():
    with _LOCK:
        try:
            os.remove(_ruta())
        except OSError:
            pass
    return estado()


def conectado():
    d = _leer()
    return bool(d.get("token") and d.get("chat"))


def base_url():
    return _leer().get("base_url") or ""


# ================================================================ MANDAR

def en_pausa():
    return time.time() < _PAUSA["hasta"]


def _fallo():
    _PAUSA["fallos"] = min(_PAUSA["fallos"] + 1, 6)
    _PAUSA["hasta"] = time.time() + min(600, 15 * (2 ** _PAUSA["fallos"]))


def enviar(texto, silencioso=False, respetar_pausa=True):
    """-> id del mensaje (str). Lanza ErrorTelegram."""
    d = _leer()
    if not (d.get("token") and d.get("chat")):
        raise ErrorTelegram("Telegram no está conectado", 409)
    if respetar_pausa and en_pausa():
        raise ErrorTelegram("Telegram falló hace poco: se reintenta en un rato", 503)
    try:
        r = _llamar(d["token"], "sendMessage", {
            "chat_id": d["chat"], "text": str(texto)[:4000],
            "disable_web_page_preview": True, "disable_notification": bool(silencioso)})
    except ErrorTelegram:
        _fallo()
        raise
    _PAUSA.update(hasta=0.0, fallos=0)
    return str((r or {}).get("message_id") or "")


def editar(mensaje, texto):
    """Cambia un mensaje ya mandado. -> bool (False si no se pudo: no pasa nada,
    la página manda)."""
    d = _leer()
    if not (d.get("token") and d.get("chat") and mensaje) or en_pausa():
        return False
    try:
        _llamar(d["token"], "editMessageText", {
            "chat_id": d["chat"], "message_id": int(mensaje), "text": str(texto)[:4000],
            "disable_web_page_preview": True})
        return True
    except (ErrorTelegram, ValueError) as fallo:
        # «message is not modified» no es un fallo; la red caída sí (pausa)
        if "not modified" in str(fallo):
            return True
        http = getattr(fallo, "http", 0)
        if "no se pudo hablar" in str(fallo) or http == 429 or http >= 500:
            _fallo()                    # Telegram caído o saturado: se espera
        return False

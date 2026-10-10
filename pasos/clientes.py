"""Los PROYECTOS (clientes): carpetas que agrupan estilos, y con ellos sus videos.

    listar()                      -> {"clientes": [...], "estilos": {preset: cliente}}
    crear(nombre)                 -> ficha
    cambiar(cid, nombre=, oculto=, clave=)  -> ficha
    borrar(cid)                   -> los estilos que tenia quedan sin proyecto
    asignar(preset_id, cid|"")
    abrir(cid, clave)             -> bool

Para que
--------
Un mismo Estudio trabaja para varios clientes, y la galeria los mezclaba: los
estilos de uno y los videos de otro en la misma lista (10-10-2026). Un proyecto
agrupa ESTILOS; un video pertenece al proyecto de su estilo (lo dice su config,
`estilo_light`), asi que no hay que asignar cada video a mano ni dos sitios
que puedan contradecirse.

Ocultar y la clave
------------------
Un proyecto OCULTO no sale en la lista hasta que se pide «ver los ocultos». Uno
con CLAVE no enseña sus estilos ni sus videos hasta que se escribe: es
privacidad DE PANTALLA --que quien mira por encima del hombro, o quien comparte
el acceso, no vea lo de otro cliente--, no seguridad. La seguridad de verdad es
el acceso de delante (el login); quien entra en el servidor lee los ficheros.
Por eso la clave se guarda con sal y PBKDF2 y nunca se devuelve, pero no cifra
nada.

Vive en `<proyectos>/_sistema/clientes.json`: son datos, como las notas, y
`asvs actualizar` no los toca.
"""
import hashlib
import os
import re
import secrets
import threading
import time

try:
    from nucleo.proyecto import escribir_json, leer_json
except ImportError:                                     # corriendo desde pasos/
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from nucleo.proyecto import escribir_json, leer_json

MAX_NOMBRE = 80
MAX_CLIENTES = 200
_LOCK = threading.Lock()


class ErrorCliente(ValueError):
    """Lo pedido no se puede hacer, con el motivo en castellano."""


def ruta(raiz_proyectos):
    return os.path.join(raiz_proyectos, "_sistema", "clientes.json")


def _leer(raiz):
    datos = leer_json(ruta(raiz), {}) or {}
    clientes = [c for c in (datos.get("clientes") or [])
                if isinstance(c, dict) and c.get("id")]
    estilos = {str(k): str(v) for k, v in (datos.get("estilos") or {}).items()
               if isinstance(v, str)}
    return {"clientes": clientes, "estilos": estilos}


def _escribir(raiz, datos):
    os.makedirs(os.path.dirname(ruta(raiz)), exist_ok=True)
    escribir_json(ruta(raiz), datos)


def _huella(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", str(clave).encode("utf-8"),
                               bytes.fromhex(sal), 120_000).hex()


def publica(ficha):
    """La ficha sin la clave: solo si la tiene."""
    return {"id": ficha["id"], "nombre": ficha.get("nombre") or ficha["id"],
            "oculto": bool(ficha.get("oculto")),
            "con_clave": bool(ficha.get("clave")),
            "creado": ficha.get("creado") or ""}


def listar(raiz):
    datos = _leer(raiz)
    ids = {c["id"] for c in datos["clientes"]}
    return {"clientes": [publica(c) for c in datos["clientes"]],
            # una asignacion a un proyecto borrado no cuenta
            "estilos": {k: v for k, v in datos["estilos"].items() if v in ids}}


def _nombre(nombre):
    limpio = " ".join(str(nombre or "").split())[:MAX_NOMBRE]
    if not limpio:
        raise ErrorCliente("el proyecto necesita un nombre")
    return limpio


def _ficha(datos, cid):
    for ficha in datos["clientes"]:
        if ficha["id"] == cid:
            return ficha
    raise ErrorCliente(f"no hay ningun proyecto «{cid}»")


def crear(raiz, nombre):
    with _LOCK:
        datos = _leer(raiz)
        if len(datos["clientes"]) >= MAX_CLIENTES:
            raise ErrorCliente(f"como mucho {MAX_CLIENTES} proyectos")
        nombre = _nombre(nombre)
        if any(c.get("nombre", "").lower() == nombre.lower() for c in datos["clientes"]):
            raise ErrorCliente(f"ya hay un proyecto que se llama «{nombre}»")
        base = re.sub(r"[^a-z0-9]+", "_", nombre.lower()).strip("_")[:24] or "proyecto"
        cid = f"cl_{base}_{secrets.token_hex(3)}"
        ficha = {"id": cid, "nombre": nombre, "oculto": False, "clave": "",
                 "creado": time.strftime("%Y-%m-%d %H:%M")}
        datos["clientes"].append(ficha)
        _escribir(raiz, datos)
        return publica(ficha)


def cambiar(raiz, cid, nombre=None, oculto=None, clave=None):
    """`clave` "" la quita; None la deja como estaba."""
    with _LOCK:
        datos = _leer(raiz)
        ficha = _ficha(datos, cid)
        if nombre is not None:
            nuevo = _nombre(nombre)
            if any(c["id"] != cid and c.get("nombre", "").lower() == nuevo.lower()
                   for c in datos["clientes"]):
                raise ErrorCliente(f"ya hay un proyecto que se llama «{nuevo}»")
            ficha["nombre"] = nuevo
        if oculto is not None:
            ficha["oculto"] = bool(oculto)
        if clave is not None:
            clave = str(clave)
            if clave and len(clave) < 4:
                raise ErrorCliente("la clave necesita al menos 4 caracteres")
            if clave:
                sal = secrets.token_hex(16)
                ficha["clave"] = f"{sal}:{_huella(clave, sal)}"
            else:
                ficha["clave"] = ""
        _escribir(raiz, datos)
        return publica(ficha)


def borrar(raiz, cid):
    """El proyecto se va; sus estilos (y sus videos) se quedan, sin proyecto."""
    with _LOCK:
        datos = _leer(raiz)
        _ficha(datos, cid)
        datos["clientes"] = [c for c in datos["clientes"] if c["id"] != cid]
        sueltos = [k for k, v in datos["estilos"].items() if v == cid]
        for preset in sueltos:
            datos["estilos"].pop(preset, None)
        _escribir(raiz, datos)
        return sueltos


def asignar(raiz, preset_id, cid):
    preset_id = str(preset_id or "").strip()
    if not preset_id:
        raise ErrorCliente("falta el estilo")
    with _LOCK:
        datos = _leer(raiz)
        if cid:
            _ficha(datos, cid)
            datos["estilos"][preset_id] = cid
        else:
            datos["estilos"].pop(preset_id, None)
        _escribir(raiz, datos)


def abrir(raiz, cid, clave):
    """Si la clave es la del proyecto (o no tiene). -> bool"""
    datos = _leer(raiz)
    guardada = _ficha(datos, cid).get("clave") or ""
    if not guardada:
        return True
    sal, _, huella = guardada.partition(":")
    try:
        return secrets.compare_digest(_huella(clave or "", sal), huella)
    except ValueError:
        return False

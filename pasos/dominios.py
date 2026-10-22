"""LOS TIPOS DE NEGOCIO («dominios»): lo que el Studio sabe de UN tipo de
cliente (rama dominio-negocio y Etapa Foto C, 21-10-2026, pedidos del dueño).

Hasta la rama dominio-negocio, lo de EstadoPlay estaba escrito a mano por todo
el código: los servicios de alquiler y cómo se reconocen en el texto, la
escalera de cartas de foto con estaciones, trípodes y mandos, el criterio del
revisor y las reglas de foto de mandos y equipo. Un vídeo de baños o de plantas
en foto recibía ese criterio igual.

Aquí cada negocio es un TIPO, con todo lo suyo junto:

  servicios   los servicios que pueden pedir sus cartas;
  en_texto    cómo se reconoce cada servicio en el texto del vídeo;
  escalera    sus cartas de foto (con el servicio que pide cada una);
  revisor     las frases del revisor que hablan de SU equipo;
  reglas      sus reglas de foto (Etapa C), que entran en el hueco
              `reglas-del-negocio` de `motores/reglas/reglas_foto.json`.

NINGÚN NEGOCIO EN EL CÓDIGO (Etapa C, decisión del dueño: «nada de un
cliente metido en el código»). De fábrica solo hay uno, en
`dominios_fabrica.json`:
  general     ningún servicio: la escalera general de foto y un revisor que
              no habla de ningún equipo en concreto.
El negocio de cada cliente es una FICHA que se llena en su proyecto y vive en
`<proyectos>/_sistema/dominios.json` (ver más abajo). Lo que antes era de
EstadoPlay (sus cartas de consolas, sus reglas de mandos y equipo) ya no viene
con el Studio: el dueño lo escribe en la ficha de su proyecto si lo quiere.

QUÉ TIPO RIGE (`de_estilo`, `reglas_de_foto`):
  - el que fije el estilo (`estilo.dominio`): la ficha de su cliente;
  - si no fija ninguno: el general, sin reglas de ningún negocio.

Y SI ALGÚN DÍA vuelve un tipo con escalera propia: el sorteo de cartas
(`encuadres.carta_de`) va por `arranque % len(fondo)`, así que añadir, quitar o
mover una carta cambia la carta de casi todos los planos de ese tipo.
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata

RUTA_FABRICA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "dominios_fabrica.json")


def _congelar(crudo):
    """Un tipo leido del JSON con las formas de siempre: tuplas donde el codigo
    las espera (`encuadres` suma `ESCALERA_FOTO + ESCALERA_FOTO_GENERAL`) y la
    escalera con las mismas cartas, en el mismo orden y con los mismos pesos."""
    escalera = tuple(
        dict(c, servicios=(c["servicios"] if c.get("servicios", "todos") == "todos"
                           else tuple(c["servicios"])))
        for c in crudo.get("escalera") or ())
    return {
        "id": crudo["id"],
        "nombre": crudo["nombre"],
        "descripcion": crudo.get("descripcion") or "",
        "servicios": tuple(crudo.get("servicios") or ()),
        "en_texto": {k: tuple(v) for k, v in (crudo.get("en_texto") or {}).items()},
        "escalera": escalera,
        "revisor": dict(crudo["revisor"]),
        "reglas": [dict(r) for r in crudo.get("reglas") or ()],
        "por_defecto": tuple(crudo.get("por_defecto") or ()),
        "palabras": (),
        "de_fabrica": True,
    }


def _cargar_fabrica():
    with open(RUTA_FABRICA, "r", encoding="utf-8") as fh:
        datos = json.load(fh)
    return {d["id"]: _congelar(d) for d in datos["dominios"]}


#: Los de fabrica, por id y en el orden del fichero (general, estadoplay). Uno
#: nuevo se anade en `dominios_fabrica.json` (y su prueba).
DE_FABRICA = _cargar_fabrica()

GENERAL = DE_FABRICA["general"]

#: Lo que lee `encuadres` cuando un vídeo no tiene negocio: nada de ningún
#: cliente (antes, lo de EstadoPlay). Los mismos objetos que el tipo general.
SERVICIOS = GENERAL["servicios"]
SERVICIOS_EN_TEXTO = GENERAL["en_texto"]
ESCALERA_FOTO = GENERAL["escalera"]
REVISOR_GENERAL = GENERAL["revisor"]


#: El valor de `estilo.dominio` que pide la detección por texto de siempre.
AUTOMATICO = ""


# ======================================== la ficha del negocio de un cliente
#
# Etapa Foto C (21-10-2026): «nada de un cliente metido en el código». El
# negocio de cada cliente es una FICHA que se llena en su proyecto (Crear → el
# proyecto → «Ficha del negocio»), una por proyecto:
#
#   nombre       qué hace el negocio («Mamparas y baños a medida»)
#   reglas       sus reglas de foto, con el formato de las reglas del estilo
#                (`pasos/reglas_estilo.py`: texto, palabras «solo si…», versión
#                afinada en inglés)
#   revisor      lo que el revisor vigila del EQUIPO o PRODUCTO y de hacia dónde
#                MIRA la gente; lo demás, como el general
#
# Su id es `cliente-<id del proyecto>` y la llevan en `estilo.dominio` los
# estilos de ese proyecto (lo pone la API al guardar la ficha y al mover un
# estilo de proyecto). No lleva escalera propia: se reparte la general de foto.
#
# VIVEN FUERA DEL CÓDIGO, en `<proyectos>/_sistema/dominios.json`, como las
# notas: `asvs actualizar` renueva el código y no las toca.
#
# Un estilo SIN ficha (sin proyecto, o su proyecto no la ha llenado) es
# automático: general, sin reglas de ningún negocio.

MAX_NOMBRE = 120
MAX_FRASE = 400

#: Lo del revisor que se puede escribir en una ficha.
FRASES_EDITABLES = ("equipo", "orientacion")

_LOCK = threading.Lock()
_CACHE = {}


def _raiz_del_servicio():
    """La carpeta de proyectos del servicio que está corriendo, si lo hay.

    `app.py` la fija con `--proyectos` (las pruebas) o con ESTUDIO_PROYECTOS (el
    servidor), y la guarda en SU memoria, no en el entorno. Este módulo no puede
    importar app.py, así que la pregunta a quien ya lo tenga cargado: así las
    fichas viven siempre al lado de los proyectos con los que se usan, y una
    prueba con su carpeta aparte no escribe en la de verdad."""
    for nombre in ("app", "__main__"):
        modulo = sys.modules.get(nombre)
        funcion = getattr(modulo, "raiz_proyectos", None)
        if callable(funcion):
            try:
                return funcion()
            except Exception:                                    # noqa: BLE001
                return None
    return None


def ruta_usuario(raiz=None):
    """Donde viven las fichas: `<proyectos>/_sistema/dominios.json`.

    `ESTUDIO_DOMINIOS` (un fichero; lo usan las pruebas) manda. Si no, la
    carpeta que se le pase, la del servicio que corre (`_raiz_del_servicio`), la
    del entorno o la de siempre, como `profundidad.carpeta_cache`."""
    propia = os.environ.get("ESTUDIO_DOMINIOS")
    if propia:
        return propia
    raiz = (raiz or _raiz_del_servicio() or os.environ.get("ESTUDIO_PROYECTOS")
            or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "proyectos"))
    return os.path.join(raiz, "_sistema", "dominios.json")


def _llano(texto):
    """minúsculas y sin tildes, para comparar."""
    sin = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


_VARIANTES = {"a": "aáàäâ", "e": "eéèëê", "i": "iíìïî", "o": "oóòöô",
              "u": "uúùüû", "n": "nñ", "c": "cç"}


def patron_de_palabra(palabra):
    """Una palabra escrita por una persona -> expresión regular que la encuentra
    con o sin tildes y por el principio («jugador» casa con «jugadores»), como
    `reglas_estilo.aplica`."""
    trozos = []
    for letra in _llano(palabra):
        if letra in _VARIANTES:
            trozos.append("[" + _VARIANTES[letra] + "]")
        else:
            trozos.append(re.escape(letra))
    return r"(?<![\w])" + "".join(trozos)


def _limpio(valor, tope):
    return " ".join(str(valor or "").split())[:tope]


def _reglas_estilo():
    try:
        from . import reglas_estilo                               # noqa: PLC0415
    except ImportError:                                           # pragma: no cover
        import reglas_estilo                                      # noqa: PLC0415
    return reglas_estilo


def id_de_cliente(cid):
    """El id de la ficha del negocio de un proyecto. ValueError si no vale."""
    limpio = re.sub(r"[^a-z0-9_-]", "", str(cid or "").strip().lower())
    if not limpio:
        raise ValueError("ese proyecto no existe")
    return f"cliente-{limpio}"


def validar(datos):
    """Lo que manda la pantalla, limpio. -> dict (sin id ni fechas)

    Lanza ValueError con el motivo para la persona."""
    if not isinstance(datos, dict):
        raise ValueError("la ficha del negocio es un objeto")
    nombre = _limpio(datos.get("nombre"), MAX_NOMBRE + 1)
    if not nombre:
        raise ValueError("escribe qué hace este negocio")
    if len(nombre) > MAX_NOMBRE:
        raise ValueError(f"«qué hace» es demasiado largo (máximo {MAX_NOMBRE})")
    reglas_estilo = _reglas_estilo()
    try:
        reglas = reglas_estilo.normalizar(datos.get("reglas"))
    except reglas_estilo.ReglaInvalida as fallo:
        raise ValueError(f"reglas: {fallo}") from None
    revisor = {}
    crudo = datos.get("revisor") or {}
    if not isinstance(crudo, dict):
        raise ValueError("lo del revisor es un objeto")
    for clave in FRASES_EDITABLES:
        frase = _limpio(crudo.get(clave), MAX_FRASE + 1)
        if len(frase) > MAX_FRASE:
            raise ValueError(f"la frase del revisor «{clave}» es demasiado larga")
        if frase:
            revisor[clave] = frase
    return {"nombre": nombre, "reglas": reglas, "revisor": revisor}


def _a_tipo(crudo):
    """Una ficha, tal cual se guarda -> con la forma de los tipos de fábrica."""
    tid = crudo["id"]
    reglas = []
    for r in crudo.get("reglas") or []:
        regla = {"id": f"negocio-{tid}-{r['id']}", "ambito": "prompt_imagen",
                 "prioridad": 1, "regla": r.get("en") or r["texto"]}
        if r.get("palabras"):
            regla["solo_si"] = [patron_de_palabra(p) for p in r["palabras"]]
        reglas.append(regla)
    revisor = dict(GENERAL["revisor"])
    revisor.update({k: v for k, v in (crudo.get("revisor") or {}).items()
                    if k in FRASES_EDITABLES and v})
    return {
        "id": tid, "nombre": crudo["nombre"], "cliente": crudo.get("cliente") or "",
        "descripcion": "", "servicios": (), "en_texto": {}, "escalera": (),
        "por_defecto": (), "revisor": revisor, "reglas": reglas,
        "palabras": (), "de_fabrica": False,
        # lo que se escribió, para volver a enseñarlo en la pantalla
        "crudo": crudo,
    }


def _leer_usuario(ruta):
    """{id: crudo} del fichero. Un fichero roto no tumba nada: sin fichas, y
    los estilos que las tenían se leen como automáticos."""
    try:
        info = os.stat(ruta)
    except OSError:
        return {}
    clave = (ruta, info.st_mtime_ns, info.st_size)
    if clave in _CACHE:
        return _CACHE[clave]
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        lista = datos.get("dominios") if isinstance(datos, dict) else None
        fichas = {}
        for crudo in lista or []:
            if (isinstance(crudo, dict) and crudo.get("id")
                    and crudo["id"] not in DE_FABRICA and crudo.get("nombre")):
                fichas[crudo["id"]] = crudo
    except (OSError, ValueError):
        fichas = {}
    _CACHE.clear()
    _CACHE[clave] = fichas
    return fichas


def _escribir_usuario(ruta, fichas):
    carpeta = os.path.dirname(ruta)
    os.makedirs(carpeta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=".dominios-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "dominios": list(fichas.values())}, fh,
                  ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)
    _CACHE.clear()


def de_usuario(raiz=None, con_borrados=False):
    """{id: tipo} de las fichas de los clientes.

    Las BORRADAS no salen, pero se guardan: un vídeo ya creado con esa ficha en
    su copia del estilo la sigue leyendo igual (`obtener`), así que borrar no
    deja sus imágenes para rehacer."""
    return {tid: _a_tipo(c) for tid, c in _leer_usuario(ruta_usuario(raiz)).items()
            if con_borrados or not c.get("borrado")}


def todos(raiz=None):
    """{id: tipo}: el general y después las fichas de los clientes."""
    salida = dict(DE_FABRICA)
    salida.update(de_usuario(raiz))
    return salida


def obtener(tid, raiz=None):
    """El tipo con ese id, o None. Incluye las fichas borradas: ver `de_usuario`."""
    if not tid:
        return None
    clave = str(tid).strip().lower()
    return DE_FABRICA.get(clave) or de_usuario(raiz, con_borrados=True).get(clave)


def de_cliente(cid, raiz=None):
    """La ficha del negocio de un proyecto (crudo, como se escribió) o None."""
    try:
        tid = id_de_cliente(cid)
    except ValueError:
        return None
    crudo = _leer_usuario(ruta_usuario(raiz)).get(tid)
    if not crudo or crudo.get("borrado"):
        return None
    return crudo


def guardar_de_cliente(cid, datos, raiz=None):
    """Crea o cambia la ficha del negocio de un proyecto. -> la ficha (crudo)"""
    limpio = validar(datos)
    tid = id_de_cliente(cid)
    ruta = ruta_usuario(raiz)
    with _LOCK:
        fichas = dict(_leer_usuario(ruta))
        ahora = time.strftime("%Y-%m-%dT%H:%M:%S")
        anterior = fichas.get(tid) or {}
        nueva = dict(limpio, id=tid, cliente=str(cid),
                     creado=(anterior.get("creado") if not anterior.get("borrado") else None)
                     or ahora, cambiado=ahora)
        if anterior and not anterior.get("borrado") and \
                _sin_fechas(anterior) == _sin_fechas(nueva):
            return anterior
        fichas[tid] = nueva
        _escribir_usuario(ruta, fichas)
    return nueva


def _sin_fechas(crudo):
    return {k: v for k, v in crudo.items() if k not in ("creado", "cambiado")}


def borrar_de_cliente(cid, raiz=None):
    """Quita la ficha de un proyecto. -> bool (si estaba)

    Se MARCA como borrada (ver `de_usuario`): sus estilos vuelven a automático
    (la API les quita la clave) y los vídeos ya creados siguen como estaban."""
    tid = id_de_cliente(cid)
    ruta = ruta_usuario(raiz)
    with _LOCK:
        fichas = dict(_leer_usuario(ruta))
        if tid not in fichas or fichas[tid].get("borrado"):
            return False
        fichas[tid] = dict(fichas[tid], borrado=time.strftime("%Y-%m-%dT%H:%M:%S"))
        _escribir_usuario(ruta, fichas)
    return True


# ===================================================== qué tipo rige


def normalizar(valor, raiz=None):
    """Lo que se guarda en `estilo.dominio`. -> "" (automático) o el id de un
    tipo que existe (el general o la ficha de un cliente).

    Lanza ValueError con un id que no existe."""
    if valor is None:
        return AUTOMATICO
    if not isinstance(valor, str):
        raise ValueError("el negocio es el id de una ficha que exista")
    clave = valor.strip().lower()
    if clave in ("", "auto", "automatico", "automático"):
        return AUTOMATICO
    if clave not in todos(raiz):
        raise ValueError(f"«{valor}» no es la ficha de ningún negocio")
    return clave


def fijado(estilo, raiz=None):
    """El tipo que fija el estilo, o None si es automático (o ya no existe)."""
    if not isinstance(estilo, dict):
        return None
    clave = estilo.get("dominio")
    if not isinstance(clave, str) or not clave.strip():
        return None
    return obtener(clave, raiz)


def servicios_en_texto(texto, dominio=None):
    """Los servicios que nombra un texto, según los patrones del tipo (sin
    tipo, ninguno: el general no tiene). -> tupla"""
    texto = str(texto or "")
    patrones = (dominio or GENERAL)["en_texto"]
    if not texto or not patrones:
        return ()
    return tuple(nombre for nombre, lista in patrones.items()
                 if any(re.search(pat, texto, flags=re.IGNORECASE) for pat in lista))


def de_estilo(estilo, texto="", raiz=None):
    """El tipo que rige: el fijado o, sin fijar, el general. -> (tipo, automatico)

    `texto` se queda por compatibilidad: desde la Etapa Foto C nada se adivina
    por el texto del vídeo."""
    propio = fijado(estilo, raiz)
    if propio is not None:
        return propio, False
    return GENERAL, True


def frases_revisor(estilo, texto="", raiz=None):
    """Las frases del revisor para este vídeo. -> dict"""
    dominio, _ = de_estilo(estilo, texto, raiz)
    return dict(dominio["revisor"])


def reglas_de_foto(estilo, raiz=None):
    """LAS REGLAS DE FOTO DEL NEGOCIO que entran en un prompt. -> [regla]

    Con el formato de `motores/reglas/reglas_foto.json`; entran en su hueco
    `reglas-del-negocio`, cada una con su `solo_si` si lo lleva. Las de la ficha
    del cliente si el estilo la tiene; si no, ninguna."""
    propio = fijado(estilo, raiz)
    if propio is None:
        return []
    return [dict(r) for r in propio.get("reglas") or []]


def publicar(crudo):
    """Una ficha para la pantalla. -> dict"""
    return {"id": crudo["id"], "cliente": crudo.get("cliente") or "",
            "nombre": crudo["nombre"],
            "reglas": [dict(r) for r in crudo.get("reglas") or []],
            "revisor": dict(crudo.get("revisor") or {}),
            "creado": crudo.get("creado") or "", "cambiado": crudo.get("cambiado") or ""}


def listar(raiz=None):
    """El general y las fichas de los clientes, para la pantalla."""
    salida = [{"id": d["id"], "nombre": d["nombre"], "de_fabrica": True,
               "descripcion": d.get("descripcion") or ""}
              for d in DE_FABRICA.values()]
    for tipo in de_usuario(raiz).values():
        salida.append(dict(publicar(tipo["crudo"]), de_fabrica=False))
    return salida

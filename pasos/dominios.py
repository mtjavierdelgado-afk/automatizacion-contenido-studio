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

NINGÚN NEGOCIO EN EL CÓDIGO (Etapa C: «nada de un cliente metido en el
código»). Los de fábrica viven en `dominios_fabrica.json`, que viaja con el
código:
  estadoplay  los valores de antes, mismo orden y mismos pesos;
  general     ningún servicio: la escalera general de foto y un revisor que
              no habla de consolas.
Los que crea el dueño en Configuración viven en `<proyectos>/_sistema/
dominios.json` (ver más abajo).

QUÉ TIPO RIGE (`de_estilo`, `reglas_de_foto`):
  - el que fije el estilo (`estilo.dominio`);
  - si no fija ninguno: AUTOMÁTICO, que es exactamente lo de antes, byte a
    byte: las cartas de EstadoPlay si el texto nombra sus servicios, las
    reglas de consolas si el encargo habla de consolas (`solo_si`).

LA REGLA QUE NO SE PUEDE ROMPER: la escalera de EstadoPlay expandida por peso
tiene que quedar idéntica en longitud y en orden. `encuadres.carta_de` sortea
con `arranque % len(fondo)`: una carta de más, de menos o en otro sitio cambia
la carta de casi todos los planos de foto y deja sus imágenes obsoletas. Lo
comprueba `prueba_dominios.py` contra la escalera de `main`.
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
ESTADOPLAY = DE_FABRICA["estadoplay"]

#: Los nombres de antes de la Etapa C, para quien los lea (`encuadres`, las
#: pruebas): los MISMOS objetos que hay dentro de cada tipo.
SERVICIOS = ESTADOPLAY["servicios"]
SERVICIOS_EN_TEXTO = ESTADOPLAY["en_texto"]
ESCALERA_FOTO = ESTADOPLAY["escalera"]
REVISOR_ESTADOPLAY = ESTADOPLAY["revisor"]
REVISOR_GENERAL = GENERAL["revisor"]


#: El valor de `estilo.dominio` que pide la detección por texto de siempre.
AUTOMATICO = ""


# ============================================== los tipos que crea el dueño
#
# Etapa Foto C (21-10-2026): «nada de un cliente metido en el código». El dueño
# crea en Configuración los tipos de SUS clientes (baños, plantas, una clínica)
# con lo que se puede decir sin programar:
#
#   nombre       como se llama («Mamparas y baños»)
#   descripcion  para quien lo elige
#   palabras     con que palabras se reconoce en el texto de un vídeo (sirven
#                para que el revisor use sus frases en automático; NUNCA para
#                meter sus reglas en un vídeo que no lo ha fijado)
#   reglas       sus reglas de foto, con el formato de las reglas del estilo
#                (`pasos/reglas_estilo.py`: texto, palabras «solo si», versión
#                afinada en inglés)
#   revisor      lo que el revisor vigila del EQUIPO y de hacia dónde MIRA la
#                gente; lo demás, como el general
#
# No llevan escalera propia (cartas de encuadre por negocio: más adelante): se
# reparte la general de foto.
#
# VIVEN FUERA DEL CÓDIGO, en `<proyectos>/_sistema/dominios.json`, como las
# notas: `asvs actualizar` renueva el código y no los toca.
#
# Y SOLO ENTRAN SI UN ESTILO LOS FIJA. En automático un vídeo sigue saliendo
# byte a byte como antes: crear o cambiar un tipo no puede mover la firma de
# las imágenes de ningún vídeo que no lo haya elegido (regla 1 de CLAUDE.md).

MAX_TIPOS = 50
MAX_NOMBRE = 80
MAX_DESCRIPCION = 300
MAX_PALABRAS = 30
MAX_PALABRA = 40
MAX_FRASE = 400

#: Lo del revisor que se puede escribir en un tipo propio.
FRASES_EDITABLES = ("equipo", "orientacion")

_LOCK = threading.Lock()
_CACHE = {}


def _raiz_del_servicio():
    """La carpeta de proyectos del servicio que está corriendo, si lo hay.

    `app.py` la fija con `--proyectos` (las pruebas) o con ESTUDIO_PROYECTOS (el
    servidor), y la guarda en SU memoria, no en el entorno. Este módulo no puede
    importar app.py, así que la pregunta a quien ya lo tenga cargado: así los
    tipos viven siempre al lado de los proyectos con los que se usan, y una
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
    """Donde viven los tipos del dueño: `<proyectos>/_sistema/dominios.json`.

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


def _slug(nombre):
    base = re.sub(r"[^a-z0-9]+", "-", _llano(nombre)).strip("-")[:32]
    return base or "tipo"


def _limpio(valor, tope):
    return " ".join(str(valor or "").split())[:tope]


def _reglas_estilo():
    try:
        from . import reglas_estilo                               # noqa: PLC0415
    except ImportError:                                           # pragma: no cover
        import reglas_estilo                                      # noqa: PLC0415
    return reglas_estilo


def validar(datos):
    """Lo que manda la pantalla, limpio. -> dict (sin id ni fechas)

    Lanza ValueError con el motivo para la persona."""
    if not isinstance(datos, dict):
        raise ValueError("un tipo de negocio es un objeto")
    nombre = _limpio(datos.get("nombre"), MAX_NOMBRE + 1)
    if not nombre:
        raise ValueError("ponle un nombre al tipo de negocio")
    if len(nombre) > MAX_NOMBRE:
        raise ValueError(f"el nombre es demasiado largo (máximo {MAX_NOMBRE})")
    descripcion = _limpio(datos.get("descripcion"), MAX_DESCRIPCION + 1)
    if len(descripcion) > MAX_DESCRIPCION:
        raise ValueError(f"la descripción es demasiado larga (máximo {MAX_DESCRIPCION})")
    palabras = datos.get("palabras") or []
    if isinstance(palabras, str):
        palabras = palabras.split(",")
    if not isinstance(palabras, list):
        raise ValueError("las palabras son una lista")
    limpias = []
    for p in palabras:
        p = _limpio(p, MAX_PALABRA + 1)
        if not p:
            continue
        if len(p) > MAX_PALABRA:
            raise ValueError(f"«{p[:20]}…» es demasiado larga para una palabra")
        if _llano(p) not in {_llano(x) for x in limpias}:
            limpias.append(p)
    if len(limpias) > MAX_PALABRAS:
        raise ValueError(f"como mucho {MAX_PALABRAS} palabras")
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
    salida = {"nombre": nombre, "descripcion": descripcion, "palabras": limpias,
              "reglas": reglas, "revisor": revisor}
    return salida


def _de_usuario_a_tipo(crudo):
    """Un tipo del dueño, tal cual se guarda -> con la forma de los de fábrica."""
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
        "id": tid, "nombre": crudo["nombre"],
        "descripcion": crudo.get("descripcion") or "",
        "servicios": (), "en_texto": {}, "escalera": (), "por_defecto": (),
        "revisor": revisor, "reglas": reglas,
        "palabras": tuple(crudo.get("palabras") or ()),
        "de_fabrica": False,
        # lo que se escribió, para volver a enseñarlo en la pantalla
        "crudo": crudo,
    }


def _leer_usuario(ruta):
    """{id: crudo} del fichero del dueño. Un fichero roto no tumba nada: sin
    tipos propios, y los estilos que los fijaban vuelven a automático."""
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
        tipos = {}
        for crudo in lista or []:
            if (isinstance(crudo, dict) and crudo.get("id")
                    and crudo["id"] not in DE_FABRICA and crudo.get("nombre")):
                tipos[crudo["id"]] = crudo
    except (OSError, ValueError):
        tipos = {}
    _CACHE.clear()
    _CACHE[clave] = tipos
    return tipos


def _escribir_usuario(ruta, tipos):
    carpeta = os.path.dirname(ruta)
    os.makedirs(carpeta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=carpeta, prefix=".dominios-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "dominios": list(tipos.values())}, fh,
                  ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)
    _CACHE.clear()


def de_usuario(raiz=None):
    """{id: tipo} de los que creó el dueño, ya con la forma de los de fábrica."""
    return {tid: _de_usuario_a_tipo(c) for tid, c in _leer_usuario(ruta_usuario(raiz)).items()}


def todos(raiz=None):
    """{id: tipo}: los de fábrica y después los del dueño."""
    salida = dict(DE_FABRICA)
    salida.update(de_usuario(raiz))
    return salida


def obtener(tid, raiz=None):
    """El tipo con ese id, o None."""
    if not tid:
        return None
    return todos(raiz).get(str(tid).strip().lower())


def guardar(datos, tid=None, raiz=None):
    """Crea (sin `tid`) o cambia un tipo del dueño. -> el tipo guardado (crudo)

    Lanza ValueError: datos que no valen, un id de fábrica (esos no se
    cambian), uno que no existe o demasiados."""
    limpio = validar(datos)
    ruta = ruta_usuario(raiz)
    with _LOCK:
        tipos = dict(_leer_usuario(ruta))
        ahora = time.strftime("%Y-%m-%dT%H:%M:%S")
        if tid:
            tid = str(tid).strip().lower()
            if tid in DE_FABRICA:
                raise ValueError("los tipos de fábrica no se cambian: crea uno tuyo")
            if tid not in tipos:
                raise ValueError(f"no hay ningún tipo «{tid}»")
            anterior = tipos[tid]
            nuevo = dict(limpio, id=tid, creado=anterior.get("creado") or ahora,
                         cambiado=ahora)
        else:
            if len(tipos) >= MAX_TIPOS:
                raise ValueError(f"como mucho {MAX_TIPOS} tipos de negocio propios")
            nombres = {_llano(c.get("nombre")) for c in tipos.values()}
            nombres |= {_llano(d["nombre"]) for d in DE_FABRICA.values()}
            if _llano(limpio["nombre"]) in nombres:
                raise ValueError(f"ya hay un tipo que se llama «{limpio['nombre']}»")
            base = _slug(limpio["nombre"])
            tid, n = base, 2
            while tid in tipos or tid in DE_FABRICA or tid in ("auto", "automatico"):
                tid = f"{base}-{n}"
                n += 1
            nuevo = dict(limpio, id=tid, creado=ahora, cambiado=ahora)
        if tid in tipos and _sin_fechas(tipos[tid]) == _sin_fechas(nuevo):
            return tipos[tid]
        tipos[tid] = nuevo
        _escribir_usuario(ruta, tipos)
    return nuevo


def _sin_fechas(crudo):
    return {k: v for k, v in crudo.items() if k not in ("creado", "cambiado")}


def borrar(tid, raiz=None):
    """Quita un tipo del dueño. -> bool (si estaba). Los de fábrica, ValueError.

    Quien lo use (estilos, vídeos) vuelve a AUTOMÁTICO: `fijado` no lo encuentra.
    La API avisa antes de qué estilos lo tienen fijado."""
    tid = str(tid or "").strip().lower()
    if tid in DE_FABRICA:
        raise ValueError("los tipos de fábrica no se borran")
    ruta = ruta_usuario(raiz)
    with _LOCK:
        tipos = dict(_leer_usuario(ruta))
        if tid not in tipos:
            return False
        tipos.pop(tid)
        _escribir_usuario(ruta, tipos)
    return True


# ===================================================== qué tipo rige


def normalizar(valor, raiz=None):
    """Lo que se guarda en `estilo.dominio`. -> "" (automático) o el id de un
    tipo que existe (de fábrica o del dueño).

    Lanza ValueError con un id que no existe."""
    if valor is None:
        return AUTOMATICO
    if not isinstance(valor, str):
        raise ValueError("el tipo de negocio es el id de uno que exista: "
                         + ", ".join(todos(raiz)))
    clave = valor.strip().lower()
    if clave in ("", "auto", "automatico", "automático"):
        return AUTOMATICO
    if clave not in todos(raiz):
        raise ValueError(f"«{valor}» no es un tipo de negocio "
                         f"(valen: {', '.join(todos(raiz))})")
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
    """Los servicios que nombra un texto, según los patrones del dominio
    (sin dominio, los de EstadoPlay: lo de siempre). -> tupla"""
    texto = str(texto or "")
    patrones = (dominio or ESTADOPLAY)["en_texto"]
    if not texto or not patrones:
        return ()
    return tuple(nombre for nombre, lista in patrones.items()
                 if any(re.search(pat, texto, flags=re.IGNORECASE) for pat in lista))


def _lo_nombra(dominio, texto):
    """Si un texto delata ese tipo: por sus servicios (los de fábrica) o por
    sus palabras (los del dueño)."""
    if not texto:
        return False
    if dominio.get("en_texto"):
        return bool(servicios_en_texto(texto, dominio))
    return any(re.search(patron_de_palabra(p), texto, flags=re.IGNORECASE)
               for p in dominio.get("palabras") or ())


def de_estilo(estilo, texto="", raiz=None):
    """El tipo que rige: el fijado o, en automático, el que delata el texto.

    -> (dominio, automatico: bool). En automático se prueban los tipos en orden
    --los de fábrica primero, así EstadoPlay sigue ganando como antes-- y el
    primero cuyo texto aparezca rige; si ninguno, el general."""
    propio = fijado(estilo, raiz)
    if propio is not None:
        return propio, False
    for dominio in todos(raiz).values():
        if _lo_nombra(dominio, str(texto or "")):
            return dominio, True
    return GENERAL, True


def frases_revisor(estilo, texto="", raiz=None):
    """Las frases del revisor para este vídeo. -> dict"""
    dominio, _ = de_estilo(estilo, texto, raiz)
    return dict(dominio["revisor"])


def reglas_de_foto(estilo, raiz=None):
    """LAS REGLAS DE FOTO DEL NEGOCIO que pueden entrar en un prompt. -> [regla]

    Con el formato de `motores/reglas/reglas_foto.json`; entran en su hueco
    `reglas-del-negocio` y cada una con su `solo_si`, si lo lleva.

    - Tipo FIJADO: las suyas (las de general: ninguna; un vídeo de un estilo
      fijado en general no recibe las de consolas aunque hable de mandos).
    - AUTOMÁTICO: las reglas CONDICIONALES de los de fábrica, que es justo lo
      que había antes en `reglas_foto.json` (las de consolas, con su `solo_si`).
      Las de los tipos del dueño no: crear un tipo no cambia ningún vídeo que no
      lo haya elegido.
    """
    propio = fijado(estilo, raiz)
    if propio is not None:
        return [dict(r) for r in propio.get("reglas") or []]
    return [dict(r) for d in DE_FABRICA.values()
            for r in d.get("reglas") or [] if r.get("solo_si")]


def listar(raiz=None):
    """Los tipos, para la pantalla: los de fábrica (de solo lectura) y los del
    dueño, con lo que hace falta para enseñarlos y editarlos."""
    salida = []
    for d in todos(raiz).values():
        ficha = {"id": d["id"], "nombre": d["nombre"],
                 "descripcion": d.get("descripcion") or "",
                 "de_fabrica": bool(d.get("de_fabrica")),
                 "servicios": list(d["servicios"]),
                 "cartas_propias": bool(d.get("escalera")),
                 "revisor": {k: " ".join(str(d["revisor"].get(k) or "").split())
                             for k in FRASES_EDITABLES}}
        if d.get("de_fabrica"):
            ficha["palabras"] = list(d["servicios"])
            ficha["reglas"] = [{"id": r["id"], "texto": r["regla"],
                                "condicional": bool(r.get("solo_si"))}
                               for r in d.get("reglas") or []]
        else:
            crudo = d.get("crudo") or {}
            ficha["palabras"] = list(crudo.get("palabras") or [])
            ficha["reglas"] = [dict(r) for r in crudo.get("reglas") or []]
            ficha["revisor_propio"] = dict(crudo.get("revisor") or {})
            ficha["creado"] = crudo.get("creado") or ""
            ficha["cambiado"] = crudo.get("cambiado") or ""
        salida.append(ficha)
    return salida

"""EL PILOTO AUTOMÁTICO: niveles 2 y 3 (rama `piloto-2`, CIS 4c, 24-11-2026).

Plan aprobado por el árbitro: `estado/plan_piloto_niveles_2_3_2026-11-24.md`
del Proyecto. El nivel 1 («🤖 Hacer el vídeo completo») vive en `piloto.py` y
en el bloque PILOTO de `app.py`; esto se pone ENCIMA:

    nivel 2   cada proyecto tiene un calendario (días, horas y redes). Antes de
              cada hueco el Studio toma el siguiente guion de la Parrilla, hace
              el vídeo con el nivel 1 y avisa por Telegram con un enlace a una
              página para el móvil. Nada sale sin «✓ Publicar así».
    nivel 3   igual, pero lo programa solo en Upload-Post SALVO que haya una
              razón para esperar (`razones_*`): entonces avisa y espera tu OK.

AQUÍ SOLO VIVEN LOS DATOS Y LAS DECISIONES, como en `piloto.py`: funciones
puras con el reloj como argumento, para poder probarlas sin servidor
(`prueba_piloto_auto.py`). Quien llama a Upload-Post, a Telegram y al nivel 1
es `app.py` (bloque PILOTO, `_auto_*`), y SOLO desde el vigía (o desde una
ruta, con el mismo cerrojo): nunca dos sitios a la vez.

DÓNDE VIVE
----------
`<proyectos>/_sistema/piloto/auto.json`, junto a `piloto.json`, fuera de la
carpeta de cada vídeo: nada de aquí entra en ninguna firma (regla 1). Se
escribe SOLO cuando el dueño guarda la ficha, o cuando el vigía apunta lo que
ha hecho. Abrir una pantalla no escribe nada.

    {"proyectos": {cid: ficha},              la ficha «🤖 Piloto automático»
     "historial": {"cid|gid|indice": {...}}, qué encargos hizo el automático
     "avisos": {clave: "AAAA-MM-DD..."}}     qué avisos de proyecto ya se dieron

EL HISTORIAL NO SE PODA. Es lo que dice si un encargo de un guion ya se hizo:
la ficha de `piloto.json` se olvida a los 300 vídeos y, sin esto, un encargo
ya publicado volvería a la lista y se pagaría (y publicaría) otra vez.

LOS PASOS DE UN VÍDEO AUTOMÁTICO (`ficha["auto"]["paso"]` en piloto.json)
------------------------------------------------------------------------
    preparando     el nivel 1 lo está haciendo (o espera su turno)
    espera_ok      terminado; espera «✓ Publicar así» (o una razón lo frena)
    publicando     se está llamando a `enviar` (se guarda ANTES de llamar)
    programado     Upload-Post lo tiene para su hora
    reprogramando  cancelando sus envíos para ponerle otra fecha
    retirando      cancelando sus envíos porque dijiste «No publicar»
    publicado      salió en todas sus redes
    no_publicar    no se publica (lo dijiste tú, o el vídeo ya no existe)
    fallo          alguna red falló; las demás siguen como estaban

Lo que se ENSEÑA no es el paso guardado: se calcula al leer juntando el paso
con los envíos de Publicar (`estado_vivo`). Si un reinicio dejó el paso viejo,
mandan los envíos y la siguiente vuelta del vigía lo corrige.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import threading

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_ESTUDIO not in sys.path:
    sys.path.insert(0, RAIZ_ESTUDIO)
from nucleo.proyecto import ahora, escribir_json, leer_json  # noqa: E402


class ErrorAuto(ValueError):
    """Lo pedido no se puede hacer, con el motivo en castellano. `codigo` HTTP."""

    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = int(codigo)


PASOS = ("preparando", "espera_ok", "publicando", "programado", "reprogramando",
         "retirando", "publicado", "no_publicar", "fallo")
#: Los que ya no harán nada más solos.
PASOS_FINALES = ("publicado", "no_publicar")
#: Los que aún NO tienen nada en Upload-Post (cuentan en el freno de gasto).
SIN_PROGRAMAR = ("preparando", "espera_ok")
#: Los que el vigía tiene que seguir mirando en Upload-Post.
EN_UPLOAD = ("publicando", "programado", "reprogramando", "retirando", "fallo")

MODOS = (2, 3)
NOMBRE_MODO = {2: "Nivel 2 · con tu OK", 3: "Nivel 3 · publica solo"}
FRASE_MODO = {
    2: "Hace el vídeo antes de su hora y te avisa al móvil. No sale nada sin tu OK.",
    3: "Hace el vídeo y lo programa solo. Si algo no está bien, te avisa y espera tu OK.",
}
DIAS = ("L", "M", "X", "J", "V", "S", "D")          # 1 = lunes … 7 = domingo
NOMBRE_DIA = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")

#: Un hueco tiene que quedar al menos a esto de ahora (Upload-Post rechaza lo
#: que está a menos de 2 min, y la subida tarda).
MARGEN_MIN = 10
#: Cuántos días por delante se miran los huecos.
DIAS_VISTA = 21
MAX_HUECOS = 28                         # líneas del calendario de un proyecto

FICHA_DEFECTO = {
    "activo": False, "modo": 2, "huecos": [], "estilo": "",
    "duracion_s": None, "formato": None,
    "anticipacion_h": 24, "max_pendientes": 2, "aviso_guiones_dias": 3,
    # avanzado: los del nivel 1 para estos vídeos ("" = los generales del piloto)
    "avanzado": {},
}
LIMITES = {"anticipacion_h": (1, 72), "max_pendientes": (1, 5),
           "aviso_guiones_dias": (1, 14)}
AVANZADO = ("tope_usd", "si_falla", "umbral_pct", "vueltas", "portadas")

_LOCK = threading.RLock()


# ================================================================ DÓNDE VIVE

def _ruta(raiz):
    return os.path.join(raiz, "_sistema", "piloto", "auto.json")


def _leer(raiz):
    """ESTRICTO, como el piloto: ilegible es un 503, nunca una ficha vacía (el
    siguiente guardado borraría el historial y se repagarían encargos)."""
    try:
        datos = leer_json(_ruta(raiz), {}, estricto=True) or {}
    except (ValueError, OSError) as fallo:
        raise ErrorAuto(f"la ficha del piloto automático no se puede leer ({fallo}). No se "
                        "ha tocado nada: avisa para revisar _sistema/piloto/auto.json",
                        503) from None
    if not isinstance(datos, dict):
        datos = {}
    for k in ("proyectos", "historial", "avisos"):
        if not isinstance(datos.get(k), dict):
            datos[k] = {}
    return datos


def _guardar(raiz, datos):
    os.makedirs(os.path.dirname(_ruta(raiz)), exist_ok=True)
    escribir_json(_ruta(raiz), datos)


def clave_proyecto(cid):
    """«» y «_sin» son el mismo proyecto (el «Sin proyecto» de Publicar)."""
    cid = str(cid or "").strip()
    return "" if cid in ("", "_sin") else cid


# ================================================================ LA FICHA

def _hora(texto):
    texto = str(texto or "").strip()
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", texto)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ErrorAuto(f"la hora va como 19:00 (has puesto «{texto}»)")
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _numero(clave, valor):
    menor, mayor = LIMITES[clave]
    try:
        n = float(valor)
    except (TypeError, ValueError):
        raise ErrorAuto(f"«{clave}» tiene que ser un número") from None
    if n != n:
        raise ErrorAuto(f"«{clave}» tiene que ser un número")
    return int(round(max(menor, min(mayor, n))))


def limpiar_ficha(cambios, redes_validas):
    """Valida lo que manda la pantalla. -> dict solo con lo que viene"""
    if not isinstance(cambios, dict):
        raise ErrorAuto("la ficha va en un objeto")
    salida = {}
    for clave, valor in cambios.items():
        if clave == "activo":
            salida[clave] = bool(valor)
        elif clave == "modo":
            try:
                modo = int(valor)
            except (TypeError, ValueError):
                modo = 0
            if modo not in MODOS:
                raise ErrorAuto("el modo es 2 (con tu OK) o 3 (publica solo)")
            salida[clave] = modo
        elif clave == "huecos":
            if not isinstance(valor, list):
                raise ErrorAuto("el calendario va en una lista")
            if len(valor) > MAX_HUECOS:
                raise ErrorAuto(f"como mucho {MAX_HUECOS} horas en el calendario")
            huecos = []
            for h in valor:
                if not isinstance(h, dict):
                    raise ErrorAuto("cada hora del calendario va en un objeto")
                dias = sorted({int(d) for d in (h.get("dias") or [])
                               if str(d).isdigit() and 1 <= int(d) <= 7})
                if not dias:
                    raise ErrorAuto("cada hora del calendario necesita al menos un día")
                redes = [r for r in redes_validas if r in (h.get("redes") or [])]
                if not redes:
                    raise ErrorAuto("cada hora del calendario necesita al menos una red")
                if any(r not in redes_validas for r in (h.get("redes") or [])):
                    raise ErrorAuto("una de las redes no existe")
                huecos.append({"dias": dias, "hora": _hora(h.get("hora")), "redes": redes})
            salida[clave] = huecos
        elif clave == "estilo":
            salida[clave] = str(valor or "").strip()[:120]
        elif clave == "duracion_s":
            if valor in (None, ""):
                salida[clave] = None
            else:
                try:
                    d = int(float(valor))
                except (TypeError, ValueError):
                    raise ErrorAuto("la duración va en segundos") from None
                if not 5 <= d <= 3600:
                    raise ErrorAuto("la duración tiene que estar entre 5 s y 1 hora")
                salida[clave] = d
        elif clave == "formato":
            f = str(valor or "").strip().lower() or None
            if f and f not in ("vertical", "horizontal"):
                raise ErrorAuto("el formato es «vertical» u «horizontal»")
            salida[clave] = f
        elif clave in LIMITES:
            salida[clave] = _numero(clave, valor)
        elif clave == "avanzado":
            if not isinstance(valor, dict):
                raise ErrorAuto("«avanzado» va en un objeto")
            malos = [k for k in valor if k not in AVANZADO]
            if malos:
                raise ErrorAuto(f"ajuste avanzado desconocido: {', '.join(malos)}")
            salida[clave] = {k: v for k, v in valor.items() if v not in (None, "")}
        elif clave == "rev":
            continue
        else:
            raise ErrorAuto(f"campo desconocido en la ficha: {clave}")
    return salida


def leer_ficha(raiz, cid):
    """La ficha GUARDADA de un proyecto, o None si nunca se guardó."""
    with _LOCK:
        propia = _leer(raiz)["proyectos"].get(clave_proyecto(cid))
    if not isinstance(propia, dict):
        return None
    ficha = dict(FICHA_DEFECTO, **propia)
    ficha["rev"] = int(propia.get("rev") or 0)
    return ficha


def ficha_para_pantalla(raiz, cid, hora_publicar="19:00", redes_publicar=()):
    """Lo que enseña la ficha: la guardada, o una PROPUESTA sin guardar (el
    calendario sale de la hora y las redes de Publicar del proyecto)."""
    guardada = leer_ficha(raiz, cid)
    if guardada is not None:
        return dict(guardada, guardada=True)
    propuesta = dict(FICHA_DEFECTO, rev=0, guardada=False)
    try:
        hora = _hora(hora_publicar)
    except ErrorAuto:
        hora = "19:00"
    propuesta["huecos"] = [{"dias": [1, 3, 5], "hora": hora,
                            "redes": list(redes_publicar or [])}]
    return propuesta


def guardar_ficha(raiz, cid, cambios, redes_validas, rev=None):
    """Guarda la ficha (solo al pulsar «Guardar»). `rev` es el que leyó la
    pantalla: si alguien guardó entre medias -> 409. -> la ficha"""
    limpios = limpiar_ficha(cambios, redes_validas)
    clave = clave_proyecto(cid)
    with _LOCK:
        datos = _leer(raiz)
        actual = datos["proyectos"].get(clave)
        actual = dict(actual) if isinstance(actual, dict) else {}
        rev_actual = int(actual.get("rev") or 0)
        if rev is not None and int(rev or 0) != rev_actual:
            raise ErrorAuto("Esto se cambió en otro sitio hace un momento: vuelve a abrir la "
                            "ficha para ver lo nuevo", 409)
        nueva = dict(FICHA_DEFECTO, **actual)
        nueva.update(limpios)
        if nueva.get("activo"):
            if not nueva.get("huecos"):
                raise ErrorAuto("para encenderlo, pon al menos una hora en el calendario")
            if not nueva.get("estilo"):
                raise ErrorAuto("para encenderlo, elige el estilo de los vídeos")
        nueva["rev"] = rev_actual + 1
        nueva["guardada_el"] = ahora()
        datos["proyectos"][clave] = nueva
        _guardar(raiz, datos)
    return leer_ficha(raiz, cid)


def proyectos_activos(raiz):
    """{cid: ficha} de los proyectos con el piloto automático encendido."""
    with _LOCK:
        datos = _leer(raiz)
    return {cid: dict(FICHA_DEFECTO, **f) for cid, f in datos["proyectos"].items()
            if isinstance(f, dict) and f.get("activo")}


def apagar(raiz, cid, motivo=""):
    """Apaga la ficha de un proyecto (borrado, o lo pide el dueño)."""
    clave = clave_proyecto(cid)
    with _LOCK:
        datos = _leer(raiz)
        ficha = datos["proyectos"].get(clave)
        if isinstance(ficha, dict) and ficha.get("activo"):
            ficha["activo"] = False
            ficha["rev"] = int(ficha.get("rev") or 0) + 1
            ficha["apagado_porque"] = str(motivo or "")[:200]
            _guardar(raiz, datos)


# ================================================================ EL RELOJ

def a_texto(momento):
    return momento.strftime("%Y-%m-%dT%H:%M")


def de_texto(texto):
    """«AAAA-MM-DDTHH:MM» -> datetime SIN zona (hora de Lima: Perú no cambia
    de hora, así que sumar días no se equivoca nunca)."""
    try:
        return dt.datetime.strptime(str(texto or "")[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _sin_zona(momento):
    return momento.replace(tzinfo=None, second=0, microsecond=0)


def bonito(texto):
    """«2026-11-26T19:00» -> «jue 26 a las 19:00»."""
    m = de_texto(texto)
    if m is None:
        return str(texto or "")
    return f"{NOMBRE_DIA[m.weekday()]} {m.day} a las {m.strftime('%H:%M')}"


# ================================================================ LOS HUECOS

def huecos_de(ficha, desde, dias=DIAS_VISTA):
    """Los momentos concretos del calendario a partir de `desde` (incluido),
    ordenados. Dos líneas con la misma hora el mismo día son UN hueco con la
    unión de sus redes. -> [{"cuando", "redes"}]"""
    desde = _sin_zona(desde)
    juntos = {}
    for d in range(int(dias) + 1):
        dia = (desde + dt.timedelta(days=d)).date()
        for linea in (ficha or {}).get("huecos") or []:
            if dia.isoweekday() not in (linea.get("dias") or []):
                continue
            try:
                hh, mm = [int(x) for x in str(linea.get("hora")).split(":")]
            except (TypeError, ValueError):
                continue
            momento = dt.datetime.combine(dia, dt.time(hh, mm))
            if momento < desde:
                continue
            clave = a_texto(momento)
            redes = juntos.setdefault(clave, [])
            for r in linea.get("redes") or []:
                if r not in redes:
                    redes.append(r)
    return [{"cuando": c, "redes": r} for c, r in sorted(juntos.items())]


def horas_repetidas(ficha):
    """Las horas que salen en dos líneas el mismo día (se juntan; se avisa)."""
    vistos, repetidas = {}, set()
    for linea in (ficha or {}).get("huecos") or []:
        for d in linea.get("dias") or []:
            clave = (d, linea.get("hora"))
            if clave in vistos:
                repetidas.add(f"{DIAS[d - 1]} {linea.get('hora')}")
            vistos[clave] = True
    return sorted(repetidas)


def es_automatico(ficha):
    return isinstance((ficha or {}).get("auto"), dict)


def ocupa_hueco(ficha):
    """¿Este vídeo del piloto tiene su hueco tomado? Un cancelado a mano lo
    suelta; uno que no se publica, también; uno con una red fallida NO."""
    if not es_automatico(ficha):
        return False
    a = ficha["auto"]
    if a.get("paso") == "no_publicar":
        return False
    if ficha.get("estado") == "cancelado" and a.get("paso") in SIN_PROGRAMAR:
        return False
    return bool(a.get("hueco"))


def ocupados(fichas_piloto, cid):
    cid = clave_proyecto(cid)
    return {f["auto"]["hueco"] for f in fichas_piloto
            if ocupa_hueco(f) and clave_proyecto(f["auto"].get("cid")) == cid}


def hueco_libre(ficha, fichas_piloto, cid, ahora_, despues=None, quitar=None):
    """El siguiente hueco del calendario que no tiene vídeo y queda al menos a
    `MARGEN_MIN` de ahora (y después de `despues`, si viene). `quitar` es el
    hueco del propio vídeo (no se cuenta como ocupado). -> {cuando, redes} o None"""
    limite = _sin_zona(ahora_) + dt.timedelta(minutes=MARGEN_MIN)
    if despues:
        d = de_texto(despues)
        if d is not None and d >= limite:
            limite = d + dt.timedelta(minutes=1)
    tomados = ocupados(fichas_piloto, cid)
    if quitar:
        tomados.discard(quitar)
    for h in huecos_de(ficha, limite):
        if h["cuando"] not in tomados:
            return h
    return None


def vencido(hueco, ahora_):
    """¿Ese hueco ya no da tiempo? (menos de MARGEN_MIN por delante)"""
    m = de_texto(hueco)
    return m is None or m < _sin_zona(ahora_) + dt.timedelta(minutes=MARGEN_MIN)


def toca_preparar(hueco, ahora_, anticipacion_h):
    """¿Ya hay que empezar el vídeo de ese hueco?"""
    m = de_texto(hueco)
    return m is not None and m - dt.timedelta(hours=int(anticipacion_h or 24)) <= _sin_zona(ahora_)


# ================================================================ EL HISTORIAL

def clave_unidad(cid, gid, indice):
    return f"{clave_proyecto(cid) or '_sin'}|{gid}|{int(indice or 0)}"


def historial(raiz):
    with _LOCK:
        return dict(_leer(raiz)["historial"])


def apuntar_unidad(raiz, cid, gid, indice, vid):
    """El automático ha empezado este encargo: ya no vuelve a la lista solo."""
    with _LOCK:
        datos = _leer(raiz)
        datos["historial"][clave_unidad(cid, gid, indice)] = {
            "vid": vid, "cuando": ahora(), "devuelto": False}
        _guardar(raiz, datos)


def devolver_unidad(raiz, cid, gid, indice):
    """«Devolver a la lista»: ese encargo (solo ese) se puede volver a hacer
    (y a pagar). -> True si estaba apuntado"""
    clave = clave_unidad(cid, gid, indice)
    with _LOCK:
        datos = _leer(raiz)
        entrada = datos["historial"].get(clave)
        if not isinstance(entrada, dict):
            return False
        entrada["devuelto"] = True
        entrada["devuelto_el"] = ahora()
        _guardar(raiz, datos)
    return True


def _hecha(hist, clave):
    e = hist.get(clave)
    return isinstance(e, dict) and not e.get("devuelto")


def unidades_candidatas(parrilla, cid, hist):
    """Los encargos que el automático puede hacer, en el orden de la Parrilla.

    Entran: todos los encargos de un guion «pendiente», y los encargos aún no
    hechos de un guion que YA tiene rastro en el historial automático (sus
    siguientes vídeos). Un guion «usado» o «publicado» SIN rastro (hecho a mano
    o con el nivel 1) no se toca nunca. -> [{gid, indice, codigo, titulo, avisos}]"""
    salida = []
    pref = (clave_proyecto(cid) or "_sin") + "|"
    con_rastro = {k.split("|")[1] for k in hist if k.startswith(pref)}
    for matriz in (parrilla or {}).get("matrices") or []:
        for g in matriz.get("guiones") or []:
            gid = g.get("id")
            if not gid:
                continue
            if g.get("estado", "pendiente") != "pendiente" and gid not in con_rastro:
                continue
            for indice in range(max(1, int(g.get("encargos") or 0))):
                if _hecha(hist, clave_unidad(cid, gid, indice)):
                    continue
                salida.append({"gid": gid, "indice": indice, "codigo": g.get("codigo") or "",
                               "titulo": g.get("titulo") or "", "estilo": g.get("estilo") or ""})
    return salida


# ================================================================ AVISOS DE PROYECTO

def ya_avisado(raiz, clave, horas=24):
    """¿Se dio este aviso hace menos de `horas`? (para no repetir Telegram)"""
    with _LOCK:
        cuando = _leer(raiz)["avisos"].get(clave)
    m = de_texto(cuando)
    if m is None:
        return False
    return dt.datetime.now() - m < dt.timedelta(hours=horas)


def apuntar_aviso(raiz, clave, cuando=None):
    with _LOCK:
        datos = _leer(raiz)
        datos["avisos"][clave] = cuando or dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
        # no crece sin fin: los de hace más de 30 días se olvidan
        limite = (dt.datetime.now() - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
        datos["avisos"] = {k: v for k, v in datos["avisos"].items() if str(v) >= limite}
        _guardar(raiz, datos)


def olvidar_aviso(raiz, clave):
    """El motivo ya no aplica: la próxima vez que vuelva, se avisa otra vez."""
    with _LOCK:
        datos = _leer(raiz)
        if datos["avisos"].pop(clave, None) is not None:
            _guardar(raiz, datos)


def faltan_guiones(ficha, candidatas, fichas_piloto, cid, ahora_):
    """¿Los guiones que quedan cubren los huecos de los próximos días?
    -> None, o {"huecos": n, "guiones": m, "dias": d, "ninguno": bool}"""
    dias = int((ficha or {}).get("aviso_guiones_dias") or 3)
    tomados = ocupados(fichas_piloto, cid)
    libres = [h for h in huecos_de(ficha, _sin_zona(ahora_), dias)
              if h["cuando"] not in tomados and not vencido(h["cuando"], ahora_)]
    if not candidatas:
        return {"huecos": len(libres), "guiones": 0, "dias": dias, "ninguno": True}
    if len(candidatas) < len(libres):
        return {"huecos": len(libres), "guiones": len(candidatas), "dias": dias,
                "ninguno": False}
    return None


# ================================================================ LAS RAZONES

def _razon(clave, texto, que_hacer="", salta=False, bloquea=True):
    return {"clave": clave, "texto": texto, "que_hacer": que_hacer,
            "salta": bool(salta), "bloquea": bool(bloquea)}


def razones_antes_de_gastar(hechos):
    """Grupo A del plan: ¿se puede EMPEZAR este vídeo? Nada se paga si sale
    alguna con `bloquea`. `salta` = la salta «Hacer igualmente».

    `hechos` (los junta app.py): avisos_encargo, sin_material, falta_duracion,
    falta_formato, estilo_existe, estilo_del_proyecto, perfil, clave_upload,
    redes_sin_cuenta, freno {pendientes, max}."""
    h = hechos or {}
    salida = []
    if h.get("sin_material"):
        salida.append(_razon("material", "el guion no tiene material para hacer el vídeo",
                             "escribe la voz de cada escena o «- Material:» en el guion"))
    if any("[FALTA CTA]" in str(a) for a in h.get("avisos_encargo") or []):
        salida.append(_razon("cta", "al guion le falta la llamada a la acción ([FALTA CTA])",
                             "escríbela en el guion, o pulsa «Hacer igualmente»", salta=True))
    if h.get("falta_duracion") or h.get("falta_formato"):
        falta = " y ".join(x for x, s in (("la duración", h.get("falta_duracion")),
                                          ("el formato", h.get("falta_formato"))) if s)
        salida.append(_razon("duracion", f"el guion no dice {falta} y la ficha tampoco",
                             "escríbelo en el guion o en la ficha del piloto automático"))
    if not h.get("estilo_existe", True):
        salida.append(_razon("estilo", "el estilo elegido ya no existe",
                             "elige otro estilo en la ficha del piloto automático"))
    elif not h.get("estilo_del_proyecto", True):
        salida.append(_razon("estilo_ajeno",
                             "el estilo de este guion es de otro proyecto: el vídeo caería allí",
                             "cambia el estilo del guion o muévelo a este proyecto"))
    if not h.get("clave_upload", True):
        salida.append(_razon("clave", "falta la clave de Upload-Post",
                             "ponla en Configuración → Claves"))
    elif not h.get("perfil", True):
        salida.append(_razon("perfil", "este proyecto no tiene perfil de Upload-Post",
                             "ponlo en Publicar → Cuentas y ajustes"))
    sin = h.get("redes_sin_cuenta") or []
    if sin:
        salida.append(_razon("cuentas", f"{', '.join(sin)} no tiene cuenta conectada",
                             "conéctala en Publicar → Cuentas y ajustes y pulsa «Ver cuentas»"))
    freno = h.get("freno") or {}
    if freno and int(freno.get("pendientes") or 0) >= int(freno.get("max") or 1):
        salida.append(_razon("freno", f"ya hay {freno['pendientes']} vídeos sin publicar "
                                      "esperando: no hago más hasta que salgan",
                             "apruébalos o quítalos, o sube «cuántos a la vez» en la ficha"))
    return salida


#: Los tipos de «Para revisar» que frenan la publicación sola (grupo B.9).
TIPOS_QUE_BLOQUEAN = ("imagen_marcada", "imagen_sin_revisar", "textos", "portada")
#: Los que son solo información.
TIPOS_INFO = ("aprobado_por_piloto", "portada_ia_tope", "del_guion", "del_encargo", "info")


def revisar_bloquea(lineas):
    """Las líneas de «Para revisar» que frenan el nivel 3. Una línea sin tipo
    (de antes de esta rama) frena, por prudencia."""
    return [l for l in (lineas or [])
            if isinstance(l, dict) and l.get("tipo") not in TIPOS_INFO]


def razones_durante(ficha):
    """Grupo B: lo que pasó mientras se hacía el vídeo (paradas, fallos y lo
    apuntado en «Para revisar»)."""
    salida = []
    estado = (ficha or {}).get("estado")
    tipo = (ficha or {}).get("tipo_parada") or ""
    if estado == "parado":
        if tipo == "tope":
            salida.append(_razon("tope", "costaría más que tu tope de $ por vídeo",
                                 "mira el coste y pulsa «Seguir igualmente», o quítalo"))
        elif tipo == "interruptor":
            salida.append(_razon("imagenes", "el revisor dejó demasiadas imágenes marcadas",
                                 "míralas en el Studio y pulsa «Seguir igualmente»"))
        else:
            salida.append(_razon("parado", (ficha.get("porque") or ficha.get("mensaje")
                                            or "se detuvo"), "míralo en el Studio"))
    elif estado == "error":
        salida.append(_razon("error", ficha.get("porque") or ficha.get("mensaje") or "falló",
                             "pulsa «Reintentar» (sigue donde iba, sin volver a pagar lo hecho)"))
    elif estado == "interrumpido":
        salida.append(_razon("interrumpido",
                             "se reinició el Studio (por ejemplo, al actualizar) mientras se hacía",
                             "pulsa «Reintentar»: sigue donde iba"))
    elif estado in ("listo", "revisar"):
        for linea in revisar_bloquea(ficha.get("revisar"))[:5]:
            salida.append(_razon("revisar", linea.get("que") or "algo que revisar",
                                 "míralo; si está bien, apruébalo"))
    return salida


def razones_antes_de_publicar(hechos):
    """Grupo C: mirado justo antes de `enviar`. `hechos` (los junta app.py):
    redes, portada, textos_faltan[], encaje_malo[], desactualizada, mp4_cambiado,
    guion_cambiado, salio (texto o ""), cliente_ok, redes_sin_cuenta[],
    clave_upload, perfil."""
    h = hechos or {}
    salida = []
    if not h.get("portada", True):
        salida.append(_razon("portada", "no tiene portada", "elige o haz una portada"))
    if h.get("textos_faltan"):
        salida.append(_razon("textos", "falta el texto de " + ", ".join(h["textos_faltan"]),
                             "escríbelo o pulsa «🎯 Dame 4 títulos»"))
    if h.get("encaje_malo"):
        salida.append(_razon("encaje", "; ".join(h["encaje_malo"]),
                             "quita esa red de este vídeo"))
    if h.get("desactualizada"):
        salida.append(_razon("desactualizada", "los textos se escribieron para un montaje anterior",
                             "vuelve a escribirlos o revísalos"))
    if h.get("mp4_cambiado"):
        salida.append(_razon("mp4", "alguien cambió el vídeo después de que lo terminara el piloto",
                             "míralo y apruébalo"))
    if h.get("guion_cambiado"):
        salida.append(_razon("guion", "el guion cambió en la Parrilla después de hacer el vídeo",
                             "mira si el vídeo sigue valiendo"))
    if h.get("salio"):
        salida.append(_razon("salio", h["salio"], "no hace falta hacer nada"))
    if not h.get("cliente_ok", True):
        salida.append(_razon("cliente", "este vídeo ya no es de este proyecto: no lo publico en "
                                        "sus cuentas", "muévelo de vuelta o publícalo a mano"))
    if not h.get("clave_upload", True):
        salida.append(_razon("clave", "falta la clave de Upload-Post",
                             "ponla en Configuración → Claves"))
    elif not h.get("perfil", True):
        salida.append(_razon("perfil", "este proyecto no tiene perfil de Upload-Post",
                             "ponlo en Publicar → Cuentas y ajustes"))
    if h.get("redes_sin_cuenta"):
        salida.append(_razon("cuentas", ", ".join(h["redes_sin_cuenta"])
                             + " no tiene cuenta conectada",
                             "conéctala en Publicar → Cuentas y ajustes"))
    return salida


# ================================================================ LOS ENVÍOS

def envios_del_intento(auto, envios):
    """Los envíos de Publicar que salieron de ESTE vídeo automático (los que no
    estaban antes de su primer intento)."""
    antes = set((auto or {}).get("envios_antes") or [])
    return [e for e in envios or [] if e.get("id") and e["id"] not in antes]


def _de_red(envios, red):
    return [e for e in envios if e.get("red") == red]


def resumen_envios(auto, envios):
    """Cómo están las redes del vídeo en Upload-Post. -> dict"""
    propios = envios_del_intento(auto, envios)
    redes = list((auto or {}).get("redes") or [])
    por_red = {}
    for red in redes:
        de_red = _de_red(propios, red)
        # el más nuevo manda (un reintento de una red fallida es un envío nuevo)
        de_red.sort(key=lambda e: str(e.get("creado") or ""))
        por_red[red] = de_red[-1].get("estado") if de_red else ""
    estados = list(por_red.values())
    vivos = ("enviando", "programado", "publicando", "publicado", "comprobar", "a_mano")
    return {
        "por_red": por_red,
        "todas_publicadas": bool(redes) and all(e == "publicado" for e in estados),
        "alguna_fallida": [r for r, e in por_red.items() if e == "fallido"],
        "comprobar": [r for r, e in por_red.items() if e == "comprobar"],
        "todas_canceladas": bool(propios) and all(e in ("cancelado", "") for e in estados)
        and any(e == "cancelado" for e in estados),
        "sin_envio": [r for r, e in por_red.items() if e in ("", "cancelado")],
        "vivas": [r for r, e in por_red.items() if e in vivos],
        "alguno": bool(propios),
        "cancelables": [e for e in propios if e.get("estado") in ("programado", "espera_ok")],
        "esperar": [e for e in propios if e.get("estado") == "enviando"],
        "envios_comprobar": [e for e in propios if e.get("estado") == "comprobar"],
        "salidos": [r for r, e in por_red.items() if e in ("publicado", "publicando", "a_mano")],
    }


def reconciliar(auto, envios):
    """Qué paso le toca al vídeo según sus envíos (grupo de §4.2.3 del plan).
    -> {"paso": nuevo o None, "aviso": clave o "", "accion": ...}

    No llama a nadie: app.py hace la acción y guarda el paso."""
    paso = (auto or {}).get("paso")
    r = resumen_envios(auto, envios)
    if paso in ("no_publicar", "publicado", "preparando"):
        return {"paso": None, "aviso": "", "accion": ""}
    if paso in ("retirando", "reprogramando"):
        if r["envios_comprobar"]:
            return {"paso": None, "aviso": "comprobar", "accion": "refrescar"}
        if r["esperar"]:
            return {"paso": None, "aviso": "", "accion": "esperar"}
        if r["cancelables"]:
            return {"paso": None, "aviso": "", "accion": "cancelar"}
        if paso == "retirando":
            if r["salidos"]:
                return {"paso": "publicado" if r["todas_publicadas"] else "no_publicar",
                        "aviso": "ya_salio", "accion": ""}
            return {"paso": "no_publicar", "aviso": "", "accion": ""}
        # reprogramando: todo cancelado o salido -> programar la fecha nueva
        if r["salidos"]:
            return {"paso": "programado", "aviso": "ya_salio", "accion": ""}
        return {"paso": None, "aviso": "", "accion": "programar"}
    if paso == "espera_ok":
        if r["todas_publicadas"]:
            return {"paso": "publicado", "aviso": "", "accion": ""}
        if r["vivas"] and not r["sin_envio"]:
            # se publicó desde Publicar a mano: ya no espera nada
            return {"paso": "programado", "aviso": "", "accion": ""}
        return {"paso": None, "aviso": "", "accion": ""}
    # publicando / programado / fallo
    if not r["alguno"]:
        if paso == "publicando":
            return {"paso": None, "aviso": "", "accion": "sin_envios"}
        return {"paso": None, "aviso": "", "accion": ""}
    if r["todas_publicadas"]:
        return {"paso": "publicado", "aviso": "", "accion": ""}
    if r["alguna_fallida"]:
        return {"paso": "fallo", "aviso": "fallido", "accion": ""}
    if r["comprobar"]:
        return {"paso": None if paso != "publicando" else "programado",
                "aviso": "comprobar", "accion": ""}
    if r["todas_canceladas"] and paso in ("publicando", "programado"):
        return {"paso": "espera_ok", "aviso": "cancelado_en_publicar", "accion": ""}
    if r["sin_envio"] and r["vivas"]:
        return {"paso": "programado" if paso != "fallo" else None, "aviso": "faltan_redes",
                "accion": ""}
    if paso == "publicando":
        return {"paso": "programado", "aviso": "", "accion": ""}
    if paso == "fallo" and not r["alguna_fallida"]:
        return {"paso": "programado", "aviso": "", "accion": ""}
    return {"paso": None, "aviso": "", "accion": ""}


# ================================================================ LO QUE SE ENSEÑA

ETIQUETAS = {
    "haciendo": "🤖 haciendo el vídeo",
    "esperando_turno": "🤖 en cola para hacerse",
    "espera_ok": "⏳ espera tu OK",
    "detenido": "⚠ detenido: mira qué pasa",
    "programado": "📅 programado",
    "publicando": "📤 subiéndolo",
    "cambiando": "🔁 cambiando la fecha",
    "retirando": "✗ quitándolo de Upload-Post",
    "publicado": "✓ publicado",
    "no_publicar": "✗ no se publica",
    "fallo": "⚠ falló la subida",
    "comprobar": "⚠ no sé si salió",
}


def estado_vivo(ficha, envios=()):
    """La etiqueta que ven las TRES pantallas (Parrilla, móvil y piloto),
    calculada de la ficha y de los envíos: nunca una copia guardada.
    -> {"clave", "texto", "hueco", "hueco_texto"}"""
    a = (ficha or {}).get("auto") or {}
    paso = a.get("paso") or "preparando"
    r = resumen_envios(a, envios)
    hueco = a.get("hueco") or ""
    if paso == "preparando":
        estado = (ficha or {}).get("estado")
        if estado == "en_cola":
            clave = "esperando_turno"
        elif estado == "trabajando":
            clave = "haciendo"
        elif estado in ("listo", "revisar"):
            clave = "haciendo"          # el vigía lo pasa enseguida a su paso
        elif estado == "cancelado":
            clave = "no_publicar"
        else:
            clave = "detenido"
    elif paso in ("programado", "publicando") and r["todas_publicadas"]:
        clave = "publicado"
    elif paso in ("programado", "fallo") and r["alguna_fallida"]:
        clave = "fallo"
    elif paso in ("programado", "publicando", "retirando", "reprogramando") and r["comprobar"]:
        clave = "comprobar"
    elif paso == "reprogramando":
        clave = "cambiando"
    else:
        clave = {"espera_ok": "espera_ok", "publicando": "publicando",
                 "programado": "programado", "retirando": "retirando",
                 "publicado": "publicado", "no_publicar": "no_publicar",
                 "fallo": "fallo"}.get(paso, "detenido")
    texto = ETIQUETAS[clave]
    if clave in ("programado", "espera_ok", "cambiando") and hueco:
        texto += (" para el " if clave == "programado" else " · iría el ") + bonito(hueco)
    return {"clave": clave, "texto": texto, "hueco": hueco, "hueco_texto": bonito(hueco)}


def huella(valor):
    """Una huella corta de un texto u objeto (para el «antes» de los textos)."""
    crudo = json.dumps(valor, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()[:16]


# ================================================================ TELEGRAM (los textos)

def texto_aviso(tipo, titulo, proyecto, enlace, extra=""):
    """El mensaje corto de Telegram. Sin botones: todo se decide en la página."""
    cab = {
        "espera_ok": "⏳ Vídeo listo: espera tu OK",
        "razon": "⚠ Vídeo listo, pero no lo publico solo",
        "programado": "📅 Programado",
        "publicado": "✓ Publicado",
        "no_publicar": "✗ No se publica",
        "movido": "🔁 Nueva hora",
        "fallo": "⚠ Falló una subida",
        "comprobar": "⚠ No sé si salió",
        "detenido": "⚠ El piloto se detuvo",
        "guiones": "📝 Se acaban los guiones",
        "freno": "⏸ El piloto automático espera",
        "antes": "⚠ No empiezo el siguiente vídeo",
        "cupo": "⏸ Esperando cupo de Claude",
        "prueba": "✓ Prueba del Studio",
    }.get(tipo, "Aviso del Studio")
    lineas = [cab, f"{titulo}" + (f" · {proyecto}" if proyecto else "")]
    if extra:
        lineas.append(str(extra))
    if enlace:
        lineas.append(enlace)
    return "\n".join(l for l in lineas if l)[:3500]

"""EL PILOTO: «Hacer el vídeo completo» desde un guion de la Parrilla.

Rama `video-completo` (pedido del dueño, 23 y 28-10-2026). Es el nivel 1 del
piloto automático: un botón en la Parrilla que, sin más clics, crea el vídeo
con su estilo, escribe el guion, pone la voz, dibuja las imágenes con el
revisor detrás (y rehace lo marcado hasta un tope), monta el vídeo en la cola
de montaje y deja el PAQUETE DE PUBLICACIÓN: títulos, descripciones y hashtags
por red y la portada. NO publica nada: eso sigue siendo de una persona
(`publicar.py`, «espera tu OK»).

AQUÍ SOLO VIVEN LOS DATOS Y LAS DECISIONES. Lo que corre cada paso es el MISMO
código que corre su botón, y vive en `app.py` (bloque PILOTO): aquí no se
importa ningún motor, igual que `recetas.py`. Se parte así para que esto se
pueda probar sin servidor (`prueba_piloto.py`) y para que no haya un camino
«automático» y otro «a mano» que se separen con el tiempo.

    ajustes(raiz)                     el interruptor, los topes y las portadas
    guardar_ajustes(raiz, cambios)
    encolar(raiz, pedido)             un vídeo a la cola -> su ficha
    listar(raiz) / leer(raiz, vid)
    cambiar(raiz, vid, **campos)      lo usa app.py mientras trabaja
    quitar(raiz, vid)                 solo lo que aún no ha empezado
    siguientes(raiz, libres)          los que tocan arrancar ahora
    al_arrancar(raiz)                 lo que el servicio dejó a medias
    decidir(modo, marcadas, planos, umbral)   ¿se sigue o se para?

DÓNDE VIVE
----------
`<proyectos>/_sistema/piloto/piloto.json`, FUERA de la carpeta de cada vídeo,
como la Parrilla y Publicar: nada de aquí entra en ninguna firma (regla 1 de
CLAUDE.md) y `asvs actualizar` no lo toca. Las portadas candidatas, en
`<proyectos>/_sistema/piloto/portadas/<vid>/`.

EL INTERRUPTOR (decisión del dueño, 28-10-2026)
-----------------------------------------------
Qué hace el piloto si, después del tope de rehacer, quedan imágenes que el
revisor sigue marcando:

    seguir   monta igual y las deja marcadas para revisar.
    parar    se detiene antes de montar y avisa. No se gasta nada más.
    mezcla   para si las marcadas pasan del umbral (25 % por defecto) y si
             no, sigue y marca. Es el de fábrica.

Un FALLO de verdad (el guion o la voz que no salen, un error) para siempre: no
hay vídeo que montar. Y en los tres casos el piloto pasa al siguiente vídeo de
la cola: uno con problemas no bloquea a los demás.

Los vistos buenos que un vídeo pide antes de dibujar (la imagen base del tipo
de relato, el guion visual) los da el piloto en «seguir» y en «mezcla», y quedan
apuntados en «Para revisar»; en «parar», se detiene y los pide.

LOS ESTADOS DE UN VÍDEO DEL PILOTO
----------------------------------
    en_cola        esperando su turno (o el cupo de Claude)
    trabajando     en marcha
    listo          vídeo montado y paquete listo, sin nada que revisar
    revisar        listo, pero con cosas apuntadas para mirar
    parado         se detuvo y espera tu decisión («Seguir igualmente»)
    error          algo falló; «Reintentar» sigue desde donde iba
    interrumpido   el servicio se reinició a mitad; «Reintentar» sigue
    cancelado      lo paraste tú
"""
import os
import re
import sys
import threading
import uuid

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ_ESTUDIO not in sys.path:
    sys.path.insert(0, RAIZ_ESTUDIO)
from nucleo.proyecto import ahora, escribir_json, leer_json  # noqa: E402


class ErrorPiloto(ValueError):
    """Lo pedido no se puede hacer, con el motivo en castellano. `codigo` HTTP."""

    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = int(codigo)


MODOS_FALLO = ("seguir", "parar", "mezcla")
NOMBRES_MODO = {"seguir": "Seguir y marcar", "parar": "Detenerse y avisar",
                "mezcla": "Mezcla con regla"}
PORTADAS = ("ambas", "plano", "ia")
FORMATOS = ("vertical", "horizontal")

ESTADOS = ("en_cola", "trabajando", "listo", "revisar", "parado", "error",
           "interrumpido", "cancelado")
#: Los que ocupan un hueco de «a la vez».
EN_MARCHA = ("trabajando",)
#: Los que se pueden retomar con «Seguir igualmente» / «Reintentar».
RETOMABLES = ("parado", "error", "interrumpido", "cancelado")
#: Los que van a la bandeja «Necesita revisión».
A_REVISAR = ("revisar", "parado", "error", "interrumpido")
#: Los que ya no van a hacer nada más solos.
TERMINADOS = ("listo", "revisar", "parado", "error", "interrumpido", "cancelado")

NOMBRES_ESTADO = {
    "en_cola": "En cola", "trabajando": "Trabajando", "listo": "Listo para publicar",
    "revisar": "Listo, con cosas que revisar", "parado": "Detenido: espera tu decisión",
    "error": "Falló", "interrumpido": "Interrumpido (se reinició el servicio)",
    "cancelado": "Parado por ti",
}

#: Las etapas que se ven en la ficha, en orden. `etapa` de cada vídeo es una.
ETAPAS = (
    ("crear", "Crear el vídeo"), ("guion", "Guion"), ("voz", "Voz"),
    ("vistos", "Vistos buenos"), ("imagenes", "Imágenes y revisor"),
    ("decidir", "Decidir"), ("montaje", "Montaje"), ("textos", "Títulos y textos"),
    ("portadas", "Portadas"), ("fin", "Listo"),
)
ETAPAS_IDS = tuple(e for e, _n in ETAPAS)

AJUSTES_DEFECTO = {
    # el interruptor
    "si_falla": "mezcla",
    # con «mezcla»: para si las marcadas pasan de este % de los planos
    "umbral_pct": 25,
    # rondas de «revisar y rehacer» después de dibujar (el tope de rehacer)
    "vueltas": 2,
    # lo más que puede costar un vídeo, previsto antes de empezar
    "tope_usd": 5.0,
    # cuántos vídeos trabajan a la vez (imágenes y montaje van igual por turnos)
    "a_la_vez": 2,
    # opción C del dueño: una portada con un plano (gratis) y otra con IA
    "portadas": "ambas",
    # calidad de la portada hecha con IA (se paga una imagen)
    "calidad_portada_ia": "low",
    # no arrancar un vídeo nuevo con el cupo de Claude por encima de esto
    "cupo_max_pct": 90,
}
LIMITES = {"umbral_pct": (1, 100), "vueltas": (1, 5), "tope_usd": (0.1, 100.0),
           "a_la_vez": (1, 5), "cupo_max_pct": (50, 100)}

#: Lo más que se guarda en la lista: los terminados más viejos se olvidan.
MAX_VIDEOS = 300

_LOCK = threading.RLock()


# ================================================================ DÓNDE VIVE

def carpeta(raiz):
    return os.path.join(raiz, "_sistema", "piloto")


def _ruta(raiz):
    return os.path.join(carpeta(raiz), "piloto.json")


def carpeta_portadas(raiz, vid):
    _vid(vid)
    return os.path.join(carpeta(raiz), "portadas", vid)


def _vid(vid):
    vid = str(vid or "")
    if not re.fullmatch(r"[a-f0-9]{12}", vid):
        raise ErrorPiloto(f"vídeo del piloto no válido: {vid!r}", 404)
    return vid


def _leer(raiz):
    """ESTRICTO, como la Parrilla: un fichero ilegible es un 503, no una cola
    vacía. Sin esto el siguiente guardado escribiría una lista vacía encima."""
    try:
        datos = leer_json(_ruta(raiz), {}, estricto=True) or {}
    except (ValueError, OSError) as fallo:
        raise ErrorPiloto(f"la cola del piloto no se puede leer ({fallo}). No se ha "
                          "tocado nada: avisa para revisar _sistema/piloto/piloto.json",
                          503) from None
    if not isinstance(datos, dict):
        datos = {}
    if not isinstance(datos.get("videos"), list):
        datos["videos"] = []
    if not isinstance(datos.get("ajustes"), dict):
        datos["ajustes"] = {}
    return datos


def _guardar(raiz, datos):
    # se olvidan los terminados más viejos si la lista crece sin fin
    videos = datos.get("videos") or []
    if len(videos) > MAX_VIDEOS:
        sobran = len(videos) - MAX_VIDEOS
        quedan = []
        for v in videos:
            if sobran > 0 and v.get("estado") in TERMINADOS:
                sobran -= 1
                continue
            quedan.append(v)
        datos["videos"] = quedan
    escribir_json(_ruta(raiz), datos)


# ================================================================ AJUSTES

def _limpio(clave, valor):
    if clave == "si_falla":
        valor = str(valor or "").strip().lower()
        if valor not in MODOS_FALLO:
            raise ErrorPiloto(f"«si falla»: {', '.join(MODOS_FALLO)}")
        return valor
    if clave == "portadas":
        valor = str(valor or "").strip().lower()
        if valor not in PORTADAS:
            raise ErrorPiloto(f"«portadas»: {', '.join(PORTADAS)}")
        return valor
    if clave == "calidad_portada_ia":
        valor = str(valor or "").strip().lower()
        if valor not in ("low", "medium", "high"):
            raise ErrorPiloto("la calidad de la portada con IA: low, medium o high")
        return valor
    if clave in LIMITES:
        menor, mayor = LIMITES[clave]
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ErrorPiloto(f"«{clave}» tiene que ser un número") from None
        if numero != numero:            # NaN
            raise ErrorPiloto(f"«{clave}» tiene que ser un número")
        numero = max(menor, min(mayor, numero))
        return round(numero, 2) if clave == "tope_usd" else int(round(numero))
    raise ErrorPiloto(f"ajuste desconocido: {clave}")


def ajustes(raiz):
    """Los ajustes del piloto: los guardados sobre los de fábrica."""
    with _LOCK:
        guardados = _leer(raiz).get("ajustes") or {}
    salida = dict(AJUSTES_DEFECTO)
    for clave, valor in guardados.items():
        if clave in AJUSTES_DEFECTO:
            try:
                salida[clave] = _limpio(clave, valor)
            except ErrorPiloto:
                pass                          # uno roto vuelve al de fábrica
    return salida


def guardar_ajustes(raiz, cambios):
    """Cambia los ajustes que vengan. -> los ajustes de ahora"""
    if not isinstance(cambios, dict):
        raise ErrorPiloto("los ajustes van en un objeto")
    nuevos = {}
    for clave, valor in cambios.items():
        if clave not in AJUSTES_DEFECTO:
            raise ErrorPiloto(f"ajuste desconocido: {clave}")
        nuevos[clave] = _limpio(clave, valor)
    with _LOCK:
        datos = _leer(raiz)
        datos["ajustes"] = dict(datos.get("ajustes") or {}, **nuevos)
        _guardar(raiz, datos)
    return ajustes(raiz)


def ajustes_del_video(raiz, ficha):
    """Los ajustes con los que trabaja ESE vídeo: los que se fijaron al
    encolarlo (lo que se eligió en su diálogo), sobre los generales."""
    base = ajustes(raiz)
    propios = (ficha or {}).get("ajustes") or {}
    for clave, valor in propios.items():
        if clave in base:
            try:
                base[clave] = _limpio(clave, valor)
            except ErrorPiloto:
                pass
    return base


# ================================================================ LA DECISIÓN

def decidir(modo, marcadas, planos, umbral_pct=25):
    """¿Se monta o se para? -> ("seguir"|"parar", porque)

    `marcadas` son las imágenes que el revisor sigue marcando después del tope
    de rehacer; `planos`, cuántas imágenes tiene el vídeo."""
    marcadas = max(0, int(marcadas or 0))
    planos = max(0, int(planos or 0))
    if marcadas == 0:
        return "seguir", "el revisor no ha dejado ninguna imagen marcada"
    cuantas = f"{marcadas} {'imagen sigue' if marcadas == 1 else 'imágenes siguen'} marcada" \
              + ("" if marcadas == 1 else "s")
    if modo == "seguir":
        return "seguir", f"{cuantas}: se monta igual y quedan para revisar"
    if modo == "parar":
        return "parar", f"{cuantas} después de rehacer: se para antes de montar"
    pct = (100.0 * marcadas / planos) if planos else 100.0
    umbral = max(1, int(umbral_pct or 25))
    if pct > umbral:
        return "parar", (f"{cuantas} ({pct:.0f} % de {planos}), más del {umbral} %: "
                         "este vídeo no merece más gasto sin que lo mires")
    return "seguir", (f"{cuantas} ({pct:.0f} % de {planos}), no pasa del {umbral} %: "
                      "se monta y quedan para revisar")


def da_vistos_buenos(modo):
    """Si el piloto aprueba solo la imagen base y el guion visual."""
    return modo in ("seguir", "mezcla")


# ================================================================ LA COLA

def _nueva(pedido):
    p = pedido if isinstance(pedido, dict) else {}
    cid = str(p.get("cid") or "").strip()
    gid = str(p.get("gid") or "").strip()
    estilo = str(p.get("estilo") or "").strip()
    if not gid:
        raise ErrorPiloto("falta el guion")
    if not estilo:
        raise ErrorPiloto("elige con qué estilo")
    try:
        indice = int(p.get("indice") or 0)
    except (TypeError, ValueError):
        indice = 0
    duracion = p.get("duracion_s")
    if duracion not in (None, ""):
        try:
            duracion = int(float(duracion))
        except (TypeError, ValueError):
            raise ErrorPiloto("la duración va en segundos") from None
        if not 5 <= duracion <= 3600:
            raise ErrorPiloto("la duración tiene que estar entre 5 s y 1 hora")
    else:
        duracion = None
    formato = str(p.get("formato") or "").strip().lower() or None
    if formato and formato not in FORMATOS:
        raise ErrorPiloto("el formato es «vertical» u «horizontal»")
    propios = {}
    for clave, valor in (p.get("ajustes") or {}).items() if isinstance(p.get("ajustes"), dict) else ():
        if clave in AJUSTES_DEFECTO and clave != "a_la_vez":
            propios[clave] = _limpio(clave, valor)
    return {
        "id": uuid.uuid4().hex[:12], "cid": cid, "gid": gid, "indice": indice,
        "estilo": estilo[:120], "titulo": str(p.get("titulo") or "")[:120],
        "duracion_s": duracion, "formato": formato, "ajustes": propios,
        "estado": "en_cola", "etapa": "crear", "pid": "", "nombre": "",
        "trabajo": "", "mensaje": "esperando su turno", "porque": "", "donde": "",
        "revisar": [], "avisos": [], "portadas": [], "portada_puesta": "",
        "redes": [], "coste_usd": None, "previsto_usd": None,
        "creado": ahora(), "empezado": "", "terminado": "", "intentos": 0,
        "forzar_seguir": False,
    }


def encolar(raiz, pedido):
    """Un vídeo a la cola. -> su ficha. El mismo guion no entra dos veces a la
    vez: un segundo clic sería pagar dos veces el mismo vídeo."""
    ficha = _nueva(pedido)
    with _LOCK:
        datos = _leer(raiz)
        for v in datos["videos"]:
            if (v.get("gid") == ficha["gid"] and v.get("cid") == ficha["cid"]
                    and int(v.get("indice") or 0) == ficha["indice"]
                    and v.get("estado") in ("en_cola", "trabajando")):
                raise ErrorPiloto("ese guion ya está en el piloto: mira la cola", 409)
        datos["videos"].append(ficha)
        _guardar(raiz, datos)
    return dict(ficha)


def listar(raiz):
    with _LOCK:
        return [dict(v) for v in _leer(raiz)["videos"]]


def leer(raiz, vid):
    _vid(vid)
    for v in listar(raiz):
        if v.get("id") == vid:
            return v
    raise ErrorPiloto("ese vídeo ya no está en el piloto", 404)


#: Lo único que se puede cambiar de una ficha desde fuera de este módulo.
CAMPOS = ("estado", "etapa", "pid", "nombre", "trabajo", "mensaje", "porque", "donde",
          "revisar", "avisos", "portadas", "portada_puesta", "redes", "coste_usd",
          "previsto_usd", "empezado", "terminado", "intentos", "forzar_seguir")


def cambiar(raiz, vid, **campos):
    """Cambia campos de una ficha. -> la ficha nueva"""
    _vid(vid)
    malos = [c for c in campos if c not in CAMPOS]
    if malos:
        raise ErrorPiloto(f"campos que no se cambian: {', '.join(malos)}", 500)
    if "estado" in campos and campos["estado"] not in ESTADOS:
        raise ErrorPiloto(f"estado desconocido: {campos['estado']}", 500)
    if "etapa" in campos and campos["etapa"] not in ETAPAS_IDS:
        raise ErrorPiloto(f"etapa desconocida: {campos['etapa']}", 500)
    with _LOCK:
        datos = _leer(raiz)
        for v in datos["videos"]:
            if v.get("id") == vid:
                v.update(campos)
                _guardar(raiz, datos)
                return dict(v)
    raise ErrorPiloto("ese vídeo ya no está en el piloto", 404)


def apuntar_revision(raiz, vid, que, donde=""):
    """Añade una cosa a «Para revisar» de un vídeo (sin repetirla)."""
    linea = {"que": str(que)[:300], "donde": str(donde or "")[:80]}
    with _LOCK:
        datos = _leer(raiz)
        for v in datos["videos"]:
            if v.get("id") == vid:
                lista = list(v.get("revisar") or [])
                if linea not in lista:
                    lista.append(linea)
                v["revisar"] = lista[-30:]
                _guardar(raiz, datos)
                return dict(v)
    raise ErrorPiloto("ese vídeo ya no está en el piloto", 404)


def quitar(raiz, vid):
    """Quita un vídeo de la lista. Uno en marcha no: primero se para."""
    _vid(vid)
    with _LOCK:
        datos = _leer(raiz)
        for v in datos["videos"]:
            if v.get("id") == vid:
                if v.get("estado") in EN_MARCHA:
                    raise ErrorPiloto("está trabajando: páralo antes de quitarlo", 409)
                datos["videos"] = [x for x in datos["videos"] if x.get("id") != vid]
                _guardar(raiz, datos)
                return dict(v)
    raise ErrorPiloto("ese vídeo ya no está en el piloto", 404)


def preparar_reintento(raiz, vid, forzar_seguir=False):
    """«Seguir igualmente» / «Reintentar»: vuelve a la cola desde donde iba.
    Con `forzar_seguir`, la próxima decisión del interruptor se salta (lo has
    mirado tú). -> la ficha"""
    _vid(vid)
    with _LOCK:
        datos = _leer(raiz)
        for v in datos["videos"]:
            if v.get("id") == vid:
                if v.get("estado") not in RETOMABLES:
                    raise ErrorPiloto("este vídeo no está parado: no hay nada que retomar", 409)
                v.update(estado="en_cola", mensaje="esperando su turno (retomado)",
                         porque="", donde="", trabajo="", terminado="",
                         forzar_seguir=bool(forzar_seguir) or bool(v.get("forzar_seguir")))
                _guardar(raiz, datos)
                return dict(v)
    raise ErrorPiloto("ese vídeo ya no está en el piloto", 404)


def siguientes(raiz, a_la_vez=None):
    """Los vídeos que tocan arrancar ahora, por orden de llegada. -> [fichas]"""
    with _LOCK:
        datos = _leer(raiz)
    tope = int(a_la_vez or ajustes(raiz)["a_la_vez"])
    en_marcha = sum(1 for v in datos["videos"] if v.get("estado") in EN_MARCHA)
    libres = max(0, tope - en_marcha)
    return [dict(v) for v in datos["videos"] if v.get("estado") == "en_cola"][:libres]


def al_arrancar(raiz):
    """Lo que el servicio dejó «trabajando» al reiniciarse pasa a interrumpido.

    NO se retoma solo: retomar puede gastar dinero, y después de un reinicio
    eso lo decide una persona con «Reintentar» (que sigue donde iba, sin
    volver a pagar lo hecho). -> cuántos"""
    cuantos = 0
    with _LOCK:
        try:
            datos = _leer(raiz)
        except ErrorPiloto:
            return 0
        for v in datos["videos"]:
            if v.get("estado") in EN_MARCHA:
                v.update(estado="interrumpido", trabajo="", terminado=ahora(),
                         mensaje="el servicio se reinició mientras trabajaba")
                cuantos += 1
        if cuantos:
            _guardar(raiz, datos)
    return cuantos


def resumen(raiz):
    """Para la pantalla: los vídeos, cuántos hay en cada estado y los ajustes."""
    videos = listar(raiz)
    cuenta = {e: 0 for e in ESTADOS}
    for v in videos:
        cuenta[v.get("estado") or "en_cola"] = cuenta.get(v.get("estado") or "en_cola", 0) + 1
    return {
        "videos": list(reversed(videos)),
        "cuenta": cuenta,
        "a_revisar": sum(cuenta.get(e, 0) for e in A_REVISAR),
        "ajustes": ajustes(raiz),
        "modos": [{"id": m, "nombre": NOMBRES_MODO[m]} for m in MODOS_FALLO],
        "estados": NOMBRES_ESTADO, "etapas": [{"id": e, "nombre": n} for e, n in ETAPAS],
        "limites": {k: list(v) for k, v in LIMITES.items()},
    }

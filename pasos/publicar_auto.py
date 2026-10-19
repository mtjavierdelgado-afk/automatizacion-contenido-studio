"""LAS CIFRAS AUTOMATICAS (rama `publicar-mas`, 18-10-2026).

Hasta ahora las cifras de lo publicado se pedian solo al pulsar «Actualizar».
Esto las pide solas, con la frecuencia que se elija en Publicar → Cuentas y
ajustes, y APAGADAS de fabrica: nadie ha pedido gastar consultas hasta que lo
encienda (la pantalla sugiere «una vez al día, los últimos 30 posts»).

Que gasta, y por eso se enseña antes de confirmar (`coste`):

- **Dinero: nada.** Las consultas de cifras de Upload-Post van incluidas en sus
  planes de pago; no gastan subidas ni llaman a Claude.
- **Consultas del cupo de Upload-Post** (100 cada 5 minutos por cuenta): una por
  envio en vivo (los ultimos N). Los seguidores (una por proyecto) y la lectura
  guardada no gastan del cupo (docs.upload-post.com/api/get-analytics). Para no comerse el cupo de quien
  pulse «Actualizar» a la vez, las consultas van separadas ESPACIO_S segundos
  (como mucho 60 de las 100 en cada 5 minutos).

La vuelta corre en un hilo del propio servicio (`arrancar`, desde `app.py`), no
detras del proxy, asi que no tiene el tope de 60 s de una peticion. Nada de esto
entra en la firma de ningun video.

Fichero: `<proyectos>/_sistema/publicar/metricas_auto.json`
    {"frecuencia", "hora", "posts", "activada_al", "ultima": {...}, "historial": [...]}
"""
from __future__ import annotations

import datetime as dt
import os
import threading
import time

try:                                    # el cerrojo entre procesos (Linux); en
    import fcntl                        # Windows basta el del proceso
except ImportError:                     # pragma: no cover
    fcntl = None

import publicar as P          # noqa: E402  (pasos/ en sys.path, como en app.py)
from nucleo.proyecto import escribir_json, leer_json  # noqa: E402

#: frecuencia -> horas entre vueltas (0 = apagada)
FRECUENCIAS = {"apagada": 0, "semanal": 24 * 7, "diaria": 24, "12h": 12, "6h": 6}
NOMBRE_FRECUENCIA = {"apagada": "apagadas", "semanal": "una vez a la semana (los lunes)",
                     "diaria": "una vez al día", "12h": "cada 12 horas", "6h": "cada 6 horas"}
POSTS = (10, 30, 60, 100)
DEFECTO = {"frecuencia": "apagada", "hora": "04:00", "posts": 30}
#: lo que la pantalla propone al encenderlas (lo que pidio el dueño)
SUGERIDO = {"frecuencia": "diaria", "hora": "04:00", "posts": 30}

#: El cupo de Upload-Post para las cifras: 100 consultas cada 5 minutos.
CUPO = 100
CUPO_VENTANA_MIN = 5
#: Pausa entre consultas en vivo: 5 s = 60 por cada 5 minutos, y quedan 40 para
#: quien pulse «Actualizar» mientras.
ESPACIO_S = float(os.environ.get("ESTUDIO_METRICAS_AUTO_ESPACIO") or 5)
#: Lo que se calcula que tarda una consulta (para decir cuanto dura la vuelta).
TARDA_CONSULTA_S = 3
#: Una vuelta no pasa de aqui (lo que no de tiempo, a la siguiente).
TOPE_VUELTA_S = 30 * 60
#: Cuanto se espera, como mucho, a que quien pulsa «Actualizar» termine.
ESPERA_OCUPADO_S = 120
#: Cada cuanto mira el hilo si toca vuelta.
LATIDO_S = float(os.environ.get("ESTUDIO_METRICAS_AUTO_LATIDO") or 60)
HISTORIAL = 14

_LOCK = threading.Lock()
_HILO = {"hilo": None, "parar": None}


def _ruta(raiz):
    return os.path.join(P.carpeta(raiz), "metricas_auto.json")


def _leer(raiz):
    datos = leer_json(_ruta(raiz), {}) or {}
    return datos if isinstance(datos, dict) else {}


def leer(raiz, ocultar=None):
    """La configuracion con sus valores de fabrica, lo ultimo que paso y la
    proxima vuelta. Leer no escribe nada. `ocultar`: proyectos que quien
    pregunta no puede ver (con clave y cerrados): sus avisos no salen y su
    nombre o su perfil se tapan en los demas."""
    datos = _leer(raiz)
    salida = dict(DEFECTO)
    salida.update({k: datos[k] for k in DEFECTO if k in datos})
    salida["activada_al"] = datos.get("activada_al") or ""
    salida["corriendo"] = en_marcha(raiz)
    ultima = dict(datos.get("ultima") or {}) or None
    # una vuelta sin terminar y sin nadie corriendola: el servicio se reinicio
    if ultima and not ultima.get("fin") and not salida["corriendo"]:
        ultima["cortada"] = True
    salida["ultima"] = ultima
    salida["historial"] = list(datos.get("historial") or [])[:HISTORIAL]
    prox = proxima(salida)
    salida["proxima"] = P._iso_lima(prox) if prox else ""
    if ocultar:
        tapar = _tapador(raiz, ocultar)
        salida["ultima"] = tapar(salida["ultima"])
        salida["historial"] = [tapar(x) for x in salida["historial"]]
    return salida


def _texto_aviso(aviso):
    return aviso.get("texto", "") if isinstance(aviso, dict) else str(aviso or "")


def _tapador(raiz, ocultar):
    ocultar = set(ocultar)
    nombres = set()
    for cid in ocultar:
        nombres.add(cid)
        perfil = P.ajustes_de(raiz, cid).get("perfil")
        if perfil:
            nombres.add(perfil)
    nombres = sorted((n for n in nombres if n), key=len, reverse=True)

    def tapar(vuelta):
        if not vuelta:
            return vuelta
        vuelta = dict(vuelta)
        avisos = []
        for aviso in vuelta.get("errores") or []:
            if isinstance(aviso, dict) and aviso.get("proyecto") in ocultar:
                continue
            texto = _texto_aviso(aviso)
            for n in nombres:
                texto = texto.replace(n, "(un proyecto con clave)")
            avisos.append(dict(aviso, texto=texto) if isinstance(aviso, dict) else texto)
        vuelta["errores"] = avisos
        return vuelta
    return tapar


def _validar(cambios):
    limpios = {}
    if "frecuencia" in cambios:
        f = str(cambios["frecuencia"] or "").strip()
        if f not in FRECUENCIAS:
            raise P.ErrorPublicar(f"frecuencia desconocida: {f}", 400)
        limpios["frecuencia"] = f
    if "hora" in cambios:
        hora = str(cambios["hora"] or "").strip()
        try:
            hh, mm = hora.split(":")
            hh, mm = int(hh), int(mm)
            assert 0 <= hh < 24 and 0 <= mm < 60
        except (ValueError, AssertionError):
            raise P.ErrorPublicar("la hora va como 04:00", 400) from None
        limpios["hora"] = f"{hh:02d}:{mm:02d}"
    if "posts" in cambios:
        try:
            n = int(cambios["posts"])
        except (TypeError, ValueError):
            raise P.ErrorPublicar("¿cuántos posts?", 400) from None
        if n not in POSTS:
            raise P.ErrorPublicar(f"los posts van de {POSTS[0]} a {POSTS[-1]}", 400)
        limpios["posts"] = n
    return limpios


def guardar(raiz, cambios):
    """Guarda lo que cambia. Encenderla (o cambiar la frecuencia o la hora)
    apunta `activada_al`: la primera vuelta es la proxima hora elegida, no ya."""
    limpios = _validar(cambios or {})
    with P._lock("metricas_auto"):
        datos = _leer(raiz)
        antes = {k: datos.get(k, DEFECTO[k]) for k in DEFECTO}
        datos.update(limpios)
        despues = {k: datos.get(k, DEFECTO[k]) for k in DEFECTO}
        if (antes["frecuencia"], antes["hora"]) != (despues["frecuencia"], despues["hora"]):
            datos["activada_al"] = P._iso_lima()
        os.makedirs(P.carpeta(raiz), exist_ok=True)
        escribir_json(_ruta(raiz), datos)
    if antes != despues:
        P._log("metricas_auto_ajustes", {"antes": antes, "despues": despues})
    return leer(raiz)


# ------------------------------------------------------------------ cuando

def proxima(config, ahora=None):
    """El momento de la siguiente vuelta (datetime de Lima), o None si estan
    apagadas. Las vueltas caen en huecos fijos desde la hora elegida (con «cada
    6 horas» y las 04:00: 04, 10, 16 y 22); la semanal, los lunes. Toca el
    primer hueco DESPUES de la ultima vuelta y de cuando se encendio."""
    horas = FRECUENCIAS.get(config.get("frecuencia") or "apagada", 0)
    if not horas:
        return None
    ahora = ahora or P.ahora_lima()
    try:
        hh, mm = (int(x) for x in str(config.get("hora") or "04:00").split(":"))
    except ValueError:
        hh, mm = 4, 0
    referencias = [P._leer_momento(config.get("activada_al"))]
    ultima = config.get("ultima") or {}
    referencias.append(P._leer_momento(ultima.get("empezo")))
    referencias = [r for r in referencias if r]
    desde = max(referencias) if referencias else ahora
    ancla = desde.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if horas == 24 * 7:
        ancla -= dt.timedelta(days=ancla.weekday())        # el lunes de esa semana
    paso = dt.timedelta(hours=horas)
    while ancla > desde:
        ancla -= paso
    while ancla <= desde:
        ancla += paso
    return ancla


def _ruta_cerrojo(raiz):
    return os.path.join(P.carpeta(raiz), "metricas_auto.lock")


def _coger_cerrojo(raiz):
    """El cerrojo de la vuelta ENTRE PROCESOS (dos servicios con la misma carpeta
    de proyectos no hacen la vuelta dos veces). -> el fichero abierto, o None si
    lo tiene otro. Lo suelta el sistema si el proceso muere: una vuelta cortada
    por un reinicio no deja nada bloqueado."""
    if fcntl is None:
        return True
    os.makedirs(P.carpeta(raiz), exist_ok=True)
    fh = open(_ruta_cerrojo(raiz), "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def _soltar_cerrojo(fh):
    if fh is True or fh is None:
        return
    try:
        fcntl.flock(fh, fcntl.LOCK_UN)
    finally:
        fh.close()


def en_marcha(raiz):
    """Si hay una vuelta corriendo ahora, en este proceso o en otro."""
    if _LOCK.locked():
        return True
    fh = _coger_cerrojo(raiz)
    if fh is None:
        return True
    _soltar_cerrojo(fh)
    return False


# ------------------------------------------------------------------ coste

def _publicados(raiz):
    """[(momento, id de envio, [pid])] de lo publicado por Upload-Post que da
    cifras, de lo mas nuevo a lo mas viejo. De TODOS los proyectos: la vuelta
    corre en el servidor, no la ve nadie en concreto."""
    lotes = P._lotes_publicados(raiz, P._videos_con_ficha(raiz))
    filas = []
    for lote, envios in lotes.items():
        momentos = [P._leer_momento(e.get("cuando") or e.get("actualizado") or e.get("creado"))
                    for _p, e in envios]
        momentos = [m for m in momentos if m]
        filas.append((max(momentos) if momentos else None, lote,
                      sorted({pid for pid, _e in envios})))
    filas.sort(key=lambda x: (x[0] is not None, x[0] or 0), reverse=True)
    return filas


def _proyectos_con_cuentas(raiz):
    """Los proyectos a los que se les pueden pedir seguidores (con perfil y
    con «Ver cuentas» hecho alguna vez)."""
    salida = []
    for cid, a in P.todos_los_ajustes(raiz).items():
        if a.get("perfil") and a.get("cuentas_vistas") and any((a.get("cuentas") or {}).values()):
            salida.append(cid)
    return salida


def coste(raiz, config=None):
    """Lo que gastaria una configuracion, para enseñarlo ANTES de confirmar.
    `config` sin guardar (lo que se esta eligiendo) o la guardada."""
    actual = leer(raiz)
    config = dict(actual, **_validar(config or {}))
    publicados = _publicados(raiz)
    perfiles = len(_proyectos_con_cuentas(raiz))
    horas = FRECUENCIAS[config["frecuencia"]]
    en_vivo = min(int(config["posts"]), len(publicados))
    # los seguidores no cuentan en el cupo, pero se enseñan aparte
    por_vuelta = en_vivo
    vueltas_dia = (24 / horas) if horas else 0
    minutos = (en_vivo * (ESPACIO_S + TARDA_CONSULTA_S) + perfiles * 10) / 60
    salida = {
        "frecuencia": config["frecuencia"], "posts": int(config["posts"]),
        "hora": config["hora"],
        "publicados": len(publicados), "en_vivo": en_vivo, "perfiles": perfiles,
        "consultas_vuelta": por_vuelta,
        "vueltas_dia": round(vueltas_dia, 2),
        "consultas_dia": round(por_vuelta * vueltas_dia, 1),
        "consultas_mes": int(round(por_vuelta * vueltas_dia * 30)),
        "minutos_vuelta": round(minutos, 1),
        "cupo": CUPO, "cupo_ventana_min": CUPO_VENTANA_MIN,
        "maximo_ventana": int(CUPO_VENTANA_MIN * 60 // (ESPACIO_S + TARDA_CONSULTA_S)) or 1,
        "dinero": 0,
    }
    salida["texto"] = texto_coste(salida)
    return salida


def texto_coste(c):
    if c["frecuencia"] == "apagada":
        return ("Apagadas: no se gasta nada. Las cifras se piden solo al pulsar "
                "«Actualizar» en Resultados.")
    partes = [
        f"Cada vuelta: {c['consultas_vuelta']} consulta(s) del cupo de Upload-Post "
        f"(los últimos {c['posts']} posts"
        + (f"; hoy hay {c['publicados']} con cifras que pedir" if c["publicados"] < c["posts"] else "")
        + ")"
        + (f", más los seguidores de {c['perfiles']} proyecto(s), que no gastan cupo"
           if c["perfiles"] else "") + ".",
        f"{NOMBRE_FRECUENCIA[c['frecuencia']].capitalize()}: unas {c['consultas_dia']:g} "
        f"consultas al día, {c['consultas_mes']} al mes.",
        f"Dinero: 0 $. Van incluidas en el plan de pago de Upload-Post; no gastan "
        f"subidas ni llaman a Claude (en el plan gratis puede que no den cifras).",
        f"El cupo es de {c['cupo']} consultas cada {c['cupo_ventana_min']} minutos; la vuelta "
        f"usa como mucho {c['maximo_ventana']} de ellas por tramo y tarda unos "
        f"{max(1, round(c['minutos_vuelta']))} min, así que «Actualizar» sigue funcionando mientras.",
    ]
    return " ".join(partes)


# ------------------------------------------------------------------ la vuelta

def correr(raiz, motivo="programada"):
    """Una vuelta entera: lo guardado (gratis), los ultimos N envios en vivo y
    los seguidores de cada proyecto. -> lo que se apunta en `ultima`."""
    if not _LOCK.acquire(blocking=False):
        return {"ocupado": True}
    try:
        cerrojo = _coger_cerrojo(raiz)
        if cerrojo is None:
            return {"ocupado": True}            # la esta haciendo otro proceso
        try:
            return _correr(raiz, motivo)
        finally:
            _soltar_cerrojo(cerrojo)
    finally:
        _LOCK.release()


def _apuntar(raiz, ultima, terminada=False):
    with P._lock("metricas_auto"):
        datos = _leer(raiz)
        previa = datos.get("ultima") or {}
        if not terminada and previa.get("empezo") and not previa.get("fin"):
            # la anterior se corto (reinicio del servicio): al historial, marcada
            datos["historial"] = ([dict(previa, cortada=True)]
                                  + list(datos.get("historial") or []))[:HISTORIAL]
        datos["ultima"] = ultima
        if terminada:
            datos["historial"] = ([ultima] + list(datos.get("historial") or []))[:HISTORIAL]
        os.makedirs(P.carpeta(raiz), exist_ok=True)
        escribir_json(_ruta(raiz), datos)


def _sigue(raiz, motivo):
    """Una vuelta programada para si se apagan mientras corre."""
    return motivo != "programada" or _leer(raiz).get("frecuencia", DEFECTO["frecuencia"]) != "apagada"


def _correr(raiz, motivo):
    config = leer(raiz)
    horas = FRECUENCIAS.get(config["frecuencia"]) or 0
    # lo mirado hace menos de media vuelta no se repite (una «Pedirlas ahora»
    # justo antes de la programada no hace que esta vuelva a pedirlo todo)
    respiro = max(P.RESPIRO_METRICAS_S, horas * 3600 / 2) if motivo == "programada" \
        else P.RESPIRO_METRICAS_S
    ultima = {"empezo": P._iso_lima(), "motivo": motivo, "posts": config["posts"],
              "consultados": 0, "actualizados": 0, "guardadas": 0, "seguidores": 0,
              "pendientes": 0, "errores": []}
    _apuntar(raiz, ultima)
    arranque = time.time()
    errores = []
    try:
        if not P.estado_clave()["puesta"]:
            errores.append("no hay clave de Upload-Post")
        else:
            publicados = _publicados(raiz)
            elegidos = publicados[:int(config["posts"])]
            pids = sorted({pid for _m, _l, lista in publicados for pid in lista})
            # 1) lo guardado: no gasta del cupo y trae la retencion de YouTube
            try:
                g = P.leer_guardadas(raiz, pids, dias=35)
                ultima["guardadas"] += int(g.get("actualizados") or 0)
                errores += list(g.get("errores") or [])
            except Exception as fallo:                          # noqa: BLE001
                errores.append(f"lectura guardada: {fallo}"[:200])
            # 2) en vivo, los ultimos N, DE UNO EN UNO: el cerrojo de las cifras
            # se coge solo para cada consulta y la pausa va fuera, asi quien
            # pulsa «Actualizar» mientras no se queda esperando toda la vuelta
            pendientes = list(elegidos)
            while pendientes:
                if time.time() - arranque > TOPE_VUELTA_S:
                    errores.append("no dio tiempo a todos los posts: siguen en la próxima")
                    break
                if not _sigue(raiz, motivo):
                    errores.append("se apagaron a mitad de la vuelta: parada")
                    break
                _m, lote, lista = pendientes[0]
                r = P.actualizar_metricas(raiz, lista, limite=1, solo={lote}, tope=60,
                                          respiro_s=respiro)
                if r.get("ocupado"):
                    if time.time() - arranque > ESPERA_OCUPADO_S and not ultima["consultados"]:
                        errores.append("las cifras las estaba pidiendo otra persona: a la próxima")
                        break
                    time.sleep(5)
                    continue
                pendientes.pop(0)
                ultima["consultados"] += int(r.get("consultados") or 0)
                ultima["actualizados"] += int(r.get("actualizados") or 0)
                errores += list(r.get("errores") or [])
                if any("demasiadas consultas" in str(e) for e in r.get("errores") or []):
                    break                       # Upload-Post pide esperar: a la proxima
                if r.get("consultados"):
                    time.sleep(ESPACIO_S)
            ultima["pendientes"] = len(pendientes)
            # 3) los seguidores de cada proyecto con cuentas (no gastan cupo)
            for cid in _proyectos_con_cuentas(raiz):
                if time.time() - arranque > TOPE_VUELTA_S or not _sigue(raiz, motivo):
                    errores.append("seguidores: no dio tiempo en esta vuelta")
                    break
                try:
                    P.actualizar_seguidores(raiz, cid)
                    ultima["seguidores"] += 1
                except P.ErrorPublicar as fallo:
                    errores.append({"texto": f"seguidores de {cid or 'sin proyecto'}: {fallo}"[:200],
                                    "proyecto": cid})
    except Exception as fallo:                                  # noqa: BLE001
        errores.append(f"la vuelta falló: {fallo}"[:300])
    # sin repetir el mismo aviso diez veces
    vistos, unicos = set(), []
    for e in errores:
        if _texto_aviso(e) not in vistos:
            vistos.add(_texto_aviso(e))
            unicos.append(e)
    ultima["errores"] = unicos[:8]
    ultima["fin"] = P._iso_lima()
    ultima["segundos"] = int(time.time() - arranque)
    _apuntar(raiz, ultima, terminada=True)
    P._log("metricas_auto", {k: ultima.get(k) for k in (
        "motivo", "consultados", "actualizados", "guardadas", "seguidores", "pendientes",
        "segundos", "errores")})
    return ultima


def correr_ya(raiz):
    """«Pedirlas ahora»: la vuelta en un hilo aparte (puede tardar minutos)."""
    if en_marcha(raiz):
        raise P.ErrorPublicar("ya hay una vuelta en marcha", 409)
    hilo = threading.Thread(target=correr, args=(raiz, "a mano"), daemon=True,
                            name="metricas-auto-ya")
    hilo.start()
    return {"lanzada": True}


# ------------------------------------------------------------------ el reloj

def toca(raiz, ahora=None):
    config = leer(raiz)
    prox = proxima(config, ahora)
    return bool(prox) and (ahora or P.ahora_lima()) >= prox and not config["corriendo"]


def _latido(raiz_de, parar):
    while not parar.wait(LATIDO_S):
        try:
            raiz = raiz_de()
            if raiz and toca(raiz):
                correr(raiz)
        except Exception as fallo:                              # noqa: BLE001
            P._log("metricas_auto_fallo", {"error": str(fallo)[:300]})


def arrancar(raiz_de):
    """Arranca el reloj (un hilo del servicio). `raiz_de`: funcion que dice la
    carpeta de proyectos. Con ESTUDIO_METRICAS_AUTO=0 no arranca."""
    if os.environ.get("ESTUDIO_METRICAS_AUTO", "1") == "0":
        return None
    if _HILO["hilo"] and _HILO["hilo"].is_alive():
        return _HILO["hilo"]
    parar = threading.Event()
    hilo = threading.Thread(target=_latido, args=(raiz_de, parar), daemon=True,
                            name="metricas-auto")
    _HILO.update(hilo=hilo, parar=parar)
    hilo.start()
    return hilo


def parar():
    if _HILO["parar"]:
        _HILO["parar"].set()

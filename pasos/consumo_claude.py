"""
El medidor de Claude: cuánto queda de la membresía y en qué se gasta.

Rama `medidor-claude` (25-10-2026). Dos cosas distintas, en dos ficheros junto
a `salud_cli.json` (la carpeta de ESTUDIO_SECRETOS, que es la que redirigen las
suites que doblan el CLI):

1. EL CUPO DE VERDAD (`cupo_claude.json`). Lo da el propio CLI: con
   `--output-format stream-json --verbose` emite, antes de contestar, una línea

       {"type": "rate_limit_event", "rate_limit_info": {
           "status": "allowed", "rateLimitType": "five_hour", "resetsAt": ...,
           "unifiedWindows": {"five_hour": {"utilization": 0.13, "resetsAt": ...},
                              "seven_day": {"utilization": 0.04, "resetsAt": ...}}}}

   (medido el 25-10-2026 con el CLI 2.1.310). `utilization` es la fracción
   usada de esa ventana y `resetsAt`, cuándo se reinicia (segundos epoch). Es
   el mismo número que enseña la web de Claude: no se estima nada. Se mide con
   UNA llamada mínima (haiku, «ok») que también cuenta, poquísimo, como consumo:
   a pedido («Medir ahora») y sola, como mucho cada CADA_S, cuando alguien mira
   el medidor y ha habido llamadas desde la última medida. Las llamadas de
   trabajo NO cambian: siguen con `--output-format json` (`cli_claude`).

2. EL REGISTRO DE CADA LLAMADA (`consumo_claude.jsonl`). `cli_claude._una_pasada`,
   el único sitio por el que pasa toda llamada, apunta aquí los tokens, el
   equivalente en dólares que da el CLI (`total_cost_usd`: lo que costaría por
   API, no lo que se paga), la tarea (`para`), el vídeo y el paso si los hay
   (`nucleo.coste.contexto_actual`) y la cuenta. Va APARTE del coste de cada
   proyecto a propósito: el asistente, la Parrilla o el chat de guiones no
   tienen proyecto, y en el coste se perdían como «sin contexto».

Nada de aquí lanza hacia quien llama: es un registro. Con ESTUDIO_SIMULAR no
se sale al CLI (la medida devuelve un cupo de mentira marcado «simulado»).
Ningún param, ninguna firma.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: A partir de qué fracción de una ventana se avisa: ojo y casi lleno.
UMBRAL_OJO = 0.70
UMBRAL_MALO = 0.90
#: Cada cuánto, como mucho, se mide sola (si ha habido consumo).
CADA_S = 15 * 60
#: Hasta cuándo se mira atrás para el resumen.
DIAS_RESUMEN = 7

INSTRUCCION = "Contesta solo con la palabra: ok"
MODELO_MEDIDA = "haiku"
ESFUERZO_MEDIDA = "low"
TIEMPO_MEDIDA_S = 60

#: Cómo se llama cada ventana en la pantalla.
NOMBRES_VENTANA = {
    "five_hour": "Ventana de 5 horas",
    "seven_day": "Semana",
    "seven_day_opus": "Semana (Opus)",
    "seven_day_sonnet": "Semana (Sonnet)",
}

#: El registro se poda al pasar de este tamaño: se queda lo de los últimos DIAS_GUARDAR.
MAX_BYTES = 4 * 1024 * 1024
DIAS_GUARDAR = 35

_LOCK = threading.Lock()
_MIDIENDO = set()
#: {clave de cuenta: epoch de su última llamada de trabajo}, para no recorrer
#: el registro entero en cada GET (`toca_medir`). Tras reiniciar, se mira el fichero.
_ULTIMA = {}


# ------------------------------------------------------------------ ficheros

def carpeta():
    """Se mira el entorno EN CADA LLAMADA (como `salud_cli.fichero`): las
    suites redirigen ESTUDIO_SECRETOS después de importar."""
    return os.environ.get("ESTUDIO_SECRETOS") or os.path.join(RAIZ_ESTUDIO, "secretos")


def fichero_registro():
    return os.path.join(carpeta(), "consumo_claude.jsonl")


def fichero_cupo():
    return os.path.join(carpeta(), "cupo_claude.json")


def simulado():
    return str(os.environ.get("ESTUDIO_SIMULAR", "")).strip().lower() in ("1", "true", "si")


def _salud():
    try:
        from . import salud_cli                           # noqa: PLC0415
    except ImportError:                                   # pasos/ suelto en sys.path
        import salud_cli                                  # noqa: PLC0415
    return salud_cli


def _cli():
    try:
        from . import cli_claude                          # noqa: PLC0415
    except ImportError:
        import cli_claude                                 # noqa: PLC0415
    return cli_claude


def clave_de(cuenta):
    try:
        return _salud().clave_de(cuenta)
    except Exception:                                     # noqa: BLE001
        return "defecto"


def etiqueta_de(cuenta):
    if isinstance(cuenta, dict):
        return str(cuenta.get("etiqueta") or "").strip() or "principal"
    return "principal"


def _contexto():
    """(proyecto, paso) de lo que se está midiendo ahora, si hay."""
    try:
        try:
            from nucleo import coste                      # noqa: PLC0415
        except ImportError:
            import sys                                    # noqa: PLC0415
            sys.path.insert(0, RAIZ_ESTUDIO)
            from nucleo import coste                      # noqa: PLC0415
        # SOLO EL DE ESTE HILO: `contexto_actual` cae al único trabajo activo
        # del proceso, y una llamada del asistente o de la Parrilla se
        # apuntaría al vídeo que estuviera trabajando a la vez
        pila = getattr(coste._LOCAL, "pila", None)
        actual = pila[-1] if pila else None
        if actual is None:
            return "", ""
        return str(actual.medidor.proyecto.id or ""), str(actual.paso or "")
    except Exception:                                     # noqa: BLE001
        return "", ""


def _numero(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _append(registro):
    ruta = fichero_registro()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    linea = json.dumps(registro, ensure_ascii=False)
    with _LOCK:
        with open(ruta, "a", encoding="utf-8") as fh:
            fh.write(linea + "\n")
        try:
            if os.path.getsize(ruta) > MAX_BYTES:
                _podar(ruta)
        except OSError:
            pass


def _podar(ruta):
    """Se queda con lo de los últimos DIAS_GUARDAR (con `_LOCK` tomado)."""
    desde = time.time() - DIAS_GUARDAR * 86400
    temporal = ruta + ".poda"
    with open(ruta, "r", encoding="utf-8") as origen, open(temporal, "w", encoding="utf-8") as destino:
        for linea in origen:
            try:
                if float(json.loads(linea).get("t") or 0) >= desde:
                    destino.write(linea)
            except (ValueError, TypeError, AttributeError):
                continue
    os.replace(temporal, ruta)


# ---------------------------------------------------------------- registrar

def anotar(cuenta, sobre, para=""):
    """Una llamada que salió bien. Nunca lanza."""
    try:
        sobre = sobre if isinstance(sobre, dict) else {}
        usage = sobre.get("usage") if isinstance(sobre.get("usage"), dict) else {}
        ajuste = sobre.get("_ajuste") if isinstance(sobre.get("_ajuste"), dict) else {}
        proyecto, paso = _contexto()
        usd = sobre.get("total_cost_usd")
        _append({
            "t": round(time.time(), 3),
            "tipo": "llamada",
            "cuenta": etiqueta_de(cuenta),
            "clave": clave_de(cuenta),
            "para": str(para or "")[:80],
            "modelo": str(ajuste.get("modelo") or sobre.get("model") or ""),
            "esfuerzo": str(ajuste.get("esfuerzo") or ""),
            "segundos": ajuste.get("segundos"),
            "entrada": _numero(usage.get("input_tokens")),
            "salida": _numero(usage.get("output_tokens")),
            "cache_creada": _numero(usage.get("cache_creation_input_tokens")),
            "cache_leida": _numero(usage.get("cache_read_input_tokens")),
            "usd": round(float(usd), 4) if isinstance(usd, (int, float)) else None,
            "proyecto": proyecto,
            "paso": paso,
        })
        if para != "medir el cupo":
            _ULTIMA[clave_de(cuenta)] = time.time()
    except Exception:                                     # noqa: BLE001 -- es un registro
        pass


def anotar_fallo(cuenta, fallo, para=""):
    """Un cupo agotado se apunta (en el registro y en el cupo). Nunca lanza."""
    try:
        estado, mensaje = _salud().clasificar(fallo)
    except Exception:                                     # noqa: BLE001
        return
    try:
        if estado != "cupo":
            # lo que vence o falla también ha gastado: se cuenta (sin tokens)
            _append({"t": round(time.time(), 3), "tipo": "fallo", "cuenta": etiqueta_de(cuenta),
                     "clave": clave_de(cuenta), "para": str(para or "")[:80], "estado": estado})
            return
        _append({"t": round(time.time(), 3), "tipo": "cupo", "cuenta": etiqueta_de(cuenta),
                 "clave": clave_de(cuenta), "para": str(para or "")[:80],
                 "mensaje": str(mensaje or "")[:300]})
        with _LOCK:
            cupos = leer_cupo()
            ficha = dict(cupos.get(clave_de(cuenta)) or {})
            ficha.update(cuenta=etiqueta_de(cuenta), estado="rejected",
                         mensaje=str(mensaje or "")[:300], agotado_en=round(time.time(), 3))
            cupos[clave_de(cuenta)] = ficha
            _escribir_cupo(cupos)
    except Exception:                                     # noqa: BLE001
        pass


def leer_registro(desde=0.0):
    """Las líneas desde `desde` (epoch). Una línea rota se salta."""
    salida = []
    try:
        with open(fichero_registro(), "r", encoding="utf-8") as fh:
            for linea in fh:
                try:
                    r = json.loads(linea)
                    if isinstance(r, dict) and float(r.get("t") or 0) >= desde:
                        salida.append(r)
                except (ValueError, TypeError):
                    continue
    except OSError:
        return []
    return salida


# --------------------------------------------------------------------- cupo

def leer_cupo():
    try:
        with open(fichero_cupo(), "r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def _escribir_cupo(datos):
    ruta = fichero_cupo()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=os.path.dirname(ruta),
                                         prefix=".cupo-", suffix=".tmp", delete=False) as fh:
            temporal = fh.name
            json.dump(datos, fh, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta)
        temporal = None
    finally:
        if temporal and os.path.exists(temporal):
            os.unlink(temporal)


def ventanas_de(info):
    """{ventana: {uso, reinicia, estado}} de un `rate_limit_info`."""
    info = info if isinstance(info, dict) else {}
    salida = {}
    unificadas = info.get("unifiedWindows")
    if isinstance(unificadas, dict):
        for nombre, v in unificadas.items():
            if isinstance(v, dict) and isinstance(v.get("utilization"), (int, float)):
                salida[str(nombre)] = {"uso": max(0.0, float(v["utilization"])),
                                       "reinicia": _numero(v.get("resetsAt")) or None,
                                       "estado": v.get("status") or ""}
    tipo = info.get("rateLimitType")
    if tipo and tipo not in salida and isinstance(info.get("utilization"), (int, float)):
        salida[str(tipo)] = {"uso": max(0.0, float(info["utilization"])),
                             "reinicia": _numero(info.get("resetsAt")) or None,
                             "estado": info.get("status") or ""}
    return salida


def leer_salida_medida(texto):
    """De la salida stream-json del CLI: (rate_limit_info | None, sobre | None)."""
    info, sobre = None, None
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea.startswith("{"):
            continue
        try:
            d = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        if d.get("type") == "rate_limit_event" and isinstance(d.get("rate_limit_info"), dict):
            info = d["rate_limit_info"]
        elif d.get("type") == "result":
            sobre = d
    return info, sobre


def _cupo_simulado():
    ahora = time.time()
    return {"status": "allowed", "rateLimitType": "five_hour",
            "unifiedWindows": {"five_hour": {"utilization": 0.42, "resetsAt": int(ahora + 7200)},
                               "seven_day": {"utilization": 0.18, "resetsAt": int(ahora + 4 * 86400)}}}


def _correr_medida(cuenta):
    """La llamada mínima, con su árbol de procesos y una carpeta de un solo uso:
    sin carpeta propia el CLI cargaba el CLAUDE.md del Studio (decenas de miles
    de tokens) en cada medida. -> (rate_limit_info, sobre)"""
    cli = _cli()
    orden = cli.construir_orden(MODELO_MEDIDA, ESFUERZO_MEDIDA,
                                herramientas_vetadas=cli.HERRAMIENTAS_VETADAS)
    i = orden.index("--output-format")
    orden[i + 1] = "stream-json"
    orden[i + 2:i + 2] = ["--verbose", "--no-session-persistence"]
    carpeta_vacia = tempfile.mkdtemp(prefix="medir_cupo_")
    try:
        proceso = subprocess.Popen(orden, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, cwd=carpeta_vacia, env=cli.entorno(cuenta),
                                   **getattr(cli, "SIN_VENTANA", {}), **getattr(cli, "GRUPO_PROPIO", {}))
        if getattr(cli, "GRUPO_PROPIO", None):
            proceso._grupo_propio = True
        try:
            crudo, _error = proceso.communicate(INSTRUCCION.encode("utf-8"), timeout=TIEMPO_MEDIDA_S)
        except subprocess.TimeoutExpired:
            cli.matar_arbol(proceso)
            raise RuntimeError(f"el CLI no contestó en {TIEMPO_MEDIDA_S} s")
        return leer_salida_medida(crudo.decode("utf-8", errors="replace"))
    finally:
        shutil.rmtree(carpeta_vacia, ignore_errors=True)


def medir(cuenta=None):
    """UNA llamada mínima para leer el cupo de esa cuenta. -> su ficha.

    Va con su propia orden (la de `cli_claude.construir_orden` con stream-json):
    las llamadas de trabajo no cambian de formato. Si ya se está midiendo esa
    cuenta (otra pestaña, la medida sola), espera a esa y devuelve su ficha."""
    clave = clave_de(cuenta)
    with _LOCK:
        ocupada = clave in _MIDIENDO
        if not ocupada:
            _MIDIENDO.add(clave)
    if ocupada:
        tope = time.time() + TIEMPO_MEDIDA_S
        while time.time() < tope:
            with _LOCK:
                if clave not in _MIDIENDO:
                    break
            time.sleep(0.3)
        return leer_cupo().get(clave) or {}
    try:
        return _medir(cuenta, clave)
    finally:
        with _LOCK:
            _MIDIENDO.discard(clave)


def _medir(cuenta, clave):
    ficha = {"cuenta": etiqueta_de(cuenta), "medido_en": round(time.time(), 3)}
    if simulado():
        info, sobre = _cupo_simulado(), None
        ficha["simulado"] = True
    else:
        try:
            info, sobre = _correr_medida(cuenta)
        except Exception as fallo:                        # noqa: BLE001
            info, sobre = None, None
            ficha["error"] = f"{type(fallo).__name__}: {str(fallo)[:200]}"
        if isinstance(sobre, dict) and not sobre.get("is_error"):
            anotar(cuenta, sobre, "medir el cupo")
    ventanas = ventanas_de(info)
    if info is not None:
        ficha.update(ventanas=ventanas, estado=info.get("status") or "",
                     tipo=info.get("rateLimitType") or "",
                     pago_extra=bool(info.get("isUsingOverage")))
    else:
        ficha.update(ventanas={}, estado="sin_dato")
        if isinstance(sobre, dict) and sobre.get("is_error"):
            ficha["error"] = str(sobre.get("result") or "")[:300]
    with _LOCK:
        cupos = leer_cupo()
        anterior = cupos.get(clave) or {}
        # sin dato nuevo, se queda la última medida buena (dice «hace N min»)
        if not ventanas and anterior.get("ventanas"):
            ficha = dict(anterior, ultimo_intento=ficha["medido_en"],
                         error=ficha.get("error") or "el CLI no dio el cupo esta vez")
        cupos[clave] = ficha
        _escribir_cupo(cupos)
    return ficha


def medir_en_segundo_plano(cuenta=None):
    """Lanza `medir` en un hilo si no hay ya una medida de esa cuenta. -> bool"""
    with _LOCK:
        if clave_de(cuenta) in _MIDIENDO:
            return False
    threading.Thread(target=medir, args=(cuenta,), name="medir-cupo", daemon=True).start()
    return True


def midiendo():
    with _LOCK:
        return bool(_MIDIENDO)


def toca_medir(cuenta=None, ahora=None):
    """Si hace más de CADA_S de la última medida y desde entonces ha habido
    llamadas de esa cuenta. Con ESTUDIO_SIMULAR, nunca sola."""
    if simulado():
        return False
    ahora = ahora or time.time()
    ficha = leer_cupo().get(clave_de(cuenta)) or {}
    ultima = float(ficha.get("ultimo_intento") or ficha.get("medido_en") or 0)
    if ahora - ultima < CADA_S:
        return False
    clave = clave_de(cuenta)
    if clave in _ULTIMA:
        return _ULTIMA[clave] > ultima
    # tras reiniciar el servicio no hay memoria: se mira el fichero (una vez)
    return any(r.get("tipo") == "llamada" and r.get("clave") == clave and r.get("para") != "medir el cupo"
               and float(r.get("t") or 0) > ultima for r in leer_registro(ultima))


# ------------------------------------------------------------------ resumen

def _dia(t):
    return time.strftime("%Y-%m-%d", time.localtime(t))


def _sumar(caja, r):
    caja["llamadas"] += 1
    caja["tokens"] += (_numero(r.get("entrada")) + _numero(r.get("salida"))
                       + _numero(r.get("cache_creada")) + _numero(r.get("cache_leida")))
    caja["salida"] += _numero(r.get("salida"))
    if isinstance(r.get("usd"), (int, float)):
        caja["usd"] = round(caja["usd"] + float(r["usd"]), 4)


def tarea_de(para):
    """«el corrector del plano 12» y «el revisor de imágenes (p1–p8)» son la
    misma tarea para el resumen: sin números ni paréntesis."""
    texto = re.sub(r"\([^)]*\)", "", str(para or ""))
    texto = re.sub(r"\s*\b[\w-]*\d[\w–-]*", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" :·-")
    return texto or "otra"


def _caja(**extra):
    return dict({"llamadas": 0, "tokens": 0, "salida": 0, "usd": 0.0}, **extra)


def resumen(ahora=None, dias=DIAS_RESUMEN):
    """Lo de los últimos `dias`: hoy, la semana, por día, por tarea, por vídeo y
    por cuenta, y cuándo se agotó el cupo si pasó."""
    ahora = ahora or time.time()
    desde = ahora - dias * 86400
    registros = leer_registro(desde)
    hoy, semana = _caja(), _caja()
    por_dia, por_tarea, por_video, por_cuenta = {}, {}, {}, {}
    agotados = []
    dia_de_hoy = _dia(ahora)
    for r in registros:
        if r.get("tipo") == "cupo":
            agotados.append({"t": r.get("t"), "cuenta": r.get("cuenta"), "mensaje": r.get("mensaje")})
            continue
        if r.get("tipo") != "llamada":
            continue
        t = float(r.get("t") or 0)
        dia = _dia(t)
        _sumar(semana, r)
        if dia == dia_de_hoy:
            _sumar(hoy, r)
        _sumar(por_dia.setdefault(dia, _caja(fecha=dia)), r)
        tarea = tarea_de(r.get("para"))
        _sumar(por_tarea.setdefault(tarea, _caja(tarea=tarea)), r)
        if r.get("proyecto"):
            _sumar(por_video.setdefault(r["proyecto"], _caja(pid=r["proyecto"])), r)
        cuenta = r.get("cuenta") or "principal"
        _sumar(por_cuenta.setdefault(cuenta, _caja(cuenta=cuenta)), r)

    def orden(d):
        return sorted(d.values(), key=lambda c: (-c["usd"], -c["tokens"]))
    return {"hoy": hoy, "semana": semana,
            "por_dia": sorted(por_dia.values(), key=lambda c: c["fecha"], reverse=True),
            "por_tarea": orden(por_tarea)[:12], "por_video": orden(por_video)[:12],
            "por_cuenta": orden(por_cuenta), "agotados": agotados[-5:], "dias": dias}


def avisos(cupos, ahora=None):
    """[{nivel: ojo|malo, cuenta, ventana, nombre, uso, reinicia}] de cada
    ventana que pasa de UMBRAL_OJO y aún no se ha reiniciado."""
    ahora = ahora or time.time()
    salida = []
    for ficha in (cupos or {}).values():
        if not isinstance(ficha, dict):
            continue
        for nombre, v in (ficha.get("ventanas") or {}).items():
            uso = float(v.get("uso") or 0)
            reinicia = v.get("reinicia")
            if reinicia and float(reinicia) <= ahora:
                continue                                  # ya se reinició
            if uso >= UMBRAL_OJO:
                salida.append({"nivel": "malo" if uso >= UMBRAL_MALO else "ojo",
                               "cuenta": ficha.get("cuenta") or "principal", "ventana": nombre,
                               "nombre": NOMBRES_VENTANA.get(nombre, nombre),
                               "uso": round(uso, 4), "reinicia": reinicia})
        if ficha.get("estado") == "rejected" and not any(
                a["cuenta"] == (ficha.get("cuenta") or "principal") and a["nivel"] == "malo" for a in salida):
            salida.append({"nivel": "malo", "cuenta": ficha.get("cuenta") or "principal",
                           "ventana": "", "nombre": "Cupo agotado", "uso": 1.0,
                           "reinicia": None, "mensaje": ficha.get("mensaje") or "",
                           "agotado_en": ficha.get("agotado_en")})
    return sorted(salida, key=lambda a: -a["uso"])


def describir_modulo():
    return f"consumo de Claude en {fichero_registro()} y cupo en {fichero_cupo()}"

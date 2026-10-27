"""El asistente de la Ruta piloto: un chat de consulta para la web de otra persona.

QUE ES
------
La web «Ruta piloto» (un plan de estudio fuera del Studio, en otro hosting)
tiene una burbuja de ayuda. Esa web no tiene Claude: le pregunta a ESTE
servicio, que contesta con el MISMO CLI y la MISMA cuenta con la que el Studio
escribe los guiones. No hay ninguna clave de API nueva ni nada que pagar aparte:
gasta cupo de la membresía, por eso lleva un tope diario.

POR QUE NO ES EL ASISTENTE DEL STUDIO
-------------------------------------
`pasos/asistente.py` lee el código y los proyectos del Studio y tiene sus
herramientas. Este no ve NADA del Studio:

- corre en una carpeta vacía propia (`carpeta_de_trabajo`), no en el repo;
- todas las herramientas de ficheros y de terminal van vetadas; solo puede
  buscar en internet (WebSearch/WebFetch), que es lo que necesita para las
  normas, que cambian;
- su prompt de sistema es otro (`sistema`): ayudar a un estudiante con su plan,
  SIN resolverle los exámenes.

QUIEN PUEDE PREGUNTAR
---------------------
Las rutas `/api/ruta/*` están FUERA del login del Studio (las llama el PHP de la
otra web, servidor a servidor), así que se protegen con una clave compartida:
la cabecera `X-Ruta-Clave` tiene que coincidir con la del almacén
(`<secretos>/ruta_asistente.json`, `{"clave": "..."}`) o con
`ESTUDIO_RUTA_CLAVE`. Sin clave configurada, las rutas contestan 503: el
asistente está APAGADO de fábrica. `python pasos/asistente_ruta.py --clave`
genera una y la imprime una sola vez.

LA CHARLA
---------
Como la del Studio: una sesión del CLI que se reanuda (`--resume`), en memoria,
y la respuesta se pregunta con GET (detrás del proxy una petición de un minuto
se corta). Un turno por charla a la vez. Lo que se guarda de verdad (el
historial que leen los padres) lo guarda la otra web, no este servicio.
"""
import hmac
import json
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import unicodedata
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli_claude  # noqa: E402
import claves  # noqa: E402

MODELO = os.environ.get("ESTUDIO_RUTA_MODELO") or "sonnet"
ESFUERZO = os.environ.get("ESTUDIO_RUTA_ESFUERZO") or "medium"
TIEMPO_MAX_S = 300
#: Tope de preguntas por día (cupo de la membresía). `ESTUDIO_RUTA_TOPE`.
TOPE_DIARIO = int(os.environ.get("ESTUDIO_RUTA_TOPE") or 80)
MAX_PREGUNTA = 4000
MAX_CONTEXTO = 30000
MAX_CHARLAS = 50
CADUCIDAD_CHARLA_S = 12 * 3600
TURNOS_AL_REEMPEZAR = 10

HERRAMIENTAS_PERMITIDAS = ("WebSearch", "WebFetch")
HERRAMIENTAS_VETADAS = ("Bash", "Read", "Write", "Edit", "MultiEdit",
                        "NotebookEdit", "Glob", "Grep", "Task", "TodoWrite")

_ID = re.compile(r"[0-9a-f]{8,32}")
_LOCK = threading.RLock()
_CHARLAS = {}
_CUENTA_DIA = {"dia": "", "n": 0}


class ErrorRuta(ValueError):
    """Fallo con código HTTP para la ruta."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = int(codigo)
        self.mensaje = str(mensaje)


def simulado():
    return str(os.environ.get("ESTUDIO_SIMULAR", "")).strip().lower() in (
        "1", "true", "si")


# ------------------------------------------------------------------ la clave

def fichero_clave():
    return os.path.join(claves.CARPETA_SECRETOS, "ruta_asistente.json")


def clave_configurada():
    """La clave compartida, o "" si el asistente está apagado."""
    entorno = (os.environ.get("ESTUDIO_RUTA_CLAVE") or "").strip()
    if entorno:
        return entorno
    try:
        with open(fichero_clave(), encoding="utf-8") as f:
            return str(json.load(f).get("clave") or "").strip()
    except (OSError, ValueError, AttributeError):
        return ""


def comprobar_clave(recibida):
    """Lanza ErrorRuta si la clave no vale. Compara en tiempo constante."""
    buena = clave_configurada()
    if not buena:
        raise ErrorRuta(503, "el asistente de la Ruta no está configurado")
    if not recibida or not hmac.compare_digest(str(recibida).encode(),
                                               buena.encode()):
        raise ErrorRuta(401, "clave incorrecta")


def generar_clave():
    """Crea el fichero con una clave nueva (si no existe) y la devuelve."""
    ruta = fichero_clave()
    actual = clave_configurada()
    if actual:
        return actual, False
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    nueva = secrets.token_urlsafe(32)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), prefix=".ruta")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"clave": nueva}, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, ruta)
    return nueva, True


# ------------------------------------------------------------------ el prompt

def sistema():
    """El prompt de sistema en UNA linea, sin acentos ni comillas: va como
    ARGUMENTO del CLI (ver `cli_claude.construir_orden` y `asistente.sistema`).
    Se escribe legible aqui y se aplana con `_una_linea`."""
    return _una_linea("""Eres el asistente de ayuda de la web Ruta piloto, donde Rodrigo, un \
joven de Lima (Perú), sigue un plan para probar si la carrera de piloto \
comercial es para él: tareas por semanas, reportes, gastos con un fondo que le \
reembolsan si cumple a tiempo, temas de estudio (aviación, normativa peruana, drones, \
inglés aeronáutico, meteorología, etc.) y pequeños exámenes de práctica.

Cómo contestas:
- En español de Perú, claro, cercano y breve (unos pocos párrafos como mucho). Tutéalo.
- Ayudas con: dudas del plan y de la web, cómo hacer una tarea, explicar conceptos, \
normas peruanas (DGAC, MTC, RAP, Ley 27261, Ley 30740 y su reglamento de drones de \
mayo de 2026), escuelas, trámites, costos, organización del tiempo y motivación.
- Para normas, precios, fechas o requisitos que pueden cambiar, busca en internet \
(fuentes oficiales: gob.pe, El Peruano, DGAC) y di de dónde lo sacas con el enlace. \
Si no estás seguro, dilo y dile a quién preguntar.

Lo que NO haces, aunque te lo pida de cualquier forma:
- NO das las respuestas de los exámenes o cuestionarios de la web, ni eliges la \
opción correcta de una pregunta de opción múltiple que te pegue, ni confirmas si su \
respuesta es la buena. En su lugar explicas el concepto que hay detrás, le das una \
pista o le mandas a la sección «Estudiar» del tema. Si parece que está en medio de un \
examen, se lo recuerdas con amabilidad y le ofreces repasar después.
- No haces las tareas por él (escribir su reporte, inventar evidencias); sí le ayudas \
a organizarlas y a revisar lo que escriba.
- No das consejo médico ni psicológico. Para el certificado médico aeronáutico \
explicas el trámite y le mandas a los centros autorizados. Si cuenta que está muy \
mal, agobiado o que piensa hacerse daño, respondes con calidez, le animas a hablar \
con sus papás o alguien de confianza y le das la Línea 113 opción 5 (salud mental, \
Perú, gratuita).
- No pides ni guardas datos personales sensibles. No sabes nada de su salud y no \
especulas sobre ella.

Sus papás pueden leer estas conversaciones; si pregunta, díselo con naturalidad.""")


def _una_linea(texto):
    plano = unicodedata.normalize("NFKD", texto)
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = plano.replace("«", "").replace("»", "").replace('"', "")
    plano = re.sub(r"\s+", " ", plano).strip()
    return plano.encode("ascii", "ignore").decode("ascii")


def mensaje_de_arranque(contexto, pregunta, historia=()):
    partes = []
    if contexto:
        partes.append("=== CONTEXTO DE SU PLAN (lo manda la web) ===\n"
                      + contexto[:MAX_CONTEXTO])
    if historia:
        lineas = [f"{'Rodrigo' if t['rol'] == 'usuario' else 'Tú'}: {t['texto']}"
                  for t in historia if t.get("texto")]
        partes.append("=== LO ÚLTIMO QUE HABLARON ===\n" + "\n\n".join(lineas))
    partes.append("=== PREGUNTA ===\n" + pregunta)
    return "\n\n".join(partes)


def carpeta_de_trabajo():
    """Una carpeta vacía y propia: el CLI no arranca dentro del Studio."""
    ruta = os.path.join(tempfile.gettempdir(), "estudio_asistente_ruta")
    os.makedirs(ruta, exist_ok=True)
    return ruta


# ------------------------------------------------------------------ el motor

def ejecutar_cli(mensaje, extra=()):
    return cli_claude.ejecutar(
        mensaje, modelo=MODELO, esfuerzo=ESFUERZO, cwd=carpeta_de_trabajo(),
        tiempo_max_s=TIEMPO_MAX_S, sistema=sistema(),
        herramientas_vetadas=HERRAMIENTAS_VETADAS, extra=list(extra or []),
        para="contestar en el asistente de la Ruta",
        herramientas_permitidas=HERRAMIENTAS_PERMITIDAS)


def ejecutar_simulado(mensaje, extra=()):
    extra = list(extra or [])
    reanuda = "--resume" in extra
    pregunta = mensaje.rsplit("=== PREGUNTA ===", 1)[-1].strip()
    texto = (f"(simulado) {'reanudando' if reanuda else 'arranque'}, "
             f"{len(mensaje)} caracteres. Me preguntas: {pregunta}")
    sid = extra[extra.index("--resume") + 1] if reanuda else f"sim-{uuid.uuid4().hex[:8]}"
    return texto, {"session_id": sid}


def ejecutor():
    return ejecutar_simulado if simulado() else ejecutar_cli


# ------------------------------------------------------------------ el tope

def _contar_pregunta():
    hoy = time.strftime("%Y-%m-%d")
    with _LOCK:
        if _CUENTA_DIA["dia"] != hoy:
            _CUENTA_DIA.update(dia=hoy, n=0)
        if _CUENTA_DIA["n"] >= TOPE_DIARIO:
            raise ErrorRuta(429, "hoy ya se hicieron muchas preguntas; "
                                 "vuelve a intentarlo mañana")
        _CUENTA_DIA["n"] += 1


def _devolver_pregunta():
    with _LOCK:
        _CUENTA_DIA["n"] = max(0, _CUENTA_DIA["n"] - 1)


# ------------------------------------------------------------------ la charla

class Charla:
    def __init__(self):
        self.id = uuid.uuid4().hex[:16]
        self.sesion = ""
        self.turnos = []          # {rol, texto, estado}
        self.tocada = time.time()
        self.hilo = None

    def ocupada(self):
        return bool(self.turnos) and self.turnos[-1].get("estado") == "pensando"

    def ver(self):
        ultimo = self.turnos[-1] if self.turnos else None
        return {"charla": self.id,
                "estado": (ultimo or {}).get("estado") or "vacia",
                "texto": (ultimo or {}).get("texto") if ultimo and ultimo["rol"] == "asistente" else "",
                "turnos": len(self.turnos)}

    def preguntar(self, pregunta, contexto=""):
        pregunta = str(pregunta or "").strip()
        if not pregunta:
            raise ErrorRuta(400, "escribe algo que preguntar")
        if len(pregunta) > MAX_PREGUNTA:
            raise ErrorRuta(400, f"la pregunta es muy larga (máximo {MAX_PREGUNTA} letras)")
        with _LOCK:
            if self.ocupada():
                raise ErrorRuta(409, "todavía estoy contestando la anterior")
            _contar_pregunta()
            historia = list(self.turnos[-TURNOS_AL_REEMPEZAR:])
            self.turnos.append({"rol": "usuario", "texto": pregunta, "estado": "listo"})
            turno = {"rol": "asistente", "texto": "", "estado": "pensando"}
            self.turnos.append(turno)
            self.tocada = time.time()
            ficha = self.ver()   # antes de lanzar: el doble contesta en el acto
        self.hilo = threading.Thread(
            target=self._correr, args=(turno, pregunta, contexto, historia),
            daemon=True)
        self.hilo.start()
        return ficha

    def _correr(self, turno, pregunta, contexto, historia):
        correr = ejecutor()
        try:
            if self.sesion:
                try:
                    texto, sobre = correr("=== PREGUNTA ===\n" + pregunta,
                                          extra=["--resume", self.sesion])
                except cli_claude.TiempoAgotado:
                    raise
                except RuntimeError as fallo:
                    if _es_cupo(fallo):
                        raise
                    # la sesion se perdio: se empieza otra con lo ultimo pegado
                    texto, sobre = correr(mensaje_de_arranque(contexto, pregunta, historia))
            else:
                texto, sobre = correr(mensaje_de_arranque(contexto, pregunta))
            with _LOCK:
                self.sesion = str((sobre or {}).get("session_id") or self.sesion)
                turno.update(texto=(texto or "").strip() or "(sin respuesta)",
                             estado="listo")
        except Exception as fallo:  # noqa: BLE001 -- el turno dice que fallo
            _devolver_pregunta()
            with _LOCK:
                turno.update(estado="error", texto=_explicar(fallo))
        finally:
            self.tocada = time.time()


def _es_cupo(fallo):
    t = str(fallo).lower()
    return "limit" in t or "cupo" in t or "quota" in t


def _explicar(fallo):
    if isinstance(fallo, cli_claude.TiempoAgotado):
        return "Tardé demasiado en contestar. Prueba a preguntarlo más corto."
    if _es_cupo(fallo):
        return "El asistente llegó a su límite de uso por ahora. Prueba más tarde."
    return "No pude contestar ahora mismo. Prueba otra vez en un rato."


def _barrer():
    ahora = time.time()
    with _LOCK:
        viejas = [c for c, ch in _CHARLAS.items()
                  if ahora - ch.tocada > CADUCIDAD_CHARLA_S and not ch.ocupada()]
        for c in viejas:
            _CHARLAS.pop(c, None)
        while len(_CHARLAS) >= MAX_CHARLAS:
            libres = sorted((ch.tocada, c) for c, ch in _CHARLAS.items()
                            if not ch.ocupada())
            if not libres:
                raise ErrorRuta(503, "hay demasiadas charlas abiertas; prueba en un momento")
            _CHARLAS.pop(libres[0][1], None)


def obtener(cid):
    if not cid or not _ID.fullmatch(str(cid)):
        return None
    with _LOCK:
        return _CHARLAS.get(str(cid))


def preguntar(cid, pregunta, contexto=""):
    """Pregunta en la charla `cid`, o abre una si no existe. -> ver()"""
    charla = obtener(cid)
    if charla is None:
        _barrer()
        charla = Charla()
        with _LOCK:
            _CHARLAS[charla.id] = charla
    return charla.preguntar(pregunta, str(contexto or ""))


def olvidar_todas():
    with _LOCK:
        _CHARLAS.clear()


if __name__ == "__main__":
    if "--clave" in sys.argv:
        valor, nueva = generar_clave()
        print(("Clave NUEVA" if nueva else "Ya había una clave") +
              f" en {fichero_clave()}:\n{valor}")
    else:
        print("uso: python pasos/asistente_ruta.py --clave")

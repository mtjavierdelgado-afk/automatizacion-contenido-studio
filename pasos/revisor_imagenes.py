"""EL REVISOR DE IMAGENES: mira cada plano dibujado contra su guion y su estilo.

QUE ES
------
Lo que hasta el 18-10-2026 se hacia a mano: abrir las imagenes de una tanda,
leer a la vez el trozo de guion de cada una, la guia del estilo, las
indicaciones del Encargo y las reglas de la casa, y escribir por plano una nota
concreta --«el televisor va en su rack de tripode negro, no en un mueble; los
mandos son DualSense blancos, no negros; que los jugadores miren a la pantalla»--
para rehacerlo. En el video del torneo de EstadoPlay (EP-CONT-021) eso fueron
siete planos y una tarde: mandos fundidos en S001, un monitor gigante en S004,
mandos negros, la tele sobre un mueble.

El revisor es un agente del CLI (`cli_claude`, el mismo motor que el corrector)
que abre las imagenes con `Read` --solo `Read`, y solo dentro del proyecto-- y
devuelve, plano a plano, un veredicto y, si hay que corregir, la NOTA en
espanol, con la misma forma que escribiria una persona. Esa nota entra en el
repaso como cualquier otra (pantalla «imagenes», `autor: "revisor"`), y de ahi
la rehace la cola de notas de siempre: el revisor no genera nada.

QUE NO HACE
-----------
- No escribe params. Su estado (lo revisado, lo gastado, los intentos por plano)
  vive en `<proyecto>/revisor.json`, fuera de toda firma: revisar un video no
  puede dejar nada obsoleto (regla 1 de CLAUDE.md).
- No decide cuanto se paga. Elige QUE rehacer dentro de los topes que le dan
  (`elegir`); cuanto vale una imagen lo dice quien llama.
- No vuelve a mirar una imagen que ya miro. Cada plano se apunta con la huella
  de su PNG: lo que no cambio no se revisa otra vez, y por eso se puede llamar
  despues de cada tanda sin pagar dos veces la misma lectura.

LOS TRES MODOS (ajuste del servidor `revisor_modo`, ver `pasos/ajustes.py`)
-------------------------------------------------------------------------
  manual       solo con el boton «Revisar imagenes»: escribe las notas y la
               persona decide que se rehace.
  autonomo     despues de cada tanda de imagenes revisa lo nuevo y rehace solo
               lo GRAVE (lo que contradice el guion, la marca o las reglas),
               una vuelta y dentro de los topes. Lo demas queda como nota.
  automatico   lo mismo, pero rehace todo lo marcado y vuelve a revisar lo
               rehecho, hasta `revisor_vueltas` vueltas.
"""
import hashlib
import json
import os
import threading
import time

try:
    from . import cli_claude, comun, dominios, estadisticas, repaso
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun
    import dominios
    import estadisticas
    import repaso

FASE = "revisor_imagenes"
FICHERO = "revisor.json"
CARPETA = "revisor"
AUTOR = "revisor"

MODOS = ("manual", "autonomo", "automatico")

#: Cuantos planos ve el agente en cada llamada. Seguidos, para que pueda
#: comparar la continuidad (la misma estacion, la misma gente) entre vecinos;
#: mas de ocho y empieza a mezclar lo que vio en cada uno.
POR_LLAMADA = 8

#: La copia que se le ensena: 768 px de lado mayor. Un PNG de 1024x1536 son
#: ~1.600 tokens de imagen y no deja ver nada que no se vea a 768.
LADO = 768

#: Cuantas veces, como mucho, se rehace SOLO un mismo plano. Un plano que sale
#: mal tres veces no lo arregla una cuarta: lo arregla una persona.
INTENTOS_POR_PLANO = 2

TIEMPO_BASE_S = 420

TIPOS = ("regla", "guion", "equipo", "congruencia", "personas", "manos",
         "orientacion", "estilo", "texto", "artefacto")

#: El hueco de las reglas del estilo en la instruccion, cuando el estilo las
#: tiene (pasos/reglas_estilo.py). Sin reglas el hueco queda vacio.
BLOQUE_REGLAS_ESTILO = """
LAS REGLAS DEL ESTILO (las escribio quien hizo el estilo; son lo PRIMERO que se
comprueba en cada plano al que aplican, y si una se incumple el problema es de
tipo "regla", con la gravedad que dice la propia regla -- esa manda sobre tu
criterio):
{reglas}
"""
GRAVEDADES = ("alta", "media", "baja")

HERRAMIENTAS_VETADAS = ("Bash", "Write", "Edit", "NotebookEdit", "Grep", "Glob",
                        "WebFetch", "WebSearch", "Task", "TodoWrite")
HERRAMIENTAS_PERMITIDAS = ("Read",)

SISTEMA = ("Eres el director de arte que revisa las imagenes de un video corto "
           "narrado antes de montarlo. Abre con Read TODAS las imagenes que se "
           "te listan antes de opinar de ninguna: se juzgan una a una y tambien "
           "entre si. Responde despues exclusivamente con el objeto JSON pedido, "
           "sin texto alrededor y sin vallas de markdown.")

INSTRUCCION = """Revisa {n} planos de «{titulo}» ({formato}). Cada plano es una
imagen fija que se ve mientras la voz dice su frase.

QUE TIENE QUE SER CADA IMAGEN, por orden de autoridad:
  1. Lo que dice la voz en ese plano y el bloque del guion: la imagen lo
     ilustra; si la voz habla de ocho jugadores no pueden salir dos.
  2. Las indicaciones del Encargo y del estilo (abajo): el sitio, el equipo, la
     gente, como se monta todo. Lo que digan, se cumple en TODOS los planos.
  3. Las reglas de la casa (abajo).
  4. La descripcion con la que se pidio el plano y su tipo de plano: dicen lo
     que se queria; si la imagen la contradice, es un fallo.

LAS INDICACIONES DEL ESTILO:
{estilo}

LA GUIA ESCRITA DEL ESTILO:
{guia}

LAS INDICACIONES DEL ENCARGO (las del video):
{encargo}

LAS REGLAS DE LA CASA:
{reglas}
{reglas_estilo}
{referencia}LOS PLANOS (abre cada imagen con Read; van en orden de video):
{planos}

QUE BUSCAR, y en este orden:
  - regla: incumple una de las REGLAS DEL ESTILO que aplican a ese plano (si
    el estilo tiene); la gravedad es la de la regla.
  - guion: la imagen no cuenta lo que dice la voz (otra accion, otro numero de
    personas, otro momento).
  - equipo: {f_equipo}
  - congruencia: {f_congruencia}
  - personas: gente que no deberia estar, caras o cuerpos deformes, una
    persona que no deberia salir con cara segun las indicaciones.
  - manos: {f_manos}
  - orientacion: {f_orientacion}
  - estilo: no parece del mismo video (otra luz, otra paleta, render en vez de
    foto, dibujo en vez de foto o al reves).
  - texto: letras, logos o marcas que nadie pidio, o texto ilegible.
  - artefacto: objetos fundidos, duplicados o que no se entienden.

NO MARQUES lo que no se veria en un movil a tamano normal, ni gustos: solo lo
que alguien que conoce el guion y la marca notaria al verlo. Una imagen que
cumple es "bien" aunque se pudiera hacer de otra manera.

QUE TIENES QUE DEVOLVER
Un objeto JSON {{"planos": [...]}} con UNA entrada por plano de la lista:
  "id"         el id del plano, tal cual.
  "veredicto"  "bien" o "corregir".
  "gravedad"   solo si es "corregir": "alta" (contradice el guion, el equipo o
               las reglas; se nota a la primera), "media" (se nota si te
               fijas) o "baja" (detalle).
  "problemas"  lista de {{"tipo": uno de {tipos}, "detalle": que se ve mal, en
               espanol y en una frase}}. Vacia si esta bien.
  "nota"       solo si es "corregir": la nota para rehacer el plano, en
               espanol, como la escribiria un director de arte: que se
               CONSERVA de la imagen y que se CAMBIA, con los objetos, colores,
               posiciones y miradas concretos que piden las indicaciones. Dos
               o tres frases. Nada de «mejorar» o «mas bonito»: cosas que se
               puedan dibujar.
  "alcance"    solo si es "corregir": "retoque" si la composicion vale y
               cambia algo concreto; "sustituye" si hay que hacer otra
               imagen (la composicion misma esta mal).
"""


# ---------------------------------------------------------------- el estado

_CERROJO = threading.RLock()


def ruta_estado(proyecto):
    return proyecto.ruta(FICHERO)


def leer_estado(proyecto):
    """{revisadas: {plano: {huella, veredicto, gravedad, nota, fecha}},
    intentos: {plano: n}, gastado_usd, ultima: {...}}. Nunca levanta."""
    try:
        with open(ruta_estado(proyecto), "r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        datos = {}
    if not isinstance(datos, dict):
        datos = {}
    return {"revisadas": dict(datos.get("revisadas") or {}),
            "intentos": {str(k): int(v or 0)
                         for k, v in (datos.get("intentos") or {}).items()},
            "gastado_usd": round(float(datos.get("gastado_usd") or 0.0), 4),
            "ultima": dict(datos.get("ultima") or {})}


def guardar_estado(proyecto, datos):
    with _CERROJO:
        comun.escribir_json(ruta_estado(proyecto), datos)
    return datos


#: {(ruta, mtime_ns, tamano): huella}. La pantalla pregunta cuantas faltan
#: por revisar cada medio minuto y leer ochenta PNG cada vez no es gratis.
_HUELLAS = {}


def huella(ruta):
    """sha1 del fichero, o "" si no se puede leer."""
    try:
        datos = os.stat(ruta)
        clave = (os.path.abspath(ruta), datos.st_mtime_ns, datos.st_size)
        if clave in _HUELLAS:
            return _HUELLAS[clave]
        with open(ruta, "rb") as fh:
            valor = hashlib.sha1(fh.read()).hexdigest()[:16]
    except OSError:
        return ""
    if len(_HUELLAS) > 5000:
        _HUELLAS.clear()
    _HUELLAS[clave] = valor
    return valor


def sin_revisar(proyecto, imagenes, forzar=False):
    """Los planos cuya imagen de ahora no se ha revisado. -> [plano]

    `imagenes` es {plano: ruta absoluta del PNG activo}, en orden de video."""
    revisadas = leer_estado(proyecto)["revisadas"]
    salida = []
    for plano, ruta in imagenes.items():
        if not os.path.isfile(ruta):
            continue
        if forzar or (revisadas.get(plano) or {}).get("huella") != huella(ruta):
            salida.append(plano)
    return salida


# ------------------------------------------------------------ lo que se ensena

def _texto(valor, tope=1200):
    return " ".join(str(valor or "").split())[:tope]


def _copia(proyecto, plano, ruta):
    """Una copia JPEG pequena dentro del proyecto. -> ruta relativa al proyecto.

    Dentro del proyecto porque el agente corre con cwd en su raiz y `Read` no
    sale de ahi. Si Pillow no puede, se ensena el PNG tal cual."""
    carpeta = proyecto.ruta(CARPETA)
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, f"{plano}.jpg")
    try:
        from PIL import Image                               # noqa: PLC0415
        with Image.open(ruta) as imagen:
            imagen = imagen.convert("RGB")
            imagen.thumbnail((LADO, LADO))
            imagen.save(destino, "JPEG", quality=85)
        return os.path.relpath(destino, proyecto.raiz).replace(os.sep, "/")
    except Exception:                                        # noqa: BLE001
        return os.path.relpath(ruta, proyecto.raiz).replace(os.sep, "/")


def _bloques_por_id(plan):
    return {str(b.get("id")): str(b.get("texto") or "")
            for b in (plan.get("bloques") or []) if isinstance(b, dict)}


def _planos_legibles(proyecto, escenas, imagenes, bloques):
    lineas = []
    for escena in escenas:
        sid = str(escena.get("id"))
        bloque = bloques.get(str((escena.get("origen") or {}).get("bloque") or ""), "")
        t_in, t_out = escena.get("t_in"), escena.get("t_out")
        reloj = (f"{float(t_in):.1f}-{float(t_out):.1f} s"
                 if isinstance(t_in, (int, float)) and isinstance(t_out, (int, float))
                 else "")
        lineas.append(
            f"- {sid} ({reloj})  imagen: {_copia(proyecto, sid, imagenes[sid])}\n"
            f"    voz: {_texto(escena.get('narracion'), 500) or '(sin voz)'}\n"
            f"    bloque del guion: {_texto(bloque, 500) or '(sin bloque)'}\n"
            f"    se pidio (en ingles): {_texto(escena.get('prompt'), 700) or '(sin descripcion)'}\n"
            f"    tipo de plano: {_texto(escena.get('encuadre'), 200) or '(libre)'}"
            + (f"\n    personajes: {', '.join(escena.get('personajes') or [])}"
               if escena.get("personajes") else "")
            # EDITADO DESDE LA IMAGEN BASE (rama tipo-de-relato): solo los
            # planos que lo estan llevan esta linea; los demas, como siempre
            + (f"\n    EDITADO DESDE LA IMAGEN BASE de «{escena.get('set')}»; lo unico "
               f"que se pidio cambiar: {_texto(escena.get('cambio'), 400) or '(nada del sitio: solo la accion)'}"
               if escena.get("editar_base") and not escena.get("base_clave") else "")
            # la imagen de un ESTADO ya trae el cambio: el plano no cambia nada
            + (f"\n    EDITADO DESDE LA IMAGEN BASE de «{escena['base_clave'].replace('#', ' · estado ')}» "
               f"(que ya muestra: {_texto(escena.get('cambio'), 400)}); lo unico que se pidio "
               f"cambiar: (nada del sitio: solo la accion)"
               if escena.get("editar_base") and escena.get("base_clave") else "")
            # GUION VISUAL (rama guion-visual): lo que tiene que verse lo dice
            # su linea, no la voz; sin linea, como siempre
            + (f"\n    GUION VISUAL: lo que tiene que verse es «{_texto((escena.get('linea_gv') or {}).get('visual'), 500)}». "
               f"Juzga la imagen contra ESTA linea, NO contra la voz: en este video la voz va "
               f"por su lado y no es un problema de \"guion\" que la imagen no la ilustre"
               if escena.get("linea_gv") else ""))
    return "\n".join(lineas)


#: Lo que se le dice del plano de REFERENCIA: el que va justo antes del primero
#: de la tanda. Solo para comparar la continuidad, nunca para juzgarlo.
REFERENCIA = """EL PLANO DE ANTES, SOLO COMO REFERENCIA (abrelo con Read, pero NO lo
juzgues ni lo pongas en tu respuesta: ya se reviso o se revisa aparte). Sirve
para ver si el primer plano de la lista mantiene {continuidad} que venia de antes:
{plano}

"""


#: La imagen base de un sitio (rama tipo-de-relato). Los planos que se generan
#: EDITANDOLA tienen que ser ese mismo sitio, con la misma camara: todo lo que
#: cambie fuera de lo pedido es congruencia, y de gravedad alta.
REFERENCIA_BASE = """LA IMAGEN BASE DE «{sitio}» (abrela con Read, pero NO la juzgues ni la
pongas en tu respuesta): los planos marcados «EDITADO DESDE LA IMAGEN BASE» se
generaron editandola. Comparalos con ella uno a uno. La distribucion, la camara
(posicion, altura, angulo), las paredes, el suelo, los muebles fijos y los
acabados tienen que ser LOS MISMOS que en la base, salvo lo que diga «lo unico
que se pidio cambiar» de cada plano. Cualquier otro cambio del sitio es un
problema de tipo "congruencia" con gravedad "alta". El cambio pedido NO es una
incongruencia, y la gente o los objetos sueltos que pide la voz tampoco.
  imagen base: {imagen}

"""


def _referencia_base(proyecto, tanda, bases):
    """El bloque de la imagen base de los sitios editados de la tanda, o ""."""
    texto = ""
    # la clave es el sitio o, en «un espacio que cambia», la imagen del estado
    # del plano («sitio#estado»): se compara con la que se edito de verdad
    for clave in sorted({e.get("base_clave") or e.get("set") for e in tanda
                         if e.get("editar_base")
                         and (e.get("base_clave") or e.get("set")) in (bases or {})}):
        texto += REFERENCIA_BASE.format(
            sitio=clave.replace("#", " · estado "),
            imagen=_copia(proyecto, "base_" + clave.replace("#", "__"), bases[clave]))
    return texto


def _frases(estilo, plan, guia="", encargo=""):
    """Las frases del revisor que hablan del equipo del negocio (rama
    dominio-negocio): las del dominio que fija el estilo o, en automático, las
    de EstadoPlay si el vídeo nombra sus servicios y las generales si no. Antes
    eran siempre las de consolas, también en un vídeo de baños."""
    texto = " ".join([str((estilo or {}).get("prompt") or ""), str(guia or ""), str(encargo or "")]
                     + [str(e.get("prompt") or "") for e in (plan or {}).get("escenas") or []])
    return dominios.frases_revisor(estilo, texto)


def _referencia_de(proyecto, plan, primero, imagenes, bloques, frases=None):
    """El texto del plano que va justo antes de `primero` en el video, o "".

    Los grupos se miran por separado, y sin esto el ultimo plano de un grupo y
    el primero del siguiente no se comparaban nunca: justo donde la estacion
    podia cambiar sin que nadie lo viera. Vale tambien cuando se revisa un plano
    suelto (el que acaba de rehacer una tanda): se compara con el de antes."""
    anterior = None
    for escena in plan.get("escenas") or []:
        sid = str(escena.get("id"))
        if sid == primero:
            break
        if sid in imagenes and os.path.isfile(imagenes[sid]):
            anterior = escena
    if anterior is None:
        return ""
    return REFERENCIA.format(
        continuidad=(frases or dominios.REVISOR_GENERAL)["continuidad"],
        plano=_planos_legibles(proyecto, [anterior], imagenes, bloques))


def _rango(ids):
    """«S001» o «S001–S008»."""
    return ids[0] if len(ids) == 1 else f"{ids[0]}–{ids[-1]}"


def _ajuste(ajuste):
    ajuste = dict(ajuste or {})
    defecto = cli_claude.por_defecto_de(FASE)
    modelo = cli_claude.normalizar_modelo(
        ajuste.get("modelo") or os.environ.get("ESTUDIO_REVISOR_MODELO"),
        defecto=defecto["modelo"])
    esfuerzo = cli_claude.normalizar_esfuerzo(
        ajuste.get("esfuerzo") or os.environ.get("ESTUDIO_REVISOR_ESFUERZO"),
        defecto=defecto["esfuerzo"])
    return modelo, esfuerzo


def _limpiar(crudo, validos):
    """Una entrada de la respuesta, validada. -> (plano, ficha) | (None, None)"""
    if not isinstance(crudo, dict):
        return None, None
    sid = str(crudo.get("id") or "").strip()
    if sid not in validos:
        return None, None
    veredicto = str(crudo.get("veredicto") or "").strip().lower()
    problemas = []
    for p in crudo.get("problemas") or []:
        if not isinstance(p, dict):
            continue
        tipo = str(p.get("tipo") or "").strip().lower()
        detalle = _texto(p.get("detalle"), 300)
        if detalle:
            problemas.append({"tipo": tipo if tipo in TIPOS else "artefacto",
                              "detalle": detalle})
    nota = _texto(crudo.get("nota"), repaso.MAX_TEXTO)
    if veredicto != "corregir" or not nota:
        return sid, {"veredicto": "bien", "problemas": problemas}
    gravedad = str(crudo.get("gravedad") or "").strip().lower()
    alcance = str(crudo.get("alcance") or "").strip().lower()
    return sid, {"veredicto": "corregir",
                 "gravedad": gravedad if gravedad in GRAVEDADES else "media",
                 "problemas": problemas, "nota": nota,
                 "alcance": alcance if alcance in repaso.ALCANCES else "retoque"}


RECORDATORIO_JSON = ("\n\nOJO: tu respuesta anterior no se pudo leer. Contesta "
                     "SOLO con UN objeto JSON {\"planos\": [...]}, con una "
                     "entrada por plano, sin nada antes ni despues.")


class RespuestaIlegible(RuntimeError):
    """La respuesta del revisor no trae ninguna entrada de plano legible."""


def entradas_de(texto):
    """Las entradas de plano de una respuesta, la traiga como la traiga. -> [dict]

    Lo pedido es {"planos": [...]}, pero el modelo a veces devuelve ese objeto
    y algo mas detras, un objeto por plano seguidos, o una lista suelta. Se
    leen TODOS los valores JSON del texto, uno detras de otro, y se recogen las
    entradas que tengan "id". Si no hay ninguna, RespuestaIlegible."""
    texto = str(texto or "")
    decodificador = json.JSONDecoder()
    entradas, i = [], 0

    def recoger(valor):
        if isinstance(valor, dict):
            if isinstance(valor.get("planos"), list):
                for v in valor["planos"]:
                    recoger(v)
            elif valor.get("id"):
                entradas.append(valor)
        elif isinstance(valor, list):
            for v in valor:
                recoger(v)

    while i < len(texto):
        siguiente = min([p for p in (texto.find("{", i), texto.find("[", i)) if p >= 0],
                        default=-1)
        if siguiente < 0:
            break
        try:
            valor, fin = decodificador.raw_decode(texto, siguiente)
        except ValueError:
            i = siguiente + 1
            continue
        recoger(valor)
        i = fin
    if not entradas:
        raise RespuestaIlegible("la respuesta del revisor no trae ningún plano "
                                "legible: " + " ".join(texto.split())[:200])
    return entradas


def revisar(proyecto, plan, imagenes, planos, estilo=None, encargo="",
            reglas="", guia="", formato="", ajuste=None, avisar=None,
            reglas_estilo="", bases=None):
    """Mira esos planos y devuelve {plano: ficha}. Los que no se pudieron mirar
    no salen (y se vuelven a mirar la proxima vez).

    `imagenes` es {plano: ruta absoluta}; `estilo` el dict del estilo del video
    (su `prompt` son las indicaciones que escribio la persona); `guia` la guia
    escrita ya en texto; `reglas` las reglas de la casa ya en texto.
    `bases` es {sitio: ruta absoluta} de las imagenes base aprobadas (tipo de
    relato explicito, `p6_assets.rutas_de_bases`): los planos editados desde
    una se comparan con ella. Sin bases, la instruccion es la de siempre.
    """
    avisar = avisar or (lambda *a, **k: None)
    escenas = [e for e in (plan.get("escenas") or [])
               if str(e.get("id")) in set(planos) and str(e.get("id")) in imagenes]
    if not escenas:
        return {}
    bloques = _bloques_por_id(plan)
    modelo, esfuerzo = _ajuste(ajuste)
    estilo = estilo if isinstance(estilo, dict) else {}
    salida, fallos = {}, []
    frases = _frases(estilo, plan, guia, encargo)
    tandas = [escenas[i:i + POR_LLAMADA] for i in range(0, len(escenas), POR_LLAMADA)]
    for n, tanda in enumerate(tandas):
        ids = [str(e.get("id")) for e in tanda]
        avisar(n / len(tandas), f"revisando {_rango(ids)}",
               f"Revisando las imágenes · {n + 1} de {len(tandas)}")
        instruccion = INSTRUCCION.format(
            n=len(tanda), titulo=_texto(plan.get("titulo"), 120) or "sin titulo",
            formato=_texto(formato, 40) or "formato del video",
            estilo=_texto(estilo.get("prompt"), 4000) or "(sin indicaciones)",
            guia=guia or "(sin guia escrita)",
            encargo=_texto(encargo, 3000) or "(sin indicaciones)",
            reglas=reglas or "(sin reglas)",
            reglas_estilo=(BLOQUE_REGLAS_ESTILO.format(reglas=reglas_estilo)
                           if reglas_estilo else ""),
            referencia=(_referencia_base(proyecto, tanda, bases)
                        + _referencia_de(proyecto, plan, ids[0], imagenes, bloques, frases)),
            planos=_planos_legibles(proyecto, tanda, imagenes, bloques),
            tipos=" | ".join(TIPOS),
            f_equipo=frases["equipo"], f_congruencia=frases["congruencia"],
            f_manos=frases["manos"], f_orientacion=frases["orientacion"])
        # CON SU AVANCE: es lo que corta la llamada al CLI si alguien cancela
        # el trabajo (lo mata `cli_claude` desde `al_cancelar`). Sin el, cancelar
        # esperaba a que acabara la tanda de ocho, que pueden ser siete minutos.
        avance = estadisticas.Avance(
            avisar, n / len(tandas), (n + 1) / len(tandas),
            {"segundos": 30.0 * len(tanda), "origen": "estimacion"},
            f"revisando {_rango(ids)}")
        avance.arrancar()
        try:
            crudas = None
            for intento in range(2):
                # UNA SEGUNDA VEZ si la respuesta no se pudo leer: el 18-10 la
                # primera prueba de verdad devolvio el JSON y algo mas detras
                # («Extra data»), y se perdio la tanda entera
                texto, _sobre = cli_claude.ejecutar(
                    instruccion if intento == 0 else instruccion + RECORDATORIO_JSON,
                    modelo=modelo, esfuerzo=esfuerzo, cwd=proyecto.raiz,
                    tiempo_max_s=0, base_tiempo_s=TIEMPO_BASE_S, sistema=SISTEMA,
                    herramientas_vetadas=HERRAMIENTAS_VETADAS,
                    herramientas_permitidas=HERRAMIENTAS_PERMITIDAS,
                    extra=["--no-session-persistence"], avance=avance,
                    para=f"el revisor de imágenes ({ids[0]}–{ids[-1]})")
                try:
                    crudas = entradas_de(texto)
                    break
                except RespuestaIlegible:
                    if intento == 1:
                        raise
        except Exception as fallo:                               # noqa: BLE001
            if type(fallo).__name__ == "Cancelado":
                raise
            if avance.cancelado:
                # el corte llego por el avance: `avisar` lanza Cancelado
                avance.parar()
                avisar(n / len(tandas), "cancelado")
                raise
            fallos.append(f"{ids[0]}–{ids[-1]}: {type(fallo).__name__}: {fallo}"[:300])
            continue
        finally:
            avance.parar()
        for cruda in crudas:
            sid, ficha = _limpiar(cruda, set(ids))
            if sid and sid not in salida:
                ficha["huella"] = huella(imagenes[sid])
                salida[sid] = ficha
        # LAS QUE SE CALLO se dicen: si no, «Última revisión: 3 imágenes» en un
        # grupo de 7 no explicaba por que las otras cuatro seguian sin mirar
        calladas = [sid for sid in ids if sid not in salida]
        if calladas:
            fallos.append(f"{', '.join(calladas)}: no dijo nada de "
                          f"{'ella' if len(calladas) == 1 else 'ellas'}; "
                          f"se miran en la próxima revisión")
    if fallos:
        salida["_fallos"] = fallos
    return salida


# ----------------------------------------------------- de veredicto a nota

def _notas_del_revisor(proyecto):
    """{plano: nota pendiente del revisor} (la ultima de cada plano)."""
    salida = {}
    for nota in repaso.leer(proyecto)["notas"]:
        if (nota.get("autor") == AUTOR and repaso.pantalla_de(nota) == "imagenes"
                and nota.get("estado") != "aplicado" and nota.get("plano")):
            salida[str(nota["plano"])] = nota
    return salida


def apuntar(proyecto, plan, veredictos):
    """Lleva los veredictos al repaso y a `revisor.json`. -> resumen

    Un plano a corregir deja SU nota (si ya habia una pendiente del revisor
    para ese plano, se reescribe en vez de sumar otra). Un plano que ahora esta
    bien se lleva por delante la nota pendiente del revisor que tuviera: era de
    una imagen que ya no esta. Las notas de las personas no se tocan nunca.
    """
    t_de = {str(e.get("id")): float(e.get("t_in") or 0.0)
            for e in plan.get("escenas") or []}
    ancla_de = {str(e.get("id")): str(e.get("narracion") or "")
                for e in plan.get("escenas") or []}
    fallos = list(veredictos.get("_fallos") or [])
    with repaso.CERROJO:
        previas = _notas_del_revisor(proyecto)
        estado = leer_estado(proyecto)
        marcadas = []
        for plano, ficha in veredictos.items():
            if plano.startswith("_"):
                continue
            previa = previas.get(plano)
            if ficha["veredicto"] == "corregir":
                if previa:
                    repaso.editar(proyecto, previa["id"], texto=ficha["nota"],
                                  error="", aviso="")
                    nota = repaso.marcar_autor(proyecto, previa["id"], AUTOR,
                                               alcance=ficha["alcance"],
                                               gravedad=ficha["gravedad"])
                else:
                    nota = repaso.anadir(proyecto, ficha["nota"], t_de.get(plano, 0.0),
                                         plano=plano, pantalla="imagenes",
                                         ancla=ancla_de.get(plano, ""), autor=AUTOR,
                                         alcance=ficha["alcance"],
                                         gravedad=ficha["gravedad"])
                marcadas.append({"plano": plano, "nota": nota["id"],
                                 "gravedad": ficha["gravedad"],
                                 "alcance": ficha["alcance"]})
            elif previa:
                try:
                    repaso.borrar(proyecto, previa["id"])
                except KeyError:
                    pass
            estado["revisadas"][plano] = {
                "huella": ficha.get("huella", ""), "veredicto": ficha["veredicto"],
                "gravedad": ficha.get("gravedad", ""),
                "problemas": ficha.get("problemas") or [],
                "fecha": time.strftime("%Y-%m-%dT%H:%M:%S")}
        revisados = [p for p in veredictos if not p.startswith("_")]
        estado["ultima"] = {"fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "revisados": len(revisados),
                            "bien": sum(1 for p in revisados
                                        if veredictos[p]["veredicto"] == "bien"),
                            "marcadas": marcadas, "fallos": fallos}
        guardar_estado(proyecto, estado)
    return estado["ultima"]


def elegir(proyecto, modo, max_imagenes, max_usd, usd_por_imagen, planos=None):
    """Que notas del revisor se rehacen SOLAS en este modo. -> (retoque, sustituye, porque)

    `retoque` y `sustituye` son listas de ids de nota. En «manual» ninguna. En
    «autonomo» solo las de gravedad alta; en «automatico», todas. Siempre
    dentro de los topes: imagenes por pasada, dolares por video (lo ya gastado
    por el revisor cuenta) e intentos por plano.

    `planos` acota a las notas de esos planos: tras una tanda, SOLO las de lo
    que esa tanda dibujo. Sin acotar, una tanda de un plano rehacia notas
    viejas de otros que la persona habia decidido no aplicar.

    Sin precio (`usd_por_imagen` 0: no se ha podido saber) no se rehace nada
    solo: un tope de dolares que no se puede medir no es un tope.
    """
    if modo not in ("autonomo", "automatico"):
        return [], [], "modo manual: el revisor solo apunta"
    estado = leer_estado(proyecto)
    candidatas = sorted(_notas_del_revisor(proyecto).values(),
                        key=lambda n: (GRAVEDADES.index(n.get("gravedad") or "media")
                                       if (n.get("gravedad") or "media") in GRAVEDADES
                                       else 1, float(n.get("t") or 0.0)))
    if planos is not None:
        acotar = {str(p) for p in planos}
        candidatas = [n for n in candidatas if str(n.get("plano")) in acotar]
    if modo == "autonomo":
        candidatas = [n for n in candidatas if n.get("gravedad") == "alta"]
    precio = max(0.0, float(usd_por_imagen or 0.0))
    if precio <= 0:
        return [], [], ("no se sabe lo que cuesta una imagen: el revisor no rehace "
                        "nada solo")
    cupo = max(0, int(max_imagenes or 0))
    restante = max(0.0, float(max_usd or 0.0) - estado["gastado_usd"])
    cupo = min(cupo, int(restante / precio + 1e-9))
    elegidas, topadas, agotadas = [], 0, 0
    for nota in candidatas:
        plano = str(nota["plano"])
        if estado["intentos"].get(plano, 0) >= INTENTOS_POR_PLANO:
            agotadas += 1
            continue
        if len(elegidas) >= cupo:
            topadas += 1
            continue
        elegidas.append(nota)
    porque = []
    if topadas:
        porque.append(f"{topadas} se quedan como nota por el tope de imágenes o de gasto")
    if agotadas:
        porque.append(f"{agotadas} ya se rehicieron {INTENTOS_POR_PLANO} veces y "
                      f"esperan a una persona")
    retoque = [n["id"] for n in elegidas if n.get("alcance") != "sustituye"]
    sustituye = [n["id"] for n in elegidas if n.get("alcance") == "sustituye"]
    return retoque, sustituye, "; ".join(porque)


def contar_intento(proyecto, notas_ids, usd_por_imagen):
    """Apunta que esas notas se mandan a rehacer solas: un intento por plano y
    su coste estimado en lo gastado por el revisor."""
    with repaso.CERROJO:
        planos = {str(n.get("plano")) for n in repaso.leer(proyecto)["notas"]
                  if n.get("id") in set(notas_ids)}
        estado = leer_estado(proyecto)
        for plano in planos:
            estado["intentos"][plano] = estado["intentos"].get(plano, 0) + 1
        estado["gastado_usd"] = round(estado["gastado_usd"]
                                      + len(planos) * float(usd_por_imagen or 0.0), 4)
        guardar_estado(proyecto, estado)
    return len(planos)


def descartar(proyecto, plano):
    """«Esta imagen esta bien así»: quita la nota pendiente del revisor de ese
    plano y la da por revisada con su imagen de ahora."""
    with repaso.CERROJO:
        previa = _notas_del_revisor(proyecto).get(str(plano))
        if previa:
            repaso.borrar(proyecto, previa["id"])
        estado = leer_estado(proyecto)
        ficha = dict(estado["revisadas"].get(str(plano)) or {})
        ficha.update({"veredicto": "bien", "descartada": True,
                      "fecha": time.strftime("%Y-%m-%dT%H:%M:%S")})
        estado["revisadas"][str(plano)] = ficha
        guardar_estado(proyecto, estado)
    return bool(previa)


def resumen(proyecto, imagenes=None):
    """Lo que ensena la pantalla: la ultima revision y lo que falta por mirar."""
    estado = leer_estado(proyecto)
    pendientes = _notas_del_revisor(proyecto)
    return {"ultima": estado["ultima"],
            "gastado_usd": estado["gastado_usd"],
            "pendientes": [{"plano": p, "nota": n["id"],
                            "gravedad": n.get("gravedad") or "media",
                            "alcance": n.get("alcance") or "retoque"}
                           for p, n in sorted(pendientes.items())],
            "sin_revisar": len(sin_revisar(proyecto, imagenes)) if imagenes else None}

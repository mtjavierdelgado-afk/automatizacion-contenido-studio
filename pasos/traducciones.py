"""LO QUE SE MANDA A DIBUJAR, EN ESPAÑOL: traducir para leer y editar sin tocar el inglés.

QUÉ ES
------
Los cambios de cada estado del tipo de relato («floor and all walls in the same
large-format ivory porcelain tile…») y lo que la imagen base ya trae
(`inicial`) se escriben en INGLÉS a propósito: es lo que se le manda al
generador de imágenes, que sigue mejor las instrucciones en inglés. El dueño
los quiere leer y retocar en español (pedido del 22-10-2026). Este módulo hace
las dos direcciones:

    al_espanol([textos en inglés], cwd=None) -> {inglés: español}
    al_ingles(texto en español, anterior="", cwd=None) -> inglés

y guarda lo traducido para no volver a preguntar:

    de(raiz, [textos en inglés]) -> {inglés: español o ""}
    guardar(raiz, {inglés: español})

POR QUÉ UN FICHERO Y NO UN PARAM
--------------------------------
La traducción vive en `<proyecto>/traducciones.json`, FUERA de params y de toda
firma. Es solo para leer: si fuera un param de assets movería su firma y la
pantalla ofrecería rehacer imágenes por haber traducido una frase (regla 1 de
CLAUDE.md). Va por la HUELLA del texto en inglés: si el inglés cambia (Claude
reescribe los cambios, o alguien edita un estado), su traducción vieja deja de
casar sola y se vuelve a pedir. Nunca se enseña una traducción de otro texto.

Va por SUSCRIPCIÓN (el CLI de Claude), con sonnet y poco esfuerzo, como la
ortografía: son frases cortas y la pantalla espera.
"""
import hashlib
import json
import os
import re
import tempfile
import threading

try:
    from . import cli_claude, comun
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun

MODELO = os.environ.get("ESTUDIO_TRADUCIR_MODELO", "sonnet")
ESFUERZO = os.environ.get("ESTUDIO_TRADUCIR_ESFUERZO", "low")
FICHERO = "traducciones.json"
#: Un texto más largo que esto no es un cambio de estado: se recorta al pedir.
MAX_TEXTO = 1200
#: Lo que se pide de una vez. Un vídeo trae dos o tres estados y una línea de
#: `inicial`; el tope es para que un catálogo raro no mande cien frases juntas.
POR_LLAMADA = 30
REINTENTOS_JSON = 1

_LOCK = threading.Lock()


class ErrorTraduccion(RuntimeError):
    """No se ha podido traducir, con el motivo en castellano."""


def _limpio(texto):
    return " ".join(str(texto or "").split())


def huella(texto):
    """La clave de un texto en inglés: espacios aparte, el mismo texto da la misma."""
    return hashlib.sha1(_limpio(texto).encode("utf-8")).hexdigest()[:16]


def ruta(raiz):
    return os.path.join(raiz, FICHERO)


def _leer(raiz):
    try:
        with open(ruta(raiz), encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def de(raiz, textos):
    """{texto en inglés: español guardado, o "" si no hay}. Solo casa si la
    traducción se hizo para ESE texto (se comprueba también el inglés guardado,
    no solo la huella)."""
    guardadas = _leer(raiz)
    salida = {}
    for texto in textos or []:
        limpio = _limpio(texto)
        if not limpio:
            continue
        ficha = guardadas.get(huella(limpio))
        bien = isinstance(ficha, dict) and _limpio(ficha.get("en")) == limpio
        salida[limpio] = _limpio(ficha.get("es")) if bien else ""
    return salida


def faltan(raiz, textos):
    """Los textos en inglés que todavía no tienen traducción guardada."""
    return [t for t, es in de(raiz, textos).items() if not es]


def guardar(raiz, pares):
    """Apunta {inglés: español}. Escribe en un temporal y lo mueve: un corte a
    medias no deja un fichero roto (y si lo dejara, `_leer` lo da por vacío y
    se vuelve a traducir; no se pierde nada que cueste dinero)."""
    pares = {_limpio(en): _limpio(es) for en, es in (pares or {}).items()
             if _limpio(en) and _limpio(es)}
    if not pares:
        return 0
    with _LOCK:
        datos = _leer(raiz)
        for en, es in pares.items():
            datos[huella(en)] = {"en": en, "es": es}
        os.makedirs(raiz, exist_ok=True)
        fd, temporal = tempfile.mkstemp(prefix=".traducciones-", suffix=".json", dir=raiz)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(datos, fh, ensure_ascii=False, indent=2)
            os.replace(temporal, ruta(raiz))
        except BaseException:
            try:
                os.remove(temporal)
            except OSError:
                pass
            raise
    return len(pares)


# ------------------------------------------------------------ inglés -> español

SISTEMA_ES = ("Traduces al español instrucciones visuales para un generador de "
              "imágenes. Contestas únicamente con el JSON pedido.")

INSTRUCCION_ES = """Traduce al ESPAÑOL estas descripciones. Son cambios que se le piden a una
imagen (un espacio que se reforma, se decora o cambia de estado) y las va a
leer una persona que no lee inglés y que tiene que entender EXACTAMENTE qué se
va a dibujar:

- Español neutro y claro, como lo diría un interiorista en Latinoamérica.
- Conserva cada material, color, medida, posición y objeto: no resumas, no
  añadas nada y no quites nada. Las marcas y los nombres propios, igual.
- Términos de obra y acabados con su nombre habitual (porcelanato, mueble
  flotante, mampara, grifería empotrada…).

<traducir_al_espanol>
{textos}
</traducir_al_espanol>

Devuelve SOLO este JSON, con una entrada por cada id:
{{"traducciones": {{"<id>": "<la traduccion>"}}}}"""


def _lote(pares):
    return "\n".join(f'<t id="{i}">{_limpio(t)[:MAX_TEXTO]}</t>' for i, t in pares)


def _pedir_json(instruccion, sistema, que, cwd):
    ultimo = ""
    for _intento in range(1 + REINTENTOS_JSON):
        respuesta, _sobre = cli_claude.ejecutar(
            instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
            base_tiempo_s=120, sistema=sistema,
            extra=["--no-session-persistence"], para=que)
        try:
            datos = comun.extraer_json(respuesta, que)
        except RuntimeError as fallo:
            ultimo = str(fallo)
            continue
        if isinstance(datos, dict):
            return datos
        ultimo = f"{que} no es un objeto JSON"
    raise ErrorTraduccion("Claude devolvió una respuesta que no se ha podido leer; "
                          f"vuelve a pedirla. No se ha cambiado nada.\n\n{ultimo}")


def al_espanol(textos, cwd=None):
    """[inglés] -> {inglés: español}. Solo vuelven los que el modelo tradujo; un
    texto sin traducción se queda fuera (la pantalla enseña el inglés)."""
    unicos = []
    for texto in textos or []:
        limpio = _limpio(texto)
        if limpio and limpio not in unicos:
            unicos.append(limpio)
    salida = {}
    for desde in range(0, len(unicos), POR_LLAMADA):
        trozo = list(enumerate(unicos[desde:desde + POR_LLAMADA]))
        datos = _pedir_json(INSTRUCCION_ES.format(textos=_lote(trozo)), SISTEMA_ES,
                            "la traduccion al espanol", cwd)
        traducciones = datos.get("traducciones")
        if not isinstance(traducciones, dict):
            continue
        for i, texto in trozo:
            es = _limpio(traducciones.get(str(i)))
            if es:
                salida[texto] = es
    return salida


# ------------------------------------------------------------ español -> inglés

SISTEMA_EN = ("You turn a Spanish description into the English change instruction "
              "for an image editor. You answer only with the requested JSON.")

INSTRUCCION_EN = """A person has rewritten, in Spanish, what changes in one state of a room
that is drawn by EDITING a fixed base image (same room, same camera). Turn it
into the English instruction the image editor will receive.

- Say exactly what the Spanish says: every material, colour, position and
  object, nothing more and nothing less. Do not invent details.
- Write it like the previous instruction (below): one concrete sentence or a
  short list of changes, present tense, no camera directions, no people.
- If the Spanish only tweaks the previous instruction, keep the rest of it.

<instruccion_anterior>
{anterior}
</instruccion_anterior>

<pasar_al_ingles>
{texto}
</pasar_al_ingles>

Return ONLY this JSON: {{"ingles": "<the English instruction>"}}"""


def al_ingles(texto, anterior="", cwd=None):
    """El texto en español, pasado a la instrucción en inglés que se manda. Lanza
    `ErrorTraduccion` si no sale nada."""
    limpio = _limpio(texto)[:MAX_TEXTO]
    if not limpio:
        raise ErrorTraduccion("escribe el cambio en español antes de guardarlo")
    datos = _pedir_json(INSTRUCCION_EN.format(anterior=_limpio(anterior)[:MAX_TEXTO] or "(none)",
                                              texto=limpio),
                        SISTEMA_EN, "el paso al ingles", cwd)
    ingles = _limpio(datos.get("ingles"))[:400]
    if not ingles or not re.search(r"[A-Za-z]", ingles):
        raise ErrorTraduccion("Claude no ha devuelto el cambio en inglés; vuelve a "
                              "intentarlo. No se ha cambiado nada.")
    return ingles

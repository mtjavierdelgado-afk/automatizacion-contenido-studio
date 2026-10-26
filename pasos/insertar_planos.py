"""INSERTAR UNA IMAGEN NUEVA DENTRO DE UN PLANO (rama insertar-imagen, 26-10-2026).

QUÉ ES
------
Lo contrario de quitar (`pasos/quitar_planos.py`). Pedido del dueño: una frase
larga se queda con una sola imagen y le falta algo (el «antes» del baño, el
detalle que se nombra). Se elige la PALABRA de la frase donde empieza la
imagen nueva y se escribe en español qué se tiene que ver:

    S004 «Este baño era el más feo | con baldosas grises»
      ->  S004  «Este baño era el más feo»   (su dibujo de siempre)
          S004B «con baldosas grises»        (la nueva, se dibuja y se paga)

    leer(raiz) -> [{"texto", "n", "palabra", "id", "que", "direccion"}]
    insertar(raiz, texto, n, palabra, ...) / deshacer(raiz, texto, n, palabra)
    aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte)

CÓMO SE GUARDA
--------------
En `<proyecto>/planos_insertados.json`, FUERA de params, por lo mismo que lo
quitado (ver su docstring): un param global movería la firma de todos los
planos, y uno por unidad movería la del plano que se parte y su imagen ya
pagada saldría obsoleta. Cada entrada se reconoce por EL TEXTO del plano que
se parte y por cuántos planos antes dicen lo mismo (`n`), no por su número.

Lo que se ve en la nueva va en INGLÉS en `direccion` (lo pasa Claude desde el
español de `que`), y entra en su prompt como la dirección del plano: es lo que
la hace distinta de su vecina. El español se guarda para enseñarlo.

CÓMO SE PARTE
-------------
Lo aplica `p6_assets.planificar`, DESPUÉS de escribir los prompts y ANTES de
quitar planos. El plano partido conserva su prompt y su `narracion_imagen`
(la frase entera para la que se dibujó), así que su PNG no se mueve ni sale
obsoleto; se queda con las palabras de antes del corte. La nueva es una copia
del plano (el mismo sitio, reparto, luz y estado) con las palabras de después,
SIN rótulos, con su dirección y con un prompt nuevo que escribe `preparar`.
Su id es el del plano con una letra (S004B, S004C...): no se renumera nada, y
las notas apuntadas a S005 siguen en S005.

Sin fichero, nada cambia.
"""
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
#: La dirección en inglés: una frase de plano, como las de `direccion`
MAX_DIRECCION = 400

FICHERO = "planos_insertados.json"
#: Lo que se ve en la nueva, en español: lo bastante para un plano, no un guion
MAX_QUE = 400
LETRAS = "BCDEFGHIJ"

_LOCK = threading.Lock()


def ruta(raiz):
    return os.path.join(raiz, FICHERO)


def _entero(valor, minimo=0):
    try:
        return max(minimo, int(valor))
    except (TypeError, ValueError):
        return None


def leer(raiz):
    """Las entradas guardadas (las rotas o raras se ignoran)."""
    try:
        with open(ruta(raiz), encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return []
    salida = []
    for entrada in (datos or {}).get("insertados") or [] if isinstance(datos, dict) else []:
        if not isinstance(entrada, dict):
            continue
        texto = str(entrada.get("texto") or "").strip()
        palabra = _entero(entrada.get("palabra"), 1)
        direccion = " ".join(str(entrada.get("direccion") or "").split())
        if not texto or not palabra or not direccion:
            continue
        letra = str(entrada.get("letra") or "")
        salida.append({"texto": texto, "n": _entero(entrada.get("n")) or 0, "palabra": palabra,
                       "id": str(entrada.get("id") or ""),
                       "letra": letra if len(letra) == 1 and letra in LETRAS else "",
                       "que": " ".join(str(entrada.get("que") or "").split())[:MAX_QUE],
                       "direccion": direccion})
    return salida


def _escribir(raiz, entradas):
    os.makedirs(raiz, exist_ok=True)
    if not entradas:
        try:
            os.remove(ruta(raiz))
        except FileNotFoundError:
            pass
        return
    fd, temporal = tempfile.mkstemp(prefix=".insertados-", suffix=".json", dir=raiz)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"insertados": entradas}, fh, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta(raiz))
    except BaseException:
        try:
            os.remove(temporal)
        except OSError:
            pass
        raise


def _llave(entrada):
    return (entrada["texto"], entrada["n"], entrada["palabra"])


def letra_libre(entradas, texto, n):
    """La letra de la siguiente imagen insertada en ese plano: la primera que no
    lleve otra. Va guardada en la entrada, así que una imagen nueva más arriba
    en la frase no le cambia el nombre (ni la unidad) a las de antes."""
    usadas = {e.get("letra") for e in entradas if (e["texto"], e["n"]) == (texto, n)}
    return next((l for l in LETRAS if l not in usadas), "")


def insertar(raiz, texto, n, palabra, sid="", que="", direccion="", letra=""):
    """Apunta una imagen nueva en el plano que dice `texto` (la `n`-ésima vez),
    desde su palabra número `palabra` (0 = la primera; tiene que ser >= 1).
    -> las entradas tal como quedan."""
    texto = str(texto or "").strip()
    palabra = _entero(palabra, 0)
    direccion = " ".join(str(direccion or "").split())
    if not texto:
        raise ValueError("ese plano no dice nada: no se puede reconocer después")
    if not palabra:
        raise ValueError("la imagen nueva tiene que empezar después de la primera palabra")
    if not direccion:
        raise ValueError("falta lo que se ve en la imagen nueva")
    entrada = {"texto": texto, "n": _entero(n) or 0, "palabra": palabra, "id": str(sid or ""),
               "que": " ".join(str(que or "").split())[:MAX_QUE], "direccion": direccion}
    with _LOCK:
        entradas = [e for e in leer(raiz) if _llave(e) != _llave(entrada)]
        entrada["letra"] = (letra if letra in LETRAS and len(letra) == 1
                            else letra_libre(entradas, entrada["texto"], entrada["n"]))
        if not entrada["letra"]:
            raise ValueError("este plano ya tiene todas las imágenes insertadas que admite")
        entradas.append(entrada)
        _escribir(raiz, entradas)
    return entradas


def deshacer(raiz, texto, n, palabra):
    """Quita la imagen insertada. -> la entrada que había, o None."""
    llave = (str(texto or "").strip(), _entero(n) or 0, _entero(palabra, 0))
    with _LOCK:
        entradas = leer(raiz)
        fuera = [e for e in entradas if _llave(e) == llave]
        if not fuera:
            return None
        _escribir(raiz, [e for e in entradas if e not in fuera])
    return fuera[0]


def reponer(raiz, entradas):
    """Deja el fichero exactamente con `entradas` (deshacer un intento fallido)."""
    with _LOCK:
        _escribir(raiz, list(entradas or []))


def palabras_de(escena):
    """Las palabras del plano si se puede partir por ellas: tantas como marcas
    de tiempo. Si no cuadran, [] (no se sabe en qué segundo cae cada una)."""
    palabras = str((escena or {}).get("narracion") or "").split()
    marcas = (escena or {}).get("marcas") or []
    return palabras if len(palabras) >= 2 and len(palabras) == len(marcas) else []


def se_puede_partir(escenas, i, sin_imagen):
    """Si el plano `i` admite una imagen insertada: una imagen normal (ni
    cartela, ni continuación de otro, ni con su continuación detrás, ni ya
    insertada, ni con voz de un quitado) con al menos dos palabras medidas."""
    escena = escenas[i] if 0 <= i < len(escenas) else None
    if not escena or sin_imagen(escena) or escena.get("cartela") or escena.get("sigue_a"):
        return False
    if escena.get("insertada") or escena.get("absorbe") or escena.get("partida_en"):
        return False
    if i + 1 < len(escenas) and escenas[i + 1].get("sigue_a") == escena.get("id"):
        return False
    return bool(palabras_de(escena))


def _trozo(escena, desde, hasta, palabras, marcas):
    escena["narracion"] = " ".join(palabras[desde:hasta])
    escena["marcas"] = [list(m) for m in marcas[desde:hasta]]


def _partir(escena, cortes, palabras, tipo_de_corte):
    """Parte `escena` (EN SITIO, se queda la primera parte) por las palabras de
    `cortes` (ordenados). -> [(nueva, entrada)] en orden."""
    marcas = [list(m) for m in escena.get("marcas") or []]
    t_out, corte_final = escena["t_out"], escena.get("corte")
    escena.setdefault("narracion_imagen", escena.get("narracion") or "")
    limites = [k for k, _e in cortes] + [len(palabras)]
    usadas = {e.get("letra") for _k, e in cortes if e.get("letra")}
    libres = [l for l in LETRAS if l not in usadas]
    nuevas = []
    for orden, (k, entrada) in enumerate(cortes):
        nueva = json.loads(json.dumps(escena))
        nueva["id"] = f"{escena['id']}{entrada.get('letra') or libres.pop(0)}"
        _trozo(nueva, k, limites[orden + 1], palabras, marcas)
        nueva["t_in"] = round(float(marcas[k][0]), 3)
        fin = limites[orden + 1]
        nueva["t_out"] = (t_out if fin == len(palabras)
                          else round(float(marcas[fin][0]), 3))
        nueva["corte"] = (corte_final if fin == len(palabras)
                          else tipo_de_corte(palabras[fin - 1]))
        for clave in ("narracion_imagen", "redactado", "capa_vectorial", "hereda_de",
                      "absorbe", "partida_en"):
            nueva.pop(clave, None)
        nueva["capa_vectorial"] = []
        nueva["direccion"] = entrada["direccion"]
        nueva["insertada"] = {"en": escena["id"], "texto": entrada["texto"], "n": entrada["n"],
                              "palabra": entrada["palabra"], "que": entrada.get("que") or ""}
        nuevas.append(nueva)
    primero = cortes[0][0]
    _trozo(escena, 0, primero, palabras, marcas)
    escena["t_out"] = round(float(marcas[primero][0]), 3)
    escena["corte"] = tipo_de_corte(palabras[primero - 1])
    escena["partida_en"] = [n["id"] for n in nuevas]
    for nueva in nuevas + [escena]:
        nueva["duracion"] = round(float(nueva["t_out"]) - float(nueva["t_in"]), 3)
    return nuevas


def aplicar(escenas, raiz, clave, sin_imagen, preparar, tipo_de_corte):
    """Mete en `escenas` (EN SITIO) las imágenes apuntadas. `clave(escena)`:
    el texto con el que se reconoce un plano; `preparar(nueva, partida)`
    escribe el prompt de la nueva; `tipo_de_corte(palabra)` el corte de
    salida de cada trozo.

    -> {"insertados": [ids nuevos], "sin_casar": [entradas que no casan]}.
    Sin fichero no toca nada."""
    entradas = leer(raiz) if raiz else []
    salida = {"insertados": [], "sin_casar": []}
    if not entradas or not escenas:
        salida["sin_casar"] = list(entradas)
        return salida
    pendientes = list(entradas)
    vistos = {}
    i = 0
    while i < len(escenas):
        escena = escenas[i]
        texto = clave(escena)
        n = vistos.get(texto, 0)
        vistos[texto] = n + 1
        suyas = [e for e in pendientes if (e["texto"], e["n"]) == (texto, n)]
        palabras = palabras_de(escena)
        if not suyas or not se_puede_partir(escenas, i, sin_imagen):
            i += 1
            continue
        validas = {}
        for entrada in suyas:
            if 1 <= entrada["palabra"] < len(palabras):
                validas.setdefault(entrada["palabra"], entrada)
        if not validas:
            i += 1
            continue
        for entrada in validas.values():
            pendientes.remove(entrada)
        nuevas = _partir(escena, sorted(validas.items()), palabras, tipo_de_corte)
        for nueva in nuevas:
            preparar(nueva, escena)
        escenas[i + 1:i + 1] = nuevas
        salida["insertados"].extend(n["id"] for n in nuevas)
        i += 1 + len(nuevas)
    salida["sin_casar"] = pendientes
    return salida


# ------------------------------------------- lo que se ve, del español al inglés

class ErrorDireccion(RuntimeError):
    """No se ha podido pasar al inglés, con el motivo en castellano."""


SISTEMA = ("You turn a Spanish description of one new shot into the English shot "
           "direction for an image generator. You answer only with the requested JSON.")

INSTRUCCION = """A person is inserting a NEW image into a narrated video, between two parts of
one sentence. The new image shows what they describe in Spanish below. Write
the English shot direction for it, the way a director writes one line per shot:

- Say exactly what the Spanish says: subject, action, objects, materials,
  colours. Do not invent anything else.
- Start with the shot type (wide shot, medium shot, close-up, detail shot...):
  the one the Spanish asks for, or the one that best shows it.
- It is the same place and the same moment as the image it comes from (below),
  so do not describe the place again unless the Spanish changes it.
- One or two sentences, present tense. No style words, no camera brands.

<imagen_de_la_que_sale>
{prompt}
</imagen_de_la_que_sale>

<lo_que_se_oye>
{narracion}
</lo_que_se_oye>

<imagen_nueva>
{que}
</imagen_nueva>

Return ONLY this JSON: {{"direccion": "<the English shot direction>"}}"""


def al_ingles(que, prompt="", narracion="", cwd=None):
    """Lo que se ve, escrito en español, pasado a la dirección en inglés de
    la imagen nueva. Lanza `ErrorDireccion` si no sale nada utilizable."""
    limpio = " ".join(str(que or "").split())[:MAX_QUE]
    if not limpio:
        raise ErrorDireccion("escribe qué quieres que se vea en la imagen nueva")
    instruccion = INSTRUCCION.format(prompt=" ".join(str(prompt or "").split())[:1500] or "(none)",
                                     narracion=" ".join(str(narracion or "").split())[:600] or "(none)",
                                     que=limpio)
    ultimo = ""
    for _intento in range(2):
        respuesta, _sobre = cli_claude.ejecutar(
            instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd, base_tiempo_s=120,
            sistema=SISTEMA, extra=["--no-session-persistence"], para="la imagen nueva")
        try:
            datos = comun.extraer_json(respuesta, "la imagen nueva")
        except RuntimeError as fallo:
            ultimo = str(fallo)
            continue
        direccion = " ".join(str((datos or {}).get("direccion") or "").split()) \
            if isinstance(datos, dict) else ""
        if not direccion or not re.search(r"[A-Za-z]", direccion):
            raise ErrorDireccion("Claude no ha devuelto la imagen nueva en inglés; vuelve a "
                                 "intentarlo. No se ha cambiado nada.")
        if len(direccion) > MAX_DIRECCION:
            raise ErrorDireccion("lo que se ve es demasiado largo para una imagen: escríbelo "
                                 "más corto. No se ha cambiado nada.")
        return direccion
    raise ErrorDireccion("Claude devolvió una respuesta que no se ha podido leer; vuelve a "
                         f"intentarlo. No se ha cambiado nada.\n\n{ultimo}")

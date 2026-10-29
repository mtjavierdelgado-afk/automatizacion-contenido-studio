"""¿CHOCAN LAS REGLAS DEL NEGOCIO CON LAS DEL ESTILO? (rama reglas-claras, 28-10-2026)

POR QUE
-------
Cada imagen de foto lleva dos listas de reglas a la vez: las de la FICHA DEL
NEGOCIO de su proyecto (valen para todos sus estilos de foto) y las PROPIAS del
estilo. El dueño tenía «la tele en su trípode o sobre un mueble» en la ficha y
«nunca sobre un mueble» en el estilo, y en pantalla no había forma de verlo.

DOS CAPAS
---------
- `hablan_de_lo_mismo`: la pista GRATIS, sin IA. Pares que comparten palabras
  («tele», «trípode», «mueble»): «léelas juntas». No sabe si se contradicen y
  nunca lo dice. La pantalla tiene su copia en JavaScript (`paresQueHablanDeLoMismo`
  en `web/app.js`), que es la que se ve; esta sirve al doble de Claude.
- `revisar`: Claude (la membresía, por el CLI) compara las dos listas y señala
  los pares que se contradicen o se repiten, con una frase de qué cambiar.

Y NO ESCRIBE NADA: ni en el estilo, ni en la ficha, ni en ningún vídeo. Solo
lee y contesta; lo que cambie lo cambia la persona a mano. Nada de esto entra
en un prompt ni en una firma (regla 1 de CLAUDE.md).
"""
import os
import re
import time
import unicodedata

try:
    from . import cli_claude, comun
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun

TIPOS = ("contradicen", "repiten")
MAX_PARES = 12
MAX_FRASE = 400

#: Comparar dos listas cortas pide segundos, no el defecto del canal.
MODELO = "sonnet"
ESFUERZO = "medium"
TIEMPO_MAX_S = 150

# Palabras que salen en casi cualquier regla y no dicen de qué habla.
_VACIAS = {
    "nunca", "siempre", "solo", "sola", "solos", "solas", "cada", "sobre", "como",
    "para", "entre", "plano", "planos", "imagen", "imagenes", "foto", "fotos",
    "todo", "toda", "todos", "todas", "tiene", "tienen", "debe", "deben", "esta",
    "este", "estos", "estas", "esto", "algo", "nada", "donde", "cuando", "aunque",
    "desde", "hasta", "hacia", "mismo", "misma", "otro", "otra", "otros", "otras",
    "pero", "porque", "parece", "parecen", "real", "reales", "verdad", "cosa",
    "cosas", "estan", "esten", "sean", "sera", "hace", "hacen", "lleva", "llevan",
    "va", "van", "dos", "tres", "con", "sin", "mas", "muy", "bien", "regla",
}


def _llano(texto):
    sin = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


def raices(texto):
    """Las raíces de las palabras con contenido de un texto. -> set

    Cinco letras de cada palabra de cuatro o más: «mandos» y «mando» casan,
    «trípode» y «tripodes» también."""
    salida = set()
    for palabra in re.findall(r"[a-zñ]+", _llano(texto)):
        if len(palabra) >= 4 and palabra not in _VACIAS:
            salida.add(palabra[:5])
    return salida


def _palabra_visible(texto, raiz):
    """La primera palabra del texto con esa raíz, para enseñarla."""
    for palabra in re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", str(texto or "")):
        if _llano(palabra)[:5] == raiz and len(palabra) >= 4:
            return palabra.lower()
    return raiz


def hablan_de_lo_mismo(negocio, estilo, minimo=2):
    """Los pares (negocio, estilo) que comparten al menos `minimo` palabras.

    -> [{negocio: i, estilo: j, palabras: [str]}], índices desde 0."""
    pares = []
    for i, rn in enumerate(negocio or []):
        tn = (rn or {}).get("texto") or ""
        rz_n = raices(tn)
        for j, re_ in enumerate(estilo or []):
            te = (re_ or {}).get("texto") or ""
            comunes = sorted(rz_n & raices(te))
            if len(comunes) >= minimo:
                pares.append({"negocio": i, "estilo": j,
                              "palabras": [_palabra_visible(tn, r) for r in comunes]})
    return pares


# ------------------------------------------------------------------ con Claude

SISTEMA = ("Eres director de fotografía y revisas reglas de un generador de "
           "imágenes. Responde exclusivamente con el objeto JSON pedido, sin "
           "texto alrededor y sin vallas de markdown.")

INSTRUCCION = """Cada imagen de un estilo de foto recibe A LA VEZ dos listas de reglas:

LAS DEL NEGOCIO (valen para todos los estilos del proyecto):
{negocio}

LAS DE ESTE ESTILO (valen solo para este estilo):
{estilo}

Busca SOLO pares (una del negocio y una del estilo) que:
  - "contradicen": no se pueden cumplir las dos a la vez en la misma imagen
    (una permite o pide lo que la otra prohíbe).
  - "repiten": piden lo mismo con otras palabras (sobra una).
Una regla que solo es más concreta que otra NO es un choque. Si no hay
ninguno, devuelve la lista vacía. No inventes reglas que no están.

Devuelve un objeto JSON:
  "pares": lista de objetos con
     "tipo"         "contradicen" o "repiten"
     "negocio"      el número de la regla del negocio (N1, N2… -> 1, 2…)
     "estilo"       el número de la regla del estilo (E1, E2… -> 1, 2…)
     "por_que"      una frase en español sencillo: en qué chocan
     "que_cambiar"  una frase en español sencillo: qué cambiar y dónde. Lo que
                    vale para todo el cliente va en la ficha del negocio; lo
                    específico de este estilo, en el estilo.
"""


def _lista(reglas, letra):
    lineas = []
    for i, r in enumerate(reglas):
        texto = " ".join(str((r or {}).get("texto") or "").split())[:800]
        cuando = (f" (solo si el plano habla de: {', '.join(r['palabras'])})"
                  if (r or {}).get("palabras") else "")
        lineas.append(f"  {letra}{i + 1}. {texto}{cuando}")
    return "\n".join(lineas) or "  (ninguna)"


def _frase(valor):
    return " ".join(str(valor or "").split())[:MAX_FRASE]


def limpiar(datos, n_negocio, n_estilo):
    """Lo que vale de la respuesta: tipos conocidos, índices que existen, sin
    pares repetidos. Índices de la respuesta desde 1; los de salida, desde 0.

    -> [{tipo, negocio, estilo, por_que, que_cambiar}]"""
    crudos = (datos or {}).get("pares") if isinstance(datos, dict) else None
    salida, vistos = [], set()
    for p in crudos if isinstance(crudos, list) else []:
        if not isinstance(p, dict) or p.get("tipo") not in TIPOS:
            continue
        try:
            i, j = int(p.get("negocio")) - 1, int(p.get("estilo")) - 1
        except (TypeError, ValueError):
            continue
        if not (0 <= i < n_negocio and 0 <= j < n_estilo) or (i, j) in vistos:
            continue
        vistos.add((i, j))
        salida.append({"tipo": p["tipo"], "negocio": i, "estilo": j,
                       "por_que": _frase(p.get("por_que")),
                       "que_cambiar": _frase(p.get("que_cambiar"))})
        if len(salida) >= MAX_PARES:
            break
    return salida


def simulando():
    return str(os.environ.get("ESTUDIO_SIMULAR", "")).strip().lower() in ("1", "si", "true")


def _simulado(negocio, estilo):
    """El doble de Claude: ni CLI ni cupo. Cada par que comparte palabras sale
    como choque (el primero «contradicen», el resto «repiten")."""
    pares = []
    for k, p in enumerate(hablan_de_lo_mismo(negocio, estilo)):
        pares.append({"tipo": "contradicen" if k == 0 else "repiten",
                      "negocio": p["negocio"] + 1, "estilo": p["estilo"] + 1,
                      "por_que": "(simulado) hablan de " + ", ".join(p["palabras"]),
                      "que_cambiar": "(simulado) deja la regla en un solo sitio"})
    return {"pares": pares}


def revisar(negocio, estilo, cwd=None):
    """Claude compara las dos listas. -> {pares, segundos, simulado}. Levanta
    si falla. No escribe nada."""
    negocio = [r for r in negocio or [] if str((r or {}).get("texto") or "").strip()]
    estilo = [r for r in estilo or [] if str((r or {}).get("texto") or "").strip()]
    if not negocio or not estilo:
        raise ValueError("hacen falta reglas en las dos listas para compararlas")
    arranque = time.time()
    if simulando():
        datos = _simulado(negocio, estilo)
    else:
        modelo = cli_claude.normalizar_modelo(os.environ.get("ESTUDIO_CHOQUES_MODELO"),
                                              defecto=MODELO)
        esfuerzo = cli_claude.normalizar_esfuerzo(os.environ.get("ESTUDIO_CHOQUES_ESFUERZO"),
                                                  defecto=ESFUERZO)
        texto, _sobre = cli_claude.ejecutar(
            INSTRUCCION.format(negocio=_lista(negocio, "N"), estilo=_lista(estilo, "E")),
            modelo=modelo, esfuerzo=esfuerzo, cwd=cwd,
            tiempo_max_s=TIEMPO_MAX_S, sistema=SISTEMA,
            herramientas_vetadas=("Bash", "Write", "Edit", "NotebookEdit", "Read",
                                  "Grep", "Glob", "WebFetch", "WebSearch", "Task",
                                  "TodoWrite"),
            extra=["--no-session-persistence"],
            para="revisar si chocan las reglas del negocio y del estilo")
        datos = comun.extraer_json(texto, "la revisión de las reglas")
    return {"pares": limpiar(datos, len(negocio), len(estilo)),
            "segundos": round(time.time() - arranque, 1), "simulado": simulando()}

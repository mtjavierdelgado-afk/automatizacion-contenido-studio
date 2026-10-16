"""COMO SE PRONUNCIA: las palabras que la voz lee mal, escritas como suenan.

El video se graba entero con `language=es`, asi que Cartesia lee las palabras
en ingles con fonetica castellana: «Just Dance» sale «just dánse», «Logitech»
sale «lo-gi-tech». Cartesia tiene diccionarios de pronunciacion, pero son un
buscar y reemplazar ANTES del modelo, y eso se puede hacer aqui igual, con una
lista que el dueño ve y edita en Configuracion, sin depender de un id guardado
en la cuenta de Cartesia (15-10-2026).

Lo delicado no es reemplazar: es que TODO lo de despues --el reparto de marcas
entre bloques, los cortes de plano, los subtitulos-- empareja palabra a palabra
lo que dice el guion con lo que devuelve Cartesia. «PlayStation» (una palabra
escrita) dicho «Pléi Estéishon» (dos habladas) desplazaria cada corte siguiente.
Por eso hay dos mitades:

    aplicar(texto, lista)       lo que se MANDA a Cartesia: la palabra escrita
                                cambiada por como suena (fuera de las etiquetas)
    devolver(palabras, lista)   lo que VUELVE: las marcas de la forma dicha se
                                juntan otra vez en la escrita, con sus tiempos

El guion, los subtitulos y la revision siguen viendo «PlayStation». Solo cambia
lo que se oye. La lista vive FUERA del codigo (junto a ajustes.json), para que
`asvs actualizar` no se la lleve.
"""
import json
import os
import re
import unicodedata

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ruta():
    """Donde se guarda la lista: al lado de los ajustes del servidor."""
    propia = os.environ.get("ESTUDIO_PRONUNCIACIONES")
    if propia:
        return propia
    ajustes = os.environ.get("ESTUDIO_AJUSTES") or os.path.join(RAIZ_ESTUDIO, "ajustes.json")
    return os.path.join(os.path.dirname(os.path.abspath(ajustes)), "pronunciaciones.json")


#: La lista de partida, mientras no se guarde otra. Son las marcas que salen en
#: los videos de EstadoPlay y que la voz leia mal (el bloque de los extras:
#: «simrace con volante Logitech, lentes Meta Quest tres S, Just Dance»). Se
#: escriben con la ortografia castellana del sonido ingles; la tilde marca el
#: golpe de voz. Se cambian en Configuracion: es una propuesta, no una regla.
INICIAL = [
    {"escrito": "PlayStation", "dicho": "Pléi Estéishon"},
    {"escrito": "Xbox", "dicho": "Équis Box"},
    {"escrito": "Nintendo Switch", "dicho": "Nintendo Suích"},
    {"escrito": "Switch", "dicho": "Suích"},
    {"escrito": "Meta Quest", "dicho": "Meta Cuést"},
    {"escrito": "Quest", "dicho": "Cuést"},
    {"escrito": "Just Dance", "dicho": "Yast Dans"},
    {"escrito": "Logitech", "dicho": "Lóyitec"},
    {"escrito": "simrace", "dicho": "sim réis"},
    {"escrito": "sim racing", "dicho": "sim réising"},
    {"escrito": "gaming", "dicho": "guéiming"},
    {"escrito": "gamer", "dicho": "guéimer"},
    {"escrito": "gamers", "dicho": "guéimers"},
    {"escrito": "Mario Kart", "dicho": "Mario Cart"},
    {"escrito": "Fortnite", "dicho": "Fórtnait"},
    {"escrito": "Minecraft", "dicho": "Máincraft"},
    {"escrito": "streaming", "dicho": "estríming"},
]

#: Topes, para que la lista siga siendo una lista y no un segundo guion.
MAXIMO = 300
LARGO_MAXIMO = 60


def validar(lista):
    """La lista tal y como se puede guardar, o ValueError con el motivo."""
    if not isinstance(lista, list):
        raise ValueError("la lista de pronunciaciones es una lista")
    if len(lista) > MAXIMO:
        raise ValueError(f"como mucho {MAXIMO} palabras")
    limpia, vistas = [], set()
    for fila in lista:
        if not isinstance(fila, dict):
            raise ValueError("cada fila lleva «escrito» y «dicho»")
        escrito = " ".join(str(fila.get("escrito") or "").split())
        dicho = " ".join(str(fila.get("dicho") or "").split())
        if not escrito and not dicho:
            continue
        if not escrito or not dicho:
            raise ValueError(f"«{escrito or dicho}»: falta cómo se escribe o cómo suena")
        if len(escrito) > LARGO_MAXIMO or len(dicho) > LARGO_MAXIMO:
            raise ValueError(f"«{escrito}»: como mucho {LARGO_MAXIMO} letras")
        # una etiqueta dentro se mandaria a Cartesia, y lo que no reconoce lo LEE
        if re.search(r"[<>]", escrito + dicho):
            raise ValueError(f"«{escrito}»: sin «<» ni «>»")
        if not _tokens(escrito) or not _tokens(dicho):
            raise ValueError(f"«{escrito}»: tiene que llevar letras")
        clave = escrito.lower()
        if clave in vistas:
            raise ValueError(f"«{escrito}» está dos veces")
        vistas.add(clave)
        limpia.append({"escrito": escrito, "dicho": dicho})
    return limpia


def cargar():
    """La lista guardada, o la de partida si nunca se guardo ninguna."""
    try:
        with open(ruta(), "r", encoding="utf-8") as fh:
            datos = json.load(fh)
        return validar(datos.get("lista") if isinstance(datos, dict) else datos)
    except FileNotFoundError:
        return [dict(fila) for fila in INICIAL]
    except (OSError, ValueError):
        # un fichero roto no puede dejar sin voz al video: se graba sin lista
        return []


def guardar(lista):
    """Guarda la lista (validada) y la devuelve."""
    limpia = validar(lista)
    destino = ruta()
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    temporal = destino + ".tmp"
    with open(temporal, "w", encoding="utf-8") as fh:
        json.dump({"lista": limpia}, fh, ensure_ascii=False, indent=1)
    os.replace(temporal, destino)
    return limpia


# ------------------------------------------------------------------ aplicar

def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def _norma(palabra):
    """Como se comparan las palabras: sin puntuacion, sin tildes, en minuscula.
    Sin tildes porque Cartesia puede devolver la palabra dicha sin la tilde que
    le pusimos para marcar el golpe de voz."""
    return re.sub(r"[^\w]", "", _sin_tildes(str(palabra or "")).lower())


def _tokens(texto):
    return [t for t in (_norma(x) for x in str(texto or "").split()) if t]


def _patron(escrito):
    """La palabra (o frase) escrita, entera y sin distinguir mayusculas."""
    partes = [re.escape(p) for p in escrito.split()]
    return re.compile(r"(?<![\w])" + r"\s+".join(partes) + r"(?![\w])", re.IGNORECASE)


_ETIQUETA = re.compile(r"(<spell>.*?</spell>|<[^<>]*>)", re.IGNORECASE | re.DOTALL)


def aplicar(texto, lista):
    """El texto que se MANDA a Cartesia: cada palabra de la lista, como suena.

    Las mas largas primero («Nintendo Switch» antes que «Switch»), y nunca dentro
    de una etiqueta: ni en `<break time=...>` ni en lo que va a deletrearse con
    `<spell>`.
    """
    texto = str(texto or "")
    if not lista or not texto.strip():
        return texto
    orden = sorted(lista, key=lambda f: -len(f["escrito"]))
    trozos = _ETIQUETA.split(texto)
    for i in range(0, len(trozos), 2):                  # los pares son texto
        trozo = trozos[i]
        # se marca lo ya cambiado para que una palabra mas corta no lo vuelva a tocar
        marcas = []
        for fila in orden:
            def poner(m, fila=fila):
                marcas.append(fila["dicho"])
                return f"\x00{len(marcas) - 1}\x00"
            trozo = _patron(fila["escrito"]).sub(poner, trozo)
        trozos[i] = re.sub(r"\x00(\d+)\x00", lambda m: marcas[int(m.group(1))], trozo)
    return "".join(trozos)


# ------------------------------------------------------------------ devolver

def _puntuacion(palabra):
    """(lo de delante, lo de detras) que no son letras: «¡Hola,» -> («¡», «,»)."""
    texto = str(palabra or "")
    delante = re.match(r"^[^\w]*", texto).group(0)
    detras = re.search(r"[^\w]*$", texto[len(delante):]).group(0)
    return delante, detras


def devolver(palabras, lista):
    """Las marcas de Cartesia con la palabra ESCRITA donde se dijo otra cosa.

    Donde vuelve la forma dicha («Pléi», «Estéishon») se pone la escrita
    («PlayStation»), con el tiempo de principio de la primera y el de final de
    la ultima; si la escrita tiene varias palabras, el tramo se reparte a partes
    iguales. La puntuacion pegada se conserva. Lo demas, tal cual.
    """
    if not lista or not palabras:
        return palabras
    formas = []
    for fila in lista:
        dichas, escritas = _tokens(fila["dicho"]), fila["escrito"].split()
        if dichas and escritas:
            formas.append((dichas, escritas))
    formas.sort(key=lambda f: -len(f[0]))
    salida, i = [], 0
    while i < len(palabras):
        encontrada = None
        for dichas, escritas in formas:
            m = len(dichas)
            if i + m <= len(palabras) and all(
                    _norma(palabras[i + k].get("w")) == dichas[k] for k in range(m)):
                encontrada = (m, escritas)
                break
        if not encontrada:
            salida.append(palabras[i])
            i += 1
            continue
        m, escritas = encontrada
        primera, ultima = palabras[i], palabras[i + m - 1]
        delante, _ = _puntuacion(primera.get("w"))
        _, detras = _puntuacion(ultima.get("w"))
        inicio, fin = float(primera.get("s") or 0.0), float(ultima.get("e") or 0.0)
        paso = (fin - inicio) / len(escritas)
        for k, escrita in enumerate(escritas):
            ficha = dict(primera)
            ficha["w"] = (delante if k == 0 else "") + escrita + (detras if k == len(escritas) - 1 else "")
            ficha["s"] = round(inicio + paso * k, 3)
            ficha["e"] = round(inicio + paso * (k + 1), 3) if k < len(escritas) - 1 else ultima.get("e")
            salida.append(ficha)
        i += m
    return salida

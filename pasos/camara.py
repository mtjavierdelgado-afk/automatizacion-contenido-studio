"""La CAMARA de cada plano y el MONTAJE del video: cuanto se mueve, como corta.

    trayecto = camara.trayecto_de(escena, indice, montaje, ...)   # p7, al hacer la capa
    caja = camara.ventana_en_t(mov, t, tamano, aspecto)            # p7 y quien mapee capturas

POR QUE EXISTE (18-10-2026)
---------------------------
Hasta hoy cada plano tenia UN movimiento: acercarse o alejarse un 5 %, despacio
y al centro (`segmentar.alternar_zoom`, ajustado el 20-08 para documentales
largos: «empujar el plano sin que se vea empujar»). En un Reel de 30-60 s eso
no se percibe y el video se ve plano. El dueno pidio que los videos, sobre todo
los cortos, se movieran: niveles de movimiento, reencuadres dentro de un plano
largo, un golpe de zoom en la palabra clave y un gancho en el primer segundo.

LO DE SIEMPRE NO SE TOCA. Sin `montaje` (o con movimiento «sobrio») no sale
ningun trayecto, el movimiento.json de cada plano es el de antes y la pagina
del render pinta exactamente lo mismo, pixel a pixel. Todo lo nuevo vive en
`trayecto`, una clave que antes no existia.

COMO SE DESCRIBE UN MOVIMIENTO
------------------------------
Igual que la ventana de siempre --[x, y, ancho, alto] normalizados sobre el
hyperframe, cuadrada (ancho = alto = 1/escala) y recortada despues al aspecto de
salida--, pero por TRAMOS:

    {"tramos": [{"t0": 0.0, "t1": 2.4, "ini": [...], "fin": [...], "curva": "suave"},
                {"t0": 2.4, "t1": 5.1, "ini": [...], "fin": [...], "curva": "suave"}],
     "golpes": [{"t": 3.2, "escala": 1.08, "sube": 0.08, "baja": 0.7}]}

Entre dos tramos hay un SALTO (un corte dentro del plano, que es el reencuadre):
el segundo empieza donde quiere. Un golpe es un empujon de zoom de un instante
sobre lo que este haciendo el tramo, centrado en el mismo sitio.

Los tiempos van en segundos DEL PLANO (0 = su t_in), que es el reloj de la
pagina del render (`pintar(t)`). La MISMA cuenta vive en tres sitios --aqui, la
pagina del render (`p8_render.PAGINA`) y `p7_callouts.ventana_en`--, y por eso
esta escrita con las mismas operaciones en el mismo orden: si se separan, una
captura tomada en el segundo 2,2 deja de caer donde el video ensena el 2,2.
"""
import math
import re

# ---------------------------------------------------------------- el montaje

#: Los niveles de movimiento. «sobrio» es lo de siempre y por eso no tiene
#: parametros: con el no se calcula ningun trayecto.
NIVELES = ("sobrio", "vivo", "dinamico")

#: Lo que hace cada nivel. Los numeros estan pensados para leerse en un movil:
#:
#:   zoom        cuanto cierra el plano en el recorrido (0,12 = del 100 al 89 %).
#:               El de siempre son 0,05 (`segmentar.CIERRE`).
#:   paneo       fraccion del ancho que se desplaza la camara en un paneo.
#:   reencuadre  a partir de cuantos segundos un plano se parte en dos
#:               encuadres de la misma imagen (un corte dentro del plano).
#:   cierre      cuanto MAS cerrado va el segundo encuadre que el primero.
#:   golpe       si lleva el empujon de zoom en la palabra clave.
#:   curva       como acelera: «suave» (lo de siempre) o «salida» (arranca
#:               rapido y se posa, que es lo que se lee como energico).
#:   cortes      si los cambios de plano van en seco (las transiciones quedan
#:               solo en los acentos).
AJUSTES_NIVEL = {
    "vivo": {"zoom": 0.12, "paneo": 0.16, "reencuadre": 4.2, "cierre": 0.16,
             "golpe": False, "curva": "suave", "cortes": False},
    "dinamico": {"zoom": 0.18, "paneo": 0.20, "reencuadre": 2.8, "cierre": 0.22,
                 "golpe": True, "curva": "salida", "cortes": True},
}

#: Los dos estilos de subtitulo. «clasicos» son los de siempre.
SUBTITULOS = ("clasicos", "redes")

#: Lo que se escribe por defecto en un video NUEVO de hasta 2 minutos
#: (decision del dueno, 18-10-2026). Solo al crearlo: un video que ya existe
#: no cambia si nadie lo pide (regla 1 de CLAUDE.md).
MONTAJE_CORTOS = {"movimiento": "vivo", "subtitulos": "redes", "gancho": True,
                  "cifras": True, "barra": True}

#: Hasta aqui un video es corto (la misma cifra que `p3_guion.DURACION_CORTA_S`).
DURACION_CORTA_S = 120

#: El montaje de siempre, completo. Es lo que vale cualquier clave que falte.
MONTAJE_DE_SIEMPRE = {"movimiento": "sobrio", "subtitulos": "clasicos",
                      "gancho": False, "cifras": False, "barra": False}


def normalizar_montaje(crudo, estricto=False):
    """El montaje pedido, validado y completo. -> dict

    Lo que falta vale lo de siempre. Con `estricto` un valor que no existe es un
    ValueError (para la API); sin el, se ignora (para leer lo guardado).
    """
    salida = dict(MONTAJE_DE_SIEMPRE)
    if not isinstance(crudo, dict):
        if crudo not in (None, "") and estricto:
            raise ValueError("el montaje tiene que ser un objeto")
        return salida
    nivel = str(crudo.get("movimiento") or "").strip().lower()
    nivel = {"dinámico": "dinamico"}.get(nivel, nivel)
    if nivel in NIVELES:
        salida["movimiento"] = nivel
    elif nivel and estricto:
        raise ValueError("movimiento: " + ", ".join(NIVELES))
    sub = str(crudo.get("subtitulos") or "").strip().lower()
    sub = {"clásicos": "clasicos"}.get(sub, sub)
    if sub in SUBTITULOS:
        salida["subtitulos"] = sub
    elif sub and estricto:
        raise ValueError("subtitulos: " + ", ".join(SUBTITULOS))
    for clave in ("gancho", "cifras", "barra"):
        if clave in crudo:
            valor = crudo[clave]
            if not isinstance(valor, bool) and estricto:
                raise ValueError(f"{clave}: true o false")
            salida[clave] = bool(valor)
    return salida


def es_de_siempre(montaje):
    """Si este montaje es exactamente el de siempre (no hay nada que guardar)."""
    return normalizar_montaje(montaje) == MONTAJE_DE_SIEMPRE


def para_guardar(montaje):
    """Lo que se escribe en los params: SOLO lo que difiere de lo de siempre.

    Un montaje entero de siempre devuelve None, y quien guarda QUITA la clave:
    escribir «sobrio» en un video que nunca eligio moveria la firma de callouts
    sin cambiar un pixel (regla 1 de CLAUDE.md).
    """
    completo = normalizar_montaje(montaje)
    distinto = {k: v for k, v in completo.items() if MONTAJE_DE_SIEMPRE[k] != v}
    return distinto or None


def ajustes_de(montaje):
    """Los parametros del nivel de movimiento, o None si es «sobrio»."""
    return AJUSTES_NIVEL.get(normalizar_montaje(montaje)["movimiento"])


# --------------------------------------------------------------- la ventana

def _caja(centro, escala):
    """[x, y, ancho, alto] normalizados para ese centro y esa escala.

    La misma cuenta que `motores/render_video/movimiento.ventana`: cuadrada en
    normalizado y metida dentro del lienzo. Sin clamp de aspecto: eso lo hace
    quien la pinta, con el aspecto de salida delante.
    """
    escala = max(1.0, float(escala))
    lado = 1.0 / escala
    x = min(max(float(centro[0]) - lado / 2, 0.0), 1.0 - lado)
    y = min(max(float(centro[1]) - lado / 2, 0.0), 1.0 - lado)
    return [round(x, 5), round(y, 5), round(lado, 5), round(lado, 5)]


def curva(nombre, u):
    """La aceleracion de un tramo. -> 0..1

    «suave» es la de siempre (`p8_render.suavizar`). «salida» arranca rapido y
    se posa (cubica de salida). «lineal» para lo que tiene que ir constante.
    """
    u = min(max(float(u), 0.0), 1.0)
    if nombre == "salida":
        return 1 - (1 - u) ** 3
    if nombre == "lineal":
        return u
    return u * u * (3 - 2 * u)


def _golpe_en(golpe, t):
    """Cuanto empuja un golpe en el instante t. -> factor >= 1"""
    try:
        inicio = float(golpe["t"])
        escala = float(golpe.get("escala") or 1.0)
        sube = max(0.01, float(golpe.get("sube") or 0.08))
        baja = max(0.01, float(golpe.get("baja") or 0.6))
    except (KeyError, TypeError, ValueError):
        return 1.0
    if t < inicio or escala <= 1.0:
        return 1.0
    if t < inicio + sube:
        e = curva("salida", (t - inicio) / sube)
    elif t < inicio + sube + baja:
        e = 1 - curva("suave", (t - inicio - sube) / baja)
    else:
        return 1.0
    return 1 + (escala - 1) * e


def ventana_cruda_en(trayecto, t):
    """La ventana cuadrada [x, y, w, h] del trayecto en el instante t (s del plano).

    Busca el tramo, interpola con su curva y aplica los golpes encogiendo la
    ventana sobre su propio centro. La pagina del render hace exactamente esto.
    """
    tramos = (trayecto or {}).get("tramos") or []
    if not tramos:
        return None
    tramo = tramos[-1]
    for candidato in tramos:
        if float(candidato["t0"]) <= t < float(candidato["t1"]):
            tramo = candidato
            break
    if t < float(tramos[0]["t0"]):
        tramo = tramos[0]
    largo = max(1e-6, float(tramo["t1"]) - float(tramo["t0"]))
    e = curva(tramo.get("curva") or "suave", (t - float(tramo["t0"])) / largo)
    a, b = tramo["ini"], tramo["fin"]
    x = a[0] + (b[0] - a[0]) * e
    y = a[1] + (b[1] - a[1]) * e
    w = a[2] + (b[2] - a[2]) * e
    h = a[3] + (b[3] - a[3]) * e
    factor = 1.0
    for golpe in (trayecto or {}).get("golpes") or []:
        factor *= _golpe_en(golpe, t)
    if factor > 1.0:
        cx, cy = x + w / 2, y + h / 2
        w, h = w / factor, h / factor
        x, y = cx - w / 2, cy - h / 2
    return [x, y, w, h]


def recorte(caja, tamano, aspecto):
    """La ventana cuadrada recortada al aspecto de salida, en px. -> (x0, y0, x1, y1)

    La regla de siempre (`p7_callouts.ventana_en`, `p8_render.ventana`): manda
    el lado que limita y la ventana nunca se sale del lienzo.
    """
    ancho, alto = tamano
    x, y, w, h = caja
    if aspecto >= float(ancho) / float(alto):
        px_ancho = w * ancho
        px_alto = px_ancho / aspecto
        if px_alto > alto:
            px_alto, px_ancho = alto, alto * aspecto
    else:
        px_alto = h * alto
        px_ancho = px_alto * aspecto
        if px_ancho > ancho:
            px_ancho, px_alto = ancho, ancho / aspecto
    cx, cy = (x + w / 2) * ancho, (y + h / 2) * alto
    x0 = min(max(cx - px_ancho / 2, 0), ancho - px_ancho)
    y0 = min(max(cy - px_alto / 2, 0), alto - px_alto)
    return (x0, y0, x0 + px_ancho, y0 + px_alto)


# ------------------------------------------------------------ el trayecto

#: Las palabras que nunca son «la palabra clave» de un golpe.
_VACIAS = set("""
a al algo algun alguna algunas alguno algunos ante antes aqui asi aun bajo bien
cada casi como con contra cual cuando de del desde donde dos durante el ella
ellas ellos en entre era eres es esa esas ese eso esos esta estas este esto
estos fue fueron ha hace hacia han hasta hay la las le les lo los mas me mi
mientras mucho muy nada ni no nos nosotros o os otra otras otro otros para pero
poco por porque pues que quien se sea ser si sin sino sobre solo son su sus
tambien tan tanto te tiene tienen todo todos tu tus un una unas uno unos usted
ya yo the and that this with from have will your about which there their what
when would could should because these those
""".split())


def _llana(palabra):
    texto = str(palabra or "").lower()
    texto = (texto.replace("á", "a").replace("é", "e").replace("í", "i")
             .replace("ó", "o").replace("ú", "u").replace("ü", "u").replace("ñ", "n"))
    return re.sub(r"[^a-z0-9]", "", texto)


def _palabras_con_tiempo(escena):
    """[(palabra, inicio, fin)] en segundos DEL PLANO, o [] si no cuadran."""
    palabras = str(escena.get("narracion") or "").split()
    marcas = escena.get("marcas") or []
    if not palabras or len(palabras) != len(marcas):
        return []
    t_in = float(escena.get("t_in") or 0.0)
    salida = []
    for palabra, marca in zip(palabras, marcas):
        try:
            salida.append((palabra, float(marca[0]) - t_in, float(marca[1]) - t_in))
        except (TypeError, ValueError, IndexError):
            return []
    return salida


def _corte_interior(palabras, duracion, minimo=1.3):
    """Donde partir un plano en dos encuadres: en una pausa, cerca del medio. -> t | None

    Candidatos: el hueco entre dos palabras, puntuando mas una frase que acaba
    («.», «?») que una coma y una coma que nada. Los dos lados tienen que durar
    al menos `minimo` segundos: un encuadre de medio segundo es un parpadeo.
    """
    mejor, nota = None, None
    for (palabra, _ini, fin), (_sig, ini_sig, _fin_sig) in zip(palabras, palabras[1:]):
        corte = (fin + ini_sig) / 2.0
        if corte < minimo or duracion - corte < minimo:
            continue
        hueco = max(0.0, ini_sig - fin)
        if re.search(r"[.!?…]$", palabra):
            peso = 0.0
        elif re.search(r"[,;:]$", palabra):
            peso = 0.25
        elif hueco >= 0.12:
            peso = 0.45
        else:
            peso = 0.9
        distancia = abs(corte - duracion / 2.0) / max(0.1, duracion)
        valor = peso + distancia
        if nota is None or valor < nota:
            mejor, nota = round(corte, 3), valor
    return mejor


def _palabra_clave(palabras, cifras=()):
    """El instante de la palabra que se lleva el golpe. -> t | None

    Una cifra si la hay (es lo que el espectador tiene que retener); si no, la
    palabra con mas contenido: la mas larga que no sea vacia.
    """
    for indice in cifras:
        if 0 <= indice < len(palabras):
            return palabras[indice][1]
    elegida = None
    for palabra, inicio, _fin in palabras:
        llana = _llana(palabra)
        if len(llana) < 7 or llana in _VACIAS:
            continue
        if elegida is None or len(llana) > len(_llana(elegida[0])):
            elegida = (palabra, inicio)
    return elegida[1] if elegida else None


#: Centros por los que pasea la camara: el centro y los tercios, sin irse a
#: los bordes (el sujeto casi siempre esta en el medio de la imagen).
_CENTROS = ((0.5, 0.46), (0.40, 0.42), (0.60, 0.44), (0.5, 0.56),
            (0.42, 0.52), (0.58, 0.50))

#: Los cuatro movimientos que se alternan plano a plano. Alternar no es un
#: capricho: dos acercamientos seguidos se leen como uno solo y el corte entre
#: ellos desaparece (lo mismo que `segmentar.alternar_zoom`).
_PATRONES = ("acercar", "paneo", "alejar", "paneo_inverso")


def _con_entrada(tramos):
    """EL GANCHO: el primer plano entra desde muy cerca y se abre de golpe hasta
    su movimiento (medio segundo, arrancando rapido). Es lo que en un movil
    hace que el primer segundo no parezca una foto. -> tramos
    """
    entrada = min(0.55, float(tramos[0]["t1"]) * 0.5)
    if entrada < 0.2:
        return tramos
    primero = tramos[0]
    llegada = list(primero["ini"])
    cx = llegada[0] + llegada[2] / 2
    cy = llegada[1] + llegada[3] / 2
    cerca = _caja((cx, cy), 1.0 / max(1e-6, llegada[2]) + 0.3)
    return ([{"t0": 0.0, "t1": round(entrada, 3), "ini": cerca, "fin": llegada,
              "curva": "salida"},
             dict(primero, t0=round(entrada, 3))] + list(tramos[1:]))


def trayecto_de(escena, indice, montaje, semilla=0, cifras=None, gancho=False,
                base=None):
    """El trayecto de camara de un plano, o None si va el movimiento de siempre.

    `indice` es su posicion en el video (decide el patron, alternando).
    `cifras` son los indices de palabra donde empieza una cifra dicha (las
    pone p7, que ya las calcula para pintarlas). `gancho` marca el primer plano
    de un video con gancho: entra con un zoom rapido desde muy cerca.
    `base` es el movimiento de siempre del plano (`movimiento.calcular`): sus
    ventanas y su centro, que puede venir de un ancla o del plan. Con el
    gancho en sobrio se usan TAL CUAL, y en vivo y dinamico un centro que no
    sea el de por defecto manda sobre el de la alternancia: el plano sigue
    encuadrando a su sujeto.

    Devuelve None con el montaje de siempre, y tambien en los planos donde el
    movimiento no se puede tocar sin romper algo (cartelas y cabeceras, cuyo
    texto viaja dentro del zoom): ahi va lo de siempre.
    """
    ajustes = ajustes_de(montaje)
    try:
        duracion = float(escena["t_out"]) - float(escena["t_in"])
    except (KeyError, TypeError, ValueError):
        return None
    if duracion <= 0.05:
        return None
    if not ajustes:
        # MOVIMIENTO DE SIEMPRE, PERO CON GANCHO: el primer plano lleva su zoom
        # de siempre (el del plan) y delante la entrada rapida. Los demas
        # planos no llevan trayecto y salen exactamente como antes.
        if not (gancho and int(indice) == 0):
            return None
        if base and base.get("ventana_ini") and base.get("ventana_fin"):
            ini, fin = list(base["ventana_ini"]), list(base["ventana_fin"])
        else:
            zoom = escena.get("zoom") or {}
            try:
                de, a = float(zoom.get("de", 1.0)), float(zoom.get("a", 1.0))
            except (TypeError, ValueError):
                de, a = 1.0, 1.0
            ini, fin = _caja((0.5, 0.5), de), _caja((0.5, 0.5), a)
        tramos = [{"t0": 0.0, "t1": round(duracion, 3), "ini": ini,
                   "fin": fin, "curva": "suave"}]
        return {"tramos": _con_entrada(tramos), "golpes": []}
    paso = (int(indice) + int(semilla or 0)) % len(_PATRONES)
    patron = _PATRONES[paso]
    centro = _CENTROS[(int(indice) * 5 + int(semilla or 0)) % len(_CENTROS)]
    propio = (base or {}).get("centro")
    if (propio and (base or {}).get("origen_centro") not in (None, "por_defecto")
            and len(propio) == 2 and all(es_finito(v) for v in propio)):
        centro = (float(propio[0]), float(propio[1]))
    zoom = float(ajustes["zoom"])
    curva_nombre = ajustes["curva"]

    def movimiento(c, t0, t1, extra=0.0, quieto=False):
        """El tramo de un patron entre t0 y t1, con un cierre extra encima."""
        base = 1.0 + extra
        if quieto:
            ini = fin = _caja(c, base + zoom * 0.4)
        elif patron == "acercar":
            ini, fin = _caja(c, base), _caja(c, base + zoom)
        elif patron == "alejar":
            ini, fin = _caja(c, base + zoom), _caja(c, base)
        else:
            mitad = float(ajustes["paneo"]) / 2.0
            signo = 1 if patron == "paneo" else -1
            escala = base + zoom * 0.5
            ini = _caja((c[0] - signo * mitad, c[1]), escala)
            fin = _caja((c[0] + signo * mitad, c[1]), escala)
        return {"t0": round(t0, 3), "t1": round(t1, 3), "ini": ini, "fin": fin,
                "curva": curva_nombre}

    palabras = _palabras_con_tiempo(escena)
    tramos = []
    corte = None
    if duracion >= float(ajustes["reencuadre"]) and palabras:
        corte = _corte_interior(palabras, duracion)
    if corte:
        tramos.append(movimiento(centro, 0.0, corte))
        # EL SEGUNDO ENCUADRE: mas cerrado y en OTRO sitio de la imagen. Si
        # fuera el mismo centro con un poco mas de zoom, el corte se leeria
        # como un salto de montaje mal hecho y no como un cambio de plano.
        otro = _CENTROS[(int(indice) * 5 + int(semilla or 0) + 3) % len(_CENTROS)]
        tramos.append(movimiento(otro, corte, duracion, extra=float(ajustes["cierre"])))
    else:
        tramos.append(movimiento(centro, 0.0, duracion))

    if gancho and int(indice) == 0:
        tramos = _con_entrada(tramos)

    golpes = []
    if ajustes["golpe"] and palabras:
        cuando = _palabra_clave(palabras, cifras or ())
        fronteras = [float(t["t0"]) for t in tramos[1:]]
        if (cuando is not None and 0.35 <= cuando <= duracion - 0.5
                and all(abs(cuando - f) >= 0.35 for f in fronteras)):
            golpes.append({"t": round(max(0.0, cuando - 0.03), 3), "escala": 1.08,
                           "sube": 0.08, "baja": 0.7})
    return {"tramos": tramos, "golpes": golpes}


def ventana_en_t(mov, t, tamano, aspecto):
    """El recorte en px del plano en el instante t (s del plano), con o sin trayecto.

    Sin trayecto es la cuenta de siempre (ventana_ini -> ventana_fin con la
    curva suave). Con trayecto, la de los tramos y los golpes.
    """
    trayecto = (mov or {}).get("trayecto")
    if trayecto and trayecto.get("tramos"):
        caja = ventana_cruda_en(trayecto, float(t))
    else:
        try:
            duracion = float(mov.get("t_out")) - float(mov.get("t_in"))
        except (TypeError, ValueError):
            duracion = 0.0
        u = (float(t) / duracion) if duracion > 0 else 0.0
        e = curva("suave", u)
        a, b = mov["ventana_ini"], mov["ventana_fin"]
        caja = [a[k] + (b[k] - a[k]) * e for k in range(4)]
    return recorte(caja, tamano, aspecto)


def duracion_de(mov):
    """Lo que dura el plano de este movimiento, o 0."""
    try:
        return max(0.0, float(mov.get("t_out")) - float(mov.get("t_in")))
    except (TypeError, ValueError, AttributeError):
        return 0.0


def es_finito(valor):
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError):
        return False

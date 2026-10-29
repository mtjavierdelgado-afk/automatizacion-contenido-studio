"""QUE CLASE DE PLANO es cada uno: la escalera de cartas y su reparto.

NO CONFUNDIR CON cartelas.py, que es el texto que se escribe sobre la imagen.
Aqui una "carta" es una clase de encuadre -- una vista aerea, un detalle macro,
una silueta a contraluz --, y lo unico que produce este modulo es cual le toca a
cada plano.

DE DONDE VIENE
--------------
Esto era la mitad viva de `planos3d.py`, que construia un blockout 3D por plano
en Blender. La caja se retiro entera el 23-08-2026; la carta
no, porque nunca dependio de ella: pedirle a un modelo de imagen «haz un plano
distinto» devuelve el mismo plano medio con otras palabras, y decidirlo ANTES
--este es un aereo, el siguiente un detalle macro-- es lo que produce ritmo.

Cada carta lleva su `encuadre` en ingles, que entra en el prompt del plano como
SHOT TYPE obligatorio y es lo unico que fija el cuadro. Las cartas ya no llevan
numeros de camara (distancia, altura, focal): eran para Blender y no los leia
nadie mas.

LO QUE NO PUEDE CAMBIAR
-----------------------
El reparto es DETERMINISTA y tiene que seguir siendolo: la imagen de un plano se
cachea por su prompt, y el encuadre va en el prompt. Cambiar el orden de la
escalera, un peso o un texto de `encuadre` le cambia la carta a planos que narran
exactamente lo mismo, y eso se paga en imagenes. Por eso al retirar la caja se
conservaron los ids, las familias, los pesos y el orden EXACTOS.
"""
import re

import dominios
import medios


# --------------------------------------------------------------- la escalera

#: Las clases de plano que se van alternando.
#:
#: 'familia' es lo que impide que dos planos seguidos se parezcan: dos cartas de
#: la misma familia miran el mundo igual aunque cambien de nombre.
#:
#: 'peso' inclina el reparto sin cerrarlo: un documental es sobre todo gente y
#: sitios, y si los detalles macro salieran tanto como el plano medio el video
#: pareceria un anuncio.
#:
#: 'abstracta' marca las que no ocurren en ningun sitio fisico. Lo lee el prompt
#: del plano: un diagrama no se rueda en «la sede del banco», asi que su sitio
#: se sustituye por una base conceptual.
ESCALERA = (
    {"id": "aereo", "familia": "lejos", "peso": 2, "nombre": "vista aerea",
     "encuadre": ("a high aerial bird's-eye shot looking steeply down on the "
                  "scene from far above, wide angle, the whole layout visible "
                  "and the people small within it")},

    {"id": "general", "familia": "lejos", "peso": 3, "nombre": "plano general",
     "encuadre": ("a wide establishing shot from far back, the figures small "
                  "inside a large space, plenty of air above and around them")},

    {"id": "contrapicado", "familia": "angulo", "peso": 2,
     "nombre": "contrapicado extremo",
     "encuadre": ("an extreme low-angle shot from near the floor tilted sharply "
                  "up, towering vertical lines, the subject looming over the "
                  "viewer")},

    {"id": "cenital", "familia": "angulo", "peso": 2, "nombre": "cenital",
     "encuadre": ("a top-down overhead shot looking straight down on the surface "
                  "below, the objects arranged flat within the frame")},

    {"id": "detalle", "familia": "cerca", "peso": 3, "nombre": "detalle macro",
     "encuadre": ("an extreme close-up of one single object filling the frame, "
                  "shallow depth, everything behind it out of focus and abstract")},

    {"id": "retrato", "familia": "cerca", "peso": 3, "nombre": "retrato cerrado",
     "encuadre": ("a tight close-up portrait of the face and shoulders, long "
                  "lens, the background simple and far behind")},

    {"id": "hombro", "familia": "medio", "peso": 2, "nombre": "sobre el hombro",
     "encuadre": ("an over-the-shoulder shot, the back and shoulder of one "
                  "figure large and dark on one side of the frame, the subject "
                  "of their attention beyond")},

    {"id": "silueta", "familia": "luz", "peso": 2,
     "nombre": "silueta a contraluz",
     "encuadre": ("a backlit silhouette shot: the figure is a dark shape against "
                  "a large bright opening behind, almost no detail on the figure "
                  "itself")},

    {"id": "entre", "familia": "luz", "peso": 2,
     "nombre": "mirando entre las cosas",
     "encuadre": ("a shot framed through a gap: something in the immediate "
                  "foreground partly blocks the view from the edges, the subject "
                  "seen through the opening between")},

    {"id": "perfil", "familia": "medio", "peso": 2, "nombre": "perfil lateral",
     "encuadre": ("a flat side-on profile shot, the subject seen exactly from "
                  "the side against a background parallel to the frame, almost "
                  "graphic")},

    {"id": "suelo", "familia": "angulo", "peso": 1, "nombre": "a ras de suelo",
     "encuadre": ("a ground-level shot with the camera resting on the floor, the "
                  "floor filling the lower half of the frame, everything seen "
                  "from below")},

    {"id": "hueco", "familia": "lejos", "peso": 1, "nombre": "el sitio vacio",
     "encuadre": ("an empty establishing shot of the place with no people in it "
                  "at all, still and quiet, the traces of what happened left "
                  "behind")},

    # -------- cartas ABSTRACTAS: sin caja posible, solo en geometria 'directa'.
    # No llevan "plano" porque no hay nada que construir en Blender: son planos
    # que no ocurren en un sitio fisico. Es lo que ese modo gana -- un documental
    # que funciona tambien corta a un diagrama, a una pantalla o a una metafora,
    # no solo a otra habitacion -- y siempre con los monigotes y el estilo del
    # video, que lo imponen las referencias de estilo, no la carta.
    {"id": "diagrama", "familia": "abstracta", "peso": 2, "abstracta": True,
     "nombre": "diagrama",
     "encuadre": ("a clean explanatory diagram filling the frame: simple flat "
                  "shapes, thick arrows and short labels laid out on a plain "
                  "graphic background, the idea drawn as a chart rather than a "
                  "place, with small stick figures integrated as part of the "
                  "diagram")},

    {"id": "pantalla", "familia": "abstracta", "peso": 2, "abstracta": True,
     "nombre": "pantalla",
     "encuadre": ("a full-frame computer screen taking up the entire image: "
                  "terminal windows, scrolling code, progress bars and blinking "
                  "cursors drawn flat in the video's own style, slightly angled "
                  "as if glowing in a dark room, no visible person unless the "
                  "scene names one")},

    {"id": "eterea", "familia": "abstracta", "peso": 1, "abstracta": True,
     "nombre": "composicion eterea",
     "encuadre": ("an abstract conceptual composition floating on an empty "
                  "backdrop: the subject suspended in space among drifting "
                  "symbolic elements, no floor, no walls, no horizon, a visual "
                  "metaphor of the idea rather than a scene")},
)

POR_ID = {carta["id"]: carta for carta in ESCALERA}


# ------------------------------------------------ la escalera del MODO FOTO
#
# UNA ESCALERA APARTE, Y NO CARTAS NUEVAS EN LA DE ARRIBA. La de ilustracion no
# se toca: anadirle una carta, cambiarle un peso o un texto le cambia la carta a
# planos que narran lo mismo, y eso son imagenes ya pagadas que salen obsoletas.
# El modo foto (`estilo.modo == "foto"`, Etapa Foto A) reparte sobre esta y el
# de ilustracion sigue repartiendo sobre aquella exactamente igual que antes.
#
# Que cambia respecto a la de ilustracion, y por que:
#   * el aereo pasa a ser un PICADO desde una escalera o un altillo: un dron
#     dentro de una sala de fiestas no es creible en una foto;
#   * las tres abstractas (diagrama, pantalla, eterea) se van: una foto de un
#     evento no corta a un diagrama, y una «composicion eterea» fotografiada es
#     una imagen generada que se nota;
#   * entran los planos que venden un servicio de alquiler: las manos en el
#     mando, la estacion completa y la reaccion de quien mira.
#
# `servicios` dice en que videos tiene sentido la carta: los pies en los pedales
# solo si hay simuladores, el cuerpo con el visor solo si hay realidad virtual.
# "todos" vale para cualquiera. Cual lleva el video lo dice el param
# `servicios` de assets (ver `servicios_de`).
#
# Los ids llevan el prefijo `foto_` para que no se confundan nunca con los de
# la escalera de ilustracion en un informe o en una carta forzada a mano.

#: Los servicios que una carta de foto puede pedir SIN un negocio fijado.
#: NINGUNO desde la Etapa Foto C (21-10-2026): lo de cada negocio --sus
#: servicios, cómo se reconocen y sus cartas-- vive en la FICHA de su cliente
#: (`pasos/dominios.py`), no en el código. Sin ficha, la escalera general.
SERVICIOS = dominios.SERVICIOS

#: Lo que se supone cuando un video no dice que servicios lleva Y su texto no
#: nombra ninguno: NINGUNO, y entonces reparte la escalera GENERAL de foto (ver
#: `ESCALERA_FOTO_GENERAL`). Antes era «consolas», y con eso un video de plantas
#: salia con «primer plano de las manos en el mando» y «la estacion completa con
#: el televisor en su tripode»: el modo foto es para cualquier proyecto.
SERVICIOS_POR_DEFECTO = ()

SERVICIOS_EN_TEXTO = dominios.SERVICIOS_EN_TEXTO

#: (Lo que sigue describe `SERVICIOS_EN_TEXTO`, que vive en el dominio.)
#: COMO SE RECONOCE CADA SERVICIO EN EL TEXTO DEL VIDEO (la guia del estilo, su
#: prompt, el catalogo visual del guion). Mientras la Etapa Foto C no lo ponga en
#: pantalla, es lo que hace que un video de EstadoPlay siga saliendo con sus
#: planos de consolas sin que nadie tenga que decirlo. Expresiones regulares, sin
#: distinguir mayusculas; en ingles y en castellano.


def servicios_en_texto(texto):
    """Los servicios que nombra un texto. -> tupla (vacia si ninguno)"""
    texto = str(texto or "")
    if not texto:
        return ()
    return tuple(nombre for nombre, patrones in SERVICIOS_EN_TEXTO.items()
                 if any(re.search(pat, texto, flags=re.IGNORECASE)
                        for pat in patrones))

#: La escalera de foto de los servicios sin negocio fijado: vacía desde la
#: Etapa Foto C (era la de EstadoPlay, con estaciones, trípodes y mandos). Un
#: negocio con cartas propias las trae en su ficha (`dominio["escalera"]`).
ESCALERA_FOTO = dominios.ESCALERA_FOTO

#: LA ESCALERA GENERAL DE FOTO, la de cualquier proyecto que no sea de un
#: servicio de alquiler. La de arriba se escribio para EstadoPlay --estaciones,
#: tripodes, mandos-- y repartida en un video de otra cosa metia consolas donde
#: no las hay. Estas no nombran ningun objeto: piden la CLASE de plano y dejan
#: que la escena diga que sale. Mismas familias, para que el reparto respire
#: igual (dos lejos no seguidos, un cerca entre medios).
ESCALERA_FOTO_GENERAL = (
    {"id": "foto_g_general", "familia": "lejos", "peso": 2, "servicios": "todos",
     "nombre": "plano general",
     "encuadre": ("a wide establishing shot of the whole place taken from a "
                  "corner at standing height, the people small within the space "
                  "and the setting clearly readable")},

    {"id": "foto_g_picado", "familia": "lejos", "peso": 1, "servicios": "todos",
     "nombre": "picado",
     "encuadre": ("a high-angle shot taken from a staircase, a balcony or a "
                  "raised spot, looking down on the people and what they are "
                  "doing")},

    {"id": "foto_g_medio", "familia": "medio", "peso": 3, "servicios": "todos",
     "nombre": "plano medio",
     "encuadre": ("a medium shot of the main subject from the waist up, doing "
                  "what the scene describes, the setting soft behind them")},

    {"id": "foto_g_hombro", "familia": "medio", "peso": 2, "servicios": "todos",
     "nombre": "sobre el hombro",
     "encuadre": ("an over-the-shoulder shot of one person looking at what the "
                  "scene is about, their shoulder and hair soft in the "
                  "foreground")},

    {"id": "foto_g_perfil", "familia": "medio", "peso": 2, "servicios": "todos",
     "nombre": "perfil",
     "encuadre": ("a side profile of two people next to each other, both "
                  "absorbed in the same thing")},

    {"id": "foto_g_reaccion", "familia": "medio", "peso": 2, "servicios": "todos",
     "nombre": "reacción",
     "encuadre": ("the people around the main action reacting to it -- "
                  "listening, laughing, watching -- with the action itself "
                  "softly out of focus")},

    {"id": "foto_g_manos", "familia": "cerca", "peso": 3, "servicios": "todos",
     "nombre": "manos",
     "encuadre": ("a close-up of hands doing what the scene describes, the "
                  "fingers and the object they hold sharp, everything else "
                  "soft")},

    {"id": "foto_g_detalle", "familia": "cerca", "peso": 2, "servicios": "todos",
     "nombre": "detalle",
     "encuadre": ("a close detail of the key object of the scene resting where "
                  "it belongs, its material and texture readable")},

    {"id": "foto_g_primer_termino", "familia": "cerca", "peso": 2,
     "servicios": "todos", "nombre": "objeto en primer término",
     "encuadre": ("the key object of the scene large and sharp in the "
                  "foreground, the people out of focus behind it")},

    {"id": "foto_g_retrato", "familia": "cerca", "peso": 2, "servicios": "todos",
     "nombre": "retrato",
     "encuadre": ("a candid head-and-shoulders portrait of one person in the "
                  "middle of the moment, the setting soft behind them")},

    {"id": "foto_g_contraluz", "familia": "luz", "peso": 1, "servicios": "todos",
     "nombre": "contraluz",
     "encuadre": ("the people in silhouette against a bright window or the open "
                  "sky, the light wrapping around their outline")},

    {"id": "foto_g_bajo", "familia": "angulo", "peso": 1, "servicios": "todos",
     "nombre": "a ras de suelo",
     "encuadre": ("a low angle from near the ground looking up at the people "
                  "and the setting")},
)

#: Las dos de foto en un solo diccionario: una carta forzada o una carta ya
#: repartida se encuentra sea de la general o de la de servicios.
POR_ID_FOTO = {carta["id"]: carta
               for carta in ESCALERA_FOTO + ESCALERA_FOTO_GENERAL}


def escalera_de(modo="ilustracion"):
    """La escalera de cartas de ese modo de imagen. -> tupla de cartas

    Cualquier valor que no sea "foto" es ilustracion, que es lo que lee un
    proyecto que nunca guardo `estilo.modo`.
    """
    return (ESCALERA_FOTO or ESCALERA_FOTO_GENERAL) if modo == "foto" else ESCALERA


def por_id_de(modo="ilustracion"):
    """{id: carta} de la escalera de ese modo."""
    return POR_ID_FOTO if modo == "foto" else POR_ID


def servicios_de(valor, dominio=None):
    """Los servicios de un video, limpios y conocidos. -> tupla

    Vacio o sin ninguno conocido es el servicio base (`SERVICIOS_POR_DEFECTO`).
    Admite una lista o una cadena separada por comas. `dominio` dice cuales son
    «conocidos» (sin el, los de `SERVICIOS`: ninguno desde la Etapa Foto C).
    """
    conocidos = SERVICIOS if dominio is None else tuple(dominio.get("servicios") or ())
    if isinstance(valor, str):
        valor = valor.split(",")
    limpios = []
    for crudo in (valor or []):
        nombre = str(crudo or "").strip().lower()
        if nombre in conocidos and nombre not in limpios:
            limpios.append(nombre)
    return tuple(limpios) or SERVICIOS_POR_DEFECTO


def _vale_para(carta, servicios):
    """Si una carta de foto tiene sentido con esos servicios."""
    suyos = carta.get("servicios") or "todos"
    if suyos == "todos":
        return True
    return any(s in servicios for s in suyos)


def escalera_para(modo="ilustracion", servicios=None, dominio=None):
    """La escalera sobre la que se reparte: la del modo, filtrada por servicios.

    El filtro solo existe en el modo foto. En ilustracion devuelve `ESCALERA`
    tal cual, sin mirar `servicios`: el reparto de siempre no cambia ni en el
    orden.

    `dominio` (rama dominio-negocio) es el del negocio del video, ya resuelto
    (`dominios.de_estilo`). Sin el, la escalera de servicios es `ESCALERA_FOTO`
    (vacía desde la Etapa Foto C, así que la general),
    como siempre. Un dominio sin escalera propia (el general) reparte siempre
    la general.
    """
    if modo != "foto":
        return ESCALERA
    propia = ESCALERA_FOTO if dominio is None else tuple(dominio.get("escalera") or ())
    suyos = servicios_de(servicios, dominio)
    if not suyos or not propia:
        # un video que no es de un servicio de alquiler: la general
        return ESCALERA_FOTO_GENERAL
    return tuple(c for c in propia if _vale_para(c, suyos))


#: Cuantos planos hacia atras se mira para no repetir FAMILIA. Regla dura. Dos y
#: no uno: con uno, 'aereo'-'retrato'-'general' pasa el filtro y el espectador ve
#: dos planos lejanos separados por uno cercano, que es el ritmo de siempre.
VENTANA_FAMILIA = 2

#: Y cuantos para no repetir la MISMA carta. Preferencia, no regla: con quince
#: cartas y videos de cuarenta y ocho planos, exigirlo dejaria sin candidatos.
VENTANA_CARTA = 5


def _repartidas(escalera=ESCALERA):
    """La escalera expandida por peso, que es sobre lo que se reparte."""
    expandida = []
    for carta in escalera:
        expandida.extend([carta] * max(1, int(carta.get("peso") or 1)))
    return expandida


def carta_de(sid, previas=(), semilla=0, forzada="", modo="ilustracion",
             servicios=None, dominio=None):
    """Que clase de plano es este. Determinista, y nunca la familia de al lado.

    'previas' son los ids de carta de los planos que van justo antes, en orden.
    De ahi salen las dos reglas: dura contra la familia (ver VENTANA_FAMILIA) y
    blanda contra la carta (ver VENTANA_CARTA).

    Determinista porque replanificar no puede rebarajar el video: un plano que
    narra lo mismo tiene que salir con la misma carta, o su prompt cambia y se
    vuelve a pagar una imagen que ya estaba bien.

    'forzada' es el id que haya pedido una persona para ESE plano, y manda sobre
    todo lo demas. Una decision tomada mirando el video no se rebate sola.

    'modo' y 'servicios' eligen la escalera (ver `escalera_para`). Una carta
    forzada solo vale si es de la escalera de ese modo: un «diagrama» forzado
    antes de pasar el estilo a foto no tiene sentido en una foto, y se reparte
    como si no se hubiera forzado. Forzar a mano si salta el filtro de
    servicios: es una decision tomada mirando.
    """
    lookup = por_id_de(modo)
    if modo == "foto" and dominio is not None and dominio.get("escalera"):
        # las cartas propias de un negocio también tienen familia: sin esto la
        # regla de «nunca dos familias seguidas» no las veía (Etapa Foto C)
        lookup = dict(lookup, **{c["id"]: c for c in dominio["escalera"]})
    if forzada and forzada in lookup:
        return lookup[forzada]
    previas = [str(p) for p in (previas or [])]
    vetadas = {(lookup.get(p) or {}).get("familia")
               for p in previas[-VENTANA_FAMILIA:]}
    vetadas.discard(None)
    recientes = set(previas[-VENTANA_CARTA:])
    fondo = _repartidas(escalera_para(modo, servicios, dominio))
    arranque = medios.desempatar(semilla, sid, "carta") % len(fondo)
    orden = [fondo[(arranque + i) % len(fondo)] for i in range(len(fondo))]
    libres = [c for c in orden if c["familia"] not in vetadas]
    if not libres:
        return orden[0]
    frescas = [c for c in libres if c["id"] not in recientes]
    return (frescas or libres)[0]


def repartir(escenas, semilla=0, forzadas=None, modo="ilustracion",
             servicios=None, dominio=None):
    """Una carta por plano, en orden y con las dos reglas puestas.

    Va aparte de `carta_de` porque el reparto depende del ORDEN -- cada plano
    mira los que tiene delante --, y eso es una decision del conjunto.
    """
    forzadas = forzadas or {}
    cartas, previas = {}, []
    for escena in escenas or []:
        sid = escena.get("id")
        if not sid:
            continue
        carta = carta_de(sid, previas, semilla, forzadas.get(sid, ""),
                         modo=modo, servicios=servicios, dominio=dominio)
        cartas[sid] = carta
        previas.append(carta["id"])
    return cartas

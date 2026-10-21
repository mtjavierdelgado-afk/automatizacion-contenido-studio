"""EL DOMINIO DE UN NEGOCIO: lo que el Studio sabe de UN tipo de cliente (rama
dominio-negocio, 21-10-2026, pedido del dueño).

Hasta esta rama, lo de EstadoPlay estaba escrito a mano por todo el código:
los servicios de alquiler y cómo se reconocen en el texto (`encuadres`), la
escalera de cartas de foto con estaciones, trípodes y mandos, y el criterio del
revisor («una tele sobre un mueble cuando va en su trípode», «mandos de otro
color»). Un vídeo de baños o de plantas en foto recibía ese criterio igual.

Aquí cada negocio es un DOMINIO, con todo lo suyo junto:

  servicios   los servicios que pueden pedir sus cartas;
  en_texto    cómo se reconoce cada servicio en el texto del vídeo;
  escalera    sus cartas de foto (con el servicio que pide cada una);
  revisor     las frases del revisor que hablan de SU equipo.

DOS DE FÁBRICA:
  estadoplay  los valores de antes de esta rama, MISMOS objetos y mismo orden;
  general     ningún servicio: la escalera general de foto y un revisor que
              no habla de consolas.

QUÉ DOMINIO RIGE (`de_estilo`):
  - el que fije el estilo (`estilo.dominio`, id de uno de fábrica);
  - si no fija ninguno: AUTOMÁTICO, que es exactamente lo de antes. Se buscan
    los servicios de EstadoPlay en el texto del vídeo; si sale alguno es
    EstadoPlay y si no, general. Así un vídeo de EstadoPlay sigue saliendo con
    sus cartas sin que nadie lo diga, y ninguna carta ni firma se mueve.

LA REGLA QUE NO SE PUEDE ROMPER: la escalera de EstadoPlay expandida por peso
tiene que quedar idéntica en longitud y en orden. `encuadres.carta_de` sortea
con `arranque % len(fondo)`: una carta de más, de menos o en otro sitio cambia
la carta de casi todos los planos de foto y deja sus imágenes obsoletas. Lo
comprueba `prueba_dominios.py` contra la escalera de `main`.

Este módulo solo tiene datos y funciones puras.
"""
import re

SERVICIOS = ("consolas", "simuladores", "vr", "karaoke")

SERVICIOS_EN_TEXTO = {
    "consolas": (r"\bconsol(e|es|a|as)\b", r"\bcontrollers?\b", r"\bgamepads?\b",
                 r"\bmandos?\b", r"\bvideo ?games?\b", r"\bvideojuegos?\b",
                 r"\bgameplay\b", r"\bgaming\b", r"\bplaystation\b",
                 r"\bps[345]\b", r"\bxbox\b", r"\bnintendo\b"),
    "simuladores": (r"\bsimulat(or|ors)\b", r"\bsimuladore?s?\b",
                    r"\bracing (rig|sim|wheel)s?\b", r"\bpedals?\b.*\bwheel\b"),
    "vr": (r"\bvr\b", r"\bvirtual reality\b", r"\brealidad virtual\b",
           r"\bmeta quest\b"),
    "karaoke": (r"\bkaraoke\b",),
}

ESCALERA_FOTO = (
    {"id": "foto_sala", "familia": "lejos", "peso": 2, "servicios": "todos",
     "nombre": "sala completa",
     "encuadre": ("a wide shot of the whole room taken from a corner at "
                  "standing height, every gaming station and the party table "
                  "visible, guests small within the space")},

    {"id": "foto_picado", "familia": "lejos", "peso": 1, "servicios": "todos",
     "nombre": "picado",
     "encuadre": ("a high-angle shot taken from a staircase or a mezzanine "
                  "looking down on the gaming stations and the guests around "
                  "them")},

    {"id": "foto_estacion", "familia": "medio", "peso": 3, "servicios": "todos",
     "nombre": "estación completa",
     "encuadre": ("the full gaming station in frame: the TV on its tripod "
                  "stand, the low black side table, the console, and two "
                  "players seen from behind")},

    {"id": "foto_hombro", "familia": "medio", "peso": 2,
     "servicios": ("consolas", "simuladores"), "nombre": "sobre el hombro",
     "encuadre": ("an over-the-shoulder shot of one player looking at the "
                  "screen, their hands and the controller soft in the "
                  "foreground")},

    {"id": "foto_perfil", "familia": "medio", "peso": 2,
     "servicios": ("consolas", "karaoke"), "nombre": "perfil de jugadores",
     "encuadre": ("a side profile of two players next to each other, their "
                  "faces lit by the glow of the screen")},

    {"id": "foto_reaccion", "familia": "medio", "peso": 2, "servicios": "todos",
     "nombre": "reacción",
     "encuadre": ("the people watching behind the players, laughing or "
                  "cheering, the game screen softly out of focus")},

    {"id": "foto_vr", "familia": "medio", "peso": 1, "servicios": ("vr",),
     "nombre": "cuerpo VR",
     "encuadre": ("a full-body shot of one player wearing a VR headset, arms "
                  "extended holding both controllers, the room around them")},

    {"id": "foto_manos", "familia": "cerca", "peso": 3,
     "servicios": ("consolas", "simuladores"), "nombre": "manos",
     "encuadre": ("a close-up of hands on the controller or on the steering "
                  "wheel, thumbs and fingers in action")},

    {"id": "foto_detalle", "familia": "cerca", "peso": 2, "servicios": "todos",
     "nombre": "detalle de equipo",
     "encuadre": ("a detail of the console and the controllers resting on the "
                  "low black side table, a cable running to the tripod")},

    {"id": "foto_pedales", "familia": "cerca", "peso": 1,
     "servicios": ("simuladores",), "nombre": "pies en pedales",
     "encuadre": ("a low close-up of sneakers pressing the three metal pedals "
                  "of the racing simulator")},

    {"id": "foto_pantalla", "familia": "cerca", "peso": 2, "servicios": "todos",
     "nombre": "pantalla al frente",
     "encuadre": ("the game screen large in the foreground, the players' "
                  "silhouettes at the edge of the frame")},

    {"id": "foto_contraluz", "familia": "luz", "peso": 1, "servicios": "todos",
     "nombre": "contraluz",
     "encuadre": ("the players in silhouette against a bright window, the "
                  "screen glowing in front of them")},

    {"id": "foto_suelo", "familia": "angulo", "peso": 1,
     "servicios": ("consolas", "vr"), "nombre": "a ras de suelo",
     "encuadre": ("a low angle from floor level between the poufs, looking up "
                  "towards the TV and the players")},
)


#: Las frases del revisor de imágenes que hablan del EQUIPO de un negocio. Las
#: de EstadoPlay son las de antes de esta rama, letra por letra.
REVISOR_ESTADOPLAY = {
    "equipo": ("el equipo no es el que mandan las indicaciones o esta montado\n"
               "    como no se monta (una tele sobre un mueble cuando va en su tripode, un\n"
               "    monitor gigante, mandos de otro color o de otra consola, cables imposibles)."),
    "congruencia": ("el mismo sitio o la misma estacion cambia de un plano a otro\n"
                    "    sin que el guion lo pida."),
    "manos": "dedos de mas o de menos, manos fundidas con el mando o con otra mano.",
    "orientacion": ("la gente no mira a donde tiene que mirar (jugadores de\n"
                    "    espaldas a la tele, mirando a camara cuando juegan)."),
    "continuidad": "el mismo sitio, la misma\nestacion, los mismos mandos y la misma gente",
}

#: Las mismas frases sin ningún negocio dentro.
REVISOR_GENERAL = {
    "equipo": ("los objetos, el equipo o el producto no son los que mandan las\n"
               "    indicaciones o estan montados o colocados como no se hace de verdad\n"
               "    (tamanos imposibles, piezas de otro modelo, cables o soportes absurdos)."),
    "congruencia": ("el mismo sitio, los mismos objetos o la misma gente cambian de un\n"
                    "    plano a otro sin que el guion lo pida."),
    "manos": "dedos de mas o de menos, manos fundidas con lo que sujetan o con otra mano.",
    "orientacion": ("la gente no mira a donde tiene que mirar (de espaldas a lo que\n"
                    "    hace, mirando a camara cuando esta ocupada en otra cosa)."),
    "continuidad": "el mismo sitio, los\nmismos objetos y la misma gente",
}

ESTADOPLAY = {
    "id": "estadoplay",
    "nombre": "EstadoPlay (alquiler de consolas para eventos)",
    "servicios": SERVICIOS,
    "en_texto": SERVICIOS_EN_TEXTO,
    "escalera": ESCALERA_FOTO,
    "revisor": REVISOR_ESTADOPLAY,
    # con el dominio FIJADO en el estilo y ningún servicio nombrado en el
    # texto: los de su negocio (en automático no se usa: ahí, ninguno)
    "por_defecto": ("consolas",),
}

GENERAL = {
    "id": "general",
    "nombre": "General (cualquier negocio)",
    "servicios": (),
    "en_texto": {},
    "escalera": (),
    "revisor": REVISOR_GENERAL,
    "por_defecto": (),
}

#: Los de fábrica, por id. Uno nuevo se añade aquí (y su prueba).
DE_FABRICA = {d["id"]: d for d in (GENERAL, ESTADOPLAY)}

#: El valor de `estilo.dominio` que pide la detección por texto de siempre.
AUTOMATICO = ""


def normalizar(valor):
    """Lo que se guarda en `estilo.dominio`. -> "" (automático) o un id de fábrica.

    Lanza ValueError con un id que no existe."""
    if valor in (None, "", "auto", "automatico", "automático"):
        return AUTOMATICO
    if not isinstance(valor, str):
        raise ValueError("el dominio es el id de uno de fábrica: "
                         + ", ".join(DE_FABRICA))
    clave = valor.strip().lower()
    if clave not in DE_FABRICA:
        raise ValueError(f"«{valor}» no es un dominio (valen: {', '.join(DE_FABRICA)})")
    return clave


def fijado(estilo):
    """El dominio que fija el estilo, o None si es automático (o no vale)."""
    try:
        clave = normalizar((estilo or {}).get("dominio"))
    except ValueError:
        return None
    return DE_FABRICA.get(clave) if clave else None


def servicios_en_texto(texto, dominio=None):
    """Los servicios que nombra un texto, según los patrones del dominio
    (sin dominio, los de EstadoPlay: lo de siempre). -> tupla"""
    texto = str(texto or "")
    patrones = (dominio or ESTADOPLAY)["en_texto"]
    if not texto or not patrones:
        return ()
    return tuple(nombre for nombre, lista in patrones.items()
                 if any(re.search(pat, texto, flags=re.IGNORECASE) for pat in lista))


def de_estilo(estilo, texto=""):
    """El dominio que rige: el fijado o, en automático, el que delata el texto.

    -> (dominio, automatico: bool). En automático es EstadoPlay si el texto
    nombra alguno de sus servicios, y general si no."""
    propio = fijado(estilo)
    if propio is not None:
        return propio, False
    return (ESTADOPLAY if servicios_en_texto(texto) else GENERAL), True


def frases_revisor(estilo, texto=""):
    """Las frases del revisor para este vídeo. -> dict"""
    dominio, _ = de_estilo(estilo, texto)
    return dict(dominio["revisor"])


def listar():
    """[{id, nombre, servicios}] de los de fábrica, para la pantalla."""
    return [{"id": d["id"], "nombre": d["nombre"], "servicios": list(d["servicios"])}
            for d in DE_FABRICA.values()]

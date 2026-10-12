"""Lo mismo que se pedia, sin marcas ni personajes protegidos.

    reescribir(prompt) -> {"prompt", "cambios": [(antes, despues)], "como"}
    quitar_con_tabla(texto) -> (texto, cambios)

Para que
--------
El filtro de OpenAI rechaza las imagenes que piden marcas, logos o personajes
con derechos («Your request was rejected by the safety system»). Paso de verdad
el 10-10-2026 con un video de Mario Kart: la tanda se paraba entera y el
error salia en todas las pantallas sin decir que hacer.

No se intenta saltar el filtro: se pide LO MISMO QUE SE VE --colores, formas,
la escena, la accion, el encuadre-- con nombres genericos. «Mario Kart» pasa a
«un videojuego de carreras de karts de dibujos animados, colorido, con
personajes caricaturescos genericos»; los mandos de una Switch, a «mandos
desmontables rojo y azul de una consola portatil». La imagen sale lo mas
parecida posible y sin copiar nada de nadie, que es ademas lo unico que se
puede usar en un video para un cliente.

Dos caminos, en este orden:
  1. el CLI de Claude (suscripcion, no cuesta imagenes), que entiende el
     contexto y no deja frases rotas;
  2. una TABLA de las marcas que mas salen, que funciona sin red y es la red de
     seguridad si el CLI no esta.

Lo que NO hace: rebajar nada que no sea propiedad intelectual. Si el rechazo es
por otra cosa, el prompt reescrito sigue pidiendo lo mismo y el segundo
intento vuelve a fallar: se dice y se para ahi.
"""
import re

try:
    from . import cli_claude, comun
except ImportError:                                   # corriendo desde pasos/
    try:
        import cli_claude
        import comun
    except ImportError:                               # dentro de un motor suelto
        cli_claude = None
        comun = None

MAX_PROMPT = 16000

#: (patron, generico en ingles). Los prompts del motor van en ingles. El orden
#: importa: lo largo antes que lo corto («Nintendo Switch» antes que «Switch»).
TABLA = [
    (r"mario\s*kart", "a colorful cartoon kart-racing video game with generic "
                      "cartoon characters driving go-karts on a bright track"),
    (r"super\s+mario(\s+bros\.?)?", "a colorful cartoon platform video game"),
    # Solo los que no son nombres de persona corrientes: «Mario» a secas puede
    # ser alguien del reparto (es un nombre comun), y se lo llevaba por delante
    (r"\bbowser\b|\byoshi\b|princess\s+peach|donkey\s+kong",
     "a generic cartoon character"),
    (r"nintendo\s+switch(\s+(oled|lite))?", "a handheld hybrid game console with "
                                            "detachable red and blue controllers"),
    (r"joy[\s-]?cons?", "small detachable red and blue game controllers"),
    (r"\bnintendo\b", "a video game console"),
    (r"playstation\s*\d?|\bps[45]\b", "a modern home video game console"),
    (r"dualsense|dualshock", "a black and white gamepad"),
    (r"\bxbox(\s+series\s+[xs]|\s+one)?\b", "a modern home video game console"),
    (r"pok[eé]mon|pikachu", "a cute generic cartoon creature"),
    (r"minecraft", "a blocky voxel-style video game world"),
    (r"fortnite", "a colorful cartoon battle video game"),
    (r"\bdisney\b|mickey\s+mouse|\bmarvel\b|spider[\s-]?man|\bpixar\b",
     "a generic cartoon character"),
    (r"coca[\s-]?cola|\bpepsi\b", "a soda bottle with a plain red label"),
    (r"\biphone\b|\bipad\b|\bmacbook\b|\bapple\b(?=\s+(logo|watch|device))",
     "a sleek modern device without logos"),
    (r"\bsamsung\b|\bsony\b|\blg\b(?=\s+tv)", "unbranded"),
    (r"\bnike\b|\badidas\b", "unbranded sports"),
]

INSTRUCCION = """Reescribe este prompt de generacion de imagen para que NO
nombre ni dibuje ninguna MARCA, LOGO, PRODUCTO COMERCIAL CONCRETO, VIDEOJUEGO,
PERSONAJE CON DERECHOS NI PERSONA REAL. Sustituye cada uno por una descripcion
GENERICA que conserve lo que se VE: colores, forma, tamano, materiales, la
accion, la escena, el encuadre y la luz. Ningun nombre propio de producto.
Anade al final: "No logos, no brand names, no trademarked characters."

No cambies NADA mas: ni el estilo, ni las reglas, ni el idioma de los textos
que se pidan dibujados, ni el resto de instrucciones. No suavices ni quites
nada que no sea propiedad intelectual.

<prompt>
{prompt}
</prompt>

Devuelve SOLO este JSON:
{{"prompt": "<el prompt entero reescrito>",
  "cambios": [["<lo que habia>", "<lo que has puesto>"]]}}"""


def quitar_con_tabla(texto):
    """La red de seguridad sin red. -> (texto, [(antes, despues)])"""
    cambios = []
    salida = str(texto or "")
    for patron, generico in TABLA:
        def poner(encaje, generico=generico):
            cambios.append((encaje.group(0), generico))
            antes = encaje.string[:encaje.start()]
            # «on a Nintendo Switch» -> «on a handheld...», no «on a a handheld»
            if re.search(r"\b(a|an|the|my|his|her|their|our|your)\s+$", antes, re.I):
                return re.sub(r"^(a|an)\s+", "", generico)
            return generico
        salida = re.sub(patron, poner, salida, flags=re.I)
    if cambios and "no logos" not in salida.lower():
        salida = salida.rstrip()
        if salida and salida[-1] not in ".!?":
            salida += "."
        salida += " No logos, no brand names, no trademarked characters."
    return salida, cambios


def reescribir(prompt, cwd=None, usar_cli=True):
    """El prompt sin marcas. -> {"prompt", "cambios", "como"}"""
    prompt = str(prompt or "")
    if usar_cli and cli_claude is not None and len(prompt) <= MAX_PROMPT:
        try:
            respuesta, _sobre = cli_claude.ejecutar(
                INSTRUCCION.format(prompt=prompt), modelo="sonnet", esfuerzo="low",
                cwd=cwd, base_tiempo_s=90,
                sistema="Reescribes prompts de imagen quitando marcas y personajes "
                        "con derechos. Contestas solo con el JSON pedido.",
                extra=["--no-session-persistence"], para="quitar las marcas")
            datos = comun.extraer_json(respuesta, "quitar las marcas")
            nuevo = str((datos or {}).get("prompt") or "").strip()
            if nuevo and len(nuevo) > len(prompt) * 0.5:
                cambios = [tuple(map(str, c[:2])) for c in (datos.get("cambios") or [])
                           if isinstance(c, (list, tuple)) and len(c) >= 2]
                # la tabla detras, por si al modelo se le escapo alguna
                nuevo, extra = quitar_con_tabla(nuevo)
                return {"prompt": nuevo, "cambios": cambios + extra, "como": "claude"}
        except Exception:                                   # noqa: BLE001
            pass                    # sin CLI se sigue con la tabla
    nuevo, cambios = quitar_con_tabla(prompt)
    return {"prompt": nuevo, "cambios": cambios, "como": "tabla"}


def tiene_marcas(texto):
    """Si la tabla encuentra algo protegido en el texto. -> [lo encontrado]"""
    return [c[0] for c in quitar_con_tabla(texto)[1]]


# ----------------------------------------------------------- la NOTA, en castellano
#
# Lo de arriba reescribe el prompt en ingles que va al motor (automatico, al
# primer rechazo). Esto es lo que se le PROPONE a la persona para su nota, en
# castellano y editable antes de usarlo: «lo mas parecido posible sin copiar».

TABLA_ES = [
    (r"mario\s*kart", "un videojuego de carreras de karts de dibujos animados, "
                      "colorido, con personajes caricaturescos genéricos"),
    (r"nintendo\s+switch", "una consola portátil híbrida con dos mandos pequeños "
                           "desmontables, uno rojo y otro azul"),
    (r"joy[\s-]?cons?", "mandos pequeños desmontables rojo y azul"),
    (r"\bnintendo\b", "una consola de videojuegos"),
    (r"playstation\s*\d?|\bps[45]\b", "una consola de sobremesa moderna"),
    (r"\bxbox\b", "una consola de sobremesa moderna"),
    (r"pok[eé]mon|pikachu", "una criatura de dibujos animados genérica"),
    (r"\bbowser\b|\byoshi\b", "un personaje de dibujos animados genérico"),
    (r"coca[\s-]?cola|\bpepsi\b", "un refresco con etiqueta roja lisa"),
    (r"\biphone\b", "un móvil moderno sin logos"),
]

INSTRUCCION_NOTA = """Esta es una nota de correccion que una persona escribio
sobre una imagen de su video. OpenAI ha rechazado dibujarla, casi seguro porque
nombra MARCAS, PRODUCTOS, VIDEOJUEGOS O PERSONAJES CON DERECHOS.

Reescribela en castellano para que se dibuje LO MAS PARECIDO POSIBLE sin copiar
nada protegido: describe lo que se VE (colores, formas, tamano, materiales,
disposicion, la accion, el ambiente, el estilo de lo que sale en una pantalla)
sin ningun nombre de marca, producto, juego ni personaje. Conserva todo lo
demas que pide la nota. Si dice que algo «no se parece» a un producto, describe
como es ese producto por fuera, sin nombrarlo y sin logos.

<nota>
{texto}
</nota>

Devuelve SOLO este JSON:
{{"texto": "<la nota reescrita>", "cambios": [["<lo que habia>", "<lo que has puesto>"]]}}"""


def reescribir_nota(texto, cwd=None, usar_cli=True):
    """La nota sin marcas, para ensenarla y editarla. -> {"texto", "cambios", "como"}"""
    texto = " ".join(str(texto or "").split())
    if usar_cli and cli_claude is not None and texto:
        try:
            respuesta, _sobre = cli_claude.ejecutar(
                INSTRUCCION_NOTA.format(texto=texto), modelo="sonnet", esfuerzo="low",
                cwd=cwd, base_tiempo_s=45,
                sistema="Reescribes notas de correccion de imagen quitando marcas y "
                        "personajes con derechos. Contestas solo con el JSON pedido.",
                extra=["--no-session-persistence"], para="quitar las marcas de la nota")
            datos = comun.extraer_json(respuesta, "quitar las marcas de la nota")
            nuevo = " ".join(str((datos or {}).get("texto") or "").split())
            if nuevo:
                cambios = [tuple(map(str, c[:2])) for c in (datos.get("cambios") or [])
                           if isinstance(c, (list, tuple)) and len(c) >= 2]
                return {"texto": nuevo, "cambios": cambios, "como": "claude"}
        except Exception:                                   # noqa: BLE001
            pass
    cambios = []
    salida = texto
    for patron, generico in TABLA_ES:
        def poner(encaje, generico=generico):
            cambios.append((encaje.group(0), generico))
            return generico
        salida = re.sub(patron, poner, salida, flags=re.I)
    if cambios:
        salida = salida.rstrip(" .") + ". Sin logos ni marcas."
    return {"texto": salida, "cambios": cambios, "como": "tabla"}

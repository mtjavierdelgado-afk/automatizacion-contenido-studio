"""QUE DIBUJAN LAS IMAGENES: lo que dice la voz o lo que dice el guion (rama guion-visual).

EL HUECO QUE TAPA (prueba real de la mampara, 21-10-2026)
---------------------------------------------------------
El «Guion» del Studio es la LOCUCION: lo que se oye. Que se ve lo inventaba el
catalogo (una `accion` por tramo) y cada plano se ataba a su frase
(`p6_assets._con_narracion`: «Show the specific moment that line describes»).
Asi, si la voz decia «una corrediza», se dibujaba una corrediza aunque el estado
aprobado del tipo de relato fuera la batiente. Y las lineas «Visual:» de la
Parrilla -- lo que el dueño escribe que se VE -- se leian y se tiraban.

Con «lo que dice el guion» manda un GUION VISUAL: una lista de planos, cada uno
atado a un bloque de la voz (que solo pone el reloj), con lo que se ve, la
camara y, si el video es «un espacio que cambia», el estado del objeto. Sale de
las lineas «Visual:» de la Parrilla o de un borrador que escribe Claude, y lo
aprueba una persona antes de pagar ninguna imagen.

REGLA 1
-------
«Lo que dice la voz» es el defecto y NO se guarda: sin `assets.imagenes` (ni
`estilo.imagenes`) igual a "guion", ningun plan, prompt ni firma cambia.

Aqui solo hay datos y funciones puras, mas las dos llamadas a Claude (proponer
y comprobar), que no escriben nada: devuelven y la ruta guarda.
"""
import hashlib
import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from . import cli_claude, comun, estadisticas
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun
    import estadisticas

PASO = "catalogo_visual"            # mismo canal de Claude que el catalogo
MODELO_POR_DEFECTO = cli_claude.por_defecto_de(PASO)["modelo"]
ESFUERZO_POR_DEFECTO = cli_claude.por_defecto_de(PASO)["esfuerzo"]
TIEMPO_BASE_S = 420
SISTEMA = ("Responde exclusivamente con el objeto JSON pedido, sin texto "
           "alrededor y sin bloques de codigo.")
HERRAMIENTAS_VETADAS = ("Bash", "Read", "Write", "Edit", "NotebookEdit", "Glob",
                        "Grep", "WebFetch", "WebSearch", "Task")

#: Lo que se puede elegir. "voz" es el defecto y no se guarda nunca.
MODOS = {"voz": "Lo que dice la voz", "guion": "Lo que dice el guion"}
MAX_PLANOS = 400
MAX_VISUAL = 600
MAX_CAMARA = 160
ORIGENES = ("parrilla", "claude", "manual")


def _texto(valor, tope):
    return " ".join(str(valor or "").split())[:tope]


def _llano(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _etiqueta(valor):
    return re.sub(r"[^a-z0-9_]", "", _llano(valor).replace(" ", "_"))[:30]


# ------------------------------------------------------------ modo

def normalizar_modo(valor):
    """"guion" o "" (= lo de siempre). Lanza ValueError si no es ninguno."""
    if valor is None:
        return ""
    llano = _llano(valor).strip()
    if llano in ("", "voz", "lo que dice la voz", "por defecto"):
        return ""
    if llano in ("guion", "lo que dice el guion"):
        return "guion"
    raise ValueError(f"«{valor}» no es un modo: «voz» o «guion»")


def modo_de(params):
    """El modo que rige: el del video, si no el del estilo, si no "voz"."""
    p = params or {}
    for crudo in (p.get("imagenes"), ((p.get("estilo") or {}) if isinstance(
            p.get("estilo"), dict) else {}).get("imagenes")):
        try:
            modo = normalizar_modo(crudo)
        except ValueError:
            modo = ""
        if modo:
            return modo
        if crudo not in (None, ""):
            return "voz"       # el video dijo «voz» explicitamente: manda
    return "voz"


# ------------------------------------------------------------ el guion visual

def _plano(crudo, bloques_validos=None):
    if not isinstance(crudo, dict):
        raise ValueError("cada plano del guion visual tiene que ser un objeto")
    visual = _texto(crudo.get("visual"), MAX_VISUAL)
    if not visual:
        raise ValueError("un plano del guion visual sin «visual»")
    bloque = _texto(crudo.get("bloque"), 20).upper()
    if bloques_validos is not None and bloque not in bloques_validos:
        raise ValueError(f"el plano «{visual[:40]}» apunta a un bloque que no existe ({bloque})")
    salida = {"bloque": bloque, "visual": visual}
    camara = _texto(crudo.get("camara"), MAX_CAMARA)
    if camara:
        salida["camara"] = camara
    estado = _etiqueta(crudo.get("estado"))
    if estado:
        salida["estado"] = estado
    gente = crudo.get("personajes")
    if isinstance(gente, list):
        gente = [_texto(x, 60) for x in gente if _texto(x, 60)][:8]
        if gente:
            salida["personajes"] = gente
    return salida


def normalizar(crudo, bloques_validos=None):
    """`assets.guion_visual` tal como se guarda. -> {} o {origen, planos, aprobado, visuales?}

    `visuales` son las escenas de la Parrilla tal cual llegaron (voz + lineas
    «Visual:»), por si el guion aun no existe y hay que casarlas despues. Los
    planos llevan id V001… en orden. Lanza ValueError si llega mal formado."""
    if crudo in (None, "", {}):
        return {}
    if not isinstance(crudo, dict):
        raise ValueError("guion_visual tiene que ser un objeto")
    origen = str(crudo.get("origen") or "manual")
    if origen not in ORIGENES:
        raise ValueError(f"guion_visual.origen: «{origen}» no vale")
    planos = crudo.get("planos") or []
    if not isinstance(planos, list) or len(planos) > MAX_PLANOS:
        raise ValueError(f"guion_visual.planos: una lista de como mucho {MAX_PLANOS}")
    limpios = []
    for i, plano in enumerate(planos):
        limpio = _plano(plano, bloques_validos)
        limpio = {"id": f"V{i + 1:03d}", **limpio}
        limpios.append(limpio)
    salida = {"origen": origen, "planos": limpios,
              "aprobado": bool(crudo.get("aprobado")) and bool(limpios)}
    visuales = crudo.get("visuales")
    if visuales:
        salida["visuales"] = normalizar_visuales(visuales)
    return salida


def normalizar_visuales(crudo):
    """Las escenas de la Parrilla: [{voz, visual: [lineas]}]."""
    if not isinstance(crudo, list):
        raise ValueError("guion_visual.visuales tiene que ser una lista")
    salida = []
    for escena in crudo[:MAX_PLANOS]:
        if not isinstance(escena, dict):
            continue
        lineas = [_texto(x, MAX_VISUAL) for x in (escena.get("visual") or [])
                  if _texto(x, MAX_VISUAL)]
        if lineas:
            salida.append({"voz": _texto(escena.get("voz"), 3000), "visual": lineas})
    return salida


def visuales_de_parrilla(escenas):
    """Las escenas de un guion de la Parrilla que traen «Visual:». -> [{voz, visual}]"""
    return normalizar_visuales([{"voz": e.get("voz"), "visual": e.get("visual")}
                                for e in (escenas or []) if isinstance(e, dict)])


def activo(params):
    """Los planos del guion visual que mandan, o None.

    Solo en modo «guion» y con el guion visual APROBADO: sin aprobar no se usa
    nada (y `faltan` lo dice antes de pagar)."""
    if modo_de(params) != "guion":
        return None
    try:
        gv = normalizar((params or {}).get("guion_visual"))
    except ValueError:
        return None
    if not gv.get("aprobado"):
        return None
    return gv["planos"] or None


# ------------------------------------------------------------ casar con el guion

def _palabras(texto):
    return [w for w in re.findall(r"[a-z0-9ñ]+", _llano(texto)) if len(w) > 2]


def casar(visuales, bloques):
    """Ata cada escena de la Parrilla a su bloque del guion, sin llamar a nadie.

    -> (planos, avisos). Cada linea «Visual:» es un plano del bloque cuya voz
    mas se parece a la de su escena (por palabras compartidas). Una escena sin
    voz va al bloque de la escena anterior. Si no hay guion todavia, nada."""
    bloques = [b for b in (bloques or []) if str(b.get("id") or "").strip()]
    if not bloques or not visuales:
        return [], []
    bolsas = [(str(b["id"]).upper(), set(_palabras(b.get("texto")))) for b in bloques]
    planos, avisos = [], []
    ultimo = bolsas[0][0]
    for n, escena in enumerate(visuales, 1):
        voz = set(_palabras(escena.get("voz")))
        elegido = None
        if voz:
            mejor = max(bolsas, key=lambda par: (len(voz & par[1]) / max(1, len(voz)), -bolsas.index(par)))
            if voz & mejor[1]:
                elegido = mejor[0]
        if elegido is None:
            elegido = ultimo
            avisos.append(f"la escena {n} de la Parrilla no casa con ningún bloque del guion: "
                          f"va con {elegido}; revísalo")
        ultimo = elegido
        for linea in escena.get("visual") or []:
            planos.append({"bloque": elegido, "visual": linea})
    return planos, avisos


# ------------------------------------------------------------ el corte

def segmentos(palabras, bloque_de, planos):
    """El corte en planos del modo guion: uno por linea visual.

    `palabras` son las marcas de la voz en orden y `bloque_de[i]` el id del
    bloque de la palabra i. Las lineas de un mismo bloque se reparten sus
    palabras a partes iguales (en cortes de palabra). Un bloque sin lineas se
    queda con la linea anterior (continua lo que se estaba viendo).

    -> (segmentos [(inicio, fin, palabras)], lineas [plano], avisos)."""
    if not palabras:
        return [], [], []
    por_bloque = {}
    for plano in planos or []:
        por_bloque.setdefault(plano["bloque"], []).append(plano)
    # tramos de palabras por bloque, en orden
    tramos = []
    for i, bid in enumerate(bloque_de):
        if tramos and tramos[-1][0] == bid:
            tramos[-1][2] = i + 1
        else:
            tramos.append([bid, i, i + 1])
    avisos = []
    usados = set()
    cortes, lineas = [], []
    anterior = None
    for bid, ini, fin in tramos:
        suyas = por_bloque.get(bid) or []
        if not suyas:
            if anterior is None:
                anterior = (planos or [None])[0]
            if cortes and lineas and lineas[-1] is anterior:
                cortes[-1][1] = fin            # se alarga el plano que se veia
            else:
                cortes.append([ini, fin])
                lineas.append(anterior)
            continue
        usados.add(bid)
        n = min(len(suyas), fin - ini)
        if n < len(suyas):
            avisos.append(f"el bloque {bid} tiene {len(suyas)} planos y solo "
                          f"{fin - ini} palabra(s): se quedan {n}")
        for k in range(n):
            a = ini + (fin - ini) * k // n
            b = ini + (fin - ini) * (k + 1) // n
            cortes.append([a, b])
            lineas.append(suyas[k])
        anterior = suyas[n - 1]
    for bid in por_bloque:
        if bid not in usados and bid not in {t[0] for t in tramos}:
            avisos.append(f"el bloque {bid} del guion visual no está en la voz: "
                          f"sus planos no salen")
    segs = [(palabras[a]["s"], palabras[b - 1]["e"], palabras[a:b]) for a, b in cortes]
    return segs, lineas, avisos


def estado_de_linea(plano, estados):
    """{cambio, estado} con que se edita el plano: el de su linea, o la base."""
    estado = (plano or {}).get("estado") or ""
    if estado and estado in (estados or {}):
        return {"cambio": estados[estado], "estado": estado}
    return {"cambio": "", "estado": ""}


# ------------------------------------------------------------ Claude: proponer

INSTRUCCION_PROPONER = """Eres el director de un video. El texto de abajo es la
LOCUCION (lo que se oye), partida en bloques con su id. Escribe el GUION VISUAL:
la lista de planos que se VEN, en orden.

COMO
  - Cada plano es una imagen fija: quien sale, donde, que hace, que se ve. Una
    frase concreta y visual, en INGLES (la lee un generador de imagenes).
  - Cada plano va atado al bloque de la voz durante el que se ve ("bloque").
    Un bloque puede tener uno, dos o tres planos; todos los bloques al menos uno.
  - "camara": el encuadre, en ingles y corto ("wide shot from the doorway, eye
    level", "close-up of the hinge").
  - NO ilustres palabra por palabra lo que dice la voz: cuenta con imagenes lo
    que el video quiere contar. Si la voz menciona una alternativa o un «no
    hagas esto», decide tu que se ve para que se entienda.
  - Nada que contradiga lo fijo de abajo: el sitio es ese y solo ese, y los
    objetos que cambian solo pueden estar en uno de sus ESTADOS.
{estados_txt}
LO FIJO
<<<
{fijo}
>>>

LA LOCUCION, BLOQUE A BLOQUE
<<<
{guion}
>>>

DEVUELVE EXACTAMENTE ESTE JSON, sin nada alrededor:

{{
  "planos": [
    {{"bloque": "<id>", "visual": "<en ingles>", "camara": "<en ingles>",
      "estado": "<uno de los estados, o vacio>", "personajes": ["<id del reparto>"]}}
  ]
}}
"""


def _fijo_legible(espacio, reparto, estados):
    partes = []
    if espacio:
        partes.append(f"SITIO: {espacio.get('descripcion') or ''} "
                      f"(luz: {espacio.get('luz') or '-'})")
    for pid, ficha in (reparto or {}).items():
        partes.append(f"PERSONAJE {pid}: {(ficha or {}).get('descripcion') or ''}")
    for est, cambio in (estados or {}).items():
        partes.append(f"ESTADO {est}: {cambio}")
    return "\n".join(partes) or "(nada fijo: elige tu el sitio de cada plano)"


def proponer(bloques, espacio=None, reparto=None, estados=None, ajuste=None,
             avisar=None, proyecto_id=None, cwd=None):
    """El borrador del guion visual que escribe Claude. NO guarda nada.

    -> (planos, avisos)."""
    bloques = [b for b in (bloques or []) if str(b.get("id") or "").strip()]
    if not bloques:
        raise RuntimeError("no hay guion que leer: genera el guion antes")
    ajuste = ajuste or {}
    modelo = ajuste.get("modelo") or MODELO_POR_DEFECTO
    esfuerzo = ajuste.get("esfuerzo") or ESFUERZO_POR_DEFECTO
    guion = "\n".join(f"[{str(b['id']).upper()}] {_texto(b.get('texto'), 4000)}" for b in bloques)
    estados_txt = ("  - Los estados que existen son SOLO estos: "
                   + ", ".join(estados) + ".\n") if estados else ""
    instruccion = INSTRUCCION_PROPONER.format(
        estados_txt=estados_txt, fijo=_fijo_legible(espacio, reparto, estados), guion=guion)
    avance = None
    if avisar is not None:
        avance = estadisticas.Avance(
            avisar, 0.05, 0.9, estadisticas.estimar(PASO, tamano=len(guion) // 6,
                                                    ajuste={"modelo": modelo,
                                                            "esfuerzo": esfuerzo}),
            f"escribiendo el guion visual plano a plano, con {modelo}")
        avance.arrancar()
    arranque = time.time()
    try:
        texto, _sobre = _llamar_claude(instruccion, modelo, esfuerzo, cwd, avance,
                                       "el guion visual")
    finally:
        if avance is not None:
            avance.parar()
    estadisticas.anotar(PASO, time.time() - arranque, ajuste={"modelo": modelo,
                                                              "esfuerzo": esfuerzo},
                        proyecto=proyecto_id, unidades=len(bloques),
                        detalle={"que": "guion_visual"})
    crudo = comun.extraer_json(texto, "el guion visual")
    validos = {str(b["id"]).upper() for b in bloques}
    planos, avisos = [], []
    for item in (crudo or {}).get("planos") or []:
        try:
            plano = _plano(item, validos)
        except ValueError as fallo:
            avisos.append(f"un plano propuesto no vale y se quita: {fallo}")
            continue
        if plano.get("estado") and estados is not None and plano["estado"] not in estados:
            avisos.append(f"«{plano['visual'][:50]}» pedía el estado «{plano['estado']}», "
                          f"que no existe: va con la base")
            plano.pop("estado")
        planos.append(plano)
    sin = [b for b in validos if b not in {p["bloque"] for p in planos}]
    if sin:
        avisos.append("bloques sin plano propio (siguen viendo el anterior): "
                      + ", ".join(sorted(sin)))
    if not planos:
        raise RuntimeError("Claude no ha propuesto ningún plano que valga")
    return planos, avisos


def _llamar_claude(instruccion, modelo, esfuerzo, cwd, avance=None, para="el guion visual"):
    return cli_claude.ejecutar(
        instruccion, modelo=modelo, esfuerzo=esfuerzo, cwd=cwd,
        tiempo_max_s=0, base_tiempo_s=TIEMPO_BASE_S,
        sistema=SISTEMA, herramientas_vetadas=HERRAMIENTAS_VETADAS,
        extra=["--no-session-persistence"], avance=avance, para=para)


# ------------------------------------------------------------ Claude: comprobar

INSTRUCCION_COMPROBAR = """Eres el script supervisor de un video. Abajo esta LO
FIJO (el sitio, el reparto y los estados aprobados del objeto que cambia) y el
GUION VISUAL, plano a plano. Di que planos piden algo que CONTRADICE lo fijo: un
mueble o una pieza que el sitio no tiene, otro sitio, un estado que no existe,
un personaje que no esta en el reparto. Lo fijo manda: si un plano lo
contradice, se dibujara lo fijo. No juzgues el estilo ni el gusto: solo
contradicciones.

LO FIJO
<<<
{fijo}
>>>

EL GUION VISUAL
<<<
{planos}
>>>

DEVUELVE EXACTAMENTE ESTE JSON, sin nada alrededor (lista vacia si no hay nada):

{{"avisos": [{{"plano": "V001", "que": "<en castellano: que pide y que se dibujara>"}}]}}
"""


def comprobar(planos, espacio=None, reparto=None, estados=None, ajuste=None,
              cwd=None, proyecto_id=None):
    """Las contradicciones del guion visual con lo fijo. -> [{plano, que}]. Solo texto."""
    if not planos:
        return []
    ajuste = ajuste or {}
    modelo = ajuste.get("modelo") or "sonnet"
    esfuerzo = ajuste.get("esfuerzo") or "low"
    lista = "\n".join(f"{p.get('id') or ''} [{p.get('bloque')}] {p.get('visual')}"
                      + (f" · estado: {p['estado']}" if p.get("estado") else "")
                      + (f" · personajes: {', '.join(p['personajes'])}" if p.get("personajes") else "")
                      for p in planos)
    instruccion = INSTRUCCION_COMPROBAR.format(
        fijo=_fijo_legible(espacio, reparto, estados), planos=lista)
    arranque = time.time()
    texto, _sobre = _llamar_claude(instruccion, modelo, esfuerzo, cwd, None,
                                   "comprobar el guion visual")
    estadisticas.anotar(PASO, time.time() - arranque, ajuste={"modelo": modelo,
                                                              "esfuerzo": esfuerzo},
                        proyecto=proyecto_id, unidades=len(planos),
                        detalle={"que": "guion_visual_comprobar"})
    crudo = comun.extraer_json(texto, "la comprobación del guion visual")
    ids = {p.get("id") for p in planos}
    salida = []
    for item in (crudo or {}).get("avisos") or []:
        if isinstance(item, dict) and item.get("plano") in ids and _texto(item.get("que"), 300):
            salida.append({"plano": item["plano"], "que": _texto(item["que"], 300)})
    return salida


def huella(planos):
    """Para saber si la comprobacion guardada es de ESTE guion visual."""
    return hashlib.sha256(repr([(p.get("bloque"), p.get("visual"), p.get("estado"),
                                 tuple(p.get("personajes") or ()))
                                for p in planos or []]).encode("utf-8")).hexdigest()[:16]

"""EL TIPO DE RELATO: como se cuenta un video en imagenes (rama tipo-de-relato,
20-10-2026, pedido del dueño).

Un «tipo de relato» habla de ESTRUCTURA, nunca de un negocio:

  documental           lo de siempre: el guion se reparte en sitios.
  espacio_que_cambia   un sitio con imagen base; cada plano cambia SOLO lo que
                       nombra la voz (subtipo `cambia`: objeto, acabados,
                       estado u hora).
  recorrido            varios ambientes de un mismo lugar con la misma luz,
                       materiales y estilo. En esta rama, un solo espacio.
  escenario_y_apoyos   el espacio fijo de siempre, con sus secundarios.
  producto             el producto es protagonista y el fondo no se mueve.
  clase                se declara aqui; su comportamiento llega en la rama
                       formato-clase (hasta entonces, como `recorrido`).

POR QUE EXISTE. En un Reel sobre un baño cada imagen salia con un baño
distinto: la foto del sitio iba como una referencia mas, detras de las de
estilo, y el texto decia «la camara puede ponerse donde quiera». Para que un
sitio sea EL MISMO sitio hace falta EDITAR una imagen base (misma camara, misma
distribucion) y cambiar solo lo que se pide.

DONDE SE GUARDA (regla 1 de CLAUDE.md: solo cuando alguien lo elige)
  - por video: `assets.tipo_relato = {modo, cambia?, bases?}`;
  - por defecto del estilo: `estilo.relato = {modo, cambia?}`, que viaja en el
    preset de Estilo grafico y, con el, en el de Canal.

COMO SE RESUELVE (`resolver`, decision del dueño del 20-10, opcion B)
  1. el del video (Encargo o Parrilla);
  2. el del estilo, si no es documental;
  3. si hay espacio fijo con descripcion: escenario_y_apoyos IMPLICITO;
  4. documental.
El espacio fijo dice DONDE pasa el video y el modo dice COMO se cuenta: no
compiten. Lo que importa para las firmas es `explicito`: con un modo implicito
(documental, o escenario_y_apoyos por haber espacio fijo) no se ejecuta ni una
linea nueva y prompts, cartas y firmas salen byte a byte como antes de esta
rama. Todo lo nuevo cuelga de `explicito`.

Este modulo solo tiene datos y funciones puras: no lee disco ni llama a nadie.
"""
import hashlib
import re
import unicodedata

#: clave -> nombre visible. El orden es el de la pantalla.
MODOS = {
    "documental": "Documental",
    "espacio_que_cambia": "Un espacio que cambia",
    "recorrido": "Recorrido",
    "escenario_y_apoyos": "Escenario y apoyos",
    "producto": "Producto",
    "clase": "Clase",
}

#: lo que cambia en «un espacio que cambia». clave -> nombre visible.
CAMBIA = {
    "objeto": "Un objeto",
    "acabados": "Los acabados",
    "estado": "El estado",
    "hora": "La hora",
}

#: Los modos cuyos planos se generan EDITANDO la imagen base del sitio.
EDITAN = ("espacio_que_cambia", "producto")

#: Las familias de carta que NO se editan desde la base aunque el modo edite:
#: un detalle macro con la camara de la base no es un detalle, y un diagrama no
#: ocurre en ningun sitio. Esos planos llevan la base como REFERENCIA del sitio
#: (decision del dueño del 20-10: «planos de detalle como referencia»).
FAMILIAS_SIN_EDICION = ("cerca", "abstracta")

#: La imagen base se guarda en la carpeta del espacio fijo del proyecto, con
#: ruta RELATIVA (viaja con la carpeta en una mudanza sin tocar nada).
RE_IMAGEN_BASE = re.compile(r"^espacio_fijo/[0-9a-f]{12,40}\.png$")

MAX_SITIOS_BASE = 12


def _llano(texto):
    """Minusculas, sin tildes, con espacios y guiones como «_»."""
    sin = unicodedata.normalize("NFKD", str(texto or ""))
    sin = "".join(c for c in sin if not unicodedata.combining(c)).lower().strip()
    return re.sub(r"[\s\-]+", "_", sin)


_POR_NOMBRE = {}
for _clave, _nombre in MODOS.items():
    _POR_NOMBRE[_llano(_clave)] = _clave
    _POR_NOMBRE[_llano(_nombre)] = _clave
_POR_NOMBRE["espacio_que_cambia"] = "espacio_que_cambia"
_POR_NOMBRE["escenario_apoyos"] = "escenario_y_apoyos"

_CAMBIA_POR_NOMBRE = {}
for _clave, _nombre in CAMBIA.items():
    _CAMBIA_POR_NOMBRE[_llano(_clave)] = _clave
    _CAMBIA_POR_NOMBRE[_llano(_nombre)] = _clave
_CAMBIA_POR_NOMBRE.update({"objetos": "objeto", "acabado": "acabados",
                           "estados": "estado", "horas": "hora", "luz": "hora"})


def modo_de_texto(texto):
    """La clave del modo que nombra `texto` (clave o nombre visible, con o sin
    tildes, en mayusculas o no). -> clave o None."""
    return _POR_NOMBRE.get(_llano(texto))


def cambia_de_texto(texto):
    """La clave de `cambia` que nombra `texto`. -> clave o None."""
    return _CAMBIA_POR_NOMBRE.get(_llano(texto))


def leer_linea(texto):
    """«espacio_que_cambia (acabados)», «Un espacio que cambia — acabados»,
    «Producto»... -> {modo, cambia?}. Lanza ValueError si no se reconoce.

    Es lo que lee la linea «Tipo de relato:» de la cabecera de la Parrilla."""
    crudo = " ".join(str(texto or "").split())
    if not crudo:
        raise ValueError("vacío")
    cambia = ""
    m = re.match(r"^(.*?)\s*\(\s*([^)]*)\s*\)\s*$", crudo)
    if m:
        crudo, cambia = m.group(1), m.group(2)
    else:
        partes = re.split(r"\s+[—–-]\s+|\s*[:/,]\s*", crudo, maxsplit=1)
        if len(partes) == 2 and not modo_de_texto(crudo):
            crudo, cambia = partes
    modo = modo_de_texto(crudo)
    if not modo:
        raise ValueError(f"«{crudo}» no es un tipo de relato (valen: "
                         + ", ".join(MODOS) + ")")
    salida = {"modo": modo}
    if cambia.strip():
        clave = cambia_de_texto(cambia)
        if not clave:
            raise ValueError(f"«{cambia}» no es lo que cambia (valen: "
                             + ", ".join(CAMBIA) + ")")
        if modo == "espacio_que_cambia":
            salida["cambia"] = clave
    if modo == "espacio_que_cambia" and "cambia" not in salida:
        salida["cambia"] = "objeto"
    return salida


def _normalizar_modo_y_cambia(crudo, donde):
    if not isinstance(crudo, dict):
        raise ValueError(f"{donde} tiene que ser un objeto con modo (y cambia)")
    modo = crudo.get("modo")
    if modo in (None, ""):
        return {}
    clave = modo_de_texto(modo) if isinstance(modo, str) else None
    if not clave:
        raise ValueError(f"{donde}.modo: «{modo}» no es un tipo de relato "
                         f"(valen: {', '.join(MODOS)})")
    salida = {"modo": clave}
    cambia = crudo.get("cambia")
    if clave == "espacio_que_cambia":
        if cambia in (None, ""):
            salida["cambia"] = "objeto"
        else:
            sub = cambia_de_texto(cambia) if isinstance(cambia, str) else None
            if not sub:
                raise ValueError(f"{donde}.cambia: «{cambia}» no vale "
                                 f"(valen: {', '.join(CAMBIA)})")
            salida["cambia"] = sub
    return salida


def normalizar(crudo):
    """`assets.tipo_relato` tal como se guarda. -> {} o {modo, cambia?, bases?}

    {} es «el video no fija tipo de relato» (se resuelve por el estilo o por el
    espacio fijo). Lanza ValueError si llega mal formado.

    `bases` es {sitio: {"imagen": "espacio_fijo/<huella>.png", "aprobada": bool,
    "estados"?: {estado: {imagen, aprobada, cambio}}}}: la imagen base de cada
    sitio y si alguien la ha aprobado, y en «un espacio que cambia» la imagen de
    cada ESTADO (la base ya cambiada, una vez). Sin aprobar no se edita ningun
    plano desde ella."""
    if crudo is None or crudo == "" or crudo == {}:
        return {}
    salida = _normalizar_modo_y_cambia(crudo, "tipo_relato")
    bases = crudo.get("bases")
    if bases not in (None, {}):
        if not isinstance(bases, dict):
            raise ValueError("tipo_relato.bases tiene que ser un objeto {sitio: base}")
        if len(bases) > MAX_SITIOS_BASE:
            raise ValueError(f"tipo_relato.bases: como mucho {MAX_SITIOS_BASE} sitios")
        limpias = {}
        for sitio, ficha in bases.items():
            sid = re.sub(r"[^a-z0-9_]", "", _llano(sitio))[:120]
            if not sid:
                raise ValueError("tipo_relato.bases: un sitio sin nombre")
            if not isinstance(ficha, dict):
                raise ValueError(f"tipo_relato.bases.{sid} tiene que ser "
                                 f"{{imagen, aprobada}}")
            imagen = ficha.get("imagen")
            if not isinstance(imagen, str) or not RE_IMAGEN_BASE.match(imagen):
                raise ValueError(f"tipo_relato.bases.{sid}.imagen no es una imagen "
                                 f"guardada del espacio: genérala o súbela otra vez")
            limpias[sid] = {"imagen": imagen, "aprobada": bool(ficha.get("aprobada"))}
            estados = _normalizar_estados(ficha.get("estados"), sid)
            if estados:
                limpias[sid]["estados"] = estados
        if limpias:
            salida["bases"] = limpias
    if not salida.get("modo") and not salida.get("bases"):
        return {}
    return salida


#: Estados distintos por sitio, como mucho (un video de 30 s trae 2-4).
MAX_ESTADOS = 12


def _normalizar_estados(crudo, sid):
    """Las imagenes de cada estado de un sitio. -> {estado: {imagen, aprobada, cambio}}"""
    if crudo in (None, {}):
        return {}
    if not isinstance(crudo, dict):
        raise ValueError(f"tipo_relato.bases.{sid}.estados tiene que ser un objeto")
    if len(crudo) > MAX_ESTADOS:
        raise ValueError(f"tipo_relato.bases.{sid}.estados: como mucho {MAX_ESTADOS}")
    salida = {}
    for estado, ficha in crudo.items():
        clave = _etiqueta(estado)
        if not clave or not isinstance(ficha, dict):
            raise ValueError(f"tipo_relato.bases.{sid}.estados: un estado mal formado")
        imagen = ficha.get("imagen")
        if not isinstance(imagen, str) or not RE_IMAGEN_BASE.match(imagen):
            raise ValueError(f"tipo_relato.bases.{sid}.estados.{clave}.imagen no es una "
                             f"imagen guardada del espacio")
        salida[clave] = {"imagen": imagen, "aprobada": bool(ficha.get("aprobada")),
                         "cambio": _texto(ficha.get("cambio"), 400)}
    return salida


def clave_estado(sitio, estado):
    """La clave de la imagen de un estado en el mapa de bases: «sitio#estado»."""
    return f"{sitio}#{estado}"


def estado_de(beat):
    """La etiqueta del estado de un tramo con cambio (o "" si no cambia nada).

    Un tramo con cambio y sin etiqueta recibe una sacada del propio cambio,
    para que dos tramos con el mismo cambio compartan imagen."""
    cambio = _texto((beat or {}).get("cambio"), 400)
    if not cambio:
        return ""
    return _etiqueta((beat or {}).get("estado")) or "c" + hashlib.sha1(
        cambio.encode("utf-8")).hexdigest()[:8]


def lleva_estados(relato):
    """¿Cada estado se dibuja UNA vez, aprobado, y los planos lo editan?
    Solo en «un espacio que cambia» (prueba real del 21-10: la mampara abierta
    se reinventaba en cada plano)."""
    return activo(relato) and relato.get("modo") == "espacio_que_cambia"


def estados_del_catalogo(catalogo, sitio=None):
    """{estado: cambio} de los tramos con cambio, en orden de aparicion."""
    salida = {}
    for beat in (catalogo or {}).get("beats") or []:
        if not isinstance(beat, dict) or (sitio and beat.get("set") not in (None, "", sitio)):
            continue
        estado = estado_de(beat)
        if estado and estado not in salida:
            salida[estado] = _texto(beat.get("cambio"), 400)
    return salida


def normalizar_de_estilo(crudo):
    """`estilo.relato` (el defecto del preset). -> {} o {modo, cambia?}.

    Documental es lo mismo que no tenerlo: no se guarda (como `estilo.modo`
    «ilustracion»), para que un preset que lo trae no mueva ninguna firma."""
    if crudo is None or crudo == "" or crudo == {}:
        return {}
    salida = _normalizar_modo_y_cambia(crudo, "relato")
    if salida.get("modo") in (None, "documental"):
        return {}
    return salida


def _tiene_espacio(params):
    espacio = (params or {}).get("espacio_fijo") or {}
    return isinstance(espacio, dict) and bool(" ".join(
        str(espacio.get("descripcion") or "").split()))


def resolver(params):
    """El tipo de relato que rige un video. Nunca lanza.

    -> {modo, cambia, explicito, origen}; `origen` es "video", "estilo",
    "espacio_fijo" o "" (documental por defecto). Ver la cabecera del modulo:
    con `explicito` False todo sale como antes de esta rama."""
    params = params or {}
    try:
        propio = normalizar(params.get("tipo_relato"))
    except ValueError:
        propio = {}
    if propio.get("modo"):
        return {"modo": propio["modo"], "cambia": propio.get("cambia", ""),
                "explicito": True, "origen": "video"}
    try:
        del_estilo = normalizar_de_estilo((params.get("estilo") or {}).get("relato"))
    except ValueError:
        del_estilo = {}
    if del_estilo.get("modo"):
        return {"modo": del_estilo["modo"], "cambia": del_estilo.get("cambia", ""),
                "explicito": True, "origen": "estilo"}
    if _tiene_espacio(params):
        return {"modo": "escenario_y_apoyos", "cambia": "", "explicito": False,
                "origen": "espacio_fijo"}
    return {"modo": "documental", "cambia": "", "explicito": False, "origen": ""}


def activo(relato):
    """¿Corre algo nuevo? Solo con un modo EXPLICITO que no sea documental."""
    return bool(relato and relato.get("explicito")
                and relato.get("modo") not in (None, "", "documental"))


def edita(relato):
    """¿Los planos del sitio se generan editando la base?"""
    return activo(relato) and relato.get("modo") in EDITAN


def bases_aprobadas(params, catalogo=None):
    """{clave: ruta relativa} de las bases APROBADAS del video.

    La clave es el sitio para la base, y «sitio#estado» (`clave_estado`) para la
    imagen de un estado aprobada cuyo cambio sigue siendo el del catalogo: si
    Claude reescribe lo que cambia, esa imagen ya no vale y no entra. Sin
    `catalogo`, solo las bases de los sitios."""
    try:
        propio = normalizar((params or {}).get("tipo_relato"))
    except ValueError:
        return {}
    salida = {}
    for sid, ficha in (propio.get("bases") or {}).items():
        if not ficha.get("aprobada"):
            continue
        salida[sid] = ficha["imagen"]
        # los cambios vigentes DE ESTE SITIO (como la pantalla y la generacion)
        vigentes = estados_del_catalogo(catalogo, sid) if catalogo is not None else {}
        for estado, otra in (ficha.get("estados") or {}).items():
            if otra.get("aprobada") and otra.get("cambio") and \
                    vigentes.get(estado) == otra.get("cambio"):
                salida[clave_estado(sid, estado)] = otra["imagen"]
    return salida


def plano_se_edita(escena, relato, principal, familia=""):
    """¿Este plano se genera EDITANDO la base del sitio? -> bool

    Solo en un modo que edita, solo los planos del sitio principal, y nunca los
    de detalle ni los abstractos (familia «cerca» o «abstracta»), que llevan la
    base como referencia del sitio."""
    if not edita(relato) or not escena or not principal:
        return False
    if escena.get("set") != principal or escena.get("abstracta"):
        return False
    return familia not in FAMILIAS_SIN_EDICION


def nombre(modo, cambia=""):
    """«Un espacio que cambia (los acabados)», para la pantalla y los avisos."""
    texto = MODOS.get(modo, modo or "Documental")
    if modo == "espacio_que_cambia" and cambia in CAMBIA:
        texto += f" ({CAMBIA[cambia].lower()})"
    return texto


# ------------------------------------------------------------ catalogo

#: Lo que se le añade al criterio del catalogo en «un espacio que cambia»: que
#: cada tramo diga QUE CAMBIA respecto a la imagen base. Va detras de la parte
#: de sitios (la del espacio fijo), y los campos nuevos se piden aqui y no en la
#: plantilla JSON de INSTRUCCION, que se queda byte a byte como estaba.
CRITERIO_CAMBIOS = """UN ESPACIO QUE CAMBIA — que cambia en cada tramo
Este video NO reparte el guion en escenas: es UN mismo sitio que se ve siempre
igual (la misma habitacion, la misma distribucion, la misma camara) y en el que
cambia SOLO lo que la voz nombra. Cada plano se va a dibujar EDITANDO una imagen
base del sitio, asi que lo unico que tienes que decir por tramo es que cambia
respecto a esa base. Lo que cambia en este video: {que_cambia}.

  - En cada beat añade dos campos mas:
      "cambio": que cambia respecto a la imagen base en este tramo, EN INGLES, en
        una frase concreta y visual: «the hinged shower door is replaced by a
        sliding glass door», «walls in sage green, oak vanity, brass fittings».
        Vacio ("") si en este tramo el sitio se ve tal cual la base (el «antes»).
        Solo lo que dice la voz: nada que el guion no pida.
      "estado": una etiqueta corta del estado del sitio en ese tramo, en
        minusculas y sin espacios: «antes», «despues», «paleta_1», «obra»,
        «montada», «noche». Dos tramos con el mismo estado tienen el MISMO cambio.
  - La imagen base es el sitio en su estado inicial{antes}: dila en la
    'descripcion' del sitio si la escribes tu.
  - Añade al JSON, al mismo nivel que 'beats', un campo "inicial": EN INGLES,
    COMO ESTA en la imagen base lo que luego cambia, y DONDE exactamente,
    respecto a lo fijo del sitio (que pared, junto a que mueble, hacia donde
    abre, que lado lleva las bisagras): «a closed clear glass hinged shower door,
    0.7 m wide and 1.9 m tall, on the shower's left edge, hinges on the wall side;
    it opens outward, toward the toilet». Es lo que hace que ese objeto salga en
    la base y no se invente distinto en cada plano. Vacio ("") si lo que cambia
    no es una cosa que se ve (la hora, los colores).
    Describe UNA posicion quieta (una puerta, CERRADA salvo que la voz pida otra
    cosa), con su tamaño real y sin movimiento: nada de «swinging», «its arc»,
    «reaching»; por donde abre se dice como dato («it opens outward, toward the
    toilet»). Un modelo de imagen que lee un arco dibuja la hoja torcida, a
    medio abrir y fuera de escala (prueba real del 21-10).
  - La distribucion y "inicial" tienen que hacer VERDAD lo que cuenta la voz, a
    la vista: si la voz dice que la puerta choca con el inodoro, el inodoro esta
    dentro de su barrido (mas cerca de la puerta que el ancho de la hoja); si dice
    que no cabe, que se vea que no cabe. Si escribes tu la 'descripcion' del sitio,
    pon las distancias que lo hacen verdad («the toilet bowl only 0.4 m from the
    glass front»); un baño holgado contradice el video entero.
  - Si un cambio tiene geometria (por donde abre una puerta, una marca en el
    suelo, una medida), dila respecto a lo fijo y coherente con "inicial": «blue
    tape on the floor tracing the quarter circle the hinged door sweeps, from
    its hinge at the shower's left edge out toward the toilet».
  - 'accion' sigue siendo lo que se ve (alguien que abre la puerta, una mano que
    señala), pero sin mover paredes, muebles fijos ni camara.

"""

#: Lo que cambia, dicho para el criterio del catalogo.
QUE_CAMBIA = {
    "objeto": "un OBJETO concreto del sitio (lo demas, igual)",
    "acabados": "los ACABADOS: materiales y colores, con la misma geometria y el "
                "mismo angulo",
    "estado": "el ESTADO del sitio: en obra, montandose, terminado",
    "hora": "la HORA: la luz y la gente que hay",
}

#: Cuando el modo pide un solo sitio y nadie ha escrito el espacio fijo, Claude
#: lo declara. Sustituye a la parte de SETS del criterio igual que el espacio
#: fijo (`catalogo_visual._criterio`), y se impone despues por codigo.
SETS_UN_SITIO = """SETS — donde ocurre: ESTE VIDEO PASA EN UN SOLO SITIO
El editor ha elegido un tipo de relato ({nombre}) que pasa entero en UN sitio,
y eso va por delante de todo lo que se dice en este criterio sobre sitios. Aqui
NO se reparte el guion en sitios: lo que cambia de un tramo a otro es la accion
y el encuadre, no el lugar.

  - Declara en 'sets' UN solo sitio, con un id corto y una 'descripcion' en ingles
    que diga como es de forma que se pueda dibujar igual en todos los planos:
    tamaño, forma, que hay en cada pared, materiales y colores.
  - 'luz': la eliges tu, en ingles, y es la misma en todo el video.
  - 'rotulo': vacio. Este video no lleva cabeceras de sitio.
  - TODOS los tramos van a ese sitio. Sigue habiendo un tramo por idea visual.

"""

#: La «ficha de casa» de un recorrido: varios ambientes que son el mismo lugar.
CRITERIO_RECORRIDO = """UN RECORRIDO — varios ambientes de un mismo lugar
Este video recorre un mismo lugar: aunque cambie el ambiente, la luz, los
materiales y el estilo son los mismos en todos los planos. Escribe la
'descripcion' del sitio pensando en eso: que materiales, que colores y que luz
comparten todos los ambientes.

"""

#: Producto: el fondo no se mueve.
CRITERIO_PRODUCTO = """PRODUCTO — el producto manda y el fondo no se mueve
El protagonista de cada plano es el producto. El sitio es un FONDO constante: la
misma superficie, la misma pared, la misma luz en todos los planos. La 'accion'
de cada tramo dice que se ve del producto (de frente, en uso, un detalle), nunca
un sitio nuevo.

"""


def criterio_extra(relato):
    """El texto que el modo añade al criterio del catalogo, o ""."""
    if not activo(relato):
        return ""
    modo = relato["modo"]
    if modo == "espacio_que_cambia":
        cambia = relato.get("cambia") or "objeto"
        antes = (" (el «antes»: en obra, vacio o sin montar)" if cambia == "estado"
                 else " (el «antes»)" if cambia == "objeto" else "")
        return CRITERIO_CAMBIOS.format(que_cambia=QUE_CAMBIA.get(cambia, QUE_CAMBIA["objeto"]),
                                       antes=antes)
    if modo in ("recorrido", "clase"):
        return CRITERIO_RECORRIDO
    if modo == "producto":
        return CRITERIO_PRODUCTO
    return ""


def _texto(valor, tope):
    return " ".join(str(valor or "").split())[:tope]


def _etiqueta(valor):
    return re.sub(r"[^a-z0-9_]", "", _llano(valor))[:30]


def anotar_cambios(crudos, beats):
    """Pega a cada beat ya limpio su `cambio` y su `estado` de la respuesta cruda.

    `_limpiar` del catalogo solo conserva las claves de siempre (y asi tiene que
    seguir, para que sin modo el catalogo salga igual). Aqui se recuperan los
    dos campos nuevos emparejando por rango de bloques, en orden. Dos tramos con
    el mismo estado comparten el cambio del primero: es lo que hace que «paleta
    2» sea la misma paleta en todos sus planos."""
    libres = [c for c in (crudos or []) if isinstance(c, dict)]
    usados = set()
    por_estado = {}
    for beat in beats or []:
        elegido = None
        for i, crudo in enumerate(libres):
            if i in usados:
                continue
            desde = str(crudo.get("desde") or "").strip().upper()
            hasta = str(crudo.get("hasta") or desde).strip().upper()
            if {desde, hasta} == {beat.get("desde"), beat.get("hasta")}:
                elegido = i
                break
        cambio, estado = "", ""
        if elegido is not None:
            usados.add(elegido)
            cambio = _texto(libres[elegido].get("cambio"), 400)
            estado = _etiqueta(libres[elegido].get("estado"))
        if estado and estado in por_estado:
            cambio = por_estado[estado]
        elif estado and cambio:
            por_estado[estado] = cambio
        beat["cambio"] = cambio
        beat["estado"] = estado or ("antes" if not cambio else "")
    # y los del mismo estado que llegaron vacios ANTES del primero con cambio
    for beat in beats or []:
        if beat.get("estado") in por_estado and not beat.get("cambio"):
            beat["cambio"] = por_estado[beat["estado"]]
    return beats


# ------------------------------------------------------------ imagen

#: La frase que convierte la imagen base en «la imagen que se edita». Va como
#: primera referencia: en /v1/images/edits la primera imagen es la que mas pesa
#: como «esto es lo que se edita». Sin camara nueva: el SHOT TYPE del plano se
#: calla en los planos editados (`p6_assets._prompt_visual`), porque pedir un
#: contrapicado y «la misma camara» a la vez es pedir dos cosas.
FRASE_EDICION = (
    "Reference image {indice} is THE SHOT TO EDIT ('{sitio}'): keep the same "
    "room, the same layout, the same camera position, height, lens and framing, "
    "the same walls, floor, fixed furniture and fittings{acabados}, and the same "
    "proportions. Change ONLY: {cambio}. Everything that is not named there stays "
    "exactly as it is in reference image {indice}.{subtipo}{estilo}")

SUBTIPO = {
    "objeto": " Only that object changes; nothing else moves or is redesigned.",
    "acabados": " Same geometry and the same angle: only materials and colours "
                "change, exactly as described.",
    "estado": " The room shows the stage of work described; the architecture and "
              "the camera stay put.",
    "hora": " Only the light and the people change; the room and the camera stay "
            "put.",
}

#: Lo que se cambia en un plano cuyo tramo no trae cambio (el «antes»).
SIN_CAMBIO = ("nothing in the room itself: only what the scene description below "
              "shows happening in it (people, gestures, small loose objects)")


def frase_edicion(indice, ref, modo_imagen="ilustracion"):
    """La frase del prompt que presenta la imagen base como la que se edita."""
    cambia = ref.get("cambia") or ""
    cambio = _texto(ref.get("cambio"), 400) or SIN_CAMBIO
    if ref.get("modo") == "producto":
        cambio = (_texto(ref.get("cambio"), 400)
                  or "only the product and what the scene description below shows "
                     "of it; the background, surface and light stay exactly the same")
    return FRASE_EDICION.format(
        indice=indice, sitio=ref.get("nombre") or "the set",
        acabados="" if cambia == "acabados" else " and finishes",
        cambio=cambio,
        subtipo=SUBTIPO.get(cambia, "") if ref.get("modo") == "espacio_que_cambia" else "",
        estilo=(" Keep the photographic style of the style references."
                if modo_imagen == "foto" else
                " Keep it drawn in the art style of the style references, never "
                "as a photograph."))


#: El cierre de un plano editado: lo ultimo del prompt, por encima de la linea
#: de direccion, que se escribe con libertad de camara y no sabe de la base.
CIERRE_EDICION = (
    "FINAL CHECK, and it overrides anything above about camera, framing or the room: "
    "this image is an EDIT of reference image {indice}. Keep exactly its camera position, "
    "height, angle, lens and framing, its walls, floor, ceiling, fixed furniture, fittings "
    "and layout{acabados}. Change ONLY: {cambio}. People, gestures and small loose objects "
    "that the scene describes may be added or moved; nothing that belongs to the room itself "
    "moves, appears or disappears.")


def cierre_edicion(indice, ref):
    cambia = ref.get("cambia") or ""
    cambio = _texto(ref.get("cambio"), 400) or SIN_CAMBIO
    return CIERRE_EDICION.format(indice=indice, cambio=cambio,
                                 acabados="" if cambia == "acabados" else " and finishes")


# ------------------------------------------------------------ imagen base

PROMPT_BASE = (
    "{cabecera} The empty set of this film, seen whole, with nobody in it. THE LAYOUT IS "
    "MANDATORY and is the whole point of this image: every wall, fixture and piece of "
    "furniture must be exactly where this description puts it, with the materials and "
    "colours it names, and nothing it does not name: {descripcion}. Before finishing, check "
    "the description item by item against the picture (what is on the left, what is on "
    "the back wall, what is on the right, where the door is). The colours and materials "
    "named here WIN over any palette of the style (its references and its description): "
    "take only the look and the rendering from the style, never its colours or finishes. Light: {luz}. {antes}Frame "
    "it as a clear, level, eye-height view from the entrance that shows the whole layout, "
    "as the reference shot every other shot of this place will be edited from. No people, "
    "no text, no letters.")

ANTES = {
    "objeto": "Show it in its INITIAL state, before anything changes. ",
    "acabados": "Show it with plain, neutral finishes. ",
    "estado": "Show it in its INITIAL state: before the set-up or the works. ",
    "hora": "",
}


#: Lo que luego cambia, dibujado YA en la base (prueba real del 21-10: sin
#: esto la base salia sin mampara y cada plano inventaba la suya en otro sitio).
INICIAL = ("The element that changes later in the film MUST already be in this picture, "
           "in its initial state, exactly like this and exactly there: {inicial}. Draw it as a "
           "real, rigid object at its true size, standing still in that one position: straight "
           "edges, truly vertical, flat and rectangular if it is a panel or a door, never bent, "
           "skewed, faceted or caught half-way through a movement. ")


def inicial_de(valor):
    """El «inicial» que escribe Claude, limpio (o "")."""
    return _texto(valor if isinstance(valor, str) else "", 500)


#: La imagen de un estado: la base, ya cambiada, vacia. Se pinta UNA vez y la
#: aprueba una persona; los planos de ese estado la editan sin cambiar nada.
PROMPT_ESTADO = (
    "The same empty set as reference image 1, with nobody in it, seen from exactly the "
    "same camera, after ONE change: {cambio}. Show the result standing still, as it "
    "would look in a real photograph: anything that moves (a door, a panel) is drawn "
    "rigid, straight, at its true size and fixed in the position the change describes. "
    "No people, no text, no letters.")


def prompt_imagen_estado(cambio):
    return PROMPT_ESTADO.format(cambio=_texto(cambio, 400) or "nothing")


def prompt_imagen_base(espacio, relato, cabecera="", inicial=""):
    """El prompt de la imagen base generada de un sitio (vacio, estado inicial).

    `inicial` (o el de `relato`): como esta y donde lo que luego cambia."""
    descripcion = _texto((espacio or {}).get("descripcion"), 2000) or "the set"
    luz = _texto((espacio or {}).get("luz"), 400) or "soft even daylight"
    antes = ANTES.get((relato or {}).get("cambia") or "", "") \
        if (relato or {}).get("modo") == "espacio_que_cambia" else ""
    inicial = inicial_de(inicial or (relato or {}).get("inicial"))
    if antes and inicial and (relato or {}).get("cambia") in ("objeto", "estado"):
        antes += INICIAL.format(inicial=inicial)
    return PROMPT_BASE.format(cabecera=_texto(cabecera, 400), descripcion=descripcion,
                              luz=luz, antes=antes).strip()

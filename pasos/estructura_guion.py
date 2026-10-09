"""El guion EFECTIVO: el de la version activa con lo escrito a mano encima.

    aplicar(bloques, params_guion)          -> [{"id","texto", "insertado"?}]
    insertar(params, bloques, texto, donde, ancla) -> (cambios, id_nuevo)
    partir(params, bloques, bid, trozos)     -> (cambios, ids_nuevos)
    quitar(params, bid)                      -> cambios

Lo escrito a mano sobre el guion vive en DOS claves de `params.guion`, y las
dos son CORRECCIONES DE SU SALIDA (ver `nucleo.estado.CORRECCIONES`): no dejan
obsoleto al guion -- rehacerlo las borraria -- pero si a todo lo que se hizo
leyendolo.

  bloques     {id: {"texto": ...}}   el texto de cada bloque tocado. Es el cajon
                                     de siempre, y tambien guarda el texto de
                                     los bloques AÑADIDOS: un solo sitio para
                                     el texto, sea de un bloque viejo o nuevo.
  insertados  [{"id", "despues_de"|"antes_de"}]   donde va cada bloque añadido,
                                     anclado a OTRO BLOQUE y no a un numero de
                                     posicion. En el orden en que se hicieron.

Por que anclado y no una lista con el orden entero: un guion se puede volver a
redactar, y el modelo puede devolver otro numero de bloques. Una lista de orden
se quedaria a medias; un ancla sigue diciendo lo mismo mientras el bloque al
que apunta exista, y si desaparece el añadido se va al final -- nunca se
pierde un texto que alguien escribio.

Por que reproducir en orden: «X despues de A» y luego «Z despues de A» tiene
que dejar A, Z, X -- Z se puso justo detras de A cuando se pidio --. Aplicar
las operaciones en el orden en que se hicieron da exactamente lo que se vio en
pantalla al hacer cada una.

LOS IDS NO SE RENOMBRAN. Partir B002 deja la primera parte en B002 y el resto
en bloques NUEVOS con el siguiente numero libre (B031, B032...). Renumerar
moveria la identidad de cada plano, que se reconoce por el bloque del que sale,
y las ediciones guardadas por id caerian en el bloque de al lado. Los nuevos
tienen la misma forma (B + tres cifras) porque `p3_guion` renumera el guion
entero si le llega un id con otra forma.

Un proyecto de antes no trae `insertados` y abre igual: sin la clave, esto es
exactamente `p4_voz.ediciones_a_mano` de siempre.
"""
import re

CLAVE_TEXTOS = "bloques"
CLAVE_INSERTADOS = "insertados"
DONDES = ("antes", "despues", "principio", "final")
_ID = re.compile(r"B(\d{1,4})")


def _limpio(texto):
    return " ".join(str(texto or "").split())


def textos_de(params):
    """El cajon de textos escritos a mano, normalizado: {ID: texto}."""
    crudos = (params or {}).get(CLAVE_TEXTOS) or {}
    salida = {}
    if isinstance(crudos, dict):
        for clave, valor in crudos.items():
            texto = valor.get("texto") if isinstance(valor, dict) else valor
            texto = _limpio(texto)
            if texto:
                salida[str(clave).strip().upper()] = texto
    return salida


def insertados_de(params):
    """La lista de bloques añadidos, saneada. Lo que no se entiende se ignora."""
    crudos = (params or {}).get(CLAVE_INSERTADOS) or []
    salida, vistos = [], set()
    if not isinstance(crudos, list):
        return salida
    for ficha in crudos:
        if not isinstance(ficha, dict):
            continue
        bid = str(ficha.get("id") or "").strip().upper()
        if not bid or bid in vistos:
            continue
        limpia = {"id": bid}
        for clave in ("despues_de", "antes_de"):
            ancla = ficha.get(clave)
            if ancla is not None:
                limpia[clave] = str(ancla).strip().upper()
                break
        vistos.add(bid)
        salida.append(limpia)
    return salida


def aplicar(bloques, params):
    """Los bloques con los añadidos en su sitio y los textos escritos encima.

    IDEMPOTENTE: un añadido que ya esta en `bloques` (porque `p3_guion` lo dejo
    dentro al volver a redactar) no se repite. Y un añadido sin texto no se
    pone: es uno que se vacio, y un bloque vacio no se locuta.
    """
    textos = textos_de(params)
    lista = [dict(b) for b in (bloques or [])]
    presentes = {str(b.get("id") or "").upper() for b in lista}
    for ficha in insertados_de(params):
        bid = ficha["id"]
        if bid in presentes or not textos.get(bid):
            continue
        nuevo = {"id": bid, "texto": textos[bid], "insertado": True}
        ancla = ficha.get("despues_de") or ficha.get("antes_de")
        posiciones = [i for i, b in enumerate(lista)
                      if str(b.get("id") or "").upper() == ancla]
        if ficha.get("antes_de") is not None and posiciones:
            lista.insert(posiciones[0], nuevo)
        elif posiciones:
            lista.insert(posiciones[0] + 1, nuevo)
        else:
            # el ancla ya no existe (el guion se volvio a redactar): al final,
            # que es peor sitio pero nunca perder lo escrito
            lista.append(nuevo)
        presentes.add(bid)
    for bloque in lista:
        texto = textos.get(str(bloque.get("id") or "").upper())
        if texto:
            bloque["texto"] = texto
    return lista


def siguiente_id(*grupos):
    """El primer id libre DESPUES de todos los que se conocen."""
    mayor = 0
    for grupo in grupos:
        for bid in grupo or ():
            encaje = _ID.fullmatch(str(bid or "").strip().upper())
            if encaje:
                mayor = max(mayor, int(encaje.group(1)))
    return f"B{mayor + 1:03d}"


def _conocidos(params, bloques, otros=()):
    """Todos los ids que ya significan algo. `otros` son los de la toma
    grabada: un añadido que se quito despues de grabarlo sigue sonando hasta
    que se regraba su tramo, y su numero no se puede dar a otro bloque."""
    return ([b.get("id") for b in bloques or []],
            list(textos_de(params)),
            [f["id"] for f in insertados_de(params)],
            list(otros or ()))


def _cajon(params):
    """Copia del cajon de textos TAL CUAL se guarda ({id: {"texto"}})."""
    crudos = (params or {}).get(CLAVE_TEXTOS) or {}
    return {str(k).strip().upper(): (dict(v) if isinstance(v, dict) else {"texto": v})
            for k, v in (crudos.items() if isinstance(crudos, dict) else [])}


def insertar(params, bloques, texto, donde, ancla=None, otros=()):
    """Un bloque nuevo con su texto, en el sitio pedido. -> (cambios, id)

    `bloques` es el guion efectivo de ahora (con lo ya añadido): es contra lo
    que se ve en pantalla contra lo que se elige el sitio.
    """
    texto = _limpio(texto)
    if not texto:
        raise ValueError("el bloque nuevo necesita texto")
    donde = str(donde or "").strip().lower()
    if donde not in DONDES:
        raise ValueError(f"'donde' tiene que ser uno de: {', '.join(DONDES)}")
    ids = [str(b.get("id") or "").upper() for b in bloques or []]
    if not ids:
        raise ValueError("todavia no hay guion al que añadirle un bloque")
    if donde in ("antes", "despues"):
        ancla = str(ancla or "").strip().upper()
        if ancla not in ids:
            raise ValueError(f"no hay ningun bloque {ancla or '(vacio)'} en el guion")
        posicion = {"antes_de" if donde == "antes" else "despues_de": ancla}
    elif donde == "principio":
        posicion = {"antes_de": ids[0]}
    else:
        posicion = {"despues_de": ids[-1]}
    nuevo = siguiente_id(*_conocidos(params, bloques, otros))
    insertados = insertados_de(params) + [dict(posicion, id=nuevo)]
    cajon = _cajon(params)
    cajon[nuevo] = {"texto": texto}
    return {CLAVE_INSERTADOS: insertados, CLAVE_TEXTOS: cajon}, nuevo


def partir(params, bloques, bid, trozos, otros=()):
    """Parte un bloque en dos o mas. -> (cambios, [ids nuevos])

    La primera parte se queda en el bloque de siempre (una edicion mas de su
    texto) y cada una de las demas es un bloque añadido detras de la anterior.
    Las partes vacias se descartan: cortar dos veces en el mismo sitio no crea
    un bloque en blanco.
    """
    bid = str(bid or "").strip().upper()
    ids = [str(b.get("id") or "").upper() for b in bloques or []]
    if bid not in ids:
        raise ValueError(f"no hay ningun bloque {bid or '(vacio)'} en el guion")
    partes = [_limpio(t) for t in (trozos or []) if _limpio(t)]
    if len(partes) < 2:
        raise ValueError("para partir un bloque hacen falta al menos dos trozos con texto")
    cajon = _cajon(params)
    insertados = insertados_de(params)
    conocidos = list(_conocidos(params, bloques, otros))
    cajon[bid] = {"texto": partes[0]}
    anterior, nuevos = bid, []
    for parte in partes[1:]:
        nuevo = siguiente_id(*conocidos, nuevos)
        insertados.append({"id": nuevo, "despues_de": anterior})
        cajon[nuevo] = {"texto": parte}
        nuevos.append(nuevo)
        anterior = nuevo
    return {CLAVE_INSERTADOS: insertados, CLAVE_TEXTOS: cajon}, nuevos


def quitar(params, bid):
    """Quita un bloque AÑADIDO. Los del guion original no se quitan desde aqui.

    Los añadidos que estaban anclados a el pasan a su ancla: quitar X de
    «A, X, Y» deja «A, Y», no manda Y al final del guion.
    """
    bid = str(bid or "").strip().upper()
    insertados = insertados_de(params)
    ficha = next((f for f in insertados if f["id"] == bid), None)
    if ficha is None:
        raise ValueError(f"{bid or '(vacio)'} no es un bloque añadido: solo esos se pueden quitar")
    # Los que colgaban de el heredan su ancla Y SU TURNO: se reproducen en el
    # sitio de la lista donde estaba el quitado. Con el turno propio, un «Z
    # despues de A» hecho entre medias quedaria detras de ellos al reproducir,
    # y el orden de pantalla cambiaria solo por quitar otro bloque.
    herederos, resto, sitio = [], [], None
    for otra in insertados:
        if otra["id"] == bid:
            sitio = len(resto)
            continue
        if bid in (otra.get("despues_de"), otra.get("antes_de")):
            nueva = {"id": otra["id"]}
            nueva.update({k: v for k, v in ficha.items() if k != "id"})
            herederos.append(nueva)
            continue
        resto.append(otra)
    resto[sitio:sitio] = herederos
    cajon = _cajon(params)
    cajon.pop(bid, None)
    return {CLAVE_INSERTADOS: resto, CLAVE_TEXTOS: cajon}

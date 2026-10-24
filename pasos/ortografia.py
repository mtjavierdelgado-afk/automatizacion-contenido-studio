"""El corrector de ORTOGRAFIA de lo que acaba escrito en pantalla o publicado:
el guion (antes de grabar la voz), los subtitulos (de un video ya hecho) y
cualquier campo de texto que se vea o se publique (`fuente: "textos"`: las
llamadas a la accion, la ficha de la Parrilla y, cuando se una `publicar-mas`,
los textos de cada red).

    revisar({id: texto}, cwd=None, informe=None) -> {id: {"texto": corregido, "cambios": [[mal, bien], ...]}}

Solo vuelven los textos que cambian. Corrige ORTOGRAFIA y nada mas: tildes,
letras cambiadas, mayusculas al empezar una frase, los signos de apertura ¿ ¡
y la puntuacion claramente rota. NO reescribe, no cambia palabras por otras ni
el estilo: lo que sale en un subtitulo tiene que ser lo que se OYE.

Por que dos sitios y no uno
---------------------------
- EL GUION se corrige antes de grabar la voz: ahi es gratis, y de ahi salen la
  voz y los subtitulos. Despues de grabada, tocar el guion es regrabar (y las
  imagenes de los planos cuyo texto cambie), asi que en un video ya grabado se
  corrige donde es barato:
- LOS SUBTITULOS se corrigen con el texto escrito a mano de cada plano
  (`callouts.unidades["escena:S00x"].subtitulo_texto`, el mismo cajon que usa
  el repaso). Deja obsoleto SOLO el rotulo de ese plano: volver a montar no
  dibuja imagenes ni graba voz, no cuesta dinero.

LA MEMORIA (`revisar_con_memoria`, 18-10-2026): lo revisado se apunta en
`<proyecto>/ortografia.json` por la huella de cada texto, fuera de toda firma.
Un texto que ya se reviso no vuelve al CLI: la pantalla del guion puede
revisar SOLA cada vez que cambia el guion y solo se pregunta por los bloques
que cambiaron. Lo que la persona deja sin marcar al aplicar se apunta como
bueno (`descartar`) y no se vuelve a proponer.

LA REVISION EDITORIAL (`revisar_editorial`, 19-10-2026) es un modo APARTE, al
final del fichero: sintaxis y redaccion, con propuestas sueltas. No toca nada
de lo de aqui arriba.

Va por SUSCRIPCION (el CLI de Claude), con sonnet y poco esfuerzo, igual que
«Revisar». Si el modelo devuelve algo que no es una correccion ortografica
--otra frase, palabras de mas o de menos-- se descarta (`_es_ortografia`).
"""
import hashlib
import json
import os
import re
import threading
import unicodedata

try:
    from . import cli_claude, comun
except ImportError:                                   # corriendo desde pasos/
    import cli_claude
    import comun

MODELO = "sonnet"
ESFUERZO = "low"
#: Cuantos textos van en cada llamada: un video largo son cientos de planos y
#: una sola llamada con todos tarda y se corta. Eran 60; con 60 un JSON roto
#: (una comilla sin escapar, una coma de mas) se llevaba por delante la
#: revision de 60 textos, y cuanto mas larga la respuesta mas facil que salga
#: rota. Con 20 se reintenta poco y se pierde poco (N6 de las notas de
#: mejoras, 13-10-2026).
POR_LLAMADA = 20
#: Una tanda cuyo JSON no se puede leer se vuelve a pedir UNA vez: el modelo
#: contesta distinto cada vez, y lo normal es que la segunda salga bien.
REINTENTOS_JSON = 1

#: Lo que lee la persona cuando NINGUNA tanda da un JSON legible. El detalle
#: tecnico va aparte, despues de una linea en blanco: la pantalla
#: (`partirError` en web/app.js) ensena el primer parrafo como titular y pliega
#: el resto. Antes el titular era «la revision de ortografia no es un JSON
#: legible: Expecting ',' delimiter…», tal cual.
RESPUESTA_ROTA = ("El corrector devolvió una respuesta rota; pulsa «Revisar otra vez». "
                  "No se ha cambiado nada.")
MAX_TEXTO = 2000

SISTEMA = ("Eres corrector ortografico de castellano. Corriges SOLO ortografia y "
           "contestas unicamente con el JSON pedido.")

INSTRUCCION = """Corrige la ORTOGRAFIA de estos textos en castellano. Son los
subtitulos (o el guion) de un video narrado: lo que se lee tiene que ser
EXACTAMENTE lo que se oye, asi que:

- Corrige: tildes que faltan o sobran, letras equivocadas, mayuscula al empezar
  una frase, signos de apertura ¿ y ¡ que faltan, comas o puntos claramente
  rotos, espacios dobles y letras raras de codificacion («TÃº» -> «Tú»).
- NO cambies palabras por otras, NO reordenes, NO quites ni anadas palabras,
  NO cambies el estilo, el registro ni las cifras. Los nombres propios y las
  marcas se quedan como estan.
- «guion» y «solo» sin tilde son correctos.
- Algunos textos son para publicar en redes: los #hashtags, las @menciones,
  los enlaces, los emojis y los saltos de linea se quedan tal cual.

<textos>
{textos}
</textos>

Devuelve SOLO este JSON, con UNICAMENTE los textos que cambian (si ninguno
cambia, {{"correcciones": {{}}}}):
{{"correcciones": {{"<id>": {{"texto": "<el texto entero corregido>",
                            "cambios": [["<mal>", "<bien>"]]}}}}}}"""


class ErrorOrtografia(RuntimeError):
    """No se ha podido revisar, con el motivo en castellano."""


def _llano(texto):
    """Sin tildes, sin signos y en minusculas: para comparar que las palabras
    son LAS MISMAS aunque cambie la ortografia."""
    sin = unicodedata.normalize("NFD", str(texto or ""))
    sin = "".join(c for c in sin if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9]+", sin.lower())


def _es_ortografia(antes, despues):
    """Si `despues` es `antes` con la ortografia corregida y nada mas: las
    mismas palabras en el mismo orden (comparadas sin tildes ni signos), con
    margen para una letra cambiada aqui y alla. Lo que reescribe se descarta."""
    a, d = _llano(antes), _llano(despues)
    if not d or abs(len(a) - len(d)) > max(1, len(a) // 20):
        return False
    distintas = sum(1 for x, y in zip(a, d) if x != y)
    return distintas <= max(1, len(a) // 8)


def _lote(textos):
    return "\n".join(f"<t id=\"{i}\">{' '.join(str(t).split())[:MAX_TEXTO]}</t>"
                     for i, t in textos)


class _JsonRoto(RuntimeError):
    """Una tanda cuya respuesta no se ha podido leer ni a la segunda."""


def _cierra_cadena(texto, i):
    """Si la comilla de `texto[i]` (dentro de una cadena) es la que la cierra:
    detras viene `:`, `}` o `]`, o una coma seguida de otra cosa del JSON."""
    j = i + 1
    while j < len(texto) and texto[j] in " \t\r\n":
        j += 1
    if j >= len(texto) or texto[j] in ":}]":
        return True
    if texto[j] != ",":
        return False
    j += 1
    while j < len(texto) and texto[j] in " \t\r\n":
        j += 1
    return j >= len(texto) or texto[j] in '"{[-0123456789tfn'


def reparar_comillas(texto):
    """El JSON con las comillas de DENTRO de un texto escapadas.

    LA RESPUESTA ROTA DEL CORRECTOR (notas del dueño, 24-10-2026). El corrector
    devuelve el texto entero corregido, y si el guion lleva comillas rectas
    («comenta "BAÑO"») el modelo las copia sin escapar y el JSON no se puede
    leer, ni a la segunda: la misma frase rompe los dos intentos. Una comilla
    dentro de una cadena que no va seguida de lo que puede venir detras de una
    cadena (`:`, `}`, `]` o una coma y otro valor) es del texto, y se escapa."""
    texto = str(texto or "")
    salida, dentro, i = [], False, 0
    while i < len(texto):
        c = texto[i]
        if dentro and c == "\\":
            salida.append(texto[i:i + 2])
            i += 2
            continue
        if c == '"':
            if not dentro:
                dentro = True
            elif _cierra_cadena(texto, i):
                dentro = False
            else:
                salida.append('\\"')
                i += 1
                continue
        elif dentro and c in "\n\r":
            salida.append("\\n" if c == "\n" else "")
            i += 1
            continue
        salida.append(c)
        i += 1
    return "".join(salida)


def leer_json(respuesta, que):
    """`comun.extraer_json`, y si no se puede leer, otra vez con las comillas
    del texto escapadas (`reparar_comillas`). Si tampoco, el error de antes."""
    try:
        return comun.extraer_json(respuesta, que)
    except RuntimeError as fallo:
        try:
            return comun.extraer_json(reparar_comillas(respuesta), que)
        except RuntimeError:
            raise fallo from None


def _pedir_tanda(trozo, cwd):
    """Las correcciones de una tanda, leidas del JSON del modelo. Si el JSON no
    se puede leer se pide otra vez (`REINTENTOS_JSON`); si sigue roto, lanza
    `_JsonRoto` con el detalle tecnico. Los fallos del CLI (sin cupo, sin
    sesion, plazo vencido) NO se reintentan aqui: no los arregla preguntar otra
    vez, y suben como siempre."""
    instruccion = INSTRUCCION.format(textos=_lote(trozo))
    ultimo = ""
    for _intento in range(1 + REINTENTOS_JSON):
        respuesta, _sobre = cli_claude.ejecutar(
            instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
            base_tiempo_s=180, sistema=SISTEMA,
            extra=["--no-session-persistence"], para="la revision de ortografia")
        try:
            datos = leer_json(respuesta, "la revision de ortografia")
        except RuntimeError as fallo:
            ultimo = str(fallo)
            continue
        return (datos or {}).get("correcciones") if isinstance(datos, dict) else None
    raise _JsonRoto(ultimo)


def revisar(textos, cwd=None, informe=None):
    """{id: texto} -> {id: {"texto", "cambios"}} solo de los que cambian.

    POR TANDAS, Y UNA TANDA ROTA NO SE LLEVA LAS DEMAS (N6 de las notas de
    mejoras, 13-10-2026): antes un JSON roto en cualquier tanda lanzaba y se
    perdia la revision ENTERA, tambien lo ya revisado. Ahora una tanda que no
    se puede leer ni a la segunda se salta, y lo que salio bien vuelve. Si se
    pasa un dict en `informe`, ahi se apunta `sin_revisar` (cuantos textos se
    quedaron sin revisar) y `detalle` (el error tecnico de la ultima tanda
    rota), para que la pantalla lo diga. Si no sale NINGUNA tanda, lanza
    `ErrorOrtografia` con `RESPUESTA_ROTA` de titular."""
    if not isinstance(textos, dict):
        raise ErrorOrtografia("hacen falta los textos a revisar")
    pares = [(str(k), str(v)) for k, v in textos.items() if str(v or "").strip()]
    if informe is not None:
        informe.update({"sin_revisar": 0, "detalle": ""})
    if not pares:
        return {}
    salida = {}
    sin_revisar, tandas_bien, detalle = 0, 0, ""
    ids_sin_revisar = []
    for desde in range(0, len(pares), POR_LLAMADA):
        trozo = pares[desde:desde + POR_LLAMADA]
        try:
            correcciones = _pedir_tanda(trozo, cwd)
        except _JsonRoto as fallo:
            sin_revisar += len(trozo)
            ids_sin_revisar.extend(k for k, _t in trozo)
            detalle = str(fallo)
            continue
        tandas_bien += 1
        originales = dict(trozo)
        for cid, ficha in (correcciones or {}).items():
            cid = str(cid)
            if cid not in originales or not isinstance(ficha, dict):
                continue
            nuevo = " ".join(str(ficha.get("texto") or "").split())
            viejo = " ".join(originales[cid].split())
            if not nuevo or nuevo == viejo or not _es_ortografia(viejo, nuevo):
                continue
            cambios = [[str(a)[:80], str(b)[:80]] for a, b in
                       (c for c in (ficha.get("cambios") or []) if isinstance(c, (list, tuple)) and len(c) == 2)]
            salida[cid] = {"texto": nuevo, "cambios": cambios[:20]}
    if not tandas_bien:
        raise ErrorOrtografia(f"{RESPUESTA_ROTA}\n\n{detalle}")
    if informe is not None:
        informe.update({"sin_revisar": sin_revisar, "detalle": detalle,
                        "ids_sin_revisar": ids_sin_revisar})
    return salida


# ------------------------------------------------------------------ la memoria

FICHERO_MEMORIA = "ortografia.json"
#: Cambia cuando cambia lo que se le pide al corrector: lo apuntado con otra
#: instruccion no vale (vuelve a revisarse).
VERSION_MEMORIA = 2
#: Cuantos textos se recuerdan por proyecto. Un video largo son ~300 planos y
#: ~60 bloques; con cada edicion entra uno nuevo. Se quitan los mas viejos.
MAX_MEMORIA = 4000

_LOCK_MEMORIA = threading.Lock()


def huella(texto):
    """La clave de un texto en la memoria: el texto con los espacios juntados."""
    llano = " ".join(str(texto or "").split())
    return hashlib.sha1(f"{VERSION_MEMORIA}|{llano}".encode("utf-8")).hexdigest()[:20]


def _ruta_memoria(carpeta):
    return os.path.join(carpeta, FICHERO_MEMORIA)


def leer_memoria(carpeta):
    """{huella: {"texto": corregido o "", "cambios": [...]}}. Nunca lanza: una
    memoria ilegible es una memoria vacia (se vuelve a revisar, nada mas)."""
    if not carpeta:
        return {}
    try:
        with open(_ruta_memoria(carpeta), encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return {}
    textos = datos.get("textos") if isinstance(datos, dict) else None
    return textos if isinstance(textos, dict) else {}


def apuntar(carpeta, nuevas):
    """Suma `nuevas` ({huella: ficha}) a la memoria, de forma atomica."""
    if not carpeta or not nuevas:
        return
    with _LOCK_MEMORIA:
        memoria = leer_memoria(carpeta)
        for clave in nuevas:
            memoria.pop(clave, None)              # lo nuevo, al final (lo ultimo en irse)
        memoria.update(nuevas)
        if len(memoria) > MAX_MEMORIA:
            memoria = dict(list(memoria.items())[-MAX_MEMORIA:])
        ruta = _ruta_memoria(carpeta)
        temporal = f"{ruta}.{os.getpid()}.{threading.get_ident()}.tmp"
        try:
            os.makedirs(carpeta, exist_ok=True)
            with open(temporal, "w", encoding="utf-8") as fh:
                json.dump({"version": VERSION_MEMORIA, "textos": memoria}, fh, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temporal, ruta)
        except OSError:
            try:
                os.remove(temporal)
            except OSError:
                pass


def descartar(carpeta, textos):
    """Apunta como BUENOS estos textos (lo que la persona dejo sin marcar al
    aplicar): no se vuelven a proponer mientras no cambien."""
    apuntar(carpeta, {huella(t): {"texto": "", "cambios": []}
                      for t in textos if str(t or "").strip()})


def revisar_con_memoria(textos, carpeta, cwd=None, informe=None):
    """Como `revisar`, pero lo ya revisado sale de la memoria y solo va al CLI
    lo nuevo. Lo que se reviso bien se apunta (tambien lo que no tenia faltas);
    lo que se quedo sin revisar (una tanda rota) no. En `informe` va ademas
    `de_memoria`: cuantos textos no han hecho falta preguntar."""
    if not isinstance(textos, dict):
        raise ErrorOrtografia("hacen falta los textos a revisar")
    pares = {str(k): str(v) for k, v in textos.items() if str(v or "").strip()}
    memoria = leer_memoria(carpeta)
    salida, nuevos = {}, {}
    # UN TEXTO MAS LARGO QUE `MAX_TEXTO` NO SE MANDA: `_lote` lo cortaria y la
    # correccion volveria sin su final (y aplicarla lo borraria). Se cuenta como
    # sin revisar y no se recuerda.
    largos = [cid for cid, t in pares.items() if len(" ".join(t.split())) > MAX_TEXTO]
    for cid in largos:
        pares.pop(cid)
    for cid, texto in pares.items():
        ficha = memoria.get(huella(texto))
        if not isinstance(ficha, dict):
            nuevos[cid] = texto
        elif ficha.get("texto"):
            salida[cid] = {"texto": ficha["texto"], "cambios": ficha.get("cambios") or []}
    propio = {}
    if nuevos:
        corregidos = revisar(nuevos, cwd=cwd, informe=propio)
        rotos = set(propio.get("ids_sin_revisar") or ())
        apuntar(carpeta, {huella(t): (corregidos.get(cid) or {"texto": "", "cambios": []})
                          for cid, t in nuevos.items() if cid not in rotos})
        salida.update(corregidos)
    if informe is not None:
        detalle = str(propio.get("detalle") or "")
        if largos:
            detalle = (f"{len(largos)} texto(s) de más de {MAX_TEXTO} caracteres no se revisan: "
                       f"pártelos ({', '.join(largos[:5])}). {detalle}").strip()
        informe.update({"sin_revisar": int(propio.get("sin_revisar") or 0) + len(largos),
                        "detalle": detalle,
                        "de_memoria": len(pares) - len(nuevos)})
    return salida


def como_json(resultado):
    return json.dumps(resultado, ensure_ascii=False)


# ------------------------------------------------------ la revision EDITORIAL
#
# Arreglos del 19-10 (5), pedido del dueño: «una revision de sintaxis y
# redaccion del guion, como la haria un corrector editorial». Es un modo
# APARTE: la ortografia de arriba no cambia (corrige solo letras y signos, y
# su filtro `_es_ortografia` tira todo lo que cambie palabras). Aqui se
# proponen cambios de redaccion --sintaxis, concordancia, puntuacion,
# repeticiones, frases confusas o largas para decirlas en voz alta, registro--
# como PROPUESTAS sueltas {original, propuesta, motivo}: un trozo literal del
# texto y su sustitucion, para aceptarlas o rechazarlas una a una.
#
# No hay memoria: cada revision pregunta (lo editorial no es «correcto o no»,
# y lo rechazado una vez puede tener sentido despues de otros cambios).
#
# MODELO: sonnet con esfuerzo medio. Pide criterio (mas que la ortografia,
# que va con poco esfuerzo) y se espera mirando la pantalla; opus tardaria el
# doble por tanda para un guion que se lee en segundos.

MODELO_EDITORIAL = "sonnet"
ESFUERZO_EDITORIAL = "medium"
#: Textos por llamada: cada uno vuelve con varias propuestas y su motivo, asi
#: que la respuesta es mas larga que la de la ortografia.
POR_LLAMADA_EDITORIAL = 8
#: Propuestas por texto como mucho: un bloque con veinte no se revisa, se
#: reescribe, y eso es otra cosa (regenerar el guion).
MAX_PROPUESTAS_POR_TEXTO = 6
MAX_FRAGMENTO = 400
TIPOS_EDITORIALES = ("sintaxis", "concordancia", "puntuacion", "repeticion",
                     "claridad", "registro")

SISTEMA_EDITORIAL = ("Eres corrector editorial experto en castellano. Propones "
                     "cambios minimos de redaccion y contestas unicamente con el "
                     "JSON pedido.")

INSTRUCCION_EDITORIAL = """Haz una REVISION EDITORIAL de estos bloques de un
guion narrado en castellano (se graban con una voz y se oyen, no se leen).
Revisa como un corrector editorial profesional:

- sintaxis: frases mal construidas, subordinadas que no cierran, orden confuso;
- concordancia: genero, numero, tiempos verbales que saltan sin motivo;
- puntuacion: comas que separan sujeto y verbo, que faltan en un inciso,
  puntos que hacen falta en una frase demasiado larga para decirla de un tiron;
- repeticiones: la misma palabra o idea muy cerca;
- claridad: frases ambiguas o que obligan a releer;
- registro: un salto de tono (coloquial en medio de algo formal, o al reves).

Reglas:
- CAMBIOS MINIMOS: no reescribas el bloque ni cambies el estilo del autor. Si
  algo esta bien, no lo toques. Lo normal es que muchos bloques no tengan nada.
- NO cambies hechos, cifras, nombres propios, marcas ni el sentido.
- La ortografia (tildes, letras) NO es tu trabajo: hay otro corrector.
- «original» es un trozo COPIADO LITERALMENTE del bloque (letra a letra, con sus
  signos), lo mas corto posible pero que se encuentre una sola vez; «propuesta»
  es por lo que se cambia; «motivo», una frase corta para el autor.
- Como mucho {maximo} propuestas por bloque.

<textos>
{textos}
</textos>

Devuelve SOLO este JSON, con UNICAMENTE los bloques que tienen propuestas (si
ninguno, {{"propuestas": {{}}}}):
{{"propuestas": {{"<id>": [{{"original": "<trozo literal>", "propuesta": "<como queda>",
                           "motivo": "<por que>", "tipo": "<{tipos}>"}}]}}}}"""


def _llano_espacios(texto):
    return " ".join(str(texto or "").split())


def _pedir_tanda_editorial(trozo, cwd):
    instruccion = INSTRUCCION_EDITORIAL.format(
        textos=_lote(trozo), maximo=MAX_PROPUESTAS_POR_TEXTO,
        tipos="|".join(TIPOS_EDITORIALES))
    ultimo = ""
    for _intento in range(1 + REINTENTOS_JSON):
        respuesta, _sobre = cli_claude.ejecutar(
            instruccion, modelo=MODELO_EDITORIAL, esfuerzo=ESFUERZO_EDITORIAL, cwd=cwd,
            base_tiempo_s=240, sistema=SISTEMA_EDITORIAL,
            extra=["--no-session-persistence"], para="la revision editorial")
        try:
            datos = leer_json(respuesta, "la revision editorial")
        except RuntimeError as fallo:
            ultimo = str(fallo)
            continue
        return (datos or {}).get("propuestas") if isinstance(datos, dict) else None
    raise _JsonRoto(ultimo)


def _propuestas_validas(texto, crudas):
    """Las propuestas de un bloque que se pueden aplicar tal cual: su
    `original` esta UNA vez en el texto, la propuesta es distinta y no
    vacia, y no se pisan entre ellas. Lo demas se descarta en silencio (un
    trozo que no esta no se podria poner)."""
    texto = _llano_espacios(texto)
    salida, ocupado = [], []
    for cruda in crudas if isinstance(crudas, list) else []:
        if not isinstance(cruda, dict):
            continue
        original = _llano_espacios(cruda.get("original"))
        propuesta = _llano_espacios(cruda.get("propuesta"))
        if (not original or not propuesta or original == propuesta
                or len(original) > MAX_FRAGMENTO or len(propuesta) > MAX_FRAGMENTO * 2
                or texto.count(original) != 1):
            continue
        desde = texto.index(original)
        tramo = (desde, desde + len(original))
        if any(a < tramo[1] and tramo[0] < b for a, b in ocupado):
            continue
        ocupado.append(tramo)
        tipo = str(cruda.get("tipo") or "").strip().lower()
        salida.append({"original": original, "propuesta": propuesta,
                       "motivo": _llano_espacios(cruda.get("motivo"))[:240],
                       "tipo": tipo if tipo in TIPOS_EDITORIALES else ""})
        if len(salida) >= MAX_PROPUESTAS_POR_TEXTO:
            break
    return salida


def revisar_editorial(textos, cwd=None, informe=None):
    """{id: texto} -> {id: [{original, propuesta, motivo, tipo}]}, solo de los
    bloques con propuestas. Por tandas, y una tanda rota no se lleva las demas
    (como `revisar`): en `informe` van `sin_revisar`, `ids_sin_revisar` y
    `detalle`. Si no sale NINGUNA tanda, `ErrorOrtografia`."""
    if not isinstance(textos, dict):
        raise ErrorOrtografia("hacen falta los textos a revisar")
    pares = [(str(k), str(v)) for k, v in textos.items() if str(v or "").strip()]
    largos = [k for k, t in pares if len(_llano_espacios(t)) > MAX_TEXTO]
    pares = [(k, t) for k, t in pares if k not in largos]
    if informe is not None:
        informe.update({"sin_revisar": len(largos), "detalle": "", "ids_sin_revisar": list(largos)})
    if not pares:
        return {}
    salida, tandas_bien, detalle, sin_revisar = {}, 0, "", []
    for desde in range(0, len(pares), POR_LLAMADA_EDITORIAL):
        trozo = pares[desde:desde + POR_LLAMADA_EDITORIAL]
        try:
            propuestas = _pedir_tanda_editorial(trozo, cwd)
        except _JsonRoto as fallo:
            sin_revisar.extend(k for k, _t in trozo)
            detalle = str(fallo)
            continue
        tandas_bien += 1
        originales = dict(trozo)
        for cid, lista in (propuestas or {}).items():
            cid = str(cid)
            if cid not in originales:
                continue
            validas = _propuestas_validas(originales[cid], lista)
            if validas:
                salida[cid] = validas
    if not tandas_bien:
        raise ErrorOrtografia(f"{RESPUESTA_ROTA}\n\n{detalle}")
    if informe is not None:
        if largos:
            detalle = (f"{len(largos)} bloque(s) de más de {MAX_TEXTO} caracteres no se revisan: "
                       f"pártelos ({', '.join(largos[:5])}). {detalle}").strip()
        informe.update({"sin_revisar": len(sin_revisar) + len(largos), "detalle": detalle,
                        "ids_sin_revisar": sin_revisar + largos})
    return salida

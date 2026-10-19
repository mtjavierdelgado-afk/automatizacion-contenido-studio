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
            datos = comun.extraer_json(respuesta, "la revision de ortografia")
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

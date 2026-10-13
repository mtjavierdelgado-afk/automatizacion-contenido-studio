"""El corrector de ORTOGRAFIA de lo que acaba escrito en pantalla: el guion
(antes de grabar la voz) y los subtitulos (de un video ya hecho).

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

Va por SUSCRIPCION (el CLI de Claude), con sonnet y poco esfuerzo, igual que
«Revisar». Si el modelo devuelve algo que no es una correccion ortografica
--otra frase, palabras de mas o de menos-- se descarta (`_es_ortografia`).
"""
import json
import re
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
    for desde in range(0, len(pares), POR_LLAMADA):
        trozo = pares[desde:desde + POR_LLAMADA]
        try:
            correcciones = _pedir_tanda(trozo, cwd)
        except _JsonRoto as fallo:
            sin_revisar += len(trozo)
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
        informe.update({"sin_revisar": sin_revisar, "detalle": detalle})
    return salida


def como_json(resultado):
    return json.dumps(resultado, ensure_ascii=False)

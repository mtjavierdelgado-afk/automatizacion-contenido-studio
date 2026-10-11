"""El corrector de ORTOGRAFIA de lo que acaba escrito en pantalla: el guion
(antes de grabar la voz) y los subtitulos (de un video ya hecho).

    revisar({id: texto}, cwd=None) -> {id: {"texto": corregido, "cambios": [[mal, bien], ...]}}

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
#: una sola llamada con todos tarda y se corta.
POR_LLAMADA = 60
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


def revisar(textos, cwd=None):
    """{id: texto} -> {id: {"texto", "cambios"}} solo de los que cambian."""
    if not isinstance(textos, dict):
        raise ErrorOrtografia("hacen falta los textos a revisar")
    pares = [(str(k), str(v)) for k, v in textos.items() if str(v or "").strip()]
    if not pares:
        return {}
    salida = {}
    for desde in range(0, len(pares), POR_LLAMADA):
        trozo = pares[desde:desde + POR_LLAMADA]
        instruccion = INSTRUCCION.format(textos=_lote(trozo))
        respuesta, _sobre = cli_claude.ejecutar(
            instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
            base_tiempo_s=180, sistema=SISTEMA,
            extra=["--no-session-persistence"], para="la revision de ortografia")
        datos = comun.extraer_json(respuesta, "la revision de ortografia")
        correcciones = (datos or {}).get("correcciones") if isinstance(datos, dict) else None
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
    return salida


def como_json(resultado):
    return json.dumps(resultado, ensure_ascii=False)

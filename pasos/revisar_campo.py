"""«Revisar»: lee lo escrito en un campo y lo compara con SU guia de escritura.

    revisar(gid, texto) -> {"veredicto", "resumen", "problemas": [...], "sugerida"}

Para que
--------
Las guias (`pasos/guias.py`) dicen como se rellena cada campo y QUE HACE EL
SISTEMA con lo que se escribe. Pero leer la guia y despues tu texto y juzgar si
encajan es trabajo que se hacia a ojo, y los fallos salen tarde: un tono que
habla de temas en vez de como contar se nota en el guion, diez minutos despues
(10-10-2026). Esto lo comprueba ANTES, con el mismo texto de la guia que lee la
pantalla y el asistente --una sola fuente--, y propone una version corregida
que se puede poner en el campo con un boton.

Va por SUSCRIPCION (el CLI de Claude), con sonnet y poco esfuerzo: es un juicio
corto. No cuesta imagenes ni dinero por llamada.
"""
try:
    from . import cli_claude, comun, guias
except ImportError:                                   # corriendo desde pasos/
    import cli_claude
    import comun
    import guias

MODELO = "sonnet"
ESFUERZO = "low"
MAX_TEXTO = 12000
VEREDICTOS = ("sirve", "mejorable", "no_sirve")

SISTEMA = ("Revisas textos que una persona escribe en un campo de una herramienta "
           "de creacion de videos. Juzgas SOLO si el texto cumple la guia de ese "
           "campo. Contestas en castellano y unicamente con el JSON pedido.")

INSTRUCCION = """Esta es la GUIA del campo «{titulo}». Dice que hace el sistema con
lo que se escribe ahi, que SI hay que poner y que NO:

<guia>
{guia}
</guia>

Y esto es lo que la persona ha escrito en ese campo:

<texto>
{texto}
</texto>

Comprueba si el texto sirve PARA LO QUE EL SISTEMA HACE CON EL, segun la guia.
Fijate sobre todo en lo que la guia pone en «NO» (cosas que el sistema
malinterpreta o ignora) y en lo que falta de «SI». No corrijas el estilo ni la
ortografia salvo que confundan al sistema. No inventes requisitos que la guia
no tenga.

EL LISTON ES FIJO, no se mueve en cada vuelta:
- «sirve» = nada de lo escrito hara que el sistema se equivoque. Un texto que
  cumple la guia SIRVE aunque se pudiera pulir mas: no busques mejoras de gusto.
- «mejorable» = hay algo CONCRETO que hara que el resultado salga peor (cita
  el trozo y di que hara mal el sistema).
- «no_sirve» = el sistema no puede trabajar con esto (falta lo esencial o
  contradice la guia).
- Si el veredicto NO es «sirve», la «sugerida» es OBLIGATORIA: el texto entero
  ya corregido, que la persona pone en el campo con un boton. Tiene que CUMPLIR
  LA GUIA ENTERA: es el texto que tu mismo darias por «sirve» si te lo volvieran
  a pasar. Si falta un dato que solo la persona sabe, no lo inventes: escribe
  la version que mejor cumpla sin el y dilo en el resumen.
{anterior}
Devuelve SOLO este JSON:
{{
  "veredicto": "sirve" | "mejorable" | "no_sirve",
  "resumen": "<una o dos frases, para la persona>",
  "problemas": [
    {{"que": "<lo que falla, citando un trozo corto>",
      "por_que": "<que hara mal el sistema con eso, segun la guia>",
      "arreglo": "<que poner en su lugar>"}}
  ],
  "sugerida": "<el texto entero corregido, conservando todo lo que ya estaba bien
               y la voz de la persona; vacio si el veredicto es «sirve»>"
}}
Como mucho 6 problemas, los que mas importan primero."""


class ErrorRevision(RuntimeError):
    """No se ha podido revisar, con el motivo en castellano."""


ANTERIOR = """
ESTE CAMPO YA SE REVISO ANTES, y esto es lo que se dijo:
<revision_anterior>
{anterior}
</revision_anterior>
Mira SOBRE TODO si esos problemas estan resueltos. No pidas cosas nuevas que no
pediste entonces, salvo que el texto de ahora haya metido un problema que antes
no estaba. Si lo de antes esta resuelto y no hay nada nuevo que haga fallar al
sistema, el veredicto es «sirve».
"""


def _anterior_como_texto(anterior):
    if not isinstance(anterior, dict):
        return ""
    lineas = []
    if anterior.get("veredicto"):
        lineas.append(f"veredicto: {anterior['veredicto']}")
    if anterior.get("resumen"):
        lineas.append(f"resumen: {str(anterior['resumen'])[:600]}")
    for p in (anterior.get("problemas") or [])[:6]:
        if isinstance(p, dict) and p.get("que"):
            lineas.append(f"- {str(p.get('que'))[:300]} -> {str(p.get('arreglo') or '')[:300]}")
    return ANTERIOR.format(anterior="\n".join(lineas)) if lineas else ""


def revisar(gid, texto, cwd=None, anterior=None):
    if gid not in guias.GUIAS:
        raise ErrorRevision(f"no hay ninguna guia «{gid}»")
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorRevision("el campo esta vacio: escribe algo y vuelve a revisar")
    if len(texto) > MAX_TEXTO:
        raise ErrorRevision(f"el texto pasa de {MAX_TEXTO} caracteres: revisalo por partes")
    instruccion = INSTRUCCION.format(titulo=guias.GUIAS[gid]["titulo"],
                                     guia=guias.como_texto(gid), texto=texto,
                                     anterior=_anterior_como_texto(anterior))
    respuesta, sobre = cli_claude.ejecutar(
        instruccion, modelo=MODELO, esfuerzo=ESFUERZO, cwd=cwd,
        base_tiempo_s=120, sistema=SISTEMA,
        extra=["--no-session-persistence"], para="la revision del campo")
    datos = comun.extraer_json(respuesta, "la revision del campo")
    return normalizar(datos, sobre)


def normalizar(datos, sobre=None):
    """Lo que devolvio el modelo, saneado: nada que la pantalla no sepa pintar."""
    datos = datos if isinstance(datos, dict) else {}
    veredicto = datos.get("veredicto") if datos.get("veredicto") in VEREDICTOS else "mejorable"
    problemas = []
    for p in (datos.get("problemas") or [])[:6]:
        if isinstance(p, dict) and str(p.get("que") or "").strip():
            problemas.append({k: " ".join(str(p.get(k) or "").split())[:500]
                              for k in ("que", "por_que", "arreglo")})
    sugerida = str(datos.get("sugerida") or "").strip()
    if veredicto == "sirve":
        sugerida = ""
    return {"veredicto": veredicto,
            "resumen": " ".join(str(datos.get("resumen") or "").split())[:600],
            "problemas": problemas, "sugerida": sugerida[:MAX_TEXTO],
            "tokens": comun.tokens_de_cli(sobre) if sobre else {}}


def huella(gid, texto):
    """La misma revision para el mismo texto: se compara sin espacios de mas."""
    import hashlib                                          # noqa: PLC0415
    llano = " ".join(str(texto or "").split())
    # CON LA GUIA DENTRO: si la guia cambia, lo revisado contra la vieja no vale
    try:
        guia = guias.como_texto(gid)
    except Exception:                                       # noqa: BLE001
        guia = ""
    # Y CON LA INSTRUCCION: las revisiones guardadas con la de antes (que
    # dejaba la sugerida vacia a menudo) no se vuelven a servir
    sello = hashlib.sha1((guia + INSTRUCCION).encode("utf-8")).hexdigest()[:8]
    return hashlib.sha1(f"{gid}\n{sello}\n{llano}".encode("utf-8")).hexdigest()[:20]


def aprobada_por_la_revision():
    """Lo que se responde cuando el texto ES la version que propuso la revision."""
    return {"veredicto": "sirve",
            "resumen": "Es la versión que propuso la propia revisión: cumple la guía. "
                       "Si la cambias, vuelve a revisarla.",
            "problemas": [], "sugerida": "", "tokens": {}, "de_memoria": True}

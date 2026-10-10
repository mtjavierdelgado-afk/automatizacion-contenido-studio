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


def revisar(gid, texto, cwd=None):
    if gid not in guias.GUIAS:
        raise ErrorRevision(f"no hay ninguna guia «{gid}»")
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorRevision("el campo esta vacio: escribe algo y vuelve a revisar")
    if len(texto) > MAX_TEXTO:
        raise ErrorRevision(f"el texto pasa de {MAX_TEXTO} caracteres: revisalo por partes")
    instruccion = INSTRUCCION.format(titulo=guias.GUIAS[gid]["titulo"],
                                     guia=guias.como_texto(gid), texto=texto)
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

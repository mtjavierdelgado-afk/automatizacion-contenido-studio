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
{contexto}
EL LISTON ES FIJO, no se mueve en cada vuelta:
- «sirve» = nada de lo escrito hara que el sistema se equivoque. Un texto que
  cumple la guia SIRVE aunque se pudiera pulir mas: no busques mejoras de gusto.
- «mejorable» = hay algo CONCRETO que hara que el resultado salga peor (cita
  el trozo y di que hara mal el sistema).
- «no_sirve» = el sistema no puede trabajar con esto (falta lo esencial o
  contradice la guia).
- Si listas ALGUN problema (aunque el veredicto sea «sirve») o el veredicto no
  es «sirve», la «sugerida» es OBLIGATORIA: el texto entero ya corregido, que
  la persona pone en el campo con un boton. Tiene que CUMPLIR
  LA GUIA ENTERA: es el texto que tu mismo darias por «sirve» si te lo volvieran
  a pasar. Si falta un dato que solo la persona sabe, no lo inventes: escribe
  la version que mejor cumpla sin el y dilo en el resumen.
- En cada problema, «original» es el trozo EXACTO del texto que hay que
  cambiar, copiado letra a letra (con sus tildes y signos), y «mejor» lo que va
  en su lugar, listo para pegar: la persona lo cambia con un boton aunque no
  aplique la sugerida entera. Deja los dos vacios si el problema es que FALTA
  algo y no hay trozo que cambiar. Con un texto largo, aunque te cueste
  reescribirlo entero, rellena SIEMPRE «original» y «mejor».
{anterior}
Devuelve SOLO este JSON:
{{
  "veredicto": "sirve" | "mejorable" | "no_sirve",
  "resumen": "<una o dos frases, para la persona>",
  "problemas": [
    {{"que": "<lo que falla, citando un trozo corto>",
      "por_que": "<que hara mal el sistema con eso, segun la guia>",
      "arreglo": "<que poner en su lugar>",
      "original": "<el trozo exacto del texto que se cambia; vacio si falta algo>",
      "mejor": "<lo que va en lugar de «original»>"}}
  ],
  "sugerida": "<el texto entero corregido, conservando todo lo que ya estaba bien
               y la voz de la persona; vacio SOLO si no hay ningun problema>"
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


#: LO QUE EL CAMPO NO SABE POR SI SOLO: cuanto dura el video (17-10-2026).
#:
#: Sin esto, «Revisar» del material juzgaba el texto solo contra su guia, que
#: dice «mas hechos dan mejor guion», y daba por bueno un material de dos o tres
#: minutos para un video de treinta segundos. El redactor, con eso delante,
#: solo puede resumir (ver `p3_guion.DURACION_CORTA_S`). Ahora, en el material y
#: en las indicaciones, la revision sabe la duracion, las palabras que caben y,
#: en el material, lo que piden las indicaciones.
GUIAS_CON_DURACION = ("material", "indicaciones")

#: Hasta aqui un video es corto: LA MISMA cifra que usa el redactor
#: (`p3_guion.DURACION_CORTA_S`; lo comprueba prueba_piezas). No se importa
#: de alli para no cargar el paso entero en una revision de un campo.
DURACION_CORTA_S = 90

CONTEXTO = """
LO QUE ESTE CAMPO NO DICE Y CAMBIA EL JUICIO: el video dura {segundos} s, y en
ese tiempo caben unas {palabras} palabras de locucion en total.{corto}{extra}
"""

CONTEXTO_MATERIAL = """
Comprueba tambien si el material CABE: si trae muchos mas hechos de los que se
pueden contar bien en {palabras} palabras, el redactor tendra que elegir y
el guion puede salir como un resumen que nombra todo y no explica nada. En ese
caso es «mejorable»: dilo y, en la sugerida, NO borres hechos: {como_elegir}
Si las indicaciones
piden mostrar, medir o comparar algo y el material no trae los datos para
hacerlo (medidas, tamanos, tiempos), dilo como problema y pide a la persona
esos datos: no los inventes.{indicaciones}"""

CONTEXTO_INDICACIONES = """
Comprueba tambien que lo que piden quepa en ese tiempo: una sola idea en ENSENA
y un ANGULO que sea una escena concreta que se pueda contar paso a paso (algo
que se ve: meter, comparar, probar), no un tema general. Si el ANGULO es un
tema y no una escena, es «mejorable»."""


def contexto_saneado(gid, crudo):
    """Lo que manda la pantalla, reducido a lo que se usa. -> dict ({} si nada)

    Solo para el material y las indicaciones, y solo dos claves: la duracion
    (segundos > 0, hasta cuatro horas) y, en el material, las indicaciones.
    """
    if gid not in GUIAS_CON_DURACION or not isinstance(crudo, dict):
        return {}
    if isinstance(crudo.get("duracion_s"), bool):
        return {}
    try:
        segundos = float(crudo.get("duracion_s") or 0)
    except (TypeError, ValueError):
        return {}
    if not 0 < segundos <= 4 * 3600 or segundos != segundos:
        return {}
    contexto = {"duracion_s": segundos}
    if gid == "material" and isinstance(crudo.get("indicaciones"), str):
        contexto["indicaciones"] = crudo["indicaciones"][:4000]
    return contexto


def _contexto_como_texto(gid, contexto):
    """El trozo de la instruccion con la duracion del video. -> str ("" si no aplica)"""
    if gid not in GUIAS_CON_DURACION or not isinstance(contexto, dict):
        return ""
    try:
        segundos = int(round(float(contexto.get("duracion_s") or 0)))
    except (TypeError, ValueError):
        return ""
    if segundos <= 0:
        return ""
    try:
        try:
            from . import cadencia                    # noqa: PLC0415
        except ImportError:
            import cadencia                           # noqa: PLC0415
        palabras = int(cadencia.palabras_para(segundos, idioma="es")["palabras"])
    except Exception:                                 # noqa: BLE001
        palabras = int(round(segundos * 2.3))
    corto = (" Es un video CORTO: cabe UNA idea bien contada, no un repaso del "
             "tema." if segundos <= DURACION_CORTA_S else "")
    if gid == "material":
        otras = " ".join(str(contexto.get("indicaciones") or "").split())[:1500]
        # «IMPRESCINDIBLE:» solo lo lee el redactor de los cortos
        como_elegir = (
            "marca con «IMPRESCINDIBLE:» los dos o tres que tienen que entrar si "
            "o si (los que empujan lo que piden las indicaciones) y deja el resto "
            "debajo." if segundos <= DURACION_CORTA_S else
            "deja los hechos como estan y di en el resumen que conviene alargar "
            "el video o recortar el material a lo que pide este video.")
        extra = CONTEXTO_MATERIAL.format(
            palabras=palabras, como_elegir=como_elegir,
            indicaciones=(f"\nLas indicaciones de este video dicen: «{otras}»"
                          if otras else ""))
    else:
        extra = CONTEXTO_INDICACIONES
    return CONTEXTO.format(segundos=segundos, palabras=palabras, corto=corto,
                           extra=extra)


def _contexto_para_huella(gid, contexto):
    """Lo del contexto que cambia la revision, en una linea estable."""
    if gid not in GUIAS_CON_DURACION or not isinstance(contexto, dict):
        return ""
    try:
        segundos = int(round(float(contexto.get("duracion_s") or 0)))
    except (TypeError, ValueError):
        segundos = 0
    if segundos <= 0:
        return ""
    otras = " ".join(str(contexto.get("indicaciones") or "").split()) \
        if gid == "material" else ""
    return f"{segundos}|{otras}"


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


def revisar(gid, texto, cwd=None, anterior=None, contexto=None):
    if gid not in guias.GUIAS:
        raise ErrorRevision(f"no hay ninguna guia «{gid}»")
    texto = str(texto or "").strip()
    if not texto:
        raise ErrorRevision("el campo esta vacio: escribe algo y vuelve a revisar")
    if len(texto) > MAX_TEXTO:
        raise ErrorRevision(f"el texto pasa de {MAX_TEXTO} caracteres: revisalo por partes")
    instruccion = INSTRUCCION.format(titulo=guias.GUIAS[gid]["titulo"],
                                     guia=guias.como_texto(gid), texto=texto,
                                     anterior=_anterior_como_texto(anterior),
                                     contexto=_contexto_como_texto(gid, contexto))
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
            problema = {k: " ".join(str(p.get(k) or "").split())[:500]
                        for k in ("que", "por_que", "arreglo")}
            # EL TROZO Y SU MEJORA, TAL CUAL: la pantalla los busca letra a
            # letra en el campo para cambiar solo ese trozo con un boton, asi
            # que aqui no se aplanan los espacios ni los saltos de linea (N5 de
            # las notas de mejoras, 13-10-2026)
            original = str(p.get("original") or "").strip()
            mejor = str(p.get("mejor") or "").strip()
            # un trozo más largo que el tope NO se corta: cortado ya no coincide
            # con el campo y la pantalla diría «ya no está tal cual»; sin él, el
            # problema se enseña sin botón de aplicar
            if (original and mejor and original != mejor
                    and len(original) <= 1000 and len(mejor) <= 2000):
                problema["original"], problema["mejor"] = original, mejor
            problemas.append(problema)
    sugerida = str(datos.get("sugerida") or "").strip()
    # «Sirve» SIN problemas no propone nada. Pero un «sirve» que lista
    # problemas con su «Mejor: …» y se quedaba sin la version corregida dejaba
    # a la persona viendo mejoras sin ningun boton para aplicarlas (N5 de las
    # notas de mejoras, 13-10-2026): si hay problemas, la sugerida se queda.
    if veredicto == "sirve" and not problemas:
        sugerida = ""
    return {"veredicto": veredicto,
            "resumen": " ".join(str(datos.get("resumen") or "").split())[:600],
            "problemas": problemas, "sugerida": sugerida[:MAX_TEXTO],
            "tokens": comun.tokens_de_cli(sobre) if sobre else {}}


def huella(gid, texto, contexto=None):
    """La misma revision para el mismo texto: se compara sin espacios de mas.

    Con la duracion dentro en el material y las indicaciones: el mismo texto
    puede servir para cuatro minutos y no para treinta segundos.
    """
    import hashlib                                          # noqa: PLC0415
    llano = " ".join(str(texto or "").split())
    # CON LA GUIA DENTRO: si la guia cambia, lo revisado contra la vieja no vale
    try:
        guia = guias.como_texto(gid)
    except Exception:                                       # noqa: BLE001
        guia = ""
    # Y CON LA INSTRUCCION: las revisiones guardadas con la de antes (que
    # dejaba la sugerida vacia a menudo) no se vuelven a servir
    # SIN EL HUECO DEL CONTEXTO: es la instruccion de siempre, y con el hueco
    # dentro la huella de TODAS las guias cambiaba y ninguna revision guardada
    # se volvia a servir (revision independiente de guion-cortos)
    sello = hashlib.sha1((guia + INSTRUCCION.replace("{contexto}", ""))
                         .encode("utf-8")).hexdigest()[:8]
    extra = _contexto_para_huella(gid, contexto)
    if extra:
        sello = hashlib.sha1((sello + "\n" + extra + "\n" + CONTEXTO_MATERIAL
                              + CONTEXTO_INDICACIONES).encode("utf-8")).hexdigest()[:8]
    return hashlib.sha1(f"{gid}\n{sello}\n{llano}".encode("utf-8")).hexdigest()[:20]


def aprobada_por_la_revision():
    """Lo que se responde cuando el texto ES la version que propuso la revision."""
    return {"veredicto": "sirve",
            "resumen": "Es la versión que propuso la propia revisión: cumple la guía. "
                       "Si la cambias, vuelve a revisarla.",
            "problemas": [], "sugerida": "", "tokens": {}, "de_memoria": True}

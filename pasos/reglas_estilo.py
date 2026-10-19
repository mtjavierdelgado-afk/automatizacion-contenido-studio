"""LAS REGLAS DEL ESTILO: lo que un estilo no puede romper nunca.

QUE ES
------
Una lista corta de reglas que escribe quien hace el estilo, en su idioma y como
se lo diria a un fotografo: «quien juega mira siempre la pantalla, nunca a
camara». Nacio del video del torneo de EstadoPlay (18-10-2026): la estacion ya
salia bien --eso lo arreglo una regla de la casa-- pero los jugadores seguian
mirando a camara, porque el plano pedia a la vez la pantalla y las caras y el
generador hacia trampa. Meter esa regla en el codigo la habria impuesto a todos
los canales; aqui es del ESTILO, y cada canal trae las suyas.

Cada regla:

  nombre     corto, para la pantalla («Los jugadores miran la pantalla»)
  texto      lo que se exige, en el idioma de quien la escribe
  palabras   «solo si el plano habla de…»: si hay alguna, la regla solo entra
             en los planos cuyo texto (la descripcion, la voz, la nota) las
             nombra; sin ninguna, entra siempre
  gravedad   alta, media o baja: lo que el revisor pone si se incumple, y lo
             que decide si el modo autonomo la corrige solo
  en         (opcional) la version afinada en ingles, para el generador; la
             escribe «Afinar con Claude» y la aprueba la persona

DONDE TRABAJA
-------------
- En el prompt de cada plano (`p6_assets._prompt_completo`), detras de las
  reglas de la casa y delante de la escena, marcadas como obligatorias.
- En el corrector (`p6_assets._corregir_con_agente`), para que una correccion
  no las rompa.
- En el revisor (`revisor_imagenes`), como lista que comprobar una a una con
  su gravedad.

Y NO ESCRIBE NADA POR DEFECTO: un estilo sin reglas no lleva la clave, y el
prompt de un video sin reglas sale byte a byte como antes (regla 1 de
CLAUDE.md: una firma que se mueve sin que nadie pida nada es dinero).
"""
import os
import re
import time
import unicodedata

try:
    from . import cli_claude, comun
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun

GRAVEDADES = ("alta", "media", "baja")
MAX_REGLAS = 20
MAX_NOMBRE = 80
MAX_TEXTO = 800
MAX_EN = 1200
MAX_PALABRAS = 12
MAX_PALABRA = 40


class ReglaInvalida(ValueError):
    """Una regla que no se puede guardar, con el motivo para la persona."""


def _limpio(valor, tope):
    return " ".join(str(valor or "").split())[:tope]


def _llano(texto):
    """minusculas y sin tildes, para comparar palabras."""
    sin = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


def normalizar(reglas):
    """La lista validada y limpia. -> [dict] (vacia si no hay ninguna).

    Una regla sin texto se descarta (es un borrador vacio de la pantalla); una
    con texto y algo mal (gravedad rara, demasiadas) levanta ReglaInvalida."""
    if reglas in (None, ""):
        return []
    if not isinstance(reglas, list):
        raise ReglaInvalida("las reglas son una lista")
    salida, ids = [], set()
    # LOS IDS QUE YA TRAEN SE RESERVAN ANTES: si no, una regla sin id delante de
    # la «r1» se quedaba ese nombre y la «r1» de verdad pasaba a ser otra
    for cruda in reglas:
        if isinstance(cruda, dict) and _limpio(cruda.get("texto"), MAX_TEXTO + 1):
            propio = re.sub(r"[^a-z0-9_-]", "", str(cruda.get("id") or "").lower())[:24]
            if propio:
                ids.add(propio)
    vistos = set()
    for n, cruda in enumerate(reglas):
        if not isinstance(cruda, dict):
            raise ReglaInvalida(f"la regla {n + 1} no es un objeto")
        texto = _limpio(cruda.get("texto"), MAX_TEXTO + 1)
        if not texto:
            continue
        if len(texto) > MAX_TEXTO:
            raise ReglaInvalida(f"la regla {n + 1} es demasiado larga "
                                f"(máximo {MAX_TEXTO} caracteres)")
        gravedad = str(cruda.get("gravedad") or "media").strip().lower()
        if gravedad not in GRAVEDADES:
            raise ReglaInvalida(f"gravedad {gravedad!r}: solo alta, media o baja")
        palabras = cruda.get("palabras") or []
        if isinstance(palabras, str):
            palabras = palabras.split(",")
        if not isinstance(palabras, list):
            raise ReglaInvalida(f"las palabras de la regla {n + 1} son una lista")
        limpias = []
        for p in palabras:
            p = _limpio(p, MAX_PALABRA)
            if p and _llano(p) not in {_llano(x) for x in limpias}:
                limpias.append(p)
        if len(limpias) > MAX_PALABRAS:
            raise ReglaInvalida(f"la regla {n + 1} tiene más de {MAX_PALABRAS} palabras")
        rid = re.sub(r"[^a-z0-9_-]", "", str(cruda.get("id") or "").lower())[:24]
        if not rid or rid in vistos:
            rid = f"r{n + 1}"
            while rid in ids or rid in vistos:
                rid += "b"
        ids.add(rid)
        vistos.add(rid)
        regla = {"id": rid,
                 "nombre": _limpio(cruda.get("nombre"), MAX_NOMBRE) or texto[:60],
                 "texto": texto, "gravedad": gravedad}
        if limpias:
            regla["palabras"] = limpias
        en = _limpio(cruda.get("en"), MAX_EN)
        if en:
            regla["en"] = en
            # lo mismo en espanol, SOLO para leerlo en pantalla: la IA lee `en`
            es = _limpio(cruda.get("en_es"), MAX_EN)
            if es:
                regla["en_es"] = es
        salida.append(regla)
    if len(salida) > MAX_REGLAS:
        raise ReglaInvalida(f"como mucho {MAX_REGLAS} reglas por estilo: una lista "
                            f"más larga deja de leerse entera")
    return salida


def de_estilo(estilo):
    """Las reglas de un dict de estilo, sin levantar nunca. -> [dict]"""
    try:
        return normalizar((estilo or {}).get("reglas") if isinstance(estilo, dict) else None)
    except ReglaInvalida:
        return []


def aplica(regla, texto):
    """Si la regla entra en un plano con ese texto. Sin palabras, siempre."""
    palabras = regla.get("palabras") or []
    if not palabras:
        return True
    llano = _llano(texto)
    for p in palabras:
        # por el principio de la palabra: «jugador» casa con «jugadores»
        if re.search(r"(?<![a-z0-9])" + re.escape(_llano(p)), llano):
            return True
    return False


def para_prompt(reglas, texto_del_plano):
    """Las lineas que se anaden al prompt de un plano. -> [str] ([] si ninguna)"""
    vivas = [r for r in reglas or [] if aplica(r, texto_del_plano)]
    if not vivas:
        return []
    cuerpo = " ".join(f"({i + 1}) {r.get('en') or r['texto']}"
                      for i, r in enumerate(vivas))
    return ["RULES OF THIS STYLE, all of them mandatory -- they beat any "
            "description of the scene below, and where a rule and the scene "
            f"seem to clash, compose the shot so that the rule is kept: {cuerpo}"]


def para_corrector(reglas):
    """El texto de las reglas para el corrector de un plano. -> str"""
    if not reglas:
        return ""
    return "\n".join(["  REGLAS DEL ESTILO (obligatorias; la descripcion nueva "
                      "tiene que cumplirlas):"]
                     + [f"  - {r.get('en') or r['texto']}" for r in reglas])


def para_revisor(reglas):
    """El texto de las reglas para el revisor de imagenes. -> str"""
    if not reglas:
        return ""
    lineas = []
    for r in reglas:
        cuando = (f" (solo en los planos que hablan de: {', '.join(r['palabras'])})"
                  if r.get("palabras") else "")
        lineas.append(f"  - [{r['id']}] «{r['nombre']}»{cuando}: {r['texto']} "
                      f"-> si se incumple, gravedad {r['gravedad'].upper()}")
    return "\n".join(lineas)


# --------------------------------------------------------- afinar con Claude

FASE = "reglas_estilo"
#: Una regla se afina en segundos: con el defecto del canal (opus, esfuerzo muy
#: alto) el techo era de una hora, y la pantalla deja de preguntar a los tres
#: minutos. Sonnet/medium y un techo de dos minutos y medio, como el asistente.
MODELO = "sonnet"
ESFUERZO = "medium"
TIEMPO_MAX_S = 150

SISTEMA = ("Eres director de fotografia y redactor de prompts para un generador "
           "de imagenes. Responde exclusivamente con el objeto JSON pedido, sin "
           "texto alrededor y sin vallas de markdown.")

INSTRUCCION = """Una persona ha escrito una REGLA para su estilo de imagen: algo que
ninguna imagen de sus videos puede romper. Tienes que convertirla en lo que
necesita un generador de imagenes para cumplirla de verdad.

LA REGLA, como la escribio:
<<<
{texto}
>>>
{contexto}
Devuelve un objeto JSON con:
  "nombre"    un nombre corto en espanol (maximo 8 palabras), como titulo.
  "en"        la regla en INGLES, en imperativo, concreta y fisica: que se ve,
              donde esta la camara, hacia donde mira cada persona, que queda
              fuera de cuadro. Si la regla puede chocar con lo que pide un plano
              (por ejemplo, ver a la vez una pantalla y las caras de quien la
              mira), di COMO se compone para cumplir las dos cosas, y que esta
              prohibido. Maximo 120 palabras. Sin nombres de marcas.
  "palabras"  de 0 a 8 palabras en espanol que, si aparecen en lo que cuenta
              un plano, hacen que la regla aplique (por ejemplo: jugadores,
              mandos, partida). Lista vacia si debe aplicar siempre.
  "en_es"     EXACTAMENTE lo mismo que "en", traducido al espanol, frase por
              frase, sin anadir ni quitar nada: es para que la persona sepa
              que va a leer la IA.
  "gravedad"  "alta", "media" o "baja": cuanto se nota si se rompe.
"""


def afinar(texto, nombre="", palabras=(), cwd=None):
    """La regla afinada: {nombre, en, palabras, gravedad}. Levanta si falla."""
    texto = _limpio(texto, MAX_TEXTO)
    if not texto:
        raise ReglaInvalida("escribe primero lo que exige la regla")
    modelo = cli_claude.normalizar_modelo(os.environ.get("ESTUDIO_REGLAS_MODELO"),
                                          defecto=MODELO)
    esfuerzo = cli_claude.normalizar_esfuerzo(os.environ.get("ESTUDIO_REGLAS_ESFUERZO"),
                                              defecto=ESFUERZO)
    contexto = ""
    if nombre:
        contexto += f"\nSu nombre ahora: {_limpio(nombre, MAX_NOMBRE)}\n"
    if palabras:
        contexto += f"Palabras que ya puso: {', '.join(palabras)}\n"
    arranque = time.time()
    texto_resp, _sobre = cli_claude.ejecutar(
        INSTRUCCION.format(texto=texto, contexto=contexto),
        modelo=modelo, esfuerzo=esfuerzo, cwd=cwd,
        tiempo_max_s=TIEMPO_MAX_S, sistema=SISTEMA,
        herramientas_vetadas=("Bash", "Write", "Edit", "NotebookEdit", "Read",
                              "Grep", "Glob", "WebFetch", "WebSearch", "Task",
                              "TodoWrite"),
        extra=["--no-session-persistence"], para="afinar una regla del estilo")
    datos = comun.extraer_json(texto_resp, "la regla afinada")
    if not isinstance(datos, dict):
        raise RuntimeError("la respuesta no es un objeto")
    regla = normalizar([{"texto": texto, "nombre": datos.get("nombre") or nombre,
                         "palabras": datos.get("palabras") or [],
                         "gravedad": datos.get("gravedad") if datos.get("gravedad")
                         in GRAVEDADES else "media",
                         "en": datos.get("en"), "en_es": datos.get("en_es")}])
    if not regla or not regla[0].get("en"):
        raise RuntimeError("Claude no devolvió la regla afinada")
    salida = {k: v for k, v in regla[0].items() if k != "id"}
    salida["segundos"] = round(time.time() - arranque, 1)
    return salida

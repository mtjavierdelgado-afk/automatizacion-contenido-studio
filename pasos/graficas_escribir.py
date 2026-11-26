"""«Escríbelo por mí» de Gráficas (rama graficas-facil, 26-11-2026; plan en
`estado/plan_graficas_facil_2026-11-26.md`).

Claude (por el CLI de la membresía: cupo, no dinero) escribe los textos de una
publicación, una historia o un carrusel a partir de un tema y de la ficha del
negocio. Lo que vuelve NO se usa tal cual: el servidor aplica sus reglas, que
son las que de verdad mandan (el prompt también las pide, pero un modelo se
equivoca):

- **Tipos**: solo los de `TIPOS_IA`. Nunca una Cita (sería un testimonio
  falso). Dato y Precio, solo si su cifra o su precio están en el tema o en la
  ficha.
- **Cifras**: se permiten las que solo cuentan o numeran («Los 3 juegos»,
  «Paso 2», «#1», hasta 2 cifras). La moneda (S/, $, US$, €), el %, «x de y»,
  «x veces» y las cifras de 3 o más dígitos, solo si aparecen tal cual en el
  tema o en la ficha; si no, ese campo vuelve a su texto de muestra (y la nota
  del carrusel avisa de los textos de muestra antes de publicar).
- **Comparativa**: siempre «Nosotros» / «Lo de siempre»; nunca el nombre de un
  competidor.
- Topes de largo por campo, portada primero y cierre al final.

El resultado es una lista de piezas `[(tipo, {campo: texto})]`, la misma forma
que da `graficas_carrusel.partir`, así se monta con las funciones de siempre.
"""
import json
import re
import unicodedata

import comun
import graficas_carrusel as K
from graficas import ErrorGraficas

QUE = ("publicacion", "carrusel", "historia")
#: Los tipos que la IA puede elegir para las imágenes de dentro.
TIPOS_IA = ("punto", "lista", "pasos", "pregunta", "mito", "checklist", "ranking", "comparativa", "dato", "precio")
#: Solo con una cifra o un precio que estén en el tema o en la ficha.
TIPOS_CON_CIFRA = ("dato", "precio")
CUANTAS_MIN, CUANTAS_MAX, CUANTAS_DEFECTO = 3, 10, 7
MAX_TEMA = 600
#: Tope de letras por campo (lo que cabe bien en una imagen).
TOPES = {"titulo": 80, "apoyo": 120, "texto": 160, "numero": 4, "cifra": 14, "cta": 28, "guardalo": 40,
         "pregunta": 110, "mito": 120, "realidad": 140, "etiqueta1": 14, "etiqueta2": 16,
         "precio": 16, "precio_antes": 16, **{f"v{i}": 70 for i in range(1, 6)}}
#: Los campos de cada tipo (lo que se le pide a la IA y lo único que se acepta).
CAMPOS = {
    "portada": ("titulo", "apoyo"),
    "punto": ("numero", "titulo", "texto"),
    "lista": ("titulo", "v1", "v2", "v3", "v4", "v5"),
    "pasos": ("titulo", "v1", "v2", "v3", "v4", "v5"),
    "pregunta": ("pregunta", "texto"),
    "mito": ("mito", "realidad"),
    "checklist": ("titulo", "v1", "v2", "v3", "v4", "v5"),
    "ranking": ("titulo", "v1", "v2", "v3", "v4", "v5"),
    "comparativa": ("titulo", "v1", "v2", "v3", "v4", "v5"),
    "dato": ("cifra", "texto"),
    "precio": ("titulo", "precio_antes", "precio", "texto", "cta"),
    "cierre": ("titulo", "texto", "cta"),
}
#: Las cifras que solo valen si están en el tema o en la ficha.
_RE_CIFRA = re.compile(
    r"(?:S/\.?|US\$|\$|€|USD|PEN)\s*\d[\d.,\s]*\d|(?:S/\.?|US\$|\$|€)\s*\d"     # moneda delante
    r"|\d[\d.,]*\s*(?:%|por\s*ciento|soles|dólares|dolares|euros)"              # %, o moneda detrás
    r"|\d+\s+de\s+(?:cada\s+)?\d+"                                              # «8 de 10»
    r"|\d+\s*(?:x|veces)\b"                                                     # «3x», «2 veces»
    r"|\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d+)?|\d{3,}(?:[.,]\d+)?",                  # 1 250, 1.250, 300
    re.I)

INSTRUCCION = """Escribe los textos de {que_largo} para las redes de un negocio. Tema:
<tema>
{tema}
</tema>

<negocio>
{negocio}
</negocio>

Reglas:
- En español de Perú, cercano y claro, con el tono del negocio. Frases cortas: se leen en un móvil.
- {cuantas_txt}
- Tipos que puedes usar para las de dentro: {tipos}. {dato_precio}
- NUNCA inventes testimonios ni opiniones de clientes, ni estadísticas, porcentajes, precios,
  ofertas, plazos o cifras que no estén en el tema o en el negocio. Los números que solo
  cuentan («Los 3 juegos», «Paso 2») sí valen.
- No nombres a ninguna otra marca ni a la competencia.
- Campos de cada tipo (y su largo máximo en letras):
{campos}

Devuelve SOLO este JSON: {{"laminas": [{{"tipo": "portada", "titulo": "...", "apoyo": "..."}}, ...]}}
"""

QUE_LARGO = {"publicacion": "UNA publicación (una sola imagen: solo la portada)",
             "historia": "UNA historia (una sola imagen vertical: solo la portada)",
             "carrusel": "un carrusel de Instagram"}


def _plano(texto):
    """Para comparar cifras: minúsculas, sin tildes y con los espacios juntos."""
    texto = unicodedata.normalize("NFKC", str(texto or "")).lower()
    return re.sub(r"\s+", " ", texto).strip()


def _solo_digitos(texto):
    return re.sub(r"\D", "", texto)


def cifras_que_no_estan(texto, fuente):
    """Las cifras «de verdad» (moneda, %, «x de y», 3+ dígitos…) de `texto` que
    no aparecen en `fuente` (el tema y la ficha). Se compara por sus dígitos
    («S/ 1 299» casa con «S/1299» o «1.299 soles»)."""
    fuente_p = _plano(fuente)
    digitos_fuente = {_solo_digitos(m.group(0)) for m in re.finditer(r"\d[\d.,\s]*\d|\d", fuente_p)}
    faltan = []
    for m in _RE_CIFRA.finditer(_plano(texto)):
        cifra = m.group(0).strip()
        numeros = re.findall(r"\d[\d.,\s]*\d|\d", cifra)
        # «8 de 10»: valen si los dos números están en la fuente
        if numeros and all(_solo_digitos(n) in digitos_fuente for n in numeros):
            continue
        faltan.append(cifra)
    return faltan


def _texto(valor, campo):
    texto = " ".join(re.sub(r"[\x00-\x1f\x7f<>]", " ", str(valor or "")).split())
    tope = TOPES.get(campo, 80)
    if len(texto) > tope:
        # se corta en la última palabra entera que cabe
        texto = texto[:tope].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return texto


def _muestra(tipo, campo):
    if tipo == "portada":
        return {"titulo": "Tu titular aquí", "apoyo": ""}.get(campo, "")
    return K.MUESTRA.get(tipo, {}).get(campo, "")


def validar(datos, que, tema, negocio="", cuantas=CUANTAS_DEFECTO):
    """Lo que devolvió Claude -> (piezas, avisos), con las reglas del servidor."""
    fuente = f"{tema}\n{negocio}"
    bruto = datos.get("laminas") if isinstance(datos, dict) else None
    if not isinstance(bruto, list):
        raise ErrorGraficas("la IA no ha devuelto las imágenes: prueba otra vez o escríbelo tú")
    avisos, piezas, cambiadas = [], [], 0
    hay_cifra = bool(_RE_CIFRA.search(_plano(fuente)))
    for item in bruto[:30]:
        if not isinstance(item, dict):
            continue
        tipo = str(item.get("tipo") or "").strip().lower()
        if tipo == "portada" and not piezas:
            pass
        elif tipo == "cierre":
            pass
        elif tipo not in TIPOS_IA:
            continue                                        # Cita, inventados, una 2.ª portada…
        elif tipo in TIPOS_CON_CIFRA and not hay_cifra:
            continue                                        # un Dato o un Precio sin cifra dada
        t = {}
        for campo in CAMPOS[tipo]:
            valor = _texto(item.get(campo), campo)
            if not valor:
                continue
            if cifras_que_no_estan(valor, fuente):
                valor = _muestra(tipo, campo)
                cambiadas += 1
            if valor:
                t[campo] = valor
        if tipo == "comparativa":
            t["etiqueta1"], t["etiqueta2"] = "Nosotros", "Lo de siempre"
        if tipo == "mito":
            t["etiqueta1"], t["etiqueta2"] = "Mito", "Realidad"
        if tipo == "precio" and not (t.get("precio") and t["precio"] != _muestra("precio", "precio")):
            continue                                        # sin un precio dado, no hay lámina de precio
        if tipo in ("lista", "pasos", "checklist", "ranking", "comparativa") and not any(t.get(f"v{i}") for i in range(1, 6)):
            continue
        if not any(v.strip() for k, v in t.items() if not k.startswith("etiqueta")):
            continue
        piezas.append((tipo, t))
    if not piezas or piezas[0][0] != "portada":
        titulo = _texto(tema.split("\n")[0], "titulo")
        if cifras_que_no_estan(titulo, fuente):
            titulo = _muestra("portada", "titulo")
        piezas.insert(0, ("portada", {"titulo": titulo or _muestra("portada", "titulo")}))
    if que in ("publicacion", "historia"):
        piezas = piezas[:1]
    else:
        cierre = next((p for p in piezas[1:] if p[0] == "cierre"), None)
        dentro = [p for p in piezas[1:] if p[0] != "cierre"][:max(1, cuantas - 2)]
        if not dentro:
            raise ErrorGraficas("la IA no ha escrito ninguna imagen de dentro: prueba otra vez o escríbelo tú")
        # los puntos, numerados en orden
        n = 0
        for tipo, t in dentro:
            if tipo == "punto":
                n += 1
                t["numero"] = f"{n:02d}"
        piezas = [piezas[0]] + dentro + [cierre or ("cierre", dict(K.MUESTRA["cierre"]))]
    if cambiadas:
        avisos.append(f"{cambiadas} texto(s) llevaban una cifra o un precio que no diste: quedan como texto "
                      "de muestra para que pongas el dato real.")
    return piezas, avisos


def instruccion(que, tema, negocio="", cuantas=CUANTAS_DEFECTO):
    tipos = [t for t in TIPOS_IA if t not in TIPOS_CON_CIFRA]
    campos = "\n".join(f"  - {t}: " + ", ".join(f"{c} ({TOPES.get(c, 80)})" for c in CAMPOS[t])
                       for t in ("portada", *TIPOS_IA, "cierre"))
    if que == "carrusel":
        cuantas_txt = (f"{cuantas} imágenes en total: la 1.ª «portada» (el gancho, 10 palabras o menos), "
                       f"{cuantas - 2} de dentro con UNA idea cada una, y la última «cierre» con UNA sola "
                       "petición (guardar, escribir o comentar).")
    else:
        cuantas_txt = "Solo UNA imagen, de tipo «portada»: un titular con gancho y, si ayuda, una frase de apoyo."
    return INSTRUCCION.format(
        que_largo=QUE_LARGO[que], tema=tema[:MAX_TEMA], negocio=(negocio or "—")[:2500], cuantas_txt=cuantas_txt,
        tipos=", ".join(tipos),
        dato_precio=("Si el tema o el negocio dan una cifra o un precio, puedes usar «dato» o «precio» con ESA cifra."),
        campos=campos)


def escribir(que, tema, negocio, cuantas, llamar):
    """Pide los textos a Claude (`llamar(instruccion) -> texto`) y los valida.
    Si el JSON viene roto, se pide UNA vez más. -> (piezas, avisos)"""
    if que not in QUE:
        raise ErrorGraficas("¿una publicación, un carrusel o una historia?")
    tema = " ".join(str(tema or "").split())
    if len(tema) < 3:
        raise ErrorGraficas("escribe de qué trata (una frase basta)")
    if len(tema) > MAX_TEMA:
        raise ErrorGraficas(f"el tema es largo: con {MAX_TEMA} letras como mucho basta")
    try:
        cuantas = int(cuantas) if cuantas not in (None, "") else CUANTAS_DEFECTO
    except (TypeError, ValueError):
        cuantas = CUANTAS_DEFECTO
    cuantas = max(CUANTAS_MIN, min(CUANTAS_MAX, cuantas))
    pedido = instruccion(que, tema, negocio, cuantas)
    ultimo = None
    for _vez in range(2):
        respuesta = llamar(pedido)
        try:
            datos = comun.extraer_json(respuesta, "los textos")
            return validar(datos, que, tema, negocio, cuantas)
        except (ValueError, RuntimeError, ErrorGraficas) as fallo:
            ultimo = fallo
    raise ErrorGraficas(f"la IA no ha devuelto unos textos que se puedan usar ({ultimo}): "
                        "prueba otra vez o escríbelos tú")


def simulado(instruccion):
    """La respuesta de Claude cuando el Studio corre simulado (ESTUDIO_SIMULAR):
    un carrusel corto con el tema de titular, y una Cita que las reglas quitan."""
    tema = re.search(r"<tema>\s*(.*?)\s*</tema>", instruccion, re.S)
    tema = tema.group(1) if tema else "Tu tema"
    return json.dumps({"laminas": [
        {"tipo": "portada", "titulo": tema[:70], "apoyo": "Lo que nadie te cuenta"},
        {"tipo": "punto", "titulo": "Prueba todo antes", "texto": "Revisa cada mando y cada cable el día anterior."},
        {"tipo": "lista", "titulo": "Lo que no puede faltar", "v1": "Pantalla grande", "v2": "4 mandos", "v3": "Juegos para varios"},
        {"tipo": "pregunta", "pregunta": "¿Cuántos mandos necesitas?", "texto": "La respuesta, en la siguiente"},
        {"tipo": "cita", "cita": "«Inventada»", "autor": "Nadie"},
        {"tipo": "cierre", "titulo": "¿Te sirvió?", "texto": "Guárdalo para tu próxima fiesta.", "cta": "Escríbenos"}]},
        ensure_ascii=False)


"""«Crear desde un vídeo» (rama graficas-desde-video, 26-11-2026).

Lee la narración y la descripción de los planos de un vídeo del proyecto
(su plan de imágenes; NO toca el vídeo, sus params ni sus firmas, regla 1),
le pide a Claude (cupo de la membresía, sin dinero) las imágenes de una
publicación, historia o carrusel con, en cada una, el plano que mejor la
ilustra, y aplica las reglas del servidor:

- los planos permitidos: con imagen y narración; sin cartelas, mapas ni
  gráficos (llevan sus propias letras y cifras); sin imágenes repetidas (la
  continuación de un plano largo es la misma imagen con otro id), mirado por la
  huella del fichero; como mucho 80 repartidos a lo largo del vídeo y 8.000
  letras;
- un plano que no está en la lista, o repetido, deja esa imagen sin foto;
- cifras: las de la ficha y el tema como siempre; de la narración, una cifra
  con moneda o % vale solo si está, con una unidad del mismo tipo, en la
  narración del plano elegido para esa imagen (así «S/ 300» no pasa porque el
  vídeo diga «300 personas»); un número suelto, si está en esa narración;
- siempre en español (si la narración está en otro idioma, se entiende y se
  escribe en español).

Plan: estado/plan_graficas_desde_video_2026-11-26.md (v3, aprobado).
"""
import hashlib
import json
import os
import re

import graficas_escribir as E
from graficas import ErrorGraficas

MAX_PLANOS = 80
MAX_LETRAS = 8000
MAX_VISUAL = 160
MIN_PLANOS = 3

INSTRUCCION = """Escribe los textos de {que_largo} para las redes de un negocio, a partir de uno de sus vídeos.

El vídeo «{titulo}». Sus planos, en orden (id, lo que dice la voz y lo que se ve):
<planos>
{planos}
</planos>

<negocio>
{negocio}
</negocio>

Reglas:
- SIEMPRE en español de Perú, aunque la voz del vídeo esté en otro idioma. Cercano y claro, frases cortas.
- {cuantas_txt}
- Tipos que puedes usar para las de dentro: {tipos}. Si una cifra o un precio sale en la voz o en el negocio,
  puedes usar «dato» o «precio» con ESA cifra.
- Cuenta lo que dice el vídeo; NUNCA inventes testimonios, opiniones de clientes, estadísticas, porcentajes,
  precios, ofertas o plazos. Los números que solo cuentan («Los 3 juegos», «Paso 2») sí valen.
- No nombres a ninguna otra marca ni a la competencia.
- En CADA imagen pon «plano»: el id del plano cuya imagen mejor la ilustra (uno distinto en cada una), y
  «alt»: una frase corta que diga qué se ve, para quien no puede verla.
- Campos de cada tipo (y su largo máximo en letras):
{campos}

Devuelve SOLO este JSON: {{"laminas": [{{"tipo": "portada", "titulo": "...", "apoyo": "...", "plano": "...", "alt": "..."}}, ...]}}
"""


def _huella(ruta):
    """La huella del fichero (los primeros 256 KB y el tamaño): dos ids con la misma imagen dan la misma."""
    h = hashlib.sha1()
    with open(ruta, "rb") as fh:
        h.update(fh.read(262144))
    h.update(str(os.path.getsize(ruta)).encode())
    return h.hexdigest()


def planos_permitidos(plan, rutas):
    """Los planos que se pueden usar: [{sid, narracion, visual, ruta}] en orden
    de vídeo, con las reglas del módulo. `plan`: el plan de imágenes (`escenas`);
    `rutas`: {sid: ruta del PNG activo}."""
    vistos, salida = set(), []
    for escena in (plan or {}).get("escenas") or []:
        sid = str(escena.get("id") or "")
        ruta = rutas.get(sid)
        narracion = " ".join(str(escena.get("narracion") or "").split())
        if not sid or not ruta or not os.path.isfile(ruta) or not narracion:
            continue
        if escena.get("componente"):
            continue                                        # cartelas, mapas, gráficos: llevan letras
        try:
            huella = _huella(ruta)
        except OSError:
            continue
        if huella in vistos:
            continue
        vistos.add(huella)
        visual = " ".join(str(escena.get("linea_gv") or escena.get("prompt") or "").split())[:MAX_VISUAL]
        salida.append({"sid": sid, "narracion": narracion, "visual": visual, "ruta": ruta})
    if len(salida) > MAX_PLANOS:
        paso = len(salida) / MAX_PLANOS
        salida = [salida[int(i * paso)] for i in range(MAX_PLANOS)]
    return salida


def _bloque_de_planos(planos):
    """Los planos en texto para Claude, dentro de las 8.000 letras (se recorta
    cada narración por igual si no caben)."""
    lineas = [f"[{p['sid']}] voz: {p['narracion']} | se ve: {p['visual']}" for p in planos]
    total = sum(len(x) + 1 for x in lineas)
    if total > MAX_LETRAS and planos:
        tope = max(40, MAX_LETRAS // len(planos) - 30)
        lineas = [f"[{p['sid']}] voz: {p['narracion'][:tope]} | se ve: {p['visual'][:60]}" for p in planos]
    texto = "\n".join(lineas)
    return texto[:MAX_LETRAS]


def instruccion(que, titulo, planos, negocio="", cuantas=E.CUANTAS_DEFECTO):
    base = E.instruccion(que, titulo or "el vídeo", negocio, cuantas)
    # se reutiliza lo que ya escribe la de siempre (tipos, campos, cuántas)
    tipos = ", ".join(t for t in E.TIPOS_IA if t not in E.TIPOS_CON_CIFRA)
    campos = "\n".join(f"  - {t}: " + ", ".join(f"{c} ({E.TOPES.get(c, 80)})" for c in E.CAMPOS[t])
                       for t in ("portada", *E.TIPOS_IA, "cierre"))
    cuantas_txt = re.search(r"- (.+?)\n- Tipos", base, re.S).group(1).strip()
    return INSTRUCCION.format(que_largo=E.QUE_LARGO[que], titulo=(titulo or "sin título")[:120],
                              planos=_bloque_de_planos(planos), negocio=(negocio or "—")[:2500],
                              cuantas_txt=cuantas_txt, tipos=tipos, campos=campos)


_RE_MONEDA = re.compile(r"s/\.?|us\$|\$|€|usd|pen|soles?|d[oó]lares?|euros?|nuevos soles", re.I)


_MONEDAS = (("PEN", re.compile(r"s/|nuevos soles|soles?\b|\bpen\b")),
            ("EUR", re.compile(r"€|euros?\b|\beur\b")),
            ("USD", re.compile(r"us\$|\$|\busd\b|d[oó]lares?\b|dollars?\b")))


def _clase_de_unidad(cifra):
    """«porcentaje», la moneda concreta (PEN, USD, EUR) o "" (árbitro, 26-11:
    «S/ 300» no es «300 dólares»)."""
    c = E._plano(cifra)
    if "%" in c or "por ciento" in c or "percent" in c:
        return "porcentaje"
    for moneda, patron in _MONEDAS:
        if patron.search(c):
            return moneda
    if _RE_MONEDA.search(c):
        return "moneda"
    return ""


def cifra_en_narracion(cifra, narracion):
    """¿Esta cifra del texto está en la narración del plano? Con moneda o %,
    tiene que estar con una unidad del mismo tipo; si no, basta el número."""
    clase = _clase_de_unidad(cifra)
    numeros = [E._solo_digitos(n) for n in re.findall(r"\d[\d.,\s]*\d|\d", E._plano(cifra))]
    if not numeros:
        return True
    narr = E._plano(narracion)
    if not clase:
        digitos = {E._solo_digitos(m.group(0)) for m in re.finditer(r"\d[\d.,\s]*\d|\d", narr)}
        return all(n in digitos for n in numeros)
    # las cifras de la narración con su unidad (también «300 soles», «300 percent», «$300»)
    patron = re.compile(r"(?:s/\.?|us\$|\$|€|usd|pen)\s*\d[\d.,\s]*\d?|\d[\d.,\s]*\s*(?:%|por\s*ciento|(?:percent|soles?|"
                        r"d[oó]lares?|dollars?|euros?|nuevos soles|pen|usd|eur)\b)", re.I)
    con_unidad = {(E._solo_digitos(m.group(0)), _clase_de_unidad(m.group(0))) for m in patron.finditer(narr)}
    return all((n, clase) in con_unidad for n in numeros)


def validar(datos, que, titulo, planos, negocio="", cuantas=E.CUANTAS_DEFECTO):
    """Lo que devolvió Claude -> (piezas, avisos); cada pieza lleva en su dict
    «plano» (un sid permitido, distinto en cada una, o "") y «alt»."""
    por_sid = {p["sid"]: p for p in planos}
    bruto = datos.get("laminas") if isinstance(datos, dict) else None
    if not isinstance(bruto, list):
        raise ErrorGraficas("la IA no ha devuelto las imágenes: prueba otra vez o escríbelo tú")
    # 1) cifras de la narración: una cifra que solo está en la voz del plano
    #    elegido se acepta (se pasa a la fuente de ESA imagen); las demás, a las reglas de siempre
    limpio, cambiadas = [], 0
    for item in bruto[:30]:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        narr = por_sid.get(str(item.get("plano") or ""), {}).get("narracion", "")
        # la misma forma de leer el tipo que graficas_escribir.validar (árbitro: « precio » se saltaba esto)
        item["tipo"] = str(item.get("tipo") or "").strip().lower()
        for campo in E.CAMPOS.get(item["tipo"], ()):
            valor = E._texto(item.get(campo), campo)
            faltan = E.cifras_que_no_estan(valor, negocio) if valor else []
            if faltan and all(cifra_en_narracion(c, narr) for c in faltan):
                item[campo] = valor
                item.setdefault("_de_la_voz", []).append(campo)
            elif faltan:
                item[campo] = ""
                cambiadas += 1
        limpio.append(item)
    # 2) las reglas de siempre, con las cifras de la voz ya dadas por buenas
    fuente_voz = " ".join(E._texto(it.get(c), c) for it in limpio for c in it.get("_de_la_voz", []))
    piezas, avisos = E.validar({"laminas": limpio}, que, titulo or "", f"{negocio}\n{fuente_voz}", cuantas)
    # 3) el plano y el alt de cada pieza (por orden: validar no reordena lo que deja)
    restantes = list(limpio)
    usados = set()

    def clave(tipo, d):
        campos = [c for c in E.CAMPOS.get(tipo, ()) if c != "numero"]
        return next((E._texto(d.get(c), c) for c in campos if E._texto(d.get(c), c)), "")
    for tipo, t in piezas:
        origen = None
        for j, cand in enumerate(restantes):
            if str(cand.get("tipo") or "").lower() == tipo and clave(tipo, cand) == clave(tipo, t):
                origen = restantes.pop(j)
                break
        if origen is None:
            # su texto cambió (una cifra que pasó a muestra): el primero de su tipo
            j = next((j for j, cand in enumerate(restantes) if str(cand.get("tipo") or "").lower() == tipo), None)
            origen = restantes.pop(j) if j is not None else None
        sid = str((origen or {}).get("plano") or "")
        if sid not in por_sid or sid in usados:
            sid = ""
        if sid:
            usados.add(sid)
        t["plano"] = sid
        t["alt"] = E._texto((origen or {}).get("alt"), "texto")[:200] if origen else ""
    if cambiadas:
        avisos.append(f"{cambiadas} texto(s) llevaban una cifra que no está en el vídeo ni en tu negocio: "
                      "quedan como texto de muestra para que pongas el dato real.")
    return piezas, avisos


def escribir(que, titulo, planos, negocio, cuantas, llamar):
    """Pide los textos a Claude y los valida (1 reintento si el JSON viene roto)."""
    if que not in E.QUE:
        raise ErrorGraficas("¿una publicación, un carrusel o una historia?")
    if len(planos) < MIN_PLANOS:
        raise ErrorGraficas("este vídeo no tiene imágenes con narración suficientes: elige otro")
    try:
        cuantas = int(cuantas) if cuantas not in (None, "") else E.CUANTAS_DEFECTO
    except (TypeError, ValueError):
        cuantas = E.CUANTAS_DEFECTO
    cuantas = max(E.CUANTAS_MIN, min(E.CUANTAS_MAX, cuantas))
    pedido = instruccion(que, titulo, planos, negocio, cuantas)
    ultimo = None
    for _vez in range(2):
        respuesta = llamar(pedido)
        try:
            datos = E.comun.extraer_json(respuesta, "los textos")
            return validar(datos, que, titulo, planos, negocio, cuantas)
        except (ValueError, RuntimeError, ErrorGraficas) as fallo:
            ultimo = fallo
    raise ErrorGraficas(f"la IA no ha devuelto unos textos que se puedan usar ({ultimo}): prueba otra vez o escríbelos tú")


def simulado(instruccion_texto):
    """La respuesta de Claude simulado: usa los primeros planos de la lista (y
    repite uno y se inventa otro, que las reglas quitan)."""
    ids = re.findall(r"^\[([^\]]+)\]", instruccion_texto, re.M)
    titulo = re.search(r"El vídeo «(.*?)»", instruccion_texto)
    titulo = titulo.group(1) if titulo else "Tu vídeo"
    sid = (ids + ["", "", "", ""])
    return json.dumps({"laminas": [
        {"tipo": "portada", "titulo": titulo[:70], "apoyo": "Lo que cuenta el vídeo", "plano": sid[0], "alt": "La portada"},
        {"tipo": "punto", "titulo": "La primera idea", "texto": "Lo que dice el vídeo al principio.", "plano": sid[1], "alt": "Un plano"},
        {"tipo": "lista", "titulo": "Lo que se ve", "v1": "Uno", "v2": "Dos", "v3": "Tres", "plano": sid[1], "alt": "El mismo plano"},
        {"tipo": "pregunta", "pregunta": "¿Y tú qué harías?", "texto": "La respuesta, en la siguiente", "plano": "no-existe"},
        {"tipo": "cierre", "titulo": "¿Te sirvió?", "texto": "Guárdalo.", "cta": "Escríbenos", "plano": sid[2] if len(ids) > 2 else ""}]},
        ensure_ascii=False)

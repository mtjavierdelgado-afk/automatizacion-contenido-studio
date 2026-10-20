"""ELEMENTOS DENTRO DEL VIDEO (rama `elementos-video`, 19-10-2026): el grafismo
de las portadas (`pasos/grafismo.py`) puesto ENCIMA de cada plano y animado al
ritmo de la voz, para que el video no pierda a quien lo mira.

    els = elementos_video.de_plano(params_callouts, "escena:S004")
    svg = elementos_video.fragmento(escena, els, salida, paleta, duracion)

Donde vive
----------
En la unidad de callouts de cada plano: `unidades["escena:S004"]["elementos"]`,
como el movimiento propio del plano. Asi cambiarlo deja obsoleto SOLO ese plano
(sus capas y su trozo del montaje, gratis) y ni una imagen. Sin elementos la
clave no existe y la capa sale identica a la de siempre (regla 1).

Un elemento
-----------
Los campos de `grafismo` (tipo, texto, x, y, tam, color, icono...) y estos:

    palabra   indice de la palabra de la narracion del plano en la que salta
              (la voz trae el momento de cada palabra: `escena["marcas"]`)
    desde     o, si no hay palabra, el segundo dentro del plano
    dura      cuanto se queda (s); por defecto, hasta 1,6 s
    entrada   pop | golpe | desliza | aparece | dibuja

Los colores pueden ser un #rrggbb o un papel: «acento» (el del video),
«alerta» (rojo), «bien» (verde) o «texto» (blanco); asi un elemento sigue a
la paleta del video aunque esta cambie.

La intensidad (sobrio, vivo, dinamico) NO se guarda: solo dice a Claude
cuantos proponer. Lo guardado son los elementos.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grafismo  # noqa: E402

CLAVE = "elementos"

ENTRADAS = ("pop", "golpe", "desliza", "aparece", "dibuja")

#: Cada cuantos segundos de narracion va un elemento, segun la intensidad (la
#: investigacion del 19-10: no pasar 5 s sin un cambio; para negocios locales,
#: «vivo» por defecto; «dinamico» solo para cortos muy juveniles).
INTENSIDADES = {
    "sobrio": {"nombre": "Sobrio", "cada_s": 9.0, "que": "unos 6 por minuto: lo justo"},
    "vivo": {"nombre": "Vivo", "cada_s": 4.5, "que": "unos 13 por minuto: lo recomendado"},
    "dinamico": {"nombre": "Dinámico", "cada_s": 2.6, "que": "unos 23 por minuto: muy movido"},
}

#: Los papeles de color, resueltos con la paleta del video al dibujar.
PAPELES = {"alerta": "#ff3b30", "bien": "#22c55e", "texto": "#ffffff", "negro": "#111111"}

#: Lo que se puede poner dentro del video (el marco y la rafaga, no: tapan).
TIPOS = ("texto", "insignia", "flecha", "circulo", "rayo", "icono", "etiqueta",
         "banda", "subrayado", "estrellas", "cinta")

MAX_POR_PLANO = 6
DURA_DEFECTO = 1.6


def limpiar(lista):
    """Los elementos de un plano, validados. -> list (nunca lanza)."""
    crudos = [e for e in (lista or []) if isinstance(e, dict) and e.get("tipo") in TIPOS][:MAX_POR_PLANO]
    salida = []
    for crudo, limpio in zip(crudos, grafismo.limpiar_elementos(crudos)):
        # los colores por papel («acento») no son #rrggbb: grafismo los quitaria
        for campo in ("color", "contorno", "acento", "color_texto"):
            valor = str(crudo.get(campo) or "")
            if valor in PAPELES or valor == "acento":
                limpio[campo] = valor
        try:
            palabra = int(crudo.get("palabra"))
            if 0 <= palabra < 2000:
                limpio["palabra"] = palabra
        except (TypeError, ValueError):
            pass
        for campo, (minimo, maximo) in {"desde": (0.0, 600.0), "dura": (0.3, 30.0)}.items():
            try:
                valor = float(crudo.get(campo))
            except (TypeError, ValueError):
                continue
            if valor == valor:                                  # no NaN
                limpio[campo] = round(max(minimo, min(maximo, valor)), 3)
        if crudo.get("entrada") in ENTRADAS:
            limpio["entrada"] = crudo["entrada"]
        salida.append(limpio)
    return salida


def de_plano(params, uid):
    """Los elementos de ESE plano, o [] (sin clave = sin elementos)."""
    bloque = ((params or {}).get("unidades") or {}).get(uid)
    return limpiar(bloque.get(CLAVE)) if isinstance(bloque, dict) else []


def momento(el, escena, duracion):
    """(desde, hasta) en segundos dentro del plano."""
    t_in = float(escena.get("t_in") or 0.0)
    marcas = escena.get("marcas") or []
    desde = None
    if "palabra" in el and el["palabra"] < len(marcas):
        try:
            desde = float(marcas[el["palabra"]][0]) - t_in
        except (TypeError, ValueError, IndexError):
            desde = None
    if desde is None:
        desde = float(el.get("desde") or 0.0)
    desde = max(0.0, min(desde, max(0.0, duracion - 0.3)))
    hasta = min(duracion - 0.04, desde + float(el.get("dura") or DURA_DEFECTO))
    return round(desde, 3), round(max(desde + 0.25, hasta), 3)


def _colores(el, paleta):
    """El elemento con sus papeles de color cambiados por colores de verdad."""
    acento = (paleta or {}).get("linea") or (paleta or {}).get("acento") or "#ffd84d"
    resuelto = dict(el)
    for campo in ("color", "contorno", "acento", "color_texto"):
        valor = resuelto.get(campo)
        if valor == "acento":
            resuelto[campo] = acento
        elif valor in PAPELES:
            resuelto[campo] = PAPELES[valor]
    if resuelto.get("tipo") == "texto":
        resuelto.setdefault("acento", acento)
    return resuelto


def _centro(el, W, H):
    if el.get("tipo") in ("flecha", "rayo"):
        x = (float(el.get("x", 0.3)) + float(el.get("x2", 0.6))) / 2
        y = (float(el.get("y", 0.3)) + float(el.get("y2", 0.6))) / 2
        return x * W, y * H
    if el.get("tipo") == "banda":
        return W / 2, float(el.get("y", 0.88)) * H
    return float(el.get("x", 0.5)) * W, float(el.get("y", 0.5)) * H


def _animado(interior, entrada, desde, hasta, cx, cy, W, uid):
    """El elemento con su entrada y su salida (SMIL, como las cifras)."""
    aparece = (f'<set attributeName="opacity" to="1" begin="{desde:.2f}s"/>'
               f'<animate attributeName="opacity" from="1" to="0" begin="{hasta - 0.18:.2f}s" '
               f'dur="0.18s" fill="freeze"/>')
    if entrada == "aparece":
        aparece = (f'<animate attributeName="opacity" from="0" to="1" begin="{desde:.2f}s" '
                   f'dur="0.25s" fill="freeze"/>'
                   f'<animate attributeName="opacity" from="1" to="0" begin="{hasta - 0.2:.2f}s" '
                   f'dur="0.2s" fill="freeze"/>')
        cuerpo = interior
    elif entrada == "golpe":
        cuerpo = (f'<g transform="translate({cx:.0f},{cy:.0f})"><g>'
                  f'<animateTransform attributeName="transform" type="scale" values="1.9;0.92;1.04;1" '
                  f'keyTimes="0;0.55;0.8;1" dur="0.22s" begin="{desde:.2f}s" fill="freeze"/>'
                  f'<animateTransform attributeName="transform" type="rotate" values="0;-3;3;0" '
                  f'dur="0.16s" begin="{desde + 0.2:.2f}s" additive="sum" fill="freeze"/>'
                  f'<g transform="translate({-cx:.0f},{-cy:.0f})">{interior}</g></g></g>')
    elif entrada == "desliza":
        cuerpo = (f'<g><animateTransform attributeName="transform" type="translate" '
                  f'values="{-W * 0.25:.0f},0;8,0;0,0" keyTimes="0;0.8;1" dur="0.28s" '
                  f'begin="{desde:.2f}s" fill="freeze"/>{interior}</g>')
    elif entrada == "dibuja":
        # se descubre de izquierda a derecha, como si se trazara
        cuerpo = (f'<clipPath id="{uid}-dib"><rect x="0" y="0" width="0" height="100%">'
                  f'<animate attributeName="width" from="0" to="{W}" dur="0.4s" begin="{desde:.2f}s" '
                  f'fill="freeze"/></rect></clipPath><g clip-path="url(#{uid}-dib)">{interior}</g>')
    else:                                                       # pop
        cuerpo = (f'<g transform="translate({cx:.0f},{cy:.0f})"><g>'
                  f'<animateTransform attributeName="transform" type="scale" values="0.2;1.15;1" '
                  f'keyTimes="0;0.65;1" dur="0.24s" begin="{desde:.2f}s" fill="freeze"/>'
                  f'<g transform="translate({-cx:.0f},{-cy:.0f})">{interior}</g></g></g>')
    return f'<g opacity="0">{cuerpo}{aparece}</g>'


def fragmento(escena, elementos, salida, paleta, duracion):
    """Los elementos de un plano, dibujados y animados. -> svg ('' si no hay)."""
    elementos = limpiar(elementos)
    if not elementos:
        return ""
    W, H = int(salida[0]), int(salida[1])
    piezas = []
    for i, el in enumerate(elementos):
        resuelto = _colores(el, paleta)
        interior = grafismo.elemento(resuelto, W, H)
        if not interior:
            continue
        desde, hasta = momento(el, escena, float(duracion))
        cx, cy = _centro(resuelto, W, H)
        uid = f"el{re.sub(r'[^A-Za-z0-9]', '', str(escena.get('id') or ''))}{i}"
        piezas.append(_animado(interior, el.get("entrada") or "pop", desde, hasta, cx, cy, W, uid))
    if not piezas:
        return ""
    return grafismo.css_fuentes(grafismo.fuentes_de(elementos)) + "".join(piezas)


def fichas(escena, elementos, duracion):
    """Lo que se apunta en la ficha del plano (para la pantalla)."""
    salida = []
    for el in limpiar(elementos):
        desde, hasta = momento(el, escena, float(duracion))
        salida.append({"tipo": f"elemento:{el['tipo']}", "texto": el.get("texto") or el.get("icono") or "",
                       "desde": desde, "hasta": hasta})
    return salida


def estatico(elementos, salida, paleta):
    """Los elementos SIN animar (todos a la vista), para la vista previa."""
    W, H = int(salida[0]), int(salida[1])
    els = [_colores(e, paleta) for e in limpiar(elementos)]
    return grafismo.css_fuentes(grafismo.fuentes_de(els)) + "".join(grafismo.elemento(e, W, H) for e in els)


# ------------------------------------------------------------------ las posiciones

#: Donde va cada cosa en el cuadro: Claude elige un sitio con nombre y aqui se
#: convierte en coordenadas, lejos del subtitulo (abajo en horizontal, a dos
#: tercios en vertical) y de los botones de las redes (a la derecha en vertical).
POSICIONES = {
    "horizontal": {"arriba": (0.5, 0.16), "centro": (0.5, 0.42), "izquierda": (0.24, 0.38),
                   "derecha": (0.76, 0.38), "arriba_izquierda": (0.2, 0.16), "arriba_derecha": (0.8, 0.16)},
    "vertical": {"arriba": (0.48, 0.2), "centro": (0.48, 0.42), "izquierda": (0.28, 0.36),
                 "derecha": (0.66, 0.36), "arriba_izquierda": (0.26, 0.2), "arriba_derecha": (0.68, 0.2)},
}


def colocar(el, posicion, vertical):
    """Pone x, y (y x2, y2 en flechas y rayos) segun una posicion con nombre."""
    tabla = POSICIONES["vertical" if vertical else "horizontal"]
    x, y = tabla.get(posicion) or tabla["arriba"]
    el = dict(el, x=x, y=y)
    if el.get("tipo") == "flecha":
        el.update(x=max(0.05, x - 0.18), y=min(0.9, y + 0.14), x2=x, y2=y)
    if el.get("tipo") == "rayo":
        el.update(x=0.56, y=-0.02, x2=0.44, y2=1.02)
    return el


# ------------------------------------------------------------------ con Claude

INSTRUCCION = """Eres editor de videos para redes. Este video narrado se ve con
imagenes fijas, y para que no pierda a quien lo mira hay que poner encima, en el
momento justo, ELEMENTOS GRAFICOS: una palabra clave que salta, una flecha o un
circulo que señala, una insignia, una cifra grande, un check o una cruz, un
icono, estrellas en un testimonio, un precio en una etiqueta...

Intensidad pedida: {intensidad} ({que}). En total, unos {total} elementos para
todo el video, repartidos (no todos al principio) y en los momentos que lo
merecen: cifras, precios, palabras fuertes, comparaciones, preguntas,
llamadas a la accion, cambios de tema. Nunca dos en la misma palabra. El texto
de un elemento: 1 a 3 palabras, en el idioma del video, sacadas o resumidas de
lo que se dice (no inventes datos). Los subtitulos ya estan abajo: no repitas
la frase entera.

Tipos: texto (palabra que salta), insignia (circulo/estallido con texto corto:
VS, -50 %, NUEVO, 1, 2, 3), etiqueta (pastilla: precio, GRATIS), icono
({iconos}), flecha (señala), circulo (rodea), estrellas (testimonio), subrayado,
banda (texto de lado a lado, para un CTA), rayo (versus).
Posiciones: arriba, centro, izquierda, derecha, arriba_izquierda, arriba_derecha.
Entradas: pop (salto), golpe (impacto fuerte), desliza, aparece (suave), dibuja.
Colores: acento (el del video), alerta (rojo), bien (verde), texto (blanco).

Cada plano trae sus palabras numeradas: «palabra» es el NUMERO de la palabra
en la que salta el elemento.

<planos>
{planos}
</planos>

Contesta SOLO con este JSON (los planos sin nada, no los pongas):
{{"planos": {{"<id>": [{{"tipo": "<tipo>", "texto": "<texto>", "palabra": <n>,
  "posicion": "<posicion>", "entrada": "<entrada>", "color": "<color>",
  "icono": "<icono si es icono>", "forma": "circulo|estallido|pastilla (insignia)"}}]}}}}"""


def planos_para_claude(escenas, maximo_palabras=60):
    """Las narraciones de los planos con sus palabras numeradas."""
    lineas = []
    for e in escenas:
        palabras = str(e.get("narracion") or "").split()
        if not palabras:
            continue
        numeradas = " ".join(f"{i}:{p}" for i, p in enumerate(palabras[:maximo_palabras]))
        dur = float(e.get("t_out") or 0) - float(e.get("t_in") or 0)
        lineas.append(f'<p id="{e.get("id")}" s="{dur:.1f}">{numeradas}</p>')
    return "\n".join(lineas)


def instruccion(escenas, intensidad):
    intensidad = intensidad if intensidad in INTENSIDADES else "vivo"
    total_s = sum(max(0.0, float(e.get("t_out") or 0) - float(e.get("t_in") or 0)) for e in escenas)
    total = max(1, int(round(total_s / INTENSIDADES[intensidad]["cada_s"])))
    return INSTRUCCION.format(intensidad=INTENSIDADES[intensidad]["nombre"],
                              que=INTENSIDADES[intensidad]["que"], total=total,
                              iconos=", ".join(grafismo.ICONOS), planos=planos_para_claude(escenas))


def leer_propuesta(datos, escenas, vertical):
    """{plano: [elementos]} validados, colocados y sin pasar de MAX_POR_PLANO.
    Un plano o una palabra que no existen se descartan."""
    por_id = {str(e.get("id")): e for e in escenas}
    salida = {}
    for sid, lista in ((datos or {}).get("planos") or {}).items():
        escena = por_id.get(str(sid))
        if escena is None or not isinstance(lista, list):
            continue
        n_palabras = len(str(escena.get("narracion") or "").split())
        usadas, elementos = set(), []
        for crudo in lista:
            if not isinstance(crudo, dict) or crudo.get("tipo") not in TIPOS:
                continue
            try:
                palabra = int(crudo.get("palabra"))
            except (TypeError, ValueError):
                palabra = 0
            if not 0 <= palabra < max(1, n_palabras) or palabra in usadas:
                continue
            usadas.add(palabra)
            el = {k: v for k, v in crudo.items() if k not in ("posicion",)}
            el["palabra"] = palabra
            el.setdefault("color", "acento" if el["tipo"] in ("texto", "insignia", "etiqueta", "subrayado") else "alerta")
            if el["tipo"] == "texto":
                el.setdefault("estilos", ["contorno", "sombra"])
                el.setdefault("tam", 0.1)
                el.setdefault("lineas", 2)
                el.setdefault("ancho", 0.7)
            if el["tipo"] == "icono":
                el.setdefault("tam", 0.07)
            if el["tipo"] in ("insignia",):
                el.setdefault("tam", 0.08)
            el = colocar(el, crudo.get("posicion") or "arriba", vertical)
            elementos.append(el)
        elementos = limpiar(elementos)
        if elementos:
            salida[str(sid)] = elementos
    return salida


def proponer(escenas, intensidad, vertical, cwd=None):
    """Claude propone los elementos de estos planos. -> {plano: [elementos]}"""
    import cli_claude                                           # noqa: PLC0415
    import comun                                                # noqa: PLC0415
    texto, _sobre = cli_claude.ejecutar(
        instruccion(escenas, intensidad), modelo="sonnet", esfuerzo="low", cwd=cwd,
        base_tiempo_s=240, extra=["--no-session-persistence"], para="los elementos del video")
    datos = comun.extraer_json(texto, "los elementos del video")
    return leer_propuesta(datos, escenas, vertical)


def nota_texto_en_imagen(texto):
    """LA OTRA OPCION (se paga): pedir la imagen otra vez con el texto DENTRO,
    por la cola de notas de imagenes de siempre."""
    texto = " ".join(str(texto or "").split())[:60]
    return (f"Integra en la imagen el texto «{texto}» escrito de forma grande, muy legible y bien "
            f"contrastada, como parte del dibujo (cartel, pantalla o rótulo dentro de la escena), "
            f"con las tildes exactas. Sin más texto que ese.")


def como_json(x):
    return json.dumps(x, ensure_ascii=False)

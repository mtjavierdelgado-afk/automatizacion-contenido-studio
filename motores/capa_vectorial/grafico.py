"""
Graficos con cifras como SVG vectorial (rama diagramas-por-contenido).

Como los mapas, NO pasan por el generador de imagen: un modelo de difusion
escribe «35 %» como «3S %» y dibuja la barra del 35 mas alta que la del 60. Aqui
las barras miden lo que dicen las cifras y las cifras salen escritas como en el
guion. Y es gratis: no se paga ninguna imagen.

Las cifras ya llegan validadas (`pasos/diagramas.limpiar_grafico`: cada una
esta escrita en el guion). Este modulo solo dibuja.

    python grafico.py --config config.json --out grafico.svg

Clases: barras (2 a 6), comparacion (2), proporcion (1, de 0 a 100) y
antes_despues (2, el primero es el antes).
"""
import argparse
import json
import math
import os
from xml.sax.saxutils import escape

# La paleta de los mapas: los dos componentes vectoriales de un video tienen
# que parecer del mismo video.
COLORES = {
    "fondo": "#2c3f4d",
    "panel": "#3f4a3a",
    "linea": "#12130f",
    "barra": "#d8a657",
    "barra_2": "#d8785a",
    "pista": "#4d5c66",
    "texto": "#ece7dc",
    "suave": "#b9b3a6",
}

ANCHO, ALTO = 1536, 1024
FUENTE = "Verdana, sans-serif"


def _cifra(valor, unidad=""):
    """La cifra como se lee: 1.500, 2,5 y la unidad pegada o con espacio."""
    if float(valor).is_integer():
        texto = f"{int(valor):,}".replace(",", ".")
    else:
        texto = f"{valor:,.2f}".rstrip("0").rstrip(".")
        texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    unidad = (unidad or "").strip()
    if not unidad:
        return texto
    if unidad == "%":
        return f"{texto} %"
    if unidad in ("S/", "$", "€", "US$"):
        return f"{unidad} {texto}"
    return f"{texto} {unidad}"


def _texto(x, y, contenido, tam=34, ancla="middle", color=None, peso=700):
    return (f'<text x="{round(x, 1)}" y="{round(y, 1)}" text-anchor="{ancla}" '
            f'font-family="{FUENTE}" font-size="{tam}" font-weight="{peso}" '
            f'fill="{color or COLORES["texto"]}" stroke="{COLORES["linea"]}" '
            f'stroke-width="6" paint-order="stroke">{escape(str(contenido))}</text>')


def _tam_para(texto, ancho, tam):
    """El cuerpo de letra que cabe en 'ancho' (Verdana: ~0,62 em por letra)."""
    largo = max(1, len(str(texto)))
    return max(18, min(tam, int(ancho / (largo * 0.62))))


def _barras(datos, unidad, caja, colores=None):
    x0, y0, x1, y1 = caja
    n = len(datos)
    hueco = (x1 - x0) / n
    ancho = min(220, hueco * 0.6)
    tope = max(d["valor"] for d in datos) or 1
    alto_util = (y1 - y0) - 150
    partes = [f'<line x1="{x0}" y1="{y1 - 70}" x2="{x1}" y2="{y1 - 70}" '
              f'stroke="{COLORES["linea"]}" stroke-width="6" stroke-linecap="round"/>']
    for i, dato in enumerate(datos):
        cx = x0 + hueco * (i + 0.5)
        alto = max(6, alto_util * dato["valor"] / tope)
        base = y1 - 70
        color = (colores or [COLORES["barra"]])[i % len(colores or [1])]
        partes.append(
            f'<rect class="barra" data-indice="{i}" x="{round(cx - ancho / 2, 1)}" '
            f'y="{round(base - alto, 1)}" width="{round(ancho, 1)}" '
            f'height="{round(alto, 1)}" rx="10" fill="{color}" '
            f'stroke="{COLORES["linea"]}" stroke-width="5"/>')
        cifra = _cifra(dato["valor"], unidad)
        partes.append(_texto(cx, base - alto - 22, cifra,
                             _tam_para(cifra, hueco * 0.95, 44)))
        partes.append(_texto(cx, base + 52, dato["etiqueta"],
                             _tam_para(dato["etiqueta"], hueco * 0.95, 32),
                             color=COLORES["suave"]))
    return partes


def _proporcion(dato, unidad, caja):
    x0, y0, x1, y1 = caja
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - 20
    r = min(x1 - x0, y1 - y0) * 0.36
    grosor = r * 0.34
    fraccion = max(0.0, min(1.0, dato["valor"] / 100.0))
    largo = 2 * math.pi * r
    partes = [
        f'<circle cx="{cx}" cy="{cy}" r="{round(r, 1)}" fill="none" '
        f'stroke="{COLORES["pista"]}" stroke-width="{round(grosor, 1)}"/>',
        f'<circle class="arco" cx="{cx}" cy="{cy}" r="{round(r, 1)}" fill="none" '
        f'stroke="{COLORES["barra"]}" stroke-width="{round(grosor, 1)}" '
        f'stroke-dasharray="{round(largo * fraccion, 1)} {round(largo, 1)}" '
        f'transform="rotate(-90 {cx} {cy})"/>',
    ]
    cifra = _cifra(dato["valor"], unidad or "%")
    partes.append(_texto(cx, cy + 30, cifra, _tam_para(cifra, r * 1.2, 92)))
    partes.append(_texto(cx, cy + r + grosor / 2 + 60, dato["etiqueta"],
                         _tam_para(dato["etiqueta"], x1 - x0, 36),
                         color=COLORES["suave"]))
    return partes


def _antes_despues(datos, unidad, caja):
    x0, y0, x1, y1 = caja
    partes = _barras(datos, unidad, caja, [COLORES["pista"], COLORES["barra"]])
    # la flecha entre las dos barras: el antes y el despues se leen como paso
    medio_y = (y0 + y1) / 2
    cx = (x0 + x1) / 2
    partes.append(
        f'<path class="flecha" d="M {cx - 60} {medio_y} L {cx + 40} {medio_y} '
        f'M {cx + 10} {medio_y - 34} L {cx + 50} {medio_y} L {cx + 10} {medio_y + 34}" '
        f'fill="none" stroke="{COLORES["texto"]}" stroke-width="12" '
        f'stroke-linecap="round" stroke-linejoin="round"/>')
    return partes


def construir(config):
    clase = config.get("clase") or "barras"
    datos = [d for d in (config.get("datos") or []) if isinstance(d, dict)]
    if not datos:
        raise ValueError("un grafico sin datos no se puede dibujar")
    unidad = config.get("unidad") or ""
    titulo = (config.get("titulo") or "").upper()
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {ALTO}" '
        f'width="{ANCHO}" height="{ALTO}" data-clase="{escape(clase)}">',
        f'<rect width="{ANCHO}" height="{ALTO}" fill="{COLORES["fondo"]}"/>',
        f'<rect x="70" y="60" width="{ANCHO - 140}" height="{ALTO - 120}" rx="28" '
        f'fill="{COLORES["panel"]}" stroke="{COLORES["linea"]}" stroke-width="6"/>',
    ]
    arriba = 110
    if titulo:
        partes.append(_texto(ANCHO / 2, 160, titulo, _tam_para(titulo, ANCHO - 260, 56)))
        arriba = 210
    caja = (150, arriba, ANCHO - 150, ALTO - 110)
    if clase == "proporcion":
        partes += _proporcion(datos[0], unidad, caja)
    elif clase == "antes_despues":
        partes += _antes_despues(datos[:2], unidad, caja)
    elif clase == "comparacion":
        partes += _barras(datos[:2], unidad, caja, [COLORES["barra"], COLORES["barra_2"]])
    else:
        partes += _barras(datos[:6], unidad, caja)
    partes.append("</svg>")
    return "\n".join(partes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    with open(args.config, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    svg = construir(config)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[grafico] {args.out}  ({len(svg)} bytes)")


if __name__ == "__main__":
    main()

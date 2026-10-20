"""PORTADAS DISENADAS (rama `portadas`, 19-10-2026): la miniatura de un video
hecha como las que funcionan en YouTube, Instagram y TikTok, en vez de un
fotograma suelto.

    diseno = portadas.de_plantilla("versus", textos, paleta="gamer", formato="9:16")
    png = portadas.renderizar(diseno, resolver, destino)   # resolver: fondos -> rutas
    portadas.guardar(raiz, pid, diseno)                    # el diseno, para retocarlo luego

Lo que hay
----------
- PLANTILLAS: veinte maneras probadas de montar una miniatura (versus, antes y
  despues, top N, pregunta, oferta, dato impactante...). Cada una pone sus
  elementos (`pasos/grafismo.py`) en su sitio, para cada formato.
- FONDOS: un fotograma del video, la imagen de un plano, DOS planos partidos
  por un rayo, una imagen subida, o una hecha con IA (se paga).
- DOS MANERAS de poner el texto (lo pidio el dueno, «dame ambas opciones»):
  en CAPAS, gratis y exacto, que es lo de por defecto; o la portada ENTERA
  hecha por la IA con el texto dentro (`prompt_portada_ia`), que se paga y
  puede escribir alguna letra mal.

Las zonas que tapa cada red (`ZONAS`) salen de la investigacion del 19-10
(docs del Proyecto, `investigacion/portadas_y_retencion`): en vertical, lo que
importa va en el cuadrado central y por encima del pie; en 16:9 la esquina de
abajo a la derecha la tapa la duracion del video.

Nada de aqui escribe params de ningun paso: el diseno vive en la carpeta de
Publicar (`<publicar>/portadas/<pid>.diseno.json`), fuera de toda firma, y la
portada hecha entra por `publicar.guardar_imagen_portada`, como una subida.
"""
import copy
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grafismo  # noqa: E402

VERSION = 1

FORMATOS = {"9:16": (1080, 1920), "16:9": (1280, 720), "4:5": (1080, 1350), "1:1": (1080, 1080)}

#: Lo que tapa cada red, en fracciones del cuadro: la pantalla lo dibuja como
#: guia y las plantillas dejan ahi solo lo que puede perderse.
ZONAS = {
    "9:16": [{"x": 0, "y": 0, "w": 1, "h": 0.14, "que": "arriba: la barra de la red"},
             {"x": 0, "y": 0.65, "w": 1, "h": 0.35, "que": "abajo: el texto del post y los botones"},
             {"x": 0.85, "y": 0.4, "w": 0.15, "h": 0.6, "que": "derecha: me gusta, comentar, compartir"}],
    "16:9": [{"x": 0.78, "y": 0.82, "w": 0.22, "h": 0.18, "que": "la duración del vídeo"}],
    "4:5": [],
    "1:1": [],
}

#: Paletas de miniatura (la investigacion del 19-10). acento = lo que salta.
PALETAS = {
    "impacto": {"nombre": "Impacto", "fondo": "#228fda", "acento": "#ffff00", "alerta": "#ff0000",
                "texto": "#ffffff", "contorno": "#000000"},
    "gamer": {"nombre": "Gamer / neón", "fondo": "#0d0221", "acento": "#00f0ff", "alerta": "#ff2bd6",
              "texto": "#ffffff", "contorno": "#000000"},
    "oferta": {"nombre": "Oferta", "fondo": "#e10600", "acento": "#ffd400", "alerta": "#e10600",
               "texto": "#ffffff", "contorno": "#000000"},
    "confianza": {"nombre": "Confianza", "fondo": "#0b1f3a", "acento": "#ff7a00", "alerta": "#ff7a00",
                  "texto": "#ffffff", "contorno": "#0b1f3a"},
    "fiesta": {"nombre": "Fiesta", "fondo": "#7b2ff7", "acento": "#ffc700", "alerta": "#00c2a8",
               "texto": "#ffffff", "contorno": "#2a0a5e"},
    "peru": {"nombre": "Fiestas Patrias / Navidad", "fondo": "#d91023", "acento": "#f5b700",
             "alerta": "#ffffff", "texto": "#ffffff", "contorno": "#5a0008"},
    "calido": {"nombre": "Cálido (diseño vs función)", "fondo": "#2b1d14", "acento": "#ff9a3c",
               "alerta": "#8a7dff", "texto": "#ffffff", "contorno": "#1a120c"},
}

#: Los textos que puede pedir una plantilla. La pantalla ensena solo los suyos.
CAMPOS_TEXTO = {
    "titulo": "Título (1–3 palabras)", "antetitulo": "Texto pequeño de arriba",
    "izquierda": "Lado izquierdo", "derecha": "Lado derecho",
    "numero": "Número", "etiqueta": "Etiqueta / precio", "insignia": "Insignia (VS, RETO, NUEVO)",
    "pie": "Texto de abajo",
}


def _p(formato, vertical, horizontal, cuadrado=None):
    """La posicion segun el formato: (x, y)."""
    if formato == "9:16":
        return vertical
    if formato == "16:9":
        return horizontal
    return cuadrado or (vertical[0], 0.18 + (vertical[1] - 0.15) * 0.75)


def _texto(t, campo, defecto=""):
    return str((t or {}).get(campo) or defecto).strip()


def _titulo(t, pal, fuente, x, y, tam=0.17, ancho=0.86, lineas=2, estilos=None, **extra):
    return dict({"tipo": "texto", "rol": "titulo", "texto": _texto(t, "titulo", "TU TÍTULO"),
                 "x": x, "y": y, "tam": tam, "ancho": ancho, "lineas": lineas, "fuente": fuente,
                 "color": pal["texto"], "contorno": pal["contorno"], "acento": pal["acento"],
                 "estilos": estilos or ["contorno", "sombra"]}, **extra)


def _ante(t, pal, fuente, x, y, tam=0.045, alinear="centro"):
    if not _texto(t, "antetitulo"):
        return None
    return {"tipo": "texto", "rol": "antetitulo", "texto": _texto(t, "antetitulo"), "x": x, "y": y,
            "tam": tam, "ancho": 0.7, "lineas": 1, "fuente": "bebas" if fuente != "bebas" else "anton",
            "color": pal["texto"], "contorno": pal["contorno"], "estilos": ["contorno"],
            "alinear": alinear}


# ------------------------------------------------------------------ plantillas
#
# Cada una: (fondo, elementos, efectos). `fondo` es la DISPOSICION del fondo:
# «uno» (una imagen), «diagonal», «vertical» u «horizontal» (dos partidas).

def _versus(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "rayo", "x": 0.56, "y": -0.02, "x2": 0.44, "y2": 1.02, "color": pal["alerta"], "tam": 0.012}
        if v else {"tipo": "rayo", "x": 0.53, "y": -0.05, "x2": 0.47, "y2": 1.05, "color": pal["alerta"], "tam": 0.014},
        {"tipo": "texto", "rol": "izquierda", "texto": _texto(t, "izquierda", "ESTO"),
         "x": 0.3 if v else 0.25, "y": 0.2 if v else 0.2, "tam": 0.15, "ancho": 0.55 if v else 0.45,
         "lineas": 1, "fuente": f, "color": pal["texto"], "contorno": pal["contorno"],
         "acento": pal["acento"], "estilos": ["contorno", "sombra", "brillo"], "rot": -4},
        {"tipo": "texto", "rol": "derecha", "texto": _texto(t, "derecha", "AQUELLO"),
         "x": 0.68 if v else 0.75, "y": 0.6 if v else 0.82, "tam": 0.15, "ancho": 0.6 if v else 0.45,
         "lineas": 1, "fuente": f, "color": pal["texto"], "contorno": pal["contorno"],
         "acento": pal["alerta"], "estilos": ["contorno", "sombra", "brillo"], "rot": -4},
        {"tipo": "insignia", "rol": "insignia", "texto": _texto(t, "insignia", "VS"), "x": 0.5,
         "y": 0.42 if v else 0.5, "tam": 0.13, "forma": "circulo", "color": "#e53935",
         "contorno": "#ffffff", "brillo": True, "fuente": f},
    ]
    if _texto(t, "antetitulo"):
        els.append(_ante(t, pal, f, 0.3 if v else 0.25, 0.155 if v else 0.08))
    return "diagonal", els, {"contraste": 1.12, "saturacion": 1.2, "vineta": 0.35}


def _antes_despues(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "etiqueta", "rol": "izquierda", "texto": _texto(t, "izquierda", "ANTES"),
         "x": 0.5 if v else 0.25, "y": 0.18 if v else 0.14, "tam": 0.06, "color": "#555555"},
        {"tipo": "etiqueta", "rol": "derecha", "texto": _texto(t, "derecha", "DESPUÉS"),
         "x": 0.5 if v else 0.75, "y": 0.5 if v else 0.14, "tam": 0.06, "color": pal["acento"]},
        {"tipo": "flecha", "x": 0.2 if v else 0.42, "y": 0.36 if v else 0.55, "x2": 0.3 if v else 0.58,
         "y2": 0.46 if v else 0.55, "tam": 0.028, "color": pal["alerta"], "curva": 0.3},
        _titulo(t, pal, f, 0.5, 0.6 if v else 0.84, tam=0.11, lineas=2),
    ]
    return ("horizontal" if v else "vertical"), els, {"contraste": 1.1, "saturacion": 1.15, "oscurecer": 0.3}


def _top(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "texto", "rol": "numero", "texto": _texto(t, "numero", "5"),
         "x": 0.28 if v else 0.2, "y": 0.3 if v else 0.5, "tam": 0.55 if v else 0.75, "ancho": 0.5,
         "lineas": 1, "fuente": f, "color": pal["acento"], "contorno": pal["contorno"],
         "estilos": ["contorno", "sombra", "extruido"]},
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.55), (0.62, 0.42))), tam=0.12,
                ancho=0.9 if v else 0.6, lineas=3),
    ]
    return "uno", els, {"contraste": 1.1, "saturacion": 1.2, "oscurecer": 0.35, "vineta": 0.3}


def _pregunta(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "texto", "rol": "decorado", "texto": "?", "x": 0.78 if v else 0.85,
         "y": 0.28 if v else 0.45, "tam": 0.5 if v else 0.8, "ancho": 0.4, "lineas": 1, "fuente": f,
         "color": pal["acento"], "contorno": pal["contorno"], "estilos": ["contorno", "sombra"], "rot": 12},
        _titulo(t, pal, f, *(_p(fmt, (0.45, 0.33), (0.4, 0.5))), tam=0.13,
                ancho=0.8 if v else 0.62, lineas=3, resaltar=[_texto(t, "titulo").split(" ")[-1]]),
    ]
    return "uno", els, {"contraste": 1.1, "oscurecer": 0.3, "vineta": 0.4}


def _oferta(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "rafaga", "x": 0.5, "y": 0.35 if v else 0.5, "color": "#ffffff", "opacidad": 0.14},
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.2), (0.32, 0.3))), tam=0.12, ancho=0.86 if v else 0.6),
        {"tipo": "insignia", "rol": "etiqueta", "texto": _texto(t, "etiqueta", "S/ 99"),
         "x": 0.5 if v else 0.75, "y": 0.42 if v else 0.55, "tam": 0.17, "forma": "estallido",
         "color": pal["alerta"] if pal["alerta"] != "#ffffff" else "#e10600", "contorno": "#ffffff",
         "color_texto": "#ffd400", "fuente": f},
    ]
    if _texto(t, "pie"):
        els.append({"tipo": "texto", "rol": "pie", "texto": _texto(t, "pie"), "x": 0.5 if v else 0.32,
                    "y": 0.58 if v else 0.62, "tam": 0.06, "ancho": 0.8 if v else 0.5, "lineas": 1,
                    "fuente": f, "color": pal["texto"], "contorno": pal["contorno"],
                    "estilos": ["contorno", "tachado"]})
    return "uno", els, {"contraste": 1.15, "saturacion": 1.25, "vineta": 0.3}


def _dato(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "texto", "rol": "numero", "texto": _texto(t, "numero", "300"), "x": 0.5,
         "y": 0.3 if v else 0.42, "tam": 0.32, "ancho": 0.9, "lineas": 1, "fuente": f,
         "color": pal["acento"], "contorno": pal["contorno"], "acento": pal["acento"],
         "estilos": ["contorno", "brillo", "sombra"]},
        _titulo(t, pal, f, 0.5, 0.47 if v else 0.75, tam=0.08, ancho=0.86, lineas=2),
    ]
    return "uno", els, {"contraste": 1.1, "oscurecer": 0.45, "vineta": 0.45}


def _error(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.2), (0.35, 0.28))), tam=0.13, ancho=0.86 if v else 0.6,
                resaltar=["NO"]),
        {"tipo": "icono", "icono": "cruz", "x": 0.72 if v else 0.78, "y": 0.42 if v else 0.55,
         "tam": 0.13},
        {"tipo": "circulo", "x": 0.5 if v else 0.6, "y": 0.45 if v else 0.6, "tam": 0.22, "color": "#ff1f1f"},
    ]
    return "uno", els, {"contraste": 1.12, "vineta": 0.35}


def _tutorial(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        _ante(t, pal, f, 0.5 if v else 0.3, 0.16 if v else 0.14) or
        {"tipo": "etiqueta", "rol": "antetitulo", "texto": "CÓMO", "x": 0.5 if v else 0.2,
         "y": 0.16 if v else 0.15, "tam": 0.06, "color": pal["acento"]},
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.3), (0.34, 0.45))), tam=0.14, ancho=0.86 if v else 0.6,
                lineas=3),
        {"tipo": "flecha", "x": 0.3 if v else 0.6, "y": 0.45 if v else 0.75, "x2": 0.5 if v else 0.75,
         "y2": 0.55 if v else 0.6, "tam": 0.025, "color": pal["alerta"]},
    ]
    return "uno", els, {"contraste": 1.1, "oscurecer": 0.3}


def _pasos(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [_titulo(t, pal, f, *(_p(fmt, (0.5, 0.18), (0.5, 0.18))), tam=0.11, ancho=0.86)]
    for i in range(3):
        x = (0.25 + i * 0.25) if v else (0.22 + i * 0.28)
        y = (0.38 + i * 0.07) if v else (0.55 + i * 0.08)
        els.append({"tipo": "insignia", "texto": str(i + 1), "x": x, "y": y, "tam": 0.07,
                    "forma": "circulo", "color": pal["acento"], "contorno": "#ffffff", "fuente": f})
    return "uno", els, {"contraste": 1.1, "oscurecer": 0.35}


def _testimonio(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "texto", "rol": "decorado", "texto": "“", "x": 0.18 if v else 0.1, "y": 0.2 if v else 0.3,
         "tam": 0.4, "ancho": 0.3, "lineas": 1, "fuente": "luckiest", "color": pal["acento"],
         "contorno": pal["contorno"], "estilos": ["contorno"], "mayusculas": False},
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.28), (0.45, 0.45))), tam=0.11, ancho=0.82 if v else 0.6,
                lineas=3),
        {"tipo": "estrellas", "x": 0.5 if v else 0.45, "y": 0.45 if v else 0.75, "tam": 0.045, "valor": 5},
    ]
    return "uno", els, {"contraste": 1.08, "oscurecer": 0.4}


def _secreto(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.18), (0.32, 0.25))), tam=0.12, ancho=0.86 if v else 0.55,
                lineas=2),
        {"tipo": "circulo", "x": 0.6 if v else 0.7, "y": 0.45 if v else 0.55, "tam": 0.16, "color": pal["alerta"]},
        {"tipo": "flecha", "x": 0.2 if v else 0.35, "y": 0.35 if v else 0.6, "x2": 0.45 if v else 0.55,
         "y2": 0.43 if v else 0.58, "tam": 0.026, "color": "#ff1f1f"},
    ]
    return "uno", els, {"contraste": 1.12, "vineta": 0.5}


def _desafio(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "insignia", "rol": "insignia", "texto": _texto(t, "insignia", "RETO"),
         "x": 0.75 if v else 0.85, "y": 0.15 if v else 0.2, "tam": 0.11, "forma": "estallido",
         "color": pal["alerta"], "contorno": "#ffffff", "fuente": f},
        _titulo(t, pal, f, *(_p(fmt, (0.45, 0.32), (0.38, 0.5))), tam=0.15, ancho=0.82 if v else 0.6,
                estilos=["contorno", "sombra", "inclinado"]),
        {"tipo": "icono", "icono": "reloj", "x": 0.2 if v else 0.1, "y": 0.47 if v else 0.82, "tam": 0.07},
    ]
    return "uno", els, {"contraste": 1.15, "saturacion": 1.2, "vineta": 0.35}


def _precios(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "etiqueta", "rol": "izquierda", "texto": _texto(t, "izquierda", "COMPRAR S/ 2000"),
         "x": 0.5 if v else 0.27, "y": 0.22 if v else 0.3, "tam": 0.06, "color": "#555555", "rot": 0},
        {"tipo": "etiqueta", "rol": "derecha", "texto": _texto(t, "derecha", "ALQUILAR S/ 99"),
         "x": 0.5 if v else 0.73, "y": 0.42 if v else 0.3, "tam": 0.075, "color": pal["acento"], "rot": -4},
        {"tipo": "icono", "icono": "check", "x": 0.85 if v else 0.92, "y": 0.42 if v else 0.3, "tam": 0.06},
        _titulo(t, pal, f, 0.5, 0.56 if v else 0.75, tam=0.1, ancho=0.86),
    ]
    return "uno", els, {"contraste": 1.1, "oscurecer": 0.35}


def _urgencia(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "cinta", "texto": _texto(t, "insignia", "ÚLTIMOS DÍAS"), "esquina": "si",
         "color": pal["alerta"] if pal["alerta"] != "#ffffff" else "#e10600"},
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.3), (0.42, 0.45))), tam=0.14, ancho=0.86 if v else 0.62),
        {"tipo": "icono", "icono": "reloj", "x": 0.5 if v else 0.85, "y": 0.5 if v else 0.45, "tam": 0.08},
    ]
    return "uno", els, {"contraste": 1.15, "vineta": 0.5}


def _resultado(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "texto", "rol": "numero", "texto": _texto(t, "numero", "+40"), "x": 0.5 if v else 0.3,
         "y": 0.28 if v else 0.45, "tam": 0.26, "ancho": 0.8 if v else 0.5, "lineas": 1, "fuente": f,
         "color": "#22c55e", "contorno": pal["contorno"], "estilos": ["contorno", "sombra"]},
        {"tipo": "flecha", "x": 0.15 if v else 0.1, "y": 0.5 if v else 0.85, "x2": 0.85 if v else 0.5,
         "y2": 0.38 if v else 0.6, "tam": 0.03, "color": "#22c55e", "curva": -0.15},
        _titulo(t, pal, f, 0.5 if v else 0.7, 0.5 if v else 0.45, tam=0.09, ancho=0.86 if v else 0.5),
    ]
    return "uno", els, {"contraste": 1.1, "oscurecer": 0.35}


def _detras(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "etiqueta", "texto": "● REC", "x": 0.2 if v else 0.1, "y": 0.17 if v else 0.1,
         "tam": 0.045, "color": "#111111", "color_texto": "#ff2d2d", "rot": 0},
        _titulo(t, pal, "marker", *(_p(fmt, (0.5, 0.3), (0.4, 0.75))), tam=0.11, ancho=0.86 if v else 0.7,
                lineas=2, estilos=["sombra"], mayusculas=False),
        {"tipo": "marco", "tam": 0.012, "color": "#ffffff"},
    ]
    return "uno", els, {"saturacion": 0.85, "vineta": 0.4}


def _mito(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "texto", "rol": "izquierda", "texto": _texto(t, "izquierda", "MITO"),
         "x": 0.5 if v else 0.25, "y": 0.2 if v else 0.3, "tam": 0.11, "ancho": 0.8 if v else 0.45,
         "lineas": 1, "fuente": f, "color": "#ff4d4d", "contorno": "#000000",
         "estilos": ["contorno", "tachado"]},
        {"tipo": "texto", "rol": "derecha", "texto": _texto(t, "derecha", "REALIDAD"),
         "x": 0.5 if v else 0.75, "y": 0.4 if v else 0.3, "tam": 0.11, "ancho": 0.8 if v else 0.45,
         "lineas": 1, "fuente": f, "color": "#22c55e", "contorno": "#000000",
         "estilos": ["contorno", "sombra"]},
        _titulo(t, pal, f, 0.5, 0.55 if v else 0.75, tam=0.08, ancho=0.86),
    ]
    return ("horizontal" if v else "vertical"), els, {"contraste": 1.1, "oscurecer": 0.3}


def _evento(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        {"tipo": "insignia", "rol": "insignia", "texto": _texto(t, "insignia", "28 JUL"),
         "x": 0.8 if v else 0.86, "y": 0.18 if v else 0.2, "tam": 0.1, "forma": "escudo",
         "color": pal["acento"], "contorno": "#ffffff", "fuente": f},
        _titulo(t, pal, f, *(_p(fmt, (0.45, 0.32), (0.4, 0.5))), tam=0.14, ancho=0.82 if v else 0.62,
                estilos=["contorno", "sombra", "brillo"]),
        {"tipo": "rafaga", "x": 0.5, "y": 0.45, "opacidad": 0.1},
    ]
    return "uno", els, {"contraste": 1.12, "saturacion": 1.25, "vineta": 0.4}


def _escala(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.22), (0.5, 0.2))), tam=0.14, ancho=0.9, lineas=2,
                estilos=["contorno", "sombra", "extruido"]),
        {"tipo": "icono", "icono": "fuego", "x": 0.15 if v else 0.1, "y": 0.4 if v else 0.75, "tam": 0.07},
        {"tipo": "icono", "icono": "fuego", "x": 0.85 if v else 0.9, "y": 0.4 if v else 0.75, "tam": 0.07},
    ]
    return "uno", els, {"contraste": 1.15, "saturacion": 1.3, "vineta": 0.3}


def _reaccion(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [
        _titulo(t, pal, f, *(_p(fmt, (0.5, 0.2), (0.7, 0.3))), tam=0.14, ancho=0.86 if v else 0.5,
                estilos=["contorno", "sombra", "inclinado"]),
        {"tipo": "icono", "icono": "exclamacion", "x": 0.82 if v else 0.9, "y": 0.4 if v else 0.62,
         "tam": 0.07},
        {"tipo": "flecha", "x": 0.75 if v else 0.62, "y": 0.42 if v else 0.6, "x2": 0.55 if v else 0.45,
         "y2": 0.5 if v else 0.65, "tam": 0.025, "color": "#ff1f1f"},
    ]
    return "uno", els, {"contraste": 1.15, "saturacion": 1.25, "vineta": 0.35}


def _titular(t, pal, f, fmt):
    v = fmt == "9:16"
    els = [_ante(t, pal, f, 0.5, 0.17 if v else 0.2),
           _titulo(t, pal, f, 0.5, 0.3 if v else 0.55, tam=0.17, ancho=0.88, lineas=3,
                   resaltar=[_texto(t, "titulo").split(" ")[-1]] if _texto(t, "titulo") else [])]
    return "uno", [e for e in els if e], {"contraste": 1.1, "saturacion": 1.15, "oscurecer": 0.35}


#: id -> (nombre, cuando usarla, campos de texto que pide, funcion)
PLANTILLAS = {
    "titular": ("Titular", "Un título grande y claro: vale para casi todo", ["antetitulo", "titulo"], _titular),
    "versus": ("Versus", "Comparar dos opciones (como «diseño vs función»)",
               ["izquierda", "derecha", "insignia", "antetitulo"], _versus),
    "antes_despues": ("Antes / Después", "Una transformación o el resultado de un servicio",
                      ["izquierda", "derecha", "titulo"], _antes_despues),
    "top": ("Top N", "Listas: un número enorme y lo que cuentas", ["numero", "titulo"], _top),
    "pregunta": ("Pregunta", "Las dudas del cliente («¿Cuánto cuesta?»)", ["titulo"], _pregunta),
    "oferta": ("Precio / Oferta", "Promociones con el precio en una pegatina", ["titulo", "etiqueta", "pie"], _oferta),
    "dato": ("Dato impactante", "Una cifra gigante con su contexto", ["numero", "titulo"], _dato),
    "error": ("Error común", "Lo que NO hay que hacer, con una X roja", ["titulo"], _error),
    "tutorial": ("Tutorial / Cómo", "Guías: «cómo» y el resultado", ["antetitulo", "titulo"], _tutorial),
    "pasos": ("Lista de pasos", "Procesos en 1-2-3", ["titulo"], _pasos),
    "testimonio": ("Testimonio", "Lo que dice un cliente, con cinco estrellas", ["titulo"], _testimonio),
    "secreto": ("Curiosidad / secreto", "«Nadie te dice esto»: círculo y flecha", ["titulo"], _secreto),
    "desafio": ("Desafío", "Retos y eventos, con su insignia", ["titulo", "insignia"], _desafio),
    "precios": ("Comparativa de precios", "Comprar vs alquilar, plan A vs plan B", ["izquierda", "derecha", "titulo"], _precios),
    "urgencia": ("Cuenta atrás / Urgencia", "Fechas límite, últimos cupos", ["titulo", "insignia"], _urgencia),
    "resultado": ("Resultado / logro", "Casos de éxito con la cifra en verde", ["numero", "titulo"], _resultado),
    "detras": ("Detrás de cámaras", "Humanizar la marca: REC y letra a mano", ["titulo"], _detras),
    "mito": ("Mito vs realidad", "Desmentir algo", ["izquierda", "derecha", "titulo"], _mito),
    "evento": ("Evento / temporada", "Navidad, Fiestas Patrias, Halloween", ["titulo", "insignia"], _evento),
    "escala": ("Escala / tamaño", "Impresionar con el volumen («10 pantallas, 1 fiesta»)", ["titulo"], _escala),
    "reaccion": ("Reacción", "Sorpresa: título inclinado, exclamación y flecha", ["titulo"], _reaccion),
}

FONDOS = ("fotograma", "plano", "subida", "ia")
DISPOSICIONES = ("uno", "diagonal", "vertical", "horizontal")


def catalogo():
    """Todo lo que la pantalla necesita para ofrecer opciones."""
    return {
        "plantillas": [{"id": k, "nombre": v[0], "cuando": v[1], "campos": v[2]} for k, v in PLANTILLAS.items()],
        "campos": CAMPOS_TEXTO,
        "paletas": [dict(v, id=k) for k, v in PALETAS.items()],
        "fuentes": grafismo.fuentes_estado(),
        "elementos": grafismo.ELEMENTOS,
        "estilos_texto": grafismo.ESTILOS_TEXTO,
        "iconos": list(grafismo.ICONOS),
        "formatos": {k: {"ancho": v[0], "alto": v[1], "zonas": ZONAS[k]} for k, v in FORMATOS.items()},
        "fondos": list(FONDOS),
        "disposiciones": list(DISPOSICIONES),
    }


# ------------------------------------------------------------------ el diseno

def formato_de_video(formato_video):
    return "9:16" if str(formato_video or "") == "vertical" else "16:9"


def de_plantilla(plantilla, textos=None, paleta="gamer", fuente="anton", formato="9:16",
                 fondo=None, base=None):
    """Un diseno nuevo desde una plantilla. Si se pasa `base` (el de antes), se
    conserva su fondo y sus textos: cambiar de plantilla no borra lo escrito."""
    plantilla = plantilla if plantilla in PLANTILLAS else "titular"
    formato = formato if formato in FORMATOS else "9:16"
    paleta = paleta if paleta in PALETAS else "gamer"
    fuente = fuente if fuente in grafismo.FUENTES else "anton"
    base = normalizar(base) if base else None
    textos = dict((base or {}).get("textos") or {}, **{k: v for k, v in (textos or {}).items() if v is not None})
    disposicion, elementos, efectos = PLANTILLAS[plantilla][3](textos, PALETAS[paleta], fuente, formato)
    fondo_previo = dict((base or {}).get("fondo") or {})
    fondo_nuevo = dict(fondo_previo, **(fondo or {}))
    fondo_nuevo["disposicion"] = disposicion
    return normalizar({
        "version": VERSION, "plantilla": plantilla, "formato": formato, "paleta": paleta,
        "fuente": fuente, "textos": textos, "fondo": fondo_nuevo,
        "elementos": [e for e in elementos if e], "efectos": efectos,
    })


def _limpiar_textos(textos):
    return {k: str(v or "")[:80] for k, v in (textos or {}).items() if k in CAMPOS_TEXTO}


def _limpiar_fondo(fondo):
    fondo = fondo if isinstance(fondo, dict) else {}
    salida = {"tipo": fondo.get("tipo") if fondo.get("tipo") in FONDOS else "fotograma",
              "disposicion": fondo.get("disposicion") if fondo.get("disposicion") in DISPOSICIONES else "uno"}
    try:
        salida["ms"] = max(0, int(fondo.get("ms") or 0))
    except (TypeError, ValueError):
        salida["ms"] = 0
    planos = [str(p)[:20] for p in (fondo.get("planos") or []) if re.match(r"^[A-Za-z0-9_-]{1,20}$", str(p))]
    salida["planos"] = planos[:2]
    for clave in ("imagen", "imagen2"):
        nombre = str(fondo.get(clave) or "")
        if re.match(r"^[a-z0-9_.-]{1,80}$", nombre) and ".." not in nombre:
            salida[clave] = nombre
    for clave in ("ms2",):
        try:
            salida[clave] = max(0, int(fondo.get(clave) or 0))
        except (TypeError, ValueError):
            pass
    foco = str(fondo.get("foco") or "")
    if foco in ("xMidYMid", "xMinYMid", "xMaxYMid", "xMidYMin", "xMidYMax"):
        salida["foco"] = foco
    return salida


def _limpiar_efectos(efectos):
    efectos = efectos if isinstance(efectos, dict) else {}
    salida = {}
    for clave, (minimo, maximo) in {"contraste": (0.5, 1.8), "saturacion": (0, 2), "brillo": (0.5, 1.6),
                                    "vineta": (0, 1), "oscurecer": (0, 1)}.items():
        if clave in efectos:
            try:
                salida[clave] = round(max(minimo, min(maximo, float(efectos[clave]))), 3)
            except (TypeError, ValueError):
                pass
    return salida


def normalizar(diseno):
    """El diseno validado (de la pantalla, de Claude o del disco). Nunca lanza."""
    d = diseno if isinstance(diseno, dict) else {}
    return {
        "version": VERSION,
        "plantilla": d.get("plantilla") if d.get("plantilla") in PLANTILLAS else "titular",
        "formato": d.get("formato") if d.get("formato") in FORMATOS else "9:16",
        "paleta": d.get("paleta") if d.get("paleta") in PALETAS else "gamer",
        "fuente": d.get("fuente") if d.get("fuente") in grafismo.FUENTES else "anton",
        "textos": _limpiar_textos(d.get("textos")),
        "fondo": _limpiar_fondo(d.get("fondo")),
        "elementos": grafismo.limpiar_elementos(d.get("elementos")),
        "efectos": _limpiar_efectos(d.get("efectos")),
        "modo": "ia" if d.get("modo") == "ia" else "capas",
    }


def aplicar_textos(diseno, textos):
    """Pone los textos nuevos en los elementos que tienen ese papel (`rol`),
    sin mover nada de lo retocado a mano."""
    d = normalizar(diseno)
    d["textos"].update(_limpiar_textos(textos))
    for el in d["elementos"]:
        rol = el.get("rol")
        if rol in d["textos"] and d["textos"][rol]:
            el["texto"] = d["textos"][rol]
    return d


# ------------------------------------------------------------------ el disco

def carpeta(raiz_publicar):
    return os.path.join(raiz_publicar, "portadas")


def ruta_diseno(raiz_publicar, pid):
    if not re.match(r"^[A-Za-z0-9_-]{1,80}$", str(pid)):
        raise ValueError("vídeo desconocido")
    return os.path.join(carpeta(raiz_publicar), f"{pid}.diseno.json")


def leer(raiz_publicar, pid):
    """El diseno guardado, o None."""
    try:
        with open(ruta_diseno(raiz_publicar, pid), encoding="utf-8") as fh:
            return normalizar(json.load(fh))
    except (OSError, ValueError):
        return None


def guardar(raiz_publicar, pid, diseno):
    d = normalizar(diseno)
    ruta = ruta_diseno(raiz_publicar, pid)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    temporal = f"{ruta}.{os.getpid()}.tmp"
    with open(temporal, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(temporal, ruta)
    return d


def nombre_fondo(pid, contenido, extension=".png"):
    return f"{pid.lower()}_fondo_{hashlib.sha1(contenido).hexdigest()[:10]}{extension}"


def ruta_fondo(raiz_publicar, nombre):
    if not re.match(r"^[a-z0-9_.-]{1,80}$", str(nombre)) or ".." in str(nombre):
        raise ValueError("ese fondo no existe")
    return os.path.join(carpeta(raiz_publicar), "fondos", nombre)


# ------------------------------------------------------------------ componer

def _fondo_svg(diseno, rutas, W, H, uid):
    """El fondo: una imagen o dos partidas. `rutas` son 1 o 2 ficheros."""
    filtro_def, filtro = grafismo.efectos_de_imagen(uid, diseno.get("efectos"))
    rutas = [r for r in rutas if r and os.path.isfile(r)]
    if not rutas:
        return f"<defs>{filtro_def}</defs>" if filtro_def else ""
    foco = (diseno.get("fondo") or {}).get("foco") or "xMidYMid"
    disposicion = (diseno.get("fondo") or {}).get("disposicion") or "uno"
    a = grafismo.data_uri(rutas[0])
    b = grafismo.data_uri(rutas[1]) if len(rutas) > 1 else a
    piezas = [f"<defs>{filtro_def}"]
    if disposicion == "uno" or len(rutas) == 1 and disposicion == "uno":
        piezas.append("</defs>")
        piezas.append(grafismo.imagen_cubre(a, 0, 0, W, H, filtro, foco))
        return "".join(piezas)
    if disposicion == "diagonal":
        izq = f"0,0 {W * 0.58:.1f},0 {W * 0.42:.1f},{H} 0,{H}"
        der = f"{W * 0.58:.1f},0 {W},0 {W},{H} {W * 0.42:.1f},{H}"
        piezas.append(f'<clipPath id="{uid}-a"><polygon points="{izq}"/></clipPath>'
                      f'<clipPath id="{uid}-b"><polygon points="{der}"/></clipPath></defs>')
        piezas.append(f'<g clip-path="url(#{uid}-a)">{grafismo.imagen_cubre(a, 0, 0, W * 0.62, H, filtro)}</g>')
        piezas.append(f'<g clip-path="url(#{uid}-b)">{grafismo.imagen_cubre(b, W * 0.38, 0, W * 0.62, H, filtro)}</g>')
        return "".join(piezas)
    if disposicion == "vertical":
        piezas.append("</defs>")
        piezas.append(grafismo.imagen_cubre(a, 0, 0, W / 2, H, filtro))
        piezas.append(grafismo.imagen_cubre(b, W / 2, 0, W / 2, H, filtro))
        piezas.append(f'<rect x="{W / 2 - 4:.0f}" y="0" width="8" height="{H}" fill="#ffffff"/>')
        return "".join(piezas)
    piezas.append("</defs>")
    piezas.append(grafismo.imagen_cubre(a, 0, 0, W, H / 2, filtro))
    piezas.append(grafismo.imagen_cubre(b, 0, H / 2, W, H / 2, filtro))
    piezas.append(f'<rect x="0" y="{H / 2 - 4:.0f}" width="{W}" height="8" fill="#ffffff"/>')
    return "".join(piezas)


def componer(diseno, rutas_fondo):
    """El SVG de la portada a su tamano de verdad. -> (svg, W, H)"""
    d = normalizar(diseno)
    W, H = FORMATOS[d["formato"]]
    uid = "p" + hashlib.sha1(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    fondo = _fondo_svg(d, list(rutas_fondo or []), W, H, uid)
    paleta = PALETAS[d["paleta"]]
    svg = grafismo.lienzo(W, H, fondo, d["elementos"], d["efectos"], fondo_color=paleta["fondo"])
    return svg, W, H


def renderizar(diseno, rutas_fondo, destino, ancho_vista=0):
    """La portada en PNG. Con `ancho_vista` sale reducida (para la pantalla)."""
    import medios                                             # noqa: PLC0415
    svg, W, H = componer(diseno, rutas_fondo)
    escala = (float(ancho_vista) / W) if ancho_vista and ancho_vista < W else 1.0
    w, h = int(round(W * escala)), int(round(H * escala))
    if escala != 1.0:
        svg = svg.replace(f'width="{W}" height="{H}"', f'width="{w}" height="{h}"', 1)
    # EL NAVEGADOR SIN CABEZA DEJA UNA FRANJA ABAJO en algunas versiones (la
    # ventana es mayor que lo que pinta): se pide mas alto y se recorta.
    medios.rasterizar(svg, destino, w, h + 160, transparente=False, espera_ms=1200)
    try:
        from PIL import Image                                 # noqa: PLC0415
        with Image.open(destino) as im:
            recorte = im.convert("RGB").crop((0, 0, w, h))
        temporal = destino + ".tmp.png"
        recorte.save(temporal, "PNG")
        os.replace(temporal, destino)
    except Exception:                                         # noqa: BLE001
        pass
    return destino


# ------------------------------------------------------------------ con Claude

INSTRUCCION_PROPONER = """Eres director de arte de miniaturas para redes (YouTube, Instagram, TikTok).
Propón {n} portadas DISTINTAS para este vídeo de un negocio. Cada una con una
plantilla diferente si tiene sentido, textos MUY cortos (1–3 palabras por
campo, en mayúsculas, en el idioma del vídeo, sin repetir el título del post
palabra por palabra), una paleta y una fuente.

<video>
Título del post: {titulo}
Palabras clave: {palabras}
Resumen del guion: {resumen}
Negocio: {negocio}
</video>

Plantillas (id: cuándo · campos que usa):
{plantillas}

Paletas: {paletas}
Fuentes: {fuentes}

Contesta SOLO con este JSON:
{{"propuestas": [{{"plantilla": "<id>", "paleta": "<id>", "fuente": "<id>",
  "textos": {{"<campo>": "<texto>"}}, "por_que": "<una frase>"}}]}}"""


def instruccion_proponer(info, n=3):
    plantillas = "\n".join(f"- {k}: {v[1]} · {', '.join(v[2])}" for k, v in PLANTILLAS.items())
    return INSTRUCCION_PROPONER.format(
        n=n, titulo=str(info.get("titulo") or "")[:200],
        palabras=", ".join(str(p) for p in (info.get("palabras") or [])[:10]),
        resumen=" ".join(str(info.get("resumen") or "").split())[:1500],
        negocio=str(info.get("negocio") or "")[:300], plantillas=plantillas,
        paletas=", ".join(PALETAS), fuentes=", ".join(k for k in grafismo.FUENTES if k != "sistema"))


def leer_propuestas(datos, formato, base=None, n=3):
    """Las propuestas de Claude, validadas y convertidas en disenos completos."""
    salida = []
    for p in ((datos or {}).get("propuestas") or [])[:n * 3]:
        if len(salida) >= n:
            break
        if not isinstance(p, dict) or p.get("plantilla") not in PLANTILLAS:
            continue
        textos = _limpiar_textos(p.get("textos"))
        diseno = de_plantilla(p["plantilla"], textos, p.get("paleta"), p.get("fuente"), formato, base=base)
        salida.append({"diseno": diseno, "por_que": str(p.get("por_que") or "")[:200]})
    return salida


def proponer(info, formato, base=None, n=3, cwd=None):
    """Tres portadas propuestas por Claude (suscripcion, no se paga aparte)."""
    import cli_claude                                         # noqa: PLC0415
    import comun                                              # noqa: PLC0415
    texto, _sobre = cli_claude.ejecutar(
        instruccion_proponer(info, n), modelo="sonnet", esfuerzo="low", cwd=cwd,
        base_tiempo_s=180, extra=["--no-session-persistence"], para="las portadas propuestas")
    datos = comun.extraer_json(texto, "las portadas propuestas")
    propuestas = leer_propuestas(datos, formato, base=base, n=n)
    if not propuestas:
        raise RuntimeError("Claude no ha propuesto ninguna portada que se pueda usar; vuelve a pedirlo")
    return propuestas


# ------------------------------------------------------------------ con la IA de imagenes

TAMANO_IA = {"9:16": "vertical", "16:9": "apaisado", "4:5": "vertical", "1:1": "cuadrado"}


def prompt_fondo_ia(diseno, info):
    """El fondo hecho por la IA, SIN texto, con sitio para el titulo."""
    d = normalizar(diseno)
    sitio = {"9:16": "the upper half", "16:9": "the left side", "4:5": "the upper part", "1:1": "the top"}[d["formato"]]
    return (f"Eye-catching background for a social media cover about: "
            f"{' '.join(str(info.get('resumen') or info.get('titulo') or '').split())[:600]}. "
            f"Bold, vivid colors, strong contrast, a single clear subject, cinematic light. "
            f"Leave clean empty space in {sitio} for a big headline added later. "
            f"ABSOLUTELY NO text, letters, numbers, logos or watermarks in the image.")


def prompt_portada_ia(diseno, info):
    """LA OTRA OPCION: la portada entera con el texto dentro, hecha por la IA.
    Se paga y puede escribir alguna letra mal: la pantalla lo dice."""
    d = normalizar(diseno)
    nombre = PLANTILLAS[d["plantilla"]][0]
    textos = [v for k, v in d["textos"].items() if v]
    comillas = " / ".join(f'"{t}"' for t in textos) or f'"{info.get("titulo") or ""}"'
    pal = PALETAS[d["paleta"]]
    return (f"High click-through social media thumbnail, style «{nombre}», for: "
            f"{' '.join(str(info.get('resumen') or info.get('titulo') or '').split())[:500]}. "
            f"Render EXACTLY this text, spelled exactly as written including accents and Ñ: {comillas}. "
            f"Huge bold condensed letters with thick black outline and drop shadow, "
            f"colors {pal['acento']} and {pal['texto']} over a {pal['fondo']} mood, "
            f"high contrast, punchy saturated look, readable at small size, no other text, no watermark.")

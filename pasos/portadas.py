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
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grafismo  # noqa: E402

VERSION = 1

FORMATOS = {"9:16": (1080, 1920), "16:9": (1280, 720), "4:5": (1080, 1350), "1:1": (1080, 1080)}

#: Lo que tapa cada red, en fracciones del cuadro: la pantalla lo dibuja como
#: guia y las plantillas dejan ahi solo lo que puede perderse.
ZONAS = {
    "9:16": [{"x": 0, "y": 0, "w": 1, "h": 0.14, "que": "arriba: la barra de la red"},
             {"x": 0, "y": 0.65, "w": 1, "h": 0.35, "que": "abajo: el texto del post y los botones"},
             {"x": 0.85, "y": 0.4, "w": 0.15, "h": 0.6, "que": "derecha: me gusta, comentar, compartir"},
             # la cuadrícula del perfil de Instagram enseña el centro en 3:4:
             # lo de fuera de este marco no se ve ahí (21-10)
             {"x": 0, "y": 0.125, "w": 1, "h": 0.75, "que": "Instagram, en la cuadrícula: solo esto (3:4)",
              "marco": True}],
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
    # SIN PALETA (portadas-2, 21-10): texto blanco con borde negro y nada que
    # resalte en color. Para quien no quiere que los colores los elija nadie.
    "ninguna": {"nombre": "Sin paleta (blanco y negro)", "fondo": "#111111", "acento": "#ffffff",
                "alerta": "#000000", "texto": "#ffffff", "contorno": "#000000"},
}

#: Lo que hace cada capa, para decirlo en la pantalla (portadas-2, 21-10).
CAPAS = {
    "imagen": "La imagen de fondo y, si quieres, sus ajustes (contraste, color, brillo, viñeta, "
              "oscurecer). Es lo ÚNICO que toca la foto, y empieza sin ajustes: tal cual llega.",
    "plantilla": "Dónde va cada texto y cada elemento. No toca la foto.",
    "paleta": "Los colores de los textos y los elementos (título, resaltado, insignias, flechas). "
              "No toca la foto. «Sin paleta»: blanco con borde negro.",
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
    # SIEMPRE EXISTE, aunque esté vacío (portadas-2, 21-10): antes solo se
    # creaba si ya tenía texto al elegir la plantilla, y lo que se escribía
    # después no tenía dónde salir. Vacío no pinta nada.
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
        {"tipo": "rafaga", "rol": "look", "oculto": True, "x": 0.5, "y": 0.35 if v else 0.5, "color": "#ffffff", "opacidad": 0.14},
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
        _ante(t, pal, f, 0.5 if v else 0.3, 0.16 if v else 0.14) if _texto(t, "antetitulo") else
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
        {"tipo": "marco", "rol": "look", "oculto": True, "tam": 0.012, "color": "#ffffff"},
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
        {"tipo": "rafaga", "rol": "look", "oculto": True, "x": 0.5, "y": 0.45, "opacidad": 0.1},
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
        "capas": CAPAS,
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
    disposicion, elementos, look = PLANTILLAS[plantilla][3](textos, PALETAS[paleta], fuente, formato)
    # QUÉ PAPEL TIENE CADA COLOR: la misma plantilla con una paleta de marcas
    # dice qué color salió de qué papel (dos papeles pueden valer lo mismo,
    # como en «Sin paleta», y por valor no se distinguen)
    marcas = {k: f"@{k}" for k in grafismo.PAPELES_PALETA}
    marcas["nombre"] = ""
    _d, con_marcas, _l = PLANTILLAS[plantilla][3](textos, marcas, fuente, formato)
    fondo_previo = dict((base or {}).get("fondo") or {})
    fondo_nuevo = dict(fondo_previo, **(fondo or {}))
    fondo_nuevo["disposicion"] = disposicion
    # LA IMAGEN, LIMPIA (portadas-2, 21-10): la plantilla ya no mete efectos en
    # la foto. Los suyos quedan como «look» que se aplica con un botón; los
    # ajustes que la persona ya puso se quedan al cambiar de plantilla.
    efectos = dict((base or {}).get("efectos") or {})
    nuevos = []
    for el, marcado in zip(elementos, con_marcas):
        if el:
            el = dict(el)
            # (y solo si de verdad salió de ese papel: hay plantillas que, si
            # el papel no les vale, ponen un color fijo)
            papeles = {c: str(marcado.get(c))[1:] for c in grafismo.CAMPOS_COLOR
                       if str((marcado or {}).get(c) or "").startswith("@")
                       and el.get(c) == PALETAS[paleta][str(marcado.get(c))[1:]]}
            # siempre, aunque vacío: un color de la plantilla que no es de
            # ningún papel (el rojo de la «X») es fijo y no se repinta
            el["papeles"] = papeles
            # «Restablecer» no vuelve a esconder lo que se enseñó a propósito
            el["orig"] = {k: v for k, v in el.items() if k not in ("texto", "orig", "oculto")}
            nuevos.append(el)
    # LO AÑADIDO A MANO SE QUEDA al cambiar de plantilla
    propios = [e for e in (base or {}).get("elementos") or [] if e.get("propio")]
    return normalizar({
        "version": VERSION, "plantilla": plantilla, "formato": formato, "paleta": paleta,
        "fuente": fuente, "textos": textos, "fondo": fondo_nuevo,
        "elementos": (nuevos + propios)[:grafismo.MAX_ELEMENTOS], "efectos": efectos, "look": look,
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
        if re.match(r"^[a-z0-9_.-]{1,120}$", nombre) and ".." not in nombre:
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
        "look": _limpiar_efectos(d.get("look")),
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
    # hasta 160: los ids nuevos llegan a 60 y los de antes pueden ser mas largos
    if not re.match(r"^[A-Za-z0-9_-]{1,160}$", str(pid)):
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
    temporal = f"{ruta}.{os.getpid()}.{uuid.uuid4().hex[:6]}.tmp"
    with open(temporal, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(temporal, ruta)
    return d


def prefijo_fondo(pid):
    """El principio del nombre de los fondos de UN video: corto aunque el id
    sea largo (un id de 60 hacia un nombre de 81 que no pasaba la validacion,
    y la imagen de la IA, ya pagada, se perdia; revision 19-10)."""
    return "v" + hashlib.sha1(str(pid).encode("utf-8")).hexdigest()[:12]


def nombre_fondo(pid, contenido, extension=".png"):
    return f"{prefijo_fondo(pid)}_{hashlib.sha1(contenido).hexdigest()[:10]}{extension}"


def es_fondo_de(pid, nombre):
    return str(nombre or "").startswith(prefijo_fondo(pid) + "_")


def fondos_de(raiz_publicar, pid):
    """Los fondos que ya tiene este video (subidos o hechos con IA), del mas
    nuevo al mas viejo: lo pagado no se pierde aunque se cierre el editor."""
    carpeta_f = os.path.join(carpeta(raiz_publicar), "fondos")
    try:
        nombres = [n for n in os.listdir(carpeta_f) if es_fondo_de(pid, n) and not n.endswith(".tmp")]
    except OSError:
        return []
    nombres.sort(key=lambda n: os.path.getmtime(os.path.join(carpeta_f, n)), reverse=True)
    return nombres[:40]


def cambiar_estilo(diseno, paleta=None, fuente=None, formato=None):
    """Cambia la paleta, la letra o el formato SIN rehacer los elementos: lo
    movido, escondido o anadido a mano se queda (revision 19-10). Los colores
    que eran de la paleta vieja pasan a los de la nueva; la letra vieja, a la
    nueva. Las posiciones son relativas: valen en cualquier formato."""
    d = normalizar(diseno)
    vieja, nueva = PALETAS[d["paleta"]], PALETAS.get(paleta) or PALETAS[d["paleta"]]
    for el in d["elementos"]:
        papeles = el.get("papeles")
        for cual in (el, el.get("orig")):
            if not isinstance(cual, dict):
                continue
            for campo in grafismo.CAMPOS_COLOR:
                if campo not in cual:
                    continue
                if papeles is not None:
                    # de la plantilla: por papel, exacto; sin papel, color fijo
                    if campo in papeles:
                        cual[campo] = nueva[papeles[campo]]
                else:
                    cual[campo] = _color_en_paleta(cual.get(campo), campo, vieja, nueva)
            if fuente in grafismo.FUENTES and cual.get("fuente") in (None, d["fuente"]):
                cual["fuente"] = fuente
    if paleta in PALETAS:
        d["paleta"] = paleta
    if fuente in grafismo.FUENTES:
        d["fuente"] = fuente
    if formato in FORMATOS:
        d["formato"] = formato
    return normalizar(d)


#: Qué papel de la paleta se mira primero según el campo. Con una sola tabla
#: de color a color, dos papeles del mismo color (en «Sin paleta» el texto y
#: el resaltado son blancos) se confundían y el resaltado se perdía al volver.
_PAPELES_DE_CAMPO = {"acento": ("acento", "alerta", "texto"), "contorno": ("contorno", "fondo"),
                     "color": ("texto", "acento", "alerta", "fondo", "contorno"),
                     "color_texto": ("texto", "contorno", "acento")}


def _color_en_paleta(valor, campo, vieja, nueva):
    """El color de un campo en la paleta nueva, si era uno de la vieja."""
    if valor is None:
        return None
    for papel in _PAPELES_DE_CAMPO[campo]:
        if str(valor).lower() == vieja[papel].lower():
            return nueva[papel]
    return valor


def ruta_fondo(raiz_publicar, nombre):
    if not re.match(r"^[a-z0-9_.-]{1,120}$", str(nombre)) or ".." in str(nombre):
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


def svg_guias(formato, W, H):
    """Las zonas que tapa cada red, en rojo translucido (SOLO en la vista)."""
    piezas = []
    for z in ZONAS.get(formato) or []:
        x, y, w, h = z["x"] * W, z["y"] * H, z["w"] * W, z["h"] * H
        if z.get("marco"):
            # un MARCO (lo que SÍ se ve), no una zona tapada: amarillo, sin relleno
            piezas.append(f'<rect x="{x + 3:.0f}" y="{y:.0f}" width="{w - 6:.0f}" height="{h:.0f}" fill="none" '
                          f'stroke="#ffd400" stroke-width="6" stroke-dasharray="26 14"/>'
                          f'<text x="{x + 14:.0f}" y="{y + h - 18:.0f}" font-family="Verdana, sans-serif" '
                          f'font-size="30" fill="#ffd400" stroke="#000" stroke-width="5" paint-order="stroke">'
                          f'{grafismo.escapar(z["que"])}</text>')
            continue
        piezas.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#ff0000" '
                      f'opacity="0.22" stroke="#ff0000" stroke-width="4" stroke-dasharray="18 12"/>'
                      f'<text x="{x + 14:.0f}" y="{y + 44:.0f}" font-family="Verdana, sans-serif" '
                      f'font-size="30" fill="#ffffff" stroke="#000" stroke-width="5" paint-order="stroke">'
                      f'{grafismo.escapar(z["que"])}</text>')
    return "".join(piezas)


def componer(diseno, rutas_fondo, guias=False):
    """El SVG de la portada a su tamano de verdad. -> (svg, W, H)

    En modo «ia» la imagen de la IA ES la portada (lleva el texto dentro): no se
    le pone nada encima ni se le tocan los colores."""
    d = normalizar(diseno)
    W, H = FORMATOS[d["formato"]]
    uid = "p" + hashlib.sha1(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    if d["modo"] == "ia":
        d = dict(d, elementos=[], efectos={}, fondo=dict(d["fondo"], disposicion="uno"))
    fondo = _fondo_svg(d, list(rutas_fondo or []), W, H, uid)
    paleta = PALETAS[d["paleta"]]
    svg = grafismo.lienzo(W, H, fondo, d["elementos"], d["efectos"], fondo_color=paleta["fondo"])
    if guias:
        svg = svg[:-len("</svg>")] + svg_guias(d["formato"], W, H) + "</svg>"
    return svg, W, H


def renderizar(diseno, rutas_fondo, destino, ancho_vista=0, guias=False):
    """La portada en PNG. Con `ancho_vista` sale reducida (para la pantalla)."""
    import medios                                             # noqa: PLC0415
    svg, W, H = componer(diseno, rutas_fondo, guias=guias)
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


#: Las reglas que van SIEMPRE al final del prompt, lo escriba quien lo escriba
#: (Claude, la persona o la plantilla): sin ellas un prompt editado a mano
#: podía pedir un fondo con letras encima del título de las capas.
CIERRE_FONDO = ("Muy importante: SIN texto, letras, números, logotipos ni marcas de agua en la imagen. "
                "Deja un espacio limpio en {sitio} para un titular grande que se pone después.")
CIERRE_PORTADA = ("Escribe EXACTAMENTE estos textos, con sus tildes y eñes, y ningún otro: {textos}. "
                  "Letras grandes y gruesas, con borde oscuro, que se lean en pequeño. Sin marcas de agua.")
SITIO_TITULAR = {"9:16": "la mitad de arriba", "16:9": "el lado izquierdo", "4:5": "la parte de arriba",
                 "1:1": "la parte de arriba"}
MAX_PROMPT = 1500


def _de_que_va(info):
    texto = " ".join(str(info.get("resumen") or info.get("titulo") or "").split())[:1200].rstrip(" .")
    return f"{texto}." if texto else "un negocio."


def prompt_fondo_ia(diseno, info):
    """El fondo hecho por la IA, SIN texto, con sitio para el titulo. Lo que
    se le manda se ve y se puede cambiar en la pantalla antes de pagar."""
    d = normalizar(diseno)
    return (f"Imagen de fondo para la portada de un vídeo para redes sobre: {_de_que_va(info)} "
            f"Un solo protagonista claro, colores vivos, buen contraste y luz de cine. "
            f"Formato {d['formato']}.")


def prompt_portada_ia(diseno, info):
    """LA OTRA OPCION: la portada entera con el texto dentro, hecha por la IA.
    Se paga y puede escribir alguna letra mal: la pantalla lo dice."""
    d = normalizar(diseno)
    nombre = PLANTILLAS[d["plantilla"]][0]
    pal = PALETAS[d["paleta"]]
    colores = ("blanco y negro" if d["paleta"] == "ninguna"
               else f"{pal['acento']} y {pal['texto']} sobre un ambiente {pal['fondo']}")
    return (f"Miniatura para redes, estilo «{nombre}», de un vídeo sobre: {_de_que_va(info)} "
            f"Una composición simple: un protagonista claro y el texto grande. Colores {colores}, "
            f"mucho contraste. Formato {d['formato']}.")


def textos_para_ia(diseno, info=None):
    d = normalizar(diseno)
    textos = [v for v in d["textos"].values() if v]
    return " / ".join(f"«{t}»" for t in textos) or f"«{(info or {}).get('titulo') or ''}»"


def prompt_final(que, prompt, diseno, info=None):
    """El prompt que se manda de verdad: el de la pantalla (o el de partida)
    más las reglas fijas del final. -> str"""
    d = normalizar(diseno)
    base = " ".join(str(prompt or "").split())[:MAX_PROMPT]
    if not base:
        base = prompt_portada_ia(d, info or {}) if que == "portada" else prompt_fondo_ia(d, info or {})
    if que == "portada":
        return f"{base} {CIERRE_PORTADA.format(textos=textos_para_ia(d, info))}"
    return f"{base} {CIERRE_FONDO.format(sitio=SITIO_TITULAR[d['formato']])}"


# ------------------------------------------------------------------ ideas de imagen con Claude

INSTRUCCION_IDEAS_IA = """Eres director de arte de miniaturas para redes (YouTube, Instagram, TikTok).
Lee el guion y propón {n} ideas DISTINTAS de imagen para la portada de este
vídeo. Cada idea es una escena concreta y fotografiable: quién o qué sale, qué
hace, dónde, el encuadre y la luz. Nada genérico («gente feliz», «fondo
colorido»): algo que solo encaje con ESTE vídeo y que se entienda en un
segundo en un móvil.

Cada idea trae:
- "titulo": 2–5 palabras para reconocerla.
- "prompt": la descripción para la IA de imágenes, en castellano, 40–90
  palabras. NO pidas texto, letras ni logotipos dentro (el texto va aparte).
- "por_que": una frase con por qué haría clic la gente.

<video>
Título del post: {titulo}
Textos de la portada: {textos}
Plantilla: {plantilla}
Negocio: {negocio}
Guion: {guion}
</video>

Contesta SOLO con este JSON:
{{"ideas": [{{"titulo": "...", "prompt": "...", "por_que": "..."}}]}}"""


def instruccion_ideas_ia(info, diseno, n=3):
    d = normalizar(diseno)
    return INSTRUCCION_IDEAS_IA.format(
        n=n, titulo=str(info.get("titulo") or "")[:200], textos=textos_para_ia(d, info),
        plantilla=PLANTILLAS[d["plantilla"]][0], negocio=str(info.get("negocio") or "")[:300],
        guion=" ".join(str(info.get("guion") or info.get("resumen") or "").split())[:6000])


def leer_ideas_ia(datos, n=3):
    salida = []
    for idea in ((datos or {}).get("ideas") or [])[:n * 3]:
        if len(salida) >= n:
            break
        if not isinstance(idea, dict):
            continue
        prompt = " ".join(str(idea.get("prompt") or "").split())[:MAX_PROMPT]
        if len(prompt) < 20:
            continue
        salida.append({"titulo": " ".join(str(idea.get("titulo") or "").split())[:60] or "Idea",
                       "prompt": prompt, "por_que": " ".join(str(idea.get("por_que") or "").split())[:200]})
    return salida


def proponer_ideas_ia(info, diseno, n=3, cwd=None):
    """Tres ideas de imagen de Claude (suscripción, no se paga aparte)."""
    import cli_claude                                         # noqa: PLC0415
    import comun                                              # noqa: PLC0415
    texto, _sobre = cli_claude.ejecutar(
        instruccion_ideas_ia(info, diseno, n), modelo="sonnet", esfuerzo="low", cwd=cwd,
        base_tiempo_s=180, extra=["--no-session-persistence"], para="las ideas de imagen de la portada")
    ideas = leer_ideas_ia(comun.extraer_json(texto, "las ideas de imagen"), n)
    if not ideas:
        raise RuntimeError("Claude no ha propuesto ninguna idea que se pueda usar; vuelve a pedirlo")
    return ideas
"""«+ Crear» de Gráficas (rama graficas-facil, 26-11-2026; plan en
`estado/plan_graficas_facil_2026-11-26.md`).

Lo que hace el servidor para el asistente de 3 pasos:

- `miniatura`: la PORTADA de una familia, pintada pequeña con el titular, la
  foto y los colores del Kit de quien crea (las miniaturas de «Estilo»). La
  pantalla las pide de 4 en 4 (`MAX_POR_TANDA`): cada tanda es un turno del
  navegador de Gráficas, que se suelta entre tanda y tanda para no hacer
  esperar al resto del servidor.
- `crear`: la pieza entera (publicación, historia o carrusel) con las piezas de
  texto (las de «Escríbelo por mí» o las de «Partir un texto») y la foto, en la
  familia elegida. NO guarda: el editor la abre en el «modo sencillo» y se
  guarda con «Guardar», como cualquier otra.

Nada llama a una IA ni gasta dinero. Nada de vídeos, params ni firmas.
"""
import io

import graficas as G
import graficas_capas as C
import graficas_carrusel as K
from graficas import ErrorGraficas

QUE = ("publicacion", "carrusel", "historia")
#: El tamaño de partida de cada cosa (se puede cambiar en el paso 1).
#: El botón de una publicación o una historia (en un carrusel es «Desliza →»).
CTA_UNA_IMAGEN = "Escríbenos"
FORMATO_DE = {"publicacion": "v45", "carrusel": "v45", "historia": "h916"}
MAX_POR_TANDA = 4
ANCHO_MINIATURA = 270
#: Las familias que pintan una foto en su portada (si pusiste una, salen primero).
CON_FOTO = tuple(n for n in sorted(K.FAMILIAS) if "«img»" in G._PL.PLANTILLAS[n])


def _formato(que, formato):
    if que not in QUE:
        raise ErrorGraficas("¿una publicación, un carrusel o una historia?")
    fid = formato or FORMATO_DE[que]
    G.formato(fid)
    return fid


def _poner_foto(doc, foto):
    """La foto elegida, en la foto de la plantilla de la portada (si la tiene). -> ¿se puso?"""
    if not foto:
        return False
    if not G._RE_IMAGEN.fullmatch(str(foto)):
        raise ErrorGraficas("esa foto no está")
    for c in doc["laminas"][0]["capas"]:
        if c["tipo"] == "imagen" and c.get("rol") == "foto":
            c["src"] = foto
            c["encuadre"] = {"x": 50, "y": 50, "zoom": 1}
            c["oculto"] = False
            return True
    return False


def _portada(pincel, n, formato, titulo, apoyo, foto, kit, logo, logo_oscuro, marca):
    familia = K.familia(n)
    base = C.limpiar_doc({"version": 2, "formato": formato, "laminas": [{"capas": []}]})
    textos = K.textos_de_portada(n, {"titulo": titulo, "apoyo": apoyo}, (), marca)
    doc = C.montar(pincel, n, formato, base, textos, kit, logo, logo_oscuro, 0)
    doc["laminas"][0].update(tipo="portada", familia=familia["n"])
    _poner_foto(doc, foto)
    return doc


def miniatura(pincel, n, que, formato, titulo, apoyo="", foto="", kit=None, logo=None, logo_oscuro=None, marca="",
              imagen_de=None):
    """La portada de la familia `n`, pintada pequeña. -> bytes JPG"""
    from PIL import Image                                   # noqa: PLC0415
    fid = _formato(que, formato)
    titulo = " ".join(str(titulo or "").split())[:90] or "Tu titular aquí"
    apoyo = " ".join(str(apoyo or "").split())[:140]
    doc = _portada(pincel, n, fid, titulo, apoyo, foto, kit, logo, logo_oscuro, marca)
    png, _avisos, _m = C.pintar(pincel, doc, kit, imagen_de or (lambda _n: None), logo, logo_oscuro, 0)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.thumbnail((ANCHO_MINIATURA, ANCHO_MINIATURA * 2))
    salida = io.BytesIO()
    im.save(salida, "JPEG", quality=82)
    return salida.getvalue()


def orden_de_familias(con_foto):
    """Las familias en el orden en que se enseñan: con foto, las que la usan primero."""
    todas = sorted(K.FAMILIAS)
    if not con_foto:
        return todas
    return list(CON_FOTO) + [n for n in todas if n not in CON_FOTO]


def crear(pincel, que, n, formato, piezas, foto="", kit=None, logo=None, logo_oscuro=None, marca="", nombre=""):
    """La pieza nueva, sin guardar. `piezas`: [(tipo, {campo: texto})] (la 1.ª,
    la portada). -> (doc, avisos)"""
    fid = _formato(que, formato)
    K.familia(n)
    piezas = [(str(t), dict(x)) for t, x in (piezas or []) if isinstance(x, dict)]
    if not piezas or piezas[0][0] != "portada":
        raise ErrorGraficas("falta la portada: escribe de qué trata")
    if que != "carrusel":
        piezas = piezas[:1]
        # una sola imagen no se desliza: su botón invita a escribir (se cambia tocándolo)
        piezas[0][1].setdefault("cta", CTA_UNA_IMAGEN)
    titulo = piezas[0][1].get("titulo") or "Tu titular aquí"
    base = {"version": 2, "formato": fid, "nombre": (nombre or titulo)[:80], "laminas": [{"capas": []}]}
    doc, avisos = K.carrusel_desde_texto(pincel, base, n, "", "sustituir", kit, logo, logo_oscuro, marca, piezas=piezas)
    # el aviso de «Partir» habla de láminas: dicho para quien está creando
    avisos = [("Este estilo no lleva la frase de apoyo en la portada: elige otro estilo si quieres que salga."
               if "no lleva texto de apoyo" in a else a) for a in avisos]
    if len(doc["laminas"]) == 1:
        # una sola imagen: sin la marca, el número ni el «Desliza» de un carrusel
        doc["laminas"][0]["capas"] = [c for c in doc["laminas"][0]["capas"] if not c.get("enlace")]
    if foto and not _poner_foto(doc, foto):
        avisos.append("Este estilo no lleva foto en la portada: tu foto no sale. Elige un estilo con foto "
                      "o ponla con «Cambiar foto».")
    doc["nombre"] = (nombre or titulo)[:80]
    return C.limpiar_doc(doc), avisos

"""El mapa de profundidad de una imagen, para la profundidad 2.5D del montaje.

QUE ES: una imagen en gris del mismo tamano que la original, BLANCO = CERCA y
negro = lejos. La pagina del render (`p8_render.PAGINA`) la usa para mover lo
cercano mas que el fondo mientras la camara hace su trayecto: eso es el
«2.5D». No cuesta un dolar: el modelo corre en el propio servidor.

EL MODELO: Depth Anything (vits14, ~99 MB) exportado a ONNX
(github.com/fabio-sim/Depth-Anything-ONNX, release v1.0.0, licencia Apache 2.0),
con `onnxruntime` en CPU. Medido el 18-10-2026 en 2 vCPU: 0,7-0,9 s por imagen.
Sirve tambien con ilustracion plana (separa el arbol de delante, la casa del
medio y los montes del fondo).

LO QUE NO PUEDE PASAR: que falte el modelo o `onnxruntime` y se caiga el
montaje. Sin ellos `disponible()` dice que no y por que, y `mapa_de` devuelve
None: el plano se monta con el movimiento de siempre, y quien llama lo avisa.

LA CACHE va por CONTENIDO de la imagen (su sha1), fuera de las firmas: volver a
montar un video, o montar otro que reusa una imagen del banco, no vuelve a
calcular nada. Vive en `<proyectos>/_sistema/profundidad/`.
"""
from __future__ import annotations

import hashlib
import os
import threading

#: Donde esta el modelo si nadie dice otra cosa (en el servidor lo dice
#: `ESTUDIO_MODELO_PROFUNDIDAD`, que pone `despliegue/plantillas.sh`).
NOMBRE_MODELO = "depth_anything_vits14.onnx"
#: La huella del modelo con el que se probo. `asvs actualizar` la comprueba al
#: bajarlo; aqui solo se usa para decirlo si alguien pregunta.
SHA256_MODELO = "21e149bdc73d9173c2dfe0dce9a2b7d0d3bcf9be06440ad987a703b7ce30ea54"
URL_MODELO = ("https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/"
              "v1.0.0/depth_anything_vits14.onnx")

#: El lado al que se reduce la imagen para el modelo (multiplo de 14: el
#: tamano de parche del ViT). Mas grande es mas lento y no mas util: el mapa se
#: desenfoca despues.
LADO = 518
#: Desenfoque del mapa, en px de la imagen ORIGINAL por cada 1000 px de ancho.
#: Suaviza los bordes, que es donde el desplazamiento «derrite» la imagen.
DESENFOQUE_POR_MIL = 6.0

_RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SESION = {"sesion": None, "ruta": None}
_CERROJO = threading.Lock()


def ruta_modelo():
    return (os.environ.get("ESTUDIO_MODELO_PROFUNDIDAD")
            or os.path.join(_RAIZ_ESTUDIO, "modelos", NOMBRE_MODELO))


def carpeta_cache():
    raiz = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(_RAIZ_ESTUDIO, "proyectos")
    return os.path.join(raiz, "_sistema", "profundidad")


def disponible():
    """(si, por_que) -- si se puede calcular un mapa en esta maquina."""
    try:
        import onnxruntime  # noqa: F401,PLC0415
    except Exception:                                         # noqa: BLE001
        return False, "falta la libreria onnxruntime (la instala `asvs actualizar`)"
    if not os.path.isfile(ruta_modelo()):
        return False, (f"falta el modelo de profundidad ({NOMBRE_MODELO}); "
                       "lo baja `asvs actualizar`")
    return True, ""


def _sesion():
    import onnxruntime as ort                                # noqa: PLC0415
    ruta = ruta_modelo()
    with _CERROJO:
        if _SESION["sesion"] is None or _SESION["ruta"] != ruta:
            opciones = ort.SessionOptions()
            # un hilo menos que la maquina: el montaje sigue corriendo al lado
            opciones.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
            _SESION["sesion"] = ort.InferenceSession(ruta, sess_options=opciones,
                                                     providers=["CPUExecutionProvider"])
            _SESION["ruta"] = ruta
        return _SESION["sesion"]


def huella_de(ruta):
    h = hashlib.sha1()
    with open(ruta, "rb") as fh:
        for trozo in iter(lambda: fh.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def calcular(origen, destino):
    """Calcula el mapa de `origen` y lo escribe en `destino` (PNG gris). -> destino"""
    import numpy as np                                        # noqa: PLC0415
    from PIL import Image, ImageFilter                        # noqa: PLC0415
    with Image.open(origen) as abierta:
        imagen = abierta.convert("RGB")
    ancho, alto = imagen.size
    x = np.asarray(imagen.resize((LADO, LADO), Image.BICUBIC), dtype=np.float32) / 255.0
    x = (x - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / \
        np.array([0.229, 0.224, 0.225], dtype=np.float32)
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    sesion = _sesion()
    entrada = sesion.get_inputs()[0].name
    with _CERROJO:
        d = sesion.run(None, {entrada: x})[0]
    d = np.asarray(d, dtype=np.float32).reshape(d.shape[-2], d.shape[-1])
    bajo, alto_d = float(d.min()), float(d.max())
    d = (d - bajo) / max(1e-6, alto_d - bajo)
    mapa = Image.fromarray((d * 255).astype(np.uint8)).resize((ancho, alto), Image.BICUBIC)
    radio = max(1.0, ancho * DESENFOQUE_POR_MIL / 1000.0)
    mapa = mapa.filter(ImageFilter.GaussianBlur(radio))
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    temporal = destino + ".tmp"
    mapa.save(temporal, format="PNG")
    os.replace(temporal, destino)
    return destino


def mapa_de(origen):
    """El mapa de profundidad de esa imagen, de la cache o recien hecho. -> ruta | None

    None si no se puede (sin modelo, sin libreria o la imagen no se abre): quien
    llama monta el plano con el movimiento de siempre.
    """
    si, _por_que = disponible()
    if not si or not origen or not os.path.isfile(origen):
        return None
    try:
        guardado = os.path.join(carpeta_cache(), huella_de(origen) + ".png")
        if not os.path.isfile(guardado):
            calcular(origen, guardado)
        return guardado
    except Exception:                                         # noqa: BLE001
        return None

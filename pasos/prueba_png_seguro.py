"""Rama png-seguro: ninguna imagen se lee a medias, y una rota no se reparte.

El fallo (piloto, Y15, 11-11-2026): «broken PNG file (chunk b'\\x00\\x00\\x00\\x00')»
en «Imágenes y revisor», y el vídeo se cortaba. El disco del servidor estaba
al 36 %: no era falta de sitio. Las imágenes se escribían EN SU SITIO poco a
poco (`open(destino, "wb")` y `shutil.copy2`), y quien las leía a la vez --el
revisor, otra tanda que la coge del banco, el montaje-- veía una a medias. Y
una copia a medias que quedaba en el banco (compartido por todos los
proyectos) se volvía a repartir a cada plano con esa firma.

Lo que se comprueba, sin pagar nada:

  1] EL FALLO, reproducido: escribir en el sitio con un lector a la vez deja
     ver imagenes a medias;
  2] con `medios.escribir_bytes` y `medios.copiar`, el lector no ve ninguna;
  3] `imagen_sana`: una sana, una con un trozo de ceros, una cortada, una de
     ceros, una JPEG (que no se toca nunca);
  4] p6: una imagen rota en el banco se aparta y se dibuja otra; una sana se
     reutiliza sin pagar; lo que llega roto de OpenAI no se guarda; un plano
     con su PNG roto se vuelve a producir y uno sano se conserva.

    python pasos/prueba_png_seguro.py
"""
import io
import os
import shutil
import sys
import tempfile
import threading
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))
os.environ.setdefault("ESTUDIO_SIMULAR", "1")

from PIL import Image  # noqa: E402

import medios  # noqa: E402
import p6_assets as P6  # noqa: E402

_fallos = []
_cuenta = [0]


def ok(condicion, texto):
    _cuenta[0] += 1
    if condicion:
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLO {texto}")


def seccion(titulo):
    print(f"\n[{titulo}]")


def png_de(color, lado=900):
    """Un PNG de verdad y grande (ruido, para que no se comprima a nada)."""
    imagen = Image.effect_noise((lado, lado), 80).convert("RGB")
    imagen.paste(color, (0, 0, 40, 40))
    salida = io.BytesIO()
    imagen.save(salida, "PNG")
    return salida.getvalue()


def _carrera(escribir, destino, vueltas=40):
    """Un hilo escribe `vueltas` veces y otro lee sin parar. -> lecturas rotas."""
    datos = [png_de((255, 0, 0)), png_de((0, 0, 255))]
    escribir(destino, datos[0])
    rotas, acabado = [0], threading.Event()

    def lector():
        while not acabado.is_set():
            try:
                with open(destino, "rb") as fh:
                    leido = fh.read()
            except OSError:
                continue
            if not medios.bytes_de_imagen_sanos(leido):
                rotas[0] += 1

    hilo = threading.Thread(target=lector)
    hilo.start()
    try:
        for i in range(vueltas):
            escribir(destino, datos[i % 2])
    finally:
        acabado.set()
        hilo.join()
    return rotas[0]


def escribir_en_el_sitio(destino, datos):
    """Como se escribia antes del arreglo."""
    with open(destino, "wb") as fh:
        for i in range(0, len(datos), 65536):
            fh.write(datos[i:i + 65536])
            fh.flush()


def prueba_la_carrera(carpeta):
    seccion("1] EL FALLO: escribir en el sitio con alguien leyendo")
    antes = _carrera(escribir_en_el_sitio, os.path.join(carpeta, "antes.png"))
    ok(antes > 0, f"el lector ve imagenes a medias ({antes} lecturas rotas): es el «broken PNG»")

    seccion("2] escribir_bytes y copiar: entera o nada")
    ahora = _carrera(medios.escribir_bytes, os.path.join(carpeta, "ahora.png"))
    ok(ahora == 0, f"con escribir_bytes el lector no ve ninguna a medias ({ahora})")
    origenes = {}

    def copiando(destino, datos):
        clave = hash(datos)
        if clave not in origenes:
            origenes[clave] = os.path.join(carpeta, f"origen_{len(origenes)}.png")
            medios.escribir_bytes(origenes[clave], datos)
        medios.copiar(origenes[clave], destino)
    copias = _carrera(copiando, os.path.join(carpeta, "banco.png"))
    ok(copias == 0, f"con copiar (el banco, la carpeta del vídeo) tampoco ({copias})")
    sobras = [n for n in os.listdir(carpeta) if n.endswith(".parcial")]
    ok(not sobras, f"y no quedan temporales sueltos ({sobras[:3]})")


def prueba_imagen_sana(carpeta):
    seccion("3] imagen_sana")
    buena = png_de((10, 200, 10), 64)
    ruta = os.path.join(carpeta, "sana.png")
    medios.escribir_bytes(ruta, buena)
    ok(medios.imagen_sana(ruta), "una imagen entera está sana")
    con_ceros = bytearray(buena)
    mitad = len(buena) // 2
    con_ceros[mitad:mitad + 64] = b"\x00" * 64
    rota = os.path.join(carpeta, "ceros.png")
    medios.escribir_bytes(rota, bytes(con_ceros))
    ok(not medios.imagen_sana(rota), "una con un trozo de ceros, no")
    cortada = os.path.join(carpeta, "cortada.png")
    medios.escribir_bytes(cortada, buena[:len(buena) // 2])
    ok(not medios.imagen_sana(cortada), "una cortada, no")
    vacia = os.path.join(carpeta, "vacia.png")
    medios.escribir_bytes(vacia, b"\x00" * 200)
    ok(not medios.imagen_sana(vacia), "una que es solo ceros, no")
    ok(not medios.imagen_sana(os.path.join(carpeta, "no_existe.png")), "una que no existe, no")
    jpg = os.path.join(carpeta, "subida.jpg")
    Image.new("RGB", (8, 8)).save(jpg, "JPEG")
    ok(medios.imagen_sana(jpg), "una JPEG subida se da por sana (nunca se borra)")


def prueba_p6(carpeta):
    seccion("4] p6: el banco, lo que llega y lo que ya había")
    banco = os.path.join(carpeta, "banco")
    os.makedirs(banco)
    p = {"calidad": "low", "banco_imagenes": banco, "motor_imagen": "api",
         "imagenes_previas": []}
    pedidas = []
    llega = {"png": png_de((200, 200, 0), 64)}
    falso = types.SimpleNamespace(generar=lambda prompt, refs, quality, tamano: (
        pedidas.append(prompt) or llega["png"], {"coste": 0.05, "segundos": 1.0}))
    real = medios.motor
    medios.motor = lambda nombre: falso if "imagen" in nombre else real(nombre)
    try:
        firma = P6._firma_imagen("un plano", "low", "apaisado", [])   # noqa: SLF001
        cacheada = os.path.join(banco, f"{firma}.png")
        with open(cacheada, "wb") as fh:                            # rota, como la de antes
            fh.write(png_de((0, 0, 0), 64)[:300])
        destino = os.path.join(carpeta, "v", "S001.png")
        meta = P6._producir_imagen("S001", "un plano", [], destino, p)  # noqa: SLF001
        ok(meta["origen"] == "generada" and len(pedidas) == 1,
           "una imagen rota en el banco no se reparte: se dibuja otra")
        ok(medios.imagen_sana(destino) and medios.imagen_sana(cacheada),
           "y el plano y el banco quedan con la sana")
        destino2 = os.path.join(carpeta, "v", "S002.png")
        meta = P6._producir_imagen("S002", "un plano", [], destino2, p)  # noqa: SLF001
        ok(meta["origen"] == "cache" and len(pedidas) == 1,
           "una sana del banco se reutiliza sin pagar")
        llega["png"] = png_de((1, 2, 3), 64)[:500]
        destino3 = os.path.join(carpeta, "v", "S003.png")
        try:
            P6._producir_imagen("S003", "otro plano", [], destino3, p)   # noqa: SLF001
            ok(False, "lo que llega roto de OpenAI se dice")
        except RuntimeError as fallo:
            ok("no se puede leer" in str(fallo), f"lo que llega roto de OpenAI se dice ({fallo})")
        firma3 = P6._firma_imagen("otro plano", "low", "apaisado", [])  # noqa: SLF001
        ok(not os.path.exists(destino3) and not os.path.exists(os.path.join(banco, f"{firma3}.png")),
           "y no se guarda ni en el plano ni en el banco")
        rota = os.path.join(carpeta, "v", "S004.png")
        with open(rota, "wb") as fh:
            fh.write(png_de((5, 5, 5), 64)[:200])
        ok(not P6._sana_o_apartada(rota, "S004") and not os.path.exists(rota),   # noqa: SLF001
           "un plano con su PNG roto se aparta (se vuelve a producir)")
        ok(P6._sana_o_apartada(destino2, "S002") and os.path.exists(destino2),   # noqa: SLF001
           "y uno sano se conserva")
    finally:
        medios.motor = real


def main():
    carpeta = tempfile.mkdtemp(prefix="png_seguro_")
    try:
        prueba_la_carrera(carpeta)
        prueba_imagen_sana(carpeta)
        prueba_p6(carpeta)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print()
    if _fallos:
        print(f"PNG SEGURO: FALLAN {len(_fallos)} de {_cuenta[0]} comprobaciones")
        for texto in _fallos:
            print(f"  - {texto}")
        return 1
    print(f"PNG SEGURO OK: {_cuenta[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

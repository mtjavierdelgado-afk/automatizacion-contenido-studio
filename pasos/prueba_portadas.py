"""Prueba de las portadas disenadas (rama `portadas`): el motor de grafismo y
las plantillas, sin red, sin CLI de verdad y sin gastar nada.

  - grafismo: cada elemento sale como SVG valido, lo que viene de fuera se
    limpia (tipos, campos, numeros, colores), los textos se escapan y caben;
  - portadas: las veintiuna plantillas en los cuatro formatos dan un SVG que
    se puede leer, cambiar de plantilla conserva textos y fondo, el diseno se
    guarda de forma atomica y una ruta de fondo no sale de su carpeta;
  - Claude: las propuestas se validan (una plantilla inventada no entra) y un
    CLI doble devuelve tres disenos completos;
  - el render: una portada sale como PNG del tamano pedido;
  - la IA: los dos prompts (fondo sin texto, portada con el texto exacto).

    python pasos/prueba_portadas.py
"""
import json
import os
import shutil
import sys
import tempfile
import xml.dom.minidom

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CARPETA = tempfile.mkdtemp(prefix="portadas_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_FUENTES_GRAFISMO"] = os.path.join(CARPETA, "fuentes")
os.environ["ESTUDIO_SIN_DESCARGAS"] = "1"

import cli_claude  # noqa: E402
import grafismo  # noqa: E402
import portadas  # noqa: E402

FALLOS = []
OK = [0]


def ok(condicion, texto):
    if condicion:
        OK[0] += 1
        print(f"  ok   {texto}")
    else:
        FALLOS.append(texto)
        print(f"  FALLO {texto}")


def seccion(titulo):
    print(f"\n[{titulo}]")


def svg_legible(svg):
    try:
        xml.dom.minidom.parseString(svg.encode("utf-8"))
        return True
    except Exception as fallo:                              # noqa: BLE001
        print("    ", str(fallo)[:200])
        return False


def prueba_grafismo():
    seccion("1] grafismo: cada elemento, limpio y legible")
    for tipo in grafismo.ELEMENTOS:
        el = {"tipo": tipo, "texto": "Ñandú & <ácido>", "x": 0.5, "y": 0.5, "x2": 0.8, "y2": 0.7}
        frag = grafismo.elemento(el, 1080, 1920)
        ok(frag and svg_legible(f'<svg xmlns="http://www.w3.org/2000/svg">{frag}</svg>'),
           f"«{tipo}» sale como SVG legible")
    frag = grafismo.elemento({"tipo": "texto", "texto": "a<b>&c"}, 1080, 1920)
    ok("&lt;B&gt;&amp;C" in frag, "el texto se escapa (no se cuela marcado)")
    ok(grafismo.elemento({"tipo": "inventado"}, 100, 100) == "", "un tipo que no existe no pinta nada")
    ok(grafismo.elemento({"tipo": "texto", "texto": "x", "oculto": True}, 100, 100) == "",
       "un elemento oculto no pinta nada")
    limpios = grafismo.limpiar_elementos([
        {"tipo": "texto", "texto": "x" * 500, "x": "nan", "tam": 99, "color": "red",
         "onload": "alert(1)", "estilos": ["contorno"] * 40},
        {"tipo": "script"}, "no soy un dict"] + [{"tipo": "icono"}] * 40)
    ok(len(limpios) <= grafismo.MAX_ELEMENTOS, f"como mucho {grafismo.MAX_ELEMENTOS} elementos")
    ok(limpios[0]["tipo"] == "texto" and "onload" not in limpios[0] and len(limpios[0]["texto"]) <= 160,
       "los campos que no existen se quitan y los textos se acortan")
    ok("x" not in limpios[0], "un número que no es número (nan) no entra")
    frag = grafismo.elemento(limpios[0], 1080, 1920)
    ok('fill="#ffffff"' in frag, "un color que no es #rrggbb cae al de por defecto")
    largo = grafismo.elemento({"tipo": "texto", "texto": "UNA FRASE MUY MUY LARGA QUE NO CABE NI DE BROMA",
                               "tam": 0.3, "ancho": 0.5, "lineas": 2}, 1080, 1920)
    ok(largo.count("<text ") <= 2 * 3, "un título largo se parte y se encoge, no se sale")
    ok(grafismo.contraste_de("#ffff00") == "#111111" and grafismo.contraste_de("#000080") == "#ffffff",
       "el texto sobre un color elige negro o blanco, el que se lee")
    estado = grafismo.fuentes_estado()
    ok(any(f["id"] == "sistema" and f["lista"] for f in estado), "la fuente del sistema siempre está")
    ok(grafismo.asegurar_fuentes() == {}, "sin red (ESTUDIO_SIN_DESCARGAS) no se baja nada y no falla")
    ok(grafismo.css_fuentes(["anton"]) == "", "sin la fuente bajada no se incrusta nada (cae al respaldo)")
    # una fuente «bajada» de mentira no se incrusta si no es TrueType: no la baja
    # nadie de verdad aqui, pero `ruta_fuente` exige que pese algo
    os.makedirs(grafismo.carpeta_fuentes(), exist_ok=True)
    with open(os.path.join(grafismo.carpeta_fuentes(), "Anton-Regular.ttf"), "wb") as fh:
        fh.write(b"\x00\x01\x00\x00" + b"0" * 2000)
    ok("@font-face" in grafismo.css_fuentes(["anton"]), "con la fuente en su carpeta, va dentro del SVG")
    os.remove(os.path.join(grafismo.carpeta_fuentes(), "Anton-Regular.ttf"))


def prueba_plantillas():
    seccion("2] portadas: todas las plantillas en todos los formatos")
    textos = {"titulo": "Fiesta épica", "izquierda": "Diseño", "derecha": "Función", "numero": "5",
              "etiqueta": "S/ 99", "insignia": "VS", "antetitulo": "Lo que se ve", "pie": "S/ 150"}
    malos = []
    for pid in portadas.PLANTILLAS:
        for fmt in portadas.FORMATOS:
            d = portadas.de_plantilla(pid, textos, "gamer", "anton", fmt)
            svg, W, H = portadas.componer(d, [])
            if not (d["elementos"] and svg_legible(svg) and (W, H) == portadas.FORMATOS[fmt]):
                malos.append(f"{pid}/{fmt}")
    ok(not malos, f"las {len(portadas.PLANTILLAS)} plantillas × {len(portadas.FORMATOS)} formatos "
       f"dan un SVG legible con elementos ({malos[:5]})")
    ok(len(portadas.PLANTILLAS) >= 20, f"hay al menos veinte plantillas ({len(portadas.PLANTILLAS)})")
    d = portadas.de_plantilla("versus", {"izquierda": "Diseño", "derecha": "Función"}, "calido", "bebas", "9:16",
                              fondo={"tipo": "plano", "planos": ["S001", "S004"]})
    otro = portadas.de_plantilla("top", None, "oferta", "anton", "16:9", base=d)
    ok(otro["textos"].get("izquierda") == "Diseño" and otro["fondo"]["planos"] == ["S001", "S004"],
       "cambiar de plantilla conserva lo escrito y el fondo elegido")
    ok(otro["fondo"]["disposicion"] == "uno" and d["fondo"]["disposicion"] == "diagonal",
       "cada plantilla pone su disposición del fondo (versus parte en diagonal)")
    raro = portadas.normalizar({"plantilla": "no", "formato": "3:2", "paleta": "x", "fuente": "comic sans",
                                "fondo": {"tipo": "../../etc", "imagen": "../secreto.png", "planos": ["S1;rm"]},
                                "efectos": {"contraste": 99}, "textos": {"titulo": "x" * 300, "otro": "y"}})
    ok(raro["plantilla"] == "titular" and raro["formato"] == "9:16" and raro["fuente"] == "anton",
       "lo que no existe cae a lo de por defecto")
    ok("imagen" not in raro["fondo"] and raro["fondo"]["planos"] == [] and raro["fondo"]["tipo"] == "fotograma",
       "un fondo con rutas raras no entra")
    ok(raro["efectos"]["contraste"] == 1.8 and len(raro["textos"]["titulo"]) == 80 and "otro" not in raro["textos"],
       "los efectos se acotan y los textos se recortan")
    puesto = portadas.aplicar_textos(d, {"izquierda": "Bonito"})
    ok(any(e.get("rol") == "izquierda" and e.get("texto") == "Bonito" for e in puesto["elementos"]),
       "cambiar un texto lo pone en su elemento sin rehacer el diseño")
    try:
        portadas.ruta_fondo(CARPETA, "../../etc/passwd")
        ok(False, "una ruta de fondo con .. tenía que fallar")
    except ValueError:
        ok(True, "una ruta de fondo no sale de su carpeta")
    try:
        portadas.ruta_diseno(CARPETA, "../x")
        ok(False, "un vídeo con .. tenía que fallar")
    except ValueError:
        ok(True, "el diseño de un vídeo con nombre raro no se escribe")
    guardado = portadas.guardar(CARPETA, "video1", d)
    ok(portadas.leer(CARPETA, "video1") == guardado, "el diseño se guarda y se lee igual")
    ok(not [f for f in os.listdir(portadas.carpeta(CARPETA)) if f.endswith(".tmp")],
       "sin temporales a medias")
    with open(portadas.ruta_diseno(CARPETA, "video2"), "w") as fh:
        fh.write("{roto")
    ok(portadas.leer(CARPETA, "video2") is None, "un diseño ilegible es como no tenerlo")
    cat = portadas.catalogo()
    ok(len(cat["plantillas"]) == len(portadas.PLANTILLAS) and cat["formatos"]["9:16"]["zonas"],
       "el catálogo lleva las plantillas y las zonas que tapa cada red")


def prueba_claude():
    seccion("3] Claude propone (con un CLI doble)")
    original = cli_claude.ejecutar
    pedidos = []

    def doble(instruccion, **_k):
        pedidos.append(instruccion)
        return json.dumps({"propuestas": [
            {"plantilla": "versus", "paleta": "gamer", "fuente": "anton",
             "textos": {"izquierda": "PS5", "derecha": "XBOX"}, "por_que": "compara"},
            {"plantilla": "inventada", "textos": {}},
            {"plantilla": "oferta", "paleta": "nada", "fuente": "nada", "textos": {"titulo": "TODO EL DÍA",
                                                                                 "etiqueta": "S/ 99"}},
            {"plantilla": "pregunta", "textos": {"titulo": "¿CUÁNTO CUESTA?"}}]}), {}
    try:
        cli_claude.ejecutar = doble
        props = portadas.proponer({"titulo": "Alquiler de consolas", "resumen": "fiestas en Lima"}, "9:16")
        ok(len(props) == 3, f"tres propuestas (la de la plantilla inventada se descarta) ({len(props)})")
        ok(props[0]["diseno"]["textos"]["izquierda"] == "PS5" and props[1]["diseno"]["paleta"] == "gamer",
           "cada propuesta es un diseño completo; lo que no existe cae a lo de por defecto")
        ok("versus" in pedidos[0] and "fiestas en Lima" in pedidos[0], "a Claude le llegan las plantillas y el guion")

        def vacio(instruccion, **_k):
            return '{"propuestas": []}', {}
        cli_claude.ejecutar = vacio
        try:
            portadas.proponer({"titulo": "x"}, "9:16")
            ok(False, "sin ninguna propuesta válida tenía que lanzar")
        except RuntimeError:
            ok(True, "sin ninguna propuesta que se pueda usar, lo dice")
    finally:
        cli_claude.ejecutar = original


def prueba_render():
    seccion("4] el render (navegador sin cabeza)")
    try:
        import medios                                       # noqa: F401
        medios.edge()
    except Exception as fallo:                              # noqa: BLE001
        print(f"  (sin navegador: {fallo}; se omite)")
        return
    from PIL import Image
    fondo = os.path.join(CARPETA, "fondo.png")
    Image.new("RGB", (640, 480), (200, 120, 60)).save(fondo)
    d = portadas.de_plantilla("versus", {"izquierda": "Diseño", "derecha": "Función"}, "calido", "anton", "9:16")
    destino = os.path.join(CARPETA, "vista.png")
    portadas.renderizar(d, [fondo, fondo], destino, ancho_vista=270)
    with Image.open(destino) as im:
        ok(im.size == (270, 480), f"la vista sale del tamaño pedido ({im.size})")
        abajo = im.convert("RGB").getpixel((135, 470))
        ok(abajo != (255, 255, 255), f"sin franja blanca abajo (recortada) ({abajo})")
    destino = os.path.join(CARPETA, "final.png")
    d = portadas.de_plantilla("titular", {"titulo": "Hola"}, "gamer", "anton", "16:9")
    portadas.renderizar(d, [fondo], destino)
    with Image.open(destino) as im:
        ok(im.size == (1280, 720), f"la portada de 16:9 sale a 1280×720 ({im.size})")


def prueba_ia():
    seccion("5] las dos opciones con IA")
    d = portadas.de_plantilla("versus", {"izquierda": "Diseño", "derecha": "Función"}, "calido", "anton", "9:16")
    fondo = portadas.prompt_fondo_ia(d, {"resumen": "cocina con islas de madera"})
    ok("NO text" in fondo and "cocina" in fondo, "el fondo con IA se pide SIN texto y con el tema del vídeo")
    entera = portadas.prompt_portada_ia(d, {"resumen": "cocina"})
    ok('"Diseño"' in entera and '"Función"' in entera and "accents" in entera,
       "la portada entera con IA lleva el texto exacto, con tildes")
    ok(set(portadas.TAMANO_IA) == set(portadas.FORMATOS), "cada formato tiene su tamaño de imagen")


def main():
    try:
        prueba_grafismo()
        prueba_plantillas()
        prueba_claude()
        prueba_render()
        prueba_ia()
    finally:
        shutil.rmtree(CARPETA, ignore_errors=True)
    print()
    if FALLOS:
        print(f"PRUEBA PORTADAS CON FALLOS: {len(FALLOS)}")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        return 1
    print(f"PRUEBA PORTADAS OK: {OK[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

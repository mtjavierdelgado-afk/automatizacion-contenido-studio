"""Las comprobaciones de Gráficas (rama graficas-1, 05-11-2026).

    python pasos/prueba_graficas.py

Necesita el navegador (ESTUDIO_EDGE, o microsoft-edge / google-chrome en el
PATH), como `prueba_pasos_visuales`. No baja nada ni llama a ninguna IA.
"""
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["ESTUDIO_SIN_DESCARGAS"] = "1"

import graficas as G  # noqa: E402

CUENTA = {"ok": 0, "mal": 0}


def ok(cond, que):
    CUENTA["ok" if cond else "mal"] += 1
    if not cond:
        print(f"  MAL: {que}")


def falla(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except G.ErrorGraficas:
        return True
    return False


TEXTOS = {"marca": "Casa Sabor", "tipo": "Restaurante", "kicker": "Nuevo menú", "titulo": "Tu próximo hogar empieza aquí",
          "apoyo": "Departamentos de 2 y 3 dormitorios", "cta": "Agenda tu visita", "oferta": "-20%",
          "oferta_txt": "de lunes a jueves", "dia": "15", "mes": "de noviembre", "lugar": "Miraflores",
          "i1": "Elige tu plato", "i2": "Reserva en un minuto", "i3": "Ven y disfruta",
          "cita": "El mejor almuerzo del barrio, sin duda.", "autor": "Cliente de ejemplo"}


def imagen_de_prueba(modo="RGB", tam=(800, 600)):
    from PIL import Image
    salida = io.BytesIO()
    Image.new(modo, tam, (200, 80, 40) if modo == "RGB" else (200, 80, 40, 128)).save(salida, "PNG")
    return salida.getvalue()


def datos_y_kit(raiz):
    print("kit de marca")
    ok(G.leer_kit(raiz, "cli") is None, "sin kit, leer devuelve None")
    ok(not os.path.exists(G.carpeta(raiz)), "leer no escribe nada (regla 1)")
    ok(falla(G.guardar_kit, raiz, "cli", {"colores": {"principal": "rojo"}}), "un color raro se rechaza")
    ok(falla(G.guardar_kit, raiz, "cli", {"fuente_titulos": "../x"}), "una letra fuera de la lista se rechaza")
    ok(falla(G.guardar_kit, raiz, "../fuera", {}), "un proyecto con ruta rara se rechaza")
    kit = G.guardar_kit(raiz, "cli", {"colores": {"principal": "#ff5a00"}, "fuente_titulos": "anton", "reglas": "x" * 5000, "otro": 1})
    ok(kit["colores"]["principal"] == "#FF5A00", "el color se guarda normalizado")
    ok(len(kit["reglas"]) == 1200 and "otro" not in kit, "largo acotado y sin campos ajenos")
    ok(G.leer_kit(raiz, "cli") == kit, "lo guardado se vuelve a leer")
    print("colores")
    ok(G.contraste("#000000", "#FFFFFF") > 20, "el contraste se calcula")
    for fondo in ("#FFD60A", "#5B2EFF", "#808080", "#00C2A8"):
        ok(G.contraste(fondo, G._tinta_para(fondo, "#808080", "#808080")) >= 4.5, f"texto legible sobre {fondo}, aunque el kit no ayude")
    f = G.colores_finales({"colores": {"principal": "#111111"}}, {"colores": {"secundario": "#222222"}})
    ok(f["principal"] == "#111111" and f["secundario"] == "#222222" and f["claro"] == G.COLORES_DEFECTO["claro"],
       "manda la pieza, luego el kit, luego lo de partida")


def la_pagina():
    print("la página no sale de sí misma")
    malo = '<img src=x onerror=alert(1)>"</style><script>alert(2)</script>'
    doc, *_ = G.html_de({"plantilla": 2, "textos": {"titulo": malo}})
    ok("<script" not in doc and "onerror=alert(1)>" not in doc.replace("&lt;img src=x onerror=alert(1)&gt;", ""), "el texto va escapado")
    for n in G._PL.PLANTILLAS:
        doc, *_ = G.html_de({"plantilla": n, "textos": TEXTOS})
        limpio = re.sub(r"data:[a-z/]+;base64,[A-Za-z0-9+/=]+", "", doc)
        ok("http" not in limpio and "file:" not in limpio, f"plantilla {n} sin nada de fuera")
        ok("«" not in limpio.replace("«", "«", 0) or "«" not in limpio, f"plantilla {n} sin huecos sin rellenar")
    ok(falla(G.limpiar_pieza, {"plantilla": 99}), "una plantilla que no existe se rechaza")
    ok(falla(G.limpiar_pieza, {"formato": "x"}), "un tamaño que no existe se rechaza")
    ok(falla(G.limpiar_pieza, {"imagen": "../../secreto.jpg"}), "una imagen con ruta rara se rechaza")
    ok(falla(G.limpiar_pieza, {"textos": "x"}), "unos textos sin forma se rechazan")
    ok(falla(G.limpiar_pieza, {"colores": ["x"]}), "unos colores sin forma se rechazan")
    ok(falla(G.limpiar_pieza, {"plantilla": True}), "la plantilla tiene que ser un número")
    ok(set(p[0] for p in G.CATALOGO) == set(G._PL.PLANTILLAS), "el catálogo y las plantillas coinciden")
    ok(len(G.CATALOGO) == 14, "son las 14 de la maqueta")


def en_el_navegador(imagen):
    print("las 14 plantillas en los 8 tamaños")
    from PIL import Image
    pincel = G.Pincel()
    try:
        ok(pincel.evaluar("(() => { try { const s = document.createElement('script'); s.textContent='window.X=1'; document.head.appendChild(s); } catch (e) {} return window.X === 1; })()") in (False, None),
           "la página no ejecuta scripts")
        pincel.abrir('<!doctype html><img id="i" src="https://example.com/x.png">', 100, 100)
        ok(pincel.evaluar("document.getElementById('i').naturalWidth") == 0, "ni sale a internet")
        for f in G.FORMATOS:
            for n in G._PL.PLANTILLAS:
                for ruta in (imagen, None):
                    png, avisos, medida = G.pintar(pincel, {"plantilla": n, "formato": f["id"], "textos": TEXTOS}, None, ruta)
                    ok(not medida["fuera"] and not medida["choca"], f"{n}/{f['id']}: el texto cabe y no pisa lo que tapa la red {medida}")
                    if ruta:
                        ok(Image.open(io.BytesIO(png)).size == (f["W"], f["H"]), f"{n}/{f['id']}: medida exacta")
        largo = dict(TEXTOS, titulo="palabra " * 11)
        _, avisos, _ = G.pintar(pincel, {"plantilla": 1, "formato": "c11", "textos": largo})
        ok(any("no cabe" in a or "reducida" in a for a in avisos), "un texto muy largo avisa")
        _, _, medida = G.pintar(pincel, {"plantilla": 14, "textos": {}})
        ok(medida["fuera"] == [], "una pieza vacía no se rompe")
        jpg = G.a_jpg(G.pintar(pincel, {"plantilla": 2, "textos": TEXTOS})[0])
        ok(jpg[:3] == b"\xff\xd8\xff" and len(jpg) < 8 * 1024 * 1024, "el JPG para publicar pesa menos que el tope de Instagram")
    finally:
        pincel.cerrar()


def las_piezas(raiz):
    print("retoques del texto y de la foto")
    pieza = G.limpiar_pieza({"plantilla": 2, "capas": {"titulo": {"x": 500, "escala": 99, "negrita": True, "color": "#ff0000"}, "raro": {"x": 1}},
                             "encuadre": {"x": 900, "zoom": 2}})
    ok(pieza["capas"]["titulo"]["x"] == 100 and pieza["capas"]["titulo"]["escala"] == 3 and "raro" not in pieza["capas"], "los retoques se acotan")
    ok(pieza["encuadre"] == {"x": 100, "y": 50, "zoom": 2}, "el encuadre se acota")
    ok(falla(G.limpiar_pieza, {"capas": {"titulo": {"color": "red;background:url(x)"}}}), "un color raro en el texto se rechaza")
    doc, *_ = G.html_de({"plantilla": 2, "textos": TEXTOS, "capas": {"titulo": {"x": 5, "y": -4, "escala": 1.5, "negrita": True, "subrayado": True, "fondo": "#112233", "color": "#FFFFFF"}}, "encuadre": {"x": 20, "y": 80, "zoom": 2}})
    ok("translate:5.0cqw -4.0cqh" in doc and "background:#112233" in doc and "underline" in doc and "*1.5)" in doc, "los retoques llegan a la página")
    ok("object-view-box:inset(40.000% 40.000% 10.000% 10.000%)" in doc, "el encuadre recorta la parte pedida")
    pincel = G.Pincel()
    try:
        base, _, _ = G.pintar(pincel, {"plantilla": 2, "textos": TEXTOS, "capas": {"titulo": {"x": 0}}}, None, G.ruta_imagen(raiz, "cli", G.guardar_imagen(raiz, "cli", imagen_de_prueba())))
        pincel.evaluar(G._CAJAS)
        _, _, _ = G.pintar(pincel, {"plantilla": 2, "textos": TEXTOS}, None, None)
        antes = pincel.evaluar(G._CAJAS)["cajas"]["titulo"]
        _, avisos, _ = G.pintar(pincel, {"plantilla": 2, "textos": TEXTOS, "capas": {"titulo": {"x": 10, "y": 500}}}, None, None)
        despues = pincel.evaluar(G._CAJAS)["cajas"]["titulo"]
        ok(abs(despues["x"] - antes["x"] - 10) < 0.5, "arrastrar mueve el texto en la pieza")
        ok(any("tapa la red" in a for a in avisos), "y si cae fuera de lo seguro, avisa")
        _, _, _ = G.pintar(pincel, {"plantilla": 2, "textos": TEXTOS, "capas": {"titulo": {"oculto": True}}}, None, None)
        ok("titulo" not in pincel.evaluar(G._CAJAS)["cajas"], "ocultar lo quita")
        _, _, _ = G.pintar(pincel, {"plantilla": 1, "textos": TEXTOS, "capas": {"titulo": {"escala": 1.5}}}, None, None)
        grande = pincel.evaluar(G._CAJAS)["cajas"]["titulo"]
        _, _, _ = G.pintar(pincel, {"plantilla": 1, "textos": TEXTOS}, None, None)
        ok(grande["h"] > pincel.evaluar(G._CAJAS)["cajas"]["titulo"]["h"], "el tamaño cambia de verdad")
    finally:
        pincel.cerrar()
    print("imágenes y piezas")
    ok(falla(G.guardar_imagen, raiz, "cli", b"esto no es una imagen"), "un fichero que no es imagen se rechaza")
    nombre = G.guardar_imagen(raiz, "cli", imagen_de_prueba("RGBA"))
    ok(G.ruta_imagen(raiz, "cli", nombre), "la imagen con transparencia se normaliza")
    ok(G.ruta_imagen(raiz, "otro", nombre) is None, "la imagen de un proyecto no se ve desde otro")
    ok(G.ruta_imagen(raiz, "cli", "../../x") is None, "ni con una ruta rara")
    grande = G.guardar_imagen(raiz, "cli", imagen_de_prueba("RGB", (5000, 1000)))
    from PIL import Image
    ok(max(Image.open(G.ruta_imagen(raiz, "cli", grande)).size) == G.LADO_MAX_IMAGEN, "una imagen enorme se reduce")
    ficha = G.guardar_pieza(raiz, "cli", {"plantilla": 3, "formato": "h916", "imagen": nombre, "textos": TEXTOS})
    ok(os.path.isfile(G.ruta_final(raiz, "cli", ficha["id"], "png")), "guardar deja el PNG")
    ok(os.path.isfile(G.ruta_final(raiz, "cli", ficha["id"], "jpg")), "y el JPG")
    ok(ficha["medida"] == "1080×1920", "con su medida")
    ok(falla(G.ruta_final, raiz, "cli", ficha["id"], "exe"), "no se descarga otra cosa")
    ok(falla(G.ruta_final, raiz, "cli", "../..", "png"), "ni con una ruta rara")
    otra = G.guardar_pieza(raiz, "cli", dict(ficha, textos=dict(TEXTOS, titulo="Otro título")), ficha["id"])
    ok(otra["id"] == ficha["id"] and otra["textos"]["titulo"] == "Otro título", "cambiar conserva la pieza")
    ok([p["id"] for p in G.listar_piezas(raiz, "cli")] == [ficha["id"]], "la lista la tiene una vez")
    ok(G.listar_piezas(raiz, "otro") == [], "y otro proyecto no la ve")
    ok(falla(G.guardar_pieza, raiz, "cli", {"plantilla": 1}, "000000000000"), "cambiar una que no existe avisa")
    resultado = G.vistas(raiz, "cli", {"plantilla": 3, "imagen": nombre, "textos": TEXTOS}, [1, 3])
    ok(len(resultado["vistas"]) == 2 and resultado["grande"]["img"].startswith("data:image/jpeg"), "las vistas devuelven miniaturas y la grande")
    G.borrar_pieza(raiz, "cli", ficha["id"])
    ok(G.listar_piezas(raiz, "cli") == [], "borrar la quita")
    ok(json.dumps(G.catalogo()) and len(G.catalogo()["formatos"]) == 8, "el catálogo se puede enviar a la pantalla")


def main():
    raiz = tempfile.mkdtemp(prefix="prueba_graficas_")
    try:
        datos_y_kit(raiz)
        la_pagina()
        ruta = G.guardar_imagen(raiz, "cli", imagen_de_prueba())
        en_el_navegador(G.ruta_imagen(raiz, "cli", ruta))
        las_piezas(raiz)
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

"""
LA PORTADA PROPUESTA EN EL GUION DE LA PARRILLA (rama portada-en-guion, 04-11-2026).

El dueño quiere que el guion de la Parrilla traiga, si hace falta, cómo es su
portada (el texto grande y la imagen de fondo), y que en Publicar → Portada se
pueda crear esa portada con un clic o hacer otra. La IA dibuja SOLO el fondo y
el texto lo pone el Studio encima (opción A del dueño, sin faltas).

Lo que se comprueba, en memoria y sin el CLI ni pagar nada:

  1. LA PARRILLA lee la sección PORTADA (texto e imagen, varias líneas, con
     comillas o con los huecos de la plantilla) y no la confunde con un
     «Portada» suelto en minúsculas.
  2. EL ENCARGO recibe la portada; sin imagen no hay portada y se avisa.
  3. UN GUION LEÍDO ANTES DE ESTA RAMA se vuelve a leer al pasar al Encargo.
  4. PUBLICAR la guarda limpia en la ficha del vídeo, la deja corregir y no la
     deja sin descripción.
  5. AL CREAR EL VÍDEO (app.py) va a la ficha de Publicar y no escribe ningún
     param (regla 1).

    python pasos/prueba_portada_guion.py
"""
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import parrilla as P  # noqa: E402
import publicar as PUB  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"      FALLO: {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}\n             esperado {esperado!r}\n             obtenido {obtenido!r}")


def seccion(titulo):
    print(f"\n{titulo}")


GUION = """G07 — Tu baño en tres días
Cliente / proyecto: Reformas
Uso: exacto
Formato: vertical
Duración: 30 s

ESCENA 1
Visual: un baño viejo con azulejos rotos
Voz: «Este baño tenía treinta años.»
Texto en pantalla: Antes

ESCENA 2
Visual: el baño reformado con mampara de vidrio
Voz: «Tres días después, así quedó.»

CIERRE DE MARCA: Reformas Lima

PORTADA
- Texto: «Tu baño en 3 días»
- Imagen: baño reformado con mampara de vidrio y luz cálida,
  plano general desde la puerta

MARCA DEL CLIENTE
- Mostrar: el antes y el después
- Evitar: personas

PARA EL ENCARGO
- Material: Este baño tenía treinta años. Tres días después, así quedó.
- Indicaciones: tono directo
- Llamadas a la acción: escríbenos
- Duración: 30 s · Formato: vertical

AVISOS
- ninguno
"""


def prueba_parrilla():
    seccion("1] la Parrilla lee la sección PORTADA")
    g = P.leer_guion(GUION)
    igual(g["portada"], {"texto": "Tu baño en 3 días",
                         "imagen": "baño reformado con mampara de vidrio y luz cálida, plano general desde la puerta"},
          "texto sin comillas e imagen en dos líneas")
    igual(g["marca"]["mostrar"], "el antes y el después", "la sección de después (MARCA) se sigue leyendo")
    igual(g["cierre"], "Reformas Lima", "y el cierre de antes no se come la portada")
    igual(len(g["escenas"]), 2, "las escenas siguen siendo dos")
    sin = P.leer_guion(GUION.split("PORTADA")[0] + "MARCA DEL CLIENTE\n- Mostrar: x\n")
    igual(sin["portada"], {}, "un guion sin PORTADA no trae portada")
    plantilla = P.leer_guion(GUION.split("PORTADA")[0]
                             + "PORTADA (opcional; si no, quita esta sección)\n"
                             "- Texto: [2–5 palabras grandes para la portada]\n"
                             "- Imagen: [la imagen de fondo: quién o qué sale, dónde, encuadre y luz; sin letras]\n")
    igual(plantilla["portada"], {}, "los huecos de la plantilla no son una portada")
    minus = P.leer_guion(GUION.replace("CIERRE DE MARCA: Reformas Lima\n\nPORTADA",
                                       "CIERRE DE MARCA: Reformas Lima\nPortada de la marca"))
    igual(minus["portada"], {}, "«Portada» en minúsculas no abre la sección")
    otra = P.leer_guion(GUION.replace("- Texto:", "- Titular:").replace("- Imagen:", "- Fondo:"))
    ok(otra["portada"].get("texto") == "Tu baño en 3 días" and otra["portada"].get("imagen", "").startswith("baño"),
       "también vale «Titular:» y «Fondo:»")
    solo_texto = P.leer_guion(GUION.replace("- Imagen: baño reformado con mampara de vidrio y luz cálida,\n"
                                            "  plano general desde la puerta\n", ""))
    igual(solo_texto["portada"], {"texto": "Tu baño en 3 días"}, "sin imagen solo queda el texto")
    larga = P.leer_guion(GUION.replace("- Texto: «Tu baño en 3 días»", "- Texto: " + "x" * 300))
    igual(len(larga["portada"]["texto"]), P.MAX_TEXTO_PORTADA, "un texto larguísimo se corta")
    ok("PORTADA (opcional" in P._FORMATO_SALIDA and "12. PORTADA" in P._REGLAS,
       "las instrucciones de la Parrilla piden la sección y explican la regla")
    return g


def prueba_encargo(g):
    seccion("2] el Encargo recibe la portada")
    enc = P.encargo_de(g)
    igual(enc.get("portada"), g["portada"], "la portada viaja al Encargo")
    sin = P.encargo_de(P.leer_guion(GUION.split("PORTADA")[0]))
    ok("portada" not in sin, "sin PORTADA el Encargo no trae la clave")
    solo_texto = P.encargo_de({**g, "portada": {"texto": "Hola"}})
    ok("portada" not in solo_texto and any("PORTADA" in a for a in solo_texto["avisos"]),
       "con texto y sin imagen: no hay portada y se avisa")


def prueba_guion_viejo():
    seccion("3] un guion leído antes de esta rama")
    raiz = tempfile.mkdtemp(prefix="estudio_pg_")
    cid = "c1"
    P._guardar(raiz, cid, {"matrices": [{"id": "m1", "guiones": [
        {"id": "g1", "texto": GUION, "estado": "nuevo"}]}]})
    datos = P._leer(raiz, cid)
    g0 = datos["matrices"][0]["guiones"][0]
    viejo = dict(P.leer_guion(GUION))
    viejo.pop("portada", None)
    g0["leido"] = viejo
    P._guardar(raiz, cid, datos)
    try:
        enc = P.pasar_al_encargo(raiz, cid, "g1")
    except Exception as fallo:                               # noqa: BLE001
        ok(False, f"pasar al Encargo un guion viejo falla: {fallo}")
        return
    ok((enc.get("portada") or {}).get("imagen", "").startswith("baño"),
       "se vuelve a leer y pasa al Encargo con su portada")


def prueba_publicar():
    seccion("4] la ficha de Publicar")
    igual(PUB.limpiar_portada_guion({"texto": "  a   b ", "imagen": " una   sala "}),
          {"texto": "a b", "imagen": "una sala"}, "limpia los espacios")
    igual(PUB.limpiar_portada_guion({"texto": "x", "imagen": ""}), {}, "sin imagen no hay portada")
    igual(PUB.limpiar_portada_guion("no"), {}, "lo que no es un objeto, nada")
    igual(len(PUB.limpiar_portada_guion({"imagen": "y" * 2000})["imagen"]), PUB.MAX_IMAGEN_PORTADA_GUION,
          "una descripción larguísima se corta")
    raiz = tempfile.mkdtemp(prefix="estudio_pgp_")
    igual(PUB.guardar_portada_guion(raiz, "video_1", {"texto": "t"}), {}, "sin imagen no se guarda nada")
    ok("portada_guion" not in PUB._leer_video(raiz, "video_1"), "y la ficha no gana el campo")
    PUB.guardar_portada_guion(raiz, "video_1", {"texto": "Tu baño", "imagen": "un baño"})
    igual(PUB._leer_video(raiz, "video_1").get("portada_guion"),
          {"texto": "Tu baño", "imagen": "un baño", "origen": "parrilla"}, "se guarda con su origen")
    PUB.guardar_ficha(raiz, "video_1", {"portada_guion": {"texto": "Otro", "imagen": "otra"}})
    igual(PUB._leer_video(raiz, "video_1").get("portada_guion"),
          {"texto": "Otro", "imagen": "otra", "origen": "parrilla"}, "corregirla conserva el origen")
    for malo, que in (({"texto": "x", "imagen": "  "}, "sin descripción"), ("no", "que no es un objeto")):
        try:
            PUB.guardar_ficha(raiz, "video_1", {"portada_guion": malo})
            ok(False, f"una portada {que} se rechaza")
        except PUB.ErrorPublicar:
            ok(True, f"una portada {que} se rechaza")
    igual(PUB._leer_video(raiz, "video_1").get("portada_guion", {}).get("imagen"), "otra",
          "y lo rechazado no toca lo guardado")


def prueba_al_crear():
    seccion("5] al crear el vídeo (app.py)")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    from nucleo import Estado, Proyecto                           # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_pgc_")
    servidor.fijar_raiz_proyectos(base)
    pid = Proyecto.crear(base, "con portada").id
    Estado(servidor.contexto(pid).proyecto)
    ctx = servidor.contexto(pid)
    antes = repr(ctx.estado.params("assets"))
    avisos = servidor._portada_guion_al_crear(ctx, {"portada": {"texto": "Hola", "imagen": "una sala"}})
    igual(avisos, [], "sin avisos")
    igual(servidor._publicar()._leer_video(base, pid).get("portada_guion"),
          {"texto": "Hola", "imagen": "una sala", "origen": "parrilla"}, "la portada va a la ficha de Publicar")
    igual(repr(ctx.estado.params("assets")), antes, "y no escribe ningún param (regla 1)")
    pid2 = Proyecto.crear(base, "sin portada").id
    Estado(servidor.contexto(pid2).proyecto)
    ctx2 = servidor.contexto(pid2)
    igual(servidor._portada_guion_al_crear(ctx2, {"portada": {"texto": "x"}}), [], "sin imagen: nada")
    igual(servidor._portada_guion_al_crear(ctx2, {}), [], "sin portada: nada")
    ok("portada_guion" not in servidor._publicar()._leer_video(base, pid2),
       "y su ficha de Publicar no gana el campo")


def main():
    print("PRUEBA DE LA PORTADA PROPUESTA EN EL GUION")
    g = prueba_parrilla()
    prueba_encargo(g)
    prueba_guion_viejo()
    prueba_publicar()
    prueba_al_crear()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PORTADA DEL GUION OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

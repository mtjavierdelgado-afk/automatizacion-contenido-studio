"""Prueba de graficas-facil (26-11-2026): «+ Crear» en 3 pasos y «Escríbelo por mí».

    python pasos/prueba_graficas_facil.py

- las reglas del servidor sobre lo que escribe la IA (tipos, cifras, precios,
  comparativa, JSON roto, topes) con respuestas simuladas, buenas y malas;
- que lo escrito se monta y se pinta sin choques en las 16 familias;
- las miniaturas de estilo (tandas, cache) y la creación de la pieza.

Necesita el navegador que pinta las gráficas (ESTUDIO_EDGE). No llama a Claude.
"""
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ["ESTUDIO_SIN_DESCARGAS"] = "1"

import graficas as G                    # noqa: E402
import graficas_capas as C              # noqa: E402
import graficas_carrusel as K           # noqa: E402
import graficas_escribir as E           # noqa: E402

CUENTA = {"ok": 0, "mal": 0}


def ok(cond, que):
    if cond:
        CUENTA["ok"] += 1
    else:
        CUENTA["mal"] += 1
        print(f"  MAL: {que}")


def falla(fn, *a, **k):
    try:
        fn(*a, **k)
        return ""
    except G.ErrorGraficas as e:
        return str(e) or "error"


TEMA = "5 errores al alquilar una consola para una fiesta"
NEGOCIO = "EstadoPlay: alquiler de consolas para fiestas en Lima. Pack fiesta S/ 250 por día. Envío gratis en La Molina."


def respuesta(laminas):
    return json.dumps({"laminas": laminas}, ensure_ascii=False)


BUENA = [
    {"tipo": "portada", "titulo": "5 errores al alquilar una consola", "apoyo": "Y cómo evitarlos en tu fiesta"},
    {"tipo": "punto", "numero": "9", "titulo": "No probar los mandos", "texto": "Pruébalos todos antes de que lleguen los invitados."},
    {"tipo": "lista", "titulo": "Lo que no puede faltar", "v1": "Pantalla grande", "v2": "4 mandos", "v3": "Juegos para varios"},
    {"tipo": "pregunta", "pregunta": "¿Sabes cuántos mandos necesitas?", "texto": "La respuesta, en la siguiente"},
    {"tipo": "comparativa", "titulo": "¿Por qué con nosotros?", "etiqueta1": "EstadoPlay", "etiqueta2": "PlayRent SAC",
     "v1": "Instalación incluida", "v2": "Juegos al día"},
    {"tipo": "cita", "cita": "«El mejor cumpleaños de mi hijo»", "autor": "Ana, mamá de Lucas"},
    {"tipo": "cierre", "titulo": "¿Te sirvió?", "texto": "Guárdalo para tu próxima fiesta.", "cta": "Escríbenos"},
]


def reglas():
    print("«Escríbelo por mí»: las reglas del servidor")
    piezas, avisos = E.escribir("carrusel", TEMA, NEGOCIO, 7, lambda _i: respuesta(BUENA))
    tipos = [t for t, _ in piezas]
    ok(tipos[0] == "portada" and tipos[-1] == "cierre", f"portada primero y cierre al final ({tipos})")
    ok("cita" not in tipos, "nunca una Cita: sería un testimonio falso")
    comp = next(t for tipo, t in piezas if tipo == "comparativa")
    ok(comp["etiqueta1"] == "Nosotros" and comp["etiqueta2"] == "Lo de siempre", "la comparativa nunca nombra a otra marca")
    ok(not any("PlayRent" in v for _t, t in piezas for v in t.values()), "el nombre del competidor no sale por ningún lado")
    ok([t["numero"] for tipo, t in piezas if tipo == "punto"] == ["01"], "los puntos se numeran en orden (no los de la IA)")
    ok(not avisos, f"sin cifras inventadas, sin avisos ({avisos})")
    ok(any(t.get("titulo") == "5 errores al alquilar una consola" for _x, t in piezas), "«5 errores» (un número que cuenta) se queda")
    ok(any(t.get("v2") == "4 mandos" for _x, t in piezas), "«4 mandos» se queda")

    # cifras inventadas: moneda, %, x de y, veces, 3+ dígitos
    inventadas = [
        {"tipo": "portada", "titulo": "Alquila desde S/ 99", "apoyo": "El 90 % de las fiestas lo repite"},
        {"tipo": "punto", "titulo": "8 de 10 familias lo prefieren", "texto": "Y 3 veces más divertido, con 1500 juegos."},
        {"tipo": "dato", "cifra": "8 de 10", "texto": "fiestas piden otra consola"},
        {"tipo": "precio", "titulo": "Pack fiesta", "precio_antes": "S/ 400", "precio": "S/ 199", "cta": "Resérvalo"},
        {"tipo": "cierre", "titulo": "¿Te sirvió?", "texto": "Escríbenos", "cta": "Escríbenos"},
    ]
    piezas, avisos = E.escribir("carrusel", TEMA, "", 7, lambda _i: respuesta(inventadas))
    textos = " ".join(v for _t, t in piezas for v in t.values())
    ok(not re.search(r"S/\s*99|90 %|8 de 10|3 veces|1500", textos), f"ninguna cifra inventada sale ({textos[:200]})")
    ok(piezas[0][1]["titulo"] == "Tu titular aquí", "un titular con un precio inventado vuelve a su texto de muestra")
    ok(not any(t == "dato" for t, _ in piezas), "sin cifra dada, no hay lámina de Dato")
    ok(not any(t == "precio" for t, _ in piezas), "sin precio dado, no hay lámina de Precio")
    ok(avisos and "cifra" in avisos[0], "y se avisa de los textos que volvieron a muestra")
    # con el precio en la ficha, sí
    con_precio = [{"tipo": "portada", "titulo": "Tu fiesta con consola"},
                  {"tipo": "precio", "titulo": "Pack fiesta", "precio": "S/ 250", "texto": "Por día", "cta": "Resérvalo"},
                  {"tipo": "dato", "cifra": "S/ 250", "texto": "por un día entero"},
                  {"tipo": "cierre", "titulo": "¿Hablamos?", "cta": "Escríbenos"}]
    piezas, avisos = E.escribir("carrusel", TEMA, NEGOCIO, 7, lambda _i: respuesta(con_precio))
    precio = next((t for tipo, t in piezas if tipo == "precio"), None)
    ok(precio is not None and precio["precio"] == "S/ 250", "con el precio en la ficha, la lámina de Precio sale con ESE precio")
    ok(any(t == "dato" for t, _ in piezas), "y un Dato con una cifra de la ficha también")
    ok(E.cifras_que_no_estan("S/250 el día", "Pack a S/ 250") == [], "«S/250» casa con «S/ 250»")
    ok(E.cifras_que_no_estan("1.299 soles", "S/ 1 299") == [], "«1.299 soles» casa con «S/ 1 299»")
    ok(E.cifras_que_no_estan("Paso 2: los 3 juegos #1", "") == [], "los números que cuentan o numeran no son cifras")
    ok(E.cifras_que_no_estan("el 100% gratis", "") != [], "un % sí")

    # publicación e historia: una sola imagen
    piezas, _a = E.escribir("publicacion", TEMA, NEGOCIO, 7, lambda _i: respuesta(BUENA))
    ok(len(piezas) == 1 and piezas[0][0] == "portada", "una publicación es una sola imagen")
    piezas, _a = E.escribir("historia", TEMA, NEGOCIO, 7, lambda _i: respuesta([]))
    ok(len(piezas) == 1 and piezas[0][1]["titulo"] == TEMA[:80] or len(piezas) == 1, "sin nada útil, la portada sale del tema")

    # cuántas: de 3 a 10, y los textos con su tope
    muchas = [{"tipo": "portada", "titulo": "Hola"}] + [{"tipo": "punto", "titulo": f"Idea {i}", "texto": "x" * 400} for i in range(20)]
    piezas, _a = E.escribir("carrusel", TEMA, "", 5, lambda _i: respuesta(muchas))
    ok(len(piezas) == 5, f"«cuántas» manda ({len(piezas)})")
    ok(all(len(v) <= E.TOPES.get(k, 80) + 1 for _t, t in piezas for k, v in t.items()), "cada texto con su tope")
    piezas, _a = E.escribir("carrusel", TEMA, "", 99, lambda _i: respuesta(muchas))
    ok(len(piezas) == E.CUANTAS_MAX, "como mucho 10")

    # tipos que no existen y basura
    raras = [{"tipo": "portada", "titulo": "Hola<script>"}, {"tipo": "video"}, "nada", {"tipo": "punto", "titulo": "Bien"},
             {"tipo": "lista", "titulo": "Vacía"}, {"tipo": "cierre"}]
    piezas, _a = E.escribir("carrusel", TEMA, "", 7, lambda _i: respuesta(raras))
    ok([t for t, _ in piezas] == ["portada", "punto", "cierre"], f"lo raro y lo vacío se descarta ({[t for t, _ in piezas]})")
    ok("<" not in piezas[0][1]["titulo"], "sin etiquetas")

    # JSON roto: un reintento
    vueltas = []

    def una_mala(_i):
        vueltas.append(1)
        return "lo siento, no puedo" if len(vueltas) == 1 else respuesta(BUENA)
    piezas, _a = E.escribir("carrusel", TEMA, "", 7, una_mala)
    ok(len(vueltas) == 2 and piezas, "un JSON roto se pide otra vez, una sola")
    vueltas.clear()
    msg = falla(E.escribir, "carrusel", TEMA, "", 7, lambda _i: vueltas.append(1) or "nada")
    ok(len(vueltas) == 2 and "prueba otra vez" in msg, f"dos veces roto: una frase clara ({msg})")
    ok("una publicación" in falla(E.escribir, "video", TEMA, "", 7, lambda _i: ""), "solo publicación, carrusel o historia")
    ok("de qué trata" in falla(E.escribir, "carrusel", " ", "", 7, lambda _i: ""), "sin tema, se pide")
    ok("largo" in falla(E.escribir, "carrusel", "x" * 700, "", 7, lambda _i: ""), "un tema enorme se rechaza")
    ins = E.instruccion("carrusel", TEMA, NEGOCIO, 7)
    ok("NUNCA inventes testimonios" in ins and "cita" not in ins.split("Tipos que puedes usar")[1].split("\n")[0],
       "el prompt pide no inventar y no ofrece la Cita")


def montaje(pincel):
    print("lo escrito se monta y se pinta sin choques en las 16 familias")
    import graficas_crear as CR                             # noqa: PLC0415
    piezas, _a = E.escribir("carrusel", TEMA, NEGOCIO, 7, lambda _i: respuesta(BUENA + [
        {"tipo": "checklist", "titulo": "Antes de la fiesta", "v1": "Mandos cargados", "v2": "Juegos instalados"},
        {"tipo": "mito", "mito": "Alquilar es complicado", "realidad": "Lo llevamos e instalamos nosotros"}]))
    for n in sorted(K.FAMILIAS):
        for que in ("carrusel", "publicacion", "historia"):
            doc, avisos = CR.crear(pincel, que, n, None, piezas, "", None, None, None, "EstadoPlay")
            esperado = len(piezas) if que == "carrusel" else 1
            ok(len(doc["laminas"]) == esperado, f"{que} en la familia {n}: {esperado} imagen(es)")
            ok(doc["formato"] == CR.FORMATO_DE[que], f"{que}: su tamaño ({doc['formato']})")
            ok(all(lam.get("familia") == n for lam in doc["laminas"]), f"{que} {n}: con su familia")
            if que != "carrusel":
                ok(not any(c.get("enlace") for c in doc["laminas"][0]["capas"]), f"{que} {n}: sin marca/número/«Desliza» de carrusel")
                ok(not any(c["tipo"] == "texto" and "Desliza" in c.get("txt", "") for c in doc["laminas"][0]["capas"]),
                   f"{que} {n}: una sola imagen no dice «Desliza»")
            for i in ((0, len(doc["laminas"]) - 1) if que == "carrusel" else (0,)):
                _png, _av, medida = C.pintar(pincel, doc, None, lambda _n: None, None, None, i)
                ok(not medida["fuera"] and not medida["choca"], f"{que} {n} imagen {i + 1}: nada tapado ni encimado {medida}")
    ok(CR.orden_de_familias(True)[0] in CR.CON_FOTO and CR.orden_de_familias(False) == sorted(K.FAMILIAS),
       "con foto, primero los estilos que la usan")
    doc, avisos = CR.crear(pincel, "publicacion", 2, None, piezas, "img_0123456789abcdef.jpg")
    ok(any(c["tipo"] == "imagen" and c.get("rol") == "foto" and c["src"] == "img_0123456789abcdef.jpg"
           for c in doc["laminas"][0]["capas"]) and not any("foto" in a for a in avisos), "la foto elegida va en la foto de la portada")
    ok(any("frase de apoyo" in a and "lámina" not in a for a in avisos), "y el aviso del apoyo se dice sin hablar de láminas")
    doc, avisos = CR.crear(pincel, "publicacion", 1, None, piezas, "img_0123456789abcdef.jpg")
    ok(avisos and "no lleva foto" in avisos[0], "un estilo sin foto lo dice")
    ok("esa foto" in falla(CR.crear, pincel, "publicacion", 2, None, piezas, "../x.jpg"), "una foto con ruta rara se rechaza")
    ok("portada" in falla(CR.crear, pincel, "carrusel", 2, None, [("punto", {"titulo": "x"})]), "sin portada, error claro")
    ok(CR.miniatura(pincel, 10, "carrusel", None, "Hola")[:3] == b"\xff\xd8\xff", "una miniatura es un JPG")


def por_la_api():
    print("las rutas: escribir (trabajo), miniaturas (en tandas y en cache) y crear")
    import shutil, tempfile, time                           # noqa: E401,PLC0415
    import requests                                         # noqa: PLC0415
    import prueba_graficas_carrusel as P                    # noqa: PLC0415
    carpeta = tempfile.mkdtemp(prefix="graficas_facil_")
    os.makedirs(os.path.join(carpeta, "proyectos"), exist_ok=True)
    proceso, base = P._arrancar(carpeta)
    try:
        d = requests.post(base + "/api/clientes", json={"nombre": "Fácil"}, timeout=30).json()
        cid = d.get("id") or (d.get("cliente") or {}).get("id")
        r = requests.post(base + f"/api/graficas/{cid}/escribir", json={"que": "carrusel", "tema": TEMA, "cuantas": 6}, timeout=30)
        ok(r.status_code == 202 and r.json().get("trabajo"), f"«Escríbelo por mí» es un trabajo (202): {r.status_code}")
        r2 = requests.post(base + f"/api/graficas/{cid}/escribir", json={"que": "carrusel", "tema": TEMA}, timeout=30)
        ok(r2.status_code in (202, 409), "un segundo a la vez: 409 (o ya terminó el primero)")
        tid, estado = r.json().get("trabajo"), {}
        limite = time.time() + 60
        while time.time() < limite:
            estado = requests.get(base + f"/api/graficas/{cid}/capas/trabajo/{tid}", timeout=30).json()
            if estado.get("estado") != "pintando":
                break
            time.sleep(0.3)
        piezas = (estado.get("resultado") or {}).get("piezas") or []
        ok(estado.get("estado") == "listo" and piezas and piezas[0][0] == "portada" and piezas[0][1]["titulo"] == TEMA[:70],
           f"devuelve las piezas con el tema de titular ({estado})")
        ok(not any(p[0] == "cita" for p in piezas), "sin la Cita que la IA metió")
        ok(requests.post(base + f"/api/graficas/{cid}/escribir", json={"que": "video", "tema": TEMA}, timeout=30).status_code == 400,
           "un «qué» raro: 400 al momento")
        t0 = time.time()
        r = requests.post(base + f"/api/graficas/{cid}/capas/miniaturas",
                          json={"que": "carrusel", "titulo": "Hola", "familias": [1, 2, 3, 4]}, timeout=120)
        primera = time.time() - t0
        m = r.json().get("miniaturas") or []
        ok(r.status_code == 200 and [x["n"] for x in m] == [1, 2, 3, 4] and all(x["jpg"].startswith("data:image/jpeg") for x in m),
           f"4 miniaturas con su nombre ({r.status_code})")
        t0 = time.time()
        requests.post(base + f"/api/graficas/{cid}/capas/miniaturas", json={"que": "carrusel", "titulo": "Hola", "familias": [1, 2, 3, 4]}, timeout=60)
        ok(time.time() - t0 < max(0.5, primera / 3), f"la segunda vez salen de la cache ({primera:.2f} s y luego {time.time() - t0:.2f} s)")
        ok(requests.post(base + f"/api/graficas/{cid}/capas/miniaturas", json={"que": "carrusel", "titulo": "x", "familias": [1, 2, 3, 4, 5]},
                         timeout=30).status_code == 400, "más de 4 por tanda: 400")
        r = requests.post(base + f"/api/graficas/{cid}/capas/crear", json={"que": "carrusel", "familia": 16, "piezas": piezas}, timeout=60)
        doc = r.json().get("doc") or {}
        ok(r.status_code == 200 and len(doc.get("laminas", [])) == len(piezas) and doc["laminas"][0]["familia"] == 16,
           f"«Crear» monta el carrusel sin guardarlo ({r.status_code})")
        ok(requests.get(base + f"/api/graficas/{cid}/piezas", timeout=30).json().get("piezas") == [], "y no guarda nada")
        r = requests.post(base + f"/api/graficas/{cid}/capas/crear", json={"que": "historia", "familia": 3, "texto": "Mi titular\n\nUna frase"}, timeout=60)
        ok(r.status_code == 200 and r.json()["doc"]["formato"] == "h916", "con texto escrito a mano también (historia en 9:16)")
        ok(requests.post(base + f"/api/graficas/{cid}/capas/crear", json={"que": "carrusel", "familia": 3}, timeout=30).status_code == 400,
           "sin texto ni piezas: 400")
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except Exception:                                   # noqa: BLE001
            proceso.kill()
        shutil.rmtree(carpeta, ignore_errors=True)


def main():
    reglas()
    pincel = G.Pincel()
    try:
        montaje(pincel)
    finally:
        pincel.cerrar()
    por_la_api()
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

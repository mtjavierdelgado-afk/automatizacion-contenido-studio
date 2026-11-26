"""Pruebas de la rama graficas-desde-video (26-11-2026).

Parte 1: la foto tenue de fondo en cualquier imagen del carrusel (capa
«foto_fondo» con su opacidad calculada): el orden de las capas tras montar,
cambiar de estilo y hacer historias; el contraste con Kits al azar y la foto
más desfavorable; la portada que pasa del hueco al fondo y al revés; quitarla;
y la nota.
Parte 2: «Crear desde un vídeo» (la lectura del vídeo y las reglas).

Uso: python pasos/prueba_graficas_desde_video.py
"""
import io
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import graficas as G                                        # noqa: E402
import graficas_capas as C                                  # noqa: E402
import graficas_carrusel as K                               # noqa: E402
import graficas_crear as CR                                 # noqa: E402

BIEN = []
MAL = []
FOTO = "img_0123456789abcdef.jpg"
FOTO2 = "img_fedcba9876543210.jpg"


def ok(cond, que):
    (BIEN if cond else MAL).append(que)
    if not cond:
        print(f"  MAL: {que}")


def falla(fn, *a, **k):
    try:
        fn(*a, **k)
    except G.ErrorGraficas as e:
        return str(e)
    return ""


def _kit_al_azar(rnd):
    """Un Kit cualquiera; la mitad, con colores que llegan justo a 4,5:1."""
    def color():
        return "#{:02X}{:02X}{:02X}".format(*(rnd.randint(0, 255) for _ in range(3)))
    colores = {r: color() for r in K.ROLES_KIT}
    if rnd.random() < 0.5:
        # un principal justo en el límite sobre el claro
        claro = colores["claro"]
        for _ in range(400):
            c = color()
            if 4.5 <= G.contraste(c, claro) <= 4.7:
                colores["principal"] = c
                break
    return {"colores": colores}


def _orden_ok(doc, i):
    capas = doc["laminas"][i]["capas"]
    fotos = [j for j, c in enumerate(capas) if c.get("rol") == K.FOTO_FONDO]
    if not fotos:
        return True
    sin = [c for c in capas if c.get("rol") != K.FOTO_FONDO]
    return len(fotos) == 1 and fotos[0] == K._indice_tras_fondo(sin)


def _imagen(ruta, tono):
    from PIL import Image                                   # noqa: PLC0415
    Image.new("RGB", (900, 1100), tono).save(ruta)


def _rgb_de(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _luz(rgb):
    """La luminancia relativa de WCAG, escrita aquí aparte (no la del módulo)."""
    def canal(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _peor_contraste(imagen, caja, tinta):
    """El contraste más bajo entre la letra y cualquier píxel del fondo de su caja."""
    x0, y0, x1, y1 = caja
    trozo = imagen.crop((max(0, x0), max(0, y0), max(x0 + 1, x1), max(y0 + 1, y1)))
    lt = _luz(tinta)
    peor = 99.0
    for px in set(trozo.getdata()):
        a, b = sorted((lt, _luz(px)), reverse=True)
        peor = min(peor, (a + 0.05) / (b + 0.05))
    return peor


def parte_1(pincel):
    print("la foto de fondo: orden, contraste, portada, quitar y nota")
    carpeta = tempfile.mkdtemp(prefix="desde_video_")
    blanca, negra = os.path.join(carpeta, FOTO), os.path.join(carpeta, FOTO2)
    _imagen(blanca, (255, 255, 255))
    _imagen(negra, (0, 0, 0))
    imagen_de = {FOTO: blanca, FOTO2: negra}.get
    piezas = [("portada", {"titulo": "5 errores al alquilar"}), ("punto", {"numero": "1", "titulo": "No probar", "texto": "Pruébalos"}),
              ("lista", {"titulo": "Lo que llevar", "v1": "Mandos", "v2": "Cables"}), ("pregunta", {"pregunta": "¿Cuántos mandos?", "texto": "Depende"}),
              ("cierre", {})]
    doc, _a = CR.crear(pincel, "carrusel", 2, None, piezas, FOTO, None, None, None, "EstadoPlay", "", imagen_de)
    for i in range(1, len(doc["laminas"])):
        doc, av = K.poner_foto_fondo(doc, i, FOTO if i % 2 else FOTO2, None, imagen_de)
    con = [i for i, lam in enumerate(doc["laminas"]) if any(c.get("rol") == K.FOTO_FONDO for c in lam["capas"])]
    ok(len(con) >= 3, f"la foto de fondo se pone en las imágenes de dentro ({con})")
    ok(all(_orden_ok(doc, i) for i in range(len(doc["laminas"]))), "justo encima del Fondo, una sola")
    ok(all(K.OPAC_FOTO_MIN - 1e-9 <= c["opac"] <= K.OPAC_FOTO_MAX + 1e-9 for lam in doc["laminas"] for c in lam["capas"]
           if c.get("rol") == K.FOTO_FONDO), "con opacidad entre el mínimo y el máximo")
    ok(all(c.get("bloqueado") for lam in doc["laminas"] for c in lam["capas"] if c.get("rol") == K.FOTO_FONDO), "y bloqueada")
    # cambiar de estilo y hacer historias: sigue debajo de los textos
    for n in sorted(K.FAMILIAS):
        avisos = []
        d = K.montar_todas(pincel, doc, n, None, None, None, "EstadoPlay", avisos, imagen_de)
        ok(all(_orden_ok(d, i) for i in range(len(d["laminas"]))), f"familia {n}: la foto sigue justo encima del Fondo")
        quitadas = [i for i in con if not any(c.get("rol") == K.FOTO_FONDO for c in d["laminas"][i]["capas"])
                    and i > 0]
        dentro = [a for a in avisos if "se ha quitado" in a and not a.startswith("En la imagen 1,")]
        ok(len(quitadas) == len(dentro), f"familia {n}: cada foto quitada se dice ({quitadas}, {avisos})")
        portada = d["laminas"][0]["capas"]
        visibles = [c for c in portada if c["tipo"] == "imagen" and not c.get("oculto") and c.get("src") == FOTO]
        ocultas = [c for c in portada if c["tipo"] == "imagen" and c.get("oculto") and c.get("src")]
        ok(len(visibles) <= 1 and not ocultas, f"familia {n}: la foto de la portada, una sola y nunca oculta")
        if n in K.CON_FOTO_GRANDE:
            ok(any(c.get("rol") == "foto" and c.get("src") == FOTO for c in portada), f"familia {n}: la foto, en el hueco grande")
    hist_av = []
    h = K.historias(pincel, doc, None, None, None, "EstadoPlay", hist_av, imagen_de)
    ok(all(_orden_ok(h, i) for i in range(len(h["laminas"]))), "en las historias, también debajo de los textos")
    # la portada en los dos sentidos
    for de, a in ((1, 2), (2, 1), (2, 9), (9, 2)):
        d, _ = CR.crear(pincel, "carrusel", de, None, piezas, FOTO, None, None, None, "EP", "", imagen_de)
        d = K.montar_todas(pincel, d, a, None, None, None, "EP", [], imagen_de)
        portada = d["laminas"][0]["capas"]
        en_hueco = [c for c in portada if c.get("rol") == "foto" and c.get("src") == FOTO and not c.get("oculto")]
        de_fondo = [c for c in portada if c.get("rol") == K.FOTO_FONDO]
        ok(len(en_hueco) + len(de_fondo) == 1 and (bool(en_hueco) == (a in K.CON_FOTO_GRANDE)),
           f"portada {de}→{a}: la foto va {'al hueco' if a in K.CON_FOTO_GRANDE else 'de fondo'}, una sola")
    # quitar deja la lámina como sin foto
    d1, _ = K.poner_foto_fondo(doc, 1, FOTO, None, imagen_de)
    sin = K.quitar_foto_fondo(d1, 1)
    ok(not any(c.get("rol") == K.FOTO_FONDO for c in sin["laminas"][1]["capas"])
       and [c["id"] for c in sin["laminas"][1]["capas"]] == [c["id"] for c in d1["laminas"][1]["capas"] if c.get("rol") != K.FOTO_FONDO],
       "quitar la foto deja la imagen como estaba")
    ok("esa foto" in falla(K.poner_foto_fondo, doc, 1, "../x.jpg"), "una foto con ruta rara se rechaza")
    # la nota: subir la opacidad a mano se avisa
    d2 = C.limpiar_doc(d1)
    for c in d2["laminas"][1]["capas"]:
        if c.get("rol") == K.FOTO_FONDO:
            c["opac"] = 0.9
    nota = " ".join(a["texto"] for a in K.avisos_del_carrusel(d2, None, imagen_de))
    ok("foto de fondo de la imagen 2" in nota, "la nota avisa si la foto se subió de más a mano")
    ok("foto de fondo" not in " ".join(a["texto"] for a in K.avisos_del_carrusel(d1, None, imagen_de)), "y no si está bien")
    # el contraste, con 30 Kits al azar y la foto más desfavorable (blanca y negra)
    rnd = random.Random(26)
    peores = 0
    for k in range(30):
        kit = _kit_al_azar(rnd)
        n = rnd.choice(sorted(K.FAMILIAS))
        tipo = rnd.choice([t for t in K.TIPOS if t not in ("portada",)])
        colores = G.colores_finales(kit, {"colores": {}})
        lam = K.lamina(n, tipo, "v45", colores, None, "EP")
        base = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [lam]})
        for src in (FOTO, FOTO2):
            d, _av = K.poner_foto_fondo(base, 0, src, kit, imagen_de)
            foto = next((c for c in d["laminas"][0]["capas"] if c.get("rol") == K.FOTO_FONDO), None)
            if foto is None:
                continue
            f = G.formato("v45")
            capas = d["laminas"][0]["capas"]
            extremo = "#FFFFFF" if src == FOTO else "#000000"
            for i in K._textos_que_cuentan(capas):
                t = capas[i]
                minimo = 3 if K._es_grande(t, f) else 4.5
                tinta = C.resolver_color(t["color"], colores)
                for x, y in K._puntos(t):
                    sin = K._fondos_bajo(capas, i, x, y, colores, foto, extremo, 0)
                    con = K._fondos_bajo(capas, i, x, y, colores, foto, extremo, foto["opac"])
                    if sin is None:
                        continue
                    for fs, fc in zip(sin, con):
                        a = t.get("alfa", 1) * t.get("opac", 1)
                        antes = G.contraste(K._mezcla(tinta, fs, a), fs)
                        ahora = G.contraste(K._mezcla(tinta, fc, a), fc)
                        if ahora < min(minimo, antes) - 1e-9:
                            peores += 1
    ok(peores == 0, f"30 Kits al azar con foto blanca y negra: ningún texto baja de 4,5:1 (3:1 si es grande) ({peores})")
    # con una foto media, la opacidad sube; con blanco/negro puros sin foto a mano, el peor caso
    gris = os.path.join(carpeta, "img_1111111111111111.jpg")
    _imagen(gris, (128, 120, 110))
    lam = K.lamina(2, "punto", "v45", G.colores_finales(None, {"colores": {}}), None, "EP")
    base = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [lam]})
    d_gris, _ = K.poner_foto_fondo(base, 0, "img_1111111111111111.jpg", None, {"img_1111111111111111.jpg": gris}.get)
    d_sin, _ = K.poner_foto_fondo(base, 0, "img_1111111111111111.jpg", None, None)
    op = [next((c["opac"] for c in d["laminas"][0]["capas"] if c.get("rol") == K.FOTO_FONDO), 0) for d in (d_gris, d_sin)]
    ok(op[0] >= op[1], f"con la foto real se mide esa foto (gris {op[0]}), sin ella el peor caso ({op[1]})")
    # el peor caso de la foto, a resolución completa: una raya de luz de 2 px cuenta
    from PIL import Image                                   # noqa: PLC0415
    rayas = os.path.join(carpeta, "img_2222222222222222.jpg")
    im = Image.new("RGB", (1080, 1350), (0, 0, 0))
    for x in range(0, 1080, 40):
        for dx in range(2):
            for y in range(1350):
                im.putpixel((x + dx, y), (255, 255, 255))
    im.save(rayas, quality=100)
    foto_r = K.capa_foto_fondo("img_2222222222222222.jpg")
    bajo = K._extremos_de_foto(rayas, foto_r, G.formato("v45"))({"x": 10, "y": 10, "w": 30, "h": 10})
    ok(G.contraste(bajo[1], "#FFFFFF") < 1.2 and G.contraste(bajo[0], "#000000") < 1.2,
       f"los extremos de la foto se miden a resolución completa ({bajo})")
    # Y LO PINTADO DE VERDAD (Chromium): en la caja de cada texto, el peor píxel del
    # fondo con la foto no baja de 4,5:1 (3:1 si es grande) ni de lo que tenía sin
    # foto. Medido en el PNG, sin las cuentas del módulo.
    rayas_de = {"img_2222222222222222.jpg": rayas}.get
    colores = G.colores_finales(None, {"colores": {}})
    peores = []
    for n in (1, 2, 4, 10, 13, 16):
        for tipo in ("punto", "dato", "lista", "cierre"):
            lam = K.lamina(n, tipo, "v45", colores, None, "EP")
            base = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [lam]})
            con, _av = K.poner_foto_fondo(base, 0, "img_2222222222222222.jpg", None, rayas_de)
            if not any(c.get("rol") == K.FOTO_FONDO for c in con["laminas"][0]["capas"]):
                continue
            sin_letra = C.limpiar_doc(con)
            for c in sin_letra["laminas"][0]["capas"]:
                if c["tipo"] == "texto":
                    c["oculto"] = True
            sin_nada = K.quitar_foto_fondo(sin_letra, 0)
            fondo_con = Image.open(io.BytesIO(C.pintar(pincel, sin_letra, None, rayas_de, None, None, 0)[0])).convert("RGB")
            fondo_sin = Image.open(io.BytesIO(C.pintar(pincel, sin_nada, None, rayas_de, None, None, 0)[0])).convert("RGB")
            W, H = fondo_con.size
            for c in con["laminas"][0]["capas"]:
                if c["tipo"] != "texto" or c.get("oculto") or c.get("rol") == "deco" or not c["txt"].strip() or c.get("fondo"):
                    continue
                tinta = _rgb_de(C.resolver_color(c["color"], colores))
                caja = (int(c["x"] / 100 * W), int(c["y"] / 100 * H), int((c["x"] + c["w"]) / 100 * W), int((c["y"] + max(c["h"], 1)) / 100 * H))
                grande = c.get("tam", 4) >= 5.5 or (c.get("peso", 400) >= 700 and c.get("tam", 4) >= 4.4)
                minimo = 3 if grande else 4.5
                peor_con = _peor_contraste(fondo_con, caja, tinta)
                peor_sin = _peor_contraste(fondo_sin, caja, tinta)
                if peor_con < min(minimo, peor_sin) - 0.05:
                    peores.append((n, tipo, c["rol"], round(peor_con, 2), round(peor_sin, 2)))
    ok(not peores, f"pintado de verdad con una foto de rayas: ningún texto se lee peor de lo permitido {peores[:4]}")
    # se VE: con la foto, la imagen pintada cambia (no queda tapada por un fondo de la plantilla)
    gris_de = {"img_1111111111111111.jpg": gris}.get
    for n in (1, 8, 9, 14, 15):
        d_con, _ = CR.crear(pincel, "publicacion", n, None, [("portada", {"titulo": "Hola"})], "img_1111111111111111.jpg",
                            None, None, None, "EP", "", gris_de)
        d_sin, _ = CR.crear(pincel, "publicacion", n, None, [("portada", {"titulo": "Hola"})], "", None, None, None, "EP")
        png_con = C.pintar(pincel, d_con, None, gris_de, None, None, 0)[0]
        png_sin = C.pintar(pincel, d_sin, None, gris_de, None, None, 0)[0]
        ok(C.diferencia(png_con, png_sin) > 0.2, f"estilo {n}: la foto de fondo de la portada se ve")
    # pinta sin choques
    _png, _av, medida = C.pintar(pincel, d1, None, imagen_de, None, None, 1)
    ok(not medida["fuera"] and not medida["choca"], f"la imagen con foto de fondo pinta sin choques {medida}")


def parte_2(pincel):
    print("crear desde un vídeo: planos permitidos, cifras de la voz, planos repetidos o inventados")
    import json                                             # noqa: PLC0415
    import graficas_desde_video as D                        # noqa: PLC0415
    carpeta = tempfile.mkdtemp(prefix="desde_video_2_")
    rutas = {}
    for i, tono in enumerate([(200, 80, 40), (40, 120, 200), (200, 80, 40), (90, 200, 90), (220, 220, 60), (10, 10, 10)]):
        rutas[f"p{i}"] = os.path.join(carpeta, f"p{i}.png")
        _imagen(rutas[f"p{i}"], tono)
    plan = {"escenas": [
        {"id": "p0", "narracion": "Alquilar una consola cuesta S/ 190 la noche.", "prompt": "A living room with a console " * 20},
        {"id": "p1", "narracion": "Llevamos 4 mandos y 300 juegos.", "linea_gv": "Una sala con cuatro mandos"},
        {"id": "p2", "narracion": "La misma imagen sigue.", "prompt": "same"},          # misma imagen que p0
        {"id": "p3", "narracion": "", "prompt": "sin voz"},                           # sin narración
        {"id": "p4", "narracion": "En 2025 vinieron 300 personas.", "componente": "cartela"},
        {"id": "p5", "narracion": "Rent it for 250 soles per night.", "prompt": "night"},
        {"id": "p6", "narracion": "Sin imagen", "prompt": "x"},
    ]}
    planos = D.planos_permitidos(plan, rutas)
    sids = [p["sid"] for p in planos]
    ok(sids == ["p0", "p1", "p5"], f"permitidos: con imagen y voz, sin cartelas ni repetidas ({sids})")
    ok(all(len(p["visual"]) <= D.MAX_VISUAL for p in planos), "la descripción visual, recortada a 160")
    ok(planos[1]["visual"] == "Una sala con cuatro mandos", "en modo guion, la línea del guion visual")
    muchos = {"escenas": [{"id": f"m{i}", "narracion": "Una frase " * 30, "prompt": "x"} for i in range(200)]}
    rut = {}
    for i in range(200):
        rut[f"m{i}"] = os.path.join(carpeta, f"m{i}.png")
        _imagen(rut[f"m{i}"], (i, 255 - i, (i * 7) % 255))
    lista = D.planos_permitidos(muchos, rut)
    ok(len(lista) == D.MAX_PLANOS and lista[0]["sid"] == "m0" and lista[-1]["sid"] != "m79",
       f"tope de {D.MAX_PLANOS} planos, repartidos a lo largo del vídeo")
    ok(len(D._bloque_de_planos(lista)) <= D.MAX_LETRAS, "y dentro de las 8.000 letras")
    # las cifras de la voz
    ok(D.cifra_en_narracion("S/ 190", planos[0]["narracion"]), "«S/ 190» está en la voz de su plano")
    ok(not D.cifra_en_narracion("S/ 300", planos[1]["narracion"]), "«S/ 300» no pasa porque la voz diga «300 juegos»")
    ok(D.cifra_en_narracion("300", planos[1]["narracion"]), "un número suelto que está en la voz, sí")
    ok(D.cifra_en_narracion("S/ 250", planos[2]["narracion"]), "«S/ 250» casa con «250 soles» (voz en inglés)")
    ok(not D.cifra_en_narracion("20 %", planos[0]["narracion"]), "un % que no está, no")
    ok(not D.cifra_en_narracion("S/ 300", "cuesta 300 dólares"), "«S/ 300» no es «300 dólares» (otra moneda)")
    ok(not D.cifra_en_narracion("US$ 50", "son 50 soles"), "«US$ 50» no es «50 soles»")
    ok(D.cifra_en_narracion("$ 40", "they are 40 dollars"), "«$ 40» sí es «40 dollars»")
    ok(D.cifra_en_narracion("S/ 300", "cuesta 300 PEN") and D.cifra_en_narracion("20 %", "baja un 20%"),
       "«300 PEN» detrás del número y «20%» pegado también valen")
    r2 = {"laminas": [{"tipo": "portada", "titulo": "Hola", "plano": "p0"},
                      {"tipo": " Precio ", "titulo": "Precio", "precio": "S/ 300", "texto": "x", "plano": "p0"},
                      {"tipo": "punto", "titulo": "300 juegos", "plano": "p1"}, {"tipo": "cierre"}]}
    pz, _ = D.validar(r2, "carrusel", "x", planos, "", 7)
    ok(not any(x.get("precio") == "S/ 300" for _t, x in pz), "un tipo con espacios («␣Precio␣») no se salta la regla de cifras")
    respuesta = {"laminas": [
        {"tipo": "portada", "titulo": "Alquila tu consola", "apoyo": "Desde S/ 190 la noche", "plano": "p0", "alt": "Una sala"},
        {"tipo": "punto", "titulo": "4 mandos y 300 juegos", "texto": "Todo listo para jugar", "plano": "p1", "alt": "Mandos"},
        {"tipo": "dato", "cifra": "S/ 190", "texto": "la noche", "plano": "p1"},                     # la cifra no es de SU plano
        {"tipo": "lista", "titulo": "Lo que llevas", "v1": "Consola", "v2": "Juegos", "plano": "p1"},   # plano repetido
        {"tipo": "pregunta", "pregunta": "¿Cuántos sois?", "texto": "Dínoslo", "plano": "p4"},         # cartela: no
        {"tipo": "precio", "titulo": "Precio", "precio": "S/ 250", "texto": "la noche", "plano": "p5"},
        {"tipo": "cita", "cita": "Genial", "autor": "Ana", "plano": "p5"},
        {"tipo": "cierre", "titulo": "¿Te sirvió?", "cta": "Escríbenos"}]}
    piezas, avisos = D.validar(respuesta, "carrusel", "Alquiler de consolas", planos, "", 8)
    tipos = [t for t, _ in piezas]
    por_tipo = {t: x for t, x in piezas}
    ok(tipos[0] == "portada" and tipos[-1] == "cierre" and "cita" not in tipos, f"portada, cierre y sin citas ({tipos})")
    ok(por_tipo["portada"]["apoyo"] == "Desde S/ 190 la noche" and por_tipo["portada"]["plano"] == "p0",
       "la cifra de la voz de SU plano se queda, con su plano")
    ok(por_tipo["punto"]["plano"] == "p1" and por_tipo["punto"]["alt"] == "Mandos", "cada imagen lleva su plano y su alt")
    ok("dato" not in tipos or por_tipo["dato"].get("cifra") != "S/ 190", "una cifra de la voz de OTRO plano no pasa")
    ok(por_tipo["lista"]["plano"] == "", "un plano repetido deja esa imagen sin foto")
    ok(por_tipo["pregunta"]["plano"] == "", "una cartela (o un id que no está) deja la imagen sin foto")
    ok(por_tipo.get("precio", {}).get("precio") == "S/ 250", "el precio que dice la voz (en inglés, en soles) vale")
    ok(any("cifra" in a for a in avisos), "lo que se quitó, se dice")
    # simulado y escribir
    texto_pedido = D.instruccion("carrusel", "Mi vídeo", planos, "", 7)
    ok("SIEMPRE en español" in texto_pedido and "[p0]" in texto_pedido and "«plano»" in texto_pedido, "la instrucción lleva los planos y el idioma")
    piezas, _a = D.escribir("carrusel", "Mi vídeo", planos, "", 7, D.simulado)
    ok(piezas[0][1]["plano"] == "p0" and all(x["plano"] in ("", "p0", "p1", "p5") for _t, x in piezas), "el simulado da planos válidos")
    ok(len({x["plano"] for _t, x in piezas if x["plano"]}) == len([1 for _t, x in piezas if x["plano"]]), "y ninguno repetido")
    ok("narración suficientes" in falla(D.escribir, "carrusel", "x", planos[:2], "", 7, D.simulado), "con menos de 3 planos, lo dice")
    ok(json.loads(D.simulado(texto_pedido))["laminas"][0]["plano"] == "p0", "simulado legible")


def parte_3():
    print("cerrar «+ Crear» cancela «Escríbelo por mí» y libera el proyecto; la foto de fondo por la API")
    import shutil                                           # noqa: PLC0415
    import requests                                         # noqa: PLC0415
    import prueba_graficas_carrusel as P                    # noqa: PLC0415
    carpeta = tempfile.mkdtemp(prefix="desde_video_3_")
    os.makedirs(os.path.join(carpeta, "proyectos"), exist_ok=True)
    os.environ["ESTUDIO_SIMULAR_ESPERA"] = "4"
    try:
        proceso, base = P._arrancar(carpeta)
    finally:
        os.environ.pop("ESTUDIO_SIMULAR_ESPERA", None)
    try:
        d = requests.post(base + "/api/clientes", json={"nombre": "Desde vídeo"}, timeout=30).json()
        cid = d.get("id") or (d.get("cliente") or {}).get("id")
        cuerpo = {"que": "carrusel", "tema": "Cómo elegir una consola"}
        r = requests.post(base + f"/api/graficas/{cid}/escribir", json=cuerpo, timeout=30)
        tid = r.json().get("trabajo")
        ok(r.status_code == 202 and tid, "«Escríbelo por mí» arranca")
        ok(requests.post(base + f"/api/graficas/{cid}/escribir", json=cuerpo, timeout=30).status_code == 409, "un segundo a la vez: 409")
        ok(requests.delete(base + f"/api/graficas/{cid}/escribir/{tid}", timeout=30).status_code == 200, "cerrar lo cancela")
        t = requests.get(base + f"/api/graficas/{cid}/capas/trabajo/{tid}", timeout=30).json()
        ok(t.get("estado") == "error" and t.get("error") == "cancelado", "y queda cancelado")
        r = requests.post(base + f"/api/graficas/{cid}/escribir", json=cuerpo, timeout=30)
        ok(r.status_code == 202, "el proyecto queda libre para otro «Escríbelo por mí» al momento")
        import time                                         # noqa: PLC0415
        time.sleep(5)
        t = requests.get(base + f"/api/graficas/{cid}/capas/trabajo/{tid}", timeout=30).json()
        ok(t.get("error") == "cancelado", "lo cancelado no se pisa cuando el hilo termina")
        ok(requests.delete(base + f"/api/graficas/otro/escribir/{tid}", timeout=30).status_code in (403, 404),
           "no se cancela el trabajo de otro proyecto")
        ok(requests.get(base + f"/api/graficas/{cid}/videos/no_existe/planos", timeout=30).status_code in (403, 404),
           "un vídeo que no existe: no se lee")
        # la foto de fondo por la API (POST /capas/foto-fondo)
        from PIL import Image                               # noqa: PLC0415
        import io                                           # noqa: PLC0415
        b = io.BytesIO()
        Image.new("RGB", (300, 400), (120, 110, 100)).save(b, "PNG")
        nombre = requests.post(base + f"/api/graficas/{cid}/imagen", files={"imagen": ("f.png", b.getvalue(), "image/png")}, timeout=30).json()["nombre"]
        doc = requests.post(base + f"/api/graficas/{cid}/capas/crear", json={"que": "carrusel", "familia": 2,
                            "texto": "Titular\n\nUno\nDos\n\nTres\nCuatro"}, timeout=60).json()["doc"]
        r = requests.post(base + f"/api/graficas/{cid}/capas/foto-fondo", json={"doc": doc, "lamina": 1, "src": nombre}, timeout=60)
        doc2 = r.json().get("doc") or {}
        ok(r.status_code == 200 and any(c.get("rol") == "foto_fondo" for c in doc2["laminas"][1]["capas"]), "la foto de fondo se pone por la API")
        r = requests.post(base + f"/api/graficas/{cid}/capas/foto-fondo", json={"doc": doc2, "lamina": 1}, timeout=60)
        ok(not any(c.get("rol") == "foto_fondo" for c in r.json()["doc"]["laminas"][1]["capas"]), "y se quita")
        ok(requests.post(base + f"/api/graficas/{cid}/capas/foto-fondo", json={"doc": doc, "lamina": 1, "src": "img_ffffffffffffffff.jpg"},
                         timeout=30).status_code == 404, "una foto que no es de este proyecto: 404")
        r = requests.post(base + f"/api/graficas/{cid}/capas/crear", json={"que": "carrusel", "familia": 2,
                          "piezas": [["portada", {"titulo": "Hola", "plano": "x1"}], ["punto", {"titulo": "A", "plano": "x2"}], ["cierre", {}]]}, timeout=60)
        ok(r.status_code == 200 and not any(c.get("rol") == "foto_fondo" for lam in r.json()["doc"]["laminas"] for c in lam["capas"]),
           "sin vídeo, un «plano» mandado a mano no pone nada")
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except Exception:                                   # noqa: BLE001
            proceso.kill()
        shutil.rmtree(carpeta, ignore_errors=True)


def main():
    pincel = G.Pincel()
    try:
        parte_1(pincel)
        parte_2(pincel)
        parte_3()
    finally:
        pincel.cerrar()
    print(f"\n{len(BIEN)} comprobaciones bien, {len(MAL)} mal")
    sys.exit(1 if MAL else 0)


if __name__ == "__main__":
    main()

"""Prueba de graficas-3c-extras (25-11-2026): lo nuevo del carrusel de Gráficas.

    python pasos/prueba_graficas_extras.py

- las familias Publicación (15) y Gamer (16): su portada, sus láminas y lo que
  NO llevan (nada que imite a una red);
- la tarjeta de dentro ya no tapa la marca «en todas» (familias 3 y 15);
- los tipos de lámina nuevos, el QR, «Hacer también las historias», los iconos
  y pegatinas y los carruseles en lote (cada uno, en su apartado).

Necesita el navegador que pinta las gráficas (ESTUDIO_EDGE, como
prueba_graficas_carrusel). No sale a internet: las fuentes que falten se
sustituyen y se dice.
"""
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ["ESTUDIO_SIN_DESCARGAS"] = "1"

import graficas as G                    # noqa: E402
import graficas_capas as C              # noqa: E402
import graficas_carrusel as K           # noqa: E402
import graficas_plantillas as PL        # noqa: E402

CUENTA = {"ok": 0, "mal": 0}


def ok(cond, que):
    if cond:
        CUENTA["ok"] += 1
    else:
        CUENTA["mal"] += 1
        print(f"  MAL: {que}")


TEXTO = ("5 errores al alquilar una consola\n\nNo revisar los mandos\nPrueba cada mando en casa.\n\n"
         "- Llamar tarde\n- No pedir boleta\n- Olvidar los juegos\n\n8 de 10\nfiestas piden otra consola")
FORMATOS = ("v45", "v34", "c11", "h916", "tt", "pin", "h19", "h169")


def familias_nuevas():
    print("las familias Publicación y Gamer")
    cat = K.catalogo()
    nombres = {f["n"]: f["nombre"] for f in cat["familias"]}
    ok(nombres.get(15) == "Publicación" and nombres.get(16) == "Gamer", "las dos familias nuevas, con su nombre")
    ok(dict((n, c) for n, _nom, _u, c in G.CATALOGO)[15] == ("marca", "usuario", "titulo", "apoyo"),
       "Publicación pide nombre, @usuario, titular y texto")
    ok(G.CAMPOS.get("usuario", ("", 0))[1] == 30, "el @usuario cabe en 30 letras")
    # lo que NO lleva la de Publicación: ni insignias, ni contadores, ni iconos de red, ni su azul ni su letra
    html = PL.PLANTILLAS[15].lower()
    prohibido = ("verific", "♥", "❤", "like", "retweet", "compart", "seguidores", "hace ", "#1d9bf0", "#1877f2",
                 "#0a66c2", "segoe", "helvetica", "chirp", "svg")
    ok(not any(p in html for p in prohibido), "Publicación no imita a ninguna red (ni insignia, contadores, iconos, azul ni letra)")
    ok("«usuario»" in PL.PLANTILLAS[15] and "«img»" in PL.PLANTILLAS[15], "la tarjeta lleva la foto redonda y el @usuario")
    ok(PL.PLANTILLAS[16].count("border-top") + PL.PLANTILLAS[16].count("border-bottom") == 4,
       "Gamer lleva las cuatro esquinas")
    t = K.textos_de_portada(15, {"titulo": "Hola"}, (), "Estado Play")
    ok(t["usuario"] == "@estadoplay", "el @usuario de la portada sale del nombre de la marca")
    ok(K.textos_de_portada(15, {}, (), "")["usuario"] == "@tumarca", "sin marca, «@tumarca»")
    ok(K.textos_de_portada(15, {}, (), "Ñandú & Cía!")["usuario"] == "@nanducia", "un nombre con símbolos da un @usuario limpio")
    ok(K.textos_de_portada(15, {}, (), "Peña Café")["usuario"] == "@penacafe", "las tildes y la ñ no se pierden: se quitan los acentos (árbitro)")
    for fid in FORMATOS:
        L = K._Lienzo(K.familia(16), fid, G.COLORES_DEFECTO, "Marca")
        if L.horiz:
            continue
        esquinas = [c for c in K._fondo_y_adorno(L, "punto")[0] if c.get("nombre", "").startswith("Esquina")]
        ok(len(esquinas) == 4 and all(c["borde"] and sum(1 for a in c["borde"]["anchos"] if a) == 2 for c in esquinas),
           f"Gamer {fid}: cuatro esquinas en L")
        ok(all(0 <= c["x"] and c["x"] + c["w"] <= 100 and 0 <= c["y"] and c["y"] + c["h"] <= 100 for c in esquinas),
           f"Gamer {fid}: las esquinas no se salen")


def tarjeta_no_tapa_la_marca():
    print("la tarjeta de dentro no tapa la marca «en todas»")
    for n in (3, 15):
        for fid in FORMATOS:
            L = K._Lienzo(K.familia(n), fid, G.COLORES_DEFECTO, "EstadoPlay")
            for tipo in K.TIPOS[1:]:
                if L.horiz and tipo not in K.TIPOS_HORIZONTAL:
                    continue
                tarjeta = next((c for c in K._fondo_y_adorno(L, tipo)[0] if c.get("nombre") == "Tarjeta"), None)
                marca = K.en_todas(L)[0]
                ok(tarjeta is not None and tarjeta["y"] >= marca["y"] + marca["h"] - 0.05,
                   f"familia {n}, {fid}, {tipo}: la tarjeta empieza debajo de la marca")


def pintadas(pincel):
    print("las familias nuevas se pintan en todos los tamaños, sin letras de respaldo")
    for n in (15, 16):
        for fid in FORMATOS:
            doc = {"version": 2, "formato": fid, "laminas": [{"capas": []}]}
            doc, _av = K.carrusel_desde_texto(pincel, doc, n, TEXTO, "sustituir", None, None, None, "EstadoPlay")
            ok(len(doc["laminas"]) >= 5, f"familia {n} {fid}: el texto se parte en láminas")
            for i in (0, 1, len(doc["laminas"]) - 1):
                png, avisos, medida = C.pintar(pincel, doc, None, lambda _n: None, None, None, i)
                ok(png[:8] == b"\x89PNG\r\n\x1a\n", f"familia {n} {fid} lámina {i + 1}: sale el PNG")
                ok(not medida["fuera"] and not medida["choca"],
                   f"familia {n} {fid} lámina {i + 1}: ningún texto en lo que tapa la red ni pisando a otro {medida}")
                ok(not any("tipografía" in a for a in avisos), f"familia {n} {fid} lámina {i + 1}: con sus letras ({avisos})")

NUEVOS = ("mito", "pregunta", "ranking", "checklist", "comparativa", "precio")
LARGOS = {
    "mito": {"mito": "Alquilar una consola para una fiesta de cumpleaños infantil siempre sale más caro que comprarla",
             "realidad": "Para un solo día, alquilarla con los juegos y los mandos incluidos cuesta bastante menos"},
    "pregunta": {"pregunta": "¿Sabes cuál es el error más común al alquilar una consola para una fiesta grande?"},
    "ranking": {"titulo": "Los cinco juegos que más piden en las fiestas",
                **{f"v{i}": f"Un juego con un nombre bastante largo número {i}" for i in range(1, 6)}},
    "checklist": {"titulo": "Antes de que llegue la consola, revisa todo esto",
                  **{f"v{i}": f"Una cosa que revisar con calma antes, la número {i}" for i in range(1, 6)}},
    "comparativa": {"titulo": "¿Por qué alquilar con nosotros y no con otros?",
                    **{f"v{i}": f"Una ventaja bastante larga número {i}" for i in range(1, 6)}},
    "precio": {"titulo": "Pack fiesta: consola, cuatro mandos y diez juegos", "precio_antes": "S/ 1 250",
               "precio": "S/ 1 299,90", "texto": "Hasta el 30 de noviembre, en Lima Metropolitana, con instalación incluida",
               "cta": "Resérvalo por WhatsApp"},
}


def tipos_nuevos_sin_pintar():
    print("los 6 tipos nuevos: catálogo, roles, símbolos dibujados y la nota")
    cat = K.catalogo()
    ids = [t["id"] for t in cat["tipos"]]
    ok(all(t in ids for t in NUEVOS) and ids[0] == "portada" and ids[-1] == "cierre", "los 6 tipos, entre la portada y el cierre")
    ok(all(t in C.TIPOS_LAMINA for t in NUEVOS), "el documento los admite")
    js = open(os.path.join(AQUI, "..", "web", "graficas_editor.js"), encoding="utf-8").read()
    ok(all(re.search(rf"\b{t}: '", js) for t in NUEVOS), "el editor sabe sus nombres")
    ok(not any(t in K.TIPOS_HORIZONTAL for t in NUEVOS), "en horizontal no se ofrecen (no caben bien)")
    for t in NUEVOS:
        ok(all(k in K.ROLES for k in K.MUESTRA[t]), f"{t}: todos sus textos tienen rol (montar por tipo los lleva)")
    for n in sorted(K.FAMILIAS):
        for fid in ("v45", "c11", "h916"):
            for t in NUEVOS:
                lam = K.lamina(n, t, fid, G.COLORES_DEFECTO, LARGOS[t], "EstadoPlay")
                letras = "".join(c.get("txt", "") for c in lam["capas"] if c["tipo"] == "texto")
                ok(not re.search("[✓✗✔✘→←]", letras), f"familia {n} {fid} {t}: ✓, ✗ y → dibujados, no escritos")
                ok(len(lam["capas"]) <= C.MAX_CAPAS, f"familia {n} {fid} {t}: cabe en el tope de capas")
    # el precio de antes, tachado; y solo se guarda si lo está
    lam = K.lamina(1, "precio", "v45", G.COLORES_DEFECTO, None, "M")
    antes = [c for c in lam["capas"] if c.get("rol") == "precio_antes"]
    ok(len(antes) == 1 and antes[0].get("tachado") is True, "el precio de antes va tachado")
    doc = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [{"capas": []}, lam]})
    capas = doc["laminas"][1]["capas"]
    ok(sum(1 for c in capas if c.get("tachado")) == 1 and all("tachado" not in c for c in capas if c.get("rol") != "precio_antes"),
       "«tachado» solo se guarda en el texto que lo está (las piezas de antes no cambian)")
    html = C.html_capas(doc, None, lambda _n: None, None, None, 1)[0]
    ok(html.count("line-through") == 1, "y solo ese sale con la raya")
    # volver a montar por tipo lleva los textos a su sitio
    previa = K.lamina(3, "checklist", "v45", G.COLORES_DEFECTO, LARGOS["checklist"], "M")
    otra = K.lamina(3, "ranking", "v45", G.COLORES_DEFECTO, None, "M", previa)
    ok([c["txt"] for c in otra["capas"] if c.get("rol") in ("v1", "v5")] == [LARGOS["checklist"]["v1"], LARGOS["checklist"]["v5"]],
       "de Checklist a Ranking, los 5 puntos pasan a sus puestos")
    # la nota: avisa del precio tachado y «La respuesta, en la siguiente» no es texto de muestra
    pregunta = K.lamina(1, "pregunta", "v45", G.COLORES_DEFECTO, {"pregunta": "¿Cuánto cuesta?"}, "M")
    precio = K.lamina(1, "precio", "v45", G.COLORES_DEFECTO, LARGOS["precio"], "M")
    nota = K.avisos_del_carrusel({"version": 2, "formato": "v45", "laminas": [
        {"capas": [{"tipo": "texto", "id": "t1", "rol": "titulo", "txt": "Hola"}]}, pregunta, precio, K.lamina(1, "cierre", "v45", G.COLORES_DEFECTO)]})
    textos = " ".join(x["texto"] for x in nota)
    ok("Precio tachado en la lámina 3" in textos and "Código de Protección" in textos, "la nota recuerda que el precio de antes tiene que ser real")
    ok(not re.search(r"muestra en la lámina [^:]*\b2\b", textos), "«La respuesta, en la siguiente» sirve tal cual")


def tipos_nuevos_pintados(pincel):
    print("los 6 tipos nuevos, pintados: 16 familias, 4 tamaños, 3 Kits y textos largos")
    import prueba_graficas_carrusel as P                    # noqa: PLC0415
    malas, cuenta = [], 0
    for fid, kits in (("v45", list(P.KITS)), ("v34", ["de siempre"]), ("c11", ["de siempre"]), ("h916", ["de siempre"]),
                      ("tt", ["de siempre", "poco contraste"]), ("pin", ["de siempre"])):
        f = G.formato(fid)
        for kit_n in kits:
            kit = P.KITS[kit_n]
            colores = G.colores_finales(kit, {})
            for n in sorted(K.FAMILIAS):
                L = K._Lienzo(K.familia(n), fid, colores, "EstadoPlay")
                seguro = {"l": L.m["l"] / 100 * f["W"] - 1, "r": f["W"] - L.m["r"] / 100 * f["W"] + 1,
                          "t": L.m["t"] / 100 * f["H"] - 1, "b": f["H"] - L.m["b"] / 100 * f["H"] + 1}
                for t in NUEVOS:
                    for textos in (None, LARGOS[t]):
                        lam = K.lamina(n, t, fid, colores, textos, "EstadoPlay")
                        lam["capas"] += [dict(c) for c in K.en_todas(L)]
                        doc = C.limpiar_doc({"version": 2, "formato": fid, "laminas": [{"capas": []}, lam, {"capas": []}]})
                        documento, ff, _m, _f = C.html_capas(doc, kit, lambda _n: None, None, None, 1)
                        pincel.abrir(documento, ff["W"], ff["H"])
                        pincel.evaluar(C._AJUSTAR)
                        medida = pincel.evaluar(P._MEDIR_LAMINA)
                        lineas = pincel.evaluar(C._LINEAS_POR_CAPA)
                        cuenta += 1
                        et = f"{K.familia(n)['nombre']} · {t} · {fid} · {kit_n} · {'largos' if textos else 'muestra'}"
                        minimo = K.LETRA_MINIMA / 100 * min(ff["W"], ff["H"]) * 0.95
                        tx = medida["textos"]
                        for x in tx:
                            c = x["caja"]
                            if c["l"] < seguro["l"] or c["r"] > seguro["r"] or c["t"] < seguro["t"] or c["b"] > seguro["b"]:
                                malas.append(f"{et}: «{x['txt']}» se sale de lo útil")
                            if x.get("sale"):
                                malas.append(f"{et}: «{x['txt']}» no cabe en su caja")
                            if x["fs"] < minimo:
                                malas.append(f"{et}: «{x['txt']}» con letra de {x['fs']:.0f} px (mínimo {minimo:.0f})")
                            if x.get("fondo"):
                                grande = x["fs"] >= 0.05 * min(ff["W"], ff["H"]) or x["rol"] in ("numero", "cifra", "titulo", "precio", "pregunta")
                                if P._contraste(x["color"], x["fondo"]) < (3 if grande else 4.5):
                                    malas.append(f"{et}: «{x['txt']}» con poco contraste ({P._contraste(x['color'], x['fondo']):.1f}:1)")
                        for i in range(len(tx)):
                            for j in range(i + 1, len(tx)):
                                a, b = tx[i]["caja"], tx[j]["caja"]
                                if min(a["r"], b["r"]) - max(a["l"], b["l"]) > 4 and min(a["b"], b["b"]) - max(a["t"], b["t"]) > 4:
                                    malas.append(f"{et}: «{tx[i]['txt']}» pisa a «{tx[j]['txt']}»")
                        if t == "pregunta":
                            signo = next(x for x in tx if x["txt"] == "?")
                            preg = next(x for x in tx if x["rol"] == "pregunta")
                            if signo["caja"]["b"] > preg["caja"]["t"]:
                                malas.append(f"{et}: el «?» baja hasta el titular")
                        if t == "precio":
                            for rol in ("cta", "precio"):
                                capa = next(c for c in lam["capas"] if c.get("rol") == rol)
                                if lineas.get(capa["id"], 1) > 1:
                                    malas.append(f"{et}: «{rol}» ocupa {lineas[capa['id']]} líneas")
    ok(cuenta >= 900, f"{cuenta} láminas nuevas pintadas y medidas")
    for m in malas[:30]:
        print("   ", m)
    ok(not malas, f"ningún texto se sale, pisa a otro, se lee mal ni baja de la letra mínima ({len(malas)} fallos)")


def _leer_qr(png_o_jpg):
    """El texto de un QR en una imagen, con OpenCV si está (si no, None y se dice)."""
    try:
        import cv2                                          # noqa: PLC0415
        import numpy as np                                  # noqa: PLC0415
    except ImportError:
        return None
    im = cv2.imdecode(np.frombuffer(png_o_jpg, np.uint8), cv2.IMREAD_COLOR)
    texto, _puntos, _ = cv2.QRCodeDetector().detectAndDecode(im)
    return texto


def qr(pincel):
    print("el QR del cierre: WhatsApp o web, hecho aquí y legible")
    import tempfile, shutil                                 # noqa: E401,PLC0415
    import graficas_qr as Q                                 # noqa: PLC0415

    def falla(*a):
        try:
            Q.destino(*a)
            return False
        except G.ErrorGraficas:
            return True
    ok(Q.destino("whatsapp", "999 888 777") == "https://wa.me/51999888777", "un celular de Perú sin código lleva el 51")
    ok(Q.destino("whatsapp", "+51 (999) 888-777") == "https://wa.me/51999888777", "con +, espacios, guiones y paréntesis")
    ok(Q.destino("whatsapp", "34 600 111 222") == "https://wa.me/34600111222", "un número de otro país, tal cual")
    ok(falla("whatsapp", "999888777", "Hola " * 40) and falla("whatsapp", "999888777", "😀" * 40),
       "un mensaje largo (o con muchos emojis) se rechaza con una frase: el QR no se leería (árbitro)")
    ok(falla("web", "crearia.tech/" + "a" * 160), "una web de más de 150 letras se rechaza")
    try:
        Q.png("😀" * 3000)
        ok(False, "lo que no cabe en un QR da un error claro, nunca un 500")
    except G.ErrorGraficas:
        ok(True, "lo que no cabe en un QR da un error claro, nunca un 500")
    ok(Q.destino("whatsapp", "999888777", "Hola, quiero alquilar & reservar") ==
       "https://wa.me/51999888777?text=Hola%2C%20quiero%20alquilar%20%26%20reservar", "el mensaje va codificado")
    ok(falla("whatsapp", "llámame") and falla("whatsapp", "123") and falla("whatsapp", "1" * 16), "un WhatsApp que no es un número se rechaza")
    ok(Q.destino("web", "crearia.tech") == "https://crearia.tech", "una web sin https lo lleva")
    ok(Q.destino("web", "http://estadoplay.pe/alquiler") == "http://estadoplay.pe/alquiler", "con su http y su ruta, tal cual")
    ok(falla("web", "javascript:alert(1)") and falla("web", "ftp://x.pe") and falla("web", "http://localhost")
       and falla("web", "mi web.com") and falla("web", "") and falla("web", "a." + "b" * 300), "una web rara se rechaza")
    ok(falla("correo", "x@y.pe"), "solo WhatsApp o web")
    req = open(os.path.join(AQUI, "..", "requirements.txt"), encoding="utf-8").read()
    ok(re.search(r"^segno==\d", req, re.M) is not None, "segno va fijado en requirements.txt (lo instala asvs actualizar)")
    app = open(os.path.join(AQUI, "..", "app.py"), encoding="utf-8").read()
    ok('@app.post("/api/graficas/{cid}/qr"' in app, "la ruta del QR existe")
    raiz = tempfile.mkdtemp(prefix="graficas_qr_")
    try:
        r = Q.hacer(raiz, "cli", "web", "crearia.tech/carrusel?x=1")
        ok(re.fullmatch(r"img_[0-9a-f]{16}\.jpg", r["nombre"]) and r["destino"] == "https://crearia.tech/carrusel?x=1",
           "se guarda como una imagen más")
        ruta = G.ruta_imagen(raiz, "cli", r["nombre"])
        leido = _leer_qr(open(ruta, "rb").read())
        if leido is None:
            print("   (sin OpenCV: no se lee el QR, solo se genera)")
        else:
            ok(leido == r["destino"], f"el JPG guardado se lee con un lector de QR ({leido!r})")
            # y pintado en el cierre, a un 22 % del ancho, en el tamaño más pequeño
            for fid in ("v45", "c11", "h916"):
                lam = K.lamina(16, "cierre", fid, G.COLORES_DEFECTO, None, "M")
                lam["capas"].append({"tipo": "imagen", "id": "qr1", "src": r["nombre"], "x": 70, "y": 40, "w": 22,
                                     "h": 22 * G.formato(fid)["W"] / G.formato(fid)["H"], "encuadre": {"x": 50, "y": 50, "zoom": 1}})
                doc = C.limpiar_doc({"version": 2, "formato": fid, "laminas": [{"capas": []}, lam]})
                png, _a, _m = C.pintar(pincel, doc, None, lambda n: G.ruta_imagen(raiz, "cli", n), None, None, 1)
                ok(_leer_qr(png) == r["destino"], f"pintado en el cierre ({fid}, 22 % del ancho) se sigue leyendo")
    finally:
        shutil.rmtree(raiz, ignore_errors=True)


def historias(pincel):
    print("«Hacer también las historias»: el mismo carrusel en 9:16")
    for n in (3, 10, 15, 16):
        doc = {"version": 2, "formato": "v45", "nombre": "Errores", "laminas": [{"capas": []}]}
        doc, _av = K.carrusel_desde_texto(pincel, doc, n, TEXTO, "sustituir", None, None, None, "EstadoPlay")
        doc["laminas"].insert(2, K.lamina(n, "precio", "v45", G.COLORES_DEFECTO, None, "EstadoPlay"))
        f = G.formato("v45")
        doc["laminas"][-1]["capas"].append({"tipo": "imagen", "id": "qr1", "nombre": "QR", "src": "", "x": 70, "y": 40,
                                            "w": 22, "h": 22 * f["W"] / f["H"], "encuadre": {"x": 50, "y": 50, "zoom": 1}})
        doc = C.limpiar_doc(doc)
        h = K.historias(pincel, doc, None, None, None, "EstadoPlay")
        fh = G.formato("h916")
        ok(h["formato"] == "h916" and h["nombre"] == "Errores (historias)", f"familia {n}: en 9:16 y con su nombre")
        ok(len(h["laminas"]) == len(doc["laminas"]) and [l.get("tipo") for l in h["laminas"]] == [l.get("tipo") for l in doc["laminas"]],
           f"familia {n}: las mismas láminas, del mismo tipo")
        ok(all(l.get("familia") == n for l in h["laminas"]), f"familia {n}: con su familia")
        textos = lambda d: sorted(c["txt"] for l in d["laminas"] for c in l["capas"] if c["tipo"] == "texto" and c.get("rol") in K.ROLES)
        ok(textos(h) == textos(doc), f"familia {n}: ni un texto se pierde")
        qr_ = next(c for c in h["laminas"][-1]["capas"] if c.get("nombre") == "QR")
        ok(abs(qr_["w"] / 100 * fh["W"] - qr_["h"] / 100 * fh["H"]) < 1, f"familia {n}: el QR sigue cuadrado")
        for i in range(len(h["laminas"])):
            _png, _a, medida = C.pintar(pincel, h, None, lambda _n: None, None, None, i)
            ok(not medida["fuera"] and not medida["choca"], f"familia {n}, historia {i + 1}: nada en lo que tapa la red ni encimado {medida}")
        ok(doc["formato"] == "v45", f"familia {n}: el carrusel de antes no se toca")
    try:
        K.historias(pincel, dict(doc, formato="h916"))
        ok(False, "uno que ya es 9:16 se rechaza")
    except G.ErrorGraficas:
        ok(True, "uno que ya es 9:16 se rechaza")
    js = open(os.path.join(AQUI, "..", "web", "graficas_editor.js"), encoding="utf-8").read()
    ok("'/capas/historias'" in js and "Guarda primero este carrusel" in js, "el editor pide guardar antes y abre las historias aparte")


def iconos(pincel):
    print("iconos y pegatinas")
    import io, tempfile, shutil                             # noqa: E401,PLC0415
    from PIL import Image                                   # noqa: PLC0415
    import graficas_iconos as I                             # noqa: PLC0415
    cat = I.catalogo()
    ok(len(cat) >= 50 and all(x["svg"] for x in cat), f"{len(cat)} iconos, todos con sus trazos")
    marcas = ("instagram", "facebook", "whatsapp", "tiktok", "youtube", "twitter", "linkedin", "pinterest", "threads", "github")
    ok(not any(m in x["id"] for x in cat for m in marcas), "ningún logo de red ni de marca")
    licencia = os.path.join(I.CARPETA, "lucide", "LICENSE")
    ok(os.path.isfile(licencia) and "ISC License" in open(licencia, encoding="utf-8").read(), "la licencia ISC de Lucide va con los iconos")
    svgs = {f[:-4] for f in os.listdir(os.path.join(I.CARPETA, "lucide")) if f.endswith(".svg")}
    ok(svgs == {i for i in I.NOMBRES if I.ORIGEN.get(i, "lucide") == "lucide"}, "cada icono copiado tiene su nombre en español, y al revés")
    ok(all(not re.search(r"<(script|style|a|image|use)\b|on\w+=", x["svg"]) for x in cat), "solo trazos (nada de scripts ni enlaces)")
    # un fichero con trampa no se cuela
    viejo = I.CARPETA
    raro = tempfile.mkdtemp(prefix="iconos_")
    try:
        os.makedirs(os.path.join(raro, "lucide"))
        with open(os.path.join(raro, "lucide", "heart.svg"), "w", encoding="utf-8") as fh:
            fh.write('<svg viewBox="0 0 24 24"><path d="M1 1"/><script>alert(1)</script></svg>')
        I.CARPETA, memo = raro, dict(I._MEMO)
        I._MEMO.clear()
        ok(I.interior("heart") == "" and I.svg("heart", "#000000") == "", "un SVG con un script no se pinta")
        ok(I.interior("../../app") == "" and I.interior("no-existe") == "", "ni un id raro ni uno que no está")
    finally:
        I.CARPETA = viejo
        I._MEMO.clear()
        I._MEMO.update(memo)
        shutil.rmtree(raro, ignore_errors=True)
    # la capa: se guarda, se pinta con el color del Kit y uno que ya no está no rompe nada
    f = G.formato("v45")
    capa = {"tipo": "icono", "id": "ic1", "icono": "star", "color": "kit:principal", "alfa": 1, "grosor": 3,
            "x": 30, "y": 30, "w": 40, "h": 40 * f["W"] / f["H"]}
    fantasma = dict(capa, id="ic2", icono="ya-no-esta", y=5, h=8, w=8)
    doc = C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [{"capas": [
        {"tipo": "forma", "id": "f1", "x": 0, "y": 0, "w": 100, "h": 100, "relleno": {"color": "#FFFFFF", "alfa": 1}}, capa, fantasma]}]})
    c = doc["laminas"][0]["capas"][1]
    ok(c["tipo"] == "icono" and c["icono"] == "star" and c["grosor"] == 3 and c["color"] == "kit:principal", "la capa de icono se guarda")
    ok(doc["laminas"][0]["capas"][2]["icono"] == "ya-no-esta", "un icono que ya no está se guarda igual (la pieza se abre)")
    ok(C.limpiar_doc({"version": 2, "formato": "v45", "laminas": [{"capas": [dict(capa, grosor=99, icono="<x>")]}]})["laminas"][0]["capas"][0]
       ["grosor"] == 4, "el grosor tiene su tope y un id raro se vacía")
    html = C.html_capas(doc, None, lambda _n: None)[0]
    ok(html.count("data:image/svg+xml;base64,") == 1, "se pinta el que está y el que no, no")
    png, _a, _m = C.pintar(pincel, doc, None, lambda _n: None)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    caja = im.crop((int(0.3 * f["W"]), int(0.3 * f["H"]), int(0.7 * f["W"]), int(0.3 * f["H"] + 0.4 * f["W"])))
    principal = tuple(int(G.COLORES_DEFECTO["principal"][i:i + 2], 16) for i in (1, 3, 5))
    cerca = sum(1 for px in caja.getdata() if sum(abs(a - b) for a, b in zip(px, principal)) < 40)
    ok(cerca > 2000, f"la estrella sale con el color principal del Kit ({cerca} px)")
    js = open(os.path.join(AQUI, "..", "web", "graficas_editor.js"), encoding="utf-8").read()
    ok("'＋ Icono'" in js and "'＋ Pegatina'" in js and "/api/graficas/iconos" in js, "el editor ofrece iconos y pegatinas")
    for ref in ("tinta:acento", "tinta:secundario", "tinta:claro", "kit:acento", "kit:secundario", "kit:claro"):
        ok(C._RE_REF.fullmatch(ref) is not None, f"las pegatinas usan colores que se guardan ({ref})")


def Q_destino_largo_ok():
    import graficas_qr as Q                                 # noqa: PLC0415
    return Q.destino("web", "crearia.tech/" + "a" * 130) == "https://crearia.tech/" + "a" * 130


def lote(pincel):
    print("carruseles en lote: una lista o un CSV")
    import tempfile, shutil                                 # noqa: E401,PLC0415
    import graficas_lote as LOTE                            # noqa: PLC0415

    def falla(texto):
        try:
            LOTE.leer(texto)
            return ""
        except G.ErrorGraficas as e:
            return str(e)
    lista = "Familia: Gamer\n" + TEXTO + "\n---\nCómo elegir el juego\n\nMira la edad\nNo es lo mismo 8 que 30.\n\n---\n\n---\nFamilia: publicacion\nTres trucos\n\n- Uno\n- Dos\n- Tres"
    e = LOTE.leer(lista)
    ok([x["familia"] for x in e] == [16, None, 15], "la lista: cada uno con su familia (por nombre, sin tildes ni mayúsculas) o la elegida")
    ok([x["nombre"] for x in e] == ["5 errores al alquilar una consola", "Cómo elegir el juego", "Tres trucos"], "cada uno se llama como su titular")
    ok(not e[0]["texto"].lower().startswith("familia"), "la línea «Familia:» no entra en el carrusel")
    csv_comas = 'familia,titular,lamina 1,lamina 2\n16,Errores al alquilar,"No probar | Pruébalos antes",8 de 10 | fiestas\n,Sin familia,Uno | dos,\n'
    e = LOTE.leer(csv_comas)
    ok([x["familia"] for x in e] == [16, None] and e[0]["texto"] == "Errores al alquilar\n\nNo probar\nPruébalos antes\n\n8 de 10\nfiestas",
       "un CSV con comas: cada fila un carrusel y «|» parte titular y frase")
    tabs = "familia\ttitular\tlámina 2\tlámina 3\n" + "".join(
        f"Gamer\t5 errores, y cómo evitarlos {i}\tNo probar los mandos, ni las pilas, ni el cable\tLlamar tarde, sin reservar, sin pedir boleta\n"
        for i in range(3))
    e = LOTE.leer(tabs)
    ok(len(e) == 3 and e[0]["texto"].startswith("5 errores, y cómo evitarlos 0\n\nNo probar los mandos, ni las pilas"),
       "pegado de Sheets con comas en los textos: el separador sale de la fila de títulos (árbitro)")
    e = LOTE.leer('Familia;Titular;L1\nGamer;"Hola, qué tal";Uno, dos y tres\nGamer;Otro, más;Cuatro, cinco\n')
    ok(len(e) == 2 and e[0]["nombre"] == "Hola, qué tal", "con punto y coma y comas dentro de las celdas")
    e = LOTE.leer("familia\ttitular\ttexto de la lámina 2\n" + "Gamer\tHola\tUna, dos\n" * 3)
    ok(len(e) == 3, "pegado de Sheets con títulos largos: sigue siendo un CSV (árbitro, 2.ª vuelta)")
    ok(Q_destino_largo_ok(), "una web de 143 letras escritas cabe (el https:// no cuenta)")
    e = LOTE.leer("Portada, lo que nadie te cuenta\n\nUna idea\nCon su frase.")
    ok(len(e) == 1 and e[0]["nombre"] == "Portada, lo que nadie te cuenta", "una lista que empieza por «Portada,» no es un CSV (árbitro)")
    e = LOTE.leer("Familia;Titular;L1\nGamer;Hola;Uno | dos\n")
    ok(len(e) == 1 and e[0]["familia"] == 16, "con punto y coma (Excel en español)")
    e = LOTE.leer("titular\tl1\tl2\nHola\tUno\tDos\n")
    ok(len(e) == 1 and e[0]["familia"] is None and e[0]["texto"] == "Hola\n\nUno\n\nDos", "con tabuladores (pegado de Excel o Sheets)")
    ok("Galaxia" in falla("Familia: Galaxia\nHola"), "una familia que no existe se dice con su nombre")
    ok("fila 2" in falla("familia,titular\n99,Hola\n"), "en el CSV se dice la fila")
    ok("titular" in falla("familia\totra\n1\tx\n"), "un CSV sin «titular» se rechaza")
    e = LOTE.leer("Familia, amigos y fiestas\n\nUna idea\nCon su frase.")
    ok(len(e) == 1 and e[0]["nombre"] == "Familia, amigos y fiestas", "una lista que empieza por «Familia, …» es una lista (árbitro, 2.ª vuelta)")
    ok("ningún" in falla("   \n---\n  "), "sin ningún carrusel se dice")
    ok("caben 20" in falla("\n---\n".join(f"Carrusel {i}" for i in range(21))), "más de 20 por tanda se rechaza")
    ok("demasiado" in falla("x" * 60001), "un texto enorme se rechaza")
    raiz = tempfile.mkdtemp(prefix="graficas_lote_")
    try:
        vistos = []
        hechos = LOTE.hacer(raiz, "cli", LOTE.leer(lista), 3, "v45", lambda fn: fn(pincel), None, None, None, "EstadoPlay",
                            lambda h, t: vistos.append((h, t)))
        ok(vistos == [(1, 3), (2, 3), (3, 3)], "la barra avanza de uno en uno")
        ok(len(hechos) == 3 and all(x["id"] and x["laminas"] >= 2 for x in hechos), "se guardan 3 piezas nuevas, con sus láminas")
        piezas = {p["id"]: p for p in G.listar_piezas(raiz, "cli")}
        ok(all(x["id"] in piezas for x in hechos), "y salen en la lista de Gráficas")
        _ficha, doc = C.leer(raiz, "cli", hechos[0]["id"])
        ok(doc["nombre"] == "5 errores al alquilar una consola" and doc["laminas"][1].get("familia") == 16,
           "con su nombre y su familia")
        _ficha, doc = C.leer(raiz, "cli", hechos[1]["id"])
        ok(doc["laminas"][1].get("familia") == 3, "el que no dice familia va con la elegida")
        try:
            LOTE.hacer(raiz, "cli", LOTE.leer("Hola"), 99, "v45", lambda fn: fn(pincel))
            ok(False, "una familia elegida que no existe se rechaza")
        except G.ErrorGraficas:
            ok(True, "una familia elegida que no existe se rechaza")
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    app = open(os.path.join(AQUI, "..", "app.py"), encoding="utf-8").read()
    js = open(os.path.join(AQUI, "..", "web", "app.js"), encoding="utf-8").read()
    ok('@app.post("/api/graficas/{cid}/capas/lote"' in app and "'/capas/lote'" in js and "+ Carruseles en lote" in js,
       "la ruta y el botón «+ Carruseles en lote»")


def main():
    familias_nuevas()
    tarjeta_no_tapa_la_marca()
    tipos_nuevos_sin_pintar()
    pincel = G.Pincel()
    try:
        pintadas(pincel)
        tipos_nuevos_pintados(pincel)
        qr(pincel)
        historias(pincel)
        iconos(pincel)
        lote(pincel)
    finally:
        pincel.cerrar()
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

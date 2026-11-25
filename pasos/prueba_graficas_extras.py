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
    ok(re.fullmatch(r"@[a-z0-9_.]{1,29}", K.textos_de_portada(15, {}, (), "Ñandú & Cía!")["usuario"]) is not None,
       "un nombre con símbolos da un @usuario limpio")
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
               "precio": "S/ 990", "texto": "Hasta el 30 de noviembre, en Lima Metropolitana, con instalación incluida",
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
    for fid, kits in (("v45", list(P.KITS)), ("v34", ["de siempre"]), ("c11", ["de siempre"]), ("h916", ["de siempre"])):
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
                            boton = next(c for c in lam["capas"] if c.get("rol") == "cta")
                            if lineas.get(boton["id"], 1) > 1:
                                malas.append(f"{et}: el botón ocupa {lineas[boton['id']]} líneas")
    ok(cuenta >= 600, f"{cuenta} láminas nuevas pintadas y medidas")
    for m in malas[:30]:
        print("   ", m)
    ok(not malas, f"ningún texto se sale, pisa a otro, se lee mal ni baja de la letra mínima ({len(malas)} fallos)")


def main():
    familias_nuevas()
    tarjeta_no_tapa_la_marca()
    tipos_nuevos_sin_pintar()
    pincel = G.Pincel()
    try:
        pintadas(pincel)
        tipos_nuevos_pintados(pincel)
    finally:
        pincel.cerrar()
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

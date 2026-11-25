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


def main():
    familias_nuevas()
    tarjeta_no_tapa_la_marca()
    pincel = G.Pincel()
    try:
        pintadas(pincel)
    finally:
        pincel.cerrar()
    print(f"\n{CUENTA['ok']} comprobaciones bien, {CUENTA['mal']} mal")
    return 1 if CUENTA["mal"] else 0


if __name__ == "__main__":
    sys.exit(main())

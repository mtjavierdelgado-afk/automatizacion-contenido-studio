#!/usr/bin/env python3
"""Un CLI de Claude FALSO, para el recorrido automatico (`prueba_recorrido.py`).

Contesta como `claude -p --output-format json` a lo que la pantalla puede pedir
sin gastar nada y sin red: la revision de un campo («Revisar»), quitar las
marcas de una nota o de un prompt y «✨ Más emojis» de Publicar. A lo demas contesta un JSON vacio, que es
lo que haria un modelo que no sabe que decir: el codigo que llama tiene que
aguantarlo.

Se usa poniendo su carpeta (con un `claude` que lo llama) la PRIMERA del PATH.
"""
import json
import re
import sys


def _entre(texto, etiqueta):
    encaje = re.search(rf"<{etiqueta}>\s*(.*?)\s*</{etiqueta}>", texto, re.S)
    return encaje.group(1) if encaje else ""


#: Lo que el corrector de ortografia falso sabe arreglar (las palabras sin
#: tilde del video de prueba).
TILDES = {"kilometros": "kilómetros", "mas": "más", "gruas": "grúas",
          "mercancia": "mercancía", "decia": "decía", "identicas": "idénticas",
          "manana": "mañana", "tripulacion": "tripulación", "zarpo": "zarpó"}


def _ortografia(entrada):
    salida = {}
    for tid, texto in re.findall(r'<t id="([^"]+)">(.*?)</t>', entrada, re.S):
        nuevo = re.sub(r"\b(" + "|".join(TILDES) + r")\b",
                       lambda m: TILDES[m.group(1)], texto)
        if nuevo != texto:
            cambios = [[a, b] for a, b in TILDES.items() if re.search(rf"\b{a}\b", texto)]
            salida[tid] = {"texto": nuevo, "cambios": cambios}
    return {"correcciones": salida}


#: Lo que el corrector EDITORIAL falso propone (arreglos-19oct): frases del
#: guion del video de prueba, con su motivo.
EDITORIALES = [("el buque atraca", "el buque atracó", "concordancia",
                "el resto del relato va en pasado"),
               ("La marina llega", "La marina llegó", "concordancia",
                "el resto del relato va en pasado"),
               ("todo queda incautado", "todo quedó incautado", "concordancia",
                "el resto del relato va en pasado"),
               ("descargan el patio entero", "vacían el patio entero", "claridad",
                "lo que se descarga es la carga, no el patio")]


def _editorial(entrada):
    salida = {}
    for tid, texto in re.findall(r'<t id="([^"]+)">(.*?)</t>', entrada, re.S):
        lista = [{"original": a, "propuesta": b, "tipo": t, "motivo": m}
                 for a, b, t, m in EDITORIALES if a in texto]
        if lista:
            salida[tid] = lista
    return {"propuestas": salida}


def responder(entrada):
    if "<texto_para_emojis>" in entrada:
        # «✨ Más emojis» de Publicar: el mismo texto, con un emoji delante
        # (las palabras no se tocan: si se tocaran, el Studio lo rechaza)
        return {"texto": "🎮 " + _entre(entrada, "texto_para_emojis")}
    if "<textos>" in entrada and "REVISION EDITORIAL" in entrada:
        return _editorial(entrada)
    if "<textos>" in entrada and "ORTOGRAFIA" in entrada:
        return _ortografia(entrada)
    if "Eres editor de videos para redes" in entrada:
        # los elementos del video (pasos/elementos_video.py): uno por plano,
        # en la primera palabra, y una flecha en el segundo
        planos = {}
        for n, (pid, texto) in enumerate(re.findall(r'<p id="([^"]+)"[^>]*>(.*?)</p>', entrada, re.S)):
            primera = (texto.split(" ")[0].split(":", 1) + [""])[1] or "MIRA"
            planos[pid] = [{"tipo": "texto", "texto": primera.upper()[:20], "palabra": 0,
                            "posicion": "arriba", "entrada": "pop", "color": "acento"}]
            if n == 1:
                planos[pid].append({"tipo": "flecha", "palabra": 1, "posicion": "centro",
                                    "entrada": "dibuja", "color": "alerta"})
        planos["NOEXISTE"] = [{"tipo": "texto", "texto": "x", "palabra": 0}]
        return {"planos": planos}
    if "ideas DISTINTAS de imagen" in entrada:
        # las ideas de imagen para la IA (portadas-2): cada una con su prompt
        return {"ideas": [
            {"titulo": "La sala llena", "prompt": "Una sala de fiesta con diez pantallas encendidas y "
             "niños jugando con mandos, luz azul de neón, plano general desde la puerta", "por_que": "se ve la escala"},
            {"titulo": "El mando en primer plano", "prompt": "Primer plano de unas manos sujetando un mando "
             "de consola, fondo desenfocado con luces de colores, mucho contraste", "por_que": "se entiende en un segundo"},
            {"titulo": "Cara de sorpresa", "prompt": "Un adulto sorprendido delante de una pantalla gigante "
             "con un videojuego, boca abierta, luz cálida", "por_que": "las caras atraen clics"}]}
    if "director de arte de miniaturas" in entrada:
        # las portadas propuestas (pasos/portadas.py): tres distintas
        return {"propuestas": [
            {"plantilla": "versus", "paleta": "gamer", "fuente": "anton",
             "textos": {"izquierda": "PS5", "derecha": "XBOX"}, "por_que": "compara dos opciones"},
            {"plantilla": "oferta", "paleta": "oferta", "fuente": "luckiest",
             "textos": {"titulo": "TODO EL DÍA", "etiqueta": "S/ 99"}, "por_que": "el precio vende"},
            {"plantilla": "pregunta", "paleta": "impacto", "fuente": "bebas",
             "textos": {"titulo": "¿CUÁNTO CUESTA?"}, "por_que": "la duda del cliente"}]}
    if "<guia>" in entrada and "<texto>" in entrada:
        texto = _entre(entrada, "texto")
        if "BORRADOR" in texto:
            # «Sirve» CON problemas, que es lo que dejaba la pantalla sin ningun
            # boton (N5 de las notas de mejoras, 13-10-2026): uno con su trozo
            # en el texto y otro con un trozo que no esta
            return {"veredicto": "sirve",
                    "resumen": "Sirve, aunque hay dos cosas que mejorar.",
                    "problemas": [
                        {"que": "BORRADOR", "por_que": "el guionista lo leeria como contenido",
                         "arreglo": "quitalo", "original": "BORRADOR",
                         "mejor": "versión final"},
                        {"que": "una frase que no esta", "por_que": "x", "arreglo": "y",
                         "original": "frase que no aparece en el campo", "mejor": "otra"}],
                    "sugerida": texto.replace("BORRADOR", "").strip() + " (revisado)"}
        if "[" in texto or "PENDIENTE" in texto:
            limpio = re.sub(r"\[[^\]]*\]", "", texto).replace("PENDIENTE", "").strip()
            return {"veredicto": "mejorable",
                    "resumen": "Hay huecos sin rellenar entre corchetes.",
                    "problemas": [{"que": "[...]", "por_que": "el sistema los lee como texto",
                                   "arreglo": "rellenalos o borralos"}],
                    "sugerida": limpio + " (revisado)"}
        return {"veredicto": "sirve", "resumen": "Cumple la guía.", "problemas": [],
                "sugerida": ""}
    if "<traducir_al_espanol>" in entrada:
        # lo que se manda a dibujar, en español (rama estados-en-espanol): cada
        # texto con «ES:» delante, para que la pantalla enseñe que es la traducción
        textos = re.findall(r'<t id="([^"]+)">(.*?)</t>', _entre(entrada, "traducir_al_espanol"), re.S)
        return {"traducciones": {tid: "ES: " + texto.strip() for tid, texto in textos}}
    if "<imagen_nueva>" in entrada:
        # lo que se ve en una imagen insertada (rama insertar-imagen): «EN:» y el
        # español; «ROMPER» en el texto, sin respuesta
        que = _entre(entrada, "imagen_nueva")
        return {"direccion": "" if "ROMPER" in que else "close-up, EN: " + que}
    if "<pasar_al_ingles>" in entrada:
        # el cambio reescrito en español, de vuelta al inglés que se manda
        texto = _entre(entrada, "pasar_al_ingles")
        # «ROMPER» en el texto: Claude no devuelve nada (el error en el acto)
        return {"ingles": "" if "ROMPER" in texto else "EN: " + texto}
    if "Escribe el GUION VISUAL" in entrada:
        # el borrador del guion visual (rama guion-visual): un plano por bloque
        bloques = re.findall(r"^\[([A-Z0-9_]+)\]", entrada, re.M)
        return {"planos": [{"bloque": b, "visual": f"wide shot of the room while {b} is heard",
                            "camara": "wide shot, eye level", "estado": "", "personajes": []}
                           for b in bloques]}
    if "script supervisor" in entrada:
        # la comprobacion del guion visual contra lo fijo: nada que decir
        return {"avisos": []}
    if "LOS TRAMOS (no los cambies" in entrada:
        # el «qué cambia en cada tramo» de un espacio que cambia (rama
        # tipo-de-relato): un cambio por tramo, con su estado
        tramos = re.findall(r"^- ([A-Z0-9_]+)-([A-Z0-9_]+):", entrada, re.M)
        # (con un solo tramo, ese cambia: si no, no habria ningun estado que ver)
        return {"beats": [{"desde": d, "hasta": h,
                           "cambio": "" if i == 0 and len(tramos) > 1
                           else "the hinged shower door is a sliding door",
                           "estado": "antes" if i == 0 and len(tramos) > 1 else "despues"}
                          for i, (d, h) in enumerate(tramos)]}
    if "<nota>" in entrada:
        nota = _entre(entrada, "nota")
        nuevo = re.sub(r"mario\s*kart", "un juego de carreras de karts de dibujos", nota, flags=re.I)
        nuevo = re.sub(r"nintendo\s+switch", "una consola portátil con mandos rojo y azul",
                       nuevo, flags=re.I)
        nuevo = nuevo.replace("PROHIBIDO", "permitido")
        return {"texto": nuevo, "cambios": [["Mario Kart", "un juego de carreras de karts"]]}
    if "<prompt>" in entrada:
        prompt = _entre(entrada, "prompt")
        nuevo = re.sub(r"mario\s*kart", "a cartoon kart racing game", prompt, flags=re.I)
        nuevo = re.sub(r"nintendo\s+switch", "a handheld console", nuevo, flags=re.I)
        return {"prompt": nuevo + " No logos, no brand names, no trademarked characters.",
                "cambios": [["Mario Kart", "a cartoon kart racing game"]]}
    return {}


def main():
    entrada = sys.stdin.read()
    if "--version" in sys.argv:
        print("9.9.9 (Claude Code falso)")
        return 0
    if "auth" in sys.argv:
        print(json.dumps({"loggedIn": True, "email": "prueba@ejemplo.com",
                          "subscriptionType": "pro", "authMethod": "claude.ai"}))
        return 0
    respuesta = responder(entrada)
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                      "result": json.dumps(respuesta, ensure_ascii=False),
                      "session_id": "falso", "usage": {"input_tokens": 10,
                                                       "output_tokens": 10}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

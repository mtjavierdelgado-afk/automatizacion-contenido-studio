#!/usr/bin/env python3
"""Un CLI de Claude FALSO, para el recorrido automatico (`prueba_recorrido.py`).

Contesta como `claude -p --output-format json` a lo que la pantalla puede pedir
sin gastar nada y sin red: la revision de un campo («Revisar») y quitar las
marcas de una nota o de un prompt. A lo demas contesta un JSON vacio, que es
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


def responder(entrada):
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

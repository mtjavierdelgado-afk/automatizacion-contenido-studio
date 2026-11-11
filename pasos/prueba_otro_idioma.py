"""Prueba de HACER UN VÍDEO EN OTRO IDIOMA (pasos/otro_idioma.py).

Lo que se comprueba es lo que costaría dinero o saldría mal sin avisar:

  - cada plano se reconoce como suma de trozos del corte (las cartelas funden
    trozos), y un plano tocado a mano se traduce aparte;
  - un trozo que cruza de un bloque al siguiente se parte en dos, una parte
    por bloque: ningún bloque dice de más ni de menos (nada se repite);
  - la traducción vuelve con todos los trozos y sus partes, o NO sigue (un
    vídeo a medio traducir se locutaría en dos idiomas);
  - lo que cuesta: la voz por caracteres (con lo que ocupa el otro idioma),
    Claude 0 $ y las imágenes 0 $ si todas existen;
  - preparar la copia escribe el guion como edición a mano, la voz en el
    idioma nuevo, las cartelas traducidas sin perder su plantilla, quita los
    subtítulos escritos a mano y deja el resto de cada plano como estaba;
  - la lista «Cómo se pronuncia» (ortografía castellana) solo va a una voz en
    español.

    python pasos/prueba_otro_idioma.py
"""
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(RAIZ))

_TMP = tempfile.mkdtemp(prefix="prueba_otro_idioma_")
os.environ.setdefault("ESTUDIO_SECRETOS", os.path.join(_TMP, "secretos"))
os.environ.setdefault("ESTUDIO_ESTADISTICAS", os.path.join(_TMP, "estadisticas.json"))
os.environ.setdefault("ESTUDIO_AJUSTES", os.path.join(_TMP, "ajustes.json"))

import otro_idioma as oi                                     # noqa: E402
import pronunciacion                                         # noqa: E402
from nucleo.estado import Estado                             # noqa: E402
from nucleo.proyecto import Proyecto                         # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        return True
    _fallos.append(mensaje)
    print(f"      FALLO: {mensaje}")
    return False


def igual(obtenido, esperado, mensaje):
    return ok(obtenido == esperado,
              f"{mensaje} (esperaba {esperado!r}, llego {obtenido!r})")


def seccion(titulo):
    print(f"\n  {titulo}")


CORTE = ["El carguero zarpó del puerto.", "Iba lleno.",
         "Cuatro mil kilómetros de mar", "separaban los dos puertos."]


def prueba_planos_y_trozos():
    seccion("cada plano, como suma de trozos del corte")
    escenas = [{"id": "S001", "narracion": "El carguero zarpó del puerto. Iba lleno."},
               {"id": "S002", "narracion": "Cuatro mil kilómetros de mar"},
               {"id": "S003", "narracion": "separaban los dos puertos."}]
    salida = oi._escenas_por_trozos(escenas, CORTE)
    igual([e["trozos"] for e in salida], [[0, 1], [2], [3]],
          "una cartela que funde dos trozos se queda los dos; los demás, el suyo")
    ok(not any(e.get("propio") for e in salida), "y ninguno se traduce aparte")
    partido = [{"id": "S001", "narracion": "El carguero zarpó"},
               {"id": "S001B", "narracion": "del puerto. Iba lleno."},
               {"id": "S002", "narracion": "Cuatro mil kilómetros de mar"},
               {"id": "S003", "narracion": "separaban los dos puertos."}]
    salida = oi._escenas_por_trozos(partido, CORTE)
    ok(salida[0].get("propio") == "El carguero zarpó" and salida[1].get("propio"),
       "un plano partido a mano se traduce aparte (su ficha dice lo suyo)")
    igual([e["trozos"] for e in salida[2:]], [[2], [3]], "y los de después siguen casando")


def prueba_bloques():
    seccion("un trozo que cruza de bloque se parte en dos")
    palabras = []
    t = 0.0
    for w in " ".join(CORTE).split():
        palabras.append({"w": w, "s": t, "e": t + 0.3})
        t += 0.4
    # B001: las 9 primeras palabras (hasta «mil»); B002: el resto
    tramos = [(0.0, 3.3, "B001"), (3.35, 100.0, "B002")]

    def bloque_en(palabra, tramos_):
        for i, (a, b, _bid) in enumerate(tramos_):
            if a <= palabra["s"] <= b:
                return i
        return -1
    por_palabra = oi._bloque_de_cada_palabra(CORTE, palabras, tramos, bloque_en)
    igual(por_palabra[0], ["B001"] * 5, "el primer trozo, entero en B001")
    ok(set(por_palabra[2]) == {"B001", "B002"}, f"el tercero cruza ({por_palabra[2]})")

    datos = {"trozos": [
        {"id": "T001", "partes": [{"bloque": "B001", "texto": "El carguero zarpó del puerto."}]},
        {"id": "T002", "partes": [{"bloque": "B001", "texto": "Iba lleno."}]},
        {"id": "T003", "partes": [{"bloque": "B001", "texto": "Cuatro mil"},
                                  {"bloque": "B002", "texto": "kilómetros de mar"}]},
        {"id": "T004", "partes": [{"bloque": "B002", "texto": "separaban los dos puertos."}]}],
        "escenas": [{"id": "S001", "trozos": [0, 1]}, {"id": "S002", "trozos": [2]},
                    {"id": "S003", "trozos": [3]}]}
    traduccion = {"trozos": {"T001": ["The freighter left port."], "T002": ["It was full."],
                             "T003": ["Four thousand", "kilometres of sea"],
                             "T004": ["separated the two ports."]},
                  "sueltos": {}, "propios": {}, "cartelas": {}}
    bloques, escenas, por_trozo = oi.textos_traducidos(datos, traduccion)
    igual(bloques, {"B001": "The freighter left port. It was full. Four thousand",
                    "B002": "kilometres of sea separated the two ports."},
          "cada bloque dice lo suyo, en orden y sin repetir nada")
    igual(escenas["S002"], "Four thousand kilometres of sea",
          "y el plano que cruza dice las dos partes juntas")
    igual(len(por_trozo), 4, "un texto por trozo del corte (el corte de la copia)")


def prueba_traducir():
    seccion("la traducción vuelve entera o no sigue")
    datos = {"trozos": [
        {"id": "T001", "partes": [{"bloque": "B001", "texto": "Hola."}]},
        {"id": "T002", "partes": [{"bloque": "B001", "texto": "Uno"},
                                  {"bloque": "B002", "texto": "dos tres cuatro"}]}],
        "escenas": [], "sueltos": [{"bloque": "B003", "texto": "Adiós."}],
        "cartelas": {"escena:S002": {"texto": "CUATRO MIL KM", "plantilla": None}}}
    datos["cartelas"]["escena:S002"].pop("plantilla")
    llamadas = []

    def llamar(instruccion, que):
        llamadas.append(instruccion)
        if len(llamadas) == 1:
            # le falta un trozo y la cartela: se vuelven a pedir SOLO esos
            return {"trozos": {"T001": ["Hello &amp; welcome."]}}
        return {"trozos": {"T002": ["One two three four"], "S_B003": ["Bye."]},
                "cartelas": {"C001": "FOUR THOUSAND KM"}}
    salida = oi.traducir(datos, "en", llamar=llamar)
    igual(len(llamadas), 2, "lo que falta se vuelve a pedir una vez")
    ok('id="T001"' not in llamadas[1] and 'id="T002"' in llamadas[1],
       "y la segunda vez solo se pide lo que faltaba")
    igual(salida["trozos"]["T001"], ["Hello & welcome."], "sin entidades ni etiquetas")
    igual(len(salida["trozos"]["T002"]), 2,
          "una sola parte para un trozo de dos se reparte en dos")
    igual(salida["sueltos"], {"B003": "Bye."}, "el bloque suelto también")
    igual(salida["cartelas"], {"escena:S002": {"texto": "FOUR THOUSAND KM"}},
          "y la cartela, a su plano y su campo")
    ok("CUATRO MIL KM" in llamadas[0] and "<guion>" in llamadas[0],
       "la instrucción lleva el guion entero de contexto y las cartelas")

    def nunca(instruccion, que):
        return {"trozos": {}}
    try:
        oi.traducir(datos, "en", llamar=nunca)
        ok(False, "sin traducción no sigue")
    except oi.ErrorOtroIdioma as fallo:
        ok("No se ha grabado" in str(fallo), "sin traducción no sigue, y dice que no se gastó nada")


def prueba_estimar():
    seccion("lo que cuesta, antes de hacer nada")
    datos = {"idioma_origen": "es", "caracteres": 1000, "trozos": [{}] * 90,
             "palabras": 170, "con_imagen": 40, "sin_dibujo": []}
    e = oi.estimar(datos, "en", tarifa_caracter=0.0001, usd_por_imagen=0.05)
    igual(e["voz"]["caracteres"], 880, "el inglés ocupa menos que el español")
    igual(e["voz"]["usd"], 0.09, "la voz, por caracteres")
    igual(e["claude"]["usd"], 0.0, "Claude va con la suscripción")
    igual(e["claude"]["llamadas"], 2, "90 planos son dos llamadas")
    igual((e["imagenes"]["reutilizadas"], e["imagenes"]["usd"]), (40, 0.0),
          "las imágenes se reutilizan: 0 $")
    con_huecos = dict(datos, sin_dibujo=["S003", "S007"])
    e = oi.estimar(con_huecos, "pt", tarifa_caracter=0.0001, usd_por_imagen=0.05)
    igual(e["imagenes"]["a_dibujar"], 2, "lo que no tiene dibujo se dice")
    igual(e["usd_total"], round(0.1 + 0.1, 2), "y entra en el total")
    sin_tarifa = oi.estimar(datos, "en")
    ok(sin_tarifa["voz"]["usd"] is None and sin_tarifa["usd_total"] is None,
       "sin precio por carácter no se inventa un número")
    for malo in ("es", "xx"):
        try:
            oi.estimar(datos, malo)
            ok(False, f"«{malo}» se rechaza")
        except oi.ErrorOtroIdioma:
            ok(True, "")


def prueba_preparar():
    seccion("preparar la copia: solo la copia, y sin perder nada de cada plano")
    raiz = os.path.join(_TMP, "proyectos")
    copia = Proyecto.crear(raiz, "Copia EN")
    estado = Estado(copia)
    estado.set_params("guion", {"bloques": {"B009": "texto viejo"}})
    estado.set_params("voz", {"voz_id": "voz-es", "velocidad": "normal"})
    estado.set_params("revision_audio", {"comentarios": [{"id": "c1", "bloque_id": "B001"}]})
    estado.set_params("assets", {"calidad": "low", "unidades": {
        "escena:S002": {"cartela": {"plantilla": "cifra", "fondo": "negro",
                                    "datos": {"texto": "CUATRO MIL KM", "n": 4000}},
                        "direccion": "close-up"},
        "escena:S003": {"direccion": "wide"}}})
    estado.set_params("callouts", {"unidades": {
        "escena:S001": {"subtitulo_texto": "Hola", "subtitulo_ancla": "Hola", "evitar": [{"x": 1}]},
        "escena:S003": {"subtitulo_texto": "Solo esto"}}})
    os.makedirs(copia.ruta_paso("assets", 1, crear=True), exist_ok=True)
    base = copia.ruta_paso("assets", 1)
    os.makedirs(os.path.join(base, "escenas"), exist_ok=True)
    with open(os.path.join(base, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump({"corte": CORTE, "escenas": [
            {"id": "S001", "narracion": "El carguero zarpó del puerto. Iba lleno."},
            {"id": "S002", "narracion": "Cuatro mil kilómetros de mar", "narracion_imagen": "Cuatro"},
            {"id": "S003", "narracion": "separaban los dos puertos."}]}, fh)
    for sid in ("S001", "S002", "S003"):
        with open(os.path.join(base, "escenas", f"{sid}.json"), "w", encoding="utf-8") as fh:
            json.dump({"id": sid, "png": f"escenas/{sid}.png", "narracion": "viejo"}, fh)
    estado.completar("assets", {"plan": "plan.json"})

    datos = {"trozos": [{"id": f"T{i + 1:03d}", "partes": [{"bloque": "B001" if i < 2 else "B002",
                                                           "texto": t}]}
                        for i, t in enumerate(CORTE)],
             "escenas": [{"id": "S001", "trozos": [0, 1]}, {"id": "S002", "trozos": [2]},
                         {"id": "S003", "trozos": [3]}]}
    traduccion = {"trozos": {"T001": ["The freighter left port."], "T002": ["It was full."],
                             "T003": ["Four thousand kilometres of sea"],
                             "T004": ["separated the two ports."]},
                  "sueltos": {}, "propios": {},
                  "cartelas": {"escena:S002": {"texto": "FOUR THOUSAND KM"}}}
    resumen = oi.preparar_copia(copia, estado, datos, traduccion, "en", voz_id="voz-en",
                                origen="original")
    guion = estado.params("guion")
    igual(guion["bloques"]["B001"], "The freighter left port. It was full.",
          "el guion va como edición a mano de cada bloque")
    igual(guion["bloques"]["B009"], "texto viejo", "sin tocar lo que no se traduce")
    voz = estado.params("voz")
    igual((voz["idioma"], voz["voz_id"], voz["velocidad"]), ("en", "voz-en", "normal"),
          "la voz, en el idioma nuevo y con la voz elegida, sin perder sus mandos")
    igual(estado.params("revision_audio").get("comentarios"), [],
          "los comentarios de la revisión (sobre el texto de antes) fuera")
    unidades = estado.params("assets")["unidades"]
    igual(unidades["escena:S002"]["cartela"],
          {"plantilla": "cifra", "fondo": "negro", "datos": {"texto": "FOUR THOUSAND KM", "n": 4000}},
          "la cartela traducida conserva su plantilla y sus otros datos")
    igual(unidades["escena:S002"]["direccion"], "close-up", "y el plano su dirección")
    igual(unidades["escena:S003"], {"direccion": "wide"}, "los demás planos, igual")
    cu = estado.params("callouts")["unidades"]
    igual(cu, {"escena:S001": {"evitar": [{"x": 1}]}},
          "los subtítulos escritos a mano fuera, lo demás de cada plano se queda")
    with open(os.path.join(base, "plan.json"), encoding="utf-8") as fh:
        plan = json.load(fh)
    igual(plan["corte"], ["The freighter left port.", "It was full.",
                          "Four thousand kilometres of sea", "separated the two ports."],
          "el corte de la copia, traducido trozo a trozo")
    igual([e["narracion"] for e in plan["escenas"]],
          ["The freighter left port. It was full.", "Four thousand kilometres of sea",
           "separated the two ports."], "cada plano dice lo suyo")
    ok("narracion_imagen" not in plan["escenas"][1], "sin la frase de antes para reconocerlo")
    with open(os.path.join(base, "escenas", "S003.json"), encoding="utf-8") as fh:
        igual(json.load(fh)["narracion"], "separated the two ports.",
              "y la ficha de su imagen también (así p6 la reconoce)")
    igual(resumen["fichas"], 3, "las tres fichas")
    igual(Proyecto(copia.raiz).config.get("traduccion_de", {}).get("video"), "original",
          "la copia apunta de qué vídeo sale")


def prueba_pronunciacion():
    seccion("«Cómo se pronuncia» solo para una voz en español")
    ok(pronunciacion.cargar("es") == pronunciacion.cargar(), "en español, la lista de siempre")
    ok(pronunciacion.cargar() != [], "que trae marcas escritas en castellano")
    igual(pronunciacion.cargar("en"), [], "a una voz en inglés no se le manda")
    igual(pronunciacion.cargar("pt"), [], "ni en portugués")


def main():
    prueba_planos_y_trozos()
    prueba_bloques()
    prueba_traducir()
    prueba_estimar()
    prueba_preparar()
    prueba_pronunciacion()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"OTRO IDIOMA OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

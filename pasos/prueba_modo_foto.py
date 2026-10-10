r"""
Prueba de la Etapa Foto A: el modo de imagen `estilo.modo` ("ilustracion" | "foto").

Lo que se protege aqui es lo que cuesta dinero si se rompe:

  1. LA HUELLA          sin `estilo.modo`, los prompts salen IDENTICOS byte a
                        byte a los de antes de la Etapa Foto A: el plano, sus
                        frases de referencia, la hoja de reparto, las laminas,
                        la guia escrita, la escalera y su reparto. Se compara
                        contra la huella SHA-256 tomada con el codigo de antes
                        (commit ba23adc). Si esta comprobacion falla, NO se
                        actualiza la huella sin mas: un prompt distinto es una
                        imagen distinta, y eso son planos ya pagados que salen
                        obsoletos en todos los proyectos guardados.
  2. NADA POR DEFECTO   `modo` no esta en los defectos, `_con_defectos` no lo
                        anade, y aplicar un estilo de ilustracion no lo escribe.
  3. LA FIRMA           un proyecto con `assets` listo y sin `estilo.modo` sigue
                        listo despues de pasar por todo lo que toca el modo; y
                        la firma SI se mueve al pasar a foto (si no, la prueba no
                        probaria nada).
  4. EL MODO FOTO       la cabecera, las frases sin «flat vector cartoon», las
                        reglas de foto y ninguna de cartoon, la hoja de reparto,
                        las laminas y la guia de foto.
  5. LA ESCALERA DE FOTO las 13 cartas con familia y servicios, el filtro de
                        servicios y las dos reglas del reparto.

    python pasos/prueba_modo_foto.py
"""
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import encuadres  # noqa: E402
import estilo as estilo_mod  # noqa: E402
import medios  # noqa: E402
import moodboard  # noqa: E402
import p6_assets  # noqa: E402
import p7_callouts  # noqa: E402
import presets_canal  # noqa: E402
import presets_light  # noqa: E402

from nucleo import Estado, Proyecto  # noqa: E402

FALLOS = []
COMPROBACIONES = 0


def ok(condicion, texto):
    global COMPROBACIONES
    COMPROBACIONES += 1
    if condicion:
        print(f"  ok   {texto}")
    else:
        print(f"  FALLO {texto}")
        FALLOS.append(texto)


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def titulo(texto):
    print(f"\n--- {texto}")


# =========================================================== 1 · la huella

#: SHA-256 de `_muestras_ilustracion()` con el codigo de ANTES de la Etapa Foto
#: A (commit ba23adc de main, 09-10-2026). Ver la cabecera: si falla, lo que hay
#: que mirar es que prompt ha cambiado, no esta cifra.
HUELLA_ILUSTRACION = ("9358025cbb3564c8d2ee58d2638529c579a7f89a23eaa81a9dba5a68b4bf0dec")

#: Reglas fijas para la huella. Las de verdad (`reglas.json`) las reescribe el
#: destilador en cada servidor, asi que una huella que las incluyera fallaria en
#: cualquier maquina que haya aprendido una regla. Se sustituye el fichero, no
#: la funcion: lo que se prueba es que el camino de ilustracion sigue leyendo
#: `reglas.json` igual que antes.
REGLAS_FIJAS = {
    "version": 1, "descripcion": "reglas fijas de prueba",
    "reglas": [
        {"id": "a", "ambito": "prompt_imagen", "prioridad": 2,
         "regla": "Second house rule."},
        {"id": "b", "ambito": "prompt_imagen", "prioridad": 1,
         "regla": "First house rule."},
        {"id": "c", "ambito": "reparto", "prioridad": 1,
         "regla": "Cast sheet house rule."},
    ],
}

GUIA_DIBUJO = {
    "guia": "flat vector cartoon, bold uniform black outlines, 4-6px thick",
    "paleta": ["#c4b8a4", "#1a1a1a", "#8fa8b2", "#ffffff", "#000000",
               "#123456", "#654321", "#abcdef", "#fedcba"],
    "trazo": "Uniform-width black outline",
    "relleno": "flat fills, no gradients",
    "personajes": "oversized round heads, 2-3 heads tall",
    "caras": "dot eyes, no nose",
    "manos": "mitten-shaped, no separate fingers",
    "fondos": "flat colour, no texture",
    "luz": "no cast shadows",
    "composicion": "centred, lots of air",
    "acabado": "clean vector",
    "evitar": "no gradients, no realistic proportions",
    "resumen_es": "dibujo plano",
    "palabras": 12,
}

ESTILOS_ILUSTRACION = {
    "vacio": {},
    "solo_texto": {"guia": "a plain string guide"},
    "monigote": {"referencias": ["a.png"], "guia": GUIA_DIBUJO},
    "con_prompt": {"referencias": ["a.png"], "guia": GUIA_DIBUJO,
                   "prompt": "muted earthy palette"},
}

REFS = [
    {"papel": "estilo", "ruta": "e1.png"},
    {"papel": "estilo", "ruta": "e2.png"},
    {"papel": "reparto", "nombre": "ana", "ruta": "r.png"},
    {"papel": "reparto", "nombre": "ana", "ruta": "r.png", "tapada": True},
    {"papel": "reparto", "nombre": "luis", "ruta": "r2.png", "de_nota": True},
    {"papel": "continuidad", "ruta": "c.png", "mismo_set": True, "desde": "wide"},
    {"papel": "continuidad", "ruta": "c.png"},
    {"papel": "parecido", "ruta": "p.png", "que_es": "politician",
     "rasgos": "grey hair"},
    {"papel": "parecido", "ruta": "p.png"},
    {"papel": "real", "ruta": "x.png", "que_es": "bridge", "nombre": "Golden Gate"},
    {"papel": "real", "ruta": "x.png", "tipo": "logo", "nombre": "Acme"},
    {"papel": "real", "ruta": "x.png"},
    {"papel": "rechazada", "ruta": "z.png"},
    {"papel": "adjunta", "ruta": "y.png", "detalle": "only the red cup"},
]
LAMINA = [{"papel": "lamina", "cuantas": 6, "ruta": "l.png"}]
ESCENAS = {
    "simple": {"prompt": "five hackers at their desks", "luz": "night"},
    "gente": {"prompt": "a family eats", "luz": "noon",
              "personajes": ["ana", "luis"]},
    "nada": {},
}
FICHAS = (
    {"nombre": "nubla", "grupo": True,
     "descripcion": "a small group of young adults in hoodies"},
    {"nombre": "ana", "descripcion": "a woman in a red coat",
     "feedback": "younger"},
    {"nombre": "zorro", "descripcion": "a man wearing a mask"},
)
CATALOGO = {
    "sets": {"bar": {"prompt": "a dim bar with a long counter", "luz": "night"}},
    "componentes": {"mapa": {"prompt": "a flat map"}},
    "reparto": {"ana": {"descripcion": "a woman"},
                "luis": {"descripcion": "a man"}},
    "prompt_por_defecto": "an ordinary place",
    "primer_termino": {"vaso": "a glass of beer"},
}
VISUALES = {
    "redactado": ({"redactado": "Ana counts coins at the bar.",
                   "narracion": "she counted", "personajes": ["ana"],
                   "encuadre": "a wide shot"}, {"tono": "tenso"}),
    "beat_prompt": ({"narracion": "it was late", "direccion": "a clock"},
                    {"prompt": "a street at night"}),
    "abstracta": ({"abstracta": True, "narracion": "four thousand",
                   "personajes": ["ana"], "encuadre": "a clean diagram",
                   "set": "bar"}, {"accion": "money flows", "tono": "alegre"}),
    "abstracta_sola": ({"abstracta": True,
                        "encuadre": "an ethereal composition"}, {}),
    "normal": ({"set": "bar", "personajes": ["ana", "luis"],
                "narracion": "they talk", "primer_termino": "vaso",
                "encuadre": "an over-the-shoulder shot"},
               {"accion": "two people argue", "tono": "neutro"}),
    "componente": ({"componente": "mapa", "narracion": "the route"}, {}),
    "otro_sitio": ({"set": "bar", "personajes": ["ana"],
                    "direccion": "EN OTRO SITIO: a supermarket today"}, {}),
    "vacio": ({}, {}),
}


def _muestras_ilustracion():
    """Todos los prompts del camino de ilustracion, con llamadas de ANTES.

    Solo usa firmas que ya existian antes de la Etapa Foto A (ni `modo=` ni
    funciones nuevas): es lo que permite tomar la huella con el codigo viejo y
    compararla con el nuevo.
    """
    out = {}
    for ne, est in ESTILOS_ILUSTRACION.items():
        out[f"guia_escrita/{ne}"] = p6_assets.guia_escrita(est)
        for nesc, escena in ESCENAS.items():
            for nrefs, refs in (("todas", REFS), ("lamina", LAMINA),
                                ("ninguna", [])):
                for formato in ("", "vertical"):
                    out[f"completo/{ne}/{nesc}/{nrefs}/{formato or 'h'}"] = \
                        p6_assets._prompt_completo(                 # noqa: SLF001
                            escena, refs, est, feedback="the hands are wrong",
                            idioma="es", formato=formato,
                            fichas_reparto={"asset:luis":
                                            {"descripcion": "a tall man"}})
        out[f"completo_corto/{ne}"] = p6_assets._prompt_completo(   # noqa: SLF001
            ESCENAS["simple"], LAMINA, est)
        for ficha in FICHAS:
            out[f"reparto/{ne}/{ficha['nombre']}"] = \
                p6_assets._prompt_reparto(ficha, est)               # noqa: SLF001
        for eje in sorted(moodboard.EJES):
            for con in (True, False):
                out[f"eje/{ne}/{eje}/{con}"] = moodboard.prompt_de_eje(
                    eje, est, "thinner arms", p6_assets.guia_escrita(est),
                    "RULES", con_lamina=con, idioma="es")
        out[f"dibujo/{ne}"] = moodboard.prompt_de_dibujo(
            "x", est, "", ["g"], "R", con_lamina=True,
            encabezado="Produce one single full-frame image for a style "
                       "reference sheet.", idioma="es")
    for indice, ref in enumerate(REFS, start=1):
        out[f"frase/{indice}"] = p6_assets.frase_de_referencia(indice, ref)
    for nombre, (escena, beat) in VISUALES.items():
        out[f"visual/{nombre}"] = p6_assets._prompt_visual(          # noqa: SLF001
            dict(escena), beat, CATALOGO)
    reglas = medios.motor("reglas/reglas.py")
    for ambito in ("prompt_imagen", "reparto"):
        out[f"reglas/{ambito}"] = reglas.bloque_prompt(ambito)
    escenas = [{"id": f"S{n:03d}"} for n in range(1, 120)]
    for semilla in (0, 7, 12345):
        cartas = encuadres.repartir(escenas, semilla=semilla,
                                    forzadas={"S010": "diagrama", "S011": "nope"})
        out[f"cartas/{semilla}"] = [cartas[e["id"]]["id"] for e in escenas]
    out["escalera"] = [dict(c) for c in encuadres.ESCALERA]
    asignadas = [{"id": f"S{n:03d}"} for n in range(1, 30)]
    p6_assets._asignar_cartas(                                      # noqa: SLF001
        asignadas, p6_assets._con_defectos({"semilla": 3,           # noqa: SLF001
                                            "estilo": {"guia": GUIA_DIBUJO}}))
    out["asignadas"] = asignadas
    out["informe"] = p6_assets._repartir_zoom(                      # noqa: SLF001
        [dict(e) for e in asignadas])
    out["describir"] = p6_assets.describir({})
    # las instrucciones con que se escribe una guia de DIBUJO: el contrato de
    # foto va aparte y estas no se pueden mover
    out["guia_instruccion"] = estilo_mod.INSTRUCCION_GUIA
    out["guia_instruccion_descripcion"] = estilo_mod.INSTRUCCION_GUIA_DESCRIPCION
    out["guia_contrato"] = estilo_mod.CONTRATO_JSON_GUIA
    out["tonos"] = p6_assets.TONOS
    # sin `banco_imagenes`, que es una ruta de esta maquina
    out["defectos"] = {k: v for k, v in                             # noqa: SLF001
                       p6_assets._con_defectos({}).items()          # noqa: SLF001
                       if k != "banco_imagenes"}
    return out


def huella(muestras):
    texto = json.dumps(muestras, ensure_ascii=False, sort_keys=True, indent=0)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class ReglasFijas:
    """Pone `reglas.json` en una copia fija mientras dura el bloque."""

    def __enter__(self):
        self.reglas = medios.motor("reglas/reglas.py")
        self.carpeta = tempfile.mkdtemp(prefix="reglas_fijas_")
        ruta = os.path.join(self.carpeta, "reglas.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(REGLAS_FIJAS, fh)
        self.antes = self.reglas.RUTA
        self.reglas.RUTA = ruta
        return self

    def __exit__(self, *_):
        self.reglas.RUTA = self.antes
        shutil.rmtree(self.carpeta, ignore_errors=True)


def prueba_huella():
    titulo("1 · la huella: sin estilo.modo, los prompts de siempre")
    with ReglasFijas():
        muestras = _muestras_ilustracion()
        igual(huella(muestras), HUELLA_ILUSTRACION,
              f"los {len(muestras)} prompts de ilustracion son identicos byte a "
              f"byte a los de antes de la Etapa Foto A")
        # Y "ilustracion" escrito a mano da el mismo texto que no tenerlo: el
        # modo no cambia nada del prompt (la firma si cambiaria, por eso no se
        # escribe; ver la seccion 3).
        for ne, est in ESTILOS_ILUSTRACION.items():
            con = dict(est, modo="ilustracion")
            raro = dict(est, modo="acuarela")
            for nesc, escena in ESCENAS.items():
                base = p6_assets._prompt_completo(escena, REFS, est)  # noqa: SLF001
                igual(p6_assets._prompt_completo(escena, REFS, con),  # noqa: SLF001
                      base, f"{ne}/{nesc}: modo 'ilustracion' = sin modo")
                igual(p6_assets._prompt_completo(escena, REFS, raro),  # noqa: SLF001
                      base, f"{ne}/{nesc}: un modo desconocido se lee como "
                            f"ilustracion")


# ====================================================== 2 · nada por defecto

def prueba_nada_por_defecto():
    titulo("2 · el modo nunca se escribe por defecto")
    ok("modo" not in p6_assets.PARAMS_POR_DEFECTO["estilo"],
       "PARAMS_POR_DEFECTO no trae estilo.modo")
    ok("modo" not in p6_assets._con_defectos({})["estilo"],         # noqa: SLF001
       "_con_defectos no lo anade a un proyecto vacio")
    ok("modo" not in p6_assets._con_defectos(                       # noqa: SLF001
        {"estilo": {"guia": GUIA_DIBUJO}})["estilo"],
       "ni a uno con estilo")
    igual(p6_assets.modo_de({}), "ilustracion", "sin modo es ilustracion")
    igual(p6_assets.modo_de(None), "ilustracion", "sin estilo es ilustracion")
    igual(p6_assets.modo_de({"modo": "foto"}), "foto", "foto es foto")
    igual(p6_assets.modo_de({"modo": "Foto "}), "ilustracion",
          "solo 'foto' exacto es foto: lo demas, ilustracion")

    titulo("2 · estilo_con_modo: lo que se escribe al sembrar el taller")
    igual(presets_light.estilo_con_modo({"guia": "g"}, "ilustracion"), None,
          "ilustracion sobre un estilo sin modo: no hay nada que escribir")
    igual(presets_light.estilo_con_modo({}, "ilustracion"), None,
          "ni sobre un estilo vacio")
    igual(presets_light.estilo_con_modo({"guia": "g"}, "foto"),
          {"guia": "g", "modo": "foto"}, "foto lo escribe")
    igual(presets_light.estilo_con_modo({"modo": "foto"}, "foto"), None,
          "foto sobre foto: nada")
    igual(presets_light.estilo_con_modo({"guia": "g", "modo": "foto"},
                                        "ilustracion"),
          {"guia": "g"}, "volver a ilustracion QUITA la clave, no escribe "
                         "'ilustracion'")

    titulo("2 · lo que se guarda del encargo en el preset")
    claves = presets_canal.CLAVES_ORIGEN
    igual(presets_light.origen_de({"estilo_prompt": "x",
                                   "estilo_modo": "ilustracion"}, claves),
          {"estilo_prompt": "x"},
          "un estilo de ilustracion no guarda estilo_modo (main no lo sabria "
          "leer si se vuelve atras)")
    igual(presets_light.origen_de({"estilo_prompt": "x", "estilo_modo": "foto",
                                   "feedback": ""}, claves),
          {"estilo_prompt": "x", "estilo_modo": "foto"},
          "uno de foto si, y lo vacio se queda fuera como siempre")

    titulo("2 · el encargo del estilo")
    base = {"nombre": "Canal", "idioma": "es", "estilo_imagenes": ["a.png"],
            "tono_prompt": "serio pero cercano", "voz_prompt": "grave"}
    igual(presets_light.validar_encargo(dict(base))["estilo_modo"],
          "ilustracion", "un encargo sin tipo de imagen es ilustracion")
    igual(presets_light.validar_encargo(dict(base, estilo_modo="foto"))
          ["estilo_modo"], "foto", "y con foto, foto")
    try:
        presets_light.validar_encargo(dict(base, estilo_modo="acuarela"))
        ok(False, "un tipo de imagen desconocido se rechaza")
    except presets_light.ErrorEncargo:
        ok(True, "un tipo de imagen desconocido se rechaza")


# ============================================================== 3 · la firma

def _proyecto_listo(base):
    """Un proyecto con todo hasta assets LISTO y un estilo sin modo."""
    proyecto = Proyecto.crear(base, "Video de fiesta")
    estado = Estado(proyecto)
    estado.set_params("ingesta", {"texto": "una fiesta"})
    estado.completar("ingesta", {"transcripcion": "t.json"})
    estado.set_params("brief", {"idioma_salida": "es"})
    estado.completar("brief", {"brief": "b.md"})
    estado.set_params("guion", {"tono": "seco"})
    estado.completar("guion", {"escenas": 2})
    estado.set_params("voz", {"idioma": "es"})
    estado.completar("voz", {"wav": "n.wav"})
    estado.completar("revision_audio", {"wav": "n.wav"})
    estado.set_params("assets", {
        "calidad": "low",
        "estilo": {"referencias": [], "guia": copy.deepcopy(GUIA_DIBUJO)}})
    estado.completar("assets", {"plan": "plan.json"})
    return proyecto, estado


def prueba_firma(base):
    titulo("3 · un proyecto sin estilo.modo no queda obsoleto")
    proyecto, estado = _proyecto_listo(base)
    igual(estado.estado_de("assets"), "listo", "assets arranca listo")
    firma = estado.firma("assets")

    # Lo que la Etapa Foto A pone en el camino de un video de ilustracion:
    # aplicarle su estilo (preset de estilo y de canal, que es lo que hace
    # «Traer los cambios del estilo») y sembrar el modo de un encargo de
    # ilustracion.
    params = {p: estado.params(p) or {} for p in ("brief", "guion", "assets",
                                                   "voz", "callouts")}
    datos = presets_canal.datos_de_params(params, incluir=("estilo",))
    ok("modo" not in (datos.get("estilo") or {}),
       "guardar el estilo de un video de ilustracion no guarda 'modo'")
    for tipo, carga in (("estilo", datos.get("estilo") or {}),
                        ("canal", datos)):
        cambios = presets_canal.cambios_para({"tipo": tipo, "datos": carga},
                                             params)
        for paso, valores in cambios.items():
            estado.actualizar_params(paso, valores)
        ok("modo" not in (estado.params("assets") or {}).get("estilo", {}),
           f"aplicar el preset de {tipo} no escribe estilo.modo")
        igual(estado.estado_de("assets"), "listo",
              f"y assets sigue listo despues de aplicar el de {tipo}")
        igual(estado.firma("assets"), firma, "con la misma firma")
    nuevo = presets_light.estilo_con_modo(
        (estado.params("assets") or {}).get("estilo"), "ilustracion")
    igual(nuevo, None, "sembrar un encargo de ilustracion no escribe nada")

    # Y la prueba no es vacia: pasar a foto SI mueve la firma.
    titulo("3 · pasar a foto si mueve la firma, y volver la deja como estaba")
    con_foto = presets_light.estilo_con_modo(
        (estado.params("assets") or {}).get("estilo"), "foto")
    estado.actualizar_params("assets", {"estilo": con_foto})
    ok(estado.firma("assets") != firma, "con estilo.modo='foto' la firma cambia")
    igual(estado.estado_de("assets"), "obsoleto",
          "y assets pasa a obsoleto: el modo foto pide imagenes nuevas")
    foto = presets_canal.datos_de_params(
        {"assets": estado.params("assets")}, incluir=("estilo",))
    igual((foto.get("estilo") or {}).get("modo"), "foto",
          "un estilo de foto se guarda con modo='foto'")
    # aplicar uno de ilustracion lo quita y todo vuelve a como estaba
    cambios = presets_canal.cambios_para(
        {"tipo": "estilo", "datos": datos.get("estilo") or {}},
        {"assets": estado.params("assets")})
    for paso, valores in cambios.items():
        estado.actualizar_params(paso, valores)
    ok("modo" not in estado.params("assets")["estilo"],
       "aplicar un estilo de ilustracion quita estilo.modo")
    igual(estado.firma("assets"), firma, "y la firma vuelve a la de antes")
    igual(estado.estado_de("assets"), "listo", "y assets vuelve a estar listo")

    # El preset de estilo guarda 'modo' entre sus claves cerradas
    ok("modo" in presets_canal.TIPOS["estilo"]["claves"],
       "el preset de estilo sabe guardar 'modo'")
    ok("estilo_modo" in presets_canal.CLAVES_ORIGEN,
       "y el origen de un canal, 'estilo_modo'")
    shutil.rmtree(proyecto.raiz, ignore_errors=True)


# =========================================================== 4 · modo foto

GUIA_FOTO = {
    "guia": "Photorealistic candid event photography of a real private party.",
    "modo": "foto",
    "paleta": ["#F2EBE3", "#E3D5C3"],
    "camara": "Camera at adult standing eye level, 24-35 mm, f/2.8 to f/4.",
    "luz": "Soft natural daylight mixed with warm interior lamps.",
    "color": "Warm-neutral white balance around 4500-5200 K.",
    "gente": "Ordinary guests of a real party in Lima, Peru.",
    "entorno": "Real homes, terraces and event rooms in Lima.",
    "composicion": "Horizontal 16:9; three depth layers.",
    "acabado": "Subtle natural film grain.",
    "evitar": "No CGI look, no plastic skin.",
    "resumen_es": "Foto realista de evento",
}
ESTILO_FOTO = {"referencias": ["a.png"], "guia": GUIA_FOTO, "modo": "foto"}


def prueba_modo_foto():
    titulo("4 · el prompt de un plano en modo foto")
    reglas = medios.motor("reglas/reglas.py")
    for nesc, escena in ESCENAS.items():
        for nrefs, refs in (("todas", REFS), ("lamina", LAMINA)):
            prompt = p6_assets._prompt_completo(escena, refs,       # noqa: SLF001
                                                ESTILO_FOTO, idioma="es")
            donde = f"{nesc}/{nrefs}"
            ok(prompt.startswith(
                "Create one photorealistic photograph for one shot of a social "
                "media video, as taken by a professional event photographer."),
               f"{donde}: empieza por la cabecera de foto")
            ok("flat vector" not in prompt and "cartoon" not in prompt,
               f"{donde}: no pide «flat vector cartoon» en ningun sitio")
            bloque = reglas.bloque_prompt("prompt_imagen", modo="foto")
            ok(bloque in prompt, f"{donde}: lleva las reglas de foto")
            # la regla `foto-nunca-render` nombra «illustration» para
            # PROHIBIRLA; fuera de las reglas no puede aparecer
            ok("illustration" not in prompt.replace(bloque, ""),
               f"{donde}: ni «illustration» (fuera de la regla que la prohibe)")
            ok("line weight" not in prompt, f"{donde}: ni «line weight»")
    prompt = p6_assets._prompt_completo(ESCENAS["gente"], REFS,     # noqa: SLF001
                                        ESTILO_FOTO)
    for regla in reglas.para("prompt_imagen"):
        ok(regla not in prompt,
           f"no lleva la regla de cartoon «{regla[:50]}…»")
    for linea in ("Camera and lens: Camera at adult",
                  "Colour and grading: Warm-neutral",
                  "People: Ordinary guests", "Setting: Real homes",
                  "Light and shadow: Soft natural",
                  "Never do this, it breaks the style: No CGI"):
        ok(linea in prompt, f"la guia de foto entra: «{linea}»")
    ok("photographic style of reference images" in prompt,
       "las referencias de estilo se presentan por su estilo fotografico")

    titulo("4 · en una foto no se «dibuja» nada")
    # «drawn-together eyebrows» es anatomia (cejas fruncidas), no dibujo
    verbos = re.compile(r"\b(?:[Rr]e)?[Dd]raw(?:s|n|ing)?\b(?!-)")
    for nesc, escena in ESCENAS.items():
        for nrefs, refs in (("todas", REFS), ("lamina", LAMINA)):
            prompt = p6_assets._prompt_completo(                     # noqa: SLF001
                escena, refs, ESTILO_FOTO, feedback="the cup is wrong",
                idioma="es",
                fichas_reparto={"asset:luis": {"descripcion": "a tall man"}})
            fuera = prompt.replace(
                reglas.bloque_prompt("prompt_imagen", modo="foto"), "")
            igual(verbos.findall(fuera), [],
                  f"{nesc}/{nrefs}: ni draw, ni drawn, ni redraw fuera de las "
                  f"reglas")
    for ficha in FICHAS:
        hoja = p6_assets._prompt_reparto(ficha, ESTILO_FOTO)        # noqa: SLF001
        igual(verbos.findall(hoja), [], f"hoja de {ficha['nombre']}: tampoco")
    for nombre, (escena, beat) in VISUALES.items():
        foto = p6_assets._prompt_visual(dict(escena), beat, CATALOGO,  # noqa: SLF001
                                        modo="foto")
        igual(verbos.findall(foto), [], f"plano {nombre}: tampoco")
    igual(p6_assets._expresion("alegre"), p6_assets.TONOS["alegre"],  # noqa: SLF001
          "la expresion alegre de ilustracion es la de siempre")

    titulo("4 · las frases de referencia en modo foto")
    for indice, ref in enumerate(REFS, start=1):
        dibujo = p6_assets.frase_de_referencia(indice, ref)
        foto = p6_assets.frase_de_referencia(indice, ref, modo="foto")
        igual(p6_assets.frase_de_referencia(indice, ref, modo="ilustracion"),
              dibujo, f"{ref['papel']} {indice}: modo='ilustracion' = sin modo")
        if foto:
            ok("flat vector" not in foto and "cartoon" not in foto,
               f"{ref['papel']} {indice}: sin «flat vector cartoon»")
        if ref["papel"] in ("parecido", "real"):
            ok(foto != dibujo, f"{ref['papel']} {indice}: tiene su version de foto")

    titulo("4 · el plano abstracto en modo foto")
    for nombre in ("abstracta", "abstracta_sola"):
        escena, beat = VISUALES[nombre]
        foto = p6_assets._prompt_visual(dict(escena), beat, CATALOGO,  # noqa: SLF001
                                        modo="foto")
        ok("flat vector" not in foto and "stick-figure" not in foto,
           f"{nombre}: sin «flat vector» ni monigotes")
        ok("photographic style" in foto, f"{nombre}: pide el estilo fotografico")
    for nombre, (escena, beat) in VISUALES.items():
        if escena.get("abstracta") or beat.get("tono") == "alegre":
            continue
        igual(p6_assets._prompt_visual(dict(escena), beat, CATALOGO,  # noqa: SLF001
                                       modo="foto"),
              p6_assets._prompt_visual(dict(escena), beat, CATALOGO),  # noqa: SLF001
              f"{nombre}: un plano no abstracto no cambia de texto")

    titulo("4 · la hoja de reparto y las laminas en modo foto")
    for ficha in FICHAS:
        hoja = p6_assets._prompt_reparto(ficha, ESTILO_FOTO)        # noqa: SLF001
        ok(hoja.startswith("Create a photographic reference cast sheet"),
           f"hoja de {ficha['nombre']}: cabecera de foto")
        ok("animated" not in hoja and "line weight" not in hoja,
           f"hoja de {ficha['nombre']}: sin dibujo animado ni trazo")
        ok(reglas.bloque_prompt("reparto", modo="foto") in hoja,
           f"hoja de {ficha['nombre']}: reglas de reparto de foto")
    for eje in sorted(moodboard.EJES):
        lamina = moodboard.prompt_de_eje(eje, ESTILO_FOTO, "",
                                         p6_assets.guia_escrita(ESTILO_FOTO))
        ok(lamina.startswith(moodboard.CABECERA_FOTO),
           f"lamina {eje}: cabecera de foto")
        ok("Draw one single illustration" not in lamina
           and "drawing style" not in lamina,
           f"lamina {eje}: sin «Draw one single illustration»")
    sin_lamina = moodboard.prompt_de_dibujo("x", ESTILO_FOTO, con_lamina=False)
    ok("photographed" in sin_lamina and "drawn" not in sin_lamina,
       "sin lamina, la guia es la unica descripcion de como se FOTOGRAFIA")
    ok(moodboard.prompt_de_dibujo("x", {}).startswith(
        "Draw one single illustration"),
       "y sin modo, la cabecera de siempre")

    titulo("4 · la guia de foto")
    dibujo = p6_assets.guia_escrita({"guia": GUIA_DIBUJO})
    ok(not any(l.startswith(("Camera and lens", "Colour and grading",
                             "People:", "Setting:")) for l in dibujo),
       "una guia de dibujo no saca ninguna linea de foto")
    foto = p6_assets.guia_escrita({"guia": GUIA_FOTO})
    igual([l.split(":")[0] for l in foto],
          ["Style guide, follow it to the letter", "Use this colour palette",
           "Camera and lens", "Light and shadow", "Colour and grading",
           "People", "Setting", "Composition", "Finish and texture",
           "Never do this, it breaks the style"],
          "la de foto saca sus claves, en orden")
    datos = dict(GUIA_FOTO, trazo="no deberia entrar")
    ficha = estilo_mod._ficha_de_guia(datos, "texto", ["/x/a.png"],  # noqa: SLF001
                                      {"modelo": "m"}, 3.2, modo="foto")
    igual(ficha.get("modo"), "foto", "la ficha de una guia de foto dice su modo")
    for clave in ("camara", "luz", "color", "gente", "entorno", "composicion",
                  "acabado", "evitar", "resumen_es", "paleta"):
        ok(ficha.get(clave), f"y trae '{clave}'")
    ok("trazo" not in ficha and "manos" not in ficha,
       "y ninguna clave de dibujo")
    ficha_dibujo = estilo_mod._ficha_de_guia(GUIA_DIBUJO, "texto", [],  # noqa: SLF001
                                             {}, 1.0)
    ok("modo" not in ficha_dibujo and "trazo" in ficha_dibujo,
       "la ficha de dibujo es la de siempre")
    for modo in ("ilustracion", "foto"):
        con = estilo_mod.instruccion_de_guia(modo).format(
            imagenes="  - a.png", carpeta="/x")
        sin = estilo_mod.instruccion_de_guia(modo, con_imagenes=False).format(
            descripcion="fotos de fiesta")
        ok('"guia"' in con and '"guia"' in sin,
           f"las instrucciones de {modo} se formatean con su contrato")
    foto = estilo_mod.instruccion_de_guia("foto").format(imagenes="", carpeta="")
    for clave in ("camara", "color", "gente", "entorno", "resumen_es"):
        ok(f'"{clave}"' in foto, f"el contrato de foto pide '{clave}'")
    ok('"trazo"' not in foto, "y no pide trazo")
    igual(estilo_mod.instruccion_de_guia("ilustracion"),
          estilo_mod.INSTRUCCION_GUIA, "la de dibujo es la de siempre")
    igual(p7_callouts.diseno_sugerido(GUIA_FOTO)[0], "realista",
          "una guia de foto pide el grafismo realista")


# ================================================ 5 · la escalera de foto

def prueba_escalera_foto():
    titulo("5 · la escalera de foto")
    ids = [c["id"] for c in encuadres.ESCALERA_FOTO]
    igual(len(ids), 13, "trece cartas")
    igual(len(set(ids)), 13, "con ids unicos")
    ok(not set(ids) & set(encuadres.POR_ID),
       "y ninguno se confunde con uno de la de ilustracion")
    for carta in encuadres.ESCALERA_FOTO:
        ok(carta["familia"] in ("lejos", "medio", "cerca", "luz", "angulo"),
           f"{carta['id']}: familia conocida")
        ok(int(carta.get("peso") or 0) >= 1, f"{carta['id']}: peso")
        suyos = carta.get("servicios")
        ok(suyos == "todos" or all(s in encuadres.SERVICIOS for s in suyos),
           f"{carta['id']}: servicios conocidos")
        ok(carta["encuadre"] == carta["encuadre"].strip()
           and carta["encuadre"][0].islower()
           and not carta["encuadre"].endswith("."),
           f"{carta['id']}: encuadre en ingles, para pegar tras «SHOT TYPE: »")
        ok(not carta.get("abstracta"), f"{carta['id']}: no es abstracta")
    igual(encuadres.escalera_para("ilustracion", ["simuladores"]),
          encuadres.ESCALERA, "en ilustracion los servicios no filtran nada")

    titulo("5 · servicios")
    igual(encuadres.servicios_de(None), ("consolas",),
          "sin servicios, el servicio base: consolas")
    igual(encuadres.servicios_de("vr, Karaoke ,raro"), ("vr", "karaoke"),
          "se limpian y se quedan los conocidos")
    escenas = [{"id": f"S{n:03d}"} for n in range(1, 400)]
    base = encuadres.repartir(escenas, semilla=7, modo="foto")
    salen = {c["id"] for c in base.values()}
    ok("foto_pedales" not in salen and "foto_vr" not in salen,
       "sin simuladores ni VR no salen pedales ni cuerpo con visor")
    ok({"foto_manos", "foto_estacion", "foto_hombro"} <= salen,
       "y si las manos, la estacion y el hombro")
    todos = encuadres.repartir(escenas, semilla=7, modo="foto",
                               servicios=list(encuadres.SERVICIOS))
    igual({c["id"] for c in todos.values()}, set(ids),
          "con todos los servicios salen las trece")
    karaoke = encuadres.repartir(escenas, semilla=7, modo="foto",
                                 servicios=["karaoke"])
    sal = {c["id"] for c in karaoke.values()}
    ok("foto_manos" not in sal and "foto_perfil" in sal,
       "solo karaoke: perfil si, manos en el mando no")

    titulo("5 · las reglas del reparto, tambien en foto")
    for nombre, reparto in (("base", base), ("todos", todos)):
        orden = [reparto[e["id"]] for e in escenas]
        seguidas = [i for i in range(1, len(orden))
                    if orden[i]["familia"] == orden[i - 1]["familia"]]
        igual(seguidas, [], f"{nombre}: nunca dos familias seguidas")
    igual([c["id"] for c in encuadres.repartir(escenas, 7, modo="foto")
           .values()], [c["id"] for c in base.values()],
          "determinista: misma semilla, mismas cartas")
    forzado = encuadres.repartir(escenas[:5], 7, modo="foto",
                                 forzadas={"S002": "foto_pedales",
                                           "S003": "diagrama"})
    igual(forzado["S002"]["id"], "foto_pedales",
          "una carta de foto forzada a mano manda, aunque salte el filtro")
    ok(forzado["S003"]["id"].startswith("foto_"),
       "una carta de ilustracion forzada no vale en foto")

    titulo("5 · p6 reparte con la escalera del modo")
    planos = [{"id": f"S{n:03d}"} for n in range(1, 30)]
    p6_assets._asignar_cartas(planos, p6_assets._con_defectos(      # noqa: SLF001
        {"semilla": 3, "estilo": dict(ESTILO_FOTO)}))
    ok(all(e["carta"].startswith("foto_") for e in planos),
       "con estilo.modo='foto', todas las cartas son de foto")
    ok(not any(e.get("abstracta") for e in planos), "y ninguna abstracta")
    informe = p6_assets._repartir_zoom(planos, modo="foto")         # noqa: SLF001
    igual(informe["planos_repetidos"], 0, "el informe ve sus familias")
    ok(all(c["id"].startswith("foto_") for c in informe["escalera"]),
       "y ofrece la escalera de foto para forzar a mano")
    planos = [{"id": f"S{n:03d}"} for n in range(1, 200)]
    p6_assets._asignar_cartas(planos, p6_assets._con_defectos(      # noqa: SLF001
        {"semilla": 3, "servicios": ["simuladores"],
         "estilo": dict(ESTILO_FOTO)}))
    cartas = {e["carta"] for e in planos}
    ok("foto_pedales" in cartas and "foto_perfil" not in cartas,
       "el param 'servicios' de assets llega al reparto: con simuladores salen "
       "los pedales y no el perfil (que es de consolas y karaoke)")


def main():
    base = tempfile.mkdtemp(prefix="prueba_modo_foto_")
    try:
        prueba_huella()
        prueba_nada_por_defecto()
        prueba_firma(base)
        prueba_modo_foto()
        prueba_escalera_foto()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print()
    if FALLOS:
        print(f"MODO FOTO: {len(FALLOS)} FALLO(S) de {COMPROBACIONES} "
              f"comprobaciones")
        for fallo in FALLOS:
            print(f"  - {fallo}")
        sys.exit(1)
    print(f"MODO FOTO OK: {COMPROBACIONES} comprobaciones pasan")


if __name__ == "__main__":
    main()

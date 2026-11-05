"""
Prueba de los pasos 4 (voz) y 5 (revision de audio).

Casi todo corre en modo simulado (ESTUDIO_SIMULAR=1): wav de silencio con marcas
sinteticas y reescritura local, para no gastar creditos de Cartesia ni del CLI de
Claude. Al final se hace UNA sola llamada real y corta a Cartesia para verificar
que el envoltorio con __experimental_controls habla de verdad con la API.

    python pasos/prueba_pasos_voz.py
    ... --sin-red      solo simulado, no toca la red
    ... --con-claude   ademas, una reescritura real con el CLI (cuesta unos centimos)
"""
import json
import os
import shutil
import struct
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)

from nucleo.estado import Estado  # noqa: E402
from nucleo.proyecto import Proyecto  # noqa: E402
from nucleo.trabajos import Cancelado, GestorTrabajos  # noqa: E402

import comun  # noqa: E402
import p4_voz  # noqa: E402
import p5_revision_audio as p5  # noqa: E402
import presets_voz  # noqa: E402

FALLOS = []
HECHAS = [0]

GUION = [
    {"id": "S01", "texto": "Octubre de 2007. Un carguero avanza en la oscuridad "
                           "del Pacifico rumbo a la costa mexicana."},
    {"id": "S02", "texto": "Nadie a bordo sabe que la bodega esconde veintitres "
                           "toneladas de precursores quimicos."},
    {"id": "S03", "texto": "Cuando la marina lo aborda, el capitan ya ha lanzado "
                           "los manifiestos por la borda."},
]


def comprobar(condicion, texto):
    """Registra el resultado de una comprobacion y sigue con las demas."""
    HECHAS[0] += 1
    if condicion:
        print(f"  ok   {texto}")
    else:
        print(f"  FALLO {texto}")
        FALLOS.append(texto)


def igual(obtenido, esperado, texto):
    comprobar(obtenido == esperado,
              texto if obtenido == esperado
              else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def falla(funcion, texto, tipo=Exception):
    HECHAS[0] += 1
    try:
        funcion()
    except tipo:
        print(f"  ok   {texto}")
        return
    except Exception as otro:
        print(f"  FALLO {texto}  [excepcion inesperada: {otro!r}]")
        FALLOS.append(texto)
        return
    print(f"  FALLO {texto}  [no fallo]")
    FALLOS.append(texto)


def duracion_wav(ruta):
    """Segundos de un wav PCM s16le mono leyendo la cabecera que escribimos."""
    with open(ruta, "rb") as fh:
        cabecera = fh.read(44)
        datos = os.path.getsize(ruta) - 44
    canales, ritmo = struct.unpack("<H", cabecera[22:24])[0], struct.unpack("<I", cabecera[24:28])[0]
    return datos / float(ritmo * canales * 2), cabecera


def energia_wav(ruta):
    """Suma de valores absolutos del PCM: 0 en un silencio puro."""
    with open(ruta, "rb") as fh:
        fh.seek(44)
        crudo = fh.read()
    muestras = struct.unpack(f"<{len(crudo) // 2}h", crudo[:len(crudo) // 2 * 2])
    return sum(abs(m) for m in muestras)


# ------------------------------------------------------------------- presets

def prueba_presets():
    print("\n[1] presets de voz")
    comprobar(len(presets_voz.PRESETS) >= 6,
              f"hay al menos 6 presets (hay {len(presets_voz.PRESETS)})")
    claves = {"nombre", "descripcion", "modelo", "velocidad", "emociones",
              "hueco_minimo", "voces_sugeridas"}
    for identificador, preset in presets_voz.PRESETS.items():
        comprobar(claves.issubset(preset), f"{identificador} tiene todas las claves")
        comprobar(preset["modelo"] in p4_voz.MODELOS,
                  f"{identificador} usa un modelo valido ({preset['modelo']})")
        comprobar(p4_voz.normalizar_velocidad(preset["velocidad"]) is not None,
                  f"{identificador} tiene velocidad valida")
        try:
            limpias = p4_voz.normalizar_emociones(preset["emociones"])
            comprobar(limpias == list(preset["emociones"]),
                      f"{identificador} usa etiquetas de emocion validas")
        except ValueError as fallo:
            comprobar(False, f"{identificador} emociones invalidas: {fallo}")
        comprobar(isinstance(preset["hueco_minimo"], float)
                  and preset["hueco_minimo"] >= 0,
                  f"{identificador} tiene hueco_minimo numerico")
        comprobar(len(preset["voces_sugeridas"]) >= 1
                  and all(isinstance(v, str) and len(v) == 36
                          for v in preset["voces_sugeridas"]),
                  f"{identificador} sugiere ids de voz con forma de uuid")

    perfiles = {p: (presets_voz.PRESETS[p]["velocidad"],
                    tuple(presets_voz.PRESETS[p]["emociones"]))
                for p in presets_voz.PRESETS}
    igual(len(set(perfiles.values())), len(perfiles),
          "ningun preset es un duplicado de otro")
    igual(len(presets_voz.listar()), len(presets_voz.PRESETS), "listar() los devuelve todos")
    falla(lambda: presets_voz.preset("no_existe"), "preset desconocido falla claro",
          ValueError)


def prueba_controles():
    print("\n[2] controles experimentales")
    igual(p4_voz.construir_controles("slow", ["curiosity:high", "sadness:low"]),
          {"speed": "slow", "emotion": ["curiosity:high", "sadness:low"]},
          "construye speed + emotion")
    igual(p4_voz.construir_controles(None, None), {}, "sin controles, dict vacio")
    igual(p4_voz.construir_controles(-0.4, "anger"),
          {"speed": -0.4, "emotion": ["anger"]}, "acepta velocidad numerica")
    igual(p4_voz.normalizar_emociones(["anger", "anger"]), ["anger"],
          "no repite etiquetas")
    falla(lambda: p4_voz.normalizar_emociones(["melancolia"]),
          "rechaza una emocion inventada", ValueError)
    falla(lambda: p4_voz.normalizar_emociones(["surprise:medium"]),
          "rechaza un nivel inventado", ValueError)
    falla(lambda: p4_voz.normalizar_velocidad("volando"),
          "rechaza una velocidad inventada", ValueError)
    falla(lambda: p4_voz.normalizar_velocidad(3.0),
          "rechaza velocidad numerica fuera de rango", ValueError)

    cfg = p4_voz.resolver_params({"preset": "true_crime_tenso"})
    igual(cfg["velocidad"], "slow", "el preset fija la velocidad")
    igual(cfg["emociones"], ["curiosity:high", "sadness:low"],
          "el preset fija las emociones")
    igual(cfg["voz_id"], presets_voz.PRESETS["true_crime_tenso"]["voces_sugeridas"][0],
          "el preset propone su primera voz")
    cfg = p4_voz.resolver_params({"preset": "true_crime_tenso", "velocidad": "fast",
                                  "voz_id": "x" * 36})
    igual(cfg["velocidad"], "fast", "lo fijado a mano gana al preset")
    igual(cfg["voz_id"], "x" * 36, "la voz elegida a mano gana al preset")
    falla(lambda: p4_voz.resolver_params({"modelo": "sonic-9"}),
          "rechaza un modelo desconocido", ValueError)


def prueba_lectura_guion(base):
    print("\n[3] lectura del guion")
    proyecto = Proyecto.crear(base, "Lectura Guion")
    estado = Estado(proyecto)

    falla(lambda: p4_voz.cargar_guion(proyecto), "sin guion, error explicito",
          RuntimeError)

    estado.set_params("guion", {"tono": "seco", "unidades": {
        "S02": {"texto": GUION[1]["texto"]},
        "S01": {"texto": GUION[0]["texto"]},
    }})
    bloques = p4_voz.cargar_guion(proyecto)
    igual([b["id"] for b in bloques], ["S01", "S02"],
          "lee las unidades del paso guion y las ordena")

    carpeta = proyecto.ruta_paso("guion", 1, crear=True)
    proyecto.fijar_version_activa("guion", 1)
    # forma exacta del guion.json que escribe el paso 3
    with open(os.path.join(carpeta, "guion.json"), "w", encoding="utf-8") as fh:
        json.dump({"titulo": "Caso Meridiano", "guion": GUION, "palabras": 40,
                   "bloques_detalle": [dict(b, palabras=7) for b in GUION]},
                  fh, ensure_ascii=False)
    bloques = p4_voz.cargar_guion(proyecto)
    igual([b["id"] for b in bloques], ["S01", "S02", "S03"],
          "lee el guion.json que deja el paso 3 y manda sobre las unidades")
    igual(bloques[0]["texto"], GUION[0]["texto"], "el texto llega intacto")

    igual([b["id"] for b in p4_voz.cargar_guion(proyecto, {"bloques": GUION[:1]})],
          ["S01"], "los params ganan a todo lo demas")
    igual([b["texto"] for b in p4_voz.normalizar_bloques(
        {"escenas": [{"id": "S01", "narracion": "Hola."}]})],
        ["Hola."], "entiende escenas/narracion del formato del plan")
    igual(len(p4_voz.normalizar_bloques("Uno.\n\nDos.")), 2,
          "entiende un guion en texto plano separado por lineas en blanco")
    igual(p4_voz.normalizar_bloques({"titulo": "Caso Meridiano", "modelo": "sonnet"}),
          [], "un documento cualquiera no se cuela como guion")
    igual([b["id"] for b in p4_voz.normalizar_bloques(
        {"B001": "Uno.", "B002": {"texto": "Dos."}})],
        ["B001", "B002"], "acepta el mapa de unidades con texto suelto o en dict")

    # LO EDITADO A MANO LLEGA AL AUDIO. `params.guion.bloques` es el cajon donde
    # la pantalla guarda lo que una persona reescribe de un bloque, y hasta el
    # 24-08 lo aplicaba SOLO p3_guion al redactar: corregir una frase y darle a
    # grabar locutaba la frase VIEJA, y la unica forma de que llegara era volver
    # a pedirle el guion entero al modelo.
    estado.set_params("guion", {"bloques": {
        "S02": {"texto": "Esto lo he escrito yo."},
        "S99": {"texto": "un bloque que ya no existe"},
    }})
    bloques = p4_voz.cargar_guion(proyecto)
    porid = {b["id"]: b["texto"] for b in bloques}
    igual(porid.get("S02"), "Esto lo he escrito yo.",
          "la edicion a mano manda sobre el guion.json")
    igual(porid.get("S01"), GUION[0]["texto"],
          "y los bloques que nadie ha tocado se quedan como estaban")
    comprobar("S99" not in porid,
              "una edicion de un guion anterior se ignora en silencio: no es un error")
    # Lo que llega por params SI gana a la edicion: ahi hay un guion explicito
    # (una prueba, o la reescritura del paso 5) y pisarlo seria contestar otra
    # cosa a lo que se pide.
    igual([b["texto"] for b in p4_voz.cargar_guion(proyecto, {"bloques": GUION[1:2]})],
          [GUION[1]["texto"]], "un guion explicito en params gana a la edicion")
    estado.set_params("guion", {"bloques": {}})

    # El idioma de la voz sale del brief. Sin esto, un guion escrito en ingles se
    # locutaba en espanol y no fallaba: lo leia con acento y no lo decia nadie.
    igual(p4_voz.idioma_de_salida(proyecto), "", "sin brief no se inventa idioma")
    igual(p4_voz.params_con_idioma(proyecto, {}), {},
          "sin brief, los params se quedan como estaban")
    estado.set_params("brief", {"idiomas_salida": ["en", "es"]})
    igual(p4_voz.idioma_de_salida(proyecto), "en",
          "hereda el idioma principal del brief")
    igual(p4_voz.params_con_idioma(proyecto, {})["idioma"], "en",
          "el idioma vacio se rellena con el del video")
    igual(p4_voz.params_con_idioma(proyecto, {"idioma": "es"})["idioma"], "es",
          "el idioma fijado a mano manda sobre el del video")
    igual(p4_voz.resolver_params(p4_voz.params_con_idioma(proyecto, {}))["idioma"],
          "en", "y llega hasta la configuracion con la que se sintetiza")
    shutil.rmtree(proyecto.raiz)


# --------------------------------------------------------------------- paso 4

def preparar_proyecto(base, nombre="Caso Meridiano"):
    proyecto = Proyecto.crear(base, nombre)
    estado = Estado(proyecto)
    estado.set_params("ingesta", {"url": "https://ejemplo/1"})
    estado.completar("ingesta", {"frames": 0})
    estado.set_params("brief", {"angulo": "seco"})
    estado.completar("brief", {"ok": True})
    estado.set_params("guion", {"unidades": {b["id"]: {"texto": b["texto"]}
                                             for b in GUION}})
    carpeta = proyecto.ruta_trabajo("guion")
    with open(os.path.join(carpeta, "guion.json"), "w", encoding="utf-8") as fh:
        json.dump({"titulo": "Caso Meridiano", "guion": GUION}, fh, ensure_ascii=False)
    estado.completar("guion", {"guion": GUION, "bloques": len(GUION)})
    return proyecto, estado


def prueba_paso4(base):
    print("\n[4] paso 4: voz (simulado)")
    proyecto, estado = preparar_proyecto(base)
    params = {"preset": "documental_sobrio", "hueco_minimo": 1.0,
              "emociones": ["curiosity:low"]}
    estado.set_params("voz", params)
    igual(estado.estado_de("voz"), "pendiente", "voz pendiente tras el guion")

    trazas = []
    salidas = p4_voz.ejecutar(proyecto, params,
                              lambda v, m="": trazas.append((v, m)))

    for clave in ("pista", "duracion", "palabras", "controles"):
        comprobar(clave in salidas, f"salidas trae {clave}")
    comprobar(os.path.exists(salidas["pista"]), "la pista existe en disco")
    segundos, cabecera = duracion_wav(salidas["pista"])
    comprobar(cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WAVE",
              "la pista es un wav valido")
    comprobar(abs(segundos - salidas["duracion"]) < 0.25,
              f"la duracion declarada cuadra con el wav ({segundos:.2f}s)")
    comprobar(salidas["duracion"] > 5, "la toma dura mas de 5 segundos")

    esperadas = sum(len(b["texto"].split()) for b in GUION)
    igual(len(salidas["palabras"]), esperadas,
          "hay una marca por palabra del guion")
    marcas = salidas["palabras"]
    comprobar(all(marcas[i]["e"] <= marcas[i + 1]["s"] + 1e-6
                  for i in range(len(marcas) - 1)),
              "las marcas van en orden y no se solapan")
    comprobar(marcas[-1]["e"] <= salidas["duracion"] + 0.5,
              "la ultima marca cae dentro de la pista")

    igual([b["id"] for b in salidas["bloques"]], ["S01", "S02", "S03"],
          "cada bloque recibe su tramo")
    huecos = [salidas["bloques"][i + 1]["t_in"] - salidas["bloques"][i]["t_out"]
              for i in range(len(salidas["bloques"]) - 1)]
    comprobar(all(h >= 0.99 for h in huecos),
              f"se respeta hueco_minimo=1.0 entre bloques ({[round(h, 2) for h in huecos]})")

    igual(salidas["controles"]["emociones"], ["curiosity:low"],
          "las emociones de los params llegan a los controles")
    igual(salidas["controles"]["experimental_controls"],
          {"speed": "slow", "emotion": ["curiosity:low"]},
          "el bloque __experimental_controls sale montado")
    comprobar(trazas and trazas[-1][0] == 1.0, "el progreso termina en 1.0")

    meta = os.path.join(os.path.dirname(salidas["pista"]), "audio_meta.json")
    comprobar(os.path.exists(meta), "deja audio_meta.json junto a la pista")

    numero = estado.completar("voz", salidas)
    igual(estado.estado_de("voz"), "listo", "el paso queda listo tras completar")
    final = os.path.join(proyecto.ruta_paso("voz"), salidas["archivo"])
    comprobar(os.path.exists(final), f"la pista viaja a la version v{numero}")
    igual(p4_voz.ruta_pista(proyecto, salidas), final,
          "ruta_pista resuelve la pista ya versionada")
    return proyecto, estado, salidas


def prueba_previsualizacion(proyecto):
    print("\n[5] previsualizacion")
    params = {"preset": "divulgacion_cercana"}
    ruta = p4_voz.previsualizar(proyecto, params, segundos=8)
    comprobar(os.path.exists(ruta), "escribe el wav de previsualizacion")
    segundos, _ = duracion_wav(ruta)
    comprobar(3 <= segundos <= 14, f"dura del orden de 8s ({segundos:.2f}s)")
    comprobar(os.path.dirname(ruta).endswith("previsualizaciones"),
              "no ensucia la carpeta de trabajo del paso")
    marca = os.path.getmtime(ruta)
    igual(p4_voz.previsualizar(proyecto, params, segundos=8), ruta,
          "la segunda llamada reutiliza el wav cacheado")
    igual(os.path.getmtime(ruta), marca, "y no lo vuelve a sintetizar")

    texto = p4_voz.recortar_texto(GUION, 8, "slow")
    comprobar(texto.endswith((".", "!", "?")), "el recorte acaba en final de frase")
    comprobar(len(texto.split()) < sum(len(b["texto"].split()) for b in GUION),
              "el recorte es mas corto que el guion entero")


def prueba_escucha_pronunciada(proyecto, base):
    """«ESCUCHAR» SUENA COMO EL VIDEO (16-10-2026): la previsualizacion manda el
    texto saneado y con «Como se pronuncia», y la cache cambia con la lista."""
    print("\n[5b] la escucha pasa por «Como se pronuncia» y por las letras sueltas")
    import pronunciacion as pron  # noqa: PLC0415
    params = {"preset": "divulgacion_cercana",
              "bloques": [{"id": "M1", "texto": "Alquila la PlayStation y la Series S."}]}
    mandado = []
    original = p4_voz._toma_simulada

    def espia(texto, cfg):
        mandado.append(texto)
        return original(texto, cfg)
    antes = os.environ.get("ESTUDIO_PRONUNCIACIONES")
    os.environ["ESTUDIO_PRONUNCIACIONES"] = os.path.join(base, "pron_escucha.json")
    p4_voz._toma_simulada = espia
    try:
        pron.guardar([])
        sin_lista = p4_voz.previsualizar(proyecto, params, segundos=8)
        comprobar(mandado and "<spell>S</spell>" in mandado[-1],
                  f"la letra suelta va a deletrear, como en el video ({mandado[-1:]!r})")
        pron.guardar(pron.validar([{"escrito": "PlayStation", "dicho": "Pléi Estéishon"}]))
        con_lista = p4_voz.previsualizar(proyecto, params, segundos=8)
        comprobar("Pléi Estéishon" in mandado[-1] and "PlayStation" not in mandado[-1],
                  f"a la voz le llega como suena ({mandado[-1]!r})")
        comprobar(con_lista != sin_lista,
                  "cambiar la lista da OTRA escucha: no sigue sonando la vieja")
        with open(con_lista[:-4] + ".json", encoding="utf-8") as fh:
            meta = json.load(fh)
        comprobar("PlayStation" in " ".join(p["w"] for p in meta["palabras"]),
                  "y sus marcas vuelven a la palabra escrita")
        veces = len(mandado)
        igual(p4_voz.previsualizar(proyecto, params, segundos=8), con_lista,
              "con la misma lista se reutiliza la escucha")
        igual(len(mandado), veces, "y no se vuelve a sintetizar (no se paga dos veces)")
    finally:
        p4_voz._toma_simulada = original
        if antes is None:
            os.environ.pop("ESTUDIO_PRONUNCIACIONES", None)
        else:
            os.environ["ESTUDIO_PRONUNCIACIONES"] = antes


def prueba_trabajo_en_segundo_plano(base):
    print("\n[6] paso 4 dentro del gestor de trabajos")
    proyecto, estado = preparar_proyecto(base, "Con Gestor")
    gestor = GestorTrabajos(estado=estado)
    trabajo = gestor.lanzar("voz", lambda avisar: p4_voz.ejecutar(
        proyecto, {"preset": "testimonio_seco"}, avisar), paso="voz")
    ficha = gestor.esperar(trabajo, 120)
    igual(ficha["estado"], "listo", "el trabajo termina bien")
    comprobar(ficha["resultado"] and ficha["resultado"].get("duracion", 0) > 0,
              "el trabajo devuelve las salidas")
    estado.completar("voz", ficha["resultado"])
    igual(estado.estado_de("voz"), "listo", "el grafo queda coherente")

    def cortar(valor, mensaje=""):
        if valor > 0.03:
            raise Cancelado("cancelado a mitad")
        return valor

    falla(lambda: p4_voz.ejecutar(proyecto, {"preset": "testimonio_seco"}, cortar),
          "la cancelacion cooperativa sale del paso, no se traga", Cancelado)
    shutil.rmtree(proyecto.raiz)


# --------------------------------------------------------------------- paso 5

def prueba_paso5(proyecto, estado, salidas_voz):
    print("\n[7] paso 5: revision de audio (simulado)")
    texto_s02 = GUION[1]["texto"]
    fragmento = "veintitres toneladas de precursores quimicos"
    inicio = texto_s02.find(fragmento)
    comentarios = [
        {"id": "C1", "bloque_id": "S02", "inicio_char": inicio,
         "fin_char": inicio + len(fragmento),
         "texto_seleccionado": fragmento,
         "comentario": "veintitres toneladas de efedrina"},
        {"id": "C2", "bloque_id": "S03", "inicio_char": 0, "fin_char": 0,
         "texto_seleccionado": "",
         "comentario": "acorta esto, se hace largo"},
    ]
    estado.set_params("revision_audio", {"comentarios": comentarios})
    igual(estado.estado_de("revision_audio"), "pendiente",
          "revision_audio pendiente con la voz lista")

    trazas = []
    salidas = p5.ejecutar(proyecto, {"comentarios": comentarios},
                          lambda v, m="": trazas.append((v, m)))

    igual(sorted(salidas["bloques_modificados"]), ["S02", "S03"],
          "solo se marcan los bloques comentados")
    textos = {b["id"]: b["texto"] for b in salidas["bloques"]}
    igual(textos["S01"], GUION[0]["texto"], "el bloque sin comentarios no se toca")
    comprobar("efedrina" in textos["S02"],
              "el comentario con offsets reescribe el fragmento seleccionado")
    comprobar("precursores" not in textos["S02"],
              "y el texto original del fragmento desaparece")
    comprobar(len(textos["S03"]) < len(GUION[2]["texto"]),
              "el comentario de acortar deja el bloque mas corto")

    for clave in ("pista", "duracion", "palabras", "controles",
                  "bloques_modificados"):
        comprobar(clave in salidas, f"salidas trae {clave}")
    comprobar(os.path.exists(salidas["pista"]), "regraba la pista completa")
    comprobar(salidas["pista"] != salidas_voz["pista"],
              "la pista nueva no pisa la del paso 4")
    esperadas = sum(len(t.split()) for t in textos.values())
    igual(len(salidas["palabras"]), esperadas,
          "las marcas corresponden al guion reescrito, no al viejo")
    igual(salidas["controles"]["voz_id"], salidas_voz["controles"]["voz_id"],
          "hereda la voz del paso 4")
    igual(salidas["controles"]["emociones"], salidas_voz["controles"]["emociones"],
          "hereda las emociones del paso 4")
    comprobar(all(c["ok"] for c in salidas["cambios"]),
              "ninguna reescritura queda en aviso")
    igual(salidas["avisos"], [], "sin avisos con comentarios bien formados")

    carpeta = os.path.dirname(salidas["pista"])
    comprobar(os.path.exists(os.path.join(carpeta, "guion_revisado.json")),
              "deja el guion revisado en disco")
    estado.completar("revision_audio", salidas)
    igual(estado.estado_de("revision_audio"), "listo", "el paso 5 queda listo")

    print("\n[8] paso 5: casos de borde")
    # Sin comentarios el paso reescribe cero bloques, asi que su resultado ES la
    # toma del paso 4: se sella copiandola, no pagando otra sintesis. Es el
    # boton de "esta bien asi" de la interfaz.
    vacio = p5.ejecutar(proyecto, {"comentarios": []})
    igual(vacio["bloques_modificados"], [],
          "sin comentarios no cambia ningun bloque")
    comprobar(vacio["duracion"] > 0, "y la toma sigue estando entera")
    comprobar(vacio.get("sellada_del_paso_4") is True,
              "sin comentarios se sella la toma del paso 4, no se regraba")
    igual(vacio["duracion"], salidas_voz["duracion"],
          "la toma sellada dura exactamente lo que la del paso 4")
    comprobar(os.path.exists(vacio["pista"]) and vacio["pista"] != salidas_voz["pista"],
              "pero la pista se copia a la carpeta del paso 5, no se referencia")
    igual([b["texto"] for b in vacio["bloques"]],
          [b["texto"] for b in salidas_voz["bloques"]],
          "y el texto sellado es el que se locuto")

    # Si alguien cambia la voz, sellar seria mentir: hay que regrabar.
    otra_voz = p5.ejecutar(proyecto, {"comentarios": [],
                                      "voz": {"velocidad": "slowest"}})
    comprobar(not otra_voz.get("sellada_del_paso_4"),
              "con otros controles de voz no se sella: se vuelve a grabar")
    igual(otra_voz["controles"]["velocidad"], "slowest",
          "y la toma nueva usa los controles pedidos")

    sueltos = p5.ejecutar(proyecto, {"comentarios": [
        {"id": "C9", "bloque_id": "S99", "comentario": "esto no existe"}]})
    comprobar(any("S99" in a for a in sueltos["avisos"]),
              "avisa de un comentario sobre un bloque inexistente")

    desfasado = {"id": "C8", "bloque_id": "S01", "inicio_char": 5, "fin_char": 9,
                 "texto_seleccionado": "carguero", "comentario": "quita esto"}
    inicio, fin = p5.localizar(GUION[0]["texto"], desfasado)
    igual(GUION[0]["texto"][inicio:fin], "carguero",
          "si los offsets mienten, se busca el fragmento seleccionado")
    igual(p5.localizar(GUION[0]["texto"],
                       {"texto_seleccionado": "no esta", "inicio_char": None,
                        "fin_char": None})[0], None,
          "si el fragmento no aparece, la nota es para el bloque entero")

    igual(p5._limpiar_respuesta("```\nAqui tienes:\nTexto final.\n```"),
          "Texto final.", "limpia fences y preambulos de la respuesta del CLI")


def prueba_regrabacion_completa(proyecto):
    print("\n[9] la toma se regraba entera, nunca se empalma")
    comentario = [{"id": "C1", "bloque_id": "S01",
                   "texto_seleccionado": "Octubre de 2007.",
                   "inicio_char": 0, "fin_char": len("Octubre de 2007."),
                   "comentario": "Noviembre de 2007."}]
    salidas = p5.ejecutar(proyecto, {"comentarios": comentario})
    tramos = {b["id"]: (b["t_in"], b["t_out"]) for b in salidas["bloques"]}
    comprobar(tramos["S01"][0] < tramos["S02"][0] < tramos["S03"][0],
              "los tres bloques vienen de la misma toma, en orden")
    comprobar(all(t[0] is not None and t[1] is not None for t in tramos.values()),
              "ningun bloque se queda sin tramo tras la reescritura")
    palabras = salidas["palabras"]
    igual(len(palabras), sum(b["palabras"] for b in salidas["bloques"]),
          "todas las marcas estan asignadas a algun bloque")


# ------------------------------------------------------------------- con red

def prueba_pausas_en_el_montaje(base):
    """La pausa del final de un bloque NO va a la voz: se hace al montar.

    Un <break> parte la generacion; con uno por bloque la toma sonaba a lista
    leida. Ahora la voz recibe el texto sin la cola de silencio y el corte se
    estira despues, con la misma duracion.
    """
    print("\n[9b] las pausas de final de bloque se hacen en el montaje")
    pausa = '<break time="1500ms"/>'
    bloques = [{"id": "B001", "texto": "Primera frase del gancho." + pausa},
               {"id": "B002", "texto": "Segunda frase, sin pausa al final."},
               {"id": "B003", "texto": "Tercera con <break time=\"400ms\"/> una dentro."}]
    cfg = p4_voz.resolver_params({"hueco_minimo": 0.3})
    destino = os.path.join(base, "pausas")
    salidas = p4_voz.sintetizar_bloques(bloques, destino, cfg)
    with open(os.path.join(destino, p4_voz.NOMBRE_META), encoding="utf-8") as fh:
        meta = json.load(fh)
    comprobar("1500ms" not in meta["transcript"],
              "a la voz NO le llega la pausa del final del bloque")
    comprobar("400ms" in meta["transcript"],
              "la de dentro de una frase si, que no se puede hacer al montar")
    comprobar("1500ms" in salidas["bloques"][0]["texto"],
              "la meta guarda el texto anotado entero (la revision compara contra el)")
    fichas = {b["id"]: b for b in salidas["bloques"]}
    hueco = fichas["B002"]["t_in"] - fichas["B001"]["t_out"]
    # la pausa se SUMA al aire entre bloques en la proporcion de la cadencia
    # (desde el 16-10-2026; antes se tomaba el mayor de los dos)
    pedida = 0.3 + 1.5 * p4_voz.cadencia.PARTE_DE_LA_PAUSA
    comprobar(hueco >= pedida - 0.02,
              f"y en el audio el corte de B001 lleva la pausa encima del aire "
              f"({hueco:.2f} s, al menos {pedida:.2f})")
    otro = fichas["B003"]["t_in"] - fichas["B002"]["t_out"]
    comprobar(0.29 <= otro < 1.0,
              f"donde no habia pausa manda el aire entre bloques ({otro:.2f} s)")

    # Y SE SUMA AL HUECO, no se lo traga (16-10-2026). Con el hueco de serie
    # (1 s) y la pausa de 0,9 s del gancho, `max(hueco, pausa)` dejaba el corte
    # del gancho igual que cualquier otro: «las pausas por bloque no figuran».
    bloques = [{"id": "B001", "texto": 'Primera frase del gancho.<break time="900ms"/>'},
               {"id": "B002", "texto": "Segunda frase, sin pausa al final."},
               {"id": "B003", "texto": "Tercera frase y se acabo."}]
    cfg = p4_voz.resolver_params({"hueco_minimo": 1.0})
    salidas = p4_voz.sintetizar_bloques(bloques, os.path.join(base, "pausas_suma"), cfg)
    fichas = {b["id"]: b for b in salidas["bloques"]}
    gancho = fichas["B002"]["t_in"] - fichas["B001"]["t_out"]
    normal = fichas["B003"]["t_in"] - fichas["B002"]["t_out"]
    extra = 0.9 * p4_voz.cadencia.PARTE_DE_LA_PAUSA
    comprobar(abs((gancho - normal) - extra) < 0.06,
              f"el corte con pausa dura {extra:.2f} s MAS que uno normal "
              f"({gancho:.2f} s frente a {normal:.2f} s)")
    comprobar(1.3 <= gancho <= 1.8,
              f"y ronda el segundo y medio que promete el guion ({gancho:.2f} s)")
    estimado = p4_voz.cadencia.aire_de([b["texto"] for b in bloques], 1.0)
    previsto = 2 * (1.0 - p4_voz.cadencia.PAUSA_ENTRE_BLOQUES) + extra
    comprobar(abs(estimado - previsto) < 0.01,
              f"y la estimacion de duracion cuenta ese aire igual ({estimado:.2f} s)")


def prueba_cache_por_clave():
    """EL CACHE SABE CON QUE CLAVE SE BAJO (06-09-2026).

    Se cambio la clave de Cartesia por la de la cuenta donde vive la voz clonada
    del canal, y el desplegable siguio diciendo «no hay voces clonadas en esta
    cuenta»: el catalogo cacheado --934 voces bajadas con la clave anterior--
    todavia estaba dentro de sus siete dias. No fallaba nada, no habia nada que
    mirar y la pantalla mentia. Iba a durar una semana.

    Sin red: se sustituye la descarga por una que cuenta cuantas veces la
    llaman, que es exactamente lo que hay que comprobar. Y se sustituye tambien
    `_hay_clave`, porque sin clave `listar_voces` no llega a pedir nada -- eso
    es lo correcto y lo prueba `prueba_catalogo_voces`, pero aqui lo que se mira
    es lo de DESPUES: que con clave puesta, el cache se invalide al cambiarla.
    """
    print("\n[10b] el cache de voces se invalida al cambiar de clave")
    bajadas = [0]
    real_descargar, real_huella = p4_voz._descargar_voces, p4_voz._huella_clave
    real_hay = p4_voz._hay_clave
    guardado = None
    if os.path.exists(p4_voz.RUTA_CACHE_VOCES):
        with open(p4_voz.RUTA_CACHE_VOCES, "r", encoding="utf-8") as fh:
            guardado = fh.read()

    def falsa():
        bajadas[0] += 1
        return [{"id": "v1", "nombre": "Una", "idioma": "es", "nativa": True,
                 "publica": False, "descripcion": ""}]

    # SIN SIMULADO, pero tampoco con red: la descarga esta sustituida. En
    # simulado `listar_voces` sirve lo cacheado sin mirar la clave, que es otro
    # camino y no el que se esta comprobando.
    simular = os.environ.get("ESTUDIO_SIMULAR")
    try:
        os.environ["ESTUDIO_SIMULAR"] = "0"
        p4_voz._descargar_voces = falsa
        p4_voz._hay_clave = lambda: True
        p4_voz._huella_clave = lambda: "clave_A"
        p4_voz.listar_voces("es")
        igual(bajadas[0], 1, "un cache bajado con OTRA clave no vale: se baja")
        p4_voz.listar_voces("es")
        igual(bajadas[0], 1, "y con cache de la MISMA clave no se vuelve a bajar")

        p4_voz._huella_clave = lambda: "clave_B"
        p4_voz.listar_voces("es")
        igual(bajadas[0], 2, "al cambiar de clave se baja otra vez, sin esperar "
                             "a que caduquen los siete dias")

        # Un cache de antes de esta fecha no lleva huella: se refresca una vez.
        with open(p4_voz.RUTA_CACHE_VOCES, "r", encoding="utf-8") as fh:
            viejo = json.load(fh)
        viejo.pop("clave", None)
        with open(p4_voz.RUTA_CACHE_VOCES, "w", encoding="utf-8") as fh:
            json.dump(viejo, fh)
        p4_voz.listar_voces("es")
        igual(bajadas[0], 3, "un cache sin huella (de antes del 06-09) se "
                             "refresca una vez y ya la tiene")

        # Y SI NO SE PUEDE SABER QUE CLAVE HAY, la huella no opina: lo cacheado
        # es mejor que nada. Sin esto, una maquina sin clave configurada
        # intentaria bajar el catalogo en cada peticion, y fallando.
        p4_voz._huella_clave = lambda: ""
        p4_voz.listar_voces("es")
        igual(bajadas[0], 3, "sin clave legible se sirve lo cacheado y no se "
                             "pide nada")
    finally:
        if simular is None:
            os.environ.pop("ESTUDIO_SIMULAR", None)
        else:
            os.environ["ESTUDIO_SIMULAR"] = simular
        p4_voz._descargar_voces, p4_voz._huella_clave = real_descargar, real_huella
        p4_voz._hay_clave = real_hay
        if guardado is None:
            if os.path.exists(p4_voz.RUTA_CACHE_VOCES):
                os.remove(p4_voz.RUTA_CACHE_VOCES)
        else:
            with open(p4_voz.RUTA_CACHE_VOCES, "w", encoding="utf-8") as fh:
                fh.write(guardado)


def prueba_catalogo_voces(con_red):
    print("\n[10] catalogo de voces")
    if not con_red:
        voces = p4_voz.listar_voces("es")
        comprobar(isinstance(voces, list) and voces,
                  "en simulado devuelve el catalogo minimo o el cacheado")
        return
    os.environ["ESTUDIO_SIMULAR"] = "0"
    try:
        voces = p4_voz.listar_voces("es", refrescar=True)
    finally:
        os.environ["ESTUDIO_SIMULAR"] = "1"
    comprobar(len(voces) > 20, f"lista voces en espanol ({len(voces)})")
    comprobar(all(v["id"] and v["nombre"] for v in voces),
              "cada ficha trae id y nombre")
    comprobar(os.path.exists(p4_voz.RUTA_CACHE_VOCES), "cachea el catalogo en disco")

    todas = p4_voz.listar_voces()
    comprobar(len(todas) > len(voces), f"sin filtro salen mas ({len(todas)})")
    catalogo = {v["id"] for v in todas}
    faltan = [i for p in presets_voz.PRESETS.values()
              for i in p["voces_sugeridas"] if i not in catalogo]
    igual(faltan, [], "todas las voces sugeridas por los presets existen")

    nativas = p4_voz.listar_voces("es", solo_nativas=True)
    comprobar(0 < len(nativas) <= len(voces),
              f"solo_nativas recorta el catalogo ({len(nativas)} de {len(voces)})")
    comprobar(all(v["nativa"] for v in nativas), "y todas son nativas")
    # El ORDEN es lo que se comprueba, no que existan las dos clases: el
    # 21-08-2026 Cartesia devolvia 78 voces en castellano y las 78 nativas, asi
    # que exigir una prestada al final era exigir que su catalogo no mejorara.
    orden_nativas = [bool(v["nativa"]) for v in voces]
    comprobar(orden_nativas == sorted(orden_nativas, reverse=True),
              f"las nativas van primero y las prestadas al final "
              f"({sum(orden_nativas)} nativas de {len(voces)})")
    sugeridas = {v["id"] for v in nativas}
    prestadas = [i for p in presets_voz.PRESETS.values()
                 for i in p["voces_sugeridas"] if i not in sugeridas]
    igual(prestadas, [], "los presets solo proponen voces nativas en espanol")


def prueba_llamada_real(base):
    print("\n[11] UNA llamada real y corta a Cartesia")
    os.environ["ESTUDIO_SIMULAR"] = "0"
    try:
        proyecto = Proyecto.crear(base, "Llamada Real")
        corto = [{"id": "S01", "texto": "Octubre de dos mil siete."},
                 {"id": "S02", "texto": "El carguero ya no responde."}]
        params = {"preset": "true_crime_tenso", "bloques": corto,
                  "hueco_minimo": 0.6}
        salidas = p4_voz.ejecutar(proyecto, params)
    finally:
        os.environ["ESTUDIO_SIMULAR"] = "1"

    comprobar(not salidas["simulado"], "la toma no es simulada")
    comprobar(os.path.exists(salidas["pista"]), "Cartesia devuelve audio")
    segundos, cabecera = duracion_wav(salidas["pista"])
    comprobar(cabecera[:4] == b"RIFF", "el wav real tiene cabecera valida")
    comprobar(2 < segundos < 20, f"dura lo esperable ({segundos:.2f}s)")
    comprobar(energia_wav(salidas["pista"]) > 0, "el audio no es silencio")
    igual(len(salidas["palabras"]),
          sum(len(b["texto"].split()) for b in corto),
          "Cartesia devuelve una marca por palabra")
    comprobar(salidas["palabras"][0]["e"] > salidas["palabras"][0]["s"],
              "las marcas reales tienen duracion")
    huecos = salidas["bloques"][1]["t_in"] - salidas["bloques"][0]["t_out"]
    comprobar(huecos >= 0.59, f"el aire entre bloques se aplica al audio real ({huecos:.2f}s)")
    igual(salidas["controles"]["experimental_controls"],
          {"speed": "slow", "emotion": ["curiosity:high", "sadness:low"]},
          "se enviaron los controles del preset")
    print(f"       pista real: {salidas['pista']}")
    shutil.rmtree(proyecto.raiz, ignore_errors=True)


def prueba_reescritura_real():
    print("\n[12] reescritura real con el CLI de Claude")
    os.environ["ESTUDIO_SIMULAR"] = "0"
    cwd = tempfile.mkdtemp(prefix="estudio_cli_")
    try:
        bloque = dict(GUION[0])
        comentario = [{"id": "C1", "bloque_id": "S01", "inicio_char": 0,
                       "fin_char": len("Octubre de 2007."),
                       "texto_seleccionado": "Octubre de 2007.",
                       "comentario": "cambia la fecha a marzo de 2011"}]
        nuevo, aviso, sobre = p5.reescribir_bloque(bloque, comentario, cwd=cwd)
    finally:
        os.environ["ESTUDIO_SIMULAR"] = "1"
        shutil.rmtree(cwd, ignore_errors=True)
    igual(aviso, "", "el CLI responde sin avisos")
    comprobar("2011" in nuevo, f"aplica la nota al fragmento ({nuevo[:60]}...)")
    comprobar("2007" not in nuevo, "y quita lo que habia")
    comprobar("carguero" in nuevo, "no toca lo que nadie comento")
    comprobar(sobre.get("total_cost_usd") is not None, "registra el coste")


def _hay_clave_cartesia():
    """Si esta maquina puede hablar con Cartesia. -> bool

    Se pregunta al MOTOR, que es quien sabe de donde puede salir la clave (el
    entorno, el almacen que escribe Configuracion, un .env). Repetir esa busqueda
    aqui seria una segunda version que se queda vieja el dia que cambie la
    primera.
    """
    try:
        motor = comun.cargar_motor("voz_cartesia", "voz.py")
        return bool(motor.cargar_api_key())
    except BaseException:                                     # noqa: BLE001
        # `cargar_api_key` aborta con SystemExit --esta escrito como CLI-- y eso
        # no lo captura un `except Exception`
        return False


def prueba_sse_en_utf8():
    """Las marcas de palabra del SSE de Cartesia se leen en UTF-8.

    El SSE llega como `text/event-stream` SIN charset y requests, sin que nadie
    se lo diga, lo lee como Latin-1: «Tú» llegaba como «TÃº» a las marcas, a la
    narracion de cada plano y a los subtitulos (10-10-2026). Aqui se le da una
    respuesta HTTP de verdad (bytes UTF-8, la cabecera sin charset) y se mira
    lo que sale.
    """
    print("\n[sse] las marcas de Cartesia, en UTF-8")
    import base64 as b64                                    # noqa: PLC0415
    import io                                               # noqa: PLC0415
    import requests                                         # noqa: PLC0415
    evento = {"data": b64.b64encode(b"\x00\x00" * 800).decode(),
              "word_timestamps": {"words": ["Tú", "papá", "«ya»"],
                                  "start": [0.0, 0.3, 0.6], "end": [0.3, 0.6, 0.9]}}
    cuerpo = f"data: {json.dumps(evento, ensure_ascii=False)}\n\n".encode("utf-8")

    def falso_post(*_a, **_k):
        r = requests.models.Response()
        r.status_code = 200
        r.headers["Content-Type"] = "text/event-stream"
        r.raw = io.BytesIO(cuerpo)
        # lo que hace el adaptador de requests con esa cabecera: «ISO-8859-1»
        r.encoding = requests.utils.get_encoding_from_headers(r.headers)
        return r

    original_post, original_clave = p4_voz.requests.post, p4_voz.motor.cargar_api_key
    p4_voz.requests.post = falso_post
    p4_voz.motor.cargar_api_key = lambda *a, **k: "clave-falsa"
    try:
        cfg = {"voz_id": "x", "modelo": "sonic-2", "idioma": "es"}
        _wav, _dur, palabras = p4_voz._toma_real("Tú papá ya", cfg, lambda *a: None)
        igual([x["w"] for x in palabras], ["Tú", "papá", "«ya»"],
              "las palabras llegan con sus tildes, no como «TÃº»")
    finally:
        p4_voz.requests.post, p4_voz.motor.cargar_api_key = original_post, original_clave


class _WebsocketFalso:
    """Lo minimo de `websocket-client` que usa `_toma_por_contexto`, sin red.

    `cortar_tras` = cuantos eventos con audio llegan antes de que la conexion
    se caiga; None = conexion rechazada al abrir (no llega nada).
    """

    def __init__(self, cortar_tras):
        self.cortar_tras = cortar_tras
        self.enviados = []
        self.aperturas = 0

    def create_connection(self, _url, timeout=None):
        self.aperturas += 1
        if self.cortar_tras is None:
            raise ConnectionRefusedError("conexion rechazada")
        modulo = self

        class _Conexion:
            def __init__(self):
                self.recibidos = 0

            def send(self, crudo):
                modulo.enviados.append(json.loads(crudo)["transcript"])

            def recv(self):
                import base64 as b64                          # noqa: PLC0415
                if self.recibidos >= modulo.cortar_tras:
                    raise ConnectionResetError("la conexion se ha cortado")
                self.recibidos += 1
                return json.dumps({
                    "data": b64.b64encode(b"\x01\x00" * 4800).decode(),
                    "word_timestamps": {"words": ["Octubre", "de"],
                                        "start": [0.0, 0.2], "end": [0.2, 0.3]}})

            def close(self):
                pass

        return _Conexion()


def prueba_espacio_entre_secciones():
    """Las entradas de un contexto van con un espacio detras (16-10-2026).

    Cartesia junta las entradas TAL CUAL: sin el espacio le llegaba
    «...remata.Primera...» en cada cambio de seccion. Websocket falso: no se
    llama a Cartesia.
    """
    print("\n[secciones] un espacio entre las entradas del contexto")
    falso = _WebsocketFalso(cortar_tras=1)
    originales = (sys.modules.get("websocket"), p4_voz.motor.cargar_api_key)
    sys.modules["websocket"] = falso
    p4_voz.motor.cargar_api_key = lambda *a, **k: "clave-falsa"
    try:
        try:
            p4_voz._toma_por_contexto(["Hola a todos. Esto se remata.",
                                       "Primera frase nueva. ", "Y el cierre."],
                                      {"voz_id": "x", "modelo": "sonic-3.5",
                                       "idioma": "es"}, lambda *a: None)
        except p4_voz.TomaCortada:
            pass                       # el falso corta tras el primer evento
    finally:
        if originales[0] is None:
            sys.modules.pop("websocket", None)
        else:
            sys.modules["websocket"] = originales[0]
        p4_voz.motor.cargar_api_key = originales[1]
    igual(falso.enviados, ["Hola a todos. Esto se remata. ",
                           "Primera frase nueva. ", "Y el cierre."],
          "cada entrada que no es la ultima acaba en UN espacio")
    comprobar("remata.Primera" not in "".join(falso.enviados),
              "y juntas, como las junta Cartesia, no pegan dos palabras")


def prueba_toma_cortada_no_se_paga_dos_veces(base):
    """D4 del informe de arreglos v2b: la voz se pagaba dos veces.

    Si la conexion con Cartesia se cortaba A MITAD de la toma por contexto, se
    caia al camino de una sola vez y volvia a grabar el texto ENTERO: Cartesia
    ya habia cobrado lo que genero, la toma perdia sus secciones y el primer
    gasto no quedaba apuntado. Todo con un websocket y un SSE FALSOS: no se
    llama a Cartesia.
    """
    print("\n[d4] la toma que se corta a mitad no se paga dos veces")
    sys.path.insert(0, os.path.dirname(AQUI))
    from nucleo import coste                                  # noqa: PLC0415
    os.makedirs(os.path.join(base, "toma_cortada"), exist_ok=True)
    proyecto = Proyecto(os.path.join(base, "toma_cortada"))
    # el historico global del gasto es el de verdad: a una copia
    ruta_global = coste.RUTA_GLOBAL
    coste.RUTA_GLOBAL = os.path.join(base, "coste_global.jsonl")
    bloques = [dict(GUION[0]), dict(GUION[1], abre_seccion=True),
               dict(GUION[2], abre_seccion=True)]
    cfg = {"voz_id": "x", "modelo": "sonic-3.5", "idioma": "es"}
    llamadas_sse = []

    def sse_falso(texto, _cfg, _progreso):
        llamadas_sse.append(texto)
        return p4_voz.motor.wav_desde_pcm(b"\x00\x00" * 2400), 0.1, [
            {"w": "Octubre", "s": 0.0, "e": 0.1}]

    originales = (p4_voz._toma_real, p4_voz.motor.cargar_api_key,
                  p4_voz._toma_por_contexto, sys.modules.get("websocket"),
                  os.environ.get("ESTUDIO_SIMULAR"))
    informe = {"enganchado": [], "ausente": []}
    p4_voz._toma_real = sse_falso
    p4_voz.motor.cargar_api_key = lambda *a, **k: "clave-falsa"
    # el medidor DE VERDAD, sobre la toma por contexto de verdad: lo unico falso
    # es la red
    coste._envolver(p4_voz, "_toma_por_contexto", coste._medir_toma_por_contexto,
                    informe, "voz.toma_por_contexto")
    os.environ["ESTUDIO_SIMULAR"] = "0"
    medidor = coste.Medidor(proyecto)
    try:
        # 1. SE CORTA CON AUDIO DENTRO
        falso = _WebsocketFalso(cortar_tras=1)
        sys.modules["websocket"] = falso
        antes = len(medidor.eventos())
        fallo = None
        with coste.contexto(proyecto, "voz"):
            try:
                p4_voz.sintetizar_bloques(bloques, os.path.join(base, "toma_cortada",
                                                                "trabajo"), cfg)
            except RuntimeError as error:
                fallo = error
        igual(len(falso.enviados), 3, "las tres secciones se mandan en un contexto")
        igual(llamadas_sse, [],
              "CON AUDIO YA RECIBIDO NO SE GRABA OTRA VEZ DE UNA TIRADA (se pagaba dos veces)")
        comprobar(fallo is not None and "Cartesia" in str(fallo)
                  and "dos veces" in str(fallo),
                  f"y se para con un mensaje claro para reintentar ({fallo})")
        nuevos = medidor.eventos()[antes:]
        igual([e.get("operacion") for e in nuevos], ["toma_cortada"],
              "EL INTENTO CORTADO QUEDA APUNTADO EN EL GASTO")
        if nuevos:
            igual(nuevos[0]["cantidad"]["caracteres"], sum(coste.caracteres_cobrados(t) for t in falso.enviados),
                  "con los caracteres que se llegaron a mandar")
            comprobar((nuevos[0].get("detalle") or {}).get("audio_recibido_s", 0) > 0,
                      "y cuanto audio habia llegado")

        # 2. SE CAE SIN HABER RECIBIDO NADA: no se ha cobrado, el respaldo vale
        falso = _WebsocketFalso(cortar_tras=None)
        sys.modules["websocket"] = falso
        antes = len(medidor.eventos())
        with coste.contexto(proyecto, "voz"):
            salidas = p4_voz.sintetizar_bloques(
                bloques, os.path.join(base, "toma_cortada", "trabajo2"), cfg)
        igual(len(llamadas_sse), 1,
              "sin nada recibido se sigue cayendo a la toma de una vez (no se ha cobrado nada)")
        igual(medidor.eventos()[antes:], [],
              "y no se apunta ningun gasto inventado por el intento que no llego a nada")
        comprobar(bool(salidas.get("pista")), "y la voz sale")

        # 3. REGRABAR UNA SECCION por el mismo camino: tambien se apunta
        falso = _WebsocketFalso(cortar_tras=1)
        sys.modules["websocket"] = falso
        antes = len(medidor.eventos())
        meta = {"secciones": [{"id": "SB001", "bloques": ["S01"], "t_in": 0.0,
                               "t_out": 1.0}], "palabras": [], "bloques": []}
        with coste.contexto(proyecto, "voz"):
            try:
                p4_voz.regrabar_seccion([dict(GUION[0])], "SB001", cfg, meta,
                                        os.path.join(base, "toma_cortada", "trabajo"))
                comprobar(False, "regrabar una seccion que se corta tiene que fallar")
            except Exception:                               # noqa: BLE001
                comprobar(True, "regrabar una seccion que se corta falla")
        igual([e.get("operacion") for e in medidor.eventos()[antes:]], ["toma_cortada"],
              "y su intento cortado tambien queda apuntado en el gasto")
    finally:
        (p4_voz._toma_real, p4_voz.motor.cargar_api_key, p4_voz._toma_por_contexto,
         websocket_previo, simular) = originales
        if websocket_previo is None:
            sys.modules.pop("websocket", None)
        else:
            sys.modules["websocket"] = websocket_previo
        os.environ["ESTUDIO_SIMULAR"] = simular if simular is not None else "1"
        coste.RUTA_GLOBAL = ruta_global


def prueba_costura_sin_chasquido(base):
    """REGRABAR UNA SECCION NO DEJA UN CHASQUIDO (19-10-2026).

    Lo que se oyo en el «Torneo de 8»: la toma vieja se cortaba en la MARCA de
    la primera palabra de la seccion, que llega un poco tarde, y se quedaban
    ~30 ms del arranque de esa palabra cortados en seco contra el silencio con
    el que empieza la toma nueva. Aqui la toma vieja tiene justo eso: una
    palabra, una pausa, y el arranque de la palabra siguiente 40 ms ANTES de su
    marca; la toma nueva (simulada) es silencio.
    """
    print("\n[costura] regrabar una seccion: sin chasquido en las costuras")
    import numpy as np  # noqa: PLC0415
    sr = p4_voz.SR
    t = np.arange(int(3.0 * sr)) / sr
    voz = np.zeros_like(t)
    tono = lambda a, b: ((t >= a) & (t < b)) * 0.4 * np.sin(2 * np.pi * 220 * t)  # noqa: E731
    voz += tono(0.20, 1.00)          # la palabra de antes
    voz += tono(1.46, 2.40)          # la de la seccion: suena desde 1,46…
    voz += tono(2.70, 3.00)          # …y la de despues
    pcm = (voz * 32767).astype("<i2").tobytes()
    destino = os.path.join(base, "costura")
    os.makedirs(destino, exist_ok=True)
    with open(os.path.join(destino, p4_voz.NOMBRE_PISTA), "wb") as fh:
        fh.write(p4_voz.motor.wav_desde_pcm(pcm))
    meta = {"archivo": p4_voz.NOMBRE_PISTA,
            # …pero su marca dice 1,50: la toma vieja guardaba 40 ms de ella
            "secciones": [{"id": "SB002", "bloques": ["S02"], "t_in": 1.50, "t_out": 2.40}],
            "palabras": [{"w": "antes", "s": 0.20, "e": 1.00},
                         {"w": "seccion", "s": 1.50, "e": 2.40},
                         {"w": "despues", "s": 2.70, "e": 3.00}]}
    bloques = [{"id": "S01", "texto": "antes"}, {"id": "S02", "texto": "seccion"},
               {"id": "S03", "texto": "despues"}]
    p4_voz.regrabar_seccion(bloques, "SB002", {"idioma": "es"}, meta, destino)
    with open(os.path.join(destino, p4_voz.NOMBRE_PISTA), "rb") as fh:
        nueva = np.frombuffer(p4_voz._pcm_de(fh.read()), dtype="<i2").astype(np.float64) / 32768
    salto = float(np.max(np.abs(np.diff(nueva)))) if len(nueva) > 1 else 0.0
    # un seno de 220 Hz a 0,4 cambia como mucho ~0,013 entre dos muestras: un
    # corte en seco desde 0,4 son 0,4 de golpe
    comprobar(salto < 0.05, f"ninguna costura salta de golpe (mayor salto {salto:.3f}; "
                            "un chasquido son ~0,4)")
    arranque = nueva[int(1.40 * sr):int(1.50 * sr)]
    comprobar(float(np.max(np.abs(arranque))) < 0.01 if len(arranque) else True,
              "y el arranque de la palabra vieja no se queda pegado delante de la nueva")

    # LA PAUSA SE QUEDA (revision independiente, 19-10): una pausa alargada por
    # `espaciar` lleva relleno con fundido a cero en sus bordes, y su punto mas
    # tranquilo puede caer pegado a la palabra de ANTES. Buscando el corte en
    # todo el hueco se tiraba la pausa entera y la seccion salia pegada.
    ruido = np.random.default_rng(7).standard_normal(len(t)) * 0.002
    rampa = np.clip((t - 1.0) / 0.5, 0.0, 1.0)        # 0 justo tras la palabra, sube hacia 1,5
    hueco = voz.copy()
    hueco[(t >= 1.0) & (t < 1.5)] = (ruido * rampa)[(t >= 1.0) & (t < 1.5)]
    hueco[(t >= 2.4) & (t < 2.7)] = (ruido * (1 - np.clip((t - 2.4) / 0.3, 0, 1)))[(t >= 2.4) & (t < 2.7)]
    pcm_h = (hueco * 32767).astype("<i2").tobytes()
    desde, hasta = p4_voz._cortes_de_seccion(pcm_h, meta["secciones"][0], meta["palabras"])
    comprobar(desde >= 1.50 - 0.13, f"el corte de antes no se come la pausa (corta en {desde:.2f}, "
                                    "la seccion empieza en 1,50)")
    comprobar(hasta <= 2.40 + 0.13, f"ni el de despues (corta en {hasta:.2f}, la seccion acaba en 2,40)")


def prueba_pronunciacion(base):
    """COMO SE PRONUNCIA (15-10-2026): lo que se manda va como suena, y lo que
    vuelve se devuelve a la palabra escrita sin descuadrar nada."""
    print("\n[pron] como se pronuncia: a la voz como suena, al guion como se escribe")
    import pronunciacion as pron  # noqa: PLC0415
    import marcas_tts  # noqa: PLC0415
    lista = pron.validar([{"escrito": "PlayStation", "dicho": "Pléi Estéishon"},
                          {"escrito": "Just Dance", "dicho": "Yast Dans"},
                          {"escrito": "Nintendo Switch", "dicho": "Nintendo Suích"},
                          {"escrito": "Switch", "dicho": "Suích"},
                          {"escrito": "Logitech", "dicho": "Lóyitec"}])
    igual(pron.aplicar("Alquila la playstation y Just Dance.", lista),
          "Alquila la Pléi Estéishon y Yast Dans.",
          "se cambia la palabra entera, sin mirar mayusculas")
    igual(pron.aplicar("La Nintendo Switch o la Switch", lista),
          "La Nintendo Suích o la Suích", "la mas larga primero, y la corta sigue valiendo")
    igual(pron.aplicar("los Switches", lista), "los Switches",
          "solo palabras enteras: «Switches» no es «Switch»")
    igual(pron.aplicar('Logitech <break time="500ms"/> y <spell>PS</spell>', lista),
          'Lóyitec <break time="500ms"/> y <spell>PS</spell>',
          "nunca dentro de una etiqueta")
    vuelven = [{"w": "la", "s": 0.0, "e": 0.2}, {"w": "Pléi", "s": 0.2, "e": 0.5},
               {"w": "Estéishon,", "s": 0.5, "e": 1.0}, {"w": "y", "s": 1.0, "e": 1.1},
               {"w": "Yast", "s": 1.1, "e": 1.4}, {"w": "dans.", "s": 1.4, "e": 1.9}]
    devueltas = pron.devolver(vuelven, lista)
    igual([p["w"] for p in devueltas], ["la", "PlayStation,", "y", "Just", "Dance."],
          "las marcas vuelven a la palabra escrita, con su puntuacion")
    igual((devueltas[1]["s"], devueltas[1]["e"]), (0.2, 1.0),
          "y con el tiempo de toda la forma dicha")
    igual((devueltas[3]["s"], devueltas[3]["e"], devueltas[4]["s"], devueltas[4]["e"]),
          (1.1, 1.4, 1.4, 1.9),
          "con las mismas palabras dichas que escritas, cada una conserva su tiempo real")
    largas = pron.devolver([{"w": "Pléi", "s": 0.0, "e": 0.4}, {"w": "Estéishon,", "s": 0.4, "e": 1.0}],
                           lista)
    igual([(p["w"], p["s"], p["e"]) for p in largas], [("PlayStation,", 0.0, 1.0)],
          "con más palabras dichas que escritas, la escrita se queda con todo el tramo")
    # LO QUE VIO LA REVISION (15-10-2026): una entrada con letra suelta y una coma
    con_letra = pron.validar([{"escrito": "Xbox Series X", "dicho": "Équis Box Síries Équis"},
                              {"escrito": "Xbox", "dicho": "Équis Box"}])
    igual(pron.aplicar(marcas_tts.sanear("La Xbox Series X es potente."), con_letra),
          "La Équis Box Síries Équis es potente.",
          "una entrada con letra suelta casa aunque la letra ya vaya a deletrearse")
    igual([p["w"] for p in pron.devolver(
        [{"w": "Nintendo,", "s": 0.0, "e": 0.4}, {"w": "Suích.", "s": 0.4, "e": 0.8}], lista)],
        ["Nintendo,", "Switch."], "la coma de «Nintendo, Switch» no se pierde al devolver")
    falla(lambda: pron.validar([{"escrito": "x<y", "dicho": "z"}]), "una etiqueta en la lista se rechaza",
          ValueError)
    falla(lambda: pron.validar([{"escrito": "Xbox", "dicho": ""}]), "una fila a medias se rechaza",
          ValueError)

    # DE PUNTA A PUNTA, con la toma simulada: que se MANDA y que se GUARDA
    ruta = os.path.join(base, "pronunciaciones.json")
    antes = os.environ.get("ESTUDIO_PRONUNCIACIONES")
    os.environ["ESTUDIO_PRONUNCIACIONES"] = ruta
    try:
        pron.guardar(lista)
        mandado = []
        original = p4_voz._toma_simulada

        def espia(texto, cfg):
            mandado.append(texto)
            return original(texto, cfg)
        p4_voz._toma_simulada = espia
        bloques = [{"id": "B01", "texto": "Alquila la PlayStation para tu fiesta."},
                   {"id": "B02", "texto": "Y si buscas mas, Just Dance o Logitech."}]
        cfg = {"voz_id": "x", "modelo": "sonic-3.5", "idioma": "es", "hueco_minimo": 0.0}
        try:
            salidas = p4_voz.sintetizar_bloques(bloques, os.path.join(base, "pron"), cfg)
        finally:
            p4_voz._toma_simulada = original
        oido = " ".join(mandado)
        comprobar("Pléi Estéishon" in oido and "Yast Dans" in oido and "Lóyitec" in oido,
                  f"a la voz le llega como suena ({oido!r})")
        comprobar("PlayStation" not in oido, "y no la palabra escrita")
        escritas = [p["w"] for p in salidas["palabras"]]
        igual(len(escritas), sum(len(b["texto"].split()) for b in bloques),
              "una marca por palabra ESCRITA: los cortes de plano no se descuadran")
        comprobar("PlayStation" in escritas and "Dance" in " ".join(escritas),
                  "y las marcas dicen la palabra escrita (subtitulos y revision)")
        por_bloque = {b["id"]: b for b in salidas["bloques"]}
        comprobar(por_bloque["B01"]["t_out"] <= por_bloque["B02"]["t_in"] + 1e-6,
                  "cada bloque conserva su tramo")
    finally:
        if antes is None:
            os.environ.pop("ESTUDIO_PRONUNCIACIONES", None)
        else:
            os.environ["ESTUDIO_PRONUNCIACIONES"] = antes


def main():
    con_red = "--sin-red" not in sys.argv
    con_claude = "--con-claude" in sys.argv
    # SIN CLAVE DE CARTESIA NO SE SALE A LA RED, y no es un fallo: es una suite
    # que no puede correr esa parte en esta maquina. Antes moria con el
    # SystemExit del motor --«No encuentro CARTESIA_API_KEY»-- y en la tanda
    # entera eso se leia igual que un rojo de verdad.
    if con_red and not _hay_clave_cartesia():
        con_red = False
        print("(sin CARTESIA_API_KEY: se omite lo que sale a la red. Ponla en "
              "Configuracion para probar el catalogo y una toma real)")
    os.environ["ESTUDIO_SIMULAR"] = "1"
    base = tempfile.mkdtemp(prefix="estudio_voz_")
    # EL HISTORICO, A UNA COPIA. Esta suite sale a Cartesia de verdad con frases
    # de DIEZ palabras y anota su cadencia: en el historico real esas muestras
    # decian 2,7 palabras/s en castellano --mas rapido que el ingles medido-- y
    # con ellas dentro pedir la voz 'slow' salia MAS rapida que 'normal'.
    # `cadencia.PALABRAS_MINIMAS_MEDIDA` lo defiende; esto lo evita de raiz.
    os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(base, "estadisticas.json")
    # Y EL GASTO: la prueba de la toma cortada anota en el medidor, y el
    # historico global es el gasto de verdad
    os.environ["ESTUDIO_COSTE_GLOBAL"] = os.path.join(base, "coste_global.jsonl")
    # la lista de «Como se pronuncia» de la maquina no entra en las pruebas
    os.environ["ESTUDIO_PRONUNCIACIONES"] = os.path.join(base, "sin_pronunciaciones.json")
    with open(os.environ["ESTUDIO_PRONUNCIACIONES"], "w", encoding="utf-8") as fh:
        fh.write('{"lista": []}')
    print(f"proyectos de prueba en {base}")
    try:
        prueba_presets()
        prueba_controles()
        prueba_lectura_guion(base)
        proyecto, estado, salidas = prueba_paso4(base)
        prueba_previsualizacion(proyecto)
        prueba_escucha_pronunciada(proyecto, base)
        prueba_trabajo_en_segundo_plano(base)
        prueba_paso5(proyecto, estado, salidas)
        prueba_regrabacion_completa(proyecto)
        prueba_pausas_en_el_montaje(base)
        prueba_cache_por_clave()
        prueba_sse_en_utf8()
        prueba_espacio_entre_secciones()
        prueba_toma_cortada_no_se_paga_dos_veces(base)
        prueba_costura_sin_chasquido(base)
        prueba_pronunciacion(base)
        prueba_catalogo_voces(con_red)
        if con_red:
            prueba_llamada_real(base)
        else:
            print("\n[11] llamada real omitida (--sin-red)")
        if con_claude:
            prueba_reescritura_real()
        else:
            print("\n[12] reescritura real omitida (pasa --con-claude para probarla)")
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    if FALLOS:
        print(f"PASOS 4 Y 5: {len(FALLOS)} de {HECHAS[0]} comprobaciones fallan")
        for texto in FALLOS:
            print(f"  - {texto}")
        return 1
    print(f"PASOS 4 Y 5 OK: {HECHAS[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

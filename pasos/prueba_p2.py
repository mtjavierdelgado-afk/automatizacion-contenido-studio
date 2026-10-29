"""
Prueba del paso 2 (brief).

El paso no llama a ningun modelo, asi que la prueba es completa y rapida:
normalizacion de idiomas, presupuesto de palabras, validaciones, avisos contra
el material de la ingesta e integracion con el nucleo.

    python pasos/prueba_p2.py
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comun
import p2_brief
from nucleo import Estado, Proyecto

FALLOS = []


def comprobar(condicion, texto):
    """Registra el resultado de una comprobacion y sigue con las demas."""
    if condicion:
        print(f"  ok   {texto}")
    else:
        print(f"  FALLO {texto}")
        FALLOS.append(texto)


def igual(obtenido, esperado, texto):
    comprobar(obtenido == esperado,
              texto if obtenido == esperado
              else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def falla(funcion, texto):
    try:
        funcion()
    except ValueError as fallo:
        comprobar(bool(str(fallo)), f"{texto} -> ValueError: {fallo}")
        return
    comprobar(False, f"{texto} (no fallo)")


def sin_progreso(valor, mensaje=""):
    return valor


def fabricar_ingesta(proyecto, estado, palabras=700, duracion=300, idioma="en"):
    """Deja una version de ingesta creible sin correr el paso 1."""
    trabajo = comun.preparar_trabajo(proyecto, "ingesta")
    frase = "the refinery bought every barrel that reached the river docks"
    por_frase = len(frase.split())
    entradas = max(1, palabras // por_frase)
    paso = duracion / entradas
    transcript = [{"t_in": round(i * paso, 2), "t_out": round((i + 1) * paso, 2),
                   "texto": frase} for i in range(entradas)]
    comun.escribir_json(os.path.join(trabajo, "ingesta.json"), {
        "transcript": transcript,
        "frames_utiles": [],
        "video": "video.webm",
        "metadatos": {"titulo": "Video de referencia", "url": "https://ejemplo/1",
                      "duracion_s": duracion, "idioma_transcript": idioma,
                      "palabras_transcript": entradas * por_frase},
    })
    estado.completar("ingesta", {"resumen": "ingesta simulada"})


def prueba_idiomas():
    print("\n[1] idiomas y cadencia")
    for entrada, esperado in (("es", "es"), ("ES", "es"), ("es-ES", "es"),
                              ("espanol", "es"), ("Español", "es"),
                              ("spanish", "es"), ("English", "en"),
                              ("en_US", "en"), ("pt-BR", "pt"), ("", "")):
        igual(p2_brief.normalizar_idioma(entrada), esperado,
              f"normalizar_idioma({entrada!r})")

    # El ingles ya no son 2,6: son 2,553, MEDIDO sobre la toma del video largo
    # (369 palabras en 144,51 s de sintesis). El espanol sigue siendo la cifra
    # escrita porque no hay ninguna toma en espanol que medir. Ver cadencia.py.
    igual(p2_brief.palabras_por_segundo("en"), 2.553, "cadencia en ingles")
    igual(p2_brief.palabras_por_segundo("espanol"), 2.3, "cadencia en espanol")
    igual(p2_brief.palabras_por_segundo("fi"), p2_brief.PALABRAS_POR_SEGUNDO_OTROS,
          "idioma sin medir usa el punto medio")

    # LA VELOCIDAD MUEVE LA CUENTA, que es la mitad de por que esto se rehizo:
    # el mismo idioma a 'slow' cabe en menos palabras.
    comprobar(p2_brief.palabras_por_segundo("es", "slow")
              < p2_brief.palabras_por_segundo("es", "normal")
              < p2_brief.palabras_por_segundo("es", "fast"),
              "la velocidad ordena la cadencia")

    # Sin aire entre bloques solo descuentan las PAUSAS DE BLOQUE que se preven
    # (la del gancho y la de cada cambio de tema: 0,9 s x 0,6 cada una), que la
    # voz mete igual con hueco 0. Antes del 16-10 no se contaban: 414, 460 y 153.
    # Un minuto es un CORTO y prevé sus dos pausas, no tres: 148 -> 150 (18-10).
    igual(p2_brief.presupuesto_de(180, "es"), 409, "180 s en espanol = 409 palabras")
    igual(p2_brief.presupuesto_de(180, "en"), 454, "180 s en ingles = 454 palabras")
    igual(p2_brief.presupuesto_de(60, "en"), 150, "60 s en ingles = 150 palabras")

    # Y CON AIRE CABEN MENOS: el silencio entre bloques son segundos que no dice
    # nadie. Con 1 s de hueco y bloques de 30 palabras, 180 s pierden unos 6 s.
    comprobar(p2_brief.presupuesto_de(180, "es", "normal", 1.0, 30) < 414,
              "el aire entre bloques descuenta palabras")

    # UNA SOLA TABLA DE VELOCIDAD, y el factor de TIEMPO es su inverso exacto.
    # Habia dos --el multiplicador que recibe Cartesia en `p4_voz` y un factor
    # escrito a mano en `cadencia`-- y no coincidian: 0,72 de tiempo son 1,39x
    # de velocidad, no 1,30x. O sea que lo que se le pedia a la voz y lo que se
    # estimaba que iba a durar no eran el mismo mando.
    import cadencia as cad                                   # noqa: PLC0415
    import p4_voz                                            # noqa: PLC0415
    igual(p4_voz.SPEED_DE_PRESET, cad.VELOCIDAD_API,
          "el multiplicador que recibe la voz sale de la tabla de cadencia")
    for nombre, api in cad.VELOCIDAD_API.items():
        igual(round(cad.FACTOR_VELOCIDAD[nombre] * api, 3), 1.0,
              f"'{nombre}': el factor de tiempo es el inverso del de velocidad")

    # LA VOZ ENTRA EN LA CUENTA. Medido: dos voces inglesas con el mismo modelo
    # dan 2,553 y 1,91 palabras/s a velocidad normal. Sin esto, cambiar de voz
    # dejaba el presupuesto igual y la toma duraba otra cosa.
    comprobar("voz_id" in p2_brief.PARAMS_POR_DEFECTO,
              "el brief declara la voz con la que hace la cuenta")
    igual(p2_brief.palabras_por_segundo("en", "normal", "una-voz-sin-tomas"),
          p2_brief.palabras_por_segundo("en", "normal"),
          "sin tomas de esa voz manda la tabla del idioma")
    ficha = p2_brief.horquilla_de(240, "en", 0.30, "normal", 1.0, 30, "vx")
    comprobar(ficha["presupuesto_palabras"] > 0,
              "la horquilla acepta la voz sin romperse")


def prueba_params():
    print("\n[2] parametros")
    for clave in ("instrucciones", "idioma_salida", "duracion_objetivo_s"):
        comprobar(clave in p2_brief.PARAMS_POR_DEFECTO,
                  f"PARAMS_POR_DEFECTO trae {clave}")

    falla(lambda: p2_brief._normalizar({"instrucciones": "   "}), "brief vacio")
    falla(lambda: p2_brief._normalizar({"instrucciones": "algo", "duracion_objetivo_s": 99999}),
          "duracion por encima del maximo")
    falla(lambda: p2_brief._normalizar({"instrucciones": "algo", "duracion_objetivo_s": "tres"}),
          "duracion que no es un numero")

    # El minimo de 10 minutos era linea editorial disfrazada de regla del
    # sistema y se quito: un video de un minuto es un video. Lo que queda es un
    # suelo TECNICO, lo justo para que haya algo que segmentar.
    corta = p2_brief._normalizar({"instrucciones": "algo", "duracion_objetivo_s": 60})
    igual(corta["duracion_objetivo_s"], 60,
          "un video de 60 s se respeta tal cual, sin subirlo a ningun minimo")
    igual(corta["duracion_pedida_s"], 60, "se recuerda lo que se pidio")
    bajo_suelo = p2_brief._normalizar({"instrucciones": "algo", "duracion_objetivo_s": 3})
    igual(bajo_suelo["duracion_objetivo_s"], p2_brief.DURACION_MINIMA_S,
          "por debajo del suelo tecnico si se sube, que si no no hay ni un plano")
    igual(bajo_suelo["duracion_pedida_s"], 3, "y se recuerda lo que se pidio")
    pasada = p2_brief._normalizar({"instrucciones": "algo", "tolerancia": 1.5})
    igual(pasada["tolerancia"], p2_brief.TOLERANCIA_MAXIMA,
          "la tolerancia se recorta al maximo admitido")

    opciones = p2_brief._normalizar({"instrucciones": "  menos tecnicismos  ",
                                     "idioma_salida": "Español",
                                     "duracion_objetivo_s": "840.6"})
    igual(opciones["instrucciones"], "menos tecnicismos", "las instrucciones se limpian")
    igual(opciones["idioma_salida"], "es", "el idioma se normaliza")
    igual(opciones["duracion_objetivo_s"], 841, "la duracion se redondea a entero")

    # UN VIDEO, UN IDIOMA. La lista vieja se sigue LEYENDO --se coge el primero,
    # que era el principal-- para que un proyecto guardado con el eje de idiomas
    # no se abra de pronto en otro idioma; no se vuelve a escribir.
    viejo = p2_brief._normalizar({"instrucciones": "algo",
                                  "idiomas_salida": ["English", "es"]})
    igual(viejo["idioma_salida"], "en", "de la lista vieja se coge el primero")
    comprobar("idiomas_salida" not in viejo, "y la lista no se vuelve a escribir")
    nuevo = p2_brief._normalizar({"instrucciones": "algo", "idioma_salida": "pt",
                                  "idiomas_salida": ["en"]})
    igual(nuevo["idioma_salida"], "pt", "la clave nueva gana a la vieja")

    resumen = p2_brief.describir({"instrucciones": "mas centrado en las cifras",
                                  "idioma_salida": "es", "duracion_objetivo_s": 900})
    # 2070 antes de que la cuenta descontara el aire entre bloques, y 2000
    # antes de que contara tambien las pausas de bloque (16-10-2026).
    comprobar("\n" not in resumen and "1989" in resumen,
              f"describir da una linea con el presupuesto: {resumen}")


def prueba_sin_ingesta(base):
    print("\n[3] brief sin material de ingesta")
    proyecto = Proyecto.crear(base, "Brief Suelto")
    salidas = p2_brief.ejecutar(proyecto, {
        "instrucciones": "el mismo video pero con menos tecnicismos",
        "idioma_salida": "es", "duracion_objetivo_s": 180}, sin_progreso)

    # 180 s a 2,3 pal/s serian 414 palabras, pero el paso descuenta el AIRE que
    # se inserta entre bloques (hueco_minimo 1,0 s de fabrica): con 13 bloques
    # son unos 6 s, y las 4 pausas de bloque previstas otros 2 s, que no dice
    # nadie: 396 palabras (401 antes de contar las pausas, el 16-10-2026). Antes
    # esto se subia a 600 s y devolvia 1380 palabras para un video de 3 minutos.
    igual(salidas["presupuesto_palabras"], 396,
          "180 s en espanol son 396 palabras con el aire descontado")
    igual(salidas["brief"]["velocidad"], "normal", "la velocidad queda escrita")
    comprobar(salidas["brief"]["aire_s"] > 0, "y el aire descontado, tambien")
    comprobar(not any("suelo tecnico" in aviso for aviso in salidas["brief"]["avisos"]),
              "y no avisa de haber subido nada, porque no ha subido nada")
    comprobar(any("no hay ingesta" in aviso for aviso in salidas["brief"]["avisos"]),
              "avisa de que no ha podido contrastar con la ingesta")
    trabajo = proyecto.ruta_trabajo("brief", crear=False)
    comprobar(os.path.exists(os.path.join(trabajo, "brief.json")), "escribe brief.json")
    comprobar(os.path.exists(os.path.join(trabajo, "brief.txt")), "escribe brief.txt")


def prueba_con_ingesta(base):
    print("\n[4] brief contrastado con la ingesta")
    proyecto = Proyecto.crear(base, "Brief Con Material")
    estado = Estado(proyecto)
    fabricar_ingesta(proyecto, estado, palabras=700, duracion=300, idioma="en")

    avisos = []
    salidas = p2_brief.ejecutar(proyecto, {
        "instrucciones": "mas centrado en las cifras y en como se financio",
        "idioma_salida": "es", "duracion_objetivo_s": 600},
        lambda valor, mensaje="": avisos.append((valor, mensaje)))

    brief = salidas["brief"]
    igual(sorted(k for k in ("brief", "presupuesto_palabras") if k in salidas),
          ["brief", "presupuesto_palabras"], "las salidas traen las claves del contrato")
    igual(salidas["presupuesto_palabras"], 1325,
          "600 s en espanol = 1325 palabras (1380 menos el aire y las pausas de bloque)")
    igual(brief["margen"], {"minimo": 927, "maximo": 1722, "tolerancia": 0.30},
          "la horquilla es el presupuesto mas menos el 30%")
    igual([brief["palabras_minimo"], brief["palabras_maximo"]], [927, 1722],
          "el minimo y el maximo de palabras van sueltos en el brief")
    igual(brief["bloques_estimados"], 44, "bloques estimados a 30 palabras por bloque")
    # LA HORQUILLA, DE VUELTA EN SEGUNDOS. Es lo que se le ensena a quien pidio
    # una duracion: cuanto se puede desviar de verdad el video que va a salir.
    comprobar(brief["segundos_minimo"] < 600 < brief["segundos_maximo"],
              "los 600 s pedidos caen dentro de la horquilla en segundos")

    textos = " | ".join(brief["avisos"])
    comprobar("pides 600s" in textos, f"avisa de que el objetivo dobla al original: {textos}")
    comprobar("supera al transcript" in textos, "avisa de que no hay material para tanto")
    comprobar("ingles" in textos and "espanol" in textos, "avisa del cambio de idioma")
    comprobar("ningun frame util" in textos, "avisa de que no hay referencia visual")
    igual(brief["referencia"]["palabras_transcript"], 700,
          "la referencia recoge las palabras del transcript")

    valores = [v for v, _ in avisos]
    comprobar(valores == sorted(valores) and valores[-1] == 1.0,
              "el progreso avanza y acaba en 1.0")

    with open(os.path.join(proyecto.ruta_trabajo("brief", crear=False), "brief.json"),
              "r", encoding="utf-8") as fh:
        igual(json.load(fh)["presupuesto_palabras"], 1325,
              "brief.json en disco coincide con las salidas")

    print("\n[5] integracion con el nucleo")
    igual(estado.estado_de("brief"), "pendiente", "antes de completar esta pendiente")
    estado.completar("brief", salidas)
    igual(estado.estado_de("brief"), "listo", "tras completar queda listo")
    igual(estado.estado_de("guion"), "pendiente", "el guion se desbloquea")
    comprobar(os.path.exists(os.path.join(proyecto.ruta_paso("brief"), "brief.json")),
              "brief.json viajo a la version v1")

    estado.set_params("brief", {"instrucciones": "otra cosa"})
    igual(estado.estado_de("brief"), "obsoleto", "cambiar el brief lo deja obsoleto")


def _guion_al_presupuesto(segundos, ficha):
    """Un guion escrito al presupuesto de `ficha`, con las pausas de bloque que
    pone `p3_guion` (la del gancho y una por tramo, 900 ms) repartidas."""
    import cadencia                                           # noqa: PLC0415
    bloques, palabras = ficha["bloques"], ficha["palabras"]
    pausas = cadencia.pausas_previstas(segundos, bloques)
    con_pausa = {round(i * (bloques - 1) / max(1, pausas)) for i in range(pausas)}
    textos = []
    for i in range(bloques):
        cuantas = palabras // bloques + (1 if i < palabras % bloques else 0)
        texto = " ".join(["palabra"] * cuantas) + "."
        if i in con_pausa and i < bloques - 1:
            texto += '<break time="900ms"/>'
        textos.append(texto)
    return textos


def prueba_pausas_en_la_horquilla():
    """El presupuesto cuenta las pausas de bloque (16-10-2026).

    Desde que la pausa del gancho y de cada cambio de tema se SUMA al aire entre
    bloques (0,9 s x `PARTE_DE_LA_PAUSA`), `estimar` y `aire_de` la contaban y
    `palabras_para` no: el guion se escribia para pausas mas cortas y el video
    salia unos segundos mas largo de lo pedido.
    """
    print("\n[6] la horquilla cuenta las pausas de bloque")
    import cadencia                                           # noqa: PLC0415
    import p3_guion                                           # noqa: PLC0415
    for segundos in (120, 240, 600):
        ficha = cadencia.palabras_para(segundos, "es", "normal", 1.0, 30)
        textos = _guion_al_presupuesto(segundos, ficha)
        habla = ficha["palabras"] / ficha["cadencia_palabras_s"]
        dura = habla + cadencia.aire_de(textos, 1.0)
        comprobar(abs(dura - segundos) < 1.0,
                  f"un guion de {segundos} s escrito al presupuesto dura {dura:.1f} s "
                  f"({ficha['palabras']} palabras, "
                  f"{cadencia.pausas_previstas(segundos, ficha['bloques'])} pausas)")
        vuelta = cadencia.segundos_para(ficha["palabras"], "es", "normal", 1.0, 30)
        comprobar(abs(vuelta - segundos) < 1.0,
                  f"y segundos_para, la inversa, devuelve {vuelta:.1f} s")
    igual(cadencia.pausas_previstas(180, 13), 4, "tres minutos: cuatro tramos (regla 11)")
    igual(cadencia.pausas_previstas(900, 66), 10, "quince minutos: diez, el tope")
    igual(cadencia.pausas_previstas(60, 2), 1, "nunca mas pausas que costuras")
    # LOS CORTOS (18-10-2026): su guion es gancho -> caso -> cierre, o sea dos
    # pausas de parada. Se escribe el guion con las pausas QUE DE VERDAD LLEVA,
    # no con las que preve la cuenta: con la regla de los largos el video de un
    # minuto salia medio segundo por debajo de lo pedido.
    igual(getattr(cadencia, "DURACION_CORTA_S", None), p3_guion.DURACION_CORTA_S,
          "la cadencia y el guion dicen lo mismo de hasta dónde es corto")
    for segundos in (30, 60, 90, 120):
        ficha = cadencia.palabras_para(segundos, "es", "normal", 1.0, 30)
        bloques = ficha["bloques"]
        textos = []
        for i in range(bloques):
            cuantas = ficha["palabras"] // bloques + (1 if i < ficha["palabras"] % bloques else 0)
            texto = " ".join(["palabra"] * cuantas) + "."
            # el gancho cierra con su pausa, y el caso con la suya
            if i in (0, max(1, bloques - 2)) and i < bloques - 1:
                texto += '<break time="900ms"/>'
            textos.append(texto)
        pausas = sum(1 for t in textos if "break" in t)
        habla = ficha["palabras"] / ficha["cadencia_palabras_s"]
        dura = habla + cadencia.aire_de(textos, 1.0)
        comprobar(abs(dura - segundos) < 0.35,
                  f"un corto de {segundos} s con sus {pausas} pausas reales dura "
                  f"{dura:.2f} s")
    # LOS SEGUNDOS DE LA HORQUILLA van con la estructura de lo PEDIDO, no con
    # la de lo que sale: el minimo de un video de 130 s (largo) no puede contar
    # las pausas de un corto por quedarse por debajo de 120 (revision 18-10).
    ficha = cadencia.palabras_para(130, "es", "normal", 1.0, 30)
    minimo = int(ficha["palabras"] * 0.7)
    igual(cadencia.segundos_para(minimo, "es", "normal", 1.0, 30, objetivo_s=130),
          cadencia.segundos_para(minimo, "es", "normal", 1.0, 30, objetivo_s=900),
          "el mínimo de un vídeo de 130 s se cuenta como el de un largo")
    comprobar(cadencia.segundos_para(minimo, "es", "normal", 1.0, 30, objetivo_s=130)
              != cadencia.segundos_para(minimo, "es", "normal", 1.0, 30, objetivo_s=60),
              "y no como el de un corto")
    defecto = p3_guion.PARAMS_POR_DEFECTO
    igual([defecto["pausa_gancho_ms"], defecto["pausa_seccion_ms"]],
          [int(cadencia.PAUSA_DE_BLOQUE_PREVISTA * 1000)] * 2,
          "la pausa prevista es la que pone el guion de serie")


def prueba_proyecto_viejo_sigue_listo(base):
    """LO DE ANTES NO SE QUEDA VIEJO. Cambiar la cuenta no puede dejar obsoleto
    el brief ni el guion de un video ya hecho: el guion se volveria a pedir y
    la voz y las imagenes detras. Las firmas miran los params, no el codigo, y
    el brief no se recalcula solo; esto lo comprueba con un proyecto completo
    hecho con la cuenta de antes."""
    print("\n[7] un proyecto hecho con la cuenta de antes sigue listo")
    import cadencia                                           # noqa: PLC0415
    proyecto = Proyecto.crear(base, "Hecho Antes")
    estado = Estado(proyecto)
    fabricar_ingesta(proyecto, estado)
    nueva = cadencia._aire_previsto

    def vieja(_segundos, bloques, hueco, _corto=None):
        return max(0.0, hueco - cadencia.PAUSA_ENTRE_BLOQUES) * max(0, int(bloques) - 1)
    params = {"instrucciones": "igual", "idioma_salida": "es", "duracion_objetivo_s": 240}
    estado.set_params("brief", params)
    cadencia._aire_previsto = vieja
    try:
        salidas = p2_brief.ejecutar(proyecto, params, sin_progreso)
    finally:
        cadencia._aire_previsto = nueva
    estado.completar("brief", salidas)
    estado.set_params("guion", {"prompt_general": "seco"})
    trabajo = comun.preparar_trabajo(proyecto, "guion")
    comun.escribir_json(os.path.join(trabajo, "guion.json"), {"guion": [
        {"id": "B001", "texto": 'Hola.<break time="900ms"/>'}, {"id": "B002", "texto": "Adios."}]})
    estado.completar("guion", {"resumen": "guion de antes"})
    estado.set_params("voz", {"velocidad": "normal"})
    estado.completar("voz", {"resumen": "voz de antes"})

    otra = Estado(Proyecto(proyecto.raiz))           # como al abrirlo despues
    for paso in ("ingesta", "brief", "guion", "voz"):
        igual(otra.estado_de(paso), "listo", f"{paso} sigue listo con la cuenta nueva")
        comprobar(otra.al_dia(paso), f"y «Generar lo pendiente» no rehace {paso}")
    guardado = comun.leer_salida(proyecto, "brief", "brief.json")["presupuesto_palabras"]
    ahora = p2_brief.presupuesto_de(240, "es", "normal", 1.0, 30)
    comprobar(ahora < guardado,
              f"aunque la cuenta de ahora da menos palabras ({ahora} frente a las "
              f"{guardado} guardadas): solo cambia lo que se genere a partir de ahora")


def principal():
    base = tempfile.mkdtemp(prefix="prueba_p2_")
    # el historico de tiempos de verdad no se toca: aqui los pasos corren
    # con el CLI sustituido por un doble y sus centesimas no miden nada
    os.environ["ESTUDIO_ESTADISTICAS"] = os.path.join(base, "estadisticas.json")
    conservar = "--conservar" in sys.argv
    try:
        prueba_idiomas()
        prueba_params()
        prueba_sin_ingesta(base)
        prueba_con_ingesta(base)
        prueba_pausas_en_la_horquilla()
        prueba_proyecto_viejo_sigue_listo(base)
    finally:
        if conservar:
            print(f"\nproyectos temporales conservados en {base}")
        else:
            shutil.rmtree(base, ignore_errors=True)

    print()
    if FALLOS:
        print(f"FALLARON {len(FALLOS)} comprobaciones:")
        for texto in FALLOS:
            print(f"  - {texto}")
        return 1
    print("P2 BRIEF OK: todas las comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(principal())

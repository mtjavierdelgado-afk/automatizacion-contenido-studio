"""Rama piloto-al-dia: los estados de las líneas casan con los del espacio.

La prueba real del 12-11-2026 (Y05, «un espacio que cambia» en modo «guion»):
las líneas «Visual:» de la Parrilla traían estado «frio» y «calido», y los
ESTADOS DEL ESPACIO se llamaban «blanco_frio» y «blanco_calido». Sin casar, los
planos 1 y 3 editaron la base sin ningún cambio, salieron iguales y el guardián
`_planos_repetidos` tumbó la tanda (ya pagada).

Lo que se comprueba, sin pagar nada y sin llamar a Claude:

  1] `casar_estado`: igual tras normalizar, o el ÚNICO que contiene las palabras;
     con dos candidatos no se adivina;
  2] EL FALLO, reproducido: sin las etiquetas del espacio (como antes), «frio»
     edita la base sin cambio;
  3] EL ARREGLO, en el plan de verdad (`P6.planificar`): «frio» edita la imagen
     de «blanco_frio» y lleva su cambio; «antes» es la base; un estado que no es
     ninguno queda apuntado en el plan y `planos_sin_estado` lo para ANTES de
     pagar;
  4] lo de antes no se mueve: una línea que ya casaba da EL MISMO prompt.

    python pasos/prueba_piloto_al_dia.py
"""
import copy
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))
os.environ.setdefault("ESTUDIO_SIMULAR", "1")

from nucleo.estado import Estado  # noqa: E402
from nucleo.proyecto import Proyecto  # noqa: E402

import guion_visual as G  # noqa: E402
import medios  # noqa: E402
import p6_assets as P6  # noqa: E402

_fallos = []
_cuenta = [0]


def ok(condicion, texto):
    _cuenta[0] += 1
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        _fallos.append(texto)


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def seccion(titulo):
    print(f"\n[{titulo}]")


FRIO = "the ceiling light now gives a cold white light"
CALIDO = "the ceiling light now gives a warm white light"
ESTADOS = {"antes": "", "blanco_frio": FRIO, "blanco_calido": CALIDO}


def prueba_casar():
    seccion("1] casar el nombre de un estado")
    todos = list(ESTADOS)
    igual(G.casar_estado("blanco_frio", todos), "blanco_frio", "igual: el mismo")
    igual(G.casar_estado("Blanco Frío", todos), "blanco_frio", "sin mayúsculas, tildes ni espacios")
    igual(G.casar_estado("frio", todos), "blanco_frio", "«frio»: el único que lo contiene (Y05)")
    igual(G.casar_estado("calido", todos), "blanco_calido", "«calido» → «blanco_calido»")
    igual(G.casar_estado("blanco", todos), "", "«blanco» casa con dos: no se adivina")
    igual(G.casar_estado("rojo", todos), "", "uno que no es ninguno: nada")
    igual(G.casar_estado("luz_blanco_frio_techo", todos), "blanco_frio", "uno más largo que contiene a uno solo")
    igual(G.casar_estado("antes", ["antes", "antes_de_pintar"]), "antes", "el exacto manda sobre el que lo contiene")
    for linea, espacio in (("muebles", ["antes", "sin_muebles"]), ("sin_muebles", ["antes", "muebles"]),
                           ("luz", ["sin_luz"]), ("no_blanco", ["blanco"]), ("pintar", ["antes_de_pintar"])):
        igual(G.casar_estado(linea, espacio), "", f"«{linea}» NO casa con {espacio} (lo que sobra cambia el sentido)")
    for linea, espacio, casa in (("despues", ["antes", "despues_de_pintar"], "despues_de_pintar"),
                                 ("muebles", ["con_muebles"], "con_muebles"),
                                 ("muebles", ["quitar_muebles"], ""), ("luz", ["luz_apagada"], ""),
                                 ("terminado", ["casi_terminado"], "")):
        igual(G.casar_estado(linea, espacio), casa, f"«{linea}» con {espacio}: {casa or 'no casa'}")
    for linea, espacio in (("en_obra", ["obra_terminada"]), ("muebles", ["muebles_retirados"]),
                           ("luces", ["luces_apagadas"]), ("pintado", ["pintado_a_medias"]),
                           ("limpio", ["nada_limpio"]), ("muebles", ["muebles_fuera"])):
        igual(G.casar_estado(linea, espacio), "", f"«{linea}» NO casa con {espacio}")
    for base, espacio in (("sin_cambios", ["antes", "sin_muebles"]), ("la_imagen_base", ["base_pintada", "imagen_final"]),
                          ("igual_que_la_base", ["igual_pero_rojo"])):
        igual(G.estados_sin_casar([{"id": "V001", "estado": base}], espacio), [],
              f"«{base}» sigue siendo la base aunque el espacio tenga {espacio}")
    igual(G.estados_sin_casar([{"id": "V001", "estado": "vacia"}], ["antes", "vacia_sin_muebles"]),
          [{"plano": "V001", "estado": "vacia", "opciones": ["antes", "vacia_sin_muebles"]}],
          "«vacia» con un estado «vacia_sin_muebles» no se da por la base: se para y se pregunta")
    for base in ("la_base", "sin_cambios", "tal_cual", "la_imagen_base", "igual_que_la_base"):
        etiqueta = G._etiqueta(base)                                   # noqa: SLF001  (como llega de la Parrilla)
        igual(G.estados_sin_casar([{"id": "V001", "estado": etiqueta}], todos), [],
              f"«{etiqueta}» es la base, no un estado desconocido (no detiene el vídeo)")
    igual(G.estados_casados([{"id": "V001", "estado": "frio"}, {"id": "V002", "estado": "blanco_calido"},
                             {"id": "V003", "estado": "rojo"}], todos),
          [{"plano": "V001", "estado": "frio", "casa_con": "blanco_frio"}],
          "las casaciones no exactas se enseñan antes de pagar («frio» → «blanco_frio»)")
    igual(G.estado_de_linea({"estado": "frio"}, {"blanco_frio": FRIO}, todos),
          {"cambio": FRIO, "estado": "blanco_frio"}, "la línea «frio» lleva el cambio de «blanco_frio»")
    igual(G.estado_de_linea({"estado": "antes"}, {"blanco_frio": FRIO}, todos), {"cambio": "", "estado": ""},
          "«antes» (sin cambio) es la base")
    igual(G.estado_de_linea({"estado": "antes"}, {"antes_de_pintar": FRIO}, ["antes", "antes_de_pintar"]),
          {"cambio": "", "estado": ""}, "y no se confunde con «antes_de_pintar» si «antes» es un estado propio")
    igual(G.estados_sin_casar([{"id": "V001", "estado": "frio"}, {"id": "V002", "estado": "rojo"},
                               {"id": "V003", "estado": ""}, {"id": "V004", "estado": "la base"}], todos),
          [{"plano": "V002", "estado": "rojo", "opciones": sorted(todos)}],
          "solo «rojo» no casa (vacío y «la base» son la base)")
    igual(G.estados_sin_casar([{"id": "V002", "estado": "rojo"}], []), [],
          "sin saber las etiquetas del espacio no se avisa (no hay con qué comparar)")


BLOQUES = [("B001", "La lámpara del baño da una luz fría y blanca que despierta."),
           ("B002", "Así se ve el baño antes de cambiar nada."),
           ("B003", "Con la luz cálida el baño parece otro, más acogedor."),
           ("B004", "Y con un color que no existe, ¿qué pasaría?")]


def _locucion():
    paso, reloj, bloques, sueltas = 1 / 2.4, 0.0, [], []
    for bid, texto in BLOQUES:
        inicio = reloj
        for cruda in texto.split():
            sueltas.append({"w": cruda, "s": round(reloj, 3), "e": round(reloj + paso * 0.85, 3)})
            reloj += paso
        bloques.append({"id": bid, "texto": texto, "narracion": texto, "t_in": round(inicio, 3),
                        "t_out": round(reloj - paso * 0.15, 3), "palabras": len(texto.split())})
        reloj += 1.0
    total = round(reloj - 1.0, 3)
    return {"bloques": bloques, "palabras": sueltas, "duracion": total,
            "transcript": " ".join(t for _b, t in BLOQUES),
            "secciones": [{"id": "SB001", "bloques": [b for b, _t in BLOQUES], "t_in": 0.0, "t_out": total}]}, total


def _proyecto(carpeta):
    proyecto = Proyecto.crear(carpeta, "Prueba piloto-al-dia")
    estado = Estado(proyecto)
    for paso in ("ingesta", "brief"):
        medios.escribir_json(os.path.join(proyecto.ruta_trabajo(paso), f"{paso}.json"), {})
        estado.set_params(paso, {"texto": "letra"} if paso == "ingesta" else {})
        estado.completar(paso, {})
    medios.escribir_json(os.path.join(proyecto.ruta_trabajo("guion"), "guion.json"),
                         {"guion": [{"id": b, "texto": t} for b, t in BLOQUES]})
    estado.set_params("guion", {"idioma": "es"})
    estado.completar("guion", {"guion": "guion.json"})
    meta, segundos = _locucion()
    medios.escribir_json(os.path.join(proyecto.ruta_trabajo("voz"), "audio_meta.json"), meta)
    estado.set_params("voz", {"voz": "prueba"})
    estado.completar("voz", {"meta": "audio_meta.json", "duracion": segundos})
    return proyecto


LINEAS = [{"id": "V001", "bloque": "B001", "visual": "The bathroom under the ceiling light, no people", "estado": "frio",
           "camara": "wide shot from the door"},
          {"id": "V002", "bloque": "B002", "visual": "The bathroom as it is, no people", "estado": "antes",
           "camara": "wide shot from the door"},
          {"id": "V003", "bloque": "B003", "visual": "The bathroom under the ceiling light, no people", "estado": "calido",
           "camara": "wide shot from the door"},
          {"id": "V004", "bloque": "B004", "visual": "The bathroom with a strange light, no people", "estado": "rojo",
           "camara": "wide shot from the door"}]

CATALOGO = {"sets": {"bano": {"descripcion": "a small white bathroom with a mirror and a ceiling lamp",
                              "luz": "soft daylight", "palabras": ["baño"], "rotulo": ""}},
            "reparto": {},
            "beats": [{"desde": "B001", "hasta": "B004", "set": "bano", "personajes": [], "tono": "neutro",
                       "accion": "the bathroom", "palabras": []}]}


def _params(lineas, estados=ESTADOS):
    return {"calidad": "low", "min_s": 2.0, "max_s": 6.0, "semilla": 7, "imagenes": "guion",
            "tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"},
            "guion_visual": {"origen": "manual", "aprobado": True, "planos": copy.deepcopy(lineas),
                             "estados": dict(estados)},
            "catalogo": copy.deepcopy(CATALOGO),
            "estilo": {"prompt": "flat vector illustration", "referencias": []}}


def prueba_el_plan(proyecto):
    seccion("2] EL FALLO: sin las etiquetas del espacio, «frio» no casa")
    igual(G.estado_de_linea({"estado": "frio"}, {"blanco_frio": FRIO, "blanco_calido": CALIDO}),
          {"cambio": "", "estado": ""}, "como antes: la línea «frio» edita la base sin cambio (Y05)")

    seccion("3] EL ARREGLO, en el plan de verdad")
    plan = P6.planificar(proyecto, _params(LINEAS))
    planos = [e for e in plan["escenas"] if e.get("prompt")]
    igual(len(planos), 4, "un plano por línea")
    por_bloque = {}
    for e in planos:
        por_bloque.setdefault((e.get("linea_gv") or {}).get("bloque"), e)
    frio, antes, calido, rojo = (por_bloque.get(b) for b in ("B001", "B002", "B003", "B004"))
    ok(frio and frio.get("editar_base") and frio.get("base_clave") == "bano#blanco_frio",
       f"«frio» edita la imagen del estado «blanco_frio» ({frio and frio.get('base_clave')})")
    ok(calido and calido.get("editar_base") and calido.get("base_clave") == "bano#blanco_calido",
       "«calido» edita la de «blanco_calido»")
    ok(antes and antes.get("editar_base") and not antes.get("base_clave"), "«antes» edita la base tal cual")
    ok(frio and calido and antes and len({frio.get("base_clave"), calido.get("base_clave"), antes.get("base_clave")}) == 3,
       "frío, cálido y «antes» editan tres imágenes distintas (ya no salen iguales)")
    sueltos = plan.get("estados_sin_casar") or []
    ok(len(sueltos) == 1 and sueltos[0]["estado"] == "rojo" and rojo and sueltos[0]["plano"] == rojo["id"],
       f"el plano de «rojo» queda apuntado en el plan ({sueltos})")
    dirs = {"escenas": os.path.join(proyecto.raiz, "no_hay_nada")}
    para = P6.planos_sin_estado(plan, dirs)
    ok(len(para) == 1 and "blanco_frio" in para[0]["opciones"], "y `planos_sin_estado` lo para antes de pagar")
    igual(P6.planos_sin_estado(plan, dirs, unidades=[f"escena:{frio['id']}"]), [],
          "rehacer solo otro plano no se bloquea por él")

    seccion("3b] la tanda se para ANTES de pagar")
    from PIL import Image                                             # noqa: PLC0415
    ref = os.path.join(proyecto.raiz, "estilo.png")
    Image.new("RGB", (64, 64), (200, 120, 40)).save(ref)
    con_estilo = _params(LINEAS)
    con_estilo["estilo"]["referencias"] = [ref]
    try:
        P6.ejecutar(proyecto, con_estilo)
        ok(False, "con «rojo» la tanda se tenía que parar")
    except RuntimeError as fallo:
        texto = str(fallo)
        ok("no es ninguno de los del espacio" in texto and "«rojo»" in texto and "V004" in texto and "blanco_frio" in texto,
           f"se para antes de pagar, nombra el plano con su línea y dice los estados que valen ({texto[:160]})")

    seccion("4] lo de antes no se mueve")
    exactas = [dict(x, estado={"frio": "blanco_frio", "calido": "blanco_calido", "rojo": ""}.get(x["estado"], x["estado"]))
               for x in LINEAS]
    plan_exacto = P6.planificar(proyecto, _params(exactas))
    p_exacto = {(e.get("linea_gv") or {}).get("bloque"): e["prompt"] for e in plan_exacto["escenas"] if e.get("prompt")}
    igual(p_exacto.get("B001"), frio["prompt"], "«frio» da EL MISMO prompt que «blanco_frio» escrito entero")
    ok("estados_sin_casar" not in plan_exacto, "con todos los estados bien escritos, el plan no lleva la clave nueva (regla 1)")
    sin_estados = P6.planificar(proyecto, _params(LINEAS, estados={}))
    ok("estados_sin_casar" not in sin_estados, "sin estados en el espacio, nada que avisar")


def _catalogo_y05():
    """Como Y05 en el servidor (12-11): sin ESTADOS DEL ESPACIO de la Parrilla
    (`guion_visual.estados` vacio); los estados salen de los tramos del catalogo."""
    cat = copy.deepcopy(CATALOGO)
    base = {"set": "bano", "personajes": [], "tono": "neutro", "accion": "the bathroom", "palabras": []}
    cat["beats"] = [dict(base, desde="B001", hasta="B001", estado="blanco_frio", cambio=FRIO),
                    dict(base, desde="B002", hasta="B002", estado="antes"),
                    dict(base, desde="B003", hasta="B004", estado="blanco_calido", cambio=CALIDO)]
    return cat


def _params_y05(lineas):
    params = _params(lineas, estados={})
    params["catalogo"] = _catalogo_y05()
    return params


def prueba_y05(proyecto):
    seccion("6] Y05 de verdad: sin estados de la Parrilla, los del catálogo (prueba del 12-11)")
    igual(P6.etiquetas_del_espacio(_catalogo_y05(), "bano"), ["blanco_frio", "antes", "blanco_calido"],
          "las etiquetas salen de los tramos: las que cambian y «antes»")
    igual(P6.etiquetas_del_espacio(_catalogo_y05(), "otro_sitio"), [], "solo las del sitio del vídeo")
    con_fijos = dict(_catalogo_y05(), estados_fijos={"blanco_frio": FRIO, "sin_nada": ""})
    igual(P6.etiquetas_del_espacio(con_fijos, "bano"), ["blanco_frio", "sin_nada"],
          "con los estados de la Parrilla mandan esos (como antes)")
    plan = P6.planificar(proyecto, _params_y05(LINEAS))
    por_bloque = {}
    for e in plan["escenas"]:
        if e.get("prompt"):
            por_bloque.setdefault((e.get("linea_gv") or {}).get("bloque"), e)
    frio, antes, calido = (por_bloque.get(b) for b in ("B001", "B002", "B003"))
    ok(frio and frio.get("base_clave") == "bano#blanco_frio",
       f"«frio» casa con «blanco_frio» también sin la Parrilla ({frio and frio.get('base_clave')})")
    ok(calido and calido.get("base_clave") == "bano#blanco_calido", "«calido» con «blanco_calido»")
    ok(antes and not antes.get("base_clave"), "«antes» sigue siendo la base")
    sueltos = plan.get("estados_sin_casar") or []
    ok(len(sueltos) == 1 and sueltos[0]["estado"] == "rojo", f"«rojo» queda apuntado ({sueltos})")
    from PIL import Image                                             # noqa: PLC0415
    ref = os.path.join(proyecto.raiz, "estilo.png")
    Image.new("RGB", (64, 64), (200, 120, 40)).save(ref)
    con_estilo = _params_y05(LINEAS)
    con_estilo["estilo"]["referencias"] = [ref]
    try:
        P6.ejecutar(proyecto, con_estilo)
        ok(False, "con «rojo» la tanda de Y05 se tenía que parar")
    except RuntimeError as fallo:
        ok("no es ninguno de los del espacio" in str(fallo) and "«rojo»" in str(fallo),
           f"y la tanda se para ANTES de pagar ({str(fallo)[:120]})")
    exactas = [dict(x, estado={"frio": "blanco_frio", "calido": "blanco_calido", "rojo": ""}.get(x["estado"], x["estado"]))
               for x in LINEAS]
    plan_exacto = P6.planificar(proyecto, _params_y05(exactas))
    p_exacto = {(e.get("linea_gv") or {}).get("bloque"): e["prompt"] for e in plan_exacto["escenas"] if e.get("prompt")}
    igual(p_exacto.get("B001"), frio and frio["prompt"], "«frio» da el mismo prompt que «blanco_frio» entero")
    ok("estados_sin_casar" not in plan_exacto, "bien escritos, el plan no lleva la clave nueva (regla 1)")


def prueba_el_aviso_y05(proyecto, carpeta):
    seccion("6b] Y05: el guion visual lo enseña (nota y aviso) y el piloto se detiene")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    if servidor.PASOS_MODULOS is None:
        print(f"  (omitida: los pasos no cargan aquí: {servidor.ERROR_PASOS[:80]})")
        return
    servidor.fijar_raiz_proyectos(carpeta)
    ctx = servidor.contexto(proyecto.id)
    ctx.estado.set_params("assets", _params_y05(LINEAS))
    ficha = servidor._ficha_guion_visual(ctx)
    ok(any(c.get("estado") == "frio" and c.get("casa_con") == "blanco_frio" for c in ficha.get("estados_casados") or []),
       f"la nota «frio» → «blanco_frio» sale ({ficha.get('estados_casados')})")
    ok(any(c.get("estado") == "rojo" for c in ficha.get("estados_sin_casar") or []),
       f"y el aviso de «rojo» ({ficha.get('estados_sin_casar')})")
    avisos = servidor._impedimentos(ctx, "video", [{"id": "assets"}])
    ok(any(a.get("donde") == "Guion visual" and "«rojo»" in a.get("que", "") for a in avisos),
       "el piloto se detiene en «Guion visual» antes de lanzar")


def prueba_revision_y05(proyecto, carpeta):
    seccion("6c] revisión del 12-11: la base sin tramo propio, otros sitios y etiquetas sacadas")
    base = {"set": "bano", "personajes": [], "tono": "neutro", "accion": "the bathroom", "palabras": []}
    # todos los tramos con cambio: ninguno se llama «antes»
    solo_cambios = copy.deepcopy(CATALOGO)
    solo_cambios["beats"] = [dict(base, desde="B001", hasta="B002", estado="blanco_frio", cambio=FRIO),
                             dict(base, desde="B003", hasta="B004", estado="blanco_calido", cambio=CALIDO)]
    params = _params(LINEAS, estados={})
    params["catalogo"] = solo_cambios
    plan = P6.planificar(proyecto, params)
    sueltos = [x["estado"] for x in plan.get("estados_sin_casar") or []]
    igual(sueltos, ["rojo"], "«antes» es la base aunque ningún tramo se llame así; solo «rojo» para")
    igual(G.estados_sin_casar([{"id": "V1", "estado": "inicial"}, {"id": "V2", "estado": "original"}],
                              ["blanco_frio", "blanco_calido"]), [], "«inicial» y «original» también son la base")
    igual([x["casa_con"] for x in G.estados_casados([{"id": "V1", "estado": "antes"}], ["antes_de_pintar", "pintado"])],
          ["antes_de_pintar"], "pero si es la parte de un estado del espacio («antes_de_pintar»), casa con él y se enseña")
    # otro sitio con su propio estado
    con_tienda = copy.deepcopy(solo_cambios)
    con_tienda["sets"]["tienda"] = {"descripcion": "a small shop", "luz": "warm", "palabras": ["tienda"], "rotulo": ""}
    con_tienda["beats"].append({"set": "tienda", "desde": "B004", "hasta": "B004", "estado": "abierta",
                                "cambio": "the shop door open", "personajes": [], "accion": "the shop", "palabras": []})
    igual(P6.etiquetas_ajenas(con_tienda, "bano"), ["abierta"], "las etiquetas de otro sitio se saben aparte")
    lineas = [dict(x, estado="abierta") if x["id"] == "V004" else x for x in LINEAS]
    params = _params(lineas, estados={})
    params["catalogo"] = con_tienda
    igual(P6.planificar(proyecto, params).get("estados_sin_casar"), None,
          "una línea con el estado de otro sitio («abierta» de la tienda) no para la tanda")
    # un tramo con cambio y sin nombre: su etiqueta sacada no se ofrece
    sin_nombre = copy.deepcopy(solo_cambios)
    sin_nombre["beats"][1].pop("estado")
    params = _params(LINEAS, estados={})
    params["catalogo"] = sin_nombre
    plan = P6.planificar(proyecto, params)
    rojo = [x for x in plan.get("estados_sin_casar") or [] if x["estado"] == "rojo"]
    ok(rojo and rojo[0]["opciones"] == ["blanco_frio"],
       f"las opciones no enseñan la etiqueta sacada del cambio («c…»), que nadie puede escribir ({rojo})")
    # todos los tramos SIN cambio: la ficha avisa igual que para `planificar`
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida la parte del servidor: falta {fallo.name})")
        return
    if servidor.PASOS_MODULOS is None:
        return
    servidor.fijar_raiz_proyectos(carpeta)
    ctx = servidor.contexto(proyecto.id)
    sin_cambios = copy.deepcopy(CATALOGO)
    sin_cambios["beats"] = [dict(base, desde="B001", hasta="B004", estado="antes")]
    params = _params(LINEAS, estados={})
    params["catalogo"] = sin_cambios
    plan = P6.planificar(proyecto, params)
    ok(any(x["estado"] == "frio" for x in plan.get("estados_sin_casar") or []),
       "sin ningún estado con cambio, «frio» para la tanda…")
    ctx.estado.set_params("assets", params)
    ficha = servidor._ficha_guion_visual(ctx)
    ok(any(x["estado"] == "frio" for x in ficha.get("estados_sin_casar") or []),
       f"…y el guion visual lo avisa antes (antes callaba) ({ficha.get('estados_sin_casar')})")


def prueba_el_aviso(proyecto, carpeta):
    seccion("5] el aviso de antes de lanzar (el piloto se DETIENE en «Guion visual»)")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return
    if servidor.PASOS_MODULOS is None:
        print(f"  (omitida: los pasos no cargan aquí: {servidor.ERROR_PASOS[:80]})")
        return
    servidor.fijar_raiz_proyectos(carpeta)
    ctx = servidor.contexto(proyecto.id)
    ctx.estado.set_params("assets", _params(LINEAS))
    avisos = servidor._impedimentos(ctx, "video", [{"id": "assets"}])
    ok(any(a.get("donde") == "Guion visual" and "«rojo»" in a.get("que", "") for a in avisos),
       f"con una línea «rojo», se avisa antes de lanzar y dice dónde se arregla ({avisos})")
    # el plano de «rojo» ya dibujado (con el plan guardado): no se paga, no bloquea
    import medios as M                                            # noqa: PLC0415
    plan = P6.plan_actual(ctx.proyecto, "assets", estado=ctx.estado)
    rojo = next(e for e in plan["escenas"] if (e.get("linea_gv") or {}).get("id") == "V004")
    escenas = os.path.join(ctx.proyecto.ruta_trabajo("assets"), "escenas")
    os.makedirs(escenas, exist_ok=True)
    png = os.path.join(escenas, f"{rojo['id']}.png")
    from PIL import Image                                         # noqa: PLC0415
    Image.new("RGB", (8, 8)).save(png)
    avisos = servidor._impedimentos(ctx, "video", [{"id": "assets"}])
    ok(not any("no es ninguno" in a.get("que", "") for a in avisos), "con su plano ya dibujado, no bloquea (p6 tampoco lo paga)")
    os.remove(png)
    del M
    ctx.estado.set_params("assets", _params([dict(x, estado="blanco_frio") if x["estado"] == "rojo" else x for x in LINEAS]))
    avisos = servidor._impedimentos(ctx, "video", [{"id": "assets"}])
    ok(not any("no es ninguno" in a.get("que", "") for a in avisos), "con los estados bien, nada que avisar por eso")


def main():
    carpeta = tempfile.mkdtemp(prefix="piloto_al_dia_")
    try:
        prueba_casar()
        proyecto = _proyecto(os.path.join(carpeta, "video"))
        prueba_el_plan(proyecto)
        prueba_el_aviso(proyecto, os.path.join(carpeta, "video"))
        prueba_y05(proyecto)
        prueba_el_aviso_y05(proyecto, os.path.join(carpeta, "video"))
        prueba_revision_y05(proyecto, os.path.join(carpeta, "video"))
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
    print()
    if _fallos:
        print(f"PILOTO AL DIA: FALLAN {len(_fallos)} de {_cuenta[0]} comprobaciones")
        for texto in _fallos:
            print(f"  - {texto}")
        return 1
    print(f"PILOTO AL DIA OK: {_cuenta[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

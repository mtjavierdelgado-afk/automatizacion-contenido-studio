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


LINEAS = [{"bloque": "B001", "visual": "The bathroom under the ceiling light, no people", "estado": "frio",
           "camara": "wide shot from the door"},
          {"bloque": "B002", "visual": "The bathroom as it is, no people", "estado": "antes",
           "camara": "wide shot from the door"},
          {"bloque": "B003", "visual": "The bathroom under the ceiling light, no people", "estado": "calido",
           "camara": "wide shot from the door"},
          {"bloque": "B004", "visual": "The bathroom with a strange light, no people", "estado": "rojo",
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

    seccion("4] lo de antes no se mueve")
    exactas = [dict(x, estado={"frio": "blanco_frio", "calido": "blanco_calido", "rojo": ""}.get(x["estado"], x["estado"]))
               for x in LINEAS]
    plan_exacto = P6.planificar(proyecto, _params(exactas))
    p_exacto = {(e.get("linea_gv") or {}).get("bloque"): e["prompt"] for e in plan_exacto["escenas"] if e.get("prompt")}
    igual(p_exacto.get("B001"), frio["prompt"], "«frio» da EL MISMO prompt que «blanco_frio» escrito entero")
    ok("estados_sin_casar" not in plan_exacto, "con todos los estados bien escritos, el plan no lleva la clave nueva (regla 1)")
    sin_estados = P6.planificar(proyecto, _params(LINEAS, estados={}))
    ok("estados_sin_casar" not in sin_estados, "sin estados en el espacio, nada que avisar")


def main():
    carpeta = tempfile.mkdtemp(prefix="piloto_al_dia_")
    try:
        prueba_casar()
        prueba_el_plan(_proyecto(os.path.join(carpeta, "video")))
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

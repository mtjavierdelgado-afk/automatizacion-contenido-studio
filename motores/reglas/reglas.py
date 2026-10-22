"""
Base de reglas transversales aprendidas del feedback humano.

Cada vez que una revision detecta un fallo, el fallo se destila en una regla
abierta y se guarda aqui. Las reglas NO pertenecen al video en el que se
descubrieron: se aplican a todos los proyectos futuros.

Uso desde un motor:

    import reglas
    lineas = reglas.para("prompt_imagen")        # texto listo para inyectar
    reglas.anadir(id="...", ambito="...", regla="...", por_que="...", origen={...})

Uso desde consola:

    python reglas.py listar [--ambito prompt_imagen]
    python reglas.py destilar --feedback feedback_gate1.json --proyecto mi_video
"""
import argparse
import json
import os
import re
from datetime import date

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reglas.json")

#: LAS REGLAS DEL MODO FOTO, en su propio fichero (Etapa Foto A).
#:
#: Las de `reglas.json` se escribieron --y el destilador las sigue aprendiendo--
#: para video cartoon, asi que en un video fotografico (`estilo.modo == "foto"`)
#: no entra ninguna: entran estas. Y van APARTE a proposito: `asvs actualizar`
#: no sobrescribe `reglas.json` en el servidor (es lo unico del arbol de codigo
#: que la aplicacion reescribe), asi que una regla de foto escrita alli no
#: llegaria nunca. Este fichero viaja con el codigo como cualquier otro.
RUTA_FOTO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "reglas_foto.json")

AMBITOS = ("prompt_imagen", "referencias", "reparto", "blockout",
           "plan_escenas", "storyboard", "montaje", "voz")


def cargar(modo="ilustracion"):
    """Las reglas de ese modo de imagen. Todo lo que no sea "foto" es cartoon."""
    ruta = RUTA_FOTO if modo == "foto" else RUTA
    with open(ruta, "r", encoding="utf-8") as fh:
        return json.load(fh)


def guardar(datos):
    with open(RUTA, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2)


def aplica(regla, contexto=None):
    """Si una regla entra con ese contexto. -> bool

    Las de siempre (sin `solo_si`) entran siempre. Las que llevan `solo_si` son
    de UN TIPO de video --las de consolas del modo foto, por ejemplo-- y solo
    entran cuando el texto de este encargo (el estilo, la escena, la nota del
    revisor) nombra alguna de sus palabras. Sin contexto no entran: es preferible
    que a un video de consolas le falte una regla a que a uno de plantas le
    sobre un televisor.
    """
    patrones = regla.get("solo_si") or []
    if not patrones:
        return True
    texto = str(contexto or "")
    if not texto:
        return False
    return any(re.search(p, texto, flags=re.IGNORECASE) for p in patrones)


def _con_negocio(lista, extra):
    """Las reglas del fichero con las del TIPO DE NEGOCIO metidas en su hueco.

    Etapa Foto C: las reglas de un negocio (las de consolas, por ejemplo) ya no
    viven en `reglas_foto.json` sino en su tipo (`pasos/dominios_fabrica.json`
    y los que crea el dueño), y llegan aqui como `extra`. Entran donde el
    fichero tiene la entrada `{"hueco": "negocio"}` --donde estaban antes--, y
    no al final: el orden de las reglas es el del prompt, y un video de antes
    tiene que sacar el mismo prompt (y la misma firma) que antes. Sin hueco, al
    final. La entrada del hueco no es una regla y no sale nunca.
    """
    extra = list(extra or [])
    salida, puesto = [], False
    for regla in lista:
        if regla.get("hueco"):
            if not puesto:
                salida.extend(extra)
                puesto = True
            continue
        salida.append(regla)
    if not puesto:
        salida.extend(extra)
    return salida


def para(ambito, como_texto=True, modo="ilustracion", contexto=None, extra=None,
         contexto_plano=None):
    """Reglas de un ambito, ordenadas por prioridad.

    `contexto` solo decide las reglas con `solo_si` (ver `aplica`); las demas
    salen igual se pase o no. `extra` son las reglas del tipo de negocio (ver
    `_con_negocio`); sin ellas, las del fichero solas.
    """
    datos = cargar(modo)
    # las de la FICHA DEL NEGOCIO con «solo si el plano habla de…» miran SOLO el
    # plano (su escena y la nota), no la guía del estilo: si la guía nombra la
    # palabra, entrarían en todos los planos (lo vio el dueño con VR y
    # simuladores, 21-10). Sin `contexto_plano`, el de siempre.
    filtradas = [r for r in _con_negocio(datos["reglas"], extra)
                 if r.get("ambito") == ambito
                 and aplica(r, contexto_plano if (r.get("solo_en_plano")
                                                  and contexto_plano is not None)
                            else contexto)]
    filtradas.sort(key=lambda r: r.get("prioridad", 9))
    if not como_texto:
        return filtradas
    return [r["regla"] for r in filtradas]


def bloque_prompt(ambito="prompt_imagen", modo="ilustracion", contexto=None,
                  extra=None, contexto_plano=None):
    """Devuelve las reglas como un parrafo listo para concatenar a un prompt.

    Con `modo="foto"` salen las de `reglas_foto.json` y ninguna de las de
    cartoon; sin decirlo, las de siempre, igual que antes. `contexto` es el
    texto del encargo con el que se deciden las reglas con `solo_si`, y `extra`
    las del tipo de negocio del video (`dominios.reglas_de_foto`).
    """
    lineas = para(ambito, modo=modo, contexto=contexto, extra=extra,
                  contexto_plano=contexto_plano)
    if not lineas:
        return ""
    return " ".join(lineas)


def anadir(*, id, ambito, regla, por_que="", origen=None, prioridad=1):
    if ambito not in AMBITOS:
        raise ValueError(f"ambito desconocido: {ambito} (validos: {AMBITOS})")
    datos = cargar()
    existentes = {r["id"] for r in datos["reglas"]}
    if id in existentes:
        # Se actualiza en lugar de duplicar: la misma leccion puede reaparecer
        # en varios proyectos y lo util es acumular origenes, no repetir reglas.
        for r in datos["reglas"]:
            if r["id"] == id:
                r["regla"] = regla
                r.setdefault("origenes_extra", []).append(origen or {})
                break
    else:
        datos["reglas"].append({
            "id": id, "ambito": ambito, "prioridad": prioridad,
            "regla": regla, "por_que": por_que,
            "origen": origen or {}, "fecha": date.today().isoformat(),
        })
    guardar(datos)
    return id


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_listar = sub.add_parser("listar")
    p_listar.add_argument("--ambito", default=None, choices=AMBITOS)

    args = parser.parse_args()

    if args.cmd == "listar":
        datos = cargar()
        reglas = datos["reglas"]
        if args.ambito:
            reglas = [r for r in reglas if r["ambito"] == args.ambito]
        reglas.sort(key=lambda r: (r["ambito"], r.get("prioridad", 9)))
        ambito_actual = None
        for r in reglas:
            if r["ambito"] != ambito_actual:
                ambito_actual = r["ambito"]
                print(f"\n=== {ambito_actual} ===")
            print(f"  [{r['id']}]  {r['regla']}")
            if r.get("origen", {}).get("feedback"):
                print(f"      nacio de: \"{r['origen']['feedback']}\"")
        print(f"\n{len(reglas)} reglas")


if __name__ == "__main__":
    main()

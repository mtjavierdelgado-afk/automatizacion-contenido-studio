"""El guion de un video escrito con DOS modelos, para compararlos a ciegas.

NO TOCA EL PROYECTO. Copia el video a una carpeta aparte (sin imagenes, voz ni
montaje: solo el material, el brief y el guion) y escribe ahi el guion con cada
modelo, con el MISMO material, las MISMAS indicaciones y la misma duracion. El
proyecto de verdad no cambia: ni un param, ni una firma, ni nada obsoleto.

Solo gasta tokens de la suscripcion de Claude (el CLI), ningun dolar.

Para que (18-10-2026, decision del dueno): saber si opus escribe mejores guiones
que sonnet --el defecto del paso, `cli_claude.POR_FASE["guion"]`-- con encargos
reales, antes de cambiar el defecto. Cambiarlo despues es una linea, y en
Configuracion ya se puede elegir el modelo del guion.

A CIEGAS: los dos guiones salen como «A» y «B» en un orden al azar; cual es cual
se guarda aparte y se ensena con --revelar, despues de elegir.

Uso (en el servidor: `asvs comparar-guion ...`, que corre como el usuario del
servicio y con su entorno):

    python herramientas/comparar_guion.py                 # lista los videos
    python herramientas/comparar_guion.py <video> [<video> ...]
    python herramientas/comparar_guion.py --revelar       # cual era cual

`<video>` es el id de la carpeta o un trozo de su nombre. Opciones:
--modelos sonnet,opus   --esfuerzo medium   --salida <carpeta>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import random
import shutil
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for camino in (RAIZ, os.path.join(RAIZ, "pasos")):
    if camino not in sys.path:
        sys.path.insert(0, camino)

#: Lo que NO hace falta para escribir un guion, y pesa: se queda fuera de la copia.
PASOS_QUE_NO_SE_COPIAN = ("voz", "revision_audio", "assets", "callouts", "render")
EXTENSIONES_PESADAS = (".mp4", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp")


def raiz_proyectos():
    return os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")


def carpeta_salida(pedida=None):
    return pedida or os.path.join(raiz_proyectos(), "_sistema", "comparar_guion")


def videos():
    """[(id, nombre, segundos, tiene_material)] de los videos que hay."""
    from nucleo.proyecto import Proyecto                     # noqa: PLC0415
    from nucleo.estado import Estado                         # noqa: PLC0415
    salida = []
    raiz = raiz_proyectos()
    for nombre in sorted(os.listdir(raiz)) if os.path.isdir(raiz) else []:
        ruta = os.path.join(raiz, nombre)
        if nombre.startswith(("_", ".")) or not os.path.isfile(os.path.join(ruta, "proyecto.json")):
            continue
        try:
            proyecto = Proyecto(ruta)
            brief = Estado(proyecto).params("brief") or {}
            hecho = proyecto.version_activa("brief") is not None \
                and proyecto.version_activa("ingesta") is not None
        except Exception:                                     # noqa: BLE001
            continue
        salida.append((proyecto.id, proyecto.config.get("nombre") or proyecto.id,
                       brief.get("duracion_objetivo_s"), hecho))
    return salida


def buscar(pedido):
    """La carpeta del video pedido (id o trozo del nombre). -> ruta | ValueError"""
    raiz = raiz_proyectos()
    directo = os.path.join(raiz, pedido)
    if os.path.isfile(os.path.join(directo, "proyecto.json")):
        return directo
    if os.path.isfile(os.path.join(pedido, "proyecto.json")):
        return os.path.abspath(pedido)
    trozo = pedido.lower()
    encontrados = [v for v in videos() if trozo in v[0].lower() or trozo in str(v[1]).lower()]
    if len(encontrados) == 1:
        return os.path.join(raiz, encontrados[0][0])
    if not encontrados:
        raise ValueError(f"no hay ningun video que se llame «{pedido}»")
    raise ValueError(f"«{pedido}» vale para varios videos: "
                     + ", ".join(f"{v[0]} ({v[1]})" for v in encontrados[:6]))


def copiar(origen, destino):
    """La copia de trabajo: el video sin lo que no hace falta para el guion."""
    def fuera(carpeta, nombres):
        relativa = os.path.relpath(carpeta, origen).replace("\\", "/")
        quitar = set()
        if relativa == "pasos":
            quitar |= {n for n in nombres if n in PASOS_QUE_NO_SE_COPIAN}
        quitar |= {n for n in nombres if n.lower().endswith(EXTENSIONES_PESADAS)}
        return quitar
    shutil.copytree(origen, destino, ignore=fuera)
    return destino


def escribir_con(origen, modelo, esfuerzo, carpeta_tmp, avisar=print):
    """El guion del video `origen` escrito con ese modelo, en una COPIA. -> ficha"""
    import cadencia                                           # noqa: PLC0415
    import p3_guion                                           # noqa: PLC0415
    from nucleo.estado import Estado                         # noqa: PLC0415
    from nucleo.proyecto import Proyecto                     # noqa: PLC0415
    copia = copiar(origen, os.path.join(carpeta_tmp, f"copia_{modelo}"))
    proyecto = Proyecto(copia)
    estado = Estado(proyecto)
    params = dict(estado.params("guion") or {})
    # LO UNICO QUE CAMBIA ES EL MODELO (y el esfuerzo, el mismo para los dos).
    # Desde cero los dos: si no, el guion que ya tiene el video --escrito con
    # uno de los dos-- entraria como base y la comparacion no seria limpia.
    params.update({"modelo": modelo, "regenerar_desde_cero": True})
    if esfuerzo:
        params["esfuerzo"] = esfuerzo
    params.pop("instruccion_vuelta", None)
    arranque = time.time()
    p3_guion.ejecutar(proyecto, params, lambda f, m="": avisar(f"  [{modelo}] {int(f * 100)} % {m}"))
    segundos_tardo = time.time() - arranque
    documento = json.load(open(os.path.join(proyecto.ruta_trabajo("guion", crear=False),
                                            "guion.json"), encoding="utf-8"))
    bloques = [b for b in (documento.get("guion") or []) if str(b.get("texto") or "").strip()]
    brief = estado.params("brief") or {}
    voz = estado.params("voz") or {}
    estimado = cadencia.estimar(bloques, brief.get("idioma_salida") or "es",
                                voz.get("velocidad"), float(voz.get("hueco_minimo") or 0.0))
    return {"modelo": modelo, "esfuerzo": params.get("esfuerzo"),
            "tardo_s": round(segundos_tardo, 1),
            "palabras": estimado["palabras"], "segundos_estimados": estimado["segundos"],
            "pedido_s": brief.get("duracion_objetivo_s"),
            "bloques": [{"id": b.get("id"), "texto": b.get("texto"),
                         "abre_seccion": bool(b.get("abre_seccion"))} for b in bloques]}


def _limpio(texto):
    import marcas_tts                                         # noqa: PLC0415
    try:
        return marcas_tts.limpiar(texto)
    except Exception:                                         # noqa: BLE001
        return str(texto)


def imprimir(letra, ficha):
    print(f"\n========== GUION {letra} ==========")
    print(f"{ficha['palabras']} palabras · unos {ficha['segundos_estimados']:.0f} s "
          f"(pedidos {ficha['pedido_s']} s) · tardó {ficha['tardo_s']:.0f} s")
    for bloque in ficha["bloques"]:
        marca = "§ " if bloque["abre_seccion"] else "  "
        print(f"{marca}{bloque['id']}  {_limpio(bloque['texto'])}")


def comparar(pedidos, modelos, esfuerzo, salida):
    os.makedirs(salida, exist_ok=True)
    # el historico de tiempos, a una copia: estas pasadas no son de un video
    os.environ.setdefault("ESTUDIO_ESTADISTICAS",
                          os.path.join(tempfile.gettempdir(), "comparar_guion_estadisticas.json"))
    sello = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    resultado = {"fecha": sello, "modelos": modelos, "videos": []}
    for pedido in pedidos:
        origen = buscar(pedido)
        print(f"\n### {os.path.basename(origen)}: escribiendo con {' y '.join(modelos)} "
              f"(una tras otra; cada una tarda unos minutos)")
        fichas = []
        with tempfile.TemporaryDirectory(prefix="comparar_guion_") as tmp:
            for modelo in modelos:
                try:
                    fichas.append(escribir_con(origen, modelo, esfuerzo, tmp))
                except Exception as fallo:                    # noqa: BLE001
                    print(f"  [{modelo}] NO SALIO: {fallo}")
        if len(fichas) < 2:
            print("  no hay dos guiones que comparar en este video")
            continue
        orden = list(range(len(fichas)))
        random.shuffle(orden)
        letras = {}
        for letra, indice in zip("AB", orden):
            letras[letra] = fichas[indice]["modelo"]
            imprimir(letra, fichas[indice])
        resultado["videos"].append({"video": os.path.basename(origen),
                                    "letras": letras, "guiones": fichas})
    ruta = os.path.join(salida, f"comparacion_{sello}.json")
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(salida, "ultima.json"), "w", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)
    print(f"\nElige en cada vídeo cuál te gusta más (A o B). Después:  asvs comparar-guion revelar")
    print(f"(guardado en {ruta})")
    return resultado


def revelar(salida):
    ruta = os.path.join(salida, "ultima.json")
    if not os.path.exists(ruta):
        print("todavía no hay ninguna comparación")
        return None
    datos = json.load(open(ruta, encoding="utf-8"))
    for video in datos.get("videos") or []:
        print(f"{video['video']}: " + ", ".join(f"{l} = {m}" for l, m in sorted(video["letras"].items())))
    return datos


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compara el guion de un vídeo escrito con dos modelos")
    ap.add_argument("videos", nargs="*")
    ap.add_argument("--modelos", default="sonnet,opus")
    ap.add_argument("--esfuerzo", default="")
    ap.add_argument("--salida", default="")
    ap.add_argument("--revelar", action="store_true")
    args = ap.parse_args(argv)
    salida = carpeta_salida(args.salida or None)
    if args.revelar or args.videos == ["revelar"]:
        revelar(salida)
        return 0
    if not args.videos:
        print("Vídeos que se pueden comparar (id · nombre · duración):")
        for vid, nombre, segundos, hecho in videos():
            if hecho:
                print(f"  {vid} · {nombre} · {segundos or '?'} s")
        print("\nUso:  asvs comparar-guion <id o trozo del nombre> [otro...]")
        return 0
    modelos = [m.strip() for m in args.modelos.split(",") if m.strip()]
    if len(modelos) != 2:
        print("hacen falta dos modelos, por ejemplo --modelos sonnet,opus")
        return 2
    try:
        comparar(args.videos, modelos, args.esfuerzo or None, salida)
    except ValueError as fallo:
        print(f"no se puede: {fallo}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

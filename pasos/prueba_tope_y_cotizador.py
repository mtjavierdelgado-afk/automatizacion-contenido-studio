"""Prueba de la rama tope-y-cotizador (12-11-2026, lo que dejó el tren con G01 e Y05).

1] «Duplicar» copia las imágenes del espacio fijo (la copia de Y05 nacía sin su base).
2] El cotizador cuenta la imagen base y la de cada estado que faltan (G01: se
   previeron 0,54 $ y costaron 0,93 $).
3] El tope: la parada de antes de dibujar no cuenta la portada (C), el paso 0
   suma lo ya gastado al reintentar (D) y «Seguir» desde el tope salta también
   el interruptor (E).
4] Un plano de OTRO sitio con un estado que no es del espacio no para el vídeo (B).

Cada comprobación falla sin su arreglo.
"""
import copy
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))
CARPETA = tempfile.mkdtemp(prefix="tope_y_cotizador_")
os.environ.setdefault("ESTUDIO_SECRETOS", os.path.join(CARPETA, "secretos"))
os.environ.setdefault("ESTUDIO_AJUSTES", os.path.join(CARPETA, "ajustes.json"))
os.environ.setdefault("ESTUDIO_BITACORA_GLOBAL", os.path.join(CARPETA, "bitacora_global.jsonl"))

import prueba_piloto_al_dia as Y  # noqa: E402
from nucleo.proyecto import Proyecto  # noqa: E402

_cuenta, _fallos = [0], []


def ok(condicion, texto):
    _cuenta[0] += 1
    print(f"  {'ok   ' if condicion else 'FALLO'} {texto}")
    if not condicion:
        _fallos.append(texto)


def seccion(titulo):
    print(f"\n[{titulo}]")


def prueba_duplicar(raiz):
    seccion("1] «Duplicar» copia las imágenes del espacio fijo")
    original = Proyecto.crear(raiz, "Y05 de prueba")
    carpeta = original.ruta("espacio_fijo")
    os.makedirs(os.path.join(carpeta, "_refs"), exist_ok=True)
    for nombre, contenido in (("0123456789abcdef.png", b"base"), ("fedcba9876543210.png", b"estado"),
                              ("_base_nueva.png", b"a medias"), ("x.png.tmp", b"a medias"),
                              (os.path.join("_refs", "ref.png"), b"cache")):
        with open(os.path.join(carpeta, nombre), "wb") as fh:
            fh.write(contenido)
    copia = original.duplicar(raiz, "Y05 copia")
    hay = lambda n: os.path.exists(copia.ruta("espacio_fijo", *n.split("/")))  # noqa: E731
    ok(hay("0123456789abcdef.png") and hay("fedcba9876543210.png"),
       "la base y la imagen del estado viajan con la copia (antes: 404 y una base nueva que pagar)")
    ok(not hay("_base_nueva.png") and not hay("x.png.tmp") and not hay("_refs/ref.png"),
       "lo que se estaba escribiendo y la cache de referencias no viajan")
    sin = Proyecto.crear(raiz, "Sin espacio")
    ok(not os.path.exists(sin.duplicar(raiz, "Sin espacio copia").ruta("espacio_fijo")),
       "un vídeo sin espacio fijo sigue copiándose igual")


def _servidor():
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return None
    return servidor if servidor.PASOS_MODULOS is not None else None


def prueba_cotizador(servidor, carpeta):
    seccion("2] el cotizador cuenta la base y los estados que faltan")
    proyecto = Y._proyecto(os.path.join(carpeta, "video"))
    servidor.fijar_raiz_proyectos(os.path.join(carpeta, "video"))
    ctx = servidor.contexto(proyecto.id)
    exactas = [dict(x, estado={"frio": "blanco_frio", "calido": "blanco_calido", "rojo": ""}.get(x["estado"], x["estado"]))
               for x in Y.LINEAS]
    params = Y._params_y05(exactas)
    ctx.estado.set_params("assets", params)
    n = servidor._imagenes_del_relato_por_pagar(ctx)
    ok(n == 3, f"sin nada hecho: la base y los dos estados (blanco_frio y blanco_calido) = 3 ({n})")
    # la base hecha y el estado frío hecho con su cambio de ahora (con su fichero)
    for nombre in ("0123456789abcdef.png", "fedcba9876543210.png"):
        os.makedirs(proyecto.ruta("espacio_fijo"), exist_ok=True)
        with open(proyecto.ruta("espacio_fijo", nombre), "wb") as fh:
            fh.write(b"png")
    hechos = dict(params)
    hechos["tipo_relato"] = dict(params["tipo_relato"], bases={"bano": {
        "imagen": "espacio_fijo/0123456789abcdef.png", "aprobada": True,
        "estados": {"blanco_frio": {"imagen": "espacio_fijo/fedcba9876543210.png", "cambio": Y.FRIO,
                                    "aprobada": True}}}})
    ctx.estado.set_params("assets", hechos)
    n = servidor._imagenes_del_relato_por_pagar(ctx)
    ok(n == 1, f"con la base y «blanco_frio» hechos, solo falta «blanco_calido» ({n})")
    os.remove(proyecto.ruta("espacio_fijo", "0123456789abcdef.png"))
    n = servidor._imagenes_del_relato_por_pagar(ctx)
    ok(n == 2, f"una base apuntada cuyo fichero no está (copia de antes) se vuelve a contar ({n})")
    ctx.estado.set_params("assets", dict(params, tipo_relato={}))
    ok(servidor._imagenes_del_relato_por_pagar(ctx) == 0, "sin tipo de relato, nada (como antes)")
    ctx.estado.set_params("assets", params)
    # el previsto del PILOTO las suma; el cotizador de la pantalla no (no las dibuja)
    original = servidor._coste_previsto
    try:
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.50, "usd_por_imagen": 0.07}
        previsto = servidor._piloto_previsto(ctx, {"portadas": "plano"})
        ok(abs(previsto - (0.50 + 3 * 0.07)) < 1e-6,
           f"el previsto del piloto suma la base y los dos estados ({previsto}; antes 0,50)")
    finally:
        servidor._coste_previsto = original
    try:
        coste = servidor._coste_previsto(ctx, ["video"])
        ok("imagenes_relato" not in coste,
           "el cotizador de la pantalla no las promete (una tanda de la pantalla no las dibuja)")
    except Exception as fallo:                                    # noqa: BLE001
        print(f"  (cotizador entero omitido aquí: {str(fallo)[:80]})")


def prueba_tope(servidor, raiz):
    seccion("3] el tope: sin la portada antes de dibujar, lo gastado al reintentar y un solo «Seguir»")
    originales = (servidor._coste_previsto, servidor._piloto_gastado, servidor._piloto_usd_portada_pendiente)
    aj = {"tope_usd": 0.90, "portadas": "ambas"}
    try:
        # C: 0,40 gastado + 0,48 de imágenes cabe; con la portada (0,05) no, y no se para
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.48}
        servidor._piloto_gastado = lambda _ctx: 0.40
        servidor._piloto_usd_portada_pendiente = lambda _r, _v, _aj: 0.05
        try:
            queda, portada = servidor._piloto_tope_antes_de_dibujar(None, raiz, "p1", aj)
            ok(queda == 0.0 and portada == 0.05,
               "C: si las imágenes caben, no se para por la portada (la portada mira el tope en su paso)")
        except servidor._PilotoPara as parada:
            ok(False, f"C: no se tenía que parar por la portada: {parada}")
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.60}
        try:
            servidor._piloto_tope_antes_de_dibujar(None, raiz, "p1", aj)
            ok(False, "C: con imágenes que no caben se tenía que parar")
        except servidor._PilotoPara as parada:
            ok("0.60" in str(parada) and "0.40" in str(parada), f"y si las imágenes no caben, para ({parada})")
        # D: el paso 0 suma lo ya gastado
        servidor._piloto_gastado = lambda _ctx: 0.50
        try:
            servidor._piloto_tope_inicial(None, aj, 0.45)
            ok(False, "D: 0,50 gastados + 0,45 por hacer pasan de 0,90: se tenía que parar")
        except servidor._PilotoPara as parada:
            ok("ya gastados" in str(parada), f"D: al reintentar, lo ya gastado cuenta ({parada})")
        servidor._piloto_gastado = lambda _ctx: 0.95
        portada = servidor._piloto_usd_portada(aj)
        try:
            servidor._piloto_tope_inicial(None, aj, portada)
            ok(True, "D: con todo dibujado y solo la portada por hacer, no para (la portada mira en su paso)")
        except servidor._PilotoPara as parada:
            ok(False, f"D: no se tenía que parar solo por la portada: {parada}")
        servidor._piloto_gastado = lambda _ctx: 0.0
        try:
            servidor._piloto_tope_inicial(None, aj, 0.80)
            servidor._piloto_tope_inicial(None, aj, 0.0)
            ok(True, "D: un vídeo nuevo que cabe, o con todo hecho, sigue")
        except servidor._PilotoPara as parada:
            ok(False, f"D: no se tenía que parar: {parada}")
    finally:
        (servidor._coste_previsto, servidor._piloto_gastado, servidor._piloto_usd_portada_pendiente) = originales
    ok("tope" in servidor.PILOTO_SALTA_INTERRUPTOR and "interruptor" in servidor.PILOTO_SALTA_INTERRUPTOR,
       "E: «Seguir igualmente» desde el tope salta también el interruptor")
    import inspect                                                    # noqa: PLC0415
    ok("saltar in PILOTO_SALTA_INTERRUPTOR" in inspect.getsource(servidor._piloto_cadena),
       "E: y la cadena del piloto lo usa al decidir")
    ok("lo has mirado tú" not in inspect.getsource(servidor._piloto_decidir),
       "E: y el aviso ya no dice «lo has mirado tú» (puede que nadie lo haya mirado)")


def prueba_otro_sitio(carpeta):
    seccion("4] un plano de OTRO sitio no para el vídeo")
    proyecto = Y._proyecto(os.path.join(carpeta, "otro"))
    cat = Y._catalogo_y05()
    cat["sets"]["tienda"] = {"descripcion": "a small shop", "luz": "warm", "palabras": ["tienda"], "rotulo": ""}
    cat["beats"][2]["hasta"] = "B003"
    cat["beats"].append({"set": "tienda", "desde": "B004", "hasta": "B004", "personajes": [], "tono": "neutro",
                         "accion": "the shop", "palabras": []})
    params = Y._params([x for x in Y.LINEAS], estados={})
    params["catalogo"] = cat
    plan = Y.P6.planificar(proyecto, params)
    sueltos = [x["estado"] for x in plan.get("estados_sin_casar") or []]
    ok("rojo" not in sueltos, f"«rojo» en un plano de la tienda no para el vídeo del baño ({sueltos})")
    params["catalogo"] = Y._catalogo_y05()
    sueltos = [x["estado"] for x in Y.P6.planificar(proyecto, params).get("estados_sin_casar") or []]
    ok(sueltos == ["rojo"], f"en un plano del baño, sí ({sueltos})")


def prueba_ficha_igual_que_plan(servidor, carpeta):
    seccion("4b] la ficha del guion visual dice lo mismo que el plan (revisión del 12-11)")
    proyecto = Y._proyecto(os.path.join(carpeta, "ficha"))
    servidor.fijar_raiz_proyectos(os.path.join(carpeta, "ficha"))
    ctx = servidor.contexto(proyecto.id)
    casos = []
    tienda = Y._catalogo_y05()
    tienda["sets"]["tienda"] = {"descripcion": "a small shop", "luz": "warm", "palabras": ["tienda"], "rotulo": ""}
    tienda["beats"][2]["hasta"] = "B003"
    tienda["beats"].append({"set": "tienda", "desde": "B004", "hasta": "B004", "personajes": [], "tono": "neutro",
                            "accion": "the shop", "palabras": []})
    casos.append(("B004 entero en la tienda", tienda))
    viejo = copy.deepcopy(Y._catalogo_y05())
    viejo["sets"]["tienda"] = {"descripcion": "a small shop", "luz": "warm", "palabras": ["tienda"], "rotulo": ""}
    viejo.update(desde_lineas=True, lineas=[{"visual": Y.LINEAS[3]["visual"], "set": "tienda"}])
    casos.append(("catálogo viejo con la línea en la tienda y el tramo en el baño", viejo))
    casos.append(("todo en el baño", Y._catalogo_y05()))
    for nombre, cat in casos:
        params = Y._params(Y.LINEAS, estados={})
        params["catalogo"] = cat
        plan = [x["estado"] for x in Y.P6.planificar(proyecto, params).get("estados_sin_casar") or []]
        ctx.estado.set_params("assets", params)
        ficha = [x["estado"] for x in servidor._ficha_guion_visual(ctx).get("estados_sin_casar") or []]
        ok(sorted(plan) == sorted(ficha), f"{nombre}: plan {plan} = ficha {ficha}")


def main():
    try:
        prueba_duplicar(os.path.join(CARPETA, "proyectos"))
        prueba_otro_sitio(CARPETA)
        servidor = _servidor()
        if servidor is not None:
            prueba_cotizador(servidor, CARPETA)
            prueba_ficha_igual_que_plan(servidor, CARPETA)
            prueba_tope(servidor, os.path.join(CARPETA, "proyectos"))
    finally:
        shutil.rmtree(CARPETA, ignore_errors=True)
    print()
    if _fallos:
        print(f"TOPE Y COTIZADOR: FALLAN {len(_fallos)} de {_cuenta[0]} comprobaciones")
        for texto in _fallos:
            print(f"  - {texto}")
        return 1
    print(f"TOPE Y COTIZADOR OK: {_cuenta[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

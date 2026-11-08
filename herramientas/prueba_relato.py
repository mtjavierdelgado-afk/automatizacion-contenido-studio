#!/usr/bin/env python3
"""LA PRUEBA REAL DEL TIPO DE RELATO (rama tipo-de-relato): hasta cinco vídeos de verdad.

    asvs probar relato              (en la consola del VPS, como root)
    asvs probar relato --estilo ID  con ese estilo (si no, uno de foto)
    asvs probar relato --tope 5     tope de gasto en dólares (5 por defecto)

Hace, con TUS claves y sin que tengas que tocar nada, las pruebas de
aceptación del tipo de relato. Sin --solo hace b, c, d y e; la «a» (la mampara
batiente) solo con --solo a: el dueño decidió el 04-11 no hacer más guiones con
puertas batientes, que el generador no dibuja bien.

  a) D01-1 «Mampara que choca con el inodoro» — Un espacio que cambia (objeto)
  b) D01-2 «3 paletas para un baño sin ventana» — Un espacio que cambia (acabados)
  c) EstadoPlay: sala vacía → montada → torneo — Un espacio que cambia (estado)
  d) Recorrido por tres ambientes de una casa — Recorrido (una imagen por ambiente)
  e) Cocina que se ordena, en modo guion con un PRIMER PLANO — Un espacio que
     cambia (estado): el plano cercano lleva la base de referencia, no la edita

Para d y e (rama prueba-relato-de, 08-11-2026): en d Claude declara los
ambientes, se dibuja y se aprueba la imagen de cada uno y el juez mira cada
plano contra la de su ambiente; en e Claude escribe el guion visual, una de sus
líneas pasa a primer plano y el juez mira que ese plano es la misma cocina de
cerca, no otro cuarto.

Por cada una: crea el vídeo con su espacio fijo y su tipo de relato, escribe el
guion y la voz, reparte los sitios (Claude), GENERA la imagen base (se paga una),
le pide a Claude que la mire y la aprueba; dibuja UNA vez cada estado (la base
con su cambio: la mampara abierta, la corrediza) y lo aprueba igual; dibuja los
planos editando la imagen de su estado, pasa el revisor, REHACE lo que marca
(hasta dos rondas, medidas) y lo monta. Al final Claude compara cada plano con
la imagen que editó: ¿el mismo sitio, la misma cámara, el objeto igual y solo
cambia lo pedido?

    asvs probar relato --solo a --video ID   sigue un vídeo de prueba ya hecho
                                             desde su imagen base

EL TOPE: antes de cada cosa que se paga se suma lo ya gastado en estos vídeos y
lo que va a costar; si pasa del tope, para y lo dice (lo hecho se queda).

SI LA CONSOLA SE CORTA no pasa nada: corre aparte del terminal y guarda su
estado tras cada paso (<proyectos>/_sistema/pruebas_reales/en_curso_relato.json).
Volver a escribir `asvs probar relato` la enseña o la RETOMA sin volver a pagar.

No toca tus vídeos: crea tres nuevos («Prueba relato a/b/c <fecha>») que se
quedan en tu Studio para que los veas. El informe sale en la consola y en
<proyectos>/_sistema/pruebas_reales/relato_<fecha>.json.
"""
import argparse
import datetime
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "herramientas"))

import prueba_real as PR  # noqa: E402

ESCENARIOS = [
    {
        "clave": "a", "titulo": "D01-1 Mampara que choca",
        "relato": {"modo": "espacio_que_cambia", "cambia": "objeto"},
        "espacio": {
            "sitio": "bano_mampara",
            "descripcion": (
                "narrow apartment bathroom in Lima, 1.5 m wide x 2.4 m deep, seen from the "
                "door in the near short wall; FAR END: a walk-in shower across the whole width, "
                "0.9 m deep, with a low curb and a straight glass front parallel to the back "
                "wall, facing the camera; LEFT long wall: the toilet, right in front of the "
                "shower, its bowl only 0.4 m from the glass front; RIGHT long wall, near the "
                "entrance: a small wall-hung vanity with a single basin and a mirror; the room "
                "is tight on purpose: there is no free floor between the shower and the "
                "toilet; same layout, same camera height and same proportions in every shot; "
                "large light-grey porcelain tiles on the floor, white walls, chrome fittings"),
            "luz": "day, soft cool daylight from a small high window plus warm ceiling downlight",
            "secundarios": []},
        "material": (
            "Este error de mampara te deja sin espacio para pasar. Una mampara batiente "
            "necesita espacio libre para abrir. Y en un baño pequeño, ese arco choca con el "
            "inodoro o contigo. Una corrediza o un paño fijo con entrada libre te devuelve "
            "el espacio. Antes de comprar, marca en el piso con cinta por dónde va a abrir. "
            "Guárdalo y envíaselo a quien esté reformando su baño."),
        "indicaciones": ("Tono cercano y práctico. El mismo baño en todas las imágenes; lo "
                         "único que cambia es la mampara: batiente (choca con el inodoro) al "
                         "principio, corrediza al final."),
        "que_cambia": "only the shower screen: a hinged door that hits the toilet at first, "
                      "a sliding screen at the end",
    },
    {
        "clave": "b", "titulo": "D01-2 Tres paletas sin ventana",
        "relato": {"modo": "espacio_que_cambia", "cambia": "acabados"},
        "espacio": {
            "sitio": "bano_sin_ventana",
            "descripcion": (
                "small windowless apartment bathroom, 1.6 x 2.2 m, rectangular; wall-hung "
                "vanity with a single basin and a round mirror on the left wall, toilet on the "
                "back wall, walk-in shower with a clear fixed glass panel on the right; door in "
                "the near short wall; same layout, same camera height and same proportions in "
                "every shot"),
            "luz": "no window: warm ceiling downlights plus a backlit mirror",
            "secundarios": []},
        "material": (
            "Tres paletas para un baño sin ventana. Primera: blanco cálido con madera clara; "
            "rebota la luz y el baño parece más grande. Segunda: verde salvia con latón; "
            "acogedor sin oscurecer. Tercera: gris piedra con negro mate; elegante, pero "
            "necesita buena iluminación. ¿Con cuál te quedas? Te leo en comentarios."),
        "indicaciones": ("El mismo baño, la misma geometría y el mismo ángulo en todas las "
                         "imágenes; cambian SOLO los materiales y colores de cada paleta."),
        "que_cambia": "only materials and colours (three palettes); the geometry and the "
                      "camera angle stay the same",
    },
    {
        "clave": "c", "titulo": "EstadoPlay sala montada",
        "relato": {"modo": "espacio_que_cambia", "cambia": "estado"},
        "espacio": {
            "sitio": "sala_evento",
            "descripcion": (
                "medium-size event room in Lima, rectangular, light wooden floor, white walls, "
                "a row of three big windows on the left wall, double door at the back, power "
                "sockets on the right wall; same layout, same camera height and same "
                "proportions in every shot"),
            "luz": "evening, warm ceiling lights plus the cool glow of the screens when they are on",
            "secundarios": []},
        "material": (
            "Así llega la sala: vacía. En una hora montamos las pantallas, las consolas y los "
            "mandos, todo probado. Y a las ocho empieza el torneo: equipos, marcador y gente "
            "gritando cada gol. Tú pones el sitio, EstadoPlay pone la fiesta. Escríbenos y "
            "reserva tu fecha."),
        "indicaciones": ("La misma sala en todas las imágenes, con la misma cámara: primero "
                         "vacía, después montada con pantallas y consolas, al final con el "
                         "torneo y gente jugando."),
        "que_cambia": "only the stage of the set-up: empty room, then screens and consoles "
                      "set up, then a tournament with people playing",
    },
    # d y e (rama prueba-relato-de, 08-11-2026): lo que trajo tipo-de-relato-2,
    # que hasta hoy solo se podia probar a mano
    {
        "clave": "d", "titulo": "Recorrido por tres ambientes de una casa",
        "relato": {"modo": "recorrido"},
        # SIN espacio fijo: Claude declara los ambientes del lugar (2 a 6) con la
        # misma luz, que es el camino nuevo; el material nombra tres
        "espacio": None,
        "ambientes": True,
        "material": (
            "Un depa de dos dormitorios en Miraflores, en tonos tierra. Entramos por la sala: "
            "sofá de lino, mesa de centro de madera y una lámpara de pie. Al fondo, la cocina "
            "abierta con su isla de cuarzo blanco y tres banquitos. Y el dormitorio principal, "
            "con la cama de madera clara y una ventana grande al parque. El mismo piso de roble "
            "y la misma luz de tarde en toda la casa. ¿Cuál es tu ambiente favorito?"),
        "indicaciones": ("Un recorrido por los tres ambientes de la misma casa: sala, cocina y "
                         "dormitorio. Cada ambiente sale siempre igual cuando se vuelve a él, y "
                         "los tres comparten el piso, los materiales y la luz."),
        "que_cambia": "nothing inside a room: each room stays the same every time it is shown; "
                      "the three rooms share floor, materials and light",
    },
    {
        "clave": "e", "titulo": "Cocina que se ordena, con un primer plano (modo guion)",
        "relato": {"modo": "espacio_que_cambia", "cambia": "estado"},
        "espacio": {
            "sitio": "cocina_pequena",
            "descripcion": (
                "small galley kitchen in a Lima apartment, 1.8 m wide x 3 m long, seen from the "
                "door at the near end; LEFT wall: a white quartz countertop with an undermount "
                "steel sink and a black tap under a small window, sage green flat-front lower "
                "cabinets, open oak shelves above; RIGHT wall: a tall white fridge and a "
                "four-burner hob with a steel hood; terracotta hexagonal floor tiles; same "
                "layout, same camera height and same proportions in every shot"),
            "luz": "morning, soft daylight from the small window plus a warm ceiling light",
            "secundarios": []},
        # «Qué dibujan las imágenes: lo que dice el guion» y una de sus lineas con
        # camara de PRIMER PLANO: no edita la base, la lleva de referencia
        "opciones": {"imagenes": "guion"},
        "primer_plano": "close-up of the countertop next to the sink",
        "material": (
            "Así estaba la cocina: platos en el lavadero, frascos por toda la encimera y nada "
            "a mano. Con tres organizadores y una tarde, todo cambió. Los frascos, alineados "
            "en la repisa. La encimera, libre para cocinar. ¿Te animas a ordenar la tuya? "
            "Guárdalo para el fin de semana."),
        "indicaciones": ("La misma cocina en todas las imágenes, con la misma cámara: primero "
                         "desordenada, al final ordenada. Un primer plano de la encimera junto "
                         "al lavadero."),
        "que_cambia": "only the clutter: dishes and jars everywhere at first, everything put "
                      "away and lined up at the end",
    },
]


#: lo que se hace sin --solo: todo menos la mampara batiente (decisión del 04-11)
POR_DEFECTO = "bcde"


def _cerrar(informe, proyectos, inicio, datos):
    minutos = (time.time() - inicio) / 60
    veredicto = "APROBADA" if not informe.fallos else "CON FALLOS"
    print(f"\nPRUEBA DEL TIPO DE RELATO {veredicto}: {informe.fallos} fallo(s), "
          f"{informe.avisos} aviso(s), {minutos:.0f} min, gastado {datos.get('gastado_usd', 0):.2f} $")
    for clave, pid in (datos.get("proyectos") or {}).items():
        print(f"  vídeo {clave}: «{pid}» (se queda en tu Studio)")
    carpeta = PR._carpeta_informes(proyectos)                    # noqa: SLF001
    try:
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, "relato_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump({"veredicto": veredicto, "fallos": informe.fallos, "avisos": informe.avisos,
                       "minutos": round(minutos, 1), "lineas": informe.lineas, **datos},
                      fh, ensure_ascii=False, indent=1)
        print(f"Informe guardado en {ruta}")
    except OSError as fallo:
        print(f"(no se ha podido guardar el informe: {fallo})")
    return 0 if not informe.fallos else 1


def _elegir_estilo(api, pedido):
    _c, lista = api.get("/api/presets-light")
    estilos = [p for p in (lista or {}).get("presets") or [] if p.get("tipo", "canal") == "canal"]
    if pedido:
        return next((p for p in estilos if p.get("id") == pedido), None)
    # DE FOTO DE VERDAD (`datos.estilo.modo`), no «la palabra foto en algún
    # sitio»: la primera prueba real (20-10) cogió uno de ilustración porque su
    # ficha decía «fotogramas»
    foto = [p for p in estilos
            if (((p.get("datos") or {}).get("estilo") or {}).get("modo")) == "foto"]
    return foto[0] if foto else None


def _plan_de(raiz):
    activa = PR._activa(raiz, "assets")                           # noqa: SLF001
    try:
        with open(os.path.join(raiz, "pasos", "assets", f"v{activa}", "plan.json"),
                  encoding="utf-8") as fh:
            return json.load(fh), os.path.join(raiz, "pasos", "assets", f"v{activa}")
    except (OSError, ValueError):
        return {}, ""


def main():
    ap = argparse.ArgumentParser(description="La prueba real del tipo de relato")
    ap.add_argument("--api", default=f"http://127.0.0.1:{os.environ.get('PUERTO', '8110')}")
    ap.add_argument("--estilo", default="")
    ap.add_argument("--tope", type=float, default=5.0)
    ap.add_argument("--seguir", action="store_true")
    ap.add_argument("--solo", default="", help="a, b, c, d, e o varias: «bcde» (sin nada, bcde)")
    ap.add_argument("--video", default="", help="con --solo de UNA letra: sigue ese vídeo de prueba ya "
                    "hecho (guion, voz y sitios) desde su imagen base; si la aprobaste tú, no paga otra")
    # PARA PROBAR ESTA PRUEBA en local, con motores simulados
    ap.add_argument("--sin-claves", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--sin-opcionales", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    args.solo = args.solo.strip() or POR_DEFECTO
    if args.video and len(args.solo.strip()) != 1:
        ap.error("--video va con --solo de una sola letra (a, b, c, d o e)")
    api = PR.Api(args.api)
    proyectos = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")
    os.makedirs(PR._carpeta_informes(proyectos), exist_ok=True)   # noqa: SLF001
    ruta_estado = os.path.join(PR._carpeta_informes(proyectos), "en_curso_relato.json")  # noqa: SLF001

    est = None
    if args.seguir:
        try:
            with open(ruta_estado, encoding="utf-8") as fh:
                est = json.load(fh)
            print("RETOMANDO la prueba del tipo de relato donde se cortó (lo hecho no se repite "
                  "ni se paga otra vez)")
        except (OSError, ValueError):
            est = None
    if not est:
        est = {"inicio": time.time(), "estilo": "", "videos": {}, "hechas": [], "lineas": [],
               "tope": args.tope}
        cuantos = len([e for e in ESCENARIOS if not args.solo or e["clave"] in args.solo])
        print(f"LA PRUEBA REAL DEL TIPO DE RELATO ({cuantos} vídeo{'s' if cuantos != 1 else ''}, "
              f"tope {args.tope:.2f} $; no toca tus vídeos)")
    tope = float(est.get("tope") or args.tope)

    def guardar():
        est["lineas"] = informe.lineas
        temporal = ruta_estado + ".tmp"
        try:
            with open(temporal, "w", encoding="utf-8") as fh:
                json.dump(est, fh, ensure_ascii=False)
            os.replace(temporal, ruta_estado)
        except OSError:
            pass

    informe = PR.Informe(guardar)
    informe.cargar(est.get("lineas"), set(est.get("hechas") or []))
    inicio = float(est.get("inicio") or time.time())

    def hecha(parte):
        if parte not in est["hechas"]:
            est["hechas"].append(parte)
        guardar()

    def gastado():
        total = 0.0
        for v in est["videos"].values():
            _c, c = api.get(f"/api/proyectos/{v['pid']}/coste")
            total += float((c or {}).get("total_usd") or 0)
        return total

    def cabe(cuanto, que):
        ya = gastado()
        if ya + cuanto > tope:
            informe.apunta("fallo", f"PARADA POR EL TOPE antes de {que}",
                           f"gastado {ya:.2f} $ + {cuanto:.2f} $ pasaría de {tope:.2f} $")
            return False
        return True

    def datos_finales():
        return {"proyectos": {k: v["pid"] for k, v in est["videos"].items()},
                "gastado_usd": round(gastado(), 3), "juicios": est.get("juicios") or {},
                # las rondas de rehacer: lo que se marco, se rehizo y costo
                "rondas": est.get("rondas") or {},
                "estilo": est.get("estilo")}

    def cerrar():
        codigo = _cerrar(informe, proyectos, inicio, datos_finales())
        try:
            os.remove(ruta_estado)
        except OSError:
            pass
        return codigo

    def esperar(tid, limite, etiqueta):
        fin = api.trabajo(tid, limite, etiqueta)
        return fin.get("estado") == "listo", fin

    PR.seccion("1. El servidor y las claves")
    informe.parte = "claves"
    informe.lineas = [l for l in informe.lineas if l.get("parte") != "claves"]
    codigo, _s = api.get("/api/salud")
    if not informe.comprueba(codigo == 200, "el Studio contesta", f"HTTP {codigo}"):
        return 2
    _c, claves = api.post("/api/claves/probar", {"claude": True})
    estados = {p.get("proveedor"): p.get("estado") for p in (claves or {}).get("pruebas") or []}
    for prov in ("openai", "cartesia", "claude"):
        informe.comprueba(estados.get(prov) in ("ok", None), f"clave de {prov}", str(estados.get(prov)),
                          solo_aviso=args.sin_claves)
    if not args.sin_claves and any(estados.get(x) not in ("ok", None) for x in ("openai", "cartesia")):
        informe.apunta("fallo", "sin las claves de OpenAI y Cartesia no se puede seguir")
        return cerrar()
    if not est.get("estilo"):
        estilo = _elegir_estilo(api, args.estilo)
        if not informe.comprueba(bool(estilo), "hay un estilo de FOTO con el que hacerlo",
                                 "no hay ninguno en modo foto: créalo o pasa --estilo ID"):
            return cerrar()
        est["estilo"] = estilo["id"]
        est["estilo_nombre"] = estilo.get("nombre")
        guardar()
    informe.apunta("ok", f"estilo: «{est.get('estilo_nombre') or est['estilo']}»")

    elegidos = [e for e in ESCENARIOS if not args.solo or e["clave"] in args.solo]
    for esc in elegidos:
        k = esc["clave"]
        v = est["videos"].get(k) or {}

        def parte(nombre):
            informe.parte = f"{k}:{nombre}"
            informe.lineas = [l for l in informe.lineas if l.get("parte") != informe.parte]
            return f"{k}:{nombre}" not in est["hechas"]

        PR.seccion(f"{k}) {esc['titulo']} — {esc['relato']['modo']}"
                   + (f" ({esc['relato']['cambia']})" if esc["relato"].get("cambia") else ""))
        # --video: un video de prueba ya hecho, desde su imagen base (la que
        # apruebe una persona en la pantalla manda sobre el juez)
        if args.video and parte("crear"):
            v = {"pid": args.video.strip()}
            est["videos"][k] = v
            for hecho in ("crear", "guion", "voz", "sitios"):
                hecha(f"{k}:{hecho}")
            informe.apunta("ok", f"se sigue el vídeo ya hecho «{v['pid']}» desde su imagen base")
        # crear
        if parte("crear"):
            nombre = f"Prueba relato {k} " + datetime.datetime.now().strftime("%Y-%m-%d %H.%M")
            codigo, creado = api.post(f"/api/presets-light/{est['estilo']}/video", {
                "nombre": nombre, "duracion_objetivo_s": 30, "formato": "vertical",
                "material": esc["material"], "guion_propio": True,
                "indicaciones": esc["indicaciones"],
                "opciones": dict({"tipo_relato": esc["relato"]},
                                 **({"espacio_fijo": esc["espacio"]} if esc.get("espacio") else {}),
                                 **(esc.get("opciones") or {}))})
            pid = ((creado or {}).get("proyecto") or {}).get("id") or ""
            if not informe.comprueba(codigo == 201 and pid, f"se crea «{nombre}»",
                                     f"HTTP {codigo}: {str(creado)[:200]}"):
                return cerrar()
            v = {"pid": pid}
            est["videos"][k] = v
            hecha(f"{k}:crear")
        pid = v["pid"]
        raiz = os.path.join(proyectos, pid)
        _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
        informe.comprueba(all((ficha.get("resuelto") or {}).get(x) == esc["relato"][x]
                              for x in esc["relato"]),
                          "el vídeo nace con su tipo de relato", str(ficha.get("resuelto")))
        if esc.get("opciones", {}).get("imagenes"):
            _c, gvf = api.get(f"/api/proyectos/{pid}/guion_visual")
            informe.comprueba((gvf or {}).get("modo") == esc["opciones"]["imagenes"],
                              f"y con «Qué dibujan las imágenes: {esc['opciones']['imagenes']}»",
                              str((gvf or {}).get("modo")))

        # guion y voz
        for tanda, limite in (("guion", 900), ("voz", 900)):
            if not parte(tanda):
                continue
            api.libre(pid)
            _c, plan = api.get(f"/api/proyectos/{pid}/generar?tanda={tanda}&modo=pendientes")
            if plan.get("tareas") == 0:
                informe.apunta("ok", f"«{tanda}» ya estaba al día")
                hecha(f"{k}:{tanda}")
                continue
            if not cabe(float((plan.get("coste") or {}).get("usd_por_generar") or 0), f"«{tanda}» de {k}"):
                return cerrar()
            tid = v.get(f"tid_{tanda}")
            if not tid:
                codigo, lanz = api.post(f"/api/proyectos/{pid}/generar", {"tanda": tanda, "modo": "pendientes"})
                tid = (lanz or {}).get("trabajo_id")
                if not informe.comprueba(codigo == 202 and tid, f"se lanza «{tanda}»", f"HTTP {codigo}: {lanz}"):
                    return cerrar()
                v[f"tid_{tanda}"] = tid
                guardar()
            ok, fin = esperar(tid, limite, tanda)
            if not informe.comprueba(ok, f"«{tanda}» termina bien", f"{fin.get('estado')}: {fin.get('error')}"):
                return cerrar()
            hecha(f"{k}:{tanda}")

        # reparto y sitios (Claude)
        if parte("sitios"):
            api.libre(pid)
            tid = v.get("tid_sitios")
            if not tid:
                codigo, lanz = api.post(f"/api/proyectos/{pid}/escenarios", {})
                tid = (lanz or {}).get("trabajo_id")
                if not informe.comprueba(codigo == 202 and tid, "se reparten los sitios", f"HTTP {codigo}: {lanz}"):
                    return cerrar()
                v["tid_sitios"] = tid
                guardar()
            ok, fin = esperar(tid, 900, "sitios")
            if not informe.comprueba(ok, "el reparto de sitios termina bien", f"{fin.get('estado')}: {fin.get('error')}"):
                return cerrar()
            _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
            if ficha.get("faltan_cambios"):
                codigo, lanz = api.post(f"/api/proyectos/{pid}/tipo_relato/cambios", {})
                if (lanz or {}).get("trabajo_id"):
                    esperar(lanz["trabajo_id"], 900, "cambios")
            hecha(f"{k}:sitios")
        _c, pa = api.get(f"/api/proyectos/{pid}/pasos/assets")
        catalogo = ((pa or {}).get("params") or {}).get("catalogo") or {}
        sets = list((catalogo.get("sets") or {}).keys())
        if esc.get("ambientes"):
            # RECORRIDO: Claude declara entre 2 y 6 ambientes del mismo lugar; el
            # material nombra tres
            informe.comprueba(2 <= len(sets) <= 6, f"Claude declara los ambientes del lugar ({sets})",
                              f"{len(sets)} ambientes: tienen que ser de 2 a 6")
            informe.comprueba(len(sets) == 3, "y son los tres que nombra el material",
                              f"son {len(sets)}", solo_aviso=True)
        else:
            informe.comprueba(len(sets) == 1, f"un solo sitio en el catálogo ({sets})", "más de uno o ninguno")
            cambios = [b.get("cambio") for b in catalogo.get("beats") or []]
            # EN MODO GUION (e) los estados los pueden traer las lineas del guion
            # visual, que se escribe despues: aqui solo es un aviso
            informe.comprueba(any(cambios),
                              f"los tramos dicen qué cambia ({sum(1 for c in cambios if c)} de {len(cambios)})",
                              "ningún tramo trae cambio", solo_aviso=bool(esc.get("primer_plano")))

        # MODO GUION (e): Claude escribe el guion visual, UNA linea pasa a primer
        # plano y se aprueba. Va despues de los sitios: los estados que puede
        # pedir cada linea salen del reparto
        if esc.get("primer_plano") and parte("guion_visual"):
            api.libre(pid)
            tid = v.get("tid_gv")
            if not tid:
                codigo, lanz = api.post(f"/api/proyectos/{pid}/guion_visual/proponer", {})
                tid = (lanz or {}).get("trabajo_id")
                if not informe.comprueba(codigo == 202 and tid, "Claude escribe el guion visual",
                                         f"HTTP {codigo}: {lanz}"):
                    return cerrar()
                v["tid_gv"] = tid
                guardar()
            ok, fin = esperar(tid, 900, "guion visual")
            if not informe.comprueba(ok, "el guion visual sale", f"{fin.get('estado')}: {fin.get('error')}"):
                return cerrar()
            _c, gvf = api.get(f"/api/proyectos/{pid}/guion_visual")
            planos_gv = [dict(p) for p in (((gvf or {}).get("guion_visual") or {}).get("planos") or [])]
            if not informe.comprueba(len(planos_gv) >= 3, f"con {len(planos_gv)} líneas", "menos de tres"):
                return cerrar()
            # la linea del medio: ni el arranque (el «antes») ni el cierre
            medio = len(planos_gv) // 2
            planos_gv[medio]["camara"] = esc["primer_plano"]
            v["primer_plano_bloque"] = planos_gv[medio]["bloque"]
            v["primer_plano_visual"] = planos_gv[medio]["visual"]
            codigo, gvf = api.put(f"/api/proyectos/{pid}/guion_visual", {"planos": planos_gv})
            if not informe.comprueba(codigo == 200, f"la línea {medio + 1} pasa a «{esc['primer_plano']}»",
                                     f"HTTP {codigo}: {str(gvf)[:200]}"):
                return cerrar()
            codigo, gvf = api.post(f"/api/proyectos/{pid}/guion_visual/aprobar", {"aprobado": True})
            if not informe.comprueba(codigo == 200 and (gvf or {}).get("aprobado"),
                                     "el guion visual queda aprobado", f"HTTP {codigo}"):
                return cerrar()
            if (gvf or {}).get("trabajo_id"):
                esperar(gvf["trabajo_id"], 900, "comprobar el guion visual")
            hecha(f"{k}:guion_visual")

        # RECORRIDO (d): la imagen de CADA ambiente, juzgada y aprobada (el
        # principal primero: los demas la llevan de referencia «casa»)
        if esc.get("ambientes") and parte("ambientes"):
            api.libre(pid)
            _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
            for amb in (ficha or {}).get("ambientes") or []:
                if amb.get("aprobada"):
                    continue
                vale = False
                for intento in range(2):
                    usd = float((ficha or {}).get("usd_base") or 0.1)
                    if not cabe(usd, f"la imagen del ambiente «{amb['nombre']}» de {k}"):
                        return cerrar()
                    clave_tid = f"tid_amb_{amb['sitio']}_{intento}"
                    tid = v.get(clave_tid)
                    if not tid:
                        codigo, lanz = api.post(f"/api/proyectos/{pid}/tipo_relato/base/generar",
                                                {"usd": usd, "sitio": amb["sitio"], "otra": intento > 0})
                        tid = (lanz or {}).get("trabajo_id")
                        if not informe.comprueba(codigo == 202 and tid,
                                                 f"se dibuja el ambiente «{amb['nombre']}» (≈ {usd:.3f} $)",
                                                 f"HTTP {codigo}: {lanz}"):
                            return cerrar()
                        v[clave_tid] = tid
                        guardar()
                    ok, fin = esperar(tid, 900, f"ambiente {amb['nombre']}")
                    if not informe.comprueba(ok, f"el ambiente «{amb['nombre']}» sale",
                                             f"{fin.get('estado')}: {fin.get('error')}"):
                        return cerrar()
                    rel = (((_leer_tr(raiz)) or {}).get("bases") or {}).get(amb["sitio"]) or {}
                    ruta = os.path.join(raiz, *str(rel.get("imagen") or "").split("/"))
                    descripcion = ((catalogo.get("sets") or {}).get(amb["sitio"]) or {}).get("descripcion") or ""
                    try:
                        juicio = PR._juez(                             # noqa: SLF001
                            f"Lee esta imagen con Read: {ruta}\nTiene que ser la imagen de referencia de "
                            f"un AMBIENTE de una casa: «{amb['nombre']}: {descripcion}». Entero, sin "
                            "gente y sin texto. Contesta 'vale' (es ese ambiente, con sus muebles "
                            "fijos; los detalles de decoración NO cuentan). Devuelve SOLO "
                            '{"vale": "si" | "no", "por_que": "<una frase>"}', raiz)
                    except Exception as fallo:                          # noqa: BLE001
                        juicio = {"vale": "?", "por_que": f"no se pudo preguntar a Claude: {fallo}"}
                    est.setdefault("juicios", {}).setdefault(k, {})[f"amb_{amb['sitio']}_{intento}"] = juicio
                    vale = juicio.get("vale") in ("si", "sí")
                    informe.comprueba(vale, f"Claude da por bueno el ambiente «{amb['nombre']}»",
                                      str(juicio.get("por_que")), solo_aviso=intento == 0)
                    if vale:
                        codigo, ficha = api.post(f"/api/proyectos/{pid}/tipo_relato/base/aprobar",
                                                 {"sitio": amb["sitio"], "aprobada": True})
                        informe.comprueba(codigo == 200, f"el ambiente «{amb['nombre']}» queda aprobado",
                                          f"HTTP {codigo}")
                        break
                    _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
                if not vale:
                    informe.apunta("fallo", f"ninguna imagen del ambiente «{amb['nombre']}» vale: no se "
                                   "dibujan los planos (míralas en su «El tipo de relato»)")
                    break
            hecha(f"{k}:ambientes")
        if esc.get("ambientes"):
            _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
            ambs = (ficha or {}).get("ambientes") or []
            if not (ambs and all(a.get("aprobada") for a in ambs)):
                informe.apunta("aviso", f"{k}: faltan ambientes aprobados, se pasa al siguiente vídeo")
                continue

        # imagen base: generar, juzgar, aprobar
        if not esc.get("ambientes") and parte("base"):
            api.libre(pid)
            _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
            for intento in range(2):
                if ficha.get("base_aprobada"):
                    break
                usd = float(ficha.get("usd_base") or 0.1)
                if not cabe(usd, f"la imagen base de {k}"):
                    return cerrar()
                tid = v.get(f"tid_base{intento}")
                if not tid:
                    codigo, lanz = api.post(f"/api/proyectos/{pid}/tipo_relato/base/generar",
                                            {"usd": usd, "otra": intento > 0})
                    tid = (lanz or {}).get("trabajo_id")
                    if not informe.comprueba(codigo == 202 and tid, f"se genera la imagen base (≈ {usd:.3f} $)",
                                             f"HTTP {codigo}: {lanz}"):
                        return cerrar()
                    v[f"tid_base{intento}"] = tid
                    guardar()
                ok, fin = esperar(tid, 900, "imagen base")
                if not informe.comprueba(ok, "la imagen base sale", f"{fin.get('estado')}: {fin.get('error')}"):
                    return cerrar()
                _c, tr_ = api.get(f"/api/proyectos/{pid}/tipo_relato")
                sitio = tr_.get("sitio")
                base_rel = ((((_leer_tr(raiz)) or {}).get("bases") or {}).get(sitio) or {}).get("imagen")
                ruta_base = os.path.join(raiz, *str(base_rel or "").split("/")) if base_rel else ""
                try:
                    juicio = PR._juez(                             # noqa: SLF001
                        f"Lee esta imagen con Read: {ruta_base}\nTiene que ser la IMAGEN BASE de un sitio: "
                        f"«{esc['espacio']['descripcion']}». Vacío, entero, sin gente y sin texto, en su "
                        "estado inicial."
                        + (f" Y tiene que verse YA, donde dice, lo que luego cambia: «{tr_.get('inicial')}»."
                           if tr_.get("inicial") else "")
                        + " Contesta por separado: 'distribucion' (cada mueble fijo en la PARED que dice "
                        "y la puerta donde dice; cuánto ocupa cada uno y en qué punto exacto de su pared "
                        "NO cuentan), "
                        + ("'objeto' (lo que luego cambia está, en su zona, y es un objeto real "
                           "a escala: una puerta o un panel recto, vertical y plano, no torcido ni a medio "
                           "abrir; el lado exacto de las bisagras NO cuenta)"
                           if esc["relato"].get("cambia") == "objeto" else
                           # SIN OBJETO QUE CAMBIE no se juzga ninguno: con la
                           # pregunta de la puerta, el juez tumbaba la base del
                           # baño de las paletas por la puerta de ENTRADA
                           # entreabierta (prueba del servidor, 04-11-2026)
                           "'objeto' (en este vídeo no cambia ningún objeto: contesta 'si')")
                        + " y 'acabados' (colores y materiales). Devuelve SOLO "
                        '{"distribucion": "si" | "no", "objeto": "si" | "no", "acabados": "si" | "no", '
                        '"por_que": "<una frase>"}', raiz)
                    # LO QUE IMPORTA es la distribucion y el objeto: los planos editan la
                    # base, asi que un color de azulejo distinto sale igual en todos y no
                    # rompe la continuidad (prueba del 21-10: dos bases tumbadas por el
                    # beige y la griferia negra)
                    if "distribucion" in juicio:
                        if juicio.get("acabados") not in ("si", "sí"):
                            informe.apunta("aviso", "los acabados de la base no son los pedidos "
                                                    "(no impide aprobarla)")
                        juicio["vale"] = "si" if all(juicio.get(x) in ("si", "sí")
                                                     for x in ("distribucion", "objeto")) else "no"
                except Exception as fallo:                          # noqa: BLE001
                    juicio = {"vale": "?", "por_que": f"no se pudo preguntar a Claude: {fallo}"}
                est.setdefault("juicios", {}).setdefault(k, {})[f"base{intento}"] = juicio
                informe.comprueba(juicio.get("vale") in ("si", "sí"), "Claude da por buena la imagen base",
                                  f"{juicio.get('vale')}: {juicio.get('por_que')}", solo_aviso=intento == 0)
                if juicio.get("vale") not in ("si", "sí") and intento == 1:
                    # DOS BASES QUE NO VALEN: no se aprueba ninguna ni se pagan planos
                    # sobre un sitio que no es el pedido (se paró aquí el 20-10)
                    informe.apunta("fallo", "ninguna de las dos imágenes base vale: no se dibujan "
                                   "los planos de este vídeo (míralas en su «El tipo de relato»)")
                    break
                if juicio.get("vale") in ("si", "sí"):
                    codigo, ficha = api.post(f"/api/proyectos/{pid}/tipo_relato/base/aprobar",
                                             {"sitio": sitio, "aprobada": True})
                    informe.comprueba(codigo == 200 and (ficha or {}).get("base_aprobada"),
                                      "la imagen base queda aprobada", f"HTTP {codigo}")
                    break
                _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
            hecha(f"{k}:base")

        _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
        if not esc.get("ambientes") and not (ficha or {}).get("base_aprobada"):
            informe.apunta("aviso", f"{k}: sin imagen base aprobada, se pasa al siguiente vídeo")
            continue

        # UN ESTADO, UNA IMAGEN (21-10): cada cambio se dibuja una vez sobre la
        # base, lo juzga Claude y se aprueba; hasta dos intentos por estado
        if not esc.get("ambientes") and parte("estados"):
            api.libre(pid)
            sitio = (ficha or {}).get("sitio")
            ruta_base = os.path.join(raiz, *str(((((_leer_tr(raiz)) or {}).get("bases") or {})
                                                 .get(sitio) or {}).get("imagen") or "").split("/"))
            for e in (ficha or {}).get("estados") or []:
                if e.get("aprobada"):
                    continue
                vale = False
                for intento in range(2):
                    usd = float(ficha.get("usd_base") or 0.1)
                    if not cabe(usd, f"el estado «{e['estado']}» de {k}"):
                        return cerrar()
                    clave_tid = f"tid_estado_{e['estado']}_{intento}"
                    tid = v.get(clave_tid)
                    if not tid:
                        codigo, lanz = api.post(f"/api/proyectos/{pid}/tipo_relato/base/generar",
                                                {"usd": usd, "estado": e["estado"], "otra": intento > 0})
                        tid = (lanz or {}).get("trabajo_id")
                        if not informe.comprueba(codigo == 202 and tid,
                                                 f"se dibuja el estado «{e['estado']}» (≈ {usd:.3f} $)",
                                                 f"HTTP {codigo}: {lanz}"):
                            return cerrar()
                        v[clave_tid] = tid
                        guardar()
                    ok, fin = esperar(tid, 900, f"estado {e['estado']}")
                    if not informe.comprueba(ok, f"el estado «{e['estado']}» sale",
                                             f"{fin.get('estado')}: {fin.get('error')}"):
                        return cerrar()
                    imagen = ((((((_leer_tr(raiz)) or {}).get("bases") or {}).get(sitio) or {})
                               .get("estados") or {}).get(e["estado"]) or {}).get("imagen")
                    ruta = os.path.join(raiz, *str(imagen or "").split("/"))
                    try:
                        juicio = PR._juez(                             # noqa: SLF001
                            f"Lee con Read la IMAGEN BASE: {ruta_base}\ny la imagen de un ESTADO: {ruta}\n"
                            f"La del estado tiene que ser la MISMA habitación con la misma cámara, vacía, "
                            f"con UN cambio: «{e['cambio']}». Contesta por separado: 'mismo_sitio' (misma "
                            "distribución y cámara), 'cambio' (se ve el cambio pedido, y nada más del sitio "
                            "cambia) y 'objeto' (" + ("lo que cambia es un objeto real a escala: recto, "
                            "plano y vertical si es un vidrio o una puerta; no torcido ni deformado"
                            if esc["relato"].get("cambia") == "objeto" else
                            "en este vídeo no cambia ningún objeto: contesta 'si'") + "). Devuelve SOLO "
                            '{"mismo_sitio": "si"|"no", "cambio": "si"|"no", "objeto": "si"|"no", '
                            '"por_que": "<una frase>"}', raiz)
                    except Exception as fallo:                          # noqa: BLE001
                        juicio = {"por_que": f"no se pudo preguntar a Claude: {fallo}"}
                    est.setdefault("juicios", {}).setdefault(k, {})[f"estado_{e['estado']}_{intento}"] = juicio
                    vale = all(juicio.get(x) in ("si", "sí") for x in ("mismo_sitio", "cambio", "objeto"))
                    informe.comprueba(vale, f"Claude da por bueno el estado «{e['estado']}»",
                                      str(juicio.get("por_que")), solo_aviso=intento == 0)
                    if vale:
                        codigo, ficha = api.post(f"/api/proyectos/{pid}/tipo_relato/base/aprobar",
                                                 {"sitio": sitio, "estado": e["estado"], "aprobada": True})
                        informe.comprueba(codigo == 200, f"el estado «{e['estado']}» queda aprobado",
                                          f"HTTP {codigo}")
                        break
                    _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
                if not vale:
                    informe.apunta("fallo", f"ninguna imagen del estado «{e['estado']}» vale: no se "
                                   "dibujan los planos (míralas en su «El tipo de relato»)")
                    break
            hecha(f"{k}:estados")
            _c, ficha = api.get(f"/api/proyectos/{pid}/tipo_relato")
        if not esc.get("ambientes") and not (ficha or {}).get("listo", (ficha or {}).get("base_aprobada")):
            informe.apunta("aviso", f"{k}: faltan imágenes de estado aprobadas, se pasa al siguiente vídeo")
            continue
        # las imagenes y el montaje
        def tanda_entera(tanda, limite, nombre=None):
            """Lanza y espera una tanda. -> True si sigue la prueba."""
            nombre = nombre or tanda
            if not parte(nombre):
                return True
            api.libre(pid, 3600)
            extra = ({"tareas": {"plan_cartelas": False, "direccion": False}}
                     if args.sin_opcionales else {})
            _c, plan = api.get(f"/api/proyectos/{pid}/generar?tanda={tanda}&modo=pendientes")
            if plan.get("impedimentos"):
                informe.apunta("fallo", f"«{tanda}» no se puede lanzar", plan["impedimentos"][0].get("que"))
                return False
            if plan.get("tareas") == 0:
                hecha(f"{k}:{nombre}")
                return True
            prometido = float((plan.get("coste") or {}).get("usd_por_generar") or 0)
            if not cabe(prometido, f"«{tanda}» de {k}"):
                return False
            tid = v.get(f"tid_{nombre}")
            if not tid:
                codigo, lanz = api.post(f"/api/proyectos/{pid}/generar",
                                        {"tanda": tanda, "modo": "pendientes", **extra})
                tid = (lanz or {}).get("trabajo_id")
                if not informe.comprueba(codigo == 202 and tid, f"se lanza «{tanda}» (≈ {prometido:.2f} $)",
                                         f"HTTP {codigo}: {lanz}"):
                    return False
                v[f"tid_{nombre}"] = tid
                guardar()
            ok, fin = esperar(tid, limite, tanda)
            if not informe.comprueba(ok, f"«{tanda}» termina bien", f"{fin.get('estado')}: {fin.get('error')}"):
                return False
            hecha(f"{k}:{nombre}")
            return True

        if not (tanda_entera("video", 3600) and tanda_entera("render", 2400)):
            return cerrar()

        # el revisor
        if parte("revisor"):
            api.libre(pid)
            codigo, lanz = api.post(f"/api/proyectos/{pid}/imagenes/revisar", {"forzar": True})
            if (lanz or {}).get("trabajo_id"):
                esperar(lanz["trabajo_id"], 1800, "revisor")
            hecha(f"{k}:revisor")

        # REHACER LO QUE MARCA EL REVISOR, HASTA DOS RONDAS (pedido del dueño,
        # 21-10): rehacer las marcadas, revisarlas otra vez y, si siguen
        # marcadas, una segunda vez; ahi se corta. Cada ronda queda medida (que
        # se marco, que se rehizo, cuanto costo) para saber cuantas rondas
        # merece la pena pagar cuando esto vaya solo.
        rondas = est.setdefault("rondas", {}).setdefault(k, [])
        rehizo = False
        for ronda in (1, 2):
            if not parte(f"ronda{ronda}"):
                rehizo = rehizo or any(r.get("rehechas") for r in rondas)
                continue
            api.libre(pid)
            _c, rev = api.get(f"/api/proyectos/{pid}/imagenes/revision")
            pend = (rev or {}).get("pendientes") or []
            if not pend:
                informe.apunta("ok", f"ronda {ronda}: el revisor no marca nada que rehacer")
                hecha(f"{k}:ronda{ronda}")
                break
            usd_img = float((ficha or {}).get("usd_base") or 0.08)
            if not cabe(len(pend) * usd_img, f"la ronda {ronda} de rehacer de {k}"):
                return cerrar()
            antes = gastado()
            arranque = time.time()
            planos = sorted({p["plano"] for p in pend})
            codigo, _r = api.post(f"/api/proyectos/{pid}/imagenes/revision/aplicar",
                                  {"notas": [p["nota"] for p in pend]})
            if not informe.comprueba(codigo == 202 or codigo == 200,
                                     f"ronda {ronda}: se rehacen las {len(planos)} marcadas {planos}",
                                     f"HTTP {codigo}: {_r}"):
                return cerrar()
            # la cola de notas: hasta que no quede nada dibujandose
            limite = time.time() + 1800
            visto = None
            while time.time() < limite:
                time.sleep(5)
                _c, cola = api.get(f"/api/proyectos/{pid}/imagenes/cola")
                trabajo = (cola or {}).get("trabajo") or {}
                quedan_cola = len((cola or {}).get("cola") or []) + (1 if (cola or {}).get("actual") else 0)
                hechas = max(0, len(planos) - quedan_cola)
                linea = (f"     … rehacer ronda {ronda}: {hechas} de {len(planos)} imágenes"
                         f" · lleva {int(time.time() - arranque)} s"
                         + (f" · ≈ {int((cola or {}).get('segundos_por_imagen') or 0) * quedan_cola} s más"
                            if quedan_cola and (cola or {}).get("segundos_por_imagen") else ""))
                if linea.split(" · lleva")[0] != visto:
                    print(linea, flush=True)
                    visto = linea.split(" · lleva")[0]
                if not quedan_cola and trabajo.get("estado") not in ("pendiente", "ejecutando"):
                    break
            api.libre(pid)
            codigo, lanz = api.post(f"/api/proyectos/{pid}/imagenes/revisar",
                                    {"planos": planos, "forzar": True})
            if (lanz or {}).get("trabajo_id"):
                esperar(lanz["trabajo_id"], 1800, f"revisor ronda {ronda}")
            _c, rev = api.get(f"/api/proyectos/{pid}/imagenes/revision")
            quedan = sorted({p["plano"] for p in (rev or {}).get("pendientes") or []})
            rondas.append({"ronda": ronda, "marcadas": planos, "rehechas": len(planos),
                           "quedan": quedan, "usd": round(gastado() - antes, 3),
                           "segundos": round(time.time() - arranque)})
            rehizo = True
            informe.comprueba(not quedan, f"ronda {ronda}: tras rehacer, el revisor ya no marca nada",
                              f"siguen marcadas {quedan}", solo_aviso=ronda == 1)
            hecha(f"{k}:ronda{ronda}")
            if not quedan:
                break
        if rehizo and not tanda_entera("render", 2400, "render2"):
            return cerrar()
        plan, carpeta = _plan_de(raiz)
        editados = [e for e in plan.get("escenas") or [] if e.get("editar_base")]
        if not esc.get("ambientes"):
            informe.comprueba(bool(editados), f"{len(editados)} planos se generaron editando la base",
                              "ningún plano editado desde la base")
        try:
            with open(os.path.join(raiz, "revisor.json"), encoding="utf-8") as fh:
                revisadas = (json.load(fh) or {}).get("revisadas") or {}
        except (OSError, ValueError):
            revisadas = {}
        congruencia = sorted(sid for sid, f in revisadas.items()
                             if any((p or {}).get("tipo") == "congruencia" for p in f.get("problemas") or []))
        informe.comprueba(not congruencia, "el revisor no marca incumplimientos de congruencia",
                          f"en {congruencia}")

        # el juez: cada plano editado contra la imagen que edito (la base o la de
        # su estado), y el objeto que cambia igual que en ella
        if parte("juez") and editados:
            def _ruta_rel(rel):
                return os.path.join(raiz, *str(rel or "").split("/"))
            sitio_b = (ficha or {}).get("sitio")
            base = _ruta_rel(((((_leer_tr(raiz)) or {}).get("bases") or {}).get(sitio_b) or {}).get("imagen"))
            lista = "\n".join(
                f"- {e['id']}: {os.path.join(carpeta, 'escenas', e['id'] + '.png')} · editado desde "
                f"{_ruta_rel(e.get('base')) if e.get('base') else base}"
                + (f" (la imagen del estado «{e['base_clave'].split('#', 1)[-1]}», que ya muestra: "
                   f"{e.get('cambio')})" if e.get("base_clave") else
                   f" · se pidió cambiar: {e.get('cambio') or '(nada del sitio: solo la acción)'}")
                for e in editados)
            try:
                juicio = PR._juez(                                 # noqa: SLF001
                    f"Lee con Read la IMAGEN BASE: {base}\ny cada uno de estos planos con la imagen "
                    f"desde la que se editó (ábrela también):\n{lista}\n"
                    f"Lo que puede cambiar en este vídeo: {esc['que_cambia']}.\nPara cada plano: "
                    "'mismo_sitio' (la misma distribución, paredes y muebles fijos que la base, con la "
                    "misma cámara aproximada), 'solo_lo_pedido' (no cambia nada del sitio fuera de lo "
                    "pedido) y 'objeto_igual' (lo que cambia —una puerta, un vidrio— está igual que en "
                    "la imagen desde la que se editó: misma posición, misma apertura, misma forma, recto "
                    "y a escala). Devuelve SOLO "
                    '{"planos": [{"id": "S001", "mismo_sitio": "si"|"no", "solo_lo_pedido": "si"|"no", '
                    '"objeto_igual": "si"|"no", "por_que": "<una frase>"}]}', raiz)
            except Exception as fallo:                              # noqa: BLE001
                juicio = {"planos": [], "error": str(fallo)}
            est.setdefault("juicios", {}).setdefault(k, {})["planos"] = juicio
            planos = (juicio or {}).get("planos") or []
            malos = [p.get("id") for p in planos if p.get("mismo_sitio") not in ("si", "sí")]
            de_mas = [p.get("id") for p in planos if p.get("solo_lo_pedido") not in ("si", "sí")]
            objeto = [p.get("id") for p in planos if p.get("objeto_igual") not in ("si", "sí")]
            informe.comprueba(planos and not malos, f"Claude ve el MISMO sitio en los {len(planos)} planos",
                              f"distinto en {malos} {juicio.get('error') or ''}")
            informe.comprueba(planos and not objeto,
                              "y lo que cambia sale igual que en su imagen en todos",
                              f"distinto en {objeto}: "
                              + "; ".join(f"{p.get('id')}: {p.get('por_que')}" for p in planos
                                          if p.get("id") in objeto)[:400])
            informe.comprueba(planos and not de_mas, "y solo cambia lo pedido", f"cambia de más en {de_mas}",
                              solo_aviso=True)
            hecha(f"{k}:juez")

        def _de_disco(rel):
            return os.path.join(raiz, *str(rel or "").split("/"))

        # e) EL PRIMER PLANO: no edita la base (la lleva de referencia, o la de
        # su estado) y es la MISMA cocina de cerca, no otro cuarto
        if esc.get("primer_plano") and parte("juez_primer_plano"):
            cercanos = [e for e in plan.get("escenas") or []
                        if ((e.get("linea_gv") or {}).get("camara") or "") == esc["primer_plano"]]
            if informe.comprueba(bool(cercanos), f"la línea de primer plano es un plano ({[e['id'] for e in cercanos]})",
                                 "ningún plano lleva la cámara de primer plano"):
                informe.comprueba(not any(e.get("editar_base") for e in cercanos),
                                  "y no edita la base: la lleva de referencia",
                                  f"edita la base: {[e['id'] for e in cercanos if e.get('editar_base')]}")
                bases_tr = ((_leer_tr(raiz)) or {}).get("bases") or {}
                sitio_e = (ficha or {}).get("sitio")
                lista = []
                for e in cercanos:
                    estado_ref = str(e.get("ref_clave") or "").split("#", 1)[-1] if "#" in str(e.get("ref_clave") or "") else ""
                    ref = (((bases_tr.get(sitio_e) or {}).get("estados") or {}).get(estado_ref) or {}).get("imagen") \
                        if estado_ref else (bases_tr.get(sitio_e) or {}).get("imagen")
                    lista.append(f"- {e['id']}: {os.path.join(carpeta, 'escenas', e['id'] + '.png')} · su "
                                 f"referencia del sitio: {_de_disco(ref)}")
                try:
                    juicio = PR._juez(                             # noqa: SLF001
                        "Cada uno de estos planos es un PRIMER PLANO de un sitio y lleva de referencia la "
                        f"imagen entera de ese sitio. Lee con Read las dos de cada uno:\n{chr(10).join(lista)}\n"
                        f"El sitio: «{esc['espacio']['descripcion']}». Para cada plano: 'de_cerca' (es un "
                        "plano cercano, no la habitación entera) y 'mismo_sitio' (lo que se ve de cerca "
                        "es de ESE sitio: los mismos materiales, colores y muebles fijos que su referencia; "
                        "no otro cuarto ni otra cocina). Devuelve SOLO "
                        '{"planos": [{"id": "S001", "de_cerca": "si"|"no", "mismo_sitio": "si"|"no", '
                        '"por_que": "<una frase>"}]}', raiz)
                except Exception as fallo:                          # noqa: BLE001
                    juicio = {"planos": [], "error": str(fallo)}
                est.setdefault("juicios", {}).setdefault(k, {})["primer_plano"] = juicio
                pls = (juicio or {}).get("planos") or []
                lejos = [p.get("id") for p in pls if p.get("de_cerca") not in ("si", "sí")]
                otro = [p.get("id") for p in pls if p.get("mismo_sitio") not in ("si", "sí")]
                informe.comprueba(pls and not otro, "Claude ve la MISMA cocina en el primer plano",
                                  f"otro sitio en {otro}: " + "; ".join(
                                      str(p.get("por_que")) for p in pls if p.get("id") in otro)[:300]
                                  + (juicio.get("error") or ""))
                informe.comprueba(pls and not lejos, "y el plano es de cerca", f"no es cercano: {lejos}",
                                  solo_aviso=True)
            hecha(f"{k}:juez_primer_plano")

        # d) EL RECORRIDO: cada plano contra la imagen de SU ambiente, y los
        # ambientes entre si como una misma casa
        if esc.get("ambientes") and parte("juez_ambientes"):
            bases_tr = ((_leer_tr(raiz)) or {}).get("bases") or {}
            imagenes = {s: _de_disco((b or {}).get("imagen")) for s, b in bases_tr.items() if (b or {}).get("imagen")}
            de_ambiente = [e for e in plan.get("escenas") or [] if e.get("set") in imagenes]
            informe.comprueba(len({e["set"] for e in de_ambiente}) >= 2,
                              f"los planos pasan por {len({e['set'] for e in de_ambiente})} ambientes",
                              "todos los planos en un solo ambiente")
            lista = "\n".join(f"- {e['id']}: {os.path.join(carpeta, 'escenas', e['id'] + '.png')} · su "
                              f"ambiente: {e['set']}" for e in de_ambiente)
            refs = "\n".join(f"- {s}: {ruta}" for s, ruta in imagenes.items())
            try:
                juicio = PR._juez(                                 # noqa: SLF001
                    f"Lee con Read la imagen de referencia de cada AMBIENTE de una casa:\n{refs}\ny cada "
                    f"uno de estos planos:\n{lista}\nPara cada plano: 'mismo_ambiente' (es SU ambiente: "
                    "los mismos muebles fijos, paredes, ventanas y suelo que su referencia; la cámara "
                    "puede ser otra y la gente o los objetos sueltos no cuentan). Y una vez: "
                    "'misma_casa' (los ambientes comparten suelo, materiales y luz). Devuelve SOLO "
                    '{"planos": [{"id": "S001", "mismo_ambiente": "si"|"no", "por_que": "<una frase>"}], '
                    '"misma_casa": "si"|"no", "por_que_casa": "<una frase>"}', raiz)
            except Exception as fallo:                              # noqa: BLE001
                juicio = {"planos": [], "error": str(fallo)}
            est.setdefault("juicios", {}).setdefault(k, {})["ambientes"] = juicio
            pls = (juicio or {}).get("planos") or []
            otro = [p.get("id") for p in pls if p.get("mismo_ambiente") not in ("si", "sí")]
            informe.comprueba(pls and not otro, f"Claude ve cada plano en SU ambiente ({len(pls)} planos)",
                              f"distinto en {otro}: " + "; ".join(
                                  str(p.get("por_que")) for p in pls if p.get("id") in otro)[:300]
                              + (juicio.get("error") or ""))
            informe.comprueba((juicio or {}).get("misma_casa") in ("si", "sí"),
                              "y los ambientes son la misma casa", str((juicio or {}).get("por_que_casa")))
            hecha(f"{k}:juez_ambientes")

        mp4 = os.path.join(raiz, "pasos", "render", f"v{PR._activa(raiz, 'render')}", "video.mp4")  # noqa: SLF001
        duracion, pistas = PR._ffprobe(mp4)                       # noqa: SLF001
        informe.comprueba(os.path.isfile(mp4) and "video" in pistas, f"el MP4 está montado ({duracion:.1f} s)",
                          mp4)
        informe.apunta("ok", f"gastado hasta ahora: {gastado():.2f} $ de {tope:.2f} $")

    return cerrar()


def _leer_tr(raiz):
    """`assets.tipo_relato` del proyecto leído del disco (las rutas de las bases)."""
    try:
        with open(os.path.join(raiz, "estado.json"), encoding="utf-8") as fh:
            doc = json.load(fh)
        return (((doc.get("pasos") or {}).get("assets") or {}).get("params") or {}).get("tipo_relato") or {}
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    sys.exit(main())

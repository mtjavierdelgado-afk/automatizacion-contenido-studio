#!/usr/bin/env python3
"""LA PRUEBA REAL DEL TIPO DE RELATO (rama tipo-de-relato): tres vídeos de verdad.

    asvs probar relato              (en la consola del VPS, como root)
    asvs probar relato --estilo ID  con ese estilo (si no, uno de foto)
    asvs probar relato --tope 5     tope de gasto en dólares (5 por defecto)

Hace, con TUS claves y sin que tengas que tocar nada, las tres pruebas de
aceptación de la rama:

  a) D01-1 «Mampara que choca con el inodoro» — Un espacio que cambia (objeto)
  b) D01-2 «3 paletas para un baño sin ventana» — Un espacio que cambia (acabados)
  c) EstadoPlay: sala vacía → montada → torneo — Un espacio que cambia (estado)

Por cada una: crea el vídeo con su espacio fijo y su tipo de relato, escribe el
guion y la voz, reparte los sitios (Claude), GENERA la imagen base (se paga una),
le pide a Claude que la mire y la aprueba, dibuja los planos editando la base,
pasa el revisor y lo monta. Al final Claude compara cada plano con su base:
¿el mismo sitio, la misma cámara, y solo cambia lo pedido?

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
                "small apartment bathroom in Lima, 1.5 m wide x 2.4 m deep, seen from the "
                "door in the near short wall; LEFT long wall: the toilet, near the middle; "
                "BACK short wall, left half: a wall-hung vanity with a single basin and a "
                "rectangular mirror above it; RIGHT side, from the back wall forward: a walk-in "
                "shower 0.9 m deep with a low curb and its glass screen facing the room; same "
                "layout, same camera height and same proportions in every shot; large "
                "light-grey porcelain tiles on the floor, white walls, chrome fittings"),
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
]


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
    ap.add_argument("--solo", default="", help="a, b, c o varias: «ab»")
    ap.add_argument("--video", default="", help="con --solo de UNA letra: sigue ese vídeo de prueba ya "
                    "hecho (guion, voz y sitios) desde su imagen base; si la aprobaste tú, no paga otra")
    # PARA PROBAR ESTA PRUEBA en local, con motores simulados
    ap.add_argument("--sin-claves", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--sin-opcionales", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.video and len(args.solo.strip()) != 1:
        ap.error("--video va con --solo de una sola letra (a, b o c)")
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
        print(f"LA PRUEBA REAL DEL TIPO DE RELATO (3 vídeos, tope {args.tope:.2f} $; no toca tus vídeos)")
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

        PR.seccion(f"{k}) {esc['titulo']} — {esc['relato']['modo']} ({esc['relato']['cambia']})")
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
                "opciones": {"espacio_fijo": esc["espacio"], "tipo_relato": esc["relato"]}})
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
        informe.comprueba((ficha.get("resuelto") or {}).get("modo") == esc["relato"]["modo"]
                          and (ficha.get("resuelto") or {}).get("cambia") == esc["relato"]["cambia"],
                          "el vídeo nace con su tipo de relato", str(ficha.get("resuelto")))

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
        informe.comprueba(len(sets) == 1, f"un solo sitio en el catálogo ({sets})", "más de uno o ninguno")
        cambios = [b.get("cambio") for b in catalogo.get("beats") or []]
        informe.comprueba(any(cambios), f"los tramos dicen qué cambia ({sum(1 for c in cambios if c)} de {len(cambios)})",
                          "ningún tramo trae cambio")

        # imagen base: generar, juzgar, aprobar
        if parte("base"):
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
                        "NO cuentan), 'objeto' (lo que luego cambia está, en su zona, y es un objeto real "
                        "a escala: una puerta o un panel recto, vertical y plano, no torcido ni a medio "
                        "abrir; el lado exacto de las bisagras NO cuenta; 'si' si no se pide ninguno) y 'acabados' (colores y materiales). Devuelve SOLO "
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
        if not (ficha or {}).get("base_aprobada"):
            informe.apunta("aviso", f"{k}: sin imagen base aprobada, se pasa al siguiente vídeo")
            continue
        # las imagenes y el montaje
        for tanda, limite in (("video", 3600), ("render", 2400)):
            if not parte(tanda):
                continue
            api.libre(pid, 3600)
            extra = ({"tareas": {"plan_cartelas": False, "direccion": False}}
                     if args.sin_opcionales else {})
            _c, plan = api.get(f"/api/proyectos/{pid}/generar?tanda={tanda}&modo=pendientes")
            if plan.get("impedimentos"):
                informe.apunta("fallo", f"«{tanda}» no se puede lanzar", plan["impedimentos"][0].get("que"))
                return cerrar()
            if plan.get("tareas") == 0:
                hecha(f"{k}:{tanda}")
                continue
            prometido = float((plan.get("coste") or {}).get("usd_por_generar") or 0)
            if not cabe(prometido, f"«{tanda}» de {k}"):
                return cerrar()
            tid = v.get(f"tid_{tanda}")
            if not tid:
                codigo, lanz = api.post(f"/api/proyectos/{pid}/generar",
                                        {"tanda": tanda, "modo": "pendientes", **extra})
                tid = (lanz or {}).get("trabajo_id")
                if not informe.comprueba(codigo == 202 and tid, f"se lanza «{tanda}» (≈ {prometido:.2f} $)",
                                         f"HTTP {codigo}: {lanz}"):
                    return cerrar()
                v[f"tid_{tanda}"] = tid
                guardar()
            ok, fin = esperar(tid, limite, tanda)
            if not informe.comprueba(ok, f"«{tanda}» termina bien", f"{fin.get('estado')}: {fin.get('error')}"):
                return cerrar()
            hecha(f"{k}:{tanda}")

        # el revisor
        if parte("revisor"):
            api.libre(pid)
            codigo, lanz = api.post(f"/api/proyectos/{pid}/imagenes/revisar", {"forzar": True})
            if (lanz or {}).get("trabajo_id"):
                esperar(lanz["trabajo_id"], 1800, "revisor")
            hecha(f"{k}:revisor")
        plan, carpeta = _plan_de(raiz)
        editados = [e for e in plan.get("escenas") or [] if e.get("editar_base")]
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

        # el juez: cada plano editado contra su base
        if parte("juez") and editados:
            base = os.path.join(raiz, *str(editados[0].get("base") or "").split("/"))
            lista = "\n".join(f"- {e['id']}: {os.path.join(carpeta, 'escenas', e['id'] + '.png')} "
                              f"· se pidió cambiar: {e.get('cambio') or '(nada del sitio: solo la acción)'}"
                              for e in editados)
            try:
                juicio = PR._juez(                                 # noqa: SLF001
                    f"Lee con Read la IMAGEN BASE: {base}\ny cada uno de estos planos:\n{lista}\n"
                    f"Lo que puede cambiar en este vídeo: {esc['que_cambia']}.\nPara cada plano: ¿es "
                    "el MISMO sitio que la base (misma distribución, paredes, muebles fijos), con la "
                    "misma cámara aproximada, y cambia SOLO lo pedido? Devuelve SOLO "
                    '{"planos": [{"id": "S001", "mismo_sitio": "si"|"no", "solo_lo_pedido": "si"|"no", '
                    '"por_que": "<una frase>"}]}', raiz)
            except Exception as fallo:                              # noqa: BLE001
                juicio = {"planos": [], "error": str(fallo)}
            est.setdefault("juicios", {}).setdefault(k, {})["planos"] = juicio
            planos = (juicio or {}).get("planos") or []
            malos = [p.get("id") for p in planos if p.get("mismo_sitio") not in ("si", "sí")]
            de_mas = [p.get("id") for p in planos if p.get("solo_lo_pedido") not in ("si", "sí")]
            informe.comprueba(planos and not malos, f"Claude ve el MISMO sitio en los {len(planos)} planos",
                              f"distinto en {malos} {juicio.get('error') or ''}")
            informe.comprueba(planos and not de_mas, "y solo cambia lo pedido", f"cambia de más en {de_mas}",
                              solo_aviso=True)
            hecha(f"{k}:juez")
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

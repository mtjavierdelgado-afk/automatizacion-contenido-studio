"""DÓNDE SE VA EL TIEMPO Y EL DINERO DE UN VÍDEO, leído en el servidor.

Rama render-y-cotizador (04-11-2026). En la primera prueba completa en el VPS
un vídeo de 30 s tardó 626 s en montarse y 671 s en las imágenes, y el
cotizador prometió 0,636 $ cuando se gastaron 0,379 $. Antes de tocar nada se
mide, y esto es lo que mide. SOLO LEE: no lanza nada, no paga nada, no escribe.

    python3 herramientas/diagnostico_velocidad.py               # el último vídeo montado
    python3 herramientas/diagnostico_velocidad.py <id del vídeo>
    python3 herramientas/diagnostico_velocidad.py --entorno /opt/as-video-studio/datos/entorno

Lo que dice:

  1. LA MÁQUINA: núcleos, memoria, carga, `ESTUDIO_LOTES` (el del fichero del
     entorno y el de esta consola) y cuántos procesos usaría el montaje.
  2. LOS TIEMPOS del vídeo: imágenes, capas y montaje, y en el montaje cada
     fase (arrancar navegadores, pintar y capturar, transiciones, codificar,
     sonido, montar, logo). Las fases solo salen en montajes hechos con esta
     rama o después.
  3. EL DINERO: por tanda, lo prometido antes de pulsar frente a lo gastado,
     cuántas imágenes se pagaron, lo que costó cada una y con cuántos tokens de
     entrada (las referencias adjuntas), y el precio con el que cotiza hoy.

Del fichero del entorno solo se leen las rutas que hacen falta y
`ESTUDIO_LOTES`: nada de claves.
"""
import argparse
import json
import os
import statistics
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTORNO_POR_DEFECTO = "/opt/as-video-studio/datos/entorno"
#: Lo único que se lee del entorno. Nada de secretos.
CLAVES_ENTORNO = ("ESTUDIO_LOTES", "ESTUDIO_ESTADISTICAS", "ESTUDIO_COSTE_GLOBAL",
                  "ESTUDIO_PROYECTOS", "ESTUDIO_TARIFAS")
MAX_LOTES = 16                     # el de pasos/p8_render.py
NOMBRE_TANDAS = "tandas_coste.jsonl"


def leer_entorno(ruta, claves=CLAVES_ENTORNO):
    """{clave: valor} de las claves pedidas del fichero del entorno. -> dict"""
    salida = {}
    try:
        with open(ruta, encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                if clave in claves:
                    salida[clave] = valor.strip().strip('"').strip("'")
    except OSError:
        return {}
    return salida


def lotes_que_usaria(nucleos, lotes_entorno, planos=999):
    """Lo que elige `p8_render._cuantos_lotes` con ese entorno. -> (n, por qué)"""
    try:
        forzado = int(lotes_entorno or 0)
    except ValueError:
        forzado = 0
    if forzado > 0:
        return max(1, min(forzado, MAX_LOTES, planos)), f"ESTUDIO_LOTES={forzado}"
    n = max(1, min(MAX_LOTES, (nucleos or 2) // 2, planos))
    return n, "sin ESTUDIO_LOTES: la mitad de los núcleos"


def maquina(entorno):
    nucleos = os.cpu_count() or 0
    memoria = ""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            datos = dict(l.split(":", 1) for l in fh if ":" in l)
        total = int(datos["MemTotal"].split()[0]) / 1024 / 1024
        libre = int(datos.get("MemAvailable", "0 kB").split()[0]) / 1024 / 1024
        memoria = f"{total:.1f} GB ({libre:.1f} GB libres ahora)"
    except (OSError, KeyError, ValueError):
        memoria = "no se puede leer"
    carga = ""
    try:
        with open("/proc/loadavg", encoding="utf-8") as fh:
            carga = " ".join(fh.read().split()[:3])
    except OSError:
        carga = "no se puede leer"
    n, porque = lotes_que_usaria(nucleos, entorno.get("ESTUDIO_LOTES"))
    return {"nucleos": nucleos, "memoria": memoria, "carga": carga,
            "lotes_entorno": entorno.get("ESTUDIO_LOTES", ""),
            "lotes_consola": os.environ.get("ESTUDIO_LOTES", ""),
            "lotes": n, "lotes_porque": porque}


def leer_estadisticas(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            documento = json.load(fh)
    except (OSError, ValueError):
        return {}
    return documento.get("pasos") or {} if isinstance(documento, dict) else {}


def leer_jsonl(ruta, max_bytes=40_000_000):
    salida = []
    try:
        tam = os.path.getsize(ruta)
        with open(ruta, "rb") as fh:
            if tam > max_bytes:
                fh.seek(tam - max_bytes)
            texto = fh.read().decode("utf-8", "replace")
    except OSError:
        return []
    lineas = texto.splitlines()
    if os.path.getsize(ruta) > max_bytes:
        lineas = lineas[1:]
    for linea in lineas:
        try:
            r = json.loads(linea)
        except ValueError:
            continue
        if isinstance(r, dict):
            salida.append(r)
    return salida


def ultimo_montado(pasos):
    """El id del último vídeo con un montaje apuntado. -> str"""
    hechos = [r for r in pasos.get("render") or [] if r.get("proyecto")]
    return hechos[-1]["proyecto"] if hechos else ""


def tiempos_del_video(pasos, pid):
    """{paso: [registros]} de las imágenes, las capas y el montaje del vídeo."""
    return {paso: [r for r in pasos.get(paso) or [] if r.get("proyecto") == pid]
            for paso in ("assets", "callouts", "render")}


def costes_del_video(registros, pid):
    """Lo cobrado por imágenes y voz de ese vídeo, con lo que llevó cada imagen."""
    imagenes, voz = [], 0.0
    for r in registros:
        if r.get("proyecto") != pid or r.get("usd") is None:
            continue
        if r.get("proveedor") == "openai" and r.get("operacion") == "imagen":
            detalle = r.get("detalle") or {}
            refs = detalle.get("refs")
            refs = len(refs) if isinstance(refs, (list, tuple)) else int(refs or 0) \
                if isinstance(refs, (int, float)) else 0
            coste = detalle.get("coste") if isinstance(detalle.get("coste"), dict) else {}
            imagenes.append({"refs": refs, "via": coste.get("via") or "",
                             "entrada_texto": int(coste.get("entrada_texto") or 0),
                             "entrada_imagen": int(coste.get("entrada_imagen") or 0),"unidad": r.get("unidad") or "", "usd": float(r["usd"]),
                             "entrada": int(((r.get("tokens") or {}).get("entrada")) or 0),
                             "calidad": detalle.get("calidad") or "", "modo": detalle.get("modo") or "",
                             "momento": r.get("momento") or ""})
        elif r.get("proveedor") in ("cartesia", "elevenlabs") or r.get("operacion") in ("tts", "voz"):
            voz += float(r["usd"])
    return imagenes, round(voz, 4)


def tandas_del_video(ruta_tandas, imagenes):
    """Cada tanda: lo prometido frente a lo gastado en imágenes mientras corría."""
    fichas = {}
    for r in leer_jsonl(ruta_tandas):
        fichas.setdefault(r.get("marca"), {}).update(r)
    salida = []
    for f in fichas.values():
        inicio, fin = f.get("inicio") or f.get("lanzada"), f.get("fin")
        if not inicio:
            continue
        dentro = [i for i in imagenes if i["momento"] >= inicio and (not fin or i["momento"] <= fin)]
        salida.append({"tandas": f.get("tandas") or [], "lanzada": f.get("lanzada") or inicio,
                       "prometido_usd": f.get("prometido_usd"),
                       "prometido_imagenes": f.get("prometido_imagenes"),
                       "imagenes": len(dentro), "gastado_imagenes_usd": round(sum(i["usd"] for i in dentro), 4)})
    return sorted(salida, key=lambda x: x["lanzada"])


def _seg(x):
    try:
        return f"{float(x):.0f} s"
    except (TypeError, ValueError):
        return "—"


NOMBRES_FASE = {"preparar": "preparar (leer el plan, sembrar la carpeta)",
                "planos": "planos (todos los procesos, de reloj)",
                "sonido": "sonido (efectos y música)", "montar": "montar (unir clips y audio)",
                "logo": "logo"}
NOMBRES_POR_PLANO = {"arrancar": "arrancar navegadores", "abrir": "abrir la página de cada plano",
                     "pintar_y_capturar": "pintar y capturar fotogramas",
                     "transicion": "transiciones", "codificar": "codificar clips"}


def informe(maq, pid, tiempos, imagenes, voz, tandas, precios):
    l = ["", "=" * 70, "1. LA MÁQUINA", "=" * 70,
         f"  núcleos:        {maq['nucleos']}",
         f"  memoria:        {maq['memoria']}",
         f"  carga (1/5/15): {maq['carga']}",
         f"  ESTUDIO_LOTES en el entorno: {maq['lotes_entorno'] or '(no está)'}"
         + (f" · en esta consola: {maq['lotes_consola']}" if maq['lotes_consola'] else ""),
         f"  el montaje usa {maq['lotes']} proceso(s) a la vez ({maq['lotes_porque']})"]
    if maq["nucleos"] and maq["lotes"] < maq["nucleos"]:
        l.append(f"  ⚠ quedan {maq['nucleos'] - maq['lotes']} núcleo(s) parados mientras se monta")
    l += ["", "=" * 70, f"2. LOS TIEMPOS DE «{pid}»", "=" * 70]
    for paso, nombre in (("assets", "imágenes"), ("callouts", "capas y movimiento"), ("render", "montaje")):
        regs = tiempos.get(paso) or []
        if not regs:
            l.append(f"  {nombre}: sin registros")
            continue
        for r in regs[-3:]:
            l.append(f"  {nombre}: {_seg(r.get('segundos'))} · {r.get('tamano')} unidad(es) · {r.get('fecha')}")
            det = r.get("detalle") or {}
            if paso == "render":
                if det.get("duracion_s"):
                    l.append(f"      vídeo de {det['duracion_s']} s a {det.get('fps')} fps "
                             f"{'x'.join(str(x) for x in det.get('resolucion') or [])}, "
                             f"{det.get('planos', '?')} planos en {det.get('procesos', '?')} proceso(s)")
                fases = det.get("fases") or {}
                if not fases:
                    l.append("      (sin fases: este montaje es de antes de esta rama)")
                for clave, texto in NOMBRES_FASE.items():
                    if clave in fases:
                        l.append(f"      · {texto}: {_seg(fases[clave])}")
                por_plano = fases.get("planos_por_plano") or {}
                if por_plano:
                    total = sum(float(v) for v in por_plano.values()) or 1.0
                    l.append("      dentro de los planos (suma de todos los procesos):")
                    for clave, texto in NOMBRES_POR_PLANO.items():
                        if clave in por_plano:
                            l.append(f"        - {texto}: {_seg(por_plano[clave])} "
                                     f"({100 * float(por_plano[clave]) / total:.0f} %)")
            elif paso == "assets" and r.get("tamano"):
                l.append(f"      ≈ {float(r.get('segundos') or 0) / max(1, int(r['tamano'])):.0f} s por unidad")
    l += ["", "=" * 70, "3. EL DINERO", "=" * 70]
    if imagenes:
        usd = [i["usd"] for i in imagenes]
        entrada = [i["entrada"] for i in imagenes if i["entrada"]]
        planos = [i for i in imagenes if i["unidad"].startswith("escena:")]
        l.append(f"  imágenes cobradas: {len(imagenes)} ({len(planos)} de plano) · {sum(usd):.3f} $ · "
                 f"mediana {statistics.median(usd):.4f} $ por imagen")
        if entrada:
            l.append(f"  tokens de entrada por imagen (las referencias): mediana {statistics.median(entrada):.0f}"
                     f" · el cotizador sin muestras supone 5114")
        refs = [i["refs"] for i in imagenes if i["refs"]]
        if refs:
            l.append(f"  referencias adjuntas por imagen: mediana {statistics.median(refs):.0f}"
                     f" (el cotizador sin muestras supone unas 7)")
        texto = [i["entrada_texto"] for i in imagenes if i["entrada_texto"]]
        if texto:
            l.append(f"  de esa entrada, texto (más barato): mediana {statistics.median(texto):.0f} tokens")
        sin_tokens = [i for i in imagenes if i["via"] and i["via"] != "tokens"]
        if sin_tokens:
            l.append(f"  ⚠ {len(sin_tokens)} imagen(es) tarifadas sin tokens (la API no los devolvió)")
        calidades = sorted({f"{i['calidad']}|{i['modo'] or '?'}" for i in imagenes})
        l.append(f"  calidad|modo: {', '.join(calidades)}")
    else:
        l.append("  sin imágenes cobradas de este vídeo en el registro global")
    if voz:
        l.append(f"  voz: {voz:.4f} $")
    for t in tandas:
        prom = t.get("prometido_usd")
        l.append(f"  tanda {'+'.join(t['tandas']) or '?'} ({t['lanzada'][:16]}): prometido "
                 f"{prom if prom is not None else '—'} $ por {t.get('prometido_imagenes', '—')} imagen(es) · "
                 f"gastado en imágenes {t['gastado_imagenes_usd']:.3f} $ por {t['imagenes']}")
    for p in precios:
        l.append(f"  hoy cotiza {p['calidad']}{' ' + p['modo'] if p.get('modo') else ''}: "
                 f"{p['usd']:.4f} $ por imagen — {p['fuente']}")
    return "\n".join(l)


def precios_de_hoy():
    """El precio con el que cotiza hoy el Studio, si se puede importar."""
    try:
        sys.path.insert(0, os.path.join(RAIZ, "pasos"))
        import ajustes                                       # noqa: PLC0415
    except Exception:                                        # noqa: BLE001
        return []
    salida = []
    for calidad in ("low", "medium"):
        for modo in (None, "foto"):
            try:
                p = ajustes.precio_por_imagen(calidad, modo=modo)
            except Exception:                                # noqa: BLE001
                continue
            if modo and p.get("modo") != modo:
                # sin muestras de foto en esa calidad cae al precio general, que
                # ya sale en la línea de arriba: no se repite
                continue
            salida.append({"calidad": calidad, "modo": p.get("modo") or "", "usd": float(p["usd"]),
                           "fuente": p.get("fuente") or ""})
    return salida


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dónde se va el tiempo y el dinero de un vídeo (solo lee)")
    ap.add_argument("video", nargs="?", default="", help="id del vídeo (por defecto, el último montado)")
    ap.add_argument("--entorno", default=ENTORNO_POR_DEFECTO)
    args = ap.parse_args(argv)
    entorno = leer_entorno(args.entorno)
    for clave, valor in entorno.items():
        if clave != "ESTUDIO_LOTES":
            os.environ.setdefault(clave, valor)       # para que ajustes lea el mismo registro
    ruta_estadisticas = os.environ.get("ESTUDIO_ESTADISTICAS") or os.path.join(RAIZ, "datos", "estadisticas.json")
    ruta_coste = os.environ.get("ESTUDIO_COSTE_GLOBAL") or os.path.join(RAIZ, "datos", "coste_global.jsonl")
    raiz_proyectos = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")
    pasos = leer_estadisticas(ruta_estadisticas)
    pid = args.video or ultimo_montado(pasos)
    maq = maquina(entorno)
    if not pid:
        print(informe(maq, "(ninguno)", {}, [], 0.0, [], precios_de_hoy()))
        print("\nNo hay ningún montaje apuntado todavía.")
        return 0
    imagenes, voz = costes_del_video(leer_jsonl(ruta_coste), pid)
    tandas = tandas_del_video(os.path.join(raiz_proyectos, pid, NOMBRE_TANDAS), imagenes)
    print(informe(maq, pid, tiempos_del_video(pasos, pid), imagenes, voz, tandas, precios_de_hoy()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

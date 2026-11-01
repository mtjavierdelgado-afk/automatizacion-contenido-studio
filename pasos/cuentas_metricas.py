"""LAS CIFRAS DE UNA CUENTA AJENA, RELATIVAS A ELLA MISMA (rama cuentas-gustan-2).

Pedido del dueño (01-11-2026): comparar vídeos y cuentas sin que una cuenta
grande mande solo por su tamaño. Todo se calcula aquí, sin Claude y sin red,
sobre lo que ya se leyó; no se guarda: se recalcula al abrir la cuenta, así
que las cuentas leídas antes de esta rama también lo tienen.

    metricas(datos)          -> {mediana_vistas, mediana_mg100, mediana_com100,
                                 con_duracion, total, dudosos, rangos, videos}
    rangos_de(videos)        vistas por rango de duración (sin los dudosos)
    TIPOS / nombre_tipo(t)   Reel, Short, Carrusel…

LAS MEDIDAS
-----------
- `rel`: las vistas de un vídeo frente a la MEDIANA de su cuenta (×2,0 = el
  doble de lo normal en esa cuenta). La mediana, y no la media, para que un
  vídeo viral no mueva la vara de todos los demás.
- `mg100` / `com100`: «me gusta» y comentarios por cada 100 vistas.

LOS DUDOSOS (se ven, pero no cuentan como referencia)
------------------------------------------------------
- Colaboración: la fuente dice que tiene coautores, o el texto lo dice
  («colab», «collab», «en colaboración», «ft.», «feat.», «con @alguien» al
  empezar). Sus vistas son en parte de otra cuenta.
- Posible promoción: 3 veces o más las vistas de la mediana con menos de un
  tercio de los «me gusta» por cada 100 vistas habituales de la cuenta. Es lo
  que deja un anuncio pagado: mucha gente lo ve y casi nadie reacciona.
"""
import re
import statistics

#: Las clases de publicación (las mismas claves que `lectores.TIPOS`).
TIPOS = {"reel": "Reel", "publicacion": "Publicación", "carrusel": "Carrusel",
         "video": "Vídeo", "short": "Short", "fotos": "Fotos"}

#: (desde, hasta, nombre) en segundos; `hasta` None = sin tope.
RANGOS = ((0, 15, "menos de 15 s"), (15, 30, "15–30 s"), (30, 60, "30–60 s"),
          (60, 120, "1–2 min"), (120, None, "más de 2 min"))

#: Cuántos vídeos con duración hacen falta para sugerir una (decisión del dueño, 01-11).
MIN_CON_DURACION = 8
VECES_PROMOCION = 3.0
FRACCION_PROMOCION = 1 / 3

_RE_COLAB = re.compile(r"\b(colab|collab|colaboraci[oó]n|ft\.|feat\.)", re.I)
_RE_CON_ARROBA = re.compile(r"^\s*(con|with|junto a)\s+@[\w.]+", re.I)


def nombre_tipo(tipo):
    return TIPOS.get(str(tipo or ""), "")


def _num(valor):
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def mediana(valores):
    valores = [v for v in valores if _num(v) is not None]
    return float(statistics.median(valores)) if valores else None


def _por_100(parte, vistas):
    parte, vistas = _num(parte), _num(vistas)
    if parte is None or not vistas:
        return None
    return round(parte * 100.0 / vistas, 2)


def _colaboracion(v):
    if v.get("coautores"):
        return "colaboración con @" + ", @".join(v["coautores"][:3])
    texto = str(v.get("texto") or "")
    if _RE_COLAB.search(texto) or _RE_CON_ARROBA.search(texto):
        return "colaboración (lo dice su texto)"
    return ""


def _rango(duracion):
    d = _num(duracion)
    if d is None or d <= 0:
        return None
    for i, (desde, hasta, _n) in enumerate(RANGOS):
        if d >= desde and (hasta is None or d < hasta):
            return i
    return None


def rangos_de(videos):
    """[{rango, desde, hasta, videos, mediana_vistas, mediana_rel}] de los
    vídeos que tienen duración y no son dudosos (necesita `rel`)."""
    cajas = [[] for _ in RANGOS]
    for v in videos:
        if v.get("dudoso"):
            continue
        i = _rango(v.get("duracion_s"))
        if i is not None:
            cajas[i].append(v)
    salida = []
    for (desde, hasta, nombre), caja in zip(RANGOS, cajas):
        salida.append({"rango": nombre, "desde": desde, "hasta": hasta, "videos": len(caja),
                       "mediana_vistas": mediana([v.get("vistas") for v in caja]),
                       "mediana_rel": mediana([v.get("rel") for v in caja])})
    return salida


def mejor_rango(rangos, minimo=MIN_CON_DURACION):
    """El rango con más vistas relativas, si en total hay al menos `minimo`
    vídeos con duración y ese rango tiene 2 o más. -> {rango, videos} o None."""
    total = sum(r["videos"] for r in rangos)
    if total < minimo:
        return None
    candidatos = [r for r in rangos if r["videos"] >= 2 and r["mediana_rel"] is not None]
    if not candidatos:
        return None
    r = max(candidatos, key=lambda x: (x["mediana_rel"], x["videos"]))
    return {"rango": r["rango"], "videos": r["videos"], "total": total,
            "mediana_rel": round(r["mediana_rel"], 2)}


def metricas(datos):
    """Las cifras de cada vídeo y de la cuenta. No cambia `datos`: devuelve
    una lista nueva de vídeos con `n` (su número en la lista), `rel`, `mg100`,
    `com100`, `tipo_nombre`, `dudoso` y `motivo`."""
    crudos = [v for v in (datos or {}).get("videos") or [] if isinstance(v, dict)]
    med_vistas = mediana([v.get("vistas") for v in crudos])
    videos = []
    for i, v in enumerate(crudos, 1):
        vistas = _num(v.get("vistas"))
        videos.append({**v, "n": i,
                       "rel": round(vistas / med_vistas, 2) if vistas is not None and med_vistas else None,
                       "mg100": _por_100(v.get("me_gusta"), vistas),
                       "com100": _por_100(v.get("comentarios"), vistas),
                       "tipo_nombre": nombre_tipo(v.get("tipo")),
                       "dudoso": False, "motivo": ""})
    # la vara de «me gusta» se mide sin los que ya son de colaboración
    for v in videos:
        colab = _colaboracion(v)
        if colab:
            v["dudoso"], v["motivo"] = True, colab
    med_mg = mediana([v["mg100"] for v in videos if not v["dudoso"]])
    for v in videos:
        if v["dudoso"] or v["rel"] is None or v["mg100"] is None or not med_mg:
            continue
        if v["rel"] >= VECES_PROMOCION and v["mg100"] < med_mg * FRACCION_PROMOCION:
            v["dudoso"] = True
            v["motivo"] = (f"posible promoción: ×{cifra(v['rel'], 1)} las vistas normales con pocos «me gusta» "
                           f"({cifra(v['mg100'], 1)} por 100 vistas; lo normal aquí es {cifra(med_mg, 1)})")
    validos = [v for v in videos if not v["dudoso"]]
    rangos = rangos_de(videos)
    return {"mediana_vistas": med_vistas,
            "mediana_mg100": mediana([v["mg100"] for v in validos]),
            "mediana_com100": mediana([v["com100"] for v in validos]),
            "con_duracion": sum(1 for v in videos if _rango(v.get("duracion_s")) is not None),
            "total": len(videos), "dudosos": sum(1 for v in videos if v["dudoso"]),
            "rangos": rangos, "mejor_rango": mejor_rango(rangos), "videos": videos}


def cifra(valor, decimales=1):
    """1.234,5 al estilo de la pantalla (para los textos que lee Claude)."""
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}" if decimales else f"{int(round(valor)):,}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def linea_video(v, usuario, largo_texto=200):
    """Una línea compacta de un vídeo para Claude, con su referencia @usuario#n."""
    partes = [f"@{usuario}#{v['n']}"]
    if v.get("vistas") is not None:
        partes.append(f"{cifra(v['vistas'], 0)} vistas")
    if v.get("rel") is not None:
        partes.append(f"×{cifra(v['rel'], 1)} su mediana")
    if v.get("mg100") is not None:
        partes.append(f"{cifra(v['mg100'], 1)} ♥/100")
    if v.get("com100") is not None:
        partes.append(f"{cifra(v['com100'], 2)} coment./100")
    if v.get("tipo_nombre"):
        partes.append(v["tipo_nombre"])
    if _num(v.get("duracion_s")):
        partes.append(f"{int(v['duracion_s'])} s")
    if v.get("fecha"):
        partes.append(str(v["fecha"])[:10])
    if v.get("dudoso"):
        partes.append(f"DUDOSO, NO LO USES DE REFERENCIA ({v['motivo']})")
    texto = " ".join(str(v.get("texto") or "").split())[:largo_texto] or "(sin texto)"
    linea = " · ".join(partes) + f"\n   Texto: {texto}"
    if v.get("transcripcion"):
        linea += f"\n   Lo que dice: {' '.join(str(v['transcripcion']).split())[:300]}"
    return linea


def cabecera_cuenta(datos, m):
    """La línea de resumen de una cuenta para Claude."""
    partes = [f"@{datos.get('usuario')} ({datos.get('red')})"]
    if datos.get("seguidores"):
        partes.append(f"{cifra(datos['seguidores'], 0)} seguidores")
    partes.append(f"{m['total']} vídeos leídos el {str(datos.get('traida') or '')[:10]}")
    if m["mediana_vistas"] is not None:
        partes.append(f"mediana {cifra(m['mediana_vistas'], 0)} vistas")
    if m["mediana_mg100"] is not None:
        partes.append(f"{cifra(m['mediana_mg100'], 1)} ♥/100 de mediana")
    if m["dudosos"]:
        partes.append(f"{m['dudosos']} dudosos")
    partes.append(f"{m['con_duracion']} de {m['total']} con duración")
    return "CUENTA " + " · ".join(partes)


def texto_rangos(m):
    filas = [f"- {r['rango']}: {r['videos']} vídeos, ×{cifra(r['mediana_rel'], 1)} su mediana"
             for r in m["rangos"] if r["videos"]]
    if not filas:
        return "Vistas por duración: sin vídeos con duración."
    return (f"Vistas por duración ({m['con_duracion']} de {m['total']} vídeos con ese dato):\n"
            + "\n".join(filas))

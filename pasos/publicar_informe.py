"""LO QUE SE LEE DE LOS RESULTADOS (rama `publicar-mas`, 18-10-2026).

Tres lecturas de lo publicado, todas con las cifras YA guardadas en cada envio
(no preguntan a Upload-Post ni gastan consultas):

- `palabras_y_ganchos`: qué palabras clave y qué primeras líneas fueron mejor.
- `horarios`: qué día y franja horaria fue mejor en cada red, con la hora que
  se propone en «Cuándo». Con pocos datos no se inventa nada: se dice que faltan
  y se da un punto de partida GENERAL, marcado como tal.
- `informe_mensual`: el mes de un proyecto, para enseñárselo al cliente
  (imprimible y con un resumen para copiar).

La palabra clave y la primera línea son las del momento de publicar (se apuntan
en el envío desde publicar-mas); en los envíos de antes se usa la de ahora.
"""
from __future__ import annotations

import datetime as dt
import statistics

import publicar as P            # noqa: E402  (pasos/ en sys.path, como en app.py)

#: Las franjas del día, en hora de Lima. (desde, hasta, nombre)
FRANJAS = ((6, 9, "6–9 h"), (9, 12, "9–12 h"), (12, 15, "12–15 h"), (15, 18, "15–18 h"),
           (18, 21, "18–21 h"), (21, 24, "21–24 h"), (0, 6, "0–6 h"))
#: Con menos publicaciones con cifras en una red no se sugiere nada propio.
MIN_POSTS_RED = 6
#: Un hueco (día y franja) cuenta con al menos estas.
MIN_POSTS_HUECO = 2
#: Para la interacción y los ganchos «por proporción», como en lo_que_funciono.
MIN_VISTAS = P.MIN_VISTAS_PROPORCION
SIN_PALABRA = "(sin palabra clave)"

#: Un punto de partida GENERAL por red, para cuando aún no hay datos propios.
#: No sale de las cifras de nadie de aquí y la pantalla lo dice.
GENERAL = {
    "tiktok": ((0, 1, 2, 3, 4), "19:00", "entre semana, de 19 a 21 h"),
    "instagram": ((0, 1, 2, 3, 4), "18:30", "entre semana, de 18 a 21 h"),
    "youtube": ((3, 4, 5, 6), "17:30", "de jueves a domingo, de 17 a 20 h"),
    "facebook": ((0, 1, 2, 3, 4), "12:30", "a mediodía (12–14 h) o por la noche (19–21 h)"),
    "linkedin": ((1, 2, 3), "08:30", "de martes a jueves, de 8 a 10 h"),
    "x": ((0, 1, 2, 3, 4), "12:30", "a mediodía, entre semana"),
    "threads": ((0, 1, 2, 3, 4), "19:30", "por la noche, entre semana"),
    "pinterest": ((4, 5, 6), "20:30", "por la noche y el fin de semana"),
    "bluesky": ((0, 1, 2, 3, 4), "10:00", "por la mañana, entre semana"),
    "discord": ((0, 1, 2, 3, 4), "19:00", "cuando la comunidad está conectada (la tarde-noche)"),
    "telegram": ((0, 1, 2, 3, 4), "19:00", "por la tarde-noche"),
    "mastodon": ((0, 1, 2, 3, 4), "10:00", "por la mañana, entre semana"),
    "google_business": ((0, 1, 2, 3, 4), "09:00", "a primera hora, cuando se busca el negocio"),
}


def _franja(hora):
    for i, (desde, hasta, _n) in enumerate(FRANJAS):
        if desde <= hora < hasta:
            return i
    return len(FRANJAS) - 1


def _con_cifras(raiz, videos, cid, desde, hasta=None):
    """[(video, envio, momento, metricas)] de lo publicado con vistas."""
    salida = []
    for v, e in P._publicados(raiz, P._de_proyecto(videos, cid), desde, hasta):
        m = e.get("metricas") or {}
        if isinstance(m.get("vistas"), (int, float)) and not isinstance(m.get("vistas"), bool):
            salida.append((v, e, P._leer_momento(e.get("cuando")), m))
    return salida


def _proxima(dia, hora, ahora=None):
    """La siguiente vez que sea ese día de la semana a esa hora (Lima), ISO."""
    ahora = ahora or P.ahora_lima()
    hh, mm = (int(x) for x in hora.split(":"))
    momento = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
    momento += dt.timedelta(days=(dia - ahora.weekday()) % 7)
    if momento <= ahora + dt.timedelta(minutes=15):
        momento += dt.timedelta(days=7)
    return momento.strftime("%Y-%m-%dT%H:%M")


def _interaccion_de(filas):
    """(me gusta + comentarios + compartidos + guardados) / vistas, sumados."""
    vistas = sum(m.get("vistas") or 0 for m in filas if P._interaccion(m) is not None)
    gestos = sum(P._interaccion(m) * (m.get("vistas") or 0) for m in filas
                 if P._interaccion(m) is not None)
    return round(gestos / vistas, 4) if vistas else None


# ------------------------------------------------------- palabras y ganchos

def palabras_y_ganchos(raiz, videos, cid=None, dias=90, cuantos=10, desde=None, hasta=None):
    """-> {"palabras": [...], "ganchos": [...], "dias"}"""
    desde = desde or (P.ahora_lima() - dt.timedelta(days=dias))
    textos, ajustes = {}, {}
    grupos = {}
    ganchos = []
    for v, e, momento, m in _con_cifras(raiz, videos, cid, desde, hasta):
        if v["pid"] not in textos:
            textos[v["pid"]] = P._leer_video(raiz, v["pid"])
        datos = textos[v["pid"]]
        cliente = v.get("cliente") or ""
        if cliente not in ajustes:
            ajustes[cliente] = P.ajustes_de(raiz, cliente)
        palabra = str(e.get("palabra") if "palabra" in e
                      else P.SEO.palabra_del_video(datos, ajustes[cliente])).strip()
        gancho = e.get("primera_linea") if "primera_linea" in e else P.primera_linea(
            (datos["textos"].get(e["red"]) or {}).get("descripcion"))
        clave = palabra.lower() or SIN_PALABRA
        g = grupos.setdefault(clave, {"palabra": palabra or SIN_PALABRA, "posts": 0, "vistas": 0,
                                      "_lista": [], "_metricas": [], "redes": set(),
                                      "mejor": None})
        g["posts"] += 1
        g["vistas"] += int(m["vistas"])
        g["_lista"].append(m["vistas"])
        g["_metricas"].append(m)
        g["redes"].add(e["red"])
        if g["mejor"] is None or m["vistas"] > g["mejor"]["vistas"]:
            g["mejor"] = {"pid": v["pid"], "nombre": v.get("nombre") or v["pid"],
                          "red": e["red"], "vistas": int(m["vistas"])}
        if gancho:
            ganchos.append({"gancho": gancho, "pid": v["pid"], "nombre": v.get("nombre") or v["pid"],
                            "red": e["red"], "palabra": palabra, "vistas": int(m["vistas"]),
                            "interaccion": P._interaccion(m) if m["vistas"] >= MIN_VISTAS else None,
                            "cuando": P._iso_lima(momento) if momento else "",
                            "url": e.get("url") or ""})
    palabras = []
    for g in grupos.values():
        lista = g.pop("_lista")
        metricas = g.pop("_metricas")
        g["redes"] = [r for r in P.REDES if r in g["redes"]]
        g["mediana"] = int(statistics.median(lista)) if lista else 0
        con_vistas = [x for x in metricas if (x.get("vistas") or 0) >= MIN_VISTAS]
        g["interaccion"] = _interaccion_de(con_vistas)
        palabras.append(g)
    # por la mediana: un post viral no hace buena a una palabra con diez flojos
    palabras.sort(key=lambda g: (g["palabra"] == SIN_PALABRA, -g["mediana"], -g["posts"]))
    # la misma primera línea en varias redes es UN gancho: se queda la que más
    # vistas trajo y se apunta en cuántas salió
    ganchos.sort(key=lambda x: -x["vistas"])
    unicos = {}
    for g in ganchos:
        clave_g = " ".join(P.SEO.sin_tildes(g["gancho"]).lower().split())
        if clave_g in unicos:
            primero = unicos[clave_g]
            primero["veces"] += 1
            primero["vistas_total"] += g["vistas"]
            if g["red"] not in primero["redes"]:
                primero["redes"].append(g["red"])
            continue
        unicos[clave_g] = dict(g, veces=1, vistas_total=g["vistas"], redes=[g["red"]])
    ganchos = list(unicos.values())
    return {"dias": dias, "desde": desde.strftime("%Y-%m-%d"),
            "palabras": palabras[:cuantos * 2], "ganchos": ganchos[:cuantos],
            "minimo_vistas": MIN_VISTAS}


# ------------------------------------------------------------------ horarios

def horarios(raiz, videos, cid=None, dias=180, ahora=None):
    """Por red: los mejores huecos (día y franja) con lo propio, o el punto de
    partida general si aún no hay bastante. -> {"redes": {red: {...}}, "todas"}"""
    ahora = ahora or P.ahora_lima()
    desde = ahora - dt.timedelta(days=dias)
    por_red = {}
    for _v, e, momento, m in _con_cifras(raiz, videos, cid, desde):
        if momento:
            por_red.setdefault(e["red"], []).append((momento, float(m["vistas"])))
    salida, todas = {}, {}
    for red in P.REDES:
        filas = por_red.get(red) or []
        dias_g, hora_g, texto_g = GENERAL[red]
        general = {"texto": texto_g, "hora": hora_g, "dias": list(dias_g),
                   "proxima": min(_proxima(d, hora_g, ahora) for d in dias_g)}
        ficha = {"posts": len(filas), "propios": False, "mejores": [], "general": general,
                 "faltan": max(0, MIN_POSTS_RED - len(filas))}
        if len(filas) >= MIN_POSTS_RED:
            mediana_red = statistics.median(v for _m, v in filas) or 1.0
            huecos = {}
            for momento, vistas in filas:
                clave = (momento.weekday(), _franja(momento.hour))
                huecos.setdefault(clave, []).append((momento, vistas))
                # para «todas»: cada post medido contra lo normal de su red
                todas.setdefault(clave, []).append((momento, vistas / mediana_red))
            ficha["mejores"] = _mejores(huecos, mediana_red, ahora)
            ficha["propios"] = bool(ficha["mejores"])
        salida[red] = ficha
    return {"dias": dias, "redes": salida, "todas": _mejores(todas, 1.0, ahora),
            "minimo": MIN_POSTS_RED, "minimo_hueco": MIN_POSTS_HUECO,
            "franjas": [n for _a, _b, n in FRANJAS]}


def _mejores(huecos, referencia, ahora, cuantos=3):
    filas = []
    for (dia, franja), lista in huecos.items():
        if len(lista) < MIN_POSTS_HUECO:
            continue
        mediana = statistics.median(v for _m, v in lista)
        horas = sorted(m.hour * 60 + m.minute for m, _v in lista)
        minuto = horas[len(horas) // 2]
        hora = f"{minuto // 60:02d}:{(minuto % 60) // 30 * 30:02d}"
        filas.append({"dia": dia, "dia_nombre": P._DIAS_SEMANA[dia],
                      "franja": FRANJAS[franja][2], "posts": len(lista),
                      "mediana": round(mediana, 2) if referencia == 1.0 else int(mediana),
                      "indice": round(mediana / referencia, 2) if referencia else None,
                      "hora": hora, "proxima": _proxima(dia, hora, ahora)})
    filas.sort(key=lambda f: (-(f["indice"] or 0), -f["posts"]))
    # solo los que van por ENCIMA de lo normal: un «mejor» por debajo no ayuda
    return [f for f in filas if (f["indice"] or 0) > 1.0][:cuantos]


# ------------------------------------------------------------ informe del mes

def _limites_mes(mes):
    try:
        anio, num = (int(x) for x in str(mes).split("-"))
        inicio = dt.datetime(anio, num, 1, tzinfo=P._zona())
    except (ValueError, TypeError):
        raise P.ErrorPublicar("el mes va como 2026-10", 400) from None
    fin = (inicio + dt.timedelta(days=32)).replace(day=1)
    return inicio, fin


def meses_con_publicaciones(raiz, videos, cid):
    meses = set()
    for _v, e in P._publicados(raiz, P._de_proyecto(videos, cid),
                               P.ahora_lima() - dt.timedelta(days=730)):
        momento = P._leer_momento(e.get("cuando"))
        if momento:
            meses.add(momento.strftime("%Y-%m"))
    meses.add(P.ahora_lima().strftime("%Y-%m"))
    return sorted(meses, reverse=True)


def informe_mensual(raiz, videos, cid, mes=None, nombre=""):
    """El mes de un proyecto. -> {mes, total, anterior, por_red, mejores,
    palabras, ganchos, horario, seguidores, resumen (texto para copiar)}"""
    ahora = P.ahora_lima()
    mes = mes or ahora.strftime("%Y-%m")
    inicio, fin = _limites_mes(mes)
    antes, _ = _limites_mes((inicio - dt.timedelta(days=1)).strftime("%Y-%m"))
    # EL MES EN CURSO se compara con el MISMO TRAMO del anterior (el día 5, con
    # el 1 al 5 del mes pasado): contra el mes entero salía «−85 %» cada
    # principio de mes, y eso se copia al cliente
    en_curso = inicio <= ahora < fin
    tope_antes = inicio
    if en_curso:
        tope_antes = min(inicio, antes + (ahora - inicio))
    propios = P._de_proyecto(videos, cid)
    pares = P._publicados(raiz, propios, inicio, fin)
    previos = P._publicados(raiz, propios, antes, tope_antes)
    total = P._totales(pares)
    anterior = P._totales(previos)
    por_red = {}
    for _v, e in pares:
        fila = por_red.setdefault(e["red"], {"posts": 0})
        fila["posts"] += 1
        P._suma(fila, e.get("metricas") or {})
    for fila in por_red.values():
        P._medias(fila)
    por_red = {r: por_red[r] for r in P.REDES if r in por_red}
    mejores = []
    for v, e in pares:
        m = e.get("metricas") or {}
        if isinstance(m.get("vistas"), (int, float)):
            mejores.append({"pid": v["pid"], "nombre": v.get("nombre") or v["pid"], "red": e["red"],
                            "cuando": e.get("cuando") or "", "url": e.get("url") or "",
                            "metricas": {k: m.get(k) for k in P.METRICAS},
                            "interaccion": P._interaccion(m)})
    mejores.sort(key=lambda x: -(x["metricas"].get("vistas") or 0))
    pg = palabras_y_ganchos(raiz, videos, cid, cuantos=5, desde=inicio, hasta=fin)
    hor = horarios(raiz, videos, cid)
    ajustes = P.ajustes_de(raiz, cid)
    salida = {
        "mes": mes, "nombre_mes": _nombre_mes(inicio), "proyecto": cid or P.SIN_PROYECTO,
        "nombre": nombre, "desde": inicio.strftime("%Y-%m-%d"),
        "hasta": (fin - dt.timedelta(days=1)).strftime("%Y-%m-%d"),
        "total": total, "anterior": anterior, "por_red": por_red,
        "en_curso": en_curso, "anterior_desde": antes.strftime("%Y-%m-%d"),
        "anterior_hasta": P._iso_lima(tope_antes)[:16],
        "videos": len({v["pid"] for v, _e in pares}),
        "dias_con_publicacion": len({str(e.get("cuando") or "")[:10] for _v, e in pares}),
        "sin_cifras": sum(1 for _v, e in pares
                          if not isinstance((e.get("metricas") or {}).get("vistas"), (int, float))),
        "mejores": mejores[:5], "palabras": pg["palabras"][:5], "ganchos": pg["ganchos"][:5],
        "horario": hor["todas"][:1],
        "seguidores": ajustes.get("seguidores") or {},
        "seguidores_al": ajustes.get("seguidores_al") or "",
        "hecho": P._iso_lima(), "meses": meses_con_publicaciones(raiz, videos, cid),
    }
    salida["resumen"] = resumen(salida)
    return salida


_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre")


def _nombre_mes(momento):
    return f"{_MESES[momento.month - 1]} de {momento.year}"


def _num(n):
    if not isinstance(n, (int, float)):
        return "—"
    return f"{int(n):,}".replace(",", ".")


def _cambio(actual, previo, frente="frente al mes anterior"):
    if not isinstance(actual, (int, float)) or not isinstance(previo, (int, float)) or not previo:
        return ""
    pct = round((actual - previo) * 100 / previo)
    return f" ({'+' if pct >= 0 else ''}{pct} % {frente})"


def resumen(inf):
    """El informe en texto llano, para pegarlo en un correo o un mensaje."""
    t, a = inf["total"], inf["anterior"]
    frente = ("frente a los mismos días del mes anterior" if inf.get("en_curso")
              else "frente al mes anterior")
    lineas = [f"Resultados de {inf['nombre'] or 'redes'}: {inf['nombre_mes']}"
              + (" (mes en curso)" if inf.get("en_curso") else ""), ""]
    lineas.append(f"• Publicaciones: {t.get('posts', 0)} ({inf['videos']} vídeo(s), "
                  f"{inf['dias_con_publicacion']} día(s) con publicación)"
                  + _cambio(t.get("posts"), a.get("posts"), frente))
    for k, nombre in (("vistas", "Vistas"), ("me_gusta", "Me gusta"),
                      ("comentarios", "Comentarios"), ("compartidos", "Compartidos")):
        if isinstance(t.get(k), (int, float)):
            lineas.append(f"• {nombre}: {_num(t[k])}" + _cambio(t.get(k), a.get(k), frente))
    if inf["por_red"]:
        lineas += ["", "Por red:"]
        for red, f in inf["por_red"].items():
            lineas.append(f"• {P.NOMBRE_RED.get(red, red)}: {f['posts']} publicación(es), "
                          f"{_num(f.get('vistas'))} vistas")
    if inf["mejores"]:
        lineas += ["", "Lo que mejor funcionó:"]
        for i, p in enumerate(inf["mejores"][:3], 1):
            lineas.append(f"{i}. {p['nombre']} en {P.NOMBRE_RED.get(p['red'], p['red'])}: "
                          f"{_num(p['metricas'].get('vistas'))} vistas"
                          + (f" — {p['url']}" if p.get("url") else ""))
    con_palabra = [p for p in inf["palabras"] if p["palabra"] != SIN_PALABRA]
    if con_palabra:
        lineas += ["", "Palabras clave que mejor fueron: "
                   + ", ".join(f"{p['palabra']} ({_num(p['mediana'])} vistas de mediana)"
                               for p in con_palabra[:3])]
    if inf["horario"]:
        h = inf["horario"][0]
        lineas.append(f"Mejor momento para publicar: {h['dia_nombre']} hacia las {h['hora']}.")
    seg = {r: s for r, s in (inf["seguidores"] or {}).items()
           if isinstance((s or {}).get("seguidores"), (int, float))}
    if seg:
        lineas += ["", "Seguidores hoy: " + ", ".join(
            f"{P.NOMBRE_RED.get(r, r)} {_num(s['seguidores'])}" for r, s in seg.items())]
    if inf["sin_cifras"]:
        lineas += ["", f"({inf['sin_cifras']} publicación(es) sin cifras: subidas a mano "
                       "o redes que no las dan.)"]
    return "\n".join(lineas)

#!/usr/bin/env python3
"""LA PRUEBA REAL: un vídeo de verdad, de punta a punta, en el servidor.

    asvs probar                 (en la consola del VPS, como root)
    asvs probar --estilo ID     con ese estilo (si no, el primero que haya)
    asvs probar nueva           empieza otra aunque haya una a medias

SI LA CONSOLA SE CORTA no pasa nada: la prueba corre aparte del terminal
(`asvs probar` la lanza desligada y solo va enseñando su registro). Volver a
escribir `asvs probar` vuelve a enseñarla si sigue corriendo, o la RETOMA donde
se quedó si el proceso murió: guarda su estado tras cada paso
(<proyectos>/_sistema/pruebas_reales/en_curso.json), no vuelve a lanzar lo ya
lanzado --espera a ESE trabajo-- y mide el gasto contra lo prometido y lo
gastado ANTES de lanzarlo, que quedaron guardados. Retomar no repite gasto ni
afloja ninguna comprobación.

Lo que prueba el recorrido (`prueba_recorrido.py`) es la PANTALLA con motores
simulados. Esto es lo otro: con TUS claves, contra OpenAI, Cartesia, Jamendo,
FreeSound y tu cuenta de Claude, crea un vídeo de prueba de 30 s en calidad
baja y lo lleva hasta el MP4, rehace dos imágenes con notas («Rehacer» y
«Desde cero») y comprueba sola lo que hoy se revisa a mano:

  - que cada paso termina sin error y en un tiempo razonable;
  - que el MP4 existe, dura lo que la voz y lleva sonido;
  - que no hay letras rotas («TÃº») en la voz ni en los subtítulos;
  - que lo gastado cuadra con lo prometido antes de pulsar, y que nada se pagó
    dos veces (cada imagen, una vez);
  - que la música y los efectos salieron de Jamendo y FreeSound;
  - y, con tu cuenta de Claude mirando las imágenes, si cada nota SE APLICÓ y si
    el guion cuenta lo que dice el material (sin inventar).

Gasta lo que gasta un vídeo de 30 s en calidad baja: ~0,6-1 $ (unas 12-15
imágenes a 0,047 $ y unos céntimos de voz). NO toca ningún vídeo tuyo: crea uno
nuevo, «Prueba real <fecha>», que se queda en tu Studio para que lo veas.

Deja el informe en la consola (es lo que hay que mandar si algo sale mal) y en
<proyectos>/_sistema/pruebas_reales/<fecha>.json.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

MATERIAL = (
    "Mario Kart 8 Deluxe es el juego de carreras más vendido de Nintendo Switch: "
    "más de 60 millones de copias en todo el mundo.\n\n"
    "En muchas familias se ha vuelto una tradición de domingo. Los padres "
    "aprendieron con Super Mario Kart en 1992 y hoy compiten contra sus hijos, "
    "que casi siempre ganan.\n\n"
    "¿Por qué? Los niños juegan más horas a la semana y se saben de memoria "
    "los atajos de cada circuito.")

NOTA_RETOQUE = "que aparezca un gato naranja sentado en primer plano"
NOTA_DESDE_CERO = "que sea de noche, con farolas encendidas y el cielo oscuro"

LETRAS_ROTAS = re.compile("[ÂÃ][\u0080-¿]|â[\u0080-¿]{2}")


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def _pedir(self, metodo, ruta, cuerpo=None, tiempo=120):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        peticion = urllib.request.Request(self.base + ruta, data=datos, method=metodo,
                                          headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=tiempo) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as fallo:
            try:
                return fallo.code, json.loads(fallo.read() or b"{}")
            except ValueError:
                return fallo.code, {}
        except (urllib.error.URLError, OSError, ValueError):
            # el Studio reiniciandose (o un corte de un segundo): 0 y se reintenta
            return 0, {}

    def get(self, ruta):
        return self._pedir("GET", ruta)

    def post(self, ruta, cuerpo=None):
        return self._pedir("POST", ruta, cuerpo or {})

    def put(self, ruta, cuerpo=None):
        return self._pedir("PUT", ruta, cuerpo or {})

    def trabajo(self, tid, limite_s=3600, etiqueta=""):
        fin = time.time() + limite_s
        ultimo = ""
        caidas = 0
        while time.time() < fin:
            codigo, ficha = self.get(f"/api/trabajos/{tid}")
            if codigo == 0 and caidas < 60:              # el Studio no contesta: se espera
                caidas += 1
                time.sleep(5)
                continue
            if codigo != 200:
                return {"estado": "desconocido"}
            caidas = 0
            if ficha.get("estado") in ("listo", "error", "cancelado"):
                return ficha
            texto = f"{etiqueta}: {int(100 * float(ficha.get('progreso') or 0))} % {ficha.get('publico') or ficha.get('mensaje') or ''}"
            if texto != ultimo:
                print(f"     … {texto[:110]}", flush=True)
                ultimo = texto
            time.sleep(5)
        return {"estado": "colgado"}

    def libre(self, pid, limite_s=1800):
        fin = time.time() + limite_s
        while time.time() < fin:
            codigo, d = self.get(f"/api/trabajos?proyecto={pid}&activos=1")
            if codigo == 200 and not (d.get("trabajos") if isinstance(d, dict) else d):
                return True
            time.sleep(3)
        return False


class Informe:
    """Las comprobaciones, cada una con la PARTE de la prueba a la que
    pertenece. Al retomar una prueba cortada se conservan las de las partes
    terminadas (no se vuelven a pagar ni a medir) y se rehacen las demás."""

    def __init__(self, guardar=None):
        self.lineas = []
        self.fallos = 0
        self.avisos = 0
        self.parte = ""
        self._guardar = guardar or (lambda: None)

    def cargar(self, lineas, hechas):
        for linea in lineas or []:
            if linea.get("parte") in hechas:
                self.lineas.append(linea)
                self.fallos += linea.get("estado") == "fallo"
                self.avisos += linea.get("estado") == "aviso"
                marca = {"ok": "✓", "fallo": "✗", "aviso": "!"}[linea["estado"]]
                print(f"  {marca} {linea['que']}" + (f"  — {linea['detalle']}" if linea.get("detalle") else "")
                      + "   (de antes del corte)", flush=True)

    def apunta(self, estado, que, detalle=""):
        marca = {"ok": "✓", "fallo": "✗", "aviso": "!"}[estado]
        if estado == "fallo":
            self.fallos += 1
        elif estado == "aviso":
            self.avisos += 1
        self.lineas.append({"estado": estado, "que": que, "detalle": detalle, "parte": self.parte})
        print(f"  {marca} {que}" + (f"  — {detalle}" if detalle else ""), flush=True)
        self._guardar()

    def comprueba(self, condicion, que, detalle="", solo_aviso=False):
        self.apunta("ok" if condicion else ("aviso" if solo_aviso else "fallo"), que,
                    "" if condicion else detalle)
        return condicion


def seccion(titulo):
    print(f"\n[{titulo}]", flush=True)


def _ffprobe(ruta):
    try:
        salida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
             "-of", "json", ruta], capture_output=True, text=True, timeout=60).stdout
        datos = json.loads(salida or "{}")
        return (float((datos.get("format") or {}).get("duration") or 0),
                {s.get("codec_type") for s in datos.get("streams") or []})
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0, set()


def _juez(instruccion, cwd):
    """Pregunta a Claude (tu suscripción) y devuelve su JSON. Puede LEER imágenes."""
    from pasos import cli_claude, comun                     # noqa: PLC0415
    respuesta, _sobre = cli_claude.ejecutar(
        instruccion, modelo="sonnet", esfuerzo="low", cwd=cwd, base_tiempo_s=240,
        sistema="Eres un revisor estricto. Contestas solo con el JSON pedido.",
        extra=["--no-session-persistence"], para="la prueba real",
        # Read hay que QUITARLO de las vetadas, no basta con permitirlo: el
        # veto por defecto del CLI incluye Read y gana (el 11-10 el juez
        # contesto «la herramienta Read esta desactivada» y marco «no»)
        herramientas_vetadas=tuple(h for h in cli_claude.HERRAMIENTAS_VETADAS if h != "Read"),
        herramientas_permitidas=("Read",))
    return comun.extraer_json(respuesta, "la prueba real")


def _carpeta_informes(proyectos):
    return os.path.join(proyectos, "_sistema", "pruebas_reales")


def _ruta_en_curso(proyectos):
    """La prueba a medias: lo justo para retomarla donde se cortó."""
    return os.path.join(_carpeta_informes(proyectos), "en_curso.json")


def _leer_en_curso(proyectos):
    try:
        with open(_ruta_en_curso(proyectos), encoding="utf-8") as fh:
            est = json.load(fh)
        return est if isinstance(est, dict) and est.get("proyecto") else None
    except (OSError, ValueError):
        return None


def _prueba_cortada_sin_estado(api, proyectos):
    """Una «Prueba real» que se cortó ANTES de que existiera el retomar (no
    dejó en_curso.json): la más nueva, si es posterior al último informe."""
    _c, lista = api.get("/api/proyectos")
    fichas = lista if isinstance(lista, list) else (lista or {}).get("proyectos") or []
    candidatas = []
    for f in fichas:
        m = re.match(r"Prueba real (\d{4}-\d{2}-\d{2} \d{2}\.\d{2})$", str(f.get("nombre") or ""))
        if m:
            candidatas.append((datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H.%M"), f.get("id")))
    if not candidatas:
        return None
    fecha, pid = max(candidatas)
    carpeta = _carpeta_informes(proyectos)
    for nombre in os.listdir(carpeta) if os.path.isdir(carpeta) else []:
        m = re.match(r"(\d{4}-\d{2}-\d{2}_\d{4})\.json$", nombre)
        if m and datetime.datetime.strptime(m.group(1), "%Y-%m-%d_%H%M") >= fecha:
            return None                                 # esa ya terminó y tiene informe
    return pid


def main():
    ap = argparse.ArgumentParser(description="La prueba real del Studio")
    ap.add_argument("--api", default=f"http://127.0.0.1:{os.environ.get('PUERTO', '8110')}")
    ap.add_argument("--estilo", default="", help="id del estilo (si no, el primero)")
    ap.add_argument("--segundos", type=int, default=30)
    ap.add_argument("--seguir", action="store_true",
                    help="si hay una prueba cortada, la sigue donde se quedó (sin volver a pagar)")
    # PARA PROBAR ESTA PRUEBA (en local, con motores simulados): sobre un video
    # que ya existe y sin exigir las claves
    ap.add_argument("--proyecto", default="", help=argparse.SUPPRESS)
    ap.add_argument("--sin-claves", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    api = Api(args.api)
    proyectos = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")
    os.makedirs(_carpeta_informes(proyectos), exist_ok=True)

    # EL ESTADO DE LA PRUEBA, en disco despues de cada paso: si la consola se
    # corta (o el proceso muere), `asvs probar` la retoma donde estaba. Lo ya
    # lanzado NO se vuelve a lanzar: se espera a SU trabajo y se mide contra lo
    # que se prometio y se gastaba ANTES de lanzarlo, guardado aqui.
    est = _leer_en_curso(proyectos) if args.seguir else None
    adoptada = None
    if args.seguir and not est and not args.proyecto:
        adoptada = _prueba_cortada_sin_estado(api, proyectos)
    if est:
        est["retomada"] = True
        print(f"RETOMANDO LA PRUEBA REAL del vídeo «{est['proyecto']}» donde se cortó "
              "(lo ya hecho no se repite ni se paga otra vez)")
    else:
        est = {"proyecto": args.proyecto or adoptada or "", "estilo": "", "inicio": time.time(),
               "hechas": [], "lineas": [], "tandas": {}, "notas": {}, "adoptada": bool(adoptada)}
        if adoptada:
            print(f"RETOMANDO la prueba real cortada «{adoptada}» (se cortó antes de que la "
                  "prueba guardara su estado: la tanda que estaba en marcha no se puede medir "
                  "contra lo prometido; el resto sí)")
        else:
            print("LA PRUEBA REAL DEL STUDIO (gasta ~0,6-1 $; no toca tus vídeos)")

    def guardar():
        est["lineas"] = informe.lineas
        temporal = _ruta_en_curso(proyectos) + ".tmp"
        try:
            with open(temporal, "w", encoding="utf-8") as fh:
                json.dump(est, fh, ensure_ascii=False)
            os.replace(temporal, _ruta_en_curso(proyectos))
        except OSError:
            pass

    informe = Informe(guardar)
    informe.cargar(est.get("lineas"), set(est.get("hechas") or []))
    inicio = float(est.get("inicio") or time.time())

    def hecha(parte):
        if parte not in est["hechas"]:
            est["hechas"].append(parte)
        guardar()

    def cerrar(datos):
        codigo = _cerrar(informe, proyectos, inicio, datos)
        try:
            os.remove(_ruta_en_curso(proyectos))
        except OSError:
            pass
        return codigo

    # 1. LAS CLAVES: siempre (es gratis y pueden haber cambiado)
    seccion("1. El servidor y las claves")
    informe.parte = "claves"
    informe.lineas = [l for l in informe.lineas if l.get("parte") != "claves"]
    codigo, _salud = api.get("/api/salud")
    if not informe.comprueba(codigo == 200, "el Studio contesta", f"HTTP {codigo}"):
        return 2
    codigo, claves = api.post("/api/claves/probar", {"claude": True})
    for p in claves.get("pruebas") or []:
        opcional = p.get("proveedor") in ("jamendo", "freesound") or args.sin_claves
        informe.comprueba(p.get("estado") == "ok", f"clave de {p.get('proveedor')}",
                          f"{p.get('estado')}: {p.get('mensaje')}", solo_aviso=opcional)
    imprescindibles = {p.get("proveedor"): p.get("estado") for p in claves.get("pruebas") or []}
    if not args.sin_claves and any(imprescindibles.get(x) not in ("ok", None)
                                   for x in ("openai", "cartesia")):
        informe.apunta("fallo", "sin las claves de OpenAI y Cartesia no se puede seguir")
        return cerrar({})

    seccion("2. El vídeo de prueba")
    informe.parte = "crear"
    if est["proyecto"]:
        pid = est["proyecto"]
        if "crear" not in est["hechas"]:
            informe.apunta("ok", f"se sigue con el vídeo de prueba «{pid}»")
            hecha("crear")
    else:
        _c, lista = api.get("/api/presets-light")
        estilos = [p for p in lista.get("presets") or [] if p.get("tipo", "canal") == "canal"]
        estilo = next((p for p in estilos if p.get("id") == args.estilo), None) or (estilos[0] if estilos else None)
        if not informe.comprueba(bool(estilo), "hay un estilo con el que hacerlo", "crea uno primero"):
            return cerrar({})
        nombre = "Prueba real " + datetime.datetime.now().strftime("%Y-%m-%d %H.%M")
        codigo, creado = api.post(f"/api/presets-light/{estilo['id']}/video", {
            "nombre": nombre, "duracion_objetivo_s": args.segundos, "material": MATERIAL,
            "indicaciones": "Cercano y con humor, frases cortas."})
        pid = (creado.get("proyecto") or {}).get("id") or ""
        if not informe.comprueba(codigo == 201 and pid, f"se crea «{nombre}» con el estilo «{estilo.get('nombre')}»",
                                 f"HTTP {codigo}: {creado}"):
            return cerrar({})
        # CALIDAD BAJA: es una prueba (se escribe antes de generar nada: no mueve firmas)
        api.put(f"/api/proyectos/{pid}/pasos/assets/params", {"params": {"calidad": "low"}})
        est["proyecto"], est["estilo"] = pid, estilo.get("id")
        hecha("crear")
    raiz = os.path.join(proyectos, pid)
    datos = {"proyecto": pid, "estilo": est.get("estilo")}

    for tanda, limite in (("guion", 900), ("voz", 900), ("video", 3600), ("render", 2400)):
        parte = f"tanda:{tanda}"
        if parte in est["hechas"]:
            continue
        seccion(f"3. La tanda «{tanda}»")
        informe.parte = parte
        informe.lineas = [l for l in informe.lineas if l.get("parte") != parte]
        t = est["tandas"].get(tanda) or {}
        if t.get("tid"):
            # LANZADA ANTES DEL CORTE: se espera a ESE trabajo, no se lanza otro
            print(f"     (estaba en marcha antes del corte: se sigue su trabajo {t['tid']})", flush=True)
            fin = api.trabajo(t["tid"], limite, tanda)
            if fin.get("estado") == "desconocido":
                # el Studio se reinició y olvidó el trabajo: manda lo que diga el plan
                api.libre(pid)
                _c, plan = api.get(f"/api/proyectos/{pid}/generar?tanda={tanda}&modo=pendientes")
                if plan.get("tareas") == 0:
                    fin = {"estado": "listo"}
        else:
            # lo que hubiera en marcha (una prueba adoptada que se cortó a media tanda)
            if not api.libre(pid, 3600):
                informe.apunta("fallo", f"«{tanda}»: el vídeo sigue ocupado con otro trabajo tras una hora")
                return cerrar(datos)
            _c, plan = api.get(f"/api/proyectos/{pid}/generar?tanda={tanda}&modo=pendientes")
            if plan.get("tareas") == 0:
                informe.apunta("ok", f"«{tanda}» ya estaba al día")
                if est.get("adoptada") and tanda in ("guion", "voz", "video"):
                    informe.apunta("aviso", f"«{tanda}»: lo gastado no se ha podido comparar con lo prometido",
                                   "se hizo antes del corte, cuando la prueba aún no guardaba lo prometido")
                hecha(parte)
                continue
            _c, antes = api.get(f"/api/proyectos/{pid}/coste")
            t = {"prometido": float(((plan.get("coste") or {}).get("usd_por_generar")) or 0),
                 "antes": float(antes.get("total_usd") or 0), "t0": time.time()}
            codigo, lanzada = api.post(f"/api/proyectos/{pid}/generar", {"tanda": tanda, "modo": "pendientes"})
            tid = lanzada.get("trabajo_id") or (lanzada.get("trabajo") or {}).get("id")
            if not informe.comprueba(codigo == 202 and tid, f"se lanza «{tanda}»", f"HTTP {codigo}: {lanzada}"):
                return cerrar(datos)
            t["tid"] = tid
            est["tandas"][tanda] = t
            guardar()
            fin = api.trabajo(tid, limite, tanda)
        segundos = round(time.time() - float(t.get("t0") or time.time()))
        est.setdefault("tiempos_s", {})[tanda] = segundos
        if not informe.comprueba(fin.get("estado") == "listo", f"«{tanda}» termina bien ({segundos} s)",
                                 f"{fin.get('estado')}: {fin.get('error') or fin.get('mensaje')}"):
            return cerrar(datos)
        _c, despues = api.get(f"/api/proyectos/{pid}/coste")
        gastado = float(despues.get("total_usd") or 0) - float(t.get("antes") or 0)
        prometido = float(t.get("prometido") or 0)
        if prometido or gastado > 0.01:
            informe.comprueba(gastado <= prometido * 1.35 + 0.05,
                              f"«{tanda}»: gastado {gastado:.3f} $ frente a {prometido:.3f} $ prometidos",
                              "se ha gastado bastante más de lo que se dijo antes de pulsar")
        hecha(parte)
    datos["tiempos_s"] = est.get("tiempos_s") or {}

    # 4. LO QUE HA SALIDO: solo lee, se repite entera al retomar
    seccion("4. Lo que ha salido")
    informe.parte = "salida"
    informe.lineas = [l for l in informe.lineas if l.get("parte") != "salida"]
    meta = os.path.join(raiz, "pasos", "voz")
    activa = _activa(raiz, "voz")
    palabras = []
    try:
        with open(os.path.join(meta, f"v{activa}", "audio_meta.json"), encoding="utf-8") as fh:
            palabras = [p.get("w", "") for p in json.load(fh).get("palabras") or []]
    except (OSError, ValueError):
        pass
    informe.comprueba(bool(palabras), f"la voz tiene sus marcas de palabra ({len(palabras)})", "sin marcas")
    rotas = [w for w in palabras if LETRAS_ROTAS.search(w)]
    informe.comprueba(not rotas, "la voz llega sin letras rotas (las tildes bien)", f"rotas: {rotas[:5]}")
    mp4 = os.path.join(raiz, "pasos", "render", f"v{_activa(raiz, 'render')}", "video.mp4")
    duracion, pistas = _ffprobe(mp4)
    informe.comprueba(os.path.isfile(mp4), "el MP4 existe", mp4)
    informe.comprueba("audio" in pistas and "video" in pistas, "con imagen y sonido", f"pistas: {pistas}")
    informe.comprueba(args.segundos * 0.5 <= duracion <= args.segundos * 2.2,
                      f"y dura {duracion:.1f} s (pedidos {args.segundos})", "fuera de lo razonable")
    capas = ""
    carpeta = os.path.join(raiz, "pasos", "callouts", f"v{_activa(raiz, 'callouts')}", "capas_fijas")
    for nombre_svg in sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []:
        with open(os.path.join(carpeta, nombre_svg), encoding="utf-8", errors="replace") as fh:
            capas += fh.read()
    informe.comprueba(capas and not LETRAS_ROTAS.search(capas), "los subtítulos dibujados, sin letras rotas",
                      "hay subtítulos con «Ã»")
    _c, render = api.get(f"/api/proyectos/{pid}/pasos/render")
    pr = render.get("params") or {}
    informe.comprueba(bool((pr.get("musica") or {}).get("pista") or pr.get("musica")),
                      "la música de Jamendo está puesta", "sin música (¿clave de Jamendo?)", solo_aviso=True)
    informe.comprueba(bool(pr.get("efectos")), "los efectos de FreeSound están puestos",
                      "sin efectos (¿clave de FreeSound?)", solo_aviso=True)
    _c, eventos = api.get(f"/api/proyectos/{pid}/coste/eventos?proveedor=openai&limite=500")
    unidades = [e.get("unidad") for e in eventos.get("eventos") or [] if e.get("unidad")]
    # las dos notas de la parte 5 rehacen DOS planos a proposito: no cuentan como repetidas
    rehechas = {f"escena:{plano}" for plano in est["notas"]}
    repetidas = sorted({u for u in unidades if unidades.count(u) > (2 if u in rehechas else 1)})
    informe.comprueba(not repetidas, f"cada imagen se pagó UNA vez ({len(unidades)} imágenes)",
                      f"pagadas dos veces: {repetidas[:6]}")

    seccion("5. Rehacer con notas (Rehacer y Desde cero)")
    juicios = est.setdefault("juicios", [])
    if not est.get("elegidas"):
        _c, previa = api.get(f"/api/proyectos/{pid}/previsualizacion")
        escenas = [e for e in previa.get("escenas") or [] if e.get("imagen") and not e.get("cartela")]
        elegidas = escenas[1:3] if len(escenas) >= 3 else escenas[:2]
        est["elegidas"] = [{"id": e["id"], "t_in": e.get("t_in", 0),
                            "antes_img": os.path.join(raiz, e["imagen"])} for e in elegidas]
        guardar()
    for escena, texto, cero in zip(est["elegidas"], (NOTA_RETOQUE, NOTA_DESDE_CERO), (False, True)):
        parte = f"nota:{escena['id']}"
        if parte in est["hechas"]:
            continue
        informe.parte = parte
        informe.lineas = [l for l in informe.lineas if l.get("parte") != parte]
        juicios[:] = [j for j in juicios if j.get("plano") != escena["id"]]
        n = est["notas"].setdefault(escena["id"], {})
        antes_img = escena["antes_img"]
        if not n.get("nid"):
            _c, nota = api.post(f"/api/proyectos/{pid}/repaso", {"texto": texto, "t": escena.get("t_in", 0),
                                                                   "plano": escena["id"], "pantalla": "imagenes"})
            n["nid"] = (nota.get("nota") or {}).get("id")
            guardar()
        nid = n["nid"]
        if not n.get("pedida"):
            # pedir dos veces la misma nota la volveria a dibujar (y a pagar): solo una
            api.post(f"/api/proyectos/{pid}/imagenes/rehacer", {"notas": [nid], "desde_cero": cero})
            n["pedida"] = True
            guardar()
        else:
            print(f"     (la nota de {escena['id']} ya estaba pedida antes del corte: se espera)", flush=True)
        fin = time.time() + 900
        aplicada, nota_viva = False, {}
        while time.time() < fin and not aplicada:
            time.sleep(5)
            _c, rep = api.get(f"/api/proyectos/{pid}/repaso")
            nota_viva = next((x for x in rep.get("notas") or [] if x.get("id") == nid), {})
            aplicada = nota_viva.get("estado") == "aplicado"
            if nota_viva.get("error"):
                break
        modo = "desde cero" if cero else "retoque"
        if not informe.comprueba(aplicada, f"{escena['id']} se rehace ({modo})",
                                 nota_viva.get("error") or "no terminó"):
            hecha(parte)
            continue
        _c, previa2 = api.get(f"/api/proyectos/{pid}/previsualizacion")
        nueva = next((e for e in previa2.get("escenas") or [] if e.get("id") == escena["id"]), {})
        despues_img = os.path.join(raiz, nueva.get("imagen") or "")
        informe.comprueba(os.path.isfile(despues_img) and despues_img != antes_img,
                          f"{escena['id']}: hay imagen nueva", "la imagen no cambió de versión")
        try:
            veredicto = _juez(
                f"Lee estas dos imágenes con la herramienta Read:\n- ANTES: {antes_img}\n"
                f"- DESPUÉS: {despues_img}\nLa persona pidió esta corrección: «{texto}».\n"
                "¿La imagen DESPUÉS aplica la corrección? Devuelve SOLO "
                '{"aplicada": "si" | "parcial" | "no", "por_que": "<una frase>"}', raiz)
        except Exception as fallo:                          # noqa: BLE001
            veredicto = {"aplicada": "?", "por_que": f"no se pudo preguntar a Claude: {fallo}"}
        if re.search(r"no pude (abrir|ver|leer|comprobar)|no est[aá] disponible|desactivada",
                     str((veredicto or {}).get("por_que") or ""), re.I):
            veredicto = {"aplicada": "?", "por_que": "Claude no pudo abrir las imágenes: " +
                         str((veredicto or {}).get("por_que"))}
        juicios.append({"plano": escena["id"], "nota": texto, "modo": modo, **(veredicto or {})})
        informe.comprueba((veredicto or {}).get("aplicada") in ("si", "sí"),
                          f"{escena['id']} ({modo}): Claude ve la nota aplicada",
                          f"{(veredicto or {}).get('aplicada')}: {(veredicto or {}).get('por_que')}",
                          solo_aviso=(veredicto or {}).get("aplicada") == "parcial")
        hecha(parte)
    datos["juicios_imagenes"] = juicios

    seccion("6. El guion frente al material")
    informe.parte = "guion"
    informe.lineas = [l for l in informe.lineas if l.get("parte") != "guion"]
    guion = ""
    try:
        with open(os.path.join(raiz, "pasos", "guion", f"v{_activa(raiz, 'guion')}", "guion.json"),
                  encoding="utf-8") as fh:
            doc = json.load(fh)
        # el guion guarda sus bloques en «bloques» o en «guion», segun la version
        bloques = (doc.get("bloques") or doc.get("guion") or []) if isinstance(doc, dict) else doc
        if isinstance(bloques, dict):
            bloques = bloques.get("bloques") or []
        guion = " ".join(str(b.get("texto") or b.get("narracion") or "")
                         for b in bloques or [] if isinstance(b, dict))
    except (OSError, ValueError):
        pass
    if informe.comprueba(bool(guion), "hay guion", "sin guion.json"):
        try:
            veredicto = _juez(
                f"<material>\n{MATERIAL}\n</material>\n<guion>\n{guion}\n</guion>\n"
                "¿El guion cuenta lo que dice el material, sin inventar datos que no "
                "están (cifras, fechas, nombres)? Devuelve SOLO "
                '{"fiel": true | false, "inventos": ["<dato inventado>"], "por_que": "<una frase>"}', raiz)
        except Exception as fallo:                          # noqa: BLE001
            veredicto = {"fiel": None, "por_que": f"no se pudo preguntar a Claude: {fallo}"}
        datos["juicio_guion"] = veredicto
        informe.comprueba((veredicto or {}).get("fiel") is True, "el guion es fiel al material",
                          f"{(veredicto or {}).get('inventos')}: {(veredicto or {}).get('por_que')}")
        try:
            from pasos import ortografia                    # noqa: PLC0415
            faltas = ortografia.revisar({"guion": guion}, cwd=raiz)
        except Exception as fallo:                          # noqa: BLE001
            faltas = {"error": {"cambios": [[str(fallo), ""]]}}
        cambios = sum((f.get("cambios") or [] for f in faltas.values()), [])
        informe.comprueba(not cambios, "el guion sale sin faltas de ortografía",
                          f"{len(cambios)}: {cambios[:5]}", solo_aviso=True)
    if est.get("adoptada") or est.get("retomada"):
        datos["retomada"] = True
    return cerrar(datos)


def _activa(raiz, paso):
    try:
        with open(os.path.join(raiz, "pasos", paso, "activa.json"), encoding="utf-8") as fh:
            return json.load(fh).get("activa")
    except (OSError, ValueError):
        return None


def _cerrar(informe, proyectos, inicio, datos):
    minutos = (time.time() - inicio) / 60
    veredicto = ("APROBADA" if not informe.fallos else "CON FALLOS")
    print(f"\nPRUEBA REAL {veredicto}: {informe.fallos} fallo(s), {informe.avisos} aviso(s), "
          f"{minutos:.0f} min")
    if datos.get("proyecto"):
        print(f"El vídeo de prueba se queda en tu Studio: «{datos['proyecto']}».")
    carpeta = os.path.join(proyectos, "_sistema", "pruebas_reales")
    try:
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump({"veredicto": veredicto, "fallos": informe.fallos, "avisos": informe.avisos,
                       "minutos": round(minutos, 1), "lineas": informe.lineas, **datos},
                      fh, ensure_ascii=False, indent=1)
        print(f"Informe guardado en {ruta}")
    except OSError as fallo:
        print(f"(no se ha podido guardar el informe: {fallo})")
    return 0 if not informe.fallos else 1


if __name__ == "__main__":
    sys.exit(main())

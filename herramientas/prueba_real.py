#!/usr/bin/env python3
"""LA PRUEBA REAL: un vídeo de verdad, de punta a punta, en el servidor.

    asvs probar                 (en la consola del VPS, como root)
    asvs probar --estilo ID     con ese estilo (si no, el primero que haya)

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

    def get(self, ruta):
        return self._pedir("GET", ruta)

    def post(self, ruta, cuerpo=None):
        return self._pedir("POST", ruta, cuerpo or {})

    def put(self, ruta, cuerpo=None):
        return self._pedir("PUT", ruta, cuerpo or {})

    def trabajo(self, tid, limite_s=3600, etiqueta=""):
        fin = time.time() + limite_s
        ultimo = ""
        while time.time() < fin:
            codigo, ficha = self.get(f"/api/trabajos/{tid}")
            if codigo != 200:
                return {"estado": "desconocido"}
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
            _c, d = self.get(f"/api/trabajos?proyecto={pid}&activos=1")
            if not (d.get("trabajos") if isinstance(d, dict) else d):
                return True
            time.sleep(3)
        return False


class Informe:
    def __init__(self):
        self.lineas = []
        self.fallos = 0
        self.avisos = 0

    def apunta(self, estado, que, detalle=""):
        marca = {"ok": "✓", "fallo": "✗", "aviso": "!"}[estado]
        if estado == "fallo":
            self.fallos += 1
        elif estado == "aviso":
            self.avisos += 1
        self.lineas.append({"estado": estado, "que": que, "detalle": detalle})
        print(f"  {marca} {que}" + (f"  — {detalle}" if detalle else ""), flush=True)

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
        herramientas_permitidas=("Read",))
    return comun.extraer_json(respuesta, "la prueba real")


def main():
    ap = argparse.ArgumentParser(description="La prueba real del Studio")
    ap.add_argument("--api", default=f"http://127.0.0.1:{os.environ.get('PUERTO', '8110')}")
    ap.add_argument("--estilo", default="", help="id del estilo (si no, el primero)")
    ap.add_argument("--segundos", type=int, default=30)
    # PARA PROBAR ESTA PRUEBA (en local, con motores simulados): sobre un video
    # que ya existe y sin exigir las claves
    ap.add_argument("--proyecto", default="", help=argparse.SUPPRESS)
    ap.add_argument("--sin-claves", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    api = Api(args.api)
    informe = Informe()
    inicio = time.time()
    proyectos = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")
    print("LA PRUEBA REAL DEL STUDIO (gasta ~0,6-1 $; no toca tus vídeos)")

    seccion("1. El servidor y las claves")
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
        return _cerrar(informe, proyectos, inicio, {})

    seccion("2. El vídeo de prueba")
    _c, lista = api.get("/api/presets-light")
    estilos = [p for p in lista.get("presets") or [] if p.get("tipo", "canal") == "canal"]
    estilo = next((p for p in estilos if p.get("id") == args.estilo), None) or (estilos[0] if estilos else None)
    if not informe.comprueba(bool(estilo), "hay un estilo con el que hacerlo", "crea uno primero"):
        return _cerrar(informe, proyectos, inicio, {})
    nombre = "Prueba real " + datetime.datetime.now().strftime("%Y-%m-%d %H.%M")
    if args.proyecto:
        pid = args.proyecto
    else:
        codigo, creado = api.post(f"/api/presets-light/{estilo['id']}/video", {
            "nombre": nombre, "duracion_objetivo_s": args.segundos, "material": MATERIAL,
            "indicaciones": "Cercano y con humor, frases cortas."})
        pid = (creado.get("proyecto") or {}).get("id") or ""
        if not informe.comprueba(codigo == 201 and pid, f"se crea «{nombre}» con el estilo «{estilo.get('nombre')}»",
                                 f"HTTP {codigo}: {creado}"):
            return _cerrar(informe, proyectos, inicio, {})
        # CALIDAD BAJA: es una prueba (se escribe antes de generar nada: no mueve firmas)
        api.put(f"/api/proyectos/{pid}/pasos/assets/params", {"params": {"calidad": "low"}})
    raiz = os.path.join(proyectos, pid)
    datos = {"proyecto": pid, "estilo": estilo.get("id")}

    tiempos = {}
    for tanda, limite in (("guion", 900), ("voz", 900), ("video", 3600), ("render", 2400)):
        seccion(f"3. La tanda «{tanda}»")
        _c, plan = api.get(f"/api/proyectos/{pid}/generar?tanda={tanda}&modo=pendientes")
        prometido = float(((plan.get("coste") or {}).get("usd_por_generar")) or 0)
        if plan.get("tareas") == 0:
            informe.apunta("ok", f"«{tanda}» ya estaba al día")
            continue
        _c, antes = api.get(f"/api/proyectos/{pid}/coste")
        t0 = time.time()
        codigo, lanzada = api.post(f"/api/proyectos/{pid}/generar", {"tanda": tanda, "modo": "pendientes"})
        tid = lanzada.get("trabajo_id") or (lanzada.get("trabajo") or {}).get("id")
        if not informe.comprueba(codigo == 202 and tid, f"se lanza «{tanda}»", f"HTTP {codigo}: {lanzada}"):
            return _cerrar(informe, proyectos, inicio, datos)
        fin = api.trabajo(tid, limite, tanda)
        tiempos[tanda] = round(time.time() - t0)
        if not informe.comprueba(fin.get("estado") == "listo", f"«{tanda}» termina bien ({tiempos[tanda]} s)",
                                 f"{fin.get('estado')}: {fin.get('error') or fin.get('mensaje')}"):
            return _cerrar(informe, proyectos, inicio, datos)
        _c, despues = api.get(f"/api/proyectos/{pid}/coste")
        gastado = float(despues.get("total_usd") or 0) - float(antes.get("total_usd") or 0)
        if prometido or gastado > 0.01:
            informe.comprueba(gastado <= prometido * 1.35 + 0.05,
                              f"«{tanda}»: gastado {gastado:.3f} $ frente a {prometido:.3f} $ prometidos",
                              "se ha gastado bastante más de lo que se dijo antes de pulsar")
    datos["tiempos_s"] = tiempos

    seccion("4. Lo que ha salido")
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
    repetidas = sorted({u for u in unidades if unidades.count(u) > 1})
    informe.comprueba(not repetidas, f"cada imagen se pagó UNA vez ({len(unidades)} imágenes)",
                      f"pagadas dos veces: {repetidas[:6]}")

    seccion("5. Rehacer con notas (Rehacer y Desde cero)")
    _c, previa = api.get(f"/api/proyectos/{pid}/previsualizacion")
    escenas = [e for e in previa.get("escenas") or [] if e.get("imagen") and not e.get("cartela")]
    elegidas = escenas[1:3] if len(escenas) >= 3 else escenas[:2]
    juicios = []
    for escena, texto, cero in zip(elegidas, (NOTA_RETOQUE, NOTA_DESDE_CERO), (False, True)):
        antes_img = os.path.join(raiz, escena["imagen"])
        _c, nota = api.post(f"/api/proyectos/{pid}/repaso", {"texto": texto, "t": escena.get("t_in", 0),
                                                               "plano": escena["id"], "pantalla": "imagenes"})
        nid = (nota.get("nota") or {}).get("id")
        api.post(f"/api/proyectos/{pid}/imagenes/rehacer", {"notas": [nid], "desde_cero": cero})
        fin = time.time() + 900
        hecha = False
        while time.time() < fin and not hecha:
            time.sleep(5)
            _c, rep = api.get(f"/api/proyectos/{pid}/repaso")
            nota_viva = next((n for n in rep.get("notas") or [] if n.get("id") == nid), {})
            hecha = nota_viva.get("estado") == "aplicado"
            if nota_viva.get("error"):
                break
        modo = "desde cero" if cero else "retoque"
        if not informe.comprueba(hecha, f"{escena['id']} se rehace ({modo})",
                                 nota_viva.get("error") or "no terminó"):
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
        juicios.append({"plano": escena["id"], "nota": texto, "modo": modo, **(veredicto or {})})
        informe.comprueba((veredicto or {}).get("aplicada") in ("si", "sí"),
                          f"{escena['id']} ({modo}): Claude ve la nota aplicada",
                          f"{(veredicto or {}).get('aplicada')}: {(veredicto or {}).get('por_que')}",
                          solo_aviso=(veredicto or {}).get("aplicada") == "parcial")
    datos["juicios_imagenes"] = juicios

    seccion("6. El guion frente al material")
    guion = ""
    try:
        with open(os.path.join(raiz, "pasos", "guion", f"v{_activa(raiz, 'guion')}", "guion.json"),
                  encoding="utf-8") as fh:
            doc = json.load(fh)
        # el guion guarda sus bloques en «bloques» o en «guion», segun la version
        bloques = doc.get("bloques") or doc.get("guion") or [] if isinstance(doc, dict) else doc
        if isinstance(bloques, dict):
            bloques = bloques.get("bloques") or []
        guion = " ".join(str(b.get("texto") or b.get("narracion") or "")
                         for b in bloques if isinstance(b, dict))
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
    return _cerrar(informe, proyectos, inicio, datos)


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

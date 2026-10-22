#!/usr/bin/env python3
"""LA PRUEBA COMPLETA: el Studio entero con vídeos de verdad, de punta a punta.

    asvs probar completo             (en la consola del VPS, como root)
    asvs probar completo --tope 5    tope de gasto en dólares (5 por defecto)
    asvs probar completo nueva       empieza otra aunque haya una a medias

Al empezar pregunta EN QUÉ CUENTA PUBLICAR (uno de tus proyectos con perfil de
Upload-Post y sus redes conectadas) y pide que lo confirmes: se publica DE
VERDAD. Después corre aparte de la consola, como `asvs probar`, y si la consola
se corta sigue sola; volver a escribir el comando la enseña o la retoma sin
volver a pagar lo hecho.

Las partes, en orden, con una barra de progreso de todo y el gasto a la vista:

  1. El servidor y las claves (OpenAI, Cartesia, Claude, Upload-Post).
  2. Un vídeo normal (`prueba_real.py`): guion, voz, imágenes, montaje, rehacer
     dos imágenes con notas y Claude comprobando que se aplicaron.
  3. Un vídeo de foto con «Un espacio que cambia» (`prueba_relato.py`, el de la
     mampara): imagen base, estados, planos editándolas, el revisor y hasta DOS
     rondas de rehacer lo que marca, con Claude juzgando cada imagen.
  4. La portada: Claude propone tres y se usa la primera.
  5. Los textos de cada red (con emojis) y el SEO real, y Claude los juzga.
  6. PUBLICAR de verdad en las redes elegidas y esperar a que salgan.

EL TOPE vale para todo: antes de cada cosa que se paga se mira lo gastado en
los vídeos de la prueba; la parte 3 recibe lo que queda. La portada, los
textos, el SEO y publicar no se pagan aparte (suscripción de Claude, cupo de
YouTube y las subidas del plan de Upload-Post).

No toca tus vídeos: los de prueba se quedan en tu Studio para que los veas. El
informe sale en la consola y en <proyectos>/_sistema/pruebas_reales/completa_<fecha>.json.
"""
import argparse
import datetime
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "herramientas"))

import prueba_real as PR  # noqa: E402
import revisar as RV      # noqa: E402

#: Las partes, su nombre y cuántos minutos suelen tardar (para la barra).
FASES = [
    ("claves", "El servidor y las claves", 1),
    ("basica", "Un vídeo normal de punta a punta", 20),
    ("relato", "Foto con «Un espacio que cambia»", 40),
    ("portada", "La portada", 3),
    ("textos", "Los textos de cada red y el SEO", 6),
    ("publicar", "Publicar de verdad", 10),
]

#: Lo que cuesta como mínimo la parte 2 (un vídeo de 30 s en calidad baja).
MINIMO_BASICA = 1.2
#: Lo mínimo que tiene que quedar del tope para la parte 3 (base, 2 estados,
#: ~12 planos y alguna imagen rehecha, en foto).
MINIMO_RELATO = 1.5
#: Los temas del vídeo de foto (escenarios de prueba_relato.py).
TEMAS = [("a", "Un baño: la mampara que choca con el inodoro (diseño de interiores)"),
         ("c", "Una sala de eventos: vacía → consolas montadas → torneo (EstadoPlay)")]

#: Las redes que se escriben si no se publica en ninguna.
REDES_SIN_PUBLICAR = ["youtube", "tiktok", "instagram"]
#: Los estados de un envío que todavía pueden cambiar (pasos/publicar.py).
PENDIENTES = ("enviando", "programado", "publicando", "comprobar")

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⭕←-⇿✀-➿]")


def _carpeta(proyectos):
    return PR._carpeta_informes(proyectos)                      # noqa: SLF001


def _ruta_estado(proyectos):
    return os.path.join(_carpeta(proyectos), "en_curso_completa.json")


def _ruta_config(proyectos):
    return os.path.join(_carpeta(proyectos), "completa_config.json")


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    os.replace(ruta + ".tmp", ruta)


def informe_de_hijo(carpeta, patron, desde):
    """El informe más nuevo que dejó una prueba hija desde `desde` (epoch)."""
    mejores = []
    for nombre in os.listdir(carpeta) if os.path.isdir(carpeta) else []:
        if not re.fullmatch(patron, nombre):
            continue
        ruta = os.path.join(carpeta, nombre)
        try:
            momento = os.path.getmtime(ruta)
        except OSError:
            continue
        if momento >= desde - 5:
            mejores.append((momento, ruta))
    return _leer_json(max(mejores)[1]) if mejores else None


# ------------------------------------------------------------- preparar

def _preguntar(texto, defecto=""):
    try:
        respuesta = input(texto).strip()
    except EOFError:
        respuesta = ""
    return respuesta or defecto


def preparar(api, proyectos, args):
    """Antes de lanzarla (en la consola, con la persona delante): en qué cuenta
    se publica y el tope. Escribe completa_config.json. -> 0 si sigue."""
    print("LA PRUEBA COMPLETA DEL STUDIO")
    print(f"Vídeos de verdad, de punta a punta. Tope de gasto: {args.tope:.2f} $. Tarda 1-2 horas.\n")
    codigo, _s = api.get("/api/salud")
    if codigo != 200:
        print(f"El Studio no contesta (HTTP {codigo}): mira  asvs estado")
        return 2
    config = {"tope": args.tope, "publicar": None, "escenario": "a",
              "creada": datetime.datetime.now().isoformat()}
    # EL TEMA DEL VÍDEO DE FOTO, que es el que se publica: que pegue con la cuenta
    print("¿De qué trata el vídeo de foto (el que se publica)?")
    for i, (_letra, titulo) in enumerate(TEMAS, 1):
        print(f"  {i}) {titulo}")
    tema = _preguntar("Escribe el número (Enter = 1): ", "1")
    if not tema.isdigit() or not 1 <= int(tema) <= len(TEMAS):
        print("No es una opción. No he lanzado nada.")
        return 1
    config["escenario"] = TEMAS[int(tema) - 1][0]
    print()
    if args.sin_publicar:
        print("Sin publicar: los textos y el SEO se prueban, pero no se sube nada.")
        _escribir_json(_ruta_config(proyectos), config)
        return 0
    _c, estado = api.get("/api/publicar/estado")
    if not ((estado or {}).get("clave") or {}).get("puesta"):
        print("No hay clave de Upload-Post: la prueba sigue SIN publicar "
              "(ponla en Configuración para probar Publicar).")
        _escribir_json(_ruta_config(proyectos), config)
        return 0
    _c, lista = api.get("/api/publicar/proyectos")
    opciones = []
    print("Mirando qué cuentas tiene conectadas cada proyecto…")
    for fila in (lista or {}).get("proyectos") or []:
        if not ((fila.get("ajustes") or {}).get("perfil")):
            continue
        codigo, vistas = api.post(f"/api/publicar/proyectos/{fila['id']}/cuentas")
        cuentas = (((vistas or {}).get("ajustes") or {}).get("cuentas")) or {}
        redes = [r for r, c in cuentas.items() if c and not c.get("reconectar")]
        if codigo == 200 and redes:
            opciones.append({"cid": fila["id"], "nombre": fila.get("nombre") or fila["id"],
                             "perfil": fila["ajustes"]["perfil"], "redes": redes,
                             "cuentas": {r: cuentas[r] for r in redes}})
    if not opciones:
        print("Ningún proyecto tiene cuentas conectadas en Upload-Post: la prueba sigue SIN publicar.")
        _escribir_json(_ruta_config(proyectos), config)
        return 0
    print("\n¿En qué cuenta publico el vídeo de prueba?")
    for i, o in enumerate(opciones, 1):
        detalle = ", ".join(f"{r} ({(o['cuentas'][r] or {}).get('usuario') or (o['cuentas'][r] or {}).get('nombre')})"
                            for r in o["redes"])
        print(f"  {i}) {o['nombre']} — {detalle}")
    print("  0) No publicar (solo textos y SEO)")
    eleccion = _preguntar("Escribe el número: ", "0")
    if not eleccion.isdigit() or not 0 <= int(eleccion) <= len(opciones):
        print("No es una opción. No he lanzado nada.")
        return 1
    if int(eleccion) == 0:
        _escribir_json(_ruta_config(proyectos), config)
        print("De acuerdo: sin publicar.")
        return 0
    elegida = opciones[int(eleccion) - 1]
    print(f"\nRedes de «{elegida['nombre']}»:")
    for i, r in enumerate(elegida["redes"], 1):
        print(f"  {i}) {r}")
    texto = _preguntar("¿En cuáles? Números separados por comas (Enter = todas): ", "")
    if texto:
        try:
            redes = [elegida["redes"][int(x) - 1] for x in re.split(r"[,\s]+", texto) if x]
        except (ValueError, IndexError):
            print("No entiendo esa lista. No he lanzado nada.")
            return 1
    else:
        redes = list(elegida["redes"])
    redes = list(dict.fromkeys(redes))
    print(f"\nSe va a PUBLICAR DE VERDAD un vídeo de prueba de 30 s en: {', '.join(redes)}"
          f" (cuenta de «{elegida['nombre']}»).")
    print("Saldrá como cualquier publicación tuya (en YouTube, con la privacidad de ese proyecto).")
    print("Puedes borrarlo después desde cada red.")
    if _preguntar("Escribe SI para confirmar: ").strip().upper() not in ("SI", "SÍ"):
        print("No confirmado. No he lanzado nada.")
        return 1
    config["publicar"] = {"cid": elegida["cid"], "nombre": elegida["nombre"],
                          "perfil": elegida["perfil"], "redes": redes}
    _escribir_json(_ruta_config(proyectos), config)
    print("\nListo. La prueba arranca ahora y corre aparte de esta consola.")
    return 0


# ------------------------------------------------------------- la prueba

class Progreso:
    """La barra de todas las partes: lo hecho, la parte en marcha y el gasto."""

    def __init__(self, est, gasto):
        self.est = est
        self.gasto = gasto              # () -> dólares gastados en los vídeos de prueba
        self.fase = ""
        self.t_fase = time.time()
        self.ultimo = 0.0

    def empieza(self, fase):
        self.fase = fase
        self.t_fase = time.time()

    def fraccion(self):
        total = sum(m for _f, _n, m in FASES)
        hecho = sum(m for f, _n, m in FASES if f in self.est["hechas"])
        if self.fase and self.fase not in self.est["hechas"]:
            previsto = next(m for f, _n, m in FASES if f == self.fase)
            hecho += min((time.time() - self.t_fase) / 60, 0.95 * previsto)
        return hecho / total

    def faltan_s(self):
        quedan = 0.0
        for f, _n, m in FASES:
            if f in self.est["hechas"]:
                continue
            if f == self.fase:
                quedan += max(0.05 * m, m - (time.time() - self.t_fase) / 60)
            else:
                quedan += m
        return quedan * 60

    def linea(self):
        numero = next((i for i, (f, _n, _m) in enumerate(FASES, 1) if f == self.fase), 0)
        nombre = next((n for f, n, _m in FASES if f == self.fase), "")
        try:
            gastado = self.gasto()
        except Exception:                                       # noqa: BLE001
            gastado = 0.0
        return (f"\n  {RV.barra(self.fraccion())} · parte {numero} de {len(FASES)}: {nombre}"
                f"\n     lleva {RV.minutos(time.time() - float(self.est['inicio']))}"
                f" · faltan ≈ {RV.minutos(self.faltan_s())}"
                f" · gastado {gastado:.2f} $ de {float(self.est['tope']):.2f} $")

    def latido(self, forzar=False, cada=60):
        if forzar or time.time() - self.ultimo >= cada:
            print(self.linea(), flush=True)
            self.ultimo = time.time()


def correr_hijo(orden, progreso, cada=60):
    """Corre una prueba hija enseñando lo que dice (con sangría) y la barra
    cada minuto. -> código de salida."""
    proceso = subprocess.Popen(orden, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    cola = queue.Queue()

    def leer():
        for linea in proceso.stdout:
            cola.put(linea.rstrip("\n"))
        cola.put(None)

    threading.Thread(target=leer, daemon=True).start()
    while True:
        try:
            linea = cola.get(timeout=5)
        except queue.Empty:
            progreso.latido(cada=cada)
            continue
        if linea is None:
            break
        print(f"   │ {linea}", flush=True)
        progreso.latido(cada=cada)
    return proceso.wait()


def main():
    ap = argparse.ArgumentParser(description="La prueba completa del Studio")
    ap.add_argument("--api", default=f"http://127.0.0.1:{os.environ.get('PUERTO', '8110')}")
    ap.add_argument("--tope", type=float, default=5.0)
    ap.add_argument("--preparar", action="store_true",
                    help="pregunta en qué cuenta publicar (con la persona delante) y sale")
    ap.add_argument("--sin-publicar", action="store_true")
    ap.add_argument("--seguir", action="store_true",
                    help="si hay una prueba completa cortada, la sigue donde se quedó")
    ap.add_argument("--cada", type=float, default=60.0, help=argparse.SUPPRESS)
    # PARA PROBAR ESTA PRUEBA en local, con motores simulados
    ap.add_argument("--sin-claves", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--espera-publicar", type=float, default=1800, help=argparse.SUPPRESS)
    ap.add_argument("--hijos", default=os.path.join(RAIZ, "herramientas"), help=argparse.SUPPRESS)
    ap.add_argument("--pausa", type=float, default=5.0, help=argparse.SUPPRESS)
    args = ap.parse_args()
    api = PR.Api(args.api)
    proyectos = os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos")
    carpeta = _carpeta(proyectos)
    os.makedirs(carpeta, exist_ok=True)
    if args.preparar:
        return preparar(api, proyectos, args)

    est = _leer_json(_ruta_estado(proyectos)) if args.seguir else None
    if est:
        print("RETOMANDO LA PRUEBA COMPLETA donde se cortó (lo hecho no se repite ni se paga otra vez)")
    else:
        config = _leer_json(_ruta_config(proyectos)) or {}
        est = {"inicio": time.time(), "tope": float(config.get("tope") or args.tope),
               "publicar": None if args.sin_publicar else config.get("publicar"),
               "escenario": config.get("escenario") if config.get("escenario") in ("a", "b", "c") else "a",
               "hechas": [], "empezadas": {}, "lineas": [], "videos": {}, "resultados": {}}
        print(f"LA PRUEBA COMPLETA DEL STUDIO (tope {est['tope']:.2f} $; no toca tus vídeos)")
        if est["publicar"]:
            p = est["publicar"]
            print(f"Publica de verdad en {', '.join(p['redes'])} (cuenta de «{p['nombre']}»).")
        else:
            print("Sin publicar: los textos y el SEO se prueban, pero no se sube nada.")
    tope = float(est["tope"])

    def guardar():
        est["lineas"] = informe.lineas
        try:
            _escribir_json(_ruta_estado(proyectos), est)
        except OSError:
            pass

    informe = PR.Informe(guardar)
    informe.cargar(est.get("lineas"), set(est.get("hechas") or []))

    def gastado():
        total = 0.0
        for pid in set(est["videos"].values()):
            _c, c = api.get(f"/api/proyectos/{pid}/coste")
            total += float((c or {}).get("total_usd") or 0)
        return total

    progreso = Progreso(est, gastado)

    def parte(fase):
        """¿Hay que hacer esta parte? Si sí, la empieza (y limpia sus líneas)."""
        if fase in est["hechas"]:
            return False
        informe.parte = fase
        informe.lineas = [l for l in informe.lineas if l.get("parte") != fase]
        progreso.empieza(fase)
        PR.seccion(f"{next(i for i, (f, _n, _m) in enumerate(FASES, 1) if f == fase)}. "
                   f"{next(n for f, n, _m in FASES if f == fase)}")
        progreso.latido(forzar=True)
        return True

    def hecha(fase):
        if fase not in est["hechas"]:
            est["hechas"].append(fase)
        guardar()

    def cerrar():
        return _cerrar(informe, proyectos, est, gastado)

    # 1. EL SERVIDOR Y LAS CLAVES (siempre: es gratis y pueden haber cambiado)
    est["hechas"] = [f for f in est["hechas"] if f != "claves"]
    if parte("claves"):
        codigo, _s = api.get("/api/salud")
        if not informe.comprueba(codigo == 200, "el Studio contesta", f"HTTP {codigo}"):
            return cerrar()
        _c, claves = api.post("/api/claves/probar", {"claude": True})
        estados = {p.get("proveedor"): p for p in (claves or {}).get("pruebas") or []}
        for prov in ("openai", "cartesia", "claude"):
            p = estados.get(prov) or {}
            informe.comprueba(p.get("estado") in ("ok", None), f"clave de {prov}",
                              f"{p.get('estado')}: {p.get('mensaje')}", solo_aviso=args.sin_claves)
        if est["publicar"]:
            _c, r = api.post("/api/publicar/probar")
            informe.comprueba(bool((r or {}).get("ok")), "Upload-Post acepta la clave",
                              str((r or {}).get("mensaje")))
        if not args.sin_claves and any((estados.get(x) or {}).get("estado") not in ("ok", None)
                                       for x in ("openai", "cartesia")):
            informe.apunta("fallo", "sin las claves de OpenAI y Cartesia no se puede seguir")
            return cerrar()
        hecha("claves")

    # 2 y 3. LAS PRUEBAS QUE YA HABÍA, como hijas: cada una con su retomar
    def hija(fase, guion, patron, extra):
        t0 = float(est["empezadas"].get(fase) or 0)
        seguir = bool(t0)
        if not t0:
            t0 = time.time()
            est["empezadas"][fase] = t0
            guardar()
        orden = [sys.executable, "-u", os.path.join(args.hijos, guion),
                 "--api", args.api] + extra + (["--seguir"] if seguir else []) \
            + (["--sin-claves"] if args.sin_claves else [])
        codigo = correr_hijo(orden, progreso, cada=args.cada)
        datos = informe_de_hijo(carpeta, patron, t0)
        return codigo, datos

    if parte("basica"):
        if gastado() + MINIMO_BASICA > tope:
            informe.apunta("fallo", "PARADA POR EL TOPE antes del vídeo normal",
                           f"gastado {gastado():.2f} $ + ≈ {MINIMO_BASICA:.2f} $ pasaría de {tope:.2f} $")
            return cerrar()
        codigo, datos = hija("basica", "prueba_real.py", r"\d{4}-\d{2}-\d{2}_\d{4}\.json", [])
        if datos and datos.get("proyecto"):
            est["videos"]["basica"] = datos["proyecto"]
        est["resultados"]["basica"] = _resumen_hijo(datos, codigo)
        informe.comprueba(bool(datos) and not datos.get("fallos"),
                          f"el vídeo normal sale bien ({_texto_resumen(datos)})",
                          "mira sus líneas arriba (│)" if datos else f"la prueba terminó sin informe (código {codigo})")
        hecha("basica")

    if parte("relato"):
        queda = round(tope - gastado(), 2)
        if queda < MINIMO_RELATO:
            informe.apunta("fallo", "PARADA POR EL TOPE antes de la prueba de foto",
                           f"quedan {queda:.2f} $ y hacen falta al menos {MINIMO_RELATO:.2f} $")
        else:
            codigo, datos = hija("relato", "prueba_relato.py", r"relato_\d{4}-\d{2}-\d{2}_\d{4}\.json",
                                 ["--solo", est.get("escenario") or "a", "--tope", f"{queda:.2f}"])
            pid = ((datos or {}).get("proyectos") or {}).get(est.get("escenario") or "a")
            if pid:
                est["videos"]["relato"] = pid
            est["resultados"]["relato"] = _resumen_hijo(datos, codigo)
            informe.comprueba(bool(datos) and not datos.get("fallos"),
                              f"la prueba de foto sale bien ({_texto_resumen(datos)})",
                              "mira sus líneas arriba (│)" if datos
                              else f"la prueba terminó sin informe (código {codigo})")
        hecha("relato")

    # EL VÍDEO PARA LO QUE SIGUE: el de foto (vertical, el que se publica en
    # redes) si quedó montado; si no, el normal
    if not est.get("para_publicar"):
        for clave in ("relato", "basica"):
            pid = est["videos"].get(clave)
            if not pid:
                continue
            codigo, ficha = api.get(f"/api/publicar/videos/{pid}")
            if codigo == 200 and (ficha or {}).get("montado"):
                est["para_publicar"] = pid
                break
        guardar()
    pid = est.get("para_publicar")
    if not pid:
        informe.apunta("fallo", "no hay ningún vídeo de prueba montado: no se puede probar "
                       "portada, textos ni publicar")
        return cerrar()

    # 4. LA PORTADA: Claude propone tres y se usa la primera (gratis)
    if parte("portada"):
        codigo, r = api.post(f"/api/publicar/videos/{pid}/portada/proponer", {})
        rid = (r or {}).get("id")
        propuesta = {}
        if informe.comprueba(codigo == 202 and rid, "se piden tres portadas a Claude", f"HTTP {codigo}: {r}"):
            limite = time.time() + 600
            while time.time() < limite:
                time.sleep(args.pausa)
                progreso.latido(cada=args.cada)
                _c, propuesta = api.get(f"/api/publicar/videos/{pid}/portada/proponer/{rid}")
                if (propuesta or {}).get("estado") in ("listo", "error"):
                    break
            propuestas = (propuesta or {}).get("propuestas") or []
            if informe.comprueba(bool(propuestas), f"Claude propone {len(propuestas)} portadas",
                                 str((propuesta or {}).get("error") or (propuesta or {}).get("estado"))):
                codigo, ficha = api.post(f"/api/publicar/videos/{pid}/portada/usar",
                                         {"diseno": propuestas[0]["diseno"]})
                informe.comprueba(codigo == 200 and bool(((ficha or {}).get("portada") or {}).get("imagen")),
                                  "la primera queda como portada del vídeo", f"HTTP {codigo}: {str(ficha)[:200]}")
        hecha("portada")

    # 5. LOS TEXTOS DE CADA RED Y EL SEO (gratis: suscripción de Claude y cupo de YouTube)
    redes = list((est["publicar"] or {}).get("redes") or REDES_SIN_PUBLICAR)
    if parte("textos"):
        if est["publicar"] and not est.get("movido"):
            # el vídeo, al proyecto de la cuenta elegida: sus textos, su perfil
            # y sus redes son los de ESE proyecto
            codigo, r = api.put(f"/api/clientes/videos/{pid}", {"cliente": est["publicar"]["cid"]})
            if not informe.comprueba(codigo == 200, f"el vídeo pasa al proyecto «{est['publicar']['nombre']}»",
                                     f"HTTP {codigo}: {r}"):
                return cerrar()
            est["movido"] = True
            guardar()
        codigo, r = api.put(f"/api/publicar/videos/{pid}", {"redes": redes})
        informe.comprueba(codigo == 200, f"se eligen las redes: {', '.join(redes)}", f"HTTP {codigo}: {str(r)[:200]}")
        codigo, r = api.post(f"/api/publicar/videos/{pid}/textos", {"redes": redes})
        ficha = {}
        if informe.comprueba(codigo == 202, "Claude escribe los textos de cada red", f"HTTP {codigo}: {r}"):
            ficha = _esperar_ficha(api, pid, lambda f: not f.get("escribiendo"), 900, progreso,
                                   args.cada, args.pausa)
            informe.comprueba(not (ficha or {}).get("error_textos"), "los textos terminan sin error",
                              str((ficha or {}).get("error_textos")))
        textos = (ficha or {}).get("textos") or {}
        for red in redes:
            t = textos.get(red) or {}
            cuerpo = " ".join(str(t.get(k) or "") for k in ("titulo", "descripcion"))
            informe.comprueba(bool(cuerpo.strip()), f"{red}: hay texto", "vacío")
            informe.comprueba(bool(EMOJI.search(cuerpo)), f"{red}: lleva emojis", "sin ningún emoji",
                              solo_aviso=True)
            rotas = PR.LETRAS_ROTAS.search(cuerpo)
            informe.comprueba(not rotas, f"{red}: sin letras rotas", f"«{rotas.group(0) if rotas else ''}»")
        # el SEO real (autocompletado y, con clave, la API de YouTube)
        codigo, r = api.post(f"/api/publicar/videos/{pid}/seo/investigar")
        if informe.comprueba(codigo == 202, "se investigan las búsquedas de verdad (SEO)", f"HTTP {codigo}: {r}"):
            ficha = _esperar_ficha(api, pid, lambda f: "investigar" not in ((f.get("seo") or {}).get("trabajando") or {}),
                                   600, progreso, args.cada, args.pausa)
            seo = (ficha or {}).get("seo") or {}
            errores = seo.get("errores") or {}
            informe.comprueba(bool(seo.get("real")) and not errores.get("investigar"),
                              f"el SEO trae búsquedas para «{seo.get('palabra') or '?'}»",
                              str(errores.get("investigar") or "sin resultados"), solo_aviso=True)
        # el juez: ¿se leen bien y enganchan?
        if textos:
            try:
                veredicto = PR._juez(                               # noqa: SLF001
                    "Estos son los textos de un vídeo corto para cada red social:\n"
                    + json.dumps({r_: textos.get(r_) for r_ in redes}, ensure_ascii=False)[:6000]
                    + "\nJuzga como un community manager exigente: 'atractivo' (el título engancha), "
                    "'emojis' (llevan emojis a juego con el vídeo), 'ortografia' (sin faltas ni frases "
                    "raras) y 'formato' (cada uno encaja en su red). Devuelve SOLO "
                    '{"atractivo": "si"|"no", "emojis": "si"|"no", "ortografia": "si"|"no", '
                    '"formato": "si"|"no", "por_que": "<una frase>"}', os.path.join(proyectos, pid))
            except Exception as fallo:                               # noqa: BLE001
                veredicto = {"por_que": f"no se pudo preguntar a Claude: {fallo}"}
            est["resultados"]["juez_textos"] = veredicto
            for clave, que in (("atractivo", "el título engancha"), ("emojis", "los emojis van a juego"),
                               ("ortografia", "sin faltas"), ("formato", "cada texto encaja en su red")):
                informe.comprueba((veredicto or {}).get(clave) in ("si", "sí"), f"Claude: {que}",
                                  str((veredicto or {}).get("por_que")), solo_aviso=True)
        hecha("textos")

    # 6. PUBLICAR DE VERDAD
    if parte("publicar"):
        if not est["publicar"]:
            informe.apunta("ok", "sin publicar (así se eligió al empezar)")
            hecha("publicar")
            return cerrar()
        if not est.get("enviado"):
            codigo, r = api.post(f"/api/publicar/videos/{pid}/enviar",
                                 {"redes": redes, "modo": "ahora", "confirmado": True})
            if not informe.comprueba(codigo == 202, f"se envía a {', '.join(redes)}",
                                     f"HTTP {codigo}: {(r or {}).get('detail') or (r or {}).get('error') or r}"):
                hecha("publicar")
                return cerrar()
            est["enviado"] = time.time()
            guardar()
        limite = time.time() + args.espera_publicar
        envios = []
        while time.time() < limite:
            api.post("/api/publicar/refrescar", {})
            _c, ficha = api.get(f"/api/publicar/videos/{pid}")
            envios = [e for e in (ficha or {}).get("envios") or [] if e.get("red") in redes]
            ultimos = {}
            for e in envios:              # el más nuevo por red (vienen del más nuevo al más viejo)
                if e.get("red") not in ultimos:
                    ultimos[e["red"]] = e
            envios = list(ultimos.values())
            if envios and all(e.get("estado") not in PENDIENTES for e in envios):
                break
            progreso.latido(cada=args.cada)
            time.sleep(4 * args.pausa)
        por_red = {e.get("red"): e for e in envios}
        resumen = {}
        for red in redes:
            e = por_red.get(red) or {}
            resumen[red] = {"estado": e.get("estado"), "url": e.get("url"), "error": e.get("error")}
            informe.comprueba(e.get("estado") == "publicado",
                              f"{red}: publicado" + (f" → {e.get('url')}" if e.get("url") else ""),
                              f"{e.get('estado') or 'sin envío'}: {e.get('error') or ''}".strip(),
                              solo_aviso=e.get("estado") in PENDIENTES)
        est["resultados"]["publicar"] = resumen
        hecha("publicar")
    return cerrar()


def _esperar_ficha(api, pid, condicion, limite_s, progreso, cada, pausa=5.0):
    """Pregunta por la ficha de Publicar hasta que se cumple `condicion`."""
    fin = time.time() + limite_s
    ficha = {}
    while time.time() < fin:
        time.sleep(pausa)
        progreso.latido(cada=cada)
        codigo, ficha = api.get(f"/api/publicar/videos/{pid}")
        if codigo == 200 and condicion(ficha or {}):
            return ficha
    return ficha


def _resumen_hijo(datos, codigo):
    if not datos:
        return {"codigo": codigo, "veredicto": "sin informe"}
    return {"veredicto": datos.get("veredicto"), "fallos": datos.get("fallos"),
            "avisos": datos.get("avisos"), "minutos": datos.get("minutos"),
            "gastado_usd": datos.get("gastado_usd"),
            "fallidas": [l for l in datos.get("lineas") or [] if l.get("estado") == "fallo"][:12]}


def _texto_resumen(datos):
    if not datos:
        return "sin informe"
    return f"{datos.get('fallos', 0)} fallo(s), {datos.get('avisos', 0)} aviso(s)"


def _cerrar(informe, proyectos, est, gastado):
    try:
        total = gastado()
    except Exception:                                           # noqa: BLE001
        total = 0.0
    minutos_ = (time.time() - float(est["inicio"])) / 60
    veredicto = "APROBADA" if not informe.fallos else "CON FALLOS"
    print("\n" + "=" * 60)
    print(f"PRUEBA COMPLETA {veredicto}: {informe.fallos} fallo(s), {informe.avisos} aviso(s), "
          f"{minutos_:.0f} min, gastado {total:.2f} $ de {float(est['tope']):.2f} $")
    print("=" * 60)
    for clave, pid in est["videos"].items():
        print(f"  vídeo {clave}: «{pid}» (se queda en tu Studio)")
    fallos = [l for l in informe.lineas if l.get("estado") == "fallo"]
    for clave in ("basica", "relato"):
        fallos += [dict(l, que=f"[{clave}] {l.get('que')}")
                   for l in ((est["resultados"].get(clave) or {}).get("fallidas") or [])]
    if fallos:
        print("\nLO QUE HA FALLADO:")
        for l in fallos:
            print(f"  ✗ {l.get('que')}" + (f"  — {l.get('detalle')}" if l.get("detalle") else ""))
        print("\nManda este informe en el chat del Studio para arreglarlo.")
    publicado = est["resultados"].get("publicar") or {}
    if any(v.get("url") for v in publicado.values()):
        print("\nLO PUBLICADO (bórralo de cada red si no lo quieres dejar):")
        for red, v in publicado.items():
            if v.get("url"):
                print(f"  {red}: {v['url']}")
    carpeta = _carpeta(proyectos)
    try:
        ruta = os.path.join(carpeta, "completa_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".json")
        _escribir_json(ruta, {"veredicto": veredicto, "fallos": informe.fallos, "avisos": informe.avisos,
                              "minutos": round(minutos_, 1), "gastado_usd": round(total, 3),
                              "tope": est["tope"], "publicar": est.get("publicar"),
                              "videos": est["videos"], "resultados": est["resultados"],
                              "lineas": informe.lineas})
        print(f"\nInforme guardado en {ruta}")
    except OSError as fallo:
        print(f"(no se ha podido guardar el informe: {fallo})")
    try:
        os.remove(_ruta_estado(proyectos))
    except OSError:
        pass
    return 0 if not informe.fallos else 1


if __name__ == "__main__":
    sys.exit(main())

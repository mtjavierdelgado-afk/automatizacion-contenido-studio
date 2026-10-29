#!/usr/bin/env python3
"""LA REVISIÓN GRATIS: todas las pruebas del Studio, con barra de progreso.

    asvs revisar            (en la consola del VPS, como root)
    asvs revisar ver        vuelve a enseñar la que está en marcha

Es `pruebas.sh` (las suites y el recorrido botón por botón, con motores
simulados: NO gasta nada), pero:

  - corre como el usuario del servicio (`asvs` lo lanza así): como root, Edge no
    arranca y la cuenta de Claude no tiene sesión, y salían fallos que no lo eran
    (22-10-2026);
  - va desligada de la consola, como `asvs probar`: si la consola se corta, sigue;
  - enseña una barra con cuántas suites van, cuánto lleva y cuánto falta (con lo
    que tardó cada suite la última vez);
  - y al final da un informe en español: qué salió bien, qué falló y, para los
    fallos que se conocen, qué hacer.

La lista de suites NO se repite aquí: se lee de `pruebas.sh`, que es la que manda.
El informe queda en <proyectos>/_sistema/pruebas_reales/revisar_<fecha>.txt.
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

#: Lo que prueba cada suite, para que el informe se entienda sin abrir el código.
QUE_PRUEBA = {
    "prueba_api.py": "el servidor: todas las rutas de la API",
    "prueba_coste_capturas.py": "el coste y las capturas",
    "prueba_clases_css.py": "que cada clase de la pantalla tenga su estilo",
    "prueba_textos.py": "los textos de la pantalla",
    "nucleo/prueba_nucleo.py": "el núcleo: estado, versiones y firmas",
    "nucleo/prueba_adversarial.py": "el núcleo frente a datos rotos",
    "nucleo/prueba_manifiestos.py": "los manifiestos de cada versión",
    "pasos/prueba_ajustes.py": "Configuración",
    "pasos/prueba_login.py": "que la cuenta de Claude del Studio deja entrar",
    "pasos/prueba_asistente.py": "el asistente (la burbuja)",
    "pasos/prueba_salud_cli.py": "la salud de la cuenta de Claude",
    "pasos/prueba_enrutar_estilo.py": "el reparto del estilo",
    "pasos/prueba_p1.py": "el material",
    "pasos/prueba_p2.py": "el brief",
    "pasos/prueba_p3.py": "el guion",
    "pasos/prueba_cta.py": "las llamadas a la acción",
    "pasos/prueba_pasos_guion.py": "guion de punta a punta (con Claude de verdad)",
    "pasos/prueba_marcas_tts.py": "las marcas de la voz",
    "pasos/prueba_pasos_voz.py": "la voz y su revisión",
    "pasos/prueba_pasos_visuales.py": "imágenes, rótulos y montaje del vídeo",
    "pasos/prueba_repaso.py": "las notas de repaso",
    "pasos/prueba_revisor.py": "el revisor de imágenes",
    "pasos/prueba_reglas_estilo.py": "las reglas del estilo",
    "pasos/prueba_portadas.py": "las portadas",
    "pasos/prueba_piezas.py": "las piezas del vídeo",
    "pasos/prueba_conservar.py": "que no se rehaga lo que ya está hecho",
    "pasos/prueba_encuadres.py": "los encuadres",
    "pasos/prueba_presets.py": "los estilos",
    "pasos/prueba_presets_light.py": "los estilos (pantalla de Crear)",
    "pasos/prueba_modo_foto.py": "el modo foto",
    "pasos/prueba_publicar.py": "Publicar",
    "pasos/prueba_parrilla.py": "la Parrilla",
    "pasos/prueba_cuentas.py": "analizar cuentas",
    "pasos/prueba_espacio_fijo.py": "el espacio fijo",
    "pasos/prueba_tipo_relato.py": "el tipo de relato",
    "pasos/prueba_seo_real.py": "el SEO real",
    "pasos/prueba_seo_canal.py": "el canal de YouTube",
    "pasos/prueba_dominios.py": "el negocio de cada estilo (dominios)",
    "pasos/prueba_guion_visual.py": "qué dibujan las imágenes (la voz o el guion)",
    "pasos/prueba_traducciones.py": "lo pedido al dibujante, en español",
    "pasos/prueba_quitar_planos.py": "quitar una imagen e igualar con la vecina",
    "pasos/prueba_insertar_planos.py": "insertar una imagen dentro de otra",
    "pasos/prueba_consumo_claude.py": "el medidor del cupo de Claude",
    "herramientas/prueba_herramientas_prueba.py": "estas mismas herramientas de prueba",
    "prueba_recorrido.py": "la pantalla entera, botón por botón",
}

#: Las variables del entorno que señalan DATOS de verdad del servicio: las
#: suites no deben verlas (cada una monta los suyos). Las de las herramientas
#: (ESTUDIO_EDGE, ESTUDIO_FFMPEG, ESTUDIO_FUENTES, ESTUDIO_LOTES…) sí pasan: sin
#: ESTUDIO_EDGE el navegador no arranca en el VPS (revisión del 22-10).
DATOS_DEL_SERVICIO = {
    "ESTUDIO_PROYECTOS", "ESTUDIO_SECRETOS", "ESTUDIO_AJUSTES", "ESTUDIO_PRESETS",
    "ESTUDIO_COSTE_GLOBAL", "ESTUDIO_BITACORA_GLOBAL", "ESTUDIO_ESTADISTICAS",
    "ESTUDIO_RECETAS", "ESTUDIO_TARIFAS", "ESTUDIO_ENV", "ESTUDIO_API",
    "ESTUDIO_PRONUNCIACIONES", "ESTUDIO_ASISTENTE_HISTORIAL", "ESTUDIO_METRICAS_AUTO",
}

#: Tiempo de una suite sin medida anterior (segundos).
POR_DEFECTO_S = 60
POR_DEFECTO_ESPECIALES = {"prueba_recorrido.py": 900, "prueba_api.py": 240,
                          "pasos/prueba_pasos_visuales.py": 240}

#: Fallos que se conocen y qué hacer con ellos (se buscan en el detalle).
PISTAS = [
    (re.compile(r"Running as root without --no-sandbox", re.I),
     "Se corrió como root y Edge no arranca así. Usa  asvs revisar  (corre como el usuario del Studio)."),
    (re.compile(r"Not logged in|Please run /login", re.I),
     "La cuenta de Claude del Studio no tiene sesión: entra en Configuración → Claude y vuelve a entrar."),
    (re.compile(r"No module named", re.I),
     "Falta una librería de Python: ejecuta  asvs actualizar  (la instala) y repite."),
    (re.compile(r"Address already in use|ya est[aá] en uso", re.I),
     "Un puerto estaba ocupado (otra prueba a la vez): espera a que termine y repite."),
    (re.compile(r"No space left|sin espacio", re.I),
     "El disco está lleno: libera espacio y repite."),
]


def barra(fraccion, ancho=24):
    """[██████░░░░░░] — la barra de progreso de las pruebas (también la usa
    prueba_completa)."""
    fraccion = max(0.0, min(1.0, float(fraccion or 0)))
    llenos = int(round(fraccion * ancho))
    return "[" + "█" * llenos + "░" * (ancho - llenos) + f"] {int(fraccion * 100):3d} %"


def hora_de_fin(segundos):
    """La hora (de Lima) a la que se espera terminar: «21:14»."""
    try:
        from zoneinfo import ZoneInfo                         # noqa: PLC0415
        ahora = datetime.datetime.now(ZoneInfo("America/Lima"))
    except Exception:                                           # noqa: BLE001
        ahora = datetime.datetime.now()
    return (ahora + datetime.timedelta(seconds=max(0, segundos))).strftime("%H:%M")


def lista_corta(nombres, cuantos=3):
    """«a, b, c y 5 más» (o «—» si no hay ninguno)."""
    nombres = list(nombres)
    if not nombres:
        return "—"
    texto = ", ".join(nombres[:cuantos])
    return texto + (f" y {len(nombres) - cuantos} más" if len(nombres) > cuantos else "")


def cuadro(titulo, filas):
    """El cuadro de progreso: una fila por cosa, con su etiqueta a la izquierda.

    ┌─ PROGRESO · … ───────
    │ Avance     [████░░░]  34 %
    │ Hecho      …
    └──────────────────────
    """
    ancho = 64
    salida = ["", "┌─ " + titulo + " " + "─" * max(3, ancho - len(titulo) - 3)]
    for etiqueta, valor in filas:
        if valor in (None, ""):
            continue
        primera, *resto = str(valor).split("\n")
        salida.append(f"│ {etiqueta:<10} {primera}")
        salida += [f"│ {'':<10} {r}" for r in resto]
    salida.append("└" + "─" * ancho)
    return "\n".join(salida)


def minutos(segundos):
    """«3 min», «menos de 1 min», «1 h 05 min»."""
    segundos = max(0, int(segundos))
    if segundos < 60:
        return "menos de 1 min"
    m = int(round(segundos / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def suites_de(pruebas_sh):
    """La lista `suites=( … )` de pruebas.sh, en su orden."""
    with open(pruebas_sh, encoding="utf-8") as fh:
        texto = fh.read()
    m = re.search(r"^suites=\((.*?)^\)", texto, re.S | re.M)
    if not m:
        raise RuntimeError("no encuentro la lista de suites en pruebas.sh")
    cuerpo = "\n".join(l.split("#", 1)[0] for l in m.group(1).splitlines())
    return cuerpo.split()


def _ruta_tiempos(carpeta):
    return os.path.join(carpeta, "revisar_tiempos.json")


def leer_tiempos(carpeta):
    try:
        with open(_ruta_tiempos(carpeta), encoding="utf-8") as fh:
            datos = json.load(fh)
        return {str(k): float(v) for k, v in datos.items()} if isinstance(datos, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def guardar_tiempos(carpeta, tiempos):
    ruta = _ruta_tiempos(carpeta)
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(tiempos, fh, indent=1)
        os.replace(ruta + ".tmp", ruta)
    except OSError:
        pass


def previsto(suite, tiempos):
    return float(tiempos.get(suite) or POR_DEFECTO_ESPECIALES.get(suite, POR_DEFECTO_S))


class Marcador:
    """Lleva la cuenta de las suites y pinta la barra."""

    def __init__(self, suites, tiempos, salida=print):
        self.suites = list(suites)
        # lo PREVISTO se congela al empezar (la barra no salta al medir); lo
        # medido va a `tiempos`, que es lo que se guarda para la próxima vez
        self.previstos = {s: previsto(s, tiempos) for s in self.suites}
        self.tiempos = dict(tiempos)
        self.hechas = []          # [(suite, estado, segundos)]
        self.inicio = time.time()
        self.t_suite = time.time()
        self.salida = salida

    @property
    def actual(self):
        return self.suites[len(self.hechas)] if len(self.hechas) < len(self.suites) else ""

    def fraccion(self):
        total = sum(self.previstos.values()) or 1
        hecho = sum(self.previstos.get(s, 0) for s, _e, _t in self.hechas)
        if self.actual:
            # la suite en marcha cuenta lo que lleva, sin pasar del 95 % de lo previsto
            hecho += min(time.time() - self.t_suite, 0.95 * self.previstos[self.actual])
        return min(1.0, hecho / total)

    def faltan_s(self):
        restantes = self.suites[len(self.hechas):]
        quedan = sum(self.previstos[s] for s in restantes)
        if self.actual:
            quedan -= min(time.time() - self.t_suite, 0.95 * self.previstos[self.actual])
        return max(0, quedan)

    def linea(self):
        """El cuadro de progreso: avance, tiempo, hecho, ahora y pendiente."""
        total = len(self.suites)
        bien = [s for s, e, _t in self.hechas if e == "OK"]
        mal = [s for s, e, _t in self.hechas if e == "FALLA"]
        cupo = [s for s, e, _t in self.hechas if e == "CUPO"]
        faltan = self.faltan_s()
        tiempo = f"lleva {minutos(time.time() - self.inicio)}"
        if self.actual:
            tiempo += f" · faltan ≈ {minutos(faltan)} · termina ≈ {hora_de_fin(faltan)}"
        hecho = f"{len(self.hechas)} de {total}"
        if self.hechas:
            hecho += f" · {len(bien)} bien ✓"
            if mal:
                hecho += f" · {len(mal)} con fallo ✗ ({lista_corta(QUE_PRUEBA.get(x, x) for x in mal)})"
            if cupo:
                hecho += f" · {len(cupo)} sin cupo de Claude"
        ahora = ""
        if self.actual:
            lleva = time.time() - self.t_suite
            ahora = (f"▶ {QUE_PRUEBA.get(self.actual, self.actual)}"
                     f" (lleva {minutos(lleva)} · suele tardar ≈ {minutos(max(60, self.previstos[self.actual]))})")
        pendientes = self.suites[len(self.hechas) + 1:]
        pendiente = (f"{len(pendientes)}: " + lista_corta(QUE_PRUEBA.get(x, x) for x in pendientes)
                     if pendientes else "nada")
        return cuadro(f"PROGRESO · revisión gratis · {len(self.hechas)}/{total}", [
            ("Avance", barra(self.fraccion())),
            ("Tiempo", tiempo),
            ("Hecho", hecho),
            ("Ahora", ahora or "terminando…"),
            ("Pendiente", pendiente),
        ])

    def termina(self, suite, estado):
        segundos = time.time() - self.t_suite
        self.hechas.append((suite, estado, segundos))
        self.tiempos[suite] = round(segundos, 1)
        self.t_suite = time.time()


RE_SUITE = re.compile(r"^(OK|FALLA|CUPO)\s+(\S+)")


def informe_final(marcador, detalles, analisis, codigo):
    """El texto final, en español llano."""
    bien = [s for s, e, _t in marcador.hechas if e == "OK"]
    mal = [s for s, e, _t in marcador.hechas if e == "FALLA"]
    cupo = [s for s, e, _t in marcador.hechas if e == "CUPO"]
    lineas = ["", "=" * 60,
              f"REVISIÓN {'TODO EN VERDE' if not mal and codigo == 0 else 'CON FALLOS'}"
              f" · {len(bien)} bien, {len(mal)} con fallos"
              + (f", {len(cupo)} sin cupo de Claude (no cuentan)" if cupo else "")
              + f" · {minutos(time.time() - marcador.inicio)}", "=" * 60]
    if mal:
        lineas.append("\nLO QUE HA FALLADO:")
        for s in mal:
            lineas.append(f"\n  ✗ {QUE_PRUEBA.get(s, s)}  ({s})")
            detalle = "\n".join(detalles.get(s) or [])
            pistas = [texto for patron, texto in PISTAS if patron.search(detalle)]
            for p in dict.fromkeys(pistas):
                lineas.append(f"    → {p}")
            for l in (detalles.get(s) or [])[-8:]:
                lineas.append(f"      {l.strip()[:160]}")
    if cupo:
        lineas.append("\nSIN CUPO DE CLAUDE (se repiten cuando se renueve): "
                      + ", ".join(QUE_PRUEBA.get(s, s) for s in cupo))
    # lo «de siempre» (22-10-2026): dos sospechosas de huerfanas_js (async y
    # fallar), dos atributos y la clase `anotacion` sin usar, que ya estaban
    raras = [l for l in analisis if not re.search(
        r"\bOK\b|NADIE LAS LLAMA: 0|0 NO \(|SOSPECHOSAS: 2|ATRIBUTOS QUE NO EXISTEN: 2|"
        r"^\S*css_sin_usar\.py\s+anotacion\b", l)]
    if raras:
        lineas.append("\nLAS HERRAMIENTAS DE ANÁLISIS DICEN (no siempre es un fallo):")
        lineas += [f"  · {l.strip()[:160]}" for l in raras]
    if not mal and codigo != 0:
        lineas.append("\npruebas.sh terminó con error sin decir qué prueba falló (mira las primeras "
                      "líneas del registro: ¿falta Python?).")
    elif not mal:
        lineas.append("\nTodo lo que se prueba sin gastar funciona. Para probar con vídeos de verdad: "
                      " asvs probar completo")
    else:
        lineas.append("\nSi no sabes qué hacer con un fallo, manda este informe en el chat del Studio.")
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser(description="Todas las pruebas gratis, con barra de progreso")
    ap.add_argument("--pruebas", default=os.path.join(RAIZ, "pruebas.sh"))
    ap.add_argument("--solo", default="", help="una suite suelta (como pruebas.sh --solo)")
    ap.add_argument("--cada", type=float, default=60.0, help="segundos entre barras (latido)")
    ap.add_argument("--informes", default="", help="carpeta del informe y de los tiempos "
                    "(por defecto <proyectos>/_sistema/pruebas_reales)")
    args = ap.parse_args()
    carpeta = args.informes or os.path.join(
        os.environ.get("ESTUDIO_PROYECTOS") or os.path.join(RAIZ, "proyectos"),
        "_sistema", "pruebas_reales")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("AVISO: corres como root. Edge no arranca así y la cuenta de Claude no tiene "
              "sesión: usa  asvs revisar  (corre como el usuario del Studio).", flush=True)
    suites = [args.solo] if args.solo else suites_de(args.pruebas)
    tiempos = leer_tiempos(carpeta)
    marcador = Marcador(suites, tiempos)
    total_previsto = sum(previsto(s, tiempos) for s in suites)
    print(f"LA REVISIÓN DEL STUDIO: {len(suites)} pruebas, gratis (motores simulados).", flush=True)
    print(f"Tardará unos {minutos(total_previsto)}"
          + (" (lo que tardó la última vez)." if tiempos else " (primera vez: es una estimación)."),
          flush=True)
    print(marcador.linea(), flush=True)

    orden = ["bash", args.pruebas] + (["--solo", args.solo] if args.solo else [])
    # LAS SUITES NO VEN EL ENTORNO DEL SERVICIO: cada una monta sus datos de
    # prueba, y con ESTUDIO_PROYECTOS, ESTUDIO_SECRETOS o ESTUDIO_AJUSTES del
    # servicio puestos una suite despistada escribiria en los de verdad
    entorno = {k: v for k, v in os.environ.items() if k not in DATOS_DEL_SERVICIO
               and not k.startswith("ESTUDIO_BANCO")}
    proceso = subprocess.Popen(orden, cwd=os.path.dirname(os.path.abspath(args.pruebas)), env=entorno,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    cola = queue.Queue()

    def leer():
        for linea in proceso.stdout:
            cola.put(linea.rstrip("\n"))
        cola.put(None)

    threading.Thread(target=leer, daemon=True).start()
    detalles, analisis = {}, []
    ultima_falla = None
    ultima_barra = time.time()
    while True:
        try:
            linea = cola.get(timeout=5)
        except queue.Empty:
            if time.time() - ultima_barra >= args.cada:
                print(marcador.linea(), flush=True)
                ultima_barra = time.time()
            continue
        if linea is None:
            break
        m = RE_SUITE.match(linea)
        if m:
            estado, suite = m.group(1), m.group(2)
            marcador.termina(suite, estado)
            marca = {"OK": "✓", "FALLA": "✗", "CUPO": "·"}[estado]
            print(f"  {marca} {QUE_PRUEBA.get(suite, suite)}", flush=True)
            ultima_falla = suite if estado == "FALLA" else None
            print(marcador.linea(), flush=True)
            ultima_barra = time.time()
        elif linea.startswith("ANAL "):
            analisis.append(linea[5:].strip())
            ultima_falla = None
        elif ultima_falla and linea.startswith("        "):
            detalles.setdefault(ultima_falla, []).append(linea)
        elif linea.startswith("interprete:") or not linea.strip():
            continue
    codigo = proceso.wait()
    guardar_tiempos(carpeta, marcador.tiempos)
    texto = informe_final(marcador, detalles, analisis, codigo)
    print(texto, flush=True)
    try:
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, "revisar_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".txt")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto.lstrip() + "\n")
        print(f"\nInforme guardado en {ruta}", flush=True)
    except OSError as fallo:
        print(f"(no se ha podido guardar el informe: {fallo})", flush=True)
    return 0 if codigo == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

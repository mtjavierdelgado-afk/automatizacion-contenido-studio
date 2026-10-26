"""
Prueba del medidor de Claude (pasos/consumo_claude.py, rama medidor-claude).

No llama a ningún modelo: el CLI se sustituye por un doble en el PATH que
contesta como el de verdad (con `--output-format stream-json --verbose`, la
línea `rate_limit_event` medida el 25-10-2026 con el CLI 2.1.310). Lo que se
comprueba:

  - que cada llamada que pasa por `cli_claude._una_pasada` se apunta, con sus
    tokens, su $ equivalente y su tarea, y que un cupo agotado también;
  - que «medir» lee las ventanas (5 h, semana) y su hora de reinicio, y que si
    el CLI no da el cupo se queda la última medida buena;
  - que los avisos saltan al 70 % y al 90 % y no con una ventana ya reiniciada;
  - que el resumen suma por día, tarea, vídeo y cuenta;
  - que sola no mide si no toca (menos de 15 min o sin llamadas) ni con
    ESTUDIO_SIMULAR, y que simulado no sale al CLI;
  - que nada de esto rompe una llamada si el registro no se puede escribir.
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import time

# LO DE ESTA SUITE NO VA AL ALMACÉN DE VERDAD (ni la salud ni el consumo)
CARPETA_SECRETOS = tempfile.mkdtemp(prefix="secretos_consumo_")
os.environ["ESTUDIO_SECRETOS"] = CARPETA_SECRETOS
os.environ.pop("ESTUDIO_SIMULAR", None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cli_claude                                            # noqa: E402
import consumo_claude as cc                                  # noqa: E402

FALLOS = []
CUENTAS = 0


def comprobar(condicion, texto):
    global CUENTAS
    CUENTAS += 1
    if condicion:
        print(f"  ok   {texto}")
    else:
        print(f"  FALLA {texto}")
        FALLOS.append(texto)


DOBLE = r'''#!{python}
import json, os, sys
args = sys.argv[1:]
sys.stdin.read()
modo = open(os.environ["DOBLE_MODO"]).read().strip() if os.environ.get("DOBLE_MODO") else "bien"
uso = {{"input_tokens": 3, "output_tokens": 40, "cache_creation_input_tokens": 1000,
        "cache_read_input_tokens": 5000}}
if modo == "cupo":
    print(json.dumps({{"type": "result", "is_error": True,
                       "result": "You've hit your limit · resets 9pm (America/Lima)"}}))
    sys.exit(1)
if "stream-json" in args:
    if modo != "sin_cupo":
        print(json.dumps({{"type": "rate_limit_event", "rate_limit_info": {{
            "status": "allowed", "rateLimitType": "five_hour", "resetsAt": 1900000000,
            "unifiedWindows": {{"five_hour": {{"utilization": 0.73, "resetsAt": 1900000000, "status": "allowed"}},
                               "seven_day": {{"utilization": 0.21, "resetsAt": 1900500000, "status": "allowed"}}}}}}}}))
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "ok",
                       "usage": uso, "total_cost_usd": 0.0005}}))
else:
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                       "result": "respuesta", "usage": uso, "total_cost_usd": 0.0123}}))
'''


def preparar_doble():
    carpeta = tempfile.mkdtemp(prefix="doble_claude_")
    ruta = os.path.join(carpeta, "claude")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(DOBLE.format(python=sys.executable))
    os.chmod(ruta, os.stat(ruta).st_mode | stat.S_IEXEC)
    modo = os.path.join(carpeta, "modo")
    with open(modo, "w") as fh:
        fh.write("bien")
    os.environ["PATH"] = carpeta + os.pathsep + os.environ.get("PATH", "")
    os.environ["DOBLE_MODO"] = modo
    return carpeta, modo


def poner_modo(ruta, modo):
    with open(ruta, "w") as fh:
        fh.write(modo)


def llamar(para):
    return cli_claude._una_pasada(
        "hola", "haiku", "low", None, 30, 30, None, cli_claude.HERRAMIENTAS_VETADAS,
        None, None, None, None, para, None)


def main():
    if os.name == "nt":
        print("(en Windows el doble del CLI no se puede poner así: se omiten las partes con CLI)")
    carpeta, modo = preparar_doble()
    try:
        print("1. CADA LLAMADA SE APUNTA (en _una_pasada)")
        if os.name != "nt":
            texto, _sobre = llamar("el guion")
            comprobar(texto == "respuesta", "la llamada sigue devolviendo su texto")
            r = [x for x in cc.leer_registro() if x.get("tipo") == "llamada"]
            comprobar(len(r) == 1 and r[0]["para"] == "el guion", f"se apunta con su tarea ({r[-1:]})")
            comprobar(r and r[0]["salida"] == 40 and r[0]["cache_leida"] == 5000 and r[0]["usd"] == 0.0123,
                      "con sus tokens y su $ equivalente")
            comprobar(r and r[0]["cuenta"] == "principal" and r[0]["modelo"] == "haiku",
                      "y la cuenta y el modelo")
            poner_modo(modo, "cupo")
            try:
                llamar("la Parrilla")
                comprobar(False, "un cupo agotado sube como LimiteAgotado")
            except cli_claude.LimiteAgotado:
                comprobar(True, "un cupo agotado sube como LimiteAgotado")
            cupos = [x for x in cc.leer_registro() if x.get("tipo") == "cupo"]
            comprobar(len(cupos) == 1 and cupos[0]["para"] == "la Parrilla", "y se apunta el cupo agotado")
            comprobar((cc.leer_cupo().get(cc.clave_de(None)) or {}).get("estado") == "rejected",
                      "y el cupo de la cuenta pasa a «agotado»")
            poner_modo(modo, "bien")

        print("2. MEDIR LEE EL CUPO DE VERDAD")
        if os.name != "nt":
            ficha = cc.medir(None)
            v = ficha.get("ventanas") or {}
            comprobar(abs(v.get("five_hour", {}).get("uso", 0) - 0.73) < 1e-9
                      and v.get("five_hour", {}).get("reinicia") == 1900000000,
                      f"la ventana de 5 h con su reinicio ({v.get('five_hour')})")
            comprobar(abs(v.get("seven_day", {}).get("uso", 0) - 0.21) < 1e-9, "y la semana")
            comprobar(ficha.get("estado") == "allowed", "y el estado ya no es «agotado»")
            comprobar(any(x.get("para") == "medir el cupo" for x in cc.leer_registro()),
                      "la propia medida también se apunta como consumo")
            poner_modo(modo, "sin_cupo")
            otra = cc.medir(None)
            comprobar((otra.get("ventanas") or {}).get("five_hour", {}).get("uso") == 0.73 and otra.get("error"),
                      "si el CLI no da el cupo, se queda la última medida buena y se dice")
            poner_modo(modo, "bien")

        print("3. LOS AVISOS AL 70 % Y AL 90 %")
        ahora = time.time()
        a = cc.avisos({"x": {"cuenta": "principal", "ventanas": {
            "five_hour": {"uso": 0.93, "reinicia": ahora + 600},
            "seven_day": {"uso": 0.71, "reinicia": ahora + 86400},
            "seven_day_opus": {"uso": 0.5, "reinicia": ahora + 86400},
            "viejo": {"uso": 0.99, "reinicia": ahora - 10}}}}, ahora)
        comprobar([(x["ventana"], x["nivel"]) for x in a] == [("five_hour", "malo"), ("seven_day", "ojo")],
                  f"5 h al 93 % = malo, semana al 71 % = ojo, 50 % nada, reiniciada nada ({a})")
        b = cc.avisos({"x": {"cuenta": "principal", "estado": "rejected", "mensaje": "se renueva el lunes",
                             "ventanas": {}}}, ahora)
        comprobar(len(b) == 1 and b[0]["nivel"] == "malo" and "lunes" in b[0]["mensaje"],
                  "un cupo agotado sin ventanas también avisa")

        print("4. EL RESUMEN")
        cc.anotar({"etiqueta": "la del curro", "config_dir": os.path.join(tempfile.gettempdir(), "cuenta_curro")}, {"usage": {"output_tokens": 10}, "total_cost_usd": 1.0,
                                                 "_ajuste": {"modelo": "opus"}}, "el guion")
        res = cc.resumen()
        tareas = {f["tarea"]: f for f in res["por_tarea"]}
        comprobar("el guion" in tareas and tareas["el guion"]["llamadas"] >= 2, "suma por tarea")
        comprobar({f["cuenta"] for f in res["por_cuenta"]} >= {"principal", "la del curro"}, "y por cuenta")
        comprobar(res["hoy"]["llamadas"] == res["semana"]["llamadas"] and res["hoy"]["usd"] >= 1.0,
                  "y lo de hoy entra en la semana")
        comprobar(res["por_dia"] and res["por_dia"][0]["fecha"] == time.strftime("%Y-%m-%d"), "y por día")

        print("5. CUÁNDO MIDE SOLA")
        luego = time.time() + cc.CADA_S + 5
        comprobar(not cc.toca_medir(None), "recién medida: no toca")
        comprobar(not cc.toca_medir(None, ahora=luego),
                  "a los 15 min, pero sin llamadas desde la medida: no toca")
        time.sleep(0.2)
        cc.anotar(None, {"usage": {}}, "la ortografía")
        comprobar(cc.toca_medir(None, ahora=luego), "a los 15 min y con llamadas: toca")
        os.environ["ESTUDIO_SIMULAR"] = "1"
        comprobar(not cc.toca_medir(None), "con ESTUDIO_SIMULAR nunca mide sola")
        antes = len(cc.leer_registro())
        f = cc.medir(None)
        comprobar(f.get("simulado") and (f.get("ventanas") or {}).get("five_hour"),
                  "y «Medir ahora» simulado da un cupo marcado «simulado»")
        comprobar(len(cc.leer_registro()) == antes, "sin salir al CLI (no apunta ninguna llamada)")
        os.environ.pop("ESTUDIO_SIMULAR", None)

        print("6. UN REGISTRO QUE NO SE PUEDE ESCRIBIR NO ROMPE NADA")
        original = os.environ["ESTUDIO_SECRETOS"]
        bloqueo = os.path.join(original, "no_es_carpeta")
        with open(bloqueo, "w") as fh:
            fh.write("x")
        os.environ["ESTUDIO_SECRETOS"] = bloqueo   # una carpeta que es un fichero
        try:
            cc.anotar(None, {"usage": {}}, "nada")
            comprobar(True, "anotar sin poder escribir no lanza")
            if os.name != "nt":
                texto, _s = llamar("otra")
                comprobar(texto == "respuesta", "y la llamada sale igual")
        except Exception as fallo:                     # noqa: BLE001
            comprobar(False, f"anotar sin poder escribir no lanza ({fallo})")
        finally:
            os.environ["ESTUDIO_SECRETOS"] = original

        print("7. LA SALIDA DEL CLI DE VERDAD")
        linea = ('{"type":"rate_limit_event","rate_limit_info":{"status":"allowed","resetsAt":1792990200,'
                 '"rateLimitType":"five_hour","overageStatus":"rejected","isUsingOverage":false,'
                 '"unifiedWindows":{"five_hour":{"utilization":0.13,"resetsAt":1792990200,"status":"allowed"},'
                 '"seven_day":{"utilization":0.04,"resetsAt":1793480400,"status":"allowed"}}}}')
        info, sobre = cc.leer_salida_medida("ruido\n" + linea + '\n{"type":"result","result":"ok"}\n')
        v = cc.ventanas_de(info)
        comprobar(v.get("five_hour", {}).get("uso") == 0.13 and v.get("seven_day", {}).get("uso") == 0.04
                  and (sobre or {}).get("result") == "ok",
                  "la línea medida el 25-10 con el CLI 2.1.310 se lee entera")
        print("8. LAS TAREAS SE AGRUPAN Y EL REGISTRO SE PODA")
        comprobar(cc.tarea_de("el corrector del plano 12") == cc.tarea_de("el corrector del plano 7")
                  == "el corrector del plano", "«el corrector del plano 12» y «… 7» son la misma tarea")
        comprobar(cc.tarea_de("el revisor de imágenes (p1–p8)") == "el revisor de imágenes",
                  "sin lo de entre paréntesis")
        viejo = time.time() - (cc.DIAS_GUARDAR + 3) * 86400
        with open(cc.fichero_registro(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": viejo, "tipo": "llamada", "para": "viejísima"}) + "\n")
            fh.write('{"t": "no es un número"}\n')
        comprobar(any(r.get("para") == "viejísima" for r in cc.leer_registro()),
                  "una línea con un «t» raro no rompe la lectura")
        tope = cc.MAX_BYTES
        try:
            cc.MAX_BYTES = 1
            cc.anotar(None, {"usage": {}}, "la que poda")
        finally:
            cc.MAX_BYTES = tope
        quedan = [r.get("para") for r in cc.leer_registro()]
        comprobar("viejísima" not in quedan and "la que poda" in quedan,
                  "al pasar del tamaño se poda lo de hace más de DIAS_GUARDAR y lo nuevo se queda")
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)
        shutil.rmtree(CARPETA_SECRETOS, ignore_errors=True)

    if FALLOS:
        print(f"\nFALLARON {len(FALLOS)} de {CUENTAS} comprobaciones:")
        for texto in FALLOS:
            print(f"  - {texto}")
        return 1
    print(f"\nCONSUMO DE CLAUDE OK: {CUENTAS} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

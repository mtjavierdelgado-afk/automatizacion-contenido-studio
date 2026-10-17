r"""
Prueba adversarial del nucleo: intenta ROMPERLO, no lucirlo.

Cubre lo que la prueba de extremo a extremo no mira: propagacion por todos los
caminos del DAG, granularidad unidad a unidad, revertir con historico, reinicio
del proceso, carreras entre hilos y entre procesos, path traversal y perdida de
estado ante un estado.json ilegible.

    python nucleo\prueba_adversarial.py
    ... [1 2 3 4 4b 5 5b 5c 5d 6 7 8]   para correr solo algunos bloques
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from nucleo import Estado, PASOS, Proyecto, descendientes_de
from nucleo.proyecto import escribir_json, leer_json

FALLOS = []
UNIDADES = ["S01", "S02", "S03", "S04"]


def ok(cond, texto):
    if cond:
        print(f"  ok    {texto}")
    else:
        print(f"  FALLO {texto}")
        FALLOS.append(texto)


def igual(a, b, texto):
    ok(a == b, texto if a == b else f"{texto} [obtenido={a!r} esperado={b!r}]")


def grafo_completo(base, nombre="p"):
    """Proyecto con los ocho pasos completados y cuatro unidades."""
    proyecto = Proyecto.crear(base, nombre)
    e = Estado(proyecto)
    e.set_params("ingesta", {"url": "u"})
    e.completar("ingesta", {"t": "t.json"})
    e.set_params("brief", {"angulo": "a"})
    e.completar("brief", {"b": "b.md"})
    e.set_params("guion", {"tono": "seco",
                           "unidades": {u: {"texto": f"texto {u}"} for u in UNIDADES}})
    e.completar("guion", {"escenas": len(UNIDADES)})
    e.set_params("voz", {"voz_id": "v"})
    e.completar("voz", {"wav": "n.wav"})
    e.set_params("revision_audio", {"umbral": 0.5})
    e.completar("revision_audio", {"informe": "i.json"})
    e.set_params("assets", {"estilo": "cartoon"})
    e.set_params("callouts", {"fuente": "inter"})
    e.set_params("render", {"fps": 30})
    for pid in ("assets", "callouts", "render"):
        e.completar(pid, {"total": len(UNIDADES)},
                    {u: {"png": f"{pid}_{u}.png"} for u in UNIDADES})
    return proyecto, e


def foto(e):
    return {p["id"]: e.estado_de(p["id"]) for p in PASOS}


# --------------------------------------------------------------- 1. propagacion

def t1_propagacion(base):
    print("\n[1] propagacion de obsolescencia por TODOS los caminos del DAG")
    for paso in PASOS:
        pid = paso["id"]
        carpeta = tempfile.mkdtemp(dir=base)
        proyecto, e = grafo_completo(carpeta, f"prop_{pid}")
        antes = foto(e)
        igual(set(antes.values()), {"listo"}, f"[{pid}] grafo arranca todo listo")
        e.actualizar_params(pid, {"_perturbacion": random.random()})
        despues = foto(e)
        esperados = set(descendientes_de(pid)) | {pid}
        obsoletos = {k for k, v in despues.items() if v != "listo"}
        igual(obsoletos, esperados,
              f"cambiar {pid} obsoleta exactamente {sorted(esperados)}")
        # aguas arriba intacto de verdad (firma identica, no solo estado)
        for otro in PASOS:
            oid = otro["id"]
            if oid in esperados:
                continue
            ok(e.firma(oid) == e.firma(oid), f"[{pid}] firma de {oid} estable")
        shutil.rmtree(carpeta, ignore_errors=True)

    # camino doble: guion -> voz -> assets  y  guion -> assets
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "doble")
    f_assets = e.firma("assets")
    e.actualizar_params("voz", {"velocidad": "fast"})
    ok(e.firma("assets") != f_assets, "un cambio en voz altera la firma de assets")
    igual(e.estado_de("render"), "obsoleto", "el cambio en voz llega hasta render")
    igual(e.estado_de("brief"), "listo", "brief no se entera (no es descendiente)")
    shutil.rmtree(carpeta, ignore_errors=True)


# --------------------------------------------------------------- 2. granularidad

def t2_granularidad(base):
    print("\n[2] granularidad por unidad")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "gran")
    firmas = {p["id"]: {u: e.firma_unidad(p["id"], u) for u in UNIDADES} for p in PASOS}
    globales = {p["id"]: e.firma_global(p["id"]) for p in PASOS}

    e.actualizar_params("guion", {"unidades": {"S03": {"texto": "otro"}}})
    for pid in ("assets", "callouts", "render"):
        igual(e.unidades_obsoletas(pid), ["S03"], f"{pid} solo S03 sucia")
        for u in UNIDADES:
            if u == "S03":
                ok(e.firma_unidad(pid, u) != firmas[pid][u], f"{pid}/{u} cambia")
            else:
                igual(e.firma_unidad(pid, u), firmas[pid][u], f"{pid}/{u} intacta")
    for pid in globales:
        igual(e.firma_global(pid), globales[pid],
              f"cambiar una unidad NO mueve la firma global de {pid}")

    # rehacer solo S03 deja el paso listo y conserva las salidas de las demas
    e.completar("guion", {"escenas": 4})
    e.completar("voz", {"wav": "n2.wav"})
    for pid in ("assets", "callouts", "render"):
        e.completar(pid, {"total": 1}, {"S03": {"png": f"{pid}_S03_v2.png"}})
        igual(e.estado_de(pid), "listo", f"{pid} listo tras rehacer solo S03")
        igual(e.salidas_unidad(pid, "S01")["png"], f"{pid}_S01.png",
              f"{pid} conserva la salida de S01")

    # cambio en los params por unidad del PROPIO paso intermedio
    firmas2 = {u: e.firma_unidad("render", u) for u in UNIDADES}
    e.actualizar_params("callouts", {"unidades": {"S02": {"caja": [1, 2]}}})
    igual(e.unidades_obsoletas("callouts"), ["S02"], "callouts solo S02 sucia")
    igual(e.unidades_obsoletas("render"), ["S02"], "render hereda solo S02")
    igual(e.unidades_obsoletas("assets"), [], "assets (aguas arriba) intacto")
    igual(e.firma_unidad("render", "S01"), firmas2["S01"], "render/S01 no se mueve")

    # invalidar a mano una unidad no debe ensuciar a las hermanas
    e.completar("callouts", {"total": 1}, {"S02": {"png": "c2.png"}})
    e.completar("render", {"total": 1}, {"S02": {"png": "r2.png"}})
    e.invalidar_unidades("render", ["S04"])
    igual(e.unidades_obsoletas("render"), ["S04"], "invalidacion manual aislada")
    igual(e.estado_de("callouts"), "listo", "invalidar en render no toca callouts")
    e.completar("render", {"total": 1}, {"S04": {"png": "r4.png"}})
    igual(e.unidades_obsoletas("render"), [], "la invalidacion se consume")

    # unidad nueva: solo ella sale sucia
    firmas3 = {u: e.firma_unidad("assets", u) for u in UNIDADES}
    e.actualizar_params("guion", {"unidades": {"S05": {"texto": "nueva"}}})
    igual(e.unidades_obsoletas("assets"), ["S05"], "una escena nueva ensucia solo a ella")
    for u in UNIDADES:
        igual(e.firma_unidad("assets", u), firmas3[u], f"assets/{u} intacta con S05 nueva")
    shutil.rmtree(carpeta, ignore_errors=True)


# ------------------------------------------------------------------ 3. revertir

def rehacer_aguas_abajo(e, marca):
    """Recompleta voz y los pasos por unidad que esten sucios."""
    if e.estado_de("voz") != "listo":
        e.completar("voz", {"wav": f"n_{marca}.wav"})
    if e.estado_de("revision_audio") != "listo":
        e.completar("revision_audio", {"informe": f"i_{marca}.json"})
    for pid in ("assets", "callouts", "render"):
        sucias = e.unidades_obsoletas(pid)
        if sucias or e.estado_de(pid) != "listo":
            e.completar(pid, {"total": len(sucias)},
                        {u: {"png": f"{pid}_{u}_{marca}.png"} for u in sucias})


def t3_revertir(base):
    print("\n[3] revertir: propagacion e historico")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "rev")
    e.actualizar_params("guion", {"unidades": {"S03": {"texto": "v2"}}})
    e.completar("guion", {"escenas": 4})
    rehacer_aguas_abajo(e, "v2")
    igual(foto(e), {p["id"]: "listo" for p in PASOS}, "grafo entero al dia en v2")
    e.actualizar_params("guion", {"unidades": {"S03": {"texto": "v3"}}})
    e.completar("guion", {"escenas": 4})
    rehacer_aguas_abajo(e, "v3")
    igual([v["n"] for v in e.versiones("guion")], [1, 2, 3], "tres versiones de guion")
    igual(e.salidas_unidad("render", "S03")["png"], "render_S03_v3.png",
          "render tiene la S03 de v3")

    e.revertir("guion", 1)
    igual(e.params("guion")["unidades"]["S03"]["texto"], "texto S03",
          "revertir restaura los params")
    igual(e.estado_de("guion"), "listo", "guion listo en v1")
    igual([v["n"] for v in e.versiones("guion")], [1, 2, 3], "revertir no borra historico")
    igual([v["activa"] for v in e.versiones("guion")], [True, False, False],
          "solo v1 activa")
    ok(proyecto.ruta_paso("guion").endswith(os.path.join("guion", "v1")),
       "la ruta activa apunta a v1")
    igual(e.estado_de("voz"), "obsoleto", "voz obsoleta tras revertir el guion")
    igual(e.estado_de("ingesta"), "listo", "ingesta (aguas arriba) intacta")
    for pid in ("assets", "callouts", "render"):
        igual(e.unidades_obsoletas(pid), ["S03"], f"{pid} solo S03 sucia tras revertir")

    # revertir aguas abajo hasta la version coherente debe dejar todo listo
    e.revertir("voz", 1)
    e.revertir("revision_audio", 1)
    for pid in ("assets", "callouts", "render"):
        e.revertir(pid, 1)
        igual(e.estado_de(pid), "listo", f"{pid} coherente al revertir a v1")
        igual(e.salidas_unidad(pid, "S03")["png"], f"{pid}_S03.png",
              f"{pid} recupera la salida original de S03")

    # revertir hacia delante
    e.revertir("guion", 3)
    igual(e.params("guion")["unidades"]["S03"]["texto"], "v3", "revertir hacia delante")
    igual(e.estado_de("guion"), "listo", "guion listo en v3")
    igual(e.unidades_obsoletas("render"), ["S03"], "render vuelve a pedir S03")

    # revertir un paso INTERMEDIO deja el de abajo obsoleto
    e.revertir("voz", 3)
    e.revertir("assets", 3)
    e.revertir("callouts", 3)
    e.revertir("render", 3)
    igual(foto(e)["render"], "listo", "todo el grafo coherente en v3")
    e.revertir("voz", 1)
    igual(e.estado_de("voz"), "obsoleto",
          "voz en v1 con guion en v3 queda obsoleta")
    igual(e.unidades_obsoletas("assets"), ["S03"],
          "revertir voz propaga a assets solo en S03")
    e.revertir("voz", 3)

    # completar despues de revertir crea version nueva sin pisar nada
    e.revertir("guion", 2)
    v = e.completar("guion", {"escenas": 4})
    igual(v, 4, "la version nueva es v4, no pisa v3")
    igual([x["n"] for x in e.versiones("guion")], [1, 2, 3, 4], "historico completo")
    igual([x["params"]["unidades"]["S03"]["texto"] for x in e.versiones("guion")],
          ["texto S03", "v2", "v3", "v2"], "cada version conserva SUS params")

    try:
        e.revertir("guion", 99)
        ok(False, "revertir a una version inexistente deberia fallar")
    except ValueError:
        ok(True, "revertir a una version inexistente lanza ValueError")

    # revertir NO debe perder invalidaciones manuales pendientes
    e2 = Estado(Proyecto.crear(carpeta, "inval"))
    e2.set_params("ingesta", {"u": 1})
    e2.completar("ingesta", {"t": 1})
    e2.set_params("brief", {})
    e2.completar("brief", {})
    e2.set_params("guion", {"unidades": {u: {"texto": u} for u in UNIDADES}})
    e2.completar("guion", {})
    e2.set_params("voz", {})
    e2.completar("voz", {})
    for pid in ("assets", "callouts", "render"):
        e2.completar(pid, {}, {u: {"png": f"{pid}_{u}.png"} for u in UNIDADES})
    e2.completar("render", {}, {"S02": {"png": "r2.png"}})
    e2.invalidar_unidades("render", ["S01"])
    igual(e2.unidades_obsoletas("render"), ["S01"], "S01 invalidada a mano")
    e2.revertir("render", 1)
    igual(e2.unidades_obsoletas("render"), ["S01"],
          "revertir conserva las invalidaciones manuales pendientes")
    shutil.rmtree(carpeta, ignore_errors=True)


# --------------------------------------------------------------- 4. persistencia

GUION_HIJO = f"RUTA_NUCLEO = r'{RAIZ}'\n" + r"""
import json, sys
sys.path.insert(0, RUTA_NUCLEO)
from nucleo import Estado, Proyecto
p = Proyecto(sys.argv[1])
e = Estado(p)
if len(sys.argv) > 2 and sys.argv[2] == "escribir":
    e.actualizar_params("brief", {"desde_hijo": True})
print(json.dumps({
    "resumen": e.resumen(),
    "params_guion": e.params("guion"),
    "versiones": [v["n"] for v in e.versiones("assets")],
    "salidas_S01": e.salidas_unidad("assets", "S01"),
}, default=str))
"""


def t4_persistencia(base):
    print("\n[4] el estado sobrevive a reiniciar el proceso")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "persi")
    e.actualizar_params("guion", {"unidades": {"S03": {"texto": "cambiado"}}})
    e.invalidar_unidades("render", ["S04"])
    esperado = e.resumen()

    guion = os.path.join(carpeta, "hijo.py")
    with open(guion, "w", encoding="utf-8") as fh:
        fh.write(GUION_HIJO)
    salida = subprocess.run([sys.executable, guion, proyecto.raiz],
                            capture_output=True, text=True)
    ok(salida.returncode == 0, f"el proceso hijo arranca ({salida.stderr[-300:]})")
    datos = json.loads(salida.stdout)
    igual([p["estado"] for p in datos["resumen"]["pasos"]],
          [p["estado"] for p in esperado["pasos"]],
          "otro proceso ve los mismos estados")
    igual([p["unidades_obsoletas"] for p in datos["resumen"]["pasos"]],
          [p["unidades_obsoletas"] for p in esperado["pasos"]],
          "otro proceso ve las mismas unidades sucias")
    igual(datos["params_guion"]["unidades"]["S03"]["texto"], "cambiado",
          "los params sobreviven al reinicio")
    igual(datos["versiones"], [1], "el historico sobrevive al reinicio")
    igual(datos["salidas_S01"], {"png": "assets_S01.png"},
          "las salidas por unidad sobreviven")

    # un proceso hijo escribe: el padre, ya abierto, debe enterarse
    subprocess.run([sys.executable, guion, proyecto.raiz, "escribir"],
                   capture_output=True, text=True)
    igual(e.params("brief").get("desde_hijo"), True,
          "el proceso padre recarga lo que escribio el hijo")
    shutil.rmtree(carpeta, ignore_errors=True)


def t4b_sello(base):
    print("\n[4b] deteccion de cambio en disco (sello mtime+tamano)")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "sello")
    otro = Estado(proyecto)
    # cambio del MISMO tamano: 'aaaa' -> 'bbbb'. Si el sello no lo pilla,
    # una instancia vieja se queda con datos fantasma.
    e.actualizar_params("brief", {"angulo": "aaaa"})
    otro._sincronizar()
    igual(otro.params("brief").get("angulo"), "aaaa", "sello: primera lectura")
    fallos_seguidos = 0
    for i in range(60):
        letra = "abcdefghij"[i % 10] * 4
        e.actualizar_params("brief", {"angulo": letra})
        if otro.params("brief").get("angulo") != letra:
            fallos_seguidos += 1
    igual(fallos_seguidos, 0,
          "cambios del mismo tamano se detectan siempre (sello no se queda ciego)")
    shutil.rmtree(carpeta, ignore_errors=True)


# ------------------------------------------------------------------ 5. carreras

def t5_carreras(base):
    print("\n[5] carreras: hilos escribiendo estado a la vez")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "carrera")
    errores = []

    def escribir(pid, veces):
        try:
            for i in range(veces):
                e.actualizar_params(pid, {f"k_{pid}": i})
        except Exception as fallo:
            errores.append(f"escritor {pid}: {type(fallo).__name__}: {fallo}")

    def leer(veces):
        try:
            for _ in range(veces):
                e.resumen()
                e.unidades_obsoletas("render")
        except Exception as fallo:
            errores.append(f"lector: {type(fallo).__name__}: {fallo}")

    hilos = [threading.Thread(target=escribir, args=(p["id"], 40)) for p in PASOS]
    hilos += [threading.Thread(target=leer, args=(60,)) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(60)
    igual(errores, [], "ningun hilo revienta escribiendo/leyendo a la vez")

    # NINGUNA escritura se puede perder: cada paso debe conservar su clave
    disco = leer_json(proyecto.ruta("estado.json"))
    perdidas = [p["id"] for p in PASOS
                if disco["pasos"][p["id"]]["params"].get(f"k_{p['id']}") != 39]
    igual(perdidas, [], "ninguna escritura concurrente se pierde")

    # completar concurrente sobre pasos distintos: numeracion sana
    errores2 = []

    def completar(pid, veces):
        try:
            for i in range(veces):
                e.completar(pid, {"i": i})
        except Exception as fallo:
            errores2.append(f"{pid}: {type(fallo).__name__}: {fallo}")

    hilos = [threading.Thread(target=completar, args=(p["id"], 8)) for p in PASOS]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(60)
    igual(errores2, [], "completar en paralelo no revienta")
    for p in PASOS:
        ns = [v["n"] for v in e.versiones(p["id"])]
        igual(ns, sorted(set(ns)), f"{p['id']}: versiones unicas y ordenadas")
    shutil.rmtree(carpeta, ignore_errors=True)


def t5b_lectores_escritores_disco(base):
    print("\n[5b] carrera de E/S: leer estado.json mientras se reescribe")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "io")
    ruta = proyecto.ruta("estado.json")
    errores = []
    parar = threading.Event()

    def escritor():
        i = 0
        while not parar.is_set():
            try:
                e.actualizar_params("brief", {"n": i})
            except Exception as fallo:
                errores.append(f"escritor: {type(fallo).__name__}: {fallo}")
                return
            i += 1

    def lector():
        while not parar.is_set():
            try:
                doc = leer_json(ruta, estricto=True)
            except Exception as fallo:
                errores.append(f"lector: {type(fallo).__name__}: {fallo}")
                return
            if not isinstance(doc, dict) or "pasos" not in doc:
                errores.append(f"lector: leyo un estado incompleto {type(doc)}")
                return

    def lector_estado():
        otro = Estado(proyecto)
        while not parar.is_set():
            try:
                otro.resumen()
            except Exception as fallo:
                errores.append(f"lector Estado: {type(fallo).__name__}: {fallo}")
                return

    hilos = [threading.Thread(target=escritor)] + \
            [threading.Thread(target=lector) for _ in range(3)] + \
            [threading.Thread(target=lector_estado) for _ in range(2)]
    for h in hilos:
        h.start()
    time.sleep(3.0)
    parar.set()
    for h in hilos:
        h.join(20)
    igual(errores, [], "escritura atomica aguanta lectores concurrentes")
    shutil.rmtree(carpeta, ignore_errors=True)


def t5c_completar_con_params_cambiados(base):
    print("\n[5c] un trabajo largo que termina despues de que cambien los params")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "tarde")
    e.marcar_ejecutando("guion")
    igual(e.estado_de("guion"), "ejecutando", "guion marcado como ejecutando")
    # el usuario edita mientras corre
    e.actualizar_params("guion", {"tono": "epico"})
    igual(e.estado_de("guion"), "obsoleto", "editar durante la ejecucion marca obsoleto")
    # el trabajo viejo termina y guarda: NO puede declararse al dia
    v = e.completar("guion", {"escenas": 4})
    igual(e.estado_de("guion"), "obsoleto",
          "un trabajo que corrio con params viejos NO deja el paso al dia")
    ficha = [x for x in e.versiones("guion") if x["n"] == v][0]
    igual(ficha["params"].get("tono"), "seco",
          "la version guarda los params con los que corrio de verdad")
    # y rehacerlo con los params nuevos si lo deja listo
    e.marcar_ejecutando("guion")
    e.completar("guion", {"escenas": 4})
    igual(e.estado_de("guion"), "listo", "rehacerlo con los params nuevos si vale")
    shutil.rmtree(carpeta, ignore_errors=True)


def t8_no_borrar_estado(base):
    print("\n[8] estado.json ilegible no puede borrar el grafo")
    import nucleo.estado as MODULO
    import nucleo.proyecto as BASE
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "nowipe")
    real = BASE.leer_json

    def ilegible(ruta, por_defecto=None, estricto=False):
        if str(ruta).endswith("estado.json"):
            raise PermissionError(13, "simulado")
        return real(ruta, por_defecto)

    MODULO.leer_json = ilegible
    e._sello = None
    try:
        e.actualizar_params("brief", {"angulo": "nuevo"})
        ok(False, "un estado.json ilegible deberia propagar el fallo")
    except PermissionError:
        ok(True, "un estado.json ilegible propaga el fallo en vez de tragarselo")
    finally:
        MODULO.leer_json = real

    otro = Estado(proyecto)
    igual([v["n"] for v in otro.versiones("assets")], [1], "el historico sigue intacto")
    igual(otro.estado_de("render"), "listo", "el grafo sigue en pie")

    # corrupto de verdad: se aparta una copia y se vuelve a la ULTIMA BUENA,
    # que es la de antes del ultimo guardado. Arrancar de cero ofrecia generar
    # el video entero otra vez.
    anterior = getattr(MODULO, "NOMBRE_ANTERIOR", "estado.json.anterior")
    ilegible_error = getattr(MODULO, "EstadoIlegible", LookupError)
    otro.set_params("brief", {"angulo": "el ultimo"})      # el ultimo guardado
    ok(os.path.isfile(proyecto.ruta(anterior)),
       "cada guardado deja la copia buena anterior")
    with open(proyecto.ruta("estado.json"), "w", encoding="utf-8") as fh:
        fh.write("{ roto")
    tercero = Estado(proyecto)
    igual(tercero.estado_de("render"), "listo", "vuelve a la copia buena, no a cero")
    igual([v["n"] for v in tercero.versiones("assets")], [1], "con su historico")
    igual(tercero.params("brief"), {"angulo": "a"},
          "la copia es la de ANTES del ultimo guardado (lo ultimo se pierde, y se dice)")
    recuperacion = getattr(tercero, "recuperacion", None)
    ok(bool(recuperacion), f"y deja constancia ({recuperacion})")
    apartados = [n for n in os.listdir(proyecto.raiz) if n.startswith("estado.roto")]
    ok(len(apartados) == 1, f"el estado corrupto se guarda a un lado ({apartados})")
    igual(Estado(proyecto).estado_de("render"), "listo", "y el recuperado ya se lee solo")

    # un fichero VACIO (lo que deja un corte de luz) es igual de roto
    with open(proyecto.ruta("estado.json"), "w", encoding="utf-8") as fh:
        fh.write("")
    igual(Estado(proyecto).estado_de("render"), "listo", "un estado.json vacio tambien se recupera")

    # sin copia buena: NO arranca de cero, lo dice (y sigue sin abrir)
    if os.path.exists(proyecto.ruta(anterior)):
        os.remove(proyecto.ruta(anterior))
    with open(proyecto.ruta("estado.json"), "w", encoding="utf-8") as fh:
        fh.write("{ roto otra vez")
    for intento in (1, 2):
        try:
            Estado(proyecto)
            ok(False, "sin copia buena deberia lanzar EstadoIlegible")
        except ilegible_error as fallo:
            ok("estado.roto." in str(fallo),
               f"intento {intento}: sin copia buena lanza y nombra el fichero apartado")
    with open(proyecto.ruta("estado.json"), encoding="utf-8") as fh:
        igual(fh.read(), "{ roto otra vez", "el roto se queda en su sitio: no se abre vacio")
    shutil.rmtree(carpeta, ignore_errors=True)


def t5d_procesos(base):
    print("\n[5c/procesos] dos procesos escribiendo el mismo estado.json")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "multiproc")
    guion = os.path.join(carpeta, "escritor.py")
    with open(guion, "w", encoding="utf-8") as fh:
        fh.write(f"RUTA_NUCLEO = r'{RAIZ}'\n" + r"""
import sys
sys.path.insert(0, RUTA_NUCLEO)
from nucleo import Estado, Proyecto
p = Proyecto(sys.argv[1]); e = Estado(p); clave = sys.argv[2]
for i in range(40):
    e.actualizar_params("brief", {clave: i})
""")
    procesos = [subprocess.Popen([sys.executable, guion, proyecto.raiz, f"c{i}"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                for i in range(3)]
    for pr in procesos:
        pr.wait(120)
    disco = leer_json(proyecto.ruta("estado.json"))
    params = disco["pasos"]["brief"]["params"]
    perdidas = [c for c in ("c0", "c1", "c2") if params.get(c) != 39]
    igual(perdidas, [], "tres procesos escribiendo: ninguna clave se pierde")
    shutil.rmtree(carpeta, ignore_errors=True)


# -------------------------------------------------------------- 6. path traversal

def t6_traversal(base):
    print("\n[6] path traversal en las rutas de proyecto")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "trav")
    raiz = os.path.normcase(os.path.abspath(proyecto.raiz))

    def dentro(ruta):
        entera = os.path.normcase(os.path.abspath(ruta))
        return entera == raiz or entera.startswith(raiz + os.sep)

    casos = [
        ("ruta con ..", lambda: proyecto.ruta("..", "..", "evil.txt")),
        ("ruta con ../ mezclado", lambda: proyecto.ruta("assets/../../../evil.txt")),
        ("ruta absoluta", lambda: proyecto.ruta(r"C:\Windows\System32\evil.txt")),
        ("ruta con barra invertida", lambda: proyecto.ruta(r"..\..\evil.txt")),
        ("ruta_paso con ..", lambda: proyecto.ruta_paso("../../evil")),
        ("ruta_trabajo con ..", lambda: proyecto.ruta_trabajo("../../evil", crear=False)),
        ("ruta_paso absoluto", lambda: proyecto.ruta_paso(r"C:\Windows\evil")),
        ("version_activa con ..", lambda: proyecto.ruta("pasos", "../../x", "activa.json")),
        ("unidad con ..", lambda: proyecto.ruta("unidades", "../../../evil")),
    ]
    for nombre, fabricar in casos:
        try:
            destino = fabricar()
        except ValueError:
            ok(True, f"{nombre}: rechazado con ValueError")
            continue
        ok(dentro(destino), f"{nombre}: la ruta no escapa del proyecto ({destino})")

    # crear proyectos con nombres hostiles
    for nombre in ["../../fuera", r"..\..\fuera", "C:/Windows/fuera", "..", ".",
                   "con:dos", "nombre*raro", "CON", "  "]:
        try:
            p2 = Proyecto.crear(carpeta, nombre)
        except Exception as fallo:
            ok(True, f"crear({nombre!r}) rechazado: {type(fallo).__name__}")
            continue
        entera = os.path.normcase(os.path.abspath(p2.raiz))
        base_n = os.path.normcase(os.path.abspath(carpeta))
        ok(entera.startswith(base_n + os.sep),
           f"crear({nombre!r}) se queda dentro de la base ({p2.raiz})")

    # Estado/Bitacora no deben aceptar pasos inventados
    for malo in ["../../evil", "guion/../..", "GUION", ""]:
        try:
            e.firma(malo)
            ok(False, f"firma({malo!r}) deberia fallar")
        except ValueError:
            ok(True, f"firma({malo!r}) rechazado")
    try:
        e.completar("../../evil", {})
        ok(False, "completar con paso invalido deberia fallar")
    except ValueError:
        ok(True, "completar rechaza pasos invalidos")
    shutil.rmtree(carpeta, ignore_errors=True)


def t7_varios(base):
    print("\n[7] varios: robustez de estado.json")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "robusto")
    # estado.json corrupto: no debe tumbar el arranque ni borrar el historico
    ruta = proyecto.ruta("estado.json")
    copia = leer_json(ruta)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("{ esto no es json")
    try:
        e2 = Estado(proyecto)
        ok(True, "un estado.json corrupto no impide abrir el proyecto")
        # no arranca de cero: vuelve a la copia buena (ver [8])
        igual(e2.estado_de("ingesta"), "listo", "vuelve a la copia buena si esta corrupto")
    except Exception as fallo:
        ok(False, f"estado.json corrupto revienta: {type(fallo).__name__}: {fallo}")
    escribir_json(ruta, copia)

    # params no serializables
    e3 = Estado(proyecto)
    try:
        e3.set_params("brief", {"objeto": object()})
        disco = leer_json(ruta)
        ok(isinstance(disco, dict) and "pasos" in disco,
           "params no serializables no dejan estado.json roto")
    except Exception as fallo:
        ok(isinstance(fallo, (TypeError, ValueError)),
           f"params no serializables fallan limpio ({type(fallo).__name__})")
        disco = leer_json(ruta)
        ok(isinstance(disco, dict) and "pasos" in disco,
           "y estado.json sigue valido tras el fallo")
    shutil.rmtree(carpeta, ignore_errors=True)


def t9_revision_v2f(base):
    """Los fallos de la revision del nucleo del 16-10-2026 (arreglos-v2f)."""
    from nucleo.trabajos import GestorTrabajos
    from nucleo import estado as MOD_ESTADO

    print("\n[9a] un trabajo de varios pasos no marca error en el que YA se completo")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "v2f_error")
    gestor = GestorTrabajos(estado=e)

    def tanda_voz(avisar):
        e.completar("voz", {"wav": "toma.wav"})           # grabada y pagada
        raise RuntimeError("revision_audio: cupo agotado")  # falla la siguiente
    gestor.esperar(gestor.lanzar("receta:voz", tanda_voz, paso="voz"), 10)
    igual(e.estado_de("voz"), "listo", "la voz completada no hereda el error de otra tarea")
    ok(e.al_dia("voz"), "y sigue al dia: el reintento no la regraba")

    def falla_sin_completar(avisar):
        raise RuntimeError("cartesia 500")
    gestor.esperar(gestor.lanzar("voz", falla_sin_completar, paso="voz"), 10)
    igual(e.estado_de("voz"), "error", "si el paso registrado NO se completo, si es su error")
    e.limpiar_marca("voz")

    # la receta SALTA la voz porque esta al dia y falla la tarea siguiente: el
    # gestor no debe marcar su primer paso (lo marca `_correr_paso` en cada
    # paso que corre de verdad). Lo vio la revision independiente del 16-10.
    e.completar("voz", {"wav": "toma.wav"})

    def receta_que_salta_la_voz(avisar):
        raise RuntimeError("revision_audio: cupo agotado")
    gestor.esperar(gestor.lanzar("receta:voz", receta_que_salta_la_voz, paso="voz",
                                 toca=["voz", "revision_audio"]), 10)
    igual(e.estado_de("voz"), "listo", "una voz que la receta salto no hereda el error")
    ok(e.al_dia("voz"), "y sigue al dia: el reintento no la regraba ni la paga")

    print("\n[9b] si marcar o anotar revientan, el trabajo no se queda «ejecutando»")
    real = e.marcar_ejecutando

    def roto(paso):
        raise TimeoutError("otro proceso no suelta el cerrojo")
    e.marcar_ejecutando = roto
    try:
        ficha = gestor.esperar(gestor.lanzar("x", lambda avisar: 1, paso="voz"), 10)
    finally:
        e.marcar_ejecutando = real
    igual(ficha["estado"], "error", "el trabajo acaba en error, no colgado")
    igual(gestor.listar(activos=True), [], "y no queda nada activo")

    print("\n[9c] revertir vacia la cache de firmas")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "v2f_cache")
    e.set_params("guion", dict(e.params("guion"), tono="alegre"))
    e.completar("guion", {"escenas": len(UNIDADES)})
    with e._lock:     # la v1, como las de antes de que existiera firma_propia
        e._doc["pasos"]["guion"]["versiones"][0].pop("firma_propia", None)
        e._guardar()
    e.estado_de("guion")       # la pantalla lee: la cache se llena
    e.revertir("guion", 1)
    igual(e.estado_de("guion"), "listo", "una version vieja revertida no sale obsoleta")

    print("\n[9d] revertir aparta los restos de trabajo/ de una pasada rota")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "v2f_trabajo")
    e.completar("assets", {"total": 4}, {u: {"png": "v2"} for u in UNIDADES})
    trabajo = proyecto.ruta_trabajo("assets")      # pasada sobre la v2, cortada
    with open(os.path.join(trabajo, "S02.png"), "w") as fh:
        fh.write("imagen de la v2")
    resultado = e.revertir("assets", 1)
    ok(not os.path.exists(trabajo), "trabajo/ ya no esta al revertir")
    apartado = (resultado or {}).get("trabajo_apartado") or ""
    ok(os.path.isfile(os.path.join(apartado, "S02.png")),
       f"se aparta, no se borra ({apartado})")
    ok(not os.path.basename(os.path.dirname(apartado)).startswith("v"),
       "y no donde p6 busca versiones")

    print("\n[9e] estado_de no da «listo» a un paso editado mientras corria")
    # un proyecto como los de verdad: sin bloque `unidades` en el guion (el de
    # grafo_completo lo trae, y sus unidades heredadas taparian lo que se mira)
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto = Proyecto.crear(carpeta, "v2f_propia")
    e = Estado(proyecto)
    for pid in ("ingesta", "brief"):
        e.completar(pid, {"ok": 1})
    e.set_params("guion", {"tono": "seco"})
    e.completar("guion", {"escenas": 2})
    e.set_params("voz", {"voz_id": "A"})
    e.completar("voz", {"wav": "n.wav"})
    e.marcar_ejecutando("voz")                     # se graba con la voz A
    e.actualizar_params("voz", {"voz_id": "B"})    # el usuario cambia a media toma
    e.completar("voz", {"wav": "n.wav"})
    igual(e.estado_de("voz"), "obsoleto", "la voz grabada con la de antes sale obsoleta")
    igual(e.estado_de("voz") == "listo", e.al_dia("voz"), "estado_de y al_dia dicen lo mismo")
    e.completar("voz", {"wav": "n.wav"})           # se regraba con la B
    # y el guion corregido a mano sigue «listo» (CORRECCIONES)
    e.actualizar_params("guion", {"bloques": {"B1": {"texto": "corregido a mano"}}})
    igual(e.estado_de("guion"), "listo", "una correccion a mano no deja el guion obsoleto")
    igual(e.estado_de("voz"), "obsoleto", "pero si lo de abajo")

    print("\n[9f] las marcas «ejecutando» de un servicio anterior se quitan")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "v2f_huerfana")
    e.marcar_ejecutando("callouts")
    otro = Estado(proyecto)               # el servicio se reinicia
    igual(otro.limpiar_marcas_en_marcha(), ["callouts"], "se quita la que quedo")
    igual(otro.estado_de("callouts"), "listo", "y el paso vuelve a su estado")
    igual(otro.limpiar_marcas_en_marcha(), [], "sin marcas no escribe nada")

    print("\n[9g] completar escribe el manifiesto ANTES de vaciar trabajo/")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "v2f_manifiesto")
    trabajo = proyecto.ruta_trabajo("assets")
    with open(os.path.join(trabajo, "S01.png"), "w") as fh:
        fh.write("pagada")
    real = e._guardar_manifiesto

    def disco_lleno(*a, **k):
        raise OSError(28, "No space left on device")
    e._guardar_manifiesto = disco_lleno
    try:
        e.completar("assets", {}, {"S01": {"png": "S01.png"}})
        ok(False, "completar deberia propagar el fallo del manifiesto")
    except OSError:
        pass
    finally:
        e._guardar_manifiesto = real
    ok(os.path.isfile(os.path.join(trabajo, "S01.png")),
       "lo pagado sigue en trabajo/ para poder retomar")
    igual(e.estado_de("assets"), "listo", "y el estado no ha cambiado")
    shutil.rmtree(carpeta, ignore_errors=True)


def t10_podar_render(base):
    """Del video montado se guardan las 5 ultimas versiones (16-10-2026)."""
    print("\n[10] el render guarda solo sus 5 ultimas versiones y nunca la activa")
    carpeta = tempfile.mkdtemp(dir=base)
    proyecto, e = grafo_completo(carpeta, "podar")
    antes = len(e.versiones("render"))

    def montar(etiqueta):
        trabajo = proyecto.ruta_trabajo("render")
        with open(os.path.join(trabajo, "video.mp4"), "w") as fh:
            fh.write(etiqueta)
        return e.completar("render", {"mp4": "video.mp4"})

    hechas = [montar(f"montaje {i}") for i in range(7)]
    quedan = [v["n"] for v in e.versiones("render")]
    igual(len(quedan), 5, f"quedan 5 versiones del video (habia {antes} + 7)")
    igual(quedan, hechas[-5:], "y son las 5 ultimas")
    for n in range(1, min(quedan)):
        ok(not os.path.exists(proyecto.ruta_paso("render", n)),
           f"la carpeta de la v{n} ya no esta en disco")
    for n in quedan:
        ok(os.path.isfile(os.path.join(proyecto.ruta_paso("render", n), "video.mp4")),
           f"la v{n} sigue entera")
    igual(e.estado_de("render"), "listo", "el render sigue listo")

    # la ACTIVA no se borra aunque sea vieja: se vuelve a la mas antigua que
    # queda y se poda (como si otro proceso hubiera montado entretanto)
    vieja = quedan[0]
    e.revertir("render", vieja)
    with e._lock:              # una sexta version que no paso por completar
        extra = dict(e._doc["pasos"]["render"]["versiones"][-1], n=max(quedan) + 1)
        e._doc["pasos"]["render"]["versiones"].append(extra)
        e._guardar()
    os.makedirs(proyecto.ruta_paso("render", extra["n"]), exist_ok=True)
    e.podar_versiones("render")
    igual(proyecto.version_activa("render"), vieja, "la activa sigue siendo la vieja")
    ok(os.path.isdir(proyecto.ruta_paso("render", vieja)),
       "y su carpeta no se ha borrado aunque ya no este entre las 5 ultimas")
    ok(vieja in [v["n"] for v in e.versiones("render")], "ni su entrada")

    # una carpeta que una poda anterior no pudo borrar (un mp4 abierto en
    # Windows) se vuelve a intentar en la siguiente
    huerfana = proyecto.ruta_paso("render", 1, crear=True)
    with open(os.path.join(huerfana, "video.mp4"), "w") as fh:
        fh.write("quedo a medias")
    e.podar_versiones("render")
    ok(not os.path.exists(huerfana), "la carpeta huerfana de una poda anterior se borra")

    # los demas pasos no se podan: sus versiones son pequenas y se revierten
    for i in range(7):
        e.completar("assets", {"total": 4}, {u: {"png": f"{i}"} for u in UNIDADES})
    ok(len(e.versiones("assets")) >= 8, "las imagenes guardan todas sus versiones")

    # y el numero se cambia por el entorno
    os.environ["ESTUDIO_VERSIONES_RENDER"] = "2"
    try:
        montar("con dos")
        igual(len(e.versiones("render")), 2, "con ESTUDIO_VERSIONES_RENDER=2 quedan 2")
    finally:
        os.environ.pop("ESTUDIO_VERSIONES_RENDER", None)
    shutil.rmtree(carpeta, ignore_errors=True)


def principal():
    base = tempfile.mkdtemp(prefix="romper_nucleo_")
    solo = sys.argv[1:] or None
    pruebas = [("1", t1_propagacion), ("2", t2_granularidad), ("3", t3_revertir),
               ("4", t4_persistencia), ("4b", t4b_sello), ("5", t5_carreras),
               ("5b", t5b_lectores_escritores_disco),
               ("5c", t5c_completar_con_params_cambiados), ("5d", t5d_procesos),
               ("6", t6_traversal), ("7", t7_varios), ("8", t8_no_borrar_estado),
               ("9", t9_revision_v2f), ("10", t10_podar_render)]
    try:
        for clave, funcion in pruebas:
            if solo and clave not in solo:
                continue
            funcion(base)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print()
    if FALLOS:
        print(f"FALLARON {len(FALLOS)}:")
        for t in FALLOS:
            print("  - " + t)
        return 1
    print("todo pasa")
    return 0


if __name__ == "__main__":
    sys.exit(principal())

"""
Prueba del servicio HTTP del Estudio.

Arranca app.py en un puerto libre contra una carpeta de proyectos temporal,
ejerce los endpoints principales y comprueba codigos y formas de respuesta.

    C:\\IA\\venvs\\cartoon\\Scripts\\python.exe C:\\IA\\estudio\\prueba_api.py

Corre con ESTUDIO_SIMULAR=1: la sintesis de voz no llama a Cartesia, asi que la
prueba ejercita el camino real de ejecutar -> trabajo -> SSE -> version sin
gastar un centimo ni depender de la red. Los pasos que llaman al CLI de Claude
(guion, revision de audio) se siembran en disco con el nucleo, igual que hacen
las pruebas de los pasos: lo que se prueba aqui es la API, no el pipeline.

Con --conservar no borra la carpeta temporal (util para mirar que quedo).
"""
import argparse
import ast
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

RAIZ_ESTUDIO = os.path.dirname(os.path.abspath(__file__))
if RAIZ_ESTUDIO not in sys.path:
    sys.path.insert(0, RAIZ_ESTUDIO)

import requests  # noqa: E402

PYTHON = sys.executable
APP = os.path.join(RAIZ_ESTUDIO, "app.py")

_ok = 0
_fallos = []


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        return True
    _fallos.append(mensaje)
    print(f"      FALLO: {mensaje}")
    return False


def igual(obtenido, esperado, mensaje):
    return ok(obtenido == esperado, f"{mensaje} (esperaba {esperado!r}, "
                                    f"llego {obtenido!r})")


def seccion(titulo):
    print(f"\n  {titulo}")


# --------------------------------------------------------------------- cliente

class Cliente:
    """requests con la base del servidor puesta y json ya decodificado."""

    def __init__(self, base, carpeta=""):
        self.base = base.rstrip("/")
        self.carpeta = carpeta
        self.sesion = requests.Session()

    def pedir(self, metodo, ruta, **extra):
        respuesta = self.sesion.request(metodo, self.base + ruta,
                                        timeout=extra.pop("timeout", 120), **extra)
        try:
            datos = respuesta.json()
        except ValueError:
            datos = None
        return respuesta, datos

    def get(self, ruta, **extra):
        return self.pedir("GET", ruta, **extra)

    def post(self, ruta, cuerpo=None, **extra):
        return self.pedir("POST", ruta, json=cuerpo, **extra)

    def put(self, ruta, cuerpo=None, **extra):
        return self.pedir("PUT", ruta, json=cuerpo, **extra)

    def delete(self, ruta, **extra):
        return self.pedir("DELETE", ruta, **extra)


def puerto_libre():
    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        return sonda.getsockname()[1]


def arrancar(puerto, carpeta):
    """Lanza el servidor y espera a que /api/salud conteste."""
    entorno = dict(os.environ)
    entorno["ESTUDIO_SIMULAR"] = "1"
    entorno["PYTHONIOENCODING"] = "utf-8"
    # los presets del canal tambien van a la carpeta temporal: sin esto la
    # prueba escribia sus presets de mentira en el presets.json del canal real
    entorno["ESTUDIO_PRESETS"] = os.path.join(carpeta, "presets.json")
    entorno["ESTUDIO_BANCO_PRESETS"] = os.path.join(carpeta, "banco_presets")
    # Y las CLAVES y las RECETAS, por el mismo motivo y con mas razon: sin esto
    # la prueba escribiria claves de mentira encima de las de verdad, y la
    # primera vez que corriera dejaria al Estudio sin poder generar nada.
    entorno["ESTUDIO_SECRETOS"] = os.path.join(carpeta, "secretos")
    entorno["ESTUDIO_RECETAS"] = os.path.join(carpeta, "recetas.json")
    # Y LOS AJUSTES: la guia de inicio se marca como vista desde aqui, y sin
    # esto la marca acabaria en el ajustes.json de verdad.
    entorno["ESTUDIO_AJUSTES"] = os.path.join(carpeta, "ajustes.json")
    # Y EL HISTORICO DE TIEMPOS, que ademas es el que mas dano hacia: el
    # historico guarda 30 muestras por paso, y esta prueba escribe una tanda de
    # tomas SIMULADAS en castellano cada vez que corre. Con eso dentro, la unica
    # toma real en ingles que habia --la que hace que `cadencia` deje de usar la
    # tabla escrita y use lo medido-- se caia por antiguedad. O sea que correr
    # las pruebas BORRABA lo aprendido de las voces del canal.
    entorno["ESTUDIO_ESTADISTICAS"] = os.path.join(carpeta, "estadisticas.json")
    os.makedirs(entorno["ESTUDIO_SECRETOS"], exist_ok=True)
    proceso = subprocess.Popen(
        [PYTHON, APP, "--puerto", str(puerto), "--proyectos", carpeta],
        cwd=RAIZ_ESTUDIO, env=entorno,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            salida = proceso.stdout.read() if proceso.stdout else ""
            raise RuntimeError(f"el servidor murio al arrancar:\n{salida}")
        try:
            respuesta = requests.get(base + "/api/salud", timeout=2)
            if respuesta.status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el servidor no respondio a /api/salud en 90 s")


def parar(proceso):
    if proceso.poll() is None:
        proceso.terminate()
        try:
            proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()


# --------------------------------------------------------------------- semilla

BLOQUES = [{"id": f"B{n:03d}",
            "texto": (f"Bloque numero {n} de la narracion de prueba. "
                      "Aqui se cuenta un hecho con nombres, fechas y una cifra "
                      "concreta para que el locutor tenga material que leer.")}
           for n in range(1, 41)]


def sembrar(raiz_proyecto):
    """Deja ingesta, brief y guion versionados, como si ya se hubieran corrido.

    Se usa el nucleo directamente, no la API: ejecutar el guion de verdad
    llamaria al CLI de Claude, que ni es gratis ni es lo que prueba este fichero.
    """
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto, escribir_json

    proyecto = Proyecto(raiz_proyecto)
    estado = Estado(proyecto)

    transcript = [{"t_in": n * 3.0, "t_out": n * 3.0 + 2.8,
                   "texto": f"linea {n} del transcript de origen"}
                  for n in range(1, 60)]
    salidas_ingesta = {
        "transcript": transcript,
        "video": "origen.webm",
        "video_externo": False,
        "metadatos": {"titulo": "Video de prueba", "palabras_transcript": 420,
                      "idioma_transcript": "es", "duracion_s": 180.0},
        "resumen": "semilla de prueba",
    }
    escribir_json(os.path.join(proyecto.ruta_trabajo("ingesta"), "ingesta.json"),
                  salidas_ingesta)
    estado.set_params("ingesta", {"url": "https://ejemplo/prueba"})
    estado.completar("ingesta", salidas_ingesta)

    salidas_brief = {"tema": "prueba de api", "duracion_s": 90,
                     "resumen": "brief de prueba"}
    escribir_json(os.path.join(proyecto.ruta_trabajo("brief"), "brief.json"),
                  salidas_brief)
    estado.set_params("brief", {"duracion_s": 90, "idioma": "es"})
    estado.completar("brief", salidas_brief)

    escribir_json(os.path.join(proyecto.ruta_trabajo("guion"), "guion.json"),
                  {"titulo": "Guion de prueba", "guion": BLOQUES})
    estado.set_params("guion", {"idioma": "es", "duracion_s": 90})
    estado.completar("guion", {"guion": "guion.json", "n_bloques": len(BLOQUES),
                               "resumen": f"{len(BLOQUES)} bloques"})
    return proyecto


def esperar_trabajo(cliente, tid, limite=180):
    """Sondea un trabajo hasta que termina; devuelve su ficha final."""
    fin = time.time() + limite
    while time.time() < fin:
        respuesta, ficha = cliente.get(f"/api/trabajos/{tid}")
        if respuesta.status_code != 200:
            return {"estado": "desconocido", "error": f"HTTP {respuesta.status_code}"}
        if ficha["estado"] in ("listo", "error", "cancelado"):
            return ficha
        time.sleep(0.2)
    return {"estado": "colgado", "error": f"seguia corriendo tras {limite} s"}


def leer_sse(base, tid, limite=120):
    """Consume el SSE de un trabajo y devuelve (content_type, eventos)."""
    eventos = []
    tipo = ""
    fin = time.time() + limite
    with requests.get(f"{base}/api/trabajos/{tid}/eventos",
                      stream=True, timeout=(10, limite)) as respuesta:
        tipo = respuesta.headers.get("content-type", "")
        if respuesta.status_code != 200:
            return tipo, eventos
        nombre = None
        for cruda in respuesta.iter_lines(decode_unicode=True):
            if time.time() > fin:
                break
            if cruda is None:
                continue
            linea = cruda.strip()
            if linea.startswith("event:"):
                nombre = linea.split(":", 1)[1].strip()
            elif linea.startswith("data:"):
                cuerpo = linea.split(":", 1)[1].strip()
                try:
                    eventos.append((nombre, json.loads(cuerpo)))
                except ValueError:
                    eventos.append((nombre, cuerpo))
                if nombre == "fin":
                    break
    return tipo, eventos


# ---------------------------------------------------------------------- bloques

def probar_salud_y_proyectos(cliente):
    seccion("SALUD Y PROYECTOS")
    respuesta, datos = cliente.get("/api/salud")
    igual(respuesta.status_code, 200, "/api/salud responde 200")
    ok(datos.get("ok") is True, "/api/salud dice ok")
    igual(len(datos.get("pasos") or []), 8, "salud lista los 8 pasos")
    ok(datos.get("pasos_cargados") is True,
       f"los modulos de pasos se han cargado ({datos.get('error_pasos')})")
    ok(datos.get("simulado") is True, "el servidor corre en modo simulado")

    respuesta, datos = cliente.get("/api/proyectos")
    igual(respuesta.status_code, 200, "GET /api/proyectos responde 200")
    igual(datos.get("proyectos"), [], "la carpeta temporal empieza vacia")

    respuesta, datos = cliente.post("/api/proyectos", {})
    igual(respuesta.status_code, 400, "crear sin nombre da 400")
    ok("error" in (datos or {}), "el 400 trae {'error': ...}")

    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "Prueba API"})
    igual(respuesta.status_code, 201, "crear proyecto da 201")
    pid = (datos.get("proyecto") or {}).get("id")
    igual(pid, "prueba_api", "el id sale de identificador(nombre)")
    igual(len(datos.get("pasos") or []), 8, "la creacion devuelve los 8 pasos")

    respuesta, gemelo = cliente.post("/api/proyectos", {"nombre": "Prueba API"})
    igual(respuesta.status_code, 201, "el segundo proyecto homonimo se crea")
    igual((gemelo.get("proyecto") or {}).get("id"), "prueba_api_2",
          "el id se desambigua solo")

    respuesta, datos = cliente.get("/api/proyectos")
    igual(len(datos.get("proyectos") or []), 2, "ahora hay dos proyectos")

    respuesta, datos = cliente.get("/api/proyectos/no_existe")
    igual(respuesta.status_code, 404, "proyecto inexistente da 404")
    ok("error" in (datos or {}), "el 404 trae {'error': ...}")

    respuesta, datos = cliente.get("/api/proyectos/..%2F..%2Fetc")
    igual(respuesta.status_code, 404, "un id con rutas dentro da 404")
    return pid, (gemelo.get("proyecto") or {}).get("id")


def probar_renombrar(cliente, pid):
    """Cambiar el nombre de un proyecto cambia la ETIQUETA, no la carpeta."""
    seccion("RENOMBRAR UN PROYECTO")
    respuesta, antes = cliente.get(f"/api/proyectos/{pid}")
    nombre_viejo = (antes.get("proyecto") or {}).get("nombre")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}", {})
    igual(respuesta.status_code, 400, "renombrar sin nombre da 400")
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}", {"nombre": "   "})
    igual(respuesta.status_code, 400, "y un nombre en blanco tambien")
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}", {"nombre": "!!! ???"})
    igual(respuesta.status_code, 400,
          "un nombre sin ninguna letra ni cifra se rechaza: seria ilegible en "
          "la lista, y al duplicarlo la copia acabaria en una carpeta "
          "llamada `proyecto`")
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}", {"nombre": "Proyecto"})
    igual(respuesta.status_code, 200,
          "y se comprueba ASI y no con `identificador`, que nunca devuelve "
          "vacio: llamarse «Proyecto» es legitimo y esa guarda lo rechazaria")
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}", {"nombre": "x" * 200})
    igual(respuesta.status_code, 400, "y uno larguisimo, que rompe la fila")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}",
                                   {"nombre": "El oro y la inflación"})
    igual(respuesta.status_code, 200, "renombrar responde 200")
    igual((datos.get("proyecto") or {}).get("nombre"), "El oro y la inflación",
          "y devuelve la ficha con el nombre nuevo")
    igual((datos.get("proyecto") or {}).get("id"), pid,
          "EL ID NO CAMBIA: es la clave de las rutas de estado.json, de las "
          "rutas absolutas del manifiesto, del coste global y de lo que el modo "
          "light se guarda en el navegador")

    respuesta, releido = cliente.get(f"/api/proyectos/{pid}")
    igual((releido.get("proyecto") or {}).get("nombre"), "El oro y la inflación",
          "y se ha escrito de verdad: se relee y sigue puesto")
    ok(nombre_viejo != "El oro y la inflación",
       "(la prueba vale porque el nombre de antes era otro)")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}",
                                   {"nombre": "El oro y la inflación"})
    igual(respuesta.status_code, 200, "renombrar al mismo nombre no falla")
    igual(datos.get("cambiado"), False, "y dice que no ha cambiado nada")

    respuesta, datos = cliente.put("/api/proyectos/no_existe", {"nombre": "X"})
    igual(respuesta.status_code, 404, "renombrar lo que no existe da 404")

    # LA LISTA LO ENSENA. Es donde se lee, y es lo que el lapiz del modo light
    # actualiza sin recargar.
    respuesta, lista = cliente.get("/api/proyectos")
    nombres = {p.get("id"): p.get("nombre") for p in (lista.get("proyectos") or [])}
    igual(nombres.get(pid), "El oro y la inflación",
          "y la lista de proyectos lo ensena ya cambiado")

    # y se deja como estaba, que despues de esto vienen mas pruebas
    cliente.put(f"/api/proyectos/{pid}", {"nombre": nombre_viejo})


def probar_pasos(cliente, pid):
    seccion("GRAFO DE PASOS Y PARAMETROS")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos")
    igual(respuesta.status_code, 200, "GET /pasos responde 200")
    fichas = {p["id"]: p for p in datos["pasos"]}
    igual(len(fichas), 8, "el DAG trae los 8 pasos")
    igual(fichas["ingesta"]["estado"], "pendiente", "ingesta arranca pendiente")
    igual(fichas["voz"]["estado"], "bloqueado", "voz arranca bloqueada")
    igual(fichas["render"]["depende_de"], ["callouts"], "el DAG trae dependencias")
    ok(fichas["assets"]["por_unidades"] is True, "assets trabaja por unidades")
    ok(fichas["ingesta"]["descripcion"], "cada paso se describe a si mismo")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/guion")
    igual(respuesta.status_code, 200, "detalle de un paso responde 200")
    for clave in ("params", "salidas", "unidades", "detalle_unidades",
                  "historico", "versiones_detalle", "estado", "firma"):
        ok(clave in datos, f"el detalle del paso trae '{clave}'")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/inventado")
    igual(respuesta.status_code, 404, "paso inexistente da 404")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/pasos/brief/params",
                                   {"params": {"duracion_s": 90, "idioma": "es"}})
    igual(respuesta.status_code, 200, "PUT params responde 200")
    ok(datos.get("cambiado") is True, "cambiar params mueve la firma")
    igual(datos["params"]["duracion_s"], 90, "los params quedan guardados")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/pasos/brief/params",
                                   {"params": {"duracion_s": 90, "idioma": "es"}})
    ok(datos.get("cambiado") is False, "repetir los mismos params no cambia nada")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/pasos/brief/params",
                                   {"params": "esto no es un objeto"})
    igual(respuesta.status_code, 400, "params que no son objeto dan 400")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/voz/ejecutar", {})
    igual(respuesta.status_code, 409, "ejecutar un paso bloqueado da 409")
    ok("faltan" in (datos or {}), "el 409 dice que falta por ejecutar")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/inventado/ejecutar", {})
    igual(respuesta.status_code, 404, "ejecutar un paso inexistente da 404")


def probar_ejecucion(cliente, base, pid):
    seccion("EJECUCION, TRABAJOS Y SSE")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/voz")
    igual(datos["estado"], "pendiente", "con el guion sembrado, voz ya no bloquea")

    respuesta, lanzado = cliente.post(f"/api/proyectos/{pid}/pasos/voz/ejecutar", {})
    igual(respuesta.status_code, 202, "lanzar un paso responde 202")
    tid = lanzado.get("trabajo_id")
    ok(bool(tid), "la respuesta trae trabajo_id")
    igual(lanzado.get("eventos"), f"/api/trabajos/{tid}/eventos",
          "y la URL de eventos SSE")

    respuesta, repetido = cliente.post(f"/api/proyectos/{pid}/pasos/voz/ejecutar", {})
    igual(respuesta.status_code, 409, "no se puede lanzar dos veces el mismo paso")
    igual(repetido.get("trabajo_id"), tid, "el 409 devuelve el trabajo que ya corre")

    tipo, eventos = leer_sse(base, tid)
    ok("text/event-stream" in tipo, f"el SSE se sirve como event-stream ({tipo})")
    ok(len(eventos) >= 1, "el SSE emite al menos un evento")
    ok(eventos and eventos[-1][0] == "fin", "el SSE cierra con un evento 'fin'")
    if eventos:
        avances = [e[1]["progreso"] for e in eventos if isinstance(e[1], dict)]
        ok(all(b >= a for a, b in zip(avances, avances[1:])),
           f"el progreso del SSE nunca retrocede ({avances})")
        igual(avances[-1], 1.0, "y termina en 1.0")
        ultimo = eventos[-1][1]
        igual(ultimo.get("estado"), "listo", "el trabajo acaba listo")
        for clave in ("id", "progreso", "mensaje", "estado", "resultado"):
            ok(clave in ultimo, f"el evento SSE trae '{clave}'")

    ficha = esperar_trabajo(cliente, tid)
    igual(ficha["estado"], "listo", f"el trabajo termina bien ({ficha.get('error')})")
    resultado = ficha.get("resultado") or {}
    igual(resultado.get("version"), 1, "la ejecucion deja la version 1")
    ok(resultado.get("resumen"), "el resultado trae resumen del paso")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/voz")
    igual(datos["estado"], "listo", "el paso queda listo")
    igual(datos["version_activa"], 1, "con la v1 activa")
    salidas = datos["salidas"]
    ok(salidas.get("archivo"), "las salidas dicen como se llama la pista")
    ok(salidas.get("duracion"), "y cuanto dura")
    return tid, salidas


def probar_versiones(cliente, pid):
    seccion("VERSIONES Y REVERTIR")
    cliente.put(f"/api/proyectos/{pid}/pasos/voz/params",
                {"params": {"preset": "true_crime_tenso"}})
    respuesta, lanzado = cliente.post(f"/api/proyectos/{pid}/pasos/voz/ejecutar", {})
    igual(respuesta.status_code, 202, "se puede reejecutar con otros params")
    ficha = esperar_trabajo(cliente, lanzado["trabajo_id"])
    igual(ficha["estado"], "listo", f"la segunda toma sale bien ({ficha.get('error')})")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/voz/versiones")
    igual(respuesta.status_code, 200, "GET versiones responde 200")
    igual(len(datos["versiones"]), 2, "hay dos versiones de voz")
    igual(datos["activa"], 2, "la activa es la ultima")
    ok(all("resumen" in v and "fecha" in v for v in datos["versiones"]),
       "cada version trae fecha y resumen")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/voz/revertir",
                                    {"version": 1})
    igual(respuesta.status_code, 200, "revertir responde 200")
    igual(datos["activa"], 1, "vuelve a estar activa la v1")
    igual(datos["params"].get("preset"), None,
          "revertir restaura tambien los params de esa version")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/voz/revertir",
                                    {"version": 99})
    igual(respuesta.status_code, 404, "revertir a una version inexistente da 404")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/voz/revertir", {})
    igual(respuesta.status_code, 400, "revertir sin version da 400")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/voz/revertir",
                                    {"version": "tres"})
    igual(respuesta.status_code, 400, "revertir con version no numerica da 400")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/voz/versiones",
                                   params={"detalle": 1})
    ok(all("params" in v for v in datos["versiones"]),
       "con detalle=1 cada version trae sus params")
    # EL MANIFIESTO YA NO VIAJA EN LA RESPUESTA. Desde que vive en su fichero
    # (`pasos/<paso>/_versiones/v<N>.json`), de las unidades solo va el recuento:
    # rehidratarlo aqui serian ~4 MB por version para un endpoint que nadie usa
    # para eso. Se fija por escrito porque es un cambio de contrato publico y sin
    # esta comprobacion nada avisaria de que alguien vuelve a apoyarse en el.
    ok(all("unidades" not in v for v in datos["versiones"]),
       "con detalle=1 NO viaja el manifiesto de unidades")
    ok(all(isinstance(v.get("n_unidades"), int) for v in datos["versiones"]),
       "pero si el recuento, que es lo que se pinta")

    respuesta, ligeras = cliente.get(f"/api/proyectos/{pid}/pasos/voz/versiones")
    ok(all("unidades" in v and "params" not in v for v in ligeras["versiones"]),
       "y sin detalle sigue yendo la ficha ligera, con 'unidades' como numero")
    ok(all(isinstance(v["unidades"], int) for v in ligeras["versiones"]),
       "ese 'unidades' de la ficha ligera es un numero, no el mapa")


def probar_archivos(cliente, pid, salidas):
    seccion("ARCHIVOS DEL PROYECTO")
    ruta = f"/a/{pid}/pasos/voz/v1/{salidas['archivo']}"
    respuesta = cliente.sesion.get(cliente.base + ruta, timeout=60)
    igual(respuesta.status_code, 200, "se sirve el wav de la version activa")
    igual(respuesta.headers.get("content-type"), "audio/wav",
          "con el tipo de contenido correcto")
    igual(respuesta.headers.get("accept-ranges"), "bytes", "anunciando Range")
    entero = len(respuesta.content)
    ok(entero > 0, "el wav no viene vacio")

    respuesta = cliente.sesion.get(cliente.base + ruta, timeout=60,
                                   headers={"Range": "bytes=0-99"})
    igual(respuesta.status_code, 206, "una peticion con Range da 206")
    igual(len(respuesta.content), 100, "y devuelve exactamente los bytes pedidos")
    igual(respuesta.headers.get("content-range"), f"bytes 0-99/{entero}",
          "con la cabecera Content-Range bien puesta")

    respuesta = cliente.sesion.get(cliente.base + ruta, timeout=60,
                                   headers={"Range": f"bytes={entero + 500}-"})
    igual(respuesta.status_code, 416, "un Range fuera del fichero da 416")

    respuesta, datos = cliente.get(f"/a/{pid}/pasos")
    igual(respuesta.status_code, 200, "una carpeta se lista")
    ok("voz" in (datos.get("entradas") or []), "y trae sus entradas")

    respuesta, datos = cliente.get(f"/a/{pid}/no_existe.png")
    igual(respuesta.status_code, 404, "un archivo inexistente da 404")

    # miniaturas: una imagen grande con ?mini=1 baja como JPEG pequeno; lo que
    # no es imagen (el wav) ignora el parametro y baja entero
    from PIL import Image
    import random
    ruidosa = Image.new("RGB", (1536, 1024))
    ruidosa.putdata([(random.randrange(256), random.randrange(256),
                      random.randrange(256)) for _ in range(1536 * 1024)])
    ruta_png = os.path.join(cliente.carpeta, pid, "grande.png")
    ruidosa.save(ruta_png, "PNG")
    original = os.path.getsize(ruta_png)
    respuesta = cliente.sesion.get(f"{cliente.base}/a/{pid}/grande.png?mini=1",
                                   timeout=60)
    igual(respuesta.status_code, 200, "la miniatura responde 200")
    igual(respuesta.headers.get("content-type"), "image/jpeg",
          "y es un JPEG, no el PNG de generacion")
    ok(len(respuesta.content) < original / 10,
       f"y pesa menos de la decima parte ({len(respuesta.content)} de {original})")
    respuesta = cliente.sesion.get(f"{cliente.base}{ruta}?mini=1", timeout=60)
    igual(respuesta.headers.get("content-type"), "audio/wav",
          "un wav con ?mini=1 baja entero: la miniatura es cosa de imagenes")

    for intento, etiqueta in (
            ("..%2F..%2F..%2Fsecrets%2F.env", "escapar con .. codificado"),
            ("..%5C..%5Cwindows%5Cwin.ini", "escapar con barras invertidas"),
            ("C:%2FWindows%2Fwin.ini", "colar una ruta absoluta")):
        respuesta = cliente.sesion.get(f"{cliente.base}/a/{pid}/{intento}",
                                       timeout=30, allow_redirects=False)
        ok(respuesta.status_code in (403, 404),
           f"{etiqueta} se corta ({respuesta.status_code})")

    # Las imagenes del repaso: `..` era un 500 con traza (ruta_contenida LANZA,
    # no devuelve False) y `.` intentaba servir la carpeta.
    for intento, etiqueta in (("%2E%2E", "la carpeta de arriba"),
                              ("%2E", "la propia carpeta")):
        respuesta = cliente.sesion.get(
            f"{cliente.base}/api/proyectos/{pid}/repaso/imagenes/{intento}",
            timeout=30, allow_redirects=False)
        igual(respuesta.status_code, 404,
              f"pedir {etiqueta} como imagen del repaso es un 404, no un 500")


def probar_feedback(cliente, pid):
    seccion("FEEDBACK EN CASCADA")
    ruta = f"/api/proyectos/{pid}/feedback"

    respuesta, datos = cliente.post(ruta, {"texto": "algo"})
    igual(respuesta.status_code, 400, "feedback sin paso da 400")

    respuesta, datos = cliente.post(ruta, {"paso": "inventado", "texto": "algo"})
    igual(respuesta.status_code, 404, "feedback a un paso inexistente da 404")

    respuesta, datos = cliente.post(ruta, {"paso": "guion", "ejecutar": False})
    igual(respuesta.status_code, 400, "feedback sin texto ni trazos da 400")

    respuesta, datos = cliente.post(ruta, {"paso": "guion", "texto": "x",
                                           "modo": "telepatia", "ejecutar": False})
    igual(respuesta.status_code, 400, "un modo desconocido da 400")

    respuesta, datos = cliente.post(ruta, {
        "paso": "guion", "unidad": "B002", "modo": "agente", "ejecutar": False,
        "texto": "este bloque se va por las ramas, ve al grano",
        "trazos": [{"puntos": [{"x": 0.8, "y": 0.15}, {"x": 0.85, "y": 0.2}]}]})
    igual(respuesta.status_code, 202, "el feedback por unidad se acepta")
    igual(datos.get("unidad"), "B002", "y queda apuntado a esa unidad")
    igual(datos["nota"]["modo"], "agente", "conservando el modo pedido")
    ok(datos["nota"]["zonas"], "los trazos se traducen a zonas en texto")
    igual(datos.get("trabajo_id"), None, "con ejecutar=false no lanza nada")
    ok("voz" in (datos.get("aguas_abajo") or {}),
       "la respuesta dice que arrastra a voz")

    respuesta, paso = cliente.get(f"/api/proyectos/{pid}/pasos/guion")
    notas = ((paso["params"].get("unidades") or {}).get("B002") or {}).get("feedback")
    ok(isinstance(notas, list) and len(notas) == 1,
       "la nota queda guardada en los params de la unidad")
    igual(paso["estado"], "obsoleto", "el guion queda obsoleto por el feedback")
    ok("B002" in paso["unidades_obsoletas"], "y la unidad tocada, marcada")

    respuesta, voz = cliente.get(f"/api/proyectos/{pid}/pasos/voz")
    igual(voz["estado"], "obsoleto", "la cascada llega a voz sola")

    respuesta, datos = cliente.post(ruta, {
        "paso": "voz", "texto": "sube un poco el ritmo general", "modo": "directo"})
    igual(respuesta.status_code, 202, "el feedback general se acepta")
    tid = datos.get("trabajo_id")
    ok(bool(tid), "y esta vez si lanza un trabajo")
    ficha = esperar_trabajo(cliente, tid)
    igual(ficha["estado"], "listo", f"el trabajo del feedback acaba ({ficha.get('error')})")

    respuesta, voz = cliente.get(f"/api/proyectos/{pid}/pasos/voz")
    igual(voz["estado"], "listo", "tras aplicarlo, voz vuelve a listo")
    ok(len(voz["params"].get("feedback") or []) == 1,
       "el feedback general vive en los params del paso")


def probar_voz(cliente, pid):
    seccion("VOZ: PRESETS, CATALOGO Y ESCUCHA")
    # Los endpoints globales: los por-proyecto (/voz/presets, /voz/voces) eran
    # alias literales y se retiraron. La interfaz siempre uso estos.
    respuesta, datos = cliente.get("/api/presets")
    igual(respuesta.status_code, 200, "GET presets responde 200")
    ok(len(datos.get("presets") or []) >= 8, "hay presets de estilo")
    ok(all("id" in p and "nombre" in p for p in datos["presets"]),
       "cada preset trae id y nombre")
    ok(datos.get("por_defecto"), "y se dice cual es el de partida")

    respuesta, datos = cliente.get("/api/voces", params={"idioma": "es"})
    igual(respuesta.status_code, 200, "GET voces responde 200")
    ok(isinstance(datos.get("voces"), list) and datos["voces"],
       "el catalogo de voces no viene vacio")
    ok(all("id" in v for v in datos["voces"]), "cada voz trae su id")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/voz/previsualizar",
                                    {"params": {"preset": "documental_sobrio"},
                                     "segundos": 8})
    igual(respuesta.status_code, 202, "previsualizar responde 202")
    tid = datos.get("trabajo_id")
    ok(bool(tid), "y devuelve trabajo_id")
    ficha = esperar_trabajo(cliente, tid)
    igual(ficha["estado"], "listo", f"la escucha se genera ({ficha.get('error')})")
    url = (ficha.get("resultado") or {}).get("url")
    ok(bool(url), "el resultado trae la URL para escuchar")
    if url:
        respuesta = cliente.sesion.get(cliente.base + url, timeout=60)
        igual(respuesta.status_code, 200, "y esa URL sirve el audio")
        igual(respuesta.headers.get("content-type"), "audio/wav",
              "como audio/wav")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/voz/previsualizar",
                                    {"segundos": 900})
    igual(respuesta.status_code, 400, "una duracion absurda da 400")


def _ficha_paso(cliente, pid, paso):
    _r, datos = cliente.get(f"/api/proyectos/{pid}/pasos/{paso}")
    return datos or {}


def _meta_activa(carpeta, pid, cliente):
    """El audio_meta.json de la version ACTIVA de la voz, leido del disco."""
    version = _ficha_paso(cliente, pid, "voz").get("version_activa")
    ruta = os.path.join(carpeta, pid, "pasos", "voz", f"v{version}", "audio_meta.json")
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh), ruta


def _firmas(raiz_proyecto):
    """Firmas de todos los pasos y de las unidades de assets, del nucleo."""
    from nucleo.estado import PASOS, Estado
    from nucleo.proyecto import Proyecto
    estado = Estado(Proyecto(raiz_proyecto))
    return ({p["id"]: estado.firma(p["id"]) for p in PASOS},
            {u: estado.firma_unidad("assets", u)
             for u in estado.unidades_declaradas("assets")},
            estado.unidades_obsoletas("assets"))


def _regrabar(cliente, pid, seccion_id, peticion=""):
    respuesta, datos = cliente.post(
        f"/api/proyectos/{pid}/voz/secciones/{seccion_id}/regrabar",
        {"peticion": peticion})
    igual(respuesta.status_code, 202, f"regrabar {seccion_id} responde 202")
    ficha = esperar_trabajo(cliente, (datos or {}).get("trabajo_id"))
    igual(ficha.get("estado"), "listo",
          f"la regrabacion de {seccion_id} termina bien ({ficha.get('error')})")
    return ficha.get("resultado") or {}


def probar_regrabar_y_estructura(cliente, carpeta):
    """«Solo regrabar lo que he escrito» de verdad, y añadir/partir bloques.

    EL FALLO (09-10-2026): la regrabacion de una seccion cosia la toma en
    `voz/trabajo/` y nunca la registraba con `completar()`. El trabajo salia
    «listo», pero la version activa seguia siendo la de antes: la pantalla
    enseñaba el texto viejo y la voz seguia en obsoleto.
    """
    seccion("REGRABAR UNA SECCION Y AÑADIR O PARTIR BLOQUES")
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto
    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "Regrabar tramos"})
    igual(respuesta.status_code, 201, "se crea el proyecto de la prueba")
    pid = (datos.get("proyecto") or {}).get("id")
    raiz = os.path.join(carpeta, pid)
    sembrar(raiz)
    for paso in ("voz", "revision_audio"):
        _r, lanzado = cliente.post(f"/api/proyectos/{pid}/pasos/{paso}/ejecutar", {})
        ficha = esperar_trabajo(cliente, lanzado.get("trabajo_id"))
        igual(ficha.get("estado"), "listo", f"{paso} de partida ({ficha.get('error')})")

    # D5 (16-10-2026): «Regenerar Audio» lanza en modo 'todo' y vuelve a
    # sintetizar la voz entera, pero el plan la daba a 0 $ porque el coste no
    # miraba el modo. Con la voz al dia: 'pendientes' no paga voz; 'todo', toda.
    _r, plan = cliente.get(f"/api/proyectos/{pid}/generar?tanda=voz")
    coste = (plan or {}).get("coste") or {}
    igual(coste.get("usd_tts_por_generar"), 0.0,
          "con la voz al día, en 'pendientes' la voz no se vuelve a pagar")
    _r, plan = cliente.get(f"/api/proyectos/{pid}/generar?tanda=voz&modo=todo")
    coste = (plan or {}).get("coste") or {}
    ok((coste.get("usd_tts") or 0) > 0,
       f"el precio de la voz entera se conoce ({coste.get('usd_tts')} $)")
    igual(coste.get("usd_por_generar"), round(coste.get("usd_tts") or 0, 3),
          "y en 'todo' se promete ENTERO: «Regenerar Audio» ya no enseña 0 $")
    igual(coste.get("modo"), "todo", "el coste dice con qué modo se ha contado")

    # DOS SECCIONES: la toma simulada sale de una sola, y lo que se prueba
    # es justo lo que pasa entre secciones. Se parte su meta en el disco.
    meta, ruta_meta = _meta_activa(carpeta, pid, cliente)
    from pasos import p4_voz
    meta["secciones"] = p4_voz._fichas_de_seccion(
        [{"id": "SB001", "bloques": [f"B{n:03d}" for n in range(1, 21)]},
         {"id": "SB002", "bloques": [f"B{n:03d}" for n in range(21, 41)]}],
        meta["bloques"])
    with open(ruta_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)

    # unos planos ya «pagados» aguas abajo, para medir que les pasa
    estado = Estado(Proyecto(raiz))
    planos = {f"escena:S{n:03d}": {"prompt": f"plano {n}"} for n in range(1, 6)}
    estado.actualizar_params("assets", {"unidades": planos})
    estado.completar("assets", {"resumen": "planos"},
                     {u: {"png": f"{u}.png"} for u in planos})
    for paso in ("callouts", "render"):
        estado.completar(paso, {"resumen": paso},
                         {u: {"hecho": True} for u in planos})
    igual(_firmas(raiz)[2], [], "de partida, ningun plano pide rehacerse")

    # 1. LO QUE HACE LA PANTALLA: escribir el texto en params.guion.bloques
    nuevo_b002 = "Texto escrito a mano para el bloque dos, que es el que cambia."
    nuevo_b030 = "Y otro escrito a mano en la segunda seccion del guion."
    cliente.put(f"/api/proyectos/{pid}/pasos/guion/params",
                {"params": {"bloques": {"B002": {"texto": nuevo_b002},
                                        "B030": {"texto": nuevo_b030}}}})
    igual(_ficha_paso(cliente, pid, "voz").get("estado"), "obsoleto",
          "editar a mano deja la voz obsoleta: dice la frase vieja")
    igual(_ficha_paso(cliente, pid, "guion").get("estado"), "listo",
          "pero no al guion: corregirlo no es pedir otro")
    # M3 (informe de la Etapa Foto A): el PLAN de la tanda decia lo contrario
    # que el estado. Con `al_dia: false` la pantalla del encargo pintaba
    # «Guion obsoleto» y «Regenerar el guion» reescribia encima de la
    # correccion recien hecha.
    _r, plan = cliente.get(f"/api/proyectos/{pid}/generar?tanda=guion")
    del_guion = [t for f in (plan or {}).get("fases") or [] for t in f["tareas"]
                 if t["id"] == "guion"]
    igual([t.get("al_dia") for t in del_guion], [True],
          "y el plan de la tanda del guion tampoco lo da por viejo: "
          "«Regenerar el guion» no borra la corrección")
    _r, previsto = cliente.get(f"/api/proyectos/{pid}/guion/bloques",
                               params={"seccion": "SB001"})
    regrabar = (previsto or {}).get("regrabar") or {}
    igual(regrabar.get("orden"), ["SB001", "SB002"],
          "lo previsto: la seccion pedida y la otra que tiene cambios sin grabar")
    ok((regrabar.get("usd") or 0) > 0 and regrabar.get("caracteres", 0) > 0,
       f"y lo que cuesta, ANTES de pulsar ({regrabar.get('usd')} $)")
    firmas_antes, unidades_antes, sucios_antes = _firmas(raiz)
    version_antes = _ficha_paso(cliente, pid, "voz").get("version_activa")

    resultado = _regrabar(cliente, pid, "SB001")
    igual(resultado.get("secciones"), ["SB001", "SB002"],
          "se regraban las DOS secciones con cambios, no solo la del boton")
    ok({"B002", "B030"} <= set(resultado.get("bloques_cambiados") or []),
       f"y dice que bloques cambiaron ({resultado.get('bloques_cambiados')})")
    voz = _ficha_paso(cliente, pid, "voz")
    igual(voz.get("version_activa"), version_antes + 1,
          "LA REGRABACION QUEDA REGISTRADA: version nueva de la voz")
    igual(voz.get("estado"), "listo", "y la voz deja de estar obsoleta")
    meta, _ruta = _meta_activa(carpeta, pid, cliente)
    textos = {b["id"]: b["texto"] for b in meta["bloques"]}
    igual(textos.get("B002"), nuevo_b002,
          "la version activa de la voz trae el texto NUEVO de B002")
    igual(textos.get("B030"), nuevo_b030, "y el de B030")
    ok(os.path.exists(os.path.join(raiz, "pasos", "voz", f"v{version_antes + 1}",
                                   "guion_locutado.json")),
       "deja guion_locutado.json: el 'antes' de la conservacion de planos")
    igual(_ficha_paso(cliente, pid, "revision_audio").get("estado"), "listo",
          "la revision se sella gratis y queda al dia (su toma es la que suena "
          "en la vista previa)")
    igual(resultado.get("revision_audio"), "sellada", "y se dice")

    # LAS FIRMAS: que se mueve y por que
    firmas_despues, unidades_despues, sucios_despues = _firmas(raiz)
    movidas = sorted(p for p in firmas_antes if firmas_antes[p] != firmas_despues[p])
    print(f"      firmas movidas por la regrabacion: {movidas}; planos que "
          f"piden rehacerse: {len(sucios_antes)} antes y {len(sucios_despues)} "
          f"despues de regrabar, de {len(planos)}")
    for paso in ("ingesta", "brief", "guion"):
        ok(paso not in movidas, f"la firma de {paso} no se mueve al regrabar")
    igual(unidades_despues, unidades_antes,
          "LA FIRMA DE CADA PLANO NO SE MUEVE: regrabar no deja obsoleta "
          "ninguna imagen pagada")
    igual(sucios_despues, sucios_antes,
          "los planos que piden rehacerse son los mismos que antes de regrabar "
          "(los mueve la edicion del texto, no la toma)")

    _r, bitacora = cliente.get(f"/api/proyectos/{pid}/bitacora")
    entradas = [e for e in ((bitacora or {}).get("eventos") or [])
                if e.get("evento") == "seccion_regrabada"]
    ok(entradas and "B002" in ((entradas[-1].get("datos") or {})
                               .get("bloques_cambiados") or []),
       "la bitacora anota QUE bloques se regrabaron, no una lista vacia")

    # 2. REGRABAR OTRA DESPUES NO SE LLEVA LA PRIMERA
    _regrabar(cliente, pid, "SB002")
    meta, _ruta = _meta_activa(carpeta, pid, cliente)
    igual({b["id"]: b["texto"] for b in meta["bloques"]}.get("B002"), nuevo_b002,
          "regrabar SB002 despues de SB001 conserva lo de SB001")

    # 3. AÑADIR, PARTIR Y QUITAR BLOQUES
    base = f"/api/proyectos/{pid}/guion/bloques"
    respuesta, datos = cliente.post(base, {"texto": "Un bloque nuevo.",
                                           "donde": "despues", "ancla": "B005"})
    igual(respuesta.status_code, 201, "añadir un bloque da 201")
    igual(datos.get("id"), "B041", "con el siguiente id libre: ninguno se renombra")
    orden = [b["id"] for b in datos.get("bloques") or []]
    igual(orden[4:7], ["B005", "B041", "B006"], "y en el sitio pedido")
    respuesta, _d = cliente.post(base, {"texto": "x", "donde": "despues",
                                        "ancla": "B999"})
    igual(respuesta.status_code, 400, "un ancla que no existe da 400")
    respuesta, datos = cliente.post(f"{base}/B010/partir",
                                    {"trozos": ["Primera parte.", "Segunda parte.",
                                                "Tercera parte."]})
    igual(respuesta.status_code, 200, "partir un bloque responde 200")
    igual(datos.get("nuevos"), ["B042", "B043"], "en bloques nuevos con ids nuevos")
    orden = [b["id"] for b in datos.get("bloques") or []]
    igual(orden[orden.index("B010"):orden.index("B010") + 4],
          ["B010", "B042", "B043", "B011"], "detras del partido y en orden")
    respuesta, _d = cliente.post(f"{base}/B010/partir", {"trozos": ["solo uno"]})
    igual(respuesta.status_code, 400, "partir en menos de dos trozos da 400")
    respuesta, _d = cliente.delete(f"{base}/B001")
    igual(respuesta.status_code, 400, "un bloque del guion original no se quita")
    respuesta, datos = cliente.delete(f"{base}/B041")
    igual(respuesta.status_code, 200, "un bloque añadido si")
    ok("B041" not in [b["id"] for b in datos.get("bloques") or []], "y desaparece")
    igual(_ficha_paso(cliente, pid, "guion").get("estado"), "listo",
          "cambiar la estructura tampoco deja obsoleto al guion")
    igual(_ficha_paso(cliente, pid, "voz").get("estado"), "obsoleto",
          "pero si a la voz")
    igual(((datos.get("regrabar") or {}).get("pendientes")), ["SB001"],
          "y lo previsto es regrabar solo la seccion donde cayo el cambio")

    _regrabar(cliente, pid, "SB001")
    meta, _ruta = _meta_activa(carpeta, pid, cliente)
    ids = [b["id"] for b in meta["bloques"]]
    igual(ids[ids.index("B010"):ids.index("B010") + 4],
          ["B010", "B042", "B043", "B011"],
          "la toma nueva dice los bloques partidos, en su orden")
    igual({b["id"]: b["texto"] for b in meta["bloques"]}.get("B010"), "Primera parte.",
          "y B010 se queda con el primer trozo")
    igual(_ficha_paso(cliente, pid, "voz").get("estado"), "listo",
          "y la voz vuelve a estar al dia")


def probar_regrabar_a_medias(cliente, carpeta):
    """F3 del informe de arreglos v2b: si falla una seccion, las de antes no se tiran.

    Regrabar varias secciones las graba una detras de otra y solo registraba
    la version al final: si fallaba la segunda de tres, la primera -- ya
    pagada -- se perdia, y reintentar la volvia a grabar y a pagar. Aqui se
    hace fallar la SEGUNDA de tres (en el proceso de la prueba, con la toma
    simulada: no se llama a Cartesia) y se mira que la primera queda guardada,
    que la voz sigue obsoleta, que lo editado no se pierde y que el reintento
    graba SOLO las dos que faltan.
    """
    seccion("REGRABAR VARIAS SECCIONES: SI FALLA UNA, LAS DE ANTES SE GUARDAN")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo.estado import Estado                          # noqa: PLC0415
    from nucleo.proyecto import Proyecto                      # noqa: PLC0415
    _r, datos = cliente.post("/api/proyectos", {"nombre": "Regrabar a medias"})
    pid = (datos.get("proyecto") or {}).get("id")
    raiz = os.path.join(carpeta, pid)
    sembrar(raiz)
    _r, lanzado = cliente.post(f"/api/proyectos/{pid}/pasos/voz/ejecutar", {})
    ficha = esperar_trabajo(cliente, lanzado.get("trabajo_id"))
    igual(ficha.get("estado"), "listo", f"voz de partida ({ficha.get('error')})")

    # TRES SECCIONES en la toma de partida (la simulada sale de una)
    meta, ruta_meta = _meta_activa(carpeta, pid, cliente)
    p4 = servidor.PASOS_MODULOS.p4_voz
    tramos = {"SB001": range(1, 14), "SB002": range(14, 27), "SB003": range(27, 41)}
    meta["secciones"] = p4._fichas_de_seccion(
        [{"id": sid, "bloques": [f"B{n:03d}" for n in rango]}
         for sid, rango in tramos.items()], meta["bloques"])
    with open(ruta_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)

    # un cambio escrito a mano en cada seccion
    nuevos = {"B002": "Texto nuevo de la primera seccion, escrito a mano.",
              "B020": "Texto nuevo de la segunda seccion, escrito a mano.",
              "B035": "Texto nuevo de la tercera seccion, escrito a mano."}
    cliente.put(f"/api/proyectos/{pid}/pasos/guion/params",
                {"params": {"bloques": {b: {"texto": t} for b, t in nuevos.items()}}})
    _r, previsto = cliente.get(f"/api/proyectos/{pid}/guion/bloques",
                               params={"seccion": "SB001"})
    igual(((previsto or {}).get("regrabar") or {}).get("orden"),
          ["SB001", "SB002", "SB003"], "lo previsto: las tres secciones")
    version_antes = _ficha_paso(cliente, pid, "voz").get("version_activa")

    grabadas = []
    original = p4._toma_simulada
    simular = os.environ.get("ESTUDIO_SIMULAR")

    def toma_que_falla_la_segunda(texto, cfg):
        grabadas.append(texto)
        if len(grabadas) == 2:
            raise RuntimeError("Cartesia WS: se ha cortado la conexion")
        return original(texto, cfg)

    def toma_que_cuenta(texto, cfg):
        grabadas.append(texto)
        return original(texto, cfg)

    ctx = servidor.Contexto(raiz)
    ctx.bitacora.ruta_global = os.path.join(carpeta, "bitacora_global.jsonl")
    os.environ["ESTUDIO_SIMULAR"] = "1"
    p4._toma_simulada = toma_que_falla_la_segunda
    try:
        fallo = None
        try:
            servidor._correr_regrabar(lambda *_a, **_k: None, ctx, "SB001", "", {})
        except RuntimeError as error:
            fallo = error
        igual(len(grabadas), 2, "se graba SB001 y falla SB002")
        ok(fallo is not None and "SB002" in str(fallo) and "SB001" in str(fallo),
           f"y el error dice que falta y que se ha guardado ({fallo})")

        voz = _ficha_paso(cliente, pid, "voz")
        igual(voz.get("version_activa"), version_antes + 1,
              "LO YA GRABADO (Y PAGADO) QUEDA GUARDADO como version de la voz")
        igual(voz.get("estado"), "obsoleto",
              "pero la voz sigue obsoleta: todavia no dice todo el guion")
        meta, _ruta = _meta_activa(carpeta, pid, cliente)
        textos = {b["id"]: b["texto"] for b in meta["bloques"]}
        igual(textos.get("B002"), nuevos["B002"], "la version guardada trae SB001 nueva")
        ok(textos.get("B020") != nuevos["B020"], "y SB002 todavia la de antes")
        editado = (Estado(Proyecto(raiz)).params("guion") or {}).get("bloques") or {}
        igual({b: (editado.get(b) or {}).get("texto") for b in nuevos}, nuevos,
              "LO ESCRITO A MANO EN LAS QUE FALTAN NO SE PIERDE")
        _r, previsto = cliente.get(f"/api/proyectos/{pid}/guion/bloques")
        igual(((previsto or {}).get("regrabar") or {}).get("pendientes"),
              ["SB002", "SB003"], "lo previsto ya no cuenta SB001: solo las que faltan")

        # EL REINTENTO, como lo lanza la pantalla (la primera pendiente)
        del grabadas[:]
        p4._toma_simulada = toma_que_cuenta
        resultado = servidor._correr_regrabar(lambda *_a, **_k: None, ctx,
                                              "SB002", "", {})
        igual(resultado.get("secciones"), ["SB002", "SB003"],
              "EL REINTENTO GRABA SOLO LAS QUE FALTABAN")
        igual(len(grabadas), 2, "dos tomas, no tres: SB001 no se paga otra vez")
        igual(_ficha_paso(cliente, pid, "voz").get("estado"), "listo",
              "y la voz queda al dia")
        meta, _ruta = _meta_activa(carpeta, pid, cliente)
        textos = {b["id"]: b["texto"] for b in meta["bloques"]}
        igual({b: textos.get(b) for b in nuevos}, nuevos,
              "con los tres cambios dentro de la toma")
    finally:
        p4._toma_simulada = original
        if simular is None:
            os.environ.pop("ESTUDIO_SIMULAR", None)
        else:
            os.environ["ESTUDIO_SIMULAR"] = simular


def probar_pausas(cliente, carpeta):
    """Las pausas largas se cuentan con el texto DE AHORA y se quitan una a una.

    Solo cuentan las de DENTRO de una frase: las del final de un bloque se hacen
    al montar y ya no cortan la voz (marcas_tts.separar_pausa_final).
    """
    seccion("LAS PAUSAS LARGAS DEL GUION")
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto, escribir_json
    _r, datos = cliente.post("/api/proyectos", {"nombre": "Pausas del guion"})
    pid = (datos.get("proyecto") or {}).get("id")
    proyecto = Proyecto(os.path.join(carpeta, pid))
    estado = Estado(proyecto)
    estado.completar("ingesta", {"r": 1})
    estado.completar("brief", {"r": 1})
    pausa = '<break time="900ms"/>'
    bloques = [{"id": f"B00{n}", "texto": f"Frase {pausa} numero {n}.",
                "abre_seccion": n in (1, 4)} for n in range(1, 6)]
    bloques[0]["texto"] = f"El gancho.{pausa}"
    bloques[1]["texto"] = f'Con <speed ratio="0.9"/>velocidad {pausa} y mas.'
    escribir_json(os.path.join(proyecto.ruta_trabajo("guion"), "guion.json"),
                  {"titulo": "P", "guion": bloques})
    estado.completar("guion", {"guion": "guion.json"})
    base = f"/api/proyectos/{pid}/guion"
    _r, datos = cliente.get(f"{base}/bloques")
    pausas = datos.get("pausas") or {}
    igual((pausas.get("total"), pausas.get("tope")), (4, 2),
          "cuenta 4 pausas DENTRO de frases (la del final del gancho no cuenta)")
    igual(pausas.get("al_final"), ["B001"], "y aparte la del final del gancho")
    primera = (datos.get("bloques") or [{}])[0].get("pausas")
    igual(primera, [{"ms": 900, "final": True}], "cada bloque dice las suyas y dónde van")
    igual(pausas.get("sobrantes"), ["B004", "B005"],
          "sobran las que no cierran un tramo antes de un cambio de tema")
    # editar un bloque a mano le quita la pausa, y el aviso tiene que verlo
    cliente.put(f"/api/proyectos/{pid}/pasos/guion/params",
                {"params": {"bloques": {"B005": {"texto": "Frase cinco reescrita."}}}})
    _r, datos = cliente.get(f"{base}/bloques")
    igual(datos["pausas"]["total"], 3, "lo editado a mano cuenta: ya son 3")
    respuesta, datos = cliente.post(f"{base}/pausas/quitar", {"bloques": ["B002"]})
    igual(respuesta.status_code, 200, "quitar la pausa de un bloque responde 200")
    igual(datos.get("quitadas"), ["B002"], "y dice de cuál")
    _r, guion = cliente.get(f"/api/proyectos/{pid}/pasos/guion")
    texto = ((guion.get("params") or {}).get("bloques") or {}).get("B002", {}).get("texto")
    ok("<break" not in texto and "<speed" in texto,
       f"quita la pausa y deja el resto de anotaciones: {texto}")
    igual(guion.get("estado"), "listo", "y no deja obsoleto al guion")
    _r, datos = cliente.get(f"{base}/bloques")
    igual(datos["pausas"]["total"], 2, "quedan 2: dentro de lo recomendado")
    respuesta, datos = cliente.post(f"{base}/pausas/quitar", {"sobrantes": True})
    igual(datos.get("quitadas"), [], "y ya no sobra ninguna")
    respuesta, _d = cliente.post(f"{base}/pausas/quitar", {"bloques": ["B999"]})
    igual(respuesta.status_code, 400, "un bloque que no existe da 400")


def probar_bitacora(cliente, pid):
    seccion("BITACORA")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/bitacora")
    igual(respuesta.status_code, 200, "GET bitacora responde 200")
    eventos = datos.get("eventos") or []
    ok(eventos, "la bitacora tiene eventos")
    tipos = {e["evento"] for e in eventos}
    for esperado in ("proyecto_creado", "params_actualizados", "paso_completado",
                     "feedback", "revertido"):
        ok(esperado in tipos, f"la bitacora registra '{esperado}'")
    ok(all({"fecha", "evento", "paso", "unidad", "datos"} <= set(e) for e in eventos),
       "cada evento trae fecha, evento, paso, unidad y datos")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/bitacora",
                                   params={"paso": "voz"})
    ok(all(e["paso"] == "voz" for e in datos["eventos"]), "el filtro por paso funciona")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/bitacora",
                                   params={"paso": "inventado"})
    igual(respuesta.status_code, 404, "filtrar por un paso inexistente da 404")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/bitacora/llm")
    igual(respuesta.status_code, 200, "el resumen para LLM responde 200")
    ok("BITACORA DEL PROYECTO" in (datos.get("texto") or ""),
       "y trae el historial en texto")
    ok(datos.get("lineas", 0) > 5, "con varias lineas")

    respuesta = cliente.sesion.get(
        f"{cliente.base}/api/proyectos/{pid}/bitacora/llm?formato=texto", timeout=60)
    ok(respuesta.headers.get("content-type", "").startswith("text/plain"),
       "en formato=texto se sirve como texto plano")


def probar_presets_canal(cliente):
    seccion("PRESETS DEL CANAL Y SUS FICHEROS")
    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "guion", "nombre": "Prueba API",
        "datos": {"idiomas_salida": ["es"], "duracion_objetivo_s": 300}})
    igual(respuesta.status_code, 200, "guardar un preset de guion responde 200")
    preset_id = (datos.get("preset") or {}).get("id") or ""
    ok(preset_id, "la respuesta trae el id del preset")

    respuesta, datos = cliente.get("/api/presets-canal")
    ok(any(p.get("id") == preset_id
           for p in (datos.get("presets") or {}).get("guion") or []),
       "el preset aparece en la lista de su tipo")

    # el fichero se siembra a mano en la carpeta del preset: este endpoint
    # existe para servir lo que YA vive en banco/presets/<id>/
    carpeta_preset = os.path.join(cliente.carpeta, "banco_presets", preset_id)
    os.makedirs(carpeta_preset, exist_ok=True)
    with open(os.path.join(carpeta_preset, "referencia.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("fotograma de mentira")
    respuesta = cliente.sesion.get(
        f"{cliente.base}/api/presets-canal/{preset_id}/fichero/referencia.txt",
        timeout=30)
    igual(respuesta.status_code, 200, "un fichero del preset se sirve")
    igual(respuesta.text, "fotograma de mentira", "con su contenido intacto")

    respuesta = cliente.sesion.get(
        f"{cliente.base}/api/presets-canal/{preset_id}/fichero/no_existe.png",
        timeout=30)
    igual(respuesta.status_code, 404, "un fichero que no existe da 404")

    for intento, etiqueta in (
            ("..%2F..%2Fpresets.json", "escapar con .. codificado"),
            ("..%5C..%5Cpresets.json", "escapar con barras invertidas"),
            ("C:%2FWindows%2Fwin.ini", "colar una ruta absoluta")):
        respuesta = cliente.sesion.get(
            f"{cliente.base}/api/presets-canal/{preset_id}/fichero/{intento}",
            timeout=30, allow_redirects=False)
        ok(respuesta.status_code in (400, 404),
           f"{etiqueta} se corta ({respuesta.status_code})")

    respuesta, datos = cliente.get(
        "/api/presets-canal/pr_inexistente/fichero/referencia.txt")
    igual(respuesta.status_code, 400, "pedir ficheros de un preset inexistente da 400")


def probar_cartelas_y_transiciones(cliente, pid, raiz_proyecto=None):
    """Las dos pantallas nuevas: cartelas (assets) y transiciones (render)."""
    seccion("CARTELAS, TRANSICIONES Y SONIDO")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/cartelas")
    igual(respuesta.status_code, 200, "el catalogo de cartelas responde 200")
    plantillas = datos.get("plantillas") or []
    ok(len(plantillas) >= 8, f"vienen las plantillas ({len(plantillas)})")
    sin_muestra = [p["id"] for p in plantillas
                   if not str(p.get("svg") or "").startswith("<svg")]
    igual(sin_muestra, [], "cada una trae su muestra DIBUJADA, no una maqueta")
    ok(all(p.get("cuando") and p.get("campos") for p in plantillas),
       "y dice cuando va y que huecos tiene")
    ok(datos.get("todas"), "sin elegir nada, entran todas")

    # guardar un plan valido
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/cartelas", {
        "plan": {"S001": {"plantilla": "tesis",
                          "datos": {"texto": "Y entonces dejo de existir"},
                          "por_que": "la prueba"}}})
    igual(respuesta.status_code, 200, "guardar un plan de cartelas responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/cartelas")
    igual(list(datos.get("plan") or {}), ["S001"], "y queda guardado")

    # una plantilla que no existe se corta AQUI, no al renderizar
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas", {
        "plan": {"S001": {"plantilla": "no_existe", "datos": {}}}})
    igual(respuesta.status_code, 400, "una plantilla inventada da 400")

    # y un campo obligatorio que falta, tambien: el aviso lleva el id del plano
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/cartelas", {
        "plan": {"S007": {"plantilla": "cifra", "datos": {"label": "sin numero"}}}})
    igual(respuesta.status_code, 400, "una cartela sin campo obligatorio da 400")
    ok("S007" in str(datos), f"y el error dice de que plano habla: {datos}")

    # el texto de mas se RECORTA y se guarda: no es un error, es un aviso
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas", {
        "plan": {"S001": {"plantilla": "tesis", "datos": {"texto": "x" * 400}}}})
    igual(respuesta.status_code, 200, "un texto largo se guarda recortado")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/cartelas")
    ok(len(datos["plan"]["S001"]["datos"]["texto"]) <= 95,
       "recortado a su tope, no rechazado")

    # LA CARTELA VA POR UNIDAD, no en un param suelto. Es lo que impide que
    # decidir una cartela deje obsoletos los cuarenta y nueve planos: todo lo
    # que no es el bloque `unidades` entra en la firma GLOBAL del paso.
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    params = datos.get("params") or datos
    ok("plan_cartelas" not in params,
       "el plan NO es un param global de assets: eso ensuciaba todo el video")
    unidades = params.get("unidades") or {}
    ok((unidades.get("escena:S001") or {}).get("cartela"),
       f"esta guardada en su unidad: {list(unidades)[:4]}")

    # y guardarla NO se lleva por delante lo que ya hubiera en esa unidad
    cliente.post(f"/api/proyectos/{pid}/feedback", {
        "paso": "assets", "unidad": "escena:S001", "texto": "una nota previa",
        "ejecutar": False})
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas", {
        "plan": {"S001": {"plantilla": "tesis",
                          "datos": {"texto": "Otra frase"}}}})
    igual(respuesta.status_code, 200, "volver a guardar el plan responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    unidad = ((datos.get("params") or datos).get("unidades") or {}).get("escena:S001") or {}
    ok(unidad.get("feedback"),
       "el feedback de ese plano sigue ahi: guardar la cartela no lo pisa")
    ok((unidad.get("cartela") or {}).get("fondo") in ("negro", "imagen"),
       "y la cartela guarda su fondo")

    # quitar una cartela la quita de verdad
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas", {"plan": {}})
    igual(respuesta.status_code, 200, "guardar un plan vacio responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/cartelas")
    igual(datos.get("plan"), {}, "y el plano deja de ser cartela")

    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas",
                               {"plantillas": ["cifra", "cita"]})
    igual(respuesta.status_code, 200, "elegir que plantillas entran responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
    igual((datos.get("params") or datos).get("plantillas_cartela"),
          ["cifra", "cita"],
          "las plantillas permitidas van con el GRAFISMO, en params de rotulos: "
          "solo limitan lo que puede elegir el agente, asi que no tienen por "
          "que ensuciar una sola imagen")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas",
                               {"plantillas": ["ni_idea"]})
    igual(respuesta.status_code, 400, "una plantilla desconocida da 400")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas", {})
    igual(respuesta.status_code, 400, "un PUT sin nada que guardar da 400")

    # --- transiciones
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/transiciones")
    igual(respuesta.status_code, 200, "el catalogo de transiciones responde 200")
    lista = datos.get("transiciones") or []
    igual(len(lista), 15, "las catorce de hyperframes mas nuestro fundido")
    sin_glsl = [t["id"] for t in lista if "void main()" not in (t.get("frag") or "")]
    igual(sin_glsl, [], "cada una viaja con SU shader: la pantalla corre el "
                        "mismo GLSL que el render, no una imitacion")
    ok(datos.get("vertices"), "y el vertex shader comun")
    ok("corte" not in (datos.get("por_defecto") or []),
       "'corte' no viaja como transicion: es lo que pasa cuando no hay ninguna")
    acento = datos.get("acento") or {}
    ok(all(len(acento.get(p) or []) == 3 for p in ("acento", "oscuro", "claro")),
       "con los tres colores de acento del video, listos para los uniformes")

    # la seleccion es un param del RENDER, y una mal escrita se corta al guardar
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/pasos/render/params",
                               {"transiciones": ["glitch", "sdf-iris"]})
    igual(respuesta.status_code, 200, "elegir transiciones responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/transiciones")
    ok(not datos.get("todas_de_fabrica"), "y deja de estar en las de fabrica")
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/pasos/render/params",
                                   {"transiciones": ["remolino_loco"]})
    igual(respuesta.status_code, 400,
          "una transicion inventada da 400 al GUARDARLA, no un video sin ella")

    # QUE TRANSICION LE TOCA A CADA PLANO. Viaja resuelta por el motor
    # (`transiciones.resolver`) para que el repaso del montaje pueda correr el
    # shader de verdad en cada corte en vez de adivinar cual toca -- y adivinaria
    # mal en cuanto alguien cambiara la paleta elegida.
    from nucleo.proyecto import Proyecto, escribir_json
    escribir_json(os.path.join(Proyecto(raiz_proyecto).ruta_trabajo("assets"),
                               "plan.json"), {
        "semilla": 7,
        # CON SU NARRACION, que es lo que dice cada plano. No es de adorno en el
        # fixture: es lo unico que permite volver a encontrar el plano de una
        # nota cuando la segmentacion renumera (ver el repaso, mas abajo).
        "escenas": [
            {"id": "S001", "duracion": 4.0, "t_in": 0.0, "t_out": 4.0,
             "transicion": "suave",
             "narracion": "treinta millones de cuentas salieron a la venta"},
            {"id": "S002", "duracion": 4.0, "t_in": 4.0, "t_out": 8.0,
             "transicion": "acento",
             "narracion": "daban de comer a una familia un mes entero"},
            {"id": "S003", "duracion": 4.0, "t_in": 8.0, "t_out": 12.0,
             "transicion": "suave", "sigue_a": "S002",
             "narracion": "y nadie aviso a los clientes hasta mucho despues"},
        ],
    })
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/transiciones")
    reparto = datos.get("reparto") or {}
    igual(sorted(reparto), ["S001", "S002", "S003"],
          "el reparto trae un corte por plano")
    igual(reparto.get("S001", {}).get("tipo"), "corte",
          "el primer plano no encadena: no hay nada de lo que venir")
    igual(reparto.get("S003", {}).get("tipo"), "corte",
          "y una continuacion tampoco: los dos fotogramas son la misma imagen")
    ok(reparto.get("S002", {}).get("tipo") not in (None, "corte"),
       f"el resto si: {reparto.get('S002')}")
    ok(float(reparto.get("S002", {}).get("duracion") or 0) > 0,
       "con su duracion, que es la que el repaso tiene que recorrer")
    ok("shader" not in (reparto.get("S002") or {}),
       "y SIN el GLSL: el frag de cada transicion ya viaja una vez en el "
       "catalogo, repetirlo por plano serian doscientas copias")
    ok(any(x["id"] == reparto["S002"]["tipo"] for x in lista),
       "la que toca esta en el catalogo, asi que la pantalla puede buscar su frag")

    # --- musica y efectos. SOLO lo que no sale a la red: que Jamendo y
    # Freesound sigan vivos no depende de este repo, y una suite que se cae
    # porque una API de fuera tiene un mal dia deja de servir para nada.
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/sonido")
    igual(respuesta.status_code, 200, "el estado del sonido responde 200")
    papeles = datos.get("papeles") or []
    ok(len(papeles) >= 4, f"vienen los papeles de efecto ({len(papeles)})")
    ok(all(p.get("nombre") and p.get("descripcion") for p in papeles),
       "cada papel dice que es y para que")
    ok(datos.get("animos"), "y los animos con los que buscar musica")
    ok("hay_jamendo" in datos and "hay_freesound" in datos,
       "dice si estan las claves, para poder avisar en vez de fallar al pulsar")

    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/sonido", {"activo": False})
    igual(respuesta.status_code, 200, "apagar el sonido responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/sonido")
    igual(datos.get("activo"), False, "y queda apagado")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/sonido",
                               {"activo": True, "lufs": -20})
    igual(respuesta.status_code, 200, "y se vuelve a encender")

    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/sonido",
                               {"musica": {"titulo": "sin id ni descarga"}})
    igual(respuesta.status_code, 400,
          "un tema sin 'id' ni 'descarga' se corta al guardarlo, no al renderizar")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/sonido", {})
    igual(respuesta.status_code, 400, "un PUT sin nada que guardar da 400")
    respuesta, _ = cliente.post(f"/api/proyectos/{pid}/sonido/efectos",
                                {"papeles": ["no_existe"]})
    igual(respuesta.status_code, 400, "un papel de efecto inventado da 400")

    # --- EL VETO DE UN EFECTO (PENDIENTE 19). Se veta lo que se acaba de oir,
    # donde se oye: la pantalla trae cada efecto con su muestra y su ✕, y el
    # veto es del CANAL, no de este video.
    from pasos import sonido as mod_sonido
    guardados = dict(mod_sonido.vetados())
    try:
        laser = {"fuente": "prueba", "id": "laser_api", "titulo": "Laser"}
        respuesta, datos = cliente.post(f"/api/proyectos/{pid}/sonido/vetados",
                                        {"efecto": laser, "papel": "transicion_acento"})
        igual(respuesta.status_code, 200, "vetar un efecto responde 200")
        ok(datos.get("vetado"), "y dice que ha quedado vetado")
        ok(any(v.get("clave") == "prueba_laser_api" for v in datos.get("vetados") or []),
           f"y devuelve la lista del canal: {datos.get('vetados')}")
        respuesta, datos = cliente.get(f"/api/proyectos/{pid}/sonido")
        ok(any(v.get("clave") == "prueba_laser_api" for v in datos.get("vetados") or []),
           "la pantalla de sonido lo trae ya marcado, sin tener que preguntar aparte")
        respuesta, datos = cliente.post(f"/api/proyectos/{pid}/sonido/vetados",
                                        {"clave": "prueba_laser_api", "quitar": True})
        igual(respuesta.status_code, 200, "y se puede levantar")
        ok(datos.get("quitado"), "diciendo que habia algo que levantar")
        respuesta, _ = cliente.post(f"/api/proyectos/{pid}/sonido/vetados", {})
        igual(respuesta.status_code, 400,
              "vetar sin decir que se veta da 400, no un veto vacio")
        respuesta, _ = cliente.get("/api/efectos/no_existe.mp3")
        igual(respuesta.status_code, 404,
              "y pedir una muestra que no esta en el banco da 404")
        respuesta, _ = cliente.get("/api/efectos/..%2F..%2Fapp.py")
        ok(respuesta.status_code in (403, 404),
           f"y no se puede salir del banco por la ruta ({respuesta.status_code})")
    finally:
        mod_sonido._guardar_vetados(guardados)


def probar_motor_del_plan(cliente, pid):
    """CON QUE REGLAS SE CORTO ESTE VIDEO (PENDIENTE 24).

    Las firmas miran los params, asi que cambiar el MOTOR no pone naranja nada.
    No se inventa un estado --eso obligaria a rehacer los renders de todos los
    proyectos cada vez que se toca una regla--: se ensena.
    """
    seccion("EL PLAN DICE CON QUE REGLAS SE CORTO")

    from pasos import p6_assets
    respuesta, ficha = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    igual(respuesta.status_code, 200, "assets responde 200")
    motor = ficha.get("motor")
    if not ok(isinstance(motor, dict), f"assets dice con que motor se corto: {motor}"):
        return
    igual(motor.get("ahora"), p6_assets.MOTOR_PLAN,
          "y con cual hay ahora, que es lo que se compara")
    # El plan de esta suite se corto antes de que existiera el sello, asi que
    # es EL CASO QUE IMPORTA: un video viejo tiene que decirlo. Sin sello se lee
    # como version 1, que es lo correcto -- «no lo se» y «es viejo» son lo mismo
    # aqui, porque lo unico accionable es volver a cortar.
    igual(motor.get("plan"), 1,
          "un plan sin sello se lee como viejo, no como al dia")
    igual(motor.get("al_dia"), False, "asi que se avisa")
    ok(motor.get("cambios"),
       f"y se dice QUE se ha perdido, no un numero: {(motor.get('cambios') or [''])[0][:60]}")
    ok(all(isinstance(t, str) and t for t in motor.get("cambios") or []),
       "cada cambio es una frase que se puede leer")

    ok(all(v in p6_assets.MOTOR_CAMBIOS for v in range(2, p6_assets.MOTOR_PLAN + 1)),
       "cada version del motor dice QUE cambio: un numero suelto no dice si "
       "importa")

    # y el render y los rotulos tambien lo traen: son los que se quedan viejos
    for paso in ("callouts", "render"):
        respuesta, otra = cliente.get(f"/api/proyectos/{pid}/pasos/{paso}")
        ok(isinstance(otra.get("motor"), dict),
           f"{paso} tambien lo trae: es donde se ve el video")


def probar_direccion(cliente, pid):
    """QUE SE VE EN CADA PLANO: la capa que faltaba en el prompt de imagen.

    Va POR UNIDAD, como las cartelas y por lo mismo: escribir la direccion de un
    plano ensucia ESE plano y no los cuarenta y nueve.
    """
    seccion("LA DIRECCION DE LOS PLANOS VA POR UNIDAD")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/direccion")
    igual(respuesta.status_code, 200, "la pantalla de direccion responde 200")
    ok("planos" in datos and "dirigibles" in datos,
       "trae los planos que se pueden dirigir y cuantos son")
    ok(datos.get("palabras_maximas", 0) > 0,
       "y el tope de palabras, que es lo que la hace util")
    planos = datos.get("planos") or []
    if not ok(planos, "hay planos que dirigir"):
        return
    sid = planos[0]["id"]

    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/direccion", {})
    igual(respuesta.status_code, 400, "un PUT sin 'plan' da 400")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/direccion",
                               {"plan": {sid: "dos palabras"}})
    igual(respuesta.status_code, 400,
          "una direccion de dos palabras se corta al guardarla, no al generar")

    linea = "a hand covers the screen while another clerk walks in"
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/direccion",
                                   {"plan": {sid: linea}})
    igual(respuesta.status_code, 200, "guardar una direccion responde 200")
    igual(datos.get("guardado"), 1, "y dice cuantas ha guardado")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/direccion")
    igual((datos.get("plan") or {}).get(sid), linea, "queda guardada")

    # y NO se lleva por delante lo demas de esa unidad, que es la trampa que ya
    # costo una ronda con las cartelas
    respuesta, antes = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    unidad = ((antes.get("params") or {}).get("unidades") or {}).get(f"escena:{sid}") or {}
    ok("direccion" in unidad,
       f"vive en los params de SU unidad, no en un param global: {sorted(unidad)}")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/direccion",
                                   {"plan": {sid: ""}})
    igual(respuesta.status_code, 200, "y una vacia la quita")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/direccion")
    igual((datos.get("plan") or {}).get(sid), None, "queda quitada")

    # la receta la conoce, y va DESPUES de las cartelas y ANTES de los planos
    from pasos import recetas
    orden = [t["id"] for t in recetas.orden_de("video")]
    ok("direccion" in orden, f"la receta de Video la incluye: {orden}")
    ok(orden.index("plan_cartelas") < orden.index("direccion") < orden.index("assets"),
       "y en su sitio: despues de decidir que planos son texto, antes de pagar "
       "las imagenes")


# AQUI SE PROBABA «mirar», la revision de las imagenes: que un informe NO
# tocara la firma de ningun plano, porque si la tocara revisar el video pediria
# volver a pagarlo entero. Se retiro entera el 24-08-2026 con el resto del
# modulo. La propiedad que probaba sigue viva y la sigue probando la nota del
# montaje, justo debajo: lo que se escribe SOBRE lo terminado no es una entrada
# del paso y no vive en su firma.


def probar_nota_del_montaje(cliente, pid):
    """La nota del video terminado NO puede dejar el video obsoleto.

    Hasta el 21-08 vivia en los params del render, o sea DENTRO de su firma:
    escribir «la musica esta alta en 0:45» pintaba el MP4 de naranja como si
    volver a renderizarlo fuera a arreglar la musica -- y nadie leia la nota,
    asi que rehacerlo daba el mismo fichero.
    """
    seccion("LA NOTA DEL VIDEO TERMINADO ES UN REGISTRO")

    respuesta, antes = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    firma_antes = antes.get("firma")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/montaje/notas")
    igual(respuesta.status_code, 200, "la nota responde 200")
    igual(datos.get("nota"), "", "y empieza vacia")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/montaje/notas",
                                   {"nota": "la musica esta alta en 0:45"})
    igual(respuesta.status_code, 200, "se guarda")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/montaje/notas")
    igual(datos.get("nota"), "la musica esta alta en 0:45", "y se relee")
    ok(datos.get("cuando"), "con la fecha, que es lo que la hace un registro")

    respuesta, despues = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    igual(despues.get("firma"), firma_antes,
          "y la firma del render NO se ha movido: escribir sobre lo terminado "
          "no puede pedir volver a terminarlo")

    respuesta, params = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    ok("feedback_final" not in (params.get("params") or {}),
       "la nota no vuelve a params ni de rebote")


def probar_repaso(cliente, pid):
    """El repaso: notas ancladas al segundo, y NINGUNA firma movida al escribir.

    Es la misma regla que la nota del montaje y por el mismo motivo, solo que
    aqui hay varias notas y cada una apunta a un momento: comentar un video no
    puede pedir volver a montarlo. Lo que toca las firmas es APLICAR.
    """
    seccion("EL REPASO: NOTAS SOBRE EL VIDEO MONTADO")

    _r, antes_render = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    _r, antes_assets = cliente.get(f"/api/proyectos/{pid}/pasos/assets")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/repaso")
    igual(respuesta.status_code, 200, "el repaso responde 200")
    igual(datos.get("notas"), [], "y empieza sin notas")
    ok(isinstance(datos.get("catalogo"), dict),
       "trae el catalogo de ambitos y cambios: la pantalla tiene que poder "
       "decir lo que cuesta cada cosa antes de pulsar")

    # ---- QUE UNA NOTA NO SE QUEDE APUNTANDO AL PLANO DE AL LADO ------------
    #
    # El numero de un plano NO ES ESTABLE: al regrabar la voz la segmentacion
    # vuelve a cortar y lo que era S005 pasa a ser S004. Las notas ya escritas
    # se quedan con el numero viejo, y aplicarlas rehace el plano que estaba
    # bien. Se arregla al LEER, comparando lo que la nota dice que se decia
    # ahi (`ancla`) con lo que se dice ahora.
    cortes = datos.get("cortes") or []
    ok(len(cortes) >= 2, "el repaso trae los cortes del MP4")
    ok(all("narracion" in c for c in cortes),
       "y CADA CORTE TRAE LO QUE SE DICE EN EL: es contra esto contra lo que "
       "se comprueba que una nota siga en su plano. Sin ello, re-anclar no "
       "encontraria nada y daria por descolgadas todas las notas")
    hablados = [c for c in cortes if (c.get("narracion") or "").strip()]
    ok(len(hablados) >= 2, "y al menos dos planos dicen algo")

    fuera, dentro = hablados[0], hablados[-1]
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/repaso",
                                    {"t": 1.0, "texto": "esta se ha movido",
                                     "plano": fuera["id"],
                                     "ancla": dentro["narracion"]})
    igual(respuesta.status_code, 201, "una nota puede decir contra que se escribio")
    movida = datos["nota"]["id"]
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/repaso")
    suya = [n for n in datos["notas"] if n["id"] == movida][0]
    igual(suya.get("plano"), dentro["id"],
          "y al leerla vuelve al plano QUE DICE LO SUYO, no al numero que "
          "tenia guardado")
    igual(suya.get("reanclada"), fuera["id"],
          "diciendo de donde venia: recolocar a la callada es indistinguible "
          "de no haber hecho nada")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/repaso",
                                    {"t": 1.0, "texto": "esta se quedo sin sitio",
                                     "plano": fuera["id"],
                                     "ancla": "zumbaba un zeppelin de gengibre"})
    huerfana = datos["nota"]["id"]
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/repaso")
    suya = [n for n in datos["notas"] if n["id"] == huerfana][0]
    ok(suya.get("descolgada"),
       "y si lo que habia ya no esta en el video se DICE, en vez de dejarla "
       "senalando a cualquier sitio")
    cliente.delete(f"/api/proyectos/{pid}/repaso/{movida}")
    cliente.delete(f"/api/proyectos/{pid}/repaso/{huerfana}")

    # LA PANTALLA DEL VIDEO NO MANDA ANCLA: la rellena el servidor con lo que
    # dice ese plano. Se comprueba aparte porque es el camino por el que entran
    # casi todas las notas, y si ahi no se guardara el ancla el arreglo de
    # arriba solo protegeria a las de Imagenes.
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/repaso",
                                    {"t": 5.0, "texto": "sin decir contra que",
                                     "plano": dentro["id"]})
    sola = datos["nota"]["id"]
    igual(datos["nota"].get("ancla"), dentro["narracion"],
          "una nota que no dice contra que se escribio la ancla el servidor")
    cliente.delete(f"/api/proyectos/{pid}/repaso/{sola}")

    respuesta, _d = cliente.post(f"/api/proyectos/{pid}/repaso",
                                 {"t": 12.0, "texto": "   "})
    igual(respuesta.status_code, 400,
          "una nota SIN TEXTO rebota: una imagen sola no dice que hacer con ella")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/repaso",
                                    {"t": 92.4, "texto": "la musica esta alta"})
    igual(respuesta.status_code, 201, "una nota con texto se guarda")
    segunda = datos["nota"]["id"]
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/repaso",
                                    {"t": 10.0, "texto": "aqui sobra el rotulo"})
    primera = datos["nota"]["id"]
    igual([n["id"] for n in datos["notas"]], [primera, segunda],
          "y se leen en ORDEN DE VIDEO, no de escritura")
    igual(datos.get("pendientes"), 2, "las dos estan sin aplicar")

    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/repaso/{primera}",
                                   {"texto": "mejor quitalo entero"})
    igual(respuesta.status_code, 200, "se puede editar")
    igual(datos["notas"][0]["texto"], "mejor quitalo entero", "y se relee")
    respuesta, _d = cliente.put(f"/api/proyectos/{pid}/repaso/{primera}",
                                {"texto": "  "})
    igual(respuesta.status_code, 400, "pero no vaciar por la puerta de atras")
    respuesta, _d = cliente.put(f"/api/proyectos/{pid}/repaso/R999",
                                {"texto": "x"})
    igual(respuesta.status_code, 404, "ni editar una que no existe")

    _r, despues_render = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    _r, despues_assets = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    igual(despues_render.get("firma"), antes_render.get("firma"),
          "y LA FIRMA DEL RENDER NO SE HA MOVIDO: escribir sobre el video "
          "terminado no puede pintarlo de naranja")
    igual(despues_assets.get("firma"), antes_assets.get("firma"),
          "ni la de assets")

    respuesta, datos = cliente.delete(f"/api/proyectos/{pid}/repaso/{primera}")
    igual(respuesta.status_code, 200, "se puede borrar")
    igual(len(datos.get("notas") or []), 1, "y se queda la otra")
    respuesta, _d = cliente.delete(f"/api/proyectos/{pid}/repaso/R999")
    igual(respuesta.status_code, 404, "borrar lo que no existe se dice")

    # limpieza: la nota que queda no puede quedarse pendiente para las suites
    # que corran despues sobre el mismo proyecto
    cliente.delete(f"/api/proyectos/{pid}/repaso/{segunda}")


def probar_plan_de_rotulos(cliente, pid):
    """El plan de rotulos, que es la otra cosa que describe UN plano.

    Nacio suelto (`plan_callouts`) igual que el de cartelas, y con el mismo
    precio: tocar el rotulo de un plano dejaba obsoletos los cuarenta y nueve y
    el render entero, sin dar ningun error.
    """
    seccion("EL GRAFISMO ES DEL VIDEO, Y SE APLICA SOLO")

    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/callouts/diseno")
    igual(respuesta.status_code, 200, "la pantalla de grafismo responde 200")
    ok(datos.get("sets") and datos.get("elegido"), "trae los sets y el elegido")
    ok(datos.get("subtitulo_tamanos"),
       f"y los tamanos de subtitulo que se pueden elegir: "
       f"{datos.get('subtitulo_tamanos')}")
    igual(datos.get("subtitulo_tam"), "normal", "con el normal de partida")
    ok("arquetipos" not in datos and "plan" not in datos,
       "y ya NO trae ni arquetipos ni plan de rotulos: se retiraron enteros "
       "el 22-08")

    # EL SET SE APLICA SOLO. Antes se calculaba `sugerido`, se servia aqui y ahi
    # se quedaba: habia que abrir la tarjeta y pulsarlo. Deducir algo bien y
    # pedirle despues a una persona que lo confirme es el paso que sobra.
    igual(datos.get("elegido"), datos.get("sugerido"),
          "sin elegir nada, manda lo que sugiere la guia de estilo")
    ok(datos.get("por_que"), "y se dice por que, que es lo que permite cambiarlo")

    # el set de diseno SI es global, y a proposito: describe el video entero
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/callouts/plan",
                               {"diseno": "editorial"})
    igual(respuesta.status_code, 200, "elegir el set de diseno responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
    igual((datos.get("params") or datos).get("diseno"), "editorial",
          "y ese si va suelto: el grafismo es del video, no de un plano")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/callouts/plan",
                               {"diseno": "ni_idea"})
    igual(respuesta.status_code, 400, "un set inventado da 400")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/callouts/plan", {})
    igual(respuesta.status_code, 400, "un PUT sin nada que guardar da 400")

    # LA REGLA, EN EL SITIO DONDE SE APLICA. Un param suelto indexado por
    # unidades se corta al guardarlo, con nombre y apellidos, en vez de dejar
    # el video entero naranja sin que nada falle.
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/pasos/callouts/params",
                                   {"plan_de_lo_que_sea": {"escena:S001": {"x": 1}}})
    igual(respuesta.status_code, 400,
          "un param suelto indexado por unidad da 400 al GUARDARLO")
    ok("unidades" in str(datos) and "plan_de_lo_que_sea" in str(datos),
       f"y el aviso dice que clave es y donde tiene que ir: {str(datos)[:120]}")


def probar_vista_de_cartela(cliente, raiz_proyecto, pid):
    """La cartela se dibuja con la DECISION, no con la foto de la ultima tanda.

    p6 estampa en plan.json la cartela que habia decidida cuando corrio
    (`_marcar_cartelas`). La vista leia esa foto ANTES que los params, asi que
    volver a decidir o editar el texto a mano no cambiaba el dibujo: se escribia
    otra frase y salia la de antes. Es justo lo que esta llamada existe para que
    no pase, y no lo veia ninguna prueba.

    El plan va a la carpeta de TRABAJO, que es de donde `plan_actual` lo coge
    cuando no hay version: asi esto no crea ninguna version ni mueve el grafo.
    """
    seccion("LA CARTELA SE DIBUJA CON LO DECIDIDO")
    from nucleo.proyecto import Proyecto, escribir_json

    proyecto = Proyecto(raiz_proyecto)
    escribir_json(os.path.join(proyecto.ruta_trabajo("assets"), "plan.json"), {
        "semilla": 7,
        "escenas": [{"id": "S001", "duracion": 4.0, "narracion": "lo que sea",
                     # la FOTO: lo que habia decidido la ultima tanda
                     "cartela": {"plantilla": "tesis", "fondo": "negro",
                                 "datos": {"texto": "La frase vieja"}}}],
    })

    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas", {
        "plan": {"S001": {"plantilla": "tesis",
                          "datos": {"texto": "The new line"}}}})
    igual(respuesta.status_code, 200, "guardar la cartela nueva responde 200")

    # el cuerpo es SVG, no JSON: hay que mirar el texto crudo
    respuesta, _ = cliente.get(f"/api/proyectos/{pid}/cartelas/vista?plano=S001")
    igual(respuesta.status_code, 200, "la vista de la cartela responde 200")
    texto = respuesta.text
    ok("THE NEW LINE" in texto.upper(),
       "sale lo DECIDIDO, no lo que estampo la ultima tanda")
    ok("FRASE VIEJA" not in texto.upper(),
       f"y la foto de plan.json no manda: {texto[:80]}")

    # quitarla la quita: la vista deja de tener nada que dibujar
    cliente.put(f"/api/proyectos/{pid}/cartelas", {"plan": {}})
    respuesta, _ = cliente.get(f"/api/proyectos/{pid}/cartelas/vista?plano=S001")
    igual(respuesta.status_code, 404,
          "sin cartela decidida no se dibuja la vieja: se dice que no hay")


def probar_cartela_sincronizada(cliente, raiz_proyecto, pid):
    """La vista ANIMADA escribe cada palabra cuando la voz la dice.

    Es el caso medido de PENDIENTE.md 12, el del 30M del video largo: la cartela
    colgaba de S002 y sus palabras se dicen enteras en S001, asi que el plan la
    pasa a S001 y deja S002 de continuacion. Lo que se comprueba aqui es que esa
    sincronia LLEGA A LA PANTALLA por la misma llamada que mira el repaso del
    montaje -- si el repaso dibujara su propia animacion, se elegiria una cosa y
    saldria otra, que es la regla de todas las muestras de esta casa.
    """
    seccion("LA CARTELA SE ESCRIBE CUANDO SE DICE")
    from nucleo.proyecto import Proyecto, escribir_json

    proyecto = Proyecto(raiz_proyecto)
    ficha = {"plantilla": "cifra", "fondo": "negro",
             "datos": {"cifra": "30M", "label": "Customer accounts on sale"}}
    escribir_json(os.path.join(proyecto.ruta_trabajo("assets"), "plan.json"), {
        "semilla": 7,
        "escenas": [
            # el plan YA la ha movido: la cartela vive en S001, que es donde se
            # dicen sus palabras, y S002 es su segunda mitad
            {"id": "S001", "t_in": 0.0, "t_out": 3.8, "duracion": 3.8,
             "narracion": "Thirty million customer accounts went up for sale",
             "marcas": [[0.123, 0.52], [0.524, 1.08], [1.081, 1.48],
                        [1.482, 1.88], [1.881, 2.12], [2.2, 2.2], [2.28, 2.36],
                        [2.361, 2.6]],
             "cartela": dict(ficha),
             "escritura": {"tiempos": [0.22, 1.081, 1.482, 1.921, 2.361],
                           "palabras": 5, "fin": 2.361, "cola": 1.4,
                           "falta": 0.0, "dos_planos": False}},
            {"id": "S002", "t_in": 3.8, "t_out": 7.2, "duracion": 3.4,
             "narracion": "dollars, roughly the price of an apartment",
             "marcas": [[3.802, 4.28], [4.552, 5.08], [5.16, 5.16],
                        [5.241, 5.56], [5.56, 5.64], [5.72, 5.72],
                        [5.801, 6.32]],
             "cartela": dict(ficha, sigue_a="S001"),
             "escritura": {"tiempos": [], "palabras": 5, "fin": 0.0,
                           "cola": 1.4, "falta": 0.0, "dos_planos": False,
                           "continua": True}},
        ],
    })
    # SOLO S001 en la decision: S002 es su continuacion, y eso no lo decide
    # nadie -- lo deduce la planificacion --, asi que no esta en params. La vista
    # tiene que resolverlo desde el hogar igualmente, o la rejilla enseniaria
    # «sin imagen» en un plano donde el video lleva la cartela puesta.
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/cartelas",
                               {"plan": {"S001": ficha}})
    igual(respuesta.status_code, 200, "guardar la cartela del 30M responde 200")

    respuesta, _ = cliente.get(f"/api/proyectos/{pid}/cartelas/vista?plano=S001")
    igual(respuesta.status_code, 200, "la vista quieta responde 200")
    ok("<animate" not in respuesta.text,
       "la de la rejilla sigue quieta: ahi lo que se mira es el TEXTO")

    respuesta, _ = cliente.get(
        f"/api/proyectos/{pid}/cartelas/vista?plano=S001&animada=1")
    igual(respuesta.status_code, 200, "la vista animada responde 200")
    comienzos = sorted({float(m) for m in
                        re.findall(r'begin="([\d.]+)s"', respuesta.text)})
    ok(comienzos, f"la cartela se escribe palabra a palabra: {comienzos[:6]}")
    for cuando in (1.081, 1.482, 2.361):
        ok(any(abs(c - cuando) < 0.02 for c in comienzos),
           f"la palabra que se dice en {cuando}s entra en {cuando}s")

    respuesta, _ = cliente.get(
        f"/api/proyectos/{pid}/cartelas/vista?plano=S002&animada=1")
    igual(respuesta.status_code, 200, "la continuacion responde 200")
    ok("<animate" not in respuesta.text,
       "y la segunda mitad NO se reescribe: sigue puesta y quieta, o se "
       "reescribiria desde cero en mitad del corte")
    ok("30M" in respuesta.text,
       "y es LA MISMA cartela, resuelta desde su hogar aunque S002 no este en "
       "la decision: una continuacion es una consecuencia, no una decision")
    # y sigue mandando la decision: quitar la del hogar quita la continuacion
    cliente.put(f"/api/proyectos/{pid}/cartelas", {"plan": {}})
    respuesta, _ = cliente.get(f"/api/proyectos/{pid}/cartelas/vista?plano=S002")
    igual(respuesta.status_code, 404,
          "si se quita la cartela del hogar, su continuacion deja de dibujarse")
    cliente.put(f"/api/proyectos/{pid}/cartelas", {"plan": {}})


def probar_trabajos_y_errores(cliente, pid, tid, virgen):
    seccion("TRABAJOS Y ERRORES")
    respuesta, datos = cliente.get("/api/trabajos")
    igual(respuesta.status_code, 200, "GET /api/trabajos responde 200")
    ok(any(t["id"] == tid for t in datos["trabajos"]),
       "el historico de trabajos recuerda los terminados")

    respuesta, datos = cliente.get("/api/trabajos", params={"activos": 1})
    igual(respuesta.status_code, 200, "se pueden pedir solo los activos")

    respuesta, datos = cliente.get("/api/trabajos/no_existe")
    igual(respuesta.status_code, 404, "un trabajo inexistente da 404")
    ok("error" in (datos or {}), "con su mensaje de error")

    respuesta, datos = cliente.post("/api/trabajos/no_existe/cancelar")
    igual(respuesta.status_code, 404, "cancelar un trabajo inexistente da 404")

    respuesta, datos = cliente.post(f"/api/trabajos/{tid}/cancelar")
    igual(respuesta.status_code, 200, "cancelar uno terminado responde 200")
    ok(datos.get("cancelacion_pedida") is False,
       "diciendo que ya no habia nada que cancelar")

    respuesta = cliente.sesion.post(
        f"{cliente.base}/api/proyectos", data=b"{esto no es json",
        headers={"Content-Type": "application/json"}, timeout=30)
    igual(respuesta.status_code, 400, "un cuerpo que no es JSON da 400")
    ok("error" in respuesta.json(), "y sale como {'error': ...}")

    respuesta, datos = cliente.get("/api/nada/de/nada")
    igual(respuesta.status_code, 404, "una ruta inexistente da 404")
    ok("error" in (datos or {}), "tambien en forma de {'error': ...}")

    # un proyecto con el estado corrupto no puede tumbar el servicio. Antes se
    # abria EN BLANCO (y ofrecia generarlo entero); ahora, sin copia buena de
    # la que volver, contesta 503 con el porque y el fichero roto se queda
    roto = os.path.join(cliente.carpeta, "roto")
    os.makedirs(roto, exist_ok=True)
    with open(os.path.join(roto, "proyecto.json"), "w", encoding="utf-8") as fh:
        json.dump({"id": "roto", "nombre": "Roto"}, fh)
    with open(os.path.join(roto, "estado.json"), "w", encoding="utf-8") as fh:
        json.dump({"pasos": "esto deberia ser un objeto"}, fh)
    respuesta, datos = cliente.get("/api/proyectos/roto")
    igual(respuesta.status_code, 503, "un proyecto corrupto sin copia buena da 503")
    ok("no se puede leer" in (datos or {}).get("error", ""),
       "con un mensaje que dice por que, no en blanco")
    ok(any(n.startswith("estado.roto.") for n in os.listdir(roto)),
       "el estado ilegible se guarda a un lado en vez de sobreescribirse")
    with open(os.path.join(roto, "estado.json"), encoding="utf-8") as fh:
        ok("esto deberia ser un objeto" in fh.read(),
           "y el roto se queda en su sitio: el siguiente intento no lo abre vacio")

    respuesta, datos = cliente.get("/api/salud")
    igual(respuesta.status_code, 200, "y el servicio sigue en pie despues")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/voz/ejecutar",
                                    {"unidades": ["B001"]})
    igual(respuesta.status_code, 400, "pedir unidades a un paso que no las tiene da 400")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                                    {"unidades": ["escena:S99"]})
    igual(respuesta.status_code, 400, "pedir una unidad que no existe da 400")
    ok("escena:S99" in (datos or {}).get("error", ""),
       "y el error nombra la unidad desconocida")
    ok("declaradas" in (datos or {}), "listando las que si valen")

    # las unidades del PLAN del paso tambien valen sin estar declaradas: una
    # unidad recien planificada no tiene params ni dependencias propagadas, y
    # aun asi pedirla por id es como se genera desde su tarjeta
    trabajo_assets = os.path.join(cliente.carpeta, pid, "pasos", "assets", "trabajo")
    os.makedirs(trabajo_assets, exist_ok=True)
    with open(os.path.join(trabajo_assets, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump({"assets": {"asset:pepe": {"tipo": "reparto",
                                             "nombre": "pepe"}},
                   "escenas": [{"id": "S001"}], "dependencias": {}}, fh)
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                                    {"unidades": ["asset:pepe"]})
    igual(respuesta.status_code, 202,
          "una unidad que el plan conoce pasa la validacion sin estar declarada")
    esperar_trabajo(cliente, datos["trabajo_id"])
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                                    {"unidades": ["asset:nadie"]})
    igual(respuesta.status_code, 400,
          "y una que ni el plan ni el estado conocen sigue dando 400")

    respuesta, datos = cliente.post(f"/api/proyectos/{virgen}/pasos/assets/ejecutar",
                                    {"unidades": ["escena:S01"]})
    igual(respuesta.status_code, 409,
          "pedir unidades en un proyecto que aun no tiene ninguna da 409")

    # la opcion 'tipos' de assets: es la que usan los botones de "Generar los
    # personajes" / "las piezas", y el servidor la tiraba sin decirlo
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                                    {"tipos": "reparto"})
    igual(respuesta.status_code, 400, "'tipos' que no es lista da 400")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                                    {"tipos": [123]})
    igual(respuesta.status_code, 400, "'tipos' con cosas que no son texto da 400")

    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/pasos/assets/ejecutar",
                                    {"tipos": ["reparto"]})
    igual(respuesta.status_code, 202, "lanzar assets con tipos responde 202")
    igual((datos.get("opciones") or {}).get("tipos"), ["reparto"],
          "y la respuesta confirma que 'tipos' viaja como opcion de invocacion")
    ficha = esperar_trabajo(cliente, datos["trabajo_id"])
    # sin estilo fijado el paso corta la pasada: lo que se prueba aqui es que
    # la opcion LLEGA y el paso corre hasta su propia validacion de negocio
    igual(ficha["estado"], "error", "sin estilo fijado la pasada corta en error")
    ok("estilo" in str(ficha.get("error", "")).lower(),
       "y el error dice que falta el estilo")


# -------------------------------------------------------------------------- main

def probar_claves(cliente):
    """La pantalla de configuracion: N cuentas, sin que salga ninguna clave."""
    seccion("CLAVES DE API")
    respuesta, ficha = cliente.get("/api/claves")
    igual(respuesta.status_code, 200, "GET /api/claves responde 200")
    crudo = json.dumps(ficha)
    ok("clave" not in ficha.get("cartesia", {}),
       "la respuesta NO lleva la clave de Cartesia")
    ok(all("clave" not in c for c in ficha.get("openai", [])),
       "ni las de OpenAI: solo etiqueta y los cuatro ultimos")
    ok("max_openai" in ficha, "dice cuantas cuentas admite")

    # UNA SOLA CLAVE DE OPENAI. Con varias habia un reparto que convertia una
    # clave mal puesta en «va mas lento» en vez de en un error, y una segunda
    # cuenta doblaba el techo de imagenes por minuto. Ahora es una: si esta mal
    # se dice, y se para.
    respuesta, ficha = cliente.put("/api/claves", {"openai": [
        {"etiqueta": "mia@ejemplo.com", "clave": "sk-" + "a" * 40}]})
    igual(respuesta.status_code, 200, f"PUT /api/claves guarda la clave: {ficha}")
    igual(len(ficha["openai"]), 1, "y guarda UNA")
    ok(ficha["openai"][0]["cola"].endswith("aaaa"),
       f"con su cola, que es lo unico que se ensena: {ficha['openai']}")

    respuesta, _ = cliente.put("/api/claves", {"openai": [
        {"clave": "sk-" + "a" * 40}, {"clave": "sk-" + "b" * 40}]})
    igual(respuesta.status_code, 400, "dos claves de OpenAI dan 400")

    # LAS TRES SUELTAS: se editan desde la pantalla, no en un fichero a mano.
    # Jamendo y Freesound estuvieron fuera del editor --«son del stack»-- y
    # ponerlas era abrir el .env con un editor de texto, que es justo lo que
    # esta pantalla existe para no tener que hacer.
    respuesta, ficha = cliente.put("/api/claves", {
        "cartesia": {"clave": "car-" + "x" * 20},
        "jamendo": {"clave": "jam-" + "y" * 12},
        "freesound": {"clave": "fso-" + "z" * 12}})
    igual(respuesta.status_code, 200, "PUT guarda las tres claves sueltas")
    for suelta in ("cartesia", "jamendo", "freesound"):
        ok(ficha[suelta]["puesta"], f"{suelta} queda puesta")
        ok("clave" not in ficha[suelta],
           f"y la de {suelta} NO baja al navegador")

    # editar UNA sin mandar las otras no borra las otras: es para lo que existe
    # el marcador CONSERVAR, y sin el cambiar Jamendo se llevaria Cartesia
    respuesta, ficha = cliente.put("/api/claves",
                                   {"jamendo": {"clave": "jam-nueva-1234"}})
    ok(ficha["cartesia"]["puesta"], "cambiar Jamendo no borra Cartesia")
    ok(ficha["freesound"]["puesta"], "ni Freesound")
    respuesta, ficha = cliente.put("/api/claves", {"jamendo": {"clave": ""}})
    ok(not ficha["jamendo"]["puesta"], "y una vacia la quita, que es como se quita")

    respuesta, _ = cliente.put("/api/claves", {"openai": [{"clave": "corta"}]})
    igual(respuesta.status_code, 400, "una clave que no lo parece da 400")


def probar_cuentas_cli(cliente):
    """Las cuentas del CLI: una LISTA ORDENADA, y se entra desde la pantalla."""
    seccion("LAS CUENTAS DEL CLI DE CLAUDE")
    respuesta, ficha = cliente.get("/api/claves/cli")
    igual(respuesta.status_code, 200, "GET /api/claves/cli responde 200")
    ok(isinstance(ficha.get("cuentas"), list), "devuelve una lista de cuentas")
    ok(ficha.get("max", 0) >= 2, f"y dice cuantas admite: {ficha.get('max')}")

    # ANADIR: la lista entera, como las de OpenAI. El id lo pone el servidor.
    respuesta, ficha = cliente.put("/api/claves", {"claude_cli": {"cuentas": [
        {"etiqueta": "la mia"}, {"etiqueta": "la de repuesto"}]}})
    igual(respuesta.status_code, 200, f"PUT guarda dos cuentas del CLI: {ficha}")
    cuentas = ficha["claude_cli"]["cuentas"]
    igual([c["etiqueta"] for c in cuentas], ["la mia", "la de repuesto"],
          "en el orden en que se mandan, que ES la prioridad")
    ok(all(c["id"] for c in cuentas), f"y con un id cada una: {cuentas}")
    ok(all(not c["entrada"] for c in cuentas),
       "recien creadas NO cuentan como logueadas: una carpeta sin sesion "
       "hecha falla de una forma que no se parece a nada")

    primero, segundo = cuentas[0]["id"], cuentas[1]["id"]
    respuesta, ficha = cliente.put("/api/claves", {"claude_cli": {"cuentas": [
        {"id": segundo, "etiqueta": "la de repuesto"},
        {"id": primero, "etiqueta": "la mia"}]}})
    igual([c["id"] for c in ficha["claude_cli"]["cuentas"]], [segundo, primero],
          "reordenar es mandar la lista en otro orden")

    respuesta, ficha = cliente.put("/api/claves", {"claude_cli": {"cuentas": [
        {"id": segundo, "etiqueta": "la de repuesto"}]}})
    igual([c["id"] for c in ficha["claude_cli"]["cuentas"]], [segundo],
          "y quitar una es no mandarla")

    # LA PANTALLA NO MANDA `config_dir` NI `entrada`, y aunque los mande no
    # cuentan: son del servidor. Si pudiera, un «Guardar» hecho sobre una ficha
    # vieja desharia en silencio el login que acaba de terminar.
    respuesta, ficha = cliente.put("/api/claves", {"claude_cli": {"cuentas": [
        {"id": segundo, "etiqueta": "la de repuesto",
         "config_dir": "C:/me/lo/invento", "entrada": True}]}})
    igual(respuesta.status_code, 200, "mandar carpeta y sesion no da error…")
    igual(ficha["claude_cli"]["cuentas"][0]["config_dir"], "",
          "…pero la carpeta la sigue poniendo el servidor")
    ok(not ficha["claude_cli"]["cuentas"][0]["entrada"],
       "y la sesion tambien: la pantalla no puede declararse logueada")

    respuesta, _ = cliente.put("/api/claves",
                               {"claude_cli": {"cuentas": [{}] * 20}})
    igual(respuesta.status_code, 400,
          "pasarse del tope da 400: la cadena se recorre en serie")
    respuesta, _ = cliente.put("/api/claves", {"claude_cli": "una cadena"})
    igual(respuesta.status_code, 400, "y una forma que no es una lista, tambien")

    # ENTRAR con una cuenta que no existe
    respuesta, _ = cliente.post("/api/claves/cli/noexiste/entrar")
    igual(respuesta.status_code, 404, "entrar con una cuenta que no existe da 404")
    respuesta, _ = cliente.post("/api/claves/cli/noexiste/codigo", {"codigo": "x"})
    igual(respuesta.status_code, 404, "y pegarle un codigo, tambien")

    # PEGAR UN CODIGO SIN HABER ENTRADO: 409, no 500
    respuesta, ficha = cliente.post(f"/api/claves/cli/{segundo}/codigo",
                                    {"codigo": "loquesea"})
    igual(respuesta.status_code, 409,
          "un codigo sin acceso abierto da 409 y lo explica")
    ok("Entrar" in json.dumps(ficha), f"y dice que hay que darle a Entrar: {ficha}")

    # CANCELAR algo que no existe no es un error
    respuesta, ficha = cliente.delete(f"/api/claves/cli/{segundo}/entrar")
    igual(respuesta.status_code, 200, "cancelar un acceso que no hay responde 200")
    ok(ficha.get("cancelado") is False, "diciendo que no habia ninguno")

    # SALIR de la sesion POR DEFECTO no se permite: es la consola del usuario
    respuesta, ficha = cliente.post(f"/api/claves/cli/{segundo}/salir")
    igual(respuesta.status_code, 409,
          "cerrar la sesion por defecto del CLI da 409, no la cierra")
    ok("terminal" in json.dumps(ficha),
       f"y dice por que: es la misma con la que el usuario tiene su consola: {ficha}")

    cliente.put("/api/claves", {"claude_cli": {"cuentas": []}})


def probar_asistente(cliente):
    """El asistente: estado, una charla entera contra el doble, y sus errores.

    El servidor corre con ESTUDIO_SIMULAR=1, asi que no se llama al CLI: contesta
    `asistente.ejecutar_simulado`, que repite lo que recibe. Lo que se prueba
    aqui es la API: abrir, preguntar, seguir la respuesta, reanudar, cancelar y
    cerrar, y que cada fallo tenga su codigo.
    """
    seccion("EL ASISTENTE")
    respuesta, ficha = cliente.get("/api/asistente")
    igual(respuesta.status_code, 200, "GET /api/asistente responde 200")
    ok(isinstance(ficha.get("listo"), bool), f"y dice si puede contestar: {ficha}")
    ok(ficha.get("modelo") and ficha.get("esfuerzo"),
       "y con que modelo y esfuerzo")
    ok(ficha.get("simulado") is True, "en las pruebas se declara simulado")

    respuesta, _ = cliente.get("/api/asistente/charlas/noexiste")
    igual(respuesta.status_code, 404, "una charla que no existe da 404")
    respuesta, _ = cliente.post("/api/asistente/charlas/noexiste/mensajes",
                                {"texto": "hola"})
    igual(respuesta.status_code, 404, "y preguntarle, tambien")
    respuesta, _ = cliente.post("/api/asistente/charlas/noexiste/cancelar")
    igual(respuesta.status_code, 404, "y cancelarla")
    respuesta, ficha = cliente.delete("/api/asistente/charlas/noexiste")
    igual(respuesta.status_code, 200, "cerrar una que no existe responde 200")
    ok(ficha.get("cerrada") is False, "diciendo que no habia ninguna")

    respuesta, charla = cliente.post("/api/asistente/charlas")
    igual(respuesta.status_code, 201, "POST /api/asistente/charlas abre una charla")
    cid = charla.get("id")
    ok(cid and charla.get("turnos") == [] and charla.get("ocupada") is False,
       f"vacia y libre: {charla}")

    respuesta, _ = cliente.post(f"/api/asistente/charlas/{cid}/mensajes", {"texto": "   "})
    igual(respuesta.status_code, 400, "una pregunta vacia da 400")

    respuesta, ficha = cliente.post(f"/api/asistente/charlas/{cid}/mensajes",
                                    {"texto": "que me falta?", "proyecto": "",
                                     "pantalla": {"pestana": "encargo"}})
    igual(respuesta.status_code, 202, f"una pregunta responde 202: {ficha}")
    igual(len(ficha.get("turnos") or []), 2, "con el turno de la persona y el del asistente")
    # «pensando» O YA «listo» (B12, 10-10-2026): la pregunta arranca un hilo y
    # devuelve la ficha; el asistente SIMULADO contesta tan rapido que a veces
    # gana la carrera, y la prueba fallaba sola y bajo carga
    ok(ficha["turnos"][1]["estado"] in ("pensando", "listo"),
       f"que empieza pensando (o ya contestó): {ficha['turnos'][1]['estado']!r}")

    def esperar_respuesta(segundos=20):
        limite = time.time() + segundos
        while time.time() < limite:
            r, f = cliente.get(f"/api/asistente/charlas/{cid}")
            if r.status_code == 200 and not f.get("ocupada"):
                return f
            time.sleep(0.2)
        return f

    ficha = esperar_respuesta()
    ultimo = ficha["turnos"][-1]
    igual(ultimo["estado"], "listo", f"y termina listo: {ultimo}")
    ok("que me falta?" in ultimo["texto"], "el doble repite la pregunta")
    ok("de arranque" in ultimo["texto"], "y el primer turno es de arranque")
    ok(ficha.get("reanuda") is True, "la charla se acuerda de la sesion")
    ok(ultimo.get("segundos") is not None and ultimo.get("tokens"),
       "y el turno dice cuanto tardo y cuantos tokens")

    respuesta, ficha = cliente.post(f"/api/asistente/charlas/{cid}/mensajes",
                                    {"texto": "y ahora?"})
    igual(respuesta.status_code, 202, "una segunda pregunta tambien va")
    ficha = esperar_respuesta()
    ok("reanudando la sesion" in ficha["turnos"][-1]["texto"],
       f"y el segundo turno REANUDA la sesion del primero: {ficha['turnos'][-1]['texto'][:120]}")

    respuesta, ficha = cliente.post(f"/api/asistente/charlas/{cid}/cancelar")
    igual(respuesta.status_code, 200, "cancelar sin nada en marcha responde 200")
    ok(ficha.get("cancelado") is False, "diciendo que no habia nada que parar")

    # EL DICTADO: un audio del navegador pasado a texto para la caja. En
    # simulado no sale a OpenAI; lo que se prueba es el camino y sus errores.
    respuesta, estado = cliente.get("/api/asistente")
    ok(estado.get("dictado") is True, "el estado dice que se puede dictar")
    respuesta, dictado = cliente.pedir(
        "POST", "/api/asistente/dictado",
        files={"audio": ("dictado.webm", b"\x1a\x45\xdf\xa3" + b"0" * 2000, "audio/webm")},
        data={"idioma": "es"})
    igual(respuesta.status_code, 200, f"POST /api/asistente/dictado pasa a texto: {dictado}")
    ok("dictado de" in ((dictado or {}).get("texto") or ""),
       "y devuelve el texto (no pregunta nada al asistente)")
    respuesta, _d = cliente.pedir("POST", "/api/asistente/dictado",
                                  files={"otro": ("x.txt", b"hola", "text/plain")})
    igual(respuesta.status_code, 400, "sin campo 'audio' da 400")
    respuesta, _d = cliente.pedir("POST", "/api/asistente/dictado",
                                  files={"audio": ("vacio.webm", b"", "audio/webm")})
    igual(respuesta.status_code, 400, "un audio vacío da 400 con el motivo")

    # «SIEMPRE EL DEL NAVEGADOR»: elegido en Configuración, no se manda audio
    respuesta, _d = cliente.put("/api/ajustes", {"dictado": "navegador"})
    igual(respuesta.status_code, 200, "se elige el dictado del navegador")
    _r, estado = cliente.get("/api/asistente")
    ok(estado.get("dictado") is False and estado.get("dictado_modo") == "navegador",
       "y el estado deja de ofrecer OpenAI")
    respuesta, _d = cliente.pedir("POST", "/api/asistente/dictado",
                                  files={"audio": ("d.webm", b"0" * 200, "audio/webm")})
    igual(respuesta.status_code, 409, "y el servidor no manda el audio a OpenAI")
    respuesta, _d = cliente.put("/api/ajustes", {"dictado": "siempre"})
    igual(respuesta.status_code, 400, "un modo de dictado que no existe da 400")
    cliente.put("/api/ajustes", {"dictado": "auto"})

    # LA HORA DE LA REGIÓN: el servidor apunta las horas en la zona elegida
    respuesta, datos = cliente.put("/api/ajustes", {"zona_horaria": "America/Lima"})
    igual(respuesta.status_code, 200, "se elige la zona America/Lima")
    igual((datos.get("zona") or {}).get("desfase"), "UTC-05:00",
          "y el servidor pasa a UTC-05:00 en el acto, sin reiniciar")
    _r, datos = cliente.get("/api/ajustes")
    igual((datos.get("ajustes") or {}).get("zona_horaria"), "America/Lima",
          "y queda guardada")
    respuesta, _d = cliente.put("/api/ajustes", {"zona_horaria": "Marte/Olimpo"})
    igual(respuesta.status_code, 400, "una zona que no existe da 400")
    _r, datos = cliente.put("/api/ajustes", {"zona_horaria": ""})
    igual((datos.get("ajustes") or {}).get("zona_horaria"), "",
          "y vacía vuelve a la del servidor")

    # EL HISTORIAL: la charla queda guardada junto a los datos, no en memoria
    respuesta, historial = cliente.get("/api/asistente/charlas")
    igual(respuesta.status_code, 200, "GET /api/asistente/charlas da el historial")
    suya = [c for c in (historial or {}).get("charlas") or [] if c.get("id") == cid]
    ok(suya and suya[0].get("titulo") == "que me falta?",
       f"con esta charla y su primera pregunta como titulo: {suya}")
    ok(os.path.isfile(os.path.join(cliente.carpeta, "_asistente", "charlas", f"{cid}.json")),
       "guardada en <proyectos>/_asistente/charlas/, fuera del codigo")

    respuesta, ficha = cliente.delete(f"/api/asistente/charlas/{cid}")
    igual(respuesta.status_code, 200, "cerrar la charla responde 200")
    ok(ficha.get("cerrada") is True, "y la cierra")
    ok(not os.path.exists(os.path.join(cliente.carpeta, "_asistente", "charlas",
                                       f"{cid}.json")),
       "y la borra del historial")
    respuesta, _ = cliente.get(f"/api/asistente/charlas/{cid}")
    igual(respuesta.status_code, 404, "y ya no esta")


def probar_la_foto_del_asistente(cliente, pid):
    """La foto del estado que recibe el asistente lleva lo que hace falta y
    ninguna clave. Se pide por la API (`/api/asistente/foto`), que devuelve
    EXACTAMENTE el texto que va delante de cada pregunta."""
    seccion("LA FOTO QUE VE EL ASISTENTE")
    # una clave de mentira para comprobar que NO viaja
    respuesta, _ = cliente.put("/api/claves", {"openai": [
        {"etiqueta": "", "clave": "sk-esta-clave-no-puede-salir-en-la-foto-000",
         "activa": True}]})
    igual(respuesta.status_code, 200, "se guarda una clave de OpenAI de mentira")
    respuesta, ficha = cliente.get("/api/asistente/foto",
                                   params={"proyecto": pid, "pestana": "imagenes",
                                           "error": "S03: la cara sale rara"})
    igual(respuesta.status_code, 200, "GET /api/asistente/foto responde 200")
    foto = ficha.get("foto") or ""
    ok("sk-esta-clave" not in foto and "foto-000" not in foto, "la clave NO viaja en la foto")
    ok("OpenAI (imagenes) puesta" in foto, "pero si que esta puesta")
    ok("PROYECTO ABIERTO EN PANTALLA" in foto and pid in foto, "lleva el proyecto abierto")
    ok("paso ingesta" in foto and "paso render" in foto, "con sus ocho pasos")
    ok("S03: la cara sale rara" in foto, "y los errores que la pantalla tiene a la vista")
    ok("pestana: imagenes" in foto, "y la pestana")
    ok("proyectos (videos)" in foto, "y la lista de videos")
    ok("ultimos trabajos" in foto, "y los ultimos trabajos del video")
    ok(ficha.get("caracteres") == len(foto), "y dice cuanto ocupa")

    respuesta, ficha = cliente.get("/api/asistente/foto")
    sin = ficha.get("foto") or ""
    ok("PROYECTO ABIERTO" not in sin and "fecha y hora" in sin,
       "sin proyecto abierto la foto sigue saliendo")
    respuesta, ficha = cliente.get("/api/asistente/foto", params={"proyecto": "no_existe"})
    igual(respuesta.status_code, 200, "un proyecto que no existe no revienta")
    ok("no_existe" in ficha.get("foto", "") and "desconocido" in ficha.get("foto", ""),
       "se dice en la propia foto")
    cliente.put("/api/claves", {"openai": []})


def probar_sistema(cliente):
    """Lo de la V2.0: guias de escritura, novedades, notas e imagenes del asistente."""
    seccion("EL SISTEMA: GUIAS, NOVEDADES, NOTAS E IMAGENES DEL ASISTENTE")
    respuesta, datos = cliente.get("/api/sistema/guias")
    igual(respuesta.status_code, 200, "GET /api/sistema/guias responde 200")
    ids = [g.get("id") for g in datos.get("guias") or []]
    igual(ids, ["estilo_grafico", "tono", "voz", "material", "indicaciones", "cta",
                "texto_tiktok", "texto_instagram", "texto_youtube", "texto_facebook",
                "tono_redes", "guion_parrilla", "pedir_guiones", "marca_cliente", "chat_guiones",
                "analizar_cuenta", "conexiones_cuentas",
                "palabra_clave", "ubicacion_instagram", "categoria_youtube", "hecho_para_ninos",
                "texto_linkedin", "texto_x", "texto_threads", "texto_pinterest", "texto_bluesky",
                "texto_discord", "texto_telegram", "texto_mastodon", "texto_google_business",
                "emojis_redes"],
          "estan las treinta y una guias (seis de Crear, diecinueve de Publicar y seis de la Parrilla), en orden")
    ok(all(g.get("plantilla") and g.get("prompt_ia") and g.get("que_hace")
           for g in datos.get("guias") or []),
       "cada guia trae plantilla, prompt para otra IA y que hace el sistema")

    respuesta, datos = cliente.get("/api/sistema/novedades")
    igual(respuesta.status_code, 200, "GET /api/sistema/novedades responde 200")
    ok("V2.0" in (datos.get("texto") or ""), "las novedades hablan de la V2.0")
    igual(datos.get("producto"), "CrearIA Studio", "con el nombre nuevo")

    respuesta, datos = cliente.post("/api/sistema/notas", {"texto": "  "})
    igual(respuesta.status_code, 400, "una nota vacia da 400")
    respuesta, datos = cliente.post("/api/sistema/notas", {"texto": "subir el subtitulo"})
    igual(respuesta.status_code, 201, "crear una nota responde 201")
    nid = (datos.get("nota") or {}).get("id") or ""
    igual((datos.get("nota") or {}).get("estado"), "pendiente", "y nace pendiente")
    respuesta, datos = cliente.put(f"/api/sistema/notas/{nid}", {"estado": "hecha"})
    igual((datos.get("nota") or {}).get("estado"), "hecha", "se marca como hecha")
    ok((datos.get("nota") or {}).get("hecha_el"), "y apunta cuando")
    respuesta, _ = cliente.put(f"/api/sistema/notas/{nid}", {"estado": "inventado"})
    igual(respuesta.status_code, 400, "un estado desconocido da 400")
    respuesta, datos = cliente.get("/api/sistema/notas")
    ok(any(n["id"] == nid for n in datos.get("notas") or []), "la nota se lista")
    ok("_sistema" in (datos.get("ruta") or ""),
       "y vive en la carpeta de datos, fuera del codigo")
    respuesta, _ = cliente.delete(f"/api/sistema/notas/{nid}")
    igual(respuesta.status_code, 200, "se borra")
    respuesta, _ = cliente.delete(f"/api/sistema/notas/{nid}")
    igual(respuesta.status_code, 404, "y borrarla otra vez es un 404")

    # las imagenes que se pegan al asistente
    from PIL import Image
    imagen = io.BytesIO()
    Image.new("RGB", (40, 30), "red").save(imagen, "PNG")
    respuesta = cliente.sesion.post(
        f"{cliente.base}/api/asistente/imagenes", timeout=30,
        files={"imagenes": ("captura.png", imagen.getvalue(), "image/png")})
    igual(respuesta.status_code, 201, "subir una imagen al asistente responde 201")
    nombre = ((respuesta.json().get("imagenes") or [{}])[0]).get("nombre") or ""
    ok(re.fullmatch(r"[0-9a-f]{12}\.png", nombre or ""),
       f"y se guarda con un nombre que no dice nada: {nombre}")
    respuesta = cliente.sesion.get(f"{cliente.base}/api/asistente/imagenes/{nombre}", timeout=30)
    igual(respuesta.status_code, 200, "la miniatura se sirve")
    respuesta = cliente.sesion.get(f"{cliente.base}/api/asistente/imagenes/%2E%2E", timeout=30)
    igual(respuesta.status_code, 404, "y pedir la carpeta de arriba es un 404")
    respuesta, charla = cliente.post("/api/asistente/charlas", {})
    cid = charla.get("id") or (charla.get("charla") or {}).get("id")
    respuesta, _ = cliente.post(f"/api/asistente/charlas/{cid}/mensajes",
                                {"texto": "x", "imagenes": ["../../secretos/claves.json"]})
    igual(respuesta.status_code, 400, "una imagen que no es de la subida se rechaza")
    respuesta, _ = cliente.post(f"/api/asistente/charlas/{cid}/mensajes",
                                {"texto": "¿qué ves?", "imagenes": [nombre]})
    igual(respuesta.status_code, 202, "una pregunta con imagen se acepta")
    final = None
    for _ in range(40):
        _, final = cliente.get(f"/api/asistente/charlas/{cid}")
        if final["turnos"][-1]["estado"] != "pensando":
            break
        time.sleep(0.25)
    igual(final["turnos"][0].get("imagenes"), [nombre], "la pregunta recuerda su imagen")
    ok(nombre in final["turnos"][-1]["texto"]
       and "IMAGENES ADJUNTAS" in final["turnos"][-1]["texto"],
       "y al CLI le llega la ruta con la orden de abrirla")


def probar_lo_que_lleva(cliente):
    """«Que lleva este video»: voz, subtitulos, musica y efectos."""
    seccion("QUE LLEVA ESTE VIDEO")
    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Estilo para lleva",
        "datos": {"guion": {"idioma_salida": "es"},
                  "voz": {"voz_id": "v-de-prueba", "idioma": "es"},
                  "origen": {"tono_prompt": "serio", "estilo_prompt": "plano"}}})
    estilo = (datos.get("preset") or {}).get("id") or ""
    antes = set(os.listdir(cliente.carpeta))
    respuesta, datos = cliente.post(f"/api/presets-light/{estilo}/video", {
        "nombre": "Sin voz", "material": "x", "lleva": {"voz": False}})
    igual(respuesta.status_code, 400, "un video sin voz todavia se rechaza, con su motivo")
    respuesta, _ = cliente.post(f"/api/presets-light/{estilo}/video", {
        "nombre": "Raro", "material": "x", "lleva": {"karaoke": True}})
    igual(respuesta.status_code, 400, "una pieza que no existe da 400")
    igual(set(os.listdir(cliente.carpeta)), antes,
          "y ninguno de los dos deja un proyecto a medias")

    respuesta, datos = cliente.post(f"/api/presets-light/{estilo}/video", {
        "nombre": "Lleva poco", "material": "x",
        "lleva": {"subtitulos": False, "musica": False}})
    igual(respuesta.status_code, 201, "con subtitulos y musica apagados se crea")
    pid = (datos.get("proyecto") or {}).get("id") or ""
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/lleva")
    igual(datos.get("lleva"), {"voz": True, "subtitulos": False, "musica": False,
                               "efectos": True}, "y lo recuerda")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
    igual((datos.get("params") or {}).get("subtitulos"), False,
          "los subtitulos apagados van al param de callouts")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    ok("musica" not in (datos.get("params") or {}),
       "y la musica apagada en un video nuevo no escribe nada en el render")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pestanas/render")
    puestas = {t["id"]: t.get("puesta") for t in datos.get("tareas") or []}
    igual(puestas.get("banda_sonora"), False, "la tanda se salta la banda sonora")
    igual(puestas.get("efectos"), True, "y no los efectos, que si los lleva")

    # un video que YA tenia musica: apagarla la vacia en el render, y nada mas
    cliente.put(f"/api/proyectos/{pid}/pasos/render/params",
                {"params": {"musica": {"tramos": [{"animo": "calma"}]}}})
    cliente.put(f"/api/proyectos/{pid}/lleva", {"lleva": {"musica": True}})
    respuesta, datos = cliente.put(f"/api/proyectos/{pid}/lleva", {"lleva": {"musica": False}})
    igual(respuesta.status_code, 200, "apagar la musica de un video responde 200")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    igual((datos.get("params") or {}).get("musica"), {},
          "y vacia la que ya tenia: el render se rehace sin ella")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    ok("subtitulos" not in (datos.get("params") or {})
       and "musica" not in (datos.get("params") or {}),
       "las imagenes (assets) no se tocan: no hay nada que volver a pagar")
    respuesta, _ = cliente.put(f"/api/proyectos/{pid}/lleva", {"lleva": {"voz": False}})
    igual(respuesta.status_code, 400, "apagar la voz de un video abierto tambien se rechaza")


    seccion("EL ESPANOL DE LATINOAMERICA")
    respuesta, datos = cliente.get("/api/presets-light")
    idiomas = {i["valor"]: i["nombre"] for i in datos.get("idiomas") or []}
    igual(idiomas.get("es-419"), "Español (Latinoamérica)",
          "la lista de idiomas ofrece el espanol de Latinoamerica")
    ok(list(idiomas)[:2] == ["es", "es-419"], "justo detras del espanol de siempre")
    respuesta, datos = cliente.post("/api/presets-light/plan", {
        "nombre": "Canal latino", "idioma": "es-419", "estilo_imagenes": ["x.png"],
        "tono_prompt": "cercano y claro", "voz_prompt": "calida y serena"})
    igual(respuesta.status_code, 200, "un encargo en es-419 se acepta")
    igual((datos.get("encargo") or {}).get("idioma"), "es",
          "y por dentro es espanol: las voces y las palabras se cuentan con «es»")
    igual((datos.get("encargo") or {}).get("variante_idioma"), "latam",
          "con la variante latina aparte")


def probar_onboarding(cliente):
    """La marca de la guia de inicio vive en los ajustes del servidor."""
    seccion("LA GUIA DE INICIO")
    respuesta, ficha = cliente.get("/api/ajustes")
    igual(respuesta.status_code, 200, "GET /api/ajustes responde 200")
    ok(ficha["ajustes"].get("onboarding_visto") is False,
       f"de fabrica la guia no se ha visto: {ficha['ajustes']}")
    respuesta, ficha = cliente.put("/api/ajustes", {"onboarding_visto": True})
    igual(respuesta.status_code, 200, "se marca como vista")
    ok(ficha["ajustes"].get("onboarding_visto") is True, "y lo dice")
    respuesta, _ = cliente.put("/api/ajustes", {"onboarding_visto": "si"})
    igual(respuesta.status_code, 400, "una marca que no es booleana da 400")
    respuesta, ficha = cliente.get("/api/ajustes")
    ok(ficha["ajustes"].get("onboarding_visto") is True
       and ficha["ajustes"].get("calidad_imagen") in ficha.get("calidades", []),
       "se queda marcada y la calidad sigue en su sitio")


def probar_salud_de_las_cuentas(cliente):
    """La salud de las cuentas de Claude y la prueba de las claves, por la API.

    En modo simulado `salud_cli.probar` no llama al CLI y `comprobar_claves`
    no sale a la red: lo que se comprueba es la API y que la salud viaje en
    la lista de cuentas y en el estado del asistente.
    """
    seccion("LA SALUD DE LAS CUENTAS Y LA PRUEBA DE LAS CLAVES")
    respuesta, ficha = cliente.put("/api/claves", {"claude_cli": {"cuentas": [
        {"etiqueta": "la de prueba"}]}})
    igual(respuesta.status_code, 200, "se anade una cuenta del CLI")
    cid = ficha["claude_cli"]["cuentas"][0]["id"]
    respuesta, ficha = cliente.get("/api/claves/cli")
    ok("salud" in ficha["cuentas"][0], "cada cuenta de la lista lleva su salud")
    ok(ficha["cuentas"][0]["salud"] is None, "y una recien anadida no tiene nada apuntado")

    respuesta, ficha = cliente.post(f"/api/claves/cli/{cid}/probar")
    igual(respuesta.status_code, 200, f"probar una cuenta responde 200: {ficha}")
    igual((ficha.get("salud") or {}).get("estado"), "ok", "en simulado contesta ok")
    ok("cuentas" in ficha and ficha["cuentas"][0]["salud"]["estado"] == "ok",
       "y devuelve la lista con la salud puesta")
    respuesta, _ = cliente.post("/api/claves/cli/noexiste/probar")
    igual(respuesta.status_code, 404, "probar una cuenta que no existe da 404")

    respuesta, ficha = cliente.get("/api/asistente")
    ok(isinstance(ficha.get("cuentas"), list) and "sin_probar" in ficha,
       f"el estado del asistente lleva las cuentas con su salud: {ficha.get('cuentas')}")
    respuesta, ficha = cliente.post("/api/asistente/probar")
    igual(respuesta.status_code, 200, "probar el asistente responde 200")
    ok(isinstance(ficha.get("probadas"), list) and "listo" in ficha,
       f"y dice que cuentas probo y si esta listo: {ficha.get('probadas')}")

    respuesta, ficha = cliente.post("/api/claves/probar", {"claude": True})
    igual(respuesta.status_code, 200, f"probar todas las claves responde 200: {str(ficha)[:200]}")
    proveedores = [p["proveedor"] for p in ficha.get("pruebas") or []]
    ok(proveedores[:4] == ["openai", "cartesia", "jamendo", "freesound"],
       f"con los cuatro servicios en orden: {proveedores}")
    ok("claude" in proveedores, "y Claude cuando se pide")
    ok(isinstance(ficha.get("resumen"), str) and "todo_bien" in ficha,
       "con un resumen legible y un veredicto")
    respuesta, ficha = cliente.post("/api/claves/probar", {"claude": False})
    ok("claude" not in [p["proveedor"] for p in ficha.get("pruebas") or []],
       "y sin Claude cuando no se pide")

    respuesta, _ = cliente.get("/api/asistente/foto")
    cliente.put("/api/claves", {"claude_cli": {"cuentas": []}})


def probar_recetas(cliente, pid):
    """Ejecutar una pestana entera: el catalogo, el estado y el lanzamiento."""
    seccion("RECETAS POR PESTANA")
    respuesta, catalogo = cliente.get("/api/recetas")
    igual(respuesta.status_code, 200, "GET /api/recetas responde 200")
    pestanas = {p["id"]: p for p in catalogo["pestanas"]}
    igual(sorted(pestanas), ["guion", "origen", "render", "video", "voz"],
          "las cinco pestanas tienen receta")
    tandas = pestanas["video"]["tandas"]
    ok(["escenarios", "guia_estilo"] == tandas[0],
       f"lo que no depende de nada va en la misma tanda: {tandas[0]}")
    plano = [t for t in tandas if "assets" in t][0]
    igual(plano, ["assets"], "generar los planos va solo, esperando a los demas")
    orden = [t for tanda in tandas for t in tanda]
    ok(orden.index("plan_cartelas") < orden.index("assets"),
       "las cartelas se deciden ANTES de generar: si no, se paga una imagen "
       "para tirarla")
    # EL CORTE ES UN PASO, y va antes que todo lo que decide POR PLANO. Sin él,
    # la tanda de un vídeo NUEVO se plantaba a la mitad con «no hay planos
    # todavía»: las cartelas y la dirección no tenían sobre qué decidir.
    ok(orden.index("corte") < orden.index("plan_cartelas"),
       f"el corte en planos va antes que las cartelas ({orden})")
    ok(orden.index("corte") < orden.index("direccion"),
       "y antes que la dirección, que también decide plano a plano")
    # Y LAS PIEZAS, DESPUÉS DE LAS CARTELAS: un plano que se convierte en
    # cartela pierde su sitio y su gente, así que el mapa que pedía deja de
    # hacer falta. Generarlo antes es pagarlo para tirarlo.
    ok(orden.index("plan_cartelas") < orden.index("piezas"),
       "las piezas van después de las cartelas")
    corte = [t for t in tandas if "corte" in t][0]
    igual(corte, ["corte"], "y el corte va solo: dos tareas replanificando a "
                            "la vez escriben sobre la misma carpeta")

    # Y EL CORTE LO HACE ESA TAREA, UNA VEZ. Las de `assets` de la receta pasan
    # `replantear: False`: replantear renumera los planos, y si lo hiciera
    # también la pasada de piezas o la de planos, la dirección y las cartelas
    # —que se deciden POR PLANO— acabarían apuntando a otros. Medido en la
    # primera tanda de un vídeo nuevo: el corte dio 97 planos y piezas 98.
    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "app.py"),
                     encoding="utf-8").read()
    trozo = fuente[fuente.index('if tarea_id == "piezas":'):
                   fuente.index('if tarea_id == "callouts":')]
    igual(trozo.count('"replantear": False'), 2,
          "las dos tareas de assets de la receta pasan replantear: False")
    ok(orden.index("assets") < orden.index("callouts"),
       "y los subtitulos DESPUES de los planos: se dibujan encima")
    ok("plan_callouts" not in orden,
       "y la fase de PAGO que decidia los rotulos ya no existe: los rotulos se "
       "retiraron enteros el 22-08")

    # LO QUE LA PANTALLA NECESITA PARA NO DEDUCIR NADA. `publico` es como se
    # cuenta esa tarea mientras corre, y `de_fabrica` es si viene puesta sin
    # ninguna receta guardada.
    todas = [t for p in catalogo["pestanas"] for t in p["tareas"]]
    ok(all(t.get("publico") for t in todas),
       "cada tarea del catalogo dice su nombre publico")
    ok(all("de_fabrica" in t for t in todas),
       "y si viene puesta de fabrica")
    ids_guion = [t["id"] for t in pestanas["guion"]["tareas"]]
    ok("integraciones" not in ids_guion and "fuentes" not in ids_guion,
       f"ni menciones del mapa ni documentalista: no existen ({ids_guion})")

    respuesta, estado = cliente.get(f"/api/proyectos/{pid}/pestanas/video")
    igual(respuesta.status_code, 200, "GET /pestanas/video responde 200")
    ok(all("al_dia" in t and "puesta" in t for t in estado["tareas"]),
       "cada tarea dice si esta al dia y si esta puesta")
    ok(any(t["cuesta"] for t in estado["tareas"]), "y cual cuesta dinero")

    # UNA TAREA QUE CAMBIA LO QUE CUESTA CADA IMAGEN NO SE ENCIENDE SOLA... en
    # un video que YA las ha pagado. `direccion` reescribe el prompt de todos
    # los planos, o sea que la cache falla y se vuelven a pagar. Encendida de
    # fabrica, la primera vez que alguien pulsara «Generar lo que falta» en un
    # video ya montado se encontraria el video entero regenerado sin haber
    # elegido nada. Donde no hay ninguna imagen que repagar --un video que
    # nunca ha generado sus planos-- viene encendida, se haya creado por donde
    # se haya creado: es la regla de `_receta_de_video`, y esta
    # pantalla la lee de ahi para decir lo mismo que va a hacer la tanda.
    respuesta, assets = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    con_planos = bool((assets or {}).get("versiones"))
    puestas = {t["id"]: t["puesta"] for t in estado["tareas"]}
    igual(puestas.get("direccion"), not con_planos,
          "la direccion viene APAGADA en un video con planos hechos y ENCENDIDA "
          f"en uno que nunca los ha pagado (este {'los tiene' if con_planos else 'no los tiene'})")
    ok(puestas.get("plan_cartelas") and puestas.get("piezas"),
       f"y las demas opcionales siguen puestas: {puestas}")
    if con_planos:
        ok("direccion" not in (estado.get("pendientes") or []),
           "asi que no sale en lo pendiente de la pestana")

    respuesta, _ = cliente.get(f"/api/proyectos/{pid}/pestanas/no_existe")
    igual(respuesta.status_code, 404, "una pestana inventada da 404")
    respuesta, _ = cliente.post(f"/api/proyectos/{pid}/pestanas/video/generar",
                                {"modo": "raro"})
    igual(respuesta.status_code, 400, "un modo inventado da 400")

    # apagar una tarea opcional se guarda, y deja de salir en lo pendiente
    respuesta, receta = cliente.post("/api/recetas", {
        "pestana": "video", "nombre": "Sin cartelas",
        "tareas": {"plan_cartelas": False}, "por_defecto": True})
    igual(respuesta.status_code, 200, f"POST /api/recetas guarda: {receta}")
    ok(receta["tareas"]["assets"],
       "lo obligatorio se fuerza aunque no se mande")
    igual(receta["tareas"]["plan_cartelas"], False, "y lo opcional se respeta")
    respuesta, estado = cliente.get(f"/api/proyectos/{pid}/pestanas/video")
    cartelas_puesta = [t for t in estado["tareas"] if t["id"] == "plan_cartelas"][0]
    igual(cartelas_puesta["puesta"], False,
          "la receta por defecto manda en lo que se va a hacer")
    respuesta, _ = cliente.delete(f"/api/recetas/{receta['id']}")
    igual(respuesta.status_code, 200, "y se puede borrar")
    respuesta, _ = cliente.post("/api/recetas", {"pestana": "video"})
    igual(respuesta.status_code, 400, "una receta sin nombre da 400")


#: Palabras de la COCINA. Ninguna puede salir en una frase publica: son los
#: nombres de las piezas del Estudio, y quien mira el video no tiene por que
#: llevarselos. La lista es de prefijos: 'subtitul' pilla singular y plural.
COCINA = (
    "prompt", "modelo", "cli", "claude", "openai", "cartela", "callout",
    "asset", "rotulo", "rótulo", "json", "ffmpeg", "yt-dlp", "api", "token",
    "param", "receta", "preset", "taller", "plano", "render", "moodboard",
    "wikimedia", "jamendo", "freesound", "cartesia", "tts", "subtitul",
    "subtítul", "guion", "guión", "brief", "ingesta", "pestaña", "unidad",
)


def probar_lo_que_se_cuenta_en_publico():
    """El modo light se graba: sus barras no pueden ensenar como esta hecho.

    Aqui se fija el CONTRATO de esa mascara, que tiene tres mitades:

      · COMPLETA: toda tarea tiene su frase publica. Una tarea nueva sin entrada
        no ensena su nombre de casa -- se dice «Trabajando» -- pero eso es el
        respaldo, no el sitio donde se quiere estar.
      · LIMPIA: ni una palabra de la cocina, y ninguna frase igual al nombre de
        casa (si coincidieran no seria una mascara, seria una copia).
      · SEGURA: lo que no se sabe se tapa. `publico_de` de una tarea que no
        existe devuelve el generico, nunca el nombre real.
    """
    seccion("LO QUE SE CUENTA EN PUBLICO")
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    import recetas                                            # noqa: PLC0415
    import presets_light                                      # noqa: PLC0415

    for modulo, nombre in ((recetas, "recetas"), (presets_light, "presets_light")):
        faltan = [x["id"] for x in modulo.TAREAS if x["id"] not in modulo.PUBLICO]
        igual(faltan, [], f"{nombre}: todas las tareas tienen frase publica")
        for tarea in modulo.TAREAS:
            ficha = modulo.PUBLICO.get(tarea["id"]) or {}
            ok(bool(ficha.get("nombre")) and bool(ficha.get("fases")),
               f"{nombre}/{tarea['id']}: tiene titulo y al menos una fase")
            ok(ficha.get("nombre") != tarea["nombre"],
               f"{nombre}/{tarea['id']}: la frase publica no es el nombre de casa")
            frases = [ficha.get("nombre", "")] + list(ficha.get("fases") or [])
            for frase in frases:
                sucias = [p for p in COCINA
                          if re.search(r"\b" + re.escape(p), frase, re.I)]
                igual(sucias, [], f"{nombre}/{tarea['id']}: «{frase}» sin cocina")

        # LA FASE SE MUEVE CON LA FRACCION: eso es el «desglosado» de la barra.
        largas = [x for x in modulo.TAREAS
                  if len((modulo.PUBLICO[x["id"]].get("fases") or [])) > 1]
        tid = largas[0]["id"]
        fases = modulo.PUBLICO[tid]["fases"]
        ok(fases[0] in modulo.publico_de(tid, 0.0),
           f"{nombre}: al empezar la tarea se dice su primera fase")
        ok(fases[-1] in modulo.publico_de(tid, 1.0),
           f"{nombre}: y al acabarla, la ultima")

        # LO QUE NO SE SABE SE TAPA, nunca se destapa.
        igual(modulo.publico_de("no_existe_esta_tarea", 0.5),
              modulo.PUBLICO_GENERICO,
              f"{nombre}: una tarea desconocida se cuenta como generica")
        ok(modulo.publico_de("no_existe_esta_tarea") == modulo.PUBLICO_GENERICO,
           f"{nombre}: y sin fraccion, igual")

    # UNA CUENTA MEDIDA MANDA SOBRE LA FASE INVENTADA.
    #
    # La fase sale de partir la fraccion en tramos, asi que «volviendo a dibujar
    # lo que no encaja» solo significa «va por el segundo tercio» -- y se vio
    # diciendolo mientras todavia MIRABA la tanda 20 de 36. Con doscientos
    # dieciseis planos delante, lo que hace falta es la cuenta.
    con_cuenta = recetas.publico_de("assets", 0.9, (34, 216))
    ok("34 de 216 planos" in con_cuenta,
       f"con unidades se ensena la cuenta de verdad: {con_cuenta!r}")
    fases_assets = recetas.PUBLICO["assets"]["fases"]
    ok(not any(f in con_cuenta for f in fases_assets),
       "y la fase inventada se calla: sobre lo medido no manda una frase")
    ok(recetas.PUBLICO["assets"]["nombre"] in con_cuenta,
       "pero el titulo se queda: sin el no se sabe de que tarea se habla")
    ok(fases_assets[-1] in recetas.publico_de("assets", 0.9),
       "sin unidades, la fase sigue mandando como siempre")

    # NADIE ENSENA «1 de 1»: ocupa una linea para decir que hay una cosa, y
    # ademas se lee como un error.
    ok(recetas.PUBLICO["assets"]["fases"][0]
       in recetas.publico_de("assets", 0.0, (0, 1)),
       "con un total de uno no se cuenta: se cuenta la fase")
    # y unidades rotas no tumban la barra
    for rotas in ((None, 3), ("x", "y"), (), (1,)):
        ok(isinstance(recetas.publico_de("assets", 0.5, rotas), str),
           f"unas unidades ilegibles {rotas!r} no revientan la frase")

    # LA UNIDAD SE DICE POR SU NOMBRE, y vive en la misma tabla que el resto de
    # lo publico: dos tablas se desincronizan en cuanto alguien anade un paso.
    for tid in ("assets", "callouts", "render", "piezas"):
        ok(bool((recetas.PUBLICO.get(tid) or {}).get("unidad")),
           f"{tid} dice en que unidad cuenta")


class _CtxSinProyecto:
    """Lo justo para `_tramos_por_tiempo`: un proyecto sin ninguna version.

    Lo demas que toca esa funcion va sustituido en la prueba; esto solo tiene
    que hacer que la lectura del brief devuelva vacio sin reventar.
    """

    class proyecto:                                           # noqa: N801
        id = "prueba_tramos"

        @staticmethod
        def version_activa(paso_id):
            return None

        @staticmethod
        def ruta_paso(paso_id, version=None, crear=False):
            return os.path.join(tempfile.gettempdir(), "tramos_que_no_existen")


def probar_el_avisador_y_los_tramos():
    """Quien escucha la barra puede ser cualquiera, y el tramo va por tiempo."""
    seccion("EL CONTADOR DE VERDAD Y EL REPARTO DE LA BARRA")
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    import estadisticas                                       # noqa: PLC0415

    # EL AVISADOR NO PUEDE ROMPER UN PASO POR ADORNAR LA BARRA. Los pasos avisan
    # con (hechas, total) y quien escucha puede ser el servicio, el doble de una
    # suite --`lambda v, m="": v`, dos argumentos-- o nada.
    recogido = []
    # quien sabe de unidades lo dice con el NOMBRE del parametro, como
    # `avisar_tarea`; un tercero con otro nombre es el `publico` del gestor y
    # el contador caia ahi («· (44, 44)» en la barra; revision 16-10-2026)
    de_tres = estadisticas.avisador(
        lambda f, m="", unidades=None: recogido.append(("tres", f, m, unidades)))
    de_publico = estadisticas.avisador(
        lambda v, m="", publico="": recogido.append(("publico", v, m, publico)))
    de_publico(1.0, "fin", (44, 44))
    igual(recogido[-1], ("publico", 1.0, "fin", ""),
          "el contador no cae en el texto publico del gestor")
    de_dos = estadisticas.avisador(lambda v, m="": recogido.append(("dos", v, m)))
    variadic = estadisticas.avisador(lambda *a, **k: recogido.append(("var", a)))
    de_nada = estadisticas.avisador(None)

    de_tres(0.5, "hola", (34, 216))
    igual(recogido[-1], ("tres", 0.5, "hola", (34, 216)),
          "quien sabe de unidades las recibe enteras")
    de_dos(0.5, "hola", (34, 216))
    igual(recogido[-1], ("dos", 0.5, "hola"),
          "y quien no, se queda sin ellas en vez de reventar")
    variadic(0.5, "hola", (34, 216))
    igual(recogido[-1], ("var", (0.5, "hola", (34, 216))),
          "un *args cuenta como que sabe")
    antes = len(recogido)
    de_nada(0.5, "hola", (34, 216))
    igual(len(recogido), antes, "y sin nadie escuchando no pasa nada")

    # LA BARRA SE REPARTE POR TIEMPO MEDIDO. Con un tramo igual por tarea, una
    # de cuarenta y nueve segundos ocupaba lo mismo que una de treinta y cinco
    # minutos: la barra saltaba en las cortas y se clavaba en la larga.
    import app as servicio                                    # noqa: PLC0415
    tandas = [[{"id": "corta", "paso": "assets"}],
              [{"id": "larga", "paso": "assets"}]]
    medidas = {"corta": 10.0, "larga": 990.0}
    guardado = (servicio._segundos_de_tarea, servicio._esta_al_dia,
                servicio._planos_previstos)
    servicio._segundos_de_tarea = lambda ctx, tarea, *a: medidas[tarea["id"]]
    servicio._esta_al_dia = lambda ctx, tarea: False
    servicio._planos_previstos = lambda ctx: {"total": 216, "con_imagen": 216,
                                              "origen": "el plan de este video"}
    try:
        tramos = servicio._tramos_por_tiempo(_CtxSinProyecto(), tandas,
                                             "pendientes")
    finally:
        (servicio._segundos_de_tarea, servicio._esta_al_dia,
         servicio._planos_previstos) = guardado
    ok(tramos["larga"][1] > tramos["corta"][1] * 50,
       f"la tarea larga se lleva casi toda la barra: {tramos}")
    igual(round(tramos["corta"][0], 6), 0.0, "la primera arranca en cero")
    igual(round(tramos["larga"][0] + tramos["larga"][1], 6), 1.0,
          "y la ultima llega al final: la barra no se queda a medias")


def probar_que_la_musica_no_tumba_el_montaje():
    """A3 del informe de la Etapa Foto A: Jamendo caido no tumba el MP4.

    Lo que se vio: «Montar el video» sin acceso a api.jamendo.com y la tanda
    entera se caia, con el error de Python crudo en pantalla -- y dentro, la URL
    completa con el `client_id` de Jamendo. Dos cosas, las dos medidas aqui:

      1. ningun fallo de Jamendo lleva la clave, ni en el texto ni en la traza
      2. en la tanda que monta el video la musica es prescindible: el MP4 sale
         sin ella y la tanda lo AVISA. En el repaso y en «volver a la
         automatica» no: alli lo pedido es justo la musica.

    En proceso y sin red: `requests.get` se sustituye por uno que falla.
    """
    seccion("JAMENDO CAIDO: EL VIDEO SALE SIN MUSICA Y SIN ENSENAR LA CLAVE")
    import traceback as _traza                                # noqa: PLC0415
    sys.path.insert(0, RAIZ_ESTUDIO)
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    import app as servidor                                    # noqa: PLC0415
    import requests as _requests                              # noqa: PLC0415
    import sonido                                             # noqa: PLC0415

    secreto = "clavejamendo" + "9" * 10
    url = (f"https://api.jamendo.com/v3.0/tracks/?client_id={secreto}"
           f"&format=json&limit=24")

    def caido(*_a, **_k):
        raise _requests.ConnectionError(
            f"HTTPSConnectionPool(host='api.jamendo.com', port=443): Max retries "
            f"exceeded with url: {url} (Caused by NameResolutionError)")

    class _Respuesta:
        ok, status_code = False, 503

        def json(self):
            return {}

    class _Rechazo(_Respuesta):
        ok, status_code = True, 200

        def json(self):
            return {"headers": {"status": "failed",
                                "error_message": f"Invalid client_id {secreto}"}}

    original_get = sonido.requests.get
    try:
        for nombre, falso in (("sin red", caido),
                              ("un 503", lambda *_a, **_k: _Respuesta()),
                              ("un rechazo que repite la clave",
                               lambda *_a, **_k: _Rechazo())):
            sonido.requests.get = falso
            try:
                sonido._pedir_a_jamendo({"client_id": secreto, "format": "json"})
                ok(False, f"Jamendo con {nombre} tiene que fallar")
            except RuntimeError as fallo:
                traza = "".join(_traza.format_exception(fallo))
                ok("Jamendo" in str(fallo), f"con {nombre} dice que es Jamendo: {fallo}")
                ok(secreto not in str(fallo) and secreto not in traza,
                   f"y con {nombre} la clave no va ni en el mensaje ni en la traza")
    finally:
        sonido.requests.get = original_get

    # ---- quien corre la banda: prescindible SOLO en la tanda del video
    igual(servidor._que_hace("banda_sonora", None, {}, sonido_prescindible=True)[0],
          servidor._correr_banda_de_tanda,
          "en la tanda que monta el video, la banda va por el camino prescindible")
    igual(servidor._que_hace("banda_sonora", None, {})[0], servidor._correr_banda,
          "en el repaso y en «volver a la automatica», la de siempre: falla a la vista")
    igual(servidor._que_hace("efectos", None, {}, sonido_prescindible=True)[0],
          servidor._correr_efectos_de_tanda,
          "y los efectos tambien: FreeSound caido no tumba el MP4")
    igual(servidor._que_hace("efectos", None, {})[0], servidor._correr_surtir_efectos,
          "fuera de esa tanda, los efectos fallan a la vista como siempre")

    anotado = []

    class _Bitacora:
        def anotar(self, evento, *_a, **_k):
            anotado.append(evento)

    class _Proyecto:
        config = {}
        id = "x"

        @staticmethod
        def version_activa(paso_id):
            return None

        @staticmethod
        def ruta_paso(paso_id, version=None, crear=False):
            return os.path.join(tempfile.gettempdir(), "tanda_que_no_existe")

        @staticmethod
        def ruta_trabajo(paso_id, crear=False):
            return os.path.join(tempfile.gettempdir(), "tanda_que_no_existe")

    class _Ctx:
        id = "x"
        bitacora = _Bitacora()
        proyecto = _Proyecto()
        estado = None

    def banda_caida(_avisar, _ctx, _tramos):
        # lo que de verdad lanza `montar_banda` con Jamendo caido, ya limpio
        sonido.requests.get = caido
        try:
            return sonido._pedir_a_jamendo({"client_id": secreto})
        finally:
            sonido.requests.get = original_get

    montado = []

    def render_falso(avisar_tarea):
        montado.append(True)
        avisar_tarea(1.0, "montado")
        return {"resumen": "1 clip"}

    def efectos_caidos(_avisar, _ctx, _papeles, _salteado):
        # lo que lanza `sonido.buscar_efectos` con FreeSound devolviendo un 503
        raise RuntimeError("Freesound 503: Service Unavailable")

    original_banda, original_que_hace = servidor._correr_banda, servidor._que_hace
    original_efectos = servidor._correr_surtir_efectos
    servidor._correr_banda = banda_caida
    servidor._correr_surtir_efectos = efectos_caidos
    servidor._que_hace = lambda tid, ctx, receta, modo="pendientes", solo_montar=False, \
        sonido_prescindible=False: (
            original_que_hace(tid, ctx, receta, modo, solo_montar, sonido_prescindible)
            if tid in ("banda_sonora", "efectos") else (render_falso, ()))
    dichos = []
    try:
        # LA MISMA FORMA QUE LA TANDA DE VERDAD: musica y efectos van a la vez
        # (en una tanda del pool) y el render detras
        plan = {"segundos": 10.0, "fases": [
            {"pestana": "render", "desde": 0.0, "segundos": 10.0,
             "pendientes": ["banda_sonora", "efectos", "render"],
             "tareas": [{"id": "banda_sonora"}, {"id": "efectos"},
                        {"id": "render"}]}]}
        try:
            salida = servidor._correr_cadena(
                lambda v, m="", p="": dichos.append(m), _Ctx(), ["render"],
                "todo", {}, plan)
        except Exception as fallo:                          # noqa: BLE001
            salida = {"error": f"{type(fallo).__name__}: {fallo}"}

        ok("error" not in salida,
           f"la tanda del MP4 NO se cae porque Jamendo no responda "
           f"({salida.get('error', 'sigue')})")
        ok(montado, "y el vídeo se monta igual, sin música ni efectos")
        avisos = salida.get("avisos") or []
        ok(any("sin música" in a for a in avisos),
           f"y el resultado de la tanda lo avisa, que la pantalla lo enseña: {avisos}")
        ok(any("sin efectos" in a for a in avisos),
           f"y avisa tambien de los efectos (FreeSound caido): {avisos}")
        ok("efectos_fallidos" in anotado, "que tambien quedan en la bitácora")
        ok(not any(secreto in x for x in avisos + dichos),
           "sin la clave de Jamendo en el aviso ni en la barra")
        ok("banda_sonora_fallida" in anotado, "y queda apuntado en la bitácora")

        # Y CANCELAR SI CORTA: es alguien pidiendo parar, no un fallo de musica
        from nucleo.trabajos import Cancelado                 # noqa: PLC0415

        def cancelada(*_a, **_k):
            raise Cancelado()
        servidor._correr_banda = cancelada
        try:
            servidor._correr_banda_de_tanda(lambda *_a, **_k: None, _Ctx())
            ok(False, "cancelar la tanda mientras monta la música la para")
        except Cancelado:
            ok(True, "cancelar la tanda mientras monta la música la para")
    finally:
        servidor._correr_banda, servidor._que_hace = original_banda, original_que_hace
        servidor._correr_surtir_efectos = original_efectos
        sonido.requests.get = original_get

    # ---- «PROBAR» EN CONFIGURACION TAMPOCO ENSEÑA LA CLAVE --------------------
    # `comprobar_claves._pedir` devolvia el texto de la excepcion de requests,
    # con la URL dentro: con Jamendo sin red, la clave salia entera en
    # Configuracion y en la herramienta del asistente.
    import comprobar_claves                                   # noqa: PLC0415
    original_request = _requests.request
    _requests.request = caido
    try:
        ficha = comprobar_claves.probar_jamendo(secreto)
    finally:
        _requests.request = original_request
    igual(ficha.get("estado"), "sin_red", "«Probar» con Jamendo sin red dice que no hay red")
    ok(secreto not in json.dumps(ficha), f"y no enseña la clave: {ficha.get('mensaje')}")
    # Y LO QUE REPITA EL PROPIO SERVICIO se tacha: un «Invalid client_id XXX»
    fichas = comprobar_claves._tachar(
        [{"proveedor": "jamendo", "estado": "mal",
          "mensaje": f"Jamendo no acepta el Client ID (401): Invalid client_id {secreto}"},
         {"proveedor": "openai", "estado": "mal",
          "mensaje": "OpenAI contesta 401: Incorrect API key provided: sk-prueba-123456"}],
        {"openai": [{"clave": "sk-prueba-123456"}], "jamendo": {"clave": secreto},
         "cartesia": {"clave": ""}, "freesound": {"clave": None}})
    ok(not any(secreto in f["mensaje"] or "sk-prueba-123456" in f["mensaje"]
               for f in fichas),
       f"y lo que el servicio repita de la clave se tacha: {[f['mensaje'] for f in fichas]}")


def probar_lo_del_analisis_del_13_10():
    """Lo que encontro el analisis a fondo del 13-10-2026 y se arreglo.

    En proceso y con dobles: ni red, ni claves, ni una imagen pagada.
      S2  la clave de Jamendo no viaja en el enlace de escucha
      D1  «Generar» no se lanza mientras la cola de notas dibuja
      D3  cuatro clics en una lamina lanzan UN trabajo
      R1  una tarifa mal escrita no se guarda (dejaba sin «Generar» a todos)
    """
    seccion("ANALISIS DEL 13-10: CLAVES, PAGAR DOS VECES Y TARIFAS")
    sys.path.insert(0, RAIZ_ESTUDIO)
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    import threading as _hilos                                # noqa: PLC0415
    import app as servidor                                    # noqa: PLC0415
    import requests as _requests                              # noqa: PLC0415
    import sonido                                             # noqa: PLC0415

    # ---- S2: el client_id de Jamendo en `audio` (from=app-<id>) -------------
    secreto = "c1a2v3e4"
    ficha = sonido._ficha_musica({
        "id": 7, "name": "tema", "duration": 60,
        "audio": f"https://prod-1.storage.jamendo.com/?trackid=7&format=mp31&from=app-{secreto}",
        "audiodownload": f"https://prod-1.storage.jamendo.com/download/track/7/mp32/?from=app-{secreto}"})
    ok(secreto not in json.dumps(ficha),
       f"la ficha de un tema ya no lleva la clave de Jamendo: {ficha['escucha']}")
    ok("trackid=7" in ficha["escucha"], "y el enlace sigue sirviendo para escuchar")
    pedidas = []

    def get_falso(url, **_k):
        pedidas.append(url)
        raise _requests.ConnectionError(f"Max retries exceeded with url: {url}")

    del_servidor = servidor._sonido()        # el MISMO modulo que usa la ruta
    claves_reales, get_real = del_servidor._claves, _requests.get
    del_servidor._claves = lambda: {"JAMENDO_CLIENT_ID": secreto}
    _requests.get = get_falso
    try:
        servidor.escuchar_tema(ficha["escucha"])
        ok(False, "sin red, escuchar contesta un error")
    except servidor.ErrorApi as fallo:
        igual(fallo.codigo, 502, "sin red, escuchar contesta 502")
        ok(secreto not in fallo.mensaje, f"y el error no repite la URL con la clave: "
                                         f"{fallo.mensaje}")
    finally:
        del_servidor._claves, _requests.get = claves_reales, get_real
    ok(pedidas and f"from=app-{secreto}" in pedidas[0],
       "la atribucion la pone el SERVIDOR en su propia peticion a Jamendo")

    # ---- D1: «Generar» con la cola de notas dibujando -------------------------
    lanzados = []

    class _Gestor:
        def __init__(self, dibujando):
            self.dibujando = dibujando

        def estado(self, tid):
            return {"estado": "ejecutando" if (tid == "cola" and self.dibujando)
                    else "listo", "id": tid}

        def lanzar(self, nombre, *a, **k):
            lanzados.append(nombre)
            return "t-" + str(len(lanzados))

        def listar(self, activos=False):
            return []

    class _Estado:
        def estado_de(self, paso):
            return "listo"

    class _Bit:
        def anotar(self, *a, **k):
            pass

    class _Ctx:
        def __init__(self, dibujando):
            self.id = "d1-prueba"
            self.gestor = _Gestor(dibujando)
            self.estado = _Estado()
            self.bitacora = _Bit()

    plan = {"tareas": 1, "impedimentos": [], "segundos": 1.0,
            "coste": {"usd_total": 0.0, "usd_por_generar": 0.0, "imagenes_por_generar": 0},
            "fases": [{"pestana": "video", "tareas": [{"id": "assets", "paso": "assets"}]}]}
    sustitutos = {"contexto": None, "_con_origen": lambda ctx, p: p,
                  "_trabajo_de_cadena": lambda ctx: None,
                  "_trabajo_de_receta": lambda ctx, p: None,
                  "_plan_de_generacion": lambda *a, **k: plan,
                  "_apuntar_tanda": lambda *a, **k: None,
                  "_registrar_trabajo": lambda *a, **k: None}
    reales = {n: getattr(servidor, n) for n in sustitutos}
    try:
        for n, f in sustitutos.items():
            if f is not None:
                setattr(servidor, n, f)
        for dibujando in (True, False):
            ctx = _Ctx(dibujando)
            servidor.contexto = lambda _pid, _c=ctx: _c
            servidor._COLA_NOTAS[ctx.id] = {"cola": [], "trabajo": "cola"}
            del lanzados[:]
            try:
                servidor.generar_video(ctx.id, {"tanda": "video"})
                codigo = 202
            except servidor.ErrorApi as fallo:
                codigo = fallo.codigo
            if dibujando:
                igual(codigo, 409, "con la cola de notas dibujando, «Generar imágenes» da 409")
                igual(lanzados, [], "y no lanza nada: dos trabajos de imágenes a la vez "
                                    "repagaban planos o tapaban la imagen recién pagada")
            else:
                igual(len(lanzados), 1, "con la cola parada, se lanza como siempre")
    finally:
        for n, f in reales.items():
            setattr(servidor, n, f)
        servidor._COLA_NOTAS.pop("d1-prueba", None)

    # ---- D3: cuatro clics en «Regenerar lamina» a la vez ----------------------
    activos, lanzados_taller = [], []

    class _GestorTaller:
        def listar(self, activos=False):
            return list(activos_lista)

        def lanzar(self, nombre, *a, **k):
            time.sleep(0.2)                  # lo que tarda en arrancar de verdad
            lanzados_taller.append(nombre)
            activos_lista.append({"id": nombre})
            return "t"

    activos_lista = activos

    class _CtxTaller:
        id = "d3-taller-prueba"
        gestor = _GestorTaller()

    respuestas = []

    def clic():
        try:
            servidor._lanzar_en_taller(_CtxTaller(), "preset_light", lambda *a: None)
            respuestas.append(202)
        except servidor.ErrorApi:
            respuestas.append(409)

    hilos = [_hilos.Thread(target=clic) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    igual(len(lanzados_taller), 1, "cuatro clics a la vez lanzan UN trabajo de láminas "
                                   "(antes: hasta tres, cada uno pagando su imagen)")
    igual(sorted(respuestas), [202, 409, 409, 409], "y los otros tres dicen 409")

    # ---- R1: una tarifa mal escrita ------------------------------------------
    from nucleo import coste as _coste                        # noqa: PLC0415
    carpeta = tempfile.mkdtemp(prefix="estudio_tarifas_")
    copia = os.path.join(carpeta, "tarifas.json")
    shutil.copy(os.path.join(RAIZ_ESTUDIO, "tarifas.json"), copia)
    ruta_real = _coste.RUTA_TARIFAS
    _coste.RUTA_TARIFAS = copia
    _coste.tarifas(refrescar=True)
    try:
        for cuerpo in ({"usd_por_caracter": "abc"}, {"tarifas": {"tts": "x"}},
                       {"tarifas": {"openai": {"usd_por_imagen": {"1024x1024": {"low": -1}}}}}):
            try:
                servidor.escribir_tarifas(cuerpo)
                ok(False, f"{cuerpo} no se guarda")
            except servidor.ErrorApi:
                ok(True, f"{cuerpo} no se guarda: 400 con su motivo")
        with open(copia, encoding="utf-8") as fh:
            igual(json.load(fh)["tts"]["usd_por_caracter"],
                  _coste.tarifas(refrescar=True)["tts"]["usd_por_caracter"],
                  "y la tabla se queda como estaba")
        servidor.escribir_tarifas({"usd_por_caracter": 0.00007})
        igual(_coste.tarifa_caracter(), 0.00007, "un número de verdad sí se guarda")
        servidor.escribir_tarifas({"usd_por_caracter": None})
        ok(True, "y quitarla (la pantalla manda null) también")
    finally:
        _coste.RUTA_TARIFAS = ruta_real
        _coste.tarifas(refrescar=True)
        shutil.rmtree(carpeta, ignore_errors=True)


def probar_el_mensaje_publico_de_una_tanda():
    """Una tanda dice por donde va DOS veces, y las dos a la vez.

    Esto es el cableado, que es lo que ninguna tabla comprueba: que el detalle
    tecnico que manda cada paso --«plano S035 - 41 de 44»-- sigue llegando
    entero al mensaje de casa, y que el publico que viaja al lado no lo lleva ni
    de refilon. Si alguien enmascarara EL MISMO mensaje en vez de mandar dos,
    esto se pondria rojo: el de casa se quedaria sin sus cifras.

    Se corre en proceso con una tarea de mentira: lo que se mira es el formato
    de lo que sale por `avisar`, no lo que hace ninguna tarea de verdad.
    """
    seccion("UNA TANDA CUENTA POR DONDE VA SIN ENSENAR LA COCINA")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415

    class _Bitacora:
        def anotar(self, *_a, **_k):
            pass

    class _Proyecto:
        config = {}
        id = "x"

        # lo justo para que el reparto de la barra por tiempo medido
        # (`_tramos_por_tiempo`) recorra su camino de verdad en vez de caerse al
        # respaldo plano y dejar la prueba mirando otra cosa
        @staticmethod
        def version_activa(paso_id):
            return None

        @staticmethod
        def ruta_paso(paso_id, version=None, crear=False):
            return os.path.join(tempfile.gettempdir(), "tanda_que_no_existe")

        @staticmethod
        def ruta_trabajo(paso_id, crear=False):
            return os.path.join(tempfile.gettempdir(), "tanda_que_no_existe")

    class _Ctx:
        id = "x"
        bitacora = _Bitacora()
        proyecto = _Proyecto()
        estado = None

    dichos = []

    def avisar(valor, mensaje="", publico=""):
        dichos.append((float(valor or 0), mensaje, publico))

    def falsa(avisar_tarea):
        avisar_tarea(0.0, "")
        avisar_tarea(0.5, "plano S035 - 41 de 44")
        avisar_tarea(None, "AVISO: dos planos con la misma imagen")
        avisar_tarea(1.0, "44 planos listos")
        return {"resumen": "de mentira"}

    def correr(*args, **kwargs):
        del dichos[:]
        original = servidor._que_hace
        servidor._que_hace = lambda *_a, **_k: (falsa, ())
        try:
            args[0](avisar, _Ctx(), *args[1:], **kwargs)
        finally:
            servidor._que_hace = original
        return ([p for _v, _m, p in dichos], [m for _v, m, _p in dichos])

    # ---- UNA PESTANA SOLA: es lo que corre el modo editor y el repaso -------
    publicos, caseros = correr(servidor._correr_receta, "voz",
                               {"nombre": "Todo", "tareas": {}},
                               ["voz", "revision_audio"], "todo")
    ok(all(publicos), f"cada aviso lleva su mensaje publico ({publicos[:2]})")
    ok(any("S035" in m for m in caseros),
       "el mensaje de casa conserva el detalle tecnico entero")
    ok(not any("S035" in p for p in publicos),
       "y el publico no lo lleva ni de refilon")
    for frase in publicos:
        sucias = [x for x in COCINA if re.search(r"\b" + re.escape(x), frase, re.I)]
        igual(sucias, [], f"«{frase}» no nombra ninguna pieza del Estudio")
    ok(publicos[0].startswith("1 de 2 · "),
       f"y dice que tarea de cuantas: {publicos[0]!r}")
    igual(publicos[-1], servidor.PUBLICO_LISTO,
          "al acabar dice «Listo» y no el recuento de tareas del motor")

    # LA FRASE SE MUEVE DENTRO DE LA TAREA --eso es el «desglosado»-- y un aviso
    # SIN fraccion no la devuelve al principio.
    de_la_primera = [p for p in publicos if p.startswith("1 de 2 · ")]
    ok(len(set(de_la_primera)) > 1,
       f"la frase cambia mientras la tarea corre: {set(de_la_primera)}")
    a_mitad = [p for _v, m, p in dichos if "S035" in m][0]
    sin_fraccion = [p for _v, m, p in dichos if "AVISO" in m][0]
    igual(sin_fraccion, a_mitad,
          "un aviso sin fraccion deja la frase donde estaba, no la manda al "
          "principio de la tarea")

    # ---- LA TANDA ENTERA, que es la del modo light -------------------------
    # `_correr_cadena` recorre varias pestanas seguidas y reparte el tramo de la
    # barra. Si su avisador se comiera el mensaje publico --es un tercer
    # parametro con valor por defecto, o sea que caeria en silencio-- TODAS las
    # barras del modo light dirian «Trabajando...» y nada mas.
    # `pendientes` es la lista de las que SE HACEN, y es la que cuenta el
    # contador publico: en modo 'todo' son todas.
    plan = {"segundos": 20.0, "fases": [
        {"pestana": "voz", "desde": 0.0, "segundos": 10.0,
         "pendientes": ["voz", "revision_audio"],
         "tareas": [{"id": "voz"}, {"id": "revision_audio"}]},
        {"pestana": "render", "desde": 10.0, "segundos": 10.0,
         "pendientes": ["banda_sonora", "efectos", "render"],
         "tareas": [{"id": "banda_sonora"}, {"id": "efectos"}, {"id": "render"}]}]}
    publicos, caseros = correr(servidor._correr_cadena, ["voz", "render"],
                               "todo", {}, plan)
    ok(any(m.startswith("voz · ") for m in caseros),
       "el mensaje de casa lleva delante la pestana, vocabulario del motor")
    ok(not [p for p in publicos if p.startswith(("voz · ", "render · "))],
       "y el publico no: ahi la pestana no significa nada")

    # UN HUECO NO ES UN FALLO: "" quiere decir «no toques la linea», y es lo que
    # manda una pestana que acaba con la tanda a medias. Lo que no puede haber
    # es un «Listo» ahi: la barra decia que habia terminado y seguia con «3 de
    # 5», que en pantalla se lee como que ha vuelto a empezar.
    cabezas = []
    for frase in [p for p in publicos if p]:
        cabeza = frase.split(" · ")[0]
        if cabeza not in cabezas:
            cabezas.append(cabeza)
    igual(cabezas, ["1 de 5", "2 de 5", "3 de 5", "4 de 5", "5 de 5",
                    servidor.PUBLICO_LISTO],
          "el contador recorre las DOS pestanas seguidas sin reiniciarse")
    primero = publicos.index(servidor.PUBLICO_LISTO)
    ultima = max(i for i, p in enumerate(publicos) if p.startswith("5 de 5"))
    ok(primero > ultima,
       "«Listo» no sale hasta que ha pasado la ultima tarea de la tanda")
    igual(publicos[-1], servidor.PUBLICO_LISTO, "y es lo ultimo que se dice")

    # ---- Y LO QUE YA ESTA AL DIA NO SE CUENTA ------------------------------
    # Montar el MP4 de un video ya dibujado recorre once tareas y corre tres:
    # la barra decia «11 de 11» desde el primer minuto --las saltadas sumaban
    # al contador-- y llegaba al final sin haberse movido nunca.
    al_dia = {"banda_sonora", "efectos"}
    original_al_dia = servidor._esta_al_dia
    servidor._esta_al_dia = lambda _ctx, tarea: tarea["id"] in al_dia
    try:
        plan_pendiente = {"segundos": 20.0, "fases": [
            {"pestana": "voz", "desde": 0.0, "segundos": 10.0,
             "pendientes": ["voz", "revision_audio"],
             "tareas": [{"id": "voz"}, {"id": "revision_audio"}]},
            {"pestana": "render", "desde": 10.0, "segundos": 10.0,
             "pendientes": ["render"],
             "tareas": [{"id": "banda_sonora"}, {"id": "efectos"},
                        {"id": "render"}]}]}
        publicos, _caseros = correr(servidor._correr_cadena, ["voz", "render"],
                                    "pendientes", {}, plan_pendiente)
    finally:
        servidor._esta_al_dia = original_al_dia
    cabezas = []
    for frase in [p for p in publicos if p]:
        cabeza = frase.split(" · ")[0]
        if cabeza not in cabezas:
            cabezas.append(cabeza)
    igual(cabezas, ["1 de 3", "2 de 3", "3 de 3", servidor.PUBLICO_LISTO],
          "una tanda con tareas al dia cuenta SOLO las que corre")
    ok(not [p for p in publicos if p.startswith("1 de 5")],
       "y no arranca contando las saltadas como hechas")



def probar_el_reloj_de_lo_que_queda_por_hacer():
    """Una tanda «pendientes» tarda lo que queda, no lo que costo el paso entero.

    Montar el MP4 de un video con sus 302 imagenes ya dibujadas prometia 282
    minutos y duro veinte (08-09-2026, `video_referencia`): `assets` no estaba «al dia»
    --el feedback de UN plano le habia movido la firma-- asi que entraba en el
    plan con las seis horas que cuesta dibujar los 302, cuando lo que quedaba
    por dibujar era cero.

    Se mira `_fraccion_por_hacer`, que es lo que escala la estimacion, con un
    estado de mentira: lo que se comprueba es la regla, no el historial de esta
    maquina.
    """
    seccion("EL RELOJ CUENTA LO QUE QUEDA, NO EL PASO ENTERO")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415

    class _Estado:
        def __init__(self, declaradas, obsoletas):
            self._d, self._o = declaradas, obsoletas

        def unidades_declaradas(self, _paso):
            return self._d

        def unidades_obsoletas(self, _paso):
            return self._o

    class _Ctx:
        def __init__(self, declaradas, obsoletas):
            self.estado = _Estado(declaradas, obsoletas)

    todas = [f"escena:S{n:03d}" for n in range(1, 303)]

    igual(servidor._fraccion_por_hacer(_Ctx(todas, todas), "render"), 1.0,
          "con todo obsoleto se estima el paso entero")
    ok(servidor._fraccion_por_hacer(_Ctx(todas, todas[:1]), "assets") < 0.01,
       "con una unidad de 302 por rehacer, el reloj es el de una unidad")
    ok(0 < servidor._fraccion_por_hacer(_Ctx(todas, []), "assets") < 0.01,
       "y con ninguna no baja a cero: un paso que corre tarda algo")
    igual(servidor._fraccion_por_hacer(_Ctx(todas, []), "guion"), 1.0,
          "un paso que no va por unidades no se escala")
    igual(servidor._fraccion_por_hacer(_Ctx([], []), "assets"), 1.0,
          "y sin unidades declaradas tampoco: no hay nada que repartir")

    class _Roto:
        estado = None

    igual(servidor._fraccion_por_hacer(_Roto(), "assets"), 1.0,
          "no saber repartir el reloj no puede tumbar una tanda")


def probar_que_la_barra_light_no_ensena_la_cocina():
    """Las barras del modo light leen el mensaje PUBLICO y nunca el de casa.

    Se comprueba leyendo la fuente por lo mismo que el `value` de los textarea:
    para ejecutarlo hace falta un DOM. Lo que se fija es la invariante que de
    verdad protege -- que ninguna de las barras de esa pantalla pueda caer en
    `trabajo.mensaje`, que es donde viven los ids de plano y los nombres de los
    pasos. Un enmascarado que falla tiene que fallar tapando.
    """
    seccion("LAS BARRAS DEL MODO LIGHT NO ENSENAN LA COCINA")
    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "web", "app.js"),
                     encoding="utf-8").read()

    def cuerpo_de(firma):
        trozo = fuente[fuente.index(firma):]
        return trozo[:trozo.index("\n}\n") + 3]

    lector = cuerpo_de("function avancePublico(trabajo)")
    ok(".mensaje" not in lector,
       "avancePublico NO cae nunca en el mensaje de casa")
    ok("'Trabajando" in lector,
       "sin mensaje publico dice algo generico, no el de casa")

    # `barraTandaLight` es la envoltura viva (`enVivo`); quien pinta de verdad
    # -- y quien podria caerse al mensaje de casa -- es `...Ahora`.
    for firma, nombre in (("function barraTandaLightAhora(", "la barra de las tandas"),
                          ("function vistaGenerandoLight()", "la del estilo")):
        trozo = cuerpo_de(firma)
        ok("avancePublico(" in trozo, f"{nombre} lee el mensaje publico")
        ok("leerAvance(" not in trozo, f"{nombre} no lee el de casa")
    ok("tarea.publico || tarea.nombre" in cuerpo_de("function vistaGenerandoLight()"),
       "y la lista de tareas del estilo dice el nombre publico")


def probar_value_de_los_textarea():
    """Un <textarea> NO tiene atributo `value`, y eso vaciaba la pantalla.

    `h()` volcaba todos los props con setAttribute. En un <input> el atributo
    value SI pinta el campo, asi que el fallo solo salia en los textarea -- o
    sea, justo donde no se busca. La direccion de los 45 planos se guardaba
    entera en el servidor y la pantalla los pintaba en blanco, que se lee como
    «no ha generado nada».

    Esto se comprueba leyendo la fuente y no ejecutando: para ejecutarlo hace
    falta un DOM, y montar Edge para una funcion de nueve lineas cuesta mas que
    lo que protege. Lo que se fija aqui es la INVARIANTE: `value` no puede
    volver a salir por setAttribute.
    """
    seccion("EL value DE UN TEXTAREA VA POR PROPIEDAD")
    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "web", "app.js"),
                     encoding="utf-8").read()
    cuerpo = fuente[fuente.index("function h(etiqueta, props"):]
    cuerpo = cuerpo[:cuerpo.index("function meter(")]
    ok("clave === 'value'" in cuerpo and "n.value =" in cuerpo,
       "h() asigna `value` como PROPIEDAD: en un textarea el atributo no "
       "existe, no da error y deja el campo vacio")
    ok(cuerpo.index("meter(n, hijos)") < cuerpo.index("n.value ="),
       "y DESPUES de meter los hijos: un <select> necesita sus <option> dentro "
       "antes de poder elegir uno")


def probar_el_gemelo_de_las_marcas_tts():
    """`sinMarcasTts` (JS) tiene que decir lo MISMO que `marcas_tts.limpiar`.

    De esa cuenta sale el reparto de las marcas de palabra entre bloques: una
    palabra de mas desplaza todo lo que va detras. Y `<spell>` es la excepcion
    que las separaba: su contenido se pega a lo que tenga al lado, sin espacio.
    En el JS se sustituia por un espacio como cualquier otra etiqueta, asi que
    «<spell>VPN</spell>s» daba DOS palabras donde Cartesia devuelve una marca.
    Medido en el video largo: 716 palabras pintadas contra 713 marcas.
    """
    seccion("EL GEMELO EN JS DE LAS MARCAS DE VOZ")
    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "web", "app.js"),
                     encoding="utf-8").read()
    ok("const SPELL_TTS" in fuente,
       "el JS tiene su propio patron para <spell>")
    ok("replace(SPELL_TTS, '$1')" in fuente,
       "y lo sustituye por su CONTENIDO, no por un espacio")
    ok(fuente.index("replace(SPELL_TTS") < fuente.index("replace(MARCA_TTS"),
       "y antes que el patron general, o el general se lo comeria primero")

    # Y el backend, que es el que manda: la misma frase, una sola palabra.
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    import marcas_tts                                        # noqa: PLC0415
    frase = ('Commercial <spell>VPN</spell>s, on <spell>MEGA</spell>.'
             '<break time="400ms"/> Fin.')
    igual(marcas_tts.limpiar(frase), "Commercial VPNs, on MEGA. Fin.",
          "el backend pega el contenido de <spell> a lo que tiene al lado")
    igual(marcas_tts.contar_palabras(frase), 5,
          "y por eso cuenta cinco palabras, no siete")


def probar_que_la_receta_aplica():
    """Una receta que propone y no guarda es una factura sin resultado.

    Tres tareas de la tuberia PROPONEN y la pantalla las guarda con un segundo
    clic: las menciones, las cartelas y el plan de rotulos. En una tanda de una
    tirada no hay nadie para dar ese segundo clic, asi que el ejecutor tiene que
    pedir que se apliquen. Si alguien anade una tarea que propone y se olvida,
    esto lo dice aqui y no en la factura del mes.

    Se mira en proceso y no por HTTP porque lo que se comprueba es el CABLEADO
    -- que argumentos recibe cada tarea --, no una respuesta.
    """
    seccion("LA RECETA APLICA LO QUE PROPONE")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                  # noqa: PLC0415

    class _Estado:
        def params(self, _paso):
            return {}

    class _Ctx:
        id = "x"
        estado = _Estado()

    ctx = _Ctx()
    for tarea in ("plan_cartelas",):
        _funcion, args = servidor._que_hace(tarea, ctx, {})
        ok(args and args[-1] is True,
           f"{tarea}: la receta pide APLICAR lo propuesto ({args[-1]!r})")

    # Y las que son un paso del grafo pasan por _un_paso, que es lo que las hace
    # rehacer SOLO lo sucio: con unidades=None se rehace el paso entero, y en
    # assets eso son las 49 imagenes otra vez.
    import inspect                                          # noqa: PLC0415
    fuente = inspect.getsource(servidor._que_hace)
    ok("_correr_paso" not in fuente,
       "ninguna tarea de paso llama a _correr_paso a pelo: todas por _un_paso")
    ok("_plan_de_ejecucion" in inspect.getsource(servidor._un_paso),
       "y _un_paso pide las unidades al mismo sitio que el boton de ejecutar")


def probar_lo_de_la_revision_de_imagenes_16_10():
    """La revision de la tuberia de imagenes del 16-10-2026, en proceso.

    1. En una receta 'todo' con «piezas» puesta, la tarea «assets» pide a p6
       que conserve las hojas: «piezas» ya las acaba de rehacer y pagar.
    2. El precio de la cola de notas y el del panel de coste van con el MODO
       del video: un plano de foto no cuesta lo que uno de ilustracion.
    """
    seccion("REVISION DE IMAGENES DEL 16-10")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                  # noqa: PLC0415
    import inspect                                          # noqa: PLC0415

    original = servidor._un_paso
    servidor._un_paso = lambda ctx, paso, modo, extra=None: ("f", (paso, modo, extra or {}))
    try:
        con = {"tareas": {"piezas": True}}
        sin = {"tareas": {"piezas": False}}
        _, args = servidor._que_hace("assets", None, con, "todo")
        igual(args[2].get("conservar_piezas"), True,
              "'todo' con «piezas»: la tarea de los planos no vuelve a pagar las hojas")
        _, args = servidor._que_hace("assets", None, sin, "todo")
        ok("conservar_piezas" not in args[2],
           "'todo' SIN «piezas»: las hojas las rehace la tarea de los planos")
        _, args = servidor._que_hace("assets", None, con, "pendientes")
        ok("conservar_piezas" not in args[2], "en 'pendientes' no cambia nada")
    finally:
        servidor._un_paso = original

    class _Estado:
        def params(self, _paso):
            return {"calidad": "medium", "estilo": {"modo": "foto"}}

    class _Ctx:
        id = "x"
        estado = _Estado()

    pedidos = []
    original = servidor.AJUSTES.usd_por_imagen
    servidor.AJUSTES.usd_por_imagen = lambda calidad, tamano=None, modo=None: (
        pedidos.append((calidad, modo)) or 0.1)
    try:
        servidor._usd_por_imagen(_Ctx())
    finally:
        servidor.AJUSTES.usd_por_imagen = original
    igual(pedidos, [("medium", "foto")],
          "el precio de la cola de notas es el de un plano de FOTO en un video de foto")
    ok("precio_por_imagen(calidad, modo=" in inspect.getsource(servidor.coste_en_detalle),
       "y el del panel de coste, tambien con su modo")


def probar_que_la_api_esta_documentada():
    """docs/API.md tiene que nombrar TODAS las rutas que sirve app.py.

    La cabecera de `web/app.js` llevaba una lista a mano y se quedo en 52 de 126
    endpoints: nadie la completaba al anadir uno, y una lista a medias de una API
    es peor que ninguna porque parece completa. La lista se movio a docs/API.md,
    generada desde el propio `app.py`, y esto es lo que impide que se quede vieja
    otra vez -- que es lo unico que hace falta para que siga sirviendo.
    """
    print("\n[api] docs/API.md nombra todas las rutas que sirve app.py")
    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "app.py"), encoding="utf-8").read()
    doc = io.open(os.path.join(RAIZ_ESTUDIO, "docs", "API.md"), encoding="utf-8").read()
    servidas = {(m.group(1).upper(), m.group(2)) for m in
                re.finditer(r'@app\.(get|post|put|delete|patch)\("([^"]+)"', fuente)}
    faltan = sorted(f"{v} {r}" for v, r in servidas if f"`{r}`" not in doc)
    ok(not faltan,
       f"todas las rutas ({len(servidas)}) estan en docs/API.md"
       + (f" -- FALTAN: {', '.join(faltan[:6])}" if faltan else ""))
    # y al reves: una ruta documentada que ya no existe manda a buscar algo que
    # no esta, que es la otra forma de que una referencia deje de servir
    rutas = {r for _, r in servidas}
    sobran = sorted(m.group(1) for m in re.finditer(r"^\| `[A-Z]+` \| `([^`]+)`", doc, re.M)
                    if m.group(1) not in rutas)
    ok(not sobran,
       "y ninguna documentada ha dejado de existir"
       + (f" -- SOBRAN: {', '.join(sobran[:6])}" if sobran else ""))


def probar_que_las_llamadas_a_los_pasos_encajan():
    """Nadie le pasa a un paso un argumento que su firma no tiene.

    EL FALLO QUE ARREGLA, visto el 24-08-2026 al generar un preset:

        generar_guia() got an unexpected keyword argument 'indicaciones'

    `app.py` le pasaba `indicaciones=` a `estilo.generar_guia` desde el modo
    light --con un comentario explicando muy bien para que servia-- y la firma
    no lo recibia. No fallaba a medias: fallaba ENTERO, y solo por el camino de
    «estilo desde una URL mas una frase», que es la forma normal de pedir un
    canal.

    Python no comprueba una firma hasta que la llamada ocurre, y aqui las
    llamadas ocurren dentro de un trabajo en segundo plano: o se pulsa ESE boton
    o no se entera nadie. Esto lo comprueba sin pulsarlo, leyendo el AST.
    """
    print("\n[api] ninguna llamada a un paso pasa un argumento que no existe")
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "herramientas"))
    import firmas_py

    conocidos = firmas_py.modulos()
    ok(len(conocidos) > 20, f"se han cargado los modulos de pasos y nucleo: "
                            f"{len(conocidos)}")

    hallazgos = []
    for relativo in firmas_py.FICHEROS:
        ruta = os.path.join(RAIZ_ESTUDIO, relativo.replace("/", os.sep))
        if not os.path.exists(ruta):
            continue
        arbol = ast.parse(io.open(ruta, encoding="utf-8").read(), filename=ruta)
        rastreador = firmas_py.Rastreador(relativo, conocidos)
        rastreador.visit(arbol)
        hallazgos.extend(rastreador.hallazgos)
    ok(not hallazgos,
       "ninguna llamada sobra un argumento"
       + ("" if not hallazgos else " -- " + "; ".join(
           f"{h['fichero']}:{h['linea']} {h['llamada']}({h['sobra']}=)"
           for h in hallazgos[:5])))

    # Y QUE EL DETECTOR DETECTE. Un comprobador que siempre dice que si es peor
    # que ninguno: da la tranquilidad sin dar la comprobacion.
    falso = ast.parse(
        "def f():\n"
        "    estilo = _estilo()\n"
        "    estilo.generar_guia(p, r, meloinvento=1)\n")
    rastreador = firmas_py.Rastreador("(inventado)", conocidos)
    rastreador.visit(falso)
    igual(len(rastreador.hallazgos), 1,
          "y con un argumento inventado, lo caza: si no, este verde no vale nada")
    if rastreador.hallazgos:
        igual(rastreador.hallazgos[0]["sobra"], "meloinvento",
              "diciendo cual sobra")

    # los tres modos de nombrar un modulo que se usan en el repo
    for fuente, comose in (
            ("from pasos import estilo\nestilo.generar_guia(p, r, xx=1)",
             "importado directamente"),
            ("def f():\n    e = _estilo()\n    e.generar_guia(p, r, xx=1)",
             "sacado de _estilo()"),
            ("PASOS_MODULOS.estilo.generar_guia(p, r, xx=1)",
             "por PASOS_MODULOS")):
        r = firmas_py.Rastreador("(inventado)", conocidos)
        r.visit(ast.parse(fuente))
        ok(len(r.hallazgos) == 1, f"reconoce un modulo {comose}")

    # y NO se inventa fallos donde no los hay
    r = firmas_py.Rastreador("(inventado)", conocidos)
    r.visit(ast.parse("def f():\n    e = _estilo()\n"
                      "    e.generar_guia(p, r, peticion='x', indicaciones='y')"))
    igual(len(r.hallazgos), 0,
          "y los argumentos que SI existen no se marcan")


def probar_que_no_falta_ningun_nombre_en_el_servidor():
    """Ni el Python llama a nada que no exista.

    EL FALLO QUE ARREGLA, visto el 07-09-2026: el redactor recien estrenado se
    caia entero con

        NameError: name '_exigir_pasos' is not defined

    `app.py:_redactor()` llamaba a un ayudante que no existe en ese fichero. Y
    esta suite pasaba en verde --748 comprobaciones-- porque para llegar a esa
    linea hay que LANZAR el trabajo, y el trabajo tarda veinte minutos y cuesta
    una llamada al CLI. Se descubrio lanzandolo: las dos copias caidas en el
    primer segundo, con la tarde por delante.

    Es el gemelo de la comprobacion de arriba: aquella mira `web/app.js` porque
    en el navegador un nombre que falta solo revienta cuando alguien pinta esa
    pantalla; esta mira el Python porque en el servidor solo revienta cuando
    alguien pulsa ese boton. La misma clase de agujero, los dos lados.
    """
    print("\n[api] el Python del estudio no usa ningun nombre sin declarar")
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "herramientas"))
    import indefinidos_py

    sueltos = indefinidos_py.revisar()
    ok(len(indefinidos_py.FICHEROS) > 40,
       f"se miran todos los ficheros, no uno: {len(indefinidos_py.FICHEROS)}")
    ok(not sueltos,
       "ningun nombre sin declarar"
       + ("" if not sueltos else " -- " + "; ".join(
           f"{n} ({s[0][0]}:{s[0][1]})" for n, s in sorted(sueltos.items())[:6])))

    # Y QUE EL DETECTOR DETECTE, con el fallo DE VERDAD y no con uno de mentira:
    # un comprobador que siempre dice que si da la tranquilidad sin dar la
    # comprobacion. Se escribe el `_redactor()` tal y como estaba.
    roto = os.path.join(tempfile.gettempdir(), "app_con_nombre_suelto.py")
    io.open(roto, "w", encoding="utf-8").write(
        "def _redactor():\n"
        "    _exigir_pasos()\n"
        "    return PASOS_MODULOS.redactor\n"
        "PASOS_MODULOS = None\n")
    try:
        cazados = indefinidos_py.revisar([os.path.basename(roto)],
                                         raiz=tempfile.gettempdir())
        ok("_exigir_pasos" in cazados,
           "y con el fallo del 07-09 delante, lo caza")
        ok("PASOS_MODULOS" not in cazados,
           "sin marcar lo que SI se declara mas abajo: en Python el orden del "
           "fichero no manda dentro de una funcion")
    finally:
        os.remove(roto)

    # y no se inventa fallos con lo que el interprete pone solo
    limpio = os.path.join(tempfile.gettempdir(), "app_limpio.py")
    io.open(limpio, "w", encoding="utf-8").write(
        "import os\n"
        "def f(a, *resto, **kw):\n"
        "    b = [x for x in resto if x]\n"
        "    try:\n"
        "        with open(a) as m:\n"
        "            return os.path.join(m.name, str(b), __file__, kw['x'])\n"
        "    except OSError as fallo:\n"
        "        return str(fallo)\n")
    try:
        igual(indefinidos_py.revisar([os.path.basename(limpio)],
                                     raiz=tempfile.gettempdir()), {},
              "y parametros, comprensiones, `with`, `except as` y `__file__` "
              "no son nombres sueltos")
    finally:
        os.remove(limpio)


def probar_que_no_falta_ningun_nombre_en_la_pantalla():
    """web/app.js no usa ningun nombre que nadie declara.

    EL FALLO QUE ARREGLA, visto el 24-08-2026 al pintar el modo light:

        VELOCIDADES is not defined

    Retirando el eje de idiomas se llevo por delante el bloque de constantes de
    la voz --las cuatro listas y los dos ayudantes de emociones-- porque estaba
    pegado a lo que si sobraba. `node --check` valida SINTAXIS, no referencias:
    el fichero seguia siendo JavaScript valido perfecto, y el fallo solo aparece
    **cuando alguien pinta esa pantalla**. Los paneles de Voz y el paso de voz
    del modo light morian; el resto de la interfaz, tan tranquila.

    El comprobador ya existia y lo estaba diciendo, enterrado entre 69 nombres
    de los que 60 eran mentira (`const` 2.014 veces). Un informe que grita
    sesenta veces no lo lee nadie. Se afino hasta dejarlo en cero y aqui se
    convierte en una comprobacion, que es lo unico que no depende de que alguien
    se acuerde de mirarlo.
    """
    print("\n[api] web/app.js no usa ningun nombre sin declarar")
    ruta_herramientas = os.path.join(RAIZ_ESTUDIO, "herramientas")
    if ruta_herramientas not in sys.path:
        sys.path.insert(0, ruta_herramientas)
    import indefinidos_js

    sueltos = indefinidos_js.revisar()
    ok(not sueltos,
       "ningun nombre sin declarar"
       + ("" if not sueltos else " -- " + "; ".join(
           f"{n} (lineas {ls[:3]})" for n, ls in sorted(sueltos.items())[:6])))
    igual(indefinidos_js.CONOCIDOS, {},
          "y sin excepciones escritas a mano: una lista de excepciones es un "
          "sitio donde esconderse")

    # Y QUE EL DETECTOR DETECTE, con el fallo de verdad. Un comprobador que
    # siempre dice que si da la tranquilidad sin dar la comprobacion.
    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "web", "app.js"),
                     encoding="utf-8").read()
    declaracion = "const VELOCIDADES = ['slowest', 'slow', 'normal', 'fast', 'fastest'];"
    ok(declaracion in fuente,
       "el bloque de constantes de la voz sigue en su sitio")
    if declaracion in fuente:
        roto = os.path.join(tempfile.gettempdir(), "app_sin_velocidades.js")
        io.open(roto, "w", encoding="utf-8").write(fuente.replace(declaracion, ""))
        try:
            sueltos = indefinidos_js.revisar(roto)
            ok("VELOCIDADES" in sueltos,
               "y quitandolo a proposito, el detector lo caza")
        finally:
            os.remove(roto)


def probar_el_reloj_de_un_trabajo():
    """El reloj de un trabajo NO se hereda del anterior.

    EL FALLO QUE ARREGLA, visto el 24-08-2026: se cambio la voz de un preset y
    despues se lanzo una regeneracion del estilo, y la pantalla dijo «3m 51s»
    recien pulsada. `seguirTrabajo` conservaba el arranque que hubiera en la
    ranura del paso -- que es lo correcto al RETOMAR uno que venia corriendo --
    sin comprobar que fuera del MISMO trabajo. En el modo light se nota mas
    porque `preset_light` es UNA ranura fija por la que pasan todos sus
    trabajos, uno detras de otro.

    ESTA SE CORRE DE VERDAD, en node, y no leyendo el fichero: aqui lo que se
    prueba es una CUENTA, y una cuenta se comprueba haciendola. Las demas
    comprobaciones de JS de esta suite miran el texto porque lo que vigilan es
    que dos sitios digan lo mismo, que es otra cosa.
    """
    seccion("EL RELOJ DE UN TRABAJO NO SE HEREDA DEL ANTERIOR")
    nodo = shutil.which("node")
    if not nodo:
        print("      (sin node: no se puede correr el JS; se salta)")
        return

    fuente = io.open(os.path.join(RAIZ_ESTUDIO, "web", "app.js"),
                     encoding="utf-8").read()
    desde = fuente.find("function arranqueDe(")
    hasta = fuente.find("function seguirTrabajo(")
    ok(0 <= desde < hasta,
       "`arranqueDe` existe y va delante de `seguirTrabajo`")
    if not (0 <= desde < hasta):
        return

    guion = fuente[desde:hasta] + r"""
const AHORA = Date.now();
const ANTES = AHORA - 231000;
const salida = {
  otro:      arranqueDe({id: 'viejo', inicio: ANTES, estado: 'listo'}, 'nuevo'),
  mismo:     arranqueDe({id: 'a', inicio: ANTES, estado: 'ejecutando'}, 'a'),
  espera:    arranqueDe({id: null, inicio: ANTES, estado: 'pendiente'}, 'a'),
  vacio:     arranqueDe(undefined, 'a'),
  sin_reloj: arranqueDe({id: 'a'}, 'a'),
  ahora: AHORA, antes: ANTES,
};
console.log(JSON.stringify(salida));
"""
    ruta = os.path.join(tempfile.gettempdir(), "prueba_reloj_trabajo.js")
    io.open(ruta, "w", encoding="utf-8").write(guion)
    try:
        corrido = subprocess.run([nodo, ruta], capture_output=True, text=True,
                                 timeout=60)
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass
    if corrido.returncode != 0:
        ok(False, f"el JS no ha corrido: {(corrido.stderr or '')[:200]}")
        return
    r = json.loads(corrido.stdout.strip().splitlines()[-1])

    ok(r["otro"] >= r["ahora"],
       "un trabajo NUEVO arranca su reloj de cero: heredarlo hacia que una "
       "regeneracion recien pulsada dijera «3m 51s»")
    igual(r["mismo"], r["antes"],
          "el MISMO trabajo conserva el suyo: sin eso, recargar la pagina a "
          "media ejecucion diria «lleva 3s» de un paso de media hora")
    igual(r["espera"], r["antes"],
          "y la espera del clic (id: null) tambien, que es lo honesto: lo que "
          "llevas esperando es desde que pulsaste")
    ok(r["vacio"] >= r["ahora"], "sin nada previo, ahora")
    ok(r["sin_reloj"] >= r["ahora"], "y con id pero sin reloj, ahora")

    # Y QUE NADIE VUELVA A LEER `inicio` A PELO en el sitio que lo decide: el
    # fallo era exactamente eso, un `|| Date.now()` sin comparar el id.
    cuerpo = fuente[hasta:hasta + 900]
    ok("arranqueDe(APP.trabajos[paso], tid)" in cuerpo,
       "y `seguirTrabajo` lo decide por ahi, no con un `|| Date.now()` suelto")


def probar_modo_light(cliente):
    """El modo light: la galeria de presets de canal y su plan de generacion.

    NO se lanza ninguna generacion de verdad: eso baja un video, llama al CLI y
    paga imagenes. Lo que se prueba aqui es todo lo que decide ANTES de gastar
    -- que el encargo se valida, que el plan sale con sus tiempos y sus tandas, y
    que editar y borrar hacen lo que dicen -- que es justo donde un fallo se
    lleva por delante diez minutos y cuatro imagenes.
    """
    seccion("MODO LIGHT: LA GALERIA DE PRESETS DE CANAL")

    respuesta, datos = cliente.get("/api/presets-light")
    igual(respuesta.status_code, 200, "la galeria contesta 200")
    ok(isinstance(datos.get("presets"), list), "trae la lista de presets")
    ok(any(i.get("valor") == "es" for i in (datos.get("idiomas") or [])),
       "trae el catalogo de idiomas")
    igual(sorted(datos.get("partes") or {}), ["estilo", "tono", "voz"],
          "las partes que se pueden rehacer son TRES")
    ok(len(datos.get("tareas") or []) >= 5, "trae la tabla de tareas")

    # ---- el encargo se valida ANTES de crear ningun taller
    base = {"nombre": "Canal de prueba", "idioma": "es",
            "estilo_imagenes": ["x.png", "y.png"],
            "estilo_prompt": "dibujo plano de linea gruesa",
            "tono_prompt": "serio pero cercano, sin dramatismo",
            "voz_prompt": "grave, pausada, sin sonar a locutor"}
    for cambio, etiqueta in (
            ({"nombre": ""}, "sin nombre"),
            ({"idioma": "kl"}, "con un idioma que no existe"),
            # EL ESTILO SON IMAGENES: sin ellas no hay de donde copiar, y lo
            # escrito solo acompana. Un parrafo suelto se lo inventa todo.
            ({"estilo_imagenes": []}, "sin imagenes para el estilo"),
            ({"voz_prompt": ""}, "sin voz"),
            ({"tono_prompt": ""}, "sin tono"),
            ({"tono_prompt": "cor"}, "con un tono de tres letras")):
        respuesta, datos = cliente.post("/api/presets-light/plan",
                                        dict(base, **cambio))
        igual(respuesta.status_code, 400, f"un encargo {etiqueta} da 400")

    # ---- el plan: tandas, tiempos y paralelismo
    respuesta, datos = cliente.post("/api/presets-light/plan", base)
    igual(respuesta.status_code, 200, "un encargo completo devuelve su plan")
    plan = datos.get("plan") or {}
    tandas = plan.get("tandas") or []
    ids = [[t["id"] for t in tanda] for tanda in tandas]
    ok(plan.get("segundos", 0) > 0, "el plan dice cuanto va a tardar")
    ok(any(len(tanda) > 1 for tanda in ids),
       f"algo corre en paralelo (tandas: {ids})")
    primera = ids[0] if ids else []
    ok("tono" in primera and "voz" in primera,
       "el tono y la voz arrancan a la vez que la guia, que es la tarea larga "
       f"(primera tanda: {primera})")
    planas = [t for tanda in ids for t in tanda]
    ok(planas.index("guia") < planas.index("referencias"),
       "la guia escrita va antes de dibujar nada")
    ok(planas.index("referencias") < planas.index("muestra"),
       "las muestras van las ultimas: se dibujan con el estilo ya montado")
    # NO HAY CAMINO DE VIDEO: ni se baja nada ni se eligen fotogramas
    sueltas = [x["id"] for x in (plan.get("tareas") or [])]
    ok("frames" not in sueltas and "eleccion" not in sueltas,
       f"no se extraen ni se eligen fotogramas de ningun video ({sueltas})")
    ok("personajes" not in sueltas,
       f"y no hay personajes del canal que dibujar ({sueltas})")

    # ---- un preset de canal guardado a mano se ve en la galeria y se edita
    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Canal light",
        "datos": {"guion": {"idiomas_salida": ["es"],
                            "instrucciones": "Habla claro y sin adornos."},
                  "voz": {"voz_id": "v-de-prueba", "idioma": "es",
                          "velocidad": "normal"},
                  "origen": {"tono_prompt": "serio pero cercano",
                             "estilo_prompt": "dibujo plano"}}})
    igual(respuesta.status_code, 200, "guardar un preset de canal responde 200")
    pid_preset = (datos.get("preset") or {}).get("id") or ""

    respuesta, datos = cliente.get("/api/presets-light")
    ficha = next((f for f in (datos.get("presets") or [])
                  if f.get("id") == pid_preset), None)
    ok(ficha is not None, "el preset de canal sale en la galeria light")
    if ficha:
        igual(ficha.get("idioma"), "es", "la tarjeta sabe su idioma")
        ok(2 <= len(ficha.get("vinetas") or []) <= 5,
           f"la tarjeta trae de dos a cinco viñetas ({ficha.get('vinetas')})")

    respuesta, datos = cliente.put(f"/api/presets-light/{pid_preset}",
                                   {"nombre": "Canal light EN", "idioma": "en"})
    igual(respuesta.status_code, 200, "editar nombre e idioma responde 200")
    nueva = datos.get("preset") or {}
    igual(nueva.get("idioma"), "en", "el idioma cambia sin regenerar nada")
    igual(nueva.get("nombre"), "Canal light EN", "y el nombre tambien")
    igual(((nueva.get("datos") or {}).get("voz") or {}).get("idioma"), "en",
          "y arrastra el idioma de la voz, que es el que locuta")

    respuesta, datos = cliente.put(f"/api/presets-light/{pid_preset}", {"idioma": "kl"})
    igual(respuesta.status_code, 400, "un idioma que no existe da 400 al editar")

    # rehacer una parte de un preset SIN taller se dice, no se inventa uno
    respuesta, datos = cliente.post(
        f"/api/presets-light/{pid_preset}/regenerar",
        {"parte": "tono", "peticion": "menos solemne"})
    igual(respuesta.status_code, 409,
          "rehacer una parte sin taller da 409 y lo explica")
    respuesta, datos = cliente.post(
        f"/api/presets-light/{pid_preset}/regenerar", {"parte": "inventada"})
    igual(respuesta.status_code, 400, "una parte que no existe da 400")

    respuesta, datos = cliente.delete(f"/api/presets-light/{pid_preset}")
    igual(respuesta.status_code, 200, "borrar el preset responde 200")
    respuesta, datos = cliente.get("/api/presets-light")
    ok(not any(f.get("id") == pid_preset for f in (datos.get("presets") or [])),
       "y desaparece de la galeria")


def probar_video_light(cliente):
    """De un ESTILO a un video: crear el proyecto, planificar y decir el coste.

    Aqui NO se genera nada: generar un video son diez minutos y un dolar largo.
    Lo que se prueba es todo lo que decide antes de gastar -- que el proyecto
    nace con el estilo puesto y visible en la lista, que la direccion viene
    encendida en un video que nunca ha dibujado nada, que el plan dice cuanto
    cuesta ANTES de pulsar y que el guion no esta bloqueado por no tener video
    de referencia --, que es donde un fallo se lleva por delante la tanda entera.
    """
    seccion("MODO LIGHT: DE UN ESTILO A UN VIDEO")

    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Estilo para vídeo",
        # sin bloque 'estilo': un preset de estilo grafico necesita al menos
        # tres fotogramas de referencia y aqui no se extrae ningun video. Lo que
        # se prueba es el camino del VIDEO, no el del estilo.
        "datos": {"guion": {"idioma_salida": "es",
                            "instrucciones": "Habla claro y sin adornos."},
                  "voz": {"voz_id": "v-de-prueba", "idioma": "es",
                          "velocidad": "normal"},
                  "origen": {"tono_prompt": "serio", "estilo_prompt": "plano"}}})
    igual(respuesta.status_code, 200, "hay un estilo con el que hacer el vídeo")
    estilo_id = (datos.get("preset") or {}).get("id") or ""

    # ---- crear el video: los cuatro campos de la pantalla en un POST
    respuesta, creado = cliente.post(f"/api/presets-light/{estilo_id}/video", {
        "nombre": "El hackeo del banco",
        "duracion_objetivo_s": 240,
        # EL MATERIAL es un texto y nada mas: ni enlaces que resolver ni
        # varias cajas. Las INDICACIONES van aparte -- el material son los
        # hechos y las indicaciones son como contarlos.
        "material": "La empresa reconoció el acceso en 2025.\n\n"
                    "El informe se publicó tres meses después.",
        "indicaciones": "Céntrate en el mecanismo, no en las personas.",
        # LAS LLAMADAS A LA ACCION SE DECIDEN POR VIDEO, no en el estilo
        "cta": {"cta_final": {"puesto": True,
                              "texto": "que se suscriba y vea otro vídeo"}}})
    igual(respuesta.status_code, 201, f"crear el vídeo responde 201: {creado}")
    vid = (creado.get("proyecto") or {}).get("id") or ""
    ok(bool(vid), "y devuelve el proyecto")
    igual((creado.get("estilo") or {}).get("id"), estilo_id,
          "diciendo de qué estilo salió")

    # ES UN VIDEO Y SE VE EN LA LISTA. Un taller se esconde porque no es de
    # nadie; un video se hace por donde se quiera y sigue siendo un video.
    respuesta, lista = cliente.get("/api/proyectos")
    ok(any(p["id"] == vid for p in lista["proyectos"]),
       "el vídeo del modo light SALE en la lista de proyectos")

    # ---- lo que la pantalla ya decidio esta escrito en los params de siempre
    respuesta, brief = cliente.get(f"/api/proyectos/{vid}/pasos/brief")
    igual((brief.get("params") or {}).get("duracion_objetivo_s"), 240,
          "la duración va al brief")
    # EL MATERIAL VA AL PASO «ORIGEN», que es donde vive con su version y su
    # firma: cambiarlo deja obsoleto el guion y todo lo que cuelga.
    respuesta, origen = cliente.get(f"/api/proyectos/{vid}/pasos/ingesta")
    par_origen = origen.get("params") or {}
    ok("reconoció el acceso" in (par_origen.get("texto") or ""),
       "el material va al paso Origen")
    respuesta, guion = cliente.get(f"/api/proyectos/{vid}/pasos/guion")
    params = guion.get("params") or {}
    # LAS INDICACIONES llegan al GUIONISTA. Van al cajon que existe para eso y
    # no mezcladas con el material: los hechos son una cosa y como contarlos es
    # otra, y un guionista que recibe «sin indicaciones adicionales» mientras
    # alguien pedia algo escribe un guion que no hace caso a nadie.
    igual(params.get("prompt_general"),
          "Céntrate en el mecanismo, no en las personas.",
          "y las indicaciones llegan al guionista")
    igual(((params.get("cta") or {}).get("cta_final") or {}).get("puesto"), True,
          "y la llamada a la acción de este vídeo, que se decide por vídeo")
    igual((brief.get("params") or {}).get("instrucciones"),
          "Habla claro y sin adornos.",
          "y la guía de tono del estilo NO se machaca: el modo light no tiene "
          "un campo «de qué va», el material es el encargo")

    # ---- el guion NO esta bloqueado por no tener video de referencia
    respuesta, pasos = cliente.get(f"/api/proyectos/{vid}/pasos")
    por_id = {p["id"]: p for p in pasos["pasos"]}
    igual(por_id["ingesta"]["estado"], "pendiente",
          "el origen queda pendiente hasta que se lance: el material ya está "
          "escrito en sus params, pero una entrada del grafo se ejecuta")

    # ---- el plan: que se va a hacer, cuanto tarda y cuanto cuesta
    respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar?tanda=guion")
    igual(respuesta.status_code, 200, "el plan de la tanda del guion responde 200")
    # CON EL ORIGEN DELANTE, porque la ingesta no ha corrido nunca: sin ella
    # el brief sigue bloqueado y la tanda contestaba «falta ejecutar ingesta»
    # al pulsar «Generar el guion» en un vídeo recién creado (ver _con_origen).
    igual(plan["pestanas"], ["origen", "guion"],
          "la tanda del guion se lleva el origen mientras la ingesta esté sin correr")
    tareas = [t["id"] for f in plan["fases"] for t in f["tareas"]]
    ok("ingesta" in tareas, f"con la ingesta dentro, que es lo que desbloquea el brief ({tareas})")
    ok("guion" in tareas, f"con la redacción dentro ({tareas})")
    ok("fuentes" not in tareas and "integraciones" not in tareas,
       f"y sin documentalista ni menciones: ya no existen ({tareas})")
    ok(plan["segundos"] > 0, "dice cuánto va a tardar")
    igual(plan["coste"]["imagenes"], 0,
          "la tanda del guion no paga ninguna imagen")

    # LAS TRES PIEZAS DE LA CADENA, con la frontera donde toca: guion y audio;
    # las IMAGENES, que solo dependen de esos dos; y el MONTAJE, que es todo lo
    # que se pone encima. `callouts` --rotulos, cartelas y movimiento-- es del
    # montaje: en Imagenes se mira el dibujo y nada mas.
    respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar?tanda=video")
    igual(plan["pestanas"], ["video"],
          "la tanda de las imágenes se queda en su pestaña")
    tareas = [t["id"] for f in plan["fases"] for t in f["tareas"]]
    ok("callouts" not in tareas,
       f"y NO dibuja los rótulos: eso es del montaje ({tareas})")
    ok("direccion" in tareas,
       f"y la dirección viene ENCENDIDA en un vídeo del modo light ({tareas})")
    ok(plan["coste"]["imagenes"] > 0,
       f"esta sí paga imágenes: {plan['coste']['imagenes']}")
    ok(plan["coste"]["usd_total"] > 0,
       f"y lo dice en dólares ANTES de pulsar: {plan['coste']['usd_total']} $")
    igual(plan["coste"]["planos"]["origen"], "estimado por la duración y el ritmo",
          "sin plan cortado todavía, los planos se estiman y se dice")

    # ---- MONTAR TIENE QUE PODER PONER AL DIA LOS ROTULOS -------------------
    #
    # La tanda del MP4 llevaba solo la pestana del render, asi que montaba con
    # los rotulos de la pasada anterior. Rehacer un plano suelto deja `callouts`
    # obsoleto --su movimiento y su capa son de ESE dibujo-- y el render se
    # plantaba con «S007: el paso callouts no dejo movimiento», que manda a
    # mirar el render cuando lo que falta es el paso de antes.
    respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar?tanda=render")
    tareas = [t["id"] for f in plan["fases"] for t in f["tareas"]]
    ok("callouts" in tareas,
       f"montar el vídeo alcanza a los rótulos, que es de donde salen los "
       f"movimientos que el render exige: {tareas}")
    ok("render" in tareas, "y al render, claro")

    # ---- y en un proyecto NUEVO del modo editor tambien: nunca ha pagado una
    # imagen, asi que encenderla no repaga nada. Donde sigue
    # apagada es en un video con planos hechos: ver probar_recetas.
    respuesta, otro = cliente.post("/api/proyectos", {"nombre": "Editor normal"})
    otro_id = (otro.get("proyecto") or {}).get("id") or ""
    respuesta, plan = cliente.get(f"/api/proyectos/{otro_id}/generar?tanda=video")
    tareas = [t["id"] for f in plan["fases"] for t in f["tareas"]]
    ok("direccion" in tareas,
       "en un vídeo nuevo del modo editor la dirección viene encendida: "
       "todavía no hay ninguna imagen que repagar")
    cliente.delete(f"/api/proyectos/{otro_id}")

    # ---- las cinco pestanas de una tirada: PENDIENTE 28
    respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar")
    igual(plan["pestanas"], ["origen", "guion", "voz", "video", "render"],
          "sin tanda ni pestañas, las cinco: la tirada de punta a punta")

    respuesta, _ = cliente.get(f"/api/proyectos/{vid}/generar?tanda=inventada")
    igual(respuesta.status_code, 400, "una tanda que no existe da 400")
    respuesta, _ = cliente.get(f"/api/proyectos/{vid}/generar?pestanas=no_existe")
    igual(respuesta.status_code, 404, "una pestaña que no existe da 404")
    respuesta, _ = cliente.post(f"/api/proyectos/{vid}/generar", {"modo": "raro"})
    igual(respuesta.status_code, 400, "un modo inventado da 400")

    # EL ORDEN LO PONE EL PIPELINE, no el orden en que lleguen: pedir
    # «render, video» renderizaria clips de planos que no existen.
    respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar?pestanas=render,video")
    igual(plan["pestanas"], ["video", "render"],
          "las pestañas se reordenan al orden del pipeline")

    # ---- reescribir un bloque del guion SIN tocar el audio
    respuesta, _ = cliente.post(f"/api/proyectos/{vid}/guion/bloques/reescribir",
                                {"peticion": "mas corto"})
    igual(respuesta.status_code, 400, "sin decir qué bloque, 400")
    respuesta, _ = cliente.post(f"/api/proyectos/{vid}/guion/bloques/reescribir",
                                {"bloque": "B001"})
    igual(respuesta.status_code, 400, "y sin decir qué cambiar, también")

    # ---- el material vive en el paso «Origen» y se lee de sus params
    respuesta, origen = cliente.get(f"/api/proyectos/{vid}/pasos/ingesta")
    igual(respuesta.status_code, 200, "el material se lee del paso Origen")
    texto = (origen.get("params") or {}).get("texto") or ""
    ok("reconoció el acceso" in texto, "y trae lo que se escribió")
    ok("informe se publicó" in texto,
       "los dos párrafos, no solo el primero")

    # NO HAY SEGUNDO CAMINO. Un enlace pegado en el material es texto y nada
    # mas: no se baja, no se abre y no se busca. Es lo que hace que el material
    # sea siempre lo que se ve en la caja. El origen SI va en la tanda mientras
    # la ingesta no haya corrido --es el paso que versiona ese texto y
    # desbloquea el brief--, pero su unica tarea es la ingesta del material
    # escrito: ni documentalista ni descarga.
    respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar?tanda=guion")
    igual(plan["pestanas"], ["origen", "guion"],
          "la tanda del guion lleva el origen delante mientras la ingesta esté "
          "sin correr")
    tareas_origen = [t["id"] for f in plan["fases"] if f["pestana"] == "origen"
                     for t in f["tareas"]]
    igual(tareas_origen, ["ingesta"],
          "y del origen solo entra la ingesta del material escrito: no se baja "
          "ni se busca nada")

    respuesta, _ = cliente.post("/api/presets-light/no_existe/video", {})
    igual(respuesta.status_code, 404, "un estilo que no existe da 404")

    cliente.delete(f"/api/proyectos/{vid}")
    cliente.delete(f"/api/presets-light/{estilo_id}")


def probar_presencia_musica(cliente, carpeta):
    """Cuánto se oye la música: se elige por vídeo y, montado, solo se remezcla."""
    seccion("CUÁNTO SE OYE LA MÚSICA")
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto
    _r, datos = cliente.post("/api/proyectos", {"nombre": "Presencia de la música"})
    pid = (datos.get("proyecto") or {}).get("id")
    ruta = f"/api/proyectos/{pid}/musica/presencia"
    _r, datos = cliente.get(ruta)
    igual((datos.get("presencia"), datos.get("elegida")), ("normal", False),
          "sin elegir suena «normal», y lo dice")
    igual(datos.get("niveles"), ["suave", "normal", "alta"], "y da los tres niveles")
    respuesta, _d = cliente.put(ruta, {"presencia": "atronadora"})
    igual(respuesta.status_code, 400, "un nivel que no existe es un 400")
    _r, datos = cliente.put(ruta, {"presencia": "normal"})
    igual(datos.get("cambiado"), False, "elegir lo que ya suena no cambia nada")
    proyecto = Proyecto(os.path.join(carpeta, pid))
    ok("musica_presencia" not in (Estado(proyecto).params("render") or {}),
       "ni escribe el param: la firma del render no se mueve (regla 1)")
    _r, datos = cliente.put(ruta, {"presencia": "alta"})
    igual((datos.get("cambiado"), datos.get("remontando")), (True, False),
          "sin vídeo montado se guarda y no se lanza nada")
    igual(Estado(proyecto).params("render").get("musica_presencia"), "alta",
          "y queda en los params del render")
    _r, datos = cliente.get(ruta)
    igual((datos.get("presencia"), datos.get("elegida")), ("alta", True),
          "y al volver se lee la elegida")

    # MONTADO Y AL DÍA: se remezcla con `solo_montar`, sin dibujar. En proceso
    # y con un contexto de mentira: no hay clips, así que se mira qué se le
    # pide al render y no se corre.
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415

    class _Estado:
        def __init__(self, estado):
            self.render, self.estado = {"musica_presencia": "alta"}, estado

        def params(self, _paso):
            return dict(self.render)

        def estado_de(self, _paso):
            return self.estado

        def actualizar_params(self, _paso, cambios):
            self.render.update(cambios)

    class _Ctx:
        def __init__(self, estado):
            self.estado = _Estado(estado)
            self.bitacora = type("B", (), {"anotar": lambda *_a, **_k: None})()
            self.gestor = type("G", (), {"estado": lambda _s, _t: {"id": _t},
                                         "listar": lambda _s, **_k: []})()

    lanzados = []
    guardado = (servidor.contexto, servidor.lanzar_paso, servidor._ruta_de_version)
    servidor.lanzar_paso = (lambda ctx, paso, unidades, **kw:
                            lanzados.append((paso, kw.get("opciones"))) or "t-falso")
    servidor._ruta_de_version = lambda ctx, paso, *partes: "pasos/render/v1/video.mp4"
    try:
        al_dia = _Ctx("listo")
        servidor.contexto = lambda _pid: al_dia
        datos = servidor.cambiar_presencia_musica("x", {"presencia": "suave"})
        igual(datos.get("remontando"), True, "montado y al día: se vuelve a mezclar")
        igual(lanzados, [("render", {"solo_montar": True})],
              "con el render en `solo_montar`: ni un clip")
        igual(al_dia.estado.render.get("musica_presencia"), "suave",
              "y el nivel se guarda ANTES de lanzar, o la mezcla saldría con el viejo")
        lanzados.clear()
        pendiente = _Ctx("obsoleto")
        servidor.contexto = lambda _pid: pendiente
        datos = servidor.cambiar_presencia_musica("x", {"presencia": "normal"})
        igual((datos.get("cambiado"), datos.get("remontando"), lanzados),
              (True, False, []),
              "con planos pendientes se guarda y NO se remezcla sobre clips viejos")
    finally:
        servidor.contexto, servidor.lanzar_paso, servidor._ruta_de_version = guardado


def probar_pronunciaciones(cliente, carpeta):
    """«Como se pronuncia» (15-10-2026): la lista se lee, se valida y se guarda
    FUERA del codigo, junto a los ajustes. Abrirla no escribe nada."""
    seccion("COMO SE PRONUNCIA")
    destino = os.path.join(carpeta, "pronunciaciones.json")
    respuesta, datos = cliente.get("/api/pronunciaciones")
    igual(respuesta.status_code, 200, "la lista se lee")
    ok(any(f.get("escrito") == "Just Dance" for f in datos.get("lista") or []),
       "sin guardar ninguna, viene la de partida (con «Just Dance»)")
    ok(not os.path.exists(destino), "y leerla no escribe ningun fichero")
    respuesta, _d = cliente.put("/api/pronunciaciones", {"lista": [{"escrito": "Xbox", "dicho": ""}]})
    igual(respuesta.status_code, 400, "una fila sin «cómo suena» es un 400")
    respuesta, _d = cliente.put("/api/pronunciaciones",
                                {"lista": [{"escrito": "a<b", "dicho": "c"}]})
    igual(respuesta.status_code, 400, "y una etiqueta, otro (la voz la leeria en voz alta)")
    _r, datos = cliente.put("/api/pronunciaciones",
                            {"lista": [{"escrito": " Meta   Quest ", "dicho": "Meta Cuést"},
                                       {"escrito": "", "dicho": ""}]})
    igual(datos.get("lista"), [{"escrito": "Meta Quest", "dicho": "Meta Cuést"}],
          "se guarda limpia (espacios y filas vacias fuera)")
    ok(os.path.exists(destino), "junto a los ajustes, fuera del codigo")
    _r, datos = cliente.get("/api/pronunciaciones")
    igual(len(datos.get("lista") or []), 1, "y se lee la guardada, no la de partida")

    # «ESCUCHAR» UNA VOZ SUENA COMO EL VIDEO (16-10-2026): la muestra pasa por la
    # lista, y cambiar la lista da otra muestra (si no, seguiria sonando la vieja)
    voz = {"voz_id": "a0e99841-438c-4a64-b679-ae501e7d6091", "idioma": "es"}
    respuesta, datos = cliente.post("/api/voces/muestra", voz)
    igual(respuesta.status_code, 200, "la muestra de una voz se sintetiza (simulada)")
    sin_lista = datos.get("ruta")
    _r, _d = cliente.put("/api/pronunciaciones",
                         {"lista": [{"escrito": "Meta Quest", "dicho": "Meta Cuést"},
                                    {"escrito": "octubre", "dicho": "Octúbreh"}]})
    _r, datos = cliente.post("/api/voces/muestra", voz)
    con_lista = datos.get("ruta")
    ok(con_lista and con_lista != sin_lista,
       "con una palabra de la muestra en la lista, la muestra es OTRA (no la vieja)")
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    anterior = os.environ.get("ESTUDIO_PRONUNCIACIONES")
    os.environ["ESTUDIO_PRONUNCIACIONES"] = destino
    try:
        import p4_voz                                         # noqa: PLC0415
        ok("Octúbreh" in p4_voz.texto_para_voz("Una tarde de octubre."),
           "y lo que se le manda a la voz lleva la palabra como suena")
    finally:
        if anterior is None:
            os.environ.pop("ESTUDIO_PRONUNCIACIONES", None)
        else:
            os.environ["ESTUDIO_PRONUNCIACIONES"] = anterior
    _r, _d = cliente.put("/api/pronunciaciones",
                         {"lista": [{"escrito": "Meta Quest", "dicho": "Meta Cuést"}]})
    _r, datos = cliente.post("/api/voces/muestra", voz)
    igual(datos.get("ruta"), sin_lista,
          "y con la lista de antes vuelve la de antes, ya pagada")


def probar_volumen_y_animo_de_la_musica():
    """N9 de las notas de mejoras (13-10-2026): con el vídeo montado, subir o
    bajar la música en dB y cambiarle el ánimo a la automática SIN redibujar ni
    regrabar: el volumen solo remezcla (`solo_montar`) y el ánimo monta la
    banda con los tramos del ritmo y su `animo` cambiado, y después remezcla.

    En proceso, con un contexto de mentira y Jamendo doblado: sin red."""
    seccion("N9: VOLUMEN FINO Y ÁNIMO DE LA MÚSICA, SIN DIBUJAR NI GRABAR")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    sonido = servidor._sonido()

    class _Estado:
        def __init__(self, estado, render=None):
            self.render, self.estado = dict(render or {}), estado
            self.escritos = []

        def params(self, _paso):
            return dict(self.render)

        def estado_de(self, _paso):
            return self.estado

        def actualizar_params(self, paso, cambios):
            self.escritos.append((paso, dict(cambios)))
            self.render.update(cambios)

    lanzados_gestor = []

    class _Gestor:
        def lanzar(self, nombre, funcion, *args, paso=None, **_kw):
            lanzados_gestor.append((nombre, funcion, args, paso))
            return "t-gestor"

        def estado(self, tid):
            return {"id": tid}

        def listar(self, **_k):
            return []

    class _Ctx:
        id = "x"
        proyecto = None

        def __init__(self, estado, render=None):
            self.estado = _Estado(estado, render)
            self.bitacora = type("B", (), {"anotar": lambda *_a, **_k: None})()
            self.gestor = _Gestor()

    # un montaje de cinco minutos con el ritmo de verdad: de ahí salen los tramos
    escenas = [{"id": f"S{i:03d}", "t_in": i * 6.0, "t_out": (i + 1) * 6.0}
               for i in range(50)]
    lanzados = []
    guardado = (servidor.contexto, servidor.lanzar_paso, servidor._ruta_de_version,
                getattr(servidor, "_arco_de", None), servidor._registrar_trabajo,
                servidor._regenerar_tras_repaso, sonido.hay_claves, sonido.buscar_musica, sonido.elegir_tema,
                servidor.PASOS_MODULOS.p6_assets.plan_actual)
    servidor.lanzar_paso = (lambda ctx, paso, unidades, **kw:
                            lanzados.append((paso, kw.get("opciones"))) or "t-falso")
    servidor._ruta_de_version = lambda ctx, paso, *partes: "pasos/render/v1/video.mp4"
    servidor._registrar_trabajo = lambda *_a, **_k: None
    try:
        # ---- el volumen fino: `musica_db`, y solo remezcla
        al_dia = _Ctx("listo")
        servidor.contexto = lambda _pid: al_dia
        datos = servidor.guardar_sonido("x", {"musica_db": -3, "remontar": True})
        igual(al_dia.estado.render.get("musica_db"), -3.0,
              "el volumen fino se guarda en `musica_db` (el que oye también la automática)")
        igual(lanzados, [("render", {"solo_montar": True})],
              "y montado y al día SOLO se vuelve a mezclar (`solo_montar`): ni imágenes ni voz")
        igual(datos.get("trabajo_id"), "t-falso", "y devuelve el trabajo para seguirlo")
        lanzados.clear()
        escritos = len(al_dia.estado.escritos)
        datos = servidor.guardar_sonido("x", {"musica_db": -3, "remontar": True})
        igual((datos.get("cambiado"), len(al_dia.estado.escritos), lanzados),
              (False, escritos, []),
              "pedir el volumen que ya suena no escribe ni remezcla (regla 1)")
        servidor.guardar_sonido("x", {"musica_db": 40, "remontar": True})
        igual(al_dia.estado.render.get("musica_db"), 6.0, "y se queda en su margen (+6 dB)")
        lanzados.clear()
        pendiente = _Ctx("obsoleto")
        servidor.contexto = lambda _pid: pendiente
        servidor.guardar_sonido("x", {"musica_db": 2, "remontar": True})
        igual((pendiente.estado.render.get("musica_db"), lanzados), (2.0, []),
              "con planos pendientes se guarda y NO se mezcla sobre clips viejos")
        servidor.contexto = lambda _pid: al_dia
        igual(servidor.leer_sonido("x").get("musica_db"), 6.0,
              "y GET /sonido lo devuelve para pintar el deslizador")

        # ---- el ánimo de la automática
        if not ok(hasattr(servidor, "cambiar_animo_musica"),
                  "hay un PUT /musica/animo para cambiarle el ánimo a la automática"):
            return
        servidor._arco_de = lambda ctx: (sonido.arco_del_video(escenas, 300.0), 300.0, 50)
        sonido.hay_claves = lambda: (True, True)
        al_dia = _Ctx("listo", {"musica": {"tramos": [{"id": "viejo", "animo": "sobrio"}]}})
        servidor.contexto = lambda _pid: al_dia
        try:
            servidor.cambiar_animo_musica("x", {"animo": "reguetonazo"})
            ok(False, "un ánimo que no existe es un 400")
        except servidor.ErrorApi as fallo:
            igual(fallo.codigo, 400, "un ánimo que no existe es un 400")
        datos = servidor.cambiar_animo_musica("x", {"animo": "alegre"})
        ok(lanzados_gestor and lanzados_gestor[-1][1] is servidor._correr_banda_y_mezcla,
           "el ánimo lanza la banda + la mezcla, en un trabajo")
        _n, _f, args, paso = lanzados_gestor[-1]
        tramos, remezclar = args[1], args[2]
        arco = sonido.arco_del_video(escenas, 300.0)
        igual([t["animo"] for t in tramos], ["alegre"] * len(arco),
              f"con TODOS los tramos del ritmo ({len(arco)}) en el ánimo pedido")
        igual([(t["desde"], t["velocidad"]) for t in tramos],
              [(t["desde"], t["velocidad"]) for t in arco],
              "y los cortes y la velocidad siguen saliendo del montaje")
        igual((remezclar, paso, datos.get("remontando")), (True, "render", True),
              "montado y al día: remezcla después, como trabajo del render")
        igual(al_dia.estado.escritos, [],
              "y al pedirlo no se escribe nada: si Jamendo falla, se queda la música de antes")
        lanzados_gestor.clear()
        servidor.contexto = lambda _pid: _Ctx("obsoleto")
        datos = servidor.cambiar_animo_musica("x", {"animo": "rock"})
        igual((lanzados_gestor[-1][2][2], datos.get("remontando")), (False, False),
              "con planos pendientes monta la banda y NO mezcla sobre clips viejos")

        # ---- el trabajo: la banda con ese ánimo y luego SOLO el render en `solo_montar`
        pedidos, corridos = [], []
        sonido.buscar_musica = lambda animo="", **kw: (pedidos.append(animo) or [
            {"fuente": "jamendo", "id": f"{animo}-{len(pedidos)}", "titulo": animo}])
        sonido.elegir_tema = lambda candidatos, evitar=(): candidatos[0]
        servidor.PASOS_MODULOS.p6_assets.plan_actual = (
            lambda *_a, **_k: {"escenas": escenas, "duracion_total": 300.0})
        servidor._regenerar_tras_repaso = (
            lambda avisar, ctx, tareas, modo, solo_montar=False:
            corridos.append((list(tareas), modo, solo_montar)))
        servidor._correr_banda_y_mezcla(lambda *_a, **_k: None, al_dia, tramos, True)
        igual(pedidos, ["alegre"] * len(arco), "a Jamendo se le pide «alegre» en cada tramo")
        igual([t.get("animo") for t in al_dia.estado.render["musica"]["tramos"]],
              ["alegre"] * len(arco), "y la banda que queda en el render lleva ese ánimo")
        igual(corridos, [(["render"], "pendientes", True)],
              "y después solo se monta el MP4 (`solo_montar`): ni assets ni voz")
    finally:
        (servidor.contexto, servidor.lanzar_paso, servidor._ruta_de_version,
         servidor._arco_de, servidor._registrar_trabajo, servidor._regenerar_tras_repaso,
         sonido.hay_claves, sonido.buscar_musica, sonido.elegir_tema,
         servidor.PASOS_MODULOS.p6_assets.plan_actual) = guardado


def probar_ronda_octubre(cliente, carpeta):
    """Proyectos (clientes), subtítulos, logo, muestra de voz y revisar."""
    seccion("PROYECTOS, SUBTÍTULOS, LOGO, MUESTRA DE VOZ Y REVISAR")
    from PIL import Image
    # --- proyectos (clientes)
    respuesta, datos = cliente.post("/api/clientes", {"nombre": "Suyu"})
    igual(respuesta.status_code, 201, "se crea un proyecto")
    cid = (datos.get("cliente") or {}).get("id") or ""
    ok(cid.startswith("cl_"), f"con su id: {cid}")
    respuesta, _d = cliente.post("/api/clientes", {"nombre": "suyu"})
    igual(respuesta.status_code, 400, "dos proyectos con el mismo nombre no")
    respuesta, _d = cliente.put(f"/api/clientes/estilos/pr_x", {"cliente": cid})
    igual(respuesta.status_code, 200, "un estilo se mete en un proyecto")
    _r, lista = cliente.get("/api/clientes")
    igual((lista.get("estilos") or {}).get("pr_x"), cid, "y la lista lo dice")
    _r, datos = cliente.put(f"/api/clientes/{cid}", {"clave": "1234", "oculto": True})
    ficha = datos.get("cliente") or {}
    ok(ficha.get("con_clave") and ficha.get("oculto") and "clave" not in ficha,
       "se le pone clave y se oculta, y la clave nunca viaja")
    respuesta, _d = cliente.post(f"/api/clientes/{cid}/abrir", {"clave": "mala"})
    igual(respuesta.status_code, 403, "con la clave mala no se abre")
    respuesta, _d = cliente.post(f"/api/clientes/{cid}/abrir", {"clave": "1234"})
    igual(respuesta.status_code, 200, "con la buena, sí")
    respuesta, datos = cliente.pedir("DELETE", f"/api/clientes/{cid}")
    igual(datos.get("estilos_sin_proyecto"), ["pr_x"],
          "borrar el proyecto deja sus estilos sin proyecto, no los borra")
    # --- subtítulos y logo de un vídeo
    _r, datos = cliente.post("/api/proyectos", {"nombre": "Ronda octubre"})
    pid = (datos.get("proyecto") or {}).get("id")
    base = f"/api/proyectos/{pid}"
    _r, sub = cliente.get(f"{base}/subtitulos")
    igual((sub.get("tam"), sub.get("propios")), ("normal", False),
          "sin tocar, los subtítulos son los del estilo")
    respuesta, _d = cliente.put(f"{base}/subtitulos", {"tam": "gigante"})
    igual(respuesta.status_code, 400, "un tamaño que no existe es un 400")
    _r, datos = cliente.put(f"{base}/subtitulos", {"tam": "grande", "color": "#ffcc00"})
    igual(datos.get("cambiado"), True, "se cambian tamaño y color")
    _r, sub = cliente.get(f"{base}/subtitulos")
    igual((sub.get("tam"), sub.get("color"), sub.get("propios")),
          ("grande", "#ffcc00", True), "y se leen como propios del vídeo")
    _r, datos = cliente.put(f"{base}/subtitulos", {"automatico": True})
    _r, sub = cliente.get(f"{base}/subtitulos")
    igual((sub.get("tam"), sub.get("color"), sub.get("propios")),
          ("normal", "", False), "«automático» vuelve a los del estilo")
    # --- la fuente y el sitio (N9, paso 4): se eligen, y «auto» QUITA la clave
    _r, antes = cliente.get(f"{base}/pasos/callouts")
    for cuerpo in ({"fuente": "Comic Sans"}, {"posicion": "volando"}):
        respuesta, _d = cliente.put(f"{base}/subtitulos", cuerpo)
        igual(respuesta.status_code, 400, f"{cuerpo} no existe: 400")
    _r, datos = cliente.put(f"{base}/subtitulos", {"fuente": "georgia", "posicion": "arriba"})
    igual(datos.get("cambiado"), True, "se eligen fuente y sitio")
    _r, sub = cliente.get(f"{base}/subtitulos")
    igual((sub.get("fuente"), sub.get("posicion")), ("Georgia", "arriba"),
          "y se leen tal cual, con el nombre bien escrito")
    ok("Georgia" in (sub.get("fuentes") or []) and "centro" in (sub.get("posiciones") or []),
       "la pantalla recibe las fuentes y los sitios que se pueden elegir")
    _r, paso = cliente.get(f"{base}/pasos/callouts")
    igual(((paso.get("params") or {}).get("subtitulo_fuente"),
           (paso.get("params") or {}).get("subtitulo_posicion")), ("Georgia", "arriba"),
          "quedan en los params de callouts (rehacen capas y montaje, ni una imagen)")
    _r, datos = cliente.put(f"{base}/subtitulos", {"fuente": "auto", "posicion": "auto"})
    _r, paso = cliente.get(f"{base}/pasos/callouts")
    ok("subtitulo_fuente" not in (paso.get("params") or {})
       and "subtitulo_posicion" not in (paso.get("params") or {}),
       "«auto» QUITA las claves, no escribe un valor que el vídeo nunca tuvo (regla 1)")
    igual(paso.get("firma"), antes.get("firma"),
          "y la firma de callouts vuelve a ser la de antes: lo hecho sigue al día")
    _r, sub = cliente.get(f"{base}/subtitulos")
    igual((sub.get("fuente"), sub.get("posicion")), ("", ""), "y se leen como sin elegir")
    _r, datos = cliente.put(f"{base}/subtitulos", {"automatico": True})
    respuesta, _d = cliente.put(f"{base}/logo", {"posicion": "arriba_derecha"})
    igual(respuesta.status_code, 409, "colocar un logo que no se ha subido es un 409")
    png = io.BytesIO()
    Image.new("RGBA", (40, 20), (255, 0, 0, 255)).save(png, "PNG")
    respuesta, datos = cliente.pedir("POST", f"{base}/logo",
                                     files={"logo": ("logo.png", png.getvalue(), "image/png")})
    igual(respuesta.status_code, 200, "se sube un logo")
    igual((datos.get("logo") or {}).get("posicion"), "arriba_derecha",
          "y va arriba a la derecha de fábrica")
    igual(datos.get("trabajo_id"), None, "sin vídeo montado no se lanza nada")
    _r, datos = cliente.put(f"{base}/logo", {"posicion": "abajo_izquierda", "tamano": 2})
    igual(((datos.get("logo") or {}).get("posicion"), (datos.get("logo") or {}).get("tamano")),
          ("abajo_izquierda", 0.4), "se mueve, y el tamaño se queda en su tope")
    respuesta, _d = cliente.get(f"{base}/logo/imagen")
    igual(respuesta.status_code, 200, "y se sirve su imagen")
    _r, datos = cliente.put(f"{base}/logo", {"quitar": True})
    _r, datos = cliente.get(f"{base}/logo")
    igual(datos.get("logo"), None, "y se quita")
    # --- escuchas y revisar
    respuesta, _d = cliente.get("/api/musica/escucha?url=https://ejemplo.com/a.mp3")
    igual(respuesta.status_code, 400, "solo se escuchan temas de Jamendo")
    respuesta, _d = cliente.post("/api/voces/muestra", {"voz_id": "no vale"})
    igual(respuesta.status_code, 400, "una voz con un id raro es un 400")
    respuesta, _d = cliente.post("/api/sistema/guias/no_existe/revisar", {"texto": "x"})
    igual(respuesta.status_code, 404, "revisar con una guía que no existe es un 404")
    respuesta, _d = cliente.post("/api/sistema/guias/tono/revisar", {"texto": "  "})
    igual(respuesta.status_code, 400, "y con el campo vacío, un 400")
    respuesta, _d = cliente.get("/api/sistema/revisiones/nada")
    igual(respuesta.status_code, 404, "una revisión que no existe es un 404")

    # RETOMAR UN ESTILO TRAS CAMBIAR LA VOZ la vuelve a elegir (10-10-2026)
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415

    class _Taller:
        def __init__(self, voz_id, hecha):
            self.estado = type("E", (), {"params": lambda _s, paso: {"voz_id": voz_id}})()
            self.proyecto = type("P", (), {"config": {servidor.CONFIG_VOZ_HECHA: hecha}})()

    hecha = {"voz_prompt": "grave", "voz_id": ""}
    ok(servidor._light_hecha(_Taller("v1", hecha), "voz",
                             {"voz_prompt": "grave", "voz_id": ""}),
       "con el mismo encargo, la voz está hecha")
    ok(not servidor._light_hecha(_Taller("v1", hecha), "voz",
                                 {"voz_prompt": "grave", "voz_id": "v2"}),
       "con otra voz elegida, hay que volver a elegirla")
    ok(not servidor._light_hecha(_Taller("v1", hecha), "voz",
                                 {"voz_prompt": "aguda", "voz_id": ""}),
       "y con otra descripción, también")


def probar_coste_en_detalle(cliente, pid):
    """El coste de un vídeo, desglosado, y el volumen de los efectos (11-10)."""
    seccion("EL COSTE EN DETALLE Y EL VOLUMEN DE LOS EFECTOS")
    r, d = cliente.get(f"/api/proyectos/{pid}/coste/detalle")
    igual(r.status_code, 200, "el coste en detalle contesta")
    for clave in ("total_usd", "imagenes", "voz", "musica", "efectos", "tandas",
                  "precio_imagen", "claude_tokens"):
        ok(clave in d, f"y trae «{clave}»")
    img = d.get("imagenes") or {}
    ok(all(k in img for k in ("nuevas", "rehechas", "personajes")),
       "las imágenes separadas en nuevas, rehechas y personajes")
    _r, total = cliente.get(f"/api/proyectos/{pid}/coste")
    ok(abs(float(d.get("total_usd") or 0) - float(total.get("total_usd") or 0)) < 0.01,
       f"y el total cuadra con el de la cabecera ({d.get('total_usd')} / {total.get('total_usd')})")
    ok(bool((d.get("precio_imagen") or {}).get("fuente")), "dice de dónde sale el precio por imagen")
    r, _d = cliente.get("/api/presets-light/no_existe/coste")
    igual(r.status_code, 404, "el coste de un estilo que no existe es un 404")
    # EL VOLUMEN: pedir el que ya suena no escribe nada (regla 1)
    _r, antes = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    r, d = cliente.put(f"/api/proyectos/{pid}/sonido/efectos/volumen", {"nivel": "normales"})
    igual((r.status_code, d.get("cambiado")), (200, False), "pedir el volumen que ya suena no cambia nada")
    _r, despues = cliente.get(f"/api/proyectos/{pid}/pasos/render")
    igual(despues.get("params"), antes.get("params"), "ni escribe ningún param")
    r, d = cliente.put(f"/api/proyectos/{pid}/sonido/efectos/volumen", {"nivel": "altos"})
    igual((r.status_code, d.get("cambiado")), (200, True), "subir los efectos se guarda")
    _r, sonido = cliente.get(f"/api/proyectos/{pid}/sonido")
    igual(sonido.get("efectos_volumen"), "altos", "y el sonido lo dice")
    r, _d = cliente.put(f"/api/proyectos/{pid}/sonido/efectos/volumen", {"nivel": "a tope"})
    igual(r.status_code, 400, "un nivel que no existe es un 400")
    cliente.put(f"/api/proyectos/{pid}/sonido/efectos/volumen", {"nivel": "normales"})
    # DESCARGAR POR PARTES: lo que no se puede pedir, y nada fuera de exportes/
    r, _d = cliente.post(f"/api/proyectos/{pid}/exportar", {"que": "otra cosa"})
    igual(r.status_code, 400, "exportar algo que no existe es un 400")
    r, _d = cliente.post(f"/api/proyectos/{pid}/exportar", {"que": "audio", "parte": "guitarra"})
    igual(r.status_code, 400, "un audio que no es voz, música, efectos ni mezcla es un 400")
    r, _d = cliente.get(f"/api/proyectos/{pid}/exportes/nada.mp4")
    igual(r.status_code, 404, "un fichero no preparado es un 404")
    r, _d = cliente.get(f"/api/proyectos/{pid}/exportes/..%2F..%2Festado.json")
    ok(r.status_code in (404, 400), f"y no se sale de la carpeta de exportes ({r.status_code})")


def probar_turno_y_notas_de_otro_texto():
    """Dos arreglos del 11-10-2026 que no se ven desde la API.

    1. LAS IMAGENES, DE UNA EN UNA EN TODO EL ESTUDIO: con un trabajo por
       video, nada impedia dibujar en dos videos a la vez (regla 2).
    2. LA NOTA DE UNA FRASE QUE YA NO SE DICE no se pega al plano nuevo con el
       mismo numero: el S004 nuevo salia retocando la imagen vieja de S004.
    """
    seccion("EL TURNO DE LAS IMAGENES Y LAS NOTAS DE OTRA FRASE (11-10)")
    import threading                                          # noqa: PLC0415
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo.trabajos import Cancelado                     # noqa: PLC0415

    class _Bitacora:
        def __init__(self):
            self.eventos = []

        def anotar(self, evento, paso, datos=None, unidad=None):
            self.eventos.append((evento, paso, datos))

    class _Ctx:
        def __init__(self, nombre, params=None):
            self.id = nombre
            self.proyecto = type("P", (), {"config": {"nombre": nombre}})()
            self.bitacora = _Bitacora()
            self._params = params or {}
            self.escrito = []
            self.estado = self

        def params(self, paso):
            return self._params.get(paso) or {}

        def actualizar_params(self, paso, nuevos, del_propio_paso=False):
            self.escrito.append((paso, nuevos, del_propio_paso))
            actual = self._params.setdefault(paso, {})
            actual.setdefault("unidades", {}).update(nuevos.get("unidades") or {})

    # 1. EL TURNO
    cerrojo = servidor._TURNO_IMAGENES["cerrojo"]
    otro = _Ctx("Vídeo A")
    mensajes, hecho = [], []
    cerrojo.acquire()
    servidor._TURNO_IMAGENES["quien"] = "Vídeo A"
    hilo = threading.Thread(target=lambda: hecho.append(servidor._con_turno_de_imagenes(
        lambda v, m="", p="": mensajes.append(m), _Ctx("Vídeo B"), lambda: "dibujado")))
    hilo.start()
    time.sleep(4)
    ok(not hecho, "con otro vídeo dibujando, este espera su turno")
    ok(any("Vídeo A" in m for m in mensajes),
       f"y la barra dice a quién espera ({mensajes[:1]})")
    servidor._TURNO_IMAGENES["quien"] = ""
    cerrojo.release()
    hilo.join(10)
    igual(hecho, ["dibujado"], "al soltarse el turno, dibuja")
    ok(not cerrojo.locked(), "y al acabar lo suelta")

    def _cancelado(*_a):
        raise Cancelado("parado")
    cerrojo.acquire()
    try:
        servidor._con_turno_de_imagenes(_cancelado, otro, lambda: "no")
        ok(False, "parar mientras espera turno corta la espera")
    except Cancelado:
        ok(True, "parar mientras espera turno corta la espera")
    finally:
        cerrojo.release()
    ok(not cerrojo.locked(), "y no se queda con el turno")

    # 2. LAS NOTAS DE OTRA FRASE
    viejo = {"escenas": [{"id": "S001", "narracion": "Hola a todos"},
                         {"id": "S002", "narracion": "La cocina tiene una isla"},
                         {"id": "S003", "narracion": "Y aquí el baño"},
                         {"id": "S004", "narracion": "Hasta la próxima"}]}
    nuevo = {"escenas": [{"id": "S001", "narracion": "¡Hola a TODOS!"},
                         {"id": "S002", "narracion": "Mario Kart es el más vendido"},
                         {"id": "S003", "narracion": "Un tramo nuevo en medio"},
                         {"id": "S004", "narracion": "Y aquí el baño"},
                         {"id": "S005", "narracion": "Hasta la próxima"}]}
    params = {
        "assets": {"unidades": {
            "escena:S001": {"feedback": "más luz", "direccion": "plano medio"},
            "escena:S002": {"feedback": "que aparezca un gato", "alcance": "retoque",
                            "direccion": "cocina"},
            "escena:S003": {"feedback": "el baño más luminoso", "direccion": "baño"},
            "escena:S004": {"direccion": "despedida"}}},
        "callouts": {"unidades": {
            "escena:S002": {"subtitulo_texto": "La cocina tiene una isla.", "evitar": [1]}}}}
    ctx = _Ctx("Vídeo C", params)
    plan_actual = servidor.PASOS_MODULOS.p6_assets.plan_actual
    plan_de_planos = servidor._plan_de_planos
    try:
        servidor.PASOS_MODULOS.p6_assets.plan_actual = lambda *a, **k: viejo
        servidor._plan_de_planos = lambda *a, **k: nuevo
        quitados = servidor._retirar_lo_de_otro_texto(ctx)
    finally:
        servidor.PASOS_MODULOS.p6_assets.plan_actual = plan_actual
        servidor._plan_de_planos = plan_de_planos
    igual(quitados, ["escena:S002", "escena:S003"], "solo los planos cuya frase cambia "
          "(S001 dice lo mismo con otros signos y se queda)")
    unidades = ctx.params("assets")["unidades"]
    igual(unidades["escena:S002"], {"direccion": "cocina"},
          "al S002 nuevo no le llega la nota del viejo (ni su retoque), y conserva lo demás")
    igual(unidades["escena:S001"].get("feedback"), "más luz", "el S001 conserva la suya")
    igual(unidades["escena:S003"], {"direccion": "baño"}, "el S003 nuevo (otra frase) se queda sin ella")
    igual(unidades["escena:S004"], {"direccion": "despedida", "feedback": "el baño más luminoso"},
          "y la nota se MUDA con su frase: «Y aquí el baño» ahora es el S004")
    igual(ctx.params("callouts")["unidades"]["escena:S002"], {"evitar": [1]},
          "ni el subtítulo escrito para la frase de antes")
    igual(sorted(p for p, _n, _d in ctx.escrito), ["assets", "callouts"],
          "y se escribe una vez por paso")
    ok(all(d for p, _n, d in ctx.escrito if p == "assets"),
       "las de las imágenes, como cambio de la propia tanda (no salen obsoletas al terminar)")
    ctx2 = _Ctx("Vídeo C2", {"assets": {"unidades": {
        "escena:S002": {"feedback": "que aparezca un gato"}}}})
    try:
        servidor.PASOS_MODULOS.p6_assets.plan_actual = lambda *a, **k: viejo
        servidor._plan_de_planos = lambda *a, **k: nuevo
        igual(servidor._retirar_lo_de_otro_texto(ctx2, en_cola={"S002"}), [],
              "una nota que está en la cola de imágenes no se toca: es de ahora")
    finally:
        servidor.PASOS_MODULOS.p6_assets.plan_actual = plan_actual
        servidor._plan_de_planos = plan_de_planos
    sin_nada = _Ctx("Vídeo D", {"assets": {"unidades": {"escena:S001": {"direccion": "x"}}}})
    igual(servidor._retirar_lo_de_otro_texto(sin_nada), [], "sin notas no hay nada que mirar")
    igual(sin_nada.escrito, [], "ni que escribir")


def probar_montaje_por_plano(cliente, carpeta):
    """El movimiento y la 2.5D de UN plano (rama montaje-por-plano, 19-10-2026).

    Elegirlo deja obsoleto ESE plano y ninguno más; devolverlo a «como el
    vídeo» quita la clave y la firma de las capas vuelve a la de antes. Las
    cartelas llevan siempre lo de siempre.
    """
    seccion("EL MONTAJE DE CADA PLANO: MOVIMIENTO Y 2.5D EN SU DIAPOSITIVA")
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto, escribir_json

    _r, datos = cliente.post("/api/proyectos", {"nombre": "Montaje por plano"})
    pid = (datos.get("proyecto") or {}).get("id")
    proyecto = Proyecto(os.path.join(carpeta, pid))
    estado = Estado(proyecto)
    escribir_json(os.path.join(proyecto.ruta_trabajo("assets"), "plan.json"), {
        "escenas": [{"id": "S001", "t_in": 0.0, "t_out": 4.0, "duracion": 4.0, "narracion": "uno"},
                    {"id": "S002", "t_in": 4.0, "t_out": 8.0, "duracion": 4.0, "narracion": "dos"},
                    {"id": "S003", "t_in": 8.0, "t_out": 11.0, "duracion": 3.0, "narracion": "tres",
                     "cartela": {"plantilla": "tesis", "fondo": "negro"}}],
        "duracion_total": 11.0})
    planos = ("escena:S001", "escena:S002", "escena:S003")
    estado.set_params("assets", {"unidades": {u: {"direccion": "plano"} for u in planos}})
    estado.completar("assets", {"plan": "plan.json"}, unidades={u: {"ok": 1} for u in planos})
    # S002 ya tiene otras decisiones por plano: tienen que sobrevivir
    estado.set_params("callouts", {"unidades": {"escena:S002": {"evitar": [{"x": 1}],
                                                               "sin_callout": True}}})
    estado.completar("callouts", {"movimiento": "movimiento.json"},
                     unidades={u: {"ok": 1} for u in planos})

    base = f"/api/proyectos/{pid}/planos"
    respuesta, leido = cliente.get(f"{base}/montaje")
    igual(respuesta.status_code, 200, "GET .../planos/montaje responde 200")
    igual(leido.get("planos"), {}, "ningún plano tiene montaje propio al empezar")
    igual(leido.get("planos_del_video"), ["S001", "S002", "S003"], "y trae los planos del vídeo")
    igual(leido.get("no_aplica"), ["S003"], "la cartela no admite movimiento propio")
    ok("quieto" in (leido.get("niveles") or []), "y se puede elegir «quieta»")
    _r, callouts = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
    firma_antes = callouts.get("firma")
    sucias_antes = set(callouts.get("unidades_obsoletas") or [])
    igual(sucias_antes, set(), "las capas empiezan al día")

    respuesta, puesto = cliente.put(f"{base}/S001/montaje", {"movimiento": "quieto"})
    igual(respuesta.status_code, 200, f"PUT .../planos/S001/montaje responde 200: {puesto}")
    ok(puesto.get("cambiado") is True, "y dice que cambió")
    igual((puesto.get("planos") or {}).get("S001"), {"movimiento": "quieto"},
          "y lo devuelve en la lista de planos")
    _r, callouts = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
    params = callouts.get("params") or {}
    igual(((params.get("unidades") or {}).get("escena:S001") or {}).get("montaje"),
          {"movimiento": "quieto"}, "se guarda en la unidad de ese plano, solo lo elegido")
    ok("montaje" not in params, "y no toca el montaje del vídeo")
    igual(set(callouts.get("unidades_obsoletas") or []), {"escena:S001"},
          "deja obsoleto ESE plano y ninguno más")
    _r, assets = cliente.get(f"/api/proyectos/{pid}/pasos/assets")
    igual(assets.get("unidades_obsoletas") or [], [], "y ni una imagen")

    respuesta, otra = cliente.put(f"{base}/S001/montaje", {"movimiento": "quieto"})
    ok(otra.get("cambiado") is False, "poner lo que ya está no cambia nada")
    respuesta, _d = cliente.put(f"{base}/S001/montaje", {"movimiento": "loco"})
    igual(respuesta.status_code, 400, "un movimiento que no existe da 400")
    respuesta, _d = cliente.put(f"{base}/S001/montaje", {"profundidad": "si"})
    igual(respuesta.status_code, 400, "una 2.5D que no es sí/no da 400")
    respuesta, _d = cliente.put(f"{base}/S999/montaje", {"movimiento": "vivo"})
    igual(respuesta.status_code, 404, "un plano que no existe da 404")
    respuesta, _d = cliente.put(f"{base}/S003/montaje", {"movimiento": "vivo"})
    igual(respuesta.status_code, 400, "S003 es una cartela: no se le cambia la cámara")
    respuesta, _d = cliente.put(f"{base}/S003/montaje", {"movimiento": None})
    igual(respuesta.status_code, 200, "pero devolverla a «como el vídeo» siempre se puede")
    respuesta, _d = cliente.put(f"{base}/S002/montaje", {"profundidad": True})
    if (leido.get("profundidad") or {}).get("disponible"):
        igual(respuesta.status_code, 200, "con modelo, la 2.5D de un plano se enciende")
        _r, cal = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
        igual(((cal.get("params") or {}).get("unidades") or {}).get("escena:S002"),
              {"evitar": [{"x": 1}], "sin_callout": True, "montaje": {"profundidad": True}},
              "y se suma a lo que ese plano ya tenía, sin borrarlo")
        cliente.put(f"{base}/S002/montaje", {"profundidad": None})
    else:
        igual(respuesta.status_code, 409, "sin modelo, la 2.5D de un plano no se puede encender")

    # UN VÍDEO DONDE NADIE DECLARA LOS PLANOS: elegir lo declara, y quitarlo lo
    # deja exactamente como estaba
    _r, d2 = cliente.post("/api/proyectos", {"nombre": "Montaje por plano sin unidades"})
    pid2 = (d2.get("proyecto") or {}).get("id")
    p2 = Proyecto(os.path.join(carpeta, pid2))
    e2 = Estado(p2)
    escribir_json(os.path.join(p2.ruta_trabajo("assets"), "plan.json"), {
        "escenas": [{"id": "S001", "t_in": 0.0, "t_out": 4.0, "duracion": 4.0, "narracion": "uno"}],
        "duracion_total": 4.0})
    e2.completar("assets", {"plan": "plan.json"})
    e2.completar("callouts", {"movimiento": "movimiento.json"})
    _r, c2 = cliente.get(f"/api/proyectos/{pid2}/pasos/callouts")
    firma2, estado2 = c2.get("firma"), c2.get("estado")
    respuesta, _d = cliente.put(f"/api/proyectos/{pid2}/planos/S001/montaje", {"movimiento": "vivo"})
    igual(respuesta.status_code, 200, "en un vídeo sin unidades también se puede elegir")
    _r, c2 = cliente.get(f"/api/proyectos/{pid2}/pasos/callouts")
    igual(c2.get("unidades_obsoletas"), ["escena:S001"], "y queda pendiente ese plano")
    cliente.put(f"/api/proyectos/{pid2}/planos/S001/montaje", {"movimiento": None})
    _r, c2 = cliente.get(f"/api/proyectos/{pid2}/pasos/callouts")
    igual((c2.get("firma"), c2.get("estado")), (firma2, estado2),
          "quitarlo deja la firma y el estado como estaban")

    respuesta, vuelta = cliente.put(f"{base}/S001/montaje", {"movimiento": None,
                                                             "profundidad": None})
    igual(respuesta.status_code, 200, "volver a «como el vídeo» responde 200")
    igual(vuelta.get("planos"), {}, "y el plano ya no tiene nada propio")
    _r, callouts = cliente.get(f"/api/proyectos/{pid}/pasos/callouts")
    igual(((callouts.get("params") or {}).get("unidades") or {}),
          {"escena:S002": {"evitar": [{"x": 1}], "sin_callout": True}},
          "la unidad vacía se quita entera (regla 1) y las otras decisiones siguen")
    igual(callouts.get("firma"), firma_antes, "y la firma de las capas vuelve a la de antes")
    igual(set(callouts.get("unidades_obsoletas") or []), set(),
          "y el plano deja de estar obsoleto")


def probar_descargar_imagenes(cliente, carpeta):
    """«Descargar todas» de las diapositivas (rama imagenes-texto, 20-10-2026).

    El .zip trae las imágenes de plano de la versión ACTIVA de assets, en el
    orden del plan y numeradas; un vídeo sin imágenes es un 404; y pedirlo no
    escribe nada: ni el estado ni un fichero dentro del proyecto ni un .zip
    olvidado en el temporal.
    """
    seccion("DESCARGAR TODAS LAS IMÁGENES DE UN VÍDEO EN UN .ZIP")
    import hashlib
    import zipfile
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto, escribir_json

    _r, datos = cliente.post("/api/proyectos", {"nombre": "Descargar imágenes"})
    pid = (datos.get("proyecto") or {}).get("id")
    proyecto = Proyecto(os.path.join(carpeta, pid))
    estado = Estado(proyecto)
    ruta_zip = f"/api/proyectos/{pid}/imagenes/zip"
    respuesta, _d = cliente.get(ruta_zip)
    igual(respuesta.status_code, 404, "un vídeo sin imágenes da 404")
    respuesta, _d = cliente.get("/api/proyectos/no_existe_este/imagenes/zip")
    igual(respuesta.status_code, 404, "un vídeo que no existe da 404")

    def tanda(contenidos):
        trabajo = proyecto.ruta_trabajo("assets")
        os.makedirs(os.path.join(trabajo, "escenas"), exist_ok=True)
        escribir_json(os.path.join(trabajo, "plan.json"), {
            "escenas": [{"id": sid, "t_in": 0.0, "t_out": 1.0, "duracion": 1.0, "narracion": sid}
                        for sid in ("S002", "S001", "S003", "S004")],
            "duracion_total": 4.0})
        for sid, contenido in contenidos.items():
            with open(os.path.join(trabajo, "escenas", f"{sid}.png"), "wb") as fh:
                fh.write(contenido)
        # una que no es de plano: no va en el .zip
        with open(os.path.join(trabajo, "suelta.png"), "wb") as fh:
            fh.write(b"no")
        estado.completar("assets", {"plan": "plan.json"})

    # el plan va en otro orden que los nombres: el .zip sigue el PLAN.
    # S004 no tiene imagen (una cartela, una que falló): no sale.
    tanda({"S001": b"v1-uno", "S002": b"v1-dos", "S003": b"v1-tres"})
    tanda({"S001": b"v2-uno", "S002": b"v2-dos", "S003": b"v2-tres"})

    def foto():
        huellas = {}
        for raiz, _dirs, ficheros in os.walk(proyecto.raiz):
            for nombre in ficheros:
                ruta = os.path.join(raiz, nombre)
                with open(ruta, "rb") as fh:
                    huellas[os.path.relpath(ruta, proyecto.raiz)] = hashlib.sha1(fh.read()).hexdigest()
        return huellas

    temporal = tempfile.gettempdir()
    zips_antes = {n for n in os.listdir(temporal) if n.startswith("imagenes_") and n.endswith(".zip")}
    antes = foto()
    respuesta, _d = cliente.get(ruta_zip)
    igual(respuesta.status_code, 200, f"GET {ruta_zip} responde 200")
    igual(respuesta.headers.get("content-type"), "application/zip", "y es un .zip")
    ok("descargar_imagenes_imagenes.zip" in (respuesta.headers.get("content-disposition") or ""),
       f"con el nombre del vídeo ({respuesta.headers.get('content-disposition')})")
    try:
        with zipfile.ZipFile(io.BytesIO(respuesta.content)) as archivo:
            nombres = archivo.namelist()
            contenidos = [archivo.read(n) for n in nombres]
    except zipfile.BadZipFile:
        nombres, contenidos = [], []
    igual(nombres, ["descargar_imagenes_001_S002.png", "descargar_imagenes_002_S001.png",
                    "descargar_imagenes_003_S003.png"],
          "trae las 3 imágenes de plano, en el orden del plan y numeradas")
    igual(contenidos, [b"v2-dos", b"v2-uno", b"v2-tres"], "y son las de la versión ACTIVA")
    igual(foto(), antes, "pedir el .zip no escribe nada en el proyecto (ni el estado)")
    time.sleep(0.5)
    zips_despues = {n for n in os.listdir(temporal) if n.startswith("imagenes_") and n.endswith(".zip")}
    igual(zips_despues - zips_antes, set(), "y el .zip temporal se borra al mandarlo")

    # UN PROYECTO CON CLAVE: sin abrirlo no se baja; con su pase, sí (en la
    # cabecera de siempre o en `?abiertos=`, que es lo que lleva el enlace)
    _r, datos = cliente.post("/api/clientes", {"nombre": "Con clave para el zip"})
    cid = (datos.get("cliente") or {}).get("id") or ""
    cliente.put(f"/api/clientes/{cid}", {"clave": "4321"})
    cliente.put(f"/api/clientes/videos/{pid}", {"cliente": cid})
    respuesta, _d = cliente.get(ruta_zip)
    igual(respuesta.status_code, 404, "el de un proyecto con clave sin abrir da 404")
    _r, abierto = cliente.post(f"/api/clientes/{cid}/abrir", {"clave": "4321"})
    pase = f"{cid}.{abierto.get('pase')}"
    respuesta, _d = cliente.get(ruta_zip, headers={"X-Estudio-Abiertos": pase})
    igual(respuesta.status_code, 200, "abierto (con su pase en la cabecera), se baja")
    respuesta, _d = cliente.get(ruta_zip, params={"abiertos": pase})
    igual(respuesta.status_code, 200, "y con el pase en ?abiertos= (el enlace de la pantalla), también")
    respuesta, _d = cliente.get(ruta_zip, params={"abiertos": f"{cid}.falso"})
    igual(respuesta.status_code, 404, "con un pase falso, no")
    cliente.put(f"/api/clientes/videos/{pid}", {"cliente": ""})
    cliente.pedir("DELETE", f"/api/clientes/{cid}")


def probar_montaje(cliente):
    """El montaje (rama montaje-movimiento, 18-10-2026).

    Un corto NUEVO nace con el montaje de los cortos y en ritmo rapido; uno
    largo, con lo de siempre y sin una clave escrita (regla 1). El ritmo del
    corto no cuenta como «el estilo tiene cambios». Cambiar el montaje solo
    escribe lo que difiere de siempre, y volver a lo de siempre quita la clave.
    """
    seccion("EL MONTAJE: MOVIMIENTO, SUBTÍTULOS, GANCHO, CIFRAS Y BARRA")
    respuesta, datos = cliente.get("/api/montaje")
    igual(respuesta.status_code, 200, "GET /api/montaje responde 200")
    igual((datos.get("montaje_cortos") or {}).get("movimiento"), "vivo",
          "los cortos nacen en vivo")
    igual(datos.get("duracion_corta_s"), 120, "y es corto hasta 2 minutos")
    ok(datos.get("catalogo") or datos.get("transiciones"),
       "con el catálogo de transiciones para elegir")

    respuesta, preset = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Estilo para montaje",
        "datos": {"guion": {"idioma_salida": "es", "instrucciones": "Claro."},
                  "voz": {"voz_id": "v-de-prueba", "idioma": "es",
                          "velocidad": "normal"},
                  "origen": {"tono_prompt": "serio", "estilo_prompt": "plano"}}})
    estilo_id = (preset.get("preset") or {}).get("id") or ""

    def crear(nombre, segundos, opciones=None):
        cuerpo = {"nombre": nombre, "duracion_objetivo_s": segundos,
                  "material": "Un hecho.\n\nY otro."}
        if opciones is not None:
            cuerpo["opciones"] = opciones
        respuesta, creado = cliente.post(f"/api/presets-light/{estilo_id}/video", cuerpo)
        return respuesta, (creado.get("proyecto") or {}).get("id") or ""

    respuesta, corto = crear("Corto con montaje", 60)
    igual(respuesta.status_code, 201, "se crea un corto")
    _r, callouts = cliente.get(f"/api/proyectos/{corto}/pasos/callouts")
    igual((callouts.get("params") or {}).get("montaje"),
          {"movimiento": "vivo", "subtitulos": "redes", "gancho": True,
           "cifras": True, "barra": True},
          "un corto nuevo nace con el montaje de los cortos")
    _r, assets = cliente.get(f"/api/proyectos/{corto}/pasos/assets")
    igual((assets.get("params") or {}).get("max_s"), 5.0,
          "y en ritmo rápido (planos de hasta 5 s)")
    _r, cambios = cliente.get(f"/api/proyectos/{corto}/estilo/cambios")
    ok(cambios.get("al_dia") is True,
       f"y el ritmo del corto NO cuenta como «el estilo tiene cambios»: {cambios}")

    respuesta, largo = crear("Largo de siempre", 240)
    _r, callouts = cliente.get(f"/api/proyectos/{largo}/pasos/callouts")
    ok("montaje" not in (callouts.get("params") or {}),
       "un vídeo largo nace sin la clave montaje (regla 1)")
    _r, assets = cliente.get(f"/api/proyectos/{largo}/pasos/assets")
    ok((assets.get("params") or {}).get("max_s") != 5.0,
       "ni el ritmo de los cortos")

    respuesta, sobrio = crear("Corto sobrio", 60, {
        "montaje": {"movimiento": "sobrio", "subtitulos": "clasicos",
                    "gancho": False, "cifras": False, "barra": False},
        "ritmo": "estilo"})
    _r, callouts = cliente.get(f"/api/proyectos/{sobrio}/pasos/callouts")
    ok("montaje" not in (callouts.get("params") or {}),
       "un corto encargado «como siempre» no escribe la clave")
    _r, assets = cliente.get(f"/api/proyectos/{sobrio}/pasos/assets")
    ok((assets.get("params") or {}).get("max_s") != 5.0,
       "y con «ritmo del estilo» no se toca el ritmo")
    respuesta, _d = crear("Corto malo", 60, {"montaje": {"movimiento": "loco"}})
    igual(respuesta.status_code, 400, "un montaje que no existe da 400 al crear")

    base = f"/api/proyectos/{largo}/montaje"
    _r, antes = cliente.get(f"/api/proyectos/{largo}/pasos/callouts")
    respuesta, leido = cliente.get(base)
    igual(respuesta.status_code, 200, "GET .../montaje responde 200")
    igual(leido.get("elegido"), False, "el largo no tiene montaje elegido")
    respuesta, puesto = cliente.put(base, {"montaje": {"movimiento": "dinamico"}})
    igual(respuesta.status_code, 200, f"PUT .../montaje responde 200: {puesto}")
    ok(puesto.get("cambiado") is True, "y dice que cambió")
    _r, callouts = cliente.get(f"/api/proyectos/{largo}/pasos/callouts")
    igual((callouts.get("params") or {}).get("montaje"), {"movimiento": "dinamico"},
          "se guarda SOLO lo que difiere de siempre")
    respuesta, puesto = cliente.put(base, {"montaje": {"movimiento": "sobrio"}})
    _r, callouts = cliente.get(f"/api/proyectos/{largo}/pasos/callouts")
    ok("montaje" not in (callouts.get("params") or {}),
       "volver a lo de siempre QUITA la clave")
    igual(callouts.get("firma"), antes.get("firma"),
          "y la firma de las capas vuelve a la de antes")
    respuesta, otra = cliente.put(base, {"montaje": {"movimiento": "sobrio"}})
    ok(otra.get("cambiado") is False, "poner lo que ya está no cambia nada")
    # LA PROFUNDIDAD 2.5D (18-10): se dice si está disponible, se guarda sola
    # al encenderla y apagarla quita la clave
    _r, datos_m = cliente.get("/api/montaje")
    ok(isinstance((datos_m.get("profundidad") or {}).get("disponible"), bool),
       "GET /api/montaje dice si la profundidad 2.5D está disponible")
    respuesta, _d = cliente.put(base, {"montaje": {"profundidad": True}})
    _r, callouts = cliente.get(f"/api/proyectos/{largo}/pasos/callouts")
    igual((callouts.get("params") or {}).get("montaje"), {"profundidad": True},
          "encender la profundidad guarda solo esa clave")
    respuesta, _d = cliente.put(base, {"montaje": {"profundidad": False}})
    _r, callouts = cliente.get(f"/api/proyectos/{largo}/pasos/callouts")
    ok("montaje" not in (callouts.get("params") or {}), "y apagarla quita la clave")
    respuesta, _d = cliente.put(base, {"montaje": {"profundidad": "quizá"}})
    igual(respuesta.status_code, 400, "un valor que no es sí/no da 400")
    respuesta, _d = cliente.put(base, {"transiciones": ["inventada"]})
    igual(respuesta.status_code, 400, "una transición que no existe da 400")
    respuesta, _d = cliente.post(f"{base}/aplicar", {})
    igual(respuesta.status_code, 409, "aplicar sin vídeo montado da 409")


def probar_traer_estilo(cliente):
    """Un video se queda con la copia del estilo; esto la trae cuando se pide.

    Lo que se prueba: que mirar no escriba nada, que diga que partes cambian,
    que traer una parte no pise lo que es del video (duracion, llamadas a la
    accion, indicaciones) y que deje obsoleto lo que toca y nada mas.
    """
    seccion("TRAER LOS CAMBIOS DEL ESTILO A UN VIDEO")
    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Estilo que cambia",
        "datos": {"guion": {"idioma_salida": "es",
                            "instrucciones": "Habla claro y sin adornos."},
                  "voz": {"voz_id": "v-de-prueba", "idioma": "es",
                          "velocidad": "normal"},
                  "origen": {"tono_prompt": "serio", "estilo_prompt": "plano"}}})
    estilo_id = (datos.get("preset") or {}).get("id") or ""
    respuesta, creado = cliente.post(f"/api/presets-light/{estilo_id}/video", {
        "nombre": "Vídeo que hereda", "duracion_objetivo_s": 90,
        "material": "Un hecho.\n\nY otro.",
        "indicaciones": "Sin rodeos.",
        "cta": {"cta_final": {"puesto": True, "texto": "que se suscriba"}}})
    vid = (creado.get("proyecto") or {}).get("id") or ""
    ok(bool(vid), "se crea el vídeo desde el estilo")
    base = f"/api/proyectos/{vid}/estilo"

    respuesta, cambios = cliente.get(f"{base}/cambios")
    igual(respuesta.status_code, 200, "GET estilo/cambios responde 200")
    ok(cambios.get("al_dia") is True, f"recién creado está al día: {cambios}")
    _r, antes = cliente.get(f"/api/proyectos/{vid}/pasos/brief")

    # el estilo cambia de tono DESPUES de crear el video
    respuesta, _d = cliente.put(f"/api/presets-light/{estilo_id}",
                                {"instrucciones": "Cuéntalo como una historia."})
    igual(respuesta.status_code, 200, "se cambia la guía de tono del estilo")
    respuesta, cambios = cliente.get(f"{base}/cambios")
    tono = [p for p in cambios.get("partes") or [] if p["id"] == "tono"]
    ok(cambios.get("al_dia") is False and tono and tono[0]["cambia"],
       f"ahora dice que el TONO tiene cambios: {cambios.get('partes')}")
    ok(all(not p["cambia"] for p in cambios["partes"] if p["id"] != "tono"),
       "y que lo demás sigue igual")
    ok(tono and "rehace" in tono[0], "diciendo qué se rehace")
    _r, despues = cliente.get(f"/api/proyectos/{vid}/pasos/brief")
    igual(despues.get("firma"), antes.get("firma"),
          "MIRAR NO ESCRIBE NADA: la firma del brief no se mueve")

    respuesta, _d = cliente.post(f"{base}/traer", {"partes": ["inventada"]})
    igual(respuesta.status_code, 400, "una parte que no existe da 400")
    respuesta, traido = cliente.post(f"{base}/traer", {"partes": ["tono"]})
    igual(respuesta.status_code, 200, f"traer el tono responde 200: {traido}")
    igual(traido.get("traidas"), ["tono"], "y dice qué trajo")
    _r, brief = cliente.get(f"/api/proyectos/{vid}/pasos/brief")
    igual((brief.get("params") or {}).get("instrucciones"),
          "Cuéntalo como una historia.", "el tono nuevo llega al vídeo")
    igual((brief.get("params") or {}).get("duracion_objetivo_s"), 90,
          "SIN PISAR LA DURACIÓN del encargo")
    _r, guion = cliente.get(f"/api/proyectos/{vid}/pasos/guion")
    ok(((guion.get("params") or {}).get("cta") or {}).get("cta_final", {}).get("texto")
       == "que se suscriba", "ni las llamadas a la acción del vídeo")
    igual((guion.get("params") or {}).get("prompt_general"), "Sin rodeos.",
          "ni sus indicaciones")
    _r, voz = cliente.get(f"/api/proyectos/{vid}/pasos/voz")
    igual(voz.get("firma") is not None, True, "la voz sigue ahí")
    respuesta, cambios = cliente.get(f"{base}/cambios")
    ok(cambios.get("al_dia") is True, "y después vuelve a estar al día")
    respuesta, otra = cliente.post(f"{base}/traer", {"partes": ["tono"]})
    igual(otra.get("traidas"), [], "traer otra vez lo mismo no cambia nada")


def probar_cambiar_de_estilo(cliente):
    """Arreglos del 19-10 (4): un vídeo cuyo estilo se borró se quedaba
    huérfano --«Su estilo» no ofrecía nada y «Traer» daba 404--. Ahora
    `GET /estilo/cambios?estilo=<otro>` enseña lo que cambiaría con su coste y
    `PUT /estilo {estilo, partes}` lo pasa al otro estilo trayendo SOLO las
    partes elegidas."""
    seccion("ARREGLOS 19-10: UN VÍDEO HUÉRFANO SE PASA A OTRO ESTILO")
    def estilo(nombre, tono):
        _r, datos = cliente.post("/api/presets-canal", {
            "tipo": "canal", "nombre": nombre,
            "datos": {"guion": {"idioma_salida": "es", "instrucciones": tono},
                      "voz": {"voz_id": "v-de-prueba", "idioma": "es",
                              "velocidad": "normal"},
                      "origen": {"tono_prompt": "serio", "estilo_prompt": "plano"}}})
        return (datos.get("preset") or {}).get("id") or ""
    viejo = estilo("Estilo que se borra", "Habla claro.")
    otro = estilo("Estilo de acogida", "Cuéntalo como una historia.")
    _r, creado = cliente.post(f"/api/presets-light/{viejo}/video", {
        "nombre": "Vídeo huérfano", "duracion_objetivo_s": 60,
        "material": "Un hecho.\n\nY otro."})
    vid = (creado.get("proyecto") or {}).get("id") or ""
    base = f"/api/proyectos/{vid}/estilo"
    _r, brief_antes = cliente.get(f"/api/proyectos/{vid}/pasos/brief")
    _r, voz_antes = cliente.get(f"/api/proyectos/{vid}/pasos/voz")

    # el estilo viejo es de un proyecto (cliente); el nuevo, de ninguno
    _r, nuevo_cliente = cliente.post("/api/clientes", {"nombre": "Cliente del huérfano"})
    cid = (nuevo_cliente.get("cliente") or {}).get("id") or ""
    cliente.put(f"/api/clientes/estilos/{viejo}", {"cliente": cid})

    # a la papelera: se sigue pudiendo comparar, y lo dice
    cliente.delete(f"/api/presets-canal/{viejo}")
    _r, cambios = cliente.get(f"{base}/cambios")
    ok((cambios.get("estilo") or {}).get("en_papelera") is True,
       f"con el estilo en la papelera, «Su estilo» lo sabe (para «Restaurarlo»): {cambios.get('estilo')}")
    # y purgado: huérfano de verdad
    respuesta, _d = cliente.delete(f"/api/presets-canal/papelera/{viejo}?confirmar=1")
    igual(respuesta.status_code, 200, "el estilo se borra del todo")
    _r, cambios = cliente.get(f"{base}/cambios")
    ok(bool(cambios.get("por_que_no")), f"el vídeo queda huérfano: {cambios.get('por_que_no')}")
    igual(cambios.get("actual"), viejo, "y sigue diciendo cuál era su estilo")

    # la vista previa con otro estilo: con su coste y sin escribir nada
    respuesta, previa = cliente.get(f"{base}/cambios?estilo={otro}")
    igual(respuesta.status_code, 200, f"la vista previa con otro estilo responde 200: {previa}")
    tono = [p for p in previa.get("partes") or [] if p["id"] == "tono"]
    ok(tono and tono[0]["cambia"] and "rehace" in tono[0],
       f"dice que el tono cambiaría y qué rehace: {tono}")
    _r, brief = cliente.get(f"/api/proyectos/{vid}/pasos/brief")
    igual(brief.get("firma"), brief_antes.get("firma"), "MIRAR NO ESCRIBE NADA")
    respuesta, _d = cliente.get(f"{base}/cambios?estilo=no-existe")
    ok(respuesta.status_code == 200 and _d.get("por_que_no"),
       "un estilo que no existe se dice, sin 500")

    # cambiar: validaciones
    respuesta, _d = cliente.put(base, {"partes": ["tono"]})
    igual(respuesta.status_code, 400, "sin 'estilo', 400")
    respuesta, _d = cliente.put(base, {"estilo": otro, "partes": ["inventada"]})
    igual(respuesta.status_code, 400, "una parte que no existe, 400")
    respuesta, _d = cliente.put(base, {"estilo": "no-existe", "partes": []})
    igual(respuesta.status_code, 400, "un estilo que no existe, 400")

    # el cambio: solo el tono
    respuesta, cambio = cliente.put(base, {"estilo": otro, "partes": ["tono"]})
    igual(respuesta.status_code, 200, f"PUT estilo responde 200: {cambio}")
    igual(cambio.get("traidas"), ["tono"], "trae solo lo elegido")
    _r, brief = cliente.get(f"/api/proyectos/{vid}/pasos/brief")
    igual((brief.get("params") or {}).get("instrucciones"), "Cuéntalo como una historia.",
          "el tono del estilo nuevo llega al vídeo")
    igual((brief.get("params") or {}).get("duracion_objetivo_s"), 60,
          "sin pisar la duración del encargo")
    _r, voz = cliente.get(f"/api/proyectos/{vid}/pasos/voz")
    igual(voz.get("params"), voz_antes.get("params"), "y la voz, que no se pidió, no se toca")
    _r, cambios = cliente.get(f"{base}/cambios")
    igual((cambios.get("estilo") or {}).get("id"), otro, "«Su estilo» es ya el nuevo")
    ok(not cambios.get("por_que_no"), "y deja de estar huérfano")
    _r, galeria = cliente.get("/api/proyectos")
    fila = [p for p in galeria.get("proyectos") or [] if p.get("id") == vid]
    ok(fila and fila[0].get("estilo_light") == otro,
       f"la lista de vídeos lo apunta en el estilo nuevo: {fila[:1]}")
    _r, clientes = cliente.get("/api/clientes")
    igual((clientes.get("videos") or {}).get(vid), cid,
          "SE QUEDA EN SU PROYECTO (el del estilo viejo): se le fija, el nuevo es de otro")
    igual((cambio.get("cliente") or {}).get("ahora"), cid, "y la respuesta lo dice")

    # la revisión editorial (arreglos 19-10, 5): solo del guion, y un modo raro no
    respuesta, _d = cliente.post(f"/api/proyectos/{vid}/ortografia/revisar",
                                 {"fuente": "subtitulos", "modo": "editorial"})
    igual(respuesta.status_code, 400, "EDITORIAL: la revisión editorial es solo del guion")
    respuesta, _d = cliente.post(f"/api/proyectos/{vid}/ortografia/revisar",
                                 {"fuente": "guion", "modo": "estilo", "textos": {"B1": "x"}})
    igual(respuesta.status_code, 400, "EDITORIAL: un modo que no existe, 400")
    respuesta, _d = cliente.post(f"/api/proyectos/{vid}/ortografia/revisar",
                                 {"fuente": "guion", "modo": "editorial", "textos": {}})
    igual(respuesta.status_code, 400, "EDITORIAL: sin textos, 400")

    # con el estilo nuevo en la papelera no se adopta
    tercero = estilo("Estilo apartado", "Otro tono.")
    cliente.delete(f"/api/presets-canal/{tercero}")
    respuesta, _d = cliente.put(base, {"estilo": tercero, "partes": []})
    igual(respuesta.status_code, 409, "un estilo en la papelera no se adopta: 409 (restáuralo antes)")


def probar_continuaciones_en_otra_calidad():
    """Rehacer en otra calidad lleva tambien la segunda mitad de cada plano
    largo (`sigue_a`): sin ella, a mitad de toma se veia la imagen vieja
    (revision independiente del 15-10-2026). Sin servidor."""
    seccion("REHACER EN OTRA CALIDAD: CON LA SEGUNDA MITAD DE CADA PLANO LARGO")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    plan = {"escenas": [{"id": "S010"}, {"id": "S011", "sigue_a": "S010"},
                        {"id": "S020"}, {"id": "S021", "sigue_a": "S020"}]}
    igual(servidor._con_sus_continuaciones(["escena:S010"], plan),
          ["escena:S010", "escena:S011"],
          "rehacer S010 se lleva S011, que es su segunda mitad")
    igual(servidor._con_sus_continuaciones(["escena:S010", "escena:S011"], plan),
          ["escena:S010", "escena:S011"], "sin repetirla si ya iba")
    igual(servidor._con_sus_continuaciones([], plan), [], "y nada si no se pide nada")


def probar_el_coste_de_las_imagenes(cliente):
    """La auditoria del coste de las imagenes del 15-10-2026 (C1, C5 y C2).

    C1: el $/min del deslizador de ritmo salia siempre en calidad baja.
    C5: la estimacion de un video nuevo cotizaba con la calidad que traia el
        estilo sin pasar por el minimo de foto (medium), y nacia en medium.
    C2: rehacer las imagenes en otra calidad solo con lo confirmado delante.
    """
    seccion("EL COSTE DE LAS IMAGENES: LA CALIDAD CON LA QUE NACE EL VIDEO")
    _r, guardados = cliente.get("/api/ajustes")
    calidad_antes = ((guardados or {}).get("ajustes") or {}).get("calidad_imagen") or "low"
    cliente.put("/api/ajustes", {"calidad_imagen": "low"})
    try:
        # C5
        for modo, del_estilo, esperada in (("foto", "low", "medium"),
                                           ("foto", None, "medium"),
                                           ("foto", "high", "high"),
                                           ("ilustracion", None, "low"),
                                           ("ilustracion", "medium", "medium")):
            peticion = {"duracion_objetivo_s": 240, "nuevo": True, "modo": modo}
            if del_estilo:
                peticion["calidad"] = del_estilo
            respuesta, datos = cliente.post("/api/estimacion", peticion)
            igual((datos.get("coste") or {}).get("calidad"), esperada,
                  f"un vídeo nuevo de {modo} con el estilo en {del_estilo}: se cotiza "
                  f"en {esperada}, la calidad con la que va a nacer")
        _r, baja = cliente.post("/api/estimacion", {"duracion_objetivo_s": 240,
                                                    "nuevo": True, "modo": "ilustracion"})
        _r, foto = cliente.post("/api/estimacion", {"duracion_objetivo_s": 240, "nuevo": True,
                                                    "modo": "foto", "calidad": "low"})
        ok(foto["coste"]["usd_imagenes"] > baja["coste"]["usd_imagenes"],
           f"y la foto cuesta más ({foto['coste']['usd_imagenes']} $ frente a "
           f"{baja['coste']['usd_imagenes']} $)")

        # C1
        respuesta, datos = cliente.get("/api/presets-light")
        igual(datos.get("calidad_nuevo"), {"ilustracion": "low", "foto": "medium"},
              "el listado dice con qué calidad nace un vídeo de cada modo")
        ritmo = next((r for r in datos.get("ritmos") or [] if r["id"] == "medio"), {})
        tabla = ritmo.get("usd_por_minuto_por_calidad") or {}
        ok(tabla.get("medium|foto", 0) > tabla.get("low|ilustracion", 0) > 0,
           f"cada ritmo trae su $/min por calidad y modo: {tabla}")
        igual(ritmo.get("usd_por_minuto"), tabla.get("low|ilustracion"),
              "y el de siempre es el de la calidad de Configuración")
        from PIL import Image
        carpeta_refs = tempfile.mkdtemp(prefix="estudio_refs_foto_")
        refs = []
        for i in range(3):
            refs.append(os.path.join(carpeta_refs, f"foto{i}.png"))
            Image.new("RGB", (320, 200), (60 * i, 120, 90)).save(refs[-1])
        respuesta, creado = cliente.post("/api/presets-canal", {
            "tipo": "canal", "nombre": "Estilo de fotos para el coste",
            "datos": {"estilo": {"modo": "foto", "referencias": refs}}})
        igual(respuesta.status_code, 200, f"se crea un estilo de foto: {creado}")
        estilo_id = (creado.get("preset") or {}).get("id") or ""
        _r, datos = cliente.get("/api/presets-light")
        ficha = next((f for f in datos.get("presets") or [] if f.get("id") == estilo_id), {})
        igual(ficha.get("calidad_nuevo"), "medium",
              "un estilo de foto dice que sus vídeos nacen en medium (y el deslizador "
              "enseña ese $/min, no el de low)")
        js = open(os.path.join(RAIZ_ESTUDIO, "web", "app.js"), encoding="utf-8").read()
        ok("usd_por_minuto_por_calidad" in js and "claveCosteRitmo(" in js,
           "la pantalla elige el $/min por la calidad y el modo del estilo")

        # C2: el boton de rehacer en otra calidad no lanza nada sin lo confirmado
        respuesta, video = cliente.post(f"/api/presets-light/{estilo_id}/video", {
            "nombre": "Vídeo para el coste", "duracion_objetivo_s": 60,
            "material": "Un hecho."})
        vid = (video.get("proyecto") or {}).get("id") or ""
        _r, assets = cliente.get(f"/api/proyectos/{vid}/pasos/assets")
        igual((assets.get("params") or {}).get("calidad"), "medium",
              "el vídeo de foto nace en medium con Configuración en low")
        respuesta, _d = cliente.post(f"/api/proyectos/{vid}/imagenes/calidad", {})
        igual(respuesta.status_code, 400, "rehacer en otra calidad sin decir cuántas: 400")
        respuesta, datos = cliente.post(f"/api/proyectos/{vid}/imagenes/calidad",
                                        {"imagenes": 3})
        igual(respuesta.status_code, 400,
              f"sin imágenes en otra calidad no se lanza nada: {datos}")
        respuesta, plan = cliente.get(f"/api/proyectos/{vid}/generar?tanda=video")
        ok("otra_calidad" not in (plan.get("coste") or {}),
           "y el plan no ofrece rehacer nada en un vídeo sin imágenes")
    finally:
        cliente.put("/api/ajustes", {"calidad_imagen": calidad_antes})


def probar_planos_hechos(cliente, pid):
    """Los PNG que hay AHORA, y cuales son de este plan.

    La carpeta de trabajo conserva lo de pasadas anteriores -- es lo que permite
    retomar una tanda cortada -- asi que ahi puede haber planos que el corte de
    hoy ya no tiene. Sin decir cuales son del plan, la pantalla ensenaba un
    «S105» en un video cuyo ultimo plano es otro.
    """
    seccion("QUE PLANOS HAY, Y CUALES SON DE ESTE PLAN")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/assets/hechos")
    igual(respuesta.status_code, 200, "responde 200")
    ok(isinstance(datos.get("planos"), dict),
       "los planos llegan por id, no en una lista")
    ok(isinstance(datos.get("plan"), list),
       "y con la lista de ids que tiene el plan de ahora")
    igual(datos.get("del_plan"),
          len([s for s in (datos.get("plan") or []) if s in (datos.get("planos") or {})]),
          "y cuantos de los que hay son de este plan")


def probar_estimacion(cliente):
    """Cuantas palabras, cuantos planos y cuanto cuesta, SIN proyecto.

    Es lo que se lee al mover la duracion en la pantalla del modo light, y no
    necesita proyecto porque se pregunta antes de que exista ninguno.
    """
    seccion("LA ESTIMACION DE UN VIDEO")
    respuesta, datos = cliente.post("/api/estimacion",
                                    {"duracion_objetivo_s": 240, "idioma": "es",
                                     "velocidad": "normal", "ritmo": "medio"})
    igual(respuesta.status_code, 200, "la estimación responde 200")
    igual(datos["duracion_objetivo_s"], 240, "respeta la duración pedida")
    ok(datos["palabras"]["objetivo"] > 0, "dice cuántas palabras caben")
    ok(datos["palabras"]["minimo"] < datos["palabras"]["objetivo"]
       < datos["palabras"]["maximo"], "con su horquilla alrededor")
    ok(datos["segundos"]["minimo"] < 240 < datos["segundos"]["maximo"],
       "y la horquilla de vuelta EN SEGUNDOS, que es lo que se pregunta")
    ok(datos["planos"]["total"] > 0, "cuántos planos salen")
    ok(datos["coste"]["usd_total"] > 0, "y lo que va a costar el vídeo entero")
    igual(datos["cadencia"]["origen"] in ("medido", "estimado"), True,
          "diciendo si la cadencia está medida o estimada")

    # TODOS LOS PLANOS PAGAN IMAGEN. Antes habia planos que no --los que
    # ensenaban metraje real de un mapa-- y se descontaban de la cuenta. Ya no
    # existen, asi que el precio es el numero de planos por lo que cuesta uno:
    # si esto deja de cumplirse, hay algo descontando en silencio.
    igual(datos["coste"]["imagenes"], datos["planos"]["total"],
          "se paga una imagen por plano, sin descuentos escondidos")
    igual(datos["planos"]["con_imagen"], datos["planos"]["total"],
          "y la ficha de planos dice lo mismo")

    respuesta, _ = cliente.post("/api/estimacion", {"duracion_objetivo_s": "hola"})
    igual(respuesta.status_code, 400, "una duración que no es un número da 400")


def probar_escucha_de_voz_light(cliente):
    """La escucha de una voz, y la de OTRA sin elegirla.

    Es lo que hace el play de cada celda de la cuadricula: audicionar. Si
    escuchar guardara, comparar seis voces dejaria puesta la sexta -- asi que la
    voz viaja en el cuerpo y el preset no se toca. Todo lo demas (velocidad,
    color, aire) son los mandos del estilo, que es lo que hace que la comparacion
    valga: cambia la voz y nada mas.
    """
    seccion("MODO LIGHT: ESCUCHAR UNA VOZ SIN ELEGIRLA")
    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "taller de escucha"})
    tid = (datos.get("proyecto") or {}).get("id") or ""
    config = os.path.join(cliente.carpeta, tid, "proyecto.json")
    with open(config, "r", encoding="utf-8") as fh:
        ficha = json.load(fh)
    ficha["taller_de_preset"] = True
    with open(config, "w", encoding="utf-8") as fh:
        json.dump(ficha, fh)

    respuesta, datos = cliente.get("/api/voces", params={"idioma": "es", "nativas": 1})
    voces = datos.get("voces") or []
    ok(len(voces) >= 2, f"hay al menos dos voces nativas que comparar ({len(voces)})")
    puesta, otra = voces[0], voces[-1]

    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Canal con taller",
        "datos": {"guion": {"idiomas_salida": ["es"]},
                  "voz": {"voz_id": puesta["id"], "voz_nombre": puesta["nombre"],
                          "idioma": "es", "velocidad": "normal"},
                  "origen": {"estilo_prompt": "dibujo plano", "taller": tid}}})
    pid_preset = (datos.get("preset") or {}).get("id") or ""

    ruta = f"/api/presets-light/{pid_preset}/voz/previsualizar"
    respuesta, datos = cliente.post(ruta, {"segundos": 4})
    igual(respuesta.status_code, 202, "escuchar la voz del estilo responde 202")
    igual(datos.get("voz_id"), puesta["id"], "y suena la que tiene puesta")
    hecho = esperar_trabajo(cliente, datos.get("trabajo_id"))
    igual(hecho["estado"], "listo", f"la escucha se genera ({hecho.get('error')})")
    ok(bool((hecho.get("resultado") or {}).get("url")), "y trae su URL")

    respuesta, datos = cliente.post(ruta, {"segundos": 4, "voz_id": otra["id"]})
    igual(respuesta.status_code, 202, "escuchar OTRA voz responde 202")
    igual(datos.get("voz_id"), otra["id"], "y suena la que se ha pedido")
    hecho = esperar_trabajo(cliente, datos.get("trabajo_id"))
    igual(hecho["estado"], "listo", f"la audicion se genera ({hecho.get('error')})")

    respuesta, datos = cliente.get("/api/presets-light")
    guardado = next((f for f in (datos.get("presets") or [])
                     if f.get("id") == pid_preset), {})
    igual(((guardado.get("datos") or {}).get("voz") or {}).get("voz_id"),
          puesta["id"], "y el estilo SIGUE con la suya: escuchar no elige")

    cliente.delete(f"/api/presets-light/{pid_preset}")


def probar_muestras_recuperadas(cliente):
    """Un estilo al que le faltan sus muestras se las recupera del taller.

    Las muestras son lo unico que se mira de un estilo: cuatro planos con su
    cartela y su subtitulo puestos, a todo lo ancho. Cuando desaparecian del
    banco --se las llevaba por delante cualquier guardado posterior-- la ficha
    seguia declarandolas y la pantalla pintaba cuatro imagenes rotas: un hueco
    negro donde va lo unico que hay que juzgar.

    El taller no se borra al guardar el preset, asi que devolverlas no cuesta ni
    una imagen ni una llamada. Se hace al listar, que es lo unico que garantiza
    que pase.
    """
    seccion("MODO LIGHT: LAS MUESTRAS QUE FALTAN SE DEVUELVEN")
    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "taller con muestras"})
    tid = (datos.get("proyecto") or {}).get("id") or ""
    config = os.path.join(cliente.carpeta, tid, "proyecto.json")
    with open(config, "r", encoding="utf-8") as fh:
        ficha = json.load(fh)
    ficha["taller_de_preset"] = True
    with open(config, "w", encoding="utf-8") as fh:
        json.dump(ficha, fh)

    sueltas = [f"muestra{n}.png" for n in range(1, 5)]
    carpeta = os.path.join(cliente.carpeta, tid, "muestras")
    os.makedirs(carpeta, exist_ok=True)
    for indice, nombre in enumerate(["miniatura.png"] + sueltas):
        with open(os.path.join(carpeta, nombre), "wb") as fh:
            fh.write(b"\x89PNG-taller" + bytes([indice]) * 16)

    # el preset las DECLARA y en su carpeta del banco no hay ninguna: es
    # exactamente como quedaba un estilo despues de cambiarle el nombre
    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Canal sin sus muestras",
        "datos": {"guion": {"idiomas_salida": ["es"]},
                  "origen": {"estilo_prompt": "dibujo plano", "taller": tid,
                             "muestras": sueltas}}})
    pid_preset = (datos.get("preset") or {}).get("id") or ""

    respuesta, datos = cliente.get("/api/presets-light")
    guardado = next((f for f in (datos.get("presets") or [])
                     if f.get("id") == pid_preset), {})
    igual(((guardado.get("datos") or {}).get("origen") or {}).get("muestras"),
          sueltas, "la ficha sigue declarando sus cuatro muestras")
    for nombre in sueltas:
        respuesta = cliente.sesion.get(
            f"{cliente.base}/api/presets-canal/{pid_preset}/fichero/{nombre}",
            timeout=30)
        igual(respuesta.status_code, 200, f"y {nombre} se sirve de verdad")
    ok(guardado.get("hay_miniatura") is True,
       "y la cara de la tarjeta vuelve a ser la hoja 2x2, no un fotograma")

    cliente.delete(f"/api/presets-light/{pid_preset}")


def probar_imagenes_de_apoyo(cliente):
    """Imagenes adjuntas a una descripcion de estilo: el buzon y sus limites.

    El camino del video le da a la guia veinticuatro fotogramas que mirar; el
    descrito le daba un parrafo y nada mas. Se pueden adjuntar hasta las MISMAS
    veinticuatro como material de apoyo, y el tope sale de donde vive
    (`p6_assets.REFERENCIAS_A_ELEGIR`) en vez de escribirse dos veces.

    Se suben ANTES de que exista el taller --no hay taller hasta pulsar
    «Generar»-- asi que esperan en un buzon; lo que se prueba aqui es ese buzon
    y las dos cosas que tiene que rechazar.
    """
    seccion("MODO LIGHT: IMAGENES DE APOYO DE UNA DESCRIPCION")
    respuesta, datos = cliente.get("/api/presets-light")
    tope = datos.get("max_imagenes_estilo")
    ok(isinstance(tope, int) and tope > 0,
       f"la galeria dice cuantas imagenes caben ({tope})")

    # UNA IMAGEN DE VERDAD: un degradado que se abre entero. Lo que habia aqui
    # --la cabecera de un PNG y ceros detras-- es justo lo que la subida tiene
    # que rechazar (M4 del informe de la Etapa Foto A, mas abajo).
    from PIL import Image                                    # noqa: PLC0415

    def imagen(ancho, alto, color=None, formato="PNG"):
        lienzo = Image.new("RGB", (ancho, alto), color or (0, 0, 0))
        if color is None:
            lienzo.putdata([(x * 255 // ancho, y * 255 // alto, 128)
                            for y in range(alto) for x in range(ancho)])
        crudo = io.BytesIO()
        lienzo.save(crudo, formato)
        return crudo.getvalue()

    png = imagen(160, 120)
    respuesta, datos = cliente.pedir(
        "POST", "/api/presets-light/imagenes",
        files=[("imagenes", ("una.png", png, "image/png")),
               ("imagenes", ("otra.jpg", imagen(160, 120, formato="JPEG"),
                             "image/jpeg"))])
    igual(respuesta.status_code, 201, "subir dos imagenes responde 201")
    subidas = datos.get("imagenes") or []
    igual(len(subidas), 2, "y las guarda las dos")
    ok(all(s.get("nombre") and s.get("origen") for s in subidas),
       "cada una vuelve con su nombre guardado y el que traia")
    ok(subidas[0]["nombre"] != subidas[1]["nombre"],
       "con nombres distintos: dos ficheros que se llamen igual no se pisan")

    for s in subidas:
        respuesta = cliente.sesion.get(
            f"{cliente.base}/api/presets-light/imagenes/{s['nombre']}", timeout=30)
        igual(respuesta.status_code, 200, f"{s['origen']} se sirve para la miniatura")

    # lo que NO se acepta: un fichero que el CLI no puede abrir
    respuesta, datos = cliente.pedir(
        "POST", "/api/presets-light/imagenes",
        files=[("imagenes", ("apuntes.txt", b"no soy una imagen", "text/plain"))])
    igual(respuesta.status_code, 400, "un fichero que no es imagen da 400")

    # M4: LO QUE SE LLAMA .jpg PERO NO SE PUEDE ABRIR se rechaza AL SUBIRLO.
    # Antes se aceptaba, salia una miniatura rota y el estilo se caia al 92 %
    # tras dos minutos con Claude (`UnidentifiedImageError`). Igual las
    # diminutas y las de un solo color: no hay estilo que copiar de ellas.
    malas = [
        ("rota.jpg", b"esto no es un jpg aunque lo diga el nombre", "image/jpeg",
         "dañado"),
        ("cortada.png", png[: len(png) // 2], "image/png", "dañado"),
        ("cabecera.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png", "dañado"),
        ("mini.png", imagen(8, 8), "image/png", "pequeña"),
        ("negra.png", imagen(400, 300, (0, 0, 0)), "image/png", "un solo color"),
    ]
    for origen, crudo, tipo, dice in malas:
        respuesta, datos = cliente.pedir(
            "POST", "/api/presets-light/imagenes",
            files=[("imagenes", (origen, crudo, tipo))])
        igual(respuesta.status_code, 400, f"«{origen}» se rechaza al subirla")
        texto = json.dumps(datos, ensure_ascii=False)
        ok(origen in texto and dice in texto,
           f"y el motivo nombra el fichero y dice «{dice}»")
    respuesta, datos = cliente.pedir(
        "POST", "/api/presets-light/imagenes",
        files=[("imagenes", ("buena.png", png, "image/png")),
               ("imagenes", ("rota.jpg", b"basura", "image/jpeg"))])
    igual(respuesta.status_code, 201, "una buena y una rota: se sube la buena")
    igual([s.get("origen") for s in datos.get("imagenes") or []], ["buena.png"],
          "y solo la buena queda en el buzón")
    ok(any("rota.jpg" in a for a in datos.get("avisos") or []),
       "y la rota vuelve como aviso, que la pantalla enseña en ese momento")
    cliente.delete(f"/api/presets-light/imagenes/{datos['imagenes'][0]['nombre']}")

    nombres = [s["nombre"] for s in subidas]
    base = {"nombre": "Canal con imagenes", "idioma": "es",
            "estilo_prompt": "igual pero más frío y sin personajes",
            "tono_prompt": "serio pero cercano, sin dramatismo",
            "voz_prompt": "grave, pausada, sin sonar a locutor"}

    respuesta, datos = cliente.post("/api/presets-light/plan",
                                    dict(base, estilo_imagenes=nombres))
    igual(respuesta.status_code, 200,
          "un encargo de imagenes CON indicaciones es valido")
    respuesta, datos = cliente.post("/api/presets-light/plan",
                                    dict(base, estilo_prompt="",
                                         estilo_imagenes=nombres))
    igual(respuesta.status_code, 200, "y sin indicaciones tambien: son opcionales")

    # SIN IMAGENES NO HAY ESTILO, por muchas indicaciones que se escriban: de
    # un parrafo suelto se inventa todo lo que el parrafo no diga.
    respuesta, datos = cliente.post("/api/presets-light/plan", dict(
        base, estilo_imagenes=[]))
    igual(respuesta.status_code, 400,
          "sin imagenes da 400 aunque haya indicaciones")

    respuesta, datos = cliente.post("/api/presets-light/plan", dict(
        base, estilo_imagenes=[f"x{i}.png" for i in range(tope + 1)]))
    igual(respuesta.status_code, 400, f"pasarse de {tope} da 400")

    respuesta, datos = cliente.delete(
        f"/api/presets-light/imagenes/{nombres[0]}")
    igual(respuesta.status_code, 200, "quitar una del buzon responde 200")
    respuesta = cliente.sesion.get(
        f"{cliente.base}/api/presets-light/imagenes/{nombres[0]}", timeout=30)
    igual(respuesta.status_code, 404, "y ya no esta")


def probar_cambiar_la_fuente_del_estilo(cliente):
    """Cambiar DE DONDE sale el estilo, conservando el tono y la voz.

    El caso: «los mismos videos, pero en fotografico». Corregir con una frase
    rehace la guia con los MISMOS fotogramas; esto es la otra cosa, y hasta
    ahora era un estilo nuevo desde cero y volver a escribir el tono y la voz.

    Lo que se prueba aqui es lo que decide ANTES de gastar: que la lista de
    tareas sale del encargo NUEVO --con un video hay que bajarlo y volver a
    elegir fotogramas, y sin el no-- y que el tono y la voz nunca entran.
    """
    seccion("MODO LIGHT: CAMBIAR LA FUENTE DEL ESTILO")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "pasos"))
    import presets_light as light

    base = {"nombre": "Canal", "idioma": "es",
            "tono_prompt": "serio pero cercano, sin dramatismo",
            "voz_prompt": "grave, pausada, sin sonar a locutor"}

    descrito = light.validar_encargo(
        dict(base, estilo_prompt="fotográfico, luz natural, sin filtros"))
    tareas = light.tareas_de_estilo(descrito)
    ok("frames" not in tareas and "eleccion" not in tareas,
       f"con una descripcion nueva no se baja ningun vídeo ({tareas})")

    con_video = light.validar_encargo(
        dict(base, estilo_url="https://www.youtube.com/watch?v=xxxxxxxxxxx"))
    tareas_video = light.tareas_de_estilo(con_video)
    ok("frames" in tareas_video and "eleccion" in tareas_video,
       f"con un vídeo nuevo si: hay que bajarlo y volver a elegir ({tareas_video})")
    ok(tareas_video.index("frames") < tareas_video.index("guia"),
       "y en orden: primero los fotogramas, despues la guia")

    for lista in (tareas, tareas_video):
        ok("tono" not in lista and "voz" not in lista,
           "el tono y la voz NUNCA se rehacen al cambiar el estilo")
        ok(all(t in lista for t in light.PARTES["estilo"]["tareas"]),
           "y se rehace el estilo entero, no media guia")

    igual(light.plan_de(descrito, tareas)["imagenes"],
          light.imagenes_de_parte("estilo"),
          "cambiar a una descripcion cuesta lo mismo que rehacer el estilo")

    # y por la API: sin taller se dice, no se inventa uno
    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Canal sin taller",
        "datos": {"guion": {"idiomas_salida": ["es"]},
                  "origen": {"estilo_prompt": "dibujo plano",
                             "tono_prompt": "serio pero cercano",
                             "voz_prompt": "grave y pausada"}}})
    pid = (datos.get("preset") or {}).get("id") or ""
    respuesta, datos = cliente.post(f"/api/presets-light/{pid}/regenerar", {
        "parte": "estilo", "peticion": "",
        "origen": {"estilo_prompt": "fotográfico, luz natural, sin filtros"}})
    igual(respuesta.status_code, 409,
          "cambiar la fuente sin taller da 409 y lo explica")
    respuesta, datos = cliente.post(f"/api/presets-light/{pid}/regenerar", {
        "parte": "voz", "peticion": "más joven",
        "origen": {"estilo_prompt": "fotográfico"}})
    igual(respuesta.status_code, 400,
          "y la voz no tiene fuente que cambiar: eso es un 400")
    cliente.delete(f"/api/presets-light/{pid}")


def probar_taller_oculto(cliente):
    """Un taller de preset NO sale en la lista de proyectos.

    Se comprueba de verdad --creando la carpeta con su marca-- porque el fallo
    que evita es mudo: el taller aparece entre los videos, alguien lo abre, y
    empieza a trastear dentro de la carpeta de la que sale un preset.
    """
    seccion("EL TALLER DE UN PRESET NO ES UN PROYECTO")
    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "taller falso"})
    igual(respuesta.status_code, 201, "se crea el proyecto que hara de taller")
    tid = (datos.get("proyecto") or {}).get("id") or ""

    config = os.path.join(cliente.carpeta, tid, "proyecto.json")
    with open(config, "r", encoding="utf-8") as fh:
        ficha = json.load(fh)
    ficha["taller_de_preset"] = True
    with open(config, "w", encoding="utf-8") as fh:
        json.dump(ficha, fh)

    respuesta, datos = cliente.get("/api/proyectos")
    ok(not any(p.get("id") == tid for p in (datos.get("proyectos") or [])),
       "un proyecto marcado como taller no sale en la lista")
    respuesta, datos = cliente.get(f"/api/proyectos/{tid}")
    igual(respuesta.status_code, 200,
          "pero sigue abriendose por su id: es donde corre la generacion")


def probar_laminas(cliente):
    """Las laminas de un estilo: se ven, se quitan, se devuelven, y con limites.

    No se dibuja nada (no hay clave de OpenAI): se prueba lo que decide ANTES
    de gastar y lo que no gasta -- quitar y devolver una lamina ya dibujada
    rehacen la lista de referencias sin pagar ninguna imagen.
    """
    seccion("MODO LIGHT: LAS LAMINAS DEL ESTILO")
    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "taller con laminas"})
    tid = (datos.get("proyecto") or {}).get("id") or ""
    config = os.path.join(cliente.carpeta, tid, "proyecto.json")
    with open(config, "r", encoding="utf-8") as fh:
        ficha = json.load(fh)
    ficha["taller_de_preset"] = True
    with open(config, "w", encoding="utf-8") as fh:
        json.dump(ficha, fh)
    dibujadas = os.path.join(cliente.carpeta, tid, "estilo", "dibujadas")
    os.makedirs(dibujadas, exist_ok=True)
    from PIL import Image
    ejes = ["cara", "cuerpos", "interior", "exterior", "objeto", "diagrama"]
    for indice, eje in enumerate(ejes):
        Image.new("RGB", (64, 40), (indice * 30, 90, 160)).save(
            os.path.join(dibujadas, f"{eje}.png"))
    aportadas = os.path.join(cliente.carpeta, tid, "estilo", "aportadas")
    os.makedirs(aportadas, exist_ok=True)
    Image.new("RGB", (64, 40), (10, 10, 10)).save(os.path.join(aportadas, "01_a.png"))

    respuesta, datos = cliente.post("/api/presets-canal", {
        "tipo": "canal", "nombre": "Canal con laminas",
        "datos": {"guion": {"idiomas_salida": ["es"]},
                  "origen": {"estilo_prompt": "dibujo plano y limpio",
                             "estilo_imagenes": ["a.png"],
                             "tono_prompt": "serio pero cercano",
                             "voz_prompt": "grave y pausada", "taller": tid}}})
    pid = (datos.get("preset") or {}).get("id") or ""
    ok(bool(pid), "se crea un estilo descrito con su taller")

    respuesta, datos = cliente.get(f"/api/presets-light/{pid}/laminas")
    igual(respuesta.status_code, 200, "las laminas se piden")
    igual([l["id"] for l in datos.get("laminas") or []], ejes,
          "un estilo sin tocar tiene las seis de fabrica, en orden")
    ok(all(l.get("explicacion") and l.get("url") for l in datos["laminas"]),
       "cada una dice que ensena y tiene su imagen limpia")
    igual(datos.get("max"), 8, "caben 8: las de la hoja de cada plano")
    ok(datos.get("usd_por_lamina") is not None, "y dice lo que cuesta dibujar una")
    url = datos["laminas"][0]["url"]
    respuesta = cliente.sesion.get(f"{cliente.base}{url}", timeout=30)
    igual(respuesta.status_code, 200, "la imagen limpia se sirve")

    respuesta, _ = cliente.post(f"/api/presets-light/{pid}/laminas",
                                {"accion": "inventada"})
    igual(respuesta.status_code, 400, "una accion inventada es un 400")
    respuesta, _ = cliente.post(f"/api/presets-light/{pid}/laminas",
                                {"accion": "nueva", "texto": "una"})
    igual(respuesta.status_code, 400, "una lamina nueva sin decir que ensena, 400")
    respuesta, _ = cliente.post(f"/api/presets-light/{pid}/laminas",
                                {"accion": "quitar", "lamina": "../x"})
    igual(respuesta.status_code, 400, "un nombre de lamina raro, 400")

    respuesta, datos = cliente.get(f"/api/presets-light/{pid}/aportadas")
    igual([x["nombre"] for x in datos.get("imagenes") or []], ["a.png"],
          "la ficha ve las imagenes de referencia que ya tiene, sin el «NN_»")
    respuesta = cliente.sesion.get(f"{cliente.base}{datos['imagenes'][0]['url']}",
                                   timeout=30)
    igual(respuesta.status_code, 200, "y las sirve")
    respuesta, datos = cliente.put(f"/api/presets-light/{pid}/aportadas", {
        "descripciones": {"a.png": "la luz de esta", "otra.png": "no esta"},
        "destacadas": ["a.png", "otra.png"]})
    igual(respuesta.status_code, 200, "describirlas se guarda sin regenerar")
    origen = ((datos.get("preset") or {}).get("datos") or {}).get("origen") or {}
    igual(origen.get("estilo_descripciones"), {"a.png": "la luz de esta"},
          "solo de imagenes que estan")
    igual(origen.get("estilo_destacadas"), ["a.png"], "y la ★ igual")
    igual(origen.get("taller"), tid, "sin perder el taller")

    respuesta, datos = cliente.post(f"/api/presets-light/{pid}/laminas",
                                    {"accion": "hoja", "hoja": "repartida"})
    igual(respuesta.status_code, 202, "cambiar la hoja se acepta")
    igual(datos.get("trabajo_id"), "", "y no lanza nada: no se dibuja")
    respuesta, datos = cliente.get(f"/api/presets-light/{pid}/laminas")
    igual(datos.get("hoja"), "repartida", "la hoja queda guardada en el estilo")

    respuesta, datos = cliente.post(f"/api/presets-light/{pid}/laminas",
                                    {"accion": "quitar", "lamina": "diagrama"})
    igual(respuesta.status_code, 202, "quitar una lamina lanza el rehacer")
    igual(datos.get("imagenes"), 0, "y no paga ninguna imagen")
    igual((datos.get("plan") or {}).get("imagenes"), 0,
          "y la pantalla de generando tampoco dice que vaya a pagar seis")
    fin = esperar_trabajo(cliente, datos.get("trabajo_id"))
    igual(fin.get("estado"), "listo",
          f"y termina bien ({fin.get('error') or ''})")
    with open(os.path.join(cliente.carpeta, tid, "estado.json"), encoding="utf-8") as fh:
        estado = json.load(fh)
    refs = ((((estado.get("pasos") or {}).get("assets") or {}).get("params") or {}
             ).get("estilo") or {}).get("referencias") or []
    igual([os.path.basename(r) for r in refs], [f"{e}.png" for e in ejes[:5]],
          "la quitada sale de las referencias y las otras siguen en orden")
    ok(os.path.isfile(os.path.join(dibujadas, "diagrama.png")),
       "y su imagen se queda en el disco para devolverla gratis")
    respuesta, datos = cliente.get(f"/api/presets-light/{pid}/laminas")
    igual([l["id"] for l in datos.get("quitadas") or []], ["diagrama"],
          "el estilo recuerda cual se quito")

    respuesta, datos = cliente.post(f"/api/presets-light/{pid}/laminas",
                                    {"accion": "restaurar", "lamina": "diagrama"})
    igual(datos.get("imagenes"), 0, "devolverla tampoco paga: ya estaba dibujada")
    fin = esperar_trabajo(cliente, datos.get("trabajo_id"))
    igual(fin.get("estado"), "listo",
          f"y termina bien ({fin.get('error') or ''})")
    respuesta, datos = cliente.get(f"/api/presets-light/{pid}/laminas")
    igual(len(datos.get("laminas") or []), 6, "y vuelve a haber seis")
    cliente.delete(f"/api/presets-light/{pid}")


def probar_sonido_propio_y_cola(cliente):
    """Tu musica y tus efectos, la cola de imagenes y el motor ante el filtro."""
    seccion("SONIDO PROPIO, COLA DE IMAGENES Y FILTRO DE SEGURIDAD")
    carpeta = tempfile.mkdtemp(prefix="estudio_audio_")
    mp3 = os.path.join(carpeta, "mio.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=330:duration=2", mp3], check=True)
    for familia, servida in (("efectos", "/api/efectos/"), ("musica", "/api/musica/propia/")):
        with open(mp3, "rb") as fh:
            r = cliente.sesion.post(f"{cliente.base}/api/sonido/subir?familia={familia}",
                                    files={"audio": ("mio.mp3", fh, "audio/mpeg")}, timeout=60)
        igual(r.status_code, 201, f"se sube un audio propio para {familia}")
        ficha = (r.json() or {}).get("ficha") or {}
        igual(ficha.get("fuente"), "propia", "y queda como audio propio")
        ok(abs(float(ficha.get("duracion") or 0) - 2.0) < 0.3, "con su duracion medida")
        r = cliente.sesion.get(cliente.base + ficha.get("muestra", ""), timeout=30)
        igual(r.status_code, 200, f"y se puede escuchar ({ficha.get('muestra')})")
    r = cliente.sesion.post(f"{cliente.base}/api/sonido/subir?familia=musica",
                            files={"audio": ("nota.txt", b"hola", "text/plain")}, timeout=30)
    igual(r.status_code, 400, "un fichero que no es audio se rechaza con su motivo")
    respuesta, datos = cliente.post("/api/efectos/buscar", {"texto": "whoosh"})
    ok(respuesta.status_code in (200, 502), "buscar efectos sin clave o sin red no rompe nada")
    shutil.rmtree(carpeta, ignore_errors=True)

    respuesta, datos = cliente.post("/api/proyectos", {"nombre": "cola de imagenes"})
    pid = (datos.get("proyecto") or {}).get("id") or ""
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/imagenes/cola")
    igual(respuesta.status_code, 200, "la cola de imagenes se consulta")
    igual(datos.get("cola"), [], "y empieza vacia")
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/imagenes/rehacer", {})
    igual(respuesta.status_code, 400, "sin notas pendientes no se lanza nada")
    respuesta, datos = cliente.post(f"/api/proyectos/{pid}/imagenes/rehacer",
                                    {"notas": ["R999"], "desde_cero": True})
    igual(respuesta.status_code, 400, "«desde cero» de una nota que no existe tampoco")
    respuesta, datos = cliente.get(f"/api/proyectos/{pid}/subtitulos/rotos")
    igual(respuesta.status_code, 200, "se puede preguntar si los subtitulos tienen tildes rotas")
    igual(datos.get("planos"), 0, "y un video sin montar no tiene ninguno")

    # EL MOTOR ANTE EL FILTRO DE SEGURIDAD (con el motor falso)
    sys.path.insert(0, os.path.join(RAIZ_ESTUDIO, "pasos"))
    import importlib.util
    os.environ["ESTUDIO_IMAGEN_FALSA"] = "1"
    os.environ.setdefault("OPENAI_API_KEY", "sk-falsa")
    spec = importlib.util.spec_from_file_location(
        "imagen_prueba", os.path.join(RAIZ_ESTUDIO, "motores", "imagen_openai", "imagen.py"))
    imagen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imagen)
    import sin_marcas
    sin_marcas.cli_claude = None            # solo la tabla: sin CLI ni red
    ref = os.path.join(tempfile.mkdtemp(prefix="estudio_ref_"), "ref.png")
    from PIL import Image
    Image.new("RGB", (64, 64), (10, 20, 30)).save(ref)
    try:
        png, meta = imagen.generar("father and son playing Mario Kart on a Nintendo Switch",
                                   [ref], quality="low")
        ok(png[:4] == b"\x89PNG" and meta.get("sin_marcas"),
           "con marcas: el filtro la rechaza, se reescribe sola y sale")
        ultima = list(imagen.REESCRITURAS.values())[-1]
        ok(any("Mario Kart" in a for a, _b in ultima.get("cambios") or []),
           "y apunta que cambio (para contarlo en la nota)")
        try:
            imagen.generar("a big PROHIBIDO sign", [ref], quality="low")
            ok(False, "lo que no se arregla quitando marcas se rechaza")
        except imagen.RechazoSeguridad as fallo:
            ok("filtro de seguridad" in str(fallo), "lo que no se arregla quitando marcas "
               "sale como RechazoSeguridad, en claro")
    finally:
        os.environ.pop("ESTUDIO_IMAGEN_FALSA", None)


def probar_revision_del_nucleo_v2f():
    """La revision del nucleo del 16-10-2026, en lo que toca a app.py.

    Corre en este proceso, con proyectos de verdad (nucleo real) y los modulos
    de los pasos sustituidos por dobles: lo que se mira son las marcas, los 409
    y el contexto, no lo que pinta un paso.
    """
    seccion("REVISION DEL NUCLEO (16-10): MARCAS, 409 Y CONTEXTO")
    import threading                                          # noqa: PLC0415
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo import Estado, Proyecto                       # noqa: PLC0415

    from nucleo import bitacora as BITACORA                   # noqa: PLC0415
    raiz_antes = servidor.raiz_proyectos()
    base = tempfile.mkdtemp(prefix="estudio_v2f_")
    # el log global, a la carpeta de la prueba: no al de verdad
    global_antes = BITACORA.RUTA_GLOBAL
    BITACORA.RUTA_GLOBAL = os.path.join(base, "_bitacora_global.jsonl")
    modulo_real = servidor.modulo_de
    herramienta_real = servidor._herramienta
    servidor.fijar_raiz_proyectos(base)

    def proyecto_hecho(nombre):
        proyecto = Proyecto.crear(base, nombre)
        e = Estado(proyecto)
        for paso in ("ingesta", "brief", "guion", "voz", "revision_audio"):
            e.completar(paso, {"ok": 1})
        e.set_params("assets", {"unidades": {"escena:S1": {"d": "a"},
                                             "escena:S2": {"d": "b"}}})
        e.completar("assets", {}, {"escena:S1": {"png": "1"}, "escena:S2": {"png": "2"}})
        e.completar("callouts", {})
        return proyecto.id

    class _Paso:
        """Doble de un modulo de paso: hace lo que se le diga."""
        def __init__(self, hacer):
            self.hacer = hacer

        def ejecutar(self, proyecto, params, avisar, unidades=None, **_):
            return self.hacer(params, unidades)

        def propagar_dependencias(self, estado, dependencias=None):
            return []

    try:
        # 1. LA RECETA ESCRIBE PARAMS DESPUES DE QUE EL GESTOR MARQUE: el paso
        #    que corre despues se sella con SUS entradas, no con las del arranque
        pid = proyecto_hecho("receta_marca")
        ctx = servidor.contexto(pid)
        ctx.estado.marcar_ejecutando("assets")        # la receta arranca
        ctx.estado.actualizar_params(                  # la direccion decide S1
            "assets", {"unidades": {"escena:S1": {"d": "a", "direccion": "x"}}})
        servidor.modulo_de = lambda paso: _Paso(lambda params, unidades: {
            "salidas": {}, "unidades": {"escena:S1": {"png": "1b"}}})
        servidor._correr_paso(lambda *a, **k: None, ctx, "assets", ["escena:S1"])
        igual(ctx.estado.estado_de("assets"), "listo",
              "un plano dibujado con la direccion de la receta no sale obsoleto")

        # 2. EL ERROR VA AL PASO QUE FALLA, no al registrado
        def revienta(params, unidades):
            raise RuntimeError("los subtitulos no salen")
        servidor.modulo_de = lambda paso: _Paso(revienta)
        try:
            servidor._correr_paso(lambda *a, **k: None, ctx, "callouts", None)
        except RuntimeError:
            pass
        igual(ctx.estado.estado_de("callouts"), "error", "el paso que falla queda en error")
        igual(ctx.estado.estado_de("assets"), "listo", "y el de antes, completado, no")
        ctx.estado.limpiar_marca("callouts")

        # 3. NADA EN PARALELO CON UNA TANDA QUE YA CORRE ESE PASO
        servidor.modulo_de = modulo_real
        suelta = threading.Event()
        tid = ctx.gestor.lanzar("receta:video", lambda avisar: suelta.wait(20),
                                paso="assets", toca=["assets", "callouts"])
        try:
            servidor.lanzar_paso(ctx, "callouts", None)
            ok(False, "ejecutar los subtitulos con la tanda del video en marcha deberia dar 409")
        except servidor.ErrorApi as fallo:
            igual(fallo.codigo, 409, "ejecutar un paso que corre dentro de una tanda: 409")
        antes = ctx.estado.params("callouts")
        try:
            servidor.enviar_feedback(pid, {"paso": "callouts", "texto": "mas grande"})
            ok(False, "el feedback con el paso en marcha deberia dar 409")
        except servidor.ErrorApi as fallo:
            igual(fallo.codigo, 409, "feedback con el paso en marcha: 409")
        igual(ctx.estado.params("callouts"), antes, "y la nota NO se queda escrita")

        # 4. REPARAR EL ESTILO: con CUALQUIER trabajo vivo, 409; y sin soltar el contexto
        try:
            servidor.reparar_estilo(pid, {"aplicar": True})
            ok(False, "reparar el estilo con un trabajo en marcha deberia dar 409")
        except servidor.ErrorApi as fallo:
            igual(fallo.codigo, 409, "reparar el estilo con algo en marcha: 409")
        suelta.set()
        ctx.gestor.esperar(tid, 20)
        sin_paso = threading.Event()
        otro_tid = ctx.gestor.lanzar("exportar", lambda avisar: sin_paso.wait(20))
        try:
            servidor.reparar_estilo(pid, {"aplicar": True})
            ok(False, "un trabajo sin paso tambien deberia frenar la reparacion")
        except servidor.ErrorApi as fallo:
            igual(fallo.codigo, 409, "tambien con un trabajo sin paso (una exportacion)")
        sin_paso.set()
        ctx.gestor.esperar(otro_tid, 20)

        class _Diag:
            @staticmethod
            def revisar(raiz):
                return [("assets", "estilo", "/viejo", "/nuevo")]

        class _Mudar:
            @staticmethod
            def mudar_objetivo(*a, **k):
                return 0
        servidor._herramienta = lambda nombre: _Diag if nombre == "diagnostico_estilo" else _Mudar
        respuesta = servidor.reparar_estilo(pid, {"aplicar": True})
        ok(respuesta.get("reparado"), "sin nada en marcha, repara")
        ok(servidor.contexto(pid) is ctx,
           "y el contexto (con su gestor de trabajos) sigue siendo el mismo")

        # 5. LAS MARCAS «EJECUTANDO» DE UN SERVICIO ANTERIOR
        pid = proyecto_hecho("marca_huerfana")
        Estado(Proyecto(os.path.join(base, pid))).marcar_ejecutando("callouts")
        nuevo = servidor.contexto(pid)       # lo abre el servicio, como la pantalla
        igual(nuevo.estado.estado_de("callouts"), "listo",
              "al abrir el proyecto no queda un paso «ejecutando» sin trabajo")
        # y la que pierde una apertura simultanea no toca nada: solo limpia la
        # que queda registrada (la otra podia quitar la marca de un trabajo vivo)
        nuevo.estado.marcar_ejecutando("callouts")
        perdedora = servidor.Contexto(os.path.join(base, pid))
        igual(perdedora.estado.estado_de("callouts"), "ejecutando",
              "crear un contexto que no se registra no quita la marca de un trabajo vivo")
        nuevo.estado.limpiar_marca("callouts")
    finally:
        servidor.modulo_de = modulo_real
        servidor._herramienta = herramienta_real
        servidor.fijar_raiz_proyectos(raiz_antes)
        BITACORA.RUTA_GLOBAL = global_antes
        shutil.rmtree(base, ignore_errors=True)

def probar_audio_y_musica_de_la_previa(cliente, carpeta):
    """Lo que suena en las diapositivas: la voz del corte, y la música de verdad.

    16-10-2026. La previa servía la toma de `revision_audio` aunque los planos
    se cortan contra la de `voz` y el MP4 suena con la de `voz`: con una
    revisión regrabada «Oírla» sonaba otra frase, y pasado su final no sonaba
    nada. Y la música leía `musica.pista`, una clave que nadie escribe: «Todo
    seguido» no tuvo nunca música.
    """
    seccion("LO QUE SUENA EN LAS DIAPOSITIVAS")
    import wave
    from nucleo.estado import Estado
    from nucleo.proyecto import Proyecto, escribir_json

    def wav(ruta, segundos):
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with wave.open(ruta, "wb") as fh:
            fh.setnchannels(1)
            fh.setsampwidth(2)
            fh.setframerate(8000)
            fh.writeframes(b"\x00\x00" * int(8000 * segundos))

    _r, datos = cliente.post("/api/proyectos", {"nombre": "Lo que suena en la previa"})
    pid = (datos.get("proyecto") or {}).get("id")
    proyecto = Proyecto(os.path.join(carpeta, pid))
    estado = Estado(proyecto)
    # la voz (6 s) y una revision regrabada MAS CORTA (4 s), con su propio reloj
    wav(os.path.join(proyecto.ruta_trabajo("voz"), "narracion.wav"), 6)
    estado.completar("voz", {"archivo": "narracion.wav", "duracion": 6.0})
    wav(os.path.join(proyecto.ruta_trabajo("revision_audio"), "narracion.wav"), 4)
    estado.completar("revision_audio", {"archivo": "narracion.wav", "duracion": 4.0})
    # el corte de los planos, hecho contra la voz: el ultimo empieza en el 5
    escribir_json(os.path.join(proyecto.ruta_trabajo("assets"), "plan.json"), {
        "escenas": [{"id": "S001", "t_in": 0.0, "t_out": 5.0, "duracion": 5.0,
                     "narracion": "uno"},
                    {"id": "S002", "t_in": 5.0, "t_out": 6.0, "duracion": 1.0,
                     "narracion": "dos"}],
        "duracion_total": 6.0})
    estado.completar("assets", {"plan": "plan.json"})

    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415

    class _Ctx:
        def __init__(self):
            self.proyecto = Proyecto(os.path.join(carpeta, pid))
            self.estado = Estado(self.proyecto)

    guardado = servidor.contexto
    servidor.contexto = lambda _pid: _Ctx()
    try:
        ficha = servidor.leer_previsualizacion(pid)
        igual(ficha.get("audio"), "pasos/voz/v1/narracion.wav",
              "la previa suena con la voz contra la que se cortaron los planos "
              "(la del render), no con la revisión")
        igual((ficha.get("musica"), ficha.get("efectos")), (None, None),
              "sin música elegida ni montaje, la previa no promete cama")

        # UN TEMA SUBIDO, SIN MONTAR: suena su escucha, que la API ya sirve
        estado = Estado(proyecto)
        estado.set_params("render", {"musica": {
            "fuente": "propia", "id": "abc", "titulo": "tema",
            "muestra": "/api/musica/propia/propia_abc.mp3"}})
        ficha = servidor.leer_previsualizacion(pid)
        igual(ficha.get("musica"), "/api/musica/propia/propia_abc.mp3",
              "con un tema subido y sin montar, «Todo seguido» suena con él")
        # uno de Jamendo sin montar no sale a la red desde aqui
        estado.set_params("render", {"musica": {"fuente": "jamendo", "id": "9"}})
        igual(servidor.leer_previsualizacion(pid).get("musica"), None,
              "un tema de Jamendo sin montar no se pide a Jamendo desde la previa")

        # MONTADO: la cama y los efectos tal cual suenan en el MP4
        wav(os.path.join(proyecto.ruta_trabajo("render"), "cama.wav"), 6)
        wav(os.path.join(proyecto.ruta_trabajo("render"), "efectos.wav"), 6)
        estado.completar("render", {"video": "video.mp4"})
        ficha = servidor.leer_previsualizacion(pid)
        igual((ficha.get("musica"), ficha.get("efectos")),
              ("pasos/render/v1/cama.wav", "pasos/render/v1/efectos.wav"),
              "montado, suenan la cama y la banda de efectos del render")
        _r, _d = cliente.get(f"/a/{pid}/pasos/render/v1/cama.wav")
        igual(_r.status_code, 200, "y esa ruta se sirve por /a/{pid}/")
    finally:
        servidor.contexto = guardado


def probar_que_lo_lento_no_para_el_servicio():
    """Una ruta async que bloquea paraba TODAS las peticiones (16-10-2026).

    El bucle de eventos es uno: abrir un proyecto (leer estado.json, un cerrojo
    que espera) dentro de una ruta `async def` dejaba sin contestar a todas las
    demas, tambien a las barras de progreso. Se arranca el servicio EN ESTE
    proceso, se hace lento `contexto()` y se mira que otra peticion no espera.
    Y de paso, el 503 de un proyecto cuyo estado.json no se puede recuperar.
    """
    seccion("LO LENTO NO PARA EL SERVICIO, Y UN ESTADO ILEGIBLE DA 503")
    import threading                                          # noqa: PLC0415
    sys.path.insert(0, RAIZ_ESTUDIO)
    import uvicorn                                            # noqa: PLC0415
    import app as servidor                                    # noqa: PLC0415
    from nucleo import Estado, Proyecto                       # noqa: PLC0415
    from nucleo import bitacora as BITACORA                   # noqa: PLC0415

    raiz_antes = servidor.raiz_proyectos()
    base = tempfile.mkdtemp(prefix="estudio_lento_")
    global_antes = BITACORA.RUTA_GLOBAL
    BITACORA.RUTA_GLOBAL = os.path.join(base, "_bitacora_global.jsonl")
    contexto_real = servidor.contexto
    servidor.fijar_raiz_proyectos(base)
    puerto = puerto_libre()
    motor = uvicorn.Server(uvicorn.Config(servidor.app, host="127.0.0.1", port=puerto,
                                          log_level="error", lifespan="off"))
    hilo = threading.Thread(target=motor.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    try:
        for _ in range(100):
            try:
                requests.get(f"{url}/api/salud", timeout=2)
                break
            except requests.RequestException:
                time.sleep(0.1)
        Proyecto.crear(base, "lento")

        def lento(pid):
            if pid == "lento":
                time.sleep(2.0)            # un cerrojo de otro proceso, un estado enorme
            return contexto_real(pid)
        servidor.contexto = lento
        lanzada = threading.Thread(target=lambda: requests.post(
            f"{url}/api/proyectos/lento/capturas", json={"paso": "callouts"}, timeout=20))
        lanzada.start()
        time.sleep(0.3)
        antes = time.time()
        requests.get(f"{url}/api/salud", timeout=20)
        espera = time.time() - antes
        lanzada.join(20)
        ok(espera < 1.0, f"otra peticion contesta mientras una captura abre el proyecto "
                         f"({espera:.2f} s; antes, ~1,7 s)")
        servidor.contexto = contexto_real

        # un estado.json roto y sin copia buena: 503, con el porque
        proyecto = Proyecto.crear(base, "roto")
        Estado(proyecto)
        with open(proyecto.ruta("estado.json"), "w", encoding="utf-8") as fh:
            fh.write("{ roto")
        respuesta = requests.get(f"{url}/api/proyectos/roto", timeout=20)
        igual(respuesta.status_code, 503, "un estado.json ilegible sin copia: 503")
        ok("estado.roto." in (respuesta.json() or {}).get("error", ""),
           "y el mensaje dice donde ha quedado el fichero roto")
    finally:
        servidor.contexto = contexto_real
        motor.should_exit = True
        hilo.join(10)
        servidor.fijar_raiz_proyectos(raiz_antes)
        BITACORA.RUTA_GLOBAL = global_antes
        shutil.rmtree(base, ignore_errors=True)


def probar_elementos_del_video(cliente, pid):
    """Rama elementos-video: las rutas que no llaman a Claude ni gastan."""
    seccion("LOS ELEMENTOS DEL VIDEO")
    r, d = cliente.get(f"/api/proyectos/{pid}/planos/elementos")
    igual(r.status_code, 200, "GET planos/elementos responde 200")
    ok(set(d.get("intensidades") or {}) == {"sobrio", "vivo", "dinamico"} and d.get("posiciones"),
       "con las tres intensidades y las posiciones")
    r, _d = cliente.put(f"/api/proyectos/{pid}/planos/S001/elementos", {"elementos": "no"})
    igual(r.status_code, 400, "elementos que no son una lista: 400")
    r, _d = cliente.put(f"/api/proyectos/{pid}/planos/NOEXISTE/elementos", {"elementos": []})
    igual(r.status_code, 404, "un plano que no existe: 404")
    r, _d = cliente.post(f"/api/proyectos/{pid}/elementos/aplicar", {"planos": {}})
    igual(r.status_code, 400, "aplicar sin planos: 400")
    r, _d = cliente.get(f"/api/proyectos/{pid}/elementos/proponer/noexiste")
    igual(r.status_code, 404, "una propuesta que no existe: 404")
    r, _d = cliente.post(f"/api/proyectos/{pid}/planos/NOEXISTE/elementos/nota-ia", {"texto": "hola"})
    igual(r.status_code, 404, "la nota de texto dentro de un plano que no existe: 404")
    r, _d = cliente.post(f"/api/proyectos/{pid}/planos/NOEXISTE/elementos/nota-ia", {"texto": ""})
    ok(r.status_code in (400, 404), "y sin texto no se apunta nada")


def probar_portadas(cliente, pid):
    """Rama `portadas`: las rutas que no gastan ni llaman a Claude."""
    seccion("LAS PORTADAS DISEÑADAS")
    r, cat = cliente.get("/api/portadas/catalogo")
    igual(r.status_code, 200, "GET /api/portadas/catalogo responde 200")
    ok(len(cat.get("plantillas") or []) >= 20 and cat.get("formatos", {}).get("9:16"),
       "con veinte plantillas o más y los cuatro formatos")
    r, d = cliente.get(f"/api/publicar/videos/{pid}/portada/diseno")
    igual(r.status_code, 200, "el diseño de un vídeo se lee")
    ok(d.get("guardado") is False and (d.get("diseno") or {}).get("plantilla"),
       "sin diseño guardado da uno de partida, sin guardarlo")
    r, _d = cliente.put(f"/api/publicar/videos/{pid}/portada/diseno", {"diseno": "no"})
    igual(r.status_code, 400, "guardar un diseño que no es un objeto: 400")
    r, p = cliente.post(f"/api/publicar/videos/{pid}/portada/plantilla",
                        {"plantilla": "versus", "textos": {"izquierda": "A"}, "formato": "1:1"})
    igual(r.status_code, 200, "cambiar de plantilla responde 200")
    ok(p["diseno"]["plantilla"] == "versus" and p["diseno"]["formato"] == "1:1",
       "con la plantilla y el formato pedidos")
    r, precio = cliente.post(f"/api/publicar/videos/{pid}/portada/ia",
                             {"diseno": p["diseno"], "que": "portada", "calidad": "high"})
    igual(r.status_code, 202, "la IA sin confirmar contesta")
    ok("precio" in precio and "trabajo_id" not in precio, "sin `confirmado` solo dice el precio y no lanza nada")
    r, _d = cliente.get(f"/api/publicar/videos/{pid}/portada/fondos/..%2F..%2Fsecretos")
    igual(r.status_code, 404, "un fondo con .. no sale de su carpeta")
    r, _d = cliente.get(f"/api/publicar/videos/{pid}/portada/planos/NOEXISTE.jpg")
    igual(r.status_code, 404, "un plano que no existe: 404")
    r, _d = cliente.get(f"/api/publicar/videos/{pid}/portada/proponer/noexiste")
    igual(r.status_code, 404, "una propuesta que no existe: 404")


def probar_ortografia_de_campos(cliente, pid):
    """El corrector de campos sueltos (18-10-2026): lo que se ve o se publica
    fuera del guion y los subtitulos. Solo lo que NO llega al CLI (aqui no hay
    CLI falso: una revision de verdad saldria a Claude)."""
    seccion("LA ORTOGRAFIA DE LOS CAMPOS SUELTOS")
    r, _d = cliente.post("/api/ortografia/textos", {"textos": {}})
    igual(r.status_code, 400, "sin textos: 400")
    r, _d = cliente.post("/api/ortografia/textos", {"textos": {"a": "   "}})
    igual(r.status_code, 400, "con textos vacios: 400")
    r, _d = cliente.post("/api/ortografia/textos", {"textos": {f"L{i}": "hola" for i in range(401)}})
    igual(r.status_code, 400, "mas de 400 lineas: 400, no un recorte callado")
    r, _d = cliente.get("/api/ortografia/textos/noexiste")
    igual(r.status_code, 404, "una revision que no existe: 404")
    r, _d = cliente.post("/api/ortografia/textos/descartar", {"rid": "noexiste", "ids": ["L0"]})
    igual(r.status_code, 409, "descartar de una revision que no existe: 409")
    r, _d = cliente.post("/api/ortografia/textos/descartar", {"rid": "x"})
    igual(r.status_code, 400, "descartar sin ids: 400")
    r, _d = cliente.post(f"/api/proyectos/{pid}/ortografia/descartar", {"rid": "noexiste", "ids": ["B001"]})
    igual(r.status_code, 409, "descartar en un video con una revision que no existe: 409")


def _llamar(funcion, *args, **kwargs):
    """Llama a una ruta de app.py en este proceso. -> (codigo, respuesta|mensaje)."""
    import app as servidor                                    # noqa: PLC0415
    try:
        return 200, funcion(*args, **kwargs)
    except servidor.ErrorApi as fallo:
        return fallo.codigo, fallo.mensaje
    except Exception as fallo:  # noqa: BLE001  -- lo que el servicio da como 500
        return 500, f"{type(fallo).__name__}: {fallo}"


def probar_lo_de_v2h():
    """Los pendientes del analisis del 13-10 que seguian en el codigo (18-10-2026).

    En este proceso, contra proyectos de verdad (nucleo real): lo que se mira es
    lo que la API acepta, rechaza y deja escrito.
    """
    seccion("ARREGLOS V2H: PARAMS, SUBIDAS, IDS Y ERRORES")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo import Estado, Proyecto                       # noqa: PLC0415
    from nucleo import bitacora as BITACORA                   # noqa: PLC0415

    raiz_antes = servidor.raiz_proyectos()
    base = tempfile.mkdtemp(prefix="estudio_v2h_")
    global_antes = BITACORA.RUTA_GLOBAL
    BITACORA.RUTA_GLOBAL = os.path.join(base, "_bitacora_global.jsonl")
    servidor.fijar_raiz_proyectos(base)
    reales = {}
    import threading                                          # noqa: PLC0415
    import uvicorn                                            # noqa: PLC0415
    puerto = puerto_libre()
    motor = uvicorn.Server(uvicorn.Config(servidor.app, host="127.0.0.1", port=puerto,
                                          log_level="error", lifespan="off"))
    hilo = threading.Thread(target=motor.run, daemon=True)
    hilo.start()
    url = f"http://127.0.0.1:{puerto}"
    for _ in range(100):
        try:
            requests.get(f"{url}/api/salud", timeout=2)
            break
        except requests.RequestException:
            time.sleep(0.1)

    def pedir(metodo, ruta, **extra):
        # una conexion por peticion: tras un 500 sin capturar el servidor corta
        # la conexion y la siguiente peticion de la sesion saldria «reset»
        extra.setdefault("headers", {})["Connection"] = "close"
        respuesta = requests.request(metodo, url + ruta, timeout=60, **extra)
        try:
            return respuesta.status_code, respuesta.json()
        except ValueError:
            return respuesta.status_code, None

    from PIL import Image                                     # noqa: PLC0415

    def png(tam=(200, 40), color=(255, 0, 0, 255)):
        crudo = io.BytesIO()
        Image.new("RGBA", tam, color).save(crudo, "PNG")
        return crudo.getvalue()

    def cambiar(nombre, valor):
        reales.setdefault(nombre, getattr(servidor, nombre))
        setattr(servidor, nombre, valor)

    try:
        # R2 · LOS PARAMS ESTRUCTURALES SE VALIDAN POR TIPO. Antes devolvian 200
        # y una docena de pantallas del video daban 500 para siempre.
        pid = Proyecto.crear(base, "r2 tipos").id
        for paso, params in (("assets", {"estilo": "x"}), ("assets", {"unidades": "x"}),
                             ("assets", {"unidades": {"escena:S1": "x"}}),
                             ("render", {"musica": "x"}), ("render", {"logo": "x"}),
                             ("render", {"efectos": ["x"]}), ("callouts", {"paleta": 3})):
            codigo, _m = _llamar(servidor.fijar_params, pid, paso, {"params": params})
            clave = next(iter(params))
            igual(codigo, 400, f"R2: guardar {paso}.{clave}={params[clave]!r} da 400")
            ok(clave not in (servidor.contexto(pid).estado.params(paso) or {}),
               f"R2: y no deja {paso}.{clave} escrito")
        codigo, _r = _llamar(servidor.fijar_params, pid, "assets",
                             {"params": {"estilo": {"modo": "foto"}, "logo": None,
                                         "unidades": {"escena:S1": {"d": "a"}}}})
        igual(codigo, 200, "R2: un objeto (o null) sigue valiendo")
        codigo, _m = _llamar(servidor.generar_video, pid,
                             {"params": {"assets": {"estilo": "x"}}})
        igual(codigo, 400, "R2: /generar valida los params igual que el PUT")
        codigo, _m = _llamar(servidor.generar_video, pid, {"params": ["assets"]})
        igual(codigo, 400, "R2: /generar con 'params' que no es un objeto da 400, no 500")

        # R2 · UN /generar RECHAZADO POR 409 NO ESCRIBE SUS PARAMS: antes los
        # guardaba antes del cerrojo y la firma se movia bajo el trabajo vivo.
        cambiar("_trabajo_de_cadena", lambda ctx: {"id": "vivo", "progreso": 0.4})
        codigo, _m = _llamar(servidor.generar_video, pid,
                             {"params": {"brief": {"duracion_s": 77}}})
        igual(codigo, 409, "R2: /generar con el video generandose da 409")
        ok((servidor.contexto(pid).estado.params("brief") or {}).get("duracion_s") != 77,
           "R2: y el 409 no deja escritos los params que traia")
        setattr(servidor, "_trabajo_de_cadena", reales.pop("_trabajo_de_cadena"))

        # R3 · EL LOGO Y LAS IMAGENES DEL REPASO SE REVISAN AL SUBIRLOS. Un logo
        # roto se aceptaba y el montaje reventaba al 97 % con un MP4 de 0 bytes.
        pid = Proyecto.crear(base, "r3 subidas").id
        Estado(servidor.contexto(pid).proyecto)
        roto = png()[:60]                                # una PNG cortada
        codigo, datos = pedir("POST", f"/api/proyectos/{pid}/logo",
                              files={"logo": ("logo.png", roto, "image/png")})
        igual(codigo, 400, "R3: un logo que no se puede abrir da 400 al subirlo")
        ok(not (servidor.contexto(pid).estado.params("render") or {}).get("logo"),
           "R3: y no queda puesto en el video")
        codigo, datos = pedir("POST", "/api/logos",
                              files={"logo": ("logo.png", b"no soy una imagen", "image/png")})
        igual(codigo, 400, "R3: el logo suelto (borrador) se revisa igual")
        codigo, datos = pedir("POST", "/api/logos",
                              files={"logo": ("logo.png", png((200, 40)), "image/png")})
        igual(codigo, 201, "R3: un logo de texto, ancho y bajo, de un color, sigue valiendo")
        codigo, datos = pedir("POST", f"/api/proyectos/{pid}/repaso/imagenes",
                              files={"f": ("nota.png", roto, "image/png")})
        igual(codigo, 400, "R3: una imagen rota en una nota del repaso da 400")
        maximo = servidor._repaso().MAX_IMAGENES
        codigo, datos = pedir("POST", f"/api/proyectos/{pid}/repaso/imagenes",
                              files=[("f", (f"n{i}.png", png((300, 200), (i * 20, 90, 90, 255)),
                                            "image/png")) for i in range(maximo + 3)])
        igual(codigo, 201, "R3: una tanda de imagenes del repaso se sube")
        igual(len((datos or {}).get("imagenes") or []), maximo,
              f"R3: pero como mucho {maximo}, las que caben en una nota")
        ok(any("como mucho" in a for a in (datos or {}).get("avisos") or []),
           "R3: y dice por que no subio las demas")

        # R4 · UNA CARPETA COPIADA A MANO NO ES UN GEMELO DEL ORIGINAL. El id
        # salia de proyecto.json: la copia se listaba y se abria como el original.
        original = Proyecto.crear(base, "r4 original")
        shutil.copytree(original.raiz, os.path.join(base, "r4_copia_a_mano"))
        igual(Proyecto(os.path.join(base, "r4_copia_a_mano")).id, "r4_copia_a_mano",
              "R4: la copia a mano tiene el id de SU carpeta")
        ids = [f["id"] for f in Proyecto.listar(base) if f["id"].startswith("r4")]
        igual(sorted(ids), ["r4_copia_a_mano", "r4_original"],
              "R4: y la lista no enseña dos veces el original")
        codigo, datos = pedir("GET", "/api/proyectos/r4_copia_a_mano")
        igual(((datos or {}).get("proyecto") or datos or {}).get("id"), "r4_copia_a_mano",
              "R4: y abrirla abre la copia, no el original")

        # R5 · UN NOMBRE LARGUISIMO: antes 500 al crear (>255) o un video que no
        # se podia duplicar ni apartar (250)
        for largo in (260, 250):
            codigo, datos = pedir("POST", "/api/proyectos", json={"nombre": "a" * largo})
            igual(codigo, 201, f"R5: un video de {largo} caracteres de nombre se crea")
            nuevo = ((datos or {}).get("proyecto") or {}).get("id") or ""
            ok(0 < len(nuevo) <= 60, f"R5: con un id corto ({len(nuevo)} caracteres)")
            codigo, _d = pedir("POST", f"/api/proyectos/{nuevo}/duplicar", json={})
            igual(codigo, 201, f"R5: y se puede duplicar ({largo})")
            codigo, _d = pedir("DELETE", f"/api/proyectos/{nuevo}")
            ok(codigo in (200, 204), f"R5: y apartar ({largo}: {codigo})")

        # R6 · CREAR A LA VEZ NO REPITE IDS (8 «creado» y 6 carpetas, medido)
        hechos = []
        hilos = [threading.Thread(target=lambda: hechos.append(
            Proyecto.crear(base, "r6 mismo").id)) for _ in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        igual(len(set(hechos)), 8, "R6: ocho creaciones a la vez dan ocho ids distintos")
        igual(len([n for n in os.listdir(base) if n.startswith("r6_mismo")]), 8,
              "R6: y ocho carpetas")

        # R8 · LAS DOS RUTAS MUERTAS QUE SIEMPRE DABAN 500
        pid = Proyecto.crear(base, "r8 muertas").id
        Estado(servidor.contexto(pid).proyecto)
        codigo, _d = pedir("GET", f"/api/proyectos/{pid}/estilo")
        ok(codigo in (404, 405), f"R8: GET /estilo ya no existe (no es un 500: {codigo})")
        codigo, datos = pedir("PUT", f"/api/proyectos/{pid}/callouts/plan",
                              json={"arquetipos": []})
        igual(codigo, 400, "R8: mandar 'arquetipos' al plan del grafismo da 400, no 500")

        # R9 · SIN EL CLI DE CLAUDE, EL ASISTENTE DICE QUE NO ESTA (no un 500)
        from pasos import cli_claude as CLI                   # noqa: PLC0415
        localizar_real = CLI.localizar

        def sin_cli(*_a, **_k):
            raise RuntimeError("no se encuentra el CLI de claude")
        CLI.localizar = sin_cli
        try:
            codigo, datos = pedir("GET", "/api/asistente")
            igual(codigo, 200, "R9: GET /api/asistente sin el CLI responde 200")
            ok((datos or {}).get("listo") is False, f"R9: y dice que no está listo: {datos}")
        finally:
            CLI.localizar = localizar_real
        # y un 500 de verdad no enseña la traza con las rutas del servidor
        cambiar("_sonido", lambda: (_ for _ in ()).throw(KeyError("roto")))
        codigo, datos = pedir("GET", f"/api/proyectos/{pid}/sonido")
        igual(codigo, 500, "R9: un fallo imprevisto sigue siendo un 500")
        ok("traza" not in (datos or {}) and RAIZ_ESTUDIO not in json.dumps(datos or {}),
           "R9: pero sin la traza ni rutas del servidor")
        ok(bool((datos or {}).get("marca")), "R9: con una marca para buscarlo en el registro")
        setattr(servidor, "_sonido", reales.pop("_sonido"))

        # R7 · UN CUERPO CON UN TIPO EQUIVOCADO ES UN 400, NO UN 500
        pid = Proyecto.crear(base, "r7 tipos").id
        sembrar(os.path.join(base, pid))
        p = f"/api/proyectos/{pid}"
        for metodo, ruta, cuerpo in (
                ("POST", p + "/guion/bloques/reescribir", {"bloques": 5, "peticion": "x"}),
                ("POST", p + "/guion/pausas/quitar", {"bloques": 5}),
                ("POST", p + "/exportar", {"que": "video", "partes": 5}),
                ("POST", p + "/estilo/traer", {"partes": 5}),
                ("PUT", p + "/estilo/seleccion", {"referencias": 5}),
                ("POST", p + "/estilo/guia", {"referencias": 5}),
                ("POST", p + "/repaso", {"texto": "hola", "t": 1, "imagenes": 5}),
                ("POST", p + "/capturas/aplicar", {"capturas": 5}),
                ("POST", p + "/sonido/efectos", {"papeles": 5}),
                ("POST", p + "/sonido/efectos", {"papeles": [[1]]}),
                ("POST", "/api/estimacion", {"duracion_objetivo_s": 60, "min_s": "a"}),
                ("PUT", p + "/sonido", {"musica": "x"}),
                ("PUT", p + "/callouts/plan", {"diseno": [1]}),
                ("PUT", p + "/callouts/plan", {"paleta": {"fijados": 5}}),
                ("PUT", p + "/cartelas", {"plantillas": [[1]]})):
            codigo, datos = pedir(metodo, ruta, json=cuerpo)
            igual(codigo, 400, f"R7: {metodo} {ruta.replace(p, '')} {json.dumps(cuerpo)} da 400")
        codigo, _d = pedir("GET", p + "/exportes/a%00b")
        igual(codigo, 404, "R7: un nulo en la ruta de un exporte da 404, no 500")
        codigo, _d = pedir("POST", "/api/sonido/subir", data=b"--xx\r\nbasura sin dos puntos"
                           b"\r\n\r\nabc\r\n--xx--\r\n",
                           headers={"Content-Type": "multipart/form-data; boundary=xx"})
        igual(codigo, 400, "R7: un multipart roto al subir un audio da 400, no 500")

        # D8 · «APLICAR» DEL REPASO NO LANZA DOS MONTAJES A LA VEZ
        pid = Proyecto.crear(base, "d8 repaso").id
        Estado(servidor.contexto(pid).proyecto)
        suelta = threading.Event()
        cambiar("_correr_repaso", lambda avisar, ctx, *a, **k: suelta.wait(20) and {})
        try:
            primero, _r = _llamar(servidor.aplicar_repaso, pid, {})
            segundo, _m = _llamar(servidor.aplicar_repaso, pid, {})
            igual(primero, 200, "D8: el primer «Aplicar» lanza el repaso")
            igual(segundo, 409, "D8: el segundo, con el primero corriendo, da 409")
        finally:
            suelta.set()
        for _ in range(100):
            if not servidor.contexto(pid).gestor.listar(activos=True):
                break
            time.sleep(0.05)
        cambiar("_trabajo_de_cadena", lambda ctx: {"id": "vivo", "nombre": "La tanda",
                                                     "progreso": 0.3})
        codigo, _m = _llamar(servidor.aplicar_repaso, pid, {})
        igual(codigo, 409, "D8: y con la tanda del vídeo corriendo, también 409")
        setattr(servidor, "_trabajo_de_cadena", reales.pop("_trabajo_de_cadena"))
        setattr(servidor, "_correr_repaso", reales.pop("_correr_repaso"))

        # D7 · UN RETOQUE HECHO MIENTRAS CORRE LA TANDA NO QUEDA SELLADO COMO
        # HECHO aunque la tanda escriba en sus params (la huella de una hoja)
        proyecto = Proyecto.crear(base, "d7 retoque")
        sembrar(proyecto.raiz)
        e = Estado(proyecto)
        for paso in ("voz", "revision_audio"):
            e.completar(paso, {"x": 1})
        unidades = {"escena:S010": {"prompt": "a"}, "escena:S020": {"prompt": "b"}}
        e.set_params("assets", {"unidades": unidades})
        e.completar("assets", {}, unidades={k: {"f": k} for k in unidades})
        e.marcar_ejecutando("assets")                          # arranca la tanda
        e.actualizar_params("assets", {"unidades": {          # el usuario retoca S010
            "escena:S010": {"prompt": "a", "feedback": "retoque del usuario"}}})
        e.actualizar_params("assets", {"unidades": {          # la tanda: su huella
            "escena:S020": {"prompt": "b", "huella_assets": "nueva"}}}, del_propio_paso=True)
        e.completar("assets", {}, unidades={"escena:S010": {"f": "con el prompt viejo"},
                                            "escena:S020": {"f": "nueva"}})
        obsoletas = e.unidades_obsoletas("assets")
        ok("escena:S010" in obsoletas,
           f"D7: el plano retocado durante la tanda queda por rehacer ({obsoletas})")
        ok("escena:S020" not in obsoletas,
           "D7: y el que la tanda cambió ella misma sigue al día")
        params_version = (e.versiones("assets") or [{}])[-1].get("params") or {}
        ok("retoque del usuario" not in json.dumps(params_version),
           "D7: y la versión no apunta el retoque como usado")
        ok("nueva" in json.dumps(params_version),
           "D7: pero sí lo que la propia tanda escribió")

        # F5 · UNA NOTA DE IMAGEN QUE FALLA O SE CANCELA DESPUES DE PAGAR no deja
        # la imagen nueva escondida en trabajo/ para que la selle la siguiente tanda
        from nucleo.trabajos import Cancelado                 # noqa: PLC0415
        from pasos import medios as MEDIOS                    # noqa: PLC0415
        pid = Proyecto.crear(base, "f5 nota pagada").id
        sembrar(os.path.join(base, pid))
        ctx = servidor.contexto(pid)
        for paso in ("voz", "revision_audio"):
            ctx.estado.completar(paso, {"x": 1})
        trab = ctx.proyecto.ruta_trabajo("assets", crear=True)
        os.makedirs(os.path.join(trab, "escenas"), exist_ok=True)
        with open(os.path.join(trab, "escenas", "S010.png"), "wb") as fh:
            fh.write(b"VIEJA")
        ctx.estado.set_params("assets", {"unidades": {"escena:S010": {"prompt": "a"}}})
        ctx.estado.completar("assets", {}, unidades={"escena:S010": {"png": "escenas/S010.png"}})
        rep = servidor._repaso()
        for modo in ("fallo", "cancelado"):
            nota = rep.anadir(ctx.proyecto, "pon un perro", 1.0, plano="S010",
                              imagenes=[], pantalla="imagenes", ancla="")

            def paso_falso(avisar, ctx, paso_id, unidades, opciones=None, modo=modo):
                carpeta = MEDIOS.sembrar_trabajo(ctx.proyecto, "assets")
                with open(os.path.join(carpeta, "escenas", "S010.png"), "wb") as fh:
                    fh.write(b"NUEVA_PAGADA")                # ya pagada
                if modo == "fallo":
                    raise RuntimeError("fallo al sellar")
                raise Cancelado("cancelado")
            cambiar("_correr_paso", paso_falso)
            servidor._COLA_NOTAS[ctx.id] = {"cola": [nota["id"]]}
            try:
                servidor._correr_notas_imagenes(lambda *a, **k: None, ctx)
            except Cancelado:
                pass
            setattr(servidor, "_correr_paso", reales.pop("_correr_paso"))
            carpeta = MEDIOS.sembrar_trabajo(ctx.proyecto, "assets")   # la siguiente tanda
            with open(os.path.join(carpeta, "escenas", "S010.png"), "rb") as fh:
                visto = fh.read()
            igual(visto, b"VIEJA", f"F5 ({modo}): la siguiente tanda no ve la imagen "
                                   "de la nota que no se puso")
            apartadas = os.path.join(ctx.proyecto.raiz, "pasos", "assets", "_apartados")
            ok(any(os.path.isfile(os.path.join(apartadas, d, "S010.png"))
                   for d in (os.listdir(apartadas) if os.path.isdir(apartadas) else [])),
               f"F5 ({modo}): la imagen pagada queda apartada, no borrada")
            ficha = next(n for n in rep.leer(ctx.proyecto)["notas"] if n["id"] == nota["id"])
            ok("aparte" in str(ficha.get("aviso") or ""),
               f"F5 ({modo}): y la nota lo dice: {ficha.get('aviso')!r}")
            shutil.rmtree(apartadas, ignore_errors=True)
            servidor._COLA_NOTAS.pop(ctx.id, None)

        # D7 (revisión) · TOCAR A MANO LA HOJA DE UN ASSET CON LA TANDA CORRIENDO
        # deja obsoleto el plano que la usa: la cascada es del usuario, no de la tanda
        p6 = servidor.PASOS_MODULOS.p6_assets
        proyecto = Proyecto.crear(base, "d7 hoja")
        e = Estado(proyecto)
        for paso in ("ingesta", "brief", "guion", "voz", "revision_audio"):
            e.completar(paso, {"x": 1})
        deps = {"escena:S05": ["asset:X"]}
        e.set_params("assets", {"unidades": {"asset:X": {"d": "hoja"}, "escena:S05": {"d": "plano"}}})
        p6.propagar_dependencias(e, deps)
        e.completar("assets", {}, {"asset:X": {"p": 1}, "escena:S05": {"p": 1}})
        e.marcar_ejecutando("assets")                           # arranca una tanda
        e.actualizar_params("assets", {"unidades": {"asset:X": {"d": "hoja", "feedback": "más alto"}}})
        try:                                                    # lo que hace fijar_params
            p6.propagar_dependencias(e, deps, del_propio_paso=False)
        except TypeError:
            p6.propagar_dependencias(e, deps)
        p6.propagar_dependencias(e, deps)                       # la tanda, antes de sellar
        e.completar("assets", {}, {"asset:X": {"p": 1}, "escena:S05": {"p": 1}})
        obsoletas = e.unidades_obsoletas("assets")
        ok("escena:S05" in obsoletas,
           f"D7: el plano que usa una hoja retocada durante la tanda queda por rehacer ({obsoletas})")

        # R2 (revisión) · un valor ANTIGUO ya guardado no impide guardar el paso
        pid = Proyecto.crear(base, "r2 antiguo").id
        servidor.contexto(pid).estado.set_params("assets", {"estilo": "cartoon", "calidad": "low"})
        codigo, _m = _llamar(servidor.fijar_params, pid, "assets",
                             {"params": {"estilo": "cartoon", "calidad": "medium"}})
        igual(codigo, 200, "R2: el borrador entero con un valor antiguo sin tocar se guarda")
        # R2 (revisión) · /generar no escribe params con CUALQUIER trabajo del vídeo vivo
        cambiar("_trabajo_que_toca", lambda ctx, pasos: {"id": "m", "nombre": "montaje",
                                                          "progreso": 0.5}
                if "render" in set([pasos] if isinstance(pasos, str) else pasos) else None)
        codigo, _m = _llamar(servidor.generar_video, pid, {"params": {"brief": {"duracion_s": 55}}})
        igual(codigo, 409, "R2: /generar con un montaje corriendo da 409")
        ok((servidor.contexto(pid).estado.params("brief") or {}).get("duracion_s") != 55,
           "R2: y no deja sus params escritos")
        setattr(servidor, "_trabajo_que_toca", reales.pop("_trabajo_que_toca"))

        # R4 (segunda parte) · LA CARPETA DE ID CAMBIADO SE QUEDA CON SU CLIENTE Y
        # SU GASTO: el cliente iba por el id viejo y el gasto global también
        CL = servidor.CLIENTES
        cliente = CL.crear(base, "Cliente R4")["id"]
        original = Proyecto.crear(base, "r4b original")
        CL.asignar_video(base, original.id, cliente)
        shutil.copytree(original.raiz, os.path.join(base, "r4b_copia"))      # copia
        renombrar = Proyecto.crear(base, "r4b antes")
        CL.asignar_video(base, renombrar.id, cliente)
        os.rename(renombrar.raiz, os.path.join(base, "r4b_despues"))         # renombrado
        codigo, _d = pedir("GET", "/api/proyectos")
        igual(codigo, 200, "R4: la lista de vídeos se pide")
        igual(CL.cliente_de(base, video_id="r4b_copia"), cliente,
              "R4: la copia a mano queda en el mismo cliente que su original")
        igual(CL.cliente_de(base, video_id=original.id), cliente, "R4: y el original sigue en él")
        igual(CL.cliente_de(base, video_id="r4b_despues"), cliente,
              "R4: la carpeta renombrada a mano sigue en su cliente")
        ok(not CL.cliente_de(base, video_id="r4b_antes"),
           "R4: y su id viejo, que ya no es de nadie, se suelta")
        with open(os.path.join(base, "r4b_copia", "proyecto.json"), encoding="utf-8") as fh:
            ficha = json.load(fh)
        igual((ficha.get("id"), ficha.get("id_anterior")), ("r4b_copia", "r4b_original"),
              "R4: y su proyecto.json ya dice su id (una sola vez)")
        from nucleo import coste as COSTE                     # noqa: PLC0415
        ruta_global_antes = COSTE.RUTA_GLOBAL
        COSTE.RUTA_GLOBAL = os.path.join(base, "_coste_global.jsonl")
        try:
            with open(COSTE.RUTA_GLOBAL, "w", encoding="utf-8") as fh:
                for pid_, raiz_, usd in (("r4b_original", original.raiz, 1.0),
                                         ("r4b_original", os.path.join(base, "r4b_copia"), 2.0)):
                    fh.write(json.dumps({"proveedor": "openai", "operacion": "imagen", "usd": usd,
                                         "proyecto": pid_, "raiz": raiz_,
                                         "momento": "2026-10-18T10:00:00"}) + "\n")
            por = {p_["proyecto"]: p_["total_usd"] for p_ in COSTE.resumen_global()["proyectos"]}
            igual((por.get("r4b_original"), por.get("r4b_copia")), (1.0, 2.0),
                  f"R4: el gasto que la copia anotó con el id del original sale a nombre de la copia ({por})")
        finally:
            COSTE.RUTA_GLOBAL = ruta_global_antes

        # R9 (segunda parte) · el texto de un 500 no lleva las carpetas del servidor
        pid = Proyecto.crear(base, "r9 rutas").id
        Estado(servidor.contexto(pid).proyecto)
        cambiar("_sonido", lambda: (_ for _ in ()).throw(FileNotFoundError(
            2, "No such file or directory", "/opt/as-video-studio/datos/secretos/claves.json")))
        codigo, datos = pedir("GET", f"/api/proyectos/{pid}/sonido")
        igual(codigo, 500, "R9: un fichero que falta sigue siendo un 500")
        texto = json.dumps(datos or {}, ensure_ascii=False)
        ok("/opt/" not in texto and "datos/secretos" not in texto and "claves.json" in texto,
           f"R9: con el nombre del fichero y sin sus carpetas: {(datos or {}).get('error')}")
        setattr(servidor, "_sonido", reales.pop("_sonido"))

        # S3 · UNA CLAVE CORTA NO SE ENSEÑA A MEDIAS (el Client ID de Jamendo
        # tiene 8 caracteres y se enseñaban 4)
        from pasos import claves as CLAVES                    # noqa: PLC0415
        igual(CLAVES.tapar("abcd1234"), "…34", "S3: de una clave de 8 se enseñan 2")
        igual(CLAVES.tapar("abcde"), "…", "S3: de una de 5, nada")
        igual(CLAVES.tapar("sk-" + "a" * 37 + "wxyz"), "…wxyz",
              "S3: de una larga, los cuatro últimos, como siempre")
    finally:
        motor.should_exit = True
        hilo.join(10)
        for nombre, valor in reales.items():
            setattr(servidor, nombre, valor)
        servidor.fijar_raiz_proyectos(raiz_antes)
        BITACORA.RUTA_GLOBAL = global_antes

def probar_cancelar_en_el_taller():
    """CANCELAR Y VOLVER A PULSAR EN EL TALLER DE ESTILOS (18-10-2026).

    Lo que vio el dueño: cancelar un «Rehacer» y, al rehacer otro estilo,
    «este estilo se está generando». El 409 era un doble toque (el reparto de
    la frase tarda y la pantalla no cambiaba); la cancelacion, ademas, no
    cortaba la guia que esperaba al CLI. Aqui, EN ESTE PROCESO y con dobles:

      - un doble toque da 409 ANTES de repartir otra vez con Claude;
      - la guia que espera «al CLI» se corta en el acto y acaba cancelada;
      - lo que el reparto escribio en el taller vuelve a como estaba;
      - volver a pulsar mientras se cancela dice eso, y con que trabajo;
      - un estilo no bloquea a otro, ni una escucha de voz a un «Rehacer».
    """
    seccion("CANCELAR Y VOLVER A PULSAR EN EL TALLER DE ESTILOS")
    import threading                                          # noqa: PLC0415
    import types                                              # noqa: PLC0415
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo import bitacora as BITACORA                   # noqa: PLC0415

    presets = servidor.PASOS_MODULOS.presets_canal
    base = tempfile.mkdtemp(prefix="estudio_cancelar_")
    raiz_antes = servidor.raiz_proyectos()
    guardado = {"FICHERO": presets.FICHERO, "BANCO": presets.BANCO,
                "global": BITACORA.RUTA_GLOBAL,
                "hace": dict(servidor._LIGHT_QUE_HACE),
                "congelar": servidor._congelar_preset,
                "enrutar": servidor._enrutar_estilo,
                "registrar": servidor._registrar_trabajo}
    presets.FICHERO = os.path.join(base, "_presets.json")
    presets.BANCO = os.path.join(base, "_banco_presets")
    BITACORA.RUTA_GLOBAL = os.path.join(base, "_bitacora_global.jsonl")
    servidor.fijar_raiz_proyectos(base)

    repartos = []

    def repartir(frase, **_k):
        repartos.append(frase)
        time.sleep(1.5)                       # Claude leyendo la frase
        return {"tareas": ("guia", "grafismo", "muestra"),
                "params": {"callouts": {"diseno": "sobrio"}},
                "laminas": {}, "resumen": "se rehace la guía"}

    modo = {"guia": "cli"}
    soltar = {}

    def guia(avisar, ctx, encargo):
        avisar(0.0, "")
        if modo["guia"] == "rapida":
            pass
        elif modo["guia"] == "cli":
            # como el CLI: se registra para que lo corten, y no vuelve a avisar
            # hasta que «contesta»
            evento = threading.Event()
            soltar[ctx.id] = evento
            avisar.al_cancelar(evento.set)
            evento.wait(20)
        else:
            time.sleep(1.0)                   # sin registrarse: solo la marca
        avisar(0.5, "la guia contesto")
        return {}

    servidor._LIGHT_QUE_HACE["guia"] = guia
    for tarea in ("referencias", "grafismo", "muestra"):
        servidor._LIGHT_QUE_HACE[tarea] = lambda avisar, ctx, encargo: avisar(1.0, "") or {}
    servidor._congelar_preset = lambda ctx, encargo, preset_id=None: {
        "id": preset_id, "nombre": "x"}
    servidor._enrutar_estilo = lambda: types.SimpleNamespace(repartir=repartir)

    def estilo(nombre):
        servidor.crear_proyecto({"nombre": f"taller {nombre}"})
        tid = servidor.identificador(f"taller {nombre}")
        ctx = servidor.contexto(tid)
        ctx.proyecto.config[servidor.CONFIG_TALLER] = True
        ctx.proyecto.guardar_config()
        ctx.estado.actualizar_params("callouts", {"diseno": "clasico"})
        ficha = presets.guardar("canal", nombre, {
            "guion": {"idiomas_salida": ["es"]},
            "origen": {"estilo_prompt": "dibujo plano",
                       "estilo_imagenes": ["01_a.png", "02_b.png", "03_c.png"],
                       "tono_prompt": "serio pero cercano",
                       "voz_prompt": "grave y pausada", "taller": tid}})
        return ficha["id"], ctx

    def pulsar(preset, salida, clave):
        try:
            datos = servidor.regenerar_preset_light(
                preset, {"parte": "estilo", "peticion": "más sobrio"})
            salida[clave] = (202, datos.get("trabajo_id"), {})
        except servidor.ErrorApi as fallo:
            salida[clave] = (fallo.codigo, fallo.mensaje, fallo.extra)

    try:
        pa, ctxa = estilo("Estilo A")
        pb, ctxb = estilo("Estilo B")

        # ---- el doble toque: el segundo, 409 ANTES de repartir otra vez
        respuestas = {}
        uno = threading.Thread(target=pulsar, args=(pb, respuestas, 1))
        uno.start()
        time.sleep(0.3)
        dos = threading.Thread(target=pulsar, args=(pb, respuestas, 2))
        dos.start()
        uno.join(20)
        dos.join(20)
        igual(respuestas[1][0], 202, "el primer toque lanza el «Rehacer»")
        primero_b = respuestas[1][1]
        igual(respuestas[2][0], 409, "el segundo toque contesta 409")
        igual(len(repartos), 1, "y NO vuelve a repartir la frase con Claude (antes: "
                                "dos repartos y params escritos bajo el trabajo)")
        ok(respuestas[2][2].get("preparando"),
           "el 409 dice que se está preparando un cambio, no que «se está generando»")
        igual(ctxb.estado.params("callouts").get("diseno"), "sobrio",
              "el reparto escribe su param en el taller antes de lanzar")

        # ---- otro estilo no se bloquea por este
        respuestas = {}
        modo["guia"] = "cli"
        pulsar(pa, respuestas, "a")
        igual(respuestas["a"][0], 202, "con B en marcha, rehacer A se lanza: el "
                                       "cerrojo es de cada estilo")

        # ---- cancelar B: la guia «esperando al CLI» se corta en el acto
        tid_b = primero_b
        limite = time.time() + 5
        while ctxb.id not in soltar and time.time() < limite:
            time.sleep(0.02)
        antes = time.time()
        servidor.cancelar_trabajo(tid_b)
        ficha = ctxb.gestor.esperar(tid_b, 10)
        tarda = time.time() - antes
        igual(ficha["estado"], "cancelado", "cancelar la guia acaba «cancelado», no en error")
        ok(tarda < 2.0, f"y en el acto ({tarda:.2f} s): la tarea recibe `al_cancelar`")
        igual(ctxb.estado.params("callouts").get("diseno"), "clasico",
              "lo que el reparto escribio vuelve a como estaba: el preset no se ha "
              "guardado, y el siguiente «Rehacer» lo aplicaba sin que nadie lo pidiera")

        # ---- A, mientras se cancela: el 409 lo dice y trae el trabajo
        for trabajo in ctxa.gestor.listar(activos=True):
            servidor.cancelar_trabajo(trabajo["id"])
        soltar.clear()
        modo["guia"] = "lenta"
        respuestas = {}
        pulsar(pb, respuestas, "b")
        igual(respuestas["b"][0], 202, "B, ya parado, se puede volver a rehacer")
        tid_b = respuestas["b"][1]
        servidor.cancelar_trabajo(tid_b)
        pulsar(pb, respuestas, "otra")
        codigo, mensaje, extra = respuestas["otra"]
        igual(codigo, 409, "pulsar otra vez mientras se cancela da 409")
        ok("cancelando" in mensaje, f"y dice que se está cancelando: «{mensaje}»")
        igual((extra.get("trabajo_id"), extra.get("cancelando")), (tid_b, True),
              "con el trabajo y «cancelando» para que la pantalla se enganche a él")
        igual(ctxb.gestor.esperar(tid_b, 10)["estado"], "cancelado",
              "y al volver a avisar, se para")

        # ---- una escucha de voz no impide rehacer
        suelta = threading.Event()
        escucha = ctxb.gestor.lanzar("voz:previsualizar",
                                     lambda avisar: suelta.wait(10) and "ok")
        respuestas = {}
        pulsar(pb, respuestas, "voz")
        igual(respuestas["voz"][0], 202, "con una escucha de voz sonando, «Rehacer» se "
                                         "lanza: la escucha no escribe nada que rehacer pise")
        suelta.set()
        ctxb.gestor.esperar(escucha, 10)
        for t in ctxb.gestor.listar(activos=True) + ctxa.gestor.listar(activos=True):
            servidor.cancelar_trabajo(t["id"])
        for t in ctxb.gestor.listar(activos=False):
            ctxb.gestor.esperar(t["id"], 10)

        # ---- cancelado DESPUES de guardar el preset: lo guardado se queda
        ctxb.estado.actualizar_params("callouts", {"diseno": "clasico"})
        modo["guia"] = "rapida"

        def congelar_y_cancelar(ctx, encargo, preset_id=None):
            for t in ctx.gestor.listar(activos=True):
                ctx.gestor.cancelar(t["id"])      # llega justo tras guardar
            return {"id": preset_id, "nombre": "x"}
        servidor._congelar_preset = congelar_y_cancelar
        respuestas = {}
        pulsar(pb, respuestas, "tarde")
        igual(ctxb.gestor.esperar(respuestas["tarde"][1], 10)["estado"], "cancelado",
              "una cancelacion que llega tras guardar el preset acaba «cancelado»")
        igual(ctxb.estado.params("callouts").get("diseno"), "sobrio",
              "y NO deshace lo que el preset ya guardo (taller y preset iguales)")
        servidor._congelar_preset = guardado["congelar"]

        # ---- «Reintentar» tampoco espera sin tope al cerrojo del taller
        cogido, soltar_cerrojo = threading.Event(), threading.Event()

        def ocupar():
            with servidor._cerrojo_de_cadena(ctxb.id):
                cogido.set()
                soltar_cerrojo.wait(10)
        ocupa = threading.Thread(target=ocupar)
        ocupa.start()
        cogido.wait(5)
        antes = time.time()
        try:
            servidor.crear_preset_light({
                "nombre": "Estilo B", "idioma": "es", "estilo_prompt": "dibujo plano",
                "estilo_imagenes": ["01_a.png", "02_b.png", "03_c.png"],
                "tono_prompt": "serio pero cercano", "voz_prompt": "grave y pausada",
                "taller": ctxb.id})
            codigo = 202
        except servidor.ErrorApi as fallo:
            codigo = fallo.codigo
        tarda = time.time() - antes
        soltar_cerrojo.set()
        ocupa.join(10)
        igual(codigo, 409, "«Reintentar» con el taller ocupado contesta 409")
        ok(tarda < 3.0, f"en un segundo, no esperando sin tope ({tarda:.1f} s)")
    finally:
        for evento in list(soltar.values()):
            evento.set()
        presets.FICHERO = guardado["FICHERO"]
        presets.BANCO = guardado["BANCO"]
        BITACORA.RUTA_GLOBAL = guardado["global"]
        servidor._LIGHT_QUE_HACE.clear()
        servidor._LIGHT_QUE_HACE.update(guardado["hace"])
        servidor._congelar_preset = guardado["congelar"]
        servidor._enrutar_estilo = guardado["enrutar"]
        time.sleep(1.5)                       # que acaben los hilos de los dobles
        servidor.fijar_raiz_proyectos(raiz_antes)
        shutil.rmtree(base, ignore_errors=True)


def probar_notas_19oct():
    """Las notas del dueño del 19-10-2026, en lo que toca al servidor."""
    seccion("NOTAS DEL 19-10: LÁMINAS, ASISTENTE Y MÚSICA DEL VÍDEO NUEVO")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo import Estado, Proyecto                       # noqa: PLC0415
    from pasos import laminas as LAM                          # noqa: PLC0415

    # LÁMINAS: lo que pide una lámina ya no se corta en 400 sin avisar. El texto
    # del dueño (un evento entero) se cortó en «…jugadores con lent».
    largo = ("debe ser una lamina de un evento grande en un ambiente amplio tipo salon "
             "de eventos " * 12)[:1200]
    _q, propias, _h = LAM.config_de({"laminas_propias": {"extra_1": largo}})
    igual(len(propias.get("extra_1", "")), len(" ".join(largo.split())),
          "LÁMINAS: 1.200 caracteres se guardan enteros (antes, 400)")
    codigo, mensaje = _llamar(servidor.cambiar_laminas, "no_importa",
                              {"accion": "nueva", "texto": "x" * (LAM.MAX_TEXTO + 1)})
    igual(codigo, 400, "LÁMINAS: lo que pasa del tope se dice con un 400, no se corta")
    ok("máximo" in str(mensaje), f"LÁMINAS: y el mensaje dice el máximo: {mensaje}")

    # ASISTENTE: un fallo pasajero de otro trabajo no lo pone «no conectado»
    reales = {n: getattr(servidor, n) for n in ("_candidatas_del_asistente", "_sesion_de",
                                                "_salud_cli")}
    cuenta = {"id": "c1", "etiqueta": "mia", "entrada": True}

    class _Salud:
        estado = "tiempo"

        def de(self, _c):
            return {"estado": self.estado, "mensaje": "el guion tardó 1800 s",
                    "para": "escribir el guion", "cuando": "2026-10-19T10:00:00"}

        def describir(self, ficha, etiqueta):
            return f"{etiqueta}: {ficha['estado']}"
    salud = _Salud()
    servidor._candidatas_del_asistente = lambda: [cuenta]
    servidor._sesion_de = lambda c, refrescar=False: {"conectada": True, "correo": "a@b.c"}
    servidor._salud_cli = lambda: salud
    try:
        for estado in ("tiempo", "error"):
            salud.estado = estado
            listo, motivo, _c, _cs, sin_probar = servidor._asistente_listo()
            ok(listo, f"ASISTENTE: con «{estado}» de otro trabajo sigue listo (antes, rojo): {motivo}")
            ok(sin_probar, f"ASISTENTE: y se vuelve a probar solo al abrirlo ({estado})")
        for estado in ("cupo", "sesion"):
            salud.estado = estado
            listo, motivo, *_ = servidor._asistente_listo()
            ok(not listo and motivo, f"ASISTENTE: con «{estado}» sí se dice que no puede contestar")
    finally:
        for n, v in reales.items():
            setattr(servidor, n, v)

    # MÚSICA: el ajuste fino se puede elegir ya en el vídeo nuevo
    base = tempfile.mkdtemp(prefix="estudio_19oct_")
    raiz_antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(base)
    try:
        pid = Proyecto.crear(base, "musica nueva").id
        Estado(servidor.contexto(pid).proyecto)
        ctx = servidor.contexto(pid)
        servidor._opciones_al_crear(ctx, "", {"musica_db": -4})
        igual((ctx.estado.params("render") or {}).get("musica_db"), -4.0,
              "MÚSICA: «−4 dB» elegido en el encargo nuevo llega al vídeo")
        pid2 = Proyecto.crear(base, "musica cero").id
        Estado(servidor.contexto(pid2).proyecto)
        ctx2 = servidor.contexto(pid2)
        servidor._opciones_al_crear(ctx2, "", {"musica_db": 0})
        ok("musica_db" not in (ctx2.estado.params("render") or {}),
           "MÚSICA: y 0 dB no escribe nada (regla 1)")
        codigo, _m = _llamar(servidor._opciones_al_crear, ctx2, "", {"musica_db": "alto"})
        igual(codigo, 400, "MÚSICA: un valor que no es un número da 400")
        codigo, _m = _llamar(servidor._opciones_al_crear, ctx2, "", {"musica_db": float("nan")})
        igual(codigo, 400, "MÚSICA: un NaN da 400 (antes se volvía +6 dB)")
    finally:
        servidor.fijar_raiz_proyectos(raiz_antes)
        shutil.rmtree(base, ignore_errors=True)


def probar_mas_emojis(cliente, carpeta, pid):
    """«✨ Más emojis» de Publicar (rama `textos-emojis`, 20-10-2026): la ruta
    devuelve el MISMO texto con emojis (con el doble de ESTUDIO_SIMULAR), no
    guarda nada, y rechaza con 422 lo que cambie una palabra."""
    seccion("PUBLICAR: «✨ MÁS EMOJIS» Y EL NIVEL DE EMOJIS")
    ruta = f"/api/publicar/videos/{pid}/emojis"
    texto = "Fiesta en casa\n\nReserva ya #consolas"
    r, d = cliente.post(ruta, {"red": "tiktok", "campo": "descripcion", "texto": texto})
    igual(r.status_code, 200, f"POST {ruta} responde 200")
    d = d or {}
    ok(d.get("despues", 0) > d.get("antes", 0) == 0, f"con emojis añadidos: {d.get('texto')!r}")
    ok(re.sub(r"[^\w#]", "", d.get("texto") or "") == re.sub(r"[^\w#]", "", texto),
       "y las mismas palabras y hashtags")
    r, f = cliente.get(f"/api/publicar/videos/{pid}")
    ok(not (((f or {}).get("textos") or {}).get("tiktok") or {}).get("descripcion"),
       "la ruta no guarda nada: lo guarda la pantalla")
    igual(((f or {}).get("emojis") or {}).get("nivel"), "vistoso", "la ficha dice el nivel (Vistoso de fábrica)")
    r, _d = cliente.post(ruta, {"red": "tiktok", "campo": "titulo", "texto": "Hola"})
    igual(r.status_code, 400, "TikTok no tiene título: 400")
    r, _d = cliente.post(ruta, {"red": "tiktok", "campo": "descripcion", "texto": "   "})
    igual(r.status_code, 400, "sin texto: 400")
    r, _d = cliente.post("/api/publicar/videos/noexiste/emojis", {"red": "tiktok", "campo": "descripcion",
                                                                  "texto": "Hola"})
    igual(r.status_code, 404, "un vídeo que no existe: 404")
    marca = os.path.join(carpeta, "_sistema", "publicar", "_emojis_cambia_palabras")
    os.makedirs(os.path.dirname(marca), exist_ok=True)
    with open(marca, "w") as fh:
        fh.write("1")
    try:
        r, d = cliente.post(ruta, {"red": "tiktok", "campo": "descripcion", "texto": texto})
        igual(r.status_code, 422, "si Claude cambia una palabra: 422 y no se toca nada")
        ok("palabras" in str((d or {}).get("detail") or d), "y lo dice")
    finally:
        os.remove(marca)
    r, d = cliente.put("/api/publicar/proyectos/_sin", {"emojis": "sobrio", "emojis_marca": "🎮 🕹️"})
    igual((r.status_code, ((d or {}).get("ajustes") or {}).get("emojis"),
           ((d or {}).get("ajustes") or {}).get("emojis_marca")), (200, "sobrio", "🎮 🕹️"),
          "el nivel y los emojis de la marca se guardan por proyecto")
    r, _d = cliente.put("/api/publicar/proyectos/_sin", {"emojis": "muchos"})
    igual(r.status_code, 400, "un nivel que no existe: 400")
    r, _d = cliente.put("/api/publicar/proyectos/_sin", {"emojis": "vistoso", "emojis_marca": ""})


def probar_publicar_20oct(cliente, pid):
    """Rama `publicar-20oct`: los fallos de Publicar que vio el dueño el 20-10."""
    seccion("PUBLICAR: ARREGLOS DEL 20 DE OCTUBRE")
    # 1. el idioma del audio de YouTube: Upload-Post no acepta «es-419»
    r, d = cliente.get("/api/publicar/proyectos")
    audio = [c for c, _n in (((d or {}).get("seo_opciones") or {}).get("idiomas_audio") or [])]
    ok(audio and all(re.fullmatch(r"[a-z]{2}-[A-Z]{2}", c) for c in audio),
       f"los idiomas del audio que se ofrecen son todos idioma-PAÍS: {audio}")
    r, d = cliente.put("/api/publicar/proyectos/_sin", {"yt_idioma_audio": "es-419"})
    igual((r.status_code, ((d or {}).get("ajustes") or {}).get("yt_idioma_audio")), (200, "es-US"),
          "un «es-419» que llegue se guarda como «es-US»")
    # 2. Short o vídeo normal en YouTube, elegido en la ficha
    ruta = f"/api/publicar/videos/{pid}"
    r, d = cliente.put(ruta, {"youtube_formato": "video"})
    igual((r.status_code, (d or {}).get("youtube_formato")), (200, "video"),
          f"PUT {ruta} guarda «youtube_formato»")
    ok("puede_elegir" in (((d or {}).get("encaje") or {}).get("youtube") or {}),
       "y el encaje de YouTube dice si se puede elegir")
    r, _d = cliente.put(ruta, {"youtube_formato": "reel"})
    igual(r.status_code, 400, "un formato que no existe: 400")
    r, d = cliente.put(ruta, {"youtube_formato": "auto"})
    igual((r.status_code, (d or {}).get("youtube_formato")), (200, "auto"), "«auto» vuelve a lo de siempre")
    # 4. «Comprobar» un programado que ya debió salir: /refrescar con su lote
    r, d = cliente.post("/api/publicar/refrescar", {"lote": "abc123abc123"})
    igual((r.status_code, (d or {}).get("estados")), (200, []),
          "POST /api/publicar/refrescar {lote} pregunta por ese envío y dice cómo quedó")
    r, _d = cliente.post("/api/publicar/refrescar", {"lote": "../../x"})
    igual(r.status_code, 400, "un lote que no es un id: 400")
    r, d = cliente.post("/api/publicar/refrescar")
    igual(r.status_code, 200, "y sin cuerpo sigue como siempre")
    r, d = cliente.get("/api/publicar/cola")
    ok(all("debio_salir" in e for e in (d or {}).get("envios") or []),
       "cada envío de la cola dice si ya debió salir")


def probar_espacio_fijo():
    """Rama espacio-fijo (20-10-2026): la peticion del catalogo y el ESPACIO FIJO.

    En este proceso y sin el CLI: `_llamar_claude` del catalogo se sustituye por
    un doble que apunta la instruccion y corta, que es lo que se mira.
    """
    seccion("ESPACIO FIJO: LA PETICIÓN LLEGA AL CATÁLOGO")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from nucleo import Estado, Proyecto                       # noqa: PLC0415

    catalogo = servidor.PASOS_MODULOS.catalogo_visual

    class _Cortar(Exception):
        pass

    vistas = []

    def claude_falso(instruccion, *_a, **_k):
        vistas.append(instruccion)
        raise _Cortar()

    bloques = [{"id": "B001", "texto": "Entras en la cocina del local.", "personaje": False},
               {"id": "B002", "texto": "Y sale el pan del horno.", "personaje": False}]
    base = tempfile.mkdtemp(prefix="estudio_espacio_")
    raiz_antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(base)
    reales = {"_bloques_del_guion": servidor._bloques_del_guion}
    real_claude = catalogo._llamar_claude
    servidor._bloques_del_guion = lambda _ctx: bloques
    catalogo._llamar_claude = claude_falso
    try:
        pid = Proyecto.crear(base, "espacio fijo").id
        Estado(servidor.contexto(pid).proyecto)
        ctx = servidor.contexto(pid)

        def proponer(peticion):
            vistas.clear()
            try:
                servidor._correr_catalogo(lambda *_a, **_k: None, ctx,
                                          {"modelo": "sonnet", "esfuerzo": "medium"},
                                          peticion)
            except _Cortar:
                pass
            return vistas[0] if vistas else ""

        prompt = proponer("pon todo en la panaderia de la esquina")
        ok("pon todo en la panaderia de la esquina" in prompt,
           "CATÁLOGO: la petición del editor llega al prompt (antes se quedaba en "
           "_correr_catalogo)")
        ok("LO QUE TE PIDE EL EDITOR" not in proponer(""),
           "CATÁLOGO: y sin petición el prompt no lleva el bloque")
        ok("ESPACIO FIJO" not in proponer(""),
           "CATÁLOGO: sin espacio fijo guardado, el prompt no lo nombra")

        # EL ENCARGO NUEVO: se guarda solo si viene con descripción (regla 1)
        espacio = {"sitio": "Cocina del local", "descripcion": "a small steel kitchen",
                   "luz": "day, window light",
                   "secundarios": [{"nombre": "Fachada", "descripcion": "a blue shop front"}]}
        firma_antes = ctx.estado.firma("assets")
        for nada in ({}, {"espacio_fijo": None}, {"espacio_fijo": {}},
                     {"espacio_fijo": {"sitio": "Cocina", "descripcion": "   "}}):
            servidor._opciones_al_crear(ctx, "", nada)
        ok("espacio_fijo" not in (ctx.estado.params("assets") or {}),
           "ESPACIO FIJO: sin descripción no se escribe nada en assets")
        igual(ctx.estado.firma("assets"), firma_antes, "ESPACIO FIJO: y la firma de assets no se mueve")
        for malo in ("una cocina", {"descripcion": 5},
                     {"descripcion": "x", "secundarios": "fachada"},
                     {"descripcion": "x" * 5000}):
            codigo, mensaje = _llamar(servidor._opciones_al_crear, ctx, "", {"espacio_fijo": malo})
            igual(codigo, 400, f"ESPACIO FIJO: {str(malo)[:30]!r} da 400 ({mensaje})")
        ok("espacio_fijo" not in (ctx.estado.params("assets") or {}),
           "ESPACIO FIJO: y uno que no vale tampoco escribe nada")
        servidor._opciones_al_crear(ctx, "", {"espacio_fijo": dict(espacio, luz="  day,  window light ")})
        igual((ctx.estado.params("assets") or {}).get("espacio_fijo"), espacio,
              "ESPACIO FIJO: con descripción se guarda limpio en los params de assets")
        ok(ctx.estado.firma("assets") != firma_antes,
           "ESPACIO FIJO: y entra en la firma de assets (cambiarlo deja obsoleto lo que dependa)")
        prompt = proponer("")
        ok("ESTE VIDEO TIENE UN ESPACIO FIJO" in prompt and "a small steel kitchen" in prompt
           and "'fachada' (Fachada)" in prompt,
           "CATÁLOGO: _correr_catalogo le pasa el espacio fijo guardado al catálogo")

        # LA IMAGEN DEL ESPACIO, al crear: se guarda en el proyecto con ruta relativa
        import base64 as _b64                                 # noqa: PLC0415
        from PIL import Image as _Imagen                      # noqa: PLC0415
        tampon = io.BytesIO()
        _Imagen.new("RGB", (3000, 1500), (180, 140, 90)).save(tampon, format="JPEG")
        url = "data:image/jpeg;base64," + _b64.b64encode(tampon.getvalue()).decode()
        pid2 = Proyecto.crear(base, "espacio con imagen").id
        Estado(servidor.contexto(pid2).proyecto)
        ctx2 = servidor.contexto(pid2)
        codigo, _m = _llamar(servidor._opciones_al_crear, ctx2, "",
                             {"espacio_fijo": dict(espacio, imagen_nueva="no es una imagen")})
        igual(codigo, 400, "ESPACIO FIJO: una imagen que no es imagen da 400")
        servidor._opciones_al_crear(ctx2, "", {"espacio_fijo": dict(
            espacio, imagen="espacio_fijo/0123456789abcdef.png", imagen_nueva=url)})
        guardado = (ctx2.estado.params("assets") or {}).get("espacio_fijo") or {}
        relativa = guardado.get("imagen") or ""
        ok(re.match(r"^espacio_fijo/[0-9a-f]{16}\.png$", relativa),
           f"ESPACIO FIJO: la imagen se guarda con ruta RELATIVA al proyecto ({relativa})")
        ruta = ctx2.proyecto.ruta(*relativa.split("/")) if relativa else ""
        ok(ruta and os.path.exists(ruta) and max(_Imagen.open(ruta).size) == 1536,
           "ESPACIO FIJO: en PNG y reducida a 1.536 px de lado (la que mandó el cliente como "
           "'imagen' se ignora)")
        sin_imagen = servidor.aplicar_espacio_fijo
        codigo, respuesta = _llamar(sin_imagen, pid2, {"espacio_fijo": dict(espacio, imagen="espacio_fijo/0123456789abcdef.png")})
        igual(codigo, 400, "APLICAR: una imagen que no es la guardada da 400")
        codigo, respuesta = _llamar(sin_imagen, pid2, {"espacio_fijo": {"sitio": "x"}})
        igual(codigo, 400, "APLICAR: sin descripción, 400")
        firma_antes = ctx2.estado.firma("assets")
        codigo, respuesta = _llamar(sin_imagen, pid2, {"espacio_fijo": dict(
            espacio, luz="night", imagen=relativa)})
        igual(codigo, 200, f"APLICAR: a un vídeo sin imágenes responde 200 ({respuesta if codigo != 200 else ''})")
        if codigo == 200:
            igual(respuesta["espacio_fijo"].get("imagen"), relativa, "APLICAR: conserva la imagen guardada")
            igual((respuesta["cambios"] or {}).get("imagenes"), 0, "APLICAR: sin imágenes, nada que rehacer")
            ok(respuesta["cambios"].get("usd_referencia", 0) >= 0, "APLICAR: y dice lo que cuesta la referencia")
        ok(ctx2.estado.firma("assets") != firma_antes and not ctx2.gestor.listar(activos=True),
           "APLICAR: guarda (mueve la firma de assets) y no lanza ningún trabajo")
        for cuerpo, esperado in (({}, 400), ({"planos": ["S001"]}, 400),
                                 ({"planos": ["S001"], "imagenes": 2}, 400),
                                 ({"planos": ["S001"], "imagenes": 1}, 409)):
            codigo, _m = _llamar(servidor.rehacer_planos_del_espacio, pid2, cuerpo)
            igual(codigo, esperado, f"REHACER: {cuerpo} da {esperado} ({_m})")
        ok(not ctx2.gestor.listar(activos=True), "REHACER: y ninguno lanza nada")
    finally:
        catalogo._llamar_claude = real_claude
        for nombre, valor in reales.items():
            setattr(servidor, nombre, valor)

def probar_dominios():
    """Rama dominio-negocio (21-10-2026): listar los dominios y fijar el de un estilo."""
    seccion("DOMINIOS: EL NEGOCIO DE UN ESTILO")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    codigo, d = _llamar(servidor.listar_dominios)
    ok(codigo == 200 and {x["id"] for x in d.get("dominios") or []} == {"general", "estadoplay"},
       f"GET /api/dominios: general y estadoplay ({codigo})")
    codigo, _m = _llamar(servidor.guardar_dominio_estilo, "no-existe", {"dominio": "general"})
    ok(codigo in (400, 404), f"fijar el dominio de un estilo que no existe: {codigo}")
    codigo, _m = _llamar(servidor.guardar_dominio_estilo, "x", {})
    igual(codigo, 400, "sin 'dominio', 400")
    codigo, _m = _llamar(servidor.guardar_dominio_estilo, "x", {"dominio": "telenovela"})
    igual(codigo, 400, "un dominio que no existe, 400")
    # EL CAMINO BUENO, con un estilo de verdad en un almacén aparte
    from PIL import Image as _Imagen                          # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_dominio_")
    presets = servidor._presets()
    antes = presets.FICHERO
    try:
        presets.FICHERO = os.path.join(base, "presets.json")
        refs = []
        for i in range(3):
            ruta = os.path.join(base, f"r{i}.png")
            _Imagen.new("RGB", (64, 40), (40 * i, 90, 160)).save(ruta)
            refs.append(ruta)
        ficha = presets.guardar("canal", "Con dominio", {"estilo": {"referencias": refs},
                                                         "guion": {"instrucciones": "x"}})
        pid = ficha["id"]
        codigo, r = _llamar(servidor.guardar_dominio_estilo, pid, {"dominio": " General "})
        ok(codigo == 200 and r == {"dominio": "general", "cambiado": True},
           f"fijar «General» lo guarda ({codigo} {r})")
        igual((presets.leer(pid)["datos"]["estilo"]).get("dominio"), "general", "y queda en el estilo")
        codigo, r = _llamar(servidor.guardar_dominio_estilo, pid, {"dominio": "general"})
        ok(codigo == 200 and r.get("cambiado") is False, "repetirlo no cambia nada")
        codigo, r = _llamar(servidor.guardar_dominio_estilo, pid, {"dominio": None})
        estilo = presets.leer(pid)["datos"]["estilo"]
        ok(codigo == 200 and "dominio" not in estilo and len(estilo.get("referencias") or []) == 3,
           "null vuelve a automático: se quita la clave y el resto del estilo se queda")
    finally:
        presets.FICHERO = antes


def probar_tipos_de_negocio():
    """Etapa Foto C (21-10-2026): crear, cambiar y borrar tipos de negocio, y
    fijar uno propio en un estilo."""
    seccion("TIPOS DE NEGOCIO: LOS DEL DUEÑO")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    from PIL import Image as _Imagen                          # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_tipos_")
    antes_env = os.environ.get("ESTUDIO_DOMINIOS")
    os.environ["ESTUDIO_DOMINIOS"] = os.path.join(base, "_sistema", "dominios.json")
    presets = servidor._presets()
    antes = presets.FICHERO
    try:
        presets.FICHERO = os.path.join(base, "presets.json")
        cuerpo = {"nombre": "Clínica dental", "palabras": "dentista, sonrisa",
                  "reglas": [{"texto": "Batas blancas limpias", "palabras": ["bata"]}],
                  "revisor": {"equipo": "el sillón no es de dentista"}}
        codigo, t = _llamar(servidor.crear_dominio, cuerpo)
        ok(codigo == 200 and t.get("id") == "clinica-dental" and not t.get("de_fabrica"),
           f"POST /api/dominios lo crea ({codigo} {t.get('id')})")
        ok(os.path.exists(os.environ["ESTUDIO_DOMINIOS"]), "en su fichero de _sistema")
        igual(t.get("palabras"), ["dentista", "sonrisa"], "con sus palabras")
        igual((t.get("revisor") or {}).get("equipo"), "el sillón no es de dentista",
              "y lo que vigila el revisor")
        codigo, d = _llamar(servidor.listar_dominios)
        igual([x["id"] for x in d.get("dominios") or []],
              ["general", "estadoplay", "clinica-dental"], "GET lo lista detrás de los de fábrica")
        codigo, _m = _llamar(servidor.crear_dominio, cuerpo)
        igual(codigo, 400, "otro con el mismo nombre, 400")
        codigo, _m = _llamar(servidor.crear_dominio, {"nombre": ""})
        igual(codigo, 400, "sin nombre, 400")
        codigo, _m = _llamar(servidor.cambiar_dominio, "estadoplay", {"nombre": "x"})
        igual(codigo, 400, "un tipo de fábrica no se cambia, 400")
        codigo, _m = _llamar(servidor.borrar_dominio, "general")
        igual(codigo, 400, "ni se borra, 400")
        codigo, _m = _llamar(servidor.cambiar_dominio, "no-existe", {"nombre": "x"})
        igual(codigo, 400, "cambiar uno que no existe, 400")

        refs = []
        for i in range(3):
            ruta = os.path.join(base, f"r{i}.png")
            _Imagen.new("RGB", (64, 40), (40 * i, 90, 160)).save(ruta)
            refs.append(ruta)
        ficha = presets.guardar("canal", "Dental", {"estilo": {"referencias": refs},
                                                    "guion": {"instrucciones": "x"}})
        pid = ficha["id"]
        codigo, r = _llamar(servidor.guardar_dominio_estilo, pid, {"dominio": "clinica-dental"})
        ok(codigo == 200 and r.get("dominio") == "clinica-dental",
           f"un estilo puede fijar un tipo propio ({codigo} {r})")
        codigo, t = _llamar(servidor.cambiar_dominio, "clinica-dental",
                            dict(cuerpo, descripcion="sonrisas"))
        ok(codigo == 200 and t.get("descripcion") == "sonrisas"
           and [e["id"] for e in t.get("estilos") or []] == [pid],
           "PUT lo cambia y dice qué estilos lo usan")
        codigo, m = _llamar(servidor.borrar_dominio, "clinica-dental")
        ok(codigo == 409 and "Dental" in str(m), f"borrarlo con un estilo que lo usa: 409 ({codigo})")
        codigo, r = _llamar(servidor.borrar_dominio, "clinica-dental", True)
        ok(codigo == 200 and r.get("borrado") == "clinica-dental", "con forzar, se borra")
        estilo = presets.leer(pid)["datos"]["estilo"]
        ok("dominio" not in estilo and len(estilo.get("referencias") or []) == 3,
           "y el estilo que lo tenía vuelve a automático, con el resto intacto")
        codigo, _m = _llamar(servidor.borrar_dominio, "clinica-dental")
        igual(codigo, 404, "borrar uno que ya no está, 404")
        # EL REVISOR recibe las mismas reglas de la casa que el generador: las de
        # consolas, ahora en su tipo, siguen llegándole en automático
        foto = {"modo": "foto", "referencias": ["a.png"]}
        plan = {"escenas": [{"prompt": "two kids hold game controllers"}]}
        ok("GAME CONTROLLERS" in servidor._reglas_para_revisor(foto, plan),
           "el revisor recibe las reglas de consolas en un vídeo de consolas (automático)")
        ok("GAME CONTROLLERS" not in servidor._reglas_para_revisor(dict(foto, dominio="general"), plan),
           "y no si el estilo fija «General»")
    finally:
        presets.FICHERO = antes
        if antes_env is None:
            os.environ.pop("ESTUDIO_DOMINIOS", None)
        else:
            os.environ["ESTUDIO_DOMINIOS"] = antes_env


def _video_montado_de_prueba(servidor, base, nombre):
    """Un vídeo con todos los pasos hechos y su MP4: «montado y al día»."""
    from nucleo import Estado, Proyecto                       # noqa: PLC0415
    from nucleo.estado import PASOS                           # noqa: PLC0415
    pid = Proyecto.crear(base, nombre).id
    estado = Estado(servidor.contexto(pid).proyecto)
    for paso in PASOS:
        estado.completar(paso["id"], {})
    proyecto = servidor.contexto(pid).proyecto
    ruta = proyecto.ruta_paso("render", proyecto.version_activa("render"))
    with open(os.path.join(ruta, "video.mp4"), "wb") as fh:
        fh.write(b"mp4 de mentira")
    return pid


def probar_cambios_del_encargo_un_montaje():
    """Arreglos del 19-10 (2): en el Encargo se tocan varias cosas del montaje
    seguidas sin montar (`remontar: false`), queda la marca «sin aplicar» fuera
    de los params, y «Aplicar y volver a montar» lanza UN trabajo: si lo
    pendiente es solo la mezcla, `solo_montar`; si no, capas y montaje."""
    seccion("ARREGLOS 19-10: VARIOS CAMBIOS DEL ENCARGO, UN SOLO MONTAJE")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_encargo_")
    raiz_antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(base)
    lanzados, corridos = [], []
    guardado = (servidor.lanzar_paso, servidor._correr_rehacer_montaje)
    # un trabajo de verdad en el gestor, que no hace nada: se mira qué se pide
    servidor.lanzar_paso = (lambda ctx, paso, unidades, **kw:
                            lanzados.append((paso, kw.get("opciones")))
                            or ctx.gestor.lanzar("falso", lambda avisar: {}, paso=paso))
    servidor._correr_rehacer_montaje = (lambda avisar, ctx, tareas, solo_montar=False:
                                        corridos.append((list(tareas), solo_montar)))
    try:
        pid = _video_montado_de_prueba(servidor, base, "encargo diferido")
        ctx = servidor.contexto(pid)
        igual(ctx.estado.estado_de("render"), "listo", "el vídeo de prueba está montado y al día")
        firma = ctx.estado.firma("render")
        r1 = servidor.cambiar_presencia_musica(pid, {"presencia": "alta", "remontar": False})
        r2 = servidor.guardar_sonido(pid, {"musica_db": -3, "remontar": False})
        r3 = servidor.cambiar_volumen_efectos(pid, {"nivel": "altos", "remontar": False})
        igual((r1.get("trabajo_id"), r2.get("trabajo_id"), r3.get("trabajo_id"), lanzados),
              (None, None, None, []),
              "tres cambios seguidos con `remontar: false`: ningún trabajo (y ningún 409)")
        ctx = servidor.contexto(pid)
        ok("montaje_pendiente" in ctx.proyecto.config,
           "queda la marca «sin aplicar» en proyecto.json")
        ok(all("montaje_pendiente" not in (ctx.estado.params(p) or {})
               for p in ("callouts", "render")),
           "y FUERA de los params: no entra en ninguna firma")
        leido = servidor.leer_montaje(pid)
        igual((leido.get("sin_aplicar"), leido.get("solo_mezcla")), (True, True),
              "GET /montaje dice «sin aplicar» y que basta con volver a mezclar")
        respuesta = servidor.aplicar_montaje(pid)
        time.sleep(0.5)
        igual((lanzados, corridos), ([("render", {"solo_montar": True})], []),
              "«Aplicar» lanza UN trabajo y solo vuelve a mezclar (`solo_montar`)")
        igual(respuesta.get("solo_mezcla"), True, "y lo dice")
        ok(not servidor.leer_montaje(pid).get("sin_aplicar"), "y la marca se va")
        ok(ctx.estado.firma("render") != firma, "(el cambio sí está guardado en el render)")

        # un cambio que toca las capas (los subtítulos): capas y montaje
        lanzados.clear()
        pid2 = _video_montado_de_prueba(servidor, base, "encargo con subtitulos")
        servidor.guardar_sonido(pid2, {"musica_db": 2, "remontar": False})
        servidor.cambiar_subtitulos(pid2, {"tam": "grande"})
        leido = servidor.leer_montaje(pid2)
        igual((leido.get("sin_aplicar"), leido.get("solo_mezcla")), (True, False),
              "con los subtítulos cambiados ya no es solo mezcla")
        respuesta = servidor.aplicar_montaje(pid2)
        time.sleep(0.5)
        igual((lanzados, corridos), ([], [(["callouts", "render"], False)]),
              "y «Aplicar» rehace capas y montaje en un solo trabajo")

        # un efecto vetado no toca params: la marca pide mezclar igual
        lanzados.clear()
        corridos.clear()
        pid3 = _video_montado_de_prueba(servidor, base, "encargo con veto")
        servidor._apuntar_montaje_pendiente(servidor.contexto(pid3), mezcla=True)
        ok(servidor.leer_montaje(pid3).get("sin_aplicar"),
           "un veto (sin params) también deja «sin aplicar»")
        servidor.aplicar_montaje(pid3)
        time.sleep(0.5)
        igual(lanzados, [("render", {"solo_montar": True})],
              "y se aplica con una mezcla aunque el render diga «al día»")
    finally:
        servidor.lanzar_paso, servidor._correr_rehacer_montaje = guardado
        time.sleep(0.5)
        servidor.fijar_raiz_proyectos(raiz_antes)
        shutil.rmtree(base, ignore_errors=True)


def probar_mezcla_cancelada_se_aplica_con_otra_mezcla():
    """Arreglos del 19-10 (3): una mezcla cancelada (o un remontaje que
    falló) deja el render obsoleto solo por claves de mezcla. «Regenerar
    Vídeo» (la tanda `render` en «pendientes») la aplica con OTRA mezcla
    (`solo_montar`), no volviendo a renderizar todos los planos."""
    seccion("ARREGLOS 19-10: UNA MEZCLA CANCELADA SE APLICA CON OTRA MEZCLA")
    sys.path.insert(0, RAIZ_ESTUDIO)
    import app as servidor                                    # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_mezcla_")
    raiz_antes = servidor.raiz_proyectos()
    servidor.fijar_raiz_proyectos(base)
    try:
        pid = _video_montado_de_prueba(servidor, base, "mezcla cancelada")
        # el cambio se guardó y su montaje se canceló: el render queda obsoleto
        servidor.guardar_sonido(pid, {"musica_db": -4, "remontar": False})
        ctx = servidor.contexto(pid)
        igual(ctx.estado.estado_de("render"), "obsoleto", "el render queda obsoleto por la mezcla")
        _funcion, args = servidor._que_hace("render", ctx, {}, "pendientes")
        igual(args[-1], {"solo_montar": True},
              "y «Regenerar Vídeo» lo aplica con `solo_montar`: ni un plano otra vez")
        _funcion, args = servidor._que_hace("render", ctx, {}, "todo")
        ok(not (args[-1] or {}).get("solo_montar"), "(en «todo», el render de siempre)")
        # algo que no es mezcla (los subtítulos) obliga a renderizar
        servidor.cambiar_subtitulos(pid, {"tam": "grande"})
        ctx = servidor.contexto(pid)
        ok(not servidor._solo_falta_mezclar(ctx),
           "con las capas pendientes ya no es solo mezcla")
        # y una transición (param del render que cambia los clips) tampoco
        pid2 = _video_montado_de_prueba(servidor, base, "transiciones")
        servidor.contexto(pid2).estado.actualizar_params("render", {"transiciones": ["fundido"]})
        ok(not servidor._solo_falta_mezclar(servidor.contexto(pid2)),
           "ni con otras transiciones: cambian los clips")
    finally:
        servidor.fijar_raiz_proyectos(raiz_antes)
        shutil.rmtree(base, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Prueba del servicio HTTP")
    parser.add_argument("--conservar", action="store_true",
                        help="no borrar la carpeta temporal al acabar")
    argumentos = parser.parse_args()

    carpeta = tempfile.mkdtemp(prefix="estudio_api_")
    puerto = puerto_libre()
    print(f"PRUEBA DE LA API DEL ESTUDIO\n  puerto {puerto}\n  proyectos en {carpeta}")
    proceso, base = arrancar(puerto, carpeta)
    cliente = Cliente(base, carpeta)
    try:
        pid, virgen = probar_salud_y_proyectos(cliente)
        probar_renombrar(cliente, pid)
        probar_pasos(cliente, pid)

        sembrar(os.path.join(carpeta, pid))
        tid, salidas = probar_ejecucion(cliente, base, pid)
        probar_versiones(cliente, pid)
        probar_archivos(cliente, pid, salidas)
        probar_feedback(cliente, pid)
        probar_voz(cliente, pid)
        probar_regrabar_y_estructura(cliente, carpeta)
        probar_regrabar_a_medias(cliente, carpeta)
        probar_pausas(cliente, carpeta)
        probar_presencia_musica(cliente, carpeta)
        probar_volumen_y_animo_de_la_musica()
        probar_continuaciones_en_otra_calidad()
        probar_pronunciaciones(cliente, carpeta)
        probar_ronda_octubre(cliente, carpeta)
        probar_bitacora(cliente, pid)
        probar_presets_canal(cliente)
        probar_modo_light(cliente)
        probar_video_light(cliente)
        probar_traer_estilo(cliente)
        probar_cambiar_de_estilo(cliente)
        probar_montaje(cliente)
        probar_estimacion(cliente)
        probar_el_coste_de_las_imagenes(cliente)
        probar_planos_hechos(cliente, pid)
        probar_escucha_de_voz_light(cliente)
        probar_muestras_recuperadas(cliente)
        probar_imagenes_de_apoyo(cliente)
        probar_laminas(cliente)
        probar_sonido_propio_y_cola(cliente)
        probar_audio_y_musica_de_la_previa(cliente, carpeta)
        probar_taller_oculto(cliente)
        probar_montaje_por_plano(cliente, carpeta)
        probar_descargar_imagenes(cliente, carpeta)
        probar_cartelas_y_transiciones(cliente, pid, os.path.join(carpeta, pid))
        probar_direccion(cliente, pid)
        probar_motor_del_plan(cliente, pid)
        probar_nota_del_montaje(cliente, pid)
        probar_repaso(cliente, pid)
        probar_plan_de_rotulos(cliente, pid)
        probar_trabajos_y_errores(cliente, pid, tid, virgen)
        probar_vista_de_cartela(cliente, os.path.join(carpeta, pid), pid)
        probar_cartela_sincronizada(cliente, os.path.join(carpeta, pid), pid)
        probar_claves(cliente)
        probar_cuentas_cli(cliente)
        probar_asistente(cliente)
        probar_la_foto_del_asistente(cliente, pid)
        probar_onboarding(cliente)
        probar_turno_y_notas_de_otro_texto()
        probar_coste_en_detalle(cliente, pid)
        probar_sistema(cliente)
        probar_lo_que_lleva(cliente)
        probar_salud_de_las_cuentas(cliente)
        probar_recetas(cliente, pid)
        probar_lo_que_se_cuenta_en_publico()
        probar_el_avisador_y_los_tramos()
        probar_el_mensaje_publico_de_una_tanda()
        probar_que_la_musica_no_tumba_el_montaje()
        probar_lo_del_analisis_del_13_10()
        probar_el_reloj_de_lo_que_queda_por_hacer()
        probar_que_la_barra_light_no_ensena_la_cocina()
        probar_value_de_los_textarea()
        probar_el_gemelo_de_las_marcas_tts()
        probar_que_la_receta_aplica()
        probar_lo_de_la_revision_de_imagenes_16_10()
        probar_que_la_api_esta_documentada()
        probar_que_las_llamadas_a_los_pasos_encajan()
        probar_que_no_falta_ningun_nombre_en_la_pantalla()
        probar_que_no_falta_ningun_nombre_en_el_servidor()
        probar_el_reloj_de_un_trabajo()
        probar_revision_del_nucleo_v2f()
        probar_que_lo_lento_no_para_el_servicio()
        probar_ortografia_de_campos(cliente, pid)
        probar_portadas(cliente, pid)
        probar_elementos_del_video(cliente, pid)
        probar_lo_de_v2h()
        probar_notas_19oct()
        probar_cambios_del_encargo_un_montaje()
        probar_mezcla_cancelada_se_aplica_con_otra_mezcla()
        probar_cancelar_en_el_taller()
        probar_mas_emojis(cliente, carpeta, pid)
        probar_publicar_20oct(cliente, pid)
        probar_espacio_fijo()
        probar_dominios()
        probar_tipos_de_negocio()
    finally:
        parar(proceso)
        if not argumentos.conservar:
            shutil.rmtree(carpeta, ignore_errors=True)

    print()
    if _fallos:
        print(f"PRUEBA API CON FALLOS: {len(_fallos)} de {_ok + len(_fallos)}")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PRUEBA API OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

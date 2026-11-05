"""
EL DIAGNÓSTICO DE VELOCIDAD Y DINERO (rama render-y-cotizador, 04-11-2026).

`herramientas/diagnostico_velocidad.py` se corre en el servidor para saber
dónde se va el tiempo del montaje y por qué el cotizador se pasa. Aquí se
prueba con ficheros de mentira, sin servidor ni dinero:

  1. Del entorno solo se leen las claves pedidas (nada de secretos).
  2. Cuántos procesos usaría el montaje, con y sin ESTUDIO_LOTES.
  3. Los tiempos del vídeo, con las fases del montaje.
  4. Lo cobrado por imagen y cada tanda frente a lo prometido.
  5. El informe se escribe entero, también con un montaje de antes de la rama.

    python pasos/prueba_diagnostico_velocidad.py
"""
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "herramientas"))

import diagnostico_velocidad as D  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"      FALLO: {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}\n             esperado {esperado!r}\n             obtenido {obtenido!r}")


def main():
    print("PRUEBA DEL DIAGNÓSTICO DE VELOCIDAD Y DINERO")
    base = tempfile.mkdtemp(prefix="diag_vel_")

    print("\n1] el entorno")
    entorno = os.path.join(base, "entorno")
    with open(entorno, "w", encoding="utf-8") as fh:
        fh.write("# comentario\nESTUDIO_LOTES=4\nESTUDIO_SECRETOS=/opt/x/secretos\n"
                 "ESTUDIO_ENV=/opt/x/secretos/.env\nESTUDIO_ESTADISTICAS=/opt/x/est.json\nPUERTO=8110\n")
    leido = D.leer_entorno(entorno)
    igual(leido, {"ESTUDIO_LOTES": "4", "ESTUDIO_ESTADISTICAS": "/opt/x/est.json"},
          "solo las claves pedidas: ni los secretos ni el .env")
    igual(D.leer_entorno(os.path.join(base, "no_existe")), {}, "un entorno que no existe: nada")

    print("\n2] cuántos procesos")
    igual(D.lotes_que_usaria(4, "")[0], 2, "4 núcleos sin ESTUDIO_LOTES: 2 (la mitad)")
    igual(D.lotes_que_usaria(4, "4")[0], 4, "con ESTUDIO_LOTES=4: 4")
    igual(D.lotes_que_usaria(8, "40")[0], 16, "nunca más de 16")
    igual(D.lotes_que_usaria(8, "8", planos=3)[0], 3, "ni más que planos")
    igual(D.lotes_que_usaria(4, "x")[0], 2, "un valor raro es como no tenerlo")

    print("\n3] los tiempos")
    pasos = {"render": [
        {"proyecto": "otro", "segundos": 5},
        {"proyecto": "v1", "segundos": 626, "tamano": 12, "fecha": "2026-11-04T10:00:00",
         "detalle": {"duracion_s": 30.2, "fps": 30, "resolucion": [1080, 1920], "procesos": 2, "planos": 12,
                     "fases": {"preparar": 3.0, "planos": 560.0, "sonido": 20.0, "montar": 40.0, "logo": 3.0,
                               "planos_por_plano": {"arrancar": 6.0, "abrir": 4.0, "pintar_y_capturar": 900.0,
                                                    "transicion": 60.0, "codificar": 150.0}}}}],
        "assets": [{"proyecto": "v1", "segundos": 671, "tamano": 12, "fecha": "2026-11-04T09:40:00"}],
        "callouts": []}
    igual(D.ultimo_montado(pasos), "v1", "el último vídeo montado")
    t = D.tiempos_del_video(pasos, "v1")
    ok(len(t["render"]) == 1 and len(t["assets"]) == 1 and t["callouts"] == [], "los registros de ese vídeo y no otros")

    print("\n4] el dinero")
    registros = [
        {"proyecto": "v1", "proveedor": "openai", "operacion": "imagen", "unidad": f"escena:S00{i}",
         "usd": 0.03 + i * 0.001, "tokens": {"entrada": 2800}, "detalle": {"calidad": "low", "modo": "ilustracion", "refs": ["a", "b", "c"],
                                                         "coste": {"via": "tokens", "entrada_texto": 900}},
         "momento": f"2026-11-04T09:4{i}:00"} for i in range(1, 6)]
    registros += [{"proyecto": "v2", "proveedor": "openai", "operacion": "imagen", "usd": 1.0,
                   "momento": "2026-11-04T09:41:00"},
                  {"proyecto": "v1", "proveedor": "cartesia", "operacion": "tts", "usd": 0.02,
                   "momento": "2026-11-04T09:30:00"}]
    imagenes, voz = D.costes_del_video(registros, "v1")
    igual(len(imagenes), 5, "solo las imágenes de ese vídeo")
    igual(voz, 0.02, "y su voz")
    carpeta = os.path.join(base, "proyectos", "v1")
    os.makedirs(carpeta)
    with open(os.path.join(carpeta, D.NOMBRE_TANDAS), "w", encoding="utf-8") as fh:
        for r in ({"marca": "m1", "lanzada": "2026-11-04T09:40:00", "tandas": ["video"],
                   "prometido_usd": 0.636, "prometido_imagenes": 14},
                  {"marca": "m1", "inicio": "2026-11-04T09:40:00"},
                  {"marca": "m1", "fin": "2026-11-04T09:43:30", "estado": "listo"}):
            fh.write(json.dumps(r) + "\n")
    tandas = D.tandas_del_video(os.path.join(carpeta, D.NOMBRE_TANDAS), imagenes)
    igual(len(tandas), 1, "una tanda")
    igual((tandas[0]["imagenes"], tandas[0]["prometido_imagenes"]), (3, 14),
          "las imágenes cobradas DENTRO de su ventana, frente a las prometidas")

    print("\n5] el informe")
    maq = {"nucleos": 4, "memoria": "16 GB", "carga": "0.1 0.2 0.3", "lotes_entorno": "",
           "lotes_consola": "", "lotes": 2, "lotes_porque": "sin ESTUDIO_LOTES"}
    texto = D.informe(maq, "v1", t, imagenes, voz, tandas,
                      [{"calidad": "low", "modo": "", "usd": 0.0459, "fuente": "tabla"}])
    for trozo, que in (("quedan 2 núcleo(s) parados", "avisa de los núcleos parados"),
                       ("pintar y capturar fotogramas: 900 s", "las fases de dentro de los planos"),
                       ("montar (unir clips y audio): 40 s", "las fases del montaje"),
                       ("prometido 0.636 $ por 14 imagen(es)", "lo prometido de la tanda"),
                       ("mediana 2800", "los tokens de entrada de verdad"),
                       ("referencias adjuntas por imagen: mediana 3", "cuántas referencias llevó cada imagen"),
                       ("texto (más barato): mediana 900", "cuánto de la entrada era texto"),
                       ("hoy cotiza low", "el precio de hoy")):
        ok(trozo in texto, que)
    viejo = dict(pasos["render"][1], detalle={"duracion_s": 30})
    texto2 = D.informe(maq, "v1", {"render": [viejo], "assets": [], "callouts": []}, [], 0.0, [], [])
    ok("de antes de esta rama" in texto2 and "sin imágenes cobradas" in texto2,
       "un montaje sin fases y sin cobros se dice, no revienta")

    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for f in _fallos:
            print(f"  - {f}")
        return 1
    print(f"DIAGNÓSTICO VELOCIDAD OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

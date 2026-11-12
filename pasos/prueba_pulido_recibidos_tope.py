"""Prueba de la rama pulido-recibidos-tope (12-11-2026, lo que vio el tren con G01).

1] El estilo del recibido vuelve al guion cuando vuelve a «pendiente».
2] La extensión no ve ni puede enviar a un proyecto con clave.
3] El revisor del piloto rehace con lo que QUEDA del tope de verdad (G01: 0,95 $
   con un tope de 0,90 $).
4] Tras «Seguir igualmente», si no queda nada que pagar, el tope no para (G01:
   «las imágenes costarían unos 0.00 $ (ya van 0.95 $)»).

Cada comprobación falla sin su arreglo.
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))
CARPETA = tempfile.mkdtemp(prefix="pulido_recibidos_tope_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
os.environ["ESTUDIO_AJUSTES"] = os.path.join(CARPETA, "ajustes.json")

import parrilla as PA  # noqa: E402

_cuenta, _fallos = [0], []


def ok(condicion, texto):
    _cuenta[0] += 1
    print(f"  {'ok   ' if condicion else 'FALLO'} {texto}")
    if not condicion:
        _fallos.append(texto)


def seccion(titulo):
    print(f"\n[{titulo}]")


GUION = """CODIGO: G01
TITULO: Baño chico con efecto spa
ESCENA 1
- Voz: «Un baño chico también puede parecer un spa.»
"""


def prueba_estilo_al_volver(raiz):
    seccion("1] el estilo del recibido vuelve con el guion a «pendiente»")
    cid = "cl_prueba"
    _mid, gids = PA.anadir_en_formato(raiz, cid, "", GUION, nombre="Desde un recibido",
                                      origen={"tipo": "recibido", "estilo": "estilo_del_recibido"})
    gid = gids[0]
    ok(PA.leer(raiz, cid, gid).get("estilo") == "estilo_del_recibido", "nace con el estilo del recibido")
    # como «Pasar al Encargo» con OTRO estilo: el guion se usa y apunta ese
    datos = PA._leer(raiz, cid)
    for m in datos["matrices"]:
        for g in m["guiones"]:
            if g["id"] == gid:
                g.update(estado="usado", estilo="otro_estilo", video="v1", usado_al="hoy")
    PA._guardar(raiz, cid, datos)
    PA.guardar_guion(raiz, cid, gid, {"estado": "pendiente"})
    g = PA.leer(raiz, cid, gid)
    ok(g.get("estilo") == "estilo_del_recibido",
       f"al volver a «pendiente» vuelve el estilo con el que se pidió ({g.get('estilo')!r})")
    ok(not g.get("video") and not g.get("usado_al"), "y se suelta del vídeo, como siempre")
    _m2, (sin,) = PA.anadir_en_formato(raiz, cid, "", GUION, nombre="A mano")
    PA.guardar_guion(raiz, cid, sin, {"estado": "usado"})
    PA.guardar_guion(raiz, cid, sin, {"estado": "pendiente"})
    ok(not PA.leer(raiz, cid, sin).get("estilo"), "un guion sin recibido sigue sin estilo")


class _Peticion:
    def __init__(self, cabeceras, cuerpo=b""):
        self.headers = {k.lower(): v for k, v in cabeceras.items()}
        self._cuerpo = cuerpo

    async def stream(self):
        yield self._cuerpo


def _servidor():
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida: falta {fallo.name} en este entorno; en el servidor sí corre)")
        return None
    return servidor


def prueba_proyectos_con_clave(servidor, raiz):
    seccion("2] la extensión no ve los proyectos con clave")
    import clientes as C                                          # noqa: PLC0415
    import recibidos as R                                         # noqa: PLC0415
    abierto = C.crear(raiz, "Proyecto abierto")["id"]
    secreto = C.crear(raiz, "Proyecto secreto")["id"]
    C.cambiar(raiz, secreto, clave="una-clave-larga")
    codigo = R.crear_codigo()
    if isinstance(codigo, dict):
        codigo = codigo.get("codigo") or ""
    cab = {"x-estudio-envio": codigo}
    ids = [p["id"] for p in servidor.recibidos_proyectos(_Peticion(cab))["proyectos"]]
    ok(abierto in ids, "el proyecto sin clave sale en la extensión")
    ok(secreto not in ids, f"el proyecto con clave NO sale ({ids})")

    def enviar(proyecto):
        cuerpo = json.dumps({"url": "https://www.youtube.com/watch?v=abcdefghijk", "titulo": "x",
                             "proyecto": proyecto}).encode()
        pet = _Peticion(dict(cab, **{"content-length": str(len(cuerpo))}), cuerpo)
        try:
            return asyncio.run(servidor.recibidos_guardar(pet)), None
        except servidor.ErrorApi as fallo:
            return None, fallo

    hecho, fallo = enviar(secreto)
    ok(hecho is None and fallo is not None and getattr(fallo, "codigo", getattr(fallo, "status_code", 0)) == 400
       and "proyecto" in str(getattr(fallo, "detail", fallo)) and "clave" in str(getattr(fallo, "detail", fallo)),
       f"enviar a un proyecto con clave da 400 y dice que tiene clave (la extensión recarga la lista) ({fallo})")
    hecho, fallo = enviar(abierto)
    ok(hecho and hecho.get("ok"), f"enviar al proyecto sin clave sigue igual ({fallo})")


def prueba_tope_del_revisor(servidor):
    seccion("3] el revisor rehace con lo que queda de verdad del tope del piloto")

    class _Revisor:
        def __init__(self, ya):
            self.ya = ya

        def leer_estado(self, _proyecto):
            return {"gastado_usd": self.ya}

    class _Ctx:
        proyecto = None
        id = "v"

    original = servidor._piloto_gastado
    try:
        sin_piloto = {"revisor_max_usd": 1.0}
        ok(servidor._max_usd_del_revisor(_Ctx(), _Revisor(0.1), sin_piloto) == 1.0,
           "fuera del piloto, el tope de Configuración tal cual")
        servidor._piloto_gastado = lambda _ctx: 0.85
        con = {"revisor_max_usd": 1.0, "piloto_tope_usd": 0.90, "piloto_portada_usd": 0.0}
        ok(abs(servidor._max_usd_del_revisor(_Ctx(), _Revisor(0.10), con) - 0.15) < 1e-9,
           "con 0,85 $ gastados de 0,90 $, al revisor le quedan 0,05 $ además de lo suyo (0,10 + 0,05)")
        servidor._piloto_gastado = lambda _ctx: 0.93
        ok(abs(servidor._max_usd_del_revisor(_Ctx(), _Revisor(0.10), con) - 0.10) < 1e-9,
           "G01: las imágenes ya costaron 0,93 $ de 0,90 $ → el revisor no gasta nada más")
        servidor._piloto_gastado = lambda _ctx: 0.80
        con_portada = dict(con, piloto_portada_usd=0.05)
        ok(abs(servidor._max_usd_del_revisor(_Ctx(), _Revisor(0.0), con_portada) - 0.05) < 1e-9,
           "y se guarda lo de la portada que falta (0,90 − 0,80 − 0,05)")
    finally:
        servidor._piloto_gastado = original
    # y el tope llega de verdad al revisor mientras el piloto dibuja
    visto = {}
    original_tanda = servidor._piloto_tanda

    def _tanda(_avisar, ctx, _que):
        visto.update(servidor._ajustes_revisor(ctx))
        return {}
    try:
        servidor._piloto_tanda = _tanda
        servidor._piloto_imagenes(None, _Ctx(), {"vueltas": 2, "tope_usd": 0.90}, 0.10, 0.05)
        ok(visto.get("piloto_tope_usd") == 0.90 and visto.get("piloto_portada_usd") == 0.05,
           f"durante la tanda, el revisor ve el tope del piloto y la portada pendiente ({visto})")
        visto.clear()
        servidor._piloto_imagenes(None, _Ctx(), {"vueltas": 2, "tope_usd": 0.90}, None, None)
        ok("piloto_tope_usd" not in visto, "con «Seguir igualmente» sobre el tope, no")
        ok("piloto_tope_usd" not in servidor._ajustes_revisor(_Ctx()), "y al acabar la tanda se quita")
    finally:
        servidor._piloto_tanda = original_tanda
    import inspect                                                    # noqa: PLC0415
    ok("_max_usd_del_revisor(ctx, revisor, ajustes)" in inspect.getsource(servidor._revisar_y_corregir),
       "el bucle del revisor pide su tope a `_max_usd_del_revisor` en cada ronda")


def prueba_seguir_igualmente(servidor, raiz):
    seccion("4] tras «Seguir igualmente», si no queda nada que pagar, el tope no para")
    originales = (servidor._coste_previsto, servidor._piloto_gastado, servidor._piloto_usd_portada_pendiente)
    aj = {"tope_usd": 0.90, "portadas": "plano"}
    try:
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.0}
        servidor._piloto_gastado = lambda _ctx: 0.95
        servidor._piloto_usd_portada_pendiente = lambda _r, _v, _aj: 0.0
        try:
            queda, portada = servidor._piloto_tope_antes_de_dibujar(None, raiz, "p1", aj)
            ok(queda == 0.0 and portada == 0.0, "G01: todo dibujado y 0,95 $ de 0,90 $ → sigue, y el revisor sin nada")
        except servidor._PilotoPara as parada:
            ok(False, f"G01 no se tenía que parar por el tope: {parada}")
        servidor._piloto_usd_portada_pendiente = lambda _r, _v, _aj: 0.05
        try:
            queda, portada = servidor._piloto_tope_antes_de_dibujar(None, raiz, "p1", dict(aj, portadas="ambas"))
            ok(queda == 0.0 and portada == 0.05,
               "G01 con la portada de IA por hacer (lo de fábrica): tampoco para aquí; la portada mira el tope en su paso")
        except servidor._PilotoPara as parada:
            ok(False, f"con todo dibujado no se tenía que parar por la portada: {parada}")
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.10}
        try:
            servidor._piloto_tope_antes_de_dibujar(None, raiz, "p1", aj)
            ok(False, "con imágenes por pagar y el tope pasado, se tenía que parar")
        except servidor._PilotoPara as parada:
            ok("0.10" in str(parada) and "ya van 0.95" in str(parada),
               f"con imágenes por pagar, para y dice qué falta ({parada})")
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.40}
        servidor._piloto_gastado = lambda _ctx: 0.30
        servidor._piloto_usd_portada_pendiente = lambda _r, _v, _aj: 0.0
        queda, _p = servidor._piloto_tope_antes_de_dibujar(None, raiz, "p1", aj)
        ok(abs(queda - 0.20) < 1e-9, "lo de siempre: 0,90 − 0,30 − 0,40 = 0,20 $ para el revisor")
    finally:
        (servidor._coste_previsto, servidor._piloto_gastado, servidor._piloto_usd_portada_pendiente) = originales
    # la portada de IA no pasa el tope: si no cabe, no se hace
    original = servidor._piloto_gastado
    try:
        servidor._piloto_gastado = lambda _ctx: 0.88
        ambas = {"portadas": "ambas", "calidad_portada_ia": "low"}
        precio = servidor._piloto_usd_portada(ambas)
        ok(precio > 0.02 and not servidor._piloto_portada_ia_cabe(None, ambas, 0.90),
           f"con 0,88 $ de 0,90 $, la portada de IA ({precio:.3f} $) no cabe y no se paga")
        ok(servidor._piloto_portada_ia_cabe(None, ambas, None),
           "con «Seguir igualmente» sobre el tope, sí se hace")
        ok(servidor._piloto_portada_ia_cabe(None, ambas, 5.0), "con sitio en el tope, sí")
        ok(servidor._piloto_portada_ia_cabe(None, {"portadas": "plano"}, 0.5), "sin portada de IA pedida, nada que mirar")
    finally:
        servidor._piloto_gastado = original
    # el paso 0 con todo hecho: lo que FALTA es 0, no el total del vídeo
    originales = (servidor._coste_previsto, servidor._piloto_usd_portada)
    try:
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.0, "usd_total": 0.93}
        servidor._piloto_usd_portada = lambda _aj: 0.0
        ok(servidor._piloto_previsto(None, {}) == 0.0,
           "con todo hecho, el previsto del paso 0 es 0 (antes caía al total, 0,93 $, y volvía a parar)")
        servidor._coste_previsto = lambda _ctx, _pasos: {"usd_por_generar": 0.78, "usd_total": 0.93}
        ok(servidor._piloto_previsto(None, {}) == 0.78, "un vídeo por hacer, lo que falta, como siempre")
    finally:
        (servidor._coste_previsto, servidor._piloto_usd_portada) = originales
    # la portada de IA ya hecha no se cuenta otra vez
    P = servidor._piloto()
    carpeta = P.carpeta_portadas(raiz, "abcdef012345")
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "ia.png"), "wb") as fh:
        fh.write(b"png")
    original_leer = P.leer
    try:
        P.leer = lambda _r, _v: {"portadas": [{"tipo": "ia", "fichero": "ia.png"}]}
        ok(servidor._piloto_usd_portada_pendiente(raiz, "abcdef012345", {"portadas": "ambas"}) == 0.0,
           "la portada de IA ya pintada no cuenta como pendiente")
        P.leer = lambda _r, _v: {"portadas": []}
        ok(servidor._piloto_usd_portada_pendiente(raiz, "abcdef012345", {"portadas": "plano"}) == 0.0,
           "con portada «plano» no hay nada que pagar")
    finally:
        P.leer = original_leer


def main():
    try:
        raiz = os.path.join(CARPETA, "proyectos")
        os.makedirs(raiz, exist_ok=True)
        prueba_estilo_al_volver(raiz)
        servidor = _servidor()
        if servidor is not None and servidor.PASOS_MODULOS is not None:
            servidor.fijar_raiz_proyectos(raiz)
            prueba_proyectos_con_clave(servidor, raiz)
            prueba_tope_del_revisor(servidor)
            prueba_seguir_igualmente(servidor, raiz)
    finally:
        shutil.rmtree(CARPETA, ignore_errors=True)
    print()
    if _fallos:
        print(f"PULIDO RECIBIDOS Y TOPE: FALLAN {len(_fallos)} de {_cuenta[0]} comprobaciones")
        for texto in _fallos:
            print(f"  - {texto}")
        return 1
    print(f"PULIDO RECIBIDOS Y TOPE OK: {_cuenta[0]} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
LOS ESTADOS SIN CORTAR Y LA IMAGEN BASE QUE SE CORRIGE (rama relato-sin-cortes, 06-11-2026).

Lo que vio el dueño en «X01 — Este baño de 2 m² sin ventana…»: el cambio del
estado «despues» llegaba a la imagen cortado a 400 letras («…su barra se
reem»), «✎ Cambiar» rechazaba uno más largo, y la imagen base solo se podía
repetir con la misma descripción.

Lo que se comprueba, en memoria y sin el CLI ni pagar nada:

  1. EL TOPE: 1.200 letras donde un estado se guarda, se lee y se dibuja.
  2. NADA HECHO SE MUEVE: los prompts de los planos y la etiqueta sacada del
     cambio siguen cortando a 400, y una imagen de estado aprobada con el
     texto viejo cortado sigue valiendo.
  3. LA PARRILLA guarda el estado entero y avisa si pasa del tope.
  4. LA TRADUCCIÓN acepta un cambio largo en inglés y rechaza uno desmedido.
  5. LA BASE: la nota de una sola vez y «✎ Cambiar» en lo que trae ya puesto.

    python pasos/prueba_relato_sin_cortes.py
"""
import copy
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

import guion_visual as G  # noqa: E402
import parrilla as P  # noqa: E402
import tipo_relato as T  # noqa: E402
import traducciones as TR  # noqa: E402

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


def seccion(titulo):
    print(f"\n{titulo}")


#: Un «despues» como el de X01: más de 400 letras, con lo importante al final.
LARGO = ("the walls and floor are clad in large-format matte porcelain, warm light grey, "
         "60x120 cm, with fine almost invisible joints; the pedestal sink and the small "
         "mirror are replaced by a floating light oak vanity, 60 cm wide, with its underside "
         "30 cm above the floor so the porcelain floor continues underneath, and above it a "
         "frameless rectangular mirror as wide as the vanity; the plastic shower curtain and "
         "its rail are replaced by a fixed clear glass panel with a slim black profile, and a "
         "warm LED strip runs along the ceiling edge")


def prueba_tope():
    seccion("1] el tope: 1.200 letras donde el estado se guarda, se lee y se dibuja")
    ok(len(LARGO) > 400, f"el texto de prueba pasa de 400 ({len(LARGO)})")
    igual(T.MAX_CAMBIO, 1200, "el tope nuevo")
    igual(T.estados_fijos({"estados_fijos": {"despues": LARGO}})["despues"], LARGO,
          "los estados de la Parrilla se leen enteros")
    beats = [{"desde": "B1", "hasta": "B1", "set": "bano", "cambio": LARGO, "estado": "despues"}]
    igual(T.estados_del_catalogo({"beats": beats})["despues"], LARGO, "los del reparto, también")
    ok("warm LED strip runs along the ceiling edge" in T.prompt_imagen_estado(LARGO),
       "la imagen del estado se pide con la frase entera (lo del final llega)")
    igual(G.normalizar_estados({"despues": LARGO})["despues"], LARGO, "el guion visual lo guarda entero")
    largo_inicial = "x " * 700
    igual(len(T.inicial_de(largo_inicial)), len(" ".join(largo_inicial.split())[:1200]),
          "lo que la base trae ya puesto, hasta 1.200 (eran 500)")


def prueba_nada_se_mueve():
    seccion("2] nada hecho se mueve: los planos y las imágenes de estado ya pagadas")
    ref = {"modo": "espacio_que_cambia", "cambia": "objeto", "cambio": LARGO, "nombre": "Baño"}
    frase = T.frase_edicion(1, ref)
    ok(LARGO[:400] in frase and LARGO[:401] not in frase,
       "el prompt de un PLANO sigue cortando a 400 (ningún plano hecho cambia de prompt)")
    cierre = T.cierre_edicion(1, ref)
    ok(LARGO[:400] in cierre and LARGO[:401] not in cierre, "y el cierre del plano, igual")
    import hashlib                                              # noqa: PLC0415
    sin_nombre = {"cambio": LARGO}
    igual(T.estado_de(sin_nombre), "c" + hashlib.sha1(LARGO[:400].encode("utf-8")).hexdigest()[:8],
          "la etiqueta de un cambio sin nombre sale de sus 400 primeras letras, como antes")
    seccion("   mismo_cambio: la imagen de un estado sigue valiendo")
    ok(T.mismo_cambio(LARGO, LARGO), "el mismo texto")
    ok(T.mismo_cambio(LARGO[:400], LARGO), "dibujada con el texto cortado de antes: sigue valiendo")
    ok(not T.mismo_cambio(LARGO[:399], LARGO), "otro corte: no")
    ok(not T.mismo_cambio("a mirror", LARGO), "otro cambio: no")
    ok(not T.mismo_cambio("a mirror", "a round mirror"), "uno corto distinto: no")
    ok(T.mismo_cambio("a  round\nmirror", "a round mirror"), "los espacios no cuentan")
    ok(not T.mismo_cambio("", "a mirror") and not T.mismo_cambio("a mirror", ""), "vacíos: no")
    params = {"tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto", "bases": {"bano": {
        "imagen": "espacio_fijo/" + "a" * 16 + ".png", "aprobada": True,
        "estados": {"despues": {"imagen": "espacio_fijo/" + "b" * 16 + ".png", "aprobada": True,
                                "cambio": LARGO[:400]}}}}}}
    # la imagen se guardó con el texto ya cortado (`_correr_estado` guardaba el cambio a 400)
    bases = T.bases_aprobadas(params, {"estados_fijos": {"despues": LARGO}})
    igual(bases.get(T.clave_estado("bano", "despues")), "espacio_fijo/" + "b" * 16 + ".png",
          "la imagen del estado aprobada con el texto viejo sigue entrando en los planos")
    otra = T.bases_aprobadas(params, {"estados_fijos": {"despues": "a different change"}})
    ok(T.clave_estado("bano", "despues") not in otra, "si el cambio se reescribe de verdad, ya no")
    guardado = T.normalizar(copy.deepcopy(params["tipo_relato"]))
    igual(guardado["bases"]["bano"]["estados"]["despues"]["cambio"], LARGO[:400],
          "guardar el tipo de relato no toca el texto de la imagen hecha")
    largo_guardado = copy.deepcopy(params["tipo_relato"])
    largo_guardado["bases"]["bano"]["estados"]["despues"]["cambio"] = LARGO
    igual(T.normalizar(largo_guardado)["bases"]["bano"]["estados"]["despues"]["cambio"], LARGO,
          "una imagen nueva guarda su cambio entero")


def prueba_parrilla():
    seccion("3] la Parrilla guarda el estado entero y avisa si pasa del tope")
    guion = ("P01 — Baño\nUso: exacto\nFormato: vertical\nTipo de relato: espacio_que_cambia (objeto)\n"
             "Imágenes: guion\n\nESPACIO FIJO\n- Sitio: Baño\n- Descripción: a small bathroom\n\n"
             "ESTADOS DEL ESPACIO\n- antes: [vacío: es la imagen base tal cual]\n- despues: " + LARGO + "\n\n"
             "ESCENA 1\nEstado: antes\nVisual: the bathroom\nVoz: «Así estaba.»\n\n"
             "ESCENA 2\nEstado: despues\nVisual: the new bathroom\nVoz: «Así quedó.»\n")
    enc = P.encargo_de(P.leer_guion(guion))
    igual(enc["estados"]["despues"], LARGO, "el Encargo recibe el «despues» entero")
    ok(not any("pasa de" in a for a in enc["avisos"]), "sin aviso si cabe")
    desmedido = LARGO + (" and more" * 120)
    enc2 = P.encargo_de(P.leer_guion(guion.replace(LARGO, desmedido)))
    ok(any("despues" in a and "1200" in a for a in enc2["avisos"]), "si pasa de 1.200, lo dice")


def prueba_traduccion():
    seccion("4] la traducción acepta un cambio largo y rechaza uno desmedido")
    real = TR._pedir_json
    try:
        TR._pedir_json = lambda *a, **k: {"ingles": LARGO}
        igual(TR.al_ingles("un cambio largo en español", cwd=RAIZ), LARGO, "un inglés de más de 400: se acepta")
        TR._pedir_json = lambda *a, **k: {"ingles": "word " * 300}
        try:
            TR.al_ingles("otro", cwd=RAIZ)
            ok(False, "uno de más de 1.200 tendría que rechazarse")
        except TR.ErrorTraduccion:
            ok(True, "uno de más de 1.200: se rechaza, no se corta callando")
    finally:
        TR._pedir_json = real


def prueba_base():
    seccion("5] la imagen base: la nota de una vez")
    igual(T.nota_base(""), "", "sin nota, nada")
    ok("el lavabo a la izquierda" in T.nota_base("el lavabo  a la izquierda"), "la nota va tal cual")
    ok(len(T.nota_base("x" * 900)) < 900, "y con tope")
    try:
        import app as servidor                                    # noqa: PLC0415
    except ImportError as fallo:
        print(f"  (omitida la parte del servidor: falta {fallo.name} en este entorno)")
        return
    from nucleo import Estado, Proyecto                           # noqa: PLC0415
    base = tempfile.mkdtemp(prefix="estudio_rsc_")
    servidor.fijar_raiz_proyectos(base)
    pid = Proyecto.crear(base, "relato sin cortes").id
    Estado(servidor.contexto(pid).proyecto)
    ctx = servidor.contexto(pid)
    ctx.estado.set_params("assets", {
        "tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto"},
        "espacio_fijo": {"sitio": "Baño", "descripcion": "a small bathroom"},
        "catalogo": {"beats": [], "relato": {"inicial": "beige tiles and a pedestal sink"}}})
    p6 = servidor.PASOS_MODULOS.p6_assets
    vistos = []
    reales = (p6.generar_imagen_base, servidor._usd_por_imagen)

    def generar(proyecto, params, rehacer=False, sitio=None, nota=""):
        vistos.append({"rehacer": rehacer, "nota": nota})
        return {"sitio": "bano", "imagen": "espacio_fijo/" + "c" * 16 + ".png", "coste": 0.0}
    p6.generar_imagen_base = generar
    servidor._usd_por_imagen = lambda _ctx: 0.05
    try:
        for cuerpo, que in (({"usd": 0.05, "otra": True, "nota": 3}, "una nota que no es texto"),
                            ({"usd": 0.05, "otra": True, "nota": "x" * 401}, "una nota de más de 400")):
            try:
                servidor.generar_base_relato(pid, cuerpo)
                ok(False, f"{que}: tendría que dar 400")
            except servidor.ErrorApi as e:
                igual(e.codigo, 400, f"{que}: 400")
        servidor.generar_base_relato(pid, {"usd": 0.05, "otra": True, "nota": "  el lavabo   a la izquierda "})
        import time                                                # noqa: PLC0415
        for _ in range(100):
            if vistos:
                break
            time.sleep(0.05)
        igual(vistos[-1:], [{"rehacer": True, "nota": "el lavabo a la izquierda"}],
              "«Otra imagen base» con nota: llega a la generación, limpia")
        ok("nota" not in str(ctx.estado.params("assets")), "la nota no se guarda en ningún param")
    finally:
        p6.generar_imagen_base, servidor._usd_por_imagen = reales

    seccion("   «✎ Cambiar» lo que la base trae ya puesto")
    mod = servidor._traducciones()
    reales_t = (mod.al_ingles, mod.guardar, servidor._lanzar_traduccion)
    guardadas = {}
    mod.al_ingles = lambda es, anterior="", cwd=None: "white tiles and a floating oak vanity"
    mod.guardar = lambda raiz, textos: guardadas.update(textos)

    def en_el_acto(ctx_, tipo, correr, estado_relato=""):
        guardadas["_estado"] = estado_relato
        correr()
        return True
    servidor._lanzar_traduccion = en_el_acto
    try:
        antes_assets = copy.deepcopy(ctx.estado.params("assets"))
        servidor.editar_estado_relato(pid, {"inicial": True, "es": "azulejos blancos y un mueble de roble"})
        despues = ctx.estado.params("assets") or {}
        igual(despues["catalogo"]["relato"]["inicial"], "white tiles and a floating oak vanity",
              "se guarda en inglés en lo que la base trae ya puesto")
        igual(guardadas.get("white tiles and a floating oak vanity"), "azulejos blancos y un mueble de roble",
              "y su español, para enseñarlo")
        igual(guardadas.get("_estado"), servidor.ESTADO_INICIAL_RELATO, "la pantalla sabe qué se está traduciendo")
        sin_inicial = copy.deepcopy(antes_assets)
        quitar = {k: v for k, v in antes_assets.items() if k != "catalogo"}
        ok(set(despues) - {"catalogo"} == set(quitar), "no toca ningún otro param")
        igual({k: v for k, v in despues.items() if k != "catalogo"}, quitar, "ni lo que hay en ellos")
        sin_inicial["catalogo"]["relato"] = {}
        ctx.estado.set_params("assets", sin_inicial)
        try:
            servidor.editar_estado_relato(pid, {"inicial": True, "es": "algo"})
            ok(False, "sin nada que cambiar tendría que dar 404")
        except servidor.ErrorApi as e:
            igual(e.codigo, 404, "sin nada que traiga la base: lo dice (404)")

        seccion("   «✎ Cambiar» un estado cortado: su imagen deja de valer (revisión 06-11)")
        pid2 = Proyecto.crear(base, "estado cortado").id
        Estado(servidor.contexto(pid2).proyecto)
        ctx2 = servidor.contexto(pid2)
        img_base, img_estado = "espacio_fijo/" + "a" * 16 + ".png", "espacio_fijo/" + "b" * 16 + ".png"
        ctx2.estado.set_params("assets", {
            "imagenes": "guion",
            "tipo_relato": {"modo": "espacio_que_cambia", "cambia": "objeto", "bases": {"bano": {
                "imagen": img_base, "aprobada": True,
                "estados": {"despues": {"imagen": img_estado, "aprobada": True, "cambio": LARGO[:400]}}}}},
            "espacio_fijo": {"sitio": "bano", "descripcion": "a small bathroom"},
            "guion_visual": {"origen": "parrilla", "planos": [], "visuales": [
                {"voz": "Así quedó.", "visual": ["the new bathroom"], "estado": "despues"}],
                "estados": {"despues": LARGO[:400]}}})
        p6m = servidor.PASOS_MODULOS.p6_assets
        sitio_e, pedidos = p6m.estados_del_relato(ctx2.proyecto, ctx2.estado.params("assets"))
        if "despues" not in pedidos:
            print(f"  (omitida: este vídeo de prueba no pide el estado: {sitio_e} {pedidos})")
        else:
            antes_ok = T.clave_estado(sitio_e, "despues") in T.bases_aprobadas(
                ctx2.estado.params("assets"), p6m._catalogo_de(ctx2.estado.params("assets"), ctx2.proyecto))
            ok(antes_ok, "antes: la imagen cortada está aprobada y vale")
            mod.al_ingles = lambda es, anterior="", cwd=None: LARGO
            servidor.editar_estado_relato(pid2, {"estado": "despues", "es": "el cambio entero en español"})
            params2 = ctx2.estado.params("assets")
            hecho = params2["tipo_relato"]["bases"][sitio_e]["estados"]["despues"]
            ok(not hecho.get("aprobada") and hecho.get("imagen") == img_estado,
               "al guardarlo entero, la imagen pierde su aprobación (la imagen se queda para verla)")
            ok(T.clave_estado(sitio_e, "despues") not in T.bases_aprobadas(
                params2, p6m._catalogo_de(params2, ctx2.proyecto)),
               "y ya no se manda a los planos: hace falta otra")
            igual(params2["guion_visual"]["estados"]["despues"], LARGO, "con el cambio entero guardado")
    finally:
        mod.al_ingles, mod.guardar, servidor._lanzar_traduccion = reales_t


def main():
    print("PRUEBA DE LOS ESTADOS SIN CORTAR Y LA BASE QUE SE CORRIGE")
    prueba_tope()
    prueba_nada_se_mueve()
    prueba_parrilla()
    prueba_traduccion()
    prueba_base()
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"RELATO SIN CORTES OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

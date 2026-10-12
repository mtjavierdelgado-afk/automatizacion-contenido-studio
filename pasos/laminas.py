"""Las LAMINAS de un estilo descrito: que son, cuales hay y como se cambian.

QUE ES UNA LAMINA
-----------------
Tus imagenes de referencia NO viajan a cada plano. Lo que viaja es una hoja con
las LAMINAS del estilo: imagenes dibujadas por la IA en el estilo del canal
--mirando la guia escrita (que se escribio con TODAS tus imagenes) y una hoja de
hasta 8 de ellas--, una por cada cosa que un video suele ensenar: una cara, un
grupo de personas, un interior, un exterior, un objeto y un diagrama. Cada
plano de cada video recibe esa hoja entera (hasta 8 laminas,
`p6_assets.MAX_REFERENCIAS_ESTILO`) y copia de ella el aspecto. O sea: las
laminas SON el estilo que copian tus videos, y por eso aqui se pueden ver,
regenerar, cambiar lo que ensenan, quitar o anadir.

Lo que se guarda (en el `origen` del estilo, para que regenerarlo lo respete):

    laminas_quitadas   [eje, ...]      de las seis de fabrica, las que no van
    laminas_propias    {id: texto}     lo que ensena cada una si se cambio, y las
                                       anadidas (`extra_1`, `extra_2`...)
    laminas_hoja       "comun" | "repartida"
                                       con que imagenes tuyas se dibuja cada una:
                                       las mismas 8 para todas, o un grupo
                                       distinto de 8 para cada una (asi cuentan
                                       todas las que subiste; mismo coste)

Este modulo NO toca `moodboard.py` (reservado por la Etapa Foto A): usa sus
funciones publicas para dibujar --el mismo prompt y las mismas reglas que una
lamina de fabrica-- y deja la lista de referencias en el taller como siempre.
"""
import os
import re

try:
    from . import medios, moodboard
except ImportError:                                   # corriendo desde pasos/
    import medios
    import moodboard

#: Lo que se le cuenta a una persona de cada lamina de fabrica.
EXPLICACION = {
    "cara": "Una cara de cerca. Enseña cómo se resuelven las personas en primer plano.",
    "cuerpos": "Varias personas de cuerpo entero. Proporciones, ropa y posturas.",
    "interior": "Un interior general. Cómo se ven los espacios: luz, materiales, muebles.",
    "exterior": "Un exterior general. Calles, fachadas y cielo en este estilo.",
    "objeto": "Un objeto de cerca. Texturas y detalle de cosas sueltas.",
    "diagrama": "Un diagrama sencillo. Cómo se dibujan esquemas, flechas y rótulos.",
}

#: Cuantas laminas caben: las que entran en la hoja de cada plano.
MAX_LAMINAS = 8
MIN_LAMINAS = 3
MAX_TEXTO = 400
HOJAS = ("comun", "repartida")
_EXTRA = re.compile(r"^extra_\d{1,3}$")


def config_de(encargo):
    """(quitadas, propias, hoja) del encargo u origen, saneados."""
    encargo = encargo or {}
    crudas = encargo.get("laminas_quitadas")
    crudas = crudas if isinstance(crudas, list) else []
    quitadas = [e for e in crudas if isinstance(e, str) and e in moodboard.EJES]
    quitadas = list(dict.fromkeys(quitadas))
    propias_crudas = encargo.get("laminas_propias")
    propias_crudas = propias_crudas if isinstance(propias_crudas, dict) else {}
    propias = {}
    for clave, texto in propias_crudas.items():
        clave = str(clave)
        texto = " ".join(str(texto or "").split())[:MAX_TEXTO]
        if (clave in moodboard.EJES or _EXTRA.match(clave)) and (texto or clave in moodboard.EJES):
            if texto:
                propias[clave] = texto
    hoja = encargo.get("laminas_hoja") if encargo.get("laminas_hoja") in HOJAS else "comun"
    return quitadas, propias, hoja


def ids_de(encargo):
    """Las laminas de este estilo, en orden: las de fabrica que quedan y las anadidas."""
    quitadas, propias, _ = config_de(encargo)
    fabrica = [e for e in moodboard.EJES if e not in quitadas]
    extras = sorted((k for k in propias if _EXTRA.match(k)),
                    key=lambda k: int(k.split("_")[1]))
    return fabrica + extras


def siguiente_extra(encargo):
    _, propias, _ = config_de(encargo)
    usados = [int(k.split("_")[1]) for k in propias if _EXTRA.match(k)]
    return f"extra_{(max(usados) + 1) if usados else 1}"


def titulo_de(lamina, encargo=None):
    _, propias, _ = config_de(encargo)
    if lamina in moodboard.EJES:
        base = moodboard.EJES[lamina]["titulo"]
        return f"{base} (cambiada)" if propias.get(lamina) else base
    return "Lámina añadida"


def explicacion_de(lamina, encargo=None):
    _, propias, _ = config_de(encargo)
    if propias.get(lamina):
        return f"Enseña: {propias[lamina]}"
    return EXPLICACION.get(lamina, "")


def peticion_de(lamina, encargo, correccion=""):
    """Lo que se le pide al dibujar ESTA lamina, ademas de su descripcion."""
    _, propias, _ = config_de(encargo)
    partes = []
    if lamina in moodboard.EJES and propias.get(lamina):
        partes.append(f"Instead of the default subject, show exactly this: {propias[lamina]}")
    if correccion:
        partes.append(str(correccion))
    return " ".join(partes)


def descripcion_extra(lamina, encargo):
    _, propias, _ = config_de(encargo)
    return propias.get(lamina, "")


def repartir(rutas, cuantas, base_maximo=8, fijas=None):
    """Grupos de imagenes para dibujar `cuantas` laminas con hoja «repartida».

    Las FIJAS (marcadas con ★, o las de la hoja comun) van en todas; el resto se
    reparte en grupos distintos para que, entre todas las laminas, cuenten todas
    tus imagenes. Mismo coste: sigue siendo una hoja por lamina.
    """
    rutas = list(rutas or [])
    fijas = [r for r in (fijas or []) if r in rutas][:base_maximo]
    resto = [r for r in rutas if r not in fijas]
    hueco = max(1, base_maximo - len(fijas))
    grupos = []
    for indice in range(max(1, cuantas)):
        trozo = resto[(indice * hueco) % max(1, len(resto)):][:hueco] if resto else []
        if len(trozo) < hueco and resto:
            trozo += resto[:hueco - len(trozo)]
        grupos.append(fijas + [r for r in trozo if r not in fijas])
    return grupos


def dibujar_suelta(estilo, destino, nombre, descripcion, calidad="medium",
                   idioma="", peticion="", referencias=None):
    """Dibuja UNA lamina con una descripcion libre. -> {ruta, coste_usd}

    El mismo camino que `moodboard.dibujar_desde_guia` para una de fabrica --la
    guia escrita, las reglas de la casa, la hoja de tus imagenes como imagen 1--
    pero con lo que tu digas que ensene. Se escribe en `<destino>/<nombre>.png`.
    """
    imagen = medios.motor("imagen_openai/imagen.py")
    reglas = medios.motor("reglas/reglas.py")
    import p6_assets                                        # noqa: PLC0415
    guia = p6_assets.guia_escrita(estilo)
    if not guia:
        raise RuntimeError("este estilo no tiene guía escrita: regenera el estilo gráfico primero")
    aportadas = [r for r in (referencias or []) if r and os.path.isfile(r)]
    if not aportadas:
        raise RuntimeError("no hay imágenes de referencia en el disco para dibujar la lámina")
    os.makedirs(destino, exist_ok=True)
    cache = os.path.join(os.path.dirname(os.path.abspath(destino)), "_lamina_aportadas")
    os.makedirs(cache, exist_ok=True)
    hoja = moodboard._montar([imagen.normalizar(r, cache) for r in aportadas],
                             os.path.join(cache, f"aportadas_{nombre}.png"))
    if not hoja:
        raise RuntimeError("ninguna de las imágenes de referencia se ha podido abrir")
    prompt = moodboard.prompt_de_dibujo(
        str(descripcion or ""), estilo, peticion, guia,
        reglas.bloque_prompt("prompt_imagen"), con_lamina=True,
        encabezado="Produce one single full-frame image for a style reference sheet.",
        idioma=idioma)
    png, meta = imagen.generar(prompt, [imagen.normalizar(hoja, cache)],
                               quality=calidad, tamano="apaisado")
    ruta = os.path.join(destino, f"{nombre}.png")
    with open(ruta, "wb") as fh:
        fh.write(png)
    return {"ruta": ruta, "coste_usd": float(meta.get("coste") or 0.0)}

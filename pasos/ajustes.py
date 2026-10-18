"""Los AJUSTES del estudio: lo poco que se decide UNA vez y vale para todos.

QUE ES UN AJUSTE Y QUE NO
-------------------------
Un ajuste es una decision que no pertenece a ningun video en concreto: la
calidad con la que se piden las imagenes es la misma manana que hoy, y
preguntarla en cada video seria preguntar quince veces lo mismo. Lo que SI
pertenece a un video --su estilo, su voz, su duracion-- vive en sus params o en
su preset, y no aqui.

Y SOLO ES UN VALOR POR DEFECTO. Cambiar un ajuste NO toca ningun video ya
hecho, a proposito: `calidad` entra en la firma de cada imagen
(`p6_assets`, `firma = medios.huella({... "calidad": p["calidad"] ...})`), asi
que un defecto que se leyera al EJECUTAR dejaria obsoletas de golpe las
imagenes de todos los proyectos que nunca lo fijaron -- y regenerarlas cuesta
dinero de verdad. Por eso el valor se escribe en los params del proyecto CUANDO
SE CREA (ver `crear_proyecto` en app.py) y ahi se queda: lo viejo sigue con lo
que tenia y el modo editor lo puede cambiar video a video como siempre.

LO QUE CUESTA UNA IMAGEN, DE VERDAD
-----------------------------------
La tabla de precios de OpenAI habla de la imagen DEVUELTA, y con eso solo se
entiende la mitad de la factura: a cada plano se le adjuntan las referencias de
estilo, las de reparto y las de continuidad, y ESO se paga como tokens de
entrada. Medido sobre las 1.439 imagenes del historico (`coste_global.jsonl`),
la entrada es la mediana de abajo y sale casi tan cara como la imagen en `low`.

La consecuencia es la que importa al elegir: subir de `low` a `medium` parece
multiplicar por 6,8 y multiplica por 1,7, porque la parte que se multiplica es
la pequena. Sin esta cuenta delante, la pantalla asustaria con un numero falso.
"""
import os
import time

try:
    from nucleo import coste as COSTE
except ImportError:                                   # corriendo desde pasos/
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from nucleo import coste as COSTE
from nucleo.proyecto import escribir_json, leer_json

RAIZ_ESTUDIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Redirigible igual que el resto: en el servidor cada cuenta tiene el suyo.
RUTA = os.environ.get("ESTUDIO_AJUSTES") or os.path.join(RAIZ_ESTUDIO,
                                                         "ajustes.json")

#: Las calidades que acepta el motor de imagen, de mas barata a mas cara.
CALIDADES = ("low", "medium", "high")

#: El tamano con el que se generan los planos, y por tanto con el que hay que
#: mirar la tabla de precios. Es el de `p6_assets` para 16:9.
TAMANO = "1536x1024"

#: TOKENS DE ENTRADA POR IMAGEN. La MEDIANA de las 1.439 imagenes del historico
#: --p10 3.287, p90 6.741--, no una estimacion. Se usa la mediana y no el p90
#: porque esto es lo que cuesta una imagen tipica; el p90 ensenaria de mas casi
#: siempre. Si cambia cuantas referencias se adjuntan, este numero se vuelve a
#: medir: sale de `coste_global.jsonl`, campo tokens.entrada de las operaciones
#: 'imagen'.
TOKENS_ENTRADA_POR_IMAGEN = 5114

POR_DEFECTO = {
    "calidad_imagen": "low",
    # Si ya se ha pasado por la guia de inicio (las tarjetas que piden las
    # claves al entrar por primera vez). Vive aqui y no en el navegador
    # porque es de la instalacion, no de la pantalla: desde el movil no hay
    # que volver a verla.
    "onboarding_visto": False,
    # COMO SE DICTA AL ASISTENTE (pasos/dictado.py). «auto»: con una clave de
    # OpenAI se graba y lo transcribe OpenAI (~0,003 $/min); sin clave, el
    # dictado del navegador. «navegador»: siempre el del navegador, gratis,
    # aunque haya clave.
    "dictado": "auto",
    # LA HORA DE TU REGION (IANA: «America/Lima», «Europe/Madrid»). Vacio: la
    # del servidor, que en un VPS suele ser UTC -- y entonces el chat y la lista
    # de videos enseñan cinco horas de mas desde Lima (09-10-2026). Se aplica
    # al PROCESO (`aplicar_zona`): todo lo que el servidor apunta con hora
    # (`ahora()`, `strftime`) sale ya en esa zona, sin tocar cada sitio que la
    # escribe. Lo apuntado antes de cambiarla se queda con la hora que tenia.
    "zona_horaria": "",
    # EL REVISOR DE IMAGENES (pasos/revisor_imagenes.py). «manual»: solo con
    # el boton. «autonomo»: tras cada tanda revisa lo nuevo y rehace solo lo
    # grave, una vuelta. «automatico»: rehace todo lo marcado y vuelve a
    # revisar, hasta `revisor_vueltas`. Los topes cuentan solo lo que el
    # revisor manda rehacer SOLO (lo que pide una persona no):
    # `revisor_max_imagenes` por tanda y `revisor_max_usd` por video.
    "revisor_modo": "manual",
    "revisor_max_imagenes": 10,
    "revisor_max_usd": 1.0,
    "revisor_vueltas": 2,
}

DICTADOS = ("auto", "navegador")
REVISOR_MODOS = ("manual", "autonomo", "automatico")
#: (minimo, maximo) de los topes del revisor
REVISOR_LIMITES = {"revisor_max_imagenes": (0, 200), "revisor_max_usd": (0.0, 100.0),
                   "revisor_vueltas": (1, 5)}


def _tope_revisor(clave, valor):
    """El tope validado, o ValueError."""
    minimo, maximo = REVISOR_LIMITES[clave]
    if isinstance(valor, bool):
        raise ValueError(f"{clave} es un número")
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{clave} es un número") from None
    if not minimo <= numero <= maximo:
        raise ValueError(f"{clave}: entre {minimo} y {maximo}")
    return round(numero, 2) if isinstance(minimo, float) else int(numero)


def leer():
    """Los ajustes guardados, con los que faltan puestos por defecto."""
    guardado = leer_json(RUTA, {}) or {}
    salida = dict(POR_DEFECTO)
    for clave, valor in guardado.items():
        if clave in POR_DEFECTO:
            salida[clave] = valor
    if salida.get("calidad_imagen") not in CALIDADES:
        salida["calidad_imagen"] = POR_DEFECTO["calidad_imagen"]
    salida["onboarding_visto"] = bool(salida.get("onboarding_visto"))
    if salida.get("dictado") not in DICTADOS:
        salida["dictado"] = POR_DEFECTO["dictado"]
    if not isinstance(salida.get("zona_horaria"), str) \
            or (salida["zona_horaria"] and not zona_valida(salida["zona_horaria"])):
        salida["zona_horaria"] = ""
    if salida.get("revisor_modo") not in REVISOR_MODOS:
        salida["revisor_modo"] = POR_DEFECTO["revisor_modo"]
    for clave in REVISOR_LIMITES:
        try:
            salida[clave] = _tope_revisor(clave, salida.get(clave))
        except ValueError:
            salida[clave] = POR_DEFECTO[clave]
    return salida


def zona_valida(nombre):
    """Si `nombre` es una zona IANA que esta maquina conoce. -> bool"""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(str(nombre))
        return True
    except Exception:                                         # noqa: BLE001
        return False


#: La TZ con la que arranco el proceso, para poder volver a ella si se borra
#: el ajuste.
_TZ_DE_ARRANQUE = os.environ.get("TZ")


def aplicar_zona(zona=None):
    """Pone la zona horaria del ajuste al proceso. -> la zona en uso ("" = la
    del servidor). `time.tzset` no existe en Windows: ahi no hace nada, y la
    hora es la del propio ordenador, que ya es la de quien lo usa."""
    if zona is None:
        zona = leer().get("zona_horaria") or ""
    if not hasattr(time, "tzset"):
        return ""
    if zona:
        os.environ["TZ"] = zona
    elif _TZ_DE_ARRANQUE is not None:
        os.environ["TZ"] = _TZ_DE_ARRANQUE
    else:
        os.environ.pop("TZ", None)
    time.tzset()
    return zona


def zona_en_uso():
    """{"zona", "abreviatura", "desfase", "hora"}: lo que el servidor usa ahora."""
    desfase = -time.altzone if time.localtime().tm_isdst > 0 else -time.timezone
    signo = "+" if desfase >= 0 else "-"
    horas, resto = divmod(abs(desfase), 3600)
    return {"zona": leer().get("zona_horaria") or "",
            "abreviatura": time.strftime("%Z"),
            "desfase": f"UTC{signo}{horas:02d}:{resto // 60:02d}",
            "hora": time.strftime("%Y-%m-%d %H:%M")}


def guardar(cambios):
    """Mezcla `cambios` sobre lo que hay y devuelve los ajustes resultantes.

    Se valida aqui y no en la pantalla: un ajuste con un valor que el motor no
    entiende no da error al guardarlo, lo da meses despues al generar.
    """
    if not isinstance(cambios, dict):
        raise ValueError("los ajustes se cambian con un objeto")
    actual = leer()
    for clave, valor in cambios.items():
        if clave not in POR_DEFECTO:
            raise ValueError(f"ajuste desconocido: {clave!r}")
        if clave == "calidad_imagen" and valor not in CALIDADES:
            raise ValueError(
                f"calidad {valor!r}: solo {', '.join(CALIDADES)}")
        if clave == "onboarding_visto" and not isinstance(valor, bool):
            raise ValueError("onboarding_visto es verdadero o falso")
        if clave == "dictado" and valor not in DICTADOS:
            raise ValueError(f"dictado {valor!r}: solo {', '.join(DICTADOS)}")
        if clave == "zona_horaria":
            valor = str(valor or "").strip()
            if valor and not zona_valida(valor):
                raise ValueError(f"zona horaria {valor!r}: no es una zona que este "
                                 "servidor conozca (p. ej. America/Lima)")
        if clave == "revisor_modo" and valor not in REVISOR_MODOS:
            raise ValueError(f"revisor_modo {valor!r}: solo {', '.join(REVISOR_MODOS)}")
        if clave in REVISOR_LIMITES:
            valor = _tope_revisor(clave, valor)
        actual[clave] = valor
    escribir_json(RUTA, actual)
    return actual


def calidad_imagen():
    """La calidad con la que arranca un proyecto nuevo."""
    return leer()["calidad_imagen"]


def coste_por_imagen(calidad, tamano=TAMANO):
    """Lo que cuesta UNA imagen a esa calidad: la devuelta MAS lo adjuntado.

    Devuelve las dos mitades por separado porque el reparto es justo lo que hay
    que ensenar: sin el, la comparacion entre calidades es de la parte pequena.
    """
    tokens = COSTE.tarifa_tokens() or {}
    por_token_entrada = float(tokens.get("entrada_imagen") or 0.0)
    entrada = TOKENS_ENTRADA_POR_IMAGEN * por_token_entrada
    devuelta = float(COSTE.tarifa_imagen(tamano, calidad) or 0.0)
    return {
        "calidad": calidad,
        "usd_imagen": round(devuelta, 4),
        "usd_referencias": round(entrada, 4),
        "usd_total": round(devuelta + entrada, 4),
        "tokens_entrada": TOKENS_ENTRADA_POR_IMAGEN,
    }


#: Cuantas imagenes recientes hacen falta para fiarse de la mediana propia.
MUESTRAS_MINIMAS = 20
_MEDIDO = {"sello": None, "por_calidad": {}}


def _imagenes_registradas():
    """{clave: [usd...]} de las imagenes de PLANO ya cobradas con su `usage`
    (tarifa por tokens), las mas recientes al final. La clave es la calidad
    («medium») y, si la operacion lo apunto, tambien calidad y modo
    («medium|foto»). Lee el final del registro global, que puede ser grande, y
    se recuerda mientras no cambie.

    SOLO PLANOS (unidad `escena:...`). Se mezclaba todo lo cobrado en esa
    calidad, y en `medium` el cubo lo llenaban las LAMINAS de los estilos --que
    se dibujan en medium y llevan menos referencias que un plano--: con tres o
    cuatro estilos hechos, el precio de un plano de foto salia de las laminas y
    prometia un 40 % menos de lo que se cobraba (auditoria del 15-10-2026). Las
    hojas de reparto tampoco: son una por personaje, no una por plano."""
    ruta = COSTE.RUTA_GLOBAL
    try:
        estado = os.stat(ruta)
    except OSError:
        return {}
    sello = (ruta, estado.st_mtime_ns, estado.st_size)
    if _MEDIDO["sello"] == sello:
        return _MEDIDO["por_calidad"]
    import json                                         # noqa: PLC0415
    por_calidad = {}
    try:
        with open(ruta, "rb") as fh:
            desde = max(0, estado.st_size - 4_000_000)
            fh.seek(desde)
            lineas = fh.read().decode("utf-8", "replace").splitlines()
            if desde:
                lineas = lineas[1:]        # la primera puede venir cortada
    except OSError:
        return {}
    for linea in lineas:
        try:
            r = json.loads(linea)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        detalle = r.get("detalle") or {}
        if (r.get("proveedor") != "openai" or r.get("operacion") != "imagen"
                or r.get("usd") is None
                or not str(r.get("unidad") or "").startswith("escena:")
                or (detalle.get("coste") or {}).get("via") != "tokens"):
            continue
        calidad = str(detalle.get("calidad") or "")
        por_calidad.setdefault(calidad, []).append(float(r["usd"]))
        if detalle.get("modo") in MODOS:
            por_calidad.setdefault(f"{calidad}|{detalle['modo']}", []).append(float(r["usd"]))
    _MEDIDO.update(sello=sello, por_calidad=por_calidad)
    return por_calidad


#: Los modos de imagen de un video (`p6_assets.modo_de`).
MODOS = ("ilustracion", "foto")


def _mediana_de(cobradas):
    ordenadas = sorted(cobradas)
    return ordenadas[len(ordenadas) // 2]


def precio_por_imagen(calidad, tamano=TAMANO, modo=None):
    """LO QUE CUESTA UNA IMAGEN DE PLANO, con su procedencia. -> {usd, fuente, muestras}

    EL UNICO PRECIO DEL COTIZADOR (11-10-2026). Habia dos: el boton de generar
    y la estimacion cotizaban con un 0,033 $ escrito a mano en presets_light, y
    Configuracion, la cola de notas y las laminas con 0,047 $ de esta tabla. El
    boton prometia un 30 % menos.

    Primero, lo que de verdad te han cobrado: la MEDIANA de tus ultimas 200
    imagenes de plano de esa calidad --y de ese MODO (foto o ilustracion), si
    se pide y ya hay bastantes--, tarifadas con el `usage` que devolvio OpenAI
    (asi lleva dentro las referencias adjuntas de TU estudio). Sin bastantes de
    ese modo, las de esa calidad en cualquier modo; sin bastantes de ninguna,
    la cuenta de la tabla: imagen devuelta + la entrada medida."""
    calidad = str(calidad or "low").lower()
    registradas = _imagenes_registradas()
    if modo in MODOS:
        cobradas = (registradas.get(f"{calidad}|{modo}") or [])[-200:]
        if len(cobradas) >= MUESTRAS_MINIMAS:
            nombre = "foto" if modo == "foto" else "ilustración"
            return {"usd": round(_mediana_de(cobradas), 4), "muestras": len(cobradas),
                    "modo": modo,
                    "fuente": f"lo que te han cobrado: mediana de tus últimas "
                              f"{len(cobradas)} imágenes de plano en {nombre}"}
    cobradas = (registradas.get(calidad) or [])[-200:]
    if len(cobradas) >= MUESTRAS_MINIMAS:
        return {"usd": round(_mediana_de(cobradas), 4), "muestras": len(cobradas),
                "fuente": f"lo que te han cobrado: mediana de tus últimas "
                          f"{len(cobradas)} imágenes de plano"}
    tabla = coste_por_imagen(calidad, tamano)
    return {"usd": tabla["usd_total"], "muestras": 0,
            "fuente": "tabla de OpenAI + las referencias medidas (aún no hay bastantes imágenes tuyas)"}


def usd_por_imagen(calidad, tamano=TAMANO, modo=None):
    return precio_por_imagen(calidad, tamano, modo)["usd"]


def tabla_de_costes(tamano=TAMANO):
    """Las tres calidades con su coste real y su multiplicador contra la base.

    `veces_total` es lo que de verdad se multiplica la factura y `veces_imagen`
    lo que parece si solo se mira la tabla de OpenAI. Se sirven LOS DOS: la
    diferencia entre 1,7 y 6,8 es la razon de ser de esta pantalla.
    """
    filas = [coste_por_imagen(c, tamano) for c in CALIDADES]
    base = filas[0]
    for fila in filas:
        fila["veces_total"] = (round(fila["usd_total"] / base["usd_total"], 1)
                               if base["usd_total"] else 0.0)
        fila["veces_imagen"] = (round(fila["usd_imagen"] / base["usd_imagen"], 1)
                                if base["usd_imagen"] else 0.0)
    return filas

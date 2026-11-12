"""HACER ESTE VÍDEO EN OTRO IDIOMA (rama otro-idioma, 11-11-2026).

QUÉ ES
------
Pedido del dueño: un vídeo hecho en español, el MISMO vídeo en inglés (o en
portugués…). No otro guion escrito de cero, sino ESTE guion traducido plano a
plano, con la voz en el otro idioma, los subtítulos y las cartelas traducidos,
y montado con las MISMAS imágenes, sin pagarlas otra vez.

    material(proyecto, estado)           -> lo que hay que traducir, por plano
    estimar(material, idioma)            -> lo que cuesta (voz y Claude), ANTES
    traducir(material, idioma, ...)      -> las traducciones (una llamada a Claude
                                            por cada tanda de planos)
    preparar_copia(copia, estado, material, traduccion, idioma, voz_id)
                                         -> deja la copia lista para grabar y montar

LA IDEA, Y POR QUÉ NO SE PAGA NINGUNA IMAGEN
---------------------------------------------
Las imágenes se guardan por el NÚMERO del plano (S001.png…) y p6 conserva toda
imagen que exista si nadie la pide («un cambio en el audio NUNCA deja imágenes
pendientes», 27-08). Lo único que hace falta es que la copia, al volver a cortar
la narración contra la voz nueva, salga con LOS MISMOS planos en el mismo orden.

Eso ya lo sabe hacer p6: `segmentar.heredar` pone el corte de antes (`corte`,
la narración de cada plano tal y como salió del segmentador) sobre las palabras
de la voz nueva. Aquí se traduce ESE corte, trozo a trozo, y se escribe
traducido en el plan de la copia: la voz nueva dice exactamente esas palabras,
así que el corte cae en las mismas fronteras y cada plano conserva su número y
su dibujo. Por lo mismo se traduce la `narracion` de cada plano en el plan y en
la ficha de su imagen: con eso p6 reconoce cada dibujo como el suyo (no lo
recoloca ni lo marca obsoleto).

El guion de la copia se escribe como EDICIÓN A MANO de cada bloque (`params.
guion.bloques`, que es una corrección de la salida y no mueve la firma propia
del guion: no se ofrece reescribirlo). Cada bloque es la suma de los trozos de
sus planos, en orden; un plano que cruza de un bloque al siguiente se traduce
en dos partes, una por bloque, para que ningún bloque diga de más ni de menos.

LO QUE NO SE TOCA, NUNCA
------------------------
El vídeo de origen: todo lo de aquí escribe en la COPIA, que acaba de nacer de
`Proyecto.duplicar` (regla 1 de CLAUDE.md).

LO QUE QUEDA EN EL IDIOMA DE ANTES, Y SE DICE ANTES DE PAGAR
-------------------------------------------------------------
- el texto que vaya DIBUJADO dentro de una imagen (un cartel, una pizarra): está
  en los píxeles, y cambiarlo es redibujar esa imagen (se paga, con una nota);
- las imágenes insertadas o quitadas a mano (`planos_insertados.json`,
  `planos_quitados.json`): se reconocen por su frase en el idioma de antes, así
  que en la copia no se aplican (la insertada desaparece, la quitada vuelve);
- los textos de Publicar (título, descripción, hashtags), que tienen su botón.
"""
from __future__ import annotations

import datetime
import difflib
import html
import json
import os
import re
import shutil

try:
    from . import cli_claude, comun, estadisticas, medios, marcas_tts
except ImportError:  # ejecutado con la carpeta pasos directamente en sys.path
    import cli_claude
    import comun
    import estadisticas
    import medios
    import marcas_tts

#: Los idiomas a los que se puede pasar un vídeo, con su nombre en la pantalla
#: y en la instrucción. Son los que Cartesia (sonic) locuta bien.
IDIOMAS = {
    "es": {"nombre": "español", "en_su_idioma": "Spanish", "corto": "ES"},
    "en": {"nombre": "inglés", "en_su_idioma": "English", "corto": "EN"},
    "pt": {"nombre": "portugués", "en_su_idioma": "Portuguese (Brazil)", "corto": "PT"},
    "fr": {"nombre": "francés", "en_su_idioma": "French", "corto": "FR"},
    "it": {"nombre": "italiano", "en_su_idioma": "Italian", "corto": "IT"},
    "de": {"nombre": "alemán", "en_su_idioma": "German", "corto": "DE"},
}

#: Cuánto ocupa el mismo texto en cada idioma, con el español como 1. Es lo
#: que se usa para decir cuántos caracteres va a cobrar la voz ANTES de
#: traducir: un número aproximado, y la pantalla lo dice como «unos».
LARGO_RELATIVO = {"es": 1.0, "en": 0.88, "pt": 1.0, "fr": 1.1, "it": 1.02, "de": 1.12}

#: Planos por llamada a Claude. Un vídeo de cuatro minutos son ~86 planos: una
#: o dos llamadas. Con el guion entero delante en cada una, para el contexto.
PLANOS_POR_LLAMADA = 70

#: Reintentos si Claude devuelve algo que no se puede leer o le faltan planos.
REINTENTOS = 2

#: Las claves de la configuración del vídeo que viajan a la copia: las que
#: dicen cómo se ve en la pantalla (vídeo del modo light, su estilo, sus
#: subtítulos, lo que lleva, su ritmo). NO viajan `voz_hecha_con` (es de la voz
#: de antes) ni `montaje_pendiente`.
CONFIG_QUE_VIAJA = ("video_light", "estilo_light", "subtitulos_del_estilo", "lleva",
                    "ritmo_del_video")

#: Dónde lo apunta la copia, en su proyecto.json (no en params: no es una
#: entrada de ningún paso).
CONFIG_TRADUCCION = "traduccion_de"


class ErrorOtroIdioma(RuntimeError):
    """No se puede hacer, con el motivo en castellano."""


# ------------------------------------------------------------------ material

def _limpia(palabra):
    return re.sub(r"[^\w]", "", medios.normalizar_texto(str(palabra or "")), flags=re.U)


def _palabras_de(texto):
    return [w for w in str(texto or "").split() if w.strip()]


def _bloques_de_voz(meta):
    """[(id, texto)] de la locución, en orden: lo que se oye (sin marcas)."""
    salida = []
    for bloque in (meta or {}).get("bloques") or []:
        if not isinstance(bloque, dict):
            continue
        bid = str(bloque.get("id") or "").strip().upper()
        if bid:
            salida.append((bid, marcas_tts.limpiar(str(bloque.get("texto") or ""))))
    return salida


def _bloque_de_cada_palabra(trozos, palabras, tramos, bloque_en):
    """El bloque de cada palabra de cada trozo, alineando con la voz. -> [[bid]]

    Los trozos son la narración de cada plano (lo que dejó el segmentador) y
    `palabras` las marcas de la voz, con su tiempo. Se alinean por texto (como
    `segmentar.heredar`) y cada palabra coge el bloque en el que cae su marca.
    Una palabra que no casa coge el de la de al lado.
    """
    viejas = []
    for indice, trozo in enumerate(trozos):
        for w in _palabras_de(trozo):
            viejas.append((indice, _limpia(w)))
    nuevas = [_limpia(p.get("w")) for p in palabras]
    mapa = {}
    for a, b, n in difflib.SequenceMatcher(None, [w for _i, w in viejas], nuevas,
                                           autojunk=False).get_matching_blocks():
        for k in range(n):
            mapa[a + k] = b + k
    bloques = []
    for k in range(len(viejas)):
        bid = ""
        if k in mapa:
            i = bloque_en(palabras[mapa[k]], tramos)
            bid = tramos[i][2] if i >= 0 else ""
        bloques.append(bid)
    # las que no casan, con la de al lado (primero hacia atras, luego delante)
    for k in range(len(bloques)):
        if not bloques[k] and k > 0:
            bloques[k] = bloques[k - 1]
    for k in range(len(bloques) - 1, -1, -1):
        if not bloques[k] and k + 1 < len(bloques):
            bloques[k] = bloques[k + 1]
    salida = [[] for _ in trozos]
    for (indice, _w), bid in zip(viejas, bloques):
        salida[indice].append(bid)
    return salida


def material(proyecto, estado, p6):
    """Lo que hay que traducir de este vídeo, plano a plano. -> dict

    {"idioma_origen", "trozos": [{"id": "T001", "partes": [{"bloque", "texto"}]}],
     "escenas": [{"id", "trozos": [indices]}], "sueltos": [{"bloque", "texto"}],
     "cartelas": {uid: {"campo": texto}}, "caracteres", "palabras",
     "planos", "con_imagen", "sin_dibujo": [ids], "avisos": [...]}

    `p6` es el módulo p6_assets (se pasa para no importarlo aquí: arrastra
    medio Studio). Lanza ErrorOtroIdioma si el vídeo no está para traducirse.
    """
    plan = p6.plan_actual(proyecto, "assets", estado=estado) or {}
    escenas = [e for e in (plan.get("escenas") or []) if isinstance(e, dict)]
    if not escenas:
        raise ErrorOtroIdioma("este vídeo todavía no tiene sus planos: genera las "
                              "imágenes antes de pasarlo a otro idioma")
    params_assets = estado.params("assets") or {}
    try:
        palabras, _muros, _ruta, meta = p6._palabras_narracion(
            proyecto, p6._con_defectos(params_assets))
    except Exception as fallo:                                   # noqa: BLE001
        raise ErrorOtroIdioma("este vídeo todavía no tiene la voz grabada: "
                              f"grábala antes de pasarlo a otro idioma ({fallo})")
    tramos = p6.tramos_de_bloque(meta)
    if not tramos:
        raise ErrorOtroIdioma("la voz de este vídeo no dice dónde empieza cada bloque "
                              "del guion (es de una versión muy antigua): vuelve a "
                              "grabarla antes de pasarlo a otro idioma")

    # LO INSERTADO Y LO QUITADO A MANO SE RECONOCE POR SU FRASE EN EL IDIOMA DE
    # ANTES (`insertar_planos`, `quitar_planos`): en la copia no casaría, el
    # vídeo saldría con otros planos y alguno se dibujaría (y se pagaría). Hasta
    # que se pueda traducir, no se ofrece: se dice qué hacer.
    raiz = proyecto.raiz
    insertados = _entradas_de(os.path.join(raiz, "planos_insertados.json"))
    quitados = _entradas_de(os.path.join(raiz, "planos_quitados.json"))
    if insertados or quitados:
        raise ErrorOtroIdioma(
            "este vídeo tiene imágenes insertadas o quitadas a mano "
            f"({insertados + quitados}), y esas se reconocen por su frase en este idioma: "
            "en la versión traducida cambiarían los planos y alguno se volvería a dibujar "
            "(y a pagar). Deshazlas antes (en Imágenes) o espera a que se pueda.")

    # LA UNIDAD QUE SE TRADUCE ES EL CORTE CRUDO (`plan["corte"]`), que es lo
    # que `segmentar.heredar` vuelve a poner sobre la voz nueva. Un plan de antes
    # del 31-08 no lo trae: entonces se traducen los planos tal cual. Y en el
    # modo «lo que dice el guion» tampoco vale: ahí el corte va por las líneas
    # del guion visual (por bloque, sin depender del idioma) y el `corte`
    # guardado es el de una voz anterior.
    modo_guion = False
    try:
        # COMO SE CORTÓ DE VERDAD, no lo que dice el ajuste: en modo «guion»
        # con el guion visual sin aprobar (o que ya no casa con la voz) el plan
        # se cortó por la voz, y entonces manda el `corte`
        modo_guion = (p6.guion_visual.modo_de(params_assets) == "guion"
                      and bool(plan.get("guion_visual_ok")))
    except Exception:                                            # noqa: BLE001
        modo_guion = False
    corte = [] if modo_guion else [str(x or "") for x in (plan.get("corte") or [])
                                   if str(x or "").strip()]
    if not corte:
        corte = [str(e.get("narracion") or "") for e in escenas
                 if str(e.get("narracion") or "").strip()]
    bloques_por_palabra = _bloque_de_cada_palabra(corte, palabras, tramos, p6._bloque_en)

    trozos = []
    for indice, (texto, bloques) in enumerate(zip(corte, bloques_por_palabra)):
        partes, actual, lista = [], None, []
        for w, bid in zip(_palabras_de(texto), bloques):
            if bid != actual and lista:
                partes.append({"bloque": actual, "texto": " ".join(lista)})
                lista = []
            actual = bid
            lista.append(w)
        if lista:
            partes.append({"bloque": actual, "texto": " ".join(lista)})
        trozos.append({"id": f"T{indice + 1:03d}", "partes": partes})

    # CADA PLANO DEL VÍDEO, COMO SUMA DE TROZOS. Los planos son el corte con las
    # cartelas fundidas (`_fundir_cartelas` junta trozos seguidos): se casan por
    # palabras, en orden. Con eso se sabe qué decir en la `narracion` del plano y
    # de la ficha de su imagen.
    escenas_trozos = _escenas_por_trozos(escenas, corte)

    # TODO LO QUE SE OYE, EN ALGÚN TROZO, Y CADA TROZO EN SU BLOQUE. Si un bloque
    # que se oye no lo dice ningún trozo (o un trozo no cae en ningún bloque),
    # la voz y el plan no casan: traducirlo aparte lo diría dos veces, y dejarlo
    # lo locutaría en el idioma de antes. Se pide poner el vídeo al día.
    con_trozo = {p["bloque"] for t in trozos for p in t["partes"]}
    sin_trozo = [bid for bid, texto in _bloques_de_voz(meta)
                 if bid not in con_trozo and texto.strip()]
    if sin_trozo or "" in con_trozo or None in con_trozo:
        raise ErrorOtroIdioma(
            "la voz y los planos de este vídeo no casan "
            f"({', '.join(sin_trozo[:4]) or 'un trozo sin bloque'}): vuelve a cortar los "
            "planos o a grabar la voz (Imágenes o Voz) antes de pasarlo a otro idioma")
    sueltos = []

    # LAS CARTELAS: su texto vive en la unidad de cada plano (`params.assets.
    # unidades[uid].cartela.datos`). Se traducen los campos de texto. Y se
    # coloca por su `ancla` (la frase en este idioma contra la que se decidió):
    # si esa frase es uno de los trozos, en la copia el ancla pasa a ser ese
    # trozo traducido (`anclas`: {uid: índice del trozo}); si no es ninguno,
    # tampoco casaba en el original, y las dos van por su número.
    clave_de = getattr(p6, "_texto_clave", None) or (
        lambda e: " ".join(_palabras_de(e.get("narracion") or "")))
    por_clave = {}
    for indice, texto in enumerate(corte):
        por_clave.setdefault(clave_de({"narracion": texto}), indice)
    cartelas, anclas = {}, {}
    for uid, bloque in ((params_assets.get("unidades") or {}).items()):
        datos = ((bloque or {}).get("cartela") or {}).get("datos") if isinstance(bloque, dict) else None
        if not isinstance(datos, dict):
            continue
        campos = {k: v for k, v in datos.items() if isinstance(v, str) and v.strip()}
        if campos:
            cartelas[str(uid)] = campos
        ancla = (bloque.get("cartela") or {}).get("ancla")
        if ancla:
            indice = por_clave.get(clave_de({"narracion": ancla}))
            if indice is not None:
                anclas[str(uid)] = indice

    # LO QUE NO TIENE DIBUJO TODAVÍA: en la copia se dibujaría (y se pagaría).
    base = os.path.dirname(medios.salida_de(proyecto, "assets", claves=("plan",),
                                            patrones=(r"plan\.json",), estado=estado) or "")
    sin_dibujo = []
    for escena in escenas:
        if p6.cartelas.sin_imagen(escena):
            continue
        if not os.path.exists(os.path.join(base, "escenas", f"{escena['id']}.png")):
            sin_dibujo.append(escena["id"])

    avisos = []
    if sin_dibujo:
        avisos.append(f"{len(sin_dibujo)} plano(s) no tienen imagen todavía "
                      f"({', '.join(sin_dibujo[:6])}{'…' if len(sin_dibujo) > 6 else ''}): "
                      "en la copia se dibujarían, y eso sí se paga.")

    texto_total = " ".join(p["texto"] for t in trozos for p in t["partes"])
    texto_total += " " + " ".join(s["texto"] for s in sueltos)
    texto_total += " " + " ".join(v for campos in cartelas.values() for v in campos.values())
    hablado = " ".join(texto for _bid, texto in _bloques_de_voz(meta)) or texto_total
    return {
        "idioma_origen": _idioma_origen(estado, hablado),
        "trozos": trozos,
        "escenas": escenas_trozos,
        "sueltos": sueltos,
        "cartelas": cartelas,
        "anclas": anclas,
        "modo_guion": modo_guion,
        "bloques_voz": [{"id": b.get("id"), "texto": b.get("texto")}
                        for b in ((meta or {}).get("bloques") or []) if isinstance(b, dict)],
        "ids": [str(e.get("id")) for e in escenas],
        "caracteres": len(hablado),
        "palabras": len(_palabras_de(texto_total)),
        "planos": len(escenas),
        "con_imagen": len([e for e in escenas if not p6.cartelas.sin_imagen(e)]),
        "sin_dibujo": sin_dibujo,
        "avisos": avisos,
    }


def _entradas_de(ruta):
    try:
        with open(ruta, "r", encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return 0
    # {"quitados": [...]} / {"insertados": [...]} (`quitar_planos`,
    # `insertar_planos`); una lista vacía (todo deshecho) no cuenta
    if isinstance(datos, dict):
        datos = [e for clave in ("quitados", "insertados")
                 for e in (datos.get(clave) or []) if isinstance(e, dict)]
    return len(datos) if isinstance(datos, list) else 0


def _idioma_origen(estado, texto):
    for paso, clave in (("voz", "idioma"), ("brief", "idioma_salida")):
        valor = str((estado.params(paso) or {}).get(clave) or "").strip().lower()
        if valor in IDIOMAS:
            return valor
    return medios.idioma_de(texto)


def _escenas_por_trozos(escenas, corte):
    """[{"id", "trozos": [i, j...]} | {"id", "trozos": [], "propio": texto}]

    Qué trozos del corte dice cada plano. Los planos son el corte con las
    cartelas fundidas (trozos seguidos juntos), así que normalmente cada plano
    es una suma exacta de trozos enteros. Se alinean las dos secuencias de
    palabras (como `segmentar.heredar`) y un plano se queda los trozos que caen
    enteros dentro de lo suyo SI con ellos dice exactamente lo suyo. Si no
    (un plano partido o juntado a mano), se le traduce lo suyo aparte
    (`propio`): su ficha tiene que decir lo que dice, en el otro idioma.
    """
    trozo_pal, trozo_rango = [], []
    for texto in corte:
        ini = len(trozo_pal)
        trozo_pal.extend(_limpia(w) for w in _palabras_de(texto))
        trozo_rango.append((ini, len(trozo_pal)))
    esc_pal, esc_rango = [], []
    for escena in escenas:
        ini = len(esc_pal)
        esc_pal.extend(_limpia(w) for w in _palabras_de(escena.get("narracion")))
        esc_rango.append((ini, len(esc_pal)))
    mapa = {}
    for a, b, n in difflib.SequenceMatcher(None, trozo_pal, esc_pal,
                                           autojunk=False).get_matching_blocks():
        for k in range(n):
            mapa[a + k] = b + k
    # cada trozo, a donde cae entero en las palabras de los planos (o a ningun sitio)
    donde = []
    for ini, fin in trozo_rango:
        posiciones = [mapa.get(k) for k in range(ini, fin)]
        if fin > ini and all(p is not None for p in posiciones) and \
                posiciones == list(range(posiciones[0], posiciones[0] + (fin - ini))):
            donde.append((posiciones[0], posiciones[-1] + 1))
        else:
            donde.append(None)
    salida = []
    for escena, (c, d) in zip(escenas, esc_rango):
        dentro = [i for i, r in enumerate(donde) if r and c <= r[0] and r[1] <= d]
        cubre = sorted(donde[i] for i in dentro)
        seguido = bool(cubre) and cubre[0][0] == c and cubre[-1][1] == d and all(
            x[1] == y[0] for x, y in zip(cubre, cubre[1:]))
        if seguido or d == c:
            salida.append({"id": escena.get("id"), "trozos": dentro})
        else:
            salida.append({"id": escena.get("id"), "trozos": [],
                           "propio": " ".join(_palabras_de(escena.get("narracion")))})
    return salida


# ------------------------------------------------------------------ el coste

def estimar(datos, idioma, tarifa_caracter=None, usd_por_imagen=None):
    """Lo que cuesta pasar el vídeo a `idioma`, dicho antes de hacer nada. -> dict

    La voz se cobra por carácter (Cartesia); se estima con el largo del texto
    de ahora por lo que ocupa el otro idioma. Claude va con la suscripción: no
    son dólares, son llamadas. Las imágenes son las mismas: 0.
    """
    if idioma not in IDIOMAS:
        raise ErrorOtroIdioma(f"idioma desconocido: {idioma}")
    origen = datos.get("idioma_origen") or "es"
    if idioma == origen:
        raise ErrorOtroIdioma(f"este vídeo ya está en {IDIOMAS[idioma]['nombre']}")
    factor = LARGO_RELATIVO.get(idioma, 1.0) / LARGO_RELATIVO.get(origen, 1.0)
    caracteres = int(round(int(datos.get("caracteres") or 0) * factor))
    usd_voz = (round(caracteres * float(tarifa_caracter), 2)
               if tarifa_caracter else None)
    llamadas = max(1, -(-len(datos.get("trozos") or []) // PLANOS_POR_LLAMADA))
    dibujar = len(datos.get("sin_dibujo") or [])
    usd_imagenes = round(dibujar * float(usd_por_imagen or 0), 2)
    return {
        "idioma": idioma,
        "nombre_idioma": IDIOMAS[idioma]["nombre"],
        "voz": {"caracteres": caracteres, "usd": usd_voz,
                "usd_por_caracter": tarifa_caracter},
        "claude": {"palabras": int(datos.get("palabras") or 0), "llamadas": llamadas,
                   "usd": 0.0},
        "imagenes": {"reutilizadas": int(datos.get("con_imagen") or 0) - dibujar,
                     "a_dibujar": dibujar, "usd": usd_imagenes},
        "usd_total": (round((usd_voz or 0.0) + usd_imagenes, 2)
                      if usd_voz is not None else None),
    }


# ------------------------------------------------------------- la traducción

SISTEMA = ("Eres traductor de guiones de vídeo para locución. Traduces con fidelidad, "
           "sin reescribir ni resumir, y contestas únicamente con el JSON pedido.")

INSTRUCCION = """Traduce al {destino} el guion de un vídeo narrado. Es una LOCUCIÓN: lo va a
leer una voz sintética y los subtítulos saldrán de lo mismo.

Reglas:
- Traduce, no reescribas: cada trozo dice lo MISMO que el original, en el mismo
  orden, sin añadir, quitar ni resumir nada. Que suene natural dicho en voz alta
  ({destino} neutro, como lo diría un locutor nativo).
- Los nombres propios, las marcas y los nombres de productos se quedan como están.
- Las cifras y las medidas, las mismas, y ESCRITAS CON LETRAS como se dicen en
  {destino} («four thousand kilometres», no «4,000 km»): la voz lee lo escrito,
  igual que en el original. Lo mismo con los símbolos (%, $, &).
- Cada <t> tiene una o varias <p> (partes). Devuelve EXACTAMENTE el mismo número
  de partes, cortando la traducción en el punto equivalente: cada parte va a un
  tramo distinto del audio.
- Sin etiquetas, sin comillas de más, sin notas.
- Los <c> son textos que salen ESCRITOS en pantalla (cartelas): tradúcelos cortos,
  con el mismo tono.

Para que entiendas el contexto, este es el guion entero en su idioma (NO lo traduzcas
aquí, solo los <t> y <c> de abajo):
<guion>
{guion}
</guion>

<traducir_video>
{textos}
</traducir_video>

Devuelve SOLO este JSON, con todos los ids:
{{"trozos": {{"<id>": ["<parte 1>", "<parte 2 si la hay>"]}}, "cartelas": {{"<id>": "<texto>"}}}}"""


def _xml(texto):
    return (str(texto or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _lote(trozos, cartelas):
    lineas = []
    for trozo in trozos:
        partes = "".join(f"<p>{_xml(p['texto'])}</p>" for p in trozo["partes"])
        lineas.append(f'<t id="{trozo["id"]}">{partes}</t>')
    for cid, texto in cartelas:
        lineas.append(f'<c id="{cid}">{_xml(texto)}</c>')
    return "\n".join(lineas)


def _limpio(texto):
    """Lo que vuelve de Claude, listo para locutar: sin etiquetas ni entidades."""
    texto = html.unescape(str(texto or ""))
    texto = re.sub(r"<[^>]*>", " ", texto)
    return " ".join(texto.replace("<", " ").replace(">", " ").split())


def traducir(datos, idioma, cwd=None, avisar=None, llamar=None):
    """Las traducciones de todo lo de `material`. -> {"trozos": {id: [partes]},
    "sueltos": {bid: texto}, "cartelas": {uid: {campo: texto}}}

    `llamar(instruccion, que)` -> dict es la llamada a Claude (se pasa en las
    pruebas); sin ella va por `cli_claude.ejecutar` con el modelo del guion.
    Lanza ErrorOtroIdioma si, tras los reintentos, falta algo: un vídeo a medio
    traducir se locutaría en dos idiomas.
    """
    destino = IDIOMAS[idioma]["en_su_idioma"]
    llamar = llamar or _llamar_a_claude(cwd, avisar)
    avisar = avisar or (lambda *_a, **_k: None)
    trozos = list(datos.get("trozos") or [])
    # los bloques sueltos van como trozos de una parte (su id no choca: «B»)
    for suelto in datos.get("sueltos") or []:
        trozos.append({"id": f"S_{suelto['bloque']}", "partes": [
            {"bloque": suelto["bloque"], "texto": suelto["texto"]}]})
    # y los planos que no casaron con el corte, para su ficha (`propio`)
    for escena in datos.get("escenas") or []:
        if escena.get("propio"):
            trozos.append({"id": f"P_{escena['id']}", "partes": [
                {"bloque": "", "texto": escena["propio"]}]})
    cartelas = []
    for uid, campos in (datos.get("cartelas") or {}).items():
        for campo, texto in campos.items():
            cartelas.append((f"C{len(cartelas) + 1:03d}", texto, uid, campo))
    guion = "\n".join(" ".join(p["texto"] for p in t["partes"])
                      for t in (datos.get("trozos") or []))

    hechos, hechas = {}, {}
    ultimo = ""
    lotes = [trozos[i:i + PLANOS_POR_LLAMADA] for i in range(0, len(trozos), PLANOS_POR_LLAMADA)]
    if not lotes:
        lotes = [[]]
    for numero, lote in enumerate(lotes):
        pendientes_c = [(cid, texto) for cid, texto, _u, _c in cartelas
                        if cid not in hechas] if numero == len(lotes) - 1 else []
        pendientes = list(lote)
        for _intento in range(1 + REINTENTOS):
            if not pendientes and not pendientes_c:
                break
            avisar(numero / max(1, len(lotes)),
                   f"traduciendo al {IDIOMAS[idioma]['nombre']} · tanda {numero + 1} de {len(lotes)}")
            instruccion = INSTRUCCION.format(destino=destino, guion=_xml(guion),
                                             textos=_lote(pendientes, pendientes_c))
            try:
                respuesta = llamar(instruccion, "la traduccion del video")
            except ErrorOtroIdioma:
                raise
            except Exception as fallo:                            # noqa: BLE001
                # PARAR ES PARAR: la cancelación del trabajo no se reintenta
                if type(fallo).__name__ == "Cancelado":
                    raise
                ultimo = str(fallo)
                continue
            vuelta = (respuesta or {}).get("trozos") if isinstance(respuesta, dict) else None
            for trozo in pendientes:
                partes = (vuelta or {}).get(trozo["id"]) if isinstance(vuelta, dict) else None
                if isinstance(partes, str):
                    partes = [partes]
                if not isinstance(partes, list):
                    continue
                partes = [_limpio(x) for x in partes]
                if len(partes) == len(trozo["partes"]) and all(partes):
                    hechos[trozo["id"]] = partes
                elif (len(trozo["partes"]) > 1 and len(partes) == 1 and partes[0]
                      and len(_palabras_de(partes[0])) >= len(trozo["partes"])):
                    # una sola parte para un trozo de varias: se reparte por
                    # palabras en la misma proporción que el original
                    hechos[trozo["id"]] = _repartir(partes[0], trozo["partes"])
            vuelta_c = (respuesta or {}).get("cartelas") if isinstance(respuesta, dict) else None
            for cid, _texto in pendientes_c:
                texto = _limpio((vuelta_c or {}).get(cid)) if isinstance(vuelta_c, dict) else ""
                if texto:
                    hechas[cid] = texto
            pendientes = [t for t in pendientes if t["id"] not in hechos]
            pendientes_c = [(c, t) for c, t in pendientes_c if c not in hechas]
        if pendientes or pendientes_c:
            faltan = [t["id"] for t in pendientes] + [c for c, _t in pendientes_c]
            raise ErrorOtroIdioma(
                "Claude no ha devuelto la traducción de todo el vídeo (faltan "
                f"{len(faltan)} trozos: {', '.join(faltan[:5])}…). No se ha grabado "
                "nada ni gastado nada en voz: vuelve a intentarlo."
                + (f"\n\nLo último que dijo: {ultimo[:300]}" if ultimo else ""))
    avisar(1.0, "traducción hecha")

    salida = {"trozos": {}, "sueltos": {}, "propios": {}, "cartelas": {}}
    for tid, partes in hechos.items():
        if tid.startswith("S_"):
            salida["sueltos"][tid[2:]] = partes[0]
        elif tid.startswith("P_"):
            salida["propios"][tid[2:]] = partes[0]
        else:
            salida["trozos"][tid] = partes
    for cid, _texto, uid, campo in cartelas:
        salida["cartelas"].setdefault(uid, {})[campo] = hechas[cid]
    return salida


def _repartir(texto, partes):
    palabras = _palabras_de(texto)
    pesos = [max(1, len(_palabras_de(p["texto"]))) for p in partes]
    total = sum(pesos)
    salida, desde = [], 0
    for indice, peso in enumerate(pesos):
        hasta = (len(palabras) if indice == len(pesos) - 1
                 else desde + max(1, round(len(palabras) * peso / total)))
        salida.append(" ".join(palabras[desde:hasta]) or palabras[-1])
        desde = hasta
    return salida


def _llamar_a_claude(cwd, avisar=None):
    """La llamada de verdad: el modelo y el esfuerzo del GUION (es el guion lo
    que se traduce, y el dueño lo quiere escrito con el modelo del guion).

    Con `avisar`, la llamada va con su `Avance`: «Cancelar» corta el CLI en el
    acto, en vez de esperar a que Claude termine la tanda."""
    ajuste = cli_claude.por_defecto_de("guion")

    def llamar(instruccion, que):
        avance = None
        if avisar is not None:
            try:
                avance = estadisticas.Avance(avisar, 0.1, 0.85, 240,
                                             "traduciendo el guion con Claude")
                avance.arrancar()
            except Exception:                                    # noqa: BLE001
                avance = None
        try:
            respuesta, _sobre = cli_claude.ejecutar(
                instruccion, modelo=ajuste["modelo"], esfuerzo=ajuste["esfuerzo"], cwd=cwd,
                base_tiempo_s=600, sistema=SISTEMA,
                extra=["--no-session-persistence"], para=que, avance=avance)
        finally:
            if avance is not None:
                avance.parar()
        datos = comun.extraer_json(respuesta, que)
        if not isinstance(datos, dict):
            raise ErrorOtroIdioma(f"{que}: Claude no ha devuelto un objeto JSON")
        return datos
    return llamar


# ---------------------------------------------------- la red, con la voz hecha

def comprobar_planos(copia, estado, p6, datos, esperadas=None):
    """Con la voz nueva ya grabada, ANTES de montar: ¿salen los mismos planos? -> resumen

    Es la red de seguridad del dinero. El corte nuevo se calcula igual que lo
    hará la tanda de imágenes (`planificar`, que no dibuja ni escribe nada) y
    se compara con el del vídeo de origen: los mismos planos con los mismos
    números, y cada uno que tenía su dibujo, con su PNG en la copia. Si algo no
    casa, ErrorOtroIdioma y no se monta: la voz ya está pagada, pero ninguna
    imagen se vuelve a dibujar sin que nadie lo vea.

    Si casa, cada ficha de imagen pasa a decir EXACTAMENTE lo que dice su plano
    ahora (la voz transcrita puede diferir de la traducción en una coma), para
    que `_recolocar_escenas` deje cada dibujo en su sitio.
    """
    plan = p6.planificar(copia, estado.params("assets") or {})
    escenas = [e for e in (plan.get("escenas") or []) if isinstance(e, dict)]
    ids = [str(e.get("id")) for e in escenas]
    esperados = [str(x) for x in (datos.get("ids") or [])]
    if ids != esperados:
        raise ErrorOtroIdioma(
            f"con la voz nueva el vídeo sale con {len(ids)} planos y el original tiene "
            f"{len(esperados)}: montarlo así volvería a dibujar (y pagar) imágenes. "
            "La voz está grabada; no se ha dibujado nada. Revisa la copia en "
            "Imágenes antes de montarla.")
    # Y CADA UNO DICIENDO LO SUYO: los ids son la posición (S001, S002...), así
    # que el mismo número de planos con otro reparto pasaría la cuenta de arriba
    # y cada dibujo acabaría ilustrando la frase de al lado
    if esperadas:
        normal = medios.normalizar_texto
        mismo = getattr(p6, "_mismo_dicho", None) or (lambda a, b: a == b)
        cambiados = [e["id"] for e in escenas
                     if esperadas.get(e["id"]) and not mismo(
                         normal(e.get("narracion") or ""), normal(esperadas[e["id"]]))]
        if cambiados:
            raise ErrorOtroIdioma(
                f"con la voz nueva, {len(cambiados)} plano(s) no dicen lo que se tradujo "
                f"para ellos ({', '.join(cambiados[:6])}): cada imagen acabaría en la frase "
                "de al lado. La voz está grabada; no se ha montado ni dibujado nada.")
    ruta_plan = medios.salida_de(copia, "assets", claves=("plan",),
                                 patrones=(r"plan\.json",), estado=estado)
    carpeta = os.path.join(os.path.dirname(ruta_plan or ""), "escenas")
    tolerados = set(datos.get("sin_dibujo") or [])
    faltan = [e["id"] for e in escenas
              if not p6.cartelas.sin_imagen(e) and e["id"] not in tolerados
              and not os.path.exists(os.path.join(carpeta, f"{e['id']}.png"))]
    if faltan:
        raise ErrorOtroIdioma(
            f"con la voz nueva, {len(faltan)} plano(s) que tenían imagen se quedarían sin "
            f"ella ({', '.join(faltan[:6])}): montarlo así los volvería a dibujar (y "
            "pagar). La voz está grabada; no se ha dibujado nada.")
    fichas = 0
    for escena in escenas:
        ruta = os.path.join(carpeta, f"{escena['id']}.json")
        ficha = medios.leer_json(ruta, None)
        if not isinstance(ficha, dict):
            continue
        dicho = escena.get("narracion_imagen") or escena.get("narracion") or ""
        if ficha.get("narracion") != dicho or "narracion_imagen" in ficha:
            ficha["narracion"] = dicho
            ficha.pop("narracion_imagen", None)
            medios.escribir_json(ruta, ficha)
            fichas += 1
    return {"planos": len(ids), "fichas_ajustadas": fichas}


# --------------------------------------------------------------- la copia

def textos_traducidos(datos, traduccion):
    """Lo que dice cada bloque y cada plano, ya traducido. -> (bloques, escenas)

    bloques: {bid: texto} en el orden de la voz; escenas: {sid: narración}.
    """
    bloques, orden = {}, []
    for trozo in datos.get("trozos") or []:
        partes = traduccion["trozos"].get(trozo["id"]) or []
        for parte, original in zip(partes, trozo["partes"]):
            bid = original["bloque"]
            if bid not in bloques:
                bloques[bid] = []
                orden.append(bid)
            bloques[bid].append(parte)
    for bid, texto in (traduccion.get("sueltos") or {}).items():
        if bid not in bloques:
            bloques[bid] = [texto]
            orden.append(bid)
    textos_bloque = {bid: " ".join(bloques[bid]).strip() for bid in orden if bid}
    por_trozo = [" ".join(traduccion["trozos"].get(t["id"]) or [])
                 for t in (datos.get("trozos") or [])]
    escenas = {}
    for escena in datos.get("escenas") or []:
        if escena.get("trozos"):
            escenas[escena["id"]] = " ".join(por_trozo[i] for i in escena["trozos"]).strip()
        elif (traduccion.get("propios") or {}).get(escena["id"]):
            escenas[escena["id"]] = traduccion["propios"][escena["id"]]
    return textos_bloque, escenas, por_trozo


def preparar_copia(copia, estado, datos, traduccion, idioma, voz_id="", origen=None,
                   p6=None):
    """Deja la COPIA lista para grabar la voz y montar en `idioma`. -> resumen

    Solo escribe en la copia: sus params (guion, voz, revisión, assets,
    callouts), su plan y las fichas de sus imágenes, y su proyecto.json.
    """
    bloques, escenas, por_trozo = textos_traducidos(datos, traduccion)
    if not bloques:
        raise ErrorOtroIdioma("la traducción no ha dejado ningún bloque que locutar")

    # 1. EL GUION: cada bloque, como edición a mano (no mueve la firma propia
    #    del guion, así que no se ofrece reescribirlo; la voz sí queda pendiente).
    guion = dict(estado.params("guion") or {})
    previos = dict(guion.get("bloques") or {}) if isinstance(guion.get("bloques"), dict) else {}
    previos.update(bloques)
    estado.actualizar_params("guion", {"bloques": previos})

    # 2. LA VOZ: el idioma nuevo y, si se eligió, otra voz. Sin voz elegida se
    #    queda la misma (sonic habla los dos idiomas con el mismo timbre).
    cambios_voz = {"idioma": idioma}
    if voz_id:
        cambios_voz["voz_id"] = str(voz_id)
    estado.actualizar_params("voz", cambios_voz)

    # 3. LA REVISIÓN POR SECCIONES: sus comentarios son notas sobre el texto de
    #    antes; aplicados a la traducción la reescribirían en el otro idioma.
    #    Y sus claves de voz (idioma, voz) eran las del original: la resíntesis
    #    saldría en el idioma de antes. Fuera, para que mande la de `voz`.
    revision = dict(estado.params("revision_audio") or {})
    if revision.get("comentarios") or any(k in revision for k in ("idioma", "voz_id", "voz")):
        revision["comentarios"] = []
        for clave in ("idioma", "voz_id", "voz"):
            revision.pop(clave, None)
        estado.set_params("revision_audio", revision)

    # 4. LAS IMÁGENES: las cartelas traducidas y, si el vídeo cortaba por el
    #    guion visual (líneas en el idioma de antes), por la voz: el corte tiene
    #    que caer en los mismos planos que el original, y eso lo hace `heredar`.
    assets = estado.params("assets") or {}
    unidades = {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in (assets.get("unidades") or {}).items()}
    anclas = datos.get("anclas") or {}
    tocadas = set(traduccion.get("cartelas") or {}) | set(anclas)
    for uid in tocadas:
        bloque = unidades.get(uid)
        if not isinstance(bloque, dict) or not isinstance(bloque.get("cartela"), dict):
            continue
        cartela = dict(bloque["cartela"])
        campos = (traduccion.get("cartelas") or {}).get(uid) or {}
        if campos:
            cartela["datos"] = dict(cartela.get("datos") or {}, **campos)
        indice = anclas.get(uid)
        if indice is not None and 0 <= indice < len(por_trozo) and por_trozo[indice]:
            cartela["ancla"] = por_trozo[indice]
        bloque["cartela"] = cartela
        unidades[uid] = bloque
    cambios_assets = {}
    if tocadas:
        cambios_assets["unidades"] = unidades
    # EL GUION VISUAL SE QUEDA (si el vídeo dibujaba «lo que dice el guion»): el
    # corte va por sus líneas, bloque a bloque, y eso no depende del idioma, así
    # que salen los mismos planos. Las líneas de la Parrilla se dan por buenas
    # si casan con el texto del guion (`efectivo`); traducido ya no casarían, así
    # que en la copia se guardan aprobadas, tal y como mandaban en el original.
    if p6 is not None and datos.get("modo_guion"):
        try:
            meta_bloques = [{"id": b.get("id"), "texto": b.get("texto")}
                            for b in (datos.get("bloques_voz") or [])]
            lineas, origen_gv = p6.guion_visual.efectivo(assets, meta_bloques)
            if lineas and origen_gv == "parrilla":
                gv = dict(p6.guion_visual.normalizar(assets.get("guion_visual")))
                gv["planos"] = [{k: v for k, v in pl.items() if k != "id"} for pl in lineas]
                gv["aprobado"] = True
                cambios_assets["guion_visual"] = gv
        except Exception:                                          # noqa: BLE001
            pass
    if cambios_assets:
        estado.actualizar_params("assets", cambios_assets)

    # 5. LOS SUBTÍTULOS ESCRITOS A MANO eran del idioma de antes: fuera.
    callouts = estado.params("callouts") or {}
    cu = callouts.get("unidades") or {}
    limpias, tocado = {}, False
    for uid, bloque in cu.items():
        # y los ELEMENTOS (flechas, rótulos) colocados sobre una palabra dicha:
        # su palabra ya no se dice
        fuera = ("subtitulo_texto", "subtitulo_ancla", "elementos")
        if isinstance(bloque, dict) and any(k in bloque for k in fuera):
            bloque = {k: v for k, v in bloque.items() if k not in fuera}
            tocado = True
        if bloque:
            limpias[uid] = bloque
    if tocado:
        nuevos = dict(callouts)
        if limpias:
            nuevos["unidades"] = limpias
        else:
            nuevos.pop("unidades", None)
        estado.set_params("callouts", nuevos)

    # 6. EL PLAN Y LAS FICHAS DE LAS IMÁGENES, con lo que se dice traducido. Es
    #    lo que hace que el corte nuevo caiga en los mismos planos (`corte`) y
    #    que cada dibujo se reconozca como el suyo (`narracion`).
    ruta_plan = medios.salida_de(copia, "assets", claves=("plan",),
                                 patrones=(r"plan\.json",), estado=estado)
    if not ruta_plan or not os.path.exists(ruta_plan):
        raise ErrorOtroIdioma("la copia no tiene el plan de los planos")
    plan = medios.leer_json(ruta_plan, {}) or {}
    if plan.get("corte"):
        plan["corte"] = [t for t in por_trozo]
    traducidas = 0
    for escena in plan.get("escenas") or []:
        nuevo = escenas.get(escena.get("id"))
        if not nuevo:
            continue
        escena["narracion"] = nuevo
        escena.pop("narracion_imagen", None)
        traducidas += 1
    plan[CONFIG_TRADUCCION] = {"idioma": idioma, "de": origen}
    medios.escribir_json(ruta_plan, plan)
    carpeta = os.path.join(os.path.dirname(ruta_plan), "escenas")
    fichas = 0
    for sid, nuevo in escenas.items():
        ruta = os.path.join(carpeta, f"{sid}.json")
        ficha = medios.leer_json(ruta, None)
        if not isinstance(ficha, dict):
            continue
        ficha["narracion"] = nuevo
        ficha.pop("narracion_imagen", None)
        medios.escribir_json(ruta, ficha)
        fichas += 1

    # 7. Y LO QUE NO VIAJA: lo insertado y lo quitado a mano se reconoce por su
    #    frase en el idioma de antes (ver el docstring). `duplicar` no lo copia,
    #    pero si alguien lo pusiera a mano, fuera.
    for nombre in ("planos_insertados.json", "planos_quitados.json"):
        ruta = os.path.join(copia.raiz, nombre)
        if os.path.exists(ruta):
            apartado = os.path.join(copia.raiz, "_otro_idioma")
            os.makedirs(apartado, exist_ok=True)
            shutil.move(ruta, os.path.join(apartado, nombre))

    copia.config[CONFIG_TRADUCCION] = {
        "video": origen, "idioma": idioma,
        "fecha": datetime.datetime.now().isoformat(timespec="seconds")}
    copia.guardar_config()
    return {"bloques": len(bloques), "planos": traducidas, "fichas": fichas,
            "cartelas": sum(len(c) for c in (traduccion.get("cartelas") or {}).values())}

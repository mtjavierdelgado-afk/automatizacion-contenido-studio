"""El SEO de Publicar (rama `publicar-seo`, 18-10-2026).

Lo que hace que un vídeo se ENCUENTRE, no solo que se vea bonito: la palabra
clave del proyecto y la de cada vídeo, la zona, los campos que Upload-Post
acepta además del texto (ubicación de Instagram, categoría e idiomas de
YouTube, ubicación de TikTok, primer comentario), la nota SEO de cada red (sin
Claude y sin coste) y las instrucciones para las pasadas con Claude
(«Optimizar SEO», «Dame 3 ganchos», «Proponer palabras clave»).

Este módulo NO lee ni escribe ficheros ni llama a Claude: es todo cuentas y
textos. Quien guarda y quien lanza los hilos es `pasos/publicar.py`. Nada de
aquí entra en ninguna firma de un vídeo.

Campos de Upload-Post (docs.upload-post.com/api/upload-video, verificados el
18-10-2026 en el encargo): Instagram `location_id`, `collaborators`,
`user_tags`; YouTube `categoryId`, `defaultLanguage`, `defaultAudioLanguage`,
`selfDeclaredMadeForKids`, `tags`; TikTok `tiktok_location_id` +
`tiktok_location_name` (capacidad «location» de la cuenta); primer comentario
`<red>_first_comment` (en TikTok, capacidad «comments»). Instagram NO tiene
texto alternativo en Upload-Post.
"""

import re
import unicodedata

#: Las categorías de YouTube, con su nombre en castellano (categoryId).
CATEGORIAS_YOUTUBE = [
    ("1", "Cine y animación"), ("2", "Motor"), ("10", "Música"),
    ("15", "Mascotas y animales"), ("17", "Deportes"), ("19", "Viajes y eventos"),
    ("20", "Videojuegos"), ("22", "Gente y blogs"), ("23", "Comedia"),
    ("24", "Entretenimiento"), ("25", "Noticias y política"),
    ("26", "Consejos y estilo"), ("27", "Educación"), ("28", "Ciencia y tecnología"),
    ("29", "ONG y activismo"),
]
IDIOMAS = [("es", "Español"), ("en", "Inglés"), ("pt", "Portugués")]
#: SOLO códigos «idioma-PAÍS»: es lo único que acepta Upload-Post (20-10-2026,
#: el Short no subía con «es-419»; ver `idioma_audio_youtube` en el cliente).
#: El español de Latinoamérica va como «es-US»; lo guardado antes con «es-419»,
#: «es» o «en» se sigue leyendo y se manda traducido.
IDIOMAS_AUDIO = [("es-US", "Español de Latinoamérica (es-US)"), ("es-MX", "Español de México"),
                 ("es-ES", "Español de España"), ("en-US", "Inglés"),
                 ("pt-BR", "Portugués de Brasil")]

#: Lo SEO que es fijo de cada proyecto (se suma a los ajustes de Publicar).
AJUSTES_SEO = {
    "palabra_clave": "",            # «alquiler de consolas en Lima»
    "secundarias": "",              # separadas por comas
    "zona": "",                     # «Lima, Perú» (y distritos)
    "evitar": "",                   # palabras que no se usan nunca
    "ig_ubicacion": "",             # location_id: id numérico de un Lugar/Página de Facebook
    "ig_ubicacion_nombre": "",      # solo para que se lea en la pantalla
    "tt_ubicacion_id": "",
    "tt_ubicacion_nombre": "",
    "tt_ubicacion_puede": False,    # la cuenta de TikTok tiene la capacidad «location»
    "tt_comentarios_puede": False,  # … y la capacidad «comments»
    "yt_categoria": "22",
    "yt_idioma": "es",
    "yt_idioma_audio": "es-US",
    "yt_para_ninos": False,
    "hashtags_amplios": "",
    "hashtags_nicho": "",
    "hashtags_locales": "",
    "optimizar_al_escribir": False,
}
BOOLEANOS = ("tt_ubicacion_puede", "tt_comentarios_puede", "yt_para_ninos",
             "optimizar_al_escribir")
LARGOS = {"palabra_clave": 80, "secundarias": 500, "zona": 120, "evitar": 300,
          "ig_ubicacion": 30, "ig_ubicacion_nombre": 120, "tt_ubicacion_id": 60,
          "tt_ubicacion_nombre": 120, "hashtags_amplios": 300, "hashtags_nicho": 300,
          "hashtags_locales": 300}

#: Cuántos hashtags pide cada red (los mismos números que las reglas del texto).
import publicar_redes as _RD                                   # noqa: E402
import os as _os                                               # noqa: E402
import sys as _sys                                             # noqa: E402
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _RAIZ not in _sys.path:
    _sys.path.insert(0, _RAIZ)
from motores.publicar_uploadpost import cliente as _UP         # noqa: E402
import seo_real as SR                                          # noqa: E402

RANGO_HASHTAGS = {"tiktok": (3, 5), "instagram": (5, 8), "youtube": (3, 5), "facebook": (2, 4),
                  **_RD.HASHTAGS}
#: CUÁNTOS HASHTAGS ADMITE CADA RED como mucho (notas del 19-10: antes se
#: cortaba en 15 sin decir nada). Instagram rechaza el post con más de 30;
#: YouTube ignora TODOS si lleva más de 60. Las demás no dicen un tope claro
#: (Upload-Post tampoco, /resources/character-limits): 30. Lo que sobre no se
#: manda, y la ficha lo dice (`componer`).
TOPE_HASHTAGS = {"instagram": 30, "youtube": 60}
TOPE_HASHTAGS_DEFECTO = 30
#: Lo más que se GUARDA por red: más que cualquier tope, para que lo que sobra
#: se vea en el aviso y no desaparezca al guardar.
TOPE_HASHTAGS_GUARDADOS = 100


def tope_hashtags(red):
    return TOPE_HASHTAGS.get(red, TOPE_HASHTAGS_DEFECTO)


#: Hashtags que no posicionan nada: o vacíos, o de los que las redes castigan.
HASHTAGS_VACIOS = {"fyp", "foryou", "foryoupage", "fy", "parati", "paratii", "viral",
                   "viralvideo", "trending", "tendencia", "xyzbca", "explore", "explorepage",
                   "reels", "reel", "tiktok", "instagram", "youtube", "shorts", "follow",
                   "like", "likes", "followme", "follow4follow", "like4like", "f4f", "l4l"}
#: Largo de la primera línea que se ve sin pulsar «más».
PRIMERA_LINEA = {"instagram": 125, "tiktok": 150, "facebook": 125, "youtube": 0,
                 **_RD.PRIMERA_LINEA}
_ALIAS_OPT = {"instagram": ("instagram", "reels"), "tiktok": ("tiktok",), "youtube": ("youtube",),
              "facebook": ("facebook",), **_RD.ALIAS}
#: Donde Upload-Post acepta primer comentario (`<red>_first_comment`).
CON_PRIMER_COMENTARIO = ("instagram", "facebook", "youtube", "tiktok")

CAMPOS_OPTIMIZABLES = ("titulo", "descripcion", "cta", "hashtags", "primer_comentario")


class ErrorSeo(ValueError):
    pass


# ------------------------------------------------------------------ utilidades

def sin_tildes(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower()


def lista(texto, tope=12):
    """«a, b\\nc» -> ["a", "b", "c"] sin vacíos ni repetidos."""
    salida = []
    for trozo in re.split(r"[,\n;]+", str(texto or "")):
        trozo = " ".join(trozo.split()).strip(" #")
        if trozo and sin_tildes(trozo) not in {sin_tildes(x) for x in salida}:
            salida.append(trozo)
    return salida[:tope]


def contiene(texto, frase):
    """¿Dice el texto la frase? Sin tildes ni mayúsculas, y aceptando que la
    frase salga entera o con todas sus palabras de más de 3 letras juntas en
    la misma línea («consolas en Lima» vale para «alquiler de consolas en Lima»
    solo si están todas)."""
    t, f = sin_tildes(texto), sin_tildes(frase).strip()
    if not f:
        return False
    if f in t:
        return True
    palabras = [p for p in re.findall(r"\w+", f) if len(p) > 3]
    if not palabras:
        return False
    return any(all(p in linea for p in palabras) for linea in t.splitlines())


def slug(texto, tope=60):
    t = re.sub(r"[^a-z0-9]+", "-", sin_tildes(texto)).strip("-")
    return t[:tope].strip("-")


def nombre_fichero(palabra, nombre_video, pid):
    """El nombre con el que se SUBE el MP4 (el del proyecto no cambia):
    «alquiler-consolas-lima-fiesta-en-casa.mp4»."""
    partes = [slug(palabra, 45), slug(nombre_video, 35)]
    base = "-".join(p for p in partes if p) or slug(pid) or "video"
    return f"{base[:80].strip('-')}.mp4"


def validar(k, v):
    """Un ajuste SEO, limpio; ErrorSeo si no vale."""
    if k in BOOLEANOS:
        if not isinstance(v, bool):
            raise ErrorSeo(f"«{k}» es sí o no")
        return v
    if not isinstance(v, str):
        raise ErrorSeo(f"«{k}» es un texto")
    v = " ".join(v.split()) if k not in ("secundarias", "evitar") else v.strip()
    if len(v) > LARGOS.get(k, 200):
        raise ErrorSeo(f"«{k}» pasa de {LARGOS.get(k, 200)} caracteres")
    if k == "ig_ubicacion" and v and not re.fullmatch(r"\d{5,25}", v):
        raise ErrorSeo("la ubicación de Instagram es el NÚMERO de un Lugar o una Página "
                       "de Facebook (solo cifras; pulsa «Guía» para ver cómo encontrarlo)")
    if k == "yt_categoria" and v not in {c for c, _n in CATEGORIAS_YOUTUBE}:
        raise ErrorSeo("esa categoría de YouTube no existe")
    if k == "yt_idioma" and v not in {c for c, _n in IDIOMAS}:
        raise ErrorSeo("ese idioma no está en la lista")
    if k == "yt_idioma_audio":
        v = _UP.idioma_audio_youtube(v) or v          # «es-419» de antes -> «es-US»
    if k == "yt_idioma_audio" and v not in {c for c, _n in IDIOMAS_AUDIO}:
        raise ErrorSeo("ese idioma del audio no está en la lista")
    if k == "tt_ubicacion_id" and v and not re.fullmatch(r"[A-Za-z0-9_\-]{3,60}", v):
        raise ErrorSeo("el id de la ubicación de TikTok lleva letras, números, «_» o «-»")
    return v


def palabra_del_video(datos_video, ajustes, info=None):
    """La palabra clave que manda en este vídeo.

    La suya, si la tiene. Si no, la del proyecto SOLO si el vídeo trata de eso
    (rama seo-real, 20-10: la nota pedía meter «alquiler de consolas en Lima»
    en vídeos que no iban de alquilar consolas); si no lo trata, la que propuso
    Claude al leer el vídeo; si tampoco, ninguna. Sin `info` (quien no tiene
    el vídeo a mano, como la cuenta de lo ya publicado) es la de antes: la
    suya o la del proyecto."""
    propia = str((datos_video or {}).get("palabra_clave") or "").strip()
    if propia:
        return propia
    proyecto = str((ajustes or {}).get("palabra_clave") or "").strip()
    if info is None:
        return proyecto
    if proyecto and SR.es_relevante(proyecto, info, (ajustes or {}).get("zona") or ""):
        return proyecto
    return " ".join(str((datos_video or {}).get("palabra_propuesta") or "").split())[:80]


def secundarias_del_video(ajustes, info=None, tope=8):
    """Las secundarias del proyecto que ESTE vídeo trata (todas, sin `info`)."""
    todas = lista((ajustes or {}).get("secundarias"), tope)
    if info is None:
        return todas
    corpus = SR.Corpus(info, (ajustes or {}).get("zona") or "")
    return [s for s in todas if SR.es_relevante(s, corpus=corpus)]


def hashtag_de(frase):
    return re.sub(r"[^\w]", "", sin_tildes(frase).replace(" ", ""), flags=re.U)[:40]


# -------------------------------------------------------- lo que se pide a Claude

def bloque_instruccion(ajustes, palabra, redes, recientes=None, aprendido=None, info=None,
                       busquedas=""):
    """El apartado SEO de la instrucción de los textos. Vacío si el proyecto no
    tiene ni palabra clave ni zona (los textos salen como antes). Con `info`,
    las secundarias que el vídeo no trata no se piden (rama seo-real), y
    `busquedas` son las frases que la gente busca de verdad (`seo_real`)."""
    ajustes = ajustes or {}
    secundarias = secundarias_del_video(ajustes, info)
    zona = str(ajustes.get("zona") or "").strip()
    evitar = lista(ajustes.get("evitar"), 20)
    banco = {k: lista(ajustes.get(f"hashtags_{k}"), 20) for k in ("amplios", "nicho", "locales")}
    if not (palabra or secundarias or zona or any(banco.values())):
        return ""
    lineas = ["SEO (que se ENCUENTRE el vídeo; con naturalidad, nunca listas de palabras)",
              "- NUNCA metas una palabra clave de algo que el vídeo no trata: quien la busque "
              "y no lo encuentre se va, y eso hunde el vídeo."]
    if not palabra and info is not None:
        lineas.append("- Este vídeo no tiene palabra clave todavía: usa la frase más concreta "
                      "que alguien escribiría en el buscador para encontrar ESTE vídeo (de lo "
                      "que trata de verdad) y ponla en la primera línea y al principio del título.")
    if busquedas:
        lineas.append("- Lo que la gente BUSCA de verdad (autocompletado de YouTube y Google, "
                      "Perú), solo frases que el vídeo trata; usa las que encajen:\n" + busquedas)
    if palabra:
        lineas.append(f"- Palabra clave de ESTE vídeo: «{palabra}». Va en la PRIMERA LÍNEA de "
                      "cada red; al PRINCIPIO del título de YouTube y de Facebook; y en YouTube "
                      "otra vez en las dos primeras líneas de la descripción.")
    if secundarias:
        lineas.append("- Palabras clave secundarias, repartidas donde encajen (no todas en "
                      "todas las redes): " + "; ".join(f"«{s}»" for s in secundarias) + ".")
    if zona:
        lineas.append(f"- Zona: «{zona}». Nómbrala en el texto y pon al menos un hashtag local.")
    if evitar:
        lineas.append("- NO uses nunca: " + "; ".join(f"«{e}»" for e in evitar) + ".")
    if any(banco.values()):
        lineas.append("- Banco de hashtags del proyecto (elige de aquí SOLO los que tengan que "
                      "ver con este vídeo, y ROTA: no pongas siempre el mismo bloque): " + "; ".join(
                          f"{k}: {', '.join(v)}" for k, v in banco.items() if v) + ".")
    if recientes:
        lineas.append("- Hashtags que ya salieron en los últimos vídeos (cambia al menos la "
                      "mitad): " + ", ".join(recientes[:20]) + ".")
    if aprendido:
        lineas.append("- Lo que MEJOR funcionó en este proyecto (aprende del gancho, no lo "
                      "copies):\n" + "\n".join(f"  · {a}" for a in aprendido[:5]))
    lineas.append("- Primer comentario: una pregunta que invite a comentar o un dato extra "
                  "con alguna palabra clave (corto, sin hashtags).")
    lineas.append("- Además, en la clave \"palabra_clave\" del JSON, propón la palabra clave "
                  "más concreta para ESTE vídeo (de 2 a 6 palabras, como la buscaría alguien).")
    return "\n".join(lineas)


SISTEMA_OPTIMIZAR = ("Eres un revisor SEO de redes sociales. Mejoras textos ya escritos "
                     "para que se encuentren y enganchen, sin cambiar lo que dicen ni "
                     "inventar datos (teléfonos, precios, enlaces, fechas). Si un campo ya "
                     "está bien, lo dejas igual. Contestas únicamente con el JSON pedido.")

INSTRUCCION_OPTIMIZAR = """Revisa el SEO de los textos con los que se va a publicar este vídeo.

<video>
Nombre: {nombre} · Duración: {duracion}
</video>

<seo>
Palabra clave del vídeo: {palabra}
Secundarias: {secundarias}
Zona: {zona}
Palabras a evitar: {evitar}
</seo>

<guion>
{guion}
</guion>

<busquedas_reales>
{busquedas}
</busquedas_reales>

<lo_que_mejor_funciono_en_la_cuenta>
{aprendido}
</lo_que_mejor_funciono_en_la_cuenta>

<textos_actuales>
{textos}
</textos_actuales>

<nota_seo_sin_claude>
{nota}
</nota_seo_sin_claude>

REGLAS DE CADA RED
{reglas}

NUNCA metas una palabra clave de algo que el vídeo no trata (mira el guion): si la
palabra clave de arriba no es de este vídeo, no la fuerces y propón otra en
"palabra_clave". Si hay búsquedas reales, prefiere esas frases (son lo que la gente
escribe) siempre que el vídeo trate de eso. Aprende de los ganchos que mejor
funcionaron en la cuenta (el estilo, no las palabras).

Para cada red: arregla los fallos de la nota y lo que veas (palabra clave al principio
del título y en la primera línea, primera línea que enganche, hashtags en su rango y
con uno local, un CTA claro, primer comentario que invite a contestar). No cambies lo
que ya está bien: deja ese campo igual. Mantén el idioma, el tono y los emojis: si
reescribes una línea que llevaba emojis, que los siga llevando (son del proyecto).

La nota la pone el Studio con sus cuentas: no pongas tú otra. En «fallos» van SOLO
los que la nota de arriba NO dice ya (no repitas sus puntos: la persona ya los ve con
su botón para arreglarlos), y solo los que no arreglas tú en «campos».

Devuelve SOLO este JSON, con estas claves de red tal cual: {claves}
{{
  "palabra_clave": "la palabra clave más concreta para ESTE vídeo (de 2 a 6 palabras, como la buscaría alguien)",
  "<red>": {{
    "fallos": ["lo que falla y no está en la nota, en una frase", "..."],
    "campos": {{
      "<campo>": {{"despues": "el texto mejorado (hashtags como lista)", "porque": "por qué, en una frase"}}
    }}
  }}
}}
Los campos posibles son: titulo (solo YouTube y Facebook), descripcion, cta, hashtags,
primer_comentario. Incluye SOLO los campos que cambias.
"""

INSTRUCCION_GANCHOS = """Escribe 3 ganchos distintos para la PRIMERA LÍNEA del texto de {red}
de este vídeo. Cada uno de menos de {largo} caracteres, con la palabra clave «{palabra}»
si cabe con naturalidad, en el idioma y el tono del texto. Uno pregunta, uno con un
dato o promesa concreta y uno que rompa la expectativa. Sin hashtags. {emojis}

<texto_actual>
{texto}
</texto_actual>

<guion>
{guion}
</guion>

Devuelve SOLO este JSON: {{"ganchos": ["...", "...", "..."]}}
"""

INSTRUCCION_PALABRAS = """Propón las palabras clave SEO de un negocio para sus vídeos en redes
(TikTok, Instagram, YouTube, Facebook): las frases que su cliente ESCRIBIRÍA en el
buscador.

<negocio>
Proyecto: {nombre}
Marca y lo que hace: {marca}
Zona que ya tiene apuntada: {zona}
</negocio>

<encargos_y_guiones_recientes>
{contexto}
</encargos_y_guiones_recientes>

Devuelve SOLO este JSON:
{{
  "principal": {{"frase": "de 2 a 6 palabras", "porque": "una frase"}},
  "secundarias": [{{"frase": "...", "porque": "..."}}],
  "zona": {{"frase": "ciudad, país (y distritos si se ve en el material)", "porque": "..."}}
}}
Entre 3 y 8 secundarias. En el idioma del material. Nada inventado: solo lo que el
negocio de verdad ofrece según el material.
"""


def normalizar_optimizacion(datos, redes):
    """{red: {fallos, campos: {campo: {despues, porque}}}} limpio. Sin nota: la
    única nota es la del Studio (`nota`), también la de «con estos cambios»."""
    datos = datos if isinstance(datos, dict) else {}
    salida = {}
    for red in redes:
        bruto = None
        for clave, valor in datos.items():
            suelta = re.sub(r"[^a-z0-9]", "", sin_tildes(clave))
            buscadas = {re.sub(r"[^a-z0-9]", "", a) for a in _ALIAS_OPT.get(red, (red,))}
            if isinstance(valor, dict) and (suelta in buscadas or (
                    red in ("instagram", "tiktok", "youtube", "facebook") and suelta.startswith(red))):
                bruto = valor
                break
        if not bruto:
            continue
        campos = {}
        brutos = bruto.get("campos") if isinstance(bruto.get("campos"), dict) else {}
        for campo, cambio in brutos.items():
            campo = sin_tildes(campo).replace(" ", "_")
            if campo not in CAMPOS_OPTIMIZABLES or not isinstance(cambio, dict):
                continue
            if campo == "titulo" and red not in ("youtube", "facebook") + tuple(_RD.TITULOS):
                continue
            despues = cambio.get("despues")
            if campo == "hashtags":
                despues = [hashtag_de(h) for h in (despues if isinstance(despues, list)
                                                   else re.split(r"[\s,]+", str(despues or "")))]
                despues = [h for h in despues if h][:tope_hashtags(red)]
                if not despues:
                    continue
            else:
                despues = str(despues or "").strip()
                if not despues:
                    continue
                if campo == "titulo":
                    despues = " ".join(despues.split())[:100]
            campos[campo] = {"despues": despues,
                             "porque": " ".join(str(cambio.get("porque") or "").split())[:300]}
        fallos = bruto.get("fallos")
        fallos = [fallos] if isinstance(fallos, str) else (fallos if isinstance(fallos, list) else [])
        salida[red] = {"campos": campos,
                       "fallos": [" ".join(str(f).split())[:200] for f in fallos if str(f).strip()][:8]}
    return salida


def palabra_de_optimizacion(datos):
    """La palabra clave que propone Claude en la revisión SEO ("" si ninguna)."""
    if not isinstance(datos, dict):
        return ""
    return " ".join(str(datos.get("palabra_clave") or "").split())[:80]


#: De qué habla cada punto de la nota, para no enseñar dos veces lo mismo: un
#: «fallo» de Claude que trata del tema de un punto que ya resta en la nota
#: sale de la propuesta (la nota lo dice, y con su botón). Sin tildes.
TEMAS_DE_PUNTO = {
    "palabra": r"palabra(s)? clave",
    "palabra_titulo": r"palabra(s)? clave",
    "palabra_primera": r"palabra(s)? clave",
    "palabra_descripcion": r"palabra(s)? clave",
    "ubicacion": r"ubicacion|location",
    "portada": r"portada|miniatura|thumbnail",
    "cta": r"llamada a la accion|\bcta\b",
    "hashtags": r"hashtag",
    "hashtags_vacios": r"hashtag",
    "hashtags_repetidos": r"hashtag",
    "hashtag_local": r"hashtag",
    "titulo_largo": r"titulo.*(largo|corto|caracteres)|(largo|corto|caracteres).*titulo",
    "primera_linea": r"primera linea.*(larga|corta|caracteres|se corta)",
    "texto": r"sin texto|no hay texto",
}


def fallos_nuevos(fallos, nota_red):
    """Los «fallos» de Claude que la nota del Studio NO dice ya."""
    abiertos = [p.get("id") for p in (nota_red or {}).get("puntos") or [] if not p.get("ok")]
    temas = [TEMAS_DE_PUNTO[i] for i in abiertos if i in TEMAS_DE_PUNTO]
    return [f for f in fallos or []
            if not any(re.search(t, sin_tildes(f)) for t in temas)]


def normalizar_ganchos(datos):
    lista_ = (datos or {}).get("ganchos") if isinstance(datos, dict) else datos
    salida = []
    for g in lista_ if isinstance(lista_, list) else []:
        g = " ".join(str(g or "").split()).strip()
        if g and g not in salida:
            salida.append(g[:200])
    return salida[:3]


def normalizar_palabras(datos):
    datos = datos if isinstance(datos, dict) else {}

    def una(x):
        if isinstance(x, str):
            x = {"frase": x}
        if not isinstance(x, dict) or not str(x.get("frase") or "").strip():
            return None
        return {"frase": " ".join(str(x["frase"]).split())[:80],
                "porque": " ".join(str(x.get("porque") or "").split())[:300]}

    principal = una(datos.get("principal"))
    secundarias = [s for s in (una(x) for x in (datos.get("secundarias") or [])) if s][:8]
    zona = una(datos.get("zona"))
    if not principal:
        raise ErrorSeo("Claude no ha propuesto ninguna palabra clave principal")
    return {"principal": principal, "secundarias": secundarias, "zona": zona}


# ----------------------------------------------------- lo que va a Upload-Post

def campos_extra(red, textos_red, ajustes, datos_video, info, palabra):
    """(campos, avisos) SEO de una red para Upload-Post, además del texto."""
    textos_red = textos_red or {}
    ajustes = ajustes or {}
    datos_video = datos_video or {}
    campos, avisos = {}, []
    comentario = " ".join(str(textos_red.get("primer_comentario") or "").split())[:500]
    if red == "instagram":
        if ajustes.get("ig_ubicacion"):
            campos["location_id"] = str(ajustes["ig_ubicacion"])
        colab = lista(datos_video.get("colaboradores"), 3)
        if colab:
            campos["collaborators"] = ",".join(c.lstrip("@") for c in colab)
        etiquetas = lista(datos_video.get("etiquetas"), 20)
        if etiquetas:
            campos["user_tags"] = ",".join(e.lstrip("@") for e in etiquetas)
    elif red == "youtube":
        campos["categoryId"] = str(ajustes.get("yt_categoria") or "22")
        campos["defaultLanguage"] = str(ajustes.get("yt_idioma") or "es")
        # tal cual: lo traduce a la forma de Upload-Post `campos_para_enviar`,
        # por donde pasa toda subida
        campos["defaultAudioLanguage"] = str(ajustes.get("yt_idioma_audio") or "es-US")
        campos["selfDeclaredMadeForKids"] = bool(ajustes.get("yt_para_ninos"))
    elif red == "tiktok":
        if ajustes.get("tt_ubicacion_id"):
            if ajustes.get("tt_ubicacion_puede"):
                campos["tiktok_location_id"] = str(ajustes["tt_ubicacion_id"])
                campos["tiktok_location_name"] = str(ajustes.get("tt_ubicacion_nombre") or "")
            else:
                avisos.append("la ubicación de TikTok no se manda: marca antes que tu cuenta "
                              "tiene la función «location»")
    if comentario and red in CON_PRIMER_COMENTARIO:
        if red == "tiktok" and not ajustes.get("tt_comentarios_puede"):
            avisos.append("el primer comentario de TikTok no se manda: marca antes que tu "
                          "cuenta tiene la función «comments»")
        else:
            campos[f"{red}_first_comment"] = comentario
    return campos, avisos


def etiquetas_youtube(ajustes, palabra, tags, info=None):
    """Las etiquetas (tags) de YouTube: la palabra del vídeo, la del proyecto,
    las secundarias y los hashtags, sin repetir y en menos de 450 caracteres.
    Con `info`, las del proyecto que el vídeo no trata se quedan fuera."""
    proyecto = (ajustes or {}).get("palabra_clave")
    if info is not None and proyecto and not SR.es_relevante(proyecto, info,
                                                            (ajustes or {}).get("zona") or ""):
        proyecto = ""
    candidatas = [palabra, proyecto]
    candidatas += secundarias_del_video(ajustes, info)
    candidatas += list(tags or [])
    salida, largo = [], 0
    for c in candidatas:
        c = " ".join(str(c or "").split()).strip(" #")
        if not c or sin_tildes(c) in {sin_tildes(x) for x in salida}:
            continue
        if largo + len(c) + 1 > 450:
            break
        salida.append(c)
        largo += len(c) + 1
    return salida


# ------------------------------------------------------------------ la nota SEO

#: Dónde se pone lo que es del PROYECTO: el nombre de verdad de la pantalla
#: (antes unos decían «Lo fijo → SEO» y otros «Cuentas y ajustes → SEO»).
DONDE_SEO_PROYECTO = "Publicar → Cuentas y ajustes → SEO de este proyecto"


def nota(red, textos_red, compuesto, ajustes, datos_video, info, palabra):
    """{nota: 0-100, puntos: [{id, ok, texto}]}: lo que se puede mirar SIN
    Claude. Cada punto dice el porqué; la nota es lo que pesan los que pasan.
    Es LA nota: la de la pantalla y la de «con estos cambios» de una revisión
    de Claude. El `id` dice qué arregla cada punto y la pantalla le pone UN
    botón (notas del 19-10): palabra, palabra_titulo, palabra_primera,
    palabra_descripcion, titulo_largo, primera_linea, hashtags,
    hashtags_vacios, hashtags_repetidos, hashtag_local, cta, ubicacion,
    portada y texto."""
    textos_red = textos_red or {}
    ajustes = ajustes or {}
    datos_video = datos_video or {}
    puntos = []

    def punto(id_, ok, texto, peso=10):
        puntos.append({"id": id_, "ok": bool(ok), "texto": texto, "peso": peso})

    descripcion = str(textos_red.get("descripcion") or "").strip()
    primera = descripcion.splitlines()[0].strip() if descripcion else ""
    titulo = str(textos_red.get("titulo") or "").strip()
    tags = [str(t) for t in (compuesto or {}).get("tags") or textos_red.get("hashtags") or []]
    if not descripcion:
        return {"nota": 0, "puntos": [{"id": "texto", "ok": False, "texto": "todavía no hay texto"}]}
    if palabra:
        if red in ("youtube", "facebook"):
            al_principio = contiene(titulo[:len(palabra) + 25], palabra)
            punto("palabra_titulo", al_principio, "palabra clave al principio del título" if al_principio else (
                "la palabra clave está en el título, pero no al principio"
                if contiene(titulo, palabra) else f"el título no lleva «{palabra}»"), 20)
        punto("palabra_primera", contiene(primera, palabra), "palabra clave en la primera línea"
              if contiene(primera, palabra) else f"la primera línea no dice «{palabra}»", 20)
        if red == "youtube":
            dos = "\n".join(descripcion.splitlines()[:2])
            punto("palabra_descripcion", contiene(dos, palabra),
                  "palabra clave en las dos primeras líneas de la descripción"
                  if contiene(dos, palabra) else "las dos primeras líneas de la descripción no la dicen", 10)
    else:
        punto("palabra", False, "sin palabra clave para este vídeo: escríbela o pulsa "
              "«Investigar búsquedas»", 20)
    if red == "youtube":
        n = len(titulo)
        punto("titulo_largo", 40 <= n <= 70, f"título de {n} caracteres" + ("" if 40 <= n <= 70 else
                                                                           " (mejor entre 40 y 70)"), 10)
    tope = PRIMERA_LINEA.get(red) or 0
    if tope:
        punto("primera_linea", len(primera) <= tope, f"primera línea de {len(primera)} caracteres"
              + ("" if len(primera) <= tope else f" (se corta a los {tope}: «más»)"), 10)
    minimo, maximo = RANGO_HASHTAGS[red]
    n = len(tags)
    en_rango = minimo <= n <= maximo
    punto("hashtags", en_rango, f"{n} hashtags" + ("" if en_rango else f" (en {red} van de {minimo} a {maximo})"), 10)
    vacios = sorted({t for t in tags if sin_tildes(t) in HASHTAGS_VACIOS})
    punto("hashtags_vacios", not vacios, "sin hashtags vacíos" if not vacios else
          "hashtags que no posicionan: " + ", ".join(f"#{v}" for v in vacios), 5)
    repetidos = len(tags) != len({sin_tildes(t) for t in tags})
    punto("hashtags_repetidos", not repetidos, "sin hashtags repetidos" if not repetidos
          else "hay hashtags repetidos", 5)
    zona = str(ajustes.get("zona") or "").strip()
    locales = [hashtag_de(x) for x in lista(ajustes.get("hashtags_locales"), 20)]
    if zona or locales:
        palabras_zona = [hashtag_de(p) for p in re.split(r"[,\s]+", zona) if len(p) > 3]
        local = any(any(z and z in sin_tildes(t) for z in palabras_zona + locales) for t in tags)
        punto("hashtag_local", local, "al menos un hashtag local" if local else "ningún hashtag de la zona", 5)
    punto("cta", bool(str(textos_red.get("cta") or "").strip()), "llamada a la acción"
          if str(textos_red.get("cta") or "").strip() else "falta la llamada a la acción", 10)
    if red == "instagram":
        punto("ubicacion", bool(ajustes.get("ig_ubicacion")), "ubicación puesta" if ajustes.get("ig_ubicacion")
              else f"sin ubicación de Instagram ({DONDE_SEO_PROYECTO})", 5)
    portada = (datos_video.get("portada") or {})
    punto("portada", portada.get("ms") is not None or bool(portada.get("imagen")),
          "portada elegida" if (portada.get("ms") is not None or portada.get("imagen"))
          else "sin portada elegida (cada red pondrá la suya)", 5)
    total = sum(p["peso"] for p in puntos) or 1
    bien = sum(p["peso"] for p in puntos if p["ok"])
    for p in puntos:
        p.pop("peso", None)
    return {"nota": round(100 * bien / total), "puntos": puntos}


def nota_como_texto(notas):
    """La nota SEO de cada red, en texto para pasársela a Claude."""
    lineas = []
    for red, n in (notas or {}).items():
        fallos = [p["texto"] for p in n.get("puntos", []) if not p["ok"]]
        lineas.append(f"- {red}: {n.get('nota')}/100" + (": " + "; ".join(fallos) if fallos else ""))
    return "\n".join(lineas) or "—"

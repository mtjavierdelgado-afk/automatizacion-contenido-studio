"""Las redes de Publicar además de las cuatro de siempre (rama `publicar-mas`,
18-10-2026): LinkedIn, X, Threads, Pinterest, Bluesky, Discord, Telegram,
Mastodon y Google Business Profile.

Lo que acepta cada una sale de la documentación de Upload-Post
(docs.upload-post.com/api/upload-video y /resources/character-limits, leídas el
18-10-2026). Lo que esa documentación no dice no se inventa: se avisa en la
ficha y se deja a la red. Reddit está en la documentación pero NO se ofrece:
Upload-Post devuelve 503 («reddit_unavailable») hasta nuevo aviso. WordPress
tampoco: no es una red social, es una web.

Este módulo no lee ficheros ni llama a nadie: dice cómo es cada red. Quien
compone el envío es `pasos/publicar.py`.
"""

import math
import os
import re

#: Las nuevas, en el orden en que salen en la pantalla.
REDES = ("linkedin", "x", "threads", "pinterest", "bluesky", "discord", "telegram",
         "mastodon", "google_business")

NOMBRE = {"linkedin": "LinkedIn", "x": "X (Twitter)", "threads": "Threads",
          "pinterest": "Pinterest", "bluesky": "Bluesky", "discord": "Discord",
          "telegram": "Telegram", "mastodon": "Mastodon",
          "google_business": "Google Business Profile"}
CORTO = {"linkedin": "LinkedIn", "x": "X", "threads": "Threads", "pinterest": "Pinterest",
         "bluesky": "Bluesky", "discord": "Discord", "telegram": "Telegram",
         "mastodon": "Mastodon", "google_business": "Google"}

#: Caracteres del texto que se publica (el pie). De /resources/character-limits.
#: Mastodon no está en esa página: 500 es lo que trae un servidor de fábrica.
LIMITES = {"linkedin": 3000, "x": 280, "threads": 500, "pinterest": 800, "bluesky": 300,
           "discord": 2000, "telegram": 1024, "mastodon": 500, "google_business": 1500}
#: Las que tienen un TÍTULO aparte del texto, con su tope.
TITULOS = {"linkedin": 400, "pinterest": 100}
#: Las que aceptan texto alternativo (`<red>_alt_text`) y su tope.
ALT = {"x": 1000, "threads": 1000, "pinterest": 500, "bluesky": 1000, "discord": 1000,
       "mastodon": 1500}
#: Cuántos hashtags pide cada una.
HASHTAGS = {"linkedin": (3, 5), "x": (1, 2), "threads": (0, 1), "pinterest": (2, 5),
            "bluesky": (1, 3), "discord": (0, 0), "telegram": (0, 3), "mastodon": (2, 4),
            "google_business": (0, 0)}
#: Lo que se ve antes de pulsar «más» (0 = no aplica).
PRIMERA_LINEA = {"linkedin": 210, "x": 0, "threads": 0, "pinterest": 100, "bluesky": 0,
                 "discord": 0, "telegram": 0, "mastodon": 0, "google_business": 0}

REGLAS = {
    "linkedin": ("LinkedIn: público profesional. TÍTULO corto (hasta 100 caracteres) que "
                 "diga el beneficio. TEXTO de 3 a 6 párrafos cortos: la primera línea "
                 "engancha (se corta a los ~210 caracteres con «ver más»), luego el contexto "
                 "y una idea útil. Tono cercano pero serio. CTA: comentar, escribir o visitar. "
                 "3 a 5 hashtags al final."),
    "x": ("X: el texto entero cabe en 280 caracteres CONTANDO la llamada a la acción y los "
          "hashtags: frase directa, una idea. X QUITA LOS ENLACES del texto: no pongas "
          "ninguno. 1 o 2 hashtags."),
    "threads": ("Threads: conversación. Máximo 500 caracteres en total, en tono de charla, "
                "con una pregunta que invite a contestar. Sin lista de hashtags (uno como "
                "mucho)."),
    "pinterest": ("Pinterest: es un BUSCADOR. TÍTULO de hasta 100 caracteres con la palabra "
                  "clave al principio. DESCRIPCIÓN de hasta 800 caracteres que explique qué "
                  "es y para quién, con palabras que alguien buscaría. 2 a 5 hashtags."),
    "bluesky": ("Bluesky: máximo 300 caracteres en total (con el CTA y los hashtags). Tono "
                "natural, sin aire de anuncio. 1 a 3 hashtags."),
    "discord": ("Discord: mensaje para una comunidad que ya te conoce (hasta 2.000 "
                "caracteres). Directo y cercano, sin hashtags."),
    "telegram": ("Telegram: pie del vídeo de hasta 1.024 caracteres. Primera línea clara, "
                 "párrafos cortos, el CTA al final. Sin hashtags o muy pocos."),
    "mastodon": ("Mastodon: hasta 500 caracteres, tono natural y sin exagerar. 2 a 4 "
                 "hashtags (en Mastodon se busca por ellos)."),
    "google_business": ("Google Business Profile: publicación del perfil de empresa en "
                        "Google (sale en Maps y en la búsqueda local). TEXTO de 1 a 3 frases "
                        "con lo que ofreces y la ZONA, sin hashtags ni emojis de más. El CTA "
                        "lo pone el botón del perfil."),
}
EMOJIS = {"linkedin": "1 a 2 emojis como mucho, sobrios", "x": "0 a 1 emoji",
          "threads": "1 o 2 emojis", "pinterest": "0 a 1 emoji",
          "bluesky": "0 a 2 emojis", "discord": "1 a 3 emojis",
          "telegram": "1 a 3 emojis", "mastodon": "0 a 2 emojis",
          "google_business": "ninguno"}
ALIAS = {"linkedin": ("linkedin", "linked in"), "x": ("x", "twitter", "xtwitter"),
         "threads": ("threads",), "pinterest": ("pinterest",), "bluesky": ("bluesky", "bsky"),
         "discord": ("discord",), "telegram": ("telegram",), "mastodon": ("mastodon",),
         "google_business": ("googlebusiness", "googlebusinessprofile", "google", "gbp",
                             "googlemybusiness")}

#: Lo fijo de cada proyecto para estas redes (se suma a sus ajustes).
AJUSTES_REDES = {
    "pinterest_tablero": "",        # pinterest_board_id (OBLIGATORIO en Pinterest)
    "pinterest_enlace": "",         # pinterest_link: adónde lleva el pin
    "linkedin_pagina": "",          # target_linkedin_page_id (vacío: el perfil personal)
    "linkedin_visibilidad": "PUBLIC",
    "gbp_cta": "",                  # BOOK, ORDER, SHOP, LEARN_MORE, SIGN_UP, CALL o ""
    "gbp_cta_url": "",              # obligatorio salvo con CALL
    "gbp_ubicacion": "",            # gbp_location_id (vacío: la única que haya)
    "mastodon_visibilidad": "public",
    "threads_tema": "",             # threads_topic_tag
}
CTA_GBP = [("", "Sin botón"), ("BOOK", "Reservar"), ("ORDER", "Pedir"), ("SHOP", "Comprar"),
           ("LEARN_MORE", "Más información"), ("SIGN_UP", "Registrarse"), ("CALL", "Llamar")]
VISIBILIDAD_LINKEDIN = [("PUBLIC", "Público"), ("CONNECTIONS", "Solo mis contactos"),
                        ("LOGGED_IN", "Usuarios de LinkedIn")]
VISIBILIDAD_MASTODON = [("public", "Pública"), ("unlisted", "No listada"),
                        ("private", "Solo seguidores")]


class ErrorRedes(ValueError):
    pass


def validar(k, v):
    if not isinstance(v, str):
        raise ErrorRedes(f"«{k}» es un texto")
    v = " ".join(v.split())
    if len(v) > 300:
        raise ErrorRedes(f"«{k}» pasa de 300 caracteres")
    if k in ("pinterest_enlace", "gbp_cta_url") and v and not re.match(r"^https?://\S{3,}$", v):
        raise ErrorRedes(f"«{k}» tiene que ser un enlace que empiece por https://")
    if k in ("pinterest_tablero", "linkedin_pagina", "gbp_ubicacion") and v \
            and not re.fullmatch(r"[A-Za-z0-9_:\-/.]{2,120}", v):
        raise ErrorRedes(f"«{k}» es un identificador: letras, números, «_», «-», «:», «/» o «.»")
    if k == "gbp_cta" and v not in {c for c, _n in CTA_GBP}:
        raise ErrorRedes("ese botón de Google Business no existe")
    if k == "linkedin_visibilidad" and v not in {c for c, _n in VISIBILIDAD_LINKEDIN}:
        raise ErrorRedes("esa visibilidad de LinkedIn no existe")
    if k == "mastodon_visibilidad" and v not in {c for c, _n in VISIBILIDAD_MASTODON}:
        raise ErrorRedes("esa visibilidad de Mastodon no existe")
    if k == "threads_tema" and v and (len(v) > 50 or re.search(r"[.&]", v)):
        raise ErrorRedes("el tema de Threads va de 1 a 50 caracteres, sin puntos ni «&»")
    return v


def encaje(red, formato, duracion):
    """{tipo, nivel, texto} como `publicar.encaje`, para las redes nuevas."""
    d = float(duracion or 0)
    vertical = formato == "vertical"
    if red == "google_business":
        if d > 30:
            return {"tipo": "", "nivel": "error",
                    "texto": "Google Business no acepta vídeos de más de 30 segundos"}
        return {"tipo": "vídeo", "nivel": "ok", "texto": ""}
    if red == "bluesky":
        if d > 600:
            return {"tipo": "", "nivel": "error",
                    "texto": "Bluesky no acepta vídeos de más de 10 minutos"}
        return {"tipo": "vídeo", "nivel": "ok", "texto": ""}
    if red == "x" and d > 140:
        return {"tipo": "vídeo", "nivel": "aviso",
                "texto": "pasa de 2:20: X solo lo acepta en cuentas Premium"}
    if red == "threads" and d > 300:
        return {"tipo": "vídeo", "nivel": "aviso",
                "texto": "pasa de 5 minutos: Threads puede rechazarlo"}
    if red == "pinterest" and not vertical:
        return {"tipo": "pin de vídeo", "nivel": "aviso",
                "texto": "es horizontal: en Pinterest funcionan mejor los verticales"}
    if red == "pinterest":
        return {"tipo": "pin de vídeo", "nivel": "ok", "texto": ""}
    if red in ("discord", "telegram", "mastodon"):
        return {"tipo": "vídeo", "nivel": "ok",
                "texto": "el tamaño máximo lo pone el servidor o el canal: si es muy grande, lo rechazará"}
    return {"tipo": "vídeo", "nivel": "ok", "texto": ""}


def falta(red, ajustes):
    """Lo que falta en los ajustes del proyecto para poder enviar a esa red, o ""."""
    ajustes = ajustes or {}
    if red == "pinterest" and not ajustes.get("pinterest_tablero"):
        return ("Pinterest necesita el tablero donde va el pin (Cuentas y ajustes → "
                "Redes de este proyecto → Pinterest)")
    if red == "google_business" and ajustes.get("gbp_cta") not in ("", None, "CALL") \
            and not ajustes.get("gbp_cta_url"):
        return "el botón de Google Business necesita su enlace (Cuentas y ajustes)"
    return ""


def campos(red, texto, titulo, textos_red, ajustes, info, marcar_ia):
    """(campos, avisos) para Upload-Post de una red nueva."""
    textos_red = textos_red or {}
    ajustes = ajustes or {}
    c, avisos = {}, []
    alt = " ".join(str(textos_red.get("alt") or "").split())
    if red == "linkedin":
        if titulo:
            c["linkedin_title"] = titulo[:TITULOS["linkedin"]]
        c["linkedin_description"] = texto
        # con su prefijo: «visibility» a secas es el campo general de la subida
        # y van otras redes en ella (Upload-Post acepta los dos nombres)
        c["linkedin_visibility"] = ajustes.get("linkedin_visibilidad") or "PUBLIC"
        if ajustes.get("linkedin_pagina"):
            c["target_linkedin_page_id"] = ajustes["linkedin_pagina"]
    elif red == "x":
        c["x_title"] = texto
        if marcar_ia:
            c["made_with_ai"] = True
        if re.search(r"https?://", texto):
            avisos.append("X quita los enlaces del texto: no saldrán")
    elif red == "threads":
        c["threads_title"] = texto
        if ajustes.get("threads_tema"):
            c["threads_topic_tag"] = ajustes["threads_tema"]
        if len(texto.encode("utf-8")) > 500:
            avisos.append("Threads admite 500 bytes: con tildes y emojis caben menos letras")
    elif red == "pinterest":
        c["pinterest_title"] = (titulo or (info or {}).get("nombre") or "")[:TITULOS["pinterest"]]
        c["pinterest_description"] = texto
        if ajustes.get("pinterest_tablero"):
            c["pinterest_board_id"] = ajustes["pinterest_tablero"]
        if ajustes.get("pinterest_enlace"):
            c["pinterest_link"] = ajustes["pinterest_enlace"]
        if marcar_ia:
            c["pinterest_ai_disclosures"] = "AI_MODIFIED"
    elif red == "bluesky":
        c["bluesky_title"] = texto
        c["bluesky_langs"] = "es"
    elif red == "discord":
        c["discord_title"] = texto
        mp4 = (info or {}).get("mp4") or ""
        try:
            mb = os.path.getsize(mp4) / (1024 * 1024) if mp4 and os.path.isfile(mp4) else 0
        except OSError:
            mb = 0
        if mb > 20:
            # Upload-Post rechaza de fábrica lo que pase de 20 MiB: se sube el tope
            c["discord_max_file_mb"] = min(500, int(math.ceil(mb)) + 1)
            avisos.append(f"el vídeo pesa {mb:.0f} MB: el servidor de Discord tiene que aceptarlo")
    elif red == "telegram":
        c["telegram_title"] = texto
    elif red == "mastodon":
        c["mastodon_title"] = texto
        c["mastodon_visibility"] = ajustes.get("mastodon_visibilidad") or "public"
    elif red == "google_business":
        c["gbp_topic_type"] = "STANDARD"
        if ajustes.get("gbp_cta"):
            c["gbp_cta_type"] = ajustes["gbp_cta"]
            if ajustes.get("gbp_cta_url") and ajustes["gbp_cta"] != "CALL":
                c["gbp_cta_url"] = ajustes["gbp_cta_url"]
        if ajustes.get("gbp_ubicacion"):
            c["gbp_location_id"] = ajustes["gbp_ubicacion"]
    if alt and red in ALT:
        c[f"{red}_alt_text"] = alt[:ALT[red]]
    elif red in ALT and not alt:
        avisos.append("sin texto alternativo (lo que se ve en el vídeo, para quien no lo ve)")
    falta_algo = falta(red, ajustes)
    if falta_algo:
        avisos.append(falta_algo)
    return c, avisos

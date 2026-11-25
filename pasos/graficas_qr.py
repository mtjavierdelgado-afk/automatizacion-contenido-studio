"""El QR de Gráficas (rama graficas-3c-extras, 25-11-2026): tu WhatsApp o tu web
en un código QR para el cierre del carrusel (o cualquier lámina).

Se genera AQUÍ, en el servidor, con `segno` (Python puro, licencia BSD, fijado
en requirements.txt): no se llama a ningún servicio de fuera ni a ninguna IA, y
es gratis. El QR se guarda como una imagen más de Gráficas (`guardar_imagen`)
y en el editor es una capa de foto: se mueve y se escala como cualquier otra.

Negro sobre blanco y con su margen («zona tranquila») a propósito: con los
colores del Kit muchos móviles dejan de leerlo.
"""
import io
import re
from urllib.parse import quote, urlsplit

import graficas as G
from graficas import ErrorGraficas

TIPOS = ("whatsapp", "web")
#: Lo más largo que lleva un QR (la dirección ya codificada). Más largo, el QR
#: tiene tantos cuadritos que en una lámina vista en el móvil no se lee bien
#: (árbitro del 25-11: 323 letras daban 77 módulos de 3,6 px).
MAX_URL = 150
MAX_WEB = MAX_URL
MAX_MENSAJE = 80
#: Lado del PNG que se genera (antes de pasar a JPG): de sobra para 1080 px.
LADO = 1200


def destino(tipo, valor, mensaje=""):
    """-> el texto que lleva el QR (una dirección https). Lanza ErrorGraficas
    con una frase clara si el número o la web no valen."""
    valor = " ".join(str(valor or "").split())
    if tipo == "whatsapp":
        numero = re.sub(r"[\s+\-().]", "", valor)
        if not numero.isdigit():
            raise ErrorGraficas("el WhatsApp tiene que ser un número (con o sin +51)")
        if len(numero) == 9 and numero.startswith("9"):
            numero = "51" + numero          # un celular de Perú sin el código del país
        if not 8 <= len(numero) <= 15:
            raise ErrorGraficas("ese número no parece un WhatsApp: pon el código del país y el número (51 999 999 999)")
        url = f"https://wa.me/{numero}"
        mensaje = " ".join(str(mensaje or "").split())
        if len(mensaje) > MAX_MENSAJE:
            raise ErrorGraficas(f"el mensaje del QR es largo: con {MAX_MENSAJE} letras como mucho el código se lee bien en el móvil")
        if mensaje:
            url += "?text=" + quote(mensaje, safe="")
        if len(url) > MAX_URL:
            raise ErrorGraficas("el mensaje del QR es largo (los emojis y las tildes ocupan más): acórtalo para que se lea bien en el móvil")
        return url
    if tipo == "web":
        if not valor or " " in valor:
            raise ErrorGraficas("escribe la dirección de tu web, sin espacios (crearia.tech)")
        if not re.match(r"^https?://", valor, re.I):
            valor = "https://" + valor
        partes = urlsplit(valor)
        if partes.scheme.lower() not in ("http", "https") or "." not in partes.netloc:
            raise ErrorGraficas("esa dirección no parece una web (por ejemplo: crearia.tech)")
        if len(valor) > MAX_WEB:
            raise ErrorGraficas(f"esa dirección es larga para un QR (hasta {MAX_WEB} letras): usa la de tu página principal")
        return valor
    raise ErrorGraficas("el QR puede llevar tu WhatsApp o tu web")


def png(texto):
    """-> los bytes de un PNG con el QR de `texto` (negro sobre blanco, con su margen)."""
    try:
        import segno                                        # noqa: PLC0415
    except ImportError as fallo:
        raise ErrorGraficas("falta la librería de los QR (segno): «asvs actualizar» la instala") from fallo
    try:
        codigo = segno.make(texto, error="m", micro=False)
        ancho = codigo.symbol_size(border=4)[0]
        salida = io.BytesIO()
        codigo.save(salida, kind="png", scale=max(4, LADO // ancho), border=4, dark="#000000", light="#FFFFFF")
    except Exception as fallo:                              # noqa: BLE001
        # nunca un 500 con un texto técnico: lo que segno no cabe, se dice
        raise ErrorGraficas("no se ha podido hacer el QR con ese texto: acórtalo") from fallo
    return salida.getvalue()


def hacer(raiz, cid, tipo, valor, mensaje=""):
    """Genera el QR y lo guarda como imagen de Gráficas. -> {nombre, destino}"""
    url = destino(tipo, valor, mensaje)
    return {"nombre": G.guardar_imagen(raiz, cid, png(url)), "destino": url}

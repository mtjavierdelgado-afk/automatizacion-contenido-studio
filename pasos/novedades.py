"""Las NOVEDADES: `docs/NOVEDADES.md` mas lo que cada rama apunta en `docs/novedades/`.

QUE PROBLEMA RESUELVE (rama `ramas-sin-choques`, 05-11-2026)
------------------------------------------------------------
Cada rama apuntaba su entrada ARRIBA de `docs/NOVEDADES.md`, debajo del mismo
titulo de version. Dos ramas abiertas a la vez escribian en las MISMAS lineas,
y cada union era un choque que habia que resolver a mano sumando los dos lados.

Ahora cada rama escribe en SU fichero, `docs/novedades/<AAAA-MM-DD>-<rama>.md`,
con el mismo formato de siempre (un titulo en negrita y sus vinetas). Dos ramas
nunca tocan el mismo fichero, asi que ya no chocan. La pantalla
(Configuracion -> Novedades) y el asistente leen el texto JUNTO de `texto()`:
las entradas de la carpeta, de la mas nueva a la mas antigua, justo debajo del
primer titulo de version de NOVEDADES.md -- donde las habria puesto la rama a
mano --, y despues todo lo de siempre. Lo que se ve es identico.

Un fichero que empieza por un titulo de version («## V5.2 · …») abre una
version nueva: va ENCIMA del primer titulo de NOVEDADES.md, con lo suyo dentro.

Solo cuentan los ficheros con forma `AAAA-MM-DD-algo.md`; el resto de la
carpeta (su LEEME.md) no sale. Solo biblioteca estandar: app.py lo importa
suelto, como `ajustes`, para que un motor roto no deje las novedades en blanco.

PLEGAR (opcional): `herramientas/plegar_novedades.py` mete las entradas de la
carpeta en NOVEDADES.md y borra sus ficheros, con el MISMO texto resultante. Se
hace en `main` despues de unir, nunca en una rama (volveria a chocar).
"""
import os
import re

#: Donde viven, relativo a la raiz del Estudio.
FICHERO = os.path.join("docs", "NOVEDADES.md")
CARPETA = os.path.join("docs", "novedades")

_NOMBRE = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Za-z0-9_.-]+\.md$")
_VERSION = re.compile(r"^## ", re.M)


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _leer_trozo(ruta):
    """Un fichero de la carpeta, sin la marca BOM que pone el PowerShell 5
    (`Out-File -Encoding utf8`): con ella, un «## V…» no se veria como
    titulo de version y caeria dentro de la version de antes."""
    return _leer(ruta).lstrip("\ufeff").strip()


def fragmentos(raiz):
    """[(nombre, texto)] de la carpeta, del mas nuevo al mas antiguo.

    El orden es el del NOMBRE al reves: la fecha va delante, y dos del mismo dia
    salen en orden alfabetico inverso, siempre el mismo. Los vacios no cuentan.
    """
    carpeta = os.path.join(raiz, CARPETA)
    try:
        nombres = [n for n in os.listdir(carpeta) if _NOMBRE.match(n)]
    except OSError:
        return []
    salida = []
    for nombre in sorted(nombres, reverse=True):
        texto = _leer_trozo(os.path.join(carpeta, nombre))
        if texto:
            salida.append((nombre, texto))
    return salida


def _meter(base, trozo):
    """Mete UN trozo en `base`: un «## V…» abre version encima de la primera;
    una entrada suelta va debajo del primer titulo de version (la mas nueva)."""
    trozo = trozo.strip("\n")
    m = _VERSION.search(base)
    if not base.strip():
        return trozo + "\n"
    if not m:
        # sin ningun titulo de version: detras de todo, como un bloque mas
        return base.rstrip("\n") + "\n\n" + trozo + "\n"
    antes, desde = base[:m.start()], base[m.start():]
    if trozo.startswith("## "):
        return antes + trozo + "\n\n" + desde
    fin_titulo = desde.find("\n")
    if fin_titulo < 0:
        titulo, resto = desde, ""
    else:
        titulo, resto = desde[:fin_titulo], desde[fin_titulo + 1:].lstrip("\n")
    return antes + titulo + "\n\n" + trozo + "\n\n" + resto


def juntar(base, trozos):
    """El texto de NOVEDADES.md `base` con los `trozos` (del mas nuevo al mas
    antiguo, como los da `fragmentos`) metidos en su sitio.

    Se meten DEL MAS ANTIGUO AL MAS NUEVO, cada uno arriba del todo de la
    version mas nueva que haya en ese momento: asi una entrada fechada despues
    de un «## V5.2» suelto cae dentro de la 5.2, y una de antes, en la 5.1.
    """
    if not trozos:
        return base
    for trozo in reversed(list(trozos)):
        base = _meter(base, trozo)
    return base


def texto(raiz):
    """Las novedades enteras, como las ve la pantalla y las lee el asistente."""
    base = _leer(os.path.join(raiz, FICHERO))
    return juntar(base, [t for _n, t in fragmentos(raiz)])


def plegar(raiz):
    """Mete la carpeta en NOVEDADES.md y borra sus ficheros. -> [nombres plegados]

    El texto de `texto()` es el mismo antes y despues: se escribe primero
    NOVEDADES.md (entero, por un temporal) y solo entonces se borran los
    ficheros, para que un fallo a medias nunca deje una entrada fuera.
    """
    trozos = fragmentos(raiz)
    if not trozos:
        return []
    junto = texto(raiz)
    destino = os.path.join(raiz, FICHERO)
    temporal = destino + ".plegando"
    with open(temporal, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(junto)
    os.replace(temporal, destino)
    carpeta = os.path.join(raiz, CARPETA)
    for nombre, _t in trozos:
        os.remove(os.path.join(carpeta, nombre))
    return [n for n, _t in trozos]

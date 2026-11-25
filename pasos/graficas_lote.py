"""Carruseles en lote (rama graficas-3c-extras, 25-11-2026).

Muchos carruseles de una vez, sin IA y gratis: cada uno sale de un texto con el
mismo formato que «Partir un texto en láminas» (un párrafo, una lámina) y se
guarda como una pieza nueva de Gráficas, que luego se abre y se retoca.

Se aceptan dos formas de escribirlos:

1. **Una lista**: los carruseles separados por una línea con solo `---`. Cada
   uno puede empezar por una línea «Familia: Gamer» (o «Familia: 16»); si no,
   va con la familia elegida en la pantalla.

2. **Un CSV** (de Excel o Google Sheets, con comas o con punto y coma), con una
   fila de títulos: «familia» (opcional), «titular» y después una columna por
   lámina. En cada celda, «Titular | frase» pone la frase debajo del titular.
   Cada fila es un carrusel.

Como mucho `MAX_CARRUSELES` por tanda: cada uno se pinta lámina a lámina.
"""
import csv
import io
import re
import unicodedata

import graficas_capas as C
import graficas_carrusel as K
from graficas import ErrorGraficas

MAX_CARRUSELES = 20
MAX_TEXTO = 60000
_RE_SEPARADOR = re.compile(r"^\s*-{3,}\s*$", re.M)
_RE_FAMILIA = re.compile(r"^\s*familia\s*:\s*(.+?)\s*$", re.I)


def _sin_tildes(texto):
    return "".join(ch for ch in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(ch) != "Mn").strip()


def _familia(valor, donde):
    """«Gamer», «gamer», «16» -> 16. Lanza con el sitio donde está si no existe."""
    valor = str(valor or "").strip()
    if not valor:
        return None
    if valor.isdigit() and int(valor) in K.FAMILIAS:
        return int(valor)
    nombres = {_sin_tildes(f["nombre"]): f["n"] for f in K.catalogo()["familias"]}
    if _sin_tildes(valor) in nombres:
        return nombres[_sin_tildes(valor)]
    raise ErrorGraficas(f"{donde}: la familia «{valor[:40]}» no existe (usa su nombre o su número, del 1 al {max(K.FAMILIAS)})")


def _primera(texto):
    return next((linea for linea in texto.splitlines() if linea.strip()), "")


def _separador(primera):
    """El de la fila de títulos (no el de todo el texto: las frases llevan comas)."""
    if "\t" in primera:
        return "\t"
    return max((",", ";"), key=primera.count)


def _es_csv(texto):
    """Un CSV si su primera línea es una fila de TÍTULOS: «titular» (o
    «portada») como celda, y celdas cortas. «Portada, lo que nadie te cuenta»
    es el titular de una lista, no una cabecera."""
    primera = _primera(texto)
    if not re.search(r"[,;\t]", primera):
        return False
    celdas = [_sin_tildes(c).strip().strip('"') for c in primera.split(_separador(primera))]
    return (len(celdas) >= 2 and any(c in ("titular", "portada", "familia") for c in celdas)
            and all(len(c) <= 25 and len(c.split()) <= 3 for c in celdas))


def _desde_csv(texto):
    separador = _separador(_primera(texto))
    filas = [f for f in csv.reader(io.StringIO(texto), delimiter=separador) if any(c.strip() for c in f)]
    cabecera = [_sin_tildes(c) for c in filas[0]]
    col_familia = cabecera.index("familia") if "familia" in cabecera else None
    col_titular = next((cabecera.index(k) for k in ("titular", "portada") if k in cabecera), None)
    if col_titular is None:
        raise ErrorGraficas("al CSV le falta la columna «titular» (la portada de cada carrusel)")
    entradas = []
    for i, fila in enumerate(filas[1:], 2):
        celdas = [c.strip() for c in fila]
        titular = celdas[col_titular] if col_titular < len(celdas) else ""
        if not titular:
            raise ErrorGraficas(f"fila {i} del CSV: falta el titular")
        laminas = [c for j, c in enumerate(celdas) if j not in (col_familia, col_titular) and c]
        parrafos = [titular] + [re.sub(r"\s*\|\s*", "\n", c) for c in laminas]
        familia = _familia(celdas[col_familia], f"fila {i} del CSV") if col_familia is not None and col_familia < len(celdas) else None
        entradas.append({"familia": familia, "texto": "\n\n".join(parrafos), "nombre": titular[:80]})
    return entradas


def _desde_lista(texto):
    entradas = []
    for i, bloque in enumerate((b.strip() for b in _RE_SEPARADOR.split(texto)), 1):
        if not bloque:
            continue
        lineas = bloque.splitlines()
        familia = None
        m = _RE_FAMILIA.match(lineas[0])
        if m:
            familia = _familia(m.group(1), f"carrusel {i}")
            bloque = "\n".join(lineas[1:]).strip()
        if not bloque:
            continue
        titular = bloque.splitlines()[0].strip()
        entradas.append({"familia": familia, "texto": bloque, "nombre": titular[:80]})
    return entradas


def leer(texto):
    """-> [{familia (o None: la elegida), texto, nombre}]. Lanza ErrorGraficas
    con una frase clara si no hay ninguno, son demasiados o algo no vale."""
    texto = str(texto or "").replace("\r\n", "\n")
    if len(texto) > MAX_TEXTO:
        raise ErrorGraficas(f"es demasiado texto para una tanda (hasta {MAX_TEXTO // 1000} 000 letras): pártelo en dos")
    entradas = _desde_csv(texto) if _es_csv(texto) else _desde_lista(texto)
    if not entradas:
        raise ErrorGraficas("no hay ningún carrusel: escribe uno por bloque, separados por una línea con ---")
    if len(entradas) > MAX_CARRUSELES:
        raise ErrorGraficas(f"son {len(entradas)} carruseles y caben {MAX_CARRUSELES} por tanda: pártelos en dos")
    return entradas


def hacer(raiz, cid, entradas, familia_defecto, formato, con_turno, kit=None, logo=None, logo_oscuro=None, marca="",
          avisar=None, hechos=None):
    """Monta y guarda cada carrusel como pieza nueva. `con_turno(fn)` presta el
    navegador (G._con_turno: uno a la vez, como todo Gráficas). `avisar(hechos,
    total)`. -> [{id, nombre, laminas, avisos}]. Un fallo a mitad para la tanda
    y lo hecho se queda guardado (la pantalla dice cuántos salieron)."""
    K.familia(familia_defecto)
    hechos = [] if hechos is None else hechos
    for i, e in enumerate(entradas):
        n = e["familia"] or familia_defecto
        base = {"version": 2, "formato": formato, "nombre": e["nombre"], "laminas": [{"capas": []}]}
        doc, avisos = con_turno(lambda p, base=base, n=n, e=e: K.carrusel_desde_texto(
            p, base, n, e["texto"], "sustituir", kit, logo, logo_oscuro, marca))
        doc["nombre"] = e["nombre"]
        r = C.guardar(raiz, cid, doc, None, logo, logo_oscuro)
        hechos.append({"id": r["id"], "nombre": e["nombre"],
                       "laminas": len(doc["laminas"]), "avisos": avisos})
        if avisar:
            avisar(i + 1, len(entradas))
    return hechos

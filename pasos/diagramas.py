"""
Diagramas por contenido (rama diagramas-por-contenido, 28-10-2026).

Un ajuste, «Diagramas», que dice CUANTO se explica dibujando en un video:

    ninguna          ningun diagrama, ni por sorteo
    solo_si_lo_pide  solo donde el propio guion pide ensenar algo
    equilibrada      donde la voz explica algo; como mucho 1 de cada 8 planos
    didactica        un video para ensenar; como mucho 1 de cada 4 planos

Se guarda en el estilo (`estilo.diagramas`) y, por video, en los params de
assets (`diagramas`), que manda. SIN AJUSTE GUARDADO NO CAMBIA NADA: el
catalogo, las cartas, los prompts y las firmas salen byte a byte como antes
(regla 1). Por eso todo lo de aqui empieza preguntando `activo(modo)`.

Con el ajuste puesto pasan tres cosas:

1. El catalogo marca los TRAMOS QUE EXPLICAN (`explicativos`: medida, proceso,
   comparacion, porcentaje, paso a paso). Ver `tramo_criterio` y
   `limpiar_explicativos`.
2. El catalogo puede proponer GRAFICOS con cifras (componente `grafico` con
   `config.clase`), que se dibujan por codigo (`motores/capa_vectorial/
   grafico.py`), gratis, y SOLO si cada cifra esta escrita en el guion: un
   grafico con una cifra inventada es peor que no tener grafico. Ver
   `limpiar_grafico`.
3. En ilustracion, la carta «diagrama» deja de salir por sorteo y sale en los
   tramos que explican (ver `cartas_de_diagrama`). Las demas cartas del sorteo
   no se mueven: `encuadres.carta_de(..., excluir=...)` quita la carta DESPUES
   de barajar, no del mazo.

Este modulo no importa nada del Estudio: lo usan el catalogo, p6 y app.py, y
su prueba (`prueba_diagramas.py`) corre sin dependencias.
"""
import math
import re
import unicodedata

MODOS = ("ninguna", "solo_si_lo_pide", "equilibrada", "didactica")

NOMBRES = {
    "ninguna": "Ninguno",
    "solo_si_lo_pide": "Solo si el guion lo pide",
    "equilibrada": "Equilibrado",
    "didactica": "Didáctico",
}

DESCRIPCIONES = {
    "ninguna": "Ningún diagrama, ni siquiera por sorteo.",
    "solo_si_lo_pide": "Solo donde el propio guion dice que enseña algo "
                       "(«fíjate en este gráfico», «paso a paso»).",
    "equilibrada": "Donde la voz explica algo (una medida, un proceso, una "
                   "comparación). Como mucho 1 de cada 8 planos.",
    "didactica": "Para vídeos que enseñan: todos los tramos que explican. "
                 "Como mucho 1 de cada 4 planos.",
}

#: Que clase de explicacion es un tramo. Cerrada: es lo que lee la pantalla.
CLASES = ("medida", "proceso", "comparacion", "porcentaje", "paso_a_paso")

#: Que graficos sabe dibujar `grafico.py`, con cuantos datos cada uno.
CLASES_GRAFICO = {
    "barras": (2, 6),
    "comparacion": (2, 2),
    "proporcion": (1, 1),
    "antes_despues": (2, 2),
}

#: 1 de cada N planos como mucho acaba en diagrama. `solo_si_lo_pide` lleva el
#: mismo tope que la didactica: lo pide el guion, pero un video entero de
#: diagramas tampoco lo es.
UNO_DE_CADA = {"solo_si_lo_pide": 4, "equilibrada": 8, "didactica": 4}

#: Cuantos graficos con cifras como mucho en un video.
MAX_GRAFICOS = {"solo_si_lo_pide": 2, "equilibrada": 3, "didactica": 5}

#: Cuantos planos de un mismo tramo explicativo se vuelven diagrama.
POR_TRAMO = {"solo_si_lo_pide": 1, "equilibrada": 1, "didactica": 2}

#: La carta que se reparte por contenido y no por sorteo.
CARTA = "diagrama"


# ------------------------------------------------------------------ el ajuste
def _llano(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


_ALIAS = {
    "": "", "automatico": "", "auto": "", "por defecto": "",
    "ninguna": "ninguna", "ninguno": "ninguna", "nada": "ninguna", "no": "ninguna",
    "solo_si_lo_pide": "solo_si_lo_pide", "solo si lo pide": "solo_si_lo_pide",
    "solo si el guion lo pide": "solo_si_lo_pide",
    "equilibrada": "equilibrada", "equilibrado": "equilibrada",
    "didactica": "didactica", "didactico": "didactica",
}


def normalizar(valor):
    """El ajuste tal y como se guarda. -> "" (sin ajuste) o uno de MODOS.

    "" es NO TENERLO, que es distinto de "ninguna": sin ajuste todo sale como
    antes; con "ninguna" se quita tambien el diagrama del sorteo.
    """
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ValueError("un texto: " + ", ".join(MODOS))
    clave = _llano(valor).replace("-", " ")
    if clave in _ALIAS:
        return _ALIAS[clave]
    clave = clave.replace(" ", "_")
    if clave in MODOS:
        return clave
    raise ValueError("no es un ajuste de diagramas: " + ", ".join(MODOS))


def activo(modo):
    return modo in MODOS


def admite_graficos(modo):
    return modo in MAX_GRAFICOS


def modo_de(params):
    """El ajuste de ESTE video: el del video manda, y si no, el del estilo.

    Lee sin escribir (regla 1) y sin lanzar: un valor raro guardado a mano se
    lee como sin ajuste, que es lo que salia antes de existir esto.
    """
    params = params or {}
    for crudo in (params.get("diagramas"),
                  (params.get("estilo") or {}).get("diagramas")):
        try:
            modo = normalizar(crudo)
        except ValueError:
            modo = ""
        if modo:
            return modo
    return ""


def opciones():
    """Lo que enseña el selector, en orden."""
    return [{"id": m, "nombre": NOMBRES[m], "descripcion": DESCRIPCIONES[m]}
            for m in MODOS]


# ---------------------------------------------------------- lo que lee Claude
_TRAMO_COMUN = """
DIAGRAMAS — que se explica dibujando ({nombre})
{que_marcar}

Anade al JSON un campo "explicativos" (vacio si no hay ninguno):
  "explicativos": [
    {{"desde": "<id de bloque>", "hasta": "<id de bloque>",
      "clase": "medida|proceso|comparacion|porcentaje|paso_a_paso",
      "que": "<que hay que ensenar dibujado, en ingles y en una frase>"}}
  ]
  - Un tramo explica cuando lo que dice se entiende MEJOR dibujado que
    contado: una medida, un proceso, una comparacion, un porcentaje o un paso a
    paso. Nombrar un numero de pasada no es explicar.
  - 'desde' y 'hasta' son ids de bloque del guion, como en los beats.

GRAFICOS CON CIFRAS — cuando el tramo da cifras que se comparan
Se dibujan por codigo, exactos, y van en "componentes" junto a los mapas:
    "<id: 'grafico_precios'>": {{
      "tipo": "grafico",
      "palabras": ["<palabras del guion que piden este grafico: la cifra y de que es>"],
      "config": {{
        "clase": "barras|comparacion|proporcion|antes_despues",
        "titulo": "<ROTULO CORTO, en el idioma del guion>",
        "unidad": "<%, m, kg, S/... o vacio>",
        "datos": [{{"etiqueta": "<ROTULO>", "valor": <numero>,
                   "cita": "<el trozo LITERAL del guion donde sale esa cifra>"}}]
      }}
    }}
  - CADA CIFRA TIENE QUE ESTAR ESCRITA EN EL GUION: copia en 'cita' el trozo
    tal cual (cinco a quince palabras). Un grafico con una cifra que no esta en
    el guion se descarta entero. No calcules ni redondees cifras nuevas.
  - barras: de 2 a 6 datos. comparacion: 2. proporcion: 1, un porcentaje de 0
    a 100. antes_despues: 2, el primero es el antes.
  - Como mucho {maximo} graficos en el video. Si no hay cifras que comparar, ninguno.
"""

_QUE_MARCAR = {
    "solo_si_lo_pide":
        "Este video solo lleva diagramas donde EL PROPIO GUION pide ensenar algo\n"
        "(«como ves en este grafico», «fijate en el esquema», «paso a paso»).\n"
        "Si el guion no lo pide, deja 'explicativos' vacio y no pongas graficos.",
    "equilibrada":
        "Marca los tramos que explican de verdad. Como mucho uno de cada ocho\n"
        "planos acabara siendo un diagrama: elige los que mas lo necesitan.",
    "didactica":
        "Es un video para ensenar: marca todos los tramos que explican. Como\n"
        "mucho uno de cada cuatro planos sera un diagrama.",
}


def tramo_criterio(modo):
    """El trozo del criterio que se anade al catalogo. "" sin ajuste o con
    «ninguna»: entonces el criterio sale como siempre, byte a byte."""
    if modo not in _QUE_MARCAR:
        return ""
    return _TRAMO_COMUN.format(nombre=NOMBRES[modo].lower(),
                               que_marcar=_QUE_MARCAR[modo],
                               maximo=MAX_GRAFICOS[modo])


#: Donde va el tramo: justo despues de COMPONENTES, que es donde estan los
#: mapas, y antes de LUGARES.
ANCLA = "\nLUGARES — el rotulo que situa"


def con_tramo(criterio, modo):
    """El criterio con el tramo de diagramas. Sin ajuste, el MISMO texto."""
    tramo = tramo_criterio(modo)
    if not tramo:
        return criterio
    if ANCLA in criterio:
        i = criterio.index(ANCLA)
        return criterio[:i].rstrip("\n") + "\n" + tramo + criterio[i:]
    return criterio.rstrip("\n") + "\n" + tramo


# -------------------------------------------------- lo que devuelve, limpio
def limpiar_explicativos(crudos, ids_bloque, avisos, modo):
    """Los tramos que explican, validados. -> lista (vacia sin ajuste)

    Cada uno con sus bloques expandidos ('bloques'), que es lo que mira p6: un
    plano esta en un tramo explicativo si su bloque de origen esta ahi.
    """
    if not activo(modo) or modo == "ninguna":
        return []
    orden = {bid: i for i, bid in enumerate(ids_bloque)}
    limpios = []
    for ficha in crudos if isinstance(crudos, list) else []:
        if not isinstance(ficha, dict):
            continue
        desde = str(ficha.get("desde") or "").strip().upper()
        hasta = str(ficha.get("hasta") or desde).strip().upper()
        if desde not in orden:
            avisos.append(f"tramo explicativo descartado: el bloque "
                          f"{desde or '(vacio)'} no existe")
            continue
        if hasta not in orden:
            hasta = desde
        if orden[hasta] < orden[desde]:
            desde, hasta = hasta, desde
        clase = _llano(ficha.get("clase")).replace(" ", "_")
        if clase not in CLASES:
            clase = "proceso"
        limpios.append({
            "desde": desde, "hasta": hasta, "clase": clase,
            "que": " ".join(str(ficha.get("que") or "").split())[:300],
            "bloques": list(ids_bloque[orden[desde]:orden[hasta] + 1]),
        })
    limpios.sort(key=lambda t: orden[t["desde"]])
    return limpios


# ---- las cifras: que esten en el guion
_UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21,
    "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
    "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
    "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
    "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
    "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
    "medio": 0.5, "media": 0.5,
}
_MULTIPLOS = {"mil": 1000, "millon": 10 ** 6, "millones": 10 ** 6}


def _numeros_en_letras(palabras):
    """Los numeros escritos con letras («treinta y cinco», «dos mil»)."""
    hallados, total, actual, hay = [], 0, 0, False

    def cerrar():
        nonlocal total, actual, hay
        if hay:
            hallados.append(total + actual)
        total, actual, hay = 0, 0, False

    for palabra in palabras:
        if palabra in _UNIDADES:
            actual += _UNIDADES[palabra]
            hay = True
        elif palabra in _MULTIPLOS:
            actual = (actual or 1) * _MULTIPLOS[palabra]
            total, actual, hay = total + actual, 0, True
        elif palabra == "y" and hay:
            continue
        else:
            cerrar()
    cerrar()
    return hallados


_DIGITOS = re.compile(r"\d+(?:[.,\s]\d+)*")


def _numeros_en_cifras(texto):
    """Los numeros con digitos. «1.500» y «1,500» dan 1500 y tambien 1.5:
    se aceptan las dos lecturas, porque el guion mezcla las dos costumbres."""
    hallados = [float(n) for n in re.findall(r"\d+", texto)]
    for trozo in _DIGITOS.findall(texto):
        limpio = trozo.replace(" ", "")
        hallados.append(float(re.sub(r"[.,]", "", limpio)))
        for sep in (",", "."):
            if limpio.count(sep) == 1:
                otro = "." if sep == "," else ","
                try:
                    hallados.append(float(limpio.replace(otro, "").replace(sep, ".")))
                except ValueError:
                    pass
    return hallados


def numeros_de(texto):
    llano = _llano(texto)
    palabras = re.findall(r"[a-z]+", llano)
    return _numeros_en_cifras(llano) + [float(n) for n in _numeros_en_letras(palabras)]


def para_buscar(texto):
    """El texto para buscar una cita dentro: sin tildes ni mayusculas y sin
    signos, salvo el punto y la coma entre digitos («1.500», «2,5») y el %."""
    llano = _llano(texto)
    llano = re.sub(r"(?<!\d)[.,]|[.,](?!\d)", " ", llano)
    llano = re.sub(r"[^a-z0-9%.,]+", " ", llano)
    return " " + " ".join(llano.split()) + " "


def cifra_en_guion(valor, cita, guion_buscable):
    """Si la cifra esta escrita en el guion: la cita esta tal cual y la cifra
    sale en la cita (con digitos o con letras). 'guion_buscable' es el guion
    pasado por `para_buscar`."""
    cita_llana = para_buscar(cita)
    if len(cita_llana.strip()) < 3 or cita_llana not in guion_buscable:
        return False
    return any(math.isclose(valor, n, rel_tol=1e-9, abs_tol=1e-9)
               for n in numeros_de(cita))


def _rotulo(crudo, maximo):
    texto = " ".join(str(crudo or "").split())
    return texto[:maximo].strip()


def limpiar_grafico(nombre, ficha, guion, avisos):
    """Un grafico con cifras, validado contra el guion. -> dict o None

    Aqui NO se degrada: o cada cifra esta en el guion, o el grafico entero
    fuera. Un grafico con una barra menos cuenta otra cosa.
    """
    config = ficha.get("config") if isinstance(ficha.get("config"), dict) else {}
    clase = _llano(config.get("clase")).replace(" ", "_")
    if clase not in CLASES_GRAFICO:
        avisos.append(f"grafico '{nombre}': la clase '{clase or '(vacia)'}' no se "
                      f"sabe dibujar ({', '.join(CLASES_GRAFICO)}), se descarta")
        return None
    minimo, maximo = CLASES_GRAFICO[clase]
    crudos = config.get("datos") if isinstance(config.get("datos"), list) else []
    guion_llano = para_buscar(guion)
    datos = []
    for crudo in crudos:
        if not isinstance(crudo, dict):
            continue
        valor = crudo.get("valor")
        if isinstance(valor, str):
            try:
                valor = float(valor.replace(",", "."))
            except ValueError:
                valor = None
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) \
                or not math.isfinite(valor):
            avisos.append(f"grafico '{nombre}': un dato sin numero, se descarta "
                          f"el grafico")
            return None
        cita = str(crudo.get("cita") or "")
        if not cifra_en_guion(float(valor), cita, guion_llano):
            avisos.append(f"grafico '{nombre}': la cifra {valor:g} no esta escrita "
                          f"en el guion, se descarta el grafico")
            return None
        datos.append({"etiqueta": _rotulo(crudo.get("etiqueta"), 28) or f"{valor:g}",
                      "valor": float(valor), "cita": " ".join(cita.split())})
    if not (minimo <= len(datos) <= maximo):
        avisos.append(f"grafico '{nombre}': {clase} lleva "
                      f"{minimo if minimo == maximo else f'de {minimo} a {maximo}'} "
                      f"dato(s) y trae {len(datos)}, se descarta")
        return None
    if clase == "proporcion" and not (0 <= datos[0]["valor"] <= 100):
        avisos.append(f"grafico '{nombre}': una proporcion va de 0 a 100, se descarta")
        return None
    if any(d["valor"] < 0 for d in datos) and clase in ("barras", "comparacion"):
        avisos.append(f"grafico '{nombre}': barras con cifras negativas, se descarta")
        return None
    palabras = [str(p).strip() for p in (ficha.get("palabras") or []) if str(p).strip()]
    return {
        "tipo": "grafico",
        "palabras": palabras or [nombre.replace("_", " ")],
        "config": {"clase": clase,
                   "titulo": _rotulo(config.get("titulo"), 48),
                   "unidad": _rotulo(config.get("unidad"), 8),
                   "datos": datos},
        "descripcion": str(ficha.get("descripcion") or "").strip(),
    }


def es_grafico_con_cifras(ficha):
    """Si un componente es de los que dibuja `grafico.py` (y no `mapa.py`)."""
    return (isinstance(ficha, dict) and ficha.get("tipo") == "grafico"
            and bool((ficha.get("config") or {}).get("clase")))


def recortar_graficos(componentes, modo, avisos):
    """Como mucho MAX_GRAFICOS graficos con cifras; los mapas, intactos."""
    tope = MAX_GRAFICOS.get(modo, 0)
    vistos, salida = 0, {}
    for nombre, ficha in componentes.items():
        if es_grafico_con_cifras(ficha):
            vistos += 1
            if vistos > tope:
                avisos.append(f"grafico '{nombre}': ya hay {tope} en el video, "
                              f"se descarta")
                continue
        salida[nombre] = ficha
    return salida


def planos_de_graficos(escenas, componentes, modo):
    """En que plano va cada grafico con cifras. -> {sid: nombre del grafico}

    En el plano cuya voz dice MAS cifras del grafico (la cita, o el numero
    escrito con digitos o con letras); a igualdad, el primero. Uno por grafico
    y un grafico por plano. Va por la voz del plano y no por las palabras ni
    por el tramo: el tramo casi siempre trae su sitio, y con sitio un
    componente no ganaba nunca. Sin ajuste que admita graficos, {}.
    """
    if not admite_graficos(modo):
        return {}
    graficos = [(n, c) for n, c in sorted((componentes or {}).items())
                if es_grafico_con_cifras(c)]
    if not graficos:
        return {}
    voces = []
    for escena in escenas or []:
        if not escena.get("id") or escena.get("cartela") or escena.get("sigue_a"):
            voces.append(None)
            continue
        texto = escena.get("narracion") or ""
        voces.append((para_buscar(texto), numeros_de(texto)))
    elegidos = {}
    for nombre, ficha in graficos:
        mejor, punto = None, 0
        for escena, voz in zip(escenas or [], voces):
            if voz is None or escena["id"] in elegidos:
                continue
            buscable, numeros = voz
            valor = 0
            for dato in (ficha.get("config") or {}).get("datos") or []:
                cita = para_buscar(dato.get("cita") or "")
                if cita.strip() and cita in buscable:
                    valor += 2
                elif any(math.isclose(float(dato.get("valor") or 0), n, abs_tol=1e-9)
                         for n in numeros):
                    valor += 1
            if valor > punto:
                mejor, punto = escena["id"], valor
        if mejor:
            elegidos[mejor] = nombre
    return elegidos


# ---------------------------------------------------------------- las cartas
def tope_de(modo, planos):
    """Cuantos planos como mucho acaban en diagrama."""
    cada = UNO_DE_CADA.get(modo)
    if not cada or planos <= 0:
        return 0
    return max(1, math.ceil(planos / cada))


def _repartidos(lista, cuantos):
    """`cuantos` elementos de `lista`, repartidos a lo largo (no los primeros)."""
    if cuantos >= len(lista):
        return list(lista)
    if cuantos <= 0:
        return []
    paso = len(lista) / cuantos
    return [lista[int(i * paso)] for i in range(cuantos)]


def cartas_de_diagrama(escenas, explicativos, modo, forzadas=None):
    """Que planos llevan la carta «diagrama» por contenido. -> {sid: "diagrama"}

    Solo los de un tramo que explica, como mucho POR_TRAMO por tramo y
    `tope_de` en el video. No se tocan los planos que ya traen carta forzada a
    mano (una decision mirando manda), ni los que no se dibujan (cartela,
    componente, segunda mitad de un plano largo), ni los que siguen una linea
    del guion visual con camara: ahi la linea decide.
    """
    if not activo(modo) or modo == "ninguna" or not explicativos:
        return {}
    forzadas = forzadas or {}
    por_bloque = {}
    for indice, tramo in enumerate(explicativos):
        for bid in tramo.get("bloques") or []:
            por_bloque.setdefault(bid, indice)
    planos_por_tramo = {}
    dibujables = 0
    for escena in escenas or []:
        sid = escena.get("id")
        if not sid:
            continue
        if escena.get("cartela") or escena.get("sigue_a") or escena.get("componente"):
            continue
        dibujables += 1
        if forzadas.get(sid) or (escena.get("linea_gv") or {}).get("camara"):
            continue
        bid = str((escena.get("origen") or {}).get("bloque") or "")
        if bid in por_bloque:
            planos_por_tramo.setdefault(por_bloque[bid], []).append(sid)
    candidatos = []
    for indice in sorted(planos_por_tramo):
        candidatos.extend(_repartidos(planos_por_tramo[indice], POR_TRAMO[modo]))
    elegidos = _repartidos(candidatos, tope_de(modo, dibujables))
    return {sid: CARTA for sid in elegidos}


def excluir_del_sorteo(modo):
    """Que cartas no salen por sorteo con este ajuste. () sin ajuste."""
    if not activo(modo):
        return ()
    return (CARTA,)

"""QUITAR UNA IMAGEN Y PASAR SU VOZ AL VECINO (rama unir-planos, 25-10-2026).

QUÉ ES
------
Pedido del dueño: en un vídeo hecho, dos imágenes seguidas no casan (S001 no
tiene que ver con S002) y la solución más rápida es QUITAR una y que lo que se
oye en ella pase a la de al lado. Sin pagar nada: la imagen que se queda
conserva su dibujo, y la voz no se toca (es una sola pista).

    leer(raiz) -> [{"texto", "hacia", "id"}]
    quitar(raiz, escena, hacia) / devolver(raiz, texto)
    aplicar(escenas, raiz, clave) -> {"absorbidos": [ids], "en": {id_hogar: [...]}}

CÓMO SE GUARDA, Y POR QUÉ NO ES UN PARAM
----------------------------------------
Lo quitado va a `<proyecto>/planos_quitados.json`, FUERA de params. Es una
CORRECCIÓN DEL CORTE, no una entrada de las imágenes, y por eso no puede vivir
donde vive todo lo demás:

  - en los params globales de assets movería la firma de TODOS los planos: la
    pantalla ofrecería «Regenerar lo obsoleto (11)» por haber quitado uno;
  - en la unidad del plano quitado se perdería: al retirarlo, el núcleo borra
    los params de esa unidad (`retirar_unidades`) y en la pasada siguiente
    volvería a salir;
  - en la unidad del que se queda movería SU firma, y su imagen ya pagada
    saldría obsoleta.

Quien lo aplica es `p6_assets.planificar`, siempre: cualquier pasada (la
tanda, el corte de las cartelas, la previsualización) lee el mismo fichero. La
pasada que se lanza al quitar no dibuja nada y deja una versión nueva de
assets; detrás quedan obsoletos los rótulos y el montaje, que son gratis.

Cada entrada se reconoce por EL TEXTO del plano quitado, no por su número: los
números son posiciones y se reparten de nuevo al regrabar la voz. Si el texto
deja de existir (se reescribió esa frase), la entrada no casa con nada y el
plano vuelve a salir: no se quita a ciegas lo que dice otra cosa.

CÓMO SE JUNTAN
--------------
El plano que se queda (el «hogar») se alarga para cubrir los dos: su
narración y sus marcas de palabra llevan las dos frases, en orden, y por eso
los subtítulos y el ritmo siguen a la voz. Pero su DIBUJO es el mismo: se
junta DESPUÉS de escribir su prompt, y su `narracion_imagen` guarda la frase
para la que se dibujó, que es con la que `p6_assets._texto_clave` lo sigue
reconociendo (su PNG no se mueve ni sale «obsoleto»).
"""
import json
import os
import tempfile
import threading

FICHERO = "planos_quitados.json"
HACIA = ("anterior", "siguiente")

_LOCK = threading.Lock()


def ruta(raiz):
    return os.path.join(raiz, FICHERO)


def leer(raiz):
    """Las entradas guardadas (las rotas o raras se ignoran)."""
    try:
        with open(ruta(raiz), encoding="utf-8") as fh:
            datos = json.load(fh)
    except (OSError, ValueError):
        return []
    salida = []
    for entrada in (datos or {}).get("quitados") or [] if isinstance(datos, dict) else []:
        if not isinstance(entrada, dict):
            continue
        texto = str(entrada.get("texto") or "").strip()
        hacia = str(entrada.get("hacia") or "")
        if texto and hacia in HACIA:
            try:
                n = max(0, int(entrada.get("n") or 0))
            except (TypeError, ValueError):
                n = 0
            limpia = {"texto": texto, "hacia": hacia, "id": str(entrada.get("id") or ""), "n": n}
            if isinstance(entrada.get("unidad"), dict):
                limpia["unidad"] = entrada["unidad"]
            if entrada.get("fresca"):
                limpia["fresca"] = True
            salida.append(limpia)
    return salida


def _escribir(raiz, entradas):
    os.makedirs(raiz, exist_ok=True)
    if not entradas:
        try:
            os.remove(ruta(raiz))
        except FileNotFoundError:
            pass
        return
    fd, temporal = tempfile.mkstemp(prefix=".quitados-", suffix=".json", dir=raiz)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"quitados": entradas}, fh, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta(raiz))
    except BaseException:
        try:
            os.remove(temporal)
        except OSError:
            pass
        raise


def quitar(raiz, texto, hacia, sid="", n=0, unidad=None, fresca=False):
    """Apunta que el plano que dice `texto` se quita y su voz va `hacia`.

    `n`: cuantos planos ANTES que el dicen exactamente lo mismo (una frase
    repetida son dos planos: se quita el que se pulso, no el primero).
    `unidad`: sus params por unidad (la direccion, la nota...), que el nucleo
    borra al retirarlo; se guardan aqui para devolverselos al deshacer."""
    if hacia not in HACIA:
        raise ValueError("«hacia» tiene que ser «anterior» o «siguiente»")
    texto = str(texto or "").strip()
    if not texto:
        raise ValueError("ese plano no dice nada: no se puede reconocer después")
    entrada = {"texto": texto, "hacia": hacia, "id": str(sid or ""), "n": max(0, int(n or 0))}
    if isinstance(unidad, dict) and unidad:
        entrada["unidad"] = unidad
    if fresca:
        entrada["fresca"] = True
    with _LOCK:
        entradas = [e for e in leer(raiz) if (e["texto"], e["n"]) != (texto, entrada["n"])]
        entradas.append(entrada)
        _escribir(raiz, entradas)
    return entradas


def devolver(raiz, texto, n=0):
    """Deshace: el plano que dice `texto` vuelve. -> la entrada que se quito
    (con su `unidad`, si la guardaba), o None si no estaba quitado."""
    texto = str(texto or "").strip()
    with _LOCK:
        entradas = leer(raiz)
        fuera = [e for e in entradas if (e["texto"], e["n"]) == (texto, int(n or 0))]
        if not fuera:
            return None
        _escribir(raiz, [e for e in entradas if e not in fuera])
    return fuera[0]


def restaurar(raiz, entrada):
    """Vuelve a apuntar una entrada tal cual (si lanzar la pasada falla)."""
    with _LOCK:
        entradas = [e for e in leer(raiz)
                    if (e["texto"], e["n"]) != (entrada["texto"], entrada["n"])]
        entradas.append(entrada)
        _escribir(raiz, entradas)


def reponer(raiz, entradas):
    """Deja el fichero exactamente con `entradas` (deshacer un intento fallido)."""
    with _LOCK:
        _escribir(raiz, list(entradas or []))


def ocurrencia(escenas, i, clave):
    """Cuantos planos antes de `i` dicen lo mismo que el plano `i`."""
    texto = clave(escenas[i])
    return sum(1 for e in escenas[:i] if clave(e) == texto)


def tiene_continuacion(escenas, i):
    """Si el plano siguiente es la segunda mitad de este (copia su imagen):
    quitar este dejaria su imagen en pantalla igualmente."""
    return (i + 1 < len(escenas)
            and escenas[i + 1].get("sigue_a") == escenas[i].get("id"))


def se_puede_quitar(escena, sin_imagen):
    """Si este plano admite quitarse: no las cartelas ni las continuaciones de
    un plano largo, ni los que abren un capítulo (su cabecera iría con él)."""
    if not escena or sin_imagen(escena) or escena.get("sigue_a") or escena.get("cartela"):
        return False
    if escena.get("capitulo_svg"):
        return False
    return not any((x or {}).get("tipo") == "capitulo"
                   for x in escena.get("capa_vectorial") or [] if isinstance(x, dict))


def puede_recibir(escena, sin_imagen):
    """Si este plano puede quedarse con la voz de un vecino: tiene que ser una
    imagen normal. Ni una cartela (su texto entra al ritmo de SUS palabras, y
    con las del vecino se descolocaría) ni una continuación de otro plano."""
    return (bool(escena) and not sin_imagen(escena) and not escena.get("sigue_a")
            and not escena.get("cartela"))


def _juntar(hogar, quitado, delante):
    """Pega `quitado` al `hogar`. `delante`: lo quitado iba ANTES del hogar."""
    hogar.setdefault("narracion_imagen", hogar.get("narracion") or "")
    textos = [quitado.get("narracion"), hogar.get("narracion")] if delante \
        else [hogar.get("narracion"), quitado.get("narracion")]
    hogar["narracion"] = " ".join(t for t in textos if t)
    marcas = (list(quitado.get("marcas") or []) + list(hogar.get("marcas") or [])) if delante \
        else (list(hogar.get("marcas") or []) + list(quitado.get("marcas") or []))
    hogar["marcas"] = marcas
    if delante:
        hogar["t_in"] = quitado["t_in"]
    else:
        hogar["t_out"] = quitado["t_out"]
        # el corte de SALIDA es el del último: con él se encadena lo de después
        hogar["corte"] = quitado.get("corte")
    hogar["duracion"] = round(float(hogar["t_out"]) - float(hogar["t_in"]), 3)
    # lo que el quitado ya llevaba de otros (una cadena: S001 -> S002 -> S003)
    # viaja con él, para que la pantalla diga todo lo que se oye aquí
    hogar.setdefault("absorbe", []).extend(quitado.get("absorbe") or [])
    hogar["absorbe"].append(
        {"id": quitado["id"], "lado": "antes" if delante else "despues",
         "narracion": quitado.get("narracion_imagen") or quitado.get("narracion") or "",
         "n": int(quitado.pop("_n_quitado", 0) or 0)})


def aplicar(escenas, raiz, clave, sin_imagen):
    """Quita de `escenas` (EN SITIO) los planos apuntados y junta su voz con el
    vecino. `clave(escena)` es el texto con el que se reconoce un plano.

    -> {"absorbidos": [ids quitados], "sin_casar": [entradas que no casan]}.
    Sin fichero no toca nada (y devuelve listas vacías)."""
    entradas = leer(raiz) if raiz else []
    salida = {"absorbidos": [], "sin_casar": []}
    if not entradas or not escenas:
        salida["sin_casar"] = list(entradas) if entradas else []
        return salida
    pendientes = list(entradas)
    vistos = {}
    i = 0
    while i < len(escenas):
        escena = escenas[i]
        texto = clave(escena)
        # la ocurrencia en el corte ORIGINAL: un plano ya quitado tambien cuenta
        n = vistos.get(texto, 0)
        vistos[texto] = n + 1
        entrada = next((e for e in pendientes if (e["texto"], e["n"]) == (texto, n)), None)
        if (entrada is None or not se_puede_quitar(escena, sin_imagen)
                or tiene_continuacion(escenas, i)):
            i += 1
            continue
        j = i - 1 if entrada["hacia"] == "anterior" else i + 1
        if j < 0 or j >= len(escenas) or not puede_recibir(escenas[j], sin_imagen):
            i += 1
            continue
        pendientes.remove(entrada)
        escena["_n_quitado"] = n
        _juntar(escenas[j], escena, delante=(j > i))
        salida["absorbidos"].append(escena["id"])
        del escenas[i]
        # sin avanzar: en `i` está ahora el siguiente (que puede ser el hogar,
        # y a su vez estar quitado hacia el siguiente: la voz viaja con él)
    salida["sin_casar"] = pendientes
    return salida

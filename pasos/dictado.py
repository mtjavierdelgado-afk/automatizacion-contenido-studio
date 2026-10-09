"""Dictado para el asistente: un audio grabado en el navegador, pasado a texto.

    transcribir(audio, nombre, tipo, idioma="es") -> {"texto", "modelo", "bytes"}
    disponible() -> bool        (hay una clave de OpenAI activa)

POR QUE CON LA API DE OPENAI Y NO CON UN MODELO LOCAL. El dictado de antes se
quito porque pedia un modelo de reconocimiento aparte y su propio entorno (ver
la tabla de CLAUDE.md). Esto no instala nada: la clave de OpenAI ya esta puesta
para las imagenes, y transcribir un minuto cuesta del orden de 0,003 $
(gpt-4o-mini-transcribe). Sin clave, la pantalla usa el reconocimiento del
propio navegador (Chrome, Edge, Safari), que es gratis pero no esta en todos.

EL TEXTO NO SE ENVIA SOLO: vuelve a la caja de la pregunta, y quien habla lo
lee y lo corrige antes de mandarlo. Un «Tranquilo» transcrito como «Tranquilo»
y no como «tranquilo.» no importa; un nombre de producto mal oido si.

Con ESTUDIO_SIMULAR=1 no sale a internet: devuelve una frase fija con el
tamano del audio, que es lo que dejan comprobar las pruebas.
"""
import os
import time

try:
    from . import claves
except ImportError:  # ejecutado con la carpeta pasos en sys.path
    import claves

URL = "https://api.openai.com/v1/audio/transcriptions"
#: El modelo barato y bueno en castellano; si la cuenta no lo tiene se cae a
#: whisper-1, que existe en todas. Se cambia con ESTUDIO_DICTADO_MODELO.
MODELO = os.environ.get("ESTUDIO_DICTADO_MODELO") or "gpt-4o-mini-transcribe"
MODELO_RESPALDO = "whisper-1"
#: Lo que acepta OpenAI por fichero. Un dictado de tres minutos en webm/opus
#: pesa ~1 MB, asi que esto solo para un error.
MAX_BYTES = 25 * 1024 * 1024
TIEMPO_S = 90
EXTENSIONES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
               "audio/x-m4a": ".m4a", "audio/aac": ".m4a", "audio/mpeg": ".mp3",
               "audio/wav": ".wav", "audio/x-wav": ".wav", "video/webm": ".webm"}


class ErrorDictado(RuntimeError):
    """No se ha podido transcribir, con el motivo en castellano."""


def simulado():
    return os.environ.get("ESTUDIO_SIMULAR") == "1"


def _claves():
    try:
        datos = claves.leer()
    except Exception:                                        # noqa: BLE001
        return []
    return [c["clave"] for c in datos.get("openai") or [] if c.get("activa")]


def disponible():
    return simulado() or bool(_claves())


def _motivo(respuesta):
    try:
        datos = respuesta.json()
        error = datos.get("error") if isinstance(datos, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
    except ValueError:
        pass
    return (respuesta.text or "").strip()[:300]


def _nombre_de(nombre, tipo):
    """OpenAI decide el formato por la EXTENSION del nombre: tiene que ir bien."""
    base = os.path.basename(str(nombre or "")) or "dictado"
    if os.path.splitext(base)[1]:
        return base
    tipo = str(tipo or "").split(";")[0].strip().lower()
    return base + EXTENSIONES.get(tipo, ".webm")


def transcribir(audio, nombre="dictado.webm", tipo="audio/webm", idioma="es"):
    """El audio pasado a texto. Lanza ErrorDictado con el motivo si no se puede."""
    if not audio:
        raise ErrorDictado("el audio ha llegado vacío: vuelve a grabar")
    if len(audio) > MAX_BYTES:
        raise ErrorDictado(f"el audio pesa {len(audio) / 1024 / 1024:.1f} MB y el "
                           f"tope son {MAX_BYTES // 1024 // 1024}: graba un trozo más corto")
    arranque = time.time()
    if simulado():
        return {"texto": f"(simulado) dictado de {len(audio)} bytes",
                "modelo": "simulado", "bytes": len(audio), "segundos": 0.0}
    lista = _claves()
    if not lista:
        raise ErrorDictado("para dictar hace falta una clave de OpenAI en "
                           "Configuración (o un navegador con dictado propio, "
                           "como Chrome o Edge)")
    import requests
    fichero = _nombre_de(nombre, tipo)
    idioma = str(idioma or "es").split("-")[0].lower()[:2] or "es"
    ultimo = ""
    for clave in lista:
        for modelo in (MODELO, MODELO_RESPALDO):
            try:
                respuesta = requests.post(
                    URL, headers={"Authorization": f"Bearer {clave}"},
                    files={"file": (fichero, audio, str(tipo or "audio/webm"))},
                    data={"model": modelo, "language": idioma,
                          "response_format": "json"},
                    timeout=TIEMPO_S)
            except requests.RequestException as fallo:
                raise ErrorDictado(f"no se ha podido hablar con OpenAI: {fallo}")
            if respuesta.status_code == 200:
                try:
                    texto = str(respuesta.json().get("text") or "").strip()
                except ValueError:
                    texto = ""
                if not texto:
                    raise ErrorDictado("no se ha entendido nada: habla más cerca "
                                       "del micrófono y vuelve a probar")
                return {"texto": texto, "modelo": modelo, "bytes": len(audio),
                        "segundos": round(time.time() - arranque, 1)}
            ultimo = f"OpenAI contesta {respuesta.status_code}: {_motivo(respuesta)}"
            # un modelo que esta cuenta no tiene: el de respaldo
            if respuesta.status_code in (400, 403, 404) and modelo != MODELO_RESPALDO \
                    and "model" in ultimo.lower():
                continue
            break
        # 401 o 429 (clave mala o sin saldo): la siguiente clave, si la hay
        if not (ultimo.startswith("OpenAI contesta 401")
                or ultimo.startswith("OpenAI contesta 429")):
            break
    raise ErrorDictado(ultimo or "OpenAI no ha devuelto nada")

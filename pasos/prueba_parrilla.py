"""Prueba de la PARRILLA (Automatizar → Parrilla), con Claude simulado.

Sin red, sin claves y sin llamar al CLI de verdad:

  1. el lector del formato del anexo (cabecera, escenas, marca, varios
     encargos, avisos), `separar`, `encargo_de` (exacto/adaptar, lo que falta)
     y `cambiar_cabecera`;
  2. leer documentos sin instalar nada: Word (.docx, con tablas), Excel
     (.xlsx, una fila por guion), texto, y los rechazos (.doc, falsos, vacíos);
  3. los datos: matrices, guiones, editar, estados, pasar al Encargo y
     enlazar con el vídeo hasta «publicado»;
  4. los trabajos con Claude (doble de las suites y ESTUDIO_SIMULAR=1): pegar,
     subir, pedir, trocear una matriz larga, un fallo que se dice, uno por
     proyecto a la vez, y que la guía enseña el mismo prompt que se usa;
  5. el Studio por HTTP (si hay fastapi): rutas, proyecto con clave que no se
     ve, subir un Word, pasar al Encargo sin escribir NINGÚN param, y el
     enlace usado → vídeo → publicado.

    python pasos/prueba_parrilla.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

CARPETA = tempfile.mkdtemp(prefix="parrilla_prueba_")
os.environ["ESTUDIO_SECRETOS"] = os.path.join(CARPETA, "secretos")
os.environ["ESTUDIO_BITACORA_GLOBAL"] = os.path.join(CARPETA, "bitacora_global.jsonl")
os.environ.pop("ESTUDIO_SIMULAR", None)

import guias  # noqa: E402
import parrilla as P  # noqa: E402

_ok = 0
_fallos = []


def ok(condicion, texto):
    global _ok
    if condicion:
        _ok += 1
        print(f"  ok   {texto}")
    else:
        _fallos.append(texto)
        print(f"  FALLO {texto}")


def igual(obtenido, esperado, texto):
    ok(obtenido == esperado, texto if obtenido == esperado
       else f"{texto}  [obtenido={obtenido!r} esperado={esperado!r}]")


def seccion(titulo):
    print(f"\n[{titulo}]")


def lanza(fn, *args, **kwargs):
    """El ErrorParrilla que lanza fn, o None."""
    try:
        fn(*args, **kwargs)
    except P.ErrorParrilla as fallo:
        return fallo
    return None


GUION = """EP01 — Fregadero simple o doble
Cliente / proyecto: Cocinas Lima
Uso: exacto
Red: TikTok
Formato: vertical
Duración: 45 s
Locución estimada: 100 palabras ≈ 40 s
Objetivo: que pidan medidas
CTA: Escríbenos por WhatsApp
Tono: cercano

**ESCENA 1 (0-3 s)**
Visual: una bandeja grande sobre un fregadero
Visual: la misma bandeja atascada
Voz: «Por fuera miden igual.
Por dentro, no.»
Texto en pantalla: ¿Simple o doble?

ESCENA 2
Visual: manos midiendo
Voz: «Mide lo más grande que lavas.»

CIERRE DE MARCA: logo y teléfono

MARCA DEL CLIENTE
- Mostrar: acero
- Evitar: marcas ajenas
- Otras reglas: ninguna

PARA EL ENCARGO
- Material: Por fuera miden igual. Por dentro, no.
Mide lo más grande que lavas.
- Indicaciones: cercano, una sola idea
- Llamadas a la acción: Escríbenos por WhatsApp
- Duración: 45 s · Formato: vertical

AVISOS
- ⚠ la locución pasa de 45 s
"""


def guion_simple(codigo, titulo, uso="adaptar", material="Texto de prueba del guion.", cta="Llámanos"):
    return (f"{codigo} — {titulo}\nCliente / proyecto: prueba\nUso: {uso}\nRed: Reels\n"
            "Formato: vertical\nDuración: la elijo en el Encargo\nObjetivo: probar\n"
            f"CTA: {cta}\nTono: alegre\n\nESCENA 1\nVisual: una fiesta\nVoz: «{material}»\n\n"
            f"PARA EL ENCARGO\n- Material: {material}\n- Indicaciones: alegre\n"
            f"- Llamadas a la acción: {cta}\n- Duración: elegir en el Encargo · Formato: vertical\n\n"
            "AVISOS\n- ninguno")


# ------------------------------------------------------------- 1. el lector

def prueba_lector():
    seccion("1] el lector del formato")
    g = P.leer_guion(GUION)
    igual((g["codigo"], g["titulo"]), ("EP01", "Fregadero simple o doble"), "ID y título de la primera línea")
    igual((g["uso"], g["red"], g["formato"], g["duracion_s"]), ("exacto", "TikTok", "vertical", 45),
          "la cabecera: uso, red, formato y duración en segundos")
    igual(g["cliente"], "Cocinas Lima", "«Cliente / proyecto:»")
    igual(len(g["escenas"]), 2, "dos escenas (la primera con ** de markdown, que se quita)")
    igual(g["escenas"][0]["tiempo"], "0-3 s", "el tiempo de la escena entre paréntesis")
    igual(len(g["escenas"][0]["visual"]), 2, "varias líneas Visual en una escena")
    igual(g["escenas"][0]["voz"], "«Por fuera miden igual. Por dentro, no.»", "la voz en dos líneas se junta")
    igual(g["escenas"][0]["texto_pantalla"], "¿Simple o doble?", "el texto en pantalla")
    igual(g["cierre"], "logo y teléfono", "el cierre de marca")
    igual((g["marca"]["mostrar"], g["marca"]["evitar"]), ("acero", "marcas ajenas"), "la marca del cliente")
    igual(len(g["encargos"]), 1, "un encargo")
    e = g["encargos"][0]
    igual(e["material"], "Por fuera miden igual. Por dentro, no.\nMide lo más grande que lavas.",
          "el material en varias líneas")
    igual((e["indicaciones"], e["llamadas"], e["duracion_s"], e["formato"]),
          ("cercano, una sola idea", "Escríbenos por WhatsApp", 45, "vertical"),
          "indicaciones, llamadas, duración y formato del encargo")
    igual(g["avisos"], ["⚠ la locución pasa de 45 s"], "los avisos")
    igual(P.leer_guion(guion_simple("A1", "x"))["avisos"], [], "«ninguno» no es un aviso")

    igual([P.segundos(x) for x in ["45 s", "1 min 30 s", "1:30", "90 segundos", "2 min", "60",
                                   "la elijo en el Encargo", "… s", ""]],
          [45, 90, 90, 90, 120, 60, None, None, None], "las duraciones se leen en segundos")
    plantilla = P.leer_guion(P.plantilla_vacia())
    igual((plantilla["uso"], plantilla["formato"]), ("adaptar", "vertical"), "la plantilla vacía se lee")
    igual(P.leer_guion("X — y\nUso: exacto | adaptar\nFormato: vertical | horizontal")["uso"], "",
          "«exacto | adaptar» sin elegir no es ninguno")

    dos = GUION.replace("- Duración: 45 s · Formato: vertical",
                        "- Duración: 45 s · Formato: vertical\n- Material: Versión horizontal.\n"
                        "- Indicaciones: para YouTube\n- Duración: 2 min · Formato: horizontal")
    g2 = P.leer_guion(dos)
    igual(len(g2["encargos"]), 2, "un segundo «- Material:» es otro vídeo")
    igual((g2["encargos"][1]["duracion_s"], g2["encargos"][1]["formato"]), (120, "horizontal"),
          "con su duración y su formato")

    # separar
    varios = f"{P.SEPARADOR}\n{guion_simple('A1', 'uno')}\n{P.SEPARADOR}\n{guion_simple('A2', 'dos')}"
    igual(len(P.separar(varios)), 2, "separar por «=== GUION ===»")
    sin_sep = guion_simple("B1", "uno") + "\n\n" + guion_simple("B2", "dos") + "\n\n" + guion_simple("B3", "tres")
    igual([P.leer_guion(t)["codigo"] for t in P.separar(sin_sep)], ["B1", "B2", "B3"],
          "y sin separador, por la forma «ID — Título» + «Cliente / proyecto:»")
    igual(len(P.separar("```\n" + guion_simple("C1", "x") + "\n```")), 1, "una valla de código no estorba")
    igual(P.separar("   "), [], "nada no es un guion")

    # encargo_de
    enc = P.encargo_de(g)
    igual((enc["guion_propio"], enc["cta"]), (True, None),
          "exacto: «Esto YA es el guion» y sin pedir otra llamada a la acción")
    igual((enc["duracion_objetivo_s"], enc["formato"], enc["nombre"]),
          (45, "vertical", "EP01 — Fregadero simple o doble"), "duración, formato y nombre")
    adaptar = P.encargo_de(P.leer_guion(guion_simple("A1", "x")))
    igual(adaptar["guion_propio"], False, "adaptar: el redactor lo reescribe")
    igual(adaptar["cta"]["cta_final"], {"puesto": True, "texto": "Llámanos"},
          "y la llamada a la acción va «al final»")
    igual(adaptar["duracion_objetivo_s"], None, "«elegir en el Encargo» no pone duración")
    ok(any("duración" in a for a in adaptar["avisos"]), "y lo avisa")
    falta = P.encargo_de(P.leer_guion(guion_simple("A1", "x", cta="[FALTA CTA]")))
    igual(falta["cta"], None, "[FALTA CTA] no se pasa como llamada")
    ok(any("FALTA CTA" in a for a in falta["avisos"]), "y se avisa")
    sin_encargo = P.leer_guion("Z1 — Sin encargo\nUso: adaptar\nTono: serio\n\nESCENA 1\nVoz: «Hola.»\n\n"
                               "ESCENA 2\nVoz: «Adiós.»")
    e3 = P.encargo_de(sin_encargo)
    igual(e3["material"], "Hola.\nAdiós.", "sin PARA EL ENCARGO, el material es la voz de las escenas")
    igual(e3["indicaciones"], "Tono: serio", "y las indicaciones salen del tono")
    ok(any("PARA EL ENCARGO" in a for a in e3["avisos"]), "y se avisa")
    igual(P.encargo_de(g2, 1)["formato"], "horizontal", "encargo_de elige el vídeo pedido")

    # cambiar_cabecera
    t = P.cambiar_cabecera(GUION, "formato", "horizontal")
    g3 = P.leer_guion(t)
    igual((g3["formato"], g3["encargos"][0]["formato"]), ("horizontal", "horizontal"),
          "cambiar el formato cambia la cabecera y el encargo (hay uno solo)")
    t = P.cambiar_cabecera(GUION, "duracion", "la elijo en el Encargo")
    g4 = P.leer_guion(t)
    igual((g4["duracion_s"], g4["encargos"][0]["duracion_s"]), (None, None),
          "quitar la duración la quita de los dos sitios")
    t = P.cambiar_cabecera(dos, "formato", "horizontal")
    igual(P.leer_guion(t)["encargos"][0]["formato"], "vertical",
          "con dos encargos, cada uno conserva el suyo")
    igual(P.leer_guion(P.cambiar_cabecera("Q1 — Sin uso\nTono: x", "uso", "exacto"))["uso"], "exacto",
          "una cabecera que no estaba se añade")
    igual(P.huella_material(" Hola\n  mundo "), P.huella_material("Hola mundo"),
          "la huella del material no mira los espacios")


# ------------------------------------------------------------ 2. documentos

def _docx(ruta, parrafos, tabla=None):
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    cuerpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in parrafos)
    if tabla:
        filas = "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in f)
                        + "</w:tr>" for f in tabla)
        cuerpo += f"<w:tbl>{filas}</w:tbl>"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{cuerpo}</w:body></w:document>')


def _xlsx(ruta, filas):
    s = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    compartidas, filas_xml = [], []
    for i, fila in enumerate(filas, 1):
        celdas = []
        for j, valor in enumerate(fila):
            col = chr(65 + j)
            if isinstance(valor, (int, float)):
                celdas.append(f'<c r="{col}{i}"><v>{valor}</v></c>')
            else:
                compartidas.append(valor)
                celdas.append(f'<c r="{col}{i}" t="s"><v>{len(compartidas) - 1}</v></c>')
        filas_xml.append(f'<row r="{i}">{"".join(celdas)}</row>')
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{s}" xmlns:r="{r}"><sheets>'
                   f'<sheet name="Guiones" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{s}">'
                   + "".join(f"<si><t>{x}</t></si>" for x in compartidas) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{s}"><sheetData>'
                   + "".join(filas_xml) + "</sheetData></worksheet>")


def prueba_documentos():
    seccion("2] leer documentos sin instalar nada")
    d = os.path.join(CARPETA, "docs")
    os.makedirs(d)
    _docx(os.path.join(d, "m.docx"), ["MATRIZ", "GUION 1 — Cumpleaños", "Voz: Alquila tu consola."],
          tabla=[["ID", "Título"], ["G2", "Karaoke"]])
    texto = P.leer_documento(os.path.join(d, "m.docx"))
    ok("GUION 1 — Cumpleaños" in texto and "Voz: Alquila tu consola." in texto, "Word: los párrafos, en orden")
    ok("G2 | Karaoke" in texto, "Word: las tablas, fila a fila")
    _xlsx(os.path.join(d, "m.xlsx"), [["ID", "Título", "Guion"], ["G1", "Cumple", "Voz uno"],
                                      ["G2", "Karaoke", "Voz dos"], ["G3", 45, ""]])
    texto = P.leer_documento(os.path.join(d, "m.xlsx"))
    ok("HOJA: Guiones" in texto, "Excel: el nombre de la hoja")
    ok("ID: G1\nTítulo: Cumple\nGuion: Voz uno" in texto, "Excel: cada fila como «Columna: valor»")
    igual(texto.count("---"), 3, "Excel: una fila por guion, separadas")
    ok("Título: 45" in texto, "Excel: los números también")
    with open(os.path.join(d, "t.txt"), "wb") as fh:
        fh.write("Guion en latin-1: canción".encode("latin-1"))
    igual(P.leer_documento(os.path.join(d, "t.txt")), "Guion en latin-1: canción",
          "un texto que no es UTF-8 se lee igual")
    fallo = lanza(P.leer_documento, os.path.join(d, "viejo.doc"))
    ok(fallo and ".docx" in str(fallo), "un .doc antiguo: que lo guarde como .docx")
    fallo = lanza(P.guardar_subida, CARPETA, "falso.docx", b"esto no es un zip")
    ok(fallo and "de verdad" in str(fallo), "un .docx que no es un Word se rechaza al subirlo")
    fallo = lanza(P.guardar_subida, CARPETA, "falso.pdf", b"hola")
    ok(fallo is not None, "un .pdf que no es PDF también")
    ok(lanza(P.guardar_subida, CARPETA, "vacio.txt", b"") is not None, "un fichero vacío también")
    ok(lanza(P.guardar_subida, CARPETA, "x.exe", b"MZ") is not None, "y lo que no es un documento")
    ok(lanza(P.guardar_subida, CARPETA, "x.txt", b"x" * (P.MAX_BYTES_DOCUMENTO + 1)) is not None,
       "ni más de 20 MB")
    with open(os.path.join(d, "m.docx"), "rb") as fh:
        ruta = P.guardar_subida(CARPETA, "Mi matriz.docx", fh.read())
    ok(os.path.isfile(ruta) and ruta.startswith(P.carpeta(CARPETA)) and "Mi matriz" not in ruta,
       "lo subido va a la carpeta de la Parrilla con un nombre propio")
    vacio = os.path.join(d, "vacio.docx")
    _docx(vacio, [])
    ok(lanza(P.leer_documento, vacio) is not None, "un Word sin texto se dice")


# ---------------------------------------------------------------- 3. datos

def prueba_datos():
    seccion("3] matrices, guiones, estados y pasar al Encargo")
    raiz = os.path.join(CARPETA, "datos")
    os.makedirs(raiz)
    ok(lanza(P.listar, raiz, "../fuera") is not None, "un proyecto con «..» no es un proyecto")
    igual(P.listar(raiz, "cliente1")["matrices"], [], "un proyecto sin nada")
    mid, gids = P.anadir_en_formato(raiz, "cliente1", "", GUION + f"\n{P.SEPARADOR}\n" + guion_simple("A2", "dos"),
                                    nombre="Matriz de octubre")
    igual(len(gids), 2, "guardar dos guiones ya en el formato (sin Claude)")
    lista = P.listar(raiz, "cliente1")
    igual(lista["matrices"][0]["nombre"], "Matriz de octubre", "en una matriz nueva con su nombre")
    igual(lista["cuentas"], {"pendiente": 2, "usado": 0, "publicado": 0}, "los dos, pendientes")
    igual(lista["matrices"][0]["guiones"][0]["codigo"], "EP01", "el resumen lleva el ID")
    ok(os.path.isfile(os.path.join(raiz, "_sistema", "parrilla", "proyectos", "cliente1.json")),
       "vive en _sistema/parrilla, fuera de los vídeos")
    ok(lanza(P.anadir_en_formato, raiz, "cliente1", "", "un texto cualquiera sin formato") is not None,
       "un texto sin el formato no se guarda tal cual (que lo convierta Claude)")
    _mid2, otro = P.anadir_en_formato(raiz, "cliente1", mid, guion_simple("A3", "tres"))
    igual(_mid2, mid, "añadir a una matriz que ya existe")
    ok(lanza(P.anadir_en_formato, raiz, "cliente1", "mnoexiste", guion_simple("A4", "x")).codigo == 404,
       "a una matriz que no existe, 404")

    gid = gids[0]
    g = P.guardar_guion(raiz, "cliente1", gid, {"formato": "horizontal"})
    igual((g["formato"], g["leido"]["encargos"][0]["formato"]), ("horizontal", "horizontal"),
          "cambiar el formato en la ficha cambia el texto")
    g = P.guardar_guion(raiz, "cliente1", gid, {"duracion_s": 30})
    igual(g["duracion_s"], 30, "y la duración")
    g = P.guardar_guion(raiz, "cliente1", gid, {"duracion_s": None})
    igual(g["duracion_s"], None, "sin duración: la elijo en el Encargo")
    ok(lanza(P.guardar_guion, raiz, "cliente1", gid, {"uso": "inventado"}) is not None, "un uso que no existe")
    ok(lanza(P.guardar_guion, raiz, "cliente1", gid, {"texto": "  "}) is not None, "un guion vacío no")
    ok(lanza(P.guardar_guion, raiz, "cliente1", gid, {"duracion_s": "mucho"}) is not None, "una duración rara no")
    g = P.guardar_guion(raiz, "cliente1", gid, {"texto": GUION.replace("Fregadero simple o doble", "Fregadero nuevo")})
    igual(g["titulo"], "Fregadero nuevo", "editar el texto lo vuelve a leer")
    ok(g["editado"], "y apunta cuándo se editó")

    antes = sorted(os.listdir(raiz))
    enc = P.pasar_al_encargo(raiz, "cliente1", gid, 0, "estilo-a")
    igual(enc["material"], "Por fuera miden igual. Por dentro, no.\nMide lo más grande que lavas.",
          "«Pasar al Encargo» devuelve el material")
    igual(sorted(os.listdir(raiz)), antes, "y no crea ningún vídeo ni toca nada fuera de _sistema")
    g = P.leer(raiz, "cliente1", gid)
    igual((g["estado"], g["estilo"]), ("usado", "estilo-a"), "el guion pasa a «usado», con su estilo")
    ok(lanza(P.pasar_al_encargo, raiz, "cliente1", gid, 5) is not None, "un vídeo que no está en el guion")

    # enlazar con el vídeo y publicado
    vistos = []

    def buscar(huella, desde):
        vistos.append((huella, desde))
        return ("video-1", "Vídeo uno") if huella == P.huella_material(enc["material"]) else ("", "")

    publicados = set()
    P.poner_al_dia(raiz, "cliente1", buscar, lambda pid: pid in publicados)
    g = P.leer(raiz, "cliente1", gid)
    igual((g["estado"], g["video"], g["video_nombre"]), ("usado", "video-1", "Vídeo uno"),
          "en cuanto hay un vídeo con ese material, queda enlazado")
    ok(vistos and vistos[0][1] == g["usado_al"], "buscando solo desde que se pasó al Encargo")
    vistos.clear()
    P.poner_al_dia(raiz, "cliente1", buscar, lambda pid: pid in publicados)
    igual(vistos, [], "uno ya enlazado no se vuelve a buscar")
    publicados.add("video-1")
    P.poner_al_dia(raiz, "cliente1", buscar, lambda pid: pid in publicados)
    igual(P.leer(raiz, "cliente1", gid)["estado"], "publicado", "y cuando su vídeo se publica, «publicado»")
    publicados.clear()
    P.poner_al_dia(raiz, "cliente1", buscar, lambda pid: False)
    igual(P.leer(raiz, "cliente1", gid)["estado"], "publicado", "un «publicado» no se quita solo")
    ok(not P.poner_al_dia(raiz, "cliente1", lambda *a: 1 / 0, lambda p: 1 / 0) or True,
       "un fallo al buscar no rompe la lista")

    g = P.guardar_guion(raiz, "cliente1", gid, {"estado": "pendiente"})
    igual((g["estado"], g["video"], g["usado_al"]), ("pendiente", "", ""),
          "«Volver a pendiente» olvida el vídeo y la fecha")
    g = P.guardar_guion(raiz, "cliente1", gids[1], {"estado": "publicado"})
    igual(g["estado"], "publicado", "se puede marcar publicado a mano (lo subió fuera del Studio)")
    ok(lanza(P.guardar_guion, raiz, "cliente1", gid, {"estado": "otro"}) is not None, "un estado que no existe")
    sin_material = P.anadir_en_formato(raiz, "cliente1", mid, "Z9 — Vacío\nUso: adaptar\n\nESCENA 1\nVisual: algo")[1][0]
    ok(lanza(P.pasar_al_encargo, raiz, "cliente1", sin_material) is not None,
       "un guion sin material no se pasa al Encargo")

    P.cambiar_matriz(raiz, "cliente1", mid, "  Octubre   2026 ")
    igual(P.listar(raiz, "cliente1")["matrices"][0]["nombre"], "Octubre 2026", "renombrar la matriz")
    ok(lanza(P.cambiar_matriz, raiz, "cliente1", mid, " ") is not None, "sin nombre no")
    P.borrar_guion(raiz, "cliente1", otro[0])
    ok(lanza(P.leer, raiz, "cliente1", otro[0]).codigo == 404, "borrar un guion")
    vacia = P.crear_matriz(raiz, "cliente1", "")
    ok(any(m["id"] == vacia and m["nombre"].startswith("Matriz del") for m in P.listar(raiz, "cliente1")["matrices"]),
       "una matriz sin nombre se llama por su fecha")
    P.borrar_matriz(raiz, "cliente1", mid)
    igual([m["id"] for m in P.listar(raiz, "cliente1")["matrices"]], [vacia], "borrar una matriz con sus guiones")
    igual(P.listar(raiz, "otro")["matrices"], [], "cada proyecto tiene lo suyo")


# ------------------------------------------------------------- 4. trabajos

def _esperar_trabajo(tid, segundos=20):
    limite = time.time() + segundos
    while time.time() < limite:
        t = P.trabajo(tid)
        if t and t["estado"] != "trabajando":
            return t
        time.sleep(0.1)
    return P.trabajo(tid)


def prueba_trabajos():
    seccion("4] los trabajos con Claude (doble)")
    raiz = os.path.join(CARPETA, "trabajos")
    os.makedirs(raiz)
    pedidos = []

    def claude(instruccion, para):
        pedidos.append((instruccion, para))
        if "[[TAREA:indice]]" in instruccion:
            doc = instruccion.split("DOCUMENTO:\n", 1)[1]
            primeras = [l for l in doc.split("\n") if l.startswith("GUION ")]
            return json.dumps({"guiones": [{"id": str(i), "titulo": l, "primera_linea": l.lower()}
                                           for i, l in enumerate(primeras)]})
        if "[[TAREA:pedir]]" in instruccion:
            import re as _re
            n = int(_re.search(r"Escribe (\d+) guion", instruccion).group(1))
            desde = int(_re.search(r"desde G(\d+)", instruccion).group(1))
            return "\n".join(f"{P.SEPARADOR}\n" + guion_simple(f"G{desde + i:02d}", f"idea {desde + i}")
                             for i in range(n))
        origen = instruccion.split("GUION ORIGINAL:\n", 1)[1]
        cuantos = max(1, origen.count("GUION "))
        return "\n".join(f"{P.SEPARADOR}\n" + guion_simple(f"C{i}", f"convertido {i}") for i in range(cuantos))

    P.LLAMAR_CLAUDE = claude
    try:
        ok(lanza(P.lanzar, raiz, "c1", "pegar", {"texto": "x"}) is not None, "sin elegir el uso no se lanza")
        ok(lanza(P.lanzar, raiz, "c1", "pegar", {"texto": " ", "modo": "exacto"}) is not None, "sin texto no")
        ok(lanza(P.lanzar, raiz, "c1", "pedir", {"peticion": "x", "cuantos": 99, "modo": "adaptar"}) is not None,
           f"pedir más de {P.MAX_PEDIR} no")
        ok(lanza(P.lanzar, raiz, "c1", "otro", {"modo": "adaptar"}) is not None, "un tipo que no existe no")

        t = P.lanzar(raiz, "c1", "pegar", {"texto": "GUION 1 hola\nGUION 2 adiós", "modo": "exacto",
                                            "nombre": "Pegados", "contexto": {"cliente": "EstadoPlay", "red": "TikTok"}},
                     en_hilo=False)
        igual(t["estado"], "listo", "pegar y convertir: listo")
        igual(len(t["guiones"]), 2, "con los dos guiones")
        instr = pedidos[-1][0]
        ok("MODO: exacto" in instr, "el prompt lleva el modo elegido")
        ok("- Cliente / proyecto: EstadoPlay" in instr and "- Red: TikTok" in instr,
           "y lo que ya se sabe del proyecto")
        ok(P._REGLAS in instr and P._FORMATO_SALIDA in instr and P._AJUSTE_RED in instr,
           "y las reglas, el ajuste por red y el formato del anexo, enteros")
        igual(P.listar(raiz, "c1")["matrices"][0]["nombre"], "Pegados", "en una matriz con su nombre")

        largo = "\n\n".join(f"GUION {i}\n" + ("Voz larga del guion. " * 300) for i in range(1, 6))
        ok(len(largo) > P.MAX_UNA_LLAMADA, "una matriz más larga que una llamada")
        n_antes = len(pedidos)
        t = P.lanzar(raiz, "c1", "pegar", {"texto": largo, "modo": "adaptar"}, en_hilo=False)
        hechas = pedidos[n_antes:]
        ok(hechas and "[[TAREA:indice]]" in hechas[0][0], "primero se pregunta dónde empieza cada guion")
        convertidas = [x for x in hechas if "[[TAREA:convertir]]" in x[0]]
        ok(len(convertidas) >= 2, f"y se convierte por partes ({len(convertidas)})")
        ok(all(len(x[0].split("GUION ORIGINAL:\n", 1)[1]) <= P.MAX_UNA_LLAMADA for x in convertidas),
           "cada parte cabe en una llamada")
        ok(all(x[0].split("GUION ORIGINAL:\n", 1)[1].startswith("GUION ") for x in convertidas),
           "y cada parte empieza en un guion (no lo parte por la mitad)")
        igual(len(t["guiones"]), 5, "salen los cinco")

        n_antes = len(pedidos)
        t = P.lanzar(raiz, "c1", "pedir", {"peticion": "consolas en fiestas", "cuantos": 7, "modo": "adaptar",
                                            "matriz": t["matriz"]}, en_hilo=False)
        hechas = pedidos[n_antes:]
        igual(len(hechas), 2, "pedir siete: dos llamadas (de cinco en cinco)")
        ok("YA ESCRITOS EN ESTA TANDA" in hechas[1][0] and "G01" in hechas[1][0],
           "la segunda sabe lo que ya se escribió, para no repetir")
        igual(len(t["guiones"]), 7, "salen siete")
        ok(len(P.listar(raiz, "c1")["matrices"]) == 2, "añadidos a la matriz que se eligió")

        docx = os.path.join(CARPETA, "subir.docx")
        _docx(docx, ["GUION 1 cumple", "GUION 2 karaoke"])
        with open(docx, "rb") as fh:
            ruta = P.guardar_subida(raiz, "subir.docx", fh.read())
        t = P.lanzar(raiz, "c1", "subir", {"ruta": ruta, "nombre_fichero": "subir.docx", "modo": "adaptar"},
                     en_hilo=False)
        igual((t["estado"], len(t["guiones"])), ("listo", 2), "subir un Word y convertirlo")
        ok(not os.path.exists(ruta), "el documento subido no se queda en el servidor")
        m = [x for x in P.listar(raiz, "c1")["matrices"] if x["id"] == t["matriz"]][0]
        igual(m["origen"].get("fichero"), "subir.docx", "la matriz recuerda de qué fichero salió")

        P.LLAMAR_CLAUDE = lambda i, p: "Lo siento, no puedo."
        t = P.lanzar(raiz, "c1", "pegar", {"texto": "algo", "modo": "adaptar"}, en_hilo=False)
        igual(t["estado"], "error", "una respuesta sin ningún guion es un error")
        ok("formato del Studio" in t["error"], f"que se explica: {t['error'][:70]}")

        def lento(i, p):
            time.sleep(0.8)
            return claude(i, p)
        P.LLAMAR_CLAUDE = lento
        t1 = P.lanzar(raiz, "c1", "pegar", {"texto": "GUION 1 x", "modo": "adaptar"})
        fallo = lanza(P.lanzar, raiz, "c1", "pegar", {"texto": "GUION 1 x", "modo": "adaptar"})
        ok(fallo is not None and fallo.codigo == 409, "un segundo trabajo en el mismo proyecto: 409")
        t2 = P.lanzar(raiz, "c2", "pegar", {"texto": "GUION 1 x", "modo": "adaptar"})
        ok(t2["estado"] == "trabajando", "en otro proyecto sí")
        igual(P.trabajo_de("c1")["id"], t1["id"], "el trabajo en marcha se encuentra por proyecto")
        igual(_esperar_trabajo(t1["id"])["estado"], "listo", "y acaba")
        _esperar_trabajo(t2["id"])
        P.olvidar_trabajo(t1["id"])
        igual(P.trabajo(t1["id"]), None, "uno acabado se puede olvidar")
    finally:
        P.LLAMAR_CLAUDE = None

    # el doble de ESTUDIO_SIMULAR (el que usan el recorrido y prueba_api)
    os.environ["ESTUDIO_SIMULAR"] = "1"
    try:
        t = P.lanzar(raiz, "sim", "pedir", {"peticion": "fiestas", "cuantos": 3, "modo": "exacto"}, en_hilo=False)
        igual((t["estado"], len(t["guiones"])), ("listo", 3), "simulado: pedir tres")
        g = P.leer(raiz, "sim", t["guiones"][0])
        igual(g["uso"], "exacto", "con el uso pedido")
        t = P.lanzar(raiz, "sim", "pegar", {"texto": "uno\n---\ndos", "modo": "adaptar"}, en_hilo=False)
        igual(len(t["guiones"]), 2, "simulado: convertir separa por «---»")
        open(os.path.join(P.carpeta(raiz), "_fallar_claude"), "w").close()
        t = P.lanzar(raiz, "sim", "pegar", {"texto": "uno", "modo": "adaptar"}, en_hilo=False)
        igual(t["estado"], "error", "simulado: con _fallar_claude falla como el CLI sin cupo")
        os.remove(os.path.join(P.carpeta(raiz), "_fallar_claude"))
    finally:
        os.environ.pop("ESTUDIO_SIMULAR", None)

    seccion("4b] la guía enseña lo mismo que se usa")
    igual(guias.GUIAS["guion_parrilla"]["prompt_ia"], P.prompt_para_otra_ia(),
          "el prompt de la guía «El formato del guion» es el del anexo, el mismo que usa la Parrilla")
    igual(guias.GUIAS["guion_parrilla"]["plantilla"], P.plantilla_vacia(), "y la plantilla es la de «Escribir uno»")
    ejemplo = P.leer_guion(guias.GUIAS["guion_parrilla"]["ejemplo"])
    ok(ejemplo["encargos"] and P.encargo_de(ejemplo)["material"], "el ejemplo de la guía se lee y se puede pasar al Encargo")
    ok("pedir_guiones" in guias.ORDEN and "guion_parrilla" in guias.ORDEN, "las dos guías salen en la lista")
    ok("GUION ORIGINAL:\n<pega aquí>" in P.prompt_para_otra_ia(), "el prompt acaba donde se pega el guion")


# ----------------------------------------------------------- 5. el Studio

def _puerto():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _arrancar(carpeta):
    import requests
    puerto = _puerto()
    entorno = dict(os.environ)
    entorno.update({"PYTHONIOENCODING": "utf-8", "ESTUDIO_SIMULAR": "1",
                    "ESTUDIO_SECRETOS": os.path.join(carpeta, "secretos"),
                    "ESTUDIO_AJUSTES": os.path.join(carpeta, "ajustes.json"),
                    "ESTUDIO_PRESETS": os.path.join(carpeta, "presets.json"),
                    "ESTUDIO_BANCO_PRESETS": os.path.join(carpeta, "banco"),
                    "ESTUDIO_RECETAS": os.path.join(carpeta, "recetas.json"),
                    "ESTUDIO_ESTADISTICAS": os.path.join(carpeta, "estadisticas.json"),
                    "ESTUDIO_COSTE_GLOBAL": os.path.join(carpeta, "coste_global.jsonl")})
    os.makedirs(entorno["ESTUDIO_SECRETOS"], exist_ok=True)
    proceso = subprocess.Popen(
        [sys.executable, os.path.join(RAIZ, "app.py"), "--puerto", str(puerto),
         "--proyectos", os.path.join(carpeta, "proyectos")],
        cwd=RAIZ, env=entorno, stdout=open(os.path.join(carpeta, "servidor.log"), "w"),
        stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{puerto}"
    limite = time.time() + 90
    while time.time() < limite:
        if proceso.poll() is not None:
            with open(os.path.join(carpeta, "servidor.log"), encoding="utf-8", errors="replace") as fh:
                raise RuntimeError("el servidor murió al arrancar:\n" + fh.read()[-3000:])
        try:
            if requests.get(base + "/api/salud", timeout=2).status_code == 200:
                return proceso, base
        except requests.RequestException:
            time.sleep(0.3)
    proceso.kill()
    raise RuntimeError("el servidor no respondió en 90 s")


def _esperar(s, url, segundos=30):
    limite = time.time() + segundos
    datos = {}
    while time.time() < limite:
        datos = s.get(url, timeout=30).json()
        if datos.get("estado") != "trabajando":
            return datos
        time.sleep(0.3)
    return datos


def prueba_studio():
    import requests
    seccion("5] el Studio por HTTP, con Claude simulado")
    carpeta = os.path.join(CARPETA, "studio")
    raiz = os.path.join(carpeta, "proyectos")
    os.makedirs(raiz)
    proceso, base = _arrancar(carpeta)
    s = requests.Session()
    try:
        r = s.get(base + "/api/parrilla/proyectos")
        igual(r.status_code, 200, "GET /api/parrilla/proyectos")
        igual([p["id"] for p in r.json()["proyectos"]], ["_sin"], "sin proyectos, solo «Sin proyecto»")
        cid = s.post(base + "/api/clientes", json={"nombre": "Cocinas Lima"}).json()["cliente"]["id"]
        secreto = s.post(base + "/api/clientes", json={"nombre": "Secreto"}).json()["cliente"]["id"]
        s.put(base + f"/api/clientes/{secreto}", json={"clave": "1234"})
        ids = [p["id"] for p in s.get(base + "/api/parrilla/proyectos").json()["proyectos"]]
        ok(cid in ids and secreto not in ids, "un proyecto con clave sin abrir no sale")
        igual(s.get(base + f"/api/parrilla/proyectos/{secreto}").status_code, 404,
              "ni se puede leer su Parrilla")
        igual(s.get(base + "/api/parrilla/proyectos/noexiste").status_code, 404, "uno que no existe, 404")

        r = s.post(base + f"/api/parrilla/proyectos/{cid}/guiones", json={"texto": GUION, "nombre": "Octubre"})
        igual(r.status_code, 201, "guardar un guion ya en formato")
        gid = r.json()["guiones"][0]
        mid = r.json()["matriz"]
        lista = s.get(base + f"/api/parrilla/proyectos/{cid}").json()
        igual(lista["matrices"][0]["guiones"][0]["codigo"], "EP01", "sale en su Parrilla")
        igual(s.post(base + f"/api/parrilla/proyectos/{cid}/guiones", json={"texto": "sin formato"}).status_code,
              400, "un texto sin formato da 400 con su motivo")

        r = s.post(base + f"/api/parrilla/proyectos/{cid}/convertir",
                   json={"texto": "uno\n---\ndos", "modo": "adaptar", "matriz": mid})
        igual(r.status_code, 202, "convertir con Claude: 202 y un trabajo")
        t = _esperar(s, base + f"/api/parrilla/trabajos/{r.json()['id']}")
        igual((t["estado"], len(t["guiones"])), ("listo", 2), "el trabajo acaba con dos guiones")
        igual(s.post(base + f"/api/parrilla/proyectos/{cid}/convertir", json={"texto": "x"}).status_code,
              400, "sin uso, 400")

        docx = os.path.join(CARPETA, "studio.docx")
        _docx(docx, ["uno", "---", "dos", "---", "tres"])
        with open(docx, "rb") as fh:
            r = s.post(base + f"/api/parrilla/proyectos/{cid}/subir",
                       files={"documento": ("Matriz cliente.docx", fh.read())},
                       data={"modo": "exacto", "red": "TikTok"})
        igual(r.status_code, 202, "subir un Word: 202")
        t = _esperar(s, base + f"/api/parrilla/trabajos/{r.json()['id']}")
        igual((t["estado"], len(t["guiones"])), ("listo", 3), "convertido en tres guiones")
        lista = s.get(base + f"/api/parrilla/proyectos/{cid}").json()
        ok(any(m["nombre"] == "Matriz cliente" for m in lista["matrices"]),
           "en una matriz con el nombre del fichero")
        r = s.post(base + f"/api/parrilla/proyectos/{cid}/subir", files={"documento": ("viejo.doc", b"xx")},
                   data={"modo": "exacto"})
        igual(r.status_code, 400, "un .doc antiguo, 400")
        ok(".docx" in r.json().get("error", ""), "diciendo que lo guarde como .docx")
        restos = os.listdir(os.path.join(raiz, "_sistema", "parrilla", "subidas"))
        igual(restos, [], "no quedan documentos subidos en el servidor")

        r = s.post(base + f"/api/parrilla/proyectos/{cid}/pedir",
                   json={"peticion": "fregaderos", "cuantos": 2, "modo": "adaptar"})
        t = _esperar(s, base + f"/api/parrilla/trabajos/{r.json()['id']}")
        igual((t["estado"], len(t["guiones"])), ("listo", 2), "pedir dos guiones a Claude")

        g = s.put(base + f"/api/parrilla/proyectos/{cid}/guiones/{gid}", json={"uso": "adaptar"}).json()
        igual(g["uso"], "adaptar", "cambiar el uso desde la ficha")
        igual(s.put(base + f"/api/parrilla/proyectos/{cid}/guiones/{gid}", json={"uso": "x"}).status_code, 400,
              "un uso que no existe, 400")

        antes = sorted(x for x in os.listdir(raiz) if not x.startswith("_"))
        r = s.post(base + f"/api/parrilla/proyectos/{cid}/guiones/{gid}/encargo", json={"estilo": "noexiste"})
        igual(r.status_code, 404, "pasar al Encargo con un estilo que no existe, 404")
        r = s.post(base + f"/api/parrilla/proyectos/{cid}/guiones/{gid}/encargo", json={})
        igual(r.status_code, 200, "«Pasar al Encargo»")
        enc = r.json()["encargo"]
        igual(enc["guion_propio"], False, "adaptar: sin «Esto YA es el guion»")
        igual(enc["cta"]["cta_final"]["texto"], "Escríbenos por WhatsApp", "con la llamada a la acción al final")
        igual(sorted(x for x in os.listdir(raiz) if not x.startswith("_")), antes,
              "no crea ningún vídeo")

        # el vídeo que se crea con ese material queda enlazado, y publicado
        from nucleo.proyecto import Proyecto
        time.sleep(1.1)
        video = Proyecto.crear(raiz, "Fregadero en vídeo")
        r = s.put(base + f"/api/proyectos/{video.id}/pasos/ingesta/params", json={"texto": enc["material"]})
        ok(r.status_code == 200, "un vídeo nuevo con ese material")
        g = s.get(base + f"/api/parrilla/proyectos/{cid}").json()
        fila = [x for m in g["matrices"] for x in m["guiones"] if x["id"] == gid][0]
        igual((fila["estado"], fila["video"]), ("usado", video.id), "la Parrilla lo enlaza con el guion")
        carpeta_pub = os.path.join(raiz, "_sistema", "publicar", "videos")
        os.makedirs(carpeta_pub, exist_ok=True)
        with open(os.path.join(carpeta_pub, f"{video.id}.json"), "w", encoding="utf-8") as fh:
            json.dump({"envios": [{"id": "e1", "red": "tiktok", "estado": "publicado"}]}, fh)
        g = s.get(base + f"/api/parrilla/proyectos/{cid}").json()
        fila = [x for m in g["matrices"] for x in m["guiones"] if x["id"] == gid][0]
        igual(fila["estado"], "publicado", "y cuando se publica en Publicar, «publicado»")
        igual(g["cuentas"]["publicado"], 1, "las cuentas lo cuentan")

        r = s.get(base + f"/api/parrilla/plantilla?proyecto={cid}")
        ok("Cliente / proyecto: Cocinas Lima" in r.json()["texto"], "la plantilla lleva el nombre del proyecto")
        igual(s.get(base + "/api/parrilla/trabajos/tnoexiste").status_code, 404, "un trabajo que no existe, 404")
        igual(s.delete(base + f"/api/parrilla/proyectos/{cid}/guiones/{gid}").status_code, 200, "borrar un guion")
        igual(s.delete(base + f"/api/parrilla/proyectos/{cid}/matrices/{mid}").status_code, 200, "borrar una matriz")
        guias_api = [x["id"] for x in s.get(base + "/api/sistema/guias").json()["guias"]]
        ok("guion_parrilla" in guias_api and "pedir_guiones" in guias_api, "las guías salen en /api/sistema/guias")
    finally:
        proceso.terminate()
        proceso.wait(timeout=15)


def prueba_revision():
    """Lo que encontró la revisión independiente del 17-10-2026. Cada una
    falla con el código de antes del arreglo."""
    seccion("6] lo de la revisión independiente")
    # 1. una respuesta de UN guion con su separador delante
    uno = P.separar(f"{P.SEPARADOR}\n" + guion_simple("EP07", "Uno solo"))
    igual(len(uno), 1, "un solo guion con «=== GUION ===» delante: un guion")
    igual(P.leer_guion(uno[0])["codigo"], "EP07", "y su ID no es el separador")
    ok(P.SEPARADOR not in uno[0], "el separador no se queda en el texto guardado")
    # título con guion normal
    g = P.leer_guion("Fregadero simple - doble\nUso: adaptar")
    igual((g["codigo"], g["titulo"]), ("", "Fregadero simple - doble"),
          "«Fregadero simple - doble» es todo título (sin ID)")
    g = P.leer_guion("G05 - Karaoke\nUso: adaptar")
    igual((g["codigo"], g["titulo"]), ("G05", "Karaoke"), "«G05 - Karaoke» sí lleva ID")
    igual(P.segundos("60 s (1 min)"), 60, "«60 s (1 min)» son 60 s, no 120")
    t = P.cambiar_cabecera("\n\nQ1 — Título\nTono: x", "uso", "exacto")
    g = P.leer_guion(t)
    igual((g["codigo"], g["titulo"], g["uso"]), ("Q1", "Título", "exacto"),
          "con líneas en blanco delante, la cabecera nueva va detrás del título")

    raiz = os.path.join(CARPETA, "revision")
    os.makedirs(raiz)
    # 4. un fichero ilegible no se pisa con una Parrilla vacía
    P.anadir_en_formato(raiz, "roto", "", guion_simple("R1", "x"))
    ruta = P._ruta(raiz, "roto")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write('{"matrices": [ roto')
    fallo = lanza(P.anadir_en_formato, raiz, "roto", "", guion_simple("R2", "y"))
    ok(fallo is not None and fallo.codigo == 503, "un fichero corrupto da 503 al guardar")
    with open(ruta, encoding="utf-8") as fh:
        ok(fh.read() == '{"matrices": [ roto', "y no se escribe encima (no se pierde nada)")
    ok(lanza(P.listar, raiz, "roto") is not None, "ni se enseña como si estuviera vacío")

    # matriz borrada mientras Claude convierte: va a una nueva
    mid = P.crear_matriz(raiz, "c1", "Destino")

    def claude_que_borra(instruccion, para):
        P.borrar_matriz(raiz, "c1", mid)
        return f"{P.SEPARADOR}\n" + guion_simple("M1", "salvado")
    P.LLAMAR_CLAUDE = claude_que_borra
    try:
        t = P.lanzar(raiz, "c1", "pegar", {"texto": "x", "modo": "adaptar", "matriz": mid}, en_hilo=False)
    finally:
        P.LLAMAR_CLAUDE = None
    igual(t["estado"], "listo", "si borran la matriz de destino a mitad, lo convertido no se pierde")
    ok(t["matriz"] != mid and len(t["guiones"]) == 1, "va a una matriz nueva")

    # 5. buscar el vídeo fuera del cerrojo, y no para siempre
    _m, gids = P.anadir_en_formato(raiz, "c2", "", guion_simple("B1", "x") + f"\n{P.SEPARADOR}\n"
                                   + guion_simple("B2", "y", material="Otro material."))
    P.pasar_al_encargo(raiz, "c2", gids[0])
    P.pasar_al_encargo(raiz, "c2", gids[1])
    datos = P._leer(raiz, "c2")
    datos["matrices"][0]["guiones"][1]["usado_al"] = "2020-01-01T00:00:00"
    P._guardar(raiz, "c2", datos)
    import threading as _hilos
    buscados, bloqueado = [], []

    def buscar(huella, desde):
        buscados.append(desde)
        otro = _hilos.Thread(target=P.crear_matriz, args=(raiz, "c2", "desde otro hilo"))
        otro.start()
        otro.join(3)
        bloqueado.append(otro.is_alive())
        return "", ""
    P.poner_al_dia(raiz, "c2", buscar, lambda pid: False)
    igual(len(buscados), 1, f"un guion usado hace más de {P.DIAS_BUSCANDO_VIDEO} días ya no se busca")
    igual(bloqueado, [False], "mientras se busca el vídeo, el proyecto se puede guardar (sin cerrojo)")

    # documentos: Excel sin «r», Word con controles y tablas anidadas, bomba zip
    d = os.path.join(CARPETA, "docs_rev")
    os.makedirs(d)
    xs = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xr = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(os.path.join(d, "sin_r.xlsx"), "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{xs}" xmlns:r="{xr}"><sheets>'
                   '<sheet name="H" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{xs}"><sheetData>'
                   '<row><c t="inlineStr"><is><t>ID</t></is></c><c t="inlineStr"><is><t>Guion</t></is></c></row>'
                   '<row><c t="inlineStr"><is><t>G1</t></is></c><c t="inlineStr"><is><t>Voz uno</t></is></c></row>'
                   '</sheetData></worksheet>')
    ok("ID: G1\nGuion: Voz uno" in P.leer_documento(os.path.join(d, "sin_r.xlsx")),
       "un Excel sin «r» en las celdas no las amontona en la columna A")
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    celda = lambda t: f"<w:tc><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"  # noqa: E731
    interna = f"<w:tbl><w:tr>{celda('anidada')}</w:tr></w:tbl>"
    cuerpo = (f"<w:sdt><w:sdtContent><w:p><w:r><w:t>Texto en un control</w:t></w:r></w:p></w:sdtContent></w:sdt>"
              f"<w:tbl><w:tr>{celda('fuera')}<w:tc>{interna}</w:tc></w:tr></w:tbl>")
    with zipfile.ZipFile(os.path.join(d, "control.docx"), "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{w}"><w:body>{cuerpo}</w:body></w:document>')
    texto = P.leer_documento(os.path.join(d, "control.docx"))
    ok("Texto en un control" in texto, "Word: el texto de un control de contenido se lee")
    igual(texto.count("anidada"), 1, "Word: una tabla dentro de otra se lee una vez")
    with zipfile.ZipFile(os.path.join(d, "bomba.docx"), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"\0" * (P.MAX_PARTE_ZIP + 1024))
    ok(lanza(P.leer_documento, os.path.join(d, "bomba.docx")) is not None,
       "una «bomba zip» se rechaza sin descomprimirla")

    # 3. el PDF lo lee Claude en una carpeta con el PDF y nada más
    pdf = os.path.join(d, "m.pdf")
    with open(pdf, "wb") as fh:
        fh.write(b"%PDF-1.4\n% sin texto\n")
    vistos = {}

    def claude_pdf(instruccion, para, cwd=None, permitidas=(), vetadas=None):
        vistos.update(cwd=cwd, contenido=sorted(os.listdir(cwd)), permitidas=permitidas,
                      vetadas=vetadas, instruccion=instruccion)
        return "texto del pdf"
    antes_which, antes_claude = P.shutil.which, P._claude
    P.shutil.which = lambda nombre: None
    P._claude = claude_pdf
    try:
        texto = P.leer_pdf(pdf, cwd=P.carpeta(raiz))
    finally:
        P.shutil.which, P._claude = antes_which, antes_claude
    igual(texto, "texto del pdf", "sin pdftotext, el PDF lo lee Claude")
    igual(vistos["contenido"], ["documento.pdf"], "en una carpeta donde solo está ese PDF")
    ok(not vistos["cwd"].startswith(os.path.join(P.carpeta(raiz), "proyectos")) and
       os.path.join("parrilla", "proyectos") not in vistos["cwd"], "lejos de las matrices de los proyectos")
    ok(len(vistos["permitidas"]) == 1 and vistos["permitidas"][0].endswith("/documento.pdf)"),
       "Read solo para ese fichero")
    ok("Read" not in vistos["vetadas"] and "Bash" in vistos["vetadas"] and "WebFetch" in vistos["vetadas"],
       "y ninguna otra herramienta")
    ok(not os.path.exists(vistos["cwd"]), "la carpeta aislada se borra al acabar")


def main():
    print("PRUEBA DE LA PARRILLA")
    prueba_lector()
    prueba_documentos()
    prueba_datos()
    prueba_trabajos()
    prueba_revision()
    try:
        import fastapi  # noqa: F401
        import requests  # noqa: F401
        hay_servidor = True
    except ImportError:
        hay_servidor = False
    if hay_servidor:
        prueba_studio()
    else:
        print("\n[5] OMITIDA: falta fastapi en este entorno (en el servidor sí corre)")
    shutil.rmtree(CARPETA, ignore_errors=True)
    print("\n" + "=" * 70)
    if _fallos:
        print(f"FALLAN {len(_fallos)} de {_ok + len(_fallos)} comprobaciones:")
        for fallo in _fallos:
            print(f"  - {fallo}")
        return 1
    print(f"PARRILLA OK: {_ok} comprobaciones pasan")
    return 0


if __name__ == "__main__":
    sys.exit(main())

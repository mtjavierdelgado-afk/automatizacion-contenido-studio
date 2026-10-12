"""DESCARGAR EL VIDEO POR PARTES (11-10-2026).

El MP4 del montaje lleva todo junto: imagen con subtitulos y logo, voz, musica
y efectos. Para usar las piezas por separado (otro editor, otra musica, un
doblaje) aqui se preparan, en `<proyecto>/exportes/v<N>/`, a partir de lo que
el montaje YA dejo en su version:

  render/v<N>/video.mp4      la imagen con subtitulos, cola y logo
  render/v<N>/clips/*.mp4    los planos SIN logo (el logo se pone al final)
  render/v<N>/efectos.wav    los efectos ya colocados en su segundo
  render/v<N>/cama.wav       la musica encadenada (o el tema del banco)
  voz/v<M>/narracion.wav     la voz

NADA DE ESTO TOCA EL PROYECTO: no escribe params (no mueve ninguna firma), no
crea version y no pasa por `trabajo/`. Y NADA CUESTA DINERO: es ffmpeg y, para
quitar los subtitulos, volver a capturar los planos en el navegador.

Lo barato (segundos): cualquier combinacion de voz, musica y efectos sobre la
imagen ya montada, quitar el logo (se vuelven a unir los planos, que no lo
llevan) y los audios sueltos. Lo caro (lo que tarda un montaje): la imagen SIN
SUBTITULOS, porque estan cocidos en cada fotograma; se recapturan los planos
con la capa de subtitulos vacia, igual que el render pero en otra carpeta.

La mezcla es LA MISMA del video (`sonido.filtro_de_mezcla`, con su ducking y
su nivel), medida UNA vez con todas las pistas y aplicada igual a cada
variante: asi, por ejemplo, la musica sin voz suena exactamente como sonaba
debajo de la voz, agachada en los mismos sitios.
"""
import os
import shutil
import subprocess
import time

try:
    from . import p8_render
except ImportError:                                   # corriendo desde pasos/
    import p8_render

medios = p8_render.medios
sonido = p8_render.sonido

PARTES = ("voz", "musica", "efectos")


class ErrorExporte(RuntimeError):
    """No se puede preparar lo pedido, con el motivo en castellano."""


# ------------------------------------------------------------------ lo que hay

def material(proyecto, params_render, estado=None):
    """Lo que dejo el montaje activo, para partirlo. -> dict

    Lanza ErrorExporte si el video no esta montado."""
    ruta_video = medios.salida_de(proyecto, "render", claves=("video", "mp4"),
                                  patrones=(r"video\.mp4",), estado=estado)
    if not ruta_video or not os.path.exists(ruta_video):
        raise ErrorExporte("el vídeo todavía no está montado: móntalo antes de descargarlo por partes")
    carpeta = os.path.dirname(ruta_video)
    ruta_plan = medios.salida_de(proyecto, "assets", claves=("plan",),
                                 patrones=(r"plan\.json",), estado=estado)
    plan = medios.leer_json(ruta_plan, {}) if ruta_plan else {}
    escenas = plan.get("escenas") or []
    desfase = float(escenas[0]["t_in"]) if escenas else 0.0
    largo = (float(escenas[-1]["t_out"]) - desfase) if escenas else medios.duracion_media(ruta_video)
    largo_con_cola = largo + (p8_render.COLA_NEGRO_S if escenas else 0.0)
    voz = medios.salida_de(proyecto, "voz", claves=("wav", "audio", "narracion"),
                           patrones=(r"narracion\.wav", r".*\.wav"), estado=estado)
    p = p8_render._con_defectos(params_render or {})
    con_sonido = p.get("sonido", True)
    ficha_musica = (p.get("musica") or {}) if con_sonido else {}
    musica, cama = None, False
    if ficha_musica.get("tramos") and os.path.exists(os.path.join(carpeta, "cama.wav")):
        musica, cama = os.path.join(carpeta, "cama.wav"), True
    elif ficha_musica.get("id"):
        candidata = sonido.banco("musica", sonido._nombre_de(ficha_musica))
        musica = candidata if os.path.exists(candidata) else None
    efectos = os.path.join(carpeta, "efectos.wav")
    efectos = efectos if con_sonido and os.path.exists(efectos) else None

    def numero(clave):
        try:
            return float(p.get(clave) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    version = os.path.basename(carpeta)
    return {
        "carpeta": carpeta, "video": ruta_video, "version": version,
        "plan": plan, "escenas": escenas, "desfase": desfase,
        "largo_con_cola": max(0.1, largo_con_cola),
        "voz": voz if voz and os.path.exists(voz) else None,
        "musica": musica, "cama": cama, "efectos": efectos,
        "musica_db": numero("musica_db"), "efectos_db": numero("efectos_db"),
        "lufs": p.get("musica_lufs"), "presencia": p.get("musica_presencia"),
        "fps": int(p["fps"]), "calidad": p.get("calidad") or "media",
        "calidad_video": p.get("calidad_video"),
        "logo": p.get("logo") or {}, "params": p,
        "hay": {"voz": bool(voz and os.path.exists(voz)), "musica": bool(musica),
                "efectos": bool(efectos)},
    }


def carpeta_de(proyecto, m):
    destino = os.path.join(proyecto.raiz, "exportes", m["version"])
    os.makedirs(destino, exist_ok=True)
    return destino


def _ffmpeg(orden, que):
    proceso = subprocess.run(orden, capture_output=True, text=True, timeout=7200,
                             **medios.SIN_VENTANA)
    if proceso.returncode != 0:
        raise ErrorExporte(f"ffmpeg no pudo {que}: {proceso.stderr[-400:]}")


# ------------------------------------------------------------------ el sonido

def _entradas(m):
    """[args de ffmpeg] desde la entrada 1 (la 0 es la imagen o nada)."""
    orden = ["-ss", f"{max(0.0, m['desfase']):.3f}", "-i", m["voz"]]
    if m["musica"]:
        if not m["cama"]:
            orden += ["-stream_loop", "-1"]
        orden += ["-i", m["musica"]]
    if m["efectos"]:
        orden += ["-i", m["efectos"]]
    return orden


def _grafo(m, medida, silenciar):
    """El grafo de la mezcla del video, con las partes de `silenciar` a cero."""
    grafo = sonido.filtro_de_mezcla(
        bool(m["musica"]), bool(m["efectos"]), m["largo_con_cola"],
        m["lufs"] if m["lufs"] is not None else sonido.MUSICA_LUFS,
        ya_normalizada=m["cama"], ajuste_db=m["musica_db"], master=True,
        medida=medida, efectos_db=m["efectos_db"], presencia=m["presencia"])
    if "voz" in silenciar:
        # la voz sigue siendo la LLAVE del ducking: la musica se agacha en los
        # mismos sitios que en el video, que es como «suena» debajo de la voz
        if "[voz]asplit=2[vozmix][vozllave]" in grafo:
            grafo = grafo.replace("[voz]asplit=2[vozmix][vozllave]",
                                  "[voz]asplit=2[vozcruda][vozllave];[vozcruda]volume=0[vozmix]")
        else:
            grafo = grafo.replace("[voz]anull[vozmix]", "[voz]volume=0[vozmix]")
    if "musica" in silenciar:
        grafo = grafo.replace("makeup=1[musduck];", "makeup=1,volume=0[musduck];", 1)
    if "efectos" in silenciar:
        grafo = grafo.replace("[sfx];", ",volume=0[sfx];", 1)
    return grafo


def _medida(m):
    """La medida del master con TODAS las pistas (la del video)."""
    if not (m["musica"] or m["efectos"]):
        return None
    return p8_render._medir_mezcla(
        [medios.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "anullsrc=r=48000:cl=stereo"] + _entradas(m)
        + ["-filter_complex", _grafo(m, None, ()), "-map", "[salida]", "-f", "null", "-"])


def _orden_de_audio(m, partes, medida):
    """(args de entradas, args de mapeo) del audio con esas partes."""
    partes = [x for x in partes if m["hay"].get(x)]
    if not partes:
        return [], None
    if not m["hay"]["voz"]:
        raise ErrorExporte("este vídeo no tiene la voz a mano: no se puede rehacer su sonido")
    # el camino corto (la voz tal cual) SOLO si el video no lleva musica ni
    # efectos: con ellos el video pasa por el master, y una voz sin el sonaria
    # ~5 dB por debajo de como suena (y las pistas sueltas no sumarian la mezcla)
    if not (m["musica"] or m["efectos"]):
        if "voz" not in partes:
            return [], None
        filtro = "[1:a]apad,atrim=0:%.3f[salida]" % m["largo_con_cola"]
        return ["-ss", f"{max(0.0, m['desfase']):.3f}", "-i", m["voz"]], filtro
    silenciar = [x for x in PARTES if x not in partes]
    return _entradas(m), _grafo(m, medida, silenciar)


# ------------------------------------------------------------------ la imagen

def _concatenar_sin_audio(clips, destino, trabajo, m):
    clips = p8_render._cola_negra(clips, trabajo, m["fps"], m["calidad"])
    lista = os.path.join(trabajo, "clips.txt")
    with open(lista, "w", encoding="utf-8") as fh:
        for clip in clips:
            fh.write("file '" + clip.replace("\\", "/") + "'\n")
    _ffmpeg([medios.ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lista, "-an", "-c:v", "copy", "-movflags", "+faststart", destino],
            "unir los planos")
    return destino


def _poner_logo(proyecto, ruta, m):
    ficha = m["logo"] if isinstance(m["logo"], dict) else {}
    if not ficha.get("fichero"):
        return ruta
    logo = os.path.join(proyecto.raiz, p8_render.CARPETA_LOGO, os.path.basename(str(ficha["fichero"])))
    if os.path.exists(logo):
        p8_render.poner_logo(ruta, logo, ficha, m["calidad"])
    return ruta


def _planos_sin_subtitulos(proyecto, m, trabajo, avisar, estado=None):
    """Recaptura TODOS los planos con la capa de subtitulos vacia. -> [clips]

    Es el bucle de `p8_render.ejecutar` con dos diferencias: `capa_fija` va
    vacia y todo se escribe en `trabajo` (la carpeta de exportes), nunca en la
    del paso. Todos los planos, en orden: la transicion de cada uno se cuece
    sobre el ultimo fotograma del anterior, y el de la version lleva el
    subtitulo dentro."""
    p = m["params"]
    ruta_mov = medios.salida_de(proyecto, "callouts", claves=("movimiento",),
                                patrones=(r"movimiento\.json",), estado=estado)
    if not ruta_mov:
        raise ErrorExporte("faltan los rótulos del vídeo: vuelve a montarlo")
    base_callouts = os.path.dirname(ruta_mov)
    datos_mov = medios.leer_json(ruta_mov, {}) or {}
    movimientos = {x["id"]: x for x in datos_mov.get("movimientos", []) if x.get("id")}
    escenas = m["escenas"]
    fps = m["fps"]
    cortes = p8_render.transiciones.resolver(escenas, p, semilla=(m["plan"].get("semilla") or 0))
    ancho, alto = [int(v) for v in (m["plan"].get("resolucion") or p["resolucion"])]
    dir_clips = os.path.join(trabajo, "clips")
    dir_ultimo = os.path.join(trabajo, "ultimo")
    dir_frames = os.path.join(trabajo, "frames")
    for ruta in (dir_clips, dir_ultimo, dir_frames):
        shutil.rmtree(ruta, ignore_errors=True)
        os.makedirs(ruta, exist_ok=True)
    pagina = p8_render.transiciones.pagina(os.path.join(trabajo, "transicion.html"),
                                           ancho, alto, datos_mov.get("paleta") or {})
    arranque = time.time()
    clips, tareas = [], []
    for indice, escena in enumerate(escenas):
        sid = escena["id"]
        clip = os.path.join(dir_clips, f"{sid}.mp4")
        clips.append(clip)
        mov = movimientos.get(sid)
        if not mov:
            raise ErrorExporte(f"{sid}: faltan los rótulos de este plano: vuelve a montar el vídeo")
        hyper = mov.get("hyperframe")
        hyper = hyper if hyper and os.path.isabs(hyper) else os.path.join(base_callouts, hyper or "")
        capa = os.path.join(base_callouts, mov.get("capa") or "")
        svg = ""
        if os.path.exists(capa):
            with open(capa, "r", encoding="utf-8") as fh:
                svg = fh.read()
        tareas.append({
            "id": sid, "escena": {"id": sid, "t_in": escena["t_in"], "t_out": escena["t_out"]},
            "mov": {"ventana_ini": mov["ventana_ini"], "ventana_fin": mov["ventana_fin"],
                    "hyperframe_px": mov.get("hyperframe_px")},
            # la cartela y la cabecera se quedan (son contenido); el subtitulo no
            "capa": svg, "capa_fija": "",
            "hyper": hyper,
            "frames": max(1, round(float(escena["t_out"]) * fps) - round(float(escena["t_in"]) * fps)),
            "fps": fps, "resolucion": [ancho, alto], "calidad": p["calidad_video"],
            "carpeta": os.path.join(dir_frames, sid), "clip": clip,
            "ultimo": os.path.join(dir_ultimo, f"{sid}.png"), "desde": arranque,
            "anterior": os.path.join(dir_ultimo, f"{escenas[indice - 1]['id']}.png") if indice else None,
            "previo": escenas[indice - 1]["id"] if indice else None,
            "corte": dict(cortes.get(sid) or {}), "pagina_trans": pagina,
            "conservar_frames": False, "esperar_anterior": bool(indice)})
    lotes = p8_render._repartir_lotes(tareas, p8_render._cuantos_lotes(p, len(tareas)))
    if len(lotes) <= 1:
        avisar(0.05, f"{len(tareas)} planos, sin subtítulos")
        fichas = {f["id"]: f for f in p8_render.correr_lote(lotes[0])}
    else:
        fichas = p8_render._correr_lotes_en_procesos(lotes, trabajo, avisar, len(tareas),
                                                     dir_clips=dir_clips, desde=arranque)
    faltan = [t["id"] for t in tareas if t["id"] not in fichas]
    if faltan:
        raise ErrorExporte(f"no se pudieron capturar {len(faltan)} plano(s): {', '.join(faltan[:6])}")
    shutil.rmtree(dir_frames, ignore_errors=True)
    shutil.rmtree(os.path.join(trabajo, "lotes"), ignore_errors=True)
    return clips


def imagen(proyecto, m, subtitulos=True, logo=True, avisar=None, estado=None):
    """El MP4 SOLO IMAGEN que se pide (con o sin subtitulos y logo). -> ruta"""
    avisar = avisar or (lambda *a, **k: None)
    destino_dir = carpeta_de(proyecto, m)
    nombre = f"imagen_{'sub' if subtitulos else 'nosub'}_{'logo' if logo else 'nologo'}.mp4"
    destino = os.path.join(destino_dir, nombre)
    if os.path.exists(destino):
        return destino
    if subtitulos and logo:
        _ffmpeg([medios.ffmpeg(), "-y", "-loglevel", "error", "-i", m["video"], "-an",
                 "-c:v", "copy", "-movflags", "+faststart", destino], "separar la imagen")
        return destino
    if subtitulos:
        clips = [os.path.join(m["carpeta"], "clips", f"{e['id']}.mp4") for e in m["escenas"]]
        faltan = [os.path.basename(c) for c in clips if not os.path.exists(c)]
        if faltan:
            raise ErrorExporte(f"faltan planos del montaje ({', '.join(faltan[:4])}): vuelve a montar el vídeo")
        trabajo = os.path.join(destino_dir, "_sin_logo")
        os.makedirs(trabajo, exist_ok=True)
        avisar(0.3, "uniendo los planos sin el logo")
        _concatenar_sin_audio(clips, destino + ".tmp.mp4", trabajo, m)
        os.replace(destino + ".tmp.mp4", destino)
        return destino
    trabajo = os.path.join(destino_dir, "_sin_subtitulos")
    os.makedirs(trabajo, exist_ok=True)
    base = os.path.join(trabajo, "imagen.mp4")
    if not os.path.exists(base):
        clips = _planos_sin_subtitulos(proyecto, m, trabajo,
                                       lambda v, msg="", *a: avisar(0.05 + 0.85 * float(v or 0), msg),
                                       estado=estado)
        avisar(0.92, "uniendo los planos")
        _concatenar_sin_audio(clips, base + ".tmp.mp4", trabajo, m)
        os.replace(base + ".tmp.mp4", base)
    shutil.copyfile(base, destino + ".tmp.mp4")
    if logo:
        avisar(0.95, "poniendo el logo")
        _poner_logo(proyecto, destino + ".tmp.mp4", m)
    os.replace(destino + ".tmp.mp4", destino)
    return destino


# ------------------------------------------------------------------ lo que se pide

def _clave(partes, subtitulos, logo):
    return ("-".join(x for x in PARTES if x in partes) or "sin_audio") \
        + ("" if subtitulos else "_sin_subtitulos") + ("" if logo else "_sin_logo")


def video(proyecto, params_render, partes, subtitulos=True, logo=True, avisar=None, estado=None):
    """El MP4 con la imagen y el audio pedidos. -> ruta"""
    avisar = avisar or (lambda *a, **k: None)
    m = material(proyecto, params_render, estado=estado)
    destino = os.path.join(carpeta_de(proyecto, m), f"video_{_clave(partes, subtitulos, logo)}.mp4")
    if os.path.exists(destino):
        return destino
    base = imagen(proyecto, m, subtitulos=subtitulos, logo=logo, avisar=avisar, estado=estado)
    avisar(0.96, "mezclando el sonido elegido")
    entradas, filtro = _orden_de_audio(m, list(partes), _medida(m) if partes else None)
    orden = [medios.ffmpeg(), "-y", "-loglevel", "error", "-i", base] + entradas
    if filtro:
        orden += ["-filter_complex", filtro, "-map", "0:v", "-map", "[salida]",
                  "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
    else:
        orden += ["-map", "0:v", "-c:v", "copy", "-an"]
    orden += ["-movflags", "+faststart", destino + ".tmp.mp4"]
    _ffmpeg(orden, "montar el vídeo con ese sonido")
    os.replace(destino + ".tmp.mp4", destino)
    return destino


def audio(proyecto, params_render, parte, avisar=None, estado=None):
    """Un audio suelto (WAV): voz, musica, efectos o mezcla. -> ruta

    Voz, musica y efectos salen COMO SUENAN EN EL VIDEO (la musica agachada
    bajo la voz, los efectos a su volumen), del largo del video y alineados en
    el segundo cero: puestos juntos en otro editor suman la mezcla."""
    if parte not in PARTES + ("mezcla",):
        raise ErrorExporte("parte desconocida: voz, musica, efectos o mezcla")
    m = material(proyecto, params_render, estado=estado)
    if parte != "mezcla" and not m["hay"].get(parte):
        raise ErrorExporte({"voz": "este vídeo no tiene voz a mano",
                            "musica": "este vídeo no lleva música",
                            "efectos": "este vídeo no lleva efectos"}[parte])
    destino = os.path.join(carpeta_de(proyecto, m), f"{parte}.wav")
    if os.path.exists(destino):
        return destino
    partes = list(PARTES) if parte == "mezcla" else [parte]
    entradas, filtro = _orden_de_audio(m, partes, _medida(m))
    if not filtro:
        raise ErrorExporte("no hay nada que sacar de ese audio")
    orden = [medios.ffmpeg(), "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "anullsrc=r=48000:cl=stereo"] + entradas + [
        "-filter_complex", filtro, "-map", "[salida]", "-t", f"{m['largo_con_cola']:.3f}",
        "-c:a", "pcm_s16le", destino + ".tmp.wav"]
    _ffmpeg(orden, f"sacar el audio de {parte}")
    os.replace(destino + ".tmp.wav", destino)
    return destino


def todo_por_partes(proyecto, params_render, avisar=None, estado=None):
    """Un ZIP con la imagen (con subtitulos, sin sonido) y cada audio suelto."""
    import zipfile                                         # noqa: PLC0415
    avisar = avisar or (lambda *a, **k: None)
    m = material(proyecto, params_render, estado=estado)
    destino = os.path.join(carpeta_de(proyecto, m), "por_partes.zip")
    if os.path.exists(destino):
        return destino
    piezas = [("imagen.mp4", imagen(proyecto, m, avisar=avisar, estado=estado))]
    for i, parte in enumerate([x for x in PARTES if m["hay"].get(x)] + ["mezcla"]):
        avisar(0.3 + 0.15 * i, f"sacando {parte}")
        piezas.append((f"{parte}.wav", audio(proyecto, params_render, parte, estado=estado)))
    with zipfile.ZipFile(destino + ".tmp", "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, ruta in piezas:
            z.write(ruta, nombre)
        z.writestr("LEEME.txt", (
            "Las partes del vídeo, del mismo largo y alineadas en el segundo 0.\n"
            "imagen.mp4: la imagen con subtítulos y logo, sin sonido.\n"
            "voz.wav, musica.wav, efectos.wav: cada pista como suena en el vídeo\n"
            "(la música ya agachada bajo la voz). Juntas suman mezcla.wav.\n"))
    os.replace(destino + ".tmp", destino)
    return destino


def nombre_descarga(nombre_video, fichero):
    base = "".join(c if c.isalnum() or c in " -_" else "_" for c in str(nombre_video or "video")).strip() or "video"
    return f"{base} - {os.path.basename(fichero)}"

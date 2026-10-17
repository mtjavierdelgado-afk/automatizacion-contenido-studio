"""Un Upload-Post de mentira, con la misma cara que `ClienteUploadPost`.

Para las pruebas y para el recorrido: nadie publica nada ni gasta una subida
del mes. Se enciende con `ESTUDIO_UPLOADPOST_SIMULADO` (una ruta de fichero, o
«1» para la de por defecto en la carpeta temporal) y lo elige
`pasos/publicar.py`; no hace falta ninguna clave.

Guarda lo que pasa en un JSON para que dos procesos (la prueba y el Studio que
arranca) vean lo mismo:

    {"perfiles": {nombre: {red: {...}|None}},
     "subidas": [{id, perfil, redes, campos, cuando, zona, fichero, bytes}],
     "trabajos": {id: {"redes": [...], "cuando_utc": iso|null, "consultas": n,
                        "cancelado": bool}},
     "fallar": {red: "motivo"}}          <- la prueba lo escribe para simular
                                            que una red no acepta el video

Lo que imita: una subida «ya» contesta con `request_id` y la primera consulta
dice «procesando», la segunda «publicado» con su enlace; una programada
contesta con `job_id` y sigue «programado» hasta que pasa su hora.
"""
import datetime as dt
import json
import os
import tempfile
import threading
import uuid

try:
    from .cliente import REDES, ErrorUploadPost, ClienteUploadPost
except ImportError:                                     # cargado suelto
    from cliente import REDES, ErrorUploadPost, ClienteUploadPost  # noqa: F401

_LOCK = threading.Lock()


def ruta_por_defecto():
    return os.path.join(tempfile.gettempdir(), "estudio_uploadpost_simulado.json")


def _zona(nombre):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nombre)
    except Exception:                                   # noqa: BLE001
        return dt.timezone(dt.timedelta(hours=-5))      # Lima no cambia de hora


class SimuladoUploadPost:
    simulado = True

    def __init__(self, ruta=None):
        valor = ruta or os.environ.get("ESTUDIO_UPLOADPOST_SIMULADO") or ""
        self.ruta = ruta_por_defecto() if valor in ("", "1", "si", "true") else valor

    # ----------------------------------------------------------- almacen

    def _leer(self):
        try:
            with open(self.ruta, encoding="utf-8") as fh:
                datos = json.load(fh)
        except (OSError, ValueError):
            datos = {}
        datos.setdefault("perfiles", {})
        datos.setdefault("subidas", [])
        datos.setdefault("trabajos", {})
        datos.setdefault("fallar", {})
        return datos

    def _escribir(self, datos):
        carpeta = os.path.dirname(self.ruta) or "."
        os.makedirs(carpeta, exist_ok=True)
        temporal = f"{self.ruta}.{uuid.uuid4().hex}.tmp"
        with open(temporal, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=1)
        os.replace(temporal, self.ruta)

    # ------------------------------------------------------------ cuenta

    def probar(self):
        return {"ok": True, "email": "simulado@estudio.local", "plan": "simulado"}

    def perfiles(self):
        with _LOCK:
            datos = self._leer()
        return {"perfiles": [{"perfil": p, "cuentas": ClienteUploadPost._cuentas(c)}
                             for p, c in sorted(datos["perfiles"].items())],
                "limite": datos.get("limite") or 25, "plan": "simulado"}

    def crear_perfil(self, perfil):
        with _LOCK:
            datos = self._leer()
            if perfil in datos["perfiles"]:
                raise ErrorUploadPost("ese perfil ya existe en Upload-Post", 409)
            # el plan lleno, con el mensaje de alli (16-10-2026, plan gratis 2/2)
            limite = datos.get("limite") or 25
            if len(datos["perfiles"]) >= limite:
                raise ErrorUploadPost(f"You have reached the limit of {limite} profiles "
                                      "for your plan", 403)
            datos["perfiles"][perfil] = {}
            self._escribir(datos)
        return {"perfil": perfil, "cuentas": ClienteUploadPost._cuentas({})}

    def enlace_conectar(self, perfil, redes=None, volver_a=None):
        """Como si el cliente hubiera entrado al enlace y conectado todo."""
        with _LOCK:
            datos = self._leer()
            if perfil not in datos["perfiles"]:
                raise ErrorUploadPost("Upload-Post no encuentra ese perfil", 404)
            for red in (redes or REDES):
                datos["perfiles"][perfil][red] = {
                    "display_name": f"{perfil} en {red}", "username": f"@{perfil}",
                    "social_images": ""}
            self._escribir(datos)
        return {"url": f"https://app.upload-post.com/connect?token=SIMULADO-{perfil}",
                "caduca": "48h"}

    # ---------------------------------------------------------- publicar

    def publicar(self, perfil, redes, mp4, campos, cuando=None, zona="America/Lima",
                 id_propio=None, ficheros=None):
        redes = [r for r in redes if r in REDES]
        if not redes:
            raise ErrorUploadPost("no hay ninguna red que publicar", 400)
        if not os.path.isfile(mp4):
            raise ErrorUploadPost("no encuentro el MP4 del vídeo")
        id_propio = id_propio or uuid.uuid4().hex
        with _LOCK:
            datos = self._leer()
            cuentas = datos["perfiles"].get(perfil)
            if cuentas is None:
                raise ErrorUploadPost("Upload-Post no encuentra ese perfil", 404)
            # la misma clave de idempotencia devuelve el mismo trabajo
            if id_propio in datos["trabajos"]:
                ya = datos["trabajos"][id_propio]
                return {"modo": "programado" if ya.get("cuando_utc") else "en_cola",
                        "request_id": id_propio,
                        "job_id": id_propio if ya.get("cuando_utc") else "",
                        "programado_para": ya.get("cuando_utc") or "",
                        "resultados": {}, "avisos": []}
            cuando_utc = None
            if cuando:
                local = dt.datetime.fromisoformat(cuando).replace(tzinfo=_zona(zona))
                cuando_utc = local.astimezone(dt.timezone.utc).isoformat()
            datos["subidas"].append({
                "id": id_propio, "perfil": perfil, "redes": redes,
                "campos": campos, "cuando": cuando, "zona": zona,
                "fichero": os.path.basename(mp4), "bytes": os.path.getsize(mp4),
                "imagenes": {c: os.path.getsize(r) for c, r in (ficheros or [])
                             if r and os.path.isfile(r)}})
            datos["trabajos"][id_propio] = {
                "perfil": perfil, "redes": redes, "cuando_utc": cuando_utc, "consultas": 0,
                "cancelado": False,
                "sin_cuenta": [r for r in redes if not cuentas.get(r)]}
            self._escribir(datos)
        return {"modo": "programado" if cuando_utc else "en_cola",
                "request_id": id_propio, "job_id": id_propio if cuando_utc else "",
                "programado_para": cuando_utc or "", "resultados": {}, "avisos": []}

    def estado(self, request_id=None, job_id=None):
        clave = job_id or request_id
        with _LOCK:
            datos = self._leer()
            trabajo = datos["trabajos"].get(clave)
            if trabajo is None:
                raise ErrorUploadPost("Upload-Post no encuentra ese envío", 404)
            if trabajo.get("cancelado"):
                return {"estado": "cancelled", "redes": {}, "mensaje": "cancelado"}
            ahora = dt.datetime.now(dt.timezone.utc)
            if trabajo.get("cuando_utc") and dt.datetime.fromisoformat(
                    trabajo["cuando_utc"]) > ahora:
                return {"estado": "scheduled",
                        "redes": {r: {"estado": "programado", "url": "", "error": ""}
                                  for r in trabajo["redes"]}, "mensaje": ""}
            trabajo["consultas"] = int(trabajo.get("consultas") or 0) + 1
            self._escribir(datos)
            if trabajo["consultas"] < 2:
                return {"estado": "processing",
                        "redes": {r: {"estado": "procesando", "url": "", "error": ""}
                                  for r in trabajo["redes"]}, "mensaje": ""}
            redes = {}
            for red in trabajo["redes"]:
                if red in trabajo.get("sin_cuenta", []):
                    redes[red] = {"estado": "fallido", "url": "",
                                  "error": "profile_platform_not_configured"}
                elif datos["fallar"].get(red):
                    redes[red] = {"estado": "fallido", "url": "",
                                  "error": str(datos["fallar"][red])}
                else:
                    redes[red] = {"estado": "publicado", "error": "",
                                  "url": f"https://{red}.example/{clave[:10]}"}
            return {"estado": "completed", "redes": redes, "mensaje": ""}

    def cancelar(self, job_id):
        with _LOCK:
            datos = self._leer()
            trabajo = datos["trabajos"].get(job_id)
            if trabajo is None:
                raise ErrorUploadPost("Upload-Post no encuentra ese envío", 404)
            trabajo["cancelado"] = True
            self._escribir(datos)
        return {"ok": True}

    # ------------------------------------------------------------- metricas

    @staticmethod
    def _semilla(*partes):
        import hashlib
        return int(hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()[:8], 16)

    def metricas_post(self, request_id, red=None):
        """Cifras que crecen con cada consulta, y TikTok que aun no las tiene la
        primera vez (como pasa en las horas despues de publicar). TikTok trae su
        retencion en vivo; YouTube no (solo en la lectura guardada). Cada lectura
        en vivo queda guardada, como hace Upload-Post."""
        with _LOCK:
            datos = self._leer()
            trabajo = datos["trabajos"].get(request_id)
            if trabajo is None:
                raise ErrorUploadPost("Upload-Post no encuentra ese envío", 404)
            trabajo["metricas_consultas"] = int(trabajo.get("metricas_consultas") or 0) + 1
            vueltas = trabajo["metricas_consultas"]
            salida = {}
            for r in trabajo["redes"]:
                if red and r != red:
                    continue
                base = self._semilla(request_id, r) % 900 + 100
                post_id = f"{r[:2]}{self._semilla(request_id, r, 'id') % 10**9}"
                if r == "tiktok" and vueltas < 2:
                    salida[r] = {k: None for k in ClienteUploadPost.CAMPOS_METRICAS}
                    salida[r].update(url=f"https://{r}.example/{request_id[:10]}", post_id=post_id,
                                     vista_entera=None, media_vista=None, tiempo_medio_s=None,
                                     error="TikTok todavía no tiene las cifras de este post")
                    continue
                salida[r] = {"vistas": base * vueltas, "me_gusta": base // 10 * vueltas,
                             "comentarios": base // 100 + vueltas, "compartidos": base // 50,
                             "guardados": None if r == "youtube" else base // 40, "alcance": None,
                             "vista_entera": round((base % 40 + 10) / 100, 4) if r == "tiktok" else None,
                             "media_vista": None,
                             "tiempo_medio_s": float(base % 20 + 3) if r == "tiktok" else None,
                             "url": f"https://{r}.example/{request_id[:10]}", "post_id": post_id,
                             "error": ""}
                guardadas = trabajo.setdefault("guardadas", {})
                guardadas[r] = dict(salida[r], al=dt.datetime.now(dt.timezone.utc).isoformat())
            self._escribir(datos)
        return salida

    def metricas_guardadas(self, perfil, red=None, desde=None, hasta=None, paginas=3, plazo=None):
        """Lo ultimo leido en vivo de cada post del perfil. YouTube trae aqui su
        retencion (como el informe de YouTube Analytics de Upload-Post)."""
        with _LOCK:
            datos = self._leer()
        if perfil not in datos["perfiles"]:
            raise ErrorUploadPost("Upload-Post no encuentra ese perfil", 404)
        posts = []
        for rid, trabajo in datos["trabajos"].items():
            if trabajo.get("perfil") != perfil:
                continue
            for r, guardada in (trabajo.get("guardadas") or {}).items():
                if red and r != red:
                    continue
                item = dict(guardada, red=r)
                item.pop("error", None)
                if r == "youtube":
                    # la retencion de YouTube cambia con cada lectura, como la real
                    base = self._semilla(rid, r) % 900 + 100
                    vueltas = int(trabajo.get("metricas_consultas") or 1)
                    item.update(media_vista=round((base % 50 + 20 + vueltas) / 100, 4),
                                tiempo_medio_s=float(base % 40 + 10 + vueltas))
                posts.append(item)
        return {"posts": posts, "completo": True}

    def analiticas_perfil(self, perfil, redes, pagina_facebook=None):
        with _LOCK:
            datos = self._leer()
        if perfil not in datos["perfiles"]:
            raise ErrorUploadPost("Upload-Post no encuentra ese perfil", 404)
        salida = {}
        for r in redes:
            if r == "facebook" and not pagina_facebook:
                salida[r] = {"seguidores": None, "alcance": None, "vistas": None,
                             "error": "Facebook pide el id de la página"}
                continue
            base = self._semilla(perfil, r) % 5000 + 200
            salida[r] = {"seguidores": base, "alcance": base * 3, "vistas": base * 5, "error": ""}
        return salida


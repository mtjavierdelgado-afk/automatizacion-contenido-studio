"""El cliente de Upload-Post: subir un video a varias redes, programarlo y seguirlo.

    cli = ClienteUploadPost(clave)
    cli.probar()                                   -> {"ok", "email", "plan"}
    cli.perfiles()                                 -> [{"perfil", "cuentas": {red: {...}|None}}]
    cli.crear_perfil("cliente_x")                  -> {"perfil", "cuentas"}
    cli.enlace_conectar("cliente_x", redes=[...])  -> {"url", "caduca"}
    cli.publicar(perfil, redes, mp4, campos, cuando=None, zona=..., id_propio=...)
                                                   -> {"modo", "request_id"|"job_id", "resultados"}
    cli.estado(request_id=..., job_id=...)         -> {"estado", "redes": {red: {...}}}
    cli.cancelar(job_id)                           -> {"ok"}
    cli.metricas_post(request_id)                  -> {red: {"vistas", "me_gusta", ..., "error"}}
    cli.metricas_guardadas(perfil)                 -> {"posts": [{red, post_id, url, al, cifras}], "completo"}
    cli.analiticas_perfil(perfil, redes)           -> {red: {"seguidores", "alcance", "vistas", "error"}}

Por que un intermediario
------------------------
Las APIs propias de TikTok y de YouTube piden una auditoria de semanas antes de
dejar publicar en publico, y los robots de navegador se rompen con cada cambio
de pantalla. Upload-Post ya esta auditado en las cuatro redes y cobra por
PERFIL (un perfil = un cliente, con una cuenta por red), que es como se cuenta
aqui el trabajo. Decidido por el dueño el 13-10-2026 (ver el documento
`estado/redes_parrilla_publicar_2026-10-15.md` del Proyecto).

Lo que este modulo NO hace
--------------------------
- **No lee claves de ningun sitio.** La clave llega como argumento; de donde
  sale (el almacen, el .env) lo decide `pasos/publicar.py`. Un motor no importa
  codigo de la aplicacion (motores/README.md).
- **No reintenta una subida.** Si la conexion se corta a mitad, Upload-Post
  puede haberla recibido igual: reenviar publicaria el video DOS veces en la
  red de un cliente. Cada subida lleva un `Idempotency-Key` propio y lo que
  queda es preguntar por su estado (la documentacion de Upload-Post dice lo
  mismo: «si tu cliente HTTP vence, no reenvies; pregunta con tu request_id»).
- **Nunca pone la clave en un mensaje de error.** Ni la cabecera ni nada que
  el servicio devuelva con ella dentro (`_tachar`).

Solo biblioteca estandar: el video se sube en streaming (`_Multipart`), sin
cargarlo entero en memoria, para que un video de treinta minutos no sean
cientos de megas de RAM en el VPS.
"""
import http.client
import io
import json
import mimetypes
import os
import re
import ssl
import uuid
import urllib.error
import urllib.parse
import urllib.request

BASE_POR_DEFECTO = "https://api.upload-post.com"

#: Las redes que el Studio sabe publicar hoy, con el nombre que les da
#: Upload-Post. El orden es el de la pantalla.
REDES = ("tiktok", "instagram", "youtube", "facebook")

#: Para hablar con Upload-Post. La subida en si puede tardar: un MP4 de 200 MB
#: por la linea del VPS son minutos, y el plazo es por operacion de socket, no
#: total, asi que un plazo largo no bloquea nada que no este ya esperando.
PLAZO_CONSULTA_S = 30
PLAZO_SUBIDA_S = 300


class ErrorUploadPost(RuntimeError):
    """Upload-Post dijo que no, o no contesto. El mensaje es para una persona.

    `codigo` es el HTTP (0 si no hubo respuesta) y `sin_respuesta` dice si la
    peticion pudo llegar y no sabemos que paso: en una subida eso NO se reintenta.
    """

    def __init__(self, mensaje, codigo=0, cuerpo=None, sin_respuesta=False):
        super().__init__(mensaje)
        self.codigo = int(codigo or 0)
        self.cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
        self.sin_respuesta = bool(sin_respuesta)


# ------------------------------------------------------------------ utilidades

def _tachar(texto, clave):
    """El texto sin la clave (entera o casi): nunca sale por un error."""
    texto = str(texto or "")
    clave = str(clave or "")
    if len(clave) >= 6:
        texto = texto.replace(clave, "…")
    # y cualquier «Apikey xxxx» que el servicio repita en su mensaje
    return re.sub(r"(?i)(apikey|bearer)\s+[A-Za-z0-9._\-]{8,}", r"\1 …", texto)


def _mensaje_de(cuerpo, codigo):
    cuerpo = cuerpo if isinstance(cuerpo, dict) else {}
    texto = (cuerpo.get("message") or cuerpo.get("error") or cuerpo.get("detail")
             or "")
    if isinstance(texto, (dict, list)):
        texto = json.dumps(texto, ensure_ascii=False)[:300]
    texto = " ".join(str(texto).split())[:400]
    por_codigo = {
        401: "Upload-Post no acepta la clave (no es válida o ha caducado)",
        403: "tu plan de Upload-Post no permite esto",
        404: "Upload-Post no encuentra lo pedido",
        429: "has llegado al límite de subidas de este mes en Upload-Post",
    }
    base = por_codigo.get(int(codigo or 0), f"Upload-Post contestó {codigo}")
    return f"{base}: {texto}" if texto else base


class _Multipart:
    """Un cuerpo multipart/form-data que se lee por trozos (streaming).

    Los campos de texto van en memoria; el fichero se lee del disco a medida
    que http.client lo pide. Sabe su longitud antes de empezar, que es lo que
    hace falta para mandar `Content-Length` y no partir la subida en chunks
    (algunos proxys no los aceptan)."""

    def __init__(self, campos, ficheros):
        self.limite = f"----estudio{uuid.uuid4().hex}"
        self._partes = []          # bytes o (ruta, tamano)
        for nombre, valor in campos:
            self._partes.append(
                (f"--{self.limite}\r\n"
                 f'Content-Disposition: form-data; name="{nombre}"\r\n\r\n'
                 f"{valor}\r\n").encode("utf-8"))
        for nombre, ruta in ficheros:
            tipo = mimetypes.guess_type(ruta)[0] or "application/octet-stream"
            base = os.path.basename(ruta).replace('"', "")
            self._partes.append(
                (f"--{self.limite}\r\n"
                 f'Content-Disposition: form-data; name="{nombre}"; filename="{base}"\r\n'
                 f"Content-Type: {tipo}\r\n\r\n").encode("utf-8"))
            self._partes.append((ruta, os.path.getsize(ruta)))
            self._partes.append(b"\r\n")
        self._partes.append(f"--{self.limite}--\r\n".encode("utf-8"))
        self.longitud = sum(len(p) if isinstance(p, bytes) else p[1]
                            for p in self._partes)
        self._indice = 0
        self._actual = None

    @property
    def tipo(self):
        return f"multipart/form-data; boundary={self.limite}"

    def read(self, n=-1):
        n = 65536 if n is None or n < 0 else n
        while self._indice < len(self._partes):
            if self._actual is None:
                parte = self._partes[self._indice]
                self._actual = (io.BytesIO(parte) if isinstance(parte, bytes)
                                else open(parte[0], "rb"))
            trozo = self._actual.read(n)
            if trozo:
                return trozo
            self._actual.close()
            self._actual = None
            self._indice += 1
        return b""

    def cerrar(self):
        if self._actual is not None:
            self._actual.close()
            self._actual = None


# ---------------------------------------------------------------------- cliente

class ClienteUploadPost:
    """Habla con la API de Upload-Post. Cada metodo es una llamada."""

    simulado = False

    def __init__(self, clave, base=None):
        self.clave = str(clave or "").strip()
        if not self.clave:
            raise ErrorUploadPost("falta la clave de Upload-Post")
        self.base = (base or os.environ.get("UPLOADPOST_URL")
                     or BASE_POR_DEFECTO).rstrip("/")

    # ------------------------------------------------------------- transporte

    def _contexto_tls(self):
        try:
            return ssl.create_default_context()
        except Exception:                                   # noqa: BLE001
            return None

    def _pedir(self, metodo, ruta, cuerpo=None, consulta=None, cabeceras=None,
               multipart=None, plazo=PLAZO_CONSULTA_S):
        url = f"{self.base}{ruta}"
        if consulta:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in consulta.items() if v not in (None, "")})
        datos = None
        todas = {"Authorization": f"Apikey {self.clave}",
                 "Accept": "application/json",
                 "User-Agent": "AutomatizacionContenidoStudio/2.0"}
        todas.update(cabeceras or {})
        if multipart is not None:
            datos = multipart
            todas["Content-Type"] = multipart.tipo
            todas["Content-Length"] = str(multipart.longitud)
        elif cuerpo is not None:
            datos = json.dumps(cuerpo).encode("utf-8")
            todas["Content-Type"] = "application/json"
        peticion = urllib.request.Request(url, data=datos, headers=todas,
                                          method=metodo)
        contexto = self._contexto_tls() if url.startswith("https") else None
        try:
            with urllib.request.urlopen(peticion, timeout=plazo,
                                        context=contexto) as resp:
                crudo = resp.read()
                codigo = resp.status
        except urllib.error.HTTPError as fallo:
            crudo = fallo.read() if hasattr(fallo, "read") else b""
            try:
                cuerpo_error = json.loads(crudo.decode("utf-8", "replace") or "{}")
            except ValueError:
                cuerpo_error = {"message": crudo.decode("utf-8", "replace")[:300]}
            # UN 5xx NO DICE QUE NO HAYA LLEGADO: el servidor (o el Cloudflare de
            # delante, con su 524 a los ~100 s) puede haber recibido el video y
            # seguir procesandolo. Para una subida eso es «no se sabe», nunca
            # «fallo»: reenviar podria publicarlo dos veces.
            raise ErrorUploadPost(_tachar(_mensaje_de(cuerpo_error, fallo.code), self.clave),
                                  fallo.code, cuerpo_error,
                                  sin_respuesta=fallo.code >= 500) from None
        except (urllib.error.URLError, OSError, TimeoutError,
                http.client.HTTPException) as fallo:
            motivo = getattr(fallo, "reason", fallo)
            raise ErrorUploadPost(
                _tachar(f"Upload-Post no contesta ({motivo})", self.clave),
                sin_respuesta=True) from None
        finally:
            if multipart is not None:
                multipart.cerrar()
        try:
            respuesta = json.loads(crudo.decode("utf-8", "replace") or "{}")
        except ValueError:
            raise ErrorUploadPost("Upload-Post devolvió algo que no es JSON",
                                  codigo, sin_respuesta=True) from None
        if isinstance(respuesta, dict) and respuesta.get("success") is False:
            raise ErrorUploadPost(_tachar(_mensaje_de(respuesta, codigo), self.clave),
                                  codigo, respuesta)
        return respuesta if isinstance(respuesta, dict) else {"datos": respuesta}

    # ------------------------------------------------------------------ cuenta

    def probar(self):
        """Comprueba la clave sin gastar ninguna subida."""
        r = self._pedir("GET", "/api/uploadposts/me")
        cuenta = r.get("account") if isinstance(r.get("account"), dict) else r
        return {"ok": True,
                "email": str(cuenta.get("email") or ""),
                "plan": str(cuenta.get("plan") or cuenta.get("subscription_plan")
                            or cuenta.get("subscription") or "")}

    @staticmethod
    def _cuentas(sociales):
        """{red: {"nombre", "usuario", "foto", "reconectar"} o None}."""
        salida = {}
        sociales = sociales if isinstance(sociales, dict) else {}
        for red in REDES:
            valor = sociales.get(red)
            if isinstance(valor, dict) and valor:
                salida[red] = {
                    "nombre": str(valor.get("display_name") or valor.get("username")
                                  or valor.get("handle") or red),
                    "usuario": str(valor.get("username") or valor.get("handle") or ""),
                    "foto": str(valor.get("social_images") or ""),
                    "reconectar": bool(valor.get("reauth_required")),
                }
            elif isinstance(valor, str) and valor.strip():
                # alguna respuesta vieja trae un texto en vez de la ficha
                salida[red] = {"nombre": valor.strip(), "usuario": "", "foto": "",
                               "reconectar": False}
            else:
                salida[red] = None
        return salida

    def perfiles(self):
        r = self._pedir("GET", "/api/uploadposts/users")
        salida = []
        for p in r.get("profiles") or []:
            if isinstance(p, dict) and p.get("username"):
                salida.append({"perfil": str(p["username"]),
                               "cuentas": self._cuentas(p.get("social_accounts"))})
        return {"perfiles": salida, "limite": r.get("limit"), "plan": r.get("plan") or ""}

    def crear_perfil(self, perfil):
        r = self._pedir("POST", "/api/uploadposts/users", cuerpo={"username": perfil})
        ficha = r.get("profile") if isinstance(r.get("profile"), dict) else {}
        return {"perfil": str(ficha.get("username") or perfil),
                "cuentas": self._cuentas(ficha.get("social_accounts"))}

    def enlace_conectar(self, perfil, redes=None, volver_a=None):
        """El enlace (48 h) donde el cliente conecta o reconecta sus cuentas."""
        cuerpo = {"username": perfil}
        if redes:
            cuerpo["platforms"] = [r for r in redes if r in REDES]
        if volver_a:
            cuerpo["redirect_url"] = volver_a
            cuerpo["redirect_button_text"] = "Volver al Studio"
        r = self._pedir("POST", "/api/uploadposts/users/generate-jwt", cuerpo=cuerpo)
        url = str(r.get("access_url") or "")
        if not url.startswith("https://"):
            raise ErrorUploadPost("Upload-Post no ha devuelto el enlace para conectar")
        return {"url": url, "caduca": str(r.get("duration") or "")}

    # ---------------------------------------------------------------- publicar

    def publicar(self, perfil, redes, mp4, campos, cuando=None, zona="America/Lima",
                 id_propio=None, ficheros=None):
        """Sube el MP4 a las redes pedidas, ya o programado.

        `campos` son los campos de formulario de Upload-Post tal cual
        (tiktok_title, youtube_description, tags[] en lista...): los arma
        `pasos/publicar.py`, que es quien sabe de textos. `cuando` es
        «AAAA-MM-DDTHH:MM:SS» en la hora de `zona`; sin el, se sube ya en
        segundo plano y se sigue con `estado(request_id=...)`. `ficheros` son
        las imagenes de portada: [(campo, ruta)] (cover_image, thumbnail...).
        """
        redes = [r for r in redes if r in REDES]
        if not redes:
            raise ErrorUploadPost("no hay ninguna red que publicar")
        if not os.path.isfile(mp4):
            raise ErrorUploadPost("no encuentro el MP4 del vídeo")
        id_propio = id_propio or uuid.uuid4().hex
        pares = [("user", perfil)] + [("platform[]", r) for r in redes]
        for nombre, valor in (campos or {}).items():
            if isinstance(valor, (list, tuple)):
                pares.extend((nombre, str(v)) for v in valor)
            elif isinstance(valor, bool):
                pares.append((nombre, "true" if valor else "false"))
            elif valor not in (None, ""):
                pares.append((nombre, str(valor)))
        if cuando:
            pares += [("scheduled_date", cuando), ("timezone", zona)]
        else:
            pares.append(("async_upload", "true"))
        pares += [("request_id", id_propio), ("external_id", id_propio)]
        extra = [(c, r) for c, r in (ficheros or []) if r and os.path.isfile(r)]
        cuerpo = _Multipart(pares, [("video", mp4)] + extra)
        r = self._pedir("POST", "/api/upload", multipart=cuerpo,
                        cabeceras={"Idempotency-Key": id_propio},
                        plazo=PLAZO_SUBIDA_S)
        # EL MODO LO DICE LO PEDIDO, no la respuesta: una subida de mas de 59 s
        # pasa a segundo plano aunque fuera programada, y vuelve con request_id
        # y sin job_id (el job_id llega despues, al preguntar por su estado).
        return {
            "modo": "programado" if cuando else (
                "en_cola" if r.get("request_id") else "hecho"),
            "request_id": str(r.get("request_id") or id_propio),
            "job_id": str(r.get("job_id") or ""),
            "programado_para": str(r.get("scheduled_date") or ""),
            "resultados": self._resultados(r.get("results")),
            "avisos": [str(a)[:300] for a in (r.get("warnings") or [])][:10],
        }

    @staticmethod
    def _resultados(resultados):
        """{red: {"estado", "url", "error"}} desde cualquiera de las dos formas
        que usa Upload-Post (dict por red en la subida, lista en el estado)."""
        salida = {}
        if isinstance(resultados, dict):
            filas = [dict(v, platform=k) for k, v in resultados.items()
                     if isinstance(v, dict)]
        elif isinstance(resultados, list):
            filas = [f for f in resultados if isinstance(f, dict)]
        else:
            filas = []
        for f in filas:
            red = str(f.get("platform") or "")
            if not red:
                continue
            estado = str(f.get("status") or "").lower()
            if f.get("skipped"):
                estado = "fallido"
            elif not estado:
                if f.get("success") is True:
                    estado = "publicado"
                elif f.get("success") is False:
                    estado = "fallido"
                else:
                    estado = "procesando"
            estado = {"completed": "publicado", "success": "publicado",
                      "failed": "fallido", "skipped": "fallido",
                      "queued": "procesando", "processing": "procesando",
                      "in_progress": "procesando", "pending": "procesando",
                      "retryable": "procesando"}.get(estado, estado)
            url = str(f.get("url") or f.get("post_url") or "")
            if not url.startswith("http"):
                url = ""
            error = ""
            if estado == "fallido":
                error = str(f.get("error") or f.get("message") or f.get("skip_reason")
                            or "la red no lo aceptó")[:400]
            salida[red] = {"estado": estado, "url": url, "error": error}
        return salida

    def estado(self, request_id=None, job_id=None):
        r = self._pedir("GET", "/api/uploadposts/status",
                        consulta={"request_id": request_id, "job_id": job_id})
        general = str(r.get("status") or "").lower()
        return {"estado": general, "redes": self._resultados(r.get("results")),
                "job_id": str(r.get("job_id") or ""),
                "mensaje": str(r.get("message") or "")[:300]}

    def cancelar(self, job_id):
        self._pedir("DELETE", f"/api/uploadposts/schedule/{urllib.parse.quote(str(job_id))}")
        return {"ok": True}

    # ------------------------------------------------------------- metricas
    #
    # Lo que cada red cuenta de un post y de una cuenta. Upload-Post las pide en
    # vivo a la red (100 consultas cada 5 minutos por cuenta): quien llama se
    # encarga de no pedir lo mismo dos veces seguidas. Cada red trae los campos
    # que trae: lo que no viene se queda en None, no en 0 (no es lo mismo «no
    # lo dice» que «nadie lo ha visto»).

    #: nombre en el Studio -> nombres posibles en la respuesta de Upload-Post
    CAMPOS_METRICAS = {
        # NO «impressions»: en Facebook son impresiones, no reproducciones
        "vistas": ("views", "video_views", "plays"),
        "me_gusta": ("likes", "like_count", "reactions"),
        "comentarios": ("comments", "comment_count"),
        "compartidos": ("shares", "share_count"),
        "guardados": ("saves", "saved", "favorites"),
        "alcance": ("reach",),
    }

    #: LA RETENCION (publicar-redes-2, 17-10-2026). Son DOS medidas distintas y
    #: van en campos distintos, porque no se pueden comparar ni promediar juntas:
    #:   - `vista_entera`: la FRACCION de quien vio el video HASTA EL FINAL. La da
    #:     TikTok (`full_video_watched_rate`, ya en fraccion: 0,184 = 18,4 %).
    #:   - `media_vista`: QUE PARTE del video se ve de media. La da YouTube solo en
    #:     la lectura guardada (`average_view_percentage`, en tanto por cien), y en
    #:     un Short pasa del 100 % cuando se vuelve a ver: se guarda tal cual (1,3).
    #: Instagram y Facebook no dan ninguna: se quedan en None.
    CAMPOS_FRACCION = ("full_video_watched_rate",)
    CAMPOS_PORCENTAJE = ("average_view_percentage",)
    CAMPOS_TIEMPO_MEDIO = ("average_time_watched", "average_view_duration_seconds")
    #: Mas de 10 veces el video de media no es una cifra, es un error
    TOPE_MEDIA_VISTA = 10.0

    @staticmethod
    def _numero(valor):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            try:
                valor = float(str(valor).strip()) if isinstance(valor, str) and valor.strip() else None
            except ValueError:
                return None
        if valor is None or valor != valor or valor in (float("inf"), float("-inf")):
            return None
        return float(valor)

    @classmethod
    def _retencion(cls, bruto):
        """{"vista_entera": fraccion|None, "media_vista": fraccion|None,
        "tiempo_medio_s": s|None}"""
        bruto = bruto if isinstance(bruto, dict) else {}
        entera = None
        for suyo in cls.CAMPOS_FRACCION:
            v = cls._numero(bruto.get(suyo))
            if v is None:
                continue
            if v > 1:                      # una fraccion que llega como «18.4»
                v = v / 100
            if 0 <= v <= 1:
                entera = round(v, 4)
                break
        media = None
        for suyo in cls.CAMPOS_PORCENTAJE:
            v = cls._numero(bruto.get(suyo))
            if v is not None and 0 <= v / 100 <= cls.TOPE_MEDIA_VISTA:
                media = round(v / 100, 4)
                break
        medio = None
        for suyo in cls.CAMPOS_TIEMPO_MEDIO:
            v = cls._numero(bruto.get(suyo))
            if v is not None and 0 <= v < 86400:
                medio = round(v, 1)
                break
        return {"vista_entera": entera, "media_vista": media, "tiempo_medio_s": medio}

    @classmethod
    def _cifras(cls, bruto):
        datos = cls._numeros(bruto)
        datos.update(cls._retencion(bruto))
        return datos

    @classmethod
    def _numeros(cls, bruto):
        bruto = bruto if isinstance(bruto, dict) else {}
        salida = {}
        for nuestro, suyos in cls.CAMPOS_METRICAS.items():
            valor = None
            for suyo in suyos:
                if isinstance(bruto.get(suyo), (int, float)) and not isinstance(bruto.get(suyo), bool):
                    valor = int(bruto[suyo])
                    break
            salida[nuestro] = valor
        return salida

    def metricas_post(self, request_id, red=None, plazo=PLAZO_CONSULTA_S):
        """Las cifras de un envio (todas sus redes, o una). -> {red: {...}}"""
        r = self._pedir("GET", f"/api/uploadposts/post-analytics/{urllib.parse.quote(str(request_id))}",
                        consulta={"platform": red} if red else None, plazo=plazo)
        salida = {}
        for nombre, ficha in (r.get("platforms") or {}).items():
            if nombre not in REDES or not isinstance(ficha, dict):
                continue
            datos = self._cifras(ficha.get("post_metrics"))
            url = str(ficha.get("post_url") or "")
            datos["url"] = url if url.startswith("http") else ""
            # el id del post EN LA RED: con el se reconoce en la lectura guardada
            datos["post_id"] = str(ficha.get("platform_post_id") or "")[:120]
            datos["error"] = str(ficha.get("post_metrics_error") or "")[:300]
            salida[nombre] = datos
        return salida

    #: La lectura guardada: Upload-Post deja hasta 200 posts por pagina; mas de
    #: PAGINAS_GUARDADAS paginas no se piden en una vuelta (la peticion de la
    #: pantalla se corta a los 60 s detras del proxy).
    POR_PAGINA_GUARDADAS = 200
    PAGINAS_GUARDADAS = 3

    def metricas_guardadas(self, perfil, red=None, desde=None, hasta=None,
                           paginas=PAGINAS_GUARDADAS, plazo=PLAZO_CONSULTA_S):
        """Lo ultimo que Upload-Post leyo EN VIVO de cada post del perfil, sin
        volver a preguntar a las redes: NO gasta del limite de 100 consultas
        cada 5 minutos. Solo trae posts que se leyeron en vivo alguna vez, y
        para YouTube es el unico sitio con la retencion.
        -> {"posts": [{"red", "post_id", "url", "al", vistas…}], "completo": bool}"""
        consulta = {"user": perfil, "limit": self.POR_PAGINA_GUARDADAS,
                    "platform": red if red in REDES else None,
                    "since": desde or None, "until": hasta or None}
        posts, cursor, completo = [], None, False
        for _ in range(max(1, int(paginas))):
            if cursor:
                consulta["cursor"] = cursor
            r = self._pedir("GET", "/api/uploadposts/post-analytics/cached", consulta=consulta,
                            plazo=plazo)
            for item in r.get("posts") or []:
                if not isinstance(item, dict) or item.get("platform") not in REDES:
                    continue
                datos = self._cifras(item.get("metrics"))
                url = str(item.get("post_url") or "")
                datos.update(red=item["platform"], post_id=str(item.get("post_id") or "")[:120],
                             url=url if url.startswith("http") else "",
                             al=str(item.get("captured_at") or "")[:40])
                posts.append(datos)
            cursor = r.get("next_cursor")
            if not r.get("has_more") or not cursor:
                completo = True
                break
        return {"posts": posts, "completo": completo}

    def analiticas_perfil(self, perfil, redes, pagina_facebook=None):
        """Seguidores, alcance y vistas de cada cuenta del perfil. -> {red: {...}}"""
        redes = [r for r in redes if r in REDES]
        if not redes:
            return {}
        consulta = {"platforms": ",".join(redes)}
        if pagina_facebook:
            consulta["page_id"] = pagina_facebook
        r = self._pedir("GET", f"/api/analytics/{urllib.parse.quote(str(perfil))}", consulta=consulta)
        salida = {}
        for red in redes:
            ficha = r.get(red)
            if not isinstance(ficha, dict):
                salida[red] = {"seguidores": None, "alcance": None, "vistas": None,
                               "error": str(ficha or "sin datos")[:300] if ficha else "sin datos"}
                continue
            numeros = self._numeros(ficha)
            seguidores = ficha.get("followers")
            salida[red] = {
                "seguidores": int(seguidores) if isinstance(seguidores, (int, float))
                and not isinstance(seguidores, bool) else None,
                "alcance": numeros["alcance"], "vistas": numeros["vistas"],
                "error": str(ficha.get("error") or ficha.get("message") or "")[:300],
            }
        return salida


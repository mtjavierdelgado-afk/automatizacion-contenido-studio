"""La retención de Instagram y Facebook, leída de la API de Meta (rama
`retencion-meta`, 19-11-2026; plan en el Proyecto:
`estado/plan_retencion_meta_2026-11-12.md`).

Upload-Post da las cuentas (vistas, me gusta…) de todo lo publicado, pero de
Instagram y Facebook NO da cuánto se vio cada vídeo. Meta sí, con el mismo
token que el Studio ya guarda para leer cuentas de Instagram
(`<secretos>/lectura_redes.json`, `meta_token`):

    cli = ClienteMeta(token)
    cli.paginas()                       -> [{id, nombre, token, ig_id, ig_usuario}]
    cli.instagram(["1789…", …])         -> {id: {tiempo_medio_s, tiempo_total_s,
                                             salto_3s, reposts, tipo} | {"error": …}}
    cli.resolver_fb(token_pagina, "pagina_post")  -> id del vídeo | ""
    cli.facebook(token_pagina, [(id, duracion_s|None), …])
                                        -> {id: {tiempo_medio_s, tiempo_total_s,
                                             nuevos_seguidores, media_vista, curva,
                                             mitad_s, tipo, duracion_s} | {"error": …}}

Como todo motor (motores/README.md): no lee claves ni escribe en disco; lo
que necesita se lo pasan. Y como `lectura_redes`:

- El token va SIEMPRE en la cabecera `Authorization: Bearer`, nunca en la
  URL (una URL acaba en los registros de cualquier proxy).
- Todo texto de error pasa por `tachar` con el token del usuario Y los de
  página que se hayan visto: ni la bitácora ni el error de un envío pueden
  llevar un token.

Las unidades de Meta (comprobadas en el Explorador el 12-11, v26.0):
`ig_reels_avg_watch_time` e `ig_reels_video_view_total_time` en
MILISEGUNDOS; `reels_skip_rate` en TANTO POR CIEN (51,3 = 51,3 %); los
`post_video_*`/`total_video_*_time*` de Facebook también en milisegundos, y la
curva de Facebook (`*_retention_graph`) como {tramo: parte que sigue},
repartida en tramos iguales del vídeo.

Lo que Meta no sabe todavía (tarda hasta ~48 h en tener las cifras de un Reel)
no viene, y se queda en None: «no lo dice» no es «cero».
"""
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import http.client
import time

#: La versión de la API con la que se comprobaron las métricas (12-11). NO es
#: `lectura_redes.lectores.VERSION_META` (la de leer cuentas ajenas): cambiar
#: una no puede romper la otra.
VERSION_METRICAS = "v26.0"
BASE = "https://graph.facebook.com"
#: Plazo de cada llamada. Las llamadas van dentro de «Actualizar», que corre
#: detrás del proxy (corta a los 60 s): quien llama reparte su franja.
PLAZO_S = 6
#: Cuántos ids caben en una llamada con `?ids=` (Meta los cuenta sueltos para
#: el cupo, pero ahorra viajes).
TOPE_LOTE = 50

METRICAS_IG = ("ig_reels_avg_watch_time", "ig_reels_video_view_total_time",
               "reels_skip_rate", "reposts")
#: Un Reel de la página y un vídeo de la página llevan métricas distintas.
METRICAS_FB_REEL = ("post_video_avg_time_watched", "post_video_view_time",
                    "post_video_retention_graph", "post_video_followers")
METRICAS_FB_VIDEO = ("total_video_avg_time_watched", "total_video_view_total_time",
                     "total_video_retention_graph")
#: Cuántos puntos de la curva se guardan como mucho (como la de TikTok)
TOPE_CURVA = 120

#: Códigos de Meta que dicen «has pedido demasiado»: se para y se sigue en la
#: siguiente vuelta (nada se reintenta en bucle).
CODIGOS_CUPO = {4, 17, 32, 613} | set(range(80001, 80015))
#: Por encima de este % de uso (cabeceras X-App-Usage / X-Business-Use-Case-
#: Usage) no se empieza otra llamada.
USO_MAXIMO = 90


class ErrorMeta(RuntimeError):
    """`motivo`: sin_token · sin_permiso · caducado · cupo · red · metrica ·
    otro. `metrica`: la métrica que Meta no acepta (con motivo «metrica»)."""

    def __init__(self, mensaje, motivo="otro", metrica="", detalle=""):
        super().__init__(mensaje)
        self.motivo = motivo
        self.metrica = metrica
        # lo que dijo Meta, tal cual y SIN tokens (para diagnosticar en el
        # servidor: se guarda aparte del texto en castellano del envío)
        self.detalle = detalle


#: Los motivos con los que no tiene sentido seguir pidiendo nada esta vuelta.
#: «tiempo»: no cabe otra llamada en la franja de quien llama (`hasta`).
FATALES = ("sin_token", "sin_permiso", "caducado", "cupo", "red", "tiempo")

#: Lo que se guarda en el envío cuando Meta no da sus cifras: en castellano y
#: sin el mensaje crudo de Meta (en inglés y con detalles que no ayudan).
TEXTO_DE_MOTIVO = {
    "metrica": "Meta no da alguna de las cifras de esta publicación",
    "pocas_vistas": "Meta aún no da sus cifras: todavía tiene muy pocas vistas",
    "antes_profesional": "Meta no da las cifras de lo publicado antes de pasar la cuenta a "
                         "profesional",
    "otro": "Meta no ha devuelto las cifras de este vídeo",
    "vacio": "Meta todavía no tiene las cifras de este vídeo (tarda hasta dos días)",
}


def texto_para_envio(fallo):
    """El texto corto, en castellano, que se guarda en un envío."""
    if getattr(fallo, "motivo", "") == "vacio":
        return TEXTO_DE_MOTIVO["vacio"]
    return TEXTO_DE_MOTIVO.get(getattr(fallo, "motivo", ""), TEXTO_DE_MOTIVO["otro"])


def tachar(texto, claves):
    """El texto sin ningún token entero (ni escapado en una URL): queda su
    cola, «…ab12», para poder decir cuál era."""
    texto = str(texto or "")
    for clave in claves or ():
        clave = str(clave or "")
        if len(clave) >= 8:
            for forma in (clave, urllib.parse.quote(clave, safe="")):
                texto = texto.replace(forma, "…" + clave[-4:])
    return texto


def _numero(valor):
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor) if valor == valor and abs(valor) != float("inf") else None
    if isinstance(valor, str):
        try:
            v = float(valor.strip().replace(",", "."))
        except ValueError:
            return None
        return v if v == v and abs(v) != float("inf") else None
    return None


def _valor_de(dato):
    """El valor de una métrica de `insights`: viene en `values[0].value` o en
    `total_value.value` según la métrica y la versión."""
    if not isinstance(dato, dict):
        return None
    total = dato.get("total_value")
    if isinstance(total, dict) and "value" in total:
        return total.get("value")
    valores = dato.get("values")
    if isinstance(valores, list) and valores and isinstance(valores[0], dict):
        return valores[-1].get("value")
    return None


def _metricas(nodo, clave="insights"):
    """{nombre: valor} de un nodo con su borde de métricas."""
    borde = (nodo or {}).get(clave) if isinstance(nodo, dict) else None
    datos = borde.get("data") if isinstance(borde, dict) else None
    salida = {}
    for d in datos or []:
        if isinstance(d, dict) and d.get("name"):
            salida[str(d["name"])] = _valor_de(d)
    return salida


def curva_de(grafico, duracion_s):
    """La curva de Facebook ({tramo: parte}) en el formato del Studio:
    [[segundo, fracción 0..1]], en orden, y el segundo en que se va la mitad.
    Sin duración no se puede poner en segundos: (None, None)."""
    if not isinstance(grafico, dict) or not grafico:
        return None, None
    duracion = _numero(duracion_s)
    if not duracion or duracion <= 0:
        return None, None
    tramos = []
    for k, v in grafico.items():
        i, parte = _numero(k), _numero(v)
        if i is None or parte is None or i < 0 or parte < 0:
            continue
        tramos.append((i, parte))
    if len(tramos) < 2:
        return None, None
    tramos.sort()
    n = tramos[-1][0] + 1
    # en tanto por cien si algo pasa de 1,5 (como la de TikTok en `_escala_comun`)
    en_cien = any(p > 1.5 for _i, p in tramos)
    curva, vistos = [], set()
    for i, parte in tramos:
        f = parte / 100 if en_cien else parte
        if f > 1:
            f = 1.0
        segundo = round(i / n * duracion, 3)
        if segundo in vistos:
            continue
        vistos.add(segundo)
        curva.append([segundo, round(f, 4)])
    mitad = next((s for s, f in curva if f <= 0.5), None)
    if len(curva) > TOPE_CURVA:
        paso = -(-len(curva) // TOPE_CURVA)
        ligera = curva[::paso]
        if ligera[-1] != curva[-1]:
            ligera = ligera[:TOPE_CURVA - 1] + [curva[-1]]
        curva = ligera
    return curva, mitad


class ClienteMeta:
    simulado = False

    def __init__(self, token, base=None, plazo=PLAZO_S, version=VERSION_METRICAS, hasta=None):
        self.token = str(token or "").strip()
        #: momento (time.time()) a partir del cual no se empieza ninguna llamada
        #: que no quepa entera: quien llama tiene su franja (el proxy corta a 60 s)
        self.hasta = hasta
        #: si alguna llamada se dejó sin hacer por falta de tiempo
        self.sin_tiempo = False
        self.base = (base or BASE).rstrip("/")
        self.plazo = plazo
        self.version = version
        self._claves = [self.token]
        #: lo que Meta no aceptó (métricas retiradas), para decirlo en pantalla
        self.retiradas = []
        #: si una cabecera de uso dijo que vamos cerca del cupo
        self.cerca_del_cupo = False

    # -------------------------------------------------------------- red

    def _url(self, ruta, params):
        ruta = ruta.lstrip("/")
        url = f"{self.base}/{self.version}/{ruta}"
        if params:
            url += "?" + urllib.parse.urlencode(params, safe=",(){}")
        return url

    def _get(self, ruta, params=None, token=None):
        token = token or self.token
        if not token:
            raise ErrorMeta("falta el token de Meta: ponlo en Configuración", "sin_token")
        if self.hasta is not None and time.time() + self.plazo > self.hasta:
            self.sin_tiempo = True
            raise ErrorMeta("no da tiempo a otra consulta a Meta esta vez", "tiempo")
        peticion = urllib.request.Request(
            self._url(ruta, params), method="GET",
            headers={"Accept": "application/json", "User-Agent": "CrearIAStudio/5.1",
                     "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(peticion, timeout=self.plazo) as r:
                crudo, codigo, cabeceras = r.read(), r.status, r.headers
        except urllib.error.HTTPError as fallo:
            crudo, codigo, cabeceras = fallo.read() or b"", fallo.code, fallo.headers
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
                http.client.HTTPException, OSError) as fallo:
            raise ErrorMeta(tachar(f"no se ha podido hablar con Meta: {fallo}", self._claves),
                            "red") from None
        self._mirar_uso(cabeceras)
        try:
            datos = json.loads(crudo.decode("utf-8") or "null")
        except ValueError:
            datos = None
        if codigo >= 400 or not isinstance(datos, dict) or datos.get("error"):
            raise self._error(datos, codigo)
        return datos

    def _mirar_uso(self, cabeceras):
        """X-App-Usage {"call_count": 12, …} y X-Business-Use-Case-Usage
        {id: [{"call_count": …, "total_time": …}]}: si algo pasa de USO_MAXIMO, no
        se empieza otra llamada esta vuelta."""
        if cabeceras is None:
            return
        for nombre in ("X-App-Usage", "X-Business-Use-Case-Usage", "X-Ad-Account-Usage"):
            crudo = cabeceras.get(nombre) if hasattr(cabeceras, "get") else None
            if not crudo:
                continue
            try:
                uso = json.loads(crudo)
            except ValueError:
                continue
            trozos = []
            if isinstance(uso, dict):
                for v in uso.values():
                    if isinstance(v, list):
                        trozos.extend(x for x in v if isinstance(x, dict))
                trozos.append(uso)
            for t in trozos:
                for k in ("call_count", "total_cputime", "total_time"):
                    n = _numero(t.get(k))
                    if n is not None and n >= USO_MAXIMO:
                        self.cerca_del_cupo = True

    def _error(self, datos, codigo):
        """El ErrorMeta de una respuesta de Meta, con lo que dijo en `detalle`
        («#código/subcódigo mensaje», sin tokens)."""
        fallo = self._clasificar(datos, codigo)
        err = (datos or {}).get("error") if isinstance(datos, dict) else None
        err = err if isinstance(err, dict) else {}
        fallo.detalle = tachar(f"HTTP {codigo} #{err.get('code', '')}/{err.get('error_subcode', '')} "
                               f"{str(err.get('message') or '')}", self._claves).strip()[:240]
        return fallo

    def _clasificar(self, datos, codigo):
        err = (datos or {}).get("error") if isinstance(datos, dict) else None
        err = err if isinstance(err, dict) else {}
        mensaje = tachar(str(err.get("message") or f"Meta ha contestado {codigo}")[:300],
                         self._claves)
        num = int(_numero(err.get("code")) or 0)
        sub = int(_numero(err.get("error_subcode")) or 0)
        # #10 que son de UN solo vídeo, no del token (árbitro del tren, 25-11):
        # se apuntan en ese envío, con su reloj, y se sigue con los demás
        if sub == 2108006 or re.search(r"before business account conversion", mensaje, re.IGNORECASE):
            return ErrorMeta(f"publicado antes de pasar la cuenta a profesional: {mensaje}",
                             "antes_profesional")
        if re.search(r"not enough viewers", mensaje, re.IGNORECASE):
            return ErrorMeta(f"todavía con muy pocas vistas: {mensaje}", "pocas_vistas")
        if num == 190 or codigo == 401:
            return ErrorMeta("el token de Meta ha caducado o ya no vale: genera uno nuevo y "
                             f"pégalo en Configuración ({mensaje})", "caducado")
        if num in CODIGOS_CUPO or codigo == 429:
            return ErrorMeta(f"Meta pide esperar un rato (demasiadas consultas): {mensaje}", "cupo")
        # sin el permiso de métricas, Meta no siempre da #10/#200: a veces un
        # #100 que nombra el permiso (prueba del servidor, 25-11)
        # SOLO por el nombre del permiso: «missing permissions» a secas sale
        # también en un id borrado (#100, subcódigo 33: «does not exist, cannot be
        # loaded due to missing permissions…»), y eso es cosa del vídeo (árbitro)
        falta = re.search(r"instagram_manage_insights|read_insights|pages_read_engagement",
                          mensaje, re.IGNORECASE) and not re.search(r"does not exist", mensaje,
                                                                    re.IGNORECASE)
        if num in (10, 200) or 200 <= num < 300 or (num == 100 and falta):
            return ErrorMeta("al token de Meta le falta un permiso (read_insights o "
                             f"instagram_manage_insights): {mensaje}", "sin_permiso")
        if num == 100:
            todas = METRICAS_IG + METRICAS_FB_REEL + METRICAS_FB_VIDEO
            nombrada = next((m for m in todas if m in mensaje), "")
            if nombrada:
                return ErrorMeta(f"Meta no acepta la métrica {nombrada}: {mensaje}", "metrica",
                                 metrica=nombrada)
        return ErrorMeta(mensaje, "otro")

    # ---------------------------------------------------------- páginas

    def paginas(self):
        """Las páginas de Facebook que administra el token, con su token de
        página (solo en memoria) y su Instagram. Una sola llamada por vuelta:
        la lista se guarda en el cliente (que vive lo que dura la vuelta)."""
        if getattr(self, "_paginas", None) is not None:
            return self._paginas
        datos = self._get("me/accounts", {
            "fields": "id,name,access_token,instagram_business_account{id,username}",
            "limit": 100})
        salida = []
        for p in datos.get("data") or []:
            if not isinstance(p, dict) or not p.get("id"):
                continue
            token = str(p.get("access_token") or "")
            if token:
                self._claves.append(token)
            ig = p.get("instagram_business_account") or {}
            salida.append({"id": str(p["id"]), "nombre": str(p.get("name") or ""),
                           "token": token, "ig_id": str(ig.get("id") or ""),
                           "ig_usuario": str(ig.get("username") or "")})
        self._paginas = salida
        return salida

    # -------------------------------------------------------- instagram

    def instagram(self, ids):
        """Las cifras de retención de estos medios de Instagram. Un medio que
        no es un Reel trae {"error": …}: Meta solo da retención de Reels."""
        ids = [str(i) for i in ids if i]
        salida = {}
        metricas = list(METRICAS_IG)
        for i in range(0, len(ids), TOPE_LOTE):
            if self.cerca_del_cupo:
                break
            trozo = ids[i:i + TOPE_LOTE]
            try:
                salida.update(self._instagram_lote(trozo, metricas, salida))
            except ErrorMeta as fallo:
                if fallo.motivo == "tiempo":
                    break           # lo leído hasta aquí vale; el resto, otra vuelta
                if fallo.motivo == "cupo":
                    # lo leído en el lote antes del aviso se queda (árbitro, 24-11)
                    self.cerca_del_cupo = True
                    break
                raise
        return salida

    def _instagram_lote(self, trozo, metricas, hechos=None):
        """Un lote; si Meta lo rechaza, de uno en uno. `hechos` (lo ya
        contestado en esta vuelta) se va llenando para no perderlo si se
        acaba el tiempo a medias."""
        metricas = [m for m in metricas if m not in self.retiradas]
        campos = "id,media_product_type,permalink,insights.metric(%s)" % ",".join(metricas)
        try:
            datos = self._get("", {"ids": ",".join(trozo), "fields": campos})
        except ErrorMeta as fallo:
            if fallo.motivo in FATALES:
                raise
            if len(trozo) == 1:
                return self._instagram_solo(trozo[0], metricas, fallo)
            # un id malo (o una foto, a la que Meta no le acepta las métricas de
            # Reel) tumba el lote entero: de uno en uno, sin retirar nada
            salida = hechos if hechos is not None else {}
            for uno in trozo:
                if self.cerca_del_cupo:
                    break
                if uno not in salida:
                    salida.update(self._instagram_lote([uno], metricas))
            return {k: salida[k] for k in trozo if k in salida}
        return self._instagram_nodos(trozo, datos)

    def _instagram_solo(self, ident, metricas, fallo):
        """Un medio que Meta rechaza: ¿es que no es un Reel, o que Meta ya no
        da una métrica? Se pregunta solo su tipo (sin métricas): si no es un
        Reel, se dice; si lo es y el fallo nombraba una métrica, esa métrica se
        retira (para todos) y se pide otra vez sin ella, una sola vez."""
        try:
            nodo = self._get("", {"ids": ident, "fields": "id,media_product_type,permalink"})
        except ErrorMeta as otro:
            if otro.motivo in FATALES:
                raise
            return {ident: {"error": texto_para_envio(fallo), "detalle": _detalle(fallo, otro)}}
        nodo = nodo.get(ident) if isinstance(nodo.get(ident), dict) else {}
        tipo = str(nodo.get("media_product_type") or "")
        if tipo and tipo != "REELS":
            return {ident: {"error": "no es un Reel (Meta solo da la retención de los Reels)",
                            "tipo": tipo}}
        # «metric[2] must be one of…» trae la lista de las VÁLIDAS: la métrica
        # mala es la del número que dice, no la primera nuestra que salga
        num = re.search(r"metric\[(\d+)\]", str(fallo))
        if fallo.motivo == "metrica" and num and int(num.group(1)) < len(metricas):
            fallo.metrica = metricas[int(num.group(1))]
        if fallo.motivo == "metrica" and fallo.metrica in metricas and len(metricas) > 1:
            self.retiradas.append(fallo.metrica)
            resto = [m for m in metricas if m != fallo.metrica]
            campos = "id,media_product_type,permalink,insights.metric(%s)" % ",".join(resto)
            try:
                datos = self._get("", {"ids": ident, "fields": campos})
            except ErrorMeta as otra_vez:
                if otra_vez.motivo in FATALES:
                    raise
                return {ident: {"error": texto_para_envio(otra_vez), "detalle": _detalle(otra_vez)}}
            return self._instagram_nodos([ident], datos)
        return {ident: {"error": texto_para_envio(fallo), "detalle": _detalle(fallo)}}

    def _instagram_nodos(self, trozo, datos):
        salida = {}
        for ident in trozo:
            nodo = datos.get(ident)
            if not isinstance(nodo, dict):
                salida[ident] = {"error": "Meta no ha devuelto este medio"}
                continue
            tipo = str(nodo.get("media_product_type") or "")
            if tipo and tipo != "REELS":
                salida[ident] = {"error": "no es un Reel (Meta solo da la retención de los Reels)",
                                 "tipo": tipo}
                continue
            m = _metricas(nodo)
            medio = _numero(m.get("ig_reels_avg_watch_time"))
            total = _numero(m.get("ig_reels_video_view_total_time"))
            salto = _numero(m.get("reels_skip_rate"))
            reposts = _numero(m.get("reposts"))
            salida[ident] = {
                "tipo": tipo or "REELS",
                "permalink": str(nodo.get("permalink") or ""),
                "tiempo_medio_s": round(medio / 1000, 1) if medio is not None and medio >= 0 else None,
                "tiempo_total_s": round(total / 1000, 1) if total is not None and total >= 0 else None,
                "salto_3s": round(salto / 100, 4) if salto is not None and 0 <= salto <= 100 else None,
                "reposts": int(reposts) if reposts is not None and reposts >= 0 else None,
            }
        return salida

    def medios_ig(self, ig_id, paginas_max=4):
        """Los medios de una cuenta de Instagram (id, shortcode, permalink),
        los más nuevos primero, hasta `paginas_max` páginas de 50. Para dar con
        el id de un Reel cuando el que trae el envío no es el de Meta (prueba
        del servidor, 25-11: Instagram no contestaba ningún Reel)."""
        salida, despues = [], ""
        for _ in range(max(1, int(paginas_max))):
            params = {"fields": "id,shortcode,permalink,media_product_type", "limit": 50}
            if despues:
                params["after"] = despues
            if self.cerca_del_cupo:
                break
            try:
                datos = self._get(f"{ig_id}/media", params)
            except ErrorMeta as fallo:
                # sin tiempo o sin cupo, vale lo leído hasta aquí
                if fallo.motivo in ("tiempo", "cupo") and salida:
                    if fallo.motivo == "cupo":
                        self.cerca_del_cupo = True
                    break
                raise
            for m in datos.get("data") or []:
                if isinstance(m, dict) and m.get("id"):
                    salida.append({"id": str(m["id"]), "shortcode": str(m.get("shortcode") or ""),
                                   "permalink": str(m.get("permalink") or ""),
                                   "tipo": str(m.get("media_product_type") or "")})
            despues = (((datos.get("paging") or {}).get("cursors") or {}).get("after") or "")
            if not despues or not (datos.get("paging") or {}).get("next"):
                break
        return salida

    # --------------------------------------------------------- facebook

    def resolver_fb(self, token_pagina, pagina_post):
        """El id del vídeo de un post de página («123_456»): el `target` de su
        adjunto. "" si no lleva vídeo."""
        datos = self._get(str(pagina_post), {"fields": "attachments{media_type,target{id}}"},
                          token=token_pagina)
        for a in ((datos.get("attachments") or {}).get("data") or []):
            ident = ((a or {}).get("target") or {}).get("id")
            if ident:
                return str(ident)
        return ""

    def facebook(self, token_pagina, items):
        """[(id del vídeo, duración en s|None)] -> {id: cifras|{"error"}}. Uno a
        uno: un Reel y un vídeo llevan métricas distintas, y si Meta no acepta
        las de Reel se prueban las de vídeo."""
        if token_pagina:
            self._claves.append(token_pagina)
        salida = {}
        for ident, duracion in items:
            if self.cerca_del_cupo:
                break
            ident = str(ident or "")
            if not ident:
                continue
            try:
                salida[ident] = self._facebook_uno(token_pagina, ident, duracion)
            except ErrorMeta as fallo:
                if fallo.motivo == "tiempo":
                    break           # lo leído hasta aquí vale
                if fallo.motivo in FATALES:
                    raise
                salida[ident] = {"error": texto_para_envio(fallo)}
        return salida

    def _facebook_uno(self, token_pagina, ident, duracion):
        ultimo = vacio = None
        for tipo, metricas in (("reel", METRICAS_FB_REEL), ("video", METRICAS_FB_VIDEO)):
            metricas = [m for m in metricas if m not in self.retiradas]
            campos = "id,length,video_insights.metric(%s){name,values}" % ",".join(metricas)
            try:
                datos = self._get(ident, {"fields": campos}, token=token_pagina)
            except ErrorMeta as fallo:
                if fallo.motivo in FATALES:
                    raise
                ultimo = fallo
                continue          # con las de vídeo, por si no era un Reel
            m = _metricas(datos, "video_insights")
            if not any(v is not None for v in m.values()):
                vacio = ErrorMeta("Meta todavía no tiene las cifras de este vídeo", "vacio")
                continue
            largo = _numero(datos.get("length"))
            dur = _numero(duracion) or (largo if largo and largo > 0 else None)
            prefijo = "post_video" if tipo == "reel" else "total_video"
            medio = _numero(m.get(f"{prefijo}_avg_time_watched"))
            total = _numero(m.get("post_video_view_time" if tipo == "reel"
                                  else "total_video_view_total_time"))
            seguidores = _numero(m.get("post_video_followers")) if tipo == "reel" else None
            curva, mitad = curva_de(m.get(f"{prefijo}_retention_graph"), dur)
            tiempo_medio = round(medio / 1000, 1) if medio is not None and medio >= 0 else None
            return {
                "tipo": tipo, "duracion_s": round(dur, 1) if dur else None,
                "tiempo_medio_s": tiempo_medio,
                "tiempo_total_s": round(total / 1000, 1) if total is not None and total >= 0 else None,
                "nuevos_seguidores": int(seguidores) if seguidores is not None and seguidores >= 0
                else None,
                # puede pasar de 1 si se vuelve a ver (como en YouTube)
                "media_vista": round(tiempo_medio / dur, 4) if tiempo_medio is not None and dur
                and 0 <= tiempo_medio / dur <= 10 else None,
                "curva": curva, "mitad_s": mitad if curva else None,
            }
        # «todavía no tiene las cifras» dice más que el rechazo de la otra forma
        raise vacio or ultimo or ErrorMeta("Meta no ha devuelto las cifras de este vídeo", "otro")


def _detalle(*fallos):
    """Lo que dijo Meta en estos fallos (sin tokens), en una línea."""
    vistos = []
    for f in fallos:
        d = str(getattr(f, "detalle", "") or "")
        if d and d not in vistos:
            vistos.append(d)
    return " | ".join(vistos)[:300]


def shortcode_ig(texto):
    """El código corto de un Reel («DAbc_12-x») de su enlace
    (instagram.com/reel/<código>/, /p/, /tv/) o del propio id si no es un número.
    "" si no se puede saber."""
    texto = str(texto or "").strip()
    m = re.search(r"instagram\.com/(?:[^/?#]+/)?(?:reels?|p|tv)/([A-Za-z0-9_-]{5,40})", texto)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{5,40}", texto) and not texto.isdigit():
        return texto
    return ""


def es_pagina_post(ident):
    """«123_456» es un post de página (hay que sacar su vídeo); un número a
    secas ya es el id del vídeo."""
    return bool(re.fullmatch(r"\d+_\d+", str(ident or "")))

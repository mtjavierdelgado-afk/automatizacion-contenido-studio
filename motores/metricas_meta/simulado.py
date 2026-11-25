"""Un Meta de mentira, con la misma cara que `ClienteMeta`.

Para las suites y el recorrido: nadie llama a Meta. Lo elige `pasos/publicar.py`
cuando Upload-Post también va simulado (`ESTUDIO_UPLOADPOST_SIMULADO` o
`ESTUDIO_SIMULAR=1`). Las cifras salen del id (siempre las mismas para el
mismo post), con la forma y las unidades que dio Meta el 12-11.

`ESTUDIO_META_SIMULADO_FALLO` = sin_token | sin_permiso | caducado | cupo | red
hace que la primera llamada falle así, para probar los avisos.
"""
import hashlib
import os

try:
    from .cliente import ErrorMeta, curva_de, FATALES  # noqa: F401
except ImportError:                                     # cargado suelto
    from cliente import ErrorMeta, curva_de, FATALES    # noqa: F401


def _semilla(*trozos):
    return int(hashlib.sha1("|".join(map(str, trozos)).encode("utf-8")).hexdigest()[:8], 16)


class SimuladoMeta:
    simulado = True

    def __init__(self, token="simulado", **_kw):
        self.token = token
        self.retiradas = []
        self.cerca_del_cupo = False
        self.llamadas = 0

    def _fallo(self):
        self.llamadas += 1
        motivo = (os.environ.get("ESTUDIO_META_SIMULADO_FALLO") or "").strip()
        if motivo:
            raise ErrorMeta(f"(simulado) Meta falla: {motivo}", motivo)

    def paginas(self):
        self._fallo()
        return [{"id": "1318345554704332", "nombre": "Página simulada",
                 "token": "pagina-simulada-token", "ig_id": "17841400000000000",
                 "ig_usuario": "micuenta_studio"}]

    def instagram(self, ids):
        self._fallo()
        salida = {}
        for ident in ids:
            s = _semilla("ig", ident)
            salida[str(ident)] = {
                "tipo": "REELS", "permalink": f"https://www.instagram.com/reel/{ident}/",
                "tiempo_medio_s": round(3 + s % 90 / 10, 1),
                "tiempo_total_s": round(200 + s % 5000, 1),
                "salto_3s": round((30 + s % 40) / 100, 4),
                "reposts": s % 4,
            }
        return salida

    def resolver_fb(self, token_pagina, pagina_post):
        self._fallo()
        return str(pagina_post).split("_")[-1]

    def facebook(self, token_pagina, items):
        self._fallo()
        salida = {}
        for ident, duracion in items:
            s = _semilla("fb", ident)
            dur = float(duracion or 30)
            grafico = {str(i): round(max(0.04, 1 - i * (0.02 + s % 5 / 200)), 3) for i in range(40)}
            curva, mitad = curva_de(grafico, dur)
            medio = round(2 + s % 80 / 10, 1)
            salida[str(ident)] = {
                "tipo": "reel", "duracion_s": dur, "tiempo_medio_s": medio,
                "tiempo_total_s": round(100 + s % 3000, 1), "nuevos_seguidores": s % 6,
                "media_vista": round(medio / dur, 4), "curva": curva, "mitad_s": mitad,
            }
        return salida

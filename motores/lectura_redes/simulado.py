"""El doble de las fuentes (ESTUDIO_SIMULAR=1): sin red y sin pagar.

Para ejercitar el orden de las vías, un usuario que empieza por «personal»
hace que Instagram por la vía oficial conteste «no_profesional», uno que empieza
por «noexiste» no existe en ninguna, y uno que empieza por «caro» hace que
Apify cueste mucho (para probar el tope).
"""
from .lectores import ErrorLectura, coste_apify


def leer(fuente, red, usuario, cuantos=30):
    usuario = str(usuario or "").lstrip("@")
    if usuario.lower().startswith("noexiste"):
        raise ErrorLectura(f"no hay ninguna cuenta «{usuario}»", "no_encontrada")
    if fuente == "instagram_oficial" and usuario.lower().startswith("personal"):
        raise ErrorLectura(f"@{usuario} no es una cuenta profesional", "no_profesional")
    temas = ["cumpleaños con consola", "karaoke en la oficina", "torneo de FIFA", "noche de juegos",
             "simulador de carreras", "fiesta sorpresa", "juegos para niños", "after office"]
    videos = []
    tipo = {"instagram": "reel", "youtube": "short", "tiktok": "video"}.get(red, "")
    for i in range(min(int(cuantos or 30), 12)):
        vistas = 20000 // (i + 1) + 137 * i
        texto = (f"¿Sabías esto del {temas[i % len(temas)]}? Te cuento los tres trucos que usamos "
                 f"en cada fiesta para que nadie se aburra. #{red}")
        me_gusta = vistas // 12
        if i == 7:                       # un vídeo en colaboración (rama cuentas-gustan-2)
            texto = f"En colab con @amigo_{usuario[:8]}: {temas[i % len(temas)]} #{red}"
        if i == 9:                       # y uno con pinta de promoción pagada
            vistas, me_gusta = 90000, 90
        videos.append({"id": f"v{i}", "url": f"https://example.com/{red}/{usuario}/{i}",
                       "texto": texto,
                       "fecha": f"2026-10-{(i % 9) + 1:02d}T19:00:00", "vistas": vistas,
                       "me_gusta": me_gusta, "comentarios": vistas // 150, "compartidos": vistas // 300,
                       # Instagram por la vía oficial no trae la duración
                       "duracion_s": None if fuente == "instagram_oficial" else 15 + 5 * (i % 6),
                       "transcripcion": "", "tipo": tipo})
    coste = 0.0 if fuente != "apify" else (99.0 if usuario.lower().startswith("caro") else coste_apify(red, len(videos)))
    return {"red": red, "usuario": usuario, "nombre": usuario.capitalize(), "seguidores": 12345,
            "fuente": fuente, "coste_usd": coste, "videos": videos}


def analisis(datos):
    return ("QUÉ LE FUNCIONA\n- (simulado) Los vídeos que empiezan con una pregunta tienen más vistas "
            f"(el 1, el 2).\nTEMAS\n- {len(datos.get('videos') or [])} vídeos leídos de @{datos.get('usuario')}.\n"
            "GANCHOS\n- Una pregunta en el primer segundo.\nDURACIÓN Y FORMATO\n- Vertical, de 15 a 40 s.\n"
            "CUÁNDO PUBLICA\n- Por la tarde.\nLO QUE NO LE FUNCIONA\n- Los vídeos largos.\n"
            "IDEAS PARA MÍ\n- Cinco ideas de prueba.")

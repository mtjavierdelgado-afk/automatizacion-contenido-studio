#!/usr/bin/env python3
"""Antes y después de los títulos de YouTube y Facebook de UN vídeo (rama
`titulos-gancho`, 04-11-2026). NO guarda nada: enseña el título que tiene
guardado la ficha de Publicar (el «antes») y le pide a Claude, con la
instrucción de los textos de ahora, los títulos nuevos (el «después»).

    En la consola del VPS (como root), con la rama puesta en el servidor:
    sudo -u studio -H bash -c "set -a; . /opt/as-video-studio/datos/entorno; set +a; \\
      cd /opt/as-video-studio/app && /opt/as-video-studio/venv/bin/python \\
      herramientas/titulos_antes_despues.py <id_del_video> [--veces 3]"

Habla con Claude por la suscripción (como «Escribir con Claude»): no se paga
aparte. Cada vuelta tarda ~1 minuto.
"""
import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "pasos"))

REDES = ("youtube", "facebook")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video", help="el id del vídeo (la carpeta del proyecto)")
    ap.add_argument("--veces", type=int, default=2, help="cuántas propuestas (1 a 5)")
    args = ap.parse_args()
    import app                                              # noqa: PLC0415
    import cli_claude                                       # noqa: PLC0415
    import comun                                            # noqa: PLC0415
    P = app._publicar()
    import publicar_seo as SEO                              # noqa: PLC0415
    import seo_real as SR                                   # noqa: PLC0415
    ctx = app.contexto(args.video)
    info = app._info_para_publicar(ctx)
    raiz = app.raiz_proyectos()
    ajustes = P.ajustes_de(raiz, info["cliente"])
    datos = P._leer_video(raiz, ctx.id)
    palabra = SEO.palabra_del_video(datos, ajustes, info)
    print(f"Vídeo: {ctx.id}\nPalabra clave: {palabra or '(ninguna)'}\n")
    print("ANTES (lo guardado en Publicar):")
    for red in REDES:
        print(f"  {P.NOMBRE_RED[red]:9} {((datos.get('textos') or {}).get(red) or {}).get('titulo') or '—'}")
    seo = SEO.bloque_instruccion(ajustes, palabra, list(REDES), info=info,
                                 busquedas=SR.resumen_para_claude(P.seo_real_de(datos), palabra))
    instruccion = P.instruccion_textos(info, list(REDES), ajustes, seo, datos)
    for vuelta in range(max(1, min(5, args.veces))):
        print(f"\nDESPUÉS, propuesta {vuelta + 1} (Claude está escribiendo, ~1 min)…", flush=True)
        respuesta, _sobre = cli_claude.ejecutar(
            instruccion, modelo=P.MODELO, esfuerzo=P.ESFUERZO, cwd=ctx.proyecto.raiz,
            base_tiempo_s=180, tiempo_max_s=P.TECHO_TEXTOS_S, sistema=P.SISTEMA,
            extra=["--no-session-persistence"], para="títulos antes y después")
        textos, _caps = P.normalizar_textos(comun.extraer_json(respuesta, "los títulos"),
                                            list(REDES))
        for red in REDES:
            titulo = textos[red]["titulo"] or "—"
            print(f"  {P.NOMBRE_RED[red]:9} {titulo}  ({len(titulo)} caracteres, "
                  f"{P.contar_emojis(titulo)} emojis)")
    print("\nNo se ha guardado nada. Para usarlos: Publicar → el vídeo → «Escribir con Claude».")
    return 0


if __name__ == "__main__":
    sys.exit(main())

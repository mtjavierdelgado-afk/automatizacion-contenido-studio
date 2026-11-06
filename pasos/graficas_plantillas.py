"""Las 14 plantillas de Gráficas (rama graficas-1, 05-11-2026).

Cada una es HTML con medidas relativas al lienzo (cqmin, cqw, cqh), asi que el
mismo diseno sirve en todos los tamanos: lo que cambia por formato llega como
variable de CSS (`--pad`, `--dir`, `--corte`...). Lo pone `graficas.html_de`.

`«campo»` se sustituye por el texto ESCAPADO; `class="t"` marca el texto que
tiene que caber y quedar fuera de lo que tapa la red (lo mide `graficas`).
"""

PLANTILLAS = {
    1: """\
<div style="position: absolute; inset: 0; background: var(--a); color: var(--ta)">
  <div style="position: absolute; right: -18cqmin; bottom: -18cqmin; width: 50cqmin; height: 50cqmin; border-radius: 50%; background: var(--b)"></div>
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: space-between; gap: 2cqmin">
    <div class="t" data-e="marca" style="font-weight: 700; font-size: calc(var(--s-k)*var(--esc)); letter-spacing: 0.04em">«logo»</div>
    <div>
      <div class="t" data-e="titulo" style="font-family: var(--ft, 'Anton'), sans-serif; font-size: calc(var(--s-xl)*var(--esc)); line-height: 1.04; text-transform: uppercase">«titulo»</div>
      <div class="t" data-e="apoyo" style="margin-top: 2.5cqmin; font-size: calc(var(--s-a)*var(--esc)); font-weight: 500; max-width: 72%">«apoyo»</div>
    </div>
    <div class="t" data-e="cta" style="align-self: flex-start; background: var(--d); color: var(--l); padding: 1.8cqmin 3.6cqmin; border-radius: 99px; font-weight: 700; font-size: calc(var(--s-c)*var(--esc))">«cta»</div>
  </div>
</div>
""",
    2: """\
<div style="position: absolute; inset: 0">
  <img src="«img»" alt="Imagen de ejemplo" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover">
  <div style="position: absolute; inset: 0; background: linear-gradient(180deg, transparent 30%, var(--d) 92%)"></div>
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: flex-end; align-items: flex-start; gap: 2cqmin; color: #fff">
    <div class="t" data-e="kicker" style="background: var(--a); color: var(--ta); padding: 1cqmin 2.4cqmin; font-weight: 700; font-size: calc(var(--s-k)*var(--esc)); text-transform: uppercase; letter-spacing: 0.06em">«kicker»</div>
    <div class="t" data-e="titulo" style="font-family: var(--ft, 'Archivo Black'), sans-serif; font-size: calc(var(--s-l)*var(--esc)); line-height: 1.05">«titulo»</div>
    <div style="display: flex; align-items: center; gap: 3cqmin; flex-wrap: wrap">
      <div class="t" data-e="cta" style="background: var(--b); color: var(--tb); padding: 1.6cqmin 3.2cqmin; border-radius: 1.2cqmin; font-weight: 800; font-size: calc(var(--s-c)*var(--esc))">«cta»</div>
      <div class="t" data-e="marca" style="font-weight: 700; font-size: calc(var(--s-k)*var(--esc))">«logo»</div>
    </div>
  </div>
</div>
""",
    3: """\
<div style="position: absolute; inset: 0">
  <img src="«img»" alt="Imagen de ejemplo" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover">
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: flex-end; align-items: var(--tarjetaLado)">
    <div style="width: var(--tarjetaAncho); box-sizing: border-box; background: #fff; color: var(--d); border-radius: 3cqmin; padding: 4cqmin; box-shadow: 0 2cqmin 6cqmin rgba(0,0,0,0.35)">
      <div class="t" data-e="kicker" style="color: var(--a); font-weight: 800; font-size: calc(var(--s-k)*var(--esc)); text-transform: uppercase; letter-spacing: 0.05em">«kicker»</div>
      <div class="t" data-e="titulo" style="font-family: var(--ft, 'Poppins'), sans-serif; font-weight: 800; font-size: calc(var(--s-m)*var(--esc)); line-height: 1.1; margin-top: 1.2cqmin">«titulo»</div>
      <div class="t" data-e="cta" style="margin-top: 2.4cqmin; display: inline-block; background: var(--a); color: var(--ta); padding: 1.4cqmin 3cqmin; border-radius: 99px; font-weight: 700; font-size: calc(var(--s-c)*var(--esc))">«cta»</div>
    </div>
  </div>
</div>
""",
    4: """\
<div style="position: absolute; inset: 0">
  <img src="«img»" alt="Imagen de ejemplo" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover">
  <div style="position: absolute; inset: 0; background: var(--b); clip-path: var(--corte2)"></div>
  <div style="position: absolute; inset: 0; background: var(--a); clip-path: var(--corte)"></div>
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: flex-end; gap: 1.6cqmin; color: var(--ta)">
    <div class="t" data-e="titulo" style="width: var(--mitad); font-family: var(--ft, 'Montserrat'), sans-serif; font-weight: 900; font-size: calc(var(--s-m)*var(--esc)); line-height: 1.05; text-transform: uppercase">«titulo»</div>
    <div class="t" data-e="apoyo" style="width: var(--mitad); font-weight: 500; font-size: calc(var(--s-a)*var(--esc))">«apoyo»</div>
    <div class="t" data-e="cta" style="font-weight: 800; font-size: calc(var(--s-c)*var(--esc))">«cta» →</div>
  </div>
</div>
""",
    5: """\
<div style="position: absolute; inset: 0; background: var(--a)">
  <div style="position: absolute; inset: var(--marco); overflow: hidden; border-radius: 2cqmin">
    <img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block">
  </div>
  <div style="position: absolute; inset: var(--pad); display: flex; flex-direction: column; justify-content: space-between; align-items: flex-start">
    <div class="t" data-e="marca" style="margin: 2.5cqmin; background: var(--d); color: var(--l); padding: 1cqmin 2.4cqmin; font-weight: 700; font-size: calc(var(--s-k)*var(--esc))">«logo»</div>
    <div class="t" data-e="titulo" style="background: var(--b); color: var(--tb); padding: 2.6cqmin 3.4cqmin; transform: rotate(-2deg); margin: 0 2cqmin 3cqmin; font-family: var(--ft, 'Bebas Neue'), sans-serif; font-size: calc(var(--s-l)*var(--esc)); line-height: 1">«titulo»</div>
  </div>
</div>
""",
    6: """\
<div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); background: var(--l); color: var(--d); display: flex; flex-direction: column; gap: 2cqmin">
  <div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 0.5cqmin solid var(--d); padding-bottom: 1cqmin; gap: 2cqmin">
    <div class="t" data-e="marca" style="font-family: var(--ft, 'Playfair Display'), serif; font-weight: 700; font-size: calc(var(--s-m)*var(--esc))">«logo»</div>
    <div class="t" data-e="tipo" style="font-size: calc(var(--s-k)*var(--esc)); font-weight: 500; text-align: right">«tipo»</div>
  </div>
  <div style="flex: 1 1 0; min-height: 0; display: flex; flex-direction: var(--dir); gap: 3cqmin">
    <div style="flex: 1 1 0; min-height: 0; min-width: 0; overflow: hidden"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
    <div style="flex: 0 1 auto; width: var(--ladoTexto)">
      <div class="t" data-e="kicker" style="color: var(--a); font-weight: 700; font-size: calc(var(--s-k)*var(--esc)); text-transform: uppercase; letter-spacing: 0.1em">«kicker»</div>
      <div class="t" data-e="titulo" style="font-family: var(--ft, 'Playfair Display'), serif; font-style: italic; font-weight: 700; font-size: calc(var(--s-m)*var(--esc)); line-height: 1.1; margin-top: 1cqmin">«titulo»</div>
    </div>
  </div>
</div>
""",
    7: """\
<div style="position: absolute; inset: 0; background: var(--b); color: var(--tb)">
  <div style="position: absolute; left: 0; right: 0; bottom: 0; height: 48%"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: space-between; align-items: flex-start">
    <div style="width: 66%">
      <div class="t" data-e="marca" style="font-weight: 800; font-size: calc(var(--s-k)*var(--esc)); text-transform: uppercase">«logo»</div>
      <div class="t" data-e="titulo" style="font-family: var(--ft, 'Archivo Black'), sans-serif; font-size: calc(var(--s-m)*var(--esc)); line-height: 1.05; margin-top: 1cqmin">«titulo»</div>
    </div>
    <div class="t" data-e="cta" style="background: var(--d); color: var(--l); padding: 1.8cqmin 3.4cqmin; font-weight: 800; font-size: calc(var(--s-c)*var(--esc)); border-radius: 1cqmin">«cta»</div>
  </div>
  <div class="t" data-e="oferta" style="position: absolute; right: var(--dR); top: var(--dT); width: 34cqmin; height: 34cqmin; border-radius: 50%; background: var(--a); color: var(--ta); display: flex; flex-direction: column; align-items: center; justify-content: center; transform: rotate(8deg); text-align: center">
    <div style="font-family: var(--ft, 'Anton'), sans-serif; font-size: 10cqmin; line-height: 1">«oferta»</div>
    <div data-e="oferta_txt" style="font-weight: 700; font-size: 2.8cqmin; margin-top: 1cqmin">«ofertaTxt»</div>
  </div>
</div>
""",
    8: """\
<div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); background: var(--d)">
  <div style="width: 100%; height: 100%; display: grid; grid-template-columns: var(--gCol); grid-template-rows: var(--gFil); gap: 1.6cqmin">
    <div style="grid-column: var(--gTit); background: var(--a); color: var(--ta); border-radius: 2.4cqmin; padding: 3cqmin; display: flex; flex-direction: column; justify-content: flex-end; overflow: hidden">
      <div class="t" data-e="titulo" style="font-family: var(--ft, 'Space Grotesk'), sans-serif; font-weight: 700; font-size: calc(var(--s-m)*var(--esc)); line-height: 1.05">«titulo»</div>
    </div>
    <div style="border-radius: 2.4cqmin; overflow: hidden; min-height: 0"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
    <div style="background: var(--b); color: var(--tb); border-radius: 2.4cqmin; padding: 2.4cqmin; display: flex; flex-direction: column; justify-content: center; overflow: hidden">
      <div class="t" data-e="oferta" style="font-family: var(--ft, 'Space Grotesk'), sans-serif; font-weight: 700; font-size: 8cqmin; line-height: 1">«oferta»</div>
      <div class="t" data-e="oferta_txt" style="font-weight: 500; font-size: calc(var(--s-k)*var(--esc)); margin-top: 0.8cqmin">«ofertaTxt»</div>
    </div>
    <div style="grid-column: var(--gPie); background: var(--l); color: var(--d); border-radius: 2.4cqmin; padding: 2cqmin 3cqmin; display: flex; align-items: center; justify-content: space-between; gap: 2cqmin">
      <div class="t" data-e="cta" style="font-weight: 800; font-size: calc(var(--s-c)*var(--esc))">«cta» →</div>
      <div class="t" data-e="marca" style="font-weight: 700; font-size: calc(var(--s-k)*var(--esc)); text-align: right">«logo»</div>
    </div>
  </div>
</div>
""",
    9: """\
<div style="position: absolute; inset: 0; background: var(--d); color: var(--l)">
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: center; gap: 2.4cqmin">
    <div style="font-family: var(--ft, 'DM Serif Display'), serif; font-size: 26cqmin; line-height: 0.6; height: 11cqmin; color: var(--a)">“</div>
    <div class="t" data-e="cita" style="font-family: var(--ft, 'DM Serif Display'), serif; font-size: calc(var(--s-m)*var(--esc)); line-height: 1.15">«cita»</div>
    <div style="display: flex; align-items: center; gap: 2.4cqmin; margin-top: 1.4cqmin">
      <img src="«img»" alt="Imagen de ejemplo" style="width: 13cqmin; height: 13cqmin; border-radius: 50%; object-fit: cover; border: 0.7cqmin solid var(--a)">
      <div>
        <div class="t" data-e="autor" style="font-weight: 700; font-size: calc(var(--s-c)*var(--esc))">«autor»</div>
        <div class="t" data-e="marca" style="font-size: calc(var(--s-k)*var(--esc)); opacity: 0.85">«logo»</div>
      </div>
    </div>
  </div>
</div>
""",
    10: """\
<div style="position: absolute; inset: 0; background: var(--d)">
  <img src="«img»" alt="Imagen de ejemplo" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0.4">
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: center; align-items: flex-start; gap: 2.4cqmin">
    <div class="t" data-e="kicker" style="color: var(--b); font-weight: 700; font-size: calc(var(--s-k)*var(--esc)); letter-spacing: 0.14em; text-transform: uppercase">«kicker»</div>
    <div class="t" data-e="titulo" style="font-family: var(--ft, 'Bebas Neue'), sans-serif; font-size: calc(var(--s-xl)*var(--esc)); line-height: 0.98; color: #fff; text-shadow: 0 0 2cqmin var(--a), 0 0 5cqmin var(--a)">«titulo»</div>
    <div class="t" data-e="cta" style="border: 0.5cqmin solid var(--b); color: var(--b); padding: 1.4cqmin 3cqmin; border-radius: 99px; font-weight: 700; font-size: calc(var(--s-c)*var(--esc))">«cta»</div>
    <div class="t" data-e="marca" style="color: #fff; font-weight: 700; font-size: calc(var(--s-k)*var(--esc))">«logo»</div>
  </div>
</div>
""",
    11: """\
<div style="position: absolute; inset: 0; background: var(--a); color: var(--ta)">
  <div style="position: absolute; width: var(--cirT); height: var(--cirT); right: var(--cirR); top: var(--cirA); border-radius: 50%; overflow: hidden; border: 1.6cqmin solid var(--b)"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
  <div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); display: flex; flex-direction: column; justify-content: flex-end; gap: 1.4cqmin">
    <div class="t" data-e="kicker" style="font-weight: 800; font-size: calc(var(--s-k)*var(--esc)); text-transform: uppercase">«kicker»</div>
    <div class="t" data-e="titulo" style="width: var(--mitadC); font-family: var(--ft, 'Syne'), sans-serif; font-weight: 800; font-size: calc(var(--s-s)*var(--esc)); line-height: 1.05">«titulo»</div>
    <div class="t" data-e="cta" style="font-weight: 700; font-size: calc(var(--s-c)*var(--esc))">«cta» · «marca»</div>
  </div>
</div>
""",
    12: """\
<div style="position: absolute; inset: 0; box-sizing: border-box; padding: var(--pad); background: var(--l); color: var(--d); display: flex; flex-direction: var(--dir); gap: 3cqmin">
  <div style="flex: 1 1 0; min-height: 0; min-width: 0; border-radius: 2.4cqmin; overflow: hidden"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
  <div style="flex: 0 1 auto; width: var(--ladoTexto); display: flex; flex-direction: column; gap: 1.6cqmin">
    <div class="t" data-e="titulo" style="font-family: var(--ft, 'Poppins'), sans-serif; font-weight: 800; font-size: calc(var(--s-s)*var(--esc)); line-height: 1.08">«titulo»</div>
    <div style="display: flex; align-items: center; gap: 2cqmin"><div style="flex: none; width: 7cqmin; height: 7cqmin; border-radius: 50%; background: var(--a); color: var(--ta); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 3.4cqmin">1</div><div class="t" data-e="i1" style="font-weight: 500; font-size: calc(var(--s-a)*var(--esc))">«i1»</div></div>
    <div style="display: flex; align-items: center; gap: 2cqmin"><div style="flex: none; width: 7cqmin; height: 7cqmin; border-radius: 50%; background: var(--a); color: var(--ta); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 3.4cqmin">2</div><div class="t" data-e="i2" style="font-weight: 500; font-size: calc(var(--s-a)*var(--esc))">«i2»</div></div>
    <div style="display: flex; align-items: center; gap: 2cqmin"><div style="flex: none; width: 7cqmin; height: 7cqmin; border-radius: 50%; background: var(--a); color: var(--ta); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 3.4cqmin">3</div><div class="t" data-e="i3" style="font-weight: 500; font-size: calc(var(--s-a)*var(--esc))">«i3»</div></div>
  </div>
</div>
""",
    13: """\
<div style="position: absolute; inset: 0; background: var(--d); color: var(--l); display: flex; flex-direction: var(--dir)">
  <div style="flex: 1 1 0; min-height: 0; min-width: 0"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
  <div style="flex: 1 1 0; min-height: 0; min-width: 0; box-sizing: border-box; padding: var(--padEv); display: flex; flex-direction: column; justify-content: center; gap: 1.6cqmin; background: var(--a); color: var(--ta)">
    <div style="display: flex; align-items: flex-end; gap: 2cqmin">
      <div class="t" data-e="dia" style="font-family: var(--ft, 'Anton'), sans-serif; font-size: 18cqmin; line-height: 0.95">«dia»</div>
      <div class="t" data-e="mes" style="font-weight: 800; font-size: calc(var(--s-c)*var(--esc)); text-transform: uppercase; padding-bottom: 1cqmin">«mes»</div>
    </div>
    <div class="t" data-e="titulo" style="font-family: var(--ft, 'Montserrat'), sans-serif; font-weight: 900; font-size: calc(var(--s-s)*var(--esc)); line-height: 1.06">«titulo»</div>
    <div class="t" data-e="lugar" style="font-weight: 500; font-size: calc(var(--s-k)*var(--esc))">«lugar» · «marca»</div>
  </div>
</div>
""",
    14: """\
<div style="position: absolute; inset: 0; background: var(--l); color: var(--d)">
  <div style="position: absolute; inset: var(--pad); border: 0.3cqmin solid var(--d); box-sizing: border-box; padding: 3.4cqmin; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2cqmin; text-align: center">
    <div class="t" data-e="marca" style="font-size: calc(var(--s-k)*var(--esc)); letter-spacing: 0.26em; text-transform: uppercase; font-weight: 500">«logo»</div>
    <div style="flex: 0 1 34cqmin; width: 46cqmin; min-height: 8cqmin; overflow: hidden"><img src="«img»" alt="Imagen de ejemplo" style="width: 100%; height: 100%; object-fit: cover; display: block"></div>
    <div class="t" data-e="titulo" style="font-family: var(--ft, 'Playfair Display'), serif; font-weight: 700; font-size: calc(var(--s-s)*var(--esc)); line-height: 1.12">«titulo»</div>
    <div class="t" data-e="cta" style="font-size: calc(var(--s-k)*var(--esc)); letter-spacing: 0.16em; text-transform: uppercase; color: var(--a); font-weight: 700">«cta»</div>
  </div>
</div>
""",
}

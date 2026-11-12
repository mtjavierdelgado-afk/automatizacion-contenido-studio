/* CrearIA Studio — EL EDITOR CON CAPAS DE GRÁFICAS (rama graficas-2-editor, 12-11-2026).
 *
 * Su propia página dentro del Studio (decisión del dueño, 11-11): este fichero y
 * graficas_editor.css solo se cargan al abrir el editor (`cargarEditorCapas` en
 * app.js). Comparte con el Studio la cabecera de las claves (`pedir`), los avisos
 * y el tema; nada más.
 *
 * Lo que hace, sobre el documento en capas de `pasos/graficas_capas.py`:
 *   - pinta cada capa EN VIVO con el mismo CSS que el servidor (`_html_capa`),
 *     en medidas del lienzo (cqw/cqh/cqmin) y con las mismas letras (las sirve
 *     el Studio: /api/graficas/tipografia/<fichero>);
 *   - añadir, mover, asas, girar, guías con imán, varias a la vez, deshacer,
 *     propiedades con los colores del Kit, «Volver a montar» y el tamaño;
 *   - tras una pausa, el servidor pinta la vista final y se avisa si un texto
 *     parte en otras líneas que en la pantalla;
 *   - guarda con el sello de `graficas-2-capas` (un 409 si la pieza cambió).
 *
 * Nada de aquí toca un vídeo, params ni firmas (regla 1), ni llama a una IA.
 * La CSP no deja atributos `style=""`: todo estilo va por CSSOM (`.style`) o en
 * graficas_editor.css. Las imágenes y letras se piden con la cabecera de las
 * claves y se pintan como data: (la CSP no deja blob: en <img>).
 */
(function () {
  'use strict';

  /* ================================================================ utilidades */

  function el(etiqueta, props, ...hijos) {
    const n = document.createElement(etiqueta);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'clase') n.className = v;
      else if (k === 'texto') n.textContent = v;
      else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
      else if (k === 'value') n.value = v;
      else if (v === true) n.setAttribute(k, '');
      else n.setAttribute(k, v);
    }
    for (const hijo of hijos.flat(3)) {
      if (hijo === null || hijo === undefined || hijo === false) continue;
      n.appendChild(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
    }
    return n;
  }

  const copia = o => JSON.parse(JSON.stringify(o));
  const limitar = (v, a, b) => Math.max(a, Math.min(b, v));
  const redondo = (v, d = 4) => { const k = 10 ** d; return Math.round(v * k) / k; };
  const nuevoId = () => 'c' + Math.random().toString(16).slice(2, 10).padEnd(8, '0');

  /** Un número para CSS, como `_f` del servidor. */
  function f6(n) {
    let t = Number(n).toFixed(6).replace(/0+$/, '').replace(/\.$/, '');
    if (t === '-0' || t === '') t = '0';
    return t;
  }

  /* ================================================================ colores
   * Copia de graficas.py (`_luz`, `contraste`, `_tinta_para`, `colores_finales`)
   * y de graficas_capas.py (`resolver_color`): la pantalla y el PNG, iguales. */

  const ROLES = ['principal', 'secundario', 'acento', 'oscuro', 'claro'];
  const NOMBRE_ROL = { principal: 'Principal', secundario: 'Secundario', acento: 'Acento', oscuro: 'Oscuro', claro: 'Claro' };
  const VAR_ROL = { a: 'principal', b: 'secundario', d: 'oscuro', l: 'claro', x: 'acento' };
  const RE_HEX = /^#[0-9A-F]{6}$/;

  function luz(color) {
    const c = [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16) / 255)
      .map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  }
  function contraste(a, b) {
    const [x, y] = [luz(a), luz(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  }
  function tintaPara(fondo, oscuro, claro) {
    const mejor = contraste(fondo, oscuro) >= contraste(fondo, claro) ? oscuro : claro;
    if (contraste(fondo, mejor) >= 4.5) return mejor;
    return contraste(fondo, '#000000') >= contraste(fondo, '#FFFFFF') ? '#000000' : '#FFFFFF';
  }
  function coloresFinales(defecto, kit, doc) {
    const c = Object.assign({}, defecto, (kit && kit.colores) || {});
    for (const [k, v] of Object.entries((doc && doc.colores) || {})) {
      if (ROLES.includes(k) && /^#[0-9a-fA-F]{6}$/.test(String(v))) c[k] = String(v).toUpperCase();
    }
    for (const k of ROLES) c[k] = String(c[k] || '#000000').toUpperCase();
    return c;
  }
  function resolver(ref, colores) {
    if (!ref) return '#000000';
    if (ref[0] === '#') return ref;
    const [tipo, rol] = ref.split(':');
    if (tipo === 'kit') return colores[rol];
    return tintaPara(colores[rol], colores.oscuro, colores.claro);
  }
  function cssColor(ref, alfa, colores) {
    const c = resolver(ref, colores);
    if (alfa === undefined || alfa >= 1) return c;
    const [r, g, b] = [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));
    return `rgba(${r},${g},${b},${f6(alfa)})`;
  }
  function cssRelleno(rel, colores) {
    if (!rel) return '';
    if (rel.degradado) {
      const d = rel.degradado;
      const paradas = d.paradas.map(p => cssColor(p.color, p.alfa, colores) + (p.pos === null || p.pos === undefined ? '' : ` ${f6(p.pos)}%`)).join(', ');
      return `background:linear-gradient(${f6(d.ang)}deg, ${paradas});`;
    }
    return `background:${cssColor(rel.color, rel.alfa, colores)};`;
  }
  function cssBorde(b, colores) {
    if (!b || !b.anchos || !b.anchos.some(Boolean)) return '';
    const anchos = b.anchos.map(a => (a ? `calc(${f6(a)}cqmin + 0.01px)` : '0')).join(' ');
    return `border-style:solid;border-width:${anchos};border-color:${cssColor(b.color, b.alfa, colores)};`;
  }
  function cssRadio(r) {
    if (r === 'elipse') return 'border-radius:50%;';
    return r ? `border-radius:${f6(r)}cqmin;` : '';
  }
  function cssSombras(lista, colores, prop) {
    if (!lista || !lista.length) return '';
    const partes = lista.map(s => {
      const c = cssColor(s.color, s.alfa, colores);
      return prop === 'box-shadow'
        ? `${c} ${f6(s.x)}cqmin ${f6(s.y)}cqmin ${f6(s.blur)}cqmin ${f6(s.spread || 0)}cqmin`
        : `${c} ${f6(s.x)}cqmin ${f6(s.y)}cqmin ${f6(s.blur)}cqmin`;
    });
    return `${prop}:${partes.join(', ')};`;
  }
  function cssCaja(c, altoFijo = true, holgura = 0) {
    let s = `position:absolute;box-sizing:border-box;left:calc(${f6(c.x)}cqw + ${f6(0.002 - holgura)}px);`
      + `top:calc(${f6(c.y)}cqh + 0.002px);width:calc(${f6(c.w)}cqw + 0.002px);`;
    if (altoFijo) s += `height:calc(${f6(c.h)}cqh + 0.002px);`;
    if (c.giro) {
      s += `transform:rotate(${f6(c.giro)}deg);`;
      const o = c.origen || [50, 50];
      s += `transform-origin:calc(${f6(o[0] / 100 * c.w)}cqw + ${f6(holgura)}px) ${f6(o[1] / 100 * c.h)}cqh;`;
    }
    if (c.opac !== undefined && c.opac < 1) s += `opacity:${f6(c.opac)};`;
    return s;
  }

  /* ================================================================ el editor */

  const CAMPOS_DE_MUESTRA = {
    marca: '', tipo: 'Tu negocio', kicker: 'Novedad', titulo: 'Tu titular aquí', apoyo: 'Un texto corto que lo explica',
    cta: 'Reserva ya', oferta: '-20%', oferta_txt: 'Solo esta semana', dia: '15', mes: 'Diciembre',
    lugar: 'Lugar del evento', i1: 'Elige', i2: 'Reserva', i3: 'Disfruta', cita: '«Volveremos seguro»', autor: 'Ana, clienta',
  };
  const PESOS = [300, 400, 500, 600, 700, 800, 900];
  /** Los topes de `graficas_capas.py` (MAX_CAPAS, MAX_FOTOS, MAX_TEXTO): lo comprueba la suite. */
  const LIMITES = { capas: 60, fotos: 8, texto: 600 };
  const MAX_HIST = 150;

  let ED = null;          // el editor abierto (uno a la vez)
  /** Las letras ya registradas en esta página: se cargan una vez, aunque el
   * editor se abra y se cierre muchas veces (fid -> promesa). */
  const LETRAS_DE_LA_PAGINA = {};

  /**
   * Abre el editor.
   * opc: { cid, nombreCliente, pieza (ficha de la lista o null), catalogo, kit,
   *        api(cid, resto), pedir(url, opciones), pases(), toast(texto, malo),
   *        alCerrar(cambio) }
   */
  async function abrir(opc) {
    if (ED) cerrarYa(false);
    const raiz = el('div', { clase: 'ce', id: 'editor-capas', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Editor de gráficas con capas' });
    ED = {
      opc, raiz, cid: opc.cid, cat: opc.catalogo, kit: opc.kit || {},
      piezaId: opc.pieza && opc.pieza.id ? opc.pieza.id : '',
      nacida: false, origen: { plantilla: null, sello: '', guardado: '', nacida: false },
      doc: null, lamina: 0, sel: [], hist: [], pos: -1, guardado: '', escala: 1, zoom: 0,
      iman: true, tapa: false, fotos: {}, logos: { normal: null, oscuro: null }, letras: {},
      vista: { turno: 0, temporizador: null, pidiendo: false, otra: false, img: '', avisos: [], lineas: {}, de: '' },
      editando: null, arrastre: null, avisos: [], cerrado: false, guardando: false, ultimoToque: { id: '', t: 0 },
    };
    document.body.appendChild(raiz);
    document.body.classList.add('ce-abierto');
    raiz.appendChild(el('div', { clase: 'ce-cargando' }, 'Abriendo el editor con capas…'));
    const yo = ED;
    try {
      await prepararDoc(yo);
    } catch (e) {
      // solo si sigue siendo este editor: otro abierto mientras tanto no se toca
      if (ED === yo) cerrarYa(false);
      opc.toast(e.message || String(e), true);
      return;
    }
    if (ED !== yo || yo.cerrado) return;
    montarPantalla();
    cargarLogos();
    cargarFotosDelDoc();
    cargarLetrasDelDoc();
    pintarTodo();
    commit(true);
    ED.guardado = firmaDoc();
    pintarEstado();
    pedirVista();
  }

  /** Prepara el documento de ESTE editor (`E`): tras cada espera se escribe en
   * él y no en `ED`, que puede ser ya otro (doble clic al abrir). */
  async function prepararDoc(E) {
    const o = E.opc;
    if (E.piezaId) {
      const r = await o.pedir(o.api(E.cid, `/piezas/${E.piezaId}/capas`));
      E.doc = r.doc;
      E.convertida = r.origen === 'convertida';
    } else {
      // una pieza nueva: la plantilla elegida (1, «Titular gigante», sin foto)
      const textos = Object.assign({}, CAMPOS_DE_MUESTRA, { marca: o.nombreCliente || 'Tu marca' });
      const r = await o.pedir(o.api(E.cid, '/capas/montar'), {
        method: 'POST', cuerpo: { plantilla: o.plantilla || 1, formato: o.formato || E.cat.formato_defecto, textos } });
      E.doc = r.doc;
      E.doc.nombre = '';
      E.convertida = false;
    }
    E.origen = Object.assign({}, E.doc.origen || {});
    E.nacida = !!E.origen.nacida;
    if (o.duplicar) {
      // «Duplicar»: el mismo diseño, que se guarda como una pieza nueva
      E.piezaId = '';
      E.convertida = false;
      E.origen = { plantilla: E.origen.plantilla, sello: '', guardado: '', nacida: true };
      E.nacida = true;
      E.doc.nombre = `${E.doc.nombre || 'Pieza'} (copia)`.slice(0, 80);
    }
    delete E.doc.origen;
    for (const k of ['avisos', 'cambiada', 'medida']) delete E.doc[k];
  }

  /* ---------------------------------------------------------------- historial
   * Lo que se guarda en el historial es el documento SIN su `origen` (el sello
   * con el que se guarda): deshacer hasta antes de un guardado no puede traer
   * un sello viejo, o el siguiente «Guardar» daría un 409 sin motivo. */

  const firmaDoc = () => JSON.stringify(ED.doc);

  function commit(primero) {
    const s = firmaDoc();
    if (!primero && s === ED.hist[ED.pos]) return false;   // entrar en un campo no es un cambio
    ED.hist = ED.hist.slice(0, ED.pos + 1);
    ED.hist.push(s);
    if (ED.hist.length > MAX_HIST) ED.hist.shift();
    ED.pos = ED.hist.length - 1;
    if (!primero) { pintarEstado(); programarVista(); }
    return true;
  }

  function irAHistoria(paso) {
    const destino = ED.pos + paso;
    if (destino < 0 || destino >= ED.hist.length) return;
    terminarEdicionTexto(false);
    ED.pos = destino;
    ED.doc = JSON.parse(ED.hist[ED.pos]);
    const vivos = new Set(capas().map(c => c.id));
    ED.sel = ED.sel.filter(id => vivos.has(id));
    cargarFotosDelDoc();
    cargarLetrasDelDoc();
    pintarTodo();
    pintarPaneles();
    pintarEstado();
    programarVista();
  }

  /* ---------------------------------------------------------------- acceso */

  const capas = () => ED.doc.laminas[ED.lamina].capas;
  const capa = id => capas().find(c => c.id === id);
  const seleccion = () => ED.sel.map(capa).filter(Boolean);
  const formato = () => ED.cat.formatos.find(f => f.id === ED.doc.formato) || ED.cat.formatos[0];
  const colores = () => coloresFinales(ED.cat.colores_defecto, ED.kit, ED.doc);
  const minLado = () => Math.min(formato().W, formato().H);

  /** Los márgenes de la plantilla (`_variables`): lo que se aparta de lo que tapa la red. */
  function margenes() {
    const f = formato();
    const mg = f.W / f.H > 1.3 ? 5 : 6;
    return { t: Math.max(mg, f.zT + 2), r: Math.max(mg, f.zR + 2), b: Math.max(mg, f.zB + 2), l: Math.max(mg, f.zL + 2) };
  }

  /* ================================================================ letras */

  function familiaDe(c) {
    const fu = c.fuente || {};
    let fid = fu.id;
    if (fu.rol === 'titulos') fid = ED.doc.fuente_titulos || ED.kit.fuente_titulos || fid;
    else if (fu.rol === 'texto') fid = ED.doc.fuente_texto || ED.kit.fuente_texto || fid || 'poppins';
    if (!ED.cat.familias[fid]) fid = 'poppins';
    return fid;
  }

  /** Cada letra se registra con un nombre propio («ce-…»): así no se mezcla
   * con la Inter o la Space Grotesk que ya usa la interfaz del Studio. */
  function cargarLetra(fid) {
    if (ED.letras[fid] || !ED.cat.caras || !ED.cat.caras[fid]) return;
    const yo = ED;
    yo.letras[fid] = 'cargando';
    const familia = `ce-${yo.cat.familias[fid]}`;
    if (!LETRAS_DE_LA_PAGINA[fid]) {
      LETRAS_DE_LA_PAGINA[fid] = Promise.all(yo.cat.caras[fid].map(async cara => {
        const r = await fetch(`${yo.opc.base}/api/graficas/tipografia/${encodeURIComponent(cara.fichero)}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const ff = new FontFace(familia, await r.arrayBuffer(), { weight: cara.pesos, style: cara.estilo });
        await ff.load();
        document.fonts.add(ff);
      })).catch(e => { delete LETRAS_DE_LA_PAGINA[fid]; throw e; });
    }
    LETRAS_DE_LA_PAGINA[fid].then(() => {
      if (ED !== yo) return;
      yo.letras[fid] = 'lista';
      pintarTodo();
    }).catch(() => {
      if (ED !== yo) return;
      yo.letras[fid] = 'falta';
      avisoPantalla(`La letra ${yo.cat.familias[fid]} aún no está en el servidor: en pantalla se ve una parecida.`);
    });
  }

  function cargarLetrasDelDoc() {
    for (const c of capas()) if (c.tipo === 'texto') cargarLetra(familiaDe(c));
  }

  /* ================================================================ fotos y logo */

  async function comoDataUrl(url) {
    const pases = ED.opc.pases();
    const r = await fetch(url, { headers: pases ? { 'X-Estudio-Abiertos': pases } : {} });
    if (!r.ok) { const e = new Error(`HTTP ${r.status}`); e.status = r.status; throw e; }
    const blob = await r.blob();
    const datos = await new Promise((ok, mal) => {
      const lector = new FileReader();
      lector.onload = () => ok(lector.result);
      lector.onerror = () => mal(lector.error);
      lector.readAsDataURL(blob);
    });
    const tam = await new Promise(ok => {
      const im = new Image();
      im.onload = () => ok([im.naturalWidth, im.naturalHeight]);
      im.onerror = () => ok([0, 0]);
      im.src = datos;
    });
    return { url: datos, iw: tam[0], ih: tam[1] };
  }

  function cargarFoto(nombre) {
    if (!nombre || ED.fotos[nombre]) return;
    const yo = ED;
    yo.fotos[nombre] = { cargando: true };
    comoDataUrl(yo.opc.api(yo.cid, `/imagen/${encodeURIComponent(nombre)}`))
      .then(f => { yo.fotos[nombre] = f; if (ED === yo) pintarTodo(); })
      .catch(() => { yo.fotos[nombre] = { falta: true }; if (ED === yo) pintarTodo(); });
  }

  function cargarFotosDelDoc() {
    for (const c of capas()) if (c.tipo === 'imagen' && c.src) cargarFoto(c.src);
  }

  function cargarLogos() {
    const yo = ED;
    for (const variante of ['normal', 'oscuro']) {
      comoDataUrl(yo.opc.api(yo.cid, `/logo/${variante}`))
        .then(f => { yo.logos[variante] = f; if (ED === yo) { pintarTodo(); pintarPaneles(); } })
        .catch(() => {});
    }
  }

  function logoDe(c, col) {
    const { normal, oscuro } = ED.logos;
    let elegido = normal;
    if (oscuro && (c.variante === 'oscuro' || (c.variante !== 'normal' && luz(col[VAR_ROL[c.fondo_auto] || 'claro']) < 0.3))) elegido = oscuro;
    return elegido;
  }

  /** `encaje` del servidor: dónde va la foto dentro de su caja (en % de la caja de dentro del borde). */
  function encaje(c, iw, ih) {
    const f = formato();
    const m = minLado() / 100;
    const an = (c.borde && c.borde.anchos) || [0, 0, 0, 0];
    const bw = c.w / 100 * f.W - (an[1] + an[3]) * m;
    const bh = c.h / 100 * f.H - (an[0] + an[2]) * m;
    if (bw <= 0 || bh <= 0 || !iw || !ih) return [0, 0, 100, 100];
    const enc = c.encuadre || { x: 50, y: 50, zoom: 1 };
    const sw = iw / enc.zoom, sh = ih / enc.zoom;
    const sx = (iw - sw) * enc.x / 100, sy = (ih - sh) * enc.y / 100;
    const k = Math.max(bw / sw, bh / sh);
    const ox = (bw - sw * k) * enc.x / 100, oy = (bh - sh * k) * enc.y / 100;
    return [(ox - sx * k) / bw * 100, (oy - sy * k) / bh * 100, iw * k / bw * 100, ih * k / bh * 100];
  }

  /* ================================================================ pintar */

  /** El nodo de una capa: el mismo CSS que `_html_capa` del servidor. */
  function nodoCapa(c, col) {
    if (c.oculto) return null;
    if (c.recorte) {
      const r = c.recorte;
      const dentro = nodoCapa(Object.assign({}, c, { recorte: null, x: c.x - r.x, y: c.y - r.y }), col);
      if (!dentro) return null;
      const caja = el('div', { 'data-recorte': c.id });
      caja.style.cssText = `position:absolute;overflow:hidden;left:calc(${f6(r.x)}cqw + 0.002px);`
        + `top:calc(${f6(r.y)}cqh + 0.002px);width:calc(${f6(r.w)}cqw + 0.002px);`
        + `height:calc(${f6(r.h)}cqh + 0.002px);${cssRadio(r.radio)}`;
      caja.appendChild(dentro);
      return caja;
    }
    let n;
    if (c.tipo === 'forma') {
      let s = cssCaja(c) + cssRelleno(c.relleno, col) + cssBorde(c.borde, col) + cssSombras(c.sombra, col, 'box-shadow');
      s += c.figura === 'elipse' ? 'border-radius:50%;' : cssRadio(c.radio);
      if (c.figura === 'poligono' && c.puntos && c.puntos.length >= 3) {
        s += `clip-path:polygon(${c.puntos.map(p => `${f6(p[0])}% ${f6(p[1])}%`).join(', ')});`;
      }
      n = el('div');
      n.style.cssText = s;
    } else if (c.tipo === 'imagen') {
      let s = cssCaja(c) + cssBorde(c.borde, col) + cssRadio(c.radio) + cssSombras(c.sombra, col, 'box-shadow') + 'overflow:hidden;';
      const foto = c.src ? ED.fotos[c.src] : null;
      n = el('div');
      if (!foto || !foto.url) {
        // sin foto (o aún cargando): el bloque de color del servidor, nunca una imagen rota
        s += `background:linear-gradient(135deg, ${col.principal}, ${col.secundario});`;
        n.style.cssText = s;
        if (foto && foto.cargando) n.classList.add('ce-cargando-foto');
      } else {
        n.style.cssText = s;
        const [x, y, w, h] = encaje(c, foto.iw, foto.ih);
        const img = el('img', { alt: '', draggable: 'false' });
        img.style.cssText = `position:absolute;display:block;max-width:none;left:${f6(x)}%;top:${f6(y)}%;width:${f6(w)}%;height:${f6(h)}%;`;
        img.src = foto.url;
        n.appendChild(img);
      }
    } else if (c.tipo === 'logo') {
      const logo = logoDe(c, col);
      n = el('div');
      n.style.cssText = cssCaja(c);
      if (logo && logo.url) {
        const img = el('img', { alt: '', draggable: 'false' });
        img.style.cssText = 'display:block;width:100%;height:100%;max-width:none;max-height:none;object-fit:contain';
        img.src = logo.url;
        n.appendChild(img);
      } else {
        // sin logo subido el PNG no lo pinta; en pantalla, un hueco para poder cogerla
        n.classList.add('ce-sin-logo');
        n.appendChild(el('span', {}, 'Logo'));
      }
    } else {
      if (!String(c.txt || '').trim()) {
        // un texto vacío no sale en el PNG; aquí, un hueco para poder escribirlo
        n = el('div', { clase: 'ce-texto-vacio' });
        n.style.cssText = cssCaja(c);
        n.appendChild(el('span', {}, 'Texto vacío'));
      } else {
        const fid = familiaDe(c);
        const holgura = { izq: 0, centro: 0.015625, der: 0.03125 }[c.alin] || 0;
        let s = cssCaja(c, false, holgura);
        s = s.replace(`width:calc(${f6(c.w)}cqw + 0.002px);`, `width:calc(${f6(c.w)}cqw + 0.03325px);`);
        s += `min-height:calc(${f6(c.h)}cqh + 0.002px);display:flex;flex-direction:column;`;
        s += `justify-content:${{ arriba: 'flex-start', centro: 'center', abajo: 'flex-end' }[c.valign] || 'flex-start'};`;
        s += `text-align:${{ izq: 'left', centro: 'center', der: 'right' }[c.alin] || 'left'};`;
        const familia = ED.cat.familias[fid];
        s += `font-family:'ce-${familia}', '${familia}', ${c.fuente && c.fuente.serif ? 'serif' : 'sans-serif'};`;
        s += `font-size:calc(${f6(c.tam)}cqmin * var(--e, 1));font-weight:${c.peso};`;
        s += `font-style:${c.cursiva ? 'italic' : 'normal'};text-decoration:${c.subrayado ? 'underline' : 'none'};`;
        if (c.mayus) s += 'text-transform:uppercase;';
        if (c.espaciado) s += `letter-spacing:${f6(c.espaciado)}em;`;
        s += `line-height:${c.interlineado ? f6(c.interlineado) : 'normal'};`;
        s += `color:${cssColor(c.color, c.alfa, col)};white-space:pre-line;`;
        if (c.relleno && c.relleno.some(Boolean)) s += `padding:${c.relleno.map(p => `${f6(p)}cqmin`).join(' ')};`;
        s += cssRelleno(c.fondo, col) + cssBorde(c.borde, col) + cssRadio(c.radio);
        s += cssSombras(c.sombra, col, 'box-shadow') + cssSombras(c.sombra_texto, col, 'text-shadow');
        n = el('div');
        n.style.cssText = s;
        n.textContent = String(c.txt).trim();
        if (c.ajusta) n.dataset.ajusta = '1';
      }
    }
    n.dataset.c = c.id;
    if (c.bloqueado) n.dataset.bloqueado = '1';
    return n;
  }

  /** `_AJUSTAR` del servidor: un texto que «ajusta» baja su letra hasta caber. */
  function ajustar(nodo, c) {
    if (!nodo || !nodo.dataset || !nodo.dataset.ajusta) return;
    const k = ED.lienzo.clientWidth / formato().W;
    const max = c.h / 100 * formato().H * k;
    const tol = 2 * k;
    let s = 1;
    nodo.style.setProperty('--e', '1');
    while ((nodo.offsetHeight > max + tol || nodo.scrollWidth > nodo.clientWidth + tol) && s > 0.6) {
      s = Math.round((s - 0.05) * 100) / 100;
      nodo.style.setProperty('--e', String(s));
    }
  }

  function pintarTodo() {
    if (!ED || !ED.lienzo) return;
    const col = colores();
    const L = ED.lienzo;
    // EL TEXTO QUE SE ESTÁ ESCRIBIENDO NO SE QUITA NI SE MUEVE: quitar un nodo
    // con el foco dispara su «blur» (acababa la edición y las teclas siguientes
    // iban a los atajos: Retroceso borraba la capa). Se repinta alrededor.
    const quieto = ED.editando ? nodoDe(ED.editando) : null;
    const fijo = quieto ? (quieto.parentElement !== L ? quieto.parentElement : quieto) : null;
    for (const n of [...L.childNodes]) if (n !== fijo) n.remove();
    L.style.background = col.oscuro;
    let pasado = false;
    for (const c of capas()) {
      if (fijo && c.id === ED.editando) { pasado = true; continue; }
      const n = nodoCapa(c, col);
      if (!n) continue;
      if (fijo && !pasado) L.insertBefore(n, fijo); else L.appendChild(n);
      ajustar(n.dataset.recorte ? n.firstChild : n, c);
    }
    pintarMarcas();
  }

  /** Solo una capa (mover, asas): mucho más barato que repintar todo. */
  function pintarCapa(id) {
    if (ED.editando === id) return;        // el que se escribe no se rehace (ver pintarTodo)
    const c = capa(id);
    const viejo = ED.lienzo.querySelector(`[data-c="${id}"]`);
    const caja = viejo && viejo.parentElement && viejo.parentElement.dataset.recorte === id ? viejo.parentElement : viejo;
    if (!c || !caja) { pintarTodo(); return; }
    const n = nodoCapa(c, colores());
    if (!n) { caja.remove(); return; }
    caja.replaceWith(n);
    ajustar(n.dataset.recorte ? n.firstChild : n, c);
  }

  /* ================================================================ geometría
   * Todo en píxeles del lienzo en pantalla. Una capa es su caja SIN girar
   * (x, y, w, h) y su giro alrededor de su origen (en % de la caja). */

  function nodoDe(id) { return ED.lienzo.querySelector(`[data-c="${id}"]`); }

  function caja(c) {
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    const x = c.x / 100 * W, y = c.y / 100 * H, w = c.w / 100 * W;
    let h = c.h / 100 * H;
    if (c.tipo === 'texto') {
      const n = nodoDe(c.id);
      if (n && n.offsetHeight) h = Math.max(h, n.offsetHeight);
    }
    const o = c.origen || [50, 50];
    // el punto de giro va en % de la caja con el alto GUARDADO (como el servidor)
    return { x, y, w, h, giro: c.giro || 0, ox: o[0] / 100 * w, oy: o[1] / 100 * (c.h / 100 * H) };
  }

  const rot = (px, py, grados) => {
    const a = grados * Math.PI / 180, co = Math.cos(a), si = Math.sin(a);
    return [px * co - py * si, px * si + py * co];
  };

  /** Las cuatro esquinas en pantalla (con el giro). */
  function esquinas(k) {
    return [[0, 0], [k.w, 0], [k.w, k.h], [0, k.h]].map(([px, py]) => {
      const [rx, ry] = rot(px - k.ox, py - k.oy, k.giro);
      return [k.x + k.ox + rx, k.y + k.oy + ry];
    });
  }

  /** La caja que la contiene, sin girar (para guías, imán y seleccionar con un recuadro). */
  function aabb(c) {
    const e = esquinas(caja(c));
    const xs = e.map(p => p[0]), ys = e.map(p => p[1]);
    const l = Math.min(...xs), t = Math.min(...ys);
    return { l, t, r: Math.max(...xs), b: Math.max(...ys), w: Math.max(...xs) - l, h: Math.max(...ys) - t };
  }

  function union(lista) {
    if (!lista.length) return null;
    const cs = lista.map(aabb);
    const l = Math.min(...cs.map(c => c.l)), t = Math.min(...cs.map(c => c.t));
    const r = Math.max(...cs.map(c => c.r)), b = Math.max(...cs.map(c => c.b));
    return { l, t, r, b, w: r - l, h: b - t };
  }

  /* ================================================================ marcas
   * La capa de encima del lienzo: el recuadro de lo elegido, las asas, el
   * giro, las guías, lo que tapa la red y el recuadro para elegir varias. */

  function pintarMarcas() {
    const M = ED.marcas;
    if (!M) return;
    M.textContent = '';
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    if (ED.tapa) {
      const f = formato();
      const zonas = [['t', 0, 0, 100, f.zT], ['b', 0, 100 - f.zB, 100, f.zB], ['l', 0, 0, f.zL, 100], ['r', 100 - f.zR, 0, f.zR, 100]];
      for (const [lado, x, y, w, h] of zonas) {
        if (!w || !h) continue;
        const z = el('div', { clase: `ce-tapa ce-tapa-${lado}` });
        Object.assign(z.style, { left: `${x}%`, top: `${y}%`, width: `${w}%`, height: `${h}%` });
        M.appendChild(z);
      }
      const m = margenes();
      const marco = el('div', { clase: 'ce-margen' });
      Object.assign(marco.style, { left: `${m.l}%`, top: `${m.t}%`, right: `${m.r}%`, bottom: `${m.b}%` });
      M.appendChild(marco);
    }
    const elegidas = seleccion();
    if (elegidas.length === 1 && !ED.editando) {
      const c = elegidas[0];
      const k = caja(c);
      const marco = el('div', { clase: 'ce-elegida' + (c.bloqueado ? ' bloqueada' : '') });
      Object.assign(marco.style, { left: `${k.x}px`, top: `${k.y}px`, width: `${k.w}px`, height: `${k.h}px`,
        transformOrigin: `${k.ox}px ${k.oy}px`, transform: `rotate(${k.giro}deg)` });
      marco.dataset.mover = c.id;
      if (!c.bloqueado) {
        const asas = c.tipo === 'texto' ? ['nw', 'ne', 'se', 'sw', 'e', 'w'] : ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
        for (const a of asas) marco.appendChild(el('div', { clase: `ce-asa ce-asa-${a}`, 'data-asa': a, title: c.tipo === 'texto' && a.length === 2 ? 'Cambia el tamaño de la letra' : 'Cambia el tamaño' }));
        marco.appendChild(el('div', { clase: 'ce-girar', 'data-girar': '1', title: 'Girar (Mayús: de 15 en 15°)' }, '⟳'));
      }
      M.appendChild(marco);
    } else if (elegidas.length > 1) {
      for (const c of elegidas) {
        const k = caja(c);
        const marco = el('div', { clase: 'ce-elegida varias' });
        Object.assign(marco.style, { left: `${k.x}px`, top: `${k.y}px`, width: `${k.w}px`, height: `${k.h}px`,
          transformOrigin: `${k.ox}px ${k.oy}px`, transform: `rotate(${k.giro}deg)` });
        marco.dataset.mover = c.id;
        M.appendChild(marco);
      }
      const u = union(elegidas);
      const todo = el('div', { clase: 'ce-grupo' });
      Object.assign(todo.style, { left: `${u.l}px`, top: `${u.t}px`, width: `${u.w}px`, height: `${u.h}px` });
      M.appendChild(todo);
    }
    const a = ED.arrastre;
    if (a && a.guias) {
      for (const g of a.guias) {
        const linea = el('div', { clase: `ce-guia ${g.eje}` });
        if (g.eje === 'v') Object.assign(linea.style, { left: `${g.en}px`, top: '0', height: `${H}px` });
        else Object.assign(linea.style, { top: `${g.en}px`, left: '0', width: `${W}px` });
        M.appendChild(linea);
      }
    }
    if (a && a.tipo === 'recuadro' && a.rect) {
      const r = a.rect;
      const q = el('div', { clase: 'ce-recuadro' });
      Object.assign(q.style, { left: `${r.l}px`, top: `${r.t}px`, width: `${r.w}px`, height: `${r.h}px` });
      M.appendChild(q);
    }
    if (a && a.etiqueta) {
      const e = el('div', { clase: 'ce-medida' }, a.etiqueta);
      Object.assign(e.style, { left: `${a.ex}px`, top: `${a.ey}px` });
      M.appendChild(e);
    }
  }

  /* ================================================================ pantalla */

  function montarPantalla() {
    const R = ED.raiz;
    R.textContent = '';
    const barra = el('header', { clase: 'ce-barra' });
    ED.barra = barra;
    R.appendChild(barra);
    ED.aviso = el('div', { clase: 'ce-aviso', role: 'status', 'aria-live': 'polite' });
    R.appendChild(ED.aviso);
    if (ED.convertida) {
      R.appendChild(el('div', { clase: 'ce-migra' },
        el('span', {}, el('b', {}, 'Pieza guardada antes del cambio. '),
          'Se abrió convertida en capas y se ve igual que antes. No se guarda nada hasta que pulses «Guardar»; la versión anterior se queda intacta.'),
        el('button', { clase: 'ce-btn', onclick: ev => ev.currentTarget.parentElement.remove() }, 'Entendido')));
    }
    const zona = el('div', { clase: 'ce-zona' });
    ED.izq = el('aside', { clase: 'ce-panel ce-izq', 'aria-label': 'Añadir y capas' });
    ED.escenario = el('main', { clase: 'ce-escenario', 'aria-label': 'Lienzo' });
    ED.der = el('aside', { clase: 'ce-panel ce-der', 'aria-label': 'Propiedades' });
    zona.append(ED.izq, ED.escenario, ED.der);
    R.appendChild(zona);
    ED.marco = el('div', { clase: 'ce-marco' });
    ED.lienzo = el('div', { clase: 'ce-lienzo' });
    ED.marcas = el('div', { clase: 'ce-marcas' });
    ED.marco.append(ED.lienzo, ED.marcas);
    ED.escenario.appendChild(ED.marco);
    ED.escenario.addEventListener('pointerdown', alPulsar);
    ED.escenario.addEventListener('dblclick', alDobleClic);
    ED.ajusteVentana = () => { medirLienzo(); pintarTodo(); };
    window.addEventListener('resize', ED.ajusteVentana);
    ED.teclas = alTeclear;
    document.addEventListener('keydown', ED.teclas, true);
    for (const tipo of ['keydown', 'keyup', 'keypress']) R.addEventListener(tipo, ev => ev.stopPropagation());
    ED.antesDeSalir = ev => { if (sinGuardar()) { ev.preventDefault(); ev.returnValue = ''; } };
    window.addEventListener('beforeunload', ED.antesDeSalir);
    medirLienzo();
    pintarBarra();
    pintarPaneles();
  }

  /** El lienzo, del tamaño que cabe en el escenario (o con el zoom pedido). */
  function medirLienzo() {
    const f = formato();
    // lo que deja el relleno del escenario (24 a los lados, 40 arriba para el asa de girar)
    const ancho = Math.max(160, ED.escenario.clientWidth - 48);
    const alto = Math.max(160, (ED.escenario.clientHeight || window.innerHeight * 0.6) - 64);
    const cabe = Math.min(ancho / f.W, alto / f.H);
    ED.escala = ED.zoom ? ED.zoom : cabe;
    const w = Math.round(f.W * ED.escala), h = Math.round(f.H * ED.escala);
    for (const n of [ED.marco, ED.lienzo, ED.marcas]) { n.style.width = `${w}px`; n.style.height = `${h}px`; }
  }

  function boton(texto, props, alPulsarBoton) {
    return el('button', Object.assign({ clase: 'ce-btn', type: 'button', onclick: alPulsarBoton }, props || {}), texto);
  }

  function pintarBarra() {
    const B = ED.barra;
    B.textContent = '';
    B.appendChild(boton('← Volver', { title: 'Cerrar el editor', clase: 'ce-btn ce-volver' }, () => cerrar()));
    ED.titulo = el('span', { clase: 'ce-titulo' });
    B.appendChild(ED.titulo);
    ED.estado = el('span', { clase: 'ce-estado', role: 'status' });
    B.appendChild(ED.estado);
    B.appendChild(el('span', { clase: 'ce-crece' }));
    ED.bDeshacer = boton('↶', { title: 'Deshacer (Ctrl+Z)', 'aria-label': 'Deshacer' }, () => irAHistoria(-1));
    ED.bRehacer = boton('↷', { title: 'Rehacer (Ctrl+Y)', 'aria-label': 'Rehacer' }, () => irAHistoria(1));
    B.append(ED.bDeshacer, ED.bRehacer);
    B.appendChild(el('span', { clase: 'ce-sep' }));
    B.appendChild(boton('−', { title: 'Alejar', 'aria-label': 'Alejar' }, () => cambiarZoom(-1)));
    ED.bZoom = boton('Ajustar', { title: 'Que quepa entero' }, () => cambiarZoom(0));
    B.appendChild(ED.bZoom);
    B.appendChild(boton('+', { title: 'Acercar', 'aria-label': 'Acercar' }, () => cambiarZoom(1)));
    B.appendChild(el('span', { clase: 'ce-sep' }));
    const tapa = boton('Ver lo que tapa la red', { 'aria-pressed': String(ED.tapa) }, ev => {
      ED.tapa = !ED.tapa;
      ev.currentTarget.setAttribute('aria-pressed', String(ED.tapa));
      pintarMarcas();
    });
    const iman = boton('Imán y guías', { 'aria-pressed': String(ED.iman), title: 'Las capas se pegan a los bordes, al centro, al margen y a las demás (Alt al arrastrar lo suelta)' }, ev => {
      ED.iman = !ED.iman;
      ev.currentTarget.setAttribute('aria-pressed', String(ED.iman));
    });
    B.append(tapa, iman);
    if (ED.piezaId && !ED.nacida) {
      B.appendChild(boton('Ver la versión anterior', { title: 'La pieza tal como estaba antes de pasarla a capas' }, verVersionAnterior));
    }
    ED.bGuardar = boton('Guardar', { clase: 'ce-btn ce-primario', title: 'Guardar y pintar el PNG y el JPG (Ctrl+S)' }, () => guardar());
    B.appendChild(ED.bGuardar);
    pintarEstado();
  }

  function cambiarZoom(paso) {
    if (!paso) ED.zoom = 0;
    else {
      const actual = ED.escala;
      const pasos = [0.1, 0.15, 0.2, 0.25, 0.33, 0.4, 0.5, 0.67, 0.75, 1, 1.25, 1.5, 2];
      ED.zoom = paso > 0 ? (pasos.find(p => p > actual + 0.001) || 2) : ([...pasos].reverse().find(p => p < actual - 0.001) || 0.1);
    }
    medirLienzo();
    pintarTodo();
    ED.bZoom.textContent = ED.zoom ? `${Math.round(ED.zoom * 100)} %` : 'Ajustar';
  }

  const sinGuardar = () => !!ED && !!ED.doc && firmaDoc() !== ED.guardado;

  function pintarEstado() {
    if (!ED || !ED.estado) return;
    ED.titulo.textContent = ED.doc.nombre || (ED.piezaId ? 'Pieza sin nombre' : 'Pieza nueva');
    ED.estado.textContent = ED.guardando ? 'Guardando…' : (sinGuardar() ? 'Sin guardar' : (ED.piezaId ? 'Guardado ✓' : ''));
    ED.estado.classList.toggle('pendiente', sinGuardar());
    ED.bDeshacer.disabled = ED.pos <= 0;
    ED.bRehacer.disabled = ED.pos >= ED.hist.length - 1;
    ED.bGuardar.disabled = ED.guardando || (!!ED.piezaId && !sinGuardar());
  }

  function avisoPantalla(texto, malo) {
    if (!ED || !ED.aviso) return;
    ED.aviso.textContent = texto;
    ED.aviso.classList.toggle('malo', !!malo);
    ED.aviso.classList.add('ver');
    clearTimeout(ED.avisoTiempo);
    ED.avisoTiempo = setTimeout(() => ED && ED.aviso && ED.aviso.classList.remove('ver'), malo ? 7000 : 3500);
  }

  /* ================================================================ paneles */

  function pintarPaneles() {
    if (!ED || !ED.izq) return;
    pintarIzquierda();
    pintarDerecha();
  }

  function pintarIzquierda() {
    const P = ED.izq;
    const scroll = P.scrollTop;
    P.textContent = '';
    P.appendChild(el('h2', {}, 'Añadir'));
    const sube = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', clase: 'ce-oculto', id: 'ce-subir-foto',
      onchange: ev => { const f = ev.target.files[0]; ev.target.value = ''; if (f) subirFoto(f, null); } });
    P.appendChild(el('div', { clase: 'ce-anadir' },
      boton('＋ Título', {}, () => anadir('titulo')),
      boton('＋ Texto', {}, () => anadir('texto')),
      boton('＋ Botón', {}, () => anadir('boton')),
      sube, el('label', { clase: 'ce-btn', for: 'ce-subir-foto', tabindex: '0',
        onkeydown: ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); sube.click(); } } }, '＋ Foto'),
      boton('＋ Logo del Kit', { disabled: !(ED.logos.normal || ED.logos.oscuro), title: ED.logos.normal || ED.logos.oscuro ? '' : 'Este proyecto aún no tiene logo: súbelo en «Logo»' }, () => anadir('logo')),
      boton('＋ Rectángulo', {}, () => anadir('rect')),
      boton('＋ Círculo', {}, () => anadir('circulo')),
      boton('＋ Línea', {}, () => anadir('linea'))));
    P.appendChild(el('h2', {}, `Capas (${capas().length})`));
    const lista = el('ol', { clase: 'ce-capas', 'aria-label': 'Capas, de la de arriba a la de abajo' });
    const elegidas = new Set(ED.sel);
    for (const c of [...capas()].reverse()) {
      const fila = el('li', { clase: 'ce-capa' + (elegidas.has(c.id) ? ' elegida' : '') + (c.oculto ? ' oculta' : ''), 'data-id': c.id });
      const nombre = el('button', { clase: 'ce-capa-nombre', type: 'button', title: 'Elegir (Mayús o Ctrl: varias) · doble clic: cambiar el nombre',
        onclick: ev => { elegir(c.id, ev.shiftKey || ev.ctrlKey || ev.metaKey); },
        ondblclick: () => renombrar(fila, c) },
      el('span', { clase: 'ce-icono' }, iconoDe(c)), el('span', { clase: 'ce-nombre' }, nombreDe(c)));
      fila.append(nombre,
        el('button', { clase: 'ce-mini', type: 'button', 'aria-pressed': String(!c.oculto), title: c.oculto ? 'Enseñar' : 'Ocultar',
          'aria-label': `${c.oculto ? 'Enseñar' : 'Ocultar'} ${nombreDe(c)}`,
          onclick: () => { c.oculto = !c.oculto; pintarTodo(); commit(); pintarPaneles(); } }, c.oculto ? '◌' : '👁'),
        el('button', { clase: 'ce-mini', type: 'button', 'aria-pressed': String(!!c.bloqueado), title: c.bloqueado ? 'Desbloquear' : 'Bloquear (no se mueve al pulsar el lienzo)',
          'aria-label': `${c.bloqueado ? 'Desbloquear' : 'Bloquear'} ${nombreDe(c)}`,
          onclick: () => { c.bloqueado = !c.bloqueado; pintarTodo(); commit(); pintarPaneles(); } }, c.bloqueado ? '🔒' : '🔓'));
      lista.appendChild(fila);
    }
    P.appendChild(lista);
    const hay = ED.sel.length > 0;
    P.appendChild(el('div', { clase: 'ce-orden' },
      boton('Subir', { disabled: !hay, title: 'Una por encima' }, () => reordenar('subir')),
      boton('Bajar', { disabled: !hay, title: 'Una por debajo' }, () => reordenar('bajar')),
      boton('Al frente', { disabled: !hay }, () => reordenar('frente')),
      boton('Al fondo', { disabled: !hay }, () => reordenar('fondo')),
      boton('Duplicar', { disabled: !hay, title: 'Ctrl+D' }, duplicar),
      boton('Borrar', { disabled: !hay, clase: 'ce-btn ce-peligro', title: 'Supr' }, borrar)));
    P.scrollTop = scroll;
  }

  function iconoDe(c) {
    if (c.tipo === 'texto') return 'T';
    if (c.tipo === 'imagen') return '▣';
    if (c.tipo === 'logo') return '◆';
    return c.figura === 'elipse' ? '●' : '■';
  }

  function nombreDe(c) {
    if (c.nombre) return c.nombre;
    if (c.tipo === 'texto') return (String(c.txt || '').trim().split('\n')[0] || 'Texto').slice(0, 28);
    return { imagen: 'Foto', logo: 'Logo', forma: c.figura === 'elipse' ? 'Círculo' : 'Forma' }[c.tipo];
  }

  function renombrar(fila, c) {
    const entrada = el('input', { type: 'text', value: c.nombre || nombreDe(c), maxlength: '40', 'aria-label': 'Nombre de la capa', clase: 'ce-renombrar' });
    let hecho = false;
    const acabar = guardarlo => {
      if (hecho) return;              // quitar el campo dispara su «blur»: no cuenta dos veces
      hecho = true;
      if (guardarlo) { c.nombre = entrada.value.trim().slice(0, 40); commit(); }
      pintarPaneles();
    };
    entrada.addEventListener('keydown', ev => {
      if (ev.key === 'Enter') { ev.preventDefault(); acabar(true); }
      if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); acabar(false); }
    });
    entrada.addEventListener('blur', () => acabar(true), { once: true });
    fila.firstChild.replaceWith(entrada);
    entrada.focus();
    entrada.select();
  }

  /* ---------------------------------------------------------------- propiedades */

  function grupo(titulo, ...hijos) {
    return el('section', { clase: 'ce-grupo-props' }, el('h3', {}, titulo), ...hijos);
  }

  /** Un número: se ve al momento al escribir y cuenta como un cambio al soltar. */
  function campoNumero(etiqueta, valor, fijar, opciones) {
    const o = Object.assign({ min: -100000, max: 100000, paso: 1, unidad: '' }, opciones || {});
    const entrada = el('input', { type: 'number', value: String(redondo(valor, 2)), min: String(o.min), max: String(o.max), step: String(o.paso), 'aria-label': etiqueta });
    entrada.addEventListener('input', () => {
      const v = parseFloat(entrada.value);
      if (Number.isFinite(v)) { fijar(limitar(v, o.min, o.max)); refrescarElegidas(); }
    });
    entrada.addEventListener('change', () => { commit(); pintarDerecha(); });
    return el('label', { clase: 'ce-campo' }, el('span', {}, etiqueta), el('span', { clase: 'ce-con-unidad' }, entrada, o.unidad ? el('i', {}, o.unidad) : null));
  }

  function campoDeslizador(etiqueta, valor, fijar, min, max, paso, texto) {
    const salida = el('output', {}, texto ? texto(valor) : String(valor));
    const entrada = el('input', { type: 'range', min: String(min), max: String(max), step: String(paso), value: String(valor), 'aria-label': etiqueta });
    entrada.addEventListener('input', () => {
      const v = parseFloat(entrada.value);
      fijar(v);
      salida.textContent = texto ? texto(v) : String(v);
      refrescarElegidas();
    });
    entrada.addEventListener('change', () => commit());
    return el('label', { clase: 'ce-campo ce-deslizador' }, el('span', {}, etiqueta), entrada, salida);
  }

  function campoCasilla(etiqueta, valor, fijar) {
    const entrada = el('input', { type: 'checkbox' });
    entrada.checked = !!valor;
    entrada.addEventListener('change', () => { fijar(entrada.checked); refrescarElegidas(); commit(); pintarDerecha(); });
    return el('label', { clase: 'ce-casilla' }, entrada, el('span', {}, etiqueta));
  }

  function campoElegir(etiqueta, valor, opciones, fijar) {
    const sel = el('select', { 'aria-label': etiqueta }, ...opciones.map(([v, t]) => el('option', { value: v }, t)));
    sel.value = valor;
    sel.addEventListener('change', () => { fijar(sel.value); refrescarElegidas(); commit(); pintarDerecha(); });
    return el('label', { clase: 'ce-campo' }, el('span', {}, etiqueta), sel);
  }

  function botonera(etiqueta, valor, opciones, fijar) {
    return el('div', { clase: 'ce-campo' }, el('span', {}, etiqueta),
      el('div', { clase: 'ce-botonera', role: 'group', 'aria-label': etiqueta }, ...opciones.map(([v, t, ayuda]) =>
        el('button', { type: 'button', clase: 'ce-mini', 'aria-pressed': String(valor === v), title: ayuda || '',
          onclick: () => { fijar(v); refrescarElegidas(); commit(); pintarDerecha(); } }, t))));
  }

  /** Los colores del Kit a un clic (con «texto sobre» para que se lea) y uno propio. */
  function campoColor(etiqueta, ref, alfa, fijar, conAlfa = true) {
    const col = colores();
    const muestras = [];
    for (const rol of ROLES) muestras.push([`kit:${rol}`, NOMBRE_ROL[rol], col[rol]]);
    muestras.push(['tinta:principal', 'Texto que se lee sobre el principal', resolver('tinta:principal', col)]);
    muestras.push(['tinta:secundario', 'Texto que se lee sobre el secundario', resolver('tinta:secundario', col)]);
    const fila = el('div', { clase: 'ce-muestras', role: 'group', 'aria-label': etiqueta });
    for (const [valor, nombre, hex] of muestras) {
      const b = el('button', { type: 'button', clase: 'ce-muestra' + (valor.startsWith('tinta') ? ' tinta' : ''), title: `${nombre} (del Kit)`, 'aria-label': `${etiqueta}: ${nombre}`, 'aria-pressed': String(ref === valor),
        onclick: () => { fijar(valor, alfa); refrescarElegidas(); commit(); pintarDerecha(); } });
      b.style.background = hex;
      if (valor.startsWith('tinta')) b.textContent = 'Aa';
      if (valor.startsWith('tinta')) b.style.color = valor === 'tinta:principal' ? col.principal : col.secundario;
      fila.appendChild(b);
    }
    const propio = el('input', { type: 'color', value: resolver(ref, col).toLowerCase(), title: 'Un color propio (no sigue al Kit)', 'aria-label': `${etiqueta}: un color propio` });
    propio.addEventListener('input', () => { fijar(propio.value.toUpperCase(), alfa); refrescarElegidas(); });
    propio.addEventListener('change', () => { commit(); pintarDerecha(); });
    fila.appendChild(propio);
    const hijos = [el('span', {}, etiqueta), fila];
    const caja = el('div', { clase: 'ce-campo ce-color' }, ...hijos);
    if (ref && ref[0] === '#') caja.appendChild(el('small', { clase: 'ce-pista' }, 'Color propio: no cambia si cambias el Kit.'));
    if (conAlfa) {
      caja.appendChild(campoDeslizador('Opacidad del color', Math.round((alfa === undefined ? 1 : alfa) * 100), v => fijar(ref, v / 100), 0, 100, 1, v => `${v} %`));
    }
    return caja;
  }

  /** Para cambiar UNA propiedad de todas las elegidas a la vez. */
  function aTodas(fn) { return (...args) => { for (const c of seleccion()) fn(c, ...args); }; }

  function refrescarElegidas() {
    for (const c of seleccion()) pintarCapa(c.id);
    pintarMarcas();
  }

  function pintarDerecha() {
    const P = ED.der;
    if (!P) return;
    const scroll = P.scrollTop;
    P.textContent = '';
    const elegidas = seleccion();
    if (!elegidas.length) panelPieza(P);
    else if (elegidas.length > 1) panelVarias(P, elegidas);
    else panelCapa(P, elegidas[0]);
    panelVista(P);
    P.scrollTop = scroll;
  }

  function panelPieza(P) {
    const d = ED.doc;
    P.appendChild(el('h2', {}, 'La pieza'));
    const nombre = el('input', { type: 'text', value: d.nombre || '', maxlength: '80', placeholder: 'Nombre para encontrarla', 'aria-label': 'Nombre de la pieza' });
    nombre.addEventListener('input', () => { d.nombre = nombre.value.slice(0, 80); pintarEstado(); });
    nombre.addEventListener('change', () => commit());
    P.appendChild(el('label', { clase: 'ce-campo' }, el('span', {}, 'Nombre'), nombre));
    const tam = el('select', { 'aria-label': 'Tamaño' }, ...ED.cat.formatos.map(f => el('option', { value: f.id }, `${f.nombre} · ${f.W}×${f.H}`)));
    tam.value = d.formato;
    tam.addEventListener('change', () => cambiarFormato(tam.value));
    P.appendChild(el('label', { clase: 'ce-campo' }, el('span', {}, 'Tamaño'), tam));
    const f = formato();
    P.appendChild(el('small', { clase: 'ce-pista' }, `${f.redes}. ${f.nota}`));

    const plantillas = ED.cat.plantillas;
    const elegir = el('select', { 'aria-label': 'Plantilla' }, ...plantillas.map(p => el('option', { value: String(p.n) }, `${p.n} · ${p.nombre}`)));
    elegir.value = String(ED.origen.plantilla || 2);
    P.appendChild(grupo('Volver a montar',
      el('small', { clase: 'ce-pista' }, 'Recoloca todo con una plantilla y en el tamaño de ahora. Tus textos, la foto, los colores que elegiste a mano y lo que has añadido se conservan.'),
      el('label', { clase: 'ce-campo' }, el('span', {}, 'Plantilla'), elegir),
      boton('Volver a montar', { clase: 'ce-btn ce-ancho' }, () => volverAMontar(parseInt(elegir.value, 10)))));

    const col = colores();
    const propios = d.colores || {};
    P.appendChild(grupo('Colores de esta pieza',
      el('small', { clase: 'ce-pista' }, 'Cambian solo esta pieza. Lo que usa un color del Kit cambia con él.'),
      el('div', { clase: 'ce-colores-pieza' }, ...ROLES.map(rol => {
        const entrada = el('input', { type: 'color', value: col[rol].toLowerCase(), 'aria-label': `Color ${NOMBRE_ROL[rol]} de esta pieza` });
        entrada.addEventListener('input', () => { d.colores = Object.assign({}, d.colores, { [rol]: entrada.value.toUpperCase() }); pintarTodo(); });
        entrada.addEventListener('change', () => { commit(); pintarDerecha(); });
        return el('label', { clase: 'ce-color-rol' + (propios[rol] ? ' propio' : '') }, entrada, el('span', {}, NOMBRE_ROL[rol]));
      })),
      Object.keys(propios).length ? boton('Volver a los del Kit', {}, () => { d.colores = {}; pintarTodo(); commit(); pintarDerecha(); }) : null));

    const fuentes = [['', 'La del Kit'], ...ED.cat.fuentes.map(x => [x.id, x.nombre])];
    P.appendChild(grupo('Letras de esta pieza',
      campoElegir('Títulos', d.fuente_titulos || '', fuentes, v => { d.fuente_titulos = v; cargarLetrasDelDoc(); pintarTodo(); }),
      campoElegir('Texto', d.fuente_texto || '', fuentes, v => { d.fuente_texto = v; cargarLetrasDelDoc(); pintarTodo(); })));

    P.appendChild(grupo('Atajos',
      el('ul', { clase: 'ce-atajos' },
        el('li', {}, el('kbd', {}, 'Ctrl+Z'), ' / ', el('kbd', {}, 'Ctrl+Y'), ' deshacer y rehacer'),
        el('li', {}, el('kbd', {}, 'Flechas'), ' mover 1 px (', el('kbd', {}, 'Mayús'), ': 10 px)'),
        el('li', {}, el('kbd', {}, 'Ctrl+D'), ' duplicar · ', el('kbd', {}, 'Supr'), ' borrar'),
        el('li', {}, el('kbd', {}, 'Ctrl+A'), ' todas · ', el('kbd', {}, 'Esc'), ' ninguna'),
        el('li', {}, 'Doble clic en un texto para escribirlo'),
        el('li', {}, el('kbd', {}, 'Mayús'), ' al girar: de 15 en 15° · ', el('kbd', {}, 'Alt'), ' al arrastrar: sin imán'))));
  }

  function panelVarias(P, lista) {
    P.appendChild(el('h2', {}, `${lista.length} capas elegidas`));
    const alinear = (que) => {
      const u = union(lista);
      for (const c of lista) {
        if (c.bloqueado) continue;
        const a = aabb(c);
        moverPx(c, que === 'izq' ? u.l - a.l : que === 'der' ? u.r - a.r : que === 'centro' ? (u.l + u.w / 2) - (a.l + a.w / 2) : 0,
          que === 'arriba' ? u.t - a.t : que === 'abajo' ? u.b - a.b : que === 'medio' ? (u.t + u.h / 2) - (a.t + a.h / 2) : 0);
      }
      pintarTodo(); commit();
    };
    const repartir = (eje) => {
      const libres = lista.filter(c => !c.bloqueado).map(c => ({ c, a: aabb(c) }));
      if (libres.length < 3) { avisoPantalla('Para repartir hacen falta tres capas o más.'); return; }
      libres.sort((p, q) => (eje === 'h' ? p.a.l - q.a.l : p.a.t - q.a.t));
      const total = libres.reduce((s, x) => s + (eje === 'h' ? x.a.w : x.a.h), 0);
      const ini = eje === 'h' ? libres[0].a.l : libres[0].a.t;
      const fin = eje === 'h' ? libres[libres.length - 1].a.r : libres[libres.length - 1].a.b;
      const hueco = (fin - ini - total) / (libres.length - 1);
      let en = ini;
      for (const x of libres) {
        if (eje === 'h') moverPx(x.c, en - x.a.l, 0); else moverPx(x.c, 0, en - x.a.t);
        en += (eje === 'h' ? x.a.w : x.a.h) + hueco;
      }
      pintarTodo(); commit();
    };
    P.appendChild(grupo('Alinear entre ellas',
      el('div', { clase: 'ce-botonera' },
        boton('⇤ Izquierda', {}, () => alinear('izq')), boton('↔ Centro', {}, () => alinear('centro')), boton('⇥ Derecha', {}, () => alinear('der')),
        boton('⤒ Arriba', {}, () => alinear('arriba')), boton('↕ Medio', {}, () => alinear('medio')), boton('⤓ Abajo', {}, () => alinear('abajo'))),
      el('div', { clase: 'ce-botonera' },
        boton('Repartir en horizontal', {}, () => repartir('h')), boton('Repartir en vertical', {}, () => repartir('v')))));
    const op = Math.round((lista[0].opac === undefined ? 1 : lista[0].opac) * 100);
    P.appendChild(grupo('Todas a la vez',
      campoDeslizador('Opacidad', op, aTodas((c, v) => { c.opac = v / 100; }), 0, 100, 1, v => `${v} %`),
      el('div', { clase: 'ce-botonera' },
        boton('Bloquear todas', {}, () => { lista.forEach(c => { c.bloqueado = true; }); pintarTodo(); commit(); pintarPaneles(); }),
        boton('Desbloquear', {}, () => { lista.forEach(c => { c.bloqueado = false; }); pintarTodo(); commit(); pintarPaneles(); }))));
  }

  function panelCapa(P, c) {
    const f = formato();
    const W = f.W, H = f.H, m = minLado();
    const tipo = { texto: 'Texto', imagen: 'Foto', logo: 'Logo', forma: c.figura === 'elipse' ? 'Círculo' : 'Forma' }[c.tipo];
    P.appendChild(el('h2', {}, `${tipo}: ${nombreDe(c)}`));
    if (c.bloqueado) {
      P.appendChild(el('div', { clase: 'ce-nota' }, 'Bloqueada: no se mueve con el ratón. ',
        boton('Desbloquear', {}, () => { c.bloqueado = false; pintarTodo(); commit(); pintarPaneles(); })));
    }
    if (c.tipo === 'texto') panelTexto(P, c);
    if (c.tipo === 'forma') panelForma(P, c);
    if (c.tipo === 'imagen') panelFoto(P, c);
    if (c.tipo === 'logo') {
      P.appendChild(grupo('Logo',
        campoElegir('Qué logo', c.variante, [['auto', 'Según el fondo'], ['normal', 'El normal'], ['oscuro', 'El de fondo oscuro']], v => { c.variante = v; }),
        c.variante === 'auto' ? campoElegir('Fondo que tiene debajo', c.fondo_auto, Object.entries(VAR_ROL).map(([k, rol]) => [k, NOMBRE_ROL[rol]]), v => { c.fondo_auto = v; }) : null,
        ED.logos.oscuro ? null : el('small', { clase: 'ce-pista' }, 'Sube un logo para fondo oscuro en el Kit de marca y se elegirá solo.')));
    }
    P.appendChild(grupo('Posición y tamaño',
      el('div', { clase: 'ce-dos' },
        campoNumero('X', c.x / 100 * W, v => { const d = v / W * 100 - c.x; c.x += d; if (c.recorte) c.recorte.x += d; }, { unidad: 'px' }),
        campoNumero('Y', c.y / 100 * H, v => { const d = v / H * 100 - c.y; c.y += d; if (c.recorte) c.recorte.y += d; }, { unidad: 'px' }),
        campoNumero('Ancho', c.w / 100 * W, v => { c.w = limitar(v / W * 100, 0.1, 400); }, { min: 1, unidad: 'px' }),
        campoNumero(c.tipo === 'texto' ? 'Alto mínimo' : 'Alto', c.h / 100 * H, v => { c.h = limitar(v / H * 100, 0.1, 400); }, { min: 1, unidad: 'px' }),
        campoNumero('Giro', c.giro || 0, v => { c.giro = limitar(v, -360, 360); }, { min: -360, max: 360, unidad: '°' })),
      campoDeslizador('Opacidad', Math.round((c.opac === undefined ? 1 : c.opac) * 100), v => { c.opac = v / 100; }, 0, 100, 1, v => `${v} %`),
      el('div', { clase: 'ce-campo' }, el('span', {}, 'Alinear con la pieza'),
        el('div', { clase: 'ce-botonera' },
          boton('⇤', { title: 'Al margen izquierdo', 'aria-label': 'Al margen izquierdo' }, () => alinearConLienzo(c, 'izq')),
          boton('↔', { title: 'Centrar en horizontal', 'aria-label': 'Centrar en horizontal' }, () => alinearConLienzo(c, 'centro')),
          boton('⇥', { title: 'Al margen derecho', 'aria-label': 'Al margen derecho' }, () => alinearConLienzo(c, 'der')),
          boton('⤒', { title: 'Al margen de arriba', 'aria-label': 'Al margen de arriba' }, () => alinearConLienzo(c, 'arriba')),
          boton('↕', { title: 'Centrar en vertical', 'aria-label': 'Centrar en vertical' }, () => alinearConLienzo(c, 'medio')),
          boton('⤓', { title: 'Al margen de abajo', 'aria-label': 'Al margen de abajo' }, () => alinearConLienzo(c, 'abajo')))),
      c.recorte ? el('div', { clase: 'ce-nota' }, 'Va dentro de una caja que corta lo que se sale (como en la plantilla). ',
        boton('Quitar el recorte', {}, () => { c.recorte = null; pintarTodo(); commit(); pintarDerecha(); })) : null));
    if (c.tipo !== 'logo') {
      const sombra = (c.sombra && c.sombra[0]) || null;
      P.appendChild(grupo('Sombra',
        campoCasilla('Con sombra', !!sombra, v => { c.sombra = v ? [{ x: 0, y: 1.2, blur: 3, spread: 0, color: '#000000', alfa: 0.35 }] : []; }),
        sombra ? campoDeslizador('Desenfoque', sombra.blur, v => { sombra.blur = v; }, 0, 20, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null,
        sombra ? campoDeslizador('Distancia', sombra.y, v => { sombra.y = v; }, -10, 10, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null,
        sombra ? campoDeslizador('Hacia el lado', sombra.x, v => { sombra.x = v; }, -10, 10, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null,
        sombra ? campoColor('Color de la sombra', sombra.color, sombra.alfa, (r, a) => { sombra.color = r; sombra.alfa = a; }) : null));
    }
  }

  const opcionesLetra = () => [['rol:titulos', 'La de títulos del Kit'], ['rol:texto', 'La de texto del Kit'],
    ...ED.cat.fuentes.map(x => [`id:${x.id}`, x.nombre])];

  function panelTexto(P, c) {
    const m = minLado();
    const area = el('textarea', { rows: '3', maxlength: String(LIMITES.texto), 'aria-label': 'Texto' });
    area.value = c.txt || '';
    area.addEventListener('input', () => { c.txt = area.value.slice(0, LIMITES.texto); refrescarElegidas(); pintarIzquierda(); });
    area.addEventListener('change', () => commit());
    const letra = c.fuente.rol === 'fija' ? `id:${c.fuente.id || 'poppins'}` : `rol:${c.fuente.rol}`;
    P.appendChild(grupo('Texto',
      el('label', { clase: 'ce-campo' }, el('span', {}, 'Lo que dice'), area),
      campoElegir('Letra', letra, opcionesLetra(), v => {
        const [k, id] = v.split(':');
        c.fuente = k === 'rol' ? { rol: id, id: c.fuente.id || '', serif: !!c.fuente.serif } : { rol: 'fija', id, serif: !!c.fuente.serif };
        cargarLetra(familiaDe(c));
      }),
      el('div', { clase: 'ce-dos' },
        campoNumero('Tamaño', c.tam / 100 * m, v => { c.tam = limitar(v / m * 100, 0.3, 60); }, { min: 3, max: 650, unidad: 'px' }),
        campoElegir('Grosor', String(c.peso), PESOS.map(p => [String(p), { 300: 'Fina', 400: 'Normal', 500: 'Media', 600: 'Seminegrita', 700: 'Negrita', 800: 'Extra', 900: 'Negra' }[p]]), v => { c.peso = parseInt(v, 10); })),
      el('div', { clase: 'ce-botonera', role: 'group', 'aria-label': 'Estilo de letra' },
        el('button', { type: 'button', clase: 'ce-mini', 'aria-pressed': String(!!c.cursiva), title: 'Cursiva', onclick: () => { c.cursiva = !c.cursiva; refrescarElegidas(); commit(); pintarDerecha(); } }, el('i', {}, 'I')),
        el('button', { type: 'button', clase: 'ce-mini', 'aria-pressed': String(!!c.subrayado), title: 'Subrayado', onclick: () => { c.subrayado = !c.subrayado; refrescarElegidas(); commit(); pintarDerecha(); } }, el('u', {}, 'S')),
        el('button', { type: 'button', clase: 'ce-mini', 'aria-pressed': String(!!c.mayus), title: 'Todo en mayúsculas', onclick: () => { c.mayus = !c.mayus; refrescarElegidas(); commit(); pintarDerecha(); } }, 'AA')),
      botonera('Alineación', c.alin, [['izq', '⇤', 'A la izquierda'], ['centro', '↔', 'Centrado'], ['der', '⇥', 'A la derecha']], v => { c.alin = v; }),
      botonera('En vertical', c.valign, [['arriba', '⤒', 'Arriba'], ['centro', '↕', 'En medio'], ['abajo', '⤓', 'Abajo']], v => { c.valign = v; }),
      campoDeslizador('Espacio entre letras', Math.round((c.espaciado || 0) * 100), v => { c.espaciado = v / 100; }, -10, 50, 1, v => `${v / 100} em`),
      campoDeslizador('Altura de línea', c.interlineado || 0, v => { c.interlineado = v; }, 0, 2.5, 0.05, v => (v ? `${redondo(v, 2)}` : 'la de la letra')),
      campoCasilla('Si no cabe en su caja, la letra baja sola (hasta un 60 %)', c.ajusta, v => { c.ajusta = v; })));
    P.appendChild(grupo('Color del texto', campoColor('Color', c.color, c.alfa, (r, a) => { c.color = r; c.alfa = a; })));
    const fondo = c.fondo && !c.fondo.degradado ? c.fondo : null;
    P.appendChild(grupo('Fondo del texto',
      campoCasilla('Con fondo (como un botón)', !!c.fondo, v => {
        c.fondo = v ? { color: 'kit:principal', alfa: 1 } : null;
        if (v && !(c.relleno || []).some(Boolean)) c.relleno = [1.5, 3, 1.5, 3];
        if (v && c.color === 'kit:principal') c.color = 'tinta:principal';
      }),
      fondo ? campoColor('Color del fondo', fondo.color, fondo.alfa, (r, a) => { c.fondo = { color: r, alfa: a }; }) : null,
      c.fondo && c.fondo.degradado ? el('small', { clase: 'ce-pista' }, 'Este fondo es un degradado de la plantilla.') : null,
      c.fondo ? campoDeslizador('Margen interior', (c.relleno || [0, 0, 0, 0])[1], v => { c.relleno = [v / 2, v, v / 2, v]; }, 0, 15, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null,
      c.fondo ? campoDeslizador('Esquinas', c.radio === 'elipse' ? 50 : (c.radio || 0), v => { c.radio = v; }, 0, 50, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null));
    const st = (c.sombra_texto && c.sombra_texto[0]) || null;
    P.appendChild(grupo('Sombra de las letras',
      campoCasilla('Con sombra en las letras', !!st, v => { c.sombra_texto = v ? [{ x: 0, y: 0.3, blur: 1, color: '#000000', alfa: 0.5 }] : []; }),
      st ? campoDeslizador('Desenfoque', st.blur, v => { st.blur = v; }, 0, 6, 0.05, v => `${redondo(v / 100 * m, 1)} px`) : null,
      st ? campoDeslizador('Distancia', st.y, v => { st.y = v; }, -3, 3, 0.05, v => `${redondo(v / 100 * m, 1)} px`) : null,
      st ? campoColor('Color', st.color, st.alfa, (r, a) => { st.color = r; st.alfa = a; }) : null));
    panelBorde(P, c);
  }

  function panelBorde(P, c) {
    const m = minLado();
    const b = c.borde;
    P.appendChild(grupo('Borde',
      campoCasilla('Con borde', !!b, v => { c.borde = v ? { anchos: [0.5, 0.5, 0.5, 0.5], color: 'kit:acento', alfa: 1 } : null; }),
      b ? campoDeslizador('Grosor', b.anchos[0] || Math.max(...b.anchos), v => { b.anchos = [v, v, v, v]; }, 0.1, 5, 0.05, v => `${redondo(v / 100 * m, 0)} px`) : null,
      b ? campoColor('Color del borde', b.color, b.alfa, (r, a) => { b.color = r; b.alfa = a; }) : null));
  }

  function panelForma(P, c) {
    const m = minLado();
    const rel = c.relleno;
    const deg = rel && rel.degradado;
    P.appendChild(grupo('Forma',
      botonera('Figura', c.figura === 'poligono' ? 'poligono' : c.figura, [['rect', '■ Rectángulo'], ['elipse', '● Elipse']].concat(c.figura === 'poligono' ? [['poligono', '◆ La de la plantilla']] : []), v => { c.figura = v; }),
      c.figura === 'rect' ? campoDeslizador('Esquinas', c.radio === 'elipse' ? 50 : (c.radio || 0), v => { c.radio = v; }, 0, 50, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null));
    P.appendChild(grupo('Relleno',
      botonera('Tipo', !rel ? 'no' : deg ? 'deg' : 'color', [['no', 'Sin relleno'], ['color', 'Un color'], ['deg', 'Degradado']], v => {
        if (v === 'no') c.relleno = null;
        else if (v === 'color') c.relleno = { color: (deg ? deg.paradas[0].color : (rel && rel.color)) || 'kit:principal', alfa: 1 };
        else c.relleno = { degradado: { ang: 135, paradas: [{ color: (rel && rel.color) || 'kit:principal', alfa: 1, pos: null }, { color: 'kit:secundario', alfa: 1, pos: null }] } };
      }),
      rel && !deg ? campoColor('Color', rel.color, rel.alfa, (r, a) => { c.relleno = { color: r, alfa: a }; }) : null,
      deg ? campoColor('Desde', deg.paradas[0].color, deg.paradas[0].alfa, (r, a) => { deg.paradas[0].color = r; deg.paradas[0].alfa = a; }) : null,
      deg ? campoColor('Hasta', deg.paradas[deg.paradas.length - 1].color, deg.paradas[deg.paradas.length - 1].alfa, (r, a) => { const p = deg.paradas[deg.paradas.length - 1]; p.color = r; p.alfa = a; }) : null,
      deg ? campoDeslizador('Dirección', deg.ang, v => { deg.ang = v; }, 0, 360, 1, v => `${v}°`) : null));
    panelBorde(P, c);
  }

  function panelFoto(P, c) {
    const m = minLado();
    const enc = c.encuadre || (c.encuadre = { x: 50, y: 50, zoom: 1 });
    const sube = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', clase: 'ce-oculto', id: 'ce-cambiar-foto',
      onchange: ev => { const f = ev.target.files[0]; ev.target.value = ''; if (f) subirFoto(f, c.id); } });
    const foto = c.src && ED.fotos[c.src];
    P.appendChild(grupo('Foto',
      sube, el('label', { clase: 'ce-btn ce-ancho', for: 'ce-cambiar-foto', tabindex: '0',
        onkeydown: ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); sube.click(); } } }, c.src ? 'Cambiar la foto' : 'Poner una foto'),
      foto && foto.falta ? el('small', { clase: 'ce-pista malo' }, 'Esa foto ya no está en el proyecto: pon otra.') : null,
      campoDeslizador('Encuadre horizontal', enc.x, v => { enc.x = v; }, 0, 100, 1, v => `${v} %`),
      campoDeslizador('Encuadre vertical', enc.y, v => { enc.y = v; }, 0, 100, 1, v => `${v} %`),
      campoDeslizador('Zoom', enc.zoom, v => { enc.zoom = v; }, 1, 4, 0.05, v => `${redondo(v, 2)}×`),
      campoCasilla('Recortada en círculo', c.radio === 'elipse', v => { c.radio = v ? 'elipse' : 0; }),
      c.radio !== 'elipse' ? campoDeslizador('Esquinas', c.radio || 0, v => { c.radio = v; }, 0, 50, 0.1, v => `${redondo(v / 100 * m, 0)} px`) : null));
    panelBorde(P, c);
  }

  /* ---------------------------------------------------------------- vista final */

  function panelVista(P) {
    const v = ED.vista;
    const caja = el('section', { clase: 'ce-grupo-props ce-vista' }, el('h3', {}, 'Así sale el PNG'));
    if (v.img) {
      const img = el('img', { alt: 'Vista final pintada por el servidor', clase: 'ce-vista-img' });
      img.src = v.img;
      caja.appendChild(img);
    }
    const estado = v.pidiendo ? 'Pintando la vista final…'
      : !v.img ? 'Se pinta sola cuando dejas de tocar.'
        : (v.de === firmaDoc() ? 'Al día.' : 'Ha cambiado algo: se repinta en un momento.');
    caja.appendChild(el('small', { clase: 'ce-pista' }, estado));
    const lista = [...v.avisos, ...ED.avisos];
    if (lista.length) caja.appendChild(el('ul', { clase: 'ce-avisos' }, ...lista.map(t => el('li', {}, t))));
    P.appendChild(caja);
    ED.cajaVista = caja;
  }

  function programarVista() {
    clearTimeout(ED.vista.temporizador);
    ED.vista.temporizador = setTimeout(pedirVista, 1200);
    revisarZonas();
  }

  /** La vista final: la pinta el servidor con estas capas. Una a la vez. */
  async function pedirVista() {
    if (!ED || ED.cerrado) return;
    if (ED.arrastre || ED.editando) { programarVista(); return; }
    const v = ED.vista;
    if (v.pidiendo) { v.otra = true; return; }
    v.pidiendo = true;
    const firma = firmaDoc();
    refrescarVista();
    try {
      const r = await ED.opc.pedir(ED.opc.api(ED.cid, '/capas/vista'), { method: 'POST', cuerpo: { doc: docParaEnviar(), lamina: ED.lamina } });
      if (!ED || ED.cerrado) return;
      v.img = r.img;
      v.de = firma;
      v.avisos = (r.avisos || []).slice();
      v.lineas = r.lineas || {};
      if (firma === firmaDoc()) v.avisos.push(...saltosDistintos(v.lineas));
    } catch (e) {
      if (!ED) return;
      v.avisos = [`No se ha podido pintar la vista final: ${e.message}`];
    } finally {
      if (ED) {
        v.pidiendo = false;
        refrescarVista();
        if (v.otra) { v.otra = false; pedirVista(); }
      }
    }
  }

  function refrescarVista() {
    if (!ED.cajaVista || !ED.der) return;
    const scroll = ED.der.scrollTop;
    const vieja = ED.cajaVista;
    const tmp = el('div');
    panelVista(tmp);
    vieja.replaceWith(ED.cajaVista);
    ED.der.scrollTop = scroll;
  }

  /** Cuántas líneas ocupa cada texto en la pantalla, para compararlo con el PNG. */
  function lineasEnPantalla() {
    const salida = {};
    for (const n of ED.lienzo.querySelectorAll('[data-c]')) {
      if (!n.firstChild || n.firstChild.nodeType !== 3 || !n.textContent.trim()) continue;
      const rg = document.createRange();
      rg.selectNodeContents(n);
      const tops = new Set([...rg.getClientRects()].map(q => Math.round(q.top / Math.max(0.2, ED.escala))));
      salida[n.dataset.c] = tops.size;
    }
    return salida;
  }

  function saltosDistintos(delServidor) {
    const aqui = lineasEnPantalla();
    const avisos = [];
    for (const [id, n] of Object.entries(delServidor)) {
      if (aqui[id] && aqui[id] !== n) {
        const c = capa(id);
        avisos.push(`«${c ? nombreDe(c) : id}» parte en ${n} línea${n === 1 ? '' : 's'} en el PNG y en ${aqui[id]} aquí: mira la vista final.`);
      }
    }
    return avisos;
  }

  /** Lo que se sale de la pieza o queda en lo que tapa la red (en pantalla, al momento). */
  function revisarZonas() {
    const f = formato();
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    const avisos = [];
    for (const c of capas()) {
      if (c.oculto) continue;
      const a = aabb(c);
      const fondo = a.w >= W * 0.98 && a.h >= H * 0.98;
      if (!fondo && (a.l < -0.005 * W || a.t < -0.005 * H || a.r > W * 1.005 || a.b > H * 1.005)) {
        avisos.push(`«${nombreDe(c)}» se sale de la pieza.`);
      } else if (c.tipo === 'texto' && String(c.txt || '').trim()) {
        const zonas = [[0, 0, W, f.zT / 100 * H], [0, H - f.zB / 100 * H, W, H], [0, 0, f.zL / 100 * W, H], [W - f.zR / 100 * W, 0, W, H]];
        if (zonas.some(([l, t, r, b]) => r > l && b > t && a.l < r && a.r > l && a.t < b && a.b > t)) {
          avisos.push(`«${nombreDe(c)}» queda en lo que tapa la red: mira «Ver lo que tapa la red».`);
        }
      }
    }
    ED.avisos = avisos;
  }

  /* ================================================================ acciones */

  function centroVisible() {
    // el centro de lo que se ve del lienzo (con zoom, la parte a la vista)
    const e = ED.escenario.getBoundingClientRect(), l = ED.lienzo.getBoundingClientRect();
    const cx = (Math.max(e.left, l.left) + Math.min(e.right, l.right)) / 2 - l.left;
    const cy = (Math.max(e.top, l.top) + Math.min(e.bottom, l.bottom)) / 2 - l.top;
    return [limitar(cx / l.width * 100, 10, 90), limitar(cy / l.height * 100, 10, 90)];
  }

  function capaNueva(tipo, extra) {
    const base = { id: nuevoId(), tipo, rol: '', nombre: '', x: 0, y: 0, w: 30, h: 10, giro: 0, opac: 1, origen: [50, 50], recorte: null, oculto: false, bloqueado: false };
    return Object.assign(base, extra);
  }

  function capaDeTexto(extra) {
    return capaNueva('texto', Object.assign({
      txt: 'Escribe aquí', fuente: { rol: 'texto', id: '', serif: false }, tam: 4.5, peso: 400, cursiva: false, subrayado: false,
      mayus: false, espaciado: 0, interlineado: 0, alin: 'izq', valign: 'arriba', color: 'kit:claro', alfa: 1, fondo: null,
      relleno: [0, 0, 0, 0], borde: null, radio: 0, sombra: [], sombra_texto: [], ajusta: false,
    }, extra));
  }

  function anadir(que) {
    if (capas().length >= LIMITES.capas) { avisoPantalla(`Una pieza admite hasta ${LIMITES.capas} capas.`, true); return; }
    const f = formato();
    const prop = f.W / f.H;             // de % del ancho a % del alto, para que algo salga cuadrado
    const [cx, cy] = centroVisible();
    let c;
    const fondo = colores().oscuro;
    const tinta = luz(fondo) < 0.3 ? 'kit:claro' : 'kit:oscuro';
    if (que === 'titulo') c = capaDeTexto({ nombre: 'Título', txt: 'Tu titular', fuente: { rol: 'titulos', id: '', serif: false }, tam: 10, peso: 800, w: 80, h: 10, color: tinta, interlineado: 1.05 });
    else if (que === 'texto') c = capaDeTexto({ nombre: 'Texto', txt: 'Escribe aquí tu texto', tam: 4.5, w: 70, h: 6, color: tinta });
    else if (que === 'boton') c = capaDeTexto({ nombre: 'Botón', txt: 'Reserva ya', tam: 4, peso: 700, w: 40, h: 8, alin: 'centro', valign: 'centro', color: 'tinta:principal', fondo: { color: 'kit:principal', alfa: 1 }, relleno: [2, 4, 2, 4], radio: 3 });
    else if (que === 'rect') c = capaNueva('forma', { nombre: 'Rectángulo', figura: 'rect', puntos: [], w: 40, h: 25 * prop, relleno: { color: 'kit:principal', alfa: 1 }, borde: null, radio: 0, sombra: [] });
    else if (que === 'circulo') c = capaNueva('forma', { nombre: 'Círculo', figura: 'elipse', puntos: [], w: 30, h: 30 * prop, relleno: { color: 'kit:acento', alfa: 1 }, borde: null, radio: 0, sombra: [] });
    else if (que === 'linea') c = capaNueva('forma', { nombre: 'Línea', figura: 'rect', puntos: [], w: 50, h: 0.6 * Math.min(f.W, f.H) / f.H, relleno: { color: 'kit:acento', alfa: 1 }, borde: null, radio: 0, sombra: [] });
    else if (que === 'logo') {
      const lg = ED.logos.normal || ED.logos.oscuro;
      const ratio = lg && lg.iw && lg.ih ? lg.ih / lg.iw : 0.4;
      c = capaNueva('logo', { nombre: 'Logo', variante: 'auto', fondo_auto: 'd', w: 28, h: 28 * prop * ratio });
    }
    if (!c) return;
    c.x = cx - c.w / 2;
    c.y = cy - c.h / 2;
    capas().push(c);
    if (c.tipo === 'texto') cargarLetra(familiaDe(c));
    ED.sel = [c.id];
    pintarTodo();
    commit();
    pintarPaneles();
  }

  async function subirFoto(fichero, paraId) {
    if (!paraId && capas().filter(c => c.tipo === 'imagen' && c.src).length >= LIMITES.fotos) { avisoPantalla(`Una pieza admite hasta ${LIMITES.fotos} fotos.`, true); return; }
    avisoPantalla('Subiendo la foto…');
    try {
      const cuerpo = new FormData();
      cuerpo.append('imagen', fichero);
      const r = await ED.opc.pedir(ED.opc.api(ED.cid, '/imagen'), { method: 'POST', cuerpo });
      const foto = await comoDataUrl(ED.opc.api(ED.cid, `/imagen/${encodeURIComponent(r.nombre)}`));
      ED.fotos[r.nombre] = foto;
      const f = formato();
      const existente = paraId && capa(paraId);
      if (existente) {
        existente.src = r.nombre;
        existente.encuadre = { x: 50, y: 50, zoom: 1 };
        ED.sel = [existente.id];
      } else {
        const ratio = foto.iw && foto.ih ? foto.ih / foto.iw : 1;
        const [cx, cy] = centroVisible();
        let w = 60, h = 60 * f.W / f.H * ratio;
        if (h > 80) { w = w * 80 / h; h = 80; }
        const c = capaNueva('imagen', { nombre: 'Foto', src: r.nombre, encuadre: { x: 50, y: 50, zoom: 1 }, radio: 0, borde: null, sombra: [], w, h, x: cx - w / 2, y: cy - h / 2 });
        capas().push(c);
        ED.sel = [c.id];
      }
      pintarTodo();
      commit();
      pintarPaneles();
      avisoPantalla('Foto lista.');
    } catch (e) {
      avisoPantalla(`No se ha podido subir la foto: ${e.message}`, true);
    }
  }

  function elegir(id, sumar) {
    if (sumar) ED.sel = ED.sel.includes(id) ? ED.sel.filter(x => x !== id) : [...ED.sel, id];
    else ED.sel = [id];
    pintarMarcas();
    marcarLista();
    pintarDerecha();
  }

  /** La lista de capas sin rehacerla: un doble clic en un nombre (renombrar)
   * necesita que la fila sea la misma entre los dos clics. */
  function marcarLista() {
    if (!ED.izq) return;
    const elegidas = new Set(ED.sel);
    for (const fila of ED.izq.querySelectorAll('.ce-capa')) fila.classList.toggle('elegida', elegidas.has(fila.dataset.id));
    for (const b of ED.izq.querySelectorAll('.ce-orden button')) b.disabled = !ED.sel.length;
  }

  function reordenar(como) {
    const lista = capas();
    const ids = new Set(ED.sel);
    if (como === 'frente' || como === 'fondo') {
      const elegidas = lista.filter(c => ids.has(c.id));
      const resto = lista.filter(c => !ids.has(c.id));
      ED.doc.laminas[ED.lamina].capas = como === 'frente' ? resto.concat(elegidas) : elegidas.concat(resto);
    } else if (como === 'subir') {
      for (let i = lista.length - 2; i >= 0; i--) {
        if (ids.has(lista[i].id) && !ids.has(lista[i + 1].id)) [lista[i], lista[i + 1]] = [lista[i + 1], lista[i]];
      }
    } else {
      for (let i = 1; i < lista.length; i++) {
        if (ids.has(lista[i].id) && !ids.has(lista[i - 1].id)) [lista[i], lista[i - 1]] = [lista[i - 1], lista[i]];
      }
    }
    pintarTodo();
    if (commit()) pintarPaneles();
  }

  /** Copias de unas capas, un poco más abajo y a la derecha (con su recorte),
   * o null si no caben (capas o fotos). Lo usan «Duplicar» y Ctrl+V. */
  function copiasDe(lista) {
    if (capas().length + lista.length > LIMITES.capas) { avisoPantalla(`Una pieza admite hasta ${LIMITES.capas} capas.`, true); return null; }
    const fotos = capas().filter(c => c.tipo === 'imagen' && c.src).length + lista.filter(c => c.tipo === 'imagen' && c.src).length;
    if (fotos > LIMITES.fotos) { avisoPantalla(`Una pieza admite hasta ${LIMITES.fotos} fotos.`, true); return null; }
    const f = formato();
    return lista.map(c => {
      const d = copia(c);
      d.id = nuevoId();
      d.x += 2; d.y += 2 * f.W / f.H;
      if (d.recorte) { d.recorte.x += 2; d.recorte.y += 2 * f.W / f.H; }
      d.bloqueado = false;
      if (d.rol) d.rol = '';         // la copia es tuya: «Volver a montar» no la recoloca
      return d;
    });
  }

  function duplicar() {
    const elegidas = seleccion();
    if (!elegidas.length) return;
    const nuevas = copiasDe(elegidas);
    if (!nuevas) return;
    const lista = capas();
    const ultima = Math.max(...elegidas.map(c => lista.indexOf(c)));
    lista.splice(ultima + 1, 0, ...nuevas);
    ED.sel = nuevas.map(c => c.id);
    pintarTodo();
    commit();
    pintarPaneles();
  }

  function borrar() {
    if (!ED.sel.length) return;
    const bloqueadas = seleccion().filter(c => c.bloqueado);
    if (bloqueadas.length) avisoPantalla(`${bloqueadas.length === 1 ? 'Una capa bloqueada no se borra' : 'Las capas bloqueadas no se borran'}: desbloquéala primero.`);
    const ids = new Set(seleccion().filter(c => !c.bloqueado).map(c => c.id));
    if (!ids.size) return;
    ED.doc.laminas[ED.lamina].capas = capas().filter(c => !ids.has(c.id));
    ED.sel = [];
    pintarTodo();
    commit();
    pintarPaneles();
  }

  /** Mueve una capa en píxeles de pantalla (y su recorte con ella). */
  function moverPx(c, dx, dy) {
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    const ddx = dx / W * 100, ddy = dy / H * 100;
    c.x = redondo(c.x + ddx, 6);
    c.y = redondo(c.y + ddy, 6);
    if (c.recorte) { c.recorte.x = redondo(c.recorte.x + ddx, 6); c.recorte.y = redondo(c.recorte.y + ddy, 6); }
  }

  function alinearConLienzo(c, que) {
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    const m = margenes();
    const a = aabb(c);
    const dx = que === 'izq' ? m.l / 100 * W - a.l : que === 'der' ? W - m.r / 100 * W - a.r : que === 'centro' ? W / 2 - (a.l + a.w / 2) : 0;
    const dy = que === 'arriba' ? m.t / 100 * H - a.t : que === 'abajo' ? H - m.b / 100 * H - a.b : que === 'medio' ? H / 2 - (a.t + a.h / 2) : 0;
    moverPx(c, dx, dy);
    pintarTodo();
    commit();
    pintarDerecha();
  }

  /** Otro tamaño: las capas siguen en su sitio (en %), los círculos siguen
   * redondos y se avisa de lo que se sale o queda en lo que tapa la red. */
  function cambiarFormato(nuevo) {
    const viejo = formato();
    const f = ED.cat.formatos.find(x => x.id === nuevo);
    if (!f || f.id === viejo.id) return;
    for (const c of capas()) {
      const redonda = (c.tipo === 'forma' && c.figura === 'elipse') || (c.tipo === 'imagen' && c.radio === 'elipse') || c.tipo === 'logo';
      if (!redonda) continue;
      const wpx = c.w / 100 * viejo.W, hpx = c.h / 100 * viejo.H;
      // lo que era redondo (o un logo) conserva su forma: el alto se ajusta al ancho
      const nuevoH = hpx / wpx * c.w / 100 * f.W / f.H * 100;
      const centro = c.y + c.h / 2;
      c.h = redondo(nuevoH, 6);
      c.y = redondo(centro - c.h / 2, 6);
    }
    ED.doc.formato = nuevo;
    medirLienzo();
    pintarTodo();
    commit();
    revisarZonas();
    pintarPaneles();
    const problemas = ED.avisos.length;
    avisoPantalla(problemas ? `${problemas} capa(s) se salen o quedan en lo que tapa la red: usa «Volver a montar» o muévelas.` : 'Mismas capas en el tamaño nuevo.');
  }

  async function volverAMontar(plantilla) {
    if (ED.montando) return;
    terminarEdicionTexto(true);
    avisoPantalla('Montando con la plantilla…');
    const yo = ED;
    const antes = firmaDoc();
    const tenia = new Set(capas().filter(c => c.tipo === 'texto' && String(c.txt || '').trim()).map(c => c.rol));
    yo.montando = true;
    try {
      const textos = Object.assign({}, CAMPOS_DE_MUESTRA, { marca: yo.opc.nombreCliente || 'Tu marca' });
      const r = await yo.opc.pedir(yo.opc.api(yo.cid, '/capas/montar'), {
        method: 'POST', cuerpo: { plantilla, formato: yo.doc.formato, doc: docParaEnviar(), textos, lamina: yo.lamina } });
      if (ED !== yo) return;
      if (firmaDoc() !== antes) {
        // se cambió algo mientras el servidor montaba: no se pisa
        avisoPantalla('Has cambiado algo mientras se montaba: no se ha aplicado. Vuelve a pulsar «Volver a montar».', true);
        return;
      }
      const origen = ED.origen;
      ED.doc = r.doc;
      ED.origen = Object.assign({}, origen, { plantilla });
      delete ED.doc.origen;
      ED.sel = [];
      cargarFotosDelDoc();
      cargarLetrasDelDoc();
      pintarTodo();
      commit();
      pintarPaneles();
      const deMuestra = capas().filter(c => c.tipo === 'texto' && G_CAMPO(c.rol) && !tenia.has(c.rol) && String(c.txt || '').trim());
      avisoPantalla(deMuestra.length
        ? `Recolocado. Ojo: ${deMuestra.map(c => `«${String(c.txt).trim()}»`).join(', ')} ${deMuestra.length === 1 ? 'es un texto' : 'son textos'} de muestra: cámbialos o bórralos. Ctrl+Z vuelve a lo de antes.`
        : 'Recolocado con la plantilla: tus textos y lo añadido se conservan. Ctrl+Z vuelve a lo de antes.', deMuestra.length > 0);
    } catch (e) {
      if (ED === yo) avisoPantalla(`No se ha podido montar: ${e.message}`, true);
    } finally {
      yo.montando = false;
    }
  }

  /** ¿Es un campo de plantilla (titulo, cta…)? */
  function G_CAMPO(rol) { return Object.prototype.hasOwnProperty.call(CAMPOS_DE_MUESTRA, rol); }

  async function verVersionAnterior() {
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'La versión anterior' });
    const cuerpo = el('div', { clase: 'ce-modal-cuerpo' }, el('h2', {}, 'La versión anterior'),
      el('p', { clase: 'ce-pista' }, 'La pieza tal como se guardó con el editor de antes. No se borra ni se cambia: sigue ahí.'),
      el('div', { clase: 'ce-cargando' }, 'Trayéndola…'));
    const cerrarModal = () => capaVista.remove();
    cuerpo.appendChild(boton('Cerrar', { clase: 'ce-btn ce-primario' }, cerrarModal));
    capaVista.appendChild(cuerpo);
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    ED.raiz.appendChild(capaVista);
    try {
      const f = await comoDataUrl(ED.opc.api(ED.cid, `/piezas/${ED.piezaId}/fichero.jpg?antes=1`));
      const img = el('img', { alt: 'La versión anterior de la pieza', clase: 'ce-anterior' });
      img.src = f.url;
      cuerpo.querySelector('.ce-cargando').replaceWith(img);
    } catch (e) {
      const c = cuerpo.querySelector('.ce-cargando');
      if (c) c.textContent = e.status === 404 ? 'Esta pieza no tiene una versión anterior.' : `No se ha podido traer: ${e.message}`;
    }
  }

  /* ---------------------------------------------------------------- guardar */

  function docParaEnviar() {
    return Object.assign(copia(ED.doc), { version: 2, origen: copia(ED.origen) });
  }

  async function guardar(comoNueva) {
    if (ED.guardando) return;
    terminarEdicionTexto(true);
    ED.guardando = true;
    pintarEstado();
    const nueva = comoNueva || !ED.piezaId;
    if (!String(ED.doc.nombre || '').trim()) {
      // sin nombre, el del titular: así se encuentra en la lista
      const t = capas().find(c => c.tipo === 'texto' && c.rol === 'titulo' && String(c.txt || '').trim())
        || capas().find(c => c.tipo === 'texto' && String(c.txt || '').trim());
      ED.doc.nombre = t ? String(t.txt).trim().split('\n')[0].slice(0, 80) : 'Pieza en capas';
      commit();
    }
    if (comoNueva) {
      ED.doc.nombre = `${ED.doc.nombre || 'Pieza'} (copia)`.slice(0, 80);
      commit();
    }
    const doc = docParaEnviar();
    if (comoNueva) doc.origen = { plantilla: doc.origen.plantilla, sello: '', guardado: '', nacida: true };
    // LO QUE SE ENVÍA es lo que queda guardado: lo que cambie mientras el
    // servidor pinta (unos segundos) sigue «sin guardar» y pide confirmar al cerrar
    const enviada = firmaDoc();
    const yo = ED;
    try {
      const r = await yo.opc.pedir(nueva ? yo.opc.api(yo.cid, '/capas') : yo.opc.api(yo.cid, `/piezas/${yo.piezaId}/capas`),
        { method: nueva ? 'POST' : 'PUT', cuerpo: { doc } });
      if (ED !== yo) return;
      ED.piezaId = r.id;
      ED.origen = Object.assign({}, r.doc.origen);
      ED.nacida = !!ED.origen.nacida;
      ED.cambio = true;
      ED.guardado = enviada;
      ED.vista.avisos = (r.avisos || []).slice();
      ED.convertida = false;
      const migra = ED.raiz.querySelector('.ce-migra');
      if (migra) migra.remove();
      pintarBarra();
      avisoPantalla(comoNueva ? 'Guardada como pieza nueva.' : 'Guardado: el PNG y el JPG ya están al día.');
      const quitar = ED.raiz.querySelector('.ce-conflicto');
      if (quitar) quitar.remove();
    } catch (e) {
      if (ED !== yo) return;
      if (e.status === 409) mostrarConflicto(e.message);
      else avisoPantalla(`No se ha guardado: ${e.message}`, true);
    } finally {
      yo.guardando = false;
      if (ED === yo) { pintarEstado(); pedirVista(); }
    }
  }

  function mostrarConflicto(texto) {
    const viejo = ED.raiz.querySelector('.ce-conflicto');
    if (viejo) viejo.remove();
    const caja = el('div', { clase: 'ce-conflicto', role: 'alert' },
      el('p', {}, el('b', {}, 'No se ha guardado. '), `${texto}. Tus cambios siguen aquí.`),
      el('div', { clase: 'ce-botonera' },
        boton('Guardar como pieza nueva', { clase: 'ce-btn ce-primario' }, () => guardar(true)),
        boton('Cerrar sin guardar', {}, () => cerrarYa(true))));
    ED.raiz.insertBefore(caja, ED.raiz.querySelector('.ce-zona'));
  }

  function cerrar() {
    if (sinGuardar() && !window.confirm('Hay cambios sin guardar. ¿Cerrar el editor y perderlos?')) return;
    cerrarYa(true);
  }

  function cerrarYa(avisar) {
    if (!ED) return;
    const e = ED;
    e.cerrado = true;
    clearTimeout(e.vista.temporizador);
    window.removeEventListener('resize', e.ajusteVentana);
    document.removeEventListener('keydown', e.teclas, true);
    window.removeEventListener('beforeunload', e.antesDeSalir);
    document.removeEventListener('pointermove', alArrastrar);
    document.removeEventListener('pointerup', alSoltar);
    document.removeEventListener('pointercancel', alSoltar);
    clearTimeout(e.flechas);
    clearTimeout(e.avisoTiempo);
    e.raiz.remove();
    document.body.classList.remove('ce-abierto');
    ED = null;
    if (avisar && e.opc.alCerrar) e.opc.alCerrar(!!e.cambio);
  }

  /* ================================================================ ratón y dedo */

  function puntoEnLienzo(ev) {
    const r = ED.lienzo.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top];
  }

  function capaBajo(ev) {
    const n = ev.target.closest && ev.target.closest('[data-c]');
    if (!n || !ED.lienzo.contains(n)) return null;
    return capa(n.dataset.c);
  }

  function alPulsar(ev) {
    if (ev.button !== undefined && ev.button !== 0) return;
    if (ED.editando) {
      if (ev.target.closest && ev.target.closest(`[data-c="${ED.editando}"]`)) return;   // dentro del texto que se escribe
      terminarEdicionTexto(true);
    }
    const [px, py] = puntoEnLienzo(ev);
    const asa = ev.target.dataset && ev.target.dataset.asa;
    const girar = ev.target.dataset && ev.target.dataset.girar;
    let c = null;
    const marcada = ev.target.closest && ev.target.closest('[data-mover]');
    if (asa || girar) c = capa(ED.sel[0]);
    else if (marcada) c = capa(marcada.dataset.mover);
    else c = capaBajo(ev);
    // un doble toque detectado a mano (el navegador del iPhone no siempre avisa del doble clic)
    if (c && c.tipo === 'texto' && ev.pointerType === 'touch') {
      const ahora = Date.now();
      if (ED.ultimoToque.id === c.id && ahora - ED.ultimoToque.t < 350) {
        ED.ultimoToque = { id: '', t: 0 };
        ev.preventDefault();
        empezarEdicionTexto(c.id, true);
        return;
      }
      ED.ultimoToque = { id: c.id, t: ahora };
    }
    const sumar = ev.shiftKey || ev.ctrlKey || ev.metaKey;
    if (asa || girar) {
      ev.preventDefault();
      empezarArrastre(ev, girar ? 'girar' : 'asa', c, { asa });
      return;
    }
    if (c && c.bloqueado && !marcada) c = null;      // lo bloqueado no se coge pulsando el lienzo
    if (!c) {
      if (!ED.lienzo.parentElement.contains(ev.target) && ev.target !== ED.escenario) return;
      ev.preventDefault();
      empezarArrastre(ev, 'recuadro', null, { x0: px, y0: py, sumar, antes: sumar ? ED.sel.slice() : [] });
      return;
    }
    ev.preventDefault();
    if (sumar) {
      elegir(c.id, true);
      if (!ED.sel.includes(c.id)) return;
    } else if (!ED.sel.includes(c.id)) {
      ED.sel = [c.id];
      pintarMarcas();
      pintarPaneles();
    }
    empezarArrastre(ev, 'mover', c, {});
  }

  function empezarArrastre(ev, tipo, c, datos) {
    const [px, py] = puntoEnLienzo(ev);
    ED.arrastre = Object.assign({ tipo, id: c ? c.id : '', px, py, movido: false, puntero: ev.pointerId,
      antes: datos.antes, inicio: copia(seleccion()) }, datos);
    if (tipo === 'mover' || tipo === 'asa' || tipo === 'girar') {
      ED.arrastre.cajaInicio = c ? caja(c) : null;
      ED.arrastre.capaInicio = c ? copia(c) : null;
      ED.arrastre.uInicio = union(seleccion().filter(x => !x.bloqueado));
      ED.arrastre.blancos = blancosDelImán();
    }
    try { ED.escenario.setPointerCapture(ev.pointerId); } catch (e) { /* sin captura, se sigue con document */ }
    document.addEventListener('pointermove', alArrastrar);
    document.addEventListener('pointerup', alSoltar);
    document.addEventListener('pointercancel', alSoltar);
  }

  /** Dónde se pega lo que se mueve: bordes, centro y margen de la pieza, y las demás capas. */
  function blancosDelImán() {
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    const m = margenes();
    const xs = [0, W / 2, W, m.l / 100 * W, W - m.r / 100 * W];
    const ys = [0, H / 2, H, m.t / 100 * H, H - m.b / 100 * H];
    const fuera = new Set(ED.sel);
    for (const c of capas()) {
      if (fuera.has(c.id) || c.oculto) continue;
      const a = aabb(c);
      if (a.w >= W * 0.98 && a.h >= H * 0.98) continue;      // el fondo no aporta nada
      xs.push(a.l, a.l + a.w / 2, a.r);
      ys.push(a.t, a.t + a.h / 2, a.b);
    }
    return { xs, ys };
  }

  /** El ajuste más pequeño que pega alguno de `bordes` a un blanco (o 0). */
  function pegar(bordes, blancos, umbral) {
    let mejor = null;
    for (const b of bordes) {
      for (const t of blancos) {
        const d = t - b;
        if (Math.abs(d) <= umbral && (mejor === null || Math.abs(d) < Math.abs(mejor.d))) mejor = { d, en: t };
      }
    }
    return mejor;
  }

  function alArrastrar(ev) {
    const a = ED && ED.arrastre;
    if (!a || (a.puntero !== undefined && ev.pointerId !== a.puntero)) return;
    const [px, py] = puntoEnLienzo(ev);
    let dx = px - a.px, dy = py - a.py;
    if (!a.movido && Math.hypot(dx, dy) < 3) return;
    a.movido = true;
    const iman = ED.iman && !ev.altKey;
    const umbral = 6;
    a.guias = [];
    a.etiqueta = '';
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    if (a.tipo === 'recuadro') {
      a.rect = { l: Math.min(a.x0, px), t: Math.min(a.y0, py), w: Math.abs(px - a.x0), h: Math.abs(py - a.y0) };
      a.rect.r = a.rect.l + a.rect.w;
      a.rect.b = a.rect.t + a.rect.h;
      const dentro = capas().filter(c => !c.oculto && !c.bloqueado).filter(c => {
        const q = aabb(c);
        return q.l < a.rect.r && q.r > a.rect.l && q.t < a.rect.b && q.b > a.rect.t;
      }).map(c => c.id);
      ED.sel = a.sumar ? [...new Set([...a.antes, ...dentro])] : dentro;
      pintarMarcas();
      return;
    }
    if (a.tipo === 'mover') {
      const u = a.uInicio;
      if (!u) return;
      if (ev.shiftKey) { if (Math.abs(dx) > Math.abs(dy)) dy = 0; else dx = 0; }
      if (iman) {
        const px2 = pegar([u.l + dx, u.l + u.w / 2 + dx, u.r + dx], a.blancos.xs, umbral);
        const py2 = pegar([u.t + dy, u.t + u.h / 2 + dy, u.b + dy], a.blancos.ys, umbral);
        if (px2) { dx += px2.d; a.guias.push({ eje: 'v', en: px2.en }); }
        if (py2) { dy += py2.d; a.guias.push({ eje: 'h', en: py2.en }); }
      }
      for (const ini of a.inicio) {
        const c = capa(ini.id);
        if (!c || c.bloqueado) continue;
        c.x = ini.x; c.y = ini.y;
        if (c.recorte && ini.recorte) { c.recorte.x = ini.recorte.x; c.recorte.y = ini.recorte.y; }
        moverPx(c, dx, dy);
        pintarCapa(c.id);
      }
      const f = formato();
      a.etiqueta = `${Math.round((u.l + dx) / W * f.W)}, ${Math.round((u.t + dy) / H * f.H)} px`;
      a.ex = u.l + dx; a.ey = u.t + dy - 26;
      pintarMarcas();
      return;
    }
    const c = capa(a.id);
    if (!c) return;
    if (a.tipo === 'girar') {
      const k = a.cajaInicio;
      const cx = k.x + k.ox, cy = k.y + k.oy;
      const ang0 = Math.atan2(a.py - cy, a.px - cx), ang = Math.atan2(py - cy, px - cx);
      let giro = (a.capaInicio.giro || 0) + (ang - ang0) * 180 / Math.PI;
      giro = ((giro + 180) % 360 + 360) % 360 - 180;
      if (ev.shiftKey) giro = Math.round(giro / 15) * 15;
      else if (iman) {
        const cerca = Math.round(giro / 45) * 45;
        if (Math.abs(giro - cerca) < 3) giro = cerca;
      }
      c.giro = redondo(giro, 2);
      pintarCapa(c.id);
      a.etiqueta = `${Math.round(c.giro)}°`;
      a.ex = cx + 12; a.ey = cy - 30;
      pintarMarcas();
      return;
    }
    // las asas: en el marco de la propia capa (sin girar)
    redimensionar(c, a, dx, dy, ev.shiftKey, iman, umbral);
    pintarCapa(c.id);
    const f = formato();
    a.etiqueta = c.tipo === 'texto' && a.asa.length === 2
      ? `${Math.round(c.tam / 100 * minLado())} px de letra`
      : `${Math.round(c.w / 100 * f.W)} × ${Math.round(c.h / 100 * f.H)} px`;
    const k = caja(c);
    a.ex = k.x + k.w + 8; a.ey = k.y + k.h + 4;
    pintarMarcas();
  }

  function redimensionar(c, a, dx, dy, mantener, iman, umbral) {
    const W = ED.lienzo.clientWidth, H = ED.lienzo.clientHeight;
    const k0 = a.cajaInicio, ini = a.capaInicio;
    const giro = ini.giro || 0;
    const [lx, ly] = rot(dx, dy, -giro);              // el movimiento, en el marco de la capa
    const asa = a.asa;
    const esquina = asa.length === 2;
    let w = k0.w, h = c.tipo === 'texto' ? ini.h / 100 * H : k0.h;
    if (asa.includes('e')) w = k0.w + lx;
    if (asa.includes('w')) w = k0.w - lx;
    if (asa.includes('s')) h += ly;
    if (asa.includes('n')) h -= ly;
    const minimo = 4;
    const proporcion = (c.tipo === 'texto' && esquina) || (esquina && (mantener !== (c.tipo === 'logo' || (c.tipo === 'forma' && c.figura === 'elipse') || (c.tipo === 'imagen' && c.radio === 'elipse'))));
    if (proporcion) {
      const s = Math.max(Math.abs(w) / k0.w, 0.02);
      w = k0.w * s;
      h = (c.tipo === 'texto' ? ini.h / 100 * H : k0.h) * s;
    }
    // el imán, cuando no está girada: el borde que se mueve se pega
    if (iman && !giro && !proporcion) {
      const bl = a.blancos;
      if (asa.includes('e')) { const p = pegar([k0.x + w], bl.xs, umbral); if (p) { w += p.d; a.guias.push({ eje: 'v', en: p.en }); } }
      if (asa.includes('w')) { const p = pegar([k0.x + k0.w - w], bl.xs, umbral); if (p) { w -= p.d; a.guias.push({ eje: 'v', en: p.en }); } }
      if (asa.includes('s')) { const p = pegar([k0.y + h], bl.ys, umbral); if (p) { h += p.d; a.guias.push({ eje: 'h', en: p.en }); } }
      if (asa.includes('n')) { const p = pegar([k0.y + k0.h - h], bl.ys, umbral); if (p) { h -= p.d; a.guias.push({ eje: 'h', en: p.en }); } }
    }
    w = Math.max(minimo, w);
    h = Math.max(minimo, h);
    if (c.tipo === 'texto' && esquina) {
      // las esquinas de un texto cambian la letra (y la caja con ella)
      const s = w / k0.w;
      c.tam = redondo(limitar(ini.tam * s, 0.3, 60), 4);
      if (ini.relleno) c.relleno = ini.relleno.map(p => redondo(p * s, 4));
      if (typeof ini.radio === 'number') c.radio = redondo(ini.radio * s, 4);
    }
    // el punto contrario al asa se queda quieto en pantalla (también girada)
    const hGuardado0 = ini.h / 100 * H;
    const anclaLocal = (ancho, alto) => [asa.includes('w') ? ancho : asa.includes('e') ? 0 : ancho / 2,
      asa.includes('n') ? alto : asa.includes('s') ? 0 : alto / 2];
    const o = ini.origen || [50, 50];
    const altoVisto0 = k0.h;
    const [ax0, ay0] = anclaLocal(k0.w, altoVisto0);
    const ox0 = o[0] / 100 * k0.w, oy0 = o[1] / 100 * hGuardado0;
    const [rx0, ry0] = rot(ax0 - ox0, ay0 - oy0, giro);
    const pantallaAncla = [k0.x + ox0 + rx0, k0.y + oy0 + ry0];
    const hGuardado = c.tipo === 'texto' ? (esquina ? hGuardado0 * (w / k0.w) : hGuardado0) : h;
    const altoVisto = c.tipo === 'texto' ? Math.max(hGuardado, altoVisto0 * (esquina ? w / k0.w : 1)) : h;
    const [ax, ay] = anclaLocal(w, altoVisto);
    const ox = o[0] / 100 * w, oy = o[1] / 100 * hGuardado;
    const [rx, ry] = rot(ax - ox, ay - oy, giro);
    const nx = pantallaAncla[0] - ox - rx, ny = pantallaAncla[1] - oy - ry;
    const dX = nx / W * 100 - ini.x, dY = ny / H * 100 - ini.y;
    c.x = redondo(ini.x + dX, 6);
    c.y = redondo(ini.y + dY, 6);
    c.w = redondo(w / W * 100, 6);
    c.h = redondo(hGuardado / H * 100, 6);
    if (c.recorte && ini.recorte) {
      // el recorte acompaña: crece para que no se corte lo que agrandas
      const r = ini.recorte;
      const l = Math.min(r.x + dX, c.x), t = Math.min(r.y + dY, c.y);
      const rr = Math.max(r.x + dX + r.w, c.x + c.w), bb = Math.max(r.y + dY + r.h, c.y + c.h);
      c.recorte = Object.assign({}, r, { x: redondo(l, 6), y: redondo(t, 6), w: redondo(rr - l, 6), h: redondo(bb - t, 6) });
    }
  }

  function alSoltar(ev) {
    const a = ED && ED.arrastre;
    if (!a || (a.puntero !== undefined && ev.pointerId !== a.puntero)) return;
    document.removeEventListener('pointermove', alArrastrar);
    document.removeEventListener('pointerup', alSoltar);
    document.removeEventListener('pointercancel', alSoltar);
    ED.arrastre = null;
    if (a.tipo === 'recuadro') {
      if (!a.movido && !a.sumar) ED.sel = [];
      pintarMarcas();
      pintarPaneles();
      return;
    }
    if (a.movido) {
      pintarTodo();
      commit();
      pintarPaneles();
    }
    // sin moverse no se repinta nada: rehacer el recuadro entre los dos clics
    // de un doble clic hace que el navegador no lo avise
  }

  /* ---------------------------------------------------------------- escribir en el lienzo */

  function alDobleClic(ev) {
    // el escenario captura el puntero al pulsar, así que el doble clic le llega
    // a él: lo que hay debajo se busca por el punto
    let c = null;
    for (const n of document.elementsFromPoint(ev.clientX, ev.clientY)) {
      if (n.dataset && n.dataset.mover) { c = capa(n.dataset.mover); break; }
      const capaN = n.closest && n.closest('[data-c]');
      if (capaN && ED.lienzo.contains(capaN)) { c = capa(capaN.dataset.c); break; }
    }
    if (c && c.tipo === 'texto' && !c.bloqueado) empezarEdicionTexto(c.id, true);
  }

  function empezarEdicionTexto(id, todo) {
    const c = capa(id);
    if (!c || c.tipo !== 'texto') return;
    if (!String(c.txt || '').trim()) {
      // un texto vacío se pinta como hueco: se le pone algo para poder escribir encima
      c.txt = ' ';
    }
    ED.sel = [id];
    pintarCapa(id);
    ED.editando = id;
    const n = nodoDe(id);
    if (!n) { ED.editando = null; return; }
    n.textContent = String(c.txt).trim();
    try { n.contentEditable = 'plaintext-only'; } catch (e) { n.contentEditable = 'true'; }
    if (n.contentEditable !== 'plaintext-only') n.contentEditable = 'true';
    n.classList.add('ce-escribiendo');
    n.spellcheck = true;
    n.addEventListener('input', () => {
      const txt = (n.innerText || '').replace(/\r\n/g, '\n').slice(0, LIMITES.texto);
      c.txt = txt;
      pintarMarcas();
    });
    n.addEventListener('blur', () => { if (ED && ED.editando === id && n.isConnected) terminarEdicionTexto(true); });
    n.focus();
    if (todo) {
      const rango = document.createRange();
      rango.selectNodeContents(n);
      const s = window.getSelection();
      s.removeAllRanges();
      s.addRange(rango);
    }
    pintarMarcas();
    pintarPaneles();
  }

  function terminarEdicionTexto(guardarlo) {
    if (!ED || !ED.editando) return;
    const id = ED.editando;
    ED.editando = null;
    const c = capa(id);
    if (c) {
      if (!guardarlo) {
        const antes = JSON.parse(ED.hist[ED.pos]).laminas[ED.lamina].capas.find(x => x.id === id);
        if (antes) c.txt = antes.txt;
      }
      c.txt = String(c.txt || '').replace(/^\n+|\n+$/g, '');
      if (!c.txt.trim()) c.txt = '';       // el hueco de un texto vacío no es un cambio
    }
    pintarTodo();
    commit();
    pintarPaneles();
  }

  /* ---------------------------------------------------------------- teclado */

  function escribiendoEnCampo(ev) {
    const t = ev.target;
    if (!t || t === document.body) return false;
    if (t.isContentEditable) return true;
    return /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName);
  }

  function alTeclear(ev) {
    if (!ED || ED.cerrado) return;
    // LOS ATAJOS DEL STUDIO NO SE ENTERAN con el editor abierto (Ctrl+S, Escape,
    // espacio, flechas): una tecla con el foco fuera del editor se para aquí,
    // y una de dentro, al subir (oyente de `raiz`), cuando ya la ha visto su campo
    if (!ED.raiz.contains(ev.target)) ev.stopPropagation();
    const ctrl = ev.ctrlKey || ev.metaKey;
    const tecla = ev.key;
    if (ED.editando) {
      if (tecla === 'Escape') { ev.preventDefault(); ev.stopPropagation(); terminarEdicionTexto(false); }
      else if (ctrl && tecla === 'Enter') { ev.preventDefault(); terminarEdicionTexto(true); }
      return;
    }
    if (ED.raiz.querySelector('.ce-modal')) {
      if (tecla === 'Escape') { ev.preventDefault(); ev.stopPropagation(); ED.raiz.querySelector('.ce-modal').remove(); }
      return;
    }
    if (ctrl && (tecla === 's' || tecla === 'S')) { ev.preventDefault(); guardar(); return; }
    if (escribiendoEnCampo(ev)) return;
    if (ctrl && !ev.shiftKey && (tecla === 'z' || tecla === 'Z')) { ev.preventDefault(); irAHistoria(-1); return; }
    if (ctrl && (tecla === 'y' || tecla === 'Y' || (ev.shiftKey && (tecla === 'z' || tecla === 'Z')))) { ev.preventDefault(); irAHistoria(1); return; }
    if (ctrl && (tecla === 'd' || tecla === 'D')) { ev.preventDefault(); duplicar(); return; }
    if (ctrl && (tecla === 'a' || tecla === 'A')) {
      ev.preventDefault();
      ED.sel = capas().filter(c => !c.oculto && !c.bloqueado).map(c => c.id);
      pintarMarcas(); pintarPaneles();
      return;
    }
    if (ctrl && (tecla === 'c' || tecla === 'C')) { if (ED.sel.length) { ED.portapapeles = copia(seleccion()); avisoPantalla('Copiado: Ctrl+V lo pega.'); } return; }
    if (ctrl && (tecla === 'v' || tecla === 'V')) {
      if (!ED.portapapeles || !ED.portapapeles.length) return;
      ev.preventDefault();
      const nuevas = copiasDe(ED.portapapeles);
      if (!nuevas) return;
      capas().push(...nuevas);
      ED.portapapeles = nuevas.map(copia);
      ED.sel = nuevas.map(c => c.id);
      cargarFotosDelDoc(); cargarLetrasDelDoc();
      pintarTodo(); commit(); pintarPaneles();
      return;
    }
    if (tecla === 'Escape') {
      // Escape quita la selección; ya no cierra el editor
      ev.preventDefault();
      ev.stopPropagation();
      if (ED.sel.length) { ED.sel = []; pintarMarcas(); pintarPaneles(); }
      return;
    }
    if ((tecla === 'Delete' || tecla === 'Backspace') && ED.sel.length) { ev.preventDefault(); borrar(); return; }
    if (tecla === 'Enter' && ED.sel.length === 1 && seleccion()[0].tipo === 'texto') { ev.preventDefault(); empezarEdicionTexto(ED.sel[0], true); return; }
    const flechas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (flechas[tecla] && ED.sel.length) {
      ev.preventDefault();
      const paso = (ev.shiftKey ? 10 : 1) * ED.escala;     // 1 px de la pieza de verdad (10 con Mayús)
      for (const c of seleccion()) if (!c.bloqueado) { moverPx(c, flechas[tecla][0] * paso, flechas[tecla][1] * paso); pintarCapa(c.id); }
      pintarMarcas();
      clearTimeout(ED.flechas);
      // una ráfaga de flechas cuenta como UN cambio
      ED.flechas = setTimeout(() => { if (ED) { commit(); pintarDerecha(); } }, 400);
    }
  }

  window.EditorCapas = {
    abrir, version: 1, _estado: () => ED,
    // para pasos/prueba_graficas_editor.py: que la pantalla haga las mismas cuentas que el servidor
    _cuentas: { f6, luz, tintaPara, coloresFinales, resolver, cssColor, cssRelleno, cssBorde, cssRadio, cssSombras, cssCaja,
      LIMITES, CAMPOS_DE_MUESTRA },
  };
}());

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
    lugar: 'Lugar del evento', i1: 'Elige', i2: 'Reserva', i3: 'Disfruta', cita: '«Volveremos seguro»', autor: 'Ana, clienta', usuario: '@tumarca',
  };
  const PESOS = [300, 400, 500, 600, 700, 800, 900];
  /** Los topes de `graficas_capas.py` (MAX_CAPAS, MAX_FOTOS, MAX_LOGOS, MAX_TEXTO): lo comprueba la suite. */
  const LIMITES = { capas: 60, fotos: 8, logos: 4, texto: 600 };
  const MAX_HIST = 150;

  let ED = null;          // el editor abierto (uno a la vez)
  /** Las letras ya registradas en esta página: se cargan una vez, aunque el
   * editor se abra y se cierre muchas veces (fid -> promesa). */
  const LETRAS_DE_LA_PAGINA = {};
  /** Los iconos (graficas-3c-extras): se piden una vez por página. */
  const ICONOS = { lista: null, porId: {}, pidiendo: null };

  /**
   * Abre el editor.
   * opc: { cid, nombreCliente, pieza (ficha de la lista o null), catalogo, kit,
   *        api(cid, resto), pedir(url, opciones), pases(), toast(texto, malo),
   *        alCerrar(cambio) }
   */
  async function abrir(opc) {
    // abrir otra encima («Hacer también las historias»): lo guardado en la de
    // antes sigue contando para refrescar la lista al cerrar
    const habiaCambio = !!(ED && ED.cambio);
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
      // graficas-facil: el modo sencillo (lo recordado en el navegador manda; si no, lo que pida quien abre)
      sencillo: (modoRecordado() || (opc.sencillo ? 'sencillo' : 'avanzado')) === 'sencillo', estiloAntes: '', estiloDespues: '', sBotones: [],
      cambio: habiaCambio,
    };
    raiz.classList.toggle('ce-sencillo', ED.sencillo);
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
    catalogoCarrusel().then(() => { if (ED === yo) { pintarTira(); if (!ED.sel.length) pintarDerecha(); } }).catch(() => {});
    cargarLogos();
    cargarFotosDelDoc();
    cargarLetrasDelDoc();
    pintarTodo();
    commit(true);
    ED.guardado = firmaDoc();
    // una pieza recién creada con «+ Crear»: aún no está guardada
    if (opc.nueva) ED.guardado = '';
    // y se puede volver a su paso 2 mientras no se guarde
    ED.firmaCreada = opc.desdeCrear ? firmaDoc() : '';
    pintarEstado();
    pedirVista();
    if (opc.avisoInicial) avisoPantalla(opc.avisoInicial, true);
  }

  /** Prepara el documento de ESTE editor (`E`): tras cada espera se escribe en
   * él y no en `ED`, que puede ser ya otro (doble clic al abrir). */
  async function prepararDoc(E) {
    const o = E.opc;
    if (o.docInicial) {
      // «Hacer también las historias»: un documento ya montado por el servidor, sin guardar
      E.doc = JSON.parse(JSON.stringify(o.docInicial));
      E.convertida = false;
    } else if (E.piezaId) {
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
    if (o.docInicial) {
      E.piezaId = '';
      E.origen = { plantilla: (E.doc.laminas.find(l => l.familia) || {}).familia || 1, sello: '', guardado: '', nacida: true };
      E.nacida = true;
    }
    if (o.duplicar) {
      // «Duplicar»: el mismo diseño, que se guarda como una pieza nueva
      E.piezaId = '';
      E.convertida = false;
      E.origen = { plantilla: E.origen.plantilla, sello: '', guardado: '', nacida: true };
      E.nacida = true;
      E.doc.nombre = `${E.doc.nombre || 'Pieza'} (copia)`.slice(0, 80);
    }
    delete E.doc.origen;
    for (const k of ['avisos', 'cambiada', 'medida', 'avisos_laminas']) delete E.doc[k];
    asegurarIdsLaminas(E.doc);
  }

  /* ---------------------------------------------------------------- historial
   * Lo que se guarda en el historial es el documento SIN su `origen` (el sello
   * con el que se guarda): deshacer hasta antes de un guardado no puede traer
   * un sello viejo, o el siguiente «Guardar» daría un 409 sin motivo. */

  const firmaDoc = () => JSON.stringify(ED.doc);

  function commit(primero) {
    if (!primero) sincronizarEnlaces();
    const s = firmaDoc();
    if (!primero && s === ED.hist[ED.pos]) return false;   // entrar en un campo no es un cambio
    ED.hist = ED.hist.slice(0, ED.pos + 1);
    ED.hist.push(s);
    // un carrusel grande ocupa mucho en el historial: con él, menos pasos
    const tope = s.length > 300000 ? 40 : MAX_HIST;
    while (ED.hist.length > tope) ED.hist.shift();
    ED.pos = ED.hist.length - 1;
    if (!primero) { pintarEstado(); programarVista(); pintarMiniatura(ED.lamina); }
    return true;
  }

  function irAHistoria(paso) {
    const destino = ED.pos + paso;
    if (destino < 0 || destino >= ED.hist.length) return;
    terminarEdicionTexto(false);
    ED.pos = destino;
    ED.doc = JSON.parse(ED.hist[ED.pos]);
    ED.lamina = Math.min(ED.lamina, ED.doc.laminas.length - 1);
    const vivos = new Set(capas().map(c => c.id));
    ED.sel = ED.sel.filter(id => vivos.has(id));
    cargarFotosDelDoc();
    cargarLetrasDelDoc();
    pintarTodo();
    pintarPaneles();
    pintarEstado();
    pintarTira();
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
    // y los iconos (graficas-3c-extras), si el documento lleva alguno
    const yo = ED;
    if (!ICONOS.lista && yo.doc.laminas.some(l => l.capas.some(c => c.tipo === 'icono'))) {
      cargarIconos().then(() => { if (ED === yo) { pintarTodo(); pintarTira(); } }).catch(() => {});
    }
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

  /** `capas_de_lamina` del servidor: lo que la posición de la lámina quita
   * («salvo» primera o última; «solo_horizontal» en historias y TikTok). */
  function fueraDeLamina(c, i, total, f) {
    const salvo = c.salvo || [];
    if (salvo.includes('primera') && i === 0) return true;
    if (salvo.includes('ultima') && i === total - 1) return true;
    return !!c.solo_horizontal && f.H / f.W > 1.7;
  }
  function fueraDeAqui(c) { return fueraDeLamina(c, ED.lamina, ED.doc.laminas.length, formato()); }

  /** El texto como se pinta: {n}/{total} puestos solo si hay varias láminas. */
  function textoDeLamina(c, i, total) {
    const txt = String(c.txt || '');
    if (total < 2 || !txt.includes('{')) return txt;
    return txt.split('{n}').join(String(i + 1)).split('{total}').join(String(total));
  }
  function textoVisto(c) { return textoDeLamina(c, ED.lamina, ED.doc.laminas.length); }

  /** El nodo de una capa: el mismo CSS que `_html_capa` del servidor. */
  function nodoCapa(c, col) {
    if (c.oculto || fueraDeAqui(c)) return null;
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
    } else if (c.tipo === 'icono') {
      // el mismo SVG que `graficas_iconos.svg` del servidor, con su color y su trazo
      n = el('div');
      n.style.cssText = cssCaja(c);
      const uri = uriDeIcono(c, col);
      if (uri) {
        const img = el('img', { alt: '', draggable: 'false' });
        img.style.cssText = 'display:block;width:100%;height:100%;max-width:none;max-height:none;object-fit:contain';
        img.src = uri;
        n.appendChild(img);
      } else {
        n.classList.add('ce-sin-logo');
        n.appendChild(el('span', {}, ICONOS.lista ? 'Icono' : '…'));
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
        s += `font-style:${c.cursiva ? 'italic' : 'normal'};`;
        s += c.tachado ? `text-decoration:${c.subrayado ? 'underline ' : ''}line-through;text-decoration-thickness:0.09em;`
          : `text-decoration:${c.subrayado ? 'underline' : 'none'};`;
        if (c.mayus) s += 'text-transform:uppercase;';
        if (c.espaciado) s += `letter-spacing:${f6(c.espaciado)}em;`;
        s += `line-height:${c.interlineado ? f6(c.interlineado) : 'normal'};`;
        s += `color:${cssColor(c.color, c.alfa, col)};white-space:pre-line;`;
        if (c.relleno && c.relleno.some(Boolean)) s += `padding:${c.relleno.map(p => `${f6(p)}cqmin`).join(' ')};`;
        s += cssRelleno(c.fondo, col) + cssBorde(c.borde, col) + cssRadio(c.radio);
        s += cssSombras(c.sombra, col, 'box-shadow') + cssSombras(c.sombra_texto, col, 'text-shadow');
        n = el('div');
        n.style.cssText = s;
        n.textContent = textoVisto(c).trim();
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
      const fija = c.bloqueado || (ED.sencillo && !movibleSencillo(c));
      const marco = el('div', { clase: 'ce-elegida' + (fija ? ' bloqueada' : '') });
      Object.assign(marco.style, { left: `${k.x}px`, top: `${k.y}px`, width: `${k.w}px`, height: `${k.h}px`,
        transformOrigin: `${k.ox}px ${k.oy}px`, transform: `rotate(${k.giro}deg)` });
      marco.dataset.mover = c.id;
      if (!fija) {
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
    ED.tira = el('nav', { clase: 'ce-tira', 'aria-label': 'Láminas del carrusel' });
    R.appendChild(ED.tira);
    ED.anuncio = el('div', { clase: 'ce-oculto', role: 'status', 'aria-live': 'polite' });
    R.appendChild(ED.anuncio);
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
    pintarTira();
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
    if (ED.opc.desdeCrear && !ED.piezaId) {
      B.appendChild(boton('← Cambiar tema, foto o estilo', { clase: 'ce-btn ce-volver-crear',
        title: 'Vuelve al paso 2 de «+ Crear» con todo lo que elegiste' }, volverACrear));
    }
    ED.titulo = el('span', { clase: 'ce-titulo' });
    B.appendChild(ED.titulo);
    ED.estado = el('span', { clase: 'ce-estado', role: 'status' });
    B.appendChild(ED.estado);
    B.appendChild(el('span', { clase: 'ce-crece' }));
    ED.bDeshacer = boton('↶', { title: 'Deshacer (Ctrl+Z)', 'aria-label': 'Deshacer' }, () => irAHistoria(-1));
    ED.bRehacer = boton('↷', { title: 'Rehacer (Ctrl+Y)', 'aria-label': 'Rehacer' }, () => irAHistoria(1));
    B.append(ED.bDeshacer, ED.bRehacer);
    const avanzada = el('span', { clase: 'ce-solo-avanzado' });
    avanzada.appendChild(el('span', { clase: 'ce-sep' }));
    avanzada.appendChild(boton('−', { title: 'Alejar', 'aria-label': 'Alejar' }, () => cambiarZoom(-1)));
    ED.bZoom = boton('Ajustar', { title: 'Que quepa entero' }, () => cambiarZoom(0));
    avanzada.appendChild(ED.bZoom);
    avanzada.appendChild(boton('+', { title: 'Acercar', 'aria-label': 'Acercar' }, () => cambiarZoom(1)));
    avanzada.appendChild(el('span', { clase: 'ce-sep' }));
    B.appendChild(avanzada);
    const tapa = boton('Ver lo que tapa la red', { 'aria-pressed': String(ED.tapa) }, ev => {
      ED.tapa = !ED.tapa;
      ev.currentTarget.setAttribute('aria-pressed', String(ED.tapa));
      pintarMarcas();
    });
    const iman = boton('Imán y guías', { 'aria-pressed': String(ED.iman), title: 'Las capas se pegan a los bordes, al centro, al margen y a las demás (Alt al arrastrar lo suelta)' }, ev => {
      ED.iman = !ED.iman;
      ev.currentTarget.setAttribute('aria-pressed', String(ED.iman));
    });
    avanzada.append(tapa, iman);
    B.appendChild(boton(ED.sencillo ? 'Edición avanzada' : 'Modo sencillo', {
      clase: 'ce-btn ce-cambiar-modo',
      title: ED.sencillo ? 'Mover cada cosa a mano, las capas, el QR y el resto de opciones' : 'Solo lo de siempre: tocar para escribir, cambiar la foto y el estilo',
    }, cambiarModo));
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
    ED.estado.textContent = ED.guardando ? (ED.progreso || 'Guardando…') : (sinGuardar() ? 'Sin guardar' : (ED.piezaId ? 'Guardado ✓' : ''));
    ED.estado.classList.toggle('pendiente', sinGuardar());
    ED.bDeshacer.disabled = ED.pos <= 0;
    ED.bRehacer.disabled = ED.pos >= ED.hist.length - 1;
    ED.bGuardar.disabled = ED.guardando || (!!ED.piezaId && !sinGuardar());
    // modo sencillo: descargar y la historia salen de lo guardado
    const listo = !!ED.piezaId && !sinGuardar() && !ED.guardando;
    for (const b of ED.sBotones || []) if (b.isConnected) b.disabled = !listo;
    if (ED.sPista && ED.sPista.isConnected) ED.sPista.hidden = listo;
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
      boton('＋ Icono', { title: 'Iconos sencillos con los colores de tu Kit' }, () => elegirIcono(null)),
      boton('＋ Pegatina', { title: '«Nuevo», «Guárdalo», un globo o una flecha' }, ev => abrirPegatinas(ev.currentTarget)),
      boton('＋ QR', { title: 'Tu WhatsApp o tu web en un código QR (gratis)' }, () => abrirQR()),
      hayVideos() ? boton('＋ De un vídeo', { title: 'Foto de un vídeo: una imagen que ya pagaste en un vídeo de este proyecto (gratis)' }, () => elegirFotoDeVideo(null)) : null,
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
    if (c.tipo === 'icono') return '★';
    return c.figura === 'elipse' ? '●' : '■';
  }

  function nombreDe(c) {
    if (c.nombre) return c.nombre;
    if (c.tipo === 'texto') return (String(c.txt || '').trim().split('\n')[0] || 'Texto').slice(0, 28);
    if (c.tipo === 'icono') return (ICONOS.porId[c.icono] || {}).nombre || 'Icono';
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
    if (ED.sencillo) {
      // sin vaciar el panel: el botón que se está pulsando (Guardar, al tocarlo
      // mientras se escribe un texto) no puede desaparecer bajo el dedo
      panelSencillo(P);
      P.scrollTop = scroll;
      return;
    }
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
    panelCarruselPieza(P);

    const plantillas = ED.cat.plantillas;
    const elegir = el('select', { 'aria-label': 'Plantilla' }, ...plantillas.map(p => el('option', { value: String(p.n) }, `${p.n} · ${p.nombre}`)));
    elegir.value = String(ED.origen.plantilla || 2);
    P.appendChild(grupo('Volver a montar',
      el('small', { clase: 'ce-pista' }, 'Recoloca todo con una plantilla y en el tamaño de ahora. Tus textos, la foto, los colores que elegiste a mano y lo que has añadido se conservan.'),
      el('label', { clase: 'ce-campo' }, el('span', {}, 'Plantilla'), elegir),
      boton('Volver a montar', { clase: 'ce-btn ce-ancho' }, () => volverAMontar(parseInt(elegir.value, 10)))));
    panelFamilias(P);

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
    const tipo = { texto: 'Texto', imagen: 'Foto', logo: 'Logo', icono: 'Icono', forma: c.figura === 'elipse' ? 'Círculo' : 'Forma' }[c.tipo];
    P.appendChild(el('h2', {}, `${tipo}: ${nombreDe(c)}`));
    if (c.bloqueado) {
      P.appendChild(el('div', { clase: 'ce-nota' }, 'Bloqueada: no se mueve con el ratón. ',
        boton('Desbloquear', {}, () => { c.bloqueado = false; pintarTodo(); commit(); pintarPaneles(); })));
    }
    panelCarruselCapa(P, c);
    if (c.tipo === 'texto') panelTexto(P, c);
    if (c.tipo === 'forma') panelForma(P, c);
    if (c.tipo === 'imagen') panelFoto(P, c);
    if (c.tipo === 'icono') {
      P.appendChild(grupo('Icono',
        boton('Cambiar el icono', { clase: 'ce-btn ce-ancho' }, () => elegirIcono(c.id)),
        campoColor('Color', c.color, c.alfa, (ref, alfa) => { c.color = ref; c.alfa = alfa; }),
        campoDeslizador('Grosor del trazo', c.grosor || 2, v => { c.grosor = v; }, 0.5, 4, 0.25, v => `${redondo(v, 2)}`)));
    }
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
        el('button', { type: 'button', clase: 'ce-mini', 'aria-pressed': String(!!c.tachado), title: 'Tachado', onclick: () => { if (c.tachado) delete c.tachado; else c.tachado = true; refrescarElegidas(); commit(); pintarDerecha(); } }, el('s', {}, 'T')),
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
      hayVideos() ? boton('Usar una foto de un vídeo', { clase: 'ce-btn ce-ancho', title: 'Una imagen que ya pagaste en un vídeo de este proyecto (gratis)' }, () => elegirFotoDeVideo(c.id)) : null,
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

  /* ---------------------------------------------------------------- iconos y pegatinas (graficas-3c-extras, B4)
   * Los iconos son de web/iconos/ (Lucide, ISC, y unos propios): el servidor da
   * sus trazos (GET /api/graficas/iconos) y aquí se pintan con el color de la capa. */

  function uriDeIcono(c, col) {
    const ic = ICONOS.porId[c.icono];
    if (!ic) return '';
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="${resolver(c.color, col)}" `
      + `stroke-opacity="${c.alfa === undefined ? 1 : c.alfa}" stroke-width="${c.grosor || 2}" stroke-linecap="round" stroke-linejoin="round">${ic.svg}</svg>`;
    return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`;
  }

  async function cargarIconos() {
    if (ICONOS.lista) return ICONOS.lista;
    if (!ICONOS.pidiendo) {
      const o = ED.opc;
      ICONOS.pidiendo = o.pedir(`${o.base}/api/graficas/iconos`).then(r => {
        ICONOS.lista = r.iconos || [];
        for (const ic of ICONOS.lista) ICONOS.porId[ic.id] = ic;
        return ICONOS.lista;
      }).catch(e => { ICONOS.pidiendo = null; throw e; });
    }
    return ICONOS.pidiendo;
  }

  /** «＋ Icono» (paraId null) o «Cambiar el icono» de la capa `paraId`. */
  async function elegirIcono(paraId) {
    if (!paraId && capas().length >= LIMITES.capas) { avisoPantalla(`Una pieza admite hasta ${LIMITES.capas} capas.`, true); return; }
    const yo = ED;
    let lista;
    try { lista = await cargarIconos(); } catch (e) { avisoPantalla(`No se han podido cargar los iconos: ${e.message}`, true); return; }
    if (ED !== yo) return;
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Elegir un icono' });
    const cerrarModal = () => capaVista.remove();
    const col = colores();
    // la muestra, con el color del texto del tema (las casillas van sobre el fondo del panel)
    const tinta = (getComputedStyle(ED.raiz).getPropertyValue('--texto') || '').trim();
    const muestra = { color: /^#[0-9a-f]{6}$/i.test(tinta) ? tinta : resolver('kit:oscuro', col), alfa: 1, grosor: 2 };
    const rejilla = el('div', { clase: 'ce-iconos' }, ...lista.map(ic => {
      const img = el('img', { alt: '' });
      img.src = uriDeIcono(Object.assign({ icono: ic.id }, muestra), col);
      return el('button', { clase: 'ce-icono', type: 'button', title: ic.nombre, 'aria-label': ic.nombre, onclick: () => {
        cerrarModal();
        const existente = paraId && capa(paraId);
        if (existente) {
          existente.icono = ic.id;
          existente.nombre = ic.nombre;
          ED.sel = [existente.id];
        } else {
          const f = formato();
          const [cx, cy] = centroVisible();
          const lado = 14;
          const c = capaNueva('icono', { nombre: ic.nombre, icono: ic.id, color: 'kit:principal', alfa: 1, grosor: 2, w: lado, h: lado * f.W / f.H });
          c.x = cx - c.w / 2;
          c.y = cy - c.h / 2;
          capas().push(c);
          ED.sel = [c.id];
        }
        pintarTodo();
        commit();
        pintarPaneles();
      } }, img, el('span', {}, ic.nombre));
    }));
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo ce-modal-iconos' },
      el('h2', {}, paraId ? 'Cambiar el icono' : 'Poner un icono'),
      el('p', { clase: 'ce-pista' }, 'Salen con el color que elijas de tu Kit. Iconos de Lucide (licencia ISC) y propios; ninguno de redes ni de marcas.'),
      rejilla, el('div', { clase: 'ce-botonera' }, boton('Cancelar', {}, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    ED.raiz.appendChild(capaVista);
    const primero = rejilla.querySelector('button');
    if (primero) primero.focus();
  }

  /** Las pegatinas: capas de siempre ya montadas (un texto con su fondo, un globo, una flecha). */
  function pegatina(cual) {
    const f = formato();
    const prop = f.W / f.H;
    const [cx, cy] = centroVisible();
    const nuevas = [];
    if (cual === 'nuevo') {
      nuevas.push(capaDeTexto({ nombre: 'Pegatina «Nuevo»', txt: 'NUEVO', tam: 4.2, peso: 800, w: 24, h: 8, alin: 'centro', valign: 'centro',
        color: 'tinta:acento', fondo: { color: 'kit:acento', alfa: 1 }, relleno: [1.4, 3, 1.4, 3], radio: 99, espaciado: 0.08, giro: -8 }));
    } else if (cual === 'guardalo') {
      nuevas.push(capaDeTexto({ nombre: 'Pegatina «Guárdalo»', txt: 'Guárdalo para después', tam: 3.8, peso: 800, w: 44, h: 8, alin: 'centro', valign: 'centro',
        color: 'tinta:secundario', fondo: { color: 'kit:secundario', alfa: 1 }, relleno: [1.4, 3, 1.4, 3], radio: 2 }));
    } else if (cual === 'globo') {
      nuevas.push(capaDeTexto({ nombre: 'Globo', txt: '¡Escríbenos!', tam: 4.2, peso: 700, w: 40, h: 12, alin: 'centro', valign: 'centro',
        color: 'tinta:claro', fondo: { color: 'kit:claro', alfa: 1 }, relleno: [2, 3, 2, 3], radio: 4 }));
      nuevas.push(capaNueva('forma', { nombre: 'Pico del globo', figura: 'poligono', puntos: [[0, 0], [100, 0], [20, 100]], w: 6, h: 6 * prop,
        relleno: { color: 'kit:claro', alfa: 1 }, borde: null, radio: 0, sombra: [] }));
    } else if (cual === 'flecha') {
      nuevas.push(capaNueva('icono', { nombre: 'Flecha curva', icono: 'flecha-curva', color: 'kit:acento', alfa: 1, grosor: 2.5, w: 18, h: 18 * prop }));
    }
    if (!nuevas.length) return;
    if (capas().length + nuevas.length > LIMITES.capas) { avisoPantalla(`Una pieza admite hasta ${LIMITES.capas} capas.`, true); return; }
    // centradas, y el pico, pegado debajo del globo
    const [a, b] = nuevas;
    a.x = cx - a.w / 2;
    a.y = cy - a.h / 2;
    if (b) { b.x = a.x + a.w * 0.2; b.y = a.y + a.h - 0.1; }
    for (const c of nuevas) capas().push(c);
    if (a.tipo === 'texto') cargarLetra(familiaDe(a));
    if (a.tipo === 'icono') cargarIconos().then(() => pintarTodo()).catch(() => {});
    ED.sel = nuevas.map(c => c.id);
    pintarTodo();
    commit();
    pintarPaneles();
    avisoPantalla(b ? 'Globo listo: el texto y su pico van elegidos juntos para moverlos a la vez.' : 'Pegatina lista: muévela, gírala o cambia su texto.');
  }

  function abrirPegatinas(ancla) {
    const ya = ED.raiz.querySelector('.ce-menu-pegatinas');
    if (ya) { ya.remove(); return; }
    const menu = el('div', { clase: 'ce-menu-pegatinas', role: 'menu' },
      ...[['nuevo', '«Nuevo»'], ['guardalo', '«Guárdalo»'], ['globo', 'Globo de diálogo'], ['flecha', 'Flecha curva']].map(([id, texto]) =>
        boton(texto, { role: 'menuitem' }, () => { menu.remove(); pegatina(id); })));
    ancla.insertAdjacentElement('afterend', menu);
    const primero = menu.querySelector('button');
    if (primero) primero.focus();
  }

  async function subirFoto(fichero, paraId) {
    if (!paraId && capas().filter(c => c.tipo === 'imagen' && c.src).length >= LIMITES.fotos) { avisoPantalla(`Una pieza admite hasta ${LIMITES.fotos} fotos.`, true); return; }
    avisoPantalla('Subiendo la foto…');
    try {
      const cuerpo = new FormData();
      cuerpo.append('imagen', fichero);
      const r = await ED.opc.pedir(ED.opc.api(ED.cid, '/imagen'), { method: 'POST', cuerpo });
      await ponerFoto(r.nombre, paraId);
    } catch (e) {
      avisoPantalla(`No se ha podido subir la foto: ${e.message}`, true);
    }
  }

  /** ¿Hay vídeos de este proyecto de los que sacar una foto ya pagada? */
  function hayVideos() {
    return typeof ED.opc.videos === 'function' && ED.opc.videos().length > 0;
  }

  /**
   * «Foto de un vídeo» (graficas-3c-extras, B2): la imagen YA HECHA de un plano
   * de un vídeo de este proyecto, copiada a Gráficas por
   * POST /imagen/de-plano. Gratis: no se genera nada. `paraId`: la capa de foto
   * que se cambia, o null para añadir una nueva a esta lámina.
   */
  function elegirFotoDeVideo(paraId) {
    if (!hayVideos()) return;
    if (!paraId && capas().filter(c => c.tipo === 'imagen' && c.src).length >= LIMITES.fotos) { avisoPantalla(`Una pieza admite hasta ${LIMITES.fotos} fotos.`, true); return; }
    const yo = ED;
    const laminaDeAntes = yo.doc.laminas[yo.lamina].id;
    const videos = yo.opc.videos();
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Foto de un vídeo' });
    const cerrarModal = () => capaVista.remove();
    const rejilla = el('div', { clase: 'ce-planos', 'aria-live': 'polite' });
    const abrirVideo = async pid => {
      rejilla.textContent = '';
      if (!pid) return;
      rejilla.appendChild(el('div', { clase: 'ce-pista' }, 'Buscando sus imágenes…'));
      try {
        const planos = await yo.opc.planos(pid);
        if (ED !== yo || !capaVista.isConnected) return;
        rejilla.textContent = '';
        if (!planos.length) { rejilla.appendChild(el('div', { clase: 'ce-pista' }, 'Este vídeo aún no tiene imágenes.')); return; }
        for (const pl of planos) {
          const img = el('img', { alt: pl.texto || 'Plano' });
          yo.opc.miniatura(img, pid, pl.sid);
          rejilla.appendChild(el('button', { clase: 'ce-plano', type: 'button', title: pl.texto || '', onclick: async () => {
            cerrarModal();
            avisoPantalla('Copiando la imagen del vídeo…');
            try {
              const r = await yo.opc.pedir(yo.opc.api(yo.cid, '/imagen/de-plano'), { method: 'POST', cuerpo: { pid, sid: pl.sid } });
              if (ED !== yo) return;
              await ponerFoto(r.nombre, paraId, { lamina: laminaDeAntes });
            } catch (e) {
              if (ED === yo) avisoPantalla(`No se ha podido usar esa imagen: ${e.message}`, true);
            }
          } }, img));
        }
      } catch (e) {
        if (!capaVista.isConnected) return;
        rejilla.textContent = '';
        rejilla.appendChild(el('div', { clase: 'ce-pista malo' }, `No se han podido leer sus imágenes: ${e.message}`));
      }
    };
    const selector = el('select', { 'aria-label': 'Vídeo', onchange: ev => abrirVideo(ev.target.value) },
      el('option', { value: '' }, 'Elige un vídeo…'), ...videos.map(v => el('option', { value: v.id }, v.nombre || v.id)));
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo ce-modal-planos' },
      el('h2', {}, paraId ? 'Cambiar por una foto de un vídeo' : 'Foto de un vídeo'),
      el('p', { clase: 'ce-pista' }, 'Las imágenes que ya pagaste en tus vídeos de este proyecto. Usarlas es gratis: no se genera nada.'),
      selector, rejilla,
      el('div', { clase: 'ce-botonera' }, boton('Cancelar', {}, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    ED.raiz.appendChild(capaVista);
    if (videos.length === 1) { selector.value = videos[0].id; abrirVideo(videos[0].id); }
    selector.focus();
  }

  /** Pone en la lámina una foto ya guardada en Gráficas (subida o sacada de un vídeo). */
  async function ponerFoto(nombre, paraId, opciones) {
    const o = opciones || {};
    const yo = ED;
    const foto = await comoDataUrl(yo.opc.api(yo.cid, `/imagen/${encodeURIComponent(nombre)}`));
    if (ED !== yo) return;
    ED.fotos[nombre] = foto;
    const f = formato();
    // la lámina en la que se pidió, por su id (si mientras tanto se pasó a otra
    // o se reordenaron, va a la suya; si se borró, a la que está abierta)
    const lam = (o.lamina && ED.doc.laminas.find(l => l.id === o.lamina)) || ED.doc.laminas[ED.lamina];
    const otra = lam !== ED.doc.laminas[ED.lamina];
    const existente = paraId && lam.capas.find(c => c.id === paraId);
    if (!existente && lam.capas.filter(c => c.tipo === 'imagen' && c.src).length >= LIMITES.fotos) {
      avisoPantalla(`Una lámina admite hasta ${LIMITES.fotos} fotos.`, true);
      return;
    }
    if (existente) {
      existente.src = nombre;
      existente.encuadre = { x: 50, y: 50, zoom: 1 };
      ED.sel = [existente.id];
    } else {
      const ratio = foto.iw && foto.ih ? foto.ih / foto.iw : 1;
      const [cx, cy] = centroVisible();
      const ancho = o.ancho || 60;
      let w = ancho, h = ancho * f.W / f.H * ratio;
      if (h > 80) { w = w * 80 / h; h = 80; }
      const c = capaNueva('imagen', { nombre: o.nombre || 'Foto', rol: o.rol || '', src: nombre, encuadre: { x: 50, y: 50, zoom: 1 }, radio: 0, borde: null, sombra: [], w, h, x: cx - w / 2, y: cy - h / 2 });
      lam.capas.push(c);
      ED.sel = [c.id];
    }
    pintarTodo();
    commit();
    pintarPaneles();
    if (otra) pintarTira();
    avisoPantalla(otra ? `${o.aviso || 'Foto lista.'} Va en la lámina ${ED.doc.laminas.indexOf(lam) + 1}.` : (o.aviso || 'Foto lista.'));
  }

  /**
   * «＋ QR» (graficas-3c-extras, B1): tu WhatsApp o tu web en un QR, hecho en el
   * servidor sin salir a internet (POST /qr). Entra como una capa de foto
   * cuadrada; negro sobre blanco a propósito (con colores, muchos móviles no lo leen).
   */
  function abrirQR() {
    if (capas().filter(c => c.tipo === 'imagen' && c.src).length >= LIMITES.fotos) { avisoPantalla(`Una pieza admite hasta ${LIMITES.fotos} fotos.`, true); return; }
    const yo = ED;
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Poner un QR' });
    const cerrarModal = () => capaVista.remove();
    let tipo = 'whatsapp';
    const valor = el('input', { type: 'text', clase: 'ce-qr-valor', maxlength: '300', 'aria-label': 'Número o web', autocomplete: 'off' });
    const mensaje = el('input', { type: 'text', clase: 'ce-qr-valor', maxlength: '80', 'aria-label': 'Mensaje que ya sale escrito (opcional)',
      placeholder: 'Mensaje que ya sale escrito (opcional)' });
    const error = el('small', { clase: 'ce-pista malo', 'aria-live': 'polite' });
    const pista = el('small', { clase: 'ce-pista' });
    const pintarTipo = () => {
      valor.placeholder = tipo === 'whatsapp' ? '999 999 999 (Perú) o con el código del país' : 'crearia.tech';
      pista.textContent = tipo === 'whatsapp' ? 'Al escanearlo se abre un chat de WhatsApp contigo.' : 'Al escanearlo se abre tu web.';
      mensaje.hidden = tipo !== 'whatsapp';
      for (const b of elegirTipo.querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.tipo === tipo));
    };
    const elegirTipo = el('div', { clase: 'ce-botonera', role: 'group', 'aria-label': 'Qué lleva el QR' },
      ...[['whatsapp', 'WhatsApp'], ['web', 'Web']].map(([id, texto]) => boton(texto, { 'data-tipo': id },
        () => { tipo = id; error.textContent = ''; pintarTipo(); valor.focus(); })));
    let haciendo = false;
    const hacer = async () => {
      if (haciendo) return;                 // un doble clic o dos Intro: un solo QR
      if (!valor.value.trim()) { valor.focus(); return; }
      error.textContent = '';
      haciendo = true;
      botonHacer.disabled = true;
      let r;
      try {
        r = await yo.opc.pedir(yo.opc.api(yo.cid, '/qr'), { method: 'POST', cuerpo: { tipo, valor: valor.value, mensaje: tipo === 'whatsapp' ? mensaje.value : '' } });
      } catch (e) {
        error.textContent = e.message;
        haciendo = false;
        botonHacer.disabled = false;
        return;
      }
      // cancelado mientras se hacía, o el editor ya es otro: no se pone
      if (ED !== yo || !capaVista.isConnected) return;
      cerrarModal();
      try {
        await ponerFoto(r.nombre, null, { ancho: 26, nombre: 'QR', rol: 'qr', lamina: laminaDeAntes, aviso: `QR listo: lleva a ${r.destino}. Pruébalo con tu móvil antes de publicar.` });
      } catch (e) {
        if (ED === yo) avisoPantalla(`No se ha podido poner el QR: ${e.message}`, true);
      }
    };
    const laminaDeAntes = yo.doc.laminas[yo.lamina].id;
    const botonHacer = boton('Hacer el QR', { clase: 'ce-btn ce-primario' }, () => hacer());
    valor.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); hacer(); } });
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo ce-modal-qr' },
      el('h2', {}, 'Poner un QR'),
      el('p', { clase: 'ce-pista' }, 'Se hace aquí mismo, gratis y sin salir a internet. Va en negro sobre blanco para que lo lea cualquier móvil.'),
      elegirTipo, valor, mensaje, pista, error,
      el('div', { clase: 'ce-botonera' }, botonHacer, boton('Cancelar', {}, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    ED.raiz.appendChild(capaVista);
    pintarTipo();
    valor.focus();
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
      // una copia de una capa «en todas» es una capa normal: nunca dos copias
      // del mismo grupo en una lámina
      delete d.enlace; delete d.salvo; delete d.solo_horizontal;
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
    const enlazadas = seleccion().filter(c => ids.has(c.id) && c.enlace);
    if (enlazadas.length && !ED.borrandoEnlazadas) { preguntarBorrarEnlazadas(enlazadas); return; }
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
    for (const c of ED.doc.laminas.flatMap(l => l.capas)) {
      const redonda = (c.tipo === 'forma' && c.figura === 'elipse') || (c.tipo === 'imagen' && (c.radio === 'elipse' || c.rol === 'qr' || c.nombre === 'QR')) || c.tipo === 'logo' || c.tipo === 'icono';
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
    pintarTira();
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
      // sin nombre, el del titular de la PORTADA (antes, el de la lámina que
      // estuviera abierta: un carrusel guardado en la 3 se llamaba como la 3)
      const portada = ED.doc.laminas[0].capas;
      const t = portada.find(c => c.tipo === 'texto' && c.rol === 'titulo' && String(c.txt || '').trim())
        || portada.find(c => c.tipo === 'texto' && !c.enlace && String(c.txt || '').trim());
      ED.doc.nombre = t ? String(t.txt).trim().split('\n')[0].slice(0, 80) : 'Pieza en capas';
      commit();
    }
    const doc = docParaEnviar();
    // LO QUE SE ENVÍA es lo que queda guardado: lo que cambie mientras el
    // servidor pinta (unos segundos) sigue «sin guardar» y pide confirmar al cerrar
    let enviada = firmaDoc();
    if (comoNueva) {
      // el «(copia)» va solo en lo enviado: si falla, la pieza no cambia de nombre
      doc.origen = { plantilla: doc.origen.plantilla, sello: '', guardado: '', nacida: true };
      doc.nombre = `${doc.nombre || 'Pieza'} (copia)`.slice(0, 80);
      enviada = JSON.stringify(Object.assign(JSON.parse(enviada), { nombre: doc.nombre }));
    }
    const yo = ED;
    // la marca de ESTE guardado: si se corta la conexión, se relee el sello y
    // se sabe si lo que hay guardado es lo nuestro o de otra pestaña
    const envio = Math.random().toString(16).slice(2, 10) + Math.random().toString(16).slice(2, 10);
    doc.origen.envio = envio;
    try {
      let r = await yo.opc.pedir(nueva ? yo.opc.api(yo.cid, '/capas') : yo.opc.api(yo.cid, `/piezas/${yo.piezaId}/capas`),
        { method: nueva ? 'POST' : 'PUT', cuerpo: { doc } });
      if (r && r.trabajo) r = await seguirGuardado(yo, r, nueva ? '' : yo.piezaId, envio);
      if (ED !== yo) return;
      ED.piezaId = r.id;
      ED.origen = Object.assign({}, r.doc.origen);
      ED.nacida = !!ED.origen.nacida;
      ED.cambio = true;
      if (comoNueva) {
        const igual = firmaDoc() === JSON.stringify(Object.assign(JSON.parse(enviada), { nombre: ED.doc.nombre }));
        ED.doc.nombre = doc.nombre;
        commit();
        ED.guardado = igual ? firmaDoc() : enviada;
      } else {
        ED.guardado = enviada;
      }
      ED.vista.avisos = (r.avisos || []).slice();
      ED.convertida = false;
      const migra = ED.raiz.querySelector('.ce-migra');
      if (migra) migra.remove();
      pintarBarra();
      const n = ED.doc.laminas.length;
      avisoPantalla(comoNueva ? 'Guardada como pieza nueva.'
        : (n > 1 ? `Guardado: las ${n} láminas ya están al día.` : 'Guardado: el PNG y el JPG ya están al día.'));
      if (n > 1) avisarMuestras(yo);
      const quitar = ED.raiz.querySelector('.ce-conflicto');
      if (quitar) quitar.remove();
    } catch (e) {
      if (ED !== yo) return;
      if (e.status === 409) mostrarConflicto(e.message);
      else if (e.sinSaber) avisoPantalla(`Ojo: ${e.message}.`, true);
      else avisoPantalla(`No se ha guardado: ${e.message}`, true);
    } finally {
      yo.guardando = false;
      yo.progreso = '';
      if (ED === yo) { pintarEstado(); pedirVista(); }
    }
  }

  /** Un carrusel se guarda como trabajo: se pregunta cómo va hasta que acaba
   * (nunca una petición larga, que el proxy corta a los 60 s). -> lo que
   * devuelve un guardado, o lanza el error con su código (409, etc.). */
  async function seguirGuardado(E, inicio, piezaId, envio) {
    const espera = ms => new Promise(ok => setTimeout(ok, ms));
    let fallos = 0;
    E.progreso = `Pintando las láminas (0 de ${inicio.total})…`;
    if (ED === E) pintarEstado();
    for (;;) {
      await espera(700);
      let t;
      try {
        t = await E.opc.pedir(E.opc.api(E.cid, `/capas/trabajo/${inicio.trabajo}`));
        fallos = 0;
      } catch (e) {
        if (e.status === 404 || e.status === 403) throw e;          // el servicio se reinició: no se guardó
        if (++fallos < 8) continue;                                   // un corte de red: se reintenta
        // sin conexión durante un rato: ¿se guardó lo nuestro? (el sello lo dice)
        if (piezaId) {
          try {
            const leida = await E.opc.pedir(E.opc.api(E.cid, `/piezas/${piezaId}/capas`));
            if (leida.doc && leida.doc.origen && leida.doc.origen.envio === envio) {
              return { id: piezaId, doc: leida.doc, avisos: [] };
            }
          } catch (_) { /* se informa abajo */ }
          throw e;
        }
        // una pieza NUEVA no se puede buscar: volver a guardar podría dejarla dos veces
        const corte = new Error('se ha cortado la conexión mientras se guardaba. Puede que se haya guardado: '
          + 'cierra y mira la lista de piezas antes de volver a guardar');
        corte.sinSaber = true;
        throw corte;
      }
      if (t.estado === 'listo') return t.resultado;
      if (t.estado === 'error') {
        const fallo = new Error(t.error || 'no se ha podido guardar');
        fallo.status = t.codigo;
        throw fallo;
      }
      E.progreso = `Pintando la lámina ${Math.min(t.hechas + 1, t.total)} de ${t.total}…`;
      if (ED === E) pintarEstado();
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

  /* ================================================================ el carrusel (graficas-3-carrusel)
   * Una pieza con varias láminas: la tira de debajo del lienzo, «En todas» (copias
   * enlazadas: cada lámina lleva su copia con `enlace`, y un cambio en una se
   * pasa a las demás al confirmarlo), «Ocultar aquí» (el `oculto` de esa copia) y
   * «Este fondo a todas». Lo que el servidor quita por la posición (`salvo`,
   * `solo_horizontal`) y el número {n}/{total} los pinta igual la pantalla. */

  const MAX_LAMINAS = 20;
  const NOMBRE_TIPO = { portada: 'Portada', punto: 'Punto', lista: 'Lista', dato: 'Dato', antes_despues: 'Antes / después',
    pasos: 'Pasos', cita: 'Cita', mito: 'Mito / Realidad', pregunta: 'Pregunta', ranking: 'Ranking',
    checklist: 'Checklist', comparativa: 'Comparativa', precio: 'Precio / oferta', cierre: 'Cierre', blanco: 'En blanco' };
  const nuevoIdCorto = pre => pre + Math.random().toString(16).slice(2, 10).padEnd(8, '0');

  function asegurarIdsLaminas(doc) {
    const vistos = new Set();
    for (const lam of doc.laminas) {
      if (!lam.id || vistos.has(lam.id) || !/^[a-z0-9]{1,12}$/.test(lam.id)) lam.id = nuevoIdCorto('l');
      vistos.add(lam.id);
    }
  }

  /** Pasa a las demás copias de cada grupo «en todas» lo que cambió en ESTA
   * lámina desde el último paso del historial (solo esa propiedad; nunca el
   * id ni el `oculto`, que es «ocultar aquí»). */
  function sincronizarEnlaces() {
    const laminas = ED.doc.laminas;
    if (laminas.length < 2 || !ED.hist[ED.pos]) return;
    const aqui = laminas[ED.lamina];
    const enlazadas = aqui.capas.filter(c => c.enlace);
    if (!enlazadas.length) return;
    let antes;
    try { antes = JSON.parse(ED.hist[ED.pos]); } catch (_) { return; }
    const lamAntes = antes.laminas.find(l => l.id === aqui.id);
    if (!lamAntes) return;
    const viejas = new Map(lamAntes.capas.map(c => [c.id, c]));
    for (const c of enlazadas) {
      const v = viejas.get(c.id);
      if (!v || v.enlace !== c.enlace) continue;          // recién enlazada: ya se copió entera
      const claves = new Set([...Object.keys(c), ...Object.keys(v)]);
      for (const k of claves) {
        if (k === 'id' || k === 'oculto' || k === 'enlace') continue;
        if (JSON.stringify(c[k]) === JSON.stringify(v[k])) continue;
        for (const lam of laminas) {
          if (lam === aqui) continue;
          for (const otra of lam.capas) {
            if (otra.enlace !== c.enlace) continue;
            if (k in c) otra[k] = copia(c[k]); else delete otra[k];
          }
        }
      }
    }
  }

  /** ¿Cabe la capa `c` en la lámina, quitando `fuera` (la que reemplaza)?
   * Los mismos topes que el servidor: capas, fotos y logos por lámina. */
  function cabeEnLamina(lam, c, fuera) {
    const quedan = lam.capas.filter(x => x !== fuera);
    if (quedan.length >= LIMITES.capas) return false;
    const esFoto = x => x.tipo === 'imagen' && x.src;
    if (esFoto(c) && quedan.filter(esFoto).length >= LIMITES.fotos) return false;
    return c.tipo !== 'logo' || quedan.filter(x => x.tipo === 'logo').length < LIMITES.logos;
  }

  /** Lleva una capa a todas las láminas (copias enlazadas, encima de todo). */
  function marcarEnTodas(c) {
    if (c.enlace) return;
    c.enlace = nuevoIdCorto('e');
    let sinSitio = 0;
    ED.doc.laminas.forEach((lam, i) => {
      if (i === ED.lamina) return;
      if (!cabeEnLamina(lam, c)) { sinSitio++; return; }
      lam.capas.push(Object.assign(copia(c), { id: nuevoId(), oculto: false }));
    });
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
    avisoPantalla(sinSitio ? `En todas menos ${sinSitio} lámina(s) que ya están llenas (${LIMITES.capas} capas, ${LIMITES.fotos} fotos o ${LIMITES.logos} logos).`
      : 'Ahora sale en todas las láminas: lo que cambies aquí cambia en todas.');
  }

  /** «Quitar de todas»: se queda solo la de esta lámina, como capa normal. */
  function quitarDeTodas(c) {
    const grupo = c.enlace;
    if (!grupo) return;
    ED.doc.laminas.forEach((lam, i) => { if (i !== ED.lamina) lam.capas = lam.capas.filter(x => x.enlace !== grupo); });
    delete c.enlace; delete c.salvo; delete c.solo_horizontal;
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
  }

  function preguntarBorrarEnlazadas(enlazadas) {
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Borrar una capa de todas las láminas' });
    const cerrarModal = () => capaVista.remove();
    const nombres = enlazadas.map(c => `«${nombreDe(c)}»`).join(', ');
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo' },
      el('h2', {}, 'Está en todas las láminas'),
      el('p', {}, `${nombres} ${enlazadas.length === 1 ? 'sale' : 'salen'} en todas las láminas. ¿La quitas de todas o solo la ocultas en esta?`),
      el('div', { clase: 'ce-botonera' },
        boton('Quitar de todas', { clase: 'ce-btn ce-peligro' }, () => {
          cerrarModal();
          const grupos = new Set(enlazadas.map(c => c.enlace));
          ED.doc.laminas.forEach((lam, i) => { if (i !== ED.lamina) lam.capas = lam.capas.filter(x => !grupos.has(x.enlace)); });
          ED.borrandoEnlazadas = true;
          try { borrar(); } finally { ED.borrandoEnlazadas = false; }
          pintarTira();
        }),
        boton('Ocultarla solo aquí', { clase: 'ce-btn ce-primario' }, () => {
          cerrarModal();
          for (const c of enlazadas) c.oculto = true;
          ED.sel = [];
          pintarTodo(); commit(); pintarPaneles();
        }),
        boton('Cancelar', {}, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    ED.raiz.appendChild(capaVista);
    capaVista.querySelector('.ce-primario').focus();
  }

  /** ¿Es la capa de fondo de su lámina (la de abajo, tapándola entera)? */
  function esFondo(c, lam) {
    return lam.capas[0] === c && !c.giro && c.x <= 0.5 && c.y <= 0.5 && c.x + c.w >= 99.5 && c.y + c.h >= 99.5
      && (c.tipo === 'forma' || c.tipo === 'imagen');
  }

  /** ¿Tapa esta capa la lámina entera, sin dejar ver nada de lo de abajo?
   * (un rectángulo de color liso a sangre, o una foto a sangre, con foto o sin ella;
   * también girada si es lo bastante grande). `f`: el tamaño de la lámina. */
  function tapaTodo(c, f) {
    if (c.oculto || (c.opac != null && c.opac < 0.99) || c.recorte) return false;
    if (c.giro) {
      // girada: tapa si las cuatro esquinas de la lámina caen dentro de la caja
      // girada (con medio píxel de margen por el suavizado del borde). En píxeles,
      // porque x va en % del ancho e y en % del alto (árbitro del 25-11)
      if (!f) return false;
      const X = c.x * f.W / 100, Y = c.y * f.H / 100, W = c.w * f.W / 100, H = c.h * f.H / 100;
      const o = c.origen || [50, 50];
      const px = X + o[0] / 100 * W, py = Y + o[1] / 100 * H;
      const a = -c.giro * Math.PI / 180, cos = Math.cos(a), sin = Math.sin(a);
      const dentro = ([qx, qy]) => {
        const dx = qx - px, dy = qy - py;
        const rx = px + dx * cos - dy * sin, ry = py + dx * sin + dy * cos;
        return rx >= X + 0.5 && rx <= X + W - 0.5 && ry >= Y + 0.5 && ry <= Y + H - 0.5;
      };
      if (![[0, 0], [f.W, 0], [0, f.H], [f.W, f.H]].every(dentro)) return false;
    } else if (!(c.x <= 0.5 && c.y <= 0.5 && c.x + c.w >= 99.5 && c.y + c.h >= 99.5)) {
      return false;
    }
    // una foto a sangre tapa, también sin foto: se pinta un bloque de color
    if (c.tipo === 'imagen') return !c.radio;
    if (c.tipo !== 'forma' || (c.figura && c.figura !== 'rect') || c.radio) return false;
    const r = c.relleno;
    if (!r) return false;
    if (r.degradado) return (r.degradado.paradas || []).every(p => p.alfa == null || p.alfa >= 0.99);
    return !!r.color && (r.alfa == null || r.alfa >= 0.99);
  }

  /** El fondo de la lámina no se ve si otra capa lo tapa entero: las portadas
   * de plantilla llevan encima su propio fondo (el degradado de Neón nocturno,
   * la foto a sangre…), prueba del 24-11. */
  function fondoTapado(lam, i, total, f) {
    // lo que no sale en esta lámina («Menos en la primera», «Solo en el
    // carrusel» en historias) no tapa nada (árbitro del 25-11)
    return lam.capas.slice(1).some(c => tapaTodo(c, f) && !(f && fueraDeLamina(c, i, total, f)));
  }

  /** «la portada», «la lámina 3», «las láminas 2, 5 y 7» (números desde 1). */
  function nombrarLaminas(lista) {
    const otras = lista.filter(n => n !== 1);
    const y = l => (l.length === 1 ? String(l[0]) : `${l.slice(0, -1).join(', ')} y ${l[l.length - 1]}`);
    const resto = !otras.length ? '' : (otras.length === 1 ? `la lámina ${otras[0]}` : `las láminas ${y(otras)}`);
    if (!lista.includes(1)) return resto;
    return resto ? `la portada y ${resto}` : 'la portada';
  }

  /** El aviso de «Este fondo a todas», que dice EXACTAMENTE dónde se ve:
   * `r` = {actual, propiaTapada, puestas: [n], tapadas: [n], llenas: [n]} (números desde 1). */
  function avisoFondoATodas(r) {
    const llenas = `ya ${r.llenas.length === 1 ? 'está llena' : 'están llenas'} (${LIMITES.capas} capas, ${LIMITES.fotos} fotos o ${LIMITES.logos} logos)`;
    const tapadas = r.tapadas.length === 1 && r.tapadas[0] === 1
      ? 'la portada conserva el fondo de su plantilla, que va por encima'
      : `en ${nombrarLaminas(r.tapadas)} no se vería, porque su diseño lleva encima su propio fondo`;
    const partes = [];
    const se_ve = r.puestas.length + (r.propiaTapada ? 0 : 1);
    if (!r.puestas.length) {
      partes.push('No se ha cambiado ninguna otra lámina:');
      const porque = [];
      if (r.tapadas.length) porque.push(tapadas);
      if (r.llenas.length) porque.push(`${nombrarLaminas(r.llenas)} ${llenas}`);
      partes.push(porque.length ? `${porque.join('; ')}.` : 'no hay otras láminas.');
    } else {
      partes.push(se_ve === 1
        ? 'Este fondo se ve ahora en 1 lámina.'
        : `Este fondo se ve ahora en ${se_ve} láminas.`);
      if (r.tapadas.length) partes.push(`${tapadas.charAt(0).toUpperCase()}${tapadas.slice(1)}.`);
      if (r.llenas.length) partes.push(`En ${nombrarLaminas(r.llenas)} no se ha puesto: ${llenas}.`);
      partes.push('Ctrl+Z lo deshace.');
    }
    if (r.propiaTapada) {
      partes.push(`Ojo: en ${r.actual === 1 ? 'esta portada' : `esta lámina (la ${r.actual})`} este fondo no se ve, porque otra capa de su diseño lo tapa.`);
    }
    return partes.join(' ');
  }

  function fondoATodas(c) {
    const total = ED.doc.laminas.length;
    const r = { actual: ED.lamina + 1, propiaTapada: fondoTapado(ED.doc.laminas[ED.lamina], ED.lamina, total, formato()),
      puestas: [], tapadas: [], llenas: [] };
    ED.doc.laminas.forEach((lam, i) => {
      if (i === ED.lamina) return;
      // su diseño lo taparía: no se cambia lo que no se iba a ver
      if (fondoTapado(lam, i, total, formato())) { r.tapadas.push(i + 1); return; }
      const nuevo = Object.assign(copia(c), { id: nuevoId(), oculto: false });
      delete nuevo.enlace;
      const viejo = lam.capas[0] && esFondo(lam.capas[0], lam) ? lam.capas[0] : null;
      if (!cabeEnLamina(lam, nuevo, viejo)) { r.llenas.push(i + 1); return; }
      if (viejo) lam.capas[0] = nuevo; else lam.capas.unshift(nuevo);
      r.puestas.push(i + 1);
    });
    if (r.puestas.length) { pintarTodo(); commit(); pintarTira(); }
    avisoPantalla(avisoFondoATodas(r), !r.puestas.length);
  }

  /** Lo del carrusel en el panel de una capa. */
  function panelCarruselCapa(P, c) {
    if (ED.doc.laminas.length < 2) return;
    const lam = ED.doc.laminas[ED.lamina];
    const hijos = [];
    if (!c.enlace) {
      hijos.push(campoCasillaSuelta('En todas las láminas', false, v => { if (v) marcarEnTodas(c); }));
      hijos.push(el('small', { clase: 'ce-pista' }, 'Para el logo, el número (escribe {n}/{total}) o «Desliza →»: sale en todas, en el mismo sitio, y cambiarla en una la cambia en todas.'));
    } else {
      const salvo = new Set(c.salvo || []);
      const fijarSalvo = (que, v) => {
        if (v) salvo.add(que); else salvo.delete(que);
        const lista = ['primera', 'ultima', 'pdf'].filter(x => salvo.has(x));
        if (lista.length) c.salvo = lista; else delete c.salvo;
      };
      hijos.push(el('div', { clase: 'ce-nota' }, 'Sale en todas las láminas. Lo que cambies aquí cambia en todas. Para no verla solo en esta, ocúltala con el ojo de la lista.'));
      hijos.push(campoCasilla('Menos en la primera (la portada)', salvo.has('primera'), v => fijarSalvo('primera', v)));
      hijos.push(campoCasilla('Menos en la última', salvo.has('ultima'), v => fijarSalvo('ultima', v)));
      hijos.push(campoCasilla('Solo en el carrusel (no en historias ni TikTok)', !!c.solo_horizontal, v => { if (v) c.solo_horizontal = true; else delete c.solo_horizontal; }));
      hijos.push(campoCasilla('No en el PDF de LinkedIn', salvo.has('pdf'), v => fijarSalvo('pdf', v)));
      hijos.push(boton('Quitar de todas', { clase: 'ce-btn ce-ancho', title: 'Se queda solo la de esta lámina' }, () => quitarDeTodas(c)));
    }
    if (esFondo(c, lam)) {
      hijos.push(boton('Este fondo a todas las láminas', { clase: 'ce-btn ce-ancho' }, () => fondoATodas(c)));
    }
    P.appendChild(grupo('Carrusel', ...hijos));
  }

  /** Una casilla que llama a `fijar` y nada más (quien la usa repinta). */
  function campoCasillaSuelta(etiqueta, valor, fijar) {
    const entrada = el('input', { type: 'checkbox' });
    entrada.checked = !!valor;
    entrada.addEventListener('change', () => fijar(entrada.checked));
    return el('label', { clase: 'ce-casilla' }, entrada, el('span', {}, etiqueta));
  }

  /* ---------------------------------------------------------------- láminas */

  function irALamina(i) {
    if (!ED || i < 0 || i >= ED.doc.laminas.length) return;
    terminarEdicionTexto(true);
    ED.lamina = i;
    ED.sel = [];
    ED.vista.avisos = [];
    pintarTodo();
    pintarPaneles();
    pintarTira();
    revisarZonas();
    programarVista();
    anunciar(`Lámina ${i + 1} de ${ED.doc.laminas.length}, ${NOMBRE_TIPO[ED.doc.laminas[i].tipo] || 'sin tipo'}`);
  }

  function anunciar(texto) {
    if (ED && ED.anuncio) ED.anuncio.textContent = texto;
  }

  /** Copias, en una lámina nueva, de cada grupo «en todas» (de la primera lámina que lo tenga). */
  function enlazadasPara() {
    const vistos = new Set();
    const salida = [];
    for (const lam of ED.doc.laminas) {
      for (const c of lam.capas) {
        if (!c.enlace || vistos.has(c.enlace)) continue;
        vistos.add(c.enlace);
        salida.push(Object.assign(copia(c), { id: nuevoId(), oculto: false }));
      }
    }
    return salida;
  }

  /** Una lámina «En blanco»: el fondo de esta y lo que va en todas. */
  function laminaEnBlanco() {
    const aqui = ED.doc.laminas[ED.lamina];
    const capasNuevas = [];
    if (aqui.capas[0] && esFondo(aqui.capas[0], aqui) && !aqui.capas[0].enlace) {
      const fondo = Object.assign(copia(aqui.capas[0]), { id: nuevoId(), oculto: false });
      capasNuevas.push(fondo);
    } else {
      capasNuevas.push(capaNueva('forma', { nombre: 'Fondo', figura: 'rect', puntos: [], x: 0, y: 0, w: 100, h: 100,
        relleno: { color: 'kit:oscuro', alfa: 1 }, borde: null, radio: 0, sombra: [] }));
    }
    capasNuevas.push(...enlazadasPara());
    return { id: nuevoIdCorto('l'), tipo: 'blanco', capas: capasNuevas };
  }

  function anadirLamina(lam, donde) {
    if (ED.doc.laminas.length >= MAX_LAMINAS) { avisoPantalla(`Un carrusel tiene como mucho ${MAX_LAMINAS} láminas.`, true); return false; }
    const i = donde === undefined ? ED.lamina + 1 : donde;
    ED.doc.laminas.splice(i, 0, lam);
    cargarFotosDelDoc();
    cargarLetrasDelDoc();
    ED.lamina = i;
    ED.sel = [];
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
    anunciar(`Lámina ${i + 1} de ${ED.doc.laminas.length} añadida`);
    return true;
  }

  function duplicarLamina() {
    const lam = copia(ED.doc.laminas[ED.lamina]);
    lam.id = nuevoIdCorto('l');
    for (const c of lam.capas) c.id = nuevoId();      // las enlazadas siguen en su grupo
    anadirLamina(lam);
  }

  function borrarLamina() {
    if (ED.doc.laminas.length < 2) return;
    const i = ED.lamina;
    ED.doc.laminas.splice(i, 1);
    if (ED.doc.laminas.length === 1) {
      // una sola lámina: ya no es un carrusel, lo de «en todas» queda como capas normales
      for (const c of ED.doc.laminas[0].capas) { delete c.enlace; delete c.salvo; delete c.solo_horizontal; }
    }
    ED.lamina = Math.min(i, ED.doc.laminas.length - 1);
    ED.sel = [];
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
    avisoPantalla(ED.sencillo ? 'Imagen quitada. «↶» (arriba) la recupera.' : 'Lámina borrada. Ctrl+Z la recupera.');
  }

  function moverLamina(de, a) {
    const L = ED.doc.laminas;
    if (de === a || a < 0 || a >= L.length) return;
    const [lam] = L.splice(de, 1);
    L.splice(a, 0, lam);
    ED.lamina = a;
    ED.sel = [];
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
    anunciar(`Lámina movida a la posición ${a + 1} de ${L.length}`);
  }

  /** Los nodos de una lámina cualquiera (para la tira y la vista en el móvil). */
  function nodosDeLamina(i) {
    const antes = ED.lamina;
    ED.lamina = i;
    try {
      const col = colores();
      return ED.doc.laminas[i].capas.map(c => nodoCapa(c, col)).filter(Boolean);
    } finally {
      ED.lamina = antes;
    }
  }

  function miniLienzo(i, clase) {
    const f = formato();
    const mini = el('div', { clase: clase || 'ce-mini-lienzo', 'aria-hidden': 'true' });
    mini.style.aspectRatio = `${f.W} / ${f.H}`;
    mini.style.background = colores().oscuro;
    mini.append(...nodosDeLamina(i));
    return mini;
  }

  function pintarMiniatura(i) {
    if (!ED || !ED.tira) return;
    const hueco = ED.tira.querySelector(`.ce-tira-lamina[data-i="${i}"] .ce-mini-lienzo`);
    if (!hueco || ED.doc.laminas.length !== ED.tira.querySelectorAll('.ce-tira-lamina').length) { pintarTira(); return; }
    hueco.replaceWith(miniLienzo(i));
  }

  function pintarTira() {
    if (!ED || !ED.tira) return;
    const T = ED.tira;
    const scroll = T.querySelector('.ce-tira-lista') ? T.querySelector('.ce-tira-lista').scrollLeft : 0;
    T.textContent = '';
    const L = ED.doc.laminas;
    const S = ED.sencillo;
    const nombreL = S ? 'Imagen' : 'Lámina';
    T.classList.toggle('ce-tira-una', S && L.length < 2);
    const lista = el('ol', { clase: 'ce-tira-lista', 'aria-label': `${S ? 'Imágenes' : 'Láminas'} (${L.length})` });
    L.forEach((lam, i) => {
      const tipo = NOMBRE_TIPO[lam.tipo] || '';
      const b = el('button', { type: 'button', clase: 'ce-tira-lamina' + (i === ED.lamina ? ' actual' : ''), 'data-i': String(i),
        'aria-current': i === ED.lamina ? 'true' : 'false', draggable: 'true',
        'aria-label': `${nombreL} ${i + 1} de ${L.length}${tipo ? `, ${tipo}` : ''}`,
        title: `${nombreL} ${i + 1}${tipo ? ` · ${tipo}` : ''} (arrástrala para cambiar el orden)`,
        onclick: () => irALamina(i) },
      miniLienzo(i), el('span', { clase: 'ce-tira-num' }, String(i + 1)));
      b.addEventListener('dragstart', ev => { ev.dataTransfer.setData('text/plain', String(i)); ev.dataTransfer.effectAllowed = 'move'; b.classList.add('arrastrando'); });
      b.addEventListener('dragend', () => b.classList.remove('arrastrando'));
      b.addEventListener('dragover', ev => { ev.preventDefault(); ev.dataTransfer.dropEffect = 'move'; b.classList.add('destino'); });
      b.addEventListener('dragleave', () => b.classList.remove('destino'));
      b.addEventListener('drop', ev => {
        ev.preventDefault();
        b.classList.remove('destino');
        const de = parseInt(ev.dataTransfer.getData('text/plain'), 10);
        if (Number.isInteger(de)) moverLamina(de, i);
      });
      lista.appendChild(el('li', {}, b));
    });
    const lleno = L.length >= MAX_LAMINAS;
    const f = formato();
    const horiz = f.W / f.H > 1.3;
    const tipos = ((ED.carCat || {}).tipos || []).filter(t => t.id !== 'portada');
    const menu = el('div', { clase: 'ce-tira-menu', hidden: true, role: 'menu' },
      ...tipos.map(t => boton(t.nombre, { role: 'menuitem', disabled: horiz && !t.horizontal,
        title: horiz && !t.horizontal ? 'No cabe bien en horizontal' : 'Con el estilo de la familia' },
      () => { menu.hidden = true; anadirLaminaDeTipo(t.id); })),
      tipos.length ? el('hr', {}) : null,
      boton('En blanco', { role: 'menuitem' }, () => { menu.hidden = true; anadirLamina(laminaEnBlanco()); }),
      boton('Copia de esta', { role: 'menuitem' }, () => { menu.hidden = true; duplicarLamina(); }));
    const mas = boton('＋ Lámina', { clase: 'ce-btn ce-solo-avanzado', disabled: lleno, 'aria-haspopup': 'menu', title: lleno ? `Como mucho ${MAX_LAMINAS} láminas` : 'Añadir una lámina después de esta' },
      () => { menu.hidden = !menu.hidden; });
    const acciones = el('div', { clase: 'ce-tira-acciones' },
      el('span', { clase: 'ce-tira-cuenta' }, L.length > 1 ? `${nombreL} ${ED.lamina + 1} de ${L.length}` : (S ? 'Una imagen' : 'Una lámina')),
      el('span', { clase: 'ce-tira-mas' }, mas, menu),
      boton('← Mover', { disabled: ED.lamina === 0, title: 'Antes (Alt+←)' }, () => moverLamina(ED.lamina, ED.lamina - 1)),
      boton('Mover →', { disabled: ED.lamina >= L.length - 1, title: 'Después (Alt+→)' }, () => moverLamina(ED.lamina, ED.lamina + 1)),
      boton(S ? 'Quitar esta imagen' : 'Borrar lámina', { disabled: L.length < 2, clase: 'ce-btn ce-peligro' }, borrarLamina),
      boton('Ver como en el móvil', { disabled: L.length < 1 }, verEnElMovil));
    T.append(lista, acciones);
    const nueva = T.querySelector('.ce-tira-lista');
    nueva.scrollLeft = scroll;
    const actual = T.querySelector('.ce-tira-lamina.actual');
    if (actual && actual.scrollIntoView) actual.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  /** «Ver como en el móvil»: el carrusel se desliza con sus puntos; las historias
   * llevan las barras de arriba y se avanza tocando. */
  function verEnElMovil() {
    const f = formato();
    const historia = f.H / f.W > 1.7;
    const L = ED.doc.laminas;
    let actual = ED.lamina;
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Así se ve en el móvil' });
    const cerrarModal = () => capaVista.remove();
    const telefono = el('div', { clase: 'ce-movil' + (historia ? ' historia' : '') });
    const pasar = el('div', { clase: 'ce-movil-pasar' }, ...L.map((_l, i) => el('div', { clase: 'ce-movil-lamina' }, miniLienzo(i, 'ce-movil-lienzo'))));
    const puntos = el('div', { clase: 'ce-movil-puntos', 'aria-hidden': 'true' }, ...L.map(() => el('span', {})));
    const barras = el('div', { clase: 'ce-movil-barras', 'aria-hidden': 'true' }, ...L.map(() => el('span', {})));
    const contador = el('div', { clase: 'ce-pista', role: 'status' });
    const marcar = () => {
      [...puntos.children].forEach((p, i) => p.classList.toggle('si', i === actual));
      [...barras.children].forEach((p, i) => p.classList.toggle('si', i <= actual));
      contador.textContent = `${actual + 1} de ${L.length}`;
    };
    const ir = i => {
      actual = Math.max(0, Math.min(L.length - 1, i));
      pasar.scrollTo({ left: actual * pasar.clientWidth, behavior: 'smooth' });
      marcar();
    };
    pasar.addEventListener('scroll', () => {
      const i = Math.round(pasar.scrollLeft / Math.max(1, pasar.clientWidth));
      if (i !== actual) { actual = i; marcar(); }
    });
    if (historia) {
      pasar.addEventListener('click', ev => {
        const r = pasar.getBoundingClientRect();
        ir(actual + (ev.clientX - r.left < r.width / 3 ? -1 : 1));
      });
      telefono.append(barras, pasar);
    } else {
      telefono.append(pasar, puntos);
    }
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo ce-modal-movil' },
      el('h2', {}, historia ? 'Así se ven las historias' : 'Así se ve el carrusel'),
      el('p', { clase: 'ce-pista' }, historia ? 'Toca a la derecha para pasar y a la izquierda para volver.' : 'Desliza con el dedo (o con las flechas).'),
      telefono, contador,
      el('div', { clase: 'ce-botonera' },
        boton('←', { 'aria-label': 'Anterior' }, () => ir(actual - 1)),
        boton('→', { 'aria-label': 'Siguiente' }, () => ir(actual + 1)),
        boton('Cerrar', { clase: 'ce-btn ce-primario' }, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    capaVista.addEventListener('keydown', ev => {
      if (ev.key === 'ArrowRight') { ev.preventDefault(); ir(actual + 1); }
      if (ev.key === 'ArrowLeft') { ev.preventDefault(); ir(actual - 1); }
    });
    ED.raiz.appendChild(capaVista);
    requestAnimationFrame(() => { pasar.scrollLeft = actual * pasar.clientWidth; marcar(); });
    capaVista.querySelector('.ce-primario').focus();
  }

  /** Lo del carrusel en el panel de la pieza: la lámina que ves (su texto
   * alternativo) y dónde cabe. */
  function panelCarruselPieza(P) {
    const L = ED.doc.laminas;
    const lam = L[ED.lamina];
    const alt = el('textarea', { maxlength: '400', rows: '2', 'aria-label': 'Texto alternativo de esta lámina',
      placeholder: 'Qué se ve, para quien no puede verla (si lo dejas vacío, sale de sus textos)' });
    alt.value = lam.alt || '';
    alt.addEventListener('input', () => { if (alt.value.trim()) lam.alt = alt.value.slice(0, 400); else delete lam.alt; });
    alt.addEventListener('change', () => commit());
    const f = formato();
    const vertical = f.H / f.W > 1.7;
    const filas = [
      ['Instagram', vertical ? 'Historias: una por lámina' : '20 subiendo a mano (publicando automático, puede que 10)', L.length <= 20],
      ['Facebook', vertical ? 'Historias: una por lámina' : '20 subiendo a mano', L.length <= 20],
      ['Threads', '20', L.length <= 20],
      ['TikTok en fotos', '35, solo JPG', L.length <= 35],
      ['LinkedIn (PDF)', '300 páginas', true],
      ['Pinterest', 'de 2 a 5', L.length >= 2 && L.length <= 5],
      ['X', '4', L.length <= 4],
    ];
    const hacerHistorias = !vertical && L.some(l => l.familia)
      ? boton('Hacer también las historias (9:16)', { clase: 'ce-btn ce-ancho', title: 'El mismo carrusel en 9:16, como pieza aparte (gratis)' }, () => historias())
      : null;
    P.appendChild(grupo(L.length > 1 ? `Lámina ${ED.lamina + 1} de ${L.length}` : 'Carrusel',
      L.length > 1 ? el('label', { clase: 'ce-campo' }, el('span', {}, 'Texto alternativo de esta lámina'), alt) : null,
      L.length > 1 ? null : el('small', { clase: 'ce-pista' }, 'Para hacer un carrusel, añade láminas con «＋ Lámina», debajo del lienzo.'),
      L.length > 1 ? el('div', { clase: 'ce-campo' }, el('span', {}, `¿Dónde caben ${L.length} láminas?`),
        el('ul', { clase: 'ce-donde-cabe' }, ...filas.map(([red, cuantas, cabe]) =>
          el('li', { clase: cabe ? 'si' : 'no' }, el('b', {}, `${cabe ? '✓' : '✗'} ${red}`), ` · ${cuantas}`)))) : null,
      hacerHistorias));
  }

  /**
   * «Hacer también las historias» (graficas-3c-extras, B3): el servidor monta
   * el mismo carrusel en 9:16 y se abre como una pieza NUEVA sin guardar
   * (la de ahora no se toca). Antes hay que guardar: abrir otra cierra esta.
   */
  async function historias() {
    const yo = ED;
    if (!yo.piezaId || firmaDoc() !== yo.guardado) {
      avisoPantalla('Guarda primero este carrusel: las historias salen de lo guardado y se abren aparte.', true);
      return;
    }
    avisoPantalla('Montando las historias en 9:16…');
    try {
      const r = await yo.opc.pedir(yo.opc.api(yo.cid, '/capas/historias'), { method: 'POST', cuerpo: { doc: docParaEnviar() } });
      if (ED !== yo) return;
      await abrir(Object.assign({}, yo.opc, { pieza: null, duplicar: false, docInicial: r.doc, avisoInicial: '', que: '', desdeCrear: null }));
      // es nueva y no está guardada: al cerrar sin guardar, que lo pregunte
      if (ED && ED !== yo) { ED.guardado = ''; pintarEstado(); }
      if (ED && ED !== yo) avisoPantalla('Estas son las historias (9:16), aún sin guardar: revísalas y pulsa «Guardar». El carrusel de antes sigue igual.');
    } catch (e) {
      if (ED === yo) avisoPantalla(`No se han podido hacer las historias: ${e.message}`, true);
    }
  }


  /* ---------------------------------------------------------------- familias (graficas-3-carrusel)
   * Cada plantilla es una familia de carrusel: el servidor compone las láminas
   * de cada tipo con su estilo (pasos/graficas_carrusel.py). Lo que devuelve
   * sustituye al documento solo si no se ha cambiado nada mientras tanto. */

  function familiaActual() {
    const lam = ED.doc.laminas[ED.lamina];
    return lam.familia || (ED.doc.laminas.find(l => l.familia) || {}).familia || ED.origen.plantilla || 1;
  }

  async function catalogoCarrusel() {
    if (ED.carCat) return ED.carCat;
    const yo = ED;
    const r = await yo.opc.pedir(`${yo.opc.base}/api/graficas/carrusel/catalogo`);
    yo.carCat = r;
    return r;
  }

  /** Pide al servidor un documento nuevo (montar, añadir, partir) y lo pone si
   * no se ha tocado nada mientras tanto. -> la respuesta, o null. */
  async function docDelServidor(ruta, cuerpo, aviso) {
    if (ED.montando) return null;
    terminarEdicionTexto(true);
    const yo = ED;
    const antes = firmaDoc();
    yo.montando = true;
    avisoPantalla(aviso);
    try {
      const r = await yo.opc.pedir(yo.opc.api(yo.cid, ruta), { method: 'POST', cuerpo: Object.assign({ doc: docParaEnviar() }, cuerpo) });
      if (ED !== yo) return null;
      if (firmaDoc() !== antes) {
        avisoPantalla('Has cambiado algo mientras se componía: no se ha aplicado. Vuelve a pulsarlo.', true);
        return null;
      }
      ED.doc = r.doc;
      delete ED.doc.origen;
      asegurarIdsLaminas(ED.doc);
      ED.lamina = Math.min(ED.lamina, ED.doc.laminas.length - 1);
      ED.sel = [];
      cargarFotosDelDoc();
      cargarLetrasDelDoc();
      return r;
    } catch (e) {
      if (ED === yo) avisoPantalla(`No se ha podido: ${e.message}`, true);
      return null;
    } finally {
      yo.montando = false;
    }
  }

  function repintarTodoElCarrusel() {
    medirLienzo();
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
    revisarZonas();
  }

  async function anadirLaminaDeTipo(tipo) {
    if (ED.doc.laminas.length >= MAX_LAMINAS) { avisoPantalla(`Un carrusel tiene como mucho ${MAX_LAMINAS} láminas.`, true); return; }
    const donde = ED.lamina + 1;
    const r = await docDelServidor('/capas/lamina', { donde, familia: familiaActual(), tipo }, 'Componiendo la lámina…');
    if (!r) return;
    ED.lamina = donde;
    repintarTodoElCarrusel();
    avisoPantalla(ED.sencillo ? `Imagen «${NOMBRE_TIPO[tipo]}» añadida con el mismo estilo. Toca sus textos para escribirlos.`
      : `Lámina «${NOMBRE_TIPO[tipo]}» añadida con el estilo de la familia. Cambia sus textos con doble clic.`);
  }

  async function montarEstaLamina(n, tipo) {
    const r = await docDelServidor('/capas/lamina', { lamina: ED.lamina, familia: n, tipo }, 'Volviendo a montar la lámina…');
    if (!r) return;
    repintarTodoElCarrusel();
    avisoPantalla('Lámina recolocada: sus textos y lo que añadiste se conservan. Ctrl+Z vuelve a lo de antes.');
  }

  async function montarTodas(n) {
    const r = await docDelServidor('/capas/montar-todas', { familia: n }, 'Volviendo a montar todas las láminas…');
    if (!r) return;
    repintarTodoElCarrusel();
    avisoPantalla('Todas las láminas con la familia nueva (las «En blanco» se quedan como estaban). Ctrl+Z lo deshace.');
  }

  function abrirPartirTexto() {
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Partir un texto en láminas' });
    const cerrarModal = () => capaVista.remove();
    const area = el('textarea', { clase: 'ce-partir-texto', rows: '12', maxlength: '12000', 'aria-label': 'El texto del carrusel',
      placeholder: 'Pega aquí tu texto. Cada párrafo (separado por una línea en blanco) es una lámina:\n\nEl primero es la portada.\n\nUn párrafo con viñetas (- uno, - dos) es una lista.\n\n8 de 10\nUn párrafo que empieza por una cifra corta es un dato.\n\nLos demás, puntos numerados.' });
    const hay = ED.doc.laminas.length;
    const partir = async modo => {
      const texto = area.value;
      if (!texto.trim()) { area.focus(); return; }
      cerrarModal();
      const r = await docDelServidor('/capas/partir', { familia: familiaActual(), texto, modo }, 'Partiendo el texto en láminas…');
      if (!r) return;
      ED.lamina = 0;
      repintarTodoElCarrusel();
      const extra = (r.avisos || []).join(' ');
      avisoPantalla(`${ED.doc.laminas.length} láminas. ${extra} Ctrl+Z vuelve a lo de antes.`.trim(), !!extra);
    };
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo ce-modal-partir' },
      el('h2', {}, 'Partir un texto en láminas'),
      el('p', { clase: 'ce-pista' }, 'Sin IA: cada párrafo es una lámina, con la primera línea de titular, y al final va el cierre. Caben 20 láminas.'),
      area,
      el('div', { clase: 'ce-botonera' },
        boton(hay > 1 ? 'Sustituir las láminas' : 'Hacer el carrusel', { clase: 'ce-btn ce-primario' }, () => partir('sustituir')),
        hay > 1 ? boton('Añadirlas (antes del cierre)', {}, () => partir('anadir')) : null,
        boton('Cancelar', {}, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    ED.raiz.appendChild(capaVista);
    area.focus();
  }

  async function revisarCarrusel(caja) {
    caja.textContent = 'Revisando…';
    const yo = ED;
    try {
      const r = await yo.opc.pedir(yo.opc.api(yo.cid, '/capas/nota'), { method: 'POST', cuerpo: { doc: docParaEnviar() } });
      if (ED !== yo) return;
      const notas = r.nota.slice();
      const f = formato();
      if ((f.zL || f.zR) && !(f.H / f.W > 1.7)) {
        notas.push({ nivel: 'aviso', texto: `En la cuadrícula del perfil (3:4) la portada se recorta por los lados: «Ver lo que tapa la red» enseña qué se pierde.` });
      }
      if (ED.avisos.length) notas.push({ nivel: 'mal', texto: `En esta lámina, ${ED.avisos.length} capa(s) quedan en lo que tapa la red o se salen.` });
      caja.textContent = '';
      caja.appendChild(el('ul', { clase: 'ce-nota-carrusel' }, ...notas.map(n =>
        el('li', { clase: n.nivel }, el('b', {}, n.nivel === 'bien' ? '✓' : n.nivel === 'mal' ? '✗' : '!'), ' ', n.texto))));
    } catch (e) {
      caja.textContent = `No se ha podido revisar: ${e.message}`;
    }
  }

  /** Tras guardar un carrusel: si siguen textos de muestra, se dice antes de
   * que salga a ninguna parte (descargar o publicar). */
  async function avisarMuestras(E) {
    try {
      const r = await E.opc.pedir(E.opc.api(E.cid, '/capas/nota'), { method: 'POST', cuerpo: { doc: Object.assign(copia(E.doc), { version: 2, origen: copia(E.origen) }) } });
      const muestra = (r.nota || []).find(x => x.nivel === 'mal' && /muestra/.test(x.texto));
      if (muestra && ED === E) avisoPantalla(`Guardado. Ojo: ${muestra.texto}`, true);
    } catch (_) { /* la nota es una ayuda: si falla, no se dice nada */ }
  }

  /** La familia, el tipo, montar y partir, en el panel de la pieza. */
  function panelFamilias(P) {
    const cat = ED.carCat;
    if (!cat) {
      catalogoCarrusel().then(() => { if (ED && ED.der && !ED.sel.length) pintarDerecha(); }).catch(() => {});
      return;
    }
    const lam = ED.doc.laminas[ED.lamina];
    const f = formato();
    const horiz = f.W / f.H > 1.3;
    const fam = el('select', { 'aria-label': 'Familia del carrusel' }, ...cat.familias.map(x => el('option', { value: String(x.n) }, `${x.n} · ${x.nombre}`)));
    fam.value = String(familiaActual());
    const tipos = cat.tipos.filter(t => !horiz || t.horizontal);
    const tipo = el('select', { 'aria-label': 'Tipo de esta lámina' }, ...tipos.map(t => el('option', { value: t.id }, t.nombre)));
    tipo.value = tipos.some(t => t.id === lam.tipo) ? lam.tipo : (ED.lamina === 0 ? 'portada' : 'punto');
    const nota = el('div', { clase: 'ce-pista' });
    P.appendChild(grupo('Familia de carrusel',
      el('small', { clase: 'ce-pista' }, 'Cada plantilla es una familia: sus láminas de dentro llevan su letra, su adorno y los colores del Kit.'),
      el('label', { clase: 'ce-campo' }, el('span', {}, 'Familia'), fam),
      el('label', { clase: 'ce-campo' }, el('span', {}, 'Tipo de esta lámina'), tipo),
      horiz ? el('small', { clase: 'ce-pista' }, 'En horizontal no hay Lista, Antes / después ni Pasos: no caben bien.') : null,
      el('div', { clase: 'ce-botonera' },
        boton('Montar esta lámina', { title: 'Con esta familia y este tipo: sus textos van a su sitio' }, () => montarEstaLamina(parseInt(fam.value, 10), tipo.value)),
        ED.doc.laminas.length > 1 ? boton('… y todas con esta familia', { title: 'Las «En blanco» se quedan como están' }, () => montarTodas(parseInt(fam.value, 10))) : null),
      boton('Partir un texto en láminas…', { clase: 'ce-btn ce-ancho' }, abrirPartirTexto),
      ED.doc.laminas.length > 1 ? boton('Revisar el carrusel', { clase: 'ce-btn ce-ancho', title: 'La nota del carrusel: portada, segunda portada, una idea por lámina, cierre, textos alternativos…' },
        () => revisarCarrusel(nota)) : null,
      nota));
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
    if (ED.sencillo && !(ev.target.dataset && (ev.target.dataset.asa || ev.target.dataset.girar))) {
      // modo sencillo: un toque escribe el texto o elige la foto; solo lo
      // añadido a mano (adornos) se arrastra
      const tocada = capaParaTocar(ev);
      if (!tocada || !movibleSencillo(tocada)) { tocarSencillo(ev, tocada); return; }
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
    const proporcion = (c.tipo === 'texto' && esquina) || (esquina && (mantener !== (c.tipo === 'logo' || c.tipo === 'icono' || (c.tipo === 'forma' && c.figura === 'elipse') || (c.tipo === 'imagen' && c.radio === 'elipse'))));
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
      if (ED.sTextoArea && ED.sTextoArea.isConnected) ED.sTextoArea.value = txt;
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
    // modo sencillo: el teclado tampoco mueve, duplica ni borra lo de la plantilla (salvo un texto)
    const fijaEnSencillo = c => ED.sencillo && !movibleSencillo(c);
    if (ctrl && (tecla === 'd' || tecla === 'D')) { ev.preventDefault(); if (!seleccion().some(fijaEnSencillo)) duplicar(); return; }
    if (ctrl && (tecla === 'a' || tecla === 'A')) {
      ev.preventDefault();
      ED.sel = capas().filter(c => !c.oculto && !c.bloqueado && !fijaEnSencillo(c)).map(c => c.id);
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
    if ((tecla === 'Delete' || tecla === 'Backspace') && ED.sel.length) {
      ev.preventDefault();
      if (seleccion().some(c => fijaEnSencillo(c) && c.tipo !== 'texto')) { avisoPantalla('La foto se cambia con «Cambiar foto»; para quitar partes del diseño, «Edición avanzada».'); return; }
      borrar();
      return;
    }
    if (tecla === 'Enter' && ED.sel.length === 1 && seleccion()[0].tipo === 'texto') { ev.preventDefault(); empezarEdicionTexto(ED.sel[0], true); return; }
    if (ev.altKey && (tecla === 'ArrowLeft' || tecla === 'ArrowRight')) {
      // Alt+flechas: la lámina, antes o después
      ev.preventDefault();
      moverLamina(ED.lamina, ED.lamina + (tecla === 'ArrowLeft' ? -1 : 1));
      return;
    }
    if (tecla === 'PageUp' || tecla === 'PageDown') { ev.preventDefault(); irALamina(ED.lamina + (tecla === 'PageUp' ? -1 : 1)); return; }
    const flechas = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (flechas[tecla] && ED.sel.length) {
      ev.preventDefault();
      const paso = (ev.shiftKey ? 10 : 1) * ED.escala;     // 1 px de la pieza de verdad (10 con Mayús)
      for (const c of seleccion()) if (!c.bloqueado && !fijaEnSencillo(c)) { moverPx(c, flechas[tecla][0] * paso, flechas[tecla][1] * paso); pintarCapa(c.id); }
      pintarMarcas();
      clearTimeout(ED.flechas);
      // una ráfaga de flechas cuenta como UN cambio
      ED.flechas = setTimeout(() => { if (ED) { commit(); pintarDerecha(); } }, 400);
    }
  }

  /* ================================================================ modo sencillo (graficas-facil, 26-11-2026)
   * El mismo editor con menos a la vista: tocar un texto lo escribe, tocar la
   * foto la elige, y a la derecha solo Cambiar foto, Adornos, Otro estilo,
   * Añadir imagen, Guardar, Descargar y la historia. Lo de la plantilla no se
   * arrastra (mover cosas es de «Edición avanzada»); lo añadido a mano sí.
   * El modo se recuerda SOLO en el navegador: en el documento cambiaría su
   * huella. Vocabulario: «estilo» (familia) e «imagen» (lámina). */

  const CLAVE_MODO = 'crearia.graficas.modo';

  function modoRecordado() {
    try { return localStorage.getItem(CLAVE_MODO) || ''; } catch (_) { return ''; }
  }

  function recordarModo(modo) {
    try { localStorage.setItem(CLAVE_MODO, modo); } catch (_) { /* sin almacenamiento: vale para esta vez */ }
  }

  function cambiarModo() {
    terminarEdicionTexto(true);
    ED.sencillo = !ED.sencillo;
    recordarModo(ED.sencillo ? 'sencillo' : 'avanzado');
    ED.raiz.classList.toggle('ce-sencillo', ED.sencillo);
    ED.sel = [];
    pintarBarra();
    pintarPaneles();
    pintarTira();
    medirLienzo();
    pintarTodo();
    // el lienzo cambia de sitio al quitar o poner el panel de la izquierda
    requestAnimationFrame(() => { if (ED) { medirLienzo(); pintarTodo(); } });
    avisoPantalla(ED.sencillo ? 'Modo sencillo: toca un texto para escribirlo.' : 'Edición avanzada: arrastra, cambia el tamaño y gira cada cosa.');
  }

  /** En el modo sencillo solo se arrastra lo añadido a mano (sin papel en la plantilla). */
  function movibleSencillo(c) {
    return !!c && !c.bloqueado && !c.rol;
  }

  /** Del editor de una pieza recién creada al paso 2 de «+ Crear», con lo elegido. */
  function volverACrear() {
    terminarEdicionTexto(true);
    if (firmaDoc() !== ED.firmaCreada
        && !window.confirm('Vuelves al paso 2 con tu tema, tu foto y tu estilo. Lo que has cambiado aquí (textos, adornos) se pierde. ¿Seguir?')) return;
    const opc = Object.assign({}, ED.opc, { retomar: ED.opc.desdeCrear });
    cerrarYa(false);
    crear(opc);
  }

  const esQr = c => c.tipo === 'imagen' && (c.rol === 'qr' || c.nombre === 'QR');

  /** La capa que se toca: la primera de texto, foto, icono o logo bajo el dedo
   * (una forma de la plantilla encima de un texto no lo tapa). */
  function capaParaTocar(ev) {
    let forma = null;
    for (const n of document.elementsFromPoint(ev.clientX, ev.clientY)) {
      let c = null;
      if (n.dataset && n.dataset.mover) c = capa(n.dataset.mover);
      else {
        const capaN = n.closest && n.closest('[data-c]');
        if (capaN && ED.lienzo.contains(capaN)) c = capa(capaN.dataset.c);
      }
      if (!c || c.oculto) continue;
      if (c.tipo !== 'forma' || !c.rol) return c;
      forma = forma || c;
    }
    return forma && !forma.rol ? forma : null;
  }

  function tocarSencillo(ev, c) {
    if (!ED.marco.contains(ev.target) && ev.target !== ED.escenario) return;
    ev.preventDefault();
    const x0 = ev.clientX, y0 = ev.clientY;
    const yo = ED;
    const alSoltarToque = e2 => {
      window.removeEventListener('pointerup', alSoltarToque, true);
      window.removeEventListener('pointercancel', alSoltarToque, true);
      if (ED !== yo || e2.type === 'pointercancel' || Math.hypot(e2.clientX - x0, e2.clientY - y0) > 10) return;
      if (!c) {
        if (ED.sel.length) { ED.sel = []; pintarMarcas(); pintarPaneles(); }
        return;
      }
      if (c.tipo === 'texto') {
        empezarEdicionTexto(c.id, false);
        cursorDondeSeToca(c.id, e2.clientX, e2.clientY);
        return;
      }
      ED.sel = [c.id];
      pintarMarcas();
      pintarPaneles();
      if (c.tipo === 'imagen' && !esQr(c)) avisoPantalla('Foto elegida: «Cambiar foto», a la derecha (o debajo en el móvil).');
    };
    window.addEventListener('pointerup', alSoltarToque, true);
    window.addEventListener('pointercancel', alSoltarToque, true);
  }

  /** El cursor donde se tocó el texto (si el navegador sabe decirlo), o al final. */
  function cursorDondeSeToca(id, x, y) {
    const n = nodoDe(id);
    if (!n || ED.editando !== id) return;
    const s = window.getSelection();
    let r = null;
    try {
      if (document.caretRangeFromPoint) r = document.caretRangeFromPoint(x, y);
      else if (document.caretPositionFromPoint) {
        const pos = document.caretPositionFromPoint(x, y);
        if (pos) { r = document.createRange(); r.setStart(pos.offsetNode, pos.offset); r.collapse(true); }
      }
    } catch (_) { r = null; }
    if (!r || !n.contains(r.startContainer)) {
      r = document.createRange();
      r.selectNodeContents(n);
      r.collapse(false);
    }
    s.removeAllRanges();
    s.addRange(r);
  }

  /** ¿Qué es esta pieza? (para los nombres del panel) */
  function queEs() {
    const f = formato();
    if (ED.doc.laminas.length > 1 || ED.opc.que === 'carrusel') return 'carrusel';
    return f.H / f.W > 1.7 ? 'historia' : 'publicacion';
  }

  /** La foto de la plantilla en esta imagen (no un QR ni una foto añadida a mano). */
  function fotoDeLaImagen() {
    const lista = capas().filter(c => c.tipo === 'imagen' && !esQr(c));
    return lista.find(c => c.rol) || lista[0] || null;
  }

  function panelSencillo(Panel) {
    if (!ED.sArriba || ED.sArriba.parentElement !== Panel) {
      Panel.textContent = '';
      ED.sArriba = el('div', { clase: 'ce-s-arriba' });
      ED.sAbajo = el('div', { clase: 'ce-s-abajo' });
      ED.sClave = '';
      Panel.append(ED.sArriba, ED.sAbajo);
    }
    const P = ED.sArriba;
    P.textContent = '';
    const que = queEs();
    P.appendChild(el('h2', {}, { publicacion: 'Tu publicación', carrusel: 'Tu carrusel', historia: 'Tu historia' }[que]));
    P.appendChild(el('p', { clase: 'ce-pista ce-s-ayuda' }, 'Toca un texto de la imagen para escribirlo. ',
      'Para mover cada cosa a mano, «Edición avanzada» (arriba).'));
    const c = seleccion()[0] || null;
    if (c && c.tipo === 'texto') P.appendChild(grupoTextoSencillo(c));
    else if (c && c.tipo !== 'imagen') {
      P.appendChild(grupo(nombreDe(c),
        el('small', { clase: 'ce-pista' }, movibleSencillo(c) ? 'Arrástralo para moverlo.' : ''),
        boton('Quitar', { clase: 'ce-btn ce-peligro ce-ancho' }, borrar)));
    }
    P.appendChild(grupoFotoSencillo(c && c.tipo === 'imagen' && !esQr(c) ? c : null));
    P.appendChild(grupo('Adornos (gratis)',
      el('div', { clase: 'ce-anadir' },
        boton('＋ Icono', { title: 'Iconos sencillos con los colores de tu Kit' }, () => elegirIcono(null)),
        boton('＋ Pegatina', { title: '«Nuevo», «Guárdalo», un globo o una flecha' }, ev => abrirPegatinas(ev.currentTarget))),
      el('small', { clase: 'ce-pista' }, 'Salen en el centro: arrástralos a su sitio.')));
    P.appendChild(grupoEstiloSencillo());
    if (que === 'carrusel') P.appendChild(grupoAnadirImagen());
    // «Terminar» solo se rehace si cambia lo que ofrece (una o varias imágenes…)
    const f = formato();
    const clave = [que, ED.doc.laminas.length < 2, f.H / f.W > 1.7, ED.doc.laminas.some(l => l.familia)].join('|');
    if (clave !== ED.sClave) {
      ED.sAbajo.replaceChildren(grupoTerminar(que));
      ED.sClave = clave;
    }
    pintarEstado();
  }

  function grupoTextoSencillo(c) {
    // el mismo alto escribiendo en la imagen o no: que nada salte bajo el dedo
    const escribiendo = ED.editando === c.id;
    const area = el('textarea', { rows: '3', maxlength: String(LIMITES.texto), 'aria-label': 'Este texto', clase: 'ce-s-texto', readonly: escribiendo });
    area.value = String(c.txt || '').trim();
    ED.sTextoArea = escribiendo ? area : null;
    area.addEventListener('input', () => { c.txt = area.value.slice(0, LIMITES.texto); pintarCapa(c.id); pintarMarcas(); });
    area.addEventListener('change', () => { commit(); pintarTira(); });
    return grupo('Este texto', area,
      el('small', { clase: 'ce-pista' }, escribiendo ? 'Escribiendo en la imagen: toca fuera para terminar.' : 'Escríbelo aquí o tocándolo en la imagen.'),
      c.enlace ? el('small', { clase: 'ce-pista' }, 'Sale igual en todas las imágenes del carrusel.') : null,
      boton('Quitar este texto', { clase: 'ce-btn ce-peligro' }, borrar));
  }

  function grupoFotoSencillo(elegida) {
    const destino = elegida || fotoDeLaImagen();
    const sube = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', clase: 'ce-oculto', id: 'ce-s-foto',
      onchange: ev => { const f = ev.target.files[0]; ev.target.value = ''; if (f && destino) subirFoto(f, destino.id); } });
    if (!destino) {
      const conEstilos = ED.doc.laminas.some(l => l.familia);
      return grupo('Foto',
        el('small', { clase: 'ce-pista' }, conEstilos ? 'Este estilo no lleva foto. Elige uno marcado «📷 con foto» y luego pon la tuya (o una de tus vídeos).'
          : 'Esta pieza no tiene un hueco para foto.'),
        conEstilos ? boton('Ver los estilos con foto', { clase: 'ce-btn ce-ancho ce-s-estilos-foto' }, () => abrirEstilos(true)) : null,
        el('small', { clase: 'ce-pista' }, 'Pronto: crear la imagen con IA.'));
    }
    const foto = destino.src && ED.fotos[destino.src];
    return grupo('Foto',
      sube, el('label', { clase: 'ce-btn ce-ancho ce-s-cambiar-foto', for: 'ce-s-foto', tabindex: '0',
        onkeydown: ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); sube.click(); } } }, destino.src ? 'Cambiar foto' : 'Poner una foto'),
      hayVideos() ? boton('Una foto de mis vídeos', { clase: 'ce-btn ce-ancho', title: 'Una imagen que ya pagaste en un vídeo de este proyecto (gratis)' }, () => elegirFotoDeVideo(destino.id)) : null,
      foto && foto.falta ? el('small', { clase: 'ce-pista malo' }, 'Esa foto ya no está en el proyecto: pon otra.') : null,
      destino.src ? campoDeslizador('Acercar la foto', (destino.encuadre || {}).zoom || 1, v => {
        destino.encuadre = Object.assign({ x: 50, y: 50, zoom: 1 }, destino.encuadre, { zoom: v });
      }, 1, 4, 0.05, v => `${redondo(v, 2)}×`) : null,
      el('small', { clase: 'ce-pista' }, 'Pronto: crear la imagen con IA.'));
  }

  function grupoEstiloSencillo() {
    const cat = ED.carCat;
    const n = familiaActual();
    const nombre = cat ? ((cat.familias.find(f => f.n === n) || {}).nombre || `Estilo ${n}`) : '';
    const puedeVolver = !!ED.estiloDespues && firmaDoc() === ED.estiloDespues;
    if (!ED.doc.laminas.some(l => l.familia)) {
      // una pieza de antes o empezada en blanco no tiene estilo: cambiarlo
      // rellenaría sus huecos con textos de muestra (una cita, un descuento)
      // que nadie ha escrito. Se dice, en vez de ofrecerlo.
      return grupo('Estilo',
        el('small', { clase: 'ce-pista ce-s-sin-estilo' }, 'Esta pieza no tiene estilo (es de antes o empezada en blanco), así que no hay estilos para elegir. ',
          'Para recolocarla, «Edición avanzada» → «Volver a montar».'));
    }
    return grupo('Estilo',
      nombre ? el('p', { clase: 'ce-s-estilo' }, 'Ahora: ', el('b', {}, nombre)) : null,
      boton('Otro estilo…', { clase: 'ce-btn ce-ancho ce-s-otro-estilo', title: 'Cambia la colocación, la letra y los adornos; tus textos y tu foto se quedan' }, () => abrirEstilos(false)),
      puedeVolver ? boton('↶ Volver al estilo de antes', { clase: 'ce-btn ce-ancho ce-s-volver-estilo' }, volverAlEstiloDeAntes) : null);
  }

  function grupoAnadirImagen() {
    const cat = ED.carCat;
    const lleno = ED.doc.laminas.length >= MAX_LAMINAS;
    if (!cat) return grupo('Añadir una imagen', el('small', { clase: 'ce-pista' }, 'Cargando…'));
    const f = formato();
    const horiz = f.W / f.H > 1.3;
    // la Cita no: sería la opinión de un cliente que nadie ha dicho
    const tipos = cat.tipos.filter(t => t.id !== 'portada' && t.id !== 'cita' && (!horiz || t.horizontal));
    const sel = el('select', { 'aria-label': 'Qué imagen añadir', clase: 'ce-s-tipo' },
      ...tipos.map(t => el('option', { value: t.id }, t.nombre)));
    sel.value = 'punto';
    return grupo('Añadir una imagen al carrusel',
      el('label', { clase: 'ce-campo' }, el('span', {}, 'Qué imagen'), sel),
      boton(lleno ? `Ya tiene ${MAX_LAMINAS} imágenes` : '＋ Añadir después de esta', { clase: 'ce-btn ce-ancho ce-s-anadir', disabled: lleno },
        () => anadirLaminaDeTipo(sel.value)));
  }

  function grupoTerminar(que) {
    const vertical = formato().H / formato().W > 1.7;
    const una = ED.doc.laminas.length < 2;
    ED.sBotones = [];
    const pide = b => { ED.sBotones.push(b); return b; };
    const bajar = como => {
      if (typeof ED.opc.descargar !== 'function') return;
      ED.opc.descargar({ id: ED.piezaId, laminas: ED.doc.laminas.length, nombre: ED.doc.nombre || '' }, como);
    };
    ED.sPista = el('small', { clase: 'ce-pista ce-s-guarda-antes' }, 'Guarda primero para descargarla.');
    const g = grupo('Terminar',
      boton('Guardar', { clase: 'ce-btn ce-primario ce-ancho ce-s-guardar' }, () => guardar()),
      ED.sPista,
      el('div', { clase: 'ce-botonera ce-s-descargas' },
        una ? pide(boton('Descargar PNG', { clase: 'ce-btn ce-s-png' }, () => bajar('png'))) : pide(boton('Descargar las imágenes (ZIP)', { clase: 'ce-btn ce-s-zip' }, () => bajar('zip'))),
        una ? pide(boton('JPG', { clase: 'ce-btn ce-s-jpg', title: 'Pesa menos' }, () => bajar('jpg'))) : pide(boton('PDF para LinkedIn', { clase: 'ce-btn ce-s-pdf' }, () => bajar('pdf')))),
      !vertical && ED.doc.laminas.some(l => l.familia)
        ? pide(boton(que === 'carrusel' ? 'Hacer también las historias' : 'Hacer también la historia', {
          clase: 'ce-btn ce-ancho ce-s-historia', title: 'La misma pieza en 9:16; se crea aparte y esta no cambia (gratis)' }, () => historias()))
        : null);
    return g;
  }

  /* ---------------------------------------------------------------- «Otro estilo»
   * Las portadas de los 16 estilos pintadas pequeñas con TUS textos, tu foto y
   * tu Kit (POST /capas/miniaturas, de 4 en 4); elegir una vuelve a montar todo
   * con ese estilo (como «… y todas con esta familia») y deja «Volver al estilo
   * de antes» a la vista. */

  function datosDeLaPortada(doc) {
    const portada = doc.laminas[0].capas;
    const texto = rol => {
      const c = portada.find(x => x.tipo === 'texto' && x.rol === rol && !x.oculto && String(x.txt || '').trim());
      return c ? String(c.txt).trim() : '';
    };
    const foto = portada.find(x => x.tipo === 'imagen' && !esQr(x) && x.src);
    return { titulo: (texto('titulo') || texto('cita')).slice(0, 90), apoyo: texto('apoyo').slice(0, 140), foto: foto ? foto.src : '' };
  }

  /** Los estilos que llevan foto en la portada (lo dice el servidor con las miniaturas). */
  const conFotoConocidos = [];
  const marcaFoto = n => (conFotoConocidos.includes(n) ? el('span', { clase: 'gc-con-foto' }, '📷 con foto') : null);

  /** Pinta las miniaturas en una rejilla: `turno()` dice si siguen valiendo. */
  async function pedirMiniaturas(opc, cid, cuerpo, todas, alLlegar, sigue, senal) {
    let orden = todas.slice();
    const hechas = new Set();
    for (let vuelta = 0; vuelta < 8; vuelta++) {
      const tanda = orden.filter(n => !hechas.has(n)).slice(0, 4);
      if (!tanda.length) return orden;
      const r = await opc.pedir(opc.api(cid, '/capas/miniaturas'), { method: 'POST', cuerpo: Object.assign({}, cuerpo, { familias: tanda }), signal: senal });
      if (!sigue()) return orden;
      if (vuelta === 0 && Array.isArray(r.orden) && r.orden.length) orden = r.orden.filter(n => todas.includes(n));
      if (Array.isArray(r.con_foto)) conFotoConocidos.splice(0, conFotoConocidos.length, ...r.con_foto);
      for (const m of r.miniaturas || []) { hechas.add(m.n); alLlegar(m, orden); }
    }
    return orden;
  }

  async function abrirEstilos(conFotoPrimero) {
    const yo = ED;
    let cat;
    try { cat = await catalogoCarrusel(); } catch (e) { avisoPantalla(`No se han podido leer los estilos: ${e.message}`, true); return; }
    if (ED !== yo) return;
    terminarEdicionTexto(true);
    const capaVista = el('div', { clase: 'ce-modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Otro estilo' });
    const parar = new AbortController();
    const cerrarModal = () => { parar.abort(); capaVista.remove(); };
    const rejilla = el('div', { clase: 'gc-estilos', 'aria-live': 'polite' });
    const estado = el('p', { clase: 'ce-pista' }, 'Pintando los estilos con tus textos…');
    const actual = familiaActual();
    const celdas = {};
    const celda = (n, nombre) => {
      if (celdas[n]) return celdas[n];
      const b = el('button', { type: 'button', clase: 'gc-estilo', 'data-n': String(n), 'aria-pressed': String(n === actual),
        onclick: () => { cerrarModal(); ponerEstilo(n, nombre); } },
      el('span', { clase: 'gc-estilo-img' }, el('span', { clase: 'gc-estilo-espera' }, '…')), el('span', { clase: 'gc-estilo-nombre' }, nombre),
      el('span', { clase: 'gc-estilo-marca' }));
      celdas[n] = b;
      return b;
    };
    for (const f of cat.familias) rejilla.appendChild(celda(f.n, f.nombre));
    capaVista.appendChild(el('div', { clase: 'ce-modal-cuerpo ce-modal-estilos' },
      el('h2', {}, 'Elige otro estilo'),
      el('p', { clase: 'ce-pista' }, 'Cambia la colocación, la letra y los adornos de todas las imágenes. Tus textos y tu foto se quedan. Si no te gusta, «Volver al estilo de antes».'),
      estado, rejilla,
      el('div', { clase: 'ce-botonera' }, boton('Cancelar', {}, cerrarModal))));
    capaVista.addEventListener('pointerdown', ev => { if (ev.target === capaVista) cerrarModal(); });
    capaVista.addEventListener('keydown', ev => { if (ev.key === 'Escape') { ev.preventDefault(); cerrarModal(); } });
    ED.raiz.appendChild(capaVista);
    const p = datosDeLaPortada(ED.doc);
    const cuerpo = { que: queEs(), formato: ED.doc.formato, titulo: p.titulo, apoyo: p.apoyo, foto: p.foto, con_foto_primero: conFotoPrimero === true };
    let cuantas = 0;
    try {
      await pedirMiniaturas(yo.opc, yo.cid, cuerpo, cat.familias.map(f => f.n), (m, orden) => {
        const b = celdas[m.n];
        if (!b) return;
        b.firstChild.replaceChildren(el('img', { src: m.jpg, alt: `Estilo ${m.nombre}` }));
        b.lastChild.replaceChildren(...[marcaFoto(m.n)].filter(Boolean));
        cuantas += 1;
        estado.textContent = cuantas < cat.familias.length ? `Pintando los estilos (${cuantas} de ${cat.familias.length})…` : 'Toca el que más te guste.';
        // los primeros, los que mejor van con lo que llevas (con foto, los de foto)
        orden.forEach(n => celdas[n] && rejilla.appendChild(celdas[n]));
      }, () => ED === yo && capaVista.isConnected, parar.signal);
    } catch (e) {
      if (capaVista.isConnected && e.name !== 'AbortError') estado.textContent = `No se han podido pintar: ${e.message}. Puedes elegir por el nombre.`;
    }
  }

  async function ponerEstilo(n, nombre) {
    terminarEdicionTexto(true);
    const yo = ED;
    const antes = firmaDoc();
    if (!ED.doc.laminas.some(l => l.familia)) return;     // sin estilo no se ofrece (grupoEstiloSencillo)
    const r = await docDelServidor('/capas/montar-todas', { familia: n }, `Poniendo el estilo «${nombre}»…`);
    if (!r || ED !== yo) return;
    repintarTodoElCarrusel();
    const despues = firmaDoc();
    if (despues === antes) {
      avisoPantalla('Esta pieza no ha cambiado con ese estilo. Prueba otro, o «Edición avanzada».', true);
      return;
    }
    // «Volver al estilo de antes» solo mientras no se toque nada más (por la
    // firma del documento: la posición del historial deja de crecer en su tope)
    ED.estiloAntes = antes;
    ED.estiloDespues = despues;
    pintarDerecha();
    avisoPantalla(`Estilo «${nombre}». ¿No te gusta? «Volver al estilo de antes», a la derecha.`);
  }

  function volverAlEstiloDeAntes() {
    terminarEdicionTexto(true);
    if (!ED.estiloDespues || firmaDoc() !== ED.estiloDespues) {
      ED.estiloDespues = '';
      pintarDerecha();
      avisoPantalla('Ya cambiaste algo después del estilo: usa «↶» (arriba) para deshacer paso a paso.', true);
      return;
    }
    ED.doc = JSON.parse(ED.estiloAntes);
    ED.estiloAntes = ED.estiloDespues = '';
    ED.lamina = Math.min(ED.lamina, ED.doc.laminas.length - 1);
    ED.sel = [];
    cargarFotosDelDoc();
    cargarLetrasDelDoc();
    pintarTodo(); commit(); pintarPaneles(); pintarTira();
    avisoPantalla('Vuelve a estar como antes.');
  }

  /* ================================================================ «+ Crear» (graficas-facil)
   * Tres pasos: qué (publicación, carrusel o historia), de qué trata (el
   * texto, «Escríbelo por mí», la foto y el estilo con miniaturas) y el
   * resultado, que es este editor en el modo sencillo. Nada se guarda hasta
   * pulsar «Guardar» en el editor. Gratis: los textos van por el cupo de
   * Claude y lo demás solo pinta. */

  const QUE_CREAR = [
    { id: 'publicacion', nombre: 'Publicación', detalle: 'Una imagen para el feed', formato: 'v45', icono: '▢' },
    { id: 'carrusel', nombre: 'Carrusel', detalle: 'Varias imágenes que se deslizan', formato: 'v45', icono: '▤' },
    { id: 'historia', nombre: 'Historia', detalle: 'Vertical, a pantalla completa', formato: 'h916', icono: '▯' },
  ];
  const EJEMPLO_TEMA = '5 errores al alquilar una consola para tu fiesta';
  let ASISTENTE = null;

  /**
   * Abre «+ Crear». opc: lo mismo que `abrir`, y además
   * lote(), enBlanco() y clasico(): las puertas avanzadas de siempre.
   */
  async function crear(opc) {
    if (ASISTENTE) ASISTENTE.cerrar();
    if (ED) return;                                   // con el editor abierto, primero se cierra
    const raiz = el('div', { clase: 'gc', id: 'crear-grafica', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Crear una gráfica' });
    const S = {
      opc, cid: opc.cid, raiz, paso: 1, conFoto: [], que: '', formato: '', titulo: '', apoyo: '', tema: '', texto: '', modo: 'tema',
      cuantas: 7, piezas: null, piezasDe: '', avisosIA: [], escribiendo: false, creando: false, foto: '', fotoUrl: '', subiendo: false,
      familia: 0, elegidaAMano: false, minis: {}, orden: [], turno: 0, parar: null, espera: null, familias: [], cerrado: false,
    };
    ASISTENTE = S;
    S.cerrar = () => {
      S.cerrado = true;
      if (S.parar) S.parar.abort();
      clearTimeout(S.espera);
      document.removeEventListener('keydown', S.teclas, true);
      raiz.remove();
      document.body.classList.remove('ce-abierto');
      if (ASISTENTE === S) ASISTENTE = null;
    };
    S.salir = () => {
      const escrito = S.titulo || S.tema || S.texto || S.piezas;
      if (escrito && !window.confirm('¿Salir sin crear? Se pierde lo que has escrito.')) return;
      S.cerrar();
    };
    // Esc, esté donde esté el foco; y las teclas no llegan a los atajos del Studio
    S.teclas = ev => {
      if (ev.key === 'Escape' && !raiz.querySelector('.ce-modal')) { ev.preventDefault(); ev.stopPropagation(); S.salir(); }
    };
    document.addEventListener('keydown', S.teclas, true);
    for (const tipo of ['keydown', 'keyup', 'keypress']) raiz.addEventListener(tipo, ev => ev.stopPropagation());
    document.body.appendChild(raiz);
    document.body.classList.add('ce-abierto');
    try {
      const r = await opc.pedir(`${opc.base}/api/graficas/carrusel/catalogo`);
      S.familias = r.familias || [];
      S.tipos = r.tipos || [];
    } catch (e) {
      S.cerrar();
      opc.toast(`No se ha podido abrir «Crear»: ${e.message}`, true);
      return;
    }
    if (S.cerrado) return;
    // «← Cambiar tema, foto o estilo» desde el editor: se vuelve al paso 2 con lo elegido
    if (opc.retomar) Object.assign(S, opc.retomar, { paso: 2 });
    pintarAsistente(S);
  }

  function cabeceraAsistente(S) {
    const pasos = ['Qué', 'De qué trata', 'Ajusta y guarda'];
    return el('header', { clase: 'gc-cab' },
      el('h2', {}, 'Crear'),
      el('ol', { clase: 'gc-pasos', 'aria-label': 'Pasos' }, ...pasos.map((p, i) =>
        el('li', { clase: i + 1 === S.paso ? 'actual' : (i + 1 < S.paso ? 'hecho' : ''), 'aria-current': i + 1 === S.paso ? 'step' : null },
          el('b', {}, String(i + 1)), ' ', p))),
      el('span', { clase: 'ce-crece' }),
      el('button', { type: 'button', clase: 'ce-btn gc-cerrar', 'aria-label': 'Cerrar', title: 'Cerrar (Esc)', onclick: () => S.salir() }, '✕'));
  }

  function pintarAsistente(S) {
    const R = S.raiz;
    R.textContent = '';
    const caja = el('div', { clase: 'gc-caja' }, cabeceraAsistente(S));
    R.appendChild(caja);
    if (S.paso === 1) pasoQue(S, caja); else pasoTema(S, caja);
  }

  /* ---------------------------------------------------------------- paso 1 */

  function pasoQue(S, caja) {
    const elegir = q => {
      S.que = q.id;
      S.formato = q.formato;
      S.paso = 2;
      pintarAsistente(S);
    };
    const avanzado = (que, clase, texto, ayuda) => (typeof S.opc[que] === 'function'
      ? el('button', { type: 'button', clase: `gc-enlace ${clase}`, title: ayuda, onclick: () => { S.cerrar(); S.opc[que](); } }, texto) : null);
    caja.appendChild(el('div', { clase: 'gc-cuerpo' },
      el('h3', { clase: 'gc-pregunta' }, '¿Qué quieres crear?'),
      el('div', { clase: 'gc-ques' }, ...QUE_CREAR.map(q =>
        el('button', { type: 'button', clase: `gc-que gc-que-${q.id}`, 'data-que': q.id, onclick: () => elegir(q) },
          el('span', { clase: `gc-que-dibujo gc-dibujo-${q.id}`, 'aria-hidden': 'true' }),
          el('b', {}, q.nombre), el('span', {}, q.detalle)))),
      el('p', { clase: 'ce-pista gc-que-pista' }, 'Con los colores, la letra y el logo del Kit de este proyecto. Gratis.'),
      el('div', { clase: 'gc-avanzado' }, el('span', { clase: 'ce-pista' }, 'Avanzado:'),
        avanzado('lote', 'lote-en-capas', 'Varios carruseles de una vez (pegando una lista)', 'Para hacer muchos a la vez: pegas sus textos separados por ---, o un CSV de Excel (sin IA, gratis)'),
        avanzado('enBlanco', 'nueva-en-capas', 'Empezar en blanco', 'Un diseño libre: textos, fotos, logo y formas donde quieras'),
        avanzado('clasico', 'nueva-grafica', 'Editor clásico de una imagen', 'El editor de siempre, con sus 16 plantillas'))));
    const primera = caja.querySelector('.gc-que');
    if (primera) primera.focus();
  }

  /* ---------------------------------------------------------------- paso 2 */

  function pasoTema(S, caja) {
    const q = QUE_CREAR.find(x => x.id === S.que);
    const cuerpo = el('div', { clase: 'gc-cuerpo gc-dos' });
    const izq = el('div', { clase: 'gc-col' });
    const der = el('div', { clase: 'gc-col' });
    cuerpo.append(izq, der);
    caja.appendChild(cuerpo);
    // el tamaño, en pequeño y se puede cambiar
    const tam = el('select', { 'aria-label': 'Tamaño', clase: 'gc-tamano' },
      ...S.opc.catalogo.formatos.map(f => el('option', { value: f.id }, `${f.nombre} · ${f.W}×${f.H}`)));
    tam.value = S.formato;
    tam.addEventListener('change', () => { S.formato = tam.value; pedirEstilos(S, true); });
    izq.appendChild(el('h3', { clase: 'gc-pregunta' }, `${q.nombre}: ¿de qué trata?`));
    S.cajaTextos = el('div', { clase: 'gc-textos' });
    izq.appendChild(S.cajaTextos);
    pintarTextos(S);
    izq.appendChild(campoNegocio(S));
    izq.appendChild(el('label', { clase: 'ce-campo gc-campo-tamano' }, el('span', {}, 'Tamaño'), tam));
    S.cajaFoto = el('section', { clase: 'gc-foto' });
    izq.appendChild(S.cajaFoto);
    pintarFoto(S);
    S.cajaEstilos = el('section', { clase: 'gc-estilos-caja' });
    der.appendChild(S.cajaEstilos);
    S.bCrear = el('button', { type: 'button', clase: 'ce-btn ce-primario gc-crear', onclick: () => crearYa(S) }, 'Crear');
    S.pistaCrear = el('span', { clase: 'ce-pista gc-pista-crear', role: 'status' });
    S.bAtras = el('button', { type: 'button', clase: 'ce-btn gc-atras', disabled: S.escribiendo, onclick: () => { S.paso = 1; S.turno += 1; clearTimeout(S.espera); if (S.parar) S.parar.abort(); pintarAsistente(S); } }, '← Atrás');
    caja.appendChild(el('footer', { clase: 'gc-pie' },
      S.bAtras,
      el('span', { clase: 'ce-crece' }), S.pistaCrear, S.bCrear));
    pedirEstilos(S, true);
    revisarCrear(S);
    const primero = S.cajaTextos.querySelector('input, textarea');
    if (primero) primero.focus();
  }

  /* «Sobre tu negocio»: qué vendes y cómo hablas, para «Escríbelo por mí».
   * La ficha del proyecto solo trae su nombre y las reglas de imagen; esto se
   * recuerda en el navegador por proyecto (no toca ningún vídeo ni param). */
  const claveNegocio = cid => `crearia.graficas.negocio.${cid}`;

  function negocioRecordado(cid) {
    try { return localStorage.getItem(claveNegocio(cid)) || ''; } catch (_) { return ''; }
  }

  function campoNegocio(S) {
    if (S.sobre === undefined) S.sobre = negocioRecordado(S.cid);
    const area = el('textarea', { rows: '3', maxlength: '600', clase: 'gc-sobre', 'aria-label': 'Sobre tu negocio',
      placeholder: 'Ej.: alquilamos consolas con juegos para fiestas y eventos en Lima; te la llevamos e instalamos. Hablamos cercano y con humor.' });
    area.value = S.sobre;
    area.addEventListener('input', () => {
      S.sobre = area.value.slice(0, 600);
      try { localStorage.setItem(claveNegocio(S.cid), S.sobre); } catch (_) { /* vale para esta vez */ }
    });
    return el('details', { clase: 'gc-negocio', open: !S.sobre },
      el('summary', {}, S.sobre ? 'Sobre tu negocio ✓ (para la IA)' : 'Sobre tu negocio (para que la IA escriba mejor)'),
      area,
      el('small', { clase: 'ce-pista' }, 'Qué vendes, dónde y cómo hablas. Los precios o cifras que pongas aquí la IA los puede usar; los que no, nunca. Se recuerda en este navegador.'));
  }

  /** El titular con el que se pintan las miniaturas. */
  function tituloDeMuestra(S) {
    if (S.que !== 'carrusel') return S.titulo;
    if (S.modo === 'tema') return S.piezas ? String((S.piezas[0][1] || {}).titulo || '') : S.tema;
    return (S.texto.trim().split('\n')[0] || '').slice(0, 90);
  }

  function apoyoDeMuestra(S) {
    if (S.que !== 'carrusel') return S.apoyo;
    return S.modo === 'tema' && S.piezas ? String((S.piezas[0][1] || {}).apoyo || '') : '';
  }

  function campoTexto(etiqueta, valor, props, alCambiar) {
    const entrada = el(props.filas ? 'textarea' : 'input', Object.assign({ type: props.filas ? null : 'text', 'aria-label': etiqueta }, props.attrs));
    if (props.filas) entrada.rows = props.filas;
    entrada.value = valor;
    entrada.addEventListener('input', () => alCambiar(entrada.value));
    return el('label', { clase: 'ce-campo gc-campo' }, el('span', {}, etiqueta), entrada);
  }

  function pintarTextos(S) {
    const C = S.cajaTextos;
    C.textContent = '';
    const cambioTitular = () => { S.mensaje = ''; revisarCrear(S); programarEstilos(S); };
    if (S.que !== 'carrusel') {
      C.appendChild(campoTexto('El titular', S.titulo, { attrs: { maxlength: '90', placeholder: EJEMPLO_TEMA, clase: 'gc-titular' } },
        v => { S.titulo = v; cambioTitular(); }));
      C.appendChild(campoTexto('Una frase de apoyo (si quieres)', S.apoyo, { attrs: { maxlength: '140', placeholder: 'Te contamos cómo evitarlos', clase: 'gc-apoyo' } },
        v => { S.apoyo = v; cambioTitular(); }));
      C.appendChild(botonEscribir(S, 'Escribe el tema arriba y la IA te propone el titular y la frase.'));
      return;
    }
    C.appendChild(el('div', { clase: 'ce-botonera gc-modo', role: 'group', 'aria-label': '¿Cómo quieres escribirlo?' },
      el('button', { type: 'button', clase: 'ce-mini gc-modo-tema', 'aria-pressed': String(S.modo === 'tema'),
        onclick: () => { S.modo = 'tema'; pintarTextos(S); revisarCrear(S); programarEstilos(S, true); } }, 'Te lo escribo desde un tema'),
      el('button', { type: 'button', clase: 'ce-mini gc-modo-texto', 'aria-pressed': String(S.modo === 'texto'),
        onclick: () => { S.modo = 'texto'; pintarTextos(S); revisarCrear(S); programarEstilos(S, true); } }, 'Ya tengo el texto')));
    if (S.modo === 'texto') {
      C.appendChild(campoTexto('Tu texto', S.texto, { filas: 9, attrs: { maxlength: '12000', clase: 'gc-texto',
        placeholder: `${EJEMPLO_TEMA}\n\nNo probar los mandos\nPruébalos todos antes de la fiesta.\n\nPedirla tarde\nReserva con una semana.` } },
      v => { S.texto = v; cambioTitular(); }));
      C.appendChild(el('small', { clase: 'ce-pista' }, 'Cada párrafo (separado por una línea en blanco) es una imagen; el primero es la portada y al final va el cierre. Sin IA.'));
      return;
    }
    C.appendChild(campoTexto('El tema, en una frase', S.tema, { attrs: { maxlength: '200', placeholder: EJEMPLO_TEMA, clase: 'gc-tema' } },
      v => { S.tema = v; S.mensaje = ''; revisarCrear(S); if (!S.piezas) programarEstilos(S); }));
    const cuantas = el('select', { 'aria-label': '¿Cuántas imágenes?', clase: 'gc-cuantas' },
      ...[3, 4, 5, 6, 7, 8, 9, 10].map(n => el('option', { value: String(n) }, `${n} imágenes`)));
    cuantas.value = String(S.cuantas);
    cuantas.addEventListener('change', () => { S.cuantas = parseInt(cuantas.value, 10); });
    C.appendChild(el('label', { clase: 'ce-campo gc-campo' }, el('span', {}, '¿Cuántas imágenes?'), cuantas));
    C.appendChild(botonEscribir(S, ''));
    if (S.piezas) {
      const nombres = {};
      for (const t of S.tipos || []) nombres[t.id] = t.nombre;
      C.appendChild(el('div', { clase: 'gc-propuesta' },
        el('b', {}, `Textos listos: ${S.piezas.length} imágenes`),
        S.piezasDe !== S.tema.trim() ? el('small', { clase: 'ce-pista' }, `Escritos para «${S.piezasDe}». Pulsa «Escríbelo por mí» otra vez si cambiaste el tema.`) : null,
        el('ol', {}, ...S.piezas.map(([tipo, t]) => el('li', {}, el('i', {}, nombres[tipo] || tipo), ' · ',
          String(t.titulo || t.pregunta || t.mito || t.cifra || '').slice(0, 70)))),
        el('small', { clase: 'ce-pista' }, 'Los cambias en el paso siguiente, tocando cada texto.')));
    }
  }

  function botonEscribir(S, pista) {
    const b = el('button', { type: 'button', clase: 'ce-btn gc-escribir', disabled: S.escribiendo,
      title: 'Claude escribe los textos con la ficha de tu negocio (usa el cupo de tu membresía, no cuesta dinero)',
      onclick: () => escribirPorMi(S) }, S.escribiendo ? 'Escribiendo…' : '✍️ Escríbelo por mí');
    const avisos = S.avisosIA.length ? el('ul', { clase: 'gc-avisos' }, ...S.avisosIA.map(a => el('li', {}, a))) : null;
    return el('div', { clase: 'gc-escribir-fila' }, b,
      el('small', { clase: 'ce-pista' }, S.escribiendo ? 'Tarda entre 20 segundos y un minuto. Puedes ir eligiendo la foto.' : (pista || 'Sin dinero: usa el cupo de Claude de tu membresía.')),
      avisos);
  }

  async function escribirPorMi(S) {
    const tema = (S.que === 'carrusel' ? S.tema : S.titulo).trim();
    if (tema.length < 3) {
      const campo = S.cajaTextos.querySelector(S.que === 'carrusel' ? '.gc-tema' : '.gc-titular');
      decir(S, 'Escribe de qué trata (una frase basta) y vuelve a pulsar.');
      if (campo) campo.focus();
      return;
    }
    if (S.que !== 'carrusel' && (S.apoyo.trim()) && !window.confirm('La IA va a cambiar el titular y la frase que has escrito. ¿Seguir?')) return;
    const pedido = S.que;
    S.escribiendo = true;
    S.avisosIA = [];
    pintarTextos(S);
    revisarCrear(S);
    const o = S.opc;
    try {
      const inicio = await o.pedir(o.api(S.cid, '/escribir'), { method: 'POST', cuerpo: { que: S.que, tema, cuantas: S.cuantas, formato: S.formato, sobre: S.sobre || '' } });
      let r = null;
      // el servidor da hasta 2 intentos de 4 minutos: se espera un poco más
      for (let i = 0; i < 450 && !S.cerrado; i++) {
        await new Promise(ok => setTimeout(ok, 1200));
        let t;
        try {
          t = await o.pedir(o.api(S.cid, `/capas/trabajo/${inicio.trabajo}`));
        } catch (e) {
          if (e.status === 404) throw new Error('se ha perdido (¿se reinició el servicio?). Vuelve a pulsar «Escríbelo por mí»');
          continue;                                       // un corte de red: se vuelve a preguntar
        }
        if (t.estado === 'listo') { r = t.resultado; break; }
        if (t.estado === 'error') throw new Error(t.error || 'no se ha podido escribir');
      }
      if (S.cerrado) return;
      if (!r) throw new Error('tarda demasiado. Vuelve a probar en un rato o escríbelo tú');
      if (S.que !== pedido) throw new Error('cambiaste lo que vas a crear mientras escribía. Vuelve a pulsar «Escríbelo por mí»');
      const piezas = (r.piezas || []).filter(p => Array.isArray(p) && p.length === 2);
      if (!piezas.length) throw new Error('no ha devuelto textos');
      S.avisosIA = r.avisos || [];
      if (S.que === 'carrusel') {
        S.piezas = piezas;
        S.piezasDe = tema;
      } else {
        S.titulo = String(piezas[0][1].titulo || S.titulo).slice(0, 90);
        S.apoyo = String(piezas[0][1].apoyo || '').slice(0, 140);
      }
      decir(S, 'Textos escritos: revísalos antes de publicar.');
    } catch (e) {
      if (!S.cerrado) decir(S, `No se ha podido escribir: ${e.message}. Lo que escribiste sigue aquí.`);
    } finally {
      S.escribiendo = false;
      if (!S.cerrado) { pintarTextos(S); revisarCrear(S); programarEstilos(S, true); }
    }
  }

  /* la foto: subir o una de mis vídeos */

  async function fotoComoDataUrl(S, nombre) {
    const pases = S.opc.pases ? S.opc.pases() : '';
    const r = await fetch(S.opc.api(S.cid, `/imagen/${encodeURIComponent(nombre)}`), { headers: pases ? { 'X-Estudio-Abiertos': pases } : {} });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const blob = await r.blob();
    return new Promise((ok, mal) => { const l = new FileReader(); l.onload = () => ok(l.result); l.onerror = () => mal(l.error); l.readAsDataURL(blob); });
  }

  async function ponerFotoAsistente(S, nombre) {
    S.foto = nombre;
    S.fotoUrl = '';
    pintarFoto(S);
    try { S.fotoUrl = await fotoComoDataUrl(S, nombre); } catch (_) { S.fotoUrl = ''; }
    if (S.cerrado || S.foto !== nombre) return;
    pintarFoto(S);
    pedirEstilos(S, true);
  }

  function pintarFoto(S) {
    const C = S.cajaFoto;
    if (!C) return;
    C.textContent = '';
    const o = S.opc;
    C.appendChild(el('h3', {}, 'La imagen (si quieres)'));
    if (S.foto) {
      C.appendChild(el('div', { clase: 'gc-foto-elegida' },
        S.fotoUrl ? el('img', { src: S.fotoUrl, alt: 'Tu foto' }) : el('span', { clase: 'ce-pista' }, 'Cargando la foto…'),
        el('button', { type: 'button', clase: 'ce-btn gc-quitar-foto', onclick: () => { S.foto = ''; S.fotoUrl = ''; pintarFoto(S); pedirEstilos(S, true); } }, 'Quitar la foto')));
    }
    const sube = el('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp', clase: 'ce-oculto', id: 'gc-subir-foto',
      onchange: async ev => {
        const f = ev.target.files[0];
        ev.target.value = '';
        if (!f) return;
        S.subiendo = true;
        decir(S, 'Subiendo la foto…');
        try {
          const cuerpo = new FormData();
          cuerpo.append('imagen', f);
          const r = await o.pedir(o.api(S.cid, '/imagen'), { method: 'POST', cuerpo });
          if (S.cerrado) return;
          decir(S, '');
          await ponerFotoAsistente(S, r.nombre);
        } catch (e) {
          if (!S.cerrado) decir(S, `No se ha podido subir la foto: ${e.message}`);
        } finally { S.subiendo = false; if (!S.cerrado) revisarCrear(S); }
      } });
    C.appendChild(el('div', { clase: 'ce-botonera' }, sube,
      el('label', { clase: 'ce-btn gc-subir', for: 'gc-subir-foto', tabindex: '0',
        onkeydown: ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); sube.click(); } } }, S.foto ? 'Subir otra foto' : 'Subir una foto')));
    const videos = typeof o.videos === 'function' ? o.videos() : [];
    if (videos.length) {
      const rejilla = el('div', { clase: 'ce-planos gc-planos', 'aria-live': 'polite' });
      const sel = el('select', { 'aria-label': 'De qué vídeo', clase: 'gc-video' }, ...videos.map(v => el('option', { value: v.id }, v.nombre || v.id)));
      sel.value = S.video || videos[0].id;
      const verPlanos = async (todos) => {
        const pid = sel.value;
        S.video = pid;
        rejilla.replaceChildren(el('span', { clase: 'ce-pista' }, 'Buscando sus imágenes…'));
        let planos;
        try { planos = await o.planos(pid); } catch (e) { rejilla.replaceChildren(el('span', { clase: 'ce-pista malo' }, `No se han podido leer: ${e.message}`)); return; }
        if (S.cerrado || sel.value !== pid) return;
        rejilla.textContent = '';
        if (!planos.length) { rejilla.appendChild(el('span', { clase: 'ce-pista' }, 'Este vídeo aún no tiene imágenes.')); return; }
        for (const pl of (todos ? planos : planos.slice(0, 8))) {
          const img = el('img', { alt: pl.texto || 'Plano' });
          o.miniatura(img, pid, pl.sid);
          rejilla.appendChild(el('button', { type: 'button', clase: 'ce-plano gc-plano', title: pl.texto || '', onclick: async () => {
            decir(S, 'Copiando la imagen del vídeo…');
            try {
              const r = await o.pedir(o.api(S.cid, '/imagen/de-plano'), { method: 'POST', cuerpo: { pid, sid: pl.sid } });
              if (S.cerrado) return;
              decir(S, '');
              await ponerFotoAsistente(S, r.nombre);
            } catch (e) { if (!S.cerrado) decir(S, `No se ha podido usar esa imagen: ${e.message}`); }
          } }, img));
        }
        if (!todos && planos.length > 8) {
          rejilla.appendChild(el('button', { type: 'button', clase: 'ce-btn gc-ver-mas', onclick: () => verPlanos(true) }, `Ver las ${planos.length}`));
        }
      };
      sel.addEventListener('change', () => verPlanos(false));
      C.appendChild(el('div', { clase: 'gc-de-videos' },
        el('b', {}, 'O una de tus vídeos'), el('small', { clase: 'ce-pista' }, ' (ya pagada: gratis)'),
        videos.length > 1 ? sel : null, rejilla));
      verPlanos(false);
    }
    C.appendChild(el('small', { clase: 'ce-pista gc-pronto' }, 'Pronto: crear la imagen con IA.'));
  }

  /* el estilo, con miniaturas reales */

  /** Repinta las miniaturas tras 1,5 s sin escribir (o al momento con `ya`). */
  function programarEstilos(S, ya) {
    clearTimeout(S.espera);
    if (ya) { pedirEstilos(S, true); return; }
    if (S.cajaEstilos) {
      const ver = S.cajaEstilos.querySelector('.gc-ver-titular');
      if (ver) ver.hidden = false;
    }
    S.espera = setTimeout(() => pedirEstilos(S, true), 1500);
  }

  function pintarEstilos(S) {
    const C = S.cajaEstilos;
    if (!C) return;
    C.textContent = '';
    const hechas = Object.keys(S.minis).length;
    const orden = S.orden.length ? S.orden : S.familias.map(f => f.n);
    const nombre = n => (S.familias.find(f => f.n === n) || {}).nombre || `Estilo ${n}`;
    C.appendChild(el('div', { clase: 'gc-estilos-cab' },
      el('h3', {}, 'El estilo'),
      el('span', { clase: 'ce-pista', role: 'status' }, S.falloMinis ? `No se han podido pintar: ${S.falloMinis}` : (hechas < orden.length ? `Pintando con tu titular (${hechas} de ${orden.length})…` : 'Con tu titular, tu foto y tus colores.')),
      el('button', { type: 'button', clase: 'ce-mini gc-ver-titular', hidden: true, onclick: () => programarEstilos(S, true) }, 'Ver con mi titular')));
    C.appendChild(el('div', { clase: 'gc-estilos' }, ...orden.map(n => {
      const m = S.minis[n];
      return el('button', { type: 'button', clase: 'gc-estilo', 'data-n': String(n), 'aria-pressed': String(n === S.familia),
        onclick: () => { S.familia = n; S.elegidaAMano = true; pintarEstilos(S); revisarCrear(S); } },
      el('span', { clase: 'gc-estilo-img' }, m ? el('img', { src: m.jpg, alt: `Estilo ${nombre(n)}` }) : el('span', { clase: 'gc-estilo-espera' }, '…')),
      el('span', { clase: 'gc-estilo-nombre' }, nombre(n)), marcaFoto(n));
    })));
    if (S.foto && conFotoConocidos.length && S.familia && !conFotoConocidos.includes(S.familia)) {
      C.appendChild(el('p', { clase: 'ce-pista malo gc-sin-hueco' }, 'El estilo elegido no lleva foto: tu foto no saldrá. Elige uno marcado «📷 con foto».'));
    }
  }

  async function pedirEstilos(S) {
    if (S.cerrado || !S.cajaEstilos) return;
    clearTimeout(S.espera);
    if (S.parar) S.parar.abort();
    const parar = new AbortController();
    S.parar = parar;
    const turno = ++S.turno;
    S.minis = {};
    S.falloMinis = '';
    pintarEstilos(S);
    const cuerpo = { que: S.que, formato: S.formato, titulo: tituloDeMuestra(S).trim(), apoyo: apoyoDeMuestra(S).trim(), foto: S.foto };
    const sigue = () => !S.cerrado && turno === S.turno;
    try {
      await pedirMiniaturas(S.opc, S.cid, cuerpo, S.familias.map(f => f.n), (m, orden) => {
        S.minis[m.n] = m;
        S.orden = orden;
        // sin elegir a mano, el primero del orden (con foto, uno que la lleva)
        if (!S.elegidaAMano || !orden.includes(S.familia)) S.familia = orden[0];
        pintarEstilos(S);
        revisarCrear(S);
      }, sigue, parar.signal);
    } catch (e) {
      if (sigue() && e.name !== 'AbortError') { S.falloMinis = e.message; pintarEstilos(S); }
    }
  }

  /* crear */

  function faltaParaCrear(S) {
    if (S.escribiendo) return 'Esperando a la IA…';
    if (S.subiendo) return 'Subiendo la foto…';
    if (!S.familia) return 'Elige un estilo.';
    if (S.que !== 'carrusel') return S.titulo.trim() ? '' : 'Escribe el titular (o el tema y «Escríbelo por mí»).';
    if (S.modo === 'tema') return S.piezas ? '' : 'Escribe el tema y pulsa «Escríbelo por mí» (o «Ya tengo el texto»).';
    return S.texto.trim() ? '' : 'Pega o escribe tu texto.';
  }

  /** Un mensaje junto a «Crear» (un fallo, «textos escritos»…); se va al escribir. */
  function decir(S, texto) {
    S.mensaje = texto || '';
    revisarCrear(S);
  }

  function revisarCrear(S) {
    if (!S.bCrear) return;
    const falta = faltaParaCrear(S);
    S.bCrear.disabled = !!falta || S.creando;
    if (S.bAtras) S.bAtras.disabled = S.escribiendo || S.creando;
    S.pistaCrear.textContent = S.creando ? 'Creando…' : (S.mensaje || falta);
  }

  async function crearYa(S) {
    if (faltaParaCrear(S) || S.creando) return;
    S.creando = true;
    revisarCrear(S);
    const cuerpo = { que: S.que, familia: S.familia, formato: S.formato, foto: S.foto };
    if (S.que !== 'carrusel') cuerpo.piezas = [['portada', { titulo: S.titulo.trim(), apoyo: S.apoyo.trim() }]];
    else if (S.modo === 'tema') cuerpo.piezas = S.piezas;
    else cuerpo.texto = S.texto;
    let r;
    try {
      r = await S.opc.pedir(S.opc.api(S.cid, '/capas/crear'), { method: 'POST', cuerpo });
    } catch (e) {
      S.creando = false;
      if (!S.cerrado) { revisarCrear(S); decir(S, `No se ha podido crear: ${e.message}`); }
      return;
    }
    if (S.cerrado) return;
    const avisos = (r.avisos || []).concat(S.avisosIA || []);
    // lo elegido, para «← Cambiar tema, foto o estilo»
    const desdeCrear = {};
    for (const k of ['que', 'formato', 'titulo', 'apoyo', 'tema', 'texto', 'modo', 'cuantas', 'piezas', 'piezasDe', 'avisosIA',
      'foto', 'fotoUrl', 'familia', 'elegidaAMano', 'sobre', 'video']) desdeCrear[k] = S[k];
    S.cerrar();
    await abrir(Object.assign({}, S.opc, {
      pieza: null, duplicar: false, docInicial: r.doc, sencillo: true, nueva: true, que: S.que, retomar: null, desdeCrear,
      avisoInicial: avisos.length ? avisos.join(' ') : '',
    }));
    if (ED && !avisos.length) avisoPantalla('¡Listo! Toca un texto para cambiarlo y pulsa «Guardar».');
  }


  window.EditorCapas = {
    abrir, crear, version: 1, _estado: () => ED, _asistente: () => ASISTENTE,
    // para pasos/prueba_graficas_editor.py: que la pantalla haga las mismas cuentas que el servidor
    _cuentas: { fueraDeLamina, textoDeLamina, fondoTapado, avisoFondoATodas, nombrarLaminas, f6, luz, tintaPara, coloresFinales, resolver, cssColor, cssRelleno, cssBorde, cssRadio, cssSombras, cssCaja,
      LIMITES, CAMPOS_DE_MUESTRA },
  };
}());

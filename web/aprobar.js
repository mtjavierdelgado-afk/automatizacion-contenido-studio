/* LA PÁGINA DEL MÓVIL DEL PILOTO AUTOMÁTICO (rama piloto-2, 24-11-2026).
 *
 * Se abre desde el aviso de Telegram: aprobar.html?video=<id del piloto>.
 * Todo se lee en vivo de /api/aprobar/<id> (la misma fuente que la Parrilla y
 * el Studio): nada se guarda aquí. Cada botón manda el `rev` que vio; si el
 * vídeo cambió en otro sitio, el servidor dice 409 y aquí sale «Esto se cambió
 * en otro sitio hace un momento».
 *
 * Sin dependencias y sin atributos style="" (la CSP del proxy los bloquea).
 */
'use strict';

const BASE = location.pathname.replace(/\/[^/]*$/, '').replace(/\/$/, '');
const VIDEO = new URLSearchParams(location.search).get('video') || '';
const CLAVE_PASES = 'estudio.aprobar.pases';
const CADA_MS = 15000;

const AP = {
  datos: null,        // lo último que dijo el servidor
  editando: {},       // red -> true mientras hay cambios sin guardar
  borrador: {},       // red -> {titulo, descripcion, hashtags} sin guardar
  cambioFuera: false, // el servidor trae algo distinto de lo que se editaba
  ocupado: false,
  mensaje: '', mensajeTipo: '',
  fechaAbierta: false,
  portadaEditor: null, // {diseno, vista}
  vidiq: null,
  temporizador: null,
};

// ------------------------------------------------------------------ útiles

function h(etiqueta, props, ...hijos) {
  const n = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'clase') n.className = v;
    else if (k === 'texto') n.textContent = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (k === 'valor') n.value = v;
    else n.setAttribute(k, v === true ? '' : v);
  }
  for (const hijo of hijos.flat()) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    n.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return n;
}

function pases() {
  try { return JSON.parse(localStorage.getItem(CLAVE_PASES) || '{}') || {}; } catch (e) { return {}; }
}

function cabeceraPases() {
  const ahora = Date.now();
  return Object.entries(pases())
    .filter(([, p]) => p && p.pase && (!p.hasta || p.hasta > ahora))
    .map(([cid, p]) => `${cid}.${p.pase}`).join(',');
}

async function pedir(ruta, opciones) {
  const o = opciones || {};
  const cab = { 'Accept': 'application/json' };
  const abiertos = cabeceraPases();
  if (abiertos) cab['x-estudio-abiertos'] = abiertos;
  let cuerpo;
  if (o.cuerpo !== undefined) { cab['Content-Type'] = 'application/json'; cuerpo = JSON.stringify(o.cuerpo); }
  const r = await fetch(`${BASE}${ruta}`, { method: o.method || 'GET', headers: cab, body: cuerpo,
    credentials: 'same-origin' });
  if (o.binario && r.ok) return r.blob();
  let datos = {};
  try { datos = await r.json(); } catch (e) { datos = {}; }
  if (!r.ok) {
    const fallo = new Error(datos.error || datos.detail || `error ${r.status}`);
    fallo.codigo = r.status;
    fallo.datos = datos;
    throw fallo;
  }
  return datos;
}

function decir(texto, tipo) {
  AP.mensaje = texto || '';
  AP.mensajeTipo = tipo || '';
  pintar();
}

function nombreRed(red) {
  return ((AP.datos || {}).nombres_red || {})[red] || red;
}

function esperar(ms) { return new Promise(r => setTimeout(r, ms)); }

// ------------------------------------------------------------------ cargar

async function cargar(silencioso) {
  if (!VIDEO) { pintarFallo('Este enlace no dice qué vídeo abrir.'); return; }
  try {
    const nuevo = await pedir(`/api/aprobar/${encodeURIComponent(VIDEO)}`);
    // LO QUE SE ESCRIBE NO SE PISA: si el servidor trae otros textos para una
    // red que se está editando, se avisa en vez de cambiarlos
    if (AP.datos && Object.keys(AP.editando).some(r => AP.editando[r])) {
      const viejos = ((AP.datos.publicar || {}).antes) || {};
      const nuevos = ((nuevo.publicar || {}).antes) || {};
      if (Object.keys(AP.editando).some(r => AP.editando[r] && viejos[r] !== nuevos[r])) {
        AP.cambioFuera = true;
        AP.pendiente = nuevo;
        pintar();
        return;
      }
      nuevo.publicar = nuevo.publicar ? Object.assign({}, nuevo.publicar, { antes: viejos }) : nuevo.publicar;
    }
    AP.datos = nuevo;
    pintar();
  } catch (fallo) {
    if (fallo.codigo === 423 && fallo.datos && fallo.datos.cid) {
      pintarClave(fallo.datos);
      return;
    }
    if (!silencioso || !AP.datos) pintarFallo(fallo.message);
  }
}

function programar() {
  clearTimeout(AP.temporizador);
  AP.temporizador = setTimeout(async () => {
    if (!document.hidden && !AP.ocupado) await cargar(true);
    programar();
  }, CADA_MS);
}

document.addEventListener('visibilitychange', () => { if (!document.hidden && !AP.ocupado) cargar(true); });

// ------------------------------------------------------------------ pantallas sueltas

function raiz() { return document.getElementById('ap'); }

function pintarFallo(texto) {
  raiz().replaceChildren(
    h('div', { clase: 'ap-estado mal', role: 'alert', texto: texto || 'No se pudo abrir el vídeo.' }),
    h('p', { clase: 'ap-sub', texto: 'Si el vídeo se quitó del piloto, ya no hay nada que aprobar aquí.' }),
    h('p', { clase: 'ap-pie' }, h('a', { href: `${BASE}/`, texto: 'Abrir el Studio' })));
}

function pintarClave(info) {
  const campo = h('input', { type: 'password', autocomplete: 'current-password', id: 'ap-clave' });
  const aviso = h('p', { clase: 'ap-mensaje' });
  const abrir = async (ev) => {
    ev.preventDefault();
    try {
      const r = await pedir(`/api/clientes/${encodeURIComponent(info.cid)}/abrir`,
        { method: 'POST', cuerpo: { clave: campo.value } });
      const todos = pases();
      // comodidad del navegador: este móvil no la vuelve a pedir en 12 h. El
      // pase del servidor no caduca (igual que en el Studio): «Cerrar» lo olvida
      todos[info.cid] = { pase: r.pase, hasta: Date.now() + 12 * 3600 * 1000 };
      try { localStorage.setItem(CLAVE_PASES, JSON.stringify(todos)); } catch (e) { /* sin almacén */ }
      cargar();
    } catch (fallo) {
      aviso.textContent = fallo.message;
      aviso.className = 'ap-mensaje mal';
    }
  };
  raiz().replaceChildren(
    h('h1', { texto: `🔒 ${info.proyecto || 'Proyecto con clave'}` }),
    h('p', { clase: 'ap-sub', texto: 'Este vídeo es de un proyecto con clave. Escríbela para verlo.' }),
    h('form', { onsubmit: abrir },
      h('label', { clase: 'ap-campo', for: 'ap-clave' }, h('span', { texto: 'Clave del proyecto' })),
      campo, h('div', { clase: 'ap-fila' }, h('button', { clase: 'principal', type: 'submit', texto: 'Abrir' }))),
    aviso);
}

// ------------------------------------------------------------------ la página

function claseDeEstado(clave) {
  if (['programado', 'publicado'].includes(clave)) return 'bien';
  if (['fallo', 'detenido', 'comprobar'].includes(clave)) return 'mal';
  if (['espera_ok', 'cambiando', 'retirando'].includes(clave)) return 'aviso';
  return '';
}

function pintar() {
  const d = AP.datos;
  if (!d) return;
  const partes = [];
  if (AP.cambioFuera) {
    partes.push(h('div', { clase: 'ap-banda', role: 'alert' },
      h('p', { texto: 'Esto se cambió en otro sitio hace un momento.' }),
      h('div', { clase: 'ap-fila' },
        h('button', { texto: 'Ver lo nuevo', onclick: verLoNuevo }),
        h('button', { texto: 'Guardar lo mío igualmente', onclick: guardarLoMio }))));
  }
  partes.push(h('h1', { texto: d.titulo }));
  partes.push(h('p', { clase: 'ap-sub', texto: [d.proyecto, d.modo === 3 ? 'nivel 3' : 'nivel 2'].filter(Boolean).join(' · ') }));
  const clave = (d.vivo || {}).clave;
  let estado = (d.vivo || {}).texto || '';
  if (clave === 'programado' || clave === 'publicado') estado = `Ya está aprobado: ${estado.replace(/^[^ ]+ /, '')}`;
  partes.push(h('div', { clase: `ap-estado ${claseDeEstado(clave)}`, role: 'status', texto: estado }));
  if (d.video) {
    partes.push(h('div', { clase: 'ap-bloque' },
      h('video', { clase: 'ap-video', src: `${BASE}/${d.video}`, controls: true, playsinline: true, preload: 'metadata' })));
  } else if (!d.terminado) {
    partes.push(h('p', { clase: 'ap-sub', texto: d.mensaje || 'El vídeo todavía se está haciendo.' }));
  }
  partes.push(bloqueRazones(d));
  partes.push(bloqueComprobar(d));
  partes.push(bloqueFallidas(d));
  if (d.editable) {
    partes.push(bloqueTextos(d));
    partes.push(bloquePortadas(d));
  }
  partes.push(bloqueFecha(d));
  partes.push(h('p', { clase: `ap-mensaje ${AP.mensajeTipo}`, role: 'status', texto: AP.mensaje }));
  partes.push(h('p', { clase: 'ap-pie' },
    h('a', { href: d.pid ? `${BASE}/#publicar/${encodeURIComponent(d.pid)}` : `${BASE}/`, texto: 'Abrir en el Studio' }),
    Object.keys(pases()).length ? ' · ' : '',
    Object.keys(pases()).length ? h('a', { href: '#', onclick: cerrarPases, texto: '🔒 Cerrar' }) : ''));
  partes.push(barra(d));
  raiz().replaceChildren(...partes.filter(Boolean));
}

function bloqueRazones(d) {
  if (!(d.razones || []).length) return null;
  return h('section', { clase: 'ap-bloque' },
    h('h2', { texto: d.modo === 3 ? 'Por qué no lo publiqué solo' : 'Antes de aprobarlo, mira esto' }),
    h('ul', { clase: 'ap-razones' }, d.razones.map(r =>
      h('li', {}, r.texto, r.que_hacer ? h('small', { texto: r.que_hacer }) : null))));
}

function bloqueComprobar(d) {
  if (!(d.comprobar || []).length) return null;
  return h('section', { clase: 'ap-bloque' },
    h('h2', { texto: '⚠ No sé si salió' }),
    h('p', { texto: 'La subida se cortó a medias en: ' + d.comprobar.map(c => `${nombreRed(c.red)} (${c.texto})`).join(', ')
      + '. Entra en Upload-Post, busca esa publicación y, si está y no quieres que salga, cancélala allí.' }),
    h('div', { clase: 'ap-fila' }, h('button', { texto: 'Ya lo miré', onclick: yaLoMire, disabled: AP.ocupado })));
}

function bloqueFallidas(d) {
  if (!(d.fallidas || []).length) return null;
  return h('section', { clase: 'ap-bloque' },
    h('h2', { texto: '⚠ Falló la subida' }),
    h('p', { texto: 'Las demás redes siguen como estaban. Puedes volver a intentarlo solo en la que falló (sale en unos 15 minutos).' }),
    h('div', { clase: 'ap-fila' }, d.fallidas.map(red =>
      h('button', { texto: `Reintentar ${nombreRed(red)}`, disabled: AP.ocupado, onclick: () => reintentarRed(red) }))));
}

// ------------------------------------------------------------------ textos

function textoDe(red) {
  const pub = (AP.datos || {}).publicar || {};
  return AP.borrador[red] || Object.assign({}, (pub.textos || {})[red] || {});
}

function bloqueTextos(d) {
  const pub = d.publicar;
  if (!pub) return null;
  const redes = d.redes || [];
  return h('section', { clase: 'ap-bloque' },
    h('h2', { texto: 'Títulos y textos' }),
    pub.escribiendo ? h('p', { clase: 'ap-sub', texto: 'Claude está escribiendo los textos…' }) : null,
    redes.map(red => bloqueRed(red, pub)));
}

function bloqueRed(red, pub) {
  const t = textoDe(red);
  const formato = (pub.formato_redes || {})[red] || {};
  const encaje = (pub.encaje || {})[red] || {};
  const cambiar = (campo) => (ev) => {
    AP.borrador[red] = Object.assign(textoDe(red), { [campo]: ev.target.value });
    AP.editando[red] = true;
    const boton = document.getElementById(`ap-guardar-${red}`);
    if (boton) boton.disabled = false;
  };
  const opciones = (pub.titulos || {})[red] || [];
  const pensando = !!(pub.trabajando || {})[`titulos_${red}`];
  return h('details', { clase: 'ap-red', open: AP.editando[red] || opciones.length ? true : null },
    h('summary', { texto: nombreRed(red) + (encaje.nivel === 'error' ? ' ⚠' : '') }),
    encaje.nivel === 'error' ? h('p', { clase: 'ap-mensaje mal', texto: encaje.texto }) : null,
    formato.titulo ? h('label', { clase: 'ap-campo' }, h('span', { texto: 'Título' }),
      h('input', { type: 'text', maxlength: formato.titulo, valor: t.titulo || '', oninput: cambiar('titulo') })) : null,
    h('label', { clase: 'ap-campo' }, h('span', { texto: 'Descripción' }),
      h('textarea', { maxlength: formato.limite || null, oninput: cambiar('descripcion') }, t.descripcion || '')),
    h('label', { clase: 'ap-campo' }, h('span', { texto: 'Hashtags' }),
      h('input', { type: 'text', valor: Array.isArray(t.hashtags) ? t.hashtags.join(' ') : (t.hashtags || ''),
        oninput: cambiar('hashtags') })),
    h('div', { clase: 'ap-fila' },
      h('button', { id: `ap-guardar-${red}`, clase: 'principal', texto: 'Guardar', disabled: !AP.editando[red] || AP.ocupado,
        onclick: () => guardarTextos(red, false) }),
      ['youtube', 'facebook'].includes(red)
        ? h('button', { texto: pensando ? 'Pensando…' : '🎯 Dame 4 títulos', disabled: pensando || AP.ocupado,
          onclick: () => dameTitulos(red) }) : null,
      red === 'youtube' ? h('button', { texto: 'Mejorar con vidIQ', disabled: AP.ocupado, onclick: mejorarVidiq }) : null),
    opciones.length ? h('ul', { clase: 'ap-opciones' }, opciones.map((o, i) =>
      h('li', {}, h('span', { texto: o.titulo }), h('button', { texto: 'Usar', onclick: () => usarTitulo(red, i) })))) : null,
    red === 'youtube' && AP.vidiq ? bloqueVidiq() : null);
}

async function guardarTextos(red, sinAntes) {
  const pub = (AP.datos || {}).publicar || {};
  const t = textoDe(red);
  const cuerpo = { textos: { [red]: { descripcion: t.descripcion || '', hashtags: t.hashtags || '' } } };
  if (((pub.formato_redes || {})[red] || {}).titulo) cuerpo.textos[red].titulo = t.titulo || '';
  if (!sinAntes) cuerpo.antes = { [red]: (pub.antes || {})[red] || '' };
  await accion(async () => {
    await pedir(`/api/publicar/videos/${encodeURIComponent(AP.datos.pid)}`, { method: 'PUT', cuerpo });
    delete AP.borrador[red];
    delete AP.editando[red];
    AP.cambioFuera = false;
    AP.pendiente = null;
    await cargar(true);
    return `Guardado el texto de ${nombreRed(red)}.`;
  });
}

function verLoNuevo() {
  AP.borrador = {};
  AP.editando = {};
  AP.cambioFuera = false;
  if (AP.pendiente) { AP.datos = AP.pendiente; AP.pendiente = null; }
  pintar();
}

async function guardarLoMio() {
  const redes = Object.keys(AP.editando).filter(r => AP.editando[r]);
  for (const red of redes) await guardarTextos(red, true);
}

async function dameTitulos(red) {
  await accion(async () => {
    await pedir(`/api/publicar/videos/${encodeURIComponent(AP.datos.pid)}/titulos`, { method: 'POST', cuerpo: { red } });
    for (let i = 0; i < 40; i += 1) {
      await esperar(3000);
      await cargar(true);
      const pub = AP.datos.publicar || {};
      if (!(pub.trabajando || {})[`titulos_${red}`]) break;
    }
    return (((AP.datos.publicar || {}).titulos || {})[red] || []).length
      ? 'Elige un título con «Usar».' : 'Claude no ha devuelto títulos: inténtalo otra vez.';
  });
}

async function usarTitulo(red, indice) {
  await accion(async () => {
    await pedir(`/api/publicar/videos/${encodeURIComponent(AP.datos.pid)}/titulos/usar`,
      { method: 'POST', cuerpo: { red, indice } });
    delete AP.borrador[red];
    delete AP.editando[red];
    await cargar(true);
    return 'Título puesto.';
  });
}

async function mejorarVidiq() {
  let estado;
  try { estado = await pedir('/api/vidiq/estado'); } catch (fallo) { decir(fallo.message, 'mal'); return; }
  if (!estado.puesta) { decir('No hay clave de vidIQ: ponla en el Studio, en Configuración → vidIQ.', 'mal'); return; }
  const creditos = ((estado.creditos_aprox || {}).titulo) || 'algunos';
  const saldo = estado.saldo !== undefined && estado.saldo !== null ? ` Te quedan ${estado.saldo}.` : '';
  if (!confirm(`«Mejorar con vidIQ» gasta ${creditos} créditos de vidIQ.${saldo} ¿Seguir?`)) return;
  await accion(async () => {
    const pid = encodeURIComponent(AP.datos.pid);
    await pedir(`/api/vidiq/videos/${pid}/titulo`, { method: 'POST' });
    let v = null;
    for (let i = 0; i < 60; i += 1) {
      await esperar(3000);
      v = await pedir(`/api/vidiq/videos/${pid}`);
      if (!v.trabajando) break;
    }
    AP.vidiq = v;
    if (v && v.error) throw new Error(v.error);
    return 'vidIQ ha contestado: elige un título con «Usar».';
  });
}

function bloqueVidiq() {
  const r = (AP.vidiq || {}).resultado || {};
  const alternativas = r.alternativas || [];
  if (!alternativas.length) return null;
  return h('div', {},
    h('p', { clase: 'ap-sub', texto: `vidIQ${r.palabra ? ` · palabra clave «${r.palabra}»` : ''}` }),
    h('ul', { clase: 'ap-opciones' }, alternativas.map(a =>
      h('li', {}, h('span', { texto: a.titulo + (a.nota !== null && a.nota !== undefined ? ` (${a.nota})` : '') }),
        h('button', { texto: 'Usar', onclick: () => {
          AP.borrador.youtube = Object.assign(textoDe('youtube'), { titulo: a.titulo });
          AP.editando.youtube = true;
          guardarTextos('youtube', false);
        } })))));
}

// ------------------------------------------------------------------ portadas

function bloquePortadas(d) {
  const candidatas = d.portadas || [];
  const pid = encodeURIComponent(d.pid);
  const portada = ((d.publicar || {}).portada) || {};
  const editor = AP.portadaEditor;
  return h('section', { clase: 'ap-bloque' },
    h('h2', { texto: 'Portada' }),
    portada.imagen ? h('img', { clase: 'ap-vista', alt: 'La portada de ahora',
      src: `${BASE}/api/publicar/videos/${pid}/portada.jpg?r=${d.rev}` }) : null,
    candidatas.length ? h('div', { clase: 'ap-portadas' }, candidatas.map(c =>
      h('figure', { clase: `ap-portada${d.portada_puesta === c.id ? ' elegida' : ''}` },
        h('img', { alt: c.nombre || 'Portada propuesta', loading: 'lazy',
          src: `${BASE}/api/piloto/videos/${encodeURIComponent(d.id)}/portadas/${encodeURIComponent(c.id)}.png` }),
        h('figcaption', {}, d.portada_puesta === c.id ? '✓ Elegida'
          : h('button', { texto: 'Elegir', disabled: AP.ocupado, onclick: () => elegirPortada(c.id) }))))) : null,
    editor ? bloqueEditorPortada(editor) : h('div', { clase: 'ap-fila' },
      h('button', { texto: 'Cambiar su texto', disabled: AP.ocupado, onclick: abrirEditorPortada }),
      h('button', { texto: '✦ Hacer otra portada', disabled: AP.ocupado, onclick: otraPortada })),
    h('p', { clase: 'ap-pie' }, h('a', { href: `${BASE}/#publicar/${pid}`, texto: 'Abrir el editor completo' })));
}

async function elegirPortada(id) {
  await accion(async () => {
    await pedir(`/api/piloto/videos/${encodeURIComponent(AP.datos.id)}/portada`, { method: 'POST', cuerpo: { id } });
    await cargar(true);
    return 'Portada elegida.';
  });
}

async function abrirEditorPortada() {
  await accion(async () => {
    const r = await pedir(`/api/publicar/videos/${encodeURIComponent(AP.datos.pid)}/portada/diseno`);
    AP.portadaEditor = { diseno: r.diseno, vista: '' };
    await verPortada();
    return '';
  });
}

function bloqueEditorPortada(editor) {
  const textos = editor.diseno.textos || {};
  const usados = Object.keys(textos).filter(k => (textos[k] || '').trim() || k === 'titulo');
  return h('div', {},
    usados.map(k => h('label', { clase: 'ap-campo' }, h('span', { texto: NOMBRES_TEXTO[k] || k }),
      h('input', { type: 'text', maxlength: 80, valor: textos[k] || '', oninput: (ev) => {
        editor.diseno.textos[k] = ev.target.value;
        for (const el of editor.diseno.elementos || []) if (el.rol === k) el.texto = ev.target.value;
      } }))),
    editor.vista ? h('img', { clase: 'ap-vista', alt: 'Cómo queda', src: editor.vista }) : null,
    h('div', { clase: 'ap-fila' },
      h('button', { texto: 'Ver', disabled: AP.ocupado, onclick: () => accion(async () => { await verPortada(); return ''; }) }),
      h('button', { clase: 'principal', texto: 'Usar esta', disabled: AP.ocupado, onclick: usarPortada }),
      h('button', { texto: 'Cerrar', onclick: () => { AP.portadaEditor = null; pintar(); } })));
}

const NOMBRES_TEXTO = { titulo: 'Título', antetitulo: 'Texto pequeño de arriba', izquierda: 'Lado izquierdo',
  derecha: 'Lado derecho', numero: 'Número', etiqueta: 'Etiqueta', insignia: 'Insignia', pie: 'Texto de abajo' };

async function verPortada() {
  const ed = AP.portadaEditor;
  const blob = await pedir(`/api/publicar/videos/${encodeURIComponent(AP.datos.pid)}/portada/vista`,
    { method: 'POST', cuerpo: { diseno: ed.diseno, ancho: 360 }, binario: true });
  if (ed.vista) URL.revokeObjectURL(ed.vista);
  ed.vista = URL.createObjectURL(blob);
}

async function usarPortada() {
  await accion(async () => {
    await pedir(`/api/publicar/videos/${encodeURIComponent(AP.datos.pid)}/portada/usar`,
      { method: 'POST', cuerpo: { diseno: AP.portadaEditor.diseno } });
    AP.portadaEditor = null;
    await cargar(true);
    return 'Portada puesta.';
  });
}

async function otraPortada() {
  const pid = encodeURIComponent(AP.datos.pid);
  let diseno;
  let precio;
  try {
    diseno = (await pedir(`/api/publicar/videos/${pid}/portada/diseno`)).diseno;
    precio = await pedir(`/api/publicar/videos/${pid}/portada/ia`, { method: 'POST',
      cuerpo: { diseno, que: 'fondo', calidad: 'low' } });
  } catch (fallo) { decir(fallo.message, 'mal'); return; }
  const usd = Number(precio.precio || 0).toFixed(2);
  if (!confirm(`Una portada nueva: la IA dibuja otro fondo (tu texto se queda encima). Cuesta unos ${usd} $. ¿Hacerla?`)) return;
  await accion(async () => {
    const r = await pedir(`/api/publicar/videos/${pid}/portada/ia`, { method: 'POST',
      cuerpo: { diseno, que: 'fondo', calidad: 'low', confirmado: true } });
    for (let i = 0; i < 80; i += 1) {
      await esperar(3000);
      const t = await pedir(`/api/trabajos/${encodeURIComponent(r.trabajo_id)}`);
      const estado = t.estado || (t.trabajo || {}).estado;
      if (estado === 'error' || estado === 'cancelado') throw new Error(t.error || 'la portada no salió');
      if (estado === 'listo' || estado === 'hecho' || estado === 'completado') break;
    }
    const nuevo = await pedir(`/api/publicar/videos/${pid}/portada/diseno`);
    AP.portadaEditor = { diseno: nuevo.diseno, vista: '' };
    await verPortada();
    return 'Ya está el fondo nuevo: si te gusta, pulsa «Usar esta».';
  });
}

// ------------------------------------------------------------------ fecha y botones

function bloqueFecha(d) {
  const puede = ['preparando', 'espera_ok', 'programado', 'reprogramando'].includes(d.paso);
  if (!puede) return null;
  const libres = d.huecos_libres || [];
  const campo = h('input', { type: 'datetime-local', id: 'ap-fecha', step: 60, valor: d.hueco || '' });
  return h('section', { clase: 'ap-bloque' },
    h('h2', { texto: 'Fecha y hora' }),
    h('p', { texto: d.sin_hueco ? 'No queda ningún hueco libre en el calendario: elige tú la fecha.'
      : `Sale el ${d.hueco_texto} (hora de Lima).` }),
    AP.fechaAbierta ? h('div', {},
      libres.length ? h('p', { clase: 'ap-sub', texto: 'Los próximos huecos libres de tu calendario:' }) : null,
      h('div', { clase: 'ap-huecos' }, libres.map(l =>
        h('button', { texto: l.texto, onclick: () => { campo.value = l.cuando; } }))),
      h('label', { clase: 'ap-campo', for: 'ap-fecha' }, h('span', { texto: 'O cualquier otra fecha' })),
      campo,
      h('div', { clase: 'ap-fila' },
        h('button', { clase: 'principal', texto: 'OK', disabled: AP.ocupado, onclick: () => cambiarFecha(campo.value) }),
        h('button', { texto: 'Cancelar', onclick: () => { AP.fechaAbierta = false; pintar(); } }))) : null);
}

function barra(d) {
  const botones = [];
  const terminado = d.terminado;
  if (['preparando', 'espera_ok'].includes(d.paso) && terminado) {
    botones.push(h('button', { clase: 'principal', texto: '✓ Publicar así', disabled: AP.ocupado, onclick: publicar }));
  }
  if (['preparando', 'espera_ok', 'programado', 'reprogramando'].includes(d.paso) && !AP.fechaAbierta) {
    botones.push(h('button', { texto: 'Cambiar fecha', disabled: AP.ocupado,
      onclick: () => { AP.fechaAbierta = true; pintar(); const c = document.getElementById('ap-fecha'); if (c) c.scrollIntoView({ block: 'center' }); } }));
  }
  if (['preparando', 'espera_ok', 'programado', 'reprogramando', 'publicando', 'fallo'].includes(d.paso)
      && d.estado_piloto !== 'trabajando') {
    botones.push(h('button', { clase: 'peligro', texto: 'No publicar', disabled: AP.ocupado, onclick: noPublicar }));
  }
  if (!botones.length) return null;
  return h('div', { clase: 'ap-barra' }, h('div', { clase: 'ap-fila' }, botones));
}

async function accion(fn) {
  if (AP.ocupado) return;
  AP.ocupado = true;
  decir('Un momento…', '');
  try {
    const texto = await fn();
    AP.ocupado = false;
    decir(texto || '', 'bien');
  } catch (fallo) {
    AP.ocupado = false;
    if (fallo.codigo === 409 && /otro sitio/.test(fallo.message)) {
      await cargar(true);
      decir('Esto se cambió en otro sitio hace un momento: ya ves lo nuevo.', 'mal');
      return;
    }
    decir(fallo.message, 'mal');
  }
}

async function publicar() {
  if (Object.keys(AP.editando).some(r => AP.editando[r])) {
    if (!confirm('Tienes textos sin guardar. Si sigues, se publica con lo que estaba guardado. ¿Seguir?')) return;
  }
  if (!confirm(`Se publicará el ${AP.datos.hueco_texto} en ${AP.datos.redes.map(nombreRed).join(', ')}. ¿Publicar así?`)) return;
  await accion(async () => {
    AP.datos = await pedir(`/api/aprobar/${encodeURIComponent(VIDEO)}/publicar`,
      { method: 'POST', cuerpo: { rev: AP.datos.rev, desde: 'movil' } });
    return `Listo: ${AP.datos.vivo.texto}.`;
  });
}

async function cambiarFecha(valor) {
  if (!valor) { decir('Elige un día y una hora.', 'mal'); return; }
  await accion(async () => {
    AP.datos = await pedir(`/api/aprobar/${encodeURIComponent(VIDEO)}/fecha`,
      { method: 'POST', cuerpo: { rev: AP.datos.rev, cuando: valor.slice(0, 16) } });
    AP.fechaAbierta = false;
    return AP.datos.paso === 'reprogramando'
      ? 'Cambiando la fecha en Upload-Post: en un minuto queda programado a la hora nueva.'
      : `Nueva fecha: ${AP.datos.hueco_texto}.`;
  });
}

async function noPublicar() {
  if (!confirm('¿No publicar este vídeo? Si ya estaba programado, se cancela.')) return;
  const devolver = confirm('¿Devolver este vídeo del guion a la lista? El piloto lo volvería a hacer (y a pagar) más adelante.\n\nAceptar = devolverlo · Cancelar = no');
  await accion(async () => {
    const r = await pedir(`/api/aprobar/${encodeURIComponent(VIDEO)}/no-publicar`,
      { method: 'POST', cuerpo: { rev: AP.datos.rev, devolver } });
    if (r.quitado) { pintarFallo('No se publica, y el guion vuelve a la lista del piloto.'); AP.datos = null; return ''; }
    AP.datos = r;
    return r.paso === 'retirando' ? 'Quitándolo de Upload-Post…' : 'No se publica.';
  });
}

async function yaLoMire() {
  await accion(async () => {
    AP.datos = await pedir(`/api/aprobar/${encodeURIComponent(VIDEO)}/ya-lo-mire`,
      { method: 'POST', cuerpo: { rev: AP.datos.rev } });
    return 'Apuntado.';
  });
}

async function reintentarRed(red) {
  if (!confirm(`¿Volver a subirlo a ${nombreRed(red)}? Sale en unos 15 minutos.`)) return;
  await accion(async () => {
    AP.datos = await pedir(`/api/aprobar/${encodeURIComponent(VIDEO)}/reintentar-red`,
      { method: 'POST', cuerpo: { rev: AP.datos.rev, red, desde: 'movil' } });
    return `Reintentando ${nombreRed(red)}.`;
  });
}

function cerrarPases(ev) {
  ev.preventDefault();
  try { localStorage.removeItem(CLAVE_PASES); } catch (e) { /* sin almacén */ }
  location.reload();
}

cargar().then(programar);

/* El botón «Enviar al Studio».
 *
 * 1. Al abrirlo lee la pestaña activa con lector.js (permiso activeTab: solo
 *    esa pestaña y solo porque has pulsado el botón).
 * 2. Al pulsar «Enviar» hace una captura de lo que se ve y lo manda a
 *    `<tu Studio>/api/recibidos` con tu código de envío.
 * 3. Si la petición directa no lleva tu sesión del Studio (el login la manda a
 *    /login), se envía DESDE una pestaña del Studio que tengas abierta, que sí
 *    la lleva. Si no hay ninguna, te lo dice.
 *
 * La dirección y el código se guardan en chrome.storage.local, en este Chrome.
 */
const $ = id => document.getElementById(id);
let leido = null;

function estado(id, texto, tipo) {
  const el = $(id);
  el.textContent = texto || '';
  el.className = 'estado' + (tipo ? ' ' + tipo : '');
}

function normalizar(direccion) {
  let u;
  try { u = new URL(String(direccion || '').trim()); } catch (e) { return null; }
  if (!/^https?:$/.test(u.protocol)) return null;
  /* la dirección del Studio puede llevar una carpeta (/v2/): la API cuelga de ahí */
  let carpeta = u.pathname.replace(/\/[^/]*\.[a-z0-9]+$/i, '/');
  if (!carpeta.endsWith('/')) carpeta += '/';
  return { base: u.origin + carpeta, origen: u.origin, api: u.origin + carpeta + 'api/' };
}

async function config() {
  const c = await chrome.storage.local.get(['studio', 'codigo']);
  const n = normalizar(c.studio);
  return n && c.codigo ? Object.assign(n, { codigo: c.codigo }) : null;
}

function mostrarConfig(mostrar) {
  $('config').hidden = !mostrar;
  $('envio').hidden = mostrar;
}

/* ---------------------------------------------------------------- el envío */

async function enviarDirecto(cfg, ruta, metodo, cuerpo) {
  const r = await fetch(cfg.api + ruta, {
    method: metodo, credentials: 'include', redirect: 'manual',
    headers: Object.assign({ 'X-Estudio-Envio': cfg.codigo }, cuerpo ? { 'Content-Type': 'application/json' } : {}),
    body: cuerpo || undefined,
  });
  /* el login contesta con una redirección a /login (o con su página): no hay sesión aquí */
  if (r.type === 'opaqueredirect' || (r.headers.get('content-type') || '').includes('text/html')) return { sinSesion: true };
  let datos = null;
  try { datos = await r.json(); } catch (e) { datos = null; }
  return { status: r.status, datos };
}

async function enviarDesdeElStudio(cfg, ruta, metodo, cuerpo) {
  let pestanas = [];
  try { pestanas = await chrome.tabs.query({ url: cfg.origen + '/*' }); } catch (e) { pestanas = []; }
  const pestana = pestanas.find(p => (p.url || '').startsWith(cfg.base)) || pestanas[0];
  if (!pestana) return { sinPestana: true };
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: pestana.id },
    args: [cfg.api + ruta, metodo, cfg.codigo, cuerpo || null],
    func: async (url, metodo_, codigo, cuerpo_) => {
      const r = await fetch(url, {
        method: metodo_, credentials: 'same-origin',
        headers: Object.assign({ 'X-Estudio-Envio': codigo }, cuerpo_ ? { 'Content-Type': 'application/json' } : {}),
        body: cuerpo_ || undefined,
      });
      let datos = null;
      try { datos = await r.json(); } catch (e) { datos = null; }
      return { status: r.status, datos, redirigida: r.redirected && /\/login/.test(r.url) };
    },
  });
  const v = res && res.result;
  if (!v || v.redirigida) return { sinSesion: true };
  return v;
}

async function hablarConElStudio(cfg, ruta, metodo, cuerpo) {
  let r;
  try { r = await enviarDirecto(cfg, ruta, metodo, cuerpo); } catch (e) { r = { error: e.message }; }
  if (r.sinSesion || r.error) {
    const otra = await enviarDesdeElStudio(cfg, ruta, metodo, cuerpo).catch(e => ({ error: e.message }));
    if (otra.sinPestana) {
      return { mal: r.error ? `no se puede hablar con el Studio (${r.error}). ¿Está bien la dirección?`
        : 'Abre tu Studio en otra pestaña de este Chrome, inicia sesión y vuelve a pulsar.' };
    }
    if (otra.sinSesion) return { mal: 'Tu Studio pide iniciar sesión: entra en su pestaña y vuelve a pulsar.' };
    if (otra.error) return { mal: `no se ha podido enviar: ${otra.error}` };
    r = otra;
  }
  if (r.status === 401) return { mal: 'El código de envío no vale. Crea uno nuevo en Configuración → Enviar al Studio y pégalo aquí (⚙).' };
  if (r.status >= 400 || !r.datos) return { mal: (r.datos && (r.datos.error || r.datos.detail)) || `el Studio ha contestado ${r.status}` };
  return { bien: r.datos };
}

/* ------------------------------------------------------------- la página */

async function leerPestana() {
  const [pestana] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!pestana || !/^https?:/.test(pestana.url || '')) {
    estado('estado', 'Esta pestaña no se puede enviar: abre un post o una página web.', 'mal');
    $('enviar').disabled = true;
    return;
  }
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId: pestana.id }, files: ['lector.js'] });
    leido = Object.assign({ url: pestana.url, titulo: pestana.title }, res && res.result);
  } catch (e) {
    leido = { url: pestana.url, titulo: pestana.title, cifras: {}, red: 'web', aviso: 'no se ha podido leer la página; va el enlace y la captura' };
  }
  leido.windowId = pestana.windowId;
  const NOMBRES = { instagram: 'Instagram', tiktok: 'TikTok', youtube: 'YouTube', facebook: 'Facebook',
    linkedin: 'LinkedIn', x: 'X', threads: 'Threads', pinterest: 'Pinterest', web: 'Web' };
  const ETIQUETAS = { vistas: 'vistas', me_gusta: 'me gusta', comentarios: 'comentarios', compartidos: 'compartidos', guardados: 'guardados' };
  $('red').textContent = NOMBRES[leido.red] || 'Web';
  $('autor').textContent = leido.autor ? '@' + leido.autor : '';
  $('titulo').textContent = leido.titulo || '';
  $('cifras').textContent = Object.entries(leido.cifras || {}).map(([k, v]) => `${v} ${ETIQUETAS[k] || k}`).join(' · ')
    || 'No se ven cifras en esta página.';
  $('texto').textContent = (leido.seleccion || leido.texto || '').slice(0, 600);
  if (leido.aviso) estado('estado', leido.aviso, 'mal');
}

async function enviar() {
  const cfg = await config();
  if (!cfg) { mostrarConfig(true); return; }
  if (!leido) return;
  $('enviar').disabled = true;
  estado('estado', 'enviando…');
  let captura = '';
  if ($('conCaptura').checked) {
    try { captura = await chrome.tabs.captureVisibleTab(leido.windowId, { format: 'jpeg', quality: 72 }); }
    catch (e) { captura = ''; }
  }
  const cuerpo = JSON.stringify({
    url: leido.url, titulo: leido.titulo, autor: leido.autor, texto: leido.texto, seleccion: leido.seleccion,
    nota: $('nota').value.trim(), cifras: leido.cifras || {}, imagen: leido.imagen || '', captura,
  });
  const r = await hablarConElStudio(cfg, 'recibidos', 'POST', cuerpo);
  if (r.bien) {
    estado('estado', '✓ Enviado. Lo tienes en Automatizar → Recibidos de Chrome.', 'bien');
    $('nota').value = '';
  } else {
    estado('estado', r.mal, 'mal');
    $('enviar').disabled = false;
  }
}

/* ----------------------------------------------------------- los ajustes */

async function guardar() {
  const n = normalizar($('studio').value);
  const codigo = $('codigo').value.trim();
  if (!n) { estado('estadoConfig', 'La dirección no parece una web (https://…).', 'mal'); return; }
  if (!codigo) { estado('estadoConfig', 'Falta el código de envío.', 'mal'); return; }
  /* el permiso para hablar con TU Studio, y solo con él */
  const ok = await chrome.permissions.request({ origins: [n.origen + '/*'] }).catch(() => false);
  if (!ok) { estado('estadoConfig', 'Sin ese permiso la extensión no puede mandar nada a tu Studio.', 'mal'); return; }
  await chrome.storage.local.set({ studio: n.base, codigo });
  estado('estadoConfig', 'Guardado. Pulsa «Probar» para comprobarlo.', 'bien');
}

async function probar() {
  await guardar();
  const cfg = await config();
  if (!cfg) return;
  estado('estadoConfig', 'probando…');
  const r = await hablarConElStudio(cfg, 'recibidos/ping', 'GET', null);
  if (r.bien) {
    estado('estadoConfig', '✓ Conectado con tu Studio.', 'bien');
    setTimeout(() => { mostrarConfig(false); leerPestana(); }, 900);
  } else estado('estadoConfig', r.mal, 'mal');
}

document.addEventListener('DOMContentLoaded', async () => {
  $('ajustes').addEventListener('click', async () => {
    const c = await chrome.storage.local.get(['studio', 'codigo']);
    $('studio').value = c.studio || '';
    $('codigo').value = c.codigo || '';
    mostrarConfig($('config').hidden);
  });
  $('guardar').addEventListener('click', guardar);
  $('probar').addEventListener('click', probar);
  $('enviar').addEventListener('click', enviar);
  if (await config()) { mostrarConfig(false); leerPestana(); }
  else mostrarConfig(true);
});

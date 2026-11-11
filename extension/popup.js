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
 * La dirección y el código se guardan en chrome.storage.local, en este Chrome:
 * se ponen UNA vez y sirven para todas las pestañas. Mientras se escriben se
 * guardan como borrador (la ventanita se cierra en cuanto pulsas fuera de ella,
 * y sin eso se perdía lo pegado). El Studio da una «clave de conexión» que
 * lleva las dos cosas juntas (`https://…/#env_…`): pegada en cualquiera de los
 * dos campos, se reparte sola.
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
  /* https siempre: por http el código viajaría sin cifrar. Solo un Studio en este
     mismo ordenador (localhost) puede ir por http. */
  const local = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(u.hostname);
  if (!(u.protocol === 'https:' || (u.protocol === 'http:' && local))) return null;
  /* la dirección del Studio puede llevar una carpeta (/v2/): la API cuelga de ahí. Si se
     pega la de una pantalla (…/login, …/index.html) se quita ese último trozo */
  let carpeta = u.pathname.replace(/\/(login|studio|index\.html|[^/]*\.[a-z0-9]+)\/?$/i, '/');
  if (!carpeta.endsWith('/')) carpeta += '/';
  return { base: u.origin + carpeta, origen: u.origin, api: u.origin + carpeta + 'api/' };
}

async function config() {
  const c = await chrome.storage.local.get(['studio', 'codigo']);
  const n = normalizar(c.studio);
  return n && c.codigo ? Object.assign(n, { codigo: c.codigo }) : null;
}

/* «https://studio…/#env_abc» → { studio: 'https://studio…/', codigo: 'env_abc' }.
   Un código suelto o una dirección sola se devuelven tal cual en su sitio. */
function repartirClave(texto) {
  const t = String(texto || '').trim();
  const m = t.match(/^(.*?)#(env_[A-Za-z0-9_-]+)\s*$/);
  if (m) return { studio: m[1].trim(), codigo: m[2] };
  if (/^env_[A-Za-z0-9_-]+$/.test(t)) return { codigo: t };
  return { studio: t };
}

/* La clave pegada en cualquiera de los dos campos se reparte, aunque Chrome la
   haya añadido detrás de lo que ya había (se busca la ÚLTIMA clave entera). Un
   código a medio escribir («env») no es una dirección: solo se mueve lo que
   empieza por http. */
const CLAVE_ENTERA = /https?:\/\/(?:(?!https?:\/\/)[^\s#"'«»])+#env_[A-Za-z0-9_-]+/g;

function repartirCampos() {
  const claves = ($('studio').value + ' ' + $('codigo').value).match(CLAVE_ENTERA);
  if (claves) {
    const r = repartirClave(claves[claves.length - 1]);
    $('studio').value = r.studio;
    $('codigo').value = r.codigo;
    return;
  }
  const enDireccion = repartirClave($('studio').value);
  if (enDireccion.codigo && !enDireccion.studio) {   // un código suelto pegado en el primer campo
    $('studio').value = '';
    $('codigo').value = enDireccion.codigo;
  }
  const enCodigo = repartirClave($('codigo').value);
  if (enCodigo.studio && /^https?:\/\//i.test(enCodigo.studio)) {   // una dirección en el campo del código
    if (!$('studio').value.trim()) $('studio').value = enCodigo.studio;
    $('codigo').value = '';
  }
}

/* Lo escrito se guarda al momento como borrador: cerrar la ventanita no lo pierde. */
function guardarBorrador() {
  repartirCampos();
  /* sin esperar: «Guardar»/«Probar» tienen que pedir el permiso de Chrome antes de
     ninguna otra espera (Chrome solo lo concede justo después del clic) */
  chrome.storage.local.set({ borradorStudio: $('studio').value.trim(), borradorCodigo: $('codigo').value.trim() })
    .catch(() => { /* sin almacén no hay borrador; lo demás sigue igual */ });
  const falta = !$('studio').value.trim() ? 'la dirección' : !$('codigo').value.trim() ? 'el código' : '';
  const completo = /^env_[A-Za-z0-9_-]{10,}$/.test($('codigo').value.trim());
  estado('estadoConfig', falta ? `Guardado lo que has puesto. Falta ${falta}: puedes salir a copiarlo y volver.`
    : completo ? 'Pulsa «Probar» para conectar.' : 'El código parece incompleto: cópialo entero del Studio.', '');
}

/* Lo que se enseña al abrir: el borrador ENTERO si lo hay (aunque tenga un campo
   vacío: mezclarlo con lo guardado pondría el código de un Studio con la dirección
   de otro), y si no, lo guardado. */
async function rellenarConfig() {
  const c = await chrome.storage.local.get(['studio', 'codigo', 'borradorStudio', 'borradorCodigo']);
  const hayBorrador = 'borradorStudio' in c || 'borradorCodigo' in c;
  $('studio').value = (hayBorrador ? c.borradorStudio : c.studio) ?? '';
  $('codigo').value = (hayBorrador ? c.borradorCodigo : c.codigo) ?? '';
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

/* ¿Esa dirección es un Studio? Se pregunta SIN el código: un Studio contesta a
   /api/recibidos/ping con un 401 suyo, o su login lo manda a /login. Así una
   errata en la dirección no le regala el código a otra web. */
async function esUnStudio(n) {
  try {
    const r = await fetch(n.api + 'recibidos/ping', { credentials: 'include', redirect: 'manual' });
    if (r.type === 'opaqueredirect') return true;
    if (r.status === 401 || r.status === 200) {
      const d = await r.json().catch(() => null);
      return !!d && (r.status === 200 || /c[oó]digo de env[ií]o/.test(String(d.error || '')));
    }
  } catch (e) { return false; }
  return false;
}

async function guardar() {
  guardarBorrador();
  const n = normalizar($('studio').value);
  const codigo = $('codigo').value.trim();
  if (!$('studio').value.trim()) { estado('estadoConfig', 'Falta la dirección de tu Studio. Lo demás queda guardado: puedes salir a copiarla y volver.', 'mal'); return false; }
  if (!n) { estado('estadoConfig', 'La dirección tiene que ser una web que empiece por https://', 'mal'); return false; }
  if (!codigo) { estado('estadoConfig', 'Falta el código de envío. La dirección queda guardada: puedes salir a copiarlo y volver.', 'mal'); return false; }
  /* el permiso para hablar con TU Studio, y solo con él */
  const ok = await chrome.permissions.request({ origins: [n.origen + '/*'] }).catch(() => false);
  if (!ok) { estado('estadoConfig', 'Sin ese permiso la extensión no puede mandar nada a tu Studio.', 'mal'); return false; }
  estado('estadoConfig', 'comprobando la dirección…');
  if (!(await esUnStudio(n))) {
    estado('estadoConfig', 'En esa dirección no contesta un CrearIA Studio. Cópiala de Configuración → Enviar al Studio.', 'mal');
    return false;
  }
  await chrome.storage.local.set({ studio: n.base, codigo });
  try { await chrome.storage.local.remove(['borradorStudio', 'borradorCodigo']); } catch (e) { /* el borrador sobra, no estorba */ }
  estado('estadoConfig', 'Guardado. Pulsa «Probar» para comprobarlo.', 'bien');
  return true;
}

async function probar() {
  if (!(await guardar())) return;
  const cfg = await config();
  if (!cfg) return;
  estado('estadoConfig', 'probando…');
  const r = await hablarConElStudio(cfg, 'recibidos/ping', 'GET', null);
  if (r.bien) {
    estado('estadoConfig', '✓ Conectado con tu Studio. No hace falta volver a ponerlo: sirve en todas las pestañas de este Chrome.', 'bien');
    setTimeout(() => { mostrarConfig(false); leerPestana(); }, 2500);
  } else estado('estadoConfig', r.mal, 'mal');
}

document.addEventListener('DOMContentLoaded', async () => {
  $('ajustes').addEventListener('click', async () => {
    const abrir = $('config').hidden;
    if (abrir) { await rellenarConfig(); mostrarConfig(true); return; }
    /* sin configurar no hay nada a lo que volver: se queda en la configuración */
    if (!(await config())) return;
    mostrarConfig(false);
    leerPestana();
  });
  for (const id of ['studio', 'codigo']) {
    $(id).addEventListener('input', guardarBorrador);
    /* al entrar en un campo se selecciona entero: pegar lo REEMPLAZA en vez de añadirse detrás */
    $(id).addEventListener('focus', e => e.target.select());
  }
  $('guardar').addEventListener('click', guardar);
  $('probar').addEventListener('click', probar);
  $('enviar').addEventListener('click', enviar);
  if (await config()) { mostrarConfig(false); leerPestana(); }
  else { await rellenarConfig(); mostrarConfig(true); }
});

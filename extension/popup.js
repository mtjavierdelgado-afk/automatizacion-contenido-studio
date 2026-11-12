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
let enviando = false;

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
  let carpeta = u.pathname.replace(/\/(login|index\.html|[^/]*\.[a-z0-9]+)\/?$/i, '/');
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
const CLAVE_ENTERA = /https?:\/\/(?:(?!https?:\/\/)[^\s#"'«»])+#env_[A-Za-z0-9_-]+(?=[\s.,;:!?»"')\]]|$)/g;

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
  /* si Chrome cerró la ventanita al pedir el permiso, al volver se dice qué toca */
  if (hayBorrador && $('studio').value && $('codigo').value) estado('estadoConfig', 'Está todo puesto: pulsa «Probar» para conectar.', '');
}

/* Pegar: si lo pegado es una clave entera (o un código), se reparte en los dos
   campos en vez de entrar donde esté el cursor, que podía dejarlo a medias. */
function alPegar(e) {
  const t = String((e.clipboardData && e.clipboardData.getData('text')) || '').trim();
  const claves = t.match(CLAVE_ENTERA);
  if (claves) {
    e.preventDefault();
    const r = repartirClave(claves[claves.length - 1]);
    $('studio').value = r.studio; $('codigo').value = r.codigo;
  } else if (/^env_[A-Za-z0-9_-]+$/.test(t)) {
    e.preventDefault();
    $('codigo').value = t;
  } else if (/^https?:\/\/\S+$/.test(t) && e.target.id === 'studio') {
    e.preventDefault();
    $('studio').value = t;
  } else return;
  guardarBorrador();
}

function mostrarConfig(mostrar) {
  $('config').hidden = !mostrar;
  $('envio').hidden = mostrar;
}

/* ---------------------------------------------------------------- el envío */

async function enviarDirecto(cfg, ruta, metodo, cuerpo) {
  const r = await fetch(cfg.api + ruta, {
    method: metodo, credentials: 'include', redirect: 'manual', signal: AbortSignal.timeout(30000),
    headers: Object.assign({ 'X-Estudio-Envio': cfg.codigo }, cuerpo ? { 'Content-Type': 'application/json' } : {}),
    body: cuerpo || undefined,
  });
  /* el login contesta con una redirección a /login (o con su página): no hay sesión aquí.
     Un 5xx en HTML es otra cosa: nginx diciendo que el Studio está caído */
  if (r.type === 'opaqueredirect') return { sinSesion: true };
  if ((r.headers.get('content-type') || '').includes('text/html')) return r.status >= 500 ? { caido: r.status } : { sinSesion: true };
  let datos = null;
  try { datos = await r.json(); } catch (e) { datos = null; }
  return { status: r.status, datos };
}

async function enviarDesdeElStudio(cfg, ruta, metodo, cuerpo) {
  let pestanas = [];
  try { pestanas = await chrome.tabs.query({ url: cfg.origen + '/*' }); } catch (e) { pestanas = []; }
  /* solo pestañas que de verdad son del Studio (sin el permiso «tabs» la dirección puede no
     venir: esas no cuentan), y mejor una despierta: Chrome duerme las que llevan rato quietas */
  const delStudio = pestanas.filter(p => p.url && p.url.startsWith(cfg.base));
  const pestana = delStudio.find(p => !p.discarded) || null;
  if (!pestana) return delStudio.length ? { dormida: true } : { sinPestana: true };
  const [res] = await chrome.scripting.executeScript({
    target: { tabId: pestana.id },
    args: [cfg.api + ruta, metodo, cfg.codigo, cuerpo || null],
    func: async (url, metodo_, codigo, cuerpo_) => {
      /* sin seguir redirecciones: el código va en la cabecera y no sale de esta web */
      const r = await fetch(url, {
        method: metodo_, credentials: 'same-origin', redirect: 'manual', signal: AbortSignal.timeout(30000),
        headers: Object.assign({ 'X-Estudio-Envio': codigo }, cuerpo_ ? { 'Content-Type': 'application/json' } : {}),
        body: cuerpo_ || undefined,
      });
      let datos = null;
      try { datos = await r.json(); } catch (e) { datos = null; }
      return { status: r.status, datos, redirigida: r.type === 'opaqueredirect' };
    },
  });
  const v = res && res.result;
  if (!v || v.redirigida) return { sinSesion: true };
  return v;
}

/* Los textos que ve el dueño dicen QUÉ pasa y QUÉ hacer, en castellano: nunca el
   mensaje en inglés del navegador («Failed to fetch»). */
const CAIDO = n => `Tu Studio no contesta ahora (error ${n}). Prueba otra vez en unos minutos.`;

async function hablarConElStudio(cfg, ruta, metodo, cuerpo) {
  /* un permiso quitado a mano en chrome://extensions: se dice, en vez de «la dirección está mal» */
  const conPermiso = await chrome.permissions.contains({ origins: [cfg.origen + '/*'] }).catch(() => true);
  if (!conPermiso) return { mal: 'La extensión ya no tiene permiso para hablar con tu Studio: pulsa ⚙ y luego «Probar» para volver a darlo.' };
  let r;
  try { r = await enviarDirecto(cfg, ruta, metodo, cuerpo); }
  catch (e) { r = e && e.name === 'TimeoutError' ? { lento: true } : { sinRed: true }; }
  if (r.caido) return { mal: CAIDO(r.caido) };
  /* tardó demasiado: puede haber llegado igual, y volver a mandarlo lo duplicaría */
  if (r.lento) {
    return { mal: metodo === 'POST'
      ? 'Tu Studio tarda mucho en contestar. Mira en Automatizar → Recibidos de Chrome si ya llegó antes de volver a pulsar.'
      : 'Tu Studio tarda mucho en contestar. Prueba otra vez en unos minutos.' };
  }
  if (r.sinSesion || r.sinRed) {
    const otra = await enviarDesdeElStudio(cfg, ruta, metodo, cuerpo).catch(() => ({ fallo: true }));
    if (otra.sinPestana) {
      return { mal: r.sinRed ? 'No se puede llegar a tu Studio. Mira que tienes internet y que la dirección (⚙) es la de tu Studio.'
        : 'Abre tu Studio en otra pestaña de este Chrome, inicia sesión y vuelve a pulsar.' };
    }
    if (otra.dormida) return { mal: 'La pestaña de tu Studio está dormida: pulsa en ella, espera a que cargue y vuelve a pulsar aquí.' };
    if (otra.sinSesion) return { mal: 'Tu Studio pide iniciar sesión: entra en su pestaña y vuelve a pulsar.' };
    if (otra.fallo) return { mal: 'No se ha podido enviar desde la pestaña de tu Studio: recárgala (F5) y vuelve a pulsar.' };
    r = otra;
  }
  if (r.status === 401) return { mal: 'El código de envío no vale. Crea uno nuevo en Configuración → Enviar al Studio y pégalo aquí (⚙).', status: 401 };
  if (r.status >= 500) return { mal: CAIDO(r.status), status: r.status };
  if (r.status >= 400 || !r.datos) {
    const error = (r.datos && (r.datos.error || r.datos.detail)) || '';
    return { mal: error ? String(error).charAt(0).toUpperCase() + String(error).slice(1) + '.' : `Tu Studio ha contestado con un error (${r.status}).`,
      status: r.status, error: String(error) };
  }
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
  if (leido.aviso) estado('estado', leido.aviso.charAt(0).toUpperCase() + leido.aviso.slice(1) + '.', 'mal');
  $('enviar').disabled = false;   // hasta aquí no hay nada que enviar
}

/* El menú «Proyecto»: los proyectos del Studio (con el código de envío) y el
   último elegido marcado. Si no se pueden leer, queda «Sin proyecto» y se envía
   igual: anexarlo después se hace en el Studio (11-11-2026). */
let proyectosCargados = false;
async function cargarProyectos() {
  const cfg = await config();
  if (!cfg) return;
  $('proyecto').disabled = true;   // hasta que llegue la lista: elegir ahora no serviría
  const { ultimoProyecto } = await chrome.storage.local.get(['ultimoProyecto']).catch(() => ({}));
  const r = await hablarConElStudio(cfg, 'recibidos/proyectos', 'GET', null).catch(() => ({}));
  const sel = $('proyecto');
  const lista = (r.bien && r.bien.proyectos) || [];
  proyectosCargados = !!r.bien;
  sel.disabled = false;
  /* sin la lista se puede enviar igual, pero que se sepa que irá sin proyecto */
  const pista = $('pistaProyecto');
  pista.hidden = proyectosCargados;
  pista.textContent = proyectosCargados ? '' : 'No he podido leer tus proyectos: se enviará sin proyecto y lo puedes anexar después en el Studio.';
  while (sel.options.length > 1) sel.remove(1);   // al volver a cargarlos, sin repetir
  for (const p of lista) {
    const o = document.createElement('option');
    o.value = p.id; o.textContent = p.nombre || p.id;
    sel.appendChild(o);
  }
  if (ultimoProyecto && lista.some(p => p.id === ultimoProyecto)) sel.value = ultimoProyecto;
}

async function enviar() {
  /* lo primero, antes de ninguna espera: dos pulsaciones seguidas no mandan dos */
  if (enviando || !leido) return;
  enviando = true;
  $('enviar').disabled = true;
  try { await enviarYa(); }
  catch (e) {
    /* algo de Chrome que falla (el almacén, la captura): que se diga y se pueda volver a pulsar */
    estado('estado', 'No se ha podido enviar por un fallo de Chrome. Cierra la ventanita, ábrela otra vez y vuelve a pulsar.', 'mal');
    $('enviar').disabled = false;
  } finally { enviando = false; }
}

async function enviarYa() {
  const cfg = await config();
  if (!cfg) { $('enviar').disabled = false; await rellenarConfig(); mostrarConfig(true); return; }
  estado('estado', 'Enviando…');
  let captura = '';
  if ($('conCaptura').checked) {
    try { captura = await chrome.tabs.captureVisibleTab(leido.windowId, { format: 'jpeg', quality: 72 }); }
    catch (e) { captura = ''; }
  }
  const cuerpo = JSON.stringify({
    url: leido.url, titulo: leido.titulo, autor: leido.autor, texto: leido.texto, seleccion: leido.seleccion,
    nota: $('nota').value.trim(), cifras: leido.cifras || {}, imagen: leido.imagen || '', captura,
    proyecto: $('proyecto').value,
  });
  const r = await hablarConElStudio(cfg, 'recibidos', 'POST', cuerpo);
  if (r.bien) {
    /* solo si la lista llegó (con el menú vacío, «Sin proyecto» no es una elección) y el envío fue bien */
    if (proyectosCargados) chrome.storage.local.set({ ultimoProyecto: $('proyecto').value }).catch(() => {});
    const nombre = $('proyecto').value ? $('proyecto').selectedOptions[0].textContent : '';
    estado('estado', `✓ Enviado${nombre ? ` a ${nombre}` : ''}. Lo tienes en Automatizar → Recibidos de Chrome.`, 'bien');
    $('enviar').disabled = false;
    $('nota').value = '';
  } else if (r.status === 400 && /proyecto/i.test(r.error || '')) {
    /* el proyecto se borró mientras tanto: se vuelve a pedir la lista */
    await cargarProyectos();
    estado('estado', 'Ese proyecto ya no está en tu Studio. Elige otro en el menú y vuelve a pulsar.', 'mal');
    $('enviar').disabled = false;
  } else {
    estado('estado', r.mal, 'mal');
    $('enviar').disabled = false;
  }
}

/* ----------------------------------------------------------- los ajustes */

/* ¿Esa dirección es un Studio? Se pregunta SIN el código: un Studio contesta a
   /api/recibidos/ping con un 401 suyo, o su login lo manda a /login. Así una
   errata en la dirección no le regala el código a otra web. */
const ES_STUDIO = d => !!d && d.ok === true && /CrearIA/.test(String(d.producto || ''));
async function esUnStudio(n) {
  /* Lo que vale (12-11-2026: antes valía CUALQUIER redirección y cualquier JSON):
     - el Studio sin sesión: su login redirige, y la página /login de ESA MISMA web es la de CrearIA
       (no se sigue la redirección: se pide /login a la dirección escrita);
     - el Studio con sesión: un 401 suyo que habla del código de envío, o su ping ({ok, producto}). */
  try {
    const r = await fetch(n.api + 'recibidos/ping', { credentials: 'include', redirect: 'manual' });
    if (r.type === 'opaqueredirect') {
      for (const login of [n.base + 'login', n.origen + '/login']) {
        const l = await fetch(login, { credentials: 'include', redirect: 'manual' }).catch(() => null);
        /* la página de acceso del Studio, con su título exacto: «CrearIA» a secas lo tiene cualquier web de la marca */
        if (l && l.status === 200 && /<title>\s*Acceso · CrearIA Studio\s*<\/title>/.test(await l.text().catch(() => ''))) return true;
      }
      return false;
    }
    const d = await r.json().catch(() => null);
    if (r.status === 401) return !!d && /c[oó]digo de env[ií]o/.test(String(d.error || ''));
    if (r.status === 200) return ES_STUDIO(d);
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
  estado('estadoConfig', 'Comprobando la dirección…');
  if (!(await esUnStudio(n))) {
    /* el permiso para esa web no hace falta: se devuelve */
    /* (salvo que sea la web del Studio ya guardado: estará caído, y su permiso hace falta) */
    const guardado = normalizar((await chrome.storage.local.get(['studio']).catch(() => ({}))).studio);
    if (!guardado || guardado.origen !== n.origen) {
      try { chrome.permissions.remove({ origins: [n.origen + '/*'] }).catch(() => {}); } catch (e) { /* no estorba */ }
    }
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
  estado('estadoConfig', 'Probando…');
  const r = await hablarConElStudio(cfg, 'recibidos/ping', 'GET', null);
  if (r.bien && !ES_STUDIO(r.bien)) {
    estado('estadoConfig', 'En esa dirección no contesta un CrearIA Studio. Cópiala de Configuración → Enviar al Studio.', 'mal');
  } else if (r.bien) {
    estado('estadoConfig', '✓ Conectado con tu Studio. No hace falta volver a ponerlo: sirve en todas las pestañas de este Chrome.', 'bien');
    setTimeout(() => { mostrarConfig(false); leerPestana(); cargarProyectos(); }, 2500);
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
    cargarProyectos();   // por si se cambió de Studio: su lista, no la del anterior
  });
  for (const id of ['studio', 'codigo']) {
    $(id).addEventListener('input', guardarBorrador);
    $(id).addEventListener('paste', alPegar);
    /* al entrar en un campo se selecciona entero: pegar lo REEMPLAZA en vez de añadirse detrás */
    $(id).addEventListener('focus', e => setTimeout(() => e.target.select(), 0));   // tras soltar el ratón, o se deshace
  }
  $('guardar').addEventListener('click', guardar);
  $('probar').addEventListener('click', probar);
  $('enviar').addEventListener('click', enviar);
  $('enviar').disabled = true;   // hasta que se haya leído la página
  if (await config()) { mostrarConfig(false); leerPestana(); cargarProyectos(); }
  else { await rellenarConfig(); mostrarConfig(true); }
});

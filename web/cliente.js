// La página que ve el CLIENTE para aprobar un vídeo (rama publicar-redes-3).
// No carga nada del Studio: ve el vídeo, los textos de cada red y la fecha, y
// contesta «Aprobar» o «Pedir cambios». Todo cuelga de /cliente/<token>/.
'use strict';

(function () {
  const raiz = document.getElementById('cliente');
  const trozos = location.pathname.split('/').filter(Boolean);
  const token = trozos[trozos.length - 1] || '';
  const BASE = location.pathname.replace(/\/+$/, '') + '/';   // …/cliente/<token>/
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
    'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  let datos = null;
  let eleccion = '';
  let editando = false;

  function h(etiqueta, props, ...hijos) {
    const el = document.createElement(etiqueta);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k in el && k !== 'list') el[k] = v;
      else el.setAttribute(k, v);
    }
    for (const hijo of hijos.flat()) {
      if (hijo === null || hijo === undefined || hijo === false) continue;
      el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
    }
    return el;
  }

  // «2026-12-01T19:00:00» (hora de Lima, como la guarda el Studio) -> texto.
  // Sin pasar por Date: así no se mueve con la zona del móvil del cliente.
  function fechaBonita(iso, conHora) {
    const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(String(iso || ''));
    if (!m) return '';
    const dia = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).getUTCDay();
    let texto = `${DIAS[dia]} ${+m[3]} de ${MESES[+m[2] - 1]}`;
    if (conHora && m[4]) texto += ` a las ${m[4]}:${m[5]}`;
    return texto;
  }

  async function pedir(ruta, opciones) {
    let r;
    try {
      r = await fetch(BASE + ruta, Object.assign({ cache: 'no-store', credentials: 'omit' }, opciones));
    } catch (_e) {
      throw new Error('No hay conexión. Revisa tu internet y vuelve a probar.');
    }
    let cuerpo = {};
    try { cuerpo = await r.json(); } catch (_e) { cuerpo = {}; }
    if (r.status === 429) throw new Error('Demasiados intentos seguidos: espera un minuto y vuelve a probar.');
    if (!r.ok) throw Object.assign(new Error(cuerpo.error || 'Algo ha fallado. Vuelve a probar en un momento.'), { estado: r.status });
    return cuerpo;
  }

  function nota(clase, texto) { return h('p', { class: 'cl-nota ' + clase }, texto); }

  function cabecera() {
    return h('header', { class: 'cl-cabecera' },
      datos.proyecto ? h('p', { class: 'cl-proyecto' }, datos.proyecto) : null,
      h('h1', {}, datos.video || 'Tu vídeo'));
  }

  function bloqueVideo() {
    const caja = h('section', { class: 'cl-tarjeta' });
    if (datos.hay_video) {
      caja.append(h('video', {
        class: 'cl-video' + (datos.formato === 'vertical' ? ' cl-vertical' : ''),
        src: BASE + 'video.mp4?v=' + encodeURIComponent(datos.v || ''),
        controls: true, playsInline: true, preload: 'metadata',
      }));
    } else {
      caja.append(h('p', { class: 'cl-suave' }, 'El vídeo no está disponible ahora mismo.'));
    }
    caja.append(h('p', { class: 'cl-fecha' }, datos.fecha
      ? `Saldría el ${fechaBonita(datos.fecha, true)} (hora de Perú).`
      : 'Todavía no tiene fecha de publicación.'));
    return caja;
  }

  function bloqueTextos() {
    if (!datos.redes || !datos.redes.length) return null;
    return h('section', { class: 'cl-tarjeta' },
      h('h2', {}, datos.redes.length === 1 ? 'El texto que lo acompaña' : 'Los textos de cada red'),
      datos.redes.map(r => h('div', { class: 'cl-red' },
        h('h3', {}, r.nombre),
        r.titulo ? h('p', { class: 'cl-titulo' }, r.titulo) : null,
        r.descripcion ? h('p', { class: 'cl-texto' }, r.descripcion)
          : h('p', { class: 'cl-suave' }, 'Aún sin texto.'),
        r.hashtags ? h('p', { class: 'cl-hashtags' }, r.hashtags) : null)));
  }

  function bloqueRespuesta() {
    const caja = h('section', { class: 'cl-tarjeta' });
    const respondido = datos.respondido_al && !editando;
    if (respondido) {
      const aprobado = datos.estado === 'aprobado';
      caja.append(
        h('h2', {}, 'Tu respuesta'),
        nota(aprobado ? 'cl-bien' : 'cl-aviso', aprobado
          ? `Lo aprobaste el ${fechaBonita(datos.respondido_al, true)}. ¡Gracias!`
          : `Pediste cambios el ${fechaBonita(datos.respondido_al, true)}. Te avisaremos cuando esté.`),
        datos.comentario ? h('p', { class: 'cl-texto' }, '«' + datos.comentario + '»') : null,
        h('div', { class: 'cl-botones' }, h('button', {
          type: 'button', class: 'cl-boton cl-enlace',
          onclick: () => { editando = true; eleccion = ''; pintar(); },
        }, 'Cambiar mi respuesta')));
      return caja;
    }
    const comentario = h('textarea', {
      class: 'cl-comentario', id: 'cl-comentario', maxLength: 2000,
      placeholder: 'Por ejemplo: cambia la música, o quita la segunda frase del texto.',
    });
    const etiqueta = h('label', { class: 'cl-etiqueta', htmlFor: 'cl-comentario' }, 'Comentario (opcional)');
    const error = h('p', { class: 'cl-nota cl-mal cl-oculto', role: 'alert' });
    const enviar = h('button', { type: 'button', class: 'cl-boton cl-principal cl-oculto' }, 'Enviar');
    const aprobar = h('button', { type: 'button', class: 'cl-boton' }, '✓ Aprobar');
    const cambios = h('button', { type: 'button', class: 'cl-boton' }, '✎ Pedir cambios');
    function elegir(cual) {
      eleccion = cual;
      aprobar.classList.toggle('cl-elegido', cual === 'aprobado');
      cambios.classList.toggle('cl-elegido', cual === 'cambios');
      etiqueta.textContent = cual === 'cambios' ? '¿Qué cambiarías?' : 'Comentario (opcional)';
      enviar.textContent = cual === 'cambios' ? 'Enviar los cambios' : 'Enviar mi aprobación';
      enviar.classList.remove('cl-oculto');
      error.classList.add('cl-oculto');
      if (cual === 'cambios') comentario.focus();
    }
    aprobar.addEventListener('click', () => elegir('aprobado'));
    cambios.addEventListener('click', () => elegir('cambios'));
    enviar.addEventListener('click', async () => {
      const texto = comentario.value.trim();
      if (eleccion === 'cambios' && !texto) {
        error.textContent = 'Cuéntanos qué cambiarías.';
        error.classList.remove('cl-oculto');
        comentario.focus();
        return;
      }
      enviar.disabled = aprobar.disabled = cambios.disabled = true;
      enviar.textContent = 'Enviando…';
      try {
        const hecho = await pedir('respuesta', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decision: eleccion, comentario: texto, v: datos.v || '' }),
        });
        Object.assign(datos, hecho, { cambiado: false });
        editando = false;
        pintar();
      } catch (fallo) {
        error.textContent = fallo.message;
        error.classList.remove('cl-oculto');
        enviar.disabled = aprobar.disabled = cambios.disabled = false;
        enviar.textContent = eleccion === 'cambios' ? 'Enviar los cambios' : 'Enviar mi aprobación';
      }
    });
    if (!datos.hay_video) {
      // sin vídeo que mirar no se aprueba nada (se puede volver más tarde)
      caja.append(h('h2', {}, '¿Lo publicamos así?'),
        h('p', { class: 'cl-suave' }, 'Cuando el vídeo esté disponible podrás aprobarlo aquí mismo. Vuelve a abrir este enlace más tarde.'));
      return caja;
    }
    caja.append(
      h('h2', {}, '¿Lo publicamos así?'),
      h('p', { class: 'cl-suave' }, 'Mira el vídeo y los textos. Si está bien, apruébalo; si no, dinos qué cambiarías.'),
      h('div', { class: 'cl-botones' }, aprobar, cambios),
      etiqueta, comentario, error,
      h('div', { class: 'cl-botones' }, enviar,
        datos.respondido_al && !datos.cambiado ? h('button', {
          type: 'button', class: 'cl-boton cl-enlace',
          onclick: () => { editando = false; pintar(); },
        }, 'Dejar mi respuesta como estaba') : null));
    if (eleccion) elegir(eleccion);
    return caja;
  }

  function pintar() {
    // replaceChildren escribe «null» por cada hueco: solo los nodos de verdad
    raiz.replaceChildren(...[
      cabecera(),
      datos.cambiado ? nota('cl-aviso', 'El vídeo ha cambiado desde que lo aprobaste. Míralo otra vez y vuelve a aprobarlo si te parece bien.') : null,
      bloqueVideo(),
      bloqueTextos(),
      bloqueRespuesta(),
      h('p', { class: 'cl-pie' }, datos.caduca
        ? `Este enlace es solo para ti y vale hasta el ${fechaBonita(datos.caduca, false)}.`
        : 'Este enlace es solo para ti.'),
    ].filter(Boolean));
  }

  async function cargar() {
    try {
      datos = await pedir('datos');
      if (datos.cambiado) editando = true;
      pintar();
    } catch (fallo) {
      raiz.replaceChildren(
        h('header', { class: 'cl-cabecera' }, h('h1', {}, 'Revisión del vídeo')),
        nota('cl-mal', fallo.message));
    }
  }

  cargar();
}());

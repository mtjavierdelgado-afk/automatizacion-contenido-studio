/* Lee lo que se VE en la página abierta: el enlace, el título, el autor, el
 * texto del post, las cifras que enseña la red y lo que esté seleccionado.
 *
 * Se inyecta solo cuando pulsas el botón (permiso activeTab) y devuelve un
 * objeto; no guarda nada, no recorre la página ni pide nada a ningún servidor.
 *
 * LA REGLA (revisión del 12-11-2026): las redes son páginas que no se recargan
 * al pasar de un post a otro. La barra cambia, pero las etiquetas og:, el
 * título y muchas cajas de la página siguen siendo las del PRIMER post que se
 * abrió, o de otro que está debajo. Así que:
 *   1. las etiquetas og: solo valen si su dirección es la de la barra;
 *   2. lo que se lee de la página, solo dentro de una caja que se demuestre que
 *      es la del post de la barra (su código, su id, o el vídeo que se ve);
 *   3. si no hay ninguna de las dos, va el enlace y la captura, con un aviso.
 * Mejor no mandar nada que mandar lo de otro post.
 *
 * Las cifras van TAL CUAL se ven («1,2 mil», «12K»): las convierte el Studio
 * (pasos/recibidos.py, numero_visto), que es donde están probadas.
 */
(() => {
  const limpio = t => String(t || '').replace(/\s+/g, ' ').trim();
  const largo = t => String(t || '').replace(/\r\n/g, '\n').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  const meta = nombre => {
    const el = document.querySelector(`meta[property="${nombre}"], meta[name="${nombre}"], meta[itemprop="${nombre}"]`);
    return el ? limpio(el.getAttribute('content')) : '';
  };
  const textoDe = el => (el ? (el.innerText || el.textContent || '') : '');
  /* el primer elemento con texto DENTRO de una caja (nunca en toda la página) */
  const unoEn = (caja, ...selectores) => {
    if (!caja) return null;
    for (const s of selectores) {
      try {
        for (const el of caja.querySelectorAll(s)) if (limpio(textoDe(el))) return el;
      } catch (e) { /* selector que este navegador no entiende */ }
    }
    return null;
  };
  const textoEn = (caja, ...s) => largo(textoDe(unoEn(caja, ...s)));
  const cortoEn = (caja, ...s) => limpio(textoEn(caja, ...s));
  const numeroEn = (caja, ...s) => { const t = cortoEn(caja, ...s); return /\d/.test(t) ? t : ''; };
  const enMedio = e => { const r = e.getBoundingClientRect(); return r.height > 0 && r.width > 0 && r.top < innerHeight / 2 && r.bottom > innerHeight / 2; };
  /* la caja del vídeo que cruza la mitad de la pantalla: el primer antepasado que trae `dentro` */
  const cajaDelVideoQueSeVe = (dentro, vale = () => true) => {
    let c = [...document.querySelectorAll('video')].find(enMedio) || null;
    while (c && c !== document.body && !(c.querySelector(dentro) && vale(c))) c = c.parentElement;
    return c && c !== document.body && c !== document.documentElement ? c : null;
  };

  /* «12 respuestas, 34 reposts, 560 Me gusta, 89 mil visualizaciones» → cifras. */
  const PALABRAS = [
    ['vistas', /(visualizaciones|reproducciones|vistas|views|plays|visualizações)/],
    ['me_gusta', /(me gusta|likes?|reacciones|reactions|curtidas)/],
    ['comentarios', /(comentarios?|comments?|respuestas|replies)/],
    ['compartidos', /(compartid[oa]s?|veces compartido|shares?|reposts?|retweets?|republicaciones)/],
    ['guardados', /(guardad[oa]s?|bookmarks?|saves?)/],
  ];
  /* un espacio dentro del número solo si separa miles («12 345»): «1.024 38 comentarios» son dos;
     y el sufijo solo si es palabra entera: «12 más» o «7 mins» no son millones («mi» es el
     «milhões» abreviado del portugués: «2,5 mi») */
  const SUFIJO = '(?:mil millones|mill(?:ones|\\.)?|milh(?:ões|ão)|mil|mi|[kmb])(?![a-záéíóúñãõç])';
  const NUMERO = '(\\d(?:[\\d.,]|\\s(?=\\d{3}(?!\\d)))*(?:\\s*' + SUFIJO + ')?)';
  const SOLO = new RegExp('^\\d[\\d.,]*(?:\\s*' + SUFIJO + ')?$', 'i');
  const cifrasDeFrase = (frase, cifras) => {
    /* «230 M de vistas», «1,2 mil de reproducciones»: el «de» no separa la cifra de su nombre */
    const f = String(frase || '').toLowerCase().replace(/\s+de\s+(?=[a-záéíóúñ])/g, ' ');
    for (const [clave, palabra] of PALABRAS) {
      if (cifras[clave]) continue;
      const m = f.match(new RegExp(NUMERO + '\\s*' + palabra.source)) || f.match(new RegExp(palabra.source + '[:\\s]+' + NUMERO));
      if (m) cifras[clave] = limpio(/\d/.test(m[1]) ? m[1] : m[2]);
    }
    return cifras;
  };
  /* el primer número de una frase («al igual que 19,501,189 personas más» → «19,501,189») */
  const numeroDeFrase = frase => { const m = String(frase || '').toLowerCase().match(new RegExp(NUMERO)); return m ? limpio(m[1]) : ''; };
  /* lo que se ve en un botón, quedándose con el trozo que es SOLO un número (vidIQ pinta «1x» al lado) */
  const soloNumero = el => {
    if (!el) return '';
    const todo = limpio(textoDe(el));
    if (SOLO.test(todo)) return todo;
    for (const h of el.querySelectorAll('*')) { const v = limpio(textoDe(h)); if (SOLO.test(v)) return v; }
    return '';
  };

  const host = location.hostname.toLowerCase();
  const es = (...dominios) => dominios.some(d => host === d || host.endsWith('.' + d));
  const red = es('instagram.com') ? 'instagram' : es('tiktok.com') ? 'tiktok' : es('youtube.com', 'youtu.be') ? 'youtube'
    : es('x.com', 'twitter.com') ? 'x' : es('linkedin.com') ? 'linkedin' : es('facebook.com', 'fb.watch') ? 'facebook'
    : es('threads.net', 'threads.com') ? 'threads' : /(^|\.)pinterest\.([a-z]{2,3}|com?\.[a-z]{2})$/.test(host) ? 'pinterest' : 'web';
  const ruta = u => { try { return new URL(u, location.href).pathname.replace(/\/+$/, '').toLowerCase(); } catch (e) { return null; } };
  const aqui = ruta(location.href);

  /* 1) ¿Las etiquetas og: son de ESTA dirección? */
  const ogUrl = meta('og:url');
  const codigoIg = red === 'instagram' ? ((location.pathname.match(/\/(?:reels?|p|tv)\/([A-Za-z0-9_-]+)/) || [])[1] || '') : '';
  const vid = red === 'youtube'
    ? (new URLSearchParams(location.search).get('v') || (location.pathname.match(/^\/shorts\/([A-Za-z0-9_-]+)/) || [])[1]
      || (host === 'youtu.be' ? location.pathname.slice(1) : '') || '') : '';
  /* las portadas y los muros: ahí la barra no dice qué post es */
  const esMuro = !vid && !codigoIg && /^(|\/home|\/feed|\/foryou|\/following|\/explore|\/reels|\/shorts|\/watch)$/.test(aqui || '');
  let ogVale;
  if (red === 'web') ogVale = true;
  else if (!ogUrl) ogVale = false;
  else if (codigoIg) ogVale = new RegExp('/' + codigoIg + '(?:/|$|\\?)').test(ogUrl);
  else if (vid) ogVale = ogUrl.includes('v=' + vid) || ogUrl.includes('/shorts/' + vid) || ogUrl.includes('youtu.be/' + vid);
  else ogVale = ruta(ogUrl) === aqui;
  if (ogVale && esMuro && red !== 'web') ogVale = false;   // la og: de la portada no es la de ningún post

  const datos = {
    url: location.href,
    titulo: (ogVale && meta('og:title')) || limpio(document.title),
    autor: '', texto: '', imagen: ogVale ? meta('og:image') : '',
    seleccion: largo(String(window.getSelection ? window.getSelection() : '')).slice(0, 5000),
    cifras: {}, red, lector: red === 'web' || red === 'threads' || red === 'pinterest' ? 'generico' : red,
  };
  if (red === 'web') {
    /* una web normal se recarga en cada página: su canónico vale, salvo que sea la portada u otra web */
    const canon = (document.querySelector('link[rel="canonical"]') || {}).href || ogUrl;
    try {
      const c = new URL(canon, location.href);
      if (canon && c.hostname === location.hostname && !(c.pathname === '/' && location.pathname !== '/')) datos.url = c.href;
    } catch (e) { /* se queda la barra */ }
  } else if (ogVale && ogUrl) {
    try { if (new URL(ogUrl).hostname.replace(/^www\./, '') === host.replace(/^www\./, '')) datos.url = ogUrl; } catch (e) { /* la barra */ }
  }
  let descripcion = ogVale ? (meta('og:description') || meta('description')) : '';
  let caja = null;            // la caja que se ha demostrado que es la del post de la barra

  try {
    if (red === 'instagram') {
      /* 1) Las etiquetas og: de ESTE post: «1.234 Me gusta, 56 comentarios - usuario el 3 de
         octubre: "texto"», en inglés «… on October 3, 2026: "text"», o sin las cifras. Las cifras
         no admiten comillas ni dos puntos, para que un « - » dentro del pie no cambie el autor. */
      if (ogVale && descripcion) {
        const m = descripcion.match(/^(?:([^:"“«]*?)\s+-\s+)?([A-Za-z0-9._]+)\s+(?:el|on)\s+[^:"“«]+?:\s*["“«]?([\s\S]*?)["”»]?\.?$/);
        if (m) { if (m[1]) cifrasDeFrase(m[1], datos.cifras); datos.autor = m[2]; datos.texto = m[3]; }
        else {
          /* otra forma: las cifras solo del trozo de antes del primer « - », nunca del pie */
          const partes = descripcion.split(/\s+-\s+/);
          if (partes.length > 1 && !/[:"“«]/.test(partes[0])) {
            cifrasDeFrase(partes[0], datos.cifras);
            descripcion = partes.slice(1).join(' - ');
          }
        }
      }
      /* 2) Con un código en la barra, el reel que SE VE rellena lo que falte: el vídeo que cruza
         la mitad de la pantalla y su caja, la primera que trae el botón de comentar. Si la caja
         enlaza a otros posts y a este no, es la de otro. Lo que está en la lista de comentarios
         (li, ul) no cuenta: es de otras personas. */
      const fueraDeComentarios = e => !e.closest('li, ul');
      const BOTONES = ['Comentario', 'Comment', 'Comentar'].map(x => `svg[aria-label="${x}"]`).join(', ');
      const codigosEn = c => [...c.querySelectorAll('a[href]')].map(a => ((a.getAttribute('href') || '').match(/\/(?:reels?|p|tv)\/(?!audio\/)([A-Za-z0-9_-]+)/) || [])[1]).filter(Boolean);
      if (codigoIg) {
        caja = cajaDelVideoQueSeVe(BOTONES, c => [...c.querySelectorAll(BOTONES)].some(fueraDeComentarios));
        if (caja) { const cs = codigosEn(caja); if (cs.length && !cs.includes(codigoIg)) caja = null; }
      }
      if (caja) {
        if (!ogVale) datos.lector = 'instagram-reel';
        /* los perfiles a los que enlaza la caja (el autor y, si los hay fuera de li, quien comenta) */
        const perfiles = [...caja.querySelectorAll('a')].filter(fueraDeComentarios).map(a => {
          const u = limpio(a.innerText);
          const r = (a.getAttribute('href') || '').replace(/^https?:\/\/[^/]+/, '');
          return /^[A-Za-z0-9._]{2,30}$/.test(u) && (r + '/').startsWith('/' + u + '/') ? u : '';
        }).filter(Boolean);
        const distintos = [...new Set(perfiles)];
        if (!datos.autor && distintos.length) datos.autor = distintos[0];
        /* el pie: solo si nadie más escribe en la caja (con dos perfiles, uno es un comentario) */
        if (!datos.texto && distintos.length <= 1) {
          const BOTON = /^(seguir|siguiendo|follow|following|más|more|…\s*más|… more|ver traducción|see translation|audio original|original audio)$/i;
          datos.texto = [...caja.querySelectorAll('[dir="auto"], h1')].filter(fueraDeComentarios)
            .filter(e => !e.closest('a[href*="/audio/"], a[href*="/explore/locations/"]'))
            .map(e => e.innerText || '')
            .filter(x => limpio(x) && limpio(x) !== datos.autor && !BOTON.test(limpio(x)) && !/(audio original|original audio)/i.test(x))
            .sort((x, y) => y.length - x.length)[0] || '';
        }
        /* la cifra de cada botón es el primer hermano que sea SOLO un número (así no se cuela lo que
           pinta vidIQ al lado, «1.4K VPH»); se para en el botón siguiente o en la hora («5m») */
        const cuenta = (...nombres) => {
          let n = [...caja.querySelectorAll(nombres.map(x => `svg[aria-label="${x}"]`).join(','))].filter(fueraDeComentarios)
            .sort((x, y) => y.getBoundingClientRect().height - x.getBoundingClientRect().height)[0];
          for (let i = 0; n && n !== caja && i < 6; i++, n = n.parentElement) {
            for (let h = n.nextElementSibling; h; h = h.nextElementSibling) {
              const v = limpio(h.innerText);
              if (SOLO.test(v)) return v;
              if (h.querySelector('svg[aria-label]')) break;
              if (h.matches('time') || h.querySelector('time')) break;
            }
          }
          return '';
        };
        datos.cifras.me_gusta = datos.cifras.me_gusta || cuenta('Me gusta', 'Like', 'Ya no me gusta', 'Unlike');
        datos.cifras.comentarios = datos.cifras.comentarios || cuenta('Comentario', 'Comment', 'Comentar');
        datos.cifras.compartidos = datos.cifras.compartidos || cuenta('Compartir', 'Share');
        for (const el of caja.querySelectorAll('span, a')) {
          if (!fueraDeComentarios(el)) continue;
          const t = limpio(el.innerText);
          if (t.length < 40 && /\d/.test(t) && /\b(reproducciones|visualizaciones|views|plays)\b/i.test(t)) { cifrasDeFrase(t, datos.cifras); break; }
        }
        if (!ogVale && datos.autor) datos.titulo = `Reel de @${datos.autor}`;
      } else if (!ogVale) datos.titulo = 'Instagram';
    } else if (red === 'tiktok') {
      const idVideo = (location.pathname.match(/\/video\/(\d+)/) || [])[1] || '';
      const CUENTAS = '[data-e2e="browse-like-count"], [data-e2e="like-count"]';
      if (idVideo) {
        /* la página (o la ventana) de UN vídeo: su caja es la que lleva su descripción y sus cifras */
        let c = document.querySelector('[data-e2e="browse-video-desc"], [data-e2e="browse-username"], [data-e2e="video-desc"]');
        while (c && c !== document.documentElement && !c.querySelector(CUENTAS)) c = c.parentElement;
        caja = c && c !== document.documentElement ? c : null;
      }
      /* el reproductor nuevo (medido el 12-11 en el inicio): UNA sola capa con las cifras y la
         descripción del vídeo que suena, aparte de la lista de vídeos */
      const capas = document.querySelectorAll('[data-e2e="anchoring-chrome-host"]');
      if (!caja && capas.length === 1 && capas[0].querySelector(CUENTAS)) caja = capas[0];
      if (!caja && esMuro) {
        /* «Para ti» de antes: la barra no cambia; vale el vídeo que se ve, y su enlace si lo trae */
        caja = cajaDelVideoQueSeVe(CUENTAS);
        const enlace = caja && caja.querySelector('a[href*="/video/"]');
        if (enlace) datos.url = enlace.href;
      }
      if (caja) {
        datos.autor = cortoEn(caja, '[data-e2e="browse-username"]', '[data-e2e="video-author-uniqueid"]');
        if (!datos.autor) {
          const foto = caja.querySelector('[data-e2e="video-author-avatar"]');
          const a = foto && foto.closest('a[href]');
          datos.autor = ((a && a.getAttribute('href')) || '').match(/^\/@([A-Za-z0-9._]+)/)?.[1] || '';
        }
        datos.texto = textoEn(caja, '[data-e2e="browse-video-desc"]', '[data-e2e="video-desc"]');
        datos.cifras.me_gusta = numeroEn(caja, '[data-e2e="browse-like-count"]', '[data-e2e="like-count"]');
        datos.cifras.comentarios = numeroEn(caja, '[data-e2e="browse-comment-count"]', '[data-e2e="comment-count"]');
        datos.cifras.compartidos = numeroEn(caja, '[data-e2e="share-count"]');
        datos.cifras.guardados = numeroEn(caja, '[data-e2e="browse-favorite-count"]', '[data-e2e="undefined-count"]', '[data-e2e="favorite-count"]');
      }
      /* las vistas: TikTok no las enseña en el vídeo; solo en la miniatura que enlaza a ESTE vídeo */
      if (idVideo) {
        for (const a of document.querySelectorAll(`a[href*="/video/${idVideo}"]`)) {
          if (!new RegExp('/video/' + idVideo + '(?:\\D|$)').test(a.getAttribute('href') || '')) continue;
          const v = numeroEn(a, '[data-e2e="video-views"]');
          if (v) { datos.cifras.vistas = v; break; }
        }
      }
    } else if (red === 'youtube') {
      /* el vídeo de la barra: en /watch, su página (ytd-watch-flexy con su id y a la vista); en un
         Short, el que enlaza a su id. Nunca toda la página: una página oculta de otro vídeo (al volver
         a la portada) o un Short visto antes siguen dentro con sus cifras. */
      const short = location.pathname.startsWith('/shorts/');
      if (vid && !short) caja = document.querySelector(`ytd-watch-flexy[video-id="${vid}"]:not([hidden])`);
      if (vid && short) {
        const reels = [...document.querySelectorAll('ytd-shorts:not([hidden]) ytd-reel-video-renderer')];
        caja = reels.find(r => [...r.querySelectorAll('a[href*="/shorts/"]')].some(a => (a.getAttribute('href') || '').includes('/shorts/' + vid)))
          || reels.find(r => r.hasAttribute('is-active') && enMedio(r)) || null;
      }
      if (!ogVale) datos.imagen = vid ? `https://i.ytimg.com/vi/${vid}/hqdefault.jpg` : '';
      if (!ogVale) datos.titulo = limpio(document.title).replace(/^\(\d+\)\s*/, '').replace(/\s*-\s*YouTube$/, '');
      if (caja) {
        datos.titulo = cortoEn(caja, 'h1.ytd-watch-metadata', 'ytd-watch-metadata #title h1', 'yt-shorts-video-title-view-model h1',
          'h2.ytShortsVideoTitleViewModelShortsVideoTitle') || datos.titulo;
        datos.autor = cortoEn(caja, '#owner #channel-name a', 'ytd-watch-metadata ytd-channel-name a', '.ytReelChannelBarViewModelChannelName',
          'ytd-channel-name a');
        /* la descripción: el desplegable de debajo del vídeo (no «#description», que también es un dibujo) */
        const desc = unoEn(caja, 'ytd-watch-metadata ytd-text-inline-expander #attributed-snippet-text',
          'ytd-watch-metadata #description-inline-expander', 'ytd-text-inline-expander #attributed-snippet-text');
        datos.texto = largo(textoDe(desc)).replace(/\s*…\s*más\s*$/i, '');
        /* las vistas: el contador gira («1 2 3 4…»); su etiqueta («230 M de vistas») es lo que vale */
        const contador = caja.querySelector('#view-count');
        const vistas = (contador && contador.getAttribute('aria-label')) || (ogVale ? meta('interactionCount') : '')
          || cortoEn(caja, 'ytd-watch-info-text #info');   // «1836 M de vistas  hace 17 años» (medido el 12-11)
        if (vistas && /\d/.test(vistas)) datos.cifras.vistas = /^\d+$/.test(limpio(vistas)) ? limpio(vistas) : (cifrasDeFrase(vistas, {}).vistas || '');
        /* los me gusta: la etiqueta («al igual que 19,501,189 personas más») es el número exacto;
           si no lo trae, el trozo del botón que es solo un número */
        const gusta = caja.querySelector('like-button-view-model button, #like-button button');
        if (gusta) datos.cifras.me_gusta = numeroDeFrase(gusta.getAttribute('aria-label')) || soloNumero(gusta.closest('like-button-view-model') || gusta);
        /* los comentarios: en /watch, la cabecera de los comentarios; en un Short, su botón */
        if (short) {
          const b = caja.querySelector('#comments-button button[aria-label], button[aria-label*="comentario"], button[aria-label*="comment"]');
          datos.cifras.comentarios = (b && numeroDeFrase(b.getAttribute('aria-label'))) || soloNumero(caja.querySelector('#comments-button'));
        } else {
          datos.cifras.comentarios = numeroDeFrase(cortoEn(caja, 'ytd-comments-header-renderer #count'));
        }
      }
    } else if (red === 'x') {
      /* el tuit de la barra: el artículo que enlaza a su propio /status/ID (su hora), sin contar los
         tuits citados (van dentro de un div[role=link]) */
      const id = (location.pathname.match(/\/status\/(\d+)/) || [])[1] || '';
      const deEsteId = new RegExp('/status/' + id + '(?:[/?#]|$)');
      if (id) {
        caja = [...document.querySelectorAll('article[data-testid="tweet"]')].find(art => [...art.querySelectorAll('a[href*="/status/"]')]
          .some(a => deEsteId.test(a.getAttribute('href') || '') && !(a.parentElement && art.contains(a.parentElement.closest('div[role="link"]'))))) || null;
      }
      if (caja) {
        const art = caja;
        const fueraDeCita = el => { const q = el.closest('div[role="link"]'); return !q || !art.contains(q); };
        const primero = s => [...art.querySelectorAll(s)].find(fueraDeCita);
        datos.texto = largo(textoDe(primero('[data-testid="tweetText"]')));
        const nombre = limpio(textoDe(primero('[data-testid="User-Name"]')));
        const arroba = nombre.match(/@([A-Za-z0-9_]+)/);
        datos.autor = arroba ? arroba[1] : nombre;
        const grupo = primero('[role="group"][aria-label]');
        if (grupo) cifrasDeFrase(grupo.getAttribute('aria-label'), datos.cifras);
        const vistas = primero('a[href$="/analytics"]');
        if (vistas && !datos.cifras.vistas) cifrasDeFrase(vistas.getAttribute('aria-label') || vistas.innerText, datos.cifras);
      }
    } else if (red === 'linkedin') {
      /* el post de la barra: la caja que lleva su número de actividad (data-urn) */
      const act = (location.pathname.match(/(?:activity|ugcPost|share)[:-](\d+)/i) || [])[1] || '';
      if (act) caja = document.querySelector(`[data-urn$=":${act}"], [data-id$=":${act}"]`);
      if (caja) {
        datos.autor = cortoEn(caja, '.update-components-actor__title span[aria-hidden="true"]', '.update-components-actor__name', '.feed-shared-actor__name');
        datos.texto = textoEn(caja, '.update-components-text', '.feed-shared-update-v2__description', '.feed-shared-text');
        datos.cifras.me_gusta = numeroEn(caja, '.social-details-social-counts__reactions-count', '.social-details-social-counts__social-proof-fallback-number');
        const sociales = cortoEn(caja, '.social-details-social-counts');
        if (sociales) cifrasDeFrase(sociales, datos.cifras);
      }
    } else if (red === 'facebook') {
      /* solo en la página de UN post (o la ventana que lo abre): su ventana a la vista o, en su
         página, la parte principal. En el inicio no se sabe cuál es. */
      const esPost = /\/(posts|permalink|photo|photos|videos|reel|watch|story\.php|permalink\.php)(\/|\.|$|\?)/.test(location.pathname + '/');
      if (esPost) {
        caja = [...document.querySelectorAll('div[role="dialog"]')].filter(d => d.getBoundingClientRect().height > 0).pop()
          || document.querySelector('div[role="main"]');
      }
      if (caja) {
        datos.texto = textoEn(caja, '[data-ad-preview="message"]', '[data-ad-comet-preview="message"]', 'div[role="dialog"] [dir="auto"]');
        datos.autor = cortoEn(caja, 'h2 strong a', 'h2 a', 'strong a[role="link"]');
        for (const el of caja.querySelectorAll('[aria-label]')) {
          const a = el.getAttribute('aria-label') || '';
          if (a.length < 80 && /\d/.test(a) && /(reacciones|reactions|comentarios|comments|compartido|shares|reproducciones|views)/i.test(a)) cifrasDeFrase(a, datos.cifras);
        }
      }
    }
  } catch (e) {
    datos.aviso = `el lector de ${datos.red} no ha podido leer esta página; va lo genérico`;
  }

  /* lo genérico, solo con etiquetas de ESTA dirección (descripcion ya está vacía si no) */
  if (!datos.texto) datos.texto = descripcion;
  if (!datos.autor) {
    /* el primer trozo de la dirección es el autor (instagram.com/ana/, tiktok.com/@ana)
       salvo que sea una sección de la red: /reels/, /p/, /watch… no son nadie */
    const m = location.pathname.match(/^\/@?([A-Za-z0-9._-]{2,40})(?:\/|$)/);
    const SECCIONES = /^(reels?|p|tv|explore|stories|watch|shorts|feed|home|search|status|video|videos|channel|c|user|hashtag|i|in|posts|groups|pages|events|marketplace|live|music|tag|discover|foryou|following|company|school|pin|profile\.php|permalink\.php|story\.php|photo|photos|results)$/i;
    datos.autor = (ogVale ? (meta('author') || meta('twitter:creator')) : '') || (red !== 'web' && m && !SECCIONES.test(m[1]) ? m[1] : '');
  }
  if (red !== 'web' && !caja && !ogVale && !datos.aviso) {
    datos.aviso = esMuro
      ? 'en el inicio no se sabe qué post es: ábrelo (pulsa en su fecha o en él) y vuelve a enviar; va el enlace y la captura'
      : 'no se ha podido leer este post; va el enlace y la captura';
  }
  if (red !== 'web' && caja && esMuro && ruta(datos.url) === aqui && !datos.aviso) {
    datos.aviso = 'el enlace es el del inicio, no el del vídeo: si lo quieres guardar, ábrelo y vuelve a enviar';
  }
  datos.autor = limpio(datos.autor).replace(/^@/, '');
  datos.texto = largo(datos.texto).slice(0, 5000);
  for (const k of Object.keys(datos.cifras)) if (!datos.cifras[k]) delete datos.cifras[k];
  return datos;
})();

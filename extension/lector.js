/* Lee lo que se VE en la página abierta: el enlace, el título, el autor, el
 * texto del post, las cifras que enseña la red y lo que esté seleccionado.
 *
 * Se inyecta solo cuando pulsas el botón (permiso activeTab) y devuelve un
 * objeto; no guarda nada, no recorre la página ni pide nada a ningún servidor.
 * Cada red tiene su lector, y si cambia su página o no hay lector para ella,
 * queda el genérico (las etiquetas og: y meta, que llevan casi todas las webs).
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
  const uno = (...selectores) => {
    for (const s of selectores) {
      try {
        const el = document.querySelector(s);
        if (el && limpio(el.innerText || el.textContent)) return el;
      } catch (e) { /* selector que este navegador no entiende */ }
    }
    return null;
  };
  const texto = (...selectores) => { const el = uno(...selectores); return el ? largo(el.innerText || el.textContent) : ''; };
  const corto = (...selectores) => limpio(texto(...selectores));

  /* «12 respuestas, 34 reposts, 560 Me gusta, 89 mil visualizaciones» → cifras.
     Sirve para las etiquetas aria y para frases como la og:description de Instagram. */
  const PALABRAS = [
    ['vistas', /(visualizaciones|reproducciones|vistas|views|plays|visualizações)/],
    ['me_gusta', /(me gusta|likes?|reacciones|reactions|curtidas)/],
    ['comentarios', /(comentarios?|comments?|respuestas|replies)/],
    ['compartidos', /(compartid[oa]s?|veces compartido|shares?|reposts?|retweets?|republicaciones)/],
    ['guardados', /(guardad[oa]s?|bookmarks?|saves?)/],
  ];
  /* un espacio dentro del número solo si separa miles («12 345»): «1.024 38 comentarios» son dos */
  /* y el sufijo solo si es palabra entera: «12 más» o «7 mins» no son millones */
  const NUMERO = '(\\d(?:[\\d.,]|\\s(?=\\d{3}(?!\\d)))*(?:\\s*(?:mil millones|mill(?:ones|\\.)?|milh(?:ões|ão)|mil|[kmb])(?![a-záéíóúñãõç]))?)';
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
  const numeroDe = (...selectores) => { const t = corto(...selectores); return /\d/.test(t) ? t : ''; };

  const host = location.hostname.toLowerCase();
  const es = (...dominios) => dominios.some(d => host === d || host.endsWith('.' + d));
  const datos = {
    url: (document.querySelector('link[rel="canonical"]') || {}).href || meta('og:url') || location.href,
    titulo: meta('og:title') || limpio(document.title),
    autor: '', texto: '', imagen: meta('og:image'),
    seleccion: largo(String(window.getSelection ? window.getSelection() : '')),
    cifras: {}, red: 'web', lector: 'generico',
  };
  /* el canónico de algunas webs es la portada: si no se parece a donde estás, se usa la barra */
  try {
    const canon = new URL(datos.url, location.href);
    if (canon.hostname !== location.hostname || canon.pathname === '/' && location.pathname !== '/') datos.url = location.href;
  } catch (e) { datos.url = location.href; }
  let descripcion = meta('og:description') || meta('description');
  /* TikTok y X tampoco recargan al pasar de un post a otro: si su og:url es de otra
     dirección, sus etiquetas son las del primero que se abrió y no valen (11-11-2026) */
  if (es('tiktok.com', 'x.com', 'twitter.com') && meta('og:url')) {
    try {
      const deOg = new URL(meta('og:url')).pathname.replace(/\/$/, '');
      if (deOg && deOg !== location.pathname.replace(/\/$/, '')) {
        descripcion = ''; datos.imagen = ''; datos.url = location.href; datos.titulo = limpio(document.title);
      }
    } catch (e) { /* una og:url rara: se deja como está */ }
  }

  try {
    if (es('instagram.com')) {
      datos.red = 'instagram'; datos.lector = 'instagram';
      /* Instagram es una página que no se recarga al pasar de un reel a otro: la
         barra cambia, pero las etiquetas og: siguen siendo las del PRIMER reel que se
         abrió. Solo se fían si nombran el mismo código que la barra (11-11-2026). */
      const codigo = (location.pathname.match(/\/(?:reels?|p|tv)\/([A-Za-z0-9_-]+)/) || [])[1] || '';
      const ogUrl = meta('og:url');
      const ogDeEsta = !codigo || !ogUrl || new RegExp('/' + codigo + '(?:/|$|\\?)').test(ogUrl);
      if (!ogDeEsta) { datos.titulo = 'Instagram'; datos.imagen = ''; datos.url = location.href; descripcion = ''; }
      /* 1) Las etiquetas og: de ESTE post mandan: «1.234 Me gusta, 56 comentarios - usuario
         el 3 de octubre: "texto"», en inglés «… - usuario on October 3, 2026: "text"», y a
         veces sin las cifras: «usuario el November 4, 2026: "texto"». */
      if (ogDeEsta) {
        const m = descripcion.match(/^(?:(.*?)\s+-\s+)?([A-Za-z0-9._]+)\s+(?:el|on)\s+[^:]+:\s*["“«]?([\s\S]*?)["”»]?\.?$/);
        if (m) { if (m[1]) cifrasDeFrase(m[1], datos.cifras); datos.autor = m[2]; datos.texto = m[3]; }
        else cifrasDeFrase(descripcion, datos.cifras);
      }
      /* 2) El reel que se VE rellena lo que falte: el vídeo que cruza la mitad de la
         pantalla, y su caja la primera que trae el botón de comentar. Nada de lo que
         está dentro de la lista de comentarios (li) cuenta: sus corazones y textos son
         de otras personas. */
      const enMedio = e => { const r = e.getBoundingClientRect(); return r.height > 0 && r.top < innerHeight / 2 && r.bottom > innerHeight / 2; };
      const fueraDeComentarios = e => !e.closest('li, ul');
      const BOTONES = ['Comentario', 'Comment', 'Comentar'].map(x => `svg[aria-label="${x}"]`).join(', ');
      let caja = [...document.querySelectorAll('video')].find(enMedio) || null;
      while (caja && ![...caja.querySelectorAll(BOTONES)].some(fueraDeComentarios)) caja = caja.parentElement;
      const hayCaja = !!caja && caja !== document.body && caja !== document.documentElement;
      if (hayCaja) {
        datos.lector = ogDeEsta ? 'instagram' : 'instagram-reel';
        /* el autor: el enlace que lleva a su propio perfil (/usuario/ o /usuario/reels/) */
        const enlace = [...caja.querySelectorAll('a')].filter(fueraDeComentarios).find(a => {
          const u = limpio(a.innerText);
          const ruta = (a.getAttribute('href') || '').replace(/^https?:\/\/[^/]+/, '');
          return /^[A-Za-z0-9._]{2,30}$/.test(u) && (ruta + '/').startsWith('/' + u + '/');
        });
        if (!datos.autor && enlace) datos.autor = limpio(enlace.innerText);
        if (!datos.texto) {
          datos.texto = [...caja.querySelectorAll('[dir="auto"], h1')].filter(fueraDeComentarios).map(e => e.innerText || '')
            .filter(x => limpio(x) && limpio(x) !== datos.autor && !/(audio original|original audio)/i.test(x))
            .sort((x, y) => y.length - x.length)[0] || '';
        }
        /* la cifra de cada botón es el primer hermano que sea SOLO un número: así no se
           cuela lo que otras extensiones (vidIQ: «1.4K VPH») pintan al lado; y se para al
           llegar al botón siguiente */
        const SOLO = /^\d[\d.,]*\s*(?:mil millones|mill(?:ones|\.)?|mil|[kmb])?$/i;
        const cuenta = (...nombres) => {
          /* el botón del reel es el corazón GRANDE: los de los comentarios son más pequeños */
          let n = [...caja.querySelectorAll(nombres.map(x => `svg[aria-label="${x}"]`).join(','))].filter(fueraDeComentarios)
            .sort((x, y) => y.getBoundingClientRect().height - x.getBoundingClientRect().height)[0];
          for (let i = 0; n && n !== caja && i < 6; i++, n = n.parentElement) {
            for (let h = n.nextElementSibling; h; h = h.nextElementSibling) {
              const v = limpio(h.innerText);
              if (SOLO.test(v)) return v;
              if (h.querySelector('svg[aria-label]')) break;
              if (h.matches('time') || h.querySelector('time')) break;   // «5m» es la hora, no 5 millones
            }
          }
          return '';
        };
        datos.cifras.me_gusta = datos.cifras.me_gusta || cuenta('Me gusta', 'Like', 'Ya no me gusta', 'Unlike');
        datos.cifras.comentarios = datos.cifras.comentarios || cuenta('Comentario', 'Comment', 'Comentar');
        datos.cifras.compartidos = datos.cifras.compartidos || cuenta('Compartir', 'Share');
        if (!ogDeEsta && datos.autor) datos.titulo = `Reel de @${datos.autor}`;
      } else if (!ogDeEsta) {
        datos.aviso = 'no se ha podido leer este reel; va el enlace y la captura';
      }
      if (ogDeEsta) {
        datos.texto = datos.texto || texto('article h1', 'article ._a9zs', 'h1');
        datos.autor = datos.autor || corto('article header a[role="link"]', 'header h2', 'header a');
      }
      /* las vistas: en la caja del reel que se ve, o en la página si es la de este post */
      const dondeVistas = hayCaja ? caja : (ogDeEsta ? document : null);
      if (dondeVistas) {
        for (const el of dondeVistas.querySelectorAll('span, a')) {
          if (!fueraDeComentarios(el)) continue;
          const t = limpio(el.innerText);
          if (t.length < 40 && /\d/.test(t) && /(reproducciones|visualizaciones|views|plays)/i.test(t)) { cifrasDeFrase(t, datos.cifras); break; }
        }
      }
    } else if (es('tiktok.com')) {
      datos.red = 'tiktok'; datos.lector = 'tiktok';
      datos.autor = corto('[data-e2e="browse-username"]', '[data-e2e="video-author-uniqueid"]', 'h3[data-e2e="video-author-uniqueid"]');
      datos.texto = texto('[data-e2e="browse-video-desc"]', '[data-e2e="video-desc"]', 'h1[data-e2e="video-desc"]');
      datos.cifras.me_gusta = numeroDe('[data-e2e="browse-like-count"]', '[data-e2e="like-count"]');
      datos.cifras.comentarios = numeroDe('[data-e2e="browse-comment-count"]', '[data-e2e="comment-count"]');
      datos.cifras.compartidos = numeroDe('[data-e2e="share-count"]');
      datos.cifras.guardados = numeroDe('[data-e2e="undefined-count"]', '[data-e2e="favorite-count"]');
      datos.cifras.vistas = numeroDe('[data-e2e="video-views"]');
    } else if (es('youtube.com', 'youtu.be')) {
      datos.red = 'youtube'; datos.lector = 'youtube';
      /* YouTube tampoco recarga al pasar de un vídeo a otro: las etiquetas meta/og: son
         las del PRIMER vídeo que se abrió en la pestaña (y en la portada o la búsqueda, ni
         existen). Solo se fían si nombran el mismo vídeo que la barra (11-11-2026). */
      const corto_ = location.pathname.startsWith('/shorts/');
      const vid = new URLSearchParams(location.search).get('v') || (location.pathname.match(/^\/shorts\/([A-Za-z0-9_-]+)/) || [])[1] || '';
      const ogUrl = meta('og:url');
      const deEste = !!vid && ogUrl.includes(vid);
      if (!deEste) {
        descripcion = '';
        datos.url = location.href;
        datos.imagen = vid ? `https://i.ytimg.com/vi/${vid}/hqdefault.jpg` : '';
        datos.titulo = limpio(document.title).replace(/^\(\d+\)\s*/, '').replace(/\s*-\s*YouTube$/, '');
      }
      const activo = corto_ ? (document.querySelector('ytd-reel-video-renderer[is-active]') || document) : document;
      const en = (...s) => { for (const x of s) { const el = activo.querySelector(x); if (el && limpio(el.innerText)) return limpio(el.innerText); } return ''; };
      datos.titulo = en('h1.ytd-watch-metadata', 'ytd-watch-metadata #title h1', 'h2.ytShortsVideoTitleViewModelShortsVideoTitle') || datos.titulo;
      datos.autor = en('#owner #channel-name a', 'ytd-watch-metadata ytd-channel-name a', '.ytReelChannelBarViewModelChannelName');
      /* la descripción: el texto del desplegable de debajo del vídeo (no «#description»,
         que también es el id de un dibujo de la página) */
      const desc = activo.querySelector('ytd-watch-metadata ytd-text-inline-expander #attributed-snippet-text, '
        + 'ytd-watch-metadata #description-inline-expander, ytd-text-inline-expander #attributed-snippet-text');
      datos.texto = largo((desc || {}).innerText || (desc || {}).textContent || '').replace(/\s*…\s*más\s*$/i, '') || descripcion;
      /* las vistas: el contador de debajo del vídeo se dibuja con cifras que giran («1 2 3 4…»):
         su etiqueta para lectores de pantalla («230 M de vistas») es lo que vale */
      const contador = activo.querySelector('#view-count');
      const vistas = (contador && contador.getAttribute('aria-label')) || (deEste ? meta('interactionCount') : '') || en('ytd-watch-info-text #info span');
      if (vistas && /\d/.test(vistas)) datos.cifras.vistas = /^\d+$/.test(limpio(vistas)) ? limpio(vistas) : (cifrasDeFrase(vistas, {}).vistas || '');
      const gusta = activo.querySelector('like-button-view-model button, #like-button button, button[aria-label*="gusta"], button[aria-label*="like"]');
      if (gusta) {
        /* el número se ve en el botón («1,2 K»); si no, va en su etiqueta («…junto con 1.234 personas») */
        const visto = limpio(gusta.innerText);
        const etiqueta = (gusta.getAttribute('aria-label') || '').match(/\d[\d.,]*(?:\s*(?:mil|k|m)\b)?/i);
        datos.cifras.me_gusta = /\d/.test(visto) ? visto : (etiqueta ? limpio(etiqueta[0]) : '');
      }
      /* los comentarios: solo el número («23.133 Comentarios» → «23.133») */
      const comentarios = en('ytd-comments-header-renderer #count', '#comments-button .yt-spec-button-shape-with-label__label');
      const n = comentarios.match(new RegExp(NUMERO, 'i'));
      if (n && /\d/.test(n[1])) datos.cifras.comentarios = datos.cifras.comentarios || limpio(n[1]);
    } else if (es('x.com', 'twitter.com')) {
      datos.red = 'x'; datos.lector = 'x';
      const tuit = document.querySelector('article[data-testid="tweet"][tabindex="-1"]') || document.querySelector('article[data-testid="tweet"]');
      if (tuit) {
        datos.texto = largo((tuit.querySelector('[data-testid="tweetText"]') || {}).innerText || '');
        const nombre = limpio((tuit.querySelector('[data-testid="User-Name"]') || {}).innerText || '');
        const arroba = nombre.match(/@([A-Za-z0-9_]+)/);
        datos.autor = arroba ? arroba[1] : nombre;
        const grupo = tuit.querySelector('[role="group"][aria-label]');
        if (grupo) cifrasDeFrase(grupo.getAttribute('aria-label'), datos.cifras);
        const vistas = tuit.querySelector('a[href$="/analytics"]');
        if (vistas && !datos.cifras.vistas) cifrasDeFrase(vistas.getAttribute('aria-label') || vistas.innerText, datos.cifras);
      }
    } else if (es('linkedin.com')) {
      datos.red = 'linkedin'; datos.lector = 'linkedin';
      datos.autor = corto('.update-components-actor__title span[aria-hidden="true"]', '.update-components-actor__name', '.feed-shared-actor__name');
      datos.texto = texto('.update-components-text', '.feed-shared-update-v2__description', '.feed-shared-text') || descripcion;
      datos.cifras.me_gusta = numeroDe('.social-details-social-counts__reactions-count', '.social-details-social-counts__social-proof-fallback-number');
      const sociales = corto('.social-details-social-counts');
      if (sociales) cifrasDeFrase(sociales, datos.cifras);
    } else if (es('facebook.com', 'fb.watch')) {
      datos.red = 'facebook'; datos.lector = 'facebook';
      datos.texto = texto('[data-ad-preview="message"]', '[data-ad-comet-preview="message"]', 'div[role="dialog"] [dir="auto"]') || descripcion;
      datos.autor = corto('h2 strong a', 'h2 a', 'strong a[role="link"]');
      for (const el of document.querySelectorAll('[aria-label]')) {
        const a = el.getAttribute('aria-label') || '';
        if (a.length < 80 && /\d/.test(a) && /(reacciones|reactions|comentarios|comments|compartido|shares|reproducciones|views)/i.test(a)) cifrasDeFrase(a, datos.cifras);
      }
      if (!Object.values(datos.cifras).some(Boolean)) cifrasDeFrase(descripcion, datos.cifras);
    } else if (es('threads.net', 'threads.com')) {
      datos.red = 'threads'; datos.lector = 'generico';
    } else if (/(^|\.)pinterest\.([a-z]{2,3}|com?\.[a-z]{2})$/.test(host)) {
      datos.red = 'pinterest'; datos.lector = 'generico';
    }
  } catch (e) {
    datos.aviso = `el lector de ${datos.red} no ha podido leer esta página (${e.message}); va lo genérico`;
  }

  /* lo genérico, para lo que el lector de la red no haya llenado (en Instagram, la
     descripción ya se ha vaciado si era la de otro reel) */
  if (!datos.texto) datos.texto = descripcion;
  if (!datos.autor) {
    /* el primer trozo de la dirección es el autor (instagram.com/ana/, tiktok.com/@ana)
       salvo que sea una sección de la red: /reels/, /p/, /watch… no son nadie */
    const m = location.pathname.match(/^\/@?([A-Za-z0-9._-]{2,40})(?:\/|$)/);
    const SECCIONES = /^(reels?|p|tv|explore|stories|watch|shorts|feed|home|search|status|video|videos|channel|c|user|hashtag|i|in|posts|groups|pages|events|marketplace|live|music|tag|discover|foryou|following|company|school|pin|profile\.php)$/i;
    datos.autor = meta('author') || meta('twitter:creator') || (datos.red !== 'web' && m && !SECCIONES.test(m[1]) ? m[1] : '');
  }
  datos.autor = limpio(datos.autor).replace(/^@/, '');
  datos.texto = largo(datos.texto).slice(0, 5000);
  for (const k of Object.keys(datos.cifras)) if (!datos.cifras[k]) delete datos.cifras[k];
  return datos;
})();

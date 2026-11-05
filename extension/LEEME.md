# Enviar a CrearIA Studio (extensión de Chrome)

Un botón para mandar al Studio el post que estás viendo: el enlace, el texto,
las cifras que se ven y una captura. Llega a **Automatizar → Recibidos de
Chrome**.

## Instalarla

1. En el Studio, **Configuración → Enviar al Studio → Descargar la extensión**.
   Descomprime el ZIP en una carpeta que no vayas a borrar.
2. En el mismo sitio, copia **la dirección de tu Studio** y pulsa **Crear el
   código de envío** (se ve una sola vez: cópialo).
3. En Chrome abre `chrome://extensions`, activa **Modo de desarrollador** y pulsa
   **Cargar descomprimida**. Elige la carpeta del paso 1.
4. Fija el botón (pieza de puzle → chincheta), ábrelo, pega la dirección y el
   código y pulsa **Probar**. Chrome te pedirá permiso para hablar con tu
   Studio: acéptalo.

## Usarla

Abre un post (mejor en su página, no en el muro), selecciona si quieres un
trozo de texto, pulsa el botón, escribe una nota si quieres y **Enviar al
Studio**. Si tu Studio pide iniciar sesión, ábrelo en otra pestaña de ese
Chrome, entra y vuelve a pulsar.

## Qué hace y qué no

- Lee solo la pestaña que tienes delante y solo cuando pulsas (permiso
  `activeTab`). No recorre perfiles ni pide nada a ninguna red.
- Guarda la dirección y el código en este Chrome (`chrome.storage.local`).
- Si una red cambia su página y no lee bien las cifras, va lo genérico: el
  título, la descripción, el enlace y la captura.

## Para quien la toque

- `lector.js` lee la página (un lector por red y uno genérico). Las cifras van
  como se ven («1,2 mil»): las convierte el Studio (`pasos/recibidos.py`).
- `popup.js` manda a `<Studio>/api/recibidos` con la cabecera
  `X-Estudio-Envio`. Si la petición no lleva la sesión del login, la repite
  desde una pestaña del Studio abierta.
- Las pruebas: `pasos/prueba_recibidos.py` (el lector, en Chromium, con páginas
  de cada red).

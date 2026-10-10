# Cómo se usa Automatización Contenido Studio

Una guía para quien entra por primera vez: qué es cada pantalla, qué hace cada
campo y qué cuesta cada botón. Se ve en **Configuración → Cómo se usa** (o con
el botón **?** de arriba) y el asistente la lee: si tienes una duda concreta,
pregúntale en la burbuja de abajo a la derecha.

---

## La idea en una frase

Primero se crea un **estilo** (cómo se ve, cómo se cuenta y cómo suena un
canal). Después, con ese estilo, cada **vídeo** pasa por cuatro pantallas, en
este orden: **Encargo → Guion → Imágenes → Vídeo**. La barra de abajo te lleva
de una a otra.

## Lo que cuesta dinero y lo que no

- **Cuesta**: las imágenes (OpenAI) y la voz (Cartesia). Un vídeo de cuatro
  minutos son unas 126 imágenes y ~4,4 $ en calidad baja.
- **No cuesta** (va con tu suscripción de Claude): escribir el guion, la guía
  del estilo, los rótulos y el asistente.
- **Es gratis**: montar el vídeo, cambiar la música, los subtítulos o los
  efectos. Rehace el montaje, no las imágenes.
- Antes de cada botón que gasta se enseña cuánto va a costar.

## Proyectos (clientes)

Arriba de la primera pantalla está la barra de **Proyectos**: una carpeta por
cliente para tener sus estilos y vídeos separados.

- **+ Proyecto** crea uno y lo abre: los estilos que crees con él abierto
  quedan dentro, y los vídeos van con su estilo.
- Con un proyecto abierto: **Renombrar**, **Ocultar** (no sale en la lista
  hasta pulsar «Ver ocultos»), **Poner clave** (se pide para ver sus estilos y
  vídeos) y **Borrar** (sus estilos y vídeos no se borran: quedan sin proyecto).
- **Todos** enseña lo que no está oculto ni con clave; **Sin proyecto**, lo que
  no está en ninguno.
- Para mover un estilo de proyecto: menú **⋯** de su tarjeta → **Proyecto**.
- La clave y ocultar son privacidad de pantalla; la seguridad de verdad es la
  contraseña de acceso al Estudio.

En **Tus vídeos**, cada vídeo dice de qué estilo (🎨) y de qué proyecto (📁)
salió.

## Estilos

La primera pantalla. Cada tarjeta es un estilo; **Un estilo nuevo** crea otro.

### Un estilo nuevo

- **Nombre**: la etiqueta del estilo. Se cambia luego sin regenerar nada.
- **Estilo gráfico → Imágenes de referencia**: hasta 50 imágenes que ya tengan
  el aspecto que quieres. Es lo más importante del estilo: la guía se escribe
  mirándolas. Arrástralas o pulsa la zona para buscarlas.
  - Pulsa una miniatura para verla **en grande** (con ← y → pasas a la
    siguiente).
  - **Describir las imágenes (opcional)**: una frase por imagen para decir qué
    mirar en ella («la luz de esta», «solo el mueble, no el fondo»).
  - **★**: marca las que deben servir sí o sí para dibujar las láminas. La guía
    del estilo mira las 50, pero las láminas se dibujan con una hoja de 8 como
    mucho: primero las marcadas, luego las descritas y el resto repartidas.
- **Indicaciones (opcional)**: lo que las imágenes no dicen solas («igual pero
  más frío», «sin personas»).
- **Tono del guion**: cómo se cuenta (no de qué). Cuanto más concreto, mejor.
  El botón **Guía** al lado del título da una plantilla y un ejemplo, y
  **✓ Revisar** comprueba lo que has escrito contra esa guía: dice si sirve,
  qué falla y por qué, y propone una versión que puedes poner con un botón.
  Está en todos los campos que tienen guía y no cuesta imágenes.
- **Ritmo**: cada cuánto cambia de plano el vídeo. Más rápido = más imágenes =
  más caro.
- **Voz**: describe cómo quieres que suene. Debajo, la lista de voces: cada una
  tiene **▶** para oírla sin elegirla, y un buscador. Si eliges una, esa es la
  voz y la descripción solo pone la velocidad y el color; si no, la elige el
  sistema por la descripción. **Tu voz clonada**: clónala en play.cartesia.ai
  (Voices → Clone Voice) con la misma cuenta cuya clave pusiste en
  Configuración, y pulsa **Buscar mis voces otra vez**: sale la primera.
- **Idioma**: el del guion y la voz.
- **Generar**: crea el estilo (unos minutos y unas pocas imágenes de muestra).

Si la creación se corta a medias verás **Retomar** y **Empezar de cero**:

- **Retomar** sigue por donde iba y no vuelve a pagar lo que ya salió bien.
- **Empezar de cero** olvida ese intento y lo genera todo otra vez (se vuelve a
  pagar). Úsalo solo si cambiaste algo y quieres partir limpio.

### La ficha de un estilo

Al abrir un estilo ves sus muestras y cada parte (estilo gráfico, tono, voz).

- **Las muestras de arriba** son tus láminas con un **texto de ejemplo** encima
  («10.000.000 cuentas a la venta», «La nómina entera»…). Ese texto lo pone el
  Estudio para que veas cómo quedan una cartela y un subtítulo sobre tu estilo:
  es siempre el mismo, no sale de tus imágenes y nunca va al generador.

#### Qué es una lámina (y qué son «las 8 de la hoja»)

Tus imágenes de referencia **no viajan a cada plano**. Se usan para dos cosas:

1. **Escribir la guía del estilo**: la IA las mira **todas** (hasta 50) y
   describe por escrito cómo se dibuja tu canal.
2. **Dibujar las láminas**: con esa guía y una **hoja de hasta 8 de tus
   imágenes** (las ★ primero), la IA dibuja en tu estilo unas láminas: una cara,
   varias personas, un interior, un exterior, un objeto y un diagrama.

Cada plano de cada vídeo recibe **esas láminas** (hasta 8) como referencia y
copia de ellas el trazo, la paleta y la luz. Son lo que da consistencia a tus
vídeos. Cada lámina es una referencia más para cada plano, pero no cada imagen
tuya: tus imágenes llegan a los planos a través de la guía y de las láminas.

En **Las láminas de tu estilo** las ves limpias, con lo que enseña cada una:

- **Regenerar**: la vuelve a dibujar (una imagen, ≈ el precio que pone), con
  una corrección opcional («sin sombras duras»).
- **Cambiar qué enseña**: que enseñe otra cosa («una cocina de noche con luz
  cálida»). Se guarda con el estilo y se respeta al regenerarlo.
- **Quitar**: sale de la hoja (gratis; su imagen se guarda y **Devolver** no
  cuesta nada). Mínimo 3.
- **+ Añadir una lámina**: hasta 8, las que caben en la hoja de cada plano. Más
  de 8 no caben sin cambiar el motor de imágenes (reservado ahora por la Etapa
  Foto A): lo útil es que cada lámina enseñe lo que más sale en tus vídeos.
- **Con qué imágenes tuyas se dibuja cada lámina** (si subiste más de 8): las
  mismas 8 para todas, o un grupo distinto para cada una, para que cuenten
  todas tus imágenes. Mismo coste.
- Cambiar las láminas **no toca los vídeos ya creados**: lo llevan los nuevos,
  y en uno ya hecho, **Su estilo** en el Encargo te deja traerlo.

#### Tus imágenes de referencia

Debajo de las láminas están las imágenes que subiste: pulsa una para verla en
grande, escribe qué mirar en cada una y marca con ★ las que deben ir sí o sí a
la hoja de las láminas (se guarda solo y no gasta nada). **✕ Quitar** y añadir
imágenes nuevas sí rehacen la guía y las láminas al pulsar **Regenerar**.

- **Lo que se guarda solo**: el texto del tono (es la guía que lee el
  redactor, tal cual), el ritmo, el nombre, el idioma y los mandos de la voz.
  No hace falta regenerar nada: el botón de abajo dice **Guardar**.
- **Lo que pide regenerar**: imágenes nuevas o cambiar las **Indicaciones**
  del estilo gráfico (rehace la guía y las muestras), escribir en **qué le
  cambiarías** del tono o de la voz. Entonces el botón dice **Regenerar** y
  cuánto cuesta.
- **Voz**: arriba, cómo se pidió; debajo, la voz puesta en la misma lista con
  ▶ que al crear. Cambiarla ahí es inmediato y gratis. En **Opciones
  avanzadas**: velocidad, color y aire entre bloques.

## Encargo

Lo que se le pide a este vídeo. Todo se guarda solo mientras escribes.

- **El vídeo**: nombre, **duración objetivo** y **formato** (horizontal 16:9 o
  vertical 9:16). Cambiar el formato rehace todas las imágenes.
- **Qué lleva este vídeo**: interruptores de subtítulos, música y efectos.
  Cambiarlos rehace solo el montaje. Debajo, todo en automático si no tocas
  nada:
  - **Cuánto se oye la música**: Suave, Normal o Alta.
  - **Elegir la música**: busca temas por ánimo (Sobrio, Épico…), escúchalos
    ahí mismo y fija uno. **Volver a la automática** deja que el ritmo elija
    varios temas, como siempre.
  - **Personalizar los subtítulos**: tamaño, letra y forma, caja detrás del
    texto y color. **Volver a los del estilo** lo deshace.
  - **Logo**: sube una imagen (mejor PNG con fondo transparente), elige la
    esquina, el tamaño y la opacidad.
  - Nada de esto paga imágenes: la música y el logo solo vuelven a montar el
    MP4, y los subtítulos rehacen las capas de texto al montar.
- **Su estilo**: si cambiaste el estilo después de crear el vídeo, aquí ves qué
  ha cambiado y lo traes. Traer no genera nada; marca lo que habría que rehacer.
- **El material**: de dónde salen los hechos (pega el texto, notas, un
  artículo). El vídeo cuenta esto, no se inventa los datos.
- **Las indicaciones** (opcional): cómo quieres que se cuente este vídeo.
- **Las llamadas a la acción**: qué se pide al espectador (suscribirse, visitar
  una web) y dónde.
- **Generar el guion**: el siguiente paso.

## Guion

El texto que se va a locutar, por bloques.

- Escribe directamente sobre un bloque para corregirlo.
- **+ Añadir bloque** y **Partir** cambian la estructura sin renumerar nada.
- Las **pausas** se ven en cada bloque; si hay demasiadas, un aviso amarillo
  ofrece **Quitar las sobrantes**.
- **Regrabar lo que he escrito**: vuelve a grabar solo los tramos que cambiaste
  (dice cuánto cuesta antes de pulsar).
- **Regenerar el guion** lo vuelve a escribir entero (y obliga a rehacer la voz).

## Imágenes

Un plano por cada trozo del guion. Puedes mirar cada imagen, escribir qué le
cambiarías y regenerar solo esa. **Las imágenes se lanzan de una tanda en
una**: espera a que termine una antes de lanzar otra.

## Vídeo

- **Montar el vídeo** junta imágenes, voz, subtítulos, música y efectos en el MP4.
- **El repaso**: escribe notas sobre el vídeo («la música está alta», «este
  rótulo sobra») y se aplican rehaciendo solo lo que tocan.
- **Descargar** baja el MP4.

## Configuración (⚙)

- **Las claves**: OpenAI (imágenes), Cartesia (voz), Claude (guion y asistente),
  Jamendo y FreeSound (música y efectos). **Comprobar que funcionan** las prueba
  sin gastar.
- **Calidad de las imágenes**: el punto de partida de los vídeos nuevos.
- **Dictado al asistente**: con OpenAI o con el del navegador.
- **Hora de tu región**: para que el chat y los vídeos enseñen tu hora.
- **Novedades**: lo que ha cambiado en el sistema.
- **Notas de mejoras**: apunta lo que quieras corregir más adelante.

## El asistente

La burbuja de abajo a la derecha. Conoce el sistema, ve el estado de tu vídeo y
puede probar las claves. Puedes dictarle (micrófono), adjuntarle capturas y
**Ampliar** el panel para leer y escribir con más espacio. **Historial** guarda
las charlas anteriores: abre una para seguirla. Lo que escribas con la lista
delante va a la charla abierta, y **Nueva** empieza otra. El cursor vuelve solo al campo cuando contesta.

Los campos de texto de toda la aplicación crecen con lo que escribes; pasado
un alto tienen su propia barra y se pueden estirar desde la esquina.

## La música, la voz y los efectos: derechos

- **Música**: de Jamendo, con licencias Creative Commons. Cada tema guarda la
  suya; algunas piden citar al autor y otras no permiten uso comercial sin
  licencia de Jamendo. Si el vídeo es para un cliente o anuncio, revisa la
  licencia del tema.
- **Efectos**: de FreeSound, también Creative Commons (cada uno con la suya).
- **Voz**: generada con Cartesia; su uso comercial depende de tu plan de
  Cartesia. Una voz clonada solo debe ser la tuya o de quien te dé permiso.
- **Imágenes**: generadas con OpenAI; según sus condiciones de uso, lo
  generado es de quien lo pide.

## Si algo falla

1. Lee el aviso: casi siempre dice qué falta (una clave, un paso anterior).
2. Pregúntale al asistente: puede mirar el estado y los registros.
3. Si se cortó una generación, **Retomar** no vuelve a pagar lo hecho.

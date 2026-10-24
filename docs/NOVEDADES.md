# Novedades de CrearIA Studio

Lo que ha cambiado en el sistema, de lo más nuevo a lo más antiguo. Se ve en
**Configuración → Novedades**, y el asistente lo lee para estar al día.

Para actualizar el servidor: en la consola del VPS, `asvs actualizar`. Tus
vídeos, estilos, claves y contraseña no se tocan.

---

## V3.1 · octubre de 2026 (CrearIA Studio: la interfaz nueva)

**Tus notas de mejoras (24 de octubre)**
- **El asistente habla en español de Latinoamérica**: tutea, nada de
  «vosotros», «vale», «ordenador» ni «móvil».
- **Montar el vídeo aunque queden notas sin aplicar** (también las del revisor
  de imágenes): «Montar el vídeo» ya no se apaga. Pregunta antes, dice cuántas
  notas quedan y cuántas son del revisor, y las notas se quedan apuntadas para
  aplicarlas cuando quieras.
- **«✨ Más emojis» y los textos de Publicar reparten los emojis**: en el título
  y en el texto van también al principio y ENTRE palabras (justo después de la
  palabra que ilustran), no solo al final. Nunca en lugar de la palabra clave.
- **El coste del vídeo, por tipo de imagen**: planos nuevos, planos rehechos
  (notas, revisor, regenerar), la imagen base del tipo de relato con sus
  estados, las referencias del reparto y las portadas, cada una en su fila.
  Antes la imagen base y los estados se sumaban a «Personajes».
- **El corrector ya no se rompe con comillas en el guion** («comenta "BAÑO"»):
  esa era la «respuesta rota» que no se arreglaba ni con «Revisar otra vez».
- El botón «Cerrar» de un error ya no tapa el final del mensaje.


**El negocio de cada estilo (21 de octubre)**
- **Lo de EstadoPlay ya no está escrito a mano en el Studio.** Los servicios
  (consolas, simuladores, realidad virtual, karaoke) y cómo se reconocen, las
  cartas de foto con estaciones y trípodes, y lo que el revisor de imágenes
  mira del equipo («una tele sobre un mueble cuando va en su trípode», «mandos
  de otro color») son ahora el **dominio** «EstadoPlay». Hay otro de fábrica,
  **General**, para cualquier negocio.
- **Sin elegir nada, todo sale igual que antes**: si el vídeo habla de
  consolas o mandos es EstadoPlay, y si no, General. Las cartas, los prompts y
  las imágenes ya hechas no cambian.
- **Lo único que cambia sin pedirlo**: en un vídeo que no es de consolas (un
  baño, unas plantas), el revisor de imágenes ya no busca televisores, mandos
  ni trípodes; mira los objetos y el equipo de ESE vídeo.
- Un estilo puede fijar su dominio (`PUT /api/presets-light/{id}/dominio`); la
  pantalla para elegirlo llegará con la Etapa Foto C.
**Con el nuevo diseño empieza la versión 3.1.** Reúne todo lo de la V2.0 que
está debajo (imágenes, música y efectos, Publicar, la Parrilla, Analizar
cuentas y las notas del 19 de octubre) más la interfaz nueva de CrearIA Studio.

**Tus proyectos y la pantalla de un proyecto, nuevas (22 de octubre)**
- **«+ Nuevo vídeo» en Crear**, arriba en la portada y en cada proyecto: pregunta
  **¿con qué estilo?** y abre el Encargo de un vídeo nuevo (lo mismo que pulsar
  un estilo). Al lado, **+ Nuevo proyecto** y la **🗑 Papelera · N**.
- **Un buscador** que filtra vídeos, estilos y proyectos de la página.
- **⚠ Te necesitan** junta arriba lo que antes iba suelto: los vídeos que
  perdieron imágenes (**Reparar**) y los estilos a medias (**Retomar** /
  **Descartar**).
- **«Sigue donde lo dejaste»** (antes «Últimos vídeos») en tarjetas que dicen
  **cómo va cada vídeo** en Crear («✓ Montado», «⚠ Vídeo obsoleto», «● En el
  Guion», «⟳ 42 % · Dibujando los planos») y en Publicar («○ Listo para
  publicar», «◷ jue 22/10 12:00 · 4 redes», «✓ Publicado en 2 redes»), con la
  fecha legible («hoy 17:31»), **Publicar ›** si está montado y **⋯** con
  Renombrar, Mover a otro proyecto y Apartar. Se acaba el «Apartar» rojo en
  cada fila.
- **Tarjetas de proyecto** con su logo o su inicial, sus tres últimos vídeos y
  sus marcas («🔒 con clave», «oculto», «2 listos para publicar»). **Ver ocultos
  (N)** es un interruptor, y cada oculto trae su «Dejar de ocultar».
- **Dentro de un proyecto**, los mandos (nombre, logo, ocultar, clave, borrar)
  pasan a **⚙ Ajustes del proyecto**, un panel a la derecha; **Borrar el
  proyecto** queda abajo, en la zona de peligro, con su explicación.
- **Tocar un estilo abre su menú**: **▶ Nuevo vídeo con este estilo**, **✎
  Editar el estilo**, Duplicar, Mover y Apartar («✎ Editar» sigue en la
  tarjeta). **⇄ Traer un estilo de otro proyecto** es una tarjeta más.
- **Los vídeos del proyecto se filtran** por estado (Todos · En curso · Listos ·
  Programados · Publicados) y se ven en tarjetas o en lista.
- **«Apartar»** manda un vídeo o un estilo a la papelera; se puede devolver.
- Nada de esto gasta ni cambia ningún vídeo: el estado de cada tarjeta lo lee
  el Studio de lo que ya sabe (una consulta nueva de solo lectura).

**Arreglos urgentes (22 de octubre, tarde)**
- **La imagen base, también en «Imágenes».** Con un tipo de relato que edita
  («Un espacio que cambia», «Producto»), el paso Imágenes enseña ahora el
  bloque «La imagen base» mientras falte aprobar la base o la de algún estado:
  se genera, se usa la subida y se aprueba ahí mismo. El aviso de error dice
  dónde está (antes mandaba a «El espacio fijo», donde no se aprueba).
- **Los menús desplegables se leen**: la lista de opciones ya no sale en blanco
  con letra blanca (el selector de proyecto de Automatizar).

**Automatizar, con la cara nueva (22 de octubre)**
- **El proyecto, arriba como un chip**, y **«+ Añadir guiones»** siempre a
  mano. La «i» del título explica que la Parrilla es opcional.
- **Cinco pestañas que se pueden pulsar**: Parrilla · Añadir guiones ·
  Conversar con Claude · Cuentas que te gustan (antes «Analizar una cuenta») ·
  Marca del cliente. Se fueron «Ficha de un guion» y «Piloto automático», que
  estaban apagadas: el piloto sale como tarjeta «próximamente».
- **La Parrilla es un tablero**: Pendientes · Usados · Publicados, con el
  buscador y las matrices como filtro (Renombrar y Borrar preguntan en un
  panel). En el móvil, una columna con su botón.
- **La marca del cliente se ve siempre**: una línea arriba de la Parrilla
  («✓ guardada» o «Sin marca… Apuntarla ›») y un punto en su pestaña si falta.
- **La ficha de un guion se abre en un panel a la derecha** (a pantalla
  completa en el móvil) con Guion · Al Encargo · Estado, y **«Pasar al Encargo
  ›»** siempre abajo, con el estilo elegido y, si no se puede, el porqué.
- **Añadir guiones empieza por seis tarjetas** que dicen lo que cuesta cada
  camino; el botón va en la barra de abajo, con el mismo coste de siempre.
- **El chat con Claude tiene su pestaña**, con tus conversaciones a la
  izquierda. Las cuentas ya leídas salen como tarjetas y la abierta en dos
  columnas.
- Nada cambia de lo que hace: las mismas confirmaciones (también la de pagar
  a Apify) y las claves de YouTube, Meta y Apify donde estaban.

**Publicar: SEO con tu canal y Google Trends (21 de octubre)**
- **Conecta tu canal de YouTube** en **Configuración → YouTube: tu canal**
  (opcional). Se crea en Google Cloud un «ID de cliente de OAuth» (aplicación
  web) con la dirección de vuelta que enseña esa sección, se pegan el ID y el
  secreto y se pulsa **Conectar mi canal**. El Studio solo pide permiso de
  LECTURA (estadísticas y datos del canal). El secreto y el permiso se guardan
  en el almacén de claves y nunca bajan a la pantalla.
- Con el canal conectado, **«Investigar búsquedas»** añade **las búsquedas que
  ya te traen vistas en YouTube** (últimos 90 días) que el vídeo trata, y esas
  vistas suben **Tu historial**.
- En un vídeo ya publicado en YouTube, **«Cómo te encontraron en YouTube»**:
  sus vistas, el % visto de media y las búsquedas que le trajeron gente.
- **Columna «Tendencia»** (Google Trends, experimental): si la frase **sube,
  baja o está estable** en Perú (los últimos 3 meses frente a los 3 anteriores,
  en YouTube y en Google). Ajusta un poco la demanda. Trends no tiene una API
  abierta: si no contesta, la columna queda sin dato y se dice.
- Si tu app de Google Cloud está **«en prueba»**, Google corta la conexión cada
  7 días: Configuración lo marca («conexión cortada») y ofrece **Volver a
  conectar**. **Desconectar** quita el permiso en Google y en el Studio.

**Publicar: SEO de verdad (20 de octubre)**
- **La palabra clave sale del vídeo.** Antes la nota pedía meter la palabra
  del proyecto (por ejemplo «alquiler de consolas en Lima») aunque el vídeo
  tratara de otra cosa. Ahora, si el guion y el material no la tratan, no se
  usa: ni en la nota, ni en lo que se pide a Claude, ni en las etiquetas de
  YouTube, ni en el nombre del MP4. Lo mismo con las secundarias. La ficha lo
  dice («no se usa aquí: este vídeo no trata de eso»). La que escribas tú en
  la ficha manda siempre.
- **«Investigar búsquedas»** (bloque «Búsquedas reales» de la ficha, gratis y
  sin Claude): pregunta al autocompletado de YouTube y de Google (Perú, en
  español) qué frases de este vídeo se buscan de verdad, y enseña una tabla
  con cada frase: cuánto la trata el vídeo, su demanda, su competencia en
  YouTube, cómo le fue en tu cuenta y un total. Con «Usar» la pones de
  palabra clave del vídeo. Solo salen frases que el vídeo trata.
- **La nota SEO, en tres partes**: **Relevancia** (la palabra es del vídeo y
  está en el título y la primera línea), **Demanda** (se busca, y con la clave
  de YouTube, si está muy copada) y **Tu historial** (las vistas de tus
  publicaciones con esa palabra frente a lo normal de tu cuenta, con al menos
  3 publicaciones). La nota es la media de las partes que tienen dato, y dice
  cuántas son. Los **detalles de forma** (largo, número de hashtags, CTA,
  ubicación, portada) siguen saliendo con su botón, pero aparte y **sin contar**.
- **«Optimizar SEO con Claude» y «Que Claude escriba»** ahora leen el guion,
  usan las búsquedas reales y los ganchos que mejor funcionaron en tu cuenta,
  y tienen prohibido meter palabras que el vídeo no trata.
- **Clave de YouTube (opcional)** en **Configuración → YouTube (búsquedas
  SEO)**, con «Probar». Es una API key de Google Cloud con la «YouTube Data
  API v3». Es gratis, da unas 100 búsquedas al día (el Studio lleva la cuenta)
  y no caduca. Sin ella todo funciona igual, salvo la competencia. Los datos
  de YouTube se guardan 30 días como mucho, como pide su política.

**Qué dibujan las imágenes: la voz o el guion (22 de octubre)**
- **Nuevo, en el Encargo: «Qué dibujan las imágenes».** «Lo que dice la voz» es
  lo de siempre (cada imagen ilustra su frase) y es lo que tienen todos los
  vídeos si no eliges nada. Con **«Lo que dice el guion»**, cada imagen sigue su
  línea del **guion visual** y la frase de la voz ya no llega al dibujante: la
  voz solo marca cuándo entra cada plano. Es lo que faltaba para la mampara: la
  voz puede hablar de la corrediza sin que se dibuje la corrediza.
- **El guion visual** es la lista de planos: qué se ve, la cámara («plano general
  desde la puerta») y, en «Un espacio que cambia», el estado del objeto (la
  mampara abierta, la corrediza). Sale de las líneas «Visual:» de tu guion de la
  Parrilla (ya no se pierden) o de **«Proponer con Claude»**, que lo escribe
  leyendo el guion entero. Se revisa, se corrige y **se aprueba en el paso
  Imágenes** antes de dibujar: sin aprobar no se paga ningún plano. Escribirlo,
  proponerlo y aprobarlo es solo texto.
- **Antes de la primera tanda**, el guion visual y la imagen base salen en el paso
  **Voz**, encima de «Generar las imágenes» (el paso Imágenes sigue cerrado hasta
  que hay planos).
- **Sin gente si la línea no la nombra:** en modo guion, una persona solo sale
  en el plano cuya línea la pide.
- **Lo fijo manda:** al aprobar, Claude comprueba cada línea contra el sitio, el
  reparto y los estados aprobados, y avisa del plano que pide algo que no existe
  (se dibujará lo fijo).
- En la Parrilla, la línea de cabecera **«Imágenes: guion»** lo elige; en el
  estilo, «🎬 Qué dibujan las imágenes» (pestaña «Cómo se cuenta») es el punto de
  partida de sus vídeos nuevos. El del vídeo manda.

**Portadas, segunda vuelta (21 de octubre)**
- **La imagen sale limpia.** Las plantillas ya no meten efectos en la foto
  (contraste, color, viñeta, oscurecido, rayos de luz). Su «look» queda como un
  botón aparte, **«Poner el look de la plantilla»**, y **«Sin ajustes»** lo
  quita todo. La portada nueva empieza con la imagen de un plano tal cual (el
  fotograma del vídeo montado trae los subtítulos).
- **Tres capas, cada una con su interruptor:** **1 · Imagen** (el fondo y sus
  ajustes: lo único que toca la foto), **2 · Plantilla** (dónde va cada texto y
  elemento) y **3 · Colores** (los de los textos y elementos; **«Sin paleta»**
  los deja en blanco con borde negro).
- **«Esta imagen lleva: …»** debajo de la vista: qué hay encima de la foto, con
  una ✕ para quitar cada cosa.
- **El texto pequeño de arriba** sale al escribirlo (antes solo si ya estaba
  escrito al elegir la plantilla).
- **Elementos:** lo añadido nace en un hueco libre, más grande y de un color
  que se ve; **se conserva al cambiar de plantilla**; y cada elemento tiene
  **«Restablecer»** (vuelve a como nació, sin tocar su texto).
- **«Guardar diseño» se ve:** «Diseño guardado ✓» con la hora en la cabecera
  del editor. Los avisos flotantes salían por debajo del editor.
- **«⬇ Descargar portada»**, en el editor (PNG a tamaño real) y en el bloque
  Portada de Publicar (la puesta), para tener respaldo.
- **IA con el prompt a la vista:** **«Ideas de imagen con Claude»** lee el
  guion entero y propone tres escenas con su prompt; antes de pagar se ve el
  prompt (editable) y el precio en el botón **«Dibujar»**. Las reglas del final
  van siempre: el fondo sin letras; la portada entera con tus textos exactos.
- **Publicar: qué portada recibe cada red**, red por red, y en cada envío
  **qué portada se mandó**. Instagram acepta tu imagen (en la cuadrícula del
  perfil se ve el centro en 3:4: el editor lo marca en amarillo con «Ver lo que
  tapan las redes»); TikTok, tu imagen si la cuenta tiene el permiso
  «cover_image» de Upload-Post (el Studio lo detecta al «Ver cuentas»; si no, un
  fotograma, que ahora se puede elegir aunque haya imagen); YouTube solo con el
  canal verificado y la casilla marcada; Facebook, cuando sale como vídeo
  (largo u horizontal), no en los Reels; y ahora también **LinkedIn, X y
  Pinterest**. Las redes sin portada (Threads, Bluesky…) no reciben nada.
- **La pantalla de Publicar ya no se mueve** al llegar los 3 ganchos de otra
  red o al pulsar dos a la vez: se queda anclada a lo que estabas mirando.

**Crear en el móvil, arreglado (21 de octubre)**
- **El recorrido ya no parpadea**: la fila de pasos de arriba saltaba al paso 1
  y volvía cada medio segundo mientras algo se generaba. Ahora se queda quieta,
  solo se centra al cambiar de paso, y lo que deslizas con el dedo se queda
  donde lo dejas.
- **Al pulsar «Montar» el paso Vídeo ya no se vacía**: el reproductor (con el
  vídeo de antes y «montando…» encima), los ajustes del montaje y el repaso se
  quedan en su sitio, apagados hasta que acaba. La pantalla no salta a otro
  sitio, ni en el móvil ni en el ordenador.
- **La barra de abajo, en el móvil, es una fila**: cómo está el paso, en una
  línea, y el botón principal. Lo demás (el estado entero, lo que va a hacer y
  cuánto cuesta, y los otros botones) está en **«⋯»** (o tocando el estado),
  que se abre encima de la barra. Ya no cambia de alto mientras se genera.
  En Imágenes, ‹ ♪ Oírla ▶ Siguiente › van encima de la imagen.
- **La cabecera del vídeo, más baja en el móvil**: el nombre en una línea y el
  gasto en una pastilla (al tocarla, el desglose, como siempre).
- **Los avisos de «hay algo por actualizar», en una línea en el móvil**: «Este
  vídeo es de ANTES de tus últimos cambios» y la explicación del Encargo se
  abren al tocarlos; «Hay cambios del montaje sin aplicar» queda en una línea
  (el botón que lo resuelve ya está en la barra).
- **El aviso flotante (abajo) ya no tapa el botón de la barra**: sale encima
  de ella, al lado de la burbuja. Y si llegan dos seguidos, se ven los dos.
- **Escribiendo con el teclado del móvil abierto** (una nota, un texto), la
  barra de abajo, la cabecera de arriba y la burbuja se apartan hasta que
  dejas de escribir.
- **Al pedir una imagen con una nota, su tarjeta ya deja el sitio** de la
  nueva («dibujando la nueva…» arriba y la de ahora como «antes» abajo): al
  llegar ya no empuja el texto hacia abajo.
- Nada de esto cambia qué hace ningún botón ni cuánto cuesta.

**Crear, rediseñado: el carril de seis pasos (20 de octubre)**
- **El recorrido de un vídeo, a la izquierda** (en el móvil, una fila arriba
  que se desliza y se centra sola en el paso en el que estás): **Estilo ·
  Encargo · Guion · Voz · Imágenes · Vídeo**. Cada paso dice cómo está, con
  forma y color — ✓ hecho, ● estás aquí, ⟳ 42 % generándose, ! algo por hacer
  («Guion obsoleto», «2 tramos sin grabar», «1 imagen obsoleta», «1 nota sin
  aplicar», «Vídeo obsoleto», «1 cambio por traer»), ○ pendiente, · aún no — y
  una línea con lo suyo («6 bloques · 115 palabras», «0:53 · Gonzalo»). Debajo,
  lo gastado en el vídeo. Sustituye a la barra de pasos de abajo.
- **Una sola salida arriba** (y el logo). Desde un vídeo o un estilo de un
  proyecto **vuelve a ese proyecto** y lleva su nombre («‹ Estado Play»): sus
  estilos y sus vídeos, no la portada. Desde ahí, «‹ Tus proyectos» lleva a la
  portada; sin proyecto, la salida ya es «‹ Tus proyectos». Se fueron «‹ Mis
  vídeos», «← Volver», «‹ Volver», «‹ Todos los proyectos», «Todos los
  estilos» y «‹ Volver al vídeo». Arriba de cada paso, **la cabecera del vídeo**: su
  nombre (✏️ lo cambia ahí mismo; en «Últimos vídeos», también en su fila),
  su estilo, su proyecto y el gasto.
- **Una barra de acción pegada abajo en cada paso**: cómo está, qué va a hacer
  el botón (tareas, tiempo, precio) y el botón del siguiente paso con su coste.
  **Cada acción se llama igual en todas partes**: «Generar / Regenerar el
  guion», «Grabar / Regrabar la voz», «Regrabar N tramos», «Generar las
  imágenes», «Poner al día N imágenes», «Aplicar N notas» (antes «Rehacer N
  imágenes» en Imágenes y «Aplicar N cambios» en Vídeo), «Montar el vídeo»
  (antes también «Generar / Regenerar Vídeo») y «Enviar a Publicar ›».
- **La Voz tiene su paso**: la voz elegida («Cambiar en el estilo ›»), el
  reproductor, el guion en karaoke y, en cada bloque, **«▶ Oír»** y
  **«Regrabar este tramo»**. Si otros tramos tienen cambios sin grabar, se
  graban con él (la voz no se da por buena a medias) y el botón lo dice
  («Regrabar este tramo y 2 más con cambios»); antes de grabar pregunta con
  el precio que calcula el servidor. **«Regrabar la voz entera»**
  sustituye a «Regenerar Audio».
- **Guion**: los mandos de cada bloque se ven siempre (✂ Partir · ✎ Editar a
  mano · ↻ Cambiar con una frase); «+ Añadir bloque» en cada hueco; **«Revisar
  el guion»** con dos pestañas, Ortografía y Redacción (editorial); «Qué
  cambiarías del guion entero» ya no tiene botón propio: con algo escrito, la
  barra dice «Regenerar el guion».
- **Imágenes**: la tira de todos los planos arriba (⚠ obsoleta, 📝 con nota,
  ✓ revisada); los mandos para mirar, pegados encima de la barra.
- **Vídeo**: «Notas del vídeo» (antes «El repaso»), «Revisar» (la ortografía
  de los subtítulos), «Descargar» y «Publicar» en cajas debajo del vídeo.
- **El Estilo de un vídeo es su primer paso**: arriba, «Su estilo» (traer los
  cambios del estilo, cambiar de estilo, restaurarlo), que antes estaba en el
  Encargo; debajo, la ficha entera.
- **La ficha de un estilo, en pestañas**: 🎨 Cómo se ve · 📏 Reglas · 🗣️ Cómo
  se cuenta · 🎙️ Cómo suena · ⏱️ Ritmo · 🌐 Nombre, idioma y proyecto. El tono,
  en tres cajas con nombre: «Lo que lee el redactor (se guarda solo)», «Pídele
  un cambio al tono» y «Cómo quieres que suene (para regenerarlo entero)». Cada
  lámina tiene **«Redibujar esta lámina»** (antes «Regenerar», que chocaba con
  el de abajo), y la barra dice **«Regenerar lo pedido»**, con un punto en las
  pestañas que piden algo. Un estilo nuevo usa las mismas pestañas, y la barra
  dice lo que falta (cada aviso lleva a su pestaña).
- **La tarjeta de un estilo**: pulsarla sigue empezando un vídeo nuevo, y ahora
  lleva **«✎ Editar»** a la vista; en «⋯» quedan Duplicar y Mover a otro
  proyecto.
- **Los ajustes del montaje ya no montan solos (el único cambio de cómo se
  comporta algo).** Son el mismo panel en el Encargo y en Vídeo (también en un
  vídeo nuevo, que los guarda en el borrador): tocar la música, los
  subtítulos, el logo, los efectos o el movimiento lo guarda y la fila dice
  «· sin aplicar todavía»; sale la franja «Hay N cambios del montaje sin
  aplicar», y **solo** «Montar el vídeo con N cambios · gratis», en la barra,
  los monta, todos de una vez. Se fueron «Aplicar ahora», «Aplicar y volver a
  montar» y «Montar la música con este ánimo» (el ánimo se elige y entra al
  montar). Antes, en Vídeo, cada cambio volvía a montar el vídeo.
  «Montar el vídeo con N cambios» **no dibuja ninguna imagen nunca**: si hay
  imágenes que se han quedado viejas, montar con ellas es otro botón, «Montar
  el vídeo · ≈ X», que pregunta antes cuántas y cuánto. Lo pedido y sin
  montar (el ánimo de la música también) **no se pierde** al moverte por el
  vídeo ni al recargar la página; salir del vídeo con ello te lo recuerda, y
  si el vídeo se monta por otro camino (desde Imágenes, por ejemplo) el
  contador baja solo.
- Nada de esto cambia lo que se genera ni lo que se paga: los mismos pasos,
  los mismos parámetros y las mismas firmas.

**Publicar: arreglos del 20 de octubre**
- **El Short de YouTube vuelve a subir.** Upload-Post rechazaba el idioma del
  audio «es-419» («Invalid defaultAudioLanguage format»): solo acepta códigos
  «idioma-PAÍS» como «es-ES» o «en-US». Ahora el español de Latinoamérica se
  manda como **«es-US»** (YouTube lo enseña como «Español (Estados Unidos)», el
  más cercano que entra en esa forma), y lo guardado antes como «es-419», «es»
  o «en» se traduce solo al enviar. En «SEO de este proyecto» la lista solo
  ofrece códigos que valen (también «Español de México», «es-MX»).
- **Short o vídeo normal en YouTube.** La ficha dice cómo sale («YouTube ·
  Short» o «YouTube · Vídeo normal») y qué cambia: un Short lleva **«#Shorts»**
  en el título (o al final de la descripción si no cabe), Claude le escribe un
  título de 30 a 60 caracteres y una descripción de 1 a 3 líneas, y no lleva
  capítulos; un vídeo normal, título de 40 a 70, descripción para el buscador
  y capítulos. En un vídeo **vertical** se puede elegir «Publicarlo como»:
  Automático, Short o Vídeo normal (quien decide de verdad es YouTube, por las
  medidas: vertical de hasta 3 minutos sale en Shorts; se avisa cuando lo
  elegido no cuadra). Cada envío recuerda cómo salió («YT · Short»).
- **Al programar, la ficha se cierra.** «Programar…», «Publicar ahora…» y
  «Dejar esperando mi OK» vuelven a **Cola y calendario** con el aviso
  «Programado para … ✓» y un botón «Volver a la ficha». Guardar textos a secas
  no cierra nada, y si el guardado de los textos falla la ficha se queda
  abierta con lo escrito.
- **Lo programado que ya salió deja de decir «programado».** La pantalla solo
  le preguntaba a Upload-Post por lo que se estaba subiendo; lo programado no
  se volvía a mirar nunca. Ahora, llegada su hora, Cola y calendario y la ficha
  preguntan solas y pasa a «publicado» (o «falló», con el motivo). Si pasan 10
  minutos de su hora sin noticias, dice **«debería haber salido a las 09:00»**
  con **«Comprobar»** (también en «Te necesitan»); si Upload-Post no sabe nada
  de él, pasa a «comprobar» para que lo mires, sin dejar publicarlo dos veces.
- **El calendario ya no cambia con los filtros.** Enseña siempre todo lo
  programado y publicado de la semana o el mes; los filtros (proyecto, estilo,
  estado, buscar) solo cambian «Vídeos listos» y «Te necesitan», y se dice.

**Imágenes: descargarlas y leer lo que dice la voz (20 de octubre)**
- **«⬇ Descargar»** debajo de cada imagen de las diapositivas: baja el PNG
  original del plano que estás viendo, con un nombre que se entiende
  (`<vídeo>_<plano>.png`, por ejemplo `padres_vs_hijos_S004.png`).
- **«⬇ Descargar todas»**: un .zip con todas las imágenes de plano del vídeo,
  en el orden del vídeo y numeradas (`<vídeo>_001_S001.png`…). Solo lee: no
  cambia nada del vídeo ni cuesta nada.
- **«Lo que dice la voz»**: un cuadro debajo de la imagen con el texto del
  guion que se oye en ese plano, para leerlo y no solo escucharlo. Cambia al
  pasar de plano y, mientras suena «♪ Oírla» o «▶ Todo seguido», **se resalta
  el trozo que se está diciendo**. Con el texto a la vista, en el ordenador la
  imagen se hace un poco más pequeña para que quepan las dos cosas sin bajar.
  **«Ocultar el texto»** lo quita (y la imagen vuelve a su tamaño); el
  navegador se acuerda de tu elección.

**El tipo de relato: el mismo sitio en todas las imágenes (20 de octubre)**
- **Nuevo «El tipo de relato»** en el Encargo, en un vídeo hecho y en el estilo
  (🧭 Tipo de relato): dice CÓMO se cuenta el vídeo en imágenes, nunca de qué
  negocio es. **Documental** (lo de siempre), **Un espacio que cambia**,
  **Recorrido**, **Escenario y apoyos**, **Producto** y **Clase** (de momento,
  como un recorrido).
- **Un espacio que cambia** es un solo sitio que se ve siempre igual y en el
  que cambia SOLO lo que dice la voz: un objeto, los acabados (misma geometría
  y ángulo), el estado (obra, montaje, terminado) o la hora (la luz y la
  gente). Claude escribe qué cambia en cada tramo y **cada plano se genera
  editando una imagen base del sitio, con la misma cámara**. Los planos de
  detalle la llevan como referencia. Era el fallo del Reel del baño: cada
  imagen salía con un baño distinto.
- **La imagen base** es el sitio vacío y entero: la que subiste en «El espacio
  fijo» (gratis) o una generada (se paga una imagen y ves su coste antes). **Se
  aprueba antes de generar los planos**: sin ella aprobada no se paga ningún
  plano de ese sitio. «Producto» también edita la base (el fondo no se mueve).
- **Cada estado, dibujado una vez** (21-10, tras la prueba de la mampara): en
  «Un espacio que cambia», cada cambio del guion (la mampara abierta contra el
  inodoro, la corrediza) se dibuja UNA vez sobre la imagen base aprobada y lo
  apruebas igual que la base, viendo su coste. Los planos de ese estado editan
  su imagen, así que el objeto sale igual en todos; antes cada plano se
  inventaba la mampara abierta y salía distinta en cada uno. Las miniaturas de
  la base y de los estados se abren a tamaño completo al pulsarlas.
- **Quién manda en el tipo de relato, dicho en la pantalla**: el del vídeo
  manda sobre el del estilo («Documental» en el estilo quiere decir «no impongo
  ninguno»), y el Encargo dice de dónde sale el que rige. El manual lo explica
  junto con la diferencia entre «El espacio fijo» (el texto del sitio) y la
  imagen base (ese sitio dibujado y aprobado).
- **La distribución tiene que hacer verdad lo que cuenta la voz**: si Claude
  declara el sitio, pone las distancias (el inodoro a 0,4 m del vidrio si la
  mampara choca con él); la guía de la Parrilla lo pide también.
- **Lo que cambia sale ya en la base, en su sitio** (21-10, tras la prueba de
  la mampara): al repartir, Claude escribe cómo está y dónde va lo que luego
  cambia («una mampara batiente en el borde izquierdo de la ducha, que abre
  hacia el inodoro») y la imagen base lo dibuja así. Antes la base salía sin
  mampara y cada plano inventaba la suya en otro sitio. La ficha de la base
  lo enseña para que compruebes que está donde va antes de aprobarla.
- **El revisor compara cada plano editado con su base**: si cambió algo que no
  se pidió (la distribución, la cámara, un mueble fijo), lo marca como
  congruencia de gravedad alta.
- **Qué manda**: lo elegido en el vídeo (o la línea **«Tipo de relato:»** de la
  Parrilla, con la clave o el nombre, con o sin tildes); si no, lo del estilo;
  si tampoco, con espacio fijo es «Escenario y apoyos» y sin él, «Documental».
  **Sin elegir nada, los vídeos salen exactamente como antes.**
- **En un vídeo hecho**, «Aplicar el tipo de relato» no dibuja nada: enseña qué
  planos cambiarían y cuánto cuesta rehacerlos, y eliges todos, los marcados o
  ninguno.
- **`asvs probar relato`** (en la consola del VPS): las tres pruebas reales del
  tipo de relato, solas y con tope de gasto (5 $ salvo `--tope N`): crea tres
  vídeos de prueba, aprueba su imagen base, los dibuja y monta, pasa el revisor
  y pide a Claude que compare cada plano con su base.
- **«Pedido para el reparto de sitios»**, junto a «El reparto y los sitios» del
  vídeo: una frase que lee Claude al repartir («todo en la cocina; el patio
  solo al final») y «Volver a repartir con este pedido» (no se paga ninguna
  imagen; las hechas se quedan hasta que pidas rehacerlas).

**El espacio fijo: todo el vídeo en un mismo sitio (20 de octubre)**
- **En la Parrilla, un guion puede traer «ESPACIO FIJO»** (opcional), con
  `- Sitio:` (un nombre corto), `- Descripción:` (cómo es el sitio, en una
  frase), `- Luz:` y `- Secundarios:` (otros sitios que sí pueden salir,
  «Nombre: descripción» separados por «;» o uno por línea). Está en la
  plantilla de «Escribir uno», en el formato que se le pide a Claude y en la
  guía del formato. Sin descripción no cuenta.
- **«Pasar al Encargo» lo lleva a «Un vídeo nuevo»**, a un bloque nuevo, «El
  espacio fijo», que también se puede rellenar a mano.
- **Con él, el reparto de sitios usa UN solo sitio** con esa descripción tal
  cual (y esa luz), pone ahí todos los tramos salvo los que el guion sitúe en
  un secundario de la lista, no pone cabeceras de sitio ni rótulos de lugar y
  no reparte «dos planos por sitio». Se impone aunque Claude proponga otra
  cosa. Vacío, todo sale como siempre.
- **La petición al deducir el reparto y los sitios ya llega a Claude** (el
  campo `peticion` de `/catalogo/proponer` y `/escenarios`): se quedaba por el
  camino y no se le pasaba nunca. La pantalla todavía no tiene un campo para
  escribirla.
- **Con una imagen del sitio (opcional)**: en «El espacio fijo» puedes subir
  una foto o un dibujo del lugar (también al pasar un guion de la Parrilla). Se
  adjunta a cada imagen de plano del sitio principal —no a los secundarios—
  para que el lugar se reconozca. Se paga como una referencia más: unos ~730
  tokens de entrada por imagen, alrededor de medio céntimo (≈ +12 % en calidad
  baja, ≈ +7 % en media); el aviso de «rehacer» lo suma.
- **En un vídeo ya hecho, como corrección**: el Encargo del vídeo trae «El
  espacio fijo». «Aplicar el espacio fijo» lo guarda y reparte los tramos de
  siempre en ese sitio **sin dibujar nada ni pagar nada** (las imágenes hechas
  se conservan). Después enseña qué planos cambiarían y lo que cuesta
  rehacerlos, y eliges: **rehacer todos**, **solo los marcados** en esa lista,
  o **ninguno**. Solo se rehacen los que pidas; luego hay que volver a montar
  el vídeo.

**Arreglos del 19 de octubre (segunda tanda)**
- **La pantalla ya no salta arriba** al terminar un remontaje, al «Traer» los
  cambios del estilo ni al cambiar el proyecto, los días o el mes en Publicar →
  Resultados: se queda donde estabas. Ir a otra pantalla sí empieza arriba.
- **En el Encargo, varios cambios del montaje y un solo montaje.** La música,
  cuánto se oye, su volumen, los efectos, el logo, los subtítulos y el
  movimiento se guardan sin montar, y sale la franja «Hay cambios del montaje
  sin aplicar · **Aplicar y volver a montar**». Ya no sale «el vídeo se está
  montando ahora» al tocar la segunda cosa. Si lo cambiado es solo sonido o
  logo, se vuelve a mezclar en segundos, sin rehacer ningún plano. En la
  pantalla Vídeo cada cambio sigue montando al momento, como antes.
- **«Parar» un montaje para en el acto.** El botón dice «Cancelando…» y se
  apaga; antes esperaba a que terminara la mezcla (medio minuto, o más con el
  logo). Al parar, el vídeo sigue siendo el de antes, no queda ningún trozo a
  medias, y el cambio sigue guardado: **«Regenerar Vídeo» lo aplica volviendo a
  mezclar** (segundos), no renderizando otra vez todos los planos.
- **«Cambiar de estilo…» en «Su estilo»** (en el Encargo del vídeo). Un vídeo
  cuyo estilo se borró se quedaba sin forma de adoptar otro; ahora eliges otro
  estilo, ves qué partes cambiarían (estilo gráfico, tono, voz, rótulos) con
  lo que costaría, y marcas solo las que quieras traer. Sin marcar nada, el
  vídeo solo cambia de estilo apuntado y no se rehace nada. El vídeo **se queda
  en su proyecto** si tenía uno. Si su estilo está en la papelera sale además
  **«Restaurarlo»**, y la parada «Estilo» de un vídeo sin estilo te lleva ahí.
- **«Revisión editorial» del guion**, junto a la ortografía. Claude lo lee como
  un corrector editorial (sintaxis, concordancia, puntuación, repeticiones,
  frases confusas o largas para decirlas en voz alta y saltos de registro) y
  propone cambios sueltos con su motivo: **«Aceptar»** o **«Rechazar»** una a
  una, o **«Aceptar todas»**. Aceptar cambia el bloque como si lo escribieras a
  mano (las pausas de la voz se conservan). Si la voz ya está grabada, te avisa
  de qué bloques habrá que regrabar. La ortografía de siempre no cambia. Va con
  tu cuenta de Claude (sonnet, esfuerzo medio): no cuesta dinero de API.

**El nuevo diseño: CrearIA Studio (19 de octubre)**
- **Se llama CrearIA Studio · Automatización de contenido**, con logo nuevo: la
  C de Crear con el bucle dentro y un «play». El favicon es el mismo dibujo. Por
  dentro no cambia nada (el comando `asvs`, las carpetas y los servicios siguen
  igual). El «play» va en el mismo violeta de la C.
- **Cuatro paletas**, en Configuración → Aspecto: **Nocturno** (la de siempre),
  **Aurora** (turquesa y rosa), **Brasa** (ámbar y frambuesa) y **Día**, la
  clara. Se recuerdan en el navegador. **Día es el tema claro de antes**: el
  botón de sol y luna de arriba sigue estando y pasa de Día a tu última paleta
  oscura (si tenías elegido el claro, entras en Día). Los textos se leen bien
  (contraste AA) en las cuatro.
- **Letras nuevas**: Space Grotesk en los títulos, Inter en el texto y
  JetBrains Mono en las cifras (si no cargan, las del sistema).
- **En el ordenador, los módulos van en un menú a la izquierda**: Inicio,
  Crear, Publicar (con su contador), Automatizar y Configuración, y debajo el
  **gasto del mes** (con tu tope, si lo pones) y si el **asistente está
  listo**. En el móvil y la tableta siguen en la fila de arriba. Crear
  funciona igual que antes.
- **El Inicio es ahora tu panel**: el saludo con lo que sale esta semana, las
  cifras del mes (vídeos, programados, vistas de 7 días, para publicar), «Te
  necesitan» (fallos, lo que espera tu OK, lo de hoy y lo listo para
  publicar), la semana por días, los proyectos recientes, lo que está en marcha
  y lo mejor de 7 días.
- **«✎ Personalizar panel» (Arma tu panel)**: quita tarjetas, cámbiales el
  tamaño (S, M, L) y el orden (arrastrando o con ↑ ↓), enciende otras (Gasto
  del mes, Parrilla, Calendario, Por cliente, Novedades), empieza desde una
  vista (Producción, Publicación, Resultados, Mínima) o vuelve al original. Se
  guarda **para tu usuario** si entras con contraseña, y en el navegador si no.
- **El «?» abre un panel de Ayuda** (ya no Configuración): el manual abierto en
  el apartado de la pantalla en la que estás, todas las guías de escritura, la
  guía de inicio y las novedades. El manual tiene apartados nuevos de Inicio y
  de Automatizar (Parrilla y Analizar cuentas).
- **Al entrar se abre el Inicio** (tu panel). Recargar la página te deja donde
  estabas, y el botón Crear (o el logo) lleva siempre a **Tus proyectos**.
- **El «atrás» del móvil ya no te saca del Studio**: cuando no queda nada
  atrás, te lleva a Tus proyectos (y desde ahí, al Inicio) en vez de volver a
  la pantalla de la contraseña.
- **«‹ Volver» en pantalla** en las secciones de Publicar y Automatizar (las
  fichas ya tenían «‹ La cola» y «‹ Parrilla»; en un vídeo sigue «‹ Mis
  vídeos»), y **«✕» para cerrar** las imágenes ampliadas, para no depender del
  «atrás» del teléfono.
- **Un pie en todas las pantallas** con los derechos (© 2026 Agencia Redes
  Botánica · v3.1) y los enlaces a Novedades, Guía, **Términos de uso** (las
  condiciones de uso del Studio) y **Contacto** (escribe a
  agencia.redes.botanica@gmail.com).

**Textos de Publicar con emojis, siempre a juego con el vídeo (20 de octubre)**
- **«Emojis en los textos» tiene niveles** (Publicar → Cuentas y ajustes → Lo
  fijo de este proyecto): **Ninguno · Sobrio · Normal · Vistoso**. De fábrica,
  **Vistoso**: el título lleva uno (en YouTube, al final, para no tapar la
  palabra clave), el gancho empieza con uno, cada párrafo lleva el suyo de
  viñeta, la llamada a la acción otro y la zona va con 📍. Elegidos por el tema
  de cada vídeo (🎮 consolas, 🎂 cumpleaños, 🏢 empresa), no los mismos ✨🔥 en
  todo. LinkedIn y Google van más sobrios. Antes era un sí/no con «1 a 3» y por
  eso unos textos salían con emojis y otros no. **Si tenías «Usar emojis»
  apagado, se respeta: ese proyecto queda en Ninguno.**
- **Emojis de la marca**: una casilla con los emojis propios del proyecto (para
  EstadoPlay, 🎮 🕹️ 🎉). Claude los usa de firma en el gancho y en la llamada a
  la acción de cada red.
- **Combinaciones de dos emojis** (🎮➕🎉 = fiesta gamer, 🏠➡️🎉 = la fiesta en
  casa): es la forma real de tener emojis «propios». Emojis dibujados a medida
  no se pueden poner en un título o una descripción: las redes solo enseñan los
  emojis estándar, y uno inventado saldría como un cuadrado. Para algo dibujado
  de verdad, la portada (stickers y grafismo).
- **El aviso**: si un texto sale con menos emojis de los que pide el nivel, la
  ficha lo dice junto al campo («va con menos emojis de los pedidos»). La nota
  SEO no cambia por eso.
- **«✨ Más emojis»**, junto al título y al texto de cada red: añade emojis a lo
  ya escrito **sin cambiar ninguna palabra ni hashtag** (el Studio lo comprueba;
  si Claude cambiara algo, no se toca nada y te lo dice). Es una llamada corta y
  barata (haiku) con tu suscripción de Claude, y se guarda sola, con su
  «✓ Guardado».
- «Dame 3 ganchos» sigue el nivel de emojis, y «Optimizar SEO» ya no quita los
  emojis al reescribir una línea.

## V2.0 · octubre de 2026 (imágenes, música y efectos, y un recorrido de toda la pantalla)

**Elementos encima de las imágenes, al ritmo de la voz (19 de octubre)**
- En **Imágenes**, cada diapositiva trae **✨ Elementos de esta imagen**:
  palabras que saltan, insignias (x3, -50 %, NUEVO), etiquetas de precio,
  iconos, flechas y círculos que señalan, estrellas, subrayados, bandas,
  cintas y el rayo de un versus. Cada uno **salta en la palabra que elijas**
  (la voz trae el momento exacto de cada palabra), en el sitio que digas
  (arriba, centro, izquierda…) y con su entrada: salta, golpe, desliza,
  aparece suave o se dibuja. Uno se va cuando salta el siguiente, para que
  nunca se pisen.
- **«Ver cómo queda»** pinta la imagen con sus elementos encima.
- **«Proponer con Claude»**, para una imagen o para **todo el vídeo**, con una
  intensidad: **Sobrio** (unos 6 por minuto), **Vivo** (unos 13, lo
  recomendado) o **Dinámico** (unos 23). Lo propuesto sale «sin guardar» para
  mirarlo, y «Aplicar sumando» o «Aplicar en lugar de lo que hay» lo pone en
  todas las imágenes de una vez.
- **No se paga nada**: cambiarlos solo deja pendiente el montaje de esas
  imágenes (gratis); ninguna imagen se vuelve a dibujar. Sin elementos, el
  vídeo sale exactamente igual que antes.
- **La otra opción, con IA (se paga)**: «Texto dentro de la imagen» apunta una
  nota en esa imagen para que la IA la vuelva a dibujar con el texto DENTRO
  (un cartel, una pantalla…). Se paga al aplicar la nota, como cualquier otra.

**Portadas diseñadas, como las miniaturas que funcionan (19 de octubre)**
- En **Publicar → Portada**, el botón **Diseñar portada** abre un editor con
  la vista a un lado y los mandos al otro.
- **21 plantillas** sacadas de lo que funciona en YouTube, Instagram y
  TikTok: Titular, Versus (como «diseño vs función»), Antes / Después, Top N,
  Pregunta, Precio / Oferta, Dato impactante, Error común, Tutorial, Lista de
  pasos, Testimonio, Curiosidad, Desafío, Comparativa de precios, Urgencia,
  Resultado, Detrás de cámaras, Mito vs realidad, Evento / temporada, Escala
  y Reacción.
- **El fondo**: un fotograma del vídeo, la imagen de un plano, dos imágenes
  partidas (con el rayo del versus), una imagen tuya o una hecha con IA.
- **Encima, en capas**: títulos con contorno, sombra, brillo neón, relieve,
  degradado o palabra resaltada; insignias (VS, RETO, -50 %), flechas,
  círculos a mano, rayos, iconos, etiquetas de precio, bandas, cintas,
  estrellas, ráfagas y marcos. Cada uno se mueve, se agranda, se gira, se
  colorea o se esconde. Y efectos de la foto: contraste, color, brillo,
  viñeta y oscurecer abajo. Todo esto es gratis y el texto sale exacto.
- **Paletas** (Impacto, Gamer, Oferta, Confianza, Fiesta, Fiestas Patrias,
  Cálido) y **letras de miniatura** (Anton, Bebas Neue, Luckiest Guy,
  Bangers, Archivo Black, Montserrat, Lilita One, Permanent Marker, Russo
  One), de licencia libre: el servidor las baja solo la primera vez; mientras
  tanto se usa una parecida.
- **4 formatos**: 9:16, 16:9, 4:5 y 1:1. «Ver lo que tapan las redes» marca
  en rojo las zonas que tapan los botones (no sale en la portada).
- **Proponer 3 portadas con Claude**: lee el guion y propone plantilla,
  textos y colores; eliges una y la retocas. No se paga aparte.
- **Con la IA de imágenes (se paga, con el precio delante)**: hacer solo el
  fondo (el texto sigue en capas) o la portada entera con el texto dentro
  (más vistosa, pero puede escribir mal alguna letra).
- **Usar como portada** la pinta a tamaño real y la deja como la imagen que
  se manda a las redes, igual que si la hubieras subido. El diseño se guarda
  para retocarlo otro día.
**Tus notas del 19 de octubre**
- **«Crear» abre siempre «Tus proyectos»**, desde la barra de arriba y desde
  la tarjeta de Inicio, aunque hubieras dejado un vídeo abierto. El «atrás»
  del navegador sigue llevando adonde estabas.
- **Lo que pide una lámina ya no se corta en 400 caracteres**: ahora caben
  1.500, el campo dice cuántos llevas, y si te pasas lo dice en vez de cortar.
  Antes se guardaba cortado sin avisar y la lámina se dibujaba (y se pagaba)
  con la mitad de lo pedido.
- **El asistente ya no sale en rojo («no conectado») por un fallo pasajero**
  de otro trabajo (un guion que tardó, «Overloaded», la sesión renovándose):
  sale en ámbar y se comprueba solo al abrirlo. Rojo es solo sin sesión o sin
  cupo.
- **El ajuste fino de la música (dB) también en un vídeo nuevo**: en el Encargo,
  Ajustes del montaje → Música → «Cambiar». El vídeo nace con él.
- **Regrabar una sección ya no deja un chasquido** donde se cose con el resto
  de la voz: se corta en el punto más tranquilo de la pausa y con un fundido
  corto. Era el ruido del «Torneo de 8» (segundo 22,7). Para quitarlo de un
  vídeo ya hecho, regraba esa sección otra vez.

**Publicar: una sola nota SEO, guardar con señal y fallos que se quitan (19 de octubre)**
- **Una sola nota SEO**: la de cada red (la del Studio, sin Claude). La revisión
  de Claude ya no pone la suya («80/100 según Claude»); enseña cuánto subiría
  la nota con sus cambios («con estos cambios: 57 → 72») y no repite lo que la
  nota ya dice. Sin cambios que aceptar, no sale «Aceptar todo».
- **Cada punto que resta tiene su botón**: sin palabra clave, **Escribir
  palabra clave** (o **Usar «…»** si Claude propone una); sin portada,
  **Elegir portada**; sin ubicación de Instagram, un enlace que abre **SEO de
  este proyecto** con el cursor en su campo y la pista de qué poner (el número
  del Lugar de Facebook, no el nombre); y los demás llevan al título, al
  texto, a los hashtags o a la llamada a la acción. Todo dice el sitio con su
  nombre de verdad: **Cuentas y ajustes → SEO de este proyecto**.
- **Hashtags**: ya no se cortan a 15 sin decir nada. Cada red admite los suyos
  (Instagram 30, YouTube 60, las demás 30, contando los fijos del proyecto) y
  los que no caben se dicen debajo del texto («5 hashtags no caben en
  Instagram y no se mandan»).
- **Guardar los textos**: una pastilla encima de los textos dice **Sin
  guardar…**, **Guardando…**, **✓ Guardado** con la hora, o **No se ha
  guardado** con **Reintentar**. Cambiar de vídeo, de pestaña o de módulo
  espera a que se guarde lo último (antes, cambiar de vídeo enseguida lo
  perdía), y cerrar la pestaña con algo sin guardar lo pregunta.
- **Fallos**: en la cola, en **Inicio → Lo que pasa hoy** y en **Te
  necesitan**, cada fallo trae **Quitar de la lista**. Un fallo que volviste a
  mandar y salió en esa red ya no cuenta (ni en el número de la barra). En la
  ficha, lo cancelado o quitado va plegado en **N descartados**.

**Publicar: YouTube y Facebook van en su propia subida (19 de octubre, tarde)**
- Si publicas o programas a la vez en **YouTube o Facebook y en otras redes**
  (Instagram, TikTok…), el Studio lo manda a Upload-Post en **dos subidas**:
  una para YouTube/Facebook con su título y otra para las demás con su texto
  completo. Antes iba todo junto y el título de YouTube podía acabar como el
  texto de Instagram.
- **Cada subida cuenta en el mes de Upload-Post**: Instagram + YouTube son 2;
  con Google Business, 3. La confirmación antes de enviar dice cuántas.
- Cancelar un programado de YouTube ya no cancela el de Instagram (van en
  subidas distintas): cancela cada red por separado si quieres quitar las dos.
- En la ficha no cambia nada: cada red sigue con su envío, su estado y su
  «Reintentar». Lo que ya estaba programado antes de este cambio no se toca:
  cancélalo y vuelve a programarlo para que salga con el texto entero.

**El movimiento y la profundidad 2.5D de cada imagen (19 de octubre)**
- En **Imágenes**, cada diapositiva trae **🎬 Esta imagen**: su movimiento
  (**Quieta**, Sobrio, Vivo o Dinámico) y su **2.5D** (sí o no). De partida
  dice «Como el vídeo», que es lo elegido en 🎬 Movimiento y efectos.
- **Quieta** es nueva y solo existe por imagen: el plano no se mueve. Va bien
  en primeros planos, textos dibujados o para dar un respiro.
- La 2.5D por imagen sirve para ponerla solo donde queda bien (paisajes,
  escenas con fondo) y quitarla donde deforma (caras de cerca, textos).
- Cambiarlo deja pendiente **solo esa imagen**: se aplica al montar el vídeo
  («Montar el vídeo» sale abajo), gratis y sin redibujar nada.
- Las cartelas y las cabeceras llevan siempre el movimiento de siempre, porque
  su texto va con la imagen. Los cortes secos de «Dinámico» siguen al vídeo
  entero, no a la imagen.

**Publicar: los posts salen con el texto entero (19 de octubre)**
- **Arreglado:** sin YouTube ni Facebook en el envío, los posts salían solo con
  la primera línea (sin el resto ni los hashtags). El «title» común que se manda
  a Upload-Post llevaba solo esa línea; ahora lleva el texto completo de la red,
  el mismo que su campo propio. Con YouTube o Facebook sigue siendo su título.
- En la ficha, cada envío tiene **«Ver lo que se mandó»**: los textos exactos
  que salieron hacia Upload-Post, con su largo y **Copiar**. Si Upload-Post
  devuelve el texto que quedó en la red y es más corto, sale el aviso «la red
  lo recortó».

**Reglas del estilo: lo que ninguna imagen puede romper (19 de octubre)**
- En cada estilo, debajo de «Estilo gráfico», la sección **📏 Reglas del
  estilo**: una lista corta de normas, escritas como se las dirías a un
  fotógrafo («quien juega mira siempre la pantalla, nunca a cámara»). Cada
  una con su nombre, **«solo si el plano habla de…»** (unas palabras; vacío =
  en todos los planos) y su **gravedad** si se incumple.
- Cada regla entra en las imágenes de los planos a los que aplica, marcada
  como obligatoria; el **corrector** la respeta al rehacer una imagen con una
  nota, y el **revisor** la comprueba una por una con la gravedad que le diste
  (en modo autónomo, las de gravedad alta se corrigen solas).
- **«✦ Afinar con Claude»**: la reescribe para la IA de imágenes (en inglés,
  concreta: dónde va la cámara, hacia dónde mira cada uno) y te propone
  nombre, palabras y gravedad. Tú decides si la usas.
- Se guardan solas y no cuestan nada. Llegan a los vídeos **nuevos** al
  crearlos, y a uno ya hecho con **«Traer el estilo»**; sus imágenes no se
  rehacen solas. Un estilo sin reglas sigue exactamente igual que antes.

**Publicar: más redes, cifras automáticas e informe del mes (18 de octubre)**
- **Nueve redes más**: LinkedIn, X, Threads, Pinterest, Bluesky, Discord,
  Telegram, Mastodon y Google Business. Se añaden por proyecto en Publicar →
  Cuentas y ajustes → **Redes de este proyecto**, con lo que cada una necesita
  (el tablero de Pinterest, la página de LinkedIn, el botón de Google
  Business…). En la ficha, título donde lo hay y **texto alternativo** donde se
  admite. Claude escribe para cada una con sus reglas y límites. Reddit no, porque
  Upload-Post la tiene caída.
- **Cifras automáticas**, apagadas de fábrica: elige la frecuencia (una vez al
  día, cada 12 o 6 horas, semanal), la hora y cuántos posts (los últimos 30, por
  ejemplo). Antes de guardar se ve **lo que gasta**: 0 $ (va incluido en el plan
  de Upload-Post), y las consultas del cupo que usa. **Pedirlas ahora**, para una
  vuelta ya.
- **Resultados**: la tabla de **palabras clave y ganchos que funcionaron**,
  **cuándo publicar** en cada red (y en la ficha, la hora propuesta con «Usar»)
  y el **informe del mes** de cada proyecto, imprimible y con un resumen para
  copiar.

**El corrector de ortografía, en el guion y en los campos que se ven (18 de octubre)**
- **El guion se revisa solo**: en la pantalla del guion, sin la voz grabada,
  el panel **Ortografía del guion** revisa el texto unos segundos después de
  que deje de cambiar (un guion nuevo, un bloque editado) y propone las
  tildes, letras y signos que faltan. Antes había que acordarse de pulsarlo, y
  muchas veces se veía ya en Vídeo, con todo montado.
- **Con la voz ya grabada el panel sigue ahí** y lo dice: corregir el guion
  deja la voz de esos bloques por regrabar (se paga), y antes de hacerlo te lo
  pregunta. Para que solo se lea bien, la **Ortografía de los subtítulos** de
  Vídeo sigue funcionando igual (gratis).
- **No se pregunta dos veces lo mismo**: lo revisado se recuerda en cada
  vídeo, así que al editar un bloque solo se revisa ese. Lo que dejes sin
  marcar al aplicar no se vuelve a proponer.
- **«Revisar ortografía» en los campos de texto que se ven**: los textos de
  las llamadas a la acción y el guion de la ficha de la Parrilla. Propone las
  correcciones y «Poner las correcciones» las escribe en el campo, con los
  saltos de línea donde estaban; «Dejarlo como está» no las vuelve a proponer.
  En **Publicar**, cada red trae su «Revisar ortografía», que mira juntos el
  título, el texto, la llamada a la acción, el texto alternativo y el primer
  comentario, y dice de qué campo es cada corrección (los hashtags no).
- **El error «Failed to refresh OAuth token: another Claude Code process is
  refreshing it…»** ya no corta el corrector (ni nada que hable con Claude):
  pasa cuando dos llamadas arrancan mientras la sesión se renueva, y ahora se
  espera y se repite solo. Tampoco marca la cuenta como «sin sesión».


**Cancelar de verdad en el taller de estilos (18 de octubre)**
- **«Cancelar» un «Rehacer» para en el acto**: corta la llamada a Claude y no
  encarga ninguna lámina más (las que ya se estaban dibujando se acaban y se
  guardan, para no pagarlas otra vez). Mientras termina, la pantalla dice
  «Cancelando…» con el botón apagado, y acaba con «cancelado», no con un error.
- Si vuelves a pulsar mientras tanto, te dice qué está pasando y te lleva a ello.
- **«Regenerar» ya no se pulsa dos veces**: mientras Claude lee tu corrección
  dice «Leyendo tu corrección…», y un segundo toque no gasta nada.
- Escuchar una voz ya no impide rehacer el estilo.

**Un revisor de imágenes que mira cada plano con su guion (18 de octubre)**
- En **Imágenes**, debajo del cuadro de notas, el panel **Revisor de
  imágenes**: «Revisar imágenes» mira cada imagen con lo que dice la voz en
  ese plano, el bloque del guion, las indicaciones del estilo y del Encargo y
  las reglas de la casa, y deja una **nota por plano** en las que no cuadran
  (el equipo mal montado, mandos de otro color, gente que no mira a la
  pantalla, manos o mandos fundidos, otro estilo). Sus notas salen en la lista
  de siempre con la etiqueta **revisor · alta/media/baja** y se cambian o se
  quitan como las tuyas.
- **«Rehacer las marcadas»** las manda a la cola de siempre: las de retoque
  parten de la imagen de ahora y las que piden otra imagen se dibujan desde
  cero. Cada plano marcado tiene su «✕» para decir «está bien así».
- Mira las imágenes en grupos de 8 seguidas, para ver si el sitio, el equipo y
  la gente se mantienen de un plano a otro; cada grupo ve además la última
  imagen del anterior, para que el salto entre grupos tampoco se escape.
- Revisar **no gasta en imágenes** (usa tu cuenta de Claude) y una imagen ya
  revisada no se vuelve a mirar mientras no cambie. Lo que cuesta es rehacer.
- **Tres modos**, en Configuración → Revisor de imágenes: **manual** (solo con
  el botón; es el de fábrica), **autónomo** (al acabar cada tanda de imágenes, o
  al rehacer imágenes con tus notas, revisa las nuevas y rehace solo lo grave,
  una vez) y **automático** (también
  al generar el vídeo entero: rehace todo lo marcado y lo vuelve a revisar,
  hasta el número de vueltas que elijas, antes de montar). En los dos últimos,
  con **topes**: imágenes como mucho por tanda y gasto como mucho por vídeo; y
  una misma imagen no se rehace sola más de dos veces.
- Revisar no cambia nada del vídeo: no deja ningún paso obsoleto.

**Profundidad 2.5D en el montaje (18 de octubre)**
- **Nueva casilla en 🎬 Movimiento y efectos: «Profundidad 2.5D».** Lo que
  está cerca (un árbol, una persona, un producto) se mueve más que el fondo
  mientras la cámara hace su recorrido, como si la imagen tuviera capas.
- **No cuesta nada:** un modelo gratuito calcula en el propio servidor qué está
  cerca y qué lejos de cada imagen (menos de un segundo por imagen, y una sola
  vez: se guarda). No redibuja ninguna imagen; encenderla solo rehace las capas
  y el montaje. Eso sí, el montaje tarda más: unos dos tercios más por plano.
- **Es experimental y va apagada.** En fotos se ve limpia; en una ilustración,
  el borde de lo que va delante puede deformarse un poco al moverse.
- `asvs actualizar` instala lo que hace falta (unos 100 MB, una sola vez). Si
  no puede, el Studio sigue igual y la casilla dice qué falta.
- Por ahora se elige para el vídeo entero; elegirla plano a plano llegará con
  el revisor de imágenes, en la diapositiva de cada plano.

**Publicar: SEO de verdad (18 de octubre)**
- **Palabras clave del proyecto**, en Publicar → Cuentas y ajustes → **SEO de
  este proyecto**: la principal («alquiler de consolas en Lima»), las
  secundarias, la zona y las palabras a evitar. **«Proponer palabras clave»**:
  Claude las propone desde los encargos y guiones del proyecto, cada una con su
  porqué y, si el servidor puede salir a internet, con lo que sugiere YouTube al
  escribirlas. Tú eliges.
- **Palabra clave de cada vídeo**, en su ficha (si no, vale la del proyecto).
  Al escribir los textos, Claude la pone en la primera línea de cada red, al
  principio del título de YouTube y Facebook y en las dos primeras líneas de la
  descripción de YouTube, reparte las secundarias, nombra la zona con un
  hashtag local, propone una palabra más concreta para ese vídeo y escribe un
  **primer comentario**. Rota los hashtags del **banco del proyecto** (amplios,
  de nicho, locales) para no repetir el mismo bloque, y aprende de los posts
  que mejor funcionaron.
- **La nota SEO de cada red**, sin Claude y sin coste: ✓ y ⚠ con el porqué
  (palabra clave en el título y en la primera línea, largo del título y de la
  primera línea, hashtags en su rango y uno local, sin hashtags vacíos como
  «fyp», CTA, ubicación, categoría, portada) y una nota de 0 a 100.
- **«Optimizar SEO con Claude»**: una segunda pasada como revisor SEO que
  propone cambios campo a campo con su porqué. Tú aceptas campo a campo,
  «Aceptar todo» o «Dejar el mío»; nunca pisa lo que hayas cambiado a mano
  después de pedirla. **«Dame 3 ganchos»** para la primera línea de una red.
  Y en lo fijo, «Optimizar SEO al escribir los textos» hace las dos pasadas
  seguidas.
- **Lo que ahora va a cada red además del texto:** Instagram, la ubicación
  (el número de un Lugar o Página de Facebook, con su guía), colaboradores y
  etiquetas; YouTube, la categoría, el idioma del texto y del audio, «Hecho
  para niños» (apagado: un vídeo para padres que contratan fiestas infantiles
  NO es para niños) y las etiquetas con las palabras clave; TikTok, la
  ubicación (si tu cuenta tiene esa función); y el primer comentario. Instagram
  no admite texto alternativo en Upload-Post, y se dice.
- **El MP4 se sube con la palabra clave en el nombre**
  («alquiler-de-consolas-en-lima-fiesta.mp4»); el del proyecto no cambia.
- **En el Encargo**, si el proyecto tiene palabra clave, una sugerencia: que
  el guion la diga en los 3 primeros segundos y salga en pantalla.

**Arreglos pendientes de los análisis del 10 y 13 de octubre (18 de octubre)**
- **Ajustes guardados con un tipo equivocado** (un texto donde va un objeto, en
  el estilo, la música, el logo…) se rechazan al guardarlos: antes se aceptaban
  y varias pantallas del vídeo daban error para siempre. Y un segundo clic en
  «Generar» con el vídeo ya generándose no cambia sus ajustes a mitad.
- **El logo y las imágenes de una nota del repaso se revisan al subirlos**: un
  fichero roto se rechaza ahí, en vez de romper el montaje al 97 %. Una nota
  sube como mucho sus 4 imágenes.
- **Copiar a mano la carpeta de un vídeo** ya no crea un «gemelo» que abre el
  original; la copia se queda en el mismo cliente que el original (y una
  carpeta renombrada, en el suyo), y su gasto sale a su nombre. Nombres de
  vídeo larguísimos y vídeos creados a la vez ya no dan problemas.
- **«Aplicar» del repaso** no lanza dos montajes con dos clics, ni encima de
  la tanda del vídeo: avisa de que espere.
- **Un retoque de una imagen hecho mientras corre la tanda** ya no se da por
  hecho sin dibujarlo.
- **Si una nota de imagen se para o falla después de pagar la imagen**, esa
  imagen se guarda aparte (no se pierde) y la nota lo dice; antes la siguiente
  tanda la metía sin avisar.
- Sin el programa de Claude instalado, el asistente dice que no está (antes un
  error), y los errores ya no enseñan rutas ni carpetas del servidor (solo el
  nombre del fichero). Las claves cortas
  (como el Client ID de Jamendo) enseñan 2 caracteres, no la mitad.
- **En la pantalla:** en el móvil, el «–» de la burbuja ya no tapa el chat
  abierto, y la burbuja ya no pisa «Siguiente ›» en Imágenes; «Un vídeo nuevo»
  marca «Encargo» en la barra y la duración dice «de 10 s a 30 min»; «Un estilo
  nuevo» pide el nombre del estilo sin errores de fondo; cambiar el tipo de
  imagen con referencias puestas avisa de que deben ser fotos (o dibujos); el
  recuento de palabras del guion cuenta lo corregido a mano; el tiempo que
  queda no promete minutos con la barra casi llena; la cabecera ya no enseña
  dos veces el mismo trabajo; y textos corregidos («Imágenes» en vez de
  «Diapositivas», «el redactor», «La pausa… se hace»).

**Publicar: los resultados, más completos (17 de octubre)**
- **Cuánto se ve de cada vídeo.** TikTok dice qué parte de la gente lo vio
  **hasta el final** y los **segundos de media**; YouTube, cuando su informe
  está listo, qué parte del vídeo se ve **de media** (en un Short puede pasar
  del 100 % si se vuelve a ver). Son medidas distintas y no se mezclan.
  Instagram y Facebook no dan ninguna: ahí no sale nada (nunca un «0 %»
  inventado). Las medias pesan por vistas: un post de 50 vistas no cuenta
  como uno de 100.000.
- **Esta semana y este mes** en Publicar → Resultados: lo publicado desde el
  lunes y desde el día 1, frente al mismo tramo del periodo anterior (un
  jueves, con la semana pasada hasta el jueves).
- **Lo que mejor funcionó:** los cinco posts del periodo por vistas, por
  interacción (me gusta, comentarios, compartidos y guardados entre vistas),
  por cuántos lo vieron hasta el final (TikTok) o por cuánto se ve de media
  (YouTube), con la red, el día y la hora en que salieron. Por proporción solo
  cuentan los que tienen 50 vistas o más.
- **En Inicio, una línea con lo mejor de los últimos 7 días**, que lleva a su
  ficha.
- **Las cifras se siguen pidiendo solo al pulsar «Actualizar»**, como hasta
  ahora. Además, cada «Actualizar» trae lo que Upload-Post ya tiene guardado,
  que no gasta de las 100 consultas cada 5 minutos: así llega la retención de
  YouTube y lo que hayas mirado desde la web de Upload-Post.
- Si la carga de Resultados fallaba, la pantalla se quedaba rota en vez de
  decir el motivo: ahora sale el error.

**Los cortos duran lo pedido, y comparar el guion con opus (18 de octubre)**
- Un vídeo de hasta 2 minutos salía medio segundo o un segundo más corto de lo
  pedido: el cálculo de palabras preveía las pausas de un vídeo largo (tres o
  cuatro) y el guion corto lleva dos. Ahora cuenta las suyas. Los vídeos ya
  hechos no cambian.
- **`asvs comparar-guion`**, en la consola del servidor: escribe el guion de un
  vídeo tuyo con sonnet y con opus, con el mismo material y las mismas
  indicaciones, y te los enseña como «A» y «B» sin decir cuál es cuál.
  `asvs comparar-guion revelar` lo dice después de elegir (y cuál es el que
  usa hoy ese vídeo: por defecto, opus con esfuerzo muy alto). No toca el vídeo y
  no gasta dólares, solo tokens de la suscripción. Sin nada detrás, enseña la
  lista de vídeos que se pueden comparar.

**Vídeos con más movimiento, sobre todo los cortos (18 de octubre)**
- **Movimiento de cámara en tres niveles**, en el Encargo y en el vídeo
  (Ajustes del montaje → 🎬 Movimiento y efectos): **sobrio** (lo de siempre:
  un acercamiento o alejamiento suave por plano), **vivo** (acercamientos,
  paneos y alejamientos que se alternan, y los planos largos se reencuadran a
  mitad, en una pausa de la voz) y **dinámico** (más recorrido, un golpe de
  zoom en la palabra clave y cortes secos entre planos, salvo en los acentos).
- **Gancho del primer segundo**: el primer plano entra con un zoom rápido y la
  primera frase sale grande en el centro.
- **Subtítulos de redes**: palabras grandes, con borde, y la palabra que se
  está diciendo resaltada en el color del vídeo.
- **Cifras clave en pantalla**: «ochenta y cuatro centímetros» sale arriba,
  grande, como «84 cm»; un rango, como «23–25 cm».
- **Barra de progreso** fina arriba del vídeo.
- **Elegir las transiciones** que entran, cada una con su muestra animada.
- **Los vídeos NUEVOS de hasta 2 minutos nacen con todo esto puesto** (en
  vivo) y en **ritmo rápido** (planos de 1,5 a 5 s) si su estilo iba más
  lento. Ojo: el ritmo rápido son más planos, y un 30-40 % más de imágenes que
  pagar; el Encargo lo dice en el coste y deja elegir «Ritmo del estilo». Los
  vídeos largos y **los que ya existen no cambian** si nadie lo pide.
- Cambiar el movimiento, los subtítulos, las cifras, la barra o las
  transiciones de un vídeo hecho **no redibuja ninguna imagen**: se rehacen
  las capas y el montaje («Aplicar ahora»), que son gratis.
- La descarga «sin subtítulos» sale también sin las cifras clave ni la barra:
  van en la misma capa que los subtítulos, que es la que se quita.
- Arreglado el mismo día: en el móvil, varias muestras de transición salían
  con una carita triste en vez de la animación, y marcar o quitar una
  transición cerraba la lista. Ahora se ven todas, la lista se queda abierta y
  el texto ya no sale en mayúsculas.

**Analizar una cuenta de la competencia (18 de octubre)**
- **Automatizar → Analizar una cuenta**: escribes el @usuario o pegas el enlace
  de un perfil de **TikTok, Instagram o YouTube** que no es tuyo, y el Studio
  trae sus vídeos públicos con vistas, likes, comentarios, duración, fecha y
  texto, de más a menos vistas.
- **Primero gratis**: YouTube por su API oficial e Instagram por la vía oficial
  de Meta (solo cuentas profesionales). **Si no sirve** (TikTok, o una cuenta de
  Instagram personal), por **Apify**, de pago: unos céntimos por cuenta. **Antes
  de pagar siempre pregunta**, con el precio, también cuando lo gratis falla a
  medias; hay un **tope al mes** (5 $, lo que regala el plan gratis de Apify)
  que cuenta incluso lo que Apify cobra cuando una lectura sale mal, y una
  cuenta leída se guarda 24 h para no volver a pagarla.
- Una **clave gratis que no vale** (o el token de Meta caducado) no pasa al
  servicio de pago: te dice que la arregles en Conexiones.
- La conexión de Instagram **no queda atada a una cuenta**: sirve la de tu
  negocio o una creada solo para el Studio. Para cambiarla, pegas el token de
  la nueva y el Studio la encuentra solo; lo ya analizado se queda.
- **«Que Claude la analice»**: qué temas, ganchos, duración y horarios le
  funcionan, comparando sus vídeos con más y con menos vistas, e ideas para ti.
- **«Escribir guiones con lo que le funciona»**: para tu proyecto, con tu
  marca, inspirados y sin copiar. Van a la Parrilla.
- En **Conversar con Claude**, el selector **«📈 Con una cuenta»** le pasa sus
  vídeos y su análisis.
- Las claves (Google, Meta y Apify) se ponen en **Conexiones**, dentro de esa
  misma pestaña, con su guía paso a paso.
- Iniciar sesión con cuentas propias para mirar perfiles **no** se hace: lo
  prohíben Instagram y TikTok y acaba en bloqueos.

**La Parrilla: conversar con Claude, la marca del cliente y «Desde mis resultados» (18 de octubre)**
- **Conversar con Claude** (Automatizar → Añadir guiones): un chat como el de
  claude.ai para preparar guiones hablando. Recuerda la conversación, conoce la
  marca del proyecto y el formato del guion, y cada guion que escribe sale con
  **«Guardar en la Parrilla»**. Puedes:
  - pegar **capturas** (📎). Para analizar una cuenta de Instagram o TikTok, haz
    capturas de su perfil o de sus reels con las vistas: esas redes no dejan ver
    los reels sin iniciar sesión, así que Claude no puede entrar por su cuenta;
  - encender **«🌐 Buscar en internet»** en un mensaje (viene apagado). Lo que
    saque de fuera lleva su fuente y un aviso ⚠ para confirmarlo;
  - encender **«📊 Con mis resultados»** para que vea tus vídeos que mejor
    funcionaron;
  - elegir **Opus** (como en claude.ai) o **Sonnet** (contesta antes).
- **La marca del cliente** (Automatizar → Marca del cliente): quién es, qué
  mostrar, qué evitar, el tono y el CTA de siempre, apuntados **una vez por
  proyecto**. Claude la usa en todo lo que escribe para ese proyecto. Desde la
  ficha de un guion, **«Usar su marca para el proyecto»** la rellena con la de
  ese guion.
- **Desde mis resultados** (Añadir guiones): eliges tus vídeos que mejor
  funcionaron (con sus vistas, interacción y retención) y Claude escribe guiones
  nuevos que repiten lo que funcionó, diciendo en cuál se inspira cada uno. Usa
  las cifras que ya tiene Publicar: no gasta consultas.
- Dos guías nuevas: «La marca del cliente» y «Conversar con Claude».

**La Parrilla de guiones, en Automatizar (17 de octubre)**
- **Automatizar ya no está vacío: abre la Parrilla.** Cada proyecto tiene sus
  matrices de guiones, y cada guion su estado: **pendiente**, **usado** (se
  pasó al Encargo) o **publicado** (su vídeo ya salió en Publicar). El paso de
  usado a publicado es solo: en cuanto creas el vídeo con ese guion queda
  enlazado, y cuando lo publicas pasa a publicado. También se puede marcar a
  mano, o volver a pendiente.
- **Añadir guiones**, de tres formas: **subir una matriz** en Word (.docx),
  Excel (.xlsx), PDF o texto; **pedírselos a Claude** (de 1 a 30, de cinco en
  cinco y sin repetir ideas); o **escribir o pegar** uno o varios. Todo se
  convierte al **formato único del guion** (el del prompt de conversión), con
  «Uso: exacto» (la locución se respeta palabra por palabra) o «Uso: adaptar»
  (el original es una guía y la locución se escribe para la red). Si lo pegado
  ya está en el formato, se guarda tal cual, sin Claude. Una matriz larga se
  convierte guion a guion.
- **La ficha de un guion**: su texto entero, editable; uso, formato y
  duración a mano; sus avisos ⚠; y **lo que irá al Encargo**, tal como saldrá.
- **«Pasar al Encargo»** llena «Un vídeo nuevo» en Crear —nombre, material,
  indicaciones, llamada a la acción, duración y formato— con el estilo que
  elijas, y marca el guion como usado. Con «exacto» marca «Esto YA es el
  guion». No crea ningún vídeo ni gasta nada: el vídeo lo creas tú con
  «Generar el guion», como siempre.
- **Es opcional**: el Encargo se sigue llenando a mano igual que antes.
- Dos guías nuevas: **«El formato del guion»** (con el prompt de conversión
  para pegarlo en otra IA) y **«Pedir guiones a Claude»**.
- Convertir y escribir guiones usa Claude (tokens de la suscripción, sin
  coste en dólares). El piloto automático todavía no está: llega más adelante.

**El vídeo montado ocupa menos (17 de octubre)**
- Cada montaje ya no copia los clips de los planos que no cambian: la versión
  nueva los comparte con la anterior. Cambiar la música o el logo ya no duplica
  los clips en disco (el MP4 final y la música sí se escriben nuevos). Las versiones anteriores quedan intactas y «Revertir»
  funciona igual. (En un servidor Windows se sigue copiando.)

**Guiones de vídeos cortos que no salen «a resumen» (17 de octubre)**
- **Los vídeos de hasta 2 minutos tienen su propia forma de escribirse.**
  Antes se escribían como un documental de varios minutos (cuatro a seis temas,
  gancho de dos bloques), y en un minuto eso daba una frase por tema: el guion
  nombraba todo y no explicaba nada. Ahora el redactor cuenta UNA idea con un
  caso concreto (la mitad del vídeo, paso a paso), elige del material lo que la
  empuja y no recorre las listas punto por punto. Los vídeos de más de 2 minutos se
  escriben igual que siempre.
- **Las etiquetas de «Las indicaciones» son órdenes.** ENSEÑA es la única
  idea; ÁNGULO se cuenta como una escena que se ve pasar, no como una mención;
  EMPIEZA POR es la primera frase, y DEJA FUERA no sale ni de pasada. Valen
  en vídeos de cualquier duración. Sin etiquetas, todo sigue como antes.
- **«Revisar» del material y de las indicaciones sabe cuánto dura el vídeo.**
  Si el material no cabe, lo dice; en un vídeo corto propone marcar con
  «IMPRESCINDIBLE:» lo que tiene que entrar, y el redactor de los cortos lo
  respeta. Si las indicaciones piden demostrar algo y el material no trae las
  medidas, te las pide.
- Las etiquetas se reconocen en MAYÚSCULAS, como las enseña la guía (una nota
  como «Ángulo: no me convence el de antes» sigue siendo una nota), y cada una
  acaba en la siguiente etiqueta o en una línea en blanco.
- **«Regenerar el guion» con una instrucción ya no borra tus indicaciones.**
  Lo que escribes en «Qué cambiarías del guion» («más directo») se suma a las
  indicaciones del Encargo; antes las sustituía y ENSEÑA y ÁNGULO se perdían.
  Si ya te pasó en algún vídeo, vuelve a escribirlas en su Encargo.
- Las guías de «El material» y «Las indicaciones» explican todo esto.
- Los guiones ya hechos no cambian ni quedan para regenerar: esto se nota al
  escribir o reescribir un guion.

**Publicar: los textos de Claude ya no salen vacíos (17 de octubre, madrugada)**
- A veces Claude contestaba llamando a la red por su nombre («Instagram
  Reels») y el Studio solo buscaba «instagram»: decía «Textos listos» con las
  casillas vacías. Ahora entiende las dos formas, a Claude se le dicen las
  claves exactas, y si una red llega sin texto se dice («Claude no ha devuelto
  el texto de Instagram Reels») con «Reintentar» solo de esa; lo que ya había
  escrito no se borra. «Copiar texto» sin texto avisa en vez de decir «copiado».

**Publicar: los textos de Claude se ven al terminar (17 de octubre)**
- Si mientras Claude escribía los textos el cursor estaba en una casilla de
  texto, los textos se guardaban pero la ficha seguía vacía hasta salir de la
  casilla o recargar. Ahora aparecen en cuanto terminan, con un aviso «Textos
  listos». El aviso de «escribiendo» dice desde el principio cuánto lleva, y
  si Claude no contesta, el fallo sale a los 4 minutos (antes podía tardar 16).

**Publicar: lo que salió probándolo en el servidor (16 de octubre, tarde)**
- **El perfil de Upload-Post se apunta con lo que escribes.** «Crear perfil»
  manda el nombre del campo; **«Usar este perfil»** (o Enter) apunta uno que ya
  tengas, y **«Elegir de mi cuenta»** enseña tus perfiles de verdad en un
  desplegable (los de otro proyecto salen marcados). Da igual cómo escribas las
  mayúsculas: «suyu» encuentra «Suyu». Un perfil que ya existe se adopta
  aunque el plan esté lleno; si hay que crear uno y el plan está lleno, se
  dice en castellano antes de intentarlo. La tarjeta se pone al día sola:
  «Ver cuentas» y «Conectar» salen sin recargar, y al volver de la página de
  Conectar las cuentas se miran solas.
- **«Que Claude escriba los textos» enseña que está escribiendo** y, si
  falla, el motivo con **Reintentar** (y queda apuntado en el registro del
  servidor). Antes podía quedarse colgado sin decir nada.
- **Textos más atractivos:** gancho en la primera línea, frases cortas, una
  sola llamada a la acción y hashtags que mezclan amplios con otros de nicho o
  de la zona; reglas propias de cada red (TikTok corto con las palabras que se
  dicen, Reels con la primera línea fuerte, YouTube con título de 70 caracteres
  y descripción para el buscador, Facebook que se entienda sin sonido). Claude
  los escribe con un modelo mayor. Y **emojis** bien puestos, con un
  interruptor «Usar emojis en los textos» en lo fijo de cada proyecto
  (encendido de fábrica).
- **Portada:** elige un fotograma con un deslizador (lo ves al lado) o sube
  una imagen. Va a cada red por su campo: Instagram y TikTok el fotograma,
  Facebook cuando sale como vídeo, y YouTube o TikTok con imagen propia si lo
  marcas.
- **Título solo donde existe** (YouTube y Facebook); en Instagram y TikTok se
  explica que la primera línea hace de título.
- **«Publicar ahora» se apaga con su motivo** («Falta el texto de Instagram»)
  en vez de fallar al pulsarlo.
- **Después de publicar** la ficha dice dónde ya salió (con el enlace) y qué
  está en camino, cada red enseña su último estado, y avisa cuando una red se
  publica mientras miras.
- **La cola, con buscador y filtros** (proyecto, estilo, estado y fecha),
  agrupar por proyecto y **vista de mes**.

**Lo que quedó de la revisión (16 de octubre, noche)**
- **`asvs actualizar` pone al día también el servidor**: las unidades de
  systemd, los snippets de nginx, el lanzador del navegador y las variables
  nuevas del entorno. Solo cambia lo que ha cambiado y guarda copia; si la
  versión nueva no arranca, lo devuelve todo. El sitio de nginx (el que edita
  certbot para el HTTPS) no se toca, y del entorno nunca se cambia un valor ya
  puesto. **Tras esta actualización hay que correr `asvs actualizar` dos
  veces**: la primera la hace todavía el `asvs` viejo.
- **La duración pedida se cumple mejor.** Al calcular cuántas palabras caben
  se cuentan también las pausas del gancho y de cada cambio de tema; antes el
  vídeo salía de 2 a 5 segundos más largo. Solo en los vídeos nuevos: los que
  ya tienes no se tocan ni quedan para regenerar.
- **Corregir un bloque del guion a mano ya no le quita la pausa del final**
  (la pastilla «⏸» se queda). La pausa solo se quita con «Quitar pausa».
- **Un vídeo con el estado dañado ya no se abre vacío.** El Studio guarda la
  copia buena anterior de su estado; si un corte de luz lo estropea, vuelve a
  ella y lo apunta en la bitácora (se pierde, como mucho, el último cambio).
  Si no hay copia, el vídeo no se abre y dice por qué, en vez de ofrecer
  regenerarlo entero.
- Subir imágenes, logos o capturas ya no deja parado el resto del Studio
  mientras se guardan.

**Publicar en redes (16 de octubre)**
- **Arriba hay una barra de módulos: Inicio · Crear · Publicar · Automatizar.**
  «Crear» es lo de siempre (estilos y vídeos) y es lo que se abre. «Inicio»
  enseña los tres módulos y lo que sale hoy. «Automatizar» (la Parrilla de
  guiones y el piloto automático) llega en la próxima versión.
- **Debajo de un vídeo montado, «Enviar a Publicar».** Abre su ficha: eliges
  las redes (TikTok, Instagram Reels, YouTube, Facebook), Claude escribe el
  texto de cada una desde el encargo, el guion final y la duración real (con
  título y capítulos en YouTube), y lo corriges a mano si quieres; se guarda
  solo. Cada red tiene «Copiar texto» y está «Descargar MP4» para subirlo tú.
  Si el vídeo no encaja en una red (horizontal en TikTok, más de 3 minutos
  como Short…), se avisa; si la red no lo acepta, no se deja enviar.
- **Publicar ahora, programar (día y hora de Lima) o solo a mano.** Con
  Upload-Post, siempre con una confirmación delante que no se puede quitar.
  Cada red es su propio envío: si una falla, las demás siguen, y cada una
  enseña su estado y el enlace al post. Lo programado se puede cancelar, y
  un envío puede quedarse «esperando tu OK» hasta que lo confirmes. Volver a
  publicar el mismo vídeo en la misma red pide confirmarlo.
- **La cola y el calendario:** los vídeos listos, la semana con lo que sale
  cada día y, arriba, lo que te necesita (lo que falló o espera tu OK).
- **Cuentas y ajustes por proyecto:** el perfil de Upload-Post de cada
  cliente, «Conectar» para que conecte sus cuentas, y lo fijo del proyecto
  (hora por defecto, firma, hashtags, tono, marcar como hecho con IA, avisar a
  los suscriptores de YouTube).
- **La clave de Upload-Post va en Configuración → Publicar en redes**, como
  las de la música y los efectos (nunca en un chat), y se prueba sin subir
  nada en Publicar → Cuentas y ajustes. Sin clave se puede preparar todo y
  publicar a mano.
- Los textos para redes gastan tokens de tu suscripción de Claude y se apuntan
  en el coste del vídeo. Nada de Publicar deja obsoleto el vídeo.
- **Guías y «Revisar» también en Publicar.** El texto de cada red y el tono de
  los textos del proyecto tienen su **✦ Guía** (qué poner y qué no, plantilla,
  ejemplo y prompt para otra IA) y su **✓ Revisar**, como los campos de Crear.
  Y el manual («?») explica el módulo Publicar paso a paso.
- **Resultados: lo que pasa con lo publicado.** En Publicar hay una pestaña
  nueva, **Resultados**: por proyecto y periodo (7, 30 o 90 días), cuántas
  publicaciones, vistas, me gusta, comentarios y compartidos, por red y con
  los seguidores de cada cuenta, y los vídeos de más a menos vistos. En la
  ficha de un vídeo, cada envío publicado enseña sus cifras y hay
  **«Actualizar métricas»**. Las cifras se piden a Upload-Post solo al pulsar
  «Actualizar» (deja unas 100 consultas cada 5 minutos); TikTok las da unas
  horas después de publicar, y lo subido a mano no se puede medir desde aquí.

**El disco ya no crece sin límite (16 de octubre)**
- **De cada vídeo se guardan sus 5 últimos montajes.** Cada vez que montas un
  vídeo, el Studio guarda una copia entera (clips, música, efectos y el MP4);
  antes no se borraba ninguna y un proyecto llegó a ocupar 55 GB. Ahora, al
  terminar un montaje, se borran los más antiguos y quedan los 5 últimos. El
  que estés usando no se borra nunca, aunque sea antiguo. Las imágenes, la voz
  y el guion siguen guardando todas sus versiones. Los vídeos que ya tienes se
  recortan la próxima vez que los montes.

**Revisión completa del Studio (16 de octubre, tarde)**
- **Las diapositivas se ven y suenan después de volver a una versión
  anterior**, y siguen en la misma escena. Si la carga falla una vez, sale
  «Reintentar» en vez de quedarse la pantalla en blanco sin «Oírla» ni «Todo
  seguido».
- **«Oírla» y «Todo seguido» suenan con la voz con la que se cortaron las
  imágenes** (la del vídeo), no con la de la revisión de audio, que tenía otros
  tiempos y callaba los últimos planos. Si no pueden sonar, dicen por qué.
  «Todo seguido» lleva por fin la música (y los efectos, con el vídeo montado).
- **Pausas entre bloques que se oyen.** La pausa del gancho y de cada cambio de
  tema se suma al aire entre bloques (~1,5 s frente a ~1 s), en vez de perderse
  dentro de él. **Sin inicios cortados:** el silencio se mete en el punto más
  tranquilo entre dos bloques, no en mitad de una respiración, con un fundido
  corto a cada lado, y cada sección se manda a la voz con su espacio para que
  no se peguen palabras. Se oye en las voces que se graben o regraben desde
  ahora.
- **Reintentar ya no rehace lo que salió bien.** Si una tanda falla a medias,
  el error queda en la tarea que falló: la voz o el guion ya hechos no se
  regraban ni se reescriben al reintentar. Volver a una versión ya no la enseña
  «obsoleta» ni mezcla imágenes de la versión de la que se vuelve (lo que quedó
  a medias se aparta en `_apartados/`). Un paso que cambiaste mientras corría
  ya no dice «listo», no se pueden lanzar dos pasadas del mismo paso a la vez,
  y tras reiniciar el servicio no quedan pasos «ejecutando» para siempre.
- **Imágenes más seguras con el gasto.** Dos planos con el mismo mapa ya no
  tumban la tanda al final. Si OpenAI no contesta a tiempo (502/504), la tanda
  se para y lo dice en vez de repetir una imagen que quizá ya cobró. Las hojas
  de personaje no se vuelven a pagar al «regenerar lo obsoleto» si no han
  cambiado. El precio por imagen de la cola de notas y del panel de coste tiene
  en cuenta el modo foto.
- **Cancelar un render lo para de verdad**, navegadores incluidos. La barra ya
  no dice «(44, 44)», el logo y la cola de negro salen en la calidad del vídeo,
  y la música ya no deja WAV sueltos en cada versión del render.
- **`asvs actualizar` instala las librerías antes de tocar nada** y, si la
  versión nueva no arranca, vuelve sola a la anterior.
- **El asistente ya no puede buscar dentro de las claves** (Grep/Glob), igual
  que ya no podía leerlas.
- Un trabajo que el servidor ya no conoce (tras reiniciarlo) se da por perdido
  en vez de dejar los botones apagados.

**Más arreglos de imágenes (16 de octubre)**
- **Pegar una imagen ya no la manda al logo por sorpresa.** Con el cursor en
  un campo de texto (el nombre del vídeo, unas indicaciones), una imagen pegada
  no va a ninguna zona: sale un aviso para que pulses antes en la zona de
  imágenes. Sin cursor en un campo, va a la zona que hayas tocado la última y
  que se vea en pantalla; ninguna, tampoco el logo, la recibe por ser «la
  única a la vista». Escribiendo la nota de una imagen, lo que pegues va a los
  adjuntos de esa nota.
- **Si OpenAI rechaza un plano con su filtro de seguridad, la tanda sigue con
  los demás** y al final dice cuál (o cuáles) fue, con su frase, y qué hacer:
  cambiar su nota o, si no tenía, escribirle una describiendo lo que se ve sin
  marcas. Antes se paraban todos los planos siguientes de ese sitio y el aviso
  decía «Cambia la nota» aunque no hubiera ninguna. Lo dibujado no se vuelve a
  pagar al relanzar.
- **Un microcorte de red ya no tumba la tanda con un error de Python.** Si no
  se pudo ni conectar con OpenAI, se reintenta solo un par de veces (no se ha
  cobrado nada). Si la conexión se corta con la imagen ya pedida, no se repite
  sola, porque puede estar cobrada: lo dice claro y lo hecho se conserva.
- **Rehacer una imagen con nota conserva las caras.** La hoja de reparto de
  cada personaje del plano va siempre al rehacerlo, aunque el corrector no la
  eligiera. Las demás imágenes no se tocan ni quedan obsoletas.

**El dinero de las imágenes, revisado (15 de octubre)**
- **Cambiar la calidad ya no promete lo que no hace.** «Traer el estilo» con
  otra calidad decía «rehace las N imágenes» con su precio, y «Poner al día»
  las conservaba sin redibujar ninguna. Ahora dice la verdad: lo ya dibujado
  (también las hojas de reparto) se queda como está y la calidad nueva se
  aplica a lo que se haga o rehaga. Nada se paga sin pulsar.
- **En las diapositivas sale «N imágenes siguen en otra calidad»** con un
  botón «¿Rehacerlas en media? ≈ X $». Pide confirmación con el precio y rehace
  SOLO esas; las demás no se tocan. Las hojas de reparto se quedan como están
  (rehacerlas obligaría a rehacer los planos que las usan).
- **El $/min del deslizador de ritmo** sale con la calidad con la que nacerá
  el vídeo: en un estilo de foto (que empieza en media) decía el de calidad
  baja, un 43 % menos de lo real.
- **El precio de antes de crear un vídeo** de foto respeta siempre el mínimo
  de calidad media, aunque el estilo tenga «baja» guardada.
- **«Lo que te han cobrado» cuenta solo imágenes de plano**, y por tipo de
  imagen (foto o ilustración) cuando ya hay bastantes: las láminas de los
  estilos se colaban y abarataban el precio de un plano de foto.
- **Los vídeos verticales tienen su tarifa** cuando OpenAI no devuelve el
  recuento de tokens (antes se apuntaban «sin tarifa»).

**Copiar y pegar (15 de octubre)**
- **Las imágenes se pegan con Ctrl+V** (⌘V en el Mac) en todas las zonas que
  suben imágenes: las de referencia de un estilo (nuevo o el que editas), las
  de las notas del vídeo y de cada imagen, el logo (del vídeo y del proyecto)
  y los adjuntos del asistente. Suben igual que si eligieras el fichero: los
  mismos topes y los mismos avisos. Si hay varias zonas a la vista, la imagen
  va a la última que hayas tocado. Pegar texto en un campo sigue igual.
- Debajo de cada zona sale «o pega una imagen (Ctrl+V)»; pulsarlo también
  pega, y en el móvil es «📋 Pegar una imagen» (el navegador pide permiso la
  primera vez).
- **«Copiar» en las respuestas del asistente**: cada bloque de código lleva el
  suyo arriba a la derecha, y cada respuesta uno en el pie para copiarla
  entera, en texto llano (sin asteriscos ni comillas del formato).

**La voz (14 de octubre)**
- **Las palabras en inglés, como suenan.** En Configuración → **Cómo se
  pronuncia** hay una lista de palabras con cómo deben sonar («Just Dance» →
  «Yast Dans», «Logitech» → «Lóyitec», «PlayStation» → «Pléi Estéishon»…). La
  voz las dice así; el guion y los subtítulos siguen escritos como siempre. Ya
  viene con las marcas de tus vídeos, y puedes añadir, cambiar o quitar las que
  quieras. Vale para las voces que grabes a partir de ahora.
- **Adiós al «eco» y al zumbido entre bloques.** Cuando el Studio alargaba la
  pausa entre dos bloques, repetía en bucle un trozo de esa pausa, y si el
  trozo traía una respiración o el final de una palabra, se oía un murmullo
  repetido o un zumbido de un segundo. Ahora rellena con un fondo suave
  inventado con el mismo color que la pausa, sin repetir nada y sin copiar
  sonidos de la voz. Se nota al volver a grabar la voz.
- **Una letra suelta ya no se lee como una abreviatura.** La voz decía «Xbox
  Series sur» en vez de «Series ese»: en español, una «S» sola se tomaba por
  «Sur». Ahora cada consonante mayúscula suelta (S, X, T, B…) se deletrea con
  el nombre de la letra. «A», «E», «O», «U» e «Y» se siguen leyendo como
  palabras, y «S.A.», «T-shirt» o «USB-C» no cambian. Se nota al volver a
  grabar la voz; el subtítulo sigue diciendo «S».
- **Si se corta Cartesia a mitad, la voz ya no se paga dos veces.** Antes, si
  la conexión se caía con parte del audio ya llegado, el Studio volvía a grabar
  la voz entera por otro camino sin avisar (y Cartesia cobraba las dos) y ese
  primer intento no salía en el gasto. Ahora se para con un mensaje claro para
  que lo reintentes tú, y lo que Cartesia llegó a cobrar queda apuntado en el
  gasto del vídeo. Si no había llegado nada, sigue reintentándolo solo, como
  antes.
- **Regrabar varios tramos: si falla uno, los anteriores se guardan.** Al
  regrabar lo que has escrito en varios tramos, si fallaba el segundo se
  perdía el primero, ya pagado, y al reintentar se volvía a pagar. Ahora lo ya
  grabado queda guardado (la voz sigue marcada como pendiente) y «Regrabar lo
  que he escrito» graba solo los tramos que faltan.
- **«Carlos V» ya no se lee «Carlos uve».** Una V, X, L, C, D o M sola detrás
  del nombre de un rey, un papa o un emperador (Carlos, Felipe, Pío, León,
  Napoleón, Ramsés…) se deja como número romano, igual que ya pasaba detrás
  de «siglo» o «capítulo». «Xbox Series X», «Galaxy S» o «Plan B» se siguen
  deletreando.
- **«Escuchar» suena como el vídeo.** La muestra de voz (la de un estilo, la
  de elegir voz y la del vídeo) ahora pasa por la lista **Cómo se pronuncia**
  y deletrea las letras sueltas, como la voz del vídeo. Si cambias la lista,
  la siguiente escucha ya la recoge; si no cambias nada, se reutiliza la que
  ya habías oído y no se vuelve a pagar.
- **«Regenerar Audio» dice lo que cuesta.** Ese botón vuelve a grabar la voz
  entera, y se paga entera aunque no hayas cambiado nada. Antes se apuntaba
  como «prometido: 0 $» en «Cada vez que generaste» y la ayuda decía que lo
  que no cambió salía gratis; ahora la ayuda del botón y lo prometido dicen el
  precio de la voz entera.

**Subtítulos a tu gusto y el «atrás» del móvil (13 de octubre, noche)**
- **La fuente y el sitio de los subtítulos se eligen.** En el editor de
  subtítulos (en el Encargo y debajo del vídeo montado) hay dos filas nuevas:
  **Fuente** (la del diseño, Verdana, Arial o Georgia) y **Dónde va**
  (automática, abajo, a un tercio, en el centro o arriba). Con «Aplicar ahora»
  se rehacen las capas de texto y el montaje: ni una imagen ni la voz se
  vuelven a pagar. «La del diseño» y «Automática» lo dejan exactamente como
  estaba.
- **El diseño «Realista» ya mide su letra con Georgia.** Dibujaba Georgia pero
  medía con Verdana, que es un tercio más ancha: la caja del subtítulo salía de
  más, los renglones se partían antes de tiempo y las cartelas salían más
  pequeñas de lo que cabían. Se nota al volver a montar un vídeo con ese
  diseño; los demás diseños salen igual que antes.
- **El botón «atrás» del móvil ya no te saca del Studio.** Vuelve a la
  pantalla anterior: del Vídeo a la parada de antes, del estilo al vídeo y,
  al final, a la portada. «Adelante» lo deshace.

**Más notas de mejoras (13 de octubre)**
- **La revisión de ortografía ya no se cae por una respuesta rota.** A veces
  el corrector contestaba con algo que no se podía leer y salía «no es un JSON
  legible» y nada más. Ahora revisa por partes más pequeñas, la parte que
  llega rota la vuelve a pedir, y si aun así no sale, te enseña lo demás y te
  dice cuántos textos se quedaron sin revisar. Si no sale nada, el aviso dice
  en claro que pulses «Revisar otra vez».
- **Al aplicar las correcciones del guion, un solo aviso** con cuántas se
  pusieron y cuántas tienes que corregir a mano (y esas se quedan a la vista).
  Y cada corrección va a su palabra: «esta → está» ya no cambia la «esta» de
  dentro de «estaba».
- **Los ajustes de la voz de un estilo se guardan todos, y «Escuchar» suena
  con ellos.** Si tocabas dos mandos seguidos (la velocidad y enseguida el
  color), solo se guardaba el último. Y después de cambiar el ritmo, que mueve
  el aire de la voz, «Escuchar» repetía la muestra de antes hasta recargar la
  página.
- **Ir al estilo de un vídeo y volver ya no te saca al menú.** Desde el estilo
  de un vídeo, «‹ Volver al vídeo» te devuelve a él (también después de
  regenerar el estilo) y «Todos los estilos» abre los estilos del proyecto de
  ese vídeo, no «Tus proyectos». Y si el estilo del vídeo ya no existe,
  «Estilo» te lo dice en vez de sacarte del vídeo.
- **El dictado ya no repite palabras.** Con el dictado gratuito del navegador
  (sin clave de OpenAI), en el móvil salía «hola que talhola que tal hola que
  tal quiero un vídeo». Ahora queda lo que dijiste, una vez, y se respeta lo
  que hubieras escrito antes de pulsar el micrófono.
- **«Revisar» en el Encargo siempre te deja aplicar lo que propone.** Cuando
  la revisión decía «Sirve» pero listaba cosas a mejorar, no salía ningún
  botón: ahora sale «Aplicar la versión sugerida». Y cada mejora trae su
  propio **«Aplicar esta mejora»**, que cambia solo ese trozo del campo (útil
  con material largo, donde la revisión a veces no reescribe el texto entero).
  Si el trozo ya no está en el campo, o está varias veces, te lo dice para que
  lo cambies a mano.
- **La música, los efectos y los subtítulos, debajo del vídeo montado.** En la
  pantalla **Vídeo** sale el bloque «Música, efectos y subtítulos» (el mismo
  que había en el Encargo): cambiar la música, su volumen, los efectos o el
  aspecto de los subtítulos vuelve a montar el vídeo sin redibujar ninguna
  imagen ni regrabar la voz. Y dos cosas nuevas en la música: un **ajuste
  fino del volumen** (un deslizador, de 1 en 1 dB, encima de Suave, Normal o
  Alta) y **elegir el ánimo de la música automática** para todo el vídeo
  (alegre, gamer, rock…): busca un tema de ese ánimo para cada tramo y vuelve
  a mezclar.

**Dos de tus notas de mejoras (13 de octubre)**
- **«Un vídeo nuevo» empieza vacío** después de crear uno. Antes salía con el
  nombre, el material y las indicaciones del vídeo anterior, y se podía crear
  otro vídeo con ellos sin darse cuenta.
- **Corregir una lámina que añadiste ya no redibuja todas.** El «Regenerar»
  del estilo reconoce tus láminas añadidas y cambia solo la que nombras. Y
  avisa: para cambiar una sola lámina, lo directo es el «Regenerar» de esa
  lámina, que dibuja solo esa.

**Seguridad y no pagar dos veces (13 de octubre)**
- **El asistente ya no puede leer tus claves.** Antes, en el servidor podía
  abrir el fichero de claves, el `.env` y la sesión de Claude, porque están
  fuera de la carpeta del código. Ahora solo lee el código y tus proyectos.
- **La clave de Jamendo ya no viaja en el enlace para escuchar un tema** ni se
  guarda en el vídeo al elegirlo.
- **«Generar imágenes» espera a la cola de notas**: si se están rehaciendo
  imágenes con tus notas, te pide que esperes en vez de lanzar otra tanda
  encima (que repagaba planos o tapaba la imagen recién pagada).
- **Reintentar las láminas de un estilo que falló no vuelve a pagar las que
  ya salieron bien.** Y pulsar varias veces «Regenerar» en una lámina lanza un
  solo trabajo.
- **Una tarifa mal escrita en Configuración ya no se guarda** (dejaba sin
  «Generar» a todos los vídeos): te dice qué valor no vale.

**Tres arreglos del informe de pruebas del modo foto (12 de octubre)**
- **Si Jamendo o FreeSound no responden, el vídeo se monta igual, sin música
  o sin efectos**, y al terminar te avisa. Antes «Montar el vídeo» se caía
  entero y el error enseñaba la clave de Jamendo. La próxima vez que montes,
  vuelve a intentarlo solo; o búscalos en «Música y efectos».
- **«Probar» las claves ya no enseña la de Jamendo** cuando Jamendo no
  responde, ni nada de una clave que repita el propio servicio en su error.
- **Corregir el guion a mano ya no lo marca como «Guion obsoleto»**, y
  «Regenerar el guion» no reescribe encima de tu corrección. La voz sí queda
  por regrabar, como siempre: dice la frase de antes.
- **Las imágenes de un estilo se revisan al subirlas.** Un fichero dañado o
  que no es una imagen, una imagen diminuta o una de un solo color (toda negra)
  se rechaza en ese momento y te dice por qué. Antes se aceptaba y el estilo
  fallaba al 92 %, después de dos minutos y perdiendo el formulario.

**El coste de verdad, los efectos y descargar por partes (12 de octubre)**
- **Pulsa el coste de arriba** y sale **todo lo gastado del vídeo, desglosado**:
  imágenes nuevas, rehechas y de personajes, la voz y sus regrabaciones, Claude
  (tokens de tu suscripción), la música y los efectos (gratis, de dónde salen),
  **lo que costó su estilo**, y cada vez que generaste: **lo prometido frente a
  lo gastado**. Cada imagen va con lo que OpenAI dijo que cobró. En la ficha de
  cada estilo, **Lo que costó**.
- **El precio que se promete antes de pulsar es uno solo** y sale de lo que de
  verdad te han cobrado (la mediana de tus últimas imágenes). Antes el botón
  prometía un 30 % menos y no contaba las hojas de los personajes.
- Ya se apunta lo que antes se perdía: **regrabar un tramo**, el **taller de un
  estilo** (láminas, guía, voz), dos vídeos generando a la vez y todo lo que
  hace Claude.
- **Efectos**: ahora se **escuchan** los que eligió el automático, se puede
  **descartar** uno (✕, no vuelve a salir), **Buscar otros** y elegir **cuánto
  se oyen** (bajos, normales, altos). Solo vuelve a mezclar.
- **Descargar por partes** (junto a «Descargar»): el vídeo con lo que elijas
  —voz, música, efectos, subtítulos, logo—, cada audio suelto en WAV (como
  suena en el vídeo, alineado) o un ZIP con todo. Gratis; sin subtítulos tarda
  lo que un montaje.

**Salir al inicio, varios vídeos a la vez y volver atrás (11 de octubre, noche)**
- **Volver al inicio** desde cualquier pantalla de un vídeo: **Inicio** en la
  barra de abajo, **‹ Mis vídeos** arriba y el **logo**. «Estilo» abre el
  estilo del vídeo.
- **Cada vídeo, su progreso**: el montaje de un vídeo ya no sale ni bloquea en
  los demás, y al terminar no te saca del que estés mirando. Arriba se ve qué
  vídeo se está haciendo.
- **Las imágenes, por turnos** entre vídeos: si otro vídeo está dibujando, la
  barra dice «esperando turno» y empieza sola. Montar, voz y guion sí van a la
  vez.
- **Al regenerar el guion, las notas viejas ya no se pegan** a los planos
  nuevos: el plano nuevo con el mismo número salía retocando la imagen del
  vídeo anterior. Quedan plegadas en «Notas de una versión anterior del guion».
- **Volver a la versión anterior** del guion o de las imágenes (abajo en cada
  pantalla). Nada se borra nunca; volver a unas imágenes es gratis.
- **«Ver cómo quedó»** funciona también desde el Guion, y las miniaturas ya no
  salen rotas mientras se monta.

**Ortografía, ocultos y la prueba real (11 de octubre, tarde)**
- **Corrector de ortografía**: en el **Guion** (antes de grabar la voz, gratis)
  y en la pantalla **Vídeo** para los **subtítulos** de un vídeo ya montado.
  Propone las tildes, letras y signos que faltan; tú marcas y aplicas. En un
  vídeo hecho solo cambia el texto del subtítulo: ni voz ni imágenes, y volver
  a montar es gratis.
- Revisados **todos los textos** del Studio: 107 corregidos (sobre todo los
  mensajes de error, que iban sin tildes).
- **Proyectos ocultos**: con «Ver los ocultos», cada uno tiene **Dejar de
  ocultar** (antes solo se podía desde dentro del proyecto).
- **Quitar o devolver una lámina** se hace en la propia ficha, con su barra (ya
  no salta a la pantalla de «generando»).
- **Rehacer una imagen mientras se monta el vídeo** ya no da error: entra en la
  cola (dice qué está esperando: el montaje, la voz o la tanda en marcha) y
  arranca sola. También espera a una tanda completa que todavía va por el guion.
- La revisión de ortografía es **de su vídeo**: si cambias de vídeo no se
  aplica en el otro. En el guion, corregir no borra las **pausas** de la voz.
  Y un subtítulo corregido se deja de usar solo si después cambia lo que se
  dice en ese plano (se regraba o se vuelve a cortar): nunca enseña una frase
  que ya no se oye.
- Fuera el **menú de proyectos antiguo** y «Rendimiento» (no se veían). La
  papelera está en la portada.
- **La prueba real**: en la consola del servidor, `asvs probar` hace un vídeo
  de prueba de 30 s con tus claves (~1 $), lo comprueba solo de punta a punta
  —también si cada nota se aplicó, mirándolo con Claude— y deja un informe.
  **Si la consola se corta, la prueba sigue sola**: vuelve a escribir
  `asvs probar` para verla, o para retomarla donde se quedó si se paró. Lo ya
  hecho no se repite ni se paga dos veces, y el gasto de cada tanda se sigue
  comparando con lo prometido. `asvs probar nueva` empieza otra.

**Imágenes rehechas que «no cambiaban» (11 de octubre)**
- **«Rehacer esta imagen» retoca la de ahora** (se la pone delante al
  generador para conservar la composición), y en un cambio grande salía casi
  igual. Nuevo **«Desde cero»**: la dibuja de nuevo SIN partir de la anterior.
  En una ya hecha, **«¿Salió igual? Desde cero»**.
- La tarjeta enseña **cómo era antes** debajo de la nueva.
- **La pantalla Vídeo avisa** de que su MP4 es de antes de tus cambios (antes
  no se enteraba hasta recargar la página) y «Regenerar Vídeo» lo monta con
  las imágenes nuevas.
- «Regenerar Vídeo» **ya nunca redibuja el vídeo entero**: con el MP4 al día y
  algo menor pendiente (la música sin elegir), podía pagar todas las imágenes
  otra vez. Ahora solo rehace lo que haya quedado viejo.
- **«Arreglar los subtítulos»** en la pantalla Vídeo, para los vídeos cuya voz
  llegó con las tildes rotas («TÃº»): vuelve a dibujar los subtítulos y monta.
  No se paga nada.

**La papelera, a la vista**
- Botón **🗑 Papelera** en la portada y dentro de cada proyecto (antes solo
  se abría desde un menú que esta pantalla no enseña). Devolver un estilo lo
  devuelve con sus láminas y su escucha.

**Pantalla**
- En 19 sitios los márgenes no se aplicaban (la protección del servidor los
  bloqueaba): ya se ven.
- En el móvil, los botones de cada vídeo de la portada van debajo del nombre
  (la burbuja del asistente tapaba «Apartar»).

**Arreglos del 10 de octubre (lo que se vio abriendo un vídeo de verdad)**
- Las **fotos adjuntas a una nota** salen en miniatura (antes, a su tamaño
  real, tapando la pantalla). Pulsarlas las abre en grande.
- Pulsar **la miniatura de una tarjeta** o **Ver cómo quedó** lleva la vista
  a esa imagen (antes cambiaba arriba, fuera de la pantalla, y parecía que no
  hacía nada).
- La **narración con «TÃº», «papÃ¡»**: la voz de Cartesia se leía con la
  codificación equivocada. Las voces nuevas llegan bien; en los vídeos ya
  hechos se enseña bien y los subtítulos se dibujan bien al volver a montar,
  **sin rehacer ni pagar ninguna imagen**.
- **«Estilos» dentro de un vídeo abre el estilo de ese vídeo**, para verlo y
  cambiarlo, con **Volver al vídeo** (antes iba a la portada).
- **Revisar** ya no se pierde cuando la pantalla se refresca mientras revisa,
  y su botón es **Aplicar la versión sugerida**. Si no es «Sirve», siempre
  propone una versión.

**Imágenes con nota**
- **Una tarjeta por imagen**, en el orden del vídeo, con todas sus notas
  dentro: antes cada nota tenía su tarjeta y dos notas de la misma imagen se
  veían como «imágenes repetidas». Las ya rehechas (y miradas) se pliegan
  abajo en «Imágenes ya rehechas».
- Cada nota sale en una tarjeta con **la miniatura de su imagen**, el bloque y
  el segundo, **la frase del guion** que se oye ahí y su estado en palabras.
  «Apuntar» ahora es **Guardar nota**.
- Mientras se dibuja: **«Dibujando 0:45 de ~1:20»** (antes, un «5 %» que no se
  movía).
- La cola vive en el servidor: se dibujan **de una en una**, se puede recargar
  la página y **varias notas de la misma imagen se pagan como una**. El botón
  dice cuánto cuesta y cuánto tarda.
- **Si OpenAI rechaza una imagen** (marcas, logos, personajes con derechos):
  se reintenta sola **sin marcas**, lo más parecida posible; si aun así no,
  la nota lo explica y ofrece **Hacerla sin marcas** (texto propuesto y
  editable). Un rechazo ya no para las demás ni sale como error en el Encargo.

**Música y efectos**
- **24 ánimos** (alegre, divertido, gamer, infantil, lo-fi, rock…),
  **búsqueda libre**, **Ver más**, **Solo instrumental** y **Solo uso
  comercial**.
- **Sube tu música** (MP3, WAV, M4A) para usarla en el vídeo.
- **Efectos** en Encargo → Ajustes del montaje: cada sonido automático,
  buscado en FreeSound o **subido por ti**.

**Corregido**
- **Ver los ocultos** no enseñaba el proyecto oculto (un choque de estilos lo
  escondía). Y en general, lo marcado como «escondido» ya se esconde siempre.
- **Revisar** encontraba «errores» nuevos en cada vuelta: ahora el mismo texto
  recibe la misma respuesta y la versión sugerida, revisada, sale «Sirve».
- Los avisos de error del vídeo se pueden **cerrar**.

**Para quien mantiene el Studio**
- `prueba_recorrido.py`: abre la pantalla con un navegador y la recorre
  entera pulsando como una persona (con imágenes, voz y Claude simulados y un
  vídeo de prueba), dejando capturas. Va dentro de `pruebas.sh`.

## V2.0 · octubre de 2026 (las láminas de tu estilo)

**Las láminas, a la vista y a mano** (ficha del estilo → Estilo gráfico)
- Explicado qué es una lámina: lo que de verdad copia cada plano de cada
  vídeo. Tus imágenes escriben la guía (todas) y dibujan las láminas (8 por
  lámina); cada plano recibe las láminas.
- Cada lámina se ve limpia, con lo que enseña, y se puede **Regenerar** (con
  una corrección opcional), **Cambiar qué enseña**, **Quitar** (gratis, y
  **Devolver** también) o **Añadir** otra, hasta 8. Antes de pulsar se ve lo
  que cuesta.
- Si subiste más de 8 imágenes: **un grupo distinto para cada lámina**, para
  que cuenten todas (mismo coste).
- **Tus imágenes de referencia** en la ficha: se ven en grande, se describen y
  se marcan con ★ sin gastar nada; se pueden quitar o sumar otras nuevas.
- El texto de las muestras («10.000.000 cuentas a la venta»…) ahora dice lo
  que es: un texto de ejemplo del Estudio, no algo tuyo.
- **Corregido**: cambiar solo las *Indicaciones* del estilo gráfico en la ficha
  daba «falta el estilo gráfico». Ahora conserva tus imágenes.
- **Corregido**: **Guía** y **✓ Revisar** miraban el primer campo del bloque
  (en el tono, la guía de dos mil palabras); ahora miran el campo que toca.

**Otros**
- El asistente deja escribir mientras piensa (lo que espera es el envío).
- **Hora de tu región** con buscador.
- La lista de voces se filtra por voz de hombre o de mujer y por país.

## V2.0 · octubre de 2026 (proyectos, logo y revisar)

**Proyectos (clientes)**
- Barra de **Proyectos** arriba de tus estilos: una carpeta por cliente.
  - Los estilos que creas con un proyecto abierto quedan dentro, y sus vídeos
    van con ellos.
  - Cada proyecto se puede renombrar, ocultar, ponerle clave o borrar. Borrarlo
    no borra sus estilos ni sus vídeos.
- En **Tus vídeos** cada vídeo dice de qué estilo (🎨) y de qué proyecto (📁)
  salió.

**Música, subtítulos y logo de cada vídeo** (Encargo → Qué lleva este vídeo)
- **Elegir la música**: busca temas de Jamendo por ánimo, escúchalos ahí y
  fija uno; o deja la automática.
- **Personalizar los subtítulos**: tamaño, letra y forma, caja y color; o los
  del estilo.
- **Logo**: sube una imagen y elige la esquina, el tamaño y la opacidad.
- Ninguno paga imágenes: la música y el logo solo vuelven a montar el vídeo.

**✓ Revisar**, al lado de cada **Guía**
- Comprueba lo que has escrito en ese campo contra su guía: dice si sirve, qué
  falla y por qué, y propone una versión que puedes poner con un botón.
- Va con tu suscripción de Claude: no cuesta imágenes.

**La voz, con escucha**
- Al crear un estilo, la voz se elige en una lista con **▶** en cada voz para
  oírla antes, igual que en un estilo ya creado.
- En la ficha del estilo la voz ya no está escondida en «Opciones avanzadas»,
  y arriba se ve cómo se pidió.
- **Corregido**: si un estilo se quedaba a medias y se retomaba después de
  cambiar la voz, salía con la voz del primer intento. Ahora la vuelve a elegir.

**Imágenes de referencia**
- Las miniaturas son el doble de grandes, y al pulsar una se ve en grande, con
  ← y → para pasar de una a otra.
- **★** marca las que deben ir sí o sí a la hoja con la que se dibujan las
  láminas (8 como mucho).

**El asistente**
- Desde el **Historial** ya se puede escribir y empezar una charla nueva.
- El cursor vuelve solo al campo cuando contesta.

**Todos los campos de texto crecen con lo que escribes**, hasta el 60 % de la
pantalla, y desde ahí tienen su propia barra. Antes muchos se quedaban en dos
líneas y cortaban el texto.

**Ayuda**: «Cómo se usa» puesto al día con todo esto, y con un apartado sobre
los derechos de la música, la voz y los efectos.

## V2.0 · octubre de 2026 (arreglos antes de la fase 3)

**Corregido: generar imágenes fallaba con «No such file or directory … .tmp»**
- En el servidor (Linux), dos imágenes que se generaban a la vez y compartían
  una referencia (el estilo, un personaje) preparaban su copia con el MISMO
  nombre temporal; la segunda se encontraba la suya movida y la tanda se caía.
  Ahora cada copia tiene un nombre único, y si otra ya dejó el fichero listo
  se usa ese.

**Corregido: crear un estilo fallaba al 89 % con «la previa salió en blanco»**
- La comprobación que detecta que el navegador ha fotografiado su página de
  error miraba si la esquina de la imagen era casi blanca. Con un estilo
  **fotográfico** (paredes blancas, interiorismo) la esquina de una imagen
  buena también lo es, y el estilo se tumbaba siempre en el mismo sitio.
- Ahora la página lleva una señal invisible que se comprueba y se borra: un
  plano claro ya no se confunde con un error, y un error de verdad se sigue
  cazando.
- Las direcciones de los ficheros que se le dan al navegador se escriben bien
  en Linux y van codificadas: una carpeta con acentos, espacios o «#» ya no da
  una página de error. Si una previa vuelve a fallar, el aviso dice qué página
  y qué imagen se intentaron abrir, y la página se guarda para revisarla.

**Corregido: las imágenes de un estilo acumulaban «00_00_00_…» en el nombre**
- Cada vez que se guardaba un estilo se añadía otro prefijo de orden al nombre
  de sus imágenes, y como la carpeta vieja se sustituía, los vídeos hechos con
  ese estilo dejaban de encontrarlas («ninguna de las imágenes de estilo existe
  en el disco del servidor»). Ahora el nombre se queda en `00_cara.png`
  aunque se guarde mil veces.
- Para los vídeos que ya se rompieron hay una herramienta que solo mira
  (`herramientas/diagnostico_estilo.py`): dice qué rutas guardan, qué hay en
  disco y propone cómo repuntarlas sin regenerar nada.

**Estilos: hasta 50 imágenes de referencia, cada una con su descripción**
- Antes cabían 24. La guía del estilo las mira todas; para dibujar las láminas
  se usan ocho como mucho (con más, cada foto de la hoja quedaba diminuta).
- **Describir las imágenes (opcional)**, debajo de las miniaturas: una frase
  por imagen («la luz de esta», «solo el mueble, no el fondo»). Llega a quien
  escribe la guía con el nombre de su fichero. Las imágenes con descripción
  llevan un ✎.

**La voz al crear un estilo**
- **Voz concreta (opcional)** ya ofrece el catálogo entero de Cartesia del
  idioma, además de tus voces clonadas. Sin elegir, la escoge el sistema por la
  descripción, como antes. Escucharlas y compararlas sigue en el estilo ya
  creado: Voz → Opciones avanzadas.
- Cómo usar tu propia voz: clónala en play.cartesia.ai con la misma cuenta
  cuya clave está en Configuración y pulsa **Buscar mis voces otra vez** (la
  lista se guardaba siete días y una voz recién clonada no salía).

**El asistente, con sitio para escribir y leer**
- El campo crece con lo que escribes o dictas, hasta un tercio del panel.
- **Ampliar** (arriba del panel) lo hace más ancho y alto, para leer
  respuestas largas; **Reducir** lo devuelve. Se recuerda en ese navegador.

**La hora de tu región**
- **Configuración → Hora de tu región**: elige tu zona (o «Usar la de este
  navegador») y el Estudio apunta las horas del chat, los vídeos y las notas
  en ella. Lo apuntado antes conserva la hora que tenía.

**Ayuda: «Cómo se usa»**
- Botón **?** arriba a la derecha, o **Configuración → Cómo se usa**: qué es
  cada pantalla, cada campo y qué cuesta cada botón. El asistente lee la misma
  guía.
- «Empezar de cero» ahora explica qué hace: olvida el intento a medias y lo
  genera todo otra vez (se vuelve a pagar); «Retomar» aprovecha lo ya hecho.
  Pide confirmación.

**Corregido: la música no se oía aunque estuviera marcada**
- La música sí iba en el vídeo, pero se agachaba tanto bajo la voz (unos
  25 dB) que no se oía mientras se habla, y tardaba tanto en volver que
  tampoco subía en las pausas: solo asomaba en los segundos negros del final.
- Ahora, por defecto, queda **de fondo y audible** (unos 15 dB por debajo de
  la voz) sin tapar lo que se dice.
- Nuevo en **Encargo → Qué lleva este vídeo**, debajo de los interruptores,
  cuando la música está encendida: **«Cuánto se oye la música»** con tres
  niveles:
  - **Suave**: como antes, casi no se oye bajo la voz.
  - **Normal** (por defecto): de fondo, sin tapar la voz.
  - **Alta**: música protagonista, se nota mientras se habla.
- Cambiarlo en un vídeo ya montado **solo vuelve a mezclar el audio**: no se
  dibuja ni se paga ninguna imagen, y tarda lo que tarda el montaje final. Si
  el vídeo tiene planos pendientes, el nivel se guarda y se aplica al volver
  a montarlo.
- Los vídeos ya montados siguen sonando como estaban hasta que se vuelvan a
  montar o se elija un nivel.

---

## Etapa Foto A · octubre de 2026 · foto realista

**Tipo de imagen: Ilustración o Foto realista**
- Al crear un estilo, el bloque **«Estilo gráfico»** tiene un selector nuevo,
  **«Tipo de imagen»**. Por defecto queda en **Ilustración**, que es lo de
  siempre: los estilos y vídeos que ya tienes no cambian y **no se vuelve a
  pagar ninguna imagen**.
- Con **Foto realista**, el Studio genera **fotografías** en vez de dibujos,
  para **cualquier proyecto**:
  - la guía del estilo se escribe **para foto** (cámara y lente, luz, color,
    gente real, lugares, acabado) en vez de para dibujo (trazo, relleno, dedos);
  - cada plano se pide como **una foto de un fotógrafo profesional**, y las
    láminas de referencia también salen como fotos;
  - entran **reglas propias de foto**, para cualquier tema: piel real, manos de
    cinco dedos que sostienen bien las cosas, gente que no posa, luz coherente
    entre planos, sin logos de otras marcas y nada de aspecto de render;
  - las **caras** tienen expresiones naturales, como las pillaría una cámara:
    nada de «prohibido sonreír» en una fiesta ni de sonrisas de catálogo;
  - los planos se reparten con **encuadres de foto**: plano general, picado,
    plano medio, sobre el hombro, perfil, reacción, manos en la acción,
    detalle, objeto en primer término, retrato, contraluz y a ras de suelo.
- **Cuando el vídeo va de consolas** (lo dicen el estilo, el guion o una nota
  de revisión: consolas, mandos, videojuegos, simuladores, VR, karaoke), se
  suman solas las reglas y los encuadres de **EstadoPlay**: mandos sujetos con
  las dos manos, televisores siempre sobre su trípode, consolas nunca en el
  suelo, cables sin flotar, estación completa, pies en los pedales (solo con
  simuladores), cuerpo con visor (solo con realidad virtual). En un vídeo de
  cualquier otra cosa no aparecen.
- **La calidad de imagen**:
  - los vídeos nuevos arrancan con la calidad de **Configuración → Calidad de
    las imágenes**. Hasta ahora los vídeos creados desde un estilo **la
    ignoraban** y salían siempre en LOW;
  - los vídeos con un estilo de **Foto realista** arrancan como mínimo en
    **MEDIUM**: en LOW la piel sale lisa y la foto parece de plástico. Cuesta
    unas 1,7 veces más por imagen (no 6,8: las referencias se pagan igual).
    Con HIGH en Configuración, se respeta HIGH;
  - la cifra «El vídeo entero: … $» de «Un vídeo nuevo» ya cuenta con esa
    calidad.
- En un estilo **ya guardado** también está el selector, en «Estilo gráfico»:
  cambiarlo y pulsar **Regenerar** rehace la guía y las láminas **con las
  mismas imágenes**, y deja el tono, la voz y el ritmo como están. Cuesta lo
  mismo que rehacer el estilo gráfico.
- Las imágenes que subas a un estilo de foto deberían ser **fotos**: el
  sistema las mira para escribir la guía.
- Todavía no entran aquí los productos de la marca como referencia (Etapa B) ni
  los presets de marca, evento y servicio (Etapa C).

## V2.0 · octubre de 2026 (tercera parte)

**El guion: regrabar, añadir y partir bloques**
- **Corregido: «Solo regrabar lo que he escrito» no se veía.** El audio se
  grababa pero no se registraba como versión nueva: la pantalla seguía con el
  texto de antes, la voz en «obsoleto» y una segunda regrabación se llevaba la
  primera. Ahora queda guardado, la voz pasa a «al día» y el reproductor suena
  con lo nuevo.
- Si editas bloques de **varios tramos** del audio, se regraban **todos los
  tramos con cambios** de una vez. Una barra arriba del guion avisa de que hay
  cambios sin grabar y dice **cuánto cuesta regrabarlos antes de pulsar**.
- Un bloque editado y todavía sin grabar enseña **lo que escribiste** (en
  cursiva), no la frase vieja.
- **«+ Añadir bloque»**: escribe el texto y elige dónde va: antes o después de
  un bloque concreto, al principio o al final. Los bloques añadidos llevan la
  etiqueta «añadido» y se pueden **quitar**.
- **«Partir»** en cada bloque: pon el cursor donde quieras cortar y pulsa
  «Cortar aquí», tantas veces como quieras. El primer trozo se queda en el
  bloque y el resto pasan a ser bloques nuevos justo debajo.
- Ningún bloque cambia de número: los nuevos reciben el siguiente libre
  (B041, B042…). Las imágenes de los planos que siguen diciendo lo mismo **se
  conservan**; al generar el vídeo solo se pagan las de los planos con texto
  nuevo.
- En el móvil, los botones de cada bloque (Partir, Editar, Cambiar) ya se ven
  sin tener que pasar el ratón por encima.

**Traer los cambios del estilo a un vídeo**
- Un vídeo se queda con el estilo **tal como era el día en que se creó**: así,
  retocar el estilo no deja obsoletas las imágenes ya pagadas de los vídeos en
  curso.
- Nuevo bloque **«Su estilo»** en el Encargo de cada vídeo: dice qué partes del
  estilo han cambiado (estilo gráfico, tono del guion, voz, rótulos), qué
  habría que rehacer según la etapa en que esté el vídeo y **cuánto costaría**,
  y trae solo lo que marques.
- El bloque vuelve a comparar con el estilo **cada vez que abres el Encargo**
  (corregido: se quedaba con la primera comparación y no veía un cambio hecho
  después, como el aire entre bloques).
- Después de traer, un aviso **«Siguiente paso»** (en el Encargo y en el Guion)
  dice qué hay que pulsar, con su botón y su coste: regenerar el guion si
  cambió el tono, **regrabar el audio** si cambió la voz, o poner al día las
  imágenes si cambió el estilo gráfico.
- Cuando el guion queda marcado como viejo, el aviso dice **por qué** («cambió
  la duración», «cambió el tono»…) y ofrece dos caminos: **regenerarlo** con lo
  nuevo, o **grabar el audio con el texto tal cual** si ya te sirve.
- Traer **no genera nada**: deja marcado lo que quedó viejo y se rehace al
  pulsar Generar. No pisa lo propio del vídeo: duración, formato, llamadas a la
  acción, indicaciones, qué lleva y lo editado a mano en el guion.

**Las pausas se hacen al montar, y la voz se graba de corrido**
- Las pausas del **final de cada bloque** (después del gancho, antes de cada
  cambio de tema) ya no se le piden a la voz: la voz se graba seguida y el
  silencio se añade al montar, con la misma duración. Así la narración no se
  corta ni suena a lista leída, dure el vídeo lo que dure y con cualquier IA de
  voz.
- Solo cuentan para el aviso las pausas **dentro de una frase**, que son las que
  cortan la voz. Cada bloque lo muestra: «⏸ 0,9 s al final» (sin problema) o
  «⏸ 0,9 s dentro».
- Al regrabar un tramo suelto, sus bloques ya respetan el aire entre bloques
  (antes quedaban pegados).
- Vale para los guiones que ya tienes: se aplica la próxima vez que se grabe o
  se regrabe el audio.

**Las pausas largas del guion, a la vista**
- Cada bloque que lleva una pausa larga invisible (`<break>`) muestra la
  etiqueta **«⏸ pausa 0,9 s»** y un botón **«Quitar pausa»**, que la quita sin
  tocar el resto del bloque.
- Arriba del guion, el aviso de pausas se calcula con el **texto de ahora**
  (contando lo editado a mano), dice en qué bloques están y cuántas conviene
  dejar, y ofrece **«Quitar las sobrantes»**: deja la del principio y las de
  cambio de tema. Es gratis; si ya había audio, hay que regrabarlo.

**El asistente: dictar las preguntas con la voz**
- Botón **«🎙 Hablar»** junto a «Imagen»: pulsas, hablas y pulsas «Parar». El
  texto aparece en la caja para que lo revises y lo envíes; no se manda solo.
- Con una clave de OpenAI en Configuración, el audio se pasa a texto en el
  servidor (cualquier navegador, buen castellano; un minuto ≈ 0,003 $). Sin
  clave, usa el dictado del propio navegador (Chrome, Edge, Safari), gratis.
- La primera vez el navegador pide permiso para el micrófono. Hasta 3 minutos
  por dictado.
- El botón dice con qué se va a dictar: **«🎙 Hablar · OpenAI»** o **«🎙 Hablar
  · navegador»**. En **Configuración → Dictado al asistente** se puede elegir
  **«Siempre el del navegador (gratis)»** para no gastar nada al dictar.

**El asistente: historial de charlas**
- Botón **«Historial»** en la burbuja: las charlas de antes, con su primera
  pregunta y la fecha. Se abren para leerlas o **seguir donde se quedaron**, y
  la × las borra.
- Se guardan en el servidor junto a tus datos: sobreviven a recargar, a
  reiniciar el servicio y a `asvs actualizar`. «Nueva» ya no borra la anterior.

## V2.0 · octubre de 2026 (segunda parte)

**Qué lleva cada vídeo**
- Al crear un vídeo, el bloque **«Qué lleva este vídeo»** tiene cuatro
  interruptores: **voz, subtítulos, música y efectos**. Lo apagado no se
  produce: sin música no se busca banda sonora, sin efectos no se buscan
  sonidos, sin subtítulos no se dibujan.
- Se puede cambiar después desde el **Encargo** del vídeo. Solo se rehace el
  montaje (el MP4): **ninguna imagen se vuelve a pagar**.
- La **voz** se ve pero todavía no se puede apagar: todo el montaje se
  cronometra con la locución. El vídeo sin voz llega en la siguiente parte.

**Español de Latinoamérica**
- Nueva opción **«Español (Latinoamérica)»** en el idioma del estilo. El guion
  se escribe en español latinoamericano neutro («ustedes», computadora,
  celular, departamento…) y la voz se elige con acento latino.
- Se puede cambiar en un estilo ya creado (Nombre e idioma), sin regenerar
  imágenes.

**Guía de inicio**
- Tarjeta nueva **«Cómo se trabaja»** con lo de la V2.0: guías, qué lleva cada
  vídeo, español de Latinoamérica, duración, asistente con imágenes, novedades
  y notas. Se vuelve a ver desde Configuración → «Volver a ver la guía de
  inicio».

## V2.0 · octubre de 2026

**Nombre y aspecto**
- El sistema pasa a llamarse **Automatización Contenido Studio** en toda la
  interfaz y en la pantalla de acceso. Los nombres internos del servidor
  (`/opt/as-video-studio`, el comando `asvs`, los servicios) no cambian, para
  no romper las instalaciones que ya funcionan.
- Diseño nuevo: letra Plus Jakarta Sans, colores violeta y coral, botones y
  tarjetas con degradado.
- **Modo claro y modo oscuro**, con el botón de sol/luna de la cabecera. Cada
  navegador recuerda el suyo.
- Pie de página con los derechos: Agencia Redes Botánica · Octubre 2026 · V2.0.
- Mejoras para el móvil: la cabecera muestra el nombre corto, el medidor de
  coste se parte en dos líneas en vez de cortarse y la burbuja del asistente se
  puede minimizar.

**Al crear un vídeo**
- La duración va de **1 s a 30 min**, con la cifra grande, minutos y segundos
  por separado y atajos (15 s, 30 s, 1 min… 30 min). Por debajo de 10 s el
  sistema hace el vídeo de 10 s y lo avisa: no cabe una frase narrada en menos.

**Guías de escritura**
- Botón **«Guía»** junto a cada campo de texto: indicaciones del estilo
  gráfico, tono del guion, voz, material, indicaciones del vídeo y llamadas a
  la acción. Cada guía explica qué hace el sistema con ese texto, qué sí y qué
  no, una plantilla para copiar, un ejemplo y un **prompt para pegar en otra IA**
  (ChatGPT, Claude) junto con tus notas, que te devuelve el texto ya en la forma
  que el sistema entiende.

**El asistente**
- Se le pueden **pegar o adjuntar imágenes** (hasta 6 por pregunta): capturas
  de un error, una referencia, una imagen que no salió bien.
- La burbuja se puede **minimizar** a una pestaña pequeña en el borde.
- Conoce las guías de escritura, este historial y tus notas de mejoras, y puede
  ayudarte a reescribir un texto para que encaje con el sistema.

**Configuración**
- Sección **Novedades** (esta lista) y sección **Notas de mejoras**: apunta lo
  que quieras corregir o añadir más adelante; se guarda en el servidor, se puede
  marcar como hecha y el asistente la lee.

## Correcciones de octubre de 2026 (antes de la V2.0)

- **Crear un estilo** fallaba al dibujar las láminas con «generar() necesita al
  menos una imagen de referencia»: ahora las láminas se dibujan con las imágenes
  que subiste.
- **Generar imágenes** fallaba al instante con «KeyError: 'fijos'»: corregido.
- El instalador ya no deja una instalación sin contraseña si falla el listado de
  cuentas, y abre el puerto real del SSH antes de encender el cortafuegos.
- `asvs actualizar` no corta una tanda en marcha (salvo con `--forzar`), vuelve
  a arrancar el estudio si algo falla a medias y recuerda de qué repositorio se
  descarga (`asvs repositorio`).
- Con la sesión abierta, abrir la pantalla de acceso ya no lleva a un error 404.
- Si falta la clave de Jamendo o de FreeSound, el aviso manda a Configuración.
- Las pruebas corren en Linux (`bash pruebas.sh`).

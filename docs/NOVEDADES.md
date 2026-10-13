# Novedades de Automatización Contenido Studio

Lo que ha cambiado en el sistema, de lo más nuevo a lo más antiguo. Se ve en
**Configuración → Novedades**, y el asistente lo lee para estar al día.

Para actualizar el servidor: en la consola del VPS, `asvs actualizar`. Tus
vídeos, estilos, claves y contraseña no se tocan.

---

## V2.0 · octubre de 2026 (imágenes, música y efectos, y un recorrido de toda la pantalla)

**Tres arreglos del informe de pruebas del modo foto (12 de octubre)**
- **Si Jamendo no responde, el vídeo se monta igual, sin música**, y al
  terminar te avisa de que ha salido sin ella. Antes «Montar el vídeo» se caía
  entero y el error enseñaba la clave de Jamendo. La próxima vez que montes,
  vuelve a intentar la música sola; o móntala en «Música y efectos».
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

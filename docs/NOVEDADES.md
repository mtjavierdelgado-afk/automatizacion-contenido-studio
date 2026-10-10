# Novedades de Automatización Contenido Studio

Lo que ha cambiado en el sistema, de lo más nuevo a lo más antiguo. Se ve en
**Configuración → Novedades**, y el asistente lo lee para estar al día.

Para actualizar el servidor: en la consola del VPS, `asvs actualizar`. Tus
vídeos, estilos, claves y contraseña no se tocan.

---

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

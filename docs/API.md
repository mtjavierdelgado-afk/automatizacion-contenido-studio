# La API

Todo lo que sirve `app.py`, sacado del propio código: ruta, verbo y la primera
frase del docstring de cada endpoint. **Este fichero no se escribe a mano**: lo
escribe `generar_api.py`, y `prueba_api.py` comprueba que no se quede viejo.

Reglas que valen para toda la API y no se repiten en cada fila:

- **Un endpoint por cosa que sabe hacer el núcleo.** La pantalla no calcula
  estado: lo pide. Ver [README.md](../README.md).
- **Los errores hablan castellano.** `ErrorApi(codigo, "frase")` sale como
  `{"error": {...}}` con la frase que lee una persona y el detalle técnico
  aparte.
- **Nada bloquea.** Lo que tarda devuelve `202` con `trabajo_id`, y el progreso
  se sigue por `GET /api/trabajos/{tid}` o por el `eventos` que devuelve.
- **Editar es decidir.** No hay endpoint de «guardar y confirmar»: `PUT` guarda,
  y pasar de paso es aprobar.
- **Los ajustes del montaje aceptan `remontar: false`** (sonido, presencia,
  efectos, su volumen, los vetos y el logo; en la subida del logo, `?remontar=0`):
  se guardan sin montar y dejan la marca `montaje_pendiente` en `proyecto.json`
  (fuera de los params, no mueve ninguna firma). `GET .../montaje` la enseña como
  `sin_aplicar` (y `solo_mezcla` si basta con volver a mezclar), y
  `POST .../montaje/aplicar` lo monta todo en un solo trabajo. Es lo que usa el
  Encargo (19-10-2026).


## Proyectos y papelera

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos` | Proyectos disponibles, del mas reciente al mas antiguo. |
| `POST` | `/api/proyectos` | Crea un proyecto nuevo a partir de {"nombre"}. |
| `DELETE` | `/api/proyectos/papelera` | Vacia la papelera entera. Tampoco tiene vuelta atras. |
| `GET` | `/api/proyectos/papelera` | Proyectos apartados, del mas recientemente apartado al mas antiguo. |
| `DELETE` | `/api/proyectos/papelera/{carpeta}` | Borra DE VERDAD un proyecto apartado. No hay vuelta atras. |
| `GET` | `/api/proyectos/papelera/{carpeta}` | Que hay dentro de un proyecto apartado, para poder decir que se pierde. |
| `POST` | `/api/proyectos/papelera/{carpeta}/restaurar` | Devuelve a su sitio un proyecto apartado. |
| `DELETE` | `/api/proyectos/{pid}` | Mueve el proyecto a la papelera. No borra nada. |
| `GET` | `/api/proyectos/{pid}` | Estado del proyecto: los ocho pasos, sus params, versiones y trabajos. |
| `PUT` | `/api/proyectos/{pid}` | Cambia el nombre VISIBLE del proyecto. -> la ficha. |
| `POST` | `/api/proyectos/{pid}/duplicar` | Copia un proyecto entero con lo que tiene puesto HOY. -> el nuevo. |
| `POST` | `/api/proyectos/{pid}/escenas/{sid}/vale` | «Este dibujo me vale para lo que dice ahora». -> {ok} |
| `GET` | `/api/proyectos/{pid}/espacio_fijo` | El espacio fijo guardado del video ({} si no tiene) y los planos que cambiarian. |
| `POST` | `/api/proyectos/{pid}/espacio_fijo/aplicar` | Guarda el espacio fijo de un video hecho y ajusta su catalogo. No dibuja nada. |
| `GET` | `/api/proyectos/{pid}/espacio_fijo/imagen` | La imagen de referencia del espacio fijo de este video. |
| `POST` | `/api/proyectos/{pid}/espacio_fijo/rehacer` | Rehace SOLO los planos pedidos de los que cambian con el espacio fijo (se paga). |
| `POST` | `/api/proyectos/{pid}/exportar` | Prepara el vídeo, o una parte, para descargar (gratis, no toca el proyecto). |
| `GET` | `/api/proyectos/{pid}/exportes/{ruta:path}` | Un fichero preparado por /exportar, para descargar con su nombre. |
| `POST` | `/api/proyectos/{pid}/feedback` | Feedback general o sobre una unidad; rehace SOLO lo que apunta. |
| `GET` | `/api/proyectos/{pid}/lleva` | Lo que lleva este video: voz, subtitulos, musica y efectos. |
| `PUT` | `/api/proyectos/{pid}/lleva` | Enciende o apaga lo que lleva el video. Rehace solo el montaje, nunca imagenes. |
| `GET` | `/api/proyectos/{pid}/logo` | El logo de este video y donde va, o null si no lleva. |
| `POST` | `/api/proyectos/{pid}/logo` | Sube el logo (PNG con transparencia, mejor) y lo pone arriba a la derecha. |
| `PUT` | `/api/proyectos/{pid}/logo` | Donde va y como: {posicion?, tamano? (0,04-0,4), opacidad?} o {quitar: true}. |
| `GET` | `/api/proyectos/{pid}/logo/imagen` | — |
| `PUT` | `/api/proyectos/{pid}/musica/animo` | Rehace la música AUTOMÁTICA con un ánimo para todo el vídeo, y remezcla. |
| `GET` | `/api/proyectos/{pid}/musica/presencia` | Cuánto se oye la música bajo la voz en este vídeo, y los niveles que hay. |
| `PUT` | `/api/proyectos/{pid}/musica/presencia` | Fija cuánto se oye la música y, si el vídeo ya está montado, lo REMONTA. |
| `POST` | `/api/proyectos/{pid}/ortografia/aplicar` | Pone los subtitulos corregidos: {cambios: {plano: texto}}. |
| `POST` | `/api/proyectos/{pid}/ortografia/descartar` | Lo que se deja SIN marcar al aplicar: {rid, ids: [...]}. Esos textos se |
| `POST` | `/api/proyectos/{pid}/ortografia/revisar` | Revisa la ortografia de {fuente: "subtitulos"} (los del video) o de {fuente: "guion", textos}. Con `modo: "editorial"` (solo el guion) es la REVISION EDITORIAL: sintaxis y redaccion (sonnet, esfuerzo medio); el resultado (`GET .../ortografia/{rid}`, `fuente: "editorial"`) trae `propuestas: [{id, bloque, original, propuesta, motivo, tipo}]` y no escribe nada: la pantalla aplica cada una como una edicion a mano. |
| `GET` | `/api/proyectos/{pid}/ortografia/{rid}` | Como va la revision de ortografia, y lo que propone al terminar. |
| `GET` | `/api/proyectos/{pid}/planos/montaje` | {video, planos: {sid: {movimiento?, profundidad?}}, no_aplica, niveles, profundidad} |
| `PUT` | `/api/proyectos/{pid}/planos/{sid}/montaje` | {movimiento?: quieto|sobrio|vivo|dinamico|null, profundidad?: true|false|null} |
| `POST` | `/api/proyectos/{pid}/presets-canal/{preset_id}/aplicar` | Copia los valores del preset a los params de los pasos que toque. |
| `GET` | `/api/proyectos/{pid}/previsualizacion` | Las piezas para ver el video sin montarlo. -> {escenas, audio, ...} |
| `PUT` | `/api/proyectos/{pid}/redactor` | Guarda el prompt escrito de cada plano. Un prompt vacío lo quita. |
| `POST` | `/api/proyectos/{pid}/redactor/proponer` | Escribe el prompt de cada plano, con TODOS los planos delante de una vez. |
| `POST` | `/api/proyectos/{pid}/reparar-estilo` | Repunta las imagenes de estilo perdidas a las que SI estan. No regenera. |
| `GET` | `/api/proyectos/{pid}/repaso` | Las notas escritas sobre el vídeo montado, con los cortes para anclarlas. |
| `POST` | `/api/proyectos/{pid}/repaso` | Una nota nueva, anclada al segundo en el que se pausó. |
| `POST` | `/api/proyectos/{pid}/repaso/aplicar` | Aplica las notas del repaso y vuelve a generar SOLO lo que cambian. |
| `POST` | `/api/proyectos/{pid}/repaso/imagenes` | Las imágenes de referencia que acompañan a una nota. |
| `GET` | `/api/proyectos/{pid}/repaso/imagenes/{nombre}` | Una imagen de referencia de una nota. |
| `DELETE` | `/api/proyectos/{pid}/repaso/{nid}` | Quita una nota del repaso. |
| `PUT` | `/api/proyectos/{pid}/repaso/{nid}` | Cambia el texto, el instante o las imágenes de una nota. |
| `POST` | `/api/proyectos/{pid}/repaso/{nid}/sin-marcas` | Propone la nota reescrita sin marcas ni personajes: NO la guarda. |
| `GET` | `/api/proyectos/{pid}/subtitulos` | Como son los subtitulos de este video, y si son los del estilo. |
| `PUT` | `/api/proyectos/{pid}/subtitulos` | {tam?, caja? ("auto" o 0-1), diseno?, color? ("#rrggbb" o ""), |
| `POST` | `/api/proyectos/{pid}/subtitulos/aplicar` | Rehace las capas de texto y vuelve a montar el video. Ni una imagen. |
| `POST` | `/api/proyectos/{pid}/subtitulos/rehacer` | Rehace los subtitulos (y monta) de un video cuya voz llego con las |
| `GET` | `/api/proyectos/{pid}/subtitulos/rotos` | {planos}: cuantos planos tienen los subtitulos dibujados con las tildes |

## Pasos: estado, params y ejecución

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos/{pid}/pasos` | Resumen del DAG con el estado de cada paso. |
| `GET` | `/api/proyectos/{pid}/pasos/{paso}` | Detalle de un paso: params, salidas, unidades y versiones. |
| `POST` | `/api/proyectos/{pid}/pasos/{paso}/ejecutar` | Lanza el paso en segundo plano y devuelve el id del trabajo. |
| `PUT` | `/api/proyectos/{pid}/pasos/{paso}/params` | Actualiza los parametros del paso; la obsolescencia cae en cascada sola. |
| `POST` | `/api/proyectos/{pid}/pasos/{paso}/revertir` | Activa una version anterior del paso; nada se borra. |
| `GET` | `/api/proyectos/{pid}/pasos/{paso}/versiones` | Historico de versiones del paso. |

## Trabajos en marcha

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/trabajos` | Trabajos conocidos, opcionalmente de un solo proyecto. |
| `GET` | `/api/trabajos/{tid}` | Estado y progreso de un trabajo. |
| `POST` | `/api/trabajos/{tid}/cancelar` | Pide la cancelacion cooperativa de un trabajo. |
| `GET` | `/api/trabajos/{tid}/eventos` | Progreso del trabajo en vivo por Server-Sent Events. |

## Recetas y pestañas

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos/{pid}/generar` | Lo que va a hacer, cuanto tarda y cuanto cuesta. NO lanza nada. |
| `POST` | `/api/proyectos/{pid}/generar` | Recorre varias pestanas seguidas, en orden, en UN trabajo. |
| `GET` | `/api/proyectos/{pid}/pestanas/{pestana}` | Que le falta a esta pestana para estar terminada. |
| `POST` | `/api/proyectos/{pid}/pestanas/{pestana}/generar` | Un boton: hace todo lo de esta pestana, en orden y en paralelo lo que se pueda. |
| `GET` | `/api/recetas` | El catalogo de tareas por pestana y las recetas guardadas. |
| `POST` | `/api/recetas` | — |
| `DELETE` | `/api/recetas/{rid}` | — |

## Coste y bitácora

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/coste/global` | Agregado de todos los videos, con el desglose de cada uno. |
| `GET` | `/api/coste/tarifas` | Tabla de tarifas. Vive en un unico sitio: estudio/tarifas.json. |
| `PUT` | `/api/coste/tarifas` | Actualiza tarifas.json. Sirve para rellenar el precio por caracter. |
| `GET` | `/api/proyectos/{pid}/bitacora` | Historial estructurado del proyecto. |
| `GET` | `/api/proyectos/{pid}/bitacora/llm` | Historial en texto navegable, pensado para darselo a un LLM. |
| `GET` | `/api/proyectos/{pid}/coste` | Total del video, desglosado por proveedor, con la linea de cabecera. |
| `GET` | `/api/proyectos/{pid}/coste/detalle` | EL COSTE DE UN VIDEO, TODO Y DESGLOSADO (11-10-2026). |
| `GET` | `/api/proyectos/{pid}/coste/eventos` | Detalle de cada consumo, filtrable por proveedor, paso y unidad. |
| `GET` | `/api/proyectos/{pid}/coste/flujo` | Coste en vivo por SSE, para que la cabecera se mueva mientras corre un paso. |
| `GET` | `/api/proyectos/{pid}/coste/por-paso` | Desglose por paso del pipeline: que fase se come el presupuesto. |
| `PUT` | `/api/proyectos/{pid}/coste/presupuesto` | Fija el presupuesto en dolares del video (null para quitarlo). |

## Origen y guion

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos/{pid}/guion/bloques` | El orden de los bloques de ahora y lo que costaria regrabar lo cambiado. |
| `POST` | `/api/proyectos/{pid}/guion/bloques` | Un bloque nuevo: {texto, donde: antes|despues|principio|final, ancla}. |
| `POST` | `/api/proyectos/{pid}/guion/bloques/reescribir` | Reescribe unos bloques del guion con una frase. Sin tocar el audio. |
| `DELETE` | `/api/proyectos/{pid}/guion/bloques/{bid}` | Quita un bloque AÑADIDO a mano. Los del guion original no se quitan. |
| `POST` | `/api/proyectos/{pid}/guion/bloques/{bid}/partir` | Parte un bloque: {trozos: [texto, texto, ...]}. El primero se queda en el. |
| `POST` | `/api/proyectos/{pid}/guion/pausas/quitar` | Quita las pausas largas de unos bloques: {bloques: [ids]} o {sobrantes: true}. |

## Voz

| | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/proyectos/{pid}/voz/describir` | Describe como quieres que suene y devuelve voz y mandos propuestos. |
| `POST` | `/api/proyectos/{pid}/voz/previsualizar` | Sintetiza unos segundos con estos mandos de voz para escucharlos. |
| `POST` | `/api/proyectos/{pid}/voz/secciones/{seccion_id}/regrabar` | Regraba una seccion de la toma, con microcambio si se pide. |
| `GET` | `/api/voces` | Catalogo de voces de Cartesia, sin atarlo a ningun proyecto. |
| `POST` | `/api/voces/muestra` | Doce segundos de una voz del catalogo, sin estilo ni proyecto. |
| `GET` | `/api/voces/muestra/{nombre}` | El wav de una muestra ya sintetizada. |

## Catálogo, escenarios y piezas

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos/{pid}/assets/hechos` | Los planos que hay generados AHORA en la carpeta de trabajo. |
| `GET` | `/api/proyectos/{pid}/catalogo` | El catalogo APROBADO que hay guardado en los params de assets. |
| `PUT` | `/api/proyectos/{pid}/catalogo` | Guarda el catalogo aprobado en los params de assets. |
| `POST` | `/api/proyectos/{pid}/catalogo/proponer` | Lee el guion ENTERO y propone quien sale, donde y con que tono. |
| `GET` | `/api/proyectos/{pid}/conservacion` | Que se puede mantener del video, sin llamar a nadie y sin gastar. |
| `POST` | `/api/proyectos/{pid}/conservacion/analizar` | Pregunta por los planos dudosos y devuelve el plan definitivo. |
| `POST` | `/api/proyectos/{pid}/conservacion/aplicar` | Conserva lo que se puede conservar y marca el resto para rehacer. |
| `POST` | `/api/proyectos/{pid}/escenarios` | Un clic: deduce del guion quien sale y donde ocurre. |

## Estilo y moodboard

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/moodboard/{clave}/{origen}/{archivo}` | Sirve una lamina del banco de moodboards, que vive fuera de los proyectos. |
| `GET` | `/api/proyectos/{pid}/estilo/cambios` | Que tiene el estilo del video que el video no tiene, por partes, y lo que costaria traerlo. Con `?estilo=<otro>`, lo mismo frente a OTRO estilo (vista previa de «Cambiar de estilo…», con `cliente: {antes, ahora}`). Dice `actual` y `estilo.en_papelera`. No escribe nada. |
| `POST` | `/api/proyectos/{pid}/estilo/guia` | Escribe la guia de estilo mirando los fotogramas elegidos. |
| `PUT` | `/api/proyectos/{pid}/estilo/seleccion` | Guarda las imagenes de estilo elegidas en los params de assets. |
| `POST` | `/api/proyectos/{pid}/estilo/traer` | Trae al video las partes elegidas del estilo: {partes: [estilo, tono, voz, rotulos]}. No genera nada. |
| `PUT` | `/api/proyectos/{pid}/estilo` | Pasa el video a OTRO estilo: `{estilo, partes: [..]}`. Escribe `config.estilo_light` (no mueve firmas) y trae solo las partes elegidas (sin partes, nada queda obsoleto). El video se queda en su proyecto (cliente) si tenia uno. 400 estilo o parte que no existe, 409 algo en marcha o estilo en la papelera. |
| `GET` | `/api/proyectos/{pid}/moodboard` | Las referencias de estilo dibujadas a proposito para este estilo. |
| `POST` | `/api/proyectos/{pid}/moodboard` | Dibuja las laminas de estilo. Quedan PROPUESTAS hasta que alguien las mira. |
| `POST` | `/api/proyectos/{pid}/moodboard/aprobar` | Mete el moodboard en el banco del canal. Es la decision de una persona. |

## Grafismo: subtítulos y cartelas

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos/{pid}/callouts/diseno` | Sets de diseno, el elegido y el que sugiere la guia de estilo del video. |
| `PUT` | `/api/proyectos/{pid}/callouts/plan` | Guarda el GRAFISMO del video en los params de callouts. |
| `GET` | `/api/proyectos/{pid}/callouts/vista` | La capa de ESE plano, dibujada ahora con el código de p7. |
| `GET` | `/api/proyectos/{pid}/cartelas` | Las plantillas de cartela con su muestra dibujada, y el plan guardado. |
| `PUT` | `/api/proyectos/{pid}/cartelas` | Guarda que planos son cartela (POR UNIDAD) y que plantillas se pueden usar. |
| `POST` | `/api/proyectos/{pid}/cartelas/plan` | Lee el guion y decide que tramos se cuentan mejor con texto que con dibujo. |
| `GET` | `/api/proyectos/{pid}/cartelas/vista` | El SVG de la cartela de ESE plano, dibujado ahora con el grafismo de ahora. |
| `GET` | `/api/proyectos/{pid}/direccion` | Qué se ve en cada plano: lo dirigido, y los planos que lo admiten. |
| `PUT` | `/api/proyectos/{pid}/direccion` | Guarda qué se ve en cada plano. Un texto vacío la quita. |
| `POST` | `/api/proyectos/{pid}/direccion/proponer` | Escribe qué se ve en cada plano, con TODOS los planos delante de una vez. |
| `POST` | `/api/proyectos/{pid}/imagenes/calidad` | REHACE LAS IMAGENES QUE SIGUEN EN OTRA CALIDAD, y solo esas. |
| `GET` | `/api/proyectos/{pid}/imagenes/cola` | La cola de notas de imagenes: cual se dibuja, cuanto lleva y que espera. |
| `DELETE` | `/api/proyectos/{pid}/imagenes/cola/{nid}` | Saca una nota de la cola (la que ya se esta dibujando no se para). |
| `POST` | `/api/proyectos/{pid}/imagenes/rehacer` | Pone en la cola las notas de imagenes: {notas?: [ids], desde_cero?} (sin ids, todas). |
| `POST` | `/api/proyectos/{pid}/imagenes/revisar` | Revisa las imagenes: {planos?: [ids], forzar?}. Sin planos, las que no se |
| `GET` | `/api/proyectos/{pid}/imagenes/revision` | La ultima revision, las notas del revisor sin aplicar, lo que falta por |
| `POST` | `/api/proyectos/{pid}/imagenes/revision/aplicar` | Rehace las notas pendientes del revisor ({notas?: [ids]}; sin ids, todas) |
| `POST` | `/api/proyectos/{pid}/imagenes/revision/descartar` | «Esta imagen está bien así»: {plano}. Quita la nota pendiente del revisor |

## Sonido y transiciones

| | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/efectos/buscar` | Efectos de FreeSound por texto libre, para elegir uno: {texto, papel?, pagina?}. |
| `GET` | `/api/efectos/{archivo}` | Sirve un efecto del banco del canal, para poder oírlo antes de vetarlo. |
| `GET` | `/api/proyectos/{pid}/sonido` | Qué suena en este vídeo: el tema puesto, los efectos surtidos y el catálogo. |
| `PUT` | `/api/proyectos/{pid}/sonido` | Fija el tema (bajándolo al banco), el interruptor o el nivel de música. |
| `GET` | `/api/proyectos/{pid}/sonido/arco` | El arco que sale del RITMO del montaje. Gratis, sin salir a la red. |
| `POST` | `/api/proyectos/{pid}/sonido/banda` | Monta la banda sonora SOLA: un tema por tramo, elegido por el ritmo. |
| `PUT` | `/api/proyectos/{pid}/sonido/efecto` | Fija UN sonido para un papel ({papel, efecto}) o lo devuelve a automático |
| `POST` | `/api/proyectos/{pid}/sonido/efectos` | Llena el banco de efectos del canal para los papeles que se pidan. |
| `PUT` | `/api/proyectos/{pid}/sonido/efectos/volumen` | Fija cuánto se oyen los efectos ({nivel: bajos|normales|altos}) y, si |
| `POST` | `/api/proyectos/{pid}/sonido/musica` | Temas de Jamendo que pegan con el tono. Devuelve candidatos, no elige. |
| `POST` | `/api/proyectos/{pid}/sonido/vetados` | Prohíbe un efecto en TODO el canal, o levanta el veto con `quitar`. |
| `GET` | `/api/proyectos/{pid}/transiciones` | Las transiciones que existen, con su GLSL, y cuales entran en este video. |

## Render y montaje

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/proyectos/{pid}/capturas` | Capturas del proyecto, filtrables por paso y escena. |
| `POST` | `/api/proyectos/{pid}/capturas` | Guarda una captura anotada de los pasos callouts o render. |
| `POST` | `/api/proyectos/{pid}/capturas/aplicar` | Traduce las capturas a instruccion y rehace SOLO las escenas tocadas. |
| `GET` | `/api/proyectos/{pid}/capturas/contexto` | Donde cae un instante y con que material se compone ese fotograma. |
| `DELETE` | `/api/proyectos/{pid}/capturas/{cid}` | Borra una captura y su PNG. |
| `GET` | `/api/proyectos/{pid}/montaje` | El montaje de este video, las transiciones elegidas y si esta aplicado. |
| `PUT` | `/api/proyectos/{pid}/montaje` | {montaje?: {movimiento, subtitulos, gancho, cifras, barra}, transiciones?: [..]} |
| `POST` | `/api/proyectos/{pid}/montaje/aplicar` | Aplica lo que quede del montaje en UN solo trabajo. Ni una imagen. Si lo pendiente es solo la mezcla (música, efectos, volúmenes, logo), `solo_montar` (segundos; con la música vuelta a la automática, antes la banda); si no, capas y montaje. -> `{trabajo_id, solo_mezcla}`. 409 si aún no está montado. |
| `GET` | `/api/proyectos/{pid}/montaje/notas` | Lo escrito sobre el vídeo terminado. No toca ninguna firma. |
| `PUT` | `/api/proyectos/{pid}/montaje/notas` | Guarda la nota del vídeo entero. Autoguardado, como todo lo demás. |

## Presets del canal

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/presets` | Presets de estilo de locucion. |
| `GET` | `/api/presets-canal` | Presets guardados, agrupados por tipo, mas su papelera y el catalogo. |
| `POST` | `/api/presets-canal` | Guarda un preset nuevo, o sustituye el contenido de uno que ya existe. |
| `DELETE` | `/api/presets-canal/papelera/{pid}` | Borrado definitivo. Solo alcanza a lo que ya esta en la papelera. |
| `GET` | `/api/presets-canal/papelera/{pid}` | Que hay dentro de un preset apartado, para decir que se pierde. |
| `POST` | `/api/presets-canal/papelera/{pid}/restaurar` | Devuelve a la lista un preset apartado. Y si es un estilo, su taller con |
| `DELETE` | `/api/presets-canal/{pid}` | A la papelera. No borra nada: la ficha y sus fotogramas siguen enteros. |
| `PATCH` | `/api/presets-canal/{pid}` | Cambia solo el nombre o la nota. Lo que el preset guarda no se toca. |
| `GET` | `/api/presets-canal/{pid}/fichero/{archivo:path}` | Un fichero de la carpeta del preset (fotogramas, laminas del moodboard). |
| `GET` | `/api/presets-canal/{pid}/miniatura` | La cara del preset en el desplegable: uno de sus propios fotogramas. |

## Modo light: estilos y vídeo

| | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/estimacion` | Lo que va a salir de esa duracion: palabras, planos y dolares. |
| `GET` | `/api/presets-light` | Los presets de canal, con sus viñetas y su plan de generacion. |
| `POST` | `/api/presets-light` | Crea el estilo entero a partir de los cuatro campos. |
| `POST` | `/api/presets-light/imagenes` | Guarda las imagenes que acompanan a una descripcion de estilo. |
| `DELETE` | `/api/presets-light/imagenes/{nombre}` | Quita una imagen de la carpeta de espera. Quitarla de la lista es esto. |
| `GET` | `/api/presets-light/imagenes/{nombre}` | La miniatura de una imagen que espera en el buzon. |
| `POST` | `/api/presets-light/plan` | Lo que va a hacer, en orden y con sus tiempos. No lanza nada. |
| `DELETE` | `/api/presets-light/talleres/{taller_id}` | Tira un intento a medias. A la papelera de proyectos, no al vacio. |
| `DELETE` | `/api/presets-light/{preset_id}` | A la papelera de presets, y su taller con el. |
| `PUT` | `/api/presets-light/{preset_id}` | El nombre, el idioma y la guia de tono: lo que se cambia a mano. |
| `GET` | `/api/presets-light/{preset_id}/aportadas` | Las imagenes de referencia de un estilo, con lo que se dijo de cada una. |
| `PUT` | `/api/presets-light/{preset_id}/aportadas` | Guarda lo que se dice de cada imagen y las ★: {descripciones, destacadas}. |
| `GET` | `/api/presets-light/{preset_id}/aportadas/{nombre}/imagen` | Una de tus imagenes de referencia, tal cual la subiste. |
| `GET` | `/api/presets-light/{preset_id}/coste` | Lo que costo hacer este estilo (su taller), desglosado. |
| `POST` | `/api/presets-light/{preset_id}/duplicar` | Una copia del estilo, con su taller. |
| `GET` | `/api/presets-light/{preset_id}/laminas` | Las laminas de un estilo, limpias y con lo que ensena cada una. |
| `POST` | `/api/presets-light/{preset_id}/laminas` | Una accion sobre las laminas de un estilo. |
| `GET` | `/api/presets-light/{preset_id}/laminas/{lamina}/imagen` | Una lamina LIMPIA, sin texto encima: la que va en la hoja de cada plano. |
| `POST` | `/api/presets-light/{preset_id}/regenerar` | Rehace UNA de las tres partes con una frase de feedback. |
| `GET` | `/api/presets-light/{preset_id}/reglas` | Las reglas de un estilo. -> {reglas, gravedades, maximo} |
| `PUT` | `/api/presets-light/{preset_id}/reglas` | Guarda las reglas de un estilo: {reglas: [{id?, nombre, texto, palabras?, |
| `POST` | `/api/presets-light/{preset_id}/video` | Un proyecto de video nuevo con ese estilo ya aplicado. -> la ficha. |
| `POST` | `/api/presets-light/{preset_id}/voz/previsualizar` | Unos segundos con la voz de este estilo, para escucharla. |

## Ajustes del CLI y estadísticas

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/ajustes` | Lo que hay puesto, y lo que cuesta cada calidad de imagen. |
| `PUT` | `/api/ajustes` | Cambia ajustes. NO toca ningun proyecto: es el valor de los NUEVOS. |
| `GET` | `/api/ajustes-cli` | Catalogo de modelos y esfuerzos, y en que pasos se puede elegir. |
| `GET` | `/api/estadisticas` | Historico de tiempos reales, entre todos los proyectos. |
| `POST` | `/api/estadisticas/valoracion` | Anota si el resultado de un ajuste gusto o no. |

## Claves y enlaces

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/claves` | Que claves hay puestas, sin ninguna clave dentro. |
| `PUT` | `/api/claves` | Guarda las claves y espeja el .env que leen los motores. |
| `GET` | `/api/claves/cli` | Las cuentas del CLI en orden, con quién hay logueado en cada una. |
| `POST` | `/api/claves/cli/{cid}/codigo` | Le pasa al CLI el código que devolvió la página de acceso. |
| `DELETE` | `/api/claves/cli/{cid}/entrar` | Tira el acceso a medias de esa cuenta. |
| `POST` | `/api/claves/cli/{cid}/entrar` | Arranca el acceso de esa cuenta y devuelve el enlace donde entrar. |
| `POST` | `/api/claves/cli/{cid}/probar` | Le habla a esa cuenta con una llamada mínima y apunta cómo responde. |
| `POST` | `/api/claves/cli/{cid}/salir` | Cierra la sesión de esa cuenta, sin quitarla de la lista. |
| `POST` | `/api/claves/probar` | Prueba cada clave contra su servicio y dice cuál funciona de verdad. |

## El asistente

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/asistente` | Si el asistente puede contestar ahora, y con qué cuenta. |
| `GET` | `/api/asistente/charlas` | El historial: las charlas guardadas, la más reciente primero. |
| `POST` | `/api/asistente/charlas` | Abre una charla vacía con el asistente. |
| `DELETE` | `/api/asistente/charlas/{cid}` | Borra una charla del historial; lo que estuviera contestando se cancela. |
| `GET` | `/api/asistente/charlas/{cid}` | Los turnos de una charla; el último dice si sigue pensando. |
| `POST` | `/api/asistente/charlas/{cid}/cancelar` | Para la respuesta que esté en marcha en esa charla. |
| `POST` | `/api/asistente/charlas/{cid}/mensajes` | Manda una pregunta; la respuesta se sigue con GET de la charla. |
| `POST` | `/api/asistente/dictado` | Un audio grabado en el navegador, pasado a texto para la pregunta. |
| `GET` | `/api/asistente/foto` | Lo que el asistente ve del Estudio ahora mismo, en texto y sin claves. |
| `POST` | `/api/asistente/imagenes` | Imagenes para la proxima pregunta al asistente (pegadas o adjuntas). |
| `GET` | `/api/asistente/imagenes/{nombre}` | Una imagen pegada al asistente, para su miniatura en la charla. |
| `POST` | `/api/asistente/probar` | Prueba las cuentas con las que contestaría el asistente y dice cómo están. |

## Ficheros y salud

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/a/{pid}/{ruta:path}` | Sirve un archivo del proyecto (imagen, wav, svg, mp4) con proteccion. |
| `GET` | `/api/salud` | Estado del servicio. |

## Lo demás

| | Ruta | Qué hace |
|---|---|---|
| `GET` | `/` | La interfaz del Estudio. |
| `GET` | `/api/clientes` | Los proyectos (clientes) y a cual pertenece cada estilo. |
| `POST` | `/api/clientes` | Un proyecto nuevo: {nombre}. |
| `PUT` | `/api/clientes/estilos/{preset_id}` | Mueve un estilo (y sus videos) a un proyecto: {cliente} ("" lo saca). |
| `PUT` | `/api/clientes/videos/{video_id}` | Mueve un video a otro proyecto ("" lo devuelve al de su estilo). |
| `DELETE` | `/api/clientes/{cid}` | Borra el proyecto. Sus estilos y videos NO se borran: quedan sin proyecto. |
| `PUT` | `/api/clientes/{cid}` | Renombra, oculta o pone clave: {nombre?, oculto?, clave?} ("" la quita). |
| `POST` | `/api/clientes/{cid}/abrir` | Comprueba la clave de un proyecto. 403 si no es. |
| `GET` | `/api/inicio/panel` | El panel guardado de ese usuario, o {panel: null} si no tiene. |
| `PUT` | `/api/inicio/panel` | Guarda el panel de un usuario: {usuario, panel} (panel null lo borra). |
| `GET` | `/api/inicio/resumen` | Lo del Inicio que no sale de otras rutas, en una sola llamada. |
| `POST` | `/api/logos` | Guarda un logo sin video todavia: el de un borrador o el de un proyecto. |
| `GET` | `/api/logos/{nombre}` | Un logo subido que todavia no esta en ningun video. |
| `GET` | `/api/montaje` | Lo que la pantalla necesita para elegir el montaje antes de que exista |
| `POST` | `/api/musica/buscar` | Temas de Jamendo por animo, sin video: el borrador de un video nuevo. |
| `GET` | `/api/musica/escucha` | Pasa por aqui la escucha de un tema de Jamendo antes de elegirlo. |
| `GET` | `/api/musica/propia/{archivo}` | Un tema tuyo del banco, para escucharlo. |
| `POST` | `/api/ortografia/textos` | Revisa la ortografia de campos sueltos que se ven o se publican: {textos: |
| `POST` | `/api/ortografia/textos/descartar` | Lo que se deja como estaba: {rid, ids: [...]}. No se vuelve a proponer. |
| `GET` | `/api/ortografia/textos/{rid}` | Como va la revision de unos campos sueltos, y lo que propone al terminar. |
| `GET` | `/api/parrilla/cuentas` | Las cuentas ya leídas, las conexiones (sin claves) y el gasto del mes. |
| `PUT` | `/api/parrilla/cuentas/conexiones` | {youtube_clave?, meta_token?, ig_id?, apify_token?, pago?, tope_usd?} ("" quita una). |
| `POST` | `/api/parrilla/cuentas/conexiones/instagram` | Con el token de Meta puesto: tu cuenta profesional (se guarda si es una). |
| `POST` | `/api/parrilla/cuentas/leer` | {texto, red?, cuantos?, forzar?, pagar?} -> el trabajo (se sigue preguntando). |
| `POST` | `/api/parrilla/cuentas/plan` | {texto, red?, cuantos?} -> qué vía se usaría y cuánto costaría. |
| `GET` | `/api/parrilla/cuentas/trabajos/{tid}` | — |
| `DELETE` | `/api/parrilla/cuentas/{red}/{usuario}` | — |
| `GET` | `/api/parrilla/cuentas/{red}/{usuario}` | — |
| `POST` | `/api/parrilla/cuentas/{red}/{usuario}/analizar` | Claude dice qué le funciona a esa cuenta -> el trabajo. |
| `GET` | `/api/parrilla/plantilla` | Un guion en blanco en el formato del Studio, para «Escribir uno». |
| `GET` | `/api/parrilla/proyectos` | Los proyectos que se pueden ver, con cuántos guiones tiene cada uno, y |
| `GET` | `/api/parrilla/proyectos/{cid}` | Las matrices del proyecto y sus guiones, con el estado al día. |
| `GET` | `/api/parrilla/proyectos/{cid}/chats` | Las conversaciones del proyecto, la más nueva primero. |
| `POST` | `/api/parrilla/proyectos/{cid}/chats` | Una conversación nueva: {modelo?}. No se guarda hasta el primer mensaje. |
| `DELETE` | `/api/parrilla/proyectos/{cid}/chats/{chid}` | — |
| `GET` | `/api/parrilla/proyectos/{cid}/chats/{chid}` | — |
| `POST` | `/api/parrilla/proyectos/{cid}/chats/{chid}/cancelar` | — |
| `POST` | `/api/parrilla/proyectos/{cid}/chats/{chid}/guardar` | Los guiones de una respuesta a la Parrilla: {turno, indices?, matriz?, nombre?}. |
| `POST` | `/api/parrilla/proyectos/{cid}/chats/{chid}/mensajes` | Un mensaje (multipart): «texto», «web» (1/0), «resultados» (1/0), «modelo» |
| `POST` | `/api/parrilla/proyectos/{cid}/convertir` | Claude convierte lo pegado al formato: {texto, modo, matriz?, nombre?, |
| `POST` | `/api/parrilla/proyectos/{cid}/desde-cuenta` | Guiones para ESTE proyecto con lo que le funciona a una cuenta ajena: |
| `POST` | `/api/parrilla/proyectos/{cid}/desde-resultados` | Claude escribe guiones a partir de lo que mejor funcionó: {claves?, dias?, |
| `POST` | `/api/parrilla/proyectos/{cid}/guiones` | Sin Claude: {texto (ya en el formato), matriz?, nombre?} -> {matriz, guiones} |
| `DELETE` | `/api/parrilla/proyectos/{cid}/guiones/{gid}` | — |
| `GET` | `/api/parrilla/proyectos/{cid}/guiones/{gid}` | Un guion entero: el texto, lo leído y lo que iría al Encargo. |
| `PUT` | `/api/parrilla/proyectos/{cid}/guiones/{gid}` | {texto?, uso?, formato?, duracion_s?, estado?} -> el guion. |
| `POST` | `/api/parrilla/proyectos/{cid}/guiones/{gid}/encargo` | {indice?, estilo?} -> lo que la pantalla pone en «Un vídeo nuevo». El |
| `POST` | `/api/parrilla/proyectos/{cid}/guiones/{gid}/marca` | «Usar su marca para el proyecto»: {pisar?} -> {marca, cambiados}. |
| `GET` | `/api/parrilla/proyectos/{cid}/marca` | La marca del cliente guardada en el proyecto, con sus campos. |
| `PUT` | `/api/parrilla/proyectos/{cid}/marca` | {quien?, mostrar?, evitar?, tono?, cta?, otras?} -> la marca. |
| `POST` | `/api/parrilla/proyectos/{cid}/matrices` | {nombre} -> {id} |
| `DELETE` | `/api/parrilla/proyectos/{cid}/matrices/{mid}` | — |
| `PUT` | `/api/parrilla/proyectos/{cid}/matrices/{mid}` | {nombre} |
| `POST` | `/api/parrilla/proyectos/{cid}/pedir` | Claude escribe guiones nuevos: {peticion, cuantos, modo, matriz?, nombre?, |
| `GET` | `/api/parrilla/proyectos/{cid}/resultados` | Lo que mejor funcionó en el proyecto (solo lo guardado). |
| `POST` | `/api/parrilla/proyectos/{cid}/subir` | Una matriz en Word, Excel, PDF o texto (multipart: «documento», «modo», |
| `DELETE` | `/api/parrilla/trabajos/{tid}` | Quita de la pantalla un trabajo terminado (el aviso de listo o de error). |
| `GET` | `/api/parrilla/trabajos/{tid}` | Cómo va una conversión: {estado: trabajando|listo|error, avance, ...}. |
| `GET` | `/api/pronunciaciones` | Las palabras que la voz dice como se escriben aqui (sobre todo en ingles). |
| `PUT` | `/api/pronunciaciones` | {lista: [{escrito, dicho}]} -> la lista guardada. No graba nada ni paga nada. |
| `GET` | `/api/publicar/cola` | Los videos listos para publicar y los envios de la semana (hora de Lima). |
| `GET` | `/api/publicar/estado` | Si hay clave de Upload-Post (y de donde sale). Nunca la clave. |
| `GET` | `/api/publicar/horarios` | El mejor día y hora de cada red con lo propio (o el punto de partida |
| `GET` | `/api/publicar/informe` | El informe del mes de un proyecto, para el cliente: {proyecto, mes}. |
| `GET` | `/api/publicar/lo-que-funciono` | Los posts que mejor fueron: {proyecto?, dias, red?, por, cuantos}. |
| `GET` | `/api/publicar/metricas-auto` | La configuracion, la ultima vuelta, la proxima y lo que gasta. Los avisos |
| `PUT` | `/api/publicar/metricas-auto` | Guarda la eleccion (tras confirmar el coste en pantalla). |
| `POST` | `/api/publicar/metricas-auto/ahora` | Una vuelta ya, en segundo plano (puede tardar minutos). |
| `POST` | `/api/publicar/metricas-auto/coste` | Lo que gastaria una eleccion SIN guardarla: {frecuencia?, hora?, posts?}. |
| `GET` | `/api/publicar/palabra-clave` | La palabra clave y la zona del proyecto de un estilo, para sugerirlas en |
| `GET` | `/api/publicar/palabras-y-ganchos` | Qué palabras clave y qué primeras líneas fueron mejor. No pregunta a nadie. |
| `POST` | `/api/publicar/probar` | Prueba la clave contra Upload-Post sin gastar ninguna subida. |
| `GET` | `/api/publicar/proyectos` | Cada proyecto con lo fijo de publicar y sus cuentas (lo ultimo visto). |
| `PUT` | `/api/publicar/proyectos/{cid}` | Lo fijo de un proyecto: {perfil, redes, hora, firma, hashtags, tono, |
| `POST` | `/api/publicar/proyectos/{cid}/conectar` | El enlace (48 h) para conectar o reconectar las cuentas: {redes?, volver_a?}. |
| `POST` | `/api/publicar/proyectos/{cid}/cuentas` | Pregunta a Upload-Post que cuentas tiene conectadas el perfil del proyecto |
| `POST` | `/api/publicar/proyectos/{cid}/metricas` | Pide las cifras de lo publicado del proyecto y los seguidores de sus |
| `POST` | `/api/publicar/proyectos/{cid}/palabras` | Claude propone la palabra clave principal, las secundarias y la zona del |
| `POST` | `/api/publicar/proyectos/{cid}/perfil` | Apunta el perfil de Upload-Post del proyecto: {perfil, crear?}. Si ya |
| `GET` | `/api/publicar/proyectos/{cid}/perfiles` | Los perfiles que hay de verdad en Upload-Post, para elegir uno: los que |
| `GET` | `/api/publicar/proyectos/{cid}/tableros` | Los tableros de Pinterest del perfil del proyecto: [{id, nombre}]. |
| `POST` | `/api/publicar/refrescar` | Pregunta a Upload-Post por los envios que siguen en el aire. |
| `GET` | `/api/publicar/resultados` | El resumen de un proyecto (lo que ya se sabe; no pregunta a nadie). |
| `GET` | `/api/publicar/videos/{pid}` | La ficha de publicar de un video: redes, textos, encaje, envios. |
| `PUT` | `/api/publicar/videos/{pid}` | {redes?, textos?: {red: {titulo, descripcion, cta, hashtags}}, capitulos?} |
| `POST` | `/api/publicar/videos/{pid}/a-mano` | «Lo he subido yo»: {red, url?}. Queda en el historial. |
| `POST` | `/api/publicar/videos/{pid}/emojis` | «✨ Más emojis»: {red, campo: titulo\|descripcion, texto?} → {texto, antes, despues}, el MISMO texto con emojis añadidos (haiku, en la petición). No guarda nada; si Claude cambia una palabra o un hashtag, 422. |
| `POST` | `/api/publicar/videos/{pid}/enviar` | {redes, modo: ahora|programar|pendiente, cuando?, confirmado, repetir?} |
| `POST` | `/api/publicar/videos/{pid}/envios/{eid}/cancelar` | Cancela lo programado (en Upload-Post) o lo que esperaba tu OK, y quita |
| `POST` | `/api/publicar/videos/{pid}/envios/{eid}/confirmar` | Un envio que esperaba tu OK sale: {confirmado, modo?, cuando?}. |
| `POST` | `/api/publicar/videos/{pid}/envios/{eid}/reintentar` | Vuelve a mandar un envio que quedo en «comprobar», con su misma clave de |
| `GET` | `/api/publicar/videos/{pid}/fotograma` | El fotograma del momento `ms` (vista pequeña), para elegir la portada. |
| `POST` | `/api/publicar/videos/{pid}/ganchos` | Tres ganchos para la primera línea de una red: {red}. |
| `POST` | `/api/publicar/videos/{pid}/ganchos/usar` | Pone el gancho elegido como primera línea: {red, indice}. |
| `POST` | `/api/publicar/videos/{pid}/metricas` | Pide las cifras de lo publicado de este video: {forzar?}. |
| `POST` | `/api/publicar/videos/{pid}/optimizar` | Claude revisa el SEO de los textos: {redes}. Deja una PROPUESTA campo a |
| `POST` | `/api/publicar/videos/{pid}/portada` | Sube una imagen de portada (multipart, campo «portada»). |
| `GET` | `/api/publicar/videos/{pid}/portada.jpg` | La imagen de portada subida para este vídeo. |
| `POST` | `/api/publicar/videos/{pid}/textos` | Claude escribe los textos de las redes pedidas: {redes}. Se sigue |
| `POST` | `/api/reglas-estilo/afinar` | Claude reescribe una regla para el generador: {texto, nombre?, palabras?}. |
| `GET` | `/api/reglas-estilo/afinar/{rid}` | Como va «Afinar con Claude», y la propuesta al terminar. |
| `GET` | `/api/sistema/estilos-perdidos` | Los videos que apuntan a imagenes de estilo que ya no estan. Solo mira. |
| `GET` | `/api/sistema/guias` | Como rellenar cada campo de texto: plantilla, ejemplo y prompt para otra IA. |
| `POST` | `/api/sistema/guias/{gid}/revisar` | Lanza la revision de un texto contra la guia de su campo. -> {id} |
| `GET` | `/api/sistema/manual` | Cómo se usa el Estudio, tal cual esta en docs/MANUAL.md. |
| `GET` | `/api/sistema/notas` | Las notas de mejoras futuras, las pendientes primero. |
| `POST` | `/api/sistema/notas` | Apunta una mejora para hacer mas adelante. |
| `DELETE` | `/api/sistema/notas/{nid}` | — |
| `PUT` | `/api/sistema/notas/{nid}` | Cambia el texto de una nota o la marca como hecha / pendiente. |
| `GET` | `/api/sistema/novedades` | El historial de cambios, tal cual esta en docs/NOVEDADES.md. |
| `GET` | `/api/sistema/revisiones/{rid}` | — |
| `GET` | `/api/sistema/terminos` | Los terminos de uso, tal cual estan en docs/TERMINOS.md (el pie). |
| `POST` | `/api/sonido/subir` | Sube un audio tuyo (MP3, WAV, M4A, OGG) para la música o un efecto. |
| `GET` | `/{fichero}` | Sirve un fichero suelto de web/ (app.js, estilo.css...). |

---

**322 endpoints.** Escrito por `generar_api.py` desde `app.py`.

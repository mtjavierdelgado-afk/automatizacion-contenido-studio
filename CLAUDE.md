# Automatización Contenido Studio — lo que hay que saber antes de tocarlo

Lee primero [README.md](README.md): qué es, cómo se arranca y cómo está montado.
Y si vienes a retomar sin contexto, [docs/RETOMAR.md](docs/RETOMAR.md): el
estado al cerrar, qué está desplegado y **los fallos que se encontraron con su
causa** — el sitio donde mirar antes de volver a tocar algo.

Esto es lo otro — lo que no se deduce leyendo el código y cuesta dinero o una
tarde averiguar.

---

## LO PRIMERO: aquí se paga por generar

Una tanda de imágenes de un vídeo de cuatro minutos (ritmo medio) son ~86 planos
más una hoja por personaje, y ~4 $ en calidad baja; en foto, que nace en media,
~7 $ (`POST /api/estimacion`, 15-10-2026).
No es un detalle de producto: es la razón de la mitad de las decisiones de este
repo, y de estas tres reglas.

**1. No escribas params «por defecto» al abrir una pantalla.** La firma de un
paso se calcula sobre los params GUARDADOS. Escribir un valor que ese proyecto
nunca tuvo mueve la firma, deja obsoleto el paso y todo lo que cuelga, y la
pantalla ofrece regenerar el vídeo entero sin que nadie haya pedido nada. Las
pantallas editan una copia y solo guardan cuando alguien toca algo.

**2. Las tandas de imágenes se lanzan DE UNA EN UNA.** Dos a la vez tardan el
doble por imagen y pierden el registro del gasto.

**3. Un guardián calibrado sobre un fallo aprende a dar por bueno ese fallo.**
`p6_assets._planos_repetidos` tumba la tanda si dos planos acaban con la MISMA
imagen. Tiene tres excepciones —la cartela, la continuación de un plano largo
y los planos que copian el mismo mapa o gráfico (16-10-2026)— y las tres están
explicadas en su docstring. Si añades una cuarta, comprueba antes que lo que la
justifica no es un bug.

---

## Varias conversaciones trabajan aquí a la vez: ramas y coordinación

Este repo lo cambian VARIAS conversaciones en paralelo, cada una con una fase
distinta, y ninguna ve lo que hacen las demás. El único sitio que leen todas es
este fichero. Si vienes a trabajar aquí, haz `git pull` y lee esta sección
antes de tocar nada.

### Los nombres, para no confundir fases

| Nombre | Qué es |
|---|---|
| **V2.0 fase 1 a 5** | las fases de la V2.0 del Studio. Fase 3: vídeos sin voz (otro reloj para cronometrar). Fase 4: otras IAs (imágenes con la membresía de ChatGPT y la API de respaldo, ElevenLabs como alternativa a Cartesia, música generada por IA como alternativa a Jamendo, y una base para añadir más IAs sin rehacer nada). Fase 5: clips de vídeo (Veo 3.1 y Kling por API, modo mixto, e ida y vuelta con la membresía: descargar el paquete, generar en Flow o Kling y subir los clips) |
| **Etapa Foto A, B, C** | el modo foto realista. A: `estilo.modo`, cabecera del prompt, guía de foto, reglas de foto y escalera de encuadres para foto. B: el catálogo de productos como referencia obligatoria. C: presets de marca, evento y servicio |
| **Ruta fase 0, 1, 2…** | el plan de marketing de EstadoPlay. No es código; no la confundas con las de arriba |

### Cada fase en su rama; `main` es lo que está en el servidor

El servidor se actualiza desde `main` (`asvs actualizar`), así que `main` tiene
que estar siempre listo para servirse. Por eso:

1. **Cada fase o etapa trabaja en su propia rama**: `v2-fase-3`, `v2-fase-4a`, `v2-fase-4b`,
   `v2-fase-5`, `etapa-foto-a`, `etapa-foto-b`, `etapa-foto-c`. Se crea desde el
   `main` del día: `git fetch origin main && git switch -c <rama> origin/main`.
2. **A `main` solo llegan dos cosas**: una rama terminada y probada, o un
   arreglo urgente y pequeño (un fallo que tiene el servidor caído o roto). Todo
   lo demás va en su rama.
3. **Antes de unir una rama a `main`, se pone al día**: `git fetch origin main &&
   git merge origin/main`, se resuelven los choques, `bash pruebas.sh` en verde,
   y entonces se une (pull request en GitHub, o merge si el dueño lo pide).
4. **Probar una rama en el servidor sin tocar `main`**: en la consola del VPS,
   `ASVS_RAMA=<rama> asvs actualizar`. Para volver: `asvs actualizar` a secas
   (la rama no se guarda, así que vuelve sola a `main`). No toca vídeos, banco
   ni claves.
5. **`docs/NOVEDADES.md` se escribe en la rama** y, al unir, las entradas de las
   dos ramas se SUMAN: un choque ahí se resuelve conservando las dos, nunca
   eligiendo una.
6. **Sin límite de ramas abiertas** (decisión del dueño, 19-10-2026: antes eran
   tres como mucho). Lo que lo hace posible es la tabla de abajo: cada rama
   apunta sus ficheros y sus zonas, y nadie toca las de otra sin coordinarlo.
7. **Se une de una en una**, y antes de cada unión el dueño hace una
   instantánea del VPS en Hostinger. Después de unir, `asvs actualizar` en el
   servidor y se comprueba que el Studio arranca antes de unir la siguiente.
8. **La única excepción a «no toques `main`»** es esta sección de
   coordinación de `CLAUDE.md` (los nombres, la tabla de ficheros reservados y
   el orden). Se edita directamente en `main`, en un commit que no toca nada
   más, y después cada rama abierta hace `git merge origin/main`. Si se
   apuntara en la rama, las demás conversaciones no lo verían hasta la unión,
   que es justo cuando ya no sirve.

### Ficheros reservados mientras una rama esté abierta

Si tu fase necesita tocar un fichero reservado por otra rama abierta, no lo
cambies a ciegas: dilo en tu conversación para que el dueño lo coordine.

| Rama abierta | Ficheros reservados | Desde |
|---|---|---|
| `dominio-negocio` | **El negocio sale de los datos, no del código** (pedido del dueño, 20-10): lo que hoy es de EstadoPlay (servicios y cómo se reconocen, la escalera de cartas de foto de servicios, el criterio «equipo»/«orientación» del revisor) pasa a ser un DOMINIO de fábrica en `pasos/dominios.py`, con los MISMOS valores, y un estilo puede fijar el suyo (`estilo.dominio`). Sin dominio guardado se detecta por el texto como hoy: escalera, cartas y firmas byte a byte iguales (regla 1; la escalera expandida idéntica en longitud y orden). Sin pantalla nueva (eso es la Etapa Foto C). **Propios:** `pasos/dominios.py` y `pasos/prueba_dominios.py` (nuevos). **Por zonas:** `pasos/encuadres.py` (`SERVICIOS*`, `servicios_en_texto`, `servicios_de`, `escalera_para`, `carta_de`/`repartir` solo en cómo eligen escalera); `pasos/p6_assets.py` SOLO `servicios_del_video` y `_asignar_cartas`/`_informe_cartas` (el dominio que pasan); `pasos/revisor_imagenes.py` el texto de «equipo»/«orientación» de `INSTRUCCION` y `REFERENCIA` (no lo de la imagen base, que es de `tipo-de-relato`); `pasos/presets_canal.py` la clave `dominio` del Estilo (misma tupla que `relato` de `tipo-de-relato`: al unir se suman); en `app.py` una ruta de solo lectura `GET /api/dominios` junto al bloque TIPO DE RELATO (`tipo-de-relato` ya está unida, 21-10: al ponerse al día, sumar `dominio` a la tupla de claves del Estilo junto a `relato` y conservar las líneas de la imagen base del revisor); `pruebas.sh`/`pruebas.ps1` (una línea); `docs/NOVEDADES.md`, `docs/API.md`; `pasos/prueba_encuadres.py`. No toca `web/app.js` | 21-10-2026 |
| `etapa-foto-c` | **La ficha del negocio de cada cliente** (pedido del dueño, 21-10; la Etapa Foto C reducida: «nada de un cliente metido en el código»). Sale de `dominio-negocio` y se une DESPUÉS de ella. De fábrica SOLO queda el tipo `general` (`pasos/dominios_fabrica.json`): EstadoPlay sale del código entero (sus cartas de consolas y sus reglas de mandos/equipo; decisión del dueño, sus vídeos viejos pueden cambiar). Cada proyecto (cliente) tiene SU ficha del negocio (qué hace, reglas de foto, lo que vigila el revisor) en `<proyectos>/_sistema/dominios.json`, con id `cliente-<cid>`, y la API la escribe en `estilo.dominio` de sus estilos de FOTO. **Propios:** `pasos/dominios.py` (tras unirse `dominio-negocio`), `pasos/dominios_fabrica.json`, `pasos/prueba_dominios.py`. **Por zonas:** `motores/reglas/reglas.py` (`para`/`bloque_prompt` con `extra`) y `reglas_foto.json` (sin reglas de ningún negocio, con un hueco); `pasos/encuadres.py` (`SERVICIOS*`/`ESCALERA_FOTO` vacíos y la familia de las cartas de un negocio en `carta_de`); `pasos/revisor_imagenes.py` (el defecto de `REFERENCIA` = general); en `pasos/p6_assets.py` SOLO la línea de las reglas de la casa de `_prompt_completo`; `pasos/moodboard.py` SOLO `_reglas_de`; en `app.py` el bloque LA FICHA DEL NEGOCIO (rutas `/api/clientes/{cid}/negocio`, `_negocio_al_estilo`) junto a `GET /api/dominios`, `_reglas_para_revisor` (`extra`), y UNA llamada a `_negocio_al_estilo` en `asignar_estilo_a_cliente`, `borrar_cliente`, `duplicar_preset_light`, `restaurar_preset_canal` y tras `_congelar_preset` (creación del estilo); en `web/app.js` el bloque LA FICHA DEL NEGOCIO al final, un botón y su panel en `dentroDeProyecto` (junto al del logo) y UNA línea al principio de `bloqueReglasLight`; un bloque LA FICHA DEL NEGOCIO en `web/estilo.css` (junto a `.regla-estilo-propuesta`); `pasos/prueba_modo_foto.py` (secciones 5, 6 y 9); `prueba_api.py` (una sección); `pruebas.sh`/`pruebas.ps1` (una línea), `docs/NOVEDADES.md`, `docs/API.md`, `pasos/guias.py` (la entrada «Ficha del negocio» y una frase de «estilo_grafico») y un tramo al final de `prueba_recorrido.py`. Ya NO toca Configuración ni el selector de `fuenteDeEstiloLight`. No toca lo reservado por las otras ramas | 21-10-2026 |
| `rediseno-automatizar` | **Nueva interfaz de Automatizar** (maqueta aprobada por el dueño, 22-10: https://claude.ai/artifact/XKHvdT3eKxHgLvxdVzbZ4A, módulo Automatizar). Solo cómo se ve y dónde está cada cosa, con el sistema de Crear: proyecto en la cabecera con «+ Añadir guiones», Parrilla como tablero Pendientes · Usados · Publicados, la ficha de un guion en un panel lateral con «Pasar al Encargo ›», elegir de dónde salen los guiones con tarjetas que dicen lo que cuesta, el chat con Claude en su pestaña, la marca del cliente arriba; se quitan las pestañas que no se podían pulsar. Ningún param nuevo ni por defecto (regla 1), nada nuevo que pague, ninguna ruta se quita. **Las claves de YouTube/Meta/Apify NO se mueven aquí** (van a Configuración en otra rama, después de `seo-real`/`seo-real-3`). **Por zonas:** en `web/app.js` el bloque AUTOMATIZAR y AUTOMATIZAR → PARRILLA (`vistaParrilla` y vecinas); un bloque AUTOMATIZAR · TABLERO en `web/estilo.css`; `docs/NOVEDADES.md`, `docs/MANUAL.md` (el apartado de Automatizar); los escenarios de Automatizar de `prueba_recorrido.py`. No toca lo reservado por las otras ramas | 22-10-2026 |
| `rediseno-proyectos` | **Nueva interfaz de Tus proyectos y de la pantalla de un proyecto** (maqueta aprobada por el dueño, 22-10: https://claude.ai/artifact/XKHvdT3eKxHgLvxdVzbZ4A). Solo cómo se ve y dónde está cada cosa: «+ Nuevo vídeo» a la vista, buscador, «Sigue donde lo dejaste» con tarjetas con miniatura y estado, filtros de vídeos y vista tarjetas/lista, «⋯» por vídeo (Renombrar, Mover, Apartar), los botones de gestión del proyecto en «⚙ Ajustes del proyecto» (panel lateral), tocar un estilo abre «Nuevo vídeo / Editar». Ningún param nuevo ni por defecto, nada que pague, ninguna ruta se quita. **Coordinación con `etapa-foto-c` (autorizada por el dueño, 22-10, se programan a la vez):** el panel de Ajustes del proyecto lleva una lista de secciones (`SECCIONES_AJUSTES_PROYECTO`) con un hueco para «Ficha del negocio»: quien se una segundo coloca ahí el botón y el panel de la ficha, sin cambiarlos por dentro. **Por zonas:** en `web/app.js` la portada de Crear y `dentroDeProyecto` con sus vecinas (tarjetas de proyecto, de estilo y filas de vídeo); un bloque PROYECTOS · TARJETAS en `web/estilo.css`; `docs/NOVEDADES.md`, `docs/MANUAL.md` (su apartado); los escenarios de la portada y del proyecto en `prueba_recorrido.py` | 22-10-2026 |
| `rediseno-publicar` | **Nueva interfaz de Publicar y las claves de YouTube/Meta/Apify en Configuración** (maqueta aprobada por el dueño, 22-10: https://claude.ai/artifact/XKHvdT3eKxHgLvxdVzbZ4A). Pestañas Calendario · Por publicar · Resultados · Ajustes, «Te necesitan» fijo arriba, calendario forma **B** (compacto con «+N más», también en móvil; decisión del dueño), la ficha de un vídeo en seis pasos con barra de acción, Ajustes con lista de proyectos y pestañas; las claves de analizar cuentas pasan a Configuración (Automatizar enseña su estado y «Configurar ›»). El editor de portadas NO se rediseña. Ningún param nuevo ni por defecto, nada que pague, ninguna ruta se quita. **Coordinación con `portadas-2`, `seo-real` y `seo-real-3` (autorizada por el dueño, 22-10, se programan a la vez):** esta rama mueve DE SITIO `bloquePortadaPublicar`, el bloque PUBLICAR · SEO y la sección de clave de YouTube, sin cambiarlos por dentro; quien se una después las encaja en su sitio nuevo. No toca la memoria de scroll ni la regla `#toast`. **Por zonas:** en `web/app.js` el bloque PUBLICAR (calendario, lista, ficha, resultados, ajustes), en `pintarConfig` el sitio de las claves de analizar cuentas y, en Automatizar, SOLO la línea de esas claves (coordinado con `rediseno-automatizar`); un bloque PUBLICAR · PESTAÑAS en `web/estilo.css`; en el servidor, SOLO `probar_conexiones` nueva en `pasos/cuentas_ajenas.py` (tres GET sin coste) y su llamada en la ruta `/api/claves/probar` de `app.py`, más tres nombres en `NOMBRES_PROVEEDOR` (añadido el 22-10 tras la revisión); `docs/NOVEDADES.md`, `docs/MANUAL.md` (su apartado); los escenarios de Publicar y de las claves en `prueba_recorrido.py` | 22-10-2026 |
| `guion-visual` | **«Qué dibujan las imágenes»: lo que dice la voz o lo que dice el guion** (plan aprobado por el dueño, 22-10: `estado/plan_guion_visual_2026-10-22.md` del Proyecto). Con «lo que dice el guion» cada línea «Visual:» de la Parrilla (o el borrador que propone Claude y aprueba el dueño) es un plano; la frase de la voz deja de llegar al dibujante (`_con_narracion` no se aplica), la cámara de la línea va literal y el estado del tipo de relato se elige por línea; lo fijo (espacio, estados, reparto) manda con aviso antes de pagar. Sin `assets.imagenes`/`estilo.imagenes` guardado, prompts, cortes y firmas byte a byte como hoy (regla 1). **Propios:** `pasos/guion_visual.py` y `pasos/prueba_guion_visual.py` (nuevos). **Por zonas:** `pasos/parrilla.py` (`encargo_de`: `visuales` y la línea «Imágenes:»); `pasos/p6_assets.py` (`planificar`: el corte por líneas en modo guion; `_prompt_visual`/`_con_narracion`; la cámara como encuadre; el estado por línea en `_marcar_edicion`); `pasos/revisor_imagenes.py` (la línea visual en lugar de la frase); `pasos/presets_canal.py` (la clave `imagenes` del Estilo, junto a `relato`); en `app.py` un bloque GUION VISUAL nuevo justo después del de TIPO DE RELATO y la opción al crear (`_opciones_al_crear`); en `web/app.js` una línea en `BLOQUES_DEL_ENCARGO`, una en `BLOQUES_EXTRA_DEL_PASO.imagenes`, el selector junto al tipo de relato en «Cómo se cuenta» y funciones nuevas al final del bloque del tipo de relato; clases nuevas en `web/estilo.css` en un bloque GUION VISUAL; `pasos/guias.py` (una entrada y la plantilla de la Parrilla); `herramientas/claude_falso.py` (una respuesta más); `pruebas.sh`/`pruebas.ps1` (una línea); `docs/NOVEDADES.md`, `docs/API.md`, `docs/MANUAL.md`; `prueba_api.py` y un tramo al final de `prueba_recorrido.py`. No toca lo reservado por las otras ramas | 22-10-2026 |

Quien abre una rama la apunta aquí (en `main`, regla 8); quien la une a `main`,
la quita.

**`v2-fase-3` (vídeos sin voz) está EN PAUSA desde el 14-10-2026, por decisión
del dueño.** Sus ficheros no están reservados (`arreglos-voz`, que los tomó, ya está unida).
Quien la retome hace antes `git merge origin/main` (la voz habrá cambiado) y la
vuelve a apuntar en la tabla. Mientras siga en pausa, `v2-fase-4b` sigue
esperando, porque depende de ella.

### Cola de unión (decisión del dueño, 22-10-2026; reordenada el 22-10 por choques medidos)

Se une de una en una, en este orden. Antes de cada unión: la rama hace
`git merge origin/main`, pasa sus pruebas y la revisión independiente; el
dueño hace la instantánea de Hostinger; se une; `asvs actualizar`; se
comprueba que el Studio arranca. Solo entonces la siguiente. Una rama que no
está lista cede su turno a la siguiente lista (salvo las que dependen de ella).

Ya unidas: `tipo-de-relato`, `arreglos-crear-movil`, `portadas-2` (21/22-10),
`seo-real` con `seo-real-3` (22-10, en una sola unión y por delante de 1-3 a
petición del dueño: estaban probadas en el servidor).

El orden sale de unir de prueba cada rama con main y con las demás
(`git merge-tree`, 22-10): primero las que hoy no chocan con nada, y las que
tienen que encajar piezas de otras, detrás de esas otras.

1. `dominio-negocio` — al día con main, sin choques.
2. `rediseno-automatizar` — sin choques.
3. `rediseno-proyectos` — choque trivial (NOVEDADES, estilo.css).
4. ~~`seo-real`~~ y 5. ~~`seo-real-3`~~ — UNIDAS (22-10).
6. `rediseno-publicar` — encaja el SEO ya unido (el bloque PUBLICAR · SEO:
   `bloqueSeoVideo`, `bloqueBusquedasSeo`, `bloqueEncontraronSeo`,
   `seoDeRedPublicar`; y en Configuración `seccionClaveYouTube` y
   `seccionCanalYouTube`) en sus pasos nuevos, sin cambiarlo por dentro, y la
   línea de las claves de Automatizar (todo anotado en su informe).
7. `etapa-foto-c` (sale de `dominio-negocio`) — la que más tiene que poner al
   día: le faltan ~50 cambios de main (`tipo-de-relato`, `dominio-negocio`
   actualizada) y encaja su Ficha del negocio en `SECCIONES_AJUSTES_PROYECTO`:
   una línea `{ id: 'ficha-negocio', titulo: 'Ficha del negocio', pinta: c => panelNegocioProyecto(c.cliente) }`;
   el botón «✎ Editar la ficha» de `bloqueNegocioDelEstilo` pone
   `APP.light.ajustesProyecto = cid` en vez de `APP.light.negocioProyecto`, y
   sobran `abrirPanelNegocio` y su botón en la fila de mandos.
8. `guion-visual` — cuando esté lista; choca con `dominio-negocio` en
   `p6_assets.py` y `presets_canal.py` (al ponerse al día, sumar `imagenes` a
   la tupla de claves del Estilo junto a `relato` y `dominio`).

### El orden acordado

`parrilla` (Automatizar → Parrilla) se unió a `main` el 17-10-2026, y
`parrilla-2` con `analizar-cuentas` el 18-10-2026 (en una sola unión: la
segunda salía de la primera). Lo de abajo es el plan de fondo.

1. **Ahora, en paralelo (las tres ramas del máximo)**: la Etapa Foto A, la V2.0
   fase 3 y la V2.0 fase 4a (esta, con ficheros nuevos; ver abajo).
2. **La V2.0 fase 4 se parte en dos ramas**, porque cada mitad choca con una
   cosa distinta:
   - `v2-fase-4a` — la base para enchufar IAs y el motor de imágenes de ChatGPT
     (membresía y API). Puede empezar ya con ficheros NUEVOS (la base y el
     motor, en `motores/` o donde decida su chat). Lo único que toca un fichero
     reservado es enchufar el motor nuevo en `p6_assets.py`, y eso espera a que
     la Etapa Foto A esté unida. El prompt lo sigue armando `p6_assets.py`; la
     base solo decide a quién se le manda.
   - `v2-fase-4b` — ElevenLabs y la música por IA. Empieza cuando la V2.0 fase 3
     esté unida: las dos tocan la voz (`p4_voz.py`, `p5_revision_audio.py`,
     `marcas_tts.py`) y la música (`sonido.py`), y en un vídeo sin voz es
     probable que la música pase a marcar el ritmo.
3. **La Etapa Foto B** va después de la A. Añade imágenes de producto a cada
   plano, así que todo motor de imágenes de la base de 4a tiene que aceptar
   VARIAS imágenes de referencia por llamada (hoy se adjuntan estilo, reparto y
   continuidad: hasta ~11).
4. **La V2.0 fase 5 va la última**, con la Etapa Foto A, la fase 3 y la 4a
   unidas (la B, recomendada). Veo y Kling se enchufan como motores de la base
   de 4a, no aparte. El paquete de ida y vuelta lleva, por plano, la imagen
   inicial, el prompt, la carta de encuadre y, cuando exista, sus productos.
5. **La Etapa Foto C** va después de la B, en la misma conversación que A y B.
   Es casi solo pantalla (`web/app.js`), así que se abre cuando no haya otra
   rama abierta cambiando la pantalla; si la fase 3 o la 4a siguen abiertas, se
   espera a que se unan.

### Lo que la Etapa Foto A promete a las demás fases

- `estilo.modo` vale `"ilustracion"` o `"foto"`. **Si no está guardado se lee
  como `"ilustracion"` y el prompt sale idéntico al de hoy**: no escribas ese
  param por defecto en ningún sitio (regla 1 de arriba).
- La escalera de encuadres actual NO se toca; el modo foto tendrá la suya.
- Las reglas de foto van en un fichero aparte de `motores/reglas/reglas.json`,
  porque `asvs actualizar` no sobrescribe `reglas.json` y no llegarían al
  servidor.
- La fase 5 debe respetar `estilo.modo`, la carta de encuadre de cada plano y,
  cuando exista (Etapa B), el campo `productos` de cada plano.

---

## El grafo, y por qué no se toca

```
ingesta → brief → guion → voz → revision_audio → assets → callouts → render
```

Los ids **no se renombran** y **no se quita ninguno**, ni el que parezca que no
hace nada. `brief` es una cuenta determinista de dos segundos que no llama a
ningún modelo, y aun así sigue en el grafo: su firma encadena la del guion, así
que sacarlo dejaría obsoleto el guion de todos los proyectos guardados, en
cascada hasta el render. Mover su PANTALLA no cuesta nada; mover el PASO es una
migración.

### Lo que hay que saber de `nucleo/estado.py`

- **El manifiesto de cada versión vive fuera de `estado.json`**, en
  `pasos/<paso>/_versiones/v<N>.json`. Antes iba dentro y crecía como versiones
  × unidades: un vídeo de 300 planos llegó a 320 MB de `estado.json` y 9 s por
  petición. `Estado.manifiesto_version` **lanza** si el fichero falta o trae
  menos unidades de las que dice la versión: devolver `{}` vaciaría el mapa vivo
  y la pantalla ofrecería regenerar el vídeo entero. Se sigue leyendo el formato
  antiguo, y eso es permanente: un proyecto que llegue de fuera funciona sin
  migrar.
- **`completar()` escribe el manifiesto ANTES de tocar `datos`.** No es estilo:
  al revés, un fallo dejaría en disco `activa: N` con `versiones` sin la N, y
  «Revertir» enseñaría las imágenes de la versión anterior como si fueran las
  recién pagadas.
- **La carpeta de versiones va FUERA de `v<N>/`**: `sembrar_trabajo` copia la
  carpeta de la versión activa a `trabajo/` y `_recoger_trabajo` la vuelca en la
  SIGUIENTE, así que un manifiesto dentro de `v21` acabaría dentro de `v22` con
  pinta de correcto.
- **`estado.json.anterior` es la copia buena de antes del último guardado**
  (enlace duro, sin coste). Un `estado.json` ilegible vuelve a ella y lo apunta
  en la bitácora; sin ella, `EstadoIlegible` → 503. No se arranca de cero
  nunca. Una mudanza no la reescribe: el siguiente guardado la renueva.
- **No caches el manifiesto en el documento.** `_guardar` filtra las claves con
  guion bajo SOLO en la raíz, así que una cache anidada se escribiría dentro de
  `estado.json` y el fichero recuperaría sus 320 MB en silencio.

---

## Copiar un proyecto o un estilo a otra máquina

**No basta con copiar la carpeta.** Un proyecto guarda rutas absolutas en tres
sitios: las salidas de cada unidad, los manifiestos de cada versión y las
referencias de estilo — y ese último entra en la firma del paso. Copiar y ya
deja `assets`, `callouts` y `render` en obsoleto: la pantalla ofrece regenerar
todos los planos ya pagados.

Hay que **mudar las rutas y volver a sellar las firmas**, y el sellado tiene dos
trampas:

1. **No se re-sella todo, solo lo que la mudanza movió.** `guion` guarda a
   propósito una `firma` que no cuadra con la calculada (cuando alguien corrige
   el guion a mano manda `firma_propia` y la otra se queda atrás). «Arreglarla»
   mueve el sello de salida del guion, que entra en la firma de la voz, y la
   cascada deja obsoleto todo lo de abajo. La regla es comparar contra la firma
   **calculada ANTES de mudar**.
2. **Los manifiestos del histórico también llevan firmas de unidad.** Sin
   re-sellarlos el estado vivo queda perfecto y cada «Revertir» enseña todas las
   unidades en obsoleto.

Y la comprobación es la mitad del trabajo: hay que contar **cuántos de los
ficheros que el estado dice haber producido están de verdad en disco**, en las
dos máquinas, y comparar. Una mudanza a medias no da ningún error al abrir el
proyecto; se ve al pedir una miniatura.

---

## La interfaz: una pantalla, y sin dependencias

`web/app.js` son ~10.000 líneas de JavaScript a pelo — sin framework y sin
`npm install`. Se sirve con `?v=<sello>` calculado del propio fichero, así que
**no hay ningún número que subir a mano** al cambiarlo.

**HAY UNA SOLA PANTALLA.** Hubo dos modos (uno guiado y uno desglosado en
pestañas) y aquí solo está el guiado. Si te encuentras algo que parece del otro
—una tabla de pestañas, un panel por paso— comprueba antes si lo alcanza
alguien:

```bash
python herramientas/alcanzables_js.py            # qué está vivo y qué no
python herramientas/alcanzables_js.py --quien X  # quién nombra a X
python herramientas/alcanzables_js.py --borrar   # una vuelta, y vuelve a correrla
```

**Dos funciones con el mismo nombre es un fallo silencioso.** En JavaScript la
segunda se lleva la primera por delante, sin un solo error, y la de arriba deja
de ejecutarse leyéndose como si funcionara. Pasó: el coste que se enseña antes
de generar compartía nombre con el medidor del vídeo ya empezado, y el hueco de
al lado del botón llevaba vacío desde el día que se escribió. Lo canta
`sin_llamar_js.py`.

Y por la CSP del proxy, **no se pueden usar atributos `style=""` en el HTML**:
el navegador los bloquea. Todo estilo va en `estilo.css`.

**El login vive DELANTE, y no es de aquí.** La interfaz le pregunta quién ha
entrado (`/api/me`) y le pide salir (`/api/logout`) a un servicio aparte; en
local esas rutas no existen, la pastilla de la cuenta se queda oculta y no pasa
nada. Lo único a tener en cuenta si se despliega detrás de él: **al salir se va
a `${BASE}/login`**, no a donde diga la respuesta. Ese servicio contesta
`/login` a secas porque atiende a dos versiones del estudio y no sabe por cuál
se le está llamando; quien sí lo sabe es esta página. Con la respuesta a pelo,
salir desde `/v2/` te dejaba en el login de la otra versión.

---

### Crear: el carril y dónde enganchar (21-10-2026)

Crear es la forma «A · Carril»: seis pasos con su estado (`PASOS_CARRIL`,
`estadosDelCarril`), una salida que vuelve al proyecto del vídeo
(`salidaTusProyectos`) y UNA barra de acción por paso (`barraDeAccion`,
`botonDeBarra`). Para añadir algo **no se crea otra barra ni otro bloque suelto**:

- **Un bloque en el Encargo**: una línea `{ id: 'mi-bloque', pinta: c => miBloque(c) },`
  en `BLOQUES_DEL_ENCARGO`, en el sitio donde deba salir. `c` trae
  `{ nuevo, v, e, ficha }`; con `nuevo: true`, `e` es el borrador y no se guarda
  nada hasta «Generar el guion». Pintar no escribe en `e` (regla 1).
- **Un bloque al final de otro paso** (`estilo`, `encargo`, `guion`, `voz`,
  `imagenes`, `video`): en `BLOQUES_EXTRA_DEL_PASO`, una función `c => nodo|null`.
- **Un botón de pago** va en la barra de su paso con `botonDeBarra`, con su
  precio del plan (nunca «gratis» sin el plan) y su `confirm`: mientras algo del
  vídeo se lanza, la barra se apaga sola (`LANZANDO_TANDA`, `MONTANDO_LIGHT`).
- **Los ajustes del montaje no montan al tocarlos** (decisión del dueño): se
  guardan con `remontar: false` y solo monta «Montar el vídeo con N cambios»,
  que con MP4 es SIEMPRE `POST /montaje/aplicar` (gratis). Lo pendiente vive en
  la página (y en localStorage por vídeo), nunca como param.
- El selector «Tipo de imagen» sigue en `fuenteDeEstiloLight` (pestaña «Cómo se
  ve» de la ficha).

---

## El asistente y la guía de inicio

La burbuja de abajo a la derecha es `pasos/asistente.py` más las rutas
`/api/asistente/*` de `app.py`; la guía de la primera vez son las tarjetas de
`abrirInicio` en `web/app.js`. Lo que no se ve leyendo el código:

- **El asistente corre el CLI con `Read`, `Grep` y `Glob` sobre la carpeta del
  Estudio, y con las HERRAMIENTAS DEL ESTUDIO** (`pasos/mcp_estudio.py`, un
  servidor MCP mínimo que el CLI carga con `--mcp-config` y que van
  pre-autorizadas como `mcp__estudio__*`): probar las claves de verdad, ver el
  estado, los trabajos, la bitácora, cancelar un trabajo. Cada herramienta
  habla con la API del Estudio por HTTP (`ESTUDIO_API`, que pone `app.py` al
  arrancar), nunca importando código: lo que hace es lo que haría la
  pantalla. Sin Bash, sin escribir, sin internet. **`Read` va acotado** a la
  carpeta del Estudio y a la de proyectos (`asistente.herramientas_permitidas`):
  `Read` a secas lo autorizaba en todo el disco, y en el VPS las claves NO están
  dentro del código (`/opt/as-video-studio/datos/secretos`). Encima van los
  vetos de `asistente.vetos_de_lectura`: `./secretos`, el almacén donde esté
  (`ESTUDIO_SECRETOS`), la sesión del CLI (`~/.claude`, `CLAUDE_CONFIG_DIR`) y
  `.env`, `claves.json` y `.credentials.json` por nombre en todo el disco
  (`Read(//**/.env)`: la forma `**/.env` solo vale dentro del cwd). Cada
  veto sale también como `Grep(...)` y `Glob(...)` (16-10-2026): los vetos de
  `Read` solo frenan a Grep «cuando pueden», y `datos/**` sí se puede buscar. Está
  medido con el CLI de verdad (13-10-2026): lee el código y los proyectos, y
  niega las seis rutas con secretos. El prompt de sistema también se lo dice,
  pero la regla es la que manda. Si alguna vez las claves se guardan en otra
  carpeta, se añade a `carpetas_de_secretos` antes que nada.
- **Contesta con sonnet/medium a propósito**, no con el defecto del canal
  (opus/xhigh): un chat pide segundos. No pasa por `cli_claude.por_defecto_de`,
  que subiría al defecto del canal. Se cambia con `ESTUDIO_ASISTENTE_MODELO` y
  `ESTUDIO_ASISTENTE_ESFUERZO`.
- **Una charla es una sesión del CLI** (`--resume` con el `session_id` del
  sobre). Vive en memoria: recargar la página la reencuentra, reiniciar el
  servicio la pierde y la pantalla abre otra sin ruido. Si reanudar falla se
  vuelve a empezar con los últimos turnos pegados; un cupo agotado o un plazo
  vencido NO se reintentan.
- **La respuesta se sigue preguntando, no con una petición larga**: detrás del
  proxy una petición de un minuto se corta a los sesenta segundos. Un turno por
  charla; el segundo a la vez es un 409.
- **`_asistente_listo` tiene que decir lo mismo que `cli_claude.cuentas()`**:
  sin ninguna cuenta con `entrada`, el motor habla con la sesión por defecto
  del CLI, y el asistente también. Una cuenta añadida y nunca logueada no
  cuenta en ninguno de los dos sitios.
- **«Con sesión» no es «funciona».** `pasos/salud_cli.py` apunta cómo
  respondió cada cuenta la última vez (ok, cupo, sesión, tiempo, error) y lo
  escribe `cli_claude._una_pasada`, el único sitio por el que pasa toda
  llamada. La pantalla lo enseña al lado de la sesión (burbuja, Configuración,
  guía) y «Probar» le habla con haiku y una palabra. Un estado malo se queda
  hasta que una llamada vuelve a salir bien: nadie adivina cuándo se renueva
  un cupo, el mensaje del CLI ya trae la fecha. Toda suite que doble el CLI
  redirige `ESTUDIO_SECRETOS`, o la salud de sus dobles acaba en el almacén.
- **Las claves se prueban contra su servicio** (`pasos/comprobar_claves.py`)
  con llamadas que no cuestan dinero. Lo único que no puede saber es si OpenAI
  tiene saldo, y lo dice. FreeSound va con el token de la columna «Client
  secret/Api key», no con el Client id.
- **En la guía hay UNA cuenta de Claude** y el acceso arranca solo al abrir la
  tarjeta; el código se envía al pegarlo. La cadena de cuentas de respaldo
  sigue en Configuración, que es donde se necesita.
- **La foto del estado la hace `app.py`** (`_foto_para_asistente`) y se puede
  mirar en `GET /api/asistente/foto`. No lleva ninguna clave; lo comprueba
  `prueba_api`.
- **La marca de la guía (`onboarding_visto`) es un ajuste del servidor.** Toda
  suite que la toque redirige `ESTUDIO_AJUSTES`, o la marca acaba en el
  `ajustes.json` de verdad.
- **Configuración y la guía comparten estado** (`estadoConfig()`): quien
  guarde una clave llama a `repintarClaves()`, no a `pintarConfig()`, y las dos
  pantallas se enteran.
- **En `app.js`, un acento grave dentro de una expresión regular** parte por la
  mitad los tokenizadores de `herramientas/` (se creen que empieza una
  plantilla) y dan por muerto todo lo que venga detrás. Se escribe `\x60`.

---

## La V2.0: nombre, diseño, guías, novedades y notas

- **El producto se llama «Automatización Contenido Studio»** en todo lo que se
  ve (`NOMBRE_PRODUCTO` en `app.py`). Los nombres INTERNOS no se cambian:
  `/opt/as-video-studio`, el comando `asvs`, los servicios `as-video-*`, el
  repositorio. Renombrarlos rompe las instalaciones que ya funcionan sin que
  nada lo diga.
- **Todo cambio visible se apunta en `docs/NOVEDADES.md`.** Lo enseña
  Configuración → Novedades y lo lee el asistente en el primer turno: si no se
  apunta, el asistente explica el sistema de antes.
- **Las guías de escritura viven en `pasos/guias.py`, y SOLO ahí.** La pantalla
  las pide a `/api/sistema/guias` y el asistente las lee con Read. Si cambia lo
  que hace un campo (el código que dice su clave `usa`), se revisa su guía.
  El botón sale por el TÍTULO del bloque (`GUIA_DE_BLOQUE` en `app.js`).
- **Las notas de mejoras son datos**: `<proyectos>/_sistema/notas.json`, fuera
  del código, para que `asvs actualizar` no se las lleve.
- **El tema** (claro/oscuro) es solo `data-tema="claro"` en `<html>` y la paleta
  de `:root[data-tema="claro"]`. Ni un color fuera de las variables.
- **Dos funciones con el mismo nombre en Python también se pisan sin avisar.**
  Pasó al añadir las notas: `_ruta_notas()` ya existía para el repaso y la
  nueva la pisó (500 al guardar la nota de un vídeo). Lo canta
  `herramientas/repetidas_py.py`; los huecos de plantilla sin rellenar
  (el `KeyError: 'fijos'`) los canta `herramientas/plantillas_py.py`.

---

## Lo que NO hay, y no es un olvido

Este producto sale de uno más grande, y estas piezas se quitaron a propósito.
Si echas una en falta, esto es por qué no está:

| Qué | Por qué no está |
|---|---|
| El modo editor, con sus pestañas por paso | una sola pantalla; lo demás era el mismo motor visto en detalle |
| Vídeos de YouTube como material | el material es lo que se escribe, y vive en `ingesta.texto` |
| El documentalista (buscar en internet) | con una sola vía para el material no hay nada que decidir |
| Los personajes fijos del canal | el **reparto** de cada vídeo sí está: es lo que sostiene la consistencia visual |
| Las menciones ilustradas de un producto | con ellas se fue todo lo que llevaba el nombre de un patrocinador |
| El dictado por voz con un modelo local | pedía un modelo aparte y su propio entorno. El dictado del ASISTENTE volvió en la V2.0 sin instalar nada: graba en el navegador y lo transcribe la API de OpenAI (`pasos/dictado.py`), o el dictado del propio navegador si no hay clave |
| El bloc de enlaces, la bitácora, el monitor | notas y telemetría que no hacen un vídeo |

**Y no vuelvas a meter ninguna sin mirar `pasos/recetas.py`:** una tarea que no
está en la receta no corre, y una pantalla que la ofrece llama a una ruta que ya
no existe. Es exactamente lo que había que arreglar aquí — la interfaz seguía
pintando el micrófono y el mapa después de que el motor dejara de servirlos.

---

## Las medidas que hay, para no volver a medirlas

**El render** (`pasos/medir_render.py --reparto`), en 8 vCPU:

| Procesos | fotogramas/s |
|---|---|
| 1 | 1,98 |
| 4 (lo que elige `cpu_count()//2`) | 6,75 |
| **8 (`ESTUDIO_LOTES=8`)** | **10,40** |
| 16 | 10,85 — ya no escala |

La regla automática pide 4 y deja media máquina parada: en un servidor de ocho
hilos, `ESTUDIO_LOTES=8`.

**Lo que cuesta una imagen** no es el precio de OpenAI: es la factura. A cada
imagen se le adjuntan sus referencias de estilo, reparto y continuidad, y esas
se pagan como tokens de entrada — el 87 % del gasto en calidad baja. Medido
sobre 1.439 imágenes (mediana 5.114 tokens de entrada por imagen):

| Calidad | Imagen | Referencias | Total | Real | Aparente |
|---|---|---|---|---|---|
| low | 0,006 $ | 0,041 $ | **0,047 $** | — | — |
| medium | 0,041 $ | 0,041 $ | **0,082 $** | **1,7×** | 6,8× |
| high | 0,165 $ | 0,041 $ | **0,206 $** | **4,4×** | 27,5× |

El número de tokens vive en `pasos/ajustes.py:TOKENS_ENTRADA_POR_IMAGEN`. Si
cambia cuántas referencias se adjuntan, se vuelve a medir con el campo
`tokens.entrada` de las operaciones `imagen` de `coste_global.jsonl`.

**La calidad se elige en Configuración y es el punto de partida de los vídeos
NUEVOS**: se escribe en el param `calidad` de `assets` al crear el proyecto y no
se lee al generar. A propósito — `calidad` entra en la firma de cada imagen, así
que un defecto retroactivo dejaría obsoletas las imágenes de todos los proyectos
que nunca la fijaron, y regenerarlas se paga.

**Cambiar la calidad de un vídeo con imágenes hechas no redibuja nada** (traer
el estilo, cambiar `calidad`): p6 conserva todo PNG que exista si nadie lo pide.
Lo dice el aviso de «Traer el estilo» y, en las diapositivas, «N imágenes siguen
en otra calidad» con su botón (`POST /imagenes/calidad`, que manda SOLO esas como
unidades pedidas). La calidad de cada imagen va en su ficha (`calidad`, desde el
15-10-2026); en las viejas se deduce de la firma (`p6_assets.calidad_de_ficha`) y
si no se puede es «desconocida» y no se ofrece. **No cambies la forma de
`_firma_imagen`**: es la clave del banco y lo que permite esa deducción.

**Del render se guardan las 5 últimas versiones** (y siempre la activa):
`estado.VERSIONES_QUE_SE_GUARDAN`, decisión del dueño del 16-10-2026, y
`ESTUDIO_VERSIONES_RENDER` para cambiarlo. Cada montaje copia el vídeo entero en
una `v<N>` nueva. La poda la hace `completar()` al sellar: primero quita las
entradas del documento y guarda, y después borra las carpetas y sus
manifiestos, para que el estado nunca nombre una versión que ya no está. Los
demás pasos guardan todas: son pequeños y la pantalla ofrece volver a ellas.

**`trabajo/` del render va con enlaces duros a la versión activa**
(`sembrar_trabajo(..., enlazar=True)`, fuera de Windows, 17-10-2026): un fichero
de `trabajo/` puede ser EL MISMO que el de `v<N>`. Nada escribe encima de una
ruta de ahí sin `medios.romper_enlace(ruta)` antes (o `os.replace`):
`open(..,"w")`, `ffmpeg -y` y `shutil.copy2` sobre un destino que existe
cambiarían la versión anterior sin ningún error. Lo comprueba
`prueba_piezas.prueba_enlaces_del_render`; **si añades un escritor nuevo al
render, añádelo ahí**. Assets y callouts siguen copiando a propósito.

**Cancelar es en el acto, y se hereda** (18-10-2026). `GestorTrabajos` pone
`avisar.al_cancelar(fn)` y `cancelar()` llama a `fn` al momento: quien espera a
un subproceso se registra ahí (`estadisticas.Avance` lo hace solo). Quien
envuelva `avisar` en otra función copia el atributo, o se queda con el latido de
2 s. En Linux el CLI va en su propio grupo (`cli_claude.GRUPO_PROPIO`) y
`matar_arbol` mata el grupo; nunca hagas `killpg` a un proceso sin su grupo
propio, que comparte el del servicio. Ninguna tanda de imágenes paga sin
preguntar antes a `avisar`, y los pools van por `moodboard.en_paralelo` (tira la
cola al primer fallo). En el taller, `_taller_reservado` sostiene el cerrojo de
la cadena durante el reparto con Claude: no lo tomes sin tope desde otra ruta.

**El precio por imagen del cotizador** (`ajustes.precio_por_imagen`) es la
mediana de lo cobrado en imágenes de PLANO (`escena:`), por calidad y, con 20
muestras, por modo (foto/ilustración, que viaja en el `detalle` de cada
operación `imagen`). Las láminas y las hojas de reparto no entran: llevan menos
referencias y abarataban el precio de un plano. Sin muestras, la tabla de arriba.

---

## Antes de dar algo por terminado

```bash
powershell -NoProfile -File pruebas.ps1      # Windows
bash pruebas.sh                              # Linux: el mismo recorrido
```

**Una suite que sale en verde con el resumen en blanco es sospechosa**:
`prueba_ajustes.py` llegó a perder su `main` y pasaba sin ejecutar ni una
comprobación. Toda suite termina con su `if __name__ == "__main__"` y una línea
con «comprobaciones».

Las veintiocho en verde, y las herramientas de análisis sin nada que decir
(`huerfanas_js` trae dos sospechosas de siempre, `async` y `fallar`, que no son
llamadas).
Y si has tocado la interfaz, **ábrela**: una regla de CSS de menos o un bloque
que no se pinta no da ningún error en ningún sitio. Para eso está
`prueba_recorrido.py` (va en `pruebas.sh`): arranca el Estudio con datos de
prueba y motores simulados, recorre las pantallas con Chromium pulsando como
una persona y comprueba que lo que tiene que verse SE VE. Si añades una
pantalla o un botón, añade su paso ahí. Las capturas quedan en la carpeta que
imprime al empezar (`--capturas carpeta` para elegirla).

**La revisión completa, que es lo que se hace antes de dar por buena una
versión** (11-10-2026, después de que el dueño encontrara en un minuto cinco
fallos que el recorrido «verde» no veía). El recorrido ya la lleva dentro:

1. **El vídeo de prueba es como uno de verdad**: guía de estilo, dirección,
   música y efectos subidos, y la voz con las tildes rotas de antes del
   10-10. Un vídeo de prueba más limpio que los reales esconde sus fallos.
2. **Todos los botones** (`todos_los_botones`): en cada pantalla se pulsan
   uno a uno y cada uno tiene que cambiar algo que se vea, sin errores. Un
   botón muerto falla la suite.
3. **La cobertura** (`herramientas/inventario_botones.py`): al final se
   imprime cuántos botones del código ha VISTO y PULSADO el recorrido, y
   `cobertura.json` lista los que nunca salieron. Un botón nuevo que no sale
   ahí es un botón sin probar: añade su escenario (`lo_que_sale_a_veces`).
4. **Repintar no pierde nada** (`repintar_no_pierde_nada`): la pantalla se
   repinta sola; lo escrito tiene que seguir ahí.
5. **Tamaños, temas y textos** (`tamanos_temas_y_textos`): cada pantalla en
   móvil, tableta y ordenador y en los dos temas, sin salirse por los lados,
   sin imágenes gigantes, sin la burbuja tapando un botón y sin «undefined»,
   «NaN», «null» ni tildes rotas. Los textos de todas las pantallas quedan en
   `textos_de_pantalla.txt` para leerlos de corrido.
6. **Cada fallo que reporte el dueño entra como comprobación** en el recorrido
   (`lo_que_se_vio_el_10_de_octubre`, `rehacer_y_verlo_en_el_video`) y se
   comprueba que falla SIN el arreglo antes de darlo por arreglado.
7. **Una revisión independiente** del diff (un agente que no ha escrito el
   cambio), centrada en dinero, firmas y carreras.

Tres cosas que ahorran perseguir fallos que no existen:

- `prueba_pasos_visuales` reutiliza `%TEMP%\estudio_prueba_visual` entre
  ejecuciones; si una pasada se corta a medias, la siguiente falla por el estado
  sucio. `pruebas.ps1` la borra.
- En `prueba_pasos_visuales`, «el vídeo sale idéntico se reparta en procesos o
  corra en fila» **puede fallar en una máquina cargada** (2 núcleos con otra
  suite o un recorrido a la vez: visto el 16-10 dos veces, siempre un plano).
  Repetida sola, pasa. Si falla sola, entonces sí es de verdad.
- `prueba_pasos_voz` sale a Cartesia de verdad **si hay clave**; si no, omite esa
  parte y lo dice. No es un fallo.
- `prueba_login` llama al CLI de Claude de verdad. Es la única que comprueba que
  el CLI sigue dejando entrar sin terminal y sin abrir un navegador.
- **Las plantillas de la configuración del servidor viven en
  `despliegue/plantillas.sh`** y las usan `instalar.sh` y `asvs actualizar`. El
  sitio de nginx NO está ahí a propósito: lo edita certbot. Lo nuevo de proxy va
  en los snippets; una variable nueva del entorno se añade en
  `plantilla_entorno` y `actualizar` la agrega sin pisar las que hay.
- **En `app.py`, nada bloqueante dentro de una ruta `async def`**: va a
  `_en_hilo` (run_in_threadpool). El bucle de eventos es uno para todo el
  servicio.
- **Lo del despliegue no va en `pruebas.sh`**: si tocas `despliegue/asvs` o
  `estudio-clave`, corre a mano `bash despliegue/prueba/prueba_actualizar.sh` y
  `bash despliegue/prueba/prueba_estudio_clave.sh` (raíz falsa, no tocan nada).

**Las diapositivas suenan con la toma de `voz`**, no con la de
`revision_audio` (`_audio_de_la_toma`, 16-10-2026): los planos se cortan contra
la voz y el render monta la voz; la revisión es una resíntesis con sus propios
tiempos, y con ella «Oírla» saltaba al final del audio y se callaba.

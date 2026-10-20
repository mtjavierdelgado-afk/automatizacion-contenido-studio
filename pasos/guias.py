"""Las GUIAS de escritura: como rellenar cada campo para que el sistema lo entienda.

QUE PROBLEMA RESUELVE
---------------------
Cada campo de texto del Studio lo lee una pieza distinta, y cada pieza solo sabe
hacer una cosa con el. Las indicaciones del estilo grafico se convierten en una
guia de DIBUJO de 260-400 palabras: lo que no sea como se ve una imagen (un
titular, un logo, el formato vertical) no tiene donde caer y, peor, puede salir
dibujado como letras inventadas. El tono se convierte en instrucciones para el
redactor que tienen que valer para CUALQUIER tema. Y asi con todos.

Escribir sin saber eso es la causa de casi todos los «el sistema no me hace
caso». Estas guias lo dicen campo por campo, con una plantilla que se rellena y
un prompt para pegar en otra IA (ChatGPT, Claude) junto con unas notas sueltas,
para que te devuelva el texto ya en la forma que el Studio entiende.

UNA SOLA FUENTE
---------------
La pantalla las pide a `/api/sistema/guias` y el asistente las lee de aqui
mismo (lo dice su prompt de sistema). Cambiar una guia es cambiarla en este
fichero, y las dos caras se enteran.

Lo que dicen las guias esta sacado del codigo que usa cada campo, y lo dice al
lado de cada una (`usa`): si ese codigo cambia, la guia se revisa con el.
"""

GUIAS = {
    # ------------------------------------------------------------------ estilo
    "estilo_grafico": {
        "titulo": "Indicaciones del estilo gráfico",
        "donde": "Crear un estilo → Estilo gráfico → Indicaciones",
        "usa": "pasos/estilo.py (generar_guia, y su contrato de foto), "
               "pasos/moodboard.py y el «Tipo de imagen» (estilo.modo, "
               "pasos/p6_assets.py)",
        "que_hace": [
            "Primero eliges el TIPO DE IMAGEN: «Ilustración» (lo de siempre) o "
            "«Foto realista». Con foto, la guía se escribe para fotografía "
            "(cámara, lente, luz, color, gente, lugares) en vez de para dibujo "
            "(trazo, relleno, dedos), y cada imagen se pide como foto de un "
            "fotógrafo profesional, con sus propias reglas y sus propios "
            "encuadres (plano general, manos en la acción, reacción...). Sirve "
            "para cualquier proyecto; si el vídeo va de consolas, se suman solos "
            "los encuadres y las reglas de EstadoPlay.",
            "Las IMÁGENES que subes son la fuente principal: el sistema las mira y "
            "escribe una guía de dibujo de 260 a 400 palabras que va dentro de "
            "cada imagen que se genera. Sube de 1 a 24 (mejor 5 o más), todas con el aspecto "
            "que quieres para el vídeo.",
            "Las indicaciones escritas MANDAN sobre las imágenes cuando chocan. "
            "Sirven para lo que una imagen no dice sola: «igual pero más cálido», "
            "«sin personas», «luz natural siempre».",
            "Solo cuenta lo que se VE en una imagen: luz, paleta, materiales, "
            "trazo o tipo de foto, encuadre, nivel de detalle, qué aparece y qué no.",
        ],
        "si": [
            "Describe el aspecto: realista o ilustración, luz, colores, texturas, "
            "encuadre, qué tipo de lugares y personas salen.",
            "Di lo que NO quieres ver (lujo excesivo, colores neón, decoración "
            "recargada).",
            "Que las imágenes que subas sean coherentes con lo que escribes: si "
            "pides fotografía realista, sube fotos, no ilustraciones.",
            "Si quieres fotos, elige «Foto realista» en «Tipo de imagen»: "
            "escribirlo solo en las indicaciones no basta, porque sin ese "
            "selector cada imagen se sigue pidiendo como ilustración.",
            "Entre 60 y 250 palabras es lo ideal: más se condensa y se pierde.",
        ],
        "no": [
            "Titulares, hooks, tipografías, textos en pantalla o subtítulos: el "
            "estilo no escribe letras en las imágenes (los subtítulos van aparte).",
            "Logos o nombres de marca dibujados: saldrían distintos en cada imagen.",
            "El formato (vertical 9:16): se elige al crear cada vídeo.",
            "Estructuras de contenido (A/B, antes/después, problema→solución): son "
            "del guion y de las indicaciones de cada vídeo, no del dibujo.",
        ],
        "plantilla": (
            "TIPO DE IMAGEN: [fotografía realista / ilustración / 3D / acuarela...] "
            "de [qué se muestra].\n"
            "LUZ: [natural, suave, dura, de tarde...].\n"
            "PALETA: [colores base] con acentos de [colores de acento]. Evitar "
            "[colores que no quieres].\n"
            "MATERIALES Y TEXTURAS: [cómo se ven las superficies].\n"
            "ENCUADRE Y CÁMARA: [plano general, medio, detalle; altura de cámara; "
            "perspectiva].\n"
            "ESPACIOS / ESCENARIOS: [qué tipo de lugares, tamaño, nivel de "
            "realismo].\n"
            "PERSONAS: [si aparecen, cómo y cuándo; o «sin personas»].\n"
            "NUNCA: [lo que no debe aparecer nunca]."
        ),
        "ejemplo": (
            "TIPO DE IMAGEN: fotografía editorial realista de interiores de "
            "departamentos reales en Lima.\n"
            "LUZ: natural, suave, de ventana; sombras reales y exposición sin "
            "quemar.\n"
            "PALETA: blanco cálido, hueso, arena, madera natural y grafito, con "
            "acentos de terracota apagado y verde de plantas. Evitar neón, dorado "
            "y filtros azules.\n"
            "MATERIALES Y TEXTURAS: madera, piedra y textiles con textura visible "
            "y pequeñas imperfecciones.\n"
            "ENCUADRE Y CÁMARA: perspectiva arquitectónica coherente, cámara a la "
            "altura de los ojos, verticales rectas.\n"
            "ESPACIOS: departamentos pequeños y medianos, habitables, con "
            "decoración moderada; nunca mansiones ni showrooms vacíos.\n"
            "PERSONAS: solo cuando muestran escala o uso, de forma secundaria.\n"
            "NUNCA: muebles deformes, grifería imposible, reflejos incoherentes, "
            "lujo hotelero."
        ),
        "prompt_ia": (
            "Voy a crear un estilo gráfico en un sistema que genera las imágenes "
            "de mis vídeos con IA. Ese sistema solo entiende cómo SE VE una imagen "
            "(tipo de imagen, luz, paleta, materiales, encuadre, escenarios, "
            "personas y lo que nunca debe salir) y lo resume en una guía de dibujo "
            "de unas 300 palabras.\n\n"
            "Con mis notas de abajo, escríbeme las indicaciones del estilo "
            "gráfico siguiendo EXACTAMENTE estas etiquetas, una línea o dos por "
            "etiqueta: TIPO DE IMAGEN, LUZ, PALETA, MATERIALES Y TEXTURAS, "
            "ENCUADRE Y CÁMARA, ESPACIOS / ESCENARIOS, PERSONAS, NUNCA.\n\n"
            "Reglas: entre 120 y 250 palabras en total. No incluyas titulares, "
            "tipografías, textos en pantalla, logos, nombres de marca, formatos "
            "(vertical/horizontal), ni estructuras de contenido (A/B, "
            "antes/después, hooks): todo eso se decide en otra parte del sistema. "
            "Si mis notas hablan de eso, ignóralo y al final dime en una lista "
            "aparte qué has dejado fuera y dónde debería ir.\n\n"
            "MIS NOTAS:\n[pega aquí tus notas o tu manual de marca]"
        ),
    },

    # -------------------------------------------------------------------- tono
    "tono": {
        "titulo": "Tono del guion",
        "donde": "Crear un estilo → Tono del guion",
        "usa": "pasos/tono.py",
        "que_hace": [
            "Tu descripción se convierte en instrucciones para el redactor "
            "repartidas en piezas: registro, nivel técnico, público, ritmo del "
            "relato, estructura, forma de contar, bloques, qué hacer con las "
            "fuentes y qué evitar.",
            "Esas instrucciones se usan en TODOS los vídeos de este estilo, así "
            "que tienen que servir para cualquier tema.",
        ],
        "si": [
            "Describe cómo suena: de tú o de usted, cercano o formal, con o sin "
            "humor, qué tan técnico.",
            "Di a quién le hablas y qué sabe ya.",
            "Di cómo se ordena un vídeo (por ejemplo: problema → criterio → "
            "consecuencia → solución → cierre).",
            "Di qué se evita: sensacionalismo, adjetivos vacíos, saludos, "
            "«dale like».",
        ],
        "no": [
            "Temas, datos, nombres o casos concretos: contaminan todos los vídeos "
            "que no van de eso. Eso va en el material de cada vídeo.",
            "El texto exacto de la llamada a la acción (web, WhatsApp, asesoría): "
            "va en «Las llamadas a la acción» de cada vídeo. En el tono basta "
            "con la regla («el cierre presenta la asesoría solo después de la "
            "solución»).",
            "Instrucciones de imagen o de voz: tienen su propio campo.",
        ],
        "plantilla": (
            "CÓMO SUENA: [tú/usted], [cercano/neutro/formal], [con/sin humor; "
            "qué tipo de humor].\n"
            "A QUIÉN LE HABLA: [público] que [qué sabe y qué no].\n"
            "NIVEL TÉCNICO: [cuánto vocabulario técnico y cómo se explica].\n"
            "RITMO: [frases cortas/largas; cuánto tarda en ir al grano].\n"
            "ESTRUCTURA: [paso 1] → [paso 2] → [paso 3] → [cierre].\n"
            "FORMA DE CONTAR: [diagnóstico, historia, comparación, lista...].\n"
            "CON LAS FUENTES: [qué se conserva, qué se tira, qué nunca se "
            "inventa].\n"
            "EVITAR: [lo que nunca debe hacer]."
        ),
        "ejemplo": (
            "CÓMO SUENA: de tú a tú, cercano y profesional, como en una consulta. "
            "Humor mínimo y seco, nunca contra el espectador.\n"
            "A QUIÉN LE HABLA: una persona común, con presupuesto medio, que "
            "tiene el problema ahora y no sabe de diseño.\n"
            "NIVEL TÉCNICO: usa el término del oficio cuando aporta precisión y "
            "lo explica en la misma frase con su efecto práctico.\n"
            "RITMO: frases cortas, de una idea; entra al problema en la primera "
            "frase.\n"
            "ESTRUCTURA: problema cotidiano → qué está mal de verdad → qué pasa "
            "si no se corrige → solución aplicable → cierre breve.\n"
            "FORMA DE CONTAR: diagnóstico, como en una consulta. Una sola "
            "enseñanza por vídeo.\n"
            "CON LAS FUENTES: conserva hechos, medidas y soluciones; nunca "
            "inventes medidas, precios, normas ni testimonios.\n"
            "EVITAR: sensacionalismo, adjetivos vacíos, saludos, «quédate hasta "
            "el final», vender antes de dar la solución."
        ),
        "prompt_ia": (
            "Voy a configurar el TONO DEL GUION de un canal en un sistema que "
            "redacta guiones de vídeo con IA. Lo que escriba se usará en TODOS "
            "los vídeos del canal, de cualquier tema.\n\n"
            "Con mis notas de abajo, escríbeme la descripción del tono con "
            "EXACTAMENTE estas etiquetas: CÓMO SUENA, A QUIÉN LE HABLA, NIVEL "
            "TÉCNICO, RITMO, ESTRUCTURA, FORMA DE CONTAR, CON LAS FUENTES, "
            "EVITAR. Entre 150 y 350 palabras.\n\n"
            "Reglas: no nombres ningún tema, caso, dato, producto ni lugar "
            "concreto (tiene que valer para cualquier vídeo). No escribas el "
            "texto de la llamada a la acción: solo, si hace falta, en qué "
            "momento va. Nada sobre imágenes ni sobre la voz.\n\n"
            "MIS NOTAS:\n[pega aquí cómo quieres que hable tu canal]"
        ),
    },

    # --------------------------------------------------------------------- voz
    "voz": {
        "titulo": "Voz de quien locuta",
        "donde": "Crear un estilo → La voz",
        "usa": "pasos/voz_descrita.py",
        "que_hace": [
            "Con tu descripción se elige una voz del catálogo en el idioma del "
            "estilo, su velocidad, su emoción y el silencio entre bloques.",
            "El RITMO del estilo también mueve la velocidad: «muy lento» frena la "
            "voz. Para Reels y Shorts suele ir mejor «medio» o «rápido».",
            "Si el idioma del estilo es «Español (Latinoamérica)», la voz ya se "
            "elige con acento latino: no hace falta repetirlo.",
        ],
        "si": [
            "Género, edad aproximada y acento (por ejemplo, latinoamericano "
            "neutro).",
            "Energía y actitud: cálida, segura, serena, enérgica.",
            "Velocidad si te importa: pausada, natural, ágil.",
            "Lo que no quieres: locución comercial, dramatismo, tono de anuncio.",
        ],
        "no": [
            "Textos largos: con 2 a 4 frases basta.",
            "Nombres de voces de otras plataformas: el catálogo es otro.",
        ],
        "plantilla": (
            "Voz [femenina/masculina], [edad aproximada], acento [acento]. "
            "Suena [tres o cuatro adjetivos]. Velocidad [pausada/natural/ágil]. "
            "No debe sonar [lo que no quieres]."
        ),
        "ejemplo": (
            "Voz femenina, de 28 a 40 años, acento latinoamericano neutro. Suena "
            "cálida, segura, natural y ligeramente conversacional. Velocidad "
            "natural, sin prisa. No debe sonar a locución comercial ni a anuncio."
        ),
        "prompt_ia": (
            "Necesito describir la VOZ del narrador para un sistema que elige "
            "una voz de un catálogo de voces sintéticas. Con mis notas, "
            "escríbeme de 2 a 4 frases que digan: género, edad aproximada, "
            "acento, cómo suena (3 o 4 adjetivos), velocidad y lo que NO debe "
            "sonar. Nada más.\n\nMIS NOTAS:\n[pega aquí cómo imaginas la voz]"
        ),
    },

    # ---------------------------------------------------------------- material
    "material": {
        "titulo": "El material del vídeo",
        "donde": "Un vídeo nuevo → El material",
        "usa": "pasos/p1_ingesta.py y pasos/p3_guion.py",
        "que_hace": [
            "Es la ÚNICA fuente de hechos del vídeo: el redactor no busca en "
            "internet ni abre enlaces. Lo que no está aquí no puede salir.",
            "Si marcas «Esto ya es el guion», se respeta palabra por palabra y "
            "solo se divide en bloques.",
            "En un vídeo corto (hasta 2 minutos) el redactor ELIGE: cuenta una sola "
            "idea con un caso concreto y deja fuera lo que no cabe. No intenta "
            "meterlo todo.",
        ],
        "si": [
            "Pega texto: notas, un artículo, datos, medidas, pasos, ejemplos.",
            "Hechos concretos: cifras, causas, errores frecuentes, soluciones.",
            "Si tienes varias fuentes, pégalas todas: el redactor las ordena.",
            "Para un vídeo corto, marca con «IMPRESCINDIBLE:» los dos o tres "
            "hechos que tienen que entrar sí o sí; el resto se usa solo si cabe.",
            "Si las indicaciones piden mostrar o comparar algo (meter una olla, "
            "medir un hueco), pon aquí los datos para hacerlo: medidas, tamaños, "
            "tiempos. Sin ellos el redactor no puede inventarlos y la "
            "demostración se queda en abstracto.",
        ],
        "no": [
            "Solo enlaces: no se abren.",
            "Instrucciones de cómo contarlo: van en «Las indicaciones».",
            "Un tema de tres minutos para un vídeo de treinta segundos: no cabe y "
            "sale un resumen. Recórtalo o marca lo imprescindible.",
        ],
        "plantilla": (
            "TEMA: [de qué va, en una frase].\n"
            "HECHOS Y DATOS:\n- [dato con su cifra o medida]\n- [dato]\n"
            "CAUSAS / POR QUÉ PASA:\n- [causa]\n"
            "ERRORES FRECUENTES:\n- [error]\n"
            "SOLUCIONES:\n- [paso o recomendación]\n"
            "LO QUE HAY QUE REVISAR ANTES DE DECIDIR:\n- [revisión]"
        ),
        "ejemplo": (
            "TEMA: por qué un baño puede verse bien y estar mal iluminado.\n"
            "HECHOS Y DATOS:\n- La luz general del techo sirve para moverse, no "
            "para el espejo: deja sombras bajo los ojos.\n- Para el espejo se usa "
            "luz frontal o lateral a la altura de la cara.\n"
            "ERRORES FRECUENTES:\n- Poner un solo foco en el centro del techo.\n"
            "SOLUCIONES:\n- Tres capas: general, de espejo y ambiental "
            "(indirecta, bajo el mueble o en un nicho)."
        ),
        "prompt_ia": (
            "Voy a hacer un vídeo con un sistema que SOLO usa como fuente de "
            "hechos el texto que le doy (no busca en internet). Con mis notas, "
            "ordena el material con estas etiquetas: TEMA, HECHOS Y DATOS, "
            "CAUSAS / POR QUÉ PASA, ERRORES FRECUENTES, SOLUCIONES, LO QUE HAY "
            "QUE REVISAR ANTES DE DECIDIR. Usa viñetas cortas. No inventes "
            "cifras, normas ni precios: si falta un dato, escribe «[confirmar]».\n\n"
            "MIS NOTAS:\n[pega aquí tus notas o el artículo]"
        ),
    },

    # ------------------------------------------------------------ indicaciones
    "indicaciones": {
        "titulo": "Las indicaciones del vídeo",
        "donde": "Un vídeo nuevo → Las indicaciones",
        "usa": "pasos/p3_guion.py",
        "que_hace": [
            "Le dicen al redactor cómo contar ESTE vídeo en concreto: el ángulo, "
            "la única enseñanza, por dónde empezar. Se suman al tono del estilo, "
            "que es el de siempre.",
            "Las etiquetas ENSEÑA, ÁNGULO, EMPIEZA POR y DEJA FUERA son órdenes: "
            "mandan sobre la forma general en que el redactor estructura un "
            "vídeo. ENSEÑA es la única idea; ÁNGULO se cuenta como una escena, "
            "paso a paso y en el centro del vídeo; EMPIEZA POR es la primera "
            "frase; DEJA FUERA no sale ni de pasada.",
        ],
        "si": [
            "Una frase o tres: qué enseñar, desde qué ángulo, qué dejar fuera.",
            "Si es un formato concreto, dilo: comparación A/B, antes y después, "
            "error y solución.",
            "Escribe el ÁNGULO como algo que se VE pasar: «meter la misma olla en "
            "los dos fregaderos y ver qué espacio queda», no «la diferencia de "
            "tamaño».",
        ],
        "no": [
            "Repetir el tono del estilo: ya lo tiene.",
            "Un ÁNGULO que es un tema general: el redactor lo nombrará y no lo "
            "contará.",
            "Hechos nuevos: van en el material.",
            "El texto de la llamada a la acción: va en su apartado.",
        ],
        "plantilla": (
            "ENSEÑA: [la única idea del vídeo].\n"
            "ÁNGULO: [la escena concreta que lo demuestra].\n"
            "EMPIEZA POR: [la situación o pregunta de arranque].\n"
            "DEJA FUERA: [lo que no debe entrar]."
        ),
        "ejemplo": (
            "ENSEÑA: que la iluminación del baño se piensa en tres capas.\n"
            "ÁNGULO: encender una a una las tres capas en el mismo baño y ver qué "
            "le pasa a la cara en el espejo.\n"
            "EMPIEZA POR: te miras al espejo y te salen sombras bajo los ojos.\n"
            "DEJA FUERA: marcas de lámparas y precios."
        ),
        "prompt_ia": (
            "Con estas notas, escríbeme las indicaciones de un vídeo corto en "
            "4 líneas con estas etiquetas: ENSEÑA (una sola idea), ÁNGULO (una "
            "escena concreta que se pueda ver, no un tema), "
            "EMPIEZA POR, DEJA FUERA. Máximo 70 palabras. No incluyas datos "
            "nuevos ni la llamada a la acción.\n\nMIS NOTAS:\n[pega aquí]"
        ),
    },

    # --------------------------------------------------------------------- cta
    "cta": {
        "titulo": "Las llamadas a la acción",
        "donde": "Un vídeo nuevo → Las llamadas a la acción",
        "usa": "pasos/cta.py",
        "que_hace": [
            "Tres momentos que se encienden por separado: la presentación (tras el "
            "gancho), una llamada a mitad y una al cierre.",
            "Lo que escribes es una INDICACIÓN de qué pedir; el redactor la dice "
            "con las palabras de ese vídeo, para que no suene a cuña repetida.",
        ],
        "si": [
            "Di qué quieres que haga quien mira y por qué le conviene: «que "
            "agende la asesoría online de entrada para revisar su caso».",
            "Una sola cosa por momento; el cierre puede pedir dos, cortas.",
        ],
        "no": [
            "Frases cerradas para leer tal cual: se oyen enlatadas.",
            "Enlaces o números largos: no se leen bien en voz alta; ponlos en la "
            "descripción del vídeo al publicarlo.",
        ],
        "plantilla": (
            "PRESENTACIÓN: [quién eres, en una frase] (opcional)\n"
            "A MITAD: [qué pedir y por qué] (opcional)\n"
            "AL CIERRE: [qué pedir como siguiente paso]"
        ),
        "ejemplo": (
            "AL CIERRE: que agende la asesoría online de entrada para revisar su "
            "baño con fotos o plano, como siguiente paso si no puede resolverlo "
            "solo."
        ),
        "prompt_ia": (
            "Escríbeme las llamadas a la acción de un vídeo como INDICACIONES "
            "(qué pedir y por qué), no como frases para leer. Formato: "
            "PRESENTACIÓN, A MITAD, AL CIERRE; una línea cada una y deja vacía "
            "la que no haga falta. Sin enlaces ni números.\n\nMIS NOTAS:\n"
            "[qué quieres que haga quien vea el vídeo]"
        ),
    },
    # ------------------------------------------------------------- publicar
    # Los textos con los que sale un vídeo en cada red (módulo Publicar). Los
    # escribe Claude con `publicar.instruccion_textos` y se corrigen a mano;
    # al enviar, `publicar.componer` los junta así: texto + capítulos (YouTube)
    # + llamada a la acción + firma del proyecto + hashtags del vídeo y del
    # proyecto. Lo que estas guías dicen sale de ahí: si cambia, se revisan.
    "texto_tiktok": {
        "titulo": "Texto para TikTok",
        "donde": "Publicar → ficha de un vídeo → TikTok",
        "usa": "pasos/publicar.py (REGLAS_RED, componer)",
        "que_hace": [
            "Es el pie del vídeo en TikTok: TikTok no tiene título aparte, así "
            "que este texto hace de título y de descripción a la vez.",
            "Al enviarlo, el Studio le añade debajo la llamada a la acción, la "
            "firma del proyecto y los hashtags (los del vídeo y los fijos del "
            "proyecto, sin repetir). Todo junto no puede pasar de 2.200 "
            "caracteres: lo que sobre se corta.",
            "TikTok busca por las palabras del texto y de la voz: lo que no se "
            "nombra, no se encuentra.",
            "Si el proyecto tiene puesto «Usar emojis en los textos» (Lo fijo del "
            "proyecto), Claude pone 1 a 3; si no, ninguno.",
        ],
        "si": [
            "Una primera línea que enganche: la promesa del vídeo o la pregunta "
            "que resuelve. Es lo que hace de título.",
            "Corto: 1 a 3 líneas. Frases cortas, con las palabras clave que se "
            "DICEN en el vídeo, tal cual («alquiler de consolas para fiestas en "
            "Lima»).",
            "Hashtags que mezclen uno o dos amplios del tema con otros de nicho o "
            "de la ciudad.",
            "Que cuente lo mismo que el vídeo: si el vídeo cambia, el texto también.",
        ],
        "no": [
            "Hashtags dentro del texto: van en su casilla (de 3 a 5 concretos; con "
            "los fijos del proyecto, el Studio usa como mucho 15).",
            "La llamada a la acción ni la firma: tienen su casilla y la firma la "
            "pone el proyecto.",
            "Teléfonos, precios o enlaces que no estén en el encargo: en TikTok "
            "los enlaces del pie no se pueden pulsar, mejor «link en bio».",
        ],
        "plantilla": (
            "[Gancho: la promesa o la pregunta, en una línea]\n"
            "[Una o dos frases con lo que se ve en el vídeo y sus palabras clave]"
        ),
        "ejemplo": (
            "¿Fiesta en casa y nadie quiere irse? 🎮\n"
            "Llevamos la consola, los mandos y los juegos para que la "
            "competencia dure toda la noche, en cualquier distrito de Lima."
        ),
        "prompt_ia": (
            "Escríbeme el pie de un vídeo de TikTok (no hay título aparte). "
            "Primera línea: un gancho con la promesa del vídeo. Después una o "
            "dos frases cortas con las palabras clave del tema dichas con "
            "naturalidad. SIN hashtags, SIN llamada a la acción y SIN firma "
            "(van aparte). No inventes teléfonos, precios ni enlaces. Máximo "
            "400 caracteres.\n\nDE QUÉ VA EL VÍDEO:\n[pega aquí el guion o "
            "un resumen]"
        ),
    },
    "texto_instagram": {
        "titulo": "Texto para Instagram Reels",
        "donde": "Publicar → ficha de un vídeo → Instagram Reels",
        "usa": "pasos/publicar.py (REGLAS_RED, componer)",
        "que_hace": [
            "Es el pie del Reel. Instagram no tiene título aparte: enseña solo la "
            "primera línea (unos 125 caracteres) hasta que se pulsa «más», así "
            "que esa línea hace de título.",
            "Con «Usar emojis en los textos» puesto en el proyecto, Claude usa "
            "3 a 6 (en el gancho, como viñetas y en la llamada a la acción).",
            "Al enviarlo, el Studio le añade la llamada a la acción, la firma del "
            "proyecto y los hashtags (como mucho 15, contando los fijos del "
            "proyecto). Todo junto no puede pasar de 2.200 caracteres.",
        ],
        "si": [
            "Una primera línea que se entienda sola y den ganas de abrir el resto.",
            "Párrafos cortos, separados por una línea en blanco.",
            "Algo que invite a guardar o compartir: una lista corta, un consejo.",
        ],
        "no": [
            "Hashtags dentro del texto: van en su casilla (de 5 a 8, mezclando "
            "amplios, de nicho y de la zona).",
            "La llamada a la acción ni la firma: tienen su casilla.",
            "Enlaces: en el pie no se pueden pulsar; la llamada a la acción puede "
            "decir «link en bio» o «escríbenos por DM».",
        ],
        "plantilla": (
            "[Primera línea: el gancho, que se entienda sola]\n\n"
            "[Párrafo corto con lo que aporta el vídeo]\n\n"
            "[Opcional: una lista corta o un consejo para guardar]"
        ),
        "ejemplo": (
            "Tu próxima reunión no necesita playlist: necesita un torneo. 🏆\n\n"
            "Te llevamos la consola, cuatro mandos y los juegos que más ríen. "
            "Lo instalamos y lo recogemos nosotros."
        ),
        "prompt_ia": (
            "Escríbeme el pie de un Reel de Instagram. Primera línea: un gancho "
            "que se entienda sola. Después uno o dos párrafos cortos separados "
            "por línea en blanco. SIN hashtags, SIN llamada a la acción y SIN "
            "firma (van aparte). Sin enlaces. Máximo 600 caracteres.\n\nDE "
            "QUÉ VA EL VÍDEO:\n[pega aquí el guion o un resumen]"
        ),
    },
    "texto_youtube": {
        "titulo": "Texto para YouTube",
        "donde": "Publicar → ficha de un vídeo → YouTube",
        "usa": "pasos/publicar.py (REGLAS_RED, componer)",
        "que_hace": [
            "Hay dos casillas: el TÍTULO y este TEXTO, que es la descripción. "
            "El título admite 100 caracteres, pero en el móvil se corta hacia el "
            "70: la palabra clave, al principio. Un vídeo vertical de hasta 3 "
            "minutos sale como Short; el resto, como vídeo normal.",
            "Al enviarlo, el Studio le añade a la descripción los capítulos (solo "
            "si sale como vídeo, no como Short, y los hay), la llamada a la "
            "acción, la firma y los "
            "hashtags. Los hashtags sirven también de etiquetas. YouTube no "
            "acepta «<» ni «>»: se quitan solos.",
            "Las dos primeras líneas son las que se ven en la búsqueda y debajo "
            "del vídeo sin desplegar.",
            "Las etiquetas de YouTube las pone el Studio: la palabra clave del vídeo, "
            "la del proyecto y las secundarias (SEO de este proyecto), y los hashtags.",
        ],
        "si": [
            "En las dos primeras líneas, la palabra clave y qué va a aprender o "
            "ver quien lo abra (es lo que sale en la búsqueda).",
            "Después el detalle, con las palabras que alguien buscaría.",
            "Aquí sí puedes poner un enlace si está en el encargo (web, "
            "WhatsApp): en YouTube se puede pulsar.",
        ],
        "no": [
            "El título dentro de la descripción: tiene su casilla.",
            "Los capítulos a mano: los pone el Studio con sus horas.",
            "Hashtags, llamada a la acción o firma dentro del texto: van aparte.",
            "Datos que no estén en el encargo ni en el guion.",
        ],
        "plantilla": (
            "[Línea 1-2: la promesa del vídeo, lo que se va a ver]\n\n"
            "[Detalle: 2-4 frases con las palabras que alguien buscaría]\n\n"
            "[Opcional: enlace del encargo]"
        ),
        "ejemplo": (
            "Cómo organizar un torneo de videojuegos en una fiesta sin que nadie "
            "se quede mirando.\n\n"
            "Te contamos cuántos mandos hacen falta, qué juegos funcionan con "
            "grupos grandes y cómo armar las rondas para que todos jueguen."
        ),
        "prompt_ia": (
            "Escríbeme la DESCRIPCIÓN de un vídeo de YouTube (el título va "
            "aparte). Las dos primeras líneas dicen qué va a ver o aprender quien "
            "lo abra. Después 2-4 frases con las palabras que alguien buscaría. "
            "SIN hashtags, SIN capítulos, SIN llamada a la acción y SIN firma "
            "(van aparte). Sin «<» ni «>». No inventes datos.\n\nDE QUÉ VA EL "
            "VÍDEO:\n[pega aquí el guion o un resumen]"
        ),
    },
    "texto_facebook": {
        "titulo": "Texto para Facebook",
        "donde": "Publicar → ficha de un vídeo → Facebook",
        "usa": "pasos/publicar.py (REGLAS_RED, componer)",
        "que_hace": [
            "Hay dos casillas: el TÍTULO (corto) y este TEXTO, que es la "
            "descripción. Un vídeo vertical de hasta 90 segundos sale como Reel; "
            "el resto, como vídeo.",
            "Al enviarlo, el Studio le añade la llamada a la acción, la firma y "
            "los hashtags.",
            "En Facebook mucha gente ve el vídeo sin sonido: el texto tiene que "
            "explicar de qué va sin oírlo.",
        ],
        "si": [
            "Un gancho al principio y una frase que cuente el vídeo sin sonido: "
            "di con palabras lo que pasa en él.",
            "Párrafos cortos y fáciles de leer.",
            "Un tono cercano, como hablando con un cliente.",
            "Si el encargo lo trae, cómo contactar (la llamada a la acción puede "
            "pedir que envíen un mensaje o llamen).",
        ],
        "no": [
            "Hashtags, llamada a la acción o firma dentro del texto: van aparte "
            "(2 a 4 hashtags bastan).",
            "Repetir el título en la primera línea.",
            "Datos que no estén en el encargo ni en el guion.",
        ],
        "plantilla": (
            "[Gancho en una línea]\n"
            "[Qué se ve en el vídeo, para quien lo ve sin sonido]"
        ),
        "ejemplo": (
            "La parte de la fiesta que todos recuerdan.\n"
            "Consola, pantalla y mandos listos en tu casa o en tu oficina: tú "
            "pones a la gente, nosotros el juego."
        ),
        "prompt_ia": (
            "Escríbeme la DESCRIPCIÓN de un vídeo de Facebook (el título va "
            "aparte). Un gancho al principio y una frase que explique el vídeo a "
            "quien lo ve sin sonido. Tono cercano. SIN hashtags, SIN llamada a la "
            "acción y SIN firma (van aparte). No inventes datos.\n\nDE QUÉ VA "
            "EL VÍDEO:\n[pega aquí el guion o un resumen]"
        ),
    },
    "tono_redes": {
        "titulo": "Tono de los textos para redes",
        "donde": "Publicar → Cuentas y ajustes → un proyecto → Lo fijo de este proyecto",
        "usa": "pasos/publicar.py (instruccion_textos)",
        "que_hace": [
            "Se le pasa a Claude cada vez que escribe los textos de un vídeo de "
            "este proyecto, en todas las redes. Sin él, usa el tono del guion.",
            "Vale para TODOS los vídeos del proyecto: tiene que servir para "
            "cualquier tema.",
            "La firma y los hashtags fijos tienen su casilla y los añade el "
            "Studio al final de cada texto: no hace falta pedirlos aquí.",
            "Los emojis se encienden o apagan con «Usar emojis en los textos», "
            "justo debajo; aquí puedes afinar cuáles y cuántos.",
        ],
        "si": [
            "Cómo suena la marca en redes: de tú o de usted, con o sin humor, "
            "con o sin emojis y cuántos.",
            "Palabras o expresiones de la marca que conviene usar.",
            "Lo que se evita (sonar a anuncio, mayúsculas, ciertas palabras).",
        ],
        "no": [
            "Temas, ofertas o precios concretos: cambian de un vídeo a otro y van "
            "en el encargo.",
            "La firma o los hashtags: tienen su casilla.",
            "Reglas de cada red (largo, número de hashtags): el Studio ya las "
            "aplica.",
        ],
        "plantilla": (
            "CÓMO SUENA: [tú/usted], [cercano/formal], [humor sí/no].\n"
            "EMOJIS: [ninguno / uno o dos / libres].\n"
            "PALABRAS DE LA MARCA: [las que conviene usar].\n"
            "EVITAR: [lo que nunca debe hacer]."
        ),
        "ejemplo": (
            "CÓMO SUENA: de tú, cercano y con humor ligero.\n"
            "EMOJIS: uno o dos, de juego o fiesta.\n"
            "PALABRAS DE LA MARCA: «la consola la llevamos nosotros», «tú pones "
            "a la gente».\n"
            "EVITAR: sonar a anuncio, mayúsculas, «¡no te lo pierdas!»."
        ),
        "prompt_ia": (
            "Voy a configurar el TONO de los textos con que mi marca publica "
            "vídeos en redes (TikTok, Instagram, YouTube, Facebook). Se usará en "
            "todos los vídeos, de cualquier tema. Con mis notas, escríbelo con "
            "estas etiquetas: CÓMO SUENA, EMOJIS, PALABRAS DE LA MARCA, EVITAR. "
            "Máximo 500 caracteres. Sin temas, ofertas ni precios concretos, y "
            "sin firma ni hashtags.\n\nMIS NOTAS:\n[cómo habla tu marca]"
        ),
    },
    # ------------------------------------------------------------- parrilla
    "guion_parrilla": {
        "titulo": "El formato del guion (Parrilla)",
        "donde": "Automatizar → Añadir guiones, y la ficha de un guion",
        "usa": "pasos/parrilla.py (leer_guion, encargo_de, el prompt de conversión), "
               "«Pasar al Encargo» en web/app.js y, para ESPACIO FIJO, "
               "pasos/catalogo_visual.py (proponer)",
        "que_hace": [
            "Todo guion de la Parrilla vive en ESTE formato, venga de un Word, un PDF, "
            "un Excel, de Claude o pegado. Lo que subes o pegas lo convierte Claude; "
            "si ya está en el formato, marca «Ya está en el formato» y se guarda tal cual.",
            "«Uso: exacto» respeta la locución palabra por palabra (solo ortografía): al "
            "pasarlo al Encargo se marca «Esto YA es el guion» y el redactor no la "
            "reescribe. «Uso: adaptar» toma el original como guía y la locución se "
            "escribe para la red; el redactor del Studio la vuelve a contar con el tono "
            "del estilo.",
            "«Pasar al Encargo» lee la sección PARA EL ENCARGO: el Material va al "
            "material, las Indicaciones a las indicaciones, la Llamada a la acción a "
            "«al final» (solo en «adaptar»: en «exacto» ya va dentro de la locución), "
            "y la Duración y el Formato a los suyos. Si falta algo, se avisa.",
            "Si PARA EL ENCARGO trae varios «- Material:», son varios vídeos (por "
            "ejemplo, uno vertical y uno horizontal): la ficha deja elegir cuál pasas.",
            "Cambiar Uso, Formato o Duración en la ficha cambia su línea en el texto "
            "(y en PARA EL ENCARGO si hay uno solo).",
            "ESPACIO FIJO (opcional) es para los vídeos que ocurren enteros en un "
            "mismo sitio: «- Sitio:» (un nombre corto), «- Descripción:» (cómo es, en "
            "una frase), «- Luz:» y «- Secundarios:» (otros sitios que sí pueden "
            "salir, «Nombre: descripción» separados por «;» o uno por línea). Viaja al "
            "Encargo y, con él, el reparto de sitios usa UN solo sitio con esa "
            "descripción tal cual, pone ahí todos los tramos (salvo los que el guion "
            "sitúe en un secundario) y no pone cabeceras de sitio. Sin descripción "
            "no cuenta. La imagen del sitio (opcional) se sube en «El espacio fijo» "
            "de «Un vídeo nuevo» después de «Pasar al Encargo».",
        ],
        "si": [
            "Una línea de cabecera por dato: «Uso:», «Formato:», «Duración:»…",
            "«Voz» solo con lo que se oye; «Visual» con una imagen fija concreta.",
            "La locución completa y seguida en «- Material:» de PARA EL ENCARGO.",
            "Las reglas fijas del cliente en MARCA DEL CLIENTE, no en cada escena.",
            "«Duración: la elijo en el Encargo» si el original no la dice.",
            "La descripción de ESPACIO FIJO como la quieres ver: va tal cual a todas "
            "las imágenes (mejor en inglés, que es lo que lee el generador).",
        ],
        "no": [
            "Diálogos entre personajes: el Studio narra con UNA voz (en «exacto» "
            "se marcan con ⚠ y se propone la versión en voz en off).",
            "Inventar teléfonos, precios o enlaces: si falta el CTA, «[FALTA CTA]».",
            "Configuración técnica (cámara, modelo, aspect ratio): se ignora.",
            "Cambiar los nombres de las etiquetas: el programa las busca tal cual.",
        ],
        "plantilla": (
            "G01 — [Título]\n"
            "Cliente / proyecto: [cliente]\n"
            "Uso: adaptar\n"
            "Red: [TikTok / Reels / Shorts / YouTube / Facebook, o sin definir]\n"
            "Formato: vertical\n"
            "Duración: la elijo en el Encargo\n"
            "Locución estimada: … palabras ≈ … s\n"
            "Objetivo: [qué tiene que conseguir]\n"
            "CTA: [qué se pide al final]\n"
            "Tono: [cómo suena]\n"
            "\n"
            "ESPACIO FIJO (opcional: bórralo si el vídeo cambia de sitio)\n"
            "- Sitio: [nombre corto]\n"
            "- Descripción: [cómo es el sitio, en una frase; va tal cual a todas las imágenes]\n"
            "- Luz: [hora del día y fuente de luz]\n"
            "- Secundarios: ninguno\n"
            "\n"
            "ESCENA 1\n"
            "Visual: [una imagen fija: quién, dónde, qué hace]\n"
            "Voz: «[lo que se oye]»\n"
            "Texto en pantalla: [si lo hay]\n"
            "\n"
            "ESCENA 2\n"
            "Visual: …\n"
            "Voz: «…»\n"
            "Texto en pantalla: …\n"
            "\n"
            "MARCA DEL CLIENTE\n"
            "- Mostrar: ninguna\n"
            "- Evitar: ninguna\n"
            "- Otras reglas: ninguna\n"
            "\n"
            "PARA EL ENCARGO\n"
            "- Material: [la locución completa seguida]\n"
            "- Indicaciones: [tono + objetivo + notas visuales clave]\n"
            "- Llamadas a la acción: [la del CTA]\n"
            "- Duración: elegir en el Encargo · Formato: vertical\n"
            "\n"
            "AVISOS\n"
            "- ninguno"
        ),
        "ejemplo": (
            "EP01 — Simple o doble: la bandeja manda\n"
            "Cliente / proyecto: Cocinas Lima\n"
            "Uso: adaptar\n"
            "Red: TikTok\n"
            "Formato: vertical\n"
            "Duración: 45 s\n"
            "Locución estimada: 105 palabras ≈ 42 s\n"
            "Objetivo: que pidan la medida de su fregadero\n"
            "CTA: Escríbenos por WhatsApp con la medida\n"
            "Tono: cercano, práctico\n"
            "\n"
            "ESCENA 1\n"
            "Visual: dos fregaderos de acero lado a lado en una encimera blanca\n"
            "Voz: «Por fuera miden casi lo mismo. Por dentro, la historia cambia.»\n"
            "Texto en pantalla: ¿Simple o doble?\n"
            "\n"
            "ESCENA 2\n"
            "Visual: unas manos meten una bandeja de horno grande en el fregadero simple\n"
            "Voz: «Coge la bandeja más grande que lavas y métela en el simple: entra tumbada.»\n"
            "\n"
            "MARCA DEL CLIENTE\n"
            "- Mostrar: acero inoxidable, cocinas reales\n"
            "- Evitar: marcas ajenas\n"
            "- Otras reglas: ninguna\n"
            "\n"
            "PARA EL ENCARGO\n"
            "- Material: Por fuera miden casi lo mismo. Por dentro, la historia cambia. Coge la bandeja más grande que lavas y métela en el simple: entra tumbada.\n"
            "- Indicaciones: cercano y práctico; una sola idea (la bandeja manda); mostrar la bandeja entrando en cada fregadero.\n"
            "- Llamadas a la acción: Escríbenos por WhatsApp con la medida\n"
            "- Duración: 45 s · Formato: vertical\n"
            "\n"
            "AVISOS\n"
            "- ninguno"
        ),
        # EL PROMPT DEL ANEXO del dueño, tal cual: es el mismo que usa
        # pasos/parrilla.py al convertir (lo comprueba pasos/prueba_parrilla.py).
        "prompt_ia": (
            "Convierte el guion que pego al final al formato del Studio.\n"
            "\n"
            "MODO: [exacto | adaptar]\n"
            "- exacto: la locución del original se respeta palabra por palabra. Solo corriges ortografía y puntuación. No inventas frases.\n"
            "- adaptar: el original es una guía de ideas. Escribe la locución final respetando el orden, el tono, el objetivo y el CTA, y ajustándola a la red.\n"
            "\n"
            "REGLAS GENERALES\n"
            "1. El Studio narra con UNA sola voz sobre imágenes fijas.\n"
            "   - Diálogos entre personajes → en \"exacto\", márcalos con ⚠ y propone debajo una versión en voz en off. En \"adaptar\", pásalos directamente a voz en off.\n"
            "   - Ignora la configuración técnica (modelo, cámara, aspect ratio, audio).\n"
            "2. \"Voz\" solo lleva lo que se oye, sin acotaciones ni emojis.\n"
            "3. \"Visual\" describe una imagen fija concreta: quién, dónde, qué hace, qué se ve. Si una escena tiene varios momentos, usa varias líneas Visual.\n"
            "4. Duración:\n"
            "   - Si el original la indica, úsala. En \"exacto\" avisa con ⚠ si la locución no cabe (sin recortar); en \"adaptar\", ajústala.\n"
            "   - Si no la indica, pon \"Duración: la elijo en el Encargo\".\n"
            "   - Siempre calcula la locución estimada (unas 2,5 palabras por segundo).\n"
            "5. Tiempos por escena solo si el original los trae; si no, numera las escenas.\n"
            "6. Las reglas fijas del cliente (qué mostrar, qué evitar, colores, frases de marca) van a MARCA DEL CLIENTE, no dentro de las escenas.\n"
            "7. No inventes datos: teléfonos, precios o enlaces solo si están en el original. Si falta el CTA, pon [FALTA CTA].\n"
            "8. ESPACIO FIJO solo si el original dice que todo el vídeo ocurre en un mismo sitio (un local, una cocina, un plató). Si no lo dice, no pongas esa sección.\n"
            "\n"
            "AJUSTE POR RED (en \"adaptar\" aplícalo; en \"exacto\" solo avisa con ⚠ si algo no encaja)\n"
            "- TikTok / Reels / Shorts: vertical. Gancho en los primeros 2–3 s. Un cambio de plano cada 1–3 s. Texto en pantalla frecuente y grande, que refuerce la voz. CTA corto (comenta, guárdalo, link en bio, escríbenos). En TikTok, las palabras clave del tema dichas en la voz.\n"
            "- YouTube largo: horizontal. En los primeros 15–30 s, la promesa de qué se va a ver. Ritmo más pausado, con bloques que puedan ser capítulos. Poco texto en pantalla, solo datos clave. CTA: suscribirse o enlace en la descripción.\n"
            "- Facebook: vertical u horizontal. Gancho temprano. Que se entienda sin sonido, con texto en pantalla. CTA: enviar mensaje o llamar.\n"
            "- Si no se indica red, no ajustes nada y pon \"Red: sin definir\".\n"
            "\n"
            "FORMATO DE SALIDA (exactamente así)\n"
            "\n"
            "ID — Título\n"
            "Cliente / proyecto: …\n"
            "Uso: exacto | adaptar\n"
            "Red: …\n"
            "Formato: vertical | horizontal\n"
            "Duración: … s | la elijo en el Encargo\n"
            "Locución estimada: … palabras ≈ … s\n"
            "Objetivo: …\n"
            "CTA: …\n"
            "Tono: …\n"
            "\n"
            "ESPACIO FIJO (solo si todo el vídeo ocurre en un mismo sitio; si no, quita esta sección)\n"
            "- Sitio: [nombre corto del sitio]\n"
            "- Descripción: [cómo es el sitio, en una frase; va tal cual a todas las imágenes]\n"
            "- Luz: [hora del día y fuente de luz]\n"
            "- Secundarios: [otros sitios que sí pueden salir, «Nombre: descripción» separados por «;», o ninguno]\n"
            "\n"
            "ESCENA 1 (tiempo, si lo hay)\n"
            "Visual: …\n"
            "Voz: «…»\n"
            "Texto en pantalla: …\n"
            "\n"
            "(…resto de escenas…)\n"
            "\n"
            "CIERRE DE MARCA: … (si lo hay)\n"
            "\n"
            "MARCA DEL CLIENTE (va una vez en su estilo, no en cada vídeo)\n"
            "- Mostrar: …\n"
            "- Evitar: …\n"
            "- Otras reglas: …\n"
            "(Si el guion no trae nada: \"ninguna\")\n"
            "\n"
            "VERSIONES POR RED (solo si hay más de una red)\n"
            "- Para cada red: qué cambia en el gancho, el texto en pantalla y el CTA.\n"
            "- Indica qué redes pueden compartir el mismo vídeo (mismo formato y duración) y cuáles necesitan su propio vídeo en el Studio.\n"
            "\n"
            "PARA EL ENCARGO (uno por cada vídeo distinto que haga falta)\n"
            "- Material: [locución completa seguida]\n"
            "- Indicaciones: [tono + objetivo + notas visuales clave, en 3–5 líneas]\n"
            "- Llamadas a la acción: …\n"
            "- Duración: … | elegir en el Encargo · Formato: vertical | horizontal\n"
            "\n"
            "AVISOS\n"
            "- [lista de ⚠, o \"ninguno\"]\n"
            "\n"
            "GUION ORIGINAL:\n"
            "<pega aquí>"
        ),
    },
    "pedir_guiones": {
        "titulo": "Pedir guiones a Claude (Parrilla)",
        "donde": "Automatizar → Añadir guiones → Pedir a Claude",
        "usa": "pasos/parrilla.py (instruccion_pedir)",
        "que_hace": [
            "Claude escribe guiones NUEVOS directamente en el formato del Studio, de "
            "cinco en cinco y sin repetir ideas dentro de la misma tanda.",
            "Usa solo lo que escribes aquí y los datos de la caja (red, formato, "
            "duración, notas): no busca en internet ni inventa teléfonos, precios o "
            "enlaces. Si falta el CTA, lo deja como [FALTA CTA].",
            "Cada guion queda «pendiente» en la Parrilla: revísalo en su ficha antes "
            "de pasarlo al Encargo.",
        ],
        "si": [
            "Di el cliente, el tema, a quién va y qué tiene que conseguir.",
            "Los datos que tienen que salir (servicios, zonas, oferta vigente).",
            "El CTA exacto (WhatsApp, enlace en bio, llamar).",
            "Ángulos o series que quieras («errores frecuentes», «antes y después»).",
        ],
        "no": [
            "Pedir 30 sin decir de qué: salen genéricos y parecidos.",
            "Precios o datos que no confirmas: los usará tal cual.",
        ],
        "plantilla": (
            "CLIENTE: [nombre y a qué se dedica].\n"
            "PÚBLICO: [a quién va].\n"
            "OBJETIVO: [qué tiene que conseguir cada vídeo].\n"
            "TEMAS O ÁNGULOS: [ideas o series].\n"
            "DATOS QUE PUEDEN SALIR: [servicios, zonas, oferta].\n"
            "CTA: [lo que se pide al final].\n"
            "EVITAR: [lo que no debe salir]."
        ),
        "ejemplo": (
            "CLIENTE: EstadoPlay, alquiler de consolas para fiestas en Lima.\n"
            "PÚBLICO: padres que organizan cumpleaños de niños de 6 a 12 años.\n"
            "OBJETIVO: que escriban por WhatsApp para reservar.\n"
            "TEMAS O ÁNGULOS: errores al organizar un cumpleaños; qué juegos funcionan "
            "con muchos niños; cómo se monta todo en una hora.\n"
            "DATOS QUE PUEDEN SALIR: llevamos y montamos la consola, el televisor y los "
            "mandos; también karaoke y simulador.\n"
            "CTA: escríbenos por WhatsApp.\n"
            "EVITAR: precios."
        ),
        "prompt_ia": (
            "Voy a pedir guiones de vídeo corto a un sistema que los escribe en un "
            "formato fijo. Con mis notas, escribe la petición con estas etiquetas: "
            "CLIENTE, PÚBLICO, OBJETIVO, TEMAS O ÁNGULOS, DATOS QUE PUEDEN SALIR, CTA, "
            "EVITAR. Sin inventar datos: si falta algo, escribe «[confirmar]».\n\n"
            "MIS NOTAS:\n[pega aquí tus notas]"
        ),
    },
    # El SEO de Publicar (rama `publicar-seo`, 18-10-2026). Lo usan
    # `pasos/publicar_seo.py` (bloque_instruccion, nota, campos_extra) y
    # `publicar.componer`: si cambia lo que hacen estos campos, se revisan.
    "palabra_clave": {
        "titulo": "Palabra clave (SEO)",
        "donde": "Publicar → Cuentas y ajustes → SEO de este proyecto, y la ficha de cada vídeo",
        "usa": "pasos/publicar_seo.py (bloque_instruccion, nota, etiquetas_youtube, nombre_fichero)",
        "que_hace": [
            "Es la frase por la que quieres que te ENCUENTREN. Claude la pone en la "
            "primera línea de cada red, al principio del título de YouTube y "
            "Facebook y otra vez en las dos primeras líneas de la descripción de "
            "YouTube.",
            "La del proyecto vale para todos sus vídeos; la de un vídeo (en su ficha) "
            "manda sobre ella. Al escribir los textos, Claude propone una más "
            "concreta para ese vídeo, y tú la aceptas o no.",
            "También va en las etiquetas de YouTube y en el nombre con el que se sube "
            "el MP4. La nota SEO de cada red mira si está donde tiene que estar.",
        ],
        "si": [
            "Una frase de 2 a 6 palabras, como la escribiría tu cliente en el "
            "buscador: «alquiler de consolas en Lima».",
            "Las secundarias, de 2 a 8: los servicios o los momentos concretos "
            "(«fiestas infantiles», «eventos corporativos»).",
            "La zona tal como la busca la gente: ciudad, país y distritos si importan.",
        ],
        "no": [
            "Una sola palabra suelta («consolas»): compite con todo el mundo.",
            "Frases que nadie escribe («soluciones lúdicas integrales»).",
            "Repetir la misma palabra clave en todos los vídeos si cada uno va de "
            "otra cosa: para eso está la de cada vídeo.",
        ],
        "plantilla": (
            "PRINCIPAL: [lo que haces] en [ciudad]\n"
            "SECUNDARIAS: [servicio 1], [servicio 2], [momento o público]\n"
            "ZONA: [ciudad, país (distritos)]"
        ),
        "ejemplo": (
            "PRINCIPAL: alquiler de consolas en Lima\n"
            "SECUNDARIAS: fiestas infantiles, eventos corporativos, simulador de "
            "carreras, karaoke para fiestas\n"
            "ZONA: Lima, Perú (Miraflores, Surco, San Borja)"
        ),
        "prompt_ia": (
            "Quiero las palabras clave SEO de mi negocio para vídeos en TikTok, "
            "Instagram, YouTube y Facebook. Dame: una PRINCIPAL (2 a 6 palabras, "
            "como la escribiría mi cliente en el buscador), de 3 a 8 SECUNDARIAS y la "
            "ZONA. Sin inventar servicios que no ofrezco.\n\nMI NEGOCIO:\n[qué "
            "haces, para quién y dónde]"
        ),
    },
    "ubicacion_instagram": {
        "titulo": "Ubicación de Instagram",
        "donde": "Publicar → Cuentas y ajustes → SEO de este proyecto → Instagram",
        "usa": "pasos/publicar_seo.py (campos_extra: location_id)",
        "que_hace": [
            "Instagram etiqueta el Reel con un lugar: sale en la búsqueda de ese sitio "
            "y ayuda a que lo vea gente de la zona.",
            "Upload-Post pide el NÚMERO del lugar (el id de un Lugar o de una Página "
            "de Facebook), no su nombre. El nombre de al lado es solo para leerlo "
            "aquí.",
        ],
        "si": [
            "Busca el lugar en Facebook (tu propia Página de empresa con dirección, "
            "o la ciudad). En su página, «Información» o la dirección de la web: el "
            "número largo es el id (facebook.com/…-106042326099451).",
            "Pega solo las cifras.",
        ],
        "no": [
            "El nombre del lugar o el enlace entero: solo el número.",
            "Una ubicación que no es donde trabajas.",
        ],
        "plantilla": "[solo cifras, de 5 a 25]",
        "ejemplo": "106042326099451",
        "prompt_ia": (
            "¿Cómo encuentro el id numérico de la Página de Facebook de mi empresa (o "
            "de mi ciudad) para usarlo como ubicación de Instagram en una API? "
            "Explícamelo paso a paso desde el navegador.\n\nMI PÁGINA O CIUDAD:\n[nombre]"
        ),
    },
    "categoria_youtube": {
        "titulo": "Categoría e idioma en YouTube",
        "donde": "Publicar → Cuentas y ajustes → SEO de este proyecto → YouTube",
        "usa": "pasos/publicar_seo.py (campos_extra: categoryId, defaultLanguage, defaultAudioLanguage)",
        "que_hace": [
            "La categoría le dice a YouTube con qué vídeos se parece el tuyo: ayuda a "
            "que lo recomiende al lado de los parecidos.",
            "El idioma del título y la descripción y el del audio le dicen a quién "
            "enseñarlo. «Español de Latinoamérica» es el de Perú.",
        ],
        "si": [
            "La categoría de lo que se VE en el vídeo: un alquiler para fiestas es "
            "«Entretenimiento» o «Viajes y eventos»; un tutorial, «Consejos y estilo» "
            "o «Educación»; partidas de videojuegos, «Videojuegos».",
            "El audio en «Español de Latinoamérica» si la voz es de aquí.",
        ],
        "no": [
            "Cambiar la categoría en cada vídeo sin motivo: el canal se lee mejor si es "
            "constante.",
        ],
        "plantilla": "CATEGORÍA: [la más parecida] · IDIOMA: es · AUDIO: es-419",
        "ejemplo": "CATEGORÍA: Entretenimiento · IDIOMA: es · AUDIO: es-419",
        "prompt_ia": (
            "¿Qué categoría de YouTube encaja mejor con un canal que publica estos "
            "vídeos? Dame una y por qué.\n\nMIS VÍDEOS:\n[de qué van]"
        ),
    },
    "hecho_para_ninos": {
        "titulo": "«Hecho para niños» en YouTube",
        "donde": "Publicar → Cuentas y ajustes → SEO de este proyecto → YouTube",
        "usa": "pasos/publicar_seo.py (campos_extra: selfDeclaredMadeForKids)",
        "que_hace": [
            "Es una declaración legal: el vídeo está pensado PARA que lo vean niños. "
            "YouTube le quita los comentarios, las notificaciones, la lista de "
            "reproducción final y casi toda la publicidad personalizada, y le baja "
            "mucho el alcance.",
            "Viene apagado de fábrica.",
        ],
        "si": [
            "Márcalo solo si quien va a VER el vídeo es un niño (dibujos, canciones "
            "infantiles, juegos para niños).",
        ],
        "no": [
            "Un vídeo para PADRES que contratan una fiesta infantil NO es para niños: "
            "va a adultos aunque salgan niños o se hable de cumpleaños.",
        ],
        "plantilla": "¿Lo ve un niño? sí → marcar · no (padres, empresas) → no marcar",
        "ejemplo": "Alquiler de consolas para cumpleaños, dirigido a padres → NO marcar",
        "prompt_ia": (
            "Según la normativa de YouTube (COPPA), ¿este vídeo es «hecho para "
            "niños»? Explícame por qué.\n\nEL VÍDEO:\n[de qué va y a quién se dirige]"
        ),
    },
    "marca_cliente": {
        "titulo": "La marca del cliente (Parrilla)",
        "donde": "Automatizar → Marca del cliente",
        "usa": "pasos/parrilla.py (marca_de, marca_texto: va en el contexto de convertir, "
               "pedir y «Desde mis resultados») y pasos/guionista.py (el chat)",
        "que_hace": [
            "Se apunta UNA vez por proyecto y Claude la recibe en todo lo que escribe o "
            "convierte para él: subir un documento, pegar, pedir guiones, «Desde mis "
            "resultados» y la conversación.",
            "Claude la copia en la sección MARCA DEL CLIENTE de cada guion y la respeta en "
            "las escenas (lo que se muestra y lo que se evita).",
            "El «CTA de siempre» se usa cuando el guion no trae uno: en vez de [FALTA CTA].",
            "No toca el estilo ni ningún vídeo: es solo para escribir guiones. Lo que va en la "
            "imagen se sigue decidiendo en el estilo.",
        ],
        "si": [
            "Quién es en una o dos frases: a qué se dedica, dónde, a quién vende.",
            "Mostrar y Evitar, concretos: «consolas y mandos reales», «nada de marcas ajenas».",
            "El tono en palabras sencillas: «de tú, cercano, con humor ligero».",
            "El CTA tal como se dice: «Escríbenos por WhatsApp para reservar».",
        ],
        "no": [
            "Precios u ofertas que caducan: ponlos en la petición de cada tanda.",
            "Instrucciones de imagen detalladas (luz, encuadre): son del estilo.",
            "Copiar aquí un guion entero: es lo de siempre de la marca, no un vídeo.",
        ],
        "plantilla": (
            "QUIÉN ES: [a qué se dedica, dónde, a quién vende].\n"
            "MOSTRAR: [productos, lugares, gente que debe salir].\n"
            "EVITAR: [lo que no debe salir nunca].\n"
            "TONO: [cómo habla la marca].\n"
            "CTA DE SIEMPRE: [lo que se pide al final].\n"
            "OTRAS REGLAS: [colores, frases de marca…]."
        ),
        "ejemplo": (
            "QUIÉN ES: EstadoPlay, alquiler de consolas para fiestas y eventos en Lima.\n"
            "MOSTRAR: consolas, mandos y pantallas reales; gente jugando en casa o en una oficina.\n"
            "EVITAR: marcas de videojuegos en primer plano; precios.\n"
            "TONO: de tú, cercano y con humor ligero.\n"
            "CTA DE SIEMPRE: Escríbenos por WhatsApp para reservar.\n"
            "OTRAS REGLAS: «la consola la llevamos nosotros» como frase de marca."
        ),
        "prompt_ia": (
            "Voy a apuntar la MARCA de un cliente para que una IA escriba sus guiones de vídeo. "
            "Con mis notas, escríbela con estas etiquetas: QUIÉN ES, MOSTRAR, EVITAR, TONO, "
            "CTA DE SIEMPRE, OTRAS REGLAS. Frases cortas. Sin precios ni ofertas que caduquen. "
            "No inventes nada: si falta algo, escribe «[confirmar]».\n\n"
            "MIS NOTAS:\n[pega aquí lo que sabes del cliente]"
        ),
    },
    "chat_guiones": {
        "titulo": "Conversar con Claude (Parrilla)",
        "donde": "Automatizar → Añadir guiones → Conversar con Claude",
        "usa": "pasos/guionista.py",
        "que_hace": [
            "Es un chat con Claude, como el de claude.ai: recuerda lo que habláis en esa "
            "conversación y conoce la marca del proyecto y el formato del guion del Studio.",
            "Cada guion completo que escribe sale con el botón «Guardar en la Parrilla» (queda "
            "pendiente, como los demás). Si le pides cambios, lo devuelve entero otra vez.",
            "📎 Capturas: lee imágenes. Para analizar una cuenta de Instagram o TikTok, haz "
            "capturas del perfil o de los reels con las vistas a la vista y pégalas.",
            "🌐 Buscar en internet (por mensaje, apagado de fábrica): busca y abre páginas. "
            "Instagram y TikTok no enseñan los reels sin iniciar sesión, así que ahí pedirá "
            "capturas. Lo que saque de fuera lleva su fuente y un aviso ⚠ para confirmarlo.",
            "📊 Con mis resultados: le pasa tus vídeos de este proyecto que mejor funcionaron, "
            "con las cifras guardadas en Publicar.",
            "Opus escribe como en claude.ai; Sonnet contesta antes. Usa tokens de la "
            "suscripción, sin coste en dólares.",
        ],
        "si": [
            "Empieza contándole el cliente, el objetivo y la red.",
            "Pídele primero ideas y luego el guion de la que te guste.",
            "Corrige como a una persona: «más corto», «el gancho más directo», «sin precios».",
            "Para copiar lo que funciona a otra cuenta: capturas con sus vistas + «¿qué les funciona?».",
        ],
        "no": [
            "Pedirle que entre en Instagram o TikTok: no puede sin iniciar sesión.",
            "Dar por buenos datos de internet sin mirarlos: confírmalos antes de grabar.",
            "Una matriz de 50 guiones por el chat: para eso, «Subir un documento».",
        ],
        "plantilla": (
            "CLIENTE: [quién es].\n"
            "QUIERO: [ideas / un guion / cambiar este guion].\n"
            "RED Y DURACIÓN: [TikTok 30 s, YouTube 3 min…].\n"
            "OBJETIVO: [qué tiene que conseguir].\n"
            "LO QUE SÉ: [datos, ofertas, lo que no se puede decir]."
        ),
        "ejemplo": (
            "CLIENTE: EstadoPlay, alquiler de consolas para fiestas en Lima.\n"
            "QUIERO: cinco ideas de reels para empresas (fiestas de fin de año), y luego el "
            "guion de la mejor.\n"
            "RED Y DURACIÓN: Instagram Reels, 30 s.\n"
            "OBJETIVO: que escriban por WhatsApp para reservar.\n"
            "LO QUE SÉ: llevamos y montamos todo; hay karaoke y simulador; sin precios."
        ),
        "prompt_ia": (
            "Ayúdame a escribir el primer mensaje para un chat con una IA que escribe guiones de "
            "vídeo. Con mis notas, escríbelo con estas etiquetas: CLIENTE, QUIERO, RED Y "
            "DURACIÓN, OBJETIVO, LO QUE SÉ. Frases cortas y sin inventar datos.\n\n"
            "MIS NOTAS:\n[lo que quieres pedir]"
        ),
    },
    "analizar_cuenta": {
        "titulo": "Analizar una cuenta (Parrilla)",
        "donde": "Automatizar → Analizar una cuenta",
        "usa": "pasos/cuentas_ajenas.py y motores/lectura_redes/lectores.py",
        "que_hace": [
            "Trae los vídeos públicos de una cuenta de TikTok, Instagram o YouTube que NO es tuya "
            "(competencia, un creador que te guste), con sus vistas, likes, comentarios, duración, "
            "fecha y texto.",
            "Primero por la vía gratis: YouTube con su API oficial e Instagram con la vía oficial de "
            "Meta (solo cuentas profesionales). Si no sirve —TikTok siempre, o una cuenta de Instagram "
            "personal— y lo tienes permitido, por Apify, que es de pago: unos céntimos por cuenta, con "
            "un tope al mes. Antes de pagar te dice cuánto costará.",
            "Una cuenta leída se guarda 24 h: volver a abrirla no paga otra vez.",
            "«Que Claude la analice» compara sus vídeos con más y con menos vistas y dice qué le "
            "funciona: temas, ganchos, duración, cuándo publica e ideas para ti.",
            "«Escribir guiones con lo que le funciona» los escribe para TU proyecto, con tu marca, "
            "inspirados y sin copiar sus frases ni sus datos. Van a la Parrilla, pendientes.",
            "«Hablar de ella en el chat» la pasa a «Conversar con Claude».",
        ],
        "si": [
            "Pega el enlace del PERFIL (no el de un vídeo) o escribe el @usuario y elige la red.",
            "Empieza con 30 vídeos: da para ver qué funciona y cuesta poco.",
            "Analiza antes de pedir guiones: los guiones usan el análisis.",
            "Pide en «algo más» lo que necesites: «para Navidad», «sin precios».",
        ],
        "no": [
            "Cuentas privadas: no se pueden leer por ninguna vía.",
            "Copiar sus frases o su marca: los guiones se inspiran en la fórmula.",
            "«Volver a traer» la misma cuenta cada rato: con Apify, cada lectura se paga.",
        ],
        "plantilla": (
            "RED: [TikTok / Instagram / YouTube].\n"
            "CUENTA: [@usuario o enlace del perfil].\n"
            "QUÉ QUIERO SACAR: [ideas de temas / ganchos / formato].\n"
            "PARA: [mi proyecto y mi objetivo]."
        ),
        "ejemplo": (
            "RED: TikTok.\n"
            "CUENTA: https://www.tiktok.com/@unafiestaenlima\n"
            "QUÉ QUIERO SACAR: qué ganchos usan sus vídeos más vistos.\n"
            "PARA: EstadoPlay, reels de cumpleaños infantiles."
        ),
        "prompt_ia": (
            "Voy a analizar la cuenta de redes de un competidor para aprender qué le funciona. "
            "Con mis notas, dime en una lista corta qué debería fijarme (temas, ganchos, duración, "
            "horarios) y qué NO debería copiar.\n\nMIS NOTAS:\n[la cuenta y lo que quieres sacar]"
        ),
    },
    "conexiones_cuentas": {
        "titulo": "Conexiones para analizar cuentas",
        "donde": "Automatizar → Analizar una cuenta → Conexiones",
        "usa": "pasos/cuentas_ajenas.py (las claves van en <secretos>/lectura_redes.json)",
        "que_hace": [
            "YOUTUBE (gratis): una clave de API de Google. En console.cloud.google.com crea un "
            "proyecto, entra en «APIs y servicios → Biblioteca», activa «YouTube Data API v3» y en "
            "«Credenciales» crea una «Clave de API». Da 10.000 unidades al día gratis; leer una cuenta "
            "usa 3.",
            "INSTAGRAM (gratis): se usa UNA cuenta tuya de Instagram como «ventana» para mirar las "
            "demás. Puede ser la de tu negocio o una creada solo para el Studio: lo único que pide "
            "Meta es que sea PROFESIONAL (Empresa o Creador) y esté vinculada a una Página de "
            "Facebook que administres. Mirar otras cuentas no publica ni cambia nada en la tuya. En developers.facebook.com crea una "
            "app de tipo «Empresa», añade el producto de Instagram, y en el «Explorador de la API "
            "Graph» genera un token con instagram_basic, pages_show_list, pages_read_engagement e "
            "instagram_manage_insights. Pásalo por el «Depurador de tokens» → «Ampliar» para que dure "
            "~60 días, pégalo aquí y pulsa «Buscar mi cuenta». El Studio avisa cuando va a caducar.",
            "APIFY (de pago, de respaldo): crea una cuenta en apify.com (el plan gratis trae 5 $ al "
            "mes) y copia tu token de «Settings → API & Integrations». Se usa para TikTok y para las "
            "cuentas de Instagram que no son profesionales.",
            "El TOPE AL MES para Apify viene en 5 $ (lo del plan gratis). Al llegar, no se lee nada "
            "más de pago hasta el mes siguiente o hasta que lo subas.",
            "Las claves se guardan en el servidor y nunca bajan a la pantalla: solo sus 4 últimos "
            "caracteres. Nunca las pegues en un chat.",
        ],
        "si": [
            "Empieza por YouTube: es lo más rápido y es gratis.",
            "Para CAMBIAR de cuenta de Instagram (por ejemplo, a una nueva solo para el Studio): "
            "hazla profesional, vincúlala a una Página de Facebook, saca su token, pégalo en "
            "«Cambiar» y pulsa «Volver a buscar». Las cuentas ya analizadas se quedan.",
            "Usa una app de Meta solo para esto, a tu nombre: no hace falta pasar la revisión de Meta "
            "si solo la usa tu negocio.",
            "Renueva el token de Meta cuando el Studio lo avise.",
        ],
        "no": [
            "Iniciar sesión con cuentas falsas para mirar perfiles: lo prohíben Instagram y TikTok y "
            "acaba en bloqueos.",
            "Compartir el token de Apify: con él se gasta tu crédito.",
        ],
        "plantilla": (
            "YOUTUBE: [clave de API de Google].\n"
            "INSTAGRAM: [token largo de Meta] → «Buscar mi cuenta».\n"
            "APIFY: [token] · tope al mes: [5] $."
        ),
        "ejemplo": (
            "YOUTUBE: AIza… (puesta).\n"
            "INSTAGRAM: EAAB… → tu cuenta: @micuenta_studio.\n"
            "APIFY: apify_api_… · tope al mes: 5 $."
        ),
        "prompt_ia": (
            "Guíame paso a paso, con capturas si puedes, para [crear una clave de API de YouTube Data "
            "API v3 / crear una app de Meta y un token largo con instagram_basic y pages_show_list / "
            "sacar mi token de Apify]. Estoy en [ordenador / móvil]."
        ),
    },
}

# Las redes que se añadieron en publicar-mas (18-10-2026). Mismo formato que
# las de arriba, escrito corto: lo que Claude sigue al escribirlas está en
# `pasos/publicar_redes.py` (REGLAS, LIMITES, TITULOS, ALT). Si cambia ahí, se
# revisa aquí.
_REDES_NUEVAS = {
    "linkedin": ("LinkedIn", 3000,
                 ["Tiene TÍTULO aparte (hasta 400 caracteres; mejor corto, que diga el "
                  "beneficio) y un texto de hasta 3.000. La primera línea se corta a los "
                  "~210 caracteres con «ver más»."],
                 ["Una primera línea que enganche al público profesional.",
                  "3 a 6 párrafos cortos: contexto y una idea útil.",
                  "3 a 5 hashtags."],
                 ["Tono de anuncio o de TikTok: aquí lee gente de negocio."],
                 "[Primera línea: la idea o el resultado]\n\n[Contexto en dos frases]\n\n[La idea útil]",
                 "Una fiesta infantil sin pantallas aburridas sí existe.\n\nEn EstadoPlay llevamos "
                 "consolas a cumpleaños en Lima y vemos lo mismo cada fin de semana: los niños "
                 "juegan juntos, no cada uno con su móvil."),
    "x": ("X (Twitter)", 280,
          ["Todo junto (texto, llamada a la acción y hashtags) cabe en 280 caracteres: "
           "lo que sobre se corta.", "X QUITA LOS ENLACES del texto al publicar."],
          ["Una frase directa, una sola idea.", "1 o 2 hashtags."],
          ["Enlaces: no saldrán.", "Listas de hashtags."],
          "[Una frase con la idea del vídeo]",
          "Consolas, mandos y juegos para tu fiesta en Lima: tú pones a los invitados. 🎮"),
    "threads": ("Threads", 500,
                ["Hasta 500 BYTES en total: con tildes y emojis caben menos letras."],
                ["Tono de conversación.", "Una pregunta que invite a contestar."],
                ["Más de un hashtag."],
                "[Una frase de charla]\n[Una pregunta]",
                "Este finde llevamos la consola a un cumpleaños de 15 niños y nadie lloró. "
                "¿Cuál fue el juego de tu infancia?"),
    "pinterest": ("Pinterest", 800,
                  ["Pinterest es un BUSCADOR: título de hasta 100 caracteres y descripción "
                   "de hasta 800.", "Sin tablero (Cuentas y ajustes → Redes de este "
                   "proyecto) no se puede publicar."],
                  ["La palabra clave al principio del título.",
                   "Qué es y para quién, con palabras que alguien buscaría. 2 a 5 hashtags."],
                  ["Frases de relleno sin palabras que se busquen."],
                  "[Qué es] para [quién] en [zona]: [lo que lo hace distinto]",
                  "Alquiler de consolas para fiestas infantiles en Lima: llevamos todo y lo "
                  "montamos en tu casa."),
    "bluesky": ("Bluesky", 300,
                ["Hasta 300 caracteres en total, con la llamada a la acción y los hashtags.",
                 "Vídeos de hasta 10 minutos."],
                ["Tono natural.", "1 a 3 hashtags."],
                ["Aire de anuncio."],
                "[Una o dos frases naturales]",
                "Llevamos una consola a un cumpleaños y acabaron jugando también los padres."),
    "discord": ("Discord", 2000,
                ["Un mensaje en un canal de tu comunidad, hasta 2.000 caracteres.",
                 "El tamaño máximo del vídeo lo pone el servidor."],
                ["Directo y cercano: te leen quienes ya te conocen."],
                ["Hashtags: en Discord no sirven."],
                "[Lo nuevo, en una frase]\n[Un detalle]",
                "¡Vídeo nuevo! Así montamos la consola en un cumpleaños de este sábado."),
    "telegram": ("Telegram", 1024,
                 ["El pie del vídeo en el canal, hasta 1.024 caracteres."],
                 ["Primera línea clara, párrafos cortos, la llamada a la acción al final."],
                 ["Muchos hashtags."],
                 "[Primera línea]\n\n[Un párrafo corto]",
                 "Nuevo vídeo: un cumpleaños con consola en Lima.\n\nMira cómo lo montamos en "
                 "menos de 20 minutos."),
    "mastodon": ("Mastodon", 500,
                 ["Hasta 500 caracteres. En Mastodon se busca por hashtags."],
                 ["Tono natural, sin exagerar.", "2 a 4 hashtags."],
                 ["Exageraciones de anuncio."],
                 "[Una o dos frases]",
                 "Así se ve un cumpleaños infantil con consola: menos móviles y más juego juntos."),
    "google_business": ("Google Business", 1500,
                        ["Una publicación del perfil de empresa: sale en Google Maps y en la "
                         "búsqueda local.", "Solo vídeos de hasta 30 segundos. El botón "
                         "(Reservar, Llamar…) se elige en Cuentas y ajustes."],
                        ["1 a 3 frases con lo que ofreces y la ZONA."],
                        ["Hashtags y emojis de más.", "La llamada a la acción: la pone el botón."],
                        "[Qué ofreces] en [zona]. [Un detalle que dé confianza].",
                        "Alquiler de consolas para fiestas en Lima. Llevamos todo y lo dejamos "
                        "funcionando en tu casa."),
}
for _red, (_nombre, _tope, _hace, _si, _no, _plantilla, _ejemplo) in _REDES_NUEVAS.items():
    GUIAS[f"texto_{_red}"] = {
        "titulo": f"Texto para {_nombre}",
        "donde": f"Publicar → ficha de un vídeo → {_nombre}",
        "usa": "pasos/publicar_redes.py (REGLAS, LIMITES, campos) y pasos/publicar.py (componer)",
        "que_hace": _hace + [
            "Al enviarlo, el Studio le añade la llamada a la acción, la firma del proyecto "
            f"y los hashtags. Todo junto no pasa de {format(_tope, ',').replace(',', '.')} "
            "caracteres.",
        ],
        "si": _si,
        "no": _no + ["Teléfonos, precios o enlaces que no estén en el encargo."],
        "plantilla": _plantilla,
        "ejemplo": _ejemplo,
        "prompt_ia": (f"Escríbeme el texto de un vídeo para {_nombre}. "
                      + " ".join(_hace + _si) + " SIN llamada a la acción ni firma (van "
                      "aparte). No inventes teléfonos, precios ni enlaces.\n\nDE QUÉ VA EL "
                      "VÍDEO:\n[pega aquí el guion o un resumen]"),
    }

ORDEN = ("estilo_grafico", "tono", "voz", "material", "indicaciones", "cta",
         "texto_tiktok", "texto_instagram", "texto_youtube", "texto_facebook",
         "tono_redes", "guion_parrilla", "pedir_guiones", "marca_cliente",
         "chat_guiones", "analizar_cuenta", "conexiones_cuentas",
         "palabra_clave", "ubicacion_instagram", "categoria_youtube", "hecho_para_ninos",
         "texto_linkedin", "texto_x", "texto_threads", "texto_pinterest", "texto_bluesky",
         "texto_discord", "texto_telegram", "texto_mastodon", "texto_google_business")



def listar():
    """[{id, ...guia}] en el orden en que salen en la pantalla."""
    return [dict(GUIAS[g], id=g) for g in ORDEN]


def como_texto(gid):
    """Una guia entera como texto plano, para copiarla o leerla el asistente."""
    g = GUIAS[gid]
    lineas = [g["titulo"].upper(), f"Dónde: {g['donde']}", "", "QUÉ HACE EL SISTEMA CON ESTO:"]
    lineas += [f"- {x}" for x in g["que_hace"]]
    lineas += ["", "SÍ:"] + [f"- {x}" for x in g["si"]]
    lineas += ["", "NO:"] + [f"- {x}" for x in g["no"]]
    lineas += ["", "PLANTILLA:", g["plantilla"], "", "EJEMPLO:", g["ejemplo"]]
    return "\n".join(lineas)

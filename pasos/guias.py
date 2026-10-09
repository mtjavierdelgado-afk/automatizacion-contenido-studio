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
        "usa": "pasos/estilo.py (generar_guia) y pasos/moodboard.py",
        "que_hace": [
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
        ],
        "si": [
            "Pega texto: notas, un artículo, datos, medidas, pasos, ejemplos.",
            "Más hechos concretos dan mejor guion: cifras, causas, errores "
            "frecuentes, soluciones.",
            "Si tienes varias fuentes, pégalas todas: el redactor las ordena.",
        ],
        "no": [
            "Solo enlaces: no se abren.",
            "Instrucciones de cómo contarlo: van en «Las indicaciones».",
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
        ],
        "si": [
            "Una frase o tres: qué enseñar, desde qué ángulo, qué dejar fuera.",
            "Si es un formato concreto, dilo: comparación A/B, antes y después, "
            "error y solución.",
        ],
        "no": [
            "Repetir el tono del estilo: ya lo tiene.",
            "Hechos nuevos: van en el material.",
            "El texto de la llamada a la acción: va en su apartado.",
        ],
        "plantilla": (
            "ENSEÑA: [la única idea del vídeo].\n"
            "ÁNGULO: [desde dónde contarlo].\n"
            "EMPIEZA POR: [la situación o pregunta de arranque].\n"
            "DEJA FUERA: [lo que no debe entrar]."
        ),
        "ejemplo": (
            "ENSEÑA: que la iluminación del baño se piensa en tres capas.\n"
            "ÁNGULO: el error de poner un solo foco en el techo.\n"
            "EMPIEZA POR: te miras al espejo y te salen sombras bajo los ojos.\n"
            "DEJA FUERA: marcas de lámparas y precios."
        ),
        "prompt_ia": (
            "Con estas notas, escríbeme las indicaciones de un vídeo corto en "
            "4 líneas con estas etiquetas: ENSEÑA (una sola idea), ÁNGULO, "
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
}

ORDEN = ("estilo_grafico", "tono", "voz", "material", "indicaciones", "cta")


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

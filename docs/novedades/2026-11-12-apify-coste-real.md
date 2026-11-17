**El gasto de Apify es lo que cobra de verdad (12 de noviembre)**
- **Al leer una cuenta con Apify** (TikTok, o Instagram cuando la vía gratis no
  sirve), el gasto del mes apunta lo que Apify dice que ha cobrado en esa
  lectura, no un cálculo aproximado. Antes se apuntaba una estimación que solía
  quedar por encima de lo real.
- Si Apify no da la cifra, o da una que no cuadra (0 con vídeos traídos), se
  sigue usando la estimación de siempre.
- Si una lectura tarda más de lo permitido, el Studio la **detiene** para que no
  siga cobrando, y apunta lo reservado (nunca 0), porque la cifra de una lectura
  a medias todavía puede crecer.
- El tope de gasto al mes funciona igual que antes.
- **En los lectores que cobran por evento** (el de TikTok cobra 0,001 $ por
  arrancar y unos 0,0037 $ por cada resultado), el gasto se calcula sumando lo
  que cuesta cada evento, y se apunta lo mayor entre esa suma y la cifra de
  Apify. Pasó de verdad el 17-11: Apify cobró 0,0047 $ y el Studio apuntó
  0,001 $ porque leyó la cifra justo al terminar, antes de que Apify contara el
  resultado.
- **Si la cuenta no tiene ningún vídeo**, el aviso lo dice así: «la cuenta
  «ikeausa» de TikTok no tiene vídeos públicos (Apify la ve con 0 vídeos, 0
  seguidores), o TikTok no ha dejado verla: ¿es la cuenta que buscas?». Lo de
  «o TikTok no ha dejado verla» solo sale cuando la cuenta tiene 0 seguidores,
  porque entonces no se puede saber cuál de las dos cosas pasa. Pasó con
  @ikeausa, que no es la cuenta de IKEA sino un perfil personal vacío.
- Cada lectura nunca apunta más de lo que se le dejó cobrar a Apify en ella.
- **Si TikTok no deja leer una cuenta que sí tiene vídeos**, o el lector no trae
  los datos de la cuenta, el aviso dice: «TikTok no le ha dejado ver los vídeos
  al lector de Apify (le pide iniciar sesión)».

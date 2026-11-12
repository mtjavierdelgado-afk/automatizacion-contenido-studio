# Novedades de cada rama

Aquí escribe cada rama lo que cambia para quien usa el Studio, **en su propio
fichero**, en vez de arriba de `docs/NOVEDADES.md`. Así dos ramas abiertas a la
vez nunca escriben en las mismas líneas y no chocan al unirse.

- **Nombre:** `AAAA-MM-DD-<rama>.md`, con la fecha del día en que la rama
  apunta su primera entrada. Ejemplo: `2026-11-05-ramas-sin-choques.md`.
  Si la rama hace varias cosas, todas van en su fichero.
- **Formato:** el de siempre de `NOVEDADES.md`: un título en negrita con la
  fecha entre paréntesis y sus viñetas. Sin el título de versión: va solo
  debajo del primero que haya (hoy `## V5.1`).
- **Versión nueva:** si el fichero empieza por `## V… · …`, abre esa versión
  encima de las demás.
- **Dónde se ve:** Configuración → Novedades y el asistente lo leen ya junto
  (`pasos/novedades.py`), de lo más nuevo a lo más antiguo, encima de lo de
  `NOVEDADES.md`. Igual que si estuviera escrito ahí.
- **Plegar (solo en `main`, opcional):** `python herramientas/plegar_novedades.py`
  pasa estas entradas a `NOVEDADES.md` y borra sus ficheros, sin cambiar lo que
  se ve. Nunca en una rama: volvería a chocar.

Este fichero (`LEEME.md`) no sale en las novedades: solo cuentan los que
empiezan por una fecha.

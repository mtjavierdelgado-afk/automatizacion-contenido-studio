# Escenarios del recorrido de cada rama

Un escenario NUEVO del recorrido (`prueba_recorrido.py`) va aquí, en un fichero
propio de su rama, en vez de al final de `prueba_recorrido.py`. Así dos ramas
abiertas a la vez no escriben en las mismas líneas y no chocan al unirse.

- **Nombre:** `<rama>.py` con guiones bajos (`graficas_1.py`). Los que empiezan
  por `_` no se cargan (sirven para piezas compartidas o para dejar uno apagado).
- **Se cargan solos**, detrás de los escenarios de `prueba_recorrido.py`, en
  orden de nombre. `python prueba_recorrido.py --solo <nombre>` también los
  encuentra.
- **Cabecera** (copiar tal cual y añadir lo que se use):

  ```python
  """Recorrido de la rama <rama>: qué se comprueba."""
  from prueba_recorrido import Pagina, escenario, ok  # noqa: F401
  # y lo que haga falta: from prueba_recorrido import _paso_ficha, _panel_casa


  @escenario
  def mi_escenario(navegador, datos):
      pg = Pagina(navegador, datos)
      try:
          ok(pg.esperar("#cuerpo"), "la pantalla abre")
      finally:
          pg.cerrar()
  ```

  `from prueba_recorrido import …` da las MISMAS funciones del recorrido que se
  está corriendo (el cargador lo registra antes), no una copia.
- **Los escenarios que ya estaban** en `prueba_recorrido.py` se quedan ahí: se
  pueden seguir arreglando en su sitio. Lo nuevo, aquí.
- **Un fichero que no carga** (un error de sintaxis, un import que falta) sale
  como FALLO del recorrido, no se calla.

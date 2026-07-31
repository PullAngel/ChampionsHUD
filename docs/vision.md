# Visión del producto

## Declaración de visión

Champions HUD es el jugador top que mira tu partida por encima del hombro. No juega. No interrumpe. Recuerda todo lo que pasó, sabe todo lo que se puede saber del meta, calcula lo que vos no tenés tiempo de calcular bajo presión, y te lo muestra en el momento exacto en que lo necesitás.

## El problema real

En Pokémon Champions —y en VGC en general— una fracción enorme de las partidas se pierde no por mala estrategia sino por **límites humanos bajo presión de reloj**: no llegás a calcular si tu ataque mata, no te acordás cuántos turnos le quedan a Tailwind, no procesás a tiempo que el rival ya descartó la mitad de sus sets posibles con la información que ya soltó. Ese es el problema que resuelve Champions HUD: no reemplaza el criterio del jugador, reemplaza el trabajo mecánico que le impide usar su criterio a tiempo.

## Qué NO es Champions HUD

- **No es una Pokédex.** No compite en ser una referencia enciclopédica del juego.
- **No es un Damage Calculator standalone.** El cálculo de daño es un componente interno, no el producto.
- **No es un Team Builder.** No arma equipos; ayuda a jugar los que ya existen.
- **No es un motor de recomendación de jugadas.** Esto es lo suficientemente importante como para tener su propia sección.

## El copiloto nunca recomienda una jugada

Esta es la regla más importante del producto y **reemplaza cualquier diseño anterior que rankeara o sugiriera movimientos** (por ejemplo, un modo "compacto" que ordenara los cuatro movimientos propios por conveniencia). Esa clase de feature queda descartada, no pospuesta: contradice la razón de ser del producto.

El objetivo del copiloto **no es decirte qué hacer**. Es:

- Mostrar información difícil de calcular bajo presión (daño, velocidad, orden de turno) con la misma exactitud que una calculadora de daño, en el momento en que hace falta.
- Mantener memoria del combate completo, algo que ningún jugador humano puede hacer con precisión partido a partido.
- Eliminar hipótesis incompatibles con la evidencia observada (sets, ítems, habilidades, movimientos restantes del rival).
- Actualizar automáticamente ese estado de conocimiento a medida que aparece nueva evidencia.

**Regla operativa:** si algo se puede resolver con una calculadora de daño y datos conocidos, la app lo hace. Si algo requiere decidir *qué hacer con esa información*, esa decisión es siempre y exclusivamente del jugador. El copiloto puede mostrar la consecuencia de una acción hipotética si el jugador la pide explícitamente ("¿qué pasa si uso X?"), pero nunca la ordena, nunca la resalta como "la mejor", nunca la elige por vos.

Esta regla no es solo filosófica: es la que sostiene la confianza del usuario. Un copiloto que sugiere y se equivoca pierde al usuario en la primera partida. Un copiloto que informa con precisión y deja decidir, no.

## Filosofía central

El copiloto debe:

- **Observar** — capturar lo que ocurre en pantalla, con la menor fricción posible.
- **Recordar** — mantener un registro fiel de todo lo sucedido en el combate.
- **Inferir** — descartar lo que la evidencia hace imposible, no adivinar con falsa precisión.
- **Explicar** — cada dato mostrado tiene que poder justificarse en una línea.
- **Nunca decidir** — la última milla, la decisión de juego, es siempre humana.

No se trata de mostrar datos. Se trata de sostener, turno a turno, un modelo del combate más completo y más rápido que el que un humano puede sostener solo — y compartir ese modelo con transparencia sobre lo que es certeza y lo que es estimación.

## Principios de diseño

1. **El juego es la pantalla principal.** El HUD es un satélite: chico, movible, minimizable. Si el jugador está mirando el overlay en lugar del juego durante la resolución de un turno, el diseño falló.
2. **Un tap o nada.** Toda entrada manual en el flujo de combate se resuelve con un toque sobre opciones predichas. Si una corrección requiere teclear, es un defecto de diseño.
3. **Confianza calibrada, nunca falsa precisión.** Cada dato se muestra como hecho confirmado, deducción con evidencia, o estimación de meta — nunca disfrazado de certeza. Ver `product.md` para el sistema de confianza.
4. **No duplicar lo que el juego ya muestra.** Pokémon Champions ya informa correctamente contadores como Tailwind, clima, pantallas y otros efectos de campo. El HUD no repite esa información salvo que agregue un valor que el juego no da (por ejemplo, cruzar esa duración con una estimación oculta, o alertar sobre una interacción no obvia). Mostrar de nuevo lo que el jugador ya tiene en pantalla es ruido, no ayuda.
5. **Silencio por defecto.** El copiloto habla cuando algo relevante cambió. La ausencia de alertas también es información.
6. **Degradación elegante.** Sin conexión, sin datos de meta actualizados, con un reconocimiento parcial: el producto sigue siendo útil. La automatización es una capa opcional sobre una base que funciona sin ella.
7. **Explicable en un tap.** Toda estimación puede expandirse a su razón. La explicación es lo que además enseña al jugador a leer la partida sin la app.
8. **Fallo ruidoso, nunca silencioso.** Ante datos inconsistentes o falta de evidencia, el sistema lo dice explícitamente. Nunca degrada su output en silencio y lo presenta como si fuera confiable (ver `audit.md` y `decisions.md` — este principio nace directamente de bugs reales del proyecto que ocurrieron por lo contrario).

## Diferencial real del producto

El copiloto en tiempo real —lectura automática de equipo, overlay durante el combate— es una **funcionalidad principal y permanente** del producto, para uso personal y comunitario. No es una característica de la que haya que retroceder por prolijidad arquitectónica; es, junto con la memoria de combate y el análisis posterior, lo que distingue a Champions HUD de cualquier sitio de estadísticas del meta (que existen y van a seguir existiendo, y con los que el producto no compite). Ver `decisions.md` #3 y `architecture.md` para cómo esto se sostiene técnicamente sin atarse a una sola plataforma.

La estrategia comercial (monetización, distribución, límites free/pro) es una decisión separada, que se toma más adelante y no condiciona ni recorta la visión del producto ni su arquitectura hoy. Ver `future.md`.

## Usuarios objetivo

El producto se diseña para el jugador competitivo activo (ladder, práctica, torneos con Open Team Sheets), no para el jugador casual ni para quien busca una referencia de datos. El detalle de personas y casos de uso está en [`product.md`](./product.md).

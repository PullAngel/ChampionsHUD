# Diseño de producto

Este documento asume la filosofía definida en [`vision.md`](./vision.md). Si algo acá parece sugerir una jugada o duplicar información que el juego ya muestra, es un error de este documento, no una excepción válida.

## Personas

**Ana, grinder de ladder.** Juega muchas partidas por sesión. Quiere dejar de perder por olvidar un estado de campo o por no saber si el rival lleva un ítem que cambia todo. Usa la capa Glance y ocasionalmente Peek, nunca Deep durante el combate. Éxito: sube de rating y siente que "ve" más de lo que veía antes.

**Bruno, jugador de torneos.** Practica series al mejor de 3 con amigos y le importa lo que pasa después de la partida: qué patrones repite, qué información reveló de más. Es quien más valor le va a sacar al análisis post-combate y a la memoria entre partidas de una misma serie.

**Carla, jugadora nueva en competitivo.** No conoce todavía el vocabulario del meta. Las explicaciones expandibles del copiloto ("¿por qué estimás esto?") funcionan como micro-lecciones. Éxito: en poco tiempo entiende el meta sin haber tenido que leer una guía aparte.

Diseñar para Ana, dar profundidad para Bruno, enseñar a Carla — en ese orden de prioridad de esfuerzo.

## Modelo mental del usuario

El jugador no piensa en distribuciones de probabilidad. Piensa en preguntas concretas:

- *"¿Quién pega primero?"* → orden de velocidad.
- *"¿Me mata? / ¿Lo mato?"* → rango de daño en lenguaje de resultado ("KO probable", "sobrevive con margen").
- *"¿Qué tiene?"* → ítem, habilidad, cuarto movimiento probable.
- *"¿Qué le queda atrás?"* → los Pokémon rivales no elegidos o no revelados.
- *"¿Qué estoy pasando por alto?"* → algo que cambió y que el jugador no notó.

Toda la interfaz se organiza alrededor de estas cinco preguntas. Si un dato no responde a ninguna, no pertenece a Glance ni a Peek.

**Validado 2026-08-01** contra investigación externa sobre qué distingue a un jugador de VGC profesional (fuentes: Smogon, VGC Guide, Nugget Bridge, un paper académico de 2025 sobre predicción de leads) y contra una sesión de preguntas con Angel como jugador real — detalle completo en `decisions.md` #20. La pregunta *"¿Me mata? / ¿Lo mato?"* resultó ser, en la práctica de Angel, el cuello de botella más grande de los cinco: no la falta de info, sino la precisión del cálculo en el momento exacto en que decide (ej. necesitar bajar una cantidad de vida muy específica para asegurar un KO al turno siguiente, con margen de error real de ~10% al estimarlo de memoria). Esto no cambia el modelo de las cinco preguntas — lo confirma y indica dónde está el mayor apalancamiento: el Motor de Cálculo ya construido.

## Flujo completo de una batalla

1. **Pre-combate:** el equipo propio ya está cargado (una sola vez, no por partida). El HUD queda flotando, en reposo.
2. **Team Preview:** lectura automática del equipo rival (o corrección de 1-2 taps si el reconocimiento falla). El copiloto entrega su primer valor: equipos del meta similares al detectado, amenazas principales contra tu equipo, y lo que hace falta saber antes de elegir tus cuatro.
3. **Turno — decisión:** Glance muestra orden de velocidad estimado y, si hay algo relevante, una alerta puntual. Peek disponible para profundizar. El jugador decide en el juego, no en la app.
4. **Turno — resolución:** cada evento observable (movimiento usado, daño, cambio de Pokémon, activación de ítem/habilidad) entra al registro de eventos, por captura automática o por corrección manual mínima. El modelo interno se actualiza: un daño observado descarta spreads incompatibles; un orden de acción inesperado abre la hipótesis de un ítem de velocidad; un movimiento revelado fija un slot.
5. **Actualización silenciosa:** el HUD refleja el nuevo estado. Solo emite una alerta si una creencia importante cambió de categoría (por ejemplo, de "estimado por meta" a "confirmado").
6. **Fin de combate:** el resultado queda registrado. La pantalla de resumen es la puerta de entrada al valor de largo plazo: qué acertó y qué falló el modelo, qué información se reveló de más.
7. **Serie (Bo3):** el estado de creencias sobre el rival persiste entre juegos de la misma serie — lo confirmado sigue confirmado, y las elecciones previas informan la predicción de selección del siguiente juego.

## Capas de interfaz

Tres niveles de profundidad, un gesto entre cada uno.

**Qué entra en cada capa lo decide el motor de prioridad, no una lista fija.** Desde `decisions.md` #21, el HUD jerarquiza: calcula qué información es más probable que cambie la decisión de *este* turno y la sube a Glance; el resto baja a Peek y Deep. El criterio no es la importancia abstracta del dato sino si **cruza una frontera de decisión** — un cálculo que da 20% es información, uno que da 47–52% contra un rival al 50% de vida es decisivo. Detalle del cálculo en [`inference.md`](./inference.md) §10.

Jerarquizar información **no es recomendar una jugada**: se ordena qué mirar, nunca qué hacer. Sigue sin haber ranking de movimientos propios ni etiqueta "MEJOR" (`decisions.md` #19).

El orden de peso base salió de la sesión de asesoría VGC (`decisions.md` #20): orden de velocidad crítico › rango de KO › amenaza entrante › posibilidad de Protect/prioridad › back probable › el resto.

### Glance (siempre visible)

Legible en menos de un segundo, en visión periférica mientras se mira el juego. Contiene únicamente:

- Orden de velocidad estimado del turno actual.
- La alerta activa más relevante, si existe una.
- El dato de mayor relevancia calculada del turno, cuando cruza una frontera de decisión.

**Importante:** Glance no repite contadores que Pokémon Champions ya muestra correctamente en pantalla (Tailwind, clima, pantallas, Trick Room, etc.). Repetir esa información es ruido visual sin valor. Un dato de campo solo aparece en el HUD cuando **agrega algo que el juego no muestra** — por ejemplo, cruzar la duración restante de un efecto con una estimación oculta ("le quedan 2 turnos de Tailwind y todavía no reveló su Pokémon más rápido") o señalar una interacción no obvia entre varios efectos simultáneos. Si hay duda sobre si algo agrega valor, la respuesta por defecto es no mostrarlo.

### Peek (un tap)

Panel expandido del rival activo: sets probables (con su estado de confianza), movimientos revelados vs. probables, rangos de daño relevantes contra el Pokémon activo propio, y el PP restante de **todos** los movimientos revelados (confirmado como brecha real por Angel: *"muy pocas veces lo cuento... o cuando ya estamos en late game y no puedo recordar con precisión"*; el alcance completo — no solo los movimientos "clave" — lo decidió él, ver `decisions.md` #20. Todavía no construido, Sprint 2.5 en `roadmap.md`).

Descripción de la habilidad, expandible/secundaria — no aparece en el primer vistazo (no responde ninguna de las cinco preguntas de arriba por sí sola), pero está a un tap si hace falta consultarla. Angel, al ser consultado: *"no es información primordial, pero sería genial que la pueda dar si la necesito"*.

### Deep (dos taps, pensado para entre turnos o pausa, no para el turno en curso)

El modelo completo: los seis Pokémon rivales con su estado de hipótesis, historial de eventos del combate, hipótesis descartadas y por qué.

## Interacciones diseñadas y su costo

| Momento | Interacción esperada | Costo aceptable |
|---|---|---|
| Team preview | Confirmar lectura automática, o seleccionar manualmente | 0–6 taps |
| Durante el turno | Ninguna, salvo corrección de error de lectura | 0–2 taps por error |
| Corrección de reconocimiento | Tocar el dato erróneo → elegir de una lista corta ordenada por probabilidad | 2 taps, cero teclado |
| Post-partida | Explorar resumen (opcional, sin presión de tiempo) | Sin límite — no es tiempo de combate |

Presupuesto total de interacción manual dentro del combate: unos pocos taps por partida como máximo, salvo que el reconocimiento automático esté fallando (en cuyo caso el objetivo es que la corrección sea rápida, no que el jugador tolere el fallo).

## Sistema de confianza

Nunca se muestran porcentajes de probabilidad sueltos ("68% Choice Specs") porque transmiten una precisión que el sistema no tiene y que el jugador no puede auditar. En su lugar, tres niveles, cada uno con su cadena de evidencia disponible en un tap:

- **✔ Confirmado** — observado directamente (ítem revelado por Knock Off, habilidad activada, movimiento usado).
- **◆ Deducido** — descartado por eliminación a partir de evidencia ("superó en velocidad a un Pokémon que solo es posible con un ítem que aumenta la velocidad → los spreads lentos quedan descartados").
- **○ Estimado por meta** — sin evidencia propia todavía, solo lo más común en los datos de uso disponibles.
- **⚠ Contradicción** — la evidencia no es compatible con ninguna posibilidad conocida. No se resuelve relajando el filtro en silencio: se muestra y se ofrece deshacer.

Estos niveles **no se etiquetan a mano**: se derivan del tamaño del conjunto de hipótesis vivas de cada dato (uno solo → Deducido, varios → Estimado, ninguno → Contradicción). Ver [`inference.md`](./inference.md) §3.1 — que el vocabulario de producto salga del modelo de datos, y no de una etiqueta paralela que hay que acordarse de actualizar, es lo que evita que se desincronicen.

Cada estimación es expandible a la evidencia puntual que la sostiene: qué evento la produjo y qué regla se aplicó. Esto vale también para las descripciones de riesgo que habilita `decisions.md` #21 — si el HUD dice "el escenario más peligroso es X", tiene que poder contestar "¿por qué me estás mostrando esto?". Cuando la evidencia contradice todos los sets conocidos, el sistema lo dice explícitamente en lugar de forzar un ajuste. Ver también el principio de fallo ruidoso en `vision.md`.

## Anti-patrones prohibidos

- Formularios largos.
- Pantallas completas difíciles de cerrar.
- Diálogos de confirmación durante el combate.
- Cualquier elemento que no pueda minimizarse o moverse en cualquier momento.
- Sonido por defecto.
- Cualquier variante de "el mejor movimiento es X", o cualquier frase que le diga al jugador qué hacer en vez de describir la posición (ver `vision.md`, "El copiloto describe la posición; la jugada la elegís vos", y `decisions.md` #21).
- Repetir en el HUD información que el juego ya muestra sin agregar valor.

# Futuro (deliberadamente pospuesto)

Este documento existe para que las ideas descartadas por ahora no se pierdan ni se improvisen a mitad de una sesión de desarrollo. Nada de lo que hay acá condiciona la arquitectura actual más allá de los puntos de extensión ya reservados en [`architecture.md`](./architecture.md) §7. No se implementa nada de esta lista sin antes actualizar `decisions.md` con la decisión concreta que lo habilite.

## Modelo de licencia (pro / free)

Hoy el producto se distribuye completo. Si en el futuro se decide limitar una versión gratuita y desbloquear la versión completa con una clave:

- El mecanismo de validación de clave y el catálogo de qué se bloquea vive enteramente en el módulo de entitlements reservado en `architecture.md` §7.1.
- El dominio (Motor) no debe modificarse para esto bajo ninguna circunstancia — si en algún momento parece necesario tocarlo, es señal de que el diseño de entitlements está mal ubicado.
- Qué features específicas quedarían del lado free vs. pro es una decisión de negocio no tomada. Sugerencia para cuando se tome: nunca limitar el cálculo básico de daño/velocidad ni las alertas de seguridad — limitar profundidad (historial extendido, análisis de hábitos, series), no competencia mínima. Esto es una recomendación, no una decisión — queda pendiente de confirmación explícita.

## Publicidad

No implementada. Si se agrega en el futuro:

- Vive exclusivamente en superficies frías de la capa de Presentación (resumen post-combate, biblioteca de historial).
- Nunca en Glance/Peek ni durante el combate activo.
- No requiere ningún cambio en el Motor (ver `architecture.md` §7.2).

## Sincronización multi-dispositivo

El event log ya es, por diseño, el formato natural para sincronizar (decisión #9). Cuando exista, es una capa de replicación sobre Persistencia, opcional, con respaldo como caso de uso principal antes que colaboración en tiempo real.

## Multi-cliente / otras plataformas

Si en algún momento existe un cliente para otra plataforma, consume el mismo Motor (decisión #10) e implementa su propia Percepción y Presentación. No implica ninguna decisión sobre reemplazar o relegar el overlay Android, que sigue siendo el cliente principal (decisión #3).

## Análisis de hábitos a largo plazo

Detectar patrones propios repetidos entre partidas (por ejemplo, cambios excesivos ante cierto tipo de amenaza) es un análisis batch sobre los event logs ya guardados. No requiere cambios en el Motor de combate; es un consumidor más del log, igual que el resumen post-partida.

## Recomendaciones de equipo

Cruzar resultados históricos con debilidades recurrentes para sugerir ajustes de equipo. Importante: esto es distinto de recomendar una jugada dentro de un combate (prohibido, decisión #1) — acá se trata de un análisis fuera de combate, sobre historial propio, y con el mismo cuidado de mostrar razones antes que órdenes.

## Open Team Sheets

Ya contemplado como un tipo de evento más en la Fase 4 del roadmap (no requiere cambios en el motor de inferencia: simplemente colapsa hipótesis a certeza desde el arranque del combate).

## Multi-idioma completo

La arquitectura ya lo soporta por diseño (decisión #7: slugs canónicos en inglés, idioma solo en presentación). Agregar un idioma nuevo es un trabajo de contenido (traducciones), no de arquitectura, siempre que la adopción de `t()` se mantenga al 100% desde la Fase 0.

## Ampliar el acceso a la API de Limitless

Los endpoints de torneos usados hoy no requieren clave (ver `architecture.md` §10.1). Si en el futuro el volumen de datos necesario crece (por ejemplo, para usar el endpoint `/decks` o levantar límites de tasa), Limitless ofrece solicitar una API key gratuita para proyectos con caso de uso público/comunitario legítimo. No es necesario para el pipeline actual; queda documentado para cuando haga falta.

## Estrategia comercial y de distribución

Explícitamente sin resolver (decisión #16). Preguntas abiertas para cuando se retome: canal de distribución (APK directo vs. tienda oficial, considerando el riesgo de propiedad intelectual identificado en revisiones previas), si el overlay condiciona esa elección, y qué forma toma la monetización una vez resueltas las anteriores. Ninguna de estas preguntas bloquea el desarrollo de producto descrito en `roadmap.md`.

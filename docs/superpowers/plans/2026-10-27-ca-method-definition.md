# Cartera CA phase 2 method definition plan

> **For agentic workers:** ejecución inline en esta sesión, según la preferencia vigente. Aplicar superpowers:executing-plans si se retoma. No desarrollar el motor de trading como parte de este plan.

**Goal:** entregar un método candidato determinista, versionado, con procedencia y ejemplos verificables, listo para implementar y evaluar en fase 3.

**Architecture:** especificación de investigación independiente del importador. Un pequeño calculador local verifica la aritmética de los ejemplos; no procesa señales reales ni genera órdenes. El método no equivale a una réplica confirmada por el dueño.

**Tech Stack:** Markdown y biblioteca estándar de Python, con Decimal para importes. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-27-cacl-ca-paper-design.md`, sección «Contenido obligatorio de la fase 2».

## Restricciones

- Sólo Cartera CA y las 72 etiquetas del adjunto; admisión operativa sujeta a identificación del instrumento.
- Sin broker, credenciales, instalación de plugins, backtesting ni órdenes.
- Mantener los 134 SPY y 51 LLY como referencia histórica; no inventar stops ni motivos históricos.
- Las cifras ausentes de las fuentes son decisiones propuestas para investigación, no parámetros atribuidos al dueño.
- Un dato desconocido obligatorio bloquea la decisión; un catalizador no acreditado no gana puntos.

## Tarea 1 — Evidencia y elección del método

- [x] Leer diseño aprobado, transcripción y fotogramas del video entre 00:51 y 01:48.
- [x] Contrastar ejemplos de `Risk_Management` con el 0,40% ilustrado en el video.
- [x] Consultar documentación primaria sobre órdenes y disponibilidad temporal de datos; no derivar rentabilidad de esos documentos.
- [x] Preguntar si se desea un método propuesto o una réplica del dueño; avanzar con el borrador autorizado y señalar sus supuestos mientras no exista otra instrucción.

## Tarea 2 — Especificación completa

**Crear:** `docs/methods/ca-method-v1.md`.

- [x] Definir identidad, procedencia, universo, datos y calendario.
- [x] Precisar mercado, patrón, nueve criterios, puntuación y catalizador estructurado.
- [x] Fijar entrada, vencimiento, stops, objetivos, cierre temporal y tratamiento de ejecuciones parciales.
- [x] Fijar cantidades, efectivo, concentración, riesgos, frenos y posiciones heredadas.
- [x] Revisar que cada decisión tenga una fórmula, umbral, prioridad y comportamiento ante dato faltante.

## Tarea 3 — Ejemplos comprobables

**Crear:** `examples/ca_method_v1.py` y `docs/methods/ca-method-v1-examples.md`.

- [x] Calcular con Decimal el ejemplo del video y la diferencia al usar el patrimonio CA.
- [x] Verificar puntuaciones, límites de cantidad, reservas, huecos, stops, frenos y neutralización de aportes con entradas sintéticas explícitas.
- [x] Añadir assertions con resultados esperados y comprobar que una salida incoherente falla; no presentar estos ejemplos como prueba de un motor inexistente.
- [x] Ejecutar `.venv/bin/python examples/ca_method_v1.py` y conservar el resultado local en `.context/phase2/`.

## Tarea 4 — Cierre

**Modificar:** README y sección de estado/próximo trabajo del diseño original.

- [x] Documentar exactamente qué puede pasar a fase 3 y qué evidencia no se ha comprobado.
- [x] Verificar ejemplos, referencias locales, ausencia de contradicciones y `git diff --check`.
- [x] Commit de documentos y calculador, sin incluir adjuntos ni salidas privadas.
- [x] Completar `/goal` al cumplir el entregable de método candidato; no afirmar aprobación del dueño ni rentabilidad validada.


## Resultado de ejecución

Entregados `CA-S2-1.0.0`, sus ejemplos y el calculador local. Se adoptó el enfoque de propuesta para investigación comunicado en la sesión; no se ha recibido confirmación del dueño sobre las reglas adicionales. La clasificación de candidato permanece visible en el reglamento, README y diseño general.

Verificación: calculador ejecutado correctamente; 21 assertions en el código (las del ejemplo heredado se ejecutan para ambos activos). Una mutación del resultado esperado 373 → 374 produjo AssertionError, como corresponde. Se comprobaron nueve enlaces locales y ausencia de marcadores pendientes. La revisión manual cubrió cortes temporales, umbrales inclusivos, reservas, reglas de recuperación, protección parcial y atribución de resultados. No se modificó el importador ni se volvió a certificar su suite en esta fase documental.

Salida privada de cálculo: `.context/phase2/ca-method-v1-examples.json`. Sin acceso a brokers ni datos actuales. El siguiente entregable es la implementación/evaluación aislada de fase 3, no ejecutar las cantidades didácticas.

# Cartera CA phase 3 implementation plan

> **For agentic workers:** ejecutar inline mediante superpowers:executing-plans, siguiendo la preferencia vigente. No crear brokers, órdenes ni automatizaciones externas.

**Goal:** implementar una evaluación reproducible y comprobar sus límites con evidencia disponible.

**Architecture:** datos locales validados → decisiones temporales → contabilidad y simulación por eventos → resultados base/estrés y auditoría. Se reutilizan las revisiones CA y `atomic_write`.

**Tech Stack:** Python estándar, Decimal, unittest, SQLite existente. Sin dependencias nuevas.

**Spec:** `docs/superpowers/specs/2026-10-27-ca-evaluation-design.md` y `docs/methods/ca-method-v1.md`.

## Restricciones globales

- Método `CA-S2-1.0.0` y universo CA; no optimizar parámetros usando resultados.
- Ejemplos sintéticos claramente identificados; no sustituir cotizaciones inexistentes por precios inventados en una evaluación histórica.
- Falla de dato obligatorio bloquea nuevas entradas; nunca se elimina silenciosamente del denominador de cobertura.
- Dinero en Decimal; conservar original, procedencia y hashes.

## Tarea 1 — Datos y reglas

**Crear:** `market_data.py`, `strategy.py`, `tests/test_strategy.py` y utilidades de fixture sintética.

- [x] Escribir pruebas de 254 sesiones, barra futura, duplicado contradictorio y dato inválido. Ejecutar y observar fallo por módulo ausente.
- [x] Implementar `validate_dataset(data, allowed_symbols)`, `history_as_of(data, symbol, session_index)` y `evaluate_signals(data, session_index)`.
- [x] Probar ruptura y vector de nueve puntos con fixture calculada, falta de VIX, cobertura y catalizador conocido después del corte.
- [x] Ejecutar `python -m unittest tests.test_strategy -v` y corregir cualquier fallo.

## Tarea 2 — Contabilidad y riesgo

**Crear:** `portfolio.py`, `tests/test_portfolio.py`.

- [x] Probar que 100.000 de patrimonio, entrada100 y stop95 permiten80 acciones por riesgo, y que efectivo10.800 reduce a7 al conservar10.000 más colchón.
- [x] Implementar `Ledger`: reserva, fill, cancelación, venta, liquidación de efectivo, posición heredada y serialización/restauración.
- [x] Probar ventas no liquidadas, duplicación de fill, split, aportes unitizados, dividendos y protección desconocida.
- [x] Implementar frenos con umbrales inclusivos, cinco cierres de recuperación y reducción proporcional; verificar stop monotónico.
- [x] Ejecutar `python -m unittest tests.test_portfolio -v`.

## Tarea 3 — Simulación completa

**Crear:** `simulation.py`, `tests/test_simulation.py`, `examples/phase3_synthetic.py`.

- [x] Probar entradas a apertura+5, vencimiento+30, hueco superior y stop/objetivo ambiguos antes de implementar `simulate(data, snapshot, stress=False)`.
- [x] Integrar señales nocturnas, tamaño/reservas, posiciones heredadas, cotizaciones y OHLC, costes y deslizamiento.
- [x] Probar parcial, fallo de protección, desconexión, reinicio y cierre temporal; conservar incidencias en resultados.
- [x] Calcular patrimonio unitizado, PnL neto, drawdown, costes y referencia SPY con tratamiento explícito de flujos.
- [x] Ejecutar `python -m unittest tests.test_simulation -v`.

## Tarea 4 — Evaluación, CLI y entrega

**Crear:** `evaluation.py`, `tests/test_evaluation.py`, `docs/methods/ca-evaluation-data.md`.
**Modificar:** `__main__.py`, README y estado del diseño general.

- [x] Probar `evaluate` sin datos: salida2, informe de carencias y universo por verificar; nunca rentabilidad cero como sustituto de falta de evidencia.
- [x] Implementar reporte determinista con hashes, tipo de datos, métricas base/estrés, decisiones y limitaciones; salida1 para paquete inválido.
- [x] Ejecutar fixture sintética completa dos veces, comprobar mismo resultado y ausencia de modificaciones en la revisión CA.
- [x] Ejecutar toda la suite con `CA_WORKBOOK` definido y `git diff --check`.
- [x] Entregar resultados y criterio de avance honesto; no dar por validada rentabilidad si falta la fuente de mercado o el período prospectivo.

## Evidencia de entrega — 27 de octubre de 2026

- Suite completa: `CA_WORKBOOK='.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx' .venv/bin/python -m unittest discover -s tests -v`: **80 pruebas aprobadas**, incluidas las 33 existentes de importación/conciliación.
- Ejemplos de fase 2 conservados; sin dependencias nuevas ni cambios al reglamento `CA-S2-1.0.0`.
- `evaluate --revision 2`: salida 2, `data_insufficient`, sin métricas inventadas; inventario de las 72 etiquetas CA.
- `evaluate --revision 2 --dataset .context/phase3/synthetic-market.json`: salida 0, `synthetic_only`, cuatro sesiones ficticias, corridas base y estrés. No es validación de rentabilidad.
- Ambas evaluaciones repetidas con contenido idéntico. Evidencia privada y rutas de informes en `.context/phase3/verification.json`.
- Original Excel y SQLite mantienen sus SHA-256; no hay modificaciones a posiciones históricas ni órdenes externas.
- Casos de revisión corregidos y cubiertos: hueco de apertura, nueva comprobación de riesgo de órdenes pendientes, expiración, fill por debajo del stop, trailing con primera quote tardía, duplicación de splits, unidades de resultados, datos finales ausentes, retiro no financiable por benchmark y checkpoint incompatible.
- Entrega técnica de fase 3 completada; resultado de mercado **inconcluso**. No hay fuente histórica conectada, manifiesto real acreditado ni período prospectivo observado. Fase 4 no iniciada.

# CACL Investment Lab — Cartera CA

**Para continuar con otro agente o compañero:** leer [CONTEXT.md](CONTEXT.md), con decisiones, avances, pendientes y pasos para preparar una copia del proyecto.

Fases 1–3: importación y conciliación de CA, método candidato `CA-S2-1.0.0` y simulador local con informes reproducibles. La mecánica se comprueba con escenarios sintéticos; **la rentabilidad está sin validar por falta de históricos de mercado**. No se conecta a brokers, no descarga precios y no envía órdenes.

## Método candidato y evaluación

El [reglamento CA v1](docs/methods/ca-method-v1.md) define mercado, patrón S2, nueve puntos, catalizador estructurado, entradas, salidas, tamaño, efectivo, concentración, frenos y gestión de SPY/LLY heredados. Distingue lo observado en el video de los parámetros propuestos para probar. No representa una confirmación del método del dueño ni una estrategia validada.

Los [ejemplos calculados](docs/methods/ca-method-v1-examples.md) se reproducen sin Excel ni red:

```bash
.venv/bin/python examples/ca_method_v1.py
```

Este calculador comprueba aritmética con assertions. El simulador de fase 3 añade decisiones por fecha, reservas, riesgo, stops, costes y escenarios adversos. Su [guía de datos y uso](docs/methods/ca-evaluation-data.md) describe el contrato y sus límites.

Después de importar CA, generar el diagnóstico de datos disponibles:

```bash
.venv/bin/python -m cacl_ca evaluate
```

Sin paquete de mercado, escribe el informe en `.context/phase3/` y devuelve código **2**, estado `data_insufficient`. Para comprobar el simulador con datos **ficticios**:

```bash
mkdir -p .context/phase3
.venv/bin/python examples/phase3_synthetic.py > .context/phase3/synthetic-market.json
.venv/bin/python -m cacl_ca evaluate --dataset .context/phase3/synthetic-market.json
```

El resultado `synthetic_only` comprueba ejecución del programa, no rendimiento histórico. Los informes incluyen hashes, decisiones, operaciones hipotéticas y resultados base/estrés. No habilitan paper trading.

La siguiente etapa tiene presupuesto de **USD 0** y se ejecutará en esta Mac. La [guía de arranque gratuito](docs/methods/ca-zero-budget-setup.md) recoge cómo preparar la cuenta paper y qué permisos de datos faltan por comprobar. El acceso gratuito a IEX en tiempo real no satisface por sí solo el contrato SIP del método.

## Ejecutar

Desde la raíz del repositorio, con Python 3.11 o posterior (verificado con 3.14):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export CA_WORKBOOK='.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx'
.venv/bin/python -m cacl_ca import "$CA_WORKBOOK"
```

Se puede usar otra ruta de entrada y elegir el destino con `--output-dir RUTA`. La estructura esperada del libro está descrita en el [plan de implementación](docs/superpowers/plans/2026-10-27-ca-import-reconciliation.md).

Por defecto, los resultados privados quedan en `.context/ca/`, excluida de Git:

- `ca.sqlite3`: revisiones completas con registros, celdas de origen, fórmulas, métricas e incidencias.
- `sources/<sha256>.xlsx`: copia exacta del original, sin sobrescribir archivos distintos.
- `reports/<sha256>-v2.md`: informe de conciliación y revisión. Si hay errores financieros, termina en `-invalid.md`.

Repetir el comando con el mismo archivo y versión reutiliza la revisión, sin duplicarla ni modificar sus datos. Un Excel distinto crea otra revisión; las carteras no se suman entre revisiones. Un fallo de SQLite puede dejar una copia del Excel sin revisión, recuperable al repetir la importación. Los cálculos almacenados no se actualizan retroactivamente: si cambia el formato o el cálculo del importador, incrementar `schema_version`.

Si se elige un destino fuera de `.context/`, proteger y excluir esos archivos financieros de Git por separado.

## Alcance y resultado del adjunto

Se importan `Cartera_CA`, `Liquidación_Posiciones_CA`, `History_CA` y exclusivamente el bloque CA de `Dividend Payments`. `Risk_Management` se conserva como referencia; no activa reglas de riesgo. Los paneles laterales se conservan como datos derivados, sin contarlos otra vez como operaciones. CL y PYPL_BABA quedan fuera de la extracción financiera.

El archivo de referencia contiene 134 SPY y 51 LLY, 125 filas de operaciones cerradas, 45 flujos CA y 72 etiquetas de activos entre posiciones e historial. Los flujos incluyen retenciones negativas y pagos distintos de dividendos. Su neto es USD 1.833,60.

| Conciliación | USD |
| --- | ---: |
| Posiciones, con precios guardados | 168.508,86 |
| Efectivo calculado | 809.190,11 |
| Patrimonio calculado | 977.698,97 |
| Resultado cerrado antes de ajustes | -128.407,33 |
| Resultado cerrado con comisiones y ajuste FIFO | -128.422,52 |

La fecha de referencia del historial es 2026-10-27; no acredita la hora de los precios guardados. Se usa `Decimal` y comparación monetaria a centavos. Se comprueba el valor de las posiciones, se agregan los PnL guardados de operaciones y se contrastan saldos, flujos y métricas básicas. No se reconstruyen ejecuciones ni lotes de broker.

El resultado esperado es **`review_required`** aunque cuadren los importes. El informe muestra qué revisar:

- `History_CA!AH3` usa un rango hasta AH266 con datos posteriores; los gráficos tampoco llegan al último día de la serie.
- Un rótulo menciona 106 operaciones, frente a 125 filas cerradas.
- Las bases de rentabilidad y las fechas del aporte difieren: contrastar con el extracto de Schwab y el comprobante del aporte.
- Los errores de Excel, las métricas avanzadas y los posibles grupos de salidas parciales requieren revisar definiciones y comprobantes de lotes.
- Los símbolos se conservan tal como aparecen; su identidad y disponibilidad en Alpaca no se han comprobado.

Las fórmulas no se ejecutan ni recalculan. Sharpe, Sortino, VaR y otros indicadores avanzados quedan como `reference_only`, sin certificación. No se verifica efectivo con Schwab, ni se añaden bonos ni se habilita paper trading en esta fase.

## Estados y códigos de salida

| Estado | Salida | Efecto |
| --- | --- | --- |
| `reconciled` | 0 | Guarda revisión; no autoriza operar. |
| `review_required` | 0 | Guarda revisión e incidencias pendientes. No equivale a datos certificados. |
| `invalid` | 2 | Genera diagnóstico, sin insertar una revisión de cartera. |
| Error de lectura, escritura o SQLite | 1 | Muestra un error concreto; permite corregir y repetir. |

## Verificación

El Excel real es una fixture privada obligatoria. No está versionado; las pruebas fallan explícitamente si `CA_WORKBOOK` no apunta al adjunto de referencia.

```bash
export CA_WORKBOOK='.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx'
.venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Las pruebas cubren aislamiento CA, conciliación y revisiones inmutables; exclusión de información futura, señales, límites, efectivo liquidado, huecos, parciales, fallos de protección, reinicios, costes y reportes reproducibles. El original se conserva intacto.

El [diseño aprobado](docs/superpowers/specs/2026-10-27-cacl-ca-paper-design.md) describe el proyecto completo. La fase 3 entrega simulación y evaluación de carencias; quedan pendientes la evidencia de mercado, la integración paper de fase 4 y la operación de fase 5.

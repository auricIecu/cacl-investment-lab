# CACL Investment Lab — Cartera CA

Fase 1: importar y conciliar el Excel de CA, conservar su procedencia y generar un informe local. No se conecta a brokers, no consulta precios y no envía órdenes.

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

Las pruebas cubren aislamiento CA, paneles laterales, datos incompletos, signos de retenciones, conciliación, revisiones inmutables, fallo transaccional, integridad del original y ejecución del comando como proceso.

El [diseño aprobado](docs/superpowers/specs/2026-10-27-cacl-ca-paper-design.md) describe las fases posteriores. Esta entrega termina en importación y conciliación local.

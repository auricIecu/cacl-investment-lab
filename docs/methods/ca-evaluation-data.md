# Evaluación local de CA — datos y uso

La fase 3 entrega un simulador del método candidato `CA-S2-1.0.0`, escenarios adversos e informes reproducibles. **Con los adjuntos disponibles, la evaluación de rentabilidad es inconclusa:** faltan series de mercado y verificación de instrumentos. El Excel conserva estado `review_required`. No hay conexión a broker, órdenes ni descarga automática.

## Ejecutar

Desde la raíz del proyecto, después de importar el Excel como indica el README:

```bash
.venv/bin/python -m cacl_ca evaluate --revision 2
```

La revisión 2 corresponde al adjunto importado en este workspace; omitir `--revision` selecciona la última. `--db` permite otra base CA. Sin datos de mercado, el comando devuelve **2** y escribe el diagnóstico; eso es el resultado esperado, no una excepción.

Para comprobar la mecánica con precios ficticios:

```bash
mkdir -p .context/phase3
.venv/bin/python examples/phase3_synthetic.py > .context/phase3/synthetic-market.json
.venv/bin/python -m cacl_ca evaluate --revision 2 --dataset .context/phase3/synthetic-market.json
```

El ejemplo tiene 22 etiquetas de CA, 254 sesiones previas y cuatro sesiones de evaluación. Sus precios, sectores y calendario son inventados para pruebas. **No clasifica el universo real ni mide rentabilidad histórica.** No cambiar `kind` a `historical` para presentar este ejemplo como evidencia.

Para una evaluación exploratoria real, proporcionar `--dataset RUTA.json` con el contrato siguiente. Las credenciales no forman parte del paquete. Las rutas de salida se pueden cambiar con `--output-dir`; mantener los datos privados fuera de Git.

## Artefactos y estados

Por defecto se escriben en `.context/phase3/`:

| Archivo | Contenido |
| --- | --- |
| `evaluation-<hash>.md` | Resultado legible, carencias, métricas cuando proceden y limitaciones. |
| `evaluation-<hash>.json` | Planes, motivos, decisiones, contabilidad, operaciones hipotéticas y curva de patrimonio; corridas base y estrés. |
| `universe-<hash>.json` | Las etiquetas CA y su clasificación suministrada o pendiente. |

El hash identifica datos, código, reglamento y resultado. Una repetición idéntica reutiliza contenido idéntico; no modifica SQLite ni el Excel. La versión de la importación y su estado quedan en el reporte. El archivo original archivado se verifica contra su SHA-256 antes de evaluar.

| Estado | Código de salida | Interpretación |
| --- | ---: | --- |
| `data_insufficient` | 2 | Faltan datos, cobertura o conciliación necesaria; no valida la estrategia. |
| `synthetic_only` | 0 | Se completó un escenario ficticio. |
| `exploratory` | 0 | Replay del paquete histórico declarado, sujeto a revisión de fuentes y sesgo de selección. |
| Error de paquete, lectura o escritura | 1 | Mensaje concreto; corregir la entrada y repetir. |

**Salida 0 significa procesamiento terminado, no estrategia aprobada.** `performance_validation` sigue en `not_established` y `ready_for_paper` en `false`. Si faltan marcas de posiciones durante el replay, se suprimen las métricas finales en vez de calcularlas con precios obsoletos. El JSON conserva el diagnóstico y el estado parcial para revisión.

## Contrato JSON v1

El generador [phase3_synthetic.py](../../examples/phase3_synthetic.py) es un ejemplo ejecutable completo de la estructura. El validador está en [market_data.py](../../cacl_ca/market_data.py).

Importes, precios, ratios y volumen se recomiendan como cadenas decimales; el motor usa `Decimal`. No se aceptan NaN, infinito, booleanos como números ni timestamps sin zona. Las fechas son `YYYY-MM-DD`; las horas, ISO 8601 con offset o `Z`. `available_at` significa cuándo el sistema podía conocer el registro, no cuándo se descargó retrospectivamente una serie revisada.

Campos de primer nivel:

| Campo | Requisito |
| --- | --- |
| `schema_version`, `method_version` | `1`, `CA-S2-1.0.0`. |
| `kind` | `historical` o `synthetic`. |
| `feed`, `adjustment` | Históricos: `sip`, `raw`. Sintéticos: `synthetic_consolidated`, `raw`. |
| `source`, `calendar_source` | Procedencia verificable y referencia del calendario utilizado. |
| `frozen_at` | Fecha declarada de congelación del paquete/universo. No prueba por sí sola que hubiera una evaluación prospectiva. |
| `evaluation_start`, `evaluation_end` | Primera y última sesión del replay, incluidas. |
| `actions_complete` | En históricos debe ser `true`, con evidencia externa de cobertura; una lista vacía no acredita ausencia de eventos. |
| `sessions`, `instruments`, `daily`, `vix`, `earnings`, `actions`, `events` | Listas descritas abajo; `earnings` puede estar vacía. |

### Calendario e identidad

`sessions`: registros `{date, open, close}` ordenados, únicos, con al menos 254 sesiones anteriores al inicio. Usar horarios oficiales estadounidenses, incluidos festivos, cierres anticipados y cambios de hora. La fecha debe coincidir con la fecha local de apertura/cierre en `America/New_York`. El programa comprueba coherencia, pero no autentica el calendario contra una bolsa.

`instruments`: `{id, source_symbol, symbol, type, sector, eligible, source, known_at, valid_from, valid_to}`. `id` es estable; `source_symbol` debe existir en CA; `symbol` es el símbolo del paquete. Son únicos en esta versión. `valid_to` puede ser `null`. Clasificar las 72 etiquetas, incluidas las excluidas, sin reemplazarlas silenciosamente por otras. El mapeo temporal de varios símbolos de un mismo instrumento requiere normalizar la fuente antes de usar este contrato.

Sólo pueden ser elegibles `common_stock`, `adr` y `equity_etf`. Sector: uno de los once nombres GICS en inglés definidos en `SECTORS`, o `DIVERSIFIED_EQUITY_ETF`. Los excluidos conservan tipo y sector explícitos, por ejemplo `unknown`; no reciben señales. La fecha de conocimiento y la vigencia se comprueban en cada corte. SPY y LLY deben estar presentes para la apertura heredada. La identidad declarada debe comprobarse con una fuente; el programa no certifica elegibilidad en Alpaca.

### Cierres e indicadores

`daily`: `{symbol, session, open, high, low, close, volume, available_at, source}`. OHLC nominal, positivo y coherente; volumen no negativo. Una barra diaria no puede declararse disponible antes del cierre. Se necesitan 254 sesiones consecutivas por activo para evaluar indicadores, sin rellenar huecos.

`vix`: `{session, close, available_at, source}`. Se usa el cierre conocido al corte, no un dato posterior. Ausencia de VIX bloquea entradas.

Cada plan se calcula una hora después del cierre. Si hay revisiones de una barra, se elige la última disponible a ese corte. Precios de indicadores se ajustan sólo por splits efectivos y conocidos entonces; dividendos no ajustan OHLC. No suministrar precios ya ajustados, porque se duplicaría el efecto.

El volumen de una bolsa y el consolidado no son intercambiables para estas reglas. La documentación de Alpaca distingue IEX y SIP; disponer de una cuenta paper no acredita que todos los datos requeridos estén cubiertos. Un adaptador posterior debe verificar permisos, cobertura y retención de la fuente. [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq), [Historical Quotes](https://docs.alpaca.markets/us/reference/stockquotes-1).

### Eventos intradiarios

Todos llevan `{id, kind, timestamp, available_at, source}`. `available_at >= timestamp`. Un ID idéntico se procesa una sola vez; contenido contradictorio con el mismo ID se rechaza.

| `kind` | Campos adicionales | Uso |
| --- | --- | --- |
| `quote` | `symbol, bid, ask, ask_size` | Bid/ask positivo, bid ≤ask; tamaño ask entero no negativo, expresado en acciones. |
| `bar` | `symbol, start, open, high, low, close` | `timestamp` es el fin del intervalo; `start` es anterior. Trayectoria auxiliar para stops/objetivos. |
| `flow` | `amount` | Aporte positivo o retiro negativo externo al rendimiento, con valoración vigente. |
| `fault` | `action` | Sólo sintético: `disconnect`, `reconnect`, `protection_fail`, `protection_ok`. |

La entrada se comprueba a apertura +5 minutos; necesita quote de hasta cinco segundos de antigüedad y spread admisible. Sin fill, vence a +30. Un precio posterior por encima del límite mantiene pendiente una orden ya enviada hasta su vencimiento. Una ejecución por debajo del stop no se elimina del escenario: activa la salida protectora bajo las hipótesis del simulador.

Las marcas de activos mantenidos y de SPY de referencia se revisan cada minuto; antigüedad máxima de 60 segundos. Proporcionar quotes recientes también en apertura, cierre y momentos de salida. Una vela diaria no sustituye quotes ni prueba que un stop hubiese ejecutado. Si una vela intradiaria posterior a la entrada contiene stop y objetivo, se toma el stop primero. Una vela que incluye tiempo anterior al fill no prueba la secuencia posterior a él.

### Acciones corporativas y resultados

`actions` lleva `{id, kind, symbol, session, available_at, source}`:

- `split`: añadir `ratio` (nuevas acciones por cada antigua). Ajusta cantidades y niveles; una fracción no representable exige conciliación y bloquea conclusiones, sin redondearla silenciosamente.
- `dividend`: añadir `per_share` y `pay_session`; `session` es la fecha exdividendo. Se reconoce derecho con las acciones mantenidas y efectivo sólo al pagar. Incluir en el calendario la fecha de pago aunque sea posterior al final evaluado.

Eventos conocidos después de su fecha efectiva generan incidencia y bloquean conclusiones. La apertura contrafactual del replay no genera derechos anteriores a su inicio.

`earnings` es opcional. Cada registro lleva `id, symbol, published_at, available_at`; para puntuar requiere además `verified: true`, URL primaria `source`, `locator`, `basis: "GAAP"`, `period: "quarter"`, `quarter`, `prior_quarter`, `fiscal_year`, `prior_fiscal_year`, `currency`, `prior_currency`, `eps_unit`, `prior_eps_unit`, `revenue_unit`, `prior_revenue_unit`, `eps`, `prior_eps`, `revenue`, `prior_revenue`. Períodos, monedas y unidades deben ser comparables. El booleano no reemplaza comprobar el documento; sin hechos acreditados el catalizador vale cero.

## Supuestos de simulación y límites

- Conserva 134 SPY, 51 LLY y el efectivo del snapshot; los valora con precios del inicio del replay. Es una apertura contrafactual, no reconstrucción de compras del dueño. Si riesgo, concentración o datos iniciales no permiten gestionarla, bloquea el arranque sin cambiar cantidades.
- Base: 0,005 USD por acción, mínimo 1 USD por orden simulada; deslizamiento adverso de 5 puntos básicos por lado. Estrés: comisión doble y 20 puntos básicos. Son hipótesis explícitas, no tarifas del broker.
- El tamaño no supera el plan nocturno y se vuelve a comprobar antes del fill. Las reservas incluyen efectivo, comisiones y riesgo; no se reutiliza efectivo de ventas antes de la siguiente sesión.
- El modelo usa liquidación T+1 y restringe el inicio histórico a 2024-05-28 o posterior. El calendario debe representar correctamente las sesiones de liquidación pertinentes. [Investor.gov: nuevo ciclo T+1](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/new-t1-settlement-cycle-what-investors-need-know-investor-bulletin).
- El parcial usa como límite el tamaño ask observado, cancela el resto y asume conciliación/protección inmediata salvo fallo inyectado. No reproduce colas, liquidez oculta, impacto ni carreras de cancelación reales. Una desconexión con órdenes pendientes se informa como riesgo de ejecución no observado.
- Los stops protegen bajo hipótesis de ejecución y pueden perder más que el riesgo presupuestado ante huecos. Un fallo de protección bloquea nuevas entradas y programa respuesta a los cinco segundos; la salida espera precio y conexión admisibles.
- Aportes/retiros modifican unidades; dividendos forman parte del rendimiento. SPY de referencia se compra al inicio con los mismos costes y conserva en efectivo los aportes. Si un retiro excede su efectivo, su comparación se marca no disponible; falta definir una política de liquidación comparable antes de usarla para validar rendimiento.
- El estado serializado permite reanudar con `Simulator.checkpoint()` y `Simulator.restore(...)`; datos, referencia, código y método deben coincidir. Es una interfaz local de investigación, no recuperación del estado de un broker.

## Qué falta para una conclusión de mercado

Obtener y auditar el manifiesto CA completo y un paquete histórico con calendario, OHLCV consolidado, VIX, cotizaciones/intervalos intradiarios y acciones corporativas. Repetir la evaluación sin modificar parámetros a partir de sus resultados. La selección del universo desde operaciones pasadas introduce sesgo; un replay sigue siendo exploratorio.

El criterio prospectivo ya fijado en la sección 12 del [método](ca-method-v1.md) exige 60 sesiones, ampliables a 120 si no hay 20 ciclos nuevos cerrados, y controles técnicos cumplidos. No se ha observado ese período. La integración paper pertenece a fase 4 y debe comprobar por separado la mecánica del broker.

# CACL: diseño del piloto automático de Cartera CA

Fecha: 27 de octubre de 2026. Estado: diseño aprobado en conversación; plan técnico de fase 1 disponible en `docs/superpowers/plans/2026-10-27-ca-import-reconciliation.md`.

## Objetivo y decisiones acordadas

Construir por fases el sistema del video, limitado a Cartera CA y a sus activos y operaciones. El piloto ejecutará automáticamente en Alpaca Paper. El código aplicará reglas calculables; la IA ayudará a investigar y explicar, sin discreción para aprobar órdenes ni cambiar parámetros durante una sesión.

El estado inicial de referencia será la cartera existente del Excel, con SPY, LLY y efectivo. El historial se importará para análisis y trazabilidad, sin reenviar sus operaciones al broker. Bonos, otras carteras, trading real y captación de capital quedan fuera de este proyecto.

Esta especificación define alcance, arquitectura, fases y condiciones de avance. Las fórmulas de estrategia y sus parámetros se definirán y versionarán en la fase 2; las cifras del video son hipótesis, no reglas validadas ni garantías de rentabilidad.

## Evidencia y punto de partida

Fuente local: `.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx`.

Hojas principales: `Cartera_CA`, `Liquidación_Posiciones_CA`, `History_CA` y exclusivamente el bloque CA de `Dividend Payments`. `Risk_Management` aporta ejemplos que deben contrastarse. Las hojas generales de planes de entrada, opciones, remuneración y dimensionamiento no se incorporarán como órdenes o reglas vigentes por su mera presencia en el libro.

### Cobertura completa de las hojas y aclaración del dueño

La captura `.context/attachments/Z89qAr/image.png` aclara que `Dividend Payments` mezcla carteras y que existen bloques adicionales a la derecha de las tablas principales. Se verificaron ambos puntos contra el archivo recibido.

| Hoja | Bloques identificados en esta versión | Tratamiento |
|---|---|---|
| `Dividend Payments` | CA: encabezado en C4, movimientos en filas 6–50 y total en J50. CL comienza en la fila 54; PYPL/BABA en la 86. | Incorporar únicamente CA. Conservar dividendos, retenciones, ajustes y efectivo por fracciones con su tipo y signo. Los otros bloques no forman parte de sus flujos. |
| `Liquidación_Posiciones_CA` | Operaciones A:N; resúmenes mensuales R:T; consultas W:X; indicadores y parámetros Z:AA. | Importar operaciones una sola vez; conservar fórmulas, parámetros y resultados derivados como referencias de conciliación, sin contarlos otra vez como movimientos. |
| `History_CA` | Serie diaria B:J; semanal L:R; mensual T:Z; indicadores y parámetros AB:AC; series, supuestos y resúmenes para gráficos AD:AJ. | Cubrir todos los bloques y sus dependencias. Conservar fechas base, aportes, benchmark y supuestos; recalcular indicadores con períodos y definiciones explícitos. |

Los rangos anteriores describen este adjunto, no límites fijos del futuro importador. Se identificarán bloques mediante encabezados, tablas y contenido, revisando todas las columnas con datos o fórmulas. Un bloque nuevo o ambiguo genera una incidencia, no una atribución automática a CA.

El bloque CA contiene 45 movimientos cuyo neto es 1.833,60 USD, coincidente con J50; no son 45 dividendos brutos, porque incluye retenciones y otros ajustes. Los indicadores laterales incluyen frecuencia de aciertos, beneficio/pérdida media, profit factor, drawdown, duración, Sharpe, Sortino y comparación con benchmark. Sus valores guardados se preservarán como evidencia, no como cálculos ya certificados.

En `History_CA`, AH3 busca el último resultado sólo hasta AH266, mientras la serie diaria B:C llega a la fila 271 (2026-10-27). El bloque de fechas AD llega a la fila 270. Además, los indicadores y gráficos usan distintas fechas y bases de cálculo. La fase 1 debe explicar esas diferencias y detectar rangos incompletos; no escoger arbitrariamente uno de los porcentajes como rentabilidad oficial. El texto de `Liquidación_Posiciones_CA!Z3` menciona 106 operaciones, mientras AA9 y las filas cerradas contabilizan 125: la importación se basará en los registros, preservando la discrepancia del rótulo.

| Concepto | Cantidad | Coste medio guardado | Precio guardado | Valor guardado |
|---|---:|---:|---:|---:|
| SPY | 134 | 661,23 USD | 769,71 USD | 103.141,14 USD |
| LLY | 51 | 1.252,34 USD | 1.281,72 USD | 65.367,72 USD |
| Efectivo calculado | — | — | — | 809.190,10890463 USD |
| Patrimonio total | — | — | — | 977.698,96890463 USD |

La última fecha de `History_CA` es 2026-10-27. Los precios son valores guardados en el archivo, sin hora de cotización comprobada. No se interpretan como precios actuales de ejecución. El capital nominal de referencia de 1.000.000 USD se conservará separado del patrimonio actual.

El historial contiene 125 filas de operaciones cerradas en 71 símbolos. Las fechas de entrada van de 2025-09-10 a 2026-10-12 y las de salida de 2025-09-16 a 2026-10-26. Estas filas no necesariamente representan 125 decisiones independientes: hay que identificar salidas parciales y lotes relacionados.

Universo inicial: unión de los símbolos del historial y las posiciones abiertas, 72 etiquetas antes de normalizar identificadores y clasificar instrumentos. No habrá un escaneo inicial de 2.000 empresas. La disponibilidad, naturaleza del instrumento y cambios de símbolo se verificarán individualmente; los instrumentos no admitidos permanecerán en el historial y se excluirán de nuevas órdenes con motivo registrado.

### Conciliación aritmética ya comprobada

- Valor de posiciones: 103.141,14 + 65.367,72 = 168.508,86 USD.
- Resultado de filas cerradas: -128.407,33109537 USD.
- Ajustes `J133` y `J134`: comisiones de venta Schwab (-55,60) y ajuste de coste medio frente a FIFO (+40,41), neto -15,19 USD.
- Resultado realizado incluido en CA: -128.422,52109537 USD.
- Dividendos y ajustes del bloque CA: 1.833,60 USD.
- Efectivo calculado: 935.779,03 - 128.422,52109537 + 1.833,60 = 809.190,10890463 USD.
- Efectivo más posiciones: 977.698,96890463 USD.

Esto prueba coherencia de esas celdas, no una conciliación con Schwab. Se conservarán los conceptos de los ajustes; sus comprobantes y los de aportes deben contrastarse antes de certificar rentabilidad. Se conservará precisión de origen y se redondeará para presentación y según las exigencias de cada orden.

## Arquitectura mínima

Una aplicación Python con almacenamiento local en SQLite, tareas programadas e informes. Se evitarán microservicios, un frontend propio y varios agentes tomando decisiones en la primera versión.

Flujo: Excel y datos de mercado → validación y registro persistente → señales y puntuación → control de riesgo → plan fechado → órdenes paper → conciliación de ejecuciones → informe.

Responsabilidades:

1. **Importación y contabilidad:** conservar archivo original, huella, hoja/fila de procedencia, posiciones, operaciones, efectivo, aportes, dividendos y ajustes. Una reimportación idéntica no duplica movimientos. Cambios en la fuente generan una revisión, sin sobrescribir el historial anterior.
2. **Datos y estrategia:** guardar datos con fecha de disponibilidad, identidad del activo y versión del método. Las decisiones requieren datos vigentes y suficientes. Los errores de fórmulas de Excel se registran, sin convertirse en ceros.
3. **Riesgo y ejecución:** calcular cantidades, límites y órdenes exclusivamente por código. El ejecutor usa únicamente credenciales y destino paper. Se mantiene un solo responsable de enviar órdenes.
4. **Auditoría:** conservar tanto operaciones ejecutadas como señales rechazadas, con sus motivos. Separar resultados históricos de CA, resultados del modelo y resultados observados en Alpaca.

Las skills servirán de apoyo selectivo: TraderMonty para investigación y revisión del método; VectorBT para pruebas cuando represente correctamente las reglas; herramientas oficiales de Alpaca para integración. Su instalación no será condición de la importación ni reemplazará validaciones del código. Se incorporará un proveedor adicional de datos sólo si una carencia verificada lo exige.

## Representación de la cartera en paper

El registro local conservará exactamente las cantidades, costes y efectivo del Excel. Las posiciones iniciales son saldos de apertura del piloto; sus ganancias acumuladas anteriores no se atribuirán a la nueva estrategia.

La documentación consultada de Alpaca describe ejecuciones simuladas con cotizaciones actuales, pero no un procedimiento para cargar posiciones arbitrarias con costes históricos. No se asumirá que existe esa función.

En la fase 4 se comprobarán las capacidades reales de la cuenta. El procedimiento previsto es una cuenta paper dedicada, financiada con el patrimonio de referencia redondeado al centavo, y operaciones de inicialización para alcanzar 134 SPY y 51 LLY. Estas operaciones se identificarán como inicialización, no como señales de la estrategia. Antes de enviarlas deben estar definidos los controles y las salidas protectoras de las posiciones heredadas.

Los costes y el efectivo que resulten en Alpaca pueden diferir de los del Excel. Esa diferencia quedará en un informe de inicialización; no se inventarán depósitos o ejecuciones para hacerlos coincidir. Si el saldo no alcanza, el arranque se bloquea y registra la causa, sin cambiar las cantidades acordadas ni usar margen. El patrimonio paper inicial se medirá después de conciliar esta inicialización y se utilizará para medir los resultados futuros de ese entorno.

Se conservarán dos vistas explícitas: referencia histórica CA y ejecución paper. No se sumarán sus patrimonios. El riesgo operativo dependerá de las posiciones, efectivo y órdenes reales del entorno paper, contrastados con su registro local.

Alpaca documenta que paper no simula dividendos. El informe mostrará por separado los flujos externos de dividendos cuando se disponga de evidencia y no los tratará como efectivo gastable del broker. No se duplicarán con movimientos que el proveedor pudiera incorporar en el futuro.

## Fases y condiciones de avance

| Fase | Entregable | Condición para avanzar |
|---|---|---|
| 1. Reconstruir CA | Importación repetible, estado inicial, historial normalizado e informe de conciliación | Las dos posiciones y el efectivo concilian al centavo con el archivo; se explican los ajustes y se identifican los errores, lotes y activos no admitidos. Sólo se atribuyen los dividendos CA; todos los bloques laterales quedan inventariados y sus diferencias de rangos, fechas y bases se explican. No se presentan saldos calculados como verificación del broker. |
| 2. Definir el método | Documento versionado de reglas y ejemplos calculados | Mercado, patrones, puntuación 6/9, entradas por tramos si proceden, salidas, tamaño, efectivo, concentración y frenos quedan definidos sin lenguaje subjetivo. Las posiciones heredadas tienen política explícita. |
| 3. Evaluar las reglas | Simulación reproducible y evaluación de limitaciones | No se usa información futura; costes, huecos de precio y supuestos de ejecución son explícitos; el sistema respeta los límites incluso en escenarios adversos. Se documenta un criterio de evaluación fuera de muestra antes de observar sus resultados. |
| 4. Validar la ejecución paper | Conexión, inicialización conciliada y ciclo completo de órdenes | Funcionan entradas, salidas y protección; un reinicio o reintento no duplica órdenes; discrepancias, rechazos y fallos de protección se detectan y detienen nuevas entradas. |
| 5. Operar y revisar | Rutina diaria, informe semanal y evaluación del piloto | Cada decisión puede reconstruirse; se informa rendimiento, pérdidas máximas, exposición, incidencias y cumplimiento. Ampliaciones requieren evidencia del piloto y una nueva versión del método. |

La finalización de la fase 3 no exige conseguir una rentabilidad objetivo a cualquier coste. Un resultado negativo puede llevar a descartar o reformular la hipótesis. Los cambios de parámetros abren una nueva evaluación; no se reutiliza un período observado como si siguiera siendo una prueba independiente.

### Contenido obligatorio de la fase 2

- Definición exacta de indicadores, ventanas y umbrales; reglas distintas por patrón cuando el historial justifique incluirlos.
- Desglose de los nueve puntos y tratamiento del componente de catalizadores del video. Un resumen de IA no asigna puntos directamente: cualquier componente operable requiere hechos estructurados, procedencia y una función determinista; sin esa definición la fase no se da por terminada.
- Precio y momento de activación, caducidad de señales, reglas de segunda entrada y tratamiento de huecos de apertura. Un plan nocturno no presupone ejecución al cierre anterior.
- Presupuesto por operación y por cartera, concentración, número de posiciones, límite de entradas diarias y actuación ante pérdidas. Se distinguen riesgo hasta el stop, capital invertido y pérdida efectivamente posible ante huecos.
- Política para las posiciones heredadas SPY y LLY y para instrumentos cuya disponibilidad cambió desde la operación histórica. La automatización no obliga a vender una posición heredada por no cumplir una señal nueva de entrada.

## Datos, medición y límites del análisis

Las operaciones cerradas permiten medir resultados, duración, tamaños y concentración. Por sí solas no reconstruyen las razones de entrada, stops originales ni oportunidades rechazadas. Esos datos no se inventarán.

El universo se escogió a partir de activos que efectivamente se negociaron. Las pruebas retrospectivas sobre él tienen sesgo de selección y no prueban capacidad para encontrar ganadores en todo el mercado. El análisis del historial se etiquetará como exploratorio. La evaluación futura en paper se hará con universo y reglas congelados al inicio de cada versión.

Los datos de precios tratarán splits, dividendos y cambios de símbolo con una convención explícita para evitar dobles ajustes. El período disponible y el acceso al feed se verificarán antes de afirmar una validación de veinte años. IEX y datos consolidados no se tratarán como equivalentes para reglas de volumen.

Los informes distinguirán resultado realizado, no realizado, flujos y aportes. Las aportaciones no contarán como rendimiento. El informe semanal resumirá cinco aspectos: rendimiento neto del período con su referencia, caída desde máximos, exposición y riesgo, operaciones y costes, e incidencias de cumplimiento. La referencia será comparable en fechas y tratamiento de dividendos; SPY se evaluará como candidato por el historial del libro.

## Operación y manejo de fallos

El calendario será el de la sesión estadounidense con zona horaria explícita, festivos y cambios de horario. Después del cierre se genera un plan inmutable con huellas de datos y reglas; antes del envío se revisan vigencia, efectivo, órdenes pendientes, restricciones y precios. Una revisión crea una versión nueva del plan, no modifica silenciosamente la anterior.

Cada intención tendrá un identificador persistente. Ante una respuesta incierta de red se consulta el estado del broker antes de reenviar. Se consideran ejecuciones parciales, cancelaciones y órdenes pendientes al calcular la exposición.

Datos incompletos, saldos incongruentes o ausencia de protección bloquean nuevas entradas y generan una alerta. La protección ya existente se conserva; no se cancela indiscriminadamente ante fallos. La recuperación exige conciliación. El entorno paper se valida antes de cada envío y no se permite una alternativa automática a live.

La simulación histórica y paper necesitan pruebas de huecos de apertura, datos ausentes, duplicados, reinicios, splits, ejecuciones parciales y rechazo de stops. Las condiciones del simulador no se presentarán como garantía de ejecución real.

## Próximo trabajo tras revisar el diseño

Redactar el plan técnico ejecutable de la fase 1: archivos, importador, almacenamiento, pruebas y conciliación. Las siguientes fases conservan sus entregables y condiciones; sus planes técnicos se detallarán usando la evidencia de la fase anterior. No se necesitan credenciales para empezar la reconstrucción local.

## Fuentes y límites verificados

- Archivo Excel adjunto: valores guardados y fórmulas inspeccionados; no contrastado con un extracto de Schwab.
- [Alpaca Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading): simulación con cotizaciones actuales, credenciales paper separadas, limitaciones de ejecución y dividendos.
- [Alpaca: posiciones abiertas](https://docs.alpaca.markets/us/v1.1/reference/getallopenpositions): consulta de cantidades, coste y valor de mercado.
- [Alpaca Trading API MCP](https://docs.alpaca.markets/us/docs/trading-api-mcp): herramientas de órdenes, posiciones y configuración del entorno paper.

No se ha creado una cuenta, instalado plugins, ejecutado backtests ni enviado órdenes como parte de este diseño.

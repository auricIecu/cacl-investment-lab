# Método candidato de Cartera CA v1

**Versión:** `CA-S2-1.0.0` · **Fecha:** 2026-10-27 · **Estado:** especificación completa para investigación y evaluación en fase 3. No es un método confirmado por el dueño, una estrategia validada ni una autorización para operar. Las reglas adicionales propuestas se identifican como **P**; las observadas en las fuentes como **V** o **X**. Esta versión no incorpora código de ejecución.

**Enfoque confirmado por el usuario:** proponer un método completo para probar, marcando claramente los supuestos. Esta decisión confirma el carácter de propuesta de v1; no cambia sus parámetros ni acredita resultados.

La hipótesis es comprar rupturas de máximos con una base de volatilidad contraída, dentro de un mercado favorable, usando puntuación y límites calculables. Sólo se permiten posiciones largas sin apalancamiento. El sistema puede permanecer completamente en efectivo. No existe objetivo mínimo de operaciones ni obligación de alcanzar una rentabilidad.

## 1. Procedencia y decisiones de alcance

| Evidencia | Contenido verificable | Decisión de v1 |
| --- | --- | --- |
| V: video 00:51 | Régimen con SPY, medias de 50/200 sesiones, VIX y amplitud | Conservar los tres componentes; sus umbrales se definen como P. |
| V: 01:02 | Ejemplo «Breakout from a 52-week base · pattern S2», ilustrativo | Un único patrón `S2-v1`; su traducción numérica es P. No afirmar que replica el algoritmo original. |
| V: 01:08 | Ocho factores técnicos más catalizador, máximo nueve puntos; mínimo seis | Mantener nueve factores de un punto. El catalizador pierde su componente discrecional en v1. |
| V: 01:19 | Riesgo ilustrado de 0,40% y 4.000 / 10,72 → 373 acciones | Adoptar 0,40% como presupuesto candidato; redondear cantidad hacia abajo. |
| V: 01:36 | Hasta 12 posiciones, riesgo total ≤6%, hasta dos entradas por día | Conservar como límites de admisión, incluyendo posiciones heredadas y órdenes pendientes. |
| V: 01:36 | Frenos en −5%, −9%, −13%, −15% | Conservar niveles; precisar base, actuaciones y recuperación como P. |
| V: 01:42–01:48 | Plan nocturno fechado; órdenes al abrir Nueva York con protección | Usar calendario Nueva York y ventana de entrada cinco minutos después de abrir, como P. |
| X: `Risk_Management!I14`, `C23` | Ejemplos de 1,50% y 0,50% de riesgo | No son reglas vigentes. No promediar ni combinar con el 0,40% del video. |
| X: importación CA, revisión de formato 2 | 134 SPY, 51 LLY; efectivo 809.190,10890463 USD; patrimonio 977.698,96890463 USD | Saldos históricos de referencia, no precios ni saldos actuales del broker. |

**Todas las fórmulas, ventanas, límites y actuaciones de las secciones siguientes son P**, salvo las cifras V expresamente conservadas. La evidencia no acredita los veinte años de validación ni las pruebas anunciadas en el video. El historial tampoco revela los stops originales o las razones de compra.

Se consideraron tres enfoques: reproducir sólo lo explícito dejaría reglas sin definir; incorporar varios patrones añadiría hipótesis sin evidencia; completar un único patrón permite una prueba falsable y acotada. Se adopta el tercero como propuesta de investigación.

La fuente local es `CACL_InvestmentLab_v2.mp4`, de 135,9 segundos, y el Excel con SHA-256 `bc6eb1e91cad2659a1892a14bc18bf3b4c1be528434cc0bf3683b07de20dc041`. Los fotogramas y la transcripción se conservan en `.context/video-analysis/`. El informe de fase 1 conserva las discrepancias del libro; v1 no las convierte en rentabilidad certificada.

## 2. Universo y datos admisibles

El universo de referencia son las **72 etiquetas** de `symbols` de la revisión CA. Antes de la evaluación, congelar un manifiesto con identificador estable, etiqueta de origen, símbolo efectivo, mercado, tipo, sector, fechas de vigencia y fuentes. No sustituir `BRKB` ni fusionar clases, warrants o cambios de símbolo por semejanza textual.

Son admisibles acciones ordinarias, ADR y ETF de renta variable sin apalancamiento ni exposición inversa, cotizados en una bolsa estadounidense y negociables en el entorno de prueba. Se excluyen bonos, ETF de bonos, opciones, warrants, unidades, preferentes, OTC, cripto, ETF de materias primas y posiciones cortas. Un tipo o identidad desconocido queda `unverified` y no recibe nuevas órdenes. La exclusión no elimina registros históricos.

`U` es el subconjunto admisible congelado antes de evaluar, sin elegirlo por sus resultados. Suspensiones posteriores impiden comprar, pero no borran activos del denominador de cobertura. Para una evaluación histórica se requiere identidad y elegibilidad conocidas en cada fecha; si sólo se dispone de clasificación actual, el resultado se etiqueta exploratorio por sesgo de selección y supervivencia.

| Dato | Contrato mínimo | Si falta o es incoherente |
| --- | --- | --- |
| OHLCV diario de activo y SPY | 254 sesiones completas consecutivas, fechas oficiales, sin duplicados; precios positivos y `L ≤ min(O,C) ≤ max(O,C) ≤ H`; volumen no negativo | Rechazar señal de ese activo. SPY inválido bloquea entradas de toda la cartera. |
| Ajustes | OHLC ajustado sólo por splits conocidos a la fecha de decisión; volumen ajustado inversamente. Dividendos separados | No mezclar precios ajustados por dividendos con flujos explícitos. Una acción corporativa no conciliada bloquea el instrumento. |
| Volumen | Misma cobertura consolidada en numerador y denominador, conservando proveedor y feed | No sustituir volumen consolidado por IEX silenciosamente. |
| VIX | Cierre oficial de la misma sesión, valor finito positivo, con fuente y hora de disponibilidad | Bloquear nuevas entradas. |
| Cotización para entrada | Bid y ask positivos, `bid ≤ ask`, antigüedad ≤5 segundos en sesión regular | Rechazar esa intención. |
| Sector | Uno de los 11 sectores GICS o `DIVERSIFIED_EQUITY_ETF`, congelado y con fuente | Impedir nueva compra hasta clasificar; no asignar un sector por IA sin evidencia. |
| Cartera | Posiciones, órdenes, efectivo gastable sin préstamo y protecciones conciliadas | Bloquear nuevas compras; mantener protecciones existentes. |

Las sesiones se numeran según el calendario de la bolsa; no se inventan velas en festivos, suspensiones o datos ausentes. Las fechas de publicación, recepción, revisión y vigencia se guardan por separado. Un dato sólo puede influir si estaba disponible antes del cierre del plan. Los datos publicados después no se incorporan a una decisión anterior.

Para precios de órdenes se vuelve a unidades nominales vigentes. Un split transforma cantidad y niveles conjuntamente, manteniendo su significado económico; si no puede reconciliarse, no se emiten nuevas órdenes ni se cancelan protecciones indiscriminadamente.

## 3. Notación, indicadores y horario

`t` es la sesión recién cerrada. `C,H,L,V` son cierre, máximo, mínimo y volumen de la serie del activo. Todos los cocientes requieren denominador positivo. No redondear indicadores antes de compararlos.

| Indicador | Definición exacta |
| --- | --- |
| `SMA(n,t)` | Media aritmética de los últimos `n` cierres, incluido `t`. |
| `TR(t)` | `max(H(t)-L(t), abs(H(t)-C(t-1)), abs(L(t)-C(t-1)))`. |
| `ATR(n,t)` | Media aritmética de los últimos `n` TR; **no** suavizado de Wilder. |
| `R(n,t)` | `C(t)/C(t-n)-1`, retorno de precio con splits, sin dividendos. |
| `VOL20(t)` | Desviación estándar muestral (`ddof=1`) de 20 retornos simples diarios, multiplicada por `sqrt(252)`. |
| `ADV20(t)` | Media de volumen de las últimas 20 sesiones, incluida `t`. |
| `ADTV20(t)` | Media de `C(d)*V(d)` en esas mismas 20 sesiones. |
| `B(t)` | Máximo de `H` en las 252 sesiones **anteriores** a `t`, excluyendo `t`. |
| `base_width(t)` | `(max(H)-min(L))/max(H)` sobre las 20 sesiones anteriores a `t`. |

Generar el plan una hora después del cierre oficial, incluido cierre anticipado. Si no están listos los datos en ese momento, no hay entradas para ese plan; no reintentar con información posterior para la misma señal. Guardar fecha de sesión, hora UTC, zona `America/New_York`, versión del método y hashes de entradas. Las horas Madrid del video no son el reloj operativo.

Las señales de `t` sólo pueden intentar entrada en la sesión siguiente, cinco minutos después de su apertura oficial. La intención vence 30 minutos después de abrir. Nunca asumir que se puede comprar al cierre usado para calcular la señal. Cada plan es inmutable; corregirlo implica una revisión antes de su ventana de ejecución y la invalidación explícita del anterior. Una revisión conserva el corte temporal original: no admite noticias o datos que llegaron después.

## 4. Filtro de mercado y patrón S2

El mercado permite entradas sólo si se cumplen simultáneamente:

1. `C_SPY(t) > SMA50_SPY(t) > SMA200_SPY(t)`.
2. `VIX(t) ≤ 25`.
3. Al menos 50% de las acciones/ADR de `U` con datos válidos cierra por encima de su SMA50. Los ETF no participan en esta amplitud.
4. Hay al menos 20 acciones/ADR válidos y cobertura de al menos 80% del conjunto de acciones/ADR congelado. El denominador no elimina símbolos por faltar datos ese día.

Los factores se evalúan con los cierres, sin un criterio subjetivo de «mercado favorable». Un fallo impide nuevas compras; no vende automáticamente posiciones existentes.

`S2-v1` requiere todas las condiciones siguientes:

| Condición | Umbral |
| --- | --- |
| Primera ruptura al cierre | `C(t) > B(t)` y `C(t-1) ≤ B(t-1)`. Los 254 cierres/máximos permiten ambos cálculos. |
| Base reciente acotada | `base_width(t) ≤ 0,15`. |
| Contracción previa | `ATR(5,t-1) ≤ 0,80 * ATR(20,t-1)`. |
| Confirmación por volumen | `V(t) ≥ 1,50 * mean(V(t-20)..V(t-1))`. |
| Extensión máxima de la ruptura | `C(t) ≤ 1,03 * B(t)`. |

Además, precio nominal de cierre ≥10 USD, `ADTV20(t) ≥ 20.000.000 USD`, activo sin posición ni orden de compra pendiente y sin salida en las cinco sesiones anteriores. El enfriamiento cuenta sesiones completas posteriores a la salida: la primera entrada posible es la sexta. No hay promedios a la baja, piramidación ni segunda entrada por tramos en v1. Una ejecución parcial pertenece a la misma intención, no es una segunda señal.

## 5. Puntuación de nueve puntos

Cada fila vale exactamente 0 o 1. Se exige **suma ≥6**, además del filtro de mercado, patrón, datos y límites. Una puntuación alta nunca anula un bloqueo. Algunos puntos se solapan con el patrón; se conserva esa estructura del video sin afirmar nueve evidencias independientes.

| Punto | Criterio operable para ganar 1 |
| --- | --- |
| 1. Tendencia | `C(t) > SMA50(t) > SMA200(t)`. |
| 2. Cercanía al máximo anual | `C(t) ≥ 0,90 * max(H(t-251)..H(t))`. |
| 3. Momentum trimestral | `R(63,t)` en el primer `ceil(N/3)` de los `N` activos de `U` con los 254 datos requeridos. Orden: retorno descendente, desempate por identificador estable ascendente. Exigir cobertura ≥80% de `U` y `N ≥20`; de lo contrario no puntuar ni admitir entradas. |
| 4. Fuerza relativa semestral | `R(126,t) > R_SPY(126,t)`. |
| 5. Base ordenada | Se cumplen simultáneamente ancho y contracción de la sección 4. |
| 6. Sin extensión excesiva | `1 ≤ C(t)/SMA50(t) ≤ 1,10`. |
| 7. Continuidad | Al menos 35 de los últimos 63 retornos diarios son estrictamente positivos; un día sin cambio no suma. |
| 8. Volatilidad limitada | `VOL20(t) ≤ 0,35`. |
| 9. Catalizador acreditado | El registro estructurado de resultados trimestrales cumple la definición siguiente. |

### Catalizador determinista

El único catalizador de v1 es crecimiento trimestral publicado: EPS diluido GAAP y ventas del trimestre crecen al menos 20% y 10%, respectivamente, frente al mismo trimestre fiscal del año anterior. Los dos valores previos deben ser positivos. No se comparan EPS ajustados con GAAP, monedas distintas, períodos acumulados con trimestres aislados ni cifras anuales con trimestrales.

El registro exige identificador de emisor/evento, trimestre y año fiscal de ambos períodos, moneda/unidades, EPS y ventas de ambos períodos, URL primaria, ubicación de las cifras y fechas de publicación y disponibilidad. La publicación debe caer entre el cierre de la sesión `t-20` (excluido) y el cierre del plan (incluido). Los hechos deben estar comprobados contra el comunicado oficial o documento regulatorio disponible en ese momento; una transcripción o interpretación libre de IA no otorga el punto.

Si hay varios registros, usar el último disponible por `available_at`; desempatar por identificador del evento. Una corrección sólo sustituye cifras desde su propia disponibilidad. Un trimestre Q4 sólo entra si existe divulgación trimestral explícita comparable; no deducir EPS trimestral restando EPS anual y acumulado. Los ETF obtienen 0 por no aplicar este catalizador.

Sin registro admisible, el punto es 0 y la razón queda `catalyst_unverified`, `catalyst_expired` o `catalyst_not_applicable`, según corresponda. Los números ausentes siguen siendo ausentes: no se convierten en un EPS de cero. Es posible alcanzar 6/9 con factores técnicos. Las noticias generales se conservan como contexto, sin puntuación.

Las APIs de SEC ofrecen historial de presentaciones y hechos XBRL; su disponibilidad no garantiza que cualquier agregado sirva para reconstruir el estado histórico. El adaptador deberá conservar documento y versión accesibles a la fecha, además de comprobar contexto y período. [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

## 6. Plan de entrada y protección inicial

Para activos con precio ≥10 USD, v1 utiliza niveles a centavos. Si las reglas vigentes del instrumento requieren otra precisión, se bloquea hasta adaptar y versionar el contrato.

```text
entry_limit = ceil_cent(C(t) * 1,005)
initial_stop = floor_cent(min(min(L(t-4)..L(t)) - 0,10*ATR20(t),
                             C(t) - 2*ATR20(t)))
R = entry_limit - initial_stop
target = ceil_cent(entry_limit + 2*R)
```

Exigir `initial_stop > 0` y `0,02 ≤ R/entry_limit ≤ 0,08`. Se descarta una señal que no cumple; no se estrecha el stop para fabricar una cantidad mayor. `R`, stop y objetivo quedan fijados antes de entrar. Comprar más barato que el límite no ensancha el stop ni cambia el objetivo; el riesgo inicial real hasta el stop disminuye.

En apertura +5 minutos, comprobar una vez el ask: debe estar entre `B(t)` y `entry_limit`, ambos incluidos. El spread `(ask-bid)/((ask+bid)/2)` debe ser ≤0,002. Un hueco por encima del límite o caída por debajo de la ruptura cancela esa intención para toda la sesión; no perseguir precio ni esperar que vuelva. Con cotización válida, enviar en fase 4 una compra limitada bracket con stop de mercado y objetivo limitado, vigencia GTC y sólo sesión regular. Cancelar el remanente de entrada a apertura +30 minutos; las protecciones confirmadas de posiciones abiertas permanecen GTC. El límite no garantiza ejecución. La vigencia del plan y la de la protección son distintas.

El orden de candidatos es puntuación descendente, luego `R(126,t)-R_SPY(126,t)` descendente, luego identificador ascendente. Procesar secuencialmente y reservar capital/riesgo antes del siguiente. Máximo dos intenciones nuevas por sesión; una intención enviada consume el cupo aun si no se ejecuta. Reintentos técnicos usan el mismo identificador persistente y no crean otra intención.

### Contrato de ejecución para la fase 4

La documentación de Alpaca describe que las salidas bracket se activan tras completar la entrada; no debe asumirse protección activa de una ejecución parcial. También documenta que ambas salidas pueden ejecutarse antes de cancelarse en situaciones extremas. El trailing nativo no se presupone como pata bracket. Estos comportamientos deberán comprobarse en la integración. [Alpaca, órdenes](https://docs.alpaca.markets/us/docs/orders-at-alpaca)

| Evento | Acción definida |
| --- | --- |
| Sin fill al vencer | Cancelar entrada; liberar reservas sólo al confirmar cancelación y reconciliar fills. |
| Fill parcial | Detener entradas, cancelar resto y conciliar cantidad realmente adquirida. Adjuntar protección para esa cantidad. No acumular más acciones para completar el plan. |
| Protección no confirmada en cinco segundos desde detectar el fill | Estado `protection_failure`; gestionar cierre de emergencia de la cantidad conciliada. No reintentar compras. El tiempo es de detección y reacción, no una garantía de salida. |
| Estado de orden incierto o desconexión | Conservar reservas y consultar por identificador. No reenviar una orden ni vender una cantidad supuesta. |
| Stop, objetivo, cierre manual del controlador o emergencia concurrentes | Un solo ejecutor concilia posición y todas las patas; cancela/confirma las salidas que compiten antes de enviar una nueva. Cantidad de venta ≤posición confirmada. Un fill tardío obliga a conciliar otra vez. |

Si el proveedor no permite verificar este ciclo sin vender de más o dejar una posición desprotegida sin respuesta, no se habilita el piloto. Los stops pueden ejecutarse por debajo del nivel previsto durante un hueco; un stop-limit, en cambio, puede quedar sin ejecutar. Los límites de riesgo de este método son presupuestos hasta el stop, no pérdidas máximas garantizadas. [SEC, tipos de stop](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-15)

## 7. Tamaño, efectivo y concentración

`E` es patrimonio del entorno evaluado, con precios vigentes y sin contar dos veces CA histórico y paper. Para admitir una compra, utilizar el menor patrimonio entre plan y comprobación previa, y volver a medir posiciones/reservas. La cantidad previa sólo puede reducirse, nunca aumentar frente al plan nocturno. Si `E ≤0`, no hay compras.

| Límite base | Valor |
| --- | --- |
| Presupuesto por nueva posición | `0,004 * E`, modificado por el freno de capital. |
| Riesgo agregado hasta stops | `0,06 * E`, modificado por el freno. |
| Posiciones abiertas más símbolos con compras pendientes | 12, contando SPY y LLY. |
| Valor por instrumento | 12% de E. |
| Valor por sector GICS | 30% de E; todos los ETF diversificados juntos, 20%. |
| Exposición bruta | 90% de E, modificada por el freno; no usar margen. |
| Reserva de efectivo | Al menos 10% de E tras compras y su colchón de coste. |
| Participación por entrada | Hasta 1% de `ADV20(t)` en acciones enteras. |

El control sectorial no descompone las participaciones de ETF: por tanto no mide toda la concentración económica indirecta. Se presenta como límite por clasificación, sin afirmar diversificación completa.

`G` es valor marcado de posiciones; `P` es nominal de compras pendientes al precio límite. Para cada posición larga, riesgo abierto `q * max(mark-stop_activo, 0)`; para cada compra pendiente, `q * (entry_limit-initial_stop)`. No compensar riesgos positivos con stops en ganancia. Un stop desconocido, rechazado o sin confirmación bloquea nuevas compras. Un stop alcanzado inicia gestión de salida y también bloquea entradas hasta resolverla.

Con `L = entry_limit`, `S = initial_stop`, `r` presupuesto por operación, `g` límite bruto y `a` límite de riesgo total del estado de capital, calcular:

```text
q_risk   = floor(r*E / (L-S))
q_name   = floor((0,12*E - valor_activo - reservas_activo) / L)
q_sector = floor((limite_sector*E - valor_sector - reservas_sector) / L)
q_gross  = floor((g*E - G - P) / L)
q_cash   = floor((efectivo_gastable - reserva_compras - 0,10*E) / (1,001*L))
q_total  = floor((a*E - riesgo_abierto - riesgo_pendiente) / (L-S))
q_volume = floor(0,01 * ADV20(t))
q        = max(0, min(q_risk, q_name, q_sector, q_gross, q_cash, q_total, q_volume))
```

Efectivo gastable excluye préstamos, fondos restringidos y ventas no liquidadas. No usar `buying_power` apalancado como equivalente. `reserva_compras` incluye nominal y colchón de 0,10% para cada intención pendiente; el colchón es una propuesta contable, no una afirmación sobre comisiones. Redondear la reserva monetaria hacia arriba a centavos y revalidar; si se excede efectivo por redondeo, reducir una acción hasta cumplir. No reservar dos veces el mismo nominal.

Si cualquier cupo queda agotado, `q=0` y se registra el límite causante. Un aumento de precio posterior puede superar la concentración de admisión sin causar una venta inmediata: bloquea nuevas compras y se informa. Las reducciones obligatorias por frenos se rigen por la sección 9.

## 8. Salidas y protección de beneficios

Toda nueva posición mantiene el stop inicial y un objetivo fijo de **2R para la cantidad completa**. No hay salida parcial de beneficios en v1. «Dejar correr» significa permitir avance hasta ese objetivo o un stop ascendente; no supone ganancias ilimitadas.

Al cierre de cada sesión, `HC` es el mayor cierre observado desde la entrada, incluida su sesión. Si `HC ≥ entry_limit + R`, activar protección de beneficio:

```text
next_stop = floor_cent(max(stop_actual, entry_limit, HC - 2*ATR20(t)))
```

Antes de alcanzar +1R, conservar el stop actual. Nunca bajar un stop para evitar una salida. Aplicar el nivel nuevo al abrir la siguiente sesión, con la primera cotización válida y antes de cualquier nueva compra; no se utiliza retroactivamente dentro de la vela que lo calculó. Si el nivel deseado está a la altura o por encima del precio vigente al aplicar, se ordena salida de la cantidad restante mediante el controlador, manteniendo la protección previa hasta conciliar la sustitución. Si no hay cotización válida, mantener el stop previo y bloquear compras. El objetivo original no se eleva.

Se programa salida temporal después de **20 sesiones completas posteriores a la sesión de entrada**, en la apertura +5 minutos de la sesión siguiente. Es decir, entrada en sesión 0, mantenimiento hasta cerrar sesión 20, salida temporal en sesión 21. Un stop u objetivo ejecutado antes elimina esa salida pendiente. No se requiere vender porque la puntuación baje o falle el filtro de mercado.

Prioridad: conciliación/seguridad → stop o salida ya ejecutados → freno de capital → cierre temporal → actualización de stop → nueva entrada. Un halt o falta de liquidez puede impedir cerrar; se conserva la intención, se informa y no se abren nuevas posiciones.

## 9. Frenos de capital y recuperación

Medir caída desde máximo en una serie **unitizada del piloto**, sin ganancias históricas previas ni aportes tratados como retorno. En el inicio, `NAV_unit=100`, `unidades=E0/100`. Una aportación externa ΔC cambia unidades por `ΔC/NAV_unit_previo`, usando valoración inmediatamente anterior al flujo. Comisiones, pérdidas y dividendos son resultados, no emisiones de unidades. Un flujo sin valoración y hora fiables bloquea nuevas compras hasta conciliar.

`NAV_unit=patrimonio/unidades`, `HWM=max(NAV_unit desde inicio)` y `D=max(0,1-NAV_unit/HWM)`. Evaluar tras cada actualización conciliada de la cartera y, como mínimo durante sesión, cada minuto. Si falta un precio de posición o tiene más de 60 segundos, no afirmar un D actualizado: bloquear entradas y conservar protección. Un cruce intradiario activa el freno; la recuperación requiere cierres posteriores. Fuera de sesión, la protección no garantiza ejecución.

| Caída D | Estado | Riesgo nuevo por operación | Tope bruto | Tope de riesgo total | Acción |
| --- | --- | --- | --- | --- | --- |
| `<5%` | Normal | 0,40% | 90% | 6% | Hasta dos entradas por sesión. |
| `≥5% y <9%` | Reducido | 0,20% | 60% | 3% | Hasta una entrada por sesión; reducir exposición si excede topes. |
| `≥9% y <13%` | Defensa | 0 | 40% | 2% | Cancelar entradas y reducir hasta topes. |
| `≥13% y <15%` | Preservación | 0 | 20% | 1% | Cancelar entradas y reducir hasta topes. |
| `≥15%` | Detenido | 0 | 0 | 0 | Cancelar entradas, gestionar cierre de todas las posiciones y permanecer detenido. |

Los umbrales incluyen igualdad. Subir directamente al estado más severo alcanzado; no esperar a atravesar niveles uno por uno. El estado efectivo es el más severo entre el nivel que indica D y el estado aún retenido por las reglas de recuperación. La cantidad admitida de una orden pendiente se reserva hasta confirmar su cancelación. No cancelar indiscriminadamente órdenes de protección al activar el freno.

Aplicar reducción cuando se agrava un freno o cuando la exposición bruta/riesgo agregado conciliados exceden los topes del estado efectivo, incluso Normal. En sesión, iniciar al detectar el exceso; fuera de sesión, registrar la intención y gestionarla al abrir con datos válidos. Primero cancelar compras pendientes y conciliar. Con posiciones restantes y sin nuevas compras, `k=min(1, tope_bruto*E/G, tope_riesgo*E/R_abierto)`, omitiendo una división cuyo denominador sea cero. Objetivo de cantidad para cada posición `floor(q*k)`, salvo Detenido, donde es cero. Vender la diferencia por identificador ascendente, con un único controlador. Recalcular con fills/precios reales hasta cumplir; no asumir que un envío equivale a una venta. Si falta un stop, no calcular k como si el riesgo fuese cero: bloquear y resolver la protección o salida de emergencia.

Los estados Reducido, Defensa y Preservación pueden bajar **sólo un nivel** tras cinco cierres consecutivos con D estrictamente por debajo de 4%, 8% y 12%, respectivamente. Un cierre que no cumple reinicia el contador. Tras bajar, reiniciar contador; cualquier agravamiento vuelve a aplicar inmediatamente el nivel más severo. HWM no se reinicia. Detenido nunca se rearma automáticamente: requiere una nueva versión revisada del piloto; el historial de pérdidas permanece.

## 10. SPY y LLY heredados

El registro histórico mantiene **134 SPY a coste guardado 661,23** y **51 LLY a 1.252,34**, junto con el efectivo CA. Ninguna regla del candidato modifica ese Excel ni implica órdenes sobre la cuenta del dueño.

Para evaluar la gestión heredada, anclar `P0` al precio observado al inicio de la simulación o al coste efectivo de inicialización paper, nunca al coste histórico para atribuir ganancias nuevas. Con datos vigentes, proponer `S0=floor_cent(P0-2*ATR20)` y `T0=ceil_cent(P0+2*(P0-S0))`. Exigir stop positivo, distancia entre 2% y 8% y riesgo por posición `q*(P0-S0) ≤0,004*E`, además de los topes agregados base. Si no cumple, el inicio se bloquea y se informa; no se cambia la cantidad acordada ni se usa margen para forzarlo.

Con inicialización admisible, ambas posiciones se marcan `inherited`, cuentan en los 12 puestos, concentración, efectivo y riesgo. Su apertura de inicialización no requiere S2 ni seis puntos. Se aplican stop, objetivo, trailing y salida temporal de v1 usando P0 como ancla; no se venden sólo por faltar una señal nueva. Las dos intenciones de inicialización consumen los dos cupos de esa sesión: nuevas señales, como pronto, en la siguiente.

La cuenta paper deberá estar dedicada y separada de la referencia CA. Sus costes y efectivo pueden diferir del Excel; se documenta la diferencia sin inventar fills. La documentación de paper describe limitaciones de ejecución y no simula dividendos; esos flujos, si se acreditan externamente, se presentan por separado y no se suman al efectivo gastable. [Alpaca Paper Trading](https://docs.alpaca.markets/us/docs/paper-trading)

## 11. Resultados de decisión y trazabilidad

Cada evaluación produce una decisión única: `reject`, `candidate`, `manage_existing` o `halt`. `candidate` es una propuesta de investigación; no es una orden. Guardar versión, sesión, datos disponibles, nueve puntos, condiciones de mercado/patrón, límites de precio, cantidad y todos los motivos de rechazo.

Orden de decisión: integridad de cartera/datos → freno → elegibilidad → mercado → patrón → puntuación → prioridad/cupos → tamaño → comprobación previa. Conservar todos los fallos detectados, con motivo principal el primero de esa secuencia. Fallos globales impiden nuevas compras pero no omiten la gestión de posiciones existentes. Un dato técnico obligatorio ausente produce rechazo, nunca un punto cero que permita continuar.

Motivos mínimos: `invalid_data`, `identity_unverified`, `portfolio_unreconciled`, `protection_failure`, `capital_brake`, `market_filter`, `pattern_failed`, `score_below_six`, `cooldown`, `position_exists`, `entry_quota`, `size_zero`, `stale_quote`, `gap_outside_band`, `signal_expired`. En el catalizador opcional usar los motivos específicos de la sección 5.

El identificador de intención se deriva de versión de método, revisión de plan, sesión, identificador estable y finalidad (`entry`, `initialization`, `exit`, `protection`). El ejecutor futuro debe persistir la intención antes de enviarla y consultar su estado antes de repetir. Los eventos de broker y los cambios de stop quedan ligados a esa intención. La IA puede explicar; no modifica parámetros ni ordena operaciones.

## 12. Criterio de fase 2 y paso a evaluación

Esta fase termina con las reglas anteriores y los [ejemplos calculados](ca-method-v1-examples.md), revisados para coherencia. Completar la especificación no acredita que el dueño haya confirmado las propuestas P. El documento puede usarse para construir una simulación aislada; activar paper sigue requiriendo completar los controles de las fases 3 y 4.

Antes de observar resultados, congelar versión, universo, costes y ventanas. El historial CA se usa de forma exploratoria: seleccionar activos porque se operaron introduce sesgo, y las 125 filas no son 125 decisiones independientes. No calibrar para hacer que esas filas parezcan buenas señales.

Para la primera evaluación, usar costes hipotéticos explícitos: 0,005 USD por acción con mínimo 1 USD por orden ejecutada, más 5 puntos básicos de deslizamiento adverso por lado; escenario de estrés con el doble de comisión y 20 puntos básicos por lado. No se atribuyen esas tarifas a Alpaca. Las ejecuciones límite nunca se simulan por encima del límite de compra; si precio más deslizamiento excede el límite, no hay fill. Las ventas por stop sí admiten precios peores. Tratar stops/objetivos ambiguos dentro de una misma vela de forma adversa y documentar la resolución; no usar el máximo diario para subir retroactivamente el stop.

La ventana de entrada requiere datos intradiarios y cotizaciones verificables. Si sólo hay velas diarias, se puede estudiar el filtro, pero no afirmar que se ha simulado el método completo. La integración paper no sustituye una validación histórica y ninguna de ellas garantiza resultados reales.

| Comprobación de fase 3 | Criterio fijado antes de evaluar |
| --- | --- |
| Correctitud | Cero decisiones con información futura; cero compras violando límites al admitirlas; ninguna orden duplicada en pruebas de reintento. |
| Contabilidad | Todas las posiciones, reservas, fills, costes y flujos reconstruibles; contribuciones excluidas de retorno. |
| Casos adversos | Huecos, stop y objetivo en la misma vela, datos ausentes, splits, fill parcial, desconexión y reinicio tienen resultado documentado. |
| Evaluación temporal | Separar período de preparación y período temporal de evaluación; revelar que el universo fue seleccionado usando el historial. No etiquetarlo como prueba independiente intacta. |
| Prueba prospectiva | Congelar la versión antes del primer día observado. Evaluar 60 sesiones completas; si hay menos de 20 ciclos de entrada-salida cerrados de nuevas señales, ampliar hasta 120 sesiones. Contar un ciclo por intención original; no contar fills parciales ni inicializaciones heredadas como ciclos nuevos. Si siguen faltando, resultado inconcluso. El conteo no demuestra independencia estadística entre activos o fechas. |
| Hipótesis de rendimiento | Candidato favorable sólo si PnL neto es positivo y drawdown unitizado menor de 9% en la prueba prospectiva, con los criterios técnicos cumplidos. De lo contrario, rechazar o reformular con nueva versión. Reportar también benchmark SPY comparable y escenario de estrés, aunque sean desfavorables. |

Esos umbrales son criterios de investigación propuestos, no promesas ni demostración estadística de ventaja. No modificar esta versión después de ver el período de evaluación para seguir llamándolo fuera de muestra. La meta del video para 2027 no es un criterio que obligue a fabricar un resultado.

## 13. Revisión y límites de esta entrega

La puntuación, catalizador, activación, vencimiento, tamaño, salidas, frenos y política heredada quedan definidos. El [calculador de ejemplos](../../examples/ca_method_v1.py) comprueba aritmética con datos explícitos; no implementa estas trece secciones ni valida señales reales. No se ha conectado un proveedor de datos ni verificado la elegibilidad de las 72 etiquetas, los ATR actuales, el efectivo real o los lotes del dueño.

Una respuesta del dueño puede cambiar las propuestas P; ese cambio crea `CA-S2-1.1.0` u otra versión identificable antes de una evaluación nueva. Mientras no exista esa confirmación, el título y el estado permanecen como **método candidato**. Los números de los ejemplos son didácticos y no instrucciones de compra o venta.

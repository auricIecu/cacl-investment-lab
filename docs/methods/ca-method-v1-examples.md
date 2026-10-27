# Ejemplos calculados del método CA v1

**Método:** [CA-S2-1.0.0](ca-method-v1.md). Estos ejemplos comprueban fórmulas y límites; no son señales actuales, recomendaciones ni un backtest. Los ATR y escenarios de mercado son sintéticos. Sólo los saldos iniciales CA y las cifras del ejemplo del video proceden de las fuentes.

Reproducir desde la raíz del repositorio:

```bash
.venv/bin/python examples/ca_method_v1.py
```

El script usa Decimal y assertions con resultados esperados. Imprime JSON; falla si una comprobación aritmética no se cumple. No importa el Excel ni accede al broker. El resultado de esta entrega queda en `.context/phase2/ca-method-v1-examples.json`.

## 1. Riesgo y puntuación

| Caso | Cálculo | Resultado |
| --- | --- | --- |
| Ejemplo del video | `floor(4.000 / 10,72)` | 373 acciones; riesgo hasta stop 3.998,56 USD. La diferencia no gastada es 1,44 USD. |
| Usar patrimonio CA, no el nominal de un millón | `0,004 × 977.698,96890463` | Presupuesto 3.910,79587561852 USD. |
| Misma distancia de 10,72 con presupuesto CA | `floor(3.910,79587561852 / 10,72)` | 364 acciones, riesgo 3.902,08 USD. 365 arriesgarían 3.912,80 y excederían el presupuesto. Es cantidad **sólo por riesgo**, no una orden admitida. |
| Vector mostrado en el video | `[1,1,1,1,1,0,1,1,0]` | 7/9. Falta el punto de extensión y el catalizador. |
| Sin catalizador, seis puntos técnicos | `[1,1,1,1,1,0,1,0,0]` | 6/9; puede ser candidato si pasan todas las otras condiciones. |

Con EPS previo 1,00 y actual 1,20, crecimiento 20%; ventas previas 100 y actuales 110, crecimiento 10%. El punto de catalizador se gana **sólo** si también son trimestrales comparables, positivos los denominadores y válidas las fuentes/fechas. EPS actual 1,199 queda por debajo del umbral. Sin documento acreditado, el punto sigue en cero aunque alguien afirme esas cifras.

Un 7/9 con mercado rechazado produce `reject`. Un 6/9 con un indicador técnico ausente produce `invalid_data`. La puntuación por sí sola no habilita una compra; estas dos decisiones pertenecen al contrato de la especificación y no a un motor implementado en el calculador.

## 2. Niveles, cantidad y límites

Con cierre sintético 100,00, ATR20=2,00 y mínimo de cinco sesiones=98,00:

```text
Límite = ceil_cent(100 × 1,005) = 100,50
Stop = floor_cent(min(98 − 0,10 × 2, 100 − 2 × 2)) = 96,00
R = 4,50
Objetivo = 100,50 + 2 × 4,50 = 109,50
```

Para aislar el dimensionamiento, los casos siguientes usan **otro** plan sintético: patrimonio 100.000, límite 100, stop 95, sin compras pendientes y estado Normal. La cantidad se calcula como el mínimo de los siete límites, sin sustituir las comprobaciones de mercado y datos.

| Caso | Datos que limitan | Cantidad | Resultado relevante |
| --- | --- | ---: | --- |
| Base | Efectivo 83.150; posiciones 16.850; riesgo abierto 500; sector vacío; ADV20=100.000 | 80 | Riesgo 400; reserva de compra 8.008; efectivo restante 75.142. |
| Reserva de efectivo | Efectivo 10.800; posiciones 89.200; resto igual | 7 | 8 acciones requerirían 800,80 y romperían la reserva de 10.000. Con 7 quedan 10.099,30. |
| Sector lleno | Sector 29.950; posiciones 50.000; efectivo 50.000 | 0 | Sólo caben 50 USD antes del 30%, insuficientes para una acción de 100. |
| Riesgo agregado | Riesgo abierto 5.996 | 0 | Restan 4 USD hasta 6.000; cada acción nueva consume 5 USD. |
| Participación de volumen | ADV20=2.500 | 25 | Límite de 1% del volumen medio, aunque el presupuesto permita 80. |

En el caso base, los siete máximos son: riesgo 80, instrumento 120, sector 300, bruto 731, efectivo 730, riesgo total 1.100 y volumen 1.000. El límite efectivo es 80.

## 3. Huecos y salidas

Para una banda de entrada `[99, 100]`, los ask 99 y 100 cumplen la banda; 98,99 y 100,01 la incumplen. Cotización antigua, spread excesivo o señal vencida igualmente rechazan, aunque el ask caiga dentro. El límite aceptado puede quedarse sin fill.

Con entrada límite 100 y stop 95, `R=5` y objetivo fijo 110:

| Evolución sintética al cierre | ATR20 | Stop siguiente |
| --- | ---: | ---: |
| Mayor cierre desde entrada =106 | 3 | `max(95,100,106−6)=100` |
| Mayor cierre sube a109 | 2 | `max(100,100,109−4)=105` |
| Cierre cae a108; el mayor cierre sigue en109 | 3 | `max(105,100,109−6)=105`; no se reduce. |

Estos niveles sólo actúan después del cierre que permite calcularlos. Si 80 acciones compradas a 100 salen por un hueco a 90, la pérdida bruta es **800 USD**, frente a 400 presupuestados hasta el stop de 95. Las comisiones aumentarían la pérdida: el stop no garantiza el riesgo presupuestado.

## 4. Frenos y aportes

| Caída desde máximo unitizado | Clasificación inicial |
| --- | --- |
| 4,99% | Normal |
| 5,00% y 8,99% | Reducido |
| 9,00% y 12,99% | Defensa |
| 13,00% y 14,99% | Preservación |
| 15,00% | Detenido |

Esta tabla muestra activación. La recuperación tiene memoria: no vuelve a Normal simplemente porque la caída pase de 5% a 4,99%. Requiere cinco cierres estrictamente por debajo de 4%. Si ya está en Defensa, necesita cinco cierres por debajo de 8% para bajar sólo a Reducido; luego comienza otro contador. Los contadores son requisitos para fase 3, no funcionalidad ya probada por el calculador.

Ejemplo de reducción: patrimonio 100.000, posiciones valoradas en 80.000 y riesgo abierto 4.000, con caída 10%. Defensa exige bruto ≤40.000 y riesgo ≤2.000. `k=min(1,40.000/80.000,2.000/4.000)=0,5`. Con dos posiciones de 100 y 200 acciones, los objetivos son 50 y 100. Se trata de cantidades objetivo; sólo los fills conciliados prueban la reducción.

Ejemplo de aporte: patrimonio inicial 100.000 y NAV por unidad 100 → 1.000 unidades. Aportar 20.000 al mismo NAV emite 200 unidades; patrimonio 120.000 / 1.200 unidades mantiene NAV 100. No hay ganancia 20%. Si después el patrimonio cae a 114.000, NAV 95 implica caída 5%, activando Reducido.

## 5. Posiciones heredadas

Para ilustrar la fórmula, se usan los precios **guardados** en el Excel como anclas hipotéticas. ATR20 de SPY=10 y de LLY=30 son cifras inventadas; no son indicadores calculados ni niveles para enviar al mercado.

| Activo | Cantidad | Ancla hipotética | ATR inventado | Stop calculado | Objetivo 2R | Riesgo hasta stop |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 134 | 769,71 | 10 | 749,71 | 809,71 | 2.680 |
| LLY | 51 | 1.281,72 | 30 | 1.221,72 | 1.401,72 | 3.060 |

Riesgo agregado hipotético: 5.740 USD. Ambos riesgos individuales están por debajo del presupuesto CA de 3.910,79587561852. Esto sólo demuestra el ejemplo; la inicialización real exige ATR, precios, efectivo, disponibilidad y protección vigentes.

Los costes históricos 661,23 y 1.252,34 permanecen en la referencia CA. No se usan para adjudicar a la estrategia las ganancias que existían antes de iniciar el piloto.

## Qué queda verificado

Los ejemplos comprueban aritmética de riesgo, nueve puntos, umbrales del catalizador, redondeo de niveles, siete límites de cantidad, banda de entrada, stops que no retroceden, riesgo de huecos, activación de frenos, reducción proporcional, aportes y fórmulas heredadas.

No verifican cálculo de indicadores con datos de mercado, calidad del universo, reglas temporales completas, recuperación de frenos, órdenes, fills, rendimiento ni la interpretación del dueño. Eso pertenece a la implementación y evaluación posteriores.

# CONTEXT — relevo de CACL Investment Lab

Actualizado: **16 de noviembre de 2026**. Este archivo permite continuar el proyecto sin el historial del chat. Para un agente nuevo: leer este documento, el README y los documentos enlazados antes de modificar reglas o implementar la conexión.

## Estado en una lectura

Se construye un laboratorio de inversión limitado a **Cartera CA**, basado en un video explicativo y un Excel del dueño. Existen importador, conciliación, reglas candidatas y simulador local. **No existe conexión a Alpaca, ejecutor de órdenes ni rentabilidad validada.**

La entrega técnica de fase 3 terminó: el programa funciona con escenarios sintéticos y produce un diagnóstico explícito cuando faltan datos. La evaluación con mercado real sigue pendiente. El usuario confirmó que no dispone de históricos; pidió preparar el simulador y documentar exactamente lo que falta.

Últimas decisiones del usuario:

- Está por crear una cuenta **Alpaca Paper**; no confirmó todavía que esté lista.
- Presupuesto para datos y servicios: **USD 0**.
- El sistema se ejecutará en **esta Mac**, sin alojamiento de pago.
- Se preparó un archivo local para credenciales; no se ha probado su acceso ni confirmado su configuración. No leer ni imprimir sus valores para un simple diagnóstico de estado.

**Siguiente tarea concreta:** una vez disponibles las credenciales, implementar y probar una comprobación de sólo lectura de cuenta paper, instrumentos y una muestra histórica de SPY/LLY. El cliente/adaptador para hacerlo todavía no existe. Determinar permisos efectivos antes de prometer cobertura o descargar todo el universo.

## Alcance y acuerdos que deben mantenerse

- Sólo CA: sus posiciones, operaciones y etiquetas de activos. No incluir CL, PYPL_BABA, bonos ni un screener de miles de empresas.
- Sólo investigación y futura ejecución con dinero ficticio. No trading real, margen, posiciones cortas ni suscripciones pagadas.
- Estado histórico de referencia: **134 SPY, 51 LLY y USD 809.190,10890463 en efectivo calculado**. Son valores del Excel, no saldos actuales del broker.
- El historial no se reenvía como órdenes. La eventual inicialización paper se conciliará por separado; no se suman patrimonio histórico y paper.
- Las fuentes no especifican todas las reglas. El usuario autorizó **proponer un método completo para probar, identificando supuestos**. No atribuir esas propuestas al dueño ni tratarlas como su confirmación.
- Reglas y dinero se calculan mediante código determinista (`Decimal`). La IA ayuda a investigar y explicar, no decide libremente operaciones ni modifica parámetros durante una sesión.
- Preferencia de trabajo: español, respuestas claras y breves, cambios mínimos, ejecución inline y sin confirmaciones repetidas para trabajo ya autorizado. No contratar servicios ni habilitar un piloto por inferencia de esta autorización.
- No renombrar la rama de Conductor salvo petición expresa. No se necesita otro worktree para continuar aquí.

## Fases

| Fase | Entrega y estado | Pendiente |
| --- | --- | --- |
| 1. Reconstruir CA | Importación repetible, SQLite, archivo original conservado, informe de conciliación. | Resolver incidencias con extractos/comprobantes del dueño; no hay conciliación con Schwab. |
| 2. Definir método | Reglamento candidato `CA-S2-1.0.0` y ejemplos aritméticos verificables. | Confirmación o correcciones del dueño, si las aporta; cualquier cambio requiere nueva versión. |
| 3. Evaluar reglas | Simulador por eventos, pruebas adversas, informes reproducibles y contrato de datos. Goal de implementación cerrado. | Históricos reales, manifiesto acreditado y evaluación de mercado. Resultado actual: `data_insufficient`; pruebas ficticias: `synthetic_only`. |
| 4. Validar paper | Documentada la preparación gratuita. | Cliente Alpaca, cuenta conciliada, órdenes, protección, parciales, recuperación y controles de acceso. No iniciada la conexión. |
| 5. Operar y revisar | Criterios de evaluación escritos. | Rutina en la Mac, informes y observación prospectiva de 60–120 sesiones. No se sustituye tiempo observado por datos sintéticos. |

## Evidencia de origen y conciliación

Los archivos originales están **sólo en el workspace**, excluidos de Git:

| Archivo | Ruta local relativa |
| --- | --- |
| Video de 135,9 segundos | `.context/attachments/WQINif/CACL_InvestmentLab_v2.mp4` |
| Excel de referencia | `.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx` |
| Captura con aclaración del dueño | `.context/attachments/Z89qAr/image.png` |
| Fotogramas/transcripción e informe del video | `.context/video-analysis/` y `.context/video-analysis-report.txt` |

SHA-256 del Excel: `bc6eb1e91cad2659a1892a14bc18bf3b4c1be528434cc0bf3683b07de20dc041`.

El dueño aclaró que hay información a la derecha de las tablas principales y que `Dividend Payments` mezcla carteras. Se inventariaron los paneles laterales; sus resúmenes no se cuentan otra vez como operaciones. Se extrae exclusivamente el bloque CA de flujos.

Resultado del adjunto: 125 filas cerradas, 45 flujos CA y 72 etiquetas de activos. Posiciones con precios guardados: USD 168.508,86; patrimonio calculado: USD 977.698,96890463. El neto de flujos CA es USD 1.833,60 e incluye retenciones y ajustes, no sólo dividendos. La fecha de referencia es 2026-10-27, sin hora de cotización acreditada.

El estado es **`review_required`**, aunque cuadren los importes. Persisten rangos/gráficos incompletos en `History_CA`, un rótulo de 106 frente a 125 filas, diferencias de fechas/bases de rendimiento y necesidad de verificar lotes, ajustes y aportes. Las fórmulas se conservan pero no se ejecutan. Métricas avanzadas guardadas en Excel no están certificadas. Ver [README](README.md) y [diseño general](docs/superpowers/specs/2026-10-27-cacl-ca-paper-design.md).

## Método y límites del simulador

La fuente normativa es [ca-method-v1.md](docs/methods/ca-method-v1.md), no este resumen. Versiona qué viene del video/Excel y qué es propuesto. Incluye filtro SPY/VIX/amplitud, patrón de ruptura S2, puntuación mínima 6/9, catalizador basado en hechos trimestrales, entradas a apertura +5 minutos y vencimiento a +30.

Define riesgo base 0,40% por entrada, hasta 12 posiciones y dos intenciones diarias, riesgo agregado 6%, reservas de efectivo, concentración y frenos en caídas de 5/9/13/15%. Hay política explícita para SPY/LLY heredados, stops, objetivo, trailing, salida temporal y recuperación. Consultar las fórmulas exactas antes de implementar o cambiar algo.

El simulador usa calendario explícito, datos conocidos a cada corte, liquidación T+1, splits/dividendos y aportes unitizados. Conserva planes, hashes, rechazos, fills hipotéticos y estado recuperable. Costes base: USD 0,005 por acción con mínimo USD 1 por orden y 5 pb de deslizamiento por lado; estrés: comisión doble y 20 pb. Son supuestos de investigación, no tarifas verificadas del broker.

Límites que no deben ocultarse:

- El ejemplo usa 22 etiquetas CA y cuatro sesiones evaluadas con precios, sectores y calendario **ficticios**. No valida las 72 etiquetas reales.
- La apertura del replay traslada cantidades/efectivo del snapshot a precios del escenario. No reproduce las decisiones históricas del dueño.
- No se simulan fielmente colas de órdenes, impacto, latencias ni todas las carreras de cancelación de un broker. Una desconexión con órdenes pendientes deja incertidumbre explícita.
- Datos ausentes u obsoletos pueden bloquear métricas; no sustituirlos por cero ni rellenar precios para fabricar cobertura.
- El benchmark SPY conserva aportes en efectivo; un retiro que no puede financiar con su efectivo deja su comparación no disponible.
- El universo seleccionado desde operaciones pasadas introduce sesgo. Un replay histórico es exploratorio.
- Todos los informes mantienen `performance_validation: not_established` y `ready_for_paper: false`. Código de salida 0 no significa estrategia aprobada.

## Mapa del repositorio

| Ruta | Responsabilidad |
| --- | --- |
| `cacl_ca/workbook.py` | Leer/inventariar Excel y extraer únicamente CA con procedencia. |
| `cacl_ca/reconcile.py` | Conciliar importes y registrar incidencias. |
| `cacl_ca/storage.py` | Revisiones SQLite, copia original y escritura de artefactos. |
| `cacl_ca/market_data.py` | Validar paquete local, seleccionar historia por disponibilidad y calcular hashes. |
| `cacl_ca/strategy.py` | Indicadores, puntuación, filtros y planes candidatos. |
| `cacl_ca/portfolio.py` | Contabilidad simulada, reservas, límites, frenos y estado. |
| `cacl_ca/simulation.py` | Replay por eventos, ejecuciones hipotéticas y escenarios adversos. |
| `cacl_ca/evaluation.py` | Auditoría de datos, corridas base/estrés e informes JSON/Markdown. |
| `cacl_ca/__main__.py` | CLI: únicamente `import` y `evaluate`. |
| `examples/ca_method_v1.py` | Ejemplos aritméticos de fase 2 con assertions. |
| `examples/phase3_synthetic.py` | Generador del paquete ficticio para pruebas. |
| `tests/` | Pruebas de importación, conciliación, almacenamiento, estrategia, riesgo, simulación y CLI. |

Python 3.11 o posterior; usado en este workspace con 3.14. Dependencia de proyecto: `openpyxl==3.1.5`. Sin frontend, servicios desplegados, scheduler ni integración financiera externa. Las skills/plugins se investigaron como apoyos; no son una dependencia de ejecución ni se instalaron conectores Alpaca como parte de estas fases.

## Continuar desde otro equipo o agente

Repositorio: `https://github.com/auricIecu/cacl-investment-lab.git`.
Rama de trabajo: `dev/eric-cacl`. Base: `origin/master`; no confundir el estado de esta rama con master.

```bash
git clone --branch dev/eric-cacl https://github.com/auricIecu/cacl-investment-lab.git
cd cacl-investment-lab
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python examples/ca_method_v1.py
.venv/bin/python -m unittest tests.test_strategy tests.test_portfolio tests.test_simulation -v
```

Estas últimas pruebas funcionan sin el Excel ni credenciales. Para la suite completa y el CLI de evaluación hace falta la fixture privada. **Clonar no descarga `.context/`, la base, adjuntos, informes privados ni claves.** Pedir el Excel original al dueño por un canal privado y definir su ruta; no subirlo a Git para resolver un fallo de pruebas.

```bash
export CA_WORKBOOK='/ruta/privada/Trade_Entry_Plans_Live (4).xlsx'
.venv/bin/python -m cacl_ca import "$CA_WORKBOOK"
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m cacl_ca evaluate
```

La última orden devuelve **2** y un informe `data_insufficient` si no se aporta mercado: es el resultado esperado. La importación con `review_required` devuelve 0 conservando incidencias. Error de lectura/paquete devuelve 1.

```bash
mkdir -p .context/phase3
.venv/bin/python examples/phase3_synthetic.py > .context/phase3/synthetic-market.json
.venv/bin/python -m cacl_ca evaluate --dataset .context/phase3/synthetic-market.json
```

Esto devuelve `synthetic_only` y código 0; no demuestra rentabilidad. La evaluación usa por defecto la última revisión. Aquí existe una revisión 2 con formato de importación 2; **una base recién creada puede tener revisión 1 con ese mismo formato**. No copiar `--revision 2` sin comprobar la base.

La suite completa se volvió a ejecutar el **16 de noviembre de 2026: 80 pruebas aprobadas**. Los tests financieros requieren `CA_WORKBOOK`; no se omiten silenciosamente si falta la fixture. Al entregar fase 3, las evaluaciones repetidas produjeron contenido idéntico, sin alterar Excel ni SQLite. Durante este relevo se verificaron además enlaces locales y ausencia de adjuntos, base y credenciales en el historial a publicar; no se probó acceso a Alpaca.

## Artefactos locales y credenciales

- `.context/ca/ca.sqlite3`: revisiones de importación; `sources/` conserva originales por SHA y `reports/` los informes. Se puede reconstruir importando el Excel.
- `.context/phase3/verification.json`: evidencia local de repetibilidad, hashes y rutas de los informes. Los reportes `evaluation-<hash>.json/.md` incluyen datos privados y no viajan con Git.
- `.context/alpaca/paper-credentials.json`: plantilla con `api_key` y `api_secret`, creada con permisos 0600. No incluir valores en documentación, salida de herramientas, capturas, chat ni commits. El CLI actual **no carga ese archivo**.
- `.context/`, `.venv/`, `__pycache__/` y `*.pyc` están ignorados. No usar `git add -f` para incluirlos. Compartir la evidencia privada por separado y recrear la configuración de acceso local cuando corresponda.

## Datos gratuitos y próximo trabajo, en orden

1. Confirmar que la cuenta paper y las credenciales locales están listas. Usar host paper fijo `https://paper-api.alpaca.markets` y datos `https://data.alpaca.markets`; nunca un fallback de órdenes a live. Implementar primero sólo lectura con errores y logs que no revelen secretos.
2. Comprobar permisos reales con una muestra pequeña de barras y bid/ask históricos SPY/LLY. La investigación documental previa indicó históricos SIP con `end` al menos 15 minutos antiguo y tiempo real gratuito IEX; la página Paper Only describe permisos IEX. **Esto no es una prueba autenticada ni garantía actual de cobertura.** Revalidar documentación y cuenta antes de implementarlo.
3. Verificar las 72 identidades y elegibilidad; obtener calendario, 254 sesiones de calentamiento más evaluación, OHLCV consolidado, VIX, quotes, trayectoria intradiaria y acciones corporativas. Acreditar procedencia/fechas; resultados trimestrales opcionales para el noveno punto. El contrato exacto está en [ca-evaluation-data.md](docs/methods/ca-evaluation-data.md).
4. Construir el adaptador mínimo al paquete JSON, repetir la evaluación y conservar carencias. No inventar datos, contratar una suscripción ni sustituir SIP por IEX sin explicitar una variante del método. El acceso histórico retrasado no resuelve por sí mismo el requisito de cotizaciones recientes del piloto.
5. Preparar fase 4: diseño, pruebas y conexión paper con conciliación, inicialización, protección, parciales, idempotencia y recuperación. No activar un piloto sin haber comprobado estos controles.
6. Preparar la rutina en esta Mac cuando exista ejecutor verificado. Debe permanecer despierta y conectada durante las sesiones; aún no se ha cambiado energía ni instalado inicio automático. Usar calendario `America/New_York`, no horarios fijos de Madrid/Ecuador.

El reglamento ya fija evaluación prospectiva de 60 sesiones, ampliable a 120 si faltan 20 ciclos nuevos cerrados. No se ha observado ese período. Cambiar parámetros después de ver resultados requiere otra versión y otra evaluación.

## Documentación y commits de referencia

Orden recomendado de lectura: [README](README.md), [diseño general y cinco fases](docs/superpowers/specs/2026-10-27-cacl-ca-paper-design.md), [reglamento candidato](docs/methods/ca-method-v1.md), [ejemplos](docs/methods/ca-method-v1-examples.md), [contrato de evaluación](docs/methods/ca-evaluation-data.md), [arranque gratuito](docs/methods/ca-zero-budget-setup.md). Los planes detallados y evidencia de entrega están en `docs/superpowers/plans/`; el diseño del simulador está en [ca-evaluation-design](docs/superpowers/specs/2026-10-27-ca-evaluation-design.md).

| Commit | Hito |
| --- | --- |
| `ebd9841` | Persistencia de revisiones CA e informes, tras extracción y conciliación. |
| `51a0e27` | Método candidato de fase 2 y ejemplos verificados. |
| `0950b45` | Registro de la autorización para proponer reglas con supuestos explícitos. |
| `88931bb` | Simulador y auditoría de datos de fase 3. |
| `4e21885` | Preparación de cuenta paper con USD 0 en esta Mac. |

Actualizar este archivo cuando cambien permisos verificados, datos disponibles, estado de fases, comandos o limitaciones. El siguiente agente debe partir de este estado, sin reconstruir las fases ya entregadas ni asumir que preparar credenciales equivale a tener integración.

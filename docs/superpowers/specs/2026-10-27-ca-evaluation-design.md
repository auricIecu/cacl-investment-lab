# Evaluación aislada de Cartera CA

La fase 3 implementa el método candidato [CA-S2-1.0.0](../../methods/ca-method-v1.md) sin acceso a brokers. El usuario autorizó implementarlo y continuar hasta terminar; se mantiene la ejecución inline y la rama de Conductor existente.

## Alcance y decisión técnica

Un simulador por eventos es necesario para representar la comprobación de apertura +5 minutos, reservas, stops, frenos y disponibilidad de datos. Un cálculo vectorizado diario no representa esas reglas. Una plataforma de trading completa añadiría infraestructura ajena al encargo. Se adopta Python estándar, Decimal y archivos locales normalizados; no se agrega dependencia ni se sustituye el método por reglas más fáciles de simular.

Las entradas son un snapshot CA ya importado y un paquete JSON con calendario explícito, manifiesto de instrumentos, velas diarias nominales, VIX, cotizaciones, velas intradiarias, hechos de resultados y acciones corporativas. Cada registro tiene procedencia y hora de disponibilidad. Se rechazan NaN, duplicados contradictorios, símbolos fuera de CA y marcas de tiempo sin zona. Los calendarios sintéticos sólo sirven para escenarios sintéticos.

La selección de datos para cada decisión usa únicamente lo disponible antes de su corte. La evaluación de precios intradiarios ocurre por orden de disponibilidad, y las ambigüedades de OHLC se resuelven adversamente. No se usa información futura para ajustar tamaño, stops o elegibilidad.

## Componentes

| Archivo | Responsabilidad |
| --- | --- |
| `cacl_ca/market_data.py` | Cargar, validar, identificar y seleccionar datos disponibles a cada fecha. |
| `cacl_ca/strategy.py` | Indicadores, filtro de mercado, S2, nueve puntos y planes inmutables. |
| `cacl_ca/portfolio.py` | Efectivo, reservas, posiciones, lotes simulados, frenos, aportes y estado recuperable. |
| `cacl_ca/simulation.py` | Reloj de sesiones, eventos, fills hipotéticos, costes, gestión y métricas. |
| `cacl_ca/evaluation.py` | Auditoría de cobertura, corrida base/estrés e informes trazables. |
| `cacl_ca/__main__.py` | Añadir `evaluate`, preservando `import`. |

## Datos disponibles y límites

En el inicio de esta fase hay Excel, revisiones SQLite y video. No hay OHLCV por activo, VIX, manifiesto de elegibilidad ni histórico bid/ask conectado. No se encontraron credenciales de proveedores en el entorno del workspace. Se ha preguntado al usuario por una fuente o ruta local; la implementación no depende de su respuesta.

Sin paquete de mercado, `evaluate` produce un informe `data_insufficient` y una plantilla de los instrumentos CA por verificar. Con datos sintéticos, produce `synthetic_only`. Con históricos completos, produce evaluación exploratoria y costes base/estrés, sin afirmar una prueba prospectiva concluida. Los 60–120 días prospectivos del método no se inventan ni se sustituyen por 60 días sintéticos.

## Verificación

Pruebas de decisiones con expectativas calculadas por separado: exclusión de datos posteriores, ventanas de 254 sesiones, puntuación, umbrales, huecos, efectivo y siete límites; posiciones heredadas, stop que no retrocede, cierre temporal, frenos con recuperación, splits, dividendos, aportes, partial fills, protección fallida, desconexión y reinicio sin duplicación. El CLI debe fallar con entradas inválidas y producir el mismo contenido al repetir idénticos datos/código.

Los resultados hipotéticos del simulador no comprueban la mecánica real de Alpaca. Esa integración y sus restricciones siguen en fase 4. El criterio de rentabilidad permanece no establecido mientras falte la evidencia exigida por el método.

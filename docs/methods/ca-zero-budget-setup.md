# Arranque de CA con USD 0 y esta Mac

Decisiones del usuario: cuenta Alpaca en preparación, presupuesto mensual de datos **USD 0**, ejecución local en esta Mac. No contratar suscripciones ni alojamiento. El simulador de fase 3 está disponible; faltan datos reales e integración paper.

## Paso del usuario

1. Crear la cuenta y entrar al entorno **Paper Trading** de [Alpaca](https://app.alpaca.markets/).
2. Generar las claves API correspondientes a esa cuenta paper. Son distintas de las de una cuenta real. [Documentación paper](https://docs.alpaca.markets/us/docs/paper-trading).
3. Completar localmente `.context/alpaca/paper-credentials.json`: `api_key` y `api_secret`. La plantilla privada se crea con permisos de lectura/escritura sólo para el usuario y está excluida de Git. No pegar claves en el chat, capturas, documentación ni comandos del historial.
4. Avisar que el archivo está listo, sin enviar su contenido.

La plantilla sólo guarda la configuración pendiente. El CLI actual no la carga ni inicia una conexión por sí solo. Una clave configurada no demuestra que la cuenta permita consultar todos los datos necesarios.

## Acceso gratuito: comprobado en documentación, pendiente en la cuenta

| Recurso | Lo documentado | Consecuencia para CA |
| --- | --- | --- |
| Plan Basic | Gratis; acciones/ETF, datos históricos desde 2016, hasta 200 consultas históricas por minuto; tiempo real IEX. | La descarga deberá paginar y respetar los límites. La cobertura de cada activo se verifica individualmente. |
| Históricos SIP | La FAQ permite consultas sin suscripción si `end` es al menos 15 minutos anterior a la consulta. | Probar barras y bid/ask históricos con `feed=sip` explícito. No asumir acceso por el mero registro de la cuenta. |
| SIP reciente | Consultas de los últimos 15 minutos y endpoints SIP de último precio requieren suscripción. | El plan gratuito no proporciona por esta vía las cotizaciones SIP recientes exigidas por la comprobación a apertura +5 minutos. |
| Cuenta Paper Only | Su página específica describe permisos IEX. | Hay que contrastar los permisos efectivos de esta cuenta con la disponibilidad histórica descrita en la FAQ. |

Fuentes: [planes Market Data](https://docs.alpaca.markets/us/docs/about-market-data-api), [FAQ y diferencias SIP/IEX](https://docs.alpaca.markets/us/docs/market-data-faq), [Paper Only](https://docs.alpaca.markets/us/docs/paper-trading). Documentación consultada durante esta preparación; las respuestas autenticadas de la cuenta determinarán el acceso efectivo.

**IEX no reemplaza silenciosamente a SIP.** El método candidato usa volumen consolidado y datos recientes para sus decisiones. Consultar datos atrasados permite investigación histórica; no los convierte en cotizaciones actuales para operar. Un modo experimental basado en IEX necesitaría una versión diferenciada del método y no validaría la versión actual.

VIX, acciones corporativas completas, sectores e identidad histórica de los 72 activos siguen pendientes de fuente y verificación. No se afirma que la cuenta gratuita cubra ese conjunto. Los resultados trimestrales son opcionales y sin acreditación su punto vale cero. El [contrato de datos](ca-evaluation-data.md) conserva los requisitos exactos.

## Trabajo siguiente del proyecto

Con las credenciales locales disponibles, implementar una comprobación de sólo lectura contra el host paper fijo `https://paper-api.alpaca.markets` y los datos de `https://data.alpaca.markets`: cuenta, instrumentos y una muestra histórica pequeña de SPY/LLY. No imprimir credenciales ni incorporar respuestas privadas a Git. Registrar permisos y carencias antes de descargar el universo completo.

Después, construir el paquete histórico disponible y repetir la evaluación. La integración de órdenes paper es una etapa distinta, con conciliación, protección e idempotencia comprobadas. Mantener el límite de USD 0: una respuesta que requiera suscripción se registra como carencia, sin contratar un plan ni degradar el feed sin indicarlo.

## Uso de esta Mac

La primera etapa se ejecuta manualmente desde este workspace. Para observar el piloto durante sesiones de mercado, la Mac tendrá que permanecer encendida, despierta y conectada. No se ha instalado un servicio de inicio automático ni cambiado su configuración de energía. Esa automatización se prepara cuando exista un ejecutor paper verificado; guardar las claves ahora no activa operaciones.

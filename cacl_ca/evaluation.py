"""Reproducible evaluation artifacts and an honest audit when market data is absent."""

import html
import json
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path

from .market_data import METHOD_VERSION, fingerprint, load_dataset, number as D, implementation_hash
from .simulation import simulate
from .storage import atomic_write


ROOT=Path(__file__).resolve().parent.parent


def read_reference(db_path,revision=None):
    path=Path(db_path).resolve()
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        if revision is None:
            row=connection.execute('SELECT id, source_sha256, source_file, snapshot_json, report_json FROM imports ORDER BY id DESC LIMIT 1').fetchone()
        else:
            row=connection.execute('SELECT id, source_sha256, source_file, snapshot_json, report_json FROM imports WHERE id=?',(revision,)).fetchone()
    if row is None: raise ValueError('No existe la revisión CA solicitada')
    revision,source_hash,archive,snapshot,report=row
    snapshot,report=json.loads(snapshot),json.loads(report)
    if report['status'] not in ('reconciled','review_required') or snapshot['source_sha256']!=source_hash:
        raise ValueError('Revisión CA no admisible')
    expected=path.parent/'sources'/f'{source_hash}.xlsx'
    if (path.parent/archive).resolve()!=expected.resolve() or sha256(expected.read_bytes()).hexdigest()!=source_hash:
        raise ValueError('Archivo de referencia CA no coincide con su hash')
    return revision,snapshot,report


def evaluate(snapshot,source_report,data=None):
    symbols=[s['source_symbol'] for s in snapshot['symbols']]
    mapped={i['source_symbol']:i for i in data['instruments']} if data else {}
    universe=[dict(mapped[s],classification='provided_by_dataset') if s in mapped else
              {'source_symbol':s,'eligible':None,'classification':'unverified'} for s in symbols]
    gaps=[]
    if data is None:
        gaps=[{'code':code,'detail':detail} for code,detail in (
            ('instrument_manifest','Identidad, tipo, sector y elegibilidad fechados de las 72 etiquetas CA.'),
            ('official_calendar','Sesiones y horarios oficiales, incluidos festivos y cierres anticipados.'),
            ('daily_ohlcv','254 sesiones de calentamiento más evaluación; OHLCV nominal consolidado y disponibilidad temporal.'),
            ('vix','Cierre VIX de cada sesión con fuente y hora de disponibilidad.'),
            ('intraday_quotes','Bid/ask, tamaño disponible y timestamps; cotización reciente en apertura +5 minutos.'),
            ('intraday_path','Cotizaciones/velas intradiarias suficientes para stops, objetivos y marcas de cartera cada minuto.'),
            ('corporate_actions','Splits y dividendos con fechas efectivas y de pago; cobertura acreditada, incluso si no hay eventos.'),
            ('optional_catalyst','Resultados trimestrales comparables y fechados; sin acreditación no se obtiene el noveno punto.'),
        )]
    else:
        missing=[s for s in symbols if s not in mapped]
        if missing: gaps.append({'code':'incomplete_manifest','detail':f'{len(missing)} etiquetas CA sin clasificar en el paquete: '+', '.join(missing)})
        if data['kind']=='historical' and data.get('actions_complete') is not True:
            gaps.append({'code':'corporate_actions_coverage','detail':'No se acredita cobertura de acciones corporativas; el benchmark no se presenta como retorno total verificado.'})
    base=simulate(data,snapshot) if data else None
    stress=simulate(data,snapshot,stress=True) if data else None
    if data is None or any(r and r['status']=='data_insufficient' for r in (base,stress)):
        status='data_insufficient'
    elif data['kind']=='synthetic': status='synthetic_only'
    else: status='data_insufficient' if gaps else 'exploratory'
    report={'method_version':METHOD_VERSION,'method_hash':sha256((ROOT/'docs/methods/ca-method-v1.md').read_bytes()).hexdigest(),
            'implementation_hash':implementation_hash(),'source_sha256':snapshot['source_sha256'],
            'source_schema_version':snapshot['schema_version'],'source_status':source_report['status'],
            'status':status,'performance_validation':'not_established','ready_for_paper':False,
            'dataset_kind':data['kind'] if data else None,'dataset_hash':fingerprint(data) if data else None,
            'universe':universe,'gaps':gaps,'base':base,'stress':stress,
            'limits':[
                'CA-S2-1.0.0 es un método candidato; no se han optimizado parámetros con los resultados.',
                'Las pruebas sintéticas verifican comportamiento del programa, no rentabilidad de mercado.',
                'La cartera histórica inicial se traslada como referencia contrafactual al comienzo del replay; no reproduce decisiones históricas del dueño.',
                'El calendario y las afirmaciones de procedencia del paquete requieren comprobación contra sus fuentes.',
                'El modelo no reproduce cola de órdenes, impacto de mercado ni garantiza fills o stops de un broker.',
                'Una desconexión con órdenes pendientes deja riesgo de ejecución no observado; el escenario se informa y no acredita validación de ejecución.',
                'El benchmark simula SPY comprado al inicio con los mismos costes; sólo incorpora dividendos presentes en el paquete y no reinvierte aportes.',
                'Si un retiro no puede financiarse con efectivo del benchmark, su comparación se marca no disponible; no se inventa una venta de SPY.',
                'El período prospectivo de 60–120 sesiones no está completado ni se sustituye por este replay.',
            ]}
    report['run_id']=fingerprint(report)
    return report


def _text(value):
    return html.escape(str(value)).replace('|','\\|').replace('\n',' ')


def render_evaluation(report):
    lines=['# Evaluación de Cartera CA — fase 3','',
           f"**Estado: {report['status']}**. Método `{METHOD_VERSION}`.",'',
           '**Rentabilidad no validada. Avance a ejecución paper: no habilitado.**','']
    if report['dataset_kind']=='synthetic':
        lines+=['**DATOS SINTÉTICOS:** las cifras siguientes son resultados de un escenario ficticio para probar el programa. No son resultados históricos de CA.','']
    elif report['dataset_kind'] is None:
        lines+=['El archivo CA permite reconstruir saldos y operaciones, pero no contiene la serie OHLCV, VIX ni bid/ask necesarios. No se calcula un retorno ficticio ni se sustituye la ausencia de datos por cero.','']
    else:
        lines+=['Replay exploratorio con el paquete suministrado. Universo seleccionado desde operaciones históricas; no es una prueba prospectiva independiente.','']
    lines+=['## Trazabilidad','',f"- Corrida: `{report['run_id']}`.",
            f"- Original CA: `{report['source_sha256']}`; importación v{report['source_schema_version']}; estado `{report['source_status']}`.",
            f"- Método: `{report['method_hash']}`.",f"- Implementación: `{report['implementation_hash']}`.",
            f"- Paquete: `{report['dataset_hash'] or 'no proporcionado'}`.",'',
            '## Datos que requieren atención','']
    if report['gaps']:
        lines.extend(f"- **{g['code']}**: {_text(g['detail'])}" for g in report['gaps'])
    else: lines.append('El paquete cubre el manifiesto declarado; esto no acredita por sí solo su autenticidad ni una evaluación prospectiva.')
    if report['base'] and report['base']['metrics']:
        labels=[('initial_equity','Patrimonio inicial'),('final_equity','Patrimonio final'),('net_pnl','PnL neto'),
                ('unitized_return','Retorno unitizado'),('max_drawdown','Máxima caída unitizada'),('fees','Comisiones hipotéticas'),
                ('closed_new_cycles','Ciclos nuevos cerrados'),('completed_sessions','Sesiones observadas'),('benchmark_return','Retorno de referencia SPY')]
        lines+=['','## Resultados del replay','',
                'Base: comisión 0,005 USD por acción (mínimo 1 USD por orden), deslizamiento 5 pb por lado. Estrés: comisión doble y 20 pb. Son supuestos, no tarifas verificadas de Alpaca.','',
                '| Medida | Base | Estrés |','| --- | ---: | ---: |']
        for key,label in labels:
            values=[]
            for result in (report['base'],report['stress']):
                value=result['metrics'][key] if result and result['metrics'] else None
                if value is None: rendered='No disponible'
                elif key in ('unitized_return','max_drawdown','benchmark_return'): rendered=f'{D(value)*100:.4f}%'
                elif key in ('closed_new_cycles','completed_sessions'): rendered=str(value)
                else: rendered=f'{D(value):,.2f}'
                values.append(rendered)
            lines.append(f"| {label} | {' | '.join(values)} |")
    lines+=['','## Incidencias del simulador','']
    for label in ('base','stress'):
        result=report[label]
        if result:
            lines.append(f"{label}: {len(result['issues'])} incidencias; estado `{result['status']}`.")
            lines.extend(f"- {_text(i['code'])}: {_text(i.get('symbol') or 'cartera')} · {_text(i.get('session'))}" for i in result['issues'])
    if report['base'] is None: lines.append('No se inició replay de mercado por ausencia de datos.')
    lines+=['','## Qué contiene el archivo JSON','',
            'Decisiones nocturnas y motivos de rechazo, planes con hashes de entradas, reservas, fills hipotéticos, costes, posiciones finales y curva de patrimonio. Repetir los mismos datos y código produce la misma corrida.','',
            '## Límites y siguiente paso','']
    lines.extend('- '+_text(v) for v in report['limits'])
    lines+=['','Siguiente paso: completar el paquete descrito en `docs/methods/ca-evaluation-data.md` y repetir la evaluación. No enviar claves por chat ni incorporar datos privados a Git.','']
    return '\n'.join(lines)


def run_evaluation(db_path,revision,dataset_path,output_dir):
    revision,snapshot,source_report=read_reference(db_path,revision)
    data=load_dataset(dataset_path,[s['source_symbol'] for s in snapshot['symbols']]) if dataset_path else None
    report=evaluate(snapshot,source_report,data)
    destination=Path(output_dir)
    stem=f"evaluation-{report['run_id']}"
    atomic_write(destination/f'{stem}.json',json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode(),replace=False)
    atomic_write(destination/f'{stem}.md',render_evaluation(report).encode(),replace=False)
    atomic_write(destination/f"universe-{report['run_id']}.json",json.dumps(report['universe'],ensure_ascii=False,sort_keys=True,indent=2).encode(),replace=False)
    print(f"Estado: {report['status']}. Rentabilidad: no validada. Revisión CA: {revision}.")
    print(f"Informe: {(destination/f'{stem}.md').resolve()}")
    return 2 if report['status']=='data_insufficient' else 0

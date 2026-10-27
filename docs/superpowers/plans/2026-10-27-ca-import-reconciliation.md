# Cartera CA — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reconstruir Cartera CA desde el Excel, conservar su procedencia y producir una conciliación reproducible, sin conexión al broker.

**Architecture:** Un lector de Excel produce un inventario completo de los bloques CA; un extractor lo convierte en registros uniformes. La conciliación compara cálculos propios con valores guardados; un comando guarda cada versión en SQLite y genera un informe de texto. El original y todos los resultados financieros permanecen en almacenamiento local ignorado por Git.

**Tech Stack:** Python 3.11 o posterior; `openpyxl==3.1.5`; biblioteca estándar (`decimal`, `sqlite3`, `json`, `hashlib`, `argparse`, `unittest`, `tempfile`). Entorno inspeccionado: Python 3.14.7 y openpyxl 3.1.5. No hacen falta pandas, credenciales ni plugins en esta fase.

**Spec:** `docs/superpowers/specs/2026-10-27-cacl-ca-paper-design.md`. Leer ambos documentos antes de ejecutar.

## Global Constraints

- «El estado inicial de referencia será la cartera existente del Excel, con SPY, LLY y efectivo.»
- «Bonos, otras carteras, trading real y captación de capital quedan fuera de este proyecto.»
- «Una reimportación idéntica no duplica movimientos.»
- «Cambios en la fuente generan una revisión, sin sobrescribir el historial anterior.»
- «Los errores de fórmulas de Excel se registran, sin convertirse en ceros.»
- «Los rangos anteriores describen este adjunto, no límites fijos del futuro importador.»
- «Las aportaciones no contarán como rendimiento.»
- El análisis lateral cubre todas las columnas, incluso AD:AJ. Los resúmenes no se convierten en nuevas operaciones.
- El historial identifica 125 filas cerradas, no necesariamente 125 decisiones independientes.
- No modificar ni recalcular el archivo original con Excel, LibreOffice u otra aplicación.
- No descargar cotizaciones ni resolver símbolos mediante conjeturas. Elegibilidad de cada instrumento: `unverified`; ninguna salida de esta fase habilita operaciones.

---

## Alcance y estructura de archivos

La fase 1 entrega software local utilizable por sí mismo. Las fases 2–5 tienen sus propias condiciones en la especificación y recibirán planes separados. La comprobación efectiva de instrumentos admitidos por Alpaca se realizará antes de cualquier orden en fase 4; en fase 1 se identifican los símbolos y las ambigüedades sin afirmar admisión.

| Archivo | Responsabilidad |
|---|---|
| `requirements.txt` | Única dependencia: openpyxl 3.1.5. |
| `.gitignore` | Ignorar `.context/`, `.venv/`, `__pycache__/` y `*.pyc`. |
| `cacl_ca/__init__.py` | Paquete vacío. |
| `cacl_ca/workbook.py` | Leer valores/fórmulas, identificar bloques y extraer CA. |
| `cacl_ca/reconcile.py` | Conciliación con Decimal, inventario de métricas e incidencias. |
| `cacl_ca/storage.py` | Archivo original por hash, versiones inmutables y SQLite. |
| `cacl_ca/__main__.py` | Comando de importación e informe Markdown determinista. |
| `tests/__init__.py` | Paquete vacío. |
| `tests/support.py` | Localizar el adjunto real mediante `CA_WORKBOOK`. |
| `tests/test_workbook.py` | Cobertura de columnas, límites CA, valores ausentes y extracción. |
| `tests/test_reconcile.py` | Cálculos monetarios, diferencias y métricas históricas. |
| `tests/test_storage.py` | Idempotencia, nuevas versiones y conservación del original. |
| `tests/test_cli.py` | Ejecución del comando completo y códigos de salida. |
| `README.md` | Instalación, comando, resultados y límites de interpretación. |

Los archivos de ejecución se guardan bajo `.context/ca/`: `ca.sqlite3`, `sources/<sha256>.xlsx` y `reports/<sha256>-v1.md`. No se añade un dashboard, un servidor ni una configuración de broker.

## Contratos compartidos

Se usan diccionarios y listas serializables, sin nuevas capas de clases. Los importes y cantidades se representan como cadenas decimales, fechas como ISO 8601 y booleanos como booleanos. No redondear cada movimiento antes de sumar.

`read_workbook(path: Path) -> dict` devuelve:

```python
{
    "source_sha256": "hexadecimal del archivo completo",
    "sheets": {
        "History_CA": {
            "cells": {"AC11": {"value": "1000000", "formula": None,
                               "kind": "number", "number_format": "General"}},
            "tables": {"Tabla4": "B10:J271"},
            "merged_ranges": [],
        }
    },
    "issues": [],
}
```

Las celdas se conservan cuando hay valor o fórmula. `kind` puede ser `number`, `date`, `text`, `bool`, `error` o `blank`. Una fórmula con resultado ausente conserva su fórmula y `value=None`; no se convierte en un dato numérico. Las hojas completas autorizadas son `Cartera_CA`, `Liquidación_Posiciones_CA`, `History_CA` y `Risk_Management`. De `Dividend Payments` se conserva sólo el bloque CA identificado por sus encabezados, incluyendo su total; se registra el nombre del siguiente bloque como límite, sin importar sus movimientos.

`extract_ca(book: dict) -> dict` devuelve `source_sha256`, `schema_version=1`, `as_of`, `positions`, `trades`, `cashflows`, `history`, `balances`, `adjustments`, `symbols`, `blocks`, `source_cells` e `issues`.

| Colección | Campos de cada registro |
|---|---|
| `positions` | `symbol`, `quantity`, `average_cost`, `saved_price`, `saved_value`, `included`, `source` |
| `trades` | `symbol`, `quantity`, `average_cost`, `closing_price`, `invested`, `closing_value`, `pnl`, `entry_date`, `exit_date`, `source` |
| `cashflows` | `date`, `action`, `symbol`, `amount`, `source` |
| `history` | `date`, `nav`, `benchmark_close`, `source` |
| `adjustments` | `label`, `amount`, `source` |
| `symbols` | `source_symbol`, `eligibility="unverified"`, `sources` |
| `blocks` | `sheet`, `name`, `bounds`, `role` (`primary`, `derived`, `reference`, `unknown`) |
| `issues` | `code`, `severity` (`warning` o `error`), `message`, `source` |

`source` es un diccionario con `sheet` y `cell` o `row`. `balances` contiene `cash`, `positions_value`, `equity`, `nominal_capital`, `reported_realized`, `reported_cashflows` y `cash_before_realized_and_flows`. `source_cells` conserva las celdas de origen y sus fórmulas para poder explicar indicadores, no para ejecutar fórmulas arbitrarias.

`reconcile(snapshot: dict) -> dict` devuelve `checks`, `metrics`, `issues` y `status` (`reconciled`, `review_required`, `invalid`). Cada comprobación tiene `name`, `calculated`, `reported`, `difference` y `passed`. Las métricas incluyen `closed_rows`, `wins`, `losses`, `flat`, `gross_profit`, `gross_loss`, `trade_pnl`, `adjusted_pnl`, `cashflow_total`, `positions_value`, `cash`, `equity`, `win_rate`, `profit_factor` y `last_history_date`.

`save_import(db_path: Path, source: Path, snapshot: dict, report: dict) -> tuple[int, bool]` devuelve el identificador de revisión y si se creó. `render_report(snapshot: dict, report: dict) -> str` vive en `__main__.py` y sólo formatea resultados ya calculados.

## Task 1: Lectura completa y localización de bloques

**Files:** crear `requirements.txt`, `.gitignore`, `cacl_ca/__init__.py`, `cacl_ca/workbook.py`, `tests/__init__.py`, `tests/support.py`, `tests/test_workbook.py`.

**Interfaces:** consume `Path` del Excel; produce `read_workbook(path)`, con el contrato anterior.

- [x] **1. Crear dependencia, paquetes y soporte de pruebas.**

`requirements.txt` contiene exactamente `openpyxl==3.1.5`. Crear el entorno local con `python3 -m venv .venv` y `.venv/bin/python -m pip install -r requirements.txt`. El soporte de pruebas es:

```python
import os
from pathlib import Path

def source_path():
    path = Path(os.environ["CA_WORKBOOK"])
    if not path.is_file():
        raise FileNotFoundError(path)
    return path
```

La suite de aceptación usa el adjunto local proporcionado explícitamente por el usuario. Si falta la variable o el archivo, falla con una explicación; no omitir silenciosamente las pruebas ni guardar el Excel privado en Git.

Antes de la primera prueba, establecer la ruta en la sesión de ejecución:

```bash
export CA_WORKBOOK='.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx'
```

- [x] **2. Escribir la prueba que falla antes de crear el lector.**

```python
import unittest
from cacl_ca.workbook import read_workbook
from tests.support import source_path

class WorkbookTests(unittest.TestCase):
    def test_reads_right_panels_and_only_ca_cashflows(self):
        book = read_workbook(source_path())
        self.assertIn("AJ10", book["sheets"]["History_CA"]["cells"])
        self.assertIn("Z55", book["sheets"]["Liquidación_Posiciones_CA"]["cells"])
        dividend_cells = book["sheets"]["Dividend Payments"]["cells"]
        self.assertIn("G50", dividend_cells)
        self.assertNotIn("G56", dividend_cells)
        self.assertNotIn("Cartera_CL", book["sheets"])
```

Z55 contiene la nota al pie de los indicadores; las celdas vacías sin fórmula no pertenecen al inventario.

- [x] **3. Ejecutar `.venv/bin/python -m unittest tests.test_workbook -v` y comprobar el fallo por ausencia del lector.**

- [x] **4. Implementar lectura en dos vistas y clasificación por encabezados.**

```python
from decimal import Decimal
from datetime import date, datetime
from hashlib import sha256
from openpyxl import load_workbook

def scalar(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    return str(value)

def normalize_header(value):
    return " ".join(str(value or "").split()).casefold()
```

Abrir una vista con `data_only=False` y otra con `data_only=True`, ambas con `keep_links=False`. No usar `eval`. El SHA-256 se calcula sobre los bytes originales. Recorrer hasta `max_row` y `max_column` de cada hoja autorizada, sin recortar a las columnas de operaciones. Conservar `ArrayFormula.text` cuando exista, fórmula convencional, valor guardado, tipo de celda y formato numérico. Cerrar ambas vistas en `finally`.

En dividendos buscar exactamente el encabezado normalizado `dividend payments_ca`; cero o varias coincidencias constituyen error. El siguiente encabezado `dividend payments_…` termina el bloque. Buscar su fila de columnas `Payment Date`, `Action`, `Symbol`, `Amount` por contenido, no por número fijo. Conservar el total, sin convertirlo en movimiento. Metadatos de tablas y celdas combinadas se copian para descubrir otros bloques.

Identificar los bloques laterales por sus rótulos y filas de columnas descritos en la especificación. Conservar las celdas restantes y emitir `unknown_block` cuando no se les pueda asignar significado; no descartarlas. Si falta una hoja obligatoria o no puede abrirse el ZIP/XML, emitir error claro y no escribir una revisión parcial.

- [x] **5. Ejecutar pruebas y revisar el inventario real.** Añadir pruebas de `normalize_header("Invested\u00a0") == "invested"`, fórmula sin caché y error `#VALUE!` conservado. Confirmar presencia de las fórmulas de AH3 y de los parámetros AF3, AF8 y AF9. Ejecutar el comando de pruebas anterior hasta que pase.

- [x] **6. Commit:** `git add requirements.txt .gitignore cacl_ca tests` y `git commit -m "feat: inventory CA workbook blocks and source cells"`.

## Task 2: Extraer posiciones, operaciones, flujos y serie CA

**Files:** modificar `cacl_ca/workbook.py` y `tests/test_workbook.py`.

**Interfaces:** consume el resultado de `read_workbook`; produce `extract_ca(book)`.

- [x] **1. Añadir pruebas de aceptación de extracción.**

```python
from decimal import Decimal
from cacl_ca.workbook import extract_ca

# Métodos adicionales de WorkbookTests:
def test_extracts_ca_without_treating_summaries_as_trades(self):
    snapshot = extract_ca(read_workbook(source_path()))
    self.assertEqual(len(snapshot["trades"]), 125)
    self.assertEqual(len(snapshot["cashflows"]), 45)
    self.assertEqual(len(snapshot["symbols"]), 72)
    self.assertEqual({p["symbol"]: Decimal(p["quantity"])
                      for p in snapshot["positions"] if p["included"]},
                     {"SPY": Decimal(134), "LLY": Decimal(51)})
    self.assertEqual(snapshot["as_of"], "2026-10-27")
    self.assertEqual(sum(Decimal(f["amount"]) for f in snapshot["cashflows"])
                     .quantize(Decimal("0.01")), Decimal("1833.60"))
```

Los métodos marcados como adicionales deben colocarse dentro de la clase; el código del plan separa los imports para facilitar la lectura.

- [x] **2. Ejecutar `tests.test_workbook` y verificar fallo por ausencia de `extract_ca`.**

- [x] **3. Implementar los mapeos y validaciones de cada bloque.**

```python
POSITION_HEADERS = {
    "symbol": "symbol", "units": "quantity", "avg. cost": "average_cost",
    "current price": "saved_price", "value today": "saved_value",
}
TRADE_HEADERS = {
    "symbol": "symbol", "units": "quantity", "avg. cost": "average_cost",
    "closing price": "closing_price", "invested": "invested",
    "closing value": "closing_value", "realized pnl": "pnl",
    "entry date": "entry_date", "exit date": "exit_date",
}
```

En `Cartera_CA`, localizar la fila de columnas y recorrer las filas de posiciones hasta el primer resumen. Conservar la casilla de inclusión; no importar subtotales como posiciones. Los saldos se identifican por los rótulos de la especificación y por la columna `Value Today` de esa tabla, no por la primera cifra encontrada en la fila. Para `nominal_capital`, usar la columna `Invested` de `Total CA Portfolio YTD AUM`.

En operaciones, descubrir el rango de `Trades` y validar sus encabezados. Ignorar filas vacías y tomar `STATUS=Closed`; una fila con símbolo pero estado desconocido genera incidencia. Buscar filas de operaciones fuera del rango declarado y registrar `table_range_incomplete` si existen, sin omitirlas silenciosamente ni sumarlas hasta resolver la ambigüedad. Conservar por separado los ajustes rotulados `Comisiones de Venta Schwab` y `Ajuste Coste Medio vs. FIFO`.

En `History_CA`, usar `Tabla4` o, si falta, la fila inequívoca `DATE / Port_Value_Close / Bench_Close`. Ordenar una copia por fecha para analizar, conservar fila original y señalar fechas duplicadas. `as_of` es la máxima fecha válida, sin atribuir esa fecha a la hora de las cotizaciones guardadas.

En dividendos, cada fila con fecha y acción dentro del bloque CA es un flujo; conservar signo y categoría textual. Leer su símbolo explícito, no el campo enriquecido `Symbol / Description`, que contiene errores en el archivo. Preservar ambos en la evidencia. Un campo numérico obligatorio ausente o erróneo genera `error`; un nombre enriquecido fallido con símbolo válido genera `warning`. No imputar ceros ni sustituir símbolos como BRKB por otro sin evidencia.

Los posibles grupos de salidas parciales se identifican por símbolo, fecha de entrada y coste medio coincidentes. Se etiquetan como candidatos a revisión, conservando cada fila; no se fusionan ni se deducen lotes FIFO automáticamente.

- [x] **4. Añadir una prueba de dato obligatorio ausente y de ubicación flexible.**

```python
from copy import deepcopy

def test_missing_quantity_blocks_the_snapshot(self):
    book = deepcopy(read_workbook(source_path()))
    book["sheets"]["Cartera_CA"]["cells"]["D5"]["value"] = None
    snapshot = extract_ca(book)
    self.assertTrue(any(i["severity"] == "error" for i in snapshot["issues"]))
```

Para probar desplazamiento, mover todas las coordenadas del bloque de dividendos CA dos filas en una copia del inventario mediante `openpyxl.utils.cell.coordinate_from_string`, conservando su contenido y referencias de bloque. Comprobar los mismos 45 flujos y el mismo neto, sin depender de G50 o J50 para la extracción. Implementar esa transformación dentro de la prueba, no como función de producción.

- [x] **5. Ejecutar `tests.test_workbook` hasta que todas las pruebas pasen.**
- [x] **6. Commit:** `git add cacl_ca/workbook.py tests/test_workbook.py` y `git commit -m "feat: extract CA positions trades and cash flows"`.

## Task 3: Conciliación y revisión de indicadores laterales

**Files:** crear `cacl_ca/reconcile.py` y `tests/test_reconcile.py`.

**Interfaces:** consume `extract_ca(book)`; produce `reconcile(snapshot)`.

- [x] **1. Crear las pruebas monetarias de aceptación.**

```python
import unittest
from decimal import Decimal
from cacl_ca.workbook import read_workbook, extract_ca
from cacl_ca.reconcile import reconcile
from tests.support import source_path

class ReconcileTests(unittest.TestCase):
    def test_reconciles_source_and_preserves_findings(self):
        report = reconcile(extract_ca(read_workbook(source_path())))
        expected = {"trade_pnl": "-128407.33", "adjusted_pnl": "-128422.52",
                    "cashflow_total": "1833.60", "positions_value": "168508.86",
                    "cash": "809190.11", "equity": "977698.97"}
        for name, amount in expected.items():
            self.assertEqual(Decimal(report["metrics"][name])
                             .quantize(Decimal("0.01")), Decimal(amount))
        self.assertEqual(report["metrics"]["closed_rows"], 125)
        self.assertEqual(report["metrics"]["wins"], 78)
        self.assertEqual(report["metrics"]["losses"], 46)
        self.assertEqual(report["metrics"]["flat"], 1)
        self.assertIn("stale_summary_range", {i["code"] for i in report["issues"]})
        self.assertEqual(report["status"], "review_required")
```

- [x] **2. Ejecutar `.venv/bin/python -m unittest tests.test_reconcile -v` y comprobar el fallo antes de implementar.**

- [x] **3. Implementar sumas, comparaciones y métricas básicas.**

```python
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

def money_check(name, calculated, reported):
    calculated, reported = Decimal(calculated), Decimal(reported)
    return {"name": name, "calculated": str(calculated), "reported": str(reported),
            "difference": str(calculated - reported),
            "passed": calculated.quantize(CENT, rounding=ROUND_HALF_UP)
                      == reported.quantize(CENT, rounding=ROUND_HALF_UP)}
```

Calcular valor de cada posición incluida como cantidad × precio guardado; comparar contra su valor informado y contra el subtotal de posiciones. Sumar PnL de filas, sumar ajustes por separado y comparar contra `reported_realized`. Sumar flujos CA y comparar con `reported_cashflows`. Calcular efectivo como saldo anterior a resultados + PnL ajustado + flujos. Calcular patrimonio como efectivo + posiciones; contrastar también con el último NAV de la serie.

Calcular aciertos con PnL estrictamente positivo, pérdidas con PnL negativo y empates con cero. Profit factor = beneficio bruto / valor absoluto de pérdida bruta; si no hay pérdidas, devolver `None` y explicar que el cociente no está definido. Win rate incluye las filas con resultado cero en su denominador. No aplicar Kelly ni convertir métricas descriptivas en reglas de riesgo.

- [x] **4. Revisar bloques derivados sin construir un motor de Excel.**

Inventariar los indicadores Z:AA y AB:AC por etiqueta, valor, fórmula, unidad, período y parámetros vinculados. Recalcular los básicos de operaciones a partir de registros. Conservar Sharpe, Sortino, VaR, CVaR, beta y demás métricas avanzadas como `reference_only` mientras no se haya resuelto su definición y los aportes; indicar esta limitación individualmente. El objetivo de fase 1 es explicar las discrepancias, no certificar esas fórmulas.

Comparar las fechas finales de series diarias, semanales, mensuales y de gráficos. Examinar referencias simples a rangos mediante `openpyxl.formula.Tokenizer` y `openpyxl.utils.cell.range_boundaries`: para fórmulas de resumen que buscan el último valor en una serie, comprobar si hay valores posteriores al extremo referenciado. Fórmulas no interpretables se conservan como evidencia y generan `formula_not_recomputed`, sin evaluar texto arbitrario. Para el adjunto deben aparecer al menos:

- `stale_summary_range`: AH3 termina en AH266 con datos posteriores.
- `chart_series_incomplete`: AD no llega a la fecha final de la serie principal.
- `summary_count_label_mismatch`: texto de 106 operaciones frente a 125 registros.
- `return_basis_mismatch`: fechas base 2026-01-02 y 2026-01-08; aporte indicado el 8 de enero con reflejo en NAV señalado el 30 de enero. No elegir una fecha como verdadera sin comprobante.
- `instrument_eligibility_unverified`: símbolos conservados sin conexión a Alpaca.

Si los checks aritméticos pasan pero existen estas advertencias, devolver `review_required`. Datos monetarios obligatorios ausentes, filas ambiguas o checks monetarios fallidos producen `invalid`. Ningún estado significa que la cartera esté lista para operar.

- [x] **5. Probar una discrepancia real inducida.**

```python
def test_wrong_equity_is_not_silently_accepted(self):
    snapshot = extract_ca(read_workbook(source_path()))
    snapshot["balances"]["equity"] = "977700.00"
    report = reconcile(snapshot)
    self.assertEqual(report["status"], "invalid")
    self.assertTrue(any(not check["passed"] for check in report["checks"]))
```

Añadir casos para denominador cero, retención negativa, orden cronológico de salidas y un ajuste que no debe contarse dos veces. Ejecutar `tests.test_workbook` y `tests.test_reconcile`.

- [x] **6. Commit:** `git add cacl_ca/reconcile.py tests/test_reconcile.py` y `git commit -m "feat: reconcile CA balances and report workbook discrepancies"`.

## Task 4: Versiones locales, comando e informe

**Files:** crear `cacl_ca/storage.py`, `cacl_ca/__main__.py`, `tests/test_storage.py`, `tests/test_cli.py`, `README.md`.

**Interfaces:** consume `snapshot` y `report`; produce `save_import(...)`, `render_report(...)` y `python -m cacl_ca import`.

- [x] **1. Escribir pruebas de persistencia sin duplicados.**

```python
import tempfile
import unittest
from pathlib import Path
from cacl_ca.workbook import read_workbook, extract_ca
from cacl_ca.reconcile import reconcile
from cacl_ca.storage import save_import
from tests.support import source_path

class StorageTests(unittest.TestCase):
    def test_same_source_is_a_single_revision(self):
        snapshot = extract_ca(read_workbook(source_path()))
        report = reconcile(snapshot)
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "ca.sqlite3"
            first = save_import(db, source_path(), snapshot, report)
            again = save_import(db, source_path(), snapshot, report)
            self.assertEqual(first, (1, True))
            self.assertEqual(again, (1, False))
```

- [x] **2. Ejecutar `.venv/bin/python -m unittest tests.test_storage -v` y comprobar el fallo inicial.**

- [x] **3. Implementar SQLite y archivo inmutable.**

```sql
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    source_sha256 TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    report_json TEXT NOT NULL,
    UNIQUE(source_sha256, schema_version)
);
```

Guardar JSON con `ensure_ascii=False, sort_keys=True, allow_nan=False`. El mismo hash y versión devuelve la fila existente, sin reemplazar su fecha ni datos. Un archivo cambiado crea otra revisión completa; no se suman las dos carteras ni se mezclan las filas de revisiones distintas. Si cambia el formato o el cálculo del importador, incrementar `schema_version`.

Antes de insertar, recalcular el hash del archivo y compararlo con `snapshot["source_sha256"]`. Una diferencia bloquea la escritura. Archivar bytes bajo `sources/<hash>.xlsx` con un archivo temporal y reemplazo atómico; si ya existe, verificar el hash y no sobrescribir contenido distinto. Insertar en una transacción SQLite y revertirla ante errores. Un archivo archivado sin fila por fallo transaccional es recuperable mediante reimportación; una fila nunca debe apuntar a un archivo inexistente. No guardar snapshots `invalid` como revisiones aceptadas: generar su informe de error sin insertar registros de cartera.

Para probar revisiones distintas sin modificar datos financieros, copiar el ZIP a un temporal y añadir un comentario ZIP con `zipfile.ZipFile(..., "a").comment = b"revision-test"`; verificar que el original no cambió, el nuevo hash difiere y ambas revisiones se conservan. Añadir una prueba de hash inconsistente que no deja filas insertadas.

- [x] **4. Implementar CLI con ruta obligatoria y salidas deterministas.**

```python
import argparse
from pathlib import Path

def parser():
    root = argparse.ArgumentParser(prog="cacl_ca")
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("import")
    command.add_argument("source", type=Path)
    command.add_argument("--output-dir", type=Path, default=Path(".context/ca"))
    return root
```

El comando llama lector → extractor → conciliación → almacenamiento → informe. El informe enumera estado y alcance; estado inicial; checks; bloques y métricas; incidencias con celda de origen. Incluye la fecha de referencia, hash, revisión, límites de interpretación y pasos concretos de resolución de incidencias. No incluye información de otras carteras ni recomendaciones de compra.

Crear el informe mediante temporal y reemplazo atómico, conservando el anterior si falla la escritura. En una reimportación usar los datos ya guardados de esa revisión para producir el mismo contenido; no reescribir su timestamp. Con estado `invalid`, escribir un diagnóstico si se puede y devolver 2. Archivo ilegible, permisos o SQLite inaccesible devuelven 1 con mensaje concreto. `reconciled` o `review_required` devuelven 0, con estado e incidencias visibles; una ejecución correcta no equivale a datos certificados.

- [x] **5. Probar el comando como proceso y documentar su uso.**

```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests.support import source_path

class CliTests(unittest.TestCase):
    def test_import_reports_findings_and_preserves_input(self):
        before = source_path().read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, "-m", "cacl_ca", "import", str(source_path()),
                 "--output-dir", folder], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("review_required", result.stdout)
            self.assertTrue((Path(folder) / "ca.sqlite3").is_file())
            self.assertEqual(len(list((Path(folder) / "reports").glob("*.md"))), 1)
        self.assertEqual(source_path().read_bytes(), before)
```

README debe explicar instalación, variable de pruebas, comando, archivos locales, revisiones, incidencias ya identificadas, cobertura de dividendos CA y que no se consulta Schwab ni Alpaca. Usar los siguientes comandos de aceptación:

```bash
export CA_WORKBOOK='.context/attachments/ymjXAP/Trade_Entry_Plans_Live (4).xlsx'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m cacl_ca import "$CA_WORKBOOK"
.venv/bin/python -m cacl_ca import "$CA_WORKBOOK"
git diff --check
git status --short
```

Verificar una sola fila en SQLite después de las dos importaciones del mismo adjunto, hash del original intacto y ausencia de bases de datos, archivos financieros y credenciales en `git status`. Revisar que `git check-ignore .context/ca/ca.sqlite3` identifica el archivo como ignorado.

- [x] **6. Commit:** añadir únicamente los módulos, pruebas y README de esta tarea; `git commit -m "feat: persist CA import revisions and reconciliation reports"`.

## Resultado esperado y asuntos que requieren evidencia adicional

El usuario podrá ejecutar un comando local y ver una reconstrucción CA con 2 posiciones incluidas, 125 filas cerradas, 45 flujos CA, 72 etiquetas de símbolos y un patrimonio guardado de 977.698,97 USD. Los resúmenes de la derecha serán visibles e identificados como derivados, con sus incidencias.

El adjunto debe terminar en `review_required`: contiene rangos desactualizados y diferencias de bases que deben explicarse, no ocultarse. Esto permite entregar y revisar el importador, pero no certificar toda la rentabilidad ni habilitar trading. El contraste con Schwab, la fecha efectiva de aportes, los lotes y la elegibilidad de instrumentos siguen siendo trabajo de conciliación con evidencia externa; el informe indicará exactamente qué documento o respuesta resuelve cada punto.

## Auto-revisión del plan

- Cobertura: Task 1 inventaría todas las columnas y separa carteras; Task 2 extrae CA y conserva procedencia; Task 3 concilia e identifica diferencias; Task 4 preserva revisiones y entrega el informe.
- Las salidas de una tarea son las entradas documentadas de la siguiente. No hay scheduler, broker, señales ni UI en fase 1.
- Los importes se procesan con Decimal. El importador no ejecuta fórmulas ni inventa precios, retornos o hechos faltantes.
- Las pruebas se basan en resultados financieros concretos, aislamiento CA, revisión inmutable y fallos que podrían corromper la cartera.
- Las métricas avanzadas conservadas como referencia y la elegibilidad no comprobada se declaran explícitamente; no se contabilizan como verificaciones realizadas.


## Ejecución completada — 2026-10-27

Las cuatro tareas están implementadas. Verificación final: 33 pruebas pasan, incluidas ejecución del CLI, aislamiento CA, entradas incompletas, rollback y reintento de SQLite. Las 19 comprobaciones de conciliación del adjunto pasan; el estado sigue siendo `review_required` por los hallazgos documentados, sin habilitar trading.

Se ejecutó dos veces el comando final con el original: una sola revisión por hash y versión, mismo informe y SHA-256 intacto. La versión 2 corrige la procedencia de la cabecera diaria a `History_CA!B10`; se conserva la revisión local de validación v1 sin sobrescribirla. No cambian los saldos por esa corrección.

Informe final local: `.context/ca/reports/bc6eb1e91cad2659a1892a14bc18bf3b4c1be528434cc0bf3683b07de20dc041-v2.md`. SQLite, copias del Excel y adjuntos están excluidos de Git. `git diff --check` pasa. El README documenta instalación, ejecución, estados, límites y pruebas. Se conserva la rama de trabajo sin merge ni publicación.

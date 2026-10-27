"""Local CA workbook importer. No network or brokerage access."""

import argparse
import html
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from .workbook import read_workbook, extract_ca
from .reconcile import reconcile
from .storage import atomic_write, save_import, load_import


def _text(value):
    if value is None:
        return "No disponible"
    return (html.escape(str(value)).replace("|", "\\|").replace("\n", " ")
            .replace("\r", " ").replace("[", "\\[").replace("]", "\\]")
            .replace("`", "\\`"))


def _money(value):
    if value is None:
        return "No disponible"
    return f"{Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _source(source):
    return f"{source['sheet']}!{source.get('cell') or source.get('row') or '—'}"


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_text(v) for v in row) + " |" for row in rows)
    return "\n".join(lines)


def render_report(snapshot: dict, report: dict) -> str:
    m = report["metrics"]
    lines = ["# Cartera CA — importación y conciliación", "",
        f"**Estado: {report['status']}**. Referencia de la serie: {snapshot['as_of']}.", "",
        "Este informe compara registros y valores guardados del Excel. No verifica saldos de Schwab, "
        "no actualiza cotizaciones y no habilita trading. Los importes se presentan en USD.", "",
        f"SHA-256 del original: `{snapshot['source_sha256']}`. Formato de importación: v{snapshot['schema_version']}.", "",
        "## Resultado principal", "",
        f"- Patrimonio calculado: **USD {_money(m['equity'])}**.",
        f"- Efectivo calculado: USD {_money(m['cash'])}; posiciones: USD {_money(m['positions_value'])}.",
        f"- {len(snapshot['positions'])} posiciones registradas; {m['closed_rows']} filas cerradas; "
        f"{len(snapshot['cashflows'])} flujos CA; {len(snapshot['symbols'])} etiquetas de activos.",
        f"- Resultado cerrado: USD {_money(m['trade_pnl'])}; con ajustes: USD {_money(m['adjusted_pnl'])}.",
        f"- Dividendos, retenciones y otros flujos CA, netos: USD {_money(m['cashflow_total'])}.", "",
        "## Estado inicial", "",
        _table(["Activo", "Incluido", "Cantidad", "Coste medio", "Precio guardado", "Valor guardado", "Origen"],
            [(p["symbol"], "Sí" if p["included"] else "No", p["quantity"], _money(p["average_cost"]),
              _money(p["saved_price"]), _money(p["saved_value"]), _source(p["source"])) for p in snapshot["positions"]]), "",
        "El patrimonio nominal de referencia es distinto del patrimonio actual. Las ganancias previas de "
        "estas posiciones no representan resultados de una estrategia nueva.", "",
        "## Comprobaciones", "",
        _table(["Comprobación", "Calculado", "Informado", "Diferencia", "Resultado"],
            [(c["name"], c["calculated"], c["reported"], c["difference"], "Cuadra" if c["passed"] else "REVISAR")
             for c in report["checks"]]), "",
        "## Ajustes conservados", "",
        _table(["Concepto", "USD", "Origen"],
            [(a["label"], _money(a["amount"]), _source(a["source"])) for a in snapshot["adjustments"]]), "",
        "## Hallazgos y acciones de revisión", "",
    ]
    for issue in report["issues"]:
        lines.append(f"- **{issue['severity']} · {issue['code']}** — {_text(issue['message'])} "
                     f"Origen: {_text(_source(issue['source']))}.")
    lines += ["", "## Cobertura de las hojas", "",
        _table(["Hoja", "Bloque", "Rango o celdas", "Función"],
            [(b["sheet"], b["name"], ", ".join(b["bounds"]) if isinstance(b["bounds"], list) else b["bounds"], b["role"])
             for b in snapshot["blocks"]]), "",
        "Se conserva exclusivamente el bloque CA de Dividend Payments. Los resúmenes laterales son "
        "datos derivados y no se suman como nuevas operaciones. Fórmulas y celdas completas están en SQLite.", "",
        "## Series y bases de cálculo", "",
        _table(["Serie", "Primera fecha", "Última fecha", "Filas", "Origen"],
            [(s["name"], s["first_date"], s["last_date"], s["rows"], _source(s["source"])) for s in report["series"]]), "",
        _table(["Parámetro", "Valor guardado", "Origen en History_CA"],
            [(p["label"], p["value"], p["source"]) for p in report["parameters"]]), "",
        "## Indicadores guardados y verificación", "",
        "`recomputed`: contrastado con registros importados. `reference_only`: preservado, sin certificación "
        "del cálculo. La tasa libre de riesgo y otros supuestos pertenecen al archivo, no son datos actuales.", "",
        _table(["Indicador o parámetro", "Valor guardado", "Estado", "Período", "Origen"],
            [(r["label"], r["saved_value"], r["status"], r["period"], _source(r["source"])) for r in report["reference_metrics"]]), "",
        "## Activos del alcance", "",
        ", ".join(_text(s["source_symbol"]) for s in snapshot["symbols"]), "",
        "Las etiquetas se conservan sin fusionar clases, warrants o cambios de símbolo. Disponibilidad "
        "en Alpaca no verificada. Los grupos de posibles salidas parciales conservan sus filas originales.", "",
        "## Límites de esta fase", "",
        "La conciliación aritmética no certifica la rentabilidad. Para resolver los hallazgos hacen falta "
        "comprobantes de aportes, ajustes y lotes, además de revisar fechas, bases y rangos de indicadores. "
        "Ninguna operación histórica se envía a un broker. El archivo original se conserva sin modificaciones.", ""]
    return "\n".join(lines)


def parser():
    root = argparse.ArgumentParser(prog="cacl_ca", description="Importar y conciliar exclusivamente Cartera CA.")
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser("import")
    command.add_argument("source", type=Path)
    command.add_argument("--output-dir", type=Path, default=Path(".context/ca"))
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        snapshot = extract_ca(read_workbook(args.source))
        report = reconcile(snapshot)
        revision, created = None, False
        if report["status"] != "invalid":
            db = args.output_dir / "ca.sqlite3"
            revision, created = save_import(db, args.source, snapshot, report)
            snapshot, report = load_import(db, revision)
        suffix = "-invalid" if report["status"] == "invalid" else ""
        destination = args.output_dir / "reports" / f"{snapshot['source_sha256']}-v{snapshot['schema_version']}{suffix}.md"
        text = render_report(snapshot, report)
        if revision is not None:
            text += f"\nRevisión local: {revision}.\n"
        atomic_write(destination, text.encode("utf-8"))
        print(f"Estado: {report['status']}. Patrimonio calculado: USD {_money(report['metrics']['equity'])}.")
        if revision is not None:
            print(f"Revisión {revision}: {'creada' if created else 'existente, sin duplicados'}.")
        print(f"Informe: {destination.resolve()}")
        return 2 if report["status"] == "invalid" else 0
    except (OSError, ValueError, sqlite3.Error, BadZipFile, ParseError, InvalidFileException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

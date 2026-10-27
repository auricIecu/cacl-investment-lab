"""Read the CA workbook without executing formulas or refreshing market data."""

from datetime import date, datetime
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils.cell import coordinate_to_tuple, get_column_letter, range_boundaries


SHEETS = ("Cartera_CA", "Liquidación_Posiciones_CA", "History_CA",
          "Dividend Payments", "Risk_Management")


def normalize_header(value):
    return " ".join(str(value if value is not None else "").split()).casefold()


def scalar(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def read_workbook(path: Path) -> dict:
    data = Path(path).read_bytes()
    formulas = load_workbook(BytesIO(data), data_only=False, keep_links=False)
    cached = None
    try:
        cached = load_workbook(BytesIO(data), data_only=True, keep_links=False)
        missing = set(SHEETS) - set(formulas.sheetnames)
        if missing:
            raise ValueError(f"Falta hoja obligatoria: {', '.join(sorted(missing))}")
        result = {"source_sha256": sha256(data).hexdigest(), "sheets": {}, "issues": []}
        for name in SHEETS:
            sheet, values = formulas[name], cached[name]
            first, last = 1, sheet.max_row
            next_block = None
            if name == "Dividend Payments":
                headers = [(c.row, normalize_header(c.value)) for row in sheet for c in row
                           if isinstance(c.value, str)
                           and normalize_header(c.value).startswith("dividend payments_")]
                starts = [row for row, label in headers if label == "dividend payments_ca"]
                if len(starts) != 1:
                    raise ValueError("Dividend Payments: se requiere un único bloque CA")
                first = starts[0]
                following = sorted((row, label) for row, label in headers if row > first)
                if following:
                    last, next_block = following[0]
                    last -= 1
            cells = {}
            for row in sheet.iter_rows(min_row=first, max_row=last):
                for cell in row:
                    if cell.value is None:
                        continue
                    formula = getattr(cell.value, "text", None)
                    if cell.data_type == "f" and isinstance(cell.value, str):
                        formula = cell.value
                    saved = values[cell.coordinate]
                    value = saved.value
                    kind = ("error" if saved.data_type == "e" else
                            "blank" if value is None else
                            "bool" if isinstance(value, bool) else
                            "date" if isinstance(value, (date, datetime)) else
                            "number" if isinstance(value, (int, float)) else "text")
                    cells[cell.coordinate] = {"value": scalar(value), "formula": formula,
                                              "kind": kind, "number_format": cell.number_format}
            result["sheets"][name] = {
                "cells": cells, "tables": {n: sheet.tables[n].ref for n in sheet.tables},
                "merged_ranges": [str(r) for r in sheet.merged_cells.ranges],
                "next_block": next_block,
            }
        return result
    finally:
        formulas.close()
        if cached is not None:
            cached.close()


def _issue(issues, code, message, sheet, cell=None, severity="warning"):
    issues.append({"code": code, "severity": severity, "message": message,
                   "source": {"sheet": sheet, "cell": cell}})


def _rows(cells):
    rows = defaultdict(dict)
    for address, cell in cells.items():
        row, column = coordinate_to_tuple(address)
        rows[row][column] = cell
    return rows


def _value(rows, row, column):
    return rows.get(row, {}).get(column, {}).get("value")


def _header(rows, required, sheet):
    candidates = []
    for row, cells in sorted(rows.items()):
        headers = {}
        for column, cell in sorted(cells.items()):
            headers.setdefault(normalize_header(cell["value"]), column)
        if set(required) <= headers.keys():
            candidates.append((row, headers))
    if len(candidates) != 1:
        raise ValueError(f"{sheet}: encabezado ambiguo o ausente ({', '.join(required)})")
    return candidates[0]


def _number(rows, row, column, issues, sheet, positive=False):
    cell = rows.get(row, {}).get(column, {})
    value = cell.get("value")
    try:
        number = Decimal(value) if isinstance(value, str) else Decimal("NaN")
        if (cell.get("kind") != "number" or not number.is_finite()
                or (positive and number <= 0)):
            raise InvalidOperation
        return str(number)
    except (InvalidOperation, ValueError, TypeError):
        _issue(issues, "invalid_number", "Número obligatorio ausente o inválido.", sheet,
               f"{get_column_letter(column)}{row}", "error")
        return None


def _date(rows, row, column, issues, sheet):
    value = _value(rows, row, column)
    try:
        if rows[row][column]["kind"] != "date":
            raise ValueError
        return date.fromisoformat(value[:10]).isoformat()
    except (ValueError, TypeError, KeyError):
        _issue(issues, "invalid_date", "Fecha obligatoria ausente o inválida.", sheet,
               f"{get_column_letter(column)}{row}", "error")
        return None


def _label(rows, label, sheet):
    matches = [(row, col) for row, cells in rows.items() for col, cell in cells.items()
               if normalize_header(cell["value"]) == normalize_header(label)]
    if len(matches) != 1:
        raise ValueError(f"{sheet}: rótulo ambiguo o ausente: {label}")
    return matches[0]


def _inventory_blocks(book, issues):
    # Anchors locate horizontal panels; widths describe each known panel's fields.
    layouts = {
        "Cartera_CA": [(None, "Posiciones y saldos", 16, "primary"),
                       ("asset allocation - equities", "Distribución", 2, "derived")],
        "Liquidación_Posiciones_CA": [(None, "Operaciones y ajustes", 14, "primary"),
            ("realized monthly performance", "Resultados mensuales", 3, "derived"),
            ("asset", "Consulta por activo", 2, "derived"),
            ("trading performance kpis", "Indicadores por operación", 2, "derived")],
        "History_CA": [(None, "Serie diaria", 10, "primary"),
            ("weekly performance", "Serie semanal y parámetros", 7, "derived"),
            ("monthly performance", "Serie mensual", 7, "derived"),
            ("portfolio performance kpis", "Indicadores de cartera", 2, "derived"),
            ("chart engine", "Series de gráficos", 7, "derived")],
    }
    blocks = []
    for name, sheet in book["sheets"].items():
        cells = sheet["cells"]
        if not cells:
            continue
        coords = [coordinate_to_tuple(c) for c in cells]
        last_row = max(r for r, _ in coords)
        covered = set()
        if name not in layouts:
            first_col, last_col = min(c for _, c in coords), max(c for _, c in coords)
            intervals = [(first_col, last_col, name,
                          "primary" if name == "Dividend Payments" else "reference")]
        else:
            intervals = []
            for anchor, title, width, role in layouts[name]:
                matches = [coordinate_to_tuple(address)[1] for address, cell in cells.items()
                           if anchor and normalize_header(cell["value"]).startswith(anchor)]
                if anchor is None:
                    start = 1
                elif len(matches) == 1:
                    start = matches[0]
                else:
                    _issue(issues, "missing_panel", f"Panel no localizado: {title}", name)
                    continue
                intervals.append((start, start + width - 1, title, role))
        for first, last, title, role in intervals:
            covered.update(address for address in cells
                           if first <= coordinate_to_tuple(address)[1] <= last)
            blocks.append({"sheet": name, "name": title,
                           "bounds": f"{get_column_letter(first)}1:{get_column_letter(last)}{last_row}",
                           "role": role})
        unknown = sorted(set(cells) - covered, key=coordinate_to_tuple)
        if unknown:
            _issue(issues, "unknown_block",
                   f"{len(unknown)} celdas fuera de los paneles conocidos; conservadas para revisión.",
                   name, unknown[0])
            blocks.append({"sheet": name, "name": "Contenido sin clasificar",
                           "bounds": unknown, "role": "unknown"})
    return blocks


def extract_ca(book: dict) -> dict:
    issues = list(book["issues"])
    snapshot = {"source_sha256": book["source_sha256"], "schema_version": 1, "as_of": None,
                "positions": [], "trades": [], "cashflows": [], "history": [], "balances": {},
                "balance_sources": {}, "adjustments": [], "symbols": [], "issues": issues,
                "source_cells": {name: s["cells"] for name, s in book["sheets"].items()}}
    snapshot["blocks"] = _inventory_blocks(book, issues)
    for name, sheet in book["sheets"].items():
        errors = [c for c, v in sheet["cells"].items() if v["kind"] == "error"]
        missing = [c for c, v in sheet["cells"].items() if v["formula"] and v["value"] is None]
        if errors:
            _issue(issues, "excel_errors", f"{len(errors)} errores Excel conservados en la evidencia.",
                   name, ", ".join(errors[:8]))
        if missing:
            _issue(issues, "missing_formula_cache", f"{len(missing)} fórmulas sin resultado guardado.",
                   name, ", ".join(missing[:8]))

    name = "Cartera_CA"
    rows = _rows(book["sheets"][name]["cells"])
    start, h = _header(rows, ["symbol", "units", "avg. cost", "value today", "invested"], name)
    end, _ = _label(rows, "Unrealized P&L", name)
    for row in range(start + 1, end):
        symbol = _value(rows, row, h["symbol"])
        if not symbol:
            if _value(rows, row, h["units"]) is not None:
                _issue(issues, "missing_symbol", "Posición sin símbolo.", name, str(row), "error")
            continue
        included = _value(rows, row, min(h.values()) - 1)
        if not isinstance(included, bool):
            _issue(issues, "invalid_inclusion", "Falta la casilla de inclusión de posición.",
                   name, str(row), "error")
        record = {"symbol": symbol, "included": included is True, "source": {"sheet": name, "row": row}}
        for header, key in [("units", "quantity"), ("avg. cost", "average_cost"),
                            ("current price", "saved_price"), ("value today", "saved_value")]:
            record[key] = _number(rows, row, h[header], issues, name, positive=True)
        snapshot["positions"].append(record)
    balance_labels = {
        "cash": "Total Cash and Cash Equivalent", "positions_value": "Unrealized P&L",
        "equity": "Total CA Portfolio AUM", "nominal_capital": "Total CA Portfolio YTD AUM",
        "reported_realized": "Realized P&L", "reported_cashflows": "Dividend Payments",
        "cash_before_realized_and_flows": "Cash and Cash Equivalent (subject to real remaining cash)",
    }
    for key, label in balance_labels.items():
        row, _ = _label(rows, label, name)
        col = h["invested"] if key == "nominal_capital" else h["value today"]
        snapshot["balances"][key] = _number(rows, row, col, issues, name)
        snapshot["balance_sources"][key] = {"sheet": name, "cell": f"{get_column_letter(col)}{row}"}

    name = "Liquidación_Posiciones_CA"
    sheet = book["sheets"][name]
    rows = _rows(sheet["cells"])
    start, h = _header(rows, ["symbol", "units", "status", "realized pnl", "entry date", "exit date"], name)
    if "Trades" not in sheet["tables"]:
        raise ValueError(f"{name}: falta la tabla Trades")
    _, table_start, _, table_end = range_boundaries(sheet["tables"]["Trades"])
    if table_start != start:
        raise ValueError(f"{name}: encabezado fuera de la tabla Trades")
    mapping = {"units": "quantity", "avg. cost": "average_cost", "closing price": "closing_price",
               "invested": "invested", "closing value": "closing_value", "realized pnl": "pnl"}
    for row in sorted(rows):
        if row <= start:
            continue
        symbol, status = _value(rows, row, h["symbol"]), _value(rows, row, h["status"])
        if row > table_end:
            if status is not None:
                _issue(issues, "table_range_incomplete", "Fila con estado fuera de Trades.",
                       name, str(row), "error")
            continue
        if symbol is None and status is None:
            continue
        if not symbol or normalize_header(status) != "closed":
            _issue(issues, "invalid_trade", "Operación sin símbolo o con estado desconocido.",
                   name, str(row), "error")
            continue
        trade = {"symbol": symbol, "source": {"sheet": name, "row": row}}
        for header, key in mapping.items():
            trade[key] = _number(rows, row, h[header], issues, name, positive=key == "quantity")
        for key in ("entry_date", "exit_date"):
            trade[key] = _date(rows, row, h[key.replace("_", " ")], issues, name)
        if trade["entry_date"] and trade["exit_date"] and trade["entry_date"] > trade["exit_date"]:
            _issue(issues, "invalid_date_order", "Salida anterior a entrada.", name, str(row), "error")
        snapshot["trades"].append(trade)
    for label in ("Comisiones de Venta Schwab", "Ajuste Coste Medio vs. FIFO"):
        row, _ = _label(rows, label, name)
        snapshot["adjustments"].append({"label": label,
            "amount": _number(rows, row, h["realized pnl"], issues, name),
            "source": {"sheet": name, "row": row}})

    name = "Dividend Payments"
    rows = _rows(book["sheets"][name]["cells"])
    start, h = _header(rows, ["payment date", "action", "symbol", "amount"], name)
    for row in sorted(rows):
        if row <= start:
            continue
        if all(_value(rows, row, h[k]) is None for k in ("payment date", "action", "amount")):
            continue
        action, symbol = _value(rows, row, h["action"]), _value(rows, row, h["symbol"])
        if not action or not symbol:
            _issue(issues, "invalid_cashflow", "Flujo CA sin acción o símbolo.", name, str(row), "error")
        snapshot["cashflows"].append({"date": _date(rows, row, h["payment date"], issues, name),
            "action": action, "symbol": symbol,
            "amount": _number(rows, row, h["amount"], issues, name), "source": {"sheet": name, "row": row}})
    row, col = _label(rows, "Total Payments", name)
    snapshot["dividend_block_total"] = _number(rows, row, col + 1, issues, name)

    name = "History_CA"
    rows = _rows(book["sheets"][name]["cells"])
    start, h = _header(rows, ["date", "port_value_close", "bench_close"], name)
    for row in sorted(rows):
        if row <= start or all(_value(rows, row, h[k]) is None
                               for k in ("date", "port_value_close", "bench_close")):
            continue
        snapshot["history"].append({"date": _date(rows, row, h["date"], issues, name),
            "nav": _number(rows, row, h["port_value_close"], issues, name, positive=True),
            "benchmark_close": _number(rows, row, h["bench_close"], issues, name, positive=True),
            "source": {"sheet": name, "row": row}})
    snapshot["history"].sort(key=lambda r: r["date"] or "")
    dates = [r["date"] for r in snapshot["history"] if r["date"]]
    snapshot["as_of"] = max(dates, default=None)
    if len(set(dates)) != len(dates):
        _issue(issues, "duplicate_history_date", "Fechas duplicadas en la serie diaria.", name, severity="error")
    if not dates:
        _issue(issues, "missing_history", "Serie diaria vacía.", name, severity="error")
    symbols = defaultdict(list)
    for record in snapshot["trades"] + snapshot["positions"]:
        symbols[record["symbol"]].append(record["source"])
    snapshot["symbols"] = [{"source_symbol": symbol, "eligibility": "unverified", "sources": sources}
                           for symbol, sources in sorted(symbols.items())]
    lots = defaultdict(list)
    for trade in snapshot["trades"]:
        lots[(trade["symbol"], trade["entry_date"], trade["average_cost"])].append(trade["source"])
    snapshot["partial_exit_candidates"] = [sources for sources in lots.values() if len(sources) > 1]
    return snapshot

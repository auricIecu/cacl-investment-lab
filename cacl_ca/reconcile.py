"""Arithmetic reconciliation; Excel calculations remain evidence, not executable code."""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import TokenizerError
from openpyxl.utils.cell import coordinate_to_tuple, get_column_letter, range_boundaries

from .workbook import _issue, _rows, normalize_header


CENT = Decimal("0.01")


def _decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except InvalidOperation:
        return None


def _sum(values):
    numbers = [_decimal(v) for v in values]
    return sum(numbers, Decimal(0)) if all(v is not None for v in numbers) else None


def _product(left, right):
    left, right = _decimal(left), _decimal(right)
    return left * right if left is not None and right is not None else None


def money_check(name, calculated, reported, precision=CENT):
    calculated, reported = _decimal(calculated), _decimal(reported)
    present = calculated is not None and reported is not None
    return {"name": name, "calculated": str(calculated) if calculated is not None else None,
            "reported": str(reported) if reported is not None else None,
            "difference": str(calculated - reported) if present else None,
            "passed": present and calculated.quantize(precision, rounding=ROUND_HALF_UP)
            == reported.quantize(precision, rounding=ROUND_HALF_UP)}


def _side_panels(snapshot, metrics, checks, issues):
    references, series = [], []
    metric_names = {
        "trades cerrados (n)": "closed_rows", "trades ganadores (n)": "wins",
        "trades perdedores (n)": "losses", "pnl realizado total ($)": "trade_pnl",
        "win rate (%)": "win_rate", "beneficio bruto ($)": "gross_profit",
        "pérdida bruta ($)": "gross_loss", "profit factor (x)": "profit_factor",
        "ganancia media ($)": "average_win", "pérdida media ($)": "average_loss",
    }
    for block in snapshot["blocks"]:
        if block["name"] not in ("Indicadores por operación", "Indicadores de cartera"):
            continue
        sheet = block["sheet"]
        cells = snapshot["source_cells"][sheet]
        col, _, _, _ = range_boundaries(block["bounds"])
        for row, row_cells in sorted(_rows(cells).items()):
            label = row_cells.get(col, {}).get("value")
            value_cell = row_cells.get(col + 1)
            if not label or not value_cell:
                continue
            key = metric_names.get(normalize_header(label)) if sheet == "Liquidación_Posiciones_CA" else None
            address = f"{get_column_letter(col + 1)}{row}"
            check = None
            if key:
                precision = Decimal("0.000000001") if key in ("win_rate", "profit_factor") else CENT
                check = money_check(f"{sheet}!{address}: {label}", metrics.get(key), value_cell["value"], precision)
                # An undefined ratio is a finding, not a numeric zero.
                if metrics.get(key) is not None:
                    checks.append(check)
            references.append({"label": label, "saved_value": value_cell["value"],
                "formula": value_cell["formula"], "unit": value_cell["number_format"],
                "status": "recomputed" if check and check["passed"] else "reference_only",
                "source": {"sheet": sheet, "cell": address},
                "period": "filas cerradas" if sheet == "Liquidación_Posiciones_CA" else "según bases del libro"})
    pending = sum(r["status"] == "reference_only" for r in references)
    if pending:
        _issue(issues, "formula_not_recomputed",
               f"{pending} indicadores/parámetros se conservan como referencia; verificar definiciones y aportes antes de certificarlos.",
               "History_CA / Liquidación_Posiciones_CA")

    cells = snapshot["source_cells"]["History_CA"]
    series_names = {"Serie diaria": "daily", "Serie semanal y parámetros": "weekly",
                    "Serie mensual": "monthly", "Series de gráficos": "chart"}
    for block in snapshot["blocks"]:
        if block["sheet"] != "History_CA" or block["name"] not in series_names:
            continue
        col, _, end_col, _ = range_boundaries(block["bounds"])
        # A panel can start with a blank margin (the daily panel includes column A).
        headers = [(coordinate_to_tuple(a), c["value"]) for a, c in cells.items()
                   if col <= coordinate_to_tuple(a)[1] <= end_col
                   and normalize_header(c["value"]) in ("date", "week ending", "month end")]
        if not headers:
            continue
        (header_row, date_col), _ = min(headers)
        dates = [c["value"][:10] for a, c in cells.items() if c["kind"] == "date"
                 and coordinate_to_tuple(a)[1] == date_col and coordinate_to_tuple(a)[0] > header_row]
        series.append({"name": series_names[block["name"]], "first_date": min(dates, default=None),
                       "last_date": max(dates, default=None), "rows": len(dates),
                       "source": {"sheet": "History_CA", "cell": f"{get_column_letter(date_col)}{header_row}"}})
    chart = next((s for s in series if s["name"] == "chart"), None)
    if chart and chart["last_date"] != snapshot["as_of"]:
        _issue(issues, "chart_series_incomplete",
               f"Gráficos hasta {chart['last_date']}; serie diaria hasta {snapshot['as_of']}. Extender y revisar la serie del gráfico.",
               "History_CA", chart["source"]["cell"])

    for address, cell in cells.items():
        formula = cell["formula"]
        if not formula or "LOOKUP(" not in formula.upper():
            continue
        try:
            ranges = {t.value for t in Tokenizer(formula).items if t.subtype == "RANGE"}
        except TokenizerError:
            _issue(issues, "formula_not_recomputed", "No se pudo inspeccionar esta fórmula; revisar en el libro.",
                   "History_CA", address)
            continue
        for ref in sorted(ranges):
            if not re.fullmatch(r"\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+", ref):
                continue
            first_col, _, last_col, last_row = range_boundaries(ref)
            if first_col != last_col:
                continue
            later = [a for a, c in cells.items() if c["kind"] == "number"
                     and coordinate_to_tuple(a)[1] == last_col and coordinate_to_tuple(a)[0] > last_row]
            if later:
                _issue(issues, "stale_summary_range",
                       f"Resumen usa {ref}, pero hay datos numéricos hasta {max(later, key=coordinate_to_tuple)}. Revisar el extremo del rango.",
                       "History_CA", address)

    for address, cell in snapshot["source_cells"]["Liquidación_Posiciones_CA"].items():
        match = re.search(r"(\d+)\s+trades cerrados", str(cell["value"]), re.IGNORECASE)
        if match and int(match[1]) != metrics["closed_rows"]:
            _issue(issues, "summary_count_label_mismatch",
                   f"Rótulo menciona {match[1]} operaciones; se extrajeron {metrics['closed_rows']} filas cerradas. Actualizar el rótulo.",
                   "Liquidación_Posiciones_CA", address)
    parameters = []
    for row, row_cells in sorted(_rows(cells).items()):
        for col, cell in row_cells.items():
            label = normalize_header(cell["value"])
            if any(term in label for term in ("ytd base date", "primer día de trading",
                                              "capital added", "deposit shows in nav")):
                right = [(c, v) for c, v in sorted(row_cells.items())
                         if col < c <= col + 2 and v["kind"] in ("date", "number")]
                if right:
                    c, value = right[0]
                    parameters.append({"label": cell["value"], "value": value["value"],
                                       "source": f"{get_column_letter(c)}{row}"})
    parameter_dates = {p["value"][:10] for p in parameters if re.match(r"\d{4}-\d{2}-\d{2}", p["value"])}
    if len(parameter_dates) > 1:
        _issue(issues, "return_basis_mismatch",
               "Bases/fechas distintas: " + "; ".join(f"{p['label']} = {p['value']} ({p['source']})" for p in parameters)
               + ". Contrastar fecha efectiva del aporte con el extracto de Schwab; no atribuir el aporte a rentabilidad.",
               "History_CA")
    return references, series, parameters


def reconcile(snapshot: dict) -> dict:
    issues = list(snapshot["issues"])
    checks = []
    included = [p for p in snapshot["positions"] if p["included"]]
    positions_value = _sum(_product(p["quantity"], p["saved_price"]) for p in included)
    for p in included:
        checks.append(money_check(f"Posición {p['symbol']}", _product(p["quantity"], p["saved_price"]), p["saved_value"]))
    pnls = [_decimal(t["pnl"]) for t in snapshot["trades"]]
    wins = [p for p in pnls if p is not None and p > 0]
    losses = [p for p in pnls if p is not None and p < 0]
    trade_pnl = _sum(pnls)
    adjusted = _sum([trade_pnl, _sum(a["amount"] for a in snapshot["adjustments"])])
    cashflows = _sum(f["amount"] for f in snapshot["cashflows"])
    balance = snapshot["balances"]
    cash = _sum([balance["cash_before_realized_and_flows"], adjusted, cashflows])
    equity = _sum([cash, positions_value])
    gross_profit, gross_loss = _sum(wins), _sum(losses)
    for name, calculated, reported in (
        ("Valor de posiciones", positions_value, balance["positions_value"]),
        ("Resultado realizado con ajustes", adjusted, balance["reported_realized"]),
        ("Flujos CA contra resumen", cashflows, balance["reported_cashflows"]),
        ("Flujos CA contra bloque", cashflows, snapshot["dividend_block_total"]),
        ("Efectivo", cash, balance["cash"]),
        ("Patrimonio", equity, balance["equity"]),
        ("Último NAV histórico", equity, snapshot["history"][-1]["nav"] if snapshot["history"] else None),
    ):
        checks.append(money_check(name, calculated, reported))
    metrics = {"closed_rows": len(pnls), "wins": len(wins), "losses": len(losses),
               "flat": sum(p == 0 for p in pnls), "gross_profit": gross_profit, "gross_loss": gross_loss,
               "trade_pnl": trade_pnl, "adjusted_pnl": adjusted, "cashflow_total": cashflows,
               "positions_value": positions_value, "cash": cash, "equity": equity,
               "win_rate": Decimal(len(wins)) / len(pnls) if pnls else None,
               "profit_factor": gross_profit / abs(gross_loss) if gross_loss else None,
               "average_win": gross_profit / len(wins) if wins else None,
               "average_loss": gross_loss / len(losses) if losses else None,
               "last_history_date": snapshot["as_of"]}
    if not gross_loss:
        _issue(issues, "undefined_profit_factor", "Sin pérdidas: profit factor no definido, no cero ni infinito.",
               "Liquidación_Posiciones_CA")
    metrics = {k: str(v) if isinstance(v, Decimal) else v for k, v in metrics.items()}
    references, series, parameters = _side_panels(snapshot, metrics, checks, issues)
    for check in checks:
        if not check["passed"]:
            _issue(issues, "reconciliation_mismatch",
                   f"{check['name']}: calculado {check['calculated']}, informado {check['reported']}. Revisar registros de origen.",
                   "CA", severity="error")
    _issue(issues, "instrument_eligibility_unverified",
           f"{len(snapshot['symbols'])} etiquetas de activos sin verificar en Alpaca. Comprobar tipo, identidad y disponibilidad antes de operar.", "CA")
    if snapshot["partial_exit_candidates"]:
        _issue(issues, "partial_exit_candidates",
               f"{len(snapshot['partial_exit_candidates'])} grupos podrían ser salidas parciales. Contrastar lotes con comprobantes; no se fusionan filas.",
               "Liquidación_Posiciones_CA")
    status = "invalid" if any(i["severity"] == "error" for i in issues) else "review_required" if issues else "reconciled"
    return {"checks": checks, "metrics": metrics, "issues": issues, "status": status,
            "reference_metrics": references, "series": series, "parameters": parameters}

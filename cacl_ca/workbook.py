"""Read the CA workbook without executing formulas or refreshing market data."""

from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook


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

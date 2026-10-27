"""Local market-data contract and point-in-time selection. No network access."""

import json
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo


METHOD_VERSION = "CA-S2-1.0.0"
SECTORS = {"Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy",
           "Financials", "Health Care", "Industrials", "Information Technology", "Materials",
           "Real Estate", "Utilities", "DIVERSIFIED_EQUITY_ETF"}
TYPES = {"common_stock", "adr", "equity_etf"}


def number(value):
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError("Número ausente o booleano")
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("Número no finito")
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Número inválido: {value!r}") from exc


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError("Fecha sin zona horaria")
        return result.astimezone(timezone.utc)
    except (TypeError, AttributeError) as exc:
        raise ValueError("Fecha inválida") from exc


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False, default=str).encode()).hexdigest()


def implementation_hash():
    root=Path(__file__).resolve().parent
    names=('market_data.py','strategy.py','portfolio.py','simulation.py','evaluation.py')
    return fingerprint({name:sha256((root/name).read_bytes()).hexdigest() for name in names})


def _ohlc(row):
    o, h, lo, c = (number(row[k]) for k in ("open", "high", "low", "close"))
    if not (0 < lo <= min(o, c) <= max(o, c) <= h):
        raise ValueError("OHLC incoherente")


def _unique(rows, key):
    seen = {}
    for row in rows:
        ident = key(row)
        digest = fingerprint(row)
        if ident in seen and seen[ident] != digest:
            raise ValueError(f"Duplicado contradictorio: {ident}")
        seen[ident] = digest


def validate_dataset(data, allowed_symbols):
    try:
        if data["schema_version"] != 1 or data["method_version"] != METHOD_VERSION:
            raise ValueError("Versión de paquete o método incompatible")
        if data["kind"] not in ("synthetic", "historical"):
            raise ValueError("Tipo de datos desconocido")
        expected_feed = "synthetic_consolidated" if data["kind"] == "synthetic" else "sip"
        if data["feed"] != expected_feed or data["adjustment"] != "raw":
            raise ValueError("Se requiere feed consolidado y precios nominales sin ajustes")
        if not data["source"] or not data["calendar_source"]:
            raise ValueError("Falta procedencia")
        timestamp(data["frozen_at"])
        sessions = data["sessions"]
        dates = [date.fromisoformat(s["date"]) for s in sessions]
        if len(dates) < 255 or dates != sorted(set(dates)):
            raise ValueError("Calendario insuficiente, duplicado o desordenado")
        for s in sessions:
            opened, closed = timestamp(s["open"]), timestamp(s["close"])
            if closed <= opened or closed-opened < timedelta(minutes=31):
                raise ValueError("Sesión inválida")
            local_open,local_close=opened.astimezone(ZoneInfo('America/New_York')),closed.astimezone(ZoneInfo('America/New_York'))
            if local_open.date().isoformat()!=s['date'] or local_close.date().isoformat()!=s['date']:
                raise ValueError('Fecha y horario de sesión incoherentes')
        by_date = {s["date"]: s for s in sessions}
        if data["evaluation_start"] not in by_date or data["evaluation_end"] not in by_date:
            raise ValueError("Ventana fuera del calendario")
        if data["evaluation_start"] > data["evaluation_end"] or dates.index(date.fromisoformat(data["evaluation_start"])) < 254:
            raise ValueError("Ventana sin calentamiento de 254 sesiones")
        if data['kind']=='historical' and data['evaluation_start']<'2024-05-28':
            raise ValueError('Este modelo usa liquidación T+1 desde 2024-05-28')
        symbols, identifiers, source_symbols = set(), set(), set()
        for item in data["instruments"]:
            if item["source_symbol"] not in set(allowed_symbols):
                raise ValueError("Instrumento fuera de Cartera CA")
            if not all(isinstance(item[k],str) and item[k] for k in ('symbol','id','type','sector')):
                raise ValueError('Identidad incompleta')
            if item["symbol"] in symbols or item["id"] in identifiers or item['source_symbol'] in source_symbols:
                raise ValueError("Identificador o símbolo ambiguo")
            if not isinstance(item["eligible"], bool) or not item["source"]:
                raise ValueError("Elegibilidad o procedencia inválida")
            if item['eligible'] and (item['type'] not in TYPES or item['sector'] not in SECTORS):
                raise ValueError('Tipo o sector no admisible para un instrumento elegible')
            timestamp(item["known_at"])
            date.fromisoformat(item["valid_from"])
            if item["valid_to"]:
                date.fromisoformat(item["valid_to"])
                if item["valid_to"] < item["valid_from"]:
                    raise ValueError("Vigencia de instrumento invertida")
            symbols.add(item["symbol"])
            identifiers.add(item["id"])
            source_symbols.add(item['source_symbol'])
        if not {"SPY", "LLY"} <= symbols:
            raise ValueError("Faltan SPY/LLY del estado inicial")
        for row in data["daily"]:
            if row["symbol"] not in symbols or row["session"] not in by_date:
                raise ValueError("Vela fuera de manifiesto/calendario")
            _ohlc(row)
            if number(row["volume"]) < 0:
                raise ValueError("Volumen negativo")
            if timestamp(row["available_at"]) < timestamp(by_date[row["session"]]["close"]) or not row["source"]:
                raise ValueError("Disponibilidad de cierre/procedencia inválida")
        _unique(data["daily"], lambda r: (r["symbol"], r["session"], timestamp(r["available_at"])))
        for row in data["vix"]:
            if row["session"] not in by_date or number(row["close"]) <= 0 or not row["source"]:
                raise ValueError("VIX inválido")
            if timestamp(row["available_at"]) < timestamp(by_date[row["session"]]["close"]):
                raise ValueError("VIX disponible antes del cierre")
        _unique(data["vix"], lambda r: (r["session"], timestamp(r["available_at"])))
        for row in data["earnings"]:
            if row["symbol"] not in symbols or timestamp(row["available_at"]) < timestamp(row["published_at"]):
                raise ValueError("Resultado trimestral inválido")
        _unique(data["earnings"], lambda r: (r["id"], timestamp(r["available_at"])))
        for row in data["actions"]:
            if row["symbol"] not in symbols or row["session"] not in by_date or not row["source"]:
                raise ValueError("Acción corporativa inválida")
            timestamp(row["available_at"])
            if row["kind"] == "split":
                if number(row["ratio"]) <= 0:
                    raise ValueError("Ratio de split inválido")
            elif row["kind"] == "dividend":
                if number(row["per_share"]) < 0 or row["pay_session"] not in by_date or row["pay_session"] < row["session"]:
                    raise ValueError("Dividendo inválido")
            else:
                raise ValueError("Acción corporativa no soportada")
        _unique(data["actions"], lambda r: r["id"])
        for row in data["events"]:
            stamp, available = timestamp(row["timestamp"]), timestamp(row["available_at"])
            if available < stamp or not row["source"]:
                raise ValueError("Evento disponible antes de ocurrir")
            kind = row["kind"]
            if kind in ("quote", "bar"):
                if row["symbol"] not in symbols:
                    raise ValueError("Evento fuera del manifiesto")
                if kind == "quote":
                    if not 0 < number(row["bid"]) <= number(row["ask"]):
                        raise ValueError("Bid/ask inválido")
                    if type(row["ask_size"]) is not int or row["ask_size"] < 0:
                        raise ValueError("Profundidad inválida")
                else:
                    _ohlc(row)
                    if timestamp(row["start"]) >= stamp:
                        raise ValueError("Intervalo intradiario inválido")
            elif kind == "flow":
                number(row["amount"])
            elif kind == "fault":
                if data["kind"] != "synthetic" or row["action"] not in ("disconnect", "reconnect", "protection_fail", "protection_ok"):
                    raise ValueError("Fallo artificial sólo permitido en escenarios sintéticos")
            else:
                raise ValueError("Tipo de evento no soportado")
        _unique(data["events"], lambda r: r["id"])
        return data
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError(f"Paquete incompleto o mal formado: {exc}") from exc


def load_dataset(path, allowed_symbols):
    data = json.loads(Path(path).read_text(), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"JSON no finito: {v}")))
    return validate_dataset(data, allowed_symbols)


def cutoff(data, index):
    return timestamp(data["sessions"][index]["close"]) + timedelta(hours=1)


def history_as_of(data, symbol, index):
    if index < 253:
        return []
    required = [s["date"] for s in data["sessions"][index-253:index+1]]
    allowed = set(required)
    cut = cutoff(data, index)
    selected = {}
    for row in data["daily"]:
        if row["symbol"] != symbol or row["session"] not in allowed or timestamp(row["available_at"]) > cut:
            continue
        prev = selected.get(row["session"])
        if prev is None or timestamp(row["available_at"]) > timestamp(prev["available_at"]):
            selected[row["session"]] = row
    if set(selected) != allowed:
        return []
    actions = [a for a in {a['id']:a for a in data['actions']}.values() if a["kind"] == "split" and a["symbol"] == symbol
               and a["session"] <= required[-1] and timestamp(a["available_at"]) <= cut]
    result = []
    for day in required:
        row = deepcopy(selected[day])
        factor = Decimal(1)
        for a in actions:
            if day < a["session"]:
                factor *= number(a["ratio"])
        if factor != 1:
            for k in ("open", "high", "low", "close"):
                row[k] = str(number(row[k])/factor)
            row["volume"] = number(row["volume"])*factor
        result.append(row)
    return result

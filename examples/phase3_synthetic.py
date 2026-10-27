"""Generate explicitly fictional CA market data for integration tests, never a backtest."""

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo


SYMBOLS = ["AMD", "AMZN", "AVGO", "AZO", "BBAI", "CAT", "CAVA", "CCJ", "CMG", "CRWD",
           "DDOG", "DKNG", "GEV", "GOOG", "GOOGL", "INTC", "JPM", "KO", "LLY", "NVDA", "SPY", "TSLA"]


def make_dataset(count=258, intraday=True):
    zone = ZoneInfo("America/New_York")
    sessions, day = [], date(2025, 1, 1)
    while len(sessions) < count:
        if day.weekday() < 5:
            sessions.append({"date": day.isoformat(),
                             "open": datetime.combine(day, time(9, 30), zone).isoformat(),
                             "close": datetime.combine(day, time(16), zone).isoformat()})
        day += timedelta(days=1)
    data = {"schema_version": 1, "kind": "synthetic", "method_version": "CA-S2-1.0.0",
            "feed": "synthetic_consolidated", "adjustment": "raw",
            "source": "synthetic://CA-testing-only", "calendar_source": "fictional weekdays; NOT NYSE calendar",
            "frozen_at": sessions[0]["open"], "evaluation_start": sessions[254]["date"],
            "evaluation_end": sessions[-1]["date"], "sessions": sessions,
            "instruments": [], "daily": [], "vix": [], "earnings": [], "actions": [], "events": []}
    for symbol in SYMBOLS:
        data["instruments"].append({"id": symbol, "source_symbol": symbol, "symbol": symbol,
            "type": "equity_etf" if symbol == "SPY" else "common_stock", "eligible": True,
            "sector": "DIVERSIFIED_EQUITY_ETF" if symbol == "SPY" else "Information Technology",
            "source": data["source"], "known_at": sessions[0]["open"],
            "valid_from": sessions[0]["date"], "valid_to": None})
        for i, session in enumerate(sessions):
            width, volume = Decimal(1), 1000000
            close = Decimal(40) + Decimal("0.1") * i
            if symbol == "SPY":
                close, width = Decimal(760) + Decimal("0.5") * i, Decimal(7)
            elif symbol == "LLY":
                close, width = Decimal(1200) + Decimal("0.2") * i, Decimal(15)
            elif symbol == "TSLA":
                close = Decimal(80) + Decimal("0.05") * i
                if 234 <= i < 249:
                    close, width = Decimal(98) + Decimal("0.02")*(i-234), Decimal("1.2")
                elif 249 <= i < 254:
                    close, width = Decimal(99) + Decimal("0.03")*(i-249), Decimal("0.2")
                elif i >= 254:
                    close, width = Decimal(100) + Decimal("0.2")*(i-254), Decimal("0.1")
                    if i == 254:
                        volume = 2000000
            available = datetime.fromisoformat(session["close"]) + timedelta(minutes=30)
            data["daily"].append({"symbol": symbol, "session": session["date"], "open": str(close),
                "high": str(close+width), "low": str(close-width), "close": str(close), "volume": volume,
                "available_at": available.isoformat(), "source": data["source"]})
            if intraday and i >= 254 and (symbol in ("SPY", "LLY", "TSLA")):
                opened = datetime.fromisoformat(session["open"])
                for minute in range(391):
                    stamp = opened + timedelta(minutes=minute)
                    data["events"].append({"id": f"{symbol}-{i}-{minute}", "kind": "quote", "symbol": symbol,
                        "timestamp": stamp.isoformat(), "available_at": stamp.isoformat(),
                        "bid": str(close-Decimal("0.02")), "ask": str(close+Decimal("0.02")),
                        "ask_size": 10000, "source": data["source"]})
    for session in sessions:
        data["vix"].append({"session": session["date"], "close": "18",
                            "available_at": (datetime.fromisoformat(session["close"])+timedelta(minutes=10)).isoformat(),
                            "source": data["source"]})
    return data


if __name__ == "__main__":
    print(json.dumps(make_dataset(), ensure_ascii=False, indent=2))

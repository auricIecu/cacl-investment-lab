"""Check the arithmetic examples in CA-S2-1.0.0, not a trading engine.

All inputs below are explicit historical references or synthetic values.
No market data, broker, positions or orders are accessed or changed.
Run from the repository root: python examples/ca_method_v1.py
"""

import json
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


def D(value):
    return Decimal(str(value))


def floor(value):
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def cents(value, rounding=ROUND_FLOOR):
    return value.quantize(D("0.01"), rounding=rounding)


def sizing_example(*, cash="83150", gross="16850", sector="0", open_risk="500", adv="100000"):
    # Fixed synthetic portfolio: E=100,000, limit=100, stop=95, no pending orders.
    equity, limit, risk = D(100000), D(100), D(5)
    caps = {
        "risk": floor(D("0.004") * equity / risk),
        "name": floor(D("0.12") * equity / limit),
        "sector": floor((D("0.30") * equity - D(sector)) / limit),
        "gross": floor((D("0.90") * equity - D(gross)) / limit),
        "cash": floor((D(cash) - D("0.10") * equity) / (D("1.001") * limit)),
        "total_risk": floor((D("0.06") * equity - D(open_risk)) / risk),
        "volume": floor(D("0.01") * D(adv)),
    }
    quantity = max(0, min(caps.values()))
    reserve = cents(D(quantity) * limit * D("1.001"), ROUND_CEILING)
    return {"caps": caps, "quantity": quantity, "cash_reserved": reserve,
            "cash_after": D(cash) - reserve, "risk_to_stop": D(quantity) * risk}


def initial_brake(drawdown):
    # Threshold classification only; recovery counters require the future engine.
    d = D(drawdown)
    if not D(0) <= d <= D(1):
        raise ValueError("Drawdown must be between zero and one")
    if d >= D("0.15"):
        return "detenido"
    if d >= D("0.13"):
        return "preservacion"
    if d >= D("0.09"):
        return "defensa"
    if d >= D("0.05"):
        return "reducido"
    return "normal"


def calculate_examples():
    equity_ca = D("977698.96890463")
    video_qty = floor(D(4000) / D("10.72"))
    ca_budget = equity_ca * D("0.004")
    ca_qty = floor(ca_budget / D("10.72"))
    assert video_qty == 373 and D(video_qty) * D("10.72") == D("3998.56")
    assert ca_qty == 364 and D(ca_qty) * D("10.72") == D("3902.08")
    assert D(ca_qty + 1) * D("10.72") > ca_budget

    # The video's vector: 7 technical passes, extension and catalyst do not pass.
    score = [1, 1, 1, 1, 1, 0, 1, 1, 0]
    assert sum(score) == 7
    six_without_catalyst = [1, 1, 1, 1, 1, 0, 1, 0, 0]
    assert sum(six_without_catalyst) == 6
    eps_growth = D("1.20") / D("1.00") - 1
    sales_growth = D(110) / D(100) - 1
    assert eps_growth >= D("0.20") and sales_growth >= D("0.10")
    assert D("1.199") / D(1) - 1 < D("0.20")

    close, atr, low5 = D(100), D(2), D(98)
    planned_limit = cents(close * D("1.005"), ROUND_CEILING)
    planned_stop = cents(min(low5 - D("0.10") * atr, close - 2 * atr))
    planned_target = cents(planned_limit + 2 * (planned_limit - planned_stop), ROUND_CEILING)
    assert (planned_limit, planned_stop, planned_target) == tuple(map(D, ["100.50", "96.00", "109.50"]))

    sizing = {
        "normal": sizing_example(),
        "cash_constrained": sizing_example(cash="10800", gross="89200"),
        "sector_constrained": sizing_example(sector="29950", gross="50000", cash="50000"),
        "risk_constrained": sizing_example(open_risk="5996"),
        "volume_constrained": sizing_example(adv="2500"),
    }
    assert {k: v["quantity"] for k, v in sizing.items()} == {
        "normal": 80, "cash_constrained": 7, "sector_constrained": 0,
        "risk_constrained": 0, "volume_constrained": 25}
    assert sizing["cash_constrained"]["cash_after"] == D("10099.30")
    assert sizing["normal"]["cash_reserved"] == D("8008.00")

    # The future engine also needs market/data/score gates; quantity alone never admits a trade.
    breakout, limit, stop = D(99), D(100), D(95)
    gap_cases = {str(ask): breakout <= ask <= limit for ask in map(D, ["98.99", "99", "100", "100.01"])}
    assert list(gap_cases.values()) == [False, True, True, False]
    risk = limit - stop
    target = limit + 2 * risk
    stop_at_106 = cents(max(stop, limit, D(106) - 2 * D(3)))
    stop_at_109 = cents(max(stop_at_106, limit, D(109) - 2 * D(2)))
    stop_after_decline = cents(max(stop_at_109, limit, D(109) - 2 * D(3)))
    assert (target, stop_at_106, stop_at_109, stop_after_decline) == tuple(map(D, [110, 100, 105, 105]))
    gross_gap_loss = D(80) * (D(90) - limit)
    assert gross_gap_loss == D(-800) and abs(gross_gap_loss) > sizing["normal"]["risk_to_stop"]

    brake_values = ["0.0499", "0.05", "0.0899", "0.09", "0.1299", "0.13", "0.1499", "0.15"]
    brakes = {v: initial_brake(v) for v in brake_values}
    assert list(brakes.values()) == ["normal", "reducido", "reducido", "defensa",
                                    "defensa", "preservacion", "preservacion", "detenido"]
    k = min(D(1), D("0.40") * D(100000) / D(80000), D("0.02") * D(100000) / D(4000))
    reduced_quantities = [floor(D(q) * k) for q in [100, 200]]
    assert k == D("0.5") and reduced_quantities == [50, 100]

    units = D(100000) / D(100)
    units += D(20000) / D(100)
    nav_after_deposit = D(120000) / units
    nav_after_loss = D(114000) / units
    assert nav_after_deposit == D(100) and nav_after_loss == D(95)
    assert 1 - nav_after_loss / D(100) == D("0.05")

    # Saved prices are used only to illustrate the formula. ATRs are invented inputs.
    inherited = {}
    for symbol, quantity, anchor, atr in [("SPY", 134, "769.71", "10"), ("LLY", 51, "1281.72", "30")]:
        anchor, atr = D(anchor), D(atr)
        initial_stop = cents(anchor - 2 * atr)
        risk_per_share = anchor - initial_stop
        risk_dollars = D(quantity) * risk_per_share
        assert D("0.02") <= risk_per_share / anchor <= D("0.08")
        assert risk_dollars <= ca_budget
        inherited[symbol] = {"hypothetical_anchor": anchor, "invented_atr": atr,
                             "stop": initial_stop, "target": cents(anchor + 2 * risk_per_share, ROUND_CEILING),
                             "quantity": quantity, "risk_to_stop": risk_dollars}
    assert sum(p["risk_to_stop"] for p in inherited.values()) == D(5740)

    return {"method_version": "CA-S2-1.0.0", "purpose": "arithmetic_examples_only",
            "video": {"quantity": video_qty, "risk_to_stop": D(video_qty)*D("10.72")},
            "ca": {"equity": equity_ca, "budget": ca_budget, "quantity_by_risk_only": ca_qty,
                   "risk_to_stop": D(ca_qty)*D("10.72")},
            "score": {"video_vector": score, "total": sum(score), "six_without_catalyst": six_without_catalyst},
            "catalyst_threshold": {"eps_growth": eps_growth, "sales_growth": sales_growth},
            "entry_levels": {"close": close, "atr20": atr, "low5": low5,
                             "limit": planned_limit, "stop": planned_stop, "target": planned_target},
            "sizing": sizing, "gap_band": gap_cases,
            "exits": {"target": target, "stop_sequence": [stop_at_106, stop_at_109, stop_after_decline],
                      "gross_gap_loss": gross_gap_loss},
            "brake_thresholds": brakes, "reduction": {"factor": k, "quantities": reduced_quantities},
            "unitization": {"units": units, "nav_after_deposit": nav_after_deposit, "nav_after_loss": nav_after_loss},
            "inherited_hypothetical": inherited}


if __name__ == "__main__":
    print(json.dumps(calculate_examples(), default=str, ensure_ascii=False, indent=2))

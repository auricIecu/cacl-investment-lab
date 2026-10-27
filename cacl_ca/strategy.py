"""Deterministic daily decisions for CA-S2-1.0.0; never sends orders."""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from .market_data import METHOD_VERSION, TYPES, SECTORS, number as D, timestamp, cutoff, history_as_of, fingerprint


def mean(values):
    return sum(values, Decimal(0)) / len(values)


def cent(value, up=False):
    return D(value).quantize(D("0.01"), rounding=ROUND_CEILING if up else ROUND_FLOOR)


def indicators(bars):
    if len(bars) != 254:
        raise ValueError("Se requieren 254 sesiones completas")
    c, h, lo, v = ([D(b[k]) for b in bars] for k in ("close", "high", "low", "volume"))
    tr = [max(h[i]-lo[i], abs(h[i]-c[i-1]), abs(lo[i]-c[i-1])) for i in range(1,len(c))]
    returns = [c[i]/c[i-1]-1 for i in range(1,len(c))]
    avg = mean(returns[-20:])
    vol = (sum((r-avg)**2 for r in returns[-20:])/19*252).sqrt()
    return {"close": c[-1], "previous_close": c[-2], "sma50": mean(c[-50:]), "sma200": mean(c[-200:]),
            "atr20": mean(tr[-20:]), "atr5_previous": mean(tr[-6:-1]), "atr20_previous": mean(tr[-21:-1]),
            "breakout": max(h[-253:-1]), "previous_breakout": max(h[-254:-2]),
            "high252": max(h[-252:]), "low5": min(lo[-5:]),
            "base_width": (max(h[-21:-1])-min(lo[-21:-1]))/max(h[-21:-1]),
            "volume": v[-1], "previous_volume20": mean(v[-21:-1]), "adv20": mean(v[-20:]),
            "adtv20": mean([c[i]*v[i] for i in range(len(c)-20,len(c))]),
            "r63": c[-1]/c[-64]-1, "r126": c[-1]/c[-127]-1,
            "positive63": sum(r>0 for r in returns[-63:]), "vol20": vol}


def catalyst(data, item, index):
    if item["type"] == "equity_etf":
        return 0, "catalyst_not_applicable", None
    cut = cutoff(data,index)
    rows = [r for r in data["earnings"] if r["symbol"] == item["symbol"] and timestamp(r["available_at"]) <= cut]
    if not rows:
        return 0, "catalyst_unverified", None
    r = max(rows, key=lambda x: (timestamp(x["available_at"]), x["id"]))
    if not timestamp(data["sessions"][index-20]["close"]) < timestamp(r["published_at"]) <= cut:
        return 0, "catalyst_expired", r
    try:
        valid = (r["verified"] is True and r["source"] and r["locator"] and r["basis"] == "GAAP"
                 and r["period"] == "quarter" and r["quarter"] == r["prior_quarter"]
                 and r["quarter"] in (1,2,3,4) and r["fiscal_year"] == r["prior_fiscal_year"]+1
                 and r["currency"] == r["prior_currency"] and bool(r["currency"])
                 and r["eps_unit"] == r["prior_eps_unit"] and bool(r["eps_unit"])
                 and r["revenue_unit"] == r["prior_revenue_unit"] and bool(r["revenue_unit"])
                 and D(r["prior_eps"]) > 0 and D(r["prior_revenue"]) > 0)
        passed = valid and D(r["eps"]) >= D("1.2")*D(r["prior_eps"]) and D(r["revenue"]) >= D("1.1")*D(r["prior_revenue"])
        return int(bool(passed)), "verified" if valid else "catalyst_unverified", r
    except (KeyError, ValueError, TypeError):
        return 0, "catalyst_unverified", r


def evaluate_signals(data, index):
    cut = cutoff(data,index)
    session = data["sessions"][index]["date"]
    universe = [i for i in data["instruments"] if i["eligible"] and i["type"] in TYPES]
    usable, histories = {}, {}
    for item in universe:
        if (timestamp(item["known_at"]) > cut or item["valid_from"] > session
                or (item["valid_to"] and item["valid_to"] < session) or item["sector"] not in SECTORS):
            continue
        bars = history_as_of(data,item["symbol"],index)
        if bars:
            usable[item["symbol"]] = indicators(bars)
            histories[item["symbol"]] = bars
    stocks = [i for i in universe if i["type"] != "equity_etf"]
    valid_stocks = [i for i in stocks if i["symbol"] in usable]
    spy = usable.get("SPY")
    vx = [r for r in data["vix"] if r["session"] == session and timestamp(r["available_at"]) <= cut]
    vix = max(vx,key=lambda x:timestamp(x["available_at"])) if vx else None
    breadth = (D(sum(usable[i["symbol"]]["close"] > usable[i["symbol"]]["sma50"] for i in valid_stocks))/len(valid_stocks)
               if valid_stocks else D(0))
    coverage = len(usable) >= 20 and len(usable) >= D("0.8")*len(universe)
    stock_coverage = len(valid_stocks) >=20 and len(valid_stocks) >= D("0.8")*len(stocks)
    market = {"trend": bool(spy and spy["close"]>spy["sma50"]>spy["sma200"]),
              "vix": bool(vix and D(vix["close"])<=25), "breadth": str(breadth),
              "coverage": bool(coverage and stock_coverage)}
    market["passed"] = market["trend"] and market["vix"] and breadth>=D("0.5") and market["coverage"]
    ranked = sorted((i for i in universe if i["symbol"] in usable), key=lambda i:(-usable[i["symbol"]]["r63"], i["id"]))
    top = {i["symbol"] for i in ranked[:(len(ranked)+2)//3]}
    decisions, facts = [], {}
    for item in sorted(data["instruments"], key=lambda i:i["id"]):
        symbol, reasons = item["symbol"], []
        result = {"symbol":symbol, "instrument_id":item["id"], "sector":item["sector"], "reasons":reasons,
                  "points":[], "score":None, "decision":"reject"}
        if symbol not in usable:
            reasons.append("identity_unverified" if item not in universe or timestamp(item["known_at"])>cut
                           else "invalid_data")
            decisions.append(result)
            continue
        f = usable[symbol]
        cat, cat_reason, fact = catalyst(data,item,index)
        if fact:
            facts[symbol] = fact
        base = f["base_width"]<=D("0.15") and f["atr5_previous"]<=D("0.8")*f["atr20_previous"]
        pattern = (f["close"]>f["breakout"] and f["previous_close"]<=f["previous_breakout"] and base
                   and f["volume"]>=D("1.5")*f["previous_volume20"] and f["close"]<=D("1.03")*f["breakout"])
        points = [f["close"]>f["sma50"]>f["sma200"], f["close"]>=D("0.9")*f["high252"],
                  coverage and symbol in top, bool(spy and f["r126"]>spy["r126"]), base,
                  1<=f["close"]/f["sma50"]<=D("1.1"), f["positive63"]>=35, f["vol20"]<=D("0.35"), cat]
        limit = cent(f["close"]*D("1.005"),True)
        stop = cent(min(f["low5"]-D("0.1")*f["atr20"], f["close"]-2*f["atr20"]))
        target = cent(limit+2*(limit-stop),True)
        if not market["passed"]: reasons.append("market_filter")
        if not pattern: reasons.append("pattern_failed")
        if f["close"]<10 or f["adtv20"]<20000000: reasons.append("liquidity_filter")
        if sum(points)<6: reasons.append("score_below_six")
        if not (stop>0 and D("0.02")<=(limit-stop)/limit<=D("0.08")): reasons.append("stop_distance")
        result.update(points=list(map(int,points)),score=sum(points),pattern=bool(pattern),
                      catalyst=cat_reason, limit=str(limit),stop=str(stop),target=str(target),
                      breakout=str(f["breakout"]),adv20=str(f["adv20"]),atr20=str(f["atr20"]),
                      relative_strength=str(f["r126"]-spy["r126"]) if spy else None,
                      decision="candidate" if not reasons else "reject")
        decisions.append(result)
    evidence = {"history":histories,"vix":vix,"facts":facts,"instruments":data["instruments"],"session":session}
    result = {"method_version":METHOD_VERSION,"session":session,"cutoff":cut.isoformat(),
              "inputs_hash":fingerprint(evidence),"market":market,"decisions":decisions}
    result["plan_id"] = fingerprint(result)
    return result

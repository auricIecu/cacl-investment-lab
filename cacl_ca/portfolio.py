"""Deterministic simulated ledger, reservations and capital controls."""

import json
from decimal import Decimal, ROUND_FLOOR

from .market_data import number as D, fingerprint
from .strategy import cent


LIMITS = [("0.004","0.90","0.06",2), ("0.002","0.60","0.03",1),
          ("0","0.40","0.02",0), ("0","0.20","0.01",0), ("0","0","0",0)]
POSITION_MONEY = {"mark","stop","target","anchor","initial_risk","high_close","next_stop","entry_fee","realized"}
ORDER_MONEY = {"limit","stop","target","adv20"}


def floor(value):
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


class Ledger:
    def __init__(self, cash, positions=(), stress=False):
        self.cash = D(cash)
        if self.cash < 0:
            raise ValueError("Efectivo negativo")
        self.positions = {}
        for raw in positions:
            p = dict(raw)
            if type(p["quantity"]) is not int or p["quantity"] <= 0 or p["symbol"] in self.positions:
                raise ValueError("Posición duplicada o cantidad inválida")
            for k in ("mark","anchor","stop","target"):
                p[k] = D(p[k]) if p.get(k) is not None else None
            if p["mark"] <= 0 or p["anchor"] <= 0:
                raise ValueError("Precio inicial inválido")
            p.update(initial_risk=p["anchor"]-p["stop"] if p["stop"] is not None else None,
                     high_close=p["anchor"], next_stop=None, entry_fee=D(0), realized=D(0),
                     protected=p.get("protected",p["stop"] is not None))
            self.positions[p["symbol"]] = p
        self.receivables, self.orders, self.seen, self.audit, self.closed_cycles = [], {}, {}, [], []
        self.index, self.entries_used, self.exits = 0, 0, {}
        self.level, self.streak, self.last_close = 0, 0, None
        self.connected, self.stress = True, stress
        self.fees, self.external_flows = D(0), D(0)
        self.initial_equity = self.equity
        if self.initial_equity <= 0:
            raise ValueError("Patrimonio inicial no positivo")
        self.units = self.initial_equity/D(100)
        self.hwm, self.max_drawdown = D(100), D(0)

    @property
    def equity(self):
        return self.cash + sum((r["amount"] for r in self.receivables),D(0)) + self.gross

    @property
    def gross(self):
        return sum((p["quantity"]*p["mark"] for p in self.positions.values()),D(0))

    @property
    def nav(self):
        return self.equity/self.units

    @property
    def risk(self):
        if any(not p["protected"] or p["stop"] is None for p in self.positions.values()):
            return None
        return sum((p["quantity"]*max(D(0),p["mark"]-p["stop"]) for p in self.positions.values()),D(0))

    @property
    def pending(self):
        return [o for o in self.orders.values() if o["status"]=="open"]

    def commission(self, quantity):
        return max(D(1),D(quantity)*D("0.005")) * (2 if self.stress else 1)

    def cash_reserve(self, quantity, limit):
        nominal = D(quantity)*D(limit)
        return cent(nominal+max(nominal*D("0.001"),self.commission(quantity)),True) if quantity else D(0)

    @property
    def reserved_cash(self):
        return sum((self.cash_reserve(o["quantity"],o["limit"]) for o in self.pending),D(0))

    @property
    def pending_risk(self):
        return sum((o["quantity"]*(o["limit"]-o["stop"]) for o in self.pending),D(0))

    def size(self, plan, equity_cap=None):
        def reject(reason): return {"quantity":0,"reason":reason,"caps":{}}
        if not self.connected: return reject("portfolio_unreconciled")
        if self.risk is None: return reject("protection_failure")
        if self.level>=2: return reject("capital_brake")
        symbol = plan["symbol"]
        if symbol in self.positions or any(o["symbol"]==symbol for o in self.pending):
            return reject("position_exists")
        if symbol in self.exits and self.index-self.exits[symbol]<=5: return reject("cooldown")
        risk_limit,gross_limit,total_limit,quota = LIMITS[self.level]
        if self.entries_used>=quota: return reject("entry_quota")
        if len(self.positions)+len(self.pending)>=12: return reject("position_limit")
        equity = min(self.equity,D(equity_cap)) if equity_cap is not None else self.equity
        limit,stop,adv = D(plan["limit"]),D(plan["stop"]),D(plan["adv20"])
        if equity<=0 or stop<=0 or limit<=stop or adv<=0: return reject("invalid_data")
        if not D("0.02") <= (limit-stop)/limit <= D("0.08"): return reject("stop_distance")
        sector = plan["sector"]
        sector_limit = D("0.20") if sector=="DIVERSIFIED_EQUITY_ETF" else D("0.30")
        sector_value = sum((p["quantity"]*p["mark"] for p in self.positions.values() if p["sector"]==sector),D(0))
        sector_pending = sum((o["quantity"]*o["limit"] for o in self.pending if o["sector"]==sector),D(0))
        pending_nominal = sum((o["quantity"]*o["limit"] for o in self.pending),D(0))
        caps = {"risk":floor(D(risk_limit)*equity/(limit-stop)), "name":floor(D("0.12")*equity/limit),
                "sector":floor((sector_limit*equity-sector_value-sector_pending)/limit),
                "gross":floor((D(gross_limit)*equity-self.gross-pending_nominal)/limit),
                "cash":floor((self.cash-self.reserved_cash-D("0.10")*equity)/(D("1.001")*limit)),
                "total_risk":floor((D(total_limit)*equity-self.risk-self.pending_risk)/(limit-stop)),
                "volume":floor(D("0.01")*adv)}
        qty = max(0,min(caps.values()))
        # Known simulated commission can exceed the method's small nominal cushion.
        while qty and self.cash_reserve(qty,limit)>self.cash-self.reserved_cash-D("0.10")*equity:
            qty-=1
        return {"quantity":qty,"reason":None if qty else "size_zero","caps":caps}

    def reserve(self, intent_id, plan, quantity_limit=None, equity_cap=None):
        digest = fingerprint([plan,quantity_limit,equity_cap])
        if intent_id in self.orders:
            if self.orders[intent_id]["request_hash"] != digest:
                raise ValueError("Intención repetida con contenido distinto")
            return self.orders[intent_id]
        sized = self.size(plan,equity_cap)
        qty = sized["quantity"]
        if quantity_limit is not None:
            if type(quantity_limit) is not int or quantity_limit<0: raise ValueError("Cantidad nocturna inválida")
            qty = min(qty,quantity_limit)
        if not qty:
            return dict(sized,quantity=0,status="rejected")
        order = dict(plan,id=intent_id,quantity=qty,status="open",request_hash=digest,entered_index=self.index,
                     equity_cap=str(equity_cap if equity_cap is not None else self.equity))
        for k in ORDER_MONEY: order[k] = D(order[k])
        self.orders[intent_id] = order
        self.entries_used+=1
        self.audit.append({"kind":"reserve","id":intent_id,"quantity":qty,"symbol":plan["symbol"]})
        return order

    def cancel(self, intent_id):
        order = self.orders[intent_id]
        if order["status"]=="open":
            order["status"]="canceled"
            self.audit.append({"kind":"cancel","id":intent_id})

    def _duplicate(self, event_id, payload):
        digest = fingerprint(payload)
        if event_id in self.seen:
            if self.seen[event_id] != digest: raise ValueError("Evento repetido con contenido distinto")
            return True
        return False

    def _record(self,event_id,payload):
        self.seen[event_id]=fingerprint(payload)
        self.audit.append(dict(payload,id=event_id))

    def buy_fill(self,intent_id,quantity,price,event_id,protected=True,when=None):
        price=D(price)
        event={"kind":"buy","intent":intent_id,"quantity":quantity,"price":str(price),"protected":protected,"when":when}
        if self._duplicate(event_id,event): return False
        order=self.orders[intent_id]
        if (order["status"]!="open" or type(quantity) is not int or not 0<quantity<=order["quantity"]
                or not 0<price<=order["limit"] or order["symbol"] in self.positions):
            raise ValueError("Fill de compra inválido")
        fee=self.commission(quantity)
        if quantity*price+fee>self.cash: raise ValueError("Fill sin efectivo")
        self.cash-=quantity*price+fee
        self.fees+=fee
        self.positions[order["symbol"]]={"symbol":order["symbol"],"quantity":quantity,"mark":price,
            "anchor":order["limit"],"entry_price":str(price),"stop":order["stop"],"target":order["target"],
            "initial_risk":order["limit"]-order["stop"],"high_close":order["limit"],"next_stop":None,
            "sector":order["sector"],"entered_index":self.index,"inherited":False,"protected":protected,
            "entry_fee":fee,"realized":D(0),"entry_time":when,"intent_id":intent_id}
        order["status"]="filled" if quantity==order["quantity"] else "partial_canceled"
        self._record(event_id,event)
        return True

    def sell(self,symbol,quantity,price,index,event_id,reason):
        price=D(price)
        event={"kind":"sell","symbol":symbol,"quantity":quantity,"price":str(price),"index":index,"reason":reason}
        if self._duplicate(event_id,event): return False
        if symbol not in self.positions or type(quantity) is not int or not 0<quantity<=self.positions[symbol]["quantity"] or price<=0:
            raise ValueError("Venta inválida o superior a posición")
        p=self.positions[symbol]
        fee=self.commission(quantity)
        allocated_fee=p["entry_fee"]*quantity/p["quantity"]
        realized=quantity*(price-D(p.get("entry_price",p["anchor"])))-fee-allocated_fee
        p["realized"]+=realized
        p["entry_fee"]-=allocated_fee
        p["quantity"]-=quantity
        self.fees+=fee
        self.receivables.append({"amount":quantity*price-fee,"due":index+1,"kind":"sale"})
        if not p["quantity"]:
            self.closed_cycles.append({"symbol":symbol,"inherited":p["inherited"],"pnl":str(p["realized"]),
                                       "entry_index":p["entered_index"],"exit_index":index,"reason":reason})
            self.exits[symbol]=index
            del self.positions[symbol]
        self._record(event_id,event)
        return True

    def open_session(self,index):
        if index<self.index: raise ValueError("El reloj no puede retroceder")
        if index!=self.index:
            self.index,self.entries_used=index,0
        self.cash+=sum((r["amount"] for r in self.receivables if r["due"]<=index),D(0))
        self.receivables=[r for r in self.receivables if r["due"]>index]

    def mark(self,symbol,price):
        price=D(price)
        if price<=0: raise ValueError("Marca no positiva")
        if symbol in self.positions: self.positions[symbol]["mark"]=price

    def flow(self,amount,event_id):
        amount=D(amount)
        event={"kind":"flow","amount":str(amount)}
        if self._duplicate(event_id,event): return False
        if self.nav<=0 or self.cash+amount<0 or self.equity+amount<=0:
            raise ValueError("Flujo incompatible con saldo/unidades")
        self.units+=amount/self.nav
        self.cash+=amount
        self.external_flows+=amount
        self._record(event_id,event)
        return True

    def dividend(self,symbol,per_share,pay_index,event_id):
        per_share=D(per_share)
        event={"kind":"dividend","symbol":symbol,"per_share":str(per_share),"due":pay_index}
        if self._duplicate(event_id,event): return False
        if per_share<0 or pay_index<self.index: raise ValueError("Dividendo inválido")
        quantity=self.positions.get(symbol,{}).get("quantity",0)
        self.receivables.append({"amount":per_share*quantity,"due":pay_index,"kind":"dividend"})
        self._record(event_id,event)
        return True

    def split(self,symbol,ratio,event_id):
        ratio=D(ratio)
        event={"kind":"split","symbol":symbol,"ratio":str(ratio)}
        if self._duplicate(event_id,event): return False
        if ratio<=0: raise ValueError("Split inválido")
        p=self.positions.get(symbol)
        if p:
            quantity=p["quantity"]*ratio
            if quantity!=floor(quantity): raise ValueError("Split fraccional requiere comprobante de efectivo")
            p["quantity"]=int(quantity)
            for k in ("mark","anchor","stop","target","initial_risk","high_close","next_stop"):
                if p[k] is not None: p[k]/=ratio
            if "entry_price" in p: p["entry_price"]=str(D(p["entry_price"])/ratio)
        for order in self.pending:
            if order["symbol"]==symbol: self.cancel(order["id"])
        self._record(event_id,event)
        return True

    def update_brake(self,close_session=None):
        self.hwm=max(self.hwm,self.nav)
        dd=max(D(0),1-self.nav/self.hwm)
        self.max_drawdown=max(self.max_drawdown,dd)
        severity=sum(dd>=D(x) for x in ("0.05","0.09","0.13","0.15"))
        if severity>self.level:
            self.level,self.streak=severity,0
        if close_session is not None and close_session!=self.last_close:
            self.last_close=close_session
            if 1<=self.level<=3:
                threshold=(D("0.04"),D("0.08"),D("0.12"))[self.level-1]
                self.streak=self.streak+1 if dd<threshold else 0
                if self.streak>=5:
                    self.level,self.streak=max(severity,self.level-1),0
        return {"level":self.level,"drawdown":dd,"nav":self.nav}

    def reduction_targets(self):
        if self.risk is None: return None
        _,gross_cap,risk_cap,_=LIMITS[self.level]
        if self.level==4 or self.equity<=0:
            return {s:0 for s in self.positions}
        ratios=[D(1)]
        if self.gross: ratios.append(D(gross_cap)*self.equity/self.gross)
        if self.risk: ratios.append(D(risk_cap)*self.equity/self.risk)
        k=max(D(0),min(ratios))
        return {s:floor(p["quantity"]*k) for s,p in self.positions.items()}

    def queue_stop(self,symbol,close,atr):
        p=self.positions[symbol]
        close,atr=D(close),D(atr)
        if close<=0 or atr<=0: raise ValueError("Datos inválidos para trailing")
        p["high_close"]=max(p["high_close"],close)
        if p["stop"] is not None and p["high_close"]>=p["anchor"]+p["initial_risk"]:
            p["next_stop"]=cent(max(p["stop"],p["anchor"],p["high_close"]-2*atr))

    def activate_stop(self,symbol):
        p=self.positions[symbol]
        if p["next_stop"] is not None:
            p["stop"]=max(p["stop"],p["next_stop"])
            p["next_stop"]=None

    def snapshot(self):
        return json.loads(json.dumps(self.__dict__,default=str,sort_keys=True))

    @classmethod
    def restore(cls,state):
        obj=cls.__new__(cls)
        obj.__dict__=json.loads(json.dumps(state))
        for key in ("cash","fees","external_flows","initial_equity","units","hwm","max_drawdown"):
            obj.__dict__[key]=D(obj.__dict__[key])
        for p in obj.positions.values():
            for k in POSITION_MONEY:
                if p.get(k) is not None: p[k]=D(p[k])
        for order in obj.orders.values():
            for k in ORDER_MONEY: order[k]=D(order[k])
        for r in obj.receivables: r["amount"]=D(r["amount"])
        return obj

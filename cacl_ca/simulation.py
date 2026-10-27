"""Offline event replay. All fills are explicit simulation assumptions, never broker orders."""

import heapq
import json
from datetime import timedelta

from .market_data import number as D, timestamp, fingerprint, validate_dataset, history_as_of, cutoff, METHOD_VERSION, implementation_hash
from .strategy import evaluate_signals, indicators, cent
from .portfolio import Ledger, LIMITS, floor


class Simulator:
    def __init__(self,data,snapshot,stress=False):
        self.data=validate_dataset(data,[s['source_symbol'] for s in snapshot['symbols']])
        self.reference=snapshot
        self.stress=stress
        self.slip=D('0.002' if stress else '0.0005')
        self.input_hash=fingerprint(data)
        self.engine_hash=implementation_hash()
        self.reference_hash=fingerprint(snapshot)
        self.queue=[]
        self.sequence=0
        self.ledger=None
        self.benchmark=None
        self.benchmark_valid=True
        self.quotes={}
        self.marks_at={}
        self.handled={}
        self.issues=[]
        self.plans=[]
        self.current_plan=None
        self.execution_decisions=[]
        self.equity_curve=[]
        self.pending_exits={}
        self.protection_ok=True
        self.execution_halt=False
        self.aborted=False
        self.index=None
        self.now=None
        self.dates=[s['date'] for s in data['sessions']]
        self.first=self.dates.index(data['evaluation_start'])
        self.last=self.dates.index(data['evaluation_end'])
        start=timestamp(data['sessions'][self.first]['open'])
        end=cutoff(data,self.last)
        for index in range(self.first,self.last+1):
            session=data['sessions'][index]
            opened,closed=timestamp(session['open']),timestamp(session['close'])
            self._push(opened,20,'open',{'index':index})
            self._push(opened+timedelta(minutes=5),40,'entries',{'index':index})
            self._push(opened+timedelta(minutes=30),45,'expire',{'index':index})
            self._push(closed,50,'close',{'index':index})
            self._push(cutoff(data,index),60,'plan',{'index':index})
            tick=opened
            while tick<=closed:
                self._push(tick,30,'tick',{'index':index})
                tick+=timedelta(minutes=1)
        unique={}
        for row in data['events']:
            unique.setdefault(row['id'],row)
        for row in unique.values():
            at=timestamp(row['available_at'])
            if start<=at<=end:
                priority=10 if row['kind']=='quote' else 15
                self._push(at,priority,'external',row)
        for action in {a['id']:a for a in data['actions']}.values():
            index=self.dates.index(action['session'])
            if self.first<=index<=self.last:
                effective=timestamp(data['sessions'][index]['open'])
                self._push(max(effective,timestamp(action['available_at'])),5,'action',action)

    def _push(self,when,priority,kind,payload):
        self.sequence+=1
        heapq.heappush(self.queue,(when,priority,self.sequence,kind,payload))

    def _issue(self,code,symbol=None):
        issue={'code':code,'symbol':symbol,'session':self.dates[self.index] if self.index is not None else None}
        if issue not in self.issues: self.issues.append(issue)

    def _quote(self,symbol,seconds=5):
        q=self.quotes.get(symbol)
        if not q or not timedelta(0)<=self.now-timestamp(q['timestamp'])<=timedelta(seconds=seconds):
            return None
        return q

    def _regular(self):
        if self.index is None: return False
        s=self.data['sessions'][self.index]
        return timestamp(s['open'])<=self.now<=timestamp(s['close'])

    def _fresh(self):
        if self.ledger is None: return False
        symbols=set(self.ledger.positions) | (set(self.benchmark.positions) if self.benchmark else set())
        return all(symbol in self.marks_at and timedelta(0)<=self.now-timestamp(self.marks_at[symbol])<=timedelta(seconds=60)
                   for symbol in symbols)

    def _bootstrap(self):
        positions=[]
        for p in self.reference['positions']:
            if not p['included']: continue
            symbol=p['symbol']
            if symbol not in ('SPY','LLY'): raise ValueError('Política heredada sólo definida para SPY y LLY')
            quote=self._quote(symbol)
            bars=history_as_of(self.data,symbol,self.index-1)
            item=next((i for i in self.data['instruments'] if i['symbol']==symbol),None)
            if (not quote or not bars or not item or not item['eligible'] or timestamp(item['known_at'])>self.now
                    or item['valid_from']>self.dates[self.index] or (item['valid_to'] and item['valid_to']<self.dates[self.index])):
                raise ValueError('Datos iniciales incompletos')
            price=(D(quote['bid'])+D(quote['ask']))/2
            atr=indicators(bars)['atr20']
            stop=cent(price-2*atr)
            qty=D(p['quantity'])
            if qty!=floor(qty) or qty<=0 or not (stop>0 and D('0.02')<=(price-stop)/price<=D('0.08')):
                raise ValueError('Posición inicial incompatible con método')
            positions.append({'symbol':symbol,'quantity':int(qty),'mark':price,'anchor':price,'stop':stop,
                              'target':cent(price+2*(price-stop),True),'sector':item['sector'],
                              'entered_index':self.index,'inherited':True,'entry_time':self.now.isoformat()})
        if {p['symbol'] for p in positions}!={'SPY','LLY'}:
            raise ValueError('Faltan las dos posiciones de apertura')
        book=Ledger(self.reference['balances']['cash'],positions,self.stress)
        for p in book.positions.values():
            if p['quantity']*p['initial_risk']>D('0.004')*book.equity or p['quantity']*p['mark']>D('0.12')*book.equity:
                raise ValueError('Riesgo/concentración de posición heredada excedido')
        for sector in {p['sector'] for p in positions}:
            value=sum((p['quantity']*p['mark'] for p in book.positions.values() if p['sector']==sector),D(0))
            if value>(D('0.20') if sector=='DIVERSIFIED_EQUITY_ETF' else D('0.30'))*book.equity:
                raise ValueError('Concentración sectorial heredada excedida')
        if book.risk>D('0.06')*book.equity or book.gross>D('0.90')*book.equity or book.cash<D('0.10')*book.equity:
            raise ValueError('Estado heredado fuera de límites agregados')
        book.open_session(self.index)
        book.entries_used=2
        self.ledger=book
        quote=self._quote('SPY')
        price=cent(D(quote['ask'])*(1+self.slip),True)
        qty=floor(book.equity/price)
        while qty and qty*price+book.commission(qty)>book.equity: qty-=1
        benchmark=Ledger(book.equity-qty*price-book.commission(qty),[{
            'symbol':'SPY','quantity':qty,'mark':book.positions['SPY']['mark'],'anchor':price,
            'stop':None,'target':None,'sector':'DIVERSIFIED_EQUITY_ETF','entered_index':self.index,'inherited':True}],self.stress)
        benchmark.initial_equity=book.equity
        benchmark.units=book.equity/100
        benchmark.fees=book.commission(qty)
        benchmark.open_session(self.index)
        self.benchmark=benchmark

    def _exit(self,symbol,quantity,price,reason,key):
        if symbol not in self.ledger.positions or quantity<=0: return
        quantity=min(quantity,self.ledger.positions[symbol]['quantity'])
        self.ledger.sell(symbol,quantity,price,self.index,key,reason)
        if symbol not in self.ledger.positions: self.pending_exits.pop(symbol,None)

    def _exit_at_quote(self,symbol,reason):
        q=self._quote(symbol)
        if not q or not self._regular() or not self.ledger.connected:
            self.pending_exits[symbol]=reason
            return False
        if symbol not in self.ledger.positions:
            self.pending_exits.pop(symbol,None)
            return True
        price=cent(D(q['bid'])*(1-self.slip))
        self._exit(symbol,self.ledger.positions[symbol]['quantity'],price,reason,
                   f'exit:{reason}:{symbol}:{self.now.isoformat()}')
        return True

    def _fill(self,order,quote):
        if order['status']!='open' or not self._regular(): return
        if not self._quote(order['symbol']): return
        if not self.ledger.connected:
            self._issue('unobserved_execution_risk',order['symbol'])
            return
        if not self._fresh() or self.execution_halt:
            self.ledger.cancel(order['id'])
            return
        self.ledger.update_brake()
        recheck=Ledger.restore(self.ledger.snapshot())
        recheck.orders[order['id']]['status']='canceled'
        recheck.entries_used=max(0,recheck.entries_used-1)
        permitted=recheck.size(order,order['equity_cap'])['quantity']
        if not permitted:
            self.ledger.cancel(order['id'])
            return
        order['quantity']=min(order['quantity'],permitted)
        opened=timestamp(self.data['sessions'][self.index]['open'])
        if self.now>=opened+timedelta(minutes=30):
            if self.ledger.connected: self.ledger.cancel(order['id'])
            else: self._issue('cancellation_unconfirmed',order['symbol'])
            return
        ask=D(quote['ask'])
        price=cent(ask*(1+self.slip),True)
        if price>order['limit'] or quote['ask_size']==0: return
        quantity=min(order['quantity'],quote['ask_size'])
        self.ledger.buy_fill(order['id'],quantity,price,f"fill:{order['id']}",self.protection_ok,self.now.isoformat())
        if quantity<order['quantity']: self._issue('partial_fill',order['symbol'])
        if not self.protection_ok:
            self.execution_halt=True
            self._issue('protection_failure',order['symbol'])
            self._push(self.now+timedelta(seconds=5),25,'protection_timeout',{'symbol':order['symbol']})
        else:
            self._protect_at_quote(order['symbol'],f"post-fill:{order['id']}")

    def _protect_at_quote(self,symbol,key):
        quote=self._quote(symbol)
        if not quote: return
        p=self.ledger.positions.get(symbol)
        if p and p['protected']:
            bid=D(quote['bid'])
            if bid<=p['stop']:
                self._exit(symbol,p['quantity'],cent(bid*(1-self.slip)),'stop',f'stop:{key}')
            elif bid*(1-self.slip)>=p['target']:
                self._exit(symbol,p['quantity'],max(p['target'],cent(bid*(1-self.slip))),'target',f'target:{key}')
        if symbol in self.pending_exits: self._exit_at_quote(symbol,self.pending_exits[symbol])

    def _activate_pending_stop(self,symbol):
        if not self.ledger.connected: return
        p=self.ledger.positions.get(symbol)
        quote=self._quote(symbol)
        if p and p['next_stop'] is not None and quote:
            if p['next_stop']>=D(quote['bid']): self._exit_at_quote(symbol,'trailing')
            else: self.ledger.activate_stop(symbol)

    def _external(self,event):
        if event['id'] in self.handled: return
        self.handled[event['id']]=fingerprint(event)
        kind=event['kind']
        if kind=='quote':
            symbol=event['symbol']
            previous=self.quotes.get(symbol)
            if previous and timestamp(previous['timestamp'])>timestamp(event['timestamp']): return
            self.quotes[symbol]=event
            if self.ledger is None:
                self.marks_at[symbol]=event['timestamp']
                return
            self.marks_at[symbol]=event['timestamp']
            mid=(D(event['bid'])+D(event['ask']))/2
            self.ledger.mark(symbol,mid)
            self.benchmark.mark(symbol,mid)
            if not self._regular() or not self._quote(symbol): return
            self._protect_at_quote(symbol,event['id'])
            self._activate_pending_stop(symbol)
            for order in list(self.ledger.pending):
                if order['symbol']==symbol: self._fill(order,event)
        elif self.ledger is not None:
            if kind=='bar':
                symbol=event['symbol']
                if not self._regular(): return
                p=self.ledger.positions.get(symbol)
                # A whole bar that overlaps entry cannot prove post-entry stop/target touches.
                if p and p['protected'] and timestamp(event['start'])>=timestamp(p['entry_time']):
                    if D(event['low'])<=p['stop']:
                        price=cent(min(D(event['open']),p['stop'])*(1-self.slip))
                        self._exit(symbol,p['quantity'],price,'stop',f"bar-stop:{event['id']}")
                    elif D(event['high'])*(1-self.slip)>=p['target']:
                        self._exit(symbol,p['quantity'],p['target'],'target',f"bar-target:{event['id']}")
                if symbol not in self.marks_at or timestamp(self.marks_at[symbol])<=timestamp(event['timestamp']):
                    self.ledger.mark(symbol,event['close'])
                    self.benchmark.mark(symbol,event['close'])
                    self.marks_at[symbol]=event['timestamp']
            elif kind=='flow':
                if not self._fresh():
                    self.execution_halt=True
                    self._issue('flow_without_valuation')
                    return
                self.ledger.flow(event['amount'],event['id'])
                # shortcut: no benchmark liquidation policy; suppress comparison if cash cannot fund a withdrawal.
                if self.benchmark_valid:
                    try: self.benchmark.flow(event['amount'],event['id'])
                    except ValueError:
                        self.benchmark_valid=False
                        self._issue('benchmark_flow_unavailable')
            elif kind=='fault':
                action=event['action']
                if action=='disconnect':
                    self.ledger.connected=False
                    self._issue('disconnected')
                elif action=='reconnect': self.ledger.connected=True
                elif action=='protection_fail': self.protection_ok=False
                elif action=='protection_ok': self.protection_ok=True

    def _entries(self):
        if not self.current_plan or self.current_plan['index']!=self.index-1: return
        for decision in self.current_plan['candidates']:
            symbol=decision['symbol']
            reason=None
            quote=self._quote(symbol)
            if self.execution_halt or not self.ledger.connected or not self._fresh(): reason='portfolio_unreconciled'
            elif not quote: reason='stale_quote'
            else:
                bid,ask=D(quote['bid']),D(quote['ask'])
                if not D(decision['breakout'])<=ask<=D(decision['limit']): reason='gap_outside_band'
                elif (ask-bid)/((ask+bid)/2)>D('0.002'): reason='spread_exceeded'
            if reason is None:
                intent=fingerprint([METHOD_VERSION,self.current_plan['plan_id'],self.dates[self.index],symbol,'entry'])
                order=self.ledger.reserve(intent,decision,decision['planned_quantity'],self.current_plan['equity'])
                if order['status']=='rejected': reason=order['reason'] or 'size_zero'
                else:
                    self._fill(order,quote)
                    reason='submitted'
            self.execution_decisions.append({'session':self.dates[self.index],'symbol':symbol,'reason':reason,'when':self.now.isoformat()})

    def _tick(self,close=False):
        if not self._fresh():
            self._issue('stale_marks')
            return
        state=self.ledger.update_brake(self.index if close else None)
        self.benchmark.update_brake(self.index if close else None)
        if self.ledger.level>=2 or self.execution_halt:
            if self.ledger.connected:
                for order in list(self.ledger.pending): self.ledger.cancel(order['id'])
        targets=self.ledger.reduction_targets()
        if targets and any(targets[s]<p['quantity'] for s,p in self.ledger.positions.items()):
            if self.ledger.connected:
                for order in list(self.ledger.pending): self.ledger.cancel(order['id'])
                for symbol in sorted(targets):
                    p=self.ledger.positions.get(symbol)
                    q=self._quote(symbol)
                    if p and q and targets[symbol]<p['quantity']:
                        self._exit(symbol,p['quantity']-targets[symbol],cent(D(q['bid'])*(1-self.slip)),
                                   'capital_brake',f'reduce:{self.now.isoformat()}:{symbol}')
        if close:
            self.equity_curve.append({'session':self.dates[self.index],'equity':str(self.ledger.equity),
                                     'nav':str(self.ledger.nav),'drawdown':str(state['drawdown']),
                                     'level':self.ledger.level,'benchmark_nav':str(self.benchmark.nav) if self.benchmark_valid else None})

    def _plan(self):
        plan=evaluate_signals(self.data,self.index)
        virtual=Ledger.restore(self.ledger.snapshot())
        virtual.open_session(self.index+1)
        candidates=[]
        selected=sorted((d for d in plan['decisions'] if d['decision']=='candidate'),
                        key=lambda d:(-d['score'],-D(d['relative_strength']),d['instrument_id']))
        for d in selected:
            reserved=virtual.reserve(f"night:{plan['plan_id']}:{d['symbol']}",d)
            d['planned_quantity']=reserved['quantity']
            d['portfolio_reason']=reserved.get('reason')
            if reserved['quantity']>0: candidates.append(dict(d))
        self.plans.append(plan)
        self.current_plan={'index':self.index,'plan_id':plan['plan_id'],'candidates':candidates,'equity':str(self.ledger.equity)}
        for symbol in self.ledger.positions:
            bars=history_as_of(self.data,symbol,self.index)
            if bars:
                f=indicators(bars)
                self.ledger.queue_stop(symbol,f['close'],f['atr20'])
            else:
                self._issue('missing_trailing_data',symbol)
                self.execution_halt=True

    def _action(self,action):
        if self.ledger is None: return
        effective=timestamp(self.data['sessions'][self.dates.index(action['session'])]['open'])
        if timestamp(action['available_at'])>effective:
            self.execution_halt=True
            self._issue('late_corporate_action',action['symbol'])
            return
        for book in (self.ledger,self.benchmark):
            try:
                if action['kind']=='split': book.split(action['symbol'],action['ratio'],action['id'])
                else: book.dividend(action['symbol'],action['per_share'],self.dates.index(action['pay_session']),action['id'])
            except ValueError:
                self.execution_halt=True
                self._issue('corporate_action_unreconciled',action['symbol'])

    def run(self,until=None):
        while self.queue and not self.aborted:
            if until is not None and self.queue[0][0]>until: break
            self.now,_,_,kind,payload=heapq.heappop(self.queue)
            if kind=='external': self._external(payload); continue
            if kind=='action': self._action(payload); continue
            if 'index' in payload: self.index=payload['index']
            if kind=='open':
                if self.ledger is None:
                    try: self._bootstrap()
                    except ValueError as exc:
                        self._issue('initialization_blocked')
                        self.issues[-1]['detail']=str(exc)
                        self.ledger=None
                        self.aborted=True
                        continue
                else:
                    self.ledger.open_session(self.index)
                    self.benchmark.open_session(self.index)
                    for symbol in list(self.ledger.positions):
                        self._protect_at_quote(symbol,f'open:{self.index}:{symbol}')
                        self._activate_pending_stop(symbol)
            if self.ledger is None: continue
            if kind=='entries':
                for symbol,p in list(self.ledger.positions.items()):
                    if self.index-p['entered_index']>=21: self._exit_at_quote(symbol,'time_exit')
                self._entries()
            elif kind=='expire':
                if self.ledger.connected:
                    for order in list(self.ledger.pending): self.ledger.cancel(order['id'])
                elif self.ledger.pending: self._issue('cancellation_unconfirmed')
            elif kind=='tick': self._tick()
            elif kind=='close': self._tick(close=True)
            elif kind=='plan': self._plan()
            elif kind=='protection_timeout': self._exit_at_quote(payload['symbol'],'protection_failure')
        return self.result()

    def result(self):
        metrics=None
        incomplete=self.aborted or any(i['code'] in ('stale_marks','missing_trailing_data','flow_without_valuation',
                                                      'late_corporate_action','corporate_action_unreconciled') for i in self.issues)
        if self.ledger is not None and not incomplete:
            metrics={'initial_equity':str(self.ledger.initial_equity),'final_equity':str(self.ledger.equity),
                     'net_pnl':str(self.ledger.equity-self.ledger.initial_equity-self.ledger.external_flows),
                     'unitized_return':str(self.ledger.nav/100-1),'max_drawdown':str(self.ledger.max_drawdown),
                     'fees':str(self.ledger.fees),'closed_new_cycles':sum(not c['inherited'] for c in self.ledger.closed_cycles),
                     'completed_sessions':len(self.equity_curve),'benchmark_return':str(self.benchmark.nav/100-1) if self.benchmark_valid else None,
                     'benchmark_fees':str(self.benchmark.fees)}
        status='data_insufficient' if incomplete else 'synthetic_only' if self.data['kind']=='synthetic' else 'exploratory'
        if self.queue and not self.aborted: status='running'
        return {'status':status,'kind':self.data['kind'],'method_version':METHOD_VERSION,'stress':self.stress,
                'input_hash':self.input_hash,'engine_hash':self.engine_hash,'reference_hash':self.reference_hash,'performance_validation':'not_established',
                'metrics':metrics,'issues':self.issues,'plans':self.plans,'execution_decisions':self.execution_decisions,
                'equity_curve':self.equity_curve,'ledger':self.ledger.snapshot() if self.ledger else None}

    def checkpoint(self):
        state={k:v for k,v in self.__dict__.items() if k not in ('data','reference','ledger','benchmark','slip')}
        state['queue']=[(t.isoformat(),p,n,k,v) for t,p,n,k,v in self.queue]
        state['now']=self.now.isoformat() if self.now else None
        state['ledger']=self.ledger.snapshot() if self.ledger else None
        state['benchmark']=self.benchmark.snapshot() if self.benchmark else None
        state['method_version']=METHOD_VERSION
        return json.loads(json.dumps(state,default=str,sort_keys=True))

    @classmethod
    def restore(cls,data,snapshot,checkpoint):
        if (checkpoint['input_hash']!=fingerprint(data) or checkpoint['reference_hash']!=fingerprint(snapshot)
                or checkpoint['method_version']!=METHOD_VERSION or checkpoint['engine_hash']!=implementation_hash()):
            raise ValueError('Checkpoint no corresponde a datos o método')
        obj=cls(data,snapshot,checkpoint['stress'])
        for k,v in checkpoint.items():
            if k not in ('ledger','benchmark','queue','now','method_version'): setattr(obj,k,v)
        obj.queue=[(timestamp(t),p,n,k,v) for t,p,n,k,v in checkpoint['queue']]
        heapq.heapify(obj.queue)
        obj.now=timestamp(checkpoint['now']) if checkpoint['now'] else None
        obj.ledger=Ledger.restore(checkpoint['ledger']) if checkpoint['ledger'] else None
        obj.benchmark=Ledger.restore(checkpoint['benchmark']) if checkpoint['benchmark'] else None
        return obj


def simulate(data,snapshot,stress=False):
    return Simulator(data,snapshot,stress).run()

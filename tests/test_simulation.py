import unittest
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal as D

from examples.phase3_synthetic import make_dataset, SYMBOLS
from cacl_ca.market_data import timestamp, validate_dataset
from cacl_ca.simulation import Simulator, simulate


def snapshot():
    return {'source_sha256':'reference-test','schema_version':2,'as_of':'2026-10-27',
            'balances':{'cash':'809190.10890463'},
            'positions':[{'symbol':'SPY','quantity':'134','included':True},
                         {'symbol':'LLY','quantity':'51','included':True}],
            'symbols':[{'source_symbol':s} for s in SYMBOLS]}


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=make_dataset(count=258)

    def test_replay_enters_only_next_session_and_keeps_costs_explicit(self):
        result=simulate(deepcopy(self.data),snapshot())
        buys=[e for e in result['ledger']['audit'] if e['kind']=='buy']
        self.assertEqual(len(buys),1,result['issues'])
        self.assertEqual(timestamp(buys[0]['when']),timestamp(self.data['sessions'][255]['open'])+timedelta(minutes=5))
        self.assertGreater(D(result['metrics']['fees']),0)
        self.assertEqual(result['kind'],'synthetic')
        self.assertEqual(result['performance_validation'],'not_established')
        self.assertTrue(result['plans'])

    def test_gap_above_limit_rejects_without_buying(self):
        data=deepcopy(self.data)
        when=timestamp(data['sessions'][255]['open'])+timedelta(minutes=5)
        for e in data['events']:
            if e.get('symbol')=='TSLA' and timestamp(e['timestamp'])==when:
                e.update(bid='101',ask='101.02')
        r=simulate(data,snapshot())
        self.assertFalse(any(e['kind']=='buy' for e in r['ledger']['audit']))
        self.assertIn('gap_outside_band',{d['reason'] for d in r['execution_decisions']})

    def test_submitted_limit_waits_through_price_above_limit(self):
        data=deepcopy(self.data)
        opened=timestamp(data['sessions'][255]['open'])
        for e in data['events']:
            if e.get('symbol')!='TSLA': continue
            when=timestamp(e['timestamp'])
            if when==opened+timedelta(minutes=5): e['ask_size']=0
            if when==opened+timedelta(minutes=6): e.update(bid='101',ask='101.02')
        r=simulate(data,snapshot())
        buys=[e for e in r['ledger']['audit'] if e['kind']=='buy']
        self.assertEqual(len(buys),1)
        self.assertEqual(timestamp(buys[0]['when']),opened+timedelta(minutes=7))

    def test_submitted_limit_filled_below_stop_is_closed_immediately(self):
        data=deepcopy(self.data)
        opened=timestamp(data['sessions'][255]['open'])
        for e in data['events']:
            if e.get('symbol')!='TSLA': continue
            when=timestamp(e['timestamp'])
            if when==opened+timedelta(minutes=5): e['ask_size']=0
            if when==opened+timedelta(minutes=6): e.update(bid='90',ask='90.02')
        r=simulate(data,snapshot())
        cycles=[c for c in r['ledger']['closed_cycles'] if c['symbol']=='TSLA']
        self.assertEqual(len(cycles),1)
        self.assertEqual(cycles[0]['reason'],'stop')
        self.assertLess(D(cycles[0]['pnl']),0)

    def test_unfilled_entry_expires_after_thirty_minutes(self):
        data=deepcopy(self.data)
        opened=timestamp(data['sessions'][255]['open'])
        for e in data['events']:
            if e.get('symbol')=='TSLA' and opened<=timestamp(e['timestamp'])<opened+timedelta(minutes=30): e['ask_size']=0
        r=simulate(data,snapshot())
        self.assertFalse(any(e['kind']=='buy' for e in r['ledger']['audit']))
        self.assertTrue(any(o['status']=='canceled' for o in r['ledger']['orders'].values()))

    def test_stop_beats_target_when_same_bar_contains_both(self):
        data=deepcopy(self.data)
        opened=timestamp(data['sessions'][255]['open'])
        data['events'].append({'id':'ambiguous','kind':'bar','symbol':'TSLA',
            'start':(opened+timedelta(minutes=6)).isoformat(),'timestamp':(opened+timedelta(minutes=7)).isoformat(),
            'available_at':(opened+timedelta(minutes=7)).isoformat(),
            'open':'100','high':'120','low':'90','close':'100','source':'synthetic'})
        r=simulate(data,snapshot())
        cycle=next(c for c in r['ledger']['closed_cycles'] if c['symbol']=='TSLA')
        self.assertEqual(cycle['reason'],'stop')
        self.assertLess(D(cycle['pnl']),0)

    def test_partial_fill_cancels_remaining_quantity(self):
        data=deepcopy(self.data)
        when=timestamp(data['sessions'][255]['open'])+timedelta(minutes=5)
        for e in data['events']:
            if e.get('symbol')=='TSLA' and timestamp(e['timestamp'])==when: e['ask_size']=3
        r=simulate(data,snapshot())
        buys=[e for e in r['ledger']['audit'] if e['kind']=='buy']
        self.assertEqual([e['quantity'] for e in buys],[3])
        self.assertTrue(any(o['status']=='partial_canceled' for o in r['ledger']['orders'].values()))

    def test_protection_failure_is_closed_and_reported(self):
        data=deepcopy(self.data)
        when=timestamp(data['sessions'][255]['open'])+timedelta(minutes=4)
        data['events'].append({'id':'protection','kind':'fault','action':'protection_fail',
                              'timestamp':when.isoformat(),'available_at':when.isoformat(),'source':'synthetic'})
        r=simulate(data,snapshot())
        self.assertIn('protection_failure',{i['code'] for i in r['issues']})
        self.assertTrue(any(c['reason']=='protection_failure' for c in r['ledger']['closed_cycles']))

    def test_checkpoint_restart_is_identical_to_uninterrupted_run(self):
        full=simulate(deepcopy(self.data),snapshot())
        engine=Simulator(deepcopy(self.data),snapshot())
        engine.run(until=timestamp(self.data['sessions'][255]['open'])+timedelta(minutes=6))
        restored=Simulator.restore(deepcopy(self.data),snapshot(),engine.checkpoint())
        self.assertEqual(restored.run(),full)

    def test_cash_withdrawal_preserves_ca_and_marks_unfunded_benchmark_unavailable(self):
        data=deepcopy(self.data)
        when=timestamp(data['sessions'][255]['open'])+timedelta(minutes=1)
        data['events'].append({'id':'withdrawal','kind':'flow','amount':'-20000',
            'timestamp':when.isoformat(),'available_at':when.isoformat(),'source':'synthetic'})
        r=simulate(data,snapshot())
        self.assertEqual(r['ledger']['external_flows'],'-20000')
        self.assertIsNotNone(r['metrics'])
        self.assertIsNone(r['metrics']['benchmark_return'])
        self.assertIn('benchmark_flow_unavailable',{i['code'] for i in r['issues']})

    def test_duplicate_event_does_not_duplicate_execution(self):
        original=simulate(deepcopy(self.data),snapshot())
        data=deepcopy(self.data)
        data['events'].append(deepcopy(data['events'][400]))
        duplicate=simulate(data,snapshot())
        self.assertEqual(original['ledger'],duplicate['ledger'])

    def test_missing_initial_quote_does_not_create_fake_nav(self):
        data=deepcopy(self.data)
        opened=timestamp(data['sessions'][254]['open'])
        data['events']=[e for e in data['events'] if not(e.get('symbol')=='LLY' and timestamp(e['timestamp'])==opened)]
        result=simulate(data,snapshot())
        self.assertEqual(result['status'],'data_insufficient')
        self.assertIsNone(result['metrics'])

    def test_stress_costs_do_not_improve_identical_executions(self):
        normal=simulate(deepcopy(self.data),snapshot())
        stress=simulate(deepcopy(self.data),snapshot(),stress=True)
        self.assertGreater(D(stress['metrics']['fees']),D(normal['metrics']['fees']))
        self.assertLess(D(stress['metrics']['final_equity']),D(normal['metrics']['final_equity']))

    def test_overnight_gap_exits_on_opening_quote(self):
        data=deepcopy(self.data)
        when=timestamp(data['sessions'][256]['open'])
        for e in data['events']:
            if e.get('symbol')=='TSLA' and timestamp(e['timestamp'])==when: e.update(bid='90',ask='90.02')
        r=simulate(data,snapshot())
        sell=next(e for e in r['ledger']['audit'] if e['kind']=='sell' and e['symbol']=='TSLA')
        self.assertEqual(sell['reason'],'stop')
        self.assertLess(D(sell['price']),D(90))

    def test_time_exit_after_twenty_completed_sessions(self):
        data=make_dataset(count=277)
        r=simulate(data,snapshot())
        closed=[c for c in r['ledger']['closed_cycles'] if c['inherited']]
        self.assertEqual({c['symbol'] for c in closed},{'SPY','LLY'})
        self.assertTrue(all(c['reason']=='time_exit' and c['exit_index']==275 for c in closed),closed)

    def test_disconnected_controller_does_not_submit_new_entries(self):
        data=deepcopy(self.data)
        when=timestamp(data['sessions'][255]['open'])+timedelta(minutes=4)
        data['events'].append({'id':'offline','kind':'fault','action':'disconnect','timestamp':when.isoformat(),
                              'available_at':when.isoformat(),'source':'synthetic'})
        r=simulate(data,snapshot())
        self.assertFalse(any(e['kind']=='buy' for e in r['ledger']['audit']))
        self.assertIn('disconnected',{i['code'] for i in r['issues']})

    def test_queued_entry_rechecks_risk_after_price_shock(self):
        data=deepcopy(self.data)
        opened=timestamp(data['sessions'][255]['open'])
        for e in data['events']:
            when=timestamp(e['timestamp'])
            if e.get('symbol')=='TSLA' and when==opened+timedelta(minutes=5): e['ask_size']=0
            if e.get('symbol')=='SPY' and when==opened+timedelta(minutes=6): e.update(bid='200',ask='200.02')
        r=simulate(data,snapshot())
        self.assertFalse(any(e['kind']=='buy' for e in r['ledger']['audit']))

    def test_missing_final_marks_cannot_report_complete_returns(self):
        data=deepcopy(self.data)
        end=timestamp(data['sessions'][-1]['close'])-timedelta(minutes=2)
        data['events']=[e for e in data['events'] if timestamp(e['timestamp'])<=end]
        r=simulate(data,snapshot())
        self.assertEqual(r['status'],'data_insufficient')
        self.assertIsNone(r['metrics'])

    def test_trailing_applies_on_first_valid_quote_after_open(self):
        data=deepcopy(self.data)
        day=data['sessions'][255]['date']
        for bar in data['daily']:
            if bar['symbol']=='SPY' and bar['session']==day:
                bar.update(open='920',close='920',high='927',low='913')
        for e in data['events']:
            if e['symbol']=='SPY' and timestamp(data['sessions'][255]['open'])<=timestamp(e['timestamp'])<=timestamp(data['sessions'][255]['close']):
                e.update(bid='919.98',ask='920.02')
        opened=timestamp(data['sessions'][256]['open'])
        data['events']=[e for e in data['events'] if not(e['symbol']=='SPY' and timestamp(e['timestamp'])==opened)]
        r=simulate(data,snapshot())
        cycle=next(c for c in r['ledger']['closed_cycles'] if c['symbol']=='SPY')
        self.assertEqual(cycle['reason'],'trailing')
        self.assertEqual(cycle['exit_index'],256)

    def test_checkpoint_from_different_engine_is_rejected(self):
        engine=Simulator(deepcopy(self.data),snapshot())
        checkpoint=engine.checkpoint()
        checkpoint['engine_hash']='old-code'
        with self.assertRaises(ValueError): Simulator.restore(deepcopy(self.data),snapshot(),checkpoint)

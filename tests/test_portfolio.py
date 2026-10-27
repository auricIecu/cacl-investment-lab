import json
import unittest
from decimal import Decimal as D

from cacl_ca.portfolio import Ledger


def plan(symbol='TSLA'):
    return {'symbol':symbol,'sector':'Information Technology','limit':'100','stop':'95',
            'target':'110','adv20':'100000','instrument_id':symbol}


def position(symbol='SPY', quantity=100, mark='100', stop='95', sector='DIVERSIFIED_EQUITY_ETF'):
    return {'symbol':symbol,'quantity':quantity,'mark':mark,'stop':stop,'target':str(D(mark)+2*(D(mark)-D(stop))),
            'anchor':mark,'sector':sector,'entered_index':0,'inherited':True}


class PortfolioTests(unittest.TestCase):
    def test_risk_budget_and_cash_reserve_restrict_quantity(self):
        ledger=Ledger('100000')
        self.assertEqual(ledger.size(plan())['quantity'],80)
        limited=Ledger('10800',[position(quantity=892,mark='100',stop='99')])
        self.assertEqual(limited.equity,D(100000))
        self.assertEqual(limited.size(plan())['quantity'],7)

    def test_pending_orders_reserve_cash_risk_and_slots(self):
        ledger=Ledger('100000')
        first=ledger.reserve('one',plan())
        self.assertEqual(first['quantity'],80)
        self.assertEqual(ledger.reserved_cash,D('8008'))
        self.assertEqual(ledger.pending_risk,D(400))
        ledger.reserve('two',plan('AMD'))
        self.assertEqual(ledger.size(plan('NVDA'))['reason'],'entry_quota')
        ledger.cancel('one')
        self.assertEqual(ledger.reserved_cash,D('8008'))
        self.assertEqual(ledger.size(plan())['reason'],'entry_quota')

    def test_retry_and_restoration_do_not_duplicate_a_fill(self):
        ledger=Ledger('100000')
        ledger.reserve('one',plan())
        ledger.buy_fill('one',80,'100','fill1')
        self.assertEqual(ledger.cash,D('91999'))
        restored=Ledger.restore(json.loads(json.dumps(ledger.snapshot())))
        self.assertFalse(restored.buy_fill('one',80,'100','fill1'))
        self.assertEqual(restored.cash,D('91999'))
        self.assertEqual(restored.positions['TSLA']['quantity'],80)
        with self.assertRaises(ValueError): restored.buy_fill('one',79,'100','fill1')

    def test_sale_proceeds_are_unavailable_until_next_session(self):
        ledger=Ledger('100000')
        ledger.reserve('one',plan())
        ledger.buy_fill('one',80,'100','b1')
        ledger.sell('TSLA',80,'110',0,'s1','target')
        self.assertEqual(ledger.cash,D('91999'))
        self.assertEqual(ledger.equity,D('100798'))
        ledger.open_session(1)
        self.assertEqual(ledger.cash,D('100798'))
        self.assertEqual(ledger.closed_cycles[0]['pnl'],'798')

    def test_partial_fill_cancels_rest_and_failure_blocks_new_entries(self):
        ledger=Ledger('100000')
        ledger.reserve('one',plan())
        ledger.buy_fill('one',30,'100','b1',protected=False)
        self.assertEqual(ledger.positions['TSLA']['quantity'],30)
        self.assertEqual(ledger.reserved_cash,D(0))
        self.assertEqual(ledger.size(plan('AMD'))['reason'],'protection_failure')
        with self.assertRaises(ValueError): ledger.sell('TSLA',31,'90',0,'s1','emergency')

    def test_flow_does_not_create_returns_or_reset_high_water_mark(self):
        ledger=Ledger('100000')
        ledger.flow('20000','flow1')
        self.assertEqual(ledger.nav,D(100))
        self.assertEqual(ledger.units,D(1200))
        self.assertEqual(ledger.update_brake()['drawdown'],D(0))
        ledger.flow('-20000','flow2')
        self.assertEqual(ledger.nav,D(100))

    def test_dividend_is_return_and_is_not_cash_before_pay_day(self):
        ledger=Ledger('90000',[position()])
        ledger.dividend('SPY','1',2,'div1')
        self.assertEqual(ledger.cash,D(90000))
        self.assertEqual(ledger.equity,D(100100))
        ledger.mark('SPY','99')
        self.assertEqual(ledger.nav,D(100))
        ledger.open_session(1)
        self.assertEqual(ledger.cash,D(90000))
        ledger.open_session(2)
        self.assertEqual(ledger.cash,D(90100))

    def test_split_changes_quantity_and_levels_without_changing_equity(self):
        ledger=Ledger('90000',[position()])
        ledger.split('SPY','2','split1')
        self.assertEqual(ledger.positions['SPY']['quantity'],200)
        self.assertEqual(ledger.positions['SPY']['stop'],D('47.50'))
        self.assertEqual(ledger.equity,D(100000))
        self.assertFalse(ledger.split('SPY','2','split1'))

    def test_fractional_split_is_not_silently_rounded(self):
        ledger=Ledger('99900',[position(quantity=1)])
        with self.assertRaises(ValueError): ledger.split('SPY','0.5','split1')
        self.assertEqual(ledger.positions['SPY']['quantity'],1)

    def test_brake_recovers_one_level_after_five_distinct_closes(self):
        ledger=Ledger('0',[position(quantity=1000)])
        ledger.mark('SPY','90')
        self.assertEqual(ledger.update_brake()['level'],2)
        ledger.mark('SPY','93')
        for i in range(4): self.assertEqual(ledger.update_brake(close_session=i)['level'],2)
        self.assertEqual(ledger.update_brake(close_session=3)['level'],2)
        self.assertEqual(ledger.update_brake(close_session=4)['level'],1)
        ledger.mark('SPY','85')
        self.assertEqual(ledger.update_brake()['level'],4)
        ledger.mark('SPY','100')
        for i in range(5,20): ledger.update_brake(close_session=i)
        self.assertEqual(ledger.level,4)

    def test_brake_reduction_respects_gross_and_risk_together(self):
        ledger=Ledger('20000',[position('AMD',100,'400','380','Information Technology'),
                               position('LLY',200,'200','190','Health Care')])
        ledger.level=2
        self.assertEqual(ledger.reduction_targets(),{'AMD':50,'LLY':100})

    def test_trailing_stop_never_moves_backwards(self):
        ledger=Ledger('90000',[position()])
        ledger.queue_stop('SPY','106','3')
        self.assertEqual(ledger.positions['SPY']['next_stop'],D(100))
        ledger.activate_stop('SPY')
        ledger.queue_stop('SPY','109','2')
        ledger.activate_stop('SPY')
        ledger.queue_stop('SPY','108','3')
        self.assertEqual(ledger.positions['SPY']['next_stop'],D(105))

    def test_limits_and_cooldown_cannot_be_bypassed(self):
        ledger=Ledger('100000')
        self.assertEqual(ledger.size(dict(plan(),adv20='2500'))['quantity'],25)
        ledger.reserve('one',plan())
        ledger.buy_fill('one',80,'100','b1')
        ledger.sell('TSLA',80,'110',0,'s1','target')
        ledger.open_session(5)
        self.assertEqual(ledger.size(plan())['reason'],'cooldown')
        ledger.open_session(6)
        self.assertGreater(ledger.size(plan())['quantity'],0)

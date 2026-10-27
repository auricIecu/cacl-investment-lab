import unittest
from copy import deepcopy

from examples.phase3_synthetic import make_dataset, SYMBOLS
from cacl_ca.market_data import validate_dataset, history_as_of
from cacl_ca.strategy import evaluate_signals, indicators


class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = make_dataset(intraday=False)

    def test_s2_candidate_uses_nine_binary_points_and_expected_levels(self):
        data = validate_dataset(deepcopy(self.data), SYMBOLS)
        report = evaluate_signals(data, 254)
        tsla = next(d for d in report['decisions'] if d['symbol'] == 'TSLA')
        self.assertEqual(tsla['decision'], 'candidate', tsla)
        self.assertEqual(len(tsla['points']), 9)
        self.assertGreaterEqual(tsla['score'], 6)
        self.assertEqual(tsla['limit'], '100.50')
        # TR sum = 14*2.4 + .92 + 4*.4 + .98 = 37.10; ATR20=1.855.
        self.assertEqual(tsla['stop'], '96.29')
        self.assertEqual(tsla['target'], '108.92')
        self.assertEqual(tsla['points'][-1], 0)

    def test_future_revision_does_not_change_an_earlier_plan(self):
        data = validate_dataset(deepcopy(self.data), SYMBOLS)
        before = evaluate_signals(data, 254)
        revised = deepcopy(next(b for b in data['daily'] if b['symbol']=='TSLA' and b['session']==data['sessions'][254]['date']))
        revised.update(close='10000', high='10000', available_at=data['sessions'][256]['close'])
        data['daily'].append(revised)
        after = evaluate_signals(data, 254)
        self.assertEqual(before, after)

    def test_missing_day_does_not_fill_forward_or_shorten_window(self):
        data = deepcopy(self.data)
        data['daily'] = [b for b in data['daily'] if not (b['symbol']=='TSLA' and b['session']==data['sessions'][200]['date'])]
        self.assertEqual(history_as_of(data, 'TSLA', 254), [])
        decision = next(d for d in evaluate_signals(data,254)['decisions'] if d['symbol']=='TSLA')
        self.assertIn('invalid_data', decision['reasons'])

    def test_missing_vix_blocks_even_a_valid_pattern(self):
        data = deepcopy(self.data)
        data['vix'] = []
        report = evaluate_signals(data,254)
        self.assertFalse(report['market']['passed'])
        self.assertFalse(any(d['decision']=='candidate' for d in report['decisions']))

    def test_bad_prices_and_outside_ca_symbols_are_rejected(self):
        for edit in ('nan', 'ohlc', 'symbol', 'timezone', 'duplicate', 'calendar', 'sector'):
            with self.subTest(edit=edit):
                data = deepcopy(self.data)
                if edit=='nan': data['daily'][0]['close']='NaN'
                if edit=='ohlc': data['daily'][0]['low']='10000'
                if edit=='symbol': data['instruments'][0]['source_symbol']='OUTSIDE_CA'
                if edit=='timezone': data['daily'][0]['available_at']='2025-01-01T17:00:00'
                if edit=='duplicate': data['daily'].append(dict(data['daily'][0],close='40.1'))
                if edit=='calendar': data['sessions'][0]['open']='2024-12-31T09:30:00-05:00'
                if edit=='sector': data['instruments'][0]['sector']='unknown'
                with self.assertRaises(ValueError): validate_dataset(data, SYMBOLS)

    def test_more_than_twenty_percent_missing_blocks_coverage(self):
        data = deepcopy(self.data)
        excluded = set(SYMBOLS[:5])
        data['daily'] = [b for b in data['daily'] if b['symbol'] not in excluded]
        result = evaluate_signals(data,254)
        self.assertFalse(result['market']['passed'])
        self.assertFalse(any(d['decision']=='candidate' for d in result['decisions']))

    def test_indicator_window_requires_254_bars(self):
        bars = history_as_of(self.data, 'TSLA', 254)
        with self.assertRaises(ValueError): indicators(bars[:-1])

    def test_known_split_preserves_economic_series_without_future_adjustment(self):
        data = deepcopy(self.data)
        day=data['sessions'][254]
        data['actions']=[{'id':'split','kind':'split','symbol':'TSLA','session':day['date'],
                          'ratio':'2','available_at':day['open'],'source':'synthetic'}]
        before=history_as_of(data,'TSLA',253)
        current=history_as_of(data,'TSLA',254)
        self.assertEqual(before[-1]['close'],'99.12')
        self.assertEqual(current[-2]['close'],'49.56')
        self.assertEqual(current[-2]['volume'],2000000)
        data['actions'].append(deepcopy(data['actions'][0]))
        self.assertEqual(history_as_of(data,'TSLA',254),current)

    def test_ineligible_instrument_still_requires_identity_fields(self):
        data=deepcopy(self.data)
        data['instruments'][0]['eligible']=False
        del data['instruments'][0]['sector']
        with self.assertRaises(ValueError): validate_dataset(data,SYMBOLS)

    def test_earnings_published_after_cutoff_does_not_score(self):
        data = deepcopy(self.data)
        data['earnings']=[{'id':'earn','symbol':'TSLA','published_at':data['sessions'][255]['open'],
            'available_at':data['sessions'][255]['open'],'source':'https://issuer.example/report',
            'locator':'quarterly table','verified':True,'basis':'GAAP','period':'quarter',
            'quarter':3,'prior_quarter':3,'fiscal_year':2025,'prior_fiscal_year':2024,
            'currency':'USD','prior_currency':'USD','eps_unit':'USD/share','prior_eps_unit':'USD/share',
            'revenue_unit':'USD','prior_revenue_unit':'USD','eps':'1.20','prior_eps':'1',
            'revenue':'110','prior_revenue':'100'}]
        r=evaluate_signals(data,254)
        self.assertEqual(next(d for d in r['decisions'] if d['symbol']=='TSLA')['points'][-1],0)
        data['earnings'][0].update(published_at=data['sessions'][254]['close'],available_at=data['sessions'][254]['close'])
        r=evaluate_signals(data,254)
        self.assertEqual(next(d for d in r['decisions'] if d['symbol']=='TSLA')['points'][-1],1)
        data['earnings'][0]['prior_revenue_unit']='million_USD'
        r=evaluate_signals(data,254)
        self.assertEqual(next(d for d in r['decisions'] if d['symbol']=='TSLA')['points'][-1],0)

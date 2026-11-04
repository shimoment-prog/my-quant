"""Mock API tests: correctness of decisions, not a market backtest."""

import datetime as dt
import importlib.util
from pathlib import Path
import sys
import types
import unittest

import pandas as pd


def load_strategy():
    fake = types.ModuleType('jqdata')
    fake.__all__ = []
    original = sys.modules.get('jqdata')
    sys.modules['jqdata'] = fake
    try:
        path = Path(__file__).with_name('smallcap_roe_rank.py')
        spec = importlib.util.spec_from_file_location('smallcap_roe_under_test', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original is None:
            sys.modules.pop('jqdata', None)
        else:
            sys.modules['jqdata'] = original


class Field:
    def in_(self, codes):
        return codes


class Query:
    def filter(self, expression):
        return self


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.s = load_strategy()
        self.context = types.SimpleNamespace(
            current_dt=dt.datetime(2026, 11, 4, 9, 31),
            previous_date=dt.date(2026, 11, 3),
            run_params=types.SimpleNamespace(frequency='minute'),
            portfolio=types.SimpleNamespace(total_value=100000., available_cash=100000., positions={}),
        )
        self.orders = []
        self.order_styles = []
        self.open_orders = {}
        self.fundamental_dates = []
        self.index_dates = []
        self.codes = ['600001.XSHG', '600002.XSHG', '600003.XSHG']
        self.quotes = {code: self.quote() for code in self.codes}
        self.frame = pd.DataFrame({
            'code': self.codes, 'market_cap': [10., 20., 30.], 'roe': [30., 20., 10.],
        })
        s = self.s
        s.g = types.SimpleNamespace()
        s.log = types.SimpleNamespace(info=lambda *_: None, warn=lambda *_: None,
                                      set_level=lambda *_: None)
        s.set_benchmark = lambda *_: None
        s.set_option = lambda *_: None
        s.set_slippage = lambda *_: None
        s.set_order_cost = lambda *_, **__: None
        s.PriceRelatedSlippage = lambda value: value
        s.MarketOrderStyle = lambda value: ('market_protection', value)
        s.OrderCost = lambda **kwargs: kwargs
        s.run_daily = lambda *_, **__: None
        s.get_current_data = lambda: self.quotes
        s.get_open_orders = lambda: self.open_orders
        s.order_target_value = self.submit_order
        s.valuation = types.SimpleNamespace(code=Field(), market_cap=Field())
        s.indicator = types.SimpleNamespace(roe=Field())
        s.query = lambda *_: Query()
        s.get_index_stocks = self.index_stocks
        s.get_fundamentals = self.fundamentals
        s.attribute_history = self.history
        s.initialize(self.context)

    @staticmethod
    def quote(price=10., paused=False):
        return types.SimpleNamespace(last_price=price, paused=paused, high_limit=11., low_limit=9.)

    def history(self, code, count, *args, **kwargs):
        self.assertEqual(kwargs['skip_paused'], False)
        index = pd.bdate_range(end=self.context.previous_date, periods=count)
        return pd.DataFrame({'paused': [0] * count}, index=index)

    def index_stocks(self, code, date):
        self.index_dates.append(date)
        return self.codes

    def fundamentals(self, query, date):
        self.fundamental_dates.append(date)
        return self.frame.copy()

    def submit_order(self, code, target, **kwargs):
        self.orders.append((code, target))
        self.order_styles.append(kwargs.get('style'))
        return types.SimpleNamespace(security=code)

    def position(self, code, amount=100, sellable=100, locked=0, price=10.):
        self.context.portfolio.positions[code] = types.SimpleNamespace(
            total_amount=amount, locked_amount=locked,
            closeable_amount=sellable, price=price,
        )

    def plan(self, targets, value=49000.):
        self.s.g.has_plan = True
        self.s.g.plan_date = self.context.current_dt.date()
        self.s.g.target_codes = targets
        self.s.g.target_value = value

    def test_smaller_size_and_higher_roe_both_improve_rank(self):
        ranked = self.s.rank_factors(self.frame)
        self.assertEqual(ranked['code'].tolist(), self.codes)
        self.assertEqual(ranked['score'].tolist(), [2., 4., 6.])

    def test_missing_roe_uses_cross_section_mean_and_negative_is_allowed(self):
        self.frame['roe'] = [-10., None, 30.]
        ranked = self.s.rank_factors(self.frame).set_index('code')
        self.assertEqual(ranked.loc[self.codes[1], 'roe'], 10.)
        self.assertEqual(ranked.loc[self.codes[0], 'roe'], -10.)

    def test_tied_factors_are_deterministic_under_input_shuffle(self):
        self.frame['market_cap'] = 10.
        self.frame['roe'] = 20.
        result = self.s.rank_factors(self.frame.iloc[::-1])
        self.assertEqual(result['code'].tolist(), self.codes)

    def test_unavailable_factors_do_not_liquidate_existing_plan(self):
        self.plan([self.codes[2]])
        self.frame['roe'] = None
        self.s.prepare_plan(self.context)
        self.assertEqual(self.s.g.target_codes, [self.codes[2]])
        self.assertEqual(self.orders, [])

    def test_index_and_fundamentals_use_previous_trading_date(self):
        self.s.prepare_plan(self.context)
        self.assertEqual(self.index_dates, [self.context.previous_date])
        self.assertEqual(self.fundamental_dates, [self.context.previous_date])

    def test_rebalance_interval_counts_trading_sessions_not_calendar_days(self):
        sessions = list(pd.bdate_range('2026-09-07', periods=17))
        sessions.pop(5)  # Simulated exchange holiday; no callback that day.
        for i, session in enumerate(sessions):
            self.context.current_dt = session.to_pydatetime().replace(hour=9, minute=31)
            self.context.previous_date = (session - pd.offsets.BDay()).date()
            self.s.prepare_plan(self.context)
            self.assertEqual(len(self.fundamental_dates), 1 if i < 15 else 2)
        self.assertEqual(self.s.g.plan_date, sessions[15].date())

    def test_duplicate_prepare_on_same_date_does_not_advance_counter(self):
        self.s.prepare_plan(self.context)
        self.s.prepare_plan(self.context)
        self.assertEqual(self.s.g.session_count, 1)
        self.assertEqual(len(self.fundamental_dates), 1)

    def test_history_containing_today_is_rejected(self):
        def future_history(*args, **kwargs):
            return pd.DataFrame({'paused': [0] * 63},
                                index=pd.bdate_range(end=self.context.current_dt, periods=63))
        self.s.attribute_history = future_history
        self.s.prepare_plan(self.context)
        self.assertEqual(self.fundamental_dates, [])
        self.assertFalse(self.s.g.has_plan)

    def test_t_plus_one_then_retry_after_position_becomes_sellable(self):
        code = self.codes[0]
        self.plan([self.codes[1]])
        self.position(code, sellable=0)
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [])
        self.context.current_dt += dt.timedelta(days=1)
        self.context.portfolio.positions[code].closeable_amount = 100
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [(code, 0.)])

    def test_limit_down_exit_is_retained_and_retried_when_unlocked(self):
        code = self.codes[0]
        self.plan([self.codes[1]])
        self.position(code)
        self.quotes[code].last_price = 9.
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [])
        self.quotes[code].last_price = 9.5
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [(code, 0.)])

    def test_unsold_old_positions_still_occupy_hold_slots(self):
        self.s.g.hold_num = 2
        self.plan([self.codes[2]])
        self.position(self.codes[0])
        self.position(self.codes[1], amount=0, sellable=0, locked=100)
        self.s.execute_buys(self.context)
        self.assertEqual(self.orders, [])

    def test_pending_buy_is_not_duplicated(self):
        code = self.codes[0]
        self.plan([code])
        self.position(code, amount=100, sellable=0)
        self.open_orders['one'] = types.SimpleNamespace(
            security=code, is_buy=True, amount=400, filled=100,
        )
        self.s.execute_buys(self.context)
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [])

    def test_pending_buys_and_locked_shares_reserve_gross_exposure(self):
        self.s.g.hold_num = 4
        self.plan([self.codes[2]], value=80000.)
        self.position(self.codes[0], amount=2000, locked=1000)
        self.open_orders['one'] = types.SimpleNamespace(
            security=self.codes[1], is_buy=True, amount=2000, filled=0,
        )
        self.s.execute_buys(self.context)
        self.assertEqual(len(self.orders), 1)
        self.assertLessEqual(self.orders[0][1], 48000.)

    def test_budget_is_reserved_even_when_broker_positions_update_later(self):
        self.plan(self.codes, value=49000.)
        self.s.execute_buys(self.context)
        self.assertLessEqual(sum(value for _, value in self.orders), 98000.)

    def test_existing_star_market_position_still_needs_200_share_buy(self):
        code = '688001.XSHG'
        self.quotes[code] = self.quote()
        self.position(code, amount=200, sellable=200)
        self.plan([code], value=3500.)  # Additional 150 shares cannot be submitted.
        self.s.execute_buys(self.context)
        self.assertEqual(self.orders, [])

    def test_star_market_order_has_price_protection(self):
        code = '688001.XSHG'
        self.quotes[code] = self.quote()
        self.plan([code], value=5000.)
        self.s.execute_buys(self.context)
        self.assertEqual(self.order_styles, [('market_protection', 11.)])
        self.orders.clear()
        self.order_styles.clear()
        self.position(code, amount=200, sellable=200)
        self.plan([self.codes[0]])
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [(code, 0.)])
        self.assertEqual(self.order_styles, [('market_protection', 9.)])

    def test_partial_sellability_preserves_unavailable_shares(self):
        code = self.codes[0]
        self.position(code, amount=400, sellable=100)
        self.plan([self.codes[1]])
        self.s.execute_reductions(self.context)
        self.assertEqual(self.orders, [(code, 3000.)])

    def test_no_buy_outside_rebalance_day(self):
        self.plan([self.codes[0]])
        self.context.current_dt += dt.timedelta(days=1)
        self.s.execute_buys(self.context)
        self.assertEqual(self.orders, [])

    def test_stale_portfolio_valuation_cannot_turn_buy_branch_into_sell(self):
        code = self.codes[0]
        self.position(code, amount=1000, sellable=1000, price=8.)
        self.quotes[code].last_price = 10.
        self.plan([code], value=9500.)
        self.s.execute_buys(self.context)
        self.assertEqual(self.orders, [])


if __name__ == '__main__':
    unittest.main()

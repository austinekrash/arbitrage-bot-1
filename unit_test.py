import time
import unittest
from trader.trade_manager.order_watcher_stats import OrderWatcherStats


class SimpleTest(unittest.TestCase):

    def test_order_watcher_stats_add_remove(self):
        OrderWatcherStats.initialize()
        ows = OrderWatcherStats.instance()
        bef = tuple(ows._active)

        # add
        ows.started("huhu")
        time.sleep(0.5)

        # remove
        ows.done("huhu")
        time.sleep(0.5)

        aft = tuple(ows._active)
        print(ows.get_stats())
        ows.tear_down()
        self.assertEqual(bef, aft)

    def test_order_watcher_stats_delayed(self):
        OrderWatcherStats.initialize()
        ows = OrderWatcherStats.instance()

        # add
        ows.started("huhu")
        ows.started("huhu2")
        time.sleep(0.5)

        # delayed
        ows.delayed("huhu")
        time.sleep(0.5)

        stats = ows.get_stats()
        print(ows._active)
        print(stats)
        delayed_count = stats.get("current_delayed_count")
        ows.tear_down()
        self.assertEqual(1, delayed_count)

    def test_order_watcher_stats_error(self):
        OrderWatcherStats.initialize()
        ows = OrderWatcherStats.instance()

        # add
        ows.started("huhu")
        time.sleep(0.5)

        # delayed
        ows.error("huhu")
        time.sleep(0.5)

        stats = ows.get_stats()
        print(ows._active)
        print(stats)
        error_count = stats.get("total_error_count")
        active_count = stats.get("current_active_count")
        ows.tear_down()
        self.assertEqual(1, error_count)
        self.assertEqual(0, active_count)


if __name__ == "__main__":
    unittest.main()

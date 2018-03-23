from .market import Market
from config.global_conf import Global


class Balance:
    def __init__(self, market: Market, balance_dict: dict = None):
        self.market = market
        self._balance_dict = self.filter_target_coins(balance_dict)

    def update(self, balance_dict: dict):
        self._balance_dict = self.filter_target_coins(balance_dict)

    def __repr__(self):
        repr_str = "<%s Balance>:" % self.market.value

        for coin in self._balance_dict.keys():
            val = self._balance_dict[coin]
            repr_str += "\n %s { %f available, %f trade_in_use, %f in total }" % \
                        (coin, val["available"], val["trade_in_use"], val["balance"])

        return repr_str

    def to_dict(self):
        clone = dict(self._balance_dict)
        clone["market"] = self.market.value
        return clone

    @staticmethod
    def filter_target_coins(balance_dict: dict):
        result = dict()
        for coin in Global.COIN_FILTER_FOR_BALANCE:
            result[coin] = balance_dict[coin]
        return result

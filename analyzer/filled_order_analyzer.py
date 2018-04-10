import logging


class TakeType:
    # minask 가격에서 이뤄진 매수체결, maker => sell, taker => buy
    BUY = "buy"
    # maxbid 가격에서 이뤄진 매도체결, taker => buy, maker => sell
    SELL = "sell"


class FilledOrderAnalyzer:
    @staticmethod
    def get_filled_orders_within(prev_filled_orders: list, curr_filled_orders: list):
        if len(curr_filled_orders) == 0:
            return list()
        if len(prev_filled_orders) == 0:
            return list(curr_filled_orders)
        return list(curr_filled_orders[:curr_filled_orders.index(prev_filled_orders[0])])

    @staticmethod
    def set_take_type_from_orderbook(filled_orders_within: list, orderbook: dict):
        # if len(filled_orders_within) == 0:
        #     return

        # convert from bson decimal128 to python decimal for calculation
        min_ask_price = orderbook["asks"][0]["price"].to_decimal()
        max_bid_price = orderbook["bids"][0]["price"].to_decimal()

        for filled_order in filled_orders_within:
            # get price of filled order
            filled_order_price = filled_order["price"].to_decimal()

            # get diff
            min_ask_diff = abs(min_ask_price - filled_order_price)
            max_bid_diff = abs(max_bid_price - filled_order_price)

            # get nearest type of order
            if min_ask_diff < max_bid_diff:
                filled_order["takeType"] = TakeType.BUY
            elif max_bid_diff < min_ask_diff:
                filled_order["takeType"] = TakeType.SELL
            else:
                # min_ask_diff == max_bid_diff
                logging.warning("min_ask_diff = max_bid_diff!")
                # deem it as buy order
                filled_order["takeType"] = TakeType.BUY

import logging

import pymongo

from analyzer.trade_analyzer import MCTSAnalyzer
from analyzer.trade_analyzer import SpreadInfo
from config.global_conf import Global
from config.shared_mongo_client import SharedMongoClient
from trader.base_arb_bot import BaseArbBot
from trader.market.trade import Trade, TradeTag, TradeMeta
from trader.market_manager.market_manager import MarketManager


class RiskFreeArbBotV4(BaseArbBot):

    def __init__(self, target_currency: str, mm1: MarketManager, mm2: MarketManager, is_test: bool):
        mm1_name = mm1.get_market_name().lower()
        mm2_name = mm2.get_market_name().lower()

        if is_test:
            self.trade_commander_col = SharedMongoClient.get_test_streamer_db()["trade_commander"]
            self.balance_commander_col = SharedMongoClient.get_test_streamer_db()["balance_commander"]
        if not is_test:
            self.trade_commander_col = SharedMongoClient.get_streamer_db(
                target_currency, mm1_name, mm2_name)["trade_commander"]
            self.balance_commander_col = SharedMongoClient.get_streamer_db(
                target_currency, mm1_name, mm2_name)["balance_commander"]

        self.trade_strategy = MCTSAnalyzer.min_coin_tradable_spread_strategy

        super().__init__(mm1, mm2, target_currency)

    def run(self):
        while True:
            self.execute_trade_loop()

            if self.is_settlement:
                # handle rest of settlement
                self.settlement_handler()
                break

    def actual_trade_loop(self, mm1_data=None, mm2_data=None):

        # get latest trade_commander dict from db
        trade_commander = self.trade_commander_col.find_one(
            sort=[('_id', pymongo.DESCENDING)]
        )

        # check if settlement reached
        if trade_commander["condition"]["is_settlement"] is True:
            self.is_settlement = True
            return

        # if not execute trade, return
        execute_cond = trade_commander["execute_trade"]
        if (execute_cond["new"] is False) and (execute_cond["rev"] is False):
            logging.warning("Trade Streamer decided not to trade.. check below to see what caused this decision")

            logging.warning("[TimeFlow > Exhaust] -> NEW: %s, REV: %s"
                            % (trade_commander["condition"]["new"]["is_time_flow_above_exhaust"],
                               trade_commander["condition"]["rev"]["is_time_flow_above_exhaust"]))
            logging.warning("[Under Opportunity] -> NEW: %s, REV: %s"
                            % (trade_commander["condition"]["new"]["is_oppty"],
                               trade_commander["condition"]["rev"]["is_oppty"]))

            # post balance_commander empty data to reset
            self.balance_commander_col.insert_one(dict(is_bal_update=False))
            return

        # when execute trade
        # get orderbook data
        mm1_data = self.mm1.get_orderbook(self.mm1_currency)
        mm2_data = self.mm2.get_orderbook(self.mm2_currency)

        # get spread info from given trade strategy
        result = self.trade_strategy(
            mm1_data,
            mm2_data,
            self.mm1.taker_fee,
            self.mm2.taker_fee,
            trade_commander["streamer_mtcu"]
        )
        new_spread_info: SpreadInfo = result["new"]
        rev_spread_info: SpreadInfo = result["rev"]

        # init checker
        new_trade = None
        rev_trade = None

        # NEW
        if new_spread_info.spread_in_unit > 0:
            if new_spread_info.able_to_trade:
                new_trade = self.execute_trade(new_spread_info, trade_commander["threshold"]["new"], "new")
                self.add_trade(new_trade)
            else:
                logging.error("Trade Analyzer decided not to trade NEW.. See following failed reason:\n'%s'"
                              % new_spread_info.fail_reason)

        # REVERSE
        if rev_spread_info.spread_in_unit > 0:
            if rev_spread_info.able_to_trade:
                rev_trade = self.execute_trade(rev_spread_info, trade_commander["threshold"]["rev"], "rev")
                self.add_trade(rev_trade)
            else:
                logging.error("Trade Analyzer decided not to trade REV.. See following failed reason:\n'%s'"
                              % rev_spread_info.fail_reason)

        # update balance if there was any trade
        if new_trade or rev_trade:
            self.mm1.update_balance()
            self.mm2.update_balance()
            # fixme: ?????? ??????????????? ????????? ??????????????? ??????..
            self.balance_commander_col.insert_one(dict(is_bal_update=True))
        else:
            # post balance_commander empty data to reset
            self.balance_commander_col.insert_one(dict(is_bal_update=False))

    def execute_trade(self, spread_info: SpreadInfo, mtcu_threshold_dict: dict, trade_type: str):
        if trade_type == "new":
            buying_mkt = self.mm1
            selling_mkt = self.mm2
            buying_currency = self.mm1_currency
            selling_currency = self.mm2_currency
        elif trade_type == "rev":
            buying_mkt = self.mm2
            selling_mkt = self.mm1
            buying_currency = self.mm2_currency
            selling_currency = self.mm1_currency
        else:
            raise Exception("Invalid trade type!")

        if not buying_mkt.is_bigger_than_min_trading_coin(spread_info.buy_order_amt, self.target_currency):
            logging.warning("buy amount smaller than min trading coin: %d" % spread_info.buy_order_amt)
            return None

        if not selling_mkt.is_bigger_than_min_trading_coin(spread_info.sell_order_amt, self.target_currency):
            logging.warning("sell amount smaller than min trading coin: %d" % spread_info.sell_order_amt)
            return None

        # obey each order amount to exchange min order digit
        spread_info.buy_order_amt = round(spread_info.buy_order_amt,
                                          Global.read_min_order_digit(buying_mkt.get_market_name()))
        spread_info.sell_order_amt = round(spread_info.sell_order_amt,
                                           Global.read_min_order_digit(selling_mkt.get_market_name()))

        # check condition
        threshold_cond = spread_info.spread_to_trade >= mtcu_threshold_dict["normal"]

        # quit if conditions don't meet
        if not threshold_cond:
            logging.warning("< Spread threshold condition not met! >")
            logging.warning("---------------------------------------------------------")
            logging.critical("Spread To Trade: %.2f" % spread_info.spread_to_trade)
            logging.warning("MTCU Normal Threshold: %.2f" % mtcu_threshold_dict["normal"])
            logging.warning("MTCU Royal Threshold: %.2f" % mtcu_threshold_dict["royal"])
            logging.warning("---------------------------------------------------------")
            return None

        # balance check
        krw_needed = spread_info.buy_unit_price * spread_info.buy_order_amt
        coin_needed = spread_info.sell_order_amt
        has_enough_krw = self.has_enough_coin_checker(buying_mkt, "krw", krw_needed)
        has_enough_coin = self.has_enough_coin_checker(selling_mkt, self.target_currency, coin_needed)

        # not enough krw
        if not has_enough_krw:
            logging.warning("Not enough KRW in buying market!")
            return None

        # not enough coin
        if not has_enough_coin:
            logging.warning("Not enough %s in selling market!" % self.target_currency.upper())
            return None

        # fixme: ????????? ???????????? --> buy?????? ??????????????? ???????????? exception???????????? sell?????? ????????? ??????..
        # fixme: ????????? buy?????? ???????????? sell?????? ?????????????????? ????????? ???????????????..
        # fixme: ??? ?????? tread??? run???????????? ???????
        buy_order = buying_mkt.order_buy(buying_currency, spread_info.buy_unit_price, spread_info.buy_order_amt)
        sell_order = selling_mkt.order_sell(selling_currency, spread_info.sell_unit_price, spread_info.sell_order_amt)

        # make buy & sell order
        logging.critical("========[ Successful Trade INFO ]========================")
        logging.critical("Trade Type: %s" % trade_type.upper())
        logging.critical("Traded Spread: %.2f" % spread_info.spread_to_trade)
        logging.critical("MTCU Normal Threshold: %.2f" % mtcu_threshold_dict["normal"])
        logging.critical("MTCU Royal Threshold: %.2f" % mtcu_threshold_dict["royal"])
        logging.critical("---------------------------------------------------------")
        logging.critical("Buying Price: %.2f" % spread_info.buy_unit_price)
        logging.critical("Buying Amount: %f" % spread_info.buy_order_amt)
        logging.critical("Selling Price: %.2f" % spread_info.sell_unit_price)
        logging.critical("Selling Price: %f" % spread_info.sell_order_amt)
        logging.critical("---------------------------------------------------------")

        return Trade(getattr(TradeTag, trade_type.upper()), [buy_order, sell_order], TradeMeta({}))

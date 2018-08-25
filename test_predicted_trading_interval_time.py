import logging
from config.global_conf import Global
from config.shared_mongo_client import SharedMongoClient
from trader.trade_manager.trade_streamer import TradeStreamer


def main(coin_name: str, mm1_name: str, mm2_name: str, mm1_krw_bal: float, mm2_krw_bal: float):
    Global.configure_default_root_logging(should_log_to_file=False, log_level=logging.INFO)
    SharedMongoClient.initialize(should_use_localhost_db=False)

    streamer_settings = {
        "mm1_name": mm1_name,
        "mm2_name": mm2_name,
        "target_currency": coin_name,
        "mm1_krw_bal": mm1_krw_bal,
        "mm2_krw_bal": mm2_krw_bal,
    }

    trade_streamer = TradeStreamer(is_initiation_mode=True, is_trading_mode=False, streamer_settings=streamer_settings)
    result = trade_streamer.real_time_streamer()
    logging.critical("Streamer Initiation Mode result")
    print(result)


if __name__ == '__main__':
    main("btc", "gopax", "okcoin", 1000000, 0)
